"""Lead Magnet feature backend tests + regression for existing endpoints."""
import io
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PWD = "Demo1234!"
EXISTING_LEAD_ID = "69e081b5cd724a3d376691c4"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PWD}, timeout=20)
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ─── Regression on existing endpoints ───────────────────────────
class TestRegression:
    def test_health(self):
        r = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert r.status_code == 200

    def test_login(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PWD}, timeout=20)
        assert r.status_code == 200

    def test_leads_list(self, auth):
        r = requests.get(f"{BASE_URL}/api/leads?limit=5", headers=auth, timeout=20)
        assert r.status_code == 200

    def test_ttv(self, auth):
        r = requests.get(f"{BASE_URL}/api/ttv/milestones", headers=auth, timeout=20)
        assert r.status_code == 200
        assert "milestones" in r.json()

    def test_onboarding_status(self, auth):
        r = requests.get(f"{BASE_URL}/api/onboarding/status", headers=auth, timeout=20)
        assert r.status_code == 200


# ─── Lead Magnet config ─────────────────────────────────────────
class TestMagnetConfig:
    def test_get_config(self, auth):
        r = requests.get(f"{BASE_URL}/api/lead-magnets/config", headers=auth, timeout=20)
        assert r.status_code == 200
        data = r.json()
        # Either default or persisted; must have these keys
        for k in ["enabled", "type", "send_timing"]:
            assert k in data

    def test_put_config(self, auth):
        payload = {
            "enabled": True,
            "name": "TEST_Brochure",
            "type": "url",
            "url": "https://example.com/brochure.pdf",
            "send_timing": "post_booking",
            "message_template": "Hi {first_name}, link: {link}",
        }
        r = requests.put(f"{BASE_URL}/api/lead-magnets/config", json=payload, headers=auth, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["enabled"] is True
        assert data["url"] == payload["url"]
        assert data["type"] == "url"
        assert data["send_timing"] == "post_booking"

        # GET round-trip
        g = requests.get(f"{BASE_URL}/api/lead-magnets/config", headers=auth, timeout=20)
        gd = g.json()
        assert gd["enabled"] is True
        assert gd["url"] == payload["url"]
        assert gd["name"] == "TEST_Brochure"


# ─── Upload ─────────────────────────────────────────────────────
class TestUpload:
    def test_reject_non_pdf(self, auth):
        files = {"file": ("a.txt", io.BytesIO(b"hello"), "text/plain")}
        r = requests.post(f"{BASE_URL}/api/lead-magnets/upload", files=files, headers=auth, timeout=20)
        assert r.status_code == 400

    def test_accept_pdf(self, auth):
        # minimal PDF magic header
        pdf_bytes = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
        files = {"file": ("brochure.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
        r = requests.post(f"{BASE_URL}/api/lead-magnets/upload", files=files, headers=auth, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "file_id" in d and d["file_id"].endswith(".pdf")
        assert d["file_name"] == "brochure.pdf"
        # serve
        s = requests.get(f"{BASE_URL}/api/uploads/{d['file_id']}", headers=auth, timeout=20)
        assert s.status_code == 200

    def test_uploads_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/uploads/nonexistent.pdf", timeout=20)
        assert r.status_code in (401, 403)

    def test_uploads_404(self, auth):
        r = requests.get(f"{BASE_URL}/api/uploads/__missing__.pdf", headers=auth, timeout=20)
        assert r.status_code == 404


# ─── Send + tracking + engagement ──────────────────────────────
class TestSendAndTrack:
    def test_send_when_disabled_then_enable_and_send(self, auth):
        # Disable first
        requests.put(f"{BASE_URL}/api/lead-magnets/config",
                     json={"enabled": False, "type": "url", "url": "", "send_timing": "post_booking"},
                     headers=auth, timeout=20)
        r = requests.post(f"{BASE_URL}/api/leads/{EXISTING_LEAD_ID}/send-lead-magnet", headers=auth, timeout=20)
        assert r.status_code == 400

        # Enable with no URL
        requests.put(f"{BASE_URL}/api/lead-magnets/config",
                     json={"enabled": True, "type": "url", "url": "", "send_timing": "post_booking"},
                     headers=auth, timeout=20)
        r = requests.post(f"{BASE_URL}/api/leads/{EXISTING_LEAD_ID}/send-lead-magnet", headers=auth, timeout=20)
        assert r.status_code == 400

        # Properly configure
        requests.put(f"{BASE_URL}/api/lead-magnets/config",
                     json={"enabled": True, "type": "url", "url": "https://example.com/tested",
                           "send_timing": "post_booking", "name": "TEST_Brochure"},
                     headers=auth, timeout=20)
        r = requests.post(f"{BASE_URL}/api/leads/{EXISTING_LEAD_ID}/send-lead-magnet", headers=auth, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["sent"] is True
        assert d["channel"] in ("email", "whatsapp")
        assert "/api/lead-magnets/track/" in d["tracking_url"]

        # Track URL (public, no auth) should redirect 302
        tracking_url = d["tracking_url"]
        # NOTE: backend may return relative URL because REACT_APP_BACKEND_URL env not set on backend
        if tracking_url.startswith("/"):
            tracking_url = f"{BASE_URL}{tracking_url}"
        track_resp = requests.get(tracking_url, allow_redirects=False, timeout=20)
        assert track_resp.status_code in (302, 307), f"got {track_resp.status_code}"
        assert track_resp.headers.get("location", "").startswith("https://example.com/")

    def test_track_invalid(self):
        r = requests.get(f"{BASE_URL}/api/lead-magnets/track/__doesnotexist__", allow_redirects=False, timeout=20)
        assert r.status_code == 404

    def test_engagement(self, auth):
        r = requests.get(f"{BASE_URL}/api/lead-magnets/engagement/{EXISTING_LEAD_ID}", headers=auth, timeout=20)
        assert r.status_code == 200
        d = r.json()
        for k in ["sent_count", "view_count", "last_sent", "last_viewed", "is_hot"]:
            assert k in d
        assert d["sent_count"] >= 1
        assert d["view_count"] >= 1
        # is_hot flips when view_count>=2
        assert d["is_hot"] == (d["view_count"] >= 2)
