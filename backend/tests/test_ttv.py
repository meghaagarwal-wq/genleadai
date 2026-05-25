# Backend tests for Time-to-Value (TTV) feature & regression of related endpoints
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")

ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD", "Demo1234!")
@pytest.fixture(scope="module")
def auth_token():
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=20,
    )
    assert resp.status_code == 200, f"Login failed: {resp.status_code} {resp.text}"
    data = resp.json()
    token = data.get("access_token") or data.get("token")
    assert token, f"No token in login response: {data}"
    return token


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


# ─── TTV endpoint tests ────────────────────────────────────────────────────
class TestTTVMilestones:
    def test_requires_auth(self):
        resp = requests.get(f"{BASE_URL}/api/ttv/milestones", timeout=20)
        assert resp.status_code in (401, 403), f"Expected 401/403 unauth, got {resp.status_code}"

    def test_returns_5_milestones_with_shape(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/api/ttv/milestones", headers=auth_headers, timeout=30)
        assert resp.status_code == 200, f"{resp.status_code}: {resp.text}"
        data = resp.json()

        # Top-level shape
        for key in ("milestones", "completed_count", "total_milestones", "progress_pct", "signup_at"):
            assert key in data, f"Missing key: {key}"
        assert "ttv_to_meeting" in data  # may be None

        assert data["total_milestones"] == 5
        assert isinstance(data["milestones"], list)
        assert len(data["milestones"]) == 5

        expected_ids = ["signup", "first_lead", "first_aria", "first_meeting", "first_won"]
        actual_ids = [m["id"] for m in data["milestones"]]
        assert actual_ids == expected_ids, f"Milestone ids mismatch: {actual_ids}"

        for m in data["milestones"]:
            for k in ("id", "label", "completed", "completed_at", "time_from_start", "icon"):
                assert k in m, f"Milestone {m.get('id')} missing {k}"
            assert isinstance(m["completed"], bool)

        # signup is always completed
        signup = data["milestones"][0]
        assert signup["completed"] is True
        assert signup["time_from_start"] is None

        # progress_pct sanity
        assert 0 <= data["progress_pct"] <= 100
        completed = sum(1 for m in data["milestones"] if m["completed"])
        assert data["completed_count"] == completed
        assert data["progress_pct"] == round((completed / 5) * 100)

    def test_negative_durations_return_none(self, auth_headers):
        """Seeded milestones likely happened BEFORE admin user signup → time_from_start should be None, not negative string."""
        resp = requests.get(f"{BASE_URL}/api/ttv/milestones", headers=auth_headers, timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        for m in data["milestones"]:
            tfs = m["time_from_start"]
            if tfs is not None:
                assert isinstance(tfs, str)
                assert not tfs.startswith("-"), f"Milestone {m['id']} has negative duration: {tfs}"
                # Should also not say negative days
                assert "-" not in tfs.split("d")[0], f"Negative day component in {m['id']}: {tfs}"


# ─── Regression tests for existing endpoints ──────────────────────────────
class TestExistingFlows:
    def test_login(self):
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=20,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("access_token") or body.get("token")

    def test_leads_list(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/api/leads?limit=5", headers=auth_headers, timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert "leads" in data
        assert isinstance(data["leads"], list)

    def test_your_five_today(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/api/leads/your-five-today", headers=auth_headers, timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert "leads" in data
        assert isinstance(data["leads"], list)

    def test_onboarding_status(self, auth_headers):
        resp = requests.get(f"{BASE_URL}/api/onboarding/status", headers=auth_headers, timeout=20)
        assert resp.status_code == 200

    def test_onboarding_complete(self, auth_headers):
        payload = {
            "company_name": "TEST_TTV_CO",
            "founder_name": "TEST_TTV_Founder",
            "industry": "SaaS",
            "team_size": "1-5",
            "calendly_link": "",
            "icp_description": "",
            "completed": True,
        }
        resp = requests.post(
            f"{BASE_URL}/api/onboarding/complete",
            json=payload,
            headers=auth_headers,
            timeout=30,
        )
        assert resp.status_code in (200, 201), f"{resp.status_code}: {resp.text}"
