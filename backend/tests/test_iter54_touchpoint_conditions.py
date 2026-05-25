"""Iter 54 — Touchpoint conditions + import safety regression tests.

Covers:
  - POST /api/touchpoints/map now accepts `conditions` on each touchpoint
    and validates them against the same schema as the Outreach builder
    (`routes.outreach.validate_conditions`).
  - Saving a touchpoint with malformed conditions returns 400 with a
    descriptive `detail` string (not a Pydantic array).
  - Saved conditions are returned verbatim by GET /api/touchpoints/map.

Run:  cd /app/backend && python -m pytest tests/test_iter54_touchpoint_conditions.py -v
"""
import os
import sys
import requests
import pytest
from pymongo import MongoClient
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

API_URL = os.getenv("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com")
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD", "Demo1234!")
mongo_client = MongoClient(os.environ["MONGO_URL"])
db = mongo_client[os.environ["DB_NAME"]]


@pytest.fixture(scope="module")
def auth():
    r = requests.post(f"{API_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD,
    }, timeout=15)
    assert r.status_code == 200
    data = r.json()
    token = data["token"]
    tenant_id = data["user"].get("tenant_id") or "ten_demo"
    return {
        "headers": {
            "Authorization": f"Bearer {token}",
            "X-Tenant-Id": tenant_id,
            "Content-Type": "application/json",
        },
        "tenant_id": tenant_id,
    }


@pytest.fixture
def baseline_map(auth):
    """Snapshot the current touchpoint map and restore it after the test."""
    r = requests.get(f"{API_URL}/api/touchpoints/map", headers=auth["headers"], timeout=10)
    assert r.status_code == 200
    snapshot = (r.json() or {}).get("map") or {}
    yield snapshot
    # Restore
    requests.post(f"{API_URL}/api/touchpoints/map", headers=auth["headers"], json={
        "template_id": snapshot.get("template_id") or "tpl_standard",
        "is_customised": snapshot.get("is_customised", True),
        "touchpoints": [
            {k: v for k, v in tp.items() if k in (
                "index", "day", "hour", "channel", "message_type",
                "aria_role", "trigger", "message_template", "conditions",
            )}
            for tp in snapshot.get("touchpoints", [])
        ],
    }, timeout=10)


def test_save_map_with_conditions_persists(auth, baseline_map):
    """Save 3 touchpoints, one with full 4-branch conditions, verify round-trip."""
    payload = {
        "template_id": "tpl_standard",
        "is_customised": True,
        "touchpoints": [
            {
                "index": 0, "day": 0, "hour": 9, "channel": "whatsapp",
                "message_type": "intro", "aria_role": "autonomous",
                "trigger": "", "message_template": "Hi {{first_name}}, intro",
                "conditions": {
                    "on_reply": {"action": "notify_user"},
                    "on_keyword_match": {
                        "keywords": ["interested", "pricing"],
                        "action": "tag_contact", "tag": "hot_lead",
                    },
                    "on_negative_keyword": {
                        "keywords": ["not interested", "stop"], "action": "stop",
                    },
                    "on_no_reply": {
                        "after_hours": 72, "action": "move_to_step", "target_step": 2,
                    },
                },
            },
            {
                "index": 1, "day": 2, "hour": 10, "channel": "email",
                "message_type": "follow_up", "aria_role": "autonomous",
                "trigger": "", "message_template": "Following up",
                "conditions": {},
            },
            {
                "index": 2, "day": 5, "hour": 14, "channel": "whatsapp",
                "message_type": "follow_up", "aria_role": "autonomous",
                "trigger": "", "message_template": "Last note",
            },
        ],
    }
    r = requests.post(f"{API_URL}/api/touchpoints/map", headers=auth["headers"], json=payload, timeout=15)
    assert r.status_code == 200, r.text

    # Round-trip
    g = requests.get(f"{API_URL}/api/touchpoints/map", headers=auth["headers"], timeout=10)
    assert g.status_code == 200
    fresh = (g.json() or {}).get("map") or {}
    tp0 = next(t for t in fresh["touchpoints"] if t["index"] == 0)
    assert tp0["conditions"]["on_keyword_match"]["tag"] == "hot_lead"
    assert tp0["conditions"]["on_no_reply"]["after_hours"] == 72
    assert tp0["conditions"]["on_no_reply"]["target_step"] == 2
    tp1 = next(t for t in fresh["touchpoints"] if t["index"] == 1)
    # Empty conditions {} should be allowed and stored as {}
    assert tp1.get("conditions", {}) in ({}, None)


def test_save_map_rejects_malformed_conditions(auth, baseline_map):
    """Bad conditions schema → 400 with descriptive string (not Pydantic array)."""
    payload = {
        "template_id": "tpl_standard",
        "is_customised": True,
        "touchpoints": [
            {
                "index": 0, "day": 0, "hour": 9, "channel": "whatsapp",
                "message_type": "intro", "aria_role": "autonomous",
                "trigger": "", "message_template": "Hi",
                "conditions": {
                    "on_telepathy": {"action": "stop"},  # bogus key
                },
            },
        ],
    }
    r = requests.post(f"{API_URL}/api/touchpoints/map", headers=auth["headers"], json=payload, timeout=10)
    assert r.status_code == 400, r.text
    # detail must be a STRING so the frontend toast can render it
    detail = r.json().get("detail")
    assert isinstance(detail, str)
    assert "unknown_condition_keys" in detail


def test_save_map_rejects_bad_tag_contact_branch(auth, baseline_map):
    """tag_contact action without `tag` → 400."""
    payload = {
        "template_id": "tpl_standard",
        "is_customised": True,
        "touchpoints": [
            {
                "index": 0, "day": 0, "hour": 9, "channel": "whatsapp",
                "message_type": "intro", "aria_role": "autonomous",
                "trigger": "", "message_template": "Hi",
                "conditions": {
                    "on_reply": {"action": "tag_contact"},  # missing tag
                },
            },
        ],
    }
    r = requests.post(f"{API_URL}/api/touchpoints/map", headers=auth["headers"], json=payload, timeout=10)
    assert r.status_code == 400
    detail = r.json().get("detail")
    assert isinstance(detail, str)
    assert "tag" in detail


def test_import_document_rejects_unsupported_format_with_string_detail(auth):
    """The bug we just fixed — import-document must return a STRING detail for
    422-class errors so the React toast doesn't crash trying to render an array."""
    files = {"file": ("bad.txt", b"some text content", "text/plain")}
    r = requests.post(
        f"{API_URL}/api/touchpoints/import-document",
        headers={
            "Authorization": auth["headers"]["Authorization"],
            "X-Tenant-Id": auth["headers"]["X-Tenant-Id"],
        },
        files=files,
        timeout=15,
    )
    # 400 with string detail (preferred), OR 200 if Claude managed to parse plaintext
    assert r.status_code in (400, 415), f"got {r.status_code}: {r.text}"
    detail = r.json().get("detail")
    assert isinstance(detail, str), f"detail must be a string, got {type(detail).__name__}: {detail!r}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
