"""ARIA — Batch 4 Multi-Platform Crawl Service (Proxycurl + Serper).

This module is the single backend chokepoint for prospect/company crawls
across LinkedIn (Proxycurl) and Google web/news (Serper). API keys are
pulled from the encrypted `integration_configs` MongoDB collection that
the Universal OAuth UI (Batch 1) writes to — NEVER from `.env`.

Public surface
──────────────
    from services.crawl_service import (
        crawl_prospect,         # → orchestrated 4-6 call enrichment
        CrawlLimitExceeded,
        MissingCredential,
    )

Architectural guarantees
────────────────────────
  • Hard cap of 8 external API calls per prospect (per tenant).
  • All keys decrypted at call-time, never logged.
  • Graceful per-source failure: a missing or invalid Proxycurl key
    does not block Serper, and vice-versa.
  • Returns a stable dict shape so downstream Claude synthesis is
    deterministic across crawl outcomes.

Used by
───────
  • `services/intel_service.py` — for Claude-powered synthesis.
  • `routes/intel.py`           — for the /api/intel REST endpoints.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from deps import db
from security.encryption import decrypt

logger = logging.getLogger("crawl_service")

# ─── Constants ──────────────────────────────────────────────────────────
PROXYCURL_BASE = "https://nubela.co"
SERPER_BASE = "https://google.serper.dev"
DEFAULT_TIMEOUT = httpx.Timeout(15.0, connect=10.0)
MAX_CALLS_PER_PROSPECT = 8  # Batch 4 architectural cap

_configs_col = db["integration_configs"]
_crawl_log_col = db["prospect_crawl_log"]
_crawl_log_col.create_index([("tenant_id", 1), ("lead_id", 1)])


# ─── Errors ─────────────────────────────────────────────────────────────
class MissingCredential(Exception):
    """Raised when a tenant has not configured the requested provider."""


class CrawlLimitExceeded(Exception):
    """Raised when an enrichment would push past the 8-call cap."""


class CrawlError(Exception):
    """Raised when a provider returns a non-2xx and we can't recover."""


# ─── Credential retrieval ───────────────────────────────────────────────
def _get_api_key(tenant_id: str, provider: str) -> Optional[str]:
    """Fetch + decrypt the API key for a tenant/provider. Returns None if
    not configured (so callers can decide whether to skip the source)."""
    doc = _configs_col.find_one(
        {"tenant_id": tenant_id, "integration_type": provider},
        {"_id": 0, "config": 1, "status": 1},
    )
    if not doc:
        return None
    cfg = doc.get("config") or {}
    raw = cfg.get("api_key")
    if not raw:
        return None
    try:
        return decrypt(raw)
    except Exception:
        logger.exception("crawl_service: failed to decrypt %s key", provider)
        return None


# ─── Call-budget tracking ───────────────────────────────────────────────
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _budget_used(tenant_id: str, lead_id: str) -> int:
    doc = _crawl_log_col.find_one(
        {"tenant_id": tenant_id, "lead_id": lead_id},
        {"_id": 0, "call_count": 1},
    )
    return int((doc or {}).get("call_count", 0))


def _bump_budget(tenant_id: str, lead_id: str, source: str, delta: int = 1) -> None:
    _crawl_log_col.update_one(
        {"tenant_id": tenant_id, "lead_id": lead_id},
        {
            "$inc": {"call_count": delta, f"by_source.{source}": delta},
            "$setOnInsert": {
                "tenant_id": tenant_id,
                "lead_id": lead_id,
                "created_at": _now_iso(),
            },
            "$set": {"updated_at": _now_iso()},
        },
        upsert=True,
    )


def _assert_budget(tenant_id: str, lead_id: str, planned: int) -> None:
    used = _budget_used(tenant_id, lead_id)
    if used + planned > MAX_CALLS_PER_PROSPECT:
        raise CrawlLimitExceeded(
            f"Prospect crawl cap reached: {used} used + {planned} planned > {MAX_CALLS_PER_PROSPECT}"
        )


