"""Iter163 regression: verify chunk A backend endpoints still respond 200."""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")
EMAIL = "admin@demo.com"
PASSWORD = "Demo1234!"


@pytest.fixture(scope="module")
def auth():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=20)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    token = data.get("token") or data.get("access_token")
    assert token, f"No token returned: {data}"
    s.headers.update({"Authorization": f"Bearer {token}"})
    # set tenant header
    tr = s.get(f"{BASE_URL}/api/tenants/me", timeout=20)
    if tr.status_code == 200:
        td = tr.json()
        tid = None
        if isinstance(td, list) and td:
            tid = td[0].get("id") or td[0].get("tenant_id")
        elif isinstance(td, dict):
            tid = td.get("id") or td.get("tenant_id") or (td.get("tenants") or [{}])[0].get("id")
        if tid:
            s.headers.update({"X-Tenant-Id": tid})
    return s


@pytest.mark.parametrize("path", [
    "/api/auth/me",
    "/api/tenants/me",
    "/api/dashboard/b2c",
    "/api/dashboard/b2b-founder",
    "/api/dashboard/b2b-sales",
    "/api/dashboard/integration-showcase",
])
def test_endpoint_ok(auth, path):
    r = auth.get(f"{BASE_URL}{path}", timeout=30)
    assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:300]}"
    # basic JSON check
    try:
        r.json()
    except Exception as e:
        pytest.fail(f"{path} returned non-JSON: {e}")
