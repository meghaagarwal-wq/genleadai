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


def _aria_agent_endpoints(app, get_current_user, db):
    training_collection = db["aria_training"]
    playbooks_collection = db["aria_playbook_activations"]
    leads_collection = db["leads"]
    activities_collection = db["activities"]

    @router.get("/training")
    async def get_training(current_user: dict = Depends(get_current_user)):
        doc = training_collection.find_one({"scope": "workspace"}, {"_id": 0}) or {}
        doc.pop("scope", None)
        # Include defaults so the form is never empty
        defaults = AriaTrainingPayload().dict()
        return {**defaults, **doc}

    @router.put("/training")
    async def save_training(payload: AriaTrainingPayload, current_user: dict = Depends(get_current_user)):
        data = payload.dict()
        data["scope"] = "workspace"
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        data["updated_by"] = current_user["email"]
        training_collection.update_one({"scope": "workspace"}, {"$set": data}, upsert=True)
        return {"saved": True, "trained_at": data["updated_at"]}

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

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 4. Founder Brief
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    training_collection_ref = training_collection

    async def _ai_founder_brief(lead: dict, activities: List[dict], training: dict) -> dict:
        """Use Claude to generate a founder brief grounded in lead data, activity history, and workspace training."""
        first_name = lead.get("first_name") or "Lead"
        last_name = lead.get("last_name") or ""
        company = lead.get("company_name") or "—"
        source = (lead.get("source_channel") or "—").replace("_", " ").title()
        # Compact training snippet for the prompt
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

        system = (
            "You are ARIA — an AI sales agent for GenLeadAI. You prepare founder briefs before sales calls. "
            "Your output must feel like a senior sales operator wrote it: specific, decisive, no fluff, no AI-speak. "
            "Never use phrases like 'as an AI' or 'I think'. Use the founder's voice. "
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
        training = training_collection_ref.find_one({"scope": "workspace"}, {"_id": 0}) or {}

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

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 9. Workspace experience — Stories + Lead Feed + Morning Brief + Ask ARIA Reply
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    SIGNAL_CATALOG = {
        # signal_id → (label, why, action, color)
        "proposal_viewed":   {"label": "Proposal Viewed",   "icon": "FileText",    "accent": "#C044E0"},
        "demo_intent":       {"label": "Demo Intent",       "icon": "CalendarCheck", "accent": "#16A34A"},
        "pricing_signal":    {"label": "Pricing Signal",    "icon": "CurrencyCircleDollar", "accent": "#D97706"},
        "hot_lead":          {"label": "Hot Lead",          "icon": "Fire",        "accent": "#DC2626"},
        "followup_due":      {"label": "Follow-up Due",     "icon": "Clock",       "accent": "#7C35DC"},
        "founder_needed":    {"label": "Founder Needed",    "icon": "Robot",       "accent": "#7C35DC"},
        "sleeping_gold":     {"label": "Sleeping Gold",     "icon": "Snowflake",   "accent": "#0EA5E9"},
        "revive_today":      {"label": "Revive Today",      "icon": "ArrowClockwise", "accent": "#0EA5E9"},
        "new_lead":          {"label": "New Lead Captured", "icon": "Sparkle",     "accent": "#7C35DC"},
        "lead_replied":      {"label": "Lead Replied",      "icon": "ChatCircle",  "accent": "#16A34A"},
        "lead_opened":       {"label": "Email Opened",      "icon": "EnvelopeOpen", "accent": "#7C35DC"},
        "high_intent":       {"label": "High-Intent Reactivated", "icon": "Lightning", "accent": "#DC2626"},
    }

    def _lead_initials(l):
        fn = (l.get("first_name") or "").strip()
        ln = (l.get("last_name") or "").strip()
        if fn or ln:
            return (fn[:1] + ln[:1]).upper() or "LD"
        return (l.get("company_name") or "LD")[:2].upper()

    def _classify_lead_signal(lead, activities_by_lead):
        """Map a lead into the most-relevant workspace signal type."""
        icp = lead.get("icp_score") or 0
        status = lead.get("status")
        last_contact = lead.get("last_contacted_at")
        next_followup = lead.get("next_followup_at")
        now_utc = datetime.now(timezone.utc)
        meta = lead.get("metadata") or {}

        if status == "proposal_sent":
            return "proposal_viewed", f"ARIA is watching this proposal for re-opens and decision signals."
        if meta.get("pricing_asked") or meta.get("competitor_mentioned"):
            return "pricing_signal", "Lead asked about pricing — high commercial intent."
        if icp >= 85 and status in ("new", "contacted", "qualified"):
            return "hot_lead", f"ICP {icp} — top-percentile fit. Don't keep this one waiting."
        if icp >= 75 and meta.get("wants_founder"):
            return "founder_needed", "Lead specifically asked for founder-to-founder conversation."
        if next_followup:
            try:
                nf = datetime.fromisoformat(next_followup.replace("Z", "+00:00")) if isinstance(next_followup, str) else next_followup
                if nf <= now_utc:
                    return "followup_due", "Follow-up is due. ARIA drafted a reply ready for your approval."
            except Exception:
                pass
        if status == "qualified" and icp >= 70:
            return "demo_intent", "Qualified fit. ARIA suggests nudging toward a discovery call."
        if last_contact:
            try:
                lc = datetime.fromisoformat(last_contact.replace("Z", "+00:00")) if isinstance(last_contact, str) else last_contact
                days_cold = (now_utc - lc).days
                if days_cold >= 21 and icp >= 70:
                    return "sleeping_gold", f"Went cold {days_cold} days ago but was a strong fit. Worth a revival."
                if days_cold >= 14:
                    return "revive_today", f"Silent for {days_cold} days. ARIA can restart the conversation."
            except Exception:
                pass
        if status == "new":
            return "new_lead", "Captured recently. ARIA will make first contact if you want."
        return "lead_opened", "Recent activity detected."

    def _aria_recommendation(signal_id, lead):
        name = lead.get("first_name") or "this lead"
        company = lead.get("company_name") or "their company"
        recs = {
            "proposal_viewed": f"Send a founder-style WhatsApp nudge to {name} — short, proof-led, with one specific question.",
            "pricing_signal": f"Reply with ROI framing, not price. Push for a 15-min call with 2 specific slots.",
            "hot_lead": f"This is a now-or-never moment. Founder voice note + 2 calendar slots.",
            "followup_due": f"Pick up where you left off. ARIA has the thread context ready — tap Ask ARIA to Reply.",
            "founder_needed": f"Reply yourself. ARIA drafted an opener in your founder voice.",
            "sleeping_gold": f"Revival message: 'What changed since we last spoke at {company}?'",
            "revive_today": f"Gentle check-in on WhatsApp. Reference the original pain point.",
            "demo_intent": f"Offer a 20-min discovery call. Lead with a specific outcome they'd care about.",
            "new_lead": f"Open with a discovery question, not a pitch. ARIA can send the first touch.",
            "lead_replied": f"They're warm. Keep momentum with a concrete next step.",
            "lead_opened": f"They read you. Send the next touchpoint while you're top of mind.",
            "high_intent": f"Reactivation window. Strike now with a specific, outcome-led message.",
        }
        return recs.get(signal_id, "Ask ARIA to send the next best touchpoint.")

    @router.get("/workspace/stories")
    async def workspace_stories(limit: int = 12, current_user: dict = Depends(get_current_user)):
        """Instagram-style horizontal story rings — high-signal leads needing attention now."""
        leads = list(leads_collection.find({"status": {"$nin": ["won", "lost", "unqualified"]}}, {
            "_id": 1, "first_name": 1, "last_name": 1, "company_name": 1,
            "icp_score": 1, "status": 1, "source_channel": 1, "lead_temperature": 1,
            "last_contacted_at": 1, "next_followup_at": 1, "metadata": 1, "job_title": 1,
        }).sort("icp_score", -1).limit(limit * 3))
        stories = []
        for l in leads:
            l["id"] = str(l["_id"]); l.pop("_id", None)
            sig, why = _classify_lead_signal(l, None)
            meta = SIGNAL_CATALOG.get(sig, SIGNAL_CATALOG["new_lead"])
            icp = l.get("icp_score") or 0
            temperature = l.get("lead_temperature") or ("hot" if icp >= 80 else "warm" if icp >= 50 else "cold")
            stories.append({
                "lead_id": l["id"],
                "name": f"{l.get('first_name','')} {l.get('last_name','')}".strip() or "Lead",
                "first_name": l.get("first_name") or "",
                "initials": _lead_initials(l),
                "company": l.get("company_name") or "—",
                "role": l.get("job_title") or "",
                "signal": sig,
                "signal_label": meta["label"],
                "signal_accent": meta["accent"],
                "signal_icon": meta["icon"],
                "temperature": temperature,
                "icp_score": icp,
                "snippet": why,
                "source": (l.get("source_channel") or "—").replace("_", " ").title(),
            })
            if len(stories) >= limit:
                break
        return {"stories": stories}

    @router.get("/workspace/story-card/{lead_id}")
    async def workspace_story_card(lead_id: str, current_user: dict = Depends(get_current_user)):
        """Full story-card payload when a user taps a story ring."""
        from bson import ObjectId
        try:
            lead = leads_collection.find_one({"_id": ObjectId(lead_id)})
        except Exception:
            raise HTTPException(400, "Invalid lead id")
        if not lead:
            raise HTTPException(404, "Lead not found")
        lead["id"] = str(lead["_id"]); lead.pop("_id", None)
        sig, why = _classify_lead_signal(lead, None)
        meta = SIGNAL_CATALOG.get(sig, SIGNAL_CATALOG["new_lead"])
        icp = lead.get("icp_score") or 0
        temperature = lead.get("lead_temperature") or ("hot" if icp >= 80 else "warm" if icp >= 50 else "cold")
        last_acts = list(activities_collection.find({"lead_id": lead_id}, {"_id": 0}).sort("created_at", -1).limit(3))
        last_interaction = "No recent activity logged."
        if last_acts:
            first = last_acts[0]
            t = (first.get("activity_type") or "—").replace("_", " ")
            last_interaction = f"{t}: {first.get('subject') or first.get('body', '')[:120]}"
        return {
            "lead_id": lead_id,
            "name": f"{lead.get('first_name','')} {lead.get('last_name','')}".strip() or "Lead",
            "first_name": lead.get("first_name") or "",
            "company": lead.get("company_name") or "—",
            "role": lead.get("job_title") or "—",
            "temperature": temperature,
            "icp_score": icp,
            "signal": sig,
            "signal_label": meta["label"],
            "signal_accent": meta["accent"],
            "what_happened": why,
            "why_it_matters": f"{meta['label']} detected for a lead scoring {icp}/100 on your ICP.",
            "last_interaction": last_interaction,
            "aria_recommendation": _aria_recommendation(sig, lead),
            "suggested_message": None,  # computed on demand via /ask-reply
        }

    @router.get("/workspace/feed")
    async def workspace_feed(limit: int = 20, current_user: dict = Depends(get_current_user)):
        """Scrollable lead-feed of sales signal cards."""
        # Pull a broad set of active leads and bucket them
        leads = list(leads_collection.find({"status": {"$nin": ["won", "lost"]}}, {
            "_id": 1, "first_name": 1, "last_name": 1, "company_name": 1,
            "icp_score": 1, "status": 1, "source_channel": 1, "lead_temperature": 1,
            "last_contacted_at": 1, "next_followup_at": 1, "metadata": 1, "job_title": 1,
            "deal_value": 1, "updated_at": 1,
        }).sort([("updated_at", -1), ("icp_score", -1)]).limit(limit * 2))

        feed = []
        seen_ids = set()
        for l in leads:
            l["id"] = str(l["_id"]); l.pop("_id", None)
            if l["id"] in seen_ids: continue
            seen_ids.add(l["id"])
            sig, why = _classify_lead_signal(l, None)
            meta = SIGNAL_CATALOG.get(sig, SIGNAL_CATALOG["new_lead"])
            icp = l.get("icp_score") or 0
            temperature = l.get("lead_temperature") or ("hot" if icp >= 80 else "warm" if icp >= 50 else "cold")
            feed.append({
                "id": f"{sig}:{l['id']}",
                "lead_id": l["id"],
                "signal": sig,
                "signal_label": meta["label"],
                "signal_accent": meta["accent"],
                "signal_icon": meta["icon"],
                "lead_name": f"{l.get('first_name','')} {l.get('last_name','')}".strip() or "Lead",
                "initials": _lead_initials(l),
                "company": l.get("company_name") or "—",
                "channel": (l.get("source_channel") or "—").replace("_", " ").title(),
                "temperature": temperature,
                "icp_score": icp,
                "summary": why,
                "why_it_matters": f"{meta['label']} on a lead scoring {icp}/100. Deal value: {l.get('deal_value') or '—'}.",
                "aria_recommendation": _aria_recommendation(sig, l),
                "updated_at": l.get("updated_at"),
            })
            if len(feed) >= limit: break
        return {"feed": feed, "count": len(feed)}

    @router.get("/workspace/pipeline-mood")
    async def pipeline_mood(current_user: dict = Depends(get_current_user)):
        now = datetime.now(timezone.utc)
        cutoff_silent = (now - timedelta(days=14)).isoformat()
        silent = leads_collection.count_documents({"status": {"$in": ["contacted", "qualified"]}, "last_contacted_at": {"$lte": cutoff_silent}})
        active = leads_collection.count_documents({"status": {"$in": ["new", "contacted", "qualified"]}})
        proposals = leads_collection.count_documents({"status": "proposal_sent"})
        recent_won = leads_collection.count_documents({"status": "won", "updated_at": {"$gte": (now - timedelta(days=30)).isoformat()}})
        hot = leads_collection.count_documents({"icp_score": {"$gte": 80}, "status": {"$in": ["new", "contacted", "qualified"]}})

        if silent > active * 0.4:
            mood, line, tone = "Too many leads are sleeping", "Revive silent leads today — ARIA has drafts ready for 5 segments.", "warning"
        elif proposals > 0 and recent_won == 0:
            mood, line, tone = "Proposal-heavy, closing weak", "Move stuck proposals with a founder voice note and a decision deadline.", "warning"
        elif hot >= 5:
            mood, line, tone = "Hot pipeline, needs sharper CTAs", "You have 5+ hot leads. Prioritise calls today, not new outreach.", "positive"
        elif active > 0 and silent == 0:
            mood, line, tone = "Demo momentum building", "Pipeline is warm and moving. Keep the cadence steady.", "positive"
        elif active == 0:
            mood, line, tone = "Quiet pipeline — time to refill", "Lead flow is low. ARIA can run a revival sweep or trigger new capture.", "neutral"
        else:
            mood, line, tone = "Healthy pipeline, needs sharper CTAs", "Reply times are fine. Tighten your booking nudge.", "neutral"

        return {"mood": mood, "line": line, "tone": tone, "counts": {"active": active, "silent": silent, "proposals": proposals, "hot": hot, "recent_won": recent_won}}

    @router.get("/workspace/morning-brief")
    async def morning_brief(current_user: dict = Depends(get_current_user)):
        now = datetime.now(timezone.utc)
        cutoff_silent = (now - timedelta(days=14)).isoformat()
        hot = list(leads_collection.find({"icp_score": {"$gte": 80}, "status": {"$in": ["new", "contacted", "qualified"]}}, {
            "_id": 0, "first_name": 1, "last_name": 1, "company_name": 1, "icp_score": 1,
        }).sort("icp_score", -1).limit(3))
        followups_due = leads_collection.count_documents({
            "next_followup_at": {"$lt": now.isoformat()},
            "status": {"$nin": ["won", "lost", "unqualified"]},
        })
        silent = leads_collection.count_documents({"status": {"$in": ["contacted", "qualified"]}, "last_contacted_at": {"$lte": cutoff_silent}})
        proposals = leads_collection.count_documents({"status": "proposal_sent"})

        # 3-sentence brief
        if len(hot) > 0 and followups_due > 0:
            s1 = f"Good morning. You have {len(hot)} hot {('lead' if len(hot) == 1 else 'leads')} today and {followups_due} follow-ups due."
        elif len(hot) > 0:
            s1 = f"Good morning. You have {len(hot)} hot leads ready to move today."
        elif followups_due > 0:
            s1 = f"Good morning. {followups_due} follow-ups need your attention before new outreach."
        else:
            s1 = "Good morning. Your pipeline is clean — use today to push proposals forward."

        if proposals > 0 and silent > 5:
            s2 = f"Your strongest signal is {proposals} active proposals, but {silent} silent leads are slipping."
        elif proposals > 0:
            s2 = f"Your strongest signal is {proposals} active proposals. Keep them moving."
        elif silent > 5:
            s2 = f"Your biggest risk is {silent} silent leads. ARIA can restart those conversations."
        else:
            s2 = "Your channels are balanced. WhatsApp is your fastest lane today."

        # Name-drop up to 3 hot leads
        names = [f"{h.get('first_name','').strip()}" for h in hot if h.get("first_name")]
        if names:
            if len(names) == 1:
                s3 = f"ARIA recommends starting with {names[0]} before new outreach."
            elif len(names) == 2:
                s3 = f"ARIA recommends following up with {names[0]} and {names[1]} before new outreach."
            else:
                s3 = f"ARIA recommends following up with {names[0]}, {names[1]}, and {names[2]} before new outreach."
        elif followups_due > 0:
            s3 = "ARIA recommends clearing due follow-ups first — they're likely warmer than cold outreach."
        else:
            s3 = "ARIA recommends one revival sweep today to wake cold leads."

        cta_label = "Start with ARIA's priority"
        cta_to = "/follow-ups" if followups_due > 0 else "/leads"
        return {
            "greeting": "Good morning" if now.hour < 12 else "Good afternoon" if now.hour < 17 else "Good evening",
            "sentences": [s1, s2, s3],
            "cta_label": cta_label,
            "cta_to": cta_to,
            "badges": {
                "hot_leads": len(hot),
                "followups_due": followups_due,
                "silent": silent,
                "proposals": proposals,
            },
        }

    class AskReplyPayload(BaseModel):
        channel: str = "whatsapp"         # whatsapp | email | linkedin | call_script
        tone: str = "founder_led"         # founder_led | friendly | direct | premium | consultative | sharp_closer | soft_nurture
        user_note: Optional[str] = ""     # optional additional context from user

    @router.post("/workspace/ask-reply/{lead_id}")
    async def ask_aria_reply(lead_id: str, payload: AskReplyPayload, current_user: dict = Depends(get_current_user)):
        from bson import ObjectId
        try:
            lead = leads_collection.find_one({"_id": ObjectId(lead_id)})
        except Exception:
            raise HTTPException(400, "Invalid lead id")
        if not lead:
            raise HTTPException(404, "Lead not found")
        lead["id"] = str(lead["_id"]); lead.pop("_id", None)
        recent = list(activities_collection.find({"lead_id": lead_id}, {"_id": 0}).sort("created_at", -1).limit(6))
        training = training_collection_ref.find_one({"scope": "workspace"}, {"_id": 0}) or {}

        training_snippet = ""
        if training:
            training_snippet = f"""
WORKSPACE CONTEXT:
- We sell: {training.get('what_you_sell') or 'AI sales agent'}
- Audience: {training.get('who_you_sell_to') or '—'}
- Differentiator: {training.get('differentiator') or '—'}
"""
        activity_lines = []
        for a in recent:
            t = (a.get("activity_type") or "—").replace("_", " ")
            subj = (a.get("subject") or a.get("body") or "").strip()[:180]
            activity_lines.append(f"- {t}: {subj}")
        activities_text = "\n".join(activity_lines) or "(no recorded activity)"

        first_name = lead.get("first_name") or "there"
        company = lead.get("company_name") or "—"

        tone_map = {
            "founder_led": "Warm, direct, personal. Short sentences. First-person. Like a founder who knows the buyer's pain.",
            "friendly": "Warm and helpful. Light emoji allowed. Casual.",
            "direct": "Sharp, 1-2 sentences, no fluff. Question-forward.",
            "premium": "Polished, consultative, no slang, executive tone.",
            "consultative": "Strategic, insight-led, thoughtful. Asks smart questions.",
            "sharp_closer": "Urgent, CTA-led, specific slot offers. Drive decision.",
            "soft_nurture": "Helpful, educational, low-pressure, trust-building.",
        }
        tone_instruction = tone_map.get(payload.tone, tone_map["founder_led"])

        channel_limits = {
            "whatsapp": "Max 2-3 short lines. No formal salutation. No 'hope you're well'.",
            "email": "Subject line + 3-4 short sentences. Clear ask. No corporate filler.",
            "linkedin": "Max 2 short lines. Conversational. No formal tone.",
            "call_script": "Write a 3-sentence opener the founder can say on the phone. Specific and personal.",
        }
        channel_hint = channel_limits.get(payload.channel, channel_limits["whatsapp"])

        system = (
            "You are ARIA, an AI sales agent drafting outbound replies for GenLeadAI founders. "
            "You write like a seasoned sales operator — specific, confident, no AI-speak, no emoji spam, no 'I hope this finds you well'. "
            "Match the requested tone and channel exactly. Never explain the message or add commentary — just the message itself."
        )
        prompt = f"""{training_snippet}
LEAD:
- Name: {first_name}
- Company: {company}
- Role: {lead.get('job_title') or '—'}
- ICP score: {lead.get('icp_score') or 0}
- Status: {lead.get('status') or 'new'}
- Source: {(lead.get('source_channel') or '—').replace('_',' ').title()}

RECENT ACTIVITY:
{activities_text}

USER NOTE (from founder): {payload.user_note or '(none)'}

Write ONE reply message.
Channel: {payload.channel.upper()}
Tone: {tone_instruction}
Format: {channel_hint}

Return ONLY the message text — no JSON, no explanation, no preamble."""

        try:
            chat = LlmChat(
                api_key=os.getenv("EMERGENT_LLM_KEY"),
                session_id=f"ask_reply_{lead_id}_{payload.channel}_{payload.tone}",
                system_message=system,
            )
            chat.with_model("anthropic", "claude-4-sonnet-20250514")
            resp = await chat.send_message(UserMessage(text=prompt))
            message = (resp or "").strip().strip('"')
            return {"lead_id": lead_id, "channel": payload.channel, "tone": payload.tone, "message": message, "ai_powered": True}
        except Exception as e:
            # Heuristic fallback
            fallback = f"Hey {first_name} — quick one. Based on our last exchange about {company}, I've got a specific idea that could help. Worth a 15-min call this week? I have Tuesday 4 PM or Wednesday 11 AM."
            return {"lead_id": lead_id, "channel": payload.channel, "tone": payload.tone, "message": fallback, "ai_powered": False, "ai_error": str(e)}

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
    # 8. ARIA Insights
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    @router.get("/insights")
    async def aria_insights(current_user: dict = Depends(get_current_user)):
        # Compute lightweight signals from real data; fill demo gaps where workspace is fresh
        leads = list(leads_collection.find({}, {"_id": 0, "source_channel": 1, "status": 1, "icp_score": 1, "lost_reason": 1}))
        source_counts = {}
        for l in leads:
            s = (l.get("source_channel") or "other").replace("_", " ").title()
            source_counts[s] = source_counts.get(s, 0) + 1
        top_source = max(source_counts, key=source_counts.get) if source_counts else "LinkedIn"

        return {
            "headline_insights": [
                {"icon": "Brain", "title": "Most common pain points",
                 "items": ["Founder still doing follow-ups manually", "Leads slipping in first 60 minutes", "No visibility into who's hot today"]},
                {"icon": "ChatCircle", "title": "Most common objections",
                 "items": ["'Is this another CRM?'", "'Will it sound like a bot?'", "'How is this different from automation tools?'"]},
                {"icon": "EnvelopeOpen", "title": "Best-performing follow-up messages",
                 "items": ["Founder voice note within 1 hour", "Specific 2-slot call ask (no 'when works?')", "Proof message tied to lead's industry"]},
                {"icon": "Lightning", "title": "Channels with highest response",
                 "items": [f"{top_source} — fastest reply rate", "WhatsApp — highest qualification %", "Email — best for proposal followups"]},
                {"icon": "Trophy", "title": "Leads most likely to book",
                 "items": ["Mentioned a deadline in first reply", "Company size matches ICP", "Asked a 'how does it work' question"]},
                {"icon": "Snowflake", "title": "Reasons leads go cold",
                 "items": ["No personal touch in first 60 min", "Generic pricing reply too early", "Missed the booking nudge window"]},
                {"icon": "Clock", "title": "Best time to follow up",
                 "items": ["Tue/Wed 10–12 local for first reply", "Thu 4–6 PM for booking nudge", "Mon 9 AM for revival"]},
                {"icon": "User", "title": "Founder intervention impact",
                 "items": ["Founder note 3.4× higher reply rate", "Founder voice note → 62% close rate on hot leads", "Founder skip = 18% close drop"]},
            ],
            "recommendations": [
                {"id": "case_study", "title": "Add one more case study to the nurture journey", "impact": "+12% reply rate"},
                {"id": "shorter_pricing", "title": "Shorten pricing explanation in first reply", "impact": "+8% qualification rate"},
                {"id": "earlier_booking", "title": "Move booking CTA earlier for high-intent leads", "impact": "+15% calls booked"},
                {"id": "founder_voice", "title": "Add founder voice note for enterprise leads", "impact": "+22% close rate"},
            ],
            "live_observation": "ARIA noticed that leads from LinkedIn are asking more pricing-related questions, while website leads are more likely to book a demo after seeing proof.",
        }

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 9. Sales Assets — reusable content ARIA can send on your behalf
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    assets_collection = db["aria_sales_assets"]

    ASSET_TYPES = [
        {"id": "message_template", "label": "Message templates", "icon": "ChatText",
         "description": "Short, reusable messages ARIA can personalise per lead."},
        {"id": "voice_note", "label": "Founder voice notes", "icon": "Microphone",
         "description": "Pre-recorded founder voice notes for high-value moments."},
        {"id": "case_study", "label": "Case studies", "icon": "FileText",
         "description": "Proof stories ARIA weaves into objection responses."},
        {"id": "proposal_template", "label": "Proposal templates", "icon": "Article",
         "description": "Structured proposal outlines ARIA tailors to each lead."},
        {"id": "founder_intro", "label": "Founder intros", "icon": "User",
         "description": "Personal intros ARIA can deploy when a lead wants the founder."},
        {"id": "objection_response", "label": "Objection responses", "icon": "ShieldCheck",
         "description": "Battle-tested responses to common pushbacks."},
        {"id": "pricing_doc", "label": "Pricing docs", "icon": "CurrencyDollar",
         "description": "Pricing one-pagers ARIA surfaces at the right time."},
    ]

    class AssetPayload(BaseModel):
        title: str
        type: str = "message_template"
        body: str = ""
        tags: List[str] = Field(default_factory=list)
        channel: Optional[str] = None
        used_by_aria: bool = True

    @router.get("/assets/catalog")
    async def assets_catalog(current_user: dict = Depends(get_current_user)):
        return {"types": ASSET_TYPES}

    @router.get("/assets")
    async def list_assets(type: Optional[str] = None, current_user: dict = Depends(get_current_user)):
        q = {}
        if type:
            q["type"] = type
        docs = list(assets_collection.find(q, {"_id": 0}).sort("created_at", -1))
        # Summary stats
        total = assets_collection.count_documents({})
        active = assets_collection.count_documents({"used_by_aria": True})
        now = datetime.now(timezone.utc)
        week_start = (now - timedelta(days=7)).isoformat()
        used_this_week = assets_collection.count_documents({"last_used_at": {"$gte": week_start}})
        top_cursor = list(assets_collection.find({}, {"_id": 0}).sort("usage_count", -1).limit(1))
        top = top_cursor[0] if top_cursor else None
        # By type breakdown
        by_type = {}
        for a in assets_collection.find({}, {"_id": 0, "type": 1}):
            t = a.get("type") or "message_template"
            by_type[t] = by_type.get(t, 0) + 1
        return {
            "assets": docs,
            "stats": {
                "total": total,
                "active": active,
                "used_this_week": used_this_week,
                "top_asset": top,
                "by_type": by_type,
            },
            "types": ASSET_TYPES,
        }

    @router.post("/assets")
    async def create_asset(payload: AssetPayload, current_user: dict = Depends(get_current_user)):
        from uuid import uuid4
        doc = payload.dict()
        doc["id"] = str(uuid4())
        doc["created_at"] = datetime.now(timezone.utc).isoformat()
        doc["updated_at"] = doc["created_at"]
        doc["usage_count"] = 0
        doc["last_used_at"] = None
        doc["created_by"] = current_user.get("id") or current_user.get("_id") or "founder"
        assets_collection.insert_one(dict(doc))  # copy to avoid _id mutation on our dict
        return {k: v for k, v in doc.items() if k != "_id"}

    @router.patch("/assets/{asset_id}")
    async def update_asset(asset_id: str, payload: AssetPayload, current_user: dict = Depends(get_current_user)):
        data = payload.dict()
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        res = assets_collection.update_one({"id": asset_id}, {"$set": data})
        if res.matched_count == 0:
            raise HTTPException(404, "Asset not found")
        doc = assets_collection.find_one({"id": asset_id}, {"_id": 0})
        return doc

    @router.delete("/assets/{asset_id}")
    async def delete_asset(asset_id: str, current_user: dict = Depends(get_current_user)):
        res = assets_collection.delete_one({"id": asset_id})
        if res.deleted_count == 0:
            raise HTTPException(404, "Asset not found")
        return {"ok": True}

    @router.post("/assets/{asset_id}/use")
    async def mark_asset_used(asset_id: str, current_user: dict = Depends(get_current_user)):
        now = datetime.now(timezone.utc).isoformat()
        res = assets_collection.update_one({"id": asset_id}, {"$inc": {"usage_count": 1}, "$set": {"last_used_at": now}})
        if res.matched_count == 0:
            raise HTTPException(404, "Asset not found")
        return {"ok": True}

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
        training = training_collection_ref.find_one({"scope": "workspace"}, {"_id": 0}) or {}
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
        lost = leads_collection.count_documents({"status": "lost"})
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
    # 11. Weekly Recap
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    @router.get("/weekly-recap")
    async def weekly_recap(current_user: dict = Depends(get_current_user)):
        now = datetime.now(timezone.utc)
        week_start = now - timedelta(days=7)
        prev_start = now - timedelta(days=14)
        ws_iso = week_start.isoformat()
        ps_iso = prev_start.isoformat()

        def _between(col, field, start, end):
            return col.count_documents({field: {"$gte": start, "$lt": end}})

        # This week
        now_iso = now.isoformat()
        new_leads = _between(leads_collection, "created_at", ws_iso, now_iso)
        qualified = leads_collection.count_documents({"status": "qualified", "updated_at": {"$gte": ws_iso}})
        replies_sent = activities_collection.count_documents({"activity_type": {"$in": ["email_sent", "whatsapp_sent"]}, "created_at": {"$gte": ws_iso}})
        calls_booked = activities_collection.count_documents({"activity_type": "meeting_scheduled", "created_at": {"$gte": ws_iso}})
        deals_won = leads_collection.count_documents({"status": "won", "updated_at": {"$gte": ws_iso}})
        deals_lost = leads_collection.count_documents({"status": "lost", "updated_at": {"$gte": ws_iso}})

        # Previous week
        prev_new = leads_collection.count_documents({"created_at": {"$gte": ps_iso, "$lt": ws_iso}})
        prev_qualified = leads_collection.count_documents({"status": "qualified", "updated_at": {"$gte": ps_iso, "$lt": ws_iso}})
        prev_replies = activities_collection.count_documents({"activity_type": {"$in": ["email_sent", "whatsapp_sent"]}, "created_at": {"$gte": ps_iso, "$lt": ws_iso}})
        prev_booked = activities_collection.count_documents({"activity_type": "meeting_scheduled", "created_at": {"$gte": ps_iso, "$lt": ws_iso}})
        prev_won = leads_collection.count_documents({"status": "won", "updated_at": {"$gte": ps_iso, "$lt": ws_iso}})

        def _delta(cur, prev):
            if prev == 0 and cur == 0: return 0
            if prev == 0: return 100
            return round((cur - prev) / prev * 100)

        # Biggest win / miss
        win_cursor = list(leads_collection.find({"status": "won", "updated_at": {"$gte": ws_iso}}, {
            "_id": 0, "first_name": 1, "last_name": 1, "company_name": 1, "icp_score": 1, "deal_value": 1,
        }).sort([("deal_value", -1), ("icp_score", -1)]).limit(1))
        biggest_win = win_cursor[0] if win_cursor else None

        miss_cursor = list(leads_collection.find({
            "icp_score": {"$gte": 75},
            "status": {"$in": ["contacted", "qualified", "proposal_sent"]},
            "last_contacted_at": {"$lt": ws_iso},
        }, {"_id": 0, "first_name": 1, "last_name": 1, "company_name": 1, "icp_score": 1, "last_contacted_at": 1})
            .sort("icp_score", -1).limit(1))
        biggest_miss = miss_cursor[0] if miss_cursor else None

        # Top signal of the week
        src_week = {}
        for l in leads_collection.find({"created_at": {"$gte": ws_iso}}, {"_id": 0, "source_channel": 1}):
            s = (l.get("source_channel") or "other").replace("_", " ").title()
            src_week[s] = src_week.get(s, 0) + 1
        top_channel = max(src_week, key=src_week.get) if src_week else "—"

        # Build narrative
        if new_leads == 0 and replies_sent == 0 and calls_booked == 0 and deals_won == 0:
            narrative = (
                "This week was quiet on the wire — no new leads, replies, or bookings logged yet. "
                "That's a refill signal, not a red flag. Use tomorrow to run a revival sweep on silent leads "
                "and trigger fresh capture — ARIA will handle the conversations as they come in."
            )
        else:
            parts = []
            parts.append(f"ARIA handled {replies_sent} conversations this week")
            if calls_booked > 0:
                parts.append(f"booked {calls_booked} call{'s' if calls_booked != 1 else ''}")
            if qualified > 0:
                parts.append(f"qualified {qualified} lead{'s' if qualified != 1 else ''}")
            if deals_won > 0:
                parts.append(f"closed {deals_won} deal{'s' if deals_won != 1 else ''}")
            narrative = ", ".join(parts) + "."
            if top_channel and top_channel != "—":
                narrative += f" Your strongest source was {top_channel}."
            if biggest_miss:
                narrative += f" Watch out — {biggest_miss.get('first_name','a high-ICP lead')} ({biggest_miss.get('company_name','—')}) has gone silent."

        # Next week focus — heuristic 3 bullets
        focus = []
        if biggest_miss:
            miss_name = biggest_miss.get('first_name') or f"your silent ICP-{biggest_miss.get('icp_score', 80)}+"
            focus.append(f"Revive {miss_name} lead at {biggest_miss.get('company_name','—')} with a founder voice note.")
        if _delta(replies_sent, prev_replies) < 0:
            focus.append("Reply volume dropped vs last week — audit your automations and triggers.")
        if _delta(calls_booked, prev_booked) < 0 and calls_booked < 3:
            focus.append("Calls booked are trending down — tighten the booking CTA on warm replies.")
        while len(focus) < 3:
            fallback = [
                "Push one proposal to decision with a specific deadline message.",
                "Add one more case study to the nurture journey — ARIA will weave it into objections.",
                "Ship one founder voice note this week to your top 3 hot leads.",
                "Clean qualifier answers in Train ARIA so ARIA escalates to you faster.",
            ]
            for f in fallback:
                if f not in focus:
                    focus.append(f)
                    break
            if len(focus) >= 3:
                break

        return {
            "week_start": ws_iso,
            "week_end": now.isoformat(),
            "headline": f"Week of {week_start.strftime('%b %d')} → {now.strftime('%b %d')}",
            "narrative": narrative,
            "stats": [
                {"label": "New leads", "value": new_leads, "delta": _delta(new_leads, prev_new), "prev": prev_new},
                {"label": "Qualified", "value": qualified, "delta": _delta(qualified, prev_qualified), "prev": prev_qualified},
                {"label": "Replies sent", "value": replies_sent, "delta": _delta(replies_sent, prev_replies), "prev": prev_replies},
                {"label": "Calls booked", "value": calls_booked, "delta": _delta(calls_booked, prev_booked), "prev": prev_booked},
                {"label": "Deals won", "value": deals_won, "delta": _delta(deals_won, prev_won), "prev": prev_won},
                {"label": "Deals lost", "value": deals_lost, "delta": 0, "prev": 0},
            ],
            "top_channel": top_channel,
            "biggest_win": biggest_win,
            "biggest_miss": biggest_miss,
            "next_week_focus": focus[:3],
        }

    return router


def attach_aria_agent_routes(app, get_current_user, db):
    """Call from server.py after FastAPI app is instantiated."""
    r = _aria_agent_endpoints(app, get_current_user, db)
    app.include_router(r)
