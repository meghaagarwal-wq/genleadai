"""Iter79 regression — S8 (Master Admin Deployments + onboarding +
sidebar status + pause/resume), S6 (suggested assets), S9.5 (safe
validation errors)."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")


@pytest.fixture(scope="module")
def auth():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@demo.com", "password": "Demo1234!"}, timeout=10)
    r.raise_for_status()
    token = r.json().get("access_token") or r.json().get("token")
    return {"token": token, "headers": {"Authorization": f"Bearer {token}", "X-Tenant-Id": "ten_demo"}}


# ─── S8 ─────────────────────────────────────────────────────────────────────
def test_s8_list_deployments_requires_master_admin(auth):
    r = requests.get(f"{BASE_URL}/api/admin/deployments", headers=auth["headers"], timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "rollup" in body and "deployments" in body
    assert set(body["rollup"].keys()) >= {"total", "live", "setup", "paused"}


def test_s8_sidebar_status_returns_status_and_counts(auth):
    r = requests.get(f"{BASE_URL}/api/admin/deployments/_/sidebar-status", headers=auth["headers"], timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] in ("LIVE", "SETUP", "PAUSED")
    assert isinstance(body["leads_today"], int)
    assert isinstance(body["touchpoints_today"], int)


def test_s8_onboard_and_toggle_full_lifecycle(auth):
    suffix = uuid.uuid4().hex[:6]
    payload = {
        "step1": {"business_name": f"Test Iter79 {suffix}", "founder_name": "Test Founder", "founder_email": f"founder-{suffix}@example.com", "industry": "SaaS"},
        "step2": {"email_from_name": "Founder", "email_from_address": f"founder-{suffix}@example.com", "resend_api_key": "re_test_iter79"},
        "step3": {"icp_industry": "SaaS", "icp_target_title": "CTO", "icp_pain_point": "Lead qualification", "preferred_channel": "email"},
    }
    r = requests.post(f"{BASE_URL}/api/admin/deployments/onboard", headers=auth["headers"], json=payload, timeout=15)
    assert r.status_code == 200, r.text
    tid = r.json()["tenant_id"]
    assert r.json()["status"] in ("LIVE", "SETUP")

    # GET single
    g = requests.get(f"{BASE_URL}/api/admin/deployments/{tid}", headers=auth["headers"], timeout=10)
    assert g.status_code == 200
    assert g.json()["deployment"]["tenant_id"] == tid
    # masked keys check
    assert g.json()["api_keys"]["email"]["api_key"] is not None  # masked, not None

    # Pause
    p = requests.post(f"{BASE_URL}/api/admin/deployments/{tid}/toggle", headers=auth["headers"], json={"pause": True}, timeout=10)
    assert p.status_code == 200
    g2 = requests.get(f"{BASE_URL}/api/admin/deployments/{tid}", headers=auth["headers"], timeout=10)
    assert g2.json()["deployment"]["status"] == "PAUSED"

    # Resume
    p2 = requests.post(f"{BASE_URL}/api/admin/deployments/{tid}/toggle", headers=auth["headers"], json={"pause": False}, timeout=10)
    assert p2.status_code == 200
    g3 = requests.get(f"{BASE_URL}/api/admin/deployments/{tid}", headers=auth["headers"], timeout=10)
    assert g3.json()["deployment"]["status"] != "PAUSED"

    # Cleanup
    from pymongo import MongoClient
    cli = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    dbm = cli[os.environ.get("DB_NAME", "genleadai_lms")]
    dbm.tenants.delete_one({"id": tid})
    dbm.icps.delete_many({"tenant_id": tid})
    dbm.workspace_touchpoint_maps.delete_many({"tenant_id": tid})
    dbm.tenant_users.delete_many({"tenant_id": tid})


def test_s8_get_unknown_tenant_404(auth):
    r = requests.get(f"{BASE_URL}/api/admin/deployments/ten_does_not_exist", headers=auth["headers"], timeout=10)
    assert r.status_code == 404


# ─── S6 ─────────────────────────────────────────────────────────────────────
def test_s6_suggested_assets_endpoint(auth):
    # Pick the first available lead so this test isn't brittle
    leads_resp = requests.get(f"{BASE_URL}/api/leads?limit=1", headers=auth["headers"], timeout=10)
    items = leads_resp.json().get("leads") or []
    if not items:
        pytest.skip("no leads on ten_demo")
    lead_id = items[0].get("id") or items[0].get("_id")
    r = requests.get(f"{BASE_URL}/api/aria-agent/suggested-assets/{lead_id}?q=what+is+your+pricing", headers=auth["headers"], timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["lead_id"] == lead_id
    assert "suggested" in body
    assert "count" in body


def test_s6_suggested_assets_unknown_lead_404(auth):
    r = requests.get(f"{BASE_URL}/api/aria-agent/suggested-assets/totally_fake_id?q=hello", headers=auth["headers"], timeout=10)
    assert r.status_code == 404


# ─── S9.5 ──────────────────────────────────────────────────────────────────
def test_s9_5_safe_validation_error_returns_string_detail(auth):
    """422 from missing body should now be a plain string, not an error array."""
    r = requests.post(f"{BASE_URL}/api/admin/deployments/onboard", headers=auth["headers"], json={}, timeout=10)
    assert r.status_code == 422
    body = r.json()
    assert isinstance(body.get("detail"), str)
    assert "step1" in body["detail"]
