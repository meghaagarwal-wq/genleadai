"""Iter 52 — Multi-ICP + Outreach Campaigns end-to-end pytest.

Covers:
  Deliverable 7 — Multi-ICP
    - create (tier limit, tone validation, role gating)
    - list
    - update
    - delete (in-use guard + force=true untag)
    - assign-contact

  Deliverable 8 — Outreach Campaigns
    - campaign CRUD + listing
    - touchpoint upsert + conditions schema validation (positive + negative)
    - enroll contacts (idempotent, missing-contact detection, no_touchpoint_step_1 error)
    - pause / resume cascades to enrollments
    - render_template (pure function with token spec)
    - handle_inbound_reply (keyword match, negative keyword, generic on_reply, no-op)
    - condition branches (move_to_step, tag_contact, stop, notify_user)

Run:  cd /app/backend && python -m pytest tests/test_iter52_multi_icp_outreach.py -v
"""
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


# ─── Shared fixtures ────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def auth():
    r = requests.post(f"{API_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD,
    }, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data["token"]
    tenant_id = data["user"].get("tenant_id") or "ten_demo"
    return {
        "headers": {
            "Authorization": f"Bearer {token}",
            "X-Tenant-Id": tenant_id,
            "Content-Type": "application/json",
        },
        "tenant_id": tenant_id,
    }


@pytest.fixture(autouse=True)
def cleanup_collections(auth):
    """Wipe iter52 test rows before AND after each test for isolation."""
    tenant_id = auth["tenant_id"]
    for col in ("icps", "outreach_campaigns", "outreach_touchpoints",
                "contact_campaign_status", "outreach_campaign_logs"):
        db[col].delete_many({"tenant_id": tenant_id})
    yield
    for col in ("icps", "outreach_campaigns", "outreach_touchpoints",
                "contact_campaign_status", "outreach_campaign_logs"):
        db[col].delete_many({"tenant_id": tenant_id})


def _bump_plan(tenant_id: str, plan: str):
    db["tenants"].update_one({"id": tenant_id}, {"$set": {"plan": plan}})


# ═══════════════════════════════════════════════════════════════════════════
# DELIVERABLE 7 — MULTI-ICP
# ═══════════════════════════════════════════════════════════════════════════
def test_icp_create_then_list(auth):
    r = requests.post(f"{API_URL}/api/icps/create", headers=auth["headers"], json={
        "label": "CFO at Series B SaaS",
        "title_targets": ["CFO", "VP Finance"],
        "industry": "SaaS",
        "company_size": "50-200",
        "pain_point": "Manual finance ops",
        "value_prop": "Automate close in 1 day",
        "tone": "professional",
        "deal_size": "$30k ACV",
    }, timeout=15)
    assert r.status_code == 201, r.text
    icp = r.json()
    assert icp["id"].startswith("icp_")
    assert icp["label"] == "CFO at Series B SaaS"
    assert icp["title_targets"] == ["CFO", "VP Finance"]

    lst = requests.get(f"{API_URL}/api/icps/list", headers=auth["headers"], timeout=10)
    assert lst.status_code == 200
    data = lst.json()
    assert data["count"] >= 1
    assert any(i["id"] == icp["id"] for i in data["icps"])
    assert "limit" in data and "can_create_more" in data


def test_icp_invalid_tone(auth):
    r = requests.post(f"{API_URL}/api/icps/create", headers=auth["headers"], json={
        "label": "Bad tone test",
        "tone": "screaming",
    }, timeout=10)
    assert r.status_code == 400
    assert "invalid_tone" in r.text


def test_icp_tier_limit_starter_capped_at_2(auth):
    """Iter77 — GenLeadAI is a managed deployment; ICP caps were removed.
    Validate the cap is NO LONGER enforced: a 3rd ICP on a 'diy' tenant
    must now succeed (201) and the /list response must report
    `can_create_more: True` with `limit: null`."""
    _bump_plan(auth["tenant_id"], "diy")
    for i in range(3):
        r = requests.post(f"{API_URL}/api/icps/create", headers=auth["headers"], json={
            "label": f"ICP {i+1}", "tone": "professional",
        }, timeout=10)
        assert r.status_code == 201, r.text
    lst = requests.get(f"{API_URL}/api/icps/list", headers=auth["headers"], timeout=10).json()
    assert lst["count"] >= 3
    assert lst["limit"] is None
    assert lst["can_create_more"] is True
    _bump_plan(auth["tenant_id"], "dwy")  # restore unlimited for downstream tests


