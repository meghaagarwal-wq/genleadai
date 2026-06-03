"""Pytest fixtures shared across the backend test suite.

iter144 — session-scoped teardown that nukes test droppings accumulated
from iter140/141/143 runs:

  • applications  whose `full_name` or `company_name` start with `TEST_`
  • tenants       whose `id` matches the `ws_*` pattern AND was created
                  by `routes/applications.create_workspace` (i.e. has
                  `application_id` set)
  • tenant_memberships, onboarding_config rows pointing at those tenants
  • invitations   tied to those tenants
  • workspace_invites likewise
  • Pietential simulated leads (`@pietential-test.com`) — belt-and-
    braces in case `/_test/cleanup-simulated` was skipped

Runs once at the end of the pytest session, after all tests are done.
Never fails the suite — wraps every Mongo call in try/except.
"""
from __future__ import annotations

import logging
import os
import sys

import pytest

# Make the backend package importable when pytest is run from /app.
_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

logger = logging.getLogger("conftest")


@pytest.fixture(scope="session", autouse=True)
def _purge_test_droppings():
    """Yield first (run the tests), then sweep test artifacts on teardown."""
    yield
    try:
        from deps import db
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[teardown] could not import deps.db: {e}")
        return

    deleted = {"applications": 0, "tenants": 0, "memberships": 0,
               "onboarding_config": 0, "invitations": 0, "workspace_invites": 0,
               "pt_leads_sim": 0, "pt_insights_sim": 0, "prospect_intel_sim": 0}
    try:
        # 1. TEST_-prefixed applications + companies.
        deleted["applications"] = db["applications"].delete_many({
            "$or": [
                {"full_name": {"$regex": "^TEST_"}},
                {"company_name": {"$regex": "^TEST_"}},
            ],
        }).deleted_count

        # 2. ws_*-prefixed tenants spawned by create-workspace tests.
        test_tenants = list(db["tenants"].find(
            {"id": {"$regex": "^ws_"}, "application_id": {"$exists": True}},
            {"_id": 0, "id": 1},
        ))
        tenant_ids = [t["id"] for t in test_tenants]
        if tenant_ids:
            deleted["tenants"] = db["tenants"].delete_many({"id": {"$in": tenant_ids}}).deleted_count
            deleted["memberships"] = db["tenant_memberships"].delete_many({"tenant_id": {"$in": tenant_ids}}).deleted_count
            deleted["onboarding_config"] = db["onboarding_config"].delete_many({"tenant_id": {"$in": tenant_ids}}).deleted_count
            deleted["invitations"] = db["invitations"].delete_many({"tenant_id": {"$in": tenant_ids}}).deleted_count
            deleted["workspace_invites"] = db["workspace_invites"].delete_many({"tenant_id": {"$in": tenant_ids}}).deleted_count

        # 3. Pietential simulated leads (`@pietential-test.com` mirrors the
        #    /_test/simulate endpoint pattern).
        deleted["pt_leads_sim"] = db["pt_leads"].delete_many({
            "tenant_id": "ten_pietential",
            "email": {"$regex": "@pietential-test.com$"},
        }).deleted_count
        deleted["prospect_intel_sim"] = db["prospect_intel"].delete_many({
            "tenant_id": "ten_pietential",
            "enrichment_source": "simulated",
        }).deleted_count
        # Leftover insight cards from cleaned simulated leads — orphans.
        all_pt_lead_ids = {d["id"] for d in db["pt_leads"].find(
            {"tenant_id": "ten_pietential"}, {"_id": 0, "id": 1},
        )}
        orphan_cards = list(db["pt_insights"].find(
            {"tenant_id": "ten_pietential",
             "source": "pietential_engine",
             "lead_id": {"$nin": list(all_pt_lead_ids)}},
            {"_id": 0, "id": 1},
        ))
        if orphan_cards:
            deleted["pt_insights_sim"] = db["pt_insights"].delete_many({
                "id": {"$in": [c["id"] for c in orphan_cards]},
            }).deleted_count
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[teardown] sweep error (non-fatal): {e}")

    total = sum(deleted.values())
    if total > 0:
        print(f"\n[conftest teardown] purged {total} test artifacts: {deleted}")
