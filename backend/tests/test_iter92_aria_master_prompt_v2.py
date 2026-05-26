"""Iter92 — Aria v2 Master Prompt Assembly (Phase 1).

Covers the new /api/aria/training-profile, /api/aria/workspace-type,
/api/aria/system-prompt-preview endpoints, the assembler itself, and the
integration with aria_agent.get_aria_system_prompt().
"""
from __future__ import annotations

import os
import sys
import requests
import pytest
from pymongo import MongoClient

_BACKEND_DIR = "/app/backend"
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASS = os.environ.get("TEST_ADMIN_PASS", "Demo1234!")
SALES_EMAIL = "sarah@demo.com"
SALES_PASS = os.environ.get("TEST_SALES_PASS", "Demo1234!")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "genleadai_lms")
_mc = MongoClient(MONGO_URL)
_db = _mc[DB_NAME]


def _login(email: str, password: str) -> str:
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text[:200]}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def sales_token():
    return _login(SALES_EMAIL, SALES_PASS)


def _h(token: str, tenant_id: str = "ten_pietential") -> dict:
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": tenant_id, "Content-Type": "application/json"}


# ─── A. Unit tests on the assembler (no HTTP) ───────────────────────────
class TestAssembler:
    def test_empty_profile_renders_section_headers(self):
        from routes.aria_training import assemble_aria_prompt, _empty_profile
        out = assemble_aria_prompt("Acme", "Jane", "Aria", "hybrid", _empty_profile())
        # Every section header must be present
        for h in (
            "SECTION 1 — BUSINESS IDENTITY",
            "SECTION 2 — IDEAL CUSTOMER PROFILES",
            "SECTION 3 — QUALIFICATION LOGIC",
            "SECTION 4 — BRAND VOICE",
            "SECTION 5 — OBJECTION HANDLING",
            "SECTION 6 — BOOKING RULES",
            "SECTION 7 — B2B INSIGHTS ENGINE",
            "SECTION 8 — WHAT ARIA NEVER DOES",
            "SECTION 9 — KNOWLEDGE BASE",
            "OUTPUT CONTRACT",
        ):
            assert h in out, f"missing section: {h}"

    def test_b2c_excludes_insights_section(self):
        from routes.aria_training import assemble_aria_prompt, _empty_profile
        out = assemble_aria_prompt("Acme", "Jane", "Aria", "b2c", _empty_profile())
        assert "SECTION 7" not in out, "Section 7 (insights) must be hidden for b2c"

    def test_b2b_includes_insights_section(self):
        from routes.aria_training import assemble_aria_prompt, _empty_profile
        out = assemble_aria_prompt("Acme", "Jane", "Aria", "b2b", _empty_profile())
        assert "SECTION 7 — B2B INSIGHTS ENGINE" in out
        assert "B2B workspace" in out or "B2B workspace".lower() in out.lower()

    def test_brand_integrity_block_includes_workspace_name(self):
        from routes.aria_training import assemble_aria_prompt, _empty_profile
        out = assemble_aria_prompt("Pietential", "Megha", "Aria", "hybrid", _empty_profile())
        assert "represent Pietential" in out
        assert "Megha" in out

    def test_filled_icp_renders_correctly(self):
        from routes.aria_training import assemble_aria_prompt
        profile = {
            "what_you_sell": "Test product",
            "icp_profiles": [{
                "icp_name": "CHRO at SaaS",
                "target_industries": ["SaaS"],
                "target_titles_or_roles": ["CHRO", "VP HR"],
                "company_size": "100-1000",
                "geography": "USA",
                "budget_range": "$50k+",
                "high_intent_signals": ["recent funding"],
                "disqualification_signals": ["<50 employees"],
            }],
        }
        # Fill in remaining required fields with empty defaults
        from routes.aria_training import _empty_profile
        merged = {**_empty_profile(), **profile}
        out = assemble_aria_prompt("Acme", "Jane", "Aria", "b2b", merged)
        assert "CHRO at SaaS" in out
        assert "VP HR" in out
        assert "$50k+" in out

    def test_empty_lists_render_as_not_configured(self):
        from routes.aria_training import _bullet
        assert _bullet([]) == "NOT_CONFIGURED"
        assert _bullet(None) == "NOT_CONFIGURED"
        assert _bullet([""]) == "NOT_CONFIGURED"
        assert _bullet(["a", "b"]) == "  - a\n  - b"


