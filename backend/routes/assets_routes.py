"""iter108 — ACTION 3: server.py refactor.

Workspace asset upload / list / download / patch / delete extracted from
server.py:1269-1362. Behaviour preserved 1:1 (same paths, same payloads,
same status codes). Only the host moved from `@app` to `APIRouter`.

Why this file? Asset endpoints are completely self-contained — they only
touch `workspace_assets_collection` and the object-storage helpers from
`aria_agent`. No call sites in the rest of server.py reach into them, so
extraction is risk-free.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Response, UploadFile
from pymongo import DESCENDING

from aria_agent import get_object, put_object
from deps import get_current_user, serialize_doc, workspace_assets_collection

router = APIRouter(tags=["assets"])


@router.post("/api/assets/upload")
async def upload_asset(
    file: UploadFile = File(...),
    asset_type: str = "brand_deck",
    send_in_first_touch: bool = True,
    current_user: dict = Depends(get_current_user),
):
    """Upload an asset (PDF, document, image) to object storage."""
    try:
        data = await file.read()
        file_size_kb = len(data) / 1024
        if file_size_kb > 10240:  # 10MB limit
            raise HTTPException(status_code=400, detail="File too large (max 10MB)")
        ext = file.filename.split(".")[-1] if "." in file.filename else "bin"
        storage_path = f"genleadai/assets/{uuid.uuid4()}.{ext}"
        result = put_object(storage_path, data, file.content_type or "application/octet-stream")
        asset_doc = {
            "asset_type": asset_type,
            "name": file.filename,
            "storage_path": result.get("path", storage_path),
            "original_filename": file.filename,
            "file_size_kb": round(file_size_kb, 2),
            "mime_type": file.content_type or "application/octet-stream",
            "is_active": True,
            "send_in_first_touch": send_in_first_touch,
            "send_count": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        workspace_assets_collection.insert_one(asset_doc)
        return serialize_doc(asset_doc)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/api/assets")
async def get_assets(current_user: dict = Depends(get_current_user)):
    """Get all workspace assets."""
    assets = list(workspace_assets_collection.find({"is_active": True}).sort("created_at", DESCENDING))
    return {"assets": [serialize_doc(a) for a in assets]}


@router.get("/api/assets/download/{asset_id}")
async def download_asset(asset_id: str, auth: str = Query(None), authorization: str = Header(None)):
    """Download an asset file."""
    try:
        asset = workspace_assets_collection.find_one({"_id": ObjectId(asset_id)})
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        data, content_type = get_object(asset["storage_path"])
        return Response(
            content=data,
            media_type=asset.get("mime_type", content_type),
            headers={"Content-Disposition": f'attachment; filename="{asset.get("original_filename", "file")}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@router.patch("/api/assets/{asset_id}")
async def update_asset(asset_id: str, current_user: dict = Depends(get_current_user)):
    """Toggle asset settings (send_in_first_touch flip)."""
    asset = workspace_assets_collection.find_one({"_id": ObjectId(asset_id)})
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    new_val = not asset.get("send_in_first_touch", False)
    workspace_assets_collection.update_one(
        {"_id": ObjectId(asset_id)},
        {"$set": {"send_in_first_touch": new_val, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"send_in_first_touch": new_val}


@router.delete("/api/assets/{asset_id}")
async def delete_asset(asset_id: str, current_user: dict = Depends(get_current_user)):
    """Soft-delete an asset."""
    workspace_assets_collection.update_one(
        {"_id": ObjectId(asset_id)},
        {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"message": "Asset deleted"}
