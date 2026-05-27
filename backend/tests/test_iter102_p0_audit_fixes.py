"""Iter102 — Backend tests for the P0 audit fixes:
  1. Integration config encryption (write/read/migrate)
  2. Automation rule auto-fire from event bus
  3. 5-ICP per-tenant cap
"""
import os
import uuid
import pytest
import requests

from deps import db
from routes.integrations_hub import (
    _encrypt_config_secrets, _decrypt_config_secrets, get_decrypted_config,
)
from routes.automation_rules import evaluate_and_fire_rules

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD") or os.environ.get("DEMO_ADMIN_PASSWORD", "Demo1234!")

configs_col = db["integration_configs"]
rules_col = db["automation_rules"]
icps_col = db["icps"]


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


# ─── 1. Encryption-at-rest ─────────────────────────────────────────────────
class TestIntegrationEncryption:
    def test_encrypt_decrypt_roundtrip_in_memory(self):
        cfg = {"api_key": "pk_secret_value_xyz", "label": "not_a_secret", "webhook_secret": "wssecret"}
        enc = _encrypt_config_secrets(cfg)
        assert enc["api_key"].startswith("enc::")
        assert enc["webhook_secret"].startswith("enc::")
        assert enc["label"] == "not_a_secret"  # untouched
        dec = _decrypt_config_secrets(enc)
        assert dec["api_key"] == "pk_secret_value_xyz"
        assert dec["webhook_secret"] == "wssecret"

    def test_encrypt_is_idempotent(self):
        cfg = {"api_key": "abc123"}
        enc1 = _encrypt_config_secrets(cfg)
        # Re-encrypting an already-encrypted value should NOT double-encrypt
        # (encrypt() is internally aware via the "enc::" prefix).
        enc2 = _encrypt_config_secrets(enc1)
        # The output value should still decrypt back to original.
        assert _decrypt_config_secrets(enc2)["api_key"] == "abc123"

    def test_connect_stores_encrypted_value_in_db(self, admin_headers):
        # Use a supported integration type that won't disrupt others.
        kind = "saleshandy"
        # Snapshot existing config so we can restore.
        snapshot = configs_col.find_one({"tenant_id": "ten_pietential", "integration_type": kind}, {"_id": 0})
        secret = f"pk_{uuid.uuid4().hex}"
        try:
            r = requests.post(
                f"{BASE_URL}/api/integrations/{kind}/connect",
                headers={**admin_headers, "Content-Type": "application/json"},
                json={"config": {"api_key": secret}},
                timeout=20,
            )
            assert r.status_code == 200, r.text
            # UI receives masked
            ui_val = r.json()["integration"]["config"]["api_key"]
            assert "•" in ui_val
            # DB stores encrypted
            doc = configs_col.find_one({"tenant_id": "ten_pietential", "integration_type": kind}, {"_id": 0})
            assert doc["config"]["api_key"].startswith("enc::"), "key must be encrypted at rest"
            assert secret not in doc["config"]["api_key"], "raw secret must not be in DB"
            # Read helper decrypts
            cfg = get_decrypted_config("ten_pietential", kind)
            assert cfg["api_key"] == secret
        finally:
            # Restore prior config (or delete if there was none)
            configs_col.delete_one({"tenant_id": "ten_pietential", "integration_type": kind})
            if snapshot:
                configs_col.insert_one(snapshot)


