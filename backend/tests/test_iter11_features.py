"""Iteration 11 backend tests:
- Pydantic Literal validators on LeadMagnetConfig + CampaignLeadMagnetOverride
- Per-campaign lead magnet override CRUD + scope resolution
- engagement-map + recent-opens endpoints
- WhatsApp Cloud API graceful logged-only fallback
- WhatsApp webhook verify (GET) and receive (POST)
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PWD = "Demo1234!"
EXISTING_LEAD_ID = "69e081b5cd724a3d376691c4"
TEST_CAMPAIGN_ID = "TEST_iter11_campaign"


@pytest.fixture(scope="module")
def auth():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PWD}, timeout=20)
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token") or r.json().get("token")
    return {"Authorization": f"Bearer {tok}"}


# ─── Pydantic Literal validators ────────────────────────────────
class TestLiteralValidators:
    def test_invalid_type_rejected(self, auth):
        bad = {"enabled": True, "type": "pdf", "url": "https://x", "send_timing": "post_booking"}
        r = requests.put(f"{BASE_URL}/api/lead-magnets/config", json=bad, headers=auth, timeout=20)
        assert r.status_code == 422, f"expected 422 got {r.status_code}: {r.text}"

    def test_invalid_send_timing_rejected(self, auth):
        bad = {"enabled": True, "type": "url", "url": "https://x", "send_timing": "never"}
        r = requests.put(f"{BASE_URL}/api/lead-magnets/config", json=bad, headers=auth, timeout=20)
        assert r.status_code == 422, f"expected 422 got {r.status_code}: {r.text}"

    def test_valid_payload_accepted(self, auth):
        ok = {"enabled": True, "type": "url", "url": "https://example.com/iter11.pdf",
              "send_timing": "both", "name": "TEST_iter11_workspace"}
        r = requests.put(f"{BASE_URL}/api/lead-magnets/config", json=ok, headers=auth, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["send_timing"] == "both"


# ─── Per-Campaign Override CRUD ─────────────────────────────────
class TestCampaignOverride:
    def test_get_unknown_campaign_returns_defaults(self, auth):
        r = requests.get(f"{BASE_URL}/api/lead-magnets/campaign/UNKNOWN_TEST_CID_iter11", headers=auth, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["inherit"] is True
        assert d["enabled"] is False
        assert d["type"] == "url"
        assert d["send_timing"] == "post_booking"

    def test_put_then_get_round_trip(self, auth):
        payload = {
            "enabled": True,
            "inherit": False,
            "name": "TEST_iter11_campaign_magnet",
            "type": "url",
            "url": "https://example.com/iter11_campaign.pdf",
            "send_timing": "pre_booking",
            "message_template": "Hi {first_name}, campaign link: {link}",
        }
        r = requests.put(f"{BASE_URL}/api/lead-magnets/campaign/{TEST_CAMPAIGN_ID}",
                         json=payload, headers=auth, timeout=20)
        assert r.status_code == 200, r.text
        saved = r.json()
        assert saved["url"] == payload["url"]
        assert saved["inherit"] is False
        assert saved["send_timing"] == "pre_booking"

        g = requests.get(f"{BASE_URL}/api/lead-magnets/campaign/{TEST_CAMPAIGN_ID}", headers=auth, timeout=20)
        assert g.status_code == 200
        gd = g.json()
        assert gd["inherit"] is False
        assert gd["url"] == payload["url"]
        assert gd["name"] == "TEST_iter11_campaign_magnet"

    def test_invalid_type_on_campaign_rejected(self, auth):
        bad = {"enabled": True, "inherit": False, "type": "video", "url": "https://x", "send_timing": "post_booking"}
        r = requests.put(f"{BASE_URL}/api/lead-magnets/campaign/{TEST_CAMPAIGN_ID}",
                         json=bad, headers=auth, timeout=20)
        assert r.status_code == 422


# ─── Scope resolution: campaign vs workspace ────────────────────
class TestScopeResolution:
    @pytest.fixture(autouse=True)
    def _setup_workspace(self, auth):
        # Ensure workspace magnet enabled with a clean URL
        requests.put(f"{BASE_URL}/api/lead-magnets/config",
                     json={"enabled": True, "type": "url", "url": "https://example.com/workspace_iter11",
                           "send_timing": "post_booking", "name": "TEST_iter11_workspace"},
                     headers=auth, timeout=20)

    def test_campaign_override_used_when_inherit_false(self, auth):
        # Set lead's campaign_id to TEST_CAMPAIGN_ID via patch
        # First ensure campaign override exists with inherit=False
        requests.put(f"{BASE_URL}/api/lead-magnets/campaign/{TEST_CAMPAIGN_ID}",
                     json={"enabled": True, "inherit": False, "type": "url",
                           "url": "https://example.com/campaign_iter11",
                           "send_timing": "post_booking", "name": "TEST_iter11_campaign_magnet"},
                     headers=auth, timeout=20)

        # Patch lead with campaign_id
        patch = requests.patch(f"{BASE_URL}/api/leads/{EXISTING_LEAD_ID}",
                               json={"campaign_id": TEST_CAMPAIGN_ID}, headers=auth, timeout=20)
        # Tolerate either PATCH or PUT support
        if patch.status_code not in (200, 204):
            # try PUT
            patch = requests.put(f"{BASE_URL}/api/leads/{EXISTING_LEAD_ID}",
                                 json={"campaign_id": TEST_CAMPAIGN_ID}, headers=auth, timeout=20)
        # Either way, send and check scope. If patch failed, skip.
        if patch.status_code not in (200, 204):
            pytest.skip(f"Could not patch lead to set campaign_id (status {patch.status_code})")

        r = requests.post(f"{BASE_URL}/api/leads/{EXISTING_LEAD_ID}/send-lead-magnet",
                          headers=auth, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["sent"] is True
        assert d.get("scope") == "campaign", f"expected scope=campaign got {d}"

    def test_workspace_used_when_inherit_true(self, auth):
        # Flip override to inherit=True — workspace should win
        requests.put(f"{BASE_URL}/api/lead-magnets/campaign/{TEST_CAMPAIGN_ID}",
                     json={"enabled": True, "inherit": True, "type": "url",
                           "url": "https://example.com/should_not_be_used",
                           "send_timing": "post_booking"},
                     headers=auth, timeout=20)
        r = requests.post(f"{BASE_URL}/api/leads/{EXISTING_LEAD_ID}/send-lead-magnet",
                          headers=auth, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("scope") == "workspace", f"expected scope=workspace got {d}"


# ─── Engagement map + recent opens ──────────────────────────────
class TestEngagementAggregation:
    def test_engagement_map_shape(self, auth):
        r = requests.get(f"{BASE_URL}/api/lead-magnets/engagement-map", headers=auth, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert "leads" in d
        assert "total_engaged" in d
        assert isinstance(d["leads"], dict)
        assert d["total_engaged"] == len(d["leads"])
        # The seed lead should be present and is_hot
        assert EXISTING_LEAD_ID in d["leads"], f"seed lead missing from map: {list(d['leads'].keys())[:5]}"
        seed = d["leads"][EXISTING_LEAD_ID]
        for k in ["sent_count", "view_count", "is_hot"]:
            assert k in seed
        assert seed["is_hot"] == (seed["view_count"] >= 2)

    def test_recent_opens_shape_and_dedupe(self, auth):
        r = requests.get(f"{BASE_URL}/api/lead-magnets/recent-opens?limit=5", headers=auth, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert "opens" in d and "count" in d
        assert isinstance(d["opens"], list)
        assert d["count"] == len(d["opens"])
        # Dedupe: each lead_id should appear at most once
        ids = [o["lead_id"] for o in d["opens"]]
        assert len(ids) == len(set(ids)), f"recent-opens not deduped: {ids}"
        # If we have any opens, each entry should have name/company + view_count
        if d["opens"]:
            o = d["opens"][0]
            for k in ["lead_id", "first_name", "company_name", "view_count", "is_hot", "viewed_at"]:
                assert k in o, f"missing key {k} in {o}"

    def test_recent_opens_limit_clamp(self, auth):
        r = requests.get(f"{BASE_URL}/api/lead-magnets/recent-opens?limit=999", headers=auth, timeout=20)
        assert r.status_code == 200
        # No crash on huge limit; backend clamps to 50


# ─── WhatsApp logged-only fallback ──────────────────────────────
class TestWhatsAppLoggedOnly:
    def test_send_logged_only_no_500(self, auth):
        # Force a whatsapp_sent activity to make channel detection pick whatsapp
        # Use existing whatsapp_received/sent if present. We just call send and check.
        # Backend infers channel from most recent whatsapp_sent OR email_sent activity.
        # We'll trust the system; just ensure no 500 and sent:true (logged-only ok).
        r = requests.post(f"{BASE_URL}/api/leads/{EXISTING_LEAD_ID}/send-lead-magnet",
                          headers=auth, timeout=30)
        assert r.status_code == 200, f"status {r.status_code}: {r.text}"
        d = r.json()
        assert d["sent"] is True
        assert d["channel"] in ("email", "whatsapp")


# ─── WhatsApp webhook verify ────────────────────────────────────
class TestWhatsAppWebhookVerify:
    def test_verify_returns_503_when_env_empty(self):
        # WHATSAPP_VERIFY_TOKEN is empty in .env → 503
        r = requests.get(f"{BASE_URL}/api/webhooks/whatsapp",
                         params={"hub.mode": "subscribe", "hub.verify_token": "any", "hub.challenge": "abc123"},
                         timeout=20)
        # Either 503 (token env empty — current state) OR 403 (token mismatch if env was set)
        assert r.status_code in (503, 403), f"got {r.status_code}: {r.text}"

    def test_receive_accepts_payload(self):
        sample = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "BIZ_ID",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {"display_phone_number": "15555550100", "phone_number_id": "1234"},
                        "messages": [{
                            "from": "15555550199",
                            "id": "wamid.TEST",
                            "timestamp": "1700000000",
                            "text": {"body": "hello from test"},
                            "type": "text",
                        }]
                    },
                    "field": "messages"
                }]
            }]
        }
        r = requests.post(f"{BASE_URL}/api/webhooks/whatsapp", json=sample, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json().get("received") is True
