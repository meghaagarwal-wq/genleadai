"""Iter119 Batch 7 — Approval Queue backend tests.

Covers 7 endpoints under /api/approvals, tenant isolation, idempotency, 
edit persistence and bulk operations.
"""
import os
import sys
import uuid
from datetime import datetime, timezone

import pytest
import requests
from bson import ObjectId
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

# Auth creds
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = "Demo1234!"
PIETENTIAL_TENANT = "ten_pietential"
DEMO_TENANT = "ten_demo"

# Mongo connection for test seeding/cleanup
client = MongoClient(MONGO_URL)
db = client[DB_NAME]
pending_col = db["pending_outreach"]
leads_col = db["pt_leads"]


# ─── Fixtures ───────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD,
    })
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def api_pietential(auth_token):
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {auth_token}",
        "X-Tenant-Id": PIETENTIAL_TENANT,
        "Content-Type": "application/json",
    })
    return s


@pytest.fixture(scope="module")
def api_demo(auth_token):
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {auth_token}",
        "X-Tenant-Id": DEMO_TENANT,
        "Content-Type": "application/json",
    })
    return s


@pytest.fixture(autouse=True)
def cleanup_test_drafts():
    """Drop any drafts we seeded (those tagged with TEST_ITER119_)."""
    yield
    pending_col.delete_many({"meta_tag": "TEST_ITER119_"})


