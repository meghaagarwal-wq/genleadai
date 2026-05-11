"""Admin Revenue Panel — KPIs, subscriptions, payments, churn, trial funnel, invoices.

Master-admin (role == 'admin') only. Translates the Supabase-spec into Mongo
collections + asyncio. Builds on top of the existing `tenants`, `tenant_memberships`,
`users`, `leads` and `payment_transactions` collections — does not modify them.

New collections:
  - subscriptions      : one doc per tenant subscription record
  - payments           : one doc per recorded payment (manual or stripe)
  - invoice_sequence   : single counter doc {_id:"invoices", year, value}

Compatibility:
  - Existing tenants.plan field (trial/diy/dwy/dfy) is the source of truth for
    "current plan". A subscription record is auto-provisioned per tenant on
    first read.
"""
from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from deps import db, get_current_user
from routes.billing_plans import PLAN_CATALOG, PLAN_IDS

router = APIRouter(prefix="/api/admin/revenue", tags=["admin-revenue"])
invoice_router = APIRouter(prefix="/api/admin/invoices", tags=["admin-invoices"])

# ─── Collections ─────────────────────────────────────────────────────────────
tenants_col = db["tenants"]
memberships_col = db["tenant_memberships"]
users_col = db["users"]
subs_col = db["subscriptions"]
payments_col = db["payments"]
sequence_col = db["invoice_sequence"]
leads_col = db["leads"]

# ─── Plan price map (INR) ────────────────────────────────────────────────────
PLAN_PRICE_INR = {p["id"]: p.get("price_inr", 0) for p in PLAN_CATALOG}
PLAN_PRICE_INR["trial"] = 0
PLAN_PRICE_INR["free"] = 0
PLAN_PRICE_INR["suspended"] = 0

CANCEL_REASONS = {"price", "no_longer_needed", "competitor", "support_issue", "other"}

# GenLeadAI legal entity (for invoices)
COMPANY = {
    "name": "GenLeadAI",
    "product": "Aria by GenLeadAI",
    "address_line1": "Shillong, Meghalaya, India",
    "gstin": "17BVKPA9777N1ZP",
    "email": "meghaagarwal@genleadai.com",
}
GST_RATE = 0.18

# ─── Helpers ─────────────────────────────────────────────────────────────────
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse(dtstr: Optional[str]) -> Optional[datetime]:
    if not dtstr:
        return None
    try:
        s = str(dtstr).replace("Z", "+00:00")
        d = datetime.fromisoformat(s)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _require_master_admin(user: dict):
    if (user.get("role") or "").lower() != "admin":
        raise HTTPException(status_code=403, detail="Master admin only")


def _next_invoice_number() -> str:
    year = _now().year
    res = sequence_col.find_one_and_update(
        {"_id": f"invoices_{year}"},
        {"$inc": {"value": 1}, "$setOnInsert": {"year": year}},
        upsert=True,
        return_document=True,
    )
    n = (res or {}).get("value", 1)
    return f"INV-{year}-{n:04d}"


def _ensure_subscription(tenant: dict) -> dict:
    """Idempotent: create a subscription record for a tenant if missing."""
    sub = subs_col.find_one({"tenant_id": tenant["id"]}, {"_id": 0})
    if sub:
        return sub
    plan = tenant.get("plan") or "trial"
    started = _parse(tenant.get("trial_started_at")) or _parse(tenant.get("created_at")) or _now()
    period_end = _parse(tenant.get("trial_ends_at")) or (started + timedelta(days=30))
    status = "active" if plan in PLAN_IDS else ("trial" if plan == "trial" else "active")
    doc = {
        "id": f"sub_{uuid.uuid4().hex[:12]}",
        "tenant_id": tenant["id"],
        "tenant_name": tenant.get("name") or tenant.get("workspace_name"),
        "owner_email": tenant.get("owner_email"),
        "plan": plan,
        "custom_price": None,
        "status": status,
        "started_at": _iso(started),
        "current_period_start": _iso(started),
        "current_period_end": _iso(period_end),
        "cancelled_at": None,
        "cancel_reason": None,
        "notes": None,
        "stripe_subscription_id": None,
        "created_at": _iso(_now()),
        "updated_at": _iso(_now()),
    }
    subs_col.insert_one(doc.copy())
    doc.pop("_id", None)
    return doc


