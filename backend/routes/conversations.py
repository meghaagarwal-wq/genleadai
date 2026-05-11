"""Conversations endpoint — thread list for /conversations page."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, Query

from deps import db
from routes.tenants import get_active_tenant

router = APIRouter(prefix="/api/conversations", tags=["conversations"])

leads_col = db["leads"]
conversations_col = db["aria_conversations"]


@router.get("/threads")
async def threads(
    sentiment: Optional[str] = Query(None),
    aria_active: Optional[bool] = Query(None),
    assigned_to: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = 100,
    tenant: dict = Depends(get_active_tenant),
):
    """List leads who have an active conversation, sorted by urgency.

    Urgent / negative sentiment leads float to the top.
    """
    tenant_id = tenant["id"]
    base = {"tenant_id": tenant_id}
    if sentiment:
        base["latest_sentiment"] = sentiment
    if aria_active is not None:
        base["aria_active"] = aria_active
    if assigned_to:
        base["assigned_to"] = assigned_to
    if search:
        base["$or"] = [
            {"first_name": {"$regex": search, "$options": "i"}},
            {"last_name": {"$regex": search, "$options": "i"}},
            {"phone": {"$regex": search}},
            {"email": {"$regex": search, "$options": "i"}},
        ]

    rows = list(leads_col.find(base, {"_id": 0}).sort("updated_at", -1).limit(int(limit)))

    # Enrich with last message preview + aria_confidence
    out = []
    for r in rows:
        last_msg = conversations_col.find_one(
            {"tenant_id": tenant_id, "lead_id": r["id"]},
            {"_id": 0, "message": 1, "role": 1, "created_at": 1, "confidence": 1},
            sort=[("created_at", -1)],
        ) or {}
        out.append({
            "lead_id": r["id"],
            "first_name": r.get("first_name"),
            "last_name": r.get("last_name"),
            "phone": r.get("phone"),
            "email": r.get("email"),
            "company_name": r.get("company_name"),
            "status": r.get("status"),
            "icp_score": r.get("icp_score"),
            "icp_tier": r.get("icp_tier"),
            "aria_active": r.get("aria_active", True),
            "assigned_to": r.get("assigned_to"),
            "latest_sentiment": r.get("latest_sentiment"),
            "last_message": (last_msg.get("message") or "")[:140],
            "last_message_role": last_msg.get("role"),
            "last_message_at": last_msg.get("created_at") or r.get("updated_at"),
            "aria_confidence": last_msg.get("confidence") or r.get("aria_confidence"),
            "updated_at": r.get("updated_at"),
        })

    # Float urgent / negative to the top
    def _priority(t: dict) -> int:
        s = (t.get("latest_sentiment") or "").lower()
        if s == "urgent":
            return 0
        if s == "negative":
            return 1
        return 2
    out.sort(key=_priority)
    return {"threads": out, "count": len(out)}
