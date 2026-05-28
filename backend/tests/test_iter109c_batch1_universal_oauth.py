"""iter109c Batch 1 — Universal OAuth backend tests.

Verifies:
  V3 — configure → auth-url roundtrip (Calendly)
  V4 — DB stores client_id + client_secret with enc:: prefix
  V5 — saleshandy /test responds 200 (not 500) for connected provider
  V6 — DELETE /api/integrations/{provider} clears the doc
  V7 — frontend registry contains 13 entries (sanity smoke via file read)
  V8 — Pietential saleshandy legacy migration (status reports connected)
  V9 — backend/.env has no forbidden OAuth CLIENT_ID/CLIENT_SECRET keys
  V10 — auth-url redirect_uri starts with FRONTEND_URL
"""
import os
import re
import urllib.parse

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "genleadai_lms")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://pipeline-pro-96.preview.emergentagent.com")

ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASS = "Demo1234!"
MEGHA_EMAIL = "megha@contentvista.com"
MEGHA_PASS = "Piet-4vRQ-lDa2-ttcO"

TEN_DEMO = "ten_demo"
TEN_PIE = "ten_pietential"


@pytest.fixture(scope="module")
def mongo():
    client = MongoClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    body = r.json()
    return body.get("token") or body.get("access_token")


@pytest.fixture(scope="module")
def demo_headers():
    token = _login(ADMIN_EMAIL, ADMIN_PASS)
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": TEN_DEMO, "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def pie_headers():
    token = _login(MEGHA_EMAIL, MEGHA_PASS)
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": TEN_PIE, "Content-Type": "application/json"}


