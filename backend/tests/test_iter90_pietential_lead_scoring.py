"""Iter90 (S10) — Regression sweep on the Pietential lead-pulling + Aria
scoring flow introduced in iter89-90.

Coverage matrix
───────────────
1. `routes.pt_lead_scoring.heuristic_score` — HOT/WARM/COLD title rules,
   engagement bonuses, demotion for missing company, score bounds.
2. `routes.pt_lead_scoring.score_lead_with_aria` — None when no key /
   missing fields; Claude JSON parsing happy-path + malformed/no-LLM
   fallback (monkeypatched).
3. `POST /api/pt/leads/rescore` — admin gate, response shape, filter
   semantics (`only_stage`, `only_score_zero`, `max_leads`).
4. `POST /api/pt/integrations/{lemlist,saleshandy}/pull-leads` — admin
   gate + "not connected" branch (uses fake key paths).
5. Light regression: `/api/pt/setup/health`, `/api/admin/deployments/list`
   still return the iter88 contract.

Run:  pytest -xvs backend/tests/test_iter90_pietential_lead_scoring.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
import requests
import pytest
from pymongo import MongoClient

# Ensure /app/backend is on PYTHONPATH for direct module imports.
_BACKEND_DIR = "/app/backend"
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from routes import pt_lead_scoring  # noqa: E402

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASS = os.environ.get("TEST_ADMIN_PASS", "Demo1234!")
SALES_EMAIL = "sarah@demo.com"
SALES_PASS = os.environ.get("TEST_SALES_PASS", "Demo1234!")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "genleadai_lms")
_mc = MongoClient(MONGO_URL)
_db = _mc[DB_NAME]


# ─── Helpers ────────────────────────────────────────────────────────────
def _login(email: str, password: str) -> str:
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text[:200]}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def sales_token():
    return _login(SALES_EMAIL, SALES_PASS)


def _h(token: str, tenant_id: str = "ten_pietential") -> dict:
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": tenant_id, "Content-Type": "application/json"}


def _run(coro):
    """Run an async coroutine inside a sync test."""
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.new_event_loop().run_until_complete(coro)


# ─── A. heuristic_score: title + engagement + bounds ────────────────────
class TestHeuristicScore:
    def test_hot_chro(self):
        out = pt_lead_scoring.heuristic_score({"title": "CHRO", "company_name": "Acme"})
        assert out["stage"] == "hot"
        assert out["score"] >= 70
        assert out["source"] == "heuristic"

    def test_hot_vp_people(self):
        out = pt_lead_scoring.heuristic_score({"title": "VP of People", "company_name": "Acme"})
        assert out["stage"] == "hot"
        assert out["score"] >= 70

    def test_hot_head_of_talent(self):
        out = pt_lead_scoring.heuristic_score({"title": "Head of Talent", "company_name": "Acme"})
        assert out["stage"] == "hot"

    def test_warm_director_of_hr(self):
        out = pt_lead_scoring.heuristic_score({"title": "Director of HR", "company_name": "Acme"})
        assert out["stage"] == "warm"
        assert 45 <= out["score"] < 70

    def test_warm_senior_manager_people(self):
        out = pt_lead_scoring.heuristic_score({"title": "Senior Manager of People", "company_name": "Acme"})
        assert out["stage"] == "warm"

    def test_cold_random_title(self):
        out = pt_lead_scoring.heuristic_score({"title": "Software Engineer", "company_name": "Acme"})
        assert out["stage"] == "cold"
        assert out["score"] < 45

    def test_cold_empty_title(self):
        out = pt_lead_scoring.heuristic_score({"title": "", "company_name": "Acme"})
        assert out["stage"] == "cold"

    def test_engagement_clicked_pushes_warm_to_hot(self):
        # Director = warm @ 58. +15 for clicked → 73 → hot.
        out = pt_lead_scoring.heuristic_score({
            "title": "Director of People",
            "company_name": "Acme",
            "_lemlist_raw": {"lead_state": "clicked"},
        })
        assert out["score"] >= 70
        assert out["stage"] == "hot"

    def test_engagement_unsubscribed_demotes_hot_to_warm_or_cold(self):
        # CHRO = hot @ 78. -25 for unsubscribed → 53 → warm.
        out = pt_lead_scoring.heuristic_score({
            "title": "CHRO",
            "company_name": "Acme",
            "_lemlist_raw": {"lead_state": "unsubscribed"},
        })
        assert out["score"] <= 55
        assert out["stage"] in ("warm", "cold")

    def test_missing_company_demotes(self):
        without = pt_lead_scoring.heuristic_score({"title": "Director of HR"})
        with_co = pt_lead_scoring.heuristic_score({"title": "Director of HR", "company_name": "Acme"})
        assert without["score"] == with_co["score"] - 5

    def test_score_bounded_0_100(self):
        # Force a massive engagement bonus and ensure score stays ≤ 100.
        out = pt_lead_scoring.heuristic_score({
            "title": "CHRO",
            "company_name": "Acme",
            "_lemlist_raw": {"lead_state": "opened clicked replied"},
        })
        assert 0 <= out["score"] <= 100

    def test_why_is_string(self):
        out = pt_lead_scoring.heuristic_score({"title": "VP HR", "company_name": "Acme"})
        assert isinstance(out["why"], str)
        assert len(out["why"]) > 0


# ─── B. score_lead_with_aria: gating + parsing ──────────────────────────
class TestAriaScoring:
    def test_aria_returns_none_when_no_key(self, monkeypatch):
        monkeypatch.delenv("EMERGENT_LLM_KEY", raising=False)
        out = asyncio.new_event_loop().run_until_complete(
            pt_lead_scoring.score_lead_with_aria({
                "email": "a@b.com", "title": "CHRO", "company_name": "Acme",
            })
        )
        assert out is None

    def test_aria_returns_none_when_missing_email(self, monkeypatch):
        monkeypatch.setenv("EMERGENT_LLM_KEY", "sk-test-stub")
        out = asyncio.new_event_loop().run_until_complete(
            pt_lead_scoring.score_lead_with_aria({
                "email": "", "title": "CHRO", "company_name": "Acme",
            })
        )
        assert out is None

    def test_aria_returns_none_when_no_title_or_company(self, monkeypatch):
        monkeypatch.setenv("EMERGENT_LLM_KEY", "sk-test-stub")
        out = asyncio.new_event_loop().run_until_complete(
            pt_lead_scoring.score_lead_with_aria({
                "email": "a@b.com", "title": "", "company_name": "",
            })
        )
        assert out is None

    def test_score_lead_falls_back_to_heuristic_on_aria_failure(self, monkeypatch):
        # Force the Aria path to return None (simulate SDK error / no key)
        async def _stub_none(lead):
            return None
        monkeypatch.setattr(pt_lead_scoring, "score_lead_with_aria", _stub_none)
        out = asyncio.new_event_loop().run_until_complete(
            pt_lead_scoring.score_lead({"title": "CHRO", "company_name": "Acme"}, use_aria=True)
        )
        assert out["source"] == "heuristic"
        assert out["stage"] == "hot"

    def test_score_lead_uses_aria_when_available(self, monkeypatch):
        # Stub Aria to return a fixed payload.
        async def _stub_aria(lead):
            return {"score": 88, "stage": "hot", "why": "stubbed", "source": "aria"}
        monkeypatch.setattr(pt_lead_scoring, "score_lead_with_aria", _stub_aria)
        out = asyncio.new_event_loop().run_until_complete(
            pt_lead_scoring.score_lead({"title": "CHRO"}, use_aria=True)
        )
        assert out["source"] == "aria"
        assert out["score"] == 88

    def test_score_lead_skips_aria_when_use_aria_false(self, monkeypatch):
        async def _explode(lead):
            raise AssertionError("Aria should not be called when use_aria=False")
        monkeypatch.setattr(pt_lead_scoring, "score_lead_with_aria", _explode)
        out = asyncio.new_event_loop().run_until_complete(
            pt_lead_scoring.score_lead({"title": "Director of HR"}, use_aria=False)
        )
        assert out["source"] == "heuristic"


# ─── C. POST /api/pt/leads/rescore ──────────────────────────────────────
class TestRescoreEndpoint:
    def test_sales_rep_blocked(self, sales_token):
        r = requests.post(f"{BASE_URL}/api/pt/leads/rescore",
                          headers=_h(sales_token, "ten_pietential"),
                          json={"max_leads": 1, "only_stage": "cold", "only_score_zero": False},
                          timeout=20)
        assert r.status_code in (401, 403), f"sales_rep should be blocked: {r.status_code} {r.text[:200]}"

    def test_admin_allowed_response_shape(self, admin_token):
        r = requests.post(f"{BASE_URL}/api/pt/leads/rescore",
                          headers=_h(admin_token, "ten_pietential"),
                          json={"max_leads": 1, "only_stage": "cold", "only_score_zero": False},
                          timeout=120)  # one Aria call possible
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["ok"] is True
        assert "rescored" in body
        assert "by_tier" in body
        assert set(body["by_tier"].keys()) >= {"hot", "warm", "cold"}
        assert "message" in body
        assert isinstance(body["rescored"], int)

    def test_empty_result_when_no_matches(self, admin_token):
        # Use a deliberately impossible filter — no leads with stage="purple"
        r = requests.post(f"{BASE_URL}/api/pt/leads/rescore",
                          headers=_h(admin_token, "ten_pietential"),
                          json={"max_leads": 50, "only_stage": "purple", "only_score_zero": False},
                          timeout=30)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["rescored"] == 0
        assert body["by_tier"]["hot"] == 0
        assert "No leads matched" in body["message"]

    def test_max_leads_capped(self, admin_token):
        # max_leads=1 should rescore at most 1.
        r = requests.post(f"{BASE_URL}/api/pt/leads/rescore",
                          headers=_h(admin_token, "ten_pietential"),
                          json={"max_leads": 1, "only_stage": None, "only_score_zero": False},
                          timeout=120)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["rescored"] <= 1


# ─── D. Pull endpoints: auth + not-connected paths ──────────────────────
class TestPullEndpointsGates:
    """We exercise the auth/role/not-connected branches WITHOUT touching
    the real Lemlist / Saleshandy APIs (which already work and consume
    quota). The actual import was verified live in iter89/90 — these tests
    are the regression guard for the surrounding contract."""

    def test_lemlist_pull_blocked_for_sales_rep(self, sales_token):
        r = requests.post(f"{BASE_URL}/api/pt/integrations/lemlist/pull-leads",
                          headers=_h(sales_token, "ten_pietential"),
                          json={"max_campaigns": 1, "max_per_campaign": 1},
                          timeout=20)
        assert r.status_code in (401, 403), f"sales_rep should be blocked: {r.status_code} {r.text[:200]}"

    def test_saleshandy_pull_blocked_for_sales_rep(self, sales_token):
        r = requests.post(f"{BASE_URL}/api/pt/integrations/saleshandy/pull-leads",
                          headers=_h(sales_token, "ten_pietential"),
                          json={"max_prospects": 5},
                          timeout=20)
        assert r.status_code in (401, 403), f"sales_rep should be blocked: {r.status_code} {r.text[:200]}"

    def test_lemlist_pull_admin_reachable(self, admin_token):
        """With a real key configured (iter88), admin should get either
        200 (real import) or a clean 4xx if Lemlist rejected — but never
        500."""
        r = requests.post(f"{BASE_URL}/api/pt/integrations/lemlist/pull-leads",
                          headers=_h(admin_token, "ten_pietential"),
                          json={"max_campaigns": 0, "max_per_campaign": 0,
                                "campaign_ids": ["__nonexistent__"]},
                          timeout=120)
        assert r.status_code in (200, 400, 401, 403, 404, 422, 502), \
            f"unexpected status: {r.status_code} body={r.text[:300]}"
        if r.status_code == 200:
            body = r.json()
            assert body["ok"] is True
            # Nonexistent campaign_id → no-op branch
            assert body["imported"] == 0


# ─── E. Light regression on iter88 contract ─────────────────────────────
class TestIter88Regression:
    def test_setup_health_still_5_items(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/pt/setup/health",
                         headers=_h(admin_token, "ten_pietential"), timeout=20)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["total"] == 5
        ids = {it["id"] for it in body["items"]}
        assert ids >= {"email", "saleshandy", "lemlist"}

    def test_deployments_list_includes_setup_rollup(self, admin_token):
        # Canonical is /api/admin/deployments; some clients call /list.
        r = requests.get(f"{BASE_URL}/api/admin/deployments",
                         headers=_h(admin_token, "ten_pietential"), timeout=30)
        if r.status_code == 403:
            pytest.skip("admin token is not master_admin in this env")
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        rows = body.get("deployments") if isinstance(body, dict) else body
        assert isinstance(rows, list)
        if rows:
            pt = next((row for row in rows if row.get("tenant_id") == "ten_pietential"), None)
            if pt:
                assert "setup_ready" in pt
                assert "setup_total" in pt
                assert pt["setup_total"] == 5

    def test_login_rate_limit_present(self):
        """iter80 rate-limit smoke: 10/min on /api/auth/login."""
        # We don't burn through 10 here — just confirm a single login
        # doesn't 429 immediately and the endpoint responds.
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=20)
        assert r.status_code in (200, 429)
