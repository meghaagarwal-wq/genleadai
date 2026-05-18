"""Iter 59 — Integration Hub catalog, setup progress, health, waitlist, custom-request, test-lead."""
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
    db["integration_requests"].delete_many({"tool_name": {"$regex": "^iter59-"}})


# 1. Catalog returns all 7 categories + live + coming-soon entries
def test_catalog_returns_categories_and_integrations(client, admin_headers):
    headers, _ = admin_headers
    r = client.get("/api/integrations/catalog", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    cat_keys = {c["key"] for c in body["categories"]}
    assert {"lead_source", "outreach", "crm", "communication", "booking", "analytics", "automation"}.issubset(cat_keys)
    # Live entries present
    types = {i["type"] for i in body["integrations"]}
    assert {"ga4", "meta_capi", "zapier", "make", "typeform", "apollo"}.issubset(types)
    # Coming-soon present too
    assert {"whatsapp_biz", "calendly", "zoho_crm", "hubspot", "google_sheets"}.issubset(types)
    # by_category groups correctly
    assert len(body["by_category"]["crm"]) >= 6


# 2. Setup progress returns 7 steps + a percent
def test_setup_progress_returns_seven_steps(client, admin_headers):
    headers, _ = admin_headers
    r = client.get("/api/integrations/setup-progress", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 7
    assert 0 <= body["percent"] <= 100
    assert len(body["steps"]) == 7
    for s in body["steps"]:
        assert s["key"] and s["label"] and "complete" in s


# 3. Data flow preview returns 7 nodes
def test_data_flow_preview(client, admin_headers):
    headers, _ = admin_headers
    r = client.get("/api/integrations/data-flow", headers=headers)
    assert r.status_code == 200
    body = r.json()
    keys = {n["key"] for n in body["nodes"]}
    assert {"capture", "signal", "score", "followup", "crm", "booking", "alert"}.issubset(keys)


# 4. Integration health rollup
def test_integration_health_endpoint(client, admin_headers):
    headers, _ = admin_headers
    r = client.get("/api/integrations/health", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert 0 <= body["healthy_percent"] <= 100
    assert isinstance(body["rows"], list)


# 5. Join waitlist — idempotent, only valid coming-soon types
def test_waitlist_join_valid_type(client, admin_headers):
    headers, _ = admin_headers
    r = client.post("/api/integrations/waitlist/calendly",
                    headers=headers, json={"note": "Need this for demo booking"})
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    # Idempotent — call again
    r2 = client.post("/api/integrations/waitlist/calendly",
                     headers=headers, json={"note": "Still need it"})
    assert r2.status_code == 200
    # Bogus type → 404
    bad = client.post("/api/integrations/waitlist/totally_fake_tool",
                      headers=headers, json={})
    assert bad.status_code == 404


# 6. Catalog reflects waitlist status after joining
def test_catalog_marks_waitlist_joined(client, admin_headers):
    headers, _ = admin_headers
    client.post("/api/integrations/waitlist/hubspot", headers=headers, json={})
    body = client.get("/api/integrations/catalog", headers=headers).json()
    row = next(i for i in body["integrations"] if i["type"] == "hubspot")
    assert row["status"] == "waitlist_joined"


# 7. Custom request — validation + persistence
def test_custom_request_validates_and_persists(client, admin_headers):
    headers, _ = admin_headers
    # Reject short use_case
    bad = client.post("/api/integrations/custom-request", headers=headers,
                      json={"tool_name": "iter59-foo", "use_case": "short"})
    assert bad.status_code == 422
    # Happy path
    good = client.post("/api/integrations/custom-request", headers=headers,
                       json={
                           "tool_name": "iter59-close-com",
                           "website_url": "https://close.com",
                           "use_case": "Pipeline sync with deal stage changes",
                           "data_to_pull": "deal stages",
                           "data_to_push": "qualified leads",
                           "priority": "blocker",
                       })
    assert good.status_code == 200
    rid = good.json()["id"]
    # List endpoint returns it
    lst = client.get("/api/integrations/custom-requests", headers=headers).json()["requests"]
    assert any(r["id"] == rid for r in lst)


# 8. Send test lead — non-zero response shape, does not insert into leads
def test_send_test_lead_returns_shape(client, admin_headers):
    headers, tenant_id = admin_headers
    leads_before = db["leads"].count_documents({"tenant_id": tenant_id})
    r = client.post("/api/integrations/test-lead", headers=headers, json={})
    assert r.status_code == 200
    body = r.json()
    assert "fired" in body and "results" in body and "test_lead_id" in body
    # Importantly — no lead row was inserted
    leads_after = db["leads"].count_documents({"tenant_id": tenant_id})
    assert leads_after == leads_before
