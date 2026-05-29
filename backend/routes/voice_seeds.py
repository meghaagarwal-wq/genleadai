"""iter131 — Founder voice training.

Tenant-scoped collection of 3-10 short sample messages (the founder's own
past WhatsApps / emails / LinkedIn DMs). When `compose_message` runs, the
active seeds are stitched into a "TONE EXAMPLES" block in the system
prompt so every draft adopts the founder's voice instead of generic
ARIA.

Endpoints
─────────
  GET    /api/voice-seeds                  — list all seeds for this tenant
  POST   /api/voice-seeds                  — create
  PATCH  /api/voice-seeds/{seed_id}        — update text / channel / active
  DELETE /api/voice-seeds/{seed_id}        — remove
  GET    /api/voice-seeds/preview          — preview the tone signature block
                                              that gets injected into prompts

Collection shape
────────────────
  {
    id: str (uuid hex),
    tenant_id: str,
    channel: 'whatsapp' | 'email' | 'linkedin' | 'any',
    text: str (max 1200 chars),
    label: Optional[str],
    active: bool,
    created_at: iso str,
    updated_at: iso str,
  }
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import db
from routes.tenants import get_active_tenant

router = APIRouter()

voice_seeds_col = db["voice_seeds"]

MAX_SEEDS_PER_TENANT = 10
MAX_TEXT_LEN = 1200
ALLOWED_CHANNELS = {"whatsapp", "email", "linkedin", "any"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _public(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k != "_id"}


# ─── Schemas ────────────────────────────────────────────────────────────
class VoiceSeedCreate(BaseModel):
    channel: str = Field(default="any", description="whatsapp | email | linkedin | any")
    text: str = Field(..., min_length=10, max_length=MAX_TEXT_LEN)
    label: Optional[str] = Field(default=None, max_length=80)
    active: bool = True


class VoiceSeedPatch(BaseModel):
    channel: Optional[str] = None
    text: Optional[str] = Field(default=None, min_length=10, max_length=MAX_TEXT_LEN)
    label: Optional[str] = Field(default=None, max_length=80)
    active: Optional[bool] = None


# ─── Endpoints ──────────────────────────────────────────────────────────
@router.get("/api/voice-seeds")
async def list_seeds(tenant: dict = Depends(get_active_tenant)):
    rows = list(
        voice_seeds_col.find({"tenant_id": tenant["id"]}, {"_id": 0}).sort("created_at", 1)
    )
    return {"seeds": rows, "max_seeds": MAX_SEEDS_PER_TENANT}


@router.post("/api/voice-seeds")
async def create_seed(body: VoiceSeedCreate, tenant: dict = Depends(get_active_tenant)):
    channel = (body.channel or "any").strip().lower()
    if channel not in ALLOWED_CHANNELS:
        raise HTTPException(status_code=400, detail=f"channel must be one of {sorted(ALLOWED_CHANNELS)}")
    existing = voice_seeds_col.count_documents({"tenant_id": tenant["id"]})
    if existing >= MAX_SEEDS_PER_TENANT:
        raise HTTPException(status_code=400, detail=f"Max {MAX_SEEDS_PER_TENANT} seeds per workspace — delete one first.")

    now = _now_iso()
    doc = {
        "id": uuid.uuid4().hex,
        "tenant_id": tenant["id"],
        "channel": channel,
        "text": body.text.strip(),
        "label": (body.label or "").strip() or None,
        "active": bool(body.active),
        "created_at": now,
        "updated_at": now,
    }
    voice_seeds_col.insert_one(doc)
    return _public(doc)


@router.patch("/api/voice-seeds/{seed_id}")
async def patch_seed(seed_id: str, body: VoiceSeedPatch, tenant: dict = Depends(get_active_tenant)):
    existing = voice_seeds_col.find_one({"id": seed_id, "tenant_id": tenant["id"]}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Seed not found")
    update = {"updated_at": _now_iso()}
    if body.channel is not None:
        ch = body.channel.strip().lower()
        if ch not in ALLOWED_CHANNELS:
            raise HTTPException(status_code=400, detail=f"channel must be one of {sorted(ALLOWED_CHANNELS)}")
        update["channel"] = ch
    if body.text is not None:
        update["text"] = body.text.strip()
    if body.label is not None:
        update["label"] = body.label.strip() or None
    if body.active is not None:
        update["active"] = bool(body.active)
    voice_seeds_col.update_one({"id": seed_id, "tenant_id": tenant["id"]}, {"$set": update})
    return _public({**existing, **update})


@router.delete("/api/voice-seeds/{seed_id}")
async def delete_seed(seed_id: str, tenant: dict = Depends(get_active_tenant)):
    result = voice_seeds_col.delete_one({"id": seed_id, "tenant_id": tenant["id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Seed not found")
    return {"deleted": True, "id": seed_id}


@router.get("/api/voice-seeds/preview")
async def preview(channel: str = "any", tenant: dict = Depends(get_active_tenant)):
    """Returns the tone-signature block that gets injected into the
    compose_message system prompt for the given channel. Useful for the
    Voice Training page to show founders exactly what ARIA sees."""
    block = render_tone_block(tenant["id"], channel=channel)
    seeds = active_seeds_for(tenant["id"], channel=channel)
    return {"tone_block": block, "seed_count": len(seeds), "channel": channel}


# ─── Helpers used by intel_service.compose_message ──────────────────────
def active_seeds_for(tenant_id: str, channel: str = "any") -> List[dict]:
    """Return the active seeds that apply to the given channel.

    A seed with channel='any' applies everywhere; channel-specific seeds
    apply only when they match. We cap at 5 to keep the prompt short.
    """
    ch = (channel or "any").strip().lower()
    query = {
        "tenant_id": tenant_id,
        "active": True,
        "$or": [{"channel": ch}, {"channel": "any"}],
    }
    return list(voice_seeds_col.find(query, {"_id": 0}).sort("created_at", 1).limit(5))


def render_tone_block(tenant_id: str, channel: str = "any") -> str:
    """Stitch active seeds into a TONE EXAMPLES block. Returns empty
    string when no seeds exist so the prompt stays clean for new tenants.
    """
    seeds = active_seeds_for(tenant_id, channel=channel)
    if not seeds:
        return ""
    examples = []
    for i, s in enumerate(seeds, 1):
        label = f" ({s['label']})" if s.get("label") else ""
        examples.append(f"Example {i}{label}:\n{s['text'].strip()}")
    return (
        "TONE EXAMPLES — match this voice (cadence, openers, sign-offs, vocabulary). "
        "Do NOT copy the content — only the style.\n\n"
        + "\n\n".join(examples)
        + "\n"
    )
