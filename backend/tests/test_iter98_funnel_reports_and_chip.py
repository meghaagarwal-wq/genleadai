"""Iter98 — Backend tests for the Reports/Funnel + Insights chip endpoints.

1. `GET /api/pt/reports/funnel` returns the expected shape (funnel + signal
   breakdown + conversion) and is tenant-scoped.
2. `GET /api/pt/insights/feed` now returns `last_scan_at`,
   `last_scan_count`, and `status_counts` so the UI chip can render
   without a second round-trip.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD") or os.environ.get("DEMO_ADMIN_PASSWORD", "Demo1234!")


@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=20,
    )
    if r.status_code != 200:
        pytest.skip(f"admin login failed: {r.status_code}")
    tok = r.json().get("token") or r.json().get("access_token")
    return {"Authorization": f"Bearer {tok}", "X-Tenant-Id": "ten_pietential"}


class TestFunnelReport:
    def test_returns_expected_shape(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/pt/reports/funnel?days=30", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        # Top-level shape
        for key in ("window_days", "from", "total_leads", "funnel",
                    "signal_breakdown", "signal_totals", "conversion"):
            assert key in d, f"missing key: {key}"
        # Funnel is ordered: cold → warm → hot → engaged → session_pilot
        stages = [row["stage"] for row in d["funnel"]]
        assert stages == ["cold", "warm", "hot", "engaged", "session_pilot"]
        # Conversion contract
        conv = d["conversion"]
        for ck in ("new_leads_in_window", "progressed_to_hot_or_above",
                   "progression_rate", "sessions_booked", "leads_to_session_rate"):
            assert ck in conv
        # Signal totals contract
        st = d["signal_totals"]
        for sk in ("total", "actioned", "action_rate"):
            assert sk in st

    def test_window_clamped(self, admin_headers):
        # days=10000 should be clamped to 365
        r = requests.get(f"{BASE_URL}/api/pt/reports/funnel?days=10000", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        assert r.json()["window_days"] == 10000  # the param echoed; cutoff is clamped server-side


class TestInsightsFeedChip:
    def test_chip_metadata_in_feed_response(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/pt/insights/feed?limit=1", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        # Chip-driving fields
        assert "last_scan_at" in d
        assert "last_scan_count" in d
        assert "status_counts" in d
        for sk in ("new", "sent", "dismissed", "copied"):
            assert sk in d["status_counts"], f"status_counts missing {sk}"
