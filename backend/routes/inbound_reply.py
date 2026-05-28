"""ARIA — Inbound Reply Tracker (Batch 6).

Closes the second half of the loop: when a prospect replies on ANY
channel (email / WhatsApp / LinkedIn), this module:

  1. Captures the reply payload.
  2. Matches it back to a tenant + lead via the channel-specific
     correlation key (Reply-To token / phone_number_id / share_urn).
  3. Inserts a normalised entry into the lead timeline
     (`activities` collection — pietential workspace).
  4. Bumps the lead's `stage` to `replied` (and remembers prior stage).
  5. Runs a silent Claude qualification check on the reply text.
  6. Drafts ARIA's next message via the existing intel composer and
     queues it in `pending_outreach` with status
     `awaiting_owner_approval` — DOES NOT auto-send.

Endpoints
─────────
  POST /api/webhooks/resend       — Resend events (Svix-signed)
  POST /api/webhooks/360dialog    — 360dialog WhatsApp inbound (HMAC-signed)
  GET  /api/webhooks/health       — uptime probe

Polling
───────
  linkedin_comment_poller_loop()   — every 5 min, polls comments on
  every UGC post we created.

V10
───
  All Claude calls go through `services.claude_service.claude_call`.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import APIRouter, HTTPException, Request

from deps import db
from security.encryption import decrypt as _dec
from services.claude_service import claude_call, TaskType, ClaudeServiceError
from services.intel_service import compose_message

logger = logging.getLogger("inbound_reply")
router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

# Collections
outbound_log_col = db["outbound_log"]
pending_outreach_col = db["pending_outreach"]
activities_col = db["activities"]
inbound_messages_col = db["inbound_messages"]
configs_col = db["integration_configs"]
pt_leads_col = db["pt_leads"]
leads_col = db["leads"]
intel_profiles_col = db["intel_profiles"]
linkedin_polled_col = db["linkedin_comment_polling"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Idempotency ────────────────────────────────────────────────────────
inbound_messages_col.create_index([("provider", 1), ("external_id", 1)], unique=False)


def _already_processed(provider: str, external_id: str) -> bool:
    if not external_id:
        return False
    return inbound_messages_col.find_one(
        {"provider": provider, "external_id": external_id},
        {"_id": 1},
    ) is not None


# ─── Lead resolution helpers ────────────────────────────────────────────
def _find_lead_by_email(tenant_id: Optional[str], email: str) -> Optional[Dict[str, Any]]:
    if not email:
        return None
    email = email.strip().lower()
    q: Dict[str, Any] = {"email": {"$regex": f"^{email}$", "$options": "i"}}
    if tenant_id:
        q["tenant_id"] = tenant_id
    return pt_leads_col.find_one(q, {"_id": 0})


def _find_lead_by_phone(tenant_id: Optional[str], phone: str) -> Optional[Dict[str, Any]]:
    if not phone:
        return None
    norm = "".join(c for c in phone if c.isdigit())
    q: Dict[str, Any] = {"$or": [
        {"phone": {"$regex": norm}},
        {"whatsapp": {"$regex": norm}},
    ]}
    if tenant_id:
        q["tenant_id"] = tenant_id
    return pt_leads_col.find_one(q, {"_id": 0})


def _last_outbound_for_lead(tenant_id: str, lead_id: str, channel: str) -> Optional[Dict[str, Any]]:
    return outbound_log_col.find_one(
        {"tenant_id": tenant_id, "lead_id": lead_id, "channel": channel, "sent": True},
        {"_id": 0},
        sort=[("created_at", -1)],
    )


# ─── Silent qualification + reply drafting ──────────────────────────────
async def _qualify_reply(tenant_id: str, lead_id: str, reply_text: str, prior_summary: str) -> Dict[str, Any]:
    """Silent Claude qualification — returns {intent, sentiment, urgency, summary,
    next_action_hint}. Never raises; falls back to a heuristic on failure."""
    if not reply_text or len(reply_text.strip()) < 3:
        return {
            "intent": "unclear",
            "sentiment": "neutral",
            "urgency": "low",
            "summary": "Empty / non-textual reply",
            "next_action_hint": "Wait for a more substantive reply.",
        }
    system = (
        "You are ARIA's reply analyst. Given a single inbound reply from a "
        "B2B prospect, return STRICT JSON only — no preamble, no markdown."
    )
    prompt = f"""PRIOR CONTEXT (one-liner about the prospect):
{prior_summary or '(none)'}

