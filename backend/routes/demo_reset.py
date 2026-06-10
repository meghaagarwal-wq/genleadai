"""ARIA — Demo reset endpoint.

iter149 — Resets the `ten_demo` workspace's iter148 demo seeds back to a
pristine state. Useful for back-to-back live demos: one click, fresh
data, no MongoDB tinkering.

Endpoint
────────
POST /api/demo/reset
    master_admin only (role check on caller).
    Tenant-locked to ten_demo (will refuse to run against any other tenant).

What it does
────────────
1. Deletes every row tagged `seed_source: iter148` in ten_demo across:
   pt_leads, pt_insights, outbound_log, inbound_messages, activities.
2. Re-runs the iter148 seeder so the 6 leads + 3 insight cards + 10
   conversation messages are recreated with fresh timestamps anchored
   to NOW (so the demo always looks "current").
3. Returns a summary of what was reset.

Run via curl
────────────
    curl -X POST $API_URL/api/demo/reset \
        -H "Authorization: Bearer <master_admin_token>"
"""
from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException

from deps import get_current_user, db

router = APIRouter(tags=["iter149-demo-reset"])

DEMO_TENANT = "ten_demo"


@router.post("/api/demo/reset")
async def reset_demo_workspace(current_user: dict = Depends(get_current_user)):
    """Idempotent reset of the ten_demo workspace seeded data.

    Only master_admin can call this. The reset is hard-coded to ten_demo —
    cannot be run against ten_pietential or any other tenant.
    """
    if current_user.get("role") != "master_admin":
        raise HTTPException(status_code=403, detail="master_admin only")

    # ── 1. Purge prior seed rows ─────────────────────────────────────
    purged = {
        "pt_leads":           db["pt_leads"].delete_many({"tenant_id": DEMO_TENANT, "seed_source": "iter148"}).deleted_count,
        "pt_insights":        db["pt_insights"].delete_many({"tenant_id": DEMO_TENANT, "seed_source": "iter148"}).deleted_count,
        "outbound_log":       db["outbound_log"].delete_many({"tenant_id": DEMO_TENANT, "seed_source": "iter148"}).deleted_count,
        "inbound_messages":   db["inbound_messages"].delete_many({"tenant_id": DEMO_TENANT, "seed_source": "iter148"}).deleted_count,
        "activities":         db["activities"].delete_many({"tenant_id": DEMO_TENANT, "seed_source": "iter148"}).deleted_count,
    }

    # ── 2. Re-seed via the iter148 seeder module ─────────────────────
    # Import lazily so the script's __main__ block doesn't fire at app
    # startup. Reuse the dict constants + seed helpers from iter148.
    from scripts.iter148_seed_demo_accounts import (
        seed_b2b_lead, seed_b2c_lead,
        LEAD_SARAH, INSIGHT_SARAH,
        LEAD_ARJUN, INSIGHT_ARJUN,
        LEAD_JAMES, INSIGHT_JAMES,
        PRIYA, PRIYA_MSGS,
        RAHUL, RAHUL_MSGS,
        ANANYA, ANANYA_MSGS,
    )
    # The seed helpers anchor created_at / updated_at to module-level NOW,
    # which is set at import time. Force-re-seed by calling them after a
    # module reload so timestamps re-anchor to the moment of reset.
    import importlib
    import scripts.iter148_seed_demo_accounts as seeder_mod
    importlib.reload(seeder_mod)

    seeder_mod.seed_b2b_lead(seeder_mod.LEAD_SARAH, seeder_mod.INSIGHT_SARAH)
    seeder_mod.seed_b2b_lead(seeder_mod.LEAD_ARJUN, seeder_mod.INSIGHT_ARJUN)
    seeder_mod.seed_b2b_lead(seeder_mod.LEAD_JAMES, seeder_mod.INSIGHT_JAMES)
    seeder_mod.seed_b2c_lead(seeder_mod.PRIYA, seeder_mod.PRIYA_MSGS)
    seeder_mod.seed_b2c_lead(seeder_mod.RAHUL, seeder_mod.RAHUL_MSGS)
    seeder_mod.seed_b2c_lead(seeder_mod.ANANYA, seeder_mod.ANANYA_MSGS)

    # ── 3. Audit trail ────────────────────────────────────────────────
    db["audit_log"].insert_one({
        "tenant_id": DEMO_TENANT,
        "actor_email": current_user.get("email"),
        "action": "demo.reset",
        "metadata": {"purged": purged},
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "ok": True,
        "tenant_id": DEMO_TENANT,
        "purged": purged,
        "reseeded": {
            "b2b_leads": 3,
            "b2c_leads": 3,
            "insight_cards": 3,
            "messages": 10,  # 3 (Priya) + 5 (Rahul) + 2 (Ananya)
        },
        "reset_at": datetime.now(timezone.utc).isoformat(),
        "actor": current_user.get("email"),
    }


@router.get("/api/demo/state")
async def demo_state(current_user: dict = Depends(get_current_user)):
    """Quick read-only health check on the demo seed — useful before
    starting a live demo to confirm the data is present.
    """
    if current_user.get("role") != "master_admin":
        raise HTTPException(status_code=403, detail="master_admin only")
    counts = {
        "pt_leads":         db["pt_leads"].count_documents({"tenant_id": DEMO_TENANT, "seed_source": "iter148"}),
        "pt_insights":      db["pt_insights"].count_documents({"tenant_id": DEMO_TENANT, "seed_source": "iter148"}),
        "outbound_log":     db["outbound_log"].count_documents({"tenant_id": DEMO_TENANT, "seed_source": "iter148"}),
        "inbound_messages": db["inbound_messages"].count_documents({"tenant_id": DEMO_TENANT, "seed_source": "iter148"}),
    }
    oldest = db["pt_leads"].find_one(
        {"tenant_id": DEMO_TENANT, "seed_source": "iter148"},
        {"_id": 0, "created_at": 1},
        sort=[("created_at", 1)],
    )
    return {
        "tenant_id": DEMO_TENANT,
        "counts": counts,
        "fully_seeded": counts["pt_leads"] == 6 and counts["pt_insights"] == 3,
        "oldest_seed_created_at": oldest.get("created_at") if oldest else None,
    }
