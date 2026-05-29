"""API key management endpoints. Extracted from server.py during iter125 refactor."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import get_current_user
from routes.public_api import API_KEYS_COLLECTION

router = APIRouter()


class CreateAPIKeyRequest(BaseModel):
    name: str


@router.post("/api/settings/api-keys")
async def create_api_key(request: CreateAPIKeyRequest, current_user: dict = Depends(get_current_user)):
    """Create a new API key for external integrations."""
    key = f"glai_{uuid.uuid4().hex}"
    doc = {
        "key": key,
        "name": request.name,
        "created_by": current_user["email"],
        "is_active": True,
        "usage_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    API_KEYS_COLLECTION.insert_one(doc)
    return {"key": key, "name": request.name, "message": "API key created. Store it securely — it won't be shown again."}


@router.get("/api/settings/api-keys")
async def list_api_keys(current_user: dict = Depends(get_current_user)):
    """List all API keys (masked)."""
    keys = list(API_KEYS_COLLECTION.find({}, {"_id": 0}))
    for k in keys:
        k["key"] = k["key"][:8] + "..." + k["key"][-4:]
    return {"keys": keys}


@router.delete("/api/settings/api-keys/{key_prefix}")
async def revoke_api_key(key_prefix: str, current_user: dict = Depends(get_current_user)):
    """Revoke an API key."""
    result = API_KEYS_COLLECTION.update_one(
        {"key": {"$regex": f"^{key_prefix}"}},
        {"$set": {"is_active": False}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="API key not found")
    return {"revoked": True}
