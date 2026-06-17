"""
iter157 — Backend tests for dashboard KPI sparkline arrays.

Validates:
  - GET /api/dashboard/b2c (demo viewer): kpis include `spark` array of 7 numbers
      for leads_today, active_convos, bookings_week, revenue_pipeline.
  - GET /api/dashboard/b2b-founder (demo viewer): kpis include `spark` array of 7
      numbers for leads_month, high_intent, meetings, signals.
  - Tenant isolation regression: Pietential owner can still fetch
      /api/dashboard/b2b-founder (HTTP 200) after the chart upgrade.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not set"

DEMO_VIEWER = ("meghaagarwaljain2015@gmail.com", "DemoView2026!")
PIETENTIAL = ("megha@contentvista.com", "Pietential2026!")


def _login(email, password):
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=15,
    )
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    data = r.json()
    tenant_id = (data.get("tenants") or [{}])[0].get("id") or data.get("user", {}).get("tenant_id")
    return data["token"], tenant_id


def _headers(tok, tenant=None):
    h = {"Authorization": f"Bearer {tok}"}
    if tenant:
        h["X-Tenant-Id"] = tenant
    return h


def _assert_spark(kpi_obj, kpi_name):
    """Validate that a KPI tile dict has spark = list[7] of numerics."""
    assert isinstance(kpi_obj, dict), f"{kpi_name}: expected dict, got {type(kpi_obj).__name__}"
    spark = kpi_obj.get("spark")
    assert spark is not None, f"{kpi_name}: missing 'spark' field. keys={list(kpi_obj.keys())}"
    assert isinstance(spark, list), f"{kpi_name}: spark not a list, got {type(spark).__name__}"
    assert len(spark) == 7, f"{kpi_name}: spark length={len(spark)} (expected 7) -> {spark}"
    for i, v in enumerate(spark):
        assert isinstance(v, (int, float)), f"{kpi_name}.spark[{i}] not numeric: {v!r}"


@pytest.fixture(scope="module")
def demo_viewer():
    tok, tenant = _login(*DEMO_VIEWER)
    return tok, tenant or "ten_demo"


@pytest.fixture(scope="module")
def pietential():
    tok, tenant = _login(*PIETENTIAL)
    return tok, tenant or "ten_pietential"


# ───────────────────────── B2C spark arrays ─────────────────────────
def test_b2c_kpis_have_spark_arrays(demo_viewer):
    tok, tenant = demo_viewer
    r = requests.get(
        f"{BASE_URL}/api/dashboard/b2c",
        headers=_headers(tok, tenant),
        timeout=30,
    )
    assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
    kpis = r.json().get("kpis") or {}
    for name in ("leads_today", "active_convos", "bookings_week", "revenue_pipeline"):
        assert name in kpis, f"b2c kpis missing '{name}': keys={list(kpis.keys())}"
        _assert_spark(kpis[name], f"b2c.{name}")


# ─────────────────────── B2B Founder spark arrays ────────────────────
def test_b2b_founder_kpis_have_spark_arrays(demo_viewer):
    tok, tenant = demo_viewer
    r = requests.get(
        f"{BASE_URL}/api/dashboard/b2b-founder",
        headers=_headers(tok, tenant),
        timeout=30,
    )
    assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
    kpis = r.json().get("kpis") or {}
    for name in ("leads_month", "high_intent", "meetings", "signals"):
        assert name in kpis, f"b2b-founder kpis missing '{name}': keys={list(kpis.keys())}"
        _assert_spark(kpis[name], f"b2b-founder.{name}")


# ─────────────────── Tenant isolation regression ────────────────────
def test_pietential_b2b_founder_still_200(pietential):
    tok, tenant = pietential
    r = requests.get(
        f"{BASE_URL}/api/dashboard/b2b-founder",
        headers=_headers(tok, tenant),
        timeout=30,
    )
    assert r.status_code == 200, f"Pietential /api/dashboard/b2b-founder regressed: {r.status_code} {r.text[:300]}"
    # Should still return parseable JSON
    data = r.json()
    assert isinstance(data, dict), "Expected dict response"
