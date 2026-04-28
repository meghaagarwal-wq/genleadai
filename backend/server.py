from fastapi import FastAPI, HTTPException, Depends, status, Query, UploadFile, File, BackgroundTasks, Response, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
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

# Database
mongo_client = MongoClient(os.getenv("MONGO_URL"))
db = mongo_client[os.getenv("DB_NAME")]

# Collections
leads_collection = db["leads"]
activities_collection = db["activities"]
campaigns_collection = db["campaigns"]
users_collection = db["users"]
pipelines_collection = db["pipelines"]
aria_conversations_collection = db["aria_conversations"]
workspace_assets_collection = db["workspace_assets"]
aria_settings_collection = db["aria_settings"]

# Security
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 10080))

# Resend Email
resend.api_key = os.getenv("RESEND_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "onboarding@resend.dev")

# Pydantic Models
class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: str = "sales_rep"

class UserLogin(BaseModel):
    email: EmailStr
    password: str

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
    name: str
    description: Optional[str] = None
    channel: str
    lead_type: str
    status: str = "draft"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    budget: Optional[float] = None
    spend: Optional[float] = 0.0
    target_audience: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    goal_leads: Optional[int] = None
    goal_conversions: Optional[int] = None

class AIScoreRequest(BaseModel):
    lead_id: str

class AIEmailGenerateRequest(BaseModel):
    lead_id: str
    goal: str
    tone: str = "professional"
    length: str = "medium"

class AIChatRequest(BaseModel):
    query: str

# Helper Functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = users_collection.find_one({"email": email}, {"_id": 0})
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def serialize_doc(doc):
    if doc and "_id" in doc:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
    return doc

# Auth Endpoints
@app.post("/api/auth/register")
async def register(user: UserRegister):
    if users_collection.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_doc = {
        "email": user.email,
        "password_hash": get_password_hash(user.password),
        "full_name": user.full_name,
        "role": user.role,
        "avatar_url": f"https://ui-avatars.com/api/?name={user.full_name.replace(' ', '+')}&background=0055FF&color=fff",
        "team": "Sales",
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    result = users_collection.insert_one(user_doc)
    token = create_access_token({"sub": user.email})
    
    return {"token": token, "user": {"email": user.email, "full_name": user.full_name, "role": user.role}}

@app.post("/api/auth/login")
async def login(credentials: UserLogin):
    user = users_collection.find_one({"email": credentials.email})
    if not user or not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    token = create_access_token({"sub": credentials.email})
    return {
        "token": token,
        "user": {
            "email": user["email"],
            "full_name": user["full_name"],
            "role": user["role"],
            "avatar_url": user.get("avatar_url")
        }
    }

@app.get("/api/auth/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return current_user

# Lead Endpoints
@app.post("/api/leads")
async def create_lead(lead: LeadCreate, current_user: dict = Depends(get_current_user)):
    lead_doc = lead.dict()
    lead_doc["created_at"] = datetime.now(timezone.utc).isoformat()
    lead_doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    lead_doc["created_by"] = current_user["email"]
    lead_doc["icp_score"] = 0
    lead_doc["icp_tier"] = "cold"
    lead_doc["assigned_to"] = None
    lead_doc["last_contacted_at"] = None
    lead_doc["next_followup_at"] = None
    
    result = leads_collection.insert_one(lead_doc)
    lead_doc = serialize_doc(lead_doc)
    
    return lead_doc

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
    query = {}
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
    candidates = list(leads_collection.find({"status": {"$nin": excluded}}).limit(200))
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
        lead = leads_collection.find_one({"_id": ObjectId(lead_id)})
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        return serialize_doc(lead)
    except:
        raise HTTPException(status_code=400, detail="Invalid lead ID")

@app.patch("/api/leads/{lead_id}")
async def update_lead(lead_id: str, lead_update: LeadUpdate, current_user: dict = Depends(get_current_user)):
    try:
        update_data = {k: v for k, v in lead_update.dict().items() if v is not None}
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        result = leads_collection.update_one(
            {"_id": ObjectId(lead_id)},
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
        
        lead = leads_collection.find_one({"_id": ObjectId(lead_id)})
        return serialize_doc(lead)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/leads/{lead_id}")
async def delete_lead(lead_id: str, current_user: dict = Depends(get_current_user)):
    try:
        result = leads_collection.delete_one({"_id": ObjectId(lead_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Lead not found")
        return {"message": "Lead deleted successfully"}
    except:
        raise HTTPException(status_code=400, detail="Invalid lead ID")

# Activity Endpoints
@app.post("/api/activities")
async def create_activity(activity: ActivityCreate, current_user: dict = Depends(get_current_user)):
    activity_doc = activity.dict()
    activity_doc["user_id"] = current_user["email"]
    activity_doc["created_at"] = datetime.now(timezone.utc).isoformat()
    
    result = activities_collection.insert_one(activity_doc)
    
    # Update lead's last_contacted_at
    try:
        leads_collection.update_one(
            {"_id": ObjectId(activity.lead_id)},
            {"$set": {"last_contacted_at": datetime.now(timezone.utc).isoformat()}}
        )
    except:
        pass
    
    activity_doc = serialize_doc(activity_doc)
    return activity_doc

@app.get("/api/leads/{lead_id}/activities")
async def get_lead_activities(lead_id: str, current_user: dict = Depends(get_current_user)):
    activities = list(activities_collection.find({"lead_id": lead_id}).sort("created_at", DESCENDING))
    activities = [serialize_doc(activity) for activity in activities]
    return {"activities": activities}

# Campaign Endpoints
@app.post("/api/campaigns")
async def create_campaign(campaign: CampaignCreate, current_user: dict = Depends(get_current_user)):
    campaign_doc = campaign.dict()
    campaign_doc["created_at"] = datetime.now(timezone.utc).isoformat()
    campaign_doc["created_by"] = current_user["email"]
    
    result = campaigns_collection.insert_one(campaign_doc)
    campaign_doc = serialize_doc(campaign_doc)
    
    return campaign_doc

@app.get("/api/campaigns")
async def get_campaigns(current_user: dict = Depends(get_current_user)):
    campaigns = list(campaigns_collection.find({}).sort("created_at", DESCENDING).limit(100))
    
    # Enrich with lead counts
    for campaign in campaigns:
        campaign_id = str(campaign["_id"])
        campaign["total_leads"] = leads_collection.count_documents({"campaign_id": campaign_id})
        campaign["qualified_leads"] = leads_collection.count_documents({
            "campaign_id": campaign_id,
            "status": {"$in": ["qualified", "proposal_sent", "negotiation", "won"]}
        })
    
    campaigns = [serialize_doc(campaign) for campaign in campaigns]
    return {"campaigns": campaigns}

@app.get("/api/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str, current_user: dict = Depends(get_current_user)):
    try:
        campaign = campaigns_collection.find_one({"_id": ObjectId(campaign_id)})
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Get campaign leads
        campaign_id_str = str(campaign["_id"])
        campaign["leads"] = leads_collection.count_documents({"campaign_id": campaign_id_str})
        
        return serialize_doc(campaign)
    except:
        raise HTTPException(status_code=400, detail="Invalid campaign ID")

# AI Endpoints
@app.post("/api/ai/score")
async def score_lead(request: AIScoreRequest, current_user: dict = Depends(get_current_user)):
    try:
        lead = leads_collection.find_one({"_id": ObjectId(request.lead_id)})
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        # Prepare lead data for AI
        lead_info = f"""
        Lead Type: {lead.get('lead_type')}
        Name: {lead.get('first_name')} {lead.get('last_name')}
        Email: {lead.get('email')}
        Company: {lead.get('company_name', 'N/A')}
        Job Title: {lead.get('job_title', 'N/A')}
        Industry: {lead.get('industry', 'N/A')}
        Revenue Range: {lead.get('revenue_range', 'N/A')}
        Source Channel: {lead.get('source_channel')}
        """
        
        # Call Claude API
        chat = LlmChat(
            api_key=os.getenv("EMERGENT_LLM_KEY"),
            session_id=f"icp_score_{request.lead_id}",
            system_message="You are an expert B2B/B2C sales qualification assistant. Score leads against ideal customer profiles and return structured data."
        )
        chat.with_model("anthropic", "claude-4-sonnet-20250514")
        
        prompt = f"""
        Score this lead from 0-100 based on how well they match an ideal customer profile for a growth marketing agency.
        
        {lead_info}
        
        Provide:
        1. Score (0-100)
        2. Tier (hot: 70-100, warm: 40-69, cold: 0-39)
        3. Three bullet points explaining the score
        4. Recommended next action
        5. Any red flags
        
        Format: Return ONLY valid JSON with keys: score, tier, reasoning (array), next_action, red_flags (array)
        """
        
        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)
        
        # Parse AI response
        import json
        try:
            # Extract JSON from response
            response_text = response.strip()
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            ai_result = json.loads(response_text)
        except:
            # Fallback if JSON parsing fails
            ai_result = {
                "score": 50,
                "tier": "warm",
                "reasoning": ["Lead profile analyzed", "Standard qualification criteria applied", "Moderate fit for target ICP"],
                "next_action": "Schedule discovery call to understand needs",
                "red_flags": []
            }
        
        # Update lead with ICP score
        leads_collection.update_one(
            {"_id": ObjectId(request.lead_id)},
            {"$set": {
                "icp_score": ai_result["score"],
                "icp_tier": ai_result["tier"],
                "icp_reasoning": ai_result.get("reasoning", []),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        # Log activity
        activity_doc = {
            "lead_id": request.lead_id,
            "user_id": current_user["email"],
            "activity_type": "score_updated",
            "subject": f"ICP Score: {ai_result['score']} ({ai_result['tier']})",
            "body": "AI-powered ICP scoring completed",
            "outcome": None,
            "duration_minutes": None,
            "metadata": ai_result,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        activities_collection.insert_one(activity_doc)
        
        return ai_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI scoring failed: {str(e)}")

@app.post("/api/ai/email-generate")
async def generate_email(request: AIEmailGenerateRequest, current_user: dict = Depends(get_current_user)):
    try:
        lead = leads_collection.find_one({"_id": ObjectId(request.lead_id)})
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        lead_info = f"""
        Name: {lead.get('first_name')} {lead.get('last_name')}
        Company: {lead.get('company_name', 'N/A')}
        Job Title: {lead.get('job_title', 'N/A')}
        Industry: {lead.get('industry', 'N/A')}
        """
        
        chat = LlmChat(
            api_key=os.getenv("EMERGENT_LLM_KEY"),
            session_id=f"email_gen_{request.lead_id}",
            system_message="You are an expert email copywriter for B2B sales and marketing."
        )
        chat.with_model("anthropic", "claude-4-sonnet-20250514")
        
        prompt = f"""
        Write a {request.tone} email for this lead:
        
        {lead_info}
        
        Goal: {request.goal}
        Length: {request.length}
        
        Return JSON with keys: subject, body
        """
        
        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)
        
        import json
        try:
            response_text = response.strip()
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            email_result = json.loads(response_text)
        except:
            email_result = {
                "subject": "Let's connect",
                "body": f"Hi {lead.get('first_name')},\n\nI wanted to reach out regarding {request.goal}.\n\nBest regards"
            }
        
        return email_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email generation failed: {str(e)}")

@app.post("/api/ai/chat")
async def ai_chat(request: AIChatRequest, current_user: dict = Depends(get_current_user)):
    try:
        chat = LlmChat(
            api_key=os.getenv("EMERGENT_LLM_KEY"),
            session_id=f"chat_{current_user['email']}",
            system_message="You are a helpful AI assistant for a Lead Management System. Help users query and analyze their lead data."
        )
        chat.with_model("anthropic", "claude-4-sonnet-20250514")
        
        user_message = UserMessage(text=request.query)
        response = await chat.send_message(user_message)
        
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")

# Analytics Endpoints
@app.get("/api/analytics/dashboard")
async def get_dashboard_analytics(current_user: dict = Depends(get_current_user)):
    total_leads = leads_collection.count_documents({})
    
    # By status
    status_counts = {}
    for status in ["new", "contacted", "qualified", "proposal_sent", "negotiation", "won", "lost"]:
        status_counts[status] = leads_collection.count_documents({"status": status})
    
    # By channel
    channel_counts = {}
    for channel in ["whatsapp", "email", "linkedin", "instagram", "facebook", "website_form", "cold_call", "referral"]:
        channel_counts[channel] = leads_collection.count_documents({"source_channel": channel})
    
    # By lead type
    b2b_count = leads_collection.count_documents({"lead_type": "B2B"})
    b2c_count = leads_collection.count_documents({"lead_type": "B2C"})
    
    # By ICP tier
    hot_count = leads_collection.count_documents({"icp_tier": "hot"})
    warm_count = leads_collection.count_documents({"icp_tier": "warm"})
    cold_count = leads_collection.count_documents({"icp_tier": "cold"})
    
    return {
        "total_leads": total_leads,
        "status_distribution": status_counts,
        "channel_distribution": channel_counts,
        "lead_type_distribution": {"B2B": b2b_count, "B2C": b2c_count},
        "icp_distribution": {"hot": hot_count, "warm": warm_count, "cold": cold_count}
    }

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

# Team/Users Endpoints
@app.get("/api/users")
async def get_users(current_user: dict = Depends(get_current_user)):
    users = list(users_collection.find({"is_active": True}, {"password_hash": 0, "_id": 0}).limit(100))
    return {"users": users}

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "GenLeadAI LMS API"}

# Email Endpoints
class EmailSendRequest(BaseModel):
    recipient_email: EmailStr
    subject: str
    html_content: str

@app.post("/api/email/send")
async def send_email(request: EmailSendRequest, current_user: dict = Depends(get_current_user)):
    try:
        params = {
            "from": SENDER_EMAIL,
            "to": [request.recipient_email],
            "subject": request.subject,
            "html": request.html_content,
        }
        email = await asyncio.to_thread(resend.Emails.send, params)
        return {"status": "success", "message": f"Email sent to {request.recipient_email}", "email_id": email.get("id")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

# AI Lead Summary
class AISummaryRequest(BaseModel):
    lead_id: str

@app.post("/api/ai/summarize")
async def summarize_lead(request: AISummaryRequest, current_user: dict = Depends(get_current_user)):
    try:
        lead = leads_collection.find_one({"_id": ObjectId(request.lead_id)})
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        activities = list(activities_collection.find({"lead_id": request.lead_id}).sort("created_at", DESCENDING).limit(20))
        
        activity_log = "\n".join([
            f"- {a.get('activity_type')}: {a.get('subject', 'N/A')} ({a.get('created_at', 'N/A')})"
            for a in activities
        ])
        
        chat = LlmChat(
            api_key=os.getenv("EMERGENT_LLM_KEY"),
            session_id=f"summary_{request.lead_id}",
            system_message="You are a senior sales analyst. Provide concise, actionable summaries."
        )
        chat.with_model("anthropic", "claude-4-sonnet-20250514")
        
        prompt = f"""Summarize this lead's journey and recommend the next best action:

Lead: {lead.get('first_name')} {lead.get('last_name')}
Company: {lead.get('company_name', 'N/A')}
Status: {lead.get('status')}
ICP Score: {lead.get('icp_score')} ({lead.get('icp_tier')})

Activity History:
{activity_log if activity_log else 'No activities logged yet.'}

Give a 3-4 sentence summary and a clear next step recommendation."""
        
        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)
        
        return {"summary": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summarization failed: {str(e)}")


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
    """Get ARIA performance analytics."""
    # Total conversations
    leads_with_aria = list(leads_collection.find(
        {"aria_state": {"$exists": True, "$ne": None}},
        {"_id": 0, "aria_state": 1, "icp_tier": 1, "status": 1}
    ))
    
    total_conversations = len(leads_with_aria)
    
    # Count by state
    state_counts = {}
    for lead in leads_with_aria:
        state = lead.get("aria_state", "UNKNOWN")
        state_counts[state] = state_counts.get(state, 0) + 1
    
    # Count messages
    total_aria_messages = aria_conversations_collection.count_documents({"role": "aria"})
    total_lead_replies = aria_conversations_collection.count_documents({"role": "lead"})
    
    # Reply rate
    reply_rate = round((total_lead_replies / max(total_conversations, 1)) * 100, 1)
    
    # Booking rate
    booked = state_counts.get("MEETING_BOOKED", 0) + leads_collection.count_documents({"aria_booking_url": {"$exists": True, "$ne": None}})
    booking_rate = round((booked / max(total_conversations, 1)) * 100, 1)
    
    # Qualification rate
    active_or_beyond = sum(state_counts.get(s, 0) for s in ["CONVERSATION_ACTIVE", "BOOKING_ATTEMPTED", "MEETING_BOOKED", "ESCALATED_TO_HUMAN"])
    qualification_rate = round((active_or_beyond / max(total_conversations, 1)) * 100, 1)
    
    # Disqualification reasons
    dnc_count = state_counts.get("DO_NOT_CONTACT", 0)
    disqualified_count = leads_collection.count_documents({"aria_state": "DO_NOT_CONTACT"})
    
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
    """Get live feed of active ARIA conversations."""
    active_leads = list(leads_collection.find(
        {"aria_state": {"$exists": True, "$ne": None}},
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

# ─── Calendly Endpoints ───

@app.get("/api/calendly/event-types")
async def get_event_types(current_user: dict = Depends(get_current_user)):
    """Get available Calendly event types."""
    event_types = await get_calendly_event_types()
    return {"event_types": event_types}

@app.get("/api/calendly/availability/{event_type_uri:path}")
async def get_availability(event_type_uri: str, current_user: dict = Depends(get_current_user)):
    """Get available slots for a Calendly event type."""
    slots = await get_calendly_availability(event_type_uri)
    return {"available_slots": slots}

@app.get("/api/calendly/user")
async def get_calendly_user_info(current_user: dict = Depends(get_current_user)):
    """Get current Calendly user info."""
    user = await get_calendly_user()
    return {"user": user}

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
        # Get all active leads (not won, lost, do_not_contact)
        excluded = ["won", "lost", "do_not_contact"]
        candidates = list(leads_collection.find(
            {"status": {"$nin": excluded}},
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

SUBSCRIPTION_PLANS = {
    "starter": {"name": "Starter", "amount": 49.00, "leads": 500, "ai_credits": 100},
    "growth": {"name": "Growth", "amount": 149.00, "leads": 2000, "ai_credits": 500},
    "scale": {"name": "Scale", "amount": 399.00, "leads": 10000, "ai_credits": 2000},
}

class CheckoutRequest(BaseModel):
    plan_id: str
    origin_url: str

@app.post("/api/billing/checkout")
async def create_checkout(request: CheckoutRequest, http_request: object = None, current_user: dict = Depends(get_current_user)):
    """Create Stripe checkout session for subscription."""
    plan = SUBSCRIPTION_PLANS.get(request.plan_id)
    if not plan:
        raise HTTPException(status_code=400, detail="Invalid plan")

    from starlette.requests import Request
    stripe_key = os.getenv("STRIPE_API_KEY")
    host_url = request.origin_url.rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"

    stripe_checkout = StripeCheckout(api_key=stripe_key, webhook_url=webhook_url)

    success_url = f"{host_url}/settings?session_id={{CHECKOUT_SESSION_ID}}&payment=success"
    cancel_url = f"{host_url}/settings?payment=cancelled"

    checkout_req = CheckoutSessionRequest(
        amount=plan["amount"],
        currency="usd",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"plan_id": request.plan_id, "user_email": current_user["email"], "plan_name": plan["name"]}
    )

    session = await stripe_checkout.create_checkout_session(checkout_req)

    payment_transactions.insert_one({
        "session_id": session.session_id,
        "user_email": current_user["email"],
        "plan_id": request.plan_id,
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

    # Update transaction
    existing = payment_transactions.find_one({"session_id": session_id})
    if existing and existing.get("payment_status") != "paid":
        payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {"payment_status": status.payment_status, "status": status.status, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )

    return {"status": status.status, "payment_status": status.payment_status, "amount": status.amount_total, "currency": status.currency}

@app.post("/api/webhook/stripe")
async def stripe_webhook(request: object):
    """Handle Stripe webhook events."""
    return {"received": True}

@app.get("/api/billing/plans")
async def get_billing_plans():
    """Get available subscription plans."""
    return {"plans": SUBSCRIPTION_PLANS}

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

@app.get("/api/onboarding/status")
async def get_onboarding_status(current_user: dict = Depends(get_current_user)):
    """Check if onboarding is completed."""
    status = onboarding_collection.find_one({"user_email": current_user["email"]}, {"_id": 0})
    return {"onboarding": status, "completed": status.get("completed", False) if status else False}

@app.post("/api/onboarding/complete")
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