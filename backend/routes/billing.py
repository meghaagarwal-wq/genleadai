"""Stripe Checkout billing routes for GenLeadAI Aria.

Tenant-aware subscription checkout using the Emergent Stripe integration.

Security invariants (from integration playbook):
- NEVER accept amount from the frontend; use fixed PACKAGES defined here.
- Success/cancel URLs are built from the caller's `origin_url`.
- A `payment_transactions` row is created BEFORE redirect, updated on poll.
- Tenant.plan is updated only after a confirmed 'paid' status, and only once
  per session_id (idempotent).
"""
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from deps import db, get_current_user

router = APIRouter(prefix="/api/billing", tags=["billing"])

# ─── Fixed pricing (backend-owned, frontend cannot override) ─────────────────
PACKAGES = {
    "starter": {
        "amount": 49.00,
        "currency": "usd",
        "plan": "starter",
        "label": "Starter",
        "description": "Starter plan — 1 seat, unlimited leads, WhatsApp + Email",
    },
    "pro": {
        "amount": 149.00,
        "currency": "usd",
        "plan": "pro",
        "label": "Pro",
        "description": "Pro plan — 5 seats, automations, reports, team roles",
    },
}

# ─── Collections ─────────────────────────────────────────────────────────────
tenants_col = db["tenants"]
payments_col = db["payment_transactions"]


# ─── Models ──────────────────────────────────────────────────────────────────
class CheckoutCreatePayload(BaseModel):
    package_id: str = Field(..., description="Must be one of PACKAGES keys")
    origin_url: str = Field(..., description="Frontend origin — used for success/cancel URLs")


