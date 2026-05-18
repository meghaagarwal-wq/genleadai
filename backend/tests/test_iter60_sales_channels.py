"""Iter 60 — Sales Channel Preferences + Hot Integrations Leaderboard."""
from __future__ import annotations

import sys
import pytest

sys.path.insert(0, "/app/backend")

from fastapi.testclient import TestClient
from deps import db  # noqa: E402
from server import app  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_headers(client):
    r = client.post("/api/auth/login", json={"email": "admin@demo.com", "password": "Demo1234!"})
    body = r.json()
    token = body.get("token") or body.get("access_token")
    user = body.get("user", {})
    tenant_id = (user.get("tenants") or [{}])[0].get("id") or "ten_demo"
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": tenant_id}, tenant_id


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    db["integration_waitlist"].delete_many({"user_email": "admin@demo.com"})


# 1. Catalog endpoint returns channels + styles + presets
def test_sales_channels_catalog_returns_full_set(client, admin_headers):
    headers, _ = admin_headers
    r = client.get("/api/sales-channels/catalog", headers=headers)
    assert r.status_code == 200
    body = r.json()
    channel_keys = {c["key"] for c in body["channels"]}
    assert {"whatsapp", "email", "linkedin", "sms", "phone", "website_chat"}.issubset(channel_keys)
    assert len(body["styles"]) >= 5
    preset_keys = {p["key"] for p in body["presets"]}
    assert {"india_founder_led", "usa_b2b_saas", "uae_high_ticket", "d2c_ecom"}.issubset(preset_keys)


# 2. PUT persists + computes primary/fallback/disabled
def test_put_sales_channels_persists_and_derives(client, admin_headers):
    headers, _ = admin_headers
    payload = {
        "selected_channels": ["email", "linkedin", "whatsapp"],
        "priority_order": ["email", "linkedin", "whatsapp"],
        "conversation_style": "consultative",
        "selected_preset": "usa_b2b_saas",
    }
    r = client.put("/api/tenant/sales-channels", headers=headers, json=payload)
    assert r.status_code == 200, r.text
    prefs = r.json()["preferences"]
    assert prefs["primary_channel"] == "email"
    assert prefs["fallback_channels"] == ["linkedin", "whatsapp"]
    assert "sms" in prefs["disabled_channels"]
    # Round-trip
    r2 = client.get("/api/tenant/sales-channels", headers=headers)
    body2 = r2.json()
    assert body2["primary_channel"] == "email"
    assert body2["conversation_style"] == "consultative"


# 3. Priority_order is sanitized to only include selected channels in given order
def test_put_sanitizes_priority_order(client, admin_headers):
    headers, _ = admin_headers
    r = client.put("/api/tenant/sales-channels", headers=headers, json={
        "selected_channels": ["email", "whatsapp"],
        "priority_order": ["sms", "whatsapp", "linkedin", "email"],  # sms+linkedin not selected
    })
    prefs = r.json()["preferences"]
    assert prefs["priority_order"] == ["whatsapp", "email"]


# 4. Invalid channel keys are stripped
def test_put_strips_invalid_channels(client, admin_headers):
    headers, _ = admin_headers
    r = client.put("/api/tenant/sales-channels", headers=headers, json={
        "selected_channels": ["email", "totally_fake_channel"],
        "priority_order": ["email", "totally_fake_channel"],
    })
    prefs = r.json()["preferences"]
    assert "totally_fake_channel" not in prefs["selected_channels"]
    assert prefs["primary_channel"] == "email"


# 5. Recommendations endpoint returns integration suggestions + workflow rule
def test_recommendations_after_save(client, admin_headers):
    headers, _ = admin_headers
    client.put("/api/tenant/sales-channels", headers=headers, json={
        "selected_channels": ["email", "linkedin"],
        "priority_order": ["email", "linkedin"],
        "conversation_style": "consultative",
    })
    r = client.get("/api/tenant/sales-channels/recommendations", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["primary_channel"] == "email"
    types = {x["type"] for x in body["recommendations"]}
    assert {"saleshandy", "instantly", "lemlist"}.issubset(types)
    rule = body["workflow_rule"]
    assert rule["primary_action"] == "Send email intro"
    assert any("LinkedIn" in s for s in rule["fallback_chain"])


# 6. If user did NOT select WhatsApp, it is NOT recommended
def test_recommendations_excludes_unselected_channel(client, admin_headers):
    headers, _ = admin_headers
    client.put("/api/tenant/sales-channels", headers=headers, json={
        "selected_channels": ["email"],
        "priority_order": ["email"],
    })
    r = client.get("/api/tenant/sales-channels/recommendations", headers=headers)
    types = {x["type"] for x in r.json()["recommendations"]}
    assert "whatsapp_biz" not in types


# 7. Hot integrations leaderboard — admin only + aggregates correctly
def test_hot_integrations_aggregates_waitlist(client, admin_headers):
    headers, _ = admin_headers
    # Seed 3 waitlist rows
    client.post("/api/integrations/waitlist/hubspot", headers=headers, json={"note": "Need it"})
    client.post("/api/integrations/waitlist/calendly", headers=headers, json={"note": "For demo booking"})

    r = client.get("/api/admin/hot-integrations", headers=headers)
    assert r.status_code == 200
    body = r.json()
    types = {row["integration_type"] for row in body["hot"]}
    assert "hubspot" in types or "calendly" in types
    assert body["total_requests"] >= 2


# 8. Hot integrations forbidden for non-admin
def test_hot_integrations_forbidden_for_non_admin(client):
    r = client.post("/api/auth/login", json={"email": "sarah@demo.com", "password": "Demo1234!"})
    body = r.json()
    token = body.get("token") or body.get("access_token")
    user = body.get("user", {})
    tenant_id = (user.get("tenants") or [{}])[0].get("id") or "ten_demo"
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-Id": tenant_id}
    r2 = client.get("/api/admin/hot-integrations", headers=headers)
    assert r2.status_code == 403
