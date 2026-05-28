"""iter121 — Batch 9 final integration tests.

Covers:
  • PRECHECK V10
  • CONVERSATIONS_THREAD (GET /api/conversations/lead/{lead_id})
  • CONVERSATIONS_TENANT_ISOLATION (cross-tenant must be empty)
  • AUTO_APPROVE — decision rule, gates, disabled, intent filter, daily cap
  • NOTIFICATIONS_AGGREGATOR — GET + partial POST
  • TOKEN_USAGE — claude_call writes positive ints to api_usage_log
"""

import os
import sys
import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests

# Allow importing backend modules in-process for direct-trigger tests
sys.path.insert(0, str(Path("/app/backend").resolve()))

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")

ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = "Demo1234!"
TENANT_ID = "ten_pietential"
OTHER_TENANT_ID = "ten_demo"
LEAD_ID = "ptl_replytest01"


# ─── Fixtures ───────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def auth_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD,
    }, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    token = r.json().get("token") or r.json().get("access_token")
    assert token, f"no token in login response: {r.json()}"
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": TENANT_ID}


@pytest.fixture(scope="session")
def cross_tenant_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD,
    }, timeout=15)
    assert r.status_code == 200
    token = r.json().get("token") or r.json().get("access_token")
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": OTHER_TENANT_ID}