# ─── Helpers ─────────────────────────────────────────────────────────────────
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stripe_client(request: Request):
    from emergentintegrations.payments.stripe.checkout import StripeCheckout
    api_key = os.environ.get("STRIPE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="STRIPE_API_KEY not configured")
    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    return StripeCheckout(api_key=api_key, webhook_url=webhook_url)


def _active_tenant_id(current_user: dict) -> str:
    tid = current_user.get("tenant_id")
    if not tid:
        raise HTTPException(status_code=403, detail="No active tenant")
    return tid


# ─── Endpoints ───────────────────────────────────────────────────────────────
@router.get("/packages")
async def list_packages():
    """Public list of purchasable plans + pricing — the frontend uses this
    to render the /billing page comparison table."""
    return {
        "packages": [
            {"id": pid, **{k: v for k, v in pkg.items() if k != "plan"}}
            for pid, pkg in PACKAGES.items()
        ]
    }


@router.post("/checkout")
async def create_checkout(
    payload: CheckoutCreatePayload,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Create a Stripe Checkout session for the active tenant.

    The amount is **server-owned** — payload only carries package_id + origin.
    Emits a pending `payment_transactions` row for later reconciliation.
    """
    pkg = PACKAGES.get(payload.package_id)
    if not pkg:
        raise HTTPException(status_code=400, detail="Invalid package")

    tenant_id = _active_tenant_id(current_user)
    origin = payload.origin_url.rstrip("/")

    # Build redirect URLs with the CHECKOUT_SESSION_ID placeholder so Stripe
    # injects the session id back when we poll /billing/status/{session_id}.
    success_url = f"{origin}/billing?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/billing?cancelled=1"

    metadata = {
        "tenant_id": tenant_id,
        "package_id": payload.package_id,
        "plan": pkg["plan"],
        "user_email": current_user["email"],
        "source": "app_billing_page",
    }

    from emergentintegrations.payments.stripe.checkout import CheckoutSessionRequest
    stripe_client = _stripe_client(request)
    checkout_req = CheckoutSessionRequest(
        amount=pkg["amount"],
        currency=pkg["currency"],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
    )
    session = await stripe_client.create_checkout_session(checkout_req)

    # Persist pending transaction BEFORE returning — so the webhook/poll has a
    # row to update and we never double-grant a plan.
    payments_col.insert_one({
        "session_id": session.session_id,
        "tenant_id": tenant_id,
        "user_email": current_user["email"],
        "package_id": payload.package_id,
        "plan": pkg["plan"],
        "amount": pkg["amount"],
        "currency": pkg["currency"],
        "payment_status": "initiated",
        "status": "open",
        "metadata": metadata,
        "created_at": _now(),
        "updated_at": _now(),
    })
    return {"url": session.url, "session_id": session.session_id}


@router.get("/status/{session_id}")
async def checkout_status(
    session_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Poll checkout status. Idempotent — upgrades tenant.plan at most once
    per session_id, regardless of how many times this is called."""
    txn = payments_col.find_one({"session_id": session_id}, {"_id": 0})
    if not txn:
        raise HTTPException(status_code=404, detail="Session not found")
    # Cross-tenant guard: user can only query their own tenant's transactions.
    if txn.get("tenant_id") != current_user.get("tenant_id"):
        raise HTTPException(status_code=403, detail="Not your transaction")

    stripe_client = _stripe_client(request)
    # Work around an emergentintegrations 0.1.0 bug: `get_checkout_status`
    # fails pydantic validation when Stripe returns `metadata` as a StripeObject.
    # Fall back to the raw `stripe` SDK which handles it cleanly.
    try:
        status = await stripe_client.get_checkout_status(session_id)
        payment_status = status.payment_status
        session_status = status.status
        amount_total = status.amount_total
        currency = status.currency
    except Exception:
        import stripe as _stripe
        api_key = os.environ.get("STRIPE_API_KEY") or ""
        _stripe.api_key = api_key
        # Match emergentintegrations' base URL when the emergent test-pool key is used
        if "sk_test_emergent" in api_key:
            _stripe.api_base = "https://integrations.emergentagent.com/stripe"
        raw = _stripe.checkout.Session.retrieve(session_id)
        payment_status = getattr(raw, "payment_status", None)
        session_status = getattr(raw, "status", None)
        amount_total = getattr(raw, "amount_total", None)
        currency = getattr(raw, "currency", None)

    # Only act on state transitions; avoid re-granting the plan.
    was_paid = txn.get("payment_status") == "paid"
    is_paid_now = payment_status == "paid"

    update = {
        "payment_status": payment_status,
        "status": session_status,
        "amount_total": amount_total,
        "currency": currency,
        "updated_at": _now(),
    }
    payments_col.update_one({"session_id": session_id}, {"$set": update})

    if is_paid_now and not was_paid:
        # Grant the plan exactly once
        tenants_col.update_one(
            {"id": txn["tenant_id"]},
            {"$set": {
                "plan": txn["plan"],
                "plan_activated_at": _now(),
                "updated_at": _now(),
            }},
        )
        payments_col.update_one(
            {"session_id": session_id},
            {"$set": {"plan_granted_at": _now()}},
        )

    return {
        "session_id": session_id,
        "payment_status": payment_status,
        "status": session_status,
        "amount_total": amount_total,
        "currency": currency,
        "plan": txn["plan"],
        "plan_granted": is_paid_now,
    }


# ─── Webhook (public, no auth) ───────────────────────────────────────────────
webhook_router = APIRouter(tags=["billing-webhook"])


@webhook_router.post("/api/webhook/stripe")
async def stripe_webhook(request: Request):
    """Public Stripe webhook endpoint. Verifies signature via the emergent
    integration and upgrades tenant.plan idempotently.

    Not under /api/billing to match the standard Stripe webhook convention.
    """
    from emergentintegrations.payments.stripe.checkout import StripeCheckout
    api_key = os.environ.get("STRIPE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="STRIPE_API_KEY not configured")

    body = await request.body()
    sig = request.headers.get("Stripe-Signature")
    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"

    stripe_client = StripeCheckout(api_key=api_key, webhook_url=webhook_url)
    event = await stripe_client.handle_webhook(body, sig)

    session_id = getattr(event, "session_id", None)
    payment_status = getattr(event, "payment_status", None)

    if not session_id:
        return {"received": True, "handled": False}

    txn = payments_col.find_one({"session_id": session_id})
    if not txn:
        # Unknown session — likely test fire or stale — ack to avoid retries
        return {"received": True, "unknown_session": True}

    already_granted = txn.get("plan_granted_at") is not None

    payments_col.update_one(
        {"session_id": session_id},
        {"$set": {
            "payment_status": payment_status or txn.get("payment_status"),
            "last_webhook_event_id": getattr(event, "event_id", None),
            "last_webhook_event_type": getattr(event, "event_type", None),
            "updated_at": _now(),
        }},
    )

    if payment_status == "paid" and not already_granted:
        tenants_col.update_one(
            {"id": txn["tenant_id"]},
            {"$set": {
                "plan": txn["plan"],
                "plan_activated_at": _now(),
                "updated_at": _now(),
            }},
        )
        payments_col.update_one(
            {"session_id": session_id},
            {"$set": {"plan_granted_at": _now()}},
        )

    return {"received": True, "handled": True}
