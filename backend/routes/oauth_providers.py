"""iter109c Batch 1 — Universal OAuth backend (per-tenant credentials).

Replaces all provider-specific OAuth endpoints with a single generic set
that works for every OAuth provider registered in PROVIDER_SPECS below.

Credentials (client_id, client_secret) are entered by the workspace owner
on /app/integrations, encrypted with Fernet, and stored per tenant in
`integration_configs.config`. **No CLIENT_ID/CLIENT_SECRET ever lives in
backend/.env.** Platform-level secrets (JWT, FERNET, EMERGENT_LLM_KEY,
MONGO_URL) stay in .env.

Endpoints (mounted under /api/integrations/{provider}/)
─────────────────────────────────────────────────────────
  POST    /configure       — store encrypted CLIENT_ID + CLIENT_SECRET
  GET     /auth-url        — build OAuth authorize URL (server-side state)
  GET     /callback        — exchange code → access+refresh, store, redirect
  DELETE  /                — revoke token + delete stored credentials
  GET     /status          — connection status + last_sync + scopes
  POST    /test            — live API ping to verify credentials work

Callback URL construction
─────────────────────────
  callback = f"{FRONTEND_URL}/api/integrations/{provider}/callback"
This is identical on preview and production — Kubernetes ingress proxies
/api/* to the backend either way.
"""
from __future__ import annotations

import logging
import os
import secrets
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from deps import db
from routes.tenants import get_active_tenant
from security.encryption import encrypt, decrypt

logger = logging.getLogger("oauth_providers")

router = APIRouter(prefix="/api/integrations", tags=["integrations-oauth"])
public_router = APIRouter(prefix="/api/integrations", tags=["integrations-oauth-public"])

configs_col = db["integration_configs"]
oauth_states_col = db["oauth_states"]
configs_col.create_index([("tenant_id", 1), ("integration_type", 1)])
oauth_states_col.create_index([("state", 1)], unique=True)
oauth_states_col.create_index([("created_at", 1)], expireAfterSeconds=600)  # 10-min TTL


# ─── Provider specs ─────────────────────────────────────────────────────
PROVIDER_SPECS: Dict[str, Dict[str, Any]] = {
    "google": {
        "label": "Google",
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "revoke_url": "https://oauth2.googleapis.com/revoke",
        "userinfo_url": "https://openidconnect.googleapis.com/v1/userinfo",
        "default_scopes": [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/calendar.events",
            "https://www.googleapis.com/auth/calendar.readonly",
            "https://www.googleapis.com/auth/adwords",
            "openid", "email", "profile",
        ],
        "extra_authorize_params": {"access_type": "offline", "prompt": "consent"},
    },
    "microsoft": {
        "label": "Microsoft",
        "authorize_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "userinfo_url": "https://graph.microsoft.com/v1.0/me",
        "default_scopes": [
            "Mail.Read", "Mail.Send", "Calendars.ReadWrite", "offline_access", "User.Read",
        ],
        "extra_authorize_params": {},
    },
    "meta": {
        "label": "Meta",
        "authorize_url": "https://www.facebook.com/v23.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v23.0/oauth/access_token",
        "userinfo_url": "https://graph.facebook.com/v23.0/me",
        "default_scopes": ["ads_read", "leads_retrieval", "pages_read_engagement"],
        "extra_authorize_params": {},
    },
    "linkedin": {
        "label": "LinkedIn",
        "authorize_url": "https://www.linkedin.com/oauth/v2/authorization",
        "token_url": "https://www.linkedin.com/oauth/v2/accessToken",
        "userinfo_url": "https://api.linkedin.com/v2/userinfo",
        "default_scopes": ["r_liteprofile", "r_emailaddress", "w_member_social", "openid", "profile", "email"],
        "extra_authorize_params": {},
    },
    "calendly": {
        "label": "Calendly",
        "authorize_url": "https://auth.calendly.com/oauth/authorize",
        "token_url": "https://auth.calendly.com/oauth/token",
        "revoke_url": "https://auth.calendly.com/oauth/revoke",
        "userinfo_url": "https://api.calendly.com/users/me",
        "default_scopes": ["default"],  # Calendly OAuth doesn't use space-separated scope strings
        "extra_authorize_params": {},
    },
}


def _frontend_url() -> str:
    """Used to build the OAuth callback URL. Works on preview + prod."""
    return (
        os.environ.get("FRONTEND_URL")
        or os.environ.get("PUBLIC_API_BASE_URL")
        or os.environ.get("BACKEND_URL")
        or "http://localhost:3000"
    ).rstrip("/")


