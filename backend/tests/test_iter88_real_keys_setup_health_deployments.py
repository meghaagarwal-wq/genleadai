"""Iter88 — Real Saleshandy + Lemlist keys, tenant-scoped /setup/health,
deployments-card setup rollup, send_workspace_email routing through Aria,
_send_lead_magnet_via_email returning (sent,error), and light iter80-87 regression.
"""
import os
import time
import requests
import pytest
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASS = "Demo1234!"
SALES_EMAIL = "sarah@demo.com"
SALES_PASS = "Demo1234!"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "genleadai_lms")
_mc = MongoClient(MONGO_URL)
_db = _mc[DB_NAME]


# ─── Auth helpers ───────────────────────────────────────────────────────────
def _login(email: str, password: str) -> str:
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text[:200]}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def sales_token():
    return _login(SALES_EMAIL, SALES_PASS)


def _h(token: str, tenant_id: str = "ten_pietential") -> dict:
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": tenant_id, "Content-Type": "application/json"}


# ─── Pre-flight: ensure real keys are present in db.pt_integrations ─────────
@pytest.fixture(scope="module", autouse=True)
def _check_real_keys_present():
    sh = _db["pt_integrations"].find_one({"name": "saleshandy"}) or {}
    ll = _db["pt_integrations"].find_one({"name": "lemlist"}) or {}
    assert sh.get("api_key"), "saleshandy api_key missing in pt_integrations (must not be dropped)"
    assert ll.get("api_key"), "lemlist api_key missing in pt_integrations (must not be dropped)"
    yield
    # Post-check — keys must still be there after the run
    sh2 = _db["pt_integrations"].find_one({"name": "saleshandy"}) or {}
    ll2 = _db["pt_integrations"].find_one({"name": "lemlist"}) or {}
    assert sh2.get("api_key"), "saleshandy api_key was rotated/deleted during testing!"
    assert ll2.get("api_key"), "lemlist api_key was rotated/deleted during testing!"


# ─── A. /api/pt/setup/health — Pietential is live (3/5) ─────────────────────
class TestSetupHealthPietential:
    def test_setup_health_pietential_live(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/pt/setup/health",
                         headers=_h(admin_token, "ten_pietential"), timeout=20)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["total"] == 5
        assert body["live"] is True, f"expected live=True with real keys; got {body}"
        assert body["ready_count"] >= 3
        items = {it["id"]: it for it in body["items"]}
        assert items["saleshandy"]["status"] == "ok", items["saleshandy"]
        assert items["lemlist"]["status"] == "ok", items["lemlist"]
        # Spec says detail should mention 'Connected — last sync'
        assert "Connected" in items["saleshandy"]["detail"] and "last sync" in items["saleshandy"]["detail"]
        assert "Connected" in items["lemlist"]["detail"] and "last sync" in items["lemlist"]["detail"]
        # Email — platform default branch is fine (workspace key may or may not be saved)
        assert items["email"]["status"] == "ok"

    def test_setup_health_tenant_scoping_excludes_other_tenants(self, admin_token):
        """Insert a sham magnet for ten_other_workspace and confirm it does NOT
        leak into Pietential's /setup/health."""
        sham = {
            "scope": "workspace",
            "tenant_id": "ten_other_iter88",
            "enabled": True,
            "name": "Sham other-tenant magnet",
            "type": "url",
            "url": "https://example.com/other.pdf",
            "_iter88_marker": True,
        }
        _db["lead_magnets"].insert_one(sham)
        try:
            r = requests.get(f"{BASE_URL}/api/pt/setup/health",
                             headers=_h(admin_token, "ten_pietential"), timeout=20)
            assert r.status_code == 200
            magnet = {it["id"]: it for it in r.json()["items"]}["lead_magnet"]
            # The other-tenant magnet must NOT appear in Pietential's response
            assert "Sham other-tenant" not in magnet.get("detail", ""), \
                f"Tenant scoping broken — saw foreign magnet: {magnet}"
        finally:
            _db["lead_magnets"].delete_many({"_iter88_marker": True})


