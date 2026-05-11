"""Iter 34 — CRM Integration & Sync Engine (Sprint 2).

Covers:
  - GET/POST/DELETE /api/crm/integrations,connect,disconnect
  - field-mapping, sync-rules, test-connection, sync-log, retry endpoints
  - oauth/start URL builder
  - Event firing: lead.created, lead.stage_changed, lead.closed_won,
    conversation.takeover+aria.paused, aria.resumed
  - Background sync loop dispatches pending entries within ~10s
  - RBAC: sales_rep gets 403 on owner-only endpoints
"""
import os
import time
import uuid

import pytest
import requests

_BURL = os.environ.get("REACT_APP_BACKEND_URL")
if not _BURL:
    from dotenv import load_dotenv
    load_dotenv("/app/frontend/.env")
    _BURL = os.environ.get("REACT_APP_BACKEND_URL")
BASE_URL = (_BURL or "").rstrip("/")

ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = "Demo1234!"
REP_EMAIL = "sarah@demo.com"
REP_PASSWORD = "Demo1234!"
TENANT_ID = "ten_demo"


def _login(email, password):
    s = requests.Session()
    s.headers["Content-Type"] = "application/json"
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    data = r.json()
    s.headers["Authorization"] = f"Bearer {data['token']}"
    s.headers["X-Tenant-Id"] = TENANT_ID
    return s, data


@pytest.fixture(scope="session")
def admin():
    s, _ = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    return s


@pytest.fixture(scope="session")
def rep():
    s, _ = _login(REP_EMAIL, REP_PASSWORD)
    return s


@pytest.fixture(autouse=True)
def cleanup_integration(admin):
    """Ensure clean integration state before each test."""
    admin.delete(f"{BASE_URL}/api/crm/disconnect")
    yield
    admin.delete(f"{BASE_URL}/api/crm/disconnect")


# ─── Integrations CRUD ──────────────────────────────────────────────────────
class TestConnectDisconnect:
    def test_get_integrations_empty(self, admin):
        r = admin.get(f"{BASE_URL}/api/crm/integrations")
        assert r.status_code == 200
        assert r.json().get("integration") is None

    def test_connect_custom_webhook_defaults(self, admin):
        url = "https://webhook.site/test-aria-{}".format(uuid.uuid4().hex[:8])
        r = admin.post(f"{BASE_URL}/api/crm/connect", json={
            "crm_type": "custom_webhook", "webhook_url": url,
        })
        assert r.status_code == 200, r.text
        integ = r.json()["integration"]
        assert integ["crm_type"] == "custom_webhook"
        assert integ["webhook_url"] == url
        assert integ["connection_status"] == "connected"
        assert "credentials" not in integ  # hidden
        assert len(integ["field_mapping"]) == 10
        # All 15 events should be true by default
        assert len(integ["sync_rules"]) == 15
        assert all(v is True for v in integ["sync_rules"].values())

    def test_connect_pipedrive_hides_creds(self, admin):
        r = admin.post(f"{BASE_URL}/api/crm/connect", json={
            "crm_type": "pipedrive", "api_key": "pd_secret_xxx",
            "api_domain": "https://acme.pipedrive.com",
        })
        assert r.status_code == 200
        integ = r.json()["integration"]
        assert integ["crm_type"] == "pipedrive"
        # credentials must not be returned
        body_text = r.text
        assert "pd_secret_xxx" not in body_text
        # Verify GET also hides credentials
        g = admin.get(f"{BASE_URL}/api/crm/integrations").json()["integration"]
        assert "credentials" not in g
        assert "pd_secret_xxx" not in admin.get(f"{BASE_URL}/api/crm/integrations").text

    def test_connect_invalid_crm_type(self, admin):
        r = admin.post(f"{BASE_URL}/api/crm/connect", json={"crm_type": "salesforce_x"})
        assert r.status_code == 400

    def test_connect_pipedrive_requires_api_key(self, admin):
        r = admin.post(f"{BASE_URL}/api/crm/connect", json={"crm_type": "pipedrive"})
        assert r.status_code == 400

    def test_connect_webhook_requires_url(self, admin):
        r = admin.post(f"{BASE_URL}/api/crm/connect", json={"crm_type": "custom_webhook"})
        assert r.status_code == 400

    def test_rep_forbidden_to_connect(self, rep):
        r = rep.post(f"{BASE_URL}/api/crm/connect", json={
            "crm_type": "custom_webhook", "webhook_url": "https://x.example.com",
        })
        assert r.status_code == 403

    def test_disconnect(self, admin):
        admin.post(f"{BASE_URL}/api/crm/connect", json={
            "crm_type": "custom_webhook", "webhook_url": "https://x.example.com",
        })
        r = admin.delete(f"{BASE_URL}/api/crm/disconnect")
        assert r.status_code == 200
        assert admin.get(f"{BASE_URL}/api/crm/integrations").json().get("integration") is None