def _callback_url(provider: str) -> str:
    return f"{_frontend_url()}/api/integrations/{provider}/callback"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Payloads ───────────────────────────────────────────────────────────
class ConfigureBody(BaseModel):
    client_id: str = Field(min_length=1)
    client_secret: str = Field(min_length=1)
    extra_config: Optional[Dict[str, Any]] = None
    scopes: Optional[list] = None  # caller may narrow scopes


# ─── Helpers ────────────────────────────────────────────────────────────
def _spec(provider: str) -> Dict[str, Any]:
    s = PROVIDER_SPECS.get(provider)
    if not s:
        raise HTTPException(404, f"Unknown OAuth provider: {provider}")
    return s


def _load_config(tenant_id: str, provider: str) -> Dict[str, Any]:
    """Load integration config for (tenant_id, provider).

    Falls back to the legacy `pt_integrations` collection so existing
    Pietential workspace credentials (Saleshandy, Lemlist) survive the
    migration without manual re-entry. Legacy records are auto-mirrored
    into `integration_configs` on first read so the next call is canonical.
    """
    doc = configs_col.find_one(
        {"tenant_id": tenant_id, "integration_type": provider},
        {"_id": 0},
    )
    if doc:
        return doc

    # Legacy fallback (Pietential pt_integrations)
    legacy_col = db["pt_integrations"]
    legacy = legacy_col.find_one({"name": provider}, {"_id": 0})
    if legacy and (legacy.get("api_key") or legacy.get("status") == "connected"):
        cfg = {}
        if legacy.get("api_key"):
            cfg["api_key"] = encrypt(legacy["api_key"]) if not str(legacy["api_key"]).startswith("enc::") else legacy["api_key"]
        for extra_field in ("phone_number_id", "from_email", "from_name", "team_id"):
            if legacy.get(extra_field):
                cfg[extra_field] = legacy[extra_field]
        mirrored = {
            "tenant_id": tenant_id,
            "integration_type": provider,
            "status": legacy.get("status") or "connected",
            "config": cfg,
            "connected_at": legacy.get("connected_at") or legacy.get("updated_at"),
            "last_sync_at": legacy.get("last_sync_at"),
            "created_at": legacy.get("created_at") or _now_iso(),
            "updated_at": _now_iso(),
            "migrated_from_legacy": True,
        }
        configs_col.update_one(
            {"tenant_id": tenant_id, "integration_type": provider},
            {"$set": mirrored},
            upsert=True,
        )
        return mirrored
    return {}


