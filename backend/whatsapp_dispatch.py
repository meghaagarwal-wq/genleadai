"""Tenant-aware WhatsApp dispatch.

Single entry point used by server.py to send WhatsApp messages. Looks up the
active tenant's chosen provider (meta vs 360dialog), decrypts the stored
credential, and POSTs to the right provider API.

Falls back to global env-based Meta config when no tenant is supplied OR the
tenant has no provider configured (preserves legacy single-tenant behaviour).
"""
from __future__ import annotations

import os
from typing import Optional, Dict, Any

import httpx
from cryptography.fernet import Fernet

from deps import db

tenants_col = db["tenants"]


# ─── Helpers ─────────────────────────────────────────────────────────────────
def _normalize_phone(phone: str) -> str:
    return "".join(c for c in (phone or "") if c.isdigit())


def _fernet() -> Optional[Fernet]:
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        return None
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        return None


def _resolve_provider(tenant_id: Optional[str]) -> Dict[str, Any]:
    """Return {provider, config} dict for the tenant or {} if unconfigured.

    Provider is one of: 'meta_tenant', '360dialog', 'meta_global', 'none'.
    """
    if tenant_id:
        t = tenants_col.find_one({"id": tenant_id}, {"_id": 0, "settings": 1})
        wa = ((t or {}).get("settings") or {}).get("whatsapp") or {}
        provider = wa.get("provider")
        cfg = (wa.get("providers") or {}).get(provider) or {}
        if provider == "360dialog" and cfg.get("encrypted_api_key"):
            return {"provider": "360dialog", "config": cfg}
        if provider == "meta" and cfg.get("encrypted_access_token") and cfg.get("phone_number_id"):
            return {"provider": "meta_tenant", "config": cfg}
    # Fallback to global env-based Meta if set
    if os.getenv("WHATSAPP_ACCESS_TOKEN") and os.getenv("WHATSAPP_PHONE_NUMBER_ID"):
        return {"provider": "meta_global", "config": {}}
    return {"provider": "none", "config": {}}


def _decrypt(encrypted: str) -> Optional[str]:
    f = _fernet()
    if not f or not encrypted:
        return None
    try:
        return f.decrypt(encrypted.encode()).decode()
    except Exception as e:
        print(f"[whatsapp_dispatch] decrypt failed: {e}")
        return None


# ─── Provider implementations ───────────────────────────────────────────────
async def _send_meta(*, access_token: str, phone_number_id: str, to: str, body: str) -> Dict[str, Any]:
    ver = os.getenv("WHATSAPP_GRAPH_API_VERSION", "v23.0")
    base = os.getenv("WHATSAPP_API_BASE_URL", "https://graph.facebook.com").rstrip("/")
    url = f"{base}/{ver}/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"body": body, "preview_url": True},
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
    if resp.status_code >= 400:
        return {"sent": False, "error": "api_error", "status": resp.status_code, "detail": resp.text, "provider": "meta"}
    data = resp.json()
    return {"sent": True, "message_id": data.get("messages", [{}])[0].get("id"), "raw": data, "provider": "meta"}


async def _send_360dialog(*, api_key: str, to: str, body: str) -> Dict[str, Any]:
    url = "https://waba-v2.360dialog.io/messages"
    headers = {"D360-API-KEY": api_key, "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"body": body, "preview_url": True},
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
    if resp.status_code >= 400:
        return {"sent": False, "error": "api_error", "status": resp.status_code, "detail": resp.text, "provider": "360dialog"}
    data = resp.json()
    return {"sent": True, "message_id": data.get("messages", [{}])[0].get("id"), "raw": data, "provider": "360dialog"}


# ─── Public API ──────────────────────────────────────────────────────────────
async def send_whatsapp_text(to_phone: str, body: str, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Send a WhatsApp text via the tenant's chosen provider.

    Returns a dict with at least {sent: bool, provider?: str, error?: str}.
    Logged-only mode (sent=False, logged_only=True) when no provider is set.
    """
    normalized = _normalize_phone(to_phone)
    if not normalized:
        return {"sent": False, "error": "missing_phone"}

    resolved = _resolve_provider(tenant_id)
    provider = resolved["provider"]
    cfg = resolved["config"]

    try:
        if provider == "360dialog":
            api_key = _decrypt(cfg.get("encrypted_api_key"))
            if not api_key:
                return {"sent": False, "error": "decrypt_failed", "provider": "360dialog"}
            return await _send_360dialog(api_key=api_key, to=normalized, body=body)

        if provider == "meta_tenant":
            token = _decrypt(cfg.get("encrypted_access_token"))
            pid = cfg.get("phone_number_id")
            if not token or not pid:
                return {"sent": False, "error": "decrypt_failed", "provider": "meta"}
            return await _send_meta(access_token=token, phone_number_id=pid, to=normalized, body=body)

        if provider == "meta_global":
            token = os.getenv("WHATSAPP_ACCESS_TOKEN") or ""
            pid = os.getenv("WHATSAPP_PHONE_NUMBER_ID") or ""
            return await _send_meta(access_token=token, phone_number_id=pid, to=normalized, body=body)

        return {"sent": False, "error": "not_configured", "logged_only": True}
    except Exception as e:
        print(f"[whatsapp_dispatch] send exception: {e}")
        return {"sent": False, "error": str(e), "provider": provider}
