"""Audit log — append-only record of meaningful tenant actions.

Other modules call `audit_write(tenant_id, user, action, resource_type, resource_id, metadata)`
to record an event. The Owner of a workspace can list the workspace's events via
GET /api/audit-log. Master admins can see across workspaces.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from deps import db, get_current_user
from routes.tenants import get_active_tenant

router = APIRouter(prefix="/api/audit-log", tags=["audit-log"])

col = db["audit_log"]

# Known action categories (free-form is allowed too, this is just a hint list)
KNOWN_ACTIONS = {
    "lead.created", "lead.updated", "lead.deleted", "lead.data_purged",
    "conversation.takeover", "aria.paused", "aria.resumed",
    "member.invited", "member.removed", "member.role_changed",
    "plan.changed", "payment.recorded", "settings.updated",
    "api_key.rotated", "workspace.deleted",
    "crm.connected", "crm.disconnected", "crm.sync_triggered",
    "crm.sync_failed", "crm.field_mapping_updated",
    "touchpoint_map.updated", "touchpoint_map.imported_from_document",
    "trial.extended", "trial.expired",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _client_ip(req: Optional[Request]) -> Optional[str]:
    if not req:
        return None
    fwd = req.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return req.client.host if req.client else None


def audit_write(
    tenant_id: Optional[str],
    user: Optional[dict],
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None,
) -> str:
    """Insert a single audit log row. Returns the generated id. Best-effort —
    never raises into the caller (logs swallowed)."""
    try:
        doc = {
            "id": f"aud_{uuid.uuid4().hex[:12]}",
            "tenant_id": tenant_id,
            "user_id": (user or {}).get("email") or (user or {}).get("id"),
            "user_name": (user or {}).get("full_name"),
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "metadata": metadata or {},
            "ip_address": _client_ip(request),
            "user_agent": request.headers.get("user-agent") if request else None,
            "created_at": _now(),
        }
        col.insert_one(doc.copy())
        return doc["id"]
    except Exception:
        return ""


class AuditPatch(BaseModel):
    pass  # reserved for future fields


def _can_read_all(user: dict) -> bool:
    return (user.get("role") or "").lower() == "admin"


@router.get("")
async def list_audit(
    tenant: dict = Depends(get_active_tenant),
    user: dict = Depends(get_current_user),
    action: Optional[str] = None,
    user_email: Optional[str] = None,
    limit: int = 200,
    skip: int = 0,
):
    """Owners see their workspace's audit log. Master admins can see all by passing tenant=*"""
    if tenant.get("_member_role") not in ("owner", "admin") and not _can_read_all(user):
        raise HTTPException(status_code=403, detail="Owner/Admin only")
    q: Dict[str, Any] = {}
    # Default: scope to current tenant. Master admin can request all by setting tenant_id="*"
    q["tenant_id"] = tenant["id"]
    if action:
        q["action"] = action
    if user_email:
        q["user_id"] = user_email
    total = col.count_documents(q)
    rows = list(col.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(min(limit, 500)))
    return {"entries": rows, "total": total, "known_actions": sorted(KNOWN_ACTIONS)}


