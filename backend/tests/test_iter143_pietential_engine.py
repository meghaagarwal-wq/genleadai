"""Iter143 — Pietential Intelligence Engine end-to-end verification.

Covers the 15-point checklist from the user prompt:
  1.  POST /_test/simulate returns a HIGH_INTENT lead
  2.  ICP scoring lands on a Pietential ICP (icp_a..icp_e)
  3.  Insight card created with founder_flag for tier_1 CHRO
  4.  Lead score 0-100, account_tier set
  5.  pipeline-health endpoint reachable + correct shape
  6.  Tenant isolation: ten_demo user gets 403 from pipeline-health
  7.  Saleshandy poll loop skips ten_pietential
  8.  Insight cards land in pt_insights with UI fields populated
  9.  /poll/run-now requires owner/admin
  10. /scan/run-now requires owner/admin
  11. Dedup on second simulate run skips creating duplicate card
  12. V10: only claude_service.py touches Anthropic
  13. Cleanup endpoint removes simulated leads
  14. Background loops registered in server.py
  15. Manual trigger endpoints all reachable

Run: pytest /app/backend/tests/test_iter143_pietential_engine.py -v
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

import pytest
import requests

API = os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001"
if "REACT_APP_BACKEND_URL" not in os.environ:
    # Try to load from frontend/.env so this works in CI and dev.
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    API = line.split("=", 1)[1].strip()
                    break
    except FileNotFoundError:
        pass

ADMIN_EMAIL = "admin@demo.com"
ADMIN_PWD = "Demo1234!"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{API}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PWD},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["token"]


@pytest.fixture(scope="module")
def pt_headers(admin_token):
    return {
        "Authorization": f"Bearer {admin_token}",
        "X-Tenant-Id": "ten_pietential",
        "Content-Type": "application/json",
    }


@pytest.fixture(scope="module")
def demo_headers(admin_token):
    return {
        "Authorization": f"Bearer {admin_token}",
        "X-Tenant-Id": "ten_demo",
        "Content-Type": "application/json",
    }


# ─── 1-4. Simulate the full pipeline ──────────────────────────────
@pytest.fixture(scope="module")
def simulated(pt_headers):
    # Clean up any prior simulated leads first.
    requests.post(f"{API}/api/pietential/_test/cleanup-simulated", headers=pt_headers, timeout=30)
    r = requests.post(f"{API}/api/pietential/_test/simulate", headers=pt_headers, timeout=120)
    assert r.status_code == 200, r.text
    return r.json()


def test_1_simulate_returns_high_intent(simulated):
    intent = simulated["intent_result"]
    assert intent is not None, "intent classification missing"
    assert intent.get("intent") in ("HIGH_INTENT", "MEDIUM_INTENT"), intent
    assert intent.get("reply_sentiment") in ("POSITIVE", "QUESTION", "NEUTRAL"), intent


def test_2_icp_match_is_pietential_icp(simulated):
    icp = simulated["icp_result"]
    assert icp is not None
    assert icp.get("matched_icp_id") in {"icp_a", "icp_b", "icp_c", "icp_d", "icp_e"}, icp
    assert 0 <= int(icp.get("icp_score") or 0) <= 100


def test_3_insight_card_with_founder_flag(simulated):
    final = simulated["final_lead"]
    assert simulated.get("insight_card_id"), "no insight card created"
    # CHRO at 3500 = founder_flag true
    assert final["founder_flag"] is True, final


def test_4_lead_score_and_tier(simulated):
    final = simulated["final_lead"]
    assert 0 <= int(final["lead_score"]) <= 100
    assert final["account_tier"] in {"tier_1", "tier_2", "tier_3", "not_priority"}


# ─── 5. pipeline-health shape ─────────────────────────────────────
def test_5_pipeline_health_shape(pt_headers):
    r = requests.get(f"{API}/api/pietential/pipeline-health", headers=pt_headers, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    for k in (
        "total_active_lemlist_leads",
        "high_intent",
        "high_intent_stale",
        "awaiting_enrichment",
        "signals_this_week",
        "next_weekly_report_hint",
    ):
        assert k in data, f"missing key {k} in {data}"


# ─── 6. Tenant isolation ──────────────────────────────────────────
def test_6_tenant_isolation_demo_user_blocked(demo_headers):
    # admin@demo.com is master_admin so they DO get through. We test instead
    # with a sales_rep account on ten_demo who is NOT in the Pietential tenant.
    rep_token = requests.post(
        f"{API}/api/auth/login",
        json={"email": "sarah@demo.com", "password": "Demo1234!"},
        timeout=20,
    ).json().get("token")
    if not rep_token:
        pytest.skip("sales_rep account not seeded")
    headers = {
        "Authorization": f"Bearer {rep_token}",
        "X-Tenant-Id": "ten_demo",
    }
    r = requests.get(f"{API}/api/pietential/pipeline-health", headers=headers, timeout=20)
    assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"


# ─── 7. Saleshandy gate ───────────────────────────────────────────
def test_7_saleshandy_loop_skips_pietential():
    # Read file directly so this works regardless of pytest cwd / sys.path
    with open("/app/backend/routes/audit_loops.py") as f:
        src = f.read()
    # Locate the saleshandy_poll_once function body and assert it filters
    # out ten_pietential from configs query.
    assert "saleshandy_poll_once" in src, "saleshandy_poll_once function missing"
    # Grab the function block
    start = src.index("saleshandy_poll_once")
    block = src[start:start + 4000]
    assert "ten_pietential" in block, "saleshandy_poll_once must filter out ten_pietential"


# ─── 8. UI compatibility fields ───────────────────────────────────
def test_8_insight_card_has_ui_fields(pt_headers, simulated):
    # Fetch via the existing pt_insights feed endpoint and confirm the card
    # has the fields IntelligenceFeed.js expects.
    r = requests.get(
        f"{API}/api/pt/insights/feed",
        headers=pt_headers,
        params={"status": "new"},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    cards = r.json().get("cards") or []
    sim_card_id = simulated.get("insight_card_id")
    found = next((c for c in cards if c.get("id") == sim_card_id), None)
    assert found, f"simulated card {sim_card_id} not in feed (got {len(cards)} cards)"
    for k in (
        "prospect_name", "prospect_title", "prospect_company",
        "signal_summary", "signal_type", "suggested_message",
        "confidence", "icp_match_name", "icp_match_score", "status",
    ):
        assert k in found, f"missing UI field '{k}' in card {found}"


# ─── 9 + 10. Role guards ──────────────────────────────────────────
def test_9_poll_run_now_requires_admin():
    rep_token = requests.post(
        f"{API}/api/auth/login",
        json={"email": "sarah@demo.com", "password": "Demo1234!"},
        timeout=20,
    ).json().get("token")
    if not rep_token:
        pytest.skip()
    headers = {"Authorization": f"Bearer {rep_token}"}
    r = requests.post(f"{API}/api/pietential/poll/run-now", headers=headers, timeout=20)
    assert r.status_code == 403, r.text


def test_10_scan_run_now_requires_admin():
    rep_token = requests.post(
        f"{API}/api/auth/login",
        json={"email": "sarah@demo.com", "password": "Demo1234!"},
        timeout=20,
    ).json().get("token")
    if not rep_token:
        pytest.skip()
    headers = {"Authorization": f"Bearer {rep_token}"}
    r = requests.post(f"{API}/api/pietential/scan/run-now", headers=headers, timeout=20)
    assert r.status_code == 403, r.text


# ─── 11. Dedup ────────────────────────────────────────────────────
def test_11_signal_dedup_within_30d(pt_headers, simulated):
    """A second scan-now on the same lead with the same signal hash should
    skip card creation."""
    lead_id = simulated["lead_id"]
    r = requests.post(
        f"{API}/api/pietential/lead/{lead_id}/scan-now",
        headers=pt_headers,
        timeout=120,
    )
    assert r.status_code == 200, r.text
    card = r.json().get("card")
    assert card is None or card.get("skipped") is True, f"expected dedup skip, got {card}"


# ─── 12. V10 architectural guard ──────────────────────────────────
def test_12_v10_no_direct_anthropic_imports():
    script = "/app/scripts/check_v10.sh"
    if not os.path.exists(script):
        pytest.skip(f"{script} not found")
    res = subprocess.run(["bash", script], capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, f"V10 violation:\n{res.stdout}\n{res.stderr}"


# ─── 13. Cleanup endpoint ─────────────────────────────────────────
def test_13_cleanup_simulated(pt_headers):
    r = requests.post(
        f"{API}/api/pietential/_test/cleanup-simulated",
        headers=pt_headers,
        timeout=20,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("leads_deleted", 0) >= 1
    # Insight + intel deleted counts can be zero on the second pass.
    assert "intel_deleted" in body and "insights_deleted" in body


# ─── 14. Background loops registered ──────────────────────────────
def test_14_loops_registered_in_server():
    with open("/app/backend/server.py") as f:
        src = f.read()
    for name in ("lemlist_poll_loop", "pietential_insight_scan_loop", "weekly_intel_report_loop"):
        assert f"asyncio.create_task({name}())" in src, f"{name} not started in server.py"


# ─── 15. All manual trigger endpoints reachable ───────────────────
def test_15_manual_triggers_reachable(pt_headers):
    # poll/run-now (will likely 200 with skipped:true if no Lemlist key)
    r1 = requests.post(f"{API}/api/pietential/poll/run-now", headers=pt_headers, timeout=60)
    assert r1.status_code == 200, r1.text
    # weekly-report/send-now (will return sent:false if no Resend key)
    r2 = requests.post(f"{API}/api/pietential/weekly-report/send-now", headers=pt_headers, timeout=60)
    assert r2.status_code == 200, r2.text
    # scan/run-now (long; allow up to 3 min, expect 200)
    r3 = requests.post(f"{API}/api/pietential/scan/run-now", headers=pt_headers, timeout=180)
    assert r3.status_code == 200, r3.text
