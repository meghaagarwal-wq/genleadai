"""Iter78 supplemental tests — audit log, cross-tenant safety, playbook block,
and conversation delete behavior. Not in original suite but explicitly requested.
"""
import os
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "genleadai_lms")


@pytest.fixture(scope="module")
def auth():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@demo.com", "password": "Demo1234!"}, timeout=10)
    r.raise_for_status()
    j = r.json()
    token = j.get("access_token") or j.get("token")
    return {"headers": {"Authorization": f"Bearer {token}", "X-Tenant-Id": "ten_demo"}, "tenant_id": "ten_demo"}


@pytest.fixture(scope="module")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


def _create_lead(auth):
    r = requests.post(f"{BASE_URL}/api/leads", headers=auth["headers"], json={
        "lead_type": "b2b", "first_name": "Supp", "last_name": f"T{uuid.uuid4().hex[:4]}",
        "email": f"sup-{uuid.uuid4().hex[:6]}@example.com", "source_channel": "manual",
    }, timeout=10)
    assert r.status_code in (200, 201), r.text
    return r.json().get("id") or r.json().get("_id")


# ── S9.5 — Audit log writes ────────────────────────────────────────────────
def test_audit_log_lead_delete(auth, db):
    lead_id = _create_lead(auth)
    r = requests.delete(f"{BASE_URL}/api/leads/{lead_id}", headers=auth["headers"], timeout=10)
    assert r.status_code == 200
    entry = db.audit_log.find_one({"action": "lead.delete", "tenant_id": "ten_demo"}, sort=[("_id", -1)])
    assert entry is not None, "no audit_log entry for lead.delete"
    assert entry.get("actor_email") == "admin@demo.com"


def test_audit_log_lead_bulk_delete(auth, db):
    ids = [_create_lead(auth) for _ in range(2)]
    r = requests.post(f"{BASE_URL}/api/leads/bulk-delete", headers=auth["headers"], json={"lead_ids": ids}, timeout=10)
    assert r.status_code == 200
    entry = db.audit_log.find_one({"action": "lead.bulk_delete", "tenant_id": "ten_demo"}, sort=[("_id", -1)])
    assert entry is not None
    assert entry.get("actor_email") == "admin@demo.com"


def test_audit_log_conversation_delete(auth, db):
    r = requests.delete(f"{BASE_URL}/api/conversations/no_msgs_lead_xyz", headers=auth["headers"], timeout=10)
    assert r.status_code == 200
    entry = db.audit_log.find_one({"action": "conversation.delete", "tenant_id": "ten_demo"}, sort=[("_id", -1)])
    assert entry is not None


def test_audit_log_playbook_activate_and_deactivate(auth, db):
    r = requests.post(f"{BASE_URL}/api/aria-agent/playbooks/saas_trial/activate", headers=auth["headers"], timeout=10)
    assert r.status_code == 200
    a = db.audit_log.find_one({"action": "playbook.activate", "tenant_id": "ten_demo"}, sort=[("_id", -1)])
    assert a is not None
    assert a.get("actor_email") == "admin@demo.com"

    r = requests.post(f"{BASE_URL}/api/aria-agent/playbooks/saas_trial/deactivate", headers=auth["headers"], timeout=10)
    assert r.status_code == 200
    d = db.audit_log.find_one({"action": "playbook.deactivate", "tenant_id": "ten_demo"}, sort=[("_id", -1)])
    assert d is not None


# ── S2 conversation delete preserves the lead ──────────────────────────────
def test_conversation_delete_does_not_delete_lead(auth, db):
    lead_id = _create_lead(auth)
    # seed a fake aria conversation message
    db.aria_conversations.insert_one({"lead_id": lead_id, "tenant_id": "ten_demo", "role": "user", "content": "hi"})
    r = requests.delete(f"{BASE_URL}/api/conversations/{lead_id}", headers=auth["headers"], timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body.get("messages_deleted", 0) >= 1
    # lead must still exist
    lead = db.leads.find_one({"id": lead_id, "tenant_id": "ten_demo"})
    assert lead is not None, "conversation delete must NOT remove the lead"
    # cleanup
    requests.delete(f"{BASE_URL}/api/leads/{lead_id}", headers=auth["headers"], timeout=10)


# ── Cross-tenant safety ────────────────────────────────────────────────────
def test_cross_tenant_lead_delete_returns_404(auth, db):
    # create a lead with valid ObjectId under a different tenant
    from bson import ObjectId
    foreign_oid = ObjectId()
    db.leads.insert_one({
        "_id": foreign_oid, "tenant_id": "ten_other_xxx",
        "first_name": "Z", "last_name": "Z", "email": "z@z.com",
        "source_channel": "manual", "lead_type": "b2b",
    })
    r = requests.delete(f"{BASE_URL}/api/leads/{str(foreign_oid)}", headers=auth["headers"], timeout=10)
    assert r.status_code == 404, f"expected 404, got {r.status_code}: {r.text}"
    db.leads.delete_one({"_id": foreign_oid})


def test_cross_tenant_icp_link_returns_404(auth, db):
    foreign_icp = f"foreign_icp_{uuid.uuid4().hex[:6]}"
    db.icps.insert_one({"id": foreign_icp, "tenant_id": "ten_other_xxx", "label": "X", "tone": "professional"})
    r = requests.post(f"{BASE_URL}/api/icps/{foreign_icp}/link-campaign",
                      headers=auth["headers"], json={"campaign_id": None}, timeout=10)
    assert r.status_code == 404
    db.icps.delete_one({"id": foreign_icp})


# ── S6 playbook block injected into prompt ─────────────────────────────────
def test_get_active_playbook_block_non_empty_after_activate(auth):
    requests.post(f"{BASE_URL}/api/aria-agent/playbooks/inbound_qualification/activate",
                  headers=auth["headers"], timeout=10)
    # import the shared helper and call it directly
    import sys
    sys.path.insert(0, "/app/backend")
    from aria_agent_routes._shared import get_active_playbook_block
    block = get_active_playbook_block("ten_demo")
    assert isinstance(block, str)
    assert len(block) > 0, "active playbook block must be non-empty after activation"
    assert "inbound" in block.lower() or "playbook" in block.lower()


def test_get_active_playbook_block_empty_after_deactivate(auth):
    requests.post(f"{BASE_URL}/api/aria-agent/playbooks/inbound_qualification/activate",
                  headers=auth["headers"], timeout=10)
    requests.post(f"{BASE_URL}/api/aria-agent/playbooks/inbound_qualification/deactivate",
                  headers=auth["headers"], timeout=10)
    import sys
    sys.path.insert(0, "/app/backend")
    from aria_agent_routes._shared import get_active_playbook_block
    block = get_active_playbook_block("ten_demo")
    assert block == "" or block is None or block.strip() == ""
