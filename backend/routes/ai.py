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
        lead = leads_collection.find_one({"_id": ObjectId(request.lead_id)})
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

        chat = LlmChat(
            api_key=os.getenv("EMERGENT_LLM_KEY"),
            session_id=f"icp_score_{request.lead_id}",
            system_message="You are an expert B2B/B2C sales qualification assistant. Score leads against ideal customer profiles and return structured data.",
        )
        chat.with_model(*CLAUDE_MODEL)

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
            {"_id": ObjectId(request.lead_id)},
            {"$set": {
                "icp_score": ai_result["score"],
                "icp_tier": ai_result["tier"],
                "icp_reasoning": ai_result.get("reasoning", []),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )

        activities_collection.insert_one({
            "lead_id": request.lead_id,
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
