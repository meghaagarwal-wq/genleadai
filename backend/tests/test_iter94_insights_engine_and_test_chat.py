"""Iter94 — Phase 3 (B2B Insights Engine) + Test Aria chat + migration fix."""
from __future__ import annotations

import os
import sys
import requests
import pytest
from pymongo import MongoClient

_BACKEND_DIR = "/app/backend"
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASS = os.environ.get("TEST_ADMIN_PASS", "Demo1234!")
SALES_EMAIL = "sarah@demo.com"
SALES_PASS = os.environ.get("TEST_SALES_PASS", "Demo1234!")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "genleadai_lms")
_mc = MongoClient(MONGO_URL)
_db = _mc[DB_NAME]


def _login(email: str, password: str) -> str:
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text[:200]}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def sales_token():
    return _login(SALES_EMAIL, SALES_PASS)


def _h(token: str, tenant_id: str = "ten_pietential") -> dict:
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": tenant_id, "Content-Type": "application/json"}


# ─── A. Insights endpoints (B2B Insights Engine) ────────────────────────
class TestInsightsIntegrations:
    def test_get_integrations_returns_handshake(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/pt/insights/integrations",
                         headers=_h(admin_token, "ten_pietential"), timeout=20)
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        assert "proxycurl" in body
        assert "newsapi" in body
        assert "connected" in body["proxycurl"]
        assert "connected" in body["newsapi"]

    def test_sales_rep_blocked_on_put_integrations(self, sales_token):
        r = requests.put(f"{BASE_URL}/api/pt/insights/integrations",
                         headers=_h(sales_token, "ten_demo"),
                         json={"proxycurl_api_key": "fake"}, timeout=20)
        assert r.status_code in (401, 403)

    def test_admin_can_set_and_clear_keys(self, admin_token):
        # Set keys
        r = requests.put(f"{BASE_URL}/api/pt/insights/integrations",
                         headers=_h(admin_token, "ten_pietential"),
                         json={"proxycurl_api_key": "test-proxy-key-12345",
                               "newsapi_key": "test-news-key-67890"}, timeout=20)
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        assert body["proxycurl"]["connected"] is True
        assert body["newsapi"]["connected"] is True

        # Verify stored encrypted (raw key must not appear in tenant doc)
        t = _db["tenants"].find_one({"id": "ten_pietential"}, {"_id": 0, "settings.pt_enrichment": 1})
        enrich = t.get("settings", {}).get("pt_enrichment") or {}
        assert enrich.get("proxycurl_api_key", "").startswith("enc::")
        assert "test-proxy-key-12345" not in enrich.get("proxycurl_api_key", "")

        # Clear keys
        r2 = requests.put(f"{BASE_URL}/api/pt/insights/integrations",
                          headers=_h(admin_token, "ten_pietential"),
                          json={"proxycurl_api_key": "", "newsapi_key": ""}, timeout=20)
        assert r2.status_code == 200
        body2 = r2.json()
        assert body2["proxycurl"]["connected"] is False
        assert body2["newsapi"]["connected"] is False


class TestInsightsFeedAndScan:
    def test_feed_empty_initial(self, admin_token):
        # Clear any existing insights for clean state
        _db["pt_insights"].delete_many({"tenant_id": "ten_pietential"})
        r = requests.get(f"{BASE_URL}/api/pt/insights/feed",
                         headers=_h(admin_token, "ten_pietential"), timeout=20)
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 0
        assert body["cards"] == []

    def test_sales_rep_blocked_on_scan(self, sales_token):
        r = requests.post(f"{BASE_URL}/api/pt/insights/scan/run-now",
                          headers=_h(sales_token, "ten_demo"), timeout=30)
        assert r.status_code in (401, 403)

    def test_admin_scan_runs_returns_status(self, admin_token):
        """Scan should complete (even with no enrichment keys), returning status."""
        r = requests.post(f"{BASE_URL}/api/pt/insights/scan/run-now",
                          headers=_h(admin_token, "ten_pietential"), timeout=180)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["ok"] is True
        assert "scanned" in body
        assert "insights_created" in body
        assert "enrichment_status" in body
        # Claude should always be available via EMERGENT_LLM_KEY
        assert body["enrichment_status"]["claude"] is True

    def test_invalid_action_rejected(self, admin_token):
        # Make sure action endpoint validates
        r = requests.post(f"{BASE_URL}/api/pt/insights/some_fake_id/action",
                          headers=_h(admin_token, "ten_pietential"),
                          json={"action": "explode"}, timeout=20)
        assert r.status_code == 422  # pydantic regex

    def test_action_on_nonexistent_card_404(self, admin_token):
        r = requests.post(f"{BASE_URL}/api/pt/insights/ins_nonexistent_id/action",
                          headers=_h(admin_token, "ten_pietential"),
                          json={"action": "dismiss"}, timeout=20)
        assert r.status_code == 404


