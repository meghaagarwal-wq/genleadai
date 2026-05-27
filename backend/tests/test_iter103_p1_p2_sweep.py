"""Iter103 — Backend tests for the P1+P2 sweep:
  1. CSV lead import (preview + import)
  2. Real-time /api/realtime/since polling
  3. Onboarding state GET/PUT/resume
  4. Audit-loops smoke (pure helpers don't crash on empty DB)
"""
import io
import os
import uuid
import pytest
import requests

from deps import db
from routes.audit_loops import (
    pixel_attribution_once, enrichment_retry_once, saleshandy_poll_once,
)

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD") or os.environ.get("DEMO_ADMIN_PASSWORD", "Demo1234!")

leads_col = db["leads"]
onboarding_col = db["onboarding_state"]


@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=20,
    )
    if r.status_code != 200:
        pytest.skip(f"admin login failed: {r.status_code}")
    tok = r.json().get("token") or r.json().get("access_token")
    return {"Authorization": f"Bearer {tok}", "X-Tenant-Id": "ten_pietential"}


# ─── 1. CSV import ─────────────────────────────────────────────────────────
class TestCsvImport:
    def test_preview_returns_headers_and_suggested_mapping(self, admin_headers):
        csv = "First Name,Email,Company,Notes\nAlice,a@iter103.example.com,Acme,Demo\n"
        r = requests.post(
            f"{BASE_URL}/api/leads/import-csv/preview",
            headers=admin_headers,
            files={"file": ("t.csv", io.BytesIO(csv.encode()), "text/csv")},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["headers"] == ["First Name", "Email", "Company", "Notes"]
        assert d["row_count"] == 1
        assert d["suggested_mapping"]["Email"] == "email"
        assert d["suggested_mapping"]["First Name"] == "first_name"
        assert d["suggested_mapping"]["Company"] == "company"
        assert "supported_aria_fields" in d

    def test_import_creates_leads_via_pipeline(self, admin_headers):
        uid = uuid.uuid4().hex[:8]
        csv = (
            "Email,First,Company\n"
            f"alice_{uid}@iter103.example.com,Alice,Acme\n"
            f"bob_{uid}@iter103.example.com,Bob,BobInc\n"
        )
        r = requests.post(
            f"{BASE_URL}/api/leads/import-csv",
            headers=admin_headers,
            files={"file": ("t.csv", io.BytesIO(csv.encode()), "text/csv")},
            data={"mapping_json": '{"Email":"email","First":"first_name","Company":"company"}'},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["rows_processed"] == 2
        assert d["imported"] == 2
        assert d["failed"] == 0
        # Cleanup
        leads_col.delete_many({"email": {"$regex": f"_{uid}@iter103"}})

    def test_import_requires_email_or_phone_in_mapping(self, admin_headers):
        csv = "Name,Note\nAlice,hello\n"
        r = requests.post(
            f"{BASE_URL}/api/leads/import-csv",
            headers=admin_headers,
            files={"file": ("t.csv", io.BytesIO(csv.encode()), "text/csv")},
            data={"mapping_json": '{"Name":"first_name","Note":"message"}'},
            timeout=20,
        )
        assert r.status_code == 400
        assert "email" in r.json()["detail"].lower()


# ─── 2. Realtime polling ────────────────────────────────────────────────────
class TestRealtimeSince:
    def test_returns_empty_with_future_ts(self, admin_headers):
        future = "2099-01-01T00:00:00+00:00"
        r = requests.get(
            f"{BASE_URL}/api/realtime/since",
            params={"ts": future},
            headers=admin_headers,
            timeout=15,
        )
        assert r.status_code == 200
        d = r.json()
        assert d["lead_count"] == 0
        assert d["insight_count"] == 0
        assert d["new_leads"] == []
        assert d["new_insights"] == []

    def test_returns_recent_lead_after_creation(self, admin_headers):
        # Bootstrap a cursor
        r = requests.get(f"{BASE_URL}/api/realtime/since", headers=admin_headers, timeout=15)
        cursor = r.json()["now"]
        # Create a lead via pixel
        uid = uuid.uuid4().hex[:8]
        requests.post(
            f"{BASE_URL}/api/integrations/website-pixel/track/ten_pietential",
            json={"event": "form_submit", "email": f"realtime_{uid}@iter103.example.com"},
            timeout=20,
        )
        # Poll
        import time
        time.sleep(0.5)
        r = requests.get(
            f"{BASE_URL}/api/realtime/since",
            params={"ts": cursor},
            headers=admin_headers,
            timeout=15,
        )
        assert r.status_code == 200
        d = r.json()
        # The new lead must appear
        emails = [l.get("email") for l in d["new_leads"]]
        assert any(f"realtime_{uid}" in (e or "") for e in emails), f"new lead should appear; got {emails}"


# ─── 3. Onboarding state ───────────────────────────────────────────────────
class TestOnboardingState:
    def test_get_default_state_for_new_user(self, admin_headers):
        # Reset to known state
        onboarding_col.delete_one({"user_email": ADMIN_EMAIL})
        r = requests.get(f"{BASE_URL}/api/onboarding/state", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["is_new"] is True
        assert d["state"]["step"] == 0
        assert d["state"]["completed"] is False

    def test_put_persists_and_resumes(self, admin_headers):
        # Put progress
        body = {"step": 2, "business_name": "Iter103 Inc", "mode": "hybrid"}
        r = requests.put(
            f"{BASE_URL}/api/onboarding/state",
            headers={**admin_headers, "Content-Type": "application/json"},
            json=body, timeout=15,
        )
        assert r.status_code == 200
        # Read back
        r = requests.get(f"{BASE_URL}/api/onboarding/state", headers=admin_headers, timeout=15)
        d = r.json()
        assert d["is_new"] is False
        assert d["state"]["step"] == 2
        assert d["state"]["business_name"] == "Iter103 Inc"
        assert d["state"]["mode"] == "hybrid"
        # Cleanup
        onboarding_col.delete_one({"user_email": ADMIN_EMAIL})


# ─── 4. Audit loops smoke ──────────────────────────────────────────────────
class TestAuditLoopsSmoke:
    """Verify the three new background helpers run without crashing on the
    current DB state. Functional behaviour is covered by the dedicated
    integration tests when relevant fixtures exist.
    """

    def test_pixel_attribution_returns_summary(self):
        import asyncio
        out = asyncio.get_event_loop().run_until_complete(pixel_attribution_once())
        assert isinstance(out, dict)
        assert "events_scanned" in out
        assert "attributed" in out

    def test_enrichment_retry_returns_summary(self):
        import asyncio
        out = asyncio.get_event_loop().run_until_complete(enrichment_retry_once())
        assert isinstance(out, dict)
        assert "tenants_retried" in out

    def test_saleshandy_poll_returns_summary(self):
        import asyncio
        out = asyncio.get_event_loop().run_until_complete(saleshandy_poll_once())
        assert isinstance(out, dict)
        assert "tenants_scanned" in out
        assert "replies_imported" in out
