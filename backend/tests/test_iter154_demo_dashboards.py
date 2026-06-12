"""
iter154 — Backend tests for demo dashboards seeding + endpoints.

Validates:
  - POST /api/demo/reset (admin@demo.com) runs both iter148 + iter154 seeders
  - GET /api/dashboard/b2c (demo viewer)  → all coming_soon flags False
  - GET /api/dashboard/b2b-founder        → signal_attribution rows, why_now, founder_flags
  - GET /api/dashboard/b2b-sales          → hot_leads, pipeline ≥6, top_actions 3 rows
  - Tenant isolation: Pietential dashboards must NOT see demo leads
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not set"

ADMIN = ("admin@demo.com", "Demo1234!")
DEMO_VIEWER = ("meghaagarwaljain2015@gmail.com", "DemoView2026!")
PIETENTIAL = ("megha@contentvista.com", "Pietential2026!")

DEMO_LEAD_NAMES = {
    "Sarah Chen", "Arjun Mehta", "James Whitfield",
    "Priya Sharma", "Rahul Verma", "Ananya Iyer",
}


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password},
                      timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    data = r.json()
    return data["token"], data


@pytest.fixture(scope="module")
def admin_token():
    tok, _ = _login(*ADMIN)
    return tok


@pytest.fixture(scope="module")
def demo_viewer_token():
    tok, payload = _login(*DEMO_VIEWER)
    tenant_id = (payload.get("tenants") or [{}])[0].get("id") or payload.get("user", {}).get("tenant_id") or "ten_demo"
    return tok, tenant_id


@pytest.fixture(scope="module")
def pietential_token():
    tok, payload = _login(*PIETENTIAL)
    tenant_id = (payload.get("tenants") or [{}])[0].get("id") or payload.get("user", {}).get("tenant_id") or "ten_pietential"
    return tok, tenant_id


def _h(tok, tenant=None):
    h = {"Authorization": f"Bearer {tok}"}
    if tenant:
        h["X-Tenant-Id"] = tenant
    return h


# ───────────────────────── 1. demo/reset ─────────────────────────
def test_demo_reset_runs_both_seeders(admin_token):
    r = requests.post(f"{BASE_URL}/api/demo/reset",
                      headers=_h(admin_token, "ten_demo"), timeout=120)
    assert r.status_code == 200, f"reset failed: {r.status_code} {r.text[:500]}"
    body = r.json()
    assert body.get("ok") is True
    assert body.get("tenant_id") == "ten_demo"
    # iter154 should not have raised
    purged = body.get("purged", {})
    assert "iter154_error" not in purged, f"iter154 seeder errored: {purged.get('iter154_error')}"


# ───────────────── 2. B2C dashboard ────────────────────
def test_b2c_dashboard_no_coming_soon(demo_viewer_token):
    tok, tenant = demo_viewer_token
    r = requests.get(f"{BASE_URL}/api/dashboard/b2c", headers=_h(tok, tenant), timeout=30)
    assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
    d = r.json()

    rf = d.get("revenue_forecast") or {}
    assert rf.get("coming_soon") is False, f"revenue_forecast.coming_soon != False: {rf}"

    ap = d.get("asset_performance") or {}
    assert ap.get("coming_soon") is False
    assert len(ap.get("rows", [])) >= 5, f"asset_performance rows={len(ap.get('rows', []))}"

    co = d.get("channel_overlap") or {}
    assert co.get("coming_soon") is False
    assert len(co.get("rows", [])) >= 3, f"channel_overlap rows={len(co.get('rows', []))}"

    cpql = d.get("cost_per_qualified_lead") or {}
    assert cpql.get("coming_soon") is False
    assert len(cpql.get("rows", [])) >= 3

    gl = d.get("ghost_leads") or {}
    gl_rows = gl.get("rows", gl) if isinstance(gl, dict) else gl
    assert len(gl_rows) >= 2, f"ghost_leads count={len(gl_rows)}"

    conv = d.get("conversations") or {}
    conv_rows = conv.get("rows", conv) if isinstance(conv, dict) else conv
    assert len(conv_rows) >= 4, f"conversations count={len(conv_rows)}"

    seq = d.get("sequences") or {}
    seq_rows = seq.get("rows", seq) if isinstance(seq, dict) else seq
    assert len(seq_rows) >= 3

    kpis = d.get("kpis") or {}
    # kpis values are wrapped: {"value": N, "trend": {...}}
    def _kpi_val(k):
        v = kpis.get(k)
        return v.get("value") if isinstance(v, dict) else (v or 0)
    assert _kpi_val("leads_today") >= 1, f"kpis={kpis}"
    assert _kpi_val("bookings_week") >= 1


# ───────────────── 3. B2B Founder dashboard ────────────────────
def test_b2b_founder_dashboard(demo_viewer_token):
    tok, tenant = demo_viewer_token
    r = requests.get(f"{BASE_URL}/api/dashboard/b2b-founder", headers=_h(tok, tenant), timeout=30)
    assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
    d = r.json()

    sa = d.get("signal_attribution") or {}
    assert sa.get("coming_soon") is False, f"signal_attribution: {sa}"
    rows = sa.get("rows", [])
    assert len(rows) >= 3, f"signal_attribution rows={len(rows)}"
    sample = rows[0]
    for k in ("signal_type", "leads", "meetings", "conv_rate"):
        assert k in sample, f"missing {k} in signal_attribution row: {sample}"

    cp = d.get("channel_performance") or {}
    cp_rows = cp.get("rows", cp) if isinstance(cp, dict) else cp
    assert len(cp_rows) >= 4, f"channel_performance rows={len(cp_rows)}"

    wn = d.get("why_now") or {}
    wn_rows = wn.get("rows", wn) if isinstance(wn, dict) else wn
    assert len(wn_rows) >= 5, f"why_now={len(wn_rows)}"

    ff = d.get("founder_flags") or {}
    ff_rows = ff.get("rows", ff) if isinstance(ff, dict) else ff
    assert len(ff_rows) >= 3

    drf = d.get("deal_risk_flags") or {}
    drf_rows = drf.get("rows", drf) if isinstance(drf, dict) else drf
    assert len(drf_rows) >= 1

    gl = d.get("ghost_leads") or {}
    gl_rows = gl.get("rows", gl) if isinstance(gl, dict) else gl
    assert len(gl_rows) >= 2


# ───────────────── 4. B2B Sales dashboard ────────────────────
def test_b2b_sales_dashboard(demo_viewer_token):
    tok, tenant = demo_viewer_token
    r = requests.get(f"{BASE_URL}/api/dashboard/b2b-sales", headers=_h(tok, tenant), timeout=30)
    assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
    d = r.json()

    hot = d.get("hot_leads") or {}
    hot_rows = hot.get("rows", hot) if isinstance(hot, dict) else hot
    assert len(hot_rows) == 3, f"hot_leads={len(hot_rows)}"

    pipe = d.get("pipeline") or {}
    pipe_rows = pipe.get("rows", pipe) if isinstance(pipe, dict) else pipe
    assert len(pipe_rows) >= 6, f"pipeline rows={len(pipe_rows)}"
    stages = {r_.get("pipeline_stage") or r_.get("stage") or r_.get("status") for r_ in pipe_rows if isinstance(r_, dict)}
    stages.discard(None)
    assert len(stages) >= 2, f"pipeline stages={stages}"

    agenda = d.get("agenda") or {}
    agenda_rows = agenda.get("rows", agenda) if isinstance(agenda, dict) else agenda
    assert len(agenda_rows) >= 1

    aq = d.get("approval_queue") or {}
    aq_rows = aq.get("rows", aq) if isinstance(aq, dict) else aq
    assert len(aq_rows) >= 2, f"approval_queue={len(aq_rows)}"

    drf = d.get("deal_risk_flags") or {}
    drf_rows = drf.get("rows", drf) if isinstance(drf, dict) else drf
    assert len(drf_rows) >= 1

    at3 = d.get("attribution_top3") or []
    if isinstance(at3, dict):
        assert at3.get("coming_soon") is not True
        at3_rows = at3.get("rows", [])
    else:
        at3_rows = at3
    assert len(at3_rows) >= 1, f"attribution_top3={at3}"

    ta = d.get("top_actions") or {}
    ta_rows = ta.get("rows", [])
    assert len(ta_rows) == 3, f"top_actions rows={len(ta_rows)}"


# ───────────────── 5. Tenant isolation ────────────────────
def test_pietential_does_not_see_demo_leads(pietential_token):
    tok, tenant = pietential_token
    # Try all 3 dashboards and ensure no demo lead name appears
    for path in ("/api/dashboard/b2b-founder", "/api/dashboard/b2b-sales", "/api/dashboard/b2c"):
        r = requests.get(f"{BASE_URL}{path}", headers=_h(tok, tenant), timeout=30)
        if r.status_code != 200:
            continue
        body_text = r.text
        for name in DEMO_LEAD_NAMES:
            assert name not in body_text, f"DEMO LEAK in {path}: '{name}' visible to Pietential"
