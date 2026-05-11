"""Lead capture — public endpoint + embeddable widget configuration.

Workflow:
  1. Tenant configures widget look + fields in Settings → Lead Capture.
  2. They copy the embed snippet (loads `/aria-widget.js`) onto their site.
  3. Visitors submit the form → `POST /api/leads/capture` (no auth, tenant_id in body).
  4. Endpoint creates a lead, fires CRM sync, auto-instantiates touchpoints,
     respects opt-in compliance.
"""
from __future__ import annotations
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, EmailStr

from deps import db, get_current_user
from routes.tenants import get_active_tenant

router = APIRouter(prefix="/api/lead-capture", tags=["lead-capture"])
public_router = APIRouter(prefix="/api/leads", tags=["lead-capture-public"])
widget_public_router = APIRouter(prefix="/api/lead-capture", tags=["lead-capture-public"])

tenants_col = db["tenants"]
leads_col = db["leads"]
widget_col = db["lead_capture_widgets"]


# ─── Tenant-side: widget configuration ──────────────────────────────────────
class WidgetConfig(BaseModel):
    enabled: bool = True
    mode: str = Field("popup", pattern="^(inline|popup|floating)$")
    title: str = "Get in touch"
    subtitle: str = "Tell us about your needs — Aria replies within minutes."
    button_label: str = "Send message"
    accent_color: str = "#7C35DC"
    fields: List[str] = Field(default_factory=lambda: ["first_name", "email", "phone", "message"])
    require_consent: bool = True
    consent_text: str = "I agree to be contacted via WhatsApp/email regarding my enquiry."
    allowed_origins: List[str] = Field(default_factory=list)  # CORS allowlist; empty = any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/config")
async def get_config(tenant: dict = Depends(get_active_tenant)):
    doc = widget_col.find_one({"tenant_id": tenant["id"]}, {"_id": 0})
    if not doc:
        doc = {**WidgetConfig().model_dump(), "tenant_id": tenant["id"]}
    backend_url = os.environ.get("BACKEND_URL", "").rstrip("/")
    return {
        "config": doc,
        "embed_snippet": _build_snippet(tenant["id"], backend_url),
        "widget_js_url": f"{backend_url}/aria-widget.js" if backend_url else "/aria-widget.js",
    }


@router.post("/config")
async def save_config(payload: WidgetConfig, tenant: dict = Depends(get_active_tenant), current_user: dict = Depends(get_current_user)):
    if tenant.get("_member_role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")
    doc = {**payload.model_dump(), "tenant_id": tenant["id"], "updated_at": _now()}
    widget_col.update_one({"tenant_id": tenant["id"]}, {"$set": doc}, upsert=True)
    return {"status": "ok", "config": doc}


def _build_snippet(tenant_id: str, backend_url: str) -> str:
    base = backend_url or "https://your-aria-backend.example.com"
    return (
        f'<!-- Aria Lead Capture Widget -->\n'
        f'<script>\n'
        f'  window.AriaWidget = window.AriaWidget || {{}};\n'
        f'  window.AriaWidget.tenantId = "{tenant_id}";\n'
        f'  window.AriaWidget.endpoint = "{base}";\n'
        f'</script>\n'
        f'<script src="{base}/aria-widget.js" async defer></script>'
    )


# ─── Public-side: lead capture ───────────────────────────────────────────────
PHONE_RE = re.compile(r"[^\d+]")


class CapturePayload(BaseModel):
    tenant_id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    message: Optional[str] = None
    consent: bool = False
    utm_source: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_medium: Optional[str] = None
    source_detail: Optional[str] = "website_widget"


