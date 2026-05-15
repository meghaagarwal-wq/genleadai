"""Outreach Campaigns with Conditional Logic — Deliverable 8.

Expandi-style visual-logic campaign builder. Each campaign has N ordered
touchpoints; each touchpoint has a message_template, delay_hours, and a
conditions JSON describing how to branch based on contact behaviour.

Why not extend the existing `campaigns` collection?
  The existing `campaigns` collection at /api/campaigns is for marketing
  campaigns (UTM tracking, lead count rollup). It's a different domain
  concept. This module uses prefix `/api/outreach` and a separate
  `outreach_campaigns` collection so neither steps on the other.

Collections:
  outreach_campaigns
    - id: str (oc_<hex>)
    - tenant_id: str
    - icp_id: str | None
    - name: str
    - status: 'draft' | 'active' | 'paused' | 'archived'
    - created_at, updated_at

  outreach_touchpoints
    - id: str (ot_<hex>)
    - campaign_id: str
    - tenant_id: str
    - step_number: int (1-based, unique per campaign)
    - channel: str (default 'whatsapp')
    - message_template: str
    - delay_hours: int
    - conditions: dict (validated schema below)

  contact_campaign_status
    - id: str (ccs_<hex>)
    - tenant_id: str
    - campaign_id: str
    - contact_id: str (lead.id)
    - current_step: int
    - status: 'active' | 'paused' | 'completed' | 'unsubscribed' | 'hot_lead'
    - tags: List[str]
    - next_due_at: ISO str | None (when the engine should fire current_step)
    - no_reply_target_step: int | None (which step to jump to if no_reply timeout hits)
    - no_reply_due_at: ISO str | None
    - last_action_at, created_at
    - UNIQUE: (tenant_id, campaign_id, contact_id)

  outreach_campaign_logs
    - id, tenant_id, campaign_id, contact_id, step_number, action,
      message_sent, timestamp

Conditions schema (validated on write):
  {
    "on_reply": {"action": "move_to_step|notify_user|tag_contact|stop",
                 "target_step": int | null, "tag": str | null},
    "on_keyword_match": {"keywords": [str], "action": "...",
                         "tag": str | null, "target_step": int | null},
    "on_negative_keyword": {"keywords": [str], "action": "...",
                            "tag": str | null},
    "on_no_reply": {"after_hours": int, "action": "move_to_step|stop",
                    "target_step": int | null}
  }
Every key is optional. Unknown keys → 400.
"""
from __future__ import annotations

import asyncio
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import db, leads_collection
from routes.tenants import get_active_tenant
from routes.compliance import can_send_outbound
from routes.icps import fetch_icp

router = APIRouter(prefix="/api/outreach", tags=["outreach"])

oc_col = db["outreach_campaigns"]
ot_col = db["outreach_touchpoints"]
ccs_col = db["contact_campaign_status"]
ocl_col = db["outreach_campaign_logs"]
tenants_col = db["tenants"]


# ─── Helpers ────────────────────────────────────────────────────────────────
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _scrub(doc: Optional[dict]) -> Optional[dict]:
    if not doc:
        return doc
    return {k: v for k, v in doc.items() if k != "_id"}


# ─── Conditions validator ───────────────────────────────────────────────────
ALLOWED_CONDITION_KEYS = {"on_reply", "on_keyword_match", "on_negative_keyword", "on_no_reply"}
ALLOWED_ACTIONS = {"move_to_step", "notify_user", "tag_contact", "stop"}


