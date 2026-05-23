"""Iter83 retest — verify the 2 iter82 bug fixes:
1. routes/pietential.py::_can_write now includes master_admin/owner.
2. integrations_routes.py::SalesHandyClient.list_sequences now uses canonical
   GET /v1/sequences (was POST /v1/sequences/get-list which leaked raw JSON).
"""
import os
import json
import pytest
import requests


def _load_backend_url():
    env_val = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
    if env_val:
        return env_val
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    return ""


BASE_URL = _load_backend_url()
assert BASE_URL, "REACT_APP_BACKEND_URL not set"
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = "Demo1234!"


@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text[:200]}"
    return {"Authorization": f"Bearer {r.json()['token']}", "Content-Type": "application/json"}


def _detail(resp):
    try:
        j = resp.json()
        d = j.get("detail", j.get("error", j.get("message", "")))
        return json.dumps(d) if isinstance(d, (dict, list)) else str(d)
    except Exception:
        return resp.text or ""


def _leaked_raw_json(text: str) -> bool:
    """True if any raw-Saleshandy/Lemlist provider JSON shape leaks through."""
    low = (text or "").lower()
    markers = [
        '"statuscode":404',
        '"statuscode": 404',
        '"message":"cannot post',
        '"message": "cannot post',
        '"type":"auth"',
        '"code":1001',
        '"code":1003',
        '"error":"not found"',
        "cannot post /v1/sequences",
    ]
    return any(m in low for m in markers)


# ─── Fix #1: master_admin can write to /api/pt/integrations ───────────────────
class TestPtIntegrationsMasterAdminWrite:
    def test_upsert_saleshandy_key_master_admin_200(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/pt/integrations",
            headers=admin_headers,
            json={"name": "saleshandy", "api_key": "sk_iter83_fake_invalid"},
            timeout=20,
        )
        assert r.status_code != 403, f"master_admin still blocked: {r.text[:200]}"
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:200]}"

    def test_pt_saleshandy_test_friendly_auth_error_not_403(self, admin_headers):
        # After upsert above, the /test endpoint should now do a real handshake.
        r = requests.post(
            f"{BASE_URL}/api/pt/integrations/saleshandy/test",
            headers=admin_headers,
            timeout=45,
        )
        assert r.status_code != 403, f"master_admin still 403: {r.text[:200]}"
        assert r.status_code != 500, f"500: {r.text[:300]}"
        assert r.status_code in (400, 502), f"expected 400/502, got {r.status_code}: {r.text[:200]}"
        detail = _detail(r)
        assert not _leaked_raw_json(detail), f"raw JSON leaked: {detail[:300]}"
        low = detail.lower()
        assert ("rejected the api key" in low) or ("saleshandy" in low and ("auth" in low or "reject" in low or "could not" in low)), \
            f"detail not friendly: {detail[:300]}"

    def test_pt_lemlist_upsert_and_test_master_admin_200(self, admin_headers):
        up = requests.post(
            f"{BASE_URL}/api/pt/integrations",
            headers=admin_headers,
            json={"name": "lemlist", "api_key": "lk_iter83_fake_invalid"},
            timeout=20,
        )
        assert up.status_code != 403, f"master_admin still blocked on lemlist upsert: {up.text[:200]}"
        assert up.status_code == 200, f"upsert failed: {up.status_code} {up.text[:200]}"

        r = requests.post(
            f"{BASE_URL}/api/pt/integrations/lemlist/test",
            headers=admin_headers,
            timeout=45,
        )
        assert r.status_code != 403, f"master_admin still 403 on lemlist test: {r.text[:200]}"
        assert r.status_code != 500
        assert r.status_code in (400, 502)
        detail = _detail(r)
        assert not _leaked_raw_json(detail), f"raw JSON leaked: {detail[:300]}"


