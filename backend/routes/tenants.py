"""Multi-tenant foundation for Aria SaaS.

Adds tenants, memberships, and per-tenant onboarding config.
A tenant is a customer workspace — has its own isolated data.
A user can belong to multiple tenants (membership table).
The "active tenant" for a request is resolved from:
1. X-Tenant-Id header if present and user is a member, OR
2. The user's primary tenant (first membership found).
"""
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel, EmailStr, Field

from deps import (
    db,
    users_collection,
    get_current_user,
    get_password_hash,
    create_access_token,
)

router = APIRouter(prefix="/api", tags=["tenants"])

# ─── Collections ────────────────────────────────────────────────────────────
tenants_col = db["tenants"]
memberships_col = db["tenant_memberships"]
onboarding_col = db["onboarding_config"]
invitations_col = db["invitations"]


# ─── Helpers ────────────────────────────────────────────────────────────────
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _user_memberships(email: str) -> List[dict]:
    return list(memberships_col.find({"user_email": email}, {"_id": 0}).sort("joined_at", 1))


def get_active_tenant(
    current_user: dict = Depends(get_current_user),
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-Id"),
) -> dict:
    """Resolve the active tenant for this request.

    1. If X-Tenant-Id is provided and user is a member → use it.
    2. Else use user's primary (first) tenant.
    3. If user has no memberships at all (legacy account that pre-dates the
       multi-tenant migration) → auto-provision a personal tenant + owner
       membership so the request can continue. This is the safety net for
       any production deploy where the migration hasn't fully run yet.
    """
    email = current_user["email"]
    memberships = _user_memberships(email)
    if not memberships:
        # Auto-provision a personal tenant for this legacy user
        full_name = current_user.get("full_name") or email.split("@")[0]
        tenant_id = _new_id("ten")
        tenants_col.insert_one({
            "id": tenant_id,
            "name": f"{full_name}'s Workspace",
            "owner_email": email,
            "plan": "free",
            "settings": {},
            "onboarding_completed": False,
            "created_at": _now(),
            "auto_provisioned": True,
        })
        memberships_col.insert_one({
            "id": _new_id("mem"),
            "tenant_id": tenant_id,
            "user_email": email,
            "role": "owner",
            "invited_by": None,
            "joined_at": _now(),
            "auto_provisioned": True,
        })
        memberships = _user_memberships(email)

    chosen_membership = None
    if x_tenant_id:
        chosen_membership = next((m for m in memberships if m["tenant_id"] == x_tenant_id), None)
        if not chosen_membership:
            raise HTTPException(status_code=403, detail="Not a member of requested tenant")
    else:
        chosen_membership = memberships[0]

    tenant = tenants_col.find_one({"id": chosen_membership["tenant_id"]}, {"_id": 0})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Embed the user's role inside this tenant for the request lifecycle
    tenant["_member_role"] = chosen_membership.get("role", "member")
    return tenant


def require_tenant_role(allowed: List[str]):
    """Dependency factory enforcing a minimum role within the active tenant."""

    def _inner(tenant: dict = Depends(get_active_tenant)) -> dict:
        role = tenant.get("_member_role", "member")
        if role not in allowed:
            raise HTTPException(status_code=403, detail=f"Requires one of roles: {','.join(allowed)}")
        return tenant

    return _inner


