"""ARIA — Auto-Approve Rule + Notification Aggregator (Batch 9).

Two small things:

1. Per-tenant **auto-approve rule** for drafts queued from inbound
   replies and morning briefs. When the rule matches, the draft is
   dispatched IMMEDIATELY via outreach_dispatch instead of sitting in
   pending_outreach. Founder still gets the dispatch result in the
   outbound_log.

2. **Notification settings aggregator** — single GET/POST endpoint set
   that combines the Morning Brief config + Approval Digest config +
   Auto-Approve config so the Settings → Notifications UI can drive
   all three from one page.

Endpoints
─────────
  GET  /api/aria/settings/notifications   — { morning_brief, approval_digest, auto_approve }
  POST /api/aria/settings/notifications   — { morning_brief?, approval_digest?, auto_approve? }
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from deps import db, get_current_user

logger = logging.getLogger("aria_auto_approve")

router = APIRouter(prefix="/api/aria/settings", tags=["aria-settings"])

auto_cfg_col = db["aria_auto_approve_config"]
mb_cfg_col = db["aria_morning_brief_config"]
ad_cfg_col = db["aria_approval_digest_config"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Auto-approve evaluator ─────────────────────────────────────────────
DEFAULT_AUTO_APPROVE = {
    "enabled": False,
    "min_fit_score": 85,
    "allowed_intents": ["positive", "interested"],
    "allowed_channels": ["email", "whatsapp"],  # NOT linkedin by default
    "max_per_day": 20,  # safety cap so a bad rule doesn't spam
}


def get_auto_approve_cfg(tenant_id: str) -> Dict[str, Any]:
    doc = auto_cfg_col.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if not doc:
        return dict(DEFAULT_AUTO_APPROVE)
    out = dict(DEFAULT_AUTO_APPROVE)
    out.update({k: v for k, v in doc.items() if k in DEFAULT_AUTO_APPROVE})
    return out


def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def auto_approve_eligible(
    *,
    tenant_id: str,
    channel: str,
    fit_score: int,
    intent: str,
) -> Dict[str, Any]:
    """Pure decision function — returns {eligible: bool, reason: str}.
    Caller is responsible for actually dispatching."""
    cfg = get_auto_approve_cfg(tenant_id)
    if not cfg.get("enabled"):
        return {"eligible": False, "reason": "rule_disabled"}
    if channel not in (cfg.get("allowed_channels") or []):
        return {"eligible": False, "reason": f"channel_{channel}_not_allowed"}
    if intent not in (cfg.get("allowed_intents") or []):
        return {"eligible": False, "reason": f"intent_{intent}_not_allowed"}
    if int(fit_score or 0) < int(cfg.get("min_fit_score") or 0):
        return {"eligible": False, "reason": f"fit_score_below_threshold ({fit_score}<{cfg['min_fit_score']})"}
    # Daily cap
    today = _today_iso()
    used = db["aria_auto_approve_usage"].find_one(
        {"tenant_id": tenant_id, "day": today}, {"_id": 0, "count": 1},
    ) or {}
    if int(used.get("count", 0)) >= int(cfg.get("max_per_day", 20)):
        return {"eligible": False, "reason": "daily_cap_reached"}
    return {"eligible": True, "reason": "ok"}


def record_auto_approve_used(tenant_id: str) -> None:
    db["aria_auto_approve_usage"].update_one(
        {"tenant_id": tenant_id, "day": _today_iso()},
        {"$inc": {"count": 1}, "$set": {"updated_at": _now_iso()}},
        upsert=True,
    )


# ─── Schemas ────────────────────────────────────────────────────────────
class MorningBriefCfg(BaseModel):
    enabled: bool = False
    send_to_email: str = ""
    send_hour_local: int = Field(8, ge=0, le=23)
    timezone_offset_hours: float = Field(0.0, ge=-12.0, le=14.0)
    weekdays_only: bool = True
    max_new_intel: int = Field(20, ge=1, le=50)


class ApprovalDigestCfg(BaseModel):
    enabled: bool = False
    send_to_email: str = ""
    send_hour_local: int = Field(20, ge=0, le=23)
    timezone_offset_hours: float = Field(0.0, ge=-12.0, le=14.0)
    weekdays_only: bool = False


class AutoApproveCfg(BaseModel):
    enabled: bool = False
    min_fit_score: int = Field(85, ge=0, le=100)
    allowed_intents: List[str] = Field(default_factory=lambda: ["positive", "interested"])
    allowed_channels: List[str] = Field(default_factory=lambda: ["email", "whatsapp"])
    max_per_day: int = Field(20, ge=0, le=500)


class NotificationsBody(BaseModel):
    morning_brief: Optional[MorningBriefCfg] = None
    approval_digest: Optional[ApprovalDigestCfg] = None
    auto_approve: Optional[AutoApproveCfg] = None


# ─── Aggregator endpoints ───────────────────────────────────────────────
@router.get("/notifications")
async def get_notifications(current_user: dict = Depends(get_current_user)):
    tenant_id = current_user.get("tenant_id")
    mb = mb_cfg_col.find_one({"tenant_id": tenant_id}, {"_id": 0}) or {
        "enabled": False, "send_to_email": current_user.get("email", ""),
        "send_hour_local": 8, "timezone_offset_hours": 5.5,
        "weekdays_only": True, "max_new_intel": 20,
    }
    ad = ad_cfg_col.find_one({"tenant_id": tenant_id}, {"_id": 0}) or {
        "enabled": False, "send_to_email": current_user.get("email", ""),
        "send_hour_local": 20, "timezone_offset_hours": 5.5, "weekdays_only": False,
    }
    aa = get_auto_approve_cfg(tenant_id)
    return {"morning_brief": mb, "approval_digest": ad, "auto_approve": aa}


@router.post("/notifications")
async def save_notifications(body: NotificationsBody, current_user: dict = Depends(get_current_user)):
    tenant_id = current_user.get("tenant_id")
    now = _now_iso()
    saved = {}

    if body.morning_brief is not None:
        payload = body.morning_brief.model_dump()
        payload["tenant_id"] = tenant_id
        payload["updated_at"] = now
        mb_cfg_col.update_one(
            {"tenant_id": tenant_id},
            {"$set": payload, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        saved["morning_brief"] = payload

    if body.approval_digest is not None:
        payload = body.approval_digest.model_dump()
        payload["tenant_id"] = tenant_id
        payload["updated_at"] = now
        ad_cfg_col.update_one(
            {"tenant_id": tenant_id},
            {"$set": payload, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        saved["approval_digest"] = payload

    if body.auto_approve is not None:
        payload = body.auto_approve.model_dump()
        payload["tenant_id"] = tenant_id
        payload["updated_at"] = now
        auto_cfg_col.update_one(
            {"tenant_id": tenant_id},
            {"$set": payload, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        saved["auto_approve"] = payload

    return {"saved": True, **saved}


__all__ = [
    "router",
    "auto_approve_eligible",
    "record_auto_approve_used",
    "get_auto_approve_cfg",
]