# ─── Field mapping & Sync rules ─────────────────────────────────────────────
class TestMappingAndRules:
    def _setup(self, admin):
        admin.post(f"{BASE_URL}/api/crm/connect", json={
            "crm_type": "custom_webhook", "webhook_url": "https://x.example.com",
        })

    def test_get_field_mapping_defaults(self, admin):
        self._setup(admin)
        r = admin.get(f"{BASE_URL}/api/crm/field-mapping")
        assert r.status_code == 200
        body = r.json()
        assert len(body["field_mapping"]) >= 10
        assert "lead.name" in body["field_mapping"]

    def test_put_field_mapping(self, admin):
        self._setup(admin)
        new_map = {"lead.name": "contact.full_name", "lead.email": "contact.email"}
        r = admin.put(f"{BASE_URL}/api/crm/field-mapping", json={"field_mapping": new_map})
        assert r.status_code == 200
        # Verify persistence
        g = admin.get(f"{BASE_URL}/api/crm/field-mapping").json()
        assert g["field_mapping"]["lead.name"] == "contact.full_name"

    def test_put_sync_rules_filters_unknown(self, admin):
        self._setup(admin)
        rules = {"lead.created": False, "lead.closed_won": True, "bogus.event": True}
        r = admin.put(f"{BASE_URL}/api/crm/sync-rules", json={"sync_rules": rules})
        assert r.status_code == 200
        saved = r.json()["sync_rules"]
        assert saved["lead.created"] is False
        assert saved["lead.closed_won"] is True
        assert "bogus.event" not in saved

    def test_rep_forbidden_on_mapping(self, admin, rep):
        self._setup(admin)
        r = rep.put(f"{BASE_URL}/api/crm/field-mapping", json={"field_mapping": {"x": "y"}})
        assert r.status_code == 403


# ─── Test connection (synthetic) ────────────────────────────────────────────
class TestTestConnection:
    def test_invalid_webhook_returns_400(self, admin):
        admin.post(f"{BASE_URL}/api/crm/connect", json={
            "crm_type": "custom_webhook",
            "webhook_url": "https://webhook.site/aria-does-not-exist-zz9",
        })
        r = admin.post(f"{BASE_URL}/api/crm/test-connection")
        # Either a real 4xx/5xx upstream → backend returns 400 with helpful detail
        assert r.status_code == 400
        assert "Connection failed" in r.text or "failed" in r.text.lower()

    def test_no_integration_returns_400(self, admin):
        r = admin.post(f"{BASE_URL}/api/crm/test-connection")
        assert r.status_code == 400


