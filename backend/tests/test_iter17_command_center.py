"""Iter 17 — Founder Command Center endpoint smoke + shape tests."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fall back to frontend env file
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass

ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = "Demo1234!"


@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    body = r.json()
    tok = body.get("token") or body.get("access_token")
    assert tok, f"No token in login response: {body}"
    return tok


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


# Auth requirement
def test_command_center_requires_auth():
    r = requests.get(f"{BASE_URL}/api/insights/founder-command-center", timeout=15)
    assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"


# Full payload shape
def test_command_center_full_shape(auth_headers):
    r = requests.get(f"{BASE_URL}/api/insights/founder-command-center", headers=auth_headers, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()

    # Top-level keys
    for k in [
        "computed_from_real_data", "revenue_leakage", "money_at_risk", "daily_brief",
        "hot_leads_untouched", "first_response", "proposal_graveyard",
        "source_quality", "lost_reasons", "pipeline_value", "pipeline_value_label",
    ]:
        assert k in d, f"Missing top-level key: {k}"

    assert isinstance(d["computed_from_real_data"], bool)

    # Revenue leakage
    rl = d["revenue_leakage"]
    for k in ["score_pct", "headline", "subhead", "breakdown", "cta"]:
        assert k in rl, f"revenue_leakage missing {k}"
    assert isinstance(rl["score_pct"], int)
    assert 0 <= rl["score_pct"] <= 100
    assert len(rl["breakdown"]) == 5
    expected_keys = {"overdue", "hot_untouched", "proposal_stuck", "unassigned", "lost_no_reason"}
    actual_keys = {b["key"] for b in rl["breakdown"]}
    assert actual_keys == expected_keys, f"breakdown keys mismatch: {actual_keys}"
    for b in rl["breakdown"]:
        assert "label" in b and "count" in b and "key" in b

    # Money at risk
    mar = d["money_at_risk"]
    for k in ["total_inr", "total_label", "rows", "cta"]:
        assert k in mar
    assert isinstance(mar["total_inr"], (int, float))
    assert isinstance(mar["total_label"], str) and mar["total_label"].startswith("₹")
    assert isinstance(mar["rows"], list)
    assert len(mar["rows"]) <= 4
    if mar["rows"]:
        row = mar["rows"][0]
        for k in ["name", "deal_value", "reason", "owner", "action"]:
            assert k in row, f"money_at_risk row missing {k}"

    # Daily brief
    db = d["daily_brief"]
    for k in ["greeting", "lines", "cta"]:
        assert k in db
    assert len(db["lines"]) == 6
    assert db["cta"] == "Generate Today's Sales Brief"

    # Hot leads untouched
    hu = d["hot_leads_untouched"]
    assert "count" in hu and "rows" in hu
    assert isinstance(hu["rows"], list)
    assert len(hu["rows"]) <= 5

    # First response
    fr = d["first_response"]
    for k in ["avg_hours", "best_rep", "slowest_rep", "target_minutes", "pending_first_response", "insight"]:
        assert k in fr, f"first_response missing {k}"
    assert "name" in fr["best_rep"] and "minutes" in fr["best_rep"]
    assert "name" in fr["slowest_rep"] and "minutes" in fr["slowest_rep"]
    assert fr["target_minutes"] == 30

    # Proposal graveyard
    pg = d["proposal_graveyard"]
    assert "count" in pg and "rows" in pg
    assert len(pg["rows"]) <= 5

    # Source quality
    sq = d["source_quality"]
    assert "rows" in sq and "insight" in sq
    assert isinstance(sq["rows"], list)
    if sq["rows"]:
        for k in ["source", "total", "hot", "calls_booked", "pipeline"]:
            assert k in sq["rows"][0], f"source_quality row missing {k}"

    # Lost reasons
    lr = d["lost_reasons"]
    assert "rows" in lr and "insight" in lr
    if lr["rows"]:
        for k in ["reason", "count", "insight"]:
            assert k in lr["rows"][0], f"lost_reasons row missing {k}"


def test_command_center_real_data_when_leads_exist(auth_headers):
    # Sanity: with 25 demo leads in DB, we should see computed_from_real_data=True
    r = requests.get(f"{BASE_URL}/api/insights/founder-command-center", headers=auth_headers, timeout=20)
    d = r.json()
    # leads exist → must be true; demo fallback only triggers on empty leads collection
    leads_resp = requests.get(f"{BASE_URL}/api/leads?limit=1", headers=auth_headers, timeout=15)
    if leads_resp.status_code == 200:
        body = leads_resp.json()
        items = body.get("items", body) if isinstance(body, dict) else body
        if items:
            assert d["computed_from_real_data"] is True, "Should be computed from real data since leads exist"


def test_inr_format_in_labels(auth_headers):
    r = requests.get(f"{BASE_URL}/api/insights/founder-command-center", headers=auth_headers, timeout=20)
    d = r.json()
    assert d["money_at_risk"]["total_label"].startswith("₹")
    assert d["pipeline_value_label"].startswith("₹")
