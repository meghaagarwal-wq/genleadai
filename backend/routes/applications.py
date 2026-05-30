"""ARIA — Application intake (V3/V4 of UX flow standardisation, iter140).

Public, no-auth endpoint that lets potential clients submit the 4-section
qualification form on /apply. Admin endpoints (V19 — iter141 Batch 4) added
for the /admin/applications review surface.

Public Endpoints
────────────────
  POST /api/applications                — public submit (no auth)
  GET  /api/applications/{id}/confirm   — public read of name+company
                                          for the thank-you page

Admin Endpoints (master_admin only)
───────────────────────────────────
  GET   /api/applications                            — list with status filter
  GET   /api/applications/{id}                       — full detail
  PATCH /api/applications/{id}/status                — mark new|reviewing|qualified|not_fit|onboarded
  POST  /api/applications/{id}/create-workspace      — provision tenant + invite

Document shape (collection: `applications`)
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import secrets
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import resend
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr, Field

from deps import db, get_current_user

logger = logging.getLogger("applications")
router = APIRouter(prefix="/api/applications", tags=["applications"])

_apps = db["applications"]
_apps.create_index("work_email")
_apps.create_index([("created_at", -1)])
_apps.create_index("status")

_ALLOWED_TIMELINES = {"now", "1-3_months", "3-6_months", "exploring"}
_ALLOWED_BUDGETS = {"under_10k", "10k_50k", "50k_500k", "500k_plus"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ───────────────────────────── models ─────────────────────────────

class ApplicationIn(BaseModel):
    # Section 1 — About you
    full_name: str = Field(..., min_length=2, max_length=120)
    work_email: EmailStr
    role: str = Field(..., min_length=2, max_length=120)
    country: str = Field(..., min_length=2, max_length=80)

    # Section 2 — Your business
    company_name: str = Field(..., min_length=1, max_length=160)
    company_url: Optional[str] = Field(default=None, max_length=300)
    industry: str = Field(..., min_length=2, max_length=120)
    employees: str = Field(..., max_length=40)
    revenue: Optional[str] = Field(default=None, max_length=40)

    # Section 3 — Your current setup
    current_setup: str = Field(..., min_length=4, max_length=2000)
    channels: List[str] = Field(default_factory=list, max_items=20)
    current_volume: str = Field(..., min_length=1, max_length=120)
    biggest_pain: str = Field(..., min_length=4, max_length=2000)

    # Section 4 — Fit & readiness
    goal: str = Field(..., min_length=4, max_length=2000)
    timeline: str = Field(..., max_length=40)
    budget_band: str = Field(..., max_length=40)
    ready_to_start: bool = True


class ApplicationCreated(BaseModel):
    id: str
    full_name: str
    company_name: str


class ApplicationConfirm(BaseModel):
    id: str
    full_name: str
    company_name: str
    created_at: str


# ─────────────────────── public endpoints ────────────────────────

@router.post("", response_model=ApplicationCreated, status_code=201)
async def submit_application(payload: ApplicationIn, request: Request):
    if payload.timeline not in _ALLOWED_TIMELINES:
        raise HTTPException(400, f"Invalid timeline. Expected one of {sorted(_ALLOWED_TIMELINES)}.")
    if payload.budget_band not in _ALLOWED_BUDGETS:
        raise HTTPException(400, f"Invalid budget band. Expected one of {sorted(_ALLOWED_BUDGETS)}.")
    if payload.company_url:
        if not re.match(r"^(https?://)?[\w\-.]+\.[a-zA-Z]{2,}", payload.company_url.strip()):
            raise HTTPException(400, "Company URL doesn't look like a valid web address.")

    # Light duplicate guard — same email within 60s shouldn't be allowed (form double-tap).
    cutoff = datetime.now(timezone.utc).timestamp() - 60
    recent = _apps.find_one(
        {"work_email": str(payload.work_email).lower(), "_ts_unix": {"$gte": cutoff}},
        {"_id": 0, "id": 1, "full_name": 1, "company_name": 1},
    )
    if recent:
        return ApplicationCreated(**recent)

    app_id = f"app_{uuid.uuid4().hex[:14]}"
    ip = (request.client.host if request.client else "") or ""
    ip_hash = hashlib.sha256(ip.encode("utf-8")).hexdigest()[:16] if ip else ""
    now = _now()

    doc = payload.model_dump()
    doc["work_email"] = str(doc["work_email"]).lower()
    doc.update({
        "id": app_id,
        "status": "new",
        "created_at": now,
        "updated_at": now,
        "_ts_unix": datetime.now(timezone.utc).timestamp(),
        "source": "public_form",
        "ip_hash": ip_hash,
    })
    _apps.insert_one(doc)

    # Fire-and-forget notifications — never block the submit on any of them.
    try:
        _notify_founder(payload)
    except Exception:  # noqa: BLE001
        logger.exception("application notify email failed (non-fatal)")
    try:
        _notify_slack(payload)
    except Exception:  # noqa: BLE001
        logger.exception("application notify slack failed (non-fatal)")
    try:
        _notify_whatsapp(payload)
    except Exception:  # noqa: BLE001
        logger.exception("application notify whatsapp failed (non-fatal)")

    return ApplicationCreated(id=app_id, full_name=payload.full_name, company_name=payload.company_name)


@router.get("/{app_id}/confirm", response_model=ApplicationConfirm)
async def confirm_application(app_id: str):
    """Public read used by /apply/thank-you to personalise the page."""
    doc = _apps.find_one(
        {"id": app_id},
        {"_id": 0, "id": 1, "full_name": 1, "company_name": 1, "created_at": 1},
    )
    if not doc:
        raise HTTPException(404, "Application not found")
    return ApplicationConfirm(**doc)


# ───────────────────── internal helpers ─────────────────────

def _notify_founder(payload: ApplicationIn) -> None:
    """Email the founder so they don't have to babysit the admin panel."""
    key = os.environ.get("RESEND_API_KEY")
    to = os.environ.get("APPLICATION_NOTIFY_TO") or os.environ.get("SENDER_EMAIL")
    sender = os.environ.get("SENDER_EMAIL") or "onboarding@resend.dev"
    if not key or not to:
        return
    resend.api_key = key
    body = (
        f"<h2>New ARIA application — {payload.company_name}</h2>"
        f"<p><strong>{payload.full_name}</strong> · {payload.role} · {payload.country}<br/>"
        f"{payload.work_email}</p>"
        f"<p><strong>Company:</strong> {payload.company_name} ({payload.industry})<br/>"
        f"<strong>Employees:</strong> {payload.employees}<br/>"
        f"<strong>Revenue:</strong> {payload.revenue or '—'}</p>"
        f"<p><strong>Volume:</strong> {payload.current_volume}<br/>"
        f"<strong>Channels:</strong> {', '.join(payload.channels) or '—'}</p>"
        f"<p><strong>Biggest pain:</strong> {payload.biggest_pain}</p>"
        f"<p><strong>Goal:</strong> {payload.goal}<br/>"
        f"<strong>Timeline:</strong> {payload.timeline} · "
        f"<strong>Budget:</strong> {payload.budget_band} · "
        f"<strong>Ready:</strong> {'Yes' if payload.ready_to_start else 'No'}</p>"
        f"<hr/><p>Review in <a href='https://app.genleadai.com/admin/applications'>Admin → Applications</a>.</p>"
    )
    try:
        resend.Emails.send({
            "from": f"ARIA <{sender}>",
            "to": [to],
            "subject": f"[ARIA Application] {payload.company_name} — {payload.full_name}",
            "html": body,
        })
    except Exception as e:  # noqa: BLE001
        # Don't crash the submit. Sandbox/missing-domain is expected on preview.
        logger.warning("application notify resend failed: %s", str(e)[:200])


