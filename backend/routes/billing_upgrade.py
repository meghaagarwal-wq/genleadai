"""Plan upgrade via Stripe Checkout — Iter 56.

Wires the tier_limit_reached banner (and any other "upgrade" CTA) to a
Stripe-hosted checkout session. Backend defines the price catalog (so the
frontend can never tamper with the amount). Webhook + status-polling both
land here; whichever fires first flips the tenant's `plan` field.

Endpoints:
  POST /api/billing/checkout/session    — create session, returns {url}
  GET  /api/billing/checkout/status/{session_id} — poll status (used by success page)
  POST /api/webhook/stripe              — Stripe webhook receiver
  GET  /api/billing/packages            — public price catalog for the upgrade modal

Collection: `payment_transactions`
  - id, tenant_id, user_email, session_id, plan_target, amount, currency,
    metadata, payment_status ('initiated'|'paid'|'failed'|'expired'),
    plan_applied (bool), created_at, updated_at
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from deps import db
from routes.tenants import get_active_tenant
from routes.auth import get_current_user

from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout, CheckoutSessionRequest,
)

router = APIRouter(tags=["billing-upgrade"])

tx_col = db["payment_transactions"]
tenants_col = db["tenants"]


# ─── Server-side price catalog (never trust the frontend) ────────────────────
# Amounts in INR (paise are not used here — Stripe accepts decimal float).
PACKAGES: Dict[str, Dict[str, Any]] = {
    "diy_to_dwy": {
        "plan_target": "dwy",
        "amount": 12999.0,
        "currency": "inr",
        "label": "Upgrade to DWY (Done With You)",
        "description": "Unlimited ICPs · Multi-channel automation · Priority support",
    },
    "diy_to_dfy": {
        "plan_target": "dfy",
        "amount": 29999.0,
        "currency": "inr",
        "label": "Upgrade to DFY (Done For You)",
        "description": "Everything in DWY + dedicated success manager + custom integrations",
    },
    "dwy_to_dfy": {
        "plan_target": "dfy",
        "amount": 17000.0,
        "currency": "inr",
        "label": "Upgrade to DFY (Done For You)",
        "description": "Top-up from DWY: dedicated success manager + custom integrations",
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return f"tx_{uuid.uuid4().hex[:14]}"


def _stripe_client(request: Request) -> StripeCheckout:
    api_key = os.getenv("STRIPE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Stripe is not configured")
    host = str(request.base_url).rstrip("/")
    webhook_url = f"{host}/api/webhook/stripe"
    return StripeCheckout(api_key=api_key, webhook_url=webhook_url)


def _apply_plan_change(tx: dict) -> None:
    """Idempotent — apply plan change exactly once per transaction."""
    if tx.get("plan_applied"):
        return
    tenants_col.update_one(
        {"id": tx["tenant_id"]},
        {"$set": {"plan": tx["plan_target"], "plan_updated_at": _now_iso()}},
    )
    tx_col.update_one(
        {"_id": tx["_id"]},
        {"$set": {"plan_applied": True, "plan_applied_at": _now_iso()}},
    )
    # Audit
    db["audit_log"].insert_one({
        "tenant_id": tx["tenant_id"],
        "action": "plan_upgraded_via_stripe",
        "admin_email": tx.get("user_email"),
        "timestamp": _now_iso(),
        "details": {
            "from": tx.get("plan_from"),
            "to": tx["plan_target"],
            "amount": tx["amount"],
            "currency": tx["currency"],
            "session_id": tx["session_id"],
        },
    })


# ─── Public catalog ──────────────────────────────────────────────────────────
@router.get("/api/billing/upgrade-packages")
async def list_packages():
    """Server-side price catalog for the plan-upgrade modal."""
    return {"packages": {k: {**{kk: vv for kk, vv in v.items() if kk != "plan_target"}, "plan_target": v["plan_target"], "package_id": k}
                          for k, v in PACKAGES.items()}}


# ─── Create checkout session ─────────────────────────────────────────────────
class CheckoutRequest(BaseModel):
    package_id: str
    origin_url: str   # provided by frontend via window.location.origin


@router.post("/api/billing/checkout/session")
async def create_session(
    payload: CheckoutRequest,
    request: Request,
    tenant: dict = Depends(get_active_tenant),
    current_user: dict = Depends(get_current_user),
):
    """Create a Stripe Checkout session for the given package.

    Errors:
      - 400 invalid_package
      - 403 already_on_target_plan or higher
    """
    role = tenant.get("_member_role")
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")

    pkg = PACKAGES.get(payload.package_id)
    if not pkg:
        raise HTTPException(status_code=400, detail="invalid_package")

    current_plan = (tenant.get("plan") or "trial").lower()
    if current_plan == pkg["plan_target"]:
        raise HTTPException(status_code=403, detail=f"already_on_{pkg['plan_target']}")

    # Build URLs from frontend origin (never hardcode)
    origin = payload.origin_url.rstrip("/")
    success_url = f"{origin}/billing/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/billing/cancel"

    stripe = _stripe_client(request)
    tx_id = _new_id()
    checkoutreq = CheckoutSessionRequest(
        amount=float(pkg["amount"]),
        currency=pkg["currency"],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "tx_id": tx_id,
            "tenant_id": tenant["id"],
            "user_email": current_user.get("email") or "",
            "package_id": payload.package_id,
            "plan_target": pkg["plan_target"],
            "plan_from": current_plan,
        },
    )
    session = await stripe.create_checkout_session(checkoutreq)

    tx_col.insert_one({
        "id": tx_id,
        "tenant_id": tenant["id"],
        "user_email": current_user.get("email"),
        "session_id": session.session_id,
        "package_id": payload.package_id,
        "plan_target": pkg["plan_target"],
        "plan_from": current_plan,
        "amount": float(pkg["amount"]),
        "currency": pkg["currency"],
        "payment_status": "initiated",
        "plan_applied": False,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "metadata": {"package_id": payload.package_id},
    })

    return {"url": session.url, "session_id": session.session_id, "tx_id": tx_id}


# ─── Poll status (called from success page) ──────────────────────────────────
@router.get("/api/billing/checkout/status/{session_id}")
async def get_status(session_id: str, request: Request):
    """Poll the Stripe session status. Idempotently flips plan once."""
    tx = tx_col.find_one({"session_id": session_id})
    if not tx:
        raise HTTPException(status_code=404, detail="transaction_not_found")

    stripe = _stripe_client(request)
    status_resp = await stripe.get_checkout_status(session_id)

    # Update tx state if changed
    new_status = "paid" if status_resp.payment_status == "paid" else (
        "expired" if status_resp.status == "expired" else tx.get("payment_status", "initiated")
    )
    if new_status != tx.get("payment_status"):
        tx_col.update_one(
            {"_id": tx["_id"]},
            {"$set": {"payment_status": new_status, "updated_at": _now_iso()}},
        )

    if new_status == "paid":
        _apply_plan_change(tx)

    return {
        "status": status_resp.status,
        "payment_status": status_resp.payment_status,
        "amount_total": status_resp.amount_total,
        "currency": status_resp.currency,
        "plan_target": tx["plan_target"],
        "plan_applied": tx_col.find_one({"_id": tx["_id"]}, {"plan_applied": 1}).get("plan_applied", False),
    }


# ─── Webhook (Stripe → us) ───────────────────────────────────────────────────
@router.post("/api/webhook/stripe")
async def stripe_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("Stripe-Signature", "")
    stripe = _stripe_client(request)
    try:
        event = await stripe.handle_webhook(body, signature)
    except Exception as e:
        # Don't 500 on signature errors — Stripe will retry; we just log.
        print(f"[stripe-webhook] signature/parse error: {e}")
        return {"received": False}

    # Only act on successful payments
    if event.payment_status == "paid" and event.session_id:
        tx = tx_col.find_one({"session_id": event.session_id})
        if tx:
            tx_col.update_one(
                {"_id": tx["_id"]},
                {"$set": {"payment_status": "paid", "updated_at": _now_iso()}},
            )
            _apply_plan_change(tx)
    return {"received": True, "event_type": event.event_type, "session_id": event.session_id}
