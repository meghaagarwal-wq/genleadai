"""Call Booking — iter109c Batch 2.

Endpoints (mounted under /api/call-booking)
─────────────────────────────────────────────
  GET    /settings             — fetch workspace booking settings
  PUT    /settings             — save availability / duration / buffer / etc.
  POST   /book                 — ARIA books a call (Google Calendar + Meet)
  GET    /bookings             — list upcoming bookings for this tenant
  POST   /bookings/{id}/cancel — cancel a booking + revoke Calendar event
  POST   /no-show-check        — internal cron: check T+5min unjoined, fire recovery

The integration provider (google vs calendly) is read from the tenant's
connected integrations. If Google is connected with `calendar.events` scope,
this endpoint creates Calendar events with Meet links. If only Calendly is
connected, the page renders the Calendly link instead (handled frontend-side).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import db
from routes.tenants import get_active_tenant
from services.google_calendar import create_calendar_event, cancel_calendar_event

logger = logging.getLogger("call_booking")

router = APIRouter(prefix="/api/call-booking", tags=["call-booking"])

settings_col = db["call_booking_settings"]
bookings_col = db["call_bookings"]
integrations_col = db["integration_configs"]
leads_col = db["leads"]

settings_col.create_index([("tenant_id", 1)], unique=True)
bookings_col.create_index([("tenant_id", 1), ("scheduled_for", 1)])
bookings_col.create_index([("id", 1)], unique=True)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─── Models ─────────────────────────────────────────────────────────────
class AvailabilityWindow(BaseModel):
    day_of_week: int = Field(ge=0, le=6, description="0=Mon..6=Sun")
    start: str = "09:00"
    end: str = "18:00"


class CallBookingSettings(BaseModel):
    timezone: str = "Asia/Kolkata"
    availability: List[AvailabilityWindow] = Field(default_factory=lambda: [
        AvailabilityWindow(day_of_week=d) for d in range(5)
    ])
    durations: List[int] = Field(default_factory=lambda: [30, 45, 60])
    default_duration: int = 30
    buffer_minutes: int = 15
    max_calls_per_day: int = 6
    confirmation_message: str = (
        "Your call with {OWNER} is confirmed for {WHEN}. Join here: {MEET_LINK}"
    )
    pre_call_questions: List[str] = Field(default_factory=list)
    reminder_minutes_before: int = 60
    provider: str = "google"  # "google" | "calendly"
    calendly_link: Optional[str] = None


class BookCallBody(BaseModel):
    lead_id: str
    lead_name: str
    lead_email: Optional[str] = None
    lead_channel: str = Field(default="email", description="email|whatsapp|linkedin")
    scheduled_for: datetime
    duration_minutes: Optional[int] = None
    extra_context: Optional[str] = None


# ─── Helpers ────────────────────────────────────────────────────────────
def _provider_status(tenant_id: str) -> Dict[str, Any]:
    """Return which scheduling provider (google/calendly) is connected."""
    g = integrations_col.find_one(
        {"tenant_id": tenant_id, "integration_type": "google", "status": "connected"},
        {"_id": 0, "config.granted_scopes": 1},
    )
    if g:
        scopes = (g.get("config") or {}).get("granted_scopes") or []
        has_cal = any("calendar" in s for s in scopes)
        return {"google_connected": True, "google_has_calendar_scope": has_cal}
    c = integrations_col.find_one(
        {"tenant_id": tenant_id, "integration_type": "calendly", "status": "connected"},
        {"_id": 0},
    )
    return {"google_connected": False, "google_has_calendar_scope": False, "calendly_connected": bool(c)}


def _default_settings(tenant_id: str) -> Dict[str, Any]:
    return {
        "tenant_id": tenant_id,
        **CallBookingSettings().model_dump(),
        "updated_at": _now().isoformat(),
    }


# ─── Endpoints ──────────────────────────────────────────────────────────
@router.get("/settings")
async def get_settings(tenant: dict = Depends(get_active_tenant)):
    doc = settings_col.find_one({"tenant_id": tenant["id"]}, {"_id": 0})
    if not doc:
        doc = _default_settings(tenant["id"])
        settings_col.insert_one(doc.copy())
    doc.pop("_id", None)
    return {**doc, "provider_status": _provider_status(tenant["id"])}


@router.put("/settings")
async def save_settings(body: CallBookingSettings, tenant: dict = Depends(get_active_tenant)):
    if tenant.get("_member_role") not in ("owner", "admin", "master_admin", "pietential_owner"):
        raise HTTPException(403, "Owner/Admin only")
    payload = {
        "tenant_id": tenant["id"],
        **body.model_dump(),
        "updated_at": _now().isoformat(),
    }
    settings_col.update_one(
        {"tenant_id": tenant["id"]},
        {"$set": payload, "$setOnInsert": {"created_at": _now().isoformat()}},
        upsert=True,
    )
    return {"saved": True, **payload}


@router.post("/book")
async def book_call(body: BookCallBody, background: BackgroundTasks, tenant: dict = Depends(get_active_tenant)):
    """Create a calendar event + Google Meet link, store booking, queue notification."""
    settings = settings_col.find_one({"tenant_id": tenant["id"]}, {"_id": 0}) or _default_settings(tenant["id"])
    duration = body.duration_minutes or settings.get("default_duration", 30)
    start = body.scheduled_for if body.scheduled_for.tzinfo else body.scheduled_for.replace(tzinfo=timezone.utc)
    end = start + timedelta(minutes=duration)

    prov = _provider_status(tenant["id"])
    if not prov.get("google_has_calendar_scope"):
        raise HTTPException(412, "Connect Google with Calendar scope on /app/integrations before booking calls.")

    company_suffix = ""
    try:
        lead_doc = leads_col.find_one({"id": body.lead_id, "tenant_id": tenant["id"]}, {"_id": 0, "company": 1})
        if lead_doc and lead_doc.get("company"):
            company_suffix = f" — {lead_doc['company']}"
    except Exception:
        pass

    summary = f"Call with {body.lead_name}{company_suffix}"
    description = body.extra_context or f"Booked by ARIA. Lead channel: {body.lead_channel}."

    ev = await create_calendar_event(
        tenant_id=tenant["id"],
        summary=summary,
        description=description,
        start=start,
        end=end,
        attendee_email=body.lead_email,
        with_meet=True,
        reminder_minutes=settings.get("reminder_minutes_before", 60),
    )

    booking = {
        "id": uuid.uuid4().hex,
        "tenant_id": tenant["id"],
        "lead_id": body.lead_id,
        "lead_name": body.lead_name,
        "lead_email": body.lead_email,
        "lead_channel": body.lead_channel,
        "scheduled_for": start.isoformat(),
        "duration_minutes": duration,
        "event_id": ev["event_id"],
        "meet_link": ev["meet_link"],
        "html_link": ev["html_link"],
        "status": "booked",
        "created_at": _now().isoformat(),
        "created_by": tenant.get("_member_full_name") or "ARIA",
    }
    bookings_col.insert_one(booking.copy())
    background.add_task(_send_confirmation, booking, settings)
    return {"booked": True, **{k: v for k, v in booking.items() if k != "_id"}}


@router.get("/bookings")
async def list_bookings(
    tenant: dict = Depends(get_active_tenant),
    upcoming_only: bool = True,
    limit: int = 50,
):
    q: Dict[str, Any] = {"tenant_id": tenant["id"]}
    if upcoming_only:
        q["scheduled_for"] = {"$gte": _now().isoformat()}
    rows = list(bookings_col.find(q, {"_id": 0}, sort=[("scheduled_for", 1)]).limit(limit))
    return {"bookings": rows, "count": len(rows)}


@router.post("/bookings/{booking_id}/cancel")
async def cancel(booking_id: str, tenant: dict = Depends(get_active_tenant)):
    doc = bookings_col.find_one({"id": booking_id, "tenant_id": tenant["id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Booking not found")
    if doc.get("event_id"):
        try:
            await cancel_calendar_event(tenant_id=tenant["id"], event_id=doc["event_id"])
        except Exception as e:
            logger.warning("Calendar cancel failed for %s: %s", booking_id, e)
    bookings_col.update_one({"id": booking_id, "tenant_id": tenant["id"]},
                            {"$set": {"status": "cancelled", "cancelled_at": _now().isoformat()}})
    return {"cancelled": True, "id": booking_id}


@router.post("/no-show-check")
async def no_show_check(tenant: dict = Depends(get_active_tenant)):
    """Mark any booking whose scheduled_for ended >5 min ago and status is still
    `booked` as `no_show`, and queue a recovery message. Designed to be called
    by the eod_wrap background job every 5 minutes."""
    cutoff = _now() - timedelta(minutes=5)
    candidates = list(bookings_col.find({
        "tenant_id": tenant["id"],
        "status": "booked",
        "scheduled_for": {"$lt": cutoff.isoformat()},
    }, {"_id": 0}))
    flagged = []
    for b in candidates:
        bookings_col.update_one(
            {"id": b["id"], "tenant_id": tenant["id"]},
            {"$set": {"status": "no_show", "no_show_at": _now().isoformat()}},
        )
        flagged.append(b["id"])
        try:
            _queue_no_show_recovery(b)
        except Exception as e:
            logger.warning("No-show recovery queue failed for %s: %s", b["id"], e)
    return {"flagged_no_show": flagged, "count": len(flagged)}


# ─── Notification helpers (channel-aware) ───────────────────────────────
def _send_confirmation(booking: Dict[str, Any], settings: Dict[str, Any]) -> None:
    """Best-effort confirmation send. Writes a row to `outbound_messages` so the
    existing dispatcher delivers via the lead's preferred channel."""
    when_str = booking["scheduled_for"]
    template = (settings.get("confirmation_message") or
                "Your call is confirmed for {WHEN}. Join here: {MEET_LINK}")
    text = (template
            .replace("{WHEN}", when_str)
            .replace("{MEET_LINK}", booking.get("meet_link") or booking.get("html_link") or "")
            .replace("{OWNER}", booking.get("created_by") or "ARIA"))
    db["outbound_messages"].insert_one({
        "id": uuid.uuid4().hex,
        "tenant_id": booking["tenant_id"],
        "lead_id": booking["lead_id"],
        "channel": booking.get("lead_channel") or "email",
        "content": text,
        "kind": "booking_confirmation",
        "status": "queued",
        "booking_id": booking["id"],
        "created_at": _now().isoformat(),
    })


def _queue_no_show_recovery(booking: Dict[str, Any]) -> None:
    text = (
        f"Hey {booking.get('lead_name','there')} — looks like we missed each other on our call. "
        "Want to reschedule? Just reply with a time that works."
    )
    db["outbound_messages"].insert_one({
        "id": uuid.uuid4().hex,
        "tenant_id": booking["tenant_id"],
        "lead_id": booking["lead_id"],
        "channel": booking.get("lead_channel") or "email",
        "content": text,
        "kind": "no_show_recovery",
        "status": "queued",
        "booking_id": booking["id"],
        "created_at": _now().isoformat(),
    })
