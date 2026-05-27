"""Admin Dashboard backend (PART D of ARIA Master Build v3.0).

Master-admin-only endpoints for platform-wide visibility:
- Overview: workspace counts, lead volume, API cost estimate
- Workspaces: table with impersonation
- Usage & Billing: per-workspace API breakdown
- System Health: background job + integration error logs

All endpoints gated by `role == "master_admin"`.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import db, get_current_user

router = APIRouter(prefix="/api/admin/v3", tags=["admin-v3"])

tenants_col = db["tenants"]
leads_col = db["leads"]
pt_leads_col = db["pt_leads"]
conversations_col = db["conversations"]
insights_col = db["pt_insights"]
users_col = db["users"]
audit_col = db["audit_log"]
api_usage_col = db["api_usage_log"]


def _require_master_admin(user: dict = Depends(get_current_user)) -> dict:
    role = (user or {}).get("role")
    if role != "master_admin":
        raise HTTPException(403, "master_admin role required")
    return user


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _start_of_day() -> datetime:
    n = _now()
    return n.replace(hour=0, minute=0, second=0, microsecond=0)


# ─── D.2 Overview ────────────────────────────────────────────────────────
@router.get("/overview")
async def overview(_: dict = Depends(_require_master_admin)):
    tenants = list(tenants_col.find({}, {"_id": 0, "id": 1, "name": 1, "settings": 1, "is_active": 1}))
    active = [t for t in tenants if t.get("is_active", True)]

    today_iso = _start_of_day().isoformat()

    # Lead volume today across all leads collections
    leads_today = (
        leads_col.count_documents({"created_at": {"$gte": today_iso}})
        + pt_leads_col.count_documents({"created_at": {"$gte": today_iso}})
    )

    # Active conversations (last activity within 24h)
    one_day_ago = (_now() - timedelta(days=1)).isoformat()
    active_convos = conversations_col.count_documents({"last_activity_at": {"$gte": one_day_ago}})

    # Insights generated today
    insights_today = insights_col.count_documents({"created_at": {"$gte": today_iso}})

    # API usage today (cost estimate from api_usage_log if collection exists)
    api_cost_today = 0.0
    try:
        agg = list(api_usage_col.aggregate([
            {"$match": {"timestamp": {"$gte": today_iso}}},
            {"$group": {"_id": None, "cost": {"$sum": "$estimated_cost_usd"}}},
        ]))
        api_cost_today = round((agg[0].get("cost") if agg else 0.0) or 0.0, 4)
    except Exception:
        pass

    # Error alerts — last 24h
    errors_24h = audit_col.count_documents({
        "timestamp": {"$gte": one_day_ago},
        "action": {"$regex": "error|fail", "$options": "i"},
    })

    return {
        "workspaces": {
            "total": len(tenants),
            "active": len(active),
            "inactive": len(tenants) - len(active),
        },
        "tenants_total": len(tenants),  # flat model: 1 tenant per workspace today
        "leads_today": leads_today,
        "active_conversations": active_convos,
        "insights_today": insights_today,
        "api_cost_today_usd": api_cost_today,
        "errors_24h": errors_24h,
    }


# ─── D.3 Workspaces ──────────────────────────────────────────────────────
@router.get("/workspaces")
async def list_workspaces(_: dict = Depends(_require_master_admin)):
    rows = []
    for t in tenants_col.find({}, {"_id": 0}):
        settings = t.get("settings") or {}
        mode = settings.get("workspace_type") or "hybrid"
        tid = t["id"]
        lead_count = leads_col.count_documents({"tenant_id": tid}) + pt_leads_col.count_documents({"tenant_id": tid})
        owner_email = (settings.get("business_profile") or {}).get("owner_email") or t.get("owner_email")
        rows.append({
            "id": tid,
            "name": t.get("name") or tid,
            "mode": mode,
            "owner_email": owner_email,
            "tenant_count": 1,
            "lead_volume": lead_count,
            "created_at": t.get("created_at"),
            "is_active": t.get("is_active", True),
            "has_aria_training": bool((settings.get("aria_training_profile") or {}).get("assembled_prompt")),
        })
    return {"workspaces": rows, "count": len(rows)}


class WorkspaceActionPayload(BaseModel):
    action: str  # "suspend" | "activate" | "delete"


@router.post("/workspaces/{workspace_id}/action")
async def workspace_action(
    workspace_id: str,
    payload: WorkspaceActionPayload,
    user: dict = Depends(_require_master_admin),
):
    target = tenants_col.find_one({"id": workspace_id}, {"_id": 0})
    if not target:
        raise HTTPException(404, "workspace_not_found")
    if payload.action == "suspend":
        tenants_col.update_one({"id": workspace_id}, {"$set": {"is_active": False, "suspended_at": _now().isoformat()}})
    elif payload.action == "activate":
        tenants_col.update_one({"id": workspace_id}, {"$set": {"is_active": True}, "$unset": {"suspended_at": ""}})
    elif payload.action == "delete":
        # Soft delete only — never hard-delete from admin panel
        tenants_col.update_one({"id": workspace_id}, {"$set": {"is_active": False, "deleted_at": _now().isoformat()}})
    else:
        raise HTTPException(400, "invalid action")
    audit_col.insert_one({
        "tenant_id": workspace_id,
        "actor_id": user.get("id") or user.get("email"),
        "action": f"admin_workspace_{payload.action}",
        "timestamp": _now().isoformat(),
    })
    return {"ok": True, "workspace_id": workspace_id, "action": payload.action}


@router.post("/workspaces/{workspace_id}/impersonate")
async def impersonate(
    workspace_id: str,
    user: dict = Depends(_require_master_admin),
):
    """Return an impersonation token + banner config.

    The frontend sets X-Tenant-Id to this workspace_id and shows a
    persistent banner. We use the master admin's own JWT — no token
    minting — but log the impersonation for audit.
    """
    target = tenants_col.find_one({"id": workspace_id}, {"_id": 0})
    if not target:
        raise HTTPException(404, "workspace_not_found")
    audit_col.insert_one({
        "tenant_id": workspace_id,
        "actor_id": user.get("id") or user.get("email"),
        "action": "admin_impersonate_start",
        "timestamp": _now().isoformat(),
    })
    return {
        "ok": True,
        "workspace_id": workspace_id,
        "workspace_name": target.get("name"),
        "mode": (target.get("settings") or {}).get("workspace_type") or "hybrid",
        "impersonation_banner": True,
    }


# ─── D.4 Usage & Billing ────────────────────────────────────────────────
@router.get("/usage")
async def usage_breakdown(_: dict = Depends(_require_master_admin)):
    """Per-workspace API call breakdown for the current month."""
    month_start = _now().replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    rows = []
    for t in tenants_col.find({}, {"_id": 0, "id": 1, "name": 1, "settings": 1}):
        tid = t["id"]
        plan = (t.get("settings") or {}).get("plan") or "trial"
        # Aggregate API usage by provider for this tenant this month
        breakdown: Dict[str, Any] = {}
        try:
            for r in api_usage_col.aggregate([
                {"$match": {"tenant_id": tid, "timestamp": {"$gte": month_start}}},
                {"$group": {
                    "_id": "$provider",
                    "calls": {"$sum": 1},
                    "cost": {"$sum": "$estimated_cost_usd"},
                }},
            ]):
                breakdown[r["_id"] or "unknown"] = {
                    "calls": r.get("calls", 0),
                    "cost_usd": round(r.get("cost") or 0.0, 4),
                }
        except Exception:
            pass
        total_cost = round(sum(v["cost_usd"] for v in breakdown.values()), 4)
        rows.append({
            "workspace_id": tid,
            "workspace_name": t.get("name") or tid,
            "plan": plan,
            "providers": breakdown,
            "total_cost_usd_month": total_cost,
        })
    return {"month_start": month_start, "rows": rows}


# ─── D.5 System Health ──────────────────────────────────────────────────
@router.get("/system-health")
async def system_health(_: dict = Depends(_require_master_admin)):
    """Last-run + error status per background job, per workspace."""
    one_day_ago = (_now() - timedelta(days=1)).isoformat()
    # Last audit entries grouped by action
    job_status: Dict[str, Any] = {}
    try:
        for r in audit_col.aggregate([
            {"$match": {"timestamp": {"$gte": one_day_ago}}},
            {"$group": {
                "_id": "$action",
                "count": {"$sum": 1},
                "latest": {"$max": "$timestamp"},
            }},
            {"$sort": {"latest": -1}},
            {"$limit": 30},
        ]):
            job_status[r["_id"] or "unknown"] = {
                "count_24h": r.get("count", 0),
                "latest_at": r.get("latest"),
            }
    except Exception:
        pass

    # Integration error log
    integration_errors = list(audit_col.find(
        {
            "timestamp": {"$gte": one_day_ago},
            "action": {"$regex": "integration.*error|enrichment.*fail|saleshandy.*fail|lemlist.*fail", "$options": "i"},
        },
        {"_id": 0, "tenant_id": 1, "action": 1, "timestamp": 1, "detail": 1},
    ).sort([("timestamp", -1)]).limit(30))

    return {
        "job_status": job_status,
        "integration_errors": integration_errors,
        "checked_at": _now().isoformat(),
    }
