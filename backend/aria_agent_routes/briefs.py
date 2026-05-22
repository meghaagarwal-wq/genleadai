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
# 4. Founder Brief
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _ai_founder_brief(lead: dict, activities: List[dict], training: dict) -> dict:
    """Use Claude to generate a founder brief grounded in lead data, activity history, and workspace training."""
    first_name = lead.get("first_name") or "Lead"
    last_name = lead.get("last_name") or ""
    company = lead.get("company_name") or "—"
    source = (lead.get("source_channel") or "—").replace("_", " ").title()
    # White-label — workspace context Aria will speak from.
    biz_name = (training.get("business_name") or training.get("company_name") or "").strip() if isinstance(training, dict) else ""
    training_snippet = ""
    if training:
        t = training
        sells = (t.get("what_you_sell") or "").strip()
        audience = (t.get("who_you_sell_to") or "").strip()
        problem = (t.get("problem_you_solve") or "").strip()
        differentiator = (t.get("differentiator") or "").strip()
        tone = (t.get("tone") or "founder_like").replace("_", " ")
        objections = (t.get("pricing_objections") or t.get("trust_concerns") or "").strip()
        training_snippet = f"""
WORKSPACE / FOUNDER CONTEXT (use for tone, framing, and language):
- Business name (use THIS as the brand on every message — never 'GenLeadAI', never 'Aria as a platform'): {biz_name or '— not configured —'}
- We sell: {sells or 'AI sales agent for founder-led businesses.'}
- We sell to: {audience or 'Startups, agencies, consultants who cannot yet hire a sales team.'}
- Problem we solve: {problem or 'Founders manually chasing leads, follow-ups slipping.'}
- Our differentiator: {differentiator or 'AI sales hire, not a CRM, not a chatbot.'}
- Tone: {tone}
- Common objections + our pre-set responses: {objections[:300] or '—'}
"""

    # Activity history compact
    activity_lines = []
    for a in (activities or [])[:12]:
        t = (a.get("activity_type") or "—").replace("_", " ")
        subj = (a.get("subject") or "").strip()[:120]
        body = (a.get("body") or a.get("notes") or "").strip()[:200]
        when = a.get("created_at") or ""
        activity_lines.append(f"- [{when[:10]}] {t}: {subj} {('· ' + body) if body else ''}")
    activities_text = "\n".join(activity_lines) if activity_lines else "(no recorded activity yet)"

    meta = lead.get("metadata") or {}
    lead_summary = f"""
LEAD:
- Name: {first_name} {last_name}
- Company: {company}
- Role: {lead.get('job_title') or '—'}
- Source: {source}
- ICP score: {lead.get('icp_score') or 0}/100
- Status: {lead.get('status') or 'new'}
- Lead temperature: {lead.get('lead_temperature') or '—'}
- Industry: {lead.get('industry') or '—'}
- Geography: {lead.get('geography') or lead.get('location') or '—'}
- Deal value: {lead.get('deal_value') or '—'}
- Pipeline type: {lead.get('pipeline_type') or '—'}
- Last contacted: {lead.get('last_contacted_at') or 'never'}
- Notes: {(meta.get('notes') or lead.get('notes') or '')[:400]}
- Known need (if captured): {meta.get('need') or '—'}
- Known pain (if captured): {meta.get('pain') or '—'}
- Known objection (if captured): {meta.get('objection') or '—'}

RECENT ACTIVITY (most recent first):
{activities_text}
"""

    # White-label — the system prompt must reflect THIS tenant's business,
    # not the platform's. Otherwise every workspace's leads see "GenLeadAI"
    # in the brief, which is the wrong brand for everyone except us.
    tenant_business_name = (
        (training.get("business_name") if isinstance(training, dict) else None)
        or (training.get("company_name") if isinstance(training, dict) else None)
        or "this business"
    )
    system = (
        f"You are ARIA — an AI sales agent for {tenant_business_name}. You prepare founder briefs before sales calls. "
        "Your output must feel like a senior sales operator wrote it: specific, decisive, no fluff, no AI-speak. "
        "Never use phrases like 'as an AI' or 'I think'. Use the founder's voice. "
        f"You ALWAYS represent {tenant_business_name} — never any other company, and never mention 'GenLeadAI' or 'Aria' as a platform. "
        "Tailor every section to THIS lead — no generic boilerplate."
    )

    prompt = f"""{training_snippet}{lead_summary}

Generate a Founder Brief for an upcoming or pending sales conversation with this lead.

Return ONLY valid JSON with EXACTLY these keys (no markdown, no commentary):
{{
  "what_they_need": "<1 sentence — what is this lead really trying to solve?>",
  "main_pain_point": "<1 sentence — root pain, not a symptom>",
  "current_process": "<1 sentence — how they're handling it today>",
  "urgency": "<one of: 'This week', 'This month', 'This quarter', 'Exploring'>",
  "budget_signal": "<one of: 'High', 'Medium-high', 'Medium', 'Low', 'Unknown'>",
  "objection": "<the single objection most likely to come up — be specific>",
  "lead_temperature": "<'hot' | 'warm' | 'cold'>",
  "recommended_pitch": "<2 sentences — exactly how to position OUR offer to THIS lead. Anchor on outcome, not features>",
  "suggested_opening": "<a single founder-style opening line, in quotes ready to deliver. Reference something specific from the lead's data>",
  "questions_to_ask": ["<question 1>", "<question 2>", "<question 3>", "<question 4>"],
  "aria_recommendation": "<2-3 sentences — what should the founder actually do on this call? specific, actionable, no platitudes>"
}}

Make every word earn its place."""

    chat = LlmChat(
        api_key=os.getenv("EMERGENT_LLM_KEY"),
        session_id=f"founder_brief_{lead.get('id') or 'unknown'}",
        system_message=system,
    )
    chat.with_model("anthropic", "claude-4-sonnet-20250514")
    resp = await chat.send_message(UserMessage(text=prompt))
    text = (resp or "").strip()
    # Robust JSON extraction
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0].strip()
    return json.loads(text)

