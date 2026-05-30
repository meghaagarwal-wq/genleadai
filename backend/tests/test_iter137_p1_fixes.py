"""iter137 — verify the 3 P1 fixes from iter136 audit:
  Fix 1: POST /api/aria/eod-wrap/send-now returns structured 503 (was uncaught 500)
  Fix 2: GET  /api/aria/eod-wrap/last returns proper shape (was 404)
  Fix 3: POST /api/journey/generate is async (job_id + poll), no 60s timeout
Also covers cross-tenant + bogus-job-id 404 paths."""
from __future__ import annotations

import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = "Demo1234!"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    tok = data.get("token") or data.get("access_token")
    assert tok, f"no token in {data}"
    return tok


def _h(tok, tenant="ten_demo"):
    return {"Authorization": f"Bearer {tok}", "X-Tenant-Id": tenant, "Content-Type": "application/json"}


# ─── Fix 1: eod-wrap/send-now structured 503 ────────────────────────────
class TestFix1EodWrapSendNow:
    def test_send_now_returns_structured_503_not_500(self, admin_token):
        r = requests.post(f"{BASE_URL}/api/aria/eod-wrap/send-now",
                          headers=_h(admin_token), timeout=60)
        # Could be 200 (verified recipient) or 503 structured. Must NOT be 500.
        assert r.status_code != 500, f"REGRESSION — 500 traceback leak: {r.text[:500]}"
        if r.status_code == 503:
            body = r.json()
            detail = body.get("detail")
            assert isinstance(detail, dict), f"detail must be structured object, got: {detail!r}"
            assert detail.get("code") in {
                "resend_sandbox_or_unverified_domain", "no_resend_key",
                "no_recipient", "send_failed", "unknown",
            }, f"unexpected code: {detail.get('code')}"
            assert detail.get("status") == 503
            assert isinstance(detail.get("user_message"), str) and len(detail["user_message"]) > 0
            # For the EXPECTED sandbox case, verify user_message helpfulness
            if detail["code"] == "resend_sandbox_or_unverified_domain":
                assert "verify a domain" in detail["user_message"].lower() or "resend.com/domains" in detail["user_message"].lower()
        else:
            assert r.status_code == 200, f"unexpected status {r.status_code}: {r.text[:300]}"


# ─── Fix 2: eod-wrap/last shape ─────────────────────────────────────────
class TestFix2EodWrapLast:
    def test_last_endpoint_exists_and_has_shape(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/aria/eod-wrap/last",
                         headers=_h(admin_token), timeout=15)
        assert r.status_code == 200, f"REGRESSION — expected 200, got {r.status_code}: {r.text[:300]}"
        body = r.json()
        for key in ("last_sent_at", "last_sent_date", "last_sent_touches", "last_sent_manual"):
            assert key in body, f"missing key {key} in {body}"
        assert isinstance(body["last_sent_touches"], int)
        assert isinstance(body["last_sent_manual"], bool)


