"""
ARIA Iter117 Batch 5 — Morning Brief cron + Compose-and-Send dispatch tests.
Tests: Morning Brief endpoints (config/send-now/last) + intel/compose-and-send for email/whatsapp/linkedin.
"""
import os
import pytest
import requests
from pymongo import MongoClient
from datetime import datetime, timezone

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASS = "Demo1234!"
TENANT = "ten_pietential"
LEAD_ID = "ptl_c41810995a20"


@pytest.fixture(scope="module")
def db():
    # Read DB_NAME from backend .env to ensure parity
    import re
    try:
        with open("/app/backend/.env") as f:
            content = f.read()
        m = re.search(r"^DB_NAME=(.+)$", content, re.MULTILINE)
        dbn = m.group(1).strip().strip('"').strip("'") if m else DB_NAME
        m2 = re.search(r"^MONGO_URL=(.+)$", content, re.MULTILINE)
        mongo = m2.group(1).strip().strip('"').strip("'") if m2 else MONGO_URL
    except Exception:
        dbn = DB_NAME
        mongo = MONGO_URL
    client = MongoClient(mongo)
    yield client[dbn]
    client.close()


@pytest.fixture(scope="module")
def auth_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    token = r.json().get("token") or r.json().get("access_token")
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": TENANT, "Content-Type": "application/json"}