def validate_conditions(conditions: Optional[dict]) -> dict:
    """Return a sanitised copy. Raises HTTPException(400) on malformed schema."""
    if conditions is None:
        return {}
    if not isinstance(conditions, dict):
        raise HTTPException(status_code=400, detail="conditions_must_be_object")

    bad_keys = set(conditions.keys()) - ALLOWED_CONDITION_KEYS
    if bad_keys:
        raise HTTPException(
            status_code=400,
            detail=f"unknown_condition_keys: {sorted(bad_keys)} (allowed: {sorted(ALLOWED_CONDITION_KEYS)})",
        )

    out: Dict[str, Any] = {}

    for key in ("on_reply", "on_keyword_match", "on_negative_keyword"):
        if key not in conditions:
            continue
        block = conditions[key] or {}
        if not isinstance(block, dict):
            raise HTTPException(status_code=400, detail=f"{key}_must_be_object")
        action = block.get("action")
        if action not in ALLOWED_ACTIONS:
            raise HTTPException(
                status_code=400,
                detail=f"{key}.action invalid: must be one of {sorted(ALLOWED_ACTIONS)}",
            )
        sanitized: Dict[str, Any] = {"action": action}
        if action == "move_to_step":
            ts = block.get("target_step")
            if not isinstance(ts, int) or ts < 1:
                raise HTTPException(
                    status_code=400,
                    detail=f"{key}.target_step must be int >= 1 when action=move_to_step",
                )
            sanitized["target_step"] = ts
        elif action == "tag_contact":
            tag = (block.get("tag") or "").strip()
            if not tag:
                raise HTTPException(
                    status_code=400,
                    detail=f"{key}.tag required when action=tag_contact",
                )
            sanitized["tag"] = tag
        # notify_user + stop have no extra required fields

        if key in ("on_keyword_match", "on_negative_keyword"):
            kws = block.get("keywords") or []
            if not isinstance(kws, list) or not kws:
                raise HTTPException(
                    status_code=400,
                    detail=f"{key}.keywords must be a non-empty list",
                )
            sanitized["keywords"] = [str(k).strip().lower() for k in kws if str(k).strip()]
            if not sanitized["keywords"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"{key}.keywords must contain at least one non-empty string",
                )
        out[key] = sanitized

    if "on_no_reply" in conditions:
        block = conditions["on_no_reply"] or {}
        if not isinstance(block, dict):
            raise HTTPException(status_code=400, detail="on_no_reply_must_be_object")
        action = block.get("action")
        if action not in {"move_to_step", "stop"}:
            raise HTTPException(
                status_code=400,
                detail="on_no_reply.action must be 'move_to_step' or 'stop'",
            )
        after = block.get("after_hours")
        if not isinstance(after, int) or after < 1:
            raise HTTPException(
                status_code=400,
                detail="on_no_reply.after_hours must be int >= 1",
            )
        nr: Dict[str, Any] = {"action": action, "after_hours": after}
        if action == "move_to_step":
            ts = block.get("target_step")
            if not isinstance(ts, int) or ts < 1:
                raise HTTPException(
                    status_code=400,
                    detail="on_no_reply.target_step must be int >= 1 when action=move_to_step",
                )
            nr["target_step"] = ts
        out["on_no_reply"] = nr

    return out


# ─── Template renderer (pure function, unit-tested) ─────────────────────────
_TOKEN_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def render_template(template: str, contact: Optional[dict], icp: Optional[dict]) -> str:
    """Replace {token} occurrences in `template` using contact + icp data.

    Supported tokens:
      {first_name}, {last_name}, {full_name}, {company}, {email}, {phone}
      {pain_point}, {value_prop}, {tone}, {industry}, {company_size}
    Missing values → empty string. Malformed tokens → kept literal.
    """
    if not template:
        return ""

    contact = contact or {}
    icp = icp or {}

    full_name = (contact.get("name") or "").strip()
    first_name = contact.get("first_name") or (full_name.split()[0] if full_name else "")
    last_name = contact.get("last_name") or (" ".join(full_name.split()[1:]) if len(full_name.split()) > 1 else "")

    values = {
        "first_name": first_name or "",
        "last_name": last_name or "",
        "full_name": full_name or first_name or "",
        "company": contact.get("company") or "",
        "email": contact.get("email") or "",
        "phone": contact.get("phone") or "",
        "pain_point": icp.get("pain_point") or "",
        "value_prop": icp.get("value_prop") or "",
        "tone": icp.get("tone") or "",
        "industry": icp.get("industry") or "",
        "company_size": icp.get("company_size") or "",
    }

    def _sub(match: re.Match) -> str:
        key = match.group(1)
        return str(values.get(key, ""))

    return _TOKEN_RE.sub(_sub, template)


# ─── Pydantic models ────────────────────────────────────────────────────────
class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    icp_id: Optional[str] = None


class TouchpointUpsert(BaseModel):
    step_number: int = Field(ge=1, le=200)
    channel: str = "whatsapp"
    message_template: str = Field(min_length=1)
    delay_hours: int = Field(ge=0, le=24 * 365)
    conditions: Optional[Dict[str, Any]] = None


