"""Seed data for the 8 universal touchpoint templates.

Each template is auto-selected by `_select_template(onboarding_config)` based
on industry > market+cycle > deal_size. Stored in `touchpoint_templates`
collection on first import (idempotent).

Touchpoint object shape:
{
  index: int,                    # position in the journey (0-based)
  day: float,                    # absolute day offset from lead entry
  hour: int,                     # additional hour offset within day
  channel: 'whatsapp'|'email'|'call_reminder'|'linkedin_nudge',
  message_type: 'intro'|'qualifier'|'value_drop'|'follow_up'
              |'social_proof'|'soft_cta'|'budget_probe'|'meeting_cta'
              |'human_escalation'|'re_engagement'|'urgency'|'closure',
  aria_role: 'autonomous'|'alert_human',
  trigger: str,                  # short human label e.g. 'on lead entry'
  message_template: str,         # used as Claude intent + fallback copy
}
"""
from typing import List, Dict, Any


def _t(index: int, day: float, hour: int, channel: str, message_type: str,
       aria_role: str, trigger: str, message_template: str) -> Dict[str, Any]:
    return {
        "index": index,
        "day": day,
        "hour": hour,
        "channel": channel,
        "message_type": message_type,
        "aria_role": aria_role,
        "trigger": trigger,
        "message_template": message_template,
    }


# ─── Template 1: Fast Conversion (B2C · Short cycle · Small deal) ───────────
FAST_CONVERSION = [
    _t(0, 0, 0, "whatsapp", "intro", "autonomous", "on lead entry",
       "Hi {{first_name}}! 👋 I'm {{aria_name}}, {{company}}'s sales assistant. Thanks for your interest in {{product}}! Quick question — are you looking for something for personal use or for your business?"),
    _t(1, 0, 2, "whatsapp", "follow_up", "autonomous", "no reply at +2h",
       "Hey {{first_name}}, just checking in! Happy to answer any questions about {{product}} — what's most important to you, price or speed of delivery?"),
    _t(2, 1, 0, "whatsapp", "value_drop", "autonomous", "+24h",
       "Here's what most people love about {{product}}: [top benefit 1], [top benefit 2]. Want me to send you details?"),
    _t(3, 2, 0, "whatsapp", "qualifier", "autonomous", "if unqualified at +48h",
       "Just to make sure I'm sending you the right info — what's your budget range in mind?"),
    _t(4, 3, 0, "whatsapp", "re_engagement", "autonomous", "no conversion at +72h",
       "Still thinking it over? I get it. Want me to share a quick comparison so you have everything in front of you? 😊"),
]

# ─── Template 2: Warm Nurture (B2C · Short cycle · Mid deal) ────────────────
WARM_NURTURE = [
    _t(0, 0, 0, "whatsapp", "intro", "autonomous", "on lead entry",
       "Hi {{first_name}}! I'm {{aria_name}} from {{company}}. Great to connect! Tell me — what brought you to us today?"),
    _t(1, 0, 4, "whatsapp", "qualifier", "autonomous", "+4h",
       "Quick question — is this for yourself or are others involved in the decision?"),
    _t(2, 1, 0, "email", "value_drop", "autonomous", "+24h",
       "Subject: Here's what {{company}} can do for you, {{first_name}}\n\nProduct overview, recent results, and what to expect on a discovery call."),
    _t(3, 2, 0, "whatsapp", "social_proof", "autonomous", "+48h",
       "One of our recent clients had a very similar situation — they saw [result] within [timeframe]. Happy to share more?"),
    _t(4, 3, 0, "whatsapp", "soft_cta", "autonomous", "+72h",
       "Are you ready to take the next step, or would you like a bit more time?"),
    _t(5, 7, 0, "whatsapp", "re_engagement", "autonomous", "+7 days, silent",
       "Hi {{first_name}}! It's been a week — still exploring options? I'm here if you need anything 😊"),
]

