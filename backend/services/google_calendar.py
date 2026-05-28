"""Google OAuth + Calendar helpers (iter109c Batch 2).

Provides:
  • get_access_token(tenant_id) — returns a live access token (refreshes if expired)
  • create_calendar_event(tenant_id, ...) — creates a Google Calendar event with
    a Google Meet conferenceData link.
  • cancel_calendar_event(tenant_id, event_id)
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import httpx
from fastapi import HTTPException

from deps import db
from security.encryption import encrypt, decrypt

logger = logging.getLogger("google_calendar")

_configs_col = db["integration_configs"]
_token_cache: Dict[str, Dict[str, Any]] = {}  # tenant_id → {token, expires_at}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load(tenant_id: str) -> Dict[str, Any]:
    return _configs_col.find_one(
        {"tenant_id": tenant_id, "integration_type": "google"},
        {"_id": 0},
    ) or {}


async def _refresh_token(tenant_id: str, refresh_token: str, client_id: str, client_secret: str) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post("https://oauth2.googleapis.com/token", data={
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
        })
        if resp.status_code >= 400:
            raise HTTPException(401, f"Google refresh failed: {resp.text[:200]}")
        return resp.json()


async def get_access_token(tenant_id: str) -> str:
    """Return a live access token for this tenant's Google connection.
    Refreshes via refresh_token if expired/expiring soon. Caches in-process."""
    cached = _token_cache.get(tenant_id)
    if cached and cached["expires_at"] > time.time() + 30:
        return cached["token"]

    doc = _load(tenant_id)
    cfg = doc.get("config") or {}
    access = cfg.get("access_token")
    refresh = cfg.get("refresh_token")
    if not access:
        raise HTTPException(412, "Google not connected. Connect on /app/integrations first.")

    access_dec = decrypt(access)
    expires_in = cfg.get("expires_in") or 3600
    connected_at_iso = doc.get("connected_at")
    try:
        connected_at = datetime.fromisoformat(connected_at_iso.replace("Z", "+00:00")) if connected_at_iso else _now()
    except Exception:
        connected_at = _now()
    expires_at = connected_at.timestamp() + expires_in

    if expires_at > time.time() + 60:
        _token_cache[tenant_id] = {"token": access_dec, "expires_at": expires_at}
        return access_dec

    if not refresh:
        raise HTTPException(401, "Google token expired and no refresh_token stored. Reconnect.")
    tokens = await _refresh_token(
        tenant_id,
        decrypt(refresh),
        decrypt(cfg["client_id"]),
        decrypt(cfg["client_secret"]),
    )
    new_access = tokens.get("access_token")
    new_expires = tokens.get("expires_in") or 3600
    new_cfg = {**cfg, "access_token": encrypt(new_access), "expires_in": new_expires}
    _configs_col.update_one(
        {"tenant_id": tenant_id, "integration_type": "google"},
        {"$set": {"config": new_cfg, "connected_at": _now().isoformat(), "last_sync_at": _now().isoformat()}},
    )
    _token_cache[tenant_id] = {"token": new_access, "expires_at": time.time() + new_expires}
    return new_access


async def create_calendar_event(
    *, tenant_id: str, summary: str, description: str,
    start: datetime, end: datetime,
    attendee_email: Optional[str] = None,
    with_meet: bool = True,
    reminder_minutes: int = 60,
) -> Dict[str, Any]:
    """Create a primary-calendar event with optional Google Meet link.

    Returns: { event_id, html_link, meet_link, start, end }
    """
    token = await get_access_token(tenant_id)
    body: Dict[str, Any] = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": end.isoformat()},
        "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": reminder_minutes}]},
    }
    if attendee_email:
        body["attendees"] = [{"email": attendee_email}]
    if with_meet:
        body["conferenceData"] = {
            "createRequest": {
                "requestId": f"aria-{tenant_id}-{int(time.time())}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        }

    url = "https://www.googleapis.com/calendar/v3/calendars/primary/events?conferenceDataVersion=1&sendUpdates=all"
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(url, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, json=body)
        if resp.status_code >= 400:
            raise HTTPException(resp.status_code, f"Calendar API: {resp.text[:300]}")
        ev = resp.json()
    meet_link = None
    for entry in (ev.get("conferenceData", {}).get("entryPoints") or []):
        if entry.get("entryPointType") == "video":
            meet_link = entry.get("uri")
            break
    return {
        "event_id": ev.get("id"),
        "html_link": ev.get("htmlLink"),
        "meet_link": meet_link,
        "start": ev["start"]["dateTime"],
        "end": ev["end"]["dateTime"],
    }


async def cancel_calendar_event(*, tenant_id: str, event_id: str) -> bool:
    token = await get_access_token(tenant_id)
    url = f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{event_id}?sendUpdates=all"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.delete(url, headers={"Authorization": f"Bearer {token}"})
        return resp.status_code in (200, 204)
