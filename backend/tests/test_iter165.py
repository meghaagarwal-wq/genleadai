"""Tests for iter165: dedupe leads + approvals for triage view."""
import os
import requests
import pytest

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://pipeline-pro-96.preview.emergentagent.com').rstrip('/')

EMAIL = "admin@demo.com"
PWD = "Demo1234!"
TENANT = "ten_demo"


@pytest.fixture(scope="module")
def auth():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PWD})
    assert r.status_code == 200, r.text
    tok = r.json().get("token") or r.json().get("access_token")
    return {"Authorization": f"Bearer {tok}", "X-Tenant-Id": TENANT, "Content-Type": "application/json"}


def test_login_200():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PWD})
    assert r.status_code == 200
    assert "token" in r.json() or "access_token" in r.json()


def test_tenants_me(auth):
    r = requests.get(f"{BASE_URL}/api/tenants/me", headers=auth)
    assert r.status_code == 200


def test_dashboard_b2b(auth):
    r = requests.get(f"{BASE_URL}/api/dashboard/b2b-founder", headers=auth)
    assert r.status_code == 200


def test_pt_leads_dedupe(auth):
    r = requests.get(f"{BASE_URL}/api/pt/leads", headers=auth)
    assert r.status_code == 200
    data = r.json()
    leads = data.get("leads") if isinstance(data, dict) else data
    assert isinstance(leads, list)
    ids = [l.get("id") for l in leads]
    unique_ids = set(ids)
    print(f"Total leads: {len(leads)}, Unique ids: {len(unique_ids)}")
    # Assertion: no dupes
    assert len(ids) == len(unique_ids), f"Duplicates found: {[i for i in ids if ids.count(i)>1]}"


def test_approvals_endpoint(auth):
    r = requests.get(f"{BASE_URL}/api/approvals", headers=auth)
    assert r.status_code == 200, r.text
    data = r.json()
    items = data.get("approvals") or data.get("items") or (data if isinstance(data, list) else [])
    print(f"Approvals count: {len(items)}")
    assert len(items) >= 1
    # Check shape
    a = items[0]
    print(f"Sample keys: {list(a.keys())}")
    # Look for expected fields (flexible)
    expected_any = ["lead_snapshot", "confidence", "reason_for_review", "ai_model", "channel"]
    found = [k for k in expected_any if k in a]
    print(f"Found expected fields: {found}")
    assert "channel" in a or "lead_snapshot" in a
