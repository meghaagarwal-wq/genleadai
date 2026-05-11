"""Integration Hub — unified outbound + inbound third-party integrations.

Covers (Phase 7 of the master spec):
- Outbound analytics: GA4 (Measurement Protocol), Meta Conversions API
- Outbound automation: Zapier webhooks, Make.com webhooks
- Inbound lead sources: Typeform, Instantly.ai, Google Ads Lead Form, Apollo.io import

Pattern:
  - `integration_configs` — one doc per (tenant_id, integration_type)
  - `integration_events` — log of every fired event
  - `fire_lifecycle_event(tenant_id, event_type, lead)` — fan-out to all
    enabled integrations whenever a lead changes state.
"""
from __future__ import annotations
import asyncio
import hashlib
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional, List

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from deps import db, get_current_user
from routes.tenants import get_active_tenant

router = APIRouter(prefix="/api/integrations", tags=["integrations"])
public_router = APIRouter(prefix="/api/integrations", tags=["integrations-public"])

configs_col = db["integration_configs"]
events_col = db["integration_events"]
leads_col = db["leads"]
tenants_col = db["tenants"]

SUPPORTED_TYPES = {
    # Analytics (outbound)
    "ga4": {"category": "analytics", "label": "Google Analytics 4", "direction": "outbound"},
    "meta_capi": {"category": "analytics", "label": "Meta Conversions API", "direction": "outbound"},
    # Automation (outbound)
    "zapier": {"category": "automation", "label": "Zapier", "direction": "outbound"},
    "make": {"category": "automation", "label": "Make.com", "direction": "outbound"},
    # Lead sources (inbound)
    "typeform": {"category": "lead_source", "label": "Typeform", "direction": "inbound"},
    "instantly": {"category": "outreach", "label": "Instantly.ai", "direction": "inbound"},
    "google_ads": {"category": "lead_source", "label": "Google Ads Lead Form", "direction": "inbound"},
    "apollo": {"category": "lead_source", "label": "Apollo.io", "direction": "inbound"},
}

