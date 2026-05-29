"""Conversations endpoint — thread list for /conversations page."""
from __future__ import annotations
import re
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field

from deps import db
from routes.tenants import get_active_tenant
from security.helpers import safe_query_param  # iter80 — S9.5
from services.outreach_dispatch import dispatch_outreach
from services.intel_service import compose_message

router = APIRouter(prefix="/api/conversations", tags=["conversations"])

leads_col = db["leads"]
conversations_col = db["aria_conversations"]


@router.get("/threads")
async def threads(
    sentiment: Optional[str] = Query(None),
    aria_active: Optional[bool] = Query(None),
    assigned_to: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = 100,
    tenant: dict = Depends(get_active_tenant),
):
    """List leads who have an active conversation, sorted by urgency.

    Urgent / negative sentiment leads float to the top.
    """
    tenant_id = tenant["id"]
    base = {"tenant_id": tenant_id}
    if sentiment:
        base["latest_sentiment"] = sentiment
    if aria_active is not None:
        base["aria_active"] = aria_active
    if assigned_to:
        base["assigned_to"] = assigned_to
    if search:
        # iter80 — S9.5: escape regex metacharacters & cap length (ReDoS guard)
        _safe = re.escape(safe_query_param(search, max_len=120))
        base["$or"] = [
            {"first_name": {"$regex": _safe, "$options": "i"}},
            {"last_name": {"$regex": _safe, "$options": "i"}},
            {"phone": {"$regex": _safe}},
            {"email": {"$regex": _safe, "$options": "i"}},
        ]

    rows = list(leads_col.find(base, {"_id": 0}).sort("updated_at", -1).limit(int(limit)))

    # Enrich with last message preview + aria_confidence
    out = []
    for r in rows:
        last_msg = conversations_col.find_one(
            {"tenant_id": tenant_id, "lead_id": r["id"]},
            {"_id": 0, "message": 1, "role": 1, "created_at": 1, "confidence": 1},
            sort=[("created_at", -1)],
        ) or {}
        out.append({
            "lead_id": r["id"],
            "first_name": r.get("first_name"),
            "last_name": r.get("last_name"),
            "phone": r.get("phone"),
            "email": r.get("email"),
            "company_name": r.get("company_name"),
            "status": r.get("status"),
            "icp_score": r.get("icp_score"),
            "icp_tier": r.get("icp_tier"),
            "aria_active": r.get("aria_active", True),
            "assigned_to": r.get("assigned_to"),
            "latest_sentiment": r.get("latest_sentiment"),
            "last_message": (last_msg.get("message") or "")[:140],
            "last_message_role": last_msg.get("role"),
            "last_message_at": last_msg.get("created_at") or r.get("updated_at"),
            "aria_confidence": last_msg.get("confidence") or r.get("aria_confidence"),
            "updated_at": r.get("updated_at"),
        })

    # Float urgent / negative to the top
    def _priority(t: dict) -> int:
        s = (t.get("latest_sentiment") or "").lower()
        if s == "urgent":
            return 0
        if s == "negative":
            return 1
        return 2
    out.sort(key=_priority)
    return {"threads": out, "count": len(out)}


# ─── iter121 — Conversation thread per lead (rolls up outbound + inbound + activities) ───
outbound_log_col = db["outbound_log"]
inbound_messages_col = db["inbound_messages"]
activities_col = db["activities"]
pt_leads_col = db["pt_leads"]


def _ob_entry(d):
    return {
        "id": f"ob_{d.get('provider_id') or d.get('created_at','')}",
        "ts": d.get("created_at"),
        "direction": "outbound",
        "channel": d.get("channel"),
        "actor": d.get("actor_user_id") or "aria",
        "title": d.get("subject") or f"Sent via {d.get('provider') or d.get('channel')}",
        "body": d.get("message_preview") or "",
        "meta": {
            "provider": d.get("provider"),
            "provider_id": d.get("provider_id"),
            "ai_powered": d.get("ai_powered"),
            "sent": d.get("sent"),
            "error": d.get("error"),
            "logged_only": d.get("logged_only"),
        },
    }


def _in_entry(d):
    return {
        "id": f"in_{d.get('external_id') or d.get('received_at','')}",
        "ts": d.get("received_at"),
        "direction": "inbound",
        "channel": d.get("channel"),
        "actor": d.get("from") or "prospect",
        "title": f"Reply via {d.get('channel')}",
        "body": d.get("text") or "",
        "meta": {"external_id": d.get("external_id")},
    }