class EnrollPayload(BaseModel):
    contact_ids: List[str] = Field(min_length=1, max_length=500)


# ─── Helpers (campaign + tenant scoping) ────────────────────────────────────
def _require_campaign(tenant_id: str, campaign_id: str) -> dict:
    camp = oc_col.find_one({"id": campaign_id, "tenant_id": tenant_id})
    if not camp:
        raise HTTPException(status_code=404, detail="campaign_not_found")
    return _scrub(camp)


def _require_role(tenant: dict, *allowed: str) -> None:
    role = tenant.get("_member_role")
    if role not in allowed:
        raise HTTPException(status_code=403, detail="Not allowed")


def _touchpoint_for_step(tenant_id: str, campaign_id: str, step: int) -> Optional[dict]:
    return _scrub(ot_col.find_one({
        "tenant_id": tenant_id,
        "campaign_id": campaign_id,
        "step_number": step,
    }))


def _max_step(tenant_id: str, campaign_id: str) -> int:
    last = ot_col.find_one(
        {"tenant_id": tenant_id, "campaign_id": campaign_id},
        sort=[("step_number", -1)],
    )
    return int(last.get("step_number", 0)) if last else 0


# ─── Endpoints ──────────────────────────────────────────────────────────────
@router.post("/campaigns", status_code=201)
async def create_campaign(payload: CampaignCreate, tenant: dict = Depends(get_active_tenant)):
    """Create a new outreach campaign in draft status."""
    _require_role(tenant, "owner", "admin", "member")

    if payload.icp_id:
        icp = fetch_icp(tenant["id"], payload.icp_id)
        if not icp:
            raise HTTPException(status_code=404, detail="icp_not_found")

    now = _now_iso()
    doc = {
        "id": _new_id("oc"),
        "tenant_id": tenant["id"],
        "icp_id": payload.icp_id,
        "name": payload.name.strip(),
        "status": "draft",
        "created_at": now,
        "updated_at": now,
    }
    oc_col.insert_one(doc)
    return _scrub(doc)


@router.get("/campaigns")
async def list_campaigns(tenant: dict = Depends(get_active_tenant)):
    rows = list(oc_col.find({"tenant_id": tenant["id"]}).sort("created_at", -1))
    return {"campaigns": [_scrub(r) for r in rows]}


@router.post("/campaigns/{campaign_id}/touchpoints", status_code=201)
async def upsert_touchpoint(
    campaign_id: str,
    payload: TouchpointUpsert,
    tenant: dict = Depends(get_active_tenant),
):
    """Add or update the touchpoint at the given step_number.

    Upsert semantics: if a touchpoint already exists at this step in this
    campaign, its fields are replaced. Otherwise a new row is inserted.

    Errors:
      - 404 campaign_not_found
      - 400 invalid conditions schema (see validate_conditions)
      - 400 invalid_channel
    """
    _require_role(tenant, "owner", "admin", "member")
    _require_campaign(tenant["id"], campaign_id)

    channel = (payload.channel or "whatsapp").lower()
    if channel not in {"whatsapp", "email", "linkedin", "sms"}:
        raise HTTPException(status_code=400, detail=f"invalid_channel: '{channel}'")

    conditions = validate_conditions(payload.conditions)

    existing = ot_col.find_one({
        "tenant_id": tenant["id"],
        "campaign_id": campaign_id,
        "step_number": payload.step_number,
    })

    base = {
        "tenant_id": tenant["id"],
        "campaign_id": campaign_id,
        "step_number": payload.step_number,
        "channel": channel,
        "message_template": payload.message_template,
        "delay_hours": payload.delay_hours,
        "conditions": conditions,
        "updated_at": _now_iso(),
    }
    if existing:
        ot_col.update_one({"_id": existing["_id"]}, {"$set": base})
        return _scrub({**existing, **base})
    base["id"] = _new_id("ot")
    base["created_at"] = _now_iso()
    ot_col.insert_one(base)
    return _scrub(base)


