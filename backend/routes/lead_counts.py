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

iter146 — Pietential / multi-tenant fix: also reads from `pt_leads`
collection so Pietential workspaces (which use `pt_leads` + `stage`/`score`
fields instead of legacy `leads` + `status`/`icp_tier`) show real counts
on the sidebar strip + Command Center.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends

from deps import leads_collection, get_current_user, db

router = APIRouter()


# Display buckets — collapse the long backend status list into the four
# founder-friendly buckets the sidebar strip shows.
# Legacy `leads.status` mapping.
LEGACY_STAGE_BUCKETS = {
    "qualified":  {"qualified", "proposal_sent", "negotiation"},
    "nurturing":  {"contacted", "nurture"},
    "new":        {"new"},
    "cold":       {"lost", "unqualified"},
}

# pt_leads.stage mapping (set by routes/pietential.classify_stage).
PT_STAGE_BUCKETS = {
    "qualified":  {"hot", "engaged", "session_pilot", "replied"},
    "nurturing":  {"warm", "john_owns"},
    "new":        set(),  # pt_leads don't have a "new" state — they're scored on insert.
    "cold":       {"cold", "dnc"},
}


pt_leads_col = db["pt_leads"]


@router.get("/api/leads/counts")
async def lead_counts(current_user: dict = Depends(get_current_user)):
    tenant_id = current_user.get("tenant_id")
    base_q = {"tenant_id": tenant_id} if tenant_id else {}

    # ── Legacy leads (status field) ───────────────────────────────────
    legacy_pipeline = [
        {"$match": base_q},
        {"$group": {"_id": "$status", "n": {"$sum": 1}}},
    ]
    legacy_raw = {row["_id"] or "new": row["n"] for row in leads_collection.aggregate(legacy_pipeline)}

    # ── pt_leads (stage field) ────────────────────────────────────────
    pt_pipeline = [
        {"$match": base_q},
        {"$group": {"_id": "$stage", "n": {"$sum": 1}}},
    ]
    pt_raw = {row["_id"] or "cold": row["n"] for row in pt_leads_col.aggregate(pt_pipeline)}

    total = sum(legacy_raw.values()) + sum(pt_raw.values())

    # Collapse both into the four buckets.
    by_stage = {bucket: 0 for bucket in LEGACY_STAGE_BUCKETS}
    for status, n in legacy_raw.items():
        for bucket, members in LEGACY_STAGE_BUCKETS.items():
            if status in members:
                by_stage[bucket] += n
                break
    for stage, n in pt_raw.items():
        for bucket, members in PT_STAGE_BUCKETS.items():
            if stage in members:
                by_stage[bucket] += n
                break

    # ── Pipeline Snapshot ─────────────────────────────────────────────
    now = datetime.now(timezone.utc)
    week_ago = (now - timedelta(days=7)).isoformat()
    three_days_ago = (now - timedelta(days=3)).isoformat()

    calls_booked_week = leads_collection.count_documents({
        **base_q,
        "$or": [
            {"aria_state": "MEETING_BOOKED", "updated_at": {"$gte": week_ago}},
            {"call_booked_at": {"$gte": week_ago}},
        ],
    }) + pt_leads_col.count_documents({
        **base_q,
        "stage": "session_pilot",
        "updated_at": {"$gte": week_ago},
    })

    needs_attention = leads_collection.count_documents({
        **base_q,
        "icp_tier": {"$in": ["hot", "warm"]},
        "status": {"$in": ["new", "contacted", "qualified"]},
        "$or": [
            {"last_contacted_at": {"$lt": three_days_ago}},
            {"last_contacted_at": None},
            {"last_contacted_at": {"$exists": False}},
        ],
    }) + pt_leads_col.count_documents({
        **base_q,
        "stage": {"$in": ["hot", "engaged", "replied"]},
        "$or": [
            {"last_activity_at": {"$lt": three_days_ago}},
            {"last_activity_at": None},
            {"last_activity_at": {"$exists": False}},
        ],
    })

    return {
        "total": total,
        "by_stage": by_stage,
        "by_status_raw": {**legacy_raw, **{f"pt:{k}": v for k, v in pt_raw.items()}},
        "pipeline_snapshot": {
            "total": total,
            "qualified": by_stage["qualified"],
            "nurturing": by_stage["nurturing"],
            "needs_attention": needs_attention,
            "calls_booked_week": calls_booked_week,
        },
    }
