"""ARIA — Batch 4 Intelligence Service.

Takes raw crawl output from `services.crawl_service.crawl_prospect()` and
synthesises it via Claude Sonnet 4.5 into a structured Intelligence
Profile, plus generates an Outreach Playbook and channel-adaptive
messages (WhatsApp / Email / LinkedIn) on demand.

All Claude traffic routes through `services.claude_service.claude_call`
(Batch 3 architectural rule — V10).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from deps import db
from services.claude_service import claude_call, TaskType, ClaudeServiceError

logger = logging.getLogger("intel_service")

intel_profiles_col = db["intel_profiles"]
intel_profiles_col.create_index([("tenant_id", 1), ("lead_id", 1)], unique=True)

# ─── Canonical signal taxonomy (Batch 4 spec) ───────────────────────────
SIGNAL_TYPES = [
    "intent",            # actively buying / RFP / "looking for X"
    "growth",            # hiring, funding, expansion, new market
    "pain",              # complaints, frustration, churn signals
    "trigger_event",     # acquisition, exec change, product launch
    "competitive",       # mentions of competitors or replacements
    "buying_authority",  # role / decision-maker validation
    "engagement",        # social posts, replies, public activity
    "risk",              # disqualifiers, blockers, bad-fit cues
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Synthesis: crawl → signals ─────────────────────────────────────────
def _compact_crawl_for_prompt(crawl: Dict[str, Any]) -> str:
    """Compress the crawl payload to keep us under token budget."""
    lp = crawl.get("linkedin_profile") or {}
    lc = crawl.get("linkedin_company") or {}
    exp_summary = []
    for e in (lp.get("experiences") or [])[:5]:
        exp_summary.append(
            f"- {e.get('title','?')} at {e.get('company','?')} ({e.get('starts_at',{}).get('year','?')}–{e.get('ends_at',{}).get('year','present')})"
        )
    edu_summary = []
    for e in (lp.get("education") or [])[:3]:
        edu_summary.append(f"- {e.get('degree_name') or e.get('field_of_study') or '?'} @ {e.get('school','?')}")

    web = "\n".join(
        f"- {r.get('title','?')} — {r.get('snippet','')[:160]} ({r.get('source','')})"
        for r in (crawl.get("web_results") or [])[:8]
    ) or "(none)"
    news = "\n".join(
        f"- {n.get('date','')}: {n.get('title','?')} — {n.get('snippet','')[:160]} ({n.get('source','')})"
        for n in (crawl.get("news_results") or [])[:6]
    ) or "(none)"

    return f"""LINKEDIN PROFILE:
- Name: {lp.get('full_name') or '?'}
- Headline: {lp.get('headline') or '?'}
- Current title: {lp.get('occupation') or '?'}
- Location: {lp.get('city') or '?'}, {lp.get('country_full_name') or '?'}
- Summary: {(lp.get('summary') or '')[:500]}
- Experiences (last 5):
{chr(10).join(exp_summary) or '(none)'}
- Education:
{chr(10).join(edu_summary) or '(none)'}
- Follower count: {lp.get('follower_count') or '?'}

LINKEDIN COMPANY:
- Name: {lc.get('name') or '?'}
- Industry: {lc.get('industry') or '?'}
- Size: {lc.get('company_size_on_linkedin') or lc.get('company_size') or '?'}
- HQ: {lc.get('hq', {}).get('city') if isinstance(lc.get('hq'), dict) else lc.get('hq') or '?'}
- Description: {(lc.get('description') or '')[:400]}
- Specialities: {', '.join(lc.get('specialities') or [])[:240]}

WEB MENTIONS (Google organic):
{web}

