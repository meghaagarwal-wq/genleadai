"""Beta feedback — capture one-liner user feedback from the Beta badge menu.

Anyone authenticated can submit feedback. Admin accounts can list and resolve.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo import DESCENDING

from deps import db, get_current_user

router = APIRouter(prefix="/api/beta-feedback", tags=["beta-feedback"])

_collection = db["beta_feedback"]


class FeedbackCreate(BaseModel):
    message: str = Field(..., min_length=3, max_length=2000)
    category: str = Field("idea", pattern="^(bug|idea|praise|other)$")
    page_url: Optional[str] = None


class FeedbackPatch(BaseModel):
    resolved: Optional[bool] = None
    admin_note: Optional[str] = None


def _require_admin(user: dict):
    if (user.get("role") or "").lower() != "admin":
        raise HTTPException(status_code=403, detail="Admin only")


@router.post("")
async def create_feedback(payload: FeedbackCreate, current_user: dict = Depends(get_current_user)):
    doc = {
        "id": f"fb_{uuid.uuid4().hex[:12]}",
        "message": payload.message.strip(),
        "category": payload.category,
        "page_url": payload.page_url,
        "user_email": current_user.get("email"),
        "user_name": current_user.get("full_name"),
        "resolved": False,
        "admin_note": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _collection.insert_one(doc)
    doc.pop("_id", None)
    return {"status": "ok", "feedback": doc}


@router.get("")
async def list_feedback(
    resolved: Optional[bool] = None,
    category: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    query = {}
    if resolved is not None:
        query["resolved"] = resolved
    if category:
        query["category"] = category
    rows = list(
        _collection.find(query, {"_id": 0}).sort("created_at", DESCENDING).limit(500)
    )
    # Counts for the admin header
    total = _collection.count_documents({})
    unresolved = _collection.count_documents({"resolved": False})
    by_category = {c: _collection.count_documents({"category": c}) for c in ("bug", "idea", "praise", "other")}
    return {
        "feedback": rows,
        "counts": {"total": total, "unresolved": unresolved, "by_category": by_category},
    }


@router.patch("/{feedback_id}")
async def update_feedback(feedback_id: str, payload: FeedbackPatch, current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    update = {k: v for k, v in payload.dict().items() if v is not None}
    if not update:
        raise HTTPException(status_code=400, detail="No fields to update")
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    res = _collection.update_one({"id": feedback_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Feedback not found")
    doc = _collection.find_one({"id": feedback_id}, {"_id": 0})
    return {"status": "ok", "feedback": doc}


@router.delete("/{feedback_id}")
async def delete_feedback(feedback_id: str, current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    res = _collection.delete_one({"id": feedback_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return {"status": "ok"}