LIFECYCLE_EVENTS = [
    "lead.created", "lead.qualified", "lead.stage_changed",
    "meeting.booked", "lead.closed_won", "lead.closed_lost",
    "aria.paused", "aria.resumed", "sentiment.negative",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Config CRUD (tenant-side) ──────────────────────────────────────────────
class ConfigPayload(BaseModel):
    config: dict = Field(default_factory=dict)
    status: Optional[str] = "connected"


@router.get("/list")
async def list_integrations(tenant: dict = Depends(get_active_tenant)):
    """Return all supported integration types + connection status for this tenant."""
    docs = {d["integration_type"]: d for d in configs_col.find({"tenant_id": tenant["id"]}, {"_id": 0})}
    out = []
    for t, meta in SUPPORTED_TYPES.items():
        d = docs.get(t, {})
        out.append({
            "type": t,
            "label": meta["label"],
            "category": meta["category"],
            "direction": meta["direction"],
            "status": d.get("status", "not_connected"),
            "config": _mask_secrets(d.get("config", {})),
            "last_sync_at": d.get("last_sync_at"),
            "error_message": d.get("error_message"),
        })
    return {"integrations": out}


def _mask_secrets(cfg: dict) -> dict:
    """Mask secret-y fields so they don't leak when returned to UI."""
    masked = {}
    for k, v in (cfg or {}).items():
        if isinstance(v, str) and any(s in k.lower() for s in ("token", "secret", "key", "pixel", "access")):
            masked[k] = (v[:4] + "•" * 8 + v[-4:]) if len(v) >= 12 else "•" * 6
        else:
            masked[k] = v
    return masked


@router.post("/{integration_type}/connect")
async def connect(integration_type: str, payload: ConfigPayload, tenant: dict = Depends(get_active_tenant), current_user: dict = Depends(get_current_user)):
    if integration_type not in SUPPORTED_TYPES:
        raise HTTPException(status_code=404, detail=f"Unknown integration: {integration_type}")
    if tenant.get("_member_role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")

    # Merge new config into existing (so PATCHing one field doesn't wipe others)
    existing = configs_col.find_one({"tenant_id": tenant["id"], "integration_type": integration_type}, {"_id": 0}) or {}
    merged = {**(existing.get("config", {})), **(payload.config or {})}

    doc = {
        "tenant_id": tenant["id"],
        "integration_type": integration_type,
        "status": payload.status or "connected",
        "config": merged,
        "updated_at": _now(),
    }
    if not existing:
        doc["created_at"] = _now()
    configs_col.update_one(
        {"tenant_id": tenant["id"], "integration_type": integration_type},
        {"$set": doc},
        upsert=True,
    )
    return {"status": "ok", "integration": {**doc, "config": _mask_secrets(merged)}}


@router.delete("/{integration_type}/disconnect")
async def disconnect(integration_type: str, tenant: dict = Depends(get_active_tenant), current_user: dict = Depends(get_current_user)):
    if tenant.get("_member_role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")
    configs_col.delete_one({"tenant_id": tenant["id"], "integration_type": integration_type})
    return {"status": "ok"}


@router.post("/{integration_type}/test")
async def test_connection(integration_type: str, tenant: dict = Depends(get_active_tenant)):
    """Fire a test event for the given integration. Returns success/failure."""
    cfg = configs_col.find_one({"tenant_id": tenant["id"], "integration_type": integration_type}, {"_id": 0})
    if not cfg:
        raise HTTPException(status_code=404, detail="Not configured")
    test_lead = {
        "id": "test-lead-id",
        "first_name": "Test",
        "last_name": "Lead",
        "email": "test@aria.local",
        "phone": "+919999999999",
        "tenant_id": tenant["id"],
        "source_channel": "test",
    }
    ok, msg = await _dispatch(tenant["id"], integration_type, cfg.get("config", {}), "lead.created", test_lead, {"test": True})
    return {"ok": ok, "message": msg}


# ─── Outbound dispatcher ─────────────────────────────────────────────────────
async def _dispatch(tenant_id: str, kind: str, cfg: dict, event_type: str, lead: dict, extra: dict | None = None) -> tuple[bool, str]:
    """Fire one event to one integration. Returns (ok, message)."""
    extra = extra or {}
    try:
        if kind == "ga4":
            return await _fire_ga4(cfg, event_type, lead, extra)
        if kind == "meta_capi":
            return await _fire_meta_capi(cfg, event_type, lead, extra)
        if kind in ("zapier", "make"):
            return await _fire_generic_webhook(cfg, event_type, lead, extra)
        return False, f"No outbound handler for {kind}"
    except Exception as e:
        return False, str(e)[:200]


async def _fire_ga4(cfg: dict, event_type: str, lead: dict, extra: dict) -> tuple[bool, str]:
    measurement_id = cfg.get("measurement_id")
    api_secret = cfg.get("api_secret")
    if not measurement_id or not api_secret:
        return False, "Missing measurement_id or api_secret"
    client_id = hashlib.sha256((lead.get("id") or lead.get("email") or lead.get("phone") or "anon").encode()).hexdigest()[:16]
    # Map event names to GA4-friendly snake_case
    name_map = {
        "lead.created": "aria_lead_created",
        "lead.qualified": "aria_lead_qualified",
        "meeting.booked": "aria_meeting_booked",
        "lead.closed_won": "aria_deal_closed_won",
        "lead.closed_lost": "aria_deal_closed_lost",
    }
    name = name_map.get(event_type, f"aria_{event_type.replace('.', '_')}")
    payload = {
        "client_id": client_id,
        "events": [{
            "name": name,
            "params": {
                "lead_id": lead.get("id"),
                "source": lead.get("source_channel") or lead.get("source_type") or "manual",
                "engagement_time_msec": 100,
            },
        }],
    }
    url = f"https://www.google-analytics.com/mp/collect?measurement_id={measurement_id}&api_secret={api_secret}"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, json=payload)
    if r.status_code in (200, 204):
        return True, "GA4 event sent"
    return False, f"GA4 {r.status_code}: {r.text[:80]}"