def _decrypt_secrets(cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(cfg or {})
    for k in ("client_id", "client_secret", "access_token", "refresh_token", "api_key", "webhook_secret"):
        if out.get(k):
            out[k] = decrypt(out[k])
    return out


def _require_owner(tenant: dict) -> None:
    if tenant.get("_member_role") not in ("owner", "admin", "master_admin", "pietential_owner"):
        raise HTTPException(403, "Owner/Admin only")


# ─── Endpoints ──────────────────────────────────────────────────────────
@router.post("/{provider}/configure")
async def configure(
    provider: str,
    body: ConfigureBody,
    tenant: dict = Depends(get_active_tenant),
):
    """Store encrypted CLIENT_ID + CLIENT_SECRET (and optional scopes/extras)
    for the given provider. Does NOT initiate OAuth — just persists creds."""
    _require_owner(tenant)
    spec = _spec(provider)
    existing = _load_config(tenant["id"], provider)
    existing_cfg = existing.get("config") or {}
    merged = {
        **existing_cfg,
        "client_id": encrypt(body.client_id),
        "client_secret": encrypt(body.client_secret),
        "scopes": body.scopes or spec["default_scopes"],
        **(body.extra_config or {}),
    }
    # iter109c Batch 2 — capture who configured + when (audit trail).
    audit = {
        "configured_by_user_id": tenant.get("_member_user_id"),
        "configured_by_name": tenant.get("_member_full_name") or tenant.get("_member_email") or "unknown",
        "configured_at": _now_iso(),
    }
    configs_col.update_one(
        {"tenant_id": tenant["id"], "integration_type": provider},
        {"$set": {
            "tenant_id": tenant["id"],
            "integration_type": provider,
            "status": existing.get("status") or "configured",
            "config": merged,
            "updated_at": _now_iso(),
            **audit,
            **({"created_at": _now_iso()} if not existing else {}),
        }},
        upsert=True,
    )
    return {"configured": True, "provider": provider}


@router.get("/{provider}/auth-url")
async def auth_url(provider: str, tenant: dict = Depends(get_active_tenant)):
    """Build the OAuth authorization URL using stored client_id + scopes.
    Generates a one-time CSRF `state` token bound to (tenant_id, provider)."""
    spec = _spec(provider)
    cfg = _decrypt_secrets((_load_config(tenant["id"], provider)).get("config") or {})
    if not cfg.get("client_id") or not cfg.get("client_secret"):
        raise HTTPException(412, "Provider not yet configured. POST /configure first.")
    state = secrets.token_urlsafe(32)
    oauth_states_col.insert_one({
        "state": state,
        "tenant_id": tenant["id"],
        "provider": provider,
        "created_at": datetime.now(timezone.utc),
    })
    params = {
        "client_id": cfg["client_id"],
        "redirect_uri": _callback_url(provider),
        "response_type": "code",
        "scope": " ".join(cfg.get("scopes") or spec["default_scopes"]),
        "state": state,
        **spec.get("extra_authorize_params", {}),
    }
    url = f"{spec['authorize_url']}?{urllib.parse.urlencode(params)}"
    return {"auth_url": url, "state": state}


@public_router.get("/{provider}/callback")
async def callback(provider: str, request: Request, code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    """OAuth callback. Exchanges `code` for tokens, stores them encrypted,
    then redirects the browser back to the Integrations page with a status."""
    spec = _spec(provider)
    fe = _frontend_url()
    if error:
        return RedirectResponse(f"{fe}/app/integrations?error={provider}&reason={urllib.parse.quote(error)}", status_code=302)
    if not code or not state:
        return RedirectResponse(f"{fe}/app/integrations?error={provider}&reason=missing_code", status_code=302)

    st = oauth_states_col.find_one_and_delete({"state": state})
    if not st or st.get("provider") != provider:
        return RedirectResponse(f"{fe}/app/integrations?error={provider}&reason=invalid_state", status_code=302)
    tenant_id = st["tenant_id"]
    cfg = _decrypt_secrets((_load_config(tenant_id, provider)).get("config") or {})
    if not cfg.get("client_id"):
        return RedirectResponse(f"{fe}/app/integrations?error={provider}&reason=not_configured", status_code=302)

    token_data = {
        "code": code,
        "client_id": cfg["client_id"],
        "client_secret": cfg["client_secret"],
        "redirect_uri": _callback_url(provider),
        "grant_type": "authorization_code",
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(spec["token_url"], data=token_data, headers={"Accept": "application/json"})
            resp.raise_for_status()
            tokens = resp.json()
    except Exception as e:
        logger.exception("OAuth token exchange failed for %s: %s", provider, e)
        return RedirectResponse(f"{fe}/app/integrations?error={provider}&reason=token_exchange_failed", status_code=302)

    update = {
        "access_token": encrypt(tokens.get("access_token", "")),
        "refresh_token": encrypt(tokens.get("refresh_token", "")) if tokens.get("refresh_token") else None,
        "expires_in": tokens.get("expires_in"),
        "token_type": tokens.get("token_type"),
        "granted_scopes": (tokens.get("scope") or " ".join(cfg.get("scopes") or spec["default_scopes"])).split(),
    }
    # Audit trail — copy from configure step if present, else stamp on this callback.
    prev = _load_config(tenant_id, provider) or {}
    audit = {
        "connected_by_user_id": prev.get("configured_by_user_id") or prev.get("connected_by_user_id"),
        "connected_by_name": prev.get("configured_by_name") or prev.get("connected_by_name") or "unknown",
    }
    configs_col.update_one(
        {"tenant_id": tenant_id, "integration_type": provider},
        {"$set": {
            "status": "connected",
            "config": {**(prev.get("config") or {}), **{k: v for k, v in update.items() if v is not None}},
            "connected_at": _now_iso(),
            "last_sync_at": _now_iso(),
            "updated_at": _now_iso(),
            **audit,
        }},
        upsert=True,
    )
    return RedirectResponse(f"{fe}/app/integrations?connected={provider}", status_code=302)


@router.delete("/{provider}")
async def disconnect(provider: str, tenant: dict = Depends(get_active_tenant)):
    """Revoke the token (best-effort) and delete stored credentials."""
    _require_owner(tenant)
    spec = PROVIDER_SPECS.get(provider, {})
    cfg = _decrypt_secrets((_load_config(tenant["id"], provider)).get("config") or {})
    revoke_url = spec.get("revoke_url")
    if revoke_url and cfg.get("access_token"):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(revoke_url, data={"token": cfg["access_token"]})
        except Exception:
            logger.warning("Token revoke failed for %s — proceeding with local delete", provider)
    configs_col.delete_one({"tenant_id": tenant["id"], "integration_type": provider})
    return {"disconnected": True, "provider": provider}


@router.get("/{provider}/status")
async def status(provider: str, tenant: dict = Depends(get_active_tenant)):
    doc = _load_config(tenant["id"], provider)
    cfg = doc.get("config") or {}
    has_client = bool(cfg.get("client_id"))
    has_token = bool(cfg.get("access_token"))
    has_api_key = bool(cfg.get("api_key"))
    # OAuth providers connect once tokens are stored; API-key providers
    # connect on save. Use the raw `status` from DB when present (legacy
    # records may carry "connected" / "needs_setup" already).
    derived = "not_connected"
    if has_token or has_api_key or doc.get("status") == "connected":
        derived = "connected"
    elif has_client or doc.get("status") in ("configured", "needs_setup"):
        derived = "configured"
    return {
        "provider": provider,
        "status": doc.get("status") if doc.get("status") in ("connected",) and (has_token or has_api_key) else derived,
        "configured": has_client or has_api_key,
        "connected": has_token or has_api_key,
        "scopes": cfg.get("granted_scopes") or cfg.get("scopes") or [],
        "last_sync_at": doc.get("last_sync_at"),
        "connected_at": doc.get("connected_at"),
        "connected_by_name": doc.get("connected_by_name") or doc.get("configured_by_name"),
        "error_message": doc.get("error_message"),
    }


@router.post("/{provider}/test")
async def test_credentials(provider: str, tenant: dict = Depends(get_active_tenant)):
    """Live credential check — hits the provider's userinfo endpoint."""
    spec = _spec(provider)
    cfg = _decrypt_secrets((_load_config(tenant["id"], provider)).get("config") or {})
    if not cfg.get("access_token"):
        raise HTTPException(412, "Not connected — complete OAuth first")
    url = spec.get("userinfo_url")
    if not url:
        return {"valid": True, "message": "No userinfo endpoint configured; assuming valid."}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {cfg['access_token']}"})
            ok = resp.status_code < 400
            return {
                "valid": ok,
                "status_code": resp.status_code,
                "message": "Credentials work" if ok else f"Provider returned {resp.status_code}",
            }
    except Exception as e:
        return {"valid": False, "message": f"Request failed: {e}"}


# ─── API-key providers (Saleshandy, Lemlist, Resend, Proxycurl, etc.) ───
# Reuse the same /configure shape with a single `api_key` field plus optional extras.
class ApiKeyBody(BaseModel):
    api_key: str = Field(min_length=1)
    extra_config: Optional[Dict[str, Any]] = None


@router.post("/{provider}/configure-api-key")
async def configure_api_key(
    provider: str,
    body: ApiKeyBody,
    tenant: dict = Depends(get_active_tenant),
):
    _require_owner(tenant)
    existing = _load_config(tenant["id"], provider)
    existing_cfg = existing.get("config") or {}
    merged = {
        **existing_cfg,
        "api_key": encrypt(body.api_key),
        **(body.extra_config or {}),
    }
    actor = tenant.get("_member") or {}
    audit = {
        "connected_by_user_id": tenant.get("_member_user_id") or actor.get("user_id"),
        "connected_by_name": tenant.get("_member_full_name") or actor.get("full_name") or tenant.get("_member_email") or "unknown",
    }
    configs_col.update_one(
        {"tenant_id": tenant["id"], "integration_type": provider},
        {"$set": {
            "tenant_id": tenant["id"],
            "integration_type": provider,
            "status": "connected",  # API key providers are connected on save
            "config": merged,
            "connected_at": _now_iso(),
            "updated_at": _now_iso(),
            **audit,
            **({"created_at": _now_iso()} if not existing else {}),
        }},
        upsert=True,
    )
    return {"configured": True, "provider": provider, "auth_type": "api_key"}


# ─── Catalogue (all known providers — for the frontend registry sync) ───
@router.get("/providers/list")
async def list_providers():
    """Light catalogue of OAuth providers and the scopes they request. The
    frontend has its own canonical registry; this endpoint lets QA & tests
    confirm backend + frontend agree."""
    return {
        "providers": [
            {"id": p, "label": s["label"], "scopes": s["default_scopes"], "auth_type": "oauth"}
            for p, s in PROVIDER_SPECS.items()
        ],
    }
