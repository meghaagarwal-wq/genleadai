"""Iter76 tests — Aria Health badges + Auto-Map summary re-hydrate."""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://pipeline-pro-96.preview.emergentagent.com').rstrip('/')
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD", "Demo1234!")
TENANT_ID = "ten_demo"


@pytest.fixture(scope="module")
def auth_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD,
    }, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    token = r.json().get("token") or r.json().get("access_token")
    assert token
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": TENANT_ID,
        "Content-Type": "application/json",
    }


# --- /api/aria-agent/health ---
class TestAriaHealth:
    def test_health_endpoint_returns_200_and_shape(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/aria-agent/health", headers=auth_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "overall" in data
        assert data["overall"] in ("green", "amber", "red")
        assert "score" in data and isinstance(data["score"], str)
        assert "cards" in data and isinstance(data["cards"], list)
        assert len(data["cards"]) == 7

    def test_health_cards_have_all_required_keys(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/aria-agent/health", headers=auth_headers, timeout=30)
        data = r.json()
        required_keys = {"key", "label", "value", "level", "hint", "action_path", "action_label"}
        for card in data["cards"]:
            missing = required_keys - set(card.keys())
            assert not missing, f"Card {card.get('key')} missing keys: {missing}"
            assert card["level"] in ("green", "amber", "red")

    def test_health_has_all_7_expected_capabilities(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/aria-agent/health", headers=auth_headers, timeout=30)
        data = r.json()
        keys = {c["key"] for c in data["cards"]}
        expected = {"training", "playbooks", "journey", "auto_setup", "integrations", "sales_channels", "brain"}
        assert keys == expected, f"Expected {expected}, got {keys}"

    def test_health_training_card_action_points_to_settings(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/aria-agent/health", headers=auth_headers, timeout=30)
        data = r.json()
        training = next(c for c in data["cards"] if c["key"] == "training")
        assert training["action_path"] == "/settings"


# --- /api/aria/auto-map/summary ---
class TestAutoMapSummary:
    def test_summary_endpoint_returns_200(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/aria/auto-map/summary", headers=auth_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "summary" in data

    def test_summary_returns_populated_object_when_published(self, auth_headers):
        # First publish a synthetic summary
        publish_payload = {
            "icps": [],
            "touchpoints": [],
            "touchpoints_extracted": [
                {
                    "entry_point": "TEST_iter76 cold email - Saleshandy",
                    "channel_or_tool": "Saleshandy",
                    "flow_steps": ["Email 1", "Email 2"],
                    "timeline": "Day 1-7",
                    "outcome": "Positive reply -> alert founder",
                }
            ],
            "lead_sources": ["Saleshandy"],
            "summary": "TEST_iter76 synthetic publish",
            "overwrite_journey": False,
            "apply_sales_channels": False,
        }
        rp = requests.post(
            f"{BASE_URL}/api/aria/auto-map/publish",
            headers=auth_headers, json=publish_payload, timeout=30,
        )
        assert rp.status_code == 200, f"Publish failed: {rp.status_code} {rp.text}"
        assert rp.json().get("touchpoints_extracted_saved") == 1

        # Now GET summary
        r = requests.get(f"{BASE_URL}/api/aria/auto-map/summary", headers=auth_headers, timeout=30)
        assert r.status_code == 200
        summary = r.json().get("summary")
        assert summary is not None, "summary should be populated after publish"
        assert "touchpoints_extracted" in summary
        assert len(summary["touchpoints_extracted"]) >= 1
        assert "applied_at" in summary

    def test_summary_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/aria/auto-map/summary", timeout=10)
        assert r.status_code in (401, 403)
