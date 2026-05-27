"""Iter108 — ACTION 2: Pre-save API-key validation for every integration.

A SINGLE endpoint that takes `{provider, api_key}` and verifies the key with
the provider's own API in real time — BEFORE the key ever touches MongoDB.

Why one endpoint instead of six? Each provider needs the exact same UX from
the React side: paste key → spinner → green/red. Folding all the variation
into one server function keeps the frontend dead simple (a single
`ApiKeyInput` component).

Costs of the test calls (per call, all bounded < 1¢):
  - Saleshandy : GET  /v1/sequences                 (free — list call)
  - Proxycurl  : GET  /api/v1/customer/listing      (free — NinjaPear auth probe)
  - Serper     : POST /search                       (consumes 1 search credit)
  - Apollo     : POST /v1/people/match              (consumes 1 enrichment credit)
  - 360dialog  : GET  /v1/configs                   (free meta endpoint)
  - Resend     : GET  /api-keys                     (free admin endpoint)
"""
from __future__ import annotations

import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, Optional, Tuple

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import get_current_user  # noqa: F401  (kept for symmetry; endpoint is auth'd)

router = APIRouter(tags=["iter108-key-validator"])

TIMEOUT = httpx.Timeout(8.0, connect=4.0)


class ValidateKeyPayload(BaseModel):
    provider: str
    api_key: str


def _short(s: Optional[str], n: int = 160) -> str:
    if not s:
        return ""
    return s.replace("\n", " ")[:n]


# ─── Per-provider validators ────────────────────────────────────────────────
async def _validate_saleshandy(key: str) -> Tuple[bool, str]:
    # Saleshandy returns 400 with body `{"type":"auth","message":"Invalid token"}`
    # for auth failures (not 401). See routes/outreach_import.py:91-104 for
    # the known-good pattern; reuse the same check here.
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(
                "https://open-api.saleshandy.com/v1/sequences",
                headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
            )
        body_low = (r.text or "").lower()
        is_auth_error = (
            r.status_code in (401, 403)
            or '"type":"auth"' in body_low
            or "invalid token" in body_low
            or "invalid api key" in body_low
        )
        if is_auth_error:
            return False, "Saleshandy rejected this key. Copy the FULL key from Saleshandy → Settings → API."
        if r.status_code == 200:
            return True, "Key valid — ready to connect."
        return False, f"Saleshandy returned HTTP {r.status_code}: {_short(r.text)}"
    except httpx.RequestError as e:
        return False, f"Could not reach Saleshandy: {_short(str(e))}"


async def _validate_proxycurl(key: str) -> Tuple[bool, str]:
    # Proxycurl was sunset in 2026 and replaced by NinjaPear (same Nubela team,
    # SAME API KEY — per the API_SUNSET message at /proxycurl/api/*).
    # NinjaPear's `/api/v1/customer/listing` returns 401 `{"error":"Invalid API Key"}`
    # for bad keys and 200 for valid ones — a clean auth check.
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(
                "https://nubela.co/api/v1/customer/listing",
                headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
            )
        if r.status_code == 200:
            return True, "Key valid — ready to connect (Proxycurl → NinjaPear migration)."
        if r.status_code in (401, 403):
            return False, "Proxycurl/NinjaPear rejected this key. Generate a new one at nubela.co → Account → API."
        if r.status_code in (400, 404, 422):
            # Endpoint reachable, key not rejected outright — treat as valid;
            # the real call will surface any remaining issues at enrichment time.
            return True, "Key valid — ready to connect."
        return False, f"Proxycurl/NinjaPear returned HTTP {r.status_code}: {_short(r.text)}"
    except httpx.RequestError as e:
        return False, f"Could not reach Proxycurl/NinjaPear: {_short(str(e))}"


async def _validate_serper(key: str) -> Tuple[bool, str]:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": key, "Content-Type": "application/json"},
                json={"q": "ping", "num": 1},
            )
        if r.status_code == 200:
            return True, "Key valid — ready to connect."
        if r.status_code in (401, 403):
            return False, "Serper rejected this key. Re-copy from serper.dev → API."
        return False, f"Serper returned HTTP {r.status_code}: {_short(r.text)}"
    except httpx.RequestError as e:
        return False, f"Could not reach Serper: {_short(str(e))}"


