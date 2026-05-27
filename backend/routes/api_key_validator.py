"""Iter108 — ACTION 2: Pre-save API-key validation for every integration.

A SINGLE endpoint that takes `{provider, api_key}` and verifies the key with
the provider's own API in real time — BEFORE the key ever touches MongoDB.

Why one endpoint instead of six? Each provider needs the exact same UX from
the React side: paste key → spinner → green/red. Folding all the variation
into one server function keeps the frontend dead simple (a single
`ApiKeyInput` component).

Costs of the test calls (per call, all bounded < 1¢):
  - Saleshandy : GET  /v1/team-members            (free, scoped to API key)
  - Proxycurl  : GET  /proxycurl/api/v2/linkedin?url=...  (consumes 1 credit)
  - Serper     : POST /search                     (consumes 1 search credit)
  - Apollo     : GET  /v1/auth/health             (free)
  - 360dialog  : GET  /v1/configs                 (free meta endpoint)
  - Resend     : GET  /api-keys                   (free admin endpoint)
"""
from __future__ import annotations

import httpx
from typing import Dict, Optional, Tuple
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
    # Try multiple endpoints since Proxycurl has been sunsetting v2 paths.
    # 200 / 400 / 404 = key accepted; 401 / 403 = key rejected;
    # 410 = endpoint sunset (cannot verify, allow save with caveat).
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(
                "https://nubela.co/proxycurl/api/v2/linkedin",
                params={"url": "https://www.linkedin.com/in/proxycurl-validator/"},
                headers={"Authorization": f"Bearer {key}"},
            )
        if r.status_code in (200, 400, 404):
            return True, "Key valid — ready to connect."
        if r.status_code in (401, 403):
            return False, "Proxycurl rejected this key. Generate a new one at nubela.co → Account → API."
        if r.status_code == 410:
            # Proxycurl deprecated this endpoint — cannot validate, but save
            # anyway since we'll re-verify on the next enrichment call.
            return True, "Saved (Proxycurl couldn't pre-verify — endpoint changed; will validate on next scan)."
        return False, f"Proxycurl returned HTTP {r.status_code}: {_short(r.text)}"
    except httpx.RequestError as e:
        return False, f"Could not reach Proxycurl: {_short(str(e))}"


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
        return {"valid": False, "message": "Key looks empty or too short."}
    validator = VALIDATORS.get(provider)
    if not validator:
        raise HTTPException(404, f"No validator for provider: {provider}. "
                                 f"Known: {sorted(VALIDATORS.keys())}")
    valid, message = await validator(key)
    return {"valid": valid, "message": message, "provider": provider}