async def _fire_meta_capi(cfg: dict, event_type: str, lead: dict, extra: dict) -> tuple[bool, str]:
    pixel_id = cfg.get("pixel_id")
    access_token = cfg.get("access_token")
    if not pixel_id or not access_token:
        return False, "Missing pixel_id or access_token"
    name_map = {
        "lead.created": "Lead",
        "lead.qualified": "CompleteRegistration",
        "meeting.booked": "Schedule",
        "lead.closed_won": "Purchase",
    }
    name = name_map.get(event_type, "Lead")
    # Hash user data per Meta requirements
    def _h(s: str) -> str:
        return hashlib.sha256(s.strip().lower().encode()).hexdigest()
    user_data: dict[str, Any] = {}
    if lead.get("email"):
        user_data["em"] = [_h(str(lead["email"]))]
    if lead.get("phone"):
        user_data["ph"] = [_h(str(lead["phone"]).replace("+", "").replace(" ", ""))]
    if lead.get("first_name"):
        user_data["fn"] = [_h(str(lead["first_name"]))]
    if lead.get("last_name"):
        user_data["ln"] = [_h(str(lead["last_name"]))]

    payload = {
        "data": [{
            "event_name": name,
            "event_time": int(time.time()),
            "event_id": f"{lead.get('id', uuid.uuid4().hex)}-{event_type}",
            "action_source": "system_generated",
            "user_data": user_data,
            "custom_data": {"lead_source": lead.get("source_channel") or "aria"},
        }],
        "access_token": access_token,
    }
    if extra.get("test"):
        payload["test_event_code"] = cfg.get("test_event_code") or "TEST12345"

    url = f"https://graph.facebook.com/v18.0/{pixel_id}/events"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, json=payload)
    if r.status_code == 200:
        return True, "Meta CAPI event sent"
    return False, f"Meta {r.status_code}: {r.text[:120]}"


async def _fire_generic_webhook(cfg: dict, event_type: str, lead: dict, extra: dict) -> tuple[bool, str]:
    url = cfg.get("webhook_url")
    if not url:
        return False, "Missing webhook_url"
    body = {
        "event_type": event_type,
        "fired_at": _now(),
        "lead": {
            "id": lead.get("id"),
            "first_name": lead.get("first_name"),
            "last_name": lead.get("last_name"),
            "email": lead.get("email"),
            "phone": lead.get("phone"),
            "company_name": lead.get("company_name"),
            "icp_score": lead.get("icp_score"),
            "icp_tier": lead.get("icp_tier"),
            "status": lead.get("status"),
            "source_channel": lead.get("source_channel"),
            "tenant_id": lead.get("tenant_id"),
        },
        "extra": extra,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, json=body)
    if 200 <= r.status_code < 300:
        return True, f"Webhook OK ({r.status_code})"
    return False, f"Webhook {r.status_code}: {r.text[:120]}"


# ─── Lifecycle fire — fan-out (called from server.py / route handlers) ───────
def fire_lifecycle_event(tenant_id: str, event_type: str, lead: dict, extra: dict | None = None) -> None:
    """Fire an Aria lifecycle event to every enabled outbound integration for this tenant.

    Non-blocking: schedules an async task. Safe to call from sync handlers.
    """
    try:
        configs = list(configs_col.find({"tenant_id": tenant_id, "status": "connected"}, {"_id": 0}))
        outbound = [c for c in configs if SUPPORTED_TYPES.get(c["integration_type"], {}).get("direction") == "outbound"]
        if not outbound:
            return
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_fan_out(tenant_id, outbound, event_type, lead, extra))
        except RuntimeError:
            # No running loop (called from sync ctx outside FastAPI) — fire sync via asyncio.run
            asyncio.run(_fan_out(tenant_id, outbound, event_type, lead, extra))
    except Exception:
        # Never break the caller
        return


