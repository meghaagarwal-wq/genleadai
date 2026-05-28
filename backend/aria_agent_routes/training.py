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


@router.get("/training")
async def get_training(current_user: dict = Depends(get_current_user)):
    doc = training_collection.find_one({"scope": "workspace"}, {"_id": 0}) or {}
    doc.pop("scope", None)
    # Include defaults so the form is never empty
    defaults = AriaTrainingPayload().dict()
    return {**defaults, **doc}

@router.put("/training")
async def save_training(payload: AriaTrainingPayload, current_user: dict = Depends(get_current_user)):
    data = payload.dict()
    data["scope"] = "workspace"
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    data["updated_by"] = current_user["email"]
    training_collection.update_one({"scope": "workspace"}, {"$set": data}, upsert=True)
    return {"saved": True, "trained_at": data["updated_at"]}


# Iter78 — S5: merge AI Setup Assistant extraction into Train Aria.
@router.post("/training/import-from-automap")
async def import_training_from_automap(current_user: dict = Depends(get_current_user)):
    """Pull whatever Aria extracted from the founder's GTM document
    (saved at `tenants.settings.automap_summary` by `/api/aria/auto-map/publish`)
    and prefill the Train Aria fields. Only fills BLANK fields — never
    overwrites founder-provided answers.
    """
    tid = current_user.get("tenant_id") or current_user.get("active_tenant_id")
    if not tid:
        raise HTTPException(status_code=400, detail="no_active_tenant")

    tenant = db["tenants"].find_one({"id": tid}, {"_id": 0, "settings.automap_summary": 1}) or {}
    automap = ((tenant.get("settings") or {}).get("automap_summary") or {})
    icp = (automap.get("icps") or [{}])[0] if isinstance(automap.get("icps"), list) else {}
    qual = automap.get("qualification") or {}
    handoff = automap.get("handoff") or {}

    if not automap.get("applied_at"):
        raise HTTPException(
            status_code=404,
            detail="no_automap_summary: publish an AI Setup workflow first.",
        )

    # Current training so we don't clobber non-empty answers.
    current = training_collection.find_one({"scope": "workspace"}, {"_id": 0}) or {}

    def _fill(field: str, value: str):
        v = (value or "").strip()
        if not v:
            return
        if not (current.get(field) or "").strip():
            current[field] = v

    _fill("what_you_sell", automap.get("summary") or "")
    _fill("who_you_sell_to", icp.get("label") or "")
    _fill("problem_you_solve", icp.get("pain_point") or "")
    _fill("differentiator", icp.get("value_prop") or "")
    _fill("target_industries", icp.get("industry") or "")
    _fill("target_roles", ", ".join(icp.get("title_targets") or []))
    _fill("company_size", icp.get("company_size") or "")
    _fill("geography", icp.get("geography") or "")
    _fill("qualifying_questions", "\n".join(qual.get("qualifying_questions") or []))
    _fill("qualified_definition", "\n".join(qual.get("must_have_criteria") or []))
    _fill("low_priority_definition", "\n".join(qual.get("disqualifiers") or []))
    _fill("when_to_book_call", handoff.get("trigger") or "")

    current["scope"] = "workspace"
    current["updated_at"] = datetime.now(timezone.utc).isoformat()
    current["updated_by"] = current_user["email"]
    training_collection.update_one({"scope": "workspace"}, {"$set": current}, upsert=True)

    return {
        "imported": True,
        "fields_filled": [
            k for k, v in current.items()
            if k not in ("scope", "updated_at", "updated_by") and v
        ],
        "source_applied_at": automap.get("applied_at"),
    }

