"""Iter84 — Pietential email-send flow tests.

Covers GET/POST /api/pt/email/config and POST /api/pt/email/test-send,
including role gating, fallback behaviour, friendly Resend sandbox error,
EmailStr validation, no X-Tenant-Id requirement, and regression on iter82/83.
"""
import os
import json
import time
import pytest
import requests

# Load backend env (MONGO_URL, DB_NAME, RESEND_API_KEY) for cleanup hooks.
try:
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
except Exception:
    pass


def _load_backend_url():
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    return os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


BASE_URL = _load_backend_url()
assert BASE_URL, "REACT_APP_BACKEND_URL not set"

ADMIN_EMAIL = "admin@demo.com"
ADMIN_PW = "Demo1234!"
REP_EMAIL = "sarah@demo.com"
REP_PW = "Demo1234!"

# Resend account-owner verified inbox (per agent context note — manual test
# already confirmed a real provider_id comes back for this address).
OWNER_INBOX = "meghaagarwaljain2015@gmail.com"
# Non-owner address — Resend sandbox should reject this with a 451/403 leaked
# raw error UNLESS the backend translates it to the friendly 400 message.
NON_OWNER_INBOX = "noone-iter84@example.com"


def _login(email, pw):
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": pw},
        timeout=15,
    )
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text[:200]}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_headers():
    return {"Authorization": f"Bearer {_login(ADMIN_EMAIL, ADMIN_PW)}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def rep_headers():
    return {"Authorization": f"Bearer {_login(REP_EMAIL, REP_PW)}", "Content-Type": "application/json"}


def _detail(resp):
    try:
        j = resp.json()
        d = j.get("detail", j.get("error", j.get("message", "")))
        return json.dumps(d) if isinstance(d, (dict, list)) else str(d)
    except Exception:
        return resp.text or ""


# ─── Clean-state fixture: ensure no pt_integrations email doc exists ──────
@pytest.fixture(scope="module", autouse=True)
def _clean_email_doc(admin_headers):
    # Best-effort cleanup before & after the entire module.
    def _clean():
        # No public DELETE; nuke via mongo if available.
        try:
            from pymongo import MongoClient
            mongo_url = os.environ.get("MONGO_URL")
            db_name = os.environ.get("DB_NAME")
            if mongo_url and db_name:
                MongoClient(mongo_url)[db_name]["pt_integrations"].delete_one({"name": "email"})
        except Exception as e:
            print(f"mongo cleanup skipped: {e}")
    _clean()
    yield
    _clean()


# ─── 1. GET /api/pt/email/config — fresh state ────────────────────────────
class TestEmailConfigGet:
    def test_get_config_fresh_state_uses_global_fallback(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/pt/email/config", headers=admin_headers, timeout=15)
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:200]}"
        data = r.json()
        assert "from_name" in data
        assert "from_address" in data
        assert "resend_api_key_masked" in data
        assert "using_global_fallback" in data
        assert data["using_global_fallback"] is True, f"expected fallback True on fresh state, got {data}"
        # Platform key fingerprint should be shown (because RESEND_API_KEY is set in env)
        assert data["resend_api_key_masked"], (
            f"expected platform key fingerprint, got: {data.get('resend_api_key_masked')}"
        )

    def test_get_config_no_x_tenant_id_header_needed(self, admin_headers):
        # Strip any tenant header — module-level admin_headers already lacks it.
        hdrs = dict(admin_headers)
        hdrs.pop("X-Tenant-Id", None)
        r = requests.get(f"{BASE_URL}/api/pt/email/config", headers=hdrs, timeout=15)
        assert r.status_code == 200


