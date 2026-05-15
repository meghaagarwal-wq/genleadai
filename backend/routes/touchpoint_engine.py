"""Touchpoint execution engine — Phase B of the touchpoint feature.

On lead create → instantiate one lead_touchpoint_log row per touchpoint with
status=pending and scheduled_for offset-from-now.

Async background loop (started in server.py) ticks every 60s, picks pending
rows where scheduled_for <= now, generates the message via Claude (using the
touchpoint message_template as INTENT), sends via 360dialog/Meta WhatsApp or
Resend (email), updates status.

Reply-pause: when an inbound message arrives for a lead, all pending rows for
that lead get status=paused. (Reactivation logic deferred.)

Closed-Won / Closed-Lost: stage change → all pending rows for that lead
get status=cancelled.

Owner/admin can override: "Send now" or "Pause Aria for this lead".
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import db
from routes.tenants import get_active_tenant
from routes.compliance import can_send_outbound

log_col = db["lead_touchpoint_log"]
maps_col = db["workspace_touchpoint_maps"]
leads_col = db["leads"]
tenants_col = db["tenants"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _new_id() -> str:
    return f"ltp_{uuid.uuid4().hex[:12]}"


def _scheduled_for(touchpoint: dict, start: datetime) -> datetime:
    day = float(touchpoint.get("day") or 0)
    hour = int(touchpoint.get("hour") or 0)
    return start + timedelta(days=day, hours=hour)


# ─── Lifecycle hooks ────────────────────────────────────────────────────────
def instantiate_for_lead(tenant_id: str, lead: dict) -> int:
    """On lead create — copy the tenant's active map into per-lead pending rows.

    Returns the number of touchpoints scheduled. Idempotent: skips if rows
    already exist for the lead.
    """
    lead_id = lead.get("id") or str(lead.get("_id"))
    if not lead_id:
        return 0
    existing = log_col.find_one({"tenant_id": tenant_id, "lead_id": lead_id}, {"_id": 1})
    if existing:
        return 0
    tmap = maps_col.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if not tmap or not tmap.get("touchpoints"):
        return 0
    start = _now()
    rows = []
    for tp in tmap["touchpoints"]:
        rows.append({
            "id": _new_id(),
            "tenant_id": tenant_id,
            "lead_id": lead_id,
            "touchpoint_index": tp.get("index", 0),
            "channel": tp.get("channel", "whatsapp"),
            "message_type": tp.get("message_type", "intro"),
            "aria_role": tp.get("aria_role", "autonomous"),
            "message_template": tp.get("message_template", ""),
            "scheduled_for": _scheduled_for(tp, start).isoformat(),
            "status": "pending",
            "fired_at": None,
            "message_sent": None,
            "retry_count": 0,
            "created_at": _now_iso(),
        })
    if rows:
        log_col.insert_many(rows)
    return len(rows)


def pause_lead(tenant_id: str, lead_id: str) -> int:
    """Pause all pending touchpoints for a lead (called on inbound reply)."""
    r = log_col.update_many(
        {"tenant_id": tenant_id, "lead_id": lead_id, "status": "pending"},
        {"$set": {"status": "paused", "paused_at": _now_iso()}},
    )
    return r.modified_count


def resume_lead(tenant_id: str, lead_id: str) -> int:
    """Resume previously-paused touchpoints (manual operator action)."""
    r = log_col.update_many(
        {"tenant_id": tenant_id, "lead_id": lead_id, "status": "paused"},
        {"$set": {"status": "pending"}, "$unset": {"paused_at": ""}},
    )
    return r.modified_count


def cancel_lead(tenant_id: str, lead_id: str, reason: str = "stage_change") -> int:
    """Cancel all remaining (pending+paused) touchpoints — e.g. Closed Won/Lost."""
    r = log_col.update_many(
        {"tenant_id": tenant_id, "lead_id": lead_id, "status": {"$in": ["pending", "paused"]}},
        {"$set": {"status": "cancelled", "cancel_reason": reason, "cancelled_at": _now_iso()}},
    )
    return r.modified_count


# ─── Send paths ──────────────────────────────────────────────────────────────
async def _render_with_claude(tenant: dict, lead: dict, tp_row: dict) -> Optional[str]:
    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        return None
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        biz_name = tenant.get("name") or "the team"
        biz = (tenant.get("settings") or {}).get("business_profile") or {}
        industry = biz.get("industry") or "B2B"
        persona = (tenant.get("settings") or {}).get("aria_persona") or {}
        tone = persona.get("tone") or "friendly_professional"
        aria_name = persona.get("aria_name") or "Aria"
        first_name = (lead.get("name") or "").split()[0] if lead.get("name") else "there"
        product = ((tenant.get("settings") or {}).get("sales_process") or {}).get("product_description") or "our offering"

        # Resolve ICP for this lead (Deliverable 7 — Multi-ICP context injection)
        icp_block = ""
        try:
            from routes.icps import fetch_icp_for_lead
            icp = fetch_icp_for_lead(tenant.get("id"), lead)
            if icp:
                # ICP-specific tone overrides workspace default
                if icp.get("tone"):
                    tone = icp["tone"]
                titles = ", ".join(icp.get("title_targets") or []) or "key decision-makers"
                icp_block = (
                    f"\nLead's ICP profile (use this to tailor the message):\n"
                    f"- Persona: {icp.get('label')}\n"
                    f"- Likely title(s): {titles}\n"
                    f"- Industry: {icp.get('industry') or 'n/a'} · Company size: {icp.get('company_size') or 'n/a'}\n"
                    f"- Pain point: {icp.get('pain_point') or 'n/a'}\n"
                    f"- Value prop to lean into: {icp.get('value_prop') or 'n/a'}\n"
                )
        except Exception as _e:
            print(f"[engine] icp context fetch failed: {_e}")

        system = (
            f"You are {aria_name}, AI sales assistant for {biz_name} ({industry}). Tone: {tone}. "
            "Output ONLY the message body. No preamble, markdown, quotes."
        )
        user_msg = (
            f"Lead first name: {first_name}\nProduct/service: {product}\n"
            f"Channel: {tp_row.get('channel')}\nTouchpoint intent: {tp_row.get('message_type')}"
            f"{icp_block}"
            f"\nBase template (rewrite using lead's name + the product specifics):\n{tp_row.get('message_template')}\n\n"
            "1-3 sentences max, end with one open question."
        )
        chat = LlmChat(api_key=api_key, session_id=f"send-{tp_row['id']}", system_message=system).with_model("anthropic", "claude-sonnet-4-5-20250929")
        text = (await chat.send_message(UserMessage(text=user_msg)) or "").strip()
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]
        return text or None
    except Exception as e:
        print(f"[engine] claude render failed: {e}")
        return None


def _heuristic_render(tenant: dict, lead: dict, tp_row: dict) -> str:
    msg = tp_row.get("message_template", "")
    first_name = (lead.get("name") or "").split()[0] if lead.get("name") else "there"
    persona = (tenant.get("settings") or {}).get("aria_persona") or {}
    aria_name = persona.get("aria_name") or "Aria"
    biz_name = tenant.get("name") or "our team"
    product = ((tenant.get("settings") or {}).get("sales_process") or {}).get("product_description") or "our offering"
    return (
        msg.replace("{{first_name}}", first_name)
        .replace("{{aria_name}}", aria_name)
        .replace("{{company}}", biz_name)
        .replace("{{product}}", product[:80])
    )


async def _send_one(row: dict) -> dict:
    """Fire a single due touchpoint. Returns {ok, sent, error?}."""
    tenant_id = row["tenant_id"]
    lead_id = row["lead_id"]

    tenant = tenants_col.find_one({"id": tenant_id}, {"_id": 0})
    lead = leads_col.find_one({"id": lead_id, "tenant_id": tenant_id}, {"_id": 0})
    if not tenant or not lead:
        log_col.update_one({"id": row["id"]}, {"$set": {"status": "failed", "fired_at": _now_iso(), "error": "missing_tenant_or_lead"}})
        return {"ok": False, "error": "missing_tenant_or_lead"}

    # Compliance gate
    gate = can_send_outbound(tenant_id, lead)
    if not gate["allow"]:
        log_col.update_one({"id": row["id"]}, {"$set": {"status": "skipped", "fired_at": _now_iso(), "skip_reason": gate["reason"]}})
        return {"ok": False, "error": f"skipped:{gate['reason']}"}

    # Human-alert touchpoints: don't send, just notify
    if row.get("aria_role") == "alert_human":
        rendered = f"[ARIA ALERT] Touchpoint #{row['touchpoint_index']+1} for {lead.get('name')}: {row.get('message_template')[:140]}"
        log_col.update_one(
            {"id": row["id"]},
            {"$set": {"status": "alert_sent", "fired_at": _now_iso(), "message_sent": rendered}},
        )
        db["aria_alerts"].insert_one({
            "tenant_id": tenant_id, "lead_id": lead_id, "kind": "touchpoint_alert",
            "summary": rendered, "created_at": _now_iso(), "read": False,
        })
        return {"ok": True, "alert": True}

    # Render copy
    rendered = await _render_with_claude(tenant, lead, row) or _heuristic_render(tenant, lead, row)

    channel = row.get("channel", "whatsapp")
    try:
        if channel == "whatsapp":
            from whatsapp_dispatch import send_whatsapp_text
            result = await send_whatsapp_text(lead.get("phone") or "", rendered, tenant_id=tenant_id)
            if not result.get("sent"):
                log_col.update_one(
                    {"id": row["id"]},
                    {"$set": {"status": "failed", "fired_at": _now_iso(), "error": result.get("error"), "message_sent": rendered}},
                    upsert=False,
                )
                return {"ok": False, "error": result.get("error")}
        elif channel == "email":
            email = lead.get("email")
            if not email:
                log_col.update_one({"id": row["id"]}, {"$set": {"status": "skipped", "skip_reason": "no_email", "fired_at": _now_iso()}})
                return {"ok": False, "error": "no_email"}
            await _send_email(tenant, email, lead.get("name") or "there", rendered, row)
        else:
            # call_reminder + linkedin_nudge — log as alert for the human to act on
            db["aria_alerts"].insert_one({
                "tenant_id": tenant_id, "lead_id": lead_id, "kind": f"{channel}_alert",
                "summary": f"Aria recommends {channel} for {lead.get('name')}: {rendered[:200]}",
                "created_at": _now_iso(), "read": False,
            })

        log_col.update_one(
            {"id": row["id"]},
            {"$set": {"status": "sent", "fired_at": _now_iso(), "message_sent": rendered}},
        )
        return {"ok": True}
    except Exception as e:
        log_col.update_one(
            {"id": row["id"]},
            {"$set": {"status": "failed", "fired_at": _now_iso(), "error": str(e), "message_sent": rendered}},
        )
        return {"ok": False, "error": str(e)}


async def _send_email(tenant: dict, to_email: str, name: str, body: str, row: dict) -> None:
    import resend
    if not getattr(resend, "api_key", None):
        resend.api_key = os.getenv("RESEND_API_KEY")
    if not getattr(resend, "api_key", None):
        raise RuntimeError("resend_not_configured")
    subject_match = body.lower().startswith("subject:")
    subject = "A quick note from " + (tenant.get("name") or "the team")
    if subject_match:
        first_line, _, rest = body.partition("\n")
        subject = first_line.replace("Subject:", "", 1).strip() or subject
        body = rest.strip() or body
    await asyncio.to_thread(resend.Emails.send, {
        "from": os.getenv("SENDER_EMAIL", "onboarding@resend.dev"),
        "to": [to_email],
        "subject": subject,
        "text": body,
    })


# ─── Background loop ────────────────────────────────────────────────────────
async def engine_tick() -> dict:
    """Pick due touchpoints and fire them. Capped at 30 per tick to avoid stampede."""
    now_iso = _now_iso()
    cursor = log_col.find(
        {"status": "pending", "scheduled_for": {"$lte": now_iso}},
        {"_id": 0},
    ).limit(30)
    rows = list(cursor)
    sent = 0
    failed = 0
    for row in rows:
        result = await _send_one(row)
        if result.get("ok"):
            sent += 1
        else:
            failed += 1
    return {"checked": len(rows), "sent": sent, "failed": failed}


async def engine_loop():
    """Run forever — tick every 60s. Called from server.py startup."""
    print("[touchpoint-engine] started (60s tick)")
    while True:
        try:
            stats = await engine_tick()
            if stats["checked"]:
                print(f"[touchpoint-engine] tick → {stats}")
        except Exception as e:
            print(f"[touchpoint-engine] tick error: {e}")
        await asyncio.sleep(60)


# ─── HTTP API ────────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/touchpoints", tags=["touchpoint-engine"])


@router.get("/lead/{lead_id}/journey")
async def get_journey(lead_id: str, tenant: dict = Depends(get_active_tenant)):
    """Return the full touchpoint journey for one lead."""
    rows = list(log_col.find(
        {"tenant_id": tenant["id"], "lead_id": lead_id},
        {"_id": 0},
    ).sort("touchpoint_index", 1))
    return {"lead_id": lead_id, "touchpoints": rows}


class JourneyAction(BaseModel):
    action: str  # send_now | pause_lead | resume_lead | cancel_remaining


@router.post("/lead/{lead_id}/action")
async def journey_action(lead_id: str, payload: JourneyAction, tenant: dict = Depends(get_active_tenant)):
    if tenant.get("_member_role") not in ("owner", "admin", "member"):
        raise HTTPException(status_code=403, detail="Not allowed")
    if payload.action == "pause_lead":
        n = pause_lead(tenant["id"], lead_id)
        return {"status": "ok", "paused": n}
    if payload.action == "resume_lead":
        n = resume_lead(tenant["id"], lead_id)
        return {"status": "ok", "resumed": n}
    if payload.action == "cancel_remaining":
        n = cancel_lead(tenant["id"], lead_id, reason="manual_cancel")
        return {"status": "ok", "cancelled": n}
    raise HTTPException(status_code=400, detail="Unknown action")


@router.post("/touchpoint/{tp_id}/send-now")
async def send_now(tp_id: str, tenant: dict = Depends(get_active_tenant)):
    """Owner override: fire a specific pending touchpoint immediately."""
    if tenant.get("_member_role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")
    row = log_col.find_one({"id": tp_id, "tenant_id": tenant["id"]}, {"_id": 0})
    if not row:
        raise HTTPException(status_code=404, detail="Touchpoint not found")
    if row.get("status") not in ("pending", "paused", "failed"):
        raise HTTPException(status_code=409, detail=f"Cannot send touchpoint in status '{row.get('status')}'")
    result = await _send_one(row)
    return {"status": "fired", "result": result}


# Instantiation endpoint — used by lead-create paths that don't auto-hook.
class InstantiatePayload(BaseModel):
    lead_id: str


@router.post("/lead/instantiate")
async def http_instantiate(payload: InstantiatePayload, tenant: dict = Depends(get_active_tenant)):
    if tenant.get("_member_role") not in ("owner", "admin", "member"):
        raise HTTPException(status_code=403, detail="Not allowed")
    lead = leads_col.find_one({"id": payload.lead_id, "tenant_id": tenant["id"]}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    n = instantiate_for_lead(tenant["id"], lead)
    return {"status": "ok", "scheduled": n}
