"""iter148 — Megha Pietential owner + Demo viewer + 6 demo leads
isolation verification. 8 points, all must pass.

Run: pytest /app/backend/tests/test_iter148_demo_isolation.py -v
"""
from __future__ import annotations

import os
import pytest
import requests

API = os.environ.get("REACT_APP_BACKEND_URL")
if not API:
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    API = line.split("=", 1)[1].strip()
                    break
    except FileNotFoundError:
        API = "http://localhost:8001"

PT_OWNER_EMAIL = "megha@contentvista.com"
PT_OWNER_PWD = "Pietential2026!"
DEMO_VIEWER_EMAIL = "meghaagarwaljain2015@gmail.com"
DEMO_VIEWER_PWD = "DemoView2026!"


def _login(email: str, password: str) -> str:
    r = requests.post(f"{API}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def pt_token():
    return _login(PT_OWNER_EMAIL, PT_OWNER_PWD)


@pytest.fixture(scope="module")
def dv_token():
    return _login(DEMO_VIEWER_EMAIL, DEMO_VIEWER_PWD)


# ── V1: Pietential owner sees ONLY Pietential workspace ───────────
def test_v1_pt_owner_workspace_switcher(pt_token):
    r = requests.get(f"{API}/api/tenants/me", headers={"Authorization": f"Bearer {pt_token}"}, timeout=20)
    assert r.status_code == 200, r.text
    tenants = r.json().get("tenants") or []
    assert len(tenants) == 1, f"expected exactly 1 workspace, got {len(tenants)}: {tenants}"
    assert tenants[0]["id"] == "ten_pietential", tenants[0]
    assert tenants[0]["role"] == "owner", tenants[0]


def test_v1_pt_owner_no_admin_panel(pt_token):
    r = requests.get(f"{API}/api/admin/applications", headers={"Authorization": f"Bearer {pt_token}"}, timeout=20)
    # Master admin endpoint — non-master_admin gets 403 or 404
    assert r.status_code in (403, 404), f"expected 403/404, got {r.status_code}: {r.text[:200]}"


# ── V2: Demo viewer sees ONLY Demo workspace ──────────────────────
def test_v2_demo_viewer_workspace_switcher(dv_token):
    r = requests.get(f"{API}/api/tenants/me", headers={"Authorization": f"Bearer {dv_token}"}, timeout=20)
    assert r.status_code == 200, r.text
    tenants = r.json().get("tenants") or []
    assert len(tenants) == 1, f"expected exactly 1 workspace, got {len(tenants)}: {tenants}"
    assert tenants[0]["id"] == "ten_demo", tenants[0]
    assert tenants[0]["role"] == "viewer", tenants[0]


def test_v2_demo_viewer_no_admin_panel(dv_token):
    r = requests.get(f"{API}/api/admin/applications", headers={"Authorization": f"Bearer {dv_token}"}, timeout=20)
    assert r.status_code in (403, 404), r.text[:200]


# ── V3: PT-owner sees ZERO ten_demo data even with forged header ──
def test_v3_pt_owner_cannot_see_demo_pt_leads(pt_token):
    # The pt_insights endpoint uses the STRICT get_active_tenant dep — it
    # 403s when the X-Tenant-Id header points at a tenant the user isn't
    # a member of. That's the hardest possible isolation guarantee.
    r = requests.get(
        f"{API}/api/pt/insights/feed?status=new",
        headers={"Authorization": f"Bearer {pt_token}", "X-Tenant-Id": "ten_demo"},
        timeout=20,
    )
    assert r.status_code == 403, f"expected 403 hard-block, got {r.status_code}: {r.text}"
    assert "Not a member" in r.text or "member" in r.text.lower(), r.text

    # Also verify the same user calling WITHOUT the forged header only
    # gets their own tenant's data (ten_pietential) — no demo leak.
    r2 = requests.get(
        f"{API}/api/pt/insights/feed?status=new",
        headers={"Authorization": f"Bearer {pt_token}", "X-Tenant-Id": "ten_pietential"},
        timeout=20,
    )
    assert r2.status_code == 200, r2.text
    cards = r2.json().get("cards") or []
    demo_cards = [c for c in cards if c.get("id", "").startswith("ins_demo_")]
    assert demo_cards == [], f"PT-owner leaked {len(demo_cards)} demo cards into Pietential feed"


# ── V4: Demo viewer sees ZERO ten_pietential data ─────────────────
def test_v4_demo_viewer_cannot_see_pietential_leads(dv_token):
    """Forging X-Tenant-Id=ten_pietential must NEVER return Pietential
    data. Two acceptable behaviours:
      (a) strict 403 (Pietential routes using get_active_tenant)
      (b) silent fallback to user's own tenant (routes using get_current_user)
    Either way, the response must contain ZERO Pietential leads."""
    r_block = requests.get(
        f"{API}/api/pt/leads?limit=100",
        headers={"Authorization": f"Bearer {dv_token}", "X-Tenant-Id": "ten_pietential"},
        timeout=20,
    )
    assert r_block.status_code in (200, 403), r_block.text
    if r_block.status_code == 200:
        # Silent-fallback path: response must contain demo seeds and ZERO Pietential leads.
        leads = r_block.json().get("leads") or []
        pt_domains = ("@pietential.ai", "@contentvista.com", "@lemlistdemo.com")
        pt_leak = [lead for lead in leads if any(d in (lead.get("email") or "") for d in pt_domains)]
        assert not pt_leak, f"silent-fallback leaked Pietential leads: {[lead.get('email') for lead in pt_leak]}"

    # Independently confirm demo-viewer DOES see their own demo seeds
    # via /api/pt/insights/feed (strict route).
    r2 = requests.get(
        f"{API}/api/pt/insights/feed?status=new",
        headers={"Authorization": f"Bearer {dv_token}", "X-Tenant-Id": "ten_demo"},
        timeout=20,
    )
    assert r2.status_code == 200, r2.text
    seed_cards = [c for c in r2.json().get("cards") or [] if c.get("id", "").startswith("ins_demo_")]
    assert len(seed_cards) == 3, f"expected 3 demo insight cards visible to demo-viewer, got {len(seed_cards)}"


# ── V5: All 6 demo leads visible in Demo workspace ────────────────
def test_v5_all_six_demo_leads_visible(dv_token):
    r = requests.get(f"{API}/api/pt/leads?limit=200",
                     headers={"Authorization": f"Bearer {dv_token}"}, timeout=20)
    assert r.status_code == 200, r.text
    leads = r.json().get("leads") or []
    seeds = {lead["id"]: lead for lead in leads if lead.get("seed_source") == "iter148"}
    expected_ids = {
        "ptl_demo_sarah_chen", "ptl_demo_arjun_mehta", "ptl_demo_james_whitfield",
        "ptl_demo_priya_nair", "ptl_demo_rahul_desai", "ptl_demo_ananya_sharma",
    }
    missing = expected_ids - set(seeds.keys())
    assert not missing, f"missing demo leads: {missing}"


# ── V6: No domain overlap with real Pietential leads ──────────────
def test_v6_no_email_domain_overlap(dv_token, pt_token):
    """Verify the demo-seed email domains (novabridge.io, kestrelfinancial.com,
    alveron.com, *.example) do NOT appear in real ten_pietential pt_leads."""
    demo_domains = ("novabridge.io", "kestrelfinancial.com", "alveron.com",
                    "designlab.example", "brightlogic.example", "retailco.example")
    r = requests.get(f"{API}/api/pt/leads?limit=200",
                     headers={"Authorization": f"Bearer {pt_token}"}, timeout=20)
    assert r.status_code == 200, r.text
    pt_leads = r.json().get("leads") or []
    overlap = [lead for lead in pt_leads
               if any(d in (lead.get("email") or "").lower() for d in demo_domains)]
    assert not overlap, f"Pietential workspace has leads using demo domains: {[lead.get('email') for lead in overlap]}"


# ── V7: Instinct Feed has 3 insight cards rendered properly ───────
def test_v7_instinct_feed_has_three_cards(dv_token):
    r = requests.get(f"{API}/api/pt/insights/feed?status=new",
                     headers={"Authorization": f"Bearer {dv_token}"}, timeout=20)
    assert r.status_code == 200, r.text
    cards = r.json().get("cards") or []
    seed_cards = [c for c in cards if c.get("id", "").startswith("ins_demo_")]
    assert len(seed_cards) == 3, f"expected 3 seed insight cards, got {len(seed_cards)}"

    expected = {
        "ins_demo_sarah_chen":      ("Sarah Chen", "new_people_leader", 84),
        "ins_demo_arjun_mehta":     ("Arjun Mehta", "layoffs", 71),
        "ins_demo_james_whitfield": ("James Whitfield", "benefits_hr_transformation", 58),
    }
    for card in seed_cards:
        name, sig, score = expected[card["id"]]
        assert card.get("prospect_name") == name, card
        assert card.get("signal_type") == sig, card
        assert card.get("lead_score") == score, card
        # UI fields must be populated for IntelligenceFeed.js render.
        assert card.get("suggested_message"), card
        assert card.get("prospect_company"), card
        assert card.get("icp_match_name"), card
        assert 0 <= card.get("confidence", 0) <= 1, card


# ── V8: Lead Inbox has 3 B2C automation leads with messages ───────
def test_v8_automation_leads_have_conversations(dv_token):
    for lead_id, name, expected_msg_count in (
        ("ptl_demo_priya_nair", "Priya", 3),
        ("ptl_demo_rahul_desai", "Rahul", 5),
        ("ptl_demo_ananya_sharma", "Ananya", 2),
    ):
        r = requests.get(
            f"{API}/api/conversations/lead/{lead_id}",
            headers={"Authorization": f"Bearer {dv_token}"},
            timeout=20,
        )
        assert r.status_code == 200, f"{name}: {r.status_code} {r.text[:200]}"
        body = r.json()
        assert body["lead_snapshot"]["first_name"] == name, body["lead_snapshot"]
        # outbound + inbound combined should equal expected_msg_count
        thread = body.get("thread") or []
        non_system = [t for t in thread if t.get("direction") in ("outbound", "inbound")]
        assert len(non_system) == expected_msg_count, (
            f"{name}: expected {expected_msg_count} messages, got {len(non_system)}: "
            f"{[t['direction'] for t in non_system]}"
        )
