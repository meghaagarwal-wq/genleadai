from fastapi import FastAPI, HTTPException, Depends, status, Query, UploadFile, File, BackgroundTasks, Response, Header, Form, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, FileResponse
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient, ASCENDING, DESCENDING
from bson import ObjectId
import os
import uuid
import json
from dotenv import load_dotenv
from jose import JWTError, jwt
from passlib.context import CryptContext
import csv
import io
import asyncio
import resend
from aria_agent import (
    run_aria_agent, get_calendly_event_types, get_calendly_availability,
    create_scheduling_link, get_calendly_user, init_storage, put_object, get_object
)

# Shared dependencies (DB, collections, auth utilities)
from deps import (
    mongo_client, db,
    leads_collection, activities_collection, campaigns_collection, users_collection,
    pipelines_collection, aria_conversations_collection, workspace_assets_collection,
    aria_settings_collection,
    pwd_context, security,
    JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES,
    verify_password, get_password_hash, create_access_token, get_current_user,
    serialize_doc,
)
# Modular routers — registered via routes/__init__.py blueprint aggregator (iter91)
from routes import register_all_routes
# Non-router symbols still needed in server.py (background loops, helpers, startup hooks)
from routes.pietential import register_pietential_startup
from routes.touchpoint_engine import (
    engine_loop, instantiate_for_lead, pause_lead, cancel_lead,
)
from routes.compliance import is_stop_keyword, opt_out_phone, auto_opt_in_on_inbound
from routes.classification import classify_inbound
from routes.crm_sync import fire_event as crm_fire_event, crm_sync_loop
from routes.audit_log import audit_write
from routes.integrations_hub import fire_lifecycle_event
from routes.outreach import outreach_engine_loop, handle_inbound_reply as outreach_handle_reply
from routes.retention import retention_loop
from routes.health_engine import (
    stale_lead_loop as health_stale_loop,
    classify_sentiment as health_classify_sentiment,
)
from routes.pt_insights import b2b_insight_scan_loop  # iter97 — daily B2B Insights cron
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from security.limiter import limiter  # iter80 — shared instance for route modules
from security.helpers import safe_filter_value, safe_query_param  # iter80 — S9.5 NoSQL guards
import re as _re_s95  # iter80 — S9.5: escape user input in $regex queries

load_dotenv()

app = FastAPI(title="GenLeadAI LMS API")

# CORS — restricted to known frontend origins. Wildcard removed per iter105 P1 fix.
_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
if not _cors_origins:
    # Fail-safe: if env is missing, allow nothing (deploy must set it).
    _cors_origins = []
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register modular routers — single entry point (iter91 — blueprint aggregator)
register_all_routes(app)

# Rate limiter — applied to sensitive auth & webhook endpoints
limiter = limiter  # imported shared instance
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Iter79 — S9.5: short, safe Pydantic validation errors (drop the noisy array).
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402


@app.exception_handler(RequestValidationError)
async def _safe_validation_handler(request, exc: RequestValidationError):
    """Return a single human-readable string instead of the raw Pydantic
    error array (which leaks model structure + value types)."""
    msgs: list[str] = []
    for e in exc.errors():
        loc = ".".join(str(x) for x in (e.get("loc") or []) if x not in ("body", "query"))
        msg = e.get("msg", "invalid")
        msgs.append(f"{loc}: {msg}" if loc else msg)
    detail = "; ".join(msgs)[:300] or "Invalid request payload"
    return JSONResponse(status_code=422, content={"detail": detail})


register_pietential_startup(app)


@app.on_event("startup")
def _auto_migrate_multi_tenant():
    """Idempotently ensure tenants/memberships/onboarding_config exist + backfill
    tenant_id on legacy collections. Safe to run on every boot.

    Critical for production deploys: without this, existing users (like the
    admin demo account) would have no tenant membership and every request
    would 403 with 'No tenant assigned'.
    """
    try:
        # Local import to avoid circular imports at module load time
        from scripts.migrate_to_multi_tenant import main as run_migration
        run_migration()
    except Exception as e:
        # Never block app startup on a migration error — log and move on.
        print(f"[Startup] Multi-tenant migration skipped due to error: {e}")
    # Iter105 — P0 fix: ensure secondary performance indexes exist.
    try:
        from scripts.create_perf_indexes import main as run_indexes
        result = run_indexes()
        print(f"[Startup] perf indexes: created={len(result['created'])} skipped={len(result['skipped'])} errors={len(result['errors'])}")
    except Exception as e:
        print(f"[Startup] perf indexes skipped due to error: {e}")

    # iter102 — encrypt any plaintext integration secrets on disk. Idempotent.
    try:
        from scripts.encrypt_integration_configs import run as run_enc_mig
        summary = run_enc_mig()
        if summary["fields_encrypted"] > 0:
            print(f"[Startup] Encrypted {summary['fields_encrypted']} integration secret(s) across {summary['docs_touched']} doc(s)")
    except Exception as e:
        print(f"[Startup] integration-config encryption migration skipped: {e}")

    # iter156 — bootstrap the GenLeadAI Demo workspace on every cold boot so
    # production environments have rich demo data ready for sales calls. The
    # seeder is idempotent (deletes its own previously-tagged rows before
    # re-inserting). Re-run also when the seed is stale (>24h old) so demo
    # timestamps stay relative to "now" — important for KPIs like "leads
    # today" and "bookings this week" that filter by date.
    try:
        from datetime import datetime, timezone, timedelta as _td
        from deps import db as _db
        demo_tenant = _db["tenants"].find_one({"id": "ten_demo"})
        if not demo_tenant:
            print("[Startup] iter154 demo seed skipped — ten_demo tenant not present yet")
        else:
            newest = _db["pt_leads"].find_one(
                {"tenant_id": "ten_demo", "_seed_source": "demo_seed_v154"},
                sort=[("_seed_run_at", -1)],
            )
            existing_count = _db["pt_leads"].count_documents({
                "tenant_id": "ten_demo", "_seed_source": "demo_seed_v154",
            })
            # Re-seed when the demo's last run rolled into a prior UTC day —
            # keeps KPIs like leads_today / bookings_week aligned with the
            # system clock for every cold boot.
            now_utc = datetime.now(timezone.utc)
            today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
            stale = True
            if newest and newest.get("_seed_run_at"):
                try:
                    last = datetime.fromisoformat(newest["_seed_run_at"].replace("Z", "+00:00"))
                    stale = last < today_start
                except Exception:
                    stale = True
            if existing_count >= 10 and not stale:
                print(f"[Startup] iter154 demo seed fresh ({existing_count} leads) — skipping refresh")
            else:
                from scripts.iter154_seed_demo_dashboards import main as run_demo_seed
                run_demo_seed()
                print(f"[Startup] iter154 demo seed: bootstrapped ten_demo "
                      f"(existing={existing_count}, stale={stale})")
    except Exception as e:  # noqa: BLE001 — never block boot
        print(f"[Startup] iter154 demo seed skipped due to error: {e}")

