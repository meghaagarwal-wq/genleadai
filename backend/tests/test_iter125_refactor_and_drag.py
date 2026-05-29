"""iter125 — Verify server.py refactor and Journey drag-reorder.

Covers:
  - Moved endpoints still mounted (api_keys, audit-log, exports, ttv,
    founder-command-center, onboarding-legacy).
  - Journey reorder endpoint accepts the renumbered payload from the
    new drag-and-drop UI and persists `number` for every touchpoint.
"""
from __future__ import annotations

import os
import sys
import uuid

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="module")
def client():
    from server import app
    return TestClient(app)


def _login(client) -> str:
    r = client.post("/api/auth/login", json={"email": "admin@demo.com", "password": "Demo1234!"})
    assert r.status_code == 200, r.text
    j = r.json()
    return j.get("token") or j.get("access_token")


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_command_center_moved_route_still_mounted(client):
    token = _login(client)
    r = client.get("/api/insights/founder-command-center", headers=_h(token))
    assert r.status_code == 200
    body = r.json()
    # Real-data path returns the new key; the empty-workspace branch returns it too.
    assert "computed_from_real_data" in body
    assert "money_at_risk" in body


def test_ttv_milestones_moved_route(client):
    token = _login(client)
    r = client.get("/api/ttv/milestones", headers=_h(token))
    assert r.status_code == 200
    j = r.json()
    assert isinstance(j.get("milestones"), list)
    assert len(j["milestones"]) == 5


def test_api_keys_moved_routes_round_trip(client):
    token = _login(client)
    name = f"refactor-test-{uuid.uuid4().hex[:6]}"
    created = client.post("/api/settings/api-keys", headers=_h(token), json={"name": name})
    assert created.status_code == 200, created.text
    key = created.json().get("key")
    assert key and key.startswith("glai_")

    listed = client.get("/api/settings/api-keys", headers=_h(token))
    assert listed.status_code == 200
    keys = listed.json().get("keys", [])
    assert any(k.get("name") == name for k in keys)

    # Revoke it again to keep DB tidy.
    prefix = key[:8]
    revoked = client.delete(f"/api/settings/api-keys/{prefix}", headers=_h(token))
    assert revoked.status_code == 200


def test_audit_log_moved_route_admin_only(client):
    token = _login(client)
    r = client.get("/api/audit-log", headers=_h(token))
    assert r.status_code == 200
    assert "entries" in r.json()


def test_export_leads_csv_moved_route(client):
    token = _login(client)
    r = client.get("/api/export/leads", headers=_h(token))
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("text/csv")


def test_form_submit_public_route(client):
    # No auth required — anyone can submit, but invalid email is rejected.
    r = client.post("/api/form/submit", json={"first_name": "Refactor", "email": "not-an-email"})
    assert r.status_code == 400


def test_journey_drag_reorder_full_payload(client):
    """Drag-and-drop UI sends the full renumbered list — confirm the
    endpoint accepts it and renumber persists for every touchpoint."""
    token = _login(client)
    listing = client.get("/api/journey/touchpoints", headers=_h(token))
    assert listing.status_code == 200
    tps = listing.json().get("touchpoints", [])
    if len(tps) < 2:
        pytest.skip("Need at least 2 touchpoints to test reorder")

    tps_sorted = sorted(tps, key=lambda t: t["number"])
    # Reverse order — full payload, mirrors the drag-handler in JourneyFlowchart.jsx.
    reversed_order = [{"id": t["id"], "number": i + 1} for i, t in enumerate(reversed(tps_sorted))]
    r = client.post("/api/journey/touchpoints/reorder", headers=_h(token), json={"order": reversed_order})
    assert r.status_code == 200, r.text
    new_tps = r.json().get("touchpoints", [])
    new_ids_by_number = {t["number"]: t["id"] for t in new_tps}
    # First touchpoint should now be the formerly-last one.
    assert new_ids_by_number[1] == tps_sorted[-1]["id"]
    assert new_ids_by_number[len(tps_sorted)] == tps_sorted[0]["id"]

    # Restore original order so the workspace stays clean.
    restore = [{"id": t["id"], "number": t["number"]} for t in tps_sorted]
    rr = client.post("/api/journey/touchpoints/reorder", headers=_h(token), json={"order": restore})
    assert rr.status_code == 200