NEWS MENTIONS (last 30d):
{news}
"""


async def synthesise_intel(
    *, tenant_id: str, lead_id: str, lead_meta: Dict[str, Any], crawl: Dict[str, Any]
) -> Dict[str, Any]:
    """Run Claude Sonnet 4.5 synthesis. Returns the parsed Intelligence
    Profile and persists it to `intel_profiles`."""
    compact = _compact_crawl_for_prompt(crawl)

    system = (
        "You are ARIA's prospect-intelligence analyst. Given multi-platform crawl "
        "data about a prospect, extract structured signals to power outbound sales. "
        "Always return strict JSON only — no preamble, no markdown fences."
    )
    schema_hint = (
        '{"summary": string (3–4 sentences, founder-readable, no marketing fluff), '
        '"signals": [ {"type": one of [intent,growth,pain,trigger_event,competitive,buying_authority,engagement,risk], '
        '"label": short headline, "evidence": exact quote or fact from the data, '
        '"confidence": "high"|"med"|"low", "source": "linkedin"|"news"|"web"|"inferred"} ], '
        '"interests":  [string, ...]  (3-6 inferred topics this person cares about), '
        '"risk_flags": [{"label": string, "severity": "high"|"med"|"low", "reason": string}], '
        '"buying_authority": {"role_seniority": "ic"|"manager"|"director"|"vp"|"exec"|"owner", "decision_maker_likelihood": 0-100}, '
        '"fit_score": 0-100 (overall ICP+intent fit), '
        '"best_hook": string (one specific opener fragment grounded in the data)}'
    )

    prompt = (
        f"PROSPECT META\n- Lead name: {lead_meta.get('name','?')}\n- Company: {lead_meta.get('company','?')}\n"
        f"- Email domain: {lead_meta.get('domain','?')}\n- Stated ICP: {lead_meta.get('icp','?')}\n\n"
        f"CRAWL DATA\n{compact}\n\n"
        f"Return ONLY a JSON object matching this schema:\n{schema_hint}\n\n"
        "Rules:\n"
        "- At least 4 signals if the data supports it.\n"
        "- `evidence` must be a quoted fragment from the data — never invent.\n"
        "- If a `risk` signal is found, it MUST also appear in `risk_flags`.\n"
        "- `best_hook` must reference one concrete data point (a company news item, a role change, a specific post).\n"
        "- No JSON outside the object. No code fences."
    )

    try:
        profile = await claude_call(
            task_type=TaskType.INSIGHT_GENERATION,
            system=system,
            prompt=prompt,
            tenant_id=tenant_id,
            session_id=f"intel-synth-{lead_id}",
            response_format="json",
        )
    except ClaudeServiceError as e:
        logger.warning("intel_service: synthesis failed for lead=%s: %s", lead_id, e)
        profile = {
            "summary": "Intelligence synthesis unavailable. Re-run when crawl + Claude are healthy.",
            "signals": [],
            "interests": [],
            "risk_flags": [],
            "buying_authority": {"role_seniority": "unknown", "decision_maker_likelihood": 0},
            "fit_score": 0,
            "best_hook": "",
            "synthesis_error": str(e)[:300],
        }

    if not isinstance(profile, dict):
        profile = {"summary": "Malformed synthesis", "signals": [], "interests": [], "risk_flags": []}

    # Normalize signals — clamp `type` to canonical taxonomy
    raw_signals = profile.get("signals") or []
    norm_signals: List[Dict[str, Any]] = []
    for s in raw_signals:
        if not isinstance(s, dict):
            continue
        stype = (s.get("type") or "").strip().lower()
        if stype not in SIGNAL_TYPES:
            # Loose remap
            stype = {
                "buying_intent": "intent", "buying-intent": "intent",
                "hiring": "growth", "funding": "growth", "expansion": "growth",
                "competitor": "competitive", "comp": "competitive",
                "engagement_signal": "engagement", "activity": "engagement",
                "authority": "buying_authority", "role": "buying_authority",
                "blocker": "risk", "disqualifier": "risk",
            }.get(stype, "engagement")
        norm_signals.append({
            "type": stype,
            "label": (s.get("label") or "")[:140],
            "evidence": (s.get("evidence") or "")[:400],
            "confidence": s.get("confidence") if s.get("confidence") in ("high", "med", "low") else "med",
            "source": s.get("source") if s.get("source") in ("linkedin", "news", "web", "inferred") else "inferred",
        })

    doc = {
        "tenant_id": tenant_id,
        "lead_id": lead_id,
        "summary": (profile.get("summary") or "")[:1200],
        "signals": norm_signals,
        "interests": [str(i)[:80] for i in (profile.get("interests") or [])[:8]],
        "risk_flags": (profile.get("risk_flags") or [])[:6],
        "buying_authority": profile.get("buying_authority") or {},
        "fit_score": int(profile.get("fit_score") or 0),
        "best_hook": (profile.get("best_hook") or "")[:300],
        "synthesis_error": profile.get("synthesis_error"),
        "crawl_meta": {
            "sources_attempted": crawl.get("sources_attempted") or [],
            "sources_succeeded": crawl.get("sources_succeeded") or [],
            "calls_made": crawl.get("calls_made") or 0,
            "errors": crawl.get("errors") or [],
        },
        "updated_at": _now_iso(),
    }
    intel_profiles_col.update_one(
        {"tenant_id": tenant_id, "lead_id": lead_id},
        {"$set": doc, "$setOnInsert": {"created_at": _now_iso()}},
        upsert=True,
    )
    return doc


# ─── Outreach Playbook generator ────────────────────────────────────────
async def generate_playbook(
    *, tenant_id: str, lead_id: str, lead_meta: Dict[str, Any], profile: Dict[str, Any]
) -> Dict[str, Any]:
    """Channel + timing + opening message + lead magnet + follow-up plan."""
    signals_brief = "\n".join(
        f"- [{s['type']}/{s['confidence']}] {s['label']}: {s['evidence'][:120]}"
        for s in (profile.get("signals") or [])[:8]
    ) or "(no signals)"
    risks_brief = "; ".join(r.get("label", "") for r in (profile.get("risk_flags") or [])) or "(none)"

    system = (
        "You are ARIA's outreach strategist. Given a prospect's intelligence "
        "profile, design the single best outbound playbook. JSON only."
    )
    prompt = f"""PROSPECT: {lead_meta.get('name','?')} · {lead_meta.get('company','?')}
