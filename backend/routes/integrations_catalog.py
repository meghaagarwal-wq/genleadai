"""Integration Hub catalog, waitlist, and custom-request — Iter 59 (Option A).

Extends the existing `routes/integrations_hub.py` (which handles the *live*
integrations and their webhooks) with:

  - `/api/integrations/catalog` — the full marketplace catalog (live + coming-soon),
    grouped by the 7 categories from the spec.
  - `/api/integrations/setup-progress` — counts what's connected + a categorised
    checklist for the setup progress bar.
  - `/api/integrations/health` — health rollup for the connected tools.
  - `/api/integrations/data-flow` — what nodes to render in the data-flow preview.
  - `/api/integrations/waitlist/{type}` — express interest in a coming-soon tool.
  - `/api/integrations/custom-request` — submit a request for a missing tool.
  - `/api/integrations/test-lead` — fire a test lead through every connected
    outbound integration (Send Test Lead button).

This file is intentionally separate so the live integration logic stays untouched.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import db, get_current_user
from routes.tenants import get_active_tenant
from routes.integrations_hub import (
    SUPPORTED_TYPES as LIVE_TYPES,
    configs_col,
    _dispatch,
)

router = APIRouter(prefix="/api/integrations", tags=["integrations-catalog"])

waitlist_col = db["integration_waitlist"]
requests_col = db["integration_requests"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── The full catalog ───────────────────────────────────────────────────────
# Categories from the spec.
CATEGORIES = [
    {"key": "lead_source", "label": "Lead Sources", "color": "#16A34A",
     "blurb": "Capture inbound leads from your forms, ads, landing pages, webinars, and demo requests."},
    {"key": "outreach", "label": "Outbound Tools", "color": "#7C35DC",
     "blurb": "Sync cold outreach signals like opens, clicks, replies, connection accepts, and positive responses."},
    {"key": "crm", "label": "CRM", "color": "#0055FF",
     "blurb": "Push clean, qualified, enriched leads into your CRM with Aria's summary and recommended next action."},
    {"key": "communication", "label": "Communication", "color": "#E11D48",
     "blurb": "Let Aria reply, follow up, qualify, and nurture leads across WhatsApp, email, SMS, and LinkedIn."},
    {"key": "booking", "label": "Booking & Meetings", "color": "#D97706",
     "blurb": "Connect calendars and meeting tools so Aria can turn interested leads into booked calls."},
    {"key": "analytics", "label": "Analytics & Tracking", "color": "#0EA5E9",
     "blurb": "Help Aria understand what your leads viewed, clicked, downloaded, revisited, and ignored."},
    {"key": "automation", "label": "Automation Layer", "color": "#9333EA",
     "blurb": "Connect custom workflows and third-party tools using webhooks, Zapier, Make, n8n, or API."},
]

# Map live `integrations_hub.SUPPORTED_TYPES.category` → catalog category key.
# (existing hub uses `analytics`, `automation`, `lead_source`, `outreach`).
LIVE_TO_CATALOG_CAT = {
    "analytics": "analytics",
    "automation": "automation",
    "lead_source": "lead_source",
    "outreach": "outreach",
}


# Coming-soon catalog — UI-only entries the user can join the waitlist for.
# Each row: (type_id, label, category_key, use_case)
COMING_SOON = [
    # Lead Sources
    ("website_forms", "Website Forms",     "lead_source", "Auto-create leads from any website form via embed snippet."),
    ("landing_pages", "Landing Page Forms", "lead_source", "Capture campaign-specific leads from your landing pages."),
    ("meta_lead_ads", "Meta Lead Ads",      "lead_source", "Capture Facebook + Instagram lead form submissions."),
    ("linkedin_lead_gen", "LinkedIn Lead Gen", "lead_source", "Capture LinkedIn-sponsored lead-gen form submissions."),
    ("tally", "Tally", "lead_source", "Auto-create leads from Tally form submissions."),
    ("jotform", "Jotform", "lead_source", "Auto-create leads from Jotform submissions."),
    ("webinar", "Webinar / Demo Forms", "lead_source", "Capture webinar and demo request registrations."),
    # Outbound
    ("phantombuster", "PhantomBuster", "outreach", "Sync LinkedIn prospecting + automation data."),
    ("sales_navigator", "LinkedIn Sales Navigator", "outreach", "Import lead lists and account data."),
    ("smartlead",  "Smartlead", "outreach", "Track multi-inbox cold email opens, clicks, replies."),
    ("snov_io",    "Snov.io",   "outreach", "Verify and enrich contact data."),
    ("hunter_io",  "Hunter.io", "outreach", "Find and verify business emails."),
    # CRM
    ("zoho_crm",    "Zoho CRM",   "crm", "Push qualified leads, scores, and summaries to Zoho."),
    ("hubspot",     "HubSpot",    "crm", "Sync marketing + sales pipeline."),
    ("salesforce",  "Salesforce", "crm", "Enterprise sales pipeline sync."),
    ("pipedrive",   "Pipedrive",  "crm", "Sales pipeline sync."),
    ("freshsales",  "Freshsales", "crm", "SMB sales CRM sync."),
    ("airtable",    "Airtable",   "crm", "Lightweight CRM in Airtable."),
    ("google_sheets", "Google Sheets", "crm", "Beta fallback database for lean teams."),
    ("notion_db",   "Notion Database", "crm", "Save lead notes + summaries in Notion."),
    # Communication
    ("whatsapp_biz", "WhatsApp Business API", "communication", "Aria's primary follow-up channel."),
    ("gmail", "Gmail",     "communication", "Send + track email follow-ups via Gmail."),
    ("outlook", "Outlook", "communication", "Send + track email follow-ups via Outlook."),
    ("zoho_mail", "Zoho Mail", "communication", "Send + track email follow-ups via Zoho Mail."),
    ("twilio_sms", "SMS (Twilio)", "communication", "SMS follow-ups via Twilio."),
    ("msg91_sms",  "SMS (MSG91)",  "communication", "India-focused SMS via MSG91."),
    ("website_chat", "Website Chat", "communication", "Live chat widget on your site."),
    # Booking
    ("calendly", "Calendly", "booking", "Book demo calls + sync availability."),
    ("google_calendar", "Google Calendar", "booking", "Sync availability + create meetings."),
    ("outlook_calendar", "Outlook Calendar", "booking", "Sync availability for Outlook users."),
    ("cal_com", "Cal.com", "booking", "Open-source meeting scheduler."),
    ("zoom",   "Zoom",        "booking", "Auto-create Zoom meeting links."),
    ("google_meet", "Google Meet", "booking", "Auto-create Google Meet links."),
    ("ms_teams", "Microsoft Teams", "booking", "Auto-create Teams meeting links."),
    # Analytics
    ("gtm", "Google Tag Manager", "analytics", "Manage all your tags from one place."),
    ("gsc", "Google Search Console", "analytics", "Track organic search performance."),
    ("clarity", "Microsoft Clarity", "analytics", "Session replays + heatmaps."),
    ("hotjar", "Hotjar", "analytics", "Behaviour analytics + recordings."),
    ("posthog", "PostHog", "analytics", "Product analytics."),
    ("mixpanel", "Mixpanel", "analytics", "Event analytics."),
    ("meta_pixel", "Meta Pixel", "analytics", "Client-side conversion tracking (server-side via Meta CAPI already live)."),
    ("linkedin_insight", "LinkedIn Insight Tag", "analytics", "Track LinkedIn campaign visitors."),
    # Automation
    ("n8n", "n8n", "automation", "Self-hosted automation workflows."),
    ("webhooks_custom", "Custom Webhooks", "automation", "Receive/send custom data to any endpoint."),
    ("custom_api", "Custom API", "automation", "Enterprise client-specific integrations."),
]


def _live_catalog_for_tenant(tenant_id: str) -> list[dict]:
    """Read the live integration_configs for the tenant and return enriched rows."""
    docs = {d["integration_type"]: d for d in configs_col.find({"tenant_id": tenant_id}, {"_id": 0})}
    out = []
    for t, meta in LIVE_TYPES.items():
        d = docs.get(t, {})
        out.append({
            "type": t,
            "label": meta["label"],
            "category": LIVE_TO_CATALOG_CAT.get(meta["category"], meta["category"]),
            "status": d.get("status") or ("connected" if d else "not_connected"),
            "live": True,
            "direction": meta["direction"],
            "last_sync_at": d.get("last_sync_at"),
            "error_message": d.get("error_message"),
            "use_case": _live_use_case(t),
        })
    return out


def _live_use_case(t: str) -> str:
    return {
        "ga4": "Fire server-side events for every Aria lifecycle change.",
        "meta_capi": "Server-side Pixel events (Lead, Schedule, CompleteRegistration).",
        "zapier": "Pipe every Aria event to any Zapier zap.",
        "make": "Pipe every Aria event into any Make scenario.",
        "typeform": "Auto-create leads from Typeform submissions.",
        "instantly": "Capture every Instantly.ai reply as a lead.",
        "google_ads": "Webhook from Google Ads Lead Form → leads in Aria.",
        "apollo": "Bulk import from Apollo + start touchpoints.",
        "saleshandy": "Sync opens/clicks/replies + auto-pause hot leads.",
        "lemlist": "Capture replies + LinkedIn accepts + auto-pause campaigns.",
    }.get(t, "")


def _waitlist_count(tenant_id: str, t: str) -> int:
    return waitlist_col.count_documents({"tenant_id": tenant_id, "integration_type": t})


# ─── Catalog endpoint ────────────────────────────────────────────────────────
@router.get("/catalog")
async def get_catalog(tenant: dict = Depends(get_active_tenant)):
    """Full marketplace catalog: live integrations + coming-soon, grouped by category.

    Frontend uses this as the single source-of-truth for the Integration Hub page.
    """
    live = _live_catalog_for_tenant(tenant["id"])
    # Mark waitlist-joined entries per coming-soon row
    joined_types = {w["integration_type"] for w in waitlist_col.find(
        {"tenant_id": tenant["id"]}, {"_id": 0, "integration_type": 1})}
    coming = [{
        "type": t,
        "label": label,
        "category": cat,
        "status": "waitlist_joined" if t in joined_types else "coming_soon",
        "live": False,
        "use_case": use,
    } for t, label, cat, use in COMING_SOON]

    all_rows = live + coming
    by_cat: dict[str, list[dict]] = {c["key"]: [] for c in CATEGORIES}
    for row in all_rows:
        by_cat.setdefault(row["category"], []).append(row)
    return {
        "categories": CATEGORIES,
        "integrations": all_rows,
        "by_category": by_cat,
    }


# ─── Setup progress + recommended path ──────────────────────────────────────
@router.get("/setup-progress")
async def setup_progress(tenant: dict = Depends(get_active_tenant)):
    """Compute the "Your Aria Sales System Setup: X% Complete" progress bar.

    Each step counts as 1 if ANY integration in its category is connected.
    """
    connected = {d["integration_type"]: d for d in configs_col.find(
        {"tenant_id": tenant["id"], "status": "connected"}, {"_id": 0, "integration_type": 1})}
    connected_cats = set()
    for t in connected:
        cat = LIVE_TO_CATALOG_CAT.get((LIVE_TYPES.get(t, {}).get("category") or ""), "")
        if cat:
            connected_cats.add(cat)

    steps = [
        {"key": "lead_source",  "label": "Capture Leads",     "category": "lead_source"},
        {"key": "analytics",    "label": "Track Source",      "category": "analytics"},
        {"key": "communication", "label": "Follow Up",         "category": "communication"},
        {"key": "outreach",     "label": "Score Intent",      "category": "outreach"},
        {"key": "crm",          "label": "Sync CRM",          "category": "crm"},
        {"key": "booking",      "label": "Book Calls",        "category": "booking"},
        {"key": "automation",   "label": "Alert Founder",     "category": "automation"},
    ]
    for s in steps:
        s["complete"] = s["category"] in connected_cats

    done = sum(1 for s in steps if s["complete"])
    percent = round(100 * done / len(steps)) if steps else 0
    return {"percent": percent, "completed": done, "total": len(steps), "steps": steps}


# ─── Integration Health rollup ──────────────────────────────────────────────
@router.get("/health")
async def integration_health(tenant: dict = Depends(get_active_tenant)):
    """Row-per-connected-integration health rollup for the Health table."""
    rows = list(configs_col.find({"tenant_id": tenant["id"]}, {"_id": 0}))
    out = []
    for r in rows:
        meta = LIVE_TYPES.get(r["integration_type"], {})
        out.append({
            "type": r["integration_type"],
            "label": meta.get("label") or r["integration_type"],
            "status": r.get("status", "unknown"),
            "last_sync_at": r.get("last_sync_at"),
            "error_message": r.get("error_message"),
        })
    healthy = sum(1 for r in out if r["status"] == "connected" and not r["error_message"])
    total = len(out)
    pct = round(100 * healthy / total) if total else 100
    return {"healthy_percent": pct, "healthy": healthy, "total": total, "rows": out}


# ─── Data Flow preview ──────────────────────────────────────────────────────
@router.get("/data-flow")
async def data_flow(tenant: dict = Depends(get_active_tenant)):
    """Return the dynamic data-flow preview nodes based on what's actually connected."""
    types = {d["integration_type"] for d in configs_col.find(
        {"tenant_id": tenant["id"], "status": "connected"}, {"_id": 0, "integration_type": 1})}

    # Heuristic — pick the most relevant connector in each step
    capture = None
    for prefer in ("meta_capi", "google_ads", "typeform", "apollo", "instantly", "saleshandy", "lemlist"):
        if prefer in types:
            capture = LIVE_TYPES[prefer]["label"]
            break

    followup = "WhatsApp Business API" if "whatsapp_biz" in types else "Email + WhatsApp"
    crm = None
    for prefer in ("zoho_crm", "hubspot", "google_sheets"):
        if prefer in types:
            crm = prefer.replace("_", " ").title()
            break
    booking = "Calendly" if "calendly" in types else "Google Calendar"
    automation = None
    for prefer in ("zapier", "make"):
        if prefer in types:
            automation = LIVE_TYPES[prefer]["label"]
            break

    nodes = [
        {"key": "capture", "title": "Lead Captured",
         "subtitle": capture or "Connect a lead source to populate this."},
        {"key": "signal",  "title": "Aria reads signal",
         "subtitle": "Campaign · UTM · form answers · website behaviour"},
        {"key": "score",   "title": "Aria scores intent",
         "subtitle": "Hot · Warm · Cold · Poor fit"},
        {"key": "followup", "title": "Aria follows up",
         "subtitle": followup},
        {"key": "crm",     "title": "CRM sync",
         "subtitle": crm or "Connect a CRM (or Google Sheets fallback)."},
        {"key": "booking", "title": "Demo booked",
         "subtitle": booking + " — Aria pauses nurture automatically"},
        {"key": "alert",   "title": "Founder alert",
         "subtitle": automation or "Connect Zapier / Make / Slack webhook for instant pings"},
    ]
    return {"nodes": nodes}


