"""Iter46 — Auth extras (forgot password + email-code login) backend tests.

Inspects MongoDB auth_codes + auth_code_requests collections directly to verify
hashing, rate-limiting, attempt cap and TTL behaviour without relying on real
Resend email delivery (which is in dev/test mode).
"""
import os
import time
from datetime import datetime, timedelta

import bcrypt
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "genleadai_lms"

ADMIN_EMAIL = "admin@demo.com"
ADMIN_PWD = "Demo1234!"


# ─── Fixtures ────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def db():
    client = MongoClient(MONGO_URL)
    return client[DB_NAME]


@pytest.fixture
def clean_email_state(db):
    """Clear codes + request rate-limit rows for admin@demo.com before each test."""
    db["auth_codes"].delete_many({"email": ADMIN_EMAIL})
    db["auth_code_requests"].delete_many({"email": ADMIN_EMAIL})
    yield
    # leave state for inspection; next test will clean


@pytest.fixture
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _ensure_admin_password(db, api):
    """Make sure admin can still log in with Demo1234! at end of suite."""
    r = api.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PWD})
    if r.status_code == 200:
        return True
    # Restore via forgot/reset trick
    api.post(f"{BASE_URL}/api/auth/password/forgot", json={"email": ADMIN_EMAIL})
    new_hash = bcrypt.hashpw(b"TESTCODE123", bcrypt.gensalt()).decode()
    db["auth_codes"].update_one(
        {"email": ADMIN_EMAIL, "purpose": "password_reset"},
        {"$set": {"code_hash": new_hash, "attempts": 0}},
    )
    api.post(f"{BASE_URL}/api/auth/password/reset", json={"email": ADMIN_EMAIL, "code": "TESTCODE123", "new_password": ADMIN_PWD})


# ─── Forgot password ─────────────────────────────────────────────────────
class TestForgotPassword:
    def test_forgot_returns_200_and_inserts_doc(self, api, db, clean_email_state):
        r = api.post(f"{BASE_URL}/api/auth/password/forgot", json={"email": ADMIN_EMAIL})
        assert r.status_code == 200
        assert r.json() == {"ok": True}

        doc = db["auth_codes"].find_one({"email": ADMIN_EMAIL, "purpose": "password_reset"})
        assert doc is not None, "Code doc not inserted"
        assert doc["purpose"] == "password_reset"
        assert doc["attempts"] == 0
        assert doc["used"] is False
        assert doc["code_hash"].startswith("$2b$") or doc["code_hash"].startswith("$2a$"), "code_hash not bcrypt"
        # expires_at ~10 min from now
        exp = doc["expires_at"]
        now = datetime.utcnow()
        delta = (exp - now).total_seconds()
        assert 540 < delta < 660, f"expires_at off ({delta}s)"

    def test_forgot_unknown_email_still_returns_200(self, api, db):
        r = api.post(f"{BASE_URL}/api/auth/password/forgot", json={"email": "ghost-not-a-user@example.com"})
        assert r.status_code == 200
        assert r.json() == {"ok": True}
        # No code doc should be inserted for unknown email
        doc = db["auth_codes"].find_one({"email": "ghost-not-a-user@example.com"})
        assert doc is None


# ─── Email-code request ──────────────────────────────────────────────────
class TestEmailCodeRequest:
    def test_email_code_request_inserts_with_correct_purpose(self, api, db, clean_email_state):
        r = api.post(f"{BASE_URL}/api/auth/email-code/request", json={"email": ADMIN_EMAIL})
        assert r.status_code == 200
        assert r.json() == {"ok": True}
        doc = db["auth_codes"].find_one({"email": ADMIN_EMAIL, "purpose": "email_code"})
        assert doc is not None
        assert doc["purpose"] == "email_code"
        assert doc["attempts"] == 0
        assert doc["code_hash"].startswith("$2")


# ─── Happy path reset ────────────────────────────────────────────────────
class TestResetHappyPath:
    def test_full_reset_flow_via_mongo_hash_override(self, api, db, clean_email_state):
        # 1. Request a reset code
        r = api.post(f"{BASE_URL}/api/auth/password/forgot", json={"email": ADMIN_EMAIL})
        assert r.status_code == 200

        # 2. Replace the bcrypt hash with one we know plaintext for
        known_code = "TESTCODE123"
        new_hash = bcrypt.hashpw(known_code.encode(), bcrypt.gensalt()).decode()
        upd = db["auth_codes"].update_one(
            {"email": ADMIN_EMAIL, "purpose": "password_reset"},
            {"$set": {"code_hash": new_hash, "attempts": 0}},
        )
        assert upd.matched_count == 1

        # 3. POST reset with new password
        new_pwd = "NewPass123!"
        r = api.post(
            f"{BASE_URL}/api/auth/password/reset",
            json={"email": ADMIN_EMAIL, "code": known_code, "new_password": new_pwd},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is True
        assert "token" in data and isinstance(data["token"], str) and len(data["token"]) > 10
        assert data["user"]["email"] == ADMIN_EMAIL

        # 4. Login with new password should succeed
        r2 = api.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": new_pwd})
        assert r2.status_code == 200, f"Login with new pwd failed: {r2.text}"

        # 5. RESTORE original password
        api.post(f"{BASE_URL}/api/auth/password/forgot", json={"email": ADMIN_EMAIL})
        restore_hash = bcrypt.hashpw(b"RESTORE!", bcrypt.gensalt()).decode()
        db["auth_codes"].update_one(
            {"email": ADMIN_EMAIL, "purpose": "password_reset"},
            {"$set": {"code_hash": restore_hash, "attempts": 0}},
        )
        r3 = api.post(
            f"{BASE_URL}/api/auth/password/reset",
            json={"email": ADMIN_EMAIL, "code": "RESTORE!", "new_password": ADMIN_PWD},
        )
        assert r3.status_code == 200
        r4 = api.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PWD})
        assert r4.status_code == 200, "Failed to restore original admin password!"


