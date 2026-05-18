"""Iter 62 — Simulate Inbound Lead.

Walks a hypothetical new lead through the same intelligence layer Aria uses
on real leads, but **never writes to the leads collection**. Used to make the
"Aria reads signals → scores → picks a channel → drafts the message" loop
tangible for first-time users on the Integration Hub.

The walkthrough returns 5 ordered steps:
  1. captured        — source + UTM + form_answers parsed
  2. enriched        — heuristic enrichment from email domain
  3. icp_scored      — Aria's tier + score with a reasoning trail
  4. channel_chosen  — uses saved sales-channel preferences (primary + fallback)
  5. message_drafted — Claude-rendered first-touch message (heuristic fallback)
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from deps import db, get_current_user
from routes.tenants import get_active_tenant
from routes.touchpoint_preview import _claude_render, _heuristic_render
from routes.sales_channels import CHANNELS

router = APIRouter(prefix="/api/integrations", tags=["simulate-inbound"])


# Disposable / consumer email domains — used for "Quality" signal.
CONSUMER_DOMAINS = {
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com",
    "live.com", "aol.com", "msn.com", "protonmail.com",
}


SOURCES = [
    {"key": "meta_lead_ad",   "label": "Meta Lead Ad",          "intent_hint": "high"},
    {"key": "google_ads",     "label": "Google Ads Lead Form",  "intent_hint": "high"},
    {"key": "typeform",       "label": "Typeform",              "intent_hint": "medium"},
    {"key": "website_form",   "label": "Website Form",          "intent_hint": "medium"},
    {"key": "linkedin_lead",  "label": "LinkedIn Lead Gen",     "intent_hint": "high"},
    {"key": "saleshandy",     "label": "Saleshandy reply",      "intent_hint": "very_high"},
    {"key": "lemlist",        "label": "Lemlist reply",         "intent_hint": "very_high"},
    {"key": "manual",         "label": "Manual / Other",        "intent_hint": "medium"},
]


class SimulateInboundPayload(BaseModel):
    source: str = "meta_lead_ad"
    first_name: str = "Priya"
    last_name: str = "Mehta"
    email: str = "priya@acme.com"
    phone: Optional[str] = "+919876500001"
    company: Optional[str] = "Acme Co"
    utm_campaign: Optional[str] = "demo-request-q1-2026"
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    form_answers: Optional[str] = "Looking for an AI sales PA for our 20-person SaaS team."


class StepOutput(BaseModel):
    key: str
    title: str
    summary: str
    detail: dict


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _source_meta(key: str) -> dict:
    return next((s for s in SOURCES if s["key"] == key), SOURCES[-1])


def _enrich(email: str, company: str) -> dict:
    """Cheap heuristic enrichment from the email domain.
    In production this would call Apollo / Hunter etc. — for the simulator we
    just parse the domain and flag consumer vs business.
    """
    domain = (email.split("@")[-1] or "").lower()
    is_consumer = domain in CONSUMER_DOMAINS or not domain or "." not in domain
    return {
        "domain": domain,
        "is_business_email": not is_consumer,
        "company_resolved": company or (domain.split(".")[0].title() if not is_consumer else ""),
        "enrichment_source": "domain_heuristic",
    }


def _score_icp(payload: SimulateInboundPayload, enrichment: dict) -> dict:
    """Lightweight rules-based ICP scorer that mirrors Aria's tiering logic.

    Score breakdown (0-100):
      +30  business email (not gmail/yahoo/etc.)
      +25  source intent_hint >= 'high'
      +10  source intent_hint == 'very_high' (additive)
      +15  form_answers contains buying-intent words
      +10  utm_campaign present
      +10  company filled
    Then tier: 80+ = "hot", 60+ = "warm", 40+ = "cold", else "poor_fit".
    """
    score = 0
    reasons: list[str] = []

    if enrichment["is_business_email"]:
        score += 30
        reasons.append(f"Business email — {enrichment['domain']}")
    else:
        reasons.append(f"Consumer email — {enrichment['domain']} (−30)")

    src = _source_meta(payload.source)
    intent = src["intent_hint"]
    if intent in ("high", "very_high"):
        score += 25
        reasons.append(f"{src['label']} typically high-intent")
    if intent == "very_high":
        score += 10
        reasons.append(f"{src['label']} = direct reply (very high intent)")

    answers = (payload.form_answers or "").lower()
    buying_words = ["budget", "buy", "demo", "trial", "pricing", "quote", "evaluate", "looking for", "interested"]
    matched = [w for w in buying_words if w in answers]
    if matched:
        score += 15
        reasons.append(f"Form text contains buying-intent words: {', '.join(matched[:3])}")

    if payload.utm_campaign:
        score += 10
        reasons.append(f"Attributable campaign: {payload.utm_campaign}")

    if payload.company:
        score += 10
        reasons.append(f"Company provided: {payload.company}")

    score = min(score, 100)
    tier = "hot" if score >= 80 else "warm" if score >= 60 else "cold" if score >= 40 else "poor_fit"
    next_step = {
        "hot": "Alert founder immediately + start first-touch within 15 minutes.",
        "warm": "Send first-touch within 1 hour. Add to high-intent nurture sequence.",
        "cold": "Add to standard nurture. Re-evaluate after one engagement signal.",
        "poor_fit": "Tag as poor fit. Skip nurture but keep on CRM for future.",
    }[tier]
    return {
        "score": score,
        "tier": tier,
        "reasons": reasons,
        "recommended_next_step": next_step,
    }


def _pick_channel(tenant: dict, tier: str) -> dict:
    """Use saved sales-channel prefs (if any) to choose the first-touch channel.
    Falls back to a tier-based default if no prefs are saved."""
    prefs = (tenant.get("settings") or {}).get("sales_channels") or {}
    priority = prefs.get("priority_order") or []
    primary = prefs.get("primary_channel")
    preset = prefs.get("selected_preset")

    if not primary:
        # No prefs → tier-based default
        primary = "email"
        priority = ["email"]
        reason = "No sales channel preference saved yet — defaulting to Email. (Set this in Settings → Sales Channels.)"
    else:
        order = " → ".join(primary if isinstance(primary, list) else priority) if priority else primary
        if preset:
            reason = f"Starting with {primary.title()} because your saved preset ({preset.replace('_', ' ').title()}) says: {order}."
        else:
            reason = f"Starting with {primary.title()} based on your channel priority: {order}."

    return {
        "primary_channel": primary,
        "priority_order": priority,
        "selected_preset": preset,
        "reason": reason,
    }


async def _draft_message(payload: SimulateInboundPayload, tenant: dict, channel: str) -> dict:
    """Use the existing Claude renderer (with heuristic fallback) to draft a
    first-touch message. We synthesise a fake touchpoint to reuse the existing
    rendering pipeline."""
    business = {
        "business_name": tenant.get("name") or "your business",
        "industry": (tenant.get("settings") or {}).get("industry") or "B2B",
        "description": (tenant.get("settings") or {}).get("product_description") or "",
        "primary_market": (tenant.get("settings") or {}).get("primary_market") or "B2B",
    }
    persona = {
        "aria_name": (tenant.get("settings") or {}).get("aria_name") or "Aria",
        "tone": ((tenant.get("settings") or {}).get("sales_channels") or {}).get("conversation_style")
                or "friendly_professional",
        "language": "English",
    }
    sales = {
        "product_description": business["description"] or business["business_name"],
    }
    fake_tp = {
        "index": 1,
        "channel": channel,
        "message_type": "intro",
        "message_template": (
            f"Hi {{{{first_name}}}}, this is {persona['aria_name']} from {business['business_name']}. "
            "I saw you reached out — quick question on what prompted you to look right now?"
        ),
    }
    try:
        ai_text = await _claude_render(fake_tp, business, persona, sales)
    except Exception:
        ai_text = None
    ai_powered = bool(ai_text)
    if not ai_text:
        ai_text = _heuristic_render(fake_tp, business, persona)
    # Token substitute the lead name for the simulator output
    rendered = ai_text.replace("{{first_name}}", payload.first_name)
    return {
        "channel": channel,
        "rendered_message": rendered,
        "ai_powered": ai_powered,
        "tone": persona["tone"],
        "aria_name": persona["aria_name"],
    }


@router.get("/simulate-inbound/sources")
async def list_simulator_sources():
    return {"sources": SOURCES, "channels": CHANNELS}


@router.post("/simulate-inbound")
async def simulate_inbound(
    payload: SimulateInboundPayload,
    tenant: dict = Depends(get_active_tenant),
    _user: dict = Depends(get_current_user),
):
    src = _source_meta(payload.source)

    # 1. Captured
    captured = {
        "source": payload.source,
        "source_label": src["label"],
        "fields_received": {
            "first_name": payload.first_name, "last_name": payload.last_name,
            "email": payload.email, "phone": payload.phone, "company": payload.company,
            "utm_campaign": payload.utm_campaign, "utm_source": payload.utm_source,
            "utm_medium": payload.utm_medium,
        },
        "form_answers": payload.form_answers,
        "captured_at": _now(),
    }

    # 2. Enriched
    enrichment = _enrich(payload.email, payload.company or "")

    # 3. ICP scored
    scoring = _score_icp(payload, enrichment)

    # 4. Channel chosen
    channel = _pick_channel(tenant, scoring["tier"])

    # 5. Message drafted (Claude or fallback)
    message = await _draft_message(payload, tenant, channel["primary_channel"])

    steps: List[StepOutput] = [
        StepOutput(
            key="captured",
            title=f"Lead captured from {src['label']}",
            summary=f"{payload.first_name} {payload.last_name} · {payload.email}",
            detail=captured,
        ),
        StepOutput(
            key="enriched",
            title="Aria enriched the lead",
            summary=(
                f"Business email — {enrichment['domain']}" if enrichment["is_business_email"]
                else f"Consumer email — {enrichment['domain']}"
            ),
            detail=enrichment,
        ),
        StepOutput(
            key="icp_scored",
            title=f"Aria scored intent: {scoring['tier'].upper()} ({scoring['score']}/100)",
            summary=scoring["recommended_next_step"],
            detail=scoring,
        ),
        StepOutput(
            key="channel_chosen",
            title=f"Aria will start on {channel['primary_channel'].title()}",
            summary=channel["reason"],
            detail=channel,
        ),
        StepOutput(
            key="message_drafted",
            title=f"Aria drafted the first-touch message ({channel['primary_channel'].title()})",
            summary=message["rendered_message"][:140] + ("…" if len(message["rendered_message"]) > 140 else ""),
            detail=message,
        ),
    ]
    return {
        "simulated_at": _now(),
        "is_simulation": True,
        "lead_persisted": False,  # importantly NOT written to leads collection
        "steps": [s.model_dump() for s in steps],
    }
