"""Multi-tenant foundation for Aria SaaS.

Adds tenants, memberships, and per-tenant onboarding config.
A tenant is a customer workspace — has its own isolated data.
A user can belong to multiple tenants (membership table).
The "active tenant" for a request is resolved from:
1. X-Tenant-Id header if present and user is a member, OR
2. The user's primary tenant (first membership found).
"""
import asyncio
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List

import resend
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel, EmailStr, Field

from deps import (
    db,
    users_collection,
    get_current_user,
    get_password_hash,
    create_access_token,
)

# Resend is initialised globally in server.py; this is a no-op safety net
# in case this module is imported before server.py wires the key.
if not getattr(resend, "api_key", None):
    resend.api_key = os.getenv("RESEND_API_KEY")

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


@router.patch("/tenants/active/settings")
async def patch_tenant_settings(body: dict, tenant: dict = Depends(get_active_tenant)):
    """Owner/admin patches tenant-level settings (e.g. demo_video_url).
    Only whitelisted keys are accepted to avoid rogue writes."""
    if tenant.get("_member_role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")
    allowed = {"demo_video_url", "brand_accent_color", "icp_definition"}
    current_settings = tenant.get("settings") or {}
    merged = {**current_settings}
    for k, v in (body or {}).items():
        if k in allowed:
            merged[k] = (v or "").strip() if isinstance(v, str) else v
    tenants_col.update_one(
        {"id": tenant["id"]},
        {"$set": {"settings": merged, "updated_at": _now()}},
    )
    return {"status": "ok", "settings": merged}


# ─── WhatsApp provider config (per-tenant Meta or 360dialog) ────────────────
def _fernet():
    """Return a Fernet instance for encrypting per-tenant secrets."""
    from cryptography.fernet import Fernet
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="ENCRYPTION_KEY not configured")
    return Fernet(key.encode() if isinstance(key, str) else key)


def _mask_key(plaintext: Optional[str]) -> Optional[str]:
    if not plaintext:
        return None
    last4 = plaintext[-4:] if len(plaintext) >= 4 else plaintext
    return f"••••{last4}"


def _wa_provider_summary(settings: dict) -> dict:
    wa = (settings or {}).get("whatsapp") or {}
    provider = wa.get("provider") or "meta"
    providers = wa.get("providers") or {}
    out = {"provider": provider, "providers": {}}
    for name, cfg in providers.items():
        cfg = cfg or {}
        out["providers"][name] = {
            "phone_number": cfg.get("phone_number"),
            "phone_number_id": cfg.get("phone_number_id"),
            "configured": bool(cfg.get("encrypted_api_key") or cfg.get("encrypted_access_token")),
            "api_key_masked": cfg.get("api_key_last4") and f"••••{cfg['api_key_last4']}" or None,
            "updated_at": cfg.get("updated_at"),
        }
    return out


class WhatsAppProviderPayload(BaseModel):
    provider: str = Field(..., description="meta or 360dialog")
    api_key: Optional[str] = Field(default=None, description="API key (360dialog) or access token (meta)")
    phone_number: Optional[str] = None
    phone_number_id: Optional[str] = None  # required for Meta


@router.get("/tenants/active/whatsapp")
async def get_whatsapp_config(tenant: dict = Depends(get_active_tenant)):
    """Return the active tenant's WhatsApp provider summary (no secrets)."""
    if tenant.get("_member_role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")
    return _wa_provider_summary(tenant.get("settings") or {})


@router.post("/tenants/active/whatsapp")
async def save_whatsapp_config(
    payload: WhatsAppProviderPayload,
    tenant: dict = Depends(get_active_tenant),
):
    """Save WhatsApp provider config for the active tenant.

    For 360dialog: stores an encrypted API key and selects 360dialog as provider.
    For meta: stores an encrypted access token + phone_number_id.
    Either way, the previously configured providers are NOT wiped — switching
    providers is a metadata-only flip.
    """
    if tenant.get("_member_role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")
    if payload.provider not in {"meta", "360dialog"}:
        raise HTTPException(status_code=400, detail="provider must be meta or 360dialog")

    settings = dict(tenant.get("settings") or {})
    wa = dict(settings.get("whatsapp") or {})
    providers = dict(wa.get("providers") or {})
    existing = dict(providers.get(payload.provider) or {})

    # Only re-encrypt if a new key is supplied (allows partial updates).
    if payload.api_key:
        api_key = payload.api_key.strip()
        if not api_key:
            raise HTTPException(status_code=400, detail="api_key cannot be empty")
        encrypted = _fernet().encrypt(api_key.encode()).decode()
        if payload.provider == "meta":
            existing["encrypted_access_token"] = encrypted
        else:
            existing["encrypted_api_key"] = encrypted
        existing["api_key_last4"] = api_key[-4:]

    if payload.phone_number is not None:
        existing["phone_number"] = payload.phone_number.strip() or None
    if payload.phone_number_id is not None:
        existing["phone_number_id"] = payload.phone_number_id.strip() or None

    existing["updated_at"] = _now()
    providers[payload.provider] = existing
    wa["provider"] = payload.provider
    wa["providers"] = providers
    settings["whatsapp"] = wa

    tenants_col.update_one(
        {"id": tenant["id"]},
        {"$set": {"settings": settings, "updated_at": _now()}},
    )
    return {"status": "ok", **_wa_provider_summary(settings)}


