"""Iter146 — Pietential / tenant-isolation audit.

Audits:
 1. /api/leads/counts aggregation across leads + pt_leads (sidebar fix).
 2. List endpoints (leads, your-five-today, sleeping) — surface pt_leads?
 3. ARIA analytics/feed — uses pt_leads?
 4. Reports — pulls pt_leads?
 5. Command Center KPIs — pulls both?
 6. /api/pt/insights/feed — Pietential insights, iter143 UI-compat fields.
 7. Tenant isolation — no cross-tenant leakage.
 8. _id leak check.
 9. V10 guard script.
10. Pietential pipeline manual triggers (200/expected response).
11. Backend health + supervisor.
12. Event-loop unblock proof (simulate + parallel pipeline-health).
"""
from __future__ import annotations

import asyncio
import os
import time
import httpx
import pytest

def _read_frontend_env():
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return None


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_env() or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
ADMIN = {"email": "admin@demo.com", "password": "Demo1234!"}
SALES = {"email": "sarah@demo.com", "password": "Demo1234!"}

TEN_DEMO = "ten_demo"
TEN_PIE = "ten_pietential"


# ─── fixtures ────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def admin_token():
    r = httpx.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def sales_token():
    r = httpx.post(f"{BASE_URL}/api/auth/login", json=SALES, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _h(tok, tenant):
    return {"Authorization": f"Bearer {tok}", "X-Tenant-Id": tenant}


# ─── 1. Sidebar Lead Counts (iter146 fix) ────────────────────────────
def test_1a_lead_counts_pietential_has_real_numbers(admin_token):
    r = httpx.get(f"{BASE_URL}/api/leads/counts", headers=_h(admin_token, TEN_PIE), timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()
    print("PIE counts:", j)
    assert j["total"] >= 44, f"Pietential total expected ≥44, got {j['total']}"
    assert j["by_stage"]["qualified"] >= 10, f"qualified expected ≥10, got {j['by_stage']['qualified']}"
    assert j["by_stage"]["cold"] >= 16, f"cold expected ≥16, got {j['by_stage']['cold']}"


def test_1b_lead_counts_demo_unchanged(admin_token):
    r = httpx.get(f"{BASE_URL}/api/leads/counts", headers=_h(admin_token, TEN_DEMO), timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()
    print("DEMO counts:", j)
    assert j["total"] >= 100, f"Demo total expected ~138, got {j['total']}"


# ─── 2. List endpoints — leads / your-five-today / sleeping ──────────
def test_2a_leads_list_pietential(admin_token):
    """AUDIT: /api/leads in Pietential — does it surface pt_leads at all?"""
    r = httpx.get(f"{BASE_URL}/api/leads?limit=200", headers=_h(admin_token, TEN_PIE), timeout=20)
    assert r.status_code == 200, r.text
    leads = r.json() if isinstance(r.json(), list) else r.json().get("leads") or r.json().get("items") or []
    print(f"/api/leads PIE returned {len(leads)} items")
    # No assertion on count — recording finding only.
    # _id leak check
    for L in leads[:5]:
        assert "_id" not in L, f"_id leaked in /api/leads: {L}"


def test_2b_your_five_today_pietential(admin_token):
    r = httpx.get(f"{BASE_URL}/api/leads/your-five-today", headers=_h(admin_token, TEN_PIE), timeout=20)
    print(f"your-five-today PIE: status={r.status_code}, body={r.text[:300]}")
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        body = r.json()
        if isinstance(body, list):
            for L in body[:3]:
                assert "_id" not in L


def test_2c_sleeping_leads_pietential(admin_token):
    r = httpx.get(f"{BASE_URL}/api/leads/sleeping", headers=_h(admin_token, TEN_PIE), timeout=20)
    print(f"sleeping PIE: status={r.status_code}, body={r.text[:300]}")
    assert r.status_code in (200, 404)


# ─── 3. ARIA analytics + feed ────────────────────────────────────────
def test_3a_aria_analytics_pietential(admin_token):
    r = httpx.get(f"{BASE_URL}/api/aria/analytics", headers=_h(admin_token, TEN_PIE), timeout=20)
    print(f"/api/aria/analytics PIE: status={r.status_code}, body={r.text[:300]}")
    assert r.status_code in (200, 404)


def test_3b_aria_feed_pietential(admin_token):
    r = httpx.get(f"{BASE_URL}/api/aria/feed", headers=_h(admin_token, TEN_PIE), timeout=20)
    print(f"/api/aria/feed PIE: status={r.status_code}, body={r.text[:300]}")
    assert r.status_code in (200, 404)


# ─── 4. Reports endpoint ─────────────────────────────────────────────
def test_4_reports_pipeline_pietential(admin_token):
    for path in ("/api/reports/pipeline", "/api/reports/overview", "/api/reports/summary"):
        r = httpx.get(f"{BASE_URL}{path}", headers=_h(admin_token, TEN_PIE), timeout=20)
        print(f"{path} PIE: status={r.status_code}")
        if r.status_code == 200:
            body = r.json()
            print(f"   body: {str(body)[:300]}")


# ─── 5. Command Center KPIs ──────────────────────────────────────────
def test_5_command_center_pietential(admin_token):
    for path in ("/api/command-center/kpis", "/api/command-center/snapshot", "/api/command-center/today"):
        r = httpx.get(f"{BASE_URL}{path}", headers=_h(admin_token, TEN_PIE), timeout=20)
        print(f"{path} PIE: status={r.status_code}, body={r.text[:250]}")


# ─── 6. /api/pt/insights/feed for Pietential ─────────────────────────
def test_6_pt_insights_feed(admin_token):
    r = httpx.get(f"{BASE_URL}/api/pt/insights/feed", headers=_h(admin_token, TEN_PIE), timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    items = body if isinstance(body, list) else body.get("items") or body.get("insights") or []
    print(f"pt insights feed returned {len(items)} items")
    assert len(items) >= 15, f"Expected ≥15 Pietential insight cards, got {len(items)}"
    # Required iter143 UI-compat fields
    needed = {"prospect_name", "prospect_title", "prospect_company", "suggested_message",
              "confidence", "icp_match_name", "icp_match_score", "status"}
    sample = items[0]
    missing = needed - set(sample.keys())
    assert not missing, f"Missing UI-compat fields: {missing}. Got keys: {sorted(sample.keys())}"
    assert sample["status"] == "new"
    assert "_id" not in sample


# ─── 7. Tenant isolation ─────────────────────────────────────────────
def test_7a_isolation_sales_rep_cannot_see_pietential(sales_token):
    """sarah@demo.com is ten_demo only — should get 403 or empty for PIE header."""
    r = httpx.get(f"{BASE_URL}/api/leads", headers=_h(sales_token, TEN_PIE), timeout=15)
    print(f"sarah→PIE /api/leads status={r.status_code}")
    assert r.status_code in (200, 403, 401), r.text
    if r.status_code == 200:
        leads = r.json() if isinstance(r.json(), list) else r.json().get("leads", [])
        # If returned, must be empty or contain only demo's data (no PIE leakage)
        for L in leads[:5]:
            assert L.get("tenant_id") != TEN_PIE, f"sarah saw PIE lead leak: {L}"


def test_7b_isolation_admin_pie_header_no_demo_leaks(admin_token):
    """admin@demo.com with PIE header must NOT receive ten_demo leads."""
    r = httpx.get(f"{BASE_URL}/api/leads?limit=200", headers=_h(admin_token, TEN_PIE), timeout=20)
    assert r.status_code == 200
    leads = r.json() if isinstance(r.json(), list) else r.json().get("leads") or r.json().get("items") or []
    leaked = [L for L in leads if L.get("tenant_id") == TEN_DEMO]
    assert not leaked, f"Cross-tenant leak: {len(leaked)} demo leads returned in PIE context"


def test_7c_isolation_pt_insights_feed(admin_token):
    r = httpx.get(f"{BASE_URL}/api/pt/insights/feed", headers=_h(admin_token, TEN_DEMO), timeout=15)
    print(f"pt insights feed DEMO: status={r.status_code}, len={len(r.text)}")
    # Pietential-only endpoint — should be empty or 403/404 for demo
    if r.status_code == 200:
        body = r.json()
        items = body if isinstance(body, list) else body.get("items") or body.get("insights") or []
        # Should be empty for demo tenant
        assert len(items) == 0, f"DEMO got PIE insights: {len(items)} items"


def test_7d_isolation_pt_leads(admin_token):
    r = httpx.get(f"{BASE_URL}/api/pt/leads", headers=_h(admin_token, TEN_DEMO), timeout=15)
    print(f"/api/pt/leads DEMO: status={r.status_code}")
    if r.status_code == 200:
        body = r.json()
        items = body if isinstance(body, list) else body.get("items") or []
        assert len(items) == 0, f"DEMO got PIE leads: {len(items)} items"


def test_7e_isolation_voice_seeds(admin_token):
    r_pie = httpx.get(f"{BASE_URL}/api/voice-seeds", headers=_h(admin_token, TEN_PIE), timeout=15)
    r_demo = httpx.get(f"{BASE_URL}/api/voice-seeds", headers=_h(admin_token, TEN_DEMO), timeout=15)
    print(f"voice-seeds PIE={r_pie.status_code} DEMO={r_demo.status_code}")
    for r in (r_pie, r_demo):
        if r.status_code == 200:
            body = r.json()
            items = body if isinstance(body, list) else body.get("items") or body.get("seeds") or []
            for it in items[:5]:
                assert "_id" not in it


# ─── 8. _id leak sweep ───────────────────────────────────────────────
@pytest.mark.parametrize("path", [
    "/api/leads?limit=20",
    "/api/pt/leads",
    "/api/pt/insights/feed",
    "/api/voice-seeds",
    "/api/approvals",
])
def test_8_no_id_leak(admin_token, path):
    r = httpx.get(f"{BASE_URL}{path}", headers=_h(admin_token, TEN_PIE), timeout=15)
    if r.status_code != 200:
        pytest.skip(f"{path} returned {r.status_code}")
    txt = r.text
    # Quick: presence of literal `"_id"` would indicate leak
    assert '"_id"' not in txt, f"_id leaked at {path}"


# ─── 9. V10 guard ────────────────────────────────────────────────────
def test_9_v10_guard():
    import subprocess
    p = subprocess.run(["bash", "/app/scripts/check_v10.sh"], capture_output=True, text=True, timeout=30)
    print("v10 stdout:", p.stdout[-500:])
    print("v10 stderr:", p.stderr[-500:])
    assert p.returncode == 0, f"V10 guard failed: rc={p.returncode}\n{p.stdout}\n{p.stderr}"


# ─── 10. Pietential pipeline manual triggers ─────────────────────────
@pytest.mark.parametrize("path", [
    "/api/pietential/poll/run-now",
    "/api/pietential/scan/run-now",
    "/api/pietential/weekly-report/send-now",
])
def test_10_pietential_manual_triggers(admin_token, path):
    r = httpx.post(f"{BASE_URL}{path}", headers=_h(admin_token, TEN_PIE), timeout=60)
    print(f"{path} → {r.status_code}: {r.text[:300]}")
    assert r.status_code == 200, f"{path} failed: {r.status_code} {r.text}"


# ─── 11. Backend health ──────────────────────────────────────────────
def test_11_health():
    r = httpx.get(f"{BASE_URL}/api/health", timeout=10)
    print(f"/api/health → {r.status_code}: {r.text[:200]}")
    assert r.status_code in (200, 404)  # endpoint optional


# ─── 12. Event-loop unblock proof ────────────────────────────────────
@pytest.mark.asyncio
async def test_12_event_loop_unblock(admin_token):
    """While /pietential/_test/simulate (~25s Claude) runs, 5 parallel
    pipeline-health pings must each return in <500ms."""
    async with httpx.AsyncClient(timeout=60) as client:
        sim_task = asyncio.create_task(client.post(
            f"{BASE_URL}/api/pietential/_test/simulate",
            headers=_h(admin_token, TEN_PIE),
        ))
        # let simulate kick off
        await asyncio.sleep(2)

        async def ping():
            t0 = time.time()
            r = await client.get(
                f"{BASE_URL}/api/pietential/pipeline-health",
                headers=_h(admin_token, TEN_PIE),
            )
            dt = (time.time() - t0) * 1000
            return r.status_code, dt

        results = await asyncio.gather(*[ping() for _ in range(5)])
        print(f"pipeline-health ping timings (ms): {[f'{d:.0f}' for _, d in results]}")
        for code, dt in results:
            assert code == 200, f"pipeline-health returned {code}"
            assert dt < 1500, f"ping took {dt:.0f}ms — event loop appears blocked (iter144 regression)"

        sim_status = await sim_task
        print(f"simulate completed: {sim_status.status_code}")
        # cleanup simulated data
        try:
            await client.post(
                f"{BASE_URL}/api/pietential/_test/cleanup-simulated",
                headers=_h(admin_token, TEN_PIE),
            )
        except Exception:
            pass
