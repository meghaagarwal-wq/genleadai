"""iter114 Batch 4 — Multi-Platform Crawl + Intel Service tests.

Covers:
  - Health + Auth smoke
  - INTEL: GET /api/intel/{lead_id} (empty)
  - INTEL: GET /api/intel/{lead_id}/budget
  - INTEL: POST /api/intel/{lead_id}/research with no keys → 503
  - INTEL: POST /api/intel/{lead_id}/playbook / compose → 400 (no profile)
  - INTEL: compose schema validation across whatsapp/email/linkedin
  - INTEL: profile seeded → GET shape + playbook persists + compose returns shape
  - INTEL: budget cap exhausted → 429
  - Architectural V10 grep guard
"""
import os
import subprocess
import time
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fall back to public URL inside frontend/.env (test agent only)
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

LEAD_ID = "ptl_c41810995a20"
TENANT_ID = "ten_pietential"


def _mongo():
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "test_database")
    return MongoClient(mongo_url)[db_name]


@pytest.fixture(scope="session")
def db_client():
    return _mongo()


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@demo.com", "password": "Demo1234!"},
        timeout=20,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return r.json()["token"]


@pytest.fixture(scope="session")
def auth_headers(admin_token):
    return {
        "Authorization": f"Bearer {admin_token}",
        "X-Tenant-Id": TENANT_ID,
        "Content-Type": "application/json",
    }


@pytest.fixture(scope="session")
def real_lead_id(db_client):
    """Resolve pt_lead id in ten_pietential. Falls back to first pt_lead."""
    doc = db_client["pt_leads"].find_one({"id": LEAD_ID, "tenant_id": TENANT_ID})
    if doc:
        return LEAD_ID
    any_doc = db_client["pt_leads"].find_one({"tenant_id": TENANT_ID})
    assert any_doc, "no pt_leads in ten_pietential"
    return any_doc["id"]


@pytest.fixture(autouse=True)
def _cleanup_intel(db_client, real_lead_id):
    """Clean intel_profiles + crawl log between tests so order does not matter."""
    db_client["intel_profiles"].delete_many({"tenant_id": TENANT_ID, "lead_id": real_lead_id})
    db_client["prospect_crawl_log"].delete_many({"tenant_id": TENANT_ID, "lead_id": real_lead_id})
    yield
    db_client["intel_profiles"].delete_many({"tenant_id": TENANT_ID, "lead_id": real_lead_id})
    db_client["prospect_crawl_log"].delete_many({"tenant_id": TENANT_ID, "lead_id": real_lead_id})


# ─── Smoke ───
def test_health():
    r = requests.get(f"{BASE_URL}/api/health", timeout=15)
    assert r.status_code == 200


def test_login_returns_token(admin_token):
    assert isinstance(admin_token, str) and len(admin_token) > 10


