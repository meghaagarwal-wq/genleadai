"""Iter79 — S8: Master Admin Deployments tab.

Treats every tenant as an Aria deployment with status SETUP / LIVE / PAUSED.
Surfaces a per-deployment dashboard for the agency owner + a 4-step
'simplified onboarding' creator. Also exposes a small read-only endpoint
the sidebar uses to render the per-workspace ARIA status indicator.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from deps import db, get_current_user, leads_collection, activities_collection

router = APIRouter(prefix="/api/admin/deployments", tags=["admin-deployments"])


# ─── Helpers ────────────────────────────────────────────────────────────────
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_master(current_user: dict):
    if current_user.get("role") not in ("master_admin", "owner"):
        raise HTTPException(status_code=403, detail="forbidden: master admin only")


def _mask(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    v = str(value)
    if len(v) <= 8:
        return "•" * len(v)
    return f"{v[:4]}{'•' * 6}{v[-4:]}"


def _deployment_status(tenant: dict) -> str:
    """SETUP / LIVE / PAUSED.

    PAUSED: explicit operator action stored in tenant.settings.deployment_paused.
    LIVE:   at least one ICP, at least one configured channel (WhatsApp or Email),
            and at least one touchpoint in the workspace touchpoint map.
    SETUP:  anything else.
    """
    settings = tenant.get("settings") or {}
    if settings.get("deployment_paused"):
        return "PAUSED"

    tid = tenant.get("id")
    if not tid:
        return "SETUP"

    integrations = tenant.get("integrations") or {}
    has_whatsapp = bool((integrations.get("whatsapp") or {}).get("connected") or (integrations.get("whatsapp") or {}).get("phone_number_id"))
    has_email = bool((integrations.get("resend") or {}).get("api_key") or (integrations.get("email") or {}).get("from_address"))
    has_channel = has_whatsapp or has_email
    has_icp = db["icps"].count_documents({"tenant_id": tid}) > 0
    journey = db["workspace_touchpoint_maps"].find_one({"tenant_id": tid}, {"touchpoints": 1, "_id": 0}) or {}
    has_touchpoints = len(journey.get("touchpoints") or []) > 0

    if has_channel and has_icp and has_touchpoints:
        return "LIVE"
    return "SETUP"


def _deployment_card(tenant: dict) -> dict:
    """Render the Master Admin → Deployments grid card payload."""
    tid = tenant.get("id")
    integrations = tenant.get("integrations") or {}
    settings = tenant.get("settings") or {}
    status = _deployment_status(tenant)

    # Activity rollup — last 7 days
    week_ago = datetime.now(timezone.utc).timestamp() - 7 * 24 * 3600
    week_ago_iso = datetime.fromtimestamp(week_ago, tz=timezone.utc).isoformat()
    leads_count = leads_collection.count_documents({"tenant_id": tid}) if tid else 0
    touchpoints_week = activities_collection.count_documents({
        "tenant_id": tid,
        "type": {"$in": ["touchpoint_sent", "message_sent", "outbound_sent"]},
        "created_at": {"$gte": week_ago_iso},
    }) if tid else 0
    last_activity = (activities_collection
                     .find({"tenant_id": tid}, {"_id": 0, "created_at": 1})
                     .sort("created_at", -1).limit(1)
                     ) if tid else []
    last_activity_at = next(iter(last_activity), {}).get("created_at")

    def _flag(k):
        b = integrations.get(k) or {}
        if isinstance(b, dict):
            return bool(b.get("connected") or b.get("api_key") or b.get("phone_number_id") or b.get("from_address"))
        return bool(b)

    return {
        "tenant_id": tid,
        "workspace_name": tenant.get("name") or tid,
        "founder_name": tenant.get("founder_name") or tenant.get("owner_name"),
        "industry": tenant.get("industry"),
        "status": status,
        "channels": {
            "whatsapp": _flag("whatsapp"),
            "email":    _flag("resend") or _flag("email"),
            "crm":      _flag("zoho") or _flag("hubspot") or _flag("salesforce") or _flag("crm"),
        },
        "leads_total": leads_count,
        "touchpoints_this_week": touchpoints_week,
        "last_activity_at": last_activity_at,
        "paused_at": settings.get("deployment_paused_at"),
        "launched_at": settings.get("deployment_launched_at"),
        "created_at": tenant.get("created_at"),
    }


# ─── Endpoints ──────────────────────────────────────────────────────────────
@router.get("")
async def list_deployments(current_user: dict = Depends(get_current_user)):
    _require_master(current_user)
    tenants = list(db["tenants"].find({}, {"_id": 0}).sort("created_at", -1))
    cards = [_deployment_card(t) for t in tenants]
    rollup = {
        "total": len(cards),
        "live": sum(1 for c in cards if c["status"] == "LIVE"),
        "setup": sum(1 for c in cards if c["status"] == "SETUP"),
        "paused": sum(1 for c in cards if c["status"] == "PAUSED"),
    }
    return {"rollup": rollup, "deployments": cards}


@router.get("/{tenant_id}")
async def get_deployment(tenant_id: str, current_user: dict = Depends(get_current_user)):
    _require_master(current_user)
    tenant = db["tenants"].find_one({"id": tenant_id}, {"_id": 0})
    if not tenant:
        raise HTTPException(404, "tenant_not_found")
    card = _deployment_card(tenant)

    integrations = tenant.get("integrations") or {}
    api_keys_view = {
        "whatsapp": {
            "configured": bool((integrations.get("whatsapp") or {}).get("phone_number_id")),
            "provider":   (integrations.get("whatsapp") or {}).get("provider"),
            "phone_number_id": _mask((integrations.get("whatsapp") or {}).get("phone_number_id")),
            "display_phone":  (integrations.get("whatsapp") or {}).get("display_phone"),
        },
        "email": {
            "configured": bool((integrations.get("resend") or {}).get("api_key") or (integrations.get("email") or {}).get("from_address")),
            "from_address": (integrations.get("email") or {}).get("from_address"),
            "from_name":    (integrations.get("email") or {}).get("from_name"),
            "api_key":      _mask((integrations.get("resend") or {}).get("api_key")),
        },
    }
    return {"deployment": card, "api_keys": api_keys_view}


class DeploymentToggle(BaseModel):
    pause: bool


@router.post("/{tenant_id}/toggle")
async def toggle_deployment(
    tenant_id: str,
    payload: DeploymentToggle,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    _require_master(current_user)
    if not db["tenants"].find_one({"id": tenant_id}, {"_id": 0, "id": 1}):
        raise HTTPException(404, "tenant_not_found")

    if payload.pause:
        update = {"$set": {
            "settings.deployment_paused": True,
            "settings.deployment_paused_at": _now_iso(),
            "settings.deployment_paused_by": current_user.get("email"),
        }}
        action = "deployment.pause"
    else:
        update = {"$set": {
            "settings.deployment_paused": False,
            "settings.deployment_launched_at": _now_iso(),
            "settings.deployment_launched_by": current_user.get("email"),
        }, "$unset": {"settings.deployment_paused_at": ""}}
        action = "deployment.resume"

    db["tenants"].update_one({"id": tenant_id}, update)
    try:
        from routes.audit_log import audit_write
        audit_write(
            tenant_id=tenant_id,
            user=current_user,
            action=action,
            resource_type="deployment",
            resource_id=tenant_id,
            request=request,
        )
    except Exception:
        pass
    return {"tenant_id": tenant_id, "paused": payload.pause}


# ─── 4-step simplified onboarding (Master Admin → Create deployment) ────────
class OnboardingStep1(BaseModel):
    business_name: str = Field(min_length=2, max_length=120)
    founder_name: str = Field(min_length=2, max_length=120)
    founder_email: EmailStr
    industry: Optional[str] = None
    primary_market: Optional[str] = None
    primary_language: Optional[str] = "en"


class OnboardingStep2(BaseModel):
    whatsapp_provider: Optional[str] = None   # 'meta_cloud_api' | '360dialog' | None
    whatsapp_access_token: Optional[str] = None
    whatsapp_phone_number_id: Optional[str] = None
    whatsapp_display_phone: Optional[str] = None
    email_from_name: Optional[str] = None
    email_from_address: Optional[str] = None
    resend_api_key: Optional[str] = None
    crm_webhook_url: Optional[str] = None
    calendly_link: Optional[str] = None


class OnboardingStep3(BaseModel):
    icp_industry: Optional[str] = None
    icp_target_title: Optional[str] = None
    icp_pain_point: Optional[str] = None
    preferred_channel: str = "email"           # 'whatsapp' | 'email' | 'linkedin'


class OnboardingLaunchPayload(BaseModel):
    step1: OnboardingStep1
    step2: OnboardingStep2
    step3: OnboardingStep3


@router.post("/onboard")
async def onboard_new_deployment(
    payload: OnboardingLaunchPayload,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Create a fresh tenant + minimal ICP + default touchpoint map + integrations.
    Sets `deployment_paused=False` so the new workspace is LIVE immediately
    if at least one channel + ICP + touchpoint exists.
    """
    _require_master(current_user)
    s1, s2, s3 = payload.step1, payload.step2, payload.step3
    now = _now_iso()

    # 1. Tenant
    tid = "ten_" + secrets.token_hex(6)
    integrations: dict = {}
    if s2.whatsapp_phone_number_id and s2.whatsapp_access_token:
        integrations["whatsapp"] = {
            "provider": s2.whatsapp_provider or "meta_cloud_api",
            "phone_number_id": s2.whatsapp_phone_number_id,
            "access_token": s2.whatsapp_access_token,
            "display_phone": s2.whatsapp_display_phone,
            "connected": True,
            "connected_at": now,
        }
    if s2.email_from_address:
        integrations["email"] = {
            "from_name": s2.email_from_name,
            "from_address": s2.email_from_address,
        }
    if s2.resend_api_key:
        integrations["resend"] = {"api_key": s2.resend_api_key, "connected_at": now}
    if s2.crm_webhook_url:
        integrations["crm"] = {"webhook_url": s2.crm_webhook_url}
    if s2.calendly_link:
        integrations["calendly"] = {"link": s2.calendly_link}

    tenant_doc = {
        "id": tid,
        "name": s1.business_name,
        "founder_name": s1.founder_name,
        "founder_email": s1.founder_email,
        "industry": s1.industry,
        "primary_market": s1.primary_market,
        "language": s1.primary_language or "en",
        "plan": "dwy",
        "integrations": integrations,
        "settings": {
            "deployment_paused": False,
            "deployment_launched_at": now,
            "deployment_launched_by": current_user.get("email"),
            "sales_channels": {"selected_channels": [s3.preferred_channel]},
            "onboarded_via": "master_admin_wizard",
        },
        "created_at": now,
        "created_by": current_user.get("email"),
    }
    db["tenants"].insert_one(tenant_doc)

    # 2. Owner-level membership for the founder (placeholder user — they sign up
    #    later via password-reset link). We just create the tenant_users row so
    #    the founder shows up on the team list.
    db["tenant_users"].insert_one({
        "tenant_id": tid,
        "user_email": s1.founder_email,
        "role": "owner",
        "invited_by": current_user.get("email"),
        "invited_at": now,
        "status": "invited",
    })

    # 3. Default ICP (only if step3 had at least one field)
    icp_id = None
    if any([s3.icp_industry, s3.icp_target_title, s3.icp_pain_point]):
        icp_id = "icp_" + secrets.token_hex(6)
        db["icps"].insert_one({
            "id": icp_id,
            "tenant_id": tid,
            "label": s3.icp_target_title or f"{s1.business_name} buyer",
            "industry": s3.icp_industry,
            "title_targets": [s3.icp_target_title] if s3.icp_target_title else [],
            "pain_point": s3.icp_pain_point,
            "tone": "professional",
            "created_at": now,
            "created_by": current_user.get("email"),
        })

    # 4. Minimal touchpoint journey (3-step default)
    default_tps = [
        {"index": 0, "day": 0, "hour": 10, "channel": s3.preferred_channel, "message_type": "intro",     "aria_role": "autonomous", "message_template": f"Hi {{first_name}}, I help {s1.industry or 'founders'} like you — open to a 15 min chat?"},
        {"index": 1, "day": 3, "hour": 10, "channel": s3.preferred_channel, "message_type": "follow_up", "aria_role": "autonomous", "message_template": "Quick nudge — still keen on a 15 min walkthrough this week?"},
        {"index": 2, "day": 7, "hour": 10, "channel": s3.preferred_channel, "message_type": "follow_up", "aria_role": "autonomous", "message_template": "Last check — shall I close the loop or want to grab a slot?"},
    ]
    db["workspace_touchpoint_maps"].insert_one({
        "tenant_id": tid,
        "touchpoints": default_tps,
        "created_at": now,
        "created_by": current_user.get("email"),
    })

    # 5. Audit
    try:
        from routes.audit_log import audit_write
        audit_write(
            tenant_id=tid,
            user=current_user,
            action="deployment.create",
            resource_type="deployment",
            resource_id=tid,
            metadata={"business_name": s1.business_name, "icp_id": icp_id},
            request=request,
        )
    except Exception:
        pass

    # 6. Compute final status (should be LIVE if channel + ICP + touchpoint all present).
    fresh = db["tenants"].find_one({"id": tid}, {"_id": 0})
    return {
        "tenant_id": tid,
        "status": _deployment_status(fresh),
        "deployment": _deployment_card(fresh),
        "founder_email": s1.founder_email,
    }


