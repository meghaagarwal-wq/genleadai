"""iter134 — Scan all hot leads progress endpoint."""
from __future__ import annotations

import os
import sys
import time

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="module")
def client():
    from server import app
    return TestClient(app)


@pytest.fixture(scope="module")
def token(client) -> str:
    r = client.post("/api/auth/login", json={"email": "admin@demo.com", "password": "Demo1234!"})
    assert r.status_code == 200, r.text
    j = r.json()
    return j.get("token") or j.get("access_token")


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_scan_hot_returns_batch_id(client, token):
    r = client.post("/api/intel/scan-hot", headers=_h(token), json={"max_leads": 3})
    assert r.status_code == 200, r.text
    body = r.json()
    if body.get("queued", 0) == 0:
        pytest.skip("no hot leads in tenant — cannot exercise batch id")
    assert "batch_id" in body
    assert isinstance(body["batch_id"], str)
    assert len(body["batch_id"]) >= 16


def test_scan_status_returns_shape(client, token):
    """Issue a scan + immediately poll status — must return the expected
    shape regardless of completion state."""
    r = client.post("/api/intel/scan-hot", headers=_h(token), json={"max_leads": 3})
    batch_id = r.json().get("batch_id")
    if not batch_id:
        pytest.skip("no batch id (empty tenant)")
    # Give the background tasks a beat to flip the counters.
    time.sleep(0.2)
    s = client.get(f"/api/intel/scan-hot/status/{batch_id}", headers=_h(token))
    assert s.status_code == 200, s.text
    body = s.json()
    for k in ("batch_id", "total", "completed", "failed", "in_progress", "progress_pct", "is_finished", "started_at"):
        assert k in body
    assert body["batch_id"] == batch_id
    assert body["total"] >= 1
    # completed + failed + in_progress must equal total
    assert body["completed"] + body["failed"] + body["in_progress"] == body["total"]
    assert 0 <= body["progress_pct"] <= 100


def test_scan_status_404_unknown_batch(client, token):
    r = client.get("/api/intel/scan-hot/status/nonexistent-batch-id-xyz", headers=_h(token))
    assert r.status_code == 404