@router.get("/campaigns/{campaign_id}/map")
async def get_campaign_map(campaign_id: str, tenant: dict = Depends(get_active_tenant)):
    """Return the campaign + its ordered touchpoints — what the visual map UI consumes."""
    camp = _require_campaign(tenant["id"], campaign_id)
    rows = list(
        ot_col.find({"tenant_id": tenant["id"], "campaign_id": campaign_id}).sort("step_number", 1)
    )
    return {
        "campaign": camp,
        "touchpoints": [_scrub(r) for r in rows],
    }


@router.delete("/campaigns/{campaign_id}/touchpoints/{step_number}")
async def delete_touchpoint(
    campaign_id: str,
    step_number: int,
    tenant: dict = Depends(get_active_tenant),
):
    _require_role(tenant, "owner", "admin", "member")
    _require_campaign(tenant["id"], campaign_id)
    r = ot_col.delete_one({
        "tenant_id": tenant["id"],
        "campaign_id": campaign_id,
        "step_number": step_number,
    })
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="touchpoint_not_found")
    return {"deleted": True}


@router.post("/campaigns/{campaign_id}/enroll")
async def enroll_contacts(
    campaign_id: str,
    payload: EnrollPayload,
    tenant: dict = Depends(get_active_tenant),
):
    """Enroll a list of contacts (leads) into the campaign at step 1.

    Returns {enrolled, skipped, missing}. Idempotent — already-enrolled
    contacts are silently skipped.

    Errors:
      - 404 campaign_not_found
      - 400 no_touchpoint_step_1   (cannot enroll into an empty campaign)
    """
    _require_role(tenant, "owner", "admin", "member")
    _require_campaign(tenant["id"], campaign_id)

    step1 = _touchpoint_for_step(tenant["id"], campaign_id, 1)
    if not step1:
        raise HTTPException(
            status_code=400,
            detail="no_touchpoint_step_1: define touchpoint step_number=1 before enrolling contacts",
        )

    enrolled = 0
    skipped = 0
    missing = []

    for contact_id in payload.contact_ids:
        lead = leads_collection.find_one(
            {"id": contact_id, "tenant_id": tenant["id"]},
            {"_id": 0, "id": 1},
        )
        if not lead:
            missing.append(contact_id)
            continue
        already = ccs_col.find_one({
            "tenant_id": tenant["id"],
            "campaign_id": campaign_id,
            "contact_id": contact_id,
        })
        if already:
            skipped += 1
            continue
        due_at = (_now() + timedelta(hours=int(step1.get("delay_hours") or 0))).isoformat()
        ccs_col.insert_one({
            "id": _new_id("ccs"),
            "tenant_id": tenant["id"],
            "campaign_id": campaign_id,
            "contact_id": contact_id,
            "current_step": 1,
            "status": "active",
            "tags": [],
            "next_due_at": due_at,
            "no_reply_target_step": None,
            "no_reply_due_at": None,
            "created_at": _now_iso(),
            "last_action_at": _now_iso(),
        })
        enrolled += 1

    return {"enrolled": enrolled, "skipped": skipped, "missing": missing}


@router.post("/campaigns/{campaign_id}/pause")
async def pause_campaign(campaign_id: str, tenant: dict = Depends(get_active_tenant)):
    """Pause all active enrollments under this campaign. Campaign → status='paused'."""
    _require_role(tenant, "owner", "admin")
    _require_campaign(tenant["id"], campaign_id)
    oc_col.update_one(
        {"id": campaign_id, "tenant_id": tenant["id"]},
        {"$set": {"status": "paused", "updated_at": _now_iso()}},
    )
    r = ccs_col.update_many(
        {"tenant_id": tenant["id"], "campaign_id": campaign_id, "status": "active"},
        {"$set": {"status": "paused", "paused_at": _now_iso()}},
    )
    return {"campaign_status": "paused", "paused_contacts": r.modified_count}


@router.post("/campaigns/{campaign_id}/resume")
async def resume_campaign(campaign_id: str, tenant: dict = Depends(get_active_tenant)):
    """Resume previously-paused enrollments. Campaign → status='active'."""
    _require_role(tenant, "owner", "admin")
    _require_campaign(tenant["id"], campaign_id)
    oc_col.update_one(
        {"id": campaign_id, "tenant_id": tenant["id"]},
        {"$set": {"status": "active", "updated_at": _now_iso()}},
    )
    r = ccs_col.update_many(
        {"tenant_id": tenant["id"], "campaign_id": campaign_id, "status": "paused"},
        {"$set": {"status": "active"}, "$unset": {"paused_at": ""}},
    )
    return {"campaign_status": "active", "resumed_contacts": r.modified_count}