# ─── B. HTTP endpoints ──────────────────────────────────────────────────
class TestEndpoints:
    def test_workspace_type_get(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/aria/workspace-type",
                         headers=_h(admin_token, "ten_pietential"), timeout=20)
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        assert body["workspace_type"] in ("b2b", "b2c", "hybrid")

    def test_workspace_type_set_rejects_invalid(self, admin_token):
        r = requests.put(f"{BASE_URL}/api/aria/workspace-type",
                         headers=_h(admin_token, "ten_pietential"),
                         json={"workspace_type": "saas"}, timeout=20)
        assert r.status_code == 422, r.text[:200]

    def test_workspace_type_set_accepts_valid(self, admin_token):
        for wt in ("b2b", "b2c", "hybrid"):
            r = requests.put(f"{BASE_URL}/api/aria/workspace-type",
                             headers=_h(admin_token, "ten_pietential"),
                             json={"workspace_type": wt}, timeout=30)
            assert r.status_code == 200, f"{wt}: {r.text[:200]}"
            assert r.json()["workspace_type"] == wt
        # Leave it on hybrid for downstream tests
        requests.put(f"{BASE_URL}/api/aria/workspace-type",
                     headers=_h(admin_token, "ten_pietential"),
                     json={"workspace_type": "hybrid"}, timeout=30)

    def test_training_profile_get_returns_shape(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/aria/training-profile",
                         headers=_h(admin_token, "ten_pietential"), timeout=20)
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        for k in ("data", "version", "workspace_type", "has_assembled_prompt"):
            assert k in body
        # Data must have all schema fields present even if empty
        for k in ("what_you_sell", "icp_profiles", "qualification_questions",
                  "brand_voice_style", "calendar_link"):
            assert k in body["data"], f"missing data field: {k}"

    def test_training_profile_put_reassembles(self, admin_token):
        r = requests.put(f"{BASE_URL}/api/aria/training-profile",
                         headers=_h(admin_token, "ten_pietential"),
                         json={
                             "what_you_sell": "Test offering",
                             "who_you_sell_to": "Test buyer",
                             "icp_profiles": [{"icp_name": "Test ICP"}],
                         }, timeout=30)
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        assert body["ok"] is True
        assert body["version"] >= 1
        assert body["prompt_length"] > 1000  # full prompt with all sections

    def test_system_prompt_preview_uses_saved_data(self, admin_token):
        # After PUT above, preview should contain the test ICP name.
        r = requests.get(f"{BASE_URL}/api/aria/system-prompt-preview",
                         headers=_h(admin_token, "ten_pietential"), timeout=20)
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        assert body["is_stub"] is False
        assert "Test ICP" in body["prompt"]
        assert "Test offering" in body["prompt"]

    def test_reassemble_endpoint(self, admin_token):
        r = requests.post(f"{BASE_URL}/api/aria/training-profile/reassemble",
                          headers=_h(admin_token, "ten_pietential"), timeout=30)
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        assert body["ok"] is True
        assert body["version"] >= 2  # at least one prior assembly happened


class TestRoleGating:
    def test_sales_rep_blocked_on_put_profile(self, sales_token):
        r = requests.put(f"{BASE_URL}/api/aria/training-profile",
                         headers=_h(sales_token, "ten_demo"),
                         json={"what_you_sell": "should not save"}, timeout=20)
        assert r.status_code in (401, 403), f"sales rep should be blocked: {r.status_code}"

    def test_sales_rep_blocked_on_workspace_type(self, sales_token):
        r = requests.put(f"{BASE_URL}/api/aria/workspace-type",
                         headers=_h(sales_token, "ten_demo"),
                         json={"workspace_type": "b2c"}, timeout=20)
        assert r.status_code in (401, 403), f"sales rep should be blocked: {r.status_code}"


# ─── C. Storage / encryption / aria_agent integration ───────────────────
class TestIntegration:
    def test_stored_prompt_is_encrypted(self):
        t = _db["tenants"].find_one({"id": "ten_pietential"}, {"_id": 0})
        tp = (t.get("settings") or {}).get("aria_training_profile") or {}
        if not tp.get("assembled_prompt"):
            pytest.skip("no assembled prompt yet for ten_pietential")
        # Must be Fernet token, not raw text
        assert tp["assembled_prompt"].startswith("enc::"), \
            "assembled_prompt must be Fernet-encrypted (enc:: prefix)"
        # Must NOT contain raw 'You are Aria' in the encrypted blob
        assert "You are Aria" not in tp["assembled_prompt"]

    def test_aria_agent_uses_assembled_prompt(self):
        from aria_agent import get_aria_system_prompt
        tenant = _db["tenants"].find_one({"id": "ten_pietential"}, {"_id": 0})
        p = get_aria_system_prompt(tenant)
        assert p is not None
        # v2 prompt has section markers; legacy prompt does not
        assert "SECTION 1 — BUSINESS IDENTITY" in p, \
            "get_aria_system_prompt should return the v2 assembled prompt"

    def test_aria_agent_falls_back_when_no_profile(self):
        """A tenant without an assembled profile should fall back to legacy."""
        from aria_agent import get_aria_system_prompt
        fake_tenant = {
            "id": "ten_fake_for_test",
            "name": "Test Co",
            "settings": {"business_profile": {"business_name": "TestCo", "founder_name": "Test"}},
        }
        p = get_aria_system_prompt(fake_tenant)
        # Legacy prompt has different markers
        assert "SECTION 1 — BUSINESS IDENTITY" not in p
        assert "TestCo" in p  # white-label still works