# ─── 2. Automation rule auto-fire ──────────────────────────────────────────
class TestAutomationRuleAutoFire:
    def _mk_rule(self, headers, event_type, conditions=None):
        body = {
            "name": f"Iter102 autofire {uuid.uuid4().hex[:6]}",
            "trigger": {"event_type": event_type, "conditions": conditions or []},
            "actions": [{"type": "log_only", "params": {}}],
            "enabled": True,
        }
        r = requests.post(
            f"{BASE_URL}/api/automation-rules",
            headers={**headers, "Content-Type": "application/json"},
            json=body, timeout=15,
        )
        assert r.status_code == 200, r.text
        return r.json()["rule"]["id"]

    def test_pixel_form_submit_fires_lead_created_rule(self, admin_headers):
        rid = self._mk_rule(admin_headers, "lead.created")
        try:
            before = rules_col.find_one({"id": rid}, {"_id": 0, "fire_count": 1})["fire_count"]
            r = requests.post(
                f"{BASE_URL}/api/integrations/website-pixel/track/ten_pietential",
                json={
                    "event": "form_submit",
                    "email": f"iter102auto_{uuid.uuid4().hex[:8]}@test.example",
                    "first_name": "Iter102",
                },
                timeout=20,
            )
            assert r.status_code == 200
            assert r.json()["captured"] is True
            after = rules_col.find_one({"id": rid}, {"_id": 0, "fire_count": 1})["fire_count"]
            assert after == before + 1, f"rule should fire once on lead.created (was {before}, now {after})"
        finally:
            rules_col.delete_one({"id": rid})

    def test_rule_with_unmet_condition_does_not_fire(self):
        # Pure helper test — no HTTP.
        rule = {
            "id": str(uuid.uuid4()),
            "tenant_id": "ten_pietential",
            "enabled": True,
            "trigger": {
                "event_type": "lead.created",
                "conditions": [{"field": "lead.icp_score", "op": "gte", "value": 90}],
            },
            "actions": [{"type": "log_only", "params": {}}],
            "fire_count": 0,
        }
        rules_col.insert_one(rule.copy())
        try:
            summary = evaluate_and_fire_rules(
                "ten_pietential", "lead.created",
                {"lead": {"icp_score": 40}},  # 40 < 90 → should NOT fire
                triggered_by="unit_test",
            )
            assert summary["fired_count"] == 0
        finally:
            rules_col.delete_one({"id": rule["id"]})

    def test_disabled_rule_skipped(self):
        rule = {
            "id": str(uuid.uuid4()),
            "tenant_id": "ten_pietential",
            "enabled": False,
            "trigger": {"event_type": "lead.created", "conditions": []},
            "actions": [{"type": "log_only", "params": {}}],
            "fire_count": 0,
        }
        rules_col.insert_one(rule.copy())
        try:
            summary = evaluate_and_fire_rules("ten_pietential", "lead.created", {"lead": {}})
            assert summary["fired_count"] == 0
            assert summary["evaluated"] == 0  # disabled rules aren't even loaded
        finally:
            rules_col.delete_one({"id": rule["id"]})


# ─── 3. 5-ICP cap ───────────────────────────────────────────────────────────
class TestIcpCap:
    @pytest.fixture()
    def isolated_tenant(self, admin_headers):
        """Use a throwaway tenant id so we don't disturb Pietential."""
        from routes.tenants import memberships_col, tenants_col
        tid = f"ten_iter102_icpcap_{uuid.uuid4().hex[:6]}"
        tenants_col.insert_one({"id": tid, "name": "Iter102 ICP cap", "settings": {}})
        memberships_col.insert_one({"tenant_id": tid, "user_email": ADMIN_EMAIL, "role": "owner"})
        yield tid
        icps_col.delete_many({"tenant_id": tid})
        tenants_col.delete_one({"id": tid})
        memberships_col.delete_many({"tenant_id": tid})

    def test_can_create_up_to_5(self, admin_headers, isolated_tenant):
        h = {**admin_headers, "X-Tenant-Id": isolated_tenant}
        for i in range(5):
            r = requests.post(
                f"{BASE_URL}/api/icps/create",
                headers={**h, "Content-Type": "application/json"},
                json={"label": f"ICP {i+1}", "tone": "professional"},
                timeout=15,
            )
            assert r.status_code == 201, f"ICP #{i+1} failed: {r.text}"

    def test_6th_blocked_with_403(self, admin_headers, isolated_tenant):
        h = {**admin_headers, "X-Tenant-Id": isolated_tenant}
        # Seed 5 ICPs directly
        for i in range(5):
            icps_col.insert_one({
                "id": f"icp_seed_{i}_{uuid.uuid4().hex[:8]}",
                "tenant_id": isolated_tenant,
                "label": f"Seed {i}",
                "tone": "professional",
            })
        r = requests.post(
            f"{BASE_URL}/api/icps/create",
            headers={**h, "Content-Type": "application/json"},
            json={"label": "6th try", "tone": "professional"},
            timeout=15,
        )
        assert r.status_code == 403
        assert "limit_reached" in r.json()["detail"]
        assert "max 5" in r.json()["detail"]
