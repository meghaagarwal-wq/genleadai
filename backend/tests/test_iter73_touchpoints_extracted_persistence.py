"""Iter 73 — Validate that POST /api/aria/auto-map/publish persists user-edited
`touchpoints_extracted` array into tenant.settings.automap_summary, and that a
subsequent fetch (via /api/insights/founder-command-center which exposes
automap_summary, OR direct MongoDB read) preserves the edited values.

Strategy:
- Login as admin@demo.com / Demo1234!
- POST /publish with a synthetic touchpoints_extracted payload (skip /analyze
  to keep tests fast & deterministic — Claude latency isn't what we're
  validating here; the persistence path is).
- Assert response.touchpoints_extracted_saved matches the edited count.
- Verify persistence by reading tenant.settings.automap_summary from MongoDB.
"""
import os
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "aria_db")

ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = "Demo1234!"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def auth(session):
    r = session.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("token") or data.get("access_token")
    assert token, f"No token in login response: {data}"
    user = data.get("user") or {}
    tenants = user.get("tenants") or data.get("tenants") or []
    tenant_id = None
    if tenants and isinstance(tenants, list):
        first = tenants[0]
        tenant_id = first.get("id") if isinstance(first, dict) else first
    if not tenant_id:
        # fallback — fetch /api/tenants/me
        h = {"Authorization": f"Bearer {token}"}
        rt = session.get(f"{BASE_URL}/api/tenants/me", headers=h, timeout=15)
        if rt.status_code == 200:
            j = rt.json()
            tenant_id = j.get("id") or (j.get("tenants") or [{}])[0].get("id")
    assert tenant_id, "Could not determine tenant_id"
    session.headers.update({"Authorization": f"Bearer {token}", "X-Tenant-Id": tenant_id})
    return {"token": token, "tenant_id": tenant_id}


@pytest.fixture(scope="module")
def mongo():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    yield db
    client.close()


def _sample_extracted_payload():
    """Synthetic edited touchpoints_extracted as if the user just used the inline editor."""
    return [
        {
            "entry_point": "Cold email - Saleshandy (EDITED by user)",
            "channel_or_tool": "Saleshandy",
            "flow_steps": ["Email 1: Intro", "Email 2: Value drop", "Email 3: Soft CTA"],
            "timeline": "Day 1-12",
            "outcome": "Positive reply -> route to John. No reply -> close.",
        },
        {
            "entry_point": "LinkedIn DM - Lemlist",
            "channel_or_tool": "Lemlist",
            "flow_steps": ["DM 1", "DM 2"],
            "timeline": "Day 3-10",
            "outcome": "Reply -> book demo",
        },
    ]


# ─── publish endpoint persistence ──────────────────────────────────────────
class TestTouchpointsExtractedPersistence:
    def test_publish_includes_touchpoints_extracted_count(self, session, auth):
        payload = {
            "icps": [],
            "touchpoints": [],
            "touchpoints_extracted": _sample_extracted_payload(),
            "lead_sources": ["Saleshandy", "Lemlist"],
            "recommended_integrations": ["saleshandy", "lemlist"],
            "sales_channels": ["email", "linkedin"],
            "qualification": {"must_have_criteria": [], "disqualifiers": []},
            "handoff": {"trigger": "", "alert_channels": []},
            "summary": "Iter73 persistence test",
            "overwrite_journey": False,  # don't touch real journey
            "apply_sales_channels": False,
            "force_empty_overwrite": False,
        }
        r = session.post(f"{BASE_URL}/api/aria/auto-map/publish", json=payload, timeout=30)
        assert r.status_code == 200, f"publish failed: {r.status_code} {r.text}"
        data = r.json()
        assert data.get("ok") is True
        assert data.get("touchpoints_extracted_saved") == 2, f"Expected 2, got {data}"

    def test_persisted_in_tenant_settings_automap_summary(self, mongo, auth):
        tenant = mongo["tenants"].find_one({"id": auth["tenant_id"]}, {"settings.automap_summary": 1, "_id": 0})
        assert tenant, "Tenant not found in MongoDB"
        automap = (tenant.get("settings") or {}).get("automap_summary") or {}
        tps = automap.get("touchpoints_extracted") or []
        assert len(tps) == 2, f"Expected 2 touchpoints persisted, got {len(tps)}: {tps}"
        # Validate the user's EDIT survived (not the raw doc text).
        assert tps[0]["entry_point"] == "Cold email - Saleshandy (EDITED by user)"
        assert tps[0]["channel_or_tool"] == "Saleshandy"
        assert tps[0]["timeline"] == "Day 1-12"
        assert "Email 1: Intro" in tps[0]["flow_steps"]
        assert tps[1]["entry_point"] == "LinkedIn DM - Lemlist"

    def test_publish_with_empty_touchpoints_extracted_resets(self, session, auth, mongo):
        """If user deletes ALL extracted rows then publishes, persisted array is empty."""
        payload = {
            "icps": [], "touchpoints": [],
            "touchpoints_extracted": [],
            "lead_sources": [], "recommended_integrations": [], "sales_channels": [],
            "qualification": {}, "handoff": {}, "summary": "empty test",
            "overwrite_journey": False, "apply_sales_channels": False, "force_empty_overwrite": False,
        }
        r = session.post(f"{BASE_URL}/api/aria/auto-map/publish", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json().get("touchpoints_extracted_saved") == 0
        tenant = mongo["tenants"].find_one({"id": auth["tenant_id"]}, {"settings.automap_summary": 1, "_id": 0})
        automap = (tenant.get("settings") or {}).get("automap_summary") or {}
        assert automap.get("touchpoints_extracted") == []

    def test_publish_payload_accepts_user_edits(self, session, auth, mongo):
        """Verify a 1-row payload with arbitrary user edits survives intact."""
        edited = [{
            "entry_point": "USER EDITED entry",
            "channel_or_tool": "Custom Tool",
            "flow_steps": ["Step A", "Step B", "Step C"],
            "timeline": "Day 0-7 USER",
            "outcome": "USER EDITED outcome string",
        }]
        payload = {
            "icps": [], "touchpoints": [], "touchpoints_extracted": edited,
            "lead_sources": [], "recommended_integrations": [], "sales_channels": [],
            "qualification": {}, "handoff": {}, "summary": "",
            "overwrite_journey": False, "apply_sales_channels": False, "force_empty_overwrite": False,
        }
        r = session.post(f"{BASE_URL}/api/aria/auto-map/publish", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        # Re-read from DB to confirm
        tenant = mongo["tenants"].find_one({"id": auth["tenant_id"]}, {"settings.automap_summary": 1, "_id": 0})
        tps = ((tenant or {}).get("settings") or {}).get("automap_summary", {}).get("touchpoints_extracted") or []
        assert len(tps) == 1
        assert tps[0]["entry_point"] == "USER EDITED entry"
        assert tps[0]["channel_or_tool"] == "Custom Tool"
        assert tps[0]["flow_steps"] == ["Step A", "Step B", "Step C"]
        assert tps[0]["timeline"] == "Day 0-7 USER"
        assert tps[0]["outcome"] == "USER EDITED outcome string"
