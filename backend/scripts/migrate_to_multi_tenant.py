"""Migration: backfill existing single-tenant data into multi-tenant model.

Idempotent — safe to run multiple times. Creates two tenants:
- Demo (ARIA workspace) — owns all legacy collections (leads, campaigns, etc.)
- Pietential — owns all pt_* collections

Memberships:
- admin@demo.com → owner of BOTH (so existing demo super-admin keeps full access)
- sarah@demo.com / james@demo.com → member of Demo only

Marks both tenants as onboarding_completed=true with sane defaults
so existing flows aren't blocked by the onboarding gate.

Run from /app/backend with: python scripts/migrate_to_multi_tenant.py
"""
import os
import sys
from datetime import datetime, timezone

# Allow imports from backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deps import db  # noqa: E402

NOW = datetime.now(timezone.utc).isoformat()

DEMO_TENANT = {
    "id": "ten_demo",
    "name": "GenLeadAI Demo",
    "owner_email": "admin@demo.com",
    "plan": "pro",
    "settings": {},
    "onboarding_completed": True,
    "created_at": NOW,
}

PIETENTIAL_TENANT = {
    "id": "ten_pietential",
    "name": "Pietential",
    "owner_email": "admin@demo.com",
    "plan": "pro",
    "settings": {},
    "onboarding_completed": True,
    "created_at": NOW,
}

DEMO_ONBOARDING = {
    "tenant_id": "ten_demo",
    "business_profile": {
        "business_name": "GenLeadAI",
        "industry": "SaaS",
        "description": "AI Sales Agent for founder-led businesses",
        "primary_market": "B2B",
        "country": "Global",
        "timezone": "UTC",
    },
    "aria_persona": {
        "aria_name": "Aria",
        "tone": "founder_led",
        "language": "English",
        "fallback_behavior": "ask_clarifying",
    },
    "sales_process": {
        "product_description": "AI Sales Agent that captures, qualifies, nurtures, and books calls automatically.",
        "deal_size": "50K-5L",
        "sales_cycle": "1-4 weeks",
        "qualification_criteria": ["budget_confirmed", "decision_maker_identified", "need_established"],
        "pipeline_stages": ["New", "Contacted", "Qualified", "Proposal", "Negotiation", "Won", "Lost"],
    },
    "whatsapp_config": {"provider": "meta", "configured": False},
    "completed_at": NOW,
    "completed_by": "system_migration",
}

PIETENTIAL_ONBOARDING = {
    "tenant_id": "ten_pietential",
    "business_profile": {
        "business_name": "Pietential",
        "industry": "Wellbeing",
        "description": "Wellbeing engagement intelligence platform — qualifies and routes engaged leads.",
        "primary_market": "B2B",
        "country": "Global",
        "timezone": "UTC",
    },
    "aria_persona": {
        "aria_name": "Aria",
        "tone": "consultative",
        "language": "English",
        "fallback_behavior": "escalate_to_human",
    },
    "sales_process": {
        "product_description": "Wellbeing platform with engagement scoring, account cascade, and pause logic.",
        "deal_size": "5L-50L",
        "sales_cycle": "1-3 months",
        "qualification_criteria": ["decision_maker_identified", "timeline_defined", "need_established"],
        "pipeline_stages": ["Cold", "Warm", "Hot", "Engaged", "Session/Pilot"],
    },
    "whatsapp_config": {"provider": "meta", "configured": False},
    "completed_at": NOW,
    "completed_by": "system_migration",
}

# Legacy collections that belong to the Demo (ARIA) tenant
DEMO_COLLECTIONS = [
    "leads", "activities", "campaigns", "pipelines",
    "aria_conversations", "workspace_assets", "aria_settings",
    "onboarding", "follow_ups", "notes", "tasks",
    "aria_sales_assets", "aria_brain", "aria_training",
    "synced_prospects", "automation_rules",
    "saleshandy_state", "lemlist_state",
    "beta_feedback",
]