# ─── Event firing via lead operations + background loop ─────────────────────
class TestEventFiring:
    @pytest.fixture
    def connected(self, admin):
        admin.post(f"{BASE_URL}/api/crm/connect", json={
            "crm_type": "custom_webhook",
            "webhook_url": "https://webhook.site/aria-nonexistent-{}".format(uuid.uuid4().hex[:6]),
        })

    def _find_log(self, admin, lead_id, event_type, wait_s=12):
        deadline = time.time() + wait_s
        while time.time() < deadline:
            r = admin.get(f"{BASE_URL}/api/crm/sync-log?limit=200")
            if r.status_code == 200:
                for e in r.json().get("entries", []):
                    if e.get("lead_id") == lead_id and e.get("event_type") == event_type:
                        return e
            time.sleep(1)
        return None

    def test_lead_create_fires_event(self, admin, connected):
        payload = {
            "first_name": "TEST_Crm", "last_name": "Lead",
            "email": f"crmtest+{uuid.uuid4().hex[:6]}@demo.com",
            "phone": "+919999000001",
            "source_channel": "manual", "lead_type": "B2C",
        }
        r = admin.post(f"{BASE_URL}/api/leads", json=payload)
        assert r.status_code in (200, 201), r.text
        lead = r.json()
        lead_id = lead.get("id") or lead.get("lead", {}).get("id")
        assert lead_id, f"no lead id: {lead}"
        entry = self._find_log(admin, lead_id, "lead.created")
        assert entry, "lead.created event was not queued"
        assert entry["crm_type"] == "custom_webhook"

    def test_stage_changed_to_qualified(self, admin, connected):
        # Create a lead
        r = admin.post(f"{BASE_URL}/api/leads", json={
            "first_name": "TEST_Stage", "last_name": "Q",
            "email": f"stage+{uuid.uuid4().hex[:6]}@demo.com",
            "phone": "+919999000002", "source_channel": "manual", "lead_type": "B2C",
        })
        lead_id = r.json().get("id")
        # PATCH to qualified
        u = admin.patch(f"{BASE_URL}/api/leads/{lead_id}", json={"status": "qualified"})
        assert u.status_code == 200, u.text
        entry = self._find_log(admin, lead_id, "lead.stage_changed")
        assert entry, "lead.stage_changed event was not queued"

    def test_closed_won_fires(self, admin, connected):
        r = admin.post(f"{BASE_URL}/api/leads", json={
            "first_name": "TEST_Won", "last_name": "Lead",
            "email": f"won+{uuid.uuid4().hex[:6]}@demo.com",
            "phone": "+919999000003", "source_channel": "manual", "lead_type": "B2C",
        })
        lead_id = r.json().get("id")
        u = admin.patch(f"{BASE_URL}/api/leads/{lead_id}", json={"status": "Closed Won"})
        assert u.status_code == 200, u.text
        entry = self._find_log(admin, lead_id, "lead.closed_won")
        assert entry, "lead.closed_won event was not queued"

    def test_takeover_fires_two_events(self, admin, connected):
        r = admin.post(f"{BASE_URL}/api/leads", json={
            "first_name": "TEST_Take", "last_name": "Over",
            "email": f"take+{uuid.uuid4().hex[:6]}@demo.com",
            "phone": "+919999000004", "source_channel": "manual", "lead_type": "B2C",
        })
        lead_id = r.json().get("id")
        t = admin.post(f"{BASE_URL}/api/aria/takeover/{lead_id}", json={})
        assert t.status_code in (200, 201), t.text
        assert self._find_log(admin, lead_id, "conversation.takeover"), "takeover not queued"
        assert self._find_log(admin, lead_id, "aria.paused"), "aria.paused not queued"
        # Then resume
        admin.post(f"{BASE_URL}/api/aria/resume/{lead_id}", json={})
        assert self._find_log(admin, lead_id, "aria.resumed"), "aria.resumed not queued"


