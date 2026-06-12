"""
iter155 — Re-verify the 3 follow-ups from iter154:
  (1) /api/approvals shows ≥3 pending drafts for the Demo viewer
  (2) /api/conversations/threads shows ≥10 threads (legacy leads mirror)
  (3) B2B Founder why_now has no duplicate lead_ids (React key dupe fix)
Plus tenant isolation regression.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not set"

DEMO_VIEWER = ("meghaagarwaljain2015@gmail.com", "DemoView2026!")
PIETENTIAL = ("megha@contentvista.com", "Pietential2026!")
ADMIN = ("admin@demo.com", "Demo1234!")

EXPECTED_THREAD_NAMES = {
    "Sarah Chen", "Arjun Mehta", "James Whitfield", "Priya Sharma",
    "Marcus O'Brien", "Aisha Patel", "David Müller", "Lin Zhao",
    "Olivia Tremblay", "Yusuf Rahman",
}
DEMO_LEAD_NAMES = {
    "Sarah Chen", "Arjun Mehta", "James Whitfield",
    "Priya Sharma", "Marcus O'Brien", "Aisha Patel",
    "David Müller", "Lin Zhao", "Olivia Tremblay", "Yusuf Rahman",
}


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:300]}"
    return r.json()


@pytest.fixture(scope="module")
def demo_session():
    d = _login(*DEMO_VIEWER)
    tok = d["token"]
    tid = (d.get("tenants") or [{}])[0].get("id") or "ten_demo"
    return tok, tid


@pytest.fixture(scope="module")
def pietential_session():
    d = _login(*PIETENTIAL)
    tok = d["token"]
    tid = (d.get("tenants") or [{}])[0].get("id") or "ten_pietential"
    return tok, tid


@pytest.fixture(scope="module")
def admin_session():
    d = _login(*ADMIN)
    return d["token"]


def _h(tok, tenant=None):
    h = {"Authorization": f"Bearer {tok}"}
    if tenant:
        h["X-Tenant-Id"] = tenant
    return h


# Optional: re-run seed once before tests (idempotent)
def test_demo_reset_idempotent(admin_session):
    r = requests.post(f"{BASE_URL}/api/demo/reset",
                      headers=_h(admin_session, "ten_demo"), timeout=180)
    assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
    body = r.json()
    assert body.get("ok") is True
    purged = body.get("purged", {})
    assert "iter154_error" not in purged, purged.get("iter154_error")


# (1) /api/approvals — ≥3 pending drafts
def test_approvals_returns_three_pending(demo_session):
    tok, tid = demo_session
    r = requests.get(f"{BASE_URL}/api/approvals", headers=_h(tok, tid), timeout=20)
    assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
    body = r.json()
    count = body.get("count")
    items = body.get("items") or []
    assert isinstance(items, list)
    assert len(items) >= 3, f"approvals items={len(items)} body={str(body)[:300]}"
    if count is not None:
        assert count >= 3, f"count={count}"
    sample = items[0]
    assert "channel" in sample or "draft_preview" in sample or "preview" in sample, \
        f"missing channel/draft_preview in approvals item: {list(sample.keys())}"


# (2) /api/conversations/threads — ≥10 threads with the expected names
def test_conversations_threads_has_ten_demo_leads(demo_session):
    tok, tid = demo_session
    r = requests.get(f"{BASE_URL}/api/conversations/threads",
                     headers=_h(tok, tid), timeout=20)
    assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
    body = r.json()
    threads = body if isinstance(body, list) else (
        body.get("threads") or body.get("items") or body.get("rows") or []
    )
    assert isinstance(threads, list)
    assert len(threads) >= 10, f"threads={len(threads)} body_keys={list(body.keys()) if isinstance(body, dict) else 'list'}"

    full_names = set()
    for t in threads:
        if not isinstance(t, dict):
            continue
        fn = (t.get("first_name") or "").strip()
        ln = (t.get("last_name") or "").strip()
        if fn or ln:
            full_names.add(f"{fn} {ln}".strip())
        for k in ("lead_name", "name", "contact_name"):
            v = t.get(k)
            if isinstance(v, str):
                full_names.add(v.strip())
    missing = EXPECTED_THREAD_NAMES - full_names
    assert not missing, f"missing thread names: {missing} (got {len(full_names)} names)"


# (3) B2B Founder why_now — dedup by lead_id
def test_b2b_founder_why_now_no_duplicate_lead_ids(demo_session):
    tok, tid = demo_session
    r = requests.get(f"{BASE_URL}/api/dashboard/b2b-founder",
                     headers=_h(tok, tid), timeout=30)
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    d = r.json()
    wn = d.get("why_now") or {}
    rows = wn.get("rows", wn) if isinstance(wn, dict) else wn
    assert isinstance(rows, list) and len(rows) >= 1, f"why_now empty: {wn}"
    ids = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        rid = row.get("lead_id") or row.get("id") or row.get("ptl_id")
        if rid:
            ids.append(rid)
    assert ids, f"no lead_id-like fields on why_now rows: {rows[0] if rows else None}"
    dup = [i for i in set(ids) if ids.count(i) > 1]
    assert not dup, f"duplicate lead_ids in why_now: {dup}"


# Bonus: same dedup on b2b-sales why_now (helper changed both)
def test_b2b_sales_why_now_no_duplicates(demo_session):
    tok, tid = demo_session
    r = requests.get(f"{BASE_URL}/api/dashboard/b2b-sales",
                     headers=_h(tok, tid), timeout=30)
    assert r.status_code == 200
    d = r.json()
    wn = d.get("why_now") or {}
    rows = wn.get("rows", wn) if isinstance(wn, dict) else wn
    if not isinstance(rows, list) or not rows:
        pytest.skip("b2b-sales has no why_now block")
    ids = []
    for row in rows:
        if isinstance(row, dict):
            rid = row.get("lead_id") or row.get("id") or row.get("ptl_id")
            if rid:
                ids.append(rid)
    dup = [i for i in set(ids) if ids.count(i) > 1]
    assert not dup, f"duplicate lead_ids in b2b-sales why_now: {dup}"


# Tenant isolation — Pietential must NOT see demo names anywhere on approvals/threads
def test_pietential_isolation_approvals_threads(pietential_session):
    tok, tid = pietential_session
    for path in ("/api/approvals", "/api/conversations/threads"):
        r = requests.get(f"{BASE_URL}{path}", headers=_h(tok, tid), timeout=20)
        if r.status_code != 200:
            continue
        body_text = r.text
        for name in DEMO_LEAD_NAMES:
            assert name not in body_text, f"DEMO LEAK in {path}: '{name}' visible to Pietential"
