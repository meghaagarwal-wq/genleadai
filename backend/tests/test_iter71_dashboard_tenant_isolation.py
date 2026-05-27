"""Iter 71 — Backend tests for:
1. /api/insights/founder-command-center demo flag & empty workspace behaviour
2. /api/users tenant-scoped (no leaking across tenants)
"""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD") or os.environ.get("DEMO_ADMIN_PASSWORD", "Demo1234!")
def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    if r.status_code != 200:
        return None
    return r.json().get("token") or r.json().get("access_token")


@pytest.fixture(scope="module")
def admin_token():
    tok = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not tok:
        pytest.skip("admin login failed")
    return tok


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def fresh_user():
    """Signup a brand new tenant via /api/auth/signup."""
    uid = uuid.uuid4().hex[:10]
    email = f"TEST_iter71_{uid}@example.com"
    password = os.environ.get("TEST_SIGNUP_PASSWORD") or os.environ.get("DEMO_ADMIN_PASSWORD", "Demo1234!")
    payload = {"email": email, "password": password, "full_name": "Iter71 Test", "workspace_name": f"Iter71 Co {uid}"}
    r = requests.post(f"{BASE_URL}/api/auth/signup", json=payload, timeout=30)
    if r.status_code not in (200, 201):
        pytest.skip(f"signup failed: {r.status_code} {r.text[:200]}")
    body = r.json()
    tok = body.get("token") or body.get("access_token")
    if not tok:
        pytest.skip("signup returned no token")
    return {"email": email, "password": password, "token": tok, "headers": {"Authorization": f"Bearer {tok}"}}


# ---------- founder-command-center ----------

class TestFounderCommandCenter:
    def test_fresh_tenant_empty_payload(self, fresh_user):
        r = requests.get(f"{BASE_URL}/api/insights/founder-command-center", headers=fresh_user["headers"], timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        body = str(d)
        # No fake demo names anywhere
        assert "Priya Sharma" not in body, "fake Priya Sharma leaking into fresh workspace"
        assert "Aanya Kapoor" not in body, "fake Aanya Kapoor leaking into fresh workspace"
        assert d.get("is_empty_workspace") is True
        assert d.get("money_at_risk", {}).get("rows", []) == []
        assert d.get("hot_leads_untouched", {}).get("rows", []) == []
        # pipeline_value_label can be '-' or '₹0' depending on payload shape — allow both empties
        plabel = d.get("pipeline_value_label") or d.get("pipeline_value", {}).get("label") if isinstance(d.get("pipeline_value"), dict) else d.get("pipeline_value_label")
        assert plabel in ("-", "₹0", "$0", 0, None) or plabel == "-"

    def test_demo_flag_returns_sample_names(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/insights/founder-command-center?demo=true", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        body = str(d)
        assert "Priya Sharma" in body, "demo flag should return Priya Sharma sample"
        assert "Aanya Kapoor" in body, "demo flag should return Aanya Kapoor sample"
        assert d.get("is_empty_workspace") is not True

    def test_admin_real_data_no_fake_names(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/insights/founder-command-center", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        # admin@demo.com has seeded leads, so it should be computed_from_real_data=true
        assert d.get("computed_from_real_data") is True, f"expected real data but got: {d}"
        body = str(d)
        # Real seeded data should NOT contain the fake demo placeholder names
        assert "Priya Sharma" not in body, "fake Priya Sharma leaking into admin real-data response"
        assert "Aanya Kapoor" not in body, "fake Aanya Kapoor leaking into admin real-data response"
        # is_empty_workspace should not be set / be False since admin has leads
        assert d.get("is_empty_workspace") is not True


# ---------- /api/users tenant isolation ----------

class TestUsersTenantIsolation:
    def test_admin_users_scoped(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/users", headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        users = r.json().get("users", [])
        # Should be small (definitely < 30) — admin@demo.com tenant has ~5 members
        assert len(users) < 30, f"too many users returned ({len(users)}) — looks like cross-tenant leak"
        assert len(users) >= 1
        # Each user has role + membership_status fields
        for u in users:
            assert "role" in u, f"user missing role field: {u.get('email')}"
            assert "membership_status" in u, f"user missing membership_status: {u.get('email')}"
        emails = [u.get("email") for u in users]
        assert ADMIN_EMAIL in emails

    def test_fresh_tenant_only_owner(self, fresh_user):
        r = requests.get(f"{BASE_URL}/api/users", headers=fresh_user["headers"], timeout=20)
        assert r.status_code == 200, r.text
        users = r.json().get("users", [])
        assert len(users) == 1, f"expected exactly 1 user, got {len(users)}: {[u.get('email') for u in users]}"
        u = users[0]
        assert u.get("email", "").lower() == fresh_user["email"].lower()
        assert u.get("role") == "owner"
        assert u.get("membership_status") == "active"