# ─── Proxycurl primitives ───────────────────────────────────────────────
async def _proxycurl_get(api_key: str, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    async with httpx.AsyncClient(base_url=PROXYCURL_BASE, headers=headers, timeout=DEFAULT_TIMEOUT) as client:
        resp = await client.get(path, params=params)
        if resp.status_code == 404:
            return {}
        if resp.status_code >= 400:
            raise CrawlError(f"Proxycurl {path} → {resp.status_code}: {resp.text[:200]}")
        return resp.json() if resp.text else {}


async def fetch_linkedin_profile(api_key: str, linkedin_url: str) -> Dict[str, Any]:
    return await _proxycurl_get(
        api_key,
        "/proxycurl/api/v2/linkedin",
        {"url": linkedin_url, "fallback_to_cache": "on-error"},
    )


async def resolve_linkedin_profile(
    api_key: str, *, first_name: str, last_name: Optional[str], company_domain: Optional[str]
) -> Optional[str]:
    if not company_domain or not first_name:
        return None
    params = {"first_name": first_name, "company_domain": company_domain}
    if last_name:
        params["last_name"] = last_name
    data = await _proxycurl_get(api_key, "/proxycurl/api/linkedin/profile/resolve", params)
    return data.get("url") or data.get("linkedin_profile_url")


async def fetch_linkedin_company(api_key: str, company_url: str) -> Dict[str, Any]:
    return await _proxycurl_get(
        api_key,
        "/proxycurl/api/linkedin/company",
        {"url": company_url},
    )


# ─── Serper primitives ──────────────────────────────────────────────────
async def _serper_post(api_key: str, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(base_url=SERPER_BASE, headers=headers, timeout=DEFAULT_TIMEOUT) as client:
        resp = await client.post(path, json=body)
        if resp.status_code >= 400:
            raise CrawlError(f"Serper {path} → {resp.status_code}: {resp.text[:200]}")
        return resp.json() if resp.text else {}


async def serper_web_search(api_key: str, query: str, num: int = 10) -> Dict[str, Any]:
    return await _serper_post(api_key, "/search", {"q": query, "gl": "us", "hl": "en", "num": num})


async def serper_news_search(api_key: str, query: str, num: int = 8) -> Dict[str, Any]:
    return await _serper_post(
        api_key,
        "/news",
        {"q": query, "gl": "us", "hl": "en", "num": num, "tbs": "qdr:m"},
    )


# ─── High-level orchestrator ────────────────────────────────────────────
async def crawl_prospect(
    *,
    tenant_id: str,
    lead_id: str,
    first_name: str,
    last_name: Optional[str] = None,
    email: Optional[str] = None,
    company_name: Optional[str] = None,
    company_domain: Optional[str] = None,
    linkedin_url: Optional[str] = None,
    linkedin_company_url: Optional[str] = None,
    industry: Optional[str] = None,
    bypass_budget: bool = False,
) -> Dict[str, Any]:
    """Run a multi-platform crawl for a single prospect.

    Returns a stable dict:
        {
          "linkedin_profile": {...} | None,
          "linkedin_company": {...} | None,
          "web_results":      [{title, snippet, link, source}, ...],
          "news_results":     [{title, snippet, link, source, date}, ...],
          "sources_attempted": ["proxycurl", "serper"],
          "sources_succeeded": ["serper"],
          "calls_made":        4,
          "errors":            [{source, message}],
        }
    """
    proxycurl_key = _get_api_key(tenant_id, "proxycurl")
    serper_key = _get_api_key(tenant_id, "serper")

    out: Dict[str, Any] = {
        "linkedin_profile": None,
        "linkedin_company": None,
        "web_results": [],
        "news_results": [],
        "sources_attempted": [],
        "sources_succeeded": [],
        "calls_made": 0,
        "errors": [],
    }

    # ── Plan calls (max 5; leave 3 in budget for future re-runs / playbook) ──
    planned = 0
    if proxycurl_key:
        out["sources_attempted"].append("proxycurl")
        if not linkedin_url:
            planned += 1  # resolve
        planned += 1  # person profile
        if linkedin_company_url or company_domain:
            planned += 1  # company profile
    if serper_key:
        out["sources_attempted"].append("serper")
        planned += 2  # web + news

    if planned == 0:
        raise MissingCredential(
            "Neither Proxycurl nor Serper is configured for this workspace. "
            "Connect them on /app/integrations to enable prospect intel."
        )

    if not bypass_budget:
        _assert_budget(tenant_id, lead_id, planned)

    # ── Proxycurl path ──
    if proxycurl_key:
        try:
            resolved_url = linkedin_url
            if not resolved_url and company_domain:
                resolved_url = await resolve_linkedin_profile(
                    proxycurl_key,
                    first_name=first_name,
                    last_name=last_name,
                    company_domain=company_domain,
                )
                _bump_budget(tenant_id, lead_id, "proxycurl_resolve")
                out["calls_made"] += 1

            if resolved_url:
                profile = await fetch_linkedin_profile(proxycurl_key, resolved_url)
                _bump_budget(tenant_id, lead_id, "proxycurl_profile")
                out["calls_made"] += 1
                if profile:
                    out["linkedin_profile"] = profile
                    out["linkedin_profile"]["_resolved_url"] = resolved_url

            company_url = linkedin_company_url
            if not company_url and out["linkedin_profile"]:
                experiences = out["linkedin_profile"].get("experiences") or []
                if experiences:
                    company_url = experiences[0].get("company_linkedin_profile_url")
            if company_url:
                company = await fetch_linkedin_company(proxycurl_key, company_url)
                _bump_budget(tenant_id, lead_id, "proxycurl_company")
                out["calls_made"] += 1
                if company:
                    out["linkedin_company"] = company

            out["sources_succeeded"].append("proxycurl")
        except CrawlError as e:
            out["errors"].append({"source": "proxycurl", "message": str(e)[:200]})
        except Exception as e:  # noqa: BLE001
            logger.exception("crawl_service: proxycurl unexpected error")
            out["errors"].append({"source": "proxycurl", "message": str(e)[:200]})

    # ── Serper path ──
    if serper_key:
        try:
            query_seed = " ".join(p for p in [first_name, last_name, company_name] if p) or (email or "")
            company_query = company_name or company_domain or ""
            web_task = serper_web_search(serper_key, query_seed.strip(), num=10)
            news_task = serper_news_search(serper_key, company_query.strip() or query_seed.strip(), num=8) if company_query else None
            if news_task:
                web, news = await asyncio.gather(web_task, news_task, return_exceptions=False)
                _bump_budget(tenant_id, lead_id, "serper_news")
                out["calls_made"] += 1
            else:
                web = await web_task
                news = {}
            _bump_budget(tenant_id, lead_id, "serper_web")
            out["calls_made"] += 1

            organic = (web.get("organic") or [])[:10]
            out["web_results"] = [
                {
                    "title": r.get("title"),
                    "snippet": r.get("snippet"),
                    "link": r.get("link"),
                    "source": (r.get("link") or "").split("/")[2] if r.get("link") else None,
                    "position": r.get("position"),
                }
                for r in organic if r.get("title")
            ]
            news_items = (news.get("news") or [])[:8] if news else []
            out["news_results"] = [
                {
                    "title": n.get("title"),
                    "snippet": n.get("snippet"),
                    "link": n.get("link"),
                    "source": n.get("source"),
                    "date": n.get("date"),
                }
                for n in news_items if n.get("title")
            ]
            out["sources_succeeded"].append("serper")
        except CrawlError as e:
            out["errors"].append({"source": "serper", "message": str(e)[:200]})
        except Exception as e:  # noqa: BLE001
            logger.exception("crawl_service: serper unexpected error")
            out["errors"].append({"source": "serper", "message": str(e)[:200]})

    return out


# ─── Public helper: budget snapshot ─────────────────────────────────────
def get_budget_snapshot(tenant_id: str, lead_id: str) -> Dict[str, Any]:
    doc = _crawl_log_col.find_one(
        {"tenant_id": tenant_id, "lead_id": lead_id},
        {"_id": 0},
    ) or {}
    return {
        "calls_used": int(doc.get("call_count", 0)),
        "calls_remaining": max(0, MAX_CALLS_PER_PROSPECT - int(doc.get("call_count", 0))),
        "cap": MAX_CALLS_PER_PROSPECT,
        "by_source": doc.get("by_source") or {},
        "last_updated": doc.get("updated_at"),
    }


__all__: List[str] = [
    "crawl_prospect",
    "get_budget_snapshot",
    "MissingCredential",
    "CrawlLimitExceeded",
    "CrawlError",
    "MAX_CALLS_PER_PROSPECT",
]
