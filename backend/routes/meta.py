"""Calendly scheduling endpoints and lightweight meta endpoints."""
from fastapi import APIRouter, Depends

from deps import get_current_user, users_collection, db
from aria_agent import (
    get_calendly_event_types,
    get_calendly_availability,
    get_calendly_user,
)

router = APIRouter(tags=["meta"])


@router.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "GenLeadAI LMS API"}


@router.get("/api/users")
async def get_users(current_user: dict = Depends(get_current_user)):
    """Iter 71 — return ONLY users who are members of the caller's active tenant.

    Previously this returned every user across every tenant, which made
    every workspace's team page show the entire app's user list. Now it
    joins on tenant_memberships scoped to the active tenant_id, so the
    Pietential workspace only sees Pietential team members.
    """
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        # Legacy account with no tenant — just return themselves.
        me = users_collection.find_one({"email": current_user["email"]}, {"password_hash": 0, "_id": 0})
        return {"users": [me] if me else []}

    memberships = list(
        db["tenant_memberships"].find(
            {"tenant_id": tenant_id, "status": {"$in": ["active", "invited", None]}},
            {"_id": 0, "user_email": 1, "role": 1, "status": 1, "joined_at": 1},
        )
    )
    member_emails = [m.get("user_email") for m in memberships if m.get("user_email")]
    if not member_emails:
        return {"users": []}
    role_by_email = {m["user_email"]: m for m in memberships if m.get("user_email")}

    users = list(
        users_collection.find(
            {"email": {"$in": member_emails}, "is_active": True},
            {"password_hash": 0, "_id": 0},
        ).limit(100)
    )
    # Attach tenant role + membership status to each user record so the UI
    # can show "Owner / Admin / Member / Viewer" + invited vs active.
    for u in users:
        m = role_by_email.get(u.get("email")) or {}
        u["role"] = m.get("role") or "member"
        u["membership_status"] = m.get("status") or "active"
    return {"users": users}


@router.get("/api/calendly/event-types")
async def get_event_types(current_user: dict = Depends(get_current_user)):
    event_types = await get_calendly_event_types()
    return {"event_types": event_types}


@router.get("/api/calendly/availability/{event_type_uri:path}")
async def get_availability(event_type_uri: str, current_user: dict = Depends(get_current_user)):
    slots = await get_calendly_availability(event_type_uri)
    return {"available_slots": slots}


@router.get("/api/calendly/user")
async def get_calendly_user_info(current_user: dict = Depends(get_current_user)):
    user = await get_calendly_user()
    return {"user": user}
