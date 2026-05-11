"""Touchpoint mapping endpoints for Aria onboarding Step 3B and beyond.

Read-only template library + per-tenant active map storage. Execution engine
(Phase B) will read from `workspace_touchpoint_maps` and instantiate
`lead_touchpoint_log` rows on lead create.
"""
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import db, get_current_user
from routes.tenants import get_active_tenant
from touchpoint_templates_seed import TEMPLATES, select_template

router = APIRouter(prefix="/api/touchpoints", tags=["touchpoints"])

templates_col = db["touchpoint_templates"]
maps_col = db["workspace_touchpoint_maps"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seed_templates_if_missing() -> None:
    """Idempotently seed the 8 universal templates on first read.
    Cheap upsert — runs at most once per process per template."""
    for t in TEMPLATES:
        templates_col.update_one(
            {"id": t["id"]},
            {"$set": {**t, "seeded_at": _now()}},
            upsert=True,
        )


# Run once at import (server startup picks this up via include_router)
_seed_templates_if_missing()


# ─── Models ──────────────────────────────────────────────────────────────────
ALLOWED_CHANNELS = {"whatsapp", "email", "call_reminder", "linkedin_nudge"}
ALLOWED_ROLES = {"autonomous", "alert_human"}
ALLOWED_TYPES = {
    "intro", "qualifier", "value_drop", "value_add", "follow_up",
    "social_proof", "soft_cta", "budget_probe", "meeting_cta",
    "human_escalation", "re_engagement", "urgency", "closure",
}


class Touchpoint(BaseModel):
    index: int
    day: float = Field(ge=0)
    hour: int = Field(ge=0, le=23)
    channel: str
    message_type: str
    aria_role: str
    trigger: Optional[str] = ""
    message_template: str


class SaveMapPayload(BaseModel):
    template_id: Optional[str] = None
    is_customised: bool = False
    touchpoints: List[Touchpoint]


def _validate_touchpoints(items: List[Touchpoint]) -> None:
    if not items:
        raise HTTPException(status_code=400, detail="At least one touchpoint required")
    if len(items) > 30:
        raise HTTPException(status_code=400, detail="Max 30 touchpoints per map")
    for t in items:
        if t.channel not in ALLOWED_CHANNELS:
            raise HTTPException(status_code=400, detail=f"Invalid channel '{t.channel}'")
        if t.aria_role not in ALLOWED_ROLES:
            raise HTTPException(status_code=400, detail=f"Invalid aria_role '{t.aria_role}'")
        if t.message_type not in ALLOWED_TYPES:
            raise HTTPException(status_code=400, detail=f"Invalid message_type '{t.message_type}'")
        if not t.message_template.strip():
            raise HTTPException(status_code=400, detail="message_template cannot be empty")


# ─── Endpoints ───────────────────────────────────────────────────────────────
@router.get("/templates")
async def list_templates(_: dict = Depends(get_current_user)):
    """Return all seeded universal templates (read-only library)."""
    rows = list(templates_col.find({}, {"_id": 0}).sort("id", 1))
    return {"templates": rows}


@router.get("/templates/{template_id}")
async def get_template(template_id: str, _: dict = Depends(get_current_user)):
    t = templates_col.find_one({"id": template_id}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    return t


@router.get("/auto-select")
async def auto_select(tenant: dict = Depends(get_active_tenant)):
    """Return the best-fit template based on the tenant's onboarding answers.

    Used by Step 3B to render the auto-generated journey before the user
    decides whether to accept or customise.
    """
    onboarding_col = db["onboarding_config"]
    cfg = onboarding_col.find_one({"tenant_id": tenant["id"]}, {"_id": 0}) or {}
    selected = select_template(cfg)
    return selected


@router.get("/map")
async def get_map(tenant: dict = Depends(get_active_tenant)):
    """Get the active tenant's saved touchpoint map (or null if not set)."""
    row = maps_col.find_one({"tenant_id": tenant["id"]}, {"_id": 0})
    return {"map": row}


@router.post("/map")
async def save_map(payload: SaveMapPayload, tenant: dict = Depends(get_active_tenant), current_user: dict = Depends(get_current_user)):
    """Save (or replace) the active tenant's touchpoint map.

    Owner/admin only. Used by both 'Looks good — use this' and 'Save my custom
    journey' flows.
    """
    if tenant.get("_member_role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")
    _validate_touchpoints(payload.touchpoints)

    # Re-index touchpoints to ensure they are 0..n-1 contiguous regardless of
    # what the client sent (after drag-reorder etc.)
    cleaned = []
    for i, t in enumerate(payload.touchpoints):
        cleaned.append({
            "index": i,
            "day": float(t.day),
            "hour": int(t.hour),
            "channel": t.channel,
            "message_type": t.message_type,
            "aria_role": t.aria_role,
            "trigger": (t.trigger or "").strip(),
            "message_template": t.message_template.strip(),
        })

    template_id = payload.template_id or "tpl_standard"
    template = templates_col.find_one({"id": template_id}, {"_id": 0, "name": 1, "duration_days": 1})

    doc = {
        "tenant_id": tenant["id"],
        "template_id": template_id,
        "template_name": (template or {}).get("name"),
        "is_customised": bool(payload.is_customised),
        "touchpoints": cleaned,
        "touchpoint_count": len(cleaned),
        "duration_days": (template or {}).get("duration_days"),
        "saved_by": current_user.get("email"),
        "updated_at": _now(),
    }
    existing = maps_col.find_one({"tenant_id": tenant["id"]}, {"_id": 0, "created_at": 1})
    if existing:
        doc["created_at"] = existing.get("created_at") or _now()
    else:
        doc["created_at"] = _now()

    maps_col.update_one(
        {"tenant_id": tenant["id"]},
        {"$set": doc},
        upsert=True,
    )
    return {"map": doc}


@router.post("/map/reset")
async def reset_map(tenant: dict = Depends(get_active_tenant), current_user: dict = Depends(get_current_user)):
    """Reset the tenant's map to the auto-recommended template — discards any
    customisations and re-selects from current onboarding answers."""
    if tenant.get("_member_role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")
    onboarding_col = db["onboarding_config"]
    cfg = onboarding_col.find_one({"tenant_id": tenant["id"]}, {"_id": 0}) or {}
    selected = select_template(cfg)
    doc = {
        "tenant_id": tenant["id"],
        "template_id": selected["id"],
        "template_name": selected.get("name"),
        "is_customised": False,
        "touchpoints": selected["touchpoints"],
        "touchpoint_count": len(selected["touchpoints"]),
        "duration_days": selected.get("duration_days"),
        "saved_by": current_user.get("email"),
        "updated_at": _now(),
    }
    existing = maps_col.find_one({"tenant_id": tenant["id"]}, {"_id": 0, "created_at": 1})
    doc["created_at"] = (existing or {}).get("created_at") or _now()
    maps_col.update_one(
        {"tenant_id": tenant["id"]},
        {"$set": doc},
        upsert=True,
    )
    return {"map": doc, "selection": selected.get("selection")}


@router.delete("/map")
async def clear_map(tenant: dict = Depends(get_active_tenant)):
    """Clear the saved map. Aria falls back to no journey for new leads."""
    if tenant.get("_member_role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")
    maps_col.delete_one({"tenant_id": tenant["id"]})
    return {"status": "ok"}
