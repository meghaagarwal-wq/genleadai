"""End-to-end backend tests for the Pietential workspace router."""
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


@pytest.fixture(scope="module")
def created(admin_h):
    """Container shared across tests."""
    return {}


# ─── Overview ───────────────────────────────────────────────────────────────
def test_overview_metrics_shape(admin_h):
    r = requests.get(f"{BASE_URL}/api/pt/overview", headers=admin_h, timeout=20)
    assert r.status_code == 200
    body = r.json()
    keys = body["metrics"].keys()
    expected = {
        "total_engaged_leads", "warm_leads", "hot_leads",
        "engaged_accounts_total", "sessions_booked",
        "accounts_requiring_pause", "good_slice_subscribers",
        "lead_magnet_claims", "positive_replies", "accounts_total",
    }
    assert expected.issubset(keys), f"missing keys: {expected - set(keys)}"
    assert "saleshandy_connected" in body["connections"]


# ─── Scoring rules ──────────────────────────────────────────────────────────
def test_scoring_rules_counts(admin_h):
    r = requests.get(f"{BASE_URL}/api/pt/scoring-rules", headers=admin_h, timeout=20)
    assert r.status_code == 200
    data = r.json()
    assert len(data["rules"]) == 19
    assert len(data["stages"]) == 5
    assert len(data["decay"]) == 2
    by_type = {x["event_type"]: x for x in data["rules"]}
    assert by_type["saleshandy.email_clicked"]["score"] == 10
    assert by_type["saleshandy.positive_reply"]["score"] == 30
    assert by_type["saleshandy.positive_reply"].get("trigger_pause") is True
    assert by_type["calendly.session_booked"]["score"] == 80


# ─── Lead create + GET verification ─────────────────────────────────────────
def test_create_lead_and_company(admin_h, created):
    suffix = uuid.uuid4().hex[:8]
    payload = {
        "first_name": "TEST_Ada",
        "email": f"TEST_ada_{suffix}@example.com",
        "company_name": f"TEST_PT_Acme_{suffix}",
        "title": "VP People Analytics",
    }
    r = requests.post(f"{BASE_URL}/api/pt/leads", json=payload, headers=admin_h, timeout=20)
    assert r.status_code == 200, r.text
    lead = r.json()["lead"]
    created["lead_id"] = lead["id"]
    created["company_id"] = lead["company_id"]
    created["email"] = lead["email"]
    created["company_name"] = payload["company_name"]
    assert lead["email"] == payload["email"].lower()
    assert lead["score"] == 0 and lead["stage"] == "cold"
    assert lead["company_id"]

    # GET list contains it
    rl = requests.get(f"{BASE_URL}/api/pt/leads", headers=admin_h, timeout=20)
    assert rl.status_code == 200
    ids = [x["id"] for x in rl.json()["leads"]]
    assert lead["id"] in ids

    # GET detail returns relations
    rd = requests.get(f"{BASE_URL}/api/pt/leads/{lead['id']}", headers=admin_h, timeout=20)
    assert rd.status_code == 200
    detail = rd.json()
    for k in ("lead", "company", "events", "notes", "score_breakdown", "recommendation"):
        assert k in detail


# ─── Scoring engine: clicks + positive reply cascade ────────────────────────
def test_scoring_engine_warm_then_hot(admin_h, created):
    lid = created["lead_id"]
    # +10 click
    r1 = requests.post(f"{BASE_URL}/api/pt/events", headers=admin_h,
                      json={"lead_id": lid, "event_type": "saleshandy.email_clicked"}, timeout=20)
    assert r1.status_code == 200
    assert r1.json()["lead"]["score"] == 10
    assert r1.json()["lead"]["stage"] == "cold"
    assert r1.json()["lead"]["latest_signal"] == "Email link clicked"

    # second click → 20, warm
    r2 = requests.post(f"{BASE_URL}/api/pt/events", headers=admin_h,
                      json={"lead_id": lid, "event_type": "saleshandy.email_clicked"}, timeout=20)
    assert r2.json()["lead"]["score"] == 20
    assert r2.json()["lead"]["stage"] == "warm"

    # positive_reply +30 → 50, hot, pause + tasks
    r3 = requests.post(f"{BASE_URL}/api/pt/events", headers=admin_h,
                      json={"lead_id": lid, "event_type": "saleshandy.positive_reply"}, timeout=20)
    assert r3.status_code == 200
    body = r3.json()
    assert body["lead"]["score"] == 50
    assert body["lead"]["stage"] == "hot"
    assert body["company"]["pause_required"] is True

    # auto-tasks created
    rt = requests.get(f"{BASE_URL}/api/pt/tasks", headers=admin_h, params={"lead_id": lid}, timeout=20)
    titles = [t["title"] for t in rt.json()["tasks"]]
    assert any("Pause Saleshandy" in t for t in titles)
    assert any("Route positive reply to John" in t for t in titles)
    assert any("Send John personal email" in t for t in titles)
    created["tasks_titles"] = titles


# ─── Companies ──────────────────────────────────────────────────────────────
def test_companies(admin_h, created):
    rl = requests.get(f"{BASE_URL}/api/pt/companies", headers=admin_h, timeout=20)
    assert rl.status_code == 200
    ids = [c["id"] for c in rl.json()["companies"]]
    assert created["company_id"] in ids
    rd = requests.get(f"{BASE_URL}/api/pt/companies/{created['company_id']}", headers=admin_h, timeout=20)
    assert rd.status_code == 200
    body = rd.json()
    assert body["company"]["pause_required"] is True
    assert any(l["id"] == created["lead_id"] for l in body["leads"])