# ─── Template 3: Considered Sale (B2B · Medium cycle · Mid/Large) ───────────
CONSIDERED_SALE = [
    _t(0, 0, 0, "whatsapp", "intro", "autonomous", "on lead entry",
       "Hi {{first_name}}, I'm {{aria_name}} — the sales assistant at {{company}}. Thanks for reaching out! To send you the most relevant information, may I ask — what specific challenge are you trying to solve?"),
    _t(1, 0, 2, "whatsapp", "qualifier", "autonomous", "+2h",
       "And roughly how many people would be using/affected by this? Just helps me tailor what I share."),
    _t(2, 1, 0, "whatsapp", "qualifier", "autonomous", "+24h",
       "Is there a timeline you're working towards, or are you still in early exploration?"),
    _t(3, 2, 0, "email", "value_drop", "autonomous", "+48h",
       "Subject: A relevant case study for {{company}}\n\nSend a case study or product brief tailored to their industry."),
    _t(4, 3, 0, "whatsapp", "budget_probe", "autonomous", "+72h",
       "Have you got a rough budget range in mind for this? No pressure — just helps me show you the right options."),
    _t(5, 5, 0, "whatsapp", "human_escalation", "alert_human", "+5 days if qualified",
       "ALERT: {{first_name}} is qualified (budget confirmed, decision-maker, timeline defined). Recommend scheduling a call."),
    _t(6, 7, 0, "whatsapp", "meeting_cta", "autonomous", "+7 days",
       "I'd love to connect you with our team for a proper conversation. Would [day] or [day] work for a 20-min call?"),
    _t(7, 14, 0, "whatsapp", "re_engagement", "autonomous", "+14 days, silent",
       "Hi {{first_name}}, checking in one last time. If the timing's not right, no worries — just let me know and I'll follow up in a few weeks."),
]

# ─── Template 4: Enterprise Track (B2B · Long cycle · Large/Enterprise) ─────
ENTERPRISE_TRACK = [
    _t(0, 0, 0, "whatsapp", "intro", "autonomous", "on lead entry",
       "Hi {{first_name}}, this is {{aria_name}} from {{company}}. Thanks for reaching out — I'd love to understand your situation better. What problem brought you to us today?"),
    _t(1, 0, 4, "whatsapp", "qualifier", "autonomous", "+4h",
       "Helpful context — and what's your role in evaluating this? Are you the primary lead or is this on behalf of someone else?"),
    _t(2, 1, 0, "email", "value_drop", "autonomous", "+24h",
       "Subject: {{company}} — credentials, how we work, what to expect\n\nFormal intro email with company credentials, security posture, and 2-3 customer logos."),
    _t(3, 2, 0, "whatsapp", "qualifier", "autonomous", "+48h",
       "Quick deep-dive — what's the cost of NOT solving this for the next 12 months? Helps me see how urgent this is for your team."),
    _t(4, 3, 0, "whatsapp", "qualifier", "autonomous", "+72h",
       "Got it. Are there other stakeholders we should loop in early? Procurement / Finance / IT?"),
    _t(5, 5, 0, "linkedin_nudge", "human_escalation", "alert_human", "+5 days",
       "ALERT: send LinkedIn connection from senior rep to {{first_name}} with a 1-line context-aware note."),
    _t(6, 7, 0, "email", "social_proof", "autonomous", "+7 days",
       "Subject: How [similar enterprise] solved [problem] with {{company}}\n\nShare a relevant enterprise case study + ROI numbers."),
    _t(7, 10, 0, "call_reminder", "human_escalation", "alert_human", "+10 days if qualified",
       "ALERT: escalate to senior rep for discovery call with {{first_name}}. Lead is multi-stakeholder + qualified."),
    _t(8, 14, 0, "email", "meeting_cta", "autonomous", "+14 days",
       "Subject: Ready to put together a proposal?\n\nAsk if they're at proposal-readiness and offer a structured walkthrough."),
    _t(9, 30, 0, "whatsapp", "re_engagement", "autonomous", "+30 days if stalled",
       "Hi {{first_name}}, just checking in — has anything changed on your side? Happy to revisit if priorities have shifted."),
]

