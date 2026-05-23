"""Iter85 — Pietential email-send extensions: signature, attachment, handshake, path-traversal.

Focuses ONLY on iter85-new surface:
  • signature_html persistence + presence in GET
  • include_signature toggle on /test-send
  • attachment_file_id resolution from /api/lead-magnets/upload
  • silent-drop of nonexistent file_id and path-traversal attempts
  • handshake object on POST /api/pt/email/config (real key vs fake key)
  • concurrent-safe key swap (legacy lead-magnet send still works)
  • sales_rep still blocked on the workspace-admin gate (iter84 regression)
  • light iter82-83 regression smoke

Resend rate-limits: at most ONE real success-path send to the verified
account-owner inbox (meghaagarwaljain2015@gmail.com). All other sends
hit the no-attachment / signature-toggle / silent-drop branches without
sending duplicates when possible.
"""
import os
import json
import pytest
import requests

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

OWNER_INBOX = "meghaagarwaljain2015@gmail.com"
UPLOADS_DIR = "/app/backend/uploads"

# Tiny valid-ish PDF — Resend accepts any base64 blob with a filename.
TINY_PDF_BYTES = b"%PDF-1.4\n%test\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


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


# ─── autouse cleanup: pt_integrations email doc + uploads tmp files ───────
_created_file_ids: list = []


@pytest.fixture(scope="module", autouse=True)
def _clean_state():
    def _clean():
        try:
            from pymongo import MongoClient
            mongo_url = os.environ.get("MONGO_URL")
            db_name = os.environ.get("DB_NAME")
            if mongo_url and db_name:
                MongoClient(mongo_url)[db_name]["pt_integrations"].delete_one({"name": "email"})
        except Exception as e:
            print(f"mongo cleanup skipped: {e}")
        # Wipe any test files we tracked
        for fid in list(_created_file_ids):
            p = os.path.join(UPLOADS_DIR, fid)
            try:
                if os.path.isfile(p):
                    os.remove(p)
            except Exception:
                pass
    _clean()
    yield
    _clean()


# ─────────────────────────────────────────────────────────────────────────
# 1. GET /api/pt/email/config — fresh state has signature_html + flags
# ─────────────────────────────────────────────────────────────────────────
class TestGetConfigSignatureFields:
    def test_get_fresh_state_has_signature_html_empty_and_flag_false(self, admin_headers):
        # Ensure clean (autouse already wiped at module start, but be safe).
        r = requests.get(f"{BASE_URL}/api/pt/email/config", headers=admin_headers, timeout=15)
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:200]}"
        data = r.json()
        assert "signature_html" in data, f"signature_html missing: {data}"
        assert "using_workspace_signature" in data, f"using_workspace_signature missing: {data}"
        assert data["signature_html"] == "", f"expected empty signature on fresh, got {data['signature_html']!r}"
        assert data["using_workspace_signature"] is False


