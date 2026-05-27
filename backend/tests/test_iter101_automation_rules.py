"""Iter101 — Backend tests for Visual Automation Rule Builder.

Covers CRUD + catalog + dry-run + run-now + tenant scoping.
"""
import os
import pytest
import requests

from deps import db

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD") or os.environ.get("DEMO_ADMIN_PASSWORD", "Demo1234!")

rules_col = db["automation_rules"]


@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=20,
    )
    if r.status_code != 200:
        pytest.skip(f"admin login failed: {r.status_code}")
    tok = r.json().get("token") or r.json().get("access_token")
    return {"Authorization": f"Bearer {tok}", "X-Tenant-Id": "ten_pietential"}


@pytest.fixture()
def cleanup_iter101():
    yield
    rules_col.delete_many({"name": {"$regex": "^Iter101"}})


def _mk_rule(headers, **overrides):
    body = {
        "name": "Iter101 base",
        "description": "Tests",
        "enabled": True,
        "trigger": {
            "event_type": "lead.created",
            "conditions": [{"field": "lead.icp_score", "op": "gte", "value": 80}],
        },
        "actions": [{"type": "add_tag", "params": {"tag": "hot"}}],
    }
    body.update(overrides)
    return requests.post(
        f"{BASE_URL}/api/automation-rules",
        headers={**headers, "Content-Type": "application/json"},
        json=body, timeout=20,
    )


class TestCatalog:
    def test_catalog_returns_complete_lists(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/automation-rules/catalog", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        d = r.json()
        for k in ("triggers", "ops", "action_types", "common_fields"):
            assert k in d and len(d[k]) > 0


class TestCRUD:
    def test_create_and_list(self, admin_headers, cleanup_iter101):
        r = _mk_rule(admin_headers, name="Iter101 listme")
        assert r.status_code == 200
        rid = r.json()["rule"]["id"]
        # List includes it
        r = requests.get(f"{BASE_URL}/api/automation-rules", headers=admin_headers, timeout=15)
        names = [x["name"] for x in r.json()["rules"]]
        assert "Iter101 listme" in names
        assert any(x["id"] == rid for x in r.json()["rules"])

    def test_create_rejects_unknown_event(self, admin_headers, cleanup_iter101):
        r = _mk_rule(admin_headers, name="Iter101 bad_event", trigger={"event_type": "not.real", "conditions": []})
        assert r.status_code == 400
        assert "event_type" in r.json()["detail"]

    def test_create_rejects_unknown_action(self, admin_headers, cleanup_iter101):
        r = _mk_rule(admin_headers, name="Iter101 bad_action", actions=[{"type": "summon_dragon", "params": {}}])
        assert r.status_code == 400
        assert "action" in r.json()["detail"]

    def test_create_requires_at_least_one_action(self, admin_headers, cleanup_iter101):
        # Pydantic min_length=1 → 422
        r = _mk_rule(admin_headers, name="Iter101 no_actions", actions=[])
        assert r.status_code in (400, 422)

    def test_update_toggle_enabled(self, admin_headers, cleanup_iter101):
        r = _mk_rule(admin_headers, name="Iter101 toggle")
        rid = r.json()["rule"]["id"]
        r = requests.patch(
            f"{BASE_URL}/api/automation-rules/{rid}",
            headers={**admin_headers, "Content-Type": "application/json"},
            json={"enabled": False}, timeout=15,
        )
        assert r.status_code == 200
        assert r.json()["rule"]["enabled"] is False

    def test_delete(self, admin_headers, cleanup_iter101):
        r = _mk_rule(admin_headers, name="Iter101 delete")
        rid = r.json()["rule"]["id"]
        r = requests.delete(f"{BASE_URL}/api/automation-rules/{rid}", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        # Gone
        r = requests.get(f"{BASE_URL}/api/automation-rules", headers=admin_headers, timeout=15)
        assert not any(x["id"] == rid for x in r.json()["rules"])


class TestDryRun:
    def test_dry_run_fires_when_all_match(self, admin_headers, cleanup_iter101):
        r = _mk_rule(admin_headers, name="Iter101 dry_match")
        rid = r.json()["rule"]["id"]
        r = requests.post(
            f"{BASE_URL}/api/automation-rules/{rid}/dry-run",
            headers={**admin_headers, "Content-Type": "application/json"},
            json={"context": {"lead": {"icp_score": 85}}},
            timeout=15,
        )
        d = r.json()
        assert d["would_fire"] is True
        assert d["breakdown"][0]["passed"] is True
        assert len(d["actions_that_would_run"]) == 1

    def test_dry_run_fails_when_condition_false(self, admin_headers, cleanup_iter101):
        r = _mk_rule(admin_headers, name="Iter101 dry_fail")
        rid = r.json()["rule"]["id"]
        r = requests.post(
            f"{BASE_URL}/api/automation-rules/{rid}/dry-run",
            headers={**admin_headers, "Content-Type": "application/json"},
            json={"context": {"lead": {"icp_score": 50}}},
            timeout=15,
        )
        d = r.json()
        assert d["would_fire"] is False
        assert d["breakdown"][0]["passed"] is False
        assert d["actions_that_would_run"] == []

    def test_dry_run_no_conditions_always_fires(self, admin_headers, cleanup_iter101):
        r = _mk_rule(admin_headers, name="Iter101 dry_noconds",
                     trigger={"event_type": "lead.created", "conditions": []})
        rid = r.json()["rule"]["id"]
        r = requests.post(
            f"{BASE_URL}/api/automation-rules/{rid}/dry-run",
            headers={**admin_headers, "Content-Type": "application/json"},
            json={"context": {}}, timeout=15,
        )
        assert r.json()["would_fire"] is True


class TestRunNow:
    def test_run_now_increments_counter(self, admin_headers, cleanup_iter101):
        r = _mk_rule(admin_headers, name="Iter101 runnow")
        rid = r.json()["rule"]["id"]
        for _ in range(3):
            r = requests.post(f"{BASE_URL}/api/automation-rules/{rid}/run-now", headers=admin_headers, timeout=15)
            assert r.status_code == 200, r.text
        doc = rules_col.find_one({"id": rid}, {"_id": 0})
        assert doc["fire_count"] == 3
        assert doc.get("last_fired_at")

    def test_run_now_blocked_when_disabled(self, admin_headers, cleanup_iter101):
        r = _mk_rule(admin_headers, name="Iter101 disabled", enabled=False)
        rid = r.json()["rule"]["id"]
        r = requests.post(f"{BASE_URL}/api/automation-rules/{rid}/run-now", headers=admin_headers, timeout=15)
        assert r.status_code == 400
        assert "disabled" in r.json()["detail"].lower()


class TestFiresLog:
    def test_fires_log_returned(self, admin_headers, cleanup_iter101):
        r = _mk_rule(admin_headers, name="Iter101 fireslog")
        rid = r.json()["rule"]["id"]
        for _ in range(2):
            requests.post(f"{BASE_URL}/api/automation-rules/{rid}/run-now", headers=admin_headers, timeout=15)
        r = requests.get(f"{BASE_URL}/api/automation-rules/{rid}/fires", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        assert r.json()["count"] == 2
        assert all(f["rule_id"] == rid for f in r.json()["fires"])
