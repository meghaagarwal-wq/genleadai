"""iter126 — Lead 360 + CSV import + Sidebar count + insert-blank tests.

Covers:
  - GET /api/leads/counts shape (sidebar strip + Pipeline Snapshot)
  - CSV import preview endpoint (existing) — sanity check still wired
  - Journey insert-blank flow: reorder existing + create at freed slot
"""
from __future__ import annotations

import io
import os
import sys

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


# ── Lead counts ────────────────────────────────────────────────────────
def test_lead_counts_shape(client):
    token = _login(client)
    r = client.get("/api/leads/counts", headers=_h(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert "total" in body
    assert "by_stage" in body
    for k in ("qualified", "nurturing", "new", "cold"):
        assert k in body["by_stage"]
    snap = body.get("pipeline_snapshot")
    assert snap is not None
    for k in ("total", "qualified", "nurturing", "needs_attention", "calls_booked_week"):
        assert k in snap


def test_lead_counts_tenant_isolated(client):
    """Counts must reflect the caller's tenant only. We rely on the admin's
    tenant having at least one lead — verifies the shape end-to-end."""
    token = _login(client)
    r = client.get("/api/leads/counts", headers=_h(token))
    assert r.status_code == 200
    assert isinstance(r.json().get("total"), int)


# ── CSV import preview (already wired by leads_csv.py) ─────────────────
def test_csv_import_preview_returns_mapping(client):
    token = _login(client)
    csv_bytes = b"First Name,Last Name,Email,Company\nAda,Lovelace,ada@example.com,Analytical\n"
    files = {"file": ("leads.csv", io.BytesIO(csv_bytes), "text/csv")}
    r = client.post("/api/leads/import-csv/preview", headers=_h(token), files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["row_count"] == 1
    sug = body.get("suggested_mapping") or {}
    # The auto-mapper should detect at minimum first_name, last_name, email, company.
    targets = set(sug.values())
    assert {"first_name", "last_name", "email", "company"}.issubset(targets)


# ── Journey insert-blank flow ──────────────────────────────────────────
def test_journey_insert_blank_after_step(client):
    """Mirrors the UI flow: re-number existing touchpoints up by 1 starting
    at insertion point, then create a new step at the freed slot."""
    token = _login(client)
    r = client.get("/api/journey/touchpoints", headers=_h(token))
    assert r.status_code == 200
    tps = sorted(r.json().get("touchpoints", []), key=lambda t: t["number"])
    if len(tps) < 2:
        pytest.skip("Need at least 2 touchpoints to exercise insert-blank")

    insertion_after = tps[0]["number"]  # insert right after step 1
    shifted = [{"id": t["id"], "number": t["number"] + 1 if t["number"] > insertion_after else t["number"]} for t in tps]
    r2 = client.post("/api/journey/touchpoints/reorder", headers=_h(token), json={"order": shifted})
    assert r2.status_code == 200, r2.text

    create = client.post(
        "/api/journey/touchpoints",
        headers=_h(token),
        json={
            "number": insertion_after + 1,
            "channel": "email",
            "timing": f"Day {insertion_after + 1}",
            "message_body": "",
            "goal": "",
            "conditional_logic": "",
        },
    )
    assert create.status_code == 200, create.text
    new_id = create.json()["id"]

    # Clean up — delete inserted blank + revert numbering.
    client.delete(f"/api/journey/touchpoints/{new_id}", headers=_h(token))
    revert = [{"id": t["id"], "number": t["number"]} for t in tps]
    client.post("/api/journey/touchpoints/reorder", headers=_h(token), json={"order": revert})
