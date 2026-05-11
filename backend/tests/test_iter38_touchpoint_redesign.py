"""Iter 38 — Touchpoint Mapping redesign: /scoring + /ai-quality endpoints."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = "Demo1234!"
TENANT_ID = "ten_demo"


@pytest.fixture(scope="module")
def auth_headers():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    token = r.json().get("token") or r.json().get("access_token")
    assert token, f"no token in login response: {r.json()}"
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": TENANT_ID, "Content-Type": "application/json"}


# ─── /scoring ──────────────────────────────────────────────────────────
class TestScoringEndpoint:
    def test_scoring_returns_200_and_structure(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/touchpoints/scoring", headers=auth_headers, timeout=20)
        assert r.status_code == 200, f"unexpected {r.status_code}: {r.text}"
        data = r.json()
        assert "items" in data and isinstance(data["items"], list)
        assert "journey" in data and isinstance(data["journey"], dict)

    def test_scoring_journey_fields(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/touchpoints/scoring", headers=auth_headers, timeout=20)
        j = r.json()["journey"]
        for k in ("score", "grade", "touchpoint_count", "total_sent", "total_replies",
                  "total_scheduled", "reply_rate", "skip_rate", "delivery_rate"):
            assert k in j, f"missing journey.{k}"
        # types/ranges
        assert isinstance(j["score"], (int, float))
        assert isinstance(j["touchpoint_count"], int)
        assert j["touchpoint_count"] >= 0
        assert j["grade"] in ("A", "B", "C", "D", "—")

    def test_scoring_items_have_performance_and_lead_fit(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/touchpoints/scoring", headers=auth_headers, timeout=20)
        items = r.json()["items"]
        # demo tenant has at least 1 touchpoint
        assert len(items) >= 1, "expected at least 1 touchpoint for ten_demo"
        for it in items:
            assert "index" in it
            assert isinstance(it.get("performance"), dict)
            perf = it["performance"]
            for k in ("total_scheduled", "sent", "skipped", "failed", "pending",
                      "replies", "reply_rate", "delivery_rate", "skip_rate",
                      "effectiveness", "grade"):
                assert k in perf, f"missing performance.{k} on idx {it['index']}"
            assert isinstance(it.get("lead_fit"), dict)
            for k in ("hot", "warm", "cold", "total"):
                assert k in it["lead_fit"]

    def test_scoring_no_objectid_leakage(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/touchpoints/scoring", headers=auth_headers, timeout=20)
        assert "_id" not in r.text or "ObjectId" not in r.text


# ─── /ai-quality ──────────────────────────────────────────────────────
class TestAIQualityEndpoint:
    def test_ai_quality_returns_200(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/touchpoints/ai-quality", headers=auth_headers, timeout=90)
        assert r.status_code == 200, f"unexpected {r.status_code}: {r.text[:300]}"
        data = r.json()
        assert "items" in data and isinstance(data["items"], list)

    def test_ai_quality_item_shape(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/touchpoints/ai-quality", headers=auth_headers, timeout=90)
        items = r.json().get("items", [])
        if not items:
            pytest.skip("no touchpoints in active map; skip shape check")
        for it in items:
            assert "index" in it
            for k in ("clarity", "personalisation", "cta", "tone_fit", "average", "verdict"):
                assert k in it, f"missing {k} on item {it.get('index')}"
            for k in ("clarity", "personalisation", "cta", "tone_fit", "average"):
                assert isinstance(it[k], (int, float)), f"{k} not numeric: {it[k]}"
                assert 0 <= float(it[k]) <= 10, f"{k}={it[k]} out of range"
            assert "ai_powered" in it

    def test_ai_quality_cache_second_call_fast(self, auth_headers):
        import time
        # First call (might be slow if cache cold)
        t0 = time.time()
        r1 = requests.post(f"{BASE_URL}/api/touchpoints/ai-quality", headers=auth_headers, timeout=90)
        t1 = time.time() - t0
        assert r1.status_code == 200
        # Second call should hit cache
        t0 = time.time()
        r2 = requests.post(f"{BASE_URL}/api/touchpoints/ai-quality", headers=auth_headers, timeout=30)
        t2 = time.time() - t0
        assert r2.status_code == 200
        # cache should be markedly faster (allow generous threshold)
        assert t2 < 5.0, f"second call took {t2:.2f}s — cache may not be working (first was {t1:.2f}s)"


# ─── Auth/permissions sanity ──────────────────────────────────────────
class TestScoringAuth:
    def test_scoring_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/touchpoints/scoring", timeout=10)
        assert r.status_code in (401, 403), f"expected 401/403 unauth, got {r.status_code}"

    def test_ai_quality_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/touchpoints/ai-quality", timeout=10)
        assert r.status_code in (401, 403)
