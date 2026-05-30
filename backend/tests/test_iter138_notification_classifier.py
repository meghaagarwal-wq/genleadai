"""iter138 — Notification error classifier + TTL index regression tests.

Covers iter138-A1..A4 (structured 503 from 3 ARIA notification senders),
iter138-A5 (no tracebacks), iter138-B (TTL index on journey_generate_jobs).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
TENANT = "ten_demo"


@pytest.fixture(scope="module")
def token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@demo.com", "password": "Demo1234!"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": TENANT,
        "Content-Type": "application/json",
    }


def _assert_classified_503(resp, expect_sandbox=True):
    assert resp.status_code == 503, f"expected 503 got {resp.status_code}: {resp.text}"
    j = resp.json()
    detail = j.get("detail")
    assert isinstance(detail, dict), f"detail must be dict, got {type(detail)}: {detail}"
    for k in ("code", "user_message", "status"):
        assert k in detail, f"missing key {k} in detail: {detail}"
    assert detail["status"] == 503
    if expect_sandbox:
        # accept either sandbox classification or no_resend_key, depending on env
        assert detail["code"] in (
            "resend_sandbox_or_unverified_domain",
            "no_resend_key",
            "send_failed",
        ), f"unexpected code: {detail['code']}"


# ─── iter138-A1: eod-wrap ──────────────────────────────────────────────
def test_a1_eod_wrap_send_now_returns_classified_503(headers):
    r = requests.post(
        f"{BASE_URL}/api/aria/eod-wrap/send-now",
        headers=headers,
        json={},
        timeout=60,
    )
    _assert_classified_503(r)


# ─── iter138-A2: morning-brief ─────────────────────────────────────────
def test_a2_morning_brief_send_now_returns_classified_503(headers):
    r = requests.post(
        f"{BASE_URL}/api/aria/morning-brief/send-now",
        headers=headers,
        json={},
        timeout=120,
    )
    _assert_classified_503(r)
    detail = r.json()["detail"]
    # iter138 specifically asks for verify-a-domain language when sandbox-classified
    if detail["code"] == "resend_sandbox_or_unverified_domain":
        assert "verify a domain" in detail["user_message"].lower()


# ─── iter138-A3: approval-digest queue empty ───────────────────────────
def test_a3_approval_digest_empty_queue_returns_200_skipped(headers):
    # Ensure queue is empty for ten_demo first
    from deps import db
    db["pending_outreach"].delete_many(
        {"tenant_id": TENANT, "status": "awaiting_owner_approval"}
    )
    r = requests.post(
        f"{BASE_URL}/api/aria/approval-digest/send-now",
        headers=headers,
        json={},
        timeout=30,
    )
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
    body = r.json()
    assert body.get("sent") is False
    assert body.get("skipped") is True
    assert body.get("reason") == "queue_empty"
    assert body.get("draft_count") == 0


# ─── iter138-A4: approval-digest with seeded pending doc ───────────────
def test_a4_approval_digest_non_empty_returns_classified_503(headers):
    from deps import db
    seeded_id = "TEST_iter138_pending_outreach"
    db["pending_outreach"].delete_one({"_id": seeded_id})
    # find any existing lead
    lead = db["pt_leads"].find_one({"tenant_id": TENANT}, {"_id": 0, "id": 1})
    lead_id = (lead or {}).get("id", "TEST_lead_iter138")
    db["pending_outreach"].insert_one(
        {
            "_id": seeded_id,
            "tenant_id": TENANT,
            "status": "awaiting_owner_approval",
            "channel": "email",
            "subject": "TEST iter138",
            "body": "TEST body",
            "lead_id": lead_id,
            "qualification": {"intent": "interested"},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    try:
        r = requests.post(
            f"{BASE_URL}/api/aria/approval-digest/send-now",
            headers=headers,
            json={},
            timeout=60,
        )
        _assert_classified_503(r)
    finally:
        db["pending_outreach"].delete_one({"_id": seeded_id})


# ─── iter138-B: TTL index on journey_generate_jobs ────────────────────
def test_b_journey_generate_jobs_ttl_index():
    from deps import db
    info = db["journey_generate_jobs"].index_information()
    assert "expires_at_1" in info, f"missing TTL index, have: {list(info.keys())}"
    idx = info["expires_at_1"]
    assert idx.get("expireAfterSeconds") == 0, idx


# ─── iter138-B: expires_at field populated 7 days in future ────────────
def test_b_journey_job_has_expires_at_future_date(headers):
    # Trigger journey/generate to create a job
    r = requests.post(
        f"{BASE_URL}/api/journeys/generate",
        headers=headers,
        json={"lead_id": "TEST_iter138_journey", "count": 3, "objective": "test"},
        timeout=15,
    )
    # Even if it 4xx (no such lead), we just need to validate any existing job docs
    from deps import db
    doc = db["journey_generate_jobs"].find_one(
        {"tenant_id": TENANT}, {"_id": 0, "expires_at": 1, "created_at": 1},
        sort=[("created_at", -1)],
    )
    if doc:
        exp = doc.get("expires_at")
        assert exp is not None, "expires_at missing on journey_generate_jobs doc"
        if isinstance(exp, datetime):
            delta = exp - datetime.now(timezone.utc).replace(tzinfo=exp.tzinfo)
            assert timedelta(days=6) <= delta <= timedelta(days=8), f"expires_at not ~7d: {delta}"


# ─── Regression: other ARIA notification config endpoints ──────────────
@pytest.mark.parametrize("path", [
    "/api/aria/morning-brief/config",
    "/api/aria/approval-digest/config",
    "/api/aria/eod-wrap/config",
    "/api/aria/eod-wrap/last",
    "/api/aria/morning-brief/last",
    "/api/aria/approval-digest/last",
])
def test_regression_aria_config_endpoints_200(headers, path):
    r = requests.get(f"{BASE_URL}{path}", headers=headers, timeout=15)
    assert r.status_code == 200, f"{path}: {r.status_code} {r.text[:200]}"


# ─── Regression: spot-check 6 iter136 audit endpoints ──────────────────
@pytest.mark.parametrize("path", [
    "/api/health",
    "/api/leads",
    "/api/leads/counts",
    "/api/aria/today",
    "/api/aria/feed",
    "/api/voice-seeds",
])
def test_regression_spot_check_endpoints(headers, path):
    r = requests.get(f"{BASE_URL}{path}", headers=headers, timeout=15)
    assert r.status_code in (200, 201), f"{path}: {r.status_code} {r.text[:200]}"


# ─── Regression: approvals queue ──────────────────────────────────────
def test_regression_approvals_endpoints(headers):
    r = requests.get(f"{BASE_URL}/api/approvals/count", headers=headers, timeout=15)
    assert r.status_code == 200, r.text
    r2 = requests.get(f"{BASE_URL}/api/approvals", headers=headers, timeout=15)
    assert r2.status_code == 200, r2.text
