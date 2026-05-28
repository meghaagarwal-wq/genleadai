"""iter108 — ACTION 3 (continued): Legacy ARIA plan catalog + 4-tier billing.

This module owns the 4-tier ARIA plan catalog (Starter / Growth / Pro / Custom)
with feature flags + the legacy billing endpoints that were inline in server.py.

NOTE — Why is this called "legacy"?
The newer per-tenant Stripe Checkout flow lives in:
  - `routes/billing.py`           (POST /api/billing/checkout, GET /status/...)
  - `routes/billing_upgrade.py`   (invoices, checkout/session, webhook/stripe)
  - `routes/billing_plans.py`     (/api/plans/* — newer plan catalog)

This module keeps the OLDER endpoints alive:
  - GET  /api/billing/plans            — 4-tier catalog + feature matrix
  - GET  /api/billing/current-plan     — what plan is THIS workspace on?
  - POST /api/billing/request-upgrade  — email the admin for upgrade
  - GET  /api/billing/transactions     — payment-history list
  - POST /api/dev/set-plan             — admin-only instant plan switch (no Stripe)

And it re-exports the plan-gating helpers so anyone (including tests) can
`from routes.billing_plans_legacy import require_feature, _has_feature,
SUBSCRIPTION_PLANS` without depending on `server`.

The /checkout, /status, and /webhook routes were duplicates of newer flows
in `billing.py` / `billing_upgrade.py` and have been removed.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Optional

import resend
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pymongo import DESCENDING

from deps import activities_collection, db, get_current_user

router = APIRouter(tags=["iter108-billing-legacy"])

payment_transactions = db["payment_transactions"]
workspace_settings_collection = db["workspace_settings"]


# ── 4-tier ARIA plan catalog ────────────────────────────────────────────
# Old "scale" was renamed to "pro" in iter82. "custom" is contact-sales only.
SUBSCRIPTION_PLANS: dict = {
    "starter": {
        "name": "ARIA Starter",
        "amount": 49.00,
        "leads": 500,
        "ai_credits": 100,
        "tagline": "For small teams that need basic lead control",
        "headline_features": [
            "Manual lead entry & dashboard",
            "Lead status & owner assignment",
            "Follow-up reminders & basic notes",
            "Manual Hot/Warm/Cold tagging",
            "Daily task list & basic reports",
        ],
        "features": {
            "lead_inbox": True, "lead_profile": True, "manual_lead_entry": True,
            "follow_up_reminders": True, "basic_notes": True, "source_tagging": True,
            "manual_temperature": True, "daily_task_list": True, "basic_reports": True,
            "owner_assignment": True,
            "csv_import": False, "multi_source_capture": False, "form_integration": False,
            "rep_dashboard": False, "overdue_alerts": False, "lead_aging_tracker": False,
            "stage_pipeline": False, "ai_followup_basic": False, "ai_lead_scoring": False,
            "founder_summary": False, "whatsapp_click_to_msg": False, "limited_crm_sync": False,
            "ai_qualification": False, "ai_followup_drafts": False, "whatsapp_workflow": False,
            "automated_tasks": False, "rep_performance": False, "lost_reason_tracking": False,
            "proposal_tracking": False, "deal_value": False, "pipeline_value_dashboard": False,
            "calendar_integration": False, "daily_founder_report": False,
            "weekly_sales_summary": False, "crm_sync_full": False, "rbac": False,
            "custom_stages": False, "custom_scoring": False, "custom_workflows": False,
            "ai_call_scheduling": False, "advanced_whatsapp": False, "multi_brand": False,
            "advanced_crm": False, "api_integrations": False, "client_dashboards": False,
            "advanced_attribution": False, "custom_reports": False, "sla_alerts": False,
            "training_section": False, "dedicated_support": False,
        },
    },
    "growth": {
        "name": "ARIA Growth",
        "amount": 149.00,
        "leads": 2000,
        "ai_credits": 500,
        "tagline": "For businesses running campaigns and needing sales accountability",
        "headline_features": [
            "Multi-source lead capture & CSV import",
            "Stage-wise pipeline & sales-rep dashboard",
            "Overdue follow-up alerts & lead-ageing tracker",
            "Basic AI follow-up suggestions & lead scoring",
            "WhatsApp click-to-message & founder summary",
        ],
        "features": {
            "lead_inbox": True, "lead_profile": True, "manual_lead_entry": True,
            "follow_up_reminders": True, "basic_notes": True, "source_tagging": True,
            "manual_temperature": True, "daily_task_list": True, "basic_reports": True,
            "owner_assignment": True,
            "csv_import": True, "multi_source_capture": True, "form_integration": True,
            "rep_dashboard": True, "overdue_alerts": True, "lead_aging_tracker": True,
            "stage_pipeline": True, "ai_followup_basic": True, "ai_lead_scoring": True,
            "founder_summary": True, "whatsapp_click_to_msg": True, "limited_crm_sync": True,
            "ai_qualification": False, "ai_followup_drafts": False, "whatsapp_workflow": False,
            "automated_tasks": False, "rep_performance": False, "lost_reason_tracking": False,
            "proposal_tracking": False, "deal_value": False, "pipeline_value_dashboard": False,
            "calendar_integration": False, "daily_founder_report": False,
            "weekly_sales_summary": False, "crm_sync_full": False, "rbac": False,
            "custom_stages": False, "custom_scoring": False, "custom_workflows": False,
            "ai_call_scheduling": False, "advanced_whatsapp": False, "multi_brand": False,
            "advanced_crm": False, "api_integrations": False, "client_dashboards": False,
            "advanced_attribution": False, "custom_reports": False, "sla_alerts": False,
            "training_section": False, "dedicated_support": False,
        },
    },
    "pro": {
        "name": "ARIA Pro",
        "amount": 399.00,
        "leads": 10000,
        "ai_credits": 2000,
        "tagline": "For founder-led companies that need serious sales visibility",
        "headline_features": [
            "AI lead qualification, scoring & follow-up drafts",
            "WhatsApp workflows, email templates & automated tasks",
            "Sales-rep performance, lost-reason & proposal tracking",
            "Pipeline value, calendar integration & full CRM sync",
            "Daily founder report, weekly sales summary & RBAC",
        ],
        "features": {
            "lead_inbox": True, "lead_profile": True, "manual_lead_entry": True,
            "follow_up_reminders": True, "basic_notes": True, "source_tagging": True,
            "manual_temperature": True, "daily_task_list": True, "basic_reports": True,
            "owner_assignment": True,
            "csv_import": True, "multi_source_capture": True, "form_integration": True,
            "rep_dashboard": True, "overdue_alerts": True, "lead_aging_tracker": True,
            "stage_pipeline": True, "ai_followup_basic": True, "ai_lead_scoring": True,
            "founder_summary": True, "whatsapp_click_to_msg": True, "limited_crm_sync": True,
            "ai_qualification": True, "ai_followup_drafts": True, "whatsapp_workflow": True,
            "automated_tasks": True, "rep_performance": True, "lost_reason_tracking": True,
            "proposal_tracking": True, "deal_value": True, "pipeline_value_dashboard": True,
            "calendar_integration": True, "daily_founder_report": True,
            "weekly_sales_summary": True, "crm_sync_full": True, "rbac": True,
            "custom_stages": False, "custom_scoring": False, "custom_workflows": False,
            "ai_call_scheduling": False, "advanced_whatsapp": False, "multi_brand": False,
            "advanced_crm": False, "api_integrations": False, "client_dashboards": False,
            "advanced_attribution": False, "custom_reports": False, "sla_alerts": False,
            "training_section": False, "dedicated_support": False,
        },
    },
    "custom": {
        "name": "ARIA Custom",
        "amount": None,
        "leads": -1,
        "ai_credits": -1,
        "tagline": "For complex sales engines and multi-channel funnels",
        "contact_sales": True,
        "headline_features": [
            "Custom stages, scoring & workflows",
            "AI call scheduling & qualification forms",
            "Multi-brand, multi-branch & advanced WhatsApp automation",
            "Advanced CRM, API integrations & client-specific dashboards",
            "SLA alerts, training section & dedicated implementation support",
        ],
        "features": {
            "lead_inbox": True, "lead_profile": True, "manual_lead_entry": True,
            "follow_up_reminders": True, "basic_notes": True, "source_tagging": True,
            "manual_temperature": True, "daily_task_list": True, "basic_reports": True,
            "owner_assignment": True,
            "csv_import": True, "multi_source_capture": True, "form_integration": True,
            "rep_dashboard": True, "overdue_alerts": True, "lead_aging_tracker": True,
            "stage_pipeline": True, "ai_followup_basic": True, "ai_lead_scoring": True,
            "founder_summary": True, "whatsapp_click_to_msg": True, "limited_crm_sync": True,
            "ai_qualification": True, "ai_followup_drafts": True, "whatsapp_workflow": True,
            "automated_tasks": True, "rep_performance": True, "lost_reason_tracking": True,
            "proposal_tracking": True, "deal_value": True, "pipeline_value_dashboard": True,
            "calendar_integration": True, "daily_founder_report": True,
            "weekly_sales_summary": True, "crm_sync_full": True, "rbac": True,
            "custom_stages": True, "custom_scoring": True, "custom_workflows": True,
            "ai_call_scheduling": True, "advanced_whatsapp": True, "multi_brand": True,
            "advanced_crm": True, "api_integrations": True, "client_dashboards": True,
            "advanced_attribution": True, "custom_reports": True, "sla_alerts": True,
            "training_section": True, "dedicated_support": True,
        },
    },
}

# Backwards compat: legacy "scale" id maps to "pro".
_LEGACY_PLAN_ALIASES = {"scale": "pro"}


# ── Plan-gating helpers ─────────────────────────────────────────────────
def _workspace_plan_id() -> str:
    """Return the workspace's current plan id. Defaults to 'starter'."""
    cfg = workspace_settings_collection.find_one(
        {"scope": "workspace"}, {"_id": 0, "plan_id": 1}
    ) or {}
    pid = cfg.get("plan_id") or "starter"
    return _LEGACY_PLAN_ALIASES.get(pid, pid)


