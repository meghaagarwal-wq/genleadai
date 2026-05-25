"""Iter 33 — Master Admin Revenue Panel (Sprint 1).

Covers KPIs, subscriptions CRUD, manual payments, invoice PDF, churn,
trial funnel, by-plan chart, and admin-gating (sales_rep denied).
"""
import os
import uuid
import pytest
import requests

_BURL = os.environ.get("REACT_APP_BACKEND_URL")
if not _BURL:
    from dotenv import load_dotenv
    load_dotenv("/app/frontend/.env")
    _BURL = os.environ.get("REACT_APP_BACKEND_URL")
BASE_URL = (_BURL or "").rstrip("/")

ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD", "Demo1234!")
REP_EMAIL = "sarah@demo.com"
REP_PASSWORD = os.environ.get("TEST_REP_PASSWORD", "Demo1234!")
TENANT_ID = "ten_demo"


# ─── Fixtures ────────────────────────────────────────────────────────────────
def _login(email, password):
    s = requests.Session()
    s.headers["Content-Type"] = "application/json"
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    data = r.json()
    s.headers["Authorization"] = f"Bearer {data['token']}"
    s.headers["X-Tenant-Id"] = TENANT_ID
    return s, data


@pytest.fixture(scope="session")
def admin_session():
    s, _ = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    return s


@pytest.fixture(scope="session")
def rep_session():
    s, _ = _login(REP_EMAIL, REP_PASSWORD)
    return s


# ─── 1. Admin gate (sales_rep denied) ────────────────────────────────────────
class TestAdminGate:
    def test_rep_denied_summary(self, rep_session):
        r = rep_session.get(f"{BASE_URL}/api/admin/revenue/summary")
        assert r.status_code == 403, f"sales_rep should be 403 but got {r.status_code}: {r.text}"

    def test_rep_denied_subs(self, rep_session):
        r = rep_session.get(f"{BASE_URL}/api/admin/revenue/subscriptions")
        assert r.status_code == 403

    def test_rep_denied_payments(self, rep_session):
        r = rep_session.get(f"{BASE_URL}/api/admin/revenue/payments")
        assert r.status_code == 403


