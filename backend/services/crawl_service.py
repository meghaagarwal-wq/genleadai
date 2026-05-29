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


def _get_provider_config(tenant_id: str, provider: str) -> Dict[str, Any]:
    """Return the FULL (decrypted) config dict for a tenant/provider, or {}.
    Used by RapidAPI to read extra_config knobs like `host` / `endpoint`."""
    doc = _configs_col.find_one(
        {"tenant_id": tenant_id, "integration_type": provider},
        {"_id": 0, "config": 1},
    )
    if not doc:
        return {}
    cfg = dict(doc.get("config") or {})
    raw = cfg.pop("api_key", None)
    if raw:
        try:
            cfg["api_key"] = decrypt(raw)
        except Exception:
            logger.exception("crawl_service: failed to decrypt %s key", provider)
    return cfg


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


# ─── RapidAPI LinkedIn primitives ───────────────────────────────────────
# Drop-in replacement for the Proxycurl helpers above. Targets the
# "Fresh LinkedIn Profile Data" host by default — overridable via the
# tenant's integration_configs.rapidapi.config.host so a customer can
# swap to a different RapidAPI LinkedIn scraper without a code change.
#
# All RapidAPI helpers normalise the response back to the SAME field
# names the rest of the pipeline expects (first_name, last_name,
# headline, occupation, summary, country, city, experiences[], etc.).
# This means intel_service / claude synthesis stays untouched.
RAPIDAPI_DEFAULT_HOST = "fresh-linkedin-profile-data.p.rapidapi.com"


async def _rapidapi_get(
    api_key: str,
    host: str,
    path: str,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": host,
        "Accept": "application/json",
    }
    base = f"https://{host}"
    async with httpx.AsyncClient(base_url=base, headers=headers, timeout=DEFAULT_TIMEOUT) as client:
        resp = await client.get(path, params=params)
        if resp.status_code == 404:
            return {}
        if resp.status_code >= 400:
            raise CrawlError(f"RapidAPI {host}{path} → {resp.status_code}: {resp.text[:200]}")
        return resp.json() if resp.text else {}


