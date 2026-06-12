"""Iter150 Phase B Step 1 — Mode-aware dashboards + SALES_COACH Top 3 Actions."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")

PIETENTIAL_EMAIL = "megha@contentvista.com"
PIETENTIAL_PASS = "Pietential2026!"
DEMO_EMAIL = "meghaagarwaljain2015@gmail.com"
DEMO_PASS = "DemoView2026!"


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def pietential_token():
    return _login(PIETENTIAL_EMAIL, PIETENTIAL_PASS)


@pytest.fixture(scope="module")
def demo_token():
    return _login(DEMO_EMAIL, DEMO_PASS)


# /api/dashboard/_mode — mode discovery for each tenant
class TestDashboardMode:
    def test_mode_pietential(self, pietential_token):
        r = requests.get(f"{BASE_URL}/api/dashboard/_mode", headers={"Authorization": f"Bearer {pietential_token}"}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["tenant_id"] == "ten_pietential"
        assert d["mode"] in ("b2b", "hybrid")
        assert "currency" in d and "hourly_rate" in d
        print(f"Pietential mode: {d}")

    def test_mode_demo(self, demo_token):
        r = requests.get(f"{BASE_URL}/api/dashboard/_mode", headers={"Authorization": f"Bearer {demo_token}"}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["tenant_id"] == "ten_demo"
        assert d["mode"] in ("b2c", "b2b", "hybrid")
        print(f"Demo mode: {d}")


# /api/dashboard/b2c & /api/dashboard/b2b-founder — full payload + tenant isolation
class TestFullDashboards:
    def test_b2c_payload_pietential(self, pietential_token):
        r = requests.get(f"{BASE_URL}/api/dashboard/b2c", headers={"Authorization": f"Bearer {pietential_token}"}, timeout=60)
        assert r.status_code == 200
        d = r.json()
        for k in ("kpis", "momentum", "funnel", "ghost_leads", "lead_sources"):
            assert k in d, f"missing key {k}"

    def test_b2b_founder_payload_pietential(self, pietential_token):
        r = requests.get(f"{BASE_URL}/api/dashboard/b2b-founder", headers={"Authorization": f"Bearer {pietential_token}"}, timeout=60)
        assert r.status_code == 200
        d = r.json()
        for k in ("kpis", "momentum", "channel_performance", "why_now", "deal_risk_flags", "ghost_leads"):
            assert k in d, f"missing key {k}"

    def test_tenant_isolation_b2b_founder(self, pietential_token, demo_token):
        rp = requests.get(f"{BASE_URL}/api/dashboard/b2b-founder", headers={"Authorization": f"Bearer {pietential_token}"}, timeout=60).json()
        rd = requests.get(f"{BASE_URL}/api/dashboard/b2b-founder", headers={"Authorization": f"Bearer {demo_token}"}, timeout=60).json()
        # Make sure flags / ghost leads do not leak
        p_lead_ids = {x.get("lead_id") for x in rp.get("ghost_leads", [])}
        d_lead_ids = {x.get("lead_id") for x in rd.get("ghost_leads", [])}
        if p_lead_ids and d_lead_ids:
            assert p_lead_ids.isdisjoint(d_lead_ids), "Ghost leads leak across tenants!"
        # Tenant header on workspace_name
        p_name = rp.get("header", {}).get("workspace_name")
        d_name = rd.get("header", {}).get("workspace_name")
        assert p_name != d_name or (p_name is None and d_name is None)


# /api/dashboard/b2b-sales — Top 3 Actions + cache + regenerate
class TestSalesDashboardTopActions:
    def _bust_cache(self, token):
        requests.post(f"{BASE_URL}/api/dashboard/top-actions/regenerate", headers={"Authorization": f"Bearer {token}"}, timeout=30)

    def test_first_call_returns_miss_with_3_rows(self, pietential_token):
        self._bust_cache(pietential_token)
        time.sleep(0.5)
        r = requests.get(f"{BASE_URL}/api/dashboard/b2b-sales", headers={"Authorization": f"Bearer {pietential_token}"}, timeout=90)
        assert r.status_code == 200, r.text
        d = r.json()
        top = d.get("top_actions")
        assert top is not None
        print(f"Top actions response keys: {list(top.keys()) if isinstance(top, dict) else type(top)}")
        # If coming_soon (no hot leads etc), confirm rows empty & no Claude
        if top.get("coming_soon"):
            assert top.get("rows") == []
            assert "reason" in top
            pytest.skip(f"No hot leads/risks/approvals to generate plan: {top.get('reason')}")
        assert top.get("cache") == "miss"
        rows = top.get("rows", [])
        assert isinstance(rows, list)
        assert len(rows) == 3, f"Expected 3 rows, got {len(rows)}: {rows}"
        for row in rows:
            assert "action" in row
            # lead/company/why_now are best-effort from Claude
            assert any(k in row for k in ("lead", "company", "why_now"))

    def test_second_call_returns_cache_hit_same_rows(self, pietential_token):
        # ensure we have something cached
        r1 = requests.get(f"{BASE_URL}/api/dashboard/b2b-sales", headers={"Authorization": f"Bearer {pietential_token}"}, timeout=90).json()
        top1 = r1.get("top_actions", {})
        if top1.get("coming_soon"):
            pytest.skip("coming_soon — no cacheable rows")
        r2 = requests.get(f"{BASE_URL}/api/dashboard/b2b-sales", headers={"Authorization": f"Bearer {pietential_token}"}, timeout=60).json()
        top2 = r2.get("top_actions", {})
        assert top2.get("cache") == "hit", f"Expected cache hit, got {top2.get('cache')}"
        assert top1.get("rows") == top2.get("rows"), "Cached rows must be identical."

    def test_regenerate_busts_cache(self, pietential_token):
        # First confirm there's a cached set
        r1 = requests.get(f"{BASE_URL}/api/dashboard/b2b-sales", headers={"Authorization": f"Bearer {pietential_token}"}, timeout=90).json()
        if r1["top_actions"].get("coming_soon"):
            pytest.skip("coming_soon — nothing to regenerate")
        reg = requests.post(f"{BASE_URL}/api/dashboard/top-actions/regenerate", headers={"Authorization": f"Bearer {pietential_token}"}, timeout=30)
        assert reg.status_code == 200
        body = reg.json()
        assert body.get("ok") is True
        assert body.get("cache_cleared") is True
        time.sleep(0.5)
        r2 = requests.get(f"{BASE_URL}/api/dashboard/b2b-sales", headers={"Authorization": f"Bearer {pietential_token}"}, timeout=90).json()
        assert r2["top_actions"].get("cache") == "miss", f"Expected miss after regen, got {r2['top_actions'].get('cache')}"

    def test_demo_b2b_sales_works(self, demo_token):
        r = requests.get(f"{BASE_URL}/api/dashboard/b2b-sales", headers={"Authorization": f"Bearer {demo_token}"}, timeout=90)
        assert r.status_code == 200
        d = r.json()
        assert "top_actions" in d
        assert "kpis" in d
        assert "hot_leads" in d
