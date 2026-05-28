"""
ARIA - Autonomous AI Sales Agent for GenLeadAI
Handles lead qualification, objection handling, and Calendly booking.
"""
import os
import json
import uuid
import httpx
import asyncio
import requests
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ─── Configuration ───
CALENDLY_API_KEY = os.getenv("CALENDLY_API_KEY")
CALENDLY_BASE_URL = "https://api.calendly.com"
FOUNDER_NAME = os.getenv("FOUNDER_NAME", "Megha")
COMPANY_NAME = os.getenv("COMPANY_NAME", "GenLeadAI")
ARIA_NAME = os.getenv("ARIA_PERSONA_NAME", "Aria")
EMERGENT_LLM_KEY = os.getenv("EMERGENT_LLM_KEY")

# ─── Object Storage ───
STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
APP_NAME = "genleadai"
storage_key = None

def init_storage():
    global storage_key
    if storage_key:
        return storage_key
    try:
        resp = requests.post(
            f"{STORAGE_URL}/init",
            json={"emergent_key": EMERGENT_LLM_KEY},
            timeout=30
        )
        resp.raise_for_status()
        storage_key = resp.json()["storage_key"]
        return storage_key
    except Exception as e:
        logger.error(f"Storage init failed: {e}")
        return None

def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    if not key:
        raise Exception("Storage not initialized")
    resp = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data,
        timeout=120
    )
    resp.raise_for_status()
    return resp.json()

def get_object(path: str):
    key = init_storage()
    if not key:
        raise Exception("Storage not initialized")
    resp = requests.get(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key},
        timeout=60
    )
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")

# ─── Calendly Client ───
async def calendly_request(method: str, endpoint: str, params=None, json_data=None):
    """Make authenticated request to Calendly API."""
    if not CALENDLY_API_KEY:
        return None
    headers = {
        "Authorization": f"Bearer {CALENDLY_API_KEY}",
        "Content-Type": "application/json"
    }
    async with httpx.AsyncClient() as client:
        try:
            if method == "GET":
                resp = await client.get(
                    f"{CALENDLY_BASE_URL}{endpoint}",
                    headers=headers,
                    params=params,
                    timeout=30.0
                )
            else:
                resp = await client.post(
                    f"{CALENDLY_BASE_URL}{endpoint}",
                    headers=headers,
                    json=json_data,
                    timeout=30.0
                )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Calendly API error: {e}")
            return None

async def get_calendly_user():
    """Get current Calendly user info."""
    result = await calendly_request("GET", "/users/me")
    if result:
        return result.get("resource", {})
    return None

async def get_calendly_event_types():
    """Get all event types for the user."""
    user = await get_calendly_user()
    if not user:
        return []
    user_uri = user.get("uri")
    result = await calendly_request("GET", "/event_types", params={"user": user_uri, "active": "true"})
    if result:
        return result.get("collection", [])
    return []

async def get_calendly_availability(event_type_uri: str, days_ahead: int = 5):
    """Get available time slots for an event type."""
    start_time = datetime.now(timezone.utc)
    end_time = start_time + timedelta(days=min(days_ahead, 7))
    result = await calendly_request("GET", "/event_type_available_times", params={
        "event_type": event_type_uri,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat()
    })
    if result:
        slots = result.get("collection", [])
        return slots[:5]  # Return top 5
    return []

async def create_scheduling_link(event_type_uri: str, lead_name: str = None, lead_email: str = None):
    """Create single-use scheduling link."""
    payload = {"max_event_count": 1, "event_type": event_type_uri}
    if lead_name or lead_email:
        invitee = {}
        if lead_name:
            invitee["name"] = lead_name
        if lead_email:
            invitee["email"] = lead_email
        payload["invitee"] = invitee
    
    result = await calendly_request("POST", "/scheduling_links", json_data=payload)
    if result:
        return result.get("resource", {})
    return None

