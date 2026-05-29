"""Legacy onboarding endpoints + Time-to-Value milestones.

Deprecated per-user onboarding paths kept for backward-compat. Real
tenant-aware onboarding lives in routes/tenants.py.

Extracted from server.py during iter125 refactor.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from pymongo import ASCENDING

from deps import (
    db,
    leads_collection,
    users_collection,
    aria_conversations_collection,
    aria_settings_collection,
    get_current_user,
)

router = APIRouter()

onboarding_collection = db["onboarding"]
ttv_collection = db["time_to_value"]


class OnboardingData(BaseModel):
    company_name: str
    founder_name: str
    industry: Optional[str] = None
    team_size: Optional[str] = None
    calendly_link: Optional[str] = None
    icp_description: Optional[str] = None
    completed: bool = False


@router.get("/api/onboarding/status_legacy")
async def get_onboarding_status(current_user: dict = Depends(get_current_user)):
    """[DEPRECATED] Per-user onboarding. Replaced by tenant-aware /api/onboarding/status in routes/tenants.py.
    Kept under a renamed path for backward-compat callers; do not use."""
    status = onboarding_collection.find_one({"user_email": current_user["email"]}, {"_id": 0})
    return {"onboarding": status, "completed": status.get("completed", False) if status else False}


@router.post("/api/onboarding/complete_legacy")
async def complete_onboarding(data: OnboardingData, current_user: dict = Depends(get_current_user)):
    """Save onboarding data and mark as complete."""
    doc = data.dict()
    doc["user_email"] = current_user["email"]
    doc["completed"] = True
    doc["completed_at"] = datetime.now(timezone.utc).isoformat()

    onboarding_collection.update_one(
        {"user_email": current_user["email"]},
        {"$set": doc},
        upsert=True
    )

    aria_settings_collection.update_one(
        {},
        {"$set": {
            "founder_name": data.founder_name,
            "company_name": data.company_name,
        }},
        upsert=True
    )

    return {"completed": True, "message": "Welcome to GenLeadAI!"}


@router.get("/api/ttv/milestones")
async def get_ttv_milestones(current_user: dict = Depends(get_current_user)):
    """Get Time to Value milestones for the current user/workspace."""
    now = datetime.now(timezone.utc)
    user_doc = users_collection.find_one({"email": current_user["email"]})
    signup_at = user_doc.get("created_at") if user_doc else now.isoformat()

    first_lead = leads_collection.find_one(
        {"created_by": {"$in": [current_user["email"], "web_form", "api", "meta_webhook"]}},
        {"created_at": 1},
        sort=[("created_at", ASCENDING)]
    )
    first_lead_at = first_lead.get("created_at") if first_lead else None

    first_aria = aria_conversations_collection.find_one(
        {"role": "aria"},
        {"created_at": 1},
        sort=[("created_at", ASCENDING)]
    )
    first_aria_at = first_aria.get("created_at") if first_aria else None

    first_meeting_lead = leads_collection.find_one(
        {"aria_state": "MEETING_BOOKED"},
        {"updated_at": 1},
        sort=[("updated_at", ASCENDING)]
    )
    first_meeting_at = first_meeting_lead.get("updated_at") if first_meeting_lead else None

    first_won = leads_collection.find_one(
        {"status": "won"},
        {"updated_at": 1},
        sort=[("updated_at", ASCENDING)]
    )
    first_won_at = first_won.get("updated_at") if first_won else None

    def time_diff_human(start_str, end_str):
        if not start_str or not end_str:
            return None
        try:
            start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
            diff = end - start
            total_seconds = diff.total_seconds()
            if total_seconds < 0:
                return None
            hours = total_seconds / 3600
            if hours < 1:
                return f"{int(total_seconds / 60)}m"
            elif hours < 24:
                return f"{hours:.1f}h"
            else:
                return f"{diff.days}d {int(hours % 24)}h"
        except Exception:
            return None

    milestones = [
        {"id": "signup", "label": "Account Created", "completed": True, "completed_at": signup_at, "time_from_start": None, "icon": "user"},
        {"id": "first_lead", "label": "First Lead Captured", "completed": first_lead_at is not None, "completed_at": first_lead_at, "time_from_start": time_diff_human(signup_at, first_lead_at), "icon": "tray"},
        {"id": "first_aria", "label": "First ARIA Conversation", "completed": first_aria_at is not None, "completed_at": first_aria_at, "time_from_start": time_diff_human(signup_at, first_aria_at), "icon": "robot"},
        {"id": "first_meeting", "label": "First Meeting Booked", "completed": first_meeting_at is not None, "completed_at": first_meeting_at, "time_from_start": time_diff_human(signup_at, first_meeting_at), "icon": "calendar"},
        {"id": "first_won", "label": "First Deal Won", "completed": first_won_at is not None, "completed_at": first_won_at, "time_from_start": time_diff_human(signup_at, first_won_at), "icon": "trophy"},
    ]

    completed_count = sum(1 for m in milestones if m["completed"])
    total_milestones = len(milestones)
    progress_pct = round((completed_count / total_milestones) * 100)

    ttv_to_meeting = time_diff_human(signup_at, first_meeting_at)

    ttv_collection.update_one(
        {"user_email": current_user["email"]},
        {"$set": {
            "milestones": milestones,
            "completed_count": completed_count,
            "progress_pct": progress_pct,
            "ttv_to_meeting": ttv_to_meeting,
            "updated_at": now.isoformat(),
        }},
        upsert=True
    )

    return {
        "milestones": milestones,
        "completed_count": completed_count,
        "total_milestones": total_milestones,
        "progress_pct": progress_pct,
        "ttv_to_meeting": ttv_to_meeting,
        "signup_at": signup_at,
    }
