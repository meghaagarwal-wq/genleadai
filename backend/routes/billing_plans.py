"""DIY / DWY / DFY plans + trial logic.

Replaces the legacy Starter/Pro/Growth/Custom Stripe checkout model with a
14-day trial → DIY / DWY / DFY paid tier system. Stripe remains for self-serve
DIY+DWY checkout (when its polling bug is fixed); DFY routes through
'Talk to us' / Calendly.

Tenant fields:
  - plan: 'trial' | 'diy' | 'dwy' | 'dfy'
  - trial_started_at, trial_ends_at  (ISO)
  - is_launch_ready (admin-only marker)
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import db, get_current_user
from routes.tenants import get_active_tenant

router = APIRouter(prefix="/api/plans", tags=["plans"])

tenants_col = db["tenants"]
memberships_col = db["tenant_memberships"]


# ─── Plan catalog (server-owned, frontend reads this) ───────────────────────
PLAN_CATALOG = [
    {
        "id": "diy",
        "name": "DIY",
        "tagline": "Do It Yourself",
        "subtitle": "You run Aria. We give you the tools.",
        "price_inr": 4999,
        "price_label": "₹4,999/month",
        "popular": False,
        "managed": False,
        "limits": {
            "active_leads": 500,
            "team_seats": 5,
            "monthly_conversations": 2000,
        },
        "features": [
            "Full Aria dashboard access",
            "WhatsApp integration setup (self-serve)",
            "Touchpoint map (auto-generated template)",
            "Up to 500 active leads",
            "Up to 5 team seats",
            "Email support (48hr response)",
            "Access to tutorials and documentation",
        ],
        "excluded": [
            "Onboarding call",
            "Managed conversations",
            "Dedicated account manager",
        ],
        "cta": "Start 14-Day Trial",
        "support_sla": "48hr",
    },
    {
        "id": "dwy",
        "name": "DWY",
        "tagline": "Done With You",
        "subtitle": "We set it up. You run it with our guidance.",
        "price_inr": 12999,
        "price_label": "₹12,999/month",
        "popular": True,
        "managed": False,
        "limits": {
            "active_leads": 1000,
            "team_seats": 10,
            "monthly_conversations": 5000,
        },
        "features": [
            "Everything in DIY",
            "GenLeadAI-led onboarding call (1 session)",
            "Aria persona configuration done by GenLeadAI team",
            "Touchpoint map customised by GenLeadAI for your sales process",
            "Monthly 30-min review call",
            "WhatsApp priority support (12hr response)",
            "Up to 1,000 active leads",
            "Up to 10 team seats",
        ],
        "excluded": [
            "Managed conversations",
            "Dedicated account manager",
        ],
        "cta": "Start 14-Day Trial",
        "support_sla": "12hr",
    },
    {
        "id": "dfy",
        "name": "DFY",
        "tagline": "Done For You",
        "subtitle": "GenLeadAI operates Aria on your behalf.",
        "price_inr": 29999,
        "price_label": "Custom (min ₹29,999/month)",
        "popular": False,
        "managed": True,
        "limits": {
            "active_leads": -1,  # unlimited
            "team_seats": -1,
            "monthly_conversations": -1,
        },
        "features": [
            "Everything in DWY",
            "GenLeadAI team manages all Aria conversations end-to-end",
            "Weekly performance reports with pipeline insights",
            "Human SDR escalation handled by GenLeadAI",
            "Dedicated account manager",
            "Unlimited active leads",
            "Unlimited team seats",
            "SLA: 4hr response on all escalations",
        ],
        "excluded": [],
        "cta": "Talk to Us",
        "support_sla": "4hr",
        "contact_email": "support@genleadai.com",
    },
]
PLAN_IDS = {p["id"] for p in PLAN_CATALOG}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def ensure_trial_on_tenant(tenant_id: str) -> dict:
    """Backfill trial_ends_at + plan='trial' on tenants created before this feature.
    Idempotent — only stamps if `trial_ends_at` is unset."""
    t = tenants_col.find_one({"id": tenant_id}, {"_id": 0})
    if not t:
        return {}
    if t.get("trial_ends_at"):
        return t
    now = _now_utc()
    update = {
        "trial_started_at": _iso(now),
        "trial_ends_at": _iso(now + timedelta(days=14)),
        # Don't overwrite a paid plan if one was set; default to 'trial'
        "plan": t.get("plan") if t.get("plan") in PLAN_IDS else "trial",
    }
    tenants_col.update_one({"id": tenant_id}, {"$set": update})
    return {**t, **update}


# ─── Models ──────────────────────────────────────────────────────────────────
class SelectPlanPayload(BaseModel):
    plan_id: str


class ContactPayload(BaseModel):
    note: Optional[str] = ""


# ─── Endpoints ───────────────────────────────────────────────────────────────
@router.get("/catalog")
async def get_catalog(_: dict = Depends(get_current_user)):
    return {"plans": PLAN_CATALOG}


@router.get("/status")
async def get_plan_status(tenant: dict = Depends(get_active_tenant)):
    """Return the tenant's plan + trial state."""
    t = ensure_trial_on_tenant(tenant["id"])
    trial_ends_at = t.get("trial_ends_at")
    plan = t.get("plan") or "trial"
    now = _now_utc()
    trial_expired = False
    days_left = None
    if trial_ends_at:
        try:
            ends = datetime.fromisoformat(trial_ends_at.replace("Z", "+00:00"))
            trial_expired = ends < now
            delta = ends - now
            days_left = max(0, delta.days + (1 if delta.seconds > 0 else 0))
        except Exception:
            pass
    on_trial = plan == "trial" and not trial_expired
    locked = plan == "trial" and trial_expired

    # Usage counters (best-effort, optional)
    leads_col = db["leads"]
    active_leads = leads_col.count_documents({
        "tenant_id": tenant["id"],
        "stage": {"$nin": ["Closed Won", "Closed Lost"]},
    })
    seats_used = memberships_col.count_documents({"tenant_id": tenant["id"]})

    plan_meta = next((p for p in PLAN_CATALOG if p["id"] == plan), None)
    return {
        "plan": plan,
        "plan_meta": plan_meta,
        "trial_started_at": t.get("trial_started_at"),
        "trial_ends_at": trial_ends_at,
        "trial_days_left": days_left,
        "on_trial": on_trial,
        "trial_expired": trial_expired,
        "locked": locked,
        "is_launch_ready": bool(t.get("is_launch_ready")),
        "usage": {
            "active_leads": active_leads,
            "team_seats": seats_used,
        },
    }