@router.get("/campaigns/{campaign_id}/analytics")
async def campaign_analytics(campaign_id: str, tenant: dict = Depends(get_active_tenant)):
    """Per-step stats + funnel + step-over-step conversion."""
    _require_campaign(tenant["id"], campaign_id)
    tenant_id = tenant["id"]

    touchpoints = list(
        ot_col.find({"tenant_id": tenant_id, "campaign_id": campaign_id}).sort("step_number", 1)
    )
    enrolled_total = ccs_col.count_documents({
        "tenant_id": tenant_id,
        "campaign_id": campaign_id,
    })

    by_step: List[Dict[str, Any]] = []
    for tp in touchpoints:
        step = tp["step_number"]
        # Anyone who reached or passed this step
        reached = ccs_col.count_documents({
            "tenant_id": tenant_id,
            "campaign_id": campaign_id,
            "current_step": {"$gte": step},
        }) + ocl_col.count_documents({
            "tenant_id": tenant_id,
            "campaign_id": campaign_id,
            "step_number": step,
            "action": "sent",
        })
        # Replies recorded at this step
        replied = ocl_col.count_documents({
            "tenant_id": tenant_id,
            "campaign_id": campaign_id,
            "step_number": step,
            "action": "reply_received",
        })
        keyword_matches = ocl_col.count_documents({
            "tenant_id": tenant_id,
            "campaign_id": campaign_id,
            "step_number": step,
            "action": "keyword_match",
        })
        stopped = ocl_col.count_documents({
            "tenant_id": tenant_id,
            "campaign_id": campaign_id,
            "step_number": step,
            "action": "stopped",
        })
        sent_at_step = ocl_col.count_documents({
            "tenant_id": tenant_id,
            "campaign_id": campaign_id,
            "step_number": step,
            "action": "sent",
        })
        by_step.append({
            "step_number": step,
            "channel": tp.get("channel"),
            "sent": sent_at_step,
            "reached": reached,
            "replied": replied,
            "keyword_matches": keyword_matches,
            "stopped": stopped,
            "reply_rate_pct": round(100.0 * replied / sent_at_step, 1) if sent_at_step else 0.0,
        })

    # Step-over-step conversion: how many at step N+1 / how many at step N
    for i in range(len(by_step) - 1):
        cur = by_step[i]["sent"] or 0
        nxt = by_step[i + 1]["sent"] or 0
        by_step[i]["conversion_to_next_pct"] = round(100.0 * nxt / cur, 1) if cur else 0.0
    if by_step:
        by_step[-1]["conversion_to_next_pct"] = None

    status_breakdown_cursor = ccs_col.aggregate([
        {"$match": {"tenant_id": tenant_id, "campaign_id": campaign_id}},
        {"$group": {"_id": "$status", "n": {"$sum": 1}}},
    ])
    status_breakdown = {row["_id"]: row["n"] for row in status_breakdown_cursor}

    return {
        "campaign_id": campaign_id,
        "enrolled_total": enrolled_total,
        "by_step": by_step,
        "status_breakdown": status_breakdown,
    }


