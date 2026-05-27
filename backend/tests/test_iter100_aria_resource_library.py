"""Iter100 — Backend tests for Aria Resource Library.

Covers CRUD, file upload + serve, lead matcher ranking, attach counter,
and tenant isolation.
"""
import io
import os
import uuid
import pytest
import requests

from deps import db

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD") or os.environ.get("DEMO_ADMIN_PASSWORD", "Demo1234!")

resources_col = db["aria_resources"]
leads_col = db["leads"]


@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=20,
    )
    if r.status_code != 200:
        pytest.skip(f"admin login failed: {r.status_code}")
    tok = r.json().get("token") or r.json().get("access_token")
    return {"Authorization": f"Bearer {tok}", "X-Tenant-Id": "ten_pietential"}


@pytest.fixture()
def cleanup_iter100():
    yield
    resources_col.delete_many({"title": {"$regex": "^Iter100"}})


class TestCRUD:
    def test_create_url_resource(self, admin_headers, cleanup_iter100):
        r = requests.post(
            f"{BASE_URL}/api/aria/resources",
            headers={**admin_headers, "Content-Type": "application/json"},
            json={
                "title": "Iter100 URL Deck",
                "description": "Sample URL resource",
                "category": "deck",
                "type": "url",
                "url": "https://example.com/deck.pdf",
                "tags": ["Pricing", "saas"],
            },
            timeout=20,
        )
        assert r.status_code == 200, r.text
        res = r.json()["resource"]
        assert res["category"] == "deck"
        assert res["tags"] == ["pricing", "saas"]  # lowercased
        assert res["send_count"] == 0
        assert res["archived"] is False

    def test_create_url_rejects_missing_url(self, admin_headers, cleanup_iter100):
        r = requests.post(
            f"{BASE_URL}/api/aria/resources",
            headers={**admin_headers, "Content-Type": "application/json"},
            json={"title": "Iter100 no url", "type": "url"},
            timeout=20,
        )
        assert r.status_code == 400
        assert "url required" in r.json()["detail"].lower()

    def test_create_rejects_invalid_category(self, admin_headers, cleanup_iter100):
        r = requests.post(
            f"{BASE_URL}/api/aria/resources",
            headers={**admin_headers, "Content-Type": "application/json"},
            json={"title": "Iter100 bad cat", "type": "url", "url": "https://x.com",
                  "category": "WHATEVER"},
            timeout=20,
        )
        assert r.status_code == 400

    def test_list_filters(self, admin_headers, cleanup_iter100):
        # seed 3 resources
        for cat, tag in [("deck", "saas"), ("case_study", "pricing"), ("blog", "saas")]:
            requests.post(
                f"{BASE_URL}/api/aria/resources",
                headers={**admin_headers, "Content-Type": "application/json"},
                json={"title": f"Iter100 {cat}", "type": "url", "url": "https://x.com",
                      "category": cat, "tags": [tag]},
                timeout=20,
            )
        # filter by category
        r = requests.get(f"{BASE_URL}/api/aria/resources?category=case_study", headers=admin_headers, timeout=15)
        titles = [x["title"] for x in r.json()["resources"]]
        assert any("Iter100 case_study" in t for t in titles)
        assert not any("Iter100 deck" in t for t in titles)
        # filter by tag
        r = requests.get(f"{BASE_URL}/api/aria/resources?tag=saas", headers=admin_headers, timeout=15)
        titles = [x["title"] for x in r.json()["resources"]]
        # both 'deck' and 'blog' have tag saas
        iter100_saas = [t for t in titles if t.startswith("Iter100")]
        assert len(iter100_saas) >= 2

    def test_update_and_archive(self, admin_headers, cleanup_iter100):
        r = requests.post(
            f"{BASE_URL}/api/aria/resources",
            headers={**admin_headers, "Content-Type": "application/json"},
            json={"title": "Iter100 Edit", "type": "url", "url": "https://x.com", "tags": ["a"]},
            timeout=20,
        )
        rid = r.json()["resource"]["id"]
        # Update
        r = requests.patch(
            f"{BASE_URL}/api/aria/resources/{rid}",
            headers={**admin_headers, "Content-Type": "application/json"},
            json={"title": "Iter100 Edited", "tags": ["b", "c"]},
            timeout=20,
        )
        assert r.status_code == 200
        assert r.json()["resource"]["title"] == "Iter100 Edited"
        assert r.json()["resource"]["tags"] == ["b", "c"]
        # Archive (soft delete)
        r = requests.delete(f"{BASE_URL}/api/aria/resources/{rid}", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        # Not visible by default
        r = requests.get(f"{BASE_URL}/api/aria/resources", headers=admin_headers, timeout=15)
        assert not any(x["id"] == rid for x in r.json()["resources"])
        # Visible with include_archived
        r = requests.get(f"{BASE_URL}/api/aria/resources?include_archived=true", headers=admin_headers, timeout=15)
        assert any(x["id"] == rid and x["archived"] for x in r.json()["resources"])


class TestFileUploadAndServe:
    def test_upload_then_create_then_serve(self, admin_headers, cleanup_iter100):
        # Upload
        fake_pdf = b"%PDF-1.4\nIter100 fake pdf for upload test\n%%EOF"
        files = {"file": ("iter100.pdf", io.BytesIO(fake_pdf), "application/pdf")}
        r = requests.post(
            f"{BASE_URL}/api/aria/resources/upload",
            headers=admin_headers,
            files=files,
            timeout=30,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        file_id = body["file_id"]
        assert body["size"] == len(fake_pdf)

        # Create resource pointing to that file_id
        r = requests.post(
            f"{BASE_URL}/api/aria/resources",
            headers={**admin_headers, "Content-Type": "application/json"},
            json={
                "title": "Iter100 PDF Resource",
                "type": "file",
                "file_id": file_id,
                "file_name": "iter100.pdf",
                "size": len(fake_pdf),
                "category": "one_pager",
            },
            timeout=20,
        )
        assert r.status_code == 200
        res = r.json()["resource"]
        assert res["file_url"].endswith(f"/api/aria/resources/file/{file_id}")

        # Serve — no auth required (resources are linked from emails)
        r = requests.get(f"{BASE_URL}/api/aria/resources/file/{file_id}", timeout=20)
        assert r.status_code == 200
        assert r.content == fake_pdf

    def test_file_endpoint_path_traversal_blocked(self):
        r = requests.get(f"{BASE_URL}/api/aria/resources/file/..%2F..%2Fetc%2Fpasswd", timeout=10)
        assert r.status_code == 404


class TestLeadMatcher:
    def test_match_for_lead_ranks_by_icp_then_tags(self, admin_headers, cleanup_iter100):
        # Create resources with different ICP/tag overlap
        def mk(title, icp_ids, tags):
            return requests.post(
                f"{BASE_URL}/api/aria/resources",
                headers={**admin_headers, "Content-Type": "application/json"},
                json={"title": title, "type": "url", "url": "https://x.com",
                      "target_icp_ids": icp_ids, "tags": tags},
                timeout=20,
            ).json()["resource"]["id"]
        r1 = mk("Iter100 ICP match", ["icp_b2b_founders"], ["hiring"])
        r2 = mk("Iter100 Tag only", [], ["hiring", "saas"])
        r3 = mk("Iter100 Nothing", [], ["unrelated"])

        # Seed a lead with that ICP + matching pain keyword "hiring"
        lid = str(uuid.uuid4())
        leads_col.insert_one({
            "id": lid,
            "tenant_id": "ten_pietential",
            "icp_id": "icp_b2b_founders",
            "industry": "SaaS",
            "pain_point": "We are hiring fast",
            "first_name": "Iter100",
        })
        try:
            r = requests.get(
                f"{BASE_URL}/api/aria/resources/match-for-lead/{lid}?limit=3",
                headers=admin_headers,
                timeout=20,
            )
            assert r.status_code == 200, r.text
            ranked_ids = [x["id"] for x in r.json()["resources"]]
            assert ranked_ids[0] == r1, f"ICP match must rank #1, got {ranked_ids}"
            assert r2 in ranked_ids
            # r3 shouldn't be returned (score 0)
            assert r3 not in ranked_ids
        finally:
            leads_col.delete_one({"id": lid, "tenant_id": "ten_pietential"})

    def test_match_404_when_lead_missing(self, admin_headers):
        r = requests.get(
            f"{BASE_URL}/api/aria/resources/match-for-lead/does_not_exist_iter100",
            headers=admin_headers,
            timeout=15,
        )
        assert r.status_code == 404


class TestAttachCounter:
    def test_attach_increments_send_count(self, admin_headers, cleanup_iter100):
        r = requests.post(
            f"{BASE_URL}/api/aria/resources",
            headers={**admin_headers, "Content-Type": "application/json"},
            json={"title": "Iter100 Attach", "type": "url", "url": "https://x.com"},
            timeout=20,
        )
        rid = r.json()["resource"]["id"]
        for _ in range(3):
            r = requests.post(
                f"{BASE_URL}/api/aria/resources/attach",
                headers={**admin_headers, "Content-Type": "application/json"},
                json={"resource_id": rid},
                timeout=15,
            )
            assert r.status_code == 200
        # Verify counter
        doc = resources_col.find_one({"id": rid}, {"_id": 0})
        assert doc["send_count"] == 3
        assert doc.get("last_used_at")
