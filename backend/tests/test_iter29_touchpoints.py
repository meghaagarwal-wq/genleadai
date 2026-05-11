"""Iter 29 — Touchpoint mapping endpoint tests.

Covers /api/touchpoints/templates, /auto-select, /map CRUD, reset, role gating,
and cross-tenant isolation.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")
DEMO_EMAIL = "admin@demo.com"
DEMO_PASSWORD = "Demo1234!"
DEMO_TENANT = "ten_demo"

EXPECTED_TEMPLATES = {
    "tpl_fast_conversion", "tpl_warm_nurture", "tpl_considered_sale",
    "tpl_enterprise_track", "tpl_urgency_led", "tpl_high_intent_qualifier",
    "tpl_abandoned_interest", "tpl_standard",
}


# ─── Fixtures ────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    token = r.json()["token"]
    s.headers.update({"Authorization": f"Bearer {token}", "X-Tenant-Id": DEMO_TENANT})
    return s


@pytest.fixture(scope="module")
def fresh_signup():
    """Create a brand-new signup tenant for isolation tests."""
    ts = int(time.time())
    email = f"iter29_tp_{ts}@example.com"
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/signup", json={
        "email": email, "password": "TestPass123!", "full_name": "Iter29 TP",
        "workspace_name": f"Iter29 TP {ts}",
    })
    assert r.status_code in (200, 201), f"signup failed: {r.status_code} {r.text}"
    data = r.json()
    token = data["token"]
    tenant_id = data["tenant"]["id"]
    s.headers.update({"Authorization": f"Bearer {token}", "X-Tenant-Id": tenant_id})
    return {"session": s, "tenant_id": tenant_id, "email": email}


def _patch_onboarding(session, tenant_id, business=None, sales=None):
    """Helper: patch onboarding_config via the public onboarding endpoint."""
    payload = {}
    if business:
        payload["business_profile"] = business
    if sales:
        payload["sales_process"] = sales
    session.headers["X-Tenant-Id"] = tenant_id
    r = session.post(f"{BASE_URL}/api/onboarding/save-draft", json=payload)
    # Some impls use /complete or /save; fall through gracefully
    return r


# ─── Templates ───────────────────────────────────────────────────────────────
class TestTemplates:
    def test_list_8_templates(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/touchpoints/templates")
        assert r.status_code == 200, r.text
        data = r.json()
        tpls = data.get("templates", [])
        assert len(tpls) == 8, f"expected 8 templates got {len(tpls)}"
        ids = {t["id"] for t in tpls}
        assert ids == EXPECTED_TEMPLATES, f"unexpected ids: {ids ^ EXPECTED_TEMPLATES}"
        for t in tpls:
            assert "name" in t and "description" in t and "duration_days" in t
            assert "match_rules" in t
            assert isinstance(t["touchpoints"], list) and len(t["touchpoints"]) > 0
            tp = t["touchpoints"][0]
            for f in ("index", "day", "hour", "channel", "message_type", "aria_role", "message_template"):
                assert f in tp, f"missing {f} in touchpoint of {t['id']}"

    def test_get_template_valid(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/touchpoints/templates/tpl_standard")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == "tpl_standard"
        assert data["name"] == "Standard"

    def test_get_template_invalid(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/touchpoints/templates/tpl_does_not_exist")
        assert r.status_code == 404


# ─── Auto-select ─────────────────────────────────────────────────────────────
class TestAutoSelect:
    def test_demo_tenant_considered_sale(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/touchpoints/auto-select")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["id"] == "tpl_considered_sale", f"expected considered_sale got {data['id']}"
        assert "selection" in data and "reason" in data["selection"]

    @pytest.mark.parametrize("scenario", [
        ("real_estate_any", {"industry": "Real Estate", "primary_market": "B2B"}, {"sales_cycle": "1-4 weeks", "deal_size": "50K - 5L"}, "tpl_high_intent_qualifier"),
        ("events", {"industry": "Events", "primary_market": "B2C"}, {"sales_cycle": "< 1 week", "deal_size": "< 50K"}, "tpl_urgency_led"),
        ("ecom_b2c", {"industry": "E-commerce", "primary_market": "B2C"}, {"sales_cycle": "1-4 weeks", "deal_size": "< 50K"}, "tpl_abandoned_interest"),
        ("b2c_fast", {"industry": "SaaS", "primary_market": "B2C"}, {"sales_cycle": "< 1 week", "deal_size": "< 50K"}, "tpl_fast_conversion"),
        ("b2b_enterprise", {"industry": "SaaS", "primary_market": "B2B"}, {"sales_cycle": "3+ months", "deal_size": "50L+"}, "tpl_enterprise_track"),
    ])
    def test_auto_select_scenarios(self, fresh_signup, scenario):
        name, biz, sales, expected_tpl = scenario
        s = fresh_signup["session"]
        tid = fresh_signup["tenant_id"]
        # Use save-draft endpoint to update onboarding_config without forcing completion
        s.headers["X-Tenant-Id"] = tid
        # Build a complete business + sales payload
        body = {
            "business_profile": {"business_name": "Iter29", "industry": biz["industry"], "primary_market": biz["primary_market"], "description": "test"},
            "sales_process": {"product_description": "p", "sales_cycle": sales["sales_cycle"], "deal_size": sales["deal_size"], "qualification_criteria": ["budget_confirmed"], "pipeline_stages": ["A", "B"]},
        }
        # Use complete endpoint (idempotent upsert of onboarding_config)
        body_full = {
            "business_profile": body["business_profile"],
            "aria_persona": {"aria_name": "Aria", "tone": "friendly_professional", "language": "English", "fallback_behavior": "ask_clarifying"},
            "sales_process": body["sales_process"],
            "whatsapp_config": {"provider": "meta"},
            "completed": False,
        }
        r = s.post(f"{BASE_URL}/api/onboarding/complete", json=body_full)
        assert r.status_code in (200, 201), f"save onboarding failed [{name}]: {r.status_code} {r.text}"

        rr = s.get(f"{BASE_URL}/api/touchpoints/auto-select")
        assert rr.status_code == 200, rr.text
        got = rr.json()["id"]
        assert got == expected_tpl, f"[{name}] expected {expected_tpl} got {got}"


# ─── Map CRUD ────────────────────────────────────────────────────────────────
class TestMapCRUD:
    def _sample_payload(self, n=3):
        tps = []
        for i in range(n):
            tps.append({
                "index": i, "day": float(i), "hour": 0,
                "channel": "whatsapp", "message_type": "intro" if i == 0 else "follow_up",
                "aria_role": "autonomous", "trigger": "test",
                "message_template": f"Hi there #{i}"
            })
        return {"template_id": "tpl_standard", "is_customised": False, "touchpoints": tps}

    def test_save_and_get_map(self, admin_session):
        payload = self._sample_payload(3)
        # Use non-contiguous indexes to test re-indexing
        for i, t in enumerate(payload["touchpoints"]):
            t["index"] = i * 10
        r = admin_session.post(f"{BASE_URL}/api/touchpoints/map", json=payload)
        assert r.status_code == 200, r.text
        m = r.json()["map"]
        assert m["touchpoint_count"] == 3
        for i, tp in enumerate(m["touchpoints"]):
            assert tp["index"] == i, f"index not re-indexed: {tp['index']} expected {i}"

        rg = admin_session.get(f"{BASE_URL}/api/touchpoints/map")
        assert rg.status_code == 200
        gm = rg.json()["map"]
        assert gm is not None
        assert gm["touchpoint_count"] == 3
        assert gm["tenant_id"] == DEMO_TENANT

    def test_validation_invalid_channel(self, admin_session):
        p = self._sample_payload(1)
        p["touchpoints"][0]["channel"] = "sms"
        r = admin_session.post(f"{BASE_URL}/api/touchpoints/map", json=p)
        assert r.status_code == 400, r.text

    def test_validation_invalid_role(self, admin_session):
        p = self._sample_payload(1)
        p["touchpoints"][0]["aria_role"] = "hybrid"
        r = admin_session.post(f"{BASE_URL}/api/touchpoints/map", json=p)
        assert r.status_code == 400

    def test_validation_invalid_msg_type(self, admin_session):
        p = self._sample_payload(1)
        p["touchpoints"][0]["message_type"] = "chitchat"
        r = admin_session.post(f"{BASE_URL}/api/touchpoints/map", json=p)
        assert r.status_code == 400

    def test_validation_empty_message(self, admin_session):
        p = self._sample_payload(1)
        p["touchpoints"][0]["message_template"] = "   "
        r = admin_session.post(f"{BASE_URL}/api/touchpoints/map", json=p)
        assert r.status_code == 400

    def test_validation_empty_list(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/touchpoints/map", json={"template_id": "tpl_standard", "is_customised": False, "touchpoints": []})
        assert r.status_code in (400, 422)

    def test_validation_too_many(self, admin_session):
        p = self._sample_payload(31)
        r = admin_session.post(f"{BASE_URL}/api/touchpoints/map", json=p)
        assert r.status_code == 400

    def test_reset_map(self, admin_session):
        # First save customised
        p = self._sample_payload(2)
        p["is_customised"] = True
        admin_session.post(f"{BASE_URL}/api/touchpoints/map", json=p)
        # Reset
        r = admin_session.post(f"{BASE_URL}/api/touchpoints/map/reset")
        assert r.status_code == 200, r.text
        m = r.json()["map"]
        assert m["is_customised"] is False
        # Verify GET reflects reset
        rg = admin_session.get(f"{BASE_URL}/api/touchpoints/map")
        assert rg.json()["map"]["is_customised"] is False

    def test_delete_map(self, admin_session):
        # Ensure something saved
        admin_session.post(f"{BASE_URL}/api/touchpoints/map", json=self._sample_payload(2))
        r = admin_session.delete(f"{BASE_URL}/api/touchpoints/map")
        assert r.status_code == 200
        rg = admin_session.get(f"{BASE_URL}/api/touchpoints/map")
        assert rg.json()["map"] is None


# ─── Role gating ─────────────────────────────────────────────────────────────
class TestRoleGating:
    def test_sales_rep_cannot_save(self):
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        r = s.post(f"{BASE_URL}/api/auth/login", json={"email": "sarah@demo.com", "password": "Demo1234!"})
        if r.status_code != 200:
            pytest.skip("sarah@demo.com not available")
        s.headers.update({"Authorization": f"Bearer {r.json()['token']}", "X-Tenant-Id": DEMO_TENANT})
        body = {"template_id": "tpl_standard", "is_customised": False, "touchpoints": [
            {"index": 0, "day": 0, "hour": 0, "channel": "whatsapp", "message_type": "intro",
             "aria_role": "autonomous", "trigger": "", "message_template": "hi"}
        ]}
        rr = s.post(f"{BASE_URL}/api/touchpoints/map", json=body)
        assert rr.status_code == 403, f"expected 403 got {rr.status_code} {rr.text}"
        rd = s.delete(f"{BASE_URL}/api/touchpoints/map")
        assert rd.status_code == 403


# ─── Cross-tenant isolation ──────────────────────────────────────────────────
class TestIsolation:
    def test_isolation(self, admin_session, fresh_signup):
        # Save map for demo
        body = {"template_id": "tpl_standard", "is_customised": False, "touchpoints": [
            {"index": 0, "day": 0, "hour": 0, "channel": "whatsapp", "message_type": "intro",
             "aria_role": "autonomous", "trigger": "", "message_template": "demo only"}
        ]}
        admin_session.headers["X-Tenant-Id"] = DEMO_TENANT
        r = admin_session.post(f"{BASE_URL}/api/touchpoints/map", json=body)
        assert r.status_code == 200
        # Fresh tenant should see no map
        s = fresh_signup["session"]
        s.headers["X-Tenant-Id"] = fresh_signup["tenant_id"]
        rg = s.get(f"{BASE_URL}/api/touchpoints/map")
        assert rg.status_code == 200
        assert rg.json()["map"] is None, f"leak detected: {rg.json()}"

    def test_seeded_in_mongo(self, admin_session):
        # Indirect verification: list returns 8 — direct mongo check would require admin route
        r = admin_session.get(f"{BASE_URL}/api/touchpoints/templates")
        assert len(r.json()["templates"]) == 8
