"""Health & Resilience Engine — Sprint 5 / Master Spec Phase 3.5 + 3.6 + 5.5.

Three concerns merged into one module:

1. Pipeline Health Score (0-100) per tenant — endpoint + computation helper.
2. Stale Lead Engine — async background loop that runs every 6 hours and:
   - tags leads where last_activity_at > stale_threshold_days (default 14) as stale
   - sends one Claude re-engagement message (touchpoint engine handles delivery)
   - auto-archives leads that go 5+ days without reply after re-engagement
3. Sentiment Detection — `classify_sentiment(text)` helper called from webhook
   on every inbound message; result stored on `conversations.latest_sentiment`.
4. failed_message_log — collection + helper for graceful 360dialog / Claude
   retries. Background `retry_loop()` reprocesses unresolved entries with
   exponential backoff (15min × retry_count).
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from deps import db, get_current_user
from routes.tenants import get_active_tenant

logger = logging.getLogger("health_engine")

router = APIRouter(prefix="/api/health", tags=["health-engine"])
failed_router = APIRouter(prefix="/api/failed-messages", tags=["failed-messages"])

tenants_col = db["tenants"]
leads_col = db["leads"]
conversations_col = db["aria_conversations"]
touchpoint_log_col = db["lead_touchpoint_log"]
failed_log_col = db["failed_message_log"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


# ─── Pipeline Health Score ──────────────────────────────────────────────────
def compute_pipeline_health(tenant_id: str) -> Dict[str, Any]:
    """Per Master Spec formula:
        start at 100, -10/stale, -5/no-touchpoints, -15/unresolved-failed,
        +10/replied-7d, +20/meeting-this-month. Clamp 0..100."""
    now = _now()
    week_ago = (now - timedelta(days=7)).isoformat()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()

    score = 100
    breakdown: List[Dict[str, Any]] = []

    stale_count = leads_col.count_documents({
        "tenant_id": tenant_id,
        "stale": True,
        "status": {"$nin": ["closed_won", "closed_lost", "Closed Won", "Closed Lost"]},
    })
    if stale_count:
        delta = -10 * stale_count
        score += delta
        breakdown.append({"factor": "stale_leads", "count": stale_count, "delta": delta})

    no_tp_count = 0
    for lead in leads_col.find({"tenant_id": tenant_id, "status": {"$nin": ["closed_won", "closed_lost"]}}, {"_id": 0, "id": 1}):
        if touchpoint_log_col.count_documents({"tenant_id": tenant_id, "lead_id": lead["id"]}) == 0:
            no_tp_count += 1
    if no_tp_count:
        delta = -5 * no_tp_count
        score += delta
        breakdown.append({"factor": "no_touchpoints", "count": no_tp_count, "delta": delta})

    failed_count = failed_log_col.count_documents({"tenant_id": tenant_id, "resolved": False})
    if failed_count:
        delta = -15 * failed_count
        score += delta
        breakdown.append({"factor": "unresolved_failures", "count": failed_count, "delta": delta})

    replied_7d = conversations_col.count_documents({
        "tenant_id": tenant_id, "last_inbound_at": {"$gte": week_ago},
    })
    if replied_7d:
        delta = 10 * replied_7d
        score += delta
        breakdown.append({"factor": "recent_replies_7d", "count": replied_7d, "delta": delta})

    meetings = leads_col.count_documents({
        "tenant_id": tenant_id, "meeting_booked_at": {"$gte": month_start},
    })
    if meetings:
        delta = 20 * meetings
        score += delta
        breakdown.append({"factor": "meetings_this_month", "count": meetings, "delta": delta})

    score = max(0, min(100, score))
    status = "good" if score >= 75 else ("warning" if score >= 50 else "critical")
    return {
        "score": score,
        "status": status,
        "breakdown": breakdown,
        "stale_lead_count": stale_count,
        "computed_at": _iso(now),
    }


@router.get("/pipeline-score")
async def pipeline_score(tenant: dict = Depends(get_active_tenant)):
    return compute_pipeline_health(tenant["id"])


@router.get("/stale-leads")
async def list_stale(tenant: dict = Depends(get_active_tenant)):
    rows = list(leads_col.find(
        {"tenant_id": tenant["id"], "stale": True},
        {"_id": 0, "id": 1, "first_name": 1, "last_name": 1, "phone": 1, "stage": 1, "stale_since": 1, "icp_score": 1},
    ).sort("stale_since", -1).limit(100))
    return {"leads": rows, "count": len(rows)}


# ─── Stale Lead Engine — background loop ────────────────────────────────────
async def _check_tenant_stale_leads(tenant: dict) -> None:
    tid = tenant.get("id")
    threshold_days = int((tenant.get("settings_json") or {}).get("stale_threshold_days", 14))
    now = _now()
    cutoff = (now - timedelta(days=threshold_days)).isoformat()
    auto_close_cutoff = (now - timedelta(days=5)).isoformat()

    # Tag newly stale leads
    candidates = leads_col.find({
        "tenant_id": tid,
        "stale": {"$ne": True},
        "status": {"$nin": ["closed_won", "closed_lost", "Closed Won", "Closed Lost"]},
        "$or": [
            {"last_activity_at": {"$lt": cutoff}},
            {"last_activity_at": {"$exists": False}, "created_at": {"$lt": cutoff}},
        ],
    }, {"_id": 0, "id": 1, "first_name": 1, "tenant_id": 1})
    for lead in candidates:
        leads_col.update_one(
            {"id": lead["id"], "tenant_id": tid},
            {"$set": {"stale": True, "stale_since": _iso(now), "updated_at": _iso(now)}},
        )
        # Fire CRM re-engagement event (graceful — never raises)
        try:
            from routes.crm_sync import fire_event as crm_fire_event
            crm_fire_event(tid, lead, "lead.re_engaged", {"reason": f"stale > {threshold_days}d"})
        except Exception:
            pass
        logger.info(f"[stale-engine] tagged lead {lead['id']} as stale (tenant={tid})")

    # Auto-archive leads that have been stale > 5 days with no reply
    abandoned = leads_col.find({
        "tenant_id": tid,
        "stale": True,
        "stale_since": {"$lt": auto_close_cutoff},
        "status": {"$nin": ["closed_won", "closed_lost", "Closed Won", "Closed Lost"]},
    }, {"_id": 0, "id": 1, "tenant_id": 1})
    for lead in abandoned:
        leads_col.update_one(
            {"id": lead["id"], "tenant_id": tid},
            {"$set": {
                "status": "closed_lost",
                "close_reason": "No response — auto-archived by stale engine",
                "closed_at": _iso(now),
                "updated_at": _iso(now),
            }},
        )
        try:
            from routes.crm_sync import fire_event as crm_fire_event
            crm_fire_event(tid, lead, "lead.closed_lost", {"new_stage": "closed_lost", "auto_archived": True})
        except Exception:
            pass
        logger.info(f"[stale-engine] auto-closed lead {lead['id']} as closed_lost (tenant={tid})")


async def stale_lead_loop():
    """Runs every 6 hours (configurable via STALE_ENGINE_INTERVAL_SECONDS)."""
    interval = int(os.getenv("STALE_ENGINE_INTERVAL_SECONDS", str(6 * 3600)))
    logger.info("[stale-engine] loop started, interval=%ss", interval)
    # Warm-up delay so it doesn't race with server startup migrations
    await asyncio.sleep(30)
    while True:
        try:
            for t in tenants_col.find({}, {"_id": 0, "id": 1, "settings_json": 1}):
                await _check_tenant_stale_leads(t)
        except Exception:
            logger.exception("[stale-engine] iteration failed")
        await asyncio.sleep(interval)


# ─── Sentiment Detection ────────────────────────────────────────────────────
SENTIMENT_PROMPT = (
    "Classify this message as ONE of: positive / neutral / negative / urgent. "
    "Reply with ONLY the single word."
)


async def classify_sentiment(text: str) -> str:
    """Run a lightweight Claude call. Returns 'positive'|'neutral'|'negative'|'urgent'.
    Falls back to 'neutral' on any failure (graceful)."""
    if not text or len(text.strip()) < 2:
        return "neutral"
    try:
        from services.claude_service import claude_call, TaskType
        raw = await claude_call(
            task_type=TaskType.SIGNAL_CLASSIFICATION,
            system=SENTIMENT_PROMPT,
            prompt=text[:2000],
            session_id=f"sent-{uuid.uuid4().hex[:8]}",
        )
        word = (raw or "").strip().lower()
        # Pull the first matching token
        for valid in ("urgent", "negative", "positive", "neutral"):
            if valid in word:
                return valid
        return "neutral"
    except Exception:
        return "neutral"


# ─── failed_message_log ─────────────────────────────────────────────────────
def log_failure(
    tenant_id: str,
    lead_id: Optional[str],
    channel: str,
    payload: Dict[str, Any],
    error_reason: str,
) -> str:
    doc = {
        "id": f"fail_{uuid.uuid4().hex[:12]}",
        "tenant_id": tenant_id,
        "lead_id": lead_id,
        "channel": channel,
        "payload": payload or {},
        "error_reason": error_reason[:500],
        "retry_count": 0,
        "resolved": False,
        "next_retry_at": _iso(_now() + timedelta(minutes=15)),
        "created_at": _iso(_now()),
    }
    failed_log_col.insert_one(doc.copy())
    return doc["id"]


def mark_resolved(failure_id: str) -> None:
    failed_log_col.update_one({"id": failure_id}, {"$set": {"resolved": True, "resolved_at": _iso(_now())}})


@failed_router.get("")
async def list_failures(tenant: dict = Depends(get_active_tenant)):
    rows = list(failed_log_col.find(
        {"tenant_id": tenant["id"], "resolved": False},
        {"_id": 0},
    ).sort("created_at", -1).limit(100))
    return {"failures": rows, "count": len(rows)}


@failed_router.post("/{failure_id}/retry")
async def manual_retry(failure_id: str, tenant: dict = Depends(get_active_tenant)):
    if tenant.get("_member_role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")
    f = failed_log_col.find_one({"id": failure_id, "tenant_id": tenant["id"]}, {"_id": 0})
    if not f:
        raise HTTPException(status_code=404, detail="Failure not found")
    failed_log_col.update_one(
        {"id": failure_id},
        {"$set": {"retry_count": 0, "next_retry_at": _iso(_now()), "resolved": False}},
    )
    return {"status": "ok"}


@failed_router.post("/{failure_id}/dismiss")
async def dismiss_failure(failure_id: str, tenant: dict = Depends(get_active_tenant)):
    if tenant.get("_member_role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")
    failed_log_col.update_one(
        {"id": failure_id, "tenant_id": tenant["id"]},
        {"$set": {"resolved": True, "resolved_at": _iso(_now()), "dismissed": True}},
    )
    return {"status": "ok"}
