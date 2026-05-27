"""Iter99 — Backend tests for the 4 missing V3 lead integrations.

Covers:
1. Google Ads webhook-URL generator — returns per-tenant URL + auto-rolled
   webhook key on first call (idempotent on subsequent calls).
2. Apollo direct-pull — test-connection + pull endpoints behave correctly
   when no API key is present.
3. Serper enrichment — test-connection + module-level `serper_company_news`
   helper returns NewsAPI-compatible shape (mocked via empty key path).
4. Website Pixel — snippet generator returns valid JS + per-tenant
   endpoint; track endpoint captures both pageview and form_submit
   events, only the latter creating a lead.
5. Regression: existing Saleshandy/Lemlist `test-connection` routes still
   work after the registration-order reshuffle.
"""
import asyncio
import os
import uuid
import pytest
import requests

from deps import db
from routes.integrations_extras import serper_company_news

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD") or os.environ.get("DEMO_ADMIN_PASSWORD", "Demo1234!")

configs_col = db["integration_configs"]
events_col = db["integration_events"]
leads_col = db["leads"]


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


# ─── 1. Google Ads ──────────────────────────────────────────────────────────
class TestGoogleAdsWebhookInfo:
    def test_returns_webhook_url_and_key(self, admin_headers):
        # Clean slate
        configs_col.delete_one({"tenant_id": "ten_pietential", "integration_type": "google_ads"})
        r = requests.get(
            f"{BASE_URL}/api/integrations/google-ads/webhook-info",
            headers=admin_headers, timeout=20,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["webhook_url"].endswith("/api/integrations/google-ads/webhook/ten_pietential")
        assert len(d["webhook_key"]) == 32  # uuid4().hex
        assert isinstance(d.get("instructions"), list) and len(d["instructions"]) >= 3

    def test_is_idempotent(self, admin_headers):
        r1 = requests.get(f"{BASE_URL}/api/integrations/google-ads/webhook-info", headers=admin_headers, timeout=20)
        r2 = requests.get(f"{BASE_URL}/api/integrations/google-ads/webhook-info", headers=admin_headers, timeout=20)
        # Same secret across calls — clients can refresh the modal safely
        assert r1.json()["webhook_key"] == r2.json()["webhook_key"]


# ─── 2. Apollo direct pull ──────────────────────────────────────────────────
class TestApolloDirectPull:
    def test_test_connection_400_when_unconnected(self, admin_headers):
        # Make sure we're unconnected
        configs_col.delete_one({"tenant_id": "ten_pietential", "integration_type": "apollo"})
        r = requests.post(f"{BASE_URL}/api/integrations/apollo/test-connection", headers=admin_headers, timeout=20)
        assert r.status_code == 400
        assert "not connected" in r.json()["detail"].lower()

    def test_pull_400_when_unconnected(self, admin_headers):
        configs_col.delete_one({"tenant_id": "ten_pietential", "integration_type": "apollo"})
        r = requests.post(
            f"{BASE_URL}/api/integrations/apollo/pull",
            headers=admin_headers,
            json={"keyword": "founder"},
            timeout=20,
        )
        assert r.status_code == 400

    def test_pull_400_without_saved_search_or_keyword(self, admin_headers):
        # Seed a fake API key so we move past the unconnected check
        configs_col.update_one(
            {"tenant_id": "ten_pietential", "integration_type": "apollo"},
            {"$set": {
                "tenant_id": "ten_pietential",
                "integration_type": "apollo",
                "status": "connected",
                "config": {"api_key": "FAKE_KEY_FOR_VALIDATION_TEST"},
            }},
            upsert=True,
        )
        try:
            r = requests.post(
                f"{BASE_URL}/api/integrations/apollo/pull",
                headers=admin_headers,
                json={},
                timeout=20,
            )
            assert r.status_code == 400
            assert "saved_search_id" in r.json()["detail"] or "keyword" in r.json()["detail"]
        finally:
            configs_col.delete_one({"tenant_id": "ten_pietential", "integration_type": "apollo"})


# ─── 3. Serper enrichment helper ────────────────────────────────────────────
class TestSerperHelper:
    def test_returns_empty_when_no_key(self):
        out = asyncio.get_event_loop().run_until_complete(serper_company_news("", "Acme Co"))
        assert out == []

    def test_returns_empty_when_no_company(self):
        out = asyncio.get_event_loop().run_until_complete(serper_company_news("FAKE", ""))
        assert out == []

    def test_test_connection_400_when_unconnected(self, admin_headers):
        configs_col.delete_one({"tenant_id": "ten_pietential", "integration_type": "serper"})
        r = requests.post(f"{BASE_URL}/api/integrations/serper/test-connection", headers=admin_headers, timeout=20)
        assert r.status_code == 400


# ─── 4. Website Pixel ───────────────────────────────────────────────────────
class TestWebsitePixel:
    def test_snippet_endpoint_returns_valid_js(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/integrations/website-pixel/snippet", headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "<script>" in d["snippet"]
        assert "/api/integrations/website-pixel/track/ten_pietential" in d["snippet"]
        assert d["snippet_length"] == len(d["snippet"])

    def test_pageview_logged_no_lead(self):
        tid = "ten_pietential"
        before = events_col.count_documents({"tenant_id": tid, "integration_type": "website_pixel"})
        r = requests.post(
            f"{BASE_URL}/api/integrations/website-pixel/track/{tid}",
            json={"event": "pageview", "url": "https://pietential.com/pricing"},
            timeout=20,
        )
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] is True
        assert d["captured"] is False
        # Event was logged
        after = events_col.count_documents({"tenant_id": tid, "integration_type": "website_pixel"})
        assert after == before + 1

    def test_form_submit_creates_lead(self):
        tid = "ten_pietential"
        unique_email = f"iter99_pixel_{uuid.uuid4().hex[:8]}@test.example"
        r = requests.post(
            f"{BASE_URL}/api/integrations/website-pixel/track/{tid}",
            json={
                "event": "form_submit",
                "url": "https://pietential.com/contact",
                "email": unique_email,
                "first_name": "Pixel",
                "company": "Iter99",
            },
            timeout=30,
        )
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] is True
        assert d["captured"] is True
        assert d.get("lead_id"), "form_submit must create a lead"


# ─── 5. Regression — existing tool test-connection routes still work ────────
class TestExistingToolsRegression:
    def test_saleshandy_test_connection_still_routes(self, admin_headers):
        configs_col.delete_one({"tenant_id": "ten_pietential", "integration_type": "saleshandy"})
        r = requests.post(f"{BASE_URL}/api/integrations/saleshandy/test-connection", headers=admin_headers, timeout=20)
        assert r.status_code == 400  # not 404
        assert "saleshandy" in r.json()["detail"].lower()

    def test_lemlist_test_connection_still_routes(self, admin_headers):
        configs_col.delete_one({"tenant_id": "ten_pietential", "integration_type": "lemlist"})
        r = requests.post(f"{BASE_URL}/api/integrations/lemlist/test-connection", headers=admin_headers, timeout=20)
        assert r.status_code == 400  # not 404
        assert "lemlist" in r.json()["detail"].lower()
