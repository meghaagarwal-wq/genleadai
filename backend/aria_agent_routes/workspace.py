"""Submodule of aria_agent_routes — registers routes on the shared router.
Auto-split from aria_agent_routes.py (iter75).
"""
from ._shared import (
    router, training_collection, playbooks_collection, leads_collection,
    activities_collection, db, get_current_user, AriaTrainingPayload,
    get_active_playbook_block, get_relevant_assets_block,
)
from security.limiter import limiter as _limiter
from security.helpers import sanitise_for_prompt
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from emergentintegrations.llm.chat import LlmChat, UserMessage
import os
import json


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
@_limiter.limit("30/minute")  # iter80 — S9.5: cap Aria-generated replies
async def ask_aria_reply(lead_id: str, payload: AskReplyPayload, request: Request, current_user: dict = Depends(get_current_user)):
    from bson import ObjectId
    try:
        lead = leads_collection.find_one({"_id": ObjectId(lead_id)})
    except Exception:
        raise HTTPException(400, "Invalid lead id")
    if not lead:
        raise HTTPException(404, "Lead not found")
    lead["id"] = str(lead["_id"]); lead.pop("_id", None)
    recent = list(activities_collection.find({"lead_id": lead_id}, {"_id": 0}).sort("created_at", -1).limit(6))
    training = training_collection.find_one({"scope": "workspace"}, {"_id": 0}) or {}

    # Multi-tenant: pull onboarding config to enrich prompt with tenant-specific persona
    onboarding_cfg = {}
    try:
        tenant_id = current_user.get("tenant_id")
        if tenant_id:
            onboarding_cfg = db["onboarding_config"].find_one({"tenant_id": tenant_id}, {"_id": 0}) or {}
    except Exception:
        onboarding_cfg = {}
    bp = onboarding_cfg.get("business_profile") or {}
    persona_cfg = onboarding_cfg.get("aria_persona") or {}
    sp = onboarding_cfg.get("sales_process") or {}

    training_snippet = ""
    # White-label — the brand name that goes into every drafted reply.
    tenant_business_name = (
        bp.get("business_name")
        or (training.get("business_name") if isinstance(training, dict) else None)
        or "this business"
    )
    if training or onboarding_cfg:
        training_snippet = f"""
WORKSPACE CONTEXT:
- Business name (use THIS as the brand on every message — never 'GenLeadAI', never 'Aria as a platform'): {tenant_business_name}
- Industry: {bp.get('industry') or '—'}
- We sell: {sp.get('product_description') or training.get('what_you_sell') or 'AI sales agent'}
- Audience: {bp.get('primary_market') or training.get('who_you_sell_to') or '—'}
- Differentiator: {training.get('differentiator') or '—'}
- Aria's preferred tone: {persona_cfg.get('tone') or 'founder_led'}
- Primary language: {persona_cfg.get('language') or 'English'}
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
        f"You are ARIA, an AI sales agent drafting outbound replies on behalf of {tenant_business_name}. "
        f"You ALWAYS represent {tenant_business_name} — never any other company, never 'GenLeadAI', never call yourself 'a platform'. "
        "You write like a seasoned sales operator — specific, confident, no AI-speak, no emoji spam, no 'I hope this finds you well'. "
        "Match the requested tone and channel exactly. Never explain the message or add commentary — just the message itself."
    )
    # Iter78 S6: inject active playbook + relevant assets (objection / pricing / case study).
    tid = lead.get("tenant_id") or ""
    # Iter80 — S9.5: sanitise user-controlled text before it enters the prompt.
    safe_user_note = sanitise_for_prompt(payload.user_note or "")
    system += get_active_playbook_block(tid)
    system += get_relevant_assets_block(tid, safe_user_note)
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

USER NOTE (from founder): {safe_user_note or '(none)'}

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