PROSPECT'S REPLY:
\"\"\"
{reply_text[:1500]}
\"\"\"

Classify the reply. Return ONLY this JSON:
{{
  "intent": one of [positive, interested, neutral_followup, objection, not_interested, unsubscribe, unclear],
  "sentiment": one of [positive, neutral, negative, urgent],
  "urgency": one of [high, med, low],
  "summary": 1-sentence summary,
  "next_action_hint": 1-sentence suggestion for ARIA's next move
}}"""
    try:
        result = await claude_call(
            task_type=TaskType.SIGNAL_CLASSIFICATION,
            system=system,
            prompt=prompt,
            tenant_id=tenant_id,
            session_id=f"qualify-reply-{lead_id}",
            response_format="json",
        )
        if not isinstance(result, dict):
            raise ClaudeServiceError("non-dict response")
        return {
            "intent": result.get("intent") or "unclear",
            "sentiment": result.get("sentiment") or "neutral",
            "urgency": result.get("urgency") or "med",
            "summary": (result.get("summary") or "")[:300],
            "next_action_hint": (result.get("next_action_hint") or "")[:300],
        }
    except Exception as e:  # noqa: BLE001
        logger.warning("qualify_reply: claude failed lead=%s: %s", lead_id, e)
        low = reply_text.lower()
        if any(k in low for k in ("unsubscribe", "stop", "remove me", "do not contact")):
            intent = "unsubscribe"
        elif any(k in low for k in ("not interested", "no thanks", "no thank you", "not a fit")):
            intent = "not_interested"
        elif any(k in low for k in ("yes", "sure", "interested", "book", "schedule", "let's do")):
            intent = "interested"
        elif "?" in reply_text:
            intent = "neutral_followup"
        else:
            intent = "unclear"
        return {
            "intent": intent, "sentiment": "neutral", "urgency": "low",
            "summary": reply_text[:200],
            "next_action_hint": "Founder review recommended.",
        }


async def _draft_aria_reply(tenant_id: str, lead_id: str, channel: str, reply_text: str) -> Optional[Dict[str, Any]]:
    """Generate ARIA's next message using the same channel-adaptive composer,
    biased toward acknowledging the prospect's last reply."""
    profile = intel_profiles_col.find_one(
        {"tenant_id": tenant_id, "lead_id": lead_id}, {"_id": 0}
    )
    if not profile:
        return None  # no intel → skip drafting; founder will handle manually

    lead = pt_leads_col.find_one({"id": lead_id, "tenant_id": tenant_id}, {"_id": 0})
    if not lead:
        # Try legacy
        from bson import ObjectId
        try:
            lead = leads_col.find_one({"_id": ObjectId(lead_id), "tenant_id": tenant_id})
            if lead:
                lead = {k: v for k, v in lead.items() if k != "_id"}
        except Exception:
            lead = None
    if not lead:
        return None

    first = lead.get("first_name") or "there"
    composed = await compose_message(
        tenant_id=tenant_id,
        lead_id=lead_id,
        channel=channel if channel in ("whatsapp", "email", "linkedin") else "email",
        lead_meta={
            "name": f"{first} {lead.get('last_name','')}".strip() or lead.get("email", "Lead"),
            "first_name": first,
            "company": lead.get("company_name") or lead.get("company") or "",
        },
        profile=profile,
        user_steer=f"The prospect just replied with: \"{reply_text[:500]}\". Acknowledge specifically, then move the conversation forward.",
    )
    return composed