def test_icp_tier_unlimited_on_dwy(auth):
    _bump_plan(auth["tenant_id"], "dwy")
    for i in range(4):
        r = requests.post(f"{API_URL}/api/icps/create", headers=auth["headers"], json={
            "label": f"ICP-{i}", "tone": "casual",
        }, timeout=10)
        assert r.status_code == 201


def test_icp_update_partial(auth):
    r = requests.post(f"{API_URL}/api/icps/create", headers=auth["headers"], json={
        "label": "Original", "tone": "professional", "pain_point": "old",
    }, timeout=10)
    icp_id = r.json()["id"]
    u = requests.put(f"{API_URL}/api/icps/{icp_id}", headers=auth["headers"], json={
        "label": "Renamed", "pain_point": "new pain", "tone": "bold",
    }, timeout=10)
    assert u.status_code == 200, u.text
    fresh = u.json()
    assert fresh["label"] == "Renamed"
    assert fresh["pain_point"] == "new pain"
    assert fresh["tone"] == "bold"


def test_icp_delete_with_no_tagged_records(auth):
    r = requests.post(f"{API_URL}/api/icps/create", headers=auth["headers"], json={
        "label": "Throwaway", "tone": "professional",
    }, timeout=10)
    icp_id = r.json()["id"]
    d = requests.delete(f"{API_URL}/api/icps/{icp_id}", headers=auth["headers"], timeout=10)
    assert d.status_code == 200
    assert d.json().get("deleted") is True


def test_icp_delete_blocked_when_tagged(auth):
    r = requests.post(f"{API_URL}/api/icps/create", headers=auth["headers"], json={
        "label": "Tagged ICP", "tone": "professional",
    }, timeout=10)
    icp_id = r.json()["id"]
    # Seed a lead tagged to this ICP
    test_lead_id = f"test_lead_{uuid.uuid4().hex[:8]}"
    db["leads"].insert_one({
        "id": test_lead_id, "tenant_id": auth["tenant_id"],
        "name": "Tagged Lead", "phone": "+12025550199", "email": "tag@example.com",
        "icp_id": icp_id,
    })
    try:
        # Without force → 409 with counts
        d1 = requests.delete(f"{API_URL}/api/icps/{icp_id}", headers=auth["headers"], timeout=10)
        assert d1.status_code == 409
        body = d1.json()
        assert "icp_in_use" in str(body)
        # With force=true → succeeds + untags
        d2 = requests.delete(f"{API_URL}/api/icps/{icp_id}?force=true", headers=auth["headers"], timeout=10)
        assert d2.status_code == 200
        # Lead's icp_id should now be None
        lead = db["leads"].find_one({"id": test_lead_id})
        assert lead.get("icp_id") is None
    finally:
        db["leads"].delete_one({"id": test_lead_id})


def test_icp_assign_contact_happy_path(auth):
    r = requests.post(f"{API_URL}/api/icps/create", headers=auth["headers"], json={
        "label": "Assign target", "tone": "professional",
    }, timeout=10)
    icp_id = r.json()["id"]
    test_lead_id = f"test_lead_{uuid.uuid4().hex[:8]}"
    db["leads"].insert_one({
        "id": test_lead_id, "tenant_id": auth["tenant_id"],
        "name": "Assign Me", "phone": "+12025550200",
    })
    try:
        a = requests.post(f"{API_URL}/api/icps/assign-contact", headers=auth["headers"], json={
            "contact_id": test_lead_id, "icp_id": icp_id,
        }, timeout=10)
        assert a.status_code == 200, a.text
        # Verify lead actually got tagged in Mongo
        lead = db["leads"].find_one({"id": test_lead_id})
        assert lead["icp_id"] == icp_id

        # Clear assignment
        clr = requests.post(f"{API_URL}/api/icps/assign-contact", headers=auth["headers"], json={
            "contact_id": test_lead_id, "icp_id": None,
        }, timeout=10)
        assert clr.status_code == 200
        lead = db["leads"].find_one({"id": test_lead_id})
        assert lead.get("icp_id") is None
    finally:
        db["leads"].delete_one({"id": test_lead_id})


