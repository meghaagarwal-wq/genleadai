"""iter109 Batch 2 — Command Center KPI/Signals/Pipeline/Next-Scan endpoints regression."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")

ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = "Demo1234!"
PIET_EMAIL = "megha@contentvista.com"
PIET_PASSWORD = "Piet-4vRQ-lDa2-ttcO"


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()["token"]


def _headers(token, tenant_id=None):
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if tenant_id:
        h["X-Tenant-Id"] = tenant_id
    return h


@pytest.fixture(scope="module")
def demo_token():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def piet_token():
    return _login(PIET_EMAIL, PIET_PASSWORD)


# ─── Hybrid workspace (ten_demo) ───────────────────────────────────────
class TestHybridKPIs:
    def test_kpis_hybrid_shape(self, demo_token):
        r = requests.get(f"{BASE_URL}/api/aria/command-center/kpis",
                         headers=_headers(demo_token, "ten_demo"), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["mode"] == "hybrid", f"expected hybrid mode, got {data['mode']}"
        keys = [it["key"] for it in data["items"]]
        assert keys == ["total_leads_plus_prospects", "instinct_signals", "calls_booked_today", "aria_actions_today"], keys
        for it in data["items"]:
            assert isinstance(it["value"], int)
            assert "label" in it
        # ten_demo should have ~137 leads+prospects per main-agent context
        total = next(it["value"] for it in data["items"] if it["key"] == "total_leads_plus_prospects")
        assert total > 0, f"expected >0 leads+prospects for ten_demo, got {total}"

    def test_signals_endpoint(self, demo_token):
        r = requests.get(f"{BASE_URL}/api/aria/command-center/signals",
                         headers=_headers(demo_token, "ten_demo"), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "signals" in data and "total_pending" in data
        assert isinstance(data["signals"], list)
        assert len(data["signals"]) <= 2
        assert isinstance(data["total_pending"], int)

    def test_pipeline_endpoint(self, demo_token):
        r = requests.get(f"{BASE_URL}/api/aria/command-center/pipeline",
                         headers=_headers(demo_token, "ten_demo"), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "leads" in data
        assert isinstance(data["leads"], list)
        assert len(data["leads"]) <= 6
        # ensure no _id leaked
        for lead in data["leads"]:
            assert "_id" not in lead

    def test_next_scan_endpoint(self, demo_token):
        r = requests.get(f"{BASE_URL}/api/aria/command-center/next-scan",
                         headers=_headers(demo_token, "ten_demo"), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "next_scan_time" in data and "timezone" in data
        assert isinstance(data["next_scan_time"], str)
        assert isinstance(data["timezone"], str)


# ─── B2B workspace (ten_pietential) ────────────────────────────────────
class TestB2BKPIs:
    def test_kpis_b2b_shape(self, piet_token):
        r = requests.get(f"{BASE_URL}/api/aria/command-center/kpis",
                         headers=_headers(piet_token, "ten_pietential"), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["mode"] == "b2b", f"expected b2b mode, got {data['mode']}"
        keys = [it["key"] for it in data["items"]]
        assert keys == ["signals_today", "prospects_scanned", "high_conf_signals", "cards_actioned"], keys
        for it in data["items"]:
            assert isinstance(it["value"], int)

    def test_b2b_signals_and_pipeline(self, piet_token):
        r1 = requests.get(f"{BASE_URL}/api/aria/command-center/signals",
                          headers=_headers(piet_token, "ten_pietential"), timeout=20)
        assert r1.status_code == 200
        r2 = requests.get(f"{BASE_URL}/api/aria/command-center/pipeline",
                          headers=_headers(piet_token, "ten_pietential"), timeout=20)
        assert r2.status_code == 200