# ─── Send path + condition evaluator ────────────────────────────────────────
async def _send_one(status_row: dict) -> Dict[str, Any]:
    """Fire the current touchpoint for one contact. Updates status_row state."""
    tenant_id = status_row["tenant_id"]
    campaign_id = status_row["campaign_id"]
    contact_id = status_row["contact_id"]
    step = int(status_row["current_step"])

    tenant = tenants_col.find_one({"id": tenant_id}, {"_id": 0})
    lead = leads_collection.find_one({"id": contact_id, "tenant_id": tenant_id}, {"_id": 0})
    touchpoint = _touchpoint_for_step(tenant_id, campaign_id, step)
    if not tenant or not lead or not touchpoint:
        # Mark completed if we ran past the end of the campaign
        if not touchpoint:
            ccs_col.update_one(
                {"id": status_row["id"]},
                {"$set": {"status": "completed", "completed_at": _now_iso(), "next_due_at": None}},
            )
            return {"ok": True, "completed": True}
        ccs_col.update_one(
            {"id": status_row["id"]},
            {"$set": {"status": "completed", "completed_at": _now_iso(), "next_due_at": None}},
        )
        return {"ok": False, "error": "missing_tenant_or_lead"}

    # Compliance gate (re-use existing helper for WhatsApp).
    if touchpoint.get("channel") == "whatsapp":
        gate = can_send_outbound(tenant_id, lead)
        if not gate.get("allow"):
            ocl_col.insert_one({
                "id": _new_id("ocl"),
                "tenant_id": tenant_id,
                "campaign_id": campaign_id,
                "contact_id": contact_id,
                "step_number": step,
                "action": "skipped",
                "skip_reason": gate.get("reason"),
                "timestamp": _now_iso(),
            })
            ccs_col.update_one(
                {"id": status_row["id"]},
                {"$set": {"status": "unsubscribed", "next_due_at": None, "last_action_at": _now_iso()}},
            )
            return {"ok": False, "error": f"skipped:{gate.get('reason')}"}

    # Resolve ICP for tokens
    camp = oc_col.find_one({"id": campaign_id, "tenant_id": tenant_id}, {"_id": 0})
    icp = None
    if lead.get("icp_id"):
        icp = fetch_icp(tenant_id, lead.get("icp_id"))
    if not icp and camp and camp.get("icp_id"):
        icp = fetch_icp(tenant_id, camp.get("icp_id"))

    rendered = render_template(touchpoint["message_template"], lead, icp)

    # Dispatch
    error = None
    sent_ok = False
    channel = touchpoint.get("channel", "whatsapp")
    try:
        if channel == "whatsapp":
            from whatsapp_dispatch import send_whatsapp_text
            result = await send_whatsapp_text(lead.get("phone") or "", rendered, tenant_id=tenant_id)
            sent_ok = bool(result.get("sent"))
            if not sent_ok:
                error = result.get("error") or "send_failed"
        elif channel == "email":
            email = lead.get("email")
            if not email:
                error = "no_email"
            else:
                from backend.email_delivery import send_email_safely  # type: ignore
                # Optional — only used if available; fallback to noop otherwise.
                try:
                    result = send_email_safely(  # noqa: F821
                        to=email,
                        subject=f"From {tenant.get('name') or 'us'}",
                        text=rendered,
                    )
                    sent_ok = bool(getattr(result, "delivered", False) or result.get("delivered") if isinstance(result, dict) else False)
                except Exception as ee:
                    error = f"email_send_failed:{ee}"
        else:
            # linkedin / sms — log as an alert
            sent_ok = True
            db["aria_alerts"].insert_one({
                "tenant_id": tenant_id,
                "lead_id": contact_id,
                "kind": f"{channel}_alert",
                "summary": rendered[:300],
                "created_at": _now_iso(),
                "read": False,
            })
    except Exception as e:
        error = str(e)

    if sent_ok:
        ocl_col.insert_one({
            "id": _new_id("ocl"),
            "tenant_id": tenant_id,
            "campaign_id": campaign_id,
            "contact_id": contact_id,
            "step_number": step,
            "action": "sent",
            "message_sent": rendered,
            "timestamp": _now_iso(),
        })
        # Schedule no_reply branch if defined.
        conditions = touchpoint.get("conditions") or {}
        no_reply = conditions.get("on_no_reply") or {}
        update: Dict[str, Any] = {"last_action_at": _now_iso(), "next_due_at": None}
        if no_reply.get("action") == "move_to_step":
            update["no_reply_due_at"] = (_now() + timedelta(hours=int(no_reply["after_hours"]))).isoformat()
            update["no_reply_target_step"] = int(no_reply["target_step"])
        elif no_reply.get("action") == "stop":
            update["no_reply_due_at"] = (_now() + timedelta(hours=int(no_reply["after_hours"]))).isoformat()
            update["no_reply_target_step"] = -1   # sentinel = stop
        else:
            update["no_reply_due_at"] = None
            update["no_reply_target_step"] = None
        ccs_col.update_one({"id": status_row["id"]}, {"$set": update})
        return {"ok": True, "sent": True, "step": step}

    ocl_col.insert_one({
        "id": _new_id("ocl"),
        "tenant_id": tenant_id,
        "campaign_id": campaign_id,
        "contact_id": contact_id,
        "step_number": step,
        "action": "failed",
        "error": error or "unknown",
        "timestamp": _now_iso(),
    })
    ccs_col.update_one(
        {"id": status_row["id"]},
        {"$set": {"last_action_at": _now_iso(), "last_error": error or "unknown"}},
    )
    return {"ok": False, "error": error}