def test_icp_assign_contact_missing_contact(auth):
    r = requests.post(f"{API_URL}/api/icps/create", headers=auth["headers"], json={
        "label": "Whatever", "tone": "professional",
    }, timeout=10)
    icp_id = r.json()["id"]
    a = requests.post(f"{API_URL}/api/icps/assign-contact", headers=auth["headers"], json={
        "contact_id": "does_not_exist_xxx", "icp_id": icp_id,
    }, timeout=10)
    assert a.status_code == 404
    assert "contact_not_found" in a.text


# ═══════════════════════════════════════════════════════════════════════════
# DELIVERABLE 8 — OUTREACH CAMPAIGNS
# ═══════════════════════════════════════════════════════════════════════════
def test_outreach_campaign_create_and_list(auth):
    r = requests.post(f"{API_URL}/api/outreach/campaigns", headers=auth["headers"], json={
        "name": "Q1 Outbound to CFOs",
    }, timeout=10)
    assert r.status_code == 201, r.text
    camp = r.json()
    assert camp["id"].startswith("oc_")
    assert camp["status"] == "draft"

    lst = requests.get(f"{API_URL}/api/outreach/campaigns", headers=auth["headers"], timeout=10)
    assert lst.status_code == 200
    assert any(c["id"] == camp["id"] for c in lst.json()["campaigns"])


def test_outreach_touchpoint_upsert_with_valid_conditions(auth):
    r = requests.post(f"{API_URL}/api/outreach/campaigns", headers=auth["headers"], json={
        "name": "Test Campaign with Conditions",
    }, timeout=10)
    cid = r.json()["id"]

    tp = requests.post(
        f"{API_URL}/api/outreach/campaigns/{cid}/touchpoints",
        headers=auth["headers"],
        json={
            "step_number": 1,
            "channel": "whatsapp",
            "message_template": "Hi {first_name}, saw {company} is scaling — quick question?",
            "delay_hours": 0,
            "conditions": {
                "on_reply": {"action": "notify_user"},
                "on_keyword_match": {
                    "keywords": ["interested", "pricing"],
                    "action": "tag_contact",
                    "tag": "hot_lead",
                },
                "on_negative_keyword": {
                    "keywords": ["not interested", "stop"],
                    "action": "stop",
                },
                "on_no_reply": {"after_hours": 72, "action": "move_to_step", "target_step": 2},
            },
        },
        timeout=10,
    )
    assert tp.status_code == 201, tp.text
    body = tp.json()
    assert body["step_number"] == 1
    assert body["conditions"]["on_no_reply"]["after_hours"] == 72

    # Upsert — change message → should update, not duplicate
    tp2 = requests.post(
        f"{API_URL}/api/outreach/campaigns/{cid}/touchpoints",
        headers=auth["headers"],
        json={
            "step_number": 1, "channel": "whatsapp",
            "message_template": "UPDATED message {first_name}",
            "delay_hours": 2, "conditions": {},
        },
        timeout=10,
    )
    assert tp2.status_code == 201
    # Verify only one row exists at step 1
    cnt = db["outreach_touchpoints"].count_documents({
        "tenant_id": auth["tenant_id"], "campaign_id": cid, "step_number": 1,
    })
    assert cnt == 1