ICP FIT: {profile.get('fit_score', 0)}/100
DECISION-MAKER LIKELIHOOD: {(profile.get('buying_authority') or {{}}).get('decision_maker_likelihood', 0)}/100
SUMMARY: {profile.get('summary','')[:400]}

SIGNALS:
{signals_brief}

RISKS: {risks_brief}

INTERESTS: {', '.join(profile.get('interests') or [])}

BEST HOOK SEED: {profile.get('best_hook','')}

Return JSON with these keys:
- recommended_channel: one of [whatsapp, email, linkedin]
- channel_reason: 1 sentence
- send_timing: one of [now, today_business_hours, tomorrow_morning, mid_week, next_week]
- timing_reason: 1 sentence
- opening_message: ≤320 chars, references one specific signal, ends with one question
- lead_magnet: short string (resource / case study / data point) or null
- follow_up_plan: [{{"day": int (offset from send), "channel": one of [whatsapp,email,linkedin], "intent": one of [bump,value_drop,social_proof,soft_cta,meeting_cta,closure], "message_hint": string}}] — 3 steps
- success_signals: [string] — 2-3 reply cues to escalate
- abort_signals:   [string] — 2-3 reply cues to mark cold

No markdown, no code fences. JSON only."""

    try:
        playbook = await claude_call(
            task_type=TaskType.INSIGHT_GENERATION,
            system=system,
            prompt=prompt,
            tenant_id=tenant_id,
            session_id=f"intel-playbook-{lead_id}",
            response_format="json",
        )
    except ClaudeServiceError as e:
        logger.warning("intel_service: playbook failed for lead=%s: %s", lead_id, e)
        playbook = {
            "recommended_channel": "email",
            "channel_reason": "Default channel — Claude synthesis unavailable.",
            "send_timing": "tomorrow_morning",
            "timing_reason": "Safe default for B2B outbound.",
            "opening_message": f"Hi {lead_meta.get('first_name','there')} — saw your recent work and wanted to connect briefly. Worth 15 mins this week?",
            "lead_magnet": None,
            "follow_up_plan": [
                {"day": 3, "channel": "email", "intent": "value_drop", "message_hint": "Share one relevant insight."},
                {"day": 7, "channel": "linkedin", "intent": "social_proof", "message_hint": "Drop a customer outcome."},
                {"day": 12, "channel": "email", "intent": "soft_cta", "message_hint": "Short check-in."},
            ],
            "success_signals": ["Asks a question", "Books a call"],
            "abort_signals": ["Unsubscribes", "Says 'not interested'"],
            "_fallback": True,
            "_error": str(e)[:200],
        }

    intel_profiles_col.update_one(
        {"tenant_id": tenant_id, "lead_id": lead_id},
        {"$set": {"playbook": playbook, "playbook_updated_at": _now_iso()}},
    )
    return playbook


# ─── Channel-Adaptive composer ──────────────────────────────────────────
_CHANNEL_RULES = {
    "whatsapp": (
        "Channel: WhatsApp. Max 280 characters. Conversational, no salutation block, "
        "no signature. One emoji max (optional). End with one short question."
    ),
    "email": (
        "Channel: Email. Return JSON with `subject` (≤55 chars, no salesy phrases) and `body` "
        "(≤120 words, plain text, 2–3 short paragraphs, sign off with first name)."
    ),
    "linkedin": (
        "Channel: LinkedIn DM. ≤500 characters. Professional but warm. No emojis. Reference "
        "one of the prospect's signals or interests explicitly. End with a low-friction question."
    ),
}


async def compose_message(
    *,
    tenant_id: str,
    lead_id: str,
    channel: str,
    lead_meta: Dict[str, Any],
    profile: Dict[str, Any],
    user_steer: Optional[str] = None,
) -> Dict[str, Any]:
    """Channel-adaptive single-shot composer.

    Returns: {"channel": str, "message": str | dict, "ai_powered": bool, ...}
    For email, `message` is `{subject, body}`; for whatsapp/linkedin it's a string.
    """
    channel = (channel or "email").strip().lower()
    if channel not in _CHANNEL_RULES:
        channel = "email"

    signals_brief = "\n".join(
        f"- [{s['type']}] {s['label']}: {s['evidence'][:120]}"
        for s in (profile.get("signals") or [])[:6]
    ) or "(no signals)"

    system = (
        "You are ARIA, an AI sales agent drafting a single outbound message. "
        "Ground EVERY message in real signals from the intelligence profile. "
        "Never invent facts. Never use generic 'I came across your profile' openers. "
        + _CHANNEL_RULES[channel]
    )

    response_format = "json" if channel == "email" else None

    prompt = f"""PROSPECT: {lead_meta.get('name','?')} · {lead_meta.get('company','?')}
