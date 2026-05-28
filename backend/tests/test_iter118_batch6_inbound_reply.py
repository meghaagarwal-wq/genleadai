"""Iter 118 Batch 6 — Inbound Reply Tracker tests.

Covers: webhook health, Resend inbound/bounce/unsubscribe/unmatched,
360dialog WhatsApp inbound + unmatched tenant, idempotency,
intel-aware drafting (no auto-send), bcrypt regression, V10 guard,
regression on prior batches.
"""
import os
import json
import subprocess
import time
import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or os.environ.get("PUBLIC_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback to local for in-cluster tests
    BASE_URL = "http://localhost:8001"

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


@pytest.fixture(scope="module")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_token(session):
    r = session.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@demo.com", "password": "Demo1234!"})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return r.json().get("token") or r.json().get("access_token")


# ─── PRECHECK ───
def test_check_v10_guard_passes():
    res = subprocess.run(["bash", "/app/scripts/check_v10.sh"], capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + res.stderr


def test_supervisor_loops_logged():
    out = subprocess.run(["bash", "-c", "cat /var/log/supervisor/backend.out.log"], capture_output=True, text=True).stdout
    assert "[InboundReply] LinkedIn comment poller started" in out
    assert "[MorningBrief] Background loop started" in out


# ─── BCRYPT regression ───
def test_bcrypt_no_passlib_about_error(session):
    # Clear err log first
    subprocess.run(["bash", "-c", ": > /var/log/supervisor/backend.err.log"], check=False)
    for _ in range(3):
        r = session.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@demo.com", "password": "Demo1234!"})
        assert r.status_code == 200
    time.sleep(1)
    res = subprocess.run(["bash", "-c", "grep -c '__about__' /var/log/supervisor/backend.err.log || true"], capture_output=True, text=True)
    count = int(res.stdout.strip() or "0")
    assert count == 0, f"passlib __about__ errors: {count}"


# ─── WEBHOOK HEALTH ───
def test_webhook_health(session):
    r = session.get(f"{BASE_URL}/api/webhooks/health")
    assert r.status_code == 200
    j = r.json()
    assert j.get("ok") is True
    assert "resend" in j["providers"]
    assert "360dialog" in j["providers"]
    assert "linkedin_polling" in j["providers"]


# ─── RESEND inbound ───
def test_resend_inbound_match_and_qualify(session, db):
    payload = {
        "type": "email.received",
        "data": {
            "id": "rec_b6_001",
            "from": "reply.tester@example.com",
            "to": ["x@y.com"],
            "subject": "I am interested, can we chat?",
        },
    }
    r = session.post(f"{BASE_URL}/api/webhooks/resend", json=payload)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("lead_id") == "ptl_replytest01"
    assert j.get("channel") == "email"
    assert j.get("stage_changed_to") == "replied"
    assert j.get("qualification", {}).get("intent") in ("interested", "positive", "neutral_followup", "unclear")
    # Verify Mongo persistence
    assert db.inbound_messages.find_one({"external_id": "rec_b6_001"}) is not None
    assert db.activities.find_one({"metadata.external_id": "rec_b6_001", "activity_type": "inbound_reply"}) is not None
    lead = db.pt_leads.find_one({"id": "ptl_replytest01"})
    assert lead["stage"] == "replied"
    assert lead.get("prior_stage") == "engaged"


def test_resend_inbound_idempotent(session):
    payload = {
        "type": "email.received",
        "data": {"id": "rec_b6_001", "from": "reply.tester@example.com", "to": ["x@y.com"], "subject": "Dup"},
    }
    r = session.post(f"{BASE_URL}/api/webhooks/resend", json=payload)
    assert r.status_code == 200
    assert r.json().get("duplicate") is True


def test_resend_inbound_drafting(session, db):
    payload = {
        "type": "email.received",
        "data": {
            "id": "rec_b6_002",
            "from": "reply.tester@example.com",
            "to": ["x@y.com"],
            "subject": "What is timeline to onboard?",
        },
    }
    r = session.post(f"{BASE_URL}/api/webhooks/resend", json=payload, timeout=60)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("drafted") is True, j
    po = db.pending_outreach.find_one({"in_reply_to_external_id": "rec_b6_002"})
    assert po is not None
    assert po.get("status") == "awaiting_owner_approval"
    assert po.get("ai_powered") is True
    assert (po.get("body") or "") != ""


def test_resend_unsubscribe_no_draft(session, db):
    payload = {
        "type": "email.received",
        "data": {"id": "rec_b6_unsub", "from": "reply.tester@example.com", "to": ["x@y.com"], "subject": "Unsubscribe me"},
    }
    r = session.post(f"{BASE_URL}/api/webhooks/resend", json=payload, timeout=60)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("drafted") is False
    assert j.get("qualification", {}).get("intent") in ("unsubscribe", "not_interested")
    po = db.pending_outreach.find_one({"in_reply_to_external_id": "rec_b6_unsub"})
    assert po is None


def test_resend_bounce_matched(session, db):
    payload = {"type": "email.bounced", "data": {"email_id": "eid_xyz"}}
    r = session.post(f"{BASE_URL}/api/webhooks/resend", json=payload)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("event") == "email.bounced"
    assert j.get("lead_id") == "ptl_replytest01"
    a = db.activities.find_one({"activity_type": "email_bounced", "lead_id": "ptl_replytest01"})
    assert a is not None


def test_resend_bounce_unmatched(session):
    payload = {"type": "email.bounced", "data": {"email_id": "no_such_eid_404"}}
    r = session.post(f"{BASE_URL}/api/webhooks/resend", json=payload)
    assert r.status_code == 200
    assert r.json().get("matched") is False


def test_resend_unmatched_sender(session, db):
    payload = {
        "type": "email.received",
        "data": {"id": "rec_b6_unmatched", "from": "unknown@example.com", "to": ["x@y.com"], "subject": "hi"},
    }
    r = session.post(f"{BASE_URL}/api/webhooks/resend", json=payload)
    assert r.status_code == 200
    j = r.json()
    assert j.get("matched") is False
    rec = db.inbound_messages.find_one({"external_id": "rec_b6_unmatched"})
    assert rec is not None and rec.get("unmatched") is True


# ─── WhatsApp 360dialog ───
def test_whatsapp_inbound_match(session, db):
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "metadata": {"phone_number_id": "PNID_TEST_001"},
                    "messages": [{
                        "id": "wa_b6_001",
                        "from": "919999999999",
                        "type": "text",
                        "text": {"body": "Yes, please share timeline."},
                    }],
                }
            }]
        }]
    }
    r = session.post(f"{BASE_URL}/api/webhooks/360dialog", json=payload, timeout=60)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("ok") is True
    results = j.get("results", [])
    assert len(results) == 1
    assert results[0].get("lead_id") == "ptl_replytest01"
    assert db.inbound_messages.find_one({"external_id": "wa_b6_001"}) is not None
    # idempotency
    r2 = session.post(f"{BASE_URL}/api/webhooks/360dialog", json=payload)
    assert r2.status_code == 200
    assert r2.json()["results"][0].get("duplicate") is True


