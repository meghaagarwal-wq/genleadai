"""Workspace contacts (non-lead known phone numbers).

Owners pre-register vendors, existing clients, personal contacts, press, etc.
Used by Layer 2 of inbound classification to route to the right handler
instead of treating every unknown number as a sales lead.
"""
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import db, get_current_user
from routes.tenants import get_active_tenant

router = APIRouter(prefix="/api/contacts", tags=["contacts"])

contacts_col = db["workspace_contacts"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(phone: str) -> str:
    return "".join(c for c in (phone or "") if c.isdigit())


CONTACT_TYPES = {"existing_client", "vendor", "blocked", "personal", "press", "job_applicant"}


def lookup_contact(tenant_id: str, phone: str) -> Optional[dict]:
    """Phone lookup for Layer 2 classification."""
    norm = _normalize(phone)
    if not norm:
        return None
    last10 = norm[-10:] if len(norm) >= 10 else norm
    return contacts_col.find_one(
        {"tenant_id": tenant_id, "$or": [{"phone_normalized": norm}, {"phone_last10": last10}]},
        {"_id": 0},
    )


class ContactPayload(BaseModel):
    name: Optional[str] = ""
    phone: str
    contact_type: str
    company: Optional[str] = ""
    notes: Optional[str] = ""


def _new_id() -> str:
    import uuid
    return f"con_{uuid.uuid4().hex[:12]}"


@router.get("")
async def list_contacts(
    contact_type: Optional[str] = None,
    tenant: dict = Depends(get_active_tenant),
):
    q = {"tenant_id": tenant["id"]}
    if contact_type:
        q["contact_type"] = contact_type
    rows = list(contacts_col.find(q, {"_id": 0}).sort("created_at", -1).limit(500))
    return {"contacts": rows}


@router.post("")
async def create_contact(payload: ContactPayload, tenant: dict = Depends(get_active_tenant), current_user: dict = Depends(get_current_user)):
    if tenant.get("_member_role") not in ("owner", "admin", "member"):
        raise HTTPException(status_code=403, detail="Not allowed")
    if payload.contact_type not in CONTACT_TYPES:
        raise HTTPException(status_code=400, detail=f"contact_type must be one of {sorted(CONTACT_TYPES)}")
    norm = _normalize(payload.phone)
    if not norm:
        raise HTTPException(status_code=400, detail="Phone is required")
    last10 = norm[-10:] if len(norm) >= 10 else norm
    doc = {
        "id": _new_id(),
        "tenant_id": tenant["id"],
        "name": payload.name.strip(),
        "phone": payload.phone.strip(),
        "phone_normalized": norm,
        "phone_last10": last10,
        "contact_type": payload.contact_type,
        "company": (payload.company or "").strip(),
        "notes": (payload.notes or "").strip(),
        "added_by": current_user["email"],
        "created_at": _now(),
    }
    contacts_col.insert_one(doc)
    return {"contact": {k: v for k, v in doc.items() if k != "_id"}}


@router.put("/{contact_id}")
async def update_contact(contact_id: str, payload: ContactPayload, tenant: dict = Depends(get_active_tenant)):
    if tenant.get("_member_role") not in ("owner", "admin", "member"):
        raise HTTPException(status_code=403, detail="Not allowed")
    if payload.contact_type not in CONTACT_TYPES:
        raise HTTPException(status_code=400, detail="Invalid contact_type")
    norm = _normalize(payload.phone)
    update = {
        "name": payload.name.strip(),
        "phone": payload.phone.strip(),
        "phone_normalized": norm,
        "phone_last10": norm[-10:] if len(norm) >= 10 else norm,
        "contact_type": payload.contact_type,
        "company": (payload.company or "").strip(),
        "notes": (payload.notes or "").strip(),
        "updated_at": _now(),
    }
    r = contacts_col.update_one({"id": contact_id, "tenant_id": tenant["id"]}, {"$set": update})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"status": "ok"}


@router.delete("/{contact_id}")
async def delete_contact(contact_id: str, tenant: dict = Depends(get_active_tenant)):
    if tenant.get("_member_role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")
    contacts_col.delete_one({"id": contact_id, "tenant_id": tenant["id"]})
    return {"status": "ok"}
