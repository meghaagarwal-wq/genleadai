"""Pietential × ARIA — Lemlist → Intel → Insight → Delivery pipeline.

Scope: Pietential tenant ONLY (`ten_pietential`). Additive — does not modify
any existing flow.

Implements PARTS 1-9 of the spec:
  Part 1 — lemlist_poll_loop (every 30min)
  Part 2 — Intent classification (Claude Haiku, QUALIFICATION)
  Part 3 — ICP scoring against 5 Pietential ICPs (Claude Haiku, ICP_SCORING)
  Part 4 — Enrichment gate + RapidAPI + Serper fan-out
  Part 5 — Workforce signal classification (Claude Sonnet, SIGNAL_CLASSIFICATION)
  Part 6 — Insight card generation (Claude Sonnet, INSIGHT_GENERATION)
  Part 7 — Lead score + account tier + founder_flag
  Part 8 — pietential_insight_scan loop (07:30 IST daily)
  Part 9 — Weekly Intelligence Report (Mon 08:00 IST) + WhatsApp founder alert
  Part 10 — /api/pietential/pipeline-health endpoint (dashboard card)
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import resend
from fastapi import APIRouter, Depends, HTTPException

from deps import db, get_current_user
from services.claude_service import claude_call, TaskType, ClaudeServiceError

logger = logging.getLogger("pietential_intel")
router = APIRouter(prefix="/api/pietential", tags=["pietential"])

# ─────────────────────────── constants ───────────────────────────
PT_TENANT_ID = "ten_pietential"
SLUG = "pietential"

_leads = db["pt_leads"]
_insights = db["pt_insights"]
_prospect_intel = db["prospect_intel"]
_audit = db["audit_log"]
_api_usage = db["api_usage_log"]
_icps = db["icps"]
_configs = db["integration_configs"]
_notif_prefs = db["notification_preferences"]

_leads.create_index([("tenant_id", 1), ("email", 1)])
_leads.create_index([("tenant_id", 1), ("source", 1), ("updated_at", -1)])
_insights.create_index([("tenant_id", 1), ("week_of", 1)])
_insights.create_index([("tenant_id", 1), ("founder_flag", 1), ("created_at", -1)])

ICP_SEED: List[Dict[str, Any]] = [
    {
        "id": "icp_a",
        "name": "Enterprise C-Suite",
        "titles": ["CEO", "COO", "Managing Director", "President", "Group CEO"],
        "company_size_min": 1000, "company_size_max": 10000,
        "industries": [],
        "weight": 35,
    },
    {
        "id": "icp_b",
        "name": "CHRO / CPO — Enterprise",
        "titles": ["CHRO", "Chief People Officer", "Chief HR Officer",
                   "Head of People", "VP HR", "VP People"],
        "company_size_min": 1000, "company_size_max": 10000,
        "industries": [],
        "weight": 35,
    },
    {
        "id": "icp_c",
        "name": "CFO — Mid-Market SaaS",
        "titles": ["CFO", "Chief Financial Officer", "VP Finance", "Head of Finance"],
        "company_size_min": 500, "company_size_max": 5000,
        "industries": ["SaaS", "Technology", "Software"],
        "weight": 28,
    },
    {
        "id": "icp_d",
        "name": "People Analytics / OD Leader",
        "titles": ["Head of People Analytics", "People Analytics Lead",
                   "OD Lead", "Organisational Development"],
        "company_size_min": 1000, "company_size_max": 10000,
        "industries": [],
        "weight": 25,
    },
    {
        "id": "icp_e",
        "name": "VP People / Head of HR — Growth-Stage",
        "titles": ["VP People", "Head of HR", "People Lead", "Talent Lead", "HR Director"],
        "company_size_min": 200, "company_size_max": 2000,
        "industries": [],
        "weight": 20,
    },
    {"id": "icp_unknown",  "name": "Insufficient data to classify",       "titles": [], "weight": 10},
    {"id": "icp_not_fit",  "name": "Wrong role / wrong company type",     "titles": [], "weight": 0},
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seed_icps_once() -> int:
    """Seed Pietential ICPs into the icps collection. Idempotent."""
    inserted = 0
    for icp in ICP_SEED:
        doc = {**icp, "tenant_id": PT_TENANT_ID, "updated_at": _now_iso()}
        res = _icps.update_one(
            {"tenant_id": PT_TENANT_ID, "id": icp["id"]},
            {"$set": doc, "$setOnInsert": {"created_at": _now_iso()}},
            upsert=True,
        )
        if res.upserted_id:
            inserted += 1
    return inserted


_seed_icps_once()


# ─────────────────────── secret helpers ───────────────────────

def _get_provider_key(provider: str) -> Optional[str]:
    """Fetch a decrypted secret for the Pietential tenant + provider."""
    try:
        from routes.integrations_hub import _decrypt_config_secrets
    except ImportError:
        return None
    doc = _configs.find_one({"tenant_id": PT_TENANT_ID, "integration_type": provider}, {"_id": 0})
    if not doc:
        return None
    cfg = _decrypt_config_secrets(doc.get("config") or {})
    return cfg.get("api_key") or cfg.get("key") or cfg.get("token")


def _ensure_lemlist_config() -> Optional[Dict[str, Any]]:
    """Verify lemlist integration_configs exists. If missing, create placeholder."""
    doc = _configs.find_one({"tenant_id": PT_TENANT_ID, "integration_type": "lemlist"}, {"_id": 0})
    if doc:
        return doc
    # Create placeholder so the integrations UI shows it as needs-config.
    placeholder = {
        "tenant_id": PT_TENANT_ID,
        "integration_type": "lemlist",
        "status": "pending",
        "config": {},
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "note": "API key required. Add via Integrations page.",
    }
    _configs.insert_one(dict(placeholder))
    return placeholder


_ensure_lemlist_config()


def _bump_api_usage(provider: str, n: int = 1) -> None:
    today = datetime.now(timezone.utc).date().isoformat()
    _api_usage.update_one(
        {"tenant_id": PT_TENANT_ID, "date": today},
        {"$inc": {f"{provider}_calls": n}, "$set": {"updated_at": _now_iso()}},
        upsert=True,
    )


def _audit_event(event: str, **extra) -> None:
    doc = {"event": event, "tenant_id": PT_TENANT_ID, "created_at": _now_iso(), **extra}
    _audit.insert_one(dict(doc))


# ─────────────────────── Lemlist API client ───────────────────────

_LEMLIST_BASE = "https://api.lemlist.com/api"


def _lemlist_request(path: str, api_key: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """Synchronous Lemlist GET. We run it under asyncio.to_thread so the event
    loop stays unblocked."""
    qs = ("?" + urllib.parse.urlencode(params)) if params else ""
    url = f"{_LEMLIST_BASE}{path}{qs}"
    req = urllib.request.Request(url)
    # Lemlist uses HTTP Basic auth with empty username and api_key as password.
    import base64
    auth = base64.b64encode(f":{api_key}".encode("utf-8")).decode("ascii")
    req.add_header("Authorization", f"Basic {auth}")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8") or "null")
    except Exception as e:  # noqa: BLE001
        logger.warning("lemlist GET %s failed: %s", path, str(e)[:200])
        return None


async def _lem_list_campaigns(api_key: str) -> List[Dict[str, Any]]:
    data = await asyncio.to_thread(_lemlist_request, "/campaigns", api_key)
    return data if isinstance(data, list) else []


async def _lem_list_campaign_leads(api_key: str, campaign_id: str) -> List[Dict[str, Any]]:
    data = await asyncio.to_thread(_lemlist_request, f"/campaigns/{campaign_id}/leads", api_key)
    return data if isinstance(data, list) else []


async def _lem_list_lead_activities(api_key: str, lead_email: str) -> List[Dict[str, Any]]:
    safe = urllib.parse.quote(lead_email)
    data = await asyncio.to_thread(_lemlist_request, f"/leads/{safe}/activities", api_key)
    return data if isinstance(data, list) else []


# ─────────────────────── Lemlist poll loop ───────────────────────

async def lemlist_poll_once() -> Dict[str, Any]:
    """One pass — pull all campaigns + leads for Pietential. Idempotent dedupe."""
    api_key = _get_provider_key("lemlist")
    if not api_key:
        logger.info("lemlist_poll skip — no api key configured")
        return {"skipped": True, "reason": "no_api_key"}

    new_count = 0
    updated_count = 0
    total = 0

    try:
        campaigns = await _lem_list_campaigns(api_key)
    except Exception as e:  # noqa: BLE001
        logger.exception("lemlist campaigns fetch failed")
        return {"error": str(e)[:200]}

    for camp in campaigns:
        camp_id = camp.get("_id") or camp.get("id")
        camp_name = camp.get("name") or ""
        if not camp_id:
            continue
        leads_data = await _lem_list_campaign_leads(api_key, camp_id)
        for ld in leads_data:
            email = (ld.get("email") or "").lower().strip()
            if not email:
                continue
            total += 1
            # Pull activities for engagement counters.
            try:
                acts = await _lem_list_lead_activities(api_key, email)
            except Exception:  # noqa: BLE001
                acts = []
            opens = sum(1 for a in acts if a.get("type") in ("emailsOpened", "emailOpened"))
            clicks = sum(1 for a in acts if a.get("type") in ("emailsClicked", "emailClicked"))
            replied = any(a.get("type") in ("emailsReplied", "emailReplied") for a in acts)
            reply_content = next(
                (a.get("extra", {}).get("content") or a.get("content") or ""
                 for a in acts if a.get("type") in ("emailsReplied", "emailReplied")), "")
            bounced = any(a.get("type") in ("emailsBounced", "emailBounced") for a in acts)
            unsubscribed = any(a.get("type") in ("unsubscribed",) for a in acts)
            last_activity_at = max((a.get("createdAt") or "" for a in acts), default=None)

            lemlist_data = {
                "campaign_id": camp_id,
                "campaign_name": camp_name,
                "sequence_step": ld.get("step") or ld.get("currentSequenceStep") or 0,
                "emails_sent": sum(1 for a in acts if a.get("type") in ("emailsSent", "emailSent")),
                "emails_opened": opens,
                "open_count": opens,
                "links_clicked": clicks,
                "clicked_urls": [a.get("extra", {}).get("url") for a in acts
                                 if a.get("type") in ("emailsClicked", "emailClicked")
                                 and a.get("extra", {}).get("url")],
                "replied": replied,
                "reply_content": (reply_content or "")[:4000],
                "bounced": bounced,
                "unsubscribed": unsubscribed,
                "last_activity_at": last_activity_at,
                "is_active_in_sequence": not (bounced or unsubscribed),
                "completed_sequence": bool(ld.get("isFinished")),
            }

            existing = _leads.find_one({"tenant_id": PT_TENANT_ID, "email": email}, {"_id": 0, "id": 1, "insights_enabled": 1})
            now_iso = _now_iso()
            if existing:
                _leads.update_one(
                    {"tenant_id": PT_TENANT_ID, "email": email},
                    {"$set": {
                        "lemlist_data": lemlist_data,
                        "last_lemlist_activity": last_activity_at,
                        "updated_at": now_iso,
                        "source_campaign": camp_name,
                    }},
                )
                updated_count += 1
                lead_doc_id = existing["id"]
            else:
                new_id = f"lead_{uuid.uuid4().hex[:14]}"
                doc = {
                    "id": new_id,
                    "tenant_id": PT_TENANT_ID,
                    "email": email,
                    "first_name": ld.get("firstName") or "",
                    "last_name": ld.get("lastName") or "",
                    "company_name": ld.get("companyName") or "",
                    "job_title": ld.get("jobTitle") or "",
                    "linkedin_url": ld.get("linkedinUrl") or ld.get("linkedin_url") or "",
                    "source": "lemlist",
                    "source_campaign": camp_name,
                    "lemlist_data": lemlist_data,
                    "last_lemlist_activity": last_activity_at,
                    "insights_enabled": True,
                    "created_at": now_iso,
                    "updated_at": now_iso,
                }
                _leads.insert_one(dict(doc))
                new_count += 1
                lead_doc_id = new_id

            # Inline intent classification (Part 2).
            try:
                await classify_intent_for_lead(lead_doc_id)
            except Exception:  # noqa: BLE001
                logger.exception("intent classify failed for %s", email)
            # Inline ICP scoring (Part 3).
            try:
                await score_icp_for_lead(lead_doc_id)
            except Exception:  # noqa: BLE001
                logger.exception("icp score failed for %s", email)
            # Recompute lead score (Part 7).
            try:
                _recompute_lead_score(lead_doc_id)
            except Exception:  # noqa: BLE001
                logger.exception("lead score failed for %s", email)

    _audit_event("lemlist_poll", leads_pulled=total, new_leads=new_count, updated_leads=updated_count)
    return {"leads_pulled": total, "new_leads": new_count, "updated_leads": updated_count}


async def lemlist_poll_loop() -> None:
    """30-minute cadence. Safe to start multiple times — single-tenant scope."""
    while True:
        try:
            await lemlist_poll_once()
        except Exception:  # noqa: BLE001
            logger.exception("lemlist_poll_loop iteration error")
        await asyncio.sleep(30 * 60)


# ─────────────────────── Part 2 — Intent classification ───────────────────────

async def classify_intent_for_lead(lead_id: str) -> Optional[Dict[str, Any]]:
    lead = _leads.find_one({"tenant_id": PT_TENANT_ID, "id": lead_id}, {"_id": 0})
    if not lead:
        return None
    ld = lead.get("lemlist_data") or {}
    prompt = (
        "You are an intent classification agent for a B2B sales team.\n"
        "Classify this lead's intent based ONLY on their Lemlist campaign behaviour.\n\n"
        f"Campaign: {lead.get('source_campaign')}\n"
        f"Sequence step reached: {ld.get('sequence_step')}\n"
        f"Emails sent: {ld.get('emails_sent')}\n"
        f"Times opened: {ld.get('open_count')}\n"
        f"Links clicked: {ld.get('links_clicked')}\n"
        f"Replied: {ld.get('replied')}\n"
        f"Reply content: {(ld.get('reply_content') or '')[:600]}\n"
        f"Bounced: {ld.get('bounced')}\n"
        f"Unsubscribed: {ld.get('unsubscribed')}\n"
        f"Last activity: {ld.get('last_activity_at')}\n\n"
        "Return JSON only with keys: intent, intent_reason, reply_sentiment, "
        "reply_summary, recommended_urgency. Allowed intent values: "
        "HIGH_INTENT, MEDIUM_INTENT, LOW_INTENT, DISQUALIFIED. Allowed "
        "reply_sentiment: POSITIVE, NEGATIVE, NEUTRAL, OBJECTION, QUESTION, "
        "OUT_OF_OFFICE, null. Allowed urgency: immediate, this_week, "
        "this_month, deprioritise."
    )
    try:
        data = await claude_call(
            task_type=TaskType.QUALIFICATION,
            system="You classify B2B lead intent. JSON only, no preamble.",
            prompt=prompt,
            tenant_id=PT_TENANT_ID,
            session_id=f"intent-{lead_id}",
            response_format="json",
        )
    except ClaudeServiceError as e:
        logger.warning("intent classify claude failed: %s", str(e)[:200])
        return None

    _leads.update_one(
        {"tenant_id": PT_TENANT_ID, "id": lead_id},
        {"$set": {
            "lemlist_intent": data.get("intent"),
            "intent_reason": data.get("intent_reason"),
            "reply_sentiment": data.get("reply_sentiment"),
            "reply_summary": data.get("reply_summary"),
            "recommended_urgency": data.get("recommended_urgency"),
            "intent_classified_at": _now_iso(),
        }},
    )
    return data


# ─────────────────────── Part 3 — ICP scoring ───────────────────────

async def score_icp_for_lead(lead_id: str) -> Optional[Dict[str, Any]]:
    lead = _leads.find_one({"tenant_id": PT_TENANT_ID, "id": lead_id}, {"_id": 0})
    if not lead:
        return None
    icp_defs = list(_icps.find({"tenant_id": PT_TENANT_ID}, {"_id": 0}))
    prompt = (
        "You are an ICP scoring agent for Pietential — a B2B company that improves "
        "employee wellbeing, engagement, and organisational health for enterprise "
        "companies with 1,000–10,000 employees.\n\n"
        f"Lead:\nName: {lead.get('first_name')} {lead.get('last_name')}\n"
        f"Job title: {lead.get('job_title')}\nCompany: {lead.get('company_name')}\n"
        f"Estimated company size: {lead.get('company_size') or 'unknown'}\n"
        f"Industry: {lead.get('industry') or 'unknown'}\n"
        f"Lemlist intent: {lead.get('lemlist_intent') or 'unknown'}\n\n"
        f"ICP definitions:\n{json.dumps(icp_defs, default=str)[:3500]}\n\n"
        "Return JSON only with keys: matched_icp_id, matched_icp_name, icp_score "
        "(0-100), match_reason (one sentence), buying_authority "
        "(decision_maker|influencer|user|unknown)."
    )
    try:
        data = await claude_call(
            task_type=TaskType.ICP_SCORING,
            system="You score B2B leads against ICPs. JSON only.",
            prompt=prompt,
            tenant_id=PT_TENANT_ID,
            session_id=f"icp-{lead_id}",
            response_format="json",
        )
    except ClaudeServiceError as e:
        logger.warning("icp claude failed: %s", str(e)[:200])
        return None

    _leads.update_one(
        {"tenant_id": PT_TENANT_ID, "id": lead_id},
        {"$set": {
            "icp_segment": data.get("matched_icp_id"),
            "icp_segment_name": data.get("matched_icp_name"),
            "icp_score": int(data.get("icp_score") or 0),
            "icp_match_reason": data.get("match_reason"),
            "buying_authority": data.get("buying_authority") or "unknown",
            "icp_classified_at": _now_iso(),
        }},
    )
    return data


# ─────────────────────── Part 4 — Enrichment ───────────────────────

def _enrichment_gate(lead: Dict[str, Any]) -> Tuple[bool, str]:
    intent = lead.get("lemlist_intent")
    icp = lead.get("icp_segment")
    if intent == "HIGH_INTENT":
        return True, "high_intent"
    if intent == "MEDIUM_INTENT" and icp in ("icp_a", "icp_b"):
        return True, "medium_intent_high_icp"
    return False, "below_threshold"


async def _rapidapi_linkedin(linkedin_url: str, api_key: str) -> Optional[Dict[str, Any]]:
    if not linkedin_url or not api_key:
        return None
    qs = urllib.parse.urlencode({"url": linkedin_url})
    url = f"https://linkedin-data-api.p.rapidapi.com/get-profile-data-by-url?{qs}"
    req = urllib.request.Request(url)
    req.add_header("X-RapidAPI-Key", api_key)
    req.add_header("X-RapidAPI-Host", "linkedin-data-api.p.rapidapi.com")
    def _do():
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8") or "null")
    try:
        return await asyncio.to_thread(_do)
    except Exception as e:  # noqa: BLE001
        logger.warning("rapidapi linkedin failed: %s", str(e)[:200])
        return None


async def _serper_search(query: str, api_key: str) -> List[Dict[str, Any]]:
    if not query or not api_key:
        return []
    data = json.dumps({"q": query, "num": 8}).encode("utf-8")
    req = urllib.request.Request("https://google.serper.dev/news", data=data)
    req.add_header("X-API-KEY", api_key)
    req.add_header("Content-Type", "application/json")
    def _do():
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8") or "null")
    try:
        resp = await asyncio.to_thread(_do)
        return (resp or {}).get("news") or (resp or {}).get("organic") or []
    except Exception as e:  # noqa: BLE001
        logger.warning("serper failed: %s", str(e)[:200])
        return []


async def enrich_lead(lead_id: str) -> Optional[Dict[str, Any]]:
    lead = _leads.find_one({"tenant_id": PT_TENANT_ID, "id": lead_id}, {"_id": 0})
    if not lead:
        return None
    ok, reason = _enrichment_gate(lead)
    if not ok:
        _leads.update_one(
            {"tenant_id": PT_TENANT_ID, "id": lead_id},
            {"$set": {"enrichment_status": "not_required", "enrichment_reason": reason, "enriched_at": _now_iso()}},
        )
        return {"skipped": True, "reason": reason}

    rapid_key = _get_provider_key("rapidapi") or _get_provider_key("proxycurl")
    serper_key = _get_provider_key("serper")
    raw_sources = {}

    # RapidAPI LinkedIn (1 call)
    linkedin_data = None
    if lead.get("linkedin_url") and rapid_key:
        linkedin_data = await _rapidapi_linkedin(lead["linkedin_url"], rapid_key)
        if linkedin_data is not None:
            _bump_api_usage("rapidapi", 1)
            if isinstance(linkedin_data, dict):
                _leads.update_one(
                    {"tenant_id": PT_TENANT_ID, "id": lead_id},
                    {"$set": {
                        "job_title": lead.get("job_title") or linkedin_data.get("headline") or linkedin_data.get("position") or "",
                        "company_size": linkedin_data.get("companySize") or lead.get("company_size"),
                        "industry": linkedin_data.get("industry") or lead.get("industry"),
                        "linkedin_url": lead.get("linkedin_url") or linkedin_data.get("url"),
                    }},
                )

    # Serper queries (2 calls)
    serper_company: List[Dict[str, Any]] = []
    serper_person: List[Dict[str, Any]] = []
    if serper_key:
        company = lead.get("company_name") or ""
        if company:
            q_company = f'"{company}" (hiring OR layoffs OR restructuring OR CHRO OR "people strategy" OR "employee wellbeing" OR workforce OR headcount OR culture OR HR)'
            serper_company = await _serper_search(q_company, serper_key)
            _bump_api_usage("serper", 1)
        if lead.get("first_name") and lead.get("last_name") and company:
            q_person = f'"{lead["first_name"]} {lead["last_name"]}" "{company}" (appointed OR joined OR promoted OR leading OR wellbeing OR HR OR people OR culture OR leadership)'
            serper_person = await _serper_search(q_person, serper_key)
            _bump_api_usage("serper", 1)

    raw_sources = {
        "linkedin_data": linkedin_data,
        "serper_company": serper_company,
        "serper_person": serper_person,
    }
    _prospect_intel.update_one(
        {"tenant_id": PT_TENANT_ID, "lead_id": lead_id},
        {"$set": {
            "tenant_id": PT_TENANT_ID,
            "lead_id": lead_id,
            "raw_sources": raw_sources,
            "scanned_at": _now_iso(),
            "enrichment_source": "rapidapi+serper" if linkedin_data else "serper_only",
        }},
        upsert=True,
    )
    _leads.update_one(
        {"tenant_id": PT_TENANT_ID, "id": lead_id},
        {"$set": {"enrichment_status": "done", "enriched_at": _now_iso()}},
    )
    return {"enriched": True, "raw_sources_summary": {k: len(v) if isinstance(v, list) else bool(v) for k, v in raw_sources.items()}}


# ─────────────────────── Part 5 — Signal classification ───────────────────────

async def classify_signal_for_lead(lead_id: str) -> Optional[Dict[str, Any]]:
    intel = _prospect_intel.find_one({"tenant_id": PT_TENANT_ID, "lead_id": lead_id}, {"_id": 0})
    if not intel or not intel.get("raw_sources"):
        return None
    lead = _leads.find_one({"tenant_id": PT_TENANT_ID, "id": lead_id}, {"_id": 0}) or {}
    raw = intel["raw_sources"]
    # Compact the search results to keep prompt token-tight.
    compact = []
    for src in ("serper_company", "serper_person"):
        for item in (raw.get(src) or [])[:6]:
            compact.append({
                "title": item.get("title") or "",
                "snippet": item.get("snippet") or item.get("description") or "",
                "link": item.get("link") or item.get("url") or "",
                "date": item.get("date") or "",
                "source_query": src,
            })

    prompt = (
        "You are an intelligence analyst for Pietential — a company that helps "
        "enterprise organisations (1,000–10,000 employees) improve employee "
        "wellbeing, engagement, leadership effectiveness, and workforce health.\n\n"
        "Read the raw search data and identify ONLY signals directly relevant to "
        "Pietential's use case (hiring surge, layoffs, new CHRO/CPO/HR leader, "
        "funding triggering hiring, wellbeing/burnout/retention, culture/DEI/engagement, "
        "OD/workforce transformation, HR tech stack, expansion, leadership change).\n\n"
        "Ignore: product launches unrelated to people, revenue milestones, awards "
        "unrelated to HR, marketing campaigns, generic news.\n\n"
        f"Raw search data:\n{json.dumps(compact)[:5000]}\n\n"
        f"Company: {lead.get('company_name')}\n"
        f"Prospect: {lead.get('first_name')} {lead.get('last_name')}, {lead.get('job_title')}\n\n"
        "Return JSON only. NEVER fabricate. Confidence below 0.70 → signal_found:false.\n"
        '{"signal_found": true|false, "signal_type": "hiring_surge|layoffs|'
        'new_people_leader|funding|wellbeing|culture|org_transformation|hr_tech|'
        'leadership_change|expansion|null", "signal_summary": "...", "signal_date": '
        '"approx date or null", "why_relevant_for_pietential": "one sentence", '
        '"confidence": 0.0-1.0, "source_url": "url or null"}'
    )
    try:
        data = await claude_call(
            task_type=TaskType.SIGNAL_CLASSIFICATION,
            system="You classify workforce-relevance signals from search results. JSON only.",
            prompt=prompt,
            tenant_id=PT_TENANT_ID,
            session_id=f"signal-{lead_id}",
            response_format="json",
        )
    except ClaudeServiceError as e:
        logger.warning("signal classify failed: %s", str(e)[:200])
        return None

    conf = float(data.get("confidence") or 0)
    payload = {
        "signal_found": bool(data.get("signal_found")) and conf >= 0.70,
        "signal_type": data.get("signal_type"),
        "signal_summary": data.get("signal_summary"),
        "signal_date": data.get("signal_date"),
        "why_relevant_for_pietential": data.get("why_relevant_for_pietential"),
        "confidence": conf,
        "source_url": data.get("source_url"),
        "signal_classified_at": _now_iso(),
    }
    _prospect_intel.update_one(
        {"tenant_id": PT_TENANT_ID, "lead_id": lead_id},
        {"$set": payload},
    )
    return payload


# ─────────────────────── Part 6 — Insight card ───────────────────────

def _signal_dedup_hash(lead_id: str, signal_type: str, summary: str) -> str:
    raw = f"{lead_id}|{signal_type}|{summary[:120]}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _iso_week(dt: Optional[datetime] = None) -> str:
    dt = dt or datetime.now(timezone.utc)
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w:02d}"


async def generate_insight_card_for_lead(lead_id: str) -> Optional[Dict[str, Any]]:
    intel = _prospect_intel.find_one({"tenant_id": PT_TENANT_ID, "lead_id": lead_id}, {"_id": 0})
    if not intel or not intel.get("signal_found"):
        return None
    if (intel.get("confidence") or 0) < 0.70:
        return None
    lead = _leads.find_one({"tenant_id": PT_TENANT_ID, "id": lead_id}, {"_id": 0}) or {}

    # Dedup — same (lead_id + signal_type + summary hash) within 30d → skip.
    sig_hash = _signal_dedup_hash(lead_id, intel.get("signal_type") or "", intel.get("signal_summary") or "")
    thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    if _insights.find_one({
        "tenant_id": PT_TENANT_ID,
        "lead_id": lead_id,
        "signal_dedup_hash": sig_hash,
        "created_at": {"$gte": thirty_days_ago},
    }):
        return {"skipped": True, "reason": "duplicate_within_30d"}

    prompt = (
        "You are a senior B2B sales strategist advising the Pietential founder.\n"
        "Pietential measures and improves employee wellbeing, engagement, and human "
        "potential for enterprise orgs (1,000–10,000 employees).\n\n"
        f"Prospect:\nName: {lead.get('first_name')} {lead.get('last_name')}\n"
        f"Title: {lead.get('job_title')}\n"
        f"Company: {lead.get('company_name')} ({lead.get('company_size') or 'unknown size'})\n"
        f"ICP: {lead.get('icp_segment')} — {lead.get('icp_match_reason')}\n"
        f"Lemlist engagement: {lead.get('intent_reason')}\n"
        f"Reply: {lead.get('reply_summary') or 'none'}\n\n"
        f"Signal:\nType: {intel.get('signal_type')}\n"
        f"Summary: {intel.get('signal_summary')}\n"
        f"Why relevant: {intel.get('why_relevant_for_pietential')}\n\n"
        "Generate a complete outreach recommendation. JSON only. Required keys: "
        "channel (email|linkedin|whatsapp), channel_reason, timing (be specific, "
        "include a window like 'Tue 9-11am IST'), opening_message (under 100 words, "
        "warm, peer-to-peer, no 'hope this finds you well', no product pitch in msg 1), "
        "lead_magnet_type, lead_magnet_line, follow_up_day5, what_not_to_do, "
        "key_insight_trigger, key_insight_why, key_insight_angle."
    )
    try:
        data = await claude_call(
            task_type=TaskType.INSIGHT_GENERATION,
            system="You write B2B outreach recommendations. JSON only.",
            prompt=prompt,
            tenant_id=PT_TENANT_ID,
            session_id=f"insight-{lead_id}",
            response_format="json",
        )
    except ClaudeServiceError as e:
        logger.warning("insight gen failed: %s", str(e)[:200])
        return None

    lead_score, account_tier, founder_flag = _compute_score_tier_flag(lead, intel)
    prospect_name = f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip() or lead.get('email', '')
    doc = {
        "id": f"ins_{uuid.uuid4().hex[:14]}",
        "tenant_id": PT_TENANT_ID,
        "lead_id": lead_id,
        "signal_type": intel.get("signal_type"),
        "signal_summary": intel.get("signal_summary"),
        "why_relevant_for_pietential": intel.get("why_relevant_for_pietential"),
        "outreach_recommendation": data,
        "icp_segment": lead.get("icp_segment"),
        "lemlist_intent": lead.get("lemlist_intent"),
        "lead_score": lead_score,
        "account_tier": account_tier,
        "founder_flag": founder_flag,
        "signal_dedup_hash": sig_hash,
        # UI-compatibility fields so /api/pt/insights/feed renders the card.
        "prospect_name": prospect_name,
        "prospect_title": lead.get("job_title") or "",
        "prospect_company": lead.get("company_name") or "",
        "suggested_message": (data or {}).get("opening_message") or "",
        "confidence": float(intel.get("confidence") or 0.0),
        "icp_match_name": lead.get("icp_segment_name") or "",
        "icp_match_score": (int(lead.get("icp_score") or 0) / 100.0),
        "status": "new",
        "source": "pietential_engine",
        "created_at": _now_iso(),
        "week_of": _iso_week(),
    }
    _insights.insert_one(dict(doc))

    # Founder WhatsApp alert (Part 9.2)
    if founder_flag and (intel.get("confidence") or 0) >= 0.85:
        try:
            await _whatsapp_founder_alert(doc, lead, intel)
        except Exception:  # noqa: BLE001
            logger.exception("whatsapp founder alert failed (non-fatal)")
        # iter144 — Slack ping alongside the WhatsApp alert. Fires only when
        # SLACK_WEBHOOK_URL is set in env; silent no-op otherwise.
        try:
            await _slack_founder_alert(doc, lead, intel)
        except Exception:  # noqa: BLE001
            logger.exception("slack founder alert failed (non-fatal)")

    return {k: v for k, v in doc.items() if k != "_id"}


# ─────────────────────── Part 7 — Lead scoring ───────────────────────

_ICP_SCORE = {"icp_a": 35, "icp_b": 35, "icp_c": 28, "icp_d": 25, "icp_e": 20, "icp_unknown": 10, "icp_not_fit": 0}
_INTENT_SCORE = {"HIGH_INTENT": 40, "MEDIUM_INTENT": 24, "LOW_INTENT": 8, "DISQUALIFIED": 0}
_AUTH_SCORE = {"decision_maker": 10, "influencer": 6, "user": 3, "unknown": 2}


def _compute_score_tier_flag(lead: Dict[str, Any], intel: Optional[Dict[str, Any]] = None) -> Tuple[int, str, bool]:
    icp = (lead.get("icp_segment") or "icp_unknown").lower()
    intent = (lead.get("lemlist_intent") or "LOW_INTENT").upper()
    auth = (lead.get("buying_authority") or "unknown").lower()

    last = lead.get("last_lemlist_activity") or lead.get("updated_at")
    days_since = 999
    if last:
        try:
            ts = datetime.fromisoformat(last.replace("Z", "+00:00"))
            days_since = (datetime.now(timezone.utc) - ts).days
        except Exception:  # noqa: BLE001
            days_since = 999
    if days_since <= 3:
        recency = 15
    elif days_since <= 7:
        recency = 10
    elif days_since <= 14:
        recency = 6
    elif days_since <= 30:
        recency = 3
    else:
        recency = 0

    score = min(
        _ICP_SCORE.get(icp, 10)
        + _INTENT_SCORE.get(intent, 0)
        + recency
        + _AUTH_SCORE.get(auth, 2),
        100,
    )

    if score >= 80:
        tier = "tier_1"
    elif score >= 60:
        tier = "tier_2"
    elif score >= 40:
        tier = "tier_3"
    else:
        tier = "not_priority"

    flag = False
    sig_type = (intel or {}).get("signal_type")
    if score >= 80 and sig_type in ("new_people_leader", "layoffs"):
        flag = True
    elif lead.get("reply_sentiment") == "POSITIVE" and icp in ("icp_a", "icp_b"):
        flag = True
    elif lead.get("job_title", "").upper().startswith(("CHRO", "CPO", "CHIEF PEOPLE")) and (lead.get("company_size") or 0) >= 2000:
        flag = True

    return score, tier, flag


def _recompute_lead_score(lead_id: str) -> Optional[Dict[str, Any]]:
    lead = _leads.find_one({"tenant_id": PT_TENANT_ID, "id": lead_id}, {"_id": 0})
    if not lead:
        return None
    intel = _prospect_intel.find_one({"tenant_id": PT_TENANT_ID, "lead_id": lead_id}, {"_id": 0})
    score, tier, flag = _compute_score_tier_flag(lead, intel)
    _leads.update_one(
        {"tenant_id": PT_TENANT_ID, "id": lead_id},
        {"$set": {"lead_score": score, "account_tier": tier, "founder_flag": flag}},
    )
    return {"lead_score": score, "account_tier": tier, "founder_flag": flag}


# ─────────────────────── Part 8 — Daily 07:30 IST scan ───────────────────────

async def pietential_insight_scan_once() -> Dict[str, Any]:
    leads = list(_leads.find(
        {"tenant_id": PT_TENANT_ID, "insights_enabled": True,
         "lemlist_intent": {"$in": ["HIGH_INTENT", "MEDIUM_INTENT"]}},
        {"_id": 0, "id": 1},
    ).limit(200))
    enriched = 0
    signals_found = 0
    cards_created = 0
    for ld in leads:
        try:
            e = await enrich_lead(ld["id"])
            if e and e.get("enriched"):
                enriched += 1
                sig = await classify_signal_for_lead(ld["id"])
                if sig and sig.get("signal_found"):
                    signals_found += 1
                    card = await generate_insight_card_for_lead(ld["id"])
                    if card and not card.get("skipped"):
                        cards_created += 1
            _recompute_lead_score(ld["id"])
        except Exception:  # noqa: BLE001
            logger.exception("scan failed for lead %s", ld["id"])
    _audit_event("pietential_insight_scan", processed=len(leads), enriched=enriched,
                 signals_found=signals_found, cards_created=cards_created)
    return {"processed": len(leads), "enriched": enriched, "signals_found": signals_found, "cards_created": cards_created}


async def pietential_insight_scan_loop() -> None:
    """Fires once daily when local clock matches 07:30 IST (±5min).
    IST = UTC+5:30 → 07:30 IST == 02:00 UTC."""
    fired_for_date: Optional[str] = None
    while True:
        try:
            now_utc = datetime.now(timezone.utc)
            target_hour, target_minute = 2, 0  # 07:30 IST minus 5:30 == 02:00 UTC
            today = now_utc.date().isoformat()
            if now_utc.hour == target_hour and abs(now_utc.minute - target_minute) <= 5 and fired_for_date != today:
                fired_for_date = today
                await pietential_insight_scan_once()
        except Exception:  # noqa: BLE001
            logger.exception("pietential_insight_scan_loop error")
        await asyncio.sleep(60)


# ─────────────────────── Part 9 — Delivery ───────────────────────

async def _slack_founder_alert(insight: Dict[str, Any], lead: Dict[str, Any], intel: Dict[str, Any]) -> None:
    """iter144 — Slack ping for high-confidence Pietential signals (founder_flag
    + confidence ≥ 0.85). Uses block-kit so the founder sees prospect, signal,
    score, and a deeplink in one glance. Silent no-op when SLACK_WEBHOOK_URL
    not set."""
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook:
        return
    rec = insight.get("outreach_recommendation") or {}
    opening = " ".join((rec.get("opening_message") or "").split()[:35])
    name = f"{lead.get('first_name','')} {lead.get('last_name','')}".strip() or lead.get("email", "Prospect")
    company = lead.get("company_name") or "—"
    title = lead.get("job_title") or "—"
    deeplink = f"https://app.genleadai.com/app/instinct?card_id={insight.get('id')}"
    payload = {
        "text": f"🔍 ARIA Signal · {name} · {company}",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"🔍 Founder-attention signal · Pietential", "emoji": True},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Prospect*\n{name}"},
                    {"type": "mrkdwn", "text": f"*Role*\n{title}"},
                    {"type": "mrkdwn", "text": f"*Company*\n{company}"},
                    {"type": "mrkdwn", "text": f"*Score*\n{insight.get('lead_score', 0)}/100 · {insight.get('account_tier', '—')}"},
                ],
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Signal* ({int((intel.get('confidence') or 0) * 100)}% conf · {intel.get('signal_type', '—')})\n{insight.get('signal_summary', '—')}"},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Suggested opening*\n_{opening}…_"},
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Open in ARIA", "emoji": True},
                        "url": deeplink,
                        "style": "primary",
                    },
                ],
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"channel: *{rec.get('channel', '—')}* · timing: *{rec.get('timing', '—')}*"},
                ],
            },
        ],
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(webhook, data=data, headers={"Content-Type": "application/json"})
    try:
        await asyncio.to_thread(lambda: urllib.request.urlopen(req, timeout=8).read())
        _audit_event("slack_founder_alert_sent", insight_id=insight.get("id"), lead_id=lead.get("id"))
    except Exception as e:  # noqa: BLE001
        logger.warning("slack founder alert send failed: %s", str(e)[:200])


async def _whatsapp_founder_alert(insight: Dict[str, Any], lead: Dict[str, Any], intel: Dict[str, Any]) -> None:
    key = _get_provider_key("360dialog") or _get_provider_key("whatsapp")
    pref = _notif_prefs.find_one({"tenant_id": PT_TENANT_ID}, {"_id": 0}) or {}
    to = pref.get("whatsapp_to") or os.environ.get("APPLICATION_NOTIFY_WHATSAPP")
    if not key or not to:
        return
    opening = (insight.get("outreach_recommendation") or {}).get("opening_message") or ""
    short = " ".join(opening.split()[:25])
    body = (
        f"🔍 ARIA Signal — Pietential\n"
        f"{lead.get('first_name','')} {lead.get('last_name','')} · {lead.get('job_title','')} · {lead.get('company_name','')}\n"
        f"Signal: {insight.get('signal_summary')}\n"
        f"Score: {insight.get('lead_score')}/100\n"
        f"{short}...\n"
        f"View → https://app.genleadai.com/app/instinct?card_id={insight.get('id')}"
    )
    data = json.dumps({"to": str(to).lstrip("+"), "type": "text", "text": {"body": body[:1024]}}).encode("utf-8")
    req = urllib.request.Request(
        "https://waba.360dialog.io/v1/messages",
        data=data,
        headers={"D360-API-KEY": key, "Content-Type": "application/json"},
    )
    try:
        await asyncio.to_thread(lambda: urllib.request.urlopen(req, timeout=8).read())
    except Exception as e:  # noqa: BLE001
        logger.warning("whatsapp send failed: %s", str(e)[:200])


async def send_weekly_intelligence_report() -> Dict[str, Any]:
    seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    new_leads = list(_leads.find(
        {"tenant_id": PT_TENANT_ID, "created_at": {"$gte": seven_days_ago}},
        {"_id": 0}
    ))
    cards = list(_insights.find(
        {"tenant_id": PT_TENANT_ID, "created_at": {"$gte": seven_days_ago}},
        {"_id": 0}
    ).sort("lead_score", -1))

    if not new_leads and not cards:
        return {"sent": False, "reason": "no_activity"}

    founder = [c for c in cards if c.get("founder_flag")]
    tier1 = [c for c in cards if c.get("account_tier") == "tier_1" and not c.get("founder_flag")]
    tier2 = [c for c in cards if c.get("account_tier") == "tier_2"]

    pref = _notif_prefs.find_one({"tenant_id": PT_TENANT_ID}, {"_id": 0}) or {}
    recipients = pref.get("weekly_report_to") or pref.get("send_to_email")
    if not recipients:
        # Fall back to tenant owner.
        tenant = db["tenants"].find_one({"id": PT_TENANT_ID}, {"_id": 0}) or {}
        recipients = tenant.get("owner_email")
    if not recipients:
        return {"sent": False, "reason": "no_recipient"}

    key = os.environ.get("RESEND_API_KEY") or _get_provider_key("resend")
    sender = os.environ.get("SENDER_EMAIL") or "onboarding@resend.dev"
    if not key:
        return {"sent": False, "reason": "no_resend_key"}
    resend.api_key = key

    intent_counts = {"HIGH_INTENT": 0, "MEDIUM_INTENT": 0, "LOW_INTENT": 0, "DISQUALIFIED": 0}
    for lead in new_leads:
        intent_key = lead.get("lemlist_intent") or "LOW_INTENT"
        intent_counts[intent_key] = intent_counts.get(intent_key, 0) + 1
    needs_qual = [lead for lead in new_leads if not lead.get("icp_segment") or lead.get("icp_segment") == "icp_unknown"]

    def _card_row(c):
        rec = c.get("outreach_recommendation") or {}
        opening = " ".join((rec.get("opening_message") or "").split()[:30])
        return (
            f"<li><strong>{c.get('lead_id','')[:14]}</strong> · "
            f"Signal: {c.get('signal_summary','')} · "
            f"Score {c.get('lead_score',0)}/100 · "
            f"{rec.get('channel','')} · {rec.get('timing','')}<br/>"
            f"<em>{opening}…</em></li>"
        )

    html = (
        f"<h2>ARIA Intelligence Brief — Week of {datetime.now(timezone.utc).date().isoformat()}</h2>"
        f"<p>{len(cards)} signals · {len(founder) + len(tier1)} hot leads</p>"
        f"<h3>1. Founder attention required ({len(founder)})</h3>"
        f"<ul>{''.join(_card_row(c) for c in founder) or '<li>None this week.</li>'}</ul>"
        f"<h3>2. Hot leads — Tier 1 ({len(tier1)})</h3>"
        f"<ul>{''.join(_card_row(c) for c in tier1) or '<li>None this week.</li>'}</ul>"
        f"<h3>3. Warm leads — Tier 2 ({len(tier2)})</h3>"
        f"<ul>{''.join(_card_row(c) for c in tier2) or '<li>None this week.</li>'}</ul>"
        f"<h3>4. Pipeline health</h3>"
        f"<p>Pulled this week: {len(new_leads)} leads · "
        f"High {intent_counts['HIGH_INTENT']} · Medium {intent_counts['MEDIUM_INTENT']} · "
        f"Low {intent_counts['LOW_INTENT']} · Disqualified {intent_counts['DISQUALIFIED']}<br/>"
        f"Signals detected: {sum(1 for c in cards)} · Insight cards: {len(cards)}</p>"
        f"<h3>5. Needs qualification ({len(needs_qual)})</h3>"
        f"<p>Action: enrich or confirm LinkedIn URL for these leads.</p>"
    )
    try:
        resend.Emails.send({
            "from": f"ARIA <{sender}>",
            "to": [recipients] if isinstance(recipients, str) else recipients,
            "subject": f"Your ARIA Intelligence Brief — Week of {datetime.now(timezone.utc).date()} — {len(founder)+len(tier1)} hot · {len(cards)} signals",
            "html": html,
        })
        _audit_event("weekly_intel_report_sent", to=recipients, card_count=len(cards), new_leads=len(new_leads))
        return {"sent": True, "to": recipients, "card_count": len(cards)}
    except Exception as e:  # noqa: BLE001
        logger.warning("weekly report send failed: %s", str(e)[:200])
        return {"sent": False, "error": str(e)[:200]}


async def weekly_intel_report_loop() -> None:
    """Mon 08:00 IST → 02:30 UTC. Fire once per week."""
    fired_for_week: Optional[str] = None
    while True:
        try:
            now_utc = datetime.now(timezone.utc)
            week_key = _iso_week(now_utc)
            # Monday is weekday()==0. 08:00 IST == 02:30 UTC.
            if now_utc.weekday() == 0 and now_utc.hour == 2 and 25 <= now_utc.minute <= 35 and fired_for_week != week_key:
                fired_for_week = week_key
                await send_weekly_intelligence_report()
        except Exception:  # noqa: BLE001
            logger.exception("weekly_intel_report_loop error")
        await asyncio.sleep(60)


# ─────────────────────── Part 10 — Dashboard endpoint ───────────────────────

@router.get("/pipeline-health")
async def pipeline_health(current_user: dict = Depends(get_current_user)):
    """Used by the Pietential Command Center 'Lemlist Pipeline Health' card."""
    # Open to any member of the pietential tenant.
    membership = db["tenant_memberships"].find_one(
        {"tenant_id": PT_TENANT_ID, "user_email": current_user.get("email")}, {"_id": 0}
    )
    if not membership and current_user.get("role") != "master_admin":
        raise HTTPException(403, "Pietential workspace access required")

    total_active = _leads.count_documents({"tenant_id": PT_TENANT_ID, "lemlist_data.is_active_in_sequence": True})
    high_intent = _leads.count_documents({"tenant_id": PT_TENANT_ID, "lemlist_intent": "HIGH_INTENT"})
    # "Untouched for 48h+" = high intent + no outbound since last_lemlist_activity
    forty_eight_ago = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    high_intent_stale = _leads.count_documents({
        "tenant_id": PT_TENANT_ID, "lemlist_intent": "HIGH_INTENT",
        "$or": [{"founder_actioned_at": {"$exists": False}}, {"founder_actioned_at": {"$lt": forty_eight_ago}}],
    })
    awaiting_enrichment = _leads.count_documents({
        "tenant_id": PT_TENANT_ID,
        "lemlist_intent": {"$in": ["HIGH_INTENT", "MEDIUM_INTENT"]},
        "$or": [{"enrichment_status": {"$exists": False}}, {"enrichment_status": "pending"}],
    })
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    signals_this_week = _insights.count_documents({"tenant_id": PT_TENANT_ID, "created_at": {"$gte": week_ago}})

    last_report = list(_audit.find(
        {"tenant_id": PT_TENANT_ID, "event": "weekly_intel_report_sent"},
        {"_id": 0}
    ).sort("created_at", -1).limit(1))

    return {
        "total_active_lemlist_leads": total_active,
        "high_intent": high_intent,
        "high_intent_stale": high_intent_stale,
        "awaiting_enrichment": awaiting_enrichment,
        "signals_this_week": signals_this_week,
        "last_weekly_report": (last_report[0]["created_at"] if last_report else None),
        "next_weekly_report_hint": "Monday 08:00 IST",
    }


# ─────────────────────── Manual trigger endpoints (for testing + Run Scan Now) ───────────────────────

@router.post("/poll/run-now")
async def trigger_lemlist_poll(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") not in ("master_admin", "workspace_owner", "owner", "admin"):
        raise HTTPException(403, "owner/admin only")
    return await lemlist_poll_once()


@router.post("/scan/run-now")
async def trigger_daily_scan(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") not in ("master_admin", "workspace_owner", "owner", "admin"):
        raise HTTPException(403, "owner/admin only")
    return await pietential_insight_scan_once()


@router.post("/lead/{lead_id}/scan-now")
async def trigger_lead_scan(lead_id: str, current_user: dict = Depends(get_current_user)):
    """Used by the Lead 360 Intel tab `Scan Now` button."""
    membership = db["tenant_memberships"].find_one(
        {"tenant_id": PT_TENANT_ID, "user_email": current_user.get("email")}, {"_id": 0}
    )
    if not membership and current_user.get("role") != "master_admin":
        raise HTTPException(403, "Pietential workspace access required")
    e = await enrich_lead(lead_id)
    sig = await classify_signal_for_lead(lead_id) if e and e.get("enriched") else None
    card = None
    if sig and sig.get("signal_found"):
        card = await generate_insight_card_for_lead(lead_id)
    _recompute_lead_score(lead_id)
    return {"enrich": e, "signal": sig, "card": card}


@router.post("/weekly-report/send-now")
async def trigger_weekly_report(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") not in ("master_admin", "workspace_owner", "owner", "admin"):
        raise HTTPException(403, "owner/admin only")
    return await send_weekly_intelligence_report()


@router.post("/_test/simulate")
async def simulate_pipeline(current_user: dict = Depends(get_current_user)):
    """Verification helper — inserts a fake Lemlist lead + runs intent + ICP +
    scoring through the same code paths as production. Master admin only."""
    if current_user.get("role") != "master_admin":
        raise HTTPException(403, "master_admin only")
    email = f"sim_{uuid.uuid4().hex[:8]}@pietential-test.com"
    now_iso = _now_iso()
    fake = {
        "id": f"lead_{uuid.uuid4().hex[:14]}",
        "tenant_id": PT_TENANT_ID,
        "email": email,
        "first_name": "Priya",
        "last_name": "Sharma",
        "company_name": "Acme Wellness Corp",
        "job_title": "Chief People Officer",
        "company_size": 3500,
        "industry": "Technology",
        "source": "lemlist",
        "source_campaign": "Q1 CHRO Outreach",
        "lemlist_data": {
            "campaign_id": "camp_sim", "campaign_name": "Q1 CHRO Outreach",
            "sequence_step": 3, "emails_sent": 3, "emails_opened": 5, "open_count": 5,
            "links_clicked": 2, "clicked_urls": ["https://pietential.com/case-study"],
            "replied": True,
            "reply_content": "This is interesting — we just brought on a new CHRO and are reviewing our engagement programmes. Would you have time to chat next week?",
            "bounced": False, "unsubscribed": False,
            "last_activity_at": now_iso,
            "is_active_in_sequence": True, "completed_sequence": False,
        },
        "last_lemlist_activity": now_iso,
        "insights_enabled": True,
        "created_at": now_iso, "updated_at": now_iso,
    }
    _leads.insert_one(dict(fake))
    lead_id = fake["id"]
    intent = await classify_intent_for_lead(lead_id)
    icp = await score_icp_for_lead(lead_id)
    # Inject a fake high-confidence signal directly so we can verify the insight card path
    # without needing real Serper data.
    _prospect_intel.update_one(
        {"tenant_id": PT_TENANT_ID, "lead_id": lead_id},
        {"$set": {
            "tenant_id": PT_TENANT_ID, "lead_id": lead_id,
            "raw_sources": {"_simulated": True}, "scanned_at": now_iso,
            "enrichment_source": "simulated",
            "signal_found": True,
            "signal_type": "new_people_leader",
            "signal_summary": "Acme Wellness Corp appointed a new CHRO last week.",
            "signal_date": now_iso,
            "why_relevant_for_pietential": "New CHROs typically audit their engagement programmes within the first 90 days.",
            "confidence": 0.91,
            "source_url": "https://example.com/news/acme-chro",
            "signal_classified_at": now_iso,
        }},
        upsert=True,
    )
    _leads.update_one(
        {"tenant_id": PT_TENANT_ID, "id": lead_id},
        {"$set": {"enrichment_status": "done", "enriched_at": now_iso}},
    )
    card = await generate_insight_card_for_lead(lead_id)
    _recompute_lead_score(lead_id)
    final = _leads.find_one({"tenant_id": PT_TENANT_ID, "id": lead_id}, {"_id": 0})
    return {
        "lead_id": lead_id,
        "email": email,
        "intent_result": intent,
        "icp_result": icp,
        "insight_card_id": (card or {}).get("id") if isinstance(card, dict) else None,
        "card_status": (card or {}).get("status") if isinstance(card, dict) else card,
        "final_lead": {k: final.get(k) for k in ("lemlist_intent", "icp_segment", "lead_score", "account_tier", "founder_flag")} if final else None,
    }


@router.post("/_test/cleanup-simulated")
async def cleanup_simulated(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "master_admin":
        raise HTTPException(403, "master_admin only")
    leads_deleted = _leads.delete_many({"tenant_id": PT_TENANT_ID, "email": {"$regex": "@pietential-test.com$"}}).deleted_count
    insights_deleted = _insights.delete_many({"tenant_id": PT_TENANT_ID, "lead_id": {"$regex": "^lead_"}, "outreach_recommendation.timing": {"$exists": True}}).deleted_count
    intel_deleted = _prospect_intel.delete_many({"tenant_id": PT_TENANT_ID, "enrichment_source": "simulated"}).deleted_count
    return {"leads_deleted": leads_deleted, "insights_deleted": insights_deleted, "intel_deleted": intel_deleted}


__all__ = [
    "router",
    "lemlist_poll_loop",
    "lemlist_poll_once",
    "pietential_insight_scan_loop",
    "pietential_insight_scan_once",
    "weekly_intel_report_loop",
    "send_weekly_intelligence_report",
]
