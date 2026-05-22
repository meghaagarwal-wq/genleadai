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
# 2. ARIA Sales Playbooks
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PLAYBOOKS = [
    {"id": "inbound_qualification", "name": "Inbound Lead Qualification",
     "best_for": "Website, WhatsApp, ad, or form leads",
     "what_aria_does": "Responds instantly, asks 2–3 qualifying questions, identifies fit, routes the next action.",
     "channels": ["WhatsApp", "Email", "Website Chat"], "touchpoints": 8,
     "handoff_triggers": ["High-ticket inquiry", "Custom solution", "Asks for founder"]},
    {"id": "demo_booking", "name": "Demo Booking",
     "best_for": "SaaS, startups, service businesses",
     "what_aria_does": "Qualifies interest, nudges toward booking, sends reminders, handles no-shows.",
     "channels": ["WhatsApp", "Email", "Calendar"], "touchpoints": 12,
     "handoff_triggers": ["Enterprise prospect", "Multiple stakeholders mentioned"]},
    {"id": "founder_led", "name": "Founder-Led Sales",
     "best_for": "Early-stage startups where founder still closes deals",
     "what_aria_does": "Handles first layer of conversation and sends founder-ready briefs before each call.",
     "channels": ["WhatsApp", "LinkedIn", "Email"], "touchpoints": 18,
     "handoff_triggers": ["Pricing discussion", "Buy signal detected", "Budget confirmed"]},
    {"id": "agency_nurture", "name": "Agency Lead Nurture",
     "best_for": "Service businesses and agencies",
     "what_aria_does": "Educates, shares proof, handles objections, books strategy calls.",
     "channels": ["Email", "WhatsApp"], "touchpoints": 14,
     "handoff_triggers": ["Custom scope request", "Multi-month engagement signal"]},
    {"id": "saas_trial", "name": "SaaS Trial to Demo",
     "best_for": "Self-serve SaaS with high-touch upgrade path",
     "what_aria_does": "Reads activation signals, nudges power users to book demo, handles billing questions.",
     "channels": ["In-app", "Email"], "touchpoints": 10,
     "handoff_triggers": ["Enterprise plan inquiry", "Custom contract request"]},
    {"id": "webinar_followup", "name": "Webinar Follow-up",
     "best_for": "Event registrations and webinar attendees",
     "what_aria_does": "Sends reminders, post-event nudges, speaker briefing, demo booking prompts.",
     "channels": ["Email", "WhatsApp"], "touchpoints": 9,
     "handoff_triggers": ["Multiple attendees from same company", "Direct reply to founder"]},
    {"id": "proposal_followup", "name": "Proposal Follow-up",
     "best_for": "Leads after a sales call who received a proposal",
     "what_aria_does": "Follows up, handles objections, nudges decision-making with proof and urgency.",
     "channels": ["Email", "WhatsApp"], "touchpoints": 7,
     "handoff_triggers": ["Negotiation request", "Competitor mentioned", "Decision delayed >2w"]},
    {"id": "lead_revival", "name": "Lead Revival",
     "best_for": "Old, silent, or lost leads",
     "what_aria_does": "Re-engages with context-aware messages tailored to why they went cold.",
     "channels": ["Email", "WhatsApp"], "touchpoints": 5,
     "handoff_triggers": ["Active reply detected", "Booking link clicked"]},
    {"id": "high_ticket", "name": "High-Ticket Consultation",
     "best_for": "Premium services, coaches, consultants, B2B offers",
     "what_aria_does": "Qualifies seriousness, budget, urgency. Books only high-quality discovery calls.",
     "channels": ["WhatsApp", "Email", "LinkedIn"], "touchpoints": 16,
     "handoff_triggers": ["Budget confirmed >$10K", "Decision-maker confirmed"]},
    {"id": "whatsapp_first", "name": "WhatsApp-First Sales",
     "best_for": "Markets where buyers prefer WhatsApp (India, MENA, LATAM)",
     "what_aria_does": "Runs full qualification, nurture, and booking inside WhatsApp.",
     "channels": ["WhatsApp"], "touchpoints": 11,
     "handoff_triggers": ["Voice note received", "Group inquiry", "Founder direct request"]},
]

@router.get("/playbooks")
async def list_playbooks(current_user: dict = Depends(get_current_user)):
    active = list(playbooks_collection.find({}, {"_id": 0}))
    active_ids = {a.get("playbook_id") for a in active}
    return {
        "playbooks": [{**p, "active": p["id"] in active_ids} for p in PLAYBOOKS],
        "active_count": len(active_ids),
    }

@router.post("/playbooks/{playbook_id}/activate")
async def activate_playbook(playbook_id: str, current_user: dict = Depends(get_current_user)):
    if not any(p["id"] == playbook_id for p in PLAYBOOKS):
        raise HTTPException(404, "Playbook not found")
    now = datetime.now(timezone.utc).isoformat()
    playbooks_collection.update_one(
        {"playbook_id": playbook_id},
        {"$set": {"playbook_id": playbook_id, "activated_at": now, "activated_by": current_user["email"]}},
        upsert=True,
    )
    return {"playbook_id": playbook_id, "activated_at": now}

@router.post("/playbooks/{playbook_id}/deactivate")
async def deactivate_playbook(playbook_id: str, current_user: dict = Depends(get_current_user)):
    playbooks_collection.delete_one({"playbook_id": playbook_id})
    return {"playbook_id": playbook_id, "active": False}

