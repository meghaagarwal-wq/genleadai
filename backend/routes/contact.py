"""Public contact form — captures inbound "Request ARIA Setup" leads from the
signup page and the public landing page.

Endpoint:
    POST /api/contact/request  {name, email, company, website, message, page}

Idempotent + rate-limited (3 per email per 15 min). No auth required.
Stores into `contact_requests` Mongo collection so master-admin can review
inbound leads alongside beta feedback.

The endpoint also forwards a copy of the message to Resend (best-effort,
swallowed on failure) so the founder gets an inbox ping in real time.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
import resend

from deps import db

router = APIRouter(prefix="/api/contact", tags=["contact"])

requests_col = db["contact_requests"]
rl_col = db["contact_rate_limit"]

# Reasonable cap so a bored visitor can't flood the inbox.
REQUESTS_PER_15MIN = 3
APP_NAME = "Aria by GenLeadAI"


class ContactPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    email: EmailStr
    company: Optional[str] = Field(None, max_length=200)
    website: Optional[str] = Field(None, max_length=400)
    message: str = Field(..., min_length=3, max_length=4000)
    page: Optional[str] = Field(None, max_length=80)


def _now() -> datetime:
    return datetime.utcnow()


def _rate_limited(email: str) -> bool:
    cutoff = _now() - timedelta(minutes=15)
    return rl_col.count_documents({"email": email.lower(), "created_at": {"$gte": cutoff}}) >= REQUESTS_PER_15MIN


def _record_request(email: str) -> None:
    rl_col.insert_one({"email": email.lower(), "created_at": _now()})


def _notify_owner(payload: ContactPayload) -> None:
    """Send the founder an inbox ping via the safe wrapper. Never raises."""
    try:
        from email_delivery import send_email_safe
    except Exception:
        return
    owner = os.getenv("CONTACT_FORWARD_EMAIL") or os.getenv("MASTER_ADMIN_EMAIL")
    if not owner:
        return
    safe_msg = re.sub(r"[<>]", "", payload.message)
    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 560px; margin: 0 auto; padding: 24px;">
        <div style="display: inline-block; padding: 8px 14px; background: linear-gradient(135deg, #C044E0 0%, #7C35DC 50%, #5B28D4 100%); color: white; border-radius: 8px; font-weight: 800; letter-spacing: 0.12em; font-size: 11px;">NEW CONTACT REQUEST</div>
        <h2 style="color: #1A0A2E; font-weight: 800; margin: 14px 0 6px 0;">{payload.name}</h2>
        <p style="color: #5A4A7A; margin: 0 0 14px 0;"><a href="mailto:{payload.email}" style="color:#7C35DC;">{payload.email}</a>{' &middot; ' + payload.company if payload.company else ''}{' &middot; ' + payload.website if payload.website else ''}</p>
        <div style="background: #FAF7FF; border-left: 3px solid #7C35DC; padding: 12px 14px; border-radius: 4px; color: #1A0A2E; white-space: pre-wrap;">{safe_msg}</div>
        <p style="color: #9B8AB0; font-size: 11px; margin-top: 18px;">Page: {payload.page or 'unknown'} &middot; {APP_NAME}</p>
    </div>
    """
    send_email_safe(
        to_email=owner,
        subject=f"[Aria contact] {payload.name} from {payload.company or 'a new prospect'}",
        html=html,
        reply_to=payload.email,
        purpose="contact_request",
    )


@router.post("/request")
def contact_request(payload: ContactPayload, request: Request):
    email = payload.email.lower().strip()
    if _rate_limited(email):
        # Still return ok to avoid leaking that we're rate-limiting.
        return {"ok": True}

    doc = {
        "id": __import__('uuid').uuid4().hex,
        "name": payload.name.strip(),
        "email": email,
        "company": (payload.company or "").strip() or None,
        "website": (payload.website or "").strip() or None,
        "message": payload.message.strip(),
        "page": (payload.page or "").strip() or "signup",
        "ua": request.headers.get("user-agent"),
        "ip": request.client.host if request.client else None,
        "created_at": _now(),
        "status": "new",
    }
    requests_col.insert_one(doc)
    _record_request(email)
    _notify_owner(payload)
    return {"ok": True}


# ──────────────────────────────────────────────────────────────────────────
#  Admin: list / update inbound contact requests
# ──────────────────────────────────────────────────────────────────────────
from fastapi import Depends
from pydantic import BaseModel as _BaseModel
from deps import get_current_user
from routes.audit_log import _require_master_admin

admin_router = APIRouter(prefix="/api/admin/contact-requests", tags=["admin-contact"])

VALID_STATUSES = ["new", "contacted", "qualified", "closed", "spam"]


class StatusUpdate(_BaseModel):
    status: str
    note: Optional[str] = None


@admin_router.get("")
def list_contact_requests(
    status: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
    current_user: dict = Depends(get_current_user),
):
    """Master-admin inbound CRM — paginated, filter by status."""
    _require_master_admin(current_user)
    q = {}
    if status and status in VALID_STATUSES:
        q["status"] = status
    cursor = requests_col.find(q, {"_id": 0}).sort("created_at", -1).skip(max(0, skip)).limit(max(1, min(200, limit)))
    items = list(cursor)
    # Backfill missing id for legacy docs
    for it in items:
        if not it.get("id"):
            it["id"] = it.get("email", "") + "-" + (it.get("created_at").isoformat() if it.get("created_at") else "")
        if isinstance(it.get("created_at"), datetime):
            it["created_at"] = it["created_at"].isoformat()
    total = requests_col.count_documents(q)
    # Counts per status for tab badges
    pipe = list(requests_col.aggregate([{"$group": {"_id": "$status", "n": {"$sum": 1}}}]))
    counts = {p["_id"] or "new": p["n"] for p in pipe}
    counts["all"] = requests_col.count_documents({})
    return {"items": items, "total": total, "counts": counts}


@admin_router.patch("/{request_id}/status")
def update_status(request_id: str, payload: StatusUpdate, current_user: dict = Depends(get_current_user)):
    _require_master_admin(current_user)
    if payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {VALID_STATUSES}")
    update = {"status": payload.status, "status_updated_at": _now()}
    if payload.note is not None:
        update["admin_note"] = payload.note.strip()[:2000]
    res = requests_col.update_one({"id": request_id}, {"$set": update})
    if res.matched_count == 0:
        # Fallback for legacy docs that don't have an id field
        res = requests_col.update_one({"email": request_id}, {"$set": update}, upsert=False)
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Contact request not found")
    return {"ok": True}
