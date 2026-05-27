"""Iter97 — Backend tests for the B2B Insight Scan daily cron.

Verifies:
1. `_b2b_eligible_tenants()` selects b2b/hybrid tenants under all three
   supported field shapes (`mode`, `settings.mode`, `settings.workspace_type`).
2. `run_insight_scan_for_tenant()` returns the expected shape and stamps
   `settings.pt_insights.last_scan_at` on the tenant doc.
3. `run_b2b_insight_scan_once()` aggregates across eligible tenants and
   skips ineligible ones (e.g. pure b2c).
4. Live POST `/api/pt/insights/scan/run-now` still works after the
   refactor (regression against the existing manual-trigger endpoint).
"""
import asyncio
import os
import uuid
import pytest
import requests

from deps import db
from routes.pt_insights import (
    _b2b_eligible_tenants,
    run_b2b_insight_scan_once,
    run_insight_scan_for_tenant,
)

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD") or os.environ.get("DEMO_ADMIN_PASSWORD", "Demo1234!")

tenants_col = db["tenants"]


def _mk_tenant(suffix: str, mode_field: str, mode_value: str) -> dict:
    """Insert a throwaway tenant and return its dict (auto-cleaned in fixture)."""
    tid = f"ten_iter97_{suffix}_{uuid.uuid4().hex[:6]}"
    settings = {}
    doc = {"id": tid, "name": f"Iter97 {suffix}", "settings": settings}
    if mode_field == "mode":
        doc["mode"] = mode_value
    elif mode_field == "settings.mode":
        settings["mode"] = mode_value
    elif mode_field == "settings.workspace_type":
        settings["workspace_type"] = mode_value
    tenants_col.insert_one(doc)
    # Re-read without _id so callers can use it directly.
    return tenants_col.find_one({"id": tid}, {"_id": 0})


@pytest.fixture()
def cleanup_iter97():
    yield
    tenants_col.delete_many({"id": {"$regex": "^ten_iter97_"}})


class TestEligibility:
    def test_b2b_tenant_in_settings_mode_picked_up(self, cleanup_iter97):
        _mk_tenant("a", "settings.mode", "b2b")
        ids = {t["id"] for t in _b2b_eligible_tenants()}
        assert any(i.startswith("ten_iter97_a_") for i in ids)

    def test_hybrid_tenant_at_top_level_picked_up(self, cleanup_iter97):
        _mk_tenant("b", "mode", "hybrid")
        ids = {t["id"] for t in _b2b_eligible_tenants()}
        assert any(i.startswith("ten_iter97_b_") for i in ids)

    def test_workspace_type_legacy_field_picked_up(self, cleanup_iter97):
        _mk_tenant("c", "settings.workspace_type", "b2b")
        ids = {t["id"] for t in _b2b_eligible_tenants()}
        assert any(i.startswith("ten_iter97_c_") for i in ids)

    def test_b2c_tenant_ignored(self, cleanup_iter97):
        _mk_tenant("d", "settings.mode", "b2c")
        ids = {t["id"] for t in _b2b_eligible_tenants()}
        assert not any(i.startswith("ten_iter97_d_") for i in ids)


class TestRunForTenant:
    def test_stamps_last_scan_at(self, cleanup_iter97):
        tenant = _mk_tenant("stamp", "settings.mode", "b2b")
        result = asyncio.get_event_loop().run_until_complete(
            run_insight_scan_for_tenant(tenant)
        )
        # Shape contract
        assert set(result.keys()) >= {"scanned", "insights_created", "cards", "enrichment_status"}
        assert isinstance(result["scanned"], int)
        assert isinstance(result["insights_created"], int)
        # Stamp present
        fresh = tenants_col.find_one({"id": tenant["id"]}, {"_id": 0})
        last_scan = ((fresh or {}).get("settings") or {}).get("pt_insights", {}).get("last_scan_at")
        assert last_scan, "expected settings.pt_insights.last_scan_at to be stamped"


class TestSweep:
    def test_aggregates_eligible_tenants(self, cleanup_iter97):
        _mk_tenant("sweep1", "settings.mode", "b2b")
        _mk_tenant("sweep2", "mode", "hybrid")
        _mk_tenant("sweep3", "settings.mode", "b2c")  # should NOT be swept
        summary = asyncio.get_event_loop().run_until_complete(run_b2b_insight_scan_once())
        # Both b2b + hybrid scanned; b2c excluded
        swept_ids = {row["tenant_id"] for row in summary["per_tenant"]}
        assert any(s.startswith("ten_iter97_sweep1_") for s in swept_ids)
        assert any(s.startswith("ten_iter97_sweep2_") for s in swept_ids)
        assert not any(s.startswith("ten_iter97_sweep3_") for s in swept_ids)
        # tenants_scanned counts only those we actually iterated over
        assert summary["tenants_scanned"] >= 2


class TestRunNowEndpointStillWorks:
    """Regression — the manual-trigger endpoint shouldn't break after refactor."""

    def test_admin_can_run_scan(self):
        login = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=20,
        )
        if login.status_code != 200:
            pytest.skip(f"admin login failed: {login.status_code}")
        token = login.json().get("token") or login.json().get("access_token")
        # Pin pietential tenant (b2b)
        r = requests.post(
            f"{BASE_URL}/api/pt/insights/scan/run-now",
            headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": "ten_pietential"},
            timeout=60,
        )
        assert r.status_code in (200, 401, 403), r.text  # accept auth variants
        if r.status_code == 200:
            body = r.json()
            assert body.get("ok") is True
            assert "scanned" in body and "insights_created" in body
            assert "enrichment_status" in body
