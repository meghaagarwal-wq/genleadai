"""
ARIA AI Sales Agent — additive endpoints layered on top of the existing app.
Includes Training, Playbooks, Sales Journeys, Founder Briefs, Human Handoff,
Revival Engine, Agent Activity (dashboard), and ARIA Insights.

This module does NOT remove or modify any existing functionality.
It is registered onto the main FastAPI app via include_router-style attach.
"""
import os
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from emergentintegrations.llm.chat import LlmChat, UserMessage

router = APIRouter(prefix="/api/aria-agent", tags=["aria-agent"])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. Train ARIA
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class AriaTrainingPayload(BaseModel):
    # Business context
    what_you_sell: Optional[str] = ""
    who_you_sell_to: Optional[str] = ""
    problem_you_solve: Optional[str] = ""
    differentiator: Optional[str] = ""
    main_offerings: Optional[str] = ""
    # ICP
    target_industries: Optional[str] = ""
    target_roles: Optional[str] = ""
    company_size: Optional[str] = ""
    geography: Optional[str] = ""
    budget_range: Optional[str] = ""
    intent_signals: Optional[str] = ""
    disqualification_signals: Optional[str] = ""
    # Qualification
    qualifying_questions: Optional[str] = ""
    qualified_definition: Optional[str] = ""
    low_priority_definition: Optional[str] = ""
    when_to_book_call: Optional[str] = ""
    when_to_alert_human: Optional[str] = ""
    # Brand voice
    tone: Optional[str] = "founder_like"
    custom_voice: Optional[str] = ""
    # Objection handling
    pricing_objections: Optional[str] = ""
    timing_objections: Optional[str] = ""
    trust_concerns: Optional[str] = ""
    competitor_responses: Optional[str] = ""
    custom_faq: Optional[str] = ""
    # Booking rules
    calendar_link: Optional[str] = ""
    booking_criteria: Optional[str] = ""
    pre_call_questions: Optional[str] = ""
    reminder_timing: Optional[str] = "24h, 2h, 15m"
    no_show_message: Optional[str] = ""



# ─── Collections (module level, sourced from deps.db) ───────────────────────
from deps import db, get_current_user  # noqa: E402

training_collection = db["aria_training"]
playbooks_collection = db["aria_playbook_activations"]
leads_collection = db["leads"]
activities_collection = db["activities"]