def test_outreach_touchpoint_invalid_conditions(auth):
    r = requests.post(f"{API_URL}/api/outreach/campaigns", headers=auth["headers"], json={"name": "Bad cond test"}, timeout=10)
    cid = r.json()["id"]

    # Unknown key
    bad = requests.post(
        f"{API_URL}/api/outreach/campaigns/{cid}/touchpoints",
        headers=auth["headers"],
        json={
            "step_number": 1, "message_template": "x", "delay_hours": 0,
            "conditions": {"on_telepathy": {"action": "stop"}},
        },
        timeout=10,
    )
    assert bad.status_code == 400
    assert "unknown_condition_keys" in bad.text

    # tag_contact without tag
    bad2 = requests.post(
        f"{API_URL}/api/outreach/campaigns/{cid}/touchpoints",
        headers=auth["headers"],
        json={
            "step_number": 1, "message_template": "x", "delay_hours": 0,
            "conditions": {"on_reply": {"action": "tag_contact"}},
        },
        timeout=10,
    )
    assert bad2.status_code == 400
    assert "tag required" in bad2.text or "tag_contact" in bad2.text

    # on_no_reply with bad after_hours
    bad3 = requests.post(
        f"{API_URL}/api/outreach/campaigns/{cid}/touchpoints",
        headers=auth["headers"],
        json={
            "step_number": 1, "message_template": "x", "delay_hours": 0,
            "conditions": {"on_no_reply": {"after_hours": -5, "action": "stop"}},
        },
        timeout=10,
    )
    assert bad3.status_code == 400


def test_outreach_campaign_map(auth):
    r = requests.post(f"{API_URL}/api/outreach/campaigns", headers=auth["headers"], json={"name": "Map test"}, timeout=10)
    cid = r.json()["id"]
    for step in (1, 2, 3):
        requests.post(
            f"{API_URL}/api/outreach/campaigns/{cid}/touchpoints",
            headers=auth["headers"],
            json={"step_number": step, "message_template": f"step {step}", "delay_hours": 24 * (step - 1)},
            timeout=10,
        )
    m = requests.get(f"{API_URL}/api/outreach/campaigns/{cid}/map", headers=auth["headers"], timeout=10)
    assert m.status_code == 200
    data = m.json()
    assert data["campaign"]["id"] == cid
    assert [t["step_number"] for t in data["touchpoints"]] == [1, 2, 3]


def test_outreach_enroll_idempotent(auth):
    r = requests.post(f"{API_URL}/api/outreach/campaigns", headers=auth["headers"], json={"name": "Enroll test"}, timeout=10)
    cid = r.json()["id"]
    # Try enrolling before any touchpoint exists → 400
    test_lead_id = f"test_lead_{uuid.uuid4().hex[:8]}"
    db["leads"].insert_one({
        "id": test_lead_id, "tenant_id": auth["tenant_id"],
        "name": "Enroll Me", "phone": "+12025550201",
    })
    try:
        err = requests.post(
            f"{API_URL}/api/outreach/campaigns/{cid}/enroll", headers=auth["headers"],
            json={"contact_ids": [test_lead_id]}, timeout=10,
        )
        assert err.status_code == 400
        assert "no_touchpoint_step_1" in err.text

        # Add step 1 and retry
        requests.post(
            f"{API_URL}/api/outreach/campaigns/{cid}/touchpoints",
            headers=auth["headers"],
            json={"step_number": 1, "message_template": "Hi {first_name}", "delay_hours": 0},
            timeout=10,
        )
        ok = requests.post(
            f"{API_URL}/api/outreach/campaigns/{cid}/enroll", headers=auth["headers"],
            json={"contact_ids": [test_lead_id, "missing_id_xxx"]},
            timeout=10,
        )
        assert ok.status_code == 200, ok.text
        body = ok.json()
        assert body["enrolled"] == 1
        assert body["skipped"] == 0
        assert "missing_id_xxx" in body["missing"]

        # Re-enroll → skipped
        again = requests.post(
            f"{API_URL}/api/outreach/campaigns/{cid}/enroll", headers=auth["headers"],
            json={"contact_ids": [test_lead_id]}, timeout=10,
        )
        assert again.json()["skipped"] == 1
    finally:
        db["leads"].delete_one({"id": test_lead_id})


