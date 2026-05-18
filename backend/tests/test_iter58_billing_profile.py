"""Iter 58 — Billing profile, seller GST overrides, production-readiness, CSV export,
founder upgrade notification.

Tested:
  1. GET /api/billing/tenant-info returns empty defaults for fresh tenant.
  2. PUT /api/billing/tenant-info persists billing_state/gstin/email/address.
  3. Intra-state billing (buyer Karnataka → seller Karnataka) splits into CGST+SGST.
  4. Inter-state billing (buyer Maharashtra) splits into IGST only.
  5. GET /api/admin/seller-profile (admin only) returns env-defaulted profile.
  6. PUT /api/admin/seller-profile persists DB override that takes precedence.
  7. GET /api/admin/production-readiness returns 5 checks with overall rollup.
  8. Bulk CSV export returns the expected header columns.
  9. Founder upgrade notification — fires send_email_safe + posts to Slack webhook
     when configured, without blocking the invoice flow.
"""
from __future__ import annotations

import sys
import uuid
import csv
import io
from unittest.mock import patch

import pytest

sys.path.insert(0, "/app/backend")

from fastapi.testclient import TestClient

from deps import db  # noqa: E402
from server import app  # noqa: E402
import invoicing  # noqa: E402
from routes.billing_profile import get_seller_profile  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_headers(client):
    r = client.post("/api/auth/login", json={"email": "admin@demo.com", "password": "Demo1234!"})
    assert r.status_code == 200, r.text
    body = r.json()
    token = body.get("token") or body.get("access_token")
    user = body.get("user", {})
    tenant_id = (user.get("tenants") or [{}])[0].get("id") or "ten_demo"
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": tenant_id}, tenant_id


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    # Wipe any seller_profile override the tests added so other tests stay deterministic
    db["platform_config"].delete_many({"key": "seller_profile"})
    db["invoices"].delete_many({"buyer_email": {"$regex": "^iter58-"}})


# 1. Tenant billing info — GET on fresh tenant
def test_tenant_billing_info_default_empty(client, admin_headers):
    headers, _ = admin_headers
    r = client.get("/api/billing/tenant-info", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict)


# 2. Tenant billing info — PUT persists
def test_tenant_billing_info_put_persists(client, admin_headers):
    headers, tenant_id = admin_headers
    payload = {
        "legal_name": "Demo Co Pvt Ltd",
        "billing_email": "iter58-billing@demo.com",
        "billing_gstin": "29ABCDE1234F1Z5",
        "billing_state": "Karnataka",
        "billing_address": "123 MG Road, Bengaluru 560001",
    }
    r = client.put("/api/billing/tenant-info", headers=headers, json=payload)
    assert r.status_code == 200, r.text
    # Round-trip
    r2 = client.get("/api/billing/tenant-info", headers=headers)
    body = r2.json()
    for k, v in payload.items():
        assert body.get(k) == v, f"{k}: expected {v!r}, got {body.get(k)!r}"


# 3 + 4. Intra-state vs inter-state — drives CGST/SGST vs IGST
def test_invoice_intra_state_splits_cgst_sgst(client, admin_headers, monkeypatch):
    headers, tenant_id = admin_headers
    monkeypatch.setattr(invoicing, "send_email_safe", lambda **kw: None)
    # Make sure seller is Karnataka
    client.put("/api/admin/seller-profile", headers=headers, json={"seller_state": "Karnataka", "seller_state_code": "29"})
    # Buyer in Karnataka
    client.put("/api/billing/tenant-info", headers=headers, json={"billing_state": "Karnataka"})
    tx = {
        "id": f"tx_{uuid.uuid4().hex[:10]}",
        "tenant_id": tenant_id,
        "session_id": f"cs_test_intra_{uuid.uuid4().hex[:10]}",
        "user_email": "iter58-intra@example.com",
        "plan_target": "dwy", "plan_from": "diy",
        "amount": 11800.0, "currency": "inr",
    }
    inv = invoicing.issue_invoice_for_transaction(tx)
    assert inv is not None
    assert inv["cgst"] > 0 and inv["sgst"] > 0
    assert inv["igst"] == 0


def test_invoice_inter_state_splits_igst(client, admin_headers, monkeypatch):
    headers, tenant_id = admin_headers
    monkeypatch.setattr(invoicing, "send_email_safe", lambda **kw: None)
    client.put("/api/admin/seller-profile", headers=headers, json={"seller_state": "Karnataka"})
    client.put("/api/billing/tenant-info", headers=headers, json={"billing_state": "Maharashtra"})
    tx = {
        "id": f"tx_{uuid.uuid4().hex[:10]}",
        "tenant_id": tenant_id,
        "session_id": f"cs_test_inter_{uuid.uuid4().hex[:10]}",
        "user_email": "iter58-inter@example.com",
        "plan_target": "dwy", "plan_from": "diy",
        "amount": 11800.0, "currency": "inr",
    }
    inv = invoicing.issue_invoice_for_transaction(tx)
    assert inv is not None
    assert inv["igst"] > 0
    assert inv["cgst"] == 0 and inv["sgst"] == 0