@router.post("/select")
async def select_plan(payload: SelectPlanPayload, tenant: dict = Depends(get_active_tenant)):
    """Set the tenant's plan (DIY/DWY/DFY). Owner/admin only.

    Note: this does NOT charge a card — that's a separate Stripe step. This
    endpoint is for plan-state tracking + paywall unlock when the trial expires
    and the user opts in. For DFY it just records the intent so the user can
    proceed past the paywall while sales follows up.
    """
    if tenant.get("_member_role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")
    if payload.plan_id not in PLAN_IDS:
        raise HTTPException(status_code=400, detail="Invalid plan_id")
    now = _iso(_now_utc())
    tenants_col.update_one(
        {"id": tenant["id"]},
        {"$set": {"plan": payload.plan_id, "plan_selected_at": now, "updated_at": now}},
    )
    return {"status": "ok", "plan": payload.plan_id}


@router.post("/contact-sales")
async def contact_sales(payload: ContactPayload, tenant: dict = Depends(get_active_tenant), current_user: dict = Depends(get_current_user)):
    """Logs a 'Talk to us' click on the DFY card. Frontend additionally opens
    a Calendly / mailto link client-side."""
    db["dfy_inquiries"].insert_one({
        "tenant_id": tenant["id"],
        "tenant_name": tenant.get("name"),
        "user_email": current_user["email"],
        "note": (payload.note or "").strip(),
        "created_at": _iso(_now_utc()),
    })
    return {"status": "ok"}