# ─── Intel: empty state ───
def test_get_intel_empty(auth_headers, real_lead_id):
    r = requests.get(f"{BASE_URL}/api/intel/{real_lead_id}", headers=auth_headers, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {"profile": None, "exists": False} or (
        body.get("exists") is False and body.get("profile") is None
    )


def test_get_intel_budget_fresh(auth_headers, real_lead_id):
    r = requests.get(f"{BASE_URL}/api/intel/{real_lead_id}/budget", headers=auth_headers, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cap"] == 8
    assert body["calls_used"] == 0
    assert body["calls_remaining"] == 8
    assert body["by_source"] == {}


# ─── Intel: research without keys → 503 ───
def test_research_missing_credentials_returns_503(auth_headers, real_lead_id, db_client):
    # Ensure no proxycurl/serper keys are configured for this tenant
    db_client["integration_configs"].delete_many(
        {"tenant_id": TENANT_ID, "integration_type": {"$in": ["proxycurl", "serper"]}}
    )
    r = requests.post(
        f"{BASE_URL}/api/intel/{real_lead_id}/research",
        headers=auth_headers,
        json={"refresh": False},
        timeout=30,
    )
    assert r.status_code == 503, f"expected 503, got {r.status_code}: {r.text[:300]}"
    detail = r.json().get("detail", "")
    assert "/app/integrations" in detail.lower() or "integrations" in detail.lower()


# ─── Intel: playbook / compose without profile → 400 ───
def test_playbook_without_profile_400(auth_headers, real_lead_id):
    r = requests.post(
        f"{BASE_URL}/api/intel/{real_lead_id}/playbook",
        headers=auth_headers,
        json={},
        timeout=15,
    )
    assert r.status_code == 400, r.text
    assert "No intel profile yet" in r.json()["detail"]


def test_compose_without_profile_400(auth_headers, real_lead_id):
    r = requests.post(
        f"{BASE_URL}/api/intel/{real_lead_id}/compose",
        headers=auth_headers,
        json={"channel": "email"},
        timeout=15,
    )
    assert r.status_code == 400, r.text
    assert "No intel profile yet" in r.json()["detail"]


@pytest.mark.parametrize("channel", ["whatsapp", "email", "linkedin"])
def test_compose_channel_schema_validation(auth_headers, real_lead_id, channel):
    """Schema accepts all 3 channels; without profile still 400 (not 422)."""
    r = requests.post(
        f"{BASE_URL}/api/intel/{real_lead_id}/compose",
        headers=auth_headers,
        json={"channel": channel},
        timeout=15,
    )
    assert r.status_code == 400, f"channel={channel} got {r.status_code}: {r.text[:200]}"


# ─── Intel: seeded profile flows ───
def _seed_profile(db, lead_id):
    db["intel_profiles"].update_one(
        {"tenant_id": TENANT_ID, "lead_id": lead_id},
        {"$set": {
            "tenant_id": TENANT_ID,
            "lead_id": lead_id,
            "summary": "Seeded profile for iter114 test.",
            "signals": [
                {"type": "intent", "label": "Looking for CRM", "evidence": "Posted on LinkedIn", "confidence": "high", "source": "linkedin"},
                {"type": "growth", "label": "Hiring 5 reps", "evidence": "Open roles", "confidence": "med", "source": "web"},
            ],
            "interests": ["sales automation", "AI"],
            "risk_flags": [{"label": "no budget owner", "severity": "low", "reason": "title=IC"}],
            "buying_authority": {"role_seniority": "manager", "decision_maker_likelihood": 55},
            "fit_score": 72,
            "best_hook": "Saw your hiring spree for 5 SDRs.",
            "crawl_meta": {"sources_attempted": ["serper"], "sources_succeeded": ["serper"], "calls_made": 2, "errors": []},
            "updated_at": "2026-01-01T00:00:00Z",
        }, "$setOnInsert": {"created_at": "2026-01-01T00:00:00Z"}},
        upsert=True,
    )


def test_get_intel_with_seeded_profile(auth_headers, real_lead_id, db_client):
    _seed_profile(db_client, real_lead_id)
    r = requests.get(f"{BASE_URL}/api/intel/{real_lead_id}", headers=auth_headers, timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert body["exists"] is True
    p = body["profile"]
    assert p["fit_score"] == 72
    assert len(p["signals"]) >= 2
    assert p["risk_flags"][0]["label"] == "no budget owner"
    assert "interests" in p
    # _id must NOT be present
    assert "_id" not in p


def test_playbook_with_seeded_profile(auth_headers, real_lead_id, db_client):
    _seed_profile(db_client, real_lead_id)
    r = requests.post(
        f"{BASE_URL}/api/intel/{real_lead_id}/playbook",
        headers=auth_headers,
        json={},
        timeout=90,
    )
    assert r.status_code == 200, f"playbook: {r.status_code} {r.text[:400]}"
    pb = r.json()["playbook"]
    assert "recommended_channel" in pb
    # Persisted?
    doc = db_client["intel_profiles"].find_one({"tenant_id": TENANT_ID, "lead_id": real_lead_id})
    assert doc is not None and "playbook" in doc


@pytest.mark.parametrize("channel", ["whatsapp", "email", "linkedin"])
def test_compose_with_seeded_profile_shapes(auth_headers, real_lead_id, db_client, channel):
    _seed_profile(db_client, real_lead_id)
    r = requests.post(
        f"{BASE_URL}/api/intel/{real_lead_id}/compose",
        headers=auth_headers,
        json={"channel": channel},
        timeout=90,
    )
    assert r.status_code == 200, f"compose {channel}: {r.status_code} {r.text[:400]}"
    body = r.json()
    assert body["channel"] == channel
    assert "ai_powered" in body
    if channel == "email":
        msg = body["message"]
        assert isinstance(msg, dict)
        assert "subject" in msg and "body" in msg
    else:
        assert isinstance(body["message"], str) and len(body["message"]) > 0


# ─── Crawl budget cap → 429 ───
def test_research_budget_cap_429(auth_headers, real_lead_id, db_client):
    # Seed both crawl log at 8 AND fake credentials so the budget check fires
    # (planning needs ≥1 source configured to reach _assert_budget)
    db_client["prospect_crawl_log"].update_one(
        {"tenant_id": TENANT_ID, "lead_id": real_lead_id},
        {"$set": {
            "tenant_id": TENANT_ID, "lead_id": real_lead_id,
            "call_count": 8, "by_source": {"serper_web": 8},
            "updated_at": "2026-01-01T00:00:00Z",
        }, "$setOnInsert": {"created_at": "2026-01-01T00:00:00Z"}},
        upsert=True,
    )
    # Insert a fake serper integration_config (encrypted) so crawl planning sees it
    # Use the same Fernet encryption as security.encryption.encrypt
    import sys
    sys.path.insert(0, "/app/backend")
    from security.encryption import encrypt  # noqa: E402
    db_client["integration_configs"].update_one(
        {"tenant_id": TENANT_ID, "integration_type": "serper"},
        {"$set": {
            "tenant_id": TENANT_ID, "integration_type": "serper",
            "status": "connected",
            "config": {"api_key": encrypt("fake-serper-key-for-budget-test")},
        }},
        upsert=True,
    )
    try:
        r = requests.post(
            f"{BASE_URL}/api/intel/{real_lead_id}/research",
            headers=auth_headers,
            json={"refresh": True},
            timeout=30,
        )
        assert r.status_code == 429, f"expected 429, got {r.status_code}: {r.text[:300]}"
        assert "cap" in r.json()["detail"].lower() or "limit" in r.json()["detail"].lower()
    finally:
        db_client["integration_configs"].delete_many(
            {"tenant_id": TENANT_ID, "integration_type": "serper"}
        )


# ─── Architectural V10 rule ───
def test_v10_no_direct_llmchat_in_intel_files():
    paths = [
        "/app/backend/services/crawl_service.py",
        "/app/backend/services/intel_service.py",
        "/app/backend/routes/intel.py",
    ]
    pattern = r"LlmChat|UserMessage|with_model|emergentintegrations\.llm\.chat|anthropic\.messages"
    res = subprocess.run(
        ["grep", "-rE", pattern, *paths],
        capture_output=True, text=True,
    )
    assert res.returncode != 0, f"V10 violated:\n{res.stdout}"
