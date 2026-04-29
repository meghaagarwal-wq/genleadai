"""Iter 19 — ARIA AI Sales Agent (additive) backend tests + regressions."""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@demo.com", "password": "Demo1234!"
    }, timeout=20)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    j = r.json()
    return j.get("access_token") or j.get("token")


@pytest.fixture(scope="module")
def H(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# ━━━━━━━━━━━━━ ARIA Agent endpoints ━━━━━━━━━━━━━

class TestTraining:
    def test_get_training_defaults(self, H):
        r = requests.get(f"{BASE_URL}/api/aria-agent/training", headers=H, timeout=15)
        assert r.status_code == 200
        d = r.json()
        # Required keys from default form payload
        for k in ["what_you_sell", "who_you_sell_to", "tone", "reminder_timing",
                  "target_industries", "qualifying_questions", "pricing_objections",
                  "calendar_link"]:
            assert k in d, f"missing default key {k}"
        assert d["tone"] == "founder_like"

    def test_put_then_get_persists(self, H):
        payload = {"what_you_sell": "TEST_ARIA training",
                   "tone": "professional",
                   "calendar_link": "https://cal.example.com/test"}
        r = requests.put(f"{BASE_URL}/api/aria-agent/training", headers=H, json=payload, timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body.get("saved") is True
        assert "trained_at" in body and len(body["trained_at"]) > 0

        g = requests.get(f"{BASE_URL}/api/aria-agent/training", headers=H, timeout=15)
        assert g.status_code == 200
        gd = g.json()
        assert gd["what_you_sell"] == "TEST_ARIA training"
        assert gd["tone"] == "professional"
        assert gd["calendar_link"] == "https://cal.example.com/test"


class TestPlaybooks:
    def test_list_playbooks(self, H):
        r = requests.get(f"{BASE_URL}/api/aria-agent/playbooks", headers=H, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "playbooks" in d and len(d["playbooks"]) == 10
        for p in d["playbooks"]:
            assert "id" in p and "name" in p and "active" in p
            assert isinstance(p["active"], bool)

    def test_activate_deactivate_roundtrip(self, H):
        pid = "inbound_qualification"
        r = requests.post(f"{BASE_URL}/api/aria-agent/playbooks/{pid}/activate", headers=H, timeout=15)
        assert r.status_code == 200
        assert r.json()["playbook_id"] == pid

        # verify active=true in list
        lst = requests.get(f"{BASE_URL}/api/aria-agent/playbooks", headers=H, timeout=15).json()
        match = [p for p in lst["playbooks"] if p["id"] == pid][0]
        assert match["active"] is True

        # deactivate
        r2 = requests.post(f"{BASE_URL}/api/aria-agent/playbooks/{pid}/deactivate", headers=H, timeout=15)
        assert r2.status_code == 200
        assert r2.json()["active"] is False

        lst2 = requests.get(f"{BASE_URL}/api/aria-agent/playbooks", headers=H, timeout=15).json()
        match2 = [p for p in lst2["playbooks"] if p["id"] == pid][0]
        assert match2["active"] is False


class TestJourneys:
    def test_default_journey(self, H):
        r = requests.get(f"{BASE_URL}/api/aria-agent/journeys/default", headers=H, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert len(d["journey"]) == 17
        assert d["max_touchpoints"] == 26
        assert len(d["templates"]) == 5
        # validate step shape
        s = d["journey"][0]
        for k in ["step", "name", "channel", "timing", "trigger", "goal", "personalisation", "handoff_rule"]:
            assert k in s


class TestFounderBrief:
    def test_brief_for_real_lead(self, H):
        leads = requests.get(f"{BASE_URL}/api/leads?limit=1", headers=H, timeout=15).json()
        # leads response could be list or {leads:[]}
        if isinstance(leads, dict):
            arr = leads.get("leads") or leads.get("data") or []
        else:
            arr = leads
        assert len(arr) > 0, "need at least 1 lead"
        lead_id = arr[0].get("id") or arr[0].get("_id")
        r = requests.post(f"{BASE_URL}/api/aria-agent/founder-brief/{lead_id}", headers=H, timeout=20)
        assert r.status_code == 200, r.text
        b = r.json()
        for k in ["lead_name", "company", "role", "source", "what_they_need",
                  "main_pain_point", "urgency", "budget_signal", "lead_temperature",
                  "recommended_pitch", "suggested_opening", "questions_to_ask",
                  "aria_recommendation", "generated_at"]:
            assert k in b, f"missing {k}"
        assert isinstance(b["questions_to_ask"], list) and len(b["questions_to_ask"]) >= 3


class TestHandoff:
    def test_rules(self, H):
        r = requests.get(f"{BASE_URL}/api/aria-agent/handoff/rules", headers=H, timeout=15)
        assert r.status_code == 200
        assert len(r.json()["rules"]) == 9

    def test_alerts(self, H):
        r = requests.get(f"{BASE_URL}/api/aria-agent/handoff/alerts", headers=H, timeout=15)
        assert r.status_code == 200
        alerts = r.json()["alerts"]
        assert len(alerts) >= 1
        a = alerts[0]
        for k in ["trigger", "trigger_label", "why", "recommended_action", "suggested_message"]:
            assert k in a


class TestRevival:
    def test_segments(self, H):
        r = requests.get(f"{BASE_URL}/api/aria-agent/revival/segments", headers=H, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert len(d["segments"]) == 7
        assert len(d["default_journey"]) == 5
        days = [s["day"] for s in d["default_journey"]]
        assert days == [1, 4, 9, 15, 30]


class TestAgentActivity:
    def test_activity(self, H):
        r = requests.get(f"{BASE_URL}/api/aria-agent/agent-activity", headers=H, timeout=15)
        assert r.status_code == 200
        d = r.json()
        for k in ["responded_today", "qualified_today", "followups_sent", "calls_booked",
                  "hot_escalated", "silent_revived", "headline"]:
            assert k in d
        assert isinstance(d["responded_today"], int)
        assert isinstance(d["headline"], str) and len(d["headline"]) > 0


class TestInsights:
    def test_insights(self, H):
        r = requests.get(f"{BASE_URL}/api/aria-agent/insights", headers=H, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert len(d["headline_insights"]) == 8
        for h in d["headline_insights"]:
            assert "title" in h and "items" in h and len(h["items"]) == 3
        assert len(d["recommendations"]) == 4
        assert isinstance(d["live_observation"], str) and len(d["live_observation"]) > 0


# ━━━━━━━━━━━━━ Regressions ━━━━━━━━━━━━━

@pytest.mark.parametrize("path", [
    "/api/aria/today",
    "/api/aria/eod-wrap/config",
    "/api/insights/founder-command-center",
    "/api/leads",
    "/api/dashboard",
    "/api/aria/best-time-to-call-priority",
    "/api/aria/daily-call-plan/config",
    "/api/analytics/dashboard",
])
def test_existing_endpoints_still_work(H, path):
    r = requests.get(f"{BASE_URL}{path}", headers=H, timeout=20)
    assert r.status_code == 200, f"{path} returned {r.status_code} {r.text[:200]}"