def test_outreach_pause_resume_cascade(auth):
    r = requests.post(f"{API_URL}/api/outreach/campaigns", headers=auth["headers"], json={"name": "Pause test"}, timeout=10)
    cid = r.json()["id"]
    requests.post(
        f"{API_URL}/api/outreach/campaigns/{cid}/touchpoints",
        headers=auth["headers"],
        json={"step_number": 1, "message_template": "hi", "delay_hours": 0},
        timeout=10,
    )
    # Inject 3 active enrollments directly
    for i in range(3):
        db["contact_campaign_status"].insert_one({
            "id": f"ccs_{uuid.uuid4().hex[:8]}",
            "tenant_id": auth["tenant_id"], "campaign_id": cid,
            "contact_id": f"fake_lead_{i}", "current_step": 1, "status": "active",
            "next_due_at": None, "created_at": "2026-01-01T00:00:00+00:00",
        })
    pr = requests.post(f"{API_URL}/api/outreach/campaigns/{cid}/pause", headers=auth["headers"], timeout=10)
    assert pr.status_code == 200
    assert pr.json()["paused_contacts"] == 3
    rr = requests.post(f"{API_URL}/api/outreach/campaigns/{cid}/resume", headers=auth["headers"], timeout=10)
    assert rr.status_code == 200
    assert rr.json()["resumed_contacts"] == 3


# ─── Pure helpers (no HTTP) ─────────────────────────────────────────────────
def test_render_template_all_tokens_present():
    from routes.outreach import render_template
    out = render_template(
        "Hi {first_name} at {company}, our {value_prop} helps with {pain_point}.",
        {"name": "Jane Doe", "company": "Acme Corp"},
        {"value_prop": "1-day close", "pain_point": "manual ops", "tone": "professional"},
    )
    assert "Jane" in out
    assert "Acme Corp" in out
    assert "1-day close" in out
    assert "manual ops" in out


def test_render_template_missing_tokens_become_empty():
    from routes.outreach import render_template
    out = render_template("Hi {first_name}, your {value_prop}", {"name": "Bob"}, None)
    assert out == "Hi Bob, your "


def test_render_template_no_tokens():
    from routes.outreach import render_template
    assert render_template("plain text no tokens", {}, {}) == "plain text no tokens"


def test_render_template_malformed_tokens_left_literal():
    from routes.outreach import render_template
    # Unmatched braces should not crash
    assert render_template("Hi {first_name", {"name": "Joe"}, {}) == "Hi {first_name"
    # Unknown token → empty
    assert render_template("Hi {whatever_token}", {"name": "Joe"}, {}) == "Hi "


def test_validate_conditions_accepts_all_branches():
    from routes.outreach import validate_conditions
    cond = {
        "on_reply": {"action": "move_to_step", "target_step": 3},
        "on_keyword_match": {"keywords": ["interested"], "action": "tag_contact", "tag": "hot_lead"},
        "on_negative_keyword": {"keywords": ["stop"], "action": "stop"},
        "on_no_reply": {"after_hours": 48, "action": "move_to_step", "target_step": 2},
    }
    out = validate_conditions(cond)
    assert out["on_reply"]["target_step"] == 3
    assert out["on_keyword_match"]["keywords"] == ["interested"]
    assert out["on_no_reply"]["after_hours"] == 48