@public_router.post("/capture")
async def capture_lead(payload: CapturePayload, request: Request):
    """Public endpoint — accepts a lead from the embeddable widget."""
    tenant = tenants_col.find_one({"id": payload.tenant_id}, {"_id": 0, "id": 1, "name": 1, "settings": 1})
    if not tenant:
        raise HTTPException(status_code=404, detail="Workspace not found")

    cfg = widget_col.find_one({"tenant_id": payload.tenant_id}, {"_id": 0}) or {}
    if cfg.get("enabled") is False:
        raise HTTPException(status_code=403, detail="Lead capture is disabled for this workspace")
    if cfg.get("require_consent", True) and not payload.consent:
        raise HTTPException(status_code=400, detail="Consent required")

    # Origin allowlist (best-effort; if origin missing we allow)
    origin = request.headers.get("origin") or ""
    allowed = cfg.get("allowed_origins") or []
    if allowed and origin and not any(origin.startswith(o.strip().rstrip("/")) for o in allowed):
        raise HTTPException(status_code=403, detail=f"Origin {origin} not allowed for this widget")

    # De-dupe by phone (last 10 digits) or email
    phone_clean = PHONE_RE.sub("", payload.phone or "")
    phone_tail = phone_clean[-10:] if phone_clean else None
    existing = None
    if phone_tail:
        existing = leads_col.find_one({"tenant_id": payload.tenant_id, "phone": {"$regex": f"{re.escape(phone_tail)}$"}}, {"_id": 0})
    if not existing and payload.email:
        existing = leads_col.find_one({"tenant_id": payload.tenant_id, "email": str(payload.email)}, {"_id": 0})

    if existing:
        # Update existing lead — append source_history, bump score by +5, do NOT reset touchpoints
        leads_col.update_one(
            {"id": existing["id"]},
            {
                "$push": {"source_history": {"source": "website_widget", "at": _now(), "utm": {
                    "source": payload.utm_source, "campaign": payload.utm_campaign, "medium": payload.utm_medium,
                }}},
                "$inc": {"icp_score": 5},
                "$set": {"updated_at": _now(), "last_activity_at": _now()},
            },
        )
        return {"status": "ok", "lead_id": existing["id"], "deduplicated": True}

    # Create new lead
    lead_id = str(uuid.uuid4())
    lead_doc = {
        "id": lead_id,
        "tenant_id": payload.tenant_id,
        "first_name": (payload.first_name or "").strip() or "Lead",
        "last_name": (payload.last_name or "").strip(),
        "email": str(payload.email) if payload.email else None,
        "phone": phone_clean or None,
        "company_name": (payload.company or "").strip(),
        "notes": (payload.message or "").strip(),
        "status": "new",
        "icp_score": 50,
        "icp_tier": "warm",
        "lead_type": "B2C",
        "source_channel": "website_widget",
        "source_type": "website_widget",
        "source_detail": payload.source_detail or "website_widget",
        "utm_source": payload.utm_source,
        "utm_campaign": payload.utm_campaign,
        "utm_medium": payload.utm_medium,
        "source_history": [{"source": "website_widget", "at": _now()}],
        "opted_in": bool(payload.consent),
        "opted_in_at": _now() if payload.consent else None,
        "opted_in_source": "website_form" if payload.consent else None,
        "needs_review": False,
        "stale": False,
        "high_intent": False,
        "created_at": _now(),
        "updated_at": _now(),
        "last_activity_at": _now(),
    }
    leads_col.insert_one(lead_doc)

    # Fire downstream side-effects (best-effort, swallowed errors so the
    # external caller always gets a 200 even if internals hiccup)
    try:
        from routes.touchpoint_engine import instantiate_for_lead
        instantiate_for_lead(payload.tenant_id, lead_doc)
    except Exception:
        pass
    try:
        from routes.crm_sync import fire_event as crm_fire_event
        crm_fire_event(payload.tenant_id, lead_doc, "lead.created", {"source": "website_widget"})
    except Exception:
        pass

    return {"status": "ok", "lead_id": lead_id, "deduplicated": False}



# ─── Public widget config (no auth — for embedded JS) ───────────────────────
@widget_public_router.get("/public-config")
async def public_config(tenant_id: str):
    """Public-readable subset of the widget config — never returns secrets."""
    cfg = widget_col.find_one({"tenant_id": tenant_id}, {"_id": 0, "tenant_id": 0, "updated_at": 0, "allowed_origins": 0})
    if not cfg:
        cfg = WidgetConfig().model_dump()
        cfg.pop("allowed_origins", None)
    return {"config": cfg}
