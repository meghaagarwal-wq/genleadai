"""AI endpoints: ICP scoring, email generation, chat, summarization."""
import json
import os
from datetime import datetime, timezone
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pymongo import DESCENDING

from emergentintegrations.llm.chat import LlmChat, UserMessage

from deps import (
    leads_collection,
    activities_collection,
    get_current_user,
)

router = APIRouter(prefix="/api/ai", tags=["ai"])

CLAUDE_MODEL = ("anthropic", "claude-4-sonnet-20250514")


class AIScoreRequest(BaseModel):
    lead_id: str


class AIEmailGenerateRequest(BaseModel):
    lead_id: str
    goal: str
    tone: str = "professional"
    length: str = "medium"


class AIChatRequest(BaseModel):
    query: str


class AISummaryRequest(BaseModel):
    lead_id: str


def _extract_json(response_text: str):
    """Strip ``` fences and parse JSON from an LLM response."""
    text = response_text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    return json.loads(text)


@router.post("/score")
async def score_lead(request: AIScoreRequest, current_user: dict = Depends(get_current_user)):
    try:
        # Tenant-scoped lookup: never score a lead belonging to another tenant
        lead = leads_collection.find_one({
            "_id": ObjectId(request.lead_id),
            "tenant_id": current_user.get("tenant_id"),
        })
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

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

        # Pull this tenant's ICP definition + business context so scoring is
        # genuinely tenant-aware rather than hardcoded to "growth marketing agency".
        from pymongo import MongoClient
        import os as _os
        _db = MongoClient(_os.environ.get("MONGO_URL"))[_os.environ.get("DB_NAME")]
        tenant_doc = _db["tenants"].find_one(
            {"id": current_user.get("tenant_id")},
            {"_id": 0, "name": 1, "settings": 1},
        ) or {}
        onboarding = _db["onboarding_config"].find_one(
            {"tenant_id": current_user.get("tenant_id")},
            {"_id": 0},
        ) or {}
        settings = tenant_doc.get("settings") or {}
        bp = onboarding.get("business_profile") or {}
        sp = onboarding.get("sales_process") or {}

        business_name = bp.get("business_name") or tenant_doc.get("name") or "this business"
        icp_definition = (
            settings.get("icp_definition")
            or "An ideal customer profile best-fit to this business based on industry, company size, buying signals, and role seniority."
        )
        business_ctx = (
            f"Business: {business_name}\n"
            f"Industry: {bp.get('industry', '—')}\n"
            f"Product/Service: {sp.get('product_description', '—')}\n"
            f"Primary market: {bp.get('primary_market', '—')}"
        )

        chat = LlmChat(
            api_key=os.getenv("EMERGENT_LLM_KEY"),
            session_id=f"icp_score_{request.lead_id}",
            system_message=(
                f"You are an expert B2B/B2C sales qualification assistant scoring leads for {business_name}. "
                "Score each lead against their ICP and return strict JSON only."
            ),
        )
        chat.with_model(*CLAUDE_MODEL)

        prompt = f"""Score this lead from 0-100 based on how well they match {business_name}'s ideal customer profile.

{business_ctx}

THIS BUSINESS'S ICP:
{icp_definition}

LEAD:
{lead_info}

Provide:
1. Score (0-100)
2. Tier (hot: 70-100, warm: 40-69, cold: 0-39)
3. Three bullet points explaining the score — reference specific ICP criteria above.
4. Recommended next action tailored to this business's product/service.
5. Any red flags.

Format: Return ONLY valid JSON with keys: score, tier, reasoning (array), next_action, red_flags (array)
"""

        response = await chat.send_message(UserMessage(text=prompt))
        try:
            ai_result = _extract_json(response)
        except Exception:
            ai_result = {
                "score": 50,
                "tier": "warm",
                "reasoning": ["Lead profile analyzed", "Standard qualification criteria applied", "Moderate fit for target ICP"],
                "next_action": "Schedule discovery call to understand needs",
                "red_flags": [],
            }

        leads_collection.update_one(
            {"_id": ObjectId(request.lead_id), "tenant_id": current_user.get("tenant_id")},
            {"$set": {
                "icp_score": ai_result["score"],
                "icp_tier": ai_result["tier"],
                "icp_reasoning": ai_result.get("reasoning", []),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )

        activities_collection.insert_one({
            "lead_id": request.lead_id,
            "tenant_id": current_user.get("tenant_id"),
            "user_id": current_user["email"],
            "activity_type": "score_updated",
            "subject": f"ICP Score: {ai_result['score']} ({ai_result['tier']})",
            "body": "AI-powered ICP scoring completed",
            "outcome": None,
            "duration_minutes": None,
            "metadata": ai_result,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        return ai_result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI scoring failed: {str(e)}")


@router.post("/email-generate")
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
            system_message="You are an expert email copywriter for B2B sales and marketing.",
        )
        chat.with_model(*CLAUDE_MODEL)

        prompt = f"""
        Write a {request.tone} email for this lead:

        {lead_info}

        Goal: {request.goal}
        Length: {request.length}

        Return JSON with keys: subject, body
        """

        response = await chat.send_message(UserMessage(text=prompt))
        try:
            email_result = _extract_json(response)
        except Exception:
            email_result = {
                "subject": "Let's connect",
                "body": f"Hi {lead.get('first_name')},\n\nI wanted to reach out regarding {request.goal}.\n\nBest regards",
            }
        return email_result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email generation failed: {str(e)}")


@router.post("/chat")
async def ai_chat(request: AIChatRequest, current_user: dict = Depends(get_current_user)):
    try:
        chat = LlmChat(
            api_key=os.getenv("EMERGENT_LLM_KEY"),
            session_id=f"chat_{current_user['email']}",
            system_message="You are a helpful AI assistant for a Lead Management System. Help users query and analyze their lead data.",
        )
        chat.with_model(*CLAUDE_MODEL)
        response = await chat.send_message(UserMessage(text=request.query))
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@router.post("/summarize")
async def summarize_lead(request: AISummaryRequest, current_user: dict = Depends(get_current_user)):
    try:
        lead = leads_collection.find_one({"_id": ObjectId(request.lead_id)})
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        activities = list(
            activities_collection.find({"lead_id": request.lead_id})
            .sort("created_at", DESCENDING)
            .limit(20)
        )
        activity_log = "\n".join([
            f"- {a.get('activity_type')}: {a.get('subject', 'N/A')} ({a.get('created_at', 'N/A')})"
            for a in activities
        ])

        chat = LlmChat(
            api_key=os.getenv("EMERGENT_LLM_KEY"),
            session_id=f"summary_{request.lead_id}",
            system_message="You are a senior sales analyst. Provide concise, actionable summaries.",
        )
        chat.with_model(*CLAUDE_MODEL)

        prompt = f"""Summarize this lead's journey and recommend the next best action:

Lead: {lead.get('first_name')} {lead.get('last_name')}
Company: {lead.get('company_name', 'N/A')}
Status: {lead.get('status')}
ICP Score: {lead.get('icp_score')} ({lead.get('icp_tier')})

Activity History:
{activity_log if activity_log else 'No activities logged yet.'}

Give a 3-4 sentence summary and a clear next step recommendation."""

        response = await chat.send_message(UserMessage(text=prompt))
        return {"summary": response}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summarization failed: {str(e)}")