@router.get("/export.csv")
async def export_audit_csv(
    tenant: dict = Depends(get_active_tenant),
    user: dict = Depends(get_current_user),
):
    if tenant.get("_member_role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")
    rows = list(col.find({"tenant_id": tenant["id"]}, {"_id": 0}).sort("created_at", -1).limit(5000))
    headers = ["created_at", "user_id", "action", "resource_type", "resource_id", "ip_address", "metadata"]
    out = [",".join(headers)]
    for r in rows:
        meta = str(r.get("metadata") or {}).replace(",", ";").replace("\n", " ")
        line = ",".join([
            r.get("created_at", ""),
            (r.get("user_id") or "").replace(",", " "),
            r.get("action", ""),
            r.get("resource_type") or "",
            r.get("resource_id") or "",
            r.get("ip_address") or "",
            f"\"{meta}\"",
        ])
        out.append(line)
    return Response(content="\n".join(out), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=audit_log.csv"})


# ─── Master Admin Workspaces (cross-tenant) ──────────────────────────────────
admin_router = APIRouter(prefix="/api/admin/workspaces", tags=["admin-workspaces"])

tenants_col = db["tenants"]
memberships_col = db["tenant_memberships"]
leads_col = db["leads"]
subs_col = db["subscriptions"]


def _require_master_admin(user: dict):
    if (user.get("role") or "").lower() != "admin":
        raise HTTPException(status_code=403, detail="Master admin only")


def _ws_summary(t: dict) -> dict:
    tid = t.get("id")
    sub = subs_col.find_one({"tenant_id": tid}, {"_id": 0}) or {}
    seats = memberships_col.count_documents({"tenant_id": tid})
    lead_total = leads_col.count_documents({"tenant_id": tid})
    convo_total = db["conversations"].count_documents({"tenant_id": tid})
    last_lead = leads_col.find_one(
        {"tenant_id": tid}, {"_id": 0, "updated_at": 1, "created_at": 1},
        sort=[("updated_at", -1)],
    )
    last_active = (last_lead or {}).get("updated_at") or (last_lead or {}).get("created_at")
    return {
        "id": tid,
        "name": t.get("name") or t.get("workspace_name") or "—",
        "owner_email": t.get("owner_email"),
        "plan": sub.get("plan") or t.get("plan") or "trial",
        "status": sub.get("status") or "active",
        "trial_ends_at": t.get("trial_ends_at"),
        "is_launch_ready": bool(t.get("is_launch_ready")),
        "seats": seats,
        "leads": lead_total,
        "conversations": convo_total,
        "last_active_at": last_active,
        "created_at": t.get("created_at"),
        "health_score": t.get("health_score"),
    }


@admin_router.get("")
async def list_workspaces(
    search: Optional[str] = None,
    plan: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    _require_master_admin(current_user)
    q: Dict[str, Any] = {}
    if search:
        q["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"owner_email": {"$regex": search, "$options": "i"}},
        ]
    tenants = list(tenants_col.find(q, {"_id": 0}).sort("created_at", -1).limit(500))
    rows = [_ws_summary(t) for t in tenants]
    if plan:
        rows = [r for r in rows if r["plan"] == plan]
    return {"workspaces": rows, "total": len(rows)}


@admin_router.get("/{tenant_id}")
async def workspace_detail(tenant_id: str, current_user: dict = Depends(get_current_user)):
    _require_master_admin(current_user)
    t = tenants_col.find_one({"id": tenant_id}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Workspace not found")
    members = list(memberships_col.find({"tenant_id": tenant_id}, {"_id": 0}))
    obc = db["onboarding_config"].find_one({"tenant_id": tenant_id}, {"_id": 0}) or {}
    return {
        "summary": _ws_summary(t),
        "tenant": t,
        "members": members,
        "onboarding": obc,
    }


class TrialExtendPayload(BaseModel):
    days: int = 7


@admin_router.post("/{tenant_id}/extend-trial")
async def extend_trial(tenant_id: str, payload: TrialExtendPayload, current_user: dict = Depends(get_current_user), request: Request = None):
    _require_master_admin(current_user)
    t = tenants_col.find_one({"id": tenant_id}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Workspace not found")
    from datetime import timedelta
    end_str = t.get("trial_ends_at")
    try:
        end = datetime.fromisoformat((end_str or _now()).replace("Z", "+00:00"))
    except Exception:
        end = datetime.now(timezone.utc)
    end = max(end, datetime.now(timezone.utc))
    new_end = end + timedelta(days=payload.days)
    tenants_col.update_one(
        {"id": tenant_id},
        {"$set": {"trial_ends_at": new_end.isoformat(), "updated_at": _now()}},
    )
    audit_write(tenant_id, current_user, "trial.extended", "tenant", tenant_id,
                {"days": payload.days, "new_trial_ends_at": new_end.isoformat()}, request=request)
    return {"status": "ok", "trial_ends_at": new_end.isoformat()}


# ─── Pre-Launch Checklist ────────────────────────────────────────────────────
DEFAULT_CHECKLIST_ITEMS = [
    {"key": "whatsapp_api_key_set", "label": "WhatsApp 360dialog API key configured", "group": "WhatsApp integration"},
    {"key": "whatsapp_test_message_sent", "label": "Test inbound + outbound WhatsApp message successful", "group": "WhatsApp integration"},
    {"key": "webhook_url_active", "label": "Webhook URL responding to inbound", "group": "WhatsApp integration"},
    {"key": "compliance_checkbox", "label": "Opt-in compliance checkbox accepted", "group": "WhatsApp integration"},
    {"key": "aria_persona_configured", "label": "Aria persona + tone set", "group": "Aria conversation engine"},
    {"key": "aria_test_response_generated", "label": "Aria generated a test response successfully", "group": "Aria conversation engine"},
    {"key": "touchpoint_map_saved", "label": "Touchpoint map saved (≥3 touchpoints)", "group": "Touchpoint engine"},
    {"key": "touchpoint_engine_fired_once", "label": "At least 1 touchpoint successfully fired", "group": "Touchpoint engine"},
    {"key": "pipeline_stages_set", "label": "Pipeline stages configured", "group": "Dashboard & pipeline"},
    {"key": "first_lead_created", "label": "First lead created in pipeline", "group": "Dashboard & pipeline"},
    {"key": "team_invited", "label": "At least 1 team member invited", "group": "Dashboard & pipeline"},
    {"key": "claude_fallback_tested", "label": "Claude fallback message tested", "group": "Failover scenarios"},
    {"key": "dialog360_retry_tested", "label": "360dialog retry queue tested", "group": "Failover scenarios"},
]


@admin_router.get("/{tenant_id}/launch-checklist")
async def get_checklist(tenant_id: str, current_user: dict = Depends(get_current_user)):
    _require_master_admin(current_user)
    t = tenants_col.find_one({"id": tenant_id}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Workspace not found")
    saved = (t.get("launch_checklist") or {})
    return {
        "items": DEFAULT_CHECKLIST_ITEMS,
        "state": saved,
        "is_launch_ready": bool(t.get("is_launch_ready")),
    }


class ChecklistPatch(BaseModel):
    state: Dict[str, bool]


@admin_router.put("/{tenant_id}/launch-checklist")
async def update_checklist(tenant_id: str, payload: ChecklistPatch, current_user: dict = Depends(get_current_user), request: Request = None):
    _require_master_admin(current_user)
    valid_keys = {it["key"] for it in DEFAULT_CHECKLIST_ITEMS}
    state = {k: bool(v) for k, v in payload.state.items() if k in valid_keys}
    all_done = all(state.get(k) for k in valid_keys)
    tenants_col.update_one(
        {"id": tenant_id},
        {"$set": {"launch_checklist": state, "is_launch_ready": all_done, "updated_at": _now()}},
    )
    audit_write(tenant_id, current_user, "workspace.launch_checklist_updated", "tenant", tenant_id,
                {"completed": sum(1 for v in state.values() if v), "is_launch_ready": all_done}, request=request)
    return {"status": "ok", "is_launch_ready": all_done}


@admin_router.post("/{tenant_id}/mark-launch-ready")
async def mark_launch_ready(tenant_id: str, current_user: dict = Depends(get_current_user), request: Request = None):
    _require_master_admin(current_user)
    tenants_col.update_one(
        {"id": tenant_id},
        {"$set": {"is_launch_ready": True, "launch_ready_at": _now(), "updated_at": _now()}},
    )
    audit_write(tenant_id, current_user, "workspace.marked_launch_ready", "tenant", tenant_id, {}, request=request)
    return {"status": "ok"}


# ─── Platform Stats (master admin) ───────────────────────────────────────────
@admin_router.get("/platform/stats")
async def platform_stats(current_user: dict = Depends(get_current_user)):
    _require_master_admin(current_user)
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    day_ago = (now - timedelta(days=1)).isoformat()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    total_workspaces = tenants_col.count_documents({})
    paying = subs_col.count_documents({"plan": {"$in": ["diy", "dwy", "dfy"]}, "status": "active"})
    trials = subs_col.count_documents({"plan": "trial", "status": {"$in": ["active", "trial"]}})
    total_leads = leads_col.count_documents({})
    total_convos = db["conversations"].count_documents({})
    msgs_24h = db["lead_touchpoint_log"].count_documents({"status": "sent", "fired_at": {"$gte": day_ago}})
    failed_24h = db["lead_touchpoint_log"].count_documents({"status": "failed", "fired_at": {"$gte": day_ago}})
    claude_calls_today = db["api_usage_log"].count_documents({"created_at": {"$gte": today_start}})
    cost_today = 0.0
    for r in db["api_usage_log"].find({"created_at": {"$gte": today_start}}, {"_id": 0, "estimated_cost_usd": 1}):
        cost_today += float(r.get("estimated_cost_usd") or 0)
    return {
        "total_workspaces": total_workspaces,
        "active_paying_clients": paying,
        "trial_workspaces": trials,
        "total_leads": total_leads,
        "total_conversations": total_convos,
        "messages_sent_24h": msgs_24h,
        "failed_messages_24h": failed_24h,
        "claude_calls_today": claude_calls_today,
        "claude_cost_today_usd": round(cost_today, 4),
    }


# ─── Trials expiring panel ───────────────────────────────────────────────────
@admin_router.get("/trials/expiring")
async def trials_expiring(days: int = 3, current_user: dict = Depends(get_current_user)):
    _require_master_admin(current_user)
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    cutoff = (now + timedelta(days=days)).isoformat()
    subs = list(subs_col.find(
        {"plan": "trial", "current_period_end": {"$lte": cutoff, "$gte": now.isoformat()}},
        {"_id": 0},
    ).sort("current_period_end", 1))
    out = []
    for s in subs:
        t = tenants_col.find_one({"id": s["tenant_id"]}, {"_id": 0}) or {}
        out.append({
            "tenant_id": s["tenant_id"],
            "tenant_name": s.get("tenant_name") or t.get("name"),
            "owner_email": s.get("owner_email") or t.get("owner_email"),
            "trial_ends_at": s.get("current_period_end"),
            "onboarding_completed": bool(t.get("onboarding_completed")),
            "lead_count": leads_col.count_documents({"tenant_id": s["tenant_id"]}),
        })
    return {"trials": out}



# ─── Health Monitor — service pings (master admin) ───────────────────────────
@admin_router.get("/health/services")
async def health_services(current_user: dict = Depends(get_current_user)):
    """Returns live status pings for critical infrastructure services."""
    _require_master_admin(current_user)
    import os
    import time as _time
    services = []

    # MongoDB ping
    t0 = _time.time()
    try:
        db.command("ping")
        services.append({"name": "MongoDB", "status": "ok", "latency_ms": round((_time.time() - t0) * 1000, 1)})
    except Exception as e:
        services.append({"name": "MongoDB", "status": "down", "error": str(e)[:80]})

    # Claude / Emergent LLM
    services.append({
        "name": "Claude (Emergent LLM)",
        "status": "ok" if os.environ.get("EMERGENT_LLM_KEY") else "unconfigured",
        "latency_ms": None,
    })

    # Resend — uses the actual email_delivery_log to surface real send health.
    try:
        from email_delivery import email_health_summary
        eh = email_health_summary(limit=50)
        sender = eh.get("sender") or "unconfigured"
        by_status = eh.get("by_status") or {}
        sent_n = int(by_status.get("sent", 0))
        forwarded_n = int(by_status.get("test_mode_forwarded", 0))
        failed_n = int(by_status.get("failed", 0))
        # Health rules:
        #   no api key  → unconfigured
        #   any failures in last 50 → down
        #   only forwards, never a direct send → ok-but-test-mode (yellow)
        #   at least one direct send and no recent failures → ok
        if not os.environ.get("RESEND_API_KEY"):
            r_status, r_note = "unconfigured", "RESEND_API_KEY missing"
        elif failed_n > 0 and (sent_n + forwarded_n) == 0:
            r_status, r_note = "down", f"{failed_n} recent send failures"
        elif forwarded_n > 0 and sent_n == 0:
            r_status, r_note = "unconfigured", "Test mode — verify a domain at resend.com to send to any address"
        elif (sent_n + forwarded_n) == 0:
            r_status, r_note = "idle", "No emails sent in the last 50 attempts"
        else:
            r_status, r_note = "ok", f"{sent_n} delivered, {forwarded_n} forwarded, {failed_n} failed (last 50)"
        services.append({
            "name": "Resend (email)",
            "status": r_status,
            "latency_ms": None,
            "note": r_note,
            "sender": sender,
            "by_status": by_status,
        })
    except Exception as e:
        services.append({
            "name": "Resend (email)",
            "status": "ok" if os.environ.get("RESEND_API_KEY") else "unconfigured",
            "error": str(e)[:80],
        })

    # WhatsApp / 360dialog — count configured tenants
    wa_configured = tenants_col.count_documents({"$or": [
        {"whatsapp_providers.meta.configured": True},
        {"whatsapp_providers.360dialog.configured": True},
    ]})
    services.append({
        "name": "WhatsApp (360dialog/Meta)",
        "status": "ok" if wa_configured > 0 else "unconfigured",
        "configured_tenants": wa_configured,
    })

    # Stripe
    services.append({
        "name": "Stripe",
        "status": "ok" if os.environ.get("STRIPE_API_KEY") else "unconfigured",
        "latency_ms": None,
    })

    # Background loops (heuristic: if any sent in last 5 min, OK)
    from datetime import timedelta
    recent_iso = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    touchpoint_active = db["lead_touchpoint_log"].count_documents({"fired_at": {"$gte": recent_iso}}) > 0
    services.append({
        "name": "Touchpoint Engine",
        "status": "ok" if touchpoint_active else "idle",
        "note": "Active if fired in last 10 min",
    })

    return {"services": services, "checked_at": _now()}
