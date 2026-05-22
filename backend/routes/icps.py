"""Multi-ICP Architecture — Deliverable 7.

Each tenant can define multiple Ideal Customer Profiles (ICPs). Every lead,
asset, and conversation can be tagged to an ICP. Aria injects the ICP's
pain_point / value_prop / tone / title_targets into the Claude prompt so
outbound copy and inbound replies adapt to *which* customer type the contact is.

Collection: `icps`
  - id: str (icp_<hex>)
  - tenant_id: str
  - label: str
  - title_targets: List[str]
  - industry: str | None
  - company_size: str | None
  - pain_point: str | None
  - value_prop: str | None
  - tone: str  ("professional" | "casual" | "bold")
  - deal_size: str | None
  - created_at: ISO str
  - updated_at: ISO str

Tier gating (mapped to current plan IDs):
  - trial / diy   → max 2 ICPs
  - dwy           → unlimited
  - dfy           → unlimited
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import db, leads_collection, aria_conversations_collection, workspace_assets_collection
from routes.tenants import get_active_tenant


router = APIRouter(prefix="/api/icps", tags=["icps"])

icps_col = db["icps"]


# ─── Constants ──────────────────────────────────────────────────────────────
ALLOWED_TONES = {"professional", "casual", "bold"}

# Iter77 — GenLeadAI is a managed-deployment platform; ICP caps were removed.
# The previous ICP_LIMIT_BY_PLAN dict + _icp_limit() / _icp_count() helpers are
# intentionally gone. If billing-tier caps are ever re-introduced, restore via
# a Stripe-managed feature flag rather than hardcoded plan thresholds.


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return f"icp_{uuid.uuid4().hex[:12]}"


def _scrub(doc: dict) -> dict:
    if not doc:
        return doc
    doc = {k: v for k, v in doc.items() if k != "_id"}
    return doc


def _tenant_plan(tenant: dict) -> str:
    return (tenant.get("plan") or "trial").lower()


# ─── Pydantic models ────────────────────────────────────────────────────────
class IcpCreate(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    title_targets: List[str] = Field(default_factory=list, max_length=20)
    industry: Optional[str] = None
    company_size: Optional[str] = None
    pain_point: Optional[str] = None
    value_prop: Optional[str] = None
    tone: str = "professional"
    deal_size: Optional[str] = None


class IcpUpdate(BaseModel):
    label: Optional[str] = None
    title_targets: Optional[List[str]] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    pain_point: Optional[str] = None
    value_prop: Optional[str] = None
    tone: Optional[str] = None
    deal_size: Optional[str] = None


class AssignContactPayload(BaseModel):
    contact_id: str  # this is the lead.id in our schema
    icp_id: Optional[str] = None  # null clears the assignment


# ─── Helper: fetch ICP for any caller (used by touchpoint engine + webhook) ─
def fetch_icp(tenant_id: str, icp_id: Optional[str]) -> Optional[dict]:
    """Public helper — returns the ICP doc or None. Safe to call with None."""
    if not icp_id:
        return None
    return _scrub(icps_col.find_one({"id": icp_id, "tenant_id": tenant_id}))


def fetch_icp_for_lead(tenant_id: str, lead: Optional[dict]) -> Optional[dict]:
    """Convenience — pulls icp_id off the lead and resolves it."""
    if not lead:
        return None
    return fetch_icp(tenant_id, lead.get("icp_id"))


# ─── Endpoints ──────────────────────────────────────────────────────────────
@router.post("/create", status_code=201)
async def create_icp(payload: IcpCreate, tenant: dict = Depends(get_active_tenant)):
    """Create a new ICP for the active tenant.

    Errors:
      - 403 tier_limit_reached  → caller is on a plan capped at N ICPs.
      - 400 invalid_tone        → tone must be one of: professional / casual / bold.
    """
    role = tenant.get("_member_role")
    if role not in ("owner", "admin", "member"):
        raise HTTPException(status_code=403, detail="Not allowed")

    if payload.tone not in ALLOWED_TONES:
        raise HTTPException(
            status_code=400,
            detail=f"invalid_tone: must be one of {sorted(ALLOWED_TONES)}",
        )

    # Iter77 — GenLeadAI-managed deployment: no plan-based ICP caps. ICPs are
    # operational sales segments; agency owners decide how many.

    now = _now_iso()
    doc = {
        "id": _new_id(),
        "tenant_id": tenant["id"],
        "label": payload.label.strip(),
        "title_targets": [t.strip() for t in (payload.title_targets or []) if t and t.strip()],
        "industry": payload.industry,
        "company_size": payload.company_size,
        "pain_point": payload.pain_point,
        "value_prop": payload.value_prop,
        "tone": payload.tone,
        "deal_size": payload.deal_size,
        "created_at": now,
        "updated_at": now,
    }
    icps_col.insert_one(doc)
    return _scrub(doc)


@router.get("/list")
async def list_icps(tenant: dict = Depends(get_active_tenant)):
    """List all ICPs for the active tenant. Newest first."""
    cursor = icps_col.find({"tenant_id": tenant["id"]}).sort("created_at", -1)
    items = [_scrub(d) for d in cursor]
    return {
        "icps": items,
        "count": len(items),
        "limit": None,             # iter77 — caps removed; deployment-managed
        "can_create_more": True,
    }


@router.put("/{icp_id}")
async def update_icp(icp_id: str, payload: IcpUpdate, tenant: dict = Depends(get_active_tenant)):
    """Update any subset of fields on an existing ICP. Tenant-scoped.

    Errors:
      - 404 icp_not_found
      - 400 invalid_tone
    """
    role = tenant.get("_member_role")
    if role not in ("owner", "admin", "member"):
        raise HTTPException(status_code=403, detail="Not allowed")

    existing = icps_col.find_one({"id": icp_id, "tenant_id": tenant["id"]})
    if not existing:
        raise HTTPException(status_code=404, detail="icp_not_found")

    updates = payload.dict(exclude_unset=True)
    if "tone" in updates and updates["tone"] not in ALLOWED_TONES:
        raise HTTPException(
            status_code=400,
            detail=f"invalid_tone: must be one of {sorted(ALLOWED_TONES)}",
        )
    if "title_targets" in updates and updates["title_targets"] is not None:
        updates["title_targets"] = [
            t.strip() for t in updates["title_targets"] if t and t.strip()
        ]
    if "label" in updates and updates["label"] is not None:
        updates["label"] = updates["label"].strip()
        if not updates["label"]:
            raise HTTPException(status_code=400, detail="label_required")

    updates["updated_at"] = _now_iso()
    icps_col.update_one({"id": icp_id, "tenant_id": tenant["id"]}, {"$set": updates})
    fresh = icps_col.find_one({"id": icp_id, "tenant_id": tenant["id"]})
    return _scrub(fresh)


@router.delete("/{icp_id}")
async def delete_icp(
    icp_id: str,
    force: bool = False,
    tenant: dict = Depends(get_active_tenant),
):
    """Delete an ICP. If it has tagged records, returns a warning unless force=true.

    Without force=true:
      - returns 409 with counts so the caller can confirm.

    With force=true:
      - sets icp_id = null on every tagged record, then deletes the ICP.

    Errors:
      - 404 icp_not_found
      - 409 icp_in_use (with counts)  when force=false and there are tagged records.
    """
    role = tenant.get("_member_role")
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")

    existing = icps_col.find_one({"id": icp_id, "tenant_id": tenant["id"]})
    if not existing:
        raise HTTPException(status_code=404, detail="icp_not_found")

    tenant_id = tenant["id"]
    counts = {
        "contacts": leads_collection.count_documents({"tenant_id": tenant_id, "icp_id": icp_id}),
        "assets": workspace_assets_collection.count_documents({"tenant_id": tenant_id, "icp_id": icp_id}),
        "conversations": aria_conversations_collection.count_documents({"tenant_id": tenant_id, "icp_id": icp_id}),
    }
    total_tagged = sum(counts.values())

    if total_tagged > 0 and not force:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "icp_in_use",
                "message": (
                    f"This ICP is tagged on {total_tagged} record(s). "
                    "Pass ?force=true to untag them and delete."
                ),
                "counts": counts,
            },
        )

    if total_tagged > 0:
        leads_collection.update_many(
            {"tenant_id": tenant_id, "icp_id": icp_id},
            {"$set": {"icp_id": None}},
        )
        workspace_assets_collection.update_many(
            {"tenant_id": tenant_id, "icp_id": icp_id},
            {"$set": {"icp_id": None}},
        )
        aria_conversations_collection.update_many(
            {"tenant_id": tenant_id, "icp_id": icp_id},
            {"$set": {"icp_id": None}},
        )

    icps_col.delete_one({"id": icp_id, "tenant_id": tenant_id})
    return {"deleted": True, "untagged": counts}


@router.post("/assign-contact")
async def assign_contact(payload: AssignContactPayload, tenant: dict = Depends(get_active_tenant)):
    """Tag a lead (contact) with an ICP. Pass icp_id=null to clear.

    Errors:
      - 404 contact_not_found
      - 404 icp_not_found
    """
    role = tenant.get("_member_role")
    if role not in ("owner", "admin", "member"):
        raise HTTPException(status_code=403, detail="Not allowed")

    tenant_id = tenant["id"]
    lead = leads_collection.find_one(
        {"id": payload.contact_id, "tenant_id": tenant_id},
        {"_id": 0},
    )
    if not lead:
        # accept lookup by _id as fallback so /leads (which exposes _id as id) works
        try:
            from bson import ObjectId
            lead = leads_collection.find_one(
                {"_id": ObjectId(payload.contact_id), "tenant_id": tenant_id},
                {"_id": 0},
            )
        except Exception:
            lead = None
    if not lead:
        raise HTTPException(status_code=404, detail="contact_not_found")

    if payload.icp_id:
        target = icps_col.find_one({"id": payload.icp_id, "tenant_id": tenant_id})
        if not target:
            raise HTTPException(status_code=404, detail="icp_not_found")

    leads_collection.update_one(
        {"id": payload.contact_id, "tenant_id": tenant_id},
        {"$set": {"icp_id": payload.icp_id, "icp_assigned_at": _now_iso()}},
    )
    fresh = leads_collection.find_one(
        {"id": payload.contact_id, "tenant_id": tenant_id},
        {"_id": 0},
    )
    return {"contact": fresh, "icp_id": payload.icp_id}