# ─── Final-mile: queue + timeline + status flip ─────────────────────────
async def _process_inbound(
    *,
    tenant_id: str,
    lead: Dict[str, Any],
    channel: str,
    reply_text: str,
    external_id: str,
    raw: Dict[str, Any],
    sender_label: Optional[str] = None,
) -> Dict[str, Any]:
    """Common path for all 3 channels after the lead is matched."""
    lead_id = lead.get("id") or str(lead.get("_id", ""))
    prior_stage = lead.get("stage")

    # 1) Insert normalised inbound record (for analytics + idempotency)
    inbound_messages_col.insert_one({
        "tenant_id": tenant_id,
        "lead_id": lead_id,
        "channel": channel,
        "provider": channel,
        "external_id": external_id,
        "from": sender_label,
        "text": reply_text,
        "received_at": _now_iso(),
        "raw": raw,
    })

    # 2) Activity / timeline event (pietential workspace pattern)
    activities_col.insert_one({
        "tenant_id": tenant_id,
        "lead_id": lead_id,
        "actor_user_id": "aria",
        "activity_type": "inbound_reply",
        "channel": channel,
        "subject": f"Reply via {channel}",
        "body": reply_text[:1000],
        "metadata": {"external_id": external_id, "from": sender_label},
        "created_at": _now_iso(),
    })

    # 3) Stage flip → 'replied' (preserve prior_stage for audit)
    if prior_stage != "replied":
        pt_leads_col.update_one(
            {"id": lead_id, "tenant_id": tenant_id},
            {"$set": {
                "stage": "replied",
                "prior_stage": prior_stage,
                "last_replied_at": _now_iso(),
                "last_reply_channel": channel,
            }},
        )

    # 4) Silent Claude qualification
    profile = intel_profiles_col.find_one(
        {"tenant_id": tenant_id, "lead_id": lead_id}, {"_id": 0, "summary": 1}
    ) or {}
    qualification = await _qualify_reply(
        tenant_id=tenant_id,
        lead_id=lead_id,
        reply_text=reply_text,
        prior_summary=profile.get("summary", ""),
    )

    # 5) Draft ARIA's next move — but DO NOT auto-send.
    drafted = await _draft_aria_reply(tenant_id, lead_id, channel, reply_text)
    queued_draft = False
    if drafted and qualification["intent"] not in ("unsubscribe", "not_interested"):
        msg = drafted.get("message")
        if isinstance(msg, dict):
            body_preview = msg.get("body", "")[:600]
            subject = msg.get("subject")
        else:
            body_preview = str(msg or "")[:600]
            subject = None
        pending_outreach_col.insert_one({
            "tenant_id": tenant_id,
            "lead_id": lead_id,
            "channel": channel,
            "status": "awaiting_owner_approval",
            "reason": "Auto-drafted reply to inbound — owner review required before send.",
            "subject": subject,
            "body": body_preview,
            "qualification": qualification,
            "in_reply_to_external_id": external_id,
            "ai_powered": bool(drafted.get("ai_powered")),
            "created_at": _now_iso(),
        })
        queued_draft = True

    return {
        "ok": True,
        "lead_id": lead_id,
        "channel": channel,
        "stage_changed_to": "replied" if prior_stage != "replied" else None,
        "qualification": qualification,
        "drafted": queued_draft,
    }


# ─── Resend webhook ─────────────────────────────────────────────────────
def _resend_secret(tenant_id: Optional[str] = None) -> Optional[str]:
    """Pull the Svix signing secret. Resend webhook secret can be tenant-
    specific (stored in integration_configs.config.webhook_secret) OR
    a platform-default in env RESEND_WEBHOOK_SECRET."""
    if tenant_id:
        doc = configs_col.find_one(
            {"tenant_id": tenant_id, "integration_type": "resend"},
            {"_id": 0, "config": 1},
        )
        if doc:
            cfg = doc.get("config") or {}
            raw = cfg.get("webhook_secret")
            if raw:
                try:
                    return _dec(raw)
                except Exception:
                    return raw  # may be plaintext
    return os.environ.get("RESEND_WEBHOOK_SECRET") or None


def _verify_resend(raw_body: bytes, headers: Dict[str, str], secret: str) -> bool:
    """Svix-style verification. We import svix lazily so the module
    doesn't hard-depend on it if a tenant hasn't enabled signature
    verification yet."""
    try:
        from svix.webhooks import Webhook, WebhookVerificationError  # type: ignore
    except Exception:
        logger.warning("svix not installed — accepting webhook WITHOUT signature check.")
        return True
    try:
        wh = Webhook(secret)
        wh.verify(raw_body, headers)
        return True
    except WebhookVerificationError:
        return False