def _evaluate_keyword_match(text: str, keywords: List[str]) -> bool:
    body = (text or "").lower()
    return any(kw and kw in body for kw in keywords)


def _apply_branch(status_row: dict, action: str, target_step: Optional[int], tag: Optional[str]) -> dict:
    """Apply a branch action to a contact_campaign_status row and return the patch."""
    patch: Dict[str, Any] = {"last_action_at": _now_iso()}
    if action == "stop":
        patch.update({"status": "completed", "next_due_at": None, "no_reply_due_at": None, "no_reply_target_step": None})
    elif action == "tag_contact":
        # tag merges into status_row.tags
        existing_tags = set(status_row.get("tags") or [])
        if tag:
            existing_tags.add(tag)
        patch["tags"] = sorted(existing_tags)
        # Special-case: a contact tagged 'hot_lead' flips status for visibility.
        if tag == "hot_lead":
            patch["status"] = "hot_lead"
            patch["next_due_at"] = None
    elif action == "move_to_step" and isinstance(target_step, int) and target_step >= 1:
        # Look up the touchpoint's delay
        tp = _touchpoint_for_step(status_row["tenant_id"], status_row["campaign_id"], target_step)
        if tp:
            patch["current_step"] = target_step
            patch["next_due_at"] = (_now() + timedelta(hours=int(tp.get("delay_hours") or 0))).isoformat()
            patch["no_reply_due_at"] = None
            patch["no_reply_target_step"] = None
        else:
            patch["status"] = "completed"
            patch["next_due_at"] = None
    elif action == "notify_user":
        db["aria_alerts"].insert_one({
            "tenant_id": status_row["tenant_id"],
            "lead_id": status_row["contact_id"],
            "kind": "outreach_notify",
            "summary": f"Outreach campaign {status_row['campaign_id']} step {status_row['current_step']} triggered notify_user",
            "created_at": _now_iso(),
            "read": False,
        })
    return patch


def handle_inbound_reply(tenant_id: str, contact_id: str, message_body: str) -> Dict[str, Any]:
    """Public — called from the existing 360dialog/Meta webhook handler.

    For every active enrollment for this contact, evaluate the conditions on
    the current touchpoint against the inbound message. Fire the first
    matching branch in priority order:
      negative_keyword  →  keyword_match  →  on_reply  (generic)
    Always cancels any pending no_reply timer. Idempotent across rows.
    """
    rows = list(ccs_col.find({
        "tenant_id": tenant_id,
        "contact_id": contact_id,
        "status": {"$in": ["active", "paused"]},
    }))
    if not rows:
        return {"matched": 0}

    body_lower = (message_body or "").lower()
    matched = 0

    for row in rows:
        row = _scrub(row)
        step = int(row["current_step"])
        tp = _touchpoint_for_step(tenant_id, row["campaign_id"], step)
        conditions = (tp.get("conditions") or {}) if tp else {}

        # Always log the reply event
        ocl_col.insert_one({
            "id": _new_id("ocl"),
            "tenant_id": tenant_id,
            "campaign_id": row["campaign_id"],
            "contact_id": contact_id,
            "step_number": step,
            "action": "reply_received",
            "message_received": message_body[:1000],
            "timestamp": _now_iso(),
        })

        # Always cancel pending no_reply timer (lead replied)
        cancel_no_reply = {"no_reply_due_at": None, "no_reply_target_step": None}

        # 1. Negative keyword takes priority
        neg = conditions.get("on_negative_keyword")
        if neg and _evaluate_keyword_match(body_lower, neg.get("keywords", [])):
            patch = _apply_branch(row, neg["action"], None, neg.get("tag"))
            patch.update(cancel_no_reply)
            ccs_col.update_one({"id": row["id"]}, {"$set": patch})
            ocl_col.insert_one({
                "id": _new_id("ocl"), "tenant_id": tenant_id, "campaign_id": row["campaign_id"],
                "contact_id": contact_id, "step_number": step, "action": "negative_keyword_match",
                "matched_keywords": [k for k in neg["keywords"] if k in body_lower],
                "timestamp": _now_iso(),
            })
            matched += 1
            continue

        # 2. Positive keyword
        kw = conditions.get("on_keyword_match")
        if kw and _evaluate_keyword_match(body_lower, kw.get("keywords", [])):
            patch = _apply_branch(row, kw["action"], kw.get("target_step"), kw.get("tag"))
            patch.update(cancel_no_reply)
            ccs_col.update_one({"id": row["id"]}, {"$set": patch})
            ocl_col.insert_one({
                "id": _new_id("ocl"), "tenant_id": tenant_id, "campaign_id": row["campaign_id"],
                "contact_id": contact_id, "step_number": step, "action": "keyword_match",
                "matched_keywords": [k for k in kw["keywords"] if k in body_lower],
                "timestamp": _now_iso(),
            })
            matched += 1
            continue

        # 3. Generic on_reply
        on_reply = conditions.get("on_reply")
        if on_reply:
            patch = _apply_branch(row, on_reply["action"], on_reply.get("target_step"), on_reply.get("tag"))
            patch.update(cancel_no_reply)
            ccs_col.update_one({"id": row["id"]}, {"$set": patch})
            matched += 1
            continue

        # 4. No condition matched — just cancel pending no_reply timer
        ccs_col.update_one({"id": row["id"]}, {"$set": {**cancel_no_reply, "last_action_at": _now_iso()}})
        matched += 1

    return {"matched": matched}


