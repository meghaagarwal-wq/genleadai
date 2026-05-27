"""Shared Pietential event types — extracted to break the circular
import chain (iter96 code-review fix):

  Old cycle:
    outreach_import.py (module) → integrations_hub.py (module) →
      pietential.py (lazy import) → outreach_import.py (lazy import)

  New graph:
    outreach_import.py → integrations_hub.py → pt_events.py  (one-way)
    pietential.py     → pt_events.py                          (one-way)
    pietential.py     → outreach_import.py (lazy, unchanged)

`pt_events` exposes the LeadEvent pydantic model + `log_event_internal`
helper so integrations_hub can fire scoring events without importing
pietential.py.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException
from pydantic import BaseModel


class LeadEvent(BaseModel):
    """Minimal event payload accepted by the internal log_event helper."""
    lead_email: str
    event_type: str
    payload: Dict[str, Any] = {}


async def log_event_internal(tenant_id: str, event: "LeadEvent") -> dict:
    """Fire a scoring event from a server-side caller (e.g. an inbound webhook
    handler that already validated its signature). Never raises — failures
    are caught and returned so the caller's main flow isn't blocked.

    The implementation lives in `routes.pietential._ingest_event`; we
    import it lazily here so this module stays import-cycle-free.
    """
    from routes.pietential import _ingest_event  # lazy — pt_events MUST not import pietential at module level
    try:
        return _ingest_event(
            event_type=event.event_type,
            lead_lookup={"email": event.lead_email},
            metadata={"raw": event.payload, "tenant_id": tenant_id, "via": "webhook"},
            current_user_email="webhook",
        )
    except HTTPException as e:
        return {"ok": False, "error": e.detail}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}
