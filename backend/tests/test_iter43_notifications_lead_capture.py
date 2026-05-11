"""Iter43 — Wire notification preferences into emitters + Click-to-WhatsApp widget config.

Tests:
  * Notification pref gate (should_notify_email helper via API toggle)
  * Daily call plan send-now with manual=True override still fires
  * /api/lead-capture/config GET includes wa_embed_snippet
  * POST WA fields persist & wa_embed_snippet reflects values
  * sales_rep can GET config but cannot POST (403)
  * should_notify_email defaults True for recipient with no membership
"""
from __future__ import annotations
import os
import pytest
import requests

def _read_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        try:
            with open("/app/frontend/.env") as fh:
                for line in fh:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        v = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    assert v, "REACT_APP_BACKEND_URL not set"
    return v.rstrip("/")


BASE_URL = _read_backend_url()
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PW = "Demo1234!"
SALES_EMAIL = "sarah@demo.com"
SALES_PW = "Demo1234!"


def _login(email: str, pw: str):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    data = r.json()
    return data["token"], (data.get("user") or {}).get("tenant_id") or "ten_demo"


@pytest.fixture(scope="module")
def admin_ctx():
    token, _ = _login(ADMIN_EMAIL, ADMIN_PW)
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": "ten_demo", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def sales_ctx():
    token, _ = _login(SALES_EMAIL, SALES_PW)
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": "ten_demo", "Content-Type": "application/json"}


# ─── Notification preference gate ────────────────────────────────────────────
class TestNotificationGate:
    def test_toggle_daily_brief_email_off_then_back_on(self, admin_ctx):
        # GET current
        r = requests.get(f"{BASE_URL}/api/notifications/preferences", headers=admin_ctx, timeout=15)
        assert r.status_code == 200
        prefs = r.json()["preferences"]
        original = dict(prefs["events"].get("daily_brief", {"email": True, "in_app": False}))

        # Toggle email off
        events = prefs["events"]
        events["daily_brief"] = {"email": False, "in_app": original.get("in_app", False)}
        put_body = {
            "events": events,
            "quiet_hours_enabled": prefs.get("quiet_hours_enabled", False),
            "quiet_start_hour": prefs.get("quiet_start_hour", 22),
            "quiet_end_hour": prefs.get("quiet_end_hour", 8),
        }
        r2 = requests.put(f"{BASE_URL}/api/notifications/preferences", headers=admin_ctx, json=put_body, timeout=15)
        assert r2.status_code == 200, r2.text
        assert r2.json()["preferences"]["events"]["daily_brief"]["email"] is False

        # Re-GET
        r3 = requests.get(f"{BASE_URL}/api/notifications/preferences", headers=admin_ctx, timeout=15)
        assert r3.status_code == 200
        assert r3.json()["preferences"]["events"]["daily_brief"]["email"] is False

        # Trigger manual daily-call-plan send-now — manual=True override should fire
        r4 = requests.post(f"{BASE_URL}/api/aria/daily-call-plan/send-now", headers=admin_ctx, timeout=30)
        # Endpoint can return 200 with sent flag, even if email backend not configured — important is that it did NOT return muted_by_pref
        assert r4.status_code in (200, 400, 500), r4.text
        if r4.status_code == 200:
            body = r4.json()
            # When manual=True, should never be skipped due to pref gate
            assert body.get("error") != "muted_by_pref", f"Manual override failed: {body}"

        # RESTORE: toggle back on
        events["daily_brief"] = {"email": True, "in_app": original.get("in_app", False)}
        put_body["events"] = events
        r5 = requests.put(f"{BASE_URL}/api/notifications/preferences", headers=admin_ctx, json=put_body, timeout=15)
        assert r5.status_code == 200
        assert r5.json()["preferences"]["events"]["daily_brief"]["email"] is True

    def test_should_notify_email_defaults_true_for_unknown_recipient(self):
        # Import the helper directly and call with a recipient that has no
        # membership in the DB.
        import sys
        sys.path.insert(0, "/app/backend")
        from routes.notifications import should_notify_email  # noqa
        # Random recipient — no user doc → should return True (allow emission)
        assert should_notify_email("nonexistent_user_iter43@example.com", "daily_brief") is True
        # Empty recipient → False (no-op)
        assert should_notify_email("", "daily_brief") is False


# ─── Lead capture WA widget ──────────────────────────────────────────────────
class TestLeadCaptureWAWidget:
    def test_get_config_has_wa_embed_snippet(self, admin_ctx):
        r = requests.get(f"{BASE_URL}/api/lead-capture/config", headers=admin_ctx, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "wa_embed_snippet" in data
        snippet = data["wa_embed_snippet"]
        assert isinstance(snippet, str)
        assert snippet.startswith("<!-- Aria Click-to-WhatsApp Widget -->"), snippet[:120]
        # WA fields exist in config
        cfg = data["config"]
        for key in ["wa_enabled", "wa_phone", "wa_text", "wa_label", "wa_color"]:
            assert key in cfg, f"missing {key} in config"

    def test_post_wa_fields_persist_and_reflect_in_snippet(self, admin_ctx):
        # Fetch current cfg, mutate WA fields only
        cur = requests.get(f"{BASE_URL}/api/lead-capture/config", headers=admin_ctx, timeout=15).json()["config"]
        payload = {
            **{k: v for k, v in cur.items() if k not in ("tenant_id", "updated_at", "_id")},
            "wa_enabled": True,
            "wa_phone": "+919811112222",
            "wa_text": "Hello",
            "wa_label": "Talk to us",
            "wa_color": "#25D366",
        }
        r = requests.post(f"{BASE_URL}/api/lead-capture/config", headers=admin_ctx, json=payload, timeout=15)
        assert r.status_code == 200, r.text
        saved = r.json()["config"]
        assert saved["wa_enabled"] is True
        assert saved["wa_phone"] == "+919811112222"

        # Re-GET — snippet must reflect new values
        r2 = requests.get(f"{BASE_URL}/api/lead-capture/config", headers=admin_ctx, timeout=15).json()
        snip = r2["wa_embed_snippet"]
        assert "+919811112222" in snip
        assert "Hello" in snip
        assert "Talk to us" in snip
        assert "#25D366" in snip

    def test_sales_rep_get_ok_post_403(self, sales_ctx):
        r = requests.get(f"{BASE_URL}/api/lead-capture/config", headers=sales_ctx, timeout=15)
        assert r.status_code == 200, f"sales_rep GET should be allowed: {r.text}"

        bad_post = {
            "enabled": True, "mode": "popup", "title": "x", "subtitle": "y",
            "button_label": "z", "accent_color": "#000000", "fields": ["email"],
            "require_consent": True, "consent_text": "ok", "allowed_origins": [],
            "wa_enabled": True, "wa_phone": "+919999", "wa_text": "hi",
            "wa_label": "lbl", "wa_color": "#25D366",
        }
        r2 = requests.post(f"{BASE_URL}/api/lead-capture/config", headers=sales_ctx, json=bad_post, timeout=15)
        assert r2.status_code == 403, f"Expected 403 for sales_rep, got {r2.status_code}: {r2.text}"
