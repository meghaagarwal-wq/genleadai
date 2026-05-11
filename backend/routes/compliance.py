"""WhatsApp opt-in compliance — Meta Business Messaging policy.

Tracks per-lead opt-in state and a tenant-wide opted-out blocklist. Aria's
outbound message paths MUST consult these before sending any non-templated
content.

Collections:
- opted_out_numbers: {tenant_id, phone, opted_out_at, reason}
- leads: extended in-place with {opted_in, opted_in_at, opted_in_source}
"""
import re
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import db, get_current_user
from routes.tenants import get_active_tenant

router = APIRouter(prefix="/api/compliance", tags=["compliance"])

opted_out_col = db["opted_out_numbers"]
leads_col = db["leads"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(phone: str) -> str:
    return "".join(c for c in (phone or "") if c.isdigit())


# ─── Public helpers (called from webhook + engine) ──────────────────────────
STOP_KEYWORDS = {"stop", "unsubscribe", "no more", "stop messages", "remove me"}


def is_stop_keyword(text: str) -> bool:
    body = (text or "").strip().lower()
    if not body:
        return False
    # Exact match or starts-with for single tokens like "STOP"
    if body in STOP_KEYWORDS:
        return True
    first_word = body.split()[0]
    return first_word in {"stop", "unsubscribe"}


def is_opted_out(tenant_id: str, phone: str) -> bool:
    """Check the tenant blocklist + last-10-digit fallback."""
    norm = _normalize(phone)
    if not norm:
        return True  # No phone -> can't message anyway
    last10 = norm[-10:] if len(norm) >= 10 else norm
    found = opted_out_col.find_one({
        "tenant_id": tenant_id,
        "$or": [{"phone": norm}, {"phone_last10": last10}],
    }, {"_id": 1})
    return bool(found)


def opt_out_phone(tenant_id: str, phone: str, reason: str = "stop_keyword") -> dict:
    """Add a phone to the opted-out list and flip the matching lead off."""
    norm = _normalize(phone)
    if not norm:
        return {"ok": False, "error": "invalid_phone"}
    last10 = norm[-10:] if len(norm) >= 10 else norm
    opted_out_col.update_one(
        {"tenant_id": tenant_id, "phone": norm},
        {"$set": {
            "tenant_id": tenant_id,
            "phone": norm,
            "phone_last10": last10,
            "reason": reason,
            "opted_out_at": _now(),
        }},
        upsert=True,
    )
    # Mark matching leads as opted_out
    leads_col.update_many(
        {"tenant_id": tenant_id, "phone": {"$regex": f"{last10}$"}},
        {"$set": {"opted_in": False, "opted_out": True, "opted_out_at": _now()}},
    )
    return {"ok": True, "phone": norm}


def can_send_outbound(tenant_id: str, lead: dict) -> dict:
    """Gatekeeper used by the engine before any outbound send.
    Returns {allow: bool, reason: str}.
    """
    if not lead:
        return {"allow": False, "reason": "no_lead"}
    if lead.get("opted_out"):
        return {"allow": False, "reason": "opted_out"}
    if not lead.get("opted_in"):
        return {"allow": False, "reason": "not_opted_in"}
    if is_opted_out(tenant_id, lead.get("phone") or ""):
        return {"allow": False, "reason": "tenant_blocklisted"}
    return {"allow": True, "reason": "ok"}


def auto_opt_in_on_inbound(tenant_id: str, lead_id: str) -> None:
    """When a lead sends the first inbound message, they've implicitly opted in."""
    leads_col.update_one(
        {"id": lead_id, "tenant_id": tenant_id},
        {"$set": {
            "opted_in": True,
            "opted_in_at": _now(),
            "opted_in_source": "replied_first",
        }},
    )


# ─── Endpoints ───────────────────────────────────────────────────────────────
class ManualOptInPayload(BaseModel):
    lead_id: str
    source: str = Field(default="manual_confirmed")


class OptInRequestPayload(BaseModel):
    lead_id: str


@router.post("/lead/opt-in")
async def manual_opt_in(payload: ManualOptInPayload, tenant: dict = Depends(get_active_tenant)):
    """Mark a lead as opted-in manually (with source attribution)."""
    if tenant.get("_member_role") not in ("owner", "admin", "member"):
        raise HTTPException(status_code=403, detail="Not allowed")
    lead = leads_col.find_one({"id": payload.lead_id, "tenant_id": tenant["id"]}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if payload.source not in {"manual_confirmed", "website_form", "replied_first", "imported_with_consent"}:
        raise HTTPException(status_code=400, detail="Invalid source")
    leads_col.update_one(
        {"id": payload.lead_id, "tenant_id": tenant["id"]},
        {"$set": {
            "opted_in": True,
            "opted_in_at": _now(),
            "opted_in_source": payload.source,
            "opted_out": False,
        }},
    )
    return {"status": "ok", "opted_in_source": payload.source}


@router.post("/lead/opt-out")
async def manual_opt_out(payload: OptInRequestPayload, tenant: dict = Depends(get_active_tenant)):
    """Mark a lead as opted-out manually + add phone to blocklist."""
    if tenant.get("_member_role") not in ("owner", "admin", "member"):
        raise HTTPException(status_code=403, detail="Not allowed")
    lead = leads_col.find_one({"id": payload.lead_id, "tenant_id": tenant["id"]}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    opt_out_phone(tenant["id"], lead.get("phone") or "", reason="manual")
    return {"status": "ok"}


@router.get("/opted-out")
async def list_opted_out(tenant: dict = Depends(get_active_tenant)):
    rows = list(opted_out_col.find({"tenant_id": tenant["id"]}, {"_id": 0}).sort("opted_out_at", -1).limit(500))
    return {"opted_out_numbers": rows}


@router.delete("/opted-out/{phone}")
async def remove_from_blocklist(phone: str, tenant: dict = Depends(get_active_tenant)):
    """Admin-only: remove a phone from the tenant blocklist (e.g. user changed their mind)."""
    if tenant.get("_member_role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")
    norm = _normalize(phone)
    opted_out_col.delete_one({"tenant_id": tenant["id"], "phone": norm})
    return {"status": "ok"}
