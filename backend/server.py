from fastapi import FastAPI, HTTPException, Depends, status, Query, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient, ASCENDING, DESCENDING
from bson import ObjectId
import os
from dotenv import load_dotenv
from jose import JWTError, jwt
from passlib.context import CryptContext
import csv
import io
import asyncio
import resend
from emergentintegrations.llm.chat import LlmChat, UserMessage

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