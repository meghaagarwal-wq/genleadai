"""Iter 20 — Sales Assets, ARIA Brain, Weekly Recap backend tests + regression smoke."""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@demo.com", "password": "Demo1234!"
    }, timeout=20)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    j = r.json()
    tok = j.get("access_token") or j.get("token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def H(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


def _no_objectid(obj):
    """Recursively check no MongoDB `_id` / ObjectId leak."""
    if isinstance(obj, dict):
        assert "_id" not in obj, f"_id leaked in response: {list(obj.keys())}"
        for v in obj.values():
            _no_objectid(v)
    elif isinstance(obj, list):
        for it in obj:
            _no_objectid(it)


# ━━━━━━━━━━━━━━━━━━━━━━━━━ Sales Assets ━━━━━━━━━━━━━━━━━━━━━━━━━

class TestSalesAssets:
    _created_id = None  # shared between tests

    def test_assets_catalog_has_7_types(self, H):
        r = requests.get(f"{BASE_URL}/api/aria-agent/assets/catalog", headers=H, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "types" in d
        types = d["types"]
        assert len(types) == 7, f"expected 7 types, got {len(types)}"
        for t in types:
            for k in ("id", "label", "icon", "description"):
                assert k in t, f"catalog entry missing {k}: {t}"
        ids = {t["id"] for t in types}
        expected = {"message_template", "voice_note", "case_study", "proposal_template",
                    "founder_intro", "objection_response", "pricing_doc"}
        assert ids == expected, f"ids mismatch: {ids} vs {expected}"

    def test_list_assets_shape(self, H):
        r = requests.get(f"{BASE_URL}/api/aria-agent/assets", headers=H, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert set(d.keys()) >= {"assets", "stats", "types"}
        assert isinstance(d["assets"], list)
        stats = d["stats"]
        for k in ("total", "active", "used_this_week", "top_asset", "by_type"):
            assert k in stats, f"stats missing {k}"
        assert isinstance(stats["by_type"], dict)
        assert len(d["types"]) == 7
        _no_objectid(d)

    def test_create_asset(self, H):
        payload = {
            "title": "TEST_iter20_asset",
            "type": "case_study",
            "body": "Case study body content for test.",
            "tags": ["test", "iter20"],
            "channel": "email",
            "used_by_aria": True,
        }
        r = requests.post(f"{BASE_URL}/api/aria-agent/assets", headers=H, json=payload, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["title"] == "TEST_iter20_asset"
        assert d["type"] == "case_study"
        assert "id" in d and isinstance(d["id"], str) and len(d["id"]) > 0
        assert "created_at" in d
        assert d["usage_count"] == 0
        assert d.get("last_used_at") is None
        assert "_id" not in d
        TestSalesAssets._created_id = d["id"]

    def test_created_asset_appears_in_list(self, H):
        assert TestSalesAssets._created_id, "create test must run first"
        r = requests.get(f"{BASE_URL}/api/aria-agent/assets", headers=H, timeout=15)
        assert r.status_code == 200
        ids = [a["id"] for a in r.json()["assets"]]
        assert TestSalesAssets._created_id in ids

    def test_patch_asset(self, H):
        aid = TestSalesAssets._created_id
        assert aid
        payload = {
            "title": "TEST_iter20_asset_UPDATED",
            "type": "case_study",
            "body": "Updated body",
            "tags": ["updated"],
            "channel": "whatsapp",
            "used_by_aria": False,
        }
        r = requests.patch(f"{BASE_URL}/api/aria-agent/assets/{aid}", headers=H, json=payload, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["title"] == "TEST_iter20_asset_UPDATED"
        assert d["channel"] == "whatsapp"
        assert d["used_by_aria"] is False
        assert "_id" not in d
        assert "updated_at" in d

    def test_use_increments_usage(self, H):
        aid = TestSalesAssets._created_id
        assert aid
        # before
        r0 = requests.get(f"{BASE_URL}/api/aria-agent/assets", headers=H, timeout=15)
        before = next((a for a in r0.json()["assets"] if a["id"] == aid), None)
        assert before is not None
        before_count = before.get("usage_count", 0)

        # use
        r = requests.post(f"{BASE_URL}/api/aria-agent/assets/{aid}/use", headers=H, timeout=15)
        assert r.status_code == 200
        assert r.json().get("ok") is True

        # after
        r2 = requests.get(f"{BASE_URL}/api/aria-agent/assets", headers=H, timeout=15)
        after = next((a for a in r2.json()["assets"] if a["id"] == aid), None)
        assert after is not None
        assert after["usage_count"] == before_count + 1
        assert after["last_used_at"] is not None and len(after["last_used_at"]) > 0

    def test_patch_404_on_missing(self, H):
        r = requests.patch(f"{BASE_URL}/api/aria-agent/assets/does-not-exist",
                           headers=H,
                           json={"title": "x", "type": "message_template"},
                           timeout=15)
        assert r.status_code == 404

    def test_delete_asset(self, H):
        aid = TestSalesAssets._created_id
        assert aid
        r = requests.delete(f"{BASE_URL}/api/aria-agent/assets/{aid}", headers=H, timeout=15)
        assert r.status_code == 200
        assert r.json().get("ok") is True
        # second delete -> 404
        r2 = requests.delete(f"{BASE_URL}/api/aria-agent/assets/{aid}", headers=H, timeout=15)
        assert r2.status_code == 404


# ━━━━━━━━━━━━━━━━━━━━━━━━━ ARIA Brain ━━━━━━━━━━━━━━━━━━━━━━━━━

class TestAriaBrain:
    def test_brain_shape(self, H):
        r = requests.get(f"{BASE_URL}/api/aria-agent/brain", headers=H, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("completion_pct", "filled_fields", "total_fields", "sections",
                  "gaps", "learnings", "headline"):
            assert k in d, f"brain missing {k}"
        assert isinstance(d["completion_pct"], int)
        assert 0 <= d["completion_pct"] <= 100
        assert isinstance(d["sections"], list) and len(d["sections"]) == 6
        sec_ids = {s["id"] for s in d["sections"]}
        expected_sec = {"business", "icp", "qualification", "voice", "objections", "booking"}
        assert sec_ids == expected_sec, f"sections: {sec_ids}"
        for sec in d["sections"]:
            for k in ("id", "label", "icon", "filled", "total", "completion_pct", "items"):
                assert k in sec, f"section missing {k}: {sec.keys()}"
            assert isinstance(sec["items"], list)
        assert isinstance(d["gaps"], list) and len(d["gaps"]) <= 8
        assert isinstance(d["learnings"], list) and len(d["learnings"]) >= 1
        assert isinstance(d["headline"], str) and len(d["headline"]) > 0
        _no_objectid(d)


# ━━━━━━━━━━━━━━━━━━━━━━━━━ Weekly Recap ━━━━━━━━━━━━━━━━━━━━━━━━━

class TestWeeklyRecap:
    def test_recap_shape(self, H):
        r = requests.get(f"{BASE_URL}/api/aria-agent/weekly-recap", headers=H, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("headline", "narrative", "stats", "top_channel",
                  "biggest_win", "biggest_miss", "next_week_focus"):
            assert k in d, f"recap missing {k}"
        assert isinstance(d["headline"], str) and len(d["headline"]) > 0
        assert isinstance(d["narrative"], str) and len(d["narrative"]) > 0
        assert isinstance(d["stats"], list) and len(d["stats"]) == 6
        for s in d["stats"]:
            for k in ("label", "value", "delta"):
                assert k in s, f"stat missing {k}"
        labels = {s["label"] for s in d["stats"]}
        expected = {"New leads", "Qualified", "Replies sent", "Calls booked",
                    "Deals won", "Deals lost"}
        assert labels == expected, f"labels {labels}"
        assert isinstance(d["next_week_focus"], list)
        assert len(d["next_week_focus"]) == 3
        _no_objectid(d)


# ━━━━━━━━━━━━━━━━━━━━━━━━━ Regression Smoke ━━━━━━━━━━━━━━━━━━━━━━━━━

REGRESSION_ENDPOINTS = [
    "/api/aria-agent/training",
    "/api/aria-agent/playbooks",
    "/api/aria-agent/handoff/alerts",
    "/api/aria-agent/workspace/stories",
    "/api/aria-agent/workspace/feed",
]


@pytest.mark.parametrize("path", REGRESSION_ENDPOINTS)
def test_regression_smoke(H, path):
    r = requests.get(f"{BASE_URL}{path}", headers=H, timeout=15)
    # accept 200 (endpoint works). 404 => endpoint doesn't exist; report it.
    assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"
    _no_objectid(r.json())
