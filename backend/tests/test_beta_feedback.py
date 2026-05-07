"""Tests for Beta Feedback CRUD endpoints (POST/GET/PATCH/DELETE /api/beta-feedback).

Covers:
- POST: any authenticated user can submit
- GET: admin only (sales_rep gets 403); supports ?resolved & ?category filters
- PATCH: admin only; 404 on unknown id
- DELETE: admin only; 404 on unknown id
- Validation: rejects message <3 chars, rejects invalid category
"""
import os
import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "https://pipeline-pro-96.preview.emergentagent.com").rstrip("/")


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.text}"
    body = r.json()
    return body.get("token") or body.get("access_token")


@pytest.fixture(scope="module")
def admin_headers():
    tok = _login("admin@demo.com", "Demo1234!")
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def rep_headers():
    tok = _login("sarah@demo.com", "Demo1234!")
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# Track ids created by the tests, cleaned in finalizer
_CREATED = []


@pytest.fixture(scope="module", autouse=True)
def _cleanup(admin_headers):
    yield
    for fid in _CREATED:
        try:
            requests.delete(f"{BASE_URL}/api/beta-feedback/{fid}", headers=admin_headers, timeout=15)
        except Exception:
            pass


class TestCreateFeedback:
    def test_admin_can_create(self, admin_headers):
        payload = {"message": "TEST_admin idea entry from pytest", "category": "idea", "page_url": "/dashboard"}
        r = requests.post(f"{BASE_URL}/api/beta-feedback", headers=admin_headers, json=payload, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("status") == "ok"
        fb = body["feedback"]
        assert fb["id"].startswith("fb_")
        assert fb["message"] == payload["message"]
        assert fb["category"] == "idea"
        assert fb["page_url"] == "/dashboard"
        assert fb["resolved"] is False
        assert fb["user_email"] == "admin@demo.com"
        assert "created_at" in fb
        _CREATED.append(fb["id"])

    def test_rep_can_create(self, rep_headers):
        payload = {"message": "TEST_rep bug report from pytest", "category": "bug"}
        r = requests.post(f"{BASE_URL}/api/beta-feedback", headers=rep_headers, json=payload, timeout=30)
        assert r.status_code == 200, r.text
        fb = r.json()["feedback"]
        assert fb["category"] == "bug"
        assert fb["user_email"] == "sarah@demo.com"
        _CREATED.append(fb["id"])

    def test_message_min_length_rejected(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/beta-feedback", headers=admin_headers, json={"message": "ab", "category": "idea"}, timeout=15)
        assert r.status_code == 422, r.text

    def test_invalid_category_rejected(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/beta-feedback", headers=admin_headers, json={"message": "TEST_invalid cat", "category": "complaint"}, timeout=15)
        assert r.status_code == 422, r.text

    def test_unauthenticated_rejected(self):
        r = requests.post(f"{BASE_URL}/api/beta-feedback", json={"message": "TEST_no auth", "category": "idea"}, timeout=15)
        assert r.status_code in (401, 403), r.text


class TestListFeedback:
    def test_rep_gets_403_on_list(self, rep_headers):
        r = requests.get(f"{BASE_URL}/api/beta-feedback", headers=rep_headers, timeout=15)
        assert r.status_code == 403, r.text

    def test_admin_lists_with_counts(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/beta-feedback", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "feedback" in data and isinstance(data["feedback"], list)
        assert "counts" in data
        counts = data["counts"]
        assert "total" in counts and "unresolved" in counts and "by_category" in counts
        for c in ("bug", "idea", "praise", "other"):
            assert c in counts["by_category"]
            assert isinstance(counts["by_category"][c], int)
        # The two we created should appear
        ids = {f["id"] for f in data["feedback"]}
        for fid in _CREATED:
            assert fid in ids, f"Expected {fid} in list"

    def test_filter_by_category(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/beta-feedback?category=bug", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        for fb in r.json()["feedback"]:
            assert fb["category"] == "bug"

    def test_filter_by_resolved_false(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/beta-feedback?resolved=false", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        for fb in r.json()["feedback"]:
            assert fb["resolved"] is False


class TestPatchFeedback:
    def test_rep_cannot_patch(self, rep_headers, admin_headers):
        # Create as admin so we have a valid id
        r = requests.post(f"{BASE_URL}/api/beta-feedback", headers=admin_headers, json={"message": "TEST_patch target", "category": "other"}, timeout=15)
        fid = r.json()["feedback"]["id"]
        _CREATED.append(fid)
        r2 = requests.patch(f"{BASE_URL}/api/beta-feedback/{fid}", headers=rep_headers, json={"resolved": True}, timeout=15)
        assert r2.status_code == 403

    def test_admin_can_resolve_and_persists(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/beta-feedback", headers=admin_headers, json={"message": "TEST_resolve flow", "category": "idea"}, timeout=15)
        fid = r.json()["feedback"]["id"]
        _CREATED.append(fid)

        r2 = requests.patch(f"{BASE_URL}/api/beta-feedback/{fid}", headers=admin_headers, json={"resolved": True, "admin_note": "fixed"}, timeout=15)
        assert r2.status_code == 200, r2.text
        fb = r2.json()["feedback"]
        assert fb["resolved"] is True
        assert fb["admin_note"] == "fixed"

        # Verify via GET list
        r3 = requests.get(f"{BASE_URL}/api/beta-feedback?resolved=true", headers=admin_headers, timeout=15)
        ids = {f["id"]: f for f in r3.json()["feedback"]}
        assert fid in ids and ids[fid]["resolved"] is True

    def test_patch_unknown_id_returns_404(self, admin_headers):
        r = requests.patch(f"{BASE_URL}/api/beta-feedback/fb_doesnotexist", headers=admin_headers, json={"resolved": True}, timeout=15)
        assert r.status_code == 404


class TestDeleteFeedback:
    def test_rep_cannot_delete(self, rep_headers, admin_headers):
        r = requests.post(f"{BASE_URL}/api/beta-feedback", headers=admin_headers, json={"message": "TEST_delete target rep", "category": "other"}, timeout=15)
        fid = r.json()["feedback"]["id"]
        _CREATED.append(fid)
        r2 = requests.delete(f"{BASE_URL}/api/beta-feedback/{fid}", headers=rep_headers, timeout=15)
        assert r2.status_code == 403

    def test_admin_can_delete_and_gone(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/beta-feedback", headers=admin_headers, json={"message": "TEST_delete me", "category": "praise"}, timeout=15)
        fid = r.json()["feedback"]["id"]
        r2 = requests.delete(f"{BASE_URL}/api/beta-feedback/{fid}", headers=admin_headers, timeout=15)
        assert r2.status_code == 200
        # Re-delete returns 404
        r3 = requests.delete(f"{BASE_URL}/api/beta-feedback/{fid}", headers=admin_headers, timeout=15)
        assert r3.status_code == 404

    def test_delete_unknown_id_returns_404(self, admin_headers):
        r = requests.delete(f"{BASE_URL}/api/beta-feedback/fb_nope_nope", headers=admin_headers, timeout=15)
        assert r.status_code == 404
