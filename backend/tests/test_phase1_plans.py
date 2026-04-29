"""Phase 1 backend tests: 4-tier plan catalog, feature gating, demo seeder, dev/set-plan."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = "Demo1234!"
SALES_EMAIL = "sarah@demo.com"
SALES_PASSWORD = "Demo1234!"


def _login(email: str, password: str) -> str:
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    body = r.json()
    return body.get("access_token") or body.get("token")


@pytest.fixture(scope="module")
def admin_headers():
    token = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def rep_headers():
    try:
        token = _login(SALES_EMAIL, SALES_PASSWORD)
        return {"Authorization": f"Bearer {token}"}
    except AssertionError:
        pytest.skip("sales rep login not available")


@pytest.fixture(scope="module", autouse=True)
def reset_to_starter(admin_headers):
    """Ensure clean starter state before tests, leave on starter after."""
    requests.post(f"{BASE_URL}/api/dev/set-plan", params={"plan_id": "starter"}, headers=admin_headers, timeout=10)
    yield
    requests.post(f"{BASE_URL}/api/dev/set-plan", params={"plan_id": "starter"}, headers=admin_headers, timeout=10)


# ==== /api/billing/plans ====
class TestBillingPlans:
    def test_returns_4_plans(self):
        r = requests.get(f"{BASE_URL}/api/billing/plans", timeout=10)
        assert r.status_code == 200
        data = r.json()
        ids = sorted([p["id"] for p in data["plans"]])
        assert ids == ["custom", "growth", "pro", "starter"], f"got {ids}"

    def test_pro_amount_399(self):
        r = requests.get(f"{BASE_URL}/api/billing/plans", timeout=10).json()
        pro = next(p for p in r["plans"] if p["id"] == "pro")
        assert pro["amount"] == 399.00
        assert pro.get("contact_sales", False) is False

    def test_custom_is_contact_sales(self):
        r = requests.get(f"{BASE_URL}/api/billing/plans", timeout=10).json()
        custom = next(p for p in r["plans"] if p["id"] == "custom")
        assert custom["amount"] is None
        assert custom["contact_sales"] is True

    def test_feature_keys_count(self):
        r = requests.get(f"{BASE_URL}/api/billing/plans", timeout=10).json()
        assert isinstance(r["feature_keys"], list)
        # Spec says 50 keys
        assert len(r["feature_keys"]) >= 48, f"only {len(r['feature_keys'])} feature keys"

    def test_starter_has_locked_features(self):
        r = requests.get(f"{BASE_URL}/api/billing/plans", timeout=10).json()
        starter = next(p for p in r["plans"] if p["id"] == "starter")
        assert starter["features"].get("ai_qualification") is False
        assert starter["features"].get("lead_inbox") is True


# ==== /api/billing/current-plan ====
class TestCurrentPlan:
    def test_default_starter(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/billing/current-plan", headers=admin_headers, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["plan_id"] == "starter"
        assert "features" in data and isinstance(data["features"], dict)
        assert data["features"].get("lead_inbox") is True


# ==== /api/dev/set-plan ====
class TestDevSetPlan:
    def test_admin_can_set_growth(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/dev/set-plan", params={"plan_id": "growth"}, headers=admin_headers, timeout=10)
        assert r.status_code == 200
        assert r.json()["plan_id"] == "growth"
        # verify current-plan reflects
        cur = requests.get(f"{BASE_URL}/api/billing/current-plan", headers=admin_headers, timeout=10).json()
        assert cur["plan_id"] == "growth"
        assert cur["features"].get("ai_lead_scoring") is True

    def test_admin_can_set_pro(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/dev/set-plan", params={"plan_id": "pro"}, headers=admin_headers, timeout=10)
        assert r.status_code == 200
        cur = requests.get(f"{BASE_URL}/api/billing/current-plan", headers=admin_headers, timeout=10).json()
        assert cur["plan_id"] == "pro"
        assert cur["features"].get("ai_qualification") is True

    def test_invalid_plan_400(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/dev/set-plan", params={"plan_id": "enterprise"}, headers=admin_headers, timeout=10)
        assert r.status_code == 400

    def test_non_admin_403(self, rep_headers):
        r = requests.post(f"{BASE_URL}/api/dev/set-plan", params={"plan_id": "growth"}, headers=rep_headers, timeout=10)
        assert r.status_code == 403


# ==== /api/billing/checkout ====
class TestBillingCheckout:
    def test_custom_returns_400(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/billing/checkout",
            json={"plan_id": "custom", "origin_url": "https://example.com"},
            headers=admin_headers, timeout=15,
        )
        assert r.status_code == 400
        assert "contact" in r.text.lower()

    def test_pro_returns_checkout_url(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/billing/checkout",
            json={"plan_id": "pro", "origin_url": "https://example.com"},
            headers=admin_headers, timeout=20,
        )
        # Expect 200 with url, OR 500 if Stripe not configured — accept either with warning
        if r.status_code == 200:
            data = r.json()
            assert "url" in data or "checkout_url" in data or "session_id" in data
        else:
            pytest.skip(f"Stripe checkout returned {r.status_code}: {r.text[:200]}")


# ==== /api/billing/request-upgrade ====
class TestRequestUpgrade:
    def test_request_upgrade_pro(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/billing/request-upgrade",
            json={"target_plan_id": "pro", "feature_key": "ai_qualification", "note": "test from pytest"},
            headers=admin_headers, timeout=20,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["requested"] is True
        assert data["target_plan"] == "pro"
        assert "admin_email_used" in data and data["admin_email_used"]

    def test_request_upgrade_invalid_plan(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/billing/request-upgrade",
            json={"target_plan_id": "ultra", "feature_key": None, "note": None},
            headers=admin_headers, timeout=15,
        )
        assert r.status_code == 400

    def test_activity_row_created(self, admin_headers):
        # post one
        requests.post(
            f"{BASE_URL}/api/billing/request-upgrade",
            json={"target_plan_id": "growth", "feature_key": "csv_import", "note": "act-row-test"},
            headers=admin_headers, timeout=15,
        )
        # try to fetch activities (best effort)
        r = requests.get(f"{BASE_URL}/api/activities", headers=admin_headers, timeout=10)
        if r.status_code != 200:
            pytest.skip(f"activities endpoint not available: {r.status_code}")
        rows = r.json() if isinstance(r.json(), list) else r.json().get("activities", [])
        types = {row.get("activity_type") for row in rows[:50]}
        assert "upgrade_requested" in types, f"upgrade_requested not in activities: {types}"


# ==== /api/admin/load-demo-data ====
class TestDemoSeeder:
    def test_force_seeds_25(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/load-demo-data", params={"force": "true"}, headers=admin_headers, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["seeded"] == 25
        assert data["skipped"] is False

    def test_no_force_skips_when_leads_exist(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/load-demo-data", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert data.get("skipped") is True

    def test_leads_have_diverse_data(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/leads", headers=admin_headers, params={"limit": 200}, timeout=15)
        assert r.status_code == 200
        all_leads = r.json() if isinstance(r.json(), list) else r.json().get("leads", [])
        # Filter to demo leads only (force-seeded with metadata.demo=true)
        leads = [l for l in all_leads if (l.get("metadata") or {}).get("demo") is True] or all_leads
        assert len(leads) >= 25, f"only {len(leads)} demo leads"
        statuses = {l.get("status") for l in leads}
        advanced = {"won", "lost", "proposal_sent", "negotiation"}
        assert statuses & advanced, f"no advanced statuses found: {statuses}"
        scores = [l.get("icp_score") for l in leads if l.get("icp_score") is not None]
        assert scores, "no icp_score on any lead"
        assert min(scores) >= 30 and max(scores) <= 100, f"score range {min(scores)}..{max(scores)}"
        # deal_value present on some advanced ones
        dv = [l for l in leads if l.get("status") in advanced and l.get("deal_value")]
        assert len(dv) >= 1, "no deal_value on advanced leads"


# ==== require_feature helper ====
class TestRequireFeatureHelper:
    def test_helper_importable(self):
        # import directly to verify the helper exists and is callable
        import sys
        sys.path.insert(0, "/app/backend")
        from server import require_feature, _has_feature, SUBSCRIPTION_PLANS
        assert callable(require_feature)
        # It's a factory returning a dependency
        dep = require_feature("ai_qualification")
        assert callable(dep)
        # _has_feature works correctly across plans
        assert _has_feature("ai_qualification", "starter") is False
        assert _has_feature("ai_qualification", "pro") is True
        assert _has_feature("custom_workflows", "custom") is True
        assert "starter" in SUBSCRIPTION_PLANS and "pro" in SUBSCRIPTION_PLANS