def _monthly_value(sub: dict) -> float:
    if sub.get("custom_price") is not None:
        return float(sub["custom_price"])
    return float(PLAN_PRICE_INR.get(sub.get("plan") or "trial", 0))


def _month_bounds(dt: datetime) -> (datetime, datetime):
    start = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


# ─── Models ──────────────────────────────────────────────────────────────────
class SubscriptionUpdate(BaseModel):
    plan: Optional[str] = None
    custom_price: Optional[float] = Field(None, ge=0)
    notes: Optional[str] = None
    status: Optional[str] = None  # active | suspended | cancelled


class ExtendPayload(BaseModel):
    days: int = Field(30, ge=1, le=365)


class CancelPayload(BaseModel):
    reason: str  # price | no_longer_needed | competitor | support_issue | other
    note: Optional[str] = None


class ManualPayment(BaseModel):
    tenant_id: str
    amount: float = Field(..., gt=0)
    currency: str = "INR"
    method: str  # manual | bank_transfer | upi | stripe
    paid_at: Optional[str] = None  # ISO string
    reference_number: Optional[str] = None
    note: Optional[str] = None
    plan: Optional[str] = None  # records on which plan this payment lands


# ─── Endpoints: Summary KPIs ────────────────────────────────────────────────
@router.get("/summary")
async def revenue_summary(current_user: dict = Depends(get_current_user)):
    _require_master_admin(current_user)
    now = _now()
    this_start, this_end = _month_bounds(now)
    last_start, last_end = _month_bounds(now - timedelta(days=now.day + 1))

    # Provision subscriptions for any tenants missing one
    for t in tenants_col.find({}, {"_id": 0}):
        _ensure_subscription(t)

    all_subs = list(subs_col.find({}, {"_id": 0}))
    active_paying = [s for s in all_subs if s.get("plan") in {"diy", "dwy", "dfy"} and s.get("status") == "active"]
    trials = [s for s in all_subs if s.get("plan") == "trial" and s.get("status") in ("trial", "active")]

    mrr = sum(_monthly_value(s) for s in active_paying)
    arr = mrr * 12

    active_trials = []
    for s in trials:
        end = _parse(s.get("current_period_end"))
        if end and end > now:
            active_trials.append(s)

    # Trial-to-paid conversion this month
    expired_this_month = 0
    converted_this_month = 0
    for s in all_subs:
        # converted: subscription with started_at this month and plan in paid plans
        started = _parse(s.get("started_at"))
        if s.get("plan") in {"diy", "dwy", "dfy"} and started and this_start <= started < this_end:
            converted_this_month += 1
    # trials whose period ended this month
    for s in trials + [x for x in all_subs if x.get("plan") in {"diy","dwy","dfy"}]:
        end = _parse(s.get("current_period_end"))
        if end and this_start <= end < this_end:
            expired_this_month += 1
    conv_rate = round((converted_this_month / expired_this_month) * 100, 1) if expired_this_month else 0.0

    # Monthly churn
    cancelled_this_month = sum(
        1 for s in all_subs
        if s.get("status") == "cancelled"
        and (_parse(s.get("cancelled_at")) or _now()) >= this_start
        and (_parse(s.get("cancelled_at")) or _now()) < this_end
    )
    active_last_month = sum(
        1 for s in all_subs
        if s.get("plan") in {"diy", "dwy", "dfy"}
        and (_parse(s.get("started_at")) or _now()) < last_end
    )
    churn_rate = round((cancelled_this_month / active_last_month) * 100, 1) if active_last_month else 0.0

    # Trend: last month's MRR for comparison
    last_mrr = sum(
        _monthly_value(s) for s in all_subs
        if s.get("plan") in {"diy", "dwy", "dfy"}
        and (_parse(s.get("started_at")) or _now()) < last_end
        and (s.get("status") != "cancelled" or (_parse(s.get("cancelled_at")) or _now()) >= last_end)
    )
    mrr_trend = round(((mrr - last_mrr) / last_mrr) * 100, 1) if last_mrr else 0.0

    return {
        "kpis": {
            "mrr": round(mrr, 2),
            "arr": round(arr, 2),
            "total_paying_clients": len(active_paying),
            "active_trials": len(active_trials),
            "trial_to_paid_pct": conv_rate,
            "monthly_churn_pct": churn_rate,
        },
        "trends": {
            "mrr_delta_pct": mrr_trend,
            "paying_delta": len(active_paying) - active_last_month,
            "trials_delta": 0,  # historical trial counts not tracked yet
            "conversion_delta": 0.0,
            "churn_delta": 0.0,
            "arr_delta_pct": mrr_trend,
        },
        "currency": "INR",
    }


