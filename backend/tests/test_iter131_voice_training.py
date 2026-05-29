"""iter131 — Voice Training (founder voice signature) tests."""
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


@pytest.fixture(scope="module")
def token(client) -> str:
    r = client.post("/api/auth/login", json={"email": "admin@demo.com", "password": "Demo1234!"})
    assert r.status_code == 200, r.text
    j = r.json()
    return j.get("token") or j.get("access_token")


def _login(client) -> str:
    """Kept for backwards-compat with helper signatures; callers should
    prefer the module-scoped `token` fixture."""
    r = client.post("/api/auth/login", json={"email": "admin@demo.com", "password": "Demo1234!"})
    assert r.status_code == 200, r.text
    j = r.json()
    return j.get("token") or j.get("access_token")


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _clear_all_seeds(client, token):
    r = client.get("/api/voice-seeds", headers=_h(token))
    for s in (r.json().get("seeds") or []):
        client.delete(f"/api/voice-seeds/{s['id']}", headers=_h(token))


@pytest.fixture(autouse=True)
def _isolate(client, token):
    """Each test starts with an empty seed set so order can't pollute."""
    _clear_all_seeds(client, token)
    yield
    _clear_all_seeds(client, token)


def test_create_list_delete_roundtrip(client, token):
    created = client.post("/api/voice-seeds", headers=_h(token), json={
        "channel": "whatsapp",
        "text": "yo. quick thought — worth 15 min?",
        "label": "WA mini",
    })
    assert created.status_code == 200, created.text
    seed_id = created.json()["id"]

    listed = client.get("/api/voice-seeds", headers=_h(token))
    assert listed.status_code == 200
    body = listed.json()
    assert body["max_seeds"] == 10
    assert any(s["id"] == seed_id for s in body["seeds"])

    deleted = client.delete(f"/api/voice-seeds/{seed_id}", headers=_h(token))
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True


def test_rejects_short_text(client, token):
    r = client.post("/api/voice-seeds", headers=_h(token), json={"text": "too short", "channel": "any"})
    assert r.status_code == 422


def test_rejects_bad_channel(client, token):
    r = client.post("/api/voice-seeds", headers=_h(token), json={"channel": "sms", "text": "valid length text here"})
    assert r.status_code == 400


def test_patch_toggles_active(client, token):
    created = client.post("/api/voice-seeds", headers=_h(token), json={"channel": "any", "text": "valid length text body for patch test"})
    seed_id = created.json()["id"]
    r = client.patch(f"/api/voice-seeds/{seed_id}", headers=_h(token), json={"active": False})
    assert r.status_code == 200
    assert r.json()["active"] is False


def test_preview_returns_tone_block(client, token):
    client.post("/api/voice-seeds", headers=_h(token), json={
        "channel": "whatsapp",
        "text": "yo — saw your post on ops pace, worth 15? — m",
        "label": "wa style",
    })
    r = client.get("/api/voice-seeds/preview?channel=whatsapp", headers=_h(token))
    assert r.status_code == 200
    body = r.json()
    assert body["seed_count"] == 1
    assert "TONE EXAMPLES" in body["tone_block"]
    assert "yo —" in body["tone_block"]


def test_channel_filtering(client, token):
    """A whatsapp-channel seed must NOT appear in the email preview, but
    an any-channel seed must appear everywhere."""
    client.post("/api/voice-seeds", headers=_h(token), json={"channel": "whatsapp", "text": "wa-only sample text"})
    client.post("/api/voice-seeds", headers=_h(token), json={"channel": "any", "text": "any-channel sample text"})

    wa = client.get("/api/voice-seeds/preview?channel=whatsapp", headers=_h(token)).json()
    em = client.get("/api/voice-seeds/preview?channel=email", headers=_h(token)).json()

    assert wa["seed_count"] == 2  # wa-only + any
    assert em["seed_count"] == 1  # any only


def test_cap_enforced(client, token):
    for i in range(10):
        r = client.post("/api/voice-seeds", headers=_h(token), json={"channel": "any", "text": f"sample text number {i} that is long enough"})
        assert r.status_code == 200, f"#{i} failed: {r.text}"
    overflow = client.post("/api/voice-seeds", headers=_h(token), json={"channel": "any", "text": "11th sample should be rejected"})
    assert overflow.status_code == 400
    assert "Max" in overflow.json()["detail"]
