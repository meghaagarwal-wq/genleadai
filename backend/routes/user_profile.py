"""Profile pictures — workspace owner + team members.

Avatars are stored as base64 data URLs directly in `users.avatar_url`. The
client resizes + crops on a <canvas> to 256×256 JPEG @ q=0.85 before upload
(typical payload ~30-60KB, well under MongoDB's 16MB doc limit).

Endpoints
---------
  PUT    /api/users/me/avatar               (any logged-in user)
  DELETE /api/users/me/avatar               (any logged-in user)
  PUT    /api/users/{user_email}/avatar     (owner/admin can update team member)
  DELETE /api/users/{user_email}/avatar     (owner/admin)

The membership gate lives in this file so the route doesn't depend on
external helpers — keeps the wiring trivial in server.py.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import users_collection, db, get_current_user

router = APIRouter(prefix="/api/users", tags=["users"])

# ── Limits ──────────────────────────────────────────────────────────────────
MAX_AVATAR_BYTES = 800 * 1024          # 800KB ceiling on the raw base64 string
ALLOWED_MIME = ("image/jpeg", "image/png", "image/webp")

memberships_col = db["tenant_memberships"]


class AvatarPayload(BaseModel):
    # Full data URL like `data:image/jpeg;base64,/9j/4AAQSkZ...`
    data_url: str = Field(..., min_length=20)


def _validate_data_url(data_url: str) -> str:
    """Validate the inbound data URL and return the canonical form."""
    if not data_url.startswith("data:"):
        raise HTTPException(status_code=400, detail="avatar must be a data URL")
    try:
        head, b64 = data_url.split(",", 1)
    except ValueError:
        raise HTTPException(status_code=400, detail="malformed data URL")
    mime = head.split(";")[0][5:].lower()
    if mime not in ALLOWED_MIME:
        raise HTTPException(status_code=400, detail=f"image/{{jpeg,png,webp}} only (got {mime or 'unknown'})")
    if len(data_url) > MAX_AVATAR_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"avatar too large after resize ({len(data_url)//1024}KB). Try a smaller image.",
        )
    # Decode-check: catches truncated/garbage base64
    try:
        decoded = base64.b64decode(b64, validate=True)
        if len(decoded) < 64:
            raise ValueError("too small to be a real image")
    except Exception:
        raise HTTPException(status_code=400, detail="invalid base64 image data")
    return data_url


def _is_owner_or_admin_of_same_tenant(actor: dict, target_email: str) -> bool:
    """Owner / admin can update any teammate in the same workspace."""
    if actor.get("role") in ("owner", "admin"):
        return True
    actor_email = (actor.get("email") or "").lower()
    if actor_email == target_email.lower():
        return True
    # Walk memberships — owner/admin of any tenant the target also belongs to
    target = users_collection.find_one({"email": target_email.lower()}, {"_id": 0, "id": 1})
    if not target:
        return False
    actor_tenants = {m["tenant_id"] for m in memberships_col.find({"user_id": actor.get("id")}, {"tenant_id": 1, "role": 1, "_id": 0}) if m.get("role") in ("owner", "admin")}
    if not actor_tenants:
        return False
    target_tenants = {m["tenant_id"] for m in memberships_col.find({"user_id": target.get("id")}, {"tenant_id": 1, "_id": 0})}
    return bool(actor_tenants & target_tenants)


def _persist(email: str, value: str | None) -> dict:
    update = {
        "avatar_url": value,
        "avatar_updated_at": datetime.now(timezone.utc).isoformat(),
    }
    r = users_collection.update_one({"email": email.lower()}, {"$set": update})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    u = users_collection.find_one({"email": email.lower()}, {"_id": 0, "email": 1, "full_name": 1, "avatar_url": 1, "avatar_updated_at": 1})
    return u or {}


# ── Endpoints ───────────────────────────────────────────────────────────────
@router.put("/me/avatar")
async def update_my_avatar(payload: AvatarPayload, current_user: dict = Depends(get_current_user)):
    data_url = _validate_data_url(payload.data_url)
    return {"ok": True, "user": _persist(current_user["email"], data_url)}


@router.delete("/me/avatar")
async def clear_my_avatar(current_user: dict = Depends(get_current_user)):
    return {"ok": True, "user": _persist(current_user["email"], None)}


@router.put("/{user_email}/avatar")
async def update_member_avatar(
    user_email: str,
    payload: AvatarPayload,
    current_user: dict = Depends(get_current_user),
):
    if not _is_owner_or_admin_of_same_tenant(current_user, user_email):
        raise HTTPException(status_code=403, detail="Only the user or a workspace owner/admin can update this avatar.")
    data_url = _validate_data_url(payload.data_url)
    return {"ok": True, "user": _persist(user_email, data_url)}


@router.delete("/{user_email}/avatar")
async def clear_member_avatar(user_email: str, current_user: dict = Depends(get_current_user)):
    if not _is_owner_or_admin_of_same_tenant(current_user, user_email):
        raise HTTPException(status_code=403, detail="Only the user or a workspace owner/admin can clear this avatar.")
    return {"ok": True, "user": _persist(user_email, None)}
