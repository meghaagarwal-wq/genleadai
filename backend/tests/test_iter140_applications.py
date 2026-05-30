"""iter140 — Public /api/applications smoke + V1-V5 funnel backend guards."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")

VALID = {
    "full_name": "TEST_Megha Agarwal",
    "work_email": "test_iter140@example.com",
    "role": "Founder",
    "country": "India",
    "company_name": "TEST_Pietential",
    "company_url": "pietential.com",
    "industry": "SaaS",
    "employees": "6–20",
    "revenue": "$100K–$500K",
    "current_setup": "Founder-led replies, manual follow-up via WhatsApp and Email.",
    "channels": ["WhatsApp", "Email", "LinkedIn"],
    "current_volume": "~150 inbound, ~50 outbound",
    "biggest_pain": "Leads going cold, no consistent follow-up rhythm.",
    "goal": "3x reply rate and book 20 qualified calls/week.",
    "timeline": "1-3_months",
    "budget_band": "10k_50k",
    "ready_to_start": True,
}


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def test_submit_valid_application_returns_201(api):
    r = api.post(f"{BASE_URL}/api/applications", json=VALID)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["id"].startswith("app_")
    assert data["full_name"] == VALID["full_name"]
    assert data["company_name"] == VALID["company_name"]
    pytest.app_id = data["id"]


def test_confirm_returns_persisted_fields(api):
    aid = getattr(pytest, "app_id", None)
    assert aid, "submit test must run first"
    r = api.get(f"{BASE_URL}/api/applications/{aid}/confirm")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["id"] == aid
    assert d["full_name"] == VALID["full_name"]
    assert d["company_name"] == VALID["company_name"]
    assert "created_at" in d


def test_confirm_unknown_id_returns_404(api):
    r = api.get(f"{BASE_URL}/api/applications/nope_does_not_exist/confirm")
    assert r.status_code == 404


def test_invalid_timeline_returns_400(api):
    bad = dict(VALID)
    bad["work_email"] = "test_iter140_bad_timeline@example.com"
    bad["timeline"] = "WHENEVER"
    r = api.post(f"{BASE_URL}/api/applications", json=bad)
    assert r.status_code in (400, 422), r.text
    if r.status_code == 400:
        assert "timeline" in r.text.lower()


def test_invalid_budget_returns_400(api):
    bad = dict(VALID)
    bad["work_email"] = "test_iter140_bad_budget@example.com"
    bad["budget_band"] = "infinity"
    r = api.post(f"{BASE_URL}/api/applications", json=bad)
    assert r.status_code in (400, 422)


def test_malformed_email_returns_422(api):
    bad = dict(VALID)
    bad["work_email"] = "not-an-email"
    r = api.post(f"{BASE_URL}/api/applications", json=bad)
    assert r.status_code == 422


def test_missing_required_field_returns_422(api):
    bad = dict(VALID)
    bad.pop("company_name")
    r = api.post(f"{BASE_URL}/api/applications", json=bad)
    assert r.status_code == 422


def test_endpoint_is_public_no_auth_required(api):
    # No Authorization header sent; should still accept.
    bare = requests.post(f"{BASE_URL}/api/applications", json={
        **VALID,
        "work_email": "test_iter140_public@example.com",
    })
    assert bare.status_code == 201, bare.text
