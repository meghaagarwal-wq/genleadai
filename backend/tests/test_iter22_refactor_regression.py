"""Iteration 22: Backend refactor regression + new automation-rule test endpoint.

Covers:
- routes/auth.py        -> /api/auth/register, /login, /me
- routes/meta.py        -> /api/health, /api/users, /api/calendly/*
- routes/campaigns.py   -> /api/campaigns POST/GET/{id}
- routes/ai.py          -> /api/ai/score, /email-generate, /chat, /summarize
- routes/analytics.py   -> /api/analytics/dashboard, /api/email/send
- integrations_routes   -> POST /api/integrations/automation/rules/{rule_id}/test
- regression            -> /api/leads, activities, aria-agent, integrations list
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or \
           "https://pipeline-pro-96.preview.emergentagent.com"

ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD", "Demo1234!")
@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def token(api):
    r = api.post(f"{BASE_URL}/api/auth/login",
                 json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    assert "token" in data and data["token"]
    assert data["user"]["email"] == ADMIN_EMAIL
    return data["token"]


@pytest.fixture(scope="session")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ─── auth router ─────────────────────────────────────────────────────────────
class TestAuth:
    def test_health(self, api):
        r = api.get(f"{BASE_URL}/api/health")
        assert r.status_code == 200
        assert r.json().get("status") == "healthy"

    def test_login_success(self, api):
        r = api.post(f"{BASE_URL}/api/auth/login",
                     json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200
        body = r.json()
        assert body["user"]["email"] == ADMIN_EMAIL
        assert isinstance(body["token"], str)

    def test_login_invalid(self, api):
        r = api.post(f"{BASE_URL}/api/auth/login",
                     json={"email": ADMIN_EMAIL, "password": "wrong!!"})
        assert r.status_code == 401

    def test_me(self, api, auth):
        r = api.get(f"{BASE_URL}/api/auth/me", headers=auth)
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL

    def test_register_duplicate_rejected(self, api):
        r = api.post(f"{BASE_URL}/api/auth/register", json={
            "email": ADMIN_EMAIL, "password": "xxx", "full_name": "dup"
        })
        assert r.status_code == 400

    def test_register_new_then_login(self, api):
        email = f"TEST_iter22_{uuid.uuid4().hex[:8]}@example.com"
        r = api.post(f"{BASE_URL}/api/auth/register", json={
            "email": email, "password": "Passw0rd!", "full_name": "Iter22 Tester"
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["user"]["email"] == email
        assert body["token"]
        # verify can login
        r2 = api.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": "Passw0rd!"})
        assert r2.status_code == 200


# ─── meta router (users + calendly) ──────────────────────────────────────────
class TestMeta:
    def test_users_list(self, api, auth):
        r = api.get(f"{BASE_URL}/api/users", headers=auth)
        assert r.status_code == 200
        body = r.json()
        assert "users" in body and isinstance(body["users"], list)
        for u in body["users"]:
            assert "password_hash" not in u
            assert "_id" not in u

    def test_users_unauth(self, api):
        r = api.get(f"{BASE_URL}/api/users")
        assert r.status_code in (401, 403)

    def test_calendly_event_types(self, api, auth):
        r = api.get(f"{BASE_URL}/api/calendly/event-types", headers=auth)
        # allow 200 or 500 (external API key env), but endpoint must exist
        assert r.status_code in (200, 500), r.text
        if r.status_code == 200:
            assert "event_types" in r.json()

    def test_calendly_user(self, api, auth):
        r = api.get(f"{BASE_URL}/api/calendly/user", headers=auth)
        assert r.status_code in (200, 500)


# ─── campaigns router ────────────────────────────────────────────────────────
class TestCampaigns:
    def test_create_and_get(self, api, auth):
        payload = {
            "name": f"TEST_iter22_{uuid.uuid4().hex[:6]}",
            "description": "regression",
            "channel": "email",
            "lead_type": "B2B",
            "target_audience": "B2B",
        }
        r = api.post(f"{BASE_URL}/api/campaigns", json=payload, headers=auth)
        assert r.status_code in (200, 201), r.text
        created = r.json()
        cid = created.get("id") or created.get("campaign_id")
        assert cid, created

        # list
        r2 = api.get(f"{BASE_URL}/api/campaigns", headers=auth)
        assert r2.status_code == 200
        body = r2.json()
        items = body.get("campaigns", body) if isinstance(body, dict) else body
        assert isinstance(items, list)

        # get by id
        r3 = api.get(f"{BASE_URL}/api/campaigns/{cid}", headers=auth)
        assert r3.status_code in (200, 404)


# ─── AI router ───────────────────────────────────────────────────────────────
class TestAI:
    def _first_lead_id(self, api, auth):
        r = api.get(f"{BASE_URL}/api/leads?limit=1", headers=auth)
        if r.status_code != 200:
            return None
        body = r.json()
        items = body.get("leads", body) if isinstance(body, dict) else body
        if items and len(items):
            return items[0].get("id")
        return None

    def test_ai_score(self, api, auth):
        lead_id = self._first_lead_id(api, auth)
        if not lead_id:
            pytest.skip("no leads in DB")
        r = api.post(f"{BASE_URL}/api/ai/score",
                     json={"lead_id": lead_id}, headers=auth)
        # AI may return 200 or 500 (LLM dependency). Must NOT be 404.
        assert r.status_code != 404, r.text

    def test_ai_email_generate(self, api, auth):
        lead_id = self._first_lead_id(api, auth)
        if not lead_id:
            pytest.skip("no leads")
        r = api.post(f"{BASE_URL}/api/ai/email-generate",
                     json={"lead_id": lead_id, "tone": "professional", "purpose": "intro"},
                     headers=auth)
        assert r.status_code != 404

    def test_ai_chat(self, api, auth):
        r = api.post(f"{BASE_URL}/api/ai/chat",
                     json={"message": "hello", "session_id": f"TEST_{uuid.uuid4().hex[:6]}"},
                     headers=auth)
        assert r.status_code != 404

    def test_ai_summarize(self, api, auth):
        lead_id = self._first_lead_id(api, auth)
        if not lead_id:
            pytest.skip("no leads")
        r = api.post(f"{BASE_URL}/api/ai/summarize",
                     json={"lead_id": lead_id}, headers=auth)
        assert r.status_code != 404


# ─── analytics + email ───────────────────────────────────────────────────────
class TestAnalytics:
    def test_dashboard(self, api, auth):
        r = api.get(f"{BASE_URL}/api/analytics/dashboard", headers=auth)
        assert r.status_code == 200
        body = r.json()
        for k in ("total_leads", "status_distribution", "channel_distribution",
                  "lead_type_distribution", "icp_distribution"):
            assert k in body, f"missing {k}"
        assert isinstance(body["total_leads"], int)

    def test_email_send_exists(self, api, auth):
        # must NOT 404 (i.e. endpoint must be mounted). 200 or 500 both ok.
        r = api.post(f"{BASE_URL}/api/email/send", headers=auth, json={
            "recipient_email": "TEST_iter22@example.com",
            "subject": "TEST iter22",
            "html_content": "<p>hi</p>",
        })
        assert r.status_code in (200, 500), f"expected 200/500 got {r.status_code} {r.text}"


# ─── Automation rule test endpoint ───────────────────────────────────────────
class TestAutomationRuleTest:
    def test_rule_not_found_returns_404(self, api, auth):
        r = api.post(
            f"{BASE_URL}/api/integrations/automation/rules/does-not-exist-xyz/test",
            headers=auth,
        )
        assert r.status_code == 404, r.text

    def test_rule_endpoint_contract_when_rule_exists(self, api, auth):
        # List rules; if any exist, hit the test endpoint and validate shape.
        r = api.get(f"{BASE_URL}/api/integrations/automation/rules", headers=auth)
        assert r.status_code == 200, r.text
        body = r.json()
        rules = body.get("rules", body) if isinstance(body, dict) else body
        if not rules:
            pytest.skip("no automation rules configured in this workspace")
        rid = rules[0].get("id") or rules[0].get("rule_id")
        r2 = api.post(
            f"{BASE_URL}/api/integrations/automation/rules/{rid}/test",
            headers=auth,
        )
        assert r2.status_code == 200, r2.text
        data = r2.json()
        assert "would_run" in data
        assert "reason" in data
        assert "sample" in data
        assert "rule" in data


# ─── regression on untouched routers ────────────────────────────────────────
class TestRegression:
    def test_leads_list(self, api, auth):
        r = api.get(f"{BASE_URL}/api/leads?limit=5", headers=auth)
        assert r.status_code == 200

    def test_lead_activities(self, api, auth):
        r = api.get(f"{BASE_URL}/api/leads?limit=1", headers=auth)
        assert r.status_code == 200
        body = r.json()
        items = body.get("leads", body) if isinstance(body, dict) else body
        if not items:
            pytest.skip("no leads")
        lid = items[0]["id"]
        r2 = api.get(f"{BASE_URL}/api/leads/{lid}/activities", headers=auth)
        assert r2.status_code == 200

    def test_aria_agent_activity(self, api, auth):
        r = api.get(f"{BASE_URL}/api/aria-agent/agent-activity", headers=auth)
        assert r.status_code == 200

    def test_aria_agent_insights(self, api, auth):
        r = api.get(f"{BASE_URL}/api/aria-agent/insights", headers=auth)
        assert r.status_code == 200

    def test_integrations_automation_rules_list(self, api, auth):
        r = api.get(f"{BASE_URL}/api/integrations/automation/rules", headers=auth)
        assert r.status_code == 200
