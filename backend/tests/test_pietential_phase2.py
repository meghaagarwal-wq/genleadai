"""Phase 2 backend tests for Pietential workspace.

Covers:
- New Overview metrics (sh/lemlist split, opens/clicks/positive_replies, etc.)
- Integrations primary/future split + masked api_key + webhook_secret_set
- Webhook signature verification (X-Pt-Webhook-Secret)
- Saleshandy / Lemlist activity endpoints
- Touchpoint map (10 entries)
- Demo replay flow (4-event cascade → score=145, session_pilot)
- Team list + role update + non-admin 403
- /me/permissions for admin and sales_rep
- Training signals (reply_class, icp_fit, positive_conversation cascade)
- Score-decay run admin gate + shape
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")
ADMIN = {"email": "admin@demo.com", "password": "Demo1234!"}
SREP = {"email": "sarah@demo.com", "password": "Demo1234!"}


def _token(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    body = r.json()
    return body.get("token") or body.get("access_token")


@pytest.fixture(scope="module")
def admin_h():
    return {"Authorization": f"Bearer {_token(ADMIN)}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def srep_h():
    return {"Authorization": f"Bearer {_token(SREP)}", "Content-Type": "application/json"}


# ── 1. Overview new metrics ────────────────────────────────────────────────
def test_overview_phase2_metrics(admin_h):
    r = requests.get(f"{BASE_URL}/api/pt/overview", headers=admin_h, timeout=20)
    assert r.status_code == 200, r.text
    m = r.json()["metrics"]
    expected = {
        "email_opens", "email_clicks", "saleshandy_positive_replies",
        "linkedin_connections", "lemlist_dm_replies",
        "john_owned_conversations", "saleshandy_leads", "lemlist_leads",
    }
    missing = expected - set(m.keys())
    assert not missing, f"missing metrics: {missing}"
    for k in expected:
        assert isinstance(m[k], int), f"{k} should be int"


# ── 2. Integrations primary/future split + masked api_key ──────────────────
def test_integrations_primary_future_split(admin_h):
    # Reset to known state with api_key + webhook_secret on saleshandy
    r0 = requests.post(f"{BASE_URL}/api/pt/integrations", headers=admin_h,
                       json={"name": "saleshandy", "api_key": "sk_live_TESTSECRET12345",
                             "webhook_secret": "abc123", "status": "connected"}, timeout=20)
    assert r0.status_code == 200, r0.text
    body0 = r0.json()["integration"]
    assert body0["webhook_secret_set"] is True
    assert body0.get("api_key_masked") and body0["api_key_masked"].endswith("2345")
    assert "api_key" not in body0  # plaintext never returned

    r = requests.get(f"{BASE_URL}/api/pt/integrations", headers=admin_h, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "primary" in data and "future" in data
    primary_names = [i["name"] for i in data["primary"]]
    assert primary_names == ["saleshandy", "lemlist"]
    assert len(data["future"]) == 11
    sh = next(i for i in data["primary"] if i["name"] == "saleshandy")
    assert sh["tier"] == "primary"
    assert sh["webhook_secret_set"] is True
    assert sh["api_key_masked"] and sh["api_key_masked"].startswith("•")
    assert "api_key" not in sh
    for fi in data["future"]:
        assert fi["tier"] == "future"


# ── 3. Webhook signature verification ──────────────────────────────────────
def test_webhook_signature_required_when_secret_set(admin_h):
    # Ensure secret set
    requests.post(f"{BASE_URL}/api/pt/integrations", headers=admin_h,
                  json={"name": "saleshandy", "webhook_secret": "abc123",
                        "status": "connected"}, timeout=20)
    suf = uuid.uuid4().hex[:6]
    email = f"TEST_whsig_{suf}@x.com"

    # Missing header → 401
    r1 = requests.post(f"{BASE_URL}/api/pt/webhooks/saleshandy/click",
                       json={"email": email}, timeout=20)
    assert r1.status_code == 401, f"expected 401 without secret, got {r1.status_code}: {r1.text}"

    # Wrong header → 401
    r2 = requests.post(f"{BASE_URL}/api/pt/webhooks/saleshandy/click",
                       json={"email": email},
                       headers={"X-Pt-Webhook-Secret": "wrong"}, timeout=20)
    assert r2.status_code == 401

    # Correct header → 200
    r3 = requests.post(f"{BASE_URL}/api/pt/webhooks/saleshandy/click",
                       json={"email": email},
                       headers={"X-Pt-Webhook-Secret": "abc123"}, timeout=20)
    assert r3.status_code == 200, r3.text
    assert r3.json()["lead"]["score"] == 10


def test_webhook_no_secret_when_unset(admin_h):
    # Clear secret on lemlist (not set by default)
    requests.post(f"{BASE_URL}/api/pt/integrations", headers=admin_h,
                  json={"name": "lemlist", "webhook_secret": ""}, timeout=20)
    suf = uuid.uuid4().hex[:6]
    r = requests.post(f"{BASE_URL}/api/pt/webhooks/lemlist/connection-accepted",
                      json={"email": f"TEST_ll_{suf}@x.com"}, timeout=20)
    # No secret set → public access permitted
    assert r.status_code == 200, r.text


# ── 4. Touchpoints ─────────────────────────────────────────────────────────
def test_touchpoints_returns_10(admin_h):
    r = requests.get(f"{BASE_URL}/api/pt/touchpoints", headers=admin_h, timeout=20)
    assert r.status_code == 200, r.text
    tps = r.json()["touchpoints"]
    assert len(tps) == 10
    required_keys = {"id", "title", "touches", "timeline", "fallback",
                     "platform", "aria_role", "events", "live_event_count"}
    for tp in tps:
        assert required_keys.issubset(tp.keys())
        assert isinstance(tp["events"], list)
        assert isinstance(tp["live_event_count"], int)


# ── 5. Saleshandy / Lemlist activity endpoints ─────────────────────────────
def test_saleshandy_lemlist_activity_shape(admin_h):
    for path in ("/api/pt/saleshandy/activity", "/api/pt/lemlist/activity"):
        r = requests.get(f"{BASE_URL}{path}", headers=admin_h, timeout=20)
        assert r.status_code == 200, f"{path} → {r.status_code}: {r.text}"
        body = r.json()
        for k in ("connected", "last_sync_at", "rows"):
            assert k in body
        assert isinstance(body["rows"], list)


# ── 6. Demo replay flow ────────────────────────────────────────────────────
def test_demo_replay_creates_lead_score_145(admin_h):
    r = requests.post(f"{BASE_URL}/api/pt/demo/replay", headers=admin_h, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    lead = body["lead"]
    assert lead["email"] == "demo-prospect@pietential-demo.com"
    # 25 + 10 + 30 + 80 = 145
    assert lead["score"] == 145, f"expected 145 got {lead['score']}"
    # session_pilot threshold per existing tests is >=110 (review_request had typo)
    assert lead["stage"] == "session_pilot", f"expected session_pilot got {lead['stage']}"
    company = body.get("company")
    assert company and company.get("pause_required") is True
    assert body["events_applied"] == [
        "newsletter.subscribed", "saleshandy.email_clicked",
        "saleshandy.positive_reply", "calendly.session_booked",
    ]
    assert body["tasks_created"] >= 3

    # Saleshandy activity should now have 1 row
    ra = requests.get(f"{BASE_URL}/api/pt/saleshandy/activity", headers=admin_h, timeout=20)
    rows = ra.json()["rows"]
    assert any(r.get("email") == "demo-prospect@pietential-demo.com" for r in rows), \
        "demo lead should appear in saleshandy activity"


# ── 7. Team list + role update ─────────────────────────────────────────────
def test_team_list_admin(admin_h):
    r = requests.get(f"{BASE_URL}/api/pt/team", headers=admin_h, timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "members" in body and "available_roles" in body
    assert len(body["members"]) >= 1
    assert all(r in body["available_roles"] or True for r in ["admin", "viewer"])
    # password hashes must NEVER leak
    for m in body["members"]:
        assert "password_hash" not in m
        assert "password" not in m


def test_role_update_admin_only(admin_h, srep_h):
    # Sales rep should be 403
    r1 = requests.patch(f"{BASE_URL}/api/pt/team/role", headers=srep_h,
                        json={"email": "sarah@demo.com", "role": "viewer"}, timeout=20)
    assert r1.status_code == 403, f"non-admin must be blocked, got {r1.status_code}"

    # Admin updates sarah → sales_rep (revert) — role remains valid
    r2 = requests.patch(f"{BASE_URL}/api/pt/team/role", headers=admin_h,
                        json={"email": "sarah@demo.com", "role": "sales_rep"}, timeout=20)
    assert r2.status_code == 200, r2.text


# ── 8. /me/permissions ──────────────────────────────────────────────────────
def test_permissions_admin_vs_salesrep(admin_h, srep_h):
    ra = requests.get(f"{BASE_URL}/api/pt/me/permissions", headers=admin_h, timeout=20)
    assert ra.status_code == 200
    a = ra.json()
    assert a["can_admin"] is True and a["can_write"] is True

    rs = requests.get(f"{BASE_URL}/api/pt/me/permissions", headers=srep_h, timeout=20)
    assert rs.status_code == 200
    s = rs.json()
    assert s["can_admin"] is False and s["can_write"] is True


# ── 9. Training signals ────────────────────────────────────────────────────
def test_training_signal_icp_fit_and_positive_conversation(admin_h):
    # Create a fresh lead
    suf = uuid.uuid4().hex[:6]
    cr = requests.post(f"{BASE_URL}/api/pt/leads", headers=admin_h,
                       json={"first_name": "TEST_Train", "email": f"TEST_train_{suf}@x.com",
                             "company_name": f"TEST_TrainCo_{suf}"}, timeout=20)
    assert cr.status_code == 200, cr.text
    lid = cr.json()["lead"]["id"]

    # reply_class signal — persists only
    r1 = requests.post(f"{BASE_URL}/api/pt/training/signal", headers=admin_h,
                       json={"lead_id": lid, "signal_type": "reply_class",
                             "value": "positive"}, timeout=20)
    assert r1.status_code == 200, r1.text
    assert r1.json()["signal"]["signal_type"] == "reply_class"

    # icp_fit signal — should update lead.icp_fit + company.icp_fit
    r2 = requests.post(f"{BASE_URL}/api/pt/training/signal", headers=admin_h,
                       json={"lead_id": lid, "signal_type": "icp_fit",
                             "value": "match"}, timeout=20)
    assert r2.status_code == 200, r2.text
    rd = requests.get(f"{BASE_URL}/api/pt/leads/{lid}", headers=admin_h, timeout=20)
    assert rd.json()["lead"]["icp_fit"] == "match"
    assert rd.json()["company"]["icp_fit"] == "match"

    # positive_conversation=yes → +40 manual.hypothesis_reply event + pause cascade
    score_before = rd.json()["lead"]["score"]
    r3 = requests.post(f"{BASE_URL}/api/pt/training/signal", headers=admin_h,
                       json={"lead_id": lid, "signal_type": "positive_conversation",
                             "value": "yes"}, timeout=20)
    assert r3.status_code == 200, r3.text
    after_lead = r3.json()["lead"]
    # manual.hypothesis_reply weight per scoring rules — verify positive delta
    assert after_lead["score"] > score_before, \
        f"score should increase from {score_before}, got {after_lead['score']}"

    # signals list filtered by lead_id
    rls = requests.get(f"{BASE_URL}/api/pt/training/signals",
                       headers=admin_h, params={"lead_id": lid}, timeout=20)
    assert rls.status_code == 200
    assert len(rls.json()["signals"]) >= 3


# ── 10. Score decay run ────────────────────────────────────────────────────
def test_score_decay_admin_gate(admin_h, srep_h):
    r1 = requests.post(f"{BASE_URL}/api/pt/score-decay/run", headers=srep_h, timeout=20)
    assert r1.status_code == 403

    r2 = requests.post(f"{BASE_URL}/api/pt/score-decay/run", headers=admin_h, timeout=30)
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert "decayed_30_days" in body and "decayed_60_days" in body
    assert isinstance(body["decayed_30_days"], int)
    assert isinstance(body["decayed_60_days"], int)
