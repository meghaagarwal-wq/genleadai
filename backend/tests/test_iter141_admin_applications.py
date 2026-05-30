"""iter141 — Admin /api/applications surface + V19 backend tests.

Covers: list/get/patch-status/create-workspace, role guards (master_admin),
validation, no _id leak, tenants collection persistence, public submit no-op
when Slack/WhatsApp env vars unset.
"""
import os
import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = "Demo1234!"
REP_EMAIL = "sarah@demo.com"
REP_PASSWORD = "Demo1234!"

VALID_APP = {
    "full_name": "TEST_Iter141 Admin Flow",
    "work_email": "test_iter141_admin@example.com",
    "role": "Founder",
    "country": "India",
    "company_name": "TEST_Iter141Co",
    "company_url": "iter141.example.com",
    "industry": "SaaS",
    "employees": "6-20",
    "revenue": "$100K-$500K",
    "current_setup": "Manual outbound via email.",
    "channels": ["Email"],
    "current_volume": "~50/week",
    "biggest_pain": "Slow follow-up rhythm needs automation.",
    "goal": "Hit 3x reply rate with consistent cadence.",
    "timeline": "1-3_months",
    "budget_band": "10k_50k",
    "ready_to_start": True,
}


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def rep_token():
    return _login(REP_EMAIL, REP_PASSWORD)


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def rep_headers(rep_token):
    return {"Authorization": f"Bearer {rep_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def seeded_app_id():
    """Seed a fresh application via public endpoint and return id."""
    r = requests.post(f"{BASE_URL}/api/applications", json=VALID_APP)
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ── Public submit regression (Slack/WhatsApp not configured → silent no-op) ──

def test_public_submit_still_works_no_slack_no_whatsapp():
    payload = dict(VALID_APP, work_email="test_iter141_public_regression@example.com")
    r = requests.post(f"{BASE_URL}/api/applications", json=payload)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["id"].startswith("app_")
    assert data["full_name"] == payload["full_name"]
    assert data["company_name"] == payload["company_name"]


# ── Role guards (V19) ──

def test_list_requires_auth():
    r = requests.get(f"{BASE_URL}/api/applications?status=new")
    assert r.status_code in (401, 403)


def test_list_forbidden_for_sales_rep(rep_headers):
    r = requests.get(f"{BASE_URL}/api/applications?status=new", headers=rep_headers)
    assert r.status_code == 403, r.text


def test_get_forbidden_for_sales_rep(rep_headers, seeded_app_id):
    r = requests.get(f"{BASE_URL}/api/applications/{seeded_app_id}", headers=rep_headers)
    assert r.status_code == 403


def test_patch_status_forbidden_for_sales_rep(rep_headers, seeded_app_id):
    r = requests.patch(
        f"{BASE_URL}/api/applications/{seeded_app_id}/status",
        json={"status": "reviewing"},
        headers=rep_headers,
    )
    assert r.status_code == 403


# ── Admin list / get ──

def test_admin_list_new_returns_items_counts_total(admin_headers, seeded_app_id):
    r = requests.get(f"{BASE_URL}/api/applications?status=new", headers=admin_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "items" in data and "counts" in data and "total" in data
    assert isinstance(data["items"], list)
    assert isinstance(data["counts"], dict)
    # All expected status keys present in counts
    for k in ["new", "reviewing", "qualified", "not_fit", "onboarded", "all"]:
        assert k in data["counts"]
    # Items should not leak _id
    for item in data["items"]:
        assert "_id" not in item


def test_admin_list_all_status_returns_everything(admin_headers):
    r = requests.get(f"{BASE_URL}/api/applications?status=all", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == data["counts"]["all"]


def test_admin_list_invalid_status_returns_400(admin_headers):
    r = requests.get(f"{BASE_URL}/api/applications?status=WHATEVER", headers=admin_headers)
    assert r.status_code == 400


def test_admin_get_returns_full_doc_no_id_leak(admin_headers, seeded_app_id):
    r = requests.get(f"{BASE_URL}/api/applications/{seeded_app_id}", headers=admin_headers)
    assert r.status_code == 200, r.text
    doc = r.json()
    assert doc["id"] == seeded_app_id
    assert doc["full_name"] == VALID_APP["full_name"]
    assert doc["company_name"] == VALID_APP["company_name"]
    assert doc["work_email"] == VALID_APP["work_email"].lower()
    assert "_id" not in doc
    assert "_ts_unix" not in doc
    assert "ip_hash" not in doc


def test_admin_get_unknown_id_returns_404(admin_headers):
    r = requests.get(f"{BASE_URL}/api/applications/app_does_not_exist_xx", headers=admin_headers)
    assert r.status_code == 404


# ── Patch status ──

def test_patch_status_reviewing_sets_last_reviewed_by(admin_headers, seeded_app_id):
    r = requests.patch(
        f"{BASE_URL}/api/applications/{seeded_app_id}/status",
        json={"status": "reviewing", "note": "Reviewing TEST flow"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    doc = r.json()
    assert doc["status"] == "reviewing"
    assert doc.get("last_reviewed_by") == ADMIN_EMAIL
    assert "_id" not in doc

    # Verify persisted via GET
    g = requests.get(f"{BASE_URL}/api/applications/{seeded_app_id}", headers=admin_headers)
    assert g.status_code == 200
    assert g.json()["status"] == "reviewing"


def test_patch_status_bad_value_returns_400(admin_headers, seeded_app_id):
    r = requests.patch(
        f"{BASE_URL}/api/applications/{seeded_app_id}/status",
        json={"status": "WHATEVER"},
        headers=admin_headers,
    )
    assert r.status_code == 400


def test_patch_status_unknown_id_returns_404(admin_headers):
    r = requests.patch(
        f"{BASE_URL}/api/applications/app_unknown_xx/status",
        json={"status": "qualified"},
        headers=admin_headers,
    )
    assert r.status_code == 404


# ── Create workspace ──

def test_create_workspace_provisions_tenant_and_flips_status(admin_headers, seeded_app_id):
    r = requests.post(
        f"{BASE_URL}/api/applications/{seeded_app_id}/create-workspace",
        json={"workspace_name": "TEST_Iter141Workspace", "mode": "hybrid", "invite_email": False},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["workspace_id"].startswith("ws_")
    assert out["mode"] == "hybrid"
    assert out["invite_token"]
    assert out["invite_url"].endswith(out["invite_token"])
    assert out["invited_email_sent"] is False

    # Application should now be 'onboarded'
    g = requests.get(f"{BASE_URL}/api/applications/{seeded_app_id}", headers=admin_headers)
    assert g.status_code == 200
    gd = g.json()
    assert gd["status"] == "onboarded"
    assert gd.get("onboarded_workspace_id") == out["workspace_id"]


def test_create_workspace_validation_short_name(admin_headers, seeded_app_id):
    r = requests.post(
        f"{BASE_URL}/api/applications/{seeded_app_id}/create-workspace",
        json={"workspace_name": "x", "mode": "b2b", "invite_email": False},
        headers=admin_headers,
    )
    assert r.status_code == 422


def test_create_workspace_validation_bad_mode(admin_headers, seeded_app_id):
    r = requests.post(
        f"{BASE_URL}/api/applications/{seeded_app_id}/create-workspace",
        json={"workspace_name": "TEST_Iter141Modeguard", "mode": "enterprise", "invite_email": False},
        headers=admin_headers,
    )
    assert r.status_code == 422


def test_create_workspace_unknown_app_returns_404(admin_headers):
    r = requests.post(
        f"{BASE_URL}/api/applications/app_unknown_xx/create-workspace",
        json={"workspace_name": "TEST_Iter141UnknownApp", "mode": "b2b", "invite_email": False},
        headers=admin_headers,
    )
    assert r.status_code == 404


def test_create_workspace_forbidden_for_sales_rep(rep_headers):
    # Need a fresh app
    seed = requests.post(f"{BASE_URL}/api/applications", json=dict(
        VALID_APP, work_email="test_iter141_rep_cw@example.com"
    ))
    aid = seed.json()["id"]
    r = requests.post(
        f"{BASE_URL}/api/applications/{aid}/create-workspace",
        json={"workspace_name": "TEST_Iter141RepBlocked", "mode": "b2c", "invite_email": False},
        headers=rep_headers,
    )
    assert r.status_code == 403


# ── Approvals count (V11) ──

def test_approvals_count_endpoint(admin_headers):
    r = requests.get(f"{BASE_URL}/api/approvals/count", headers=admin_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "count" in data
    assert isinstance(data["count"], int)
    assert data["count"] >= 0
