"""Iter120 Batch 8 — Approval Queue Digest (8 PM cron) backend tests.

Covers: config GET/POST, send-now (empty/singular/plural), last, HTML render validity.
"""
import os
import sys
import asyncio
from datetime import datetime, timezone

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = "Demo1234!"
PIETENTIAL_TENANT = "ten_pietential"

client = MongoClient(MONGO_URL)
db = client[DB_NAME]
pending_col = db["pending_outreach"]
sent_col = db["aria_approval_digest_sent"]
config_col = db["aria_approval_digest_config"]


# ─── Fixtures ───
@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def api(auth_token):
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {auth_token}",
        "X-Tenant-Id": PIETENTIAL_TENANT,
        "Content-Type": "application/json",
    })
    return s


@pytest.fixture(autouse=True)
def cleanup():
    # Clean any prior test drafts
    pending_col.delete_many({"meta_tag": "TEST_ITER120_"})
    yield
    pending_col.delete_many({"meta_tag": "TEST_ITER120_"})


def _wipe_queue():
    pending_col.delete_many({
        "tenant_id": PIETENTIAL_TENANT,
        "status": "awaiting_owner_approval",
    })


def _seed(channel="email", subject="Quick idea", body="Line one of preview\nLine two of preview\nLine three should be hidden"):
    doc = {
        "tenant_id": PIETENTIAL_TENANT,
        "lead_id": "ptl_replytest01",
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
        "meta_tag": "TEST_ITER120_",
    }
    pending_col.insert_one(doc)


# ─── Tests ───
class TestConfig:
    def test_get_config_returns_defaults(self, api):
        # Wipe any persisted config first
        config_col.delete_one({"tenant_id": PIETENTIAL_TENANT})
        r = api.get(f"{BASE_URL}/api/aria/approval-digest/config")
        assert r.status_code == 200, r.text
        data = r.json()
        # Spec defaults: enabled=false, send_hour_local=20
        assert data.get("enabled") is False
        assert data.get("send_hour_local") == 20
        assert data.get("weekdays_only") is False

    def test_post_config_persists(self, api):
        payload = {
            "enabled": True,
            "send_to_email": "founder@example.com",
            "send_hour_local": 20,
            "timezone_offset_hours": 5.5,
            "weekdays_only": False,
        }
        r = api.post(f"{BASE_URL}/api/aria/approval-digest/config", json=payload)
        assert r.status_code == 200, r.text
        assert r.json().get("saved") is True
        # Subsequent GET returns persisted
        r2 = api.get(f"{BASE_URL}/api/aria/approval-digest/config")
        d = r2.json()
        assert d["enabled"] is True
        assert d["send_to_email"] == "founder@example.com"
        assert d["send_hour_local"] == 20
        assert abs(d["timezone_offset_hours"] - 5.5) < 1e-6
        assert d["weekdays_only"] is False


class TestSendNow:
    def test_empty_queue_skip(self, api):
        _wipe_queue()
        # ensure recipient is set
        api.post(f"{BASE_URL}/api/aria/approval-digest/config", json={
            "enabled": True, "send_to_email": "founder@example.com",
            "send_hour_local": 20, "timezone_offset_hours": 5.5, "weekdays_only": False,
        })
        r = api.post(f"{BASE_URL}/api/aria/approval-digest/send-now")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("sent") is False
        assert data.get("skipped") is True
        assert data.get("reason") == "queue_empty"
        assert data.get("draft_count") == 0

    def test_plural_two_drafts(self, api):
        _wipe_queue()
        _seed(channel="email")
        _seed(channel="whatsapp")
        r = api.post(f"{BASE_URL}/api/aria/approval-digest/send-now")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("draft_count") == 2
        assert data.get("subject") == "[2] drafts waiting your review — ARIA"
        # Even on sandbox rejection: must contain sent, draft_count, subject, error keys
        for k in ("sent", "draft_count", "subject", "error"):
            assert k in data, f"missing key {k} in {data}"
        _wipe_queue()

    def test_singular_one_draft(self, api):
        _wipe_queue()
        _seed(channel="email")
        r = api.post(f"{BASE_URL}/api/aria/approval-digest/send-now")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("draft_count") == 1
        # Singular: no 's'
        assert data.get("subject") == "[1] draft waiting your review — ARIA"
        _wipe_queue()


class TestLast:
    def test_last_returns_most_recent(self, api):
        _wipe_queue()
        _seed(channel="email")
        api.post(f"{BASE_URL}/api/aria/approval-digest/send-now")
        r = api.get(f"{BASE_URL}/api/aria/approval-digest/last")
        assert r.status_code == 200, r.text
        d = r.json()
        assert "_id" not in d, "BSON _id leak"
        for k in ("subject", "draft_count", "sent"):
            assert k in d, f"missing {k}"
        # error key may be present and could be None
        assert "error" in d
        _wipe_queue()


class TestHtmlValidity:
    def test_run_approval_digest_html(self):
        """Directly invoke run_approval_digest() and inspect the rendered HTML."""
        sys.path.insert(0, "/app/backend")
        from routes.aria_approval_digest import run_approval_digest, _render_digest_html, _enrich, _tenant_meta

        _wipe_queue()
        _seed(channel="email", subject="Test Subject", body="First preview line\nSecond preview line\nHidden third line")
        _seed(channel="whatsapp", body="WA line one\nWA line two")

        # Render html directly via the same helper used in run_approval_digest
        pending = list(pending_col.find(
            {"tenant_id": PIETENTIAL_TENANT, "status": "awaiting_owner_approval"},
            {"_id": 0},
        ).sort("created_at", -1).limit(50))
        drafts = [_enrich(d) for d in pending]
        meta = _tenant_meta(PIETENTIAL_TENANT)
        html = _render_digest_html(meta, drafts)

        # (a) subject text fragment
        assert "draft" in html and "waiting your review" in html
        # (b) both CTA hrefs
        assert "?action=bulk-approve" in html
        assert "/app/approvals" in html
        # (c) one card per pending draft — check both bodies appear (line one)
        assert "First preview line" in html
        assert "WA line one" in html
        # signal hint
        assert "Send a calendar link" in html
        # 3rd hidden line must NOT appear (only first 2 lines)
        assert "Hidden third line" not in html
        # no broken placeholders
        assert "{" not in html.replace("{count}", "")  # raw f-string already filled
        # The cards block uses literal '{' only inside style strings — let's check
        # for undefined-template markers more loosely:
        assert "undefined" not in html.lower()
        _wipe_queue()
