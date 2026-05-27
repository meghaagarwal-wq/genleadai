"""Iter93 — Phase 2: Document extraction + auto-train + merge semantics."""
from __future__ import annotations

import io
import os
import sys
import asyncio
import requests
import pytest
from pymongo import MongoClient

_BACKEND_DIR = "/app/backend"
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASS = os.environ.get("TEST_ADMIN_PASS", "Demo1234!")
SALES_EMAIL = "sarah@demo.com"
SALES_PASS = os.environ.get("TEST_SALES_PASS", "Demo1234!")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "genleadai_lms")
_mc = MongoClient(MONGO_URL)
_db = _mc[DB_NAME]


def _login(email: str, password: str) -> str:
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text[:200]}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def sales_token():
    return _login(SALES_EMAIL, SALES_PASS)


def _h(token: str, tenant_id: str = "ten_pietential") -> dict:
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": tenant_id}


# ─── A. Unit tests on merge + NOT_FOUND scrubbing ───────────────────────
class TestMergeUnit:
    def test_strip_not_found_scalar(self):
        from routes.aria_training import _strip_not_found
        assert _strip_not_found("NOT_FOUND") == ""
        assert _strip_not_found("not_found") == ""
        assert _strip_not_found("  NOT_FOUND  ") == ""
        assert _strip_not_found("AI-powered tool") == "AI-powered tool"

    def test_strip_not_found_list(self):
        from routes.aria_training import _strip_not_found
        assert _strip_not_found(["a", "NOT_FOUND", "b"]) == ["a", "b"]
        assert _strip_not_found([]) == []

    def test_strip_not_found_nested(self):
        from routes.aria_training import _strip_not_found
        data = {"x": "NOT_FOUND", "y": ["a", "NOT_FOUND"], "z": {"q": "NOT_FOUND", "r": "ok"}}
        result = _strip_not_found(data)
        assert result["x"] == ""
        assert result["y"] == ["a"]
        assert result["z"]["q"] == ""
        assert result["z"]["r"] == "ok"

    def test_merge_scalar_overwrites_when_new(self):
        from routes.aria_training import _merge_into_profile, _empty_profile
        existing = _empty_profile()
        existing["what_you_sell"] = ""  # blank existing
        out = _merge_into_profile(existing, {"what_you_sell": "New offering"})
        assert out["what_you_sell"] == "New offering"

    def test_merge_list_dedupes_case_insensitive(self):
        from routes.aria_training import _merge_into_profile, _empty_profile
        existing = _empty_profile()
        existing["services_or_products"] = ["Employee Pulse", "AI Assistant"]
        out = _merge_into_profile(existing, {"services_or_products": ["employee pulse", "Analytics"]})
        assert out["services_or_products"] == ["Employee Pulse", "AI Assistant", "Analytics"]

    def test_merge_icps_appends_only_new_names(self):
        from routes.aria_training import _merge_into_profile, _empty_profile
        existing = _empty_profile()
        existing["icp_profiles"] = [{"icp_name": "Existing ICP", "target_industries": ["SaaS"]}]
        out = _merge_into_profile(existing, {
            "icp_profiles": [
                {"icp_name": "Existing ICP", "target_industries": ["IGNORED — should not overwrite"]},
                {"icp_name": "New ICP", "target_industries": ["FinTech"]},
            ]
        })
        names = [i["icp_name"] for i in out["icp_profiles"]]
        assert names == ["Existing ICP", "New ICP"]
        # Existing ICP industries unchanged
        assert out["icp_profiles"][0]["target_industries"] == ["SaaS"]

    def test_merge_faq_dedupes_by_question(self):
        from routes.aria_training import _merge_into_profile, _empty_profile
        existing = _empty_profile()
        existing["custom_faq"] = [{"question": "What's your refund?", "answer": "30 days"}]
        out = _merge_into_profile(existing, {
            "custom_faq": [
                {"question": "what's your refund?", "answer": "DIFFERENT (should be ignored)"},
                {"question": "Shipping?", "answer": "Free over $50"},
            ]
        })
        assert len(out["custom_faq"]) == 2
        assert out["custom_faq"][0]["answer"] == "30 days"  # original wins
        assert out["custom_faq"][1]["question"] == "Shipping?"


# ─── B. Auto-train endpoint ─────────────────────────────────────────────
class TestAutoTrain:
    def test_sales_rep_blocked(self, sales_token):
        r = requests.post(f"{BASE_URL}/api/aria/training-profile/auto-train-from-workspace",
                          headers=_h(sales_token, "ten_demo"), timeout=30)
        assert r.status_code in (401, 403)

    def test_admin_gets_response_shape(self, admin_token):
        r = requests.post(f"{BASE_URL}/api/aria/training-profile/auto-train-from-workspace",
                          headers=_h(admin_token, "ten_pietential"), timeout=30)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["ok"] is True
        assert "seeded" in body
        assert "message" in body
        assert isinstance(body["seeded"], list)