@router.post("/resend")
async def resend_webhook(request: Request):
    raw = await request.body()
    headers = {
        "svix-id": request.headers.get("svix-id", ""),
        "svix-timestamp": request.headers.get("svix-timestamp", ""),
        "svix-signature": request.headers.get("svix-signature", ""),
    }

    # Parse first to derive a tenant hint from `to` for verification key
    try:
        event = json.loads(raw.decode("utf-8") or "{}")
    except Exception:
        raise HTTPException(status_code=400, detail="invalid JSON")

    event_type = event.get("type") or ""
    data = event.get("data") or {}

    # Optional signature verification
    secret = _resend_secret(None)  # try platform default first
    if secret and all(headers.values()):
        if not _verify_resend(raw, headers, secret):
            logger.warning("resend webhook: invalid signature")
            raise HTTPException(status_code=400, detail="invalid signature")

    # Only act on inbound + bounce + complaint events
    if event_type not in {"email.received", "email.bounced", "email.complained"}:
        return {"ok": True, "ignored": event_type}

    external_id = data.get("id") or data.get("email_id") or ""
    if _already_processed("email", external_id):
        return {"ok": True, "duplicate": True}

    # Lead resolution
    if event_type == "email.received":
        from_email = (data.get("from") or "").strip()
        to_list = data.get("to") or []
        # Tenant inference: scan ALL tenants for a lead with this from-email
        sender = from_email
        match = _find_lead_by_email(None, sender)
        if not match:
            inbound_messages_col.insert_one({
                "provider": "email", "external_id": external_id,
                "channel": "email", "from": sender, "to": to_list,
                "unmatched": True, "received_at": _now_iso(), "raw": event,
            })
            return {"ok": True, "matched": False, "reason": "no lead with this from-email"}
        tenant_id = match["tenant_id"]
        return await _process_inbound(
            tenant_id=tenant_id, lead=match, channel="email",
            reply_text=data.get("subject") or "",  # body fetched via Received Emails API in future iter
            external_id=external_id, raw=event, sender_label=sender,
        )

    # Bounce / complaint → just timeline event, no draft
    elif event_type in {"email.bounced", "email.complained"}:
        ob = outbound_log_col.find_one(
            {"provider_id": data.get("email_id")},
            {"_id": 0, "tenant_id": 1, "lead_id": 1},
        ) or {}
        if not ob:
            return {"ok": True, "matched": False}
        activities_col.insert_one({
            "tenant_id": ob["tenant_id"], "lead_id": ob["lead_id"],
            "actor_user_id": "system", "activity_type": event_type.replace("email.", "email_"),
            "channel": "email", "subject": event_type, "body": json.dumps(data)[:400],
            "metadata": {"raw": data}, "created_at": _now_iso(),
        })
        return {"ok": True, "event": event_type, "lead_id": ob.get("lead_id")}

    return {"ok": True}


# ─── 360dialog WhatsApp webhook ─────────────────────────────────────────
def _whatsapp_secret(tenant_id: Optional[str] = None) -> Optional[str]:
    if tenant_id:
        doc = configs_col.find_one(
            {"tenant_id": tenant_id, "integration_type": "360dialog"},
            {"_id": 0, "config": 1},
        )
        if doc:
            cfg = doc.get("config") or {}
            raw = cfg.get("webhook_secret")
            if raw:
                try:
                    return _dec(raw)
                except Exception:
                    return raw
    return os.environ.get("WHATSAPP_WEBHOOK_SECRET") or None