def test_whatsapp_unmatched_tenant(session):
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "metadata": {"phone_number_id": "PNID_DOES_NOT_EXIST"},
                    "messages": [{
                        "id": f"wa_b6_unknown_tenant_{int(time.time()*1000)}",
                        "from": "910000000000",
                        "type": "text",
                        "text": {"body": "Hi"},
                    }],
                }
            }]
        }]
    }
    r = session.post(f"{BASE_URL}/api/webhooks/360dialog", json=payload)
    assert r.status_code == 200, r.text
    # results either empty or matched:false; no 500
    results = r.json().get("results", [])
    if results:
        assert results[0].get("matched") is False


# ─── LinkedIn poller no-op ───
@pytest.mark.asyncio
async def test_linkedin_poll_once_no_op():
    from routes.inbound_reply import _poll_linkedin_once
    # Should not raise when no linkedin configs connected
    await _poll_linkedin_once()


# ─── REGRESSION ───
def test_login_returns_jwt(session):
    r = session.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@demo.com", "password": "Demo1234!"})
    assert r.status_code == 200
    j = r.json()
    assert (j.get("token") or j.get("access_token"))


def test_intel_compose_and_send_regression(session, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}", "X-Tenant-Id": "ten_pietential"}
    r = session.post(
        f"{BASE_URL}/api/intel/ptl_c41810995a20/compose-and-send",
        headers=headers,
        json={"channel": "email", "auto_send": False},
        timeout=90,
    )
    # Acceptable: 200 with composed message; or 404 if lead doesn't exist in this env
    assert r.status_code in (200, 404), r.text


def test_intel_batch_hot_leads_regression(session, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}", "X-Tenant-Id": "ten_pietential"}
    r = session.post(f"{BASE_URL}/api/intel/batch/hot-leads", headers=headers, json={}, timeout=120)
    assert r.status_code == 200, r.text


def test_morning_brief_send_now_no_500(session, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}", "X-Tenant-Id": "ten_pietential"}
    r = session.post(f"{BASE_URL}/api/aria/morning-brief/send-now", headers=headers, json={}, timeout=120)
    # sandbox-rejection is ok; any 2xx/4xx fine, never 500
    assert r.status_code != 500, r.text
