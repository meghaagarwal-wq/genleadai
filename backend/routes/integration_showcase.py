"""Demo Integration Showcase — iter160.

Single endpoint that returns the FULL integration catalog re-bucketed
into the marketing-facing taxonomy the founder uses on sales calls:
All / Outreach / Ads / Messaging / Enrichment / Scheduling /
Productivity / Social / Email / Payments.

Live status (connected / available / coming_soon) reflects the actual
integrations_hub SUPPORTED_TYPES list so the demo never bullshits a
client about what's wired vs planned.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends

from deps import db, get_current_user
from routes.integrations_hub import SUPPORTED_TYPES as LIVE_TYPES

router = APIRouter(prefix="/api/dashboard", tags=["dashboards"])


# ─── Showcase categories (marketing-facing) ─────────────────────────
# `key` → matches the pill ID on the frontend (lowercase, kebab-safe).
SHOWCASE_CATEGORIES = [
    {"key": "outreach",      "label": "Outreach",      "color": "#7C35DC",
     "blurb": "Multi-channel sales sequences across email + LinkedIn + cold outreach."},
    {"key": "ads",           "label": "Ads",           "color": "#F59E0B",
     "blurb": "Server-side conversion APIs for paid acquisition channels."},
    {"key": "messaging",     "label": "Messaging",     "color": "#25D366",
     "blurb": "WhatsApp / SMS / live chat. ARIA handles inbound replies in real time."},
    {"key": "enrichment",    "label": "Enrichment",    "color": "#0EA5E9",
     "blurb": "Lookup company + role + intent + email verification for cold lists."},
    {"key": "scheduling",    "label": "Scheduling",    "color": "#D97706",
     "blurb": "Calendar sync + meeting links so ARIA can book demo calls instantly."},
    {"key": "productivity",  "label": "Productivity",  "color": "#A78BFA",
     "blurb": "Notion / Sheets / no-code workflows that mirror your existing ops stack."},
    {"key": "social",        "label": "Social",        "color": "#0A66C2",
     "blurb": "LinkedIn lead-gen forms + sponsored content attribution + social listening."},
    {"key": "email",         "label": "Email",         "color": "#EC4899",
     "blurb": "Send + track outbound + inbound replies across Gmail, Outlook, Zoho Mail and ESPs."},
    {"key": "payments",      "label": "Payments",      "color": "#10B981",
     "blurb": "Detect closed-won via Stripe / Razorpay / PayPal — close-loop revenue attribution."},
]


# ─── Integration registry — single source of truth ──────────────────
# Each row: (type_id, label, primary_category, also_in_categories, status, brand_hex)
# `status`: "live" | "beta" | "coming_soon"
# Re-uses LIVE_TYPES for the truth on what's connected today.
_LIVE_IDS = set(LIVE_TYPES.keys())


def _status_for(type_id: str, default: str = "coming_soon") -> str:
    return "live" if type_id in _LIVE_IDS else default


SHOWCASE_INTEGRATIONS = [
    # ── Outreach ──
    {"id": "apollo",         "label": "Apollo.io",        "cats": ["outreach", "enrichment"],            "brand": "#0066FF"},
    {"id": "instantly",      "label": "Instantly.ai",     "cats": ["outreach", "email"],                 "brand": "#FF6B35"},
    {"id": "lemlist",        "label": "Lemlist",          "cats": ["outreach", "email"],                 "brand": "#FFCD00"},
    {"id": "saleshandy",     "label": "Saleshandy",       "cats": ["outreach", "email"],                 "brand": "#1E88E5"},
    {"id": "smartlead",      "label": "Smartlead",        "cats": ["outreach", "email"],                 "brand": "#6E59A5"},
    {"id": "phantombuster",  "label": "PhantomBuster",    "cats": ["outreach", "social"],                "brand": "#9C27B0"},
    {"id": "sales_navigator","label": "Sales Navigator",  "cats": ["outreach", "social"],                "brand": "#0A66C2"},
    {"id": "snov_io",        "label": "Snov.io",          "cats": ["outreach", "enrichment", "email"],   "brand": "#16A34A"},
    {"id": "hunter_io",      "label": "Hunter.io",        "cats": ["outreach", "enrichment", "email"],   "brand": "#F97316"},

    # ── Ads ──
    {"id": "google_ads",     "label": "Google Ads",       "cats": ["ads"],                               "brand": "#4285F4"},
    {"id": "meta_capi",      "label": "Meta Conversions", "cats": ["ads"],                               "brand": "#1877F2"},
    {"id": "meta_pixel",     "label": "Meta Pixel",       "cats": ["ads"],                               "brand": "#1877F2"},
    {"id": "linkedin_insight","label": "LinkedIn Insight","cats": ["ads", "social"],                     "brand": "#0A66C2"},
    {"id": "meta_lead_ads",  "label": "Meta Lead Ads",    "cats": ["ads", "social"],                     "brand": "#1877F2"},
    {"id": "ga4",            "label": "Google Analytics 4", "cats": ["ads"],                             "brand": "#F9AB00"},

    # ── Messaging ──
    {"id": "whatsapp_biz",   "label": "WhatsApp Business","cats": ["messaging"],                         "brand": "#25D366"},
    {"id": "twilio_sms",     "label": "Twilio SMS",       "cats": ["messaging"],                         "brand": "#F22F46"},
    {"id": "msg91_sms",      "label": "MSG91 SMS",        "cats": ["messaging"],                         "brand": "#FF6B35"},
    {"id": "website_chat",   "label": "Website Chat",     "cats": ["messaging"],                         "brand": "#7C35DC"},
    {"id": "telegram",       "label": "Telegram",         "cats": ["messaging"],                         "brand": "#26A5E4"},
    {"id": "slack",          "label": "Slack",            "cats": ["messaging", "productivity"],         "brand": "#4A154B"},

    # ── Enrichment ──
    {"id": "clearbit",       "label": "Clearbit",         "cats": ["enrichment"],                        "brand": "#0066FF"},
    {"id": "zoominfo",       "label": "ZoomInfo",         "cats": ["enrichment"],                        "brand": "#0F4DA8"},
    {"id": "rocketreach",    "label": "RocketReach",      "cats": ["enrichment"],                        "brand": "#FF6900"},

    # ── Scheduling ──
    {"id": "calendly",       "label": "Calendly",         "cats": ["scheduling"],                        "brand": "#006BFF"},
    {"id": "google_calendar","label": "Google Calendar",  "cats": ["scheduling"],                        "brand": "#4285F4"},
    {"id": "outlook_calendar","label": "Outlook Calendar","cats": ["scheduling"],                        "brand": "#0078D4"},
    {"id": "cal_com",        "label": "Cal.com",          "cats": ["scheduling"],                        "brand": "#000000"},
    {"id": "zoom",           "label": "Zoom",             "cats": ["scheduling"],                        "brand": "#2D8CFF"},
    {"id": "google_meet",    "label": "Google Meet",      "cats": ["scheduling"],                        "brand": "#00897B"},
    {"id": "ms_teams",       "label": "Microsoft Teams",  "cats": ["scheduling", "messaging"],           "brand": "#5059C9"},

    # ── Productivity ──
    {"id": "notion_db",      "label": "Notion",           "cats": ["productivity"],                      "brand": "#000000"},
    {"id": "google_sheets",  "label": "Google Sheets",    "cats": ["productivity"],                      "brand": "#0F9D58"},
    {"id": "airtable",       "label": "Airtable",         "cats": ["productivity"],                      "brand": "#FCB400"},
    {"id": "zapier",         "label": "Zapier",           "cats": ["productivity"],                      "brand": "#FF4A00"},
    {"id": "make",           "label": "Make.com",         "cats": ["productivity"],                      "brand": "#6D00CC"},
    {"id": "n8n",            "label": "n8n",              "cats": ["productivity"],                      "brand": "#EA4B71"},
    {"id": "hubspot",        "label": "HubSpot",          "cats": ["productivity"],                      "brand": "#FF7A59"},
    {"id": "salesforce",     "label": "Salesforce",       "cats": ["productivity"],                      "brand": "#00A1E0"},
    {"id": "zoho_crm",       "label": "Zoho CRM",         "cats": ["productivity"],                      "brand": "#E42527"},
    {"id": "pipedrive",      "label": "Pipedrive",        "cats": ["productivity"],                      "brand": "#1A1A1A"},

    # ── Social ──
    {"id": "linkedin_lead_gen","label": "LinkedIn Lead Gen", "cats": ["social", "ads"],                  "brand": "#0A66C2"},
    {"id": "twitter_x",      "label": "Twitter / X",      "cats": ["social"],                            "brand": "#000000"},
    {"id": "instagram",      "label": "Instagram",        "cats": ["social"],                            "brand": "#E4405F"},

    # ── Email ──
    {"id": "gmail",          "label": "Gmail",            "cats": ["email"],                             "brand": "#EA4335"},
    {"id": "outlook",        "label": "Outlook",          "cats": ["email"],                             "brand": "#0078D4"},
    {"id": "zoho_mail",      "label": "Zoho Mail",        "cats": ["email"],                             "brand": "#E42527"},
    {"id": "sendgrid",       "label": "SendGrid",         "cats": ["email"],                             "brand": "#1A82E2"},
    {"id": "resend",         "label": "Resend",           "cats": ["email"],                             "brand": "#000000"},
    {"id": "mailchimp",      "label": "Mailchimp",        "cats": ["email"],                             "brand": "#FFE01B"},

    # ── Payments ──
    {"id": "stripe",         "label": "Stripe",           "cats": ["payments"],                          "brand": "#635BFF"},
    {"id": "razorpay",       "label": "Razorpay",         "cats": ["payments"],                          "brand": "#3395FF"},
    {"id": "paypal",         "label": "PayPal",           "cats": ["payments"],                          "brand": "#00457C"},
    {"id": "square",         "label": "Square",           "cats": ["payments"],                          "brand": "#000000"},
]


def _build_rows(tenant_id: Optional[str]) -> list[dict]:
    """Enrich each integration row with its current status for this tenant."""
    configs = list(db["integration_configs"].find({"tenant_id": tenant_id}, {"_id": 0, "integration_type": 1, "status": 1}))
    connected = {c["integration_type"]: c.get("status") or "connected" for c in configs}
    rows = []
    for r in SHOWCASE_INTEGRATIONS:
        type_id = r["id"]
        if type_id in connected:
            status = "live"
        elif type_id in _LIVE_IDS:
            status = "available"  # supported but not connected for this tenant
        else:
            status = "coming_soon"
        rows.append({**r, "status": status})
    return rows


@router.get("/integration-showcase")
async def integration_showcase(
    category: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Return the full integration catalog re-bucketed for the demo dashboard.

    Query param `category` (lowercase pill key) filters server-side.
    Frontend uses the full payload + a client-side filter for snappier UX,
    so `category` is optional.
    """
    tenant_id = current_user.get("tenant_id") or ""
    rows = _build_rows(tenant_id)
    if category and category != "all":
        rows = [r for r in rows if category in r["cats"]]
    # Counts per pill (always full, even when filtering — for the "All (N)" label)
    full_rows = _build_rows(tenant_id)
    counts = {"all": len(full_rows)}
    for c in SHOWCASE_CATEGORIES:
        counts[c["key"]] = sum(1 for r in full_rows if c["key"] in r["cats"])
    return {
        "categories": SHOWCASE_CATEGORIES,
        "integrations": rows,
        "counts": counts,
    }
