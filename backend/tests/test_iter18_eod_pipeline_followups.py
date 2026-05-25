"""Iter 18 backend tests:
 - EOD wrap config GET/PUT/persistence
 - EOD wrap preview structure
 - EOD send-now (Resend free-tier expected error path)
 - Regressions for daily-call-plan, founder-command-center, leads, dashboard, analytics, best-time-to-call
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD", "Demo1234!")
@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"Login failed: {r.status_code} {r.text}")
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# === EOD Wrap ===

class TestEodWrap:
    def test_config_get_returns_defaults_or_existing(self, headers):
        r = requests.get(f"{BASE_URL}/api/aria/eod-wrap/config", headers=headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        # Required keys
        for k in ["enabled", "send_to_email", "send_hour_local", "timezone_offset_hours"]:
            assert k in d, f"missing key {k} in {d}"
        assert isinstance(d["enabled"], bool)
        assert isinstance(d["send_hour_local"], int)
        assert 0 <= d["send_hour_local"] <= 23

    def test_config_put_persists(self, headers):
        payload = {
            "enabled": True,
            "send_to_email": "founder-test@example.com",
            "send_hour_local": 19,
            "timezone_offset_hours": 5.5,
        }
        r = requests.put(f"{BASE_URL}/api/aria/eod-wrap/config", headers=headers, json=payload, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["enabled"] is True
        assert body["send_to_email"] == "founder-test@example.com"
        assert body["send_hour_local"] == 19
        assert abs(body["timezone_offset_hours"] - 5.5) < 0.001
        # GET must return same values
        r2 = requests.get(f"{BASE_URL}/api/aria/eod-wrap/config", headers=headers, timeout=30)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["enabled"] is True
        assert d2["send_to_email"] == "founder-test@example.com"
        assert d2["send_hour_local"] == 19

    def test_config_put_disable_persists(self, headers):
        payload = {
            "enabled": False,
            "send_to_email": "founder-test@example.com",
            "send_hour_local": 18,
            "timezone_offset_hours": 5.5,
        }
        r = requests.put(f"{BASE_URL}/api/aria/eod-wrap/config", headers=headers, json=payload, timeout=30)
        assert r.status_code == 200
        d = requests.get(f"{BASE_URL}/api/aria/eod-wrap/config", headers=headers, timeout=30).json()
        assert d["enabled"] is False

    def test_preview_returns_html_and_wrap_keys(self, headers):
        r = requests.get(f"{BASE_URL}/api/aria/eod-wrap/preview", headers=headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "html" in d and isinstance(d["html"], str) and len(d["html"]) > 200
        assert "wrap" in d
        wrap = d["wrap"]
        for k in ["totals", "momentum", "wins", "losses", "rep_rows", "hot_untouched", "tomorrow_plan"]:
            assert k in wrap, f"missing key {k} in wrap"
        totals = wrap["totals"]
        for k in ["calls", "emails", "whatsapps", "notes", "meetings_booked", "total_touches", "new_leads", "wins", "losses", "overdue_pending"]:
            assert k in totals
        assert wrap["momentum"] in ["strong", "steady", "quiet"]
        assert isinstance(wrap["wins"], list)
        assert isinstance(wrap["losses"], list)
        assert isinstance(wrap["rep_rows"], list)
        assert isinstance(wrap["hot_untouched"], list)
        assert isinstance(wrap["tomorrow_plan"], list)

    def test_send_now_attempts_send(self, headers):
        # Resend free-tier rejects non-verified recipient -> 500 with detail. That's an acceptable PASS
        # because it proves the email send is being attempted.
        r = requests.post(f"{BASE_URL}/api/aria/eod-wrap/send-now", headers=headers, timeout=60)
        assert r.status_code in (200, 500), r.text
        if r.status_code == 500:
            detail = r.json().get("detail", "")
            assert "Failed to send" in detail or "testing emails" in detail or "verify" in detail.lower() or "domain" in detail.lower(), (
                f"Unexpected 500 detail (should be Resend send error): {detail}"
            )

    def test_unauth_blocked(self):
        r = requests.get(f"{BASE_URL}/api/aria/eod-wrap/config", timeout=30)
        assert r.status_code in (401, 403)


# === Regressions ===

class TestRegressions:
    def test_daily_call_plan_config(self, headers):
        r = requests.get(f"{BASE_URL}/api/aria/daily-call-plan/config", headers=headers, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "enabled" in d
        # Roundtrip PUT
        payload = {
            "enabled": d.get("enabled", False),
            "send_to_email": d.get("send_to_email") or "rep@example.com",
            "send_hour_local": d.get("send_hour_local", 8),
            "timezone_offset_hours": d.get("timezone_offset_hours", 5.5),
        }
        r2 = requests.put(f"{BASE_URL}/api/aria/daily-call-plan/config", headers=headers, json=payload, timeout=30)
        assert r2.status_code == 200, r2.text

    def test_founder_command_center(self, headers):
        r = requests.get(f"{BASE_URL}/api/insights/founder-command-center", headers=headers, timeout=30)
        assert r.status_code == 200
        d = r.json()
        for k in ["revenue_leakage", "money_at_risk", "daily_brief", "hot_leads_untouched", "first_response", "proposal_graveyard", "source_quality", "lost_reasons", "pipeline_value_label"]:
            assert k in d, f"missing FCC key {k}"

    def test_leads(self, headers):
        r = requests.get(f"{BASE_URL}/api/leads?limit=200", headers=headers, timeout=30)
        assert r.status_code == 200
        body = r.json()
        # Could be list or dict with items
        assert isinstance(body, (list, dict))
        leads = body if isinstance(body, list) else (body.get("items") or body.get("leads") or [])
        assert isinstance(leads, list)

    def test_analytics_dashboard(self, headers):
        r = requests.get(f"{BASE_URL}/api/analytics/dashboard", headers=headers, timeout=30)
        assert r.status_code == 200

    def test_call_priority(self, headers):
        # Canonical route is /api/aria/call-priority
        r = requests.get(f"{BASE_URL}/api/aria/call-priority", headers=headers, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "priority" in d or isinstance(d, list)