# ─────────────────────────────────────────────────────────────────────────
# 2. POST /api/pt/email/config — persist signature + handshake object
# ─────────────────────────────────────────────────────────────────────────
class TestSaveConfigSignatureAndHandshake:
    def test_save_signature_persists_and_flag_flips(self, admin_headers):
        sig = "<strong>— John</strong>"
        r = requests.post(
            f"{BASE_URL}/api/pt/email/config",
            headers=admin_headers,
            json={"signature_html": sig, "from_name": "ARIA Iter85"},
            timeout=20,
        )
        assert r.status_code == 200, f"save failed: {r.status_code} {r.text[:300]}"
        body = r.json()
        assert body.get("ok") is True
        assert "handshake" in body, f"handshake key missing from save response: {body}"
        h = body["handshake"]
        assert set(["ok", "message", "domains"]).issubset(h.keys()), f"handshake shape wrong: {h}"
        # Verify GET reflects signature
        g = requests.get(f"{BASE_URL}/api/pt/email/config", headers=admin_headers, timeout=15)
        gd = g.json()
        assert gd["signature_html"] == sig
        assert gd["using_workspace_signature"] is True

    def test_save_with_real_key_handshake_ok_true_lists_genleadai_domain(self, admin_headers):
        """For the platform RESEND_API_KEY (env), handshake should succeed and
        include mail.genleadai.com (verified domain per review request)."""
        # Save with no explicit key — backend will use env RESEND_API_KEY fallback.
        # First, wipe any leftover fake workspace key from earlier tests.
        try:
            from pymongo import MongoClient
            mc = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
            mc["pt_integrations"].update_one(
                {"name": "email"}, {"$unset": {"api_key": ""}}, upsert=True
            )
        except Exception as e:
            pytest.skip(f"mongo unset failed: {e}")
        r = requests.post(
            f"{BASE_URL}/api/pt/email/config",
            headers=admin_headers,
            json={"from_name": "ARIA"},
            timeout=20,
        )
        assert r.status_code == 200
        h = r.json().get("handshake") or {}
        assert h.get("ok") is True, f"expected ok=true with platform key, got: {h}"
        domains_blob = " ".join(h.get("domains") or [])
        assert "mail.genleadai.com" in domains_blob, (
            f"expected mail.genleadai.com in domains list, got: {h.get('domains')}"
        )

    def test_save_with_fake_key_handshake_ok_false_message_rejected(self, admin_headers):
        """Fake/invalid resend_api_key → save still 200, handshake.ok=false,
        message contains 'Resend rejected the API key'."""
        fake = "re_iter85_fakefake_DEADBEEF0000111122223333"
        try:
            r = requests.post(
                f"{BASE_URL}/api/pt/email/config",
                headers=admin_headers,
                json={"from_name": "ARIA fake", "resend_api_key": fake},
                timeout=20,
            )
            assert r.status_code == 200, f"expected 200 (saved) even with bad key, got {r.status_code}: {r.text[:200]}"
            h = r.json().get("handshake") or {}
            assert h.get("ok") is False, f"expected ok=false for fake key, got: {h}"
            msg = (h.get("message") or "").lower()
            # Spec requires the phrase 'Resend rejected the API key' — but the
            # current handshake helper only matches HTTP 401. Resend now returns
            # 400 for invalid keys, so the friendly phrase is missed and we get
            # 'Resend returned 400.' instead.
            assert "resend rejected the api key" in msg, (
                f"expected 'Resend rejected the API key' phrase per review-request, got: {h.get('message')!r} "
                "(BUG: verify_resend_handshake at routes/pt_email.py only handles 401, but Resend returns 400 for invalid keys)"
            )
        finally:
            # ALWAYS wipe the bad workspace key so downstream tests use the
            # platform RESEND_API_KEY fallback (regardless of assertion outcome).
            try:
                from pymongo import MongoClient
                mc = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
                mc["pt_integrations"].update_one(
                    {"name": "email"}, {"$unset": {"api_key": ""}}, upsert=True
                )
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────
# 3. POST /api/pt/email/test-send — signature toggle + attachment + guards
# ─────────────────────────────────────────────────────────────────────────
class TestTestSendSignatureAttachment:
    def _save_signature(self, admin_headers, sig="<em>— Test Sig iter85</em>"):
        r = requests.post(
            f"{BASE_URL}/api/pt/email/config",
            headers=admin_headers,
            json={"signature_html": sig, "from_name": "ARIA"},
            timeout=20,
        )
        assert r.status_code == 200

    def _upload_pdf(self, admin_headers) -> str:
        files = {"file": ("iter85_attach.pdf", TINY_PDF_BYTES, "application/pdf")}
        # No Content-Type override for multipart
        hdrs = {"Authorization": admin_headers["Authorization"]}
        r = requests.post(
            f"{BASE_URL}/api/lead-magnets/upload",
            files=files,
            headers=hdrs,
            timeout=30,
        )
        assert r.status_code == 200, f"upload failed: {r.status_code} {r.text[:200]}"
        fid = r.json()["file_id"]
        _created_file_ids.append(fid)
        return fid

    def test_test_send_with_signature_true_appends_signature(self, admin_headers):
        """include_signature=true + saved signature → signature_appended=true."""
        self._save_signature(admin_headers)
        r = requests.post(
            f"{BASE_URL}/api/pt/email/test-send",
            headers=admin_headers,
            json={
                "to": OWNER_INBOX,
                "subject": "iter85 — signature ON",
                "include_signature": True,
            },
            timeout=45,
        )
        if r.status_code in (400, 429, 502):
            body = r.text or ""
            assert "You can only send testing emails to your own email address" not in body
            print(f"[SIG-ON SKIP] status={r.status_code} body={body[:200]}")
            pytest.skip(f"resend non-200 (rate limit / sandbox): {r.status_code} {body[:200]}")
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:300]}"
        j = r.json()
        assert j.get("ok") is True
        assert j.get("signature_appended") is True, f"signature_appended should be true: {j}"
        assert j.get("attachments_count", 0) == 0
        msg = j.get("message", "")
        assert "Signature: appended." in msg, f"expected message to mention signature: {msg!r}"

    def test_test_send_with_signature_false_does_not_append(self, admin_headers):
        """include_signature=false → signature_appended=false even if workspace sig set."""
        self._save_signature(admin_headers)
        r = requests.post(
            f"{BASE_URL}/api/pt/email/test-send",
            headers=admin_headers,
            json={
                "to": OWNER_INBOX,
                "subject": "iter85 — signature OFF",
                "include_signature": False,
            },
            timeout=45,
        )
        if r.status_code in (400, 429, 502):
            body = r.text or ""
            assert "You can only send testing emails to your own email address" not in body
            pytest.skip(f"resend non-200 (rate limit): {r.status_code} {body[:200]}")
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:300]}"
        j = r.json()
        assert j.get("ok") is True
        assert j.get("signature_appended") is False, f"signature_appended should be false: {j}"
        msg = j.get("message", "")
        assert "Signature: appended." not in msg, f"message should NOT mention signature: {msg!r}"

    def test_test_send_with_valid_attachment_count_1(self, admin_headers):
        """Upload PDF then attach via attachment_file_id. attachments_count=1,
        signature_appended=true, message includes 'Attachment: included.' +
        'Signature: appended.'"""
        self._save_signature(admin_headers, sig="<strong>— John (attach test)</strong>")
        file_id = self._upload_pdf(admin_headers)
        r = requests.post(
            f"{BASE_URL}/api/pt/email/test-send",
            headers=admin_headers,
            json={
                "to": OWNER_INBOX,
                "subject": "iter85 — with attachment",
                "include_signature": True,
                "attachment_file_id": file_id,
            },
            timeout=60,
        )
        if r.status_code in (400, 429, 502):
            body = r.text or ""
            assert "You can only send testing emails to your own email address" not in body
            pytest.skip(f"resend non-200 (rate limit): {r.status_code} {body[:200]}")
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:300]}"
        j = r.json()
        assert j.get("ok") is True
        assert j.get("attachments_count") == 1, f"attachments_count should be 1: {j}"
        assert j.get("signature_appended") is True
        msg = j.get("message", "")
        assert "Attachment: included." in msg, f"message missing 'Attachment: included.': {msg!r}"
        assert "Signature: appended." in msg, f"message missing 'Signature: appended.': {msg!r}"

    def test_test_send_with_nonexistent_attachment_silently_drops(self, admin_headers):
        """attachment_file_id='nonexistent.pdf' → attachments_count=0, no 500/404.
        The send should still succeed (200) or skip on Resend rate-limit."""
        # Clear signature so we're verifying attachment branch only.
        requests.post(
            f"{BASE_URL}/api/pt/email/config",
            headers=admin_headers,
            json={"signature_html": "", "from_name": "ARIA"},
            timeout=20,
        )
        r = requests.post(
            f"{BASE_URL}/api/pt/email/test-send",
            headers=admin_headers,
            json={
                "to": OWNER_INBOX,
                "subject": "iter85 — nonexistent attachment",
                "include_signature": False,
                "attachment_file_id": "nonexistent.pdf",
            },
            timeout=45,
        )
        assert r.status_code != 500, f"500 leak on nonexistent attachment: {r.text[:300]}"
        assert r.status_code != 404, f"404 on nonexistent attachment should be silent-drop, got 404: {r.text[:300]}"
        if r.status_code in (400, 429, 502):
            body = r.text or ""
            assert "You can only send testing emails to your own email address" not in body
            pytest.skip(f"resend non-200 (rate limit): {r.status_code} {body[:200]}")
        assert r.status_code == 200, f"expected 200 with attachments_count=0, got {r.status_code}: {r.text[:300]}"
        j = r.json()
        assert j.get("attachments_count") == 0, f"expected attachments_count=0, got {j}"

    def test_test_send_path_traversal_silently_dropped(self, admin_headers):
        """attachment_file_id='../../../etc/passwd' → attachments_count=0, no 500,
        no file content leaked, no path leaked in response."""
        r = requests.post(
            f"{BASE_URL}/api/pt/email/test-send",
            headers=admin_headers,
            json={
                "to": OWNER_INBOX,
                "subject": "iter85 — path traversal guard",
                "include_signature": False,
                "attachment_file_id": "../../../etc/passwd",
            },
            timeout=45,
        )
        body = r.text or ""
        assert r.status_code != 500, f"500 on path traversal: {body[:300]}"
        # Verify NO /etc/passwd content leaked
        assert "root:x:" not in body, f"/etc/passwd content leaked: {body[:300]}"
        assert "/etc/passwd" not in body, f"path leaked in response: {body[:300]}"
        if r.status_code in (400, 429, 502):
            pytest.skip(f"resend non-200 (rate limit): {r.status_code} {body[:200]}")
        assert r.status_code == 200, f"expected 200 silent-drop, got {r.status_code}: {body[:300]}"
        j = r.json()
        assert j.get("attachments_count") == 0, f"path-traversal attachment NOT dropped: {j}"