async def _validate_apollo(key: str) -> Tuple[bool, str]:
    # /v1/auth/health returns 200 even with garbage keys. Use the
    # email-finder enrichment endpoint which actually requires a real key.
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.post(
                "https://api.apollo.io/v1/people/match",
                headers={"x-api-key": key, "Content-Type": "application/json", "Accept": "application/json"},
                json={"first_name": "test", "last_name": "validator"},
            )
        if r.status_code in (200, 422):
            # 200 = match returned; 422 = parameters fine, key fine, no match.
            return True, "Key valid — ready to connect."
        if r.status_code in (401, 403):
            return False, "Apollo rejected this key. Re-copy from Apollo → Settings → API."
        return False, f"Apollo returned HTTP {r.status_code}: {_short(r.text)}"
    except httpx.RequestError as e:
        return False, f"Could not reach Apollo: {_short(str(e))}"


async def _validate_360dialog(key: str) -> Tuple[bool, str]:
    # 360dialog uses D360-API-KEY header; /v1/configs returns this key's profile.
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(
                "https://waba-v2.360dialog.io/v1/configs",
                headers={"D360-API-KEY": key, "Accept": "application/json"},
            )
        if r.status_code == 200:
            return True, "Key valid — ready to connect."
        if r.status_code in (401, 403):
            return False, "360dialog rejected this key. Confirm it's a Cloud API key (not legacy)."
        return False, f"360dialog returned HTTP {r.status_code}: {_short(r.text)}"
    except httpx.RequestError as e:
        return False, f"Could not reach 360dialog: {_short(str(e))}"


async def _validate_resend(key: str) -> Tuple[bool, str]:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(
                "https://api.resend.com/api-keys",
                headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
            )
        if r.status_code == 200:
            return True, "Key valid — ready to connect."
        if r.status_code in (400, 401, 403):
            return False, "Resend rejected this key. Re-copy from resend.com → API Keys."
        return False, f"Resend returned HTTP {r.status_code}: {_short(r.text)}"
    except httpx.RequestError as e:
        return False, f"Could not reach Resend: {_short(str(e))}"


VALIDATORS: Dict[str, callable] = {
    "saleshandy": _validate_saleshandy,
    "proxycurl":  _validate_proxycurl,
    "serper":     _validate_serper,
    "apollo":     _validate_apollo,
    "360dialog":  _validate_360dialog,
    "resend":     _validate_resend,
}


@router.post("/api/integrations/validate-key")
async def validate_api_key(
    payload: ValidateKeyPayload,
    current_user: dict = Depends(get_current_user),
):
    provider = (payload.provider or "").strip().lower()
    key = (payload.api_key or "").strip()
    if not key or len(key) < 8:
        result = {"valid": False, "message": "Key looks empty or too short."}
        _record_attempt(provider, current_user, result, key)
        return result
    validator = VALIDATORS.get(provider)
    if not validator:
        raise HTTPException(404, f"No validator for provider: {provider}. "
                                 f"Known: {sorted(VALIDATORS.keys())}")
    started = time.monotonic()
    valid, message = await validator(key)
    elapsed_ms = int((time.monotonic() - started) * 1000)
    result = {"valid": valid, "message": message, "provider": provider, "elapsed_ms": elapsed_ms}
    _record_attempt(provider, current_user, result, key)
    return result


# ─── Admin debug surface ────────────────────────────────────────────────────
# In-memory ring buffer of the last 50 validation attempts. Master-admin only.
# Keys are never recorded — we store the prefix + length + masked tail so the
# operator can correlate which paste failed without leaking the secret.
_HISTORY: Deque[Dict[str, Any]] = deque(maxlen=50)


def _mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:4]}…{key[-3:]} (len={len(key)})"


def _record_attempt(provider: str, user: dict, result: Dict[str, Any], key: str) -> None:
    _HISTORY.appendleft({
        "at": datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "valid": bool(result.get("valid")),
        "message": result.get("message", ""),
        "elapsed_ms": result.get("elapsed_ms"),
        "by_user_id": str(user.get("id") or user.get("_id") or ""),
        "by_user_email": user.get("email", ""),
        "key_masked": _mask_key(key),
    })


def _is_master_admin(user: dict) -> bool:
    return user.get("role") in ("master_admin", "owner")


@router.get("/api/integrations/validate-key/history")
async def validate_key_history(current_user: dict = Depends(get_current_user)):
    """Master-admin debug view of recent pre-validation attempts (last 50)."""
    if not _is_master_admin(current_user):
        raise HTTPException(403, "Master admin only.")
    return {"count": len(_HISTORY), "items": list(_HISTORY)}


@router.get("/api/integrations/validate-key/providers")
async def validate_key_providers(current_user: dict = Depends(get_current_user)):
    """Lightweight metadata so the frontend can render a complete provider list."""
    return {"providers": sorted(VALIDATORS.keys())}
