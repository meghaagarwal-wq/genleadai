"""Analytics dashboard + email send + Resend wrapper."""
import asyncio
import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
import resend

from deps import leads_collection, get_current_user

resend.api_key = os.getenv("RESEND_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "onboarding@resend.dev")

router = APIRouter(tags=["analytics-misc"])


@router.get("/api/analytics/dashboard")
async def get_dashboard_analytics(current_user: dict = Depends(get_current_user)):
    total_leads = leads_collection.count_documents({})

    status_counts = {}
    for s in ["new", "contacted", "qualified", "proposal_sent", "negotiation", "won", "lost"]:
        status_counts[s] = leads_collection.count_documents({"status": s})

    channel_counts = {}
    for ch in ["whatsapp", "email", "linkedin", "instagram", "facebook", "website_form", "cold_call", "referral"]:
        channel_counts[ch] = leads_collection.count_documents({"source_channel": ch})

    b2b_count = leads_collection.count_documents({"lead_type": "B2B"})
    b2c_count = leads_collection.count_documents({"lead_type": "B2C"})

    hot_count = leads_collection.count_documents({"icp_tier": "hot"})
    warm_count = leads_collection.count_documents({"icp_tier": "warm"})
    cold_count = leads_collection.count_documents({"icp_tier": "cold"})

    return {
        "total_leads": total_leads,
        "status_distribution": status_counts,
        "channel_distribution": channel_counts,
        "lead_type_distribution": {"B2B": b2b_count, "B2C": b2c_count},
        "icp_distribution": {"hot": hot_count, "warm": warm_count, "cold": cold_count},
    }


class EmailSendRequest(BaseModel):
    recipient_email: EmailStr
    subject: str
    html_content: str


@router.post("/api/email/send")
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
