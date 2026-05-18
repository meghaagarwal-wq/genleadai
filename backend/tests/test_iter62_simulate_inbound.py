"""Iter 62 — Simulate Inbound Lead walkthrough."""
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


# 1. Sources + channels metadata endpoint
def test_sources_metadata(client, admin_headers):
    headers, _ = admin_headers
    r = client.get("/api/integrations/simulate-inbound/sources", headers=headers)
    assert r.status_code == 200
    body = r.json()
    keys = {s["key"] for s in body["sources"]}
    assert {"meta_lead_ad", "google_ads", "typeform", "linkedin_lead", "saleshandy", "lemlist"}.issubset(keys)
    assert any(c["key"] == "email" for c in body["channels"])


# 2. Happy-path simulate — 5 ordered steps, lead NOT persisted
def test_simulate_returns_five_steps_and_does_not_persist(client, admin_headers):
    headers, tenant_id = admin_headers
    before = db["leads"].count_documents({"tenant_id": tenant_id})
    r = client.post("/api/integrations/simulate-inbound", headers=headers, json={
        "source": "meta_lead_ad",
        "first_name": "Priya", "last_name": "Mehta",
        "email": "priya@acme.com",
        "company": "Acme Co",
        "utm_campaign": "demo-q1",
        "form_answers": "Looking to evaluate AI sales tools. Budget approved.",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["lead_persisted"] is False
    assert body["is_simulation"] is True
    step_keys = [s["key"] for s in body["steps"]]
    assert step_keys == ["captured", "enriched", "icp_scored", "channel_chosen", "message_drafted"]
    # No lead was inserted
    after = db["leads"].count_documents({"tenant_id": tenant_id})
    assert after == before


# 3. ICP scorer recognises high-intent profile + business email → HOT
def test_simulate_high_intent_business_email_scores_hot(client, admin_headers):
    headers, _ = admin_headers
    r = client.post("/api/integrations/simulate-inbound", headers=headers, json={
        "source": "saleshandy",  # very_high intent_hint
        "email": "priya@acme.com",
        "company": "Acme Co",
        "utm_campaign": "outbound-q1",
        "form_answers": "Interested in a demo and pricing. Budget approved.",
    })
    body = r.json()
    scored = next(s for s in body["steps"] if s["key"] == "icp_scored")
    assert scored["detail"]["tier"] == "hot"
    assert scored["detail"]["score"] >= 80


# 4. Consumer email + low signal → cold / poor_fit
def test_simulate_consumer_email_low_intent_scores_low(client, admin_headers):
    headers, _ = admin_headers
    r = client.post("/api/integrations/simulate-inbound", headers=headers, json={
        "source": "manual",   # medium intent_hint
        "email": "random.person@gmail.com",
        "company": "",
        "utm_campaign": None,
        "form_answers": "Just browsing.",
    })
    body = r.json()
    scored = next(s for s in body["steps"] if s["key"] == "icp_scored")
    assert scored["detail"]["tier"] in ("cold", "poor_fit")


# 5. Channel chosen uses saved prefs (email-first when USA B2B SaaS preset is set)
def test_simulate_uses_saved_channel_prefs(client, admin_headers):
    headers, _ = admin_headers
    client.put("/api/tenant/sales-channels", headers=headers, json={
        "selected_channels": ["email", "linkedin"],
        "priority_order": ["email", "linkedin"],
        "conversation_style": "consultative",
        "selected_preset": "usa_b2b_saas",
    })
    r = client.post("/api/integrations/simulate-inbound", headers=headers, json={
        "source": "typeform", "email": "priya@acme.com",
        "company": "Acme Co", "form_answers": "We want a demo.",
    })
    body = r.json()
    chan = next(s for s in body["steps"] if s["key"] == "channel_chosen")
    assert chan["detail"]["primary_channel"] == "email"
    assert "usa b2b saas" in chan["detail"]["reason"].lower()


# 6. Message drafted is non-empty + substitutes the first name
def test_simulate_drafts_message_with_first_name(client, admin_headers):
    headers, _ = admin_headers
    r = client.post("/api/integrations/simulate-inbound", headers=headers, json={
        "source": "meta_lead_ad", "first_name": "Priya",
        "email": "priya@acme.com", "company": "Acme",
        "form_answers": "Want to learn more.",
    })
    body = r.json()
    msg = next(s for s in body["steps"] if s["key"] == "message_drafted")
    text = msg["detail"]["rendered_message"]
    assert len(text) > 10
    # No raw template tokens remaining
    assert "{{first_name}}" not in text
