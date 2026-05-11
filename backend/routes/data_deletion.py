"""DPDP Act 2023 — lead personal-data deletion endpoints.

Two flows:
  • Soft-delete (anonymise) — name→"Deleted User", phone→[REDACTED-{id}],
    email→null, notes purged. Conversations retained but message bodies cleared.
    Sets `data_deleted=true`. Aria stops messaging.

  • Hard-delete — wipes the lead document plus all related rows
    (activities, touchpoints, conversation messages). Only on Owner request.

Both flows insert a row into `data_deletion_log` for the legally-required audit
trail (kept for 7 years per DPDP).
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from deps import db, get_current_user
from routes.tenants import get_active_tenant
from routes.audit_log import audit_write

router = APIRouter(prefix="/api/leads", tags=["data-deletion"])

leads_col = db["leads"]
conversations_col = db["conversations"]
activities_col = db["activities"]
touchpoint_log_col = db["lead_touchpoint_log"]
deletion_log_col = db["data_deletion_log"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _phone_hash(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None
    return hashlib.sha256(phone.encode("utf-8")).hexdigest()[:16]


def _resolve_lead(lead_id: str, tenant_id: str) -> Optional[dict]:
    """Resolve lead either by string `id` or legacy ObjectId."""
    lead = leads_col.find_one({"id": lead_id, "tenant_id": tenant_id})
    if lead:
        return lead
    try:
        return leads_col.find_one({"_id": ObjectId(lead_id), "tenant_id": tenant_id})
    except Exception:
        return None


class DeletePayload(BaseModel):
    reason: Optional[str] = None
    mode: str = "anonymise"  # anonymise | hard


@router.post("/{lead_id}/delete-personal-data")
async def delete_personal_data(
    lead_id: str,
    payload: DeletePayload,
    tenant: dict = Depends(get_active_tenant),
    user: dict = Depends(get_current_user),
    request: Request = None,
):
    if tenant.get("_member_role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")
    if payload.mode not in ("anonymise", "hard"):
        raise HTTPException(status_code=400, detail="mode must be 'anonymise' or 'hard'")

    lead = _resolve_lead(lead_id, tenant["id"])
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    real_id = lead.get("id") or str(lead.get("_id"))
    phone_hash = _phone_hash(lead.get("phone"))
    redacted_phone = f"[REDACTED-{real_id[:8]}]"
    now = _now()

    if payload.mode == "anonymise":
        leads_col.update_one(
            {"id": real_id, "tenant_id": tenant["id"]},
            {"$set": {
                "first_name": "Deleted",
                "last_name": "User",
                "name": "Deleted User",
                "email": None,
                "phone": redacted_phone,
                "notes": None,
                "company_name": None,
                "data_deleted": True,
                "data_deleted_at": now,
                "data_deleted_by": user.get("email"),
                "data_deletion_mode": "anonymise",
                "opted_in": False,
                "updated_at": now,
            }},
        )
        # Clear all conversation message bodies but keep metadata
        conversations_col.update_many(
            {"lead_id": real_id, "tenant_id": tenant["id"]},
            {"$set": {"thread_json": [], "body_redacted": True}},
        )
        # Delete activity bodies/notes
        activities_col.update_many(
            {"lead_id": real_id, "tenant_id": tenant["id"]},
            {"$set": {"body": None, "subject": "[redacted]"}},
        )
    else:  # hard
        leads_col.delete_one({"id": real_id, "tenant_id": tenant["id"]})
        conversations_col.delete_many({"lead_id": real_id, "tenant_id": tenant["id"]})
        activities_col.delete_many({"lead_id": real_id, "tenant_id": tenant["id"]})
        touchpoint_log_col.delete_many({"lead_id": real_id, "tenant_id": tenant["id"]})

    deletion_log_col.insert_one({
        "id": f"del_{uuid.uuid4().hex[:12]}",
        "tenant_id": tenant["id"],
        "lead_id": real_id,
        "phone_hash": phone_hash,
        "mode": payload.mode,
        "reason": payload.reason or "user request",
        "deleted_by": user.get("email"),
        "created_at": now,
    })
    audit_write(
        tenant["id"], user, "lead.data_purged", "lead", real_id,
        {"mode": payload.mode, "reason": payload.reason or ""},
        request=request,
    )
    return {"status": "ok", "mode": payload.mode}


@router.get("/{lead_id}/deletion-log")
async def lead_deletion_log(
    lead_id: str,
    tenant: dict = Depends(get_active_tenant),
    user: dict = Depends(get_current_user),
):
    if tenant.get("_member_role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")
    rows = list(deletion_log_col.find(
        {"tenant_id": tenant["id"], "lead_id": lead_id},
        {"_id": 0},
    ).sort("created_at", -1))
    return {"entries": rows}