def _has_feature(feature_key: str, plan_id: Optional[str] = None) -> bool:
    pid = plan_id or _workspace_plan_id()
    plan = SUBSCRIPTION_PLANS.get(_LEGACY_PLAN_ALIASES.get(pid, pid))
    if not plan:
        return False
    return bool(plan.get("features", {}).get(feature_key, False))


def require_feature(feature_key: str):
    """FastAPI dep — 402 friendly upgrade payload when feature is locked."""
    async def _check(current_user: dict = Depends(get_current_user)):
        if _has_feature(feature_key):
            return current_user
        raise HTTPException(
            status_code=402,
            detail={
                "code": "feature_locked",
                "feature": feature_key,
                "current_plan": _workspace_plan_id(),
                "message": f"Upgrade your ARIA plan to unlock '{feature_key}'.",
            },
        )
    return _check


# ── Models ──────────────────────────────────────────────────────────────
class UpgradeRequest(BaseModel):
    target_plan_id: str
    feature_key: Optional[str] = None
    note: Optional[str] = None


# ── Endpoints ───────────────────────────────────────────────────────────
@router.get("/api/billing/plans")
async def get_billing_plans():
    """Public — full 4-tier plan catalog with feature matrix."""
    plans_out = []
    for pid, p in SUBSCRIPTION_PLANS.items():
        plans_out.append({
            "id": pid,
            "name": p["name"],
            "amount": p["amount"],
            "leads": p["leads"],
            "ai_credits": p["ai_credits"],
            "tagline": p.get("tagline"),
            "headline_features": p.get("headline_features", []),
            "contact_sales": p.get("contact_sales", False),
            "features": p.get("features", {}),
        })
    return {
        "plans": plans_out,
        "feature_keys": sorted({k for p in SUBSCRIPTION_PLANS.values() for k in p.get("features", {})}),
    }