# ─────────────────────────────────────────────────────────────────────────
# 4. Concurrent-safe key swap: legacy lead-magnet send still works
# ─────────────────────────────────────────────────────────────────────────
class TestConcurrentSafeKeySwap:
    def test_legacy_send_lead_magnet_endpoint_not_broken(self, admin_headers):
        """After workspace test-sends saved+restored resend.api_key, the legacy
        /api/leads/{id}/send-lead-magnet must NOT 500. (We don't have a real lead
        id; we expect 404/400/422 — anything but 500 or auth failure.)"""
        r = requests.post(
            f"{BASE_URL}/api/leads/nonexistent_lead_iter85/send-lead-magnet",
            headers=admin_headers,
            json={},
            timeout=20,
        )
        assert r.status_code != 500, f"500 on legacy send-lead-magnet (key swap regression?): {r.text[:300]}"
        # Anything in {400, 401, 403, 404, 422} is acceptable — endpoint reachable.
        assert r.status_code in (400, 401, 403, 404, 422), (
            f"unexpected status from legacy endpoint: {r.status_code} {r.text[:200]}"
        )


# ─────────────────────────────────────────────────────────────────────────
# 5. Iter84 regression: sales_rep STILL blocked on workspace-admin endpoints
# ─────────────────────────────────────────────────────────────────────────
class TestSalesRepStillBlocked:
    def test_sales_rep_blocked_on_email_config_save(self, rep_headers):
        r = requests.post(
            f"{BASE_URL}/api/pt/email/config",
            headers=rep_headers,
            json={"from_name": "rep should be blocked", "signature_html": "<i>haha</i>"},
            timeout=15,
        )
        assert r.status_code == 403, f"expected 403 for sales_rep on /email/config, got {r.status_code}: {r.text[:300]}"

    def test_sales_rep_blocked_on_email_test_send(self, rep_headers):
        r = requests.post(
            f"{BASE_URL}/api/pt/email/test-send",
            headers=rep_headers,
            json={"to": OWNER_INBOX, "include_signature": False},
            timeout=15,
        )
        assert r.status_code == 403, f"expected 403 for sales_rep on /email/test-send, got {r.status_code}: {r.text[:300]}"


# ─────────────────────────────────────────────────────────────────────────
# 6. Light regression — iter82-83-84 endpoints still 200
# ─────────────────────────────────────────────────────────────────────────
class TestRegressionPriorIters:
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

    def test_saleshandy_test_no_raw_leak(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/integrations/test/saleshandy",
            headers=admin_headers,
            timeout=30,
        )
        assert r.status_code != 500
        body = r.text or ""
        assert '"statusCode":404' not in body
        assert "Cannot POST" not in body
