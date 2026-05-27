"""iter108 — ACTION 3 (continued): WhatsApp Cloud API webhooks extracted.

Two endpoints:
  - GET  /api/webhooks/whatsapp   — Meta hub.challenge handshake
  - POST /api/webhooks/whatsapp   — inbound message + delivery-status receiver

Pipeline preserved 1:1 from server.py:
  0. HMAC signature verification (Meta X-Hub-Signature-256 / 360dialog X-D360-Token)
  1. Tenant resolution from phone_number_id metadata
  2. Insight-card command short-circuit (Send/Dismiss via WhatsApp)
  3. STOP keyword → opt-out
  4. 3-layer classification (trigger → contact/lead → Claude)
  5. Lead path: pause touchpoints, journey/outreach reply hooks, sentiment,
     opt-in stamp, conversation mirror, CRM event, activity log

Dependencies all imported lazily where they belong to keep this router
side-effect-free at module load.
"""
from __future__ import annotations

import hashlib
import hmac as _hmac
import json
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request, Response

from deps import activities_collection, aria_conversations_collection, db, leads_collection
from routes.classification import classify_inbound
from routes.compliance import is_stop_keyword, opt_out_phone
from routes.health_engine import classify_sentiment as health_classify_sentiment
from routes.outreach import handle_inbound_reply as outreach_handle_reply
from routes.touchpoint_engine import pause_lead

router = APIRouter(tags=["iter108-webhooks-whatsapp"])


def _normalize_phone(phone: str) -> str:
    """Strip non-digits from a phone number string."""
    return "".join(c for c in (phone or "") if c.isdigit())


@router.get("/api/webhooks/whatsapp")
async def whatsapp_webhook_verify(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
):
    """Meta WhatsApp Cloud API webhook verification (GET hub.challenge echo)."""
    expected = os.getenv("WHATSAPP_VERIFY_TOKEN")
    if not expected:
        raise HTTPException(status_code=503, detail="WHATSAPP_VERIFY_TOKEN env not set")
    if hub_mode != "subscribe" or hub_verify_token != expected:
        raise HTTPException(status_code=403, detail="Invalid verification token or mode")
    return Response(content=hub_challenge or "", media_type="text/plain", status_code=200)


