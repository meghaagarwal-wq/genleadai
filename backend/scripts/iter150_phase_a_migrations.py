"""iter150 — Phase A migration.

  • Add `mode`, `currency`, `hourly_rate_assumption` to every tenant
  • Ensure indexes on the 3 new dashboard collections
  • Backfill `score_history` from existing pt_leads (one row per lead
    at its current score)

Run: cd /app/backend && python -m scripts.iter150_phase_a_migrations
Idempotent — safe to re-run.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deps import db
from routes.dashboard_data import ensure_indexes, DEFAULT_HOURLY_RATE

NOW = datetime.now(timezone.utc).isoformat()


def backfill_tenant_fields():
    tenants = list(db.tenants.find({}, {"_id": 0, "id": 1, "mode": 1, "currency": 1, "hourly_rate_assumption": 1, "settings": 1}))
    updated = 0
    for t in tenants:
        upd = {}
        if not t.get("mode"):
            upd["mode"] = (t.get("settings") or {}).get("workspace_type") or "hybrid"
        if not t.get("currency"):
            # Pietential default to INR; everyone else USD until set.
            upd["currency"] = "INR" if t.get("id") == "ten_pietential" else "USD"
        if not t.get("hourly_rate_assumption"):
            upd["hourly_rate_assumption"] = DEFAULT_HOURLY_RATE.get(upd.get("currency") or t.get("currency") or "USD", 45)
        if upd:
            upd["updated_at"] = NOW
            db.tenants.update_one({"id": t["id"]}, {"$set": upd})
            updated += 1
    print(f"  ✓ tenant fields backfilled on {updated} of {len(tenants)} tenants")


def backfill_score_history():
    """One snapshot per existing pt_lead at its current score, so the
    Why-Now-Feed has a baseline to diff against. Only inserts if there's
    no existing row for that lead."""
    inserted = 0
    for lead in db.pt_leads.find({}, {"_id": 0, "id": 1, "tenant_id": 1, "score": 1, "created_at": 1}):
        if not lead.get("id"):
            continue
        if db.score_history.find_one({"lead_id": lead["id"]}, {"_id": 1}):
            continue
        db.score_history.insert_one({
            "id": f"sh_init_{lead['id']}",
            "tenant_id": lead.get("tenant_id"),
            "lead_id": lead["id"],
            "prev_score": 0,
            "new_score": int(lead.get("score") or 0),
            "delta": int(lead.get("score") or 0),
            "reason": "backfill_iter150",
            "source": "migration",
            "created_at": lead.get("created_at") or NOW,
        })
        inserted += 1
    print(f"  ✓ score_history backfilled: {inserted} initial rows")


def add_lead_score_delta_fields():
    """Add empty lead_score_delta + next_followup_at slots so the UI doesn't
    have to handle `null` differently from `0`. Cheap one-time set."""
    res = db.pt_leads.update_many(
        {"lead_score_delta": {"$exists": False}},
        {"$set": {"lead_score_delta": 0, "next_followup_at": None}},
    )
    print(f"  ✓ pt_leads lead_score_delta default set on {res.modified_count} rows")


if __name__ == "__main__":
    print(f"iter150 Phase A migrations @ {NOW}")
    print("  → Ensuring indexes on new collections...")
    print("    →", ensure_indexes())
    print("  → Backfilling tenant fields...")
    backfill_tenant_fields()
    print("  → Backfilling pt_leads delta fields...")
    add_lead_score_delta_fields()
    print("  → Backfilling score_history...")
    backfill_score_history()
    print("✅ Phase A migrations complete.")
