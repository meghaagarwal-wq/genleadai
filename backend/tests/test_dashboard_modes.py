"""Backend tests for iter153: dashboard mode + instinct widget data + tenant isolation."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")

PT_EMAIL = "megha@contentvista.com"
PT_PASS = "Pietential2026!"
DEMO_EMAIL = "meghaagarwaljain2015@gmail.com"
DEMO_PASS = "DemoView2026!"


def _login(email, pwd):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pwd}, timeout=20)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def pt_token():
    return _login(PT_EMAIL, PT_PASS)


@pytest.fixture(scope="module")
def demo_token():
    return _login(DEMO_EMAIL, DEMO_PASS)


# /api/dashboard/_mode for Pietential owner
def test_pietential_mode(pt_token):
    r = requests.get(f"{BASE_URL}/api/dashboard/_mode", headers={"Authorization": f"Bearer {pt_token}"}, timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d["tenant_id"] == "ten_pietential"
    assert d["mode"] == "b2b"
    assert d["currency"] == "INR"


# /api/dashboard/_mode for Demo viewer
def test_demo_mode(demo_token):
    r = requests.get(f"{BASE_URL}/api/dashboard/_mode", headers={"Authorization": f"Bearer {demo_token}"}, timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d["tenant_id"] == "ten_demo"
    assert d["mode"] == "hybrid"


# InstinctFeedWidget data source — Pietential sees its own cards
def test_pietential_insights_feed(pt_token):
    r = requests.get(f"{BASE_URL}/api/pt/insights/feed", params={"status": "new"},
                     headers={"Authorization": f"Bearer {pt_token}"}, timeout=20)
    assert r.status_code == 200
    cards = r.json().get("cards", [])
    assert isinstance(cards, list)
    assert len(cards) >= 1, "Pietential should have at least 1 instinct card"
    # All cards should NOT be demo cards
    for c in cards:
        assert not str(c.get("id", "")).startswith("ins_demo_"), f"Pietential leaked demo card: {c.get('id')}"


# Tenant isolation — Demo never sees Pietential ins_* cards
def test_demo_tenant_isolation(demo_token):
    r = requests.get(f"{BASE_URL}/api/pt/insights/feed", params={"status": "new"},
                     headers={"Authorization": f"Bearer {demo_token}"}, timeout=20)
    assert r.status_code == 200
    cards = r.json().get("cards", [])
    # Either empty or only demo-prefixed cards — never Pietential's
    pietential_known_ids = {"ins_ae4c8f2e290347", "ins_8774089f195b4d", "ins_a16ba91da8ff4d"}
    for c in cards:
        cid = c.get("id", "")
        assert cid not in pietential_known_ids, f"Demo leaked Pietential card: {cid}"
        # demo cards are prefixed ins_demo_
        if cid:
            assert cid.startswith("ins_demo_") or not cid.startswith("ins_"), f"Unexpected card id leak: {cid}"
