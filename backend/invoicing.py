"""GST invoice generator for plan upgrades — Iter 57.

What this does
--------------
1. PDF invoice (ReportLab) for every successful Stripe payment.
2. Splits the charge into base + GST (CGST/SGST 9%+9% intra-state OR IGST 18%
   inter-state — defaults to IGST since we don't know buyer's state yet).
3. Stores invoice metadata in `invoices` collection so Master Admin can list them.
4. Emails the PDF to the tenant owner via the existing `email_delivery` wrapper
   (so it inherits the test-mode safe-forwarding behaviour automatically).

This is called from `routes.billing_upgrade._apply_plan_change` after a payment
has been confirmed. Failure to generate or email an invoice MUST NOT block the
plan upgrade — failures are logged but swallowed.

Seller (us) defaults are read from env so you don't redeploy when your GST
number arrives:

  - GST_SELLER_NAME            (default "GenLeadAI Technologies Pvt Ltd")
  - GST_SELLER_GSTIN           (default empty — invoice still renders but flags it)
  - GST_SELLER_ADDRESS         (default placeholder)
  - GST_SELLER_STATE           (default "Karnataka")
  - GST_SELLER_STATE_CODE      (default "29")
  - GST_SELLER_EMAIL           (default falls back to SENDER_EMAIL)
"""
from __future__ import annotations

import io
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from deps import db
from email_delivery import send_email_safe