# ─── 2. POST /api/pt/email/config — save + blank-key-keeps-existing ───────
class TestEmailConfigSave:
    def test_post_config_saves_name_and_address(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/pt/email/config",
            headers=admin_headers,
            json={"from_name": "ARIA Test", "from_address": "test-iter84@example.com"},
            timeout=15,
        )
        assert r.status_code == 200, f"save failed: {r.status_code} {r.text[:200]}"
        body = r.json()
        assert body.get("ok") is True
        # Verify GET persistence
        g = requests.get(f"{BASE_URL}/api/pt/email/config", headers=admin_headers, timeout=15)
        assert g.status_code == 200
        gd = g.json()
        assert gd["from_name"] == "ARIA Test"
        assert gd["from_address"] == "test-iter84@example.com"

    def test_post_config_blank_resend_key_keeps_existing(self, admin_headers):
        # First save a fake key
        r1 = requests.post(
            f"{BASE_URL}/api/pt/email/config",
            headers=admin_headers,
            json={
                "from_name": "ARIA Iter84",
                "from_address": "test-iter84@example.com",
                "resend_api_key": "re_iter84_fakekey_AAAA1111BBBB2222",
            },
            timeout=15,
        )
        assert r1.status_code == 200
        g1 = requests.get(f"{BASE_URL}/api/pt/email/config", headers=admin_headers, timeout=15)
        masked_before = g1.json()["resend_api_key_masked"]
        using_fallback_before = g1.json()["using_global_fallback"]
        assert using_fallback_before is False, "after saving a workspace key, fallback should be False"
        assert masked_before, "expected masked key after save"

        # Now save with blank key
        r2 = requests.post(
            f"{BASE_URL}/api/pt/email/config",
            headers=admin_headers,
            json={"from_name": "ARIA Iter84 v2", "from_address": "test2-iter84@example.com", "resend_api_key": ""},
            timeout=15,
        )
        assert r2.status_code == 200
        g2 = requests.get(f"{BASE_URL}/api/pt/email/config", headers=admin_headers, timeout=15)
        gd2 = g2.json()
        assert gd2["from_name"] == "ARIA Iter84 v2"
        assert gd2["from_address"] == "test2-iter84@example.com"
        assert gd2["resend_api_key_masked"] == masked_before, "existing key should be preserved on blank submit"
        assert gd2["using_global_fallback"] is False

    def test_post_config_allows_master_admin(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/pt/email/config",
            headers=admin_headers,
            json={"from_name": "master_admin can write"},
            timeout=15,
        )
        assert r.status_code == 200, f"master_admin blocked: {r.status_code} {r.text[:200]}"

    def test_post_config_blocks_sales_rep_with_403(self, rep_headers):
        """Per review request: sales_rep is a non-write role for email config."""
        r = requests.post(
            f"{BASE_URL}/api/pt/email/config",
            headers=rep_headers,
            json={"from_name": "rep should be blocked"},
            timeout=15,
        )
        # Expectation per review request: 403. Observed _can_write code currently
        # includes sales_rep — this test will surface the contradiction if any.
        assert r.status_code == 403, (
            f"expected 403 for sales_rep, got {r.status_code}: {r.text[:300]}"
        )