def _rapidapi_normalise_profile(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Map the RapidAPI response into the Proxycurl-shape our pipeline
    already understands. The 'Fresh LinkedIn Profile Data' provider
    nests its payload under {"data": {...}} on success — handle both
    flat and nested shapes so other RapidAPI hosts also work."""
    if not raw:
        return {}
    d = raw.get("data") if isinstance(raw.get("data"), dict) else raw

    experiences = d.get("experiences") or d.get("experience") or []
    educations = d.get("educations") or d.get("education") or []

    return {
        "first_name":   d.get("first_name") or d.get("firstName"),
        "last_name":    d.get("last_name")  or d.get("lastName"),
        "full_name":    d.get("full_name")  or d.get("name"),
        "headline":     d.get("headline")   or d.get("subtitle"),
        "occupation":   d.get("occupation") or d.get("position") or d.get("headline"),
        "summary":      d.get("summary")    or d.get("about"),
        "country":      d.get("country")    or d.get("country_full_name") or d.get("location_country"),
        "city":         d.get("city")       or d.get("location_city"),
        "profile_pic_url": d.get("profile_pic_url") or d.get("profilePic") or d.get("profile_image_url"),
        "linkedin_url":     d.get("linkedin_url") or d.get("profile_url") or d.get("input_url"),
        "follower_count":   d.get("follower_count") or d.get("followers"),
        "connection_count": d.get("connection_count") or d.get("connections"),
        # Normalised list of past + current roles for Claude synthesis.
        "experiences": [
            {
                "title":   e.get("title") or e.get("position"),
                "company": e.get("company") or e.get("companyName") or (e.get("company_info") or {}).get("name"),
                "location": e.get("location"),
                "starts_at": e.get("starts_at") or e.get("start_date") or e.get("startDate"),
                "ends_at":   e.get("ends_at")   or e.get("end_date")   or e.get("endDate"),
                "description": e.get("description"),
            }
            for e in experiences if isinstance(e, dict)
        ],
        "education": [
            {
                "school": e.get("school") or e.get("schoolName"),
                "degree_name": e.get("degree_name") or e.get("degree"),
                "field_of_study": e.get("field_of_study") or e.get("fieldOfStudy"),
                "starts_at": e.get("starts_at") or e.get("start_date"),
                "ends_at":   e.get("ends_at")   or e.get("end_date"),
            }
            for e in educations if isinstance(e, dict)
        ],
        "_source": "rapidapi",
        "_host": None,  # filled in by the calling helper
    }


def _rapidapi_normalise_company(raw: Dict[str, Any]) -> Dict[str, Any]:
    if not raw:
        return {}
    d = raw.get("data") if isinstance(raw.get("data"), dict) else raw
    return {
        "name":        d.get("name") or d.get("company_name"),
        "description": d.get("description") or d.get("about"),
        "industry":    d.get("industry"),
        "company_size": d.get("company_size") or d.get("size") or d.get("employee_count"),
        "headquarter": d.get("headquarter") or d.get("hq") or d.get("location"),
        "founded_year": d.get("founded_year") or d.get("founded"),
        "website":     d.get("website") or d.get("url"),
        "linkedin_url": d.get("linkedin_url") or d.get("input_url"),
        "follower_count": d.get("follower_count") or d.get("followers"),
        "_source": "rapidapi",
    }


async def rapidapi_get_person_profile(
    api_key: str, host: str, linkedin_url: str,
) -> Dict[str, Any]:
    """Fetch a normalised LinkedIn person profile via RapidAPI."""
    raw = await _rapidapi_get(
        api_key, host, "/get-linkedin-profile",
        {"linkedin_url": linkedin_url, "include_skills": "false", "include_certifications": "false"},
    )
    normalised = _rapidapi_normalise_profile(raw)
    if normalised:
        normalised["_host"] = host
    return normalised


async def rapidapi_get_company_profile(
    api_key: str, host: str, company_url: str,
) -> Dict[str, Any]:
    raw = await _rapidapi_get(
        api_key, host, "/get-company-by-linkedinurl",
        {"linkedin_url": company_url},
    )
    return _rapidapi_normalise_company(raw)


async def rapidapi_get_person_posts(
    api_key: str, host: str, linkedin_url: str, limit: int = 10,
) -> List[Dict[str, Any]]:
    """Recent posts by a person. Returns a list of {text, url, posted_at}.

    This is the headline value-add over Proxycurl: real recent activity
    feeds the intel synthesis with timely signals (deal announcements,
    job changes, etc.)."""
    raw = await _rapidapi_get(
        api_key, host, "/get-profile-posts",
        {"linkedin_url": linkedin_url, "limit": str(limit)},
    )
    if not raw:
        return []
    items = raw.get("data") or raw.get("posts") or raw.get("results") or []
    if not isinstance(items, list):
        return []
    out: List[Dict[str, Any]] = []
    for p in items[:limit]:
        if not isinstance(p, dict):
            continue
        out.append({
            "text":      p.get("text") or p.get("commentary") or p.get("content"),
            "url":       p.get("url") or p.get("post_url") or p.get("share_url"),
            "posted_at": p.get("posted_at") or p.get("date") or p.get("created_at"),
            "reactions": p.get("reactions") or p.get("like_count") or p.get("total_reactions"),
        })
    return out


async def rapidapi_resolve_linkedin_profile(
    api_key: str, host: str, *, first_name: str, last_name: Optional[str], company_name: Optional[str],
) -> Optional[str]:
    """Best-effort handle resolver. The 'Fresh LinkedIn Profile Data'
    host exposes /search-people; if the chosen host doesn't, this
    returns None and the caller falls back to Serper-based discovery."""
    if not first_name:
        return None
    q = " ".join(p for p in [first_name, last_name, company_name] if p).strip()
    try:
        data = await _rapidapi_get(
            api_key, host, "/search-people",
            {"keywords": q, "geo_codes": "", "company": company_name or "", "limit": "1"},
        )
    except CrawlError:
        return None
    items = data.get("data") or data.get("results") or []
    if isinstance(items, list) and items:
        first = items[0]
        if isinstance(first, dict):
            return first.get("linkedin_url") or first.get("profile_url") or first.get("url")
    return None


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


# ─── Instagram + Facebook crawl (via Serper site: search) ───────────────
# We use Serper site: filters because the public IG/FB Graph API requires
# a per-app review for non-owned pages — Serper hits the public-web index
# instead, which is what shows up in the audit report for these platforms.
async def serper_instagram_search(api_key: str, handle_or_company: str, num: int = 8) -> Dict[str, Any]:
    q = f"site:instagram.com {handle_or_company}"
    return await _serper_post(api_key, "/search", {"q": q, "gl": "us", "hl": "en", "num": num})


async def serper_facebook_search(api_key: str, handle_or_company: str, num: int = 8) -> Dict[str, Any]:
    q = f"site:facebook.com {handle_or_company}"
    return await _serper_post(api_key, "/search", {"q": q, "gl": "us", "hl": "en", "num": num})


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
    platforms: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Run a multi-platform crawl for a single prospect.

    `platforms` (optional) is a list filter — any of:
      ``linkedin``, ``web``, ``news``, ``instagram``, ``facebook``.
    Defaults to ``["linkedin","web","news"]`` so existing callers stay
    unchanged. The ``instagram`` / ``facebook`` platforms hit the Serper
    site:-filtered search and inherit the 8-call cap.

    Returns a stable dict:
        {
          "linkedin_profile": {...} | None,
          "linkedin_company": {...} | None,
          "web_results":      [...],
          "news_results":     [...],
          "instagram_results": [...],
          "facebook_results":  [...],
          "sources_attempted": [...],
          "sources_succeeded": [...],
          "calls_made":        4,
          "errors":            [...],
        }
    """
    proxycurl_key = _get_api_key(tenant_id, "proxycurl")
    serper_key = _get_api_key(tenant_id, "serper")
    # iter125 — RapidAPI replaces Proxycurl for LinkedIn. If a tenant has
    # the `rapidapi` integration configured, it takes precedence over
    # Proxycurl. The `host` extra_config knob lets a workspace pick a
    # different RapidAPI LinkedIn scraper without a code change.
    rapidapi_cfg = _get_provider_config(tenant_id, "rapidapi")
    rapidapi_key = rapidapi_cfg.get("api_key")
    rapidapi_host = (rapidapi_cfg.get("host") or RAPIDAPI_DEFAULT_HOST).strip()
    use_rapidapi = bool(rapidapi_key)

    platforms = platforms or ["linkedin", "web", "news"]
    want_linkedin = "linkedin" in platforms
    want_web = "web" in platforms
    want_news = "news" in platforms
    want_ig = "instagram" in platforms
    want_fb = "facebook" in platforms

    out: Dict[str, Any] = {
        "linkedin_profile": None,
        "linkedin_company": None,
        "linkedin_posts": [],
        "web_results": [],
        "news_results": [],
        "instagram_results": [],
        "facebook_results": [],
        "sources_attempted": [],
        "sources_succeeded": [],
        "calls_made": 0,
        "errors": [],
    }

    # ── Plan calls (max 5; leave 3 in budget for future re-runs / playbook) ──
    planned = 0
    if use_rapidapi and want_linkedin:
        out["sources_attempted"].append("rapidapi")
        if not linkedin_url:
            planned += 1  # resolve
        planned += 1  # person profile
        planned += 1  # recent posts
        if linkedin_company_url or company_domain:
            planned += 1  # company profile
    elif proxycurl_key and want_linkedin:
        out["sources_attempted"].append("proxycurl")
        if not linkedin_url:
            planned += 1  # resolve
        planned += 1  # person profile
        if linkedin_company_url or company_domain:
            planned += 1  # company profile
    if serper_key:
        out["sources_attempted"].append("serper")
        if want_web:
            planned += 1
        if want_news:
            planned += 1
        if want_ig:
            planned += 1
        if want_fb:
            planned += 1

    if planned == 0:
        raise MissingCredential(
            "No LinkedIn provider (RapidAPI or Proxycurl) and no Serper key is "
            "configured for this workspace. Connect them on /app/integrations "
            "to enable prospect intel."
        )

    if not bypass_budget:
        _assert_budget(tenant_id, lead_id, planned)

    # ── RapidAPI LinkedIn path (preferred over Proxycurl) ──
    if use_rapidapi and want_linkedin:
        try:
            resolved_url = linkedin_url
            if not resolved_url:
                resolved_url = await rapidapi_resolve_linkedin_profile(
                    rapidapi_key, rapidapi_host,
                    first_name=first_name, last_name=last_name,
                    company_name=company_name,
                )
                _bump_budget(tenant_id, lead_id, "rapidapi_resolve")
                out["calls_made"] += 1

            if resolved_url:
                profile = await rapidapi_get_person_profile(rapidapi_key, rapidapi_host, resolved_url)
                _bump_budget(tenant_id, lead_id, "rapidapi_profile")
                out["calls_made"] += 1
                if profile:
                    profile["_resolved_url"] = resolved_url
                    out["linkedin_profile"] = profile

                # Recent posts — the headline value-add over Proxycurl.
                try:
                    posts = await rapidapi_get_person_posts(rapidapi_key, rapidapi_host, resolved_url, limit=10)
                    _bump_budget(tenant_id, lead_id, "rapidapi_posts")
                    out["calls_made"] += 1
                    out["linkedin_posts"] = posts
                except CrawlError as e:
                    # Posts are optional; record the error but keep the profile.
                    out["errors"].append({"source": "rapidapi_posts", "message": str(e)[:200]})

            company_url = linkedin_company_url
            if not company_url and out["linkedin_profile"]:
                experiences = out["linkedin_profile"].get("experiences") or []
                if experiences:
                    company_url = (
                        experiences[0].get("company_linkedin_profile_url")
                        or experiences[0].get("company_url")
                    )
            if company_url:
                company = await rapidapi_get_company_profile(rapidapi_key, rapidapi_host, company_url)
                _bump_budget(tenant_id, lead_id, "rapidapi_company")
                out["calls_made"] += 1
                if company:
                    out["linkedin_company"] = company

            out["sources_succeeded"].append("rapidapi")
        except CrawlError as e:
            out["errors"].append({"source": "rapidapi", "message": str(e)[:200]})
        except Exception as e:  # noqa: BLE001
            logger.exception("crawl_service: rapidapi unexpected error")
            out["errors"].append({"source": "rapidapi", "message": str(e)[:200]})

    # ── Proxycurl path (legacy fallback when rapidapi not configured) ──
    elif proxycurl_key and want_linkedin:
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
            handle_query = company_name or company_domain or query_seed.strip()

            if want_web:
                web = await serper_web_search(serper_key, query_seed.strip(), num=10)
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

            if want_news and company_query:
                news = await serper_news_search(serper_key, company_query.strip(), num=8)
                _bump_budget(tenant_id, lead_id, "serper_news")
                out["calls_made"] += 1
                news_items = (news.get("news") or [])[:8]
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

            if want_ig and handle_query:
                try:
                    ig = await serper_instagram_search(serper_key, handle_query, num=8)
                    _bump_budget(tenant_id, lead_id, "serper_instagram")
                    out["calls_made"] += 1
                    ig_items = (ig.get("organic") or [])[:8]
                    out["instagram_results"] = [
                        {
                            "title": r.get("title"),
                            "snippet": r.get("snippet"),
                            "link": r.get("link"),
                        }
                        for r in ig_items if r.get("title")
                    ]
                    if not out["instagram_results"]:
                        out["errors"].append({"source": "instagram", "message": "platform_empty"})
                except CrawlError as e:
                    out["errors"].append({"source": "instagram", "message": str(e)[:200]})

            if want_fb and handle_query:
                try:
                    fb = await serper_facebook_search(serper_key, handle_query, num=8)
                    _bump_budget(tenant_id, lead_id, "serper_facebook")
                    out["calls_made"] += 1
                    fb_items = (fb.get("organic") or [])[:8]
                    out["facebook_results"] = [
                        {
                            "title": r.get("title"),
                            "snippet": r.get("snippet"),
                            "link": r.get("link"),
                        }
                        for r in fb_items if r.get("title")
                    ]
                    if not out["facebook_results"]:
                        out["errors"].append({"source": "facebook", "message": "platform_empty"})
                except CrawlError as e:
                    out["errors"].append({"source": "facebook", "message": str(e)[:200]})

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
