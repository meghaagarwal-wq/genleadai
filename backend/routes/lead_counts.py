"""ARIA — Lead counts + pipeline snapshot for sidebar & Command Center.

Lightweight tenant-scoped count aggregator polled every 30s by the
sidebar lead-count strip and Command Center "Pipeline Snapshot" row.

Endpoint
────────
GET /api/leads/counts
    Returns:
      {
        total: int,
        by_stage: {qualified, nurturing, new, cold, contacted, ...},
        pipeline_snapshot: {
            total, qualified, nurturing, needs_attention, calls_booked_week
        }
      }
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends

from deps import leads_collection, get_current_user

router = APIRouter()


# Display buckets — collapse the long backend status list into the four
# founder-friendly buckets the sidebar strip shows.
STAGE_BUCKETS = {
    "qualified":  {"qualified", "proposal_sent", "negotiation"},
    "nurturing":  {"contacted", "nurture"},
    "new":        {"new"},
    "cold":       {"lost", "unqualified"},
}


@router.get("/api/leads/counts")
async def lead_counts(current_user: dict = Depends(get_current_user)):
    tenant_id = current_user.get("tenant_id")
    q = {"tenant_id": tenant_id} if tenant_id else {}

    # Single aggregation: group by status, then collapse into buckets.
    pipeline = [
        {"$match": q},
        {"$group": {"_id": "$status", "n": {"$sum": 1}}},
    ]
    raw = {row["_id"] or "new": row["n"] for row in leads_collection.aggregate(pipeline)}
    total = sum(raw.values())

    by_stage = {bucket: 0 for bucket in STAGE_BUCKETS}
    for status, n in raw.items():
        for bucket, members in STAGE_BUCKETS.items():
            if status in members:
                by_stage[bucket] += n
                break

    # Pipeline Snapshot: counts for Command Center chips.
    now = datetime.now(timezone.utc)
    week_ago = (now - timedelta(days=7)).isoformat()
    three_days_ago = (now - timedelta(days=3)).isoformat()

    calls_booked_week = leads_collection.count_documents({
        **q,
        "$or": [
            {"aria_state": "MEETING_BOOKED", "updated_at": {"$gte": week_ago}},
            {"call_booked_at": {"$gte": week_ago}},
        ],
    })
    needs_attention = leads_collection.count_documents({
        **q,
        "icp_tier": {"$in": ["hot", "warm"]},
        "status": {"$in": ["new", "contacted", "qualified"]},
        "$or": [
            {"last_contacted_at": {"$lt": three_days_ago}},
            {"last_contacted_at": None},
            {"last_contacted_at": {"$exists": False}},
        ],
    })

    return {
        "total": total,
        "by_stage": by_stage,
        "by_status_raw": raw,
        "pipeline_snapshot": {
            "total": total,
            "qualified": by_stage["qualified"],
            "nurturing": by_stage["nurturing"],
            "needs_attention": needs_attention,
            "calls_booked_week": calls_booked_week,
        },
    }
