"""iter108 — ACTION 3: server.py refactor.

Inbound webhooks (Calendly + Meta Lead Ads) extracted from server.py:2652-2732.

These two endpoints are pure ingestion handlers: they read the payload,
either upsert a lead or stamp a state change on an existing one, and
return `{received: true, …}`. They are completely independent from the
rest of server.py.

The Calendly handler calls `auto_send_lead_magnet` which still lives in
server.py — imported lazily inside the handler to avoid a circular
import at module-load time.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter

from deps import activities_collection, leads_collection

router = APIRouter(tags=["webhooks-inbound"])


@router.post("/api/webhooks/calendly")
async def calendly_webhook(request_body: Dict[str, Any]):
    """Receive Calendly webhook events (booking confirmed, no-show, etc.)."""
    event = request_body.get("event", "")
    payload = request_body.get("payload", {})

    if event == "invitee.created":
        invitee = payload.get("invitee", {})
        email = invitee.get("email")
        name = invitee.get("name", "")

        if email:
            lead = leads_collection.find_one({"email": email})
            if lead:
                lead_id = str(lead["_id"])
                leads_collection.update_one(
                    {"_id": lead["_id"]},
                    {"$set": {
                        "aria_state": "MEETING_BOOKED",
                        "status": "meeting_booked",
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }},
                )
                activities_collection.insert_one({
                    "lead_id": lead_id,
                    "user_id": "calendly",
                    "activity_type": "meeting_scheduled",
                    "subject": "Meeting booked via Calendly",
                    "body": f"{name} booked a call",
                    "outcome": None,
                    "duration_minutes": None,
                    "metadata": {"source": "calendly_webhook", "event": event},
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
                # Lazy import — `auto_send_lead_magnet` lives in server.py.
                try:
                    from server import auto_send_lead_magnet  # noqa: WPS433
                    await auto_send_lead_magnet(lead_id, "post_booking")
                except Exception as e:
                    print(f"Lead magnet auto-send (post_booking) failed: {e}")

    return {"received": True}


@router.post("/api/webhooks/meta-leads")
async def meta_leads_webhook(request_body: Dict[str, Any]):
    """Receive leads from Facebook / Instagram Lead Ads (Meta webhook)."""
    entries = request_body.get("entry", [])
    created = 0
    for entry in entries:
        changes = entry.get("changes", [])
        for change in changes:
            value = change.get("value", {})
            field_data = value.get("field_data", [])

            lead_data: Dict[str, Any] = {}
            for field in field_data:
                name = field.get("name", "").lower()
                val = field.get("values", [""])[0] if field.get("values") else ""
                if "email" in name:
                    lead_data["email"] = val
                elif "name" in name or "full_name" in name:
                    lead_data["first_name"] = val
                elif "phone" in name:
                    lead_data["phone"] = val
                elif "company" in name:
                    lead_data["company_name"] = val

            if lead_data.get("email"):
                existing = leads_collection.find_one({"email": lead_data["email"]}, {"_id": 1})
                if not existing:
                    full_name = lead_data.get("first_name", "Lead").split(" ", 1)
                    doc = {
                        "first_name": full_name[0],
                        "last_name": full_name[1] if len(full_name) > 1 else "",
                        "email": lead_data["email"],
                        "phone": lead_data.get("phone"),
                        "lead_type": "B2B" if lead_data.get("company_name") else "B2C",
                        "company_name": lead_data.get("company_name"),
                        "source_channel": "paid_ads",
                        "status": "new",
                        "icp_score": 0,
                        "icp_tier": "cold",
                        "tags": ["meta-lead-ad"],
                        "custom_fields": {},
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                        "created_by": "meta_webhook",
                        "assigned_to": None,
                        "notes": None,
                        "last_contacted_at": None,
                        "next_followup_at": None,
                    }
                    leads_collection.insert_one(doc)
                    created += 1

    return {"received": True, "leads_created": created}