invoices_col = db["invoices"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _next_invoice_number() -> str:
    """Format: GLA/YYYY-YY/0001 — incremental per fiscal year."""
    now = _now()
    # Indian fiscal year = April→March
    fy_start = now.year if now.month >= 4 else now.year - 1
    fy = f"{fy_start}-{str(fy_start + 1)[2:]}"
    last = invoices_col.find_one({"fy": fy}, sort=[("seq", -1)])
    seq = int(last.get("seq", 0) if last else 0) + 1
    return f"GLA/{fy}/{seq:04d}", fy, seq


def _split_gst(total: float, is_inter_state: bool) -> Dict[str, float]:
    """Reverse-calculate base + GST from an inclusive total at 18%.

    Returns base, cgst, sgst, igst (whichever apply) so the sum equals total.
    """
    gst_rate = 0.18
    base = round(total / (1 + gst_rate), 2)
    gst_total = round(total - base, 2)
    if is_inter_state:
        return {"base": base, "cgst": 0.0, "sgst": 0.0, "igst": gst_total, "total": total}
    half = round(gst_total / 2, 2)
    # Re-balance rounding (cgst + sgst must equal gst_total)
    return {"base": base, "cgst": half, "sgst": gst_total - half, "igst": 0.0, "total": total}


def _build_pdf(invoice: Dict[str, Any]) -> bytes:
    """Render the invoice as a PDF and return the raw bytes."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"Invoice {invoice['invoice_no']}",
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=22, leading=26, textColor=colors.HexColor("#0F172A"))
    label = ParagraphStyle("lbl", parent=styles["BodyText"], fontSize=8, textColor=colors.HexColor("#64748B"))
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10, leading=14)

    elements = []
    # Header band
    elements.append(Paragraph("<font color='#7C35DC'><b>GenLeadAI</b></font>", h1))
    elements.append(Paragraph("Tax Invoice — under Rule 46 of CGST Rules, 2017", label))
    elements.append(Spacer(1, 14))

    # Seller + buyer block
    seller_lines = [
        f"<b>{invoice['seller_name']}</b>",
        invoice.get("seller_address") or "",
        f"State: {invoice.get('seller_state','')}  (Code: {invoice.get('seller_state_code','')})",
        f"GSTIN: {invoice.get('seller_gstin') or '— not registered —'}",
        f"Email: {invoice.get('seller_email','')}",
    ]
    buyer_lines = [
        f"<b>{invoice.get('buyer_name','')}</b>",
        f"Workspace: {invoice.get('tenant_id','')}",
        f"Email: {invoice.get('buyer_email','')}",
        f"State: {invoice.get('buyer_state') or 'Not provided'}",
    ]
    meta_lines = [
        f"<b>Invoice No:</b> {invoice['invoice_no']}",
        f"<b>Date:</b> {invoice['issued_at_human']}",
        f"<b>Payment:</b> {invoice.get('payment_method','Stripe')}",
        f"<b>Stripe session:</b> {invoice.get('session_id','')}",
    ]
    head_tbl = Table(
        [[
            Paragraph("<br/>".join(seller_lines), body),
            Paragraph("<br/>".join(buyer_lines), body),
            Paragraph("<br/>".join(meta_lines), body),
        ]],
        colWidths=[60 * mm, 55 * mm, 55 * mm],
    )
    head_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F8FAFC")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(head_tbl)
    elements.append(Spacer(1, 14))

    # Line items
    line_rows = [["#", "Description", "HSN/SAC", "Qty", "Amount (₹)"]]
    line_rows.append([
        "1",
        Paragraph(invoice["item_description"], body),
        invoice.get("hsn_code", "998314"),    # software services
        "1",
        f"{invoice['base']:.2f}",
    ])
    line_tbl = Table(line_rows, colWidths=[10 * mm, 80 * mm, 24 * mm, 14 * mm, 40 * mm])
    line_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7C35DC")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(line_tbl)
    elements.append(Spacer(1, 8))

    # Totals
    tot_rows = [
        ["", "Subtotal (excl. GST)", f"₹ {invoice['base']:.2f}"],
    ]
    if invoice["igst"] > 0:
        tot_rows.append(["", "IGST @ 18%", f"₹ {invoice['igst']:.2f}"])
    else:
        tot_rows.append(["", "CGST @ 9%", f"₹ {invoice['cgst']:.2f}"])
        tot_rows.append(["", "SGST @ 9%", f"₹ {invoice['sgst']:.2f}"])
    tot_rows.append(["", "Total payable", f"₹ {invoice['total']:.2f}"])
    tot_tbl = Table(tot_rows, colWidths=[114 * mm, 38 * mm, 36 * mm])
    tot_tbl.setStyle(TableStyle([
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("BOX", (1, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
        ("INNERGRID", (1, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
        ("BACKGROUND", (1, -1), (-1, -1), colors.HexColor("#F8FAFC")),
        ("FONTNAME", (1, -1), (-1, -1), "Helvetica-Bold"),
        ("LEFTPADDING", (1, 0), (-1, -1), 8),
        ("RIGHTPADDING", (1, 0), (-1, -1), 8),
        ("TOPPADDING", (1, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (1, 0), (-1, -1), 6),
    ]))
    elements.append(tot_tbl)
    elements.append(Spacer(1, 22))

    # Footer
    elements.append(Paragraph(
        "This is a system-generated invoice. No signature required. "
        "All charges are inclusive of applicable taxes. "
        "For invoice corrections, write to <b>support@genleadai.com</b> within 7 days of issue.",
        label,
    ))

    doc.build(elements)
    return buf.getvalue()


def issue_invoice_for_transaction(tx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Idempotent — generate the invoice + email the PDF for a tx row.

    Returns the saved invoice dict, or None if invoicing failed (caller swallows).
    """
    try:
        # Already invoiced?
        existing = invoices_col.find_one({"session_id": tx.get("session_id")})
        if existing:
            return {k: v for k, v in existing.items() if k != "_id"}

        # Seller info from env
        seller_state_code = os.getenv("GST_SELLER_STATE_CODE", "29")
        # Lookup buyer info
        tenant = db["tenants"].find_one({"id": tx["tenant_id"]}, {"_id": 0}) or {}
        buyer_state = (tenant.get("settings", {}) or {}).get("billing_state") or tenant.get("state")
        # If buyer didn't disclose state OR state != seller state → IGST
        is_inter_state = not buyer_state or buyer_state.lower() != os.getenv("GST_SELLER_STATE", "Karnataka").lower()

        split = _split_gst(float(tx["amount"]), is_inter_state=is_inter_state)
        invoice_no, fy, seq = _next_invoice_number()
        issued_at = _now()

        invoice = {
            "id": f"inv_{uuid.uuid4().hex[:12]}",
            "invoice_no": invoice_no,
            "fy": fy,
            "seq": seq,
            "tenant_id": tx["tenant_id"],
            "session_id": tx.get("session_id"),
            "tx_id": tx.get("id"),
            "buyer_name": tenant.get("name") or "Customer",
            "buyer_email": tx.get("user_email") or "",
            "buyer_state": buyer_state or "",
            "seller_name": os.getenv("GST_SELLER_NAME", "GenLeadAI Technologies Pvt Ltd"),
            "seller_address": os.getenv("GST_SELLER_ADDRESS", "Bengaluru, Karnataka, India"),
            "seller_state": os.getenv("GST_SELLER_STATE", "Karnataka"),
            "seller_state_code": seller_state_code,
            "seller_gstin": os.getenv("GST_SELLER_GSTIN") or "",
            "seller_email": os.getenv("GST_SELLER_EMAIL") or os.getenv("SENDER_EMAIL") or "billing@genleadai.com",
            "item_description": f"Subscription — {tx.get('plan_target', '').upper()} plan (monthly)",
            "hsn_code": "998314",
            "currency": tx.get("currency", "inr").upper(),
            "payment_method": "Stripe Checkout",
            **split,
            "issued_at": issued_at.isoformat(),
            "issued_at_human": issued_at.strftime("%d %b %Y, %H:%M IST"),
        }
        pdf = _build_pdf(invoice)
        invoice["pdf_bytes_count"] = len(pdf)
        invoices_col.insert_one(invoice)

        # Email to buyer (test-mode safe via email_delivery wrapper)
        to_email = invoice["buyer_email"]
        if to_email:
            html = (
                f"<p>Hi,</p>"
                f"<p>Thanks for upgrading to the <b>{tx.get('plan_target', '').upper()}</b> plan on GenLeadAI.</p>"
                f"<p>Your tax invoice <b>{invoice['invoice_no']}</b> is attached as a PDF. "
                f"Total: <b>₹ {invoice['total']:.2f}</b> (inclusive of GST).</p>"
                f"<p>Reply to this email if you need anything corrected within 7 days.</p>"
                f"<p>— GenLeadAI Billing</p>"
            )
            send_email_safe(
                to_email=to_email,
                subject=f"Tax Invoice {invoice['invoice_no']} — GenLeadAI",
                html=html,
                purpose="invoice",
                attachments=[{
                    "filename": f"{invoice['invoice_no'].replace('/', '-')}.pdf",
                    "content": pdf,
                }],
            )
        return {k: v for k, v in invoice.items() if k != "_id"}
    except Exception as e:
        print(f"[invoice] generation failed for tx {tx.get('id')}: {e}")
        return None
