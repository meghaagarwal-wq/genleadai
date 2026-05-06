"""Campaigns CRUD routes."""
from datetime import datetime, timezone
from typing import Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pymongo import DESCENDING

from deps import (
    campaigns_collection,
    leads_collection,
    get_current_user,
    serialize_doc,
)

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


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


@router.post("")
async def create_campaign(campaign: CampaignCreate, current_user: dict = Depends(get_current_user)):
    campaign_doc = campaign.dict()
    campaign_doc["created_at"] = datetime.now(timezone.utc).isoformat()
    campaign_doc["created_by"] = current_user["email"]
    campaigns_collection.insert_one(campaign_doc)
    return serialize_doc(campaign_doc)


@router.get("")
async def get_campaigns(current_user: dict = Depends(get_current_user)):
    campaigns = list(campaigns_collection.find(
        {},
        {"_id": 1, "name": 1, "description": 1, "status": 1, "channel": 1, "campaign_type": 1,
         "created_at": 1, "updated_at": 1, "created_by": 1, "tags": 1, "metadata": 1}
    ).sort("created_at", DESCENDING).limit(100))

    if not campaigns:
        return {"campaigns": []}

    campaign_ids = [str(c["_id"]) for c in campaigns]
    qualified_statuses = ["qualified", "proposal_sent", "negotiation", "won"]
    pipeline = [
        {"$match": {"campaign_id": {"$in": campaign_ids}}},
        {"$group": {
            "_id": "$campaign_id",
            "total_leads": {"$sum": 1},
            "qualified_leads": {"$sum": {"$cond": [{"$in": ["$status", qualified_statuses]}, 1, 0]}},
        }},
    ]
    counts_by_id = {row["_id"]: row for row in leads_collection.aggregate(pipeline)}

    for campaign in campaigns:
        cid = str(campaign["_id"])
        bucket = counts_by_id.get(cid, {})
        campaign["total_leads"] = bucket.get("total_leads", 0)
        campaign["qualified_leads"] = bucket.get("qualified_leads", 0)

    return {"campaigns": [serialize_doc(c) for c in campaigns]}


@router.get("/{campaign_id}")
async def get_campaign(campaign_id: str, current_user: dict = Depends(get_current_user)):
    try:
        campaign = campaigns_collection.find_one({"_id": ObjectId(campaign_id)})
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        campaign_id_str = str(campaign["_id"])
        campaign["leads"] = leads_collection.count_documents({"campaign_id": campaign_id_str})
        return serialize_doc(campaign)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid campaign ID")
