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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 6. Revival Engine
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

REVIVAL_JOURNEY = [
    {"day": 1, "label": "Gentle check-in", "channel": "WhatsApp", "goal": "Re-open conversation"},
    {"day": 4, "label": "Value / proof message", "channel": "Email", "goal": "Remind of outcome"},
    {"day": 9, "label": "Pain-point reminder", "channel": "WhatsApp", "goal": "Reactivate the original need"},
    {"day": 15, "label": "Founder-style note", "channel": "WhatsApp", "goal": "Personal escalation"},
    {"day": 30, "label": "Long-term nurture", "channel": "Email", "goal": "Stay top of mind"},
]

@router.get("/revival/segments")
async def revival_segments(current_user: dict = Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    cutoff_silent = (now - timedelta(days=14)).isoformat()
    cutoff_old = (now - timedelta(days=60)).isoformat()
    silent_count = leads_collection.count_documents({"status": {"$in": ["contacted", "qualified"]}, "last_contacted_at": {"$lte": cutoff_silent}})
    ghosted_count = leads_collection.count_documents({"status": "proposal_sent", "last_contacted_at": {"$lte": cutoff_silent}})
    proposal_no_decision = leads_collection.count_documents({"status": "proposal_sent"})
    old_leads = leads_collection.count_documents({"created_at": {"$lte": cutoff_old}, "status": {"$nin": ["won", "lost"]}})
    webinar_count = leads_collection.count_documents({"source_channel": "webinar", "status": "new"})
    past_inquiries = leads_collection.count_documents({"status": "unqualified"})

    segments = [
        {"id": "silent_first_reply", "name": "Silent after first reply", "count": max(silent_count, 0),
         "message_angle": "Empathy + curiosity — 'is this still on your radar?'", "channel": "WhatsApp",
         "cadence": "Day 1 → Day 4 → Day 9", "goal": "Restart conversation"},
        {"id": "ghosted_after_pricing", "name": "Ghosted after pricing", "count": max(ghosted_count, 0),
         "message_angle": "ROI and opportunity loss", "channel": "Email + WhatsApp",
         "cadence": "Day 1 → Day 7", "goal": "Restart conversation or book call"},
        {"id": "no_show", "name": "No-showed call", "count": 0,
         "message_angle": "Warm reschedule, no shame", "channel": "WhatsApp",
         "cadence": "30 min after → Day 2", "goal": "Reschedule"},
        {"id": "proposal_no_decision", "name": "Proposal sent but no decision", "count": max(proposal_no_decision, 0),
         "message_angle": "Founder voice + specific deadline framing", "channel": "Email",
         "cadence": "Day 3 → Day 7 → Day 14", "goal": "Drive decision"},
        {"id": "old_leads", "name": "Old leads (60+ days)", "count": max(old_leads, 0),
         "message_angle": "What's changed since we last spoke", "channel": "Email",
         "cadence": "Single nurture", "goal": "Surface still-active leads"},
        {"id": "webinar_no_book", "name": "Webinar attendees who never booked", "count": max(webinar_count, 0),
         "message_angle": "Replay + 1:1 strategy session", "channel": "Email",
         "cadence": "Day 1 → Day 5", "goal": "Book strategy call"},
        {"id": "past_inquiries", "name": "Past inquiries", "count": max(past_inquiries, 0),
         "message_angle": "What's new in the product", "channel": "Email",
         "cadence": "Quarterly", "goal": "Re-qualify with fresh signal"},
    ]
    return {"segments": segments, "default_journey": REVIVAL_JOURNEY}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
