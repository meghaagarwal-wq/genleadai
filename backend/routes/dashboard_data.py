"""ARIA — Phase A data-foundation helper.

iter150 — Centralised write hooks + lookups for the new dashboard
collections introduced in this iteration:

  • `score_history`   — audit trail of score changes per lead
  • `booking_events`  — every booked meeting (referenced by KPI tiles)
  • `asset_clicks`    — click telemetry for lead-magnet performance
  • tenant.mode       — 'b2c' | 'b2b' | 'hybrid'
  • tenant.currency   — 'INR' / 'USD' / 'GBP' / 'AED' / 'EUR'
  • tenant.hourly_rate_assumption — int (used for ARIA Time Saved $)

All writes are tenant-scoped and idempotent where it matters.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid

from deps import db

_score_hist = db["score_history"]
_bookings = db["booking_events"]
_asset_clicks = db["asset_clicks"]
_tenants = db["tenants"]


def _iso(dt: Optional[datetime] = None) -> str:
    return (dt or datetime.now(timezone.utc)).isoformat()


# ─────────────── tenant.mode / currency / hourly_rate ───────────
DEFAULT_HOURLY_RATE = {
    "INR": 3500,
    "USD": 45,
    "GBP": 38,
    "AED": 165,
    "EUR": 42,
}


def get_tenant_mode(tenant_id: str) -> str:
    """Returns 'b2c' | 'b2b' | 'hybrid'. Defaults to 'hybrid' if unset."""
    t = _tenants.find_one({"id": tenant_id}, {"_id": 0, "mode": 1, "settings.workspace_type": 1}) or {}
    mode = t.get("mode") or (t.get("settings") or {}).get("workspace_type") or "hybrid"
    return mode if mode in ("b2c", "b2b", "hybrid") else "hybrid"


def get_tenant_currency(tenant_id: str) -> str:
    t = _tenants.find_one({"id": tenant_id}, {"_id": 0, "currency": 1}) or {}
    return t.get("currency") or "USD"


def get_tenant_hourly_rate(tenant_id: str) -> int:
    t = _tenants.find_one({"id": tenant_id}, {"_id": 0, "hourly_rate_assumption": 1, "currency": 1}) or {}
    rate = t.get("hourly_rate_assumption")
    if rate:
        return int(rate)
    return DEFAULT_HOURLY_RATE.get(t.get("currency") or "USD", 45)


# ─────────────── score_history writes ───────────────────────────
def log_score_change(
    tenant_id: str,
    lead_id: str,
    new_score: int,
    *,
    prev_score: Optional[int] = None,
    reason: Optional[str] = None,
    source: str = "system",
) -> None:
    """Insert a `score_history` row whenever a pt_leads.score changes.

    This row powers:
      • Why Now Feed   (score_delta > 10 in last 24h)
      • Momentum tile  (trend over 14 days)
      • Ghost-Lead Recovery (lookup highest historical score)
    """
    if prev_score is None:
        prev_score = 0
    delta = (new_score or 0) - (prev_score or 0)
    if delta == 0:
        return
    _score_hist.insert_one({
        "id": f"sh_{uuid.uuid4().hex[:14]}",
        "tenant_id": tenant_id,
        "lead_id": lead_id,
        "prev_score": int(prev_score or 0),
        "new_score": int(new_score or 0),
        "delta": int(delta),
        "reason": reason,
        "source": source,
        "created_at": _iso(),
    })


def latest_score_changes(tenant_id: str, *, since_iso: str, min_delta: int = 10, limit: int = 25):
    """Score-history rows for the Why Now Feed."""
    return list(_score_hist.find(
        {"tenant_id": tenant_id, "created_at": {"$gte": since_iso},
         "$or": [{"delta": {"$gte": min_delta}}, {"delta": {"$lte": -min_delta}}]},
        {"_id": 0},
    ).sort("created_at", -1).limit(limit))


# ─────────────── booking_events writes ──────────────────────────
def log_booking(
    tenant_id: str,
    lead_id: str,
    *,
    when_iso: str,
    channel: str = "calendar",
    deal_value: Optional[float] = None,
    booked_by: Optional[str] = None,
) -> str:
    """Insert a `booking_events` row when a meeting is set."""
    bid = f"bk_{uuid.uuid4().hex[:14]}"
    _bookings.insert_one({
        "id": bid,
        "tenant_id": tenant_id,
        "lead_id": lead_id,
        "when": when_iso,
        "channel": channel,
        "deal_value": float(deal_value or 0),
        "booked_by": booked_by,
        "created_at": _iso(),
    })
    return bid


# ─────────────── asset_clicks writes ────────────────────────────
def log_asset_click(
    tenant_id: str,
    asset_id: str,
    *,
    asset_name: str,
    lead_id: Optional[str] = None,
    channel: Optional[str] = None,
) -> None:
    _asset_clicks.insert_one({
        "id": f"ac_{uuid.uuid4().hex[:14]}",
        "tenant_id": tenant_id,
        "asset_id": asset_id,
        "asset_name": asset_name,
        "lead_id": lead_id,
        "channel": channel,
        "created_at": _iso(),
    })


# ─────────────── Index creation (one-shot, idempotent) ──────────
def ensure_indexes() -> Dict[str, Any]:
    """Idempotent index creation for the new collections. Called once
    at app boot (server.py startup) — keep this cheap."""
    created = {}
    try:
        _score_hist.create_index([("tenant_id", 1), ("created_at", -1)])
        _score_hist.create_index([("tenant_id", 1), ("lead_id", 1), ("created_at", -1)])
        created["score_history"] = "ok"
    except Exception as e:
        created["score_history"] = str(e)
    try:
        _bookings.create_index([("tenant_id", 1), ("when", -1)])
        _bookings.create_index([("tenant_id", 1), ("lead_id", 1)])
        created["booking_events"] = "ok"
    except Exception as e:
        created["booking_events"] = str(e)
    try:
        _asset_clicks.create_index([("tenant_id", 1), ("created_at", -1)])
        _asset_clicks.create_index([("tenant_id", 1), ("asset_id", 1)])
        created["asset_clicks"] = "ok"
    except Exception as e:
        created["asset_clicks"] = str(e)
    return created


__all__ = [
    "get_tenant_mode", "get_tenant_currency", "get_tenant_hourly_rate",
    "log_score_change", "log_booking", "log_asset_click",
    "latest_score_changes", "ensure_indexes",
]