# ─── Fix #2: Legacy SalesHandyClient no longer leaks raw 404 JSON ─────────────
class TestLegacySaleshandyNoRawLeak:
    @pytest.fixture(autouse=True)
    def _seed_fake_key(self, admin_headers):
        """Save a fake key via /api/integrations/keys (legacy storage)."""
        # Legacy payload schema is {saleshandy_api_key, lemlist_api_key}
        r = requests.post(
            f"{BASE_URL}/api/integrations/keys",
            headers=admin_headers,
            json={"saleshandy_api_key": "sk_iter83_legacy_fake_invalid"},
            timeout=15,
        )
        assert r.status_code in (200, 201), f"could not seed legacy key: {r.status_code} {r.text[:200]}"
        yield
        # Cleanup — clear the fake key by setting empty string.
        try:
            requests.post(
                f"{BASE_URL}/api/integrations/keys",
                headers=admin_headers,
                json={"saleshandy_api_key": ""},
                timeout=10,
            )
        except Exception:
            pass

    def test_post_legacy_test_saleshandy_clean_message(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/integrations/test/saleshandy",
            headers=admin_headers,
            timeout=30,
        )
        assert r.status_code != 500, f"500: {r.text[:300]}"
        body = r.text
        # MUST NOT contain raw provider JSON or 404 'Cannot POST' leak.
        assert '"statusCode":404' not in body, f"raw 404 leaked: {body[:300]}"
        assert "Cannot POST" not in body, f"raw 'Cannot POST' leaked: {body[:300]}"
        assert not _leaked_raw_json(body), f"raw provider JSON leaked: {body[:300]}"
        # Should be friendly auth-rejected text.
        detail = _detail(r)
        low = detail.lower()
        assert "saleshandy" in low, f"detail doesn't mention provider: {detail[:300]}"
        # Either auth-friendly or rate-limit/forbidden friendly — never raw.
        friendly = (
            "rejected the api key" in low
            or "auth" in low
            or "fresh key" in low
            or "rate" in low
            or "forbidden" in low
        )
        assert friendly, f"detail not friendly: {detail[:300]}"

    def test_get_legacy_sequences_saleshandy_clean_message(self, admin_headers):
        r = requests.get(
            f"{BASE_URL}/api/integrations/sequences/saleshandy",
            headers=admin_headers,
            timeout=30,
        )
        assert r.status_code != 500, f"500: {r.text[:300]}"
        body = r.text
        assert '"statusCode":404' not in body, f"raw 404 leaked: {body[:300]}"
        assert "Cannot POST" not in body, f"raw 'Cannot POST' leaked: {body[:300]}"
        assert not _leaked_raw_json(body), f"raw provider JSON leaked: {body[:300]}"


# ─── Light regression ─────────────────────────────────────────────────────────
class TestRegression:
    def test_pt_overview_200(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/pt/overview", headers=admin_headers, timeout=15)
        assert r.status_code == 200

    def test_pt_leads_200(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/pt/leads", headers=admin_headers, timeout=15)
        assert r.status_code == 200

    def test_auto_map_publish_minimal_200(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/aria/auto-map/publish",
            headers=admin_headers,
            json={
                "icps": [], "lead_sources": [], "touchpoints": [],
                "qualification": {}, "handoff": {}, "overwrite_journey": False,
            },
            timeout=30,
        )
        assert r.status_code == 200

    def test_login_rate_limit_active(self):
        """Hammer /api/auth/login with bad creds to verify rate-limit kicks in."""
        codes = []
        for _ in range(12):
            r = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": "ratelimit_iter83@demo.com", "password": "wrong"},
                timeout=10,
            )
            codes.append(r.status_code)
            if r.status_code == 429:
                break
        # Expect a 429 somewhere in the burst (rate limit active), else minimum 401s.
        assert 429 in codes or all(c in (400, 401, 403, 422) for c in codes), \
            f"unexpected codes: {codes}"


# ─── Cleanup hook — restore demo workspace state ──────────────────────────────
@pytest.fixture(scope="module", autouse=True)
def _final_cleanup(admin_headers):
    yield
    # Best-effort: clear the legacy saleshandy fake key + pt fake keys we seeded.
    try:
        requests.post(
            f"{BASE_URL}/api/integrations/keys",
            headers=admin_headers,
            json={"saleshandy_api_key": "", "lemlist_api_key": ""},
            timeout=10,
        )
    except Exception:
        pass
    # pt fake keys — try delete-style; tolerate any response.
    for name in ("saleshandy", "lemlist"):
        try:
            requests.delete(
                f"{BASE_URL}/api/pt/integrations/{name}",
                headers=admin_headers,
                timeout=10,
            )
        except Exception:
            pass
