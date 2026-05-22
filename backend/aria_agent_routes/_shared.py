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


# ─── Iter78 S6: Playbook + assets prompt injection ──────────────────────────
def get_active_playbook_block(tenant_id: str) -> str:
    """Return a Claude-ready system-prompt snippet for the active playbook.
    Empty string if no playbook is active for this tenant.
    """
    if not tenant_id:
        return ""
    tenant = db["tenants"].find_one(
        {"id": tenant_id}, {"_id": 0, "settings.active_playbook": 1}
    ) or {}
    pb = (tenant.get("settings") or {}).get("active_playbook")
    if not pb:
        return ""
    triggers = pb.get("handoff_triggers") or []
    triggers_block = "\n".join(f"- {t}" for t in triggers) if triggers else "- (none configured)"
    return (
        "\n### ACTIVE SALES PLAYBOOK\n"
        f"You MUST follow the playbook: **{pb.get('name', 'Active playbook')}**.\n"
        f"Mode: {pb.get('what_aria_does', '')}\n"
        "Handoff to a human when ANY of the following are true:\n"
        f"{triggers_block}\n"
    )


def get_relevant_assets_block(tenant_id: str, lead_question: str = "") -> str:
    """Return objection-response + pricing + case-study assets that match the
    current lead question. Lightweight keyword routing for now — no Claude
    embedding required. Empty string if no assets configured.
    """
    if not tenant_id:
        return ""
    assets_col = db["workspace_assets"]
    docs = list(assets_col.find(
        {"tenant_id": tenant_id, "asset_type": {"$in": [
            "objection_response", "pricing_doc", "case_study", "message_template",
        ]}},
        {"_id": 0, "name": 1, "asset_type": 1, "content": 1, "tags": 1},
    ).limit(20))
    if not docs:
        return ""

    q = (lead_question or "").lower()
    triggers = {
        "objection_response": ["objection", "concern", "worried", "not sure", "expensive", "competitor"],
        "pricing_doc":       ["price", "pricing", "cost", "how much", "fee", "rate"],
        "case_study":        ["proof", "case study", "example", "customer", "success", "results"],
        "message_template":  [],   # used by campaigns, not Aria — skip from prompt
    }

    matched = []
    for d in docs:
        kind = d.get("asset_type")
        if kind == "message_template":
            continue
        keywords = triggers.get(kind, [])
        if q and not any(kw in q for kw in keywords):
            continue
        matched.append(d)

    if not matched:
        return ""

    out = ["\n### REFERENCE ASSETS (use only when relevant; never fabricate)"]
    for d in matched[:5]:
        snippet = (d.get("content") or "")[:400].replace("\n", " ")
        out.append(f"- [{d.get('asset_type')}] **{d.get('name')}**: {snippet}")
    return "\n".join(out) + "\n"

