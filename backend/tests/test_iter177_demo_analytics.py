"""Iter177 — session-aware demo analytics tests."""
import os
import uuid
import time
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")
PREFIX = f"{BASE_URL}/api/demo-analytics"


def _sid():
    return str(uuid.uuid4())


# ─── /view ───────────────────────────────────────────────────────
class TestView:
    def test_view_creates_session(self):
        sid = _sid()
        r = requests.post(f"{PREFIX}/view", json={
            "session_id": sid,
            "company": "Stripe.com",
            "mode": "b2b",
            "scenario": "scaling",
            "source": "gateway",
            "path": "/aria-demo",
        }, timeout=15)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["ok"] is True
        assert j["session_id"] == sid

        # Verify via pulse
        p = requests.get(f"{PREFIX}/pulse?limit=500", timeout=15).json()
        row = next((s for s in p["sessions"] if s["session_id"] == sid), None)
        assert row is not None, "session not visible in /pulse after /view"
        assert row["company"] == "stripe.com"  # normalized lower
        assert row["mode"] == "b2b"
        assert row["scenario"] == "scaling"
        assert row["source"] == "gateway"

    def test_view_invalid_mode_coerced_none(self):
        sid = _sid()
        r = requests.post(f"{PREFIX}/view", json={"session_id": sid, "mode": "weird", "source": "foo"}, timeout=15)
        assert r.status_code == 200
        p = requests.get(f"{PREFIX}/pulse?limit=500", timeout=15).json()
        row = next((s for s in p["sessions"] if s["session_id"] == sid), None)
        assert row is not None
        assert row["mode"] is None
        # Invalid source should normalize to 'direct'
        assert row["source"] == "direct"

    def test_view_without_session_still_200(self):
        r = requests.post(f"{PREFIX}/view", json={"company": "example.com", "source": "direct"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["ok"] is True


# ─── /heartbeat ──────────────────────────────────────────────────
class TestHeartbeat:
    def test_heartbeat_increments_dwell(self):
        sid = _sid()
        requests.post(f"{PREFIX}/view", json={
            "session_id": sid, "company": "acme.com", "mode": "b2b",
            "scenario": "default", "source": "direct",
        }, timeout=15)
        # First beat — ~0s since view
        requests.post(f"{PREFIX}/heartbeat", json={"session_id": sid, "mode": "b2b", "tab": "command"}, timeout=15)
        time.sleep(3)
        r = requests.post(f"{PREFIX}/heartbeat", json={"session_id": sid, "mode": "b2b", "tab": "approvals"}, timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert j["ok"] is True
        assert j["dwell_sec_added"] >= 2  # ~3s elapsed

        p = requests.get(f"{PREFIX}/pulse?limit=500", timeout=15).json()
        row = next((s for s in p["sessions"] if s["session_id"] == sid), None)
        assert row is not None
        assert row["dwell_sec"] >= 2
        assert row["tab"] == "approvals"

    def test_heartbeat_bad_sid(self):
        r = requests.post(f"{PREFIX}/heartbeat", json={"session_id": "nope!!!"}, timeout=15)
        assert r.status_code == 400

    def test_heartbeat_bootstraps_session_without_view(self):
        sid = _sid()
        r = requests.post(f"{PREFIX}/heartbeat", json={"session_id": sid, "mode": "b2c"}, timeout=15)
        assert r.status_code == 200
        p = requests.get(f"{PREFIX}/pulse?limit=500", timeout=15).json()
        assert any(s["session_id"] == sid for s in p["sessions"])


# ─── /identify ───────────────────────────────────────────────────
class TestIdentify:
    def test_identify_stores_name_email(self):
        sid = _sid()
        requests.post(f"{PREFIX}/view", json={"session_id": sid, "source": "direct"}, timeout=15)
        r = requests.post(f"{PREFIX}/identify", json={
            "session_id": sid,
            "name": "TEST_ Prospect",
            "email": "test_prospect@example.com",
        }, timeout=15)
        assert r.status_code == 200
        assert r.json()["ok"] is True

        p = requests.get(f"{PREFIX}/pulse?limit=500", timeout=15).json()
        row = next((s for s in p["sessions"] if s["session_id"] == sid), None)
        assert row and row["identify"]
        assert row["identify"]["name"] == "TEST_ Prospect"
        assert row["identify"]["email"] == "test_prospect@example.com"

        # Totals.identified reflects at least this one
        assert p["totals"]["identified"] >= 1

    def test_identify_bad_email_422(self):
        sid = _sid()
        r = requests.post(f"{PREFIX}/identify", json={"session_id": sid, "email": "not-an-email"}, timeout=15)
        assert r.status_code == 422


# ─── /event ──────────────────────────────────────────────────────
class TestEvent:
    def test_event_push_and_book_clicked(self):
        sid = _sid()
        requests.post(f"{PREFIX}/view", json={"session_id": sid, "source": "direct"}, timeout=15)
        r = requests.post(f"{PREFIX}/event", json={
            "session_id": sid, "kind": "book_clicked", "data": {"from": "test"}
        }, timeout=15)
        assert r.status_code == 200
        requests.post(f"{PREFIX}/event", json={"session_id": sid, "kind": "ask_aria"}, timeout=15)

        p = requests.get(f"{PREFIX}/pulse?limit=500", timeout=15).json()
        row = next((s for s in p["sessions"] if s["session_id"] == sid), None)
        assert row is not None
        kinds = [e["kind"] for e in row["events"]]
        assert "book_clicked" in kinds
        assert "ask_aria" in kinds
        assert row["book_clicked"] is True


# ─── /pulse structure ────────────────────────────────────────────
class TestPulse:
    def test_pulse_shape(self):
        r = requests.get(f"{PREFIX}/pulse", timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert "totals" in j and "sessions" in j
        for k in ("sessions", "warm", "booked", "identified"):
            assert k in j["totals"]
            assert isinstance(j["totals"][k], int)
        # Newest first
        times = [s.get("last_seen_at") or "" for s in j["sessions"]]
        assert times == sorted(times, reverse=True)

    def test_pulse_limit_param(self):
        r = requests.get(f"{PREFIX}/pulse?limit=5", timeout=15)
        assert r.status_code == 200
        assert len(r.json()["sessions"]) <= 5


# ─── End-to-end simulation: gateway → demo with stripe/b2b/scaling ─
class TestE2EStripeScaling:
    def test_e2e_session_shows_in_pulse(self):
        sid = _sid()
        # Mimic UniversalDemoDashboard mount with source=gateway
        requests.post(f"{PREFIX}/view", json={
            "session_id": sid,
            "company":    "stripe.com",
            "mode":       "b2b",
            "scenario":   "scaling",
            "source":     "gateway",
            "path":       "/aria-demo",
            "referrer":   "https://example.com/",
        }, timeout=15)
        # Heartbeat (as the dashboard does immediately)
        requests.post(f"{PREFIX}/heartbeat", json={
            "session_id": sid, "company": "stripe.com", "mode": "b2b",
            "scenario": "scaling", "tab": "command",
        }, timeout=15)

        p = requests.get(f"{PREFIX}/pulse?limit=500", timeout=15).json()
        row = next((s for s in p["sessions"] if s["session_id"] == sid), None)
        assert row is not None, "stripe/b2b/scaling session not visible in /pulse"
        assert row["mode"] == "b2b"
        assert row["scenario"] == "scaling"
        assert row["company"] == "stripe.com"
        assert row["source"] is not None
        assert row["source"] == "gateway"
