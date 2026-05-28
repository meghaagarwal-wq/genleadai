"""iter109 Batch 1 backend tests — Section 4 (Train ARIA polish).

Covers:
  - 4a: GET /api/aria/training-profile/completeness returns
        {percent, filled_count, total, missing[], nudge{field,label,section,message}}
  - 4b: POST /api/aria/training-profile/extract-from-document records
        prompt_version='v1' on new uploads AND on cache hits
  - 4c: training_extraction_jobs collection has TTL index
        `ttl_finished_at_30d` on finished_at_dt with expireAfterSeconds=2592000
"""
import os
import io
import time
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASS = "Demo1234!"
TENANT_ID = "ten_demo"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
        timeout=15,
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def headers(admin_token):
    return {
        "Authorization": f"Bearer {admin_token}",
        "X-Tenant-Id": TENANT_ID,
    }


# ───────────────────────── 4a: Completeness endpoint ─────────────────────────
class TestCompleteness:
    def test_completeness_shape(self, headers):
        r = requests.get(
            f"{BASE_URL}/api/aria/training-profile/completeness",
            headers=headers,
            timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()

        # Required top-level fields
        for key in ("percent", "filled_count", "total", "missing"):
            assert key in data, f"missing {key} in completeness response: {data}"

        assert isinstance(data["percent"], int)
        assert 0 <= data["percent"] <= 100
        assert isinstance(data["total"], int) and data["total"] == 9
        assert isinstance(data["filled_count"], int)
        assert 0 <= data["filled_count"] <= data["total"]
        assert isinstance(data["missing"], list)

        # percent derivation matches filled/total
        expected_pct = int(round((data["filled_count"] / data["total"]) * 100))
        assert data["percent"] == expected_pct

    def test_completeness_missing_and_nudge(self, headers):
        r = requests.get(
            f"{BASE_URL}/api/aria/training-profile/completeness",
            headers=headers,
            timeout=15,
        )
        assert r.status_code == 200
        data = r.json()

        # If anything is missing, nudge must be populated; else nudge can be null
        if data["missing"]:
            n = data.get("nudge")
            assert n is not None, "expected nudge when missing > 0"
            for k in ("field", "label", "section", "message"):
                assert k in n, f"nudge missing {k}: {n}"
            assert n["field"] == data["missing"][0]["field"]
            # missing entries themselves should have field/label/section
            for m in data["missing"]:
                for k in ("field", "label", "section"):
                    assert k in m

    def test_completeness_known_fields_present(self, headers):
        r = requests.get(
            f"{BASE_URL}/api/aria/training-profile/completeness",
            headers=headers,
            timeout=15,
        )
        data = r.json()
        all_fields = {m["field"] for m in data["missing"]}
        # The 9 documented checks
        expected_universe = {
            "what_you_sell", "who_you_sell_to", "problem_you_solve",
            "differentiator", "icp_profiles", "qualification_questions",
            "brand_voice_style", "pricing_objection_responses", "calendar_link",
        }
        # missing must be a subset of the documented universe
        assert all_fields.issubset(expected_universe), f"unknown fields in missing[]: {all_fields - expected_universe}"


# ───────────────────────── 4b: prompt_version in cache ─────────────────────
SAMPLE_DOC = (
    b"TEST_iter109 Acme Robotics QA marker.\n"
    b"What we sell: industrial collaborative robot arms with safety vision.\n"
    b"Who we sell to: mid-market manufacturers in automotive parts and electronics assembly.\n"
    b"Problem we solve: chronic labour shortages on repetitive pick-and-place lines.\n"
    b"Differentiator: 90-day ROI guarantee plus an on-site engineer for the first month.\n"
    b"Pricing: 45k USD per arm, financing available, typical 3-arm pilot 135k.\n"
    b"Top objection: cobots break under heavy duty - our arms run 8000 hours MTBF.\n"
    b"ICP: Director of Operations at 200-1500 employee manufacturers, US/EU.\n"
    b"Qualification: How many manual stations? Current throughput target? Existing PLC vendor?\n"
    b"Brand voice: precise, engineer-led, no fluff. Calendar: https://cal.com/acme-robotics/intro\n"
) * 4  # ~3.5 KB — well over the 50-char floor


class TestExtractPromptVersionCache:
    def test_upload_returns_prompt_version_on_completion_or_queued(self, headers):
        files = {"file": ("iter109_qa.txt", io.BytesIO(SAMPLE_DOC), "text/plain")}
        r = requests.post(
            f"{BASE_URL}/api/aria/training-profile/extract-from-document",
            headers={k: v for k, v in headers.items() if k != "Content-Type"},
            files=files,
            timeout=60,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        # On a NEW upload we usually get queued+job_id. On a cache-hit we get cached:true + prompt_version
        if data.get("cached"):
            assert data.get("prompt_version") == "v1", data
        else:
            assert "job_id" in data
            # Poll until done (max ~60s) — best-effort
            job_id = data["job_id"]
            deadline = time.time() + 60
            final = None
            while time.time() < deadline:
                pr = requests.get(
                    f"{BASE_URL}/api/aria/training-profile/extract-job/{job_id}",
                    headers=headers, timeout=10,
                )
                if pr.status_code == 200 and pr.json().get("status") in ("done", "error"):
                    final = pr.json()
                    break
                time.sleep(2)
            assert final is not None, "extraction never finished"
            if final.get("status") == "done":
                assert final.get("prompt_version") == "v1", f"prompt_version missing on done result: {final}"

    def test_second_upload_is_cached_with_prompt_version(self, headers):
        # First call (may have populated cache via previous test); call again
        for _ in range(2):
            files = {"file": ("iter109_qa.txt", io.BytesIO(SAMPLE_DOC), "text/plain")}
            r = requests.post(
                f"{BASE_URL}/api/aria/training-profile/extract-from-document",
                headers={k: v for k, v in headers.items() if k != "Content-Type"},
                files=files,
                timeout=60,
            )
            assert r.status_code == 200, r.text
            data = r.json()
            if data.get("cached"):
                assert data["status"] == "done"
                assert data.get("prompt_version") == "v1", f"expected prompt_version=v1 in cached response, got: {data}"
                return
            # Not cached yet — wait for job to finish then retry
            job_id = data.get("job_id")
            if job_id:
                deadline = time.time() + 90
                while time.time() < deadline:
                    pr = requests.get(
                        f"{BASE_URL}/api/aria/training-profile/extract-job/{job_id}",
                        headers=headers, timeout=10,
                    )
                    if pr.status_code == 200 and pr.json().get("status") in ("done", "error"):
                        break
                    time.sleep(2)
        pytest.fail("second upload did not return cached:true after waiting for job to finish")


# ───────────────────────── 4c: TTL index on finished_at_dt ─────────────────────
class TestTTLIndex:
    def test_ttl_index_exists(self):
        client = MongoClient(MONGO_URL)
        try:
            db = client[DB_NAME]
            indexes = list(db["training_extraction_jobs"].list_indexes())
            names = {ix["name"]: ix for ix in indexes}
            assert "ttl_finished_at_30d" in names, f"TTL index missing. Got: {list(names.keys())}"
            ix = names["ttl_finished_at_30d"]
            # expireAfterSeconds must be 30 days
            assert ix.get("expireAfterSeconds") == 30 * 24 * 60 * 60, ix
            # key must include finished_at_dt
            key_fields = dict(ix.get("key") or {})
            assert "finished_at_dt" in key_fields, ix
        finally:
            client.close()
