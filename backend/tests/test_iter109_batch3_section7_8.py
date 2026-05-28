"""iter109 Batch 3 — Section 7 (V9 Train ARIA streaming) + Section 8 (Platform-Ready audit)

Verifies backend contract for V9.1-V9.8 and the backend-side platform checks
F12 (KPIs payload), F19 (auth/me does not leak password_hash), and F20 (admin
route protection at backend role-check level).
"""

import os
import time
import hashlib
import io
import pytest
import requests
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = "Demo1234!"
SARAH_EMAIL = "sarah@demo.com"
SARAH_PASSWORD = "Demo1234!"
PIETENTIAL_EMAIL = "megha@contentvista.com"
PIETENTIAL_PASSWORD = "Piet-4vRQ-lDa2-ttcO"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "genleadai_lms")


@pytest.fixture(scope="module")
def mongo_db():
    client = MongoClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def sarah_token():
    return _login(SARAH_EMAIL, SARAH_PASSWORD)


@pytest.fixture(scope="module")
def pietential_token():
    return _login(PIETENTIAL_EMAIL, PIETENTIAL_PASSWORD)


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "X-Tenant-Id": "ten_demo"}


@pytest.fixture(scope="module")
def pietential_headers(pietential_token):
    return {"Authorization": f"Bearer {pietential_token}", "X-Tenant-Id": "ten_pietential"}