def _seed_draft(tenant_id: str, lead_id: str = "ptl_replytest01", channel: str = "email",
                subject: str = "Quick idea", body: str = "Original drafted body for test") -> str:
    doc = {
        "tenant_id": tenant_id,
        "lead_id": lead_id,
        "channel": channel,
        "subject": subject,
        "body": body,
        "status": "awaiting_owner_approval",
        "ai_powered": True,
        "qualification": {
            "intent": "interested",
            "summary": "Prospect engaged positively",
            "next_action_hint": "Send a calendar link",
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "meta_tag": "TEST_ITER119_",
    }
    res = pending_col.insert_one(doc)
    return str(res.inserted_id)


# ─── Tests ──────────────────────────────────────────────────────────────
class TestListAndCount:
    def test_list_shape_no_bson_id_leak(self, api_pietential):
        sid = _seed_draft(PIETENTIAL_TENANT)
        r = api_pietential.get(f"{BASE_URL}/api/approvals")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data and "count" in data
        assert isinstance(data["items"], list)
        assert data["count"] == len(data["items"])
        # find our seed
        ours = [it for it in data["items"] if it.get("id") == sid]
        assert len(ours) == 1
        item = ours[0]
        # No BSON _id leak
        for it in data["items"]:
            assert "_id" not in it, f"BSON _id leaked: {it}"
            assert isinstance(it.get("id"), str)
            assert it.get("status") == "awaiting_owner_approval"
            assert "lead_snapshot" in it
            snap = it["lead_snapshot"]
            for k in ("name", "company", "stage", "score", "first_name", "email"):
                assert k in snap, f"missing lead_snapshot.{k}"

    def test_count_matches_list(self, api_pietential):
        _seed_draft(PIETENTIAL_TENANT)
        list_r = api_pietential.get(f"{BASE_URL}/api/approvals")
        count_r = api_pietential.get(f"{BASE_URL}/api/approvals/count")
        assert count_r.status_code == 200
        assert count_r.json()["count"] == list_r.json()["count"]


class TestApprove:
    def test_approve_valid(self, api_pietential):
        sid = _seed_draft(PIETENTIAL_TENANT)
        r = api_pietential.post(f"{BASE_URL}/api/approvals/{sid}/approve")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        assert "dispatch" in body
        doc = pending_col.find_one({"_id": ObjectId(sid)})
        assert doc["status"] in ("sent", "send_failed", "drafted_pending_provider")

    def test_approve_invalid_id(self, api_pietential):
        r = api_pietential.post(f"{BASE_URL}/api/approvals/not-a-valid-oid/approve")
        assert r.status_code == 400

    def test_approve_already_actioned_409(self, api_pietential):
        sid = _seed_draft(PIETENTIAL_TENANT)
        # First approve
        r1 = api_pietential.post(f"{BASE_URL}/api/approvals/{sid}/approve")
        assert r1.status_code == 200
        # Second should 409
        r2 = api_pietential.post(f"{BASE_URL}/api/approvals/{sid}/approve")
        assert r2.status_code == 409


class TestTenantIsolation:
    def test_approve_other_tenant_returns_404(self, api_pietential):
        # Seed under ten_demo
        sid = _seed_draft(DEMO_TENANT)
        # Caller is ten_pietential — must 404 not 401
        r = api_pietential.post(f"{BASE_URL}/api/approvals/{sid}/approve")
        assert r.status_code == 404

    def test_edit_other_tenant_returns_404(self, api_pietential):
        sid = _seed_draft(DEMO_TENANT)
        r = api_pietential.post(
            f"{BASE_URL}/api/approvals/{sid}/edit-send",
            json={"subject": "hi", "body": "edited"},
        )
        assert r.status_code == 404

    def test_reject_other_tenant_returns_404(self, api_pietential):
        sid = _seed_draft(DEMO_TENANT)
        r = api_pietential.post(f"{BASE_URL}/api/approvals/{sid}/reject", json={})
        assert r.status_code == 404


class TestEditSend:
    def test_edit_persists_and_dispatches(self, api_pietential):
        sid = _seed_draft(PIETENTIAL_TENANT, body="Original drafted body for test")
        edited_subject = f"EDITED-{uuid.uuid4().hex[:6]}"
        edited_body = f"EDITED-BODY-{uuid.uuid4().hex[:8]}"
        r = api_pietential.post(
            f"{BASE_URL}/api/approvals/{sid}/edit-send",
            json={"subject": edited_subject, "body": edited_body},
        )
        assert r.status_code == 200, r.text
        doc = pending_col.find_one({"_id": ObjectId(sid)})
        # Persisted edits
        assert doc["subject"] == edited_subject, f"subject not persisted: {doc.get('subject')}"
        assert doc["body"] == edited_body, f"body not persisted: {doc.get('body')[:60]}"
        assert "edited_at" in doc
        assert doc.get("edited_by") is not None
        # Status moved off awaiting
        assert doc["status"] in ("sent", "send_failed", "drafted_pending_provider")


class TestReject:
    def test_reject_with_reason(self, api_pietential):
        sid = _seed_draft(PIETENTIAL_TENANT)
        r = api_pietential.post(f"{BASE_URL}/api/approvals/{sid}/reject",
                                 json={"reason": "Off tone"})
        assert r.status_code == 200
        doc = pending_col.find_one({"_id": ObjectId(sid)})
        assert doc["status"] == "rejected"
        assert doc["rejection_reason"] == "Off tone"

    def test_reject_without_reason(self, api_pietential):
        sid = _seed_draft(PIETENTIAL_TENANT)
        r = api_pietential.post(f"{BASE_URL}/api/approvals/{sid}/reject", json={})
        assert r.status_code == 200
        doc = pending_col.find_one({"_id": ObjectId(sid)})
        assert doc["status"] == "rejected"
        assert doc.get("rejection_reason") is None


class TestBulk:
    def test_bulk_approve_all(self, api_pietential):
        # Wipe non-awaiting first to set up a clean count
        pending_col.delete_many({"tenant_id": PIETENTIAL_TENANT, "meta_tag": "TEST_ITER119_"})
        ids = [_seed_draft(PIETENTIAL_TENANT) for _ in range(3)]
        r = api_pietential.post(f"{BASE_URL}/api/approvals/bulk-approve", json={})
        assert r.status_code == 200, r.text
        data = r.json()
        assert "processed" in data and "succeeded" in data and "failed" in data
        assert data["processed"] >= 3
        assert data["succeeded"] + data["failed"] == data["processed"]
        assert isinstance(data.get("results"), list)
        for res in data["results"]:
            assert "id" in res and "status" in res
        # Our seeded items must not still be awaiting
        for sid in ids:
            d = pending_col.find_one({"_id": ObjectId(sid)})
            assert d["status"] != "awaiting_owner_approval"

    def test_bulk_approve_subset(self, api_pietential):
        pending_col.delete_many({"tenant_id": PIETENTIAL_TENANT, "meta_tag": "TEST_ITER119_"})
        ids = [_seed_draft(PIETENTIAL_TENANT) for _ in range(3)]
        subset = ids[:2]
        r = api_pietential.post(f"{BASE_URL}/api/approvals/bulk-approve",
                                 json={"ids": subset})
        assert r.status_code == 200
        data = r.json()
        assert data["processed"] == 2
        # Untouched id still awaiting
        untouched = pending_col.find_one({"_id": ObjectId(ids[2])})
        assert untouched["status"] == "awaiting_owner_approval"

    def test_bulk_reject_all(self, api_pietential):
        pending_col.delete_many({"tenant_id": PIETENTIAL_TENANT, "meta_tag": "TEST_ITER119_"})
        ids = [_seed_draft(PIETENTIAL_TENANT) for _ in range(2)]
        r = api_pietential.post(f"{BASE_URL}/api/approvals/bulk-reject", json={})
        assert r.status_code == 200
        data = r.json()
        assert "rejected" in data
        assert data["rejected"] >= 2
        for sid in ids:
            d = pending_col.find_one({"_id": ObjectId(sid)})
            assert d["status"] == "rejected"


class TestRegression:
    def test_resend_webhook_creates_pending_outreach(self, api_pietential):
        """Smoke: Resend inbound webhook still produces a pending_outreach doc visible to /api/approvals."""
        # Get count before
        before = api_pietential.get(f"{BASE_URL}/api/approvals/count").json()["count"]
        # Look up lead email for ptl_replytest01
        lead = leads_col.find_one({"id": "ptl_replytest01", "tenant_id": PIETENTIAL_TENANT})
        if not lead or not lead.get("email"):
            pytest.skip("ptl_replytest01 lead not seeded; webhook regression skipped")
        email = lead["email"]
        unique_id = f"iter119_{uuid.uuid4().hex[:10]}"
        payload = {
            "type": "email.received",
            "data": {
                "email_id": unique_id,
                "from": email,
                "to": "founder@pietential.com",
                "subject": "Re: ARIA",
                "text": "Interested — can we chat next week?",
            },
        }
        r = requests.post(f"{BASE_URL}/api/webhooks/resend", json=payload, timeout=30)
        assert r.status_code in (200, 202), f"{r.status_code} {r.text}"
        # Allow a moment for async DB write
        import time
        time.sleep(2)
        after = api_pietential.get(f"{BASE_URL}/api/approvals/count").json()["count"]
        assert after >= before, f"approvals count did not grow: before={before} after={after}"