# Pietential collections (already isolated by name)
PIETENTIAL_COLLECTIONS = [
    "pt_leads", "pt_companies", "pt_events", "pt_tasks", "pt_notes",
    "pt_integrations", "pt_training_signals", "pt_campaigns", "pt_automation_logs",
]


def upsert(col, query, doc):
    col.update_one(query, {"$set": doc}, upsert=True)


def backfill(collection_name: str, tenant_id: str) -> int:
    """Add tenant_id to every doc in the collection that doesn't already have one."""
    if collection_name not in db.list_collection_names():
        return 0
    col = db[collection_name]
    res = col.update_many(
        {"tenant_id": {"$exists": False}},
        {"$set": {"tenant_id": tenant_id}},
    )
    return res.modified_count


def main():
    tenants_col = db["tenants"]
    memberships_col = db["tenant_memberships"]
    onboarding_col = db["onboarding_config"]
    users_col = db["users"]

    print(f"[Migrate] Starting multi-tenant migration at {NOW}")

    # 1. Create tenants
    upsert(tenants_col, {"id": DEMO_TENANT["id"]}, DEMO_TENANT)
    upsert(tenants_col, {"id": PIETENTIAL_TENANT["id"]}, PIETENTIAL_TENANT)
    print(f"[Migrate] Tenants ensured: {DEMO_TENANT['id']}, {PIETENTIAL_TENANT['id']}")

    # 2. Create memberships
    admin_email = "admin@demo.com"
    if users_col.find_one({"email": admin_email}):
        for tid in (DEMO_TENANT["id"], PIETENTIAL_TENANT["id"]):
            upsert(
                memberships_col,
                {"tenant_id": tid, "user_email": admin_email},
                {
                    "id": f"mem_{tid}_{admin_email.replace('@', '_at_')}",
                    "tenant_id": tid,
                    "user_email": admin_email,
                    "role": "owner",
                    "joined_at": NOW,
                },
            )
        print(f"[Migrate] {admin_email} → owner of demo + pietential")

    for email in ("sarah@demo.com", "james@demo.com"):
        if users_col.find_one({"email": email}):
            upsert(
                memberships_col,
                {"tenant_id": DEMO_TENANT["id"], "user_email": email},
                {
                    "id": f"mem_demo_{email.replace('@', '_at_')}",
                    "tenant_id": DEMO_TENANT["id"],
                    "user_email": email,
                    "role": "member",
                    "joined_at": NOW,
                },
            )
            print(f"[Migrate] {email} → member of demo")

    # 3. Onboarding configs (sane defaults)
    upsert(onboarding_col, {"tenant_id": DEMO_TENANT["id"]}, DEMO_ONBOARDING)
    upsert(onboarding_col, {"tenant_id": PIETENTIAL_TENANT["id"]}, PIETENTIAL_ONBOARDING)
    print("[Migrate] Onboarding configs seeded with defaults")

    # 4. Backfill tenant_id on existing collections
    total = 0
    for c in DEMO_COLLECTIONS:
        n = backfill(c, DEMO_TENANT["id"])
        total += n
        if n:
            print(f"[Migrate]   {c}: tagged {n} docs → demo tenant")
    for c in PIETENTIAL_COLLECTIONS:
        n = backfill(c, PIETENTIAL_TENANT["id"])
        total += n
        if n:
            print(f"[Migrate]   {c}: tagged {n} docs → pietential tenant")
    print(f"[Migrate] Backfill complete: {total} docs tagged")

    # Backfill string `id` on leads documents that only have ObjectId _id.
    # Required by compliance + touchpoint engine which look up by `id` field.
    try:
        leads = db["leads"]
        # Use a single update with an aggregation pipeline so it's atomic + fast.
        leads.update_many(
            {"id": {"$exists": False}},
            [{"$set": {"id": {"$toString": "$_id"}}}],
        )
        print("[Migrate] Backfilled leads.id from _id")
    except Exception as _e:
        print(f"[Migrate] leads.id backfill skipped: {_e}")

    print("[Migrate] DONE.")


if __name__ == "__main__":
    main()
