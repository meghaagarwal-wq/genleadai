"""
Aria for Pietential — Wellbeing engagement intelligence dashboard.

A self-contained workspace that captures interaction signals from
Saleshandy, Lemlist, Good Slice newsletter, lead magnets, Calendly,
GA4, LinkedIn Pixel, and manual uploads. Scores leads, classifies
stages, cascades to account-level, and triggers pause/route logic.

Designed multi-tenant ready: all data lives in `pt_*` collections,
isolated from the legacy ARIA CRM workspace. New workspaces can be
added by cloning this router under a new prefix + collection set.
"""
import asyncio
import csv
import hmac
import io
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Header
from pydantic import BaseModel, Field, EmailStr
from pymongo import DESCENDING

from deps import db, get_current_user, users_collection

router = APIRouter(prefix="/api/pt", tags=["pietential"])

# ─── Collections (isolated from legacy CRM) ──────────────────────────────────
leads_col = db["pt_leads"]
companies_col = db["pt_companies"]
events_col = db["pt_events"]
tasks_col = db["pt_tasks"]
notes_col = db["pt_notes"]
integrations_col = db["pt_integrations"]
training_col = db["pt_training_signals"]
campaigns_col = db["pt_campaigns"]
logs_col = db["pt_automation_logs"]

# ─── Encryption (reuses workspace ENCRYPTION_KEY) ───────────────────────────
_ENC_KEY = os.environ.get("ENCRYPTION_KEY")
_cipher = Fernet(_ENC_KEY.encode()) if _ENC_KEY else None


def _enc(s: str) -> str:
    if not s or not _cipher:
        return ""
    return _cipher.encrypt(s.encode()).decode()


def _dec(s: str) -> str:
    if not s or not _cipher:
        return ""
    try:
        return _cipher.decrypt(s.encode()).decode()
    except InvalidToken:
        return ""