@router.delete("/tenants/active/whatsapp/{provider}")
async def remove_whatsapp_provider(
    provider: str,
    tenant: dict = Depends(get_active_tenant),
):
    """Remove a stored WhatsApp provider config. Falls back to the other
    provider if one is left, otherwise leaves the tenant un-configured."""
    if tenant.get("_member_role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")
    if provider not in {"meta", "360dialog"}:
        raise HTTPException(status_code=400, detail="invalid provider")
    settings = dict(tenant.get("settings") or {})
    wa = dict(settings.get("whatsapp") or {})
    providers = dict(wa.get("providers") or {})
    providers.pop(provider, None)
    wa["providers"] = providers
    if wa.get("provider") == provider:
        # Fall back to the other provider if any
        other = next(iter(providers.keys()), None)
        if other:
            wa["provider"] = other
        else:
            wa.pop("provider", None)
    settings["whatsapp"] = wa
    tenants_col.update_one(
        {"id": tenant["id"]},
        {"$set": {"settings": settings, "updated_at": _now()}},
    )
    return {"status": "ok", **_wa_provider_summary(settings)}


@router.post("/tenants/active/whatsapp/test")
async def test_whatsapp_connection(tenant: dict = Depends(get_active_tenant)):
    """Validate stored credentials by calling the chosen provider's health endpoint.

    For 360dialog → GET /health_status (returns 200 when credentials valid).
    For Meta → GET /{phone_number_id}?fields=verified_name (verifies token + phone).
    """
    if tenant.get("_member_role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")
    settings = tenant.get("settings") or {}
    wa = (settings.get("whatsapp") or {})
    provider = wa.get("provider")
    cfg = (wa.get("providers") or {}).get(provider) or {}
    if not provider:
        raise HTTPException(status_code=400, detail="No WhatsApp provider configured")

    import httpx
    try:
        if provider == "360dialog":
            enc = cfg.get("encrypted_api_key")
            if not enc:
                raise HTTPException(status_code=400, detail="360dialog API key not stored")
            api_key = _fernet().decrypt(enc.encode()).decode()
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://waba-v2.360dialog.io/health_status",
                    headers={"D360-API-KEY": api_key},
                )
            ok = resp.status_code in (200, 400)  # 400 = valid key, account-level issue
            return {"ok": ok, "status_code": resp.status_code, "provider": provider}
        else:  # meta
            enc = cfg.get("encrypted_access_token")
            pid = cfg.get("phone_number_id")
            if not enc or not pid:
                raise HTTPException(status_code=400, detail="Meta access_token + phone_number_id required")
            token = _fernet().decrypt(enc.encode()).decode()
            ver = os.getenv("WHATSAPP_GRAPH_API_VERSION", "v23.0")
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"https://graph.facebook.com/{ver}/{pid}?fields=verified_name,display_phone_number",
                    headers={"Authorization": f"Bearer {token}"},
                )
            return {"ok": resp.status_code == 200, "status_code": resp.status_code, "provider": provider, "detail": resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text}
    except HTTPException:
        raise
    except Exception as e:
        return {"ok": False, "error": str(e), "provider": provider}


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


def _frontend_origin(request: Optional[Request]) -> str:
    """Best-effort frontend origin for invite email links.

    Order: explicit FRONTEND_URL env > request Origin/Referer header > BACKEND_URL.
    Falls back to a relative URL if no origin can be determined.
    """
    explicit = os.getenv("FRONTEND_URL") or os.getenv("APP_URL")
    if explicit:
        return explicit.rstrip("/")
    if request is not None:
        origin = request.headers.get("origin") or request.headers.get("referer")
        if origin:
            # Strip path component if Referer was passed
            from urllib.parse import urlparse
            p = urlparse(origin)
            if p.scheme and p.netloc:
                return f"{p.scheme}://{p.netloc}"
    backend = os.getenv("BACKEND_URL", "")
    return backend.rstrip("/") if backend else ""


