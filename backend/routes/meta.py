"""Calendly scheduling endpoints and lightweight meta endpoints."""
from fastapi import APIRouter, Depends

from deps import get_current_user, users_collection
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
    users = list(
        users_collection.find({"is_active": True}, {"password_hash": 0, "_id": 0}).limit(100)
    )
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
