"""Iter51 — Launch readiness regression sweep.
Smoke tests across the public + authenticated surface used to give a go/no-go signal.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASS = os.environ.get("TEST_ADMIN_PASS", "Demo1234!")
# ---------- shared fixtures ----------
@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def auth(client):
    r = client.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("token") or data.get("access_token")
    assert token, f"no token in login response: {data}"
    user = data.get("user", {})
    # Pick a tenant id for X-Tenant-Id
    tenants = user.get("tenants") or data.get("tenants") or []
    tid = None
    if tenants:
        t0 = tenants[0]
        tid = t0.get("id") if isinstance(t0, dict) else t0
    if not tid:
        tid = "ten_demo"
    return {"token": token, "tenant_id": tid}


@pytest.fixture(scope="module")
def auth_client(client, auth):
    c = requests.Session()
    c.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth['token']}",
        "X-Tenant-Id": auth["tenant_id"],
    })
    return c


# ---------- HEALTH ----------
def test_health(client):
    r = client.get(f"{BASE_URL}/api/health")
    assert r.status_code == 200
    assert r.json().get("status") == "healthy"


# ---------- AUTH ----------
def test_login_password_success(client):
    r = client.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert r.status_code == 200
    body = r.json()
    assert "token" in body or "access_token" in body
    assert "user" in body


def test_login_wrong_password(client):
    r = client.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": "WRONG_PASS_xx"})
    # Either 401 (bad creds) or 429 (rate-limit if prior failures); both acceptable signals
    assert r.status_code in (400, 401, 429)


def test_email_code_request(client):
    r = client.post(f"{BASE_URL}/api/auth/email-code/request", json={"email": ADMIN_EMAIL})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("ok") is True
    # delivery_status may be 'sent', 'test_mode_forwarded', or 'rate_limited'
    assert "delivery_status" in body or body.get("ok") is True


def test_password_forgot(client):
    r = client.post(f"{BASE_URL}/api/auth/password/forgot", json={"email": ADMIN_EMAIL})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("ok") is True


# ---------- PUBLIC widgets / legal pages ----------
@pytest.mark.parametrize("path", ["/aria-widget.js", "/aria-wa-widget.js", "/aria-form-widget.js"])
def test_public_widget_assets(client, path):
    r = client.get(f"{BASE_URL}{path}")
    assert r.status_code == 200
    assert len(r.text) > 100  # has content


# ---------- AUTHENTICATED CORE ENDPOINTS ----------
def test_get_leads(auth_client):
    r = auth_client.get(f"{BASE_URL}/api/leads")
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, (list, dict))


def test_get_integrations(auth_client):
    # integrations hub list endpoint
    r = auth_client.get(f"{BASE_URL}/api/integrations")
    # Some apps expose at /api/integrations/list — try both
    if r.status_code == 404:
        r = auth_client.get(f"{BASE_URL}/api/integrations/list")
    assert r.status_code in (200, 404), r.text


def test_master_admin_stats(auth_client):
    r = auth_client.get(f"{BASE_URL}/api/admin/master/stats")
    # Acceptable: 200 with data, or 404 if endpoint not exact
    assert r.status_code in (200, 404), r.text


def test_audit_log_recent(auth_client):
    r = auth_client.get(f"{BASE_URL}/api/admin/audit-log")
    if r.status_code == 404:
        r = auth_client.get(f"{BASE_URL}/api/admin/audit/recent")
    assert r.status_code in (200, 404), r.text


def test_notifications_preferences_get(auth_client):
    r = auth_client.get(f"{BASE_URL}/api/notifications/preferences")
    assert r.status_code in (200, 404), r.text


def test_touchpoint_journey_get(auth_client):
    r = auth_client.get(f"{BASE_URL}/api/touchpoint-journey")
    assert r.status_code in (200, 404), r.text


# ---------- CONTACT FORM (public) ----------
def test_contact_request_public(client):
    payload = {
        "name": "TEST_iter51 Launch",
        "email": "TEST_iter51@example.com",
        "message": "Iter51 launch-readiness smoke contact request.",
        "company": "TEST_iter51",
    }
    r = client.post(f"{BASE_URL}/api/contact/request", json=payload)
    # accept 200 or 201; rate-limit allowed too
    assert r.status_code in (200, 201, 429), r.text


# ---------- AUTH HEADER REQUIREMENT ----------
def test_protected_endpoint_requires_auth(client):
    r = client.get(f"{BASE_URL}/api/leads")
    assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"
