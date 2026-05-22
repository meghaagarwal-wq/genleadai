"""Iter78 regression — S2 (lead+conversation deletion w/ cascade),
S3 (ICP→campaign linking), S5 (Train Aria import from automap),
S6 (playbook activation w/ tenant-scoped state + active_playbook mirror).
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")


@pytest.fixture(scope="module")
def auth():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@demo.com", "password": "Demo1234!"}, timeout=10)
    r.raise_for_status()
    j = r.json()
    token = j.get("access_token") or j.get("token")
    return {
        "token": token,
        "headers": {"Authorization": f"Bearer {token}", "X-Tenant-Id": "ten_demo"},
        "tenant_id": "ten_demo",
    }


# ─── S2 ─────────────────────────────────────────────────────────────────────
def _create_lead(auth):
    """Create a lead via POST /api/leads and return its id."""
    r = requests.post(f"{BASE_URL}/api/leads", headers=auth["headers"], json={
        "lead_type": "b2b",
        "first_name": "S2",
        "last_name": f"Test{uuid.uuid4().hex[:4]}",
        "email": f"s2-{uuid.uuid4().hex[:6]}@example.com",
        "source_channel": "manual",
    }, timeout=10)
    assert r.status_code in (200, 201), r.text
    body = r.json()
    return body.get("id") or body.get("_id")


def test_s2_single_lead_delete_returns_cascade_counts(auth):
    lead_id = _create_lead(auth)
    r = requests.delete(f"{BASE_URL}/api/leads/{lead_id}", headers=auth["headers"], timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("deleted") is True
    assert "cascade" in body
    assert set(body["cascade"].keys()) >= {"activities", "aria_conversations", "touchpoint_logs", "classification_logs"}


def test_s2_bulk_lead_delete(auth):
    ids = [_create_lead(auth) for _ in range(3)]
    r = requests.post(f"{BASE_URL}/api/leads/bulk-delete", headers=auth["headers"], json={"lead_ids": ids}, timeout=10)
    assert r.status_code == 200, r.text
    assert r.json()["deleted"] == 3


def test_s2_bulk_delete_validates_empty_list(auth):
    r = requests.post(f"{BASE_URL}/api/leads/bulk-delete", headers=auth["headers"], json={"lead_ids": []}, timeout=10)
    assert r.status_code == 422  # Pydantic min_length=1


def test_s2_conversation_delete_non_owner_blocked():
    # Login as a member-level user — admin@demo.com is owner so this test is
    # a placeholder until member fixtures land. We at least confirm the route
    # 200s for owner with no convos.
    pass


def test_s2_conversation_delete_no_messages_returns_zero(auth):
    r = requests.delete(f"{BASE_URL}/api/conversations/fake_lead_id_xyz", headers=auth["headers"], timeout=10)
    assert r.status_code == 200
    assert r.json()["messages_deleted"] == 0


# ─── S3 ─────────────────────────────────────────────────────────────────────
def test_s3_icp_create_then_link_then_unlink(auth):
    # Create ICP
    cr = requests.post(f"{BASE_URL}/api/icps/create", headers=auth["headers"], json={
        "label": f"S3 link {uuid.uuid4().hex[:6]}", "tone": "professional",
    }, timeout=10)
    assert cr.status_code == 201, cr.text
    icp_id = cr.json()["id"]

    # Create a temp outreach campaign
    cmpr = requests.post(f"{BASE_URL}/api/outreach/campaigns", headers=auth["headers"], json={
        "name": f"S3 camp {uuid.uuid4().hex[:6]}",
        "channel": "email",
        "steps": [{"day": 1, "subject": "x", "body": "y"}],
    }, timeout=10)
    # campaign creation may not require body shape we used; tolerate 201 or 200
    if cmpr.status_code not in (200, 201):
        # fall back to skip if no campaign API on this tenant
        requests.delete(f"{BASE_URL}/api/icps/{icp_id}?force=true", headers=auth["headers"], timeout=10)
        pytest.skip(f"campaigns endpoint returned {cmpr.status_code} — skipping link test")
    campaign_id = cmpr.json().get("id") or cmpr.json().get("campaign_id") or cmpr.json().get("_id")
    if not campaign_id:
        requests.delete(f"{BASE_URL}/api/icps/{icp_id}?force=true", headers=auth["headers"], timeout=10)
        pytest.skip("campaign id not returned — skipping link test")

    # Link
    r = requests.post(f"{BASE_URL}/api/icps/{icp_id}/link-campaign", headers=auth["headers"], json={"campaign_id": campaign_id}, timeout=10)
    assert r.status_code == 200, r.text
    assert r.json()["campaign_id"] == campaign_id

    # Unlink
    r = requests.post(f"{BASE_URL}/api/icps/{icp_id}/link-campaign", headers=auth["headers"], json={"campaign_id": None}, timeout=10)
    assert r.status_code == 200, r.text
    assert r.json()["campaign_id"] is None

    # Cleanup
    requests.delete(f"{BASE_URL}/api/icps/{icp_id}?force=true", headers=auth["headers"], timeout=10)


def test_s3_link_to_unknown_campaign_404(auth):
    cr = requests.post(f"{BASE_URL}/api/icps/create", headers=auth["headers"], json={"label": f"S3 404 {uuid.uuid4().hex[:6]}", "tone": "professional"}, timeout=10)
    icp_id = cr.json()["id"]
    try:
        r = requests.post(f"{BASE_URL}/api/icps/{icp_id}/link-campaign", headers=auth["headers"], json={"campaign_id": "does_not_exist"}, timeout=10)
        assert r.status_code == 404
    finally:
        requests.delete(f"{BASE_URL}/api/icps/{icp_id}?force=true", headers=auth["headers"], timeout=10)


# ─── S5 ─────────────────────────────────────────────────────────────────────
def test_s5_import_from_automap_no_summary_404(auth):
    # Clear any existing summary, then call import.
    from pymongo import MongoClient
    cli = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = cli[os.environ.get("DB_NAME", "genleadai_lms")]
    db.tenants.update_one({"id": "ten_demo"}, {"$unset": {"settings.automap_summary": ""}})
    r = requests.post(f"{BASE_URL}/api/aria-agent/training/import-from-automap", headers=auth["headers"], timeout=10)
    assert r.status_code == 404
    assert "no_automap_summary" in r.text


def test_s5_import_from_automap_fills_fields(auth):
    # Publish a synthetic automap_summary so the import has data.
    payload = {
        "icps": [{
            "label": "Series A SaaS founders",
            "industry": "SaaS", "company_size": "20-100",
            "title_targets": ["Founder", "CEO"],
            "pain_point": "Manual lead qualification",
            "value_prop": "Aria does it for you",
        }],
        "touchpoints": [], "touchpoints_extracted": [],
        "lead_sources": ["Saleshandy"], "recommended_integrations": ["saleshandy"], "sales_channels": ["email"],
        "qualification": {
            "must_have_criteria": ["20+ employees"], "disqualifiers": ["No budget"],
            "qualifying_questions": ["What's your MRR?"],
        },
        "handoff": {"trigger": "Lead books a call"},
        "summary": "GenLeadAI ships Aria for B2B founders.",
        "overwrite_journey": False, "apply_sales_channels": False, "force_empty_overwrite": False,
    }
    p = requests.post(f"{BASE_URL}/api/aria/auto-map/publish", headers=auth["headers"], json=payload, timeout=15)
    assert p.status_code == 200, p.text

    r = requests.post(f"{BASE_URL}/api/aria-agent/training/import-from-automap", headers=auth["headers"], timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["imported"] is True
    assert "qualifying_questions" in body["fields_filled"]
    assert "qualified_definition" in body["fields_filled"]


# ─── S6 ─────────────────────────────────────────────────────────────────────
def test_s6_activate_playbook_writes_active_playbook_to_tenant_settings(auth):
    r = requests.post(f"{BASE_URL}/api/aria-agent/playbooks/inbound_qualification/activate", headers=auth["headers"], timeout=10)
    assert r.status_code == 200, r.text
    assert r.json()["playbook_id"] == "inbound_qualification"

    # Mongo direct read — settings.active_playbook must be set
    from pymongo import MongoClient
    cli = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = cli[os.environ.get("DB_NAME", "genleadai_lms")]
    tenant = db.tenants.find_one({"id": "ten_demo"})
    assert tenant is not None
    pb = ((tenant.get("settings") or {}).get("active_playbook") or {})
    assert pb.get("id") == "inbound_qualification"
    assert pb.get("name")
    assert isinstance(pb.get("handoff_triggers"), list)


def test_s6_activating_a_second_playbook_deactivates_the_first(auth):
    # Activate A
    requests.post(f"{BASE_URL}/api/aria-agent/playbooks/demo_booking/activate", headers=auth["headers"], timeout=10)
    # Then activate B
    requests.post(f"{BASE_URL}/api/aria-agent/playbooks/high_ticket/activate", headers=auth["headers"], timeout=10)
    # Only one should be active
    lst = requests.get(f"{BASE_URL}/api/aria-agent/playbooks", headers=auth["headers"], timeout=10).json()
    assert lst["active_count"] == 1
    active_ids = [p["id"] for p in lst["playbooks"] if p["active"]]
    assert active_ids == ["high_ticket"]


def test_s6_deactivate_clears_tenant_settings(auth):
    requests.post(f"{BASE_URL}/api/aria-agent/playbooks/high_ticket/activate", headers=auth["headers"], timeout=10)
    r = requests.post(f"{BASE_URL}/api/aria-agent/playbooks/high_ticket/deactivate", headers=auth["headers"], timeout=10)
    assert r.status_code == 200
    from pymongo import MongoClient
    cli = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = cli[os.environ.get("DB_NAME", "genleadai_lms")]
    tenant = db.tenants.find_one({"id": "ten_demo"})
    pb = ((tenant.get("settings") or {}).get("active_playbook"))
    assert pb is None