FIRST NAME: {lead_meta.get('first_name','there')}
ICP FIT: {profile.get('fit_score', 0)}/100

SIGNALS:
{signals_brief}

INTERESTS: {', '.join(profile.get('interests') or [])}

BEST HOOK SEED (you may use or improve on this): {profile.get('best_hook','')}

USER STEER (founder note, optional): {user_steer or '(none)'}

Write ONE message for {channel.upper()}. Reference at least ONE specific signal above. {('Return strict JSON {subject, body}.' if channel=='email' else 'Return ONLY the message text — no preamble, no labels.')}"""

    try:
        result = await claude_call(
            task_type=TaskType.TOUCHPOINT_GENERATION,
            system=system,
            prompt=prompt,
            tenant_id=tenant_id,
            session_id=f"intel-compose-{lead_id}-{channel}",
            response_format=response_format,
            sanitize_user_input=bool(user_steer),
        )
    except ClaudeServiceError as e:
        logger.warning("intel_service: compose failed lead=%s channel=%s: %s", lead_id, channel, e)
        fallback = f"Hi {lead_meta.get('first_name','there')} — saw your recent work and have a quick idea worth 15 mins this week. Open to it?"
        if channel == "email":
            return {
                "channel": "email",
                "message": {"subject": "Quick idea", "body": fallback},
                "ai_powered": False, "error": str(e)[:200],
            }
        return {"channel": channel, "message": fallback, "ai_powered": False, "error": str(e)[:200]}

    # Normalise
    if channel == "email":
        if isinstance(result, dict):
            msg = {
                "subject": (result.get("subject") or "Quick idea")[:80],
                "body": (result.get("body") or "")[:2000],
            }
        else:
            msg = {"subject": "Quick idea", "body": str(result)[:2000]}
        return {"channel": "email", "message": msg, "ai_powered": True}

    text = (result if isinstance(result, str) else json.dumps(result)).strip().strip('"').strip("'")
    return {"channel": channel, "message": text, "ai_powered": True}


__all__ = [
    "synthesise_intel",
    "generate_playbook",
    "compose_message",
    "SIGNAL_TYPES",
]
