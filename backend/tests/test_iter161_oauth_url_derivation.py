"""iter161 — Verify OAuth _api_base/_redirect_uri derive from request headers,
not the hardcoded PUBLIC_API_BASE_URL env var.

Scope:
 - Direct import unit tests on `_api_base` / `_redirect_uri`.
 - HTTP regression: /connect returns 503 (not 500) with correct message,
   DELETE returns 404, login+tenants+dashboards still work.
"""
import os
import sys
import pytest
import requests

# Ensure backend on sys.path for direct-import tests
sys.path.insert(0, "/app/backend")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")


# ─── Direct import: _api_base / _redirect_uri ────────────────────────────────
class FakeURL:
    def __init__(self, s):
        self._s = s
    def __str__(self):
        return self._s

class FakeRequest:
    def __init__(self, headers=None, base_url="http://localhost:8001/"):
        self.headers = headers or {}
        self.base_url = FakeURL(base_url)


class TestApiBaseDerivation:
    def test_derives_from_x_forwarded_headers_preview(self):
        from routes.oauth_integrations import _api_base
        req = FakeRequest(headers={
            "x-forwarded-proto": "https",
            "x-forwarded-host": "preview.example.com",
        })
        assert _api_base(req) == "https://preview.example.com"

    def test_derives_from_x_forwarded_headers_production(self):
        from routes.oauth_integrations import _api_base
        req = FakeRequest(headers={
            "x-forwarded-proto": "https",
            "x-forwarded-host": "app.genleadai.com",
        })
        assert _api_base(req) == "https://app.genleadai.com"

    def test_preview_host_does_not_return_production_env(self):
        """Regression: the whole point of iter161."""
        from routes.oauth_integrations import _api_base
        req = FakeRequest(headers={
            "x-forwarded-proto": "https",
            "x-forwarded-host": "pipeline-pro-96.preview.emergentagent.com",
        })
        result = _api_base(req)
        assert "app.genleadai.com" not in result
        assert result == "https://pipeline-pro-96.preview.emergentagent.com"

    def test_falls_back_to_env_when_no_request(self):
        from routes.oauth_integrations import _api_base
        result = _api_base(None)
        # PUBLIC_API_BASE_URL is set to https://app.genleadai.com in backend/.env
        assert result == "https://app.genleadai.com"

    def test_falls_back_to_base_url_when_no_forwarded_headers(self):
        from routes.oauth_integrations import _api_base
        req = FakeRequest(headers={}, base_url="https://someorigin.example.com/")
        assert _api_base(req) == "https://someorigin.example.com"

    def test_ignores_localhost_base_url(self):
        from routes.oauth_integrations import _api_base
        req = FakeRequest(headers={}, base_url="http://localhost:8001/")
        # Should NOT return localhost — should fall through to env var
        result = _api_base(req)
        assert "localhost" not in result

    def test_redirect_uri_uses_request_host(self):
        from routes.oauth_integrations import _redirect_uri
        req = FakeRequest(headers={
            "x-forwarded-proto": "https",
            "x-forwarded-host": "pipeline-pro-96.preview.emergentagent.com",
        })
        uri = _redirect_uri("calendly", req)
        assert uri == "https://pipeline-pro-96.preview.emergentagent.com/api/integrations/calendly/callback"
        assert "app.genleadai.com" not in uri

    def test_redirect_uri_all_providers(self):
        from routes.oauth_integrations import _redirect_uri, PROVIDERS
        req = FakeRequest(headers={
            "x-forwarded-proto": "https",
            "x-forwarded-host": "preview.emergentagent.com",
        })
        for provider in PROVIDERS.keys():
            uri = _redirect_uri(provider, req)
            assert uri == f"https://preview.emergentagent.com/api/integrations/{provider}/callback"


# ─── HTTP regression tests ──────────────────────────────────────────────────
@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "admin@demo.com", "password": "Demo1234!"},
                      timeout=15)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    assert "token" in data
    return data["token"]


@pytest.fixture
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


class TestOAuthEndpointRegression:
    def test_calendly_connect_returns_503_not_configured(self, auth_headers):
        """No CALENDLY_CLIENT_ID env — should return 503 with clear message.
        Must NOT 500 (would indicate signature-mismatch after iter161 changes)."""
        r = requests.get(f"{BASE_URL}/api/integrations/calendly/connect",
                         headers=auth_headers, timeout=15)
        assert r.status_code == 503, f"Expected 503, got {r.status_code}: {r.text}"
        body = r.json()
        detail = body.get("detail", "")
        assert "CALENDLY_CLIENT_ID" in detail
        assert "CALENDLY_CLIENT_SECRET" in detail

    def test_calendly_disconnect_returns_404_not_connected(self, auth_headers):
        r = requests.delete(f"{BASE_URL}/api/integrations/calendly",
                            headers=auth_headers, timeout=15)
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"
        assert "not connected" in r.json().get("detail", "").lower()

    def test_unknown_provider_returns_404(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/integrations/bogusprovider/connect",
                         headers=auth_headers, timeout=15)
        assert r.status_code == 404

    def test_all_providers_return_503_not_500(self, auth_headers):
        """Verify /connect works for all providers (no signature errors)."""
        providers = ["calendly", "gmail", "outlook", "meta", "linkedin", "googleads"]
        for p in providers:
            r = requests.get(f"{BASE_URL}/api/integrations/{p}/connect",
                             headers=auth_headers, timeout=15)
            assert r.status_code == 503, f"{p}: got {r.status_code} {r.text[:200]}"


# ─── Regression: login/tenants/dashboards ───────────────────────────────────
class TestUnrelatedRegression:
    def test_login(self):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": "admin@demo.com", "password": "Demo1234!"},
                          timeout=15)
        assert r.status_code == 200
        assert "token" in r.json()

    def test_tenants_me_returns_only_ten_demo(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/tenants/me", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        # Response could be a list or a dict with tenants field
        tenants = data if isinstance(data, list) else data.get("tenants", data.get("memberships", []))
        assert len(tenants) == 1, f"Expected 1 tenant, got {len(tenants)}: {tenants}"
        # Verify it's ten_demo
        t = tenants[0]
        tid = t.get("tenant_id") or t.get("id") or (t.get("tenant") or {}).get("id")
        assert tid == "ten_demo", f"Expected ten_demo, got {tid}"

    def test_integration_showcase_54_items(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/dashboard/integration-showcase",
                         headers=auth_headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        items = data.get("items") or data.get("integrations") or (data if isinstance(data, list) else [])
        assert len(items) == 54, f"Expected 54 showcase items, got {len(items)}"

    def test_b2c_dashboard(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/dashboard/b2c", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        # Should return a payload (dict) not empty
        data = r.json()
        assert isinstance(data, dict)
        assert len(data) > 0