# ─── 1. CONVERSATIONS_THREAD ────────────────────────────────────────────
class TestConversationThread:
    def test_thread_for_lead_returns_structured_payload(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/conversations/lead/{LEAD_ID}",
                         headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "thread" in data and isinstance(data["thread"], list)
        assert "lead_snapshot" in data
        assert "counts" in data
        counts = data["counts"]
        assert set(counts.keys()) >= {"outbound", "inbound", "activity", "total"}
        # No BSON _id leak
        for entry in data["thread"]:
            assert "_id" not in entry
            assert {"id", "ts", "direction", "channel", "actor", "title", "body", "meta"}.issubset(entry.keys())
        # ASC sort by ts
        ts_list = [e["ts"] for e in data["thread"]]
        assert ts_list == sorted(ts_list), "thread is not sorted ASC by ts"

    def test_thread_other_tenant_empty(self, cross_tenant_headers):
        r = requests.get(f"{BASE_URL}/api/conversations/lead/{LEAD_ID}",
                         headers=cross_tenant_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["counts"]["total"] == 0
        assert data["thread"] == []


# ─── 2. NOTIFICATIONS AGGREGATOR ────────────────────────────────────────
class TestNotificationsAggregator:
    def test_get_returns_three_sections(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/aria/settings/notifications",
                         headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert set(data.keys()) >= {"morning_brief", "approval_digest", "auto_approve"}
        aa = data["auto_approve"]
        assert {"enabled", "min_fit_score", "allowed_intents", "allowed_channels", "max_per_day"}.issubset(aa.keys())

    def test_partial_post_only_persists_morning_brief(self, auth_headers):
        # Snapshot existing approval_digest + auto_approve
        before = requests.get(f"{BASE_URL}/api/aria/settings/notifications",
                              headers=auth_headers, timeout=15).json()
        body = {"morning_brief": {
            "enabled": True, "send_to_email": "x@y.com",
            "send_hour_local": 9, "timezone_offset_hours": 5.5,
            "weekdays_only": True, "max_new_intel": 15,
        }}
        r = requests.post(f"{BASE_URL}/api/aria/settings/notifications",
                          json=body, headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        after = requests.get(f"{BASE_URL}/api/aria/settings/notifications",
                             headers=auth_headers, timeout=15).json()
        assert after["morning_brief"]["enabled"] is True
        assert after["morning_brief"]["send_to_email"] == "x@y.com"
        assert after["morning_brief"]["max_new_intel"] == 15
        # untouched
        assert after["approval_digest"] == before["approval_digest"]
        assert after["auto_approve"] == before["auto_approve"]


# ─── 3. AUTO-APPROVE DECISION ────────────────────────────────────────────
# These use the pure decision function — no live dispatch in sandbox.
class TestAutoApproveDecision:
    @pytest.fixture(autouse=True)
    def _reset_usage(self):
        from deps import db
        db["aria_auto_approve_usage"].delete_many({"tenant_id": TENANT_ID})
        yield
        db["aria_auto_approve_usage"].delete_many({"tenant_id": TENANT_ID})

    def _set_aa(self, headers, **overrides):
        cfg = {
            "enabled": True, "min_fit_score": 85,
            "allowed_intents": ["positive", "interested"],
            "allowed_channels": ["email", "whatsapp"], "max_per_day": 20,
        }
        cfg.update(overrides)
        r = requests.post(f"{BASE_URL}/api/aria/settings/notifications",
                          json={"auto_approve": cfg}, headers=headers, timeout=15)
        assert r.status_code == 200, r.text
        return cfg

    def test_eligible_ok_path(self, auth_headers):
        self._set_aa(auth_headers, enabled=True, min_fit_score=85)
        from routes.aria_settings import auto_approve_eligible
        d = auto_approve_eligible(tenant_id=TENANT_ID, channel="whatsapp",
                                  fit_score=85, intent="positive")
        assert d == {"eligible": True, "reason": "ok"}

    def test_gate_fit_below_threshold(self, auth_headers):
        self._set_aa(auth_headers, min_fit_score=99)
        from routes.aria_settings import auto_approve_eligible
        d = auto_approve_eligible(tenant_id=TENANT_ID, channel="whatsapp",
                                  fit_score=85, intent="positive")
        assert d["eligible"] is False
        assert d["reason"].startswith("fit_score_below_threshold")
        # reset for downstream
        self._set_aa(auth_headers, min_fit_score=85)

    def test_disabled(self, auth_headers):
        self._set_aa(auth_headers, enabled=False)
        from routes.aria_settings import auto_approve_eligible
        d = auto_approve_eligible(tenant_id=TENANT_ID, channel="whatsapp",
                                  fit_score=85, intent="positive")
        assert d == {"eligible": False, "reason": "rule_disabled"}

    def test_intent_filter(self, auth_headers):
        self._set_aa(auth_headers, enabled=True, allowed_intents=["interested"])
        from routes.aria_settings import auto_approve_eligible
        d = auto_approve_eligible(tenant_id=TENANT_ID, channel="whatsapp",
                                  fit_score=85, intent="positive")
        assert d["eligible"] is False
        assert d["reason"] == "intent_positive_not_allowed"

    def test_daily_cap(self, auth_headers):
        from routes.aria_settings import (
            auto_approve_eligible, record_auto_approve_used,
        )
        self._set_aa(auth_headers, enabled=True, max_per_day=1,
                     allowed_intents=["positive", "interested"])
        d1 = auto_approve_eligible(tenant_id=TENANT_ID, channel="whatsapp",
                                   fit_score=85, intent="positive")
        assert d1["eligible"] is True
        record_auto_approve_used(TENANT_ID)
        d2 = auto_approve_eligible(tenant_id=TENANT_ID, channel="whatsapp",
                                   fit_score=85, intent="positive")
        assert d2["eligible"] is False
        assert d2["reason"] == "daily_cap_reached"
        from deps import db
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        used = db["aria_auto_approve_usage"].find_one({"tenant_id": TENANT_ID, "day": today})
        assert used and used["count"] == 1


# ─── 4. AUTO-APPROVE — full _process_inbound integration ─────────────────
class TestProcessInboundAutoApprove:
    @pytest.fixture(autouse=True)
    def _reset(self, auth_headers):
        from deps import db
        db["aria_auto_approve_usage"].delete_many({"tenant_id": TENANT_ID})
        db["pending_outreach"].delete_many({"tenant_id": TENANT_ID, "lead_id": LEAD_ID})
        # Set rule baseline
        requests.post(f"{BASE_URL}/api/aria/settings/notifications", json={
            "auto_approve": {
                "enabled": True, "min_fit_score": 85,
                "allowed_intents": ["positive", "interested", "neutral", "question", "unknown"],
                "allowed_channels": ["email", "whatsapp"], "max_per_day": 20,
            },
        }, headers=auth_headers, timeout=15)
        yield

    def _run(self, channel="whatsapp", reply_text="Yes I'm interested please send pricing", external_id_suffix="t1"):
        from deps import db
        from routes.inbound_reply import _process_inbound
        lead = db.pt_leads.find_one({"id": LEAD_ID, "tenant_id": TENANT_ID})
        assert lead, "test lead missing"
        return asyncio.get_event_loop().run_until_complete(
            _process_inbound(
                tenant_id=TENANT_ID, lead=lead, channel=channel,
                reply_text=reply_text,
                external_id=f"test-iter121-{external_id_suffix}-{datetime.now(timezone.utc).timestamp()}",
                raw={"test": True}, sender_label="+919999999999",
            )
        )

    def test_auto_dispatched_when_eligible(self, auth_headers):
        result = self._run(external_id_suffix="eligible")
        assert result["ok"] is True
        # Intent must be in allowed list for the rule to fire
        intent = result["qualification"]["intent"]
        assert result["auto_approve_reason"] is not None, result
        if intent in ("positive", "interested", "neutral", "question", "unknown"):
            # Expected happy-path
            assert result["auto_dispatched"] is True, f"expected auto-dispatch, got {result}"
            assert result["drafted"] is False
            assert result["auto_approve_reason"] == "ok"
            from deps import db
            doc = db.pending_outreach.find_one(
                {"tenant_id": TENANT_ID, "lead_id": LEAD_ID, "auto_approved": True},
                sort=[("created_at", -1)],
            )
            assert doc is not None
            assert doc["status"].startswith("auto_approved_")
        else:
            pytest.skip(f"Claude classified intent as {intent}, outside allowed set for this test")

    def test_not_dispatched_when_fit_below(self, auth_headers):
        # Raise threshold
        requests.post(f"{BASE_URL}/api/aria/settings/notifications", json={
            "auto_approve": {
                "enabled": True, "min_fit_score": 99,
                "allowed_intents": ["positive", "interested", "neutral", "question", "unknown"],
                "allowed_channels": ["email", "whatsapp"], "max_per_day": 20,
            },
        }, headers=auth_headers, timeout=15)
        result = self._run(external_id_suffix="fit_blocked")
        if result["qualification"]["intent"] in ("unsubscribe", "not_interested"):
            pytest.skip("Claude marked as unsubscribe/not_interested — no draft branch hit")
        assert result["auto_dispatched"] is False, result
        assert result["auto_approve_reason"].startswith("fit_score_below_threshold")
        from deps import db
        doc = db.pending_outreach.find_one(
            {"tenant_id": TENANT_ID, "lead_id": LEAD_ID, "status": "awaiting_owner_approval"},
            sort=[("created_at", -1)],
        )
        assert doc is not None
        assert doc.get("auto_approve_skipped_reason", "").startswith("fit_score_below_threshold")

    def test_not_dispatched_when_rule_disabled(self, auth_headers):
        requests.post(f"{BASE_URL}/api/aria/settings/notifications", json={
            "auto_approve": {
                "enabled": False, "min_fit_score": 85,
                "allowed_intents": ["positive", "interested", "neutral", "question", "unknown"],
                "allowed_channels": ["email", "whatsapp"], "max_per_day": 20,
            },
        }, headers=auth_headers, timeout=15)
        result = self._run(external_id_suffix="disabled")
        if result["qualification"]["intent"] in ("unsubscribe", "not_interested"):
            pytest.skip("Claude marked as unsubscribe/not_interested — no draft branch hit")
        assert result["auto_dispatched"] is False
        assert result["auto_approve_reason"] == "rule_disabled"


# ─── 5. TOKEN_USAGE ──────────────────────────────────────────────────────
class TestTokenUsage:
    def test_claude_call_logs_positive_ints(self, auth_headers):
        from deps import db
        before_count = db.api_usage_log.count_documents({"tenant_id": TENANT_ID})
        # Trigger a real claude call via /api/ai/chat
        r = requests.post(f"{BASE_URL}/api/ai/chat", json={
            "query": "Say 'hello' in one word.",
        }, headers=auth_headers, timeout=60)
        if r.status_code == 404:
            pytest.skip("/api/ai/chat not present in this deployment")
        assert r.status_code in (200, 201), f"chat failed: {r.status_code} {r.text[:300]}"
        # Allow async logger to flush
        import time as _t; _t.sleep(1.5)
        after = db.api_usage_log.count_documents({"tenant_id": TENANT_ID})
        assert after > before_count, "no api_usage_log row written"
        doc = db.api_usage_log.find_one({"tenant_id": TENANT_ID}, sort=[("ts", -1)])
        assert doc, "no usage doc"
        assert isinstance(doc.get("prompt_tokens"), int) and doc["prompt_tokens"] > 0
        assert isinstance(doc.get("completion_tokens"), int) and doc["completion_tokens"] > 0