# ─── Template 5: Urgency-Led (Events) ───────────────────────────────────────
URGENCY_LED = [
    _t(0, 0, 0, "whatsapp", "intro", "autonomous", "on lead entry",
       "Hi {{first_name}}! 🎟️ Thanks for your interest in {{product}}. The event's coming up fast — I can answer anything you need. What's most important to lock in for you?"),
    _t(1, 0, 3, "whatsapp", "value_drop", "autonomous", "+3h",
       "Quick heads-up — early-bird pricing or premium passes usually go first. Want me to share what's still available?"),
    _t(2, 1, 0, "whatsapp", "urgency", "autonomous", "+24h",
       "{{first_name}}, just checking — should I hold a spot for you? Tickets at this tier are moving."),
    _t(3, 2, 0, "email", "social_proof", "autonomous", "+48h",
       "Subject: Who's attending this year — and why you don't want to miss it\n\nList 2-3 marquee speakers/attendees + agenda highlight."),
    _t(4, 3, 0, "whatsapp", "urgency", "autonomous", "+72h",
       "Last call on early-bird — closes [date]. Want me to grab your spot now and we sort details after?"),
    _t(5, 5, 0, "whatsapp", "human_escalation", "alert_human", "+5 days if VIP",
       "ALERT: {{first_name}} is high-value (corporate / multi-pass / sponsor lead). Personal outreach recommended."),
    _t(6, 7, 0, "whatsapp", "closure", "autonomous", "+7 days",
       "Hi {{first_name}}, last note before the event closes registrations — want me to send the link to lock it in?"),
]

# ─── Template 6: High-Intent Qualifier (Real Estate) ────────────────────────
HIGH_INTENT_QUALIFIER = [
    _t(0, 0, 0, "whatsapp", "intro", "autonomous", "on lead entry",
       "Hi {{first_name}}! 🏡 Thanks for your interest in {{product}}. I'm {{aria_name}} from {{company}}. To send you the right options — are you looking for end-use or investment?"),
    _t(1, 0, 2, "whatsapp", "qualifier", "autonomous", "+2h",
       "Got it — and any preferred locations, or are you open?"),
    _t(2, 0, 6, "whatsapp", "qualifier", "autonomous", "+6h",
       "What's your budget range? Helps me shortlist what's actually a fit."),
    _t(3, 1, 0, "whatsapp", "value_drop", "autonomous", "+24h",
       "Sharing 2-3 properties matching your brief. Which one feels closest? Happy to set up a site visit if any catch your eye."),
    _t(4, 2, 0, "whatsapp", "human_escalation", "alert_human", "+48h, qualified",
       "ALERT: {{first_name}} is qualified (budget confirmed, location set). Site-visit eligible — assign to senior rep."),
    _t(5, 4, 0, "whatsapp", "meeting_cta", "autonomous", "+4 days",
       "Are weekends or weekdays better for a site visit? I can block a slot with our property consultant."),
    _t(6, 7, 0, "whatsapp", "social_proof", "autonomous", "+7 days",
       "We just closed a deal on [property] at [outcome]. Wanted to share — similar profile to what you're looking at."),
    _t(7, 14, 0, "whatsapp", "re_engagement", "autonomous", "+14 days, silent",
       "Hi {{first_name}}, are you still looking? If priorities changed, just let me know and I'll pause for now."),
]