def _notify_slack(payload: ApplicationIn) -> None:
    """iter141 — fire a Slack block-kit message if SLACK_WEBHOOK_URL set.
    Silent no-op when unconfigured. Best-effort; never raises.

    URL: any incoming-webhook URL from Slack apps (Apps → Manage → Incoming Webhooks).
    """
    url = os.environ.get("SLACK_WEBHOOK_URL")
    if not url:
        return
    try:
        message = {
            "blocks": [
                {"type": "header", "text": {"type": "plain_text",
                    "text": f"🚀 New ARIA application — {payload.company_name}"}},
                {"type": "section", "fields": [
                    {"type": "mrkdwn", "text": f"*Name*\n{payload.full_name}"},
                    {"type": "mrkdwn", "text": f"*Email*\n{payload.work_email}"},
                    {"type": "mrkdwn", "text": f"*Role*\n{payload.role}"},
                    {"type": "mrkdwn", "text": f"*Country*\n{payload.country}"},
                    {"type": "mrkdwn", "text": f"*Industry*\n{payload.industry}"},
                    {"type": "mrkdwn", "text": f"*Team*\n{payload.employees}"},
                    {"type": "mrkdwn", "text": f"*Timeline*\n{payload.timeline}"},
                    {"type": "mrkdwn", "text": f"*Budget*\n{payload.budget_band}"},
                ]},
                {"type": "section", "text": {"type": "mrkdwn",
                    "text": f"*Biggest pain*\n>{payload.biggest_pain[:300]}"}},
                {"type": "section", "text": {"type": "mrkdwn",
                    "text": f"*Goal*\n>{payload.goal[:300]}"}},
                {"type": "actions", "elements": [
                    {"type": "button", "text": {"type": "plain_text", "text": "Review in Admin"},
                     "url": "https://app.genleadai.com/admin/applications", "style": "primary"},
                ]},
            ]
        }
        data = json.dumps(message).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5).read()
    except Exception as e:  # noqa: BLE001
        logger.warning("application notify slack failed: %s", str(e)[:200])