# ─── Waitlist + custom request ──────────────────────────────────────────────
class WaitlistJoin(BaseModel):
    note: Optional[str] = Field(default=None, max_length=400)


@router.post("/waitlist/{integration_type}")
async def join_waitlist(
    integration_type: str,
    payload: WaitlistJoin,
    tenant: dict = Depends(get_active_tenant),
    current_user: dict = Depends(get_current_user),
):
    if not any(t == integration_type for t, *_ in COMING_SOON):
        raise HTTPException(status_code=404, detail="Not a coming-soon integration")
    # Idempotent — one row per (tenant, integration, user)
    waitlist_col.update_one(
        {"tenant_id": tenant["id"], "integration_type": integration_type, "user_email": current_user.get("email")},
        {"$set": {
            "tenant_id": tenant["id"],
            "integration_type": integration_type,
            "user_email": current_user.get("email"),
            "note": (payload.note or "").strip(),
            "joined_at": _now(),
        }},
        upsert=True,
    )
    return {"ok": True, "waitlist_count": _waitlist_count(tenant["id"], integration_type)}


class CustomRequestPayload(BaseModel):
    tool_name: str = Field(min_length=2, max_length=120)
    website_url: Optional[str] = Field(default=None, max_length=400)
    use_case: str = Field(min_length=10, max_length=2000)
    data_to_pull: Optional[str] = Field(default=None, max_length=600)
    data_to_push: Optional[str] = Field(default=None, max_length=600)
    priority: Optional[str] = Field(default="nice_to_have")  # blocker | nice_to_have