def _build_invite_email(*, tenant_name: str, inviter_name: str, role: str, invite_url: str, expires_at: str) -> dict:
    """Build a Resend-ready params dict for an invite email."""
    role_blurb = {
        "admin": "Full access — manage team, edit Aria config, read/write all leads.",
        "member": "Manage leads + pipeline, take over conversations, run sequences.",
        "viewer": "Read-only — see leads, pipeline, and conversations.",
    }.get(role, "Workspace access")
    expiry_human = expires_at.split("T")[0] if isinstance(expires_at, str) else str(expires_at)
    plain = (
        f"{inviter_name} invited you to join {tenant_name} on Aria.\n\n"
        f"Role: {role.title()} — {role_blurb}\n\n"
        f"Accept the invite (link expires {expiry_human}):\n{invite_url}\n\n"
        "If you don't recognise this invitation you can safely ignore this email.\n— Aria"
    )
    html = f"""
    <div style="font-family:'Plus Jakarta Sans',Arial,sans-serif;max-width:560px;margin:0 auto;color:#1A0A2E;background:#FFFFFF;padding:0 16px;">
      <div style="padding:28px 0 18px 0;border-bottom:1px solid #E5E5E5;">
        <div style="display:inline-block;background:linear-gradient(135deg,#4C1D95,#7C35DC);color:#fff;font-weight:800;letter-spacing:0.04em;font-size:11px;text-transform:uppercase;padding:5px 10px;border-radius:999px;">Aria · Workspace invite</div>
      </div>
      <div style="padding:24px 0 8px 0;">
        <h1 style="font-size:22px;line-height:1.25;margin:0 0 8px 0;color:#0A0A0A;">You're invited to <span style="color:#7C35DC;">{tenant_name}</span></h1>
        <p style="font-size:14px;line-height:1.6;color:#404040;margin:8px 0;">
          <strong>{inviter_name}</strong> added you to their Aria workspace as <strong>{role.title()}</strong>.
        </p>
        <p style="font-size:13px;line-height:1.6;color:#737373;margin:0 0 20px 0;">{role_blurb}</p>
        <a href="{invite_url}" style="display:inline-block;background:linear-gradient(135deg,#4C1D95,#7C35DC);color:#FFFFFF;text-decoration:none;font-weight:700;padding:11px 22px;border-radius:8px;font-size:14px;">
          Accept invite
        </a>
        <p style="font-size:12px;line-height:1.5;color:#A3A3A3;margin-top:20px;">
          Or paste this link in your browser:<br>
          <a href="{invite_url}" style="color:#7C35DC;word-break:break-all;">{invite_url}</a>
        </p>
        <p style="font-size:12px;color:#A3A3A3;margin-top:18px;">This invite expires on <strong>{expiry_human}</strong>.</p>
      </div>
      <div style="padding:16px 0;border-top:1px solid #E5E5E5;font-size:11px;color:#A3A3A3;">
        Aria — your AI sales hire. If you weren't expecting this email, you can ignore it safely.
      </div>
    </div>
    """
    return {
        "from": os.getenv("SENDER_EMAIL", "onboarding@resend.dev"),
        "to": [],  # caller injects
        "subject": f"{inviter_name} invited you to {tenant_name} on Aria",
        "html": html,
        "text": plain,
    }


async def _send_invite_email(*, to_email: str, tenant_name: str, inviter_name: str, role: str, invite_url: str, expires_at: str) -> dict:
    """Send invite email via Resend. Returns {sent, id?, error?}."""
    if not to_email:
        return {"sent": False, "error": "no_recipient"}
    if not getattr(resend, "api_key", None):
        return {"sent": False, "error": "resend_not_configured"}
    params = _build_invite_email(
        tenant_name=tenant_name,
        inviter_name=inviter_name,
        role=role,
        invite_url=invite_url,
        expires_at=expires_at,
    )
    params["to"] = [to_email]
    try:
        resp = await asyncio.to_thread(resend.Emails.send, params)
        # Resend SDK returns a dict-like with 'id' on success
        msg_id = (resp or {}).get("id") if isinstance(resp, dict) else getattr(resp, "id", None)
        return {"sent": True, "id": msg_id}
    except Exception as e:
        print(f"[invite-email] Resend failed for {to_email}: {e}")
        return {"sent": False, "error": str(e)}


