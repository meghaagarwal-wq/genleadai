"""Lead channel touch tracking (iter158 — Phase B Step 4).

A single helper that registers a channel touch on a lead's
`source_channels` array. Used by outbound + inbound flows so the
Multi-touch Leads chart on the B2C dashboard reflects real cross-channel
reach.

Idempotent via MongoDB `$addToSet`.
"""
from __future__ import annotations

from typing import Optional

from deps import db

_pt_leads_col = db["pt_leads"]
_leads_col = db["leads"]


def register_channel_touch(tenant_id: str, lead_id: Optional[str], channel: Optional[str]) -> None:
    """Append `channel` to the lead's `source_channels` array (dedup'd).
    No-op when any of the three args is falsy. Updates BOTH pt_leads and
    legacy leads collection so the demo dashboards remain consistent."""
    if not tenant_id or not lead_id or not channel:
        return
    ch = str(channel).strip().lower()
    if not ch:
        return
    query = {"tenant_id": tenant_id, "id": lead_id}
    update = {"$addToSet": {"source_channels": ch}}
    _pt_leads_col.update_one(query, update)
    _leads_col.update_one(query, update)
