"""ARIA — Approval Queue (Batch 7).

The UX-facing surface for `pending_outreach.status='awaiting_owner_approval'`
drafts. Powers the `/app/approvals` page.

Backend contract
────────────────
  GET    /api/approvals               — list all pending drafts (newest first)
  GET    /api/approvals/count         — { count } for nav badge polling
  POST   /api/approvals/{id}/approve  — dispatch via outreach_dispatch
  POST   /api/approvals/{id}/edit-send — { subject?, body } → dispatch the edited message
  POST   /api/approvals/{id}/reject   — archive with optional reason
  POST   /api/approvals/bulk-approve  — { ids?: [...] } (empty = approve ALL)
  POST   /api/approvals/bulk-reject   — { ids?: [...], reason? }
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import db, get_current_user
from services.outreach_dispatch import dispatch_outreach

logger = logging.getLogger("approvals")
router = APIRouter(prefix="/api/approvals", tags=["approvals"])

pending_col = db["pending_outreach"]
leads_col = db["pt_leads"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _oid(s: str) -> Optional[ObjectId]:
    try:
        return ObjectId(s)
    except Exception:
        return None


# ─── Helpers ────────────────────────────────────────────────────────────
def _enrich_with_lead(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Attach name/company/stage so the FE doesn't need another round trip."""
    lead = leads_col.find_one(
        {"id": doc.get("lead_id"), "tenant_id": doc.get("tenant_id")},
        {"_id": 0, "first_name": 1, "last_name": 1, "email": 1, "company_name": 1, "stage": 1, "score": 1},
    ) or {}
    name = f"{lead.get('first_name','')} {lead.get('last_name','')}".strip() or lead.get("email") or "Prospect"
    doc["lead_snapshot"] = {
        "name": name,
        "first_name": lead.get("first_name"),
        "email": lead.get("email"),
        "company": lead.get("company_name"),
        "stage": lead.get("stage"),
        "score": lead.get("score"),
    }
    return doc


def _serialise(doc: Dict[str, Any]) -> Dict[str, Any]:
    doc["id"] = str(doc.pop("_id"))
    return _enrich_with_lead(doc)


# ─── Schemas ────────────────────────────────────────────────────────────
class EditSendBody(BaseModel):
    subject: Optional[str] = None
    body: str = Field(..., min_length=1)


class RejectBody(BaseModel):
    reason: Optional[str] = None


class BulkBody(BaseModel):
    ids: Optional[List[str]] = None
    reason: Optional[str] = None  # only used by reject


# ─── List + count ───────────────────────────────────────────────────────
@router.get("")
async def list_pending(current_user: dict = Depends(get_current_user)):
    tenant_id = current_user.get("tenant_id")
    cursor = pending_col.find(
        {"tenant_id": tenant_id, "status": "awaiting_owner_approval"},
    ).sort("created_at", -1).limit(200)
    items = [_serialise(d) for d in cursor]
    return {"items": items, "count": len(items)}


@router.get("/count")
async def pending_count(current_user: dict = Depends(get_current_user)):
    tenant_id = current_user.get("tenant_id")
    return {
        "count": pending_col.count_documents(
            {"tenant_id": tenant_id, "status": "awaiting_owner_approval"}
        )
    }


# ─── Approve (dispatch as drafted) ──────────────────────────────────────
async def _dispatch_doc(doc: Dict[str, Any], actor_email: str) -> Dict[str, Any]:
    composed_message: Any
    if doc.get("channel") == "email":
        composed_message = {"subject": doc.get("subject") or "Quick idea", "body": doc.get("body") or ""}
    else:
        composed_message = doc.get("body") or ""
    composed = {
        "channel": doc.get("channel"),
        "message": composed_message,
        "ai_powered": bool(doc.get("ai_powered")),
    }
    return await dispatch_outreach(
        tenant_id=doc["tenant_id"],
        lead_id=doc["lead_id"],
        channel=doc["channel"],
        composed=composed,
        actor_user_id=actor_email,
    )


@router.post("/{approval_id}/approve")
async def approve(approval_id: str, current_user: dict = Depends(get_current_user)):
    tenant_id = current_user.get("tenant_id")
    oid = _oid(approval_id)
    if not oid:
        raise HTTPException(status_code=400, detail="invalid id")
    doc = pending_col.find_one({"_id": oid, "tenant_id": tenant_id})
    if not doc:
        raise HTTPException(status_code=404, detail="not found")
    if doc.get("status") != "awaiting_owner_approval":
        raise HTTPException(status_code=409, detail=f"already {doc.get('status')}")

    result = await _dispatch_doc(doc, current_user.get("email", "owner"))

    pending_col.update_one(
        {"_id": oid},
        {"$set": {
            "status": "sent" if result.get("sent") else ("drafted_pending_provider" if result.get("logged_only") else "send_failed"),
            "dispatch_result": result,
            "approved_at": _now_iso(),
            "approved_by": current_user.get("email"),
        }},
    )
    return {"ok": True, "dispatch": result}


