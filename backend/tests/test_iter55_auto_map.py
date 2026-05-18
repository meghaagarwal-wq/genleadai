"""Iter 55 — AI Journey Auto Mapper backend tests.

Covers:
  - /analyze rejects unsupported file formats with STRING detail (toast-safe)
  - /analyze with a real .docx → returns the expected shape (icps, lead_sources,
    touchpoints with conditions, qualification, handoff, summary)
  - /publish persists ICPs (creates new, skips existing by case-insensitive label)
    and replaces the touchpoint map when overwrite_journey=true
  - /improve returns a {suggestions: [...]} shape (or empty if Claude can't reason)

Run:  cd /app/backend && python -m pytest tests/test_iter55_auto_map.py -v
"""
import io
import os
import sys
import requests
import pytest
from pymongo import MongoClient
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

API_URL = os.getenv("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com")
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = "Demo1234!"

mongo_client = MongoClient(os.environ["MONGO_URL"])
db = mongo_client[os.environ["DB_NAME"]]


@pytest.fixture(scope="module")
def auth():
    r = requests.post(f"{API_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD,
    }, timeout=15)
    assert r.status_code == 200
    data = r.json()
    token = data["token"]
    tenant_id = data["user"].get("tenant_id") or "ten_demo"
    return {
        "headers": {
            "Authorization": f"Bearer {token}",
            "X-Tenant-Id": tenant_id,
        },
        "tenant_id": tenant_id,
    }


def _make_docx(text: str) -> bytes:
    from docx import Document
    d = Document()
    for para in text.split("\n\n"):
        d.add_paragraph(para)
    bio = io.BytesIO()
    d.save(bio)
    return bio.getvalue()


@pytest.fixture
def baseline_map(auth):
    """Snapshot + restore the touchpoint map so the test doesn't trash demo data."""
    r = requests.get(f"{API_URL}/api/touchpoints/map",
                     headers={**auth["headers"], "Content-Type": "application/json"}, timeout=10)
    snapshot = (r.json() or {}).get("map") or {}
    yield snapshot
    if snapshot.get("touchpoints"):
        requests.post(f"{API_URL}/api/touchpoints/map",
                      headers={**auth["headers"], "Content-Type": "application/json"}, json={
            "template_id": snapshot.get("template_id") or "tpl_standard",
            "is_customised": snapshot.get("is_customised", True),
            "touchpoints": [
                {k: v for k, v in tp.items() if k in (
                    "index", "day", "hour", "channel", "message_type",
                    "aria_role", "trigger", "message_template", "conditions",
                )}
                for tp in snapshot.get("touchpoints", [])
            ],
        }, timeout=10)


def test_analyze_rejects_unsupported_format_with_string_detail(auth):
    """The same toast-safety contract — error detail must be a string, not a Pydantic array."""
    r = requests.post(
        f"{API_URL}/api/aria/auto-map/analyze",
        headers=auth["headers"],
        files={"file": ("evil.exe", b"random bytes", "application/octet-stream")},
        timeout=15,
    )
    assert r.status_code in (400, 415), r.text
    detail = r.json().get("detail")
    assert isinstance(detail, str), f"detail must be string, got {type(detail).__name__}: {detail!r}"
    assert "Unsupported file format" in detail


