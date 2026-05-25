"""
Iter74 regression — verify the structural refactor of aria_agent_routes.py
(module-level routes instead of a wrapper function) preserves behavior of
all 27 /api/aria-agent/* endpoints.
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASS = os.environ.get("TEST_ADMIN_PASS", "Demo1234!")
# ─── Fixtures ───────────────────────────────────────────────
@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
                      timeout=15)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    tok = r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def tenant_id(auth_token):
    r = requests.get(f"{BASE_URL}/api/tenants/me",
                     headers={"Authorization": f"Bearer {auth_token}"}, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    # response may be list or wrapped object
    if isinstance(data, list) and data:
        return data[0].get("id") or data[0].get("_id") or data[0].get("tenant_id")
    if isinstance(data, dict):
        if "tenants" in data and data["tenants"]:
            return data["tenants"][0].get("id")
        return data.get("id") or data.get("tenant_id")
    return None


@pytest.fixture(scope="module")
def headers(auth_token, tenant_id):
    h = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    if tenant_id:
        h["X-Tenant-Id"] = tenant_id
    return h


@pytest.fixture(scope="module")
def sample_lead_id(headers):
    r = requests.get(f"{BASE_URL}/api/leads", headers=headers, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    leads = data if isinstance(data, list) else data.get("leads") or data.get("items") or []
    if not leads:
        pytest.skip("No leads available to exercise per-lead endpoints")
    lead = leads[0]
    return lead.get("id") or lead.get("_id") or lead.get("lead_id")


# ─── GET smoke regression for the 16 representative endpoints ─────
GET_ENDPOINTS = [
    "/api/aria-agent/training",
    "/api/aria-agent/playbooks",
    "/api/aria-agent/journeys/default",
    "/api/aria-agent/handoff/rules",
    "/api/aria-agent/handoff/alerts",
    "/api/aria-agent/revival/segments",
    "/api/aria-agent/agent-activity",
    "/api/aria-agent/insights",
    "/api/aria-agent/assets/catalog",
    "/api/aria-agent/assets",
    "/api/aria-agent/brain",
    "/api/aria-agent/weekly-recap",
    "/api/aria-agent/workspace/stories",
    "/api/aria-agent/workspace/feed",
    "/api/aria-agent/workspace/pipeline-mood",
    "/api/aria-agent/workspace/morning-brief",
]


@pytest.mark.parametrize("path", GET_ENDPOINTS)
def test_aria_get_endpoint_200(headers, path):
    r = requests.get(f"{BASE_URL}{path}", headers=headers, timeout=30)
    assert r.status_code == 200, f"{path} → {r.status_code} {r.text[:300]}"
    # response shape sanity: must be JSON (dict or list)
    body = r.json()
    assert isinstance(body, (dict, list)), f"{path} returned non-JSON object"


# ─── PUT /training (mutation) ─────────────────────────────────────
def test_put_training_persists(headers):
    payload = {
        "what_you_sell": "TEST_iter74_widgets",
        "tone": "founder_like",
        "calendar_link": "https://test.example.com/cal",
    }
    r = requests.put(f"{BASE_URL}/api/aria-agent/training",
                     json=payload, headers=headers, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("saved") is True
    assert "trained_at" in body

    # GET back — verify persistence
    g = requests.get(f"{BASE_URL}/api/aria-agent/training", headers=headers, timeout=15)
    assert g.status_code == 200
    saved = g.json()
    assert saved.get("what_you_sell") == "TEST_iter74_widgets"
    assert saved.get("calendar_link") == "https://test.example.com/cal"


# ─── Playbook activate / deactivate ────────────────────────────────
def test_playbook_activate_deactivate_roundtrip(headers):
    pid = "inbound_qualification"

    a = requests.post(f"{BASE_URL}/api/aria-agent/playbooks/{pid}/activate",
                      headers=headers, timeout=15)
    assert a.status_code == 200, a.text
    abody = a.json()
    assert abody.get("active") is True or abody.get("status") == "active" or abody.get("playbook_id") == pid

    # list playbooks and confirm active flag
    lst = requests.get(f"{BASE_URL}/api/aria-agent/playbooks", headers=headers, timeout=15)
    assert lst.status_code == 200
    plist = lst.json()
    items = plist if isinstance(plist, list) else plist.get("playbooks") or plist.get("items") or []
    match = [p for p in items if (p.get("id") == pid or p.get("playbook_id") == pid)]
    if match:
        # if backend exposes active state, ensure it reflects True
        m = match[0]
        if "active" in m:
            assert m["active"] is True

    d = requests.post(f"{BASE_URL}/api/aria-agent/playbooks/{pid}/deactivate",
                      headers=headers, timeout=15)
    assert d.status_code == 200, d.text
    dbody = d.json()
    assert dbody.get("active") is False or dbody.get("status") in ("inactive", "deactivated") or "playbook_id" in dbody


# ─── Asset CRUD ────────────────────────────────────────────────────
def test_asset_crud_flow(headers):
    # Actual schema: AssetPayload(title, type, body, tags, channel, used_by_aria)
    create_payload = {
        "title": f"TEST_iter74_asset_{uuid.uuid4().hex[:6]}",
        "type": "message_template",
        "body": "Hello from iter74 refactor regression",
    }
    c = requests.post(f"{BASE_URL}/api/aria-agent/assets",
                      json=create_payload, headers=headers, timeout=15)
    assert c.status_code in (200, 201), c.text
    asset = c.json()
    asset_id = asset.get("id") or asset.get("_id") or asset.get("asset_id")
    assert asset_id, f"No asset id in {asset}"
    assert asset.get("title") == create_payload["title"]

    # GET list
    g = requests.get(f"{BASE_URL}/api/aria-agent/assets", headers=headers, timeout=15)
    assert g.status_code == 200
    listing = g.json()
    items = listing if isinstance(listing, list) else listing.get("assets") or listing.get("items") or []
    assert any((it.get("id") or it.get("_id")) == asset_id for it in items), "Created asset not in list"

    # PATCH — schema requires title + type as full payload (PATCH still uses AssetPayload)
    p = requests.patch(f"{BASE_URL}/api/aria-agent/assets/{asset_id}",
                       json={**create_payload, "title": create_payload["title"] + "_upd"},
                       headers=headers, timeout=15)
    assert p.status_code == 200, p.text

    # POST /use
    u = requests.post(f"{BASE_URL}/api/aria-agent/assets/{asset_id}/use",
                      headers=headers, json={}, timeout=15)
    assert u.status_code == 200, u.text

    # DELETE
    d = requests.delete(f"{BASE_URL}/api/aria-agent/assets/{asset_id}",
                        headers=headers, timeout=15)
    assert d.status_code in (200, 204), d.text


# ─── Workspace story card per lead ────────────────────────────────
def test_workspace_story_card(headers, sample_lead_id):
    r = requests.get(f"{BASE_URL}/api/aria-agent/workspace/story-card/{sample_lead_id}",
                     headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), (dict, list))


# ─── Founder brief (POST) ─────────────────────────────────────────
def test_founder_brief(headers, sample_lead_id):
    r = requests.post(f"{BASE_URL}/api/aria-agent/founder-brief/{sample_lead_id}",
                      headers=headers, json={}, timeout=60)
    # founder brief uses LLM; allow 200 or 502/503 (upstream LLM unavailable) but flag if 500
    assert r.status_code in (200, 502, 503), f"{r.status_code} {r.text[:300]}"
    if r.status_code == 200:
        assert isinstance(r.json(), dict)


# ─── Aria-read per lead ───────────────────────────────────────────
def test_aria_read(headers, sample_lead_id):
    r = requests.get(f"{BASE_URL}/api/aria-agent/aria-read/{sample_lead_id}",
                     headers=headers, timeout=60)
    assert r.status_code in (200, 502, 503), f"{r.status_code} {r.text[:300]}"
    if r.status_code == 200:
        assert isinstance(r.json(), dict)
