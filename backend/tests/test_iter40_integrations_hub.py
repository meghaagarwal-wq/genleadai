"""Iter40 — Integration Hub + Conversations + Legal pages backend tests."""
import os
import time
import uuid
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")
TENANT = "ten_demo"
ADMIN = {"email": "admin@demo.com", "password": "Demo1234!"}


@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(f"{BASE}/api/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200, r.text
    token = r.json().get("token") or r.json().get("access_token")
    assert token
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": TENANT, "Content-Type": "application/json"}


# ─── Integration Hub: GET /list ──────────────────────────────────────────────
class TestIntegrationList:
    def test_list_returns_eight(self, admin_headers):
        r = requests.get(f"{BASE}/api/integrations/list", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        items = r.json()["integrations"]
        types = {i["type"] for i in items}
        assert types == {"ga4", "meta_capi", "zapier", "make", "typeform", "instantly", "google_ads", "apollo"}
        for it in items:
            assert {"type", "label", "category", "direction", "status"} <= set(it.keys())


# ─── Connect + masking + disconnect ──────────────────────────────────────────
class TestConnectFlow:
    def test_connect_zapier(self, admin_headers):
        r = requests.post(
            f"{BASE}/api/integrations/zapier/connect",
            headers=admin_headers,
            json={"config": {"webhook_url": "https://example.com/hook-test"}},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()["integration"]
        assert data["status"] == "connected"
        assert data["config"]["webhook_url"]

    def test_connect_ga4_masks_secret(self, admin_headers):
        r = requests.post(
            f"{BASE}/api/integrations/ga4/connect",
            headers=admin_headers,
            json={"config": {"measurement_id": "G-TESTABC123", "api_secret": "SECRET_TOKEN_VALUE_1234"}},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        cfg = r.json()["integration"]["config"]
        # api_secret must be masked (key contains 'secret')
        assert "•" in cfg["api_secret"], f"api_secret should be masked, got: {cfg['api_secret']}"
        assert cfg["measurement_id"] == "G-TESTABC123"

    def test_unknown_integration_returns_404(self, admin_headers):
        r = requests.post(
            f"{BASE}/api/integrations/bogus_kind/connect",
            headers=admin_headers,
            json={"config": {}},
            timeout=15,
        )
        assert r.status_code == 404


# ─── Test endpoint (fires test event) ────────────────────────────────────────
class TestTestEndpoint:
    def test_zapier_test_with_bad_url(self, admin_headers):
        # Existing zapier config has https://example.com/hook-test which returns 404
        r = requests.post(f"{BASE}/api/integrations/zapier/test", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        body = r.json()
        # example.com returns 404 → ok=false expected
        assert body["ok"] is False
        assert "message" in body

    def test_test_for_not_configured(self, admin_headers):
        # Disconnect make first then call test
        requests.delete(f"{BASE}/api/integrations/make/disconnect", headers=admin_headers, timeout=10)
        r = requests.post(f"{BASE}/api/integrations/make/test", headers=admin_headers, timeout=15)
        assert r.status_code == 404


# ─── Inbound webhooks (PUBLIC — no auth) ─────────────────────────────────────
class TestInboundWebhooks:
    def test_typeform_creates_lead(self):
        uniq = uuid.uuid4().hex[:8]
        body = {
            "form_response": {
                "form_id": "abc",
                "answers": [
                    {"type": "short_text", "field": {"ref": "first_name"}, "short_text": f"TestTF{uniq}"},
                    {"type": "short_text", "field": {"ref": "last_name"}, "short_text": "User"},
                    {"type": "email", "field": {"ref": "email"}, "email": f"tf+{uniq}@example.com"},
                    {"type": "phone_number", "field": {"ref": "phone"}, "phone_number": f"+91900000{uniq[:4]}"},
                    {"type": "long_text", "field": {"ref": "message"}, "long_text": "Interested in demo"},
                ],
            }
        }
        r = requests.post(f"{BASE}/api/integrations/typeform/webhook/{TENANT}", json=body, timeout=20)
        assert r.status_code == 200, r.text
        out = r.json()
        assert out.get("lead_id") or out.get("status") in ("ok", "captured", "duplicated", "deduplicated") or out.get("deduplicated") is not None

    def test_instantly_creates_lead(self):
        uniq = uuid.uuid4().hex[:8]
        body = {
            "firstName": f"Inst{uniq}",
            "lastName": "Reply",
            "email": f"inst+{uniq}@example.com",
            "companyName": "Acme",
            "campaign_name": "Q1-Outbound",
        }
        r = requests.post(f"{BASE}/api/integrations/instantly/webhook/{TENANT}", json=body, timeout=20)
        assert r.status_code == 200, r.text

    def test_google_ads_creates_lead(self):
        uniq = uuid.uuid4().hex[:8]
        body = {
            "user_column_data": [
                {"column_id": "FIRST_NAME", "string_value": f"Goog{uniq}"},
                {"column_id": "LAST_NAME", "string_value": "Lead"},
                {"column_id": "EMAIL", "string_value": f"goog+{uniq}@example.com"},
                {"column_id": "PHONE_NUMBER", "string_value": f"+91911111{uniq[:4]}"},
            ],
            "campaign_id": "camp_1",
        }
        r = requests.post(f"{BASE}/api/integrations/google-ads/webhook/{TENANT}", json=body, timeout=20)
        assert r.status_code == 200, r.text


# ─── Apollo bulk import ──────────────────────────────────────────────────────
class TestApolloImport:
    def test_apollo_import_authenticated(self, admin_headers):
        uniq = uuid.uuid4().hex[:6]
        body = {
            "tenant_id": TENANT,
            "leads": [
                {"first_name": f"Apo1{uniq}", "last_name": "X", "email": f"a1+{uniq}@x.com", "phone": "+919800000001", "company": "A"},
                {"first_name": f"Apo2{uniq}", "last_name": "Y", "email": f"a2+{uniq}@x.com", "phone": "+919800000002", "company": "B"},
            ],
        }
        r = requests.post(f"{BASE}/api/integrations/apollo/import", headers=admin_headers, json=body, timeout=30)
        assert r.status_code == 200, r.text
        out = r.json()
        for k in ("imported", "deduplicated", "failed", "total"):
            assert k in out
        assert out["total"] == 2


# ─── Events log ──────────────────────────────────────────────────────────────
class TestEvents:
    def test_events_endpoint(self, admin_headers):
        r = requests.get(f"{BASE}/api/integrations/events?limit=20", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "events" in data and isinstance(data["events"], list)


# ─── Disconnect ──────────────────────────────────────────────────────────────
class TestDisconnect:
    def test_disconnect_removes(self, admin_headers):
        # First connect make
        requests.post(
            f"{BASE}/api/integrations/make/connect",
            headers=admin_headers,
            json={"config": {"webhook_url": "https://example.com/mk"}},
            timeout=15,
        )
        r = requests.delete(f"{BASE}/api/integrations/make/disconnect", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        # Verify gone via list
        lst = requests.get(f"{BASE}/api/integrations/list", headers=admin_headers, timeout=15).json()["integrations"]
        make_entry = next((i for i in lst if i["type"] == "make"), None)
        assert make_entry["status"] == "not_connected"


# ─── Owner/admin gate — member should be 403 ─────────────────────────────────
class TestRoleGate:
    def test_member_cannot_connect(self):
        r = requests.post(f"{BASE}/api/auth/login", json={"email": "sarah@demo.com", "password": "Demo1234!"}, timeout=15)
        if r.status_code != 200:
            pytest.skip("sarah login unavailable")
        token = r.json().get("token") or r.json().get("access_token")
        h = {"Authorization": f"Bearer {token}", "X-Tenant-Id": TENANT, "Content-Type": "application/json"}
        r2 = requests.post(
            f"{BASE}/api/integrations/zapier/connect",
            headers=h,
            json={"config": {"webhook_url": "https://example.com"}},
            timeout=15,
        )
        assert r2.status_code == 403, f"member should be 403, got {r2.status_code}"


# ─── Conversations threads ───────────────────────────────────────────────────
class TestConversations:
    def test_threads_returns_priority_sorted(self, admin_headers):
        r = requests.get(f"{BASE}/api/conversations/threads?limit=100", headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "threads" in body and isinstance(body["threads"], list)
        # Validate priority sort (urgent → negative → others)
        prio = {"urgent": 0, "negative": 1}
        last = -1
        for t in body["threads"]:
            cur = prio.get((t.get("latest_sentiment") or "").lower(), 2)
            assert cur >= last, "priority order violated"
            last = cur


# ─── Legal pages (frontend served, but should be public, no auth) ────────────
class TestLegalPages:
    @pytest.mark.parametrize("path", ["/privacy", "/terms", "/dpa"])
    def test_legal_page_loads(self, path):
        r = requests.get(f"{BASE}{path}", timeout=15)
        assert r.status_code == 200
        # SPA — should serve the index.html
        assert "html" in r.headers.get("content-type", "").lower()


# ─── Lifecycle fan-out (best-effort) ─────────────────────────────────────────
class TestLifecycleFanOut:
    def test_fanout_logs_event_on_lead_create(self, admin_headers):
        # Ensure zapier connected to example.com (will produce 404 → still fires)
        requests.post(
            f"{BASE}/api/integrations/zapier/connect",
            headers=admin_headers,
            json={"config": {"webhook_url": "https://example.com/hook-test"}},
            timeout=15,
        )
        # Snapshot events count
        before = len(requests.get(f"{BASE}/api/integrations/events?limit=50", headers=admin_headers, timeout=15).json().get("events", []))
        # Trigger a lead capture via the public typeform path which calls fire_event
        uniq = uuid.uuid4().hex[:8]
        body = {"form_response": {"answers": [
            {"type": "email", "field": {"ref": "email"}, "email": f"fan+{uniq}@example.com"},
            {"type": "phone_number", "field": {"ref": "phone"}, "phone_number": f"+91922222{uniq[:4]}"},
            {"type": "short_text", "field": {"ref": "first_name"}, "short_text": f"Fan{uniq}"},
        ]}}
        r = requests.post(f"{BASE}/api/integrations/typeform/webhook/{TENANT}", json=body, timeout=20)
        assert r.status_code == 200
        time.sleep(3)  # allow async fan-out
        after = len(requests.get(f"{BASE}/api/integrations/events?limit=50", headers=admin_headers, timeout=15).json().get("events", []))
        # After should be at least before + 1 (inbound event) — outbound zapier event optional
        assert after > before, f"no new events recorded (before={before}, after={after})"
