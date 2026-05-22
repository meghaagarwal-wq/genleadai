"""Iter79 — S6: 'Suggested Asset' surface.

Routes are added on the shared aria-agent router. For a given lead +
recent message body, returns which workspace asset(s) Aria would lean on
(objection_response / pricing_doc / case_study). Founders see this in the
Lead Detail / Aria Read panel so they know *why* Aria phrased a reply a
certain way.
"""
from ._shared import (
    router, leads_collection, db, get_current_user,
    get_relevant_assets_block,   # noqa: F401  — re-used for parity
)
from fastapi import Depends, HTTPException
from typing import Optional


def _last_inbound_text(tid: str, lead_id: str) -> str:
    """Pull the most-recent inbound message from this lead."""
    aria = db["aria_conversations"].find_one(
        {"tenant_id": tid, "lead_id": lead_id},
        sort=[("updated_at", -1)],
    )
    if aria:
        for msg in reversed(aria.get("messages") or []):
            if msg.get("direction") in ("inbound", "incoming") or msg.get("from") in ("lead", "contact"):
                return (msg.get("text") or msg.get("body") or "").strip()
    # Fall back to lead notes
    lead = leads_collection.find_one({"id": lead_id, "tenant_id": tid}) or {}
    return (lead.get("last_inbound_text") or lead.get("notes") or "").strip()


_TRIGGERS = {
    "objection_response": ["objection", "concern", "worried", "not sure", "expensive", "competitor", "but ", "however", "issue"],
    "pricing_doc":       ["price", "pricing", "cost", "how much", "fee", "rate", "discount", "quote"],
    "case_study":        ["proof", "case study", "example", "customer", "success", "results", "reference"],
}


def _suggest_assets(tid: str, query: str, max_n: int = 3) -> list[dict]:
    q = (query or "").lower()
    if not tid:
        return []
    cursor = db["workspace_assets"].find(
        {"tenant_id": tid, "asset_type": {"$in": list(_TRIGGERS.keys())}},
        {"_id": 0, "id": 1, "name": 1, "asset_type": 1, "content": 1, "tags": 1, "use_count": 1},
    )
    matched: list[dict] = []
    for d in cursor:
        kw = _TRIGGERS.get(d.get("asset_type"), [])
        if not q:
            matched.append({**d, "match_reason": "general fallback"})
            continue
        hit = next((k for k in kw if k in q), None)
        if hit:
            matched.append({**d, "match_reason": f"matched keyword '{hit}'"})
    matched.sort(key=lambda x: x.get("use_count", 0), reverse=True)
    return matched[:max_n]


@router.get("/suggested-assets/{lead_id}")
async def suggested_assets_for_lead(
    lead_id: str,
    q: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Return up to 3 workspace assets Aria would surface for this lead given
    the most recent inbound message (or the `q` query override)."""
    tid = current_user.get("tenant_id") or current_user.get("active_tenant_id")
    if not tid:
        raise HTTPException(status_code=400, detail="no_active_tenant")
    lead = leads_collection.find_one({"id": lead_id, "tenant_id": tid}, {"_id": 0, "name": 1, "first_name": 1})
    if not lead:
        # Tolerate ObjectId-style lookup too.
        try:
            from bson import ObjectId
            lead = leads_collection.find_one({"_id": ObjectId(lead_id), "tenant_id": tid}, {"_id": 0, "name": 1, "first_name": 1})
        except Exception:
            lead = None
    if not lead:
        raise HTTPException(status_code=404, detail="lead_not_found")

    query = q if q is not None else _last_inbound_text(tid, lead_id)
    suggested = _suggest_assets(tid, query)
    return {
        "lead_id": lead_id,
        "query": query[:300] if query else "",
        "suggested": suggested,
        "count": len(suggested),
    }
