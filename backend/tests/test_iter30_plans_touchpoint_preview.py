"""Iteration 30 tests:
  - /api/plans/catalog, /status, /select, /contact-sales (DIY/DWY/DFY + trial)
  - /api/touchpoints/preview (Claude-rendered preview)
"""
import os
import time
import uuid

import pytest
import requests

def _load_backend_url():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        envp = "/app/frontend/.env"
        if os.path.exists(envp):
            with open(envp) as fh:
                for line in fh:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        url = line.split("=", 1)[1].strip()
                        break
    if not url:
        raise RuntimeError("REACT_APP_BACKEND_URL is not set")
    return url.rstrip("/")


BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = "Demo1234!"


# ─── Auth helpers ───────────────────────────────────────────────────────────
def _login(email: str, password: str) -> dict:
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()


def _signup(name: str = "Trial Tester") -> dict:
    """Create a brand-new tenant + owner user."""
    uniq = uuid.uuid4().hex[:10]
    payload = {
        "full_name": name,
        "email": f"TEST_iter30_{uniq}@example.com",
        "password": "Trial1234!",
        "workspace_name": f"TEST Iter30 Co {uniq}",
    }
    r = requests.post(f"{API}/auth/signup", json=payload, timeout=20)
    assert r.status_code in (200, 201), f"signup failed: {r.status_code} {r.text}"
    return r.json()


def _hdrs(token: str, tenant_id: str | None = None) -> dict:
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if tenant_id:
        h["X-Tenant-Id"] = tenant_id
    return h


# ─── Fixtures ───────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def admin_session():
    data = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    return {"token": data["token"], "user": data["user"], "tenant_id": "ten_demo"}


@pytest.fixture(scope="module")
def fresh_signup():
    data = _signup()
    return {"token": data["token"], "user": data["user"], "tenant_id": data["tenant"]["id"]}


# ─── /api/plans/catalog ─────────────────────────────────────────────────────
class TestPlansCatalog:
    def test_catalog_returns_three_plans(self, admin_session):
        r = requests.get(f"{API}/plans/catalog", headers=_hdrs(admin_session["token"], admin_session["tenant_id"]), timeout=10)
        assert r.status_code == 200
        plans = r.json()["plans"]
        assert len(plans) == 3
        ids = [p["id"] for p in plans]
        assert ids == ["diy", "dwy", "dfy"]
        prices = {p["id"]: p["price_inr"] for p in plans}
        assert prices == {"diy": 4999, "dwy": 12999, "dfy": 29999}
        # features arrays non-empty
        for p in plans:
            assert isinstance(p["features"], list) and len(p["features"]) > 0
        # DWY popular flag
        assert next(p for p in plans if p["id"] == "dwy")["popular"] is True
        assert next(p for p in plans if p["id"] == "dfy")["managed"] is True


# ─── /api/plans/status ──────────────────────────────────────────────────────
class TestPlansStatus:
    def test_status_for_fresh_signup_stamps_trial(self, fresh_signup):
        r = requests.get(f"{API}/plans/status", headers=_hdrs(fresh_signup["token"], fresh_signup["tenant_id"]), timeout=10)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["plan"] == "trial"
        assert d["on_trial"] is True
        assert d["trial_started_at"] is not None
        assert d["trial_ends_at"] is not None
        assert 12 <= (d["trial_days_left"] or 0) <= 14

    def test_status_is_idempotent(self, fresh_signup):
        r1 = requests.get(f"{API}/plans/status", headers=_hdrs(fresh_signup["token"], fresh_signup["tenant_id"]), timeout=10).json()
        time.sleep(0.5)
        r2 = requests.get(f"{API}/plans/status", headers=_hdrs(fresh_signup["token"], fresh_signup["tenant_id"]), timeout=10).json()
        assert r1["trial_started_at"] == r2["trial_started_at"]
        assert r1["trial_ends_at"] == r2["trial_ends_at"]

    def test_status_preserves_existing_pro_plan(self, admin_session):
        r = requests.get(f"{API}/plans/status", headers=_hdrs(admin_session["token"], admin_session["tenant_id"]), timeout=10)
        assert r.status_code == 200
        d = r.json()
        # ten_demo may have legacy plan='pro' or one of diy/dwy/dfy set by earlier tests.
        assert d["plan"] in ("pro", "diy", "dwy", "dfy", "trial")
        # trial_days_left can still be a non-negative integer
        if d["trial_days_left"] is not None:
            assert d["trial_days_left"] >= 0


