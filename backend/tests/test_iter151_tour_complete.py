"""iter151 — Backend tests for tour completion persistence (P1 fix).

Verifies:
 - POST /api/auth/me/tour-complete persists `tour_completed_at` on the user doc.
 - GET /api/auth/me includes the `tour_completed_at` field.
 - POST /api/auth/login response.user now includes `tour_completed_at`.
 - Backfilled users (megha@contentvista.com, meghaagarwaljain2015@gmail.com)
   already have a non-null `tour_completed_at`.
"""
import os
import requests
import pytest
from datetime import datetime

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not set"

PIETENTIAL_OWNER = ("megha@contentvista.com", "Pietential2026!")
DEMO_VIEWER = ("meghaagarwaljain2015@gmail.com", "DemoView2026!")


def _login(email: str, password: str) -> dict:
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password},
                      timeout=20)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()


def _is_iso(s):
    if not isinstance(s, str):
        return False
    try:
        # python's fromisoformat handles both naive iso and 'YYYY-MM-DDTHH:MM:SS+00:00'
        datetime.fromisoformat(s.replace("Z", "+00:00"))
        return True
    except Exception:
        return False


# ── Login response includes tour_completed_at ──────────────────────────
class TestLoginResponseHasTourField:
    def test_pietential_owner_login_has_tour_field(self):
        data = _login(*PIETENTIAL_OWNER)
        assert "user" in data
        assert "tour_completed_at" in data["user"], \
            f"login response.user missing tour_completed_at: {data['user'].keys()}"
        # backfilled user — must not be None
        assert data["user"]["tour_completed_at"] is not None, \
            "Pietential owner is backfilled — tour_completed_at must not be null"

    def test_demo_viewer_login_has_tour_field(self):
        data = _login(*DEMO_VIEWER)
        assert "tour_completed_at" in data["user"]
        assert data["user"]["tour_completed_at"] is not None, \
            "Demo viewer is backfilled — tour_completed_at must not be null"


# ── GET /api/auth/me returns the field ────────────────────────────────
class TestMeEndpointHasTourField:
    def test_me_includes_tour_completed_at_pietential(self):
        token = _login(*PIETENTIAL_OWNER)["token"]
        r = requests.get(f"{BASE_URL}/api/auth/me",
                         headers={"Authorization": f"Bearer {token}"},
                         timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "tour_completed_at" in body, \
            f"/auth/me missing tour_completed_at: {list(body.keys())}"
        assert body["tour_completed_at"] is not None

    def test_me_includes_tour_completed_at_demo_viewer(self):
        token = _login(*DEMO_VIEWER)["token"]
        r = requests.get(f"{BASE_URL}/api/auth/me",
                         headers={"Authorization": f"Bearer {token}"},
                         timeout=20)
        assert r.status_code == 200
        assert r.json().get("tour_completed_at") is not None


# ── POST /api/auth/me/tour-complete ───────────────────────────────────
class TestTourCompleteEndpoint:
    def test_tour_complete_returns_ok_and_iso(self):
        token = _login(*PIETENTIAL_OWNER)["token"]
        r = requests.post(f"{BASE_URL}/api/auth/me/tour-complete",
                          headers={"Authorization": f"Bearer {token}"},
                          timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        assert "tour_completed_at" in body
        assert _is_iso(body["tour_completed_at"]), \
            f"tour_completed_at not ISO: {body['tour_completed_at']}"

    def test_tour_complete_persists_to_db(self):
        # Mark the tour as completed, then re-fetch /me and confirm the
        # value matches what was returned (proves it was written to mongo).
        token = _login(*PIETENTIAL_OWNER)["token"]
        post_resp = requests.post(f"{BASE_URL}/api/auth/me/tour-complete",
                                  headers={"Authorization": f"Bearer {token}"},
                                  timeout=20)
        assert post_resp.status_code == 200
        new_ts = post_resp.json()["tour_completed_at"]

        me = requests.get(f"{BASE_URL}/api/auth/me",
                          headers={"Authorization": f"Bearer {token}"},
                          timeout=20).json()
        assert me["tour_completed_at"] == new_ts, \
            f"expected persisted {new_ts}, got {me['tour_completed_at']}"

    def test_tour_complete_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/auth/me/tour-complete", timeout=20)
        # 401 or 403 both acceptable for missing bearer
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"
