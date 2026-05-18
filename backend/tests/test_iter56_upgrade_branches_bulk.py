"""Iter 56 — Stripe upgrade + 32-journey branch firing + bulk enrol regression tests."""
import os
import sys
import uuid
import requests
import pytest
from pymongo import MongoClient
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

API_URL = os.getenv("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com")
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = "Demo1234!"
mongo_client = MongoClient(os.environ["MONGO_URL"])
db = mongo_client[os.environ["DB_NAME"]]


@pytest.fixture(scope="module")
def auth():
    r = requests.post(f"{API_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200
    return {
        "headers": {
            "Authorization": f"Bearer {r.json()['token']}",
            "X-Tenant-Id": "ten_demo",
            "Content-Type": "application/json",
        },
        "tenant_id": "ten_demo",
    }


# ─── Stripe upgrade — Item 1 ───────────────────────────────────────────────
def test_upgrade_packages_catalog(auth):
    """Public catalog returns all 3 upgrade SKUs with server-side amounts."""
    r = requests.get(f"{API_URL}/api/billing/upgrade-packages",
                     headers={"Authorization": auth["headers"]["Authorization"]}, timeout=10)
    assert r.status_code == 200
    pkgs = r.json().get("packages") or {}
    assert "diy_to_dwy" in pkgs
    assert pkgs["diy_to_dwy"]["amount"] == 12999.0
    assert pkgs["diy_to_dwy"]["currency"] == "inr"
    assert pkgs["diy_to_dwy"]["plan_target"] == "dwy"


def test_create_checkout_session_returns_stripe_url(auth):
    """Hitting create-session should return a real Stripe checkout URL + tx row in mongo."""
    # Force tenant onto diy plan so the upgrade check passes
    db["tenants"].update_one({"id": "ten_demo"}, {"$set": {"plan": "diy"}})
    r = requests.post(
        f"{API_URL}/api/billing/checkout/session",
        headers=auth["headers"],
        json={"package_id": "diy_to_dwy", "origin_url": "https://app.genleadai.com"},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["url"].startswith("https://checkout.stripe.com/")
    assert body["session_id"].startswith("cs_")
    # Mongo tx row exists
    tx = db["payment_transactions"].find_one({"session_id": body["session_id"]})
    assert tx is not None
    assert tx["plan_target"] == "dwy"
    assert tx["amount"] == 12999.0
    assert tx["payment_status"] == "initiated"
    # Restore plan
    db["tenants"].update_one({"id": "ten_demo"}, {"$set": {"plan": "dwy"}})


def test_invalid_package_rejected(auth):
    r = requests.post(
        f"{API_URL}/api/billing/checkout/session",
        headers=auth["headers"],
        json={"package_id": "diy_to_unicorn", "origin_url": "https://app.genleadai.com"},
        timeout=10,
    )
    assert r.status_code == 400
    assert "invalid_package" in r.text


# ─── Bulk enrol & high-intent enrol — Item 3 ───────────────────────────────
def test_enroll_high_intent_creates_enrollments(auth):
    """Tag 2 leads as hot, enrol-high-intent, verify ccs rows created."""
    # Create a campaign + step 1
    r = requests.post(f"{API_URL}/api/outreach/campaigns", headers=auth["headers"], json={"name": "High-Intent Sweep Test"}, timeout=10)
    cid = r.json()["id"]
    requests.post(
        f"{API_URL}/api/outreach/campaigns/{cid}/touchpoints",
        headers=auth["headers"],
        json={"step_number": 1, "message_template": "hi {first_name}", "delay_hours": 0, "channel": "whatsapp"},
        timeout=10,
    )
    # Inject 2 leads tagged hot
    test_lead_ids = []
    for i in range(2):
        lid = f"test_hot_lead_{uuid.uuid4().hex[:8]}"
        db["leads"].insert_one({
            "id": lid, "tenant_id": "ten_demo", "name": f"Hot {i}", "phone": f"+1202555099{i}",
            "tier": "hot", "status": "high_intent",
        })
        test_lead_ids.append(lid)
    try:
        r = requests.post(
            f"{API_URL}/api/outreach/campaigns/{cid}/enroll-high-intent",
            headers=auth["headers"], timeout=10,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["enrolled"] >= 2     # may include other pre-existing hot leads
        assert body["matched"] >= 2
    finally:
        for lid in test_lead_ids:
            db["leads"].delete_one({"id": lid})
        # Cleanup test campaign
        db["outreach_touchpoints"].delete_many({"campaign_id": cid})
        db["contact_campaign_status"].delete_many({"campaign_id": cid})
        db["outreach_campaigns"].delete_one({"id": cid})


def test_enroll_high_intent_400_when_no_step_1(auth):
    """Campaign with no step 1 → 400 no_touchpoint_step_1 with string detail."""
    r = requests.post(f"{API_URL}/api/outreach/campaigns", headers=auth["headers"], json={"name": "Empty Test"}, timeout=10)
    cid = r.json()["id"]
    try:
        r = requests.post(
            f"{API_URL}/api/outreach/campaigns/{cid}/enroll-high-intent",
            headers=auth["headers"], timeout=10,
        )
        assert r.status_code == 400
        assert "no_touchpoint_step_1" in r.text
    finally:
        db["outreach_campaigns"].delete_one({"id": cid})


# ─── 32-journey branch firing — Item 2 ──────────────────────────────────────
def test_journey_branch_keyword_match_stops_journey():
    """Stage a sent touchpoint with conditions, call handle_inbound_reply_for_journey,
    verify pending journey rows are cancelled (stop branch)."""
    from routes.touchpoint_engine import handle_inbound_reply_for_journey
    tenant_id = "ten_demo"
    lead_id = f"test_branch_lead_{uuid.uuid4().hex[:8]}"
    db["leads"].insert_one({
        "id": lead_id, "tenant_id": tenant_id, "name": "Branch Tester", "phone": "+12025550912",
    })
    log = db["lead_touchpoint_log"]
    # Most recent "sent" touchpoint with on_negative_keyword stop branch
    sent_row = {
        "id": f"ltl_{uuid.uuid4().hex[:8]}",
        "tenant_id": tenant_id, "lead_id": lead_id, "touchpoint_index": 1,
        "channel": "whatsapp", "message_type": "intro", "aria_role": "autonomous",
        "message_template": "hi", "conditions": {
            "on_negative_keyword": {"keywords": ["not interested", "stop"], "action": "stop"},
        },
        "scheduled_for": "2026-01-01T00:00:00+00:00",
        "status": "sent", "fired_at": "2026-01-01T01:00:00+00:00",
        "message_sent": "hi", "retry_count": 0, "created_at": "2026-01-01T00:00:00+00:00",
    }
    # Plus 2 pending follow-up rows
    pending_rows = []
    for idx in (2, 3):
        pending_rows.append({
            "id": f"ltl_{uuid.uuid4().hex[:8]}",
            "tenant_id": tenant_id, "lead_id": lead_id, "touchpoint_index": idx,
            "channel": "whatsapp", "message_type": "follow_up", "aria_role": "autonomous",
            "message_template": "follow up", "conditions": {},
            "scheduled_for": "2026-01-02T00:00:00+00:00",
            "status": "pending", "fired_at": None,
            "retry_count": 0, "created_at": "2026-01-01T00:00:00+00:00",
        })
    log.insert_many([sent_row] + pending_rows)

    try:
        result = handle_inbound_reply_for_journey(tenant_id, lead_id, "please STOP, not interested")
        assert result.get("evaluated") is True, result
        assert result.get("branch") == "on_negative_keyword"
        # Verify pending rows are cancelled
        cancelled = log.count_documents({"tenant_id": tenant_id, "lead_id": lead_id, "status": "cancelled"})
        assert cancelled == 2, f"expected 2 cancelled, got {cancelled}"
    finally:
        log.delete_many({"lead_id": lead_id})
        db["leads"].delete_one({"id": lead_id})


def test_journey_branch_no_match_returns_evaluated_false():
    """If body doesn't match any keyword and no on_reply, branch returns False."""
    from routes.touchpoint_engine import handle_inbound_reply_for_journey
    tenant_id = "ten_demo"
    lead_id = f"test_nomatch_lead_{uuid.uuid4().hex[:8]}"
    db["leads"].insert_one({"id": lead_id, "tenant_id": tenant_id, "name": "X"})
    log = db["lead_touchpoint_log"]
    log.insert_one({
        "id": f"ltl_{uuid.uuid4().hex[:8]}",
        "tenant_id": tenant_id, "lead_id": lead_id, "touchpoint_index": 1,
        "channel": "whatsapp", "message_template": "hi",
        "conditions": {"on_keyword_match": {"keywords": ["interested"], "action": "tag_contact", "tag": "hot_lead"}},
        "status": "sent", "fired_at": "2026-01-01T01:00:00+00:00",
        "created_at": "2026-01-01T00:00:00+00:00", "scheduled_for": "2026-01-01T00:00:00+00:00", "retry_count": 0,
    })
    try:
        result = handle_inbound_reply_for_journey(tenant_id, lead_id, "hello there friend")
        assert result.get("evaluated") in (False, None)
    finally:
        log.delete_many({"lead_id": lead_id})
        db["leads"].delete_one({"id": lead_id})


# ─── Doc-version diff — Item 4 ──────────────────────────────────────────────
def test_auto_map_diff_returns_changes(auth):
    r = requests.post(
        f"{API_URL}/api/aria/auto-map/diff",
        headers=auth["headers"],
        json={
            "icps": [{"label": "Brand-new persona that does not exist yet", "tone": "professional"}],
            "touchpoints": [
                {"index": 0, "day": 0, "hour": 9, "channel": "whatsapp",
                 "message_type": "intro", "aria_role": "autonomous",
                 "message_template": "hi", "conditions": {}},
            ],
            "lead_sources": ["Cold email"],
        },
        timeout=15,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "icp_changes" in body
    assert "touchpoint_diff" in body
    assert "summary" in body
    # The made-up persona should be flagged as create
    assert any(c["action"] == "create" and "Brand-new" in c["label"] for c in body["icp_changes"])


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
