"""Iter174 backend tests — demo_enrich JSON-LD upgrade + demo_recording upload/serve/send."""
import io
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")
# Fallback: read from frontend .env if not present
if not BASE_URL or "None" in BASE_URL:
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass


# ── /api/enrich ──────────────────────────────────────────────────────
class TestEnrich:
    def test_enrich_hubspot_jsonld(self):
        r = requests.get(f"{BASE_URL}/api/enrich", params={"domain": "hubspot.com"}, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        print("HubSpot enrich:", data)
        assert data.get("companyName") == "HubSpot", f"Expected 'HubSpot', got {data.get('companyName')}"
        logo = data.get("logoUrl") or ""
        assert "HSLogo_color.svg" in logo, f"Expected HSLogo_color.svg in logoUrl, got {logo}"
        tagline = (data.get("tagline") or "").lower()
        assert "ai-powered customer platform" in tagline, f"Expected 'AI-powered customer platform' in tagline, got {tagline}"

    def test_enrich_stripe(self):
        r = requests.get(f"{BASE_URL}/api/enrich", params={"domain": "stripe.com"}, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        print("Stripe enrich:", data)
        assert data.get("companyName") == "Stripe", f"Expected 'Stripe', got {data.get('companyName')}"

    def test_enrich_nonexistent_domain(self):
        r = requests.get(
            f"{BASE_URL}/api/enrich",
            params={"domain": "this-domain-definitely-does-not-exist-xyz-99.io"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("source") == "fallback"
        assert data.get("companyName"), "Expected a fallback companyName"


# ── /api/demo-recording ─────────────────────────────────────────────
class TestDemoRecording:
    def test_upload_then_get_then_send(self):
        # Small binary payload
        payload = b"\x1a\x45\xdf\xa3" + os.urandom(1024)  # fake webm header + noise
        files = {"file": ("clip.webm", io.BytesIO(payload), "video/webm")}
        data = {"brand": "Acme", "duration_sec": "5"}
        r = requests.post(f"{BASE_URL}/api/demo-recording/upload", files=files, data=data, timeout=60)
        assert r.status_code == 200, f"upload failed: {r.status_code} {r.text}"
        j = r.json()
        print("Upload:", j)
        assert j.get("ok") is True
        rec_id = j.get("recording_id")
        assert rec_id, "Missing recording_id"
        assert j.get("share_url"), "Missing share_url"

        # GET serve
        g = requests.get(f"{BASE_URL}/api/demo-recording/{rec_id}", timeout=60)
        assert g.status_code == 200, f"GET failed: {g.status_code} {g.text[:200]}"
        assert len(g.content) == len(payload), f"Content size mismatch: {len(g.content)} vs {len(payload)}"

        # POST send
        s = requests.post(
            f"{BASE_URL}/api/demo-recording/send",
            json={"recording_id": rec_id, "to_email": "test@example.com", "brand": "Acme"},
            timeout=30,
        )
        assert s.status_code == 200, f"send failed: {s.status_code} {s.text}"
        sj = s.json()
        print("Send:", sj)
        assert sj.get("ok") is True
        assert "delivered" in sj  # bool either way
