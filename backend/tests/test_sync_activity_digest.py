"""Tests for GET /api/integrations/digest/today (Sync Activity Digest)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")


@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@demo.com", "password": "Demo1234!"},
        timeout=30,
    )
    assert r.status_code == 200, f"Login failed: {r.text}"
    tok = r.json().get("token") or r.json().get("access_token")
    assert tok
    return tok


@pytest.fixture
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestDigestToday:
    def test_status_and_shape(self, headers):
        r = requests.get(f"{BASE_URL}/api/integrations/digest/today", headers=headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ["today_start", "connected", "any_connected", "counts", "recent"]:
            assert k in data, f"Missing key {k}"
        assert isinstance(data["counts"], dict)
        assert isinstance(data["recent"], list)
        assert "lemlist" in data["connected"]
        assert "saleshandy" in data["connected"]
        for ck in [
            "emails_sent", "emails_opened", "links_clicked", "replies",
            "meetings_booked", "bounced", "pushed_to_sequences", "auto_pushed",
        ]:
            assert ck in data["counts"], f"Missing count {ck}"

    def test_seeded_counts(self, headers):
        r = requests.get(f"{BASE_URL}/api/integrations/digest/today", headers=headers, timeout=30)
        c = r.json()["counts"]
        # Workspace has 7 seeded events from today (per main agent context)
        assert c["emails_sent"] >= 1
        assert c["emails_opened"] >= 2
        assert c["links_clicked"] >= 1
        assert c["replies"] >= 1
        assert c["meetings_booked"] >= 1
        assert c["pushed_to_sequences"] >= 1
        assert c["auto_pushed"] >= 1

    def test_recent_hydrated_with_lead_name(self, headers):
        r = requests.get(f"{BASE_URL}/api/integrations/digest/today", headers=headers, timeout=30)
        recent = r.json()["recent"]
        assert len(recent) > 0
        # Each entry should have lead_name resolved
        for evt in recent:
            assert "lead_name" in evt
            assert "company" in evt
            assert "activity_type" in evt
        names = {evt.get("lead_name") for evt in recent}
        assert any(n for n in names if n), "Expected at least one populated lead_name"

    def test_unauthenticated(self):
        r = requests.get(f"{BASE_URL}/api/integrations/digest/today", timeout=30)
        assert r.status_code in (401, 403)
