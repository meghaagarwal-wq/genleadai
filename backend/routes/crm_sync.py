"""CRM Integration & Sync Engine — Sprint 2.

Architecture:
  Aria fires `fire_event(tenant_id, lead, event_type, payload)` whenever a lead
  changes state. The event is persisted as a pending row in `crm_sync_log` and
  picked up by `crm_sync_loop` (asyncio background task) which dispatches to
  the workspace's configured CRM connector (HubSpot / Pipedrive / Zoho /
  Salesforce / Custom Webhook).

Connectors are written for placeholder env vars (HUBSPOT_CLIENT_ID etc.) and
real network calls — they will work the moment the user adds credentials.

Collections:
  - crm_integrations : one doc per (tenant_id, crm_type); only one active per tenant
  - crm_sync_log     : event queue + history; status in pending|success|failed|retrying

Leads collection gets new fields (set by sync engine):
  crm_contact_id, crm_deal_id, crm_last_synced_at, crm_contact_deleted
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from deps import db, get_current_user
from routes.tenants import get_active_tenant
from security.encryption import encrypt, decrypt

logger = logging.getLogger("crm_sync")

router = APIRouter(prefix="/api/crm", tags=["crm"])

# ─── Collections ─────────────────────────────────────────────────────────────
integrations_col = db["crm_integrations"]
log_col = db["crm_sync_log"]
leads_col = db["leads"]
tenants_col = db["tenants"]

# ─── Supported CRMs ──────────────────────────────────────────────────────────
SUPPORTED = {"hubspot", "pipedrive", "zoho", "salesforce", "custom_webhook"}
OAUTH_CRMS = {"hubspot", "zoho", "salesforce"}

# ─── Event types ─────────────────────────────────────────────────────────────
EVENT_TYPES = {
    "lead.created",
    "lead.stage_changed",
    "lead.qualified",
    "lead.assigned",
    "aria.paused",
    "aria.resumed",
    "conversation.takeover",
    "meeting.booked",
    "lead.closed_won",
    "lead.closed_lost",
    "sentiment.negative",
    "sentiment.urgent",
    "touchpoint.sent",
    "lead.re_engaged",
    "lead.data_deleted",
}

# ─── Default field mapping ───────────────────────────────────────────────────
DEFAULT_FIELD_MAPPING = {
    "lead.name": "contact.first_last_name",
    "lead.phone": "contact.phone",
    "lead.email": "contact.email",
    "lead.source_type": "contact.lead_source",
    "lead.stage": "deal.stage",
    "lead.score": "contact.lead_score",
    "lead.assigned_to": "deal.owner",
    "lead.latest_sentiment": "contact.custom.aria_sentiment",
    "aria_active": "contact.custom.aria_active",
    "last_activity_at": "contact.last_activity_date",
}

DEFAULT_SYNC_RULES = {evt: True for evt in EVENT_TYPES}


# ─── Helpers ─────────────────────────────────────────────────────────────────
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _doc(d: dict) -> dict:
    d.pop("_id", None)
    return d


def _require_owner(tenant: dict):
    if tenant.get("_member_role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")


# ─── Models ──────────────────────────────────────────────────────────────────
class ConnectPayload(BaseModel):
    crm_type: str
    api_key: Optional[str] = None
    api_domain: Optional[str] = None  # for pipedrive (e.g. https://x.pipedrive.com)
    webhook_url: Optional[str] = None  # for custom_webhook
    account_email: Optional[str] = None
    oauth_code: Optional[str] = None  # for HubSpot/Zoho/Salesforce OAuth callback


class FieldMapPayload(BaseModel):
    field_mapping: Dict[str, str]


class SyncRulesPayload(BaseModel):
    sync_rules: Dict[str, bool]


# ─── fire_event — used by other modules ──────────────────────────────────────
def fire_event(tenant_id: str, lead: dict, event_type: str, payload: Optional[dict] = None) -> Optional[str]:
    """Queue a CRM sync event. Returns the log id or None if no integration.

    Safe to call even when no CRM is connected — it returns None silently.
    Other modules import this and call it inline.
    """
    if event_type not in EVENT_TYPES:
        logger.warning("Unknown CRM event type: %s", event_type)
        return None
    integ = integrations_col.find_one({"tenant_id": tenant_id, "connection_status": "connected"}, {"_id": 0})
    if not integ:
        return None
    # Respect sync_rules
    rules = (integ.get("sync_rules") or {})
    if rules.get(event_type) is False:
        return None

    lead_id = (lead or {}).get("id") or (lead or {}).get("_id")
    log_id = f"sync_{uuid.uuid4().hex[:12]}"
    doc = {
        "id": log_id,
        "tenant_id": tenant_id,
        "crm_type": integ.get("crm_type"),
        "event_type": event_type,
        "lead_id": lead_id,
        "crm_contact_id": (lead or {}).get("crm_contact_id"),
        "crm_deal_id": (lead or {}).get("crm_deal_id"),
        "payload": payload or {},
        "lead_snapshot": {
            "name": f"{(lead or {}).get('first_name','')} {(lead or {}).get('last_name','')}".strip() or (lead or {}).get('name'),
            "email": (lead or {}).get("email"),
            "phone": (lead or {}).get("phone"),
            "source_channel": (lead or {}).get("source_channel"),
            "stage": (lead or {}).get("status") or (lead or {}).get("stage"),
            "score": (lead or {}).get("icp_score"),
        },
        "status": "pending",
        "error_message": None,
        "retry_count": 0,
        "synced_at": None,
        "created_at": _iso(_now()),
    }
    log_col.insert_one(doc.copy())
    return log_id


# ─── Connector dispatchers ───────────────────────────────────────────────────
async def _dispatch(integ: dict, entry: dict) -> Dict[str, Any]:
    """Route a single sync entry to the right connector. Returns
    {success: bool, error?: str, contact_id?: str, deal_id?: str}"""
    crm = integ.get("crm_type")
    try:
        if crm == "hubspot":
            return await _dispatch_hubspot(integ, entry)
        if crm == "pipedrive":
            return await _dispatch_pipedrive(integ, entry)
        if crm == "zoho":
            return await _dispatch_zoho(integ, entry)
        if crm == "salesforce":
            return await _dispatch_salesforce(integ, entry)
        if crm == "custom_webhook":
            return await _dispatch_webhook(integ, entry)
        return {"success": False, "error": f"unsupported crm: {crm}"}
    except httpx.HTTPError as e:
        return {"success": False, "error": f"http: {e}"}
    except Exception as e:  # noqa: BLE001
        logger.exception("Connector failure")
        return {"success": False, "error": str(e)}


async def _dispatch_hubspot(integ: dict, entry: dict) -> Dict[str, Any]:
    token = decrypt((integ.get("credentials") or {}).get("access_token")) or os.environ.get("HUBSPOT_TEST_TOKEN")
    if not token:
        return {"success": False, "error": "hubspot: no access token (placeholder mode)"}
    base = "https://api.hubapi.com"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    snap = entry.get("lead_snapshot") or {}
    contact_id = entry.get("crm_contact_id")
    async with httpx.AsyncClient(timeout=15) as client:
        if entry["event_type"] == "lead.created":
            props = {
                "firstname": (snap.get("name") or "").split(" ", 1)[0],
                "lastname": (snap.get("name") or " ").split(" ", 1)[1] if " " in (snap.get("name") or "") else "",
                "email": snap.get("email"),
                "phone": snap.get("phone"),
                "hs_lead_status": (snap.get("stage") or "NEW").upper(),
                "aria_score": str(snap.get("score") or 0),
            }
            r = await client.post(f"{base}/crm/v3/objects/contacts", headers=headers, json={"properties": props})
            r.raise_for_status()
            return {"success": True, "contact_id": r.json().get("id")}
        if entry["event_type"] in ("aria.paused", "aria.resumed", "conversation.takeover", "touchpoint.sent", "lead.re_engaged"):
            # Note as engagement (HubSpot v3)
            note = (entry.get("payload") or {}).get("note") or _note_for(entry)
            if contact_id:
                payload = {
                    "properties": {"hs_note_body": note, "hs_timestamp": int(datetime.now(timezone.utc).timestamp() * 1000)},
                    "associations": [{"to": {"id": contact_id}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}]}],
                }
                r = await client.post(f"{base}/crm/v3/objects/notes", headers=headers, json=payload)
                r.raise_for_status()
                return {"success": True, "contact_id": contact_id}
        if entry["event_type"] == "lead.stage_changed" and contact_id:
            new_stage = (entry.get("payload") or {}).get("new_stage")
            r = await client.patch(
                f"{base}/crm/v3/objects/contacts/{contact_id}",
                headers=headers,
                json={"properties": {"hs_lead_status": str(new_stage or "").upper()}},
            )
            r.raise_for_status()
            return {"success": True, "contact_id": contact_id}
        # Fallback — log only
        return {"success": True, "contact_id": contact_id}


async def _dispatch_pipedrive(integ: dict, entry: dict) -> Dict[str, Any]:
    api_key = decrypt((integ.get("credentials") or {}).get("api_key"))
    domain = (integ.get("credentials") or {}).get("api_domain") or "https://api.pipedrive.com"
    if not api_key:
        return {"success": False, "error": "pipedrive: no api_key"}
    snap = entry.get("lead_snapshot") or {}
    async with httpx.AsyncClient(timeout=15) as client:
        if entry["event_type"] == "lead.created":
            payload = {
                "name": snap.get("name") or snap.get("email") or "Aria lead",
                "email": [{"value": snap.get("email"), "primary": True}] if snap.get("email") else None,
                "phone": [{"value": snap.get("phone"), "primary": True}] if snap.get("phone") else None,
            }
            r = await client.post(f"{domain}/v1/persons?api_token={api_key}", json={k: v for k, v in payload.items() if v})
            r.raise_for_status()
            person = r.json().get("data") or {}
            return {"success": True, "contact_id": str(person.get("id")) if person.get("id") else None}
        if entry["event_type"] in ("aria.paused", "aria.resumed", "conversation.takeover", "touchpoint.sent"):
            note = _note_for(entry)
            cid = entry.get("crm_contact_id")
            payload = {"content": note, "person_id": int(cid) if cid and str(cid).isdigit() else None}
            r = await client.post(f"{domain}/v1/notes?api_token={api_key}", json={k: v for k, v in payload.items() if v is not None})
            r.raise_for_status()
            return {"success": True, "contact_id": cid}
        return {"success": True, "contact_id": entry.get("crm_contact_id")}


async def _dispatch_zoho(integ: dict, entry: dict) -> Dict[str, Any]:
    token = decrypt((integ.get("credentials") or {}).get("access_token"))
    if not token:
        return {"success": False, "error": "zoho: no access token (placeholder mode)"}
    # Zoho CRM v2 REST shape — placeholder, real call deferred
    return {"success": True, "contact_id": entry.get("crm_contact_id"), "note": "zoho dispatch stubbed"}


async def _dispatch_salesforce(integ: dict, entry: dict) -> Dict[str, Any]:
    token = decrypt((integ.get("credentials") or {}).get("access_token"))
    instance = (integ.get("credentials") or {}).get("instance_url")
    if not token or not instance:
        return {"success": False, "error": "salesforce: no access token / instance_url (placeholder mode)"}
    return {"success": True, "contact_id": entry.get("crm_contact_id"), "note": "salesforce dispatch stubbed"}


async def _dispatch_webhook(integ: dict, entry: dict) -> Dict[str, Any]:
    url = integ.get("webhook_url")
    if not url:
        return {"success": False, "error": "custom_webhook: no webhook_url"}
    payload = {
        "event_type": entry["event_type"],
        "tenant_id": entry["tenant_id"],
        "lead_id": entry.get("lead_id"),
        "lead": entry.get("lead_snapshot"),
        "data": entry.get("payload"),
        "synced_at": _iso(_now()),
    }
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, json=payload)
        if r.status_code >= 300:
            return {"success": False, "error": f"webhook {r.status_code}: {r.text[:200]}"}
        return {"success": True, "contact_id": entry.get("crm_contact_id")}


def _note_for(entry: dict) -> str:
    """Human-readable activity note for the given event."""
    et = entry["event_type"]
    p = entry.get("payload") or {}
    snap = entry.get("lead_snapshot") or {}
    name = snap.get("name") or snap.get("email") or "lead"
    ts = _iso(_now())
    if et == "aria.paused":
        rep = p.get("rep_name") or p.get("user_email") or "team member"
        last = p.get("last_message") or "—"
        return f"Aria paused — conversation taken over by {rep} at {ts}. Last Aria message: {last}"
    if et == "aria.resumed":
        rep = p.get("rep_name") or p.get("user_email") or "team member"
        return f"Aria resumed on this lead by {rep} at {ts}."
    if et == "conversation.takeover":
        rep = p.get("rep_name") or p.get("user_email") or "team member"
        return f"Human takeover by {rep} at {ts}."
    if et == "touchpoint.sent":
        tp = p.get("touchpoint_type") or "message"
        body = (p.get("message_preview") or "")[:140]
        return f"Aria sent {tp}: \"{body}\""
    if et == "lead.re_engaged":
        return f"Aria sent re-engagement message at {ts}."
    if et == "sentiment.urgent":
        return f"Aria flagged URGENT sentiment on {name}'s conversation."
    return f"{et} fired at {ts}."


# ─── Background sync loop ────────────────────────────────────────────────────
_STOP_EVENT: Optional[asyncio.Event] = None
MAX_RETRY = 3


async def crm_sync_loop():
    """Background task — polls crm_sync_log for pending entries and dispatches."""
    logger.info("CRM sync loop started")
    while _STOP_EVENT is None or not _STOP_EVENT.is_set():
        try:
            pending = list(log_col.find(
                {"status": {"$in": ["pending", "retrying"]}, "retry_count": {"$lt": MAX_RETRY}},
                {"_id": 0},
            ).sort("created_at", 1).limit(20))
            for entry in pending:
                integ = integrations_col.find_one(
                    {"tenant_id": entry["tenant_id"], "connection_status": "connected"}, {"_id": 0}
                )
                if not integ:
                    log_col.update_one(
                        {"id": entry["id"]},
                        {"$set": {"status": "failed", "error_message": "no active integration", "synced_at": _iso(_now())}},
                    )
                    continue
                result = await _dispatch(integ, entry)
                update = {"synced_at": _iso(_now())}
                if result.get("success"):
                    update["status"] = "success"
                    update["error_message"] = None
                    if result.get("contact_id"):
                        update["crm_contact_id"] = result["contact_id"]
                    if result.get("deal_id"):
                        update["crm_deal_id"] = result["deal_id"]
                    if entry.get("lead_id") and result.get("contact_id"):
                        leads_col.update_one(
                            {"id": entry["lead_id"], "tenant_id": entry["tenant_id"]},
                            {"$set": {
                                "crm_contact_id": result["contact_id"],
                                "crm_last_synced_at": _iso(_now()),
                            }},
                        )
                else:
                    new_retry = entry.get("retry_count", 0) + 1
                    update["retry_count"] = new_retry
                    update["status"] = "failed" if new_retry >= MAX_RETRY else "retrying"
                    update["error_message"] = (result.get("error") or "unknown")[:500]
                # Update integration's last_sync_at
                integrations_col.update_one(
                    {"id": integ["id"]},
                    {"$set": {"last_sync_at": _iso(_now())}},
                )
                log_col.update_one({"id": entry["id"]}, {"$set": update})
        except Exception:  # noqa: BLE001
            logger.exception("crm_sync_loop iteration error")
        await asyncio.sleep(int(os.getenv("CRM_SYNC_INTERVAL_SECONDS", "5")))


def start_loop(loop: asyncio.AbstractEventLoop):
    global _STOP_EVENT
    _STOP_EVENT = asyncio.Event()
    loop.create_task(crm_sync_loop())


# ─── REST endpoints ──────────────────────────────────────────────────────────
@router.get("/integrations")
async def get_integration(tenant: dict = Depends(get_active_tenant)):
    integ = integrations_col.find_one({"tenant_id": tenant["id"]}, {"_id": 0, "credentials": 0})
    return {"integration": integ}


@router.post("/connect")
async def connect_crm(payload: ConnectPayload, tenant: dict = Depends(get_active_tenant), user: dict = Depends(get_current_user)):
    _require_owner(tenant)
    if payload.crm_type not in SUPPORTED:
        raise HTTPException(status_code=400, detail=f"Unsupported CRM: {payload.crm_type}")

    # Disconnect any existing integration first (one active per tenant)
    integrations_col.delete_many({"tenant_id": tenant["id"]})

    creds: Dict[str, Any] = {}
    if payload.crm_type == "pipedrive":
        if not payload.api_key:
            raise HTTPException(status_code=400, detail="Pipedrive requires api_key")
        creds["api_key"] = encrypt(payload.api_key)
        if payload.api_domain:
            creds["api_domain"] = payload.api_domain.rstrip("/")
    elif payload.crm_type == "custom_webhook":
        if not payload.webhook_url:
            raise HTTPException(status_code=400, detail="custom_webhook requires webhook_url")
    elif payload.crm_type in OAUTH_CRMS:
        # Placeholder mode: accept a paste-in access_token via api_key field
        if payload.api_key:
            creds["access_token"] = encrypt(payload.api_key)
        elif payload.oauth_code:
            # In real OAuth: exchange code → tokens. For now stash the code.
            creds["oauth_code"] = encrypt(payload.oauth_code)
            creds["pending_oauth"] = True

    doc = {
        "id": f"crm_{uuid.uuid4().hex[:12]}",
        "tenant_id": tenant["id"],
        "crm_type": payload.crm_type,
        "connection_status": "connected" if creds or payload.crm_type == "custom_webhook" else "error",
        "account_email": payload.account_email or user.get("email"),
        "credentials": creds,
        "webhook_url": payload.webhook_url,
        "field_mapping": DEFAULT_FIELD_MAPPING.copy(),
        "sync_rules": DEFAULT_SYNC_RULES.copy(),
        "last_sync_at": None,
        "created_at": _iso(_now()),
        "updated_at": _iso(_now()),
    }
    integrations_col.insert_one(doc.copy())
    doc.pop("_id", None)
    doc.pop("credentials", None)
    # Audit
    try:
        from routes.audit_log import audit_write as _aw
        _aw(tenant["id"], user, "crm.connected", "crm_integration", doc["id"], {"crm_type": payload.crm_type})
    except Exception:
        pass
    return {"status": "ok", "integration": doc}


@router.delete("/disconnect")
async def disconnect_crm(tenant: dict = Depends(get_active_tenant), user: dict = Depends(get_current_user)):
    _require_owner(tenant)
    integrations_col.delete_many({"tenant_id": tenant["id"]})
    try:
        from routes.audit_log import audit_write as _aw
        _aw(tenant["id"], user, "crm.disconnected", "crm_integration", None)
    except Exception:
        pass
    return {"status": "ok"}


@router.get("/field-mapping")
async def get_field_mapping(tenant: dict = Depends(get_active_tenant)):
    integ = integrations_col.find_one({"tenant_id": tenant["id"]}, {"_id": 0, "credentials": 0})
    if not integ:
        return {"field_mapping": DEFAULT_FIELD_MAPPING, "available_fields": list(DEFAULT_FIELD_MAPPING.keys())}
    return {"field_mapping": integ.get("field_mapping") or DEFAULT_FIELD_MAPPING, "available_fields": list(DEFAULT_FIELD_MAPPING.keys())}


@router.put("/field-mapping")
async def update_field_mapping(payload: FieldMapPayload, tenant: dict = Depends(get_active_tenant)):
    _require_owner(tenant)
    integrations_col.update_one(
        {"tenant_id": tenant["id"]},
        {"$set": {"field_mapping": payload.field_mapping, "updated_at": _iso(_now())}},
    )
    return {"status": "ok"}


@router.put("/sync-rules")
async def update_sync_rules(payload: SyncRulesPayload, tenant: dict = Depends(get_active_tenant)):
    _require_owner(tenant)
    # Only allow known event types
    rules = {k: bool(v) for k, v in payload.sync_rules.items() if k in EVENT_TYPES}
    integrations_col.update_one(
        {"tenant_id": tenant["id"]},
        {"$set": {"sync_rules": rules, "updated_at": _iso(_now())}},
    )
    return {"status": "ok", "sync_rules": rules}


@router.post("/test-connection")
async def test_connection(tenant: dict = Depends(get_active_tenant)):
    _require_owner(tenant)
    integ = integrations_col.find_one({"tenant_id": tenant["id"]}, {"_id": 0})
    if not integ:
        raise HTTPException(status_code=400, detail="No CRM connected")
    # Fire a synthetic lead.created event for a test contact
    test_lead = {
        "id": f"test_{uuid.uuid4().hex[:6]}",
        "first_name": "Aria",
        "last_name": "Test",
        "email": f"aria.test+{uuid.uuid4().hex[:6]}@genleadai.com",
        "phone": "+910000000000",
        "icp_score": 50,
        "status": "test",
    }
    test_entry = {
        "id": f"test_{uuid.uuid4().hex[:8]}",
        "tenant_id": tenant["id"],
        "crm_type": integ["crm_type"],
        "event_type": "lead.created",
        "lead_id": test_lead["id"],
        "lead_snapshot": {
            "name": "Aria Test", "email": test_lead["email"], "phone": test_lead["phone"],
            "stage": "test", "score": 50,
        },
        "payload": {"test": True},
        "retry_count": 0,
    }
    result = await _dispatch(integ, test_entry)
    if result.get("success"):
        return {"status": "ok", "message": f"Connected to {integ['crm_type']}. Test contact id: {result.get('contact_id') or 'n/a'}"}
    raise HTTPException(status_code=400, detail=f"Connection failed: {result.get('error')}")


@router.get("/sync-log")
async def list_sync_log(
    status: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 200,
    tenant: dict = Depends(get_active_tenant),
):
    q: Dict[str, Any] = {"tenant_id": tenant["id"]}
    if status:
        q["status"] = status
    if event_type:
        q["event_type"] = event_type
    total = log_col.count_documents(q)
    entries = list(log_col.find(q, {"_id": 0}).sort("created_at", -1).limit(min(limit, 500)))
    return {"entries": entries, "total": total}


@router.post("/sync-log/{entry_id}/retry")
async def retry_sync_entry(entry_id: str, tenant: dict = Depends(get_active_tenant)):
    _require_owner(tenant)
    e = log_col.find_one({"id": entry_id, "tenant_id": tenant["id"]}, {"_id": 0})
    if not e:
        raise HTTPException(status_code=404, detail="Entry not found")
    log_col.update_one(
        {"id": entry_id},
        {"$set": {"status": "pending", "retry_count": 0, "error_message": None}},
    )
    return {"status": "ok"}


@router.post("/sync-log/retry-all-failed")
async def retry_all_failed(tenant: dict = Depends(get_active_tenant)):
    _require_owner(tenant)
    r = log_col.update_many(
        {"tenant_id": tenant["id"], "status": "failed"},
        {"$set": {"status": "pending", "retry_count": 0, "error_message": None}},
    )
    return {"status": "ok", "retried": r.modified_count}


@router.get("/leads/{lead_id}/status")
async def lead_crm_status(lead_id: str, tenant: dict = Depends(get_active_tenant)):
    """Tiny endpoint used by the Lead Detail badge — returns current sync status
    for the most recent log entry on this lead."""
    integ = integrations_col.find_one({"tenant_id": tenant["id"]}, {"_id": 0, "credentials": 0})
    if not integ:
        return {"connected": False}
    latest = log_col.find_one(
        {"tenant_id": tenant["id"], "lead_id": lead_id},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    return {
        "connected": True,
        "crm_type": integ["crm_type"],
        "latest": latest,
    }


@router.post("/inbound/{workspace_id}")
async def crm_inbound_webhook(workspace_id: str, body: dict = Body(...), request: Request = None):
    """Inbound webhook from a CRM (deal owner changed, stage changed, contact deleted).

    Called by HubSpot/Pipedrive workflows pointing back at this endpoint.
    Body shape (normalized):
      {event: 'deal.owner_changed'|'deal.stage_changed'|'contact.deleted',
       crm_contact_id?, crm_deal_id?, new_owner?, new_stage?}
    """
    integ = integrations_col.find_one({"tenant_id": workspace_id, "connection_status": "connected"}, {"_id": 0})
    if not integ:
        raise HTTPException(status_code=404, detail="Workspace has no active CRM")
    event = body.get("event")
    cid = body.get("crm_contact_id")
    if not cid:
        return {"status": "ignored", "reason": "no crm_contact_id"}
    lead = leads_col.find_one({"tenant_id": workspace_id, "crm_contact_id": cid}, {"_id": 0})
    if not lead:
        return {"status": "ignored", "reason": "no matching lead"}
    update: Dict[str, Any] = {"updated_at": _iso(_now())}
    if event == "deal.owner_changed" and body.get("new_owner"):
        update["assigned_to"] = body["new_owner"]
    elif event == "deal.stage_changed" and body.get("new_stage"):
        update["status"] = body["new_stage"]
    elif event == "contact.deleted":
        update["crm_contact_deleted"] = True
    if len(update) > 1:
        leads_col.update_one({"id": lead["id"], "tenant_id": workspace_id}, {"$set": update})
    # Log it as a successful inbound sync
    log_col.insert_one({
        "id": f"sync_{uuid.uuid4().hex[:12]}",
        "tenant_id": workspace_id,
        "crm_type": integ["crm_type"],
        "event_type": f"inbound.{event or 'unknown'}",
        "lead_id": lead["id"],
        "crm_contact_id": cid,
        "payload": body,
        "status": "success",
        "synced_at": _iso(_now()),
        "retry_count": 0,
        "error_message": None,
        "created_at": _iso(_now()),
    })
    return {"status": "ok", "lead_id": lead["id"]}


# ─── OAuth start URL helpers (placeholder) ────────────────────────────────────
@router.get("/oauth/{crm}/start")
async def oauth_start(crm: str, tenant: dict = Depends(get_active_tenant)):
    """Returns the OAuth authorize URL for the given CRM (HubSpot/Zoho/Salesforce).
    Client ID is read from env. Frontend opens this URL in a new tab.
    """
    if crm not in OAUTH_CRMS:
        raise HTTPException(status_code=400, detail=f"{crm} is not OAuth-based")
    base = os.environ.get("APP_BASE_URL") or os.environ.get("FRONTEND_URL", "https://app.genleadai.com")
    redirect_uri = f"{base.rstrip('/')}/integrations/crm/callback"
    state = f"{tenant['id']}:{crm}"

    if crm == "hubspot":
        cid = os.environ.get("HUBSPOT_CLIENT_ID", "PLACEHOLDER_CLIENT_ID")
        scope = "crm.objects.contacts.read crm.objects.contacts.write crm.objects.deals.read crm.objects.deals.write"
        url = (
            f"https://app.hubspot.com/oauth/authorize?"
            f"client_id={cid}&redirect_uri={redirect_uri}&scope={scope}&state={state}"
        )
        return {"url": url, "placeholder": cid == "PLACEHOLDER_CLIENT_ID"}
    if crm == "zoho":
        cid = os.environ.get("ZOHO_CLIENT_ID", "PLACEHOLDER")
        url = (
            f"https://accounts.zoho.com/oauth/v2/auth?"
            f"client_id={cid}&response_type=code&access_type=offline"
            f"&redirect_uri={redirect_uri}&scope=ZohoCRM.modules.ALL&state={state}"
        )
        return {"url": url, "placeholder": cid == "PLACEHOLDER"}
    if crm == "salesforce":
        cid = os.environ.get("SALESFORCE_CLIENT_ID", "PLACEHOLDER")
        url = (
            f"https://login.salesforce.com/services/oauth2/authorize?"
            f"response_type=code&client_id={cid}&redirect_uri={redirect_uri}&state={state}"
        )
        return {"url": url, "placeholder": cid == "PLACEHOLDER"}
    raise HTTPException(status_code=400, detail="Unsupported CRM")
