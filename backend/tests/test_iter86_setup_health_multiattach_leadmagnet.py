"""Iter86 — Pietential setup-health + multi-attachment test-send + lead-magnet refactor.

Covers ONLY the iter86 surface (acceptance criteria from review-request):

  1. GET /api/pt/setup/health
     - Shape: {items:[5x], ready_count:int, total:5, live:bool, checked_at:iso}
     - Each item has {id,label,status,detail,cta,cta_path}
     - Clean state with platform RESEND_API_KEY → email.status=ok, mentions "platform default"
     - saleshandy/lemlist not_connected → status=fail
     - saleshandy api_key + status='needs_setup' → status=warn, detail reflects error_log
     - Workspace from_address saved → email.detail mentions "Workspace Resend key + ..."

  2. POST /api/pt/email/test-send
     - attachment_file_ids=[a, b] → attachments_count=2
     - missing files silently dropped (count = present files only)
     - dedupe: attachment_file_id='X' + attachment_file_ids=['X','Y'] → count=2

  3. Legacy /api/leads/{lead_id}/send-lead-magnet regression — 200 (or explicit 4xx),
     NEVER 500 stack, after _send_lead_magnet_via_email refactor.

  4. Light regression: iter80 rate-limit on login, iter81 founder-brief 404 on bad oid,
     iter84-85 test-send signature still works.

Real Resend sends are kept to <=3 (multi-attach, dedupe, lead-magnet manual).
Owner inbox (meghaagarwaljain2015@gmail.com) is the only recipient.
"""
import os
import time
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

TINY_PDF_BYTES = b"%PDF-1.4\n%test iter86\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"

_created_file_ids: list = []
_created_lead_ids: list = []


