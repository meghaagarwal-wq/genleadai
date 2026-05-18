"""Sales Channel Preferences + Hot Integrations Leaderboard — Iter 60.

User-side endpoints
-------------------
GET  /api/tenant/sales-channels        — read current preferences
PUT  /api/tenant/sales-channels        — save/update preferences (Owner/Admin)
GET  /api/tenant/sales-channels/recommendations — derive recommended integrations
                                          + a first-touch workflow rule from the
                                          selected channels (used by the
                                          touchpoint generator + Lead cards).

Admin-only
----------
GET /api/admin/hot-integrations — aggregate `integration_waitlist` to find the
                                  most-requested coming-soon tools across the
                                  platform. Drives the "which integration should
                                  I build next?" leaderboard on Master Admin.

Storage
-------
tenants.settings.sales_channels = {
  selected_channels: [...],
  priority_order: [...],
  primary_channel: "Email",
  fallback_channels: [...],
  conversation_style: "consultative",
  selected_preset: "usa_b2b_saas",
  disabled_channels: [...],
  updated_at: <iso>,
}
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import db, get_current_user
from routes.tenants import get_active_tenant

router = APIRouter(prefix="/api", tags=["sales-channels"])

tenants_col = db["tenants"]
waitlist_col = db["integration_waitlist"]


# ─── Catalog of channels + styles + presets ─────────────────────────────────
CHANNELS = [
    {"key": "whatsapp", "label": "WhatsApp",     "blurb": "Fast replies. India/UAE-heavy audiences, founder-led sales, service businesses."},
    {"key": "email",    "label": "Email",        "blurb": "B2B + SaaS, formal sales conversations, USA/UAE/enterprise audiences."},
    {"key": "linkedin", "label": "LinkedIn",     "blurb": "Professional outreach. Founder-led networking + B2B decision makers."},
    {"key": "sms",      "label": "SMS",          "blurb": "Appointment reminders + quick nudges."},
    {"key": "phone",    "label": "Phone / AI Call", "blurb": "High-intent leads, demo confirmations, qualification calls."},
    {"key": "website_chat", "label": "Website Chat", "blurb": "Live website visitors and inbound questions."},
]

STYLES = [
    {"key": "professional", "label": "Professional", "blurb": "Formal, clear, enterprise/B2B."},
    {"key": "founder_led",  "label": "Founder-led",  "blurb": "Direct, warm, human, startup selling."},
    {"key": "consultative", "label": "Consultative", "blurb": "Insight-first, asks questions before pitching."},
    {"key": "friendly",     "label": "Friendly",     "blurb": "Light, conversational, D2C/service businesses."},
    {"key": "premium",      "label": "Premium",      "blurb": "Polished, high-trust, luxury/high-ticket offers."},
]

PRESETS = [
    {"key": "india_founder_led", "label": "India Founder-Led Sales",
     "priority_order": ["whatsapp", "phone", "email"], "style": "founder_led"},
    {"key": "usa_b2b_saas", "label": "USA B2B SaaS",
     "priority_order": ["email", "linkedin", "phone"], "style": "consultative"},
    {"key": "uae_high_ticket", "label": "UAE High-Ticket Sales",
     "priority_order": ["email", "linkedin", "whatsapp", "phone"], "style": "premium"},
    {"key": "d2c_ecom", "label": "D2C / E-commerce",
     "priority_order": ["whatsapp", "sms", "email"], "style": "friendly"},
    {"key": "enterprise", "label": "Enterprise Sales",
     "priority_order": ["email", "linkedin", "phone"], "style": "professional"},
    {"key": "webinar_funnel", "label": "Webinar Funnel",
     "priority_order": ["email", "whatsapp", "sms"], "style": "friendly"},
    {"key": "outbound_sales", "label": "Outbound Sales",
     "priority_order": ["email", "linkedin"], "style": "consultative"},
]

# Channel → recommended integrations (mix of LIVE + Coming-Soon catalog types).
CHANNEL_INTEGRATIONS = {
    "whatsapp": [
        {"type": "whatsapp_biz",  "label": "WhatsApp Business API", "live": False},
    ],
    "email": [
        {"type": "gmail",      "label": "Gmail",          "live": False},
        {"type": "outlook",    "label": "Outlook",        "live": False},
        {"type": "zoho_mail",  "label": "Zoho Mail",      "live": False},
        {"type": "saleshandy", "label": "Saleshandy",     "live": True},
        {"type": "instantly",  "label": "Instantly.ai",   "live": True},
        {"type": "smartlead",  "label": "Smartlead",      "live": False},
    ],
    "linkedin": [
        {"type": "lemlist",         "label": "Lemlist",                  "live": True},
        {"type": "phantombuster",   "label": "PhantomBuster",            "live": False},
        {"type": "sales_navigator", "label": "LinkedIn Sales Navigator", "live": False},
    ],
    "sms": [
        {"type": "twilio_sms", "label": "SMS (Twilio)", "live": False},
        {"type": "msg91_sms",  "label": "SMS (MSG91)",  "live": False},
    ],
    "phone": [
        {"type": "twilio_sms", "label": "Twilio Voice (via Twilio)", "live": False},
        {"type": "exotel",     "label": "Exotel",                    "live": False},
    ],
    "website_chat": [
        {"type": "website_chat", "label": "Website Chat", "live": False},
    ],
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _channel_keys() -> set:
    return {c["key"] for c in CHANNELS}


def _style_keys() -> set:
    return {s["key"] for s in STYLES}


# ─── Public catalog endpoint (used by both onboarding step + Settings tab) ──
@router.get("/sales-channels/catalog")
async def sales_channels_catalog():
    """Return the static catalog so the UI can render channel + style + preset cards."""
    return {"channels": CHANNELS, "styles": STYLES, "presets": PRESETS}


# ─── Read + write tenant preferences ────────────────────────────────────────
class SalesChannelsPayload(BaseModel):
    selected_channels: List[str] = Field(default_factory=list)
    priority_order: List[str] = Field(default_factory=list)
    conversation_style: Optional[str] = Field(default=None)
    selected_preset: Optional[str] = Field(default=None)


def _get_prefs(tenant: dict) -> dict:
    return (tenant.get("settings") or {}).get("sales_channels") or {}


@router.get("/tenant/sales-channels")
async def get_sales_channels(tenant: dict = Depends(get_active_tenant)):
    prefs = _get_prefs(tenant)
    return prefs or {
        "selected_channels": [],
        "priority_order": [],
        "primary_channel": None,
        "fallback_channels": [],
        "conversation_style": None,
        "selected_preset": None,
        "disabled_channels": [],
    }


@router.put("/tenant/sales-channels")
async def update_sales_channels(
    payload: SalesChannelsPayload,
    tenant: dict = Depends(get_active_tenant),
):
    role = tenant.get("_member_role")
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")

    valid_channels = _channel_keys()
    selected = [c for c in payload.selected_channels if c in valid_channels]
    # Reconstruct a clean priority_order: only channels that are selected, in the
    # order the user provided. Append any missing selected channels at the end.
    seen: list[str] = []
    for c in payload.priority_order:
        if c in selected and c not in seen:
            seen.append(c)
    for c in selected:
        if c not in seen:
            seen.append(c)
    priority_order = seen

    style = payload.conversation_style if payload.conversation_style in _style_keys() else None
    preset = payload.selected_preset

    primary = priority_order[0] if priority_order else None
    fallback = priority_order[1:] if priority_order else []
    disabled = [c for c in valid_channels if c not in selected]

    prefs = {
        "selected_channels": selected,
        "priority_order": priority_order,
        "primary_channel": primary,
        "fallback_channels": fallback,
        "conversation_style": style,
        "selected_preset": preset,
        "disabled_channels": disabled,
        "updated_at": _now_iso(),
    }
    tenants_col.update_one(
        {"id": tenant["id"]},
        {"$set": {"settings.sales_channels": prefs}},
    )
    return {"ok": True, "preferences": prefs}


# ─── Recommendation derivation ──────────────────────────────────────────────
@router.get("/tenant/sales-channels/recommendations")
async def get_recommendations(tenant: dict = Depends(get_active_tenant)):
    """Derive recommended integrations + a first-touch workflow rule from the
    saved channel preferences. Lead cards + the touchpoint generator can call
    this to know which channel to start with.
    """
    prefs = _get_prefs(tenant)
    selected = prefs.get("selected_channels") or []
    priority = prefs.get("priority_order") or selected
    primary = prefs.get("primary_channel")

    # Recommended integrations — de-duped by `type`, ordered by channel priority.
    seen_types: set[str] = set()
    recs: list[dict] = []
    for ch in priority:
        for r in CHANNEL_INTEGRATIONS.get(ch, []):
            if r["type"] in seen_types:
                continue
            seen_types.add(r["type"])
            recs.append({**r, "channel": ch})

    # First-touch workflow rule the lead generator can use as a default.
    primary_action_map = {
        "email": "Send email intro",
        "whatsapp": "Send WhatsApp intro message",
        "linkedin": "View LinkedIn profile → send connection",
        "sms": "Send SMS nudge",
        "phone": "Schedule phone / AI qualification call",
        "website_chat": "Engage on website chat",
    }
    workflow_rule = {
        "trigger": "New lead received",
        "primary_action": primary_action_map.get(primary or "", None),
        "fallback_chain": [primary_action_map.get(c) for c in priority[1:3] if primary_action_map.get(c)],
        "stop_condition": "Lead books demo or replies negatively",
    } if primary else None

    return {
        "recommendations": recs,
        "workflow_rule": workflow_rule,
        "primary_channel": primary,
        "priority_order": priority,
    }


# ─── Master Admin: hot integrations leaderboard ─────────────────────────────
@router.get("/admin/hot-integrations")
async def hot_integrations(current_user: dict = Depends(get_current_user)):
    """Aggregate integration_waitlist across all tenants — the 'build this next'
    leaderboard. Master Admin only."""
    if (current_user.get("role") or "").lower() != "admin":
        raise HTTPException(status_code=403, detail="Master Admin only")

    pipeline = [
        {"$group": {
            "_id": "$integration_type",
            "request_count": {"$sum": 1},
            "tenant_count": {"$addToSet": "$tenant_id"},
            "last_request": {"$max": "$joined_at"},
            "sample_notes": {"$push": "$note"},
        }},
        {"$project": {
            "_id": 0,
            "integration_type": "$_id",
            "request_count": 1,
            "tenant_count": {"$size": "$tenant_count"},
            "last_request": 1,
            "sample_notes": {"$slice": ["$sample_notes", 3]},
        }},
        {"$sort": {"request_count": -1, "last_request": -1}},
        {"$limit": 15},
    ]
    rows = list(waitlist_col.aggregate(pipeline))
    # Trim empty notes; cap length
    for r in rows:
        r["sample_notes"] = [n for n in (r.get("sample_notes") or []) if (n or "").strip()][:3]
    return {"hot": rows, "total_requests": sum(r["request_count"] for r in rows)}
