"""ARIA — Approval Queue Digest (Batch 8).

8 PM workspace-local cron that ships a single email digest of every
pending_outreach.awaiting_owner_approval draft. Two CTAs:

  [Approve All] → deep-link to /app/approvals?action=bulk-approve
  [Open Queue → ] → deep-link to /app/approvals

Mirrors the architecture of `routes/aria_morning_brief.py` so the cron
loop, config endpoints, and Resend send-flow stay consistent.

Skip rule: if there are zero pending drafts at the trigger window, do
nothing — no empty digests.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import resend
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import db, get_current_user
from security.encryption import decrypt as _dec

logger = logging.getLogger("aria_approval_digest")
router = APIRouter(prefix="/api/aria/approval-digest", tags=["aria-approval-digest"])

config_col = db["aria_approval_digest_config"]
pending_col = db["pending_outreach"]
sent_col = db["aria_approval_digest_sent"]
integrations_col = db["pt_integrations"]
pt_leads_col = db["pt_leads"]
tenants_col = db["tenants"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _app_url() -> str:
    return (os.environ.get("FRONTEND_URL") or "https://app.genleadai.com").rstrip("/")


# ─── Config schema ──────────────────────────────────────────────────────
class DigestConfig(BaseModel):
    enabled: bool = False
    send_to_email: str = Field("", description="Founder's email.")
    send_hour_local: int = Field(20, ge=0, le=23)
    timezone_offset_hours: float = Field(0.0, ge=-12.0, le=14.0)
    weekdays_only: bool = False


def _get_cfg(tenant_id: str) -> Dict[str, Any]:
    return config_col.find_one({"tenant_id": tenant_id}, {"_id": 0}) or {}


# ─── Tenant + lead lookup ───────────────────────────────────────────────
def _tenant_meta(tenant_id: str) -> Dict[str, Any]:
    t = tenants_col.find_one({"id": tenant_id}, {"_id": 0, "name": 1, "settings": 1}) or {}
    settings = t.get("settings") or {}
    return {
        "workspace_name": t.get("name") or "your workspace",
        "founder_name": (settings.get("aria_persona") or {}).get("founder_name") or "there",
    }


def _enrich(draft: Dict[str, Any]) -> Dict[str, Any]:
    lead = pt_leads_col.find_one(
        {"id": draft.get("lead_id"), "tenant_id": draft.get("tenant_id")},
        {"_id": 0, "first_name": 1, "last_name": 1, "email": 1, "company_name": 1, "stage": 1},
    ) or {}
    name = f"{lead.get('first_name','')} {lead.get('last_name','')}".strip() or lead.get("email") or "Prospect"
    return {
        "name": name,
        "company": lead.get("company_name"),
        "channel": draft.get("channel"),
        "intent": (draft.get("qualification") or {}).get("intent"),
        "signal_hint": (draft.get("qualification") or {}).get("next_action_hint") or (draft.get("qualification") or {}).get("summary") or "",
        "subject": draft.get("subject"),
        "body": draft.get("body", ""),
    }


# ─── HTML render ────────────────────────────────────────────────────────
_CHANNEL_GLYPH = {"whatsapp": "💬", "email": "📧", "linkedin": "in"}
_CHANNEL_BG = {
    "whatsapp": "#DCFCE7", "email": "#E0E7FF", "linkedin": "#DBEAFE",
}
_CHANNEL_FG = {
    "whatsapp": "#166534", "email": "#3730A3", "linkedin": "#1E40AF",
}


def _first_n_lines(text: str, n: int = 2) -> str:
    if not text:
        return ""
    lines = [ln for ln in (text.splitlines()) if ln.strip()]
    return "\n".join(lines[:n])


def _render_digest_html(meta: Dict[str, Any], drafts: List[Dict[str, Any]]) -> str:
    today = datetime.now(timezone.utc).strftime("%a, %b %d")
    count = len(drafts)

    cards = ""
    for d in drafts[:25]:  # cap rendering — link to queue for the rest
        glyph = _CHANNEL_GLYPH.get(d["channel"], "•")
        bg = _CHANNEL_BG.get(d["channel"], "#F1F5F9")
        fg = _CHANNEL_FG.get(d["channel"], "#475569")
        preview = _first_n_lines(d["body"], 2)
        subject_line = f"""<div style="font-size:13px;font-weight:600;color:#0F172A;margin-bottom:4px;">{d['subject']}</div>""" if d["channel"] == "email" and d.get("subject") else ""
        intent_pill = ""
        if d.get("intent"):
            intent_pill = f"""<span style="display:inline-block;font-size:10px;font-weight:bold;text-transform:uppercase;letter-spacing:1.2px;padding:2px 6px;border-radius:4px;background:#FAF7FF;color:#7C35DC;margin-left:6px;">{d['intent'].replace('_',' ')}</span>"""

        cards += f"""
        <div style="border:1px solid #E2E8F0;border-radius:8px;padding:14px 16px;margin-bottom:10px;background:#FFFFFF;">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
            <div style="display:flex;align-items:center;gap:8px;">
              <span style="display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:6px;background:{bg};color:{fg};font-size:12px;font-weight:bold;">{glyph}</span>
              <div>
                <div style="font-size:14px;font-weight:bold;color:#0F172A;font-family:'Space Grotesk',Inter,sans-serif;">{d['name']}{intent_pill}</div>
                <div style="font-size:11px;color:#64748B;">{d.get('company') or '—'}</div>
              </div>
            </div>
          </div>
          {f'<div style="font-size:11px;color:#7C35DC;font-style:italic;margin-bottom:6px;">↳ {d["signal_hint"]}</div>' if d['signal_hint'] else ''}
          {subject_line}
          <div style="font-size:13px;color:#0F172A;white-space:pre-wrap;line-height:1.5;background:#FAFAFA;padding:8px 10px;border-radius:4px;border:1px solid #F1F5F9;">{preview or '(empty)'}</div>
        </div>
        """

    extra_note = ""
    if count > 25:
        extra_note = f"""<div style="text-align:center;font-size:11px;color:#94A3B8;margin:8px 0;">… and {count - 25} more in the queue</div>"""

    return f"""
    <div style="font-family:Inter,-apple-system,sans-serif;max-width:680px;margin:0 auto;color:#0F172A;background:#F8FAFC;padding:24px;">
      <div style="text-align:center;margin-bottom:24px;">
        <div style="display:inline-flex;align-items:center;gap:8px;background:linear-gradient(135deg,#4C1D95 0%,#7C35DC 100%);padding:8px 16px;border-radius:999px;">
          <span style="color:white;font-size:11px;font-weight:bold;letter-spacing:1.4px;text-transform:uppercase;">ARIA Approval Queue</span>
        </div>
        <div style="font-size:26px;font-weight:800;color:#0F172A;font-family:'Space Grotesk',Inter,sans-serif;margin-top:12px;">
          {count} draft{'s' if count != 1 else ''} waiting your review
        </div>
        <div style="font-size:14px;color:#64748B;margin-top:4px;">{today} · {meta['workspace_name']}</div>
      </div>

      <div style="background:#FFFFFF;border:1px solid #E2E8F0;border-radius:8px;padding:14px 18px;margin-bottom:18px;text-align:center;">
        <span style="font-size:13px;color:#475569;">Today, ARIA listened, qualified, and drafted </span>
        <span style="font-size:13px;font-weight:bold;color:#7C35DC;">{count} response{'s' if count != 1 else ''}</span>
        <span style="font-size:13px;color:#475569;"> across your workspace. Approve in one click 👇</span>
      </div>

      {cards}
      {extra_note}

      <div style="text-align:center;margin-top:24px;padding-top:18px;border-top:1px solid #E2E8F0;">
        <table style="margin:0 auto;border-collapse:separate;border-spacing:8px 0;">
          <tr>
            <td>
              <a href="{_app_url()}/app/approvals?action=bulk-approve" style="display:inline-block;padding:11px 22px;border-radius:6px;background:linear-gradient(135deg,#10B981 0%,#059669 100%);color:white;text-decoration:none;font-weight:bold;font-size:13px;letter-spacing:0.6px;">✓ Approve All</a>
            </td>
            <td>
              <a href="{_app_url()}/app/approvals" style="display:inline-block;padding:11px 22px;border-radius:6px;background:linear-gradient(135deg,#4C1D95 0%,#7C35DC 100%);color:white;text-decoration:none;font-weight:bold;font-size:13px;letter-spacing:0.6px;">Open Queue →</a>
            </td>
          </tr>
        </table>
        <div style="font-size:11px;color:#94A3B8;margin-top:14px;">Disable this digest in Settings → Notifications.</div>
      </div>
    </div>
    """


# ─── Resend send ────────────────────────────────────────────────────────
async def _send_digest_email(*, recipient: str, html: str, subject: str) -> Dict[str, Any]:
    integ = integrations_col.find_one({"name": "email"}) or {}
    workspace_key = _dec(integ.get("api_key") or "") if integ.get("api_key") else ""
    api_key = workspace_key or os.environ.get("RESEND_API_KEY") or ""
    if not api_key:
        return {"sent": False, "error": "no_resend_key"}
    from_addr = integ.get("from_address") or os.environ.get("SENDER_EMAIL") or "onboarding@resend.dev"
    from_name = (integ.get("from_name") or "").strip() or "ARIA"
    params = {
        "from": f"{from_name} <{from_addr}>",
        "to": [recipient],
        "subject": subject,
        "html": html,
    }
    saved = resend.api_key
    resend.api_key = api_key
    try:
        result = await asyncio.to_thread(resend.Emails.send, params)
        return {"sent": True, "provider_id": (result or {}).get("id") if isinstance(result, dict) else None}
    except Exception as e:  # noqa: BLE001
        # iter138 — quieter log line; full traceback only at DEBUG level.
        logger.warning("approval_digest: resend send failed: %s", str(e)[:200])
        return {"sent": False, "error": str(e)[:200]}
    finally:
        resend.api_key = saved


# ─── Public run ─────────────────────────────────────────────────────────
async def run_approval_digest(tenant_id: str, recipient: Optional[str] = None, manual: bool = False) -> Dict[str, Any]:
    cfg = _get_cfg(tenant_id)
    target = recipient or cfg.get("send_to_email") or ""
    if not target:
        return {"sent": False, "skipped": True, "reason": "no_recipient"}

    pending = list(
        pending_col.find(
            {"tenant_id": tenant_id, "status": "awaiting_owner_approval"},
            {"_id": 0},
        ).sort("created_at", -1).limit(50)
    )
    count = len(pending)

    # Spec: do not send if queue is empty.
    if count == 0:
        sent_col.insert_one({
            "tenant_id": tenant_id, "recipient": target, "subject": None,
            "skipped": True, "reason": "queue_empty", "draft_count": 0,
            "created_at": _now_iso(),
        })
        return {"sent": False, "skipped": True, "reason": "queue_empty", "draft_count": 0}

    meta = _tenant_meta(tenant_id)
    drafts = [_enrich(d) for d in pending]
    subject = f"[{count}] draft{'s' if count != 1 else ''} waiting your review — ARIA"
    html = _render_digest_html(meta, drafts)
    result = await _send_digest_email(recipient=target, html=html, subject=subject)

    sent_col.insert_one({
        "tenant_id": tenant_id, "recipient": target, "subject": subject,
        "manual": manual, "draft_count": count,
        "sent": bool(result.get("sent")), "provider_id": result.get("provider_id"),
        "error": result.get("error"), "created_at": _now_iso(),
    })

    local_today = (datetime.now(timezone.utc) + timedelta(hours=float(cfg.get("timezone_offset_hours") or 0.0))).strftime("%Y-%m-%d")
    config_col.update_one(
        {"tenant_id": tenant_id},
        {"$set": {"last_sent_date": local_today, "last_sent_at": _now_iso()}},
        upsert=True,
    )
    return {
        "sent": bool(result.get("sent")),
        "draft_count": count,
        "subject": subject,
        "provider_id": result.get("provider_id"),
        "error": result.get("error"),
    }


# ─── REST endpoints ─────────────────────────────────────────────────────
@router.get("/config")
async def get_config(current_user: dict = Depends(get_current_user)):
    tenant_id = current_user.get("tenant_id")
    return _get_cfg(tenant_id) or {
        "enabled": False, "send_to_email": current_user.get("email", ""),
        "send_hour_local": 20, "timezone_offset_hours": 5.5, "weekdays_only": False,
    }


@router.post("/config")
async def save_config(body: DigestConfig, current_user: dict = Depends(get_current_user)):
    tenant_id = current_user.get("tenant_id")
    payload = body.model_dump()
    payload["tenant_id"] = tenant_id
    payload["updated_at"] = _now_iso()
    config_col.update_one(
        {"tenant_id": tenant_id},
        {"$set": payload, "$setOnInsert": {"created_at": _now_iso()}},
        upsert=True,
    )
    return {"saved": True, "config": payload}


@router.post("/send-now")
async def send_now(current_user: dict = Depends(get_current_user)):
    tenant_id = current_user.get("tenant_id")
    cfg = _get_cfg(tenant_id) or {}
    recipient = cfg.get("send_to_email") or current_user.get("email")
    if not recipient:
        raise HTTPException(status_code=400, detail="Set a recipient email in the digest config first.")
    res = await run_approval_digest(tenant_id, recipient=recipient, manual=True)
    # iter138 — convert send failures into structured 503 (matches sibling pattern).
    # Skip-as-success (e.g. queue_empty) is NOT an error — return as-is with 200.
    if isinstance(res, dict) and res.get("sent") is False and not res.get("skipped"):
        from services.notification_errors import classify_send_error
        info = classify_send_error(res.get("error", ""))
        raise HTTPException(status_code=info["status"], detail=info)
    return res


@router.get("/last")
async def last_sent(current_user: dict = Depends(get_current_user)):
    tenant_id = current_user.get("tenant_id")
    doc = sent_col.find_one({"tenant_id": tenant_id}, {"_id": 0}, sort=[("created_at", -1)])
    return doc or {}


# ─── Background loop ────────────────────────────────────────────────────
async def approval_digest_loop():
    """Tick every 60s. For each tenant with enabled=true: if local time
    matches send_hour_local (±5 min window) AND we haven't sent today AND
    there's at least 1 pending draft, fire the digest."""
    while True:
        try:
            for cfg in config_col.find({"enabled": True}, {"_id": 0}):
                tenant_id = cfg.get("tenant_id")
                recipient = cfg.get("send_to_email")
                if not (tenant_id and recipient):
                    continue
                send_hour = int(cfg.get("send_hour_local") or 20)
                tz_off = float(cfg.get("timezone_offset_hours") or 0.0)
                weekdays_only = bool(cfg.get("weekdays_only", False))
                now_utc = datetime.now(timezone.utc)
                local_dt = now_utc + timedelta(hours=tz_off)
                if weekdays_only and local_dt.weekday() >= 5:
                    continue
                target_min_utc = int(((send_hour * 60) - (tz_off * 60)) % 1440)
                cur_min_utc = now_utc.hour * 60 + now_utc.minute
                in_window = 0 <= (cur_min_utc - target_min_utc) <= 5
                local_today = local_dt.strftime("%Y-%m-%d")
                if in_window and cfg.get("last_sent_date") != local_today:
                    print(f"[ApprovalDigest] tenant={tenant_id} → checking queue for {recipient}")
                    try:
                        await run_approval_digest(tenant_id, recipient=recipient, manual=False)
                    except Exception:
                        logger.exception("approval_digest: cron send failed")
        except Exception:
            logger.exception("approval_digest: loop iteration failed")
        await asyncio.sleep(60)


__all__ = ["router", "run_approval_digest", "approval_digest_loop"]
