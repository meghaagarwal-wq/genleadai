"""Notification preferences — Settings → Notifications tab.

Stores per-tenant notification preferences for in-app + email channels.
Master spec phase 4.2.

Collections:
  - tenant_notification_prefs  {tenant_id, channels: {email, in_app}, events: {key: {email, in_app}}}
"""
from __future__ import annotations
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import db, get_current_user
from routes.tenants import get_active_tenant

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

prefs_collection = db["tenant_notification_prefs"]

EVENT_KEYS = [
    "new_hot_lead",        # Aria flags a brand-new hot lead
    "stale_lead_alert",    # Lead has gone cold (14+ days)
    "failed_message",      # Outbound message failed (WA/Email)
    "weekly_recap",        # Weekly performance recap (Mon 9am)
    "daily_brief",         # Daily call plan email (8am)
    "aria_escalation",     # Aria escalates a lead to human
    "meeting_booked",      # New meeting scheduled
]

DEFAULTS = {
    "new_hot_lead":     {"email": True,  "in_app": True},
    "stale_lead_alert": {"email": False, "in_app": True},
    "failed_message":   {"email": True,  "in_app": True},
    "weekly_recap":     {"email": True,  "in_app": False},
    "daily_brief":      {"email": True,  "in_app": False},
    "aria_escalation":  {"email": True,  "in_app": True},
    "meeting_booked":   {"email": False, "in_app": True},
}


class EventPref(BaseModel):
    email: bool = False
    in_app: bool = False


class NotificationPrefsPayload(BaseModel):
    events: Dict[str, EventPref] = Field(default_factory=dict)
    quiet_hours_enabled: bool = False
    quiet_start_hour: int = Field(22, ge=0, le=23)  # local hr
    quiet_end_hour: int = Field(8, ge=0, le=23)


def _doc_or_default(tenant_id: str) -> Dict[str, Any]:
    doc = prefs_collection.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if doc:
        # Backfill any missing event keys with defaults
        events = doc.get("events") or {}
        for k, v in DEFAULTS.items():
            events.setdefault(k, dict(v))
        doc["events"] = events
        doc.setdefault("quiet_hours_enabled", False)
        doc.setdefault("quiet_start_hour", 22)
        doc.setdefault("quiet_end_hour", 8)
        return doc
    return {
        "tenant_id": tenant_id,
        "events": {k: dict(v) for k, v in DEFAULTS.items()},
        "quiet_hours_enabled": False,
        "quiet_start_hour": 22,
        "quiet_end_hour": 8,
    }


@router.get("/preferences")
def get_preferences(current_user: dict = Depends(get_current_user),
                    tenant: dict = Depends(get_active_tenant)):
    doc = _doc_or_default(tenant["id"])
    return {"preferences": doc, "event_keys": EVENT_KEYS}


@router.put("/preferences")
def update_preferences(payload: NotificationPrefsPayload,
                       current_user: dict = Depends(get_current_user),
                       tenant: dict = Depends(get_active_tenant)):
    # Only owner / admin can change
    role = current_user.get("tenant_role") or current_user.get("role")
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner or admin required")

    cleaned_events = {}
    for k, v in (payload.events or {}).items():
        if k in EVENT_KEYS:
            cleaned_events[k] = {"email": bool(v.email), "in_app": bool(v.in_app)}
    for k, v in DEFAULTS.items():
        cleaned_events.setdefault(k, dict(v))

    update = {
        "tenant_id": tenant["id"],
        "events": cleaned_events,
        "quiet_hours_enabled": bool(payload.quiet_hours_enabled),
        "quiet_start_hour": int(payload.quiet_start_hour),
        "quiet_end_hour": int(payload.quiet_end_hour),
    }
    prefs_collection.update_one(
        {"tenant_id": tenant["id"]},
        {"$set": update},
        upsert=True,
    )
    return {"ok": True, "preferences": _doc_or_default(tenant["id"])}