# ── V3 + V4 + V10 ──────────────────────────────────────────────────────
class TestConfigureAuthUrl:
    def test_calendly_configure_returns_configured_true(self, demo_headers):
        body = {
            "client_id": "TEST_calendly_client_id_abc123",
            "client_secret": "TEST_calendly_client_secret_xyz789",
        }
        r = requests.post(
            f"{BASE_URL}/api/integrations/calendly/configure",
            headers=demo_headers,
            json=body,
            timeout=15,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        data = r.json()
        assert data.get("configured") is True
        assert data.get("provider") == "calendly"

    def test_calendly_auth_url_contains_calendly_decrypted_client_id_and_redirect(self, demo_headers):
        r = requests.get(
            f"{BASE_URL}/api/integrations/calendly/auth-url",
            headers=demo_headers,
            timeout=15,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        data = r.json()
        url = data.get("auth_url", "")
        assert "auth.calendly.com" in url, f"missing calendly host: {url}"
        # V3 — decrypted client_id present
        assert "TEST_calendly_client_id_abc123" in url, f"decrypted client_id NOT in url: {url}"
        # V10 — redirect_uri starts with FRONTEND_URL
        qs = urllib.parse.urlparse(url).query
        params = urllib.parse.parse_qs(qs)
        redirect_uri = params.get("redirect_uri", [""])[0]
        assert redirect_uri.startswith(FRONTEND_URL), f"redirect_uri does not start with FRONTEND_URL: {redirect_uri}"
        assert redirect_uri.endswith("/api/integrations/calendly/callback"), f"bad callback path: {redirect_uri}"
        assert data.get("state"), "missing state token"

    def test_v4_db_stores_client_id_and_secret_with_enc_prefix(self, mongo):
        doc = mongo["integration_configs"].find_one(
            {"tenant_id": TEN_DEMO, "integration_type": "calendly"}
        )
        assert doc is not None, "calendly config not persisted"
        cfg = doc.get("config") or {}
        cid = cfg.get("client_id", "")
        csec = cfg.get("client_secret", "")
        assert isinstance(cid, str) and cid.startswith("enc::"), f"client_id not encrypted: {cid[:20]}"
        assert isinstance(csec, str) and csec.startswith("enc::"), f"client_secret not encrypted: {csec[:20]}"


# ── V5 ──────────────────────────────────────────────────────────────────
class TestSaleshandyTest:
    def test_saleshandy_test_responds_200_for_pietential(self, pie_headers):
        # Ensure status is fetched first to trigger legacy migration
        s = requests.get(
            f"{BASE_URL}/api/integrations/saleshandy/status",
            headers=pie_headers,
            timeout=15,
        )
        assert s.status_code == 200

        r = requests.post(
            f"{BASE_URL}/api/integrations/saleshandy/test",
            headers=pie_headers,
            timeout=20,
        )
        # V5 — MUST be 200 (not 500). valid may be true/false depending on API key.
        assert r.status_code == 200, f"saleshandy /test returned non-200: {r.status_code} {r.text}"
        body = r.json()
        assert "valid" in body or "message" in body, f"unexpected shape: {body}"


# ── V6 ──────────────────────────────────────────────────────────────────
class TestDisconnect:
    def test_delete_calendly_then_status_shows_not_configured(self, demo_headers, mongo):
        # ensure there's a doc (created by V3) — re-configure if absent
        existing = mongo["integration_configs"].find_one(
            {"tenant_id": TEN_DEMO, "integration_type": "calendly"}
        )
        if not existing:
            requests.post(
                f"{BASE_URL}/api/integrations/calendly/configure",
                headers=demo_headers,
                json={"client_id": "TEST_x", "client_secret": "TEST_y"},
                timeout=15,
            )

        d = requests.delete(
            f"{BASE_URL}/api/integrations/calendly",
            headers=demo_headers,
            timeout=15,
        )
        assert d.status_code == 200, f"{d.status_code} {d.text}"

        # status must now report not configured / not connected
        s = requests.get(
            f"{BASE_URL}/api/integrations/calendly/status",
            headers=demo_headers,
            timeout=15,
        )
        assert s.status_code == 200
        data = s.json()
        assert data.get("connected") is False, f"still connected after DELETE: {data}"
        assert data.get("configured") is False, f"still configured after DELETE: {data}"

        # raw DB check — doc gone
        doc = mongo["integration_configs"].find_one(
            {"tenant_id": TEN_DEMO, "integration_type": "calendly"}
        )
        assert doc is None, f"DB doc still present after DELETE: {doc}"


# ── V8 ──────────────────────────────────────────────────────────────────
class TestPietentialSaleshandyMigration:
    def test_pietential_saleshandy_status_connected(self, pie_headers, mongo):
        r = requests.get(
            f"{BASE_URL}/api/integrations/saleshandy/status",
            headers=pie_headers,
            timeout=15,
        )
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "connected", f"expected connected, got: {data}"
        assert data.get("configured") is True
        assert data.get("connected") is True

        # DB has the mirror with api_key encrypted
        doc = mongo["integration_configs"].find_one(
            {"tenant_id": TEN_PIE, "integration_type": "saleshandy"}
        )
        assert doc is not None, "saleshandy not mirrored to integration_configs"
        api_key = (doc.get("config") or {}).get("api_key", "")
        assert isinstance(api_key, str) and api_key.startswith("enc::"), f"api_key not encrypted: {api_key[:20]}"


# ── V9 ──────────────────────────────────────────────────────────────────
class TestEnvAudit:
    def test_no_forbidden_oauth_client_ids_in_backend_env(self):
        forbidden = [
            "CALENDLY_CLIENT_ID", "CALENDLY_CLIENT_SECRET",
            "GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET",
            "MICROSOFT_CLIENT_ID", "MICROSOFT_CLIENT_SECRET",
            "META_APP_ID", "META_APP_SECRET",
            "LINKEDIN_CLIENT_ID", "LINKEDIN_CLIENT_SECRET",
            "GOOGLE_ADS_CLIENT_ID", "GOOGLE_ADS_CLIENT_SECRET",
        ]
        with open("/app/backend/.env", "r") as f:
            env_text = f.read()
        # Only flag uncommented lines
        for line in env_text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            key = stripped.split("=", 1)[0].strip()
            assert key not in forbidden, f"FORBIDDEN OAuth credential in backend/.env: {key}"
        # FRONTEND_URL must be present
        assert "FRONTEND_URL=" in env_text, "FRONTEND_URL not set in backend/.env"


# ── V7 (file sanity) ────────────────────────────────────────────────────
class TestFrontendRegistry:
    def test_registry_has_13_entries(self):
        with open("/app/frontend/src/config/integrations.js", "r") as f:
            src = f.read()
        # count id: '...' lines inside INTEGRATIONS array
        ids = re.findall(r"^\s+id:\s*['\"]([a-z0-9_-]+)['\"]", src, flags=re.M)
        assert len(ids) == 13, f"expected 13 integration ids, found {len(ids)}: {ids}"
        # Must include the 5 OAuth providers + saleshandy
        for required in ("google", "microsoft", "meta", "linkedin", "calendly", "saleshandy"):
            assert required in ids, f"missing required provider {required}"


# ── /providers/list catalogue smoke ─────────────────────────────────────
class TestProvidersCatalogue:
    def test_list_providers_returns_5_oauth(self, demo_headers):
        r = requests.get(f"{BASE_URL}/api/integrations/providers/list", headers=demo_headers, timeout=15)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        data = r.json()
        ids = [p["id"] for p in data.get("providers", [])]
        for required in ("google", "microsoft", "meta", "linkedin", "calendly"):
            assert required in ids, f"backend catalogue missing {required}"
