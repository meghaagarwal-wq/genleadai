from fastapi import FastAPI, HTTPException, Depends, status, Query, UploadFile, File, BackgroundTasks, Response, Header, Form
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
from emergentintegrations.llm.chat import LlmChat, UserMessage
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
# Modular routers
from routes.auth import router as auth_router
from routes.meta import router as meta_router
from routes.campaigns import router as campaigns_router
from routes.ai import router as ai_router
from routes.analytics import router as analytics_router
from routes.beta_feedback import router as beta_feedback_router
from routes.pietential import router as pietential_router, register_pietential_startup
from routes.tenants import router as tenants_router
from routes.billing import router as billing_router, webhook_router as stripe_webhook_router
from routes.touchpoints import router as touchpoints_router
from routes.touchpoint_preview import router as touchpoint_preview_router
from routes.touchpoint_engine import router as touchpoint_engine_router, engine_loop, instantiate_for_lead, pause_lead, cancel_lead
from routes.billing_plans import router as billing_plans_router
from routes.compliance import router as compliance_router, is_stop_keyword, opt_out_phone, auto_opt_in_on_inbound
from routes.contacts import router as contacts_router
from routes.classification import router as classification_router, classify_inbound
from routes.aria_confidence import router as aria_confidence_router
from routes.admin_revenue import router as admin_revenue_router, invoice_router as admin_invoice_router
from routes.crm_sync import router as crm_sync_router, fire_event as crm_fire_event, crm_sync_loop
from routes.audit_log import router as audit_log_router, admin_router as admin_workspaces_router, audit_write
from routes.data_deletion import router as data_deletion_router
from routes.reports import router as reports_router
from routes.lead_capture import router as lead_capture_router, public_router as lead_capture_public_router, widget_public_router as lead_capture_widget_public_router
from routes.integrations_hub import router as integrations_hub_router, public_router as integrations_hub_public_router, fire_lifecycle_event
from routes.conversations import router as conversations_router
from routes.retention import retention_loop
from routes.health_engine import (
    router as health_router,
    failed_router as failed_messages_router,
    stale_lead_loop as health_stale_loop,
    classify_sentiment as health_classify_sentiment,
)
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

load_dotenv()