def _verify_360dialog(raw_body: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


@router.post("/360dialog")
async def whatsapp_webhook(request: Request):
    raw = await request.body()
    received_sig = request.headers.get("x-360dialog-signature")

    secret = _whatsapp_secret(None)
    if secret and received_sig:
        if not _verify_360dialog(raw, received_sig, secret):
            logger.warning("360dialog webhook: invalid signature")
            raise HTTPException(status_code=403, detail="invalid signature")

    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except Exception:
        raise HTTPException(status_code=400, detail="invalid JSON")

    if payload.get("object") != "whatsapp_business_account":
        return {"ok": True, "ignored": True}

    results: List[Dict[str, Any]] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value") or {}
            metadata = value.get("metadata") or {}
            phone_number_id = metadata.get("phone_number_id")
            tenant_cfg = configs_col.find_one(
                {"integration_type": "360dialog", "config.phone_number_id": phone_number_id},
                {"_id": 0, "tenant_id": 1},
            )
            tenant_id = (tenant_cfg or {}).get("tenant_id")

            for msg in value.get("messages", []) or []:
                if msg.get("type") != "text":
                    continue
                external_id = msg.get("id") or ""
                if _already_processed("whatsapp", external_id):
                    results.append({"duplicate": True, "id": external_id})
                    continue
                from_number = msg.get("from") or ""
                text = ((msg.get("text") or {}).get("body") or "").strip()
                if not text:
                    continue
                lead = _find_lead_by_phone(tenant_id, from_number)
                if not lead:
                    inbound_messages_col.insert_one({
                        "provider": "whatsapp", "external_id": external_id,
                        "channel": "whatsapp", "from": from_number,
                        "unmatched": True, "tenant_id": tenant_id,
                        "received_at": _now_iso(), "raw": msg,
                    })
                    results.append({"matched": False, "from": from_number})
                    continue
                res = await _process_inbound(
                    tenant_id=lead["tenant_id"], lead=lead, channel="whatsapp",
                    reply_text=text, external_id=external_id, raw=msg,
                    sender_label=from_number,
                )
                results.append(res)

    return {"ok": True, "results": results}


# ─── Health probe ───────────────────────────────────────────────────────
@router.get("/health")
async def webhook_health():
    return {"ok": True, "providers": ["resend", "360dialog", "linkedin_polling"]}


# ─── LinkedIn comment polling ───────────────────────────────────────────
LINKEDIN_API_BASE = "https://api.linkedin.com"


async def _fetch_linkedin_comments(access_token: str, share_urn: str) -> List[Dict[str, Any]]:
    """Best-effort poll. Returns [] on any failure (we'll retry on the
    next tick)."""
    url = f"{LINKEDIN_API_BASE}/v2/socialActions/{share_urn}/comments"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(url, headers=headers, params={"start": 0, "count": 50})
        if resp.status_code != 200:
            logger.warning("linkedin poll %s → %s", share_urn, resp.status_code)
            return []
        return (resp.json() or {}).get("elements", [])
    except Exception:
        logger.exception("linkedin poll: fetch error")
        return []


async def _poll_linkedin_once():
    """One pass: for each tenant with linkedin OAuth, poll every share
    URN we've stored outbound posts for."""
    for cfg_doc in configs_col.find(
        {"integration_type": "linkedin"},
        {"_id": 0, "tenant_id": 1, "config": 1},
    ):
        tenant_id = cfg_doc.get("tenant_id")
        cfg = cfg_doc.get("config") or {}
        token = _dec(cfg.get("access_token") or "") if cfg.get("access_token") else None
        if not token:
            continue
        # All outbound LinkedIn posts for this tenant
        posts = outbound_log_col.find(
            {"tenant_id": tenant_id, "channel": "linkedin", "provider": "linkedin_ugc", "sent": True},
            {"_id": 0, "provider_id": 1, "lead_id": 1, "created_at": 1},
        )
        for post in posts:
            share_urn = post.get("provider_id")
            if not share_urn:
                continue
            comments = await _fetch_linkedin_comments(token, share_urn)
            for c in comments:
                comment_urn = c.get("$URN") or c.get("urn") or c.get("commentUrn") or ""
                if not comment_urn or _already_processed("linkedin", comment_urn):
                    continue
                actor = c.get("actor") or ""
                message = ((c.get("message") or {}).get("text") or "").strip()
                if not message:
                    continue
                # We can't reliably map actor URN → our lead, so we attach
                # the comment to the lead the original post was directed
                # at (`outbound_log.lead_id`).
                lead_id = post.get("lead_id")
                lead = pt_leads_col.find_one({"id": lead_id, "tenant_id": tenant_id}, {"_id": 0}) if lead_id else None
                if not lead:
                    inbound_messages_col.insert_one({
                        "provider": "linkedin", "external_id": comment_urn,
                        "channel": "linkedin", "from": actor, "share_urn": share_urn,
                        "unmatched": True, "tenant_id": tenant_id,
                        "received_at": _now_iso(), "raw": c,
                    })
                    continue
                await _process_inbound(
                    tenant_id=tenant_id, lead=lead, channel="linkedin",
                    reply_text=message, external_id=comment_urn, raw=c,
                    sender_label=actor,
                )
            linkedin_polled_col.update_one(
                {"tenant_id": tenant_id, "share_urn": share_urn},
                {"$set": {"last_polled_at": _now_iso()}},
                upsert=True,
            )


async def linkedin_comment_poller_loop():
    """Background loop: poll every 5 min."""
    while True:
        try:
            await _poll_linkedin_once()
        except Exception:
            logger.exception("linkedin_comment_poller_loop: iteration failed")
        await asyncio.sleep(300)


__all__ = [
    "router",
    "linkedin_comment_poller_loop",
    "_process_inbound",  # exported for tests
    "_qualify_reply",
]
