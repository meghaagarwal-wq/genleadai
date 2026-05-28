"""Submodule of aria_agent_routes — registers routes on the shared router.
Auto-split from aria_agent_routes.py (iter75).
"""
from ._shared import (
    router, training_collection, playbooks_collection, leads_collection,
    activities_collection, db, get_current_user, AriaTrainingPayload,
)
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import os
import json


# 9. Sales Assets — reusable content ARIA can send on your behalf
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

assets_collection = db["aria_sales_assets"]

ASSET_TYPES = [
    {"id": "message_template", "label": "Message templates", "icon": "ChatText",
     "description": "Short, reusable messages ARIA can personalise per lead."},
    {"id": "voice_note", "label": "Founder voice notes", "icon": "Microphone",
     "description": "Pre-recorded founder voice notes for high-value moments."},
    {"id": "case_study", "label": "Case studies", "icon": "FileText",
     "description": "Proof stories ARIA weaves into objection responses."},
    {"id": "proposal_template", "label": "Proposal templates", "icon": "Article",
     "description": "Structured proposal outlines ARIA tailors to each lead."},
    {"id": "founder_intro", "label": "Founder intros", "icon": "User",
     "description": "Personal intros ARIA can deploy when a lead wants the founder."},
    {"id": "objection_response", "label": "Objection responses", "icon": "ShieldCheck",
     "description": "Battle-tested responses to common pushbacks."},
    {"id": "pricing_doc", "label": "Pricing docs", "icon": "CurrencyDollar",
     "description": "Pricing one-pagers ARIA surfaces at the right time."},
]

class AssetPayload(BaseModel):
    title: str
    type: str = "message_template"
    body: str = ""
    tags: List[str] = Field(default_factory=list)
    channel: Optional[str] = None
    used_by_aria: bool = True

@router.get("/assets/catalog")
async def assets_catalog(current_user: dict = Depends(get_current_user)):
    return {"types": ASSET_TYPES}

@router.get("/assets")
async def list_assets(type: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    q = {}
    if type:
        q["type"] = type
    docs = list(assets_collection.find(q, {"_id": 0}).sort("created_at", -1))
    # Summary stats
    total = assets_collection.count_documents({})
    active = assets_collection.count_documents({"used_by_aria": True})
    now = datetime.now(timezone.utc)
    week_start = (now - timedelta(days=7)).isoformat()
    used_this_week = assets_collection.count_documents({"last_used_at": {"$gte": week_start}})
    top_cursor = list(assets_collection.find({}, {"_id": 0}).sort("usage_count", -1).limit(1))
    top = top_cursor[0] if top_cursor else None
    # By type breakdown
    by_type = {}
    for a in assets_collection.find({}, {"_id": 0, "type": 1}):
        t = a.get("type") or "message_template"
        by_type[t] = by_type.get(t, 0) + 1
    return {
        "assets": docs,
        "stats": {
            "total": total,
            "active": active,
            "used_this_week": used_this_week,
            "top_asset": top,
            "by_type": by_type,
        },
        "types": ASSET_TYPES,
    }

@router.post("/assets")
async def create_asset(payload: AssetPayload, current_user: dict = Depends(get_current_user)):
    from uuid import uuid4
    doc = payload.dict()
    doc["id"] = str(uuid4())
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    doc["updated_at"] = doc["created_at"]
    doc["usage_count"] = 0
    doc["last_used_at"] = None
    doc["created_by"] = current_user.get("id") or current_user.get("_id") or "founder"
    assets_collection.insert_one(dict(doc))  # copy to avoid _id mutation on our dict
    return {k: v for k, v in doc.items() if k != "_id"}

@router.patch("/assets/{asset_id}")
async def update_asset(asset_id: str, payload: AssetPayload, current_user: dict = Depends(get_current_user)):
    data = payload.dict()
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    res = assets_collection.update_one({"id": asset_id}, {"$set": data})
    if res.matched_count == 0:
        raise HTTPException(404, "Asset not found")
    doc = assets_collection.find_one({"id": asset_id}, {"_id": 0})
    return doc

@router.delete("/assets/{asset_id}")
async def delete_asset(asset_id: str, current_user: dict = Depends(get_current_user)):
    res = assets_collection.delete_one({"id": asset_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Asset not found")
    return {"ok": True}

@router.post("/assets/{asset_id}/use")
async def mark_asset_used(asset_id: str, current_user: dict = Depends(get_current_user)):
    now = datetime.now(timezone.utc).isoformat()
    res = assets_collection.update_one({"id": asset_id}, {"$inc": {"usage_count": 1}, "$set": {"last_used_at": now}})
    if res.matched_count == 0:
        raise HTTPException(404, "Asset not found")
    return {"ok": True}

