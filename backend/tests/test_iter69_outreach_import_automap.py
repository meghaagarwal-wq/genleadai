"""Iter 69 — Saleshandy/Lemlist pull import + Auto-map sales_channels + integrations.

Validates the new endpoints in /api/integrations/{tool}/{test-connection,campaigns,import-leads}
and the extended /api/aria/auto-map/{analyze,publish} for sales_channels + recommended_integrations.

Coverage:
  1. Test-connection without API key → 400.
  2. Test-connection with bogus key → 200 with ok:false (Saleshandy/Lemlist auth errors caught).
  3. GET campaigns without API key → 400.
  4. POST import-leads bubbles error gracefully (no 500).
  5. GET import-logs returns {logs: []} or list-of-objects (no _id leak).
  6. Auto-map /analyze (with stubbed Claude) returns recommended_integrations + sales_channels.
  7. Auto-map /publish persists sales_channels to tenant.settings.sales_channels.
"""
from __future__ import annotations

import io
import sys
import pytest

sys.path.insert(0, "/app/backend")

from fastapi.testclient import TestClient
from server import app  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_auth(client):
    r = client.post("/api/auth/login", json={"email": "admin@demo.com", "password": "Demo1234!"})
    body = r.json()
    token = body.get("token") or body.get("access_token")
    user = body.get("user", {})
    tenant_id = (user.get("tenants") or [{}])[0].get("id") or "ten_demo"
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": tenant_id, "tenant_id": tenant_id}


def _hdrs(auth):
    return {k: v for k, v in auth.items() if k != "tenant_id"}


# ─── Cleanup helper: reset integration_configs at start ────────────────────
@pytest.fixture(autouse=True)
def cleanup_configs(admin_auth, client):
    # Cleanup any leftover Saleshandy/Lemlist configs so we always test the "not connected" path first
    yield
    # Teardown: remove test-created saleshandy/lemlist configs
    for tool in ("saleshandy", "lemlist"):
        client.delete(f"/api/integrations/{tool}/disconnect", headers=_hdrs(admin_auth))


# ── 1. test-connection / campaigns return 400 when not connected ───────────
@pytest.mark.parametrize("tool", ["saleshandy", "lemlist"])
def test_test_connection_400_when_not_connected(client, admin_auth, tool):
    # Ensure not connected first
    client.delete(f"/api/integrations/{tool}/disconnect", headers=_hdrs(admin_auth))
    r = client.post(f"/api/integrations/{tool}/test-connection", headers=_hdrs(admin_auth))
    assert r.status_code == 400
    body = r.json()
    assert "detail" in body
    assert "not connected" in body["detail"].lower() or "api key" in body["detail"].lower()


@pytest.mark.parametrize("tool", ["saleshandy", "lemlist"])
def test_campaigns_400_when_not_connected(client, admin_auth, tool):
    client.delete(f"/api/integrations/{tool}/disconnect", headers=_hdrs(admin_auth))
    r = client.get(f"/api/integrations/{tool}/campaigns", headers=_hdrs(admin_auth))
    assert r.status_code == 400
    assert "api key" in r.json()["detail"].lower() or "not connected" in r.json()["detail"].lower()


# ── 2. test-connection with bogus api_key → 200 ok:false (no 5xx) ──────────
@pytest.mark.parametrize("tool", ["saleshandy", "lemlist"])
def test_test_connection_with_bogus_key(client, admin_auth, tool):
    # Connect with junk key
    r = client.post(
        f"/api/integrations/{tool}/connect",
        headers=_hdrs(admin_auth),
        json={"config": {"api_key": "this-is-totally-invalid-xyz"}},
    )
    assert r.status_code == 200, r.text

    # Now test the connection — should call external API and get back ok:false
    r = client.post(f"/api/integrations/{tool}/test-connection", headers=_hdrs(admin_auth))
    # MUST NOT be a 500. Spec says we catch HTTPException and return {ok:false}.
    assert r.status_code == 200, f"expected 200 (caught error), got {r.status_code}: {r.text}"
    body = r.json()
    assert body.get("ok") is False, body
    assert "error" in body, body
    # Cleanup
    client.delete(f"/api/integrations/{tool}/disconnect", headers=_hdrs(admin_auth))


# ── 3. import-leads bubbles auth error gracefully (no 500) ─────────────────
def test_import_leads_bubbles_auth_error(client, admin_auth):
    tool = "saleshandy"
    # Connect with bogus key
    client.post(
        f"/api/integrations/{tool}/connect",
        headers=_hdrs(admin_auth),
        json={"config": {"api_key": "definitely-not-valid"}},
    )
    r = client.post(
        f"/api/integrations/{tool}/import-leads",
        headers=_hdrs(admin_auth),
        json={"campaign_ids": [], "import_mode": "all"},
    )
    # We expect a 4xx (most likely 400 with "Saleshandy API key invalid") — not 500
    assert r.status_code in (400, 502), f"got {r.status_code}: {r.text}"
    detail = r.json().get("detail", "")
    assert isinstance(detail, str)
    client.delete(f"/api/integrations/{tool}/disconnect", headers=_hdrs(admin_auth))