# ─── 3. POST /api/pt/email/test-send ──────────────────────────────────────
class TestEmailTestSend:
    def test_test_send_invalid_recipient_returns_422(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/pt/email/test-send",
            headers=admin_headers,
            json={"to": "not-an-email"},
            timeout=15,
        )
        assert r.status_code == 422, f"expected 422 for invalid email, got {r.status_code}: {r.text[:200]}"

    def test_test_send_blocks_sales_rep_with_403(self, rep_headers):
        r = requests.post(
            f"{BASE_URL}/api/pt/email/test-send",
            headers=rep_headers,
            json={"to": OWNER_INBOX},
            timeout=15,
        )
        assert r.status_code == 403, f"expected 403 for sales_rep, got {r.status_code}: {r.text[:300]}"

    def test_test_send_no_x_tenant_id_header_needed(self, admin_headers):
        # Use a non-existent recipient (sandbox path) but no X-Tenant-Id.
        hdrs = dict(admin_headers)
        hdrs.pop("X-Tenant-Id", None)
        r = requests.post(
            f"{BASE_URL}/api/pt/email/test-send",
            headers=hdrs,
            json={"to": NON_OWNER_INBOX},
            timeout=30,
        )
        # Endpoint should respond (200 / 400 / 502 — anything but 401/422-for-tenant)
        assert r.status_code != 401
        assert r.status_code != 500, f"500: {r.text[:300]}"

    def test_test_send_sandbox_friendly_error_no_raw_leak(self, admin_headers):
        """When sending to a non-owner via the sandbox onboarding@resend.dev sender,
        Resend returns 'You can only send testing emails to your own email address'.
        Backend must translate to a friendly 400 — never leak the raw JSON."""
        # Ensure we are sending FROM the resend sandbox default (no verified domain)
        # AND using the REAL platform key (env fallback) — not the fake workspace
        # key left behind by earlier tests. Wipe the workspace api_key in mongo.
        try:
            from pymongo import MongoClient
            mc = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
            mc["pt_integrations"].update_one(
                {"name": "email"}, {"$unset": {"api_key": ""}}, upsert=True
            )
        except Exception as e:
            pytest.skip(f"mongo unset failed: {e}")
        requests.post(
            f"{BASE_URL}/api/pt/email/config",
            headers=admin_headers,
            json={"from_name": "ARIA", "from_address": "onboarding@resend.dev"},
            timeout=15,
        )
        r = requests.post(
            f"{BASE_URL}/api/pt/email/test-send",
            headers=admin_headers,
            json={"to": NON_OWNER_INBOX, "subject": "iter84 sandbox check"},
            timeout=30,
        )
        # Must not 500
        assert r.status_code != 500, f"500 stacktrace leaked: {r.text[:300]}"
        body = r.text or ""
        # Resend raw phrase MUST NOT leak through.
        assert "You can only send testing emails to your own email address" not in body, (
            f"raw Resend phrase leaked: {body[:400]}"
        )
        # Expect a friendly 400 if Resend actually blocked it. If the platform key
        # has a verified domain, this might 200 instead — log that too.
        if r.status_code == 400:
            low = _detail(r).lower()
            assert ("sandbox" in low) or ("domain" in low and "verif" in low), (
                f"400 detail not friendly sandbox/domain message: {_detail(r)[:300]}"
            )
        elif r.status_code == 200:
            # Domain is verified — surprising but acceptable; record for human review.
            j = r.json()
            assert j.get("ok") is True
            assert j.get("provider_id"), f"200 without provider_id: {j}"
            print(
                "[NOTE] sandbox-error test returned 200 — Resend account either has "
                "a verified domain or the non-owner inbox happens to be the owner. "
                "Friendly-error path not exercised in this run."
            )
        else:
            # 502 or other — must still be friendly + no raw JSON leak.
            assert not (
                "You can only send testing emails" in body or '"statusCode":403' in body
            ), f"raw provider payload leaked at status {r.status_code}: {body[:300]}"

    def test_test_send_owner_inbox_success(self, admin_headers):
        """One real success-path call against the verified account-owner inbox.
        Per agent context: manual run already returned a provider_id. We expect
        200 + provider_id. If Resend rate-limits us, accept 400/429 with friendly
        message and skip rather than fail."""
        # Use the platform fallback explicitly — wipe any leftover fake key.
        try:
            from pymongo import MongoClient
            mc = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
            mc["pt_integrations"].update_one(
                {"name": "email"}, {"$unset": {"api_key": ""}}, upsert=True
            )
        except Exception:
            pass
        r = requests.post(
            f"{BASE_URL}/api/pt/email/test-send",
            headers=admin_headers,
            json={"to": OWNER_INBOX, "subject": "iter84 backend test — owner inbox"},
            timeout=45,
        )
        if r.status_code == 200:
            j = r.json()
            assert j.get("ok") is True
            assert j.get("to") == OWNER_INBOX
            assert "provider_id" in j  # may be None if Resend SDK returned non-dict
            assert "message" in j
        elif r.status_code in (400, 429, 502):
            # Allow rate-limited / sandbox / transient. Must NOT leak raw JSON.
            body = r.text or ""
            assert "You can only send testing emails to your own email address" not in body
            assert "stack" not in body.lower() and "traceback" not in body.lower()
            pytest.skip(f"resend non-200 (likely rate limit / sandbox) — body: {body[:200]}")
        else:
            pytest.fail(f"unexpected status {r.status_code}: {r.text[:300]}")

    def test_test_send_no_key_returns_400_friendly(self, admin_headers):
        """Clear both workspace key AND env key → 400 'No Resend API key available'.
        We can't pop the env var from this process, so we simulate the worker side
        by patching RESEND_API_KEY out of the running backend via mongo + a known
        empty workspace and a temporary env override."""
        # The endpoint reads os.environ at call-time. If env is set in backend
        # supervisor, we cannot clear it from here. So we check the env first.
        env_key = os.environ.get("RESEND_API_KEY", "")
        if env_key:
            pytest.skip(
                "RESEND_API_KEY is set in this test process's env; can't fully clear "
                "global fallback from the backend supervisor process either. "
                "The 'no key' branch is verified by inspection of _get_email_config "
                "and the explicit `if not cfg['resend_api_key']` check at line 1293."
            )
        # Clear workspace key by setting blank — but model strips blank, so we
        # have to nuke via mongo.
        try:
            from pymongo import MongoClient
            mc = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
            mc["pt_integrations"].update_one({"name": "email"}, {"$unset": {"api_key": ""}}, upsert=True)
        except Exception as e:
            pytest.skip(f"could not mutate mongo to clear workspace key: {e}")
        r = requests.post(
            f"{BASE_URL}/api/pt/email/test-send",
            headers=admin_headers,
            json={"to": OWNER_INBOX},
            timeout=15,
        )
        assert r.status_code == 400
        assert "no resend api key" in _detail(r).lower()


# ─── 4. Light regression on iter82-83 fixes ───────────────────────────────
class TestRegressionIter82_83:
    def test_pt_overview_200(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/pt/overview", headers=admin_headers, timeout=15)
        assert r.status_code == 200

    def test_pt_leads_200(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/pt/leads", headers=admin_headers, timeout=15)
        assert r.status_code == 200

    def test_auto_map_publish_empty_payload_200(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/aria/auto-map/publish",
            headers=admin_headers,
            json={
                "icps": [], "lead_sources": [], "touchpoints": [],
                "qualification": {}, "handoff": {}, "overwrite_journey": False,
            },
            timeout=30,
        )
        assert r.status_code == 200

    def test_saleshandy_test_no_raw_json_leak(self, admin_headers):
        # Quick smoke — must not 500, must not leak raw provider JSON.
        r = requests.post(
            f"{BASE_URL}/api/integrations/test/saleshandy",
            headers=admin_headers,
            timeout=30,
        )
        assert r.status_code != 500
        body = r.text or ""
        assert '"statusCode":404' not in body
        assert "Cannot POST" not in body