# ─── /api/plans/select ──────────────────────────────────────────────────────
class TestPlansSelect:
    def test_select_diy_on_fresh_signup(self, fresh_signup):
        r = requests.post(
            f"{API}/plans/select",
            json={"plan_id": "diy"},
            headers=_hdrs(fresh_signup["token"], fresh_signup["tenant_id"]),
            timeout=10,
        )
        assert r.status_code == 200, r.text
        assert r.json()["plan"] == "diy"
        # verify via GET status
        s = requests.get(f"{API}/plans/status", headers=_hdrs(fresh_signup["token"], fresh_signup["tenant_id"]), timeout=10).json()
        assert s["plan"] == "diy"
        assert s["on_trial"] is False

    def test_invalid_plan_id_400(self, fresh_signup):
        r = requests.post(
            f"{API}/plans/select",
            json={"plan_id": "platinum"},
            headers=_hdrs(fresh_signup["token"], fresh_signup["tenant_id"]),
            timeout=10,
        )
        assert r.status_code == 400

    def test_member_role_forbidden(self):
        # sarah@demo.com is sales_rep on ten_demo
        s = _login("sarah@demo.com", "Demo1234!")
        r = requests.post(
            f"{API}/plans/select",
            json={"plan_id": "dwy"},
            headers=_hdrs(s["token"], "ten_demo"),
            timeout=10,
        )
        assert r.status_code == 403


# ─── /api/plans/contact-sales ───────────────────────────────────────────────
class TestContactSales:
    def test_contact_sales_inserts_inquiry(self, fresh_signup):
        r = requests.post(
            f"{API}/plans/contact-sales",
            json={"note": "TEST iter30 inquiry"},
            headers=_hdrs(fresh_signup["token"], fresh_signup["tenant_id"]),
            timeout=10,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


# ─── /api/touchpoints/preview ───────────────────────────────────────────────
PRODUCT_DESC = (
    "We sell an AI-powered customer support tool for D2C ecommerce brands "
    "that automates WhatsApp replies, recovers abandoned carts and resolves "
    "order-status questions in under 30 seconds."
)


class TestTouchpointPreview:
    def test_preview_returns_two_items_with_claude(self, admin_session):
        body = {
            "template_id": "tpl_considered_sale",
            "business": {"business_name": "DemoCo", "industry": "SaaS", "description": "AI support tool"},
            "persona": {"aria_name": "Aria", "tone": "friendly_professional", "language": "English"},
            "sales": {"product_description": PRODUCT_DESC, "deal_size": "Medium", "sales_cycle": "Medium"},
            "limit": 2,
        }
        r = requests.post(
            f"{API}/touchpoints/preview",
            json=body,
            headers=_hdrs(admin_session["token"], admin_session["tenant_id"]),
            timeout=60,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["template_id"] == "tpl_considered_sale"
        items = d["items"]
        assert len(items) == 2
        for it in items:
            assert "rendered_message" in it
            assert isinstance(it["rendered_message"], str)
            assert len(it["rendered_message"]) > 0
            assert "ai_powered" in it
        # At least one should be AI-powered (Claude available)
        ai_count = sum(1 for it in items if it["ai_powered"])
        # If 0, the key is missing — we still want to know
        assert ai_count >= 1, f"Expected Claude-powered items, got 0. Items: {items}"
        # {first_name} token preserved in AI output
        for it in items:
            if it["ai_powered"]:
                # Claude was instructed to use {{first_name}} token
                assert "{{first_name}}" in it["rendered_message"] or "{first_name}" in it["rendered_message"], \
                    f"first_name token missing from AI output: {it['rendered_message']}"

    def test_preview_invalid_template_404(self, admin_session):
        r = requests.post(
            f"{API}/touchpoints/preview",
            json={"template_id": "tpl_does_not_exist"},
            headers=_hdrs(admin_session["token"], admin_session["tenant_id"]),
            timeout=15,
        )
        assert r.status_code == 404

    def test_preview_limit_1(self, admin_session):
        r = requests.post(
            f"{API}/touchpoints/preview",
            json={
                "template_id": "tpl_considered_sale",
                "sales": {"product_description": PRODUCT_DESC},
                "limit": 1,
            },
            headers=_hdrs(admin_session["token"], admin_session["tenant_id"]),
            timeout=45,
        )
        assert r.status_code == 200
        assert len(r.json()["items"]) == 1

    def test_preview_limit_4(self, admin_session):
        r = requests.post(
            f"{API}/touchpoints/preview",
            json={
                "template_id": "tpl_considered_sale",
                "sales": {"product_description": PRODUCT_DESC},
                "limit": 4,
            },
            headers=_hdrs(admin_session["token"], admin_session["tenant_id"]),
            timeout=120,
        )
        assert r.status_code == 200
        items = r.json()["items"]
        assert 1 <= len(items) <= 4
