"""Billing profile, seller GST profile, CSV export & production-readiness — Iter 58.

Three concerns, one file because they all support the invoicing loop:

1. Tenant billing info (per-workspace, owner/admin editable):
   - billing_state (drives intra-state CGST+SGST vs IGST)
   - billing_gstin (buyer's GSTIN — shown on invoice)
   - billing_email (override for invoice-recipient email)
   - billing_address (free-text)
   Stored on `tenants.settings.billing`.

2. Seller GST profile (platform-wide, master admin only):
   - DB-stored on `platform_config` with key=`seller_profile`.
   - Overrides env so the GST registration can be added later without redeploy.
   - Slack webhook for founder upgrade notifications also lives here.

3. Production-readiness panel (master admin):
   - Reports green/yellow/red on Resend domain, Stripe mode, GST seller info,
     Slack webhook. Used to gate "is this thing ready to launch" decisions.

4. Bulk CSV export of invoices for the tenant's accountant.
"""
from __future__ import annotations

import csv
import io
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from deps import db, get_current_user
from routes.tenants import get_active_tenant

router = APIRouter(prefix="/api", tags=["billing-profile"])

tenants_col = db["tenants"]
invoices_col = db["invoices"]
platform_config_col = db["platform_config"]
email_log_col = db["email_delivery_log"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Helpers ────────────────────────────────────────────────────────────────
def get_seller_profile() -> dict:
    """Return effective seller profile = DB override merged over env defaults."""
    env_default = {
        "seller_name": os.getenv("GST_SELLER_NAME", "GenLeadAI Technologies Pvt Ltd"),
        "seller_address": os.getenv("GST_SELLER_ADDRESS", "Bengaluru, Karnataka, India"),
        "seller_state": os.getenv("GST_SELLER_STATE", "Karnataka"),
        "seller_state_code": os.getenv("GST_SELLER_STATE_CODE", "29"),
        "seller_gstin": os.getenv("GST_SELLER_GSTIN", ""),
        "seller_email": os.getenv("GST_SELLER_EMAIL") or os.getenv("SENDER_EMAIL") or "billing@genleadai.com",
        "slack_webhook_url": "",
        "founder_notify_email": os.getenv("MASTER_ADMIN_EMAIL") or os.getenv("CONTACT_FORWARD_EMAIL") or "",
    }
    row = platform_config_col.find_one({"key": "seller_profile"}, {"_id": 0}) or {}
    overrides = {k: v for k, v in (row.get("value") or {}).items() if v}
    return {**env_default, **overrides}


def get_tenant_billing(tenant: dict) -> dict:
    return (tenant.get("settings") or {}).get("billing") or {}


# ─── Tenant billing info ────────────────────────────────────────────────────
class TenantBillingInfo(BaseModel):
    billing_state: Optional[str] = Field(default=None, max_length=80)
    billing_gstin: Optional[str] = Field(default=None, max_length=20)
    billing_email: Optional[str] = Field(default=None, max_length=160)
    billing_address: Optional[str] = Field(default=None, max_length=400)
    legal_name: Optional[str] = Field(default=None, max_length=160)


@router.get("/billing/tenant-info")
async def get_tenant_billing_info(tenant: dict = Depends(get_active_tenant)):
    return get_tenant_billing(tenant)


@router.put("/billing/tenant-info")
async def update_tenant_billing_info(
    payload: TenantBillingInfo,
    tenant: dict = Depends(get_active_tenant),
):
    role = tenant.get("_member_role")
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")

    clean = {k: (v.strip() if isinstance(v, str) else v) for k, v in payload.model_dump().items() if v is not None}
    tenants_col.update_one(
        {"id": tenant["id"]},
        {"$set": {**{f"settings.billing.{k}": v for k, v in clean.items()},
                  "settings.billing.updated_at": _now_iso()}},
    )
    return {"ok": True, "billing": clean}


# ─── Master Admin: seller GST profile + Slack webhook ───────────────────────
def _require_master_admin(user: dict):
    if (user.get("role") or "").lower() != "admin":
        raise HTTPException(status_code=403, detail="Master Admin only")


class SellerProfilePayload(BaseModel):
    seller_name: Optional[str] = Field(default=None, max_length=160)
    seller_address: Optional[str] = Field(default=None, max_length=400)
    seller_state: Optional[str] = Field(default=None, max_length=80)
    seller_state_code: Optional[str] = Field(default=None, max_length=4)
    seller_gstin: Optional[str] = Field(default=None, max_length=20)
    seller_email: Optional[str] = Field(default=None, max_length=160)
    slack_webhook_url: Optional[str] = Field(default=None, max_length=400)
    founder_notify_email: Optional[str] = Field(default=None, max_length=160)


@router.get("/admin/seller-profile")
async def admin_get_seller_profile(current_user: dict = Depends(get_current_user)):
    _require_master_admin(current_user)
    profile = get_seller_profile()
    # Mask the slack webhook so it doesn't leak in screen-shares
    if profile.get("slack_webhook_url"):
        url = profile["slack_webhook_url"]
        profile["slack_webhook_url_masked"] = url[:32] + "•••" + url[-6:] if len(url) > 40 else "•••"
    return profile


@router.put("/admin/seller-profile")
async def admin_update_seller_profile(
    payload: SellerProfilePayload,
    current_user: dict = Depends(get_current_user),
):
    _require_master_admin(current_user)
    clean = {k: (v.strip() if isinstance(v, str) else v) for k, v in payload.model_dump().items() if v is not None}
    platform_config_col.update_one(
        {"key": "seller_profile"},
        {"$set": {"value": clean, "updated_at": _now_iso(), "updated_by": current_user.get("email")}},
        upsert=True,
    )
    return {"ok": True, "profile": get_seller_profile()}


# ─── Production-readiness panel ─────────────────────────────────────────────
@router.get("/admin/production-readiness")
async def production_readiness(current_user: dict = Depends(get_current_user)):
    _require_master_admin(current_user)
    profile = get_seller_profile()
    stripe_key = os.getenv("STRIPE_API_KEY", "")
    sender = os.getenv("SENDER_EMAIL", "")
    resend_key = bool(os.getenv("RESEND_API_KEY"))

    # Look at the last 50 email log rows to detect test-mode forwarding
    last_rows = list(email_log_col.find({}, {"_id": 0}).sort("created_at", -1).limit(50))
    forwarded = sum(1 for r in last_rows if r.get("delivery_status") == "test_mode_forwarded")
    sent = sum(1 for r in last_rows if r.get("delivery_status") == "sent")
    resend_status = "green" if (resend_key and sent > 0 and forwarded == 0 and "resend.dev" not in sender) else (
        "yellow" if resend_key else "red"
    )
    resend_detail = (
        "Verified domain — emails landing in user inboxes." if resend_status == "green"
        else f"Test mode — {forwarded} email(s) forwarded to admin. Verify a domain at resend.com/domains."
        if resend_status == "yellow"
        else "RESEND_API_KEY not set."
    )

    is_live_stripe = stripe_key.startswith("sk_live_")
    stripe_status = "green" if is_live_stripe else ("yellow" if stripe_key else "red")
    stripe_detail = (
        "Live mode — real cards will be charged." if is_live_stripe
        else "Test mode — using sk_test_emergent. Switch to live key before launch."
        if stripe_key else "STRIPE_API_KEY not set."
    )

    has_gstin = bool(profile.get("seller_gstin"))
    gstin_status = "green" if has_gstin else "yellow"
    gstin_detail = (
        f"GSTIN registered: {profile['seller_gstin']}." if has_gstin
        else "GSTIN not filled — invoices render but flag '— not registered —'. Fill in Master Admin → Billing config."
    )

    has_slack = bool(profile.get("slack_webhook_url"))
    slack_status = "green" if has_slack else "yellow"
    slack_detail = (
        "Slack webhook configured — founder will get a ping on every payment." if has_slack
        else "Optional. Add a Slack incoming webhook to get a real-time 'cha-ching' on every upgrade."
    )

    has_founder_email = bool(profile.get("founder_notify_email"))

    checks = [
        {"key": "resend", "label": "Email deliverability (Resend)", "status": resend_status, "detail": resend_detail},
        {"key": "stripe", "label": "Payments (Stripe live mode)", "status": stripe_status, "detail": stripe_detail},
        {"key": "gstin", "label": "GST seller info", "status": gstin_status, "detail": gstin_detail},
        {"key": "founder_email", "label": "Founder notification email", "status": "green" if has_founder_email else "yellow",
         "detail": (f"Pinging {profile['founder_notify_email']} on every upgrade." if has_founder_email
                    else "Add a founder email to receive upgrade notifications with invoice PDFs.")},
        {"key": "slack", "label": "Slack upgrade webhook (optional)", "status": slack_status, "detail": slack_detail},
    ]

    # Roll up to a single overall light: red if any red, yellow if any yellow, else green
    statuses = [c["status"] for c in checks]
    overall = "red" if "red" in statuses else ("yellow" if "yellow" in statuses else "green")
    return {
        "overall": overall,
        "checks": checks,
        "generated_at": _now_iso(),
    }


# ─── Bulk invoice CSV export ────────────────────────────────────────────────
@router.get("/billing/invoices/export.csv")
async def export_invoices_csv(tenant: dict = Depends(get_active_tenant)):
    """Export all invoices for the current tenant as a CSV file (for the CA)."""
    role = tenant.get("_member_role")
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")
    rows = list(invoices_col.find({"tenant_id": tenant["id"]}, {"_id": 0}).sort("issued_at", -1))

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "Invoice No", "Date", "Buyer Name", "Buyer Email", "Buyer State", "Buyer GSTIN",
        "Description", "HSN", "Base (₹)", "CGST (₹)", "SGST (₹)", "IGST (₹)",
        "Total (₹)", "Currency", "Session ID", "Seller GSTIN",
    ])
    buyer_gstin_lookup = (get_tenant_billing(tenant) or {}).get("billing_gstin") or ""
    for r in rows:
        writer.writerow([
            r.get("invoice_no", ""), r.get("issued_at_human", ""),
            r.get("buyer_name", ""), r.get("buyer_email", ""),
            r.get("buyer_state", ""), buyer_gstin_lookup,
            r.get("item_description", ""), r.get("hsn_code", ""),
            f"{r.get('base', 0):.2f}", f"{r.get('cgst', 0):.2f}",
            f"{r.get('sgst', 0):.2f}", f"{r.get('igst', 0):.2f}",
            f"{r.get('total', 0):.2f}", r.get("currency", "INR"),
            r.get("session_id", ""), r.get("seller_gstin", ""),
        ])
    buf.seek(0)
    fname = f"genleadai-invoices-{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