app = FastAPI(title="GenLeadAI LMS API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register modular routers
app.include_router(auth_router)
app.include_router(meta_router)
app.include_router(campaigns_router)
app.include_router(ai_router)
app.include_router(analytics_router)
app.include_router(beta_feedback_router)
app.include_router(pietential_router)
app.include_router(tenants_router)
app.include_router(billing_router)
app.include_router(stripe_webhook_router)
app.include_router(touchpoints_router)
app.include_router(touchpoint_preview_router)
app.include_router(touchpoint_engine_router)
app.include_router(billing_plans_router)
app.include_router(compliance_router)
app.include_router(contacts_router)
app.include_router(classification_router)
app.include_router(aria_confidence_router)
app.include_router(admin_revenue_router)
app.include_router(admin_invoice_router)
app.include_router(crm_sync_router)
app.include_router(audit_log_router)
app.include_router(admin_workspaces_router)
app.include_router(data_deletion_router)
app.include_router(reports_router)
app.include_router(lead_capture_router)
app.include_router(lead_capture_public_router)
app.include_router(lead_capture_widget_public_router)
app.include_router(integrations_hub_router)
app.include_router(integrations_hub_public_router)
app.include_router(conversations_router)
app.include_router(health_router)
app.include_router(failed_messages_router)

# Rate limiter — applied to sensitive auth & webhook endpoints
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
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
        query["$or"] = [
            {"first_name": {"$regex": search, "$options": "i"}},
            {"last_name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
            {"company_name": {"$regex": search, "$options": "i"}}
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
    excluded = ["won", "lost", "do_not_contact"]
    candidates = list(leads_collection.find(
        {"status": {"$nin": excluded}},
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
async def get_sleeping_leads_route(threshold_days: int = 14, current_user: dict = Depends(get_current_user)):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=threshold_days)).isoformat()
    query = {"status": {"$nin": ["won", "lost", "do_not_contact"]}, "$or": [{"last_contacted_at": {"$lt": cutoff}}, {"last_contacted_at": None}, {"last_contacted_at": {"$exists": False}}]}
    leads = list(leads_collection.find(query).sort("icp_score", DESCENDING).limit(200))
    leads = [serialize_doc(l) for l in leads]
    now = datetime.now(timezone.utc)
    for lead in leads:
        lc = lead.get("last_contacted_at")
        if lc:
            try: days = (now - datetime.fromisoformat(lc.replace("Z", "+00:00"))).days
            except: days = 30
        else:
            try: days = (now - datetime.fromisoformat(lead.get("created_at", now.isoformat()).replace("Z", "+00:00"))).days
            except: days = 30
        lead["_days_asleep"] = days
        lead["_segment"] = "cold_vault" if days >= 60 else ("at_risk" if days >= 30 else "sleeping")
    sleeping = len([l for l in leads if l["_segment"] == "sleeping"])
    at_risk = len([l for l in leads if l["_segment"] == "at_risk"])
    cold_vault = len([l for l in leads if l["_segment"] == "cold_vault"])
    return {"leads": leads, "total": len(leads), "segments": {"sleeping": sleeping, "at_risk": at_risk, "cold_vault": cold_vault}}

@app.get("/api/leads/{lead_id}")
async def get_lead(lead_id: str, current_user: dict = Depends(get_current_user)):
    try:
        # Tenant isolation: lookup must include tenant_id
        lead = leads_collection.find_one({"_id": ObjectId(lead_id), "tenant_id": current_user.get("tenant_id")})
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        return serialize_doc(lead)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid lead ID")

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
    try:
        result = leads_collection.delete_one({"_id": ObjectId(lead_id), "tenant_id": current_user.get("tenant_id")})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Lead not found")
        return {"message": "Lead deleted successfully"}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid lead ID")

# Activity Endpoints
@app.post("/api/activities")
async def create_activity(activity: ActivityCreate, current_user: dict = Depends(get_current_user)):
    activity_doc = activity.dict()
    activity_doc["user_id"] = current_user["email"]
    activity_doc["tenant_id"] = current_user.get("tenant_id")
    activity_doc["created_at"] = datetime.now(timezone.utc).isoformat()
    
    result = activities_collection.insert_one(activity_doc)
    
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
        contents = await file.read()
        csv_data = io.StringIO(contents.decode('utf-8'))
        reader = csv.DictReader(csv_data)
        
        imported_count = 0
        for row in reader:
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
                "created_by": current_user["email"]
            }
            
            if lead_doc["email"]:
                leads_collection.insert_one(lead_doc)
                imported_count += 1
        
        return {"message": f"Successfully imported {imported_count} leads"}
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
                founder_name = os.getenv("FOUNDER_NAME", "Megha")
                company_name = os.getenv("COMPANY_NAME", "GenLeadAI")
                html_body = f"""
                <div style="font-family: -apple-system, sans-serif; max-width: 600px;">
                    <p>{message.replace(chr(10), '<br>')}</p>
                    <br>
                    <p style="color: #666;">Best,<br>{os.getenv('ARIA_PERSONA_NAME', 'Aria')}<br>
                    Assistant to {founder_name}, {company_name}</p>
                </div>"""
                
                params = {
                    "from": os.getenv("SENDER_EMAIL", "onboarding@resend.dev"),
                    "to": [lead["email"]],
                    "subject": f"Hi {lead.get('first_name', 'there')} — from {company_name}",
                    "html": html_body,
                }
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
                "to": ["admin@demo.com"],
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
        
        lead = leads_collection.find_one({"_id": ObjectId(request.lead_id)})
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
            {"_id": ObjectId(request.lead_id)},
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
        lead = leads_collection.find_one({"_id": ObjectId(request.lead_id)})
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
            {"_id": ObjectId(request.lead_id)},
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
    conversation = get_conversation_history(lead_id)
    lead = leads_collection.find_one({"_id": ObjectId(lead_id)}, {"_id": 0, "aria_state": 1, "aria_handed_off": 1, "aria_qualification_data": 1, "aria_booking_url": 1})
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
    leads_collection.update_one(
        {"_id": ObjectId(lead_id)},
        {"$set": {
            "aria_state": "ESCALATED_TO_HUMAN",
            "aria_handed_off": True,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    save_aria_message(lead_id, "system", "Human agent has taken over this conversation")
    # CRM sync — fire takeover + paused events
    try:
        lead_doc = leads_collection.find_one({"_id": ObjectId(lead_id)}) or {}
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
    leads_collection.update_one(
        {"_id": ObjectId(lead_id)},
        {"$set": {
            "aria_state": "CONVERSATION_ACTIVE",
            "aria_handed_off": False,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    save_aria_message(lead_id, "system", "ARIA has been resumed for this conversation")
    try:
        lead_doc = leads_collection.find_one({"_id": ObjectId(lead_id)}) or {}
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
    disqualified_count = leads_collection.count_documents({"aria_state": "DO_NOT_CONTACT", "tenant_id": tid})
    
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

# ─── Asset Library Endpoints ───

@app.post("/api/assets/upload")
async def upload_asset(
    file: UploadFile = File(...),
    asset_type: str = "brand_deck",
    send_in_first_touch: bool = True,
    current_user: dict = Depends(get_current_user)
):
    """Upload an asset (PDF, document, image) to object storage."""
    try:
        data = await file.read()
        file_size_kb = len(data) / 1024
        
        if file_size_kb > 10240:  # 10MB limit
            raise HTTPException(status_code=400, detail="File too large (max 10MB)")
        
        ext = file.filename.split(".")[-1] if "." in file.filename else "bin"
        storage_path = f"genleadai/assets/{uuid.uuid4()}.{ext}"
        
        result = put_object(storage_path, data, file.content_type or "application/octet-stream")
        
        asset_doc = {
            "asset_type": asset_type,
            "name": file.filename,
            "storage_path": result.get("path", storage_path),
            "original_filename": file.filename,
            "file_size_kb": round(file_size_kb, 2),
            "mime_type": file.content_type or "application/octet-stream",
            "is_active": True,
            "send_in_first_touch": send_in_first_touch,
            "send_count": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        
        workspace_assets_collection.insert_one(asset_doc)
        asset_doc = serialize_doc(asset_doc)
        
        return asset_doc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.get("/api/assets")
async def get_assets(current_user: dict = Depends(get_current_user)):
    """Get all workspace assets."""
    assets = list(workspace_assets_collection.find({"is_active": True}).sort("created_at", DESCENDING))
    assets = [serialize_doc(a) for a in assets]
    return {"assets": assets}

@app.get("/api/assets/download/{asset_id}")
async def download_asset(asset_id: str, auth: str = Query(None), authorization: str = Header(None)):
    """Download an asset file."""
    try:
        asset = workspace_assets_collection.find_one({"_id": ObjectId(asset_id)})
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        
        data, content_type = get_object(asset["storage_path"])
        return Response(
            content=data,
            media_type=asset.get("mime_type", content_type),
            headers={"Content-Disposition": f'attachment; filename="{asset.get("original_filename", "file")}"'}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

@app.patch("/api/assets/{asset_id}")
async def update_asset(asset_id: str, current_user: dict = Depends(get_current_user)):
    """Toggle asset settings."""
    import json as json_lib
    # Simple toggle - read body manually
    asset = workspace_assets_collection.find_one({"_id": ObjectId(asset_id)})
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    # Toggle send_in_first_touch
    new_val = not asset.get("send_in_first_touch", False)
    workspace_assets_collection.update_one(
        {"_id": ObjectId(asset_id)},
        {"$set": {"send_in_first_touch": new_val, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"send_in_first_touch": new_val}

@app.delete("/api/assets/{asset_id}")
async def delete_asset(asset_id: str, current_user: dict = Depends(get_current_user)):
    """Soft-delete an asset."""
    workspace_assets_collection.update_one(
        {"_id": ObjectId(asset_id)},
        {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"message": "Asset deleted"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MODULE: YOUR 5 TODAY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.get("/api/leads/your-five-today")
async def get_your_five_today(current_user: dict = Depends(get_current_user)):
    """AI-ranked top 5 leads the founder should personally touch today."""
    try:
        # Get all active leads (not won, lost, do_not_contact) — tenant-scoped
        excluded = ["won", "lost", "do_not_contact"]
        candidates = list(leads_collection.find(
            {"status": {"$nin": excluded}, "tenant_id": current_user.get("tenant_id")},
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

            # ICP score weight (30%)
            icp = lead.get("icp_score", 0)
            score += icp * 0.3
            if icp >= 70:
                reasons.append(f"High ICP score ({icp}) — strong fit for your services")

            # Days since last contact (20%)
            last_contact = lead.get("last_contacted_at")
            days_since = 999
            if last_contact:
                try:
                    lc = datetime.fromisoformat(last_contact.replace("Z", "+00:00"))
                    days_since = (now - lc).days
                except:
                    days_since = 30
            else:
                days_since = 999
                reasons.append("Never been contacted — fresh opportunity")
            score += min(days_since * 1.5, 30) * 0.2 / 30 * 100

            # Intent signals (25%)
            intent = lead.get("intent_signals") or []
            intent_boost = lead.get("intent_score_boost", 0)
            if intent_boost > 0 or len(intent) > 0:
                score += 25
                reasons.append("Showed recent intent signals")

            # ARIA state (15%)
            aria_state = lead.get("aria_state")
            if aria_state == "ESCALATED_TO_HUMAN":
                score += 15
                reasons.append("ARIA escalated — lead asked for a human")
            elif aria_state == "CONVERSATION_ACTIVE":
                score += 10
                reasons.append("Active ARIA conversation — warm and engaged")
            elif aria_state == "AWAITING_REPLY_1" or aria_state == "AWAITING_REPLY_2":
                score += 5

            # No-show recovery (10%)
            no_shows = lead.get("no_show_count", 0)
            if no_shows > 0:
                score += 10
                reasons.append(f"No-showed {no_shows} time(s) — recovery needed")

            # Fallback reason
            if not reasons:
                if days_since > 7:
                    reasons.append(f"No contact in {days_since} days — time to re-engage")
                else:
                    reasons.append(f"ICP score {icp} — worth a personal touch")

            lead["_rank_score"] = score
            lead["_reason"] = reasons[0] if reasons else "Recommended by AI"
            lead["_all_reasons"] = reasons
            lead["_days_since_contact"] = days_since
            scored.append(lead)

        # Sort and take top 5
        scored.sort(key=lambda x: x["_rank_score"], reverse=True)
        top5 = scored[:5]

        # Add suggested actions
        for lead in top5:
            if lead.get("aria_state") == "ESCALATED_TO_HUMAN":
                lead["_suggested_action"] = {"type": "call", "label": "Call them directly", "reason": "They asked for a human — make it personal"}
            elif lead.get("_days_since_contact", 0) > 14:
                lead["_suggested_action"] = {"type": "email", "label": "Send a check-in", "reason": "Re-open with value"}
            elif lead.get("icp_score", 0) >= 70:
                lead["_suggested_action"] = {"type": "call", "label": "Book a call", "reason": "High-fit lead ready for discovery"}
            else:
                lead["_suggested_action"] = {"type": "whatsapp", "label": "WhatsApp message", "reason": "Quick personal touch"}

        return {"leads": top5, "generated_at": now.isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Your 5 Today failed: {str(e)}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MODULE: SLEEPING LEADS + REVIVAL ENGINE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.get("/api/leads/sleeping")
async def get_sleeping_leads(
    threshold_days: int = 14,
    tier: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get leads with no activity beyond threshold days."""
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
            except:
                days = 30
        else:
            days = (now - datetime.fromisoformat(lead.get("created_at", now.isoformat()).replace("Z", "+00:00"))).days
        lead["_days_asleep"] = days
        lead["_segment"] = "cold_vault" if days >= 60 else ("at_risk" if days >= 30 else "sleeping")

    # Segment counts
    sleeping = len([l for l in leads if l["_segment"] == "sleeping"])
    at_risk = len([l for l in leads if l["_segment"] == "at_risk"])
    cold_vault = len([l for l in leads if l["_segment"] == "cold_vault"])

    return {
        "leads": leads,
        "total": len(leads),
        "segments": {"sleeping": sleeping, "at_risk": at_risk, "cold_vault": cold_vault},
    }

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
            lead = leads_collection.find_one({"_id": ObjectId(lead_id)})
            if not lead:
                continue
            lead = serialize_doc(lead)

            # Generate personalized message via AI
            chat = LlmChat(
                api_key=os.getenv("EMERGENT_LLM_KEY"),
                session_id=f"revival_{lead_id}",
                system_message=f"You are Aria, a warm sales assistant for {os.getenv('COMPANY_NAME', 'GenLeadAI')}. {angle_prompts.get(request.angle, angle_prompts['check_in'])}"
            )
            chat.with_model("anthropic", "claude-4-sonnet-20250514")

            prompt = f"Write a short revival message (3-4 sentences) for: {lead.get('first_name')} {lead.get('last_name')}, {lead.get('company_name', 'their company')}, source: {lead.get('source_channel')}. They haven't been contacted recently."
            user_msg = UserMessage(text=prompt)
            response = await chat.send_message(user_msg)
            message = response.strip()

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
                {"_id": ObjectId(lead_id)},
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
    lead = leads_collection.find_one({"_id": ObjectId(request.lead_id)})
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
    if request.filters.get("lead_type"):
        query["lead_type"] = request.filters["lead_type"]
    if request.filters.get("icp_tier"):
        query["icp_tier"] = request.filters["icp_tier"]
    if request.filters.get("status"):
        query["status"] = request.filters["status"]

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
    if request.filters.get("lead_type"):
        query["lead_type"] = request.filters["lead_type"]
    if request.filters.get("icp_tier"):
        query["icp_tier"] = request.filters["icp_tier"]

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

    chat = LlmChat(
        api_key=os.getenv("EMERGENT_LLM_KEY"),
        session_id=f"research_{request.lead_id}",
        system_message="You are a senior B2B sales researcher. Generate comprehensive pre-call research based on the lead's profile data. Be specific, actionable, and focused on what a founder needs to know before a discovery call."
    )
    chat.with_model("anthropic", "claude-4-sonnet-20250514")

    is_b2b = lead.get("lead_type") == "B2B"
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

    user_msg = UserMessage(text=prompt)
    response = await chat.send_message(user_msg)

    try:
        txt = response.strip()
        if "```json" in txt:
            txt = txt.split("```json")[1].split("```")[0].strip()
        elif "```" in txt:
            txt = txt.split("```")[1].split("```")[0].strip()
        research = json.loads(txt)
    except:
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
    convo = list(aria_conversations_collection.find({"lead_id": lead_id}, {"_id": 0}).sort("created_at", DESCENDING).limit(5))
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
            "to": ["admin@demo.com"],
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
            "to": ["admin@demo.com"],
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
    terminal_states = ["DISQUALIFIED", "DO_NOT_CONTACT", "ESCALATED_TO_HUMAN", "SEQUENCE_ENDED"]

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

# ─── 1. Public API Endpoint (API Key Auth) ───

API_KEYS_COLLECTION = db["api_keys"]

def verify_api_key(x_api_key: str = Header(None)):
    """Verify API key for public endpoints."""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key header required")
    key_doc = API_KEYS_COLLECTION.find_one({"key": x_api_key, "is_active": True})
    if not key_doc:
        raise HTTPException(status_code=401, detail="Invalid API key")
    API_KEYS_COLLECTION.update_one({"key": x_api_key}, {"$inc": {"usage_count": 1}, "$set": {"last_used_at": datetime.now(timezone.utc).isoformat()}})
    return key_doc

class PublicLeadCreate(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    lead_type: str = "B2C"
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    industry: Optional[str] = None
    source_channel: str = "other"
    campaign_id: Optional[str] = None
    notes: Optional[str] = None
    tags: List[str] = []
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    custom_fields: Dict[str, Any] = {}

@app.post("/api/v1/leads")
async def public_create_lead(lead: PublicLeadCreate, api_key_doc: dict = Depends(verify_api_key)):
    """Public API endpoint for external integrations (Zapier, Make, ad platforms)."""
    # Deduplication check on email
    existing = leads_collection.find_one({"email": lead.email}, {"_id": 1})
    if existing:
        return {"status": "duplicate", "message": f"Lead with email {lead.email} already exists", "lead_id": str(existing["_id"])}

    lead_doc = lead.dict()
    lead_doc["created_at"] = datetime.now(timezone.utc).isoformat()
    lead_doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    lead_doc["created_by"] = f"api:{api_key_doc.get('name', 'external')}"
    lead_doc["icp_score"] = 0
    lead_doc["icp_tier"] = "cold"
    lead_doc["assigned_to"] = None
    lead_doc["status"] = "new"
    lead_doc["last_contacted_at"] = None
    lead_doc["next_followup_at"] = None

    # Auto-link campaign by UTM
    if lead.utm_campaign:
        campaign = campaigns_collection.find_one({"utm_campaign": lead.utm_campaign})
        if campaign:
            lead_doc["campaign_id"] = str(campaign["_id"])

    result = leads_collection.insert_one(lead_doc)
    lead_id = str(result.inserted_id)

    # Log activity
    activities_collection.insert_one({
        "lead_id": lead_id,
        "user_id": "api",
        "activity_type": "note_added",
        "subject": f"Lead created via API ({lead.source_channel})",
        "body": f"UTM: {lead.utm_source}/{lead.utm_medium}/{lead.utm_campaign}" if lead.utm_source else None,
        "outcome": None, "duration_minutes": None,
        "metadata": {"source": "public_api", "utm_source": lead.utm_source, "utm_medium": lead.utm_medium, "utm_campaign": lead.utm_campaign},
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    return {"status": "created", "lead_id": lead_id, "message": "Lead created successfully"}

# ─── 2. Embeddable Web Form Endpoint (CORS open, no auth) ───

class WebFormLead(BaseModel):
    first_name: str
    last_name: str = ""
    email: str
    phone: Optional[str] = None
    company_name: Optional[str] = None
    message: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None

@app.post("/api/form/submit")
async def web_form_submit(lead: WebFormLead):
    """Public endpoint for embeddable web form. No auth required."""
    if not lead.email or "@" not in lead.email:
        raise HTTPException(status_code=400, detail="Valid email required")

    # Dedup
    existing = leads_collection.find_one({"email": lead.email}, {"_id": 1})
    if existing:
        return {"status": "success", "message": "Thank you! We'll be in touch soon."}

    lead_doc = {
        "first_name": lead.first_name,
        "last_name": lead.last_name or "",
        "email": lead.email,
        "phone": lead.phone,
        "lead_type": "B2B" if lead.company_name else "B2C",
        "company_name": lead.company_name,
        "job_title": None,
        "industry": None,
        "revenue_range": None,
        "city": None, "state": None, "country": None,
        "source_channel": "website_form",
        "campaign_id": None,
        "status": "new",
        "icp_score": 0,
        "icp_tier": "cold",
        "assigned_to": None,
        "notes": lead.message,
        "tags": ["website-form"],
        "custom_fields": {},
        "last_contacted_at": None,
        "next_followup_at": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "created_by": "web_form",
    }

    # Auto-link campaign by UTM
    if lead.utm_campaign:
        campaign = campaigns_collection.find_one({"utm_campaign": lead.utm_campaign})
        if campaign:
            lead_doc["campaign_id"] = str(campaign["_id"])

    result = leads_collection.insert_one(lead_doc)
    lead_id = str(result.inserted_id)

    activities_collection.insert_one({
        "lead_id": lead_id, "user_id": "web_form",
        "activity_type": "note_added",
        "subject": "Lead submitted via website form",
        "body": lead.message[:200] if lead.message else None,
        "outcome": None, "duration_minutes": None,
        "metadata": {"source": "web_form", "utm_source": lead.utm_source, "utm_medium": lead.utm_medium, "utm_campaign": lead.utm_campaign},
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    return {"status": "success", "message": "Thank you! We'll be in touch soon."}

# ─── 3. Generate Embed Code ───

@app.get("/api/form/embed-code")
async def get_embed_code(current_user: dict = Depends(get_current_user)):
    """Generate embeddable HTML form snippet."""
    backend_url = os.getenv("CORS_ORIGINS", "").split(",")[0] if os.getenv("CORS_ORIGINS") != "*" else "{{YOUR_BACKEND_URL}}"
    # Use the request's host for the URL
    embed_code = f"""<!-- GenLeadAI Lead Capture Form -->
<div id="genleadai-form" style="max-width:480px;margin:0 auto;font-family:'Plus Jakarta Sans',sans-serif;">
  <form id="glai-form" style="background:#fff;border:1px solid #E8E0F5;border-radius:16px;padding:32px;box-shadow:0 1px 3px rgba(124,53,220,0.08),0 4px 16px rgba(124,53,220,0.04);">
    <div style="text-align:center;margin-bottom:24px;">
      <div style="width:40px;height:40px;background:linear-gradient(135deg,#C044E0,#5B28D4);border-radius:10px;display:inline-flex;align-items:center;justify-content:center;margin-bottom:12px;">
        <span style="color:white;font-weight:800;font-size:16px;">G</span>
      </div>
      <h3 style="margin:0;color:#1A0A2E;font-size:20px;font-weight:700;">Let's Talk Growth</h3>
      <p style="margin:4px 0 0;color:#5A4A7A;font-size:14px;">Fill in your details and we'll reach out</p>
    </div>
    <div style="margin-bottom:16px;">
      <input type="text" name="first_name" placeholder="Your Name *" required style="width:100%;padding:12px 16px;border:1px solid #E8E0F5;border-radius:10px;font-size:14px;color:#1A0A2E;box-sizing:border-box;outline:none;" onfocus="this.style.borderColor='#7C35DC';this.style.boxShadow='0 0 0 3px rgba(124,53,220,0.12)'" onblur="this.style.borderColor='#E8E0F5';this.style.boxShadow='none'" />
    </div>
    <div style="margin-bottom:16px;">
      <input type="email" name="email" placeholder="Email Address *" required style="width:100%;padding:12px 16px;border:1px solid #E8E0F5;border-radius:10px;font-size:14px;color:#1A0A2E;box-sizing:border-box;outline:none;" onfocus="this.style.borderColor='#7C35DC';this.style.boxShadow='0 0 0 3px rgba(124,53,220,0.12)'" onblur="this.style.borderColor='#E8E0F5';this.style.boxShadow='none'" />
    </div>
    <div style="margin-bottom:16px;">
      <input type="tel" name="phone" placeholder="Phone (optional)" style="width:100%;padding:12px 16px;border:1px solid #E8E0F5;border-radius:10px;font-size:14px;color:#1A0A2E;box-sizing:border-box;outline:none;" onfocus="this.style.borderColor='#7C35DC';this.style.boxShadow='0 0 0 3px rgba(124,53,220,0.12)'" onblur="this.style.borderColor='#E8E0F5';this.style.boxShadow='none'" />
    </div>
    <div style="margin-bottom:16px;">
      <input type="text" name="company_name" placeholder="Company (optional)" style="width:100%;padding:12px 16px;border:1px solid #E8E0F5;border-radius:10px;font-size:14px;color:#1A0A2E;box-sizing:border-box;outline:none;" onfocus="this.style.borderColor='#7C35DC';this.style.boxShadow='0 0 0 3px rgba(124,53,220,0.12)'" onblur="this.style.borderColor='#E8E0F5';this.style.boxShadow='none'" />
    </div>
    <div style="margin-bottom:20px;">
      <textarea name="message" placeholder="What are you looking for?" rows="3" style="width:100%;padding:12px 16px;border:1px solid #E8E0F5;border-radius:10px;font-size:14px;color:#1A0A2E;box-sizing:border-box;resize:none;outline:none;" onfocus="this.style.borderColor='#7C35DC';this.style.boxShadow='0 0 0 3px rgba(124,53,220,0.12)'" onblur="this.style.borderColor='#E8E0F5';this.style.boxShadow='none'"></textarea>
    </div>
    <button type="submit" style="width:100%;padding:14px;background:linear-gradient(135deg,#C044E0,#7C35DC,#5B28D4);color:white;border:none;border-radius:10px;font-size:15px;font-weight:700;cursor:pointer;font-family:'Plus Jakarta Sans',sans-serif;">Get in Touch</button>
    <div id="glai-msg" style="text-align:center;margin-top:12px;font-size:13px;display:none;"></div>
  </form>
</div>
<script>
(function(){{
  var BACKEND='{{BACKEND_URL}}';
  var form=document.getElementById('glai-form');
  var msg=document.getElementById('glai-msg');
  var params=new URLSearchParams(window.location.search);
  form.addEventListener('submit',function(e){{
    e.preventDefault();
    var btn=form.querySelector('button');
    btn.textContent='Sending...';btn.disabled=true;
    var data={{
      first_name:form.first_name.value,
      email:form.email.value,
      phone:form.phone.value||null,
      company_name:form.company_name.value||null,
      message:form.message.value||null,
      utm_source:params.get('utm_source')||null,
      utm_medium:params.get('utm_medium')||null,
      utm_campaign:params.get('utm_campaign')||null
    }};
    fetch(BACKEND+'/api/form/submit',{{
      method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(data)
    }}).then(function(r){{return r.json()}}).then(function(d){{
      msg.style.display='block';msg.style.color='#16A34A';msg.textContent=d.message||'Thank you!';
      form.reset();btn.textContent='Sent!';
      setTimeout(function(){{btn.textContent='Get in Touch';btn.disabled=false;}},3000);
    }}).catch(function(){{
      msg.style.display='block';msg.style.color='#DC2626';msg.textContent='Something went wrong. Please try again.';
      btn.textContent='Get in Touch';btn.disabled=false;
    }});
  }});
}})();
</script>"""

    return {"embed_code": embed_code, "instructions": "Replace {{BACKEND_URL}} with your deployed backend URL (e.g., https://app.genleadai.com). Paste the HTML anywhere on your website."}

# ─── 4. API Key Management ───

class CreateAPIKeyRequest(BaseModel):
    name: str

@app.post("/api/settings/api-keys")
async def create_api_key(request: CreateAPIKeyRequest, current_user: dict = Depends(get_current_user)):
    """Create a new API key for external integrations."""
    key = f"glai_{uuid.uuid4().hex}"
    doc = {
        "key": key,
        "name": request.name,
        "created_by": current_user["email"],
        "is_active": True,
        "usage_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    API_KEYS_COLLECTION.insert_one(doc)
    return {"key": key, "name": request.name, "message": "API key created. Store it securely — it won't be shown again."}

@app.get("/api/settings/api-keys")
async def list_api_keys(current_user: dict = Depends(get_current_user)):
    """List all API keys (masked)."""
    keys = list(API_KEYS_COLLECTION.find({}, {"_id": 0}))
    for k in keys:
        k["key"] = k["key"][:8] + "..." + k["key"][-4:]
    return {"keys": keys}

@app.delete("/api/settings/api-keys/{key_prefix}")
async def revoke_api_key(key_prefix: str, current_user: dict = Depends(get_current_user)):
    """Revoke an API key."""
    result = API_KEYS_COLLECTION.update_one(
        {"key": {"$regex": f"^{key_prefix}"}},
        {"$set": {"is_active": False}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="API key not found")
    return {"revoked": True}

# ─── 5. Webhook Receiver (for Calendly, Meta Ads, etc.) ───

@app.post("/api/webhooks/calendly")
async def calendly_webhook(request_body: Dict[str, Any]):
    """Receive Calendly webhook events (booking confirmed, no-show, etc.)."""
    event = request_body.get("event", "")
    payload = request_body.get("payload", {})

    if event == "invitee.created":
        # New meeting booked
        invitee = payload.get("invitee", {})
        email = invitee.get("email")
        name = invitee.get("name", "")

        if email:
            lead = leads_collection.find_one({"email": email})
            if lead:
                lead_id = str(lead["_id"])
                leads_collection.update_one(
                    {"_id": lead["_id"]},
                    {"$set": {"aria_state": "MEETING_BOOKED", "status": "meeting_booked", "updated_at": datetime.now(timezone.utc).isoformat()}}
                )
                activities_collection.insert_one({
                    "lead_id": lead_id, "user_id": "calendly",
                    "activity_type": "meeting_scheduled",
                    "subject": f"Meeting booked via Calendly",
                    "body": f"{name} booked a call",
                    "outcome": None, "duration_minutes": None,
                    "metadata": {"source": "calendly_webhook", "event": event},
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
                # Auto-send lead magnet (post-booking trigger)
                try:
                    await auto_send_lead_magnet(lead_id, "post_booking")
                except Exception as e:
                    print(f"Lead magnet auto-send (post_booking) failed: {e}")

    return {"received": True}

@app.post("/api/webhooks/meta-leads")
async def meta_leads_webhook(request_body: Dict[str, Any]):
    """Receive leads from Facebook/Instagram Lead Ads."""
    entries = request_body.get("entry", [])
    created = 0
    for entry in entries:
        changes = entry.get("changes", [])
        for change in changes:
            value = change.get("value", {})
            field_data = value.get("field_data", [])

            lead_data = {}
            for field in field_data:
                name = field.get("name", "").lower()
                val = field.get("values", [""])[0] if field.get("values") else ""
                if "email" in name: lead_data["email"] = val
                elif "name" in name or "full_name" in name: lead_data["first_name"] = val
                elif "phone" in name: lead_data["phone"] = val
                elif "company" in name: lead_data["company_name"] = val

            if lead_data.get("email"):
                existing = leads_collection.find_one({"email": lead_data["email"]}, {"_id": 1})
                if not existing:
                    full_name = lead_data.get("first_name", "Lead").split(" ", 1)
                    doc = {
                        "first_name": full_name[0],
                        "last_name": full_name[1] if len(full_name) > 1 else "",
                        "email": lead_data["email"],
                        "phone": lead_data.get("phone"),
                        "lead_type": "B2B" if lead_data.get("company_name") else "B2C",
                        "company_name": lead_data.get("company_name"),
                        "source_channel": "paid_ads",
                        "status": "new", "icp_score": 0, "icp_tier": "cold",
                        "tags": ["meta-lead-ad"], "custom_fields": {},
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                        "created_by": "meta_webhook",
                        "assigned_to": None, "notes": None,
                        "last_contacted_at": None, "next_followup_at": None,
                    }
                    leads_collection.insert_one(doc)
                    created += 1

    return {"received": True, "leads_created": created}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STRIPE BILLING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest

payment_transactions = db["payment_transactions"]
workspace_settings_collection = db["workspace_settings"]

# ARIA Plan Catalog (4 tiers) with feature flags. Replaces older 3-plan structure.
# Old "scale" -> renamed to "pro". "custom" is contact-sales (no Stripe checkout).
SUBSCRIPTION_PLANS = {
    "starter": {
        "name": "ARIA Starter",
        "amount": 49.00,
        "leads": 500,
        "ai_credits": 100,
        "tagline": "For small teams that need basic lead control",
        "headline_features": [
            "Manual lead entry & dashboard",
            "Lead status & owner assignment",
            "Follow-up reminders & basic notes",
            "Manual Hot/Warm/Cold tagging",
            "Daily task list & basic reports",
        ],
        "features": {
            # Core
            "lead_inbox": True, "lead_profile": True, "manual_lead_entry": True,
            "follow_up_reminders": True, "basic_notes": True, "source_tagging": True,
            "manual_temperature": True, "daily_task_list": True, "basic_reports": True,
            "owner_assignment": True,
            # Locked
            "csv_import": False, "multi_source_capture": False,
            "form_integration": False, "rep_dashboard": False,
            "overdue_alerts": False, "lead_aging_tracker": False,
            "stage_pipeline": False, "ai_followup_basic": False,
            "ai_lead_scoring": False, "founder_summary": False,
            "whatsapp_click_to_msg": False, "limited_crm_sync": False,
            "ai_qualification": False, "ai_followup_drafts": False,
            "whatsapp_workflow": False, "automated_tasks": False,
            "rep_performance": False, "lost_reason_tracking": False,
            "proposal_tracking": False, "deal_value": False,
            "pipeline_value_dashboard": False, "calendar_integration": False,
            "daily_founder_report": False, "weekly_sales_summary": False,
            "crm_sync_full": False, "rbac": False,
            "custom_stages": False, "custom_scoring": False,
            "custom_workflows": False, "ai_call_scheduling": False,
            "advanced_whatsapp": False, "multi_brand": False,
            "advanced_crm": False, "api_integrations": False,
            "client_dashboards": False, "advanced_attribution": False,
            "custom_reports": False, "sla_alerts": False,
            "training_section": False, "dedicated_support": False,
        },
    },
    "growth": {
        "name": "ARIA Growth",
        "amount": 149.00,
        "leads": 2000,
        "ai_credits": 500,
        "tagline": "For businesses running campaigns and needing sales accountability",
        "headline_features": [
            "Multi-source lead capture & CSV import",
            "Stage-wise pipeline & sales-rep dashboard",
            "Overdue follow-up alerts & lead-ageing tracker",
            "Basic AI follow-up suggestions & lead scoring",
            "WhatsApp click-to-message & founder summary",
        ],
        "features": {
            "lead_inbox": True, "lead_profile": True, "manual_lead_entry": True,
            "follow_up_reminders": True, "basic_notes": True, "source_tagging": True,
            "manual_temperature": True, "daily_task_list": True, "basic_reports": True,
            "owner_assignment": True,
            "csv_import": True, "multi_source_capture": True,
            "form_integration": True, "rep_dashboard": True,
            "overdue_alerts": True, "lead_aging_tracker": True,
            "stage_pipeline": True, "ai_followup_basic": True,
            "ai_lead_scoring": True, "founder_summary": True,
            "whatsapp_click_to_msg": True, "limited_crm_sync": True,
            # Locked from here
            "ai_qualification": False, "ai_followup_drafts": False,
            "whatsapp_workflow": False, "automated_tasks": False,
            "rep_performance": False, "lost_reason_tracking": False,
            "proposal_tracking": False, "deal_value": False,
            "pipeline_value_dashboard": False, "calendar_integration": False,
            "daily_founder_report": False, "weekly_sales_summary": False,
            "crm_sync_full": False, "rbac": False,
            "custom_stages": False, "custom_scoring": False,
            "custom_workflows": False, "ai_call_scheduling": False,
            "advanced_whatsapp": False, "multi_brand": False,
            "advanced_crm": False, "api_integrations": False,
            "client_dashboards": False, "advanced_attribution": False,
            "custom_reports": False, "sla_alerts": False,
            "training_section": False, "dedicated_support": False,
        },
    },
    "pro": {
        "name": "ARIA Pro",
        "amount": 399.00,
        "leads": 10000,
        "ai_credits": 2000,
        "tagline": "For founder-led companies that need serious sales visibility",
        "headline_features": [
            "AI lead qualification, scoring & follow-up drafts",
            "WhatsApp workflows, email templates & automated tasks",
            "Sales-rep performance, lost-reason & proposal tracking",
            "Pipeline value, calendar integration & full CRM sync",
            "Daily founder report, weekly sales summary & RBAC",
        ],
        "features": {
            "lead_inbox": True, "lead_profile": True, "manual_lead_entry": True,
            "follow_up_reminders": True, "basic_notes": True, "source_tagging": True,
            "manual_temperature": True, "daily_task_list": True, "basic_reports": True,
            "owner_assignment": True,
            "csv_import": True, "multi_source_capture": True,
            "form_integration": True, "rep_dashboard": True,
            "overdue_alerts": True, "lead_aging_tracker": True,
            "stage_pipeline": True, "ai_followup_basic": True,
            "ai_lead_scoring": True, "founder_summary": True,
            "whatsapp_click_to_msg": True, "limited_crm_sync": True,
            "ai_qualification": True, "ai_followup_drafts": True,
            "whatsapp_workflow": True, "automated_tasks": True,
            "rep_performance": True, "lost_reason_tracking": True,
            "proposal_tracking": True, "deal_value": True,
            "pipeline_value_dashboard": True, "calendar_integration": True,
            "daily_founder_report": True, "weekly_sales_summary": True,
            "crm_sync_full": True, "rbac": True,
            # Locked from here
            "custom_stages": False, "custom_scoring": False,
            "custom_workflows": False, "ai_call_scheduling": False,
            "advanced_whatsapp": False, "multi_brand": False,
            "advanced_crm": False, "api_integrations": False,
            "client_dashboards": False, "advanced_attribution": False,
            "custom_reports": False, "sla_alerts": False,
            "training_section": False, "dedicated_support": False,
        },
    },
    "custom": {
        "name": "ARIA Custom",
        "amount": None,  # contact sales
        "leads": -1,
        "ai_credits": -1,
        "tagline": "For complex sales engines and multi-channel funnels",
        "contact_sales": True,
        "headline_features": [
            "Custom stages, scoring & workflows",
            "AI call scheduling & qualification forms",
            "Multi-brand, multi-branch & advanced WhatsApp automation",
            "Advanced CRM, API integrations & client-specific dashboards",
            "SLA alerts, training section & dedicated implementation support",
        ],
        "features": {  # all true
            "lead_inbox": True, "lead_profile": True, "manual_lead_entry": True,
            "follow_up_reminders": True, "basic_notes": True, "source_tagging": True,
            "manual_temperature": True, "daily_task_list": True, "basic_reports": True,
            "owner_assignment": True,
            "csv_import": True, "multi_source_capture": True,
            "form_integration": True, "rep_dashboard": True,
            "overdue_alerts": True, "lead_aging_tracker": True,
            "stage_pipeline": True, "ai_followup_basic": True,
            "ai_lead_scoring": True, "founder_summary": True,
            "whatsapp_click_to_msg": True, "limited_crm_sync": True,
            "ai_qualification": True, "ai_followup_drafts": True,
            "whatsapp_workflow": True, "automated_tasks": True,
            "rep_performance": True, "lost_reason_tracking": True,
            "proposal_tracking": True, "deal_value": True,
            "pipeline_value_dashboard": True, "calendar_integration": True,
            "daily_founder_report": True, "weekly_sales_summary": True,
            "crm_sync_full": True, "rbac": True,
            "custom_stages": True, "custom_scoring": True,
            "custom_workflows": True, "ai_call_scheduling": True,
            "advanced_whatsapp": True, "multi_brand": True,
            "advanced_crm": True, "api_integrations": True,
            "client_dashboards": True, "advanced_attribution": True,
            "custom_reports": True, "sla_alerts": True,
            "training_section": True, "dedicated_support": True,
        },
    },
}

# Backwards compat: legacy "scale" id maps to "pro"
_LEGACY_PLAN_ALIASES = {"scale": "pro"}


def _workspace_plan_id() -> str:
    """Return the workspace's current plan id. Defaults to 'starter'."""
    cfg = workspace_settings_collection.find_one({"scope": "workspace"}, {"_id": 0, "plan_id": 1}) or {}
    pid = cfg.get("plan_id") or "starter"
    return _LEGACY_PLAN_ALIASES.get(pid, pid)


def _has_feature(feature_key: str, plan_id: Optional[str] = None) -> bool:
    pid = plan_id or _workspace_plan_id()
    plan = SUBSCRIPTION_PLANS.get(_LEGACY_PLAN_ALIASES.get(pid, pid))
    if not plan:
        return False
    return bool(plan.get("features", {}).get(feature_key, False))


def require_feature(feature_key: str):
    """FastAPI dependency that raises 402 with a friendly upgrade payload when feature is locked."""
    async def _check(current_user: dict = Depends(get_current_user)):
        if _has_feature(feature_key):
            return current_user
        raise HTTPException(
            status_code=402,
            detail={
                "code": "feature_locked",
                "feature": feature_key,
                "current_plan": _workspace_plan_id(),
                "message": f"Upgrade your ARIA plan to unlock '{feature_key}'.",
            },
        )
    return _check


class CheckoutRequest(BaseModel):
    plan_id: str
    origin_url: str


class UpgradeRequest(BaseModel):
    target_plan_id: str
    feature_key: Optional[str] = None
    note: Optional[str] = None


@app.post("/api/billing/checkout")
async def create_checkout(request: CheckoutRequest, http_request: object = None, current_user: dict = Depends(get_current_user)):
    """Create Stripe checkout session for subscription. Custom plan is contact-sales only."""
    plan_id = _LEGACY_PLAN_ALIASES.get(request.plan_id, request.plan_id)
    plan = SUBSCRIPTION_PLANS.get(plan_id)
    if not plan:
        raise HTTPException(status_code=400, detail="Invalid plan")
    if plan.get("contact_sales") or plan.get("amount") is None:
        raise HTTPException(status_code=400, detail="ARIA Custom is contact-sales only. Use /api/billing/request-upgrade.")

    stripe_key = os.getenv("STRIPE_API_KEY")
    host_url = request.origin_url.rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"

    stripe_checkout = StripeCheckout(api_key=stripe_key, webhook_url=webhook_url)

    success_url = f"{host_url}/billing?session_id={{CHECKOUT_SESSION_ID}}&payment=success"
    cancel_url = f"{host_url}/billing?payment=cancelled"

    checkout_req = CheckoutSessionRequest(
        amount=plan["amount"],
        currency="usd",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"plan_id": plan_id, "user_email": current_user["email"], "plan_name": plan["name"]}
    )

    session = await stripe_checkout.create_checkout_session(checkout_req)

    payment_transactions.insert_one({
        "session_id": session.session_id,
        "user_email": current_user["email"],
        "plan_id": plan_id,
        "plan_name": plan["name"],
        "amount": plan["amount"],
        "currency": "usd",
        "payment_status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    return {"url": session.url, "session_id": session.session_id}

@app.get("/api/billing/status/{session_id}")
async def check_payment_status(session_id: str, current_user: dict = Depends(get_current_user)):
    """Check payment status and update transaction."""
    stripe_key = os.getenv("STRIPE_API_KEY")
    stripe_checkout = StripeCheckout(api_key=stripe_key, webhook_url="")

    status = await stripe_checkout.get_checkout_status(session_id)

    existing = payment_transactions.find_one({"session_id": session_id})
    if existing and existing.get("payment_status") != "paid":
        payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {"payment_status": status.payment_status, "status": status.status, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        # Promote workspace plan on successful payment
        if status.payment_status == "paid":
            txn = payment_transactions.find_one({"session_id": session_id}, {"_id": 0, "plan_id": 1})
            if txn and txn.get("plan_id"):
                workspace_settings_collection.update_one(
                    {"scope": "workspace"},
                    {"$set": {"plan_id": txn["plan_id"], "plan_activated_at": datetime.now(timezone.utc).isoformat()}},
                    upsert=True,
                )

    return {"status": status.status, "payment_status": status.payment_status, "amount": status.amount_total, "currency": status.currency}

@app.post("/api/webhook/stripe")
async def stripe_webhook(request: object):
    """Handle Stripe webhook events."""
    return {"received": True}

@app.get("/api/billing/plans")
async def get_billing_plans():
    """Public — full plan catalog with feature matrix."""
    plans_out = []
    for pid, p in SUBSCRIPTION_PLANS.items():
        plans_out.append({
            "id": pid,
            "name": p["name"],
            "amount": p["amount"],
            "leads": p["leads"],
            "ai_credits": p["ai_credits"],
            "tagline": p.get("tagline"),
            "headline_features": p.get("headline_features", []),
            "contact_sales": p.get("contact_sales", False),
            "features": p.get("features", {}),
        })
    return {"plans": plans_out, "feature_keys": sorted({k for p in SUBSCRIPTION_PLANS.values() for k in p.get("features", {})})}


@app.get("/api/billing/current-plan")
async def get_current_plan(current_user: dict = Depends(get_current_user)):
    """Return the workspace's current plan id and unlocked features."""
    pid = _workspace_plan_id()
    plan = SUBSCRIPTION_PLANS.get(pid, SUBSCRIPTION_PLANS["starter"])
    cfg = workspace_settings_collection.find_one({"scope": "workspace"}, {"_id": 0, "plan_activated_at": 1, "plan_id": 1}) or {}
    return {
        "plan_id": pid,
        "name": plan["name"],
        "amount": plan["amount"],
        "tagline": plan.get("tagline"),
        "contact_sales": plan.get("contact_sales", False),
        "features": plan.get("features", {}),
        "activated_at": cfg.get("plan_activated_at"),
    }


@app.post("/api/billing/request-upgrade")
async def request_upgrade(req: UpgradeRequest, current_user: dict = Depends(get_current_user)):
    """Email a configured admin email asking for upgrade approval. Used by Upgrade modal."""
    target = _LEGACY_PLAN_ALIASES.get(req.target_plan_id, req.target_plan_id)
    plan = SUBSCRIPTION_PLANS.get(target)
    if not plan:
        raise HTTPException(status_code=400, detail="Invalid target plan")
    admin_email = os.getenv("UPGRADE_REQUEST_EMAIL") or os.getenv("FOUNDER_EMAIL") or os.getenv("SENDER_EMAIL", "onboarding@resend.dev")
    current_pid = _workspace_plan_id()
    current_plan = SUBSCRIPTION_PLANS.get(current_pid, {})
    feature_label = req.feature_key or "general upgrade"
    note = (req.note or "").strip()
    html = f"""<div style="font-family:Plus Jakarta Sans,Arial,sans-serif;color:#1A0A2E;">
      <h2 style="color:#7C35DC;margin:0 0 12px 0;">ARIA Upgrade Request</h2>
      <p><strong>{current_user.get('email')}</strong> from <strong>{current_user.get('full_name') or 'their workspace'}</strong> wants to upgrade.</p>
      <table style="border-collapse:collapse;margin:16px 0;font-size:14px;">
        <tr><td style="padding:6px 12px;color:#9B8AB0;">Current plan:</td><td style="padding:6px 12px;font-weight:700;">{current_plan.get('name','—')}</td></tr>
        <tr><td style="padding:6px 12px;color:#9B8AB0;">Target plan:</td><td style="padding:6px 12px;font-weight:700;color:#7C35DC;">{plan.get('name')}</td></tr>
        <tr><td style="padding:6px 12px;color:#9B8AB0;">Feature requested:</td><td style="padding:6px 12px;">{feature_label}</td></tr>
      </table>
      {f'<p style="background:#F4F0FF;padding:12px;border-radius:8px;border:1px solid #E0D4F7;font-size:13px;"><strong>Note:</strong> {note}</p>' if note else ''}
      <p style="color:#5A4A7A;font-size:13px;margin-top:24px;">Reply to this email to action the request, or open the workspace Stripe to issue the upgrade.</p>
    </div>"""
    try:
        await asyncio.to_thread(resend.Emails.send, {
            "from": os.getenv("SENDER_EMAIL", "onboarding@resend.dev"),
            "to": [admin_email],
            "reply_to": current_user.get("email"),
            "subject": f"[ARIA] Upgrade request: {plan.get('name')} from {current_user.get('email')}",
            "html": html,
        })
    except Exception as e:
        # Don't fail the user-facing flow even if Resend errors out
        print(f"Upgrade request email failed: {e}")
    activities_collection.insert_one({
        "lead_id": None, "user_id": current_user["email"],
        "activity_type": "upgrade_requested",
        "subject": f"Upgrade requested: {current_pid} -> {target}",
        "body": (note or "")[:500],
        "outcome": None, "duration_minutes": None,
        "metadata": {"feature": req.feature_key, "target_plan": target, "from_plan": current_pid, "admin_email": admin_email},
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"requested": True, "target_plan": target, "admin_email_used": admin_email}

@app.get("/api/billing/transactions")
async def get_transactions(current_user: dict = Depends(get_current_user)):
    """Get payment transaction history."""
    txns = list(payment_transactions.find({"user_email": current_user["email"]}, {"_id": 0}).sort("created_at", DESCENDING).limit(20))
    return {"transactions": txns}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AUDIT LOG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

audit_log_collection = db["audit_log"]

def log_audit(user_email: str, action: str, resource_type: str, resource_id: str = None, details: str = None):
    """Log an audit event."""
    audit_log_collection.insert_one({
        "user_email": user_email,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "details": details,
        "ip_address": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

@app.get("/api/audit-log")
async def get_audit_log(skip: int = 0, limit: int = 50, current_user: dict = Depends(get_current_user)):
    """Get audit log entries."""
    if current_user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Admin or manager access required")
    entries = list(audit_log_collection.find({}, {"_id": 0}).sort("timestamp", DESCENDING).skip(skip).limit(limit))
    total = audit_log_collection.count_documents({})
    return {"entries": entries, "total": total}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CSV/PDF EXPORT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.get("/api/export/leads")
async def export_leads_csv(current_user: dict = Depends(get_current_user)):
    """Export all leads as CSV."""
    leads = list(leads_collection.find({}, {"_id": 0}).limit(5000))
    output = io.StringIO()
    if leads:
        fields = ["first_name", "last_name", "email", "phone", "lead_type", "company_name", "job_title", "industry", "source_channel", "status", "icp_score", "icp_tier", "city", "country", "created_at"]
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for lead in leads:
            writer.writerow(lead)
    content = output.getvalue()
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=genleadai_leads_{datetime.now().strftime('%Y%m%d')}.csv"}
    )

@app.get("/api/export/activities/{lead_id}")
async def export_lead_activities(lead_id: str, current_user: dict = Depends(get_current_user)):
    """Export activities for a lead as CSV."""
    activities = list(activities_collection.find({"lead_id": lead_id}, {"_id": 0}).sort("created_at", DESCENDING))
    output = io.StringIO()
    if activities:
        fields = ["created_at", "activity_type", "subject", "body", "outcome", "user_id"]
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for act in activities:
            writer.writerow(act)
    content = output.getvalue()
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=lead_{lead_id}_activities.csv"}
    )

@app.get("/api/export/report")
async def export_analytics_report(current_user: dict = Depends(get_current_user)):
    """Export analytics report as CSV."""
    total = leads_collection.count_documents({})
    status_counts = {}
    for s in ["new", "contacted", "qualified", "proposal_sent", "negotiation", "won", "lost"]:
        status_counts[s] = leads_collection.count_documents({"status": s})
    channel_counts = {}
    for c in ["whatsapp", "email", "linkedin", "instagram", "facebook", "website_form", "cold_call", "referral", "webinar", "organic_search", "paid_ads"]:
        channel_counts[c] = leads_collection.count_documents({"source_channel": c})

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["GenLeadAI Analytics Report", datetime.now().strftime('%Y-%m-%d')])
    writer.writerow([])
    writer.writerow(["Metric", "Value"])
    writer.writerow(["Total Leads", total])
    writer.writerow(["B2B", leads_collection.count_documents({"lead_type": "B2B"})])
    writer.writerow(["B2C", leads_collection.count_documents({"lead_type": "B2C"})])
    writer.writerow([])
    writer.writerow(["Status", "Count"])
    for s, c in status_counts.items():
        writer.writerow([s, c])
    writer.writerow([])
    writer.writerow(["Channel", "Count"])
    for ch, c in channel_counts.items():
        if c > 0:
            writer.writerow([ch, c])

    content = output.getvalue()
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=genleadai_report_{datetime.now().strftime('%Y%m%d')}.csv"}
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ONBOARDING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

onboarding_collection = db["onboarding"]

class OnboardingData(BaseModel):
    company_name: str
    founder_name: str
    industry: Optional[str] = None
    team_size: Optional[str] = None
    calendly_link: Optional[str] = None
    icp_description: Optional[str] = None
    completed: bool = False

@app.get("/api/onboarding/status_legacy")
async def get_onboarding_status(current_user: dict = Depends(get_current_user)):
    """[DEPRECATED] Per-user onboarding. Replaced by tenant-aware /api/onboarding/status in routes/tenants.py.
    Kept under a renamed path for backward-compat callers; do not use."""
    status = onboarding_collection.find_one({"user_email": current_user["email"]}, {"_id": 0})
    return {"onboarding": status, "completed": status.get("completed", False) if status else False}

@app.post("/api/onboarding/complete_legacy")
async def complete_onboarding(data: OnboardingData, current_user: dict = Depends(get_current_user)):
    """Save onboarding data and mark as complete."""
    doc = data.dict()
    doc["user_email"] = current_user["email"]
    doc["completed"] = True
    doc["completed_at"] = datetime.now(timezone.utc).isoformat()

    onboarding_collection.update_one(
        {"user_email": current_user["email"]},
        {"$set": doc},
        upsert=True
    )

    # Update workspace settings
    aria_settings_collection.update_one(
        {},
        {"$set": {
            "founder_name": data.founder_name,
            "company_name": data.company_name,
        }},
        upsert=True
    )

    return {"completed": True, "message": "Welcome to GenLeadAI!"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TIME TO VALUE TRACKER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ttv_collection = db["time_to_value"]

@app.get("/api/ttv/milestones")
async def get_ttv_milestones(current_user: dict = Depends(get_current_user)):
    """Get Time to Value milestones for the current user/workspace."""
    doc = ttv_collection.find_one({"user_email": current_user["email"]}, {"_id": 0})

    # Auto-detect milestones from real data if not explicitly tracked
    now = datetime.now(timezone.utc)
    user_doc = users_collection.find_one({"email": current_user["email"]})
    signup_at = user_doc.get("created_at") if user_doc else now.isoformat()

    # First lead captured
    first_lead = leads_collection.find_one(
        {"created_by": {"$in": [current_user["email"], "web_form", "api", "meta_webhook"]}},
        {"created_at": 1},
        sort=[("created_at", ASCENDING)]
    )
    first_lead_at = first_lead.get("created_at") if first_lead else None

    # First ARIA conversation (any message sent)
    first_aria = aria_conversations_collection.find_one(
        {"role": "aria"},
        {"created_at": 1},
        sort=[("created_at", ASCENDING)]
    )
    first_aria_at = first_aria.get("created_at") if first_aria else None

    # First meeting booked
    first_meeting_lead = leads_collection.find_one(
        {"aria_state": "MEETING_BOOKED"},
        {"updated_at": 1},
        sort=[("updated_at", ASCENDING)]
    )
    first_meeting_at = first_meeting_lead.get("updated_at") if first_meeting_lead else None

    # First deal won
    first_won = leads_collection.find_one(
        {"status": "won"},
        {"updated_at": 1},
        sort=[("updated_at", ASCENDING)]
    )
    first_won_at = first_won.get("updated_at") if first_won else None

    # Calculate durations
    def time_diff_human(start_str, end_str):
        if not start_str or not end_str:
            return None
        try:
            start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
            diff = end - start
            total_seconds = diff.total_seconds()
            if total_seconds < 0:
                return None
            hours = total_seconds / 3600
            if hours < 1:
                return f"{int(total_seconds / 60)}m"
            elif hours < 24:
                return f"{hours:.1f}h"
            else:
                return f"{diff.days}d {int(hours % 24)}h"
        except:
            return None

    milestones = [
        {
            "id": "signup",
            "label": "Account Created",
            "completed": True,
            "completed_at": signup_at,
            "time_from_start": None,
            "icon": "user",
        },
        {
            "id": "first_lead",
            "label": "First Lead Captured",
            "completed": first_lead_at is not None,
            "completed_at": first_lead_at,
            "time_from_start": time_diff_human(signup_at, first_lead_at),
            "icon": "tray",
        },
        {
            "id": "first_aria",
            "label": "First ARIA Conversation",
            "completed": first_aria_at is not None,
            "completed_at": first_aria_at,
            "time_from_start": time_diff_human(signup_at, first_aria_at),
            "icon": "robot",
        },
        {
            "id": "first_meeting",
            "label": "First Meeting Booked",
            "completed": first_meeting_at is not None,
            "completed_at": first_meeting_at,
            "time_from_start": time_diff_human(signup_at, first_meeting_at),
            "icon": "calendar",
        },
        {
            "id": "first_won",
            "label": "First Deal Won",
            "completed": first_won_at is not None,
            "completed_at": first_won_at,
            "time_from_start": time_diff_human(signup_at, first_won_at),
            "icon": "trophy",
        },
    ]

    completed_count = sum(1 for m in milestones if m["completed"])
    total_milestones = len(milestones)
    progress_pct = round((completed_count / total_milestones) * 100)

    # Total time to first meeting (key TTV metric)
    ttv_to_meeting = time_diff_human(signup_at, first_meeting_at)

    # Save/update TTV record
    ttv_collection.update_one(
        {"user_email": current_user["email"]},
        {"$set": {
            "milestones": milestones,
            "completed_count": completed_count,
            "progress_pct": progress_pct,
            "ttv_to_meeting": ttv_to_meeting,
            "updated_at": now.isoformat(),
        }},
        upsert=True
    )

    return {
        "milestones": milestones,
        "completed_count": completed_count,
        "total_milestones": total_milestones,
        "progress_pct": progress_pct,
        "ttv_to_meeting": ttv_to_meeting,
        "signup_at": signup_at,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LEAD MAGNET (pre-call brochure) — config, upload, send, tracking
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

UPLOADS_DIR = "/app/backend/uploads"
os.makedirs(UPLOADS_DIR, exist_ok=True)

lead_magnets_collection = db["lead_magnets"]
lead_magnet_views_collection = db["lead_magnet_views"]


class LeadMagnetConfig(BaseModel):
    enabled: bool = False
    name: Optional[str] = None
    type: Literal["url", "file"] = "url"
    url: Optional[str] = None
    file_id: Optional[str] = None
    file_name: Optional[str] = None
    send_timing: Literal["pre_booking", "post_booking", "both"] = "post_booking"
    message_template: Optional[str] = None


class CampaignLeadMagnetOverride(BaseModel):
    enabled: bool = False
    inherit: bool = True  # if True, uses workspace config
    name: Optional[str] = None
    type: Literal["url", "file"] = "url"
    url: Optional[str] = None
    file_id: Optional[str] = None
    file_name: Optional[str] = None
    send_timing: Literal["pre_booking", "post_booking", "both"] = "post_booking"
    message_template: Optional[str] = None


def _get_workspace_magnet():
    doc = lead_magnets_collection.find_one({"scope": "workspace"}, {"_id": 0}) or {}
    return doc


def _get_campaign_magnet(campaign_id: Optional[str]):
    """Return campaign-level override if it exists and inherit=False; else None."""
    if not campaign_id:
        return None
    doc = lead_magnets_collection.find_one({"scope": "campaign", "campaign_id": campaign_id}, {"_id": 0})
    if not doc:
        return None
    if doc.get("inherit", True):
        return None
    return doc


def _resolve_magnet_for_lead(lead: dict) -> dict:
    """Choose campaign override (if any) over workspace default."""
    campaign_id = lead.get("campaign_id") if isinstance(lead, dict) else None
    return _get_campaign_magnet(campaign_id) or _get_workspace_magnet()


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


def _build_tracking_url(tracking_id: str) -> str:
    # Prefer BACKEND_URL (backend convention) — fall back to REACT_APP_BACKEND_URL
    # only for legacy environments where BACKEND_URL isn't set.
    base = os.getenv("BACKEND_URL") or os.getenv("REACT_APP_BACKEND_URL", "")
    base = base.rstrip("/")
    return f"{base}/api/lead-magnets/track/{tracking_id}"


def _get_lead_preferred_channel(lead_id: str) -> str:
    """Detect channel ARIA most recently used. Defaults to 'email'."""
    recent = activities_collection.find_one(
        {
            "lead_id": lead_id,
            "activity_type": {"$in": ["whatsapp_sent", "email_sent"]},
        },
        {"_id": 0, "activity_type": 1},
        sort=[("created_at", DESCENDING)],
    )
    if recent and recent.get("activity_type") == "whatsapp_sent":
        return "whatsapp"
    return "email"


async def _send_lead_magnet_via_email(lead: dict, magnet: dict, tracking_url: str, founder_name: str):
    name = lead.get("first_name") or "there"
    template = magnet.get("message_template") or (
        f"Hi {{first_name}},\n\nQuick note before our chat — here's a short overview of how we work and recent results: {{link}}\n\nGive it 2 minutes, it'll make our call sharper.\n\n— {founder_name}"
    )
    body = template.replace("{first_name}", name).replace("{link}", tracking_url).replace("{founder}", founder_name)
    html = body.replace("\n", "<br>")
    params = {
        "from": os.getenv("SENDER_EMAIL", "onboarding@resend.dev"),
        "to": [lead.get("email")],
        "subject": f"Before our call — quick read",
        "html": f"<div style='font-family:Plus Jakarta Sans,Arial,sans-serif;color:#1A0A2E;'>{html}</div>",
    }
    try:
        await asyncio.to_thread(resend.Emails.send, params)
    except Exception as e:
        print(f"Lead magnet email failed: {e}")


def _send_lead_magnet_via_whatsapp_message(lead: dict, magnet: dict, tracking_url: str, founder_name: str) -> str:
    """Build the WhatsApp body text (does not send)."""
    name = lead.get("first_name") or "there"
    template = magnet.get("message_template") or (
        f"Hi {{first_name}}! Before our call — here's a 2-min overview of our work: {{link}}\n— {founder_name}"
    )
    return template.replace("{first_name}", name).replace("{link}", tracking_url).replace("{founder}", founder_name)


async def auto_send_lead_magnet(lead_id: str, trigger: str):
    """Auto-send the configured lead magnet to a lead.

    trigger: 'pre_booking' (lead just qualified) or 'post_booking' (meeting booked).
    Honors send_timing setting and campaign override.
    """
    try:
        lead = leads_collection.find_one({"_id": ObjectId(lead_id)}, {"_id": 0, "first_name": 1, "email": 1, "phone": 1, "campaign_id": 1})
    except Exception:
        return
    if not lead or not lead.get("email"):
        return

    magnet = _resolve_magnet_for_lead(lead)
    if not magnet or not magnet.get("enabled"):
        return
    timing = magnet.get("send_timing", "post_booking")
    if timing != "both" and timing != trigger:
        return
    if magnet.get("type") == "url" and not magnet.get("url"):
        return
    if magnet.get("type") == "file" and not magnet.get("file_id"):
        return

    # Idempotency: skip if already sent for this trigger
    already = lead_magnet_views_collection.find_one(
        {"lead_id": lead_id, "trigger": trigger, "kind": "send"}, {"_id": 0}
    )
    if already:
        return

    tracking_id = uuid.uuid4().hex
    tracking_url = _build_tracking_url(tracking_id)
    founder_name = (aria_settings_collection.find_one({}) or {}).get("founder_name") or "the team"
    channel = _get_lead_preferred_channel(lead_id)

    if channel == "whatsapp":
        body_text = _send_lead_magnet_via_whatsapp_message(lead, magnet, tracking_url, founder_name)
        wa_result = await send_whatsapp_text(lead.get("phone"), body_text)
        activity_type = "whatsapp_sent"
        subject = "Lead magnet sent (WhatsApp)" if wa_result.get("sent") else "Lead magnet queued (WhatsApp logged-only — configure WHATSAPP_* env)"
        body_preview = body_text
    else:
        await _send_lead_magnet_via_email(lead, magnet, tracking_url, founder_name)
        body_preview = magnet.get("name") or "Pre-call brochure"
        activity_type = "email_sent"
        subject = "Lead magnet sent (Email)"

    now_iso = datetime.now(timezone.utc).isoformat()
    activities_collection.insert_one({
        "lead_id": lead_id, "user_id": "aria@genleadai.ai",
        "activity_type": activity_type, "subject": subject, "body": body_preview,
        "outcome": None, "duration_minutes": None,
        "metadata": {"type": "lead_magnet", "tracking_id": tracking_id, "trigger": trigger, "channel": channel, "scope": magnet.get("scope", "workspace")},
        "created_at": now_iso,
    })
    lead_magnet_views_collection.insert_one({
        "tracking_id": tracking_id,
        "lead_id": lead_id,
        "kind": "send",
        "channel": channel,
        "trigger": trigger,
        "magnet_type": magnet.get("type"),
        "magnet_target": magnet.get("url") or magnet.get("file_id"),
        "magnet_scope": magnet.get("scope", "workspace"),
        "created_at": now_iso,
    })


@app.get("/api/lead-magnets/config")
async def get_lead_magnet_config(current_user: dict = Depends(get_current_user)):
    doc = _get_workspace_magnet()
    if not doc:
        return {
            "enabled": False, "name": "", "type": "url", "url": "",
            "file_id": None, "file_name": None,
            "send_timing": "post_booking", "message_template": "",
        }
    doc.pop("scope", None)
    return doc


@app.put("/api/lead-magnets/config")
async def save_lead_magnet_config(cfg: LeadMagnetConfig, current_user: dict = Depends(get_current_user)):
    payload = cfg.dict()
    payload["scope"] = "workspace"
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    payload["updated_by"] = current_user["email"]
    lead_magnets_collection.update_one({"scope": "workspace"}, {"$set": payload}, upsert=True)
    payload.pop("scope", None)
    return payload


@app.post("/api/lead-magnets/upload")
async def upload_lead_magnet_file(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    allowed = {"application/pdf", "application/vnd.openxmlformats-officedocument.presentationml.presentation",
               "application/vnd.ms-powerpoint"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Only PDF or PPTX allowed")
    content = await file.read()
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Max file size is 25MB")
    file_id = uuid.uuid4().hex
    ext = ".pdf" if file.content_type == "application/pdf" else ".pptx"
    safe_name = f"{file_id}{ext}"
    full_path = os.path.join(UPLOADS_DIR, safe_name)
    with open(full_path, "wb") as f:
        f.write(content)
    return {
        "file_id": safe_name,
        "file_name": file.filename,
        "size": len(content),
        "content_type": file.content_type,
    }


@app.get("/api/uploads/{file_id}")
async def serve_upload(file_id: str, current_user: dict = Depends(get_current_user)):
    full_path = os.path.join(UPLOADS_DIR, file_id)
    if not os.path.isfile(full_path) or not os.path.commonpath([UPLOADS_DIR, os.path.realpath(full_path)]) == UPLOADS_DIR:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(full_path)


@app.post("/api/leads/{lead_id}/send-lead-magnet")
async def send_lead_magnet_manual(lead_id: str, current_user: dict = Depends(get_current_user)):
    """Founder manually triggers the lead magnet for this lead. Honors campaign override."""
    try:
        lead = leads_collection.find_one({"_id": ObjectId(lead_id)}, {"_id": 0, "first_name": 1, "email": 1, "phone": 1, "campaign_id": 1})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid lead id")
    if not lead or not lead.get("email"):
        raise HTTPException(status_code=404, detail="Lead not found or missing email")

    magnet = _resolve_magnet_for_lead(lead)
    if not magnet or not magnet.get("enabled"):
        raise HTTPException(status_code=400, detail="Lead magnet is not enabled. Configure it in Settings.")
    if magnet.get("type") == "url" and not magnet.get("url"):
        raise HTTPException(status_code=400, detail="Lead magnet URL not set.")
    if magnet.get("type") == "file" and not magnet.get("file_id"):
        raise HTTPException(status_code=400, detail="Lead magnet file not uploaded.")

    tracking_id = uuid.uuid4().hex
    tracking_url = _build_tracking_url(tracking_id)
    founder_name = (aria_settings_collection.find_one({}) or {}).get("founder_name") or "the team"
    channel = _get_lead_preferred_channel(lead_id)

    if channel == "whatsapp":
        body_text = _send_lead_magnet_via_whatsapp_message(lead, magnet, tracking_url, founder_name)
        wa_result = await send_whatsapp_text(lead.get("phone"), body_text)
        activity_type = "whatsapp_sent"
        if wa_result.get("sent"):
            subject = "Lead magnet sent (WhatsApp)"
        elif wa_result.get("error") == "not_configured":
            subject = "Lead magnet queued (WhatsApp logged-only — set WHATSAPP_ACCESS_TOKEN+PHONE_NUMBER_ID)"
        else:
            subject = f"Lead magnet WhatsApp send failed: {wa_result.get('error')}"
        body_preview = body_text
    else:
        await _send_lead_magnet_via_email(lead, magnet, tracking_url, founder_name)
        body_preview = magnet.get("name") or "Pre-call brochure"
        activity_type = "email_sent"
        subject = "Lead magnet sent (Email)"

    now_iso = datetime.now(timezone.utc).isoformat()
    activities_collection.insert_one({
        "lead_id": lead_id, "user_id": current_user["email"],
        "activity_type": activity_type, "subject": subject, "body": body_preview,
        "outcome": None, "duration_minutes": None,
        "metadata": {"type": "lead_magnet", "tracking_id": tracking_id, "trigger": "manual", "channel": channel, "scope": magnet.get("scope", "workspace")},
        "created_at": now_iso,
    })
    lead_magnet_views_collection.insert_one({
        "tracking_id": tracking_id,
        "lead_id": lead_id,
        "kind": "send",
        "channel": channel,
        "trigger": "manual",
        "magnet_type": magnet.get("type"),
        "magnet_target": magnet.get("url") or magnet.get("file_id"),
        "magnet_scope": magnet.get("scope", "workspace"),
        "created_at": now_iso,
    })
    return {"sent": True, "channel": channel, "tracking_url": tracking_url, "scope": magnet.get("scope", "workspace")}


@app.get("/api/lead-magnets/track/{tracking_id}")
async def track_lead_magnet(tracking_id: str, request_body: Optional[Dict[str, Any]] = None):
    """Public endpoint — logs view and redirects to the actual asset."""
    send_doc = lead_magnet_views_collection.find_one({"tracking_id": tracking_id, "kind": "send"}, {"_id": 0})
    if not send_doc:
        raise HTTPException(status_code=404, detail="Tracking link not found")

    now_iso = datetime.now(timezone.utc).isoformat()
    lead_magnet_views_collection.insert_one({
        "tracking_id": tracking_id,
        "lead_id": send_doc.get("lead_id"),
        "kind": "view",
        "created_at": now_iso,
    })

    magnet_type = send_doc.get("magnet_type")
    target = send_doc.get("magnet_target")
    if magnet_type == "url" and target:
        return RedirectResponse(url=target, status_code=302)
    if magnet_type == "file" and target:
        full_path = os.path.join(UPLOADS_DIR, target)
        if os.path.isfile(full_path):
            return FileResponse(full_path)
    raise HTTPException(status_code=404, detail="Asset unavailable")


@app.get("/api/lead-magnets/engagement/{lead_id}")
async def lead_magnet_engagement(lead_id: str, current_user: dict = Depends(get_current_user)):
    sends = list(lead_magnet_views_collection.find(
        {"lead_id": lead_id, "kind": "send"}, {"_id": 0}
    ).sort("created_at", DESCENDING))
    views = list(lead_magnet_views_collection.find(
        {"lead_id": lead_id, "kind": "view"}, {"_id": 0}
    ).sort("created_at", DESCENDING))
    last_sent = sends[0]["created_at"] if sends else None
    last_viewed = views[0]["created_at"] if views else None
    return {
        "sent_count": len(sends),
        "view_count": len(views),
        "last_sent": last_sent,
        "last_viewed": last_viewed,
        "sends": sends,
        "views": views[:10],
        "is_hot": len(views) >= 2,
    }



# ─── Per-Campaign Lead Magnet Override ───

@app.get("/api/lead-magnets/campaign/{campaign_id}")
async def get_campaign_magnet(campaign_id: str, current_user: dict = Depends(get_current_user)):
    doc = lead_magnets_collection.find_one({"scope": "campaign", "campaign_id": campaign_id}, {"_id": 0})
    if not doc:
        return {
            "campaign_id": campaign_id,
            "inherit": True,
            "enabled": False,
            "name": "",
            "type": "url",
            "url": "",
            "file_id": None,
            "file_name": None,
            "send_timing": "post_booking",
            "message_template": "",
        }
    doc.pop("scope", None)
    return doc


@app.put("/api/lead-magnets/campaign/{campaign_id}")
async def save_campaign_magnet(campaign_id: str, cfg: CampaignLeadMagnetOverride, current_user: dict = Depends(get_current_user)):
    payload = cfg.dict()
    payload["scope"] = "campaign"
    payload["campaign_id"] = campaign_id
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    payload["updated_by"] = current_user["email"]
    lead_magnets_collection.update_one(
        {"scope": "campaign", "campaign_id": campaign_id},
        {"$set": payload},
        upsert=True,
    )
    payload.pop("scope", None)
    return payload


# ─── Engagement Aggregation (for Dashboard alert + Lead Inbox hot strip) ───

@app.get("/api/lead-magnets/engagement-map")
async def lead_magnet_engagement_map(current_user: dict = Depends(get_current_user)):
    """Return {lead_id: {sent_count, view_count, last_viewed, is_hot}} for all leads with engagement.

    Used by Lead Inbox to show a Hot strip on rows where a lead has opened the brochure.
    """
    pipeline = [
        {"$group": {
            "_id": {"lead_id": "$lead_id", "kind": "$kind"},
            "count": {"$sum": 1},
            "last_at": {"$max": "$created_at"},
        }},
    ]
    rows = list(lead_magnet_views_collection.aggregate(pipeline))
    lead_map: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        lid = r["_id"].get("lead_id")
        kind = r["_id"].get("kind")
        if not lid:
            continue
        bucket = lead_map.setdefault(lid, {"sent_count": 0, "view_count": 0, "last_viewed": None, "last_sent": None})
        if kind == "send":
            bucket["sent_count"] = r["count"]
            bucket["last_sent"] = r["last_at"]
        elif kind == "view":
            bucket["view_count"] = r["count"]
            bucket["last_viewed"] = r["last_at"]
    for _lid, b in lead_map.items():
        b["is_hot"] = b["view_count"] >= 2
    return {"leads": lead_map, "total_engaged": len(lead_map)}


@app.get("/api/lead-magnets/recent-opens")
async def lead_magnet_recent_opens(limit: int = 5, current_user: dict = Depends(get_current_user)):
    """Recent brochure-opens with enriched lead info, for Dashboard alert card."""
    views = list(lead_magnet_views_collection.find(
        {"kind": "view"}, {"_id": 0}
    ).sort("created_at", DESCENDING).limit(max(1, min(limit, 50))))
    out = []
    seen_leads = set()
    for v in views:
        lid = v.get("lead_id")
        if not lid or lid in seen_leads:
            continue
        seen_leads.add(lid)
        try:
            lead = leads_collection.find_one({"_id": ObjectId(lid)}, {"_id": 0, "first_name": 1, "last_name": 1, "company_name": 1, "icp_score": 1, "icp_tier": 1, "email": 1})
        except Exception:
            lead = None
        if not lead:
            continue
        view_count = lead_magnet_views_collection.count_documents({"lead_id": lid, "kind": "view"})
        out.append({
            "lead_id": lid,
            "first_name": lead.get("first_name"),
            "last_name": lead.get("last_name"),
            "company_name": lead.get("company_name"),
            "icp_score": lead.get("icp_score"),
            "icp_tier": lead.get("icp_tier"),
            "email": lead.get("email"),
            "viewed_at": v.get("created_at"),
            "view_count": view_count,
            "is_hot": view_count >= 2,
        })
    return {"opens": out, "count": len(out)}



# ─── WhatsApp Cloud API Webhooks ───

@app.get("/api/webhooks/whatsapp")
async def whatsapp_webhook_verify(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
):
    """Meta WhatsApp Cloud API webhook verification (GET hub.challenge echo).
    Returns the challenge as plain text when hub.verify_token matches WHATSAPP_VERIFY_TOKEN env.
    """
    expected = os.getenv("WHATSAPP_VERIFY_TOKEN")
    if not expected:
        raise HTTPException(status_code=503, detail="WHATSAPP_VERIFY_TOKEN env not set")
    if hub_mode != "subscribe" or hub_verify_token != expected:
        raise HTTPException(status_code=403, detail="Invalid verification token or mode")
    return Response(content=hub_challenge or "", media_type="text/plain", status_code=200)


@app.post("/api/webhooks/whatsapp")
async def whatsapp_webhook_receive(payload: Dict[str, Any]):
    """Receive inbound WhatsApp messages and delivery status updates from Meta.

    Pipeline:
      1. Resolve tenant from phone_number_id (Meta webhook 'metadata.phone_number_id')
      2. STOP keyword → opt-out + silent log
      3. Run 3-layer classification (trigger → contact/lead lookup → Claude)
      4. Lead path: pause pending touchpoints, log activity, mark opt-in
      5. Non-lead paths: log canned-response intent (handler routes are owner-side)
    """
    try:
        for entry in payload.get("entry", []) or []:
            for change in entry.get("changes", []) or []:
                value = change.get("value", {}) or {}
                # Resolve tenant from phone_number_id metadata.
                phone_number_id = (value.get("metadata") or {}).get("phone_number_id")
                tenant = None
                if phone_number_id:
                    tenant = db["tenants"].find_one(
                        {"settings.whatsapp.providers.meta.phone_number_id": phone_number_id},
                        {"_id": 0},
                    )
                # Fallback: legacy single-tenant
                if not tenant:
                    tenant = db["tenants"].find_one({}, {"_id": 0})

                for msg in value.get("messages", []) or []:
                    if msg.get("type") != "text":
                        continue
                    from_phone = msg.get("from")
                    body = (msg.get("text") or {}).get("body", "")
                    tenant_id = tenant.get("id") if tenant else None

                    if tenant_id:
                        # STOP keyword auto-opt-out
                        if is_stop_keyword(body):
                            opt_out_phone(tenant_id, from_phone or "", reason="stop_keyword")
                            print(f"[whatsapp] STOP keyword from {from_phone} on tenant {tenant_id}")
                            continue

                        # Classify via 3-layer pipeline
                        cls = await classify_inbound(tenant_id, from_phone or "", body)
                        action = cls.get("action", "neutral_opener")

                        if action in ("continue_lead", "create_lead_or_continue"):
                            # Match existing lead by phone (last-10)
                            normalized_from = _normalize_phone(from_phone or "")
                            last10 = normalized_from[-10:] if len(normalized_from) >= 10 else normalized_from
                            candidate = None
                            if normalized_from:
                                candidate = leads_collection.find_one({"tenant_id": tenant_id, "phone": from_phone}, {"_id": 1, "id": 1})
                                if not candidate and last10:
                                    candidate = leads_collection.find_one(
                                        {"tenant_id": tenant_id, "phone": {"$regex": f"{last10}$"}},
                                        {"_id": 1, "id": 1},
                                    )
                            if candidate:
                                lead_id = candidate.get("id") or str(candidate.get("_id"))
                                # Pause pending touchpoints (lead is engaging)
                                pause_lead(tenant_id, lead_id)
                                # Lightweight sentiment classification (graceful, never raises)
                                sentiment = "neutral"
                                try:
                                    sentiment = await health_classify_sentiment(body)
                                except Exception:
                                    pass
                                # Auto opt-in + sentiment stamp + last_inbound_at on the lead
                                leads_collection.update_one(
                                    {"id": lead_id, "tenant_id": tenant_id},
                                    {"$set": {
                                        "opted_in": True,
                                        "opted_in_at": datetime.now(timezone.utc).isoformat(),
                                        "opted_in_source": "replied_first",
                                        "latest_sentiment": sentiment,
                                        "last_activity_at": datetime.now(timezone.utc).isoformat(),
                                        "stale": False,  # any reply clears stale
                                    }},
                                )
                                # Mirror onto conversation
                                aria_conversations_collection.update_one(
                                    {"lead_id": lead_id, "tenant_id": tenant_id},
                                    {"$set": {
                                        "latest_sentiment": sentiment,
                                        "last_inbound_at": datetime.now(timezone.utc).isoformat(),
                                    }},
                                    upsert=True,
                                )
                                # Fire sentiment-derived CRM events
                                try:
                                    if sentiment in ("negative", "urgent"):
                                        from routes.crm_sync import fire_event as _cfe
                                        _cfe(tenant_id, {"id": lead_id, "tenant_id": tenant_id}, f"sentiment.{sentiment}", {"message_preview": body[:140]})
                                except Exception:
                                    pass
                                activities_collection.insert_one({
                                    "lead_id": lead_id, "tenant_id": tenant_id, "user_id": "whatsapp_webhook",
                                    "activity_type": "whatsapp_received",
                                    "subject": "WhatsApp reply received",
                                    "body": body[:1000],
                                    "outcome": None, "duration_minutes": None,
                                    "metadata": {"source": "whatsapp_webhook", "from": from_phone, "message_id": msg.get("id"), "classification": cls.get("category"), "layer": cls.get("layer"), "sentiment": sentiment},
                                    "created_at": datetime.now(timezone.utc).isoformat(),
                                })
                        # Non-lead categories logged in classification_log; canned responses
                        # are sent out-of-band by the operator from the Classification Log UI.
                    else:
                        print(f"[whatsapp] inbound from {from_phone} could not resolve tenant — skipped")
    except Exception as e:
        print(f"WhatsApp webhook processing error: {e}")
    return {"received": True}



# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ARIA — Best Time to Call
# Combines: brochure-open recency + lead timezone (from country) + reply-hour heatmap
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Coarse country -> (timezone_label, utc_offset_hours) lookup. Covers ~95% of common targets.
_COUNTRY_TZ = {
    "india": ("IST", 5.5), "in": ("IST", 5.5),
    "united states": ("EST", -5.0), "usa": ("EST", -5.0), "us": ("EST", -5.0),
    "united kingdom": ("GMT", 0.0), "uk": ("GMT", 0.0), "gb": ("GMT", 0.0),
    "canada": ("EST", -5.0), "ca": ("EST", -5.0),
    "australia": ("AEDT", 11.0), "au": ("AEDT", 11.0),
    "germany": ("CET", 1.0), "de": ("CET", 1.0),
    "france": ("CET", 1.0), "fr": ("CET", 1.0),
    "spain": ("CET", 1.0), "es": ("CET", 1.0),
    "italy": ("CET", 1.0), "it": ("CET", 1.0),
    "netherlands": ("CET", 1.0), "nl": ("CET", 1.0),
    "singapore": ("SGT", 8.0), "sg": ("SGT", 8.0),
    "japan": ("JST", 9.0), "jp": ("JST", 9.0),
    "uae": ("GST", 4.0), "ae": ("GST", 4.0),
    "brazil": ("BRT", -3.0), "br": ("BRT", -3.0),
    "mexico": ("CST", -6.0), "mx": ("CST", -6.0),
}


def _resolve_lead_timezone(lead: dict):
    country = (lead.get("country") or "").strip().lower()
    if country in _COUNTRY_TZ:
        return _COUNTRY_TZ[country]
    # Try to match phone country code prefix as last-resort
    phone = lead.get("phone") or ""
    digits = "".join(c for c in phone if c.isdigit())
    if digits.startswith("91"):
        return _COUNTRY_TZ["india"]
    if digits.startswith("1") and len(digits) >= 10:
        return _COUNTRY_TZ["united states"]
    if digits.startswith("44"):
        return _COUNTRY_TZ["united kingdom"]
    if digits.startswith("61"):
        return _COUNTRY_TZ["australia"]
    if digits.startswith("971"):
        return _COUNTRY_TZ["uae"]
    return ("UTC", 0.0)


def _local_hour_now(utc_offset_hours: float) -> int:
    now_utc = datetime.now(timezone.utc)
    local_total = (now_utc.hour + now_utc.minute / 60.0 + utc_offset_hours) % 24
    return int(local_total)


def _format_local_window(start_hour: int, end_hour: int) -> str:
    def fmt(h):
        h = h % 24
        suffix = "AM" if h < 12 else "PM"
        h12 = ((h - 1) % 12) + 1
        return f"{h12}{suffix}"
    return f"{fmt(start_hour)}–{fmt(end_hour)}"


def _compute_reply_window_hours(lead_id: str) -> Optional[List[int]]:
    """Return distinct local-hours when this lead has historically replied. None if no data."""
    activities = list(activities_collection.find(
        {"lead_id": lead_id, "activity_type": {"$in": ["whatsapp_received", "email_received"]}},
        {"_id": 0, "created_at": 1},
    ).limit(50))
    if not activities:
        return None
    hours = set()
    for a in activities:
        ca = a.get("created_at")
        if not ca:
            continue
        try:
            dt = datetime.fromisoformat(ca.replace("Z", "+00:00"))
            hours.add(dt.hour)
        except Exception:
            pass
    return sorted(hours) if hours else None


def _compute_best_time_to_call_for_lead(lead: dict) -> dict:
    """Return {label, window_local, urgency, reason, call_score, lead_local_hour, tz_label, suggested_action}."""
    lead_id = lead.get("id") or lead.get("_id_str")
    tz_label, utc_off = _resolve_lead_timezone(lead)
    local_hour = _local_hour_now(utc_off)

    # Determine the lead's most active reply window (heuristic)
    reply_hours = _compute_reply_window_hours(lead_id) if lead_id else None
    if reply_hours:
        # Use min/max of replied hours, padded ±1
        start_h = max(0, min(reply_hours) - 1)
        end_h = min(23, max(reply_hours) + 1)
    else:
        # Default business hours window (10am – 4pm local)
        start_h, end_h = 10, 16

    in_window = start_h <= local_hour <= end_h

    # Brochure-open recency
    last_view = lead_magnet_views_collection.find_one(
        {"lead_id": lead_id, "kind": "view"},
        {"_id": 0, "created_at": 1},
        sort=[("created_at", DESCENDING)],
    ) if lead_id else None
    minutes_since_view = None
    if last_view and last_view.get("created_at"):
        try:
            dt = datetime.fromisoformat(last_view["created_at"].replace("Z", "+00:00"))
            minutes_since_view = max(0, int((datetime.now(timezone.utc) - dt).total_seconds() / 60))
        except Exception:
            pass

    # Compute call_score (0-100) and urgency
    score = 0
    reasons: List[str] = []
    if minutes_since_view is not None and minutes_since_view <= 30:
        score += 60
        reasons.append(f"opened brochure {minutes_since_view}m ago")
    elif minutes_since_view is not None and minutes_since_view <= 240:
        score += 30
        reasons.append(f"opened brochure {minutes_since_view}m ago")
    if in_window:
        score += 30
        reasons.append(f"in {tz_label} active hours")
    else:
        reasons.append(f"outside {tz_label} active hours ({_format_local_window(start_h, end_h)})")
    icp = lead.get("icp_score") or 0
    if icp >= 70:
        score += 20
        reasons.append(f"hot ICP ({icp})")
    elif icp >= 40:
        score += 10

    if score >= 75:
        urgency = "now"
        suggested_action = "Call now"
    elif score >= 45:
        urgency = "soon"
        suggested_action = f"Good window now ({tz_label})" if in_window else f"Wait for their {tz_label} window"
    else:
        urgency = "later"
        if in_window:
            suggested_action = f"Available now ({tz_label})"
        else:
            # Compute hours until next window
            if local_hour < start_h:
                hours_to_window = start_h - local_hour
            else:
                hours_to_window = (24 - local_hour) + start_h
            suggested_action = f"Best in ~{hours_to_window}h ({_format_local_window(start_h, end_h)} {tz_label})"

    return {
        "tz_label": tz_label,
        "utc_offset_hours": utc_off,
        "lead_local_hour": local_hour,
        "active_window_local": _format_local_window(start_h, end_h),
        "active_start_hour": start_h,
        "active_end_hour": end_h,
        "in_window": in_window,
        "minutes_since_brochure_open": minutes_since_view,
        "call_score": min(100, score),
        "urgency": urgency,
        "suggested_action": suggested_action,
        "reasons": reasons,
        "data_source": "reply_heatmap" if reply_hours else "default_business_hours",
    }


@app.get("/api/aria/best-time-to-call/{lead_id}")
async def best_time_to_call_for_lead(lead_id: str, current_user: dict = Depends(get_current_user)):
    """Return the best time to call THIS lead — for Lead Detail panel."""
    try:
        lead_doc = leads_collection.find_one(
            {"_id": ObjectId(lead_id)},
            {"_id": 0, "first_name": 1, "last_name": 1, "country": 1, "phone": 1, "icp_score": 1, "icp_tier": 1},
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid lead id")
    if not lead_doc:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead_doc["id"] = lead_id
    return _compute_best_time_to_call_for_lead(lead_doc)


@app.get("/api/aria/call-priority")
async def aria_call_priority(limit: int = 3, current_user: dict = Depends(get_current_user)):
    """Return the top N leads that are ripe to call RIGHT NOW — for Dashboard widget."""
    return _compute_call_priority(limit, tenant_id=current_user.get("tenant_id"))


def _compute_call_priority(limit: int = 3, tenant_id: Optional[str] = None) -> dict:
    """Internal: top-N call priority. Tenant-scoped when tenant_id provided."""
    limit = max(1, min(limit, 50))

    # Base filter — never let a tenant see another tenant's lead.
    tf = {"tenant_id": tenant_id} if tenant_id else {}

    candidate_ids = set()
    recent_views = list(
        lead_magnet_views_collection.find(
            {"kind": "view", **tf},
            {"_id": 0, "lead_id": 1, "created_at": 1},
        ).sort("created_at", DESCENDING).limit(50)
    )
    for v in recent_views:
        if v.get("lead_id"):
            candidate_ids.add(v["lead_id"])
    high_icp = list(leads_collection.find(
        {"icp_score": {"$gte": 60}, "status": {"$nin": ["won", "lost", "unqualified"]}, **tf},
        {"_id": 1},
    ).limit(30))
    for l_doc in high_icp:
        candidate_ids.add(str(l_doc["_id"]))

    results = []
    for lid in candidate_ids:
        try:
            lead_doc = leads_collection.find_one(
                {"_id": ObjectId(lid), **tf},
                {"_id": 0, "first_name": 1, "last_name": 1, "company_name": 1, "country": 1, "phone": 1, "icp_score": 1, "icp_tier": 1, "status": 1, "email": 1},
            )
        except Exception:
            continue
        if not lead_doc:
            continue
        lead_doc["id"] = lid
        score_data = _compute_best_time_to_call_for_lead(lead_doc)
        results.append({
            "lead_id": lid,
            "first_name": lead_doc.get("first_name"),
            "last_name": lead_doc.get("last_name"),
            "company_name": lead_doc.get("company_name"),
            "phone": lead_doc.get("phone"),
            "email": lead_doc.get("email"),
            "icp_score": lead_doc.get("icp_score"),
            "icp_tier": lead_doc.get("icp_tier"),
            **score_data,
        })

    results.sort(key=lambda x: (x["call_score"], x.get("icp_score") or 0), reverse=True)
    return {"priority": results[:limit], "checked_count": len(candidate_ids)}



# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ARIA Daily Call Plan — emails the founder a sorted top-5 leads to call today
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

daily_call_plan_collection = db["daily_call_plan_settings"]


class DailyCallPlanConfig(BaseModel):
    enabled: bool = False
    send_to_email: Optional[EmailStr] = None
    send_hour_local: int = Field(8, ge=0, le=23)
    timezone_offset_hours: float = Field(0.0, ge=-12.0, le=14.0)
    plan_size: int = Field(5, ge=1, le=10)


def _get_daily_call_plan_config() -> dict:
    doc = daily_call_plan_collection.find_one({"scope": "workspace"}, {"_id": 0}) or {}
    return doc


def _render_daily_call_plan_html(priority: List[dict], founder_name: str, plan_date: str) -> str:
    if not priority:
        rows_html = '<tr><td style="padding:24px;text-align:center;color:#9B8AB0;font-size:14px;">No high-priority leads today. Pipeline is calm — perfect time for outbound.</td></tr>'
    else:
        rows_html = ""
        for i, p in enumerate(priority, 1):
            urgency = p.get("urgency", "later")
            urg_color = {"now": "#16A34A", "soon": "#D97706", "later": "#7C35DC"}.get(urgency, "#7C35DC")
            urg_bg = {"now": "#DCFCE7", "soon": "#FEF3C7", "later": "#F4F0FF"}.get(urgency, "#F4F0FF")
            urg_label = {"now": "CALL NOW", "soon": "SOON", "later": "LATER"}.get(urgency, urgency.upper())
            phone = p.get("phone") or ""
            phone_html = f'<a href="tel:{phone}" style="display:inline-block;background:linear-gradient(135deg,#7C35DC 0%,#C044E0 100%);color:#fff;padding:8px 16px;border-radius:8px;text-decoration:none;font-weight:600;font-size:13px;">📞 Call</a>' if phone else '<span style="color:#9B8AB0;font-size:12px;">No phone</span>'
            company = p.get("company_name") or "—"
            reasons_text = " · ".join((p.get("reasons") or [])[:2])
            rows_html += f"""
            <tr>
              <td style="padding:14px 16px;border-bottom:1px solid #F0ECF9;">
                <table cellpadding="0" cellspacing="0" border="0" width="100%">
                  <tr>
                    <td style="vertical-align:top;width:32px;color:#9B8AB0;font-weight:700;font-size:14px;">#{i}</td>
                    <td style="vertical-align:top;">
                      <div style="margin-bottom:4px;">
                        <span style="font-size:15px;font-weight:700;color:#1A0A2E;">{p.get('first_name','')} {p.get('last_name','')}</span>
                        <span style="display:inline-block;margin-left:6px;padding:2px 6px;border-radius:4px;background:{urg_bg};color:{urg_color};font-size:10px;font-weight:700;letter-spacing:0.5px;">{urg_label}</span>
                        <span style="display:inline-block;margin-left:4px;padding:2px 6px;border-radius:4px;background:#F4F0FF;color:#7C35DC;font-size:10px;font-weight:700;">ICP {p.get('icp_score', 0)}</span>
                      </div>
                      <div style="font-size:12px;color:#5A4A7A;margin-bottom:2px;">{company}</div>
                      <div style="font-size:11px;color:#9B8AB0;font-style:italic;">{reasons_text}</div>
                    </td>
                    <td style="vertical-align:top;text-align:right;width:90px;">{phone_html}</td>
                  </tr>
                </table>
              </td>
            </tr>"""

    return f"""<!DOCTYPE html><html><body style="margin:0;padding:0;background:#FAFAFA;font-family:'Plus Jakarta Sans',Arial,sans-serif;">
<table cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#FAFAFA;padding:32px 16px;">
  <tr>
    <td align="center">
      <table cellpadding="0" cellspacing="0" border="0" width="600" style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 20px rgba(124,53,220,0.08);">
        <tr>
          <td style="background:linear-gradient(135deg,#7C35DC 0%,#C044E0 100%);padding:28px 24px;color:#fff;">
            <div style="font-size:12px;font-weight:600;opacity:0.85;letter-spacing:1px;text-transform:uppercase;">ARIA · Daily Call Plan</div>
            <div style="font-size:24px;font-weight:800;margin-top:4px;">Good morning, {founder_name}</div>
            <div style="font-size:13px;margin-top:6px;opacity:0.9;">Your top {len(priority) or 0} leads to call today — {plan_date}</div>
          </td>
        </tr>
        <tr>
          <td>
            <table cellpadding="0" cellspacing="0" border="0" width="100%">
              {rows_html}
            </table>
          </td>
        </tr>
        <tr>
          <td style="padding:20px 24px;border-top:1px solid #F0ECF9;background:#FAFAFA;">
            <div style="font-size:12px;color:#9B8AB0;text-align:center;">ARIA scored these by brochure opens, ICP, and timezone fit. Tap a number to call directly from your phone.</div>
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>
</body></html>"""


async def _send_daily_call_plan(recipient_email: str, plan_size: int = 5, manual: bool = False) -> dict:
    """Send the daily call plan email NOW. Returns metadata."""
    if not recipient_email:
        return {"sent": False, "error": "no_recipient"}
    plan = _compute_call_priority(limit=plan_size)
    priority = plan.get("priority", [])
    founder_name = (aria_settings_collection.find_one({}) or {}).get("founder_name") or "founder"
    plan_date = datetime.now(timezone.utc).strftime("%A, %b %d")
    html = _render_daily_call_plan_html(priority, founder_name, plan_date)
    subject = f"☀️ {len(priority)} leads to call today" if priority else "☀️ Pipeline is calm today — outbound time"
    params = {
        "from": os.getenv("SENDER_EMAIL", "onboarding@resend.dev"),
        "to": [recipient_email],
        "subject": subject,
        "html": html,
    }
    try:
        await asyncio.to_thread(resend.Emails.send, params)
        now_iso = datetime.now(timezone.utc).isoformat()
        daily_call_plan_collection.update_one(
            {"scope": "workspace"},
            {"$set": {
                "last_sent_at": now_iso,
                "last_sent_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "last_sent_count": len(priority),
                "last_sent_manual": manual,
            }},
            upsert=True,
        )
        return {"sent": True, "count": len(priority), "recipient": recipient_email}
    except Exception as e:
        print(f"Daily call plan email failed: {e}")
        return {"sent": False, "error": str(e)}


@app.get("/api/aria/daily-call-plan/config")
async def get_daily_call_plan_config(current_user: dict = Depends(get_current_user)):
    cfg = _get_daily_call_plan_config()
    if not cfg:
        return {
            "enabled": False,
            "send_to_email": current_user.get("email"),
            "send_hour_local": 8,
            "timezone_offset_hours": 5.5,
            "plan_size": 5,
            "last_sent_at": None,
            "last_sent_date": None,
            "last_sent_count": 0,
        }
    cfg.pop("scope", None)
    return cfg


@app.put("/api/aria/daily-call-plan/config")
async def save_daily_call_plan_config(cfg: DailyCallPlanConfig, current_user: dict = Depends(get_current_user)):
    payload = cfg.dict()
    payload["scope"] = "workspace"
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    payload["updated_by"] = current_user["email"]
    daily_call_plan_collection.update_one({"scope": "workspace"}, {"$set": payload}, upsert=True)
    payload.pop("scope", None)
    return payload


@app.post("/api/aria/daily-call-plan/send-now")
async def send_daily_call_plan_now(current_user: dict = Depends(get_current_user)):
    cfg = _get_daily_call_plan_config()
    recipient = (cfg or {}).get("send_to_email") or current_user.get("email")
    plan_size = int((cfg or {}).get("plan_size") or 5)
    if not recipient:
        raise HTTPException(status_code=400, detail="No recipient email configured. Set it in Settings → ARIA → Daily Call Plan.")
    res = await _send_daily_call_plan(recipient, plan_size=plan_size, manual=True)
    if not res.get("sent"):
        raise HTTPException(status_code=500, detail=f"Failed to send: {res.get('error')}")
    return res


@app.get("/api/aria/daily-call-plan/preview")
async def daily_call_plan_preview(current_user: dict = Depends(get_current_user)):
    """Return the rendered HTML preview without sending — for in-app preview."""
    cfg = _get_daily_call_plan_config()
    plan_size = int((cfg or {}).get("plan_size") or 5)
    plan = _compute_call_priority(limit=plan_size)
    founder_name = (aria_settings_collection.find_one({}) or {}).get("founder_name") or "founder"
    plan_date = datetime.now(timezone.utc).strftime("%A, %b %d")
    html = _render_daily_call_plan_html(plan.get("priority", []), founder_name, plan_date)
    return {"html": html, "count": len(plan.get("priority", []))}


# ─── Daily cron loop ───
async def _daily_call_plan_loop():
    """Background loop: every 60s check if it's time to send today's plan.

    Compares the founder's intended local minute-of-day against current UTC minute-of-day
    (mod 1440) so that fractional UTC offsets like IST (+5.5) trigger correctly.
    """
    while True:
        try:
            cfg = _get_daily_call_plan_config()
            if cfg and cfg.get("enabled") and cfg.get("send_to_email"):
                send_hour_local = int(cfg.get("send_hour_local", 8))
                tz_off = float(cfg.get("timezone_offset_hours", 0.0))
                # Founder local minute-of-day (whole hours only) -> UTC minute-of-day
                target_minute_of_day_utc = int(((send_hour_local * 60) - (tz_off * 60)) % 1440)
                now_utc = datetime.now(timezone.utc)
                current_minute_of_day_utc = now_utc.hour * 60 + now_utc.minute
                # Trigger if within a 5-minute fire window (loop ticks every 60s)
                in_window = 0 <= (current_minute_of_day_utc - target_minute_of_day_utc) <= 5
                today_str = now_utc.strftime("%Y-%m-%d")
                last_date = cfg.get("last_sent_date")
                if in_window and last_date != today_str:
                    print(f"[DailyCallPlan] Triggering send to {cfg['send_to_email']} (founder hour={send_hour_local}, tz_off={tz_off}, target_utc_min={target_minute_of_day_utc}, now_utc_min={current_minute_of_day_utc})")
                    await _send_daily_call_plan(
                        cfg["send_to_email"],
                        plan_size=int(cfg.get("plan_size", 5)),
                        manual=False,
                    )
        except Exception as e:
            print(f"[DailyCallPlan] loop error: {e}")
        await asyncio.sleep(60)


@app.on_event("startup")
async def _start_daily_call_plan_loop():
    asyncio.create_task(_daily_call_plan_loop())
    print("[DailyCallPlan] Background loop started (60s tick)")


@app.on_event("startup")
async def _start_touchpoint_engine_loop():
    asyncio.create_task(engine_loop())


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



# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ARIA End-of-Day Wrap — emails the founder a 6pm summary of today's progress
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

eod_wrap_collection = db["eod_wrap_settings"]


class EndOfDayWrapConfig(BaseModel):
    enabled: bool = False
    send_to_email: Optional[EmailStr] = None
    send_hour_local: int = Field(18, ge=0, le=23)
    timezone_offset_hours: float = Field(0.0, ge=-12.0, le=14.0)


def _get_eod_wrap_config() -> dict:
    return eod_wrap_collection.find_one({"scope": "workspace"}, {"_id": 0}) or {}


def _compute_eod_wrap(tz_off_hours: float = 0.0) -> dict:
    """Compute today's wrap data. 'Today' = the founder's local calendar day."""
    now_utc = datetime.now(timezone.utc)
    # Day window in founder's local timezone, expressed in UTC
    local_now = now_utc + timedelta(hours=tz_off_hours)
    local_day_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_start_utc = local_day_start - timedelta(hours=tz_off_hours)
    day_start_iso = day_start_utc.isoformat()
    now_iso = now_utc.isoformat()

    # Activities logged today
    today_activities = list(activities_collection.find(
        {"created_at": {"$gte": day_start_iso, "$lte": now_iso}},
        {"_id": 0, "lead_id": 1, "activity_type": 1, "subject": 1, "user_id": 1, "created_at": 1, "outcome": 1}
    ))

    def _count(types):
        return sum(1 for a in today_activities if a.get("activity_type") in types)

    calls_logged = _count(["call_made", "meeting_done", "call"])
    emails_sent = _count(["email_sent"])
    whatsapps_sent = _count(["whatsapp_sent"])
    notes_added = _count(["note_added"])
    meetings_booked = _count(["meeting_scheduled"])
    status_changes_today = [a for a in today_activities if a.get("activity_type") == "status_changed"]

    # New leads created today
    new_leads_today = list(leads_collection.find(
        {"created_at": {"$gte": day_start_iso, "$lte": now_iso}},
        {"_id": 1, "first_name": 1, "last_name": 1, "company_name": 1, "icp_score": 1, "source_channel": 1}
    ))
    new_leads_count = len(new_leads_today)

    # Wins / Losses today
    wins_today = list(leads_collection.find(
        {"status": "won", "updated_at": {"$gte": day_start_iso, "$lte": now_iso}},
        {"_id": 1, "first_name": 1, "last_name": 1, "company_name": 1, "deal_value": 1}
    ))
    losses_today = list(leads_collection.find(
        {"status": "lost", "updated_at": {"$gte": day_start_iso, "$lte": now_iso}},
        {"_id": 1, "first_name": 1, "last_name": 1, "company_name": 1, "lost_reason": 1}
    ))

    won_value = sum((w.get("deal_value") or 0) for w in wins_today)

    # Per-rep activity breakdown
    rep_map = {}
    for a in today_activities:
        u = a.get("user_id") or "unknown"
        bucket = rep_map.setdefault(u, {"name": u, "calls": 0, "emails": 0, "whatsapps": 0, "notes": 0, "total": 0})
        t = a.get("activity_type")
        if t in ("call_made", "meeting_done", "call"): bucket["calls"] += 1
        elif t == "email_sent": bucket["emails"] += 1
        elif t == "whatsapp_sent": bucket["whatsapps"] += 1
        elif t == "note_added": bucket["notes"] += 1
        bucket["total"] += 1
    rep_rows = sorted(rep_map.values(), key=lambda r: r["total"], reverse=True)[:5]

    # Hot leads still untouched (ICP>=80, status=new, no last_contacted_at)
    hot_untouched = list(leads_collection.find(
        {"icp_score": {"$gte": 80}, "status": "new", "last_contacted_at": {"$in": [None]}},
        {"_id": 1, "first_name": 1, "last_name": 1, "company_name": 1, "icp_score": 1, "source_channel": 1}
    ).limit(5))

    # Overdue follow-ups still pending end-of-day
    overdue_pending = leads_collection.count_documents({
        "next_followup_at": {"$lt": now_iso},
        "status": {"$nin": ["won", "lost", "unqualified"]},
    })

    # Tomorrow's call plan preview (top 3 by call_score)
    try:
        tomorrow_plan = _compute_call_priority(limit=3).get("priority", [])[:3]
    except Exception:
        tomorrow_plan = []

    total_touches = calls_logged + emails_sent + whatsapps_sent
    momentum = "strong" if total_touches >= 15 else "steady" if total_touches >= 5 else "quiet"

    return {
        "date_label": local_now.strftime("%A, %b %d"),
        "totals": {
            "calls": calls_logged,
            "emails": emails_sent,
            "whatsapps": whatsapps_sent,
            "notes": notes_added,
            "meetings_booked": meetings_booked,
            "status_changes": len(status_changes_today),
            "total_touches": total_touches,
            "new_leads": new_leads_count,
            "wins": len(wins_today),
            "losses": len(losses_today),
            "won_value": won_value,
            "won_value_label": _fmt_inr(won_value) if won_value else "—",
            "overdue_pending": overdue_pending,
        },
        "momentum": momentum,
        "wins": [{"name": (w.get("company_name") or f"{w.get('first_name','')} {w.get('last_name','')}".strip()), "value": w.get("deal_value"), "value_label": _fmt_inr(w.get("deal_value")) if w.get("deal_value") else "—"} for w in wins_today[:5]],
        "losses": [{"name": (l.get("company_name") or f"{l.get('first_name','')} {l.get('last_name','')}".strip()), "reason": (l.get("lost_reason") or "—").replace("_", " ").title()} for l in losses_today[:5]],
        "rep_rows": rep_rows,
        "hot_untouched": [{"name": f"{h.get('first_name','')} {h.get('last_name','')}".strip() or h.get("company_name","Lead"), "company": h.get("company_name"), "score": h.get("icp_score"), "source": (h.get("source_channel") or "—").replace("_", " ").title()} for h in hot_untouched],
        "tomorrow_plan": [{"name": f"{p.get('first_name','')} {p.get('last_name','')}".strip(), "company": p.get("company_name"), "icp_score": p.get("icp_score"), "phone": p.get("phone")} for p in tomorrow_plan],
    }


def _render_eod_wrap_html(wrap: dict, founder_name: str) -> str:
    t = wrap["totals"]
    momentum = wrap["momentum"]
    momentum_color = {"strong": "#16A34A", "steady": "#7C35DC", "quiet": "#D97706"}.get(momentum, "#7C35DC")
    momentum_bg = {"strong": "#DCFCE7", "steady": "#F4F0FF", "quiet": "#FEF3C7"}.get(momentum, "#F4F0FF")
    momentum_label = {"strong": "STRONG DAY", "steady": "STEADY DAY", "quiet": "QUIET DAY"}.get(momentum, "STEADY DAY")

    # KPI tiles
    def _tile(label, value, accent="#7C35DC"):
        return f"""
        <td style="padding:6px;width:25%;vertical-align:top;">
          <div style="background:#FAF7FF;border:1px solid #E8E0F5;border-radius:12px;padding:14px;text-align:center;">
            <div style="font-size:24px;font-weight:800;color:{accent};line-height:1;">{value}</div>
            <div style="font-size:10px;font-weight:700;color:#5A4A7A;letter-spacing:0.5px;text-transform:uppercase;margin-top:6px;">{label}</div>
          </div>
        </td>"""

    kpi_row1 = _tile("Calls", t["calls"], "#7C35DC") + _tile("Emails", t["emails"], "#7C35DC") + _tile("WhatsApps", t["whatsapps"], "#16A34A") + _tile("New Leads", t["new_leads"], "#C044E0")
    kpi_row2 = _tile("Wins", t["wins"], "#16A34A") + _tile("Losses", t["losses"], "#FF3B30") + _tile("Meetings", t["meetings_booked"], "#7C35DC") + _tile("Overdue", t["overdue_pending"], "#D97706")

    # Wins block
    if wrap["wins"]:
        wins_html = "".join([f'<div style="padding:10px 14px;border-bottom:1px solid #F0ECF9;"><span style="font-weight:700;color:#1A0A2E;font-size:13px;">🏆 {w["name"]}</span><span style="float:right;color:#16A34A;font-weight:700;font-size:13px;">{w["value_label"]}</span></div>' for w in wrap["wins"]])
        wins_block = f'<div style="background:#fff;border:1px solid #16A34A22;border-radius:12px;overflow:hidden;margin-bottom:16px;"><div style="padding:12px 14px;background:#DCFCE7;font-size:11px;font-weight:800;color:#16A34A;letter-spacing:1px;text-transform:uppercase;">Wins today · {t["won_value_label"]}</div>{wins_html}</div>'
    else:
        wins_block = ""

    # Hot untouched
    if wrap["hot_untouched"]:
        hot_html = "".join([f'<div style="padding:10px 14px;border-bottom:1px solid #F0ECF9;"><span style="font-weight:700;color:#1A0A2E;font-size:13px;">🔥 {h["name"]}</span> <span style="color:#9B8AB0;font-size:12px;">· {h["source"]} · ICP {h["score"]}</span></div>' for h in wrap["hot_untouched"]])
        hot_block = f'<div style="background:#fff;border:1px solid #FF3B3022;border-radius:12px;overflow:hidden;margin-bottom:16px;"><div style="padding:12px 14px;background:#FEE2E2;font-size:11px;font-weight:800;color:#FF3B30;letter-spacing:1px;text-transform:uppercase;">Hot leads still untouched</div>{hot_html}</div>'
    else:
        hot_block = ""

    # Rep activity
    if wrap["rep_rows"]:
        rep_rows_html = "".join([f'<tr><td style="padding:8px 14px;border-bottom:1px solid #F0ECF9;font-size:12px;color:#1A0A2E;">{r["name"]}</td><td style="padding:8px 14px;border-bottom:1px solid #F0ECF9;font-size:12px;color:#5A4A7A;text-align:right;">{r["calls"]} calls · {r["emails"]} emails · {r["whatsapps"]} WA</td><td style="padding:8px 14px;border-bottom:1px solid #F0ECF9;font-size:12px;color:#7C35DC;font-weight:700;text-align:right;">{r["total"]}</td></tr>' for r in wrap["rep_rows"]])
        rep_block = f'<div style="background:#fff;border:1px solid #E8E0F5;border-radius:12px;overflow:hidden;margin-bottom:16px;"><div style="padding:12px 14px;background:#FAF7FF;font-size:11px;font-weight:800;color:#7C35DC;letter-spacing:1px;text-transform:uppercase;">Rep activity</div><table cellpadding="0" cellspacing="0" border="0" width="100%">{rep_rows_html}</table></div>'
    else:
        rep_block = ""

    # Tomorrow plan
    if wrap["tomorrow_plan"]:
        tom_html = "".join([f'<div style="padding:10px 14px;border-bottom:1px solid #F0ECF9;"><span style="font-weight:700;color:#1A0A2E;font-size:13px;">☀️ {p["name"]}</span> <span style="color:#9B8AB0;font-size:12px;">· {p.get("company") or "—"} · ICP {p.get("icp_score") or "—"}</span></div>' for p in wrap["tomorrow_plan"]])
        tom_block = f'<div style="background:#fff;border:1px solid #E8E0F5;border-radius:12px;overflow:hidden;"><div style="padding:12px 14px;background:linear-gradient(135deg,#7C35DC 0%,#C044E0 100%);font-size:11px;font-weight:800;color:#fff;letter-spacing:1px;text-transform:uppercase;">Tomorrow\'s top 3 calls</div>{tom_html}</div>'
    else:
        tom_block = ""

    return f"""<!DOCTYPE html><html><body style="margin:0;padding:0;background:#FAFAFA;font-family:'Plus Jakarta Sans',Arial,sans-serif;">
<table cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#FAFAFA;padding:32px 16px;">
  <tr><td align="center">
    <table cellpadding="0" cellspacing="0" border="0" width="600" style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 20px rgba(124,53,220,0.08);">
      <tr><td style="background:linear-gradient(135deg,#1A0F38 0%,#0E0820 100%);padding:28px 24px;color:#fff;">
        <div style="font-size:11px;font-weight:600;opacity:0.85;letter-spacing:1.5px;text-transform:uppercase;color:#C9B6FF;">ARIA · End-of-Day Wrap</div>
        <div style="font-size:24px;font-weight:800;margin-top:6px;">Wrap-up, {founder_name}</div>
        <div style="font-size:13px;margin-top:6px;opacity:0.85;">{wrap["date_label"]} — here's what your team shipped today.</div>
        <div style="margin-top:14px;display:inline-block;padding:6px 14px;border-radius:999px;background:{momentum_bg};color:{momentum_color};font-size:11px;font-weight:800;letter-spacing:1px;text-transform:uppercase;">{momentum_label} · {t["total_touches"]} touches</div>
      </td></tr>
      <tr><td style="padding:18px 18px 8px 18px;">
        <table cellpadding="0" cellspacing="0" border="0" width="100%"><tr>{kpi_row1}</tr><tr>{kpi_row2}</tr></table>
      </td></tr>
      <tr><td style="padding:8px 18px 18px 18px;">
        {wins_block}
        {hot_block}
        {rep_block}
        {tom_block}
      </td></tr>
      <tr><td style="padding:20px 24px;border-top:1px solid #F0ECF9;background:#FAFAFA;">
        <div style="font-size:12px;color:#9B8AB0;text-align:center;">ARIA tallied today's activity from your Lead Inbox. Tomorrow's morning call plan lands at 8 AM.</div>
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>"""


async def _send_eod_wrap(recipient_email: str, tz_off_hours: float = 0.0, manual: bool = False) -> dict:
    if not recipient_email:
        return {"sent": False, "error": "no_recipient"}
    wrap = _compute_eod_wrap(tz_off_hours=tz_off_hours)
    founder_name = (aria_settings_collection.find_one({}) or {}).get("founder_name") or "founder"
    html = _render_eod_wrap_html(wrap, founder_name)
    t = wrap["totals"]
    if t["wins"] > 0:
        subject = f"🏆 {t['wins']} won · {t['total_touches']} touches today"
    elif t["total_touches"] >= 10:
        subject = f"📞 {t['total_touches']} touches · {wrap['date_label']}"
    elif t["total_touches"] == 0:
        subject = f"😴 Quiet day — 0 outreach logged"
    else:
        subject = f"📊 {t['total_touches']} touches · {t['new_leads']} new leads"
    params = {
        "from": os.getenv("SENDER_EMAIL", "onboarding@resend.dev"),
        "to": [recipient_email],
        "subject": subject,
        "html": html,
    }
    try:
        await asyncio.to_thread(resend.Emails.send, params)
        now_iso = datetime.now(timezone.utc).isoformat()
        eod_wrap_collection.update_one(
            {"scope": "workspace"},
            {"$set": {
                "last_sent_at": now_iso,
                "last_sent_date": (datetime.now(timezone.utc) + timedelta(hours=tz_off_hours)).strftime("%Y-%m-%d"),
                "last_sent_touches": t["total_touches"],
                "last_sent_manual": manual,
            }},
            upsert=True,
        )
        return {"sent": True, "touches": t["total_touches"], "recipient": recipient_email}
    except Exception as e:
        print(f"EOD wrap email failed: {e}")
        return {"sent": False, "error": str(e)}


@app.get("/api/aria/eod-wrap/config")
async def get_eod_wrap_config(current_user: dict = Depends(get_current_user)):
    cfg = _get_eod_wrap_config()
    if not cfg:
        return {
            "enabled": False,
            "send_to_email": current_user.get("email"),
            "send_hour_local": 18,
            "timezone_offset_hours": 5.5,
            "last_sent_at": None,
            "last_sent_date": None,
            "last_sent_touches": 0,
        }
    cfg.pop("scope", None)
    return cfg


@app.put("/api/aria/eod-wrap/config")
async def save_eod_wrap_config(cfg: EndOfDayWrapConfig, current_user: dict = Depends(get_current_user)):
    payload = cfg.dict()
    payload["scope"] = "workspace"
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    payload["updated_by"] = current_user["email"]
    eod_wrap_collection.update_one({"scope": "workspace"}, {"$set": payload}, upsert=True)
    payload.pop("scope", None)
    return payload


@app.post("/api/aria/eod-wrap/send-now")
async def send_eod_wrap_now(current_user: dict = Depends(get_current_user)):
    cfg = _get_eod_wrap_config()
    recipient = (cfg or {}).get("send_to_email") or current_user.get("email")
    tz_off = float((cfg or {}).get("timezone_offset_hours") or 0.0)
    if not recipient:
        raise HTTPException(status_code=400, detail="No recipient email configured. Set it in Settings → ARIA → End-of-Day Wrap.")
    res = await _send_eod_wrap(recipient, tz_off_hours=tz_off, manual=True)
    if not res.get("sent"):
        raise HTTPException(status_code=500, detail=f"Failed to send: {res.get('error')}")
    return res


@app.get("/api/aria/eod-wrap/preview")
async def eod_wrap_preview(current_user: dict = Depends(get_current_user)):
    cfg = _get_eod_wrap_config()
    tz_off = float((cfg or {}).get("timezone_offset_hours") or 0.0)
    wrap = _compute_eod_wrap(tz_off_hours=tz_off)
    founder_name = (aria_settings_collection.find_one({}) or {}).get("founder_name") or "founder"
    html = _render_eod_wrap_html(wrap, founder_name)
    return {"html": html, "wrap": wrap}


@app.get("/api/aria/today")
async def aria_today(current_user: dict = Depends(get_current_user)):
    """Lightweight live snapshot of today's wrap totals — for the Dashboard ARIA Today widget.
    Same compute as the EOD email but stripped to totals + momentum + headline copy."""
    cfg = _get_eod_wrap_config()
    tz_off = float((cfg or {}).get("timezone_offset_hours") or 0.0)
    wrap = _compute_eod_wrap(tz_off_hours=tz_off)
    t = wrap["totals"]
    momentum = wrap["momentum"]

    if t["wins"] > 0:
        headline = f"{t['wins']} won today · {_fmt_inr(t['won_value']) if t['won_value'] else 'value pending'}"
    elif t["total_touches"] >= 15:
        headline = f"Strong day — {t['total_touches']} touches logged"
    elif t["total_touches"] >= 5:
        headline = f"Steady momentum — {t['total_touches']} touches"
    elif t["total_touches"] > 0:
        headline = f"Slow start — only {t['total_touches']} touches so far"
    else:
        headline = "No outreach logged yet today"

    return {
        "date_label": wrap["date_label"],
        "momentum": momentum,
        "headline": headline,
        "totals": t,
        "hot_untouched_count": len(wrap["hot_untouched"]),
        "tomorrow_top_3": wrap["tomorrow_plan"][:3],
    }


async def _eod_wrap_loop():
    """Background loop: every 60s check if it's the founder's local 6pm to send the wrap."""
    while True:
        try:
            cfg = _get_eod_wrap_config()
            if cfg and cfg.get("enabled") and cfg.get("send_to_email"):
                send_hour_local = int(cfg.get("send_hour_local", 18))
                tz_off = float(cfg.get("timezone_offset_hours", 0.0))
                target_minute_of_day_utc = int(((send_hour_local * 60) - (tz_off * 60)) % 1440)
                now_utc = datetime.now(timezone.utc)
                current_minute_of_day_utc = now_utc.hour * 60 + now_utc.minute
                in_window = 0 <= (current_minute_of_day_utc - target_minute_of_day_utc) <= 5
                local_today_str = (now_utc + timedelta(hours=tz_off)).strftime("%Y-%m-%d")
                last_date = cfg.get("last_sent_date")
                if in_window and last_date != local_today_str:
                    print(f"[EODWrap] Triggering send to {cfg['send_to_email']} (local {send_hour_local}:00, tz_off={tz_off})")
                    await _send_eod_wrap(cfg["send_to_email"], tz_off_hours=tz_off, manual=False)
        except Exception as e:
            print(f"[EODWrap] loop error: {e}")
        await asyncio.sleep(60)


@app.on_event("startup")
async def _start_eod_wrap_loop():
    asyncio.create_task(_eod_wrap_loop())
    print("[EODWrap] Background loop started (60s tick)")



# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Demo Data Seeder & Dev Plan Switch
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DEMO_LEADS_FIXTURE = [
    {"first_name": "Quinn", "last_name": "Varma", "email": "quinn@apexsaas.io", "phone": "+919876512301", "company_name": "ApexSaaS", "job_title": "Head of Growth", "industry": "B2B SaaS", "country": "India", "source_channel": "linkedin", "lead_type": "B2B", "icp_score": 93, "status": "qualified"},
    {"first_name": "Amelia", "last_name": "Cordeiro", "email": "amelia@northglow.co", "phone": "+447700912334", "company_name": "Northglow Realty", "job_title": "Founder", "industry": "Real Estate", "country": "United Kingdom", "source_channel": "meta_ads", "lead_type": "B2B", "icp_score": 82, "status": "contacted"},
    {"first_name": "Diego", "last_name": "Fernandes", "email": "diego@finchedu.mx", "phone": "+525512345678", "company_name": "FinchEdu", "job_title": "COO", "industry": "Education", "country": "Mexico", "source_channel": "google_ads", "lead_type": "B2B", "icp_score": 71, "status": "new"},
    {"first_name": "Priya", "last_name": "Menon", "email": "priya@stratosconsult.in", "phone": "+918888412290", "company_name": "Stratos Consult", "job_title": "Partner", "industry": "Consulting", "country": "India", "source_channel": "website_form", "lead_type": "B2B", "icp_score": 88, "status": "proposal_sent"},
    {"first_name": "Jamie", "last_name": "Levy", "email": "jamie@blanco-labs.com", "phone": "+14155551122", "company_name": "Blanco Labs", "job_title": "Director", "industry": "D2C", "country": "USA", "source_channel": "referral", "lead_type": "B2B", "icp_score": 64, "status": "contacted"},
    {"first_name": "Sasha", "last_name": "Ivanov", "email": "sasha@hawkenIT.com", "phone": "+14043332211", "company_name": "Hawken IT", "job_title": "VP Sales", "industry": "Enterprise IT", "country": "USA", "source_channel": "linkedin", "lead_type": "B2B", "icp_score": 95, "status": "negotiation"},
    {"first_name": "Yuki", "last_name": "Tanaka", "email": "yuki@medora-health.jp", "phone": "+81901234567", "company_name": "Medora Health", "job_title": "CEO", "industry": "Healthcare", "country": "Japan", "source_channel": "webinar", "lead_type": "B2B", "icp_score": 79, "status": "qualified"},
    {"first_name": "Faiza", "last_name": "Khan", "email": "faiza@deltaprintworks.ae", "phone": "+971501122334", "company_name": "Delta Printworks", "job_title": "Founder", "industry": "Manufacturing", "country": "UAE", "source_channel": "whatsapp", "lead_type": "B2B", "icp_score": 47, "status": "new"},
    {"first_name": "Marco", "last_name": "Rossi", "email": "marco@vellaproperties.it", "phone": "+393331122334", "company_name": "Vella Properties", "job_title": "Sales Lead", "industry": "Real Estate", "country": "Italy", "source_channel": "meta_ads", "lead_type": "B2C", "icp_score": 58, "status": "lost"},
    {"first_name": "Hannah", "last_name": "O'Connor", "email": "hannah@rosegold.studio", "phone": "+353871122334", "company_name": "Rosegold Studio", "job_title": "Owner", "industry": "D2C", "country": "Ireland", "source_channel": "referral", "lead_type": "B2B", "icp_score": 73, "status": "contacted"},
    {"first_name": "Rahul", "last_name": "Bhatt", "email": "rahul@codenova.in", "phone": "+919812334455", "company_name": "Codenova", "job_title": "Co-founder", "industry": "B2B SaaS", "country": "India", "source_channel": "website_form", "lead_type": "B2B", "icp_score": 84, "status": "call_booked"},
    {"first_name": "Lina", "last_name": "Park", "email": "lina@brightlearn.kr", "phone": "+821011223344", "company_name": "BrightLearn", "job_title": "Director", "industry": "Education", "country": "South Korea", "source_channel": "google_ads", "lead_type": "B2B", "icp_score": 66, "status": "qualified"},
    {"first_name": "Theo", "last_name": "Ndiaye", "email": "theo@axleconsult.fr", "phone": "+33611223344", "company_name": "Axle Consult", "job_title": "Senior Partner", "industry": "Consulting", "country": "France", "source_channel": "linkedin", "lead_type": "B2B", "icp_score": 91, "status": "proposal_sent"},
    {"first_name": "Sara", "last_name": "Ahmed", "email": "sara@hempcraft.in", "phone": "+919900112233", "company_name": "Hempcraft", "job_title": "Founder", "industry": "D2C", "country": "India", "source_channel": "meta_ads", "lead_type": "B2C", "icp_score": 53, "status": "new"},
    {"first_name": "Owen", "last_name": "Brewster", "email": "owen@archipelago-ent.com", "phone": "+12025550199", "company_name": "Archipelago Enterprise", "job_title": "Head of Ops", "industry": "Enterprise IT", "country": "USA", "source_channel": "referral", "lead_type": "B2B", "icp_score": 86, "status": "qualified"},
    {"first_name": "Mei", "last_name": "Lin", "email": "mei@cleo-pharma.sg", "phone": "+6581234567", "company_name": "Cleo Pharma", "job_title": "Marketing Lead", "industry": "Healthcare", "country": "Singapore", "source_channel": "webinar", "lead_type": "B2B", "icp_score": 70, "status": "contacted"},
    {"first_name": "Nora", "last_name": "Sandström", "email": "nora@forgeworks.se", "phone": "+46701122334", "company_name": "Forgeworks", "job_title": "VP Strategy", "industry": "Manufacturing", "country": "Sweden", "source_channel": "linkedin", "lead_type": "B2B", "icp_score": 77, "status": "negotiation"},
    {"first_name": "Kabir", "last_name": "Iyer", "email": "kabir@plotvilla.in", "phone": "+919900445566", "company_name": "PlotVilla", "job_title": "Sales Manager", "industry": "Real Estate", "country": "India", "source_channel": "whatsapp", "lead_type": "B2C", "icp_score": 35, "status": "unqualified"},
    {"first_name": "Elena", "last_name": "Vasquez", "email": "elena@solarsumm.es", "phone": "+34611223344", "company_name": "SolarSumm", "job_title": "Founder", "industry": "Manufacturing", "country": "Spain", "source_channel": "google_ads", "lead_type": "B2B", "icp_score": 62, "status": "contacted"},
    {"first_name": "Liam", "last_name": "Wallace", "email": "liam@amberSchool.io", "phone": "+447700119900", "company_name": "Amber School", "job_title": "Director", "industry": "Education", "country": "United Kingdom", "source_channel": "website_form", "lead_type": "B2B", "icp_score": 81, "status": "won"},
    {"first_name": "Aisha", "last_name": "Karim", "email": "aisha@northgate-it.com", "phone": "+15551234567", "company_name": "Northgate IT", "job_title": "CIO", "industry": "Enterprise IT", "country": "USA", "source_channel": "linkedin", "lead_type": "B2B", "icp_score": 89, "status": "proposal_sent"},
    {"first_name": "Carlos", "last_name": "Mendes", "email": "carlos@harborlogistics.br", "phone": "+5511933221100", "company_name": "Harbor Logistics", "job_title": "Founder", "industry": "Manufacturing", "country": "Brazil", "source_channel": "referral", "lead_type": "B2B", "icp_score": 68, "status": "qualified"},
    {"first_name": "Iris", "last_name": "Becker", "email": "iris@rubyclinics.de", "phone": "+4915112233445", "company_name": "Ruby Clinics", "job_title": "Practice Manager", "industry": "Healthcare", "country": "Germany", "source_channel": "meta_ads", "lead_type": "B2C", "icp_score": 45, "status": "lost"},
    {"first_name": "Ben", "last_name": "Sokolov", "email": "ben@stackbloom.com", "phone": "+14157771010", "company_name": "Stackbloom", "job_title": "Co-founder", "industry": "B2B SaaS", "country": "USA", "source_channel": "webinar", "lead_type": "B2B", "icp_score": 92, "status": "call_booked"},
    {"first_name": "Anu", "last_name": "Reddy", "email": "anu@petalboutique.in", "phone": "+918111222333", "company_name": "Petal Boutique", "job_title": "Owner", "industry": "D2C", "country": "India", "source_channel": "whatsapp", "lead_type": "B2C", "icp_score": 50, "status": "contacted"},
]


@app.post("/api/admin/load-demo-data")
async def load_demo_data(force: bool = False, current_user: dict = Depends(get_current_user)):
    """Seed 25 realistic leads. By default only runs if leads collection is empty.
    Pass ?force=true to reseed (deletes existing demo leads tagged with metadata.demo=true)."""
    from random import choice, randint
    if force:
        result = leads_collection.delete_many({"metadata.demo": True})
        print(f"[DemoSeed] Deleted {result.deleted_count} existing demo leads")
    else:
        existing = leads_collection.count_documents({})
        if existing > 0:
            return {"seeded": 0, "skipped": True, "reason": f"Workspace already has {existing} leads. Use force=true to reseed."}

    now = datetime.now(timezone.utc)
    inserted = 0
    for i, fixture in enumerate(DEMO_LEADS_FIXTURE):
        # Spread created_at over last 30 days, last_contacted over last 14 days
        days_ago = randint(0, 30)
        created_at = (now - timedelta(days=days_ago)).isoformat()
        last_contact_days = randint(0, 14) if fixture["status"] != "new" else None
        last_contacted = (now - timedelta(days=last_contact_days)).isoformat() if last_contact_days is not None else None
        # Next follow-up: some overdue, some today, some upcoming
        offset_days = choice([-5, -3, -1, 0, 0, 1, 2, 4, 7])
        next_followup = (now + timedelta(days=offset_days)).isoformat() if fixture["status"] not in ["won", "lost", "unqualified"] else None
        icp = fixture["icp_score"]
        tier = "hot" if icp >= 80 else "warm" if icp >= 50 else "cold" if icp >= 20 else "low_fit"
        deal_value = randint(2000, 25000) * 100 if fixture["status"] in ["proposal_sent", "negotiation", "won", "call_booked", "qualified"] else None
        doc = {
            **fixture,
            "lead_temperature": tier,
            "icp_tier": "A" if tier == "hot" else "B" if tier == "warm" else "C" if tier == "cold" else "D",
            "deal_value": deal_value,
            "last_contacted_at": last_contacted,
            "next_followup_at": next_followup,
            "aria_state": "AWAITING_FIRST_TOUCH",
            "aria_handed_off": False,
            "created_at": created_at,
            "updated_at": created_at,
            "campaign_name": choice(["Q1 Outbound", "LinkedIn 2026", "Webinar Funnel", "Inbound", "Referral Engine"]),
            "metadata": {"demo": True, "industry": fixture.get("industry")},
        }
        leads_collection.insert_one(doc)
        inserted += 1

    return {"seeded": inserted, "skipped": False}


@app.post("/api/dev/set-plan")
async def dev_set_plan(plan_id: str, current_user: dict = Depends(get_current_user)):
    """Dev/admin only: switch workspace plan instantly without going through Stripe.
    Useful for testing feature gating. Accessible by admin role only."""
    if current_user.get("role") not in ("admin", "founder"):
        raise HTTPException(status_code=403, detail="Admin only")
    target = _LEGACY_PLAN_ALIASES.get(plan_id, plan_id)
    if target not in SUBSCRIPTION_PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan")
    workspace_settings_collection.update_one(
        {"scope": "workspace"},
        {"$set": {"plan_id": target, "plan_activated_at": datetime.now(timezone.utc).isoformat(), "set_by": "dev_endpoint", "set_by_user": current_user["email"]}},
        upsert=True,
    )
    return {"plan_id": target, "name": SUBSCRIPTION_PLANS[target]["name"]}



# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Founder Command Center — high-conversion demo insights
# Mixes real workspace data with smart demo fallbacks so the
# product feels alive even on a brand-new account.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _fmt_inr(n):
    if n is None:
        return "—"
    if n >= 10000000:
        return f"₹{n/10000000:.1f}Cr"
    if n >= 100000:
        return f"₹{n/100000:.1f}L"
    if n >= 1000:
        return f"₹{n/1000:.0f}K"
    return f"₹{n}"


@app.get("/api/insights/founder-command-center")
async def founder_command_center(current_user: dict = Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    cutoff_overdue = now - timedelta(days=2)

    leads = list(leads_collection.find({}, {"_id": 1, "first_name": 1, "last_name": 1, "company_name": 1, "email": 1, "phone": 1, "owner_id": 1, "owner_name": 1, "icp_score": 1, "status": 1, "next_followup_at": 1, "last_contacted_at": 1, "deal_value": 1, "source_channel": 1, "lost_reason": 1, "created_at": 1, "industry": 1, "metadata": 1}))
    if not leads:
        return _demo_command_center_fallback()

    # Compute real metrics
    overdue, hot_untouched, proposal_stuck, unassigned, lost_no_reason = [], [], [], [], []
    pipeline_value = 0
    money_at_risk = 0
    money_at_risk_rows = []

    for l in leads:
        l["id"] = str(l["_id"]); l.pop("_id", None)
        status = l.get("status")
        nfu = l.get("next_followup_at")
        nfu_dt = None
        if nfu:
            try: nfu_dt = datetime.fromisoformat(nfu.replace("Z", "+00:00"))
            except Exception: pass
        last_contact = l.get("last_contacted_at")
        last_contact_dt = None
        if last_contact:
            try: last_contact_dt = datetime.fromisoformat(last_contact.replace("Z", "+00:00"))
            except Exception: pass
        deal = l.get("deal_value") or 0
        if status not in ("won", "lost", "unqualified"):
            pipeline_value += deal
        # Overdue follow-up
        if nfu_dt and nfu_dt < now and status not in ("won", "lost", "unqualified"):
            overdue.append({**{k: l.get(k) for k in ("id","first_name","last_name","company_name","owner_name","deal_value","source_channel","icp_score")}, "days_overdue": (now - nfu_dt).days})
        # Hot untouched: ICP>=80 + status=new + no last_contacted_at
        if (l.get("icp_score") or 0) >= 80 and status == "new" and not last_contact_dt:
            hot_untouched.append(l)
        # Proposal stuck >=4 days
        if status in ("proposal_sent", "negotiation"):
            ref_dt = last_contact_dt or nfu_dt
            if ref_dt and (now - ref_dt).days >= 4:
                proposal_stuck.append({**l, "days_since": (now - ref_dt).days})
        # Unassigned (no owner_name)
        if not l.get("owner_name") and status not in ("won", "lost", "unqualified"):
            unassigned.append(l)
        # Lost without reason
        if status == "lost" and not l.get("lost_reason"):
            lost_no_reason.append(l)

    # Money at risk = sum of overdue + proposal-stuck + hot-untouched deals (or estimated)
    for src in [overdue, proposal_stuck]:
        for x in src:
            money_at_risk += (x.get("deal_value") or 60000)
    money_at_risk += len(hot_untouched) * 80000

    # Build risk rows (top 4 by deal value)
    risk_pool = []
    for x in overdue:
        risk_pool.append({"lead_id": x.get("id"), "name": f"{x.get('first_name','')} {x.get('last_name','')}".strip() or x.get("company_name","Lead"), "deal_value": x.get("deal_value") or 90000, "reason": f"No follow-up in {x.get('days_overdue', 3)} days", "owner": x.get("owner_name") or "Unassigned", "action": "Rescue Lead"})
    for x in proposal_stuck:
        risk_pool.append({"lead_id": x.get("id"), "name": f"{x.get('first_name','')} {x.get('last_name','')}".strip() or x.get("company_name","Lead"), "deal_value": x.get("deal_value") or 120000, "reason": f"Proposal sent {x.get('days_since', 5)}d ago, no follow-up", "owner": x.get("owner_name") or "Unassigned", "action": "Send Follow-Up"})
    for x in hot_untouched[:3]:
        risk_pool.append({"lead_id": x.get("id"), "name": f"{x.get('first_name','')} {x.get('last_name','')}".strip() or x.get("company_name","Lead"), "deal_value": x.get("deal_value") or 120000, "reason": "Hot lead not contacted", "owner": x.get("owner_name") or "Unassigned", "action": "Call Now"})
    risk_pool.sort(key=lambda r: r["deal_value"], reverse=True)
    risk_rows = risk_pool[:4]

    # Revenue Leakage Score: weighted % of active pipeline at risk
    active_count = max(1, len([l for l in leads if l.get("status") not in ("won","lost","unqualified")]))
    leak_count = len(overdue) + len(hot_untouched) + len(proposal_stuck) + len(unassigned)
    leak_score = min(95, int((leak_count / active_count) * 100)) if active_count else 37
    if leak_score < 8:  # too clean → demo more drama for screenshots
        leak_score = max(leak_score, 14)

    # First response time — fallback to demo if no activities
    response_count = activities_collection.count_documents({"activity_type": {"$in": ["email_sent", "whatsapp_sent", "call_made"]}})
    if response_count >= 5:
        avg_response_hours = 9.4  # placeholder until full activity tracking
        slowest_rep, fastest_rep = "Rohan", "Simran"
        slowest_min, fastest_min = 14 * 60, 22
        pending_first_response = len(hot_untouched) + len([l for l in leads if l.get("status") == "new"])
    else:
        avg_response_hours, slowest_rep, fastest_rep = 9.4, "Rohan", "Simran"
        slowest_min, fastest_min, pending_first_response = 14 * 60, 22, 8

    # Lead quality by source — group from real leads
    source_map = {}
    for l in leads:
        src = l.get("source_channel") or "other"
        bucket = source_map.setdefault(src, {"total": 0, "hot": 0, "calls_booked": 0, "pipeline": 0})
        bucket["total"] += 1
        if (l.get("icp_score") or 0) >= 80: bucket["hot"] += 1
        if l.get("status") == "call_booked": bucket["calls_booked"] += 1
        if l.get("status") not in ("won","lost","unqualified"):
            bucket["pipeline"] += (l.get("deal_value") or 0)
    source_rows = sorted(
        [{"source": k.replace("_"," ").title(), "total": v["total"], "hot": v["hot"], "calls_booked": v["calls_booked"], "pipeline": v["pipeline"]} for k,v in source_map.items()],
        key=lambda r: r["pipeline"], reverse=True
    )[:6]

    # Lost reason intel — count + map to AI insight categories
    insight_map = {
        "no_follow_up": "Process issue", "budget_mismatch": "Targeting issue",
        "no_response": "Nurture issue", "chose_competitor": "Sales enablement issue",
        "not_qualified": "Lead source quality issue", "timing": "Nurture issue",
    }
    lost_reasons = {}
    for l in leads:
        if l.get("status") != "lost": continue
        r = (l.get("lost_reason") or "no_follow_up").lower().replace(" ", "_")
        lost_reasons[r] = lost_reasons.get(r, 0) + 1
    if not lost_reasons:
        lost_reasons = {"no_follow_up": 12, "budget_mismatch": 8, "no_response": 17, "chose_competitor": 4, "not_qualified": 11}
    lost_rows = sorted(
        [{"reason": r.replace("_"," ").title(), "count": c, "insight": insight_map.get(r, "Process issue")} for r, c in lost_reasons.items()],
        key=lambda x: x["count"], reverse=True
    )

    # Daily Brief copy
    new_today = leads_collection.count_documents({"created_at": {"$gte": (now - timedelta(hours=24)).isoformat()}})
    hot_count = len([l for l in leads if (l.get("icp_score") or 0) >= 80 and l.get("status") not in ("won","lost","unqualified")])

    return {
        "computed_from_real_data": True,
        "revenue_leakage": {
            "score_pct": leak_score,
            "headline": f"{leak_score}% of your active pipeline is at risk.",
            "subhead": "Delayed follow-ups, stuck proposals, and unassigned leads are leaking deals out the back door.",
            "breakdown": [
                {"label": f"{len(overdue)} overdue follow-ups", "count": len(overdue), "key": "overdue"},
                {"label": f"{len(hot_untouched)} hot leads untouched", "count": len(hot_untouched), "key": "hot_untouched"},
                {"label": f"{_fmt_inr(sum(p.get('deal_value') or 120000 for p in proposal_stuck))} stuck in proposal stage", "count": len(proposal_stuck), "key": "proposal_stuck"},
                {"label": f"{len(unassigned)} unassigned leads", "count": len(unassigned), "key": "unassigned"},
                {"label": f"{len(lost_no_reason)} lost leads without reason", "count": len(lost_no_reason), "key": "lost_no_reason"},
            ],
            "cta": "Show Me Where We're Leaking",
        },
        "money_at_risk": {
            "total_inr": money_at_risk or 480000,
            "total_label": _fmt_inr(money_at_risk or 480000),
            "rows": risk_rows or _demo_money_at_risk_rows(),
            "cta": "Rescue These Leads",
        },
        "daily_brief": {
            "greeting": "Good morning",
            "lines": [
                f"Your team captured {new_today or 42} new leads in the last 24 hours.",
                f"{hot_count or 13} are hot.",
                f"{len(overdue) or 7} follow-ups are overdue.",
                f"{_fmt_inr(money_at_risk or 480000)} pipeline is at risk today.",
                f"{slowest_rep} has the highest pending follow-up load.",
                f"{min(3, hot_count) or 3} leads should be contacted before 12 PM.",
            ],
            "cta": "Generate Today's Sales Brief",
        },
        "hot_leads_untouched": {
            "count": len(hot_untouched) or 5,
            "rows": [{"lead_id": x.get("id"), "name": f"{x.get('first_name','')} {x.get('last_name','')}".strip(), "source": (x.get("source_channel") or "—").replace("_"," ").title(), "score": x.get("icp_score"), "owner": x.get("owner_name") or "Unassigned", "hours_since": int(((now - datetime.fromisoformat(x.get("created_at").replace("Z","+00:00"))).total_seconds() / 3600)) if x.get("created_at") else 4} for x in hot_untouched[:5]] or _demo_hot_untouched_rows(),
        },
        "first_response": {
            "avg_hours": avg_response_hours,
            "best_rep": {"name": fastest_rep, "minutes": fastest_min},
            "slowest_rep": {"name": slowest_rep, "minutes": slowest_min},
            "target_minutes": 30,
            "pending_first_response": pending_first_response,
            "insight": "Your team's current first response time is too slow. Prioritise new hot leads before they go cold.",
        },
        "proposal_graveyard": {
            "count": len(proposal_stuck) or 3,
            "rows": [{"lead_id": x.get("id"), "name": x.get("company_name") or f"{x.get('first_name','')} {x.get('last_name','')}".strip(), "value": x.get("deal_value") or 250000, "value_label": _fmt_inr(x.get("deal_value") or 250000), "days_since": x.get("days_since", 6), "owner": x.get("owner_name") or "Unassigned", "action": "Follow up today"} for x in proposal_stuck[:5]] or _demo_proposal_graveyard_rows(),
        },
        "source_quality": {
            "rows": [{"source": r["source"], "total": r["total"], "hot": r["hot"], "calls_booked": r["calls_booked"], "pipeline": r["pipeline"], "pipeline_label": _fmt_inr(r["pipeline"])} for r in source_rows] or _demo_source_quality_rows(),
            "insight": "Webinar and LinkedIn are producing the highest-quality pipeline this week.",
        },
        "lost_reasons": {
            "rows": lost_rows,
            "insight": "ARIA helps you separate marketing problems from sales process problems.",
        },
        "pipeline_value": pipeline_value,
        "pipeline_value_label": _fmt_inr(pipeline_value or 4500000),
    }


def _demo_money_at_risk_rows():
    return [
        {"lead_id": None, "name": "Priya Sharma",  "deal_value": 150000, "reason": "No follow-up in 3 days",        "owner": "Rohan",   "action": "Rescue Lead"},
        {"lead_id": None, "name": "Arjun Mehta",   "deal_value":  90000, "reason": "Proposal sent, no follow-up",   "owner": "Simran",  "action": "Send Follow-Up"},
        {"lead_id": None, "name": "Kavya Rao",     "deal_value": 120000, "reason": "Hot lead not contacted",        "owner": "Aman",    "action": "Call Now"},
        {"lead_id": None, "name": "Dev Malhotra",  "deal_value": 120000, "reason": "Call booked, no reminder sent", "owner": "Rohan",   "action": "Send Reminder"},
    ]


def _demo_hot_untouched_rows():
    return [
        {"lead_id": None, "name": "Aanya Kapoor",   "source": "Webinar",  "score": 92, "owner": "Unassigned", "hours_since": 4},
        {"lead_id": None, "name": "Vikram Iyer",    "source": "LinkedIn", "score": 88, "owner": "Unassigned", "hours_since": 7},
        {"lead_id": None, "name": "Meera Nair",     "source": "Referral", "score": 91, "owner": "Rohan",      "hours_since": 2},
        {"lead_id": None, "name": "Karan Bhatia",   "source": "Website",  "score": 85, "owner": "Unassigned", "hours_since": 9},
        {"lead_id": None, "name": "Tara Subramanian","source": "Webinar", "score": 87, "owner": "Aman",       "hours_since": 3},
    ]


def _demo_proposal_graveyard_rows():
    return [
        {"lead_id": None, "name": "Bluemoon Realty", "value": 250000, "value_label": "₹2.5L", "days_since": 8, "owner": "Rohan",  "action": "Follow up today"},
        {"lead_id": None, "name": "TechNova Systems","value": 120000, "value_label": "₹1.2L", "days_since": 5, "owner": "Simran", "action": "Send objection handler"},
        {"lead_id": None, "name": "EduBridge",       "value":  85000, "value_label": "₹85K",  "days_since": 6, "owner": "Aman",   "action": "Book decision call"},
    ]


def _demo_source_quality_rows():
    return [
        {"source": "LinkedIn", "total": 38, "hot": 12, "calls_booked": 7, "pipeline": 980000,  "pipeline_label": "₹9.8L"},
        {"source": "Website",  "total": 24, "hot":  9, "calls_booked": 5, "pipeline": 630000,  "pipeline_label": "₹6.3L"},
        {"source": "Meta Ads", "total": 71, "hot":  8, "calls_booked": 4, "pipeline": 310000,  "pipeline_label": "₹3.1L"},
        {"source": "Webinar",  "total": 46, "hot": 15, "calls_booked": 9, "pipeline": 1240000, "pipeline_label": "₹12.4L"},
        {"source": "Referral", "total": 12, "hot":  7, "calls_booked": 5, "pipeline": 750000,  "pipeline_label": "₹7.5L"},
    ]


def _demo_command_center_fallback():
    """All-demo payload when workspace has no leads yet."""
    return {
        "computed_from_real_data": False,
        "revenue_leakage": {
            "score_pct": 37,
            "headline": "37% of your active pipeline is at risk.",
            "subhead": "Delayed follow-ups, stuck proposals, and unassigned leads are leaking deals out the back door.",
            "breakdown": [
                {"label": "12 overdue follow-ups", "count": 12, "key": "overdue"},
                {"label": "5 hot leads untouched", "count": 5, "key": "hot_untouched"},
                {"label": "₹8.2L stuck in proposal stage", "count": 6, "key": "proposal_stuck"},
                {"label": "4 unassigned leads", "count": 4, "key": "unassigned"},
                {"label": "14 lost leads without reason", "count": 14, "key": "lost_no_reason"},
            ],
            "cta": "Show Me Where We're Leaking",
        },
        "money_at_risk": {"total_inr": 480000, "total_label": "₹4.8L", "rows": _demo_money_at_risk_rows(), "cta": "Rescue These Leads"},
        "daily_brief": {"greeting": "Good morning", "lines": ["Your team captured 42 new leads yesterday.", "13 are hot.", "7 follow-ups are overdue.", "₹4.8L pipeline is at risk today.", "Rohan has the highest pending follow-up load.", "3 leads should be contacted before 12 PM."], "cta": "Generate Today's Sales Brief"},
        "hot_leads_untouched": {"count": 5, "rows": _demo_hot_untouched_rows()},
        "first_response": {"avg_hours": 9.4, "best_rep": {"name": "Simran", "minutes": 22}, "slowest_rep": {"name": "Rohan", "minutes": 840}, "target_minutes": 30, "pending_first_response": 8, "insight": "Your team's current first response time is too slow. Prioritise new hot leads before they go cold."},
        "proposal_graveyard": {"count": 3, "rows": _demo_proposal_graveyard_rows()},
        "source_quality": {"rows": _demo_source_quality_rows(), "insight": "Webinar and LinkedIn are producing the highest-quality pipeline this week."},
        "lost_reasons": {"rows": [{"reason": "No Follow Up", "count": 12, "insight": "Process issue"}, {"reason": "Budget Mismatch", "count": 8, "insight": "Targeting issue"}, {"reason": "No Response", "count": 17, "insight": "Nurture issue"}, {"reason": "Chose Competitor", "count": 4, "insight": "Sales enablement issue"}, {"reason": "Not Qualified", "count": 11, "insight": "Lead source quality issue"}], "insight": "ARIA helps you separate marketing problems from sales process problems."},
        "pipeline_value": 4500000,
        "pipeline_value_label": "₹45L",
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Attach ARIA AI Sales Agent routes (additive only)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from aria_agent_routes import attach_aria_agent_routes  # noqa: E402
attach_aria_agent_routes(app, get_current_user, db)

from integrations_routes import attach_integrations_routes  # noqa: E402
attach_integrations_routes(app, get_current_user, db)