@router.get("/by-plan")
async def revenue_by_plan(months: int = 6, current_user: dict = Depends(get_current_user)):
    _require_master_admin(current_user)
    now = _now()
    out = []
    for i in range(months - 1, -1, -1):
        ref = (now.replace(day=1) - timedelta(days=i * 31)).replace(day=1)
        m_start, m_end = _month_bounds(ref)
        # For each plan: sum payments collected in that month
        agg = {"diy": 0.0, "dwy": 0.0, "dfy": 0.0}
        pays = payments_col.find(
            {"status": "paid", "paid_at": {"$gte": _iso(m_start), "$lt": _iso(m_end)}},
            {"_id": 0},
        )
        for p in pays:
            pl = (p.get("plan") or "").lower()
            if pl in agg:
                agg[pl] += float(p.get("amount") or 0)
        out.append({
            "month": m_start.strftime("%b %y"),
            "month_iso": _iso(m_start),
            **agg,
            "total": round(sum(agg.values()), 2),
        })
    return {"data": out}


# ─── Endpoints: Subscriptions ────────────────────────────────────────────────
@router.get("/subscriptions")
async def list_subscriptions(
    status: Optional[str] = None,
    plan: Optional[str] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    _require_master_admin(current_user)
    # Provision for any newly-created tenants
    for t in tenants_col.find({}, {"_id": 0}):
        _ensure_subscription(t)

    q: Dict[str, Any] = {}
    if status:
        q["status"] = status
    if plan:
        q["plan"] = plan
    if search:
        q["$or"] = [
            {"tenant_name": {"$regex": search, "$options": "i"}},
            {"owner_email": {"$regex": search, "$options": "i"}},
        ]
    subs = list(subs_col.find(q, {"_id": 0}).sort("created_at", -1).limit(500))
    # Decorate with monthly value
    for s in subs:
        s["monthly_value"] = _monthly_value(s)
    return {"subscriptions": subs, "total": len(subs)}


@router.put("/subscriptions/{tenant_id}")
async def update_subscription(tenant_id: str, payload: SubscriptionUpdate, current_user: dict = Depends(get_current_user)):
    _require_master_admin(current_user)
    sub = subs_col.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    update: Dict[str, Any] = {"updated_at": _iso(_now())}
    if payload.plan is not None:
        if payload.plan not in PLAN_IDS and payload.plan not in ("trial", "suspended"):
            raise HTTPException(status_code=400, detail="Invalid plan")
        update["plan"] = payload.plan
        # Mirror back to tenants.plan for paywall consistency
        tenants_col.update_one({"id": tenant_id}, {"$set": {"plan": payload.plan, "updated_at": _iso(_now())}})
    if payload.custom_price is not None:
        update["custom_price"] = payload.custom_price
    if payload.notes is not None:
        update["notes"] = payload.notes
    if payload.status is not None:
        update["status"] = payload.status
        if payload.status == "cancelled" and not sub.get("cancelled_at"):
            update["cancelled_at"] = _iso(_now())
    subs_col.update_one({"tenant_id": tenant_id}, {"$set": update})
    return {"status": "ok"}


@router.post("/subscriptions/{tenant_id}/extend")
async def extend_subscription(tenant_id: str, payload: ExtendPayload, current_user: dict = Depends(get_current_user)):
    _require_master_admin(current_user)
    sub = subs_col.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    end = _parse(sub.get("current_period_end")) or _now()
    new_end = end + timedelta(days=payload.days)
    subs_col.update_one(
        {"tenant_id": tenant_id},
        {"$set": {"current_period_end": _iso(new_end), "updated_at": _iso(_now())}},
    )
    # If this is a trial, also extend the tenant's trial_ends_at
    if sub.get("plan") == "trial":
        tenants_col.update_one(
            {"id": tenant_id},
            {"$set": {"trial_ends_at": _iso(new_end), "updated_at": _iso(_now())}},
        )
    return {"status": "ok", "new_period_end": _iso(new_end)}


@router.post("/subscriptions/{tenant_id}/cancel")
async def cancel_subscription(tenant_id: str, payload: CancelPayload, current_user: dict = Depends(get_current_user)):
    _require_master_admin(current_user)
    if payload.reason not in CANCEL_REASONS:
        raise HTTPException(status_code=400, detail="Invalid cancellation reason")
    sub = subs_col.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    now = _iso(_now())
    subs_col.update_one(
        {"tenant_id": tenant_id},
        {"$set": {
            "status": "cancelled",
            "cancelled_at": now,
            "cancel_reason": payload.reason,
            "cancel_note": payload.note,
            "updated_at": now,
        }},
    )
    return {"status": "ok"}


# ─── Endpoints: Payments ─────────────────────────────────────────────────────
@router.get("/payments")
async def list_payments(
    tenant_id: Optional[str] = None,
    status: Optional[str] = None,
    method: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
    current_user: dict = Depends(get_current_user),
):
    _require_master_admin(current_user)
    q: Dict[str, Any] = {}
    if tenant_id:
        q["tenant_id"] = tenant_id
    if status:
        q["status"] = status
    if method:
        q["method"] = method
    total = payments_col.count_documents(q)
    pays = list(payments_col.find(q, {"_id": 0}).sort("paid_at", -1).skip(skip).limit(limit))
    return {"payments": pays, "total": total}


@router.post("/payments/manual")
async def record_manual_payment(payload: ManualPayment, current_user: dict = Depends(get_current_user)):
    _require_master_admin(current_user)
    tenant = tenants_col.find_one({"id": payload.tenant_id}, {"_id": 0})
    if not tenant:
        raise HTTPException(status_code=404, detail="Workspace not found")
    sub = _ensure_subscription(tenant)
    inv_no = _next_invoice_number()
    paid_at = payload.paid_at or _iso(_now())
    doc = {
        "id": f"pay_{uuid.uuid4().hex[:12]}",
        "tenant_id": payload.tenant_id,
        "tenant_name": tenant.get("name") or tenant.get("workspace_name"),
        "owner_email": tenant.get("owner_email"),
        "subscription_id": sub.get("id"),
        "plan": payload.plan or sub.get("plan") or "diy",
        "amount": float(payload.amount),
        "currency": payload.currency or "INR",
        "method": payload.method,
        "status": "paid",
        "reference_number": payload.reference_number,
        "paid_at": paid_at,
        "note": payload.note,
        "invoice_number": inv_no,
        "created_by": current_user.get("email"),
        "created_at": _iso(_now()),
    }
    payments_col.insert_one(doc.copy())
    doc.pop("_id", None)

    # Advance the subscription period if this is a renewal payment on a paid plan
    if doc["plan"] in {"diy", "dwy", "dfy"}:
        new_end = _parse(sub.get("current_period_end")) or _now()
        if new_end < _now():
            new_end = _now()
        new_end = new_end + timedelta(days=30)
        subs_col.update_one(
            {"tenant_id": payload.tenant_id},
            {"$set": {
                "plan": doc["plan"],
                "status": "active",
                "current_period_end": _iso(new_end),
                "updated_at": _iso(_now()),
            }},
        )
        tenants_col.update_one(
            {"id": payload.tenant_id},
            {"$set": {"plan": doc["plan"], "updated_at": _iso(_now())}},
        )
    return {"status": "ok", "payment": doc}


# ─── Endpoints: Churn ────────────────────────────────────────────────────────
@router.get("/churn")
async def churn_panel(current_user: dict = Depends(get_current_user)):
    _require_master_admin(current_user)
    now = _now()
    # Last 12 months churn line
    series = []
    for i in range(11, -1, -1):
        ref = (now.replace(day=1) - timedelta(days=i * 31)).replace(day=1)
        m_start, m_end = _month_bounds(ref)
        cancelled = subs_col.count_documents({
            "status": "cancelled",
            "cancelled_at": {"$gte": _iso(m_start), "$lt": _iso(m_end)},
        })
        active_before = subs_col.count_documents({
            "plan": {"$in": ["diy", "dwy", "dfy"]},
            "started_at": {"$lt": _iso(m_start)},
        })
        rate = round((cancelled / active_before) * 100, 1) if active_before else 0.0
        series.append({"month": m_start.strftime("%b %y"), "rate": rate, "cancelled": cancelled})

    # Churned accounts list
    churned = list(subs_col.find(
        {"status": "cancelled"}, {"_id": 0}
    ).sort("cancelled_at", -1).limit(50))
    for s in churned:
        s["monthly_value_lost"] = _monthly_value(s)

    # Simple retention cohort: % of subs started in month X still active at M+1/2/3
    cohort = []
    for i in range(5, -1, -1):
        ref = (now.replace(day=1) - timedelta(days=i * 31)).replace(day=1)
        m_start, m_end = _month_bounds(ref)
        cohort_subs = list(subs_col.find({
            "plan": {"$in": ["diy", "dwy", "dfy"]},
            "started_at": {"$gte": _iso(m_start), "$lt": _iso(m_end)},
        }, {"_id": 0, "id": 1, "status": 1, "cancelled_at": 1}))
        total = len(cohort_subs)
        retention = {"cohort": m_start.strftime("%b %y"), "size": total}
        for k in (1, 2, 3):
            check_end = _month_bounds(m_start + timedelta(days=k * 31))[0]
            still = sum(
                1 for s in cohort_subs
                if s.get("status") != "cancelled"
                or (_parse(s.get("cancelled_at")) and _parse(s.get("cancelled_at")) >= check_end)
            )
            retention[f"m{k}"] = round((still / total) * 100, 0) if total else 0
        cohort.append(retention)

    return {"series": series, "churned": churned, "cohort": cohort}


# ─── Endpoints: Trial Funnel ─────────────────────────────────────────────────
@router.get("/trial-funnel")
async def trial_funnel(current_user: dict = Depends(get_current_user)):
    _require_master_admin(current_user)
    now = _now()
    m_start, m_end = _month_bounds(now)

    # Signups this month = tenants created
    signups = list(tenants_col.find({
        "created_at": {"$gte": _iso(m_start), "$lt": _iso(m_end)},
    }, {"_id": 0}))
    # Completed onboarding
    completed = [t for t in signups if t.get("onboarding_completed")]
    # WhatsApp connected (looking at onboarding_config or tenant.whatsapp_connected)
    onbd = list(db["onboarding_config"].find({"tenant_id": {"$in": [t["id"] for t in signups]}}, {"_id": 0}))
    onbd_map = {o.get("tenant_id"): o for o in onbd}
    whatsapp_connected = [t for t in completed if onbd_map.get(t["id"], {}).get("whatsapp_api_key") or t.get("whatsapp_connected")]
    # First lead created (any lead exists for this tenant)
    first_lead = []
    for t in whatsapp_connected:
        if leads_col.count_documents({"tenant_id": t["id"]}) > 0:
            first_lead.append(t)
    # Converted to paid: subscription plan in paid + started_at this month
    sub_ids = list(subs_col.find({
        "plan": {"$in": ["diy", "dwy", "dfy"]},
        "started_at": {"$gte": _iso(m_start), "$lt": _iso(m_end)},
    }, {"_id": 0, "tenant_id": 1}))
    converted_ids = {s["tenant_id"] for s in sub_ids}
    converted = [t for t in signups if t["id"] in converted_ids]

    stages = [
        {"key": "signups", "label": "Signups", "count": len(signups), "tenants": [{"id": t["id"], "name": t.get("name"), "owner_email": t.get("owner_email")} for t in signups]},
        {"key": "completed_onboarding", "label": "Completed Onboarding", "count": len(completed), "tenants": [{"id": t["id"], "name": t.get("name"), "owner_email": t.get("owner_email")} for t in completed]},
        {"key": "whatsapp_connected", "label": "WhatsApp Connected", "count": len(whatsapp_connected), "tenants": [{"id": t["id"], "name": t.get("name"), "owner_email": t.get("owner_email")} for t in whatsapp_connected]},
        {"key": "first_lead", "label": "First Lead Created", "count": len(first_lead), "tenants": [{"id": t["id"], "name": t.get("name"), "owner_email": t.get("owner_email")} for t in first_lead]},
        {"key": "converted", "label": "Converted to Paid", "count": len(converted), "tenants": [{"id": t["id"], "name": t.get("name"), "owner_email": t.get("owner_email")} for t in converted]},
    ]

    # Trials expiring soon (≤3 days)
    soon_cutoff = _iso(now + timedelta(days=3))
    expiring = list(subs_col.find({
        "plan": "trial",
        "current_period_end": {"$lte": soon_cutoff, "$gte": _iso(now)},
    }, {"_id": 0}).sort("current_period_end", 1).limit(50))
    for s in expiring:
        t = tenants_col.find_one({"id": s["tenant_id"]}, {"_id": 0}) or {}
        s["onboarding_completed"] = bool(t.get("onboarding_completed"))
        oc = db["onboarding_config"].find_one({"tenant_id": s["tenant_id"]}, {"_id": 0}) or {}
        s["whatsapp_connected"] = bool(oc.get("whatsapp_api_key"))
        s["lead_count"] = leads_col.count_documents({"tenant_id": s["tenant_id"]})

    return {"stages": stages, "expiring_soon": expiring}


# ─── Endpoints: Invoice PDF ─────────────────────────────────────────────────
@invoice_router.get("/{payment_id}/pdf")
async def invoice_pdf(payment_id: str, current_user: dict = Depends(get_current_user)):
    _require_master_admin(current_user)
    p = payments_col.find_one({"id": payment_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")
    pdf_bytes = _render_invoice_pdf(p)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={p.get('invoice_number', payment_id)}.pdf"},
    )


def _render_invoice_pdf(payment: dict) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import cm
    from reportlab.lib.colors import HexColor

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    # Brand header
    c.setFillColor(HexColor("#1A0A2E"))
    c.rect(0, h - 3 * cm, w, 3 * cm, fill=1, stroke=0)
    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont("Helvetica-Bold", 22)
    c.drawString(2 * cm, h - 1.8 * cm, "GenLeadAI")
    c.setFont("Helvetica", 10)
    c.drawString(2 * cm, h - 2.3 * cm, COMPANY["product"])
    c.setFont("Helvetica-Bold", 18)
    c.drawRightString(w - 2 * cm, h - 1.8 * cm, "TAX INVOICE")
    c.setFont("Helvetica", 9)
    c.drawRightString(w - 2 * cm, h - 2.3 * cm, payment.get("invoice_number", "—"))

    # Company block
    y = h - 4 * cm
    c.setFillColor(HexColor("#1A0A2E"))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(2 * cm, y, "From")
    c.setFont("Helvetica", 9)
    c.drawString(2 * cm, y - 0.5 * cm, COMPANY["name"])
    c.drawString(2 * cm, y - 1.0 * cm, COMPANY["address_line1"])
    c.drawString(2 * cm, y - 1.5 * cm, f"GSTIN: {COMPANY['gstin']}")
    c.drawString(2 * cm, y - 2.0 * cm, COMPANY["email"])

    # Bill to
    c.setFont("Helvetica-Bold", 9)
    c.drawString(11 * cm, y, "Bill To")
    c.setFont("Helvetica", 9)
    c.drawString(11 * cm, y - 0.5 * cm, payment.get("tenant_name") or "—")
    c.drawString(11 * cm, y - 1.0 * cm, payment.get("owner_email") or "—")

    # Meta block
    y -= 3 * cm
    c.setFillColor(HexColor("#F4F0FF"))
    c.rect(2 * cm, y - 0.2 * cm, w - 4 * cm, 1.4 * cm, fill=1, stroke=0)
    c.setFillColor(HexColor("#1A0A2E"))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(2.2 * cm, y + 0.9 * cm, "INVOICE DATE")
    c.drawString(7 * cm, y + 0.9 * cm, "PAYMENT METHOD")
    c.drawString(12 * cm, y + 0.9 * cm, "REFERENCE")
    c.drawString(17 * cm, y + 0.9 * cm, "STATUS")
    c.setFont("Helvetica", 10)
    dt = _parse(payment.get("paid_at")) or _now()
    c.drawString(2.2 * cm, y + 0.3 * cm, dt.strftime("%d %b %Y"))
    c.drawString(7 * cm, y + 0.3 * cm, str(payment.get("method", "—")).title())
    c.drawString(12 * cm, y + 0.3 * cm, payment.get("reference_number") or "—")
    c.drawString(17 * cm, y + 0.3 * cm, "PAID")

    # Table header
    y -= 2 * cm
    c.setFillColor(HexColor("#7C35DC"))
    c.rect(2 * cm, y, w - 4 * cm, 0.8 * cm, fill=1, stroke=0)
    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(2.2 * cm, y + 0.25 * cm, "DESCRIPTION")
    c.drawRightString(w - 2.2 * cm, y + 0.25 * cm, "AMOUNT (INR)")

    # Line item
    plan_name = (payment.get("plan") or "").upper()
    line = f"Aria by GenLeadAI — {plan_name} Plan — {dt.strftime('%B %Y')}"
    base = float(payment.get("amount", 0))
    gst_part = round(base - (base / (1 + GST_RATE)), 2)
    net = round(base - gst_part, 2)

    y -= 0.5 * cm
    c.setFillColor(HexColor("#1A0A2E"))
    c.setFont("Helvetica", 10)
    c.drawString(2.2 * cm, y - 0.3 * cm, line)
    c.drawRightString(w - 2.2 * cm, y - 0.3 * cm, f"{net:,.2f}")

    # Totals block
    y -= 2 * cm
    c.setFont("Helvetica", 9)
    c.drawRightString(w - 5 * cm, y, "Subtotal")
    c.drawRightString(w - 2.2 * cm, y, f"{net:,.2f}")
    c.drawRightString(w - 5 * cm, y - 0.5 * cm, f"GST @ {int(GST_RATE * 100)}%")
    c.drawRightString(w - 2.2 * cm, y - 0.5 * cm, f"{gst_part:,.2f}")
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(w - 5 * cm, y - 1.3 * cm, "TOTAL")
    c.drawRightString(w - 2.2 * cm, y - 1.3 * cm, f"INR {base:,.2f}")

    # Footer
    c.setFillColor(HexColor("#9B8AB0"))
    c.setFont("Helvetica", 8)
    c.drawString(2 * cm, 1.5 * cm, "This is a computer-generated invoice. No signature required.")
    c.drawString(2 * cm, 1.1 * cm, f"For queries: {COMPANY['email']}")
    c.drawRightString(w - 2 * cm, 1.5 * cm, "Page 1 of 1")

    c.showPage()
    c.save()
    return buf.getvalue()
