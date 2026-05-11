"""Iter42 backend tests:
- Notifications preferences (GET + PUT, admin-only enforcement)
- Platform Stats (admin only)
- WA widget click tracker (public)
- /aria-wa-widget.js static asset serving
- WhatsApp webhook HMAC verification (no secret env → warn-allow path)
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")
TENANT_ID = "ten_demo"


# ────────────── fixtures ──────────────
@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "admin@demo.com", "password": "Demo1234!"})
    assert r.status_code == 200, f"admin login failed: {r.text[:200]}"
    return r.json()["token"]


@pytest.fixture(scope="session")
def sarah_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "sarah@demo.com", "password": "Demo1234!"})
    assert r.status_code == 200, f"sarah login failed: {r.text[:200]}"
    return r.json()["token"]


def _headers(tok):
    return {"Authorization": f"Bearer {tok}", "X-Tenant-Id": TENANT_ID,
            "Content-Type": "application/json"}


# ────────────── Notifications ──────────────
EXPECTED_EVENT_KEYS = {
    "new_hot_lead", "stale_lead_alert", "failed_message",
    "weekly_recap", "daily_brief", "aria_escalation", "meeting_booked",
}


class TestNotificationPrefs:
    def test_get_preferences_returns_full_schema(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/notifications/preferences",
                         headers=_headers(admin_token))
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert "preferences" in data and "event_keys" in data
        prefs = data["preferences"]
        assert prefs["tenant_id"] == TENANT_ID
        assert set(data["event_keys"]) == EXPECTED_EVENT_KEYS
        assert set(prefs["events"].keys()) >= EXPECTED_EVENT_KEYS
        for k, v in prefs["events"].items():
            assert "email" in v and "in_app" in v
            assert isinstance(v["email"], bool) and isinstance(v["in_app"], bool)
        assert "quiet_hours_enabled" in prefs
        assert "quiet_start_hour" in prefs
        assert "quiet_end_hour" in prefs

    def test_put_preferences_persists(self, admin_token):
        payload = {
            "events": {
                "new_hot_lead":    {"email": False, "in_app": True},
                "meeting_booked":  {"email": True,  "in_app": True},
                "failed_message":  {"email": True,  "in_app": False},
                "stale_lead_alert":{"email": False, "in_app": True},
                "weekly_recap":    {"email": True,  "in_app": False},
                "daily_brief":     {"email": True,  "in_app": True},
                "aria_escalation": {"email": True,  "in_app": True},
            },
            "quiet_hours_enabled": True,
            "quiet_start_hour": 21,
            "quiet_end_hour": 7,
        }
        r = requests.put(f"{BASE_URL}/api/notifications/preferences",
                         headers=_headers(admin_token), json=payload)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data.get("ok") is True
        prefs = data["preferences"]
        assert prefs["quiet_hours_enabled"] is True
        assert prefs["quiet_start_hour"] == 21
        assert prefs["quiet_end_hour"] == 7
        assert prefs["events"]["new_hot_lead"]["email"] is False
        assert prefs["events"]["new_hot_lead"]["in_app"] is True
        assert prefs["events"]["meeting_booked"]["email"] is True

        # GET again to verify persistence
        r2 = requests.get(f"{BASE_URL}/api/notifications/preferences",
                          headers=_headers(admin_token))
        p2 = r2.json()["preferences"]
        assert p2["quiet_start_hour"] == 21
        assert p2["events"]["new_hot_lead"]["email"] is False

    def test_put_preferences_forbidden_for_non_admin(self, sarah_token):
        r = requests.put(f"{BASE_URL}/api/notifications/preferences",
                         headers=_headers(sarah_token),
                         json={"events": {}, "quiet_hours_enabled": False,
                               "quiet_start_hour": 22, "quiet_end_hour": 8})
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text[:200]}"


# ────────────── Platform stats (master admin) ──────────────
class TestPlatformStats:
    EXPECTED_KEYS = {
        "total_workspaces", "active_paying_clients", "trial_workspaces",
        "total_leads", "total_conversations", "messages_sent_24h",
        "failed_messages_24h", "claude_calls_today", "claude_cost_today_usd",
    }

    def test_admin_gets_platform_stats(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/admin/workspaces/platform/stats",
                         headers=_headers(admin_token))
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert self.EXPECTED_KEYS.issubset(set(data.keys())), \
            f"missing keys: {self.EXPECTED_KEYS - set(data.keys())}"
        # Type sanity
        for k in self.EXPECTED_KEYS:
            assert isinstance(data[k], (int, float)), f"{k} should be numeric, got {type(data[k])}"

    def test_sales_rep_denied_platform_stats(self, sarah_token):
        r = requests.get(f"{BASE_URL}/api/admin/workspaces/platform/stats",
                         headers=_headers(sarah_token))
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text[:200]}"


# ────────────── WA widget click tracker ──────────────
class TestWaWidgetClick:
    def test_wa_click_no_auth(self):
        payload = {
            "tenant_id": TENANT_ID,
            "phone": "+919999999999",
            "page_url": "https://example.com/landing",
            "referrer": "https://google.com",
        }
        r = requests.post(f"{BASE_URL}/api/integrations/widget/wa-click",
                          json=payload)
        assert r.status_code == 200, r.text[:300]
        assert r.json().get("ok") is True


# ────────────── Static asset /aria-wa-widget.js ──────────────
class TestAriaWaWidgetJs:
    def test_widget_js_served(self):
        r = requests.get(f"{BASE_URL}/aria-wa-widget.js")
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:200]}"
        # Some servers may return text/javascript or application/javascript or text/html depending on ingress
        body = r.text
        assert "Aria Click-to-WhatsApp" in body or "wa.me" in body, \
            f"widget JS doesn't have expected content: {body[:200]}"


# ────────────── WhatsApp webhook HMAC ──────────────
class TestWhatsAppWebhookHMAC:
    def test_no_signature_passes_through(self):
        # No header at all → 200 (current env has no WHATSAPP_APP_SECRET)
        r = requests.post(f"{BASE_URL}/api/webhooks/whatsapp",
                          json={"entry": []})
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:200]}"

    def test_bogus_signature_warn_allow_when_no_secret(self):
        # Env has no WHATSAPP_APP_SECRET → bogus sig is allowed with warn (per spec)
        r = requests.post(f"{BASE_URL}/api/webhooks/whatsapp",
                          headers={"X-Hub-Signature-256": "sha256=bogus"},
                          json={"entry": []})
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:200]}"
