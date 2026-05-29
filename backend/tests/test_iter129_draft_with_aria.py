"""iter129 — Draft with ARIA button.

Verifies POST /api/conversations/lead/{lead_id}/draft:
  - Rejects unsupported channels.
  - 404s an unknown lead.
  - Returns a usable draft for each supported channel.
  - Refusal guard kicks in when no intel profile exists.
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


def test_draft_bad_channel(client):
    token = _login(client)
    lead_id = _first_lead_id(client, token)
    r = client.post(f"/api/conversations/lead/{lead_id}/draft", headers=_h(token), json={"channel": "sms"})
    assert r.status_code == 400


def test_draft_unknown_lead(client):
    token = _login(client)
    r = client.post("/api/conversations/lead/000000000000000000000000/draft", headers=_h(token), json={"channel": "email"})
    assert r.status_code == 404


def test_draft_returns_text_for_each_channel(client):
    token = _login(client)
    lead_id = _first_lead_id(client, token)
    for ch in ("email", "whatsapp", "linkedin"):
        r = client.post(f"/api/conversations/lead/{lead_id}/draft", headers=_h(token), json={"channel": ch})
        assert r.status_code == 200, f"{ch}: {r.text}"
        body = r.json()
        assert body["channel"] == ch
        # Refusal guard should always leave a non-empty starter draft.
        assert isinstance(body["draft"], str) and len(body["draft"]) > 10, f"{ch}: {body}"
        if ch == "email":
            # Email channels surface a subject too.
            assert body.get("subject")
        else:
            assert body.get("subject") is None
        # Refusal guard substrings must NOT appear in final output.
        low = body["draft"].lower()
        for forbidden in ("i cannot", "i can't", "should not be contacted"):
            assert forbidden not in low, f"refusal leaked for {ch}: {body['draft']}"


def test_draft_honours_user_steer(client):
    """user_steer must reach the composer prompt (already covered by
    intel_service unit tests). Smoke test here just ensures the field is
    accepted + the endpoint still returns 200."""
    token = _login(client)
    lead_id = _first_lead_id(client, token)
    r = client.post(
        f"/api/conversations/lead/{lead_id}/draft",
        headers=_h(token),
        json={"channel": "email", "user_steer": "highlight our 30-day pilot"},
    )
    assert r.status_code == 200