async def _fan_out(tenant_id: str, configs: List[dict], event_type: str, lead: dict, extra: dict | None) -> None:
    for c in configs:
        kind = c["integration_type"]
        ok, msg = await _dispatch(tenant_id, kind, c.get("config", {}), event_type, lead, extra)
        events_col.insert_one({
            "id": uuid.uuid4().hex,
            "tenant_id": tenant_id,
            "integration_type": kind,
            "direction": "outbound",
            "event_type": event_type,
            "lead_id": lead.get("id"),
            "raw_payload": extra or {},
            "processed": ok,
            "error": None if ok else msg[:300],
            "created_at": _now(),
        })
        if ok:
            configs_col.update_one(
                {"tenant_id": tenant_id, "integration_type": kind},
                {"$set": {"last_sync_at": _now(), "error_message": None}},
            )
        else:
            configs_col.update_one(
                {"tenant_id": tenant_id, "integration_type": kind},
                {"$set": {"error_message": msg[:300]}},
            )


# ─── Events log + retry ──────────────────────────────────────────────────────
@router.get("/events")
async def list_events(limit: int = 100, tenant: dict = Depends(get_active_tenant)):
    cur = events_col.find({"tenant_id": tenant["id"]}, {"_id": 0}).sort("created_at", -1).limit(int(limit))
    return {"events": list(cur)}


@router.post("/events/{event_id}/retry")
async def retry_event(event_id: str, tenant: dict = Depends(get_active_tenant), current_user: dict = Depends(get_current_user)):
    ev = events_col.find_one({"id": event_id, "tenant_id": tenant["id"]}, {"_id": 0})
    if not ev:
        raise HTTPException(status_code=404, detail="Not found")
    cfg = configs_col.find_one({"tenant_id": tenant["id"], "integration_type": ev["integration_type"]}, {"_id": 0})
    if not cfg:
        raise HTTPException(status_code=400, detail="Integration no longer configured")
    lead = leads_col.find_one({"id": ev.get("lead_id"), "tenant_id": tenant["id"]}, {"_id": 0}) or {"id": ev.get("lead_id"), "tenant_id": tenant["id"]}
    ok, msg = await _dispatch(tenant["id"], ev["integration_type"], cfg.get("config", {}), ev["event_type"], lead, ev.get("raw_payload"))
    events_col.update_one({"id": event_id}, {"$set": {"processed": ok, "error": None if ok else msg, "retried_at": _now()}})
    return {"ok": ok, "message": msg}


# ─── Inbound webhooks (PUBLIC — no auth, signed via tenant_id in URL) ────────
async def _normalize_and_capture(tenant_id: str, raw: dict, source: str, request: Request) -> dict:
    """Common inbound path — normalize raw payload + route through existing capture."""
    from routes.lead_capture import CapturePayload, capture_lead
    payload = CapturePayload(
        tenant_id=tenant_id,
        first_name=raw.get("first_name") or raw.get("name") or raw.get("firstName") or "Lead",
        last_name=raw.get("last_name") or raw.get("lastName") or "",
        email=raw.get("email") if raw.get("email") else None,
        phone=raw.get("phone") or raw.get("phone_number") or raw.get("mobile") or "",
        company=raw.get("company") or raw.get("company_name") or "",
        message=raw.get("message") or raw.get("notes") or raw.get("comments") or "",
        consent=bool(raw.get("consent", True)),  # inbound webhooks assume consent
        utm_source=raw.get("utm_source"),
        utm_campaign=raw.get("utm_campaign"),
        utm_medium=raw.get("utm_medium"),
        source_detail=source,
    )
    try:
        res = await capture_lead(payload, request)
    except Exception as e:
        events_col.insert_one({
            "id": uuid.uuid4().hex, "tenant_id": tenant_id, "integration_type": source,
            "direction": "inbound", "event_type": "lead.received", "raw_payload": raw,
            "processed": False, "error": str(e)[:300], "created_at": _now(),
        })
        raise
    events_col.insert_one({
        "id": uuid.uuid4().hex, "tenant_id": tenant_id, "integration_type": source,
        "direction": "inbound", "event_type": "lead.received", "raw_payload": raw,
        "lead_id": res.get("lead_id"), "processed": True, "error": None, "created_at": _now(),
    })
    return res


