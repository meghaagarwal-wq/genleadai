"""Iter106 — ACTION 5: OAuth scaffolds for 6 third-party integrations.

Scope (per the user's explicit choice 5c — build all 6 scaffolds against
placeholder env vars, real OAuth verification deferred until credentials
are populated):

  1. Calendly        — webhook:write, event_type:read, scheduled_event:read
  2. Gmail (Google)  — gmail.readonly, gmail.send
  3. Outlook (MS)    — Mail.Read, Mail.Send
  4. Meta Ads        — ads_read, leads_retrieval, pages_read_engagement
  5. LinkedIn        — r_liteprofile, r_emailaddress, w_member_social
  6. Google Ads      — https://www.googleapis.com/auth/adwords

Common contract:
  - GET  /api/integrations/{provider}/connect    — returns {auth_url} the
    frontend opens in a popup
  - GET  /api/integrations/{provider}/callback   — exchanges code for tokens,
    stores Fernet-encrypted in integration_configs
  - DELETE /api/integrations/{provider}          — revokes and clears creds
  - background `oauth_token_refresh_loop` runs every 6h, rotates any token
    whose `expires_at` is within the next 24h, never raises.

The `auth_url` builders ARE LIVE — the moment client_id + client_secret +
redirect_uri are populated in /app/backend/.env, every flow becomes
operational. Until then, /connect returns HTTP 503 with a clear message
naming the missing env vars so the operator knows exactly what to add.
"""
from __future__ import annotations

import asyncio
import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from deps import db, get_current_user
from security.encryption import encrypt, decrypt

router = APIRouter(tags=["iter106-oauth"])

integrations_col = db["integration_configs"]
audit_col = db["audit_log"]

# Default callback host. In production this should resolve to your API origin.
def _api_base(request: Optional[Request] = None) -> str:
    """Resolve the backend origin used to build OAuth redirect URIs.

    iter161 — Deployer Agent flagged the previous env-var-first approach
    because `PUBLIC_API_BASE_URL=https://app.genleadai.com` in `.env` was
    routing every preview deploy's OAuth flow to the production domain.

    Resolution order (highest → lowest priority):
      1. `X-Forwarded-Proto` + `X-Forwarded-Host` from the request (set by
         the Kubernetes ingress). This makes preview and production auto-
         resolve to the right callback URL WITHOUT any env-var pinning.
      2. `request.base_url` (uvicorn's view of the incoming request).
      3. `PUBLIC_API_BASE_URL` env override — only used when the caller
         has no request (background token-refresh loop).
      4. Legacy env fallbacks (BACKEND_URL / FRONTEND_URL).

    We deliberately do NOT fall back to `localhost` — a broken callback
    URL is preferable to silently routing production OAuth to localhost.
    """
    # 1 + 2. Derive from the incoming request when we have one.
    if request is not None:
        proto = request.headers.get("x-forwarded-proto")
        host = request.headers.get("x-forwarded-host") or request.headers.get("host")
        if proto and host:
            return f"{proto}://{host}".rstrip("/")
        try:
            base = str(request.base_url)  # e.g. "https://foo.example.com/"
            if base and not base.startswith("http://localhost") and not base.startswith("http://127."):
                return base.rstrip("/")
        except Exception:
            pass

    # 3 + 4. Env-var fallbacks (only when we don't have a request, i.e.
    # background loops). This intentionally comes AFTER the request-based
    # resolution so a preview deploy inheriting the production env var
    # doesn't leak OAuth to production.
    return (
        os.environ.get("PUBLIC_API_BASE_URL")
        or os.environ.get("BACKEND_URL")
        or os.environ.get("FRONTEND_URL")
        or ""
    ).rstrip("/")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _state_for(user_email: str, tenant_id: str, provider: str) -> str:
    """Anti-CSRF state token. Stored in DB with a 10-minute TTL."""
    state = secrets.token_urlsafe(24)
    db["oauth_states"].insert_one({
        "state": state,
        "user_email": user_email,
        "tenant_id": tenant_id,
        "provider": provider,
        "created_at": _now_iso(),
    })
    return state


def _consume_state(state: str) -> Optional[Dict[str, Any]]:
    doc = db["oauth_states"].find_one_and_delete({"state": state}, projection={"_id": 0})
    if not doc:
        return None
    # 10-min TTL guard
    try:
        created = datetime.fromisoformat(doc.get("created_at"))
        if (_now() - created).total_seconds() > 600:
            return None
    except Exception:
        return None
    return doc