@router.post("/custom-request")
async def custom_request(
    payload: CustomRequestPayload,
    tenant: dict = Depends(get_active_tenant),
    current_user: dict = Depends(get_current_user),
):
    rid = f"req_{uuid.uuid4().hex[:12]}"
    row = {
        "id": rid,
        "tenant_id": tenant["id"],
        "user_email": current_user.get("email"),
        "tool_name": payload.tool_name.strip(),
        "website_url": (payload.website_url or "").strip(),
        "use_case": payload.use_case.strip(),
        "data_to_pull": (payload.data_to_pull or "").strip(),
        "data_to_push": (payload.data_to_push or "").strip(),
        "priority": payload.priority or "nice_to_have",
        "status": "open",
        "created_at": _now(),
    }
    requests_col.insert_one(row)
    return {"ok": True, "id": rid, "request": {k: v for k, v in row.items() if k != "_id"}}


@router.get("/custom-requests")
async def list_custom_requests(tenant: dict = Depends(get_active_tenant)):
    rows = list(requests_col.find({"tenant_id": tenant["id"]}, {"_id": 0}).sort("created_at", -1).limit(50))
    return {"requests": rows}


# ─── Send Test Lead ────────────────────────────────────────────────────────
class TestLeadPayload(BaseModel):
    first_name: str = "Test"
    last_name: str = "Lead"
    email: str = "test@aria.local"
    phone: str = "+919999999999"
    source_channel: str = "test_mode"