# ─── Models ─────────────────────────────────────────────────────────────────
class SignupPayload(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str
    workspace_name: str


class OnboardingPayload(BaseModel):
    business_profile: dict = Field(default_factory=dict)
    aria_persona: dict = Field(default_factory=dict)
    sales_process: dict = Field(default_factory=dict)
    whatsapp_config: dict = Field(default_factory=dict)
    completed: bool = False


class InvitePayload(BaseModel):
    email: Optional[EmailStr] = None  # optional — link can be sent to anyone
    role: str = "member"               # member | admin | viewer
    expires_in_days: int = 14


class AcceptInvitePayload(BaseModel):
    token: str
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str


# ─── Public signup (creates tenant + owner) ─────────────────────────────────
@router.post("/auth/signup")
async def signup(payload: SignupPayload):
    """Public self-service signup. Creates user + tenant + owner membership."""
    email = payload.email.lower().strip()
    if users_collection.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create user
    user_doc = {
        "email": email,
        "password_hash": get_password_hash(payload.password),
        "full_name": payload.full_name,
        "role": "owner",  # legacy field; tenant role lives in memberships
        "avatar_url": f"https://ui-avatars.com/api/?name={payload.full_name.replace(' ', '+')}&background=7C35DC&color=fff",
        "team": "Sales",
        "is_active": True,
        "created_at": _now(),
    }
    users_collection.insert_one(user_doc)

    # Create tenant
    tenant_id = _new_id("ten")
    tenants_col.insert_one({
        "id": tenant_id,
        "name": payload.workspace_name.strip(),
        "owner_email": email,
        "plan": "free",
        "settings": {},
        "onboarding_completed": False,
        "created_at": _now(),
    })

    # Create membership
    memberships_col.insert_one({
        "id": _new_id("mem"),
        "tenant_id": tenant_id,
        "user_email": email,
        "role": "owner",
        "invited_by": None,
        "joined_at": _now(),
    })

    token = create_access_token({"sub": email})
    return {
        "token": token,
        "user": {"email": email, "full_name": payload.full_name, "role": "owner"},
        "tenant": {"id": tenant_id, "name": payload.workspace_name, "plan": "free", "onboarding_completed": False},
    }


# ─── Tenant endpoints ───────────────────────────────────────────────────────
@router.get("/tenants/me")
async def list_my_tenants(current_user: dict = Depends(get_current_user)):
    """List all tenants the current user is a member of."""
    memberships = _user_memberships(current_user["email"])
    rows = []
    for m in memberships:
        t = tenants_col.find_one({"id": m["tenant_id"]}, {"_id": 0})
        if t:
            rows.append({**t, "role": m.get("role", "member")})
    return {"tenants": rows}


@router.get("/tenants/active")
async def get_active(tenant: dict = Depends(get_active_tenant)):
    """Get currently-active tenant (from header) + role + onboarding state."""
    cfg = onboarding_col.find_one({"tenant_id": tenant["id"]}, {"_id": 0})
    return {
        "tenant": tenant,
        "role": tenant.get("_member_role"),
        "onboarding_completed": bool(tenant.get("onboarding_completed")),
        "onboarding_config": cfg,
    }


# ─── Onboarding endpoints ───────────────────────────────────────────────────
@router.get("/onboarding/status")
async def onboarding_status(tenant: dict = Depends(get_active_tenant)):
    """Single-source-of-truth onboarding gate: { completed, config }.

    Replaces the legacy per-user endpoint in server.py.
    """
    cfg = onboarding_col.find_one({"tenant_id": tenant["id"]}, {"_id": 0})
    return {
        "completed": bool(tenant.get("onboarding_completed")),
        "onboarding": cfg,
        "tenant": {"id": tenant["id"], "name": tenant.get("name")},
    }


@router.post("/onboarding/complete")
async def onboarding_complete(
    payload: OnboardingPayload,
    tenant: dict = Depends(get_active_tenant),
    current_user: dict = Depends(get_current_user),
):
    """Save onboarding config + mark tenant as onboarded. Owner/admin only."""
    if tenant.get("_member_role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")

    doc = {
        "tenant_id": tenant["id"],
        "business_profile": payload.business_profile,
        "aria_persona": payload.aria_persona,
        "sales_process": payload.sales_process,
        "whatsapp_config": payload.whatsapp_config,
        "completed_at": _now(),
        "completed_by": current_user["email"],
    }
    onboarding_col.update_one({"tenant_id": tenant["id"]}, {"$set": doc}, upsert=True)
    tenants_col.update_one(
        {"id": tenant["id"]},
        {"$set": {"onboarding_completed": True, "updated_at": _now()}},
    )
    return {"status": "ok", "tenant_id": tenant["id"]}


@router.get("/onboarding/aria-config")
async def aria_config_for_prompt(tenant: dict = Depends(get_active_tenant)):
    """Read-only flattened config for system prompt construction (used by Claude callers)."""
    cfg = onboarding_col.find_one({"tenant_id": tenant["id"]}, {"_id": 0}) or {}
    bp = cfg.get("business_profile") or {}
    persona = cfg.get("aria_persona") or {}
    sp = cfg.get("sales_process") or {}
    return {
        "tenant_id": tenant["id"],
        "tenant_name": tenant.get("name"),
        "business_name": bp.get("business_name") or tenant.get("name"),
        "industry": bp.get("industry"),
        "description": bp.get("description"),
        "primary_market": bp.get("primary_market"),
        "country": bp.get("country"),
        "timezone": bp.get("timezone"),
        "aria_name": persona.get("aria_name") or "Aria",
        "tone": persona.get("tone") or "friendly_professional",
        "language": persona.get("language") or "English",
        "fallback_behavior": persona.get("fallback_behavior") or "ask_clarifying",
        "product_description": sp.get("product_description"),
        "deal_size": sp.get("deal_size"),
        "sales_cycle": sp.get("sales_cycle"),
        "qualification_criteria": sp.get("qualification_criteria") or [],
        "pipeline_stages": sp.get("pipeline_stages") or ["New Lead", "Contacted", "Qualified", "Proposal Sent", "Negotiation", "Closed Won", "Closed Lost"],
    }


# ─── Invitations: tokenized link flow ───────────────────────────────────────
def _new_token() -> str:
    """Cryptographically-strong invite token."""
    import secrets
    return secrets.token_urlsafe(24)


def _is_valid_role(role: str) -> bool:
    return role in {"owner", "admin", "member", "viewer"}


@router.post("/invitations")
async def create_invitation(
    payload: InvitePayload,
    tenant: dict = Depends(get_active_tenant),
    current_user: dict = Depends(get_current_user),
):
    """Owner/admin creates a tokenized invite link. No email sent — link is
    returned to the caller for them to share via their preferred channel."""
    if tenant.get("_member_role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")
    if not _is_valid_role(payload.role) or payload.role == "owner":
        raise HTTPException(status_code=400, detail="role must be admin, member, or viewer")
    token = _new_token()
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=max(1, min(payload.expires_in_days, 90)))
    ).isoformat()
    doc = {
        "id": _new_id("inv"),
        "tenant_id": tenant["id"],
        "tenant_name": tenant.get("name"),
        "token": token,
        "email": (payload.email or "").lower().strip() or None,
        "role": payload.role,
        "invited_by": current_user["email"],
        "invited_by_name": current_user.get("full_name") or current_user["email"],
        "expires_at": expires_at,
        "accepted": False,
        "accepted_by": None,
        "accepted_at": None,
        "revoked": False,
        "created_at": _now(),
    }
    invitations_col.insert_one(doc)
    return {
        "invitation": {k: v for k, v in doc.items() if k != "_id"},
        "invite_url": f"/invite/{token}",
    }