@pytest.fixture(scope="module", autouse=True)
def seed_intel_profile(db):
    """Seed intel profile for the lead before tests."""
    db.intel_profiles.update_one(
        {"tenant_id": TENANT, "lead_id": LEAD_ID},
        {"$set": {
            "summary": "Test summary",
            "signals": [{"type": "intent", "label": "X", "evidence": "Y", "confidence": "med", "source": "inferred"}],
            "interests": ["B2B"],
            "risk_flags": [],
            "fit_score": 72,
            "best_hook": "X",
            "buying_authority": {"role_seniority": "vp", "decision_maker_likelihood": 70},
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    yield


# ───────────────── Health ─────────────────
def test_health():
    r = requests.get(f"{BASE_URL}/api/health")
    assert r.status_code == 200


# ─────────── Morning Brief Config GET ───────────
def test_morning_brief_config_get(auth_headers):
    r = requests.get(f"{BASE_URL}/api/aria/morning-brief/config", headers=auth_headers)
    assert r.status_code == 200, r.text
    cfg = r.json()
    # Default values when not configured yet
    assert "enabled" in cfg
    assert cfg.get("send_hour_local", 8) == 8
    assert cfg.get("weekdays_only", True) is True


# ─────────── Morning Brief Config POST (persist) ───────────
def test_morning_brief_config_post_and_persist(auth_headers):
    payload = {
        "enabled": True,
        "send_to_email": "founder@example.com",
        "send_hour_local": 8,
        "timezone_offset_hours": 5.5,
        "weekdays_only": True,
        "max_new_intel": 5,
    }
    r = requests.post(f"{BASE_URL}/api/aria/morning-brief/config", json=payload, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json().get("saved") is True

    # Verify persistence via GET
    r2 = requests.get(f"{BASE_URL}/api/aria/morning-brief/config", headers=auth_headers)
    assert r2.status_code == 200
    cfg = r2.json()
    assert cfg.get("enabled") is True
    assert cfg.get("send_to_email") == "founder@example.com"
    assert cfg.get("max_new_intel") == 5


# ─────────── Morning Brief Send Now ───────────
def test_morning_brief_send_now(auth_headers, db):
    r = requests.post(f"{BASE_URL}/api/aria/morning-brief/send-now", headers=auth_headers, json={})
    assert r.status_code != 500, f"Must not 500: {r.text}"
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, dict)
    # Either sent:true (provider_id present) OR sent:false (error string)
    assert "sent" in body
    if body.get("sent") is False:
        # Acceptable: error string returned (e.g., Resend sandbox restriction)
        assert "error" in body or "reason" in body or "note" in body

    # Verify persistence in aria_morning_brief_sent
    doc = db.aria_morning_brief_sent.find_one({"tenant_id": TENANT}, sort=[("_id", -1)])
    assert doc is not None, "No record persisted in aria_morning_brief_sent"


# ─────────── Morning Brief Last ───────────
def test_morning_brief_last(auth_headers):
    r = requests.get(f"{BASE_URL}/api/aria/morning-brief/last", headers=auth_headers)
    assert r.status_code == 200, r.text
    doc = r.json()
    # Must have subject/draft_count/enriched_count keys, no _id leak
    assert "_id" not in doc
    for key in ("subject", "draft_count", "enriched_count"):
        assert key in doc, f"Missing key {key} in {doc.keys()}"


# ─────────── Intel compose-and-send: Email Draft Only ───────────
def test_intel_compose_email_draft(auth_headers):
    r = requests.post(
        f"{BASE_URL}/api/intel/{LEAD_ID}/compose-and-send",
        json={"channel": "email", "auto_send": False},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "composed" in body
    composed = body["composed"]
    assert composed.get("channel") == "email"
    assert "message" in composed
    msg = composed["message"]
    assert "subject" in msg and "body" in msg
    assert "ai_powered" in composed
    assert body.get("dispatch") is None


# ─────────── Intel compose-and-send: Email Auto-Send ───────────
def test_intel_compose_email_auto_send(auth_headers, db):
    r = requests.post(
        f"{BASE_URL}/api/intel/{LEAD_ID}/compose-and-send",
        json={"channel": "email", "auto_send": True},
        headers=auth_headers,
    )
    assert r.status_code != 500, f"Must not 500: {r.text}"
    assert r.status_code == 200, r.text
    body = r.json()
    assert "composed" in body and "dispatch" in body
    dispatch = body["dispatch"]
    assert dispatch is not None
    assert "sent" in dispatch
    # If Resend rejects (sandbox), sent must be false and error string present
    if dispatch.get("sent") is False:
        assert "error" in dispatch and isinstance(dispatch["error"], str)

    # Verify outbound_log entry
    log = db.outbound_log.find_one(
        {"tenant_id": TENANT, "lead_id": LEAD_ID, "channel": "email"},
        sort=[("_id", -1)],
    )
    assert log is not None, "No outbound_log entry for email"
    for k in ("tenant_id", "lead_id", "channel", "provider", "sent", "ai_powered"):
        assert k in log, f"outbound_log missing field {k}"


# ─────────── Intel compose-and-send: WhatsApp (no phone) ───────────
def test_intel_compose_whatsapp_no_phone(auth_headers, db):
    # Ensure lead has no phone
    db.pt_leads.update_one(
        {"id": LEAD_ID, "tenant_id": TENANT},
        {"$unset": {"phone": "", "whatsapp": "", "mobile": ""}},
    )
    r = requests.post(
        f"{BASE_URL}/api/intel/{LEAD_ID}/compose-and-send",
        json={"channel": "whatsapp", "auto_send": True},
        headers=auth_headers,
    )
    assert r.status_code != 500
    assert r.status_code == 200, r.text
    body = r.json()
    dispatch = body.get("dispatch")
    assert dispatch is not None
    assert dispatch.get("sent") is False
    err = (dispatch.get("error") or "").lower()
    assert "phone" in err or "whatsapp" in err, f"Expected 'no phone/whatsapp' error, got: {err}"


# ─────────── Intel compose-and-send: LinkedIn (no OAuth) ───────────
def test_intel_compose_linkedin_no_oauth(auth_headers, db):
    r = requests.post(
        f"{BASE_URL}/api/intel/{LEAD_ID}/compose-and-send",
        json={"channel": "linkedin", "auto_send": True},
        headers=auth_headers,
    )
    assert r.status_code != 500
    assert r.status_code == 200, r.text
    body = r.json()
    dispatch = body.get("dispatch")
    assert dispatch is not None
    assert dispatch.get("logged_only") is True, f"Expected logged_only=True, got: {dispatch}"
    assert dispatch.get("provider") == "pending_outreach"
    note = (dispatch.get("note") or "").lower()
    assert "/app/integrations" in note or "integrations" in note

    # Verify pending_outreach record
    pending = db.pending_outreach.find_one(
        {"tenant_id": TENANT, "lead_id": LEAD_ID, "channel": "linkedin"},
        sort=[("_id", -1)],
    )
    assert pending is not None, "No pending_outreach entry for linkedin"


# ─────────── Outbound log integration check ───────────
def test_outbound_log_has_entries(db):
    cnt = db.outbound_log.count_documents({"tenant_id": TENANT, "lead_id": LEAD_ID})
    assert cnt >= 1, f"outbound_log should have at least 1 entry, got {cnt}"
