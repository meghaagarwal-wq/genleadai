"""Iter105 — P0 fix #2: create production performance indexes.

Run from the backend root:
    python3 -m scripts.create_perf_indexes

Idempotent. Safe to run on every boot — `create_index()` is a no-op if the
index already exists with the same spec. Skips collections that don't exist.
"""
from __future__ import annotations
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import OperationFailure

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deps import db


# (collection, [(field, direction), ...], options dict)
INDEXES = [
    ("workspace_contacts",  [("tenant_id", ASCENDING)],                                  {}),
    ("workspace_contacts",  [("email", ASCENDING)],                                      {}),
    ("workspace_contacts",  [("status", ASCENDING)],                                     {}),
    ("workspace_contacts",  [("tenant_id", ASCENDING), ("email", ASCENDING)],
        {"partialFilterExpression": {"email": {"$type": "string"}},
         "name": "tenant_id_1_email_1"}),

    ("pt_insights",         [("tenant_id", ASCENDING), ("status", ASCENDING)],           {}),
    ("pt_insights",         [("tenant_id", ASCENDING), ("created_at", DESCENDING)],      {}),
    ("pt_insights",         [("snooze_until", ASCENDING), ("status", ASCENDING)],        {}),

    ("pt_leads",            [("tenant_id", ASCENDING)],                                  {}),
    ("pt_leads",            [("insights_enabled", ASCENDING), ("tenant_id", ASCENDING)], {}),

    ("contacts",            [("tenant_id", ASCENDING)],                                  {}),
    ("contacts",            [("email", ASCENDING)],                                      {}),
    ("contacts",            [("status", ASCENDING)],                                     {}),
    # Unique compound — one contact per email per tenant. `partialFilterExpression`
    # so legacy docs without email don't trip the unique constraint.
    ("contacts",            [("tenant_id", ASCENDING), ("email", ASCENDING)],
        {"unique": True,
         "partialFilterExpression": {"email": {"$type": "string"}},
         "name": "tenant_id_1_email_1_unique"}),

    ("leads",               [("tenant_id", ASCENDING)],                                  {}),
    ("leads",               [("status", ASCENDING)],                                     {}),
    ("leads",               [("email", ASCENDING)],                                      {}),
    ("leads",               [("tenant_id", ASCENDING), ("created_at", DESCENDING)],      {}),

    ("aria_conversations",  [("tenant_id", ASCENDING)],                                  {}),
    ("aria_conversations",  [("lead_id", ASCENDING)],                                    {}),
    ("aria_conversations",  [("contact_id", ASCENDING)],                                 {}),

    # Insight cards live under multiple historical names; index whichever exist.
    ("insight_cards",       [("tenant_id", ASCENDING), ("status", ASCENDING)],           {}),
    ("insight_cards",       [("tenant_id", ASCENDING), ("created_at", DESCENDING)],      {}),
    ("pt_insight_cards",    [("tenant_id", ASCENDING), ("status", ASCENDING)],           {}),
    ("pt_insight_cards",    [("tenant_id", ASCENDING), ("created_at", DESCENDING)],      {}),
    ("aria_alerts",         [("tenant_id", ASCENDING), ("status", ASCENDING)],           {}),

    ("audit_log",           [("tenant_id", ASCENDING)],                                  {}),
    ("audit_log",           [("created_at", DESCENDING)],                                {}),
    ("audit_log",           [("tenant_id", ASCENDING), ("created_at", DESCENDING)],      {}),

    ("pixel_events",        [("tenant_id", ASCENDING)],                                  {}),
    ("pixel_events",        [("contact_id", ASCENDING)],                                 {}),

    ("sequence_enrolments", [("tenant_id", ASCENDING)],                                  {}),
    ("sequence_enrolments", [("contact_id", ASCENDING)],                                 {}),

    ("icps",                [("tenant_id", ASCENDING)],                                  {}),
    ("aria_resources",      [("tenant_id", ASCENDING)],                                  {}),
    ("workspace_assets",    [("tenant_id", ASCENDING)],                                  {}),
    ("aria_sales_assets",   [("tenant_id", ASCENDING)],                                  {}),
    ("integration_configs", [("tenant_id", ASCENDING)],                                  {}),
    ("automation_rules",    [("tenant_id", ASCENDING)],                                  {}),
    ("onboarding_config",   [("tenant_id", ASCENDING)],                                  {}),
    ("tenant_memberships",  [("user_email", ASCENDING)],                                 {}),
    ("tenant_memberships",  [("tenant_id", ASCENDING)],                                  {}),
    ("activities",          [("lead_id", ASCENDING)],                                    {}),
    ("activities",          [("tenant_id", ASCENDING)],                                  {}),
]


def main() -> dict:
    created = []
    skipped = []
    errors = []
    existing_collections = set(db.list_collection_names())

    for col_name, keys, opts in INDEXES:
        if col_name not in existing_collections:
            skipped.append(f"{col_name} (collection missing)")
            continue
        try:
            name = db[col_name].create_index(keys, **opts)
            created.append(f"{col_name}.{name}")
        except OperationFailure as e:
            # IndexOptionsConflict (85) or duplicate-name (86) just means it exists
            # in a slightly different shape — keep moving.
            if e.code in (85, 86):
                skipped.append(f"{col_name}.{[k[0] for k in keys]} (exists with different opts)")
            else:
                errors.append(f"{col_name}.{[k[0] for k in keys]} → {e}")
        except Exception as e:
            errors.append(f"{col_name}.{[k[0] for k in keys]} → {e}")

    return {"created": created, "skipped": skipped, "errors": errors}


if __name__ == "__main__":
    result = main()
    print(f"[create_perf_indexes] created={len(result['created'])} skipped={len(result['skipped'])} errors={len(result['errors'])}")
    for line in result["created"]:
        print(f"  + {line}")
    for line in result["skipped"]:
        print(f"  ~ {line}")
    for line in result["errors"]:
        print(f"  ! {line}")