# ─────────────────────────  SECTION 7 — V9 criteria  ─────────────────────────
class TestV9TrainAriaStreaming:
    """V9.1-V9.8 backend contract for Train ARIA streaming extraction."""

    SAMPLE_DOC = (
        "TEST_iter109_batch3 — Acme SaaS sells AI sales agents to SMB CEOs. "
        "Our differentiator: 24x7 instinct-led outreach. We solve cold-pipeline anxiety. "
        "ICP: 10-50 employees SaaS. Voice: candid friendly. Pricing pushback: ROI in 14 days. "
        "Calendar: https://cal.com/aria/demo. Qualification: budget, authority, need, timeline."
    ) * 8  # ~3KB

    def test_v91_upload_returns_job_id_quickly(self, admin_headers):
        """V9.1 — Upload returns job_id with status=queued in < ~2s."""
        fname = "TEST_iter109_batch3_v91.txt"
        files = {"file": (fname, io.BytesIO(self.SAMPLE_DOC.encode("utf-8")), "text/plain")}
        hdrs = {k: v for k, v in admin_headers.items() if k != "Content-Type"}
        t0 = time.time()
        r = requests.post(f"{API}/aria/training-profile/extract-from-document", files=files, headers=hdrs, timeout=30)
        dt_ms = int((time.time() - t0) * 1000)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        data = r.json()
        assert "job_id" in data, data
        assert data.get("status") in ("queued", "extracting", "done"), data
        # cached or not — both flows must return job_id
        pytest.shared_job_id = data["job_id"]
        pytest.shared_cached_first = data.get("cached") is True
        print(f"V9.1 upload returned in {dt_ms}ms with job_id={data['job_id']} cached={data.get('cached')}")

    def test_v92_job_status_has_phase_label(self, admin_headers):
        """V9.2 — Polling returns phase label transitions."""
        job_id = getattr(pytest, "shared_job_id", None)
        if not job_id:
            pytest.skip("V9.1 did not set job_id")
        phases_seen = set()
        deadline = time.time() + 30
        status = None
        while time.time() < deadline:
            r = requests.get(f"{API}/aria/training-profile/extract-job/{job_id}", headers=admin_headers, timeout=10)
            assert r.status_code == 200, r.text
            j = r.json()
            if j.get("phase"):
                phases_seen.add(j["phase"])
            status = j.get("status")
            if status in ("done", "error"):
                break
            time.sleep(0.5)
        assert status == "done", f"extraction did not finish: status={status}"
        print(f"V9.2 phases seen: {phases_seen}, terminal status={status}")
        # We accept >=1 phase from cached path; >=2 from non-cached.
        assert len(phases_seen) >= 1, "expected at least one phase label"

    def test_v93_extracted_fields_returned(self, admin_headers):
        """V9.3 — done response carries the extracted profile fields."""
        job_id = getattr(pytest, "shared_job_id", None)
        if not job_id:
            pytest.skip("V9.1 missing job_id")
        r = requests.get(f"{API}/aria/training-profile/extract-job/{job_id}", headers=admin_headers, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "done", data
        # extracted_fields is a map of field_name -> value
        extracted = data.get("extracted_fields") or {}
        print(f"V9.3 fields_extracted={data.get('fields_extracted')} extracted_keys={list(extracted.keys())}")
        assert isinstance(extracted, dict)
        filled = [k for k, v in extracted.items() if v]
        assert len(filled) >= 4, f"expected ≥4 filled fields, got {len(filled)}: {filled}"

    def test_v94_slow_warn_after_90s(self, admin_headers, mongo_db):
        """V9.4 — slow_warn flips true once started_at is >90s old AND job is still running."""
        col = mongo_db["training_extraction_jobs"]
        # fabricate a fake queued job with started_at 2 minutes in the past
        fake_id = f"TEST_iter109_batch3_slow_{int(time.time())}"
        past = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat().replace("+00:00", "Z")
        col.insert_one({
            "job_id": fake_id,
            "tenant_id": "ten_demo",
            "status": "extracting",
            "phase": "Running OCR on images…",
            "started_at": past,
            "filename": "TEST_slow.txt",
            "is_ocr": True,
        })
        try:
            r = requests.get(f"{API}/aria/training-profile/extract-job/{fake_id}", headers=admin_headers, timeout=10)
            assert r.status_code == 200, r.text
            data = r.json()
            assert data.get("slow_warn") is True, f"expected slow_warn=True, got {data}"
            assert data.get("elapsed_seconds", 0) > 90
            print(f"V9.4 slow_warn={data['slow_warn']} elapsed={data['elapsed_seconds']}s")
        finally:
            col.delete_one({"job_id": fake_id})

    def test_v95_job_persists_after_navigation(self, admin_headers):
        """V9.5 — Backend still tracks the job even after frontend resets."""
        job_id = getattr(pytest, "shared_job_id", None)
        if not job_id:
            pytest.skip("no shared job_id")
        r = requests.get(f"{API}/aria/training-profile/extract-job/{job_id}", headers=admin_headers, timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("job_id") == job_id
        assert data.get("status") in ("done", "extracting", "queued"), data
        print(f"V9.5 job {job_id} still retrievable: status={data.get('status')}")

    def test_v96_duplicate_upload_returns_cached_true(self, admin_headers):
        """V9.6 — Second upload of same file content returns cached:true immediately."""
        fname = "TEST_iter109_batch3_v96.txt"
        files = {"file": (fname, io.BytesIO(self.SAMPLE_DOC.encode("utf-8")), "text/plain")}
        hdrs = {k: v for k, v in admin_headers.items() if k != "Content-Type"}
        t0 = time.time()
        r = requests.post(f"{API}/aria/training-profile/extract-from-document", files=files, headers=hdrs, timeout=15)
        dt_ms = int((time.time() - t0) * 1000)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("cached") is True, f"expected cached=True on duplicate, got {data}"
        assert data.get("status") == "done"
        print(f"V9.6 duplicate upload returned in {dt_ms}ms cached={data.get('cached')}")

    def test_v97_completeness_reflects_profile(self, admin_headers):
        """V9.7 — PUT training-profile updates and GET completeness reflects %."""
        # current state
        r = requests.get(f"{API}/aria/training-profile", headers=admin_headers, timeout=10)
        assert r.status_code == 200, r.text
        current = (r.json().get("data") or {})

        # toggle calendar_link to force a known delta
        new_link = "https://cal.com/aria/test_v97"
        body = {**current, "calendar_link": new_link}
        r2 = requests.put(f"{API}/aria/training-profile", json=body, headers=admin_headers, timeout=15)
        assert r2.status_code == 200, r2.text

        r3 = requests.get(f"{API}/aria/training-profile/completeness", headers=admin_headers, timeout=10)
        assert r3.status_code == 200, r3.text
        comp = r3.json()
        assert "percent" in comp and "missing" in comp and "filled_count" in comp and "total" in comp
        # the filled_count must equal total - len(missing)
        assert comp["filled_count"] + len(comp["missing"]) == comp["total"]
        expected_pct = int(round(comp["filled_count"] / comp["total"] * 100))
        assert comp["percent"] == expected_pct, comp
        print(f"V9.7 completeness pct={comp['percent']} filled={comp['filled_count']}/{comp['total']}")

    def test_v98_nudge_points_to_first_missing(self, admin_headers, mongo_db):
        """V9.8 — Force a missing field; nudge.field == missing[0].field."""
        # Clear calendar_link by direct PUT to simulate missing
        r = requests.get(f"{API}/aria/training-profile", headers=admin_headers, timeout=10)
        current = r.json().get("data") or {}
        body = {**current, "calendar_link": "", "qualification_questions": []}
        r2 = requests.put(f"{API}/aria/training-profile", json=body, headers=admin_headers, timeout=15)
        assert r2.status_code == 200

        r3 = requests.get(f"{API}/aria/training-profile/completeness", headers=admin_headers, timeout=10)
        assert r3.status_code == 200
        comp = r3.json()
        assert comp.get("missing"), "expected at least one missing field"
        first_missing = comp["missing"][0]
        nudge = comp.get("nudge")
        assert nudge is not None, comp
        assert nudge["field"] == first_missing["field"]
        assert nudge["section"] == first_missing["section"]
        print(f"V9.8 nudge points to first missing: {nudge['field']} section={nudge['section']}")

        # restore for downstream consistency
        requests.put(f"{API}/aria/training-profile", json=current, headers=admin_headers, timeout=15)


# ─────────────────────────  SECTION 8 — F12 / F19 / F20  ─────────────────────────
class TestPlatformReadyAudit:
    """F12: KPI shape. F19: /auth/me leak. F20: /admin role guard."""

    def test_f12_kpis_real_db_numbers_hybrid(self, admin_headers, mongo_db):
        """F12 — ten_demo KPIs reflect DB counts."""
        r = requests.get(f"{API}/aria/command-center/kpis", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("mode") == "hybrid", data
        items = data.get("items") or []
        keys = {it["key"]: it for it in items}
        for k in ("total_leads_plus_prospects", "instinct_signals", "calls_booked_today", "aria_actions_today"):
            assert k in keys, f"missing kpi {k}: {keys.keys()}"
        # cross-check total leads vs Mongo
        leads_count = mongo_db["leads"].count_documents({"tenant_id": "ten_demo"})
        accounts_count = mongo_db["accounts"].count_documents({"tenant_id": "ten_demo"}) if "accounts" in mongo_db.list_collection_names() else 0
        expected_total = leads_count + accounts_count
        actual = keys["total_leads_plus_prospects"]["value"]
        assert actual in (expected_total, leads_count), (
            f"kpi.total_leads_plus_prospects={actual} expected≈{expected_total} (leads={leads_count} accounts={accounts_count})"
        )
        print(f"F12 hybrid KPIs ok: total_leads={actual} (leads={leads_count} accounts={accounts_count})")

    def test_f12_kpis_b2b(self, pietential_headers):
        r = requests.get(f"{API}/aria/command-center/kpis", headers=pietential_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("mode") == "b2b", data
        items = data.get("items") or []
        keys = {it["key"] for it in items}
        for k in ("signals_today", "prospects_scanned", "high_conf_signals", "cards_actioned"):
            assert k in keys, f"missing B2B kpi {k}: {keys}"
        print(f"F12 b2b KPIs ok: {keys}")

    def test_f19_auth_me_does_not_return_password_hash(self, admin_token):
        r = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {admin_token}"}, timeout=10)
        assert r.status_code == 200, r.text
        body = r.json()
        # Hard requirement
        assert "password_hash" not in body, f"auth/me leaked password_hash: {body}"
        # also no _id
        assert "_id" not in body, f"auth/me leaked _id: {body}"
        # Verify it returns expected safe fields
        for k in ("id", "email", "role"):
            assert k in body, body
        print(f"F19 auth/me keys: {list(body.keys())}")

    def test_f20_admin_routes_block_non_master_admin(self, sarah_token):
        """F20 — sales_rep cannot hit admin-only API endpoints."""
        hdrs = {"Authorization": f"Bearer {sarah_token}"}
        # try a couple of admin-only endpoints
        candidate_urls = [
            f"{API}/admin/deployments",
            f"{API}/admin/revenue/summary",
            f"{API}/admin/workspaces",
        ]
        blocked = 0
        tried = 0
        for url in candidate_urls:
            r = requests.get(url, headers=hdrs, timeout=10)
            tried += 1
            # 401/403/404(unregistered)→ accept 401/403 as blocked. 200 is a leak.
            print(f"F20 GET {url} -> {r.status_code}")
            if r.status_code in (401, 403):
                blocked += 1
            elif r.status_code == 404:
                # endpoint may not exist; count as not-leaked
                blocked += 1
            else:
                assert r.status_code != 200, f"admin endpoint {url} returned 200 to sales_rep"
        assert blocked == tried, f"only {blocked}/{tried} admin endpoints blocked"

    def test_f19b_login_response_no_password_hash(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
        assert r.status_code == 200
        body = r.json()
        # walk dict for any leaked secret keys
        flat = str(body)
        assert "password_hash" not in flat, "login response leaks password_hash"
        assert "$2b$" not in flat and "$2a$" not in flat, "login response contains bcrypt hash"
        print("F19b login response is clean of password_hash/bcrypt")
