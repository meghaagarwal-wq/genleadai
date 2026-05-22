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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. AI Sales Journeys
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DEFAULT_JOURNEY = [
    {"step": 1, "name": "Instant first response", "channel": "WhatsApp", "timing": "0 min", "trigger": "New lead captured", "goal": "Acknowledge and warm them up", "personalisation": "{first_name}, {source}", "handoff_rule": "—"},
    {"step": 2, "name": "Discovery question", "channel": "WhatsApp", "timing": "+2 min", "trigger": "Reply received", "goal": "Surface the real need", "personalisation": "{company_name}", "handoff_rule": "—"},
    {"step": 3, "name": "Qualification", "channel": "WhatsApp", "timing": "+5 min", "trigger": "Reply with pain", "goal": "Score fit + intent", "personalisation": "{pain_point}", "handoff_rule": "If high-value → notify founder"},
    {"step": 4, "name": "Pain-point reply", "channel": "WhatsApp", "timing": "+1 hr", "trigger": "Pain identified", "goal": "Show empathy and direction", "personalisation": "{pain_point}, {industry}", "handoff_rule": "—"},
    {"step": 5, "name": "Proof / case study", "channel": "Email + WhatsApp", "timing": "+1 day", "trigger": "Engaged prospect", "goal": "Build credibility", "personalisation": "{closest_case_study}", "handoff_rule": "—"},
    {"step": 6, "name": "Soft booking nudge", "channel": "WhatsApp", "timing": "+2 days", "trigger": "Proof received", "goal": "Warm them to a call", "personalisation": "{founder_name}", "handoff_rule": "—"},
    {"step": 7, "name": "Follow-up reminder", "channel": "WhatsApp", "timing": "+3 days", "trigger": "No reply 48h", "goal": "Re-engage gently", "personalisation": "{first_name}", "handoff_rule": "—"},
    {"step": 8, "name": "Objection handling", "channel": "WhatsApp", "timing": "Real-time", "trigger": "Objection detected", "goal": "Resolve concern with FAQ", "personalisation": "{objection_topic}", "handoff_rule": "If pricing → founder note"},
    {"step": 9, "name": "Booking attempt", "channel": "WhatsApp + Calendar", "timing": "+5 days", "trigger": "Objection cleared", "goal": "Book a discovery call", "personalisation": "{calendar_link}", "handoff_rule": "—"},
    {"step": 10, "name": "Pre-call question", "channel": "Email", "timing": "On booking", "trigger": "Call booked", "goal": "Prep founder + lead", "personalisation": "{call_time}", "handoff_rule": "—"},
    {"step": 11, "name": "Call reminder", "channel": "WhatsApp", "timing": "24h before", "trigger": "Upcoming call", "goal": "Confirm attendance", "personalisation": "{call_time}", "handoff_rule": "—"},
    {"step": 12, "name": "No-show recovery", "channel": "WhatsApp", "timing": "30 min after", "trigger": "Missed call", "goal": "Reschedule warmly", "personalisation": "{first_name}", "handoff_rule": "—"},
    {"step": 13, "name": "Post-call follow-up", "channel": "Email + WhatsApp", "timing": "+1 hr after call", "trigger": "Call complete", "goal": "Send brief + next steps", "personalisation": "{founder_name}", "handoff_rule": "—"},
    {"step": 14, "name": "Proposal nudge", "channel": "Email", "timing": "+3 days post-call", "trigger": "Proposal sent", "goal": "Surface objections early", "personalisation": "{proposal_link}", "handoff_rule": "—"},
    {"step": 15, "name": "Decision reminder", "channel": "WhatsApp", "timing": "+7 days", "trigger": "No decision yet", "goal": "Drive close", "personalisation": "{deadline}", "handoff_rule": "If multiple opens → founder note"},
    {"step": 16, "name": "Long-term nurture", "channel": "Email", "timing": "+14 days if cold", "trigger": "Lead went cold", "goal": "Stay top of mind", "personalisation": "{industry_insight}", "handoff_rule": "—"},
    {"step": 17, "name": "Revival message", "channel": "WhatsApp", "timing": "+30 days", "trigger": "Silent 30d", "goal": "Restart conversation", "personalisation": "{first_name}", "handoff_rule": "—"},
]

JOURNEY_TEMPLATES = [
    {"id": "inbound_to_call", "name": "Inbound to booked call", "touchpoints": 11, "best_for": "Website + ad leads"},
    {"id": "webinar_to_demo", "name": "Webinar attendee to demo", "touchpoints": 9, "best_for": "Event-driven funnels"},
    {"id": "proposal_to_close", "name": "Proposal sent to close", "touchpoints": 7, "best_for": "Late-stage deals"},
    {"id": "silent_revival", "name": "Silent lead revival", "touchpoints": 5, "best_for": "Old/lost leads"},
    {"id": "founder_led_journey", "name": "Founder-led sales journey", "touchpoints": 18, "best_for": "Early-stage startups"},
]

@router.get("/journeys/default")
async def get_default_journey(current_user: dict = Depends(get_current_user)):
    return {"journey": DEFAULT_JOURNEY, "max_touchpoints": 26, "templates": JOURNEY_TEMPLATES}

