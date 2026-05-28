"""iter115 — Full Day Checkup (V1–V35 + Batch hot-leads + Mongo health + Deployment).

Tests all PASS/FAIL blocks demanded by the 102-point pre-deploy sweep:
  AUTH, TENANT, OAUTH, CALL_BOOKING, BATCH, MONGO, DEPLOY.
"""
import os
import time
import uuid
import pytest
import requests
from pymongo import MongoClient

# Load env
with open("/app/backend/.env") as f:
    for line in f:
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v.strip('"').strip("'"))

with open("/app/frontend/.env") as f:
    for line in f:
        if line.startswith("REACT_APP_BACKEND_URL="):
            os.environ["REACT_APP_BACKEND_URL"] = line.split("=", 1)[1].strip()
            break

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": "admin@demo.com", "password": "Demo1234!"}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def hdr_pt(admin_token):
    return {"Authorization": f"Bearer {admin_token}",
            "X-Tenant-Id": "ten_pietential", "Content-Type": "application/json"}


# ─── AUTH block ───
def test_auth_login_success(admin_token):
    assert admin_token and isinstance(admin_token, str)


def test_auth_login_wrong_password():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": "admin@demo.com", "password": "WRONG"}, timeout=20)
    assert r.status_code in (400, 401, 403), r.status_code


def test_auth_change_password_roundtrip(admin_token):
    h = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
    new_pw = "Demo1234!Tmp"
    r = requests.post(f"{BASE}/api/auth/change-password",
                      json={"current_password": "Demo1234!", "new_password": new_pw},
                      headers=h, timeout=20)
    assert r.status_code == 200, r.text
    # login with new
    r2 = requests.post(f"{BASE}/api/auth/login",
                       json={"email": "admin@demo.com", "password": new_pw}, timeout=20)
    assert r2.status_code == 200
    # revert
    tok2 = r2.json()["token"]
    h2 = {"Authorization": f"Bearer {tok2}", "Content-Type": "application/json"}
    r3 = requests.post(f"{BASE}/api/auth/change-password",
                       json={"current_password": new_pw, "new_password": "Demo1234!"},
                       headers=h2, timeout=20)
    assert r3.status_code == 200


