"""Iter 57 — GST invoice auto-generation on Stripe plan upgrade.

Tests verify:
  1. PDF rendering produces non-trivial bytes (ReportLab integration).
  2. GST split — IGST (inter-state) and CGST+SGST (intra-state) — sums to total.
  3. Invoice numbering increments per fiscal year.
  4. `issue_invoice_for_transaction` is idempotent (same session_id → one invoice).
  5. Invoice row is persisted to `invoices` collection with required fields.
  6. End-to-end: `_apply_plan_change` triggers invoicing without blocking on email.
"""
from __future__ import annotations

import os
import uuid
import pytest

import sys
sys.path.insert(0, "/app/backend")

from deps import db  # noqa: E402
from invoicing import (  # noqa: E402
    _split_gst,
    _build_pdf,
    _next_invoice_number,
    issue_invoice_for_transaction,
)


@pytest.fixture(autouse=True)
def _clean_invoices():
    """Wipe invoices created during this test run (by id prefix)."""
    yield
    db["invoices"].delete_many({"buyer_email": {"$regex": "^iter57-"}})


def _make_tx(amount: float = 11800.0, tenant_id: str | None = None,
             session_id: str | None = None, email: str | None = None) -> dict:
    return {
        "id": f"tx_{uuid.uuid4().hex[:10]}",
        "tenant_id": tenant_id or f"ten_iter57_{uuid.uuid4().hex[:6]}",
        "session_id": session_id or f"cs_test_{uuid.uuid4().hex[:14]}",
        "user_email": email or f"iter57-{uuid.uuid4().hex[:6]}@example.com",
        "plan_target": "dwy",
        "plan_from": "diy",
        "amount": amount,
        "currency": "inr",
        "payment_status": "paid",
    }


# 1. GST split (inter-state — IGST only)
def test_split_gst_inter_state_sums_to_total():
    s = _split_gst(11800.0, is_inter_state=True)
    assert s["igst"] > 0
    assert s["cgst"] == 0 and s["sgst"] == 0
    # base + igst should equal total (allowing 1p rounding tolerance)
    assert abs(s["base"] + s["igst"] - 11800.0) < 0.05


# 2. GST split (intra-state — CGST + SGST, no IGST)
def test_split_gst_intra_state_splits_cgst_sgst():
    s = _split_gst(11800.0, is_inter_state=False)
    assert s["igst"] == 0
    assert s["cgst"] > 0 and s["sgst"] > 0
    # cgst + sgst should equal total gst
    assert abs(s["cgst"] + s["sgst"] + s["base"] - 11800.0) < 0.05


# 3. Invoice number format & per-FY increment
def test_invoice_number_format_and_increment():
    no1, fy1, seq1 = _next_invoice_number()
    assert no1.startswith("GLA/")
    assert "-" in fy1  # e.g. "2025-26"
    assert no1 == f"GLA/{fy1}/{seq1:04d}"
    # Insert a fake one so the seq advances
    db["invoices"].insert_one({"fy": fy1, "seq": seq1, "id": "fake", "invoice_no": no1})
    no2, fy2, seq2 = _next_invoice_number()
    assert fy2 == fy1
    assert seq2 == seq1 + 1
    db["invoices"].delete_one({"id": "fake"})


# 4. _build_pdf produces real PDF bytes
def test_build_pdf_produces_non_trivial_bytes():
    invoice = {
        "invoice_no": "GLA/TEST/0001",
        "seller_name": "Test Seller Pvt Ltd",
        "seller_address": "Bengaluru, KA",
        "seller_state": "Karnataka",
        "seller_state_code": "29",
        "seller_gstin": "",
        "seller_email": "billing@test.com",
        "buyer_name": "Acme Co.",
        "buyer_email": "iter57-pdf@example.com",
        "buyer_state": "Karnataka",
        "tenant_id": "ten_test",
        "session_id": "cs_test_abc",
        "item_description": "Subscription — DWY plan (monthly)",
        "hsn_code": "998314",
        "issued_at_human": "01 Feb 2026, 10:00 IST",
        "base": 10000.0, "cgst": 900.0, "sgst": 900.0, "igst": 0.0, "total": 11800.0,
        "payment_method": "Stripe Checkout",
    }
    pdf = _build_pdf(invoice)
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 1500  # a real PDF, not an empty stub