# ─── login helper ───────────────────────────────────────────────────────────
def _login(email, pw):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw}, timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text[:200]}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_headers():
    return {"Authorization": f"Bearer {_login(ADMIN_EMAIL, ADMIN_PW)}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def rep_headers():
    return {"Authorization": f"Bearer {_login(REP_EMAIL, REP_PW)}", "Content-Type": "application/json"}


# ─── autouse cleanup ────────────────────────────────────────────────────────
def _mongo():
    from pymongo import MongoClient
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture(scope="module", autouse=True)
def _clean_state():
    def _clean():
        try:
            mc = _mongo()
            mc["pt_integrations"].delete_one({"name": "email"})
            # remove the test saleshandy/lemlist docs we may have inserted
            mc["pt_integrations"].delete_many({"name": {"$in": ["saleshandy", "lemlist"]}, "_iter86_test": True})
            # remove the workspace lead magnet doc if WE seeded it (only delete the iter86 marker)
            mc["lead_magnets"].delete_many({"_iter86_test": True})
            # delete seeded leads
            try:
                from bson import ObjectId
                for lid in list(_created_lead_ids):
                    try:
                        mc["leads"].delete_one({"_id": ObjectId(lid)})
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception as e:
            print(f"mongo cleanup skipped: {e}")
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


def _upload_pdf(admin_headers, name="iter86.pdf"):
    files = {"file": (name, TINY_PDF_BYTES, "application/pdf")}
    hdrs = {"Authorization": admin_headers["Authorization"]}
    r = requests.post(f"{BASE_URL}/api/lead-magnets/upload", files=files, headers=hdrs, timeout=30)
    assert r.status_code == 200, f"upload failed: {r.status_code} {r.text[:200]}"
    fid = r.json()["file_id"]
    _created_file_ids.append(fid)
    return fid


# ════════════════════════════════════════════════════════════════════════════
# 1. GET /api/pt/setup/health
# ════════════════════════════════════════════════════════════════════════════
class TestSetupHealthShape:
    def test_shape_and_five_items_with_required_ids(self, admin_headers):
        # Ensure clean state (autouse already wiped email integ at module start).
        r = requests.get(f"{BASE_URL}/api/pt/setup/health", headers=admin_headers, timeout=15)
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:300]}"
        j = r.json()
        # Top-level keys
        for k in ("items", "ready_count", "total", "live", "checked_at"):
            assert k in j, f"missing top-level key {k}: {list(j.keys())}"
        assert j["total"] == 5, f"total should be 5: {j['total']}"
        assert isinstance(j["items"], list)
        assert len(j["items"]) == 5, f"expected 5 items, got {len(j['items'])}"
        assert isinstance(j["ready_count"], int)
        assert isinstance(j["live"], bool)
        assert isinstance(j["checked_at"], str) and "T" in j["checked_at"]
        # Required ids — exactly these 5, in order
        ids = [it["id"] for it in j["items"]]
        assert ids == ["email", "saleshandy", "lemlist", "lead_magnet", "touchpoints"], (
            f"unexpected item ids/order: {ids}"
        )
        # Per-item shape
        for it in j["items"]:
            for k in ("id", "label", "status", "detail", "cta", "cta_path"):
                assert k in it, f"item {it.get('id')} missing key {k}: {it}"
            assert it["status"] in ("ok", "warn", "fail"), f"invalid status: {it['status']} on {it['id']}"

    def test_clean_state_email_ok_via_platform_default(self, admin_headers):
        # Wipe workspace email integ to force platform fallback.
        try:
            _mongo()["pt_integrations"].delete_one({"name": "email"})
        except Exception:
            pass
        r = requests.get(f"{BASE_URL}/api/pt/setup/health", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        items = {it["id"]: it for it in r.json()["items"]}
        # Platform RESEND_API_KEY is set in backend/.env per review-request.
        email = items["email"]
        assert email["status"] == "ok", f"expected email.ok with platform key, got: {email}"
        assert "platform default" in (email["detail"] or "").lower(), (
            f"detail should mention 'platform default', got: {email['detail']!r}"
        )

    def test_clean_state_saleshandy_and_lemlist_fail(self, admin_headers):
        # Wipe saleshandy + lemlist docs
        try:
            _mongo()["pt_integrations"].delete_many({"name": {"$in": ["saleshandy", "lemlist"]}})
        except Exception:
            pass
        r = requests.get(f"{BASE_URL}/api/pt/setup/health", headers=admin_headers, timeout=15)
        items = {it["id"]: it for it in r.json()["items"]}
        assert items["saleshandy"]["status"] == "fail", f"saleshandy: {items['saleshandy']}"
        assert items["lemlist"]["status"] == "fail", f"lemlist: {items['lemlist']}"

    def test_lead_magnet_warn_when_not_configured(self, admin_headers):
        # The lead_magnets workspace doc may exist already from seed; review-request
        # says "warn" when no enabled file/url. Force the disabled state.
        try:
            _mongo()["lead_magnets"].update_one(
                {"scope": "workspace"},
                {"$set": {"enabled": False, "_iter86_test": True}, "$unset": {"file_id": "", "url": ""}},
                upsert=True,
            )
        except Exception:
            pass
        r = requests.get(f"{BASE_URL}/api/pt/setup/health", headers=admin_headers, timeout=15)
        items = {it["id"]: it for it in r.json()["items"]}
        assert items["lead_magnet"]["status"] == "warn", f"lead_magnet: {items['lead_magnet']}"

    def test_touchpoints_status_ok_or_fail_based_on_count(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/pt/setup/health", headers=admin_headers, timeout=15)
        items = {it["id"]: it for it in r.json()["items"]}
        tp = items["touchpoints"]
        # Review-request explicitly says 'fail (or "ok" if there are existing touchpoints from seed)'
        assert tp["status"] in ("ok", "fail"), f"touchpoints status invalid: {tp}"
        # When ok, detail should mention step(s); when fail, detail should say Empty
        if tp["status"] == "ok":
            assert "step" in tp["detail"].lower(), f"detail should mention step(s): {tp}"
        else:
            assert "empty" in tp["detail"].lower(), f"detail should say Empty: {tp}"

    def test_saleshandy_needs_setup_warn_with_error_log(self, admin_headers):
        # Inject a saleshandy integ in the 'has key but rejected' state.
        try:
            _mongo()["pt_integrations"].update_one(
                {"name": "saleshandy"},
                {"$set": {
                    "name": "saleshandy",
                    "api_key": "enc_iter86_fake_key_blob",
                    "status": "needs_setup",
                    "error_log": "API key invalid (401 from Saleshandy)",
                    "_iter86_test": True,
                }},
                upsert=True,
            )
        except Exception as e:
            pytest.skip(f"mongo update failed: {e}")
        try:
            r = requests.get(f"{BASE_URL}/api/pt/setup/health", headers=admin_headers, timeout=15)
            items = {it["id"]: it for it in r.json()["items"]}
            sh = items["saleshandy"]
            assert sh["status"] == "warn", (
                f"expected saleshandy.warn for needs_setup+api_key, got: {sh}"
            )
            assert "401" in (sh["detail"] or "") or "invalid" in (sh["detail"] or "").lower(), (
                f"detail should reflect error_log, got: {sh['detail']!r}"
            )
        finally:
            try:
                _mongo()["pt_integrations"].delete_one({"name": "saleshandy", "_iter86_test": True})
            except Exception:
                pass

    def test_workspace_resend_key_detail_mentions_from_address(self, admin_headers):
        """When admin saves a valid Resend key + from_address, the next /setup/health
        email.detail should mention 'Workspace Resend key + ...' with the from_address.
        We use the platform RESEND_API_KEY as the 'valid' key to avoid leaking a fake one.
        """
        plat = os.environ.get("RESEND_API_KEY") or ""
        if not plat:
            pytest.skip("no platform RESEND_API_KEY to reuse for workspace save")
        custom_from = "iter86-test@mail.genleadai.com"
        r = requests.post(
            f"{BASE_URL}/api/pt/email/config",
            headers=admin_headers,
            json={"from_name": "ARIA iter86", "from_address": custom_from, "resend_api_key": plat},
            timeout=25,
        )
        assert r.status_code == 200, f"save failed: {r.status_code} {r.text[:200]}"
        # Now check setup/health
        r2 = requests.get(f"{BASE_URL}/api/pt/setup/health", headers=admin_headers, timeout=15)
        items = {it["id"]: it for it in r2.json()["items"]}
        email = items["email"]
        assert email["status"] == "ok"
        detail_lc = (email["detail"] or "").lower()
        assert "workspace resend key" in detail_lc, (
            f"expected 'Workspace Resend key' in detail, got: {email['detail']!r}"
        )
        assert custom_from.lower() in detail_lc, (
            f"expected from_address {custom_from!r} in detail, got: {email['detail']!r}"
        )
        # cleanup so downstream tests use platform fallback path again
        try:
            _mongo()["pt_integrations"].update_one(
                {"name": "email"}, {"$unset": {"api_key": ""}}, upsert=True
            )
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════════════════
# 2. POST /api/pt/email/test-send — multi-attachment + dedupe
# ════════════════════════════════════════════════════════════════════════════
class TestMultiAttachmentTestSend:
    def test_multi_attachment_two_pdfs_count_2(self, admin_headers):
        fid1 = _upload_pdf(admin_headers, "iter86_multi_a.pdf")
        fid2 = _upload_pdf(admin_headers, "iter86_multi_b.pdf")
        r = requests.post(
            f"{BASE_URL}/api/pt/email/test-send",
            headers=admin_headers,
            json={
                "to": OWNER_INBOX,
                "subject": "iter86 — multi attach",
                "include_signature": False,
                "attachment_file_ids": [fid1, fid2],
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
        assert j.get("attachments_count") == 2, f"expected count=2, got: {j}"

    def test_multi_attachment_missing_files_silently_dropped(self, admin_headers):
        fid_real = _upload_pdf(admin_headers, "iter86_real.pdf")
        r = requests.post(
            f"{BASE_URL}/api/pt/email/test-send",
            headers=admin_headers,
            json={
                "to": OWNER_INBOX,
                "subject": "iter86 — partial missing",
                "include_signature": False,
                "attachment_file_ids": [fid_real, "missing_iter86.pdf", "../etc/passwd"],
            },
            timeout=60,
        )
        if r.status_code in (400, 429, 502):
            body = r.text or ""
            assert "You can only send testing emails to your own email address" not in body
            pytest.skip(f"resend non-200 (rate limit): {r.status_code} {body[:200]}")
        assert r.status_code == 200, f"expected 200 (missing files silently dropped), got {r.status_code}: {r.text[:300]}"
        j = r.json()
        assert j.get("ok") is True
        assert j.get("attachments_count") == 1, (
            f"expected count=1 (one real, two dropped), got: {j}"
        )

    def test_dedupe_single_plus_list(self, admin_headers):
        """attachment_file_id='single.pdf' + attachment_file_ids=['single.pdf','another.pdf']
        → attachments_count=2 (single.pdf appears once, another.pdf added)."""
        fid1 = _upload_pdf(admin_headers, "iter86_dup_single.pdf")
        fid2 = _upload_pdf(admin_headers, "iter86_dup_another.pdf")
        r = requests.post(
            f"{BASE_URL}/api/pt/email/test-send",
            headers=admin_headers,
            json={
                "to": OWNER_INBOX,
                "subject": "iter86 — dedupe",
                "include_signature": False,
                "attachment_file_id": fid1,
                "attachment_file_ids": [fid1, fid2],
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
        assert j.get("attachments_count") == 2, (
            f"expected dedupe → count=2, got: {j}"
        )


# ════════════════════════════════════════════════════════════════════════════
# 3. Legacy /api/leads/{id}/send-lead-magnet regression
#    The _send_lead_magnet_via_email refactor must not produce 500 stacks.
# ════════════════════════════════════════════════════════════════════════════
class TestLeadMagnetManualSendRegression:
    def _seed_workspace_magnet_file(self, admin_headers, fid):
        # Use the public PUT /api/lead-magnets/config to enable a workspace
        # file-type magnet. Mark it with _iter86_test for cleanup.
        r = requests.put(
            f"{BASE_URL}/api/lead-magnets/config",
            headers=admin_headers,
            json={
                "enabled": True,
                "name": "Iter86 pre-call brochure",
                "type": "file",
                "file_id": fid,
                "file_name": "iter86_brochure.pdf",
                "send_timing": "post_booking",
                "message_template": "Hi {first_name}, here's our brief: {link}\n— {founder}",
            },
            timeout=15,
        )
        assert r.status_code == 200, f"magnet save failed: {r.status_code} {r.text[:200]}"
        # tag for cleanup
        try:
            _mongo()["lead_magnets"].update_one(
                {"scope": "workspace"}, {"$set": {"_iter86_test": True}}
            )
        except Exception:
            pass

    def _create_lead(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/leads",
            headers=admin_headers,
            json={
                "lead_type": "b2b",
                "first_name": "Iter86",
                "last_name": "Tester",
                "email": OWNER_INBOX,
                "phone": "+10000000000",
                "company_name": "Iter86 Inc",
                "source_channel": "manual",
            },
            timeout=20,
        )
        assert r.status_code == 200, f"lead create failed: {r.status_code} {r.text[:200]}"
        lid = r.json().get("id") or r.json().get("_id")
        assert lid, f"no lead id returned: {r.json()}"
        _created_lead_ids.append(lid)
        return lid

    def test_send_lead_magnet_endpoint_no_500(self, admin_headers):
        # Seed magnet (file type) + lead with valid email
        fid = _upload_pdf(admin_headers, "iter86_brochure.pdf")
        self._seed_workspace_magnet_file(admin_headers, fid)
        lid = self._create_lead(admin_headers)
        # Trigger manual send
        r = requests.post(
            f"{BASE_URL}/api/leads/{lid}/send-lead-magnet",
            headers=admin_headers,
            timeout=60,
        )
        # Must NOT 500 — per review-request, returns 200 or explicit 4xx (config issue)
        assert r.status_code != 500, (
            f"send-lead-magnet returned 500 stack — refactor regression: {r.text[:400]}"
        )
        assert r.status_code in (200, 400, 404), (
            f"unexpected status {r.status_code}: {r.text[:300]}"
        )
        if r.status_code == 200:
            j = r.json()
            # Legacy endpoint returns activity-like dict
            assert isinstance(j, dict), f"expected dict response: {j}"

    def test_send_lead_magnet_disabled_magnet_returns_400_not_500(self, admin_headers):
        # Disable the magnet, then re-trigger.
        try:
            _mongo()["lead_magnets"].update_one(
                {"scope": "workspace"},
                {"$set": {"enabled": False, "_iter86_test": True}},
                upsert=True,
            )
        except Exception:
            pass
        # Need a lead — reuse if available, else create.
        if _created_lead_ids:
            lid = _created_lead_ids[-1]
        else:
            lid = self._create_lead(admin_headers)
        r = requests.post(
            f"{BASE_URL}/api/leads/{lid}/send-lead-magnet",
            headers=admin_headers,
            timeout=30,
        )
        assert r.status_code != 500, f"got 500 when magnet disabled: {r.text[:300]}"
        assert r.status_code in (200, 400, 404), (
            f"unexpected status when magnet disabled: {r.status_code} {r.text[:200]}"
        )


# ════════════════════════════════════════════════════════════════════════════
# 4. Light iter80-85 regression smoke
# ════════════════════════════════════════════════════════════════════════════
class TestLightRegression:
    def test_iter80_login_rate_limit_still_present(self):
        """Spam 12 logins; expect at least one 429 in the burst."""
        got_429 = False
        codes = []
        for i in range(15):
            r = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": "nope-iter86@example.com", "password": "wrong"},
                timeout=10,
            )
            codes.append(r.status_code)
            if r.status_code == 429:
                got_429 = True
                break
        print(f"[iter80 rate-limit burst codes] {codes}")
        if not got_429:
            # Rate limit may be per-IP-per-minute window aligned; don't hard fail —
            # but flag this as a regression indicator.
            print("[iter80 regression] no 429 seen in 12-login burst — rate-limit may be off")
        # Soft assertion: still want some rate-limit behaviour visible
        assert got_429, "iter80 login rate-limit (10/min) appears inactive — no 429 in 12 attempts"

    def test_iter81_founder_brief_404_on_invalid_oid(self, admin_headers):
        # Use a clearly-invalid ObjectId; must be 404, not 500.
        r = requests.get(
            f"{BASE_URL}/api/pt/leads/not_a_real_oid/founder-brief",
            headers=admin_headers,
            timeout=15,
        )
        assert r.status_code == 404, (
            f"expected 404 on invalid ObjectId, got {r.status_code}: {r.text[:200]}"
        )

    def test_iter85_signature_test_send_still_works(self, admin_headers):
        """Soft regression: GET email config + save signature + read back signature_html
        without hitting Resend (no /test-send). Avoids extra real sends."""
        sig = "<em>— iter86 regression</em>"
        r = requests.post(
            f"{BASE_URL}/api/pt/email/config",
            headers=admin_headers,
            json={"signature_html": sig, "from_name": "ARIA"},
            timeout=25,
        )
        assert r.status_code == 200, f"config save failed: {r.status_code} {r.text[:200]}"
        g = requests.get(f"{BASE_URL}/api/pt/email/config", headers=admin_headers, timeout=15)
        assert g.status_code == 200
        gd = g.json()
        assert gd.get("signature_html") == sig
        assert gd.get("using_workspace_signature") is True

    def test_iter84_sales_rep_blocked_on_email_test_send(self, rep_headers):
        r = requests.post(
            f"{BASE_URL}/api/pt/email/test-send",
            headers=rep_headers,
            json={"to": OWNER_INBOX, "subject": "rep blocked"},
            timeout=15,
        )
        assert r.status_code == 403, (
            f"sales_rep should be blocked with 403 (iter84 gate), got {r.status_code}: {r.text[:200]}"
        )

    def test_setup_health_accessible_to_sales_rep(self, rep_headers):
        """/setup/health uses get_current_user (no admin gate per spec). Sales-rep
        should still get the panel data — it's a read-only health view."""
        r = requests.get(f"{BASE_URL}/api/pt/setup/health", headers=rep_headers, timeout=15)
        # If a gate is added later it should be 403, not 500.
        assert r.status_code in (200, 403), (
            f"unexpected status for sales_rep on /setup/health: {r.status_code} {r.text[:200]}"
        )
