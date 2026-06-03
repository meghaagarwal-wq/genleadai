"""Pietential B2B Insights Engine (Phase 3 of Aria v2).

Implements Section 7 of /app/memory/ARIA_MASTER_SPEC.md:

- Daily scan over insights-enabled prospects (manual trigger here; cron later)
- 8-signal classification: deal_closed | funding_round | event_attending |
  job_change | hiring_signal | content_published | company_news | social_activity
- ICP matching: title 35% + industry 30% + size 20% + content 15%
- Confidence threshold 0.70 to surface, ≥0.85 for WhatsApp alert
- Deduplication: same prospect + same signal_type within 30 days = skip
- Resource mapping per signal type (see RESOURCE_MAP below)
- Storage: `pt_insights` collection (one row per insight card)

Enrichment sources
──────────────────
Proxycurl (LinkedIn) — `tenants.settings.pt_enrichment.proxycurl_api_key`
NewsAPI                — `tenants.settings.pt_enrichment.newsapi_key`
Both keys Fernet-encrypted at rest. If a key is absent, the corresponding
enrichment is skipped and Aria classifies signals from whatever data
exists on the prospect record (Claude-only fallback mode).

Endpoints
─────────
GET  /api/pt/insights/feed                  — list insight cards (sorted by recency + score)
POST /api/pt/insights/scan/run-now          — manually trigger a scan (admin)
POST /api/pt/insights/{insight_id}/action   — { action: "send" | "copy" | "dismiss" }
GET  /api/pt/insights/integrations          — current key handshake state
PUT  /api/pt/insights/integrations          — set proxycurl/newsapi keys (encrypted)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import db
from security.encryption import encrypt, decrypt
from routes.tenants import get_active_tenant, require_tenant_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pt/insights", tags=["pt-insights"])

# Collections
insights_col = db["pt_insights"]
leads_col = db["pt_leads"]
tenants_col = db["tenants"]

# ─── Constants ──────────────────────────────────────────────────────────
SIGNAL_TYPES = [
    "deal_closed", "funding_round", "event_attending", "job_change",
    "hiring_signal", "content_published", "company_news", "social_activity",
]
CONFIDENCE_SURFACE = 0.70
CONFIDENCE_WHATSAPP = 0.85
DEDUP_WINDOW_DAYS = 30
MAX_SCAN_BATCH = 20  # cap per manual run to keep latency predictable

RESOURCE_MAP = {
    "deal_closed":       "case_study",
    "funding_round":     "roi_overview",
    "event_attending":   "thought_leadership",
    "job_change":        "role_quick_win",
    "content_published": "pov_response",
    "company_news":      "capability_overview",
    "hiring_signal":     "scalability_resource",
    "social_activity":   "directly_relevant",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utc_30_days_ago() -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=DEDUP_WINDOW_DAYS)


# ─── Enrichment clients ─────────────────────────────────────────────────
async def _proxycurl_profile(api_key: str, linkedin_url: str) -> Optional[Dict[str, Any]]:
    """Fetch a LinkedIn profile via Proxycurl. Returns None on any error."""
    if not api_key or not linkedin_url:
        return None
    url = "https://nubela.co/proxycurl/api/v2/linkedin"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                params={"linkedin_profile_url": linkedin_url, "use_cache": "if-present"},
            )
            if r.status_code != 200:
                logger.warning(f"[pt-insights] proxycurl {r.status_code}: {r.text[:120]}")
                return None
            return r.json()
    except Exception as e:
        logger.warning(f"[pt-insights] proxycurl call failed: {e}")
        return None


async def _newsapi_company_news(api_key: str, company: str) -> List[Dict[str, Any]]:
    """Pull recent news for a company. Returns up to 5 headlines."""
    if not api_key or not company:
        return []
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            r = await client.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": f"\"{company}\"",
                    "sortBy": "publishedAt",
                    "pageSize": 5,
                    "language": "en",
                    "apiKey": api_key,
                },
            )
            if r.status_code != 200:
                return []
            articles = r.json().get("articles") or []
            return [
                {
                    "title": a.get("title"),
                    "description": a.get("description"),
                    "published_at": a.get("publishedAt"),
                    "source": (a.get("source") or {}).get("name"),
                    "url": a.get("url"),
                }
                for a in articles[:5]
            ]
    except Exception as e:
        logger.warning(f"[pt-insights] newsapi call failed: {e}")
        return []


# ─── Signal classifier (Claude) ─────────────────────────────────────────
_CLASSIFY_SYSTEM_PROMPT = """You are a B2B sales intelligence agent. Given enriched data about a prospect, you classify any new signals into exactly one of these 8 types:

deal_closed | funding_round | event_attending | job_change | hiring_signal | content_published | company_news | social_activity

Rules:
1. Return ONLY signals you are at least 0.70 confident in. If unsure, return an empty array.
2. Each signal MUST include: type (from list above), summary (one sentence), confidence (0.0-1.0), rationale (one short line).
3. Never fabricate. If the input has no real new signal, return [].
4. Output strict JSON: {"signals": [...]}. No preamble, no markdown.

Example output:
{"signals": [
  {"type": "funding_round", "summary": "Acme Co raised $30M Series B led by Bessemer.", "confidence": 0.92, "rationale": "TechCrunch article dated within 7 days"}
]}"""


async def _classify_signals_via_claude(
    prospect: Dict[str, Any],
    proxycurl_data: Optional[Dict[str, Any]],
    news_articles: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Run Claude to classify any new signals on this prospect."""
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        return []

    payload = {
        "prospect": {
            "name": prospect.get("name") or "",
            "title": prospect.get("title") or "",
            "company": prospect.get("company_name") or "",
            "linkedin_url": prospect.get("linkedin_url") or "",
        },
        "linkedin_profile_summary": _compact_proxycurl(proxycurl_data),
        "recent_news": news_articles[:5],
    }

    # iter109c Batch 3 — migrated to centralised Claude wrapper.
    from services.claude_service import claude_call, TaskType
    try:
        parsed = await claude_call(
            task_type=TaskType.SIGNAL_CLASSIFICATION,
            session_id=f"pt-insights-classify-{prospect.get('id', uuid.uuid4().hex[:8])}",
            system=_CLASSIFY_SYSTEM_PROMPT,
            prompt=f"Classify any new signals for this prospect.\n\nDATA:\n{json.dumps(payload, default=str)}",
            tenant_id=prospect.get("tenant_id"),
            response_format="json",
        )
    except Exception as e:
        logger.warning(f"[pt-insights] classify call failed: {e}")
        return []

    signals = parsed.get("signals") if isinstance(parsed, dict) else None
    if not isinstance(signals, list):
        return []

    cleaned: List[Dict[str, Any]] = []
    for s in signals:
        if not isinstance(s, dict):
            continue
        st = (s.get("type") or "").strip()
        if st not in SIGNAL_TYPES:
            continue
        try:
            conf = float(s.get("confidence", 0))
        except (TypeError, ValueError):
            continue
        if conf < CONFIDENCE_SURFACE:
            continue
        summary = (s.get("summary") or "").strip()
        if not summary:
            continue
        cleaned.append({
            "type": st,
            "summary": summary[:400],
            "confidence": round(min(max(conf, 0.0), 1.0), 2),
            "rationale": (s.get("rationale") or "").strip()[:200],
        })
    return cleaned


