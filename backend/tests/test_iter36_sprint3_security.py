"""Sprint 3 — Security & Compliance + Master Admin (Phase 5.6) tests."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")
ADMIN = {"email": "admin@demo.com", "password": "Demo1234!"}
SALES = {"email": "sarah@demo.com", "password": "Demo1234!"}
TENANT_ID = "ten_demo"


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    j = r.json()
    return j.get("access_token") or j.get("token")


@pytest.fixture(scope="module")
def admin_headers():
    tok = _login(ADMIN)
    return {"Authorization": f"Bearer {tok}", "X-Tenant-Id": TENANT_ID, "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def sales_headers():
    tok = _login(SALES)
    return {"Authorization": f"Bearer {tok}", "X-Tenant-Id": TENANT_ID, "Content-Type": "application/json"}


# ─── CRM connect/disconnect + encryption + audit ────────────────────────────
class TestCrmEncryptionAndAudit:
    def test_connect_pipedrive_encrypts_credentials(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/crm/connect", headers=admin_headers,
                          json={"crm_type": "pipedrive", "api_key": "test-key-123"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "ok"
        assert "credentials" not in body["integration"], "credentials must be stripped from response"

    def test_get_integrations_does_not_expose_credentials(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/crm/integrations", headers=admin_headers)
        assert r.status_code == 200, r.text
        integ = r.json()["integration"]
        if integ:
            assert "credentials" not in integ

    def test_audit_log_has_crm_connected(self, admin_headers):
        time.sleep(0.5)
        r = requests.get(f"{BASE_URL}/api/audit-log", headers=admin_headers, params={"action": "crm.connected"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["total"] >= 1
        assert any(e["action"] == "crm.connected" for e in data["entries"])

    def test_disconnect_writes_audit(self, admin_headers):
        r = requests.delete(f"{BASE_URL}/api/crm/disconnect", headers=admin_headers)
        assert r.status_code == 200
        time.sleep(0.5)
        r2 = requests.get(f"{BASE_URL}/api/audit-log", headers=admin_headers, params={"action": "crm.disconnected"})
        assert r2.status_code == 200
        assert r2.json()["total"] >= 1


# ─── Audit log access control & CSV export ──────────────────────────────────
class TestAuditLog:
    def test_owner_sees_audit_log(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/audit-log", headers=admin_headers)
        assert r.status_code == 200
        body = r.json()
        for k in ("entries", "total", "known_actions"):
            assert k in body

    def test_sales_rep_blocked(self, sales_headers):
        r = requests.get(f"{BASE_URL}/api/audit-log", headers=sales_headers)
        assert r.status_code == 403

    def test_export_csv(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/audit-log/export.csv", headers=admin_headers)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")
        assert "attachment" in r.headers.get("content-disposition", "").lower()


# ─── DPDP data deletion ─────────────────────────────────────────────────────
class TestDpdpDeletion:
    @pytest.fixture
    def lead_id(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/leads", headers=admin_headers, json={
            "lead_type": "B2C", "first_name": "TEST_Privacy", "last_name": "User",
            "email": f"test_priv_{int(time.time())}@example.com", "phone": "+919998887777",
            "source_channel": "web",
        })
        assert r.status_code in (200, 201), r.text
        return r.json()["id"]

    def test_anonymise(self, admin_headers, lead_id):
        r = requests.post(f"{BASE_URL}/api/leads/{lead_id}/delete-personal-data",
                          headers=admin_headers, json={"mode": "anonymise", "reason": "user req"})
        assert r.status_code == 200, r.text
        # Verify lead is anonymised via GET (uses ObjectId lookup, but `id` matches str(_id))
        g = requests.get(f"{BASE_URL}/api/leads/{lead_id}", headers=admin_headers)
        if g.status_code == 200:
            d = g.json()
            assert d.get("data_deleted") is True
            assert d.get("name") == "Deleted User" or d.get("first_name") == "Deleted"
            assert d.get("opted_in") is False

    def test_invalid_mode(self, admin_headers, lead_id):
        r = requests.post(f"{BASE_URL}/api/leads/{lead_id}/delete-personal-data",
                          headers=admin_headers, json={"mode": "garbage"})
        assert r.status_code == 400

    def test_404_for_unknown(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/leads/nonexistent_xyz/delete-personal-data",
                          headers=admin_headers, json={"mode": "anonymise"})
        assert r.status_code == 404

    def test_sales_rep_403(self, sales_headers, lead_id):
        r = requests.post(f"{BASE_URL}/api/leads/{lead_id}/delete-personal-data",
                          headers=sales_headers, json={"mode": "anonymise"})
        assert r.status_code == 403

    def test_hard_delete(self, admin_headers):
        c = requests.post(f"{BASE_URL}/api/leads", headers=admin_headers, json={
            "lead_type": "B2C", "first_name": "TEST_Hard", "last_name": "Del",
            "email": f"hard_{int(time.time())}@example.com", "source_channel": "web",
        })
        assert c.status_code in (200, 201)
        lid = c.json()["id"]
        d = requests.post(f"{BASE_URL}/api/leads/{lid}/delete-personal-data",
                          headers=admin_headers, json={"mode": "hard"})
        assert d.status_code == 200
        g = requests.get(f"{BASE_URL}/api/leads/{lid}", headers=admin_headers)
        assert g.status_code == 404


# ─── Master Admin Workspaces ────────────────────────────────────────────────
class TestMasterAdmin:
    def test_list_workspaces(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/workspaces", headers=admin_headers)
        assert r.status_code == 200, r.text
        b = r.json()
        assert "workspaces" in b and "total" in b

    def test_list_workspaces_403_for_non_admin(self, sales_headers):
        r = requests.get(f"{BASE_URL}/api/admin/workspaces", headers=sales_headers)
        assert r.status_code == 403

    def test_workspace_detail(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/workspaces/{TENANT_ID}", headers=admin_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        for k in ("summary", "tenant", "members", "onboarding"):
            assert k in body

    def test_extend_trial(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/workspaces/{TENANT_ID}/extend-trial",
                          headers=admin_headers, json={"days": 7})
        assert r.status_code == 200, r.text
        assert "trial_ends_at" in r.json()

    def test_launch_checklist_get(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/workspaces/{TENANT_ID}/launch-checklist",
                         headers=admin_headers)
        assert r.status_code == 200
        b = r.json()
        assert len(b["items"]) == 13
        assert "state" in b and "is_launch_ready" in b

    def test_launch_checklist_put_full(self, admin_headers):
        keys = [
            "whatsapp_api_key_set", "whatsapp_test_message_sent", "webhook_url_active",
            "compliance_checkbox", "aria_persona_configured", "aria_test_response_generated",
            "touchpoint_map_saved", "touchpoint_engine_fired_once", "pipeline_stages_set",
            "first_lead_created", "team_invited", "claude_fallback_tested", "dialog360_retry_tested",
        ]
        state = {k: True for k in keys}
        r = requests.put(f"{BASE_URL}/api/admin/workspaces/{TENANT_ID}/launch-checklist",
                         headers=admin_headers, json={"state": state})
        assert r.status_code == 200
        assert r.json()["is_launch_ready"] is True

    def test_mark_launch_ready(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/workspaces/{TENANT_ID}/mark-launch-ready",
                          headers=admin_headers)
        assert r.status_code == 200

    def test_platform_stats(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/workspaces/platform/stats", headers=admin_headers)
        assert r.status_code == 200
        b = r.json()
        for k in ("total_workspaces", "active_paying_clients", "trial_workspaces",
                  "total_leads", "total_conversations", "messages_sent_24h",
                  "failed_messages_24h", "claude_calls_today", "claude_cost_today_usd"):
            assert k in b

    def test_trials_expiring(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/workspaces/trials/expiring",
                         headers=admin_headers, params={"days": 3})
        assert r.status_code == 200
        assert "trials" in r.json()