def _act_entry(d):
    return {
        "id": f"act_{d.get('_id') or d.get('created_at','')}",
        "ts": d.get("created_at"),
        "direction": "system",
        "channel": d.get("channel"),
        "actor": d.get("actor_user_id") or "system",
        "title": (d.get("subject") or d.get("activity_type") or "event").replace("_", " ").title(),
        "body": d.get("body") or "",
        "meta": {"activity_type": d.get("activity_type")},
    }


@router.get("/lead/{lead_id}")
async def thread_by_lead(
    lead_id: str,
    tenant: dict = Depends(get_active_tenant),
):
    """Return a single chronological chat-style thread for a lead.
    Combines outbound_log + inbound_messages + activities (oldest at top)."""
    tenant_id = tenant["id"]

    outbound = [
        _ob_entry(d) for d in outbound_log_col.find(
            {"tenant_id": tenant_id, "lead_id": lead_id}, {"_id": 0},
        ).sort("created_at", -1).limit(200)
    ]
    inbound = [
        _in_entry(d) for d in inbound_messages_col.find(
            {"tenant_id": tenant_id, "lead_id": lead_id, "unmatched": {"$ne": True}}, {"_id": 0},
        ).sort("received_at", -1).limit(200)
    ]
    sysact = [
        _act_entry({**d, "_id": str(d["_id"])}) for d in activities_col.find(
            {"tenant_id": tenant_id, "lead_id": lead_id},
        ).sort("created_at", -1).limit(200)
    ]

    items = [t for t in (outbound + inbound + sysact) if t.get("ts")]
    items.sort(key=lambda t: t["ts"])

    lead = pt_leads_col.find_one(
        {"id": lead_id, "tenant_id": tenant_id},
        {"_id": 0, "first_name": 1, "last_name": 1, "email": 1, "company_name": 1, "stage": 1, "score": 1},
    ) or {}
    name = f"{lead.get('first_name','')} {lead.get('last_name','')}".strip() or lead.get("email") or "Prospect"

    return {
        "thread": items,
        "lead_snapshot": {
            "name": name,
            "first_name": lead.get("first_name"),
            "email": lead.get("email"),
            "company": lead.get("company_name"),
            "stage": lead.get("stage"),
            "score": lead.get("score"),
        },
        "counts": {
            "outbound": len(outbound),
            "inbound": len(inbound),
            "activity": len(sysact),
            "total": len(items),
        },
    }



# ─── POST /api/conversations/lead/{lead_id}/send ────────────────────────
# Reply box used by Lead 360's Conversations tab. Honours the Send-as-ARIA
# vs Send-as-me toggle so the conversation thread can attribute the
# message correctly. Routes through the same `dispatch_outreach`
# chokepoint that powers Intel-tab outreach + the touchpoint engine, so
# outbound_log + reply tracking stay in sync.
class SendReplyRequest(BaseModel):
    channel: str = Field(..., description="whatsapp | email | linkedin")
    body: str = Field(..., min_length=1, max_length=8000)
    subject: Optional[str] = Field(default=None, max_length=200)
    send_as: str = Field(default="aria", description="'aria' or 'me' — controls outbound_log attribution.")


@router.post("/lead/{lead_id}/send")
async def send_reply(
    lead_id: str,
    body: SendReplyRequest,
    tenant: dict = Depends(get_active_tenant),
):
    """Send a manual reply from the Lead 360 Conversations tab."""
    if body.channel not in {"whatsapp", "email", "linkedin"}:
        raise HTTPException(status_code=400, detail=f"Unsupported channel: {body.channel}")

    composed = {
        "channel": body.channel,
        "message": {"subject": body.subject, "body": body.body},
        "ai_powered": False,  # Founder typed it manually.
    }

    # actor_user_id = None  → attributed to ARIA on the timeline.
    # actor_user_id = "owner" → attributed to the founder.
    result = await dispatch_outreach(
        tenant_id=tenant["id"],
        lead_id=lead_id,
        channel=body.channel,
        composed=composed,
        actor_user_id=None if body.send_as == "aria" else "owner",
    )

    if not result.get("sent") and not result.get("logged_only"):
        raise HTTPException(status_code=502, detail=result.get("error") or "Send failed")

    return {
        "sent": bool(result.get("sent")),
        "logged_only": bool(result.get("logged_only")),
        "provider": result.get("provider"),
        "provider_id": result.get("provider_id"),
        "channel": body.channel,
        "send_as": body.send_as,
    }