def _compact_proxycurl(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Strip proxycurl response to only the fields we care about."""
    if not data:
        return {}
    return {
        "headline": data.get("headline"),
        "occupation": data.get("occupation"),
        "summary": (data.get("summary") or "")[:500],
        "current_company": (data.get("experiences", [{}])[0] if data.get("experiences") else {}).get("company"),
        "recent_activity": [
            (act.get("title") or "")[:200]
            for act in (data.get("activities") or [])[:5]
        ],
    }


# ─── ICP matching for insights ──────────────────────────────────────────
def _score_icp_match(prospect: Dict[str, Any], icp: Dict[str, Any]) -> float:
    """Spec weights: title 35% + industry 30% + size 20% + content 15%.

    We only have a few prospect fields, so the content weight reduces to a
    bonus if the news articles mention the ICP's pain signals.
    """
    score = 0.0
    title = (prospect.get("title") or "").lower()
    company = (prospect.get("company_name") or "").lower()

    # Title (35%)
    titles = [t.lower() for t in (icp.get("target_titles_or_roles") or [])]
    if titles and any(t in title for t in titles):
        score += 0.35

    # Industry (30%) — heuristic: company name OR title contains industry token
    industries = [i.lower() for i in (icp.get("target_industries") or [])]
    if industries and any(i in title or i in company for i in industries):
        score += 0.30

    # Company size (20%) — without size data on prospect, give 50% credit
    if (icp.get("company_size") or "").strip():
        score += 0.10  # partial — we don't have prospect company size

    # Content / signals (15%) — best-effort
    high_intent = [s.lower() for s in (icp.get("high_intent_signals") or [])]
    blob = f"{title} {company}".lower()
    if high_intent and any(sig in blob for sig in high_intent):
        score += 0.15

    return round(min(score, 1.0), 2)


def _best_icp_match(prospect: Dict[str, Any], icps: List[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], float]:
    """Return (best_icp, score). Both None+0 if no ICPs configured."""
    if not icps:
        return None, 0.0
    scored = [(icp, _score_icp_match(prospect, icp)) for icp in icps]
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored[0]


# ─── Suggested message generator ────────────────────────────────────────
_MSG_SYSTEM_PROMPT = """You draft B2B outreach messages on behalf of a workspace owner. Write a single message that:
1. Is under 120 words.
2. Uses the signal as a natural hook (never sounds salesy or templated).
3. Matches the workspace's brand voice.
4. Ends with a soft, low-pressure CTA — never a hard pitch.
5. Returns JUST the message text — no subject line, no signature, no markdown."""


async def _draft_suggested_message(
    workspace_name: str,
    founder_name: str,
    brand_voice: str,
    prospect: Dict[str, Any],
    signal: Dict[str, Any],
) -> str:
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        return ""

    ctx = (
        f"Workspace: {workspace_name}\n"
        f"Founder: {founder_name}\n"
        f"Brand voice: {brand_voice or 'warm, consultative, direct'}\n\n"
        f"Prospect: {prospect.get('name', '')} — {prospect.get('title', '')} at {prospect.get('company_name', '')}\n"
        f"Signal type: {signal.get('type')}\n"
        f"Signal summary: {signal.get('summary')}\n\n"
        "Draft the outreach message."
    )

    # iter109c Batch 3 — migrated to centralised Claude wrapper (sonnet for
    # message generation per Section 3D).
    from services.claude_service import claude_call, TaskType
    try:
        resp = await claude_call(
            task_type=TaskType.INSIGHT_GENERATION,
            session_id=f"pt-insights-draft-{uuid.uuid4().hex[:8]}",
            system=_MSG_SYSTEM_PROMPT,
            prompt=ctx,
            tenant_id=prospect.get("tenant_id"),
        )
        return (resp or "").strip()[:1200]
    except Exception as e:
        logger.warning(f"[pt-insights] draft failed: {e}")
        return ""


# ─── Core scanner ───────────────────────────────────────────────────────
async def _scan_one_prospect(
    tenant: Dict[str, Any],
    prospect: Dict[str, Any],
    proxycurl_key: str,
    newsapi_key: str,
) -> List[Dict[str, Any]]:
    """Scan one prospect for new signals; return list of inserted insight ids."""
    # Skip suppressed / do-not-contact prospects
    if prospect.get("dnc") or prospect.get("suppressed"):
        return []

    settings = (tenant.get("settings") or {})
    training = (settings.get("aria_training_profile") or {}).get("data") or {}
    icps = training.get("icp_profiles") or []

    # Enrichment
    proxy_data = None
    news = []
    if prospect.get("linkedin_url"):
        proxy_data = await _proxycurl_profile(proxycurl_key, prospect.get("linkedin_url"))
    if prospect.get("company_name"):
        news = await _newsapi_company_news(newsapi_key, prospect.get("company_name"))
        # Iter99 — Serper fallback when NewsAPI returns empty (or no key set).
        # Reads the same `integration_configs.serper.config.api_key` the
        # Integrations Hub already stores, so no extra wiring needed.
        if not news:
            try:
                serper_cfg = db["integration_configs"].find_one(
                    {"tenant_id": tenant["id"], "integration_type": "serper"},
                    {"_id": 0, "config": 1},
                ) or {}
                serper_key = (serper_cfg.get("config") or {}).get("api_key")
                if serper_key:
                    from routes.integrations_extras import serper_company_news
                    news = await serper_company_news(serper_key, prospect.get("company_name"))
            except Exception as e:
                logger.warning(f"[pt-insights] serper fallback failed: {e}")

    # Classify
    signals = await _classify_signals_via_claude(prospect, proxy_data, news)
    if not signals:
        return []

    # ICP match
    icp_match, icp_score = _best_icp_match(prospect, icps)

    # Workspace persona for drafting
    persona = settings.get("business_profile") or {}
    workspace_name = persona.get("business_name") or tenant.get("name") or "your workspace"
    founder_name = persona.get("founder_name") or "the founder"
    brand_voice = training.get("brand_voice_style") or ""

    # Dedup window
    cutoff = _utc_30_days_ago()

    inserted: List[Dict[str, Any]] = []
    for sig in signals:
        # Skip if same prospect + same signal_type seen within 30 days
        recent = insights_col.find_one({
            "tenant_id": tenant["id"],
            "prospect_id": prospect.get("id"),
            "signal_type": sig["type"],
            "created_at": {"$gte": cutoff.isoformat()},
        }, {"_id": 0, "id": 1})
        if recent:
            continue

        suggested_msg = await _draft_suggested_message(
            workspace_name, founder_name, brand_voice, prospect, sig,
        )

        card = {
            "id": f"ins_{uuid.uuid4().hex[:12]}",
            "tenant_id": tenant["id"],
            "prospect_id": prospect.get("id"),
            "prospect_name": prospect.get("name"),
            "prospect_title": prospect.get("title"),
            "prospect_company": prospect.get("company_name"),
            "signal_type": sig["type"],
            "signal_summary": sig["summary"],
            "confidence": sig["confidence"],
            "rationale": sig["rationale"],
            "icp_match_name": (icp_match or {}).get("icp_name") if icp_match else None,
            "icp_match_score": icp_score,
            "suggested_message": suggested_msg,
            "resource_hint": RESOURCE_MAP.get(sig["type"], "directly_relevant"),
            "status": "new",
            "created_at": _now_iso(),
            "high_confidence": sig["confidence"] >= CONFIDENCE_WHATSAPP,
        }
        insights_col.insert_one(card.copy())
        card.pop("_id", None)
        inserted.append(card)

        # iter102 — auto-fire matching automation rules. Never raises.
        try:
            from routes.automation_rules import evaluate_and_fire_rules
            evaluate_and_fire_rules(
                tenant["id"],
                "insight.classified",
                {"insight": card, "prospect": prospect},
                triggered_by="insight_scan",
            )
        except Exception:
            pass
    return inserted


# ─── Pydantic models ────────────────────────────────────────────────────
class ScanResponse(BaseModel):
    ok: bool
    scanned: int
    insights_created: int
    cards: List[Dict[str, Any]]
    enrichment_status: Dict[str, bool]


class InsightActionPayload(BaseModel):
    # iter105 — accepts send | copy | dismiss | snooze
    action: str = Field(pattern="^(send|copy|dismiss|snooze)$")
    # For "send" — optional edited message body (Edit + Send flow).
    message: Optional[str] = None
    # For "snooze" — ISO date/datetime string; card hides until then.
    snooze_until: Optional[str] = None


class IntegrationKeysPayload(BaseModel):
    proxycurl_api_key: Optional[str] = None
    newsapi_key: Optional[str] = None


# ─── Endpoints ──────────────────────────────────────────────────────────
def _enrichment_keys_for(tenant: Dict[str, Any]) -> Tuple[str, str]:
    enrich = ((tenant.get("settings") or {}).get("pt_enrichment") or {})
    proxy = enrich.get("proxycurl_api_key")
    news = enrich.get("newsapi_key")
    return (decrypt(proxy) if proxy else ""), (decrypt(news) if news else "")


@router.get("/integrations")
async def get_integrations(tenant: dict = Depends(get_active_tenant)):
    """Return only handshake status — never the raw keys."""
    proxy_key, news_key = _enrichment_keys_for(tenant)
    return {
        "proxycurl": {"connected": bool(proxy_key)},
        "newsapi":   {"connected": bool(news_key)},
    }


@router.put("/integrations")
async def set_integrations(
    payload: IntegrationKeysPayload,
    tenant: dict = Depends(require_tenant_role(["owner", "admin", "master_admin"])),
):
    updates: Dict[str, Any] = {}
    if payload.proxycurl_api_key is not None:
        if payload.proxycurl_api_key.strip():
            updates["settings.pt_enrichment.proxycurl_api_key"] = encrypt(payload.proxycurl_api_key.strip())
        else:
            updates["settings.pt_enrichment.proxycurl_api_key"] = ""
    if payload.newsapi_key is not None:
        if payload.newsapi_key.strip():
            updates["settings.pt_enrichment.newsapi_key"] = encrypt(payload.newsapi_key.strip())
        else:
            updates["settings.pt_enrichment.newsapi_key"] = ""
    if updates:
        tenants_col.update_one({"id": tenant["id"]}, {"$set": updates})
    # Re-fetch to return current state
    fresh = tenants_col.find_one({"id": tenant["id"]}, {"_id": 0})
    proxy_key, news_key = _enrichment_keys_for(fresh or {})
    return {
        "ok": True,
        "proxycurl": {"connected": bool(proxy_key)},
        "newsapi":   {"connected": bool(news_key)},
    }


async def run_insight_scan_for_tenant(tenant: Dict[str, Any]) -> Dict[str, Any]:
    """Run one insights scan pass for a single tenant.

    Pure helper — no FastAPI deps. Used by both the manual endpoint and the
    daily `b2b_insight_scan_loop` cron. Caller is responsible for permission
    checks; we trust the tenant dict passed in.
    """
    proxy_key, news_key = _enrichment_keys_for(tenant)
    enrichment_status = {
        "proxycurl": bool(proxy_key),
        "newsapi": bool(news_key),
        "claude": bool(os.environ.get("EMERGENT_LLM_KEY")),
    }

    # Pick prospects: hot first, then warm, then anyone else
    candidates: List[Dict[str, Any]] = []
    for stage in ("hot", "warm", "cold"):
        if len(candidates) >= MAX_SCAN_BATCH:
            break
        for p in leads_col.find(
            {"tenant_id": tenant["id"], "stage": stage},
            {"_id": 0},
        ).limit(MAX_SCAN_BATCH - len(candidates)):
            candidates.append(p)

    scanned = 0
    cards: List[Dict[str, Any]] = []
    for prospect in candidates:
        scanned += 1
        try:
            new_cards = await _scan_one_prospect(tenant, prospect, proxy_key, news_key)
            cards.extend(new_cards)
        except Exception as e:
            logger.exception(f"[pt-insights] scan failed for {prospect.get('id')}: {e}")

    # Stamp last-scan timestamp so the cron + UI can show recency.
    tenants_col.update_one(
        {"id": tenant["id"]},
        {"$set": {"settings.pt_insights.last_scan_at": _now_iso(),
                  "settings.pt_insights.last_scan_count": len(cards)}},
    )

    return {
        "scanned": scanned,
        "insights_created": len(cards),
        "cards": cards,
        "enrichment_status": enrichment_status,
    }


@router.post("/scan/run-now", response_model=ScanResponse)
async def run_scan_now(
    tenant: dict = Depends(require_tenant_role(["owner", "admin", "master_admin"])),
):
    """Manually trigger an insights scan over up to MAX_SCAN_BATCH prospects.

    Order: hot leads first, then warm, then any with a `linkedin_url`.
    Skips prospects with do-not-contact flags. Dedupes within 30 days.
    """
    result = await run_insight_scan_for_tenant(tenant)
    return ScanResponse(ok=True, **result)


# ─── Cron — daily scan over every B2B / hybrid tenant ────────────────────
B2B_SCAN_TICK_SECONDS = 24 * 60 * 60  # 24h


def _b2b_eligible_tenants() -> List[Dict[str, Any]]:
    """Tenants whose workspace mode is b2b or hybrid (insights only applies there).

    Falls back to all tenants if the new V3 `mode` field is missing on legacy
    docs — that's the safer default while we migrate.
    """
    cur = tenants_col.find(
        {
            "$or": [
                {"settings.mode": {"$in": ["b2b", "hybrid"]}},
                {"settings.workspace_type": {"$in": ["b2b", "hybrid"]}},
                {"mode": {"$in": ["b2b", "hybrid"]}},
            ]
        },
        {"_id": 0},
    )
    return list(cur)


async def run_b2b_insight_scan_once() -> Dict[str, Any]:
    """One full sweep across every eligible tenant — used by the cron loop."""
    out: Dict[str, Any] = {
        "ran_at": _now_iso(),
        "tenants_scanned": 0,
        "total_insights_created": 0,
        "per_tenant": [],
    }
    for tenant in _b2b_eligible_tenants():
        try:
            result = await run_insight_scan_for_tenant(tenant)
            out["tenants_scanned"] += 1
            out["total_insights_created"] += result["insights_created"]
            out["per_tenant"].append({
                "tenant_id": tenant["id"],
                "scanned": result["scanned"],
                "insights_created": result["insights_created"],
            })
        except Exception as e:
            logger.exception(f"[b2b_insight_scan] tenant {tenant.get('id')} failed: {e}")
    return out


async def b2b_insight_scan_loop() -> None:
    """Background cron — runs once per 24h. Never raises (always re-loops)."""
    logger.info("[b2b_insight_scan] loop started — tick every 24h")
    # Stagger first run by 5 minutes so we don't compete with startup migration.
    await asyncio.sleep(5 * 60)
    while True:
        try:
            summary = await run_b2b_insight_scan_once()
            logger.info(
                f"[b2b_insight_scan] swept {summary['tenants_scanned']} tenant(s); "
                f"created {summary['total_insights_created']} insight(s)"
            )
        except Exception as e:
            logger.exception(f"[b2b_insight_scan] sweep error: {e}")
        await asyncio.sleep(B2B_SCAN_TICK_SECONDS)


@router.get("/feed")
async def get_feed(
    tenant: dict = Depends(get_active_tenant),
    status: Optional[str] = None,
    limit: int = 50,
):
    """List insight cards for this tenant, sorted by recency + ICP score.

    Also returns scan metadata (`last_scan_at`, `last_scan_count`) and
    per-status counts so the UI can render a "Last scanned · 14m ago · 3 new"
    chip without a second round-trip.
    """
    query: Dict[str, Any] = {"tenant_id": tenant["id"]}
    if status in ("new", "sent", "dismissed"):
        query["status"] = status
    cur = insights_col.find(query, {"_id": 0}).sort([
        ("created_at", -1),
        ("icp_match_score", -1),
    ]).limit(max(1, min(limit, 200)))
    rows = list(cur)

    # Per-status counts (always tenant-wide, ignore the active filter)
    status_counts = {"new": 0, "sent": 0, "dismissed": 0, "copied": 0}
    for r in insights_col.aggregate([
        {"$match": {"tenant_id": tenant["id"]}},
        {"$group": {"_id": "$status", "n": {"$sum": 1}}},
    ]):
        status_counts[r["_id"] or "new"] = r["n"]

    # Scan metadata from tenant settings (set by run_insight_scan_for_tenant)
    pt_meta = ((tenant.get("settings") or {}).get("pt_insights") or {})
    return {
        "ok": True,
        "count": len(rows),
        "cards": rows,
        "status_counts": status_counts,
        "last_scan_at": pt_meta.get("last_scan_at"),
        "last_scan_count": pt_meta.get("last_scan_count"),
    }


@router.post("/{insight_id}/action")
async def action_on_insight(
    insight_id: str,
    payload: InsightActionPayload,
    tenant: dict = Depends(require_tenant_role(["owner", "admin", "master_admin", "sales_rep"])),
):
    card = insights_col.find_one({"id": insight_id, "tenant_id": tenant["id"]}, {"_id": 0})
    if not card:
        raise HTTPException(404, "Insight not found")

    status_map = {"send": "sent", "copy": "copied", "dismiss": "dismissed", "snooze": "snoozed"}
    new_status = status_map.get(payload.action)
    if not new_status:
        raise HTTPException(400, "Invalid action")

    set_doc: Dict[str, Any] = {
        "status": new_status,
        "actioned_at": _now_iso(),
        "actioned_action": payload.action,
    }

    # Edit + Send flow — persist the edited body so the audit trail shows what
    # actually shipped, not the AI's original suggestion.
    if payload.action == "send" and payload.message and payload.message.strip():
        set_doc["sent_message"] = payload.message.strip()
    elif payload.action == "send":
        set_doc["sent_message"] = card.get("suggested_message") or ""

    # Snooze flow — hide until snooze_until (ISO). Default to 2 days if not given.
    if payload.action == "snooze":
        if payload.snooze_until and payload.snooze_until.strip():
            set_doc["snooze_until"] = payload.snooze_until.strip()
        else:
            from datetime import datetime as _dt, timezone as _tz, timedelta as _td
            set_doc["snooze_until"] = (_dt.now(_tz.utc) + _td(days=2)).isoformat()

    insights_col.update_one(
        {"id": insight_id, "tenant_id": tenant["id"]},
        {"$set": set_doc},
    )
    return {
        "ok": True,
        "id": insight_id,
        "status": new_status,
        "snooze_until": set_doc.get("snooze_until"),
        "sent_message": set_doc.get("sent_message"),
    }


# iter105 — Snooze recovery: every hour, any snoozed card whose snooze_until
# has passed flips back to "new" so it reappears in the feed.
async def snooze_recovery_loop():
    import asyncio
    from datetime import datetime as _dt, timezone as _tz
    while True:
        try:
            now_iso = _dt.now(_tz.utc).isoformat()
            res = insights_col.update_many(
                {"status": "snoozed", "snooze_until": {"$lte": now_iso}},
                {"$set": {"status": "new"}, "$unset": {"snooze_until": ""}},
            )
            if res.modified_count:
                print(f"[snooze_recovery] reactivated {res.modified_count} card(s)")
        except Exception as e:
            print(f"[snooze_recovery] error: {e}")
        await asyncio.sleep(3600)  # 1h