# ─── Negative / security paths ───────────────────────────────────────────
class TestSecurity:
    def test_bad_code_returns_400(self, api, db, clean_email_state):
        api.post(f"{BASE_URL}/api/auth/password/forgot", json={"email": ADMIN_EMAIL})
        r = api.post(
            f"{BASE_URL}/api/auth/password/reset",
            json={"email": ADMIN_EMAIL, "code": "000000", "new_password": "Whatever123!"},
        )
        assert r.status_code == 400
        assert "Invalid or expired" in r.json().get("detail", "")

    def test_short_password_rejected(self, api, db, clean_email_state):
        api.post(f"{BASE_URL}/api/auth/password/forgot", json={"email": ADMIN_EMAIL})
        new_hash = bcrypt.hashpw(b"ABCDEF", bcrypt.gensalt()).decode()
        db["auth_codes"].update_one(
            {"email": ADMIN_EMAIL, "purpose": "password_reset"},
            {"$set": {"code_hash": new_hash, "attempts": 0}},
        )
        r = api.post(
            f"{BASE_URL}/api/auth/password/reset",
            json={"email": ADMIN_EMAIL, "code": "ABCDEF", "new_password": "short"},
        )
        assert r.status_code == 400
        assert "8 character" in r.json().get("detail", "").lower() or "8 character" in r.text.lower()

    def test_rate_limit_after_three_requests(self, api, db, clean_email_state):
        # First 3 each should produce a code doc (note: each request deletes prior, so we count requests)
        for _ in range(3):
            r = api.post(f"{BASE_URL}/api/auth/password/forgot", json={"email": ADMIN_EMAIL})
            assert r.status_code == 200
        count_before_4th = db["auth_code_requests"].count_documents({"email": ADMIN_EMAIL})
        assert count_before_4th == 3

        # 4th call still 200 but no new doc inserted (rate limit kicks in BEFORE _record_request)
        r = api.post(f"{BASE_URL}/api/auth/password/forgot", json={"email": ADMIN_EMAIL})
        assert r.status_code == 200
        assert r.json() == {"ok": True}
        count_after = db["auth_code_requests"].count_documents({"email": ADMIN_EMAIL})
        assert count_after == 3, f"Expected rate-limit to block 4th request but got {count_after} rows"

    def test_five_wrong_attempts_deletes_code(self, api, db, clean_email_state):
        # Issue a known code via mongo hash override
        api.post(f"{BASE_URL}/api/auth/password/forgot", json={"email": ADMIN_EMAIL})
        new_hash = bcrypt.hashpw(b"REAL123", bcrypt.gensalt()).decode()
        db["auth_codes"].update_one(
            {"email": ADMIN_EMAIL, "purpose": "password_reset"},
            {"$set": {"code_hash": new_hash, "attempts": 0}},
        )

        # 5 wrong attempts
        for i in range(5):
            r = api.post(
                f"{BASE_URL}/api/auth/password/reset",
                json={"email": ADMIN_EMAIL, "code": "WRONG!", "new_password": "Whatever123!"},
            )
            assert r.status_code == 400

        # 6th attempt — code should be auto-deleted, still 400
        r = api.post(
            f"{BASE_URL}/api/auth/password/reset",
            json={"email": ADMIN_EMAIL, "code": "REAL123", "new_password": "Whatever123!"},
        )
        assert r.status_code == 400
        # Confirm code doc is gone
        doc = db["auth_codes"].find_one({"email": ADMIN_EMAIL, "purpose": "password_reset"})
        assert doc is None, "Code should have been deleted after 5 failed attempts"


# ─── Final teardown ──────────────────────────────────────────────────────
def test_zz_final_password_restoration(api, db):
    """Last test — verifies admin can still log in with Demo1234!."""
    _ensure_admin_password(db, api)
    r = api.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PWD})
    assert r.status_code == 200, "Admin password is NOT Demo1234! at end of suite — review/restore manually"