def test_analyze_with_real_docx_returns_structured_workflow(auth):
    """End-to-end Claude call — slow (20-40s). Verifies the response shape."""
    doc_text = """
GTM Strategy — Q1 2026

We sell to CHROs and VP People at mid-enterprise SaaS companies in the USA, 500-5000 employees.
Pain: spending 5+ hours/week on manual candidate sourcing, slow time-to-hire.
Value prop: Aria sources candidates, qualifies them via WhatsApp, and books interviews — all in 1 day.

Lead sources: LinkedIn outreach (Saleshandy), Meta ads, Website form submissions, Webinar attendees.

Outbound sequence:
- Day 0: Intro WhatsApp message — friendly tone, mention their team size.
- Day 2: Email follow-up with case study from a similar company.
- Day 5: LinkedIn touchpoint with social proof.
- Day 7: WhatsApp soft CTA — offer a 15-min discovery call.

If lead replies positively or mentions "pricing" or "demo", tag them hot_lead and notify the founder immediately.
If lead replies negatively ("not interested" / "stop"), stop the sequence.
If lead doesn't reply for 72 hours, advance to next step automatically.

Qualification: must be at a 500+ person company, must be the actual HR decision maker.
Disqualifiers: under 50 employees, agencies, non-USA HQ.

Handoff: as soon as a lead is tagged hot_lead, send Slack + email alert to founder with lead's company, role, last message, and ARR estimate.
"""
    docx_bytes = _make_docx(doc_text)
    r = requests.post(
        f"{API_URL}/api/aria/auto-map/analyze",
        headers=auth["headers"],
        files={"file": ("gtm.docx", docx_bytes,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        timeout=90,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    extracted = body.get("extracted") or {}
    # Shape assertions
    for key in ("icps", "lead_sources", "touchpoints", "qualification", "handoff", "summary"):
        assert key in extracted, f"missing key {key} in extracted"
    # Content sanity
    assert len(extracted["icps"]) >= 1, "Expected at least 1 ICP"
    assert len(extracted["touchpoints"]) >= 3, "Expected ≥3 touchpoints"
    # At least one touchpoint should have meaningful conditions
    with_conds = [tp for tp in extracted["touchpoints"] if tp.get("conditions")]
    assert len(with_conds) >= 1, "Expected ≥1 touchpoint with branching conditions"
    # Every condition must validate against the same schema as Outreach
    from routes.outreach import validate_conditions
    for tp in extracted["touchpoints"]:
        if tp.get("conditions"):
            validate_conditions(tp["conditions"])   # raises if malformed


def test_publish_creates_icps_and_replaces_touchpoint_map(auth, baseline_map):
    """Publish a small synthetic preview — verify ICPs land in Mongo + journey is replaced."""
    tenant_id = auth["tenant_id"]
    # Cleanup any stale test ICPs
    db["icps"].delete_many({"tenant_id": tenant_id, "label": {"$in": ["AutoMap Test CHRO", "AutoMap Test CFO"]}})

    payload = {
        "icps": [
            {"label": "AutoMap Test CHRO", "title_targets": ["CHRO"], "tone": "professional",
             "industry": "SaaS", "pain_point": "slow hiring", "value_prop": "fast sourcing"},
            {"label": "AutoMap Test CFO", "title_targets": ["CFO"], "tone": "bold",
             "industry": "Finance", "pain_point": "manual close", "value_prop": "automate close"},
        ],
        "touchpoints": [
            {"index": 0, "day": 0, "hour": 9, "channel": "whatsapp",
             "message_type": "intro", "aria_role": "autonomous",
             "trigger": "", "message_template": "Hi {{first_name}}", "conditions": {}},
            {"index": 1, "day": 2, "hour": 10, "channel": "email",
             "message_type": "follow_up", "aria_role": "autonomous",
             "trigger": "", "message_template": "Following up", "conditions": {
                 "on_no_reply": {"after_hours": 72, "action": "stop"},
             }},
        ],
        "lead_sources": ["LinkedIn", "Meta Ads"],
        "qualification": {"must_have_criteria": ["500+ employees"]},
        "handoff": {"trigger": "tagged hot_lead", "alert_channels": ["slack"]},
        "summary": "test publish",
        "overwrite_journey": True,
    }
    r = requests.post(
        f"{API_URL}/api/aria/auto-map/publish",
        headers={**auth["headers"], "Content-Type": "application/json"},
        json=payload, timeout=20,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["icps_created"] == 2
    assert body["touchpoints_saved"] == 2

    # Verify ICPs persisted
    icp_count = db["icps"].count_documents({"tenant_id": tenant_id, "label": {"$in": ["AutoMap Test CHRO", "AutoMap Test CFO"]}})
    assert icp_count == 2

    # Republish with same ICPs → should be skipped (case-insensitive)
    payload["icps"] = [{"label": "automap test chro", "tone": "professional"}]
    r2 = requests.post(
        f"{API_URL}/api/aria/auto-map/publish",
        headers={**auth["headers"], "Content-Type": "application/json"},
        json=payload, timeout=20,
    )
    assert r2.status_code == 200
    assert r2.json()["icps_created"] == 0
    assert "automap test chro" in [s.lower() for s in r2.json()["icps_skipped"]]

    # Cleanup
    db["icps"].delete_many({"tenant_id": tenant_id, "label": {"$in": ["AutoMap Test CHRO", "AutoMap Test CFO"]}})


def test_improve_returns_suggestions_shape(auth):
    """Quick Claude call — must return {suggestions: [...]} (possibly empty)."""
    r = requests.post(
        f"{API_URL}/api/aria/auto-map/improve",
        headers={**auth["headers"], "Content-Type": "application/json"},
        json={
            "icps": [{"label": "CFO", "tone": "professional"}],
            "touchpoints": [
                {"index": 0, "day": 0, "channel": "email", "message_template": "Hi"},
            ],
            "lead_sources": ["Cold email"],
        },
        timeout=60,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "suggestions" in body
    assert isinstance(body["suggestions"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
