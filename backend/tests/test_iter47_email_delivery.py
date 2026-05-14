"""Iter47 — email_delivery wrapper + landing-page contact form regression tests.

Covers:
  - POST /api/auth/email-code/request returns delivery_status='test_mode_forwarded' + forwarded_to
  - POST /api/auth/password/forgot returns the same wrapped shape
  - POST /api/contact/request persists + forwards
  - email_delivery_log collection records every send attempt
"""
import os
import time
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "genleadai_lms")
FALLBACK = "meghaagarwaljain2015@gmail.com"

client = MongoClient(MONGO_URL)
db = client[DB_NAME]


@pytest.fixture(autouse=True)
def _clean_rate_limit_rows():
    # Clear rate-limit rows so each test starts fresh
    db["auth_code_requests"].delete_many({"email": "admin@demo.com"})
    db["contact_rate_limit"].delete_many({"email": {"$regex": "^test_iter47"}})
    yield


# ── auth-extras wrapped shape ──────────────────────────────────────────
class TestEmailCodeRequestWrapped:
    def test_email_code_returns_delivery_status(self):
        before = db["email_delivery_log"].count_documents({})
        r = requests.post(f"{BASE_URL}/api/auth/email-code/request",
                          json={"email": "admin@demo.com"}, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["delivery_status"] in ("sent", "test_mode_forwarded"), body
        if body["delivery_status"] == "test_mode_forwarded":
            assert body.get("forwarded_to", "").lower() == FALLBACK.lower()
            assert body["delivered"] is True
        # A new email_delivery_log doc should have been created
        after = db["email_delivery_log"].count_documents({})
        assert after >= before + 1


class TestPasswordForgotWrapped:
    def test_forgot_returns_delivery_status(self):
        r = requests.post(f"{BASE_URL}/api/auth/password/forgot",
                          json={"email": "admin@demo.com"}, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["delivery_status"] in ("sent", "test_mode_forwarded"), body
        if body["delivery_status"] == "test_mode_forwarded":
            assert body.get("forwarded_to", "").lower() == FALLBACK.lower()


# ── contact endpoint ───────────────────────────────────────────────────
class TestContactRequest:
    def test_contact_persists_and_forwards(self):
        email = f"test_iter47_{int(time.time())}@example.com"
        payload = {
            "name": "Iter47 Tester",
            "email": email,
            "company": "TestCo",
            "message": "Please reach out about Aria — automated test.",
            "page": "landing",
        }
        r = requests.post(f"{BASE_URL}/api/contact/request", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

        # Persistence
        doc = db["contact_requests"].find_one({"email": email})
        assert doc is not None
        assert doc["name"] == "Iter47 Tester"
        assert doc["page"] == "landing"
        assert doc["status"] == "new"

        # Email delivery log should contain a contact_request forward
        time.sleep(0.5)
        latest = list(db["email_delivery_log"].find({}).sort("created_at", -1).limit(5))
        # at least one record near now mentions [Aria contact] or fallback target
        assert any("Aria contact" in (r.get("subject") or "") for r in latest), latest


# ── email_delivery_log shape ───────────────────────────────────────────
class TestEmailDeliveryLog:
    def test_log_doc_shape(self):
        # Trigger one send
        requests.post(f"{BASE_URL}/api/auth/email-code/request",
                      json={"email": "admin@demo.com"}, timeout=20)
        latest = db["email_delivery_log"].find_one({}, sort=[("created_at", -1)])
        assert latest is not None
        for key in ("to", "subject", "delivery_status", "created_at"):
            assert key in latest, f"missing {key} in {latest}"
        assert latest["delivery_status"] in ("sent", "test_mode_forwarded", "failed", "skipped")
