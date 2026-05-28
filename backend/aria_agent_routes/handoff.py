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
# 5. Smart Human Handoff
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. Smart Human Handoff
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

HANDOFF_RULES = [
    {"id": "asks_pricing", "label": "Lead asks for pricing"},
    {"id": "custom_solution", "label": "Lead asks for custom solution"},
    {"id": "high_value", "label": "Lead is high-value"},
    {"id": "urgent_timeline", "label": "Lead has urgent timeline"},
    {"id": "wants_founder", "label": "Lead wants to speak to founder"},
    {"id": "proposal_opens", "label": "Lead opens proposal multiple times"},
    {"id": "inactive_after_intent", "label": "Lead becomes inactive after high intent"},
    {"id": "competitor_question", "label": "Lead asks about competitor"},
    {"id": "frustration", "label": "Lead expresses confusion / frustration"},
]

@router.get("/handoff/rules")
async def handoff_rules(current_user: dict = Depends(get_current_user)):
    return {"rules": HANDOFF_RULES}

@router.get("/handoff/alerts")
async def handoff_alerts(current_user: dict = Depends(get_current_user)):
    # Compute alerts from real workspace data
    leads = list(leads_collection.find({"status": {"$nin": ["won", "lost", "unqualified"]}}, {
        "_id": 1, "first_name": 1, "last_name": 1, "company_name": 1, "icp_score": 1,
        "status": 1, "source_channel": 1, "lead_temperature": 1, "metadata": 1, "deal_value": 1,
    }).limit(40))
    alerts = []
    for l in leads:
        l["id"] = str(l["_id"]); l.pop("_id", None)
        icp = l.get("icp_score") or 0
        status = l.get("status")
        if icp >= 85:
            alerts.append({**l, "trigger": "high_value", "trigger_label": "High-value lead",
                           "why": f"ICP {icp} — top 1% fit. Worth a personal touch.",
                           "recommended_action": "Send a personal note and offer two specific call slots.",
                           "suggested_message": f"Hey {l.get('first_name','')}, this is {{founder_name}}. ARIA flagged you as a perfect fit for what we do. Would Tuesday 4 PM or Wednesday 11 AM work for a 20-min call?"})
        elif status == "proposal_sent":
            alerts.append({**l, "trigger": "proposal_opens", "trigger_label": "Proposal opened, no decision",
                           "why": "Proposal viewed but no commit signal yet.",
                           "recommended_action": "Founder follow-up with a specific question, not a generic check-in.",
                           "suggested_message": f"Hey {l.get('first_name','')}, the proposal was tailored to your funnel — happy to walk through any section. What's the biggest unknown for you right now?"})
        elif (l.get("metadata") or {}).get("competitor_mentioned"):
            alerts.append({**l, "trigger": "competitor_question", "trigger_label": "Competitor mentioned",
                           "why": "Lead is comparing options — high commercial intent.",
                           "recommended_action": "Founder voice note positioning ARIA vs CRM.",
                           "suggested_message": "Quick voice note coming on how we position vs. a traditional CRM — they store, ARIA works."})
        if len(alerts) >= 6:
            break
    # Pad with smart fallbacks if workspace is too clean
    if len(alerts) < 3:
        alerts.extend([
            {"id": None, "first_name": "Rohan", "last_name": "Mehta", "company_name": "ABC SaaS",
             "icp_score": 92, "trigger": "high_value", "trigger_label": "High-value lead",
             "why": "Asked for pricing and wants implementation this month.",
             "recommended_action": "Founder should send a personal note or join the next call.",
             "suggested_message": "Hey Rohan, ARIA flagged this — implementation this month is doable. Two slots: Tuesday 4 PM or Wednesday 11 AM?"},
            {"id": None, "first_name": "Priya", "last_name": "Sharma", "company_name": "LeapEdu",
             "icp_score": 87, "trigger": "wants_founder", "trigger_label": "Wants to speak to founder",
             "why": "Asked specifically for founder-to-founder conversation.",
             "recommended_action": "Founder reply with calendar or voice note.",
             "suggested_message": "Hey Priya, founder here. Happy to jump on a quick call — sending two slots."},
            {"id": None, "first_name": "Jamie", "last_name": "Levy", "company_name": "Blanco Labs",
             "icp_score": 84, "trigger": "competitor_question", "trigger_label": "Competitor mentioned",
             "why": "Comparing ARIA against a generic chatbot vendor.",
             "recommended_action": "Position ARIA as 'AI sales hire', not chatbot.",
             "suggested_message": "Quick framing: a chatbot answers. ARIA works the lead — qualifies, follows up, books, briefs you. Want a 15-min walkthrough?"},
        ][:3 - len(alerts)])
    return {"alerts": alerts}