@public_router.post("/typeform/webhook/{tenant_id}")
async def typeform_webhook(tenant_id: str, request: Request):
    body = await request.json()
    answers = (body.get("form_response", {}) or {}).get("answers", []) or []
    raw: dict = {"utm_source": "typeform"}
    for a in answers:
        t = a.get("type")
        ref = (a.get("field", {}) or {}).get("ref", "")
        val = a.get(t)
        if not val:
            continue
        if t == "email":
            raw["email"] = val
        elif t == "phone_number":
            raw["phone"] = val
        elif t == "short_text" and ref in ("first_name", "name"):
            raw["first_name"] = val
        elif t == "short_text" and ref in ("last_name",):
            raw["last_name"] = val
        elif t == "long_text":
            raw["message"] = val
        elif t == "short_text" and ref == "company":
            raw["company"] = val
    return await _normalize_and_capture(tenant_id, raw, "typeform", request)


@public_router.post("/instantly/webhook/{tenant_id}")
async def instantly_webhook(tenant_id: str, request: Request):
    body = await request.json()
    raw = {
        "first_name": body.get("firstName") or body.get("first_name"),
        "last_name": body.get("lastName") or body.get("last_name"),
        "email": body.get("email") or body.get("lead_email"),
        "company": body.get("companyName") or body.get("company"),
        "message": f"Replied via Instantly · campaign: {body.get('campaign_name', body.get('campaignName', '—'))}",
        "utm_source": "instantly",
    }
    return await _normalize_and_capture(tenant_id, raw, "instantly", request)


@public_router.post("/google-ads/webhook/{tenant_id}")
async def google_ads_webhook(tenant_id: str, request: Request):
    body = await request.json()
    # Google Ads sends user_column_data — try to normalise common shapes
    cols = {c.get("column_id", c.get("column_name", "")).lower(): c.get("string_value") for c in (body.get("user_column_data") or [])} if isinstance(body.get("user_column_data"), list) else {}
    raw = {
        "first_name": cols.get("first_name") or body.get("first_name"),
        "last_name": cols.get("last_name") or body.get("last_name"),
        "email": cols.get("email") or body.get("email"),
        "phone": cols.get("phone_number") or cols.get("phone") or body.get("phone_number"),
        "company": cols.get("company_name") or body.get("company"),
        "message": "Google Ads Lead Form submission",
        "utm_source": "google_ads",
        "utm_campaign": body.get("campaign_id") or cols.get("campaign_id"),
    }
    return await _normalize_and_capture(tenant_id, raw, "google_ads", request)


class ApolloImport(BaseModel):
    tenant_id: str
    leads: list  # list of {first_name,last_name,email,phone,company}


@router.post("/apollo/import")
async def apollo_import(payload: ApolloImport, tenant: dict = Depends(get_active_tenant), request: Request = None):
    """Manual Apollo.io bulk import — accepts pre-pulled leads list. Owner/admin only."""
    if tenant.get("_member_role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")
    imported = 0
    deduped = 0
    failed = 0
    for raw in payload.leads:
        raw = {**raw, "utm_source": "apollo"}
        try:
            res = await _normalize_and_capture(tenant["id"], raw, "apollo", request)
            if res.get("deduplicated"):
                deduped += 1
            else:
                imported += 1
        except Exception:
            failed += 1
    return {"imported": imported, "deduplicated": deduped, "failed": failed, "total": len(payload.leads)}
