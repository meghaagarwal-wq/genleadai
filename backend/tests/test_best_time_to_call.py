"""Iteration 12 — ARIA Best Time to Call backend tests.

Endpoints under test:
- GET /api/aria/best-time-to-call/{lead_id}
- GET /api/aria/call-priority

Verifies:
- Response shape & required keys
- Country/phone -> timezone resolution
- call_score thresholds (brochure-open recency, ICP, active window)
- urgency mapping (now/soon/later) and 'Best in 0h' bug-fix
- Limit clamping for call-priority
- Auth (401) and missing-lead (404)
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PWD = "Demo1234!"

# Seed leads referenced by main agent
LEAD_WITH_RECENT_BROCHURE = "69e081b5cd724a3d376691c4"   # 4 brochure views, one within last hour
LEAD_QUINN_HIGH_ICP = "69df5f8410ff1b6e41ead225"         # ICP 93, no brochure opens

REQUIRED_KEYS = {
    "tz_label", "utc_offset_hours", "lead_local_hour",
    "active_window_local", "active_start_hour", "active_end_hour",
    "in_window", "minutes_since_brochure_open", "call_score",
    "urgency", "suggested_action", "reasons", "data_source",
}


@pytest.fixture(scope="module")
def auth():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PWD}, timeout=20)
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok, "no token in login response"
    return {"Authorization": f"Bearer {tok}"}


# ─── /api/aria/best-time-to-call/{lead_id} ─────────────────────────
class TestBestTimeToCallShape:
    def test_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/aria/best-time-to-call/{LEAD_WITH_RECENT_BROCHURE}", timeout=15)
        assert r.status_code in (401, 403), f"expected 401/403 got {r.status_code}"

    def test_404_for_unknown_lead(self, auth):
        # Valid 24-char hex but nonexistent
        r = requests.get(f"{BASE_URL}/api/aria/best-time-to-call/000000000000000000000000",
                         headers=auth, timeout=15)
        assert r.status_code == 404, r.text

    def test_400_for_invalid_lead_id(self, auth):
        r = requests.get(f"{BASE_URL}/api/aria/best-time-to-call/not-an-objectid",
                         headers=auth, timeout=15)
        assert r.status_code in (400, 404, 422), r.text

    def test_response_shape(self, auth):
        r = requests.get(f"{BASE_URL}/api/aria/best-time-to-call/{LEAD_WITH_RECENT_BROCHURE}",
                         headers=auth, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        missing = REQUIRED_KEYS - set(d.keys())
        assert not missing, f"Missing keys: {missing}. Got: {list(d.keys())}"
        assert isinstance(d["reasons"], list)
        assert isinstance(d["call_score"], int)
        assert 0 <= d["call_score"] <= 100
        assert d["urgency"] in {"now", "soon", "later"}
        assert isinstance(d["in_window"], bool)
        assert d["data_source"] in {"reply_heatmap", "default_business_hours"}


# ─── Brochure recency boosts call_score ──────────────────────────
class TestBrochureRecency:
    def test_recent_brochure_gives_high_score(self, auth):
        r = requests.get(f"{BASE_URL}/api/aria/best-time-to-call/{LEAD_WITH_RECENT_BROCHURE}",
                         headers=auth, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        # Lead has at least one brochure view — minutes_since should not be None
        # If most-recent view is within 30m we expect score>=60. Even at <=240m, >=30.
        if d["minutes_since_brochure_open"] is not None and d["minutes_since_brochure_open"] <= 30:
            assert d["call_score"] >= 60, f"score {d['call_score']} for {d['minutes_since_brochure_open']}m brochure"
            joined = " ".join(d["reasons"]).lower()
            assert "opened brochure" in joined, f"reasons missing brochure mention: {d['reasons']}"
        else:
            # If older view, we just confirm a reason mentions the brochure when within 4h
            if d["minutes_since_brochure_open"] is not None and d["minutes_since_brochure_open"] <= 240:
                joined = " ".join(d["reasons"]).lower()
                assert "opened brochure" in joined


# ─── Quinn (high ICP, no brochure) ───────────────────────────────
class TestHighICPNoBrochure:
    def test_quinn_in_window_softscore(self, auth):
        r = requests.get(f"{BASE_URL}/api/aria/best-time-to-call/{LEAD_QUINN_HIGH_ICP}",
                         headers=auth, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        # Quinn has no brochure opens
        assert d["minutes_since_brochure_open"] is None
        # ICP=93 → expect 'hot ICP' reason
        joined = " ".join(d["reasons"]).lower()
        assert "hot icp" in joined, f"expected 'hot icp' in reasons: {d['reasons']}"
        # If in window, urgency should be soon/later (cannot be 'now' without recent brochure since max score = 25+15=40)
        assert d["urgency"] in {"soon", "later"}, f"urgency={d['urgency']}"
        if d["in_window"]:
            assert any("active hours" in r.lower() for r in d["reasons"])


# ─── Country / phone -> timezone resolution ──────────────────────
# We can't easily craft synthetic leads, but we can verify _resolve outputs
# indirectly via the endpoint by checking known seed lead's tz_label/utc_offset.
class TestTimezoneResolution:
    def test_lead_tz_present(self, auth):
        r = requests.get(f"{BASE_URL}/api/aria/best-time-to-call/{LEAD_WITH_RECENT_BROCHURE}",
                         headers=auth, timeout=20)
        d = r.json()
        assert d["tz_label"] in {"IST", "EST", "GMT", "CET", "AEDT", "SGT", "JST", "GST", "BRT", "CST", "UTC"}
        assert isinstance(d["utc_offset_hours"], (int, float))


# ─── Suggested-action 'Best in 0h' bug-fix ───────────────────────
class TestBestInZeroHoursBugfix:
    def test_no_best_in_0h_when_in_window(self, auth):
        # Hit both seed leads — at least one is likely in_window=True
        for lid in (LEAD_WITH_RECENT_BROCHURE, LEAD_QUINN_HIGH_ICP):
            r = requests.get(f"{BASE_URL}/api/aria/best-time-to-call/{lid}", headers=auth, timeout=20)
            assert r.status_code == 200
            d = r.json()
            if d["in_window"]:
                assert "best in 0h" not in d["suggested_action"].lower(), (
                    f"'Best in 0h' bug for lead {lid}: {d['suggested_action']}"
                )
                # When in_window with low score we expect 'Available now' phrasing
                if d["urgency"] == "later":
                    assert "available now" in d["suggested_action"].lower(), d["suggested_action"]


# ─── /api/aria/call-priority ─────────────────────────────────────
class TestCallPriority:
    def test_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/aria/call-priority", timeout=15)
        assert r.status_code in (401, 403)

    def test_default_limit_returns_priority_list(self, auth):
        r = requests.get(f"{BASE_URL}/api/aria/call-priority", headers=auth, timeout=25)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "priority" in d and "checked_count" in d
        assert isinstance(d["priority"], list)
        assert isinstance(d["checked_count"], int)
        assert len(d["priority"]) <= 3
        # Every row carries lead identity + best-time fields
        if d["priority"]:
            row = d["priority"][0]
            for k in ("lead_id", "first_name", "last_name", "company_name", "phone",
                      "email", "icp_score", "icp_tier"):
                assert k in row, f"row missing {k}: {row.keys()}"
            for k in REQUIRED_KEYS:
                assert k in row, f"row missing best-time key {k}"

    def test_sorted_by_call_score_desc(self, auth):
        r = requests.get(f"{BASE_URL}/api/aria/call-priority?limit=10", headers=auth, timeout=25)
        d = r.json()
        scores = [(row["call_score"], row.get("icp_score") or 0) for row in d["priority"]]
        # Verify desc by (call_score, icp_score)
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], f"out of order: {scores}"

    def test_limit_clamped_low(self, auth):
        r = requests.get(f"{BASE_URL}/api/aria/call-priority?limit=0", headers=auth, timeout=20)
        assert r.status_code == 200
        assert len(r.json()["priority"]) <= 1

    def test_limit_clamped_high(self, auth):
        r = requests.get(f"{BASE_URL}/api/aria/call-priority?limit=99", headers=auth, timeout=25)
        assert r.status_code == 200
        assert len(r.json()["priority"]) <= 10

    def test_recent_brochure_lead_in_priority(self, auth):
        r = requests.get(f"{BASE_URL}/api/aria/call-priority?limit=10", headers=auth, timeout=25)
        d = r.json()
        ids = [row["lead_id"] for row in d["priority"]]
        # The seed lead with recent brochure should appear in top-10
        assert LEAD_WITH_RECENT_BROCHURE in ids, f"recent-brochure lead missing. Got: {ids}"