@router.post("/api/webhooks/whatsapp")
async def whatsapp_webhook_receive(request: Request):
    """Receive inbound WhatsApp messages and delivery status updates."""
    # Late imports — these live in server.py and would circular at module load.
    from server import send_whatsapp_text  # noqa: WPS433

    # ── 0. Signature verification ────────────────────────────────────────
    raw_body = await request.body()
    meta_sig = request.headers.get("X-Hub-Signature-256") or request.headers.get("x-hub-signature-256")
    d360_token = request.headers.get("X-D360-Token") or request.headers.get("x-d360-token")
    meta_secret = os.getenv("WHATSAPP_APP_SECRET")
    d360_secret = os.getenv("DIALOG360_WEBHOOK_TOKEN")
    if meta_sig:
        if not meta_secret:
            print("[whatsapp_webhook] WARN: Meta signature present but WHATSAPP_APP_SECRET not set — allowing for now")
        else:
            expected = "sha256=" + _hmac.new(meta_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
            if not _hmac.compare_digest(expected, meta_sig.strip()):
                raise HTTPException(status_code=401, detail="Invalid Meta webhook signature")
    elif d360_secret and d360_token:
        if not _hmac.compare_digest(d360_secret, d360_token.strip()):
            raise HTTPException(status_code=401, detail="Invalid 360dialog webhook token")
    elif meta_secret or d360_secret:
        print("[whatsapp_webhook] WARN: signature secret configured but no signature header on inbound payload")

    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except Exception:
        payload = {}

    try:
        for entry in payload.get("entry", []) or []:
            for change in entry.get("changes", []) or []:
                value = change.get("value", {}) or {}
                phone_number_id = (value.get("metadata") or {}).get("phone_number_id")
                tenant = None
                if phone_number_id:
                    tenant = db["tenants"].find_one(
                        {"settings.whatsapp.providers.meta.phone_number_id": phone_number_id},
                        {"_id": 0},
                    )
                if not tenant:
                    tenant = db["tenants"].find_one({}, {"_id": 0})

                for msg in value.get("messages", []) or []:
                    if msg.get("type") != "text":
                        continue
                    from_phone = msg.get("from")
                    body = (msg.get("text") or {}).get("body", "")
                    tenant_id = tenant.get("id") if tenant else None

                    if tenant_id:
                        # iter105 — FIX 15: Send/Dismiss insight-card command short-circuit
                        try:
                            from routes.iter105_fixes import parse_whatsapp_command
                            cmd_result = parse_whatsapp_command(body, from_phone or "", tenant_id)
                            if cmd_result and cmd_result.get("matched"):
                                try:
                                    await send_whatsapp_text(tenant_id, from_phone or "", cmd_result["confirmation_msg"])
                                except Exception as _e:
                                    print(f"[whatsapp] command confirmation send failed: {_e}")
                                continue
                        except Exception as _e:
                            print(f"[whatsapp] insight command parse error: {_e}")

                        if is_stop_keyword(body):
                            opt_out_phone(tenant_id, from_phone or "", reason="stop_keyword")
                            print(f"[whatsapp] STOP keyword from {from_phone} on tenant {tenant_id}")
                            continue

                        cls = await classify_inbound(tenant_id, from_phone or "", body)
                        action = cls.get("action", "neutral_opener")

                        if action in ("continue_lead", "create_lead_or_continue"):
                            normalized_from = _normalize_phone(from_phone or "")
                            last10 = normalized_from[-10:] if len(normalized_from) >= 10 else normalized_from
                            candidate = None
                            if normalized_from:
                                candidate = leads_collection.find_one({"tenant_id": tenant_id, "phone": from_phone}, {"_id": 1, "id": 1})
                                if not candidate and last10:
                                    candidate = leads_collection.find_one(
                                        {"tenant_id": tenant_id, "phone": {"$regex": f"{last10}$"}},
                                        {"_id": 1, "id": 1},
                                    )
                            if candidate:
                                lead_id = candidate.get("id") or str(candidate.get("_id"))
                                pause_lead(tenant_id, lead_id)
                                try:
                                    from routes.touchpoint_engine import handle_inbound_reply_for_journey
                                    handle_inbound_reply_for_journey(tenant_id, lead_id, body)
                                except Exception as _e:
                                    print(f"[whatsapp] journey branch handler error: {_e}")
                                try:
                                    outreach_handle_reply(tenant_id, lead_id, body)
                                except Exception as _e:
                                    print(f"[whatsapp] outreach_handle_reply error: {_e}")
                                sentiment = "neutral"
                                try:
                                    sentiment = await health_classify_sentiment(body)
                                except Exception:
                                    pass
                                leads_collection.update_one(
                                    {"id": lead_id, "tenant_id": tenant_id},
                                    {"$set": {
                                        "opted_in": True,
                                        "opted_in_at": datetime.now(timezone.utc).isoformat(),
                                        "opted_in_source": "replied_first",
                                        "latest_sentiment": sentiment,
                                        "last_activity_at": datetime.now(timezone.utc).isoformat(),
                                        "stale": False,
                                    }},
                                )
                                aria_conversations_collection.update_one(
                                    {"lead_id": lead_id, "tenant_id": tenant_id},
                                    {"$set": {
                                        "latest_sentiment": sentiment,
                                        "last_inbound_at": datetime.now(timezone.utc).isoformat(),
                                    }},
                                    upsert=True,
                                )
                                try:
                                    if sentiment in ("negative", "urgent"):
                                        from routes.crm_sync import fire_event as _cfe
                                        _cfe(tenant_id, {"id": lead_id, "tenant_id": tenant_id}, f"sentiment.{sentiment}", {"message_preview": body[:140]})
                                except Exception:
                                    pass
                                activities_collection.insert_one({
                                    "lead_id": lead_id,
                                    "tenant_id": tenant_id,
                                    "user_id": "whatsapp_webhook",
                                    "activity_type": "whatsapp_received",
                                    "subject": "WhatsApp reply received",
                                    "body": body[:1000],
                                    "outcome": None,
                                    "duration_minutes": None,
                                    "metadata": {
                                        "source": "whatsapp_webhook",
                                        "from": from_phone,
                                        "message_id": msg.get("id"),
                                        "classification": cls.get("category"),
                                        "layer": cls.get("layer"),
                                        "sentiment": sentiment,
                                    },
                                    "created_at": datetime.now(timezone.utc).isoformat(),
                                })
                    else:
                        print(f"[whatsapp] inbound from {from_phone} could not resolve tenant — skipped")
    except Exception as e:
        print(f"WhatsApp webhook processing error: {e}")
    return {"received": True}
