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
    "settings": {"workspace_type": "hybrid"},
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
    """Idempotent upsert: only sets fields on INSERT, never overwrites
    existing tenants. Use $set explicitly elsewhere for forced updates."""
    col.update_one(query, {"$setOnInsert": doc}, upsert=True)


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

    # 1b. Default workspace_type — iter92 v2 master prompt schema.
    # PART E (v3.0): Pietential is B2B Instinct mode (was hybrid pre-iter95).
    tenants_col.update_one(
        {"id": "ten_pietential", "settings.workspace_type": {"$exists": False}},
        {"$set": {"settings.workspace_type": "b2b"}},
    )
    tenants_col.update_one(
        {"id": "ten_demo", "settings.workspace_type": {"$exists": False}},
        {"$set": {"settings.workspace_type": "hybrid"}},
    )
    # Any other tenants: default to hybrid (safest — shows all sections).
    tenants_col.update_many(
        {"settings.workspace_type": {"$exists": False}},
        {"$set": {"settings.workspace_type": "hybrid"}},
    )
    print("[Migrate] workspace_type defaulted (Pietential=b2b, others=hybrid)")

    # 1c. PART E v3.0 — Pre-seed 4 Pietential ICPs (idempotent: by label).
    icps_col = db["icps"]
    PIETENTIAL_ICPS = [
        {
            "id": "icp_pt_chro_enterprise",
            "tenant_id": "ten_pietential",
            "label": "CHRO — Enterprise",
            "industry": "HR Tech / Future of Work",
            "title_targets": ["CHRO", "Chief People Officer", "Chief HR Officer"],
            "company_size": "500+ employees",
            "geography": "USA, EU, India",
            "deal_size": "$80k-300k/year",
            "pain_point": "Disengaged senior leaders, low retention, expensive talent ops",
            "value_prop": "AI-driven engagement intelligence + executive HR workflows",
            "tone": "Sharp, peer-to-peer, no fluff",
            "created_at": NOW,
            "updated_at": NOW,
        },
        {
            "id": "icp_pt_cfo_midmarket",
            "tenant_id": "ten_pietential",
            "label": "CFO — Mid-Market SaaS",
            "industry": "SaaS",
            "title_targets": ["CFO", "Chief Financial Officer", "VP Finance"],
            "company_size": "100-500 employees",
            "geography": "USA, EU",
            "deal_size": "$40k-120k/year",
            "pain_point": "Workforce cost is largest line item with zero visibility into engagement ROI",
            "value_prop": "Quantify the cost of disengagement, automate HR ops, reduce attrition spend",
            "tone": "Numbers-first, ROI-led",
            "created_at": NOW,
            "updated_at": NOW,
        },
        {
            "id": "icp_pt_people_analytics",
            "tenant_id": "ten_pietential",
            "label": "People Analytics Leader — Enterprise",
            "industry": "Enterprise HR",
            "title_targets": ["Head of People Analytics", "Director People Analytics", "VP People Analytics"],
            "company_size": "1000+ employees",
            "geography": "USA, EU",
            "deal_size": "$60k-200k/year",
            "pain_point": "Manual engagement reporting, no real-time signals, reports to CHRO with stale data",
            "value_prop": "Real-time engagement signals + auto-generated executive reports",
            "tone": "Data-driven, technical",
            "created_at": NOW,
            "updated_at": NOW,
        },
        {
            "id": "icp_pt_vp_people_growth",
            "tenant_id": "ten_pietential",
            "label": "VP People / Head of HR — Growth-Stage",
            "industry": "Growth-stage SaaS / Series B+",
            "title_targets": ["VP People", "VP HR", "Head of HR", "Director of People"],
            "company_size": "50-250 employees",
            "geography": "USA, EU, India",
            "deal_size": "$20k-60k/year",
            "pain_point": "Scaling team fast, engagement dropping, no time for manual surveys",
            "value_prop": "AI-powered pulse + automated coaching nudges to managers",
            "tone": "Warm, fast-moving, founder-aware",
            "created_at": NOW,
            "updated_at": NOW,
        },
    ]
    seeded_icps = 0
    for icp in PIETENTIAL_ICPS:
        existing = icps_col.find_one({"tenant_id": "ten_pietential", "label": icp["label"]})
        if not existing:
            icps_col.insert_one(icp.copy())
            seeded_icps += 1
    if seeded_icps:
        print(f"[Migrate] Pietential ICPs seeded: {seeded_icps} new (PART E v3.0)")

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

    # 2b. Pietential workspace owner (Megha) — idempotent seed.
    # Production environments don't carry over the preview DB, so we
    # provision the account here on every startup. Password is sourced
    # from env (PIETENTIAL_OWNER_PASSWORD) with a documented default to
    # keep onboarding zero-friction. If the user already exists, we never
    # touch their password — they may have rotated it.
    try:
        import uuid as _uuid
        from deps import get_password_hash as _hash

        pt_email = "megha@contentvista.com"
        pt_default_password = os.environ.get("PIETENTIAL_OWNER_PASSWORD", "Piet-4vRQ-lDa2-ttcO")
        existing = users_col.find_one({"email": pt_email})
        if not existing:
            users_col.insert_one({
                "id": f"usr_{_uuid.uuid4().hex[:12]}",
                "email": pt_email,
                "name": "Megha Agarwal",
                "full_name": "Megha Agarwal",
                "role": "pietential_owner",
                "tenant_id": PIETENTIAL_TENANT["id"],
                "is_active": True,
                "password_hash": _hash(pt_default_password),
                "created_at": NOW,
            })
            print(f"[Migrate] {pt_email} → provisioned as pietential_owner")
        else:
            # Backfill missing fields without overwriting the password.
            patch = {}
            if not existing.get("role"):
                patch["role"] = "pietential_owner"
            if not existing.get("tenant_id"):
                patch["tenant_id"] = PIETENTIAL_TENANT["id"]
            if existing.get("is_active") is None:
                patch["is_active"] = True
            if patch:
                users_col.update_one({"email": pt_email}, {"$set": patch})

        # Ensure owner membership exists (idempotent)
        upsert(
            memberships_col,
            {"tenant_id": PIETENTIAL_TENANT["id"], "user_email": pt_email},
            {
                "id": f"mem_pt_{pt_email.replace('@', '_at_').replace('.', '_')}",
                "tenant_id": PIETENTIAL_TENANT["id"],
                "user_email": pt_email,
                "role": "owner",
                "joined_at": NOW,
            },
        )
    except Exception as _pt_e:
        print(f"[Migrate] Pietential owner seed skipped: {_pt_e}")

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
