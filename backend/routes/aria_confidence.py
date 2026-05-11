"""Aria Confidence Score — composite engagement/intent metric per lead.

Combines several signals into a single 0-100 score that surfaces "which leads
are likeliest to convert right now" — so sales reps glance at the
Conversations / Leads list and instantly know where to spend their attention.

Recipe (60/25/15 weighting, capped at 100):
  60% — ICP score (Claude's fit rating, already computed elsewhere)
  25% — Touchpoint engagement (paused on reply = +25, recently sent = +15,
        all-cancelled = -25, journey-empty = 0)
  15% — Recency (activity in last 7d = +15, last 14d = +5)
   +  — Stage bonus (qualified/proposal/negotiation = +5)
   -  — Stale penalty (no activity > 14d = -15)

Returned color:
  >=70  green   "hot"
  50-69 yellow  "warm"
  <50   red     "cold"
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import db, get_current_user
from routes.tenants import get_active_tenant

router = APIRouter(prefix="/api/aria", tags=["aria-confidence"])

leads_col = db["leads"]
log_col = db["lead_touchpoint_log"]
activities_col = db["activities"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        s = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


# Stage bonus map (lower-cased substrings → bonus points)
STAGE_BONUSES = {
    "qualified": 5,
    "proposal": 7,
    "negotiation": 10,
    "demo": 5,
    "scheduled": 5,
}
NEGATIVE_STAGES = ("closed lost", "lost", "disqualified")


def _stage_bonus(stage: Optional[str]) -> int:
    s = (stage or "").lower()
    if any(x in s for x in NEGATIVE_STAGES):
        return -20
    for key, val in STAGE_BONUSES.items():
        if key in s:
            return val
    return 0


def _compute_for_lead(tenant_id: str, lead: dict) -> dict:
    factors = []
    score = 0.0

    # 1. ICP score — 60% weight
    icp = float(lead.get("icp_score") or 0)
    icp_component = min(60, icp * 0.6)
    score += icp_component
    factors.append({"label": "ICP fit", "delta": round(icp_component, 1), "raw": icp})

    # 2. Touchpoint engagement — 25%
    lead_id = lead.get("id") or str(lead.get("_id"))
    tps = list(log_col.find(
        {"tenant_id": tenant_id, "lead_id": lead_id},
        {"_id": 0, "status": 1, "fired_at": 1},
    ))
    tp_delta = 0
    if tps:
        statuses = [t.get("status") for t in tps]
        paused_count = statuses.count("paused")
        sent_count = statuses.count("sent")
        cancelled_count = statuses.count("cancelled")
        total = len(tps)
        if paused_count > 0:
            # paused = lead is engaging — strongest signal
            tp_delta = 25
            factors.append({"label": "Lead replied (touchpoints paused)", "delta": tp_delta})
        elif cancelled_count == total:
            tp_delta = -15
            factors.append({"label": "Journey cancelled", "delta": tp_delta})
        elif sent_count >= 3:
            tp_delta = 15
            factors.append({"label": f"{sent_count} touchpoints delivered", "delta": tp_delta})
        elif sent_count >= 1:
            tp_delta = 8
            factors.append({"label": f"{sent_count} touchpoint(s) sent", "delta": tp_delta})
    score += tp_delta

    # 3. Recency — 15%
    last_activity = activities_col.find_one(
        {"lead_id": lead_id, "tenant_id": tenant_id},
        {"_id": 0, "created_at": 1},
        sort=[("created_at", -1)],
    )
    recency_delta = 0
    if last_activity:
        dt = _parse_dt(last_activity.get("created_at"))
        if dt:
            days = (_now() - dt).days
            if days <= 7:
                recency_delta = 15
                factors.append({"label": "Active in last 7 days", "delta": recency_delta})
            elif days <= 14:
                recency_delta = 5
                factors.append({"label": "Active in last 14 days", "delta": recency_delta})
            elif days > 30:
                recency_delta = -15
                factors.append({"label": f"Stale ({days}d since last activity)", "delta": recency_delta})
    score += recency_delta

    # 4. Stage bonus / penalty
    stage_delta = _stage_bonus(lead.get("status"))
    if stage_delta:
        score += stage_delta
        factors.append({"label": f"Stage: {lead.get('status') or 'New'}", "delta": stage_delta})

    # Clamp
    score = max(0, min(100, round(score)))
    color = "green" if score >= 70 else "yellow" if score >= 50 else "red"
    label = "hot" if score >= 70 else "warm" if score >= 50 else "cold"

    return {
        "lead_id": lead_id,
        "score": int(score),
        "color": color,
        "label": label,
        "factors": factors[:4],  # top 4 factors only for UI
    }


# ─── Endpoints ───────────────────────────────────────────────────────────────
@router.get("/confidence/{lead_id}")
async def get_confidence(lead_id: str, tenant: dict = Depends(get_active_tenant)):
    lead = leads_col.find_one(
        {"$or": [{"id": lead_id}, {"_id": lead_id}], "tenant_id": tenant["id"]},
        {"_id": 0},
    )
    if not lead:
        # Try ObjectId fallback (legacy leads)
        try:
            from bson import ObjectId
            lead = leads_col.find_one({"_id": ObjectId(lead_id), "tenant_id": tenant["id"]}, {"_id": 0})
        except Exception:
            lead = None
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return _compute_for_lead(tenant["id"], lead)


class BatchPayload(BaseModel):
    lead_ids: List[str]


@router.post("/confidence/batch")
async def batch_confidence(payload: BatchPayload, tenant: dict = Depends(get_active_tenant)):
    """Batch-compute confidence for a list of lead IDs.

    Used by the Leads list and Conversations list to render the dial inline
    without N+1 queries. Capped at 200 IDs per call.
    """
    ids = (payload.lead_ids or [])[:200]
    if not ids:
        return {"scores": {}}
    leads = list(leads_col.find(
        {"$or": [{"id": {"$in": ids}}], "tenant_id": tenant["id"]},
        {"_id": 0},
    ))
    out = {}
    for lead in leads:
        result = _compute_for_lead(tenant["id"], lead)
        out[result["lead_id"]] = result
    return {"scores": out}
