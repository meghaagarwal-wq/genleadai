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
# 10. ARIA Brain — consolidated knowledge map
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BRAIN_SECTIONS = [
    {"id": "business", "label": "About your business", "icon": "Buildings",
     "fields": ["what_you_sell", "who_you_sell_to", "problem_you_solve", "differentiator", "main_offerings"]},
    {"id": "icp", "label": "Your ICP", "icon": "Crosshair",
     "fields": ["target_industries", "target_roles", "company_size", "geography", "budget_range", "intent_signals", "disqualification_signals"]},
    {"id": "qualification", "label": "Qualifying logic", "icon": "Funnel",
     "fields": ["qualifying_questions", "qualified_definition", "low_priority_definition", "when_to_book_call", "when_to_alert_human"]},
    {"id": "voice", "label": "Brand voice", "icon": "Waveform",
     "fields": ["tone", "custom_voice"]},
    {"id": "objections", "label": "Objection handling", "icon": "ShieldCheck",
     "fields": ["pricing_objections", "timing_objections", "trust_concerns", "competitor_responses", "custom_faq"]},
    {"id": "booking", "label": "Booking rules", "icon": "CalendarCheck",
     "fields": ["calendar_link", "booking_criteria", "pre_call_questions", "reminder_timing", "no_show_message"]},
]

FIELD_LABELS = {
    "what_you_sell": "What you sell", "who_you_sell_to": "Who you sell to",
    "problem_you_solve": "Problem you solve", "differentiator": "Differentiator",
    "main_offerings": "Main offerings",
    "target_industries": "Target industries", "target_roles": "Target roles",
    "company_size": "Company size", "geography": "Geography", "budget_range": "Budget range",
    "intent_signals": "Intent signals", "disqualification_signals": "Disqualifiers",
    "qualifying_questions": "Qualifying questions", "qualified_definition": "What 'qualified' means",
    "low_priority_definition": "Low-priority definition", "when_to_book_call": "When to book a call",
    "when_to_alert_human": "When to alert you",
    "tone": "Tone", "custom_voice": "Custom voice notes",
    "pricing_objections": "Pricing objections", "timing_objections": "Timing objections",
    "trust_concerns": "Trust concerns", "competitor_responses": "Competitor responses",
    "custom_faq": "Custom FAQ",
    "calendar_link": "Calendar link", "booking_criteria": "Booking criteria",
    "pre_call_questions": "Pre-call questions", "reminder_timing": "Reminder timing",
    "no_show_message": "No-show message",
}

@router.get("/brain")
async def aria_brain(current_user: dict = Depends(get_current_user)):
    training = training_collection.find_one({"scope": "workspace"}, {"_id": 0}) or {}
    training.pop("scope", None)
    training.pop("updated_at", None)

    sections_out = []
    total_fields = 0
    filled_fields = 0
    gaps = []
    for sec in BRAIN_SECTIONS:
        items = []
        sec_filled = 0
        for f in sec["fields"]:
            val = (training.get(f) or "").strip() if isinstance(training.get(f), str) else training.get(f)
            filled = bool(val) and val != "founder_like" if f == "tone" else bool(val)
            # For tone, we count any value (default "founder_like") as filled
            if f == "tone":
                filled = bool(val)
            items.append({
                "key": f,
                "label": FIELD_LABELS.get(f, f.replace("_", " ").title()),
                "value": val if filled else "",
                "filled": filled,
            })
            total_fields += 1
            if filled:
                filled_fields += 1
                sec_filled += 1
            else:
                gaps.append({"section": sec["id"], "section_label": sec["label"], "field": f, "label": FIELD_LABELS.get(f, f)})
        sections_out.append({
            "id": sec["id"], "label": sec["label"], "icon": sec["icon"],
            "filled": sec_filled, "total": len(sec["fields"]),
            "completion_pct": round(sec_filled / max(len(sec["fields"]), 1) * 100),
            "items": items,
        })

    completion_pct = round(filled_fields / max(total_fields, 1) * 100)

    # Live learnings derived from workspace data
    leads_total = leads_collection.count_documents({})
    wins = leads_collection.count_documents({"status": "won"})
    hot = leads_collection.count_documents({"icp_score": {"$gte": 80}})
    # Top source
    src_counts = {}
    for l in leads_collection.find({}, {"_id": 0, "source_channel": 1}):
        s = (l.get("source_channel") or "other").replace("_", " ").title()
        src_counts[s] = src_counts.get(s, 0) + 1
    top_source = max(src_counts, key=src_counts.get) if src_counts else "—"
    # Top objection from lost_reason
    lost_reasons = {}
    for l in leads_collection.find({"status": "lost"}, {"_id": 0, "lost_reason": 1}):
        r = (l.get("lost_reason") or "unspecified").replace("_", " ").title()
        lost_reasons[r] = lost_reasons.get(r, 0) + 1
    top_loss = max(lost_reasons, key=lost_reasons.get) if lost_reasons else "—"

    learnings = [
        {"label": "Leads tracked", "value": str(leads_total), "hint": "Total conversations ARIA has context on."},
        {"label": "Wins recorded", "value": str(wins), "hint": "ARIA learns from every closed-won."},
        {"label": "Top source", "value": top_source, "hint": "Where most of your pipeline comes from."},
        {"label": "Top loss reason", "value": top_loss, "hint": "ARIA watches this and adjusts rebuttals."},
        {"label": "Hot leads in memory", "value": str(hot), "hint": "ICP ≥ 80 — ARIA prioritises these."},
    ]

    return {
        "completion_pct": completion_pct,
        "filled_fields": filled_fields,
        "total_fields": total_fields,
        "sections": sections_out,
        "gaps": gaps[:8],
        "learnings": learnings,
        "headline": (
            "ARIA is fully trained and running your sales motion." if completion_pct >= 85
            else f"ARIA is {completion_pct}% trained — close the gaps to sharpen every reply."
        ),
    }

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