class TestInsightsUnit:
    def test_icp_score_title_match(self):
        from routes.pt_insights import _score_icp_match
        prospect = {"title": "CHRO", "company_name": "Acme SaaS"}
        icp = {
            "target_titles_or_roles": ["CHRO", "VP People"],
            "target_industries": ["SaaS"],
            "company_size": "100-1000",
            "high_intent_signals": [],
        }
        s = _score_icp_match(prospect, icp)
        # Title (0.35) + Industry (0.30) + Size partial (0.10) = 0.75
        assert s >= 0.65

    def test_icp_score_no_match(self):
        from routes.pt_insights import _score_icp_match
        prospect = {"title": "Software Engineer", "company_name": "Acme"}
        icp = {
            "target_titles_or_roles": ["CHRO"],
            "target_industries": ["SaaS"],
            "company_size": "100-1000",
            "high_intent_signals": [],
        }
        s = _score_icp_match(prospect, icp)
        # No title, no industry → only size partial 0.10
        assert s <= 0.20

    def test_best_icp_returns_highest(self):
        from routes.pt_insights import _best_icp_match
        prospect = {"title": "VP People", "company_name": "FinTech Co"}
        icps = [
            {"icp_name": "ICP A", "target_titles_or_roles": ["CHRO"], "target_industries": ["SaaS"]},
            {"icp_name": "ICP B", "target_titles_or_roles": ["VP People"], "target_industries": ["FinTech"]},
        ]
        best, score = _best_icp_match(prospect, icps)
        assert best["icp_name"] == "ICP B"
        assert score >= 0.65

    def test_best_icp_empty_returns_none(self):
        from routes.pt_insights import _best_icp_match
        best, score = _best_icp_match({"title": "CHRO"}, [])
        assert best is None
        assert score == 0.0

    def test_resource_map_covers_all_signal_types(self):
        from routes.pt_insights import RESOURCE_MAP, SIGNAL_TYPES
        for st in SIGNAL_TYPES:
            assert st in RESOURCE_MAP, f"missing resource for {st}"


# ─── B. Test Aria chat endpoint ─────────────────────────────────────────
class TestAriaTestChat:
    def test_returns_message_for_trained_workspace(self, admin_token):
        """Pietential is trained — Aria should respond using assembled prompt."""
        r = requests.post(f"{BASE_URL}/api/aria/test-chat",
                          headers=_h(admin_token, "ten_pietential"),
                          json={"message": "Hi, I'm the CHRO at a 400-person SaaS company. What do you do?"},
                          timeout=60)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["ok"] is True
        assert "message" in body
        assert "action" in body
        # Message should be non-empty
        assert len(body["message"]) > 10

    def test_rejects_empty_message(self, admin_token):
        r = requests.post(f"{BASE_URL}/api/aria/test-chat",
                          headers=_h(admin_token, "ten_pietential"),
                          json={"message": ""}, timeout=20)
        assert r.status_code == 422

    def test_works_without_training_profile(self, admin_token):
        """Even an untrained tenant should respond via the stub prompt."""
        r = requests.post(f"{BASE_URL}/api/aria/test-chat",
                          headers=_h(admin_token, "ten_demo"),
                          json={"message": "What is this?"}, timeout=60)
        # Should NOT 5xx — either 200 with conservative response or 403/404 for tenant access
        assert r.status_code in (200, 403, 404), r.text[:200]


# ─── C. Migration idempotency / training profile preservation ───────────
class TestMigrationDoesNotWipeTraining:
    def test_pietential_training_survives_migration_rerun(self):
        """Critical bug fix from iter94 — re-running migration must NOT
        wipe settings.aria_training_profile on existing tenants."""
        # Read current Pietential settings
        before = _db["tenants"].find_one({"id": "ten_pietential"}, {"_id": 0, "settings": 1})
        before_atp = (before.get("settings") or {}).get("aria_training_profile")
        if not before_atp:
            pytest.skip("ten_pietential has no training profile to test preservation")
        before_version = before_atp.get("version")

        # Re-run the migration in-process
        from dotenv import load_dotenv
        load_dotenv()
        from scripts.migrate_to_multi_tenant import main as run_migration
        run_migration()

        # Verify training profile preserved
        after = _db["tenants"].find_one({"id": "ten_pietential"}, {"_id": 0, "settings": 1})
        after_atp = (after.get("settings") or {}).get("aria_training_profile")
        assert after_atp is not None, "Migration wiped aria_training_profile!"
        assert after_atp.get("version") == before_version, "Migration modified training profile!"
        assert (after.get("settings") or {}).get("workspace_type") in ("b2b", "b2c", "hybrid")

    def test_upsert_is_set_on_insert_not_set(self):
        """Verify the upsert helper uses $setOnInsert (not $set)."""
        import inspect
        from scripts.migrate_to_multi_tenant import upsert
        src = inspect.getsource(upsert)
        assert "$setOnInsert" in src, "upsert must use $setOnInsert to be idempotent"
        assert "'$set'" not in src and '"$set"' not in src, "upsert must NOT use raw $set"