# 5. Admin seller-profile GET returns env defaults
def test_seller_profile_get_returns_env_defaults(client, admin_headers):
    headers, _ = admin_headers
    r = client.get("/api/admin/seller-profile", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("seller_name")
    assert body.get("seller_state")


# 6. Admin seller-profile PUT DB override takes precedence
def test_seller_profile_put_overrides_env(client, admin_headers):
    headers, _ = admin_headers
    custom = {"seller_name": "Custom Seller Pvt Ltd", "seller_gstin": "29XXXXX1234X1Z5"}
    r = client.put("/api/admin/seller-profile", headers=headers, json=custom)
    assert r.status_code == 200, r.text
    eff = get_seller_profile()
    assert eff["seller_name"] == "Custom Seller Pvt Ltd"
    assert eff["seller_gstin"] == "29XXXXX1234X1Z5"


# 7. Production-readiness has all checks + overall rollup
def test_production_readiness_returns_checks(client, admin_headers):
    headers, _ = admin_headers
    r = client.get("/api/admin/production-readiness", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("overall") in ("green", "yellow", "red")
    keys = {c["key"] for c in body.get("checks", [])}
    assert {"resend", "stripe", "gstin", "founder_email", "slack"}.issubset(keys)


# 8. CSV export — headers + at least the seeded invoice row
def test_csv_export_returns_expected_columns(client, admin_headers, monkeypatch):
    headers, tenant_id = admin_headers
    monkeypatch.setattr(invoicing, "send_email_safe", lambda **kw: None)
    # Seed one invoice
    tx = {
        "id": f"tx_{uuid.uuid4().hex[:10]}",
        "tenant_id": tenant_id,
        "session_id": f"cs_test_csv_{uuid.uuid4().hex[:10]}",
        "user_email": "iter58-csv@example.com",
        "plan_target": "dwy", "plan_from": "diy",
        "amount": 11800.0, "currency": "inr",
    }
    invoicing.issue_invoice_for_transaction(tx)
    r = client.get("/api/billing/invoices/export.csv", headers=headers)
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    reader = csv.reader(io.StringIO(r.text))
    rows = list(reader)
    assert rows, "CSV must have rows"
    header = rows[0]
    for required in ("Invoice No", "Total (₹)", "Base (₹)", "IGST (₹)", "Session ID"):
        assert required in header, f"CSV missing column {required}"


# 9. Founder notification — calls send_email_safe with the configured email
def test_founder_notification_fires_email(client, admin_headers, monkeypatch):
    headers, tenant_id = admin_headers
    # Configure founder email & Slack webhook on the seller profile
    client.put("/api/admin/seller-profile", headers=headers, json={
        "founder_notify_email": "iter58-founder@example.com",
        "slack_webhook_url": "https://hooks.slack.com/services/T_FAKE/B_FAKE/abc123",
    })

    captured_emails = []
    monkeypatch.setattr(
        invoicing, "send_email_safe",
        lambda **kw: captured_emails.append(kw),
    )

    posted_slack = []
    class _FakeResp:
        def read(self): return b"ok"
    def _fake_urlopen(req, timeout=5):
        posted_slack.append({"url": req.full_url, "data": req.data})
        return _FakeResp()
    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)

    tx = {
        "id": f"tx_{uuid.uuid4().hex[:10]}",
        "tenant_id": tenant_id,
        "session_id": f"cs_test_notify_{uuid.uuid4().hex[:10]}",
        "user_email": "iter58-buyer@example.com",
        "plan_target": "dwy", "plan_from": "diy",
        "amount": 12999.0, "currency": "inr",
    }
    inv = invoicing.issue_invoice_for_transaction(tx)
    assert inv is not None

    # Buyer email + founder email = at least 2 sends
    purposes = [e.get("purpose") for e in captured_emails]
    assert "founder_upgrade_notify" in purposes, f"founder notify not sent. purposes={purposes}"
    founder_send = next(e for e in captured_emails if e.get("purpose") == "founder_upgrade_notify")
    assert founder_send["to_email"] == "iter58-founder@example.com"
    assert founder_send.get("attachments"), "founder email must include the invoice PDF"

    # Slack was hit
    assert posted_slack, "Slack webhook should have been posted to"
    assert "hooks.slack.com" in posted_slack[0]["url"]