# ─── Template 7: Abandoned Interest (E-commerce · B2C) ──────────────────────
ABANDONED_INTEREST = [
    _t(0, 0, 0, "whatsapp", "intro", "autonomous", "on lead entry",
       "Hi {{first_name}}! 🛍️ Saw you were checking out {{product}} on {{company}}. Anything I can help you decide?"),
    _t(1, 0, 6, "whatsapp", "value_drop", "autonomous", "+6h",
       "Quick FYI — most people pair {{product}} with [accessory]. Want me to share the bundle?"),
    _t(2, 1, 0, "whatsapp", "social_proof", "autonomous", "+24h",
       "{{product}} is rated [rating]/5 by [N]+ buyers. Want to see the top reviews?"),
    _t(3, 3, 0, "whatsapp", "urgency", "autonomous", "+72h, discount trigger",
       "Hey {{first_name}}, made a small space for you — here's a 10% off code valid for the next 24 hours: [CODE]. Want me to apply it for you?"),
    _t(4, 5, 0, "whatsapp", "closure", "autonomous", "+5 days",
       "Last chance on the discount — want me to lock it in? After today the code expires."),
]

# ─── Template 8: Standard (fallback) ────────────────────────────────────────
STANDARD = [
    _t(0, 0, 0, "whatsapp", "intro", "autonomous", "on lead entry",
       "Hi {{first_name}}, I'm {{aria_name}} from {{company}}. Thanks for reaching out! What are you trying to solve, in a sentence or two?"),
    _t(1, 0, 4, "whatsapp", "qualifier", "autonomous", "+4h",
       "Quick context — is this something you need now, in the next month, or further out?"),
    _t(2, 1, 0, "whatsapp", "value_drop", "autonomous", "+24h",
       "Here's a quick overview of how {{company}} usually helps — [3 bullets]. Want me to dig deeper into any of these?"),
    _t(3, 3, 0, "email", "social_proof", "autonomous", "+72h",
       "Subject: A {{company}} story relevant to you\n\nShare a case study most relevant to the lead's industry/segment."),
    _t(4, 5, 0, "whatsapp", "budget_probe", "autonomous", "+5 days",
       "Got a rough budget in mind for this? No pressure — helps me share the right options."),
    _t(5, 7, 0, "whatsapp", "meeting_cta", "autonomous", "+7 days",
       "Want to hop on a quick call this week? 15-20 min, totally informal."),
    _t(6, 14, 0, "whatsapp", "re_engagement", "autonomous", "+14 days, silent",
       "Hi {{first_name}}, last check-in for now — if it's not the right time, just say the word and I'll pause."),
]


TEMPLATES: List[Dict[str, Any]] = [
    {
        "id": "tpl_fast_conversion",
        "name": "Fast Conversion",
        "description": "Aggressive, high-frequency, WhatsApp-heavy. Best for B2C with short cycles and small deals.",
        "duration_days": 7,
        "match_rules": {
            "market_in": ["B2C"],
            "cycle_in": ["< 1 week"],
            "deal_size_in": ["< 50K"],
        },
        "touchpoints": FAST_CONVERSION,
    },
    {
        "id": "tpl_warm_nurture",
        "name": "Warm Nurture",
        "description": "Friendly, value-led nurture for B2C with mid-tier deals.",
        "duration_days": 10,
        "match_rules": {
            "market_in": ["B2C"],
            "cycle_in": ["< 1 week", "1-4 weeks"],
            "deal_size_in": ["50K - 5L"],
        },
        "touchpoints": WARM_NURTURE,
    },
    {
        "id": "tpl_considered_sale",
        "name": "Considered Sale",
        "description": "Trust-building B2B sequence with a mid-cycle human escalation. Best for mid/large B2B deals.",
        "duration_days": 21,
        "match_rules": {
            "market_in": ["B2B", "Both"],
            "cycle_in": ["1-4 weeks", "1-3 months"],
            "deal_size_in": ["50K - 5L", "5L - 50L"],
        },
        "touchpoints": CONSIDERED_SALE,
    },
    {
        "id": "tpl_enterprise_track",
        "name": "Enterprise Track",
        "description": "Multi-stakeholder, long-cycle enterprise sequence with structured human prompts.",
        "duration_days": 45,
        "match_rules": {
            "market_in": ["B2B", "Both"],
            "cycle_in": ["3+ months"],
            "deal_size_in": ["5L - 50L", "50L+"],
        },
        "touchpoints": ENTERPRISE_TRACK,
    },
    {
        "id": "tpl_urgency_led",
        "name": "Urgency-Led",
        "description": "Deadline-anchored, FOMO-driven sequence compressed around an event date. Best for events businesses.",
        "duration_days": 7,
        "match_rules": {
            "industry_in": ["Events"],
        },
        "touchpoints": URGENCY_LED,
    },
    {
        "id": "tpl_high_intent_qualifier",
        "name": "High-Intent Qualifier",
        "description": "Site-visit-focused qualifier with rapid human escalation. Best for real estate.",
        "duration_days": 14,
        "match_rules": {
            "industry_in": ["Real Estate"],
        },
        "touchpoints": HIGH_INTENT_QUALIFIER,
    },
    {
        "id": "tpl_abandoned_interest",
        "name": "Abandoned Interest",
        "description": "Product-aware fast nurture with discount trigger at +72h. Best for B2C e-commerce.",
        "duration_days": 5,
        "match_rules": {
            "industry_in": ["E-commerce"],
            "market_in": ["B2C"],
        },
        "touchpoints": ABANDONED_INTEREST,
    },
    {
        "id": "tpl_standard",
        "name": "Standard",
        "description": "Balanced 7-touchpoint fallback when no industry-specific template matches.",
        "duration_days": 14,
        "match_rules": {},
        "touchpoints": STANDARD,
    },
]


