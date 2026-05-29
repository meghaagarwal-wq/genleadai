"""iter130 — Draft variants.

Verifies POST /api/conversations/lead/{lead_id}/draft accepts `attempt`
and returns visibly different drafts per attempt.
"""
from __future__ import annotations

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


def _first_lead_id(client, token: str) -> str:
    r = client.get("/api/leads?per_page=1", headers=_h(token))
    leads = r.json().get("leads") or []
    if not leads:
        pytest.skip("no leads in test DB")
    return leads[0]["id"]


def test_attempt_field_echoed(client):
    token = _login(client)
    lead_id = _first_lead_id(client, token)
    r = client.post(f"/api/conversations/lead/{lead_id}/draft", headers=_h(token), json={"channel": "whatsapp", "attempt": 2})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["attempt"] == 2
    assert body["max_attempts"] == 3


def test_attempt_out_of_range(client):
    token = _login(client)
    lead_id = _first_lead_id(client, token)
    r = client.post(f"/api/conversations/lead/{lead_id}/draft", headers=_h(token), json={"channel": "whatsapp", "attempt": 4})
    assert r.status_code == 422
    r2 = client.post(f"/api/conversations/lead/{lead_id}/draft", headers=_h(token), json={"channel": "whatsapp", "attempt": 0})
    assert r2.status_code == 422


def test_variants_are_distinct_when_no_intel(client):
    """The refusal-guard fallback varies the starter per attempt so
    "Try another" delivers a visibly different draft."""
    token = _login(client)
    lead_id = _first_lead_id(client, token)
    drafts = []
    for n in (1, 2, 3):
        r = client.post(f"/api/conversations/lead/{lead_id}/draft", headers=_h(token), json={"channel": "whatsapp", "attempt": n})
        assert r.status_code == 200, r.text
        drafts.append(r.json()["draft"])

    # All three must be distinct strings.
    assert len(set(drafts)) == 3, f"variants collapsed:\n{drafts}"
    # And none of them should contain a refusal marker (proves guard ran).
    for d in drafts:
        low = d.lower()
        for forbidden in ("i cannot", "i can't", "don't have enough", "skip this prospect"):
            assert forbidden not in low, f"refusal leaked into variant: {d}"


def test_default_attempt_is_one(client):
    token = _login(client)
    lead_id = _first_lead_id(client, token)
    r = client.post(f"/api/conversations/lead/{lead_id}/draft", headers=_h(token), json={"channel": "email"})
    assert r.status_code == 200
    assert r.json()["attempt"] == 1