def test_handle_inbound_reply_keyword_match_tags_hot_lead(auth):
    """Build a 1-step campaign with keyword=interested→tag_contact hot_lead,
    enroll a lead, then call handle_inbound_reply with 'I'm interested' — verify
    status flips to hot_lead + log row inserted."""
    from routes.outreach import handle_inbound_reply

    tenant_id = auth["tenant_id"]
    # Build campaign
    r = requests.post(f"{API_URL}/api/outreach/campaigns", headers=auth["headers"], json={"name": "Reply branch test"}, timeout=10)
    cid = r.json()["id"]
    requests.post(
        f"{API_URL}/api/outreach/campaigns/{cid}/touchpoints",
        headers=auth["headers"],
        json={
            "step_number": 1, "message_template": "hi", "delay_hours": 0,
            "conditions": {
                "on_keyword_match": {"keywords": ["interested"], "action": "tag_contact", "tag": "hot_lead"},
                "on_negative_keyword": {"keywords": ["stop", "not interested"], "action": "stop"},
            },
        },
        timeout=10,
    )
    # Enroll a real lead
    test_lead_id = f"test_lead_{uuid.uuid4().hex[:8]}"
    db["leads"].insert_one({
        "id": test_lead_id, "tenant_id": tenant_id, "name": "Reply Tester", "phone": "+12025550210",
    })
    try:
        requests.post(
            f"{API_URL}/api/outreach/campaigns/{cid}/enroll", headers=auth["headers"],
            json={"contact_ids": [test_lead_id]}, timeout=10,
        )
        # Positive keyword
        result = handle_inbound_reply(tenant_id, test_lead_id, "Yes I'm interested!")
        assert result["matched"] == 1
        ccs = db["contact_campaign_status"].find_one({
            "tenant_id": tenant_id, "campaign_id": cid, "contact_id": test_lead_id,
        })
        assert ccs["status"] == "hot_lead"
        assert "hot_lead" in ccs.get("tags", [])

        log = db["outreach_campaign_logs"].find_one({
            "tenant_id": tenant_id, "campaign_id": cid, "contact_id": test_lead_id,
            "action": "keyword_match",
        })
        assert log is not None
    finally:
        db["leads"].delete_one({"id": test_lead_id})


def test_handle_inbound_reply_negative_keyword_stops(auth):
    from routes.outreach import handle_inbound_reply
    tenant_id = auth["tenant_id"]
    r = requests.post(f"{API_URL}/api/outreach/campaigns", headers=auth["headers"], json={"name": "Neg kw test"}, timeout=10)
    cid = r.json()["id"]
    requests.post(
        f"{API_URL}/api/outreach/campaigns/{cid}/touchpoints",
        headers=auth["headers"],
        json={
            "step_number": 1, "message_template": "hi", "delay_hours": 0,
            "conditions": {
                "on_negative_keyword": {"keywords": ["not interested", "stop"], "action": "stop"},
            },
        },
        timeout=10,
    )
    test_lead_id = f"test_lead_{uuid.uuid4().hex[:8]}"
    db["leads"].insert_one({
        "id": test_lead_id, "tenant_id": tenant_id, "name": "Neg Tester", "phone": "+12025550211",
    })
    try:
        requests.post(
            f"{API_URL}/api/outreach/campaigns/{cid}/enroll", headers=auth["headers"],
            json={"contact_ids": [test_lead_id]}, timeout=10,
        )
        result = handle_inbound_reply(tenant_id, test_lead_id, "please stop, not interested")
        assert result["matched"] == 1
        ccs = db["contact_campaign_status"].find_one({
            "tenant_id": tenant_id, "contact_id": test_lead_id,
        })
        assert ccs["status"] == "completed"
    finally:
        db["leads"].delete_one({"id": test_lead_id})


def test_outreach_analytics_endpoint(auth):
    r = requests.post(f"{API_URL}/api/outreach/campaigns", headers=auth["headers"], json={"name": "Analytics"}, timeout=10)
    cid = r.json()["id"]
    requests.post(
        f"{API_URL}/api/outreach/campaigns/{cid}/touchpoints",
        headers=auth["headers"],
        json={"step_number": 1, "message_template": "step 1", "delay_hours": 0},
        timeout=10,
    )
    requests.post(
        f"{API_URL}/api/outreach/campaigns/{cid}/touchpoints",
        headers=auth["headers"],
        json={"step_number": 2, "message_template": "step 2", "delay_hours": 24},
        timeout=10,
    )
    a = requests.get(f"{API_URL}/api/outreach/campaigns/{cid}/analytics", headers=auth["headers"], timeout=10)
    assert a.status_code == 200
    data = a.json()
    assert data["campaign_id"] == cid
    assert len(data["by_step"]) == 2
    for row in data["by_step"]:
        for key in ("step_number", "sent", "reached", "replied", "stopped", "reply_rate_pct"):
            assert key in row


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
