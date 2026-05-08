"""Pietential Phase 3 — CSV imports, campaigns, automation logs, manual sync, mapping."""
import io
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")
ADMIN = {"email": "admin@demo.com", "password": "Demo1234!"}
SREP = {"email": "sarah@demo.com", "password": "Demo1234!"}


def _token(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json().get("token") or r.json().get("access_token")


@pytest.fixture(scope="module")
def admin_token():
    return _token(ADMIN)


@pytest.fixture(scope="module")
def admin_h(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin_h_noct(admin_token):
    # multipart/form-data — let requests set the Content-Type
    return {"Authorization": f"Bearer {admin_token}"}


SH_CSV = (
    "First name,Last name,Email,Company,Title,Campaign,Touch number,Opened,Clicked,Replied,Reply sentiment,Unsubscribed,Last activity\n"
    "Maria,Lopez,maria@acmewell.com,AcmeWell,VP People Analytics,Wellbeing Q1,2,Yes,Yes,Yes,positive,No,2026-01-10\n"
    "Luis,Tan,luis@bigwell.com,BigWell,CHRO,Wellbeing Q1,1,Yes,No,No,,No,2026-01-10\n"
)

LL_CSV = (
    "First name,Last name,Email,Company,Title,LinkedIn URL,Campaign,Connection sent,Connection accepted,DM sent,Replied,Reply sentiment,Last activity\n"
    "Maria,Lopez,maria@acmewell.com,AcmeWell,VP People Analytics,https://linkedin.com/in/marialopez,Awareness Jan,Yes,Yes,Yes,Yes,positive,2026-01-12\n"
    "Pat,Sumi,pat@coolco.com,CoolCo,Head of Wellbeing,https://linkedin.com/in/patsumi,Awareness Jan,Yes,No,No,No,,2026-01-12\n"
)


# ─── Saleshandy CSV import ─────────────────────────────────────────────────
def test_saleshandy_csv_import(admin_h_noct):
    files = {"file": ("sh.csv", SH_CSV, "text/csv")}
    r = requests.post(f"{BASE_URL}/api/pt/saleshandy/import-csv", headers=admin_h_noct, files=files, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] == 2, body
    assert body["updated"] == 0
    # Maria: opened+clicked+positive_reply = 3 events; Luis: opened only = 1 event → 4 total
    assert body["events_added"] >= 3
    assert isinstance(body["errors"], list)


def test_saleshandy_csv_reimport_updates(admin_h_noct):
    files = {"file": ("sh.csv", SH_CSV, "text/csv")}
    r = requests.post(f"{BASE_URL}/api/pt/saleshandy/import-csv", headers=admin_h_noct, files=files, timeout=30)
    assert r.status_code == 200
    body = r.json()
    assert body["created"] == 0
    assert body["updated"] == 2


# ─── Lemlist CSV import ────────────────────────────────────────────────────
def test_lemlist_csv_import(admin_h_noct, admin_h):
    files = {"file": ("ll.csv", LL_CSV, "text/csv")}
    r = requests.post(f"{BASE_URL}/api/pt/lemlist/import-csv", headers=admin_h_noct, files=files, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    # Maria already exists as saleshandy lead → updated; Pat is new
    assert body["created"] == 1
    assert body["updated"] == 1
    # Maria connection_accepted=Yes + dm_positive_reply (replied=Yes, sentiment=positive) → 2 events
    assert body["events_added"] >= 2

    # Verify lead has linkedin_url stored (Pat is the new one)
    leads_r = requests.get(f"{BASE_URL}/api/pt/leads", headers=admin_h, timeout=20).json()
    pat = next((l for l in leads_r.get("leads", []) if l["email"] == "pat@coolco.com"), None)
    assert pat is not None, "Pat lead not created from lemlist CSV"
    assert pat.get("linkedin_url") == "https://linkedin.com/in/patsumi"
    assert pat.get("source") == "lemlist"


# ─── Campaigns endpoint ────────────────────────────────────────────────────
def test_campaigns_list_all(admin_h):
    r = requests.get(f"{BASE_URL}/api/pt/campaigns", headers=admin_h, timeout=20)
    assert r.status_code == 200
    body = r.json()
    assert "campaigns" in body
    names = {(c["platform"], c["campaign_name"]) for c in body["campaigns"]}
    assert ("saleshandy", "Wellbeing Q1") in names
    assert ("lemlist", "Awareness Jan") in names
    sh_camp = next(c for c in body["campaigns"] if c["platform"] == "saleshandy" and c["campaign_name"] == "Wellbeing Q1")
    for k in ("lead_count", "opens", "clicks", "replies_pos", "connections", "status", "updated_at"):
        assert k in sh_camp, f"missing {k} in campaign row"
    assert sh_camp["lead_count"] >= 2
    assert sh_camp["opens"] >= 2  # Maria + Luis both opened
    assert sh_camp["clicks"] >= 1  # Maria clicked


def test_campaigns_filter_saleshandy(admin_h):
    r = requests.get(f"{BASE_URL}/api/pt/campaigns?platform=saleshandy", headers=admin_h, timeout=20)
    assert r.status_code == 200
    rows = r.json()["campaigns"]
    assert len(rows) >= 1
    assert all(c["platform"] == "saleshandy" for c in rows)


def test_campaigns_filter_lemlist(admin_h):
    r = requests.get(f"{BASE_URL}/api/pt/campaigns?platform=lemlist", headers=admin_h, timeout=20)
    assert r.status_code == 200
    rows = r.json()["campaigns"]
    assert len(rows) >= 1
    assert all(c["platform"] == "lemlist" for c in rows)


# ─── Automation Logs ───────────────────────────────────────────────────────
def test_logs_list(admin_h):
    r = requests.get(f"{BASE_URL}/api/pt/logs", headers=admin_h, timeout=20)
    assert r.status_code == 200
    body = r.json()
    assert "logs" in body and "counts" in body
    assert body["counts"]["total"] >= 1
    assert "by_kind" in body["counts"]
    for k in ("webhook", "sync", "decay", "csv_import", "rule"):
        assert k in body["counts"]["by_kind"]
    msgs = [l.get("message", "") for l in body["logs"]]
    assert any("Saleshandy CSV" in m for m in msgs), "Saleshandy CSV import log missing"


def test_logs_filter_csv_import(admin_h):
    r = requests.get(f"{BASE_URL}/api/pt/logs?kind=csv_import", headers=admin_h, timeout=20)
    assert r.status_code == 200
    rows = r.json()["logs"]
    assert len(rows) >= 1
    assert all(l["kind"] == "csv_import" for l in rows)


def test_logs_filter_level_info(admin_h):
    r = requests.get(f"{BASE_URL}/api/pt/logs?level=info", headers=admin_h, timeout=20)
    assert r.status_code == 200
    assert all(l["level"] == "info" for l in r.json()["logs"])


def test_logs_filter_level_error_returns_array(admin_h):
    r = requests.get(f"{BASE_URL}/api/pt/logs?level=error", headers=admin_h, timeout=20)
    assert r.status_code == 200
    rows = r.json()["logs"]
    assert isinstance(rows, list)
    assert all(l["level"] == "error" for l in rows)


# ─── Account flags (saleshandy_active / lemlist_active) ────────────────────
def test_account_platform_active_flags(admin_h):
    r = requests.get(f"{BASE_URL}/api/pt/companies", headers=admin_h, timeout=20)
    assert r.status_code == 200
    cos = r.json()["companies"]
    acmewell = next((c for c in cos if c.get("name") == "AcmeWell"), None)
    assert acmewell is not None
    assert acmewell.get("saleshandy_active") is True
    assert acmewell.get("lemlist_active") is True
    bigwell = next((c for c in cos if c.get("name") == "BigWell"), None)
    assert bigwell is not None
    assert bigwell.get("saleshandy_active") is True
    coolco = next((c for c in cos if c.get("name") == "CoolCo"), None)
    assert coolco is not None
    assert coolco.get("lemlist_active") is True


# ─── Manual sync ───────────────────────────────────────────────────────────
def test_manual_sync_without_api_key_400(admin_h):
    # Configure a 'lemlist' integration row WITHOUT an api_key first by deleting key
    # Use plain create with empty api_key path: backend stores empty → trips guard
    requests.post(
        f"{BASE_URL}/api/pt/integrations",
        headers=admin_h,
        json={"name": "lemlist", "api_key": "", "webhook_secret": ""},
        timeout=20,
    )
    r = requests.post(f"{BASE_URL}/api/pt/integrations/lemlist/sync", headers=admin_h, timeout=20)
    assert r.status_code == 400
    detail = r.json().get("detail", "")
    assert "API key" in detail


def test_manual_sync_with_api_key_ok(admin_h):
    # Set saleshandy api_key
    requests.post(
        f"{BASE_URL}/api/pt/integrations",
        headers=admin_h,
        json={"name": "saleshandy", "api_key": "sk_live_TEST_phase3", "webhook_secret": ""},
        timeout=20,
    )
    r = requests.post(f"{BASE_URL}/api/pt/integrations/saleshandy/sync", headers=admin_h, timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert "synced_at" in body and "message" in body
    # Sync log was written
    logs = requests.get(f"{BASE_URL}/api/pt/logs?kind=sync", headers=admin_h, timeout=20).json()["logs"]
    assert any("saleshandy" in (l.get("message") or "").lower() for l in logs)


# ─── Field mapping ─────────────────────────────────────────────────────────
def test_field_mapping_get_default(admin_h):
    r = requests.get(f"{BASE_URL}/api/pt/integrations/saleshandy/mapping", headers=admin_h, timeout=20)
    assert r.status_code == 200
    assert "mapping" in r.json()


def test_field_mapping_post_then_get(admin_h):
    r = requests.post(
        f"{BASE_URL}/api/pt/integrations/mapping",
        headers=admin_h,
        json={"name": "saleshandy", "mapping": {"first_name": "firstname", "email": "Email"}},
        timeout=20,
    )
    assert r.status_code == 200
    assert r.json()["mapping"]["first_name"] == "firstname"

    g = requests.get(f"{BASE_URL}/api/pt/integrations/saleshandy/mapping", headers=admin_h, timeout=20)
    assert g.status_code == 200
    assert g.json()["mapping"]["first_name"] == "firstname"
    assert g.json()["mapping"]["email"] == "Email"


# ─── Phase 1/2 regression smoke ────────────────────────────────────────────
@pytest.mark.parametrize("path", [
    "/api/pt/overview",
    "/api/pt/saleshandy/activity",
    "/api/pt/lemlist/activity",
    "/api/pt/touchpoints",
    "/api/pt/team",
    "/api/pt/training/signal",  # GET? actually POST — switch below
])
def test_regression_routes(admin_h, path):
    if path == "/api/pt/training/signal":
        r = requests.get(f"{BASE_URL}/api/pt/training/signals", headers=admin_h, timeout=20)
    else:
        r = requests.get(f"{BASE_URL}{path}", headers=admin_h, timeout=20)
    assert r.status_code == 200, f"{path} → {r.status_code} {r.text[:200]}"


def test_regression_demo_replay(admin_h):
    r = requests.post(f"{BASE_URL}/api/pt/demo/replay", headers=admin_h, timeout=30)
    assert r.status_code == 200


def test_regression_score_decay_admin(admin_h):
    r = requests.post(f"{BASE_URL}/api/pt/score-decay/run", headers=admin_h, timeout=30)
    assert r.status_code == 200
