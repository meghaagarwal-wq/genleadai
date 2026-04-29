"""
Iteration 15 smoke tests — ARIA brand redesign.
Verify backend regression: all critical endpoints still return 200 with expected shapes.
No backend changes were made this iteration (UI/UX only).
"""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://pipeline-pro-96.preview.emergentagent.com').rstrip('/')


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@demo.com", "password": "Demo1234!"}, timeout=15)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    assert "access_token" in data or "token" in data
    return data.get("access_token") or data.get("token")


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# === Health
def test_health():
    r = requests.get(f"{BASE_URL}/api/health", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") in ("ok", "healthy") or body.get("ok") is True or "status" in body


# === Auth
def test_auth_login_returns_user():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@demo.com", "password": "Demo1234!"}, timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data or "token" in data
    assert "user" in data
    assert data["user"]["email"] == "admin@demo.com"


def test_auth_invalid_credentials():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@demo.com", "password": "wrong"}, timeout=15)
    assert r.status_code in (400, 401, 403)


# === Leads
def test_leads_list(auth_headers):
    r = requests.get(f"{BASE_URL}/api/leads", headers=auth_headers, timeout=15)
    assert r.status_code == 200
    data = r.json()
    # accept either list or paginated dict
    assert isinstance(data, (list, dict))


# === Billing
def test_billing_plans(auth_headers):
    r = requests.get(f"{BASE_URL}/api/billing/plans", headers=auth_headers, timeout=15)
    assert r.status_code == 200
    data = r.json()
    plans = data if isinstance(data, list) else data.get("plans", [])
    assert isinstance(plans, list) and len(plans) >= 4
    plan_ids = [p.get("plan_id") or p.get("id") for p in plans]
    for needed in ("starter", "growth", "pro", "custom"):
        assert needed in plan_ids, f"missing plan {needed} in {plan_ids}"


def test_billing_current_plan(auth_headers):
    r = requests.get(f"{BASE_URL}/api/billing/current-plan", headers=auth_headers, timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert "plan_id" in data or "current_plan" in data or "plan" in data


# === ARIA call priority
def test_aria_call_priority(auth_headers):
    r = requests.get(f"{BASE_URL}/api/aria/call-priority", headers=auth_headers, timeout=20)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, (list, dict))


# === Lead magnets recent opens
def test_lead_magnets_recent_opens(auth_headers):
    r = requests.get(f"{BASE_URL}/api/lead-magnets/recent-opens", headers=auth_headers, timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, (list, dict))


# === TTV milestones
def test_ttv_milestones(auth_headers):
    r = requests.get(f"{BASE_URL}/api/ttv/milestones", headers=auth_headers, timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, (list, dict))