# ─── Sidebar ARIA status (any logged-in user, scoped to their own workspace) ─
@router.get("/_/sidebar-status")
async def sidebar_status(current_user: dict = Depends(get_current_user)):
    """Cheap endpoint that the persistent sidebar indicator polls."""
    tid = current_user.get("tenant_id") or current_user.get("active_tenant_id")
    if not tid:
        return {"status": "SETUP", "leads_today": 0, "touchpoints_today": 0, "last_activity_at": None}
    tenant = db["tenants"].find_one({"id": tid}, {"_id": 0}) or {}
    status = _deployment_status(tenant)
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    leads_today = leads_collection.count_documents({"tenant_id": tid, "created_at": {"$gte": today}})
    touchpoints_today = activities_collection.count_documents({
        "tenant_id": tid,
        "type": {"$in": ["touchpoint_sent", "message_sent", "outbound_sent"]},
        "created_at": {"$gte": today},
    })
    last_activity = (activities_collection
                     .find({"tenant_id": tid}, {"_id": 0, "created_at": 1})
                     .sort("created_at", -1).limit(1))
    return {
        "status": status,
        "leads_today": leads_today,
        "touchpoints_today": touchpoints_today,
        "last_activity_at": next(iter(last_activity), {}).get("created_at"),
    }