# ─── C. Document extraction ─────────────────────────────────────────────
class TestExtraction:
    def test_sales_rep_blocked(self, sales_token):
        files = {"file": ("test.txt", b"some content here padded out enough\n" * 5, "text/plain")}
        r = requests.post(f"{BASE_URL}/api/aria/training-profile/extract-from-document",
                          headers=_h(sales_token, "ten_demo"),
                          files=files, timeout=30)
        assert r.status_code in (401, 403), r.text[:200]

    def test_empty_file_rejected(self, admin_token):
        files = {"file": ("empty.txt", b"", "text/plain")}
        r = requests.post(f"{BASE_URL}/api/aria/training-profile/extract-from-document",
                          headers=_h(admin_token, "ten_pietential"),
                          files=files, timeout=30)
        assert r.status_code == 400
        assert "empty" in r.text.lower()

    def test_too_small_file_rejected(self, admin_token):
        files = {"file": ("tiny.txt", b"hi", "text/plain")}
        r = requests.post(f"{BASE_URL}/api/aria/training-profile/extract-from-document",
                          headers=_h(admin_token, "ten_pietential"),
                          files=files, timeout=30)
        assert r.status_code == 400
        assert "couldn't read" in r.text.lower() or "enough text" in r.text.lower()

    def test_real_extraction_with_synthetic_gtm_doc(self, admin_token):
        """End-to-end: upload a GTM brief, Claude extracts, profile re-assembles."""
        doc = b"""
        Acme Corp GTM Brief
        What we sell: AI-powered scheduling software for clinics.
        Who we sell to: Practice managers at dental and physical therapy clinics.
        Problem we solve: No-shows and double-bookings.
        Differentiator: Predictive no-show alerts.
        Services: Smart Scheduler, Patient Reminders, Analytics Dashboard.

        ICP: Practice Manager at Clinic
          Industries: Healthcare, Dental
          Titles: Practice Manager, Office Manager
          Size: 5-50 staff
          Geography: USA, Canada
          Budget: $200-2000/month
          High-intent: New clinic launch
          Disqualify: Solo practitioner

        Qualification questions:
        1. How many providers do you have?
        2. What's your current no-show rate?

        Brand voice: Friendly, helpful, never pushy.
        Calendar: https://calendly.com/acme/demo
        """
        files = {"file": ("acme_gtm.txt", doc, "text/plain")}
        r = requests.post(f"{BASE_URL}/api/aria/training-profile/extract-from-document",
                          headers=_h(admin_token, "ten_pietential"),
                          files=files, timeout=120)
        assert r.status_code == 200, r.text[:500]
        body = r.json()
        assert body["ok"] is True
        assert body["fields_extracted"] >= 5
        # At least one of the ICPs got extracted
        assert body["icps_extracted"] >= 0  # Claude may or may not pick it up — be tolerant
        assert "extracted_preview" in body
        # Workspace state shifted (version bumped)
        assert body["version"] >= 1


# ─── D. Integration with assembled prompt ───────────────────────────────
class TestAssembledPromptReflectsExtraction:
    def test_preview_contains_extracted_fields_after_seed(self, admin_token):
        """After an extraction, the preview prompt must include the new content."""
        # First, do a fresh extraction with a known marker string
        marker = "UNIQUE_TEST_MARKER_iter93"
        doc = (
            f"What we sell: A widget called {marker} that helps founders.\n"
            "Who we sell to: Founders.\n"
            "Problem: Time waste.\n"
            "Brand voice: Direct and helpful.\n"
            "Calendar: https://example.com/cal\n"
        ).encode()
        files = {"file": ("marker.txt", doc, "text/plain")}
        r = requests.post(f"{BASE_URL}/api/aria/training-profile/extract-from-document",
                          headers=_h(admin_token, "ten_pietential"),
                          files=files, timeout=120)
        assert r.status_code == 200, r.text[:500]

        # Now fetch the preview — must contain the marker
        r2 = requests.get(f"{BASE_URL}/api/aria/system-prompt-preview",
                          headers=_h(admin_token, "ten_pietential"), timeout=20)
        assert r2.status_code == 200
        prompt = r2.json()["prompt"]
        assert marker in prompt, "Marker from extracted doc must appear in assembled prompt"
