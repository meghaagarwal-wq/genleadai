"""iter108 — ACTION 3 (continued): Lead Magnet (pre-call brochure).

Self-contained module owning:
  - workspace + campaign-scoped lead-magnet config (collections, models)
  - email + WhatsApp send pipelines (resolve → render → send → track)
  - 8 endpoints (config, upload, send-now, track, engagement, campaign override,
    engagement map, recent opens)
  - the `auto_send_lead_magnet` entry point used by the rest of server.py
    (e.g. by the Calendly inbound-booking handler).

WhatsApp dispatch is delegated to `whatsapp_dispatch.send_whatsapp_text` (the
canonical helper) so this module never duplicates that logic. Email goes
through `routes.pt_email.send_workspace_email` which honours the workspace's
Resend domain/sender.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from pymongo import DESCENDING

from aria_agent import get_object, put_object
from deps import (
    activities_collection,
    aria_settings_collection,
    db,
    get_current_user,
    leads_collection,
    serialize_doc,
)

router = APIRouter(tags=["iter108-lead-magnets"])

UPLOADS_DIR = "/app/backend/uploads"
os.makedirs(UPLOADS_DIR, exist_ok=True)

lead_magnets_collection = db["lead_magnets"]
lead_magnet_views_collection = db["lead_magnet_views"]


# ── Pydantic models ─────────────────────────────────────────────────────
class LeadMagnetConfig(BaseModel):
    enabled: bool = False
    name: Optional[str] = None
    type: Literal["url", "file"] = "url"
    url: Optional[str] = None
    file_id: Optional[str] = None
    file_name: Optional[str] = None
    send_timing: Literal["pre_booking", "post_booking", "both"] = "post_booking"
    message_template: Optional[str] = None


class CampaignLeadMagnetOverride(BaseModel):
    enabled: bool = False
    inherit: bool = True
    name: Optional[str] = None
    type: Literal["url", "file"] = "url"
    url: Optional[str] = None
    file_id: Optional[str] = None
    file_name: Optional[str] = None
    send_timing: Literal["pre_booking", "post_booking", "both"] = "post_booking"
    message_template: Optional[str] = None


# ── Resolvers ───────────────────────────────────────────────────────────
def _get_workspace_magnet() -> dict:
    return lead_magnets_collection.find_one({"scope": "workspace"}, {"_id": 0}) or {}


def _get_campaign_magnet(campaign_id: Optional[str]) -> Optional[dict]:
    if not campaign_id:
        return None
    doc = lead_magnets_collection.find_one({"scope": "campaign", "campaign_id": campaign_id}, {"_id": 0})
    if not doc or doc.get("inherit", True):
        return None
    return doc


def _resolve_magnet_for_lead(lead: dict) -> dict:
    campaign_id = lead.get("campaign_id") if isinstance(lead, dict) else None
    return _get_campaign_magnet(campaign_id) or _get_workspace_magnet()


def _build_tracking_url(tracking_id: str) -> str:
    base = (os.getenv("BACKEND_URL") or os.getenv("REACT_APP_BACKEND_URL", "")).rstrip("/")
    return f"{base}/api/lead-magnets/track/{tracking_id}"


def _get_lead_preferred_channel(lead_id: str) -> str:
    recent = activities_collection.find_one(
        {"lead_id": lead_id, "activity_type": {"$in": ["whatsapp_sent", "email_sent"]}},
        {"_id": 0, "activity_type": 1},
        sort=[("created_at", DESCENDING)],
    )
    return "whatsapp" if recent and recent.get("activity_type") == "whatsapp_sent" else "email"


# ── Senders ─────────────────────────────────────────────────────────────
async def _send_lead_magnet_via_email(lead: dict, magnet: dict, tracking_url: str, founder_name: str):
    """Returns (sent, error)."""
    name = lead.get("first_name") or "there"
    template = magnet.get("message_template") or (
        f"Hi {{first_name}},\n\nQuick note before our chat — here's a short overview of how we work and recent results: {{link}}\n\nGive it 2 minutes, it'll make our call sharper.\n\n— {founder_name}"
    )
    body = template.replace("{first_name}", name).replace("{link}", tracking_url).replace("{founder}", founder_name)
    html_body = f"<div style='font-family:Plus Jakarta Sans,Arial,sans-serif;color:#1A0A2E;line-height:1.6;'>{body.replace(chr(10), '<br>')}</div>"
    try:
        from routes.pt_email import send_workspace_email
        attachment_ids = []
        if magnet.get("type") == "file" and magnet.get("file_id"):
            attachment_ids.append(magnet["file_id"])
        await send_workspace_email(
            to=lead.get("email"),
            subject=magnet.get("subject") or "Before our call — quick read",
            html_body=html_body,
            attachment_file_ids=attachment_ids or None,
            uploads_dir=UPLOADS_DIR,
            append_signature=True,
        )
        return True, None
    except HTTPException as he:
        err = str(he.detail)[:200]
        print(f"Lead magnet email failed (HTTP {he.status_code}): {err}")
        return False, err
    except Exception as e:
        err = str(e)[:200]
        print(f"Lead magnet email failed: {err}")
        return False, err


def _send_lead_magnet_via_whatsapp_message(lead: dict, magnet: dict, tracking_url: str, founder_name: str) -> str:
    """Build the WhatsApp body text (does NOT send)."""
    name = lead.get("first_name") or "there"
    template = magnet.get("message_template") or (
        f"Hi {{first_name}}! Before our call — here's a 2-min overview of our work: {{link}}\n— {founder_name}"
    )
    return template.replace("{first_name}", name).replace("{link}", tracking_url).replace("{founder}", founder_name)


async def auto_send_lead_magnet(lead_id: str, trigger: str):
    """Auto-send the configured lead magnet for a `pre_booking` / `post_booking` trigger."""
    from whatsapp_dispatch import send_whatsapp_text  # late import — keep module load lean
    try:
        lead = leads_collection.find_one(
            {"_id": ObjectId(lead_id)},
            {"_id": 0, "first_name": 1, "email": 1, "phone": 1, "campaign_id": 1},
        )
    except Exception:
        return
    if not lead or not lead.get("email"):
        return

    magnet = _resolve_magnet_for_lead(lead)
    if not magnet or not magnet.get("enabled"):
        return
    timing = magnet.get("send_timing", "post_booking")
    if timing != "both" and timing != trigger:
        return
    if magnet.get("type") == "url" and not magnet.get("url"):
        return
    if magnet.get("type") == "file" and not magnet.get("file_id"):
        return

    # Idempotency
    if lead_magnet_views_collection.find_one(
        {"lead_id": lead_id, "trigger": trigger, "kind": "send"}, {"_id": 0}
    ):
        return

    tracking_id = uuid.uuid4().hex
    tracking_url = _build_tracking_url(tracking_id)
    founder_name = (aria_settings_collection.find_one({}) or {}).get("founder_name") or "the team"
    channel = _get_lead_preferred_channel(lead_id)

    if channel == "whatsapp":
        body_text = _send_lead_magnet_via_whatsapp_message(lead, magnet, tracking_url, founder_name)
        wa_result = await send_whatsapp_text(lead.get("phone"), body_text)
        activity_type = "whatsapp_sent"
        subject = "Lead magnet sent (WhatsApp)" if wa_result.get("sent") else "Lead magnet queued (WhatsApp logged-only — configure WHATSAPP_* env)"
        body_preview = body_text
    else:
        sent_ok, send_err = await _send_lead_magnet_via_email(lead, magnet, tracking_url, founder_name)
        body_preview = magnet.get("name") or "Pre-call brochure"
        if sent_ok:
            activity_type, subject = "email_sent", "Lead magnet sent (Email)"
        else:
            activity_type, subject = "email_failed", f"Lead magnet FAILED (Email): {send_err or 'unknown error'}"

    now_iso = datetime.now(timezone.utc).isoformat()
    activities_collection.insert_one({
        "lead_id": lead_id, "user_id": "aria@genleadai.ai",
        "activity_type": activity_type, "subject": subject, "body": body_preview,
        "outcome": None, "duration_minutes": None,
        "metadata": {"type": "lead_magnet", "tracking_id": tracking_id, "trigger": trigger, "channel": channel, "scope": magnet.get("scope", "workspace")},
        "created_at": now_iso,
    })
    lead_magnet_views_collection.insert_one({
        "tracking_id": tracking_id,
        "lead_id": lead_id,
        "kind": "send",
        "channel": channel,
        "trigger": trigger,
        "magnet_type": magnet.get("type"),
        "magnet_target": magnet.get("url") or magnet.get("file_id"),
        "magnet_scope": magnet.get("scope", "workspace"),
        "created_at": now_iso,
    })


# ── Endpoints ───────────────────────────────────────────────────────────
@router.get("/api/lead-magnets/config")
async def get_lead_magnet_config(current_user: dict = Depends(get_current_user)):
    doc = _get_workspace_magnet()
    if not doc:
        return {
            "enabled": False, "name": "", "type": "url", "url": "", "file_id": None,
            "file_name": None, "send_timing": "post_booking", "message_template": "",
        }
    doc.pop("scope", None)
    return doc


@router.put("/api/lead-magnets/config")
async def save_lead_magnet_config(cfg: LeadMagnetConfig, current_user: dict = Depends(get_current_user)):
    payload = cfg.dict()
    payload["scope"] = "workspace"
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    payload["updated_by"] = current_user["email"]
    lead_magnets_collection.update_one({"scope": "workspace"}, {"$set": payload}, upsert=True)
    payload.pop("scope", None)
    return payload


@router.post("/api/lead-magnets/upload")
async def upload_lead_magnet_file(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """Upload a PDF/file lead magnet. Stored in object storage; returns file_id."""
    try:
        data = await file.read()
        file_size_kb = len(data) / 1024
        if file_size_kb > 10240:
            raise HTTPException(status_code=400, detail="File too large (max 10MB)")
        ext = file.filename.split(".")[-1] if "." in file.filename else "bin"
        file_id = f"{uuid.uuid4().hex}.{ext}"
        storage_path = f"genleadai/lead-magnets/{file_id}"
        result = put_object(storage_path, data, file.content_type or "application/octet-stream")
        return {
            "file_id": file_id,
            "file_name": file.filename,
            "storage_path": result.get("path", storage_path),
            "size_kb": round(file_size_kb, 2),
            "mime_type": file.content_type,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/api/leads/{lead_id}/send-lead-magnet")
async def send_lead_magnet_manual(lead_id: str, current_user: dict = Depends(get_current_user)):
    """Manual 'Send Brochure' button — uses preferred channel + records activity."""
    from whatsapp_dispatch import send_whatsapp_text
    try:
        lead = leads_collection.find_one({"_id": ObjectId(lead_id)})
    except Exception:
        raise HTTPException(status_code=404, detail="Lead not found")
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead = serialize_doc(lead)
    magnet = _resolve_magnet_for_lead(lead)
    if not magnet or not magnet.get("enabled"):
        raise HTTPException(status_code=400, detail="Lead magnet not configured or disabled")

    tracking_id = uuid.uuid4().hex
    tracking_url = _build_tracking_url(tracking_id)
    founder_name = (aria_settings_collection.find_one({}) or {}).get("founder_name") or "the team"
    channel = _get_lead_preferred_channel(lead_id)

    if channel == "whatsapp" and lead.get("phone"):
        body_text = _send_lead_magnet_via_whatsapp_message(lead, magnet, tracking_url, founder_name)
        wa_result = await send_whatsapp_text(lead.get("phone"), body_text)
        activity_type = "whatsapp_sent"
        subject = "Lead magnet sent manually (WhatsApp)" if wa_result.get("sent") else "Lead magnet queued (WhatsApp logged-only)"
        body_preview = body_text
        sent = True
    elif lead.get("email"):
        sent_ok, send_err = await _send_lead_magnet_via_email(lead, magnet, tracking_url, founder_name)
        body_preview = magnet.get("name") or "Pre-call brochure"
        activity_type = "email_sent" if sent_ok else "email_failed"
        subject = "Lead magnet sent manually (Email)" if sent_ok else f"Lead magnet FAILED (Email): {send_err or 'unknown error'}"
        sent = bool(sent_ok)
    else:
        raise HTTPException(status_code=400, detail="Lead has no email or phone")

    now_iso = datetime.now(timezone.utc).isoformat()
    activities_collection.insert_one({
        "lead_id": lead_id, "user_id": current_user.get("email", "manual"),
        "activity_type": activity_type, "subject": subject, "body": body_preview,
        "outcome": None, "duration_minutes": None,
        "metadata": {"type": "lead_magnet", "tracking_id": tracking_id, "trigger": "manual", "channel": channel, "scope": magnet.get("scope", "workspace")},
        "created_at": now_iso,
    })
    lead_magnet_views_collection.insert_one({
        "tracking_id": tracking_id,
        "lead_id": lead_id,
        "kind": "send",
        "channel": channel,
        "trigger": "manual",
        "magnet_type": magnet.get("type"),
        "magnet_target": magnet.get("url") or magnet.get("file_id"),
        "magnet_scope": magnet.get("scope", "workspace"),
        "created_at": now_iso,
    })
    return {"sent": sent, "channel": channel, "tracking_id": tracking_id, "tracking_url": tracking_url}


@router.get("/api/lead-magnets/track/{tracking_id}")
async def track_lead_magnet(tracking_id: str, request_body: Optional[Dict[str, Any]] = None):
    """Lead clicks the link → redirect to the actual magnet + stamp a view event."""
    send_doc = lead_magnet_views_collection.find_one({"tracking_id": tracking_id, "kind": "send"}, {"_id": 0})
    if not send_doc:
        raise HTTPException(status_code=404, detail="Invalid tracking ID")
    lead_magnet_views_collection.insert_one({
        "tracking_id": tracking_id,
        "lead_id": send_doc.get("lead_id"),
        "kind": "view",
        "channel": send_doc.get("channel"),
        "magnet_type": send_doc.get("magnet_type"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    # The magnet is either a URL (redirect) or a file id (proxy through assets download).
    magnet_target = send_doc.get("magnet_target", "")
    if send_doc.get("magnet_type") == "url" and magnet_target.startswith("http"):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=magnet_target, status_code=302)
    if send_doc.get("magnet_type") == "file" and magnet_target:
        try:
            storage_path = f"genleadai/lead-magnets/{magnet_target}"
            data, content_type = get_object(storage_path)
            from fastapi import Response
            return Response(content=data, media_type=content_type or "application/pdf")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"File fetch failed: {e}")
    raise HTTPException(status_code=404, detail="Magnet target not configured")


@router.get("/api/lead-magnets/engagement/{lead_id}")
async def lead_magnet_engagement(lead_id: str, current_user: dict = Depends(get_current_user)):
    sends = list(lead_magnet_views_collection.find(
        {"lead_id": lead_id, "kind": "send"}, {"_id": 0}
    ).sort("created_at", DESCENDING))
    views = list(lead_magnet_views_collection.find(
        {"lead_id": lead_id, "kind": "view"}, {"_id": 0}
    ).sort("created_at", DESCENDING))
    return {
        "sent_count": len(sends),
        "view_count": len(views),
        "last_sent": sends[0]["created_at"] if sends else None,
        "last_viewed": views[0]["created_at"] if views else None,
        "sends": sends,
        "views": views[:10],
        "is_hot": len(views) >= 2,
    }


@router.get("/api/lead-magnets/campaign/{campaign_id}")
async def get_campaign_magnet(campaign_id: str, current_user: dict = Depends(get_current_user)):
    doc = lead_magnets_collection.find_one({"scope": "campaign", "campaign_id": campaign_id}, {"_id": 0})
    if not doc:
        return {
            "campaign_id": campaign_id, "inherit": True, "enabled": False, "name": "",
            "type": "url", "url": "", "file_id": None, "file_name": None,
            "send_timing": "post_booking", "message_template": "",
        }
    doc.pop("scope", None)
    return doc


@router.put("/api/lead-magnets/campaign/{campaign_id}")
async def save_campaign_magnet(campaign_id: str, cfg: CampaignLeadMagnetOverride, current_user: dict = Depends(get_current_user)):
    payload = cfg.dict()
    payload["scope"] = "campaign"
    payload["campaign_id"] = campaign_id
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    payload["updated_by"] = current_user["email"]
    lead_magnets_collection.update_one(
        {"scope": "campaign", "campaign_id": campaign_id},
        {"$set": payload},
        upsert=True,
    )
    payload.pop("scope", None)
    return payload


@router.get("/api/lead-magnets/engagement-map")
async def lead_magnet_engagement_map(current_user: dict = Depends(get_current_user)):
    """Returns {lead_id: {sent, viewed, last_viewed, is_hot}} for Lead Inbox 'Hot strip'."""
    pipeline = [
        {"$group": {"_id": {"lead_id": "$lead_id", "kind": "$kind"}, "count": {"$sum": 1}, "last_at": {"$max": "$created_at"}}},
    ]
    rows = list(lead_magnet_views_collection.aggregate(pipeline))
    lead_map: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        lid = r["_id"].get("lead_id")
        kind = r["_id"].get("kind")
        if not lid:
            continue
        bucket = lead_map.setdefault(lid, {"sent_count": 0, "view_count": 0, "last_viewed": None, "last_sent": None})
        if kind == "send":
            bucket["sent_count"] = r["count"]
            bucket["last_sent"] = r["last_at"]
        elif kind == "view":
            bucket["view_count"] = r["count"]
            bucket["last_viewed"] = r["last_at"]
    for _lid, b in lead_map.items():
        b["is_hot"] = b["view_count"] >= 2
    return {"leads": lead_map, "total_engaged": len(lead_map)}


@router.get("/api/lead-magnets/recent-opens")
async def lead_magnet_recent_opens(limit: int = 5, current_user: dict = Depends(get_current_user)):
    """Recent brochure opens with enriched lead info — Dashboard alert card."""
    views = list(lead_magnet_views_collection.find(
        {"kind": "view"}, {"_id": 0}
    ).sort("created_at", DESCENDING).limit(max(1, min(limit, 50))))
    out = []
    seen_leads = set()
    for v in views:
        lid = v.get("lead_id")
        if not lid or lid in seen_leads:
            continue
        seen_leads.add(lid)
        try:
            lead = leads_collection.find_one(
                {"_id": ObjectId(lid)},
                {"_id": 0, "first_name": 1, "last_name": 1, "company_name": 1, "icp_score": 1, "icp_tier": 1, "email": 1},
            )
        except Exception:
            lead = None
        if not lead:
            continue
        view_count = lead_magnet_views_collection.count_documents({"lead_id": lid, "kind": "view"})
        out.append({
            "lead_id": lid,
            "first_name": lead.get("first_name"),
            "last_name": lead.get("last_name"),
            "company_name": lead.get("company_name"),
            "icp_score": lead.get("icp_score"),
            "icp_tier": lead.get("icp_tier"),
            "email": lead.get("email"),
            "viewed_at": v.get("created_at"),
            "view_count": view_count,
            "is_hot": view_count >= 2,
        })
    return {"opens": out, "count": len(out)}
