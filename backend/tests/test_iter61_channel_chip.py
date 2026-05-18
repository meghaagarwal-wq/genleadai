"""Iter 61 — ChannelHintChip wiring sanity check.

Confirms the recommendations endpoint that drives the Lead Inbox chip is
returning the right shape for the frontend.
"""
from __future__ import annotations

import sys
import pytest

sys.path.insert(0, "/app/backend")

from fastapi.testclient import TestClient
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


def test_chip_data_contract_email_first(client, admin_headers):
    """The Lead Inbox chip needs primary_channel + workflow_rule.primary_action + priority_order."""
    headers, _ = admin_headers
    client.put("/api/tenant/sales-channels", headers=headers, json={
        "selected_channels": ["email", "linkedin"],
        "priority_order": ["email", "linkedin"],
        "conversation_style": "consultative",
        "selected_preset": "usa_b2b_saas",
    })
    r = client.get("/api/tenant/sales-channels/recommendations", headers=headers)
    body = r.json()
    # Chip reads these three keys
    assert body["primary_channel"] == "email"
    assert body["priority_order"] == ["email", "linkedin"]
    assert body["workflow_rule"]["primary_action"] == "Send email intro"


def test_chip_handles_whatsapp_first_preset(client, admin_headers):
    """India Founder-Led preset → chip should say 'WhatsApp first'."""
    headers, _ = admin_headers
    client.put("/api/tenant/sales-channels", headers=headers, json={
        "selected_channels": ["whatsapp", "phone", "email"],
        "priority_order": ["whatsapp", "phone", "email"],
        "conversation_style": "founder_led",
        "selected_preset": "india_founder_led",
    })
    body = client.get("/api/tenant/sales-channels/recommendations", headers=headers).json()
    assert body["primary_channel"] == "whatsapp"
    assert body["workflow_rule"]["primary_action"] == "Send WhatsApp intro message"


def test_chip_empty_state_when_no_prefs(client):
    """A fresh user with no prefs gets `primary_channel: None` → frontend shows 'Set channel' CTA."""
    # Login as a non-admin sales rep who hasn't configured channels
    r = client.post("/api/auth/login", json={"email": "sarah@demo.com", "password": "Demo1234!"})
    body = r.json()
    token = body.get("token") or body.get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    # GET recommendations — should not 500 even if no prefs exist for the tenant
    r2 = client.get("/api/tenant/sales-channels/recommendations", headers=headers)
    assert r2.status_code == 200