# ─── Fix 3: journey/generate async pattern ──────────────────────────────
class TestFix3JourneyGenerateAsync:
    def test_kickoff_returns_job_id_fast(self, admin_token):
        t0 = time.time()
        r = requests.post(f"{BASE_URL}/api/journey/generate",
                          headers=_h(admin_token),
                          json={"count": 3, "replace": False}, timeout=10)
        elapsed = time.time() - t0
        assert r.status_code == 200, f"kickoff failed: {r.status_code} {r.text[:300]}"
        assert elapsed < 5, f"kickoff too slow ({elapsed:.1f}s) — should be async"
        body = r.json()
        assert "job_id" in body and body["job_id"].startswith("jgj_")
        assert body.get("status") == "queued"
        assert isinstance(body.get("eta_seconds"), int)
        assert "hint" in body
        pytest.shared_job_id = body["job_id"]

    def test_job_poll_completes(self, admin_token):
        job_id = getattr(pytest, "shared_job_id", None)
        assert job_id, "kickoff test must run first"

        statuses_seen = set()
        result = None
        deadline = time.time() + 300  # 5min ceiling
        while time.time() < deadline:
            try:
                r = requests.get(f"{BASE_URL}/api/journey/generate/job/{job_id}",
                                 headers=_h(admin_token), timeout=30)
            except requests.exceptions.RequestException as e:
                print(f"[poll] transient network error: {e}; retrying...")
                time.sleep(5)
                continue
            assert r.status_code == 200, f"poll failed: {r.status_code} {r.text[:300]}"
            body = r.json()
            statuses_seen.add(body.get("status"))
            if body.get("status") in ("done", "failed"):
                result = body
                break
            time.sleep(3)
        assert result is not None, f"job did not finish in 5min. Statuses seen: {statuses_seen}"
        assert result["status"] == "done", f"job failed: {result.get('error')}"
        res = result.get("result") or {}
        assert isinstance(res.get("touchpoints"), list) and len(res["touchpoints"]) > 0
        assert res.get("count", 0) > 0

    def test_bogus_job_id_returns_404(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/journey/generate/job/jgj_bogus_doesnotexist",
                         headers=_h(admin_token), timeout=10)
        assert r.status_code == 404

    def test_cross_tenant_isolation_404(self, admin_token):
        job_id = getattr(pytest, "shared_job_id", None)
        if not job_id:
            pytest.skip("no shared job id")
        # admin@demo is member of both tenants — but the job was created under ten_demo;
        # polling with X-Tenant-Id ten_pietential must 404.
        r = requests.get(f"{BASE_URL}/api/journey/generate/job/{job_id}",
                         headers=_h(admin_token, tenant="ten_pietential"), timeout=10)
        assert r.status_code == 404, f"tenant leak! status={r.status_code} body={r.text[:300]}"


# ─── Regression: sibling notifications still work ───────────────────────
class TestRegressionSiblingNotifs:
    def test_morning_brief_last_still_200(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/aria/morning-brief/last",
                         headers=_h(admin_token), timeout=15)
        assert r.status_code == 200

    def test_approval_digest_last_still_200(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/aria/approval-digest/last",
                         headers=_h(admin_token), timeout=15)
        assert r.status_code == 200

    def test_morning_brief_send_now(self, admin_token):
        r = requests.post(f"{BASE_URL}/api/aria/morning-brief/send-now",
                          headers=_h(admin_token), timeout=60)
        # accept 200 (verified email) or 503 structured — never 500
        assert r.status_code != 500, f"morning-brief leaked 500: {r.text[:300]}"
        assert r.status_code in (200, 503)

    def test_approval_digest_send_now(self, admin_token):
        r = requests.post(f"{BASE_URL}/api/aria/approval-digest/send-now",
                          headers=_h(admin_token), timeout=60)
        assert r.status_code != 500, f"approval-digest leaked 500: {r.text[:300]}"
        assert r.status_code in (200, 503)


# ─── Regression: Journey CRUD + single regenerate ───────────────────────
class TestRegressionJourneyCrud:
    def test_list_touchpoints(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/journey/touchpoints",
                         headers=_h(admin_token), timeout=15)
        assert r.status_code == 200
        assert "touchpoints" in r.json()

    def test_create_patch_delete_cycle(self, admin_token):
        # CREATE
        r = requests.post(f"{BASE_URL}/api/journey/touchpoints",
                          headers=_h(admin_token),
                          json={"number": 64, "channel": "email", "timing": "Day 1",
                                "message_body": "TEST iter137", "goal": "test"}, timeout=15)
        assert r.status_code == 200, r.text[:300]
        tp = r.json()
        assert tp["id"].startswith("tp_")
        tp_id = tp["id"]

        # PATCH
        r = requests.patch(f"{BASE_URL}/api/journey/touchpoints/{tp_id}",
                           headers=_h(admin_token),
                           json={"goal": "test updated"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["goal"] == "test updated"

        # REORDER
        r = requests.post(f"{BASE_URL}/api/journey/touchpoints/reorder",
                          headers=_h(admin_token),
                          json={"order": [{"id": tp_id, "number": 64}]}, timeout=15)
        assert r.status_code == 200

        # DELETE
        r = requests.delete(f"{BASE_URL}/api/journey/touchpoints/{tp_id}",
                            headers=_h(admin_token), timeout=15)
        assert r.status_code == 200