def _notify_whatsapp(payload: ApplicationIn) -> None:
    """iter141 — fire a 360dialog WhatsApp message if both
    WHATSAPP_360_API_KEY and APPLICATION_NOTIFY_WHATSAPP (E.164 phone) are set.
    Silent no-op when unconfigured. Never raises.
    """
    key = os.environ.get("WHATSAPP_360_API_KEY")
    to = os.environ.get("APPLICATION_NOTIFY_WHATSAPP")  # E.164 e.g. +919876543210
    if not key or not to:
        return
    try:
        body = (
            f"🚀 New ARIA application\n\n"
            f"{payload.full_name} · {payload.company_name}\n"
            f"{payload.work_email}\n"
            f"Timeline: {payload.timeline} · Budget: {payload.budget_band}\n\n"
            f"Pain: {payload.biggest_pain[:160]}\n\n"
            f"Review: https://app.genleadai.com/admin/applications"
        )
        data = json.dumps({
            "to": to.lstrip("+"),
            "type": "text",
            "text": {"body": body[:1024]},
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://waba.360dialog.io/v1/messages",
            data=data,
            headers={"D360-API-KEY": key, "Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5).read()
    except Exception as e:  # noqa: BLE001
        logger.warning("application notify whatsapp failed: %s", str(e)[:200])


# ─────────────────── admin endpoints (V19 / iter141) ───────────────────

_ALLOWED_STATUSES = {"new", "reviewing", "qualified", "not_fit", "onboarded"}


class AdminApplicationOut(BaseModel):
    id: str
    full_name: str
    work_email: str
    role: str
    country: str
    company_name: str
    industry: str
    timeline: str
    budget_band: str
    status: str
    created_at: str
    updated_at: Optional[str] = None


class AdminApplicationListOut(BaseModel):
    items: List[AdminApplicationOut]
    counts: dict  # {new: 5, reviewing: 1, ...}
    total: int


class StatusPatch(BaseModel):
    status: str
    note: Optional[str] = Field(default=None, max_length=1000)


class CreateWorkspaceIn(BaseModel):
    workspace_name: str = Field(..., min_length=2, max_length=120)
    mode: str = Field(..., pattern=r"^(b2b|b2c|hybrid)$")
    invite_email: bool = True


class CreateWorkspaceOut(BaseModel):
    workspace_id: str
    workspace_name: str
    mode: str
    invite_token: str
    invite_url: str
    invited_email_sent: bool


def _require_master_admin(current_user: dict = Depends(get_current_user)):
    """Use the canonical auth dependency from deps.get_current_user. Raises
    401 (no token), 403 (wrong role)."""
    if current_user.get("role") != "master_admin":
        raise HTTPException(status_code=403, detail="master_admin role required")
    return current_user


@router.get("", response_model=AdminApplicationListOut)
async def list_applications(
    status: Optional[str] = Query(default=None, description="Filter by status"),
    limit: int = Query(default=100, ge=1, le=500),
    current_user: dict = Depends(_require_master_admin),
):
    query: dict = {}
    if status:
        if status not in _ALLOWED_STATUSES and status != "all":
            raise HTTPException(400, f"Invalid status. Expected one of {sorted(_ALLOWED_STATUSES)} or 'all'.")
        if status != "all":
            query["status"] = status

    cursor = _apps.find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
    items = []
    for d in cursor:
        items.append(AdminApplicationOut(
            id=d["id"],
            full_name=d.get("full_name", ""),
            work_email=d.get("work_email", ""),
            role=d.get("role", ""),
            country=d.get("country", ""),
            company_name=d.get("company_name", ""),
            industry=d.get("industry", ""),
            timeline=d.get("timeline", ""),
            budget_band=d.get("budget_band", ""),
            status=d.get("status", "new"),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at"),
        ))

    pipeline = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
    counts = {s: 0 for s in _ALLOWED_STATUSES}
    for row in _apps.aggregate(pipeline):
        s = row.get("_id") or "new"
        counts[s] = row.get("count", 0)
    counts["all"] = sum(counts.values())

    return AdminApplicationListOut(items=items, counts=counts, total=counts["all"])


@router.get("/{app_id}")
async def get_application(app_id: str, current_user: dict = Depends(_require_master_admin)):
    doc = _apps.find_one({"id": app_id}, {"_id": 0, "_ts_unix": 0, "ip_hash": 0})
    if not doc:
        raise HTTPException(404, "Application not found")
    return doc


@router.patch("/{app_id}/status")
async def update_application_status(app_id: str, payload: StatusPatch, current_user: dict = Depends(_require_master_admin)):
    if payload.status not in _ALLOWED_STATUSES:
        raise HTTPException(400, f"Invalid status. Expected one of {sorted(_ALLOWED_STATUSES)}.")
    res = _apps.update_one(
        {"id": app_id},
        {"$set": {
            "status": payload.status,
            "updated_at": _now(),
            "last_reviewed_by": current_user.get("email"),
            "last_review_note": payload.note,
        }},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Application not found")
    doc = _apps.find_one({"id": app_id}, {"_id": 0, "_ts_unix": 0, "ip_hash": 0})
    return doc


@router.post("/{app_id}/create-workspace", response_model=CreateWorkspaceOut)
async def create_workspace_from_application(app_id: str, payload: CreateWorkspaceIn, current_user: dict = Depends(_require_master_admin)):
    app_doc = _apps.find_one({"id": app_id}, {"_id": 0})
    if not app_doc:
        raise HTTPException(404, "Application not found")

    workspace_id = f"ws_{uuid.uuid4().hex[:14]}"
    invite_token = secrets.token_urlsafe(28)
    now = _now()

    tenants_col = db["tenants"]
    tenants_col.insert_one({
        "id": workspace_id,
        "name": payload.workspace_name,
        "mode": payload.mode,
        "owner_email": app_doc["work_email"],
        "is_active": True,
        "created_at": now,
        "updated_at": now,
        "created_from_application": app_id,
        "created_by_admin": current_user.get("email"),
    })

    invites_col = db["workspace_invites"]
    invites_col.insert_one({
        "token": invite_token,
        "workspace_id": workspace_id,
        "workspace_name": payload.workspace_name,
        "mode": payload.mode,
        "email": app_doc["work_email"],
        "full_name": app_doc.get("full_name"),
        "application_id": app_id,
        "created_at": now,
        "created_by": current_user.get("email"),
        "accepted_at": None,
        "expires_at": (datetime.now(timezone.utc).timestamp() + 7 * 86400),
    })

    invite_url = f"https://app.genleadai.com/invite/{invite_token}"

    _apps.update_one(
        {"id": app_id},
        {"$set": {
            "status": "onboarded",
            "updated_at": now,
            "onboarded_workspace_id": workspace_id,
            "onboarded_by_admin": current_user.get("email"),
        }},
    )

    invited_email_sent = False
    if payload.invite_email:
        invited_email_sent = _send_invite_email(
            to_email=app_doc["work_email"],
            full_name=app_doc.get("full_name", ""),
            invite_url=invite_url,
            workspace_name=payload.workspace_name,
        )

    return CreateWorkspaceOut(
        workspace_id=workspace_id,
        workspace_name=payload.workspace_name,
        mode=payload.mode,
        invite_token=invite_token,
        invite_url=invite_url,
        invited_email_sent=invited_email_sent,
    )


def _send_invite_email(to_email: str, full_name: str, invite_url: str, workspace_name: str) -> bool:
    key = os.environ.get("RESEND_API_KEY")
    sender = os.environ.get("SENDER_EMAIL") or "onboarding@resend.dev"
    if not key:
        return False
    resend.api_key = key
    name_part = full_name.split()[0] if full_name else "there"
    body = (
        f"<p>Hi {name_part},</p>"
        f"<p>You've been invited to ARIA by GenLeadAI. Your workspace "
        f"<strong>{workspace_name}</strong> is ready.</p>"
        f"<p><a href='{invite_url}' style='display:inline-block;background:#7C35DC;color:#fff;"
        f"padding:12px 24px;border-radius:24px;text-decoration:none;font-weight:bold'>"
        f"Accept your invitation</a></p>"
        f"<p>Or paste this link in your browser:<br/><code>{invite_url}</code></p>"
        f"<p>This link expires in 7 days.</p>"
    )
    try:
        resend.Emails.send({
            "from": f"ARIA by GenLeadAI <{sender}>",
            "to": [to_email],
            "subject": "You've been invited to ARIA",
            "html": body,
        })
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning("invite email failed for %s: %s", to_email, str(e)[:200])
        return False


__all__ = ["router"]