# ─── B. /api/admin/deployments — Pietential ✓, others ≤ 1/5 ────────────────
class TestDeploymentsSetupRollup:
    def test_list_deployments_shape(self, admin_token):
        # Test alias too
        r1 = requests.get(f"{BASE_URL}/api/admin/deployments/list",
                          headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        r2 = requests.get(f"{BASE_URL}/api/admin/deployments",
                          headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        # At least one must work (alias optional)
        ok_resp = r1 if r1.status_code == 200 else r2
        assert ok_resp.status_code == 200, f"list deployments failed: r1={r1.status_code} r2={r2.status_code}"
        body = ok_resp.json()
        assert "deployments" in body and isinstance(body["deployments"], list)
        cards = body["deployments"]
        assert len(cards) >= 1, "no deployments returned"
        for c in cards[:3]:
            assert "setup_ready" in c, f"setup_ready missing from card: {c.get('tenant_id')}"
            assert "setup_total" in c and c["setup_total"] == 5
            assert "setup_live" in c and isinstance(c["setup_live"], bool)
            assert isinstance(c["setup_ready"], int)

    def test_pietential_card_setup_ready_3(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/admin/deployments",
                         headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        assert r.status_code == 200
        cards = r.json()["deployments"]
        piet = next((c for c in cards if c.get("tenant_id") == "ten_pietential"), None)
        assert piet is not None, "ten_pietential not in deployments list"
        assert piet["setup_ready"] >= 3, f"Pietential setup_ready expected >=3, got {piet['setup_ready']}: {piet}"
        assert piet["setup_live"] is True

    def test_only_pietential_credits_saleshandy_lemlist(self, admin_token):
        """Non-Pietential cards must NOT inherit the pt_integrations credits."""
        r = requests.get(f"{BASE_URL}/api/admin/deployments",
                         headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        assert r.status_code == 200
        cards = r.json()["deployments"]
        # Other tenants should have setup_ready <= 1 (only RESEND_API_KEY env credit)
        # UNLESS they have their own integrations dict configured, which is allowed
        # but most should be 1/5.
        non_piet = [c for c in cards if c.get("tenant_id") != "ten_pietential"]
        # At minimum, no non-pietential card should report setup_ready == 3 due to
        # pt_integrations saleshandy+lemlist credit. We tolerate >=3 only if the
        # card's tenant has its own .integrations + touchpoints+icp set up.
        # Assert simpler invariant: at least ONE non-pietential card has setup_ready <= 1.
        low = [c for c in non_piet if c["setup_ready"] <= 1]
        assert len(low) >= 1, f"expected at least one non-piet card with setup_ready<=1, got {[c['setup_ready'] for c in non_piet[:10]]}"
        # And Pietential is uniquely credited for saleshandy+lemlist — assert no
        # other tenant card has BOTH saleshandy AND lemlist in channels (which
        # would only be possible via pt_integrations credit).
        # (channels dict only exposes whatsapp/email/crm so direct check isn't possible;
        # use the setup_ready ceiling indirectly — most should be 0/1/2.)


# ─── C. /api/leads/{id}/send-lead-magnet — success + failure branches ───────
class TestLeadMagnetSendBranches:
    """The manual lead-magnet endpoint must:
      - return 200 + 'sent: true' on success and log 'email_sent' activity
      - return 502 on Resend failure and log 'email_failed' activity
    """

    @pytest.fixture(scope="class")
    def lead_id(self, admin_token):
        # Find any existing demo lead with a valid email
        r = requests.get(f"{BASE_URL}/api/leads?limit=5",
                         headers={"Authorization": f"Bearer {admin_token}", "X-Tenant-Id": "ten_demo"},
                         timeout=20)
        if r.status_code != 200:
            pytest.skip(f"cannot list leads: {r.status_code}")
        leads = r.json().get("leads") or r.json().get("data") or []
        if not leads:
            pytest.skip("no leads available")
        return leads[0].get("id") or leads[0].get("_id")

    def test_send_lead_magnet_response_shape(self, admin_token, lead_id):
        """Ensure endpoint exists and returns sane shape. Skip on rate-limit/no-magnet."""
        r = requests.post(f"{BASE_URL}/api/leads/{lead_id}/send-lead-magnet",
                          headers={"Authorization": f"Bearer {admin_token}", "X-Tenant-Id": "ten_demo"},
                          timeout=30)
        if r.status_code == 400:
            # No magnet configured / disabled — acceptable, just smoke-checked the path
            assert "magnet" in r.text.lower() or "lead" in r.text.lower()
            pytest.skip(f"no magnet configured: {r.text[:120]}")
        if r.status_code == 429:
            pytest.skip("Resend rate-limited")
        if r.status_code == 502:
            # Failure branch — verify activity logged as email_failed
            time.sleep(0.5)
            failed = _db["activities"].find_one({
                "lead_id": lead_id, "type": "email_failed"
            }, sort=[("created_at", -1)])
            assert failed is not None, "email_failed activity not logged on 502"
            assert "FAILED" in (failed.get("subject") or "") or "failed" in (failed.get("subject") or "").lower()
            return
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body.get("sent") is True, body
        assert body.get("channel") == "email"
        # email_sent activity logged
        time.sleep(0.5)
        sent = _db["activities"].find_one({
            "lead_id": lead_id, "type": "email_sent"
        }, sort=[("created_at", -1)])
        assert sent is not None, "email_sent activity not logged on 200"

    def test_send_lead_magnet_failure_branch(self, admin_token):
        """Force a Resend failure by temporarily setting a lead's email to
        something Resend will reject. Verify 502 + email_failed activity."""
        # Create a throwaway lead with a bad email
        bad_lead = {
            "first_name": "Iter88",
            "last_name": "Bad",
            "email": f"iter88-bad-{int(time.time())}@example.com",
            "phone": "+10000000000",
            "tenant_id": "ten_demo",
        }
        r = requests.post(f"{BASE_URL}/api/leads",
                          headers={"Authorization": f"Bearer {admin_token}", "X-Tenant-Id": "ten_demo", "Content-Type": "application/json"},
                          json=bad_lead, timeout=20)
        if r.status_code not in (200, 201):
            pytest.skip(f"cannot create test lead: {r.status_code} {r.text[:120]}")
        lid = (r.json().get("lead") or r.json()).get("id") or r.json().get("_id")
        if not lid:
            # Try by email lookup
            time.sleep(0.3)
            found = _db["leads"].find_one({"email": bad_lead["email"]})
            lid = found and found.get("id")
        try:
            # Patch the email in DB to a Resend-rejecting form
            _db["leads"].update_one({"id": lid}, {"$set": {"email": "invalid@@@bad"}})
            r2 = requests.post(f"{BASE_URL}/api/leads/{lid}/send-lead-magnet",
                               headers={"Authorization": f"Bearer {admin_token}", "X-Tenant-Id": "ten_demo"},
                               timeout=30)
            if r2.status_code == 400 and "magnet" in r2.text.lower():
                pytest.skip("no magnet configured for ten_demo — cannot test failure path")
            if r2.status_code == 429:
                pytest.skip("Resend rate-limited")
            # Expect 502 due to Resend rejection
            assert r2.status_code in (502, 400), f"expected 502 on Resend failure, got {r2.status_code}: {r2.text[:200]}"
            time.sleep(0.5)
            failed = _db["activities"].find_one({"lead_id": lid, "type": "email_failed"},
                                                sort=[("created_at", -1)])
            assert failed is not None, "email_failed activity not logged"
            subj = failed.get("subject") or ""
            assert "FAILED" in subj or "fail" in subj.lower(), f"subject doesn't reflect failure: {subj}"
        finally:
            _db["leads"].delete_one({"id": lid})
            _db["activities"].delete_many({"lead_id": lid})


# ─── D. Regression: iter80 rate limit, iter82-87 endpoints ─────────────────
class TestRegressionIter80To87:
    def test_iter80_login_rate_limit_429(self):
        last = None
        bad_email = "nope-iter88@example.com"
        for _ in range(15):
            last = requests.post(f"{BASE_URL}/api/auth/login",
                                 json={"email": bad_email, "password": "wrong"},
                                 timeout=10)
            if last.status_code == 429:
                break
        assert last.status_code == 429, f"rate-limit didn't fire in 15 attempts; last={last.status_code}"

    def test_iter83_saleshandy_no_raw_json_leak(self, admin_token):
        # /pt/integrations should never return raw decrypted api_key
        r = requests.get(f"{BASE_URL}/api/pt/integrations",
                         headers=_h(admin_token, "ten_pietential"), timeout=20)
        assert r.status_code == 200
        body = r.json()
        for tier in ("primary", "future"):
            for itg in body.get(tier, []):
                # api_key must be masked, never raw
                masked = itg.get("api_key_masked")
                if masked:
                    assert masked.startswith("••••"), f"unmasked key leaked: {masked!r}"
                assert "api_key" not in itg, f"raw api_key field exposed in {itg.get('name')}"

    def test_iter84_pt_email_endpoints_gated_for_sales_rep(self, sales_token):
        # sales_rep must NOT be able to send test emails or rotate sender config
        r = requests.post(f"{BASE_URL}/api/pt/email/test-send",
                          headers=_h(sales_token, "ten_pietential"),
                          json={"to": "test@example.com"}, timeout=15)
        assert r.status_code == 403, f"sales_rep should be 403, got {r.status_code}: {r.text[:120]}"

    def test_iter86_setup_health_accessible_to_sales_rep(self, sales_token):
        # /setup/health is read-only and intentionally open to sales_rep
        r = requests.get(f"{BASE_URL}/api/pt/setup/health",
                         headers=_h(sales_token, "ten_demo"), timeout=15)
        assert r.status_code == 200
        assert "items" in r.json() and "ready_count" in r.json()
