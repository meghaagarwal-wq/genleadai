"""iter109 Batch 2 — Command Center KPIs in the exact Aria Dashboard spec shape.

Returns the four KPI tiles per mode that the rebuilt Command Center page
renders. All values come from real database aggregates — no hardcoded data.

  B2B:    signals_today | prospects_scanned | high_conf_signals | cards_actioned_week
  B2C:    new_leads_today | active_conversations | calls_booked_today | needs_attention
  Hybrid: total_leads_plus_prospects | instinct_signals | calls_booked_today | aria_actions_today

Endpoints
─────────
GET  /api/aria/command-center/kpis      — mode-aware KPI grid
GET  /api/aria/command-center/signals   — top 2 instinct cards (B2B / Hybrid hero block)
GET  /api/aria/command-center/pipeline  — first 6 leads for the B2C pipeline preview
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from deps import db
from routes.tenants import get_active_tenant
from routes.aria_training import get_workspace_type

router = APIRouter(prefix="/api/aria/command-center", tags=["command-center"])

# ─── DB collections ─────────────────────────────────────────────────────
_leads_col = db["leads"]
_insights_col = db["insights"]              # B2B insight cards
_conversations_col = db["conversations"]
_bookings_col = db["call_bookings"]
_actions_col = db["aria_actions"]           # any ARIA-fired actions
_accounts_col = db["accounts"]              # prospects watched (B2B)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _start_of_today_utc() -> datetime:
    n = _now()
    return n.replace(hour=0, minute=0, second=0, microsecond=0)


def _start_of_week_utc() -> datetime:
    """Monday 00:00 UTC of the current week."""
    today = _start_of_today_utc()
    return today - timedelta(days=today.weekday())


def _b2b_kpis(tenant_id: str) -> Dict[str, Any]:
    today_start = _start_of_today_utc()
    week_start = _start_of_week_utc()

    signals_today = _insights_col.count_documents({
        "tenant_id": tenant_id, "created_at": {"$gte": today_start.isoformat()},
    })
    prospects_scanned = _accounts_col.count_documents({"tenant_id": tenant_id})
    high_conf = _insights_col.count_documents({
        "tenant_id": tenant_id, "confidence": {"$gte": 0.85},
    })
    cards_actioned = _insights_col.count_documents({
        "tenant_id": tenant_id,
        "status": {"$in": ["sent", "copied", "snoozed"]},
        "updated_at": {"$gte": week_start.isoformat()},
    })

    # Delta vs yesterday (signals_today only — most useful momentum signal)
    yesterday_start = today_start - timedelta(days=1)
    signals_yesterday = _insights_col.count_documents({
        "tenant_id": tenant_id,
        "created_at": {"$gte": yesterday_start.isoformat(), "$lt": today_start.isoformat()},
    })
    delta = signals_today - signals_yesterday

    return {
        "items": [
            {"key": "signals_today",      "label": "Signals Today",            "value": signals_today,
             "delta": delta, "delta_label": f"{'↑' if delta >= 0 else '↓'} {abs(delta)} from yesterday" if delta else "—", "accent": "purple"},
            {"key": "prospects_scanned",  "label": "Prospects Scanned",        "value": prospects_scanned,
             "delta_label": f"of {prospects_scanned} watched"},
            {"key": "high_conf_signals",  "label": "High-Confidence Signals",  "value": high_conf,
             "delta_label": "≥ 0.85 confidence", "accent": "amber"},
            {"key": "cards_actioned",     "label": "Cards Actioned",           "value": cards_actioned,
             "delta_label": "this week", "accent": "green"},
        ],
    }


def _b2c_kpis(tenant_id: str) -> Dict[str, Any]:
    today_start = _start_of_today_utc()
    yesterday_start = today_start - timedelta(days=1)
    stale_cutoff = _now() - timedelta(hours=48)

    new_today = _leads_col.count_documents({
        "tenant_id": tenant_id, "created_at": {"$gte": today_start.isoformat()},
    })
    new_yesterday = _leads_col.count_documents({
        "tenant_id": tenant_id,
        "created_at": {"$gte": yesterday_start.isoformat(), "$lt": today_start.isoformat()},
    })
    active = _conversations_col.count_documents({
        "tenant_id": tenant_id, "status": {"$in": ["active", "open", "engaged"]},
    })
    calls_today = _bookings_col.count_documents({
        "tenant_id": tenant_id, "created_at": {"$gte": today_start.isoformat()},
    })
    needs_attention = _leads_col.count_documents({
        "tenant_id": tenant_id,
        "status": {"$in": ["stalled", "nurturing"]},
        "updated_at": {"$lte": stale_cutoff.isoformat()},
    })
    delta = new_today - new_yesterday

    return {
        "items": [
            {"key": "new_leads_today",      "label": "New Leads Today",       "value": new_today,
             "delta": delta, "delta_label": f"{'↑' if delta >= 0 else '↓'} {abs(delta)} from yesterday" if delta else "—", "accent": "amber"},
            {"key": "active_conversations", "label": "Active Conversations",  "value": active,
             "delta_label": "ARIA handling all"},
            {"key": "calls_booked_today",   "label": "Calls Booked Today",    "value": calls_today,
             "delta_label": "today", "accent": "green"},
            {"key": "needs_attention",      "label": "Needs Attention",       "value": needs_attention,
             "delta_label": "stalled > 48h", "accent": "red"},
        ],
    }


def _hybrid_kpis(tenant_id: str) -> Dict[str, Any]:
    today_start = _start_of_today_utc()

    total = (
        _leads_col.count_documents({"tenant_id": tenant_id})
        + _accounts_col.count_documents({"tenant_id": tenant_id})
    )
    b2b_count = _accounts_col.count_documents({"tenant_id": tenant_id})
    b2c_count = _leads_col.count_documents({"tenant_id": tenant_id})

    pending_signals = _insights_col.count_documents({
        "tenant_id": tenant_id, "status": {"$in": ["new", "pending"]},
    })
    calls_today = _bookings_col.count_documents({
        "tenant_id": tenant_id, "created_at": {"$gte": today_start.isoformat()},
    })
    aria_actions = _actions_col.count_documents({
        "tenant_id": tenant_id, "created_at": {"$gte": today_start.isoformat()},
    })

    return {
        "items": [
            {"key": "total_leads_plus_prospects", "label": "Total Leads + Prospects", "value": total,
             "delta_label": f"{b2b_count} B2B · {b2c_count} B2C"},
            {"key": "instinct_signals",           "label": "Instinct Signals",        "value": pending_signals,
             "delta_label": "pending action", "accent": "purple"},
            {"key": "calls_booked_today",         "label": "Calls Booked Today",      "value": calls_today,
             "delta_label": "today", "accent": "green"},
            {"key": "aria_actions_today",         "label": "ARIA Actions Today",      "value": aria_actions,
             "delta_label": "messages + scores"},
        ],
    }


# ─── Endpoints ──────────────────────────────────────────────────────────
@router.get("/kpis")
async def kpis(tenant: dict = Depends(get_active_tenant)):
    """Return the 4 KPI tiles for the current workspace mode.

    Response: { mode: "b2b"|"b2c"|"hybrid", items: [{key,label,value,delta?,delta_label?,accent?}] }
    """
    mode = get_workspace_type(tenant)
    if mode == "b2b":
        data = _b2b_kpis(tenant["id"])
    elif mode == "b2c":
        data = _b2c_kpis(tenant["id"])
    else:
        data = _hybrid_kpis(tenant["id"])
    return {"mode": mode, **data}


@router.get("/signals")
async def top_signals(tenant: dict = Depends(get_active_tenant)):
    """Top 2 insight cards for the Command Center B2B/Hybrid hero block."""
    rows = list(_insights_col.find(
        {"tenant_id": tenant["id"], "status": {"$in": ["new", "pending"]}},
        {"_id": 0},
        sort=[("confidence", -1), ("created_at", -1)],
        limit=2,
    ))
    return {"signals": rows, "total_pending": _insights_col.count_documents(
        {"tenant_id": tenant["id"], "status": {"$in": ["new", "pending"]}}
    )}


@router.get("/pipeline")
async def lead_pipeline(tenant: dict = Depends(get_active_tenant)):
    """First 6 leads for the B2C/Hybrid Lead Pipeline preview table."""
    rows = list(_leads_col.find(
        {"tenant_id": tenant["id"]},
        {"_id": 0, "id": 1, "name": 1, "company": 1, "source": 1, "icp_score": 1,
         "icp_fit_score": 1, "status": 1, "channel": 1, "created_at": 1},
        sort=[("created_at", -1)],
        limit=6,
    ))
    return {"leads": rows}


@router.get("/next-scan")
async def next_scan(tenant: dict = Depends(get_active_tenant)):
    """When the next B2B daily scan will run for this workspace."""
    settings = (tenant.get("settings") or {})
    tp = settings.get("aria_training_profile", {}).get("data", {})
    time_str = tp.get("digest_time") or "07:00"
    tz = tp.get("digest_timezone") or "Asia/Kolkata"
    return {"next_scan_time": time_str, "timezone": tz}