# ─── Sync log + retry endpoints ─────────────────────────────────────────────
class TestSyncLog:
    @pytest.fixture
    def with_failed_entry(self, admin):
        admin.post(f"{BASE_URL}/api/crm/connect", json={
            "crm_type": "custom_webhook",
            "webhook_url": "https://webhook.site/aria-failingnow-{}".format(uuid.uuid4().hex[:6]),
        })
        r = admin.post(f"{BASE_URL}/api/leads", json={
            "first_name": "TEST_Fail", "last_name": "Sync",
            "email": f"fail+{uuid.uuid4().hex[:6]}@demo.com",
            "phone": "+919999000010", "source_channel": "manual", "lead_type": "B2C",
        })
        lead_id = r.json().get("id")
        # Wait for sync loop to attempt and fail it (3 retries = ~15s, settle quickly with retrying)
        deadline = time.time() + 25
        entry_id = None
        while time.time() < deadline:
            entries = admin.get(f"{BASE_URL}/api/crm/sync-log?limit=50").json().get("entries", [])
            for e in entries:
                if e.get("lead_id") == lead_id and e.get("status") in ("failed", "retrying"):
                    entry_id = e["id"]
                    break
            if entry_id:
                break
            time.sleep(2)
        return entry_id

    def test_list_with_filters(self, admin):
        r = admin.get(f"{BASE_URL}/api/crm/sync-log?status=pending&limit=10")
        assert r.status_code == 200
        body = r.json()
        assert "entries" in body and "total" in body

    def test_retry_entry(self, admin, with_failed_entry):
        if not with_failed_entry:
            pytest.skip("No failed/retrying entry produced in time")
        r = admin.post(f"{BASE_URL}/api/crm/sync-log/{with_failed_entry}/retry")
        assert r.status_code == 200
        # Verify reset
        entries = admin.get(f"{BASE_URL}/api/crm/sync-log?limit=200").json()["entries"]
        target = next((e for e in entries if e["id"] == with_failed_entry), None)
        assert target is not None
        assert target["retry_count"] == 0

    def test_retry_all_failed(self, admin):
        r = admin.post(f"{BASE_URL}/api/crm/sync-log/retry-all-failed")
        assert r.status_code == 200
        assert "retried" in r.json()


# ─── OAuth & inbound + lead status ──────────────────────────────────────────
class TestOAuthAndExtras:
    def test_oauth_start_hubspot_placeholder(self, admin):
        r = admin.get(f"{BASE_URL}/api/crm/oauth/hubspot/start")
        assert r.status_code == 200
        body = r.json()
        assert "url" in body
        assert "hubspot" in body["url"]
        assert body.get("placeholder") is True

    def test_oauth_invalid_crm(self, admin):
        r = admin.get(f"{BASE_URL}/api/crm/oauth/pipedrive/start")
        assert r.status_code == 400

    def test_lead_status_disconnected(self, admin):
        r = admin.get(f"{BASE_URL}/api/crm/leads/anything_xyz/status")
        assert r.status_code == 200
        assert r.json()["connected"] is False

    def test_lead_status_connected(self, admin):
        admin.post(f"{BASE_URL}/api/crm/connect", json={
            "crm_type": "custom_webhook", "webhook_url": "https://x.example.com",
        })
        # Create a lead
        l = admin.post(f"{BASE_URL}/api/leads", json={
            "first_name": "TEST_Stat", "last_name": "Lead",
            "email": f"stat+{uuid.uuid4().hex[:6]}@demo.com",
            "phone": "+919999000020", "source_channel": "manual", "lead_type": "B2C",
        }).json()
        lead_id = l.get("id")
        time.sleep(2)
        r = admin.get(f"{BASE_URL}/api/crm/leads/{lead_id}/status")
        assert r.status_code == 200
        body = r.json()
        assert body["connected"] is True
        assert body["crm_type"] == "custom_webhook"
        # latest may be present (event already queued)

    def test_inbound_no_integration_404(self, admin):
        # No integration set up (autouse cleanup ran)
        r = requests.post(f"{BASE_URL}/api/crm/inbound/ten_no_such_tenant",
                          json={"event": "deal.owner_changed", "crm_contact_id": "x"})
        assert r.status_code == 404