# ─── Tasks ──────────────────────────────────────────────────────────────────
def test_task_patch_to_done(admin_h, created):
    rt = requests.get(f"{BASE_URL}/api/pt/tasks", headers=admin_h, params={"lead_id": created["lead_id"]}, timeout=20)
    tid = rt.json()["tasks"][0]["id"]
    rp = requests.patch(f"{BASE_URL}/api/pt/tasks/{tid}", headers=admin_h, json={"status": "done"}, timeout=20)
    assert rp.status_code == 200
    assert rp.json()["task"]["status"] == "done"


# ─── Notes ──────────────────────────────────────────────────────────────────
def test_notes_create_get(admin_h, created):
    r = requests.post(f"{BASE_URL}/api/pt/notes", headers=admin_h,
                     json={"lead_id": created["lead_id"], "note": "TEST_pt note"}, timeout=20)
    assert r.status_code == 200
    rg = requests.get(f"{BASE_URL}/api/pt/notes", headers=admin_h, params={"lead_id": created["lead_id"]}, timeout=20)
    assert any(n["note"] == "TEST_pt note" for n in rg.json()["notes"])


# ─── Bulk create ────────────────────────────────────────────────────────────
def test_bulk_create_then_dup_fail(admin_h):
    suf = uuid.uuid4().hex[:6]
    leads = [
        {"first_name": "B1", "email": f"TEST_b1_{suf}@x.com", "company_name": f"TEST_BulkCo_{suf}"},
        {"first_name": "B2", "email": f"TEST_b2_{suf}@x.com", "company_name": f"TEST_BulkCo_{suf}"},
        {"first_name": "B3", "email": f"TEST_b3_{suf}@x.com", "company": f"TEST_BulkCo_{suf}"},
    ]
    r = requests.post(f"{BASE_URL}/api/pt/leads/bulk", headers=admin_h, json={"leads": leads}, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] == 3 and body["failed"] == 0

    r2 = requests.post(f"{BASE_URL}/api/pt/leads/bulk", headers=admin_h, json={"leads": leads}, timeout=30)
    body2 = r2.json()
    assert body2["created"] == 0 and body2["failed"] == 3
    assert any("already exists" in (e.get("reason") or "").lower() for e in body2["errors"])


# ─── Webhooks ───────────────────────────────────────────────────────────────
def test_webhooks_saleshandy_then_calendly(admin_h):
    suf = uuid.uuid4().hex[:6]
    email = f"TEST_webhook_{suf}@test.com"
    r = requests.post(f"{BASE_URL}/api/pt/webhooks/saleshandy/click", json={"email": email}, timeout=20)
    assert r.status_code == 200
    assert r.json()["lead"]["score"] == 10

    r2 = requests.post(f"{BASE_URL}/api/pt/webhooks/calendly/booked", json={"email": email, "company_name": f"TEST_WHCo_{suf}"}, timeout=20)
    assert r2.status_code == 200
    body = r2.json()
    assert body["lead"]["score"] == 90  # 10 + 80
    # 90 falls in 'engaged' band (70-109); session_pilot starts at 110
    assert body["lead"]["stage"] == "engaged"
    # company may be None if no company_name on initial create — verify via company endpoint
    if body.get("company"):
        assert body["company"]["pause_required"] is True


# ─── Integrations ───────────────────────────────────────────────────────────
def test_integrations_upsert_and_list(admin_h):
    r = requests.post(f"{BASE_URL}/api/pt/integrations", headers=admin_h,
                     json={"name": "saleshandy", "api_key": "test123", "status": "connected"}, timeout=20)
    assert r.status_code == 200
    assert "api_key" not in r.json()["integration"]  # redacted

    rl = requests.get(f"{BASE_URL}/api/pt/integrations", headers=admin_h, timeout=20)
    integs = rl.json()["integrations"]
    assert len(integs) == 13
    sh = next(i for i in integs if i["name"] == "saleshandy")
    assert sh["status"] == "connected"
    assert "api_key" not in sh


# ─── Reports ────────────────────────────────────────────────────────────────
def test_reports_weekly_monthly(admin_h):
    rw = requests.get(f"{BASE_URL}/api/pt/reports/weekly", headers=admin_h, timeout=20)
    assert rw.status_code == 200
    assert "metrics" in rw.json()
    rm = requests.get(f"{BASE_URL}/api/pt/reports/monthly", headers=admin_h, timeout=20)
    assert rm.status_code == 200
    body = rm.json()
    for k in ("channel_performance", "title_performance", "industry_performance"):
        assert k in body


# ─── Permissions ────────────────────────────────────────────────────────────
def test_sales_rep_can_patch_company(srep_h, admin_h, created):
    r = requests.patch(f"{BASE_URL}/api/pt/companies/{created['company_id']}", headers=srep_h,
                      json={"owner": "John"}, timeout=20)
    assert r.status_code == 200, r.text


def test_admin_can_delete_lead(admin_h):
    suf = uuid.uuid4().hex[:6]
    r = requests.post(f"{BASE_URL}/api/pt/leads", headers=admin_h,
                     json={"first_name": "TEST_Del", "email": f"TEST_del_{suf}@x.com"}, timeout=20)
    lid = r.json()["lead"]["id"]
    rd = requests.delete(f"{BASE_URL}/api/pt/leads/{lid}", headers=admin_h, timeout=20)
    assert rd.status_code == 200
    rg = requests.get(f"{BASE_URL}/api/pt/leads/{lid}", headers=admin_h, timeout=20)
    assert rg.status_code == 404
