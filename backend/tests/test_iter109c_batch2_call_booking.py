"""iter109c Batch 2 — Call Booking + Google scope picker + audit trail tests.

Order (per agent_to_agent note):
  V1  GET  /api/call-booking/settings → default + provider_status
  V2  PUT  /api/call-booking/settings → persists, GET returns same
  V3  POST /api/call-booking/book → 412 when Google calendar scope absent
  V4  GET  /api/call-booking/bookings → empty list, count 0
  V5  POST /api/call-booking/no-show-check → empty flagged list
  V6  Saleshandy audit-on-configure → connected_by_name populated
  V7  Google scope narrowing — configure with scopes=[gmail.send] → auth-url
      contains gmail.send but NOT calendar.events / adwords
"""
import os
import time
import requests
import pytest

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = "Demo1234!"
TENANT_DEMO = "ten_demo"


@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    token = r.json().get("token") or r.json().get("access_token")
    assert token, f"No token in login response: {r.json()}"
    s.headers.update({
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": TENANT_DEMO,
    })
    return s


# ─── Pre-clean: remove any existing google config on ten_demo so V3 412s ──
@pytest.fixture(scope="module", autouse=True)
def cleanup_google(admin_client):
    # Best-effort delete so V3 (book → 412) is deterministic
    admin_client.delete(f"{BASE_URL}/api/integrations/google")
    yield