@router.get("/invitations")
async def list_invitations(tenant: dict = Depends(get_active_tenant)):
    """List pending invites for the active tenant (owner/admin only)."""
    if tenant.get("_member_role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")
    rows = list(
        invitations_col.find(
            {"tenant_id": tenant["id"]},
            {"_id": 0},
        ).sort("created_at", -1).limit(100)
    )
    return {"invitations": rows}


@router.delete("/invitations/{invite_id}")
async def revoke_invitation(invite_id: str, tenant: dict = Depends(get_active_tenant)):
    """Revoke a pending invite (owner/admin only)."""
    if tenant.get("_member_role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")
    res = invitations_col.update_one(
        {"id": invite_id, "tenant_id": tenant["id"]},
        {"$set": {"revoked": True, "revoked_at": _now()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Invite not found")
    return {"status": "ok"}


# ─── Public invite endpoints (no auth) ──────────────────────────────────────
@router.get("/public/invitations/{token}")
async def get_invite_public(token: str):
    """Public endpoint used by the signup page to render an invite-aware UI.
    Returns minimal safe info — workspace name + role + inviter — never PII."""
    inv = invitations_col.find_one({"token": token}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Invite not found")
    if inv.get("revoked"):
        raise HTTPException(status_code=410, detail="Invite has been revoked")
    if inv.get("accepted"):
        raise HTTPException(status_code=409, detail="Invite has already been accepted")
    if inv.get("expires_at") and inv["expires_at"] < _now():
        raise HTTPException(status_code=410, detail="Invite has expired")
    return {
        "tenant_name": inv.get("tenant_name"),
        "role": inv.get("role"),
        "invited_by_name": inv.get("invited_by_name"),
        "expires_at": inv.get("expires_at"),
        "email_hint": inv.get("email"),  # optional: pre-fill email if provided
    }


@router.post("/public/invitations/accept")
async def accept_invite(payload: AcceptInvitePayload):
    """Accept a tokenized invite. Two cases:
    1. Email already registered → just adds membership to tenant (skip if already a member).
    2. Email not registered → create user + add membership.
    Either way, returns auth token + tenant info so the user can log straight in.
    """
    inv = invitations_col.find_one({"token": payload.token}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Invite not found")
    if inv.get("revoked"):
        raise HTTPException(status_code=410, detail="Invite has been revoked")
    if inv.get("accepted"):
        raise HTTPException(status_code=409, detail="Invite has already been accepted")
    if inv.get("expires_at") and inv["expires_at"] < _now():
        raise HTTPException(status_code=410, detail="Invite has expired")

    email = payload.email.lower().strip()
    tenant = tenants_col.find_one({"id": inv["tenant_id"]}, {"_id": 0})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no longer exists")

    # Create user if missing
    user = users_collection.find_one({"email": email})
    if not user:
        users_collection.insert_one({
            "email": email,
            "password_hash": get_password_hash(payload.password),
            "full_name": payload.full_name,
            "role": "member",
            "avatar_url": f"https://ui-avatars.com/api/?name={payload.full_name.replace(' ', '+')}&background=7C35DC&color=fff",
            "team": "Sales",
            "is_active": True,
            "created_at": _now(),
        })

    # Add membership only if user isn't already a member of this tenant
    existing = memberships_col.find_one({"tenant_id": inv["tenant_id"], "user_email": email})
    if not existing:
        memberships_col.insert_one({
            "id": _new_id("mem"),
            "tenant_id": inv["tenant_id"],
            "user_email": email,
            "role": inv["role"],
            "invited_by": inv.get("invited_by"),
            "invitation_token": inv["token"],
            "joined_at": _now(),
        })

    # Mark invite accepted
    invitations_col.update_one(
        {"token": payload.token},
        {"$set": {"accepted": True, "accepted_by": email, "accepted_at": _now()}},
    )

    token = create_access_token({"sub": email})
    return {
        "token": token,
        "user": {"email": email, "full_name": payload.full_name, "role": "member"},
        "tenant": {
            "id": tenant["id"],
            "name": tenant.get("name"),
            "plan": tenant.get("plan"),
            "onboarding_completed": bool(tenant.get("onboarding_completed", True)),
        },
    }