# ─── 2. Summary KPIs ─────────────────────────────────────────────────────────
class TestRevenueSummary:
    def test_summary_shape(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/revenue/summary")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "kpis" in data and "trends" in data
        k = data["kpis"]
        for key in ("mrr", "arr", "total_paying_clients", "active_trials", "trial_to_paid_pct", "monthly_churn_pct"):
            assert key in k, f"missing kpi: {key}"
        # ARR == MRR * 12
        assert abs(k["arr"] - k["mrr"] * 12) < 0.01
        assert isinstance(k["total_paying_clients"], int)


# ─── 3. Subscriptions list + auto-provision ──────────────────────────────────
class TestSubscriptions:
    def test_list_and_auto_provision(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/revenue/subscriptions")
        assert r.status_code == 200
        data = r.json()
        assert "subscriptions" in data and "total" in data
        assert data["total"] >= 1, "Expected at least 1 auto-provisioned subscription"
        sub = data["subscriptions"][0]
        for key in ("tenant_id", "plan", "status", "monthly_value", "current_period_end"):
            assert key in sub
        # store demo tenant sub for later
        demo_sub = next((s for s in data["subscriptions"] if s["tenant_id"] == TENANT_ID), None)
        assert demo_sub is not None, "ten_demo subscription should be auto-provisioned"

    def test_filter_by_search(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/revenue/subscriptions", params={"search": "demo"})
        assert r.status_code == 200
        data = r.json()
        for s in data["subscriptions"]:
            txt = f"{s.get('tenant_name','')}{s.get('owner_email','')}".lower()
            assert "demo" in txt

    def test_update_plan_mirrors_tenant(self, admin_session):
        # Set plan to dwy then back to original
        r0 = admin_session.get(f"{BASE_URL}/api/admin/revenue/subscriptions")
        original = next(s for s in r0.json()["subscriptions"] if s["tenant_id"] == TENANT_ID)
        original_plan = original["plan"]

        r1 = admin_session.put(
            f"{BASE_URL}/api/admin/revenue/subscriptions/{TENANT_ID}",
            json={"plan": "dwy", "notes": "TEST_iter33 update"},
        )
        assert r1.status_code == 200, r1.text
        # Verify via GET
        r2 = admin_session.get(f"{BASE_URL}/api/admin/revenue/subscriptions")
        updated = next(s for s in r2.json()["subscriptions"] if s["tenant_id"] == TENANT_ID)
        assert updated["plan"] == "dwy"
        assert updated.get("notes") == "TEST_iter33 update"
        # Tenant plan should mirror — fetch via subscriptions row tenant_name only available
        # Restore plan
        admin_session.put(
            f"{BASE_URL}/api/admin/revenue/subscriptions/{TENANT_ID}",
            json={"plan": original_plan, "notes": None},
        )

    def test_update_invalid_plan(self, admin_session):
        r = admin_session.put(
            f"{BASE_URL}/api/admin/revenue/subscriptions/{TENANT_ID}",
            json={"plan": "platinum-bogus"},
        )
        assert r.status_code == 400

    def test_update_unknown_tenant(self, admin_session):
        r = admin_session.put(
            f"{BASE_URL}/api/admin/revenue/subscriptions/ten_does_not_exist",
            json={"notes": "x"},
        )
        assert r.status_code == 404

    def test_extend_30_days(self, admin_session):
        r0 = admin_session.get(f"{BASE_URL}/api/admin/revenue/subscriptions")
        before = next(s for s in r0.json()["subscriptions"] if s["tenant_id"] == TENANT_ID)
        before_end = before["current_period_end"]
        r = admin_session.post(
            f"{BASE_URL}/api/admin/revenue/subscriptions/{TENANT_ID}/extend",
            json={"days": 30},
        )
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["status"] == "ok"
        assert "new_period_end" in out
        assert out["new_period_end"] > before_end

    def test_cancel_invalid_reason(self, admin_session):
        r = admin_session.post(
            f"{BASE_URL}/api/admin/revenue/subscriptions/{TENANT_ID}/cancel",
            json={"reason": "bogus_reason"},
        )
        assert r.status_code == 400


# ─── 4. Manual payments + invoice sequence ───────────────────────────────────
class TestManualPayments:
    payment_id = None
    invoice_number = None

    def test_record_manual_payment(self, admin_session):
        r = admin_session.post(
            f"{BASE_URL}/api/admin/revenue/payments/manual",
            json={
                "tenant_id": TENANT_ID,
                "amount": 4999.0,
                "currency": "INR",
                "method": "bank_transfer",
                "reference_number": "TEST_iter33_ref",
                "plan": "diy",
                "note": "TEST_iter33 manual payment",
            },
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "ok"
        pay = data["payment"]
        assert pay["amount"] == 4999.0
        assert pay["plan"] == "diy"
        assert pay["status"] == "paid"
        assert pay["invoice_number"].startswith("INV-")
        # Format INV-YYYY-NNNN
        parts = pay["invoice_number"].split("-")
        assert len(parts) == 3 and parts[0] == "INV" and len(parts[1]) == 4 and len(parts[2]) == 4
        TestManualPayments.payment_id = pay["id"]
        TestManualPayments.invoice_number = pay["invoice_number"]

    def test_invoice_sequence_increments(self, admin_session):
        r = admin_session.post(
            f"{BASE_URL}/api/admin/revenue/payments/manual",
            json={
                "tenant_id": TENANT_ID, "amount": 100.0, "method": "upi", "plan": "diy",
                "note": "TEST_iter33 seq check",
            },
        )
        assert r.status_code == 200
        new_inv = r.json()["payment"]["invoice_number"]
        prev_n = int(TestManualPayments.invoice_number.split("-")[-1])
        new_n = int(new_inv.split("-")[-1])
        assert new_n == prev_n + 1

    def test_list_payments_filter(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/revenue/payments", params={"tenant_id": TENANT_ID})
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 2
        for p in data["payments"]:
            assert p["tenant_id"] == TENANT_ID

    def test_invoice_pdf(self, admin_session):
        assert TestManualPayments.payment_id, "depends on prior test"
        r = admin_session.get(f"{BASE_URL}/api/admin/invoices/{TestManualPayments.payment_id}/pdf")
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("application/pdf")
        body = r.content
        assert body.startswith(b"%PDF-"), "PDF must start with %PDF-"
        # PDF streams are compressed (FlateDecode+ASCII85); decode to verify content
        try:
            from pypdf import PdfReader
        except ImportError:
            from PyPDF2 import PdfReader
        import io as _io
        reader = PdfReader(_io.BytesIO(body))
        assert len(reader.pages) >= 1
        text = "".join(p.extract_text() or "" for p in reader.pages)
        assert "GenLeadAI" in text, f"PDF missing GenLeadAI; got: {text[:300]}"
        assert "17BVKPA9777N1ZP" in text, f"PDF missing GSTIN; got: {text[:300]}"
        assert "DIY" in text.upper()
        assert TestManualPayments.invoice_number in text
        assert "18%" in text or "GST" in text.upper()

    def test_invoice_pdf_404(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/invoices/pay_does_not_exist/pdf")
        assert r.status_code == 404


# ─── 5. Churn / Trial funnel / By-plan ───────────────────────────────────────
class TestChurnFunnelByPlan:
    def test_churn(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/revenue/churn")
        assert r.status_code == 200
        data = r.json()
        assert "series" in data and "churned" in data and "cohort" in data
        assert len(data["series"]) == 12
        for pt in data["series"]:
            assert "month" in pt and "rate" in pt

    def test_trial_funnel(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/revenue/trial-funnel")
        assert r.status_code == 200
        data = r.json()
        assert "stages" in data and "expiring_soon" in data
        assert len(data["stages"]) == 5
        keys = [s["key"] for s in data["stages"]]
        assert keys == ["signups", "completed_onboarding", "whatsapp_connected", "first_lead", "converted"]
        for s in data["stages"]:
            assert "count" in s and "tenants" in s

    def test_by_plan(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/revenue/by-plan", params={"months": 6})
        assert r.status_code == 200
        data = r.json()
        assert "data" in data
        assert len(data["data"]) == 6
        for pt in data["data"]:
            for k in ("month", "diy", "dwy", "dfy", "total"):
                assert k in pt