# ─── Auto-selection logic ────────────────────────────────────────────────────
def select_template(onboarding: Dict[str, Any]) -> Dict[str, Any]:
    """Pick the best-fit template for a tenant's onboarding answers.

    Priority:
      1. Industry-specific overrides (Events, Real Estate, E-commerce + B2C)
      2. Market + cycle + deal-size match (cycle is primary signal)
      3. Fallback to Standard.
    """
    bp = (onboarding or {}).get("business_profile") or {}
    sp = (onboarding or {}).get("sales_process") or {}
    industry = (bp.get("industry") or "").strip()
    market = (bp.get("primary_market") or "B2B").strip()
    cycle = (sp.get("sales_cycle") or "1-4 weeks").strip()
    deal_size = (sp.get("deal_size") or "50K - 5L").strip()

    by_id = {t["id"]: t for t in TEMPLATES}

    # 1. Industry overrides
    if industry == "Events":
        return _ret(by_id["tpl_urgency_led"], industry, market, cycle, deal_size, "industry=Events")
    if industry == "Real Estate":
        return _ret(by_id["tpl_high_intent_qualifier"], industry, market, cycle, deal_size, "industry=Real Estate")
    if industry == "E-commerce" and market == "B2C":
        return _ret(by_id["tpl_abandoned_interest"], industry, market, cycle, deal_size, "industry=E-commerce + B2C")

    # 2. Market + cycle (primary) + deal_size (secondary)
    if market == "B2C" and cycle == "< 1 week" and deal_size == "< 50K":
        return _ret(by_id["tpl_fast_conversion"], industry, market, cycle, deal_size, "B2C + short cycle + small deal")
    if market == "B2C" and cycle in ("< 1 week", "1-4 weeks"):
        return _ret(by_id["tpl_warm_nurture"], industry, market, cycle, deal_size, "B2C + short/medium cycle")
    if market in ("B2B", "Both") and cycle in ("1-4 weeks", "1-3 months"):
        return _ret(by_id["tpl_considered_sale"], industry, market, cycle, deal_size, "B2B + medium cycle")
    if market in ("B2B", "Both") and cycle == "3+ months":
        return _ret(by_id["tpl_enterprise_track"], industry, market, cycle, deal_size, "B2B + long cycle")

    # 3. Fallback
    return _ret(by_id["tpl_standard"], industry, market, cycle, deal_size, "fallback")


def _ret(template: Dict[str, Any], industry: str, market: str, cycle: str, deal_size: str, reason: str) -> Dict[str, Any]:
    return {
        **template,
        "selection": {
            "industry": industry,
            "market": market,
            "cycle": cycle,
            "deal_size": deal_size,
            "reason": reason,
        },
    }