# Resend Email
resend.api_key = os.getenv("RESEND_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "onboarding@resend.dev")

# Pydantic Models
class LeadCreate(BaseModel):
    lead_type: str
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = None
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    industry: Optional[str] = None
    revenue_range: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    source_channel: str
    campaign_id: Optional[str] = None
    status: str = "new"
    notes: Optional[str] = None
    tags: List[str] = []
    custom_fields: Dict[str, Any] = {}

class LeadUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    industry: Optional[str] = None
    revenue_range: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    source_channel: Optional[str] = None
    campaign_id: Optional[str] = None
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    custom_fields: Optional[Dict[str, Any]] = None
    next_followup_at: Optional[str] = None

class ActivityCreate(BaseModel):
    lead_id: str
    activity_type: str
    subject: Optional[str] = None
    body: Optional[str] = None
    outcome: Optional[str] = None
    duration_minutes: Optional[int] = None
    metadata: Dict[str, Any] = {}

class CampaignCreate(BaseModel):
    # Kept for any legacy references; real schema lives in routes/campaigns.py
    pass


class AIScoreRequest(BaseModel):
    lead_id: str


class AIEmailGenerateRequest(BaseModel):
    lead_id: str
    goal: str
    tone: str = "professional"
    length: str = "medium"


class AIChatRequest(BaseModel):
    query: str

# Helper Functions (verify_password, get_password_hash, create_access_token,
# get_current_user, serialize_doc) now live in deps.py and are imported at top.
# Auth endpoints live in routes/auth.py.

# Lead Endpoints
@app.post("/api/leads")
async def create_lead(lead: LeadCreate, current_user: dict = Depends(get_current_user)):
    lead_doc = lead.dict()
    lead_doc["created_at"] = datetime.now(timezone.utc).isoformat()
    lead_doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    lead_doc["created_by"] = current_user["email"]
    lead_doc["tenant_id"] = current_user.get("tenant_id")
    lead_doc["icp_score"] = 0
    lead_doc["icp_tier"] = "cold"
    lead_doc["assigned_to"] = None
    lead_doc["last_contacted_at"] = None
    lead_doc["next_followup_at"] = None
    
    # Pre-compute ObjectId so we can stamp `id` (string) in the same insert.
    # Downstream modules (compliance, touchpoint engine, classification) look
    # up leads by the `id` field — without this they would 404.
    new_id = ObjectId()
    lead_doc["_id"] = new_id
    lead_doc["id"] = str(new_id)
    leads_collection.insert_one(lead_doc)
    lead_doc = serialize_doc(lead_doc)

    # Instantiate touchpoint journey for this lead (Phase B engine)
    try:
        tenant_id = lead_doc.get("tenant_id") or (current_user or {}).get("tenant_id")
        if tenant_id:
            instantiate_for_lead(tenant_id, lead_doc)
    except Exception as e:
        print(f"[lead-create] touchpoint instantiate failed: {e}")

    # CRM sync: fire lead.created
    try:
        if lead_doc.get("tenant_id"):
            crm_fire_event(lead_doc["tenant_id"], lead_doc, "lead.created", {"source": "manual"})
    except Exception as e:
        print(f"[lead-create] crm fire failed: {e}")

    return lead_doc

class BulkLeadsPayload(BaseModel):
    leads: List[LeadCreate]

@app.post("/api/leads/bulk")
async def bulk_create_leads(payload: BulkLeadsPayload, current_user: dict = Depends(get_current_user)):
    """Create many leads at once (CSV upload). Tolerates per-row failures."""
    if not payload.leads:
        return {"created": 0, "failed": 0, "errors": [], "leads": []}
    if len(payload.leads) > 5000:
        raise HTTPException(status_code=400, detail="Maximum 5000 leads per upload")

    now_iso = datetime.now(timezone.utc).isoformat()
    docs = []
    seen_emails = set()
    errors = []
    for idx, l in enumerate(payload.leads):
        try:
            email_lc = (l.email or "").lower().strip()
            if email_lc in seen_emails:
                errors.append({"row": idx + 1, "email": l.email, "error": "Duplicate email in upload"})
                continue
            seen_emails.add(email_lc)
            doc = l.dict()
            doc["created_at"] = now_iso
            doc["updated_at"] = now_iso
            doc["created_by"] = current_user["email"]
            doc["tenant_id"] = current_user.get("tenant_id")
            doc["icp_score"] = 0
            doc["icp_tier"] = "cold"
            doc["assigned_to"] = None
            doc["last_contacted_at"] = None
            doc["next_followup_at"] = None
            docs.append(doc)
        except Exception as ex:
            errors.append({"row": idx + 1, "email": getattr(l, "email", None), "error": str(ex)})

    created = 0
    inserted_docs = []
    if docs:
        try:
            res = leads_collection.insert_many(docs, ordered=False)
            created = len(res.inserted_ids)
            inserted_docs = [serialize_doc(d) for d in docs]
        except Exception as ex:
            # Some succeeded, some failed (e.g. duplicate key)
            details = getattr(ex, "details", {}) or {}
            write_errors = details.get("writeErrors", []) if isinstance(details, dict) else []
            created = len(docs) - len(write_errors)
            inserted_docs = [serialize_doc(d) for d in docs]
            for we in write_errors:
                errors.append({
                    "row": (we.get("index") or 0) + 1,
                    "email": (docs[we.get("index", 0)].get("email") if we.get("index") is not None and we.get("index") < len(docs) else None),
                    "error": we.get("errmsg", "Insert failed"),
                })

    return {
        "created": created,
        "failed": len(errors),
        "errors": errors[:50],
        "leads": inserted_docs[:200],
    }

@app.get("/api/leads")
async def get_leads(
    skip: int = 0,
    limit: int = 50,
    lead_type: Optional[str] = None,
    status: Optional[str] = None,
    source_channel: Optional[str] = None,
    icp_tier: Optional[str] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    # Tenant isolation — never return another tenant's leads
    query = {"tenant_id": current_user.get("tenant_id")}
    if lead_type:
        query["lead_type"] = lead_type
    if status:
        query["status"] = status
    if source_channel:
        query["source_channel"] = source_channel
    if icp_tier:
        query["icp_tier"] = icp_tier
    if search:
        # iter80 — S9.5: escape regex metacharacters to prevent ReDoS / injection
        _safe = _re_s95.escape(safe_query_param(search, max_len=120))
        query["$or"] = [
            {"first_name": {"$regex": _safe, "$options": "i"}},
            {"last_name": {"$regex": _safe, "$options": "i"}},
            {"email": {"$regex": _safe, "$options": "i"}},
            {"company_name": {"$regex": _safe, "$options": "i"}}
        ]
    
    total = leads_collection.count_documents(query)
    leads = list(leads_collection.find(query).sort("created_at", DESCENDING).skip(skip).limit(limit))
    leads = [serialize_doc(lead) for lead in leads]
    
    return {"leads": leads, "total": total, "skip": skip, "limit": limit}

# Specific lead routes MUST come before {lead_id} parameter route
@app.get("/api/leads/your-five-today")
async def get_your_five_today_route(current_user: dict = Depends(get_current_user)):
    """Redirect to the actual handler below."""
    # This is a forwarding stub — actual logic is in the handler at the bottom of the file
    # SEC-002 fix (iter168) — scope query to caller's tenant to prevent
    # cross-tenant PII leak. Prior code returned ALL tenants' leads.
    _tenant_id = current_user.get("tenant_id")
    excluded = ["won", "lost", "do_not_contact"]
    candidates = list(leads_collection.find(
        {"status": {"$nin": excluded}, "tenant_id": _tenant_id},
        {
            "_id": 1, "first_name": 1, "last_name": 1, "email": 1, "phone": 1,
            "company_name": 1, "status": 1, "icp_score": 1, "source_channel": 1,
            "last_contacted_at": 1, "created_at": 1, "aria_state": 1,
            "intent_score_boost": 1, "no_show_count": 1, "deal_value": 1,
            "tags": 1, "lost_reason": 1,
        }
    ).limit(200))
    if not candidates:
        return {"leads": [], "message": "No active leads found"}
    scored = []
    now = datetime.now(timezone.utc)
    for lead in candidates:
        lead = serialize_doc(lead)
        score = 0
        reasons = []
        icp = lead.get("icp_score", 0)
        score += icp * 0.3
        if icp >= 70:
            reasons.append(f"High ICP score ({icp}) — strong fit for your services")
        last_contact = lead.get("last_contacted_at")
        days_since = 999
        if last_contact:
            try:
                lc = datetime.fromisoformat(last_contact.replace("Z", "+00:00"))
                days_since = (now - lc).days
            except:
                days_since = 30
        else:
            reasons.append("Never been contacted — fresh opportunity")
        score += min(days_since * 1.5, 30) * 0.2 / 30 * 100
        intent_boost = lead.get("intent_score_boost", 0)
        if intent_boost > 0:
            score += 25
            reasons.append("Showed recent intent signals")
        aria_state = lead.get("aria_state")
        if aria_state == "ESCALATED_TO_HUMAN":
            score += 15
            reasons.append("ARIA escalated — lead asked for a human")
        elif aria_state == "CONVERSATION_ACTIVE":
            score += 10
            reasons.append("Active ARIA conversation — warm and engaged")
        no_shows = lead.get("no_show_count", 0)
        if no_shows > 0:
            score += 10
            reasons.append(f"No-showed {no_shows} time(s) — recovery needed")
        if not reasons:
            reasons.append(f"ICP score {icp} — worth a personal touch" if days_since <= 7 else f"No contact in {days_since} days — time to re-engage")
        lead["_rank_score"] = score
        lead["_reason"] = reasons[0]
        lead["_all_reasons"] = reasons
        lead["_days_since_contact"] = days_since
        if aria_state == "ESCALATED_TO_HUMAN":
            lead["_suggested_action"] = {"type": "call", "label": "Call them", "reason": "They asked for a human"}
        elif days_since > 14:
            lead["_suggested_action"] = {"type": "email", "label": "Send check-in", "reason": "Re-open with value"}
        elif icp >= 70:
            lead["_suggested_action"] = {"type": "call", "label": "Book a call", "reason": "High-fit lead"}
        else:
            lead["_suggested_action"] = {"type": "whatsapp", "label": "WhatsApp", "reason": "Quick personal touch"}
        scored.append(lead)
    scored.sort(key=lambda x: x["_rank_score"], reverse=True)
    return {"leads": scored[:5], "generated_at": now.isoformat()}

@app.get("/api/leads/sleeping")
async def get_sleeping_leads(
    threshold_days: int = 14,
    tier: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get leads with no activity beyond threshold days.

    iter168 — this handler MUST be registered before @app.get('/api/leads/{lead_id}')
    otherwise FastAPI matches 'sleeping' as a lead_id parameter and returns 404.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=threshold_days)).isoformat()
    query = {
        "tenant_id": current_user.get("tenant_id"),
        "status": {"$nin": ["won", "lost", "do_not_contact"]},
        "$or": [
            {"last_contacted_at": {"$lt": cutoff}},
            {"last_contacted_at": None},
            {"last_contacted_at": {"$exists": False}},
        ]
    }
    leads = list(leads_collection.find(query).sort("icp_score", DESCENDING).limit(200))
    leads = [serialize_doc(l) for l in leads]
    now = datetime.now(timezone.utc)
    for lead in leads:
        lc = lead.get("last_contacted_at")
        if lc:
            try:
                days = (now - datetime.fromisoformat(lc.replace("Z", "+00:00"))).days
            except Exception:
                days = 30
        else:
            try:
                days = (now - datetime.fromisoformat(lead.get("created_at", now.isoformat()).replace("Z", "+00:00"))).days
            except Exception:
                days = 30
        lead["_days_asleep"] = days
        lead["_segment"] = "cold_vault" if days >= 60 else ("at_risk" if days >= 30 else "sleeping")
    sleeping = len([l for l in leads if l["_segment"] == "sleeping"])
    at_risk = len([l for l in leads if l["_segment"] == "at_risk"])
    cold_vault = len([l for l in leads if l["_segment"] == "cold_vault"])
    return {"leads": leads, "total": len(leads), "segments": {"sleeping": sleeping, "at_risk": at_risk, "cold_vault": cold_vault}}


@app.get("/api/leads/{lead_id}")
async def get_lead(lead_id: str, current_user: dict = Depends(get_current_user)):
    # Try ObjectId lookup first (legacy CRM leads). If lead_id isn't a valid
    # ObjectId (e.g. it's a pt_leads UUID), fall through to a 404 so the
    # frontend can transparently try /api/pt/leads/{id} as a second hop.
    try:
        oid = ObjectId(lead_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead = leads_collection.find_one({"_id": oid, "tenant_id": current_user.get("tenant_id")})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return serialize_doc(lead)

@app.patch("/api/leads/{lead_id}")
async def update_lead(lead_id: str, lead_update: LeadUpdate, current_user: dict = Depends(get_current_user)):
    try:
        # Use exclude_unset so callers can explicitly null fields (e.g. clear next_followup_at on follow-up complete)
        update_data = lead_update.dict(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        # Tenant isolation: update only matches if lead belongs to caller's tenant
        result = leads_collection.update_one(
            {"_id": ObjectId(lead_id), "tenant_id": current_user.get("tenant_id")},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        # Log status change activity
        if "status" in update_data:
            activity_doc = {
                "lead_id": lead_id,
                "user_id": current_user["email"],
                "activity_type": "status_changed",
                "subject": f"Status changed to {update_data['status']}",
                "body": None,
                "outcome": None,
                "duration_minutes": None,
                "metadata": {"new_status": update_data["status"]},
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            activities_collection.insert_one(activity_doc)

        # Cancel pending touchpoints when stage becomes terminal (Closed Won / Closed Lost)
        new_status = update_data.get("status")
        if new_status and isinstance(new_status, str) and new_status.lower().startswith("closed"):
            try:
                lead_for_id = leads_collection.find_one({"_id": ObjectId(lead_id)}, {"_id": 0, "id": 1})
                lead_engine_id = (lead_for_id or {}).get("id") or lead_id
                cancel_lead(current_user.get("tenant_id"), lead_engine_id, reason=f"stage:{new_status}")
            except Exception as _ce:
                print(f"[lead-update] touchpoint cancel failed: {_ce}")

        # CRM sync: fire stage_changed / closed_won / closed_lost events
        if "status" in update_data:
            try:
                lead_after = leads_collection.find_one({"_id": ObjectId(lead_id)}) or {}
                tenant_id = lead_after.get("tenant_id") or current_user.get("tenant_id")
                lead_after["id"] = lead_after.get("id") or str(lead_after.get("_id"))
                new_stage = (update_data["status"] or "").lower().replace(" ", "_").replace("-", "_")
                if new_stage in ("closed_won", "won"):
                    crm_fire_event(tenant_id, lead_after, "lead.closed_won", {"new_stage": update_data["status"]})
                elif new_stage in ("closed_lost", "lost"):
                    crm_fire_event(tenant_id, lead_after, "lead.closed_lost", {"new_stage": update_data["status"]})
                else:
                    crm_fire_event(tenant_id, lead_after, "lead.stage_changed", {"new_stage": update_data["status"]})
            except Exception as _ce:
                print(f"[lead-update] crm fire failed: {_ce}")

        lead = leads_collection.find_one({"_id": ObjectId(lead_id)})
        lead_serialized = serialize_doc(lead)

        # Apply integration automation rules if status changed
        if "status" in update_data:
            try:
                apply_rules = getattr(app.state, "apply_integration_rules", None)
                if apply_rules:
                    await apply_rules(lead_serialized, {"status": update_data["status"]})
            except Exception as _re:
                print(f"[IntegrationRules] error applying on status change: {_re}")

        return lead_serialized
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/leads/{lead_id}")
async def delete_lead(lead_id: str, current_user: dict = Depends(get_current_user)):
    """Iter78 — Hard cascade delete a single lead.

    Removes the lead document plus every related record (activities,
    conversations, touchpoint logs, classification logs). Tenant-scoped
    and owner/admin-only.
    """
    if current_user.get("role") not in ("owner", "admin", "master_admin"):
        raise HTTPException(status_code=403, detail="forbidden: owner/admin only")
    try:
        oid = ObjectId(lead_id)
    except Exception:
        # Iter78 — consistent with cross-tenant lookup: just say "not found" so
        # callers can't probe for the existence of foreign leads by id format.
        raise HTTPException(status_code=404, detail="Lead not found")

    tid = current_user.get("tenant_id")
    lead = leads_collection.find_one({"_id": oid, "tenant_id": tid})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    result = leads_collection.delete_one({"_id": oid, "tenant_id": tid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Cascade — all related records tagged by lead_id.
    casc = {
        "activities":            activities_collection.delete_many({"lead_id": lead_id, "tenant_id": tid}).deleted_count,
        "aria_conversations":    aria_conversations_collection.delete_many({"lead_id": lead_id, "tenant_id": tid}).deleted_count,
        "touchpoint_logs":       db["touchpoint_logs"].delete_many({"lead_id": lead_id, "tenant_id": tid}).deleted_count,
        "classification_logs":   db["classification_logs"].delete_many({"lead_id": lead_id, "tenant_id": tid}).deleted_count,
    }

    try:
        from routes.audit_log import audit_write
        audit_write(
            tenant_id=tid,
            user=current_user,
            action="lead.delete",
            resource_type="lead",
            resource_id=lead_id,
            metadata={"cascade": casc, "lead_name": lead.get("name")},
        )
    except Exception:
        pass

    return {"deleted": True, "cascade": casc}


class BulkLeadDeletePayload(BaseModel):
    lead_ids: List[str] = Field(min_length=1, max_length=500)


@app.post("/api/leads/bulk-delete")
async def bulk_delete_leads(
    payload: BulkLeadDeletePayload,
    current_user: dict = Depends(get_current_user),
):
    """Iter78 — Hard cascade delete a batch of leads."""
    if current_user.get("role") not in ("owner", "admin", "master_admin"):
        raise HTTPException(status_code=403, detail="forbidden: owner/admin only")
    tid = current_user.get("tenant_id")
    deleted = 0
    cascades = {"activities": 0, "aria_conversations": 0, "touchpoint_logs": 0, "classification_logs": 0}
    failed: List[str] = []

    for raw_id in payload.lead_ids:
        try:
            oid = ObjectId(raw_id)
        except Exception:
            failed.append(raw_id)
            continue
        res = leads_collection.delete_one({"_id": oid, "tenant_id": tid})
        if res.deleted_count == 0:
            failed.append(raw_id)
            continue
        deleted += 1
        cascades["activities"]          += activities_collection.delete_many({"lead_id": raw_id, "tenant_id": tid}).deleted_count
        cascades["aria_conversations"]  += aria_conversations_collection.delete_many({"lead_id": raw_id, "tenant_id": tid}).deleted_count
        cascades["touchpoint_logs"]     += db["touchpoint_logs"].delete_many({"lead_id": raw_id, "tenant_id": tid}).deleted_count
        cascades["classification_logs"] += db["classification_logs"].delete_many({"lead_id": raw_id, "tenant_id": tid}).deleted_count

    try:
        from routes.audit_log import audit_write
        audit_write(
            tenant_id=tid,
            user=current_user,
            action="lead.bulk_delete",
            resource_type="lead",
            resource_id=f"{deleted}_leads",
            metadata={"requested": len(payload.lead_ids), "deleted": deleted, "failed": failed, "cascade": cascades},
        )
    except Exception:
        pass

    return {"deleted": deleted, "requested": len(payload.lead_ids), "failed": failed, "cascade": cascades}


@app.delete("/api/conversations/{lead_id}")
async def delete_conversation(lead_id: str, current_user: dict = Depends(get_current_user)):
    """Iter78 — Delete the entire Aria conversation thread for a lead WITHOUT
    deleting the lead itself. Tenant-scoped and owner/admin-only.
    """
    if current_user.get("role") not in ("owner", "admin", "master_admin"):
        raise HTTPException(status_code=403, detail="forbidden: owner/admin only")
    tid = current_user.get("tenant_id")
    # We accept either ObjectId (MongoDB-style) or lead_id-string (legacy).
    deleted = aria_conversations_collection.delete_many({"lead_id": lead_id, "tenant_id": tid}).deleted_count
    try:
        from routes.audit_log import audit_write
        audit_write(
            tenant_id=tid,
            user=current_user,
            action="conversation.delete",
            resource_type="conversation",
            resource_id=lead_id,
            metadata={"messages_deleted": deleted},
        )
    except Exception:
        pass
    return {"deleted": True, "messages_deleted": deleted}

# Activity Endpoints
@app.post("/api/activities")
async def create_activity(activity: ActivityCreate, current_user: dict = Depends(get_current_user)):
    activity_doc = activity.dict()
    activity_doc["user_id"] = current_user["email"]
    activity_doc["tenant_id"] = current_user.get("tenant_id")
    activity_doc["created_at"] = datetime.now(timezone.utc).isoformat()
    
    activities_collection.insert_one(activity_doc)
    
    # Update lead's last_contacted_at (only if lead is in same tenant)
    try:
        leads_collection.update_one(
            {"_id": ObjectId(activity.lead_id), "tenant_id": current_user.get("tenant_id")},
            {"$set": {"last_contacted_at": datetime.now(timezone.utc).isoformat()}}
        )
    except Exception:
        pass
    
    activity_doc = serialize_doc(activity_doc)
    return activity_doc

@app.get("/api/leads/{lead_id}/activities")
async def get_lead_activities(lead_id: str, current_user: dict = Depends(get_current_user)):
    activities = list(activities_collection.find({"lead_id": lead_id, "tenant_id": current_user.get("tenant_id")}).sort("created_at", DESCENDING))
    activities = [serialize_doc(activity) for activity in activities]
    return {"activities": activities}




# CSV Import
@app.post("/api/leads/import")
async def import_leads(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    try:
        # SEC-005 fix (iter168) — cap file size (5 MB) to prevent memory
        # exhaustion; require CSV content-type; stamp tenant_id on every
        # row so imports never become unscoped.
        MAX_CSV_BYTES = 5 * 1024 * 1024  # 5 MB
        MAX_CSV_ROWS = 5000
        ct = (file.content_type or "").lower()
        if ct and ct not in ("text/csv", "application/csv", "application/vnd.ms-excel", "application/octet-stream", "text/plain"):
            raise HTTPException(status_code=400, detail=f"Unsupported content type: {ct}. Upload a CSV.")
        contents = await file.read()
        if len(contents) > MAX_CSV_BYTES:
            raise HTTPException(status_code=413, detail=f"File too large. Max {MAX_CSV_BYTES // (1024*1024)} MB.")
        csv_data = io.StringIO(contents.decode('utf-8'))
        reader = csv.DictReader(csv_data)
        _tenant_id = current_user.get("tenant_id")

        imported_count = 0
        for idx, row in enumerate(reader):
            if idx >= MAX_CSV_ROWS:
                break
            lead_doc = {
                "lead_type": row.get("lead_type", "B2C"),
                "first_name": row.get("first_name", ""),
                "last_name": row.get("last_name", ""),
                "email": row.get("email", ""),
                "phone": row.get("phone"),
                "company_name": row.get("company_name"),
                "job_title": row.get("job_title"),
                "industry": row.get("industry"),
                "revenue_range": row.get("revenue_range"),
                "city": row.get("city"),
                "state": row.get("state"),
                "country": row.get("country"),
                "source_channel": row.get("source_channel", "other"),
                "status": "new",
                "icp_score": 0,
                "icp_tier": "cold",
                "tags": [],
                "custom_fields": {},
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "created_by": current_user["email"],
                "tenant_id": _tenant_id,  # SEC-005 — always stamp tenant on import
            }
            
            if lead_doc["email"]:
                leads_collection.insert_one(lead_doc)
                imported_count += 1
        
        return {"message": f"Successfully imported {imported_count} leads"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Import failed: {str(e)}")

# Team/Users + Health endpoints moved to routes/meta.py




# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ARIA - Autonomous AI Sales Agent Endpoints
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Initialize storage on startup
@app.on_event("startup")
async def startup_event():
    try:
        init_storage()
    except Exception as e:
        print(f"Storage init warning: {e}")

# Pydantic Models for ARIA
class AriaTriggerRequest(BaseModel):
    lead_id: str
    touch_type: str = "first_touch"

class AriaReplyRequest(BaseModel):
    lead_id: str
    message: str

class AriaSettingsUpdate(BaseModel):
    enabled: bool = True
    persona_name: str = "Aria"
    system_prompt_override: Optional[str] = None
    first_touch_delay_minutes: int = 5
    followup_delay_hours: int = 24
    max_messages_per_lead: int = 2
    founder_name: str = "Megha"
    company_name: str = "GenLeadAI"
    calendly_event_type_uri: Optional[str] = None

class AssetUploadResponse(BaseModel):
    id: str
    asset_type: str
    name: str
    storage_path: str
    file_size_kb: float

# Helper: Get or create ARIA settings
def get_aria_settings():
    settings = aria_settings_collection.find_one({}, {"_id": 0})
    if not settings:
        default = {
            "enabled": True,
            "persona_name": os.getenv("ARIA_PERSONA_NAME", "Aria"),
            "system_prompt_override": None,
            "first_touch_delay_minutes": int(os.getenv("ARIA_FIRST_TOUCH_DELAY_MINUTES", 5)),
            "followup_delay_hours": int(os.getenv("ARIA_FOLLOWUP_DELAY_HOURS", 24)),
            "max_messages_per_lead": 2,
            "founder_name": os.getenv("FOUNDER_NAME", "Megha"),
            "company_name": os.getenv("COMPANY_NAME", "GenLeadAI"),
            "calendly_event_type_uri": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        aria_settings_collection.insert_one(default)
        return default
    return settings

# Helper: Get conversation history for a lead
def get_conversation_history(lead_id: str):
    convos = list(aria_conversations_collection.find(
        {"lead_id": lead_id}, {"_id": 0}
    ).sort("created_at", ASCENDING))
    return convos

# Helper: Save ARIA message to conversation
def save_aria_message(lead_id: str, role: str, content: str, action: str = "NONE", action_data: dict = None, metadata: dict = None):
    doc = {
        "lead_id": lead_id,
        "role": role,  # "aria" or "lead"
        "content": content,
        "action": action,
        "action_data": action_data or {},
        "metadata": metadata or {},
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    aria_conversations_collection.insert_one(doc)
    return doc

# Helper: Execute ARIA action
async def execute_aria_action(lead_id: str, action: str, action_data: dict, message: str, lead: dict, current_user_email: str):
    """Execute the action ARIA decided to take."""
    now = datetime.now(timezone.utc).isoformat()
    
    if action == "SEND_EMAIL" or action == "NONE":
        # Send email via Resend
        if lead.get("email"):
            try:
                # White-label: derive sender identity from THIS lead's tenant —
                # never the platform-level env defaults. Hardcoded fallbacks
                # like COMPANY_NAME=GenLeadAI used to leak into every tenant's
                # outbound mail.
                tenant_doc = {}
                if lead.get("tenant_id"):
                    try:
                        tenant_doc = db["tenants"].find_one(
                            {"id": lead["tenant_id"]}, {"_id": 0}) or {}
                    except Exception:
                        tenant_doc = {}
                bp = (tenant_doc.get("settings") or {}).get("business_profile") or {}
                persona_cfg = (tenant_doc.get("settings") or {}).get("aria_persona") or {}
                onboarding = {}
                try:
                    if lead.get("tenant_id"):
                        onboarding = db["onboarding_config"].find_one(
                            {"tenant_id": lead["tenant_id"]}, {"_id": 0}) or {}
                except Exception:
                    onboarding = {}
                ob_bp = onboarding.get("business_profile") or {}

                company_name = (
                    (bp.get("business_name") or "").strip()
                    or (ob_bp.get("business_name") or "").strip()
                    or (tenant_doc.get("name") or "").strip()
                    or "the team"
                )
                founder_name = (
                    (bp.get("founder_name") or "").strip()
                    or (ob_bp.get("founder_name") or "").strip()
                    or (tenant_doc.get("owner_name") or "").strip()
                    or "the founder"
                )
                aria_label = (
                    (persona_cfg.get("aria_name") or "").strip()
                    or os.getenv("ARIA_PERSONA_NAME", "Aria")
                )
                html_body = f"""
                <div style="font-family: -apple-system, sans-serif; max-width: 600px;">
                    <p>{message.replace(chr(10), '<br>')}</p>
                    <br>
                    <p style="color: #666;">Best,<br>{aria_label}<br>
                    Assistant to {founder_name}, {company_name}</p>
                </div>"""

                params = {
                    "from": os.getenv("SENDER_EMAIL", "onboarding@resend.dev"),
                    "to": [lead["email"]],
                    "subject": f"Hi {lead.get('first_name', 'there')} — from {company_name}",
                    "html": html_body,
                }
                # iter88 — route Aria's outbound replies through the
                # workspace-scoped helper so the founder's saved Resend key,
                # from-address, and signature all apply automatically. Falls
                # back to platform default sender when no workspace config.
                try:
                    from routes.pt_email import send_workspace_email
                    await send_workspace_email(
                        to=lead["email"],
                        subject=params["subject"],
                        html_body=html_body,
                        uploads_dir=UPLOADS_DIR,
                        append_signature=True,
                    )
                except Exception:
                    # Platform-default fallback if workspace helper unavailable.
                    await asyncio.to_thread(resend.Emails.send, params)
            except Exception as e:
                print(f"Email send failed: {e}")
        
        # Log activity
        activities_collection.insert_one({
            "lead_id": lead_id,
            "user_id": f"aria@{os.getenv('COMPANY_NAME', 'genleadai').lower()}.ai",
            "activity_type": "email_sent",
            "subject": f"ARIA: Message sent to {lead.get('first_name', 'lead')}",
            "body": message[:200],
            "outcome": None,
            "duration_minutes": None,
            "metadata": {"via": "aria", "action": action},
            "created_at": now
        })
    
    if action == "UPDATE_STATUS":
        new_status = action_data.get("status", "contacted")
        leads_collection.update_one(
            {"_id": ObjectId(lead_id)},
            {"$set": {"status": new_status, "updated_at": now}}
        )
    
    if action == "BOOK_MEETING":
        # Get Calendly event types and create scheduling link
        event_types = await get_calendly_event_types()
        if event_types:
            event_type_uri = event_types[0].get("uri")
            link = await create_scheduling_link(
                event_type_uri,
                lead_name=f"{lead.get('first_name', '')} {lead.get('last_name', '')}",
                lead_email=lead.get("email")
            )
            if link:
                booking_url = link.get("booking_url")
                leads_collection.update_one(
                    {"_id": ObjectId(lead_id)},
                    {"$set": {"aria_booking_url": booking_url, "status": "negotiation", "updated_at": now}}
                )
                return {"booking_url": booking_url}
        
        # Fallback: use calendly link
        leads_collection.update_one(
            {"_id": ObjectId(lead_id)},
            {"$set": {"status": "negotiation", "updated_at": now}}
        )
    
    if action == "MARK_DNC":
        leads_collection.update_one(
            {"_id": ObjectId(lead_id)},
            {"$set": {"aria_state": "DO_NOT_CONTACT", "status": "unqualified", "updated_at": now, "aria_handed_off": True}}
        )
    
    if action == "ESCALATE":
        leads_collection.update_one(
            {"_id": ObjectId(lead_id)},
            {"$set": {"aria_state": "ESCALATED_TO_HUMAN", "status": "qualified", "updated_at": now, "aria_handed_off": True}}
        )
        # Auto-send lead magnet (pre-booking trigger)
        try:
            await auto_send_lead_magnet(lead_id, "pre_booking")
        except Exception as e:
            print(f"Lead magnet auto-send (pre_booking) failed: {e}")
        # Send handoff email to founder
        try:
            convo = get_conversation_history(lead_id)
            convo_summary = "\n".join([f"[{m['role']}]: {m['content'][:100]}" for m in convo[-5:]])
            params = {
                "from": os.getenv("SENDER_EMAIL", "onboarding@resend.dev"),
                "to": [os.getenv("MASTER_ADMIN_EMAIL", "admin@demo.com")],
                "subject": f"ARIA Handoff: {lead.get('first_name', '')} {lead.get('last_name', '')} needs human attention",
                "html": f"<h2>Lead Escalated by ARIA</h2><p><b>Lead:</b> {lead.get('first_name')} {lead.get('last_name')}</p><p><b>Email:</b> {lead.get('email')}</p><p><b>ICP Score:</b> {lead.get('icp_score')}</p><h3>Recent Conversation:</h3><pre>{convo_summary}</pre>"
            }
            await asyncio.to_thread(resend.Emails.send, params)
        except Exception as e:
            print(f"Handoff email failed: {e}")
    
    if action == "LOG_QUALIFICATION":
        leads_collection.update_one(
            {"_id": ObjectId(lead_id)},
            {"$set": {"aria_qualification_data": action_data, "updated_at": now}}
        )
    
    return None

# ─── ARIA API Endpoints ───

@app.post("/api/aria/trigger")
async def trigger_aria(request: AriaTriggerRequest, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    """Trigger ARIA to send a message to a lead (first touch or followup)."""
    try:
        settings = get_aria_settings()
        if not settings.get("enabled"):
            raise HTTPException(status_code=400, detail="ARIA is currently disabled")
        
        lead = leads_collection.find_one({"_id": ObjectId(request.lead_id), "tenant_id": current_user.get("tenant_id")})
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        lead = serialize_doc(lead)
        conversation = get_conversation_history(request.lead_id)
        
        # Run ARIA agent
        result = await run_aria_agent(lead, conversation, touch_type=request.touch_type)
        
        message = result.get("message", "")
        action = result.get("action", "NONE")
        action_data = result.get("action_data", {})
        
        # Save ARIA message
        save_aria_message(request.lead_id, "aria", message, action, action_data)
        
        # Update ARIA state
        new_state = "AWAITING_REPLY_1" if request.touch_type == "first_touch" else "AWAITING_REPLY_2"
        leads_collection.update_one(
            {"_id": ObjectId(request.lead_id), "tenant_id": current_user.get("tenant_id")},
            {"$set": {
                "aria_state": new_state,
                "aria_last_action_at": datetime.now(timezone.utc).isoformat(),
                "status": "contacted" if lead.get("status") == "new" else lead.get("status"),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        # Execute action (send email, etc.)
        action_result = await execute_aria_action(
            request.lead_id, action, action_data, message, lead, current_user["email"]
        )
        
        return {
            "message": message,
            "action": action,
            "action_data": action_data,
            "action_result": action_result,
            "aria_state": new_state
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ARIA trigger failed: {str(e)}")

@app.post("/api/aria/reply")
async def process_aria_reply(request: AriaReplyRequest, current_user: dict = Depends(get_current_user)):
    """Process an incoming reply from a lead and generate ARIA's response."""
    try:
        lead = leads_collection.find_one({"_id": ObjectId(request.lead_id), "tenant_id": current_user.get("tenant_id")})
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        lead = serialize_doc(lead)
        
        # Check if ARIA should respond
        if lead.get("aria_state") in ["DO_NOT_CONTACT", "ESCALATED_TO_HUMAN", "MEETING_BOOKED"]:
            return {"message": "ARIA is no longer active for this lead", "action": "NONE"}
        
        if lead.get("aria_handed_off"):
            return {"message": "This lead has been handed off to a human", "action": "NONE"}
        
        # Save lead's message
        save_aria_message(request.lead_id, "lead", request.message)
        
        # Get conversation history
        conversation = get_conversation_history(request.lead_id)
        
        # Run ARIA
        result = await run_aria_agent(lead, conversation, incoming_message=request.message)
        
        message = result.get("message", "")
        action = result.get("action", "NONE")
        action_data = result.get("action_data", {})
        
        # Save ARIA's response
        save_aria_message(request.lead_id, "aria", message, action, action_data)
        
        # Update state
        leads_collection.update_one(
            {"_id": ObjectId(request.lead_id), "tenant_id": current_user.get("tenant_id")},
            {"$set": {
                "aria_state": "CONVERSATION_ACTIVE",
                "aria_last_action_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        # Execute action
        action_result = await execute_aria_action(
            request.lead_id, action, action_data, message, lead, current_user["email"]
        )
        
        return {
            "message": message,
            "action": action,
            "action_data": action_data,
            "action_result": action_result
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ARIA reply failed: {str(e)}")

@app.get("/api/aria/conversation/{lead_id}")
async def get_aria_conversation(lead_id: str, current_user: dict = Depends(get_current_user)):
    """Get full ARIA conversation history for a lead."""
    # SEC-003 fix (iter168) — tenant-scoped read
    lead = leads_collection.find_one(
        {"_id": ObjectId(lead_id), "tenant_id": current_user.get("tenant_id")},
        {"_id": 0, "aria_state": 1, "aria_handed_off": 1, "aria_qualification_data": 1, "aria_booking_url": 1},
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    conversation = get_conversation_history(lead_id)
    return {
        "conversation": conversation,
        "aria_state": lead.get("aria_state", "PENDING_FIRST_TOUCH") if lead else "PENDING_FIRST_TOUCH",
        "handed_off": lead.get("aria_handed_off", False) if lead else False,
        "qualification_data": lead.get("aria_qualification_data") if lead else None,
        "booking_url": lead.get("aria_booking_url") if lead else None,
    }

@app.post("/api/aria/takeover/{lead_id}")
async def takeover_from_aria(lead_id: str, current_user: dict = Depends(get_current_user)):
    """Human takes over conversation from ARIA."""
    # SEC-003 fix (iter168) — tenant-scoped write
    res = leads_collection.update_one(
        {"_id": ObjectId(lead_id), "tenant_id": current_user.get("tenant_id")},
        {"$set": {
            "aria_state": "ESCALATED_TO_HUMAN",
            "aria_handed_off": True,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Lead not found")
    save_aria_message(lead_id, "system", "Human agent has taken over this conversation")
    # CRM sync — fire takeover + paused events
    try:
        lead_doc = leads_collection.find_one({"_id": ObjectId(lead_id), "tenant_id": current_user.get("tenant_id")}) or {}
        tenant_id = lead_doc.get("tenant_id")
        if tenant_id:
            lead_doc["id"] = str(lead_doc.get("_id"))
            crm_fire_event(tenant_id, lead_doc, "conversation.takeover", {
                "rep_name": current_user.get("full_name") or current_user.get("email"),
                "user_email": current_user.get("email"),
            })
            crm_fire_event(tenant_id, lead_doc, "aria.paused", {
                "rep_name": current_user.get("full_name") or current_user.get("email"),
                "user_email": current_user.get("email"),
            })
    except Exception:
        pass
    return {"message": "You've taken over this conversation from ARIA"}

@app.post("/api/aria/resume/{lead_id}")
async def resume_aria(lead_id: str, current_user: dict = Depends(get_current_user)):
    """Resume ARIA for a lead after human takeover."""
    # SEC-003 fix (iter168) — tenant-scoped write
    res = leads_collection.update_one(
        {"_id": ObjectId(lead_id), "tenant_id": current_user.get("tenant_id")},
        {"$set": {
            "aria_state": "CONVERSATION_ACTIVE",
            "aria_handed_off": False,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Lead not found")
    save_aria_message(lead_id, "system", "ARIA has been resumed for this conversation")
    try:
        lead_doc = leads_collection.find_one({"_id": ObjectId(lead_id), "tenant_id": current_user.get("tenant_id")}) or {}
        tenant_id = lead_doc.get("tenant_id")
        if tenant_id:
            lead_doc["id"] = str(lead_doc.get("_id"))
            crm_fire_event(tenant_id, lead_doc, "aria.resumed", {
                "rep_name": current_user.get("full_name") or current_user.get("email"),
                "user_email": current_user.get("email"),
            })
    except Exception:
        pass
    return {"message": "ARIA has been resumed for this lead"}

# ─── ARIA Settings Endpoints ───

@app.get("/api/aria/settings")
async def get_aria_settings_endpoint(current_user: dict = Depends(get_current_user)):
    return get_aria_settings()

@app.put("/api/aria/settings")
async def update_aria_settings_endpoint(settings_update: AriaSettingsUpdate, current_user: dict = Depends(get_current_user)):
    update_data = settings_update.dict()
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    aria_settings_collection.update_one({}, {"$set": update_data}, upsert=True)
    return get_aria_settings()

# ─── ARIA Analytics ───

@app.get("/api/aria/analytics")
async def get_aria_analytics(current_user: dict = Depends(get_current_user)):
    """Get ARIA performance analytics — tenant-scoped."""
    tid = current_user.get("tenant_id")
    # Total conversations
    leads_with_aria = list(leads_collection.find(
        {"aria_state": {"$exists": True, "$ne": None}, "tenant_id": tid},
        {"_id": 0, "aria_state": 1, "icp_tier": 1, "status": 1}
    ))
    
    total_conversations = len(leads_with_aria)
    
    # Count by state
    state_counts = {}
    for lead in leads_with_aria:
        state = lead.get("aria_state", "UNKNOWN")
        state_counts[state] = state_counts.get(state, 0) + 1
    
    # Count messages
    total_aria_messages = aria_conversations_collection.count_documents({"role": "aria", "tenant_id": tid})
    total_lead_replies = aria_conversations_collection.count_documents({"role": "lead", "tenant_id": tid})
    
    # Reply rate
    reply_rate = round((total_lead_replies / max(total_conversations, 1)) * 100, 1)
    
    # Booking rate
    booked = state_counts.get("MEETING_BOOKED", 0) + leads_collection.count_documents({"aria_booking_url": {"$exists": True, "$ne": None}, "tenant_id": tid})
    booking_rate = round((booked / max(total_conversations, 1)) * 100, 1)
    
    # Qualification rate
    active_or_beyond = sum(state_counts.get(s, 0) for s in ["CONVERSATION_ACTIVE", "BOOKING_ATTEMPTED", "MEETING_BOOKED", "ESCALATED_TO_HUMAN"])
    qualification_rate = round((active_or_beyond / max(total_conversations, 1)) * 100, 1)
    
    # Disqualification reasons
    dnc_count = state_counts.get("DO_NOT_CONTACT", 0)
    
    return {
        "total_conversations": total_conversations,
        "total_aria_messages": total_aria_messages,
        "total_lead_replies": total_lead_replies,
        "reply_rate": reply_rate,
        "qualification_rate": qualification_rate,
        "booking_rate": booking_rate,
        "meetings_booked": booked,
        "escalations": state_counts.get("ESCALATED_TO_HUMAN", 0),
        "do_not_contact": dnc_count,
        "state_distribution": state_counts,
    }

# ─── ARIA Live Feed ───

@app.get("/api/aria/feed")
async def get_aria_feed(current_user: dict = Depends(get_current_user)):
    """Get live feed of active ARIA conversations — tenant-scoped."""
    active_leads = list(leads_collection.find(
        {"aria_state": {"$exists": True, "$ne": None}, "tenant_id": current_user.get("tenant_id")},
    ).sort("aria_last_action_at", DESCENDING).limit(50))
    
    feed = []
    for lead in active_leads:
        lead_id = str(lead["_id"])
        last_msg = aria_conversations_collection.find_one(
            {"lead_id": lead_id}, {"_id": 0}, sort=[("created_at", DESCENDING)]
        )
        
        feed.append({
            "lead_id": lead_id,
            "lead_name": f"{lead.get('first_name', '')} {lead.get('last_name', '')}",
            "lead_email": lead.get("email"),
            "company": lead.get("company_name"),
            "aria_state": lead.get("aria_state"),
            "icp_tier": lead.get("icp_tier"),
            "icp_score": lead.get("icp_score"),
            "last_message": last_msg.get("content", "")[:100] if last_msg else "",
            "last_message_role": last_msg.get("role") if last_msg else None,
            "last_action_at": lead.get("aria_last_action_at"),
            "handed_off": lead.get("aria_handed_off", False),
        })
    
    return {"feed": feed, "total": len(feed)}

# Calendly endpoints moved to routes/meta.py

# Asset Library endpoints moved to routes/assets_routes.py (iter108 ACTION 3)

# Legacy /api/leads/your-five-today body removed (iter108 ACTION 3) — the
# canonical implementation lives at line ~361 under get_your_five_today_route().

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MODULE: SLEEPING LEADS + REVIVAL ENGINE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# iter169 — deprecated /api/leads/sleeping stub removed. Canonical
# tenant-scoped handler lives above /api/leads/{lead_id} (line ~476).

class RevivalCampaignRequest(BaseModel):
    lead_ids: List[str]
    angle: str = "check_in"  # check_in, new_value, limited_time, direct_ask
    channel: str = "email"  # email, whatsapp, both

@app.post("/api/leads/revival-campaign")
async def launch_revival_campaign(request: RevivalCampaignRequest, current_user: dict = Depends(get_current_user)):
    """Launch a revival campaign for sleeping leads."""
    results = {"sent": 0, "failed": 0, "messages": []}

    angle_prompts = {
        "check_in": "Write a warm, friendly check-in message. Be genuine and brief.",
        "new_value": "Share a valuable insight or asset. Lead with value, not a pitch.",
        "limited_time": "Create gentle urgency — a limited-time offer or exclusive opportunity.",
        "direct_ask": "Be direct and ask for a meeting. Confident but not pushy.",
    }

    for lead_id in request.lead_ids[:50]:  # Cap at 50
        try:
            # SEC-003 fix (iter168) — tenant-scoped lookup + prevent
            # sending outbound email/AI-spend on foreign leads.
            lead = leads_collection.find_one({"_id": ObjectId(lead_id), "tenant_id": current_user.get("tenant_id")})
            if not lead:
                continue
            lead = serialize_doc(lead)

            # Generate personalized message via Claude wrapper
            from services.claude_service import claude_call as _claude_call, TaskType as _TaskType
            system_msg = f"You are Aria, a warm sales assistant for {os.getenv('COMPANY_NAME', 'GenLeadAI')}. {angle_prompts.get(request.angle, angle_prompts['check_in'])}"
            prompt = f"Write a short revival message (3-4 sentences) for: {lead.get('first_name')} {lead.get('last_name')}, {lead.get('company_name', 'their company')}, source: {lead.get('source_channel')}. They haven't been contacted recently."
            response = await _claude_call(
                task_type=_TaskType.INSIGHT_GENERATION,
                system=system_msg,
                prompt=prompt,
                tenant_id=current_user.get("tenant_id"),
                session_id=f"revival_{lead_id}",
            )
            message = (response or "").strip()

            # Send via selected channel
            if request.channel in ["email", "both"] and lead.get("email"):
                try:
                    params = {
                        "from": os.getenv("SENDER_EMAIL", "onboarding@resend.dev"),
                        "to": [lead["email"]],
                        "subject": f"Quick thought for you, {lead.get('first_name', 'there')}",
                        "html": f"<div style='font-family:sans-serif;max-width:600px'><p>{message.replace(chr(10),'<br>')}</p><br><p style='color:#666'>Best,<br>Aria<br>Assistant to {os.getenv('FOUNDER_NAME','Megha')}, {os.getenv('COMPANY_NAME','GenLeadAI')}</p></div>",
                    }
                    await asyncio.to_thread(resend.Emails.send, params)
                except Exception as e:
                    print(f"Revival email failed for {lead_id}: {e}")

            # Log WhatsApp as simulated
            if request.channel in ["whatsapp", "both"]:
                activities_collection.insert_one({
                    "lead_id": lead_id, "user_id": "aria@genleadai.ai",
                    "activity_type": "whatsapp_sent",
                    "subject": f"Revival: {request.angle.replace('_',' ')} message",
                    "body": message[:200], "outcome": None, "duration_minutes": None,
                    "metadata": {"via": "aria", "channel": "whatsapp", "simulated": True, "revival_angle": request.angle},
                    "created_at": datetime.now(timezone.utc).isoformat()
                })

            # Update lead
            leads_collection.update_one(
                {"_id": ObjectId(lead_id), "tenant_id": current_user.get("tenant_id")},
                {"$set": {
                    "last_contacted_at": datetime.now(timezone.utc).isoformat(),
                    "status": "contacted",
                    "aria_state": "AWAITING_REPLY_1",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }, "$inc": {"revival_attempts": 1}}
            )

            # Log activity
            activities_collection.insert_one({
                "lead_id": lead_id, "user_id": "aria@genleadai.ai",
                "activity_type": "revival_triggered",
                "subject": f"Revival campaign: {request.angle.replace('_',' ')}",
                "body": message[:200], "outcome": None, "duration_minutes": None,
                "metadata": {"angle": request.angle, "channel": request.channel},
                "created_at": datetime.now(timezone.utc).isoformat()
            })

            results["sent"] += 1
            results["messages"].append({"lead_id": lead_id, "name": f"{lead.get('first_name')} {lead.get('last_name')}", "message": message[:150]})
        except Exception as e:
            results["failed"] += 1
            print(f"Revival failed for {lead_id}: {e}")

    return results

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MODULE: NO-SHOW RECOVERY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class NoShowRequest(BaseModel):
    lead_id: str
    step: int = 1  # 1, 2, or 3

@app.post("/api/leads/no-show-recovery")
async def trigger_no_show_recovery(request: NoShowRequest, current_user: dict = Depends(get_current_user)):
    """Trigger no-show recovery message for a lead."""
    # SEC-003 fix (iter168) — tenant-scoped read
    lead = leads_collection.find_one({"_id": ObjectId(request.lead_id), "tenant_id": current_user.get("tenant_id")})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead = serialize_doc(lead)

    messages = {
        1: f"Hey {lead.get('first_name', 'there')}, looks like we missed each other! Want to find another time that works? I'd love to connect.",
        2: f"Hi {lead.get('first_name', 'there')}! Still happy to show you how we've helped companies like yours grow. Here's a quick look at some results we've driven — would love to chat when you're free.",
        3: f"Hi {lead.get('first_name', 'there')}, I'll leave this here in case timing wasn't right. Happy to reconnect whenever you're ready. No pressure at all!",
    }

    message = messages.get(request.step, messages[1])

    # Get Calendly link
    event_types = await get_calendly_event_types()
    booking_url = None
    if event_types:
        link = await create_scheduling_link(event_types[0].get("uri"), lead.get("first_name"), lead.get("email"))
        if link:
            booking_url = link.get("booking_url")
            message += f"\n\nBook a time here: {booking_url}"

    # Send email
    if lead.get("email"):
        try:
            params = {
                "from": os.getenv("SENDER_EMAIL", "onboarding@resend.dev"),
                "to": [lead["email"]],
                "subject": f"Missed you earlier, {lead.get('first_name', 'there')}!" if request.step == 1 else f"Quick follow-up, {lead.get('first_name', 'there')}",
                "html": f"<div style='font-family:sans-serif;max-width:600px'><p>{message.replace(chr(10),'<br>')}</p></div>",
            }
            await asyncio.to_thread(resend.Emails.send, params)
        except Exception as e:
            print(f"No-show email failed: {e}")

    # Update lead
    update_data = {"updated_at": datetime.now(timezone.utc).isoformat(), "last_contacted_at": datetime.now(timezone.utc).isoformat()}
    if request.step >= 3:
        update_data["aria_state"] = "ESCALATED_TO_HUMAN"
        update_data["aria_handed_off"] = True
    leads_collection.update_one({"_id": ObjectId(request.lead_id)}, {"$set": update_data, "$inc": {"no_show_count": 1 if request.step == 1 else 0}})

    # Log activity
    activities_collection.insert_one({
        "lead_id": request.lead_id, "user_id": "aria@genleadai.ai",
        "activity_type": "no_show_detected",
        "subject": f"No-show recovery step {request.step}",
        "body": message[:200], "outcome": None, "duration_minutes": None,
        "metadata": {"step": request.step, "booking_url": booking_url},
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    return {"message": message, "step": request.step, "booking_url": booking_url, "escalated": request.step >= 3}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MODULE: REFERRAL CAPTURE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.post("/api/leads/{lead_id}/referral-ask")
async def trigger_referral_ask(lead_id: str, current_user: dict = Depends(get_current_user)):
    """Send referral ask to a won lead."""
    lead = leads_collection.find_one({"_id": ObjectId(lead_id)})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead = serialize_doc(lead)

    if lead.get("referral_message_sent"):
        return {"message": "Referral already requested", "already_sent": True}

    founder = os.getenv("FOUNDER_NAME", "Megha")
    message = f"Hey {lead.get('first_name', 'there')}, so glad to be working together! Quick question — anyone in your network dealing with similar growth challenges? Even a warm intro would mean a lot to us. Thanks so much!"

    if lead.get("email"):
        try:
            params = {
                "from": os.getenv("SENDER_EMAIL", "onboarding@resend.dev"),
                "to": [lead["email"]],
                "subject": f"Quick ask, {lead.get('first_name', 'there')} — know anyone who needs growth help?",
                "html": f"<div style='font-family:sans-serif;max-width:600px'><p>{message.replace(chr(10),'<br>')}</p><br><p style='color:#666'>Warm regards,<br>Aria<br>on behalf of {founder}</p></div>",
            }
            await asyncio.to_thread(resend.Emails.send, params)
        except Exception as e:
            print(f"Referral email failed: {e}")

    leads_collection.update_one({"_id": ObjectId(lead_id)}, {"$set": {"referral_message_sent": True, "updated_at": datetime.now(timezone.utc).isoformat()}})

    activities_collection.insert_one({
        "lead_id": lead_id, "user_id": "aria@genleadai.ai",
        "activity_type": "referral_requested",
        "subject": "Referral ask sent",
        "body": message[:200], "outcome": None, "duration_minutes": None,
        "metadata": {"channel": "email"},
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    return {"message": message, "sent": True}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MODULE: INTENT SIGNALS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class IntentSignalRequest(BaseModel):
    lead_id: str
    signal_type: str  # email_opened, link_clicked, calendly_clicked, website_revisit, whatsapp_read

@app.post("/api/intent-signals")
async def fire_intent_signal(request: IntentSignalRequest, current_user: dict = Depends(get_current_user)):
    """Log an intent signal and boost ICP score."""
    lead = leads_collection.find_one({"_id": ObjectId(request.lead_id)})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    signal_labels = {
        "email_opened": "opened your email",
        "link_clicked": "clicked a link",
        "calendly_clicked": "clicked Calendly link",
        "website_revisit": "revisited your website",
        "whatsapp_read": "read your WhatsApp message",
    }

    signal = {
        "type": request.signal_type,
        "label": signal_labels.get(request.signal_type, request.signal_type),
        "fired_at": datetime.now(timezone.utc).isoformat(),
    }

    # Update lead with signal + score boost
    leads_collection.update_one(
        {"_id": ObjectId(request.lead_id)},
        {
            "$push": {"intent_signals": signal},
            "$inc": {"icp_score": 10, "intent_score_boost": 10},
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
        }
    )

    # Cap score at 100
    lead_updated = leads_collection.find_one({"_id": ObjectId(request.lead_id)})
    if lead_updated and lead_updated.get("icp_score", 0) > 100:
        leads_collection.update_one({"_id": ObjectId(request.lead_id)}, {"$set": {"icp_score": 100}})

    # Update tier
    new_score = min(lead_updated.get("icp_score", 0), 100) if lead_updated else 0
    new_tier = "hot" if new_score >= 70 else ("warm" if new_score >= 40 else "cold")
    leads_collection.update_one({"_id": ObjectId(request.lead_id)}, {"$set": {"icp_tier": new_tier}})

    # Log activity
    activities_collection.insert_one({
        "lead_id": request.lead_id, "user_id": "system",
        "activity_type": "intent_signal_fired",
        "subject": f"Intent signal: {signal['label']}",
        "body": None, "outcome": None, "duration_minutes": None,
        "metadata": signal,
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    return {"signal": signal, "new_score": new_score, "new_tier": new_tier, "boosted": True}

@app.get("/api/intent-signals/recent")
async def get_recent_intent_signals(limit: int = 20, current_user: dict = Depends(get_current_user)):
    """Get recent intent signals across all leads."""
    signals = list(activities_collection.find(
        {"activity_type": "intent_signal_fired"}, {"_id": 0}
    ).sort("created_at", DESCENDING).limit(limit))

    # Enrich with lead names
    for sig in signals:
        lead = leads_collection.find_one({"_id": ObjectId(sig["lead_id"])}, {"first_name": 1, "last_name": 1, "company_name": 1})
        if lead:
            sig["lead_name"] = f"{lead.get('first_name', '')} {lead.get('last_name', '')}"
            sig["company"] = lead.get("company_name")

    return {"signals": signals}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MODULE: BROADCAST PERSONALIZER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class BroadcastRequest(BaseModel):
    name: str
    template: str
    channel: str = "email"  # email, whatsapp, both
    filters: Dict[str, Any] = {}  # lead_type, icp_tier, status, tags

@app.post("/api/broadcasts")
async def create_broadcast(request: BroadcastRequest, current_user: dict = Depends(get_current_user)):
    """Create and send a personalized broadcast to a filtered segment."""
    query = {"status": {"$nin": ["won", "lost", "do_not_contact"]}}
    # iter80 — S9.5: strip Mongo operators from user-controlled filter values
    _safe_filters = safe_filter_value(request.filters or {})
    if _safe_filters.get("lead_type"):
        query["lead_type"] = _safe_filters["lead_type"]
    if _safe_filters.get("icp_tier"):
        query["icp_tier"] = _safe_filters["icp_tier"]
    if _safe_filters.get("status"):
        query["status"] = _safe_filters["status"]

    leads = list(leads_collection.find(query).limit(100))
    results = {"total_targeted": len(leads), "sent": 0, "failed": 0, "channel": request.channel}

    for lead_doc in leads:
        lead = serialize_doc(lead_doc)
        try:
            # Personalize template
            personalized = request.template
            personalized = personalized.replace("{{first_name}}", lead.get("first_name", "there") or "there")
            personalized = personalized.replace("{{company}}", lead.get("company_name", "your company") or "your company")
            personalized = personalized.replace("{{industry}}", lead.get("industry", "your industry") or "your industry")

            if request.channel in ["email", "both"] and lead.get("email"):
                try:
                    params = {
                        "from": os.getenv("SENDER_EMAIL", "onboarding@resend.dev"),
                        "to": [lead["email"]],
                        "subject": f"{request.name}",
                        "html": f"<div style='font-family:sans-serif;max-width:600px'><p>{personalized.replace(chr(10),'<br>')}</p></div>",
                    }
                    await asyncio.to_thread(resend.Emails.send, params)
                except:
                    pass

            if request.channel in ["whatsapp", "both"]:
                activities_collection.insert_one({
                    "lead_id": lead["id"], "user_id": "broadcast",
                    "activity_type": "whatsapp_sent",
                    "subject": f"Broadcast: {request.name}",
                    "body": personalized[:200], "outcome": None, "duration_minutes": None,
                    "metadata": {"via": "broadcast", "channel": "whatsapp", "simulated": True},
                    "created_at": datetime.now(timezone.utc).isoformat()
                })

            results["sent"] += 1
        except:
            results["failed"] += 1

    return results

@app.post("/api/broadcasts/preview")
async def preview_broadcast(request: BroadcastRequest, current_user: dict = Depends(get_current_user)):
    """Preview personalized messages for 5 random leads from the segment."""
    query = {"status": {"$nin": ["won", "lost", "do_not_contact"]}}
    # iter80 — S9.5: strip Mongo operators from user-controlled filter values
    _safe_filters = safe_filter_value(request.filters or {})
    if _safe_filters.get("lead_type"):
        query["lead_type"] = _safe_filters["lead_type"]
    if _safe_filters.get("icp_tier"):
        query["icp_tier"] = _safe_filters["icp_tier"]

    leads = list(leads_collection.find(query).limit(5))
    previews = []
    for lead_doc in leads:
        lead = serialize_doc(lead_doc)
        msg = request.template
        msg = msg.replace("{{first_name}}", lead.get("first_name", "there") or "there")
        msg = msg.replace("{{company}}", lead.get("company_name", "your company") or "your company")
        msg = msg.replace("{{industry}}", lead.get("industry", "your industry") or "your industry")
        previews.append({"lead_name": f"{lead.get('first_name')} {lead.get('last_name')}", "message": msg})

    total = leads_collection.count_documents(query)
    return {"previews": previews, "total_in_segment": total}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ARIA SALES PA — 3-PHASE LIFECYCLE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FOUNDER_PROFILE = {
    "name": os.getenv("FOUNDER_NAME", "Megha"),
    "company": os.getenv("COMPANY_NAME", "GenLeadAI"),
    "role": "Founder & CEO",
    "what_we_do": "AI-first growth marketing and fractional CMO services for B2B and B2C businesses",
    "ideal_client": "Founders and CMOs sitting on leads but with no time or system to convert them",
    "tone": "Warm, founder-to-founder. Sounds like Megha wrote it herself — never corporate, never scripted, never salesy. Like a smart friend who knows marketing.",
    "signature_sign_off": "Warm regards, Megha",
    "timezone": "Asia/Kolkata",
    "working_hours": "9 AM – 7 PM IST",
    "calendly_event": "20-min Discovery Call with Megha",
}

# ─── Pre-Call Research ───

class PreCallResearchRequest(BaseModel):
    lead_id: str

@app.post("/api/aria/research")
async def pre_call_research(request: PreCallResearchRequest, current_user: dict = Depends(get_current_user)):
    """Run pre-call research on a lead using AI inference."""
    lead = leads_collection.find_one({"_id": ObjectId(request.lead_id)})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead = serialize_doc(lead)

    from services.claude_service import claude_call as _claude_call, TaskType as _TaskType, ClaudeServiceError as _ClaudeServiceError
    system_msg = "You are a senior B2B sales researcher. Generate comprehensive pre-call research based on the lead's profile data. Be specific, actionable, and focused on what a founder needs to know before a discovery call."

    prompt = f"""Research this lead for a pre-call briefing:

Name: {lead.get('first_name')} {lead.get('last_name')}
Email: {lead.get('email')}
Company: {lead.get('company_name', 'Unknown')}
Job Title: {lead.get('job_title', 'Unknown')}
Industry: {lead.get('industry', 'Unknown')}
Revenue Range: {lead.get('revenue_range', 'Unknown')}
City: {lead.get('city', 'Unknown')}, Country: {lead.get('country', 'Unknown')}
Source Channel: {lead.get('source_channel')}
ICP Score: {lead.get('icp_score')}
Notes: {lead.get('notes', 'None')}

Generate a JSON research object with these keys:
- company_summary: 2-3 sentences about the company
- person_summary: 2-3 sentences about the person's likely role and priorities
- industry_context: Current challenges and trends in their industry
- pain_hypothesis: The most likely problem they want solved (2-3 sentences)
- recommended_opener: A specific first question for the founder to ask
- potential_objections: Array of 2-3 likely objections with suggested responses
- relevant_case_studies: What type of past work would resonate most
- deal_value_estimate: Estimated potential deal value reasoning
- red_flags: Any concerns to watch for
- talking_points: Array of 3-4 key points to cover on the call

Return ONLY valid JSON."""

    try:
        research = await _claude_call(
            task_type=_TaskType.INSIGHT_GENERATION,
            system=system_msg,
            prompt=prompt,
            tenant_id=current_user.get("tenant_id"),
            session_id=f"research_{request.lead_id}",
            response_format="json",
        )
    except _ClaudeServiceError:
        research = {
            "company_summary": f"{lead.get('company_name', 'The company')} operates in {lead.get('industry', 'their')} industry.",
            "person_summary": f"{lead.get('first_name')} is {lead.get('job_title', 'a decision maker')} focused on growth.",
            "pain_hypothesis": "They likely need a systematic approach to converting their lead pipeline.",
            "recommended_opener": f"What's the biggest growth challenge you're facing right now?",
            "potential_objections": [{"objection": "Budget concerns", "response": "Reframe as ROI investment"}],
            "relevant_case_studies": "Growth system implementations for similar companies",
            "red_flags": [],
            "talking_points": ["Their current marketing approach", "Lead conversion challenges", "Growth timeline"]
        }

    leads_collection.update_one(
        {"_id": ObjectId(request.lead_id)},
        {"$set": {"research_data": research, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )

    activities_collection.insert_one({
        "lead_id": request.lead_id, "user_id": "aria@genleadai.ai",
        "activity_type": "note_added", "subject": "Pre-call research completed",
        "body": research.get("pain_hypothesis", "")[:200],
        "outcome": None, "duration_minutes": None,
        "metadata": {"type": "pre_call_research"},
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    return {"research": research, "lead_id": request.lead_id}

# ─── Pre-Call Brief ───

@app.post("/api/aria/pre-call-brief/{lead_id}")
async def send_pre_call_brief(lead_id: str, current_user: dict = Depends(get_current_user)):
    """Generate and send pre-call brief to the founder."""
    lead = leads_collection.find_one({"_id": ObjectId(lead_id)})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead = serialize_doc(lead)
    research = lead.get("research_data", {})
    qual = lead.get("aria_qualification_data", {})
    founder = FOUNDER_PROFILE["name"]

    # WhatsApp-style brief (short)
    whatsapp_brief = f"""Pre-call brief — {lead.get('first_name')} {lead.get('last_name')}

{lead.get('first_name')}, {lead.get('job_title', 'Lead')} at {lead.get('company_name', 'N/A')}
{lead.get('city', '')}, {lead.get('country', '')}

Why they reached out:
{research.get('pain_hypothesis', 'Interested in growth marketing services')}

What to lead with:
{research.get('recommended_opener', 'Ask about their biggest growth challenge')}

Watch out for:
{', '.join([r.get('objection','') for r in research.get('potential_objections', [])[:2]]) or 'No specific concerns flagged'}

ICP Score: {lead.get('icp_score', 0)}/100
Source: {lead.get('source_channel', 'unknown')}"""

    # Email brief (detailed)
    email_html = f"""<div style="font-family:'Plus Jakarta Sans',sans-serif;max-width:700px;margin:0 auto;">
<div style="background:linear-gradient(135deg,#C044E0,#5B28D4);padding:20px 24px;border-radius:12px 12px 0 0;">
<h1 style="color:white;margin:0;font-size:20px;">Pre-Call Brief: {lead.get('first_name')} {lead.get('last_name')}</h1>
<p style="color:rgba(255,255,255,0.8);margin:4px 0 0;font-size:14px;">{lead.get('company_name', 'N/A')} — {lead.get('job_title', 'Lead')}</p>
</div>
<div style="background:white;padding:24px;border:1px solid #E8E0F5;border-top:none;border-radius:0 0 12px 12px;">

<h2 style="color:#1A0A2E;font-size:16px;margin:0 0 8px;">WHO ARE THEY</h2>
<p style="color:#5A4A7A;font-size:14px;line-height:1.6;">{research.get('company_summary', 'Company information pending research.')}</p>
<p style="color:#5A4A7A;font-size:14px;line-height:1.6;"><strong>The Person:</strong> {research.get('person_summary', f'{lead.get("first_name")} — details pending')}</p>

<h2 style="color:#1A0A2E;font-size:16px;margin:20px 0 8px;">WHY THEY'RE TALKING TO US</h2>
<p style="color:#5A4A7A;font-size:14px;">Source: <strong>{lead.get('source_channel', 'N/A')}</strong> | ICP Score: <strong>{lead.get('icp_score', 0)}/100</strong> ({lead.get('icp_tier', 'N/A')})</p>
{f"<p style='color:#5A4A7A;font-size:14px;'>Budget: {qual.get('budget','N/A')} | Timeline: {qual.get('timeline','N/A')}</p>" if qual else ""}

<h2 style="color:#1A0A2E;font-size:16px;margin:20px 0 8px;">PAIN HYPOTHESIS</h2>
<p style="color:#7C35DC;font-size:14px;font-weight:600;background:#F4F0FF;padding:12px;border-radius:8px;border:1px solid #E0D4F7;">{research.get('pain_hypothesis', 'Needs growth marketing support')}</p>

<h2 style="color:#1A0A2E;font-size:16px;margin:20px 0 8px;">RECOMMENDED OPENING</h2>
<p style="color:#5A4A7A;font-size:14px;font-style:italic;">"{research.get('recommended_opener', 'What is your biggest growth challenge right now?')}"</p>

<h2 style="color:#1A0A2E;font-size:16px;margin:20px 0 8px;">POTENTIAL OBJECTIONS</h2>
{''.join([f"<p style='color:#5A4A7A;font-size:13px;margin:4px 0;'><strong>{o.get('objection','')}</strong> → {o.get('response','')}</p>" for o in research.get('potential_objections', [])])}

<h2 style="color:#1A0A2E;font-size:16px;margin:20px 0 8px;">TALKING POINTS</h2>
<ul style="color:#5A4A7A;font-size:14px;">{''.join([f"<li>{tp}</li>" for tp in research.get('talking_points', [])])}</ul>

</div></div>"""

    # Send email
    try:
        params = {
            "from": os.getenv("SENDER_EMAIL", "onboarding@resend.dev"),
            "to": [os.getenv("MASTER_ADMIN_EMAIL", "admin@demo.com")],
            "subject": f"Pre-call brief: {lead.get('first_name')} {lead.get('last_name')} — {lead.get('company_name', 'N/A')}",
            "html": email_html,
        }
        await asyncio.to_thread(resend.Emails.send, params)
    except Exception as e:
        print(f"Brief email failed: {e}")

    leads_collection.update_one(
        {"_id": ObjectId(lead_id)},
        {"$set": {"pre_call_brief_sent": True, "pre_call_brief_sent_at": datetime.now(timezone.utc).isoformat()}}
    )

    activities_collection.insert_one({
        "lead_id": lead_id, "user_id": "aria@genleadai.ai",
        "activity_type": "note_added", "subject": f"Pre-call brief sent to {founder}",
        "body": None, "outcome": None, "duration_minutes": None,
        "metadata": {"type": "pre_call_brief"},
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    return {"whatsapp_brief": whatsapp_brief, "email_sent": True, "brief_sent": True}

# ─── Phase 2: Call Outcome ───

class CallOutcomeRequest(BaseModel):
    lead_id: str
    outcome: str  # interested, proposal_sent, not_a_fit, needs_more_time, rescheduled, no_show
    notes: Optional[str] = None
    check_back_in_days: Optional[int] = None

@app.post("/api/aria/call-outcome")
async def record_call_outcome(request: CallOutcomeRequest, current_user: dict = Depends(get_current_user)):
    """Record the founder's post-call outcome and trigger Phase 3."""
    lead = leads_collection.find_one({"_id": ObjectId(request.lead_id)})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead = serialize_doc(lead)
    founder = FOUNDER_PROFILE["name"]
    now_iso = datetime.now(timezone.utc).isoformat()

    update_data = {
        "call_outcome": request.outcome,
        "call_happened_at": now_iso,
        "updated_at": now_iso,
    }
    if request.notes:
        update_data["post_call_notes"] = request.notes

    # Generate post-call message based on outcome
    post_call_message = None
    new_status = lead.get("status")
    new_aria_state = "CONVERSATION_ACTIVE"

    if request.outcome == "interested":
        post_call_message = f"Hey {lead.get('first_name', 'there')}, it was so great connecting with {founder} today! She's putting together something tailored for you and will be in touch shortly.\n\nIn the meantime, feel free to reach out if anything comes to mind!"
        new_aria_state = "PROPOSAL_PENDING"
        new_status = "negotiation"

    elif request.outcome == "proposal_sent":
        post_call_message = f"Hey {lead.get('first_name', 'there')}, it was so great connecting with {founder} today! She's putting together something tailored for you and will be in touch shortly.\n\nIn the meantime, feel free to reach out if anything comes to mind!"
        new_aria_state = "PROPOSAL_PENDING"
        new_status = "proposal_sent"

    elif request.outcome == "not_a_fit":
        post_call_message = f"Hey {lead.get('first_name', 'there')}, it was really lovely speaking with {founder} today. At this stage it sounds like the timing might not be quite right, but we'd love to stay in touch.\n\nI'll keep you in the loop if anything relevant comes up on our end!"
        new_aria_state = "DISQUALIFIED"
        new_status = "lost"

    elif request.outcome == "needs_more_time":
        new_aria_state = "WAITING_FOR_CHECK_IN"
        new_status = "nurture"
        if request.check_back_in_days:
            update_data["next_followup_at"] = (datetime.now(timezone.utc) + timedelta(days=request.check_back_in_days)).isoformat()

    elif request.outcome == "rescheduled":
        # Get new Calendly link
        event_types = await get_calendly_event_types()
        booking_url = None
        if event_types:
            link = await create_scheduling_link(event_types[0].get("uri"), lead.get("first_name"), lead.get("email"))
            if link:
                booking_url = link.get("booking_url")
        post_call_message = f"Hey {lead.get('first_name', 'there')}, {founder} had something come up — so sorry for the inconvenience!\n\nHere's her calendar to find a new time that works for you: {booking_url or 'I will send you a new link shortly'}"
        new_aria_state = "BOOKING_ATTEMPTED"
        new_status = "contacted"

    elif request.outcome == "no_show":
        new_aria_state = "AWAITING_REPLY_1"
        new_status = "contacted"

    update_data["aria_state"] = new_aria_state
    update_data["status"] = new_status
    update_data["aria_handed_off"] = False

    leads_collection.update_one({"_id": ObjectId(request.lead_id)}, {"$set": update_data})

    # Send post-call message
    if post_call_message and lead.get("email"):
        try:
            params = {
                "from": os.getenv("SENDER_EMAIL", "onboarding@resend.dev"),
                "to": [lead["email"]],
                "subject": f"Great speaking with you, {lead.get('first_name', 'there')}!",
                "html": f"<div style='font-family:sans-serif;max-width:600px'><p>{post_call_message.replace(chr(10),'<br>')}</p><br><p style='color:#666'>{FOUNDER_PROFILE['signature_sign_off']}</p></div>",
            }
            await asyncio.to_thread(resend.Emails.send, params)
        except Exception as e:
            print(f"Post-call email failed: {e}")

    # Save to conversation
    if post_call_message:
        save_aria_message(request.lead_id, "aria", post_call_message, "SEND_EMAIL", {"post_call": True, "outcome": request.outcome})

    # Log activity
    activities_collection.insert_one({
        "lead_id": request.lead_id, "user_id": current_user["email"],
        "activity_type": "meeting_done", "subject": f"Call outcome: {request.outcome.replace('_', ' ')}",
        "body": request.notes, "outcome": request.outcome,
        "duration_minutes": None, "metadata": {"outcome": request.outcome, "phase": "post_call"},
        "created_at": now_iso
    })

    return {"outcome": request.outcome, "new_state": new_aria_state, "new_status": new_status, "message_sent": post_call_message is not None}

# ─── Phase 3: Proposal Follow-up ───

class ProposalFollowUpRequest(BaseModel):
    lead_id: str
    step: int = 1  # 1-4

@app.post("/api/aria/proposal-followup")
async def trigger_proposal_followup(request: ProposalFollowUpRequest, current_user: dict = Depends(get_current_user)):
    """Trigger a proposal follow-up message."""
    lead = leads_collection.find_one({"_id": ObjectId(request.lead_id)})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead = serialize_doc(lead)
    founder = FOUNDER_PROFILE["name"]
    name = lead.get("first_name", "there")

    messages = {
        1: f"Hey {name}, just checking in — did you get a chance to look over what {founder} sent across?\n\nHappy to answer any questions in the meantime!",
        2: f"Hey {name}, wanted to share something quickly — we recently helped a company in {lead.get('industry', 'your space')} see some incredible results. Made me think of your situation. {founder}'s around if you'd like to talk through anything!",
        3: f"Hey {name}, I want to be respectful of your time — if the timing isn't right or you've gone a different direction, just let me know and I'll stop following up.\n\nBut if you're still evaluating, {founder} would love to answer any questions before you decide.",
        4: f"Last one from me, {name} — just leaving the door open. Whenever the time is right, we're here. Wishing you the best either way!",
    }

    message = messages.get(request.step, messages[1])

    if lead.get("email"):
        try:
            subjects = {1: f"Quick check-in, {name}", 2: f"Thought you'd find this interesting, {name}", 3: f"Just checking, {name}", 4: f"Door's always open, {name}"}
            params = {
                "from": os.getenv("SENDER_EMAIL", "onboarding@resend.dev"),
                "to": [lead["email"]],
                "subject": subjects.get(request.step, f"Following up, {name}"),
                "html": f"<div style='font-family:sans-serif;max-width:600px'><p>{message.replace(chr(10),'<br>')}</p><br><p style='color:#666'>{FOUNDER_PROFILE['signature_sign_off']}</p></div>",
            }
            await asyncio.to_thread(resend.Emails.send, params)
        except Exception as e:
            print(f"Proposal follow-up email failed: {e}")

    save_aria_message(request.lead_id, "aria", message, "SEND_EMAIL", {"proposal_followup": True, "step": request.step})

    new_state = "PROPOSAL_FOLLOW_UP"
    if request.step >= 4:
        new_state = "SEQUENCE_ENDED"
        leads_collection.update_one({"_id": ObjectId(request.lead_id)}, {"$set": {"status": "nurture"}})

    leads_collection.update_one(
        {"_id": ObjectId(request.lead_id)},
        {"$set": {"aria_state": new_state, "proposal_follow_up_count": request.step, "aria_last_action_at": datetime.now(timezone.utc).isoformat(), "updated_at": datetime.now(timezone.utc).isoformat()}}
    )

    activities_collection.insert_one({
        "lead_id": request.lead_id, "user_id": "aria@genleadai.ai",
        "activity_type": "email_sent", "subject": f"Proposal follow-up {request.step}/4",
        "body": message[:200], "outcome": None, "duration_minutes": None,
        "metadata": {"step": request.step, "type": "proposal_followup"},
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    return {"message": message, "step": request.step, "new_state": new_state, "final": request.step >= 4}

# ─── Mark Proposal Sent ───

@app.post("/api/aria/mark-proposal-sent/{lead_id}")
async def mark_proposal_sent(lead_id: str, current_user: dict = Depends(get_current_user)):
    """Mark that the founder has sent the proposal."""
    leads_collection.update_one(
        {"_id": ObjectId(lead_id)},
        {"$set": {
            "proposal_sent_at": datetime.now(timezone.utc).isoformat(),
            "aria_state": "PROPOSAL_FOLLOW_UP",
            "status": "proposal_sent",
            "proposal_follow_up_count": 0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    return {"marked": True, "proposal_sent_at": datetime.now(timezone.utc).isoformat()}

# ─── Founder Instruction (Partial Override) ───

class FounderInstructionRequest(BaseModel):
    lead_id: str
    instruction: str

@app.post("/api/aria/founder-instruction")
async def founder_instruction(request: FounderInstructionRequest, current_user: dict = Depends(get_current_user)):
    """Send a private instruction to Aria for a specific lead."""
    leads_collection.update_one(
        {"_id": ObjectId(request.lead_id)},
        {"$push": {"aria_founder_instructions": {"instruction": request.instruction, "from": current_user["email"], "at": datetime.now(timezone.utc).isoformat()}}}
    )
    save_aria_message(request.lead_id, "system", f"Founder instruction: {request.instruction}", "INSTRUCTION", {"instruction": request.instruction})
    return {"acknowledged": True, "message": f"Got it — noted for this lead's conversation."}

# ─── Pause for Call ───

@app.post("/api/aria/pause-for-call/{lead_id}")
async def pause_for_call(lead_id: str, current_user: dict = Depends(get_current_user)):
    """Pause Aria during a live call."""
    leads_collection.update_one(
        {"_id": ObjectId(lead_id)},
        {"$set": {"aria_state": "ON_HOLD_DURING_CALL", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    save_aria_message(lead_id, "system", "Aria paused — call in progress")
    return {"paused": True, "state": "ON_HOLD_DURING_CALL"}

# ─── Weekly Summary ───

@app.get("/api/aria/weekly-summary")
async def get_weekly_summary(current_user: dict = Depends(get_current_user)):
    """Generate weekly sales summary."""
    now = datetime.now(timezone.utc)
    week_ago = (now - timedelta(days=7)).isoformat()

    new_leads = leads_collection.count_documents({"created_at": {"$gte": week_ago}})
    calls = activities_collection.count_documents({"activity_type": {"$in": ["meeting_done", "call"]}, "created_at": {"$gte": week_ago}})
    proposals = leads_collection.count_documents({"proposal_sent_at": {"$gte": week_ago}})
    won = leads_collection.count_documents({"status": "won", "updated_at": {"$gte": week_ago}})
    cold = leads_collection.count_documents({"aria_state": {"$in": ["SEQUENCE_ENDED", None]}, "icp_tier": {"$in": ["warm", "hot"]}, "last_contacted_at": {"$lt": (now - timedelta(days=7)).isoformat()}})
    upcoming_calls = leads_collection.count_documents({"aria_state": "MEETING_BOOKED"})
    hot_needs_attention = leads_collection.count_documents({"icp_tier": "hot", "status": {"$in": ["proposal_sent", "negotiation"]}, "last_contacted_at": {"$lt": (now - timedelta(days=3)).isoformat()}})
    proposals_pending = leads_collection.count_documents({"aria_state": {"$in": ["PROPOSAL_PENDING", "PROPOSAL_FOLLOW_UP"]}})
    active_convos = aria_conversations_collection.count_documents({"created_at": {"$gte": week_ago}})

    summary = {
        "period": "Last 7 days",
        "new_leads": new_leads,
        "calls_happened": calls,
        "proposals_sent": proposals,
        "deals_won": won,
        "leads_went_cold": cold,
        "upcoming_calls": upcoming_calls,
        "hot_leads_need_attention": hot_needs_attention,
        "proposals_pending_reply": proposals_pending,
        "aria_active_conversations": active_convos,
    }

    # Send email
    try:
        founder = FOUNDER_PROFILE["name"]
        html = f"""<div style="font-family:'Plus Jakarta Sans',sans-serif;max-width:600px;margin:0 auto;">
<div style="background:linear-gradient(135deg,#C044E0,#5B28D4);padding:20px 24px;border-radius:12px 12px 0 0;">
<h1 style="color:white;margin:0;font-size:20px;">Weekly Sales Summary</h1>
<p style="color:rgba(255,255,255,0.8);margin:4px 0 0;font-size:14px;">Good morning {founder}!</p>
</div>
<div style="background:white;padding:24px;border:1px solid #E8E0F5;border-top:none;border-radius:0 0 12px 12px;">
<h3 style="color:#1A0A2E;margin:0 0 16px;">Last Week</h3>
<p style="color:#5A4A7A;font-size:14px;line-height:2;">
{new_leads} new leads came in<br>
{calls} calls happened<br>
{proposals} proposals sent<br>
{won} deals won<br>
{cold} leads went cold
</p>
<h3 style="color:#1A0A2E;margin:16px 0;">This Week</h3>
<p style="color:#5A4A7A;font-size:14px;line-height:2;">
{upcoming_calls} calls scheduled<br>
{hot_needs_attention} hot leads need your attention<br>
{proposals_pending} proposals pending reply
</p>
<p style="color:#7C35DC;font-size:14px;font-weight:600;margin-top:16px;">Aria is handling {active_convos} active conversations.</p>
</div></div>"""
        params = {
            "from": os.getenv("SENDER_EMAIL", "onboarding@resend.dev"),
            "to": [os.getenv("MASTER_ADMIN_EMAIL", "admin@demo.com")],
            "subject": f"Weekly Sales Summary — {founder}",
            "html": html,
        }
        await asyncio.to_thread(resend.Emails.send, params)
        summary["email_sent"] = True
    except Exception as e:
        summary["email_sent"] = False
        print(f"Weekly summary email failed: {e}")

    return summary

# ─── Get Lead Phase Info ───

@app.get("/api/aria/lead-phase/{lead_id}")
async def get_lead_phase(lead_id: str, current_user: dict = Depends(get_current_user)):
    """Get the current phase and state info for a lead's ARIA lifecycle."""
    lead = leads_collection.find_one({"_id": ObjectId(lead_id)})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead = serialize_doc(lead)

    state = lead.get("aria_state", "PENDING_FIRST_TOUCH")
    phase1_states = ["PENDING_FIRST_TOUCH", "AWAITING_REPLY_1", "AWAITING_REPLY_2", "CONVERSATION_ACTIVE", "BOOKING_ATTEMPTED", "MEETING_BOOKED"]
    phase2_states = ["ON_HOLD_DURING_CALL"]
    phase3_states = ["PROPOSAL_PENDING", "PROPOSAL_FOLLOW_UP", "WAITING_FOR_CHECK_IN"]

    if state in phase1_states:
        phase = 1
    elif state in phase2_states:
        phase = 2
    elif state in phase3_states:
        phase = 3
    else:
        phase = 0

    return {
        "phase": phase,
        "aria_state": state,
        "call_outcome": lead.get("call_outcome"),
        "proposal_sent_at": lead.get("proposal_sent_at"),
        "proposal_follow_up_count": lead.get("proposal_follow_up_count", 0),
        "pre_call_brief_sent": lead.get("pre_call_brief_sent", False),
        "research_data": lead.get("research_data"),
        "post_call_notes": lead.get("post_call_notes"),
        "aria_handed_off": lead.get("aria_handed_off", False),
        "aria_founder_instructions": lead.get("aria_founder_instructions", []),
        "founder_active": state == "FOUNDER_ACTIVE" or lead.get("aria_handed_off", False),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PRODUCTION LEAD INGESTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Public API, web-form, API-key, audit-log, exports, onboarding-legacy, and
# TTV endpoints moved to dedicated route modules (iter125 — server.py split).
# Re-exports kept for backward-compat with tests & cross-module callers.
from routes.public_api import (  # noqa: E402,F401
    API_KEYS_COLLECTION,
    verify_api_key,
)
from routes.exports_audit import (  # noqa: E402,F401
    audit_log_collection,
    log_audit,
)
from routes.onboarding_legacy import (  # noqa: E402,F401
    onboarding_collection,
    ttv_collection,
)


# Lead-magnet (pre-call brochure) moved to routes/lead_magnets.py (iter108 ACTION 3).
# Re-export for callers (e.g. Calendly inbound handler):
from routes.lead_magnets import auto_send_lead_magnet  # noqa: E402,F401

# ─── WhatsApp Cloud API (Meta) ───
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_GRAPH_API_VERSION = os.getenv("WHATSAPP_GRAPH_API_VERSION", "v23.0")
WHATSAPP_API_BASE_URL = os.getenv("WHATSAPP_API_BASE_URL", "https://graph.facebook.com")


def _whatsapp_configured() -> bool:
    return bool(WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID)


def _normalize_phone(phone: str) -> str:
    digits = "".join(c for c in (phone or "") if c.isdigit())
    return digits


async def send_whatsapp_text(to_phone: str, body: str, tenant_id: str = None) -> dict:
    """Send a WhatsApp text via the tenant's chosen provider (Meta or 360dialog).

    When tenant_id is None or no tenant config exists, falls back to the global
    Meta env credentials (legacy single-tenant behaviour). When neither is
    configured, returns logged_only=True without sending.
    """
    from whatsapp_dispatch import send_whatsapp_text as _dispatch
    return await _dispatch(to_phone, body, tenant_id=tenant_id)
# WhatsApp webhooks moved to routes/webhooks_whatsapp.py (iter108 ACTION 3)



# Call-priority + daily call-plan moved to routes/aria_call_priority.py (iter108 ACTION 3).
from routes.aria_call_priority import (  # noqa: E402,F401
    _compute_call_priority,
    _compute_best_time_to_call_for_lead,
    daily_call_plan_loop,
)

@app.on_event("startup")
async def _start_daily_call_plan_loop():
    asyncio.create_task(daily_call_plan_loop())
    print("[DailyCallPlan] Background loop started (60s tick)")



@app.on_event("startup")
async def _start_touchpoint_engine_loop():
    asyncio.create_task(engine_loop())


@app.on_event("startup")
async def _start_outreach_engine_loop():
    asyncio.create_task(outreach_engine_loop())


@app.on_event("startup")
async def _start_crm_sync_loop():
    asyncio.create_task(crm_sync_loop())


@app.on_event("startup")
async def _start_stale_lead_loop():
    asyncio.create_task(health_stale_loop())


@app.on_event("startup")
async def _start_retention_loop():
    asyncio.create_task(retention_loop())
    print("[Retention] Background loop started (24h tick)")


@app.on_event("startup")
async def _start_b2b_insight_scan_loop():
    """Iter97 — Daily B2B Insights cron. Scans every b2b/hybrid tenant once
    per 24h, classifies new signals via Claude, and persists insight cards.
    Cheap when no tenants exist; safe when LLM key absent (returns []).
    """
    asyncio.create_task(b2b_insight_scan_loop())
    # iter105 — snooze-recovery loop (hourly) so snoozed cards re-surface.
    try:
        from routes.pt_insights import snooze_recovery_loop
        asyncio.create_task(snooze_recovery_loop())
        print("[Iter105] snooze_recovery loop started")
    except Exception as _e:
        print(f"[Iter105] snooze_recovery loop NOT started: {_e}")
    # iter105 — Task 2: insight_digest_sender (fires daily at configured hour)
    try:
        from routes.insight_digest import insight_digest_sender_loop
        asyncio.create_task(insight_digest_sender_loop())
        print("[Iter105] insight_digest_sender loop started")
    except Exception as _e:
        print(f"[Iter105] insight_digest_sender loop NOT started: {_e}")
    # iter106 — OAuth token refresh (6h tick)
    try:
        from routes.oauth_integrations import oauth_token_refresh_loop
        asyncio.create_task(oauth_token_refresh_loop())
        print("[Iter106] oauth_token_refresh loop started")
    except Exception as _e:
        print(f"[Iter106] oauth_token_refresh loop NOT started: {_e}")
    print("[B2BInsightScan] Background loop started (24h tick, +5min startup stagger)")


@app.on_event("startup")
async def _start_iter103_audit_loops():
    """Iter103 — V3 audit §18 gap-fillers. Three small loops:
       - saleshandy_poll (30m): import recent Saleshandy replies
       - enrichment_retry (24h): retry failed Proxycurl/Serper enrichments
       - pixel_attribution (10m): attribute pageviews to leads by email/IP
    """
    from routes.audit_loops import (
        saleshandy_poll_loop, enrichment_retry_loop, pixel_attribution_loop,
    )
    asyncio.create_task(saleshandy_poll_loop())
    asyncio.create_task(enrichment_retry_loop())
    asyncio.create_task(pixel_attribution_loop())
    print("[Iter103] saleshandy_poll + enrichment_retry + pixel_attribution loops started")


@app.on_event("startup")
async def _start_eod_wrap_loop():
    """iter108 — EOD wrap loop (moved into routes/aria_eod_wrap.py)."""
    from routes.aria_eod_wrap import eod_wrap_loop
    asyncio.create_task(eod_wrap_loop())
    print("[EODWrap] Background loop started (60s tick)")


@app.on_event("startup")
async def _start_morning_brief_loop():
    """iter117 Batch 5 — ARIA Morning Brief (weekday 8 AM workspace-local cron)."""
    from routes.aria_morning_brief import morning_brief_loop
    asyncio.create_task(morning_brief_loop())
    print("[MorningBrief] Background loop started (60s tick)")


@app.on_event("startup")
async def _start_linkedin_poller_loop():
    """iter118 Batch 6 — LinkedIn comment polling for inbound replies."""
    from routes.inbound_reply import linkedin_comment_poller_loop
    asyncio.create_task(linkedin_comment_poller_loop())
    print("[InboundReply] LinkedIn comment poller started (5min tick)")


@app.on_event("startup")
async def _start_approval_digest_loop():
    """iter120 Batch 8 — 8 PM Approval Queue digest cron."""
    from routes.aria_approval_digest import approval_digest_loop
    asyncio.create_task(approval_digest_loop())
    print("[ApprovalDigest] Background loop started (60s tick)")


@app.on_event("startup")
async def _start_pietential_intel_loops():
    """iter143 — Pietential intelligence engine: 3 background loops."""
    from routes.pietential_intel import (
        lemlist_poll_loop,
        pietential_insight_scan_loop,
        weekly_intel_report_loop,
    )
    asyncio.create_task(lemlist_poll_loop())
    asyncio.create_task(pietential_insight_scan_loop())
    asyncio.create_task(weekly_intel_report_loop())
    print("[Pietential] Lemlist poll (30min) + daily scan (07:30 IST) + weekly report (Mon 08:00 IST) started")



# EOD-wrap module moved to routes/aria_eod_wrap.py (iter108 ACTION 3)



# Demo seeder moved to routes/demo_seeder.py (iter108 ACTION 3)

# /api/dev/set-plan moved to routes/billing_plans_legacy.py (iter108 ACTION 3)




# Founder Command Center moved to routes/founder_command_center.py (iter125 split).
# Re-export for backward-compat (aria_eod_wrap uses _fmt_inr).
from routes.founder_command_center import _fmt_inr  # noqa: E402,F401


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Attach ARIA AI Sales Agent routes (additive only)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from aria_agent_routes import attach_aria_agent_routes  # noqa: E402
attach_aria_agent_routes(app, get_current_user, db)

from integrations_routes import attach_integrations_routes  # noqa: E402
attach_integrations_routes(app, get_current_user, db)