@router.post("/test-lead")
async def send_test_lead(
    payload: TestLeadPayload,
    tenant: dict = Depends(get_active_tenant),
):
    """Fire a CLEARLY-LABELED test lead through every connected outbound integration.

    Crucially the lead is NOT inserted into the leads collection — it's purely
    a fan-out to the configured webhooks so the user can see their pipeline light up.
    """
    test_lead = {
        "id": f"test_{uuid.uuid4().hex[:8]}",
        "first_name": payload.first_name,
        "last_name": payload.last_name,
        "email": payload.email,
        "phone": payload.phone,
        "tenant_id": tenant["id"],
        "source_channel": payload.source_channel,
        "is_test": True,
        "test_label": "ARIA TEST LEAD — do not action",
    }
    # Walk connected outbound integrations
    outbound_types = [t for t, m in LIVE_TYPES.items() if m["direction"] == "outbound"]
    results = []
    for t in outbound_types:
        cfg = configs_col.find_one(
            {"tenant_id": tenant["id"], "integration_type": t, "status": "connected"}, {"_id": 0})
        if not cfg:
            continue
        ok, msg = await _dispatch(tenant["id"], t, cfg.get("config", {}), "lead.created",
                                  test_lead, {"test": True})
        results.append({"type": t, "label": LIVE_TYPES[t]["label"], "ok": ok, "message": msg})
    return {"fired": len(results), "results": results, "test_lead_id": test_lead["id"]}