@router.post("/invitations")
async def create_invitation(
    payload: InvitePayload,
    request: Request,
    tenant: dict = Depends(get_active_tenant),
    current_user: dict = Depends(get_current_user),
):
    """Owner/admin creates a tokenized invite link.

    If `payload.email` is provided, an invite email is sent via Resend with the
    accept link. The link is also returned so the caller can copy/share manually.
    """
    if tenant.get("_member_role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")
    if not _is_valid_role(payload.role) or payload.role == "owner":
        raise HTTPException(status_code=400, detail="role must be admin, member, or viewer")
    token = _new_token()
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=max(1, min(payload.expires_in_days, 90)))
    ).isoformat()

    invite_email = (payload.email or "").lower().strip() or None
    inviter_name = current_user.get("full_name") or current_user["email"]

    doc = {
        "id": _new_id("inv"),
        "tenant_id": tenant["id"],
        "tenant_name": tenant.get("name"),
        "token": token,
        "email": invite_email,
        "role": payload.role,
        "invited_by": current_user["email"],
        "invited_by_name": inviter_name,
        "expires_at": expires_at,
        "accepted": False,
        "accepted_by": None,
        "accepted_at": None,
        "revoked": False,
        "email_sent": False,
        "email_last_sent_at": None,
        "email_send_count": 0,
        "created_at": _now(),
    }
    invitations_col.insert_one(doc)

    # Build full URL using the request origin (frontend origin).
    origin = _frontend_origin(request)
    invite_url = f"{origin}/invite/{token}" if origin else f"/invite/{token}"

    email_status = {"sent": False, "skipped": True}
    if invite_email:
        email_status = await _send_invite_email(
            to_email=invite_email,
            tenant_name=tenant.get("name") or "your workspace",
            inviter_name=inviter_name,
            role=payload.role,
            invite_url=invite_url,
            expires_at=expires_at,
        )
        if email_status.get("sent"):
            invitations_col.update_one(
                {"id": doc["id"]},
                {"$set": {
                    "email_sent": True,
                    "email_last_sent_at": _now(),
                    "email_send_count": 1,
                    "email_last_message_id": email_status.get("id"),
                }},
            )
            doc.update({
                "email_sent": True,
                "email_last_sent_at": _now(),
                "email_send_count": 1,
            })

    return {
        "invitation": {k: v for k, v in doc.items() if k != "_id"},
        "invite_url": f"/invite/{token}",
        "invite_full_url": invite_url,
        "email": email_status,
    }


@router.post("/invitations/{invite_id}/resend")
async def resend_invitation(
    invite_id: str,
    request: Request,
    tenant: dict = Depends(get_active_tenant),
    current_user: dict = Depends(get_current_user),
):
    """Re-send the invite email for a pending invitation. Owner/admin only."""
    if tenant.get("_member_role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")
    inv = invitations_col.find_one({"id": invite_id, "tenant_id": tenant["id"]}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Invite not found")
    if inv.get("revoked") or inv.get("accepted"):
        raise HTTPException(status_code=409, detail="Invite is no longer pending")
    if inv.get("expires_at") and inv["expires_at"] < _now():
        raise HTTPException(status_code=410, detail="Invite has expired")
    if not inv.get("email"):
        raise HTTPException(status_code=400, detail="Invite has no email — share the link manually instead")

    origin = _frontend_origin(request)
    invite_url = f"{origin}/invite/{inv['token']}" if origin else f"/invite/{inv['token']}"
    inviter_name = current_user.get("full_name") or current_user["email"]

    email_status = await _send_invite_email(
        to_email=inv["email"],
        tenant_name=tenant.get("name") or "your workspace",
        inviter_name=inviter_name,
        role=inv.get("role", "member"),
        invite_url=invite_url,
        expires_at=inv.get("expires_at"),
    )
    if email_status.get("sent"):
        invitations_col.update_one(
            {"id": invite_id},
            {"$set": {
                "email_sent": True,
                "email_last_sent_at": _now(),
                "email_last_message_id": email_status.get("id"),
            }, "$inc": {"email_send_count": 1}},
        )
    else:
        raise HTTPException(status_code=502, detail=f"Email delivery failed: {email_status.get('error')}")
    return {"status": "sent", "email": email_status}


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
