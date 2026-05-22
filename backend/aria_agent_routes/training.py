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
from emergentintegrations.llm.chat import LlmChat, UserMessage
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