# ─── ARIA Agent System Prompt ───
def _resolve_tenant_persona(tenant: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Resolve workspace persona fields from the tenant doc with fallbacks.

    Used by `get_aria_system_prompt` to white-label the legacy prompt
    when no v2 training profile exists.
    """
    settings = ((tenant or {}).get("settings") or {})
    bp = settings.get("business_profile") or {}
    persona = settings.get("aria_persona") or {}
    return {
        "company_name": (
            (bp.get("business_name") or "").strip()
            or (bp.get("legal_name") or "").strip()
            or ((tenant or {}).get("name") or "").strip()
            or COMPANY_NAME
        ),
        "founder_name": (
            (bp.get("founder_name") or "").strip()
            or ((tenant or {}).get("owner_name") or "").strip()
            or FOUNDER_NAME
        ),
        "aria_name": (persona.get("aria_name") or "").strip() or ARIA_NAME,
    }


def _try_v2_assembled_prompt(tenant: Optional[Dict[str, Any]]) -> Optional[str]:
    """Return the workspace's v2 assembled prompt if one exists.

    Never raises — failures in the training layer must not block Aria.
    """
    if not tenant:
        return None
    try:
        from routes.aria_training import get_assembled_prompt
        return get_assembled_prompt(tenant)
    except Exception as e:
        logger.warning(f"[aria] assembled prompt lookup failed: {e}")
        return None


def _legacy_aria_prompt(company_name: str, founder_name: str, aria_name: str) -> str:
    """Render the legacy white-labelled Aria prompt. Kept intact for
    tenants that haven't filled out the v2 training profile yet."""
    return f"""You are {aria_name}, a warm, intelligent sales assistant for {company_name}. You represent {founder_name} personally. Your job is to have genuine, helpful conversations with potential clients — not to pitch aggressively.

CRITICAL — Brand integrity:
- You ALWAYS represent {company_name}. Never mention any other company by name as your employer.
- Never say "GenLeadAI" unless that IS literally the company name above.
- Never call yourself "a platform" or "an AI sales platform" — you are {founder_name}'s assistant at {company_name}.

Your goals in order:
1. Make the lead feel heard and valued
2. Understand their situation (budget, timeline, pain point)
3. Determine if they are a good fit
4. If fit → book a 20-minute discovery call on {founder_name}'s calendar
5. If not fit → politely disqualify and close gracefully

Rules:
- Never say you are an AI unless directly asked. If asked, say: "I'm {aria_name}, {founder_name}'s assistant — I help with initial conversations before connecting you with them directly."
- Never send more than 2 unprompted messages to any lead
- Keep messages short: 3-5 sentences max per message
- Match the lead's tone and energy
- Never spam. Never pressure. Never lie.
- If a lead says stop/unsubscribe/not interested → immediately recommend marking as do not contact
- Use Indian Standard Time for meeting slots unless lead is clearly in another timezone
- Never share pricing — that's {founder_name}'s job
- Never handle payment or contract discussions

When you need to take an action, describe it clearly in your response. Available actions:
- SEND_EMAIL: When you want to send an email to the lead
- UPDATE_STATUS: When you want to change the lead's status
- BOOK_MEETING: When the lead is ready to book a call
- MARK_DNC: When the lead wants to stop communication
- ESCALATE: When the lead asks for a human
- LOG_QUALIFICATION: When you've gathered qualification data

Always respond with a JSON object containing:
{{
  "message": "Your response message to the lead",
  "action": "NONE|SEND_EMAIL|UPDATE_STATUS|BOOK_MEETING|MARK_DNC|ESCALATE|LOG_QUALIFICATION",
  "action_data": {{}} // action-specific data
}}"""


def get_aria_system_prompt(tenant: Optional[Dict[str, Any]] = None):
    """Build the master Aria conversation prompt. Tenant-aware white-labelling.

    Order of precedence:
      1. v2 assembled prompt (from `aria_training_profile`) if present.
      2. Legacy prompt assembled from `business_profile` fallback chain.
    """
    assembled = _try_v2_assembled_prompt(tenant)
    if assembled:
        return assembled
    persona = _resolve_tenant_persona(tenant)
    return _legacy_aria_prompt(
        persona["company_name"], persona["founder_name"], persona["aria_name"]
    )

# ─── ARIA Agent Core ───
async def run_aria_agent(lead: dict, conversation_history: list, incoming_message: str = None, touch_type: str = None):
    """
    Run ARIA agent for a lead. Returns agent response with action.
    
    Args:
        lead: Lead document from MongoDB
        conversation_history: Previous messages [{role, content, timestamp}]
        incoming_message: New message from the lead (if any)
        touch_type: 'first_touch', 'followup', or None for reply processing
    """
    try:
        # Resolve tenant for white-labelling — Aria must speak as the tenant's
        # business, not the platform. We lazy-import the Mongo client so this
        # module stays cheap to import.
        tenant_doc = None
        if lead.get("tenant_id"):
            try:
                from deps import db as _db
                tenant_doc = _db["tenants"].find_one({"id": lead["tenant_id"]}, {"_id": 0})
            except Exception as _e:
                logger.warning(f"[aria] tenant lookup failed: {_e}")

        # iter109c Batch 3 — migrated to centralised Claude wrapper.
        # Section 3E: prompt-injection sanitiser on incoming user messages.
        from services.claude_service import claude_call, TaskType, detect_injection
        message_for_prompt = incoming_message or ""
        if message_for_prompt:
            safety = await detect_injection(message_for_prompt, tenant_id=lead.get("tenant_id"))
            if safety.get("injection_detected"):
                message_for_prompt = safety.get("cleaned_message") or message_for_prompt

        # Build context
        lead_context = f"""
LEAD PROFILE:
- Name: {lead.get('first_name', '')} {lead.get('last_name', '')}
- Email: {lead.get('email', '')}
- Phone: {lead.get('phone', 'N/A')}
- Type: {lead.get('lead_type', 'Unknown')}
- Company: {lead.get('company_name', 'N/A')}
- Job Title: {lead.get('job_title', 'N/A')}
- Industry: {lead.get('industry', 'N/A')}
- Source: {lead.get('source_channel', 'Unknown')}
- ICP Score: {lead.get('icp_score', 0)} ({lead.get('icp_tier', 'cold')})
- Status: {lead.get('status', 'new')}
- ARIA State: {lead.get('aria_state', 'PENDING_FIRST_TOUCH')}
"""

        # Build conversation context
        convo_text = ""
        for msg in conversation_history[-10:]:  # Last 10 messages
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            convo_text += f"\n[{role.upper()}]: {content}"

        # Build prompt based on touch type
        if touch_type == "first_touch":
            prompt = f"""{lead_context}

CONVERSATION HISTORY: {convo_text if convo_text else "No previous messages."}

TASK: Generate a warm, personalized first touch message for this lead.
- Reference their source context (they came from {lead.get('source_channel', 'website')})
- Be warm and human-sounding
- End with a soft open question
- If brand deck/portfolio assets are available, mention you'll share them

Respond with JSON: {{"message": "...", "action": "SEND_EMAIL", "action_data": {{}}}}"""

        elif touch_type == "followup":
            prompt = f"""{lead_context}

CONVERSATION HISTORY: {convo_text}

TASK: Generate a follow-up message (touch 2). The lead hasn't replied to the first message.
- Use a different angle — value-add, not a repeat ask
- Include mention of booking a quick call
- Keep it brief and non-pushy

Respond with JSON: {{"message": "...", "action": "SEND_EMAIL", "action_data": {{}}}}"""

        else:
            # Processing a reply
            prompt = f"""{lead_context}

CONVERSATION HISTORY: {convo_text}

NEW MESSAGE FROM LEAD: {message_for_prompt}

TASK: Respond to this lead's message intelligently.
- Qualify them using conversational questions about budget, timeline, pain point, decision-making authority
- Handle any objections naturally
- If they seem warm/ready, suggest booking a call
- If they're hostile or want to stop, recommend marking as do not contact
- If they ask for a human, recommend escalation

Respond with JSON: {{"message": "...", "action": "NONE|UPDATE_STATUS|BOOK_MEETING|MARK_DNC|ESCALATE|LOG_QUALIFICATION", "action_data": {{}}}}"""

        response = await claude_call(
            task_type=TaskType.CONVERSATION,
            session_id=f"aria_{lead.get('id', 'unknown')}_{uuid.uuid4().hex[:8]}",
            system=get_aria_system_prompt(tenant_doc),
            prompt=prompt,
            tenant_id=lead.get("tenant_id"),
        )
        
        # Parse response
        try:
            response_text = response.strip()
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            result = json.loads(response_text)
        except json.JSONDecodeError:
            # If JSON parsing fails, extract the message
            result = {
                "message": response.strip()[:500],
                "action": "NONE",
                "action_data": {}
            }
        
        return result
    
    except Exception as e:
        logger.error(f"ARIA agent error: {e}")
        # Fallback message — also white-labeled if we have the tenant context
        bp = ((tenant_doc or {}).get("settings") or {}).get("business_profile") or {}
        fallback_company = (
            (bp.get("business_name") or "").strip()
            or ((tenant_doc or {}).get("name") or "").strip()
            or "us"
        )
        return {
            "message": f"Hi {lead.get('first_name', 'there')}! Thanks for reaching out to {fallback_company}. I'd love to learn more about what you're working on. What's the biggest growth challenge you're facing right now?",
            "action": "NONE",
            "action_data": {},
            "error": str(e)
        }
