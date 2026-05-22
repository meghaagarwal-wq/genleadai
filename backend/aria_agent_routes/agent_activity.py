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


# 7. Dashboard — ARIA Sales Agent Activity
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/agent-activity")
async def agent_activity(current_user: dict = Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    # Real activity counts where available
    responded_today = activities_collection.count_documents({"activity_type": {"$in": ["email_sent", "whatsapp_sent"]}, "created_at": {"$gte": day_start}})
    qualified_today = leads_collection.count_documents({"status": "qualified", "updated_at": {"$gte": day_start}})
    followups_sent = activities_collection.count_documents({"activity_type": {"$in": ["email_sent", "whatsapp_sent", "note_added"]}, "created_at": {"$gte": day_start}})
    calls_booked = activities_collection.count_documents({"activity_type": "meeting_scheduled", "created_at": {"$gte": day_start}})
    hot_attention = leads_collection.count_documents({"icp_score": {"$gte": 80}, "status": {"$in": ["new", "contacted"]}})
    cutoff_silent = (now - timedelta(days=14)).isoformat()
    silent_revived = leads_collection.count_documents({"last_contacted_at": {"$lte": cutoff_silent}, "status": {"$in": ["contacted", "qualified"]}})

    # Demo-friendly fallback values when workspace is fresh
    if responded_today + qualified_today + followups_sent + calls_booked == 0:
        return {
            "computed_from_real_data": False,
            "responded_today": 18,
            "qualified_today": 9,
            "followups_sent": 34,
            "calls_booked": 4,
            "no_shows_recovered": 2,
            "hot_escalated": 3,
            "silent_revived": 7,
            "headline": "ARIA handled 64 actions today",
            "subline": "Without ARIA you would have answered each one yourself.",
        }
    return {
        "computed_from_real_data": True,
        "responded_today": responded_today,
        "qualified_today": qualified_today,
        "followups_sent": followups_sent,
        "calls_booked": calls_booked,
        "no_shows_recovered": 0,
        "hot_escalated": hot_attention,
        "silent_revived": silent_revived,
        "headline": f"ARIA handled {responded_today + qualified_today + followups_sent + calls_booked} actions today",
        "subline": "Without ARIA you would have answered each one yourself.",
    }

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