# ─── Provider config table ──────────────────────────────────────────────────
# Everything a provider needs to construct an OAuth flow. Adding a new
# provider = adding one row here + (optionally) overriding `exchange()`
# if the provider uses a non-standard token response.
PROVIDERS: Dict[str, Dict[str, Any]] = {
    "calendly": {
        "client_id_env":     "CALENDLY_CLIENT_ID",
        "client_secret_env": "CALENDLY_CLIENT_SECRET",
        "authorize_url":     "https://auth.calendly.com/oauth/authorize",
        "token_url":         "https://auth.calendly.com/oauth/token",
        "revoke_url":        "https://auth.calendly.com/oauth/revoke",
        "scopes":            "default",  # Calendly v2 uses a single 'default' scope
        "extra_authorize":   {},
    },
    "gmail": {
        "client_id_env":     "GMAIL_CLIENT_ID",
        "client_secret_env": "GMAIL_CLIENT_SECRET",
        "authorize_url":     "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url":         "https://oauth2.googleapis.com/token",
        "revoke_url":        "https://oauth2.googleapis.com/revoke",
        "scopes":            "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.send",
        "extra_authorize":   {"access_type": "offline", "prompt": "consent", "include_granted_scopes": "true"},
    },
    "outlook": {
        "client_id_env":     "MICROSOFT_CLIENT_ID",
        "client_secret_env": "MICROSOFT_CLIENT_SECRET",
        "authorize_url":     "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url":         "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "revoke_url":        None,  # MS Graph doesn't expose a public revoke
        "scopes":            "Mail.Read Mail.Send offline_access",
        "extra_authorize":   {"prompt": "select_account"},
    },
    "meta": {
        "client_id_env":     "META_APP_ID",
        "client_secret_env": "META_APP_SECRET",
        "authorize_url":     "https://www.facebook.com/v18.0/dialog/oauth",
        "token_url":         "https://graph.facebook.com/v18.0/oauth/access_token",
        "revoke_url":        None,
        "scopes":            "ads_read leads_retrieval pages_read_engagement",
        "extra_authorize":   {},
    },
    "linkedin": {
        "client_id_env":     "LINKEDIN_CLIENT_ID",
        "client_secret_env": "LINKEDIN_CLIENT_SECRET",
        "authorize_url":     "https://www.linkedin.com/oauth/v2/authorization",
        "token_url":         "https://www.linkedin.com/oauth/v2/accessToken",
        "revoke_url":        None,
        "scopes":            "r_liteprofile r_emailaddress w_member_social",
        "extra_authorize":   {},
    },
    "googleads": {
        "client_id_env":     "GOOGLE_ADS_CLIENT_ID",
        "client_secret_env": "GOOGLE_ADS_CLIENT_SECRET",
        "authorize_url":     "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url":         "https://oauth2.googleapis.com/token",
        "revoke_url":        "https://oauth2.googleapis.com/revoke",
        "scopes":            "https://www.googleapis.com/auth/adwords",
        "extra_authorize":   {"access_type": "offline", "prompt": "consent"},
    },
}


def _cfg(provider: str) -> Dict[str, Any]:
    p = PROVIDERS.get(provider)
    if not p:
        raise HTTPException(404, f"Unknown OAuth provider: {provider}")
    return p


def _creds(provider: str) -> Tuple[Optional[str], Optional[str]]:
    p = _cfg(provider)
    return os.getenv(p["client_id_env"]), os.getenv(p["client_secret_env"])


def _redirect_uri(provider: str, request: Optional[Request] = None) -> str:
    return f"{_api_base(request).rstrip('/')}/api/integrations/{provider}/callback"


def _active_tenant_for_user(user_email: str) -> Optional[str]:
    m = db["tenant_memberships"].find_one({"user_email": user_email}, {"_id": 0, "tenant_id": 1})
    return (m or {}).get("tenant_id")


# ─── /connect — produce the auth URL ────────────────────────────────────────
@router.get("/api/integrations/{provider}/connect")
async def oauth_connect(provider: str, request: Request, current_user: dict = Depends(get_current_user)):
    cfg = _cfg(provider)
    cid, csecret = _creds(provider)
    if not cid or not csecret:
        raise HTTPException(
            503,
            f"{provider} OAuth not configured. Set {cfg['client_id_env']} and "
            f"{cfg['client_secret_env']} in backend/.env, restart, and retry."
        )
    tenant_id = request.headers.get("X-Tenant-Id") or _active_tenant_for_user(current_user["email"])
    if not tenant_id:
        raise HTTPException(400, "No active tenant for this user")

    state = _state_for(current_user["email"], tenant_id, provider)
    params = {
        "client_id": cid,
        "redirect_uri": _redirect_uri(provider, request),
        "response_type": "code",
        "scope": cfg["scopes"],
        "state": state,
        **cfg.get("extra_authorize", {}),
    }
    return {"auth_url": f"{cfg['authorize_url']}?{urlencode(params)}", "provider": provider}