def _mask_key(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    return f"••••{s[-4:]}" if len(s) >= 4 else "••••"


# ─── Automation log helper ──────────────────────────────────────────────────
def _log(kind: str, message: str, level: str = "info", **meta):
    """Append to /pt/logs visible feed. Levels: info | warn | error."""
    logs_col.insert_one({
        "id": _new_id("ptlog"),
        "kind": kind,         # webhook | sync | decay | csv_import | rule
        "level": level,
        "message": message,
        "metadata": meta,
        "created_at": _now_iso(),
    })

# ─── Scoring rules per Pietential touchpoint roadmap ────────────────────────
SCORING_RULES = {
    # Saleshandy
    "saleshandy.email_opened":     {"score": 3,  "cap_per_sequence": 3, "label": "Email opened",            "source": "saleshandy"},
    "saleshandy.email_clicked":    {"score": 10, "label": "Email link clicked",                              "source": "saleshandy"},
    "saleshandy.positive_reply":   {"score": 30, "label": "Positive email reply",   "trigger_pause": True,   "source": "saleshandy"},
    # Lemlist
    "lemlist.connection_accepted": {"score": 15, "label": "LinkedIn connection accepted",                    "source": "lemlist"},
    "lemlist.dm_positive_reply":   {"score": 30, "label": "LinkedIn DM positive reply", "trigger_pause": True,"source": "lemlist"},
    "lemlist.post_engagement":     {"score": 5,  "label": "LinkedIn post engagement",                        "source": "lemlist"},
    # Good Slice newsletter
    "newsletter.subscribed":       {"score": 25, "label": "Newsletter subscribed",                            "source": "good_slice"},
    "newsletter.opened":           {"score": 8,  "label": "Newsletter opened",                                "source": "good_slice"},
    "newsletter.clicked":          {"score": 15, "label": "Newsletter clicked",                               "source": "good_slice"},
    "newsletter.positive_reply":   {"score": 35, "label": "Newsletter positive reply", "trigger_pause": True, "source": "good_slice"},
    # Lead magnets
    "lead_magnet.downloaded":      {"score": 25, "label": "Lead magnet downloaded",                           "source": "lead_magnet"},
    "lead_magnet.company_claim":   {"score": 20, "label": "Company page magnet claim",                        "source": "lead_magnet"},
    "jsa.claimed":                 {"score": 25, "label": "Job Satisfaction Analysis claimed",                "source": "lead_magnet"},
    "jsa.completed":               {"score": 35, "label": "Job Satisfaction Analysis completed",              "source": "lead_magnet"},
    # Website intent
    "website.pricing_visit":       {"score": 30, "label": "Pricing/contact page visited",                     "source": "website"},
    "website.long_dwell":          {"score": 8,  "label": "Content visited > 2 min",                           "source": "website"},
    # Calendly
    "calendly.session_booked":     {"score": 80, "label": "Session booked", "trigger_pause": True,            "source": "calendly"},
    # Manual
    "manual.hypothesis_reply":     {"score": 40, "label": "Hypothesis email reply", "trigger_pause": True,    "source": "manual"},
    "manual.dnc":                  {"score": -50,"label": "DNC / unsubscribed",                                "source": "manual"},
}

STAGE_BOUNDARIES = [
    (110, "session_pilot"),
    (70,  "engaged"),
    (35,  "hot"),
    (15,  "warm"),
    (-1000, "cold"),
]


def classify_stage(score: int) -> str:
    for threshold, name in STAGE_BOUNDARIES:
        if score >= threshold:
            return name
    return "cold"


def _tf(current_user: dict) -> dict:
    """Tenant filter — ensures every pt_* read/write is scoped to the caller's
    active tenant. The migration tagged all legacy pt_* docs with
    tenant_id='ten_pietential'. Admin@demo.com is a member of both tenants;
    the X-Tenant-Id header (set by the frontend tenant switcher) picks which
    one wins. Any tenant that is not 'ten_pietential' sees zero pt_* rows."""
    return {"tenant_id": current_user.get("tenant_id")}


def _stamp_tenant(doc: dict, current_user: dict) -> dict:
    """Stamp tenant_id on a document being inserted/updated."""
    doc["tenant_id"] = current_user.get("tenant_id")
    return doc


def recommendation_for(score: int) -> str:
    if score >= 110: return "Create opportunity and track session/pilot."
    if score >= 70:  return "Remove from automation. John owns this conversation."
    if score >= 35:  return "Pause outreach and alert John."
    if score >= 15:  return "Add to Good Slice and monitor."
    return "Let automation continue."


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ─── Permissions ────────────────────────────────────────────────────────────
def _role_of(user: dict) -> str:
    return (user.get("role") or "").lower()


def _is_admin(user: dict) -> bool:
    return _role_of(user) in ("admin", "master_admin", "owner")


def _can_write(user: dict) -> bool:
    # iter82 — master_admin (GenLeadAI operator) and tenant owner can always
    # write to the Pietential workspace. This unblocks the AI Setup +
    # integration test handshake flows.
    return _role_of(user) in (
        "admin", "master_admin", "owner",
        "content_vista", "pietential_owner", "sales_rep",
    )


def _require_write(user: dict):
    if not _can_write(user):
        raise HTTPException(status_code=403, detail="Read-only role")


def _strip_id(d):
    if d and "_id" in d:
        d.pop("_id", None)
    return d


# ─── Pydantic models ────────────────────────────────────────────────────────
class LeadCreate(BaseModel):
    first_name: str
    last_name: str = ""
    email: EmailStr
    company_name: Optional[str] = None
    title: Optional[str] = None
    linkedin_url: Optional[str] = None
    source: Optional[str] = "manual"
    industry: Optional[str] = None
    employee_count: Optional[int] = None
    geography: Optional[str] = None
    icp_fit: Optional[str] = None  # "match" | "partial" | "outside"
    owner: Optional[str] = "Content Vista"
    notes: Optional[str] = None


class LeadPatch(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    company_name: Optional[str] = None
    title: Optional[str] = None
    linkedin_url: Optional[str] = None
    source: Optional[str] = None
    industry: Optional[str] = None
    employee_count: Optional[int] = None
    geography: Optional[str] = None
    icp_fit: Optional[str] = None
    owner: Optional[str] = None
    automation_status: Optional[str] = None
    stage: Optional[str] = None  # admin override


class AskAriaPayload(BaseModel):
    channel: str = "linkedin"           # whatsapp | email | linkedin | call_script
    tone: str = "founder_led"           # founder_led | friendly | direct | premium | consultative | sharp_closer | soft_nurture
    user_note: Optional[str] = ""


class EventCreate(BaseModel):
    lead_id: Optional[str] = None
    email: Optional[EmailStr] = None
    event_type: str  # e.g. "saleshandy.email_clicked"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskCreate(BaseModel):
    title: str
    lead_id: Optional[str] = None
    company_id: Optional[str] = None
    owner: str = "Content Vista"
    priority: str = "normal"  # low | normal | high | urgent
    due_date: Optional[str] = None
    source_trigger: Optional[str] = None


class TaskPatch(BaseModel):
    status: Optional[str] = None  # open | in_progress | done | blocked
    owner: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[str] = None


class NoteCreate(BaseModel):
    note: str = Field(..., min_length=1, max_length=2000)
    lead_id: Optional[str] = None
    company_id: Optional[str] = None
    tag: Optional[str] = None  # e.g. "icp_checked", "added_to_good_slice", "dnc"


class IntegrationUpsert(BaseModel):
    name: str
    api_key: Optional[str] = None
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None
    status: Optional[str] = None  # not_connected | connected | needs_setup


class BulkLeadsPayload(BaseModel):
    leads: List[Dict[str, Any]]


# ─── Company resolution & cascade ───────────────────────────────────────────
def _ensure_company(name: Optional[str], lead: dict, tenant_id: Optional[str] = None) -> Optional[dict]:
    """Find or create a company doc. Tenant-scoped: company created/looked-up
    only within the caller's tenant."""
    if not name:
        return None
    norm = name.strip().lower()
    tf = {"tenant_id": tenant_id} if tenant_id else {}
    company = companies_col.find_one({**tf, "name_norm": norm})
    if not company:
        company = {
            "id": _new_id("ptc"),
            "name": name.strip(),
            "name_norm": norm,
            "industry": lead.get("industry"),
            "employee_count": lead.get("employee_count"),
            "geography": lead.get("geography"),
            "icp_fit": lead.get("icp_fit"),
            "highest_score": 0,
            "account_stage": "cold",
            "sequence_status": "not_started",
            "pause_required": False,
            "owner": "Content Vista",
            "contacts_mapped": 1,
            "exec_status": {},  # {ceo: name, cfo: name, chro: name}
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        if tenant_id:
            company["tenant_id"] = tenant_id
        companies_col.insert_one(company)
    else:
        contacts = leads_col.count_documents({**tf, "company_id": company["id"]})
        companies_col.update_one(
            {"id": company["id"], **tf},
            {"$set": {"contacts_mapped": max(1, contacts), "updated_at": _now_iso()}}
        )
    return _strip_id(company)


def _exec_role_from_title(title: Optional[str]) -> Optional[str]:
    if not title: return None
    t = title.lower()
    if "ceo" in t or "chief executive" in t: return "ceo"
    if "cfo" in t or "chief financial" in t: return "cfo"
    if "chro" in t or "chief people" in t or "chief human" in t: return "chro"
    if "vp people" in t and "analytics" in t: return "vp_people_analytics"
    if "director" in t and "wellbeing" in t: return "director_wellbeing"
    if "vp total rewards" in t or "vp rewards" in t: return "vp_total_rewards"
    return None


def _recompute_company(company_id: str):
    """Recompute account-level stage + pause flag from member leads."""
    leads = list(leads_col.find({"company_id": company_id}, {"_id": 0}))
    if not leads:
        return
    highest = max((l.get("score") or 0) for l in leads)
    stage = classify_stage(highest)
    # Pause required if any lead is hot/engaged/session OR has a pause-trigger event
    pause = stage in ("hot", "engaged", "session_pilot")
    if not pause:
        # also check for any pause-trigger event in events_col
        pause = events_col.count_documents({
            "company_id": company_id,
            "event_type": {"$in": [k for k, v in SCORING_RULES.items() if v.get("trigger_pause")]},
        }) > 0
    # Sequence status mapping
    seq_status = "active_in_saleshandy"  # default; overridden by explicit setting
    company = companies_col.find_one({"id": company_id}, {"_id": 0})
    if company and company.get("sequence_status") not in (None, "not_started", "active_in_saleshandy", "active_in_lemlist", "warm_nurture"):
        seq_status = company["sequence_status"]
    if pause and seq_status not in ("paused", "john_owns", "dnc"):
        seq_status = "pause_required"
    if stage in ("engaged", "session_pilot"):
        seq_status = "john_owns"
    # Update exec_status from member titles
    exec_status = {}
    for l in leads:
        role = _exec_role_from_title(l.get("title"))
        if role and role not in exec_status:
            exec_status[role] = f"{l.get('first_name','')} {l.get('last_name','')}".strip()
    owner = "John" if stage in ("hot", "engaged", "session_pilot") else (company.get("owner") if company else "Content Vista")
    # Per-platform activity flags — set when leads/events from that platform exist
    saleshandy_active = leads_col.count_documents({"company_id": company_id, "source": "saleshandy"}) > 0 \
        or events_col.count_documents({"company_id": company_id, "source": "saleshandy"}) > 0
    lemlist_active = leads_col.count_documents({"company_id": company_id, "source": "lemlist"}) > 0 \
        or events_col.count_documents({"company_id": company_id, "source": "lemlist"}) > 0
    companies_col.update_one(
        {"id": company_id},
        {"$set": {
            "highest_score": highest,
            "account_stage": stage,
            "pause_required": pause,
            "sequence_status": seq_status,
            "exec_status": exec_status,
            "contacts_mapped": len(leads),
            "owner": owner,
            "saleshandy_active": saleshandy_active,
            "lemlist_active": lemlist_active,
            "updated_at": _now_iso(),
        }}
    )


def _create_pause_tasks(lead: dict, company: Optional[dict], event_type: str):
    """Create the canonical pause/route tasks when a pause trigger fires."""
    base = {
        "lead_id": lead["id"],
        "company_id": (company or {}).get("id"),
        "source_trigger": event_type,
        "status": "open",
        "priority": "high",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    seeds = []
    if "saleshandy" in event_type:
        seeds.append({"title": f"Pause Saleshandy sequence for {(company or {}).get('name') or lead.get('email')}", "owner": "Content Vista"})
    if "lemlist" in event_type or "linkedin" in event_type:
        seeds.append({"title": f"Pause Lemlist sequence for {(company or {}).get('name') or lead.get('email')}", "owner": "Content Vista"})
    if any(k in event_type for k in ("positive_reply", "dm_positive_reply", "session_booked", "hypothesis_reply")):
        seeds.append({"title": f"Route positive reply to John — {lead.get('email')}", "owner": "Content Vista", "priority": "urgent"})
        seeds.append({"title": f"Send John personal email — {lead.get('email')}", "owner": "John", "priority": "urgent"})
    if event_type == "calendly.session_booked":
        seeds.append({"title": f"Create opportunity after Calendly booking — {(company or {}).get('name') or lead.get('email')}", "owner": "John", "priority": "urgent"})
    for s in seeds:
        # Dedup: skip if same title+lead+open already exists
        existing = tasks_col.find_one({"lead_id": lead["id"], "title": s["title"], "status": {"$in": ["open", "in_progress"]}})
        if existing:
            continue
        doc = {**base, **s, "id": _new_id("ptt")}
        tasks_col.insert_one(doc)


# ─── Core ingestion (used by API + webhooks) ────────────────────────────────
def _ingest_event(event_type: str, lead_lookup: dict, metadata: dict, current_user_email: str = "system") -> dict:
    """
    Apply an engagement event:
      - find/create lead by email or lead_id
      - apply score (respecting cap_per_sequence)
      - update stage + recommendation
      - cascade to company, set pause flag if needed
      - auto-create tasks on pause triggers
      - persist event row
    """
    rule = SCORING_RULES.get(event_type)
    if not rule:
        raise HTTPException(status_code=400, detail=f"Unknown event_type: {event_type}")

    # Resolve lead
    lead = None
    if lead_lookup.get("lead_id"):
        lead = leads_col.find_one({"id": lead_lookup["lead_id"]}, {"_id": 0})
    if not lead and lead_lookup.get("email"):
        lead = leads_col.find_one({"email": lead_lookup["email"].lower().strip()}, {"_id": 0})
    if not lead:
        # Auto-create a thin lead from webhook payload if email is provided
        if lead_lookup.get("email"):
            email = lead_lookup["email"].lower().strip()
            new_lead = {
                "id": _new_id("ptl"),
                "first_name": metadata.get("first_name", ""),
                "last_name": metadata.get("last_name", ""),
                "email": email,
                "company_name": metadata.get("company_name"),
                "title": metadata.get("title"),
                "linkedin_url": metadata.get("linkedin_url"),
                "source": rule["source"],
                "industry": metadata.get("industry"),
                "employee_count": metadata.get("employee_count"),
                "geography": metadata.get("geography"),
                "icp_fit": metadata.get("icp_fit"),
                "score": 0,
                "stage": "cold",
                "latest_signal": rule["label"],
                "automation_status": "active",
                "owner": "Content Vista",
                "last_activity_at": _now_iso(),
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
            }
            leads_col.insert_one(new_lead)
            lead = _strip_id(new_lead)
        else:
            raise HTTPException(status_code=404, detail="Lead not found and no email provided to auto-create")

    # Cap check (per sequence) — Saleshandy email_opened max 3 per sequence_id
    score_change = rule["score"]
    if rule.get("cap_per_sequence"):
        seq_id = metadata.get("sequence_id") or "default"
        prior = events_col.count_documents({
            "lead_id": lead["id"], "event_type": event_type, "metadata.sequence_id": seq_id,
        })
        if prior >= rule["cap_per_sequence"]:
            score_change = 0

    new_score = max(-100, (lead.get("score") or 0) + score_change)
    new_stage = classify_stage(new_score)

    company = _ensure_company(lead.get("company_name"), lead)
    company_id = (company or {}).get("id")

    # Persist lead update
    leads_col.update_one(
        {"id": lead["id"]},
        {"$set": {
            "score": new_score,
            "stage": new_stage,
            "latest_signal": rule["label"],
            "company_id": company_id,
            "last_activity_at": _now_iso(),
            "updated_at": _now_iso(),
            "automation_status": "active" if new_stage == "cold" else ("nurture" if new_stage == "warm" else "paused"),
            "owner": "John" if new_stage in ("engaged", "session_pilot", "hot") else (lead.get("owner") or "Content Vista"),
        }}
    )

    # Persist event
    event_doc = {
        "id": _new_id("pte"),
        "lead_id": lead["id"],
        "company_id": company_id,
        "event_type": event_type,
        "label": rule["label"],
        "source": rule["source"],
        "score_change": score_change,
        "score_after": new_score,
        "stage_after": new_stage,
        "metadata": metadata,
        "created_by": current_user_email,
        "created_at": _now_iso(),
    }
    events_col.insert_one(event_doc)

    # Cascade to company + tasks
    if company_id:
        _recompute_company(company_id)
    if rule.get("trigger_pause") or new_stage in ("hot", "engaged", "session_pilot"):
        _create_pause_tasks(lead, company, event_type)

    return {
        "event": _strip_id(event_doc),
        "lead": leads_col.find_one({"id": lead["id"]}, {"_id": 0}),
        "company": companies_col.find_one({"id": company_id}, {"_id": 0}) if company_id else None,
        "recommendation": recommendation_for(new_score),
    }


# ─── Leads endpoints ────────────────────────────────────────────────────────
@router.post("/leads")
async def create_lead(payload: LeadCreate, current_user: dict = Depends(get_current_user)):
    _require_write(current_user)
    if leads_col.find_one({"email": payload.email.lower().strip(), **_tf(current_user)}):
        raise HTTPException(status_code=400, detail="Lead with this email already exists")
    doc = payload.dict()
    doc["email"] = doc["email"].lower().strip()
    doc.update({
        "id": _new_id("ptl"),
        "score": 0,
        "stage": "cold",
        "latest_signal": None,
        "automation_status": "active",
        "last_activity_at": None,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    })
    _stamp_tenant(doc, current_user)
    company = _ensure_company(doc.get("company_name"), doc, tenant_id=current_user.get("tenant_id"))
    doc["company_id"] = (company or {}).get("id")
    leads_col.insert_one(doc)
    if doc["company_id"]:
        _recompute_company(doc["company_id"])
    return {"lead": _strip_id(doc)}


@router.get("/leads")
async def list_leads(
    stage: Optional[str] = None,
    source: Optional[str] = None,
    score_min: Optional[int] = None,
    score_max: Optional[int] = None,
    industry: Optional[str] = None,
    title: Optional[str] = None,
    owner: Optional[str] = None,
    company_id: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 200,
    current_user: dict = Depends(get_current_user),
):
    query = {**_tf(current_user)}
    if stage: query["stage"] = stage
    if source: query["source"] = source
    if score_min is not None: query.setdefault("score", {})["$gte"] = score_min
    if score_max is not None: query.setdefault("score", {})["$lte"] = score_max
    if industry: query["industry"] = industry
    if title: query["title"] = {"$regex": title, "$options": "i"}
    if owner: query["owner"] = owner
    if company_id: query["company_id"] = company_id
    if q:
        query["$or"] = [
            {"email": {"$regex": q, "$options": "i"}},
            {"first_name": {"$regex": q, "$options": "i"}},
            {"last_name": {"$regex": q, "$options": "i"}},
            {"company_name": {"$regex": q, "$options": "i"}},
        ]
    rows = list(leads_col.find(query, {"_id": 0}).sort("last_activity_at", DESCENDING).limit(min(limit, 1000)))
    return {"leads": rows, "total": len(rows)}


@router.get("/leads/{lead_id}")
async def get_lead(lead_id: str, current_user: dict = Depends(get_current_user)):
    lead = leads_col.find_one({"id": lead_id, **_tf(current_user)}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    company = companies_col.find_one({"id": lead.get("company_id"), **_tf(current_user)}, {"_id": 0}) if lead.get("company_id") else None
    events = list(events_col.find({"lead_id": lead_id, **_tf(current_user)}, {"_id": 0}).sort("created_at", DESCENDING).limit(200))
    notes = list(notes_col.find({"lead_id": lead_id, **_tf(current_user)}, {"_id": 0}).sort("created_at", DESCENDING).limit(100))
    # Score breakdown — group events by event_type
    breakdown = {}
    for e in events:
        bucket = breakdown.setdefault(e["event_type"], {"label": e.get("label"), "count": 0, "total": 0})
        bucket["count"] += 1
        bucket["total"] += e.get("score_change", 0)
    return {
        "lead": lead,
        "company": company,
        "events": events,
        "notes": notes,
        "score_breakdown": [{"event_type": k, **v} for k, v in breakdown.items()],
        "recommendation": recommendation_for(lead.get("score") or 0),
    }


@router.patch("/leads/{lead_id}")
async def patch_lead(lead_id: str, payload: LeadPatch, current_user: dict = Depends(get_current_user)):
    _require_write(current_user)
    update = {k: v for k, v in payload.dict().items() if v is not None}
    if not update:
        raise HTTPException(status_code=400, detail="No fields to update")
    update["updated_at"] = _now_iso()
    res = leads_col.update_one({"id": lead_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead = leads_col.find_one({"id": lead_id}, {"_id": 0})
    if lead.get("company_id"):
        _recompute_company(lead["company_id"])
    return {"lead": lead}


@router.delete("/leads/{lead_id}")
async def delete_lead(lead_id: str, current_user: dict = Depends(get_current_user)):
    _require_write(current_user)
    lead = leads_col.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    leads_col.delete_one({"id": lead_id})
    events_col.delete_many({"lead_id": lead_id})
    notes_col.delete_many({"lead_id": lead_id})
    if lead.get("company_id"):
        _recompute_company(lead["company_id"])
    return {"status": "ok"}


@router.post("/leads/{lead_id}/ask-aria")
async def ask_aria_pt(lead_id: str, payload: AskAriaPayload, current_user: dict = Depends(get_current_user)):
    """Generate a Claude-powered reply draft using rich Pietential context:
    - Lead identity + ICP fit + stage + score
    - Last 10 engagement events (with timestamps + score deltas + source)
    - Account cascade context (sequence_status, pause_required, highest_score)
    - Aria recommendation tier
    - Latest note (founder context)
    - Optional ad-hoc user note from the founder

    Falls back to a heuristic message if Claude is unavailable.
    """
    lead = leads_col.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    company = companies_col.find_one({"id": lead.get("company_id")}, {"_id": 0}) if lead.get("company_id") else None
    events = list(events_col.find({"lead_id": lead_id}, {"_id": 0}).sort("created_at", DESCENDING).limit(10))
    last_note = notes_col.find_one({"lead_id": lead_id}, {"_id": 0}, sort=[("created_at", DESCENDING)])

    first_name = (lead.get("first_name") or "there").strip()
    last_name = (lead.get("last_name") or "").strip()
    company_name = lead.get("company_name") or "—"
    title = lead.get("title") or "—"
    score = lead.get("score") or 0
    stage = lead.get("stage") or "cold"
    icp_fit = lead.get("icp_fit") or "—"
    latest_signal = lead.get("latest_signal") or "—"

    # Event lines with score delta + source
    ev_lines = []
    for e in events:
        when = (e.get("created_at") or "")[:16].replace("T", " ")
        ev_lines.append(
            f"- {when} · {e.get('label') or e.get('event_type')} (source: {e.get('source') or '—'}, score Δ {e.get('score_change', 0):+d})"
        )
    events_text = "\n".join(ev_lines) or "(no engagement events yet)"

    # Account cascade context
    account_text = "(no linked account)"
    if company:
        account_text = (
            f"- Account: {company.get('name')}\n"
            f"- Account stage: {company.get('account_stage') or '—'}\n"
            f"- Sequence status: {company.get('sequence_status') or '—'}\n"
            f"- Pause required: {bool(company.get('pause_required'))}\n"
            f"- Highest contact score in account: {company.get('highest_score') or 0}"
        )

    note_text = (last_note or {}).get("note") or "(none)"

    tone_map = {
        "founder_led": "Warm, direct, personal. Short sentences. First-person. Founder-to-founder voice.",
        "friendly": "Warm and helpful. Casual. Light tone, no formal salutation.",
        "direct": "Sharp. 1-2 sentences. No fluff. Question-forward.",
        "premium": "Polished, consultative, no slang, executive tone.",
        "consultative": "Strategic, insight-led, thoughtful. Asks one smart question.",
        "sharp_closer": "Urgent, CTA-led, specific time slot offers. Drive a decision now.",
        "soft_nurture": "Helpful, educational, low-pressure, trust-building. No CTA.",
    }
    tone_instruction = tone_map.get(payload.tone, tone_map["founder_led"])

    channel_limits = {
        "whatsapp": "Max 2-3 short lines. No formal salutation. No 'hope you're well'.",
        "email": "Subject line on first line prefixed 'Subject:'. Then 3-4 short sentences. Clear ask. No corporate filler.",
        "linkedin": "Max 2-3 short lines. Conversational. No formal tone. Reference their actual signal.",
        "call_script": "Write a 3-sentence opener the founder can say on a call. Specific and personal — name a real signal from the timeline.",
    }
    channel_hint = channel_limits.get(payload.channel, channel_limits["linkedin"])

    recommendation = recommendation_for(int(score))

    system = (
        "You are ARIA, the AI sales agent for Pietential — a wellbeing platform. "
        "You draft outbound replies for the Pietential founder team. "
        "You write like a seasoned operator: specific, confident, no AI-speak, no emoji spam, "
        "no 'I hope this finds you well'. "
        "If the engagement timeline contains signals, reference at least one concrete signal. "
        "If the timeline is empty, write a tight cold-touch grounded in the lead's title, company, "
        "ICP fit, or industry — never refuse and never ask the user for more context. "
        "Always return only the message itself, no commentary."
    )

    pause_warning = ""
    if company and company.get("pause_required"):
        pause_warning = (
            "\n⚠️ ACCOUNT IS PAUSED: another contact in this account already engaged positively. "
            "Treat this as a 1:1 founder reply — NOT a sequence step. Do not pitch hard.\n"
        )

    prompt = f"""LEAD:
- Name: {first_name} {last_name}
- Title: {title}
- Company: {company_name}
- ICP fit: {icp_fit}
- Score: {score} · Stage: {stage}
- Latest signal: {latest_signal}

ACCOUNT CONTEXT:
{account_text}
{pause_warning}
RECENT ENGAGEMENT TIMELINE (most recent first):
{events_text}

ARIA'S CURRENT RECOMMENDATION: {recommendation}

LATEST INTERNAL NOTE: {note_text}

USER NOTE (from founder, optional steer): {payload.user_note or "(none)"}

Write ONE reply message.
Channel: {payload.channel.upper()}
Tone: {tone_instruction}
Format: {channel_hint}

Reference at least one specific timeline signal if any exists (don't invent — only use what's listed above). If the timeline is empty, ground the message in the lead's title, company, or ICP fit — never refuse, never ask the user for more info.
Return ONLY the message text — no JSON, no explanation, no preamble."""

    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        fallback = (
            f"Hi {first_name} — saw your recent activity around {latest_signal or 'our content'}. "
            f"Worth a 15-min chat this week? Tuesday 4 PM or Wednesday 11 AM works on my side."
        )
        return {
            "lead_id": lead_id, "channel": payload.channel, "tone": payload.tone,
            "message": fallback, "ai_powered": False, "ai_error": "EMERGENT_LLM_KEY not set",
        }

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=api_key,
            session_id=f"pt_ask_aria_{lead_id}_{payload.channel}_{payload.tone}",
            system_message=system,
        )
        chat.with_model("anthropic", "claude-4-sonnet-20250514")
        resp = await chat.send_message(UserMessage(text=prompt))
        message = (resp or "").strip().strip('"').strip("'")
        return {
            "lead_id": lead_id, "channel": payload.channel, "tone": payload.tone,
            "message": message, "ai_powered": True,
        }
    except Exception as e:
        fallback = (
            f"Hi {first_name} — saw your recent activity around {latest_signal or 'our content'}. "
            f"Worth a 15-min chat this week? Tuesday 4 PM or Wednesday 11 AM works on my side."
        )
        return {
            "lead_id": lead_id, "channel": payload.channel, "tone": payload.tone,
            "message": fallback, "ai_powered": False, "ai_error": str(e),
        }


@router.post("/leads/bulk")
async def bulk_leads(payload: BulkLeadsPayload, current_user: dict = Depends(get_current_user)):
    _require_write(current_user)
    created, failed, errors = 0, 0, []
    seen_emails = set()
    for i, row in enumerate(payload.leads):
        email = (row.get("email") or "").strip().lower()
        if not email or "@" not in email:
            failed += 1; errors.append({"row": i, "reason": "Invalid email"}); continue
        if email in seen_emails:
            failed += 1; errors.append({"row": i, "reason": "Duplicate email in payload"}); continue
        seen_emails.add(email)
        if leads_col.find_one({"email": email}):
            failed += 1; errors.append({"row": i, "reason": "Email already exists"}); continue
        try:
            score = int(row.get("score") or 0)
        except Exception:
            score = 0
        doc = {
            "id": _new_id("ptl"),
            "first_name": row.get("first_name") or "",
            "last_name": row.get("last_name") or "",
            "email": email,
            "company_name": row.get("company") or row.get("company_name"),
            "title": row.get("title"),
            "linkedin_url": row.get("linkedin_url"),
            "source": row.get("source") or "manual",
            "industry": row.get("industry"),
            "employee_count": int(row["employee_count"]) if (row.get("employee_count") or "").strip().isdigit() else None,
            "geography": row.get("geography"),
            "icp_fit": row.get("icp_fit"),
            "score": score,
            "stage": classify_stage(score),
            "latest_signal": row.get("latest_signal"),
            "automation_status": "active",
            "owner": row.get("owner") or "Content Vista",
            "last_activity_at": row.get("last_activity_date") or _now_iso(),
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        company = _ensure_company(doc.get("company_name"), doc)
        doc["company_id"] = (company or {}).get("id")
        leads_col.insert_one(doc)
        if doc["company_id"]:
            _recompute_company(doc["company_id"])
        if row.get("notes"):
            notes_col.insert_one({"id": _new_id("ptn"), "lead_id": doc["id"], "company_id": doc["company_id"], "note": row["notes"], "created_by": current_user["email"], "created_at": _now_iso()})
        created += 1
    return {"created": created, "failed": failed, "errors": errors}


# ─── Companies endpoints ────────────────────────────────────────────────────
@router.get("/companies")
async def list_companies(
    pause_required: Optional[bool] = None,
    account_stage: Optional[str] = None,
    industry: Optional[str] = None,
    q: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    query = {**_tf(current_user)}
    if pause_required is not None: query["pause_required"] = pause_required
    if account_stage: query["account_stage"] = account_stage
    if industry: query["industry"] = industry
    if q: query["name"] = {"$regex": q, "$options": "i"}
    rows = list(companies_col.find(query, {"_id": 0}).sort("highest_score", DESCENDING).limit(500))
    return {"companies": rows, "total": len(rows)}


@router.get("/companies/{company_id}")
async def get_company(company_id: str, current_user: dict = Depends(get_current_user)):
    company = companies_col.find_one({"id": company_id, **_tf(current_user)}, {"_id": 0})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    leads = list(leads_col.find({"company_id": company_id, **_tf(current_user)}, {"_id": 0}).sort("score", DESCENDING))
    events = list(events_col.find({"company_id": company_id, **_tf(current_user)}, {"_id": 0}).sort("created_at", DESCENDING).limit(200))
    return {"company": company, "leads": leads, "events": events}


@router.patch("/companies/{company_id}")
async def patch_company(company_id: str, body: Dict[str, Any], current_user: dict = Depends(get_current_user)):
    _require_write(current_user)
    allowed = {"sequence_status", "owner", "icp_fit", "industry", "employee_count", "geography"}
    update = {k: v for k, v in body.items() if k in allowed and v is not None}
    if not update:
        raise HTTPException(status_code=400, detail="No allowed fields")
    update["updated_at"] = _now_iso()
    res = companies_col.update_one({"id": company_id, **_tf(current_user)}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Company not found")
    return {"company": companies_col.find_one({"id": company_id}, {"_id": 0})}


# ─── Events endpoints ───────────────────────────────────────────────────────
@router.post("/events")
async def post_event(payload: EventCreate, current_user: dict = Depends(get_current_user)):
    """Manual event ingest — used from UI 'simulate event' actions and demo flow."""
    _require_write(current_user)
    return _ingest_event(
        event_type=payload.event_type,
        lead_lookup={"lead_id": payload.lead_id, "email": payload.email},
        metadata=payload.metadata or {},
        current_user_email=current_user["email"],
    )


@router.get("/events")
async def list_events(lead_id: Optional[str] = None, company_id: Optional[str] = None, limit: int = 100, current_user: dict = Depends(get_current_user)):
    query = {**_tf(current_user)}
    if lead_id: query["lead_id"] = lead_id
    if company_id: query["company_id"] = company_id
    rows = list(events_col.find(query, {"_id": 0}).sort("created_at", DESCENDING).limit(min(limit, 500)))
    return {"events": rows}


# ─── Tasks endpoints ────────────────────────────────────────────────────────
@router.post("/tasks")
async def create_task(payload: TaskCreate, current_user: dict = Depends(get_current_user)):
    _require_write(current_user)
    doc = payload.dict()
    doc.update({
        "id": _new_id("ptt"),
        "status": "open",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    })
    _stamp_tenant(doc, current_user)
    tasks_col.insert_one(doc)
    return {"task": _strip_id(doc)}


@router.get("/tasks")
async def list_tasks(
    status: Optional[str] = None, owner: Optional[str] = None, priority: Optional[str] = None,
    lead_id: Optional[str] = None, company_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    tf = _tf(current_user)
    query = {**tf}
    if status: query["status"] = status
    if owner: query["owner"] = owner
    if priority: query["priority"] = priority
    if lead_id: query["lead_id"] = lead_id
    if company_id: query["company_id"] = company_id
    rows = list(tasks_col.find(query, {"_id": 0}).sort("created_at", DESCENDING).limit(500))
    counts = {
        "total": tasks_col.count_documents(tf),
        "open": tasks_col.count_documents({**tf, "status": "open"}),
        "in_progress": tasks_col.count_documents({**tf, "status": "in_progress"}),
        "done": tasks_col.count_documents({**tf, "status": "done"}),
    }
    return {"tasks": rows, "counts": counts}


@router.patch("/tasks/{task_id}")
async def patch_task(task_id: str, payload: TaskPatch, current_user: dict = Depends(get_current_user)):
    _require_write(current_user)
    update = {k: v for k, v in payload.dict().items() if v is not None}
    if not update:
        raise HTTPException(status_code=400, detail="No fields to update")
    update["updated_at"] = _now_iso()
    res = tasks_col.update_one({"id": task_id, **_tf(current_user)}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task": tasks_col.find_one({"id": task_id}, {"_id": 0})}


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str, current_user: dict = Depends(get_current_user)):
    _require_write(current_user)
    res = tasks_col.delete_one({"id": task_id, **_tf(current_user)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "ok"}


# ─── Notes endpoints ────────────────────────────────────────────────────────
@router.post("/notes")
async def create_note(payload: NoteCreate, current_user: dict = Depends(get_current_user)):
    _require_write(current_user)
    doc = {
        "id": _new_id("ptn"),
        **payload.dict(),
        "created_by": current_user["email"],
        "created_by_name": current_user.get("full_name"),
        "created_at": _now_iso(),
    }
    _stamp_tenant(doc, current_user)
    notes_col.insert_one(doc)
    return {"note": _strip_id(doc)}


@router.get("/notes")
async def list_notes(lead_id: Optional[str] = None, company_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {**_tf(current_user)}
    if lead_id: query["lead_id"] = lead_id
    if company_id: query["company_id"] = company_id
    rows = list(notes_col.find(query, {"_id": 0}).sort("created_at", DESCENDING).limit(200))
    return {"notes": rows}


# ─── Overview metrics ───────────────────────────────────────────────────────
@router.get("/overview")
async def overview(current_user: dict = Depends(get_current_user)):
    tf = _tf(current_user)
    total = leads_col.count_documents(tf)
    warm = leads_col.count_documents({**tf, "stage": "warm"})
    hot = leads_col.count_documents({**tf, "stage": "hot"})
    engaged = leads_col.count_documents({**tf, "stage": {"$in": ["engaged", "session_pilot"]}})
    accounts_total = companies_col.count_documents(tf)
    accounts_pause = companies_col.count_documents({**tf, "pause_required": True})
    sessions = events_col.count_documents({**tf, "event_type": "calendly.session_booked"})
    newsletter_subs = events_col.count_documents({**tf, "event_type": "newsletter.subscribed"})
    magnet_claims = events_col.count_documents({**tf, "event_type": {"$in": ["lead_magnet.downloaded", "lead_magnet.company_claim", "jsa.claimed"]}})
    positive_replies = events_col.count_documents({**tf, "event_type": {"$in": ["saleshandy.positive_reply", "lemlist.dm_positive_reply", "newsletter.positive_reply"]}})

    sh_int = integrations_col.find_one({**tf, "name": "saleshandy"}, {"_id": 0})
    ll_int = integrations_col.find_one({**tf, "name": "lemlist"}, {"_id": 0})

    last_event = events_col.find_one(tf, {"_id": 0, "created_at": 1}, sort=[("created_at", DESCENDING)])

    # Per-platform activity totals
    sh_events = events_col.count_documents({**tf, "source": "saleshandy"})
    ll_events = events_col.count_documents({**tf, "source": "lemlist"})
    sh_leads = leads_col.count_documents({**tf, "source": "saleshandy"})
    ll_leads = leads_col.count_documents({**tf, "source": "lemlist"})
    john_owned = leads_col.count_documents({**tf, "owner": "John"})

    return {
        "metrics": {
            "total_engaged_leads": total,
            "warm_leads": warm,
            "hot_leads": hot,
            "engaged_accounts": engaged,
            "engaged_accounts_total": companies_col.count_documents({**tf, "account_stage": {"$in": ["warm", "hot", "engaged", "session_pilot"]}}),
            "accounts_total": accounts_total,
            "sessions_booked": sessions,
            "accounts_requiring_pause": accounts_pause,
            "good_slice_subscribers": newsletter_subs,
            "lead_magnet_claims": magnet_claims,
            "positive_replies": positive_replies,
            # Saleshandy + Lemlist focus (primary platforms)
            "saleshandy_leads": sh_leads,
            "lemlist_leads": ll_leads,
            "saleshandy_events": sh_events,
            "lemlist_events": ll_events,
            "email_opens": events_col.count_documents({**tf, "event_type": "saleshandy.email_opened"}),
            "email_clicks": events_col.count_documents({**tf, "event_type": "saleshandy.email_clicked"}),
            "saleshandy_positive_replies": events_col.count_documents({**tf, "event_type": "saleshandy.positive_reply"}),
            "linkedin_connections": events_col.count_documents({**tf, "event_type": "lemlist.connection_accepted"}),
            "lemlist_dm_replies": events_col.count_documents({**tf, "event_type": "lemlist.dm_positive_reply"}),
            "john_owned_conversations": john_owned,
        },
        "connections": {
            "saleshandy_connected": bool(sh_int and sh_int.get("status") == "connected"),
            "lemlist_connected":   bool(ll_int and ll_int.get("status") == "connected"),
        },
        "last_updated_at": (last_event or {}).get("created_at"),
        "is_empty": total == 0,
    }


# ─── Reports endpoints ──────────────────────────────────────────────────────
@router.get("/reports/weekly")
async def weekly_report(current_user: dict = Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    week_ago = (now - timedelta(days=7)).isoformat()
    tf = _tf(current_user)
    def _count(qfilter):
        return events_col.count_documents({**tf, **qfilter, "created_at": {"$gte": week_ago}})
    return {
        "window": "last_7_days",
        "from": week_ago,
        "metrics": {
            "saleshandy_opens":            _count({"event_type": "saleshandy.email_opened"}),
            "saleshandy_clicks":           _count({"event_type": "saleshandy.email_clicked"}),
            "saleshandy_positive_replies": _count({"event_type": "saleshandy.positive_reply"}),
            "lemlist_connections":         _count({"event_type": "lemlist.connection_accepted"}),
            "lemlist_dm_positive":         _count({"event_type": "lemlist.dm_positive_reply"}),
            "lead_magnet_claims":          _count({"event_type": {"$in": ["lead_magnet.downloaded", "lead_magnet.company_claim"]}}),
            "jsa_claims":                  _count({"event_type": "jsa.claimed"}),
            "good_slice_subscribers":      _count({"event_type": "newsletter.subscribed"}),
            "hot_leads_created":           leads_col.count_documents({**tf, "stage": "hot", "updated_at": {"$gte": week_ago}}),
            "engaged_accounts":            companies_col.count_documents({**tf, "account_stage": {"$in": ["engaged", "session_pilot"]}, "updated_at": {"$gte": week_ago}}),
            "sessions_booked":             _count({"event_type": "calendly.session_booked"}),
            "accounts_paused":             companies_col.count_documents({**tf, "pause_required": True, "updated_at": {"$gte": week_ago}}),
            "dnc_unsubscribed":            _count({"event_type": "manual.dnc"}),
        },
    }


@router.get("/reports/monthly")
async def monthly_report(current_user: dict = Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    month_ago = (now - timedelta(days=30)).isoformat()
    tf = _tf(current_user)
    # Channel-wise performance (events grouped by source within window)
    channel = list(events_col.aggregate([
        {"$match": {**tf, "created_at": {"$gte": month_ago}}},
        {"$group": {"_id": "$source", "events": {"$sum": 1}, "score_total": {"$sum": "$score_change"}}},
        {"$sort": {"score_total": -1}},
    ]))
    # Title-wise + Industry-wise (look up lead title/industry from events)
    title_pipeline = [
        {"$match": {**tf, "created_at": {"$gte": month_ago}}},
        {"$lookup": {"from": "pt_leads", "localField": "lead_id", "foreignField": "id", "as": "lead"}},
        {"$unwind": {"path": "$lead", "preserveNullAndEmptyArrays": True}},
        {"$group": {"_id": "$lead.title", "events": {"$sum": 1}}},
        {"$sort": {"events": -1}},
        {"$limit": 20},
    ]
    title_perf = list(events_col.aggregate(title_pipeline))
    industry_pipeline = [
        {"$match": {"created_at": {"$gte": month_ago}}},
        {"$lookup": {"from": "pt_leads", "localField": "lead_id", "foreignField": "id", "as": "lead"}},
        {"$unwind": {"path": "$lead", "preserveNullAndEmptyArrays": True}},
        {"$group": {"_id": "$lead.industry", "events": {"$sum": 1}}},
        {"$sort": {"events": -1}},
    ]
    industry_perf = list(events_col.aggregate(industry_pipeline))
    # Best touchpoint
    touchpoint = list(events_col.aggregate([
        {"$match": {"created_at": {"$gte": month_ago}}},
        {"$group": {"_id": "$event_type", "events": {"$sum": 1}, "score_total": {"$sum": "$score_change"}}},
        {"$sort": {"score_total": -1}},
        {"$limit": 1},
    ]))
    return {
        "window": "last_30_days",
        "from": month_ago,
        "channel_performance": [{"source": c["_id"], "events": c["events"], "score_total": c["score_total"]} for c in channel],
        "title_performance": [{"title": t["_id"] or "Unknown", "events": t["events"]} for t in title_perf],
        "industry_performance": [{"industry": i["_id"] or "Unknown", "events": i["events"]} for i in industry_perf],
        "best_touchpoint": ({"event_type": touchpoint[0]["_id"], "events": touchpoint[0]["events"]} if touchpoint else None),
        "accounts_to_john": companies_col.count_documents({"owner": "John", "updated_at": {"$gte": month_ago}}),
        "sessions_created": events_col.count_documents({"event_type": "calendly.session_booked", "created_at": {"$gte": month_ago}}),
        "pilot_conversations": companies_col.count_documents({"account_stage": "session_pilot", "updated_at": {"$gte": month_ago}}),
    }


# ─── Integrations endpoints ─────────────────────────────────────────────────
PRIMARY_INTEGRATIONS = ["saleshandy", "lemlist"]
FUTURE_INTEGRATIONS = [
    "calendly", "newsletter_platform", "lead_magnet_form",
    "pietential_website_forms", "ga4", "linkedin_pixel",
    "make_com", "n8n", "apollo", "apify", "the_boomernag",
]
DEFAULT_INTEGRATIONS = PRIMARY_INTEGRATIONS + FUTURE_INTEGRATIONS


@router.get("/integrations")
async def list_integrations(current_user: dict = Depends(get_current_user)):
    rows = list(integrations_col.find({}, {"_id": 0}))
    by_name = {r["name"]: r for r in rows}
    primary, future = [], []
    for name in DEFAULT_INTEGRATIONS:
        existing = by_name.get(name) or {}
        item = {
            "name": name,
            "status": existing.get("status", "not_connected"),
            "webhook_url": existing.get("webhook_url"),
            "webhook_secret_set": bool(existing.get("webhook_secret")),
            "api_key_masked": _mask_key(_dec(existing["api_key"])) if existing.get("api_key") else None,
            "last_sync_at": existing.get("last_sync_at"),
            "error_log": existing.get("error_log"),
            "tier": "primary" if name in PRIMARY_INTEGRATIONS else "future",
        }
        (primary if name in PRIMARY_INTEGRATIONS else future).append(item)
    return {"primary": primary, "future": future}


@router.post("/integrations")
async def upsert_integration(payload: IntegrationUpsert, current_user: dict = Depends(get_current_user)):
    _require_write(current_user)
    update = {"name": payload.name, "updated_at": _now_iso()}
    if payload.api_key is not None:
        # Encrypt at rest
        update["api_key"] = _enc(payload.api_key) if payload.api_key else ""
    if payload.webhook_url is not None:
        update["webhook_url"] = payload.webhook_url
    if payload.webhook_secret is not None:
        update["webhook_secret"] = payload.webhook_secret if payload.webhook_secret else None
    if payload.status is not None:
        update["status"] = payload.status
    integrations_col.update_one({"name": payload.name}, {"$set": update}, upsert=True)
    integ = integrations_col.find_one({"name": payload.name}, {"_id": 0})
    return {"integration": {
        "name": integ["name"],
        "status": integ.get("status", "not_connected"),
        "webhook_url": integ.get("webhook_url"),
        "webhook_secret_set": bool(integ.get("webhook_secret")),
        "api_key_masked": _mask_key(_dec(integ["api_key"])) if integ.get("api_key") else None,
        "last_sync_at": integ.get("last_sync_at"),
    }}


@router.post("/integrations/{name}/test")
async def test_integration(name: str, current_user: dict = Depends(get_current_user)):
    _require_write(current_user)
    integ = integrations_col.find_one({"name": name})
    if not integ or not (integ.get("api_key") or integ.get("webhook_url")):
        raise HTTPException(status_code=400, detail="No API key saved yet. Paste the key, click Update, then Test connection.")
    # iter82 — for Saleshandy + Lemlist do a REAL handshake against their API
    # so the founder finds out about invalid/expired keys immediately. For
    # other integrations (webhook-only) we still soft-mark as connected.
    decrypted_key = _dec(integ.get("api_key") or "") if integ.get("api_key") else ""
    handshake_done = False
    found = 0
    if name == "saleshandy" and decrypted_key:
        try:
            from routes.outreach_import import _saleshandy_list_sequences  # lazy import
            seqs = await _saleshandy_list_sequences(decrypted_key)
            found = len(seqs)
            handshake_done = True
        except HTTPException as e:
            integrations_col.update_one(
                {"name": name},
                {"$set": {"status": "needs_setup", "error_log": str(e.detail)[:240], "updated_at": _now_iso()}},
            )
            raise HTTPException(e.status_code, e.detail)
    elif name == "lemlist" and decrypted_key:
        try:
            from routes.outreach_import import _lemlist_list_campaigns  # lazy import
            camps = await _lemlist_list_campaigns(decrypted_key)
            found = len(camps)
            handshake_done = True
        except HTTPException as e:
            integrations_col.update_one(
                {"name": name},
                {"$set": {"status": "needs_setup", "error_log": str(e.detail)[:240], "updated_at": _now_iso()}},
            )
            raise HTTPException(e.status_code, e.detail)
    integrations_col.update_one(
        {"name": name},
        {"$set": {"last_sync_at": _now_iso(), "status": "connected", "error_log": None}},
    )
    msg = (
        f"Connection verified — {found} {'sequences' if name == 'saleshandy' else 'campaigns'} reachable."
        if handshake_done else
        "Marked as connected. Live handshake for this integration is webhook-based; configure Make.com / n8n to hit the URLs above."
    )
    return {"ok": True, "tested_at": _now_iso(), "found": found, "handshake": handshake_done, "message": msg}


# ─── Webhook endpoints — single dispatcher with optional signature check ───
def _check_webhook_secret(integration_name: str, provided: Optional[str]):
    """If a webhook_secret is set on the integration, the inbound POST must
    include it via X-Pt-Webhook-Secret header. If not configured, accept all
    (acceptable for client demo; required for prod)."""
    integ = integrations_col.find_one({"name": integration_name}, {"webhook_secret": 1})
    expected = (integ or {}).get("webhook_secret")
    if expected and not hmac.compare_digest(str(expected), str(provided or "")):
        raise HTTPException(status_code=401, detail="Invalid webhook secret")


def _webhook_event(event_type: str, integration_name: str):
    async def _handler(body: Dict[str, Any], x_pt_webhook_secret: Optional[str] = Header(default=None)):
        _check_webhook_secret(integration_name, x_pt_webhook_secret)
        email = body.get("email") or (body.get("prospect") or {}).get("email") or (body.get("lead") or {}).get("email")
        if not email:
            _log("webhook", f"{integration_name}: missing email in payload", "error", event_type=event_type)
            raise HTTPException(status_code=400, detail="Webhook payload missing 'email'")
        result = _ingest_event(
            event_type=event_type,
            lead_lookup={"email": email},
            metadata=body,
            current_user_email="webhook",
        )
        _log("webhook", f"{event_type} ingested for {email}", "info",
             event_type=event_type, email=email, score_after=result["lead"].get("score"), stage_after=result["lead"].get("stage"))
        return result
    return _handler


# Register all 13 webhook routes
WEBHOOK_MAP = {
    "/webhooks/saleshandy/open":              ("saleshandy.email_opened",        "saleshandy"),
    "/webhooks/saleshandy/click":             ("saleshandy.email_clicked",       "saleshandy"),
    "/webhooks/saleshandy/reply":             ("saleshandy.positive_reply",      "saleshandy"),
    "/webhooks/lemlist/connection-accepted":  ("lemlist.connection_accepted",    "lemlist"),
    "/webhooks/lemlist/dm-reply":             ("lemlist.dm_positive_reply",      "lemlist"),
    "/webhooks/newsletter/subscribe":         ("newsletter.subscribed",          "newsletter_platform"),
    "/webhooks/newsletter/open":              ("newsletter.opened",              "newsletter_platform"),
    "/webhooks/newsletter/click":             ("newsletter.clicked",             "newsletter_platform"),
    "/webhooks/lead-magnet/claim":            ("lead_magnet.downloaded",         "lead_magnet_form"),
    "/webhooks/job-satisfaction-analysis/claim":    ("jsa.claimed",              "lead_magnet_form"),
    "/webhooks/job-satisfaction-analysis/complete": ("jsa.completed",            "lead_magnet_form"),
    "/webhooks/calendly/booked":              ("calendly.session_booked",        "calendly"),
    "/webhooks/ga4/high-intent-page-visit":   ("website.pricing_visit",          "ga4"),
}

for path, (evt, integ_name) in WEBHOOK_MAP.items():
    router.add_api_route(path, _webhook_event(evt, integ_name), methods=["POST"], name=f"webhook_{evt}")


# ─── Scoring rules introspection ────────────────────────────────────────────
@router.get("/scoring-rules")
async def get_scoring_rules(current_user: dict = Depends(get_current_user)):
    return {
        "rules": [{"event_type": k, **v} for k, v in SCORING_RULES.items()],
        "stages": [
            {"id": "cold",            "label": "Cold",           "min": 0,    "max": 14,   "auto": "Sequences continue."},
            {"id": "warm",            "label": "Warm",           "min": 15,   "max": 34,   "auto": "Add to Good Slice."},
            {"id": "hot",             "label": "Hot",            "min": 35,   "max": 69,   "auto": "Pause & alert John."},
            {"id": "engaged",         "label": "Engaged",        "min": 70,   "max": 109,  "auto": "John owns."},
            {"id": "session_pilot",   "label": "Session/Pilot",  "min": 110,  "max": 9999, "auto": "Opportunity."},
        ],
        "decay": [
            {"trigger": "no_activity_30_days", "score_change": -10},
            {"trigger": "no_activity_60_days", "score_change": -20, "side_effect": "move_to_long_cycle_nurture"},
        ],
    }


# ─── CSV import (uploadfile flow as alternative to bulk JSON) ───────────────
@router.post("/leads/import-csv")
async def import_csv(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    _require_write(current_user)
    contents = await file.read()
    reader = csv.DictReader(io.StringIO(contents.decode("utf-8")))
    rows = [r for r in reader]
    return await bulk_leads(BulkLeadsPayload(leads=rows), current_user)


# ─── Per-platform activity (Saleshandy + Lemlist focus) ────────────────────
def _platform_activity(source: str, current_user: dict):
    """Build a per-lead summary of activity from a given source."""
    leads = list(leads_col.find({"source": source}, {"_id": 0}))
    # Also include any leads that have at least one event from this source
    extra_lead_ids = set()
    extra_cursor = events_col.aggregate([
        {"$match": {"source": source}},
        {"$group": {"_id": "$lead_id"}},
    ])
    for row in extra_cursor:
        if row["_id"]:
            extra_lead_ids.add(row["_id"])
    seen = {l["id"] for l in leads}
    extra_ids = [lid for lid in extra_lead_ids if lid not in seen]
    if extra_ids:
        leads.extend(list(leads_col.find({"id": {"$in": extra_ids}}, {"_id": 0})))

    rows = []
    for l in leads:
        evs = list(events_col.find({"lead_id": l["id"], "source": source}, {"_id": 0}).sort("created_at", DESCENDING))
        opens = sum(1 for e in evs if e["event_type"] in ("saleshandy.email_opened", "newsletter.opened"))
        clicks = sum(1 for e in evs if e["event_type"] in ("saleshandy.email_clicked", "newsletter.clicked", "lemlist.post_engagement"))
        replies = sum(1 for e in evs if "positive_reply" in e["event_type"] or "dm_positive_reply" in e["event_type"])
        connections = sum(1 for e in evs if e["event_type"] == "lemlist.connection_accepted")
        rows.append({
            **l,
            "events_count": len(evs),
            "opens": opens,
            "clicks": clicks,
            "replies": replies,
            "linkedin_connections": connections,
            "last_event_at": evs[0]["created_at"] if evs else None,
            "last_event_label": evs[0]["label"] if evs else None,
        })
    rows.sort(key=lambda r: r.get("score") or 0, reverse=True)
    return rows


@router.get("/saleshandy/activity")
async def saleshandy_activity(current_user: dict = Depends(get_current_user)):
    integ = integrations_col.find_one({"name": "saleshandy"}, {"_id": 0, "api_key": 0})
    return {
        "connected": bool(integ and integ.get("status") == "connected"),
        "last_sync_at": (integ or {}).get("last_sync_at"),
        "rows": _platform_activity("saleshandy", current_user),
    }


@router.get("/lemlist/activity")
async def lemlist_activity(current_user: dict = Depends(get_current_user)):
    integ = integrations_col.find_one({"name": "lemlist"}, {"_id": 0, "api_key": 0})
    return {
        "connected": bool(integ and integ.get("status") == "connected"),
        "last_sync_at": (integ or {}).get("last_sync_at"),
        "rows": _platform_activity("lemlist", current_user),
    }


# ─── Train Aria — reply classification + ICP feedback ──────────────────────
class TrainSignal(BaseModel):
    lead_id: str
    signal_type: str = Field(..., pattern="^(reply_class|icp_fit|positive_conversation)$")
    value: str  # "positive" | "neutral" | "negative" | "match" | "partial" | "outside" | "yes" | "no"
    note: Optional[str] = None


@router.post("/training/signal")
async def post_training_signal(payload: TrainSignal, current_user: dict = Depends(get_current_user)):
    _require_write(current_user)
    lead = leads_col.find_one({"id": payload.lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    doc = {
        "id": _new_id("pttr"),
        **payload.dict(),
        "company_id": lead.get("company_id"),
        "created_by": current_user["email"],
        "created_at": _now_iso(),
    }
    training_col.insert_one(doc)
    # Side effect: positive_conversation acts like a manual positive-reply event.
    # Idempotent — only fires once per (lead, value=yes).
    if payload.signal_type == "positive_conversation" and payload.value == "yes":
        already = training_col.count_documents({
            "lead_id": payload.lead_id,
            "signal_type": "positive_conversation",
            "value": "yes",
            "id": {"$ne": doc["id"]},
        })
        if not already:
            _ingest_event("manual.hypothesis_reply", {"lead_id": payload.lead_id}, {"trained": True}, current_user["email"])
    if payload.signal_type == "icp_fit":
        leads_col.update_one({"id": payload.lead_id}, {"$set": {"icp_fit": payload.value, "updated_at": _now_iso()}})
        if lead.get("company_id"):
            companies_col.update_one({"id": lead["company_id"]}, {"$set": {"icp_fit": payload.value, "updated_at": _now_iso()}})
    return {"signal": _strip_id(doc), "lead": leads_col.find_one({"id": payload.lead_id}, {"_id": 0})}


@router.get("/training/signals")
async def list_training_signals(lead_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {}
    if lead_id:
        query["lead_id"] = lead_id
    rows = list(training_col.find(query, {"_id": 0}).sort("created_at", DESCENDING).limit(200))
    return {"signals": rows}


# ─── Team / roles ───────────────────────────────────────────────────────────
PT_ROLES = ["admin", "content_vista", "pietential_owner", "viewer"]


@router.get("/team")
async def list_team(current_user: dict = Depends(get_current_user)):
    rows = list(users_collection.find({"is_active": True}, {"_id": 0, "password_hash": 0}).limit(200))
    return {"members": rows, "available_roles": PT_ROLES}


class RoleUpdate(BaseModel):
    email: EmailStr
    role: str


@router.patch("/team/role")
async def update_member_role(payload: RoleUpdate, current_user: dict = Depends(get_current_user)):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin only")
    if payload.role not in PT_ROLES + ["sales_rep"]:
        raise HTTPException(status_code=400, detail="Invalid role")
    res = users_collection.update_one({"email": payload.email}, {"$set": {"role": payload.role}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "ok"}


@router.get("/me/permissions")
async def my_permissions(current_user: dict = Depends(get_current_user)):
    """Frontend uses this to hide write buttons for viewer role."""
    return {
        "role": _role_of(current_user),
        "can_write": _can_write(current_user),
        "can_admin": _is_admin(current_user),
    }


# ─── Score decay job ────────────────────────────────────────────────────────
def _run_score_decay():
    """Apply −10 after 30 days of inactivity, −20 + nurture flag after 60 days."""
    now = datetime.now(timezone.utc)
    cutoff_30 = (now - timedelta(days=30)).isoformat()
    cutoff_60 = (now - timedelta(days=60)).isoformat()
    decayed_30, decayed_60 = 0, 0
    # 60-day decay — applied first so 30-day doesn't double-count it
    for l in leads_col.find({"last_activity_at": {"$lt": cutoff_60}, "score": {"$gt": 0}}, {"_id": 0, "id": 1, "score": 1, "company_id": 1}):
        new_score = max(-100, (l["score"] or 0) - 20)
        leads_col.update_one({"id": l["id"]}, {"$set": {"score": new_score, "stage": classify_stage(new_score), "automation_status": "long_cycle_nurture", "updated_at": now.isoformat(), "last_decay_at": now.isoformat()}})
        events_col.insert_one({"id": _new_id("pte"), "lead_id": l["id"], "company_id": l.get("company_id"), "event_type": "decay.60_days", "label": "60-day inactivity decay", "source": "system", "score_change": -20, "score_after": new_score, "stage_after": classify_stage(new_score), "metadata": {}, "created_by": "system", "created_at": now.isoformat()})
        if l.get("company_id"):
            _recompute_company(l["company_id"])
        decayed_60 += 1
    # 30-day decay
    for l in leads_col.find({"last_activity_at": {"$lt": cutoff_30, "$gte": cutoff_60}, "score": {"$gt": 0}}, {"_id": 0, "id": 1, "score": 1, "company_id": 1}):
        new_score = max(-100, (l["score"] or 0) - 10)
        leads_col.update_one({"id": l["id"]}, {"$set": {"score": new_score, "stage": classify_stage(new_score), "updated_at": now.isoformat(), "last_decay_at": now.isoformat()}})
        events_col.insert_one({"id": _new_id("pte"), "lead_id": l["id"], "company_id": l.get("company_id"), "event_type": "decay.30_days", "label": "30-day inactivity decay", "source": "system", "score_change": -10, "score_after": new_score, "stage_after": classify_stage(new_score), "metadata": {}, "created_by": "system", "created_at": now.isoformat()})
        if l.get("company_id"):
            _recompute_company(l["company_id"])
        decayed_30 += 1
    return {"decayed_30_days": decayed_30, "decayed_60_days": decayed_60, "ran_at": now.isoformat()}


@router.post("/score-decay/run")
async def run_score_decay(current_user: dict = Depends(get_current_user)):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin only")
    return _run_score_decay()


# ─── Replay demo flow (theatrical demo button) ─────────────────────────────
@router.post("/demo/replay")
async def replay_demo_flow(current_user: dict = Depends(get_current_user)):
    """Fires 4 webhook-equivalent events on a single demo lead with timing,
    so a client demo can see cold→warm→hot→engaged cascade play out live."""
    _require_write(current_user)
    demo_email = "demo-prospect@pietential-demo.com"
    # Create or reset the demo lead
    leads_col.delete_one({"email": demo_email})
    events_col.delete_many({"metadata.demo_replay": True})
    notes_col.delete_many({"lead_id": {"$exists": False}})
    seed = {
        "id": _new_id("ptl"),
        "first_name": "Alex",
        "last_name": "Patel",
        "email": demo_email,
        "company_name": "Wellbeing Demo Corp",
        "title": "VP People Analytics",
        "source": "saleshandy",
        "industry": "SaaS",
        "employee_count": 4200,
        "geography": "United States",
        "icp_fit": "match",
        "score": 0,
        "stage": "cold",
        "latest_signal": "Just added",
        "automation_status": "active",
        "owner": "Content Vista",
        "linkedin_url": "https://linkedin.com/in/demo",
        "last_activity_at": _now_iso(),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    company = _ensure_company(seed["company_name"], seed)
    seed["company_id"] = (company or {}).get("id")
    leads_col.insert_one(seed)

    # Apply 4 events — caller should poll /leads/{id} to see scores tick up
    sequence = [
        "newsletter.subscribed",        # +25 → warm
        "saleshandy.email_clicked",     # +10
        "saleshandy.positive_reply",    # +30 → hot, pause
        "calendly.session_booked",      # +80 → engaged
    ]
    for evt in sequence:
        _ingest_event(evt, {"lead_id": seed["id"]}, {"demo_replay": True}, current_user["email"])

    final = leads_col.find_one({"id": seed["id"]}, {"_id": 0})
    company = companies_col.find_one({"id": seed["company_id"]}, {"_id": 0}) if seed.get("company_id") else None
    return {
        "lead_id": seed["id"],
        "lead": final,
        "company": company,
        "events_applied": sequence,
        "tasks_created": tasks_col.count_documents({"lead_id": seed["id"], "status": "open"}),
    }


# ─── Touchpoint map (static metadata for Touchpoint Map page) ──────────────
TOUCHPOINT_MAP = [
    {"id": "linkedin_post_comment", "title": "Comments on John's LinkedIn post", "touches": "3 DMs", "timeline": "14 days", "fallback": "Good Slice invite", "platform": "Lemlist / manual", "aria_role": "Track comment, ICP fit, Lemlist flow, score, next action", "events": ["lemlist.connection_accepted", "lemlist.dm_positive_reply"]},
    {"id": "cold_email", "title": "Cold email", "touches": "3 emails", "timeline": "12 days", "fallback": "Good Slice invite", "platform": "Saleshandy", "aria_role": "Track opens/clicks/replies, score, pause alerts, John routing", "events": ["saleshandy.email_opened", "saleshandy.email_clicked", "saleshandy.positive_reply"]},
    {"id": "cold_linkedin_dm", "title": "Cold LinkedIn DM", "touches": "3–4 DMs", "timeline": "14 days", "fallback": "Good Slice invite", "platform": "Lemlist", "aria_role": "Track connection, DMs, replies, score, pause alerts", "events": ["lemlist.connection_accepted", "lemlist.dm_positive_reply", "lemlist.post_engagement"]},
    {"id": "good_slice_subscriber", "title": "Good Slice subscriber", "touches": "Biweekly issues", "timeline": "Ongoing", "fallback": "Session CTA every 3rd issue", "platform": "Newsletter / manual", "aria_role": "Track subscribe/open/click/reply, score, session intent", "events": ["newsletter.subscribed", "newsletter.opened", "newsletter.clicked", "newsletter.positive_reply"]},
    {"id": "company_page_magnet", "title": "Company page magnet claim", "touches": "3 follow-ups", "timeline": "10 days", "fallback": "Good Slice subscriber", "platform": "Manual / LinkedIn", "aria_role": "Track claim, PDF sent, ICP check, John task", "events": ["lead_magnet.company_claim"]},
    {"id": "magnet_landing_page", "title": "Magnet download landing page", "touches": "3 emails", "timeline": "10 days", "fallback": "Good Slice subscriber", "platform": "Form / manual", "aria_role": "Track download, ICP check, nurture, score", "events": ["lead_magnet.downloaded"]},
    {"id": "job_satisfaction_analysis", "title": "Job Satisfaction Analysis", "touches": "Claim, complete, results, follow-up", "timeline": "Immediate to 10 days", "fallback": "Good Slice subscriber", "platform": "Form / manual", "aria_role": "Track claim/completion/result/follow-up", "events": ["jsa.claimed", "jsa.completed"]},
    {"id": "existing_clickers", "title": "Existing clickers re-engagement", "touches": "Good Slice + value-first DM", "timeline": "Immediate to 14 days", "fallback": "Good Slice nurture", "platform": "CSV + Lemlist", "aria_role": "Track old engagement, reactivation, score", "events": ["lemlist.connection_accepted", "saleshandy.email_clicked"]},
    {"id": "website_high_intent", "title": "Website high-intent visit", "touches": "Personal follow-up if high score", "timeline": "Immediate", "fallback": "Continue nurture", "platform": "GA4 / future", "aria_role": "Track high intent, score, alert", "events": ["website.pricing_visit", "website.long_dwell"]},
    {"id": "hypothesis_email", "title": "Hypothesis email from John", "touches": "1–2 manual emails", "timeline": "Manual", "fallback": "Close or nurture", "platform": "John / manual", "aria_role": "Track John-owned account and final outcome", "events": ["manual.hypothesis_reply"]},
]


@router.get("/touchpoints")
async def get_touchpoint_map(current_user: dict = Depends(get_current_user)):
    # Live counts per touchpoint
    out = []
    for tp in TOUCHPOINT_MAP:
        live = events_col.count_documents({"event_type": {"$in": tp["events"]}})
        out.append({**tp, "live_event_count": live})
    return {"touchpoints": out}


# ─── Startup hook for hourly score-decay ───────────────────────────────────
async def _decay_loop():
    """Run score decay once an hour. Cheap query (indexed last_activity_at)."""
    while True:
        try:
            _run_score_decay()
        except Exception as e:
            print(f"[pt-decay] error: {e}")
        await asyncio.sleep(60 * 60)


def register_pietential_startup(app):
    """Called from server.py to wire the decay loop without import cycles."""
    @app.on_event("startup")
    async def _start_pt_decay_loop():
        asyncio.create_task(_decay_loop())
        print("[pt-decay] background loop started (hourly)")


# ─── Saleshandy CSV import (their export format) ───────────────────────────
def _truthy(s):
    if not s: return False
    return str(s).strip().lower() in ("yes", "true", "1", "y", "opened", "clicked", "replied", "sent", "accepted")


def _campaign_upsert(platform: str, name: str, external_id: Optional[str] = None) -> Optional[str]:
    if not name:
        return None
    norm = name.strip()
    existing = campaigns_col.find_one({"platform": platform, "campaign_name": norm})
    if existing:
        return existing["id"]
    cid = _new_id("ptcamp")
    campaigns_col.insert_one({
        "id": cid,
        "platform": platform,
        "campaign_name": norm,
        "external_campaign_id": external_id,
        "status": "active",
        "total_leads": 0,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    })
    return cid


def _bump_campaign(campaign_id: Optional[str]):
    if not campaign_id:
        return
    campaigns_col.update_one(
        {"id": campaign_id},
        {"$inc": {"total_leads": 1}, "$set": {"updated_at": _now_iso()}},
    )


@router.post("/saleshandy/import-csv")
async def import_saleshandy_csv(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """Saleshandy export CSV → leads + events.
    Recognised columns: First name, Last name, Email, Company, Title, Campaign,
    Touch number, Opened, Clicked, Replied, Reply sentiment, Unsubscribed, Last activity.
    """
    _require_write(current_user)
    text = (await file.read()).decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(text))
    created, updated, events_added, errors = 0, 0, 0, []
    for i, row in enumerate(reader):
        norm = {k.strip().lower().replace(" ", "_"): (v or "").strip() for k, v in row.items()}
        email = (norm.get("email") or "").lower()
        if not email or "@" not in email:
            errors.append({"row": i, "reason": "Invalid email"}); continue
        campaign_id = _campaign_upsert("saleshandy", norm.get("campaign") or norm.get("campaign_name") or "")
        # Upsert lead
        existing = leads_col.find_one({"email": email}, {"_id": 0})
        if not existing:
            doc = {
                "id": _new_id("ptl"),
                "first_name": norm.get("first_name") or norm.get("firstname") or "",
                "last_name": norm.get("last_name") or norm.get("lastname") or "",
                "email": email,
                "company_name": norm.get("company") or norm.get("company_name"),
                "title": norm.get("title"),
                "source": "saleshandy",
                "saleshandy_contact_id": norm.get("contact_id") or norm.get("id") or None,
                "score": 0,
                "stage": "cold",
                "automation_status": "active",
                "owner": "Content Vista",
                "last_activity_at": norm.get("last_activity") or _now_iso(),
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
                "saleshandy_campaign_id": campaign_id,
            }
            company = _ensure_company(doc.get("company_name"), doc)
            doc["company_id"] = (company or {}).get("id")
            leads_col.insert_one(doc)
            created += 1
            lead_id = doc["id"]
        else:
            leads_col.update_one({"email": email}, {"$set": {"saleshandy_campaign_id": campaign_id, "saleshandy_contact_id": norm.get("contact_id") or norm.get("id"), "updated_at": _now_iso()}})
            updated += 1
            lead_id = existing["id"]
        _bump_campaign(campaign_id)
        # Events
        if _truthy(norm.get("opened")):
            _ingest_event("saleshandy.email_opened", {"lead_id": lead_id}, {"sequence_id": campaign_id, "csv_import": True}, current_user["email"]); events_added += 1
        if _truthy(norm.get("clicked")):
            _ingest_event("saleshandy.email_clicked", {"lead_id": lead_id}, {"sequence_id": campaign_id, "csv_import": True}, current_user["email"]); events_added += 1
        sentiment = (norm.get("reply_sentiment") or "").lower()
        if _truthy(norm.get("replied")) and sentiment in ("positive", "interested", "yes"):
            _ingest_event("saleshandy.positive_reply", {"lead_id": lead_id}, {"sequence_id": campaign_id, "sentiment": sentiment, "csv_import": True}, current_user["email"]); events_added += 1
        if _truthy(norm.get("unsubscribed")):
            _ingest_event("manual.dnc", {"lead_id": lead_id}, {"reason": "saleshandy_unsubscribe", "csv_import": True}, current_user["email"]); events_added += 1
        # Always recompute company so saleshandy_active flag reflects "lead exists"
        # even when no engagement events fired this row.
        company_id = leads_col.find_one({"id": lead_id}, {"_id": 0, "company_id": 1}).get("company_id")
        if company_id:
            _recompute_company(company_id)
    _log("csv_import", f"Saleshandy CSV: {created} new + {updated} updated leads, {events_added} events", "info", created=created, updated=updated, events=events_added)
    return {"created": created, "updated": updated, "events_added": events_added, "errors": errors}


@router.post("/lemlist/import-csv")
async def import_lemlist_csv(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """Lemlist export CSV → leads + events.
    Recognised columns: First name, Last name, Email, Company, Title, LinkedIn URL,
    Campaign, Connection sent, Connection accepted, DM sent, Replied, Reply sentiment, Last activity.
    """
    _require_write(current_user)
    text = (await file.read()).decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(text))
    created, updated, events_added, errors = 0, 0, 0, []
    for i, row in enumerate(reader):
        norm = {k.strip().lower().replace(" ", "_"): (v or "").strip() for k, v in row.items()}
        email = (norm.get("email") or "").lower()
        if not email or "@" not in email:
            errors.append({"row": i, "reason": "Invalid email"}); continue
        campaign_id = _campaign_upsert("lemlist", norm.get("campaign") or norm.get("campaign_name") or "")
        existing = leads_col.find_one({"email": email}, {"_id": 0})
        if not existing:
            doc = {
                "id": _new_id("ptl"),
                "first_name": norm.get("first_name") or norm.get("firstname") or "",
                "last_name": norm.get("last_name") or norm.get("lastname") or "",
                "email": email,
                "company_name": norm.get("company") or norm.get("company_name"),
                "title": norm.get("title"),
                "linkedin_url": norm.get("linkedin_url") or norm.get("linkedin"),
                "source": "lemlist",
                "lemlist_contact_id": norm.get("contact_id") or norm.get("id") or None,
                "score": 0,
                "stage": "cold",
                "automation_status": "active",
                "owner": "Content Vista",
                "last_activity_at": norm.get("last_activity") or _now_iso(),
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
                "lemlist_campaign_id": campaign_id,
            }
            company = _ensure_company(doc.get("company_name"), doc)
            doc["company_id"] = (company or {}).get("id")
            leads_col.insert_one(doc)
            created += 1
            lead_id = doc["id"]
        else:
            leads_col.update_one({"email": email}, {"$set": {"lemlist_campaign_id": campaign_id, "lemlist_contact_id": norm.get("contact_id") or norm.get("id"), "updated_at": _now_iso()}})
            updated += 1
            lead_id = existing["id"]
        _bump_campaign(campaign_id)
        if _truthy(norm.get("connection_accepted")):
            _ingest_event("lemlist.connection_accepted", {"lead_id": lead_id}, {"campaign_id": campaign_id, "csv_import": True}, current_user["email"]); events_added += 1
        sentiment = (norm.get("reply_sentiment") or "").lower()
        if _truthy(norm.get("replied")) and sentiment in ("positive", "interested", "yes"):
            _ingest_event("lemlist.dm_positive_reply", {"lead_id": lead_id}, {"campaign_id": campaign_id, "sentiment": sentiment, "csv_import": True}, current_user["email"]); events_added += 1
        # Always recompute company so lemlist_active flag reflects "lead exists"
        company_id = leads_col.find_one({"id": lead_id}, {"_id": 0, "company_id": 1}).get("company_id")
        if company_id:
            _recompute_company(company_id)
    _log("csv_import", f"Lemlist CSV: {created} new + {updated} updated leads, {events_added} events", "info", created=created, updated=updated, events=events_added)
    return {"created": created, "updated": updated, "events_added": events_added, "errors": errors}


# ─── Campaigns ─────────────────────────────────────────────────────────────
@router.get("/campaigns")
async def list_campaigns(platform: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {}
    if platform:
        query["platform"] = platform
    rows = list(campaigns_col.find(query, {"_id": 0}).sort("updated_at", DESCENDING))
    # Live counts
    for r in rows:
        plat = r["platform"]
        cid = r["id"]
        # Count events from leads in this campaign
        field = "saleshandy_campaign_id" if plat == "saleshandy" else "lemlist_campaign_id"
        lead_ids = [l["id"] for l in leads_col.find({field: cid}, {"_id": 0, "id": 1})]
        r["lead_count"] = len(lead_ids)
        if lead_ids:
            r["opens"] = events_col.count_documents({"lead_id": {"$in": lead_ids}, "event_type": "saleshandy.email_opened"})
            r["clicks"] = events_col.count_documents({"lead_id": {"$in": lead_ids}, "event_type": "saleshandy.email_clicked"})
            r["replies_pos"] = events_col.count_documents({"lead_id": {"$in": lead_ids}, "event_type": {"$in": ["saleshandy.positive_reply", "lemlist.dm_positive_reply"]}})
            r["connections"] = events_col.count_documents({"lead_id": {"$in": lead_ids}, "event_type": "lemlist.connection_accepted"})
        else:
            r["opens"] = r["clicks"] = r["replies_pos"] = r["connections"] = 0
    return {"campaigns": rows}


# ─── Automation Logs ───────────────────────────────────────────────────────
@router.get("/logs")
async def list_logs(kind: Optional[str] = None, level: Optional[str] = None, limit: int = 200, current_user: dict = Depends(get_current_user)):
    query = {}
    if kind: query["kind"] = kind
    if level: query["level"] = level
    rows = list(logs_col.find(query, {"_id": 0}).sort("created_at", DESCENDING).limit(min(limit, 500)))
    counts = {
        "total": logs_col.count_documents({}),
        "by_kind": {k: logs_col.count_documents({"kind": k}) for k in ("webhook", "sync", "decay", "csv_import", "rule")},
        "errors": logs_col.count_documents({"level": "error"}),
    }
    return {"logs": rows, "counts": counts}


# ─── Manual sync (stub — returns log entry for now; per-platform live sync
# will replace the inner block when API access is provisioned) ──────────────
@router.post("/integrations/{name}/sync")
async def sync_integration(name: str, current_user: dict = Depends(get_current_user)):
    _require_write(current_user)
    integ = integrations_col.find_one({"name": name})
    if not integ:
        raise HTTPException(status_code=404, detail="Integration not configured")
    if not integ.get("api_key"):
        _log("sync", f"{name}: manual sync attempted without API key", "warn")
        raise HTTPException(status_code=400, detail="API key not set — paste it under the integration first")
    # Per-platform implementation will go here when API access is provisioned.
    integrations_col.update_one({"name": name}, {"$set": {"last_sync_at": _now_iso(), "status": "connected"}})
    _log("sync", f"{name}: manual sync triggered (CSV-import-equivalent stub for demo)", "info")
    return {
        "ok": True,
        "synced_at": _now_iso(),
        "message": f"Sync queued for {name}. Live API polling will activate once {name} API access is fully wired — meanwhile use CSV import for guaranteed data.",
    }


# ─── Field mapping per integration ─────────────────────────────────────────
class FieldMappingUpdate(BaseModel):
    name: str
    mapping: Dict[str, str]  # source field → internal lead field


@router.get("/integrations/{name}/mapping")
async def get_field_mapping(name: str, current_user: dict = Depends(get_current_user)):
    integ = integrations_col.find_one({"name": name}, {"_id": 0, "field_mapping": 1})
    return {"mapping": (integ or {}).get("field_mapping") or {}}


@router.post("/integrations/mapping")
async def update_field_mapping(payload: FieldMappingUpdate, current_user: dict = Depends(get_current_user)):
    _require_write(current_user)
    integrations_col.update_one(
        {"name": payload.name},
        {"$set": {"field_mapping": payload.mapping, "updated_at": _now_iso()}},
        upsert=True,
    )
    return {"ok": True, "mapping": payload.mapping}


# ─── Public helpers used by external webhook receivers (integrations_hub) ───
class LeadEvent(BaseModel):
    """Minimal event payload accepted by the internal log_event helper."""
    lead_email: str
    event_type: str
    payload: Dict[str, Any] = {}


async def log_event_internal(tenant_id: str, event: "LeadEvent") -> dict:
    """Fire a scoring event from a server-side caller (e.g. an inbound webhook
    handler that already validated its signature). Never raises — failures
    are caught and returned so the caller's main flow isn't blocked.
    """
    # `_ingest_event` performs the scoring + cascade + task creation.
    # It accepts arbitrary metadata; we stuff the raw provider payload in
    # so analytics/debug surfaces can replay it later.
    try:
        return _ingest_event(
            event_type=event.event_type,
            lead_lookup={"email": event.lead_email},
            metadata={"raw": event.payload, "tenant_id": tenant_id, "via": "webhook"},
            current_user_email="webhook",
        )
    except HTTPException as e:
        # Unknown event types are common (we accept a wide range from providers)
        # — log and shrug instead of bubbling a 400 to the upstream webhook.
        return {"ok": False, "error": e.detail}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