# ─── TENANT block ───
def test_tenants_me(admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    r = requests.get(f"{BASE}/api/tenants/me", headers=h, timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert "_id" not in data
    assert "id" in data or "tenant_id" in data or "tenants" in data


def test_tenant_scoping_pietential(hdr_pt):
    r = requests.get(f"{BASE}/api/pt/leads", headers=hdr_pt, timeout=20)
    assert r.status_code == 200, r.text


# ─── UNIVERSAL OAUTH block ───
def test_providers_list(admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    r = requests.get(f"{BASE}/api/integrations/providers/list", headers=h, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    providers = data if isinstance(data, list) else data.get("providers", [])
    assert len(providers) >= 10, f"expected >=10 providers, got {len(providers)}"


def _configure_and_check(hdr_pt, provider):
    # cleanup
    DB.integration_configs.delete_many(
        {"tenant_id": "ten_pietential", "integration_type": provider})
    junk = f"junk_{uuid.uuid4().hex[:8]}"
    r = requests.post(f"{BASE}/api/integrations/{provider}/configure-api-key",
                      json={"api_key": junk}, headers=hdr_pt, timeout=20)
    assert r.status_code in (200, 201), f"{provider} configure: {r.status_code} {r.text}"
    # verify encrypted in DB (field is `integration_type` not `provider`)
    doc = DB.integration_configs.find_one(
        {"tenant_id": "ten_pietential", "integration_type": provider})
    assert doc is not None, f"no doc for {provider}"
    api_key = (doc.get("config") or {}).get("api_key", "")
    assert api_key.startswith("enc::"), f"{provider} api_key not enc:: → {api_key[:20]}"
    # status
    rs = requests.get(f"{BASE}/api/integrations/{provider}/status",
                      headers=hdr_pt, timeout=15)
    assert rs.status_code == 200
    assert rs.json().get("connected") is True
    assert "_id" not in rs.json()
    # delete
    rd = requests.delete(f"{BASE}/api/integrations/{provider}",
                         headers=hdr_pt, timeout=15)
    assert rd.status_code in (200, 204)
    doc2 = DB.integration_configs.find_one(
        {"tenant_id": "ten_pietential", "integration_type": provider})
    assert doc2 is None


def test_proxycurl_oauth_flow(hdr_pt):
    _configure_and_check(hdr_pt, "proxycurl")


def test_serper_oauth_flow(hdr_pt):
    _configure_and_check(hdr_pt, "serper")


def test_google_oauth_url_or_503(hdr_pt):
    r = requests.get(f"{BASE}/api/integrations/google/auth-url",
                     headers=hdr_pt, timeout=15)
    # Either returns 200 with auth URL or 4xx/503 if client_id not configured
    # 412 = "Precondition Failed" — provider not yet configured (expected here)
    assert r.status_code in (200, 400, 404, 412, 503), r.status_code
    if r.status_code == 200:
        body = r.json()
        url = body.get("url") or body.get("auth_url") or ""
        assert "google" in url.lower() or "accounts.google" in url


# ─── CALL BOOKING block ───
def test_call_booking_graceful(hdr_pt):
    # ensure a pt_lead exists
    lead = DB.pt_leads.find_one({"tenant_id": "ten_pietential"})
    assert lead, "no pt_leads"
    lead_id = lead["id"]
    payload = {"start_time": "2026-02-01T10:00:00Z",
               "duration_minutes": 30, "notes": "iter115 checkup"}
    r = requests.post(f"{BASE}/api/call-booking/{lead_id}/book",
                      json=payload, headers=hdr_pt, timeout=30)
    assert r.status_code in (200, 201, 400, 401, 403, 404, 422, 503), \
        f"call-booking unexpected {r.status_code}: {r.text[:200]}"


# ─── BATCH HOT-LEADS block ───
def test_batch_hot_leads_no_keys_aborted(hdr_pt):
    # Clear existing intel_profiles so there are candidates to enrich
    DB.intel_profiles.delete_many({"tenant_id": "ten_pietential"})
    # Ensure no serper/proxycurl keys configured
    DB.integration_configs.delete_many(
        {"tenant_id": "ten_pietential",
         "integration_type": {"$in": ["serper", "proxycurl"]}})
    r = requests.post(f"{BASE}/api/intel/batch/hot-leads",
                      json={"stages": ["hot", "engaged", "session_pilot"],
                            "min_score": 0, "limit": 5,
                            "skip_existing": False},
                      headers=hdr_pt, timeout=60)
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    body = r.json()
    assert body.get("aborted") is True, \
        f"expected aborted=True without keys, got {body}"
    reason = (body.get("reason") or "").lower()
    assert "integrations" in reason or "/app/integrations" in reason


def test_batch_hot_leads_with_key_no_500(hdr_pt):
    # seed serper key
    requests.post(f"{BASE}/api/integrations/serper/configure-api-key",
                  json={"api_key": "junkkey_iter115"},
                  headers=hdr_pt, timeout=15)
    # ensure ≥5 hot pt_leads with score≥0
    hot_count = DB.pt_leads.count_documents(
        {"tenant_id": "ten_pietential", "stage": "hot"})
    if hot_count < 5:
        # promote some leads
        ids = [d["id"] for d in DB.pt_leads.find(
            {"tenant_id": "ten_pietential"}).limit(5)]
        DB.pt_leads.update_many(
            {"id": {"$in": ids}, "tenant_id": "ten_pietential"},
            {"$set": {"stage": "hot", "score": 50}})
    r = requests.post(f"{BASE}/api/intel/batch/hot-leads",
                      json={"stages": ["hot"], "min_score": 0, "limit": 5},
                      headers=hdr_pt, timeout=180)
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    body = r.json()
    # may be aborted=False with results, or graceful errors
    results = body.get("results", [])
    if results:
        for row in results:
            assert "lead_id" in row and "name" in row and "status" in row
            if row["status"] == "succeeded":
                assert "fit_score" in row or "signal_count" in row or "risk_count" in row
    # cleanup key
    DB.integration_configs.delete_many(
        {"tenant_id": "ten_pietential", "provider": "serper"})


def test_batch_hot_leads_skip_existing(hdr_pt):
    # seed serper key + intel_profile for one hot lead
    requests.post(f"{BASE}/api/integrations/serper/configure-api-key",
                  json={"api_key": "junk_skip_test"},
                  headers=hdr_pt, timeout=15)
    hot_leads = list(DB.pt_leads.find(
        {"tenant_id": "ten_pietential", "stage": "hot"}).limit(3))
    if not hot_leads:
        pytest.skip("no hot pt_leads")
    skip_id = hot_leads[0]["id"]
    DB.intel_profiles.delete_many(
        {"tenant_id": "ten_pietential", "lead_id": skip_id})
    DB.intel_profiles.insert_one({
        "id": f"ip_{uuid.uuid4().hex[:10]}",
        "tenant_id": "ten_pietential",
        "lead_id": skip_id,
        "fit_score": 50, "signals": [], "risks": [],
        "created_at": time.time(),
    })
    r = requests.post(f"{BASE}/api/intel/batch/hot-leads",
                      json={"stages": ["hot"], "min_score": 0, "limit": 5,
                            "skip_existing": True},
                      headers=hdr_pt, timeout=180)
    assert r.status_code == 200
    body = r.json()
    results = body.get("results", [])
    ids_in_results = [row.get("lead_id") for row in results]
    assert skip_id not in ids_in_results, \
        f"skip_existing failed: {skip_id} present in {ids_in_results}"
    # cleanup
    DB.intel_profiles.delete_many(
        {"tenant_id": "ten_pietential", "lead_id": skip_id})
    DB.integration_configs.delete_many(
        {"tenant_id": "ten_pietential", "provider": "serper"})


# ─── MONGO HEALTH block (no _id leaks) ───
def test_no_mongo_id_leaks(hdr_pt, admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    lead = DB.pt_leads.find_one({"tenant_id": "ten_pietential"})
    assert lead
    lead_id = lead["id"]
    checks = [
        (f"{BASE}/api/intel/{lead_id}", hdr_pt),
        (f"{BASE}/api/integrations/proxycurl/status", hdr_pt),
        (f"{BASE}/api/pt/leads/{lead_id}", hdr_pt),
        (f"{BASE}/api/tenants/me", h),
    ]
    for url, headers in checks:
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code != 200:
            continue
        body = r.json()
        # recursive _id check
        def walk(x):
            if isinstance(x, dict):
                assert "_id" not in x, f"_id leak in {url}"
                for v in x.values():
                    walk(v)
            elif isinstance(x, list):
                for v in x:
                    walk(v)
        walk(body)


# ─── DEPLOY readiness ───
def test_no_hardcoded_oauth_in_env():
    with open("/app/backend/.env") as f:
        content = f.read()
    # Per Batch 1 rule: no per-tenant OAuth client id/secret in .env
    forbidden = ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
                 "GMAIL_CLIENT_ID", "MICROSOFT_CLIENT_ID",
                 "META_CLIENT_ID", "LINKEDIN_CLIENT_ID",
                 "PROXYCURL_API_KEY", "SERPER_API_KEY"]
    found = [k for k in forbidden if f"\n{k}=" in "\n" + content
             and content.split(f"{k}=", 1)[1].split("\n", 1)[0].strip()]
    assert not found, f"forbidden env keys with values: {found}"


def test_no_localhost_in_frontend_src():
    import subprocess
    r = subprocess.run(
        ["grep", "-rE", "localhost:8001|http://localhost",
         "/app/frontend/src/"],
        capture_output=True, text=True)
    assert r.stdout.strip() == "", f"localhost found in frontend/src:\n{r.stdout}"


def test_all_backend_routes_have_api_prefix():
    import subprocess
    # search for FastAPI route decorators in backend
    r = subprocess.run(
        ["grep", "-rnE",
         "@(app|router|api_router)\\.(get|post|put|delete|patch)\\(",
         "/app/backend/"],
        capture_output=True, text=True)
    bad = []
    for line in r.stdout.splitlines():
        if "/__pycache__/" in line or "/tests/" in line:
            continue
        # extract path argument
        try:
            after = line.split("(", 1)[1]
            path = after.split(",", 1)[0].strip().strip('"').strip("'")
        except Exception:
            continue
        if not path.startswith("/"):
            continue
        # Routes mounted under a router with /api prefix are fine, but raw
        # @app.get("/foo") without /api/ prefix is a violation
        if path.startswith("/api"):
            continue
        # @app vs @router — app routes must start with /api
        if "@app." in line or "@self.app" in line:
            bad.append(line)
    assert not bad, "non-/api @app routes found:\n" + "\n".join(bad[:10])