# ── 4. import-logs returns {logs: []} or list shape ────────────────────────
def test_import_logs_shape(client, admin_auth):
    r = client.get("/api/integrations/import-logs", headers=_hdrs(admin_auth))
    assert r.status_code == 200
    body = r.json()
    assert "logs" in body
    assert isinstance(body["logs"], list)
    # No mongo _id leak
    for log in body["logs"]:
        assert "_id" not in log


# ── 5. Auto-map /analyze returns recommended_integrations + sales_channels ─
def test_automap_analyze_extracts_integrations_and_channels(client, admin_auth, monkeypatch):
    """With a stubbed Claude that returns saleshandy+lemlist+email+linkedin, the
    /analyze response must include extracted.recommended_integrations and
    extracted.sales_channels populated."""
    from routes import aria_auto_map

    async def _fake_claude(text):
        return {
            "icps": [{"label": "CHRO at SaaS", "title_targets": ["CHRO"], "pain_point": "x", "value_prop": "y"}],
            "touchpoints": [
                {"step": 1, "channel": "email", "message_type": "intro", "day": 0, "hour": 9,
                 "aria_role": "autonomous", "message_template": "Hi {{first_name}}", "conditions": {}},
            ],
            "lead_sources": ["Website Form"],
            "recommended_integrations": ["saleshandy", "lemlist"],
            "sales_channels": ["email", "linkedin"],
            "qualification": {},
            "handoff": {},
            "summary": "test",
        }

    monkeypatch.setattr(aria_auto_map, "_claude_analyze", _fake_claude)
    txt = b"We use Saleshandy for outbound and Lemlist for LinkedIn. ICP is CHROs. Email primary, LinkedIn secondary."
    r = client.post(
        "/api/aria/auto-map/analyze",
        headers=_hdrs(admin_auth),
        files={"file": ("gtm.txt", io.BytesIO(txt), "text/plain")},
    )
    assert r.status_code == 200, r.text
    extracted = r.json().get("extracted") or {}
    assert "recommended_integrations" in extracted
    assert "sales_channels" in extracted
    # Should contain at least one of saleshandy/lemlist
    rec = extracted["recommended_integrations"]
    assert any(x in rec for x in ("saleshandy", "lemlist")), rec
    # sales_channels should contain email and linkedin
    sc = extracted["sales_channels"]
    assert "email" in sc
    assert "linkedin" in sc


# ── 6. Auto-map /publish persists sales_channels to tenant prefs ───────────
def test_automap_publish_applies_sales_channels(client, admin_auth):
    """POST /publish with sales_channels=['email','linkedin'] should save to
    tenants.settings.sales_channels. Verify via GET /api/tenant/sales-channels."""
    # Snapshot current prefs
    pre = client.get("/api/tenant/sales-channels", headers=_hdrs(admin_auth))
    assert pre.status_code == 200
    original = pre.json()

    try:
        payload = {
            "icps": [],  # don't pollute the workspace with ICPs
            "touchpoints": [],
            "lead_sources": [],
            "recommended_integrations": ["saleshandy"],
            "sales_channels": ["email", "linkedin"],
            "qualification": {},
            "handoff": {},
            "summary": "test publish",
            "overwrite_journey": False,  # avoid replacing the journey
            "apply_sales_channels": True,
        }
        r = client.post("/api/aria/auto-map/publish", headers=_hdrs(admin_auth), json=payload)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        assert body.get("sales_channels_saved") == ["email", "linkedin"]

        # Verify it actually persisted
        chk = client.get("/api/tenant/sales-channels", headers=_hdrs(admin_auth))
        assert chk.status_code == 200
        prefs = chk.json()
        assert prefs.get("selected_channels") == ["email", "linkedin"]
        assert prefs.get("primary_channel") == "email"
    finally:
        # Restore original prefs to avoid breaking other tests/tenants
        restore = {
            "selected_channels": original.get("selected_channels") or ["email", "linkedin", "whatsapp", "sms", "phone", "website_chat"],
            "priority_order": original.get("priority_order") or original.get("selected_channels"),
            "primary_channel": original.get("primary_channel") or "email",
            "fallback_channels": original.get("fallback_channels") or [],
            "conversation_style": original.get("conversation_style"),
            "selected_preset": original.get("selected_preset"),
        }
        try:
            client.put("/api/tenant/sales-channels", headers=_hdrs(admin_auth), json=restore)
        except Exception:
            pass