# ─── Edit + Send ────────────────────────────────────────────────────────
@router.post("/{approval_id}/edit-send")
async def edit_send(
    approval_id: str,
    body: EditSendBody,
    current_user: dict = Depends(get_current_user),
):
    tenant_id = current_user.get("tenant_id")
    oid = _oid(approval_id)
    if not oid:
        raise HTTPException(status_code=400, detail="invalid id")
    doc = pending_col.find_one({"_id": oid, "tenant_id": tenant_id})
    if not doc:
        raise HTTPException(status_code=404, detail="not found")
    if doc.get("status") != "awaiting_owner_approval":
        raise HTTPException(status_code=409, detail=f"already {doc.get('status')}")

    # Update the draft in-place so the audit trail shows what was actually sent.
    pending_col.update_one(
        {"_id": oid},
        {"$set": {
            "subject": (body.subject if body.subject is not None else doc.get("subject")),
            "body": body.body,
            "edited_at": _now_iso(),
            "edited_by": current_user.get("email"),
        }},
    )
    doc = pending_col.find_one({"_id": oid})
    result = await _dispatch_doc(doc, current_user.get("email", "owner"))
    pending_col.update_one(
        {"_id": oid},
        {"$set": {
            "status": "sent" if result.get("sent") else ("drafted_pending_provider" if result.get("logged_only") else "send_failed"),
            "dispatch_result": result,
            "approved_at": _now_iso(),
            "approved_by": current_user.get("email"),
        }},
    )
    return {"ok": True, "dispatch": result}


# ─── Reject ─────────────────────────────────────────────────────────────
@router.post("/{approval_id}/reject")
async def reject(
    approval_id: str,
    body: RejectBody,
    current_user: dict = Depends(get_current_user),
):
    tenant_id = current_user.get("tenant_id")
    oid = _oid(approval_id)
    if not oid:
        raise HTTPException(status_code=400, detail="invalid id")
    res = pending_col.update_one(
        {"_id": oid, "tenant_id": tenant_id, "status": "awaiting_owner_approval"},
        {"$set": {
            "status": "rejected",
            "rejected_at": _now_iso(),
            "rejected_by": current_user.get("email"),
            "rejection_reason": (body.reason or "").strip() or None,
        }},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="not found or already actioned")
    return {"ok": True}


# ─── Bulk actions ───────────────────────────────────────────────────────
@router.post("/bulk-approve")
async def bulk_approve(
    body: BulkBody,
    current_user: dict = Depends(get_current_user),
):
    tenant_id = current_user.get("tenant_id")
    query: Dict[str, Any] = {"tenant_id": tenant_id, "status": "awaiting_owner_approval"}
    if body.ids:
        valid_oids = [o for o in (_oid(i) for i in body.ids) if o]
        if not valid_oids:
            raise HTTPException(status_code=400, detail="no valid ids")
        query["_id"] = {"$in": valid_oids}

    docs = list(pending_col.find(query))
    if not docs:
        return {"ok": True, "processed": 0, "succeeded": 0, "failed": 0, "results": []}

    results = []
    succeeded = failed = 0
    for doc in docs:
        try:
            dispatch = await _dispatch_doc(doc, current_user.get("email", "owner"))
            new_status = (
                "sent" if dispatch.get("sent")
                else ("drafted_pending_provider" if dispatch.get("logged_only") else "send_failed")
            )
            pending_col.update_one(
                {"_id": doc["_id"]},
                {"$set": {
                    "status": new_status,
                    "dispatch_result": dispatch,
                    "approved_at": _now_iso(),
                    "approved_by": current_user.get("email"),
                }},
            )
            if dispatch.get("sent"):
                succeeded += 1
            else:
                failed += 1
            results.append({
                "id": str(doc["_id"]),
                "status": new_status,
                "sent": dispatch.get("sent"),
                "error": dispatch.get("error"),
                "provider": dispatch.get("provider"),
            })
        except Exception as e:  # noqa: BLE001
            logger.exception("bulk_approve: error on %s", doc.get("_id"))
            failed += 1
            results.append({"id": str(doc["_id"]), "status": "error", "error": str(e)[:200]})
    return {"ok": True, "processed": len(docs), "succeeded": succeeded, "failed": failed, "results": results}


@router.post("/bulk-reject")
async def bulk_reject(
    body: BulkBody,
    current_user: dict = Depends(get_current_user),
):
    tenant_id = current_user.get("tenant_id")
    query: Dict[str, Any] = {"tenant_id": tenant_id, "status": "awaiting_owner_approval"}
    if body.ids:
        valid_oids = [o for o in (_oid(i) for i in body.ids) if o]
        if not valid_oids:
            raise HTTPException(status_code=400, detail="no valid ids")
        query["_id"] = {"$in": valid_oids}
    res = pending_col.update_many(
        query,
        {"$set": {
            "status": "rejected",
            "rejected_at": _now_iso(),
            "rejected_by": current_user.get("email"),
            "rejection_reason": (body.reason or "").strip() or None,
        }},
    )
    return {"ok": True, "rejected": res.modified_count}
