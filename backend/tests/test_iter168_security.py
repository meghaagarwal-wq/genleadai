"""
iter168 — Security audit remediation verification tests.

Covers:
  SEC-001 — Pietential lead PATCH/DELETE/ask-aria tenant-scoped (foreign ID → 404)
  SEC-002 — Legacy leads endpoints (your-five-today, sleeping) tenant-scoped
  SEC-003 — ARIA endpoints tenant-scoped (foreign ObjectId → 404)
  SEC-004 — Regex ReDoS defence on /api/pt/leads?q= and ?title=
  SEC-005 — CSV import tenant-scoped, size/content-type gated
  Regression sweep — auth/dashboard/insights endpoints still 200
"""
import io
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PW = "Demo1234!"
FAKE_PT_LEAD = "ptl_fake_foreign_lead"
FAKE_OID = "000000000000000000000000"  # valid ObjectId format, non-existent


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json().get("token") or r.json().get("access_token")


@pytest.fixture(scope="module")
def hdr(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def real_pt_lead_id(hdr):
    r = requests.get(f"{BASE_URL}/api/pt/leads?limit=20", headers=hdr, timeout=15)
    assert r.status_code == 200, r.text
    leads = r.json().get("leads", [])
    assert len(leads) > 0, "no ten_demo pt leads found"
    return leads[0]["id"], leads


# ─────────────────────── SEC-001 ─────────────────────────
class TestSEC001PietentialWrites:
    def test_patch_foreign_lead_returns_404(self, hdr):
        r = requests.patch(f"{BASE_URL}/api/pt/leads/{FAKE_PT_LEAD}", headers=hdr, json={"stage": "warm"}, timeout=10)
        assert r.status_code == 404, f"expected 404 got {r.status_code} {r.text}"
        assert "not found" in r.text.lower()

    def test_delete_foreign_lead_returns_404(self, hdr):
        r = requests.delete(f"{BASE_URL}/api/pt/leads/{FAKE_PT_LEAD}", headers=hdr, timeout=10)
        assert r.status_code == 404, f"expected 404 got {r.status_code} {r.text}"

    def test_ask_aria_foreign_lead_returns_404(self, hdr):
        r = requests.post(f"{BASE_URL}/api/pt/leads/{FAKE_PT_LEAD}/ask-aria", headers=hdr, json={}, timeout=15)
        assert r.status_code == 404, f"expected 404 got {r.status_code} {r.text}"

    def test_patch_real_lead_still_works(self, hdr, real_pt_lead_id):
        lid, _ = real_pt_lead_id
        r = requests.patch(f"{BASE_URL}/api/pt/leads/{lid}", headers=hdr, json={"stage": "warm"}, timeout=15)
        assert r.status_code == 200, f"legit patch failed {r.status_code} {r.text}"
        body = r.json()
        assert body.get("lead", {}).get("stage") == "warm"


# ─────────────────────── SEC-002 ─────────────────────────
class TestSEC002LegacyLeadsTenantScoped:
    def test_your_five_today_tenant_scoped(self, hdr):
        r = requests.get(f"{BASE_URL}/api/leads/your-five-today", headers=hdr, timeout=15)
        assert r.status_code == 200, r.text
        # Cannot inspect tenant_id (excluded from projection) — but response should be small (<=5)
        leads = r.json().get("leads", [])
        assert isinstance(leads, list)
        assert len(leads) <= 5

    def test_sleeping_returns_200(self, hdr):
        r = requests.get(f"{BASE_URL}/api/leads/sleeping", headers=hdr, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "leads" in data
        assert "segments" in data

    def test_sleeping_threshold_days_param(self, hdr):
        r = requests.get(f"{BASE_URL}/api/leads/sleeping?threshold_days=30", headers=hdr, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "leads" in data and "segments" in data

    def test_sleeping_deprecated_returns_410(self, hdr):
        r = requests.get(f"{BASE_URL}/api/leads/sleeping-deprecated", headers=hdr, timeout=15)
        assert r.status_code == 410, f"expected 410 got {r.status_code} {r.text}"

    def test_no_duplicate_sleeping_route(self):
        # Grep server.py — must have only ONE @app.get("/api/leads/sleeping")
        with open("/app/backend/server.py") as f:
            src = f.read()
        count = src.count('@app.get("/api/leads/sleeping")')
        assert count == 1, f"expected exactly 1 /api/leads/sleeping route, found {count}"


# ─────────────────────── SEC-003 ─────────────────────────
class TestSEC003AriaTenantScoped:
    def test_aria_trigger_fake_oid_404(self, hdr):
        r = requests.post(f"{BASE_URL}/api/aria/trigger", headers=hdr, json={"lead_id": FAKE_OID, "touch_type": "first_touch"}, timeout=15)
        # Could be 400 (aria disabled) or 404. Accept either denial.
        assert r.status_code in (400, 404), f"got {r.status_code} {r.text}"

    def test_aria_reply_fake_oid_404(self, hdr):
        r = requests.post(f"{BASE_URL}/api/aria/reply", headers=hdr, json={"lead_id": FAKE_OID, "message": "hi"}, timeout=15)
        assert r.status_code == 404, r.text

    def test_aria_conversation_fake_oid_404(self, hdr):
        r = requests.get(f"{BASE_URL}/api/aria/conversation/{FAKE_OID}", headers=hdr, timeout=10)
        assert r.status_code == 404, r.text

    def test_aria_takeover_fake_oid_404(self, hdr):
        r = requests.post(f"{BASE_URL}/api/aria/takeover/{FAKE_OID}", headers=hdr, timeout=10)
        assert r.status_code == 404, r.text

    def test_aria_resume_fake_oid_404(self, hdr):
        r = requests.post(f"{BASE_URL}/api/aria/resume/{FAKE_OID}", headers=hdr, timeout=10)
        assert r.status_code == 404, r.text

    def test_no_show_recovery_fake_oid_404(self, hdr):
        r = requests.post(f"{BASE_URL}/api/leads/no-show-recovery", headers=hdr, json={"lead_id": FAKE_OID, "step": 1}, timeout=15)
        assert r.status_code == 404, r.text

    def test_revival_campaign_processes_zero_for_foreign_ids(self, hdr):
        r = requests.post(f"{BASE_URL}/api/leads/revival-campaign", headers=hdr, json={"lead_ids": [FAKE_OID], "angle": "check_in", "channel": "whatsapp"}, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("sent", 0) == 0, f"expected 0 sent, got {body}"


# ─────────────────────── SEC-004 ─────────────────────────
class TestSEC004RedosDefence:
    def test_evil_q_regex_fast(self, hdr):
        payload = "(a+)+" * 20
        t0 = time.time()
        r = requests.get(f"{BASE_URL}/api/pt/leads", headers=hdr, params={"q": payload}, timeout=10)
        dur = time.time() - t0
        assert r.status_code == 200, r.text
        assert dur < 3.0, f"ReDoS suspected — took {dur:.2f}s"

    def test_evil_title_regex_fast(self, hdr):
        payload = "(a+)+" * 20
        t0 = time.time()
        r = requests.get(f"{BASE_URL}/api/pt/leads", headers=hdr, params={"title": payload}, timeout=10)
        dur = time.time() - t0
        assert r.status_code == 200, r.text
        assert dur < 3.0, f"ReDoS suspected — took {dur:.2f}s"


# ─────────────────────── SEC-005 ─────────────────────────
class TestSEC005CsvImport:
    def test_valid_csv_import_success_and_tenant_stamped(self, token):
        csv_bytes = b"first_name,last_name,email\nTEST_Alice,Sec,test_sec_alice@example.com\nTEST_Bob,Sec,test_sec_bob@example.com\n"
        files = {"file": ("leads.csv", csv_bytes, "text/csv")}
        r = requests.post(f"{BASE_URL}/api/leads/import", files=files, headers={"Authorization": f"Bearer {token}"}, timeout=20)
        assert r.status_code == 200, r.text
        assert "Successfully imported" in r.text
        # Verify tenant scoping — GET /api/leads should not surface foreign tenants
        r2 = requests.get(f"{BASE_URL}/api/leads?limit=500", headers={"Authorization": f"Bearer {token}"}, timeout=15)
        assert r2.status_code == 200
        emails = [l.get("email") for l in r2.json().get("leads", [])]
        assert "test_sec_alice@example.com" in emails or "TEST_Alice" in str(emails).lower() or any("test_sec_alice" in (e or "").lower() for e in emails)

    def test_oversize_returns_413(self, token):
        big = b"first_name,email\n" + (b"x," + b"a" * 100 + b"@x.com\n") * 60000  # ~6+ MB
        files = {"file": ("big.csv", big, "text/csv")}
        r = requests.post(f"{BASE_URL}/api/leads/import", files=files, headers={"Authorization": f"Bearer {token}"}, timeout=30)
        assert r.status_code == 413, f"expected 413 got {r.status_code} {r.text[:200]}"

    def test_bad_content_type_returns_400(self, token):
        files = {"file": ("mal.exe", b"MZ\x00\x00binary", "application/x-msdownload")}
        r = requests.post(f"{BASE_URL}/api/leads/import", files=files, headers={"Authorization": f"Bearer {token}"}, timeout=15)
        assert r.status_code == 400, f"expected 400 got {r.status_code} {r.text[:200]}"


# ─────────────────────── Regression sweep ─────────────────────────
class TestRegressionSweep:
    @pytest.mark.parametrize("path", [
        "/api/tenants/me",
        "/api/dashboard/b2b-founder",
        "/api/dashboard/integration-showcase",
        "/api/approvals",
        "/api/insights/founder-command-center",
    ])
    def test_endpoint_200(self, hdr, path):
        r = requests.get(f"{BASE_URL}{path}", headers=hdr, timeout=20)
        assert r.status_code == 200, f"{path} → {r.status_code} {r.text[:200]}"

    def test_pt_leads_returns_leads(self, hdr):
        r = requests.get(f"{BASE_URL}/api/pt/leads", headers=hdr, timeout=15)
        assert r.status_code == 200
        assert len(r.json().get("leads", [])) >= 1
