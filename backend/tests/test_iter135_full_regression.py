"""Iter 135: Full E2E regression smoke for iter125-iter134 sprint.

Exercises live HTTP endpoints via REACT_APP_BACKEND_URL.
Always sends X-Tenant-Id: ten_demo unless otherwise noted.
"""
import os
import json
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fall back to reading /app/frontend/.env
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass

ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASS = "Demo1234!"
TENANT_ID = "ten_demo"

assert BASE_URL, "REACT_APP_BACKEND_URL must be set"


def _no_mongo_id(obj):
    """Recursive check that no `_id` field leaks."""
    if isinstance(obj, dict):
        if "_id" in obj:
            return False
        return all(_no_mongo_id(v) for v in obj.values())
    if isinstance(obj, list):
        return all(_no_mongo_id(v) for v in obj)
    return True


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def auth(session):
    r = session.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
        timeout=20,
    )
    assert r.status_code == 200, f"login failed {r.status_code} {r.text[:200]}"
    data = r.json()
    token = data.get("token") or data.get("access_token")
    assert token, f"no token in {data}"
    session.headers.update({
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": TENANT_ID,
    })
    return {"token": token, "user": data.get("user")}


# ---------------- Auth & tenant ----------------

def test_login_returns_token(auth):
    assert auth["token"]


def test_tenants_me(session, auth):
    r = session.get(f"{BASE_URL}/api/tenants/me", timeout=15)
    assert r.status_code == 200, r.text[:200]
    data = r.json()
    ids = [t.get("id") for t in (data if isinstance(data, list) else data.get("tenants", []))]
    assert "ten_demo" in ids
    # ten_pietential should also be visible to the master admin
    assert "ten_pietential" in ids


# ---------------- Sidebar counts & pipeline snapshot ----------------

def test_leads_counts(session, auth):
    r = session.get(f"{BASE_URL}/api/leads/counts", timeout=15)
    assert r.status_code == 200, r.text[:200]
    data = r.json()
    for key in ("hot", "warm", "cold"):
        assert key in data, f"missing {key} in {data}"


def test_pipeline_snapshot(session, auth):
    # try canonical endpoints
    candidates = [
        "/api/leads/pipeline-snapshot",
        "/api/leads/pipeline_snapshot",
        "/api/pipeline/snapshot",
    ]
    last = None
    for path in candidates:
        r = session.get(f"{BASE_URL}{path}", timeout=15)
        last = (path, r.status_code, r.text[:200])
        if r.status_code == 200:
            data = r.json()
            assert isinstance(data, (dict, list))
            return
    pytest.fail(f"no pipeline snapshot endpoint worked: {last}")


# ---------------- Leads + Lead 360 ----------------

@pytest.fixture(scope="module")
def lead_id(session, auth):
    r = session.get(f"{BASE_URL}/api/leads?limit=5", timeout=20)
    assert r.status_code == 200, r.text[:200]
    data = r.json()
    items = data if isinstance(data, list) else data.get("items") or data.get("leads") or []
    assert items, "no leads available in ten_demo for testing"
    assert _no_mongo_id(data), "GET /api/leads leaks _id"
    return items[0]["id"]


def test_lead_overview(session, auth, lead_id):
    r = session.get(f"{BASE_URL}/api/leads/{lead_id}", timeout=15)
    assert r.status_code == 200, r.text[:200]
    assert _no_mongo_id(r.json())


def test_lead_intel_profile(session, auth, lead_id):
    r = session.get(f"{BASE_URL}/api/intel/{lead_id}/profile", timeout=20)
    # may legitimately 404 if no intel yet; accept 200 or 404
    assert r.status_code in (200, 404), r.text[:200]
    if r.status_code == 200:
        assert _no_mongo_id(r.json())


def test_lead_conversations(session, auth, lead_id):
    r = session.get(f"{BASE_URL}/api/conversations/lead/{lead_id}", timeout=15)
    assert r.status_code == 200, r.text[:200]
    data = r.json()
    items = data if isinstance(data, list) else data.get("items", [])
    # confirm ASC sort by created_at if present
    times = [m.get("created_at") for m in items if isinstance(m, dict) and m.get("created_at")]
    assert times == sorted(times), "conversation not sorted ASC"
    assert _no_mongo_id(data)


