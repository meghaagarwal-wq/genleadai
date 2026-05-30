"""ARIA — 32-Touchpoint Journey Builder routes.

Provides CRUD over the per-workspace `journey_touchpoints` collection plus
a Claude-powered generator that synthesises a full 32-step sequence from
the workspace training profile.

Endpoints (all tenant-scoped via `get_active_tenant`)
─────────────────────────────────────────────────────
  GET    /api/journey/touchpoints                 — list, ordered
  POST   /api/journey/touchpoints                 — create one
  PATCH  /api/journey/touchpoints/{id}            — edit fields
  DELETE /api/journey/touchpoints/{id}            — remove
  POST   /api/journey/touchpoints/reorder         — bulk reorder
  POST   /api/journey/generate                    — kick off async job, returns {job_id}
  GET    /api/journey/generate/job/{job_id}       — poll job status (iter136 — added)
  POST   /api/journey/touchpoints/{id}/regenerate — regen a single touchpoint

Document shape
──────────────
    {
      id, tenant_id, number, channel, timing, message_body, goal,
      conditional_logic, created_at, updated_at, generated_by
    }
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import db
from routes.tenants import get_active_tenant
from services.claude_service import claude_call, TaskType, ClaudeServiceError

logger = logging.getLogger("journey")
router = APIRouter(prefix="/api/journey", tags=["journey"])

_touchpoints_col = db["journey_touchpoints"]
_touchpoints_col.create_index([("tenant_id", 1), ("number", 1)])

# iter136 — async job tracker for /generate so we never hit the 60s gateway ceiling.
# iter138 — added expires_at TTL field (7 days) so jobs auto-purge.
_generate_jobs_col = db["journey_generate_jobs"]
_generate_jobs_col.create_index([("tenant_id", 1), ("created_at", -1)])
_generate_jobs_col.create_index("expires_at", expireAfterSeconds=0)

_ALLOWED_CHANNELS = {"whatsapp", "email", "linkedin", "sms", "call"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _doc_to_public(d: dict) -> dict:
    d.pop("_id", None)
    return d


# ─── Models ─────────────────────────────────────────────────────────────
class TouchpointIn(BaseModel):
    number: int = Field(..., ge=1, le=64)
    channel: str
    timing: str = ""
    message_body: str = ""
    goal: str = ""
    conditional_logic: str = ""


class TouchpointPatch(BaseModel):
    number: Optional[int] = None
    channel: Optional[str] = None
    timing: Optional[str] = None
    message_body: Optional[str] = None
    goal: Optional[str] = None
    conditional_logic: Optional[str] = None


class ReorderItem(BaseModel):
    id: str
    number: int


class ReorderIn(BaseModel):
    order: List[ReorderItem]


class GenerateIn(BaseModel):
    count: int = 32
    replace: bool = True


# ─── List / Create / Patch / Delete ─────────────────────────────────────
@router.get("/touchpoints")
async def list_touchpoints(tenant: dict = Depends(get_active_tenant)):
    rows = list(_touchpoints_col.find({"tenant_id": tenant["id"]}, {"_id": 0}).sort("number", 1))
    return {"touchpoints": rows, "count": len(rows)}


@router.post("/touchpoints")
async def create_touchpoint(payload: TouchpointIn, tenant: dict = Depends(get_active_tenant)):
    if payload.channel not in _ALLOWED_CHANNELS:
        raise HTTPException(400, f"channel must be one of {sorted(_ALLOWED_CHANNELS)}")
    doc = {
        "id": f"tp_{uuid.uuid4().hex[:12]}",
        "tenant_id": tenant["id"],
        "number": payload.number,
        "channel": payload.channel,
        "timing": payload.timing,
        "message_body": payload.message_body,
        "goal": payload.goal,
        "conditional_logic": payload.conditional_logic,
        "created_at": _now(),
        "updated_at": _now(),
        "generated_by": "manual",
    }
    _touchpoints_col.insert_one(dict(doc))
    return _doc_to_public(doc)


@router.patch("/touchpoints/{tp_id}")
async def patch_touchpoint(tp_id: str, payload: TouchpointPatch, tenant: dict = Depends(get_active_tenant)):
    existing = _touchpoints_col.find_one({"tenant_id": tenant["id"], "id": tp_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Touchpoint not found")
    update = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if "channel" in update and update["channel"] not in _ALLOWED_CHANNELS:
        raise HTTPException(400, f"channel must be one of {sorted(_ALLOWED_CHANNELS)}")
    update["updated_at"] = _now()
    _touchpoints_col.update_one({"tenant_id": tenant["id"], "id": tp_id}, {"$set": update})
    return _doc_to_public(_touchpoints_col.find_one({"tenant_id": tenant["id"], "id": tp_id}, {"_id": 0}))


@router.delete("/touchpoints/{tp_id}")
async def delete_touchpoint(tp_id: str, tenant: dict = Depends(get_active_tenant)):
    r = _touchpoints_col.delete_one({"tenant_id": tenant["id"], "id": tp_id})
    if not r.deleted_count:
        raise HTTPException(404, "Touchpoint not found")
    return {"status": "ok"}


@router.post("/touchpoints/reorder")
async def reorder_touchpoints(payload: ReorderIn, tenant: dict = Depends(get_active_tenant)):
    for item in payload.order:
        _touchpoints_col.update_one(
            {"tenant_id": tenant["id"], "id": item.id},
            {"$set": {"number": item.number, "updated_at": _now()}},
        )
    rows = list(_touchpoints_col.find({"tenant_id": tenant["id"]}, {"_id": 0}).sort("number", 1))
    return {"touchpoints": rows}


# ─── Claude generation ──────────────────────────────────────────────────
def _profile_summary(tenant_id: str) -> str:
    """Pull the assembled ARIA training profile data dict into a compact
    text summary that Claude can use as the brand voice + ICP grounding."""
    tdoc = db["tenants"].find_one({"id": tenant_id}, {"_id": 0, "settings": 1}) or {}
    prof = ((tdoc.get("settings") or {}).get("aria_training_profile") or {}).get("data") or {}
    bits = []
    if prof.get("what_you_sell"):       bits.append(f"What we sell: {prof['what_you_sell']}")
    if prof.get("who_you_sell_to"):     bits.append(f"Buyer: {prof['who_you_sell_to']}")
    if prof.get("problem_you_solve"):   bits.append(f"Problem solved: {prof['problem_you_solve']}")
    if prof.get("differentiator"):      bits.append(f"Differentiator: {prof['differentiator']}")
    if prof.get("brand_voice_style"):   bits.append(f"Brand voice: {prof['brand_voice_style']}")
    if prof.get("custom_tone_instructions"): bits.append(f"Tone notes: {prof['custom_tone_instructions']}")
    icps = prof.get("icp_profiles") or []
    if icps:
        first = icps[0]
        bits.append(f"Primary ICP: {first.get('icp_name','')} · titles {first.get('target_titles_or_roles',[])} · industries {first.get('target_industries',[])}")
    if prof.get("qualified_criteria"):
        bits.append(f"Qualified criteria: {prof['qualified_criteria'][:6]}")
    return "\n".join(bits) or "No training profile yet — generate a generic founder-led sequence."


@router.post("/generate")
async def generate_journey(payload: GenerateIn, tenant: dict = Depends(get_active_tenant)):
    """iter136 — Convert to async-job pattern.

    Returns {job_id, eta_seconds} immediately. The actual Claude call runs
    in a background asyncio task and writes results to journey_generate_jobs.
    Client polls GET /api/journey/generate/job/{job_id} until status='done'
    or 'failed'.
    """
    if payload.count < 1 or payload.count > 64:
        raise HTTPException(400, "count must be between 1 and 64")

    job_id = f"jgj_{uuid.uuid4().hex[:14]}"
    now = _now()
    eta = max(15, payload.count * 2)  # roughly 2s/touchpoint

    _generate_jobs_col.insert_one({
        "job_id": job_id,
        "tenant_id": tenant["id"],
        "status": "queued",
        "phase": "queued",
        "count_requested": payload.count,
        "replace": payload.replace,
        "created_at": now,
        "updated_at": now,
        # iter138 — TTL field (BSON Date). Mongo auto-purges after 7d.
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
        "eta_seconds": eta,
        "result": None,
        "error": None,
    })

    asyncio.create_task(_run_generate_job(job_id, tenant["id"], payload.count, payload.replace))

    return {
        "job_id": job_id,
        "status": "queued",
        "eta_seconds": eta,
        "hint": f"Generating {payload.count} touchpoints via Claude — poll /api/journey/generate/job/{job_id} every 2-3s.",
    }


@router.get("/generate/job/{job_id}")
async def get_generate_job(job_id: str, tenant: dict = Depends(get_active_tenant)):
    job = _generate_jobs_col.find_one(
        {"job_id": job_id, "tenant_id": tenant["id"]},
        {"_id": 0},
    )
    if not job:
        raise HTTPException(404, "Job not found")
    # Compute elapsed for the UI progress bar.
    try:
        created = datetime.fromisoformat(job["created_at"])
        elapsed = (datetime.now(timezone.utc) - created).total_seconds()
        job["elapsed_seconds"] = round(elapsed, 1)
        job["slow_warn"] = elapsed > 90 and job["status"] not in ("done", "failed")
    except Exception:
        job["elapsed_seconds"] = 0
        job["slow_warn"] = False
    return job


async def _run_generate_job(job_id: str, tenant_id: str, count: int, replace: bool):
    """Background worker — does the actual Claude call + Mongo writes."""
    def _patch(**kw):
        kw["updated_at"] = _now()
        _generate_jobs_col.update_one({"job_id": job_id}, {"$set": kw})

    try:
        _patch(status="running", phase="building_prompt")
        profile = _profile_summary(tenant_id)

        system = (
            "You are ARIA, an expert B2B/B2C outreach sequence designer. Output STRICT JSON only — "
            "no preamble, no markdown fences. Schema: "
            '{"touchpoints":[{"number":int,"channel":"whatsapp|email|linkedin|sms|call",'
            '"timing":"Day N" OR "Day N if no reply" OR "Day N if opened but not replied",'
            '"message_body":"<150 words in the workspace brand voice>",'
            '"goal":"<1-line goal>","conditional_logic":"<plain English: if X → action>"}]}\n'
            "Rules: every touchpoint number is unique and sequential 1..N. Mix channels — "
            "weight whatsapp/email/linkedin highest, allow occasional sms/call. Every "
            "message_body is under 150 words, addressed to {{first_name}}, references the "
            "buyer's problem, and ends with one specific question or CTA. conditional_logic "
            "must include at least one branch (skip/end/loop) for the sequence to feel adaptive."
        )
        prompt = (
            f"Generate a {count}-step outbound journey for this workspace.\n\n"
            f"WORKSPACE PROFILE:\n{profile}\n\n"
            f"Return exactly {count} touchpoints, numbered 1..{count}."
        )

        _patch(phase="claude_generating")

        try:
            data = await claude_call(
                task_type=TaskType.TOUCHPOINT_GENERATION,
                system=system,
                prompt=prompt,
                tenant_id=tenant_id,
                session_id=f"journey-gen-{tenant_id}",
                response_format="json",
                sanitize_user_input=True,
            )
        except ClaudeServiceError as e:
            _patch(status="failed", phase="failed", error=f"Claude call failed: {str(e)[:200]}")
            return

        raw = data.get("touchpoints") if isinstance(data, dict) else data
        if not isinstance(raw, list) or not raw:
            _patch(status="failed", phase="failed", error="Claude returned no touchpoints")
            return

        _patch(phase="persisting")

        if replace:
            _touchpoints_col.delete_many({"tenant_id": tenant_id})

        inserted: List[dict] = []
        now = _now()
        for i, t in enumerate(raw[:count], start=1):
            ch = str(t.get("channel") or "email").lower().strip()
            if ch not in _ALLOWED_CHANNELS:
                ch = "email"
            doc = {
                "id": f"tp_{uuid.uuid4().hex[:12]}",
                "tenant_id": tenant_id,
                "number": int(t.get("number") or i),
                "channel": ch,
                "timing": str(t.get("timing") or f"Day {i}")[:120],
                "message_body": str(t.get("message_body") or "")[:2000],
                "goal": str(t.get("goal") or "")[:240],
                "conditional_logic": str(t.get("conditional_logic") or "")[:400],
                "created_at": now,
                "updated_at": now,
                "generated_by": "claude",
            }
            _touchpoints_col.insert_one(dict(doc))
            doc.pop("_id", None)
            inserted.append(doc)

        inserted.sort(key=lambda x: x["number"])
        _patch(
            status="done",
            phase="done",
            result={"touchpoints": inserted, "count": len(inserted), "generated_by": "claude"},
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("journey/generate background job failed")
        _patch(status="failed", phase="failed", error=str(e)[:200])


@router.post("/touchpoints/{tp_id}/regenerate")
async def regenerate_one(tp_id: str, tenant: dict = Depends(get_active_tenant)):
    existing = _touchpoints_col.find_one({"tenant_id": tenant["id"], "id": tp_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Touchpoint not found")
    profile = _profile_summary(tenant["id"])

    # Surrounding context: the 2 touchpoints before and after this one.
    around = list(_touchpoints_col.find(
        {"tenant_id": tenant["id"], "number": {"$ne": existing["number"]}},
        {"_id": 0, "number": 1, "channel": 1, "goal": 1, "message_body": 1},
    ).sort("number", 1))
    context_lines = [
        f"#{r['number']} ({r.get('channel','email')}) — {r.get('goal','')}"
        for r in around if abs(r["number"] - existing["number"]) <= 2
    ]

    system = (
        "You are ARIA, an expert outreach copywriter. Output STRICT JSON only — "
        "no markdown. Schema: "
        '{"channel":"whatsapp|email|linkedin|sms|call",'
        '"timing":"Day N..." ,"message_body":"<150 words>","goal":"<1 line>",'
        '"conditional_logic":"<plain English branch>"}\n'
        "Match the workspace brand voice. Stay under 150 words. End with one specific question or CTA."
    )
    prompt = (
        f"Regenerate touchpoint #{existing['number']} of the outreach journey.\n\n"
        f"WORKSPACE PROFILE:\n{profile}\n\n"
        f"NEARBY TOUCHPOINTS (for continuity):\n" + "\n".join(context_lines) +
        f"\n\nCURRENT TOUCHPOINT (improve on this):\nchannel={existing.get('channel')}\n"
        f"timing={existing.get('timing')}\ngoal={existing.get('goal')}\n"
        f"message={existing.get('message_body','')[:600]}"
    )

    try:
        data = await claude_call(
            task_type=TaskType.TOUCHPOINT_GENERATION,
            system=system,
            prompt=prompt,
            tenant_id=tenant["id"],
            session_id=f"journey-regen-{tp_id}",
            response_format="json",
            sanitize_user_input=True,
        )
    except ClaudeServiceError as e:
        raise HTTPException(502, f"Regenerate failed: {str(e)[:160]}")

    ch = str((data or {}).get("channel") or existing.get("channel") or "email").lower().strip()
    if ch not in _ALLOWED_CHANNELS:
        ch = existing.get("channel", "email")
    update = {
        "channel": ch,
        "timing": str(data.get("timing") or existing.get("timing", ""))[:120],
        "message_body": str(data.get("message_body") or "")[:2000],
        "goal": str(data.get("goal") or existing.get("goal", ""))[:240],
        "conditional_logic": str(data.get("conditional_logic") or existing.get("conditional_logic", ""))[:400],
        "updated_at": _now(),
        "generated_by": "claude",
    }
    _touchpoints_col.update_one({"tenant_id": tenant["id"], "id": tp_id}, {"$set": update})
    return _doc_to_public(_touchpoints_col.find_one({"tenant_id": tenant["id"], "id": tp_id}, {"_id": 0}))