# ─── V1 ──────────────────────────────────────────────────────────────────
class TestCallBookingSettings:
    def test_v1_get_settings_returns_default_with_provider_status(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/call-booking/settings")
        assert r.status_code == 200, f"GET /settings: {r.status_code} {r.text[:200]}"
        data = r.json()
        # Default fields exist
        assert "timezone" in data
        assert "default_duration" in data
        assert "buffer_minutes" in data
        assert "availability" in data
        assert isinstance(data["availability"], list)
        assert "provider_status" in data
        assert isinstance(data["provider_status"], dict)
        assert "google_connected" in data["provider_status"]

    # ─── V2 ──────────────────────────────────────────────────────────────
    def test_v2_put_settings_persists_then_get_returns_saved_values(self, admin_client):
        payload = {
            "timezone": "America/Los_Angeles",
            "default_duration": 45,
            "buffer_minutes": 30,
            "max_calls_per_day": 4,
            "confirmation_message": "TEST_confirm {WHEN} {MEET_LINK}",
            "pre_call_questions": ["What's your team size?", "Budget?"],
            "availability": [
                {"day_of_week": 1, "start": "10:00", "end": "16:00"},
                {"day_of_week": 3, "start": "11:00", "end": "17:00"},
            ],
            "durations": [30, 45, 60],
            "reminder_minutes_before": 30,
            "provider": "google",
        }
        r = admin_client.put(f"{BASE_URL}/api/call-booking/settings", json=payload)
        assert r.status_code == 200, f"PUT /settings: {r.status_code} {r.text[:300]}"
        saved = r.json()
        assert saved.get("saved") is True
        assert saved["timezone"] == "America/Los_Angeles"
        assert saved["default_duration"] == 45

        # GET back
        r2 = admin_client.get(f"{BASE_URL}/api/call-booking/settings")
        assert r2.status_code == 200
        d = r2.json()
        assert d["timezone"] == "America/Los_Angeles"
        assert d["default_duration"] == 45
        assert d["buffer_minutes"] == 30
        assert d["max_calls_per_day"] == 4
        assert d["confirmation_message"] == "TEST_confirm {WHEN} {MEET_LINK}"
        assert d["pre_call_questions"] == ["What's your team size?", "Budget?"]
        assert len(d["availability"]) == 2
        assert d["availability"][0]["day_of_week"] == 1


# ─── V3 ──────────────────────────────────────────────────────────────────
class TestBookGuardedByGoogle:
    def test_v3_book_without_google_calendar_scope_returns_412(self, admin_client):
        body = {
            "lead_id": "TEST_lead_001",
            "lead_name": "Test Lead",
            "lead_email": "lead@example.com",
            "lead_channel": "email",
            "scheduled_for": "2026-02-15T10:00:00+00:00",
        }
        r = admin_client.post(f"{BASE_URL}/api/call-booking/book", json=body)
        assert r.status_code == 412, f"Expected 412, got {r.status_code} {r.text[:300]}"
        detail = (r.json().get("detail") or "").lower()
        assert "google" in detail and "calendar" in detail, \
            f"Expected message about Google+Calendar, got: {detail}"


# ─── V4 ──────────────────────────────────────────────────────────────────
class TestListBookings:
    def test_v4_list_bookings_returns_empty(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/call-booking/bookings")
        assert r.status_code == 200, f"GET /bookings: {r.status_code} {r.text[:200]}"
        data = r.json()
        assert "bookings" in data and "count" in data
        assert isinstance(data["bookings"], list)
        # On fresh tenant should be empty (no successful book calls yet)
        assert data["count"] == 0
        assert data["bookings"] == []


# ─── V5 ──────────────────────────────────────────────────────────────────
class TestNoShowCheck:
    def test_v5_no_show_check_empty(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/call-booking/no-show-check")
        assert r.status_code == 200, f"POST /no-show-check: {r.status_code} {r.text[:200]}"
        d = r.json()
        assert "flagged_no_show" in d and "count" in d
        assert isinstance(d["flagged_no_show"], list)
        assert d["count"] == 0


# ─── V6 ──────────────────────────────────────────────────────────────────
class TestSaleshandyAuditOnConfigure:
    def test_v6_configure_api_key_then_status_returns_connected_by_name(self, admin_client):
        r = admin_client.post(
            f"{BASE_URL}/api/integrations/saleshandy/configure-api-key",
            json={"api_key": "TEST_saleshandy_audit_key_xyz789"},
        )
        assert r.status_code == 200, f"configure-api-key: {r.status_code} {r.text[:300]}"

        s = admin_client.get(f"{BASE_URL}/api/integrations/saleshandy/status")
        assert s.status_code == 200, f"status: {s.status_code} {s.text[:300]}"
        sd = s.json()
        assert sd.get("connected") is True
        cb = sd.get("connected_by_name")
        assert cb, f"connected_by_name missing in status: {sd}"
        assert cb.lower() != "unknown", f"connected_by_name should be a real name, got: {cb}"
        # Should be the admin's email or full_name
        assert (
            "admin@demo.com" in cb.lower()
            or "megha" in cb.lower()
            or "admin" in cb.lower()
            or "@" in cb
        ), f"Unexpected connected_by_name: {cb}"


# ─── V7 ──────────────────────────────────────────────────────────────────
class TestGoogleScopeNarrowing:
    def test_v7_configure_with_narrow_scopes_then_auth_url_contains_only_those(self, admin_client):
        # Configure with only gmail.send scope
        r = admin_client.post(
            f"{BASE_URL}/api/integrations/google/configure",
            json={
                "client_id": "TEST_google_client_id_narrow",
                "client_secret": "TEST_google_client_secret_narrow",
                "scopes": ["https://www.googleapis.com/auth/gmail.send"],
            },
        )
        assert r.status_code == 200, f"configure google: {r.status_code} {r.text[:300]}"
        assert r.json().get("configured") is True

        # Build auth URL
        au = admin_client.get(f"{BASE_URL}/api/integrations/google/auth-url")
        assert au.status_code == 200, f"auth-url: {au.status_code} {au.text[:300]}"
        url = au.json().get("auth_url") or ""
        assert "gmail.send" in url, f"auth_url missing gmail.send: {url[:400]}"
        assert "calendar.events" not in url, f"auth_url should NOT include calendar.events: {url[:400]}"
        assert "adwords" not in url, f"auth_url should NOT include adwords: {url[:400]}"
        assert "calendar.readonly" not in url, f"auth_url should NOT include calendar.readonly: {url[:400]}"


# ─── Cleanup ─────────────────────────────────────────────────────────────
@pytest.fixture(scope="module", autouse=True)
def final_cleanup(admin_client):
    yield
    # Best-effort: revert google config so future runs are clean
    try:
        admin_client.delete(f"{BASE_URL}/api/integrations/google")
        admin_client.delete(f"{BASE_URL}/api/integrations/saleshandy")
    except Exception:
        pass
