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
    campaigns = list(campaigns_collection.find({}).sort("created_at", DESCENDING))
    
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
    users = list(users_collection.find({"is_active": True}, {"password_hash": 0, "_id": 0}))
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