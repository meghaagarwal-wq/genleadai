"""ARIA — Outreach Dispatch (Batch 5).

Final-mile send-flow wrapper that takes the channel-adaptive composer's
output and dispatches the message via the correct provider:

  channel = whatsapp  → whatsapp_dispatch.send_whatsapp_text (360dialog / Meta)
  channel = email     → routes.pt_email.send_workspace_email (Resend)
  channel = linkedin  → LinkedIn UGC Posts (w_member_social scope) +
                        fallback to `pending_outreach` collection if the
                        OAuth token is missing or the prospect URN is
                        unknown.

This module is the SINGLE chokepoint for outbound message dispatch
triggered from the Intel tab + Morning Brief flows. Every successful
send writes an entry to `outbound_log` so the Insight Feed + reply
tracker stay in sync.

Return shape (uniform across channels):
  {
    "sent": bool,
    "channel": "whatsapp" | "email" | "linkedin",
    "provider": str,                # "360dialog" | "resend" | "linkedin_ugc" | …
    "provider_id": str | None,      # external id for replay/debug
    "error": str | None,            # human-readable on failure
    "logged_only": bool,            # true when no provider is configured;
                                    # message was drafted + saved but not sent
  }
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from deps import db
from security.encryption import decrypt as _dec

logger = logging.getLogger("outreach_dispatch")

outbound_log_col = db["outbound_log"]
pending_outreach_col = db["pending_outreach"]
configs_col = db["integration_configs"]
pt_leads_col = db["pt_leads"]
leads_col = db["leads"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Lead resolution ────────────────────────────────────────────────────
def _resolve_lead(tenant_id: str, lead_id: str) -> Dict[str, Any]:
    doc = pt_leads_col.find_one({"id": lead_id, "tenant_id": tenant_id}, {"_id": 0})
    if doc:
        return doc
    from bson import ObjectId
    try:
        legacy = leads_col.find_one({"_id": ObjectId(lead_id), "tenant_id": tenant_id})
        if legacy:
            return {k: v for k, v in legacy.items() if k != "_id"}
    except Exception:
        pass
    return {}


# ─── Provider: Email (Resend via send_workspace_email) ──────────────────
async def _send_email(
    *, tenant_id: str, lead: Dict[str, Any], message: Any
) -> Dict[str, Any]:
    """`message` is `{subject, body}` for the email channel."""
    to_addr = (lead.get("email") or "").strip()
    if not to_addr:
        return {"sent": False, "channel": "email", "provider": "resend",
                "error": "lead has no email address", "logged_only": False}

    if isinstance(message, dict):
        subject = (message.get("subject") or "Quick idea")[:120]
        body = message.get("body") or ""
    else:
        subject = "Quick idea"
        body = str(message)

    try:
        from routes.pt_email import send_workspace_email
    except Exception as e:
        return {"sent": False, "channel": "email", "provider": "resend",
                "error": f"email helper unavailable: {e}", "logged_only": False}

    # Convert plain-text body → simple <p>-wrapped HTML
    html_body = "".join(
        f"<p style='margin:0 0 12px 0;font-family:Inter,sans-serif;font-size:14px;line-height:1.55;color:#0F172A;'>{p}</p>"
        for p in (body.split("\n\n") if body else [""])
    )

    try:
        result = await send_workspace_email(
            to=to_addr,
            subject=subject,
            html_body=html_body,
            uploads_dir=os.environ.get("UPLOADS_DIR") or "/tmp/uploads",
            append_signature=True,
        )
        return {
            "sent": bool(result.get("ok")),
            "channel": "email",
            "provider": "resend",
            "provider_id": result.get("provider_id"),
            "to": to_addr,
            "subject": subject,
            "logged_only": False,
        }
    except Exception as e:  # noqa: BLE001 — surface friendly error
        logger.exception("outreach_dispatch: email send failed")
        return {"sent": False, "channel": "email", "provider": "resend",
                "error": str(e)[:240], "logged_only": False}


# ─── Provider: WhatsApp (whatsapp_dispatch) ─────────────────────────────
async def _send_whatsapp(
    *, tenant_id: str, lead: Dict[str, Any], message: Any
) -> Dict[str, Any]:
    phone = lead.get("phone") or lead.get("whatsapp") or ""
    if not phone:
        return {"sent": False, "channel": "whatsapp", "provider": "whatsapp",
                "error": "lead has no phone/whatsapp number", "logged_only": False}
    body = message if isinstance(message, str) else json.dumps(message)
    try:
        from whatsapp_dispatch import send_whatsapp_text
        result = await send_whatsapp_text(phone, body, tenant_id=tenant_id)
    except Exception as e:  # noqa: BLE001
        logger.exception("outreach_dispatch: whatsapp send failed")
        return {"sent": False, "channel": "whatsapp", "provider": "whatsapp",
                "error": str(e)[:240], "logged_only": False}

    return {
        "sent": bool(result.get("sent")),
        "channel": "whatsapp",
        "provider": result.get("provider") or "whatsapp",
        "provider_id": result.get("message_id"),
        "to": phone,
        "error": result.get("error"),
        "logged_only": bool(result.get("logged_only")),
    }


# ─── Provider: LinkedIn (UGC Posts API w/ pending_outreach fallback) ────
async def _send_linkedin(
    *, tenant_id: str, lead: Dict[str, Any], message: Any
) -> Dict[str, Any]:
    """Best-effort LinkedIn dispatch.

    LinkedIn's official API does NOT expose 1:1 DM endpoints publicly, so
    we cannot programmatically send a DM. Instead:

      1. If a LinkedIn OAuth integration is connected AND the lead has a
         `linkedin_url`, post the message as a *public mention* via the
         UGC Posts API (commenting on the prospect's profile is the
         closest legal channel). This requires `w_member_social` scope.
      2. Otherwise, push to `pending_outreach` with status
         `linkedin_drafted_awaiting_manual_send` so the founder can copy
         it into LinkedIn manually.

    Both paths return `sent=true` for the first case and
    `logged_only=true` for the second — so callers see a consistent
    contract.
    """
    body = message if isinstance(message, str) else json.dumps(message)

    cfg_doc = configs_col.find_one(
        {"tenant_id": tenant_id, "integration_type": "linkedin"},
        {"_id": 0, "config": 1, "status": 1},
    ) or {}
    cfg = cfg_doc.get("config") or {}
    access_token = _dec(cfg.get("access_token") or "") if cfg.get("access_token") else None
    linkedin_user_urn = cfg.get("user_urn")  # e.g. urn:li:person:abcd1234

    # Fallback path — log to pending_outreach.
    def _log_pending(reason: str) -> Dict[str, Any]:
        pending_outreach_col.insert_one({
            "tenant_id": tenant_id,
            "lead_id": lead.get("id"),
            "channel": "linkedin",
            "status": "linkedin_drafted_awaiting_manual_send",
            "reason": reason,
            "body": body,
            "linkedin_url": lead.get("linkedin_url"),
            "created_at": _now_iso(),
        })
        return {
            "sent": False,
            "channel": "linkedin",
            "provider": "pending_outreach",
            "to": lead.get("linkedin_url"),
            "error": None,
            "note": reason,
            "logged_only": True,
        }

    if not access_token or not linkedin_user_urn:
        return _log_pending(
            "LinkedIn OAuth not connected — message drafted and saved. "
            "Connect LinkedIn on /app/integrations to send programmatically."
        )

    # UGC Posts API — public-feed post (NOT a DM). We mark it as PUBLIC
    # visibility. Caller decides whether this matches their workflow.
    url = "https://api.linkedin.com/v2/ugcPosts"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    payload = {
        "author": linkedin_user_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": body[:3000]},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code >= 400:
            return _log_pending(
                f"LinkedIn UGC post rejected ({resp.status_code}): {resp.text[:180]}"
            )
        data = resp.json() if resp.text else {}
        return {
            "sent": True,
            "channel": "linkedin",
            "provider": "linkedin_ugc",
            "provider_id": data.get("id") or resp.headers.get("X-RestLi-Id"),
            "logged_only": False,
        }
    except Exception as e:  # noqa: BLE001
        logger.exception("outreach_dispatch: linkedin post failed")
        return _log_pending(f"LinkedIn API error: {str(e)[:160]}")


# ─── Public entry point ─────────────────────────────────────────────────
async def dispatch_outreach(
    *,
    tenant_id: str,
    lead_id: str,
    channel: str,
    composed: Dict[str, Any],
    actor_user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Single chokepoint: takes the output of
    `services.intel_service.compose_message` and sends it via the right
    provider.

    Args
    ────
      composed: the dict returned by compose_message — has keys
                {channel, message, ai_powered}.
    """
    channel = (channel or "email").strip().lower()
    if channel not in {"whatsapp", "email", "linkedin"}:
        return {"sent": False, "error": f"unsupported channel: {channel}", "channel": channel}

    lead = _resolve_lead(tenant_id, lead_id)
    if not lead:
        return {"sent": False, "error": "lead not found", "channel": channel}

    message = composed.get("message") if isinstance(composed, dict) else composed

    if channel == "email":
        result = await _send_email(tenant_id=tenant_id, lead=lead, message=message)
    elif channel == "whatsapp":
        result = await _send_whatsapp(tenant_id=tenant_id, lead=lead, message=message)
    else:
        result = await _send_linkedin(tenant_id=tenant_id, lead=lead, message=message)

    # Audit log — every attempt (sent or not) is recorded for reply tracking.
    outbound_log_col.insert_one({
        "tenant_id": tenant_id,
        "lead_id": lead_id,
        "channel": channel,
        "provider": result.get("provider"),
        "provider_id": result.get("provider_id"),
        "sent": bool(result.get("sent")),
        "logged_only": bool(result.get("logged_only")),
        "to": result.get("to"),
        "subject": result.get("subject"),
        "message_preview": (
            (message.get("body") if isinstance(message, dict) else str(message)) or ""
        )[:280],
        "ai_powered": bool((composed or {}).get("ai_powered")),
        "actor_user_id": actor_user_id,
        "error": result.get("error"),
        "created_at": _now_iso(),
    })

    return result


__all__ = ["dispatch_outreach"]
