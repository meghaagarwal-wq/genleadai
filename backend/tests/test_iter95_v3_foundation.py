"""Iter95 — Phase 5a: v3.0 Foundation.

- Admin Dashboard v3 endpoints (PART D)
- Pietential mode = b2b (PART E)
- Pietential 4 ICPs pre-seeded (PART E)
- Migration idempotent re Pietential mode + ICPs
"""
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


def _login(email, pw):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw}, timeout=20)
    assert r.status_code == 200, f"login {email}: {r.text[:200]}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def sales_token():
    return _login(SALES_EMAIL, SALES_PASS)


def _h(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module", autouse=True)
def _ensure_pietential_b2b(admin_token):
    """iter92 tests cycle workspace_type and may leave Pietential on hybrid.
    Force-reset to b2b before this module's tests run (PART E v3.0 baseline)."""
    requests.put(
        f"{BASE_URL}/api/aria/workspace-type",
        headers={**_h(admin_token), "X-Tenant-Id": "ten_pietential"},
        json={"workspace_type": "b2b"},
        timeout=20,
    )
    yield


class TestAdminV3Endpoints:
    def test_overview_requires_master_admin(self, sales_token):
        r = requests.get(f"{BASE_URL}/api/admin/v3/overview", headers=_h(sales_token), timeout=20)
        assert r.status_code == 403, r.text[:200]

    def test_overview_returns_expected_shape(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/admin/v3/overview", headers=_h(admin_token), timeout=20)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        for k in ("workspaces", "tenants_total", "leads_today", "active_conversations",
                  "insights_today", "api_cost_today_usd", "errors_24h"):
            assert k in body, f"missing key: {k}"
        assert "total" in body["workspaces"]
        assert body["workspaces"]["total"] >= 1

    def test_workspaces_list_includes_pietential(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/admin/v3/workspaces", headers=_h(admin_token), timeout=20)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        ids = [w["id"] for w in body["workspaces"]]
        assert "ten_pietential" in ids
        pt = next(w for w in body["workspaces"] if w["id"] == "ten_pietential")
        assert pt["mode"] == "b2b"  # PART E v3.0
        assert pt["has_aria_training"] is True

    def test_workspaces_blocks_sales_rep(self, sales_token):
        r = requests.get(f"{BASE_URL}/api/admin/v3/workspaces", headers=_h(sales_token), timeout=20)
        assert r.status_code == 403

    def test_impersonate_returns_workspace_context(self, admin_token):
        r = requests.post(
            f"{BASE_URL}/api/admin/v3/workspaces/ten_pietential/impersonate",
            headers=_h(admin_token),
            timeout=20,
        )
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["ok"] is True
        assert body["workspace_id"] == "ten_pietential"
        assert body["mode"] == "b2b"
        assert body["impersonation_banner"] is True

    def test_impersonate_404_for_missing(self, admin_token):
        r = requests.post(
            f"{BASE_URL}/api/admin/v3/workspaces/ten_does_not_exist/impersonate",
            headers=_h(admin_token), timeout=20,
        )
        assert r.status_code == 404

    def test_usage_endpoint(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/admin/v3/usage", headers=_h(admin_token), timeout=20)
        assert r.status_code == 200
        body = r.json()
        assert "month_start" in body
        assert "rows" in body
        assert isinstance(body["rows"], list)

    def test_system_health_endpoint(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/admin/v3/system-health", headers=_h(admin_token), timeout=20)
        assert r.status_code == 200
        body = r.json()
        assert "job_status" in body
        assert "integration_errors" in body
        assert "checked_at" in body


class TestPietentialV3Config:
    def test_pietential_mode_is_b2b(self):
        t = _db["tenants"].find_one({"id": "ten_pietential"}, {"_id": 0})
        assert t is not None
        assert (t.get("settings") or {}).get("workspace_type") == "b2b"

    def test_pietential_has_four_icps(self):
        # PART E v3.0 requires CHRO Ent, CFO MM, People Analytics, VP People Growth
        icps = list(_db["icps"].find({"tenant_id": "ten_pietential"}, {"_id": 0}))
        labels = {i.get("label") for i in icps}
        required = {
            "CHRO — Enterprise",
            "CFO — Mid-Market SaaS",
            "People Analytics Leader — Enterprise",
            "VP People / Head of HR — Growth-Stage",
        }
        missing = required - labels
        assert not missing, f"Pietential missing ICPs: {missing}"

    def test_pietential_icps_have_required_fields(self):
        for icp in _db["icps"].find({"tenant_id": "ten_pietential"}, {"_id": 0}):
            assert icp.get("title_targets"), f"{icp.get('label')} missing title_targets"
            assert icp.get("company_size"), f"{icp.get('label')} missing company_size"
            assert icp.get("pain_point"), f"{icp.get('label')} missing pain_point"


class TestMigrationStillIdempotent:
    def test_re_run_does_not_duplicate_icps(self):
        from dotenv import load_dotenv
        load_dotenv()
        from scripts.migrate_to_multi_tenant import main as run_migration

        before = _db["icps"].count_documents({"tenant_id": "ten_pietential"})
        run_migration()
        run_migration()  # twice
        after = _db["icps"].count_documents({"tenant_id": "ten_pietential"})
        assert before == after, f"ICPs duplicated: {before} → {after}"