# ─── POST /api/conversations/lead/{lead_id}/draft ───────────────────────
# "Draft with ARIA" button on the Conversations tab. Loads the lead's
# cached intel profile (if any) and runs the channel-adaptive composer
# so the founder can edit before sending. No outbound is dispatched —
# this only returns the draft text.
intel_profiles_col = db["intel_profiles"]


class DraftRequest(BaseModel):
    channel: str = Field(..., description="whatsapp | email | linkedin")
    user_steer: Optional[str] = Field(default=None, max_length=400, description="Optional founder note that nudges the draft.")


@router.post("/lead/{lead_id}/draft")
async def draft_reply(
    lead_id: str,
    body: DraftRequest,
    tenant: dict = Depends(get_active_tenant),
):
    """Generate a one-shot draft message for the reply box."""
    channel = (body.channel or "").strip().lower()
    if channel not in {"whatsapp", "email", "linkedin"}:
        raise HTTPException(status_code=400, detail=f"Unsupported channel: {channel}")

    tenant_id = tenant["id"]

    # Resolve lead from either store so Pietential prospects work too.
    # Legacy leads use ObjectId — try both string id field and _id.
    lead = pt_leads_col.find_one({"id": lead_id, "tenant_id": tenant_id}, {"_id": 0})
    if not lead:
        try:
            from bson import ObjectId
            if ObjectId.is_valid(lead_id):
                lead = leads_col.find_one(
                    {"_id": ObjectId(lead_id), "tenant_id": tenant_id},
                    {"_id": 0},
                )
        except Exception:
            lead = None
    if not lead:
        lead = leads_col.find_one({"id": lead_id, "tenant_id": tenant_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    name = (f"{lead.get('first_name', '')} {lead.get('last_name', '')}").strip() or lead.get("name") or lead.get("email") or "Prospect"
    lead_meta = {
        "name": name,
        "first_name": lead.get("first_name") or (name.split(" ", 1)[0] if name else "there"),
        "company": lead.get("company_name") or lead.get("company") or lead.get("domain"),
    }

    profile = intel_profiles_col.find_one({"tenant_id": tenant_id, "lead_id": lead_id}, {"_id": 0}) or {}

    composed = await compose_message(
        tenant_id=tenant_id,
        lead_id=lead_id,
        channel=channel,
        lead_meta=lead_meta,
        profile=profile,
        user_steer=body.user_steer,
    )

    # Normalise for the reply box: a single text blob (UI doesn't show a
    # separate subject input yet).
    msg = composed.get("message")
    if channel == "email" and isinstance(msg, dict):
        text = msg.get("body") or ""
        subject = msg.get("subject") or ""
    else:
        text = msg if isinstance(msg, str) else (msg.get("body") if isinstance(msg, dict) else "")
        subject = None

    # Refusal guard — when there's no intel profile + no ICP score, Claude
    # often returns a meta-response ("I can't draft this") rather than a
    # message. Detect that and fall back to a generic opener so the
    # founder gets a starter draft they can edit, instead of a refusal.
    refusal_markers = ("i cannot", "i can't", "i won't", "i will not", "should not be contacted", "no real intelligence", "without any relevant signals")
    low = (text or "").lower()
    if not profile and any(m in low for m in refusal_markers):
        first_name = lead_meta.get("first_name") or "there"
        company = lead_meta.get("company") or "your team"
        if channel == "email":
            text = (
                f"Hi {first_name},\n\nI came across {company} and wanted to reach out. "
                f"We help founders like you shorten the gap between captured leads and booked calls — "
                f"would a 15-minute chat this week be useful?\n\nBest,\nAria"
            )
            subject = subject or f"Quick idea for {company}"
        elif channel == "whatsapp":
            text = (
                f"Hi {first_name} — quick idea worth 15 mins for {company}. "
                f"Open to a chat this week?"
            )
        else:  # linkedin
            text = (
                f"Hi {first_name}, would love to connect. I work with founders on "
                f"closing the gap between captured leads and booked calls — happy to share what's worked."
            )

    return {
        "channel": channel,
        "draft": text,
        "subject": subject,
        "ai_powered": bool(composed.get("ai_powered")),
        "has_intel": bool(profile),
        "error": composed.get("error"),
    }
