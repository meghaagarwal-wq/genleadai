"""ARIA — Application intake (V3/V4 of UX flow standardisation, iter140).

Public, no-auth endpoint that lets potential clients submit the 4-section
qualification form on /apply. Admin endpoints (list/qualify/onboard) are
intentionally NOT included here yet — they belong to Batch 4 (V19).

Endpoints
─────────
  POST /api/applications                — public submit (no auth)
  GET  /api/applications/{id}/confirm   — public read of name+company
                                          for the thank-you page

Document shape (collection: `applications`)
───────────────────────────────────────────
    {
      id, full_name, work_email, role, country,
      company_name, company_url, industry, employees, revenue,
      current_setup, channels, current_volume, biggest_pain,
      goal, timeline, budget_band, ready_to_start,
      status, created_at, updated_at,
      source, ip_hash
    }

`status` starts as "new". Batch 4 will add reviewing/qualified/not_fit/onboarded.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import resend
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from deps import db

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

    # Fire-and-forget founder notification — never block the submit on it.
    try:
        _notify_founder(payload)
    except Exception:  # noqa: BLE001
        logger.exception("application notify failed (non-fatal)")

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


__all__ = ["router"]