@router.get("/api/billing/current-plan")
async def get_current_plan(current_user: dict = Depends(get_current_user)):
    """Return the workspace's current plan id and unlocked features."""
    pid = _workspace_plan_id()
    plan = SUBSCRIPTION_PLANS.get(pid, SUBSCRIPTION_PLANS["starter"])
    cfg = workspace_settings_collection.find_one(
        {"scope": "workspace"}, {"_id": 0, "plan_activated_at": 1, "plan_id": 1}
    ) or {}
    return {
        "plan_id": pid,
        "name": plan["name"],
        "amount": plan["amount"],
        "tagline": plan.get("tagline"),
        "contact_sales": plan.get("contact_sales", False),
        "features": plan.get("features", {}),
        "activated_at": cfg.get("plan_activated_at"),
    }


@router.post("/api/billing/request-upgrade")
async def request_upgrade(req: UpgradeRequest, current_user: dict = Depends(get_current_user)):
    """Email admin asking for upgrade approval. Used by the Upgrade modal."""
    target = _LEGACY_PLAN_ALIASES.get(req.target_plan_id, req.target_plan_id)
    plan = SUBSCRIPTION_PLANS.get(target)
    if not plan:
        raise HTTPException(status_code=400, detail="Invalid target plan")
    admin_email = (
        os.getenv("UPGRADE_REQUEST_EMAIL")
        or os.getenv("FOUNDER_EMAIL")
        or os.getenv("SENDER_EMAIL", "onboarding@resend.dev")
    )
    current_pid = _workspace_plan_id()
    current_plan = SUBSCRIPTION_PLANS.get(current_pid, {})
    feature_label = req.feature_key or "general upgrade"
    note = (req.note or "").strip()
    html = f"""<div style="font-family:Plus Jakarta Sans,Arial,sans-serif;color:#1A0A2E;">
      <h2 style="color:#7C35DC;margin:0 0 12px 0;">ARIA Upgrade Request</h2>
      <p><strong>{current_user.get('email')}</strong> from <strong>{current_user.get('full_name') or 'their workspace'}</strong> wants to upgrade.</p>
      <table style="border-collapse:collapse;margin:16px 0;font-size:14px;">
        <tr><td style="padding:6px 12px;color:#9B8AB0;">Current plan:</td><td style="padding:6px 12px;font-weight:700;">{current_plan.get('name','—')}</td></tr>
        <tr><td style="padding:6px 12px;color:#9B8AB0;">Target plan:</td><td style="padding:6px 12px;font-weight:700;color:#7C35DC;">{plan.get('name')}</td></tr>
        <tr><td style="padding:6px 12px;color:#9B8AB0;">Feature requested:</td><td style="padding:6px 12px;">{feature_label}</td></tr>
      </table>
      {f'<p style="background:#F4F0FF;padding:12px;border-radius:8px;border:1px solid #E0D4F7;font-size:13px;"><strong>Note:</strong> {note}</p>' if note else ''}
      <p style="color:#5A4A7A;font-size:13px;margin-top:24px;">Reply to this email to action the request, or open the workspace Stripe to issue the upgrade.</p>
    </div>"""
    try:
        await asyncio.to_thread(resend.Emails.send, {
            "from": os.getenv("SENDER_EMAIL", "onboarding@resend.dev"),
            "to": [admin_email],
            "reply_to": current_user.get("email"),
            "subject": f"[ARIA] Upgrade request: {plan.get('name')} from {current_user.get('email')}",
            "html": html,
        })
    except Exception as e:
        print(f"Upgrade request email failed: {e}")
    activities_collection.insert_one({
        "lead_id": None,
        "user_id": current_user["email"],
        "activity_type": "upgrade_requested",
        "subject": f"Upgrade requested: {current_pid} -> {target}",
        "body": (note or "")[:500],
        "outcome": None,
        "duration_minutes": None,
        "metadata": {
            "feature": req.feature_key,
            "target_plan": target,
            "from_plan": current_pid,
            "admin_email": admin_email,
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"requested": True, "target_plan": target, "admin_email_used": admin_email}


@router.get("/api/billing/transactions")
async def get_transactions(current_user: dict = Depends(get_current_user)):
    """Payment-transaction history for the current user."""
    txns = list(payment_transactions.find(
        {"user_email": current_user["email"]}, {"_id": 0},
    ).sort("created_at", DESCENDING).limit(20))
    return {"transactions": txns}


@router.post("/api/dev/set-plan")
async def dev_set_plan(plan_id: str, current_user: dict = Depends(get_current_user)):
    """Dev/admin only — switch workspace plan instantly without Stripe. Test-only."""
    if current_user.get("role") not in ("admin", "founder"):
        raise HTTPException(status_code=403, detail="Admin only")
    target = _LEGACY_PLAN_ALIASES.get(plan_id, plan_id)
    if target not in SUBSCRIPTION_PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan")
    workspace_settings_collection.update_one(
        {"scope": "workspace"},
        {"$set": {
            "plan_id": target,
            "plan_activated_at": datetime.now(timezone.utc).isoformat(),
            "set_by": "dev_endpoint",
            "set_by_user": current_user["email"],
        }},
        upsert=True,
    )
    return {"plan_id": target, "name": SUBSCRIPTION_PLANS[target]["name"]}