# ─── Background engine loop ─────────────────────────────────────────────────
async def outreach_tick() -> Dict[str, Any]:
    """One tick: fire all due 'next_due_at' sends + apply expired no_reply timers."""
    now_iso = _now_iso()

    # 1. Send due touchpoints
    due_send_cursor = ccs_col.find({
        "status": "active",
        "next_due_at": {"$ne": None, "$lte": now_iso},
    }).limit(30)
    due_send = list(due_send_cursor)
    sent = 0
    failed = 0
    for row in due_send:
        result = await _send_one(_scrub(row))
        if result.get("ok"):
            sent += 1
        else:
            failed += 1

    # 2. Apply expired no_reply timers (contact never replied)
    timer_cursor = ccs_col.find({
        "status": "active",
        "no_reply_due_at": {"$ne": None, "$lte": now_iso},
    }).limit(30)
    timer_rows = list(timer_cursor)
    transitions = 0
    for row in timer_rows:
        row = _scrub(row)
        target = row.get("no_reply_target_step")
        if target == -1:
            ccs_col.update_one(
                {"id": row["id"]},
                {"$set": {
                    "status": "completed",
                    "next_due_at": None,
                    "no_reply_due_at": None,
                    "no_reply_target_step": None,
                    "last_action_at": _now_iso(),
                }},
            )
            ocl_col.insert_one({
                "id": _new_id("ocl"), "tenant_id": row["tenant_id"], "campaign_id": row["campaign_id"],
                "contact_id": row["contact_id"], "step_number": int(row["current_step"]),
                "action": "stopped", "reason": "no_reply_timeout", "timestamp": _now_iso(),
            })
        elif isinstance(target, int) and target >= 1:
            patch = _apply_branch(row, "move_to_step", target, None)
            patch["no_reply_due_at"] = None
            patch["no_reply_target_step"] = None
            ccs_col.update_one({"id": row["id"]}, {"$set": patch})
            ocl_col.insert_one({
                "id": _new_id("ocl"), "tenant_id": row["tenant_id"], "campaign_id": row["campaign_id"],
                "contact_id": row["contact_id"], "step_number": int(row["current_step"]),
                "action": "no_reply_advance", "target_step": target, "timestamp": _now_iso(),
            })
        transitions += 1

    return {"sent": sent, "failed": failed, "no_reply_transitions": transitions, "checked": len(due_send)}


async def outreach_engine_loop():
    """Run forever — tick every 30s. Called from server.py startup."""
    print("[outreach-engine] started (30s tick)")
    while True:
        try:
            stats = await outreach_tick()
            if stats["sent"] or stats["failed"] or stats["no_reply_transitions"]:
                print(f"[outreach-engine] tick → {stats}")
        except Exception as e:
            print(f"[outreach-engine] tick error: {e}")
        await asyncio.sleep(30)