# ─── /callback — code → token exchange ──────────────────────────────────────
@router.get("/api/integrations/{provider}/callback")
async def oauth_callback(provider: str, request: Request, code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    if error:
        return HTMLResponse(
            f"<h3>OAuth error: {error}</h3><p>Close this window and try again.</p>",
            status_code=400,
        )
    if not code or not state:
        return HTMLResponse("<h3>Missing code or state</h3>", status_code=400)

    state_doc = _consume_state(state)
    if not state_doc or state_doc.get("provider") != provider:
        return HTMLResponse("<h3>Invalid or expired OAuth state</h3>", status_code=400)

    cfg = _cfg(provider)
    cid, csecret = _creds(provider)
    if not cid or not csecret:
        return HTMLResponse("<h3>Provider not configured</h3>", status_code=503)

    # Standard OAuth2 code-exchange. Meta uses GET; everyone else uses POST form.
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            if provider == "meta":
                r = await client.get(cfg["token_url"], params={
                    "client_id": cid,
                    "client_secret": csecret,
                    "redirect_uri": _redirect_uri(provider, request),
                    "code": code,
                })
            else:
                r = await client.post(
                    cfg["token_url"],
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": _redirect_uri(provider, request),
                        "client_id": cid,
                        "client_secret": csecret,
                    },
                    headers={"Accept": "application/json"},
                )
            r.raise_for_status()
            tok = r.json()
    except Exception as e:
        return HTMLResponse(f"<h3>Token exchange failed: {e}</h3>", status_code=502)

    access = tok.get("access_token")
    refresh = tok.get("refresh_token")
    expires_in = int(tok.get("expires_in") or 3600)
    expires_at = (_now() + timedelta(seconds=expires_in)).isoformat()

    integrations_col.update_one(
        {"tenant_id": state_doc["tenant_id"], "platform": provider},
        {"$set": {
            "tenant_id": state_doc["tenant_id"],
            "platform": provider,
            "type": provider,  # legacy compat
            "config": {
                "access_token": encrypt(access) if access else "",
                "refresh_token": encrypt(refresh) if refresh else "",
                "scope": tok.get("scope") or cfg["scopes"],
                "token_type": tok.get("token_type") or "Bearer",
                "expires_at": expires_at,
                "connected_at": _now_iso(),
                "connected_by": state_doc["user_email"],
            },
            "status": "connected",
            "last_sync": _now_iso(),
            "updated_at": _now_iso(),
        }},
        upsert=True,
    )

    audit_col.insert_one({
        "tenant_id": state_doc["tenant_id"],
        "event": f"oauth_connected:{provider}",
        "user_email": state_doc["user_email"],
        "created_at": _now_iso(),
    })

    # Provider-specific post-connect hooks (best-effort, never blocks the callback).
    try:
        if provider == "calendly" and access:
            # Register no-show + booked + cancelled webhooks
            await _calendly_register_webhooks(state_doc["tenant_id"], access, request)
    except Exception as e:
        print(f"[oauth_callback] {provider} post-connect hook failed: {e}")

    return HTMLResponse(f"""<!DOCTYPE html><html><body style="font-family:system-ui;padding:32px;text-align:center;">
      <div style="font-size:48px;">✅</div>
      <h2 style="color:#5B28D4">{provider.title()} connected</h2>
      <p>You can close this window — ARIA is set up.</p>
      <script>window.opener && window.opener.postMessage({{type:"oauth_done",provider:"{provider}"}},"*"); setTimeout(()=>window.close(),800);</script>
    </body></html>""")