@router.post("/founder-brief/{lead_id}")
async def generate_founder_brief(lead_id: str, current_user: dict = Depends(get_current_user)):
    from bson import ObjectId
    try:
        lead = leads_collection.find_one({"_id": ObjectId(lead_id)})
    except Exception:
        raise HTTPException(400, "Invalid lead id")
    if not lead:
        raise HTTPException(404, "Lead not found")
    lead["id"] = str(lead["_id"])
    lead.pop("_id", None)
    recent = list(activities_collection.find({"lead_id": lead_id}, {"_id": 0}).sort("created_at", -1).limit(12))
    training = training_collection.find_one({"scope": "workspace"}, {"_id": 0}) or {}

    icp = lead.get("icp_score") or 0
    source = (lead.get("source_channel") or "—").replace("_", " ").title()
    company = lead.get("company_name") or "—"
    first_name = lead.get("first_name") or "the prospect"
    lead_name = f"{lead.get('first_name','')} {lead.get('last_name','')}".strip() or "Lead"

    ai_data = None
    ai_error = None
    try:
        ai_data = await _ai_founder_brief(lead, recent, training)
    except Exception as e:
        ai_error = str(e)
        print(f"[FounderBrief] Claude generation failed for {lead_id}: {e}")

    # Fallback heuristic if Claude is unavailable / parse error
    fallback_temp = "hot" if icp >= 80 else "warm" if icp >= 50 else "cold"
    if not ai_data or not isinstance(ai_data, dict):
        ai_data = {
            "what_they_need": (lead.get("metadata") or {}).get("need") or f"Better lead response and follow-up discipline at {company}.",
            "main_pain_point": (lead.get("metadata") or {}).get("pain") or "Founder is manually managing follow-ups and leads are slipping.",
            "current_process": (lead.get("metadata") or {}).get("current") or "Manual outreach, scattered across email and WhatsApp.",
            "urgency": "This week" if icp >= 80 else "This month" if icp >= 50 else "Exploring",
            "budget_signal": "Medium-high" if icp >= 75 else "Medium" if icp >= 50 else "Unknown",
            "objection": (lead.get("metadata") or {}).get("objection") or "Wants to see how this is different from a CRM.",
            "lead_temperature": fallback_temp,
            "recommended_pitch": "Position ARIA as their first AI sales hire — not another tool. Anchor on revenue movement and reply-time, not features.",
            "suggested_opening": f"You mentioned your biggest issue is leads slipping after first contact. Let's map where the leakage is happening at {company}.",
            "questions_to_ask": [
                "Where do most of your leads come from today?",
                "What happens to a lead in the first 60 minutes after they reach you?",
                "How many of your leads do you personally still chase?",
                "If ARIA handled your first layer of sales motion, what would you do with that time?",
            ],
            "aria_recommendation": (
                f"{first_name} is showing {fallback_temp} signals from {source}. Lead with empathy, then map their funnel before pitching. "
                "Close with two specific call slots — don't ask 'when works?'."
            ),
        }

    return {
        "lead_id": lead_id,
        "lead_name": lead_name,
        "company": company,
        "role": lead.get("job_title") or "—",
        "source": source,
        "lead_temperature": ai_data.get("lead_temperature", fallback_temp),
        "what_they_need": ai_data.get("what_they_need", "—"),
        "main_pain_point": ai_data.get("main_pain_point", "—"),
        "current_process": ai_data.get("current_process", "—"),
        "urgency": ai_data.get("urgency", "—"),
        "budget_signal": ai_data.get("budget_signal", "—"),
        "objection": ai_data.get("objection", "—"),
        "recommended_pitch": ai_data.get("recommended_pitch", "—"),
        "suggested_opening": ai_data.get("suggested_opening", "—"),
        "questions_to_ask": ai_data.get("questions_to_ask", []),
        "aria_recommendation": ai_data.get("aria_recommendation", "—"),
        "recent_activities": recent,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ai_powered": ai_error is None,
        "ai_error": ai_error,
    }

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4b. ARIA's Read — conversation intelligence panel (lead detail)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/aria-read/{lead_id}")
async def aria_read(lead_id: str, current_user: dict = Depends(get_current_user)):
    from bson import ObjectId
    try:
        lead = leads_collection.find_one({"_id": ObjectId(lead_id)})
    except Exception:
        raise HTTPException(400, "Invalid lead id")
    if not lead:
        raise HTTPException(404, "Lead not found")
    lead["id"] = str(lead["_id"]); lead.pop("_id", None)
    icp = lead.get("icp_score") or 0
    status = lead.get("status") or "new"
    last_contact = lead.get("last_contacted_at")
    deal = lead.get("deal_value") or 0
    meta = lead.get("metadata") or {}

    # Temperature
    temperature = lead.get("lead_temperature") or ("hot" if icp >= 80 else "warm" if icp >= 50 else "cold")
    # Buying intent
    if status in ("proposal_sent", "negotiation", "call_booked"):
        intent = "high"
    elif icp >= 70:
        intent = "medium"
    else:
        intent = "low"
    # Urgency
    urgency = "this_week" if icp >= 80 and status in ("new", "contacted", "qualified") else \
              "this_month" if icp >= 50 else "exploring"
    # Fit score (mirror icp on a 0–10 scale)
    fit_score = round((icp or 0) / 10, 1)

    need = meta.get("need") or (
        f"Wants to automate lead response and follow-up at {lead.get('company_name') or 'their company'}." if temperature in ("hot", "warm")
        else "Exploring tools to reduce manual sales work."
    )
    pain = meta.get("pain") or "Founder still chasing leads manually — slipping in the first hour."
    objection = meta.get("objection") or (
        "Unsure how this differs from a CRM." if status == "new" else
        "Pricing or timing concern likely." if status in ("contacted", "qualified") else
        "Wants proof / case study before committing."
    )

    # Next action mapping
    if status == "new":
        next_action = "Reply with a discovery question + proof"
        suggested_response = f"Hey {lead.get('first_name','')}, ARIA here — what's slowing your sales motion the most right now: lead response, follow-up, or booking?"
    elif status == "contacted":
        next_action = "Send a tailored case study and book the call"
        suggested_response = f"Quick one — most {lead.get('industry') or 'founders'} we work with had the same pain. Want to see a 90-second walkthrough?"
    elif status in ("qualified", "proposal_sent"):
        next_action = "Founder voice note + 2 specific call slots"
        suggested_response = f"Hey {lead.get('first_name','')}, founder here. ARIA flagged you as ready — Tuesday 4 PM or Wednesday 11 AM?"
    elif status == "negotiation":
        next_action = "Address objection + close"
        suggested_response = "Happy to walk through any section of the proposal. What's the biggest unknown for you right now?"
    else:
        next_action = "Re-engage with a context-aware revival message"
        suggested_response = "Hey — what changed since we last spoke?"

    handoff_needed = bool(
        icp >= 85 or
        status in ("proposal_sent", "negotiation") or
        meta.get("competitor_mentioned") or
        meta.get("pricing_asked")
    )

    if temperature == "hot" and intent == "high":
        aria_thinks = f"This lead is HOT and ready. They've shown clear intent — don't keep them waiting."
    elif temperature == "warm" and intent == "medium":
        aria_thinks = f"This lead is warm but needs proof before booking a call."
    elif temperature == "cold":
        aria_thinks = f"This lead is cold for now. Run them through a revival journey, don't push hard."
    else:
        aria_thinks = f"Solid prospect — keep momentum and aim for the next touchpoint."

    return {
        "lead_id": lead_id,
        "temperature": temperature,
        "intent": intent,
        "urgency": urgency,
        "fit_score": fit_score,
        "icp_score": icp,
        "main_need": need,
        "main_pain": pain,
        "current_objection": objection,
        "best_next_action": next_action,
        "suggested_response": suggested_response,
        "handoff_needed": handoff_needed,
        "aria_thinks": aria_thinks,
        "deal_value": deal,
        "last_contact_at": last_contact,
    }