def test_lead_activities(session, auth, lead_id):
    r = session.get(f"{BASE_URL}/api/activities?lead_id={lead_id}", timeout=15)
    assert r.status_code == 200, r.text[:200]


# ---------------- Draft with ARIA + Send ----------------

def test_draft_with_aria_variants(session, auth, lead_id):
    r = session.post(
        f"{BASE_URL}/api/conversations/lead/{lead_id}/draft",
        json={"channel": "email"},
        timeout=120,
    )
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    variants = data.get("variants") or data.get("drafts") or []
    assert isinstance(variants, list) and len(variants) == 3, f"expected 3 variants got {len(variants)}: {data}"


# ---------------- Voice Seeds CRUD ----------------

def test_voice_seeds_crud(session, auth):
    payload = {
        "channel": "email",
        "content": "TEST_iter135 voice seed sample",
        "label": "TEST_iter135",
    }
    r = session.post(f"{BASE_URL}/api/voice-seeds", json=payload, timeout=15)
    assert r.status_code in (200, 201), r.text[:200]
    seed = r.json()
    seed_id = seed.get("id")
    assert seed_id
    assert _no_mongo_id(seed)

    # list active
    r = session.get(f"{BASE_URL}/api/voice-seeds?is_active=true", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert _no_mongo_id(data)

    # update
    r = session.patch(
        f"{BASE_URL}/api/voice-seeds/{seed_id}",
        json={"content": "TEST_iter135 updated"},
        timeout=15,
    )
    assert r.status_code in (200, 204)

    # deactivate via delete
    r = session.delete(f"{BASE_URL}/api/voice-seeds/{seed_id}", timeout=15)
    assert r.status_code in (200, 204)


# ---------------- Scan hot batch + progress ----------------

def test_scan_hot_batch(session, auth):
    r = session.post(f"{BASE_URL}/api/intel/scan-hot", json={}, timeout=180)
    # accept 200 or 202; environmental 403 from RapidAPI may surface as 200 with failures
    assert r.status_code in (200, 202), r.text[:300]
    data = r.json()
    for key in ("processed", "succeeded", "failed"):
        assert key in data, f"missing {key} in {data}"


def test_scan_progress(session, auth):
    candidates = ["/api/intel/scan-progress", "/api/intel/scan_progress", "/api/scan-progress"]
    for path in candidates:
        r = session.get(f"{BASE_URL}{path}", timeout=15)
        if r.status_code == 200:
            return
    pytest.fail("scan progress endpoint not found")


# ---------------- Journey reorder ----------------

def test_journey_reorder(session, auth):
    r = session.get(f"{BASE_URL}/api/journey/touchpoints", timeout=15)
    assert r.status_code == 200, r.text[:200]
    data = r.json()
    items = data if isinstance(data, list) else data.get("items") or data.get("touchpoints") or []
    if len(items) < 2:
        pytest.skip("not enough touchpoints to test reorder")
    ids = [i["id"] for i in items]
    reversed_ids = list(reversed(ids))
    r = session.post(
        f"{BASE_URL}/api/journey/touchpoints/reorder",
        json={"order": reversed_ids},
        timeout=15,
    )
    assert r.status_code in (200, 204), r.text[:200]
    # restore original order
    session.post(
        f"{BASE_URL}/api/journey/touchpoints/reorder",
        json={"order": ids},
        timeout=15,
    )


# ---------------- Approvals regression ----------------

def test_approvals_list(session, auth):
    r = session.get(f"{BASE_URL}/api/approvals", timeout=15)
    assert r.status_code == 200, r.text[:200]
    assert _no_mongo_id(r.json())


# ---------------- Tenant isolation ----------------

def test_tenant_isolation_voice_seeds(session, auth):
    # request voice-seeds with a bogus tenant
    headers = dict(session.headers)
    headers["X-Tenant-Id"] = "ten_does_not_exist"
    r = requests.get(f"{BASE_URL}/api/voice-seeds", headers=headers, timeout=15)
    # must NOT leak ten_demo data — accept 403/404/empty
    assert r.status_code in (200, 403, 404), r.text[:200]
    if r.status_code == 200:
        data = r.json()
        items = data if isinstance(data, list) else data.get("items", [])
        assert items == [], "voice-seeds leaked across tenant boundary"