# ─── /disconnect ─────────────────────────────────────────────────────────────
@router.delete("/api/integrations/{provider}")
async def oauth_disconnect(provider: str, request: Request, current_user: dict = Depends(get_current_user)):
    _cfg(provider)  # 404 if unknown
    tenant_id = request.headers.get("X-Tenant-Id") or _active_tenant_for_user(current_user["email"])
    if not tenant_id:
        raise HTTPException(400, "No active tenant")
    doc = integrations_col.find_one({"tenant_id": tenant_id, "platform": provider}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Integration not connected")
    cfg = _cfg(provider)
    # Best-effort revoke
    if cfg.get("revoke_url") and doc.get("config", {}).get("access_token"):
        try:
            token = decrypt(doc["config"]["access_token"])
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(cfg["revoke_url"], data={"token": token})
        except Exception as e:
            print(f"[oauth_disconnect] {provider} revoke failed: {e}")
    integrations_col.delete_one({"tenant_id": tenant_id, "platform": provider})
    audit_col.insert_one({
        "tenant_id": tenant_id,
        "event": f"oauth_disconnected:{provider}",
        "user_email": current_user["email"],
        "created_at": _now_iso(),
    })
    return {"ok": True, "provider": provider}


# ─── Calendly post-connect: register webhooks ───────────────────────────────
async def _calendly_register_webhooks(tenant_id: str, access_token: str, request: Optional[Request] = None) -> None:
    """Register Calendly webhook for invitee.created, invitee.canceled,
    and invitee_no_show.created so ARIA can react in real time."""
    base = _api_base(request).rstrip("/")
    callback_url = f"{base}/api/webhooks/calendly?tenant_id={tenant_id}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        # Need the organization URI
        me = await client.get("https://api.calendly.com/users/me",
                              headers={"Authorization": f"Bearer {access_token}"})
        me.raise_for_status()
        org = me.json()["resource"]["current_organization"]
        signing_key = secrets.token_urlsafe(24)
        for event in ("invitee.created", "invitee.canceled", "invitee_no_show.created"):
            try:
                resp = await client.post(
                    "https://api.calendly.com/webhook_subscriptions",
                    headers={"Authorization": f"Bearer {access_token}",
                             "Content-Type": "application/json"},
                    json={
                        "url": callback_url,
                        "events": [event],
                        "organization": org,
                        "scope": "organization",
                        "signing_key": signing_key,
                    },
                )
                if resp.status_code not in (200, 201):
                    print(f"[calendly_webhooks] {event} → HTTP {resp.status_code}: {resp.text[:200]}")
            except Exception as e:
                print(f"[calendly_webhooks] {event} failed: {e}")
        # Persist signing key encrypted
        integrations_col.update_one(
            {"tenant_id": tenant_id, "platform": "calendly"},
            {"$set": {"config.webhook_signing_key": encrypt(signing_key),
                      "config.organization": org}},
        )


# ─── Token refresh background loop ──────────────────────────────────────────
async def oauth_token_refresh_loop():
    """Every 6 hours, rotate any OAuth token whose expires_at is within the
    next 24h. Never raises."""
    while True:
        try:
            cutoff = (_now() + timedelta(hours=24)).isoformat()
            rotating = list(integrations_col.find({
                "platform": {"$in": list(PROVIDERS.keys())},
                "config.expires_at": {"$lte": cutoff},
                "config.refresh_token": {"$exists": True, "$ne": ""},
            }, {"_id": 0}))
            for doc in rotating:
                provider = doc.get("platform")
                cfg = PROVIDERS.get(provider) or {}
                cid, csecret = _creds(provider)
                if not (cid and csecret):
                    continue
                try:
                    refresh = decrypt(doc["config"]["refresh_token"])
                    async with httpx.AsyncClient(timeout=15.0) as client:
                        r = await client.post(cfg["token_url"], data={
                            "grant_type": "refresh_token",
                            "refresh_token": refresh,
                            "client_id": cid,
                            "client_secret": csecret,
                        }, headers={"Accept": "application/json"})
                        r.raise_for_status()
                        tok = r.json()
                    new_access = tok.get("access_token")
                    new_refresh = tok.get("refresh_token") or refresh
                    expires_in = int(tok.get("expires_in") or 3600)
                    integrations_col.update_one(
                        {"tenant_id": doc["tenant_id"], "platform": provider},
                        {"$set": {
                            "config.access_token": encrypt(new_access),
                            "config.refresh_token": encrypt(new_refresh),
                            "config.expires_at": (_now() + timedelta(seconds=expires_in)).isoformat(),
                            "config.rotated_at": _now_iso(),
                            "last_sync": _now_iso(),
                        }},
                    )
                    print(f"[oauth_refresh] rotated {provider} for {doc['tenant_id']}")
                except Exception as e:
                    print(f"[oauth_refresh] {provider} for {doc['tenant_id']} failed: {e}")
        except Exception as e:
            print(f"[oauth_token_refresh_loop] error: {e}")
        await asyncio.sleep(6 * 3600)
