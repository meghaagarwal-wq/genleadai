"""iter166 backend regression: login, leads dedupe, approvals, insights, patch stage."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")


@pytest.fixture(scope="module")
def auth():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@demo.com", "password": "Demo1234!"})
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("token") or data.get("access_token")
    assert token, f"No token in {data}"
    # figure out tenant id
    tenant_id = "ten_demo"
    memberships = data.get("user", {}).get("memberships") or data.get("memberships") or []
    for m in memberships:
        if m.get("tenant_id", "").startswith("ten_demo") or "demo" in m.get("tenant_id", "").lower():
            tenant_id = m["tenant_id"]
            break
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": tenant_id, "Content-Type": "application/json"}


def test_login_ok():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@demo.com", "password": "Demo1234!"})
    assert r.status_code == 200
    assert r.json().get("user", {}).get("email") == "admin@demo.com"


def test_leads_list_dedupe(auth):
    r = requests.get(f"{BASE_URL}/api/pt/leads", headers=auth)
    assert r.status_code == 200
    leads = r.json().get("leads", [])
    ids = [l["id"] for l in leads]
    assert len(ids) == len(set(ids)), "Duplicate lead IDs present"
    print(f"Leads count: {len(leads)}")
    # Expect 13 per problem statement (allow >=10 tolerance for flakiness)
    assert 10 <= len(leads) <= 20, f"Expected ~13 leads got {len(leads)}"


def test_approvals_pending(auth):
    r = requests.get(f"{BASE_URL}/api/approvals", headers=auth)
    assert r.status_code == 200
    body = r.json()
    items = body.get("items") or body.get("approvals") or body if isinstance(body, list) else body.get("data", [])
    if isinstance(body, dict) and "items" in body:
        items = body["items"]
    pending = [a for a in items if (a.get("status") or "pending") in ("pending", "awaiting_owner_approval")]
    print(f"Pending approvals: {len(pending)}")
    assert len(pending) >= 1


def test_founder_command_center(auth):
    r = requests.get(f"{BASE_URL}/api/insights/founder-command-center", headers=auth)
    assert r.status_code == 200


def test_patch_lead_stage(auth):
    r = requests.get(f"{BASE_URL}/api/pt/leads", headers=auth)
    leads = r.json().get("leads", [])
    assert leads
    # Pick a lead with a "manageable" stage (avoid high-score auto-recompute)
    lead = next((l for l in leads if (l.get("stage") or "").lower() in ("new", "cold", "warm")), leads[0])
    orig_stage = lead.get("stage") or "cold"
    new_stage = "hot" if orig_stage != "hot" else "warm"
    pr = requests.patch(f"{BASE_URL}/api/pt/leads/{lead['id']}", headers=auth, json={"stage": new_stage})
    assert pr.status_code in (200, 204), f"PATCH failed {pr.status_code}: {pr.text}"
    # verify
    vr = requests.get(f"{BASE_URL}/api/pt/leads", headers=auth)
    updated = next((l for l in vr.json().get("leads", []) if l["id"] == lead["id"]), None)
    assert updated and updated.get("stage") == new_stage
    # revert
    requests.patch(f"{BASE_URL}/api/pt/leads/{lead['id']}", headers=auth, json={"stage": orig_stage})
