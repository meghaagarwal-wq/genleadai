"""Iter103 — Real-time updates + Onboarding state persistence.

Two small endpoints that close audit gaps §6.6 and §19.8.

1. `GET /api/realtime/since?ts=<iso>` — returns NEW leads + insight cards
   created after `ts`. UI polls this every 10s for near-real-time Lead
   Inbox / Conversations refresh without the complexity of SSE.

2. `GET /api/onboarding/state` + `PUT /api/onboarding/state` — persists
   the wizard's current step so users can resume from where they left
   off. Per-user (not per-tenant) so it follows the human, not the
   workspace.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from deps import db, get_current_user
from routes.tenants import get_active_tenant

router = APIRouter(prefix="/api", tags=["realtime-onboarding"])

leads_col = db["leads"]
insights_col = db["pt_insights"]
onboarding_col = db["onboarding_state"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── 1. Real-time polling ───────────────────────────────────────────────────
@router.get("/realtime/since")
async def realtime_since(
    ts: Optional[str] = None,
    tenant: dict = Depends(get_active_tenant),
):
    """Return new leads + insights created strictly AFTER `ts` (ISO 8601).

    If `ts` is omitted, returns "now" with empty arrays — useful for the
    UI to bootstrap a poll cursor.
    """
    cursor = ts or _now()
    new_leads = list(leads_col.find(
        {"tenant_id": tenant["id"], "created_at": {"$gt": cursor}},
        {"_id": 0},
    ).sort("created_at", -1).limit(50))
    new_insights = list(insights_col.find(
        {"tenant_id": tenant["id"], "created_at": {"$gt": cursor}},
        {"_id": 0},
    ).sort("created_at", -1).limit(50))
    return {
        "ok": True,
        "now":          _now(),
        "since":        cursor,
        "new_leads":    new_leads,
        "lead_count":   len(new_leads),
        "new_insights": new_insights,
        "insight_count": len(new_insights),
    }


# ─── 2. Onboarding state ────────────────────────────────────────────────────
class OnboardingState(BaseModel):
    step: int = Field(default=0, ge=0, le=10)
    business_name: Optional[str] = Field(default=None, max_length=200)
    mode: Optional[str] = Field(default=None, max_length=20)
    lead_source: Optional[str] = Field(default=None, max_length=40)
    completed: bool = False
    payload: Dict[str, Any] = Field(default_factory=dict)


@router.get("/onboarding/state")
async def get_onboarding_state(current_user: dict = Depends(get_current_user)):
    """Per-user resumable wizard state. Bootstrap-empty if first visit."""
    doc = onboarding_col.find_one({"user_email": current_user["email"]}, {"_id": 0})
    if not doc:
        return {"ok": True, "state": OnboardingState().model_dump(), "is_new": True}
    # Don't leak _id / user_email back to caller.
    doc.pop("user_email", None)
    return {"ok": True, "state": doc, "is_new": False}


@router.put("/onboarding/state")
async def update_onboarding_state(
    payload: OnboardingState,
    current_user: dict = Depends(get_current_user),
):
    state = payload.model_dump()
    state["user_email"] = current_user["email"]
    state["updated_at"] = _now()
    onboarding_col.update_one(
        {"user_email": current_user["email"]},
        {"$set": state, "$setOnInsert": {"created_at": _now()}},
        upsert=True,
    )
    return {"ok": True}
