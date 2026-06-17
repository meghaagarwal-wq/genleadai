"""iter158 — Backend tests for the 4-item backlog batch.

(A) B2B Sales KPI sparklines: followups_today, meetings_today, approvals_pending,
    pipeline_value MUST each be objects with `.value` and `.spark` (list[7] numerics).
(B) Multi-touch tracking: register_channel_touch dedups onto pt_leads.source_channels.
(C) ICP drift: by_channel + snoozed_until are present on /b2b-founder. POST snooze
    flips drift_detected to False and re-fetch shows snoozed_until set. Reset after.
"""
import os
import sys
import uuid
import pytest
import requests
from datetime import datetime, timezone

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not set"

DEMO_VIEWER = ("meghaagarwaljain2015@gmail.com", "DemoView2026!")
PIETENTIAL = ("megha@contentvista.com", "Pietential2026!")

sys.path.insert(0, "/app/backend")


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text[:200]}"
    data = r.json()
    tenant_id = (data.get("tenants") or [{}])[0].get("id") or data.get("user", {}).get("tenant_id")
    return data["token"], tenant_id


def _hdr(tok, tenant=None):
    h = {"Authorization": f"Bearer {tok}"}
    if tenant:
        h["X-Tenant-Id"] = tenant
    return h


def _assert_kpi_value_spark(obj, name):
    assert isinstance(obj, dict), f"{name}: expected dict object, got {type(obj).__name__}"
    assert "value" in obj, f"{name}: missing .value (got keys {list(obj.keys())})"
    spark = obj.get("spark")
    assert isinstance(spark, list) and len(spark) == 7, f"{name}: spark not list[7] -> {spark}"
    for i, v in enumerate(spark):
        assert isinstance(v, (int, float)), f"{name}.spark[{i}] not numeric: {v!r}"


@pytest.fixture(scope="module")
def demo_viewer():
    tok, tenant = _login(*DEMO_VIEWER)
    return tok, tenant or "ten_demo"


@pytest.fixture(scope="module")
def pietential():
    tok, tenant = _login(*PIETENTIAL)
    return tok, tenant or "ten_pietential"


# ─────────────── (A) B2B Sales sparklines ───────────────
def test_b2b_sales_kpis_value_and_spark(demo_viewer):
    tok, tenant = demo_viewer
    r = requests.get(f"{BASE_URL}/api/dashboard/b2b-sales",
                     headers=_hdr(tok, tenant), timeout=30)
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    kpis = r.json().get("kpis") or {}
    for name in ("followups_today", "meetings_today", "approvals_pending", "pipeline_value"):
        assert name in kpis, f"b2b-sales kpis missing '{name}': {list(kpis.keys())}"
        _assert_kpi_value_spark(kpis[name], f"b2b-sales.{name}")
    # old shape regression: must NOT be a bare int
    assert not isinstance(kpis["followups_today"], int), "followups_today still int (old shape)"


# ─────────────── (B) Multi-touch register_channel_touch ───────────────
def test_register_channel_touch_dedups_pt_leads():
    """Insert a synthetic pt_lead, call register_channel_touch twice with the
    same channel + once with a different channel, verify $addToSet dedups."""
    from deps import db
    from services.lead_channels import register_channel_touch
    tenant_id = "ten_demo"
    lead_id = f"TEST_lead_{uuid.uuid4().hex[:8]}"
    db["pt_leads"].insert_one({
        "id": lead_id, "tenant_id": tenant_id,
        "first_name": "TEST_iter158", "source_channels": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    try:
        register_channel_touch(tenant_id, lead_id, "email")
        register_channel_touch(tenant_id, lead_id, "email")  # dup → no-op
        register_channel_touch(tenant_id, lead_id, "whatsapp")
        # inbound-style different channel
        register_channel_touch(tenant_id, lead_id, "WhatsApp")  # case folded → dup
        lead = db["pt_leads"].find_one({"id": lead_id})
        chans = sorted(lead.get("source_channels") or [])
        assert chans == ["email", "whatsapp"], f"expected dedup [email, whatsapp], got {chans}"
    finally:
        db["pt_leads"].delete_one({"id": lead_id})
        db["leads"].delete_one({"id": lead_id})


def test_register_channel_touch_noop_on_falsy():
    from services.lead_channels import register_channel_touch
    # should not raise
    register_channel_touch("", "x", "email")
    register_channel_touch("t", "", "email")
    register_channel_touch("t", "x", "")
    register_channel_touch("t", "x", None)


# ─────────────── (C) ICP drift by_channel + snooze flow ───────────────
def _reset_snooze(tenant_id="ten_demo"):
    from deps import db
    db["tenants"].update_one({"id": tenant_id},
                             {"$set": {"icp_drift_snooze_until": None}})


def test_b2b_founder_icp_drift_has_new_fields(demo_viewer):
    _reset_snooze()
    tok, tenant = demo_viewer
    r = requests.get(f"{BASE_URL}/api/dashboard/b2b-founder",
                     headers=_hdr(tok, tenant), timeout=30)
    assert r.status_code == 200, r.text[:300]
    drift = r.json().get("icp_drift") or {}
    assert "by_channel" in drift, f"icp_drift missing 'by_channel': {list(drift.keys())}"
    assert isinstance(drift["by_channel"], list), f"by_channel not list: {drift['by_channel']!r}"
    for row in drift["by_channel"]:
        assert {"channel", "total", "unknown", "unknown_pct"}.issubset(row.keys()), \
            f"by_channel row missing fields: {row}"
    assert "snoozed_until" in drift, f"icp_drift missing 'snoozed_until': {list(drift.keys())}"


def test_icp_drift_snooze_endpoint_and_flag_flip(demo_viewer):
    _reset_snooze()
    tok, tenant = demo_viewer
    # POST snooze
    r = requests.post(f"{BASE_URL}/api/dashboard/icp-drift/snooze",
                      headers=_hdr(tok, tenant), params={"days": 7}, timeout=15)
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    body = r.json()
    assert body.get("ok") is True
    assert body.get("days") == 7
    assert body.get("snoozed_until"), f"snoozed_until missing: {body}"

    # Re-fetch /b2b-founder — drift_detected should be False and snoozed_until set
    r2 = requests.get(f"{BASE_URL}/api/dashboard/b2b-founder",
                      headers=_hdr(tok, tenant), timeout=30)
    assert r2.status_code == 200
    drift = r2.json().get("icp_drift") or {}
    assert drift.get("drift_detected") is False, f"drift_detected not flipped: {drift}"
    assert drift.get("snoozed_until"), f"snoozed_until still null after snooze: {drift}"

    # Reset
    _reset_snooze()


# ─────────────── Tenant isolation regression ───────────────
def test_pietential_b2b_founder_no_cross_tenant_leak(pietential):
    tok, tenant = pietential
    r = requests.get(f"{BASE_URL}/api/dashboard/b2b-founder",
                     headers=_hdr(tok, tenant), timeout=30)
    assert r.status_code == 200, r.text[:300]
    drift = r.json().get("icp_drift") or {}
    # Should have its own by_channel, snoozed_until keys
    assert "by_channel" in drift and "snoozed_until" in drift
