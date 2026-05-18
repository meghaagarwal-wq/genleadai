"""Iter 63 — Auto-mapper error UX hardening.

Validates the new diagnostic paths added to /api/aria/auto-map/analyze:
  1. Empty PDF (< 50 chars extracted) → 400 with format-specific guidance.
  2. Empty TXT → 400 with the chars-found hint.
  3. Long TXT (>20k chars) → truncates before sending to Claude (no 502).
  4. Error detail is ALWAYS a string (frontend renders directly into the toast).
"""
from __future__ import annotations

import io
import sys
import pytest

sys.path.insert(0, "/app/backend")

from fastapi.testclient import TestClient
from server import app  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_auth(client):
    r = client.post("/api/auth/login", json={"email": "admin@demo.com", "password": "Demo1234!"})
    body = r.json()
    token = body.get("token") or body.get("access_token")
    user = body.get("user", {})
    tenant_id = (user.get("tenants") or [{}])[0].get("id") or "ten_demo"
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": tenant_id}


def _post_file(client, headers, filename, content_bytes):
    return client.post(
        "/api/aria/auto-map/analyze",
        headers=headers,
        files={"file": (filename, io.BytesIO(content_bytes), "application/octet-stream")},
    )


# 1. Empty / tiny TXT → 400 with helpful string detail
def test_tiny_txt_returns_helpful_string(client, admin_auth):
    r = _post_file(client, admin_auth, "empty.txt", b"hi")
    assert r.status_code == 400
    detail = r.json().get("detail")
    assert isinstance(detail, str), f"detail must be a string, got {type(detail)}"
    assert "chars" in detail.lower() or "gtm" in detail.lower()


# 2. PDF that yields no text (we fake by sending non-PDF bytes) → 400 with the
#    PDF-specific guidance ("scanned image or password-protected")
def test_garbage_pdf_returns_scanned_pdf_hint(client, admin_auth):
    # Garbage bytes with .pdf extension → pypdf will fail, _extract_text returns ""
    r = _post_file(client, admin_auth, "broken.pdf", b"not actually a pdf, just bytes" * 5)
    assert r.status_code == 400
    detail = r.json().get("detail")
    assert isinstance(detail, str)
    assert "scanned" in detail.lower() or "password" in detail.lower() or "ocr" in detail.lower()


# 3. Unsupported file format → 400 with string detail
def test_unsupported_format_string_detail(client, admin_auth):
    r = _post_file(client, admin_auth, "image.png", b"\x89PNG\r\n\x1a\n" + b"a" * 200)
    assert r.status_code == 400
    detail = r.json().get("detail")
    assert isinstance(detail, str)
    assert "unsupported" in detail.lower() or "pdf" in detail.lower() or "docx" in detail.lower()


# 4. Big TXT — extraction works, then truncation kicks in before Claude call.
#    We don't actually wait for Claude here (slow); we just confirm the path
#    doesn't 400 on extraction.
def test_oversized_txt_passes_extraction_step(client, admin_auth, monkeypatch):
    # Stub out _claude_analyze so the test doesn't actually call Claude.
    from routes import aria_auto_map
    async def _fake_claude(text):
        # Confirm input was truncated to MAX_TEXT_CHARS (+ truncation marker)
        assert len(text) <= aria_auto_map.MAX_TEXT_CHARS + 200
        return {
            "icps": [{"label": "Test ICP", "title_targets": ["Founder"], "pain_point": "x", "value_prop": "y"}],
            "touchpoints": [{"step": 1, "channel": "whatsapp", "message_type": "intro", "day": 0, "hour": 9,
                            "aria_role": "autonomous", "message_template": "Hi {{first_name}}",
                            "conditions": {}}],
            "lead_sources": [],
            "qualification": {},
            "handoff": {},
            "summary": "ok",
        }
    monkeypatch.setattr(aria_auto_map, "_claude_analyze", _fake_claude)
    big_txt = ("Founder. Pain point. ICP. Sequence. Day 0 whatsapp intro. " * 1000).encode("utf-8")
    r = _post_file(client, admin_auth, "big.txt", big_txt)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["extracted"]["touchpoints"]


# 5. Claude returning empty touchpoints + empty ICPs → 422, not silent success
def test_empty_claude_result_returns_clear_error(client, admin_auth, monkeypatch):
    from routes import aria_auto_map
    async def _empty_claude(text):
        return {"icps": [], "touchpoints": [], "lead_sources": [], "qualification": {}, "handoff": {}, "summary": ""}
    monkeypatch.setattr(aria_auto_map, "_claude_analyze", _empty_claude)
    r = _post_file(client, admin_auth, "ok.txt", b"This is a valid text file with enough content to pass the 50-char threshold easily.")
    assert r.status_code == 422
    detail = r.json().get("detail")
    assert isinstance(detail, str)
    assert "touchpoints" in detail.lower() or "icp" in detail.lower()