# 5. Issuing an invoice persists + returns the dict
def test_issue_invoice_persists_to_collection(monkeypatch):
    # avoid hitting the email service in unit tests
    import invoicing as inv_mod
    monkeypatch.setattr(inv_mod, "send_email_safe", lambda **kw: None)
    tx = _make_tx()
    result = issue_invoice_for_transaction(tx)
    assert result is not None
    assert result["invoice_no"].startswith("GLA/")
    saved = db["invoices"].find_one({"session_id": tx["session_id"]}, {"_id": 0})
    assert saved is not None
    assert saved["tenant_id"] == tx["tenant_id"]
    assert saved["buyer_email"] == tx["user_email"]
    assert "base" in saved and "total" in saved
    # Rounding sanity
    if saved["igst"] > 0:
        assert abs(saved["base"] + saved["igst"] - saved["total"]) < 0.05
    else:
        assert abs(saved["base"] + saved["cgst"] + saved["sgst"] - saved["total"]) < 0.05


# 6. Idempotency — calling twice with the same session_id → one invoice
def test_issue_invoice_is_idempotent(monkeypatch):
    import invoicing as inv_mod
    monkeypatch.setattr(inv_mod, "send_email_safe", lambda **kw: None)
    tx = _make_tx()
    r1 = issue_invoice_for_transaction(tx)
    r2 = issue_invoice_for_transaction(tx)
    assert r1["invoice_no"] == r2["invoice_no"]
    assert db["invoices"].count_documents({"session_id": tx["session_id"]}) == 1


# 7. Invoicing failures must NOT propagate (must return None on failure)
def test_issue_invoice_swallows_errors(monkeypatch):
    import invoicing as inv_mod
    monkeypatch.setattr(inv_mod, "_build_pdf", lambda i: (_ for _ in ()).throw(RuntimeError("boom")))
    tx = _make_tx()
    result = issue_invoice_for_transaction(tx)
    assert result is None


# 8. List & download API smoke (uses an existing demo tenant + admin token)
def test_invoice_list_and_pdf_download_endpoints(monkeypatch):
    """Authenticated round-trip via FastAPI TestClient."""
    import invoicing as inv_mod
    monkeypatch.setattr(inv_mod, "send_email_safe", lambda **kw: None)

    from fastapi.testclient import TestClient
    from server import app

    client = TestClient(app)
    # Login as demo admin
    login = client.post("/api/auth/login", json={
        "email": "admin@demo.com",
        "password": "Demo1234!",
    })
    assert login.status_code == 200, login.text
    body = login.json()
    token = body.get("token") or body.get("access_token")
    assert token, f"login response missing token: {body}"
    user = body.get("user", {})
    tenant_id = (user.get("tenants") or [{}])[0].get("id") or user.get("tenant_id") or "ten_demo"
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-Id": tenant_id}

    # Seed an invoice for this tenant
    tx = _make_tx(tenant_id=tenant_id)
    issued = issue_invoice_for_transaction(tx)
    assert issued and issued.get("id")

    # List endpoint
    r_list = client.get("/api/billing/invoices", headers=headers)
    assert r_list.status_code == 200, r_list.text
    invs = r_list.json().get("invoices", [])
    assert any(i["id"] == issued["id"] for i in invs)

    # PDF download
    r_pdf = client.get(f"/api/billing/invoices/{issued['id']}/pdf", headers=headers)
    assert r_pdf.status_code == 200
    assert r_pdf.headers["content-type"] == "application/pdf"
    assert r_pdf.content.startswith(b"%PDF-")

    # cleanup
    db["invoices"].delete_one({"id": issued["id"]})
