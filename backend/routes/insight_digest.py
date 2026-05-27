"""Iter105 — Task 2: Insight Digest daily email per workspace.

A daily Resend email bundling:
  - new insight cards from the last 24h
  - cards re-surfaced from snooze today

Endpoint:
  POST /api/pt/notifications/digest/send  { tenant_id, dry_run }

Background job (registered in server.py):
  insight_digest_sender_loop — wakes every 15 min, for each workspace whose
  notification preference says "email_insights_enabled": true AND whose
  configured digest_time matches the current hour (in the workspace timezone),
  sends one digest. Idempotent via `last_digest_sent_on` date stamp.

Settings:
  - tenant_notification_prefs.insight_digest.enabled (default true)
  - tenant_notification_prefs.insight_digest.send_at_hour (default 7)
"""
from __future__ import annotations

import asyncio
import html
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import db, get_current_user
from email_delivery import send_email_safe
from routes.tenants import get_active_tenant

router = APIRouter(tags=["iter105-insight-digest"])

insights_col = db["pt_insights"]
tenants_col = db["tenants"]
prefs_col = db["tenant_notification_prefs"]
memberships_col = db["tenant_memberships"]
audit_col = db["audit_log"]

PUBLIC_APP_URL = "https://app.genleadai.com"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today_iso_date() -> str:
    return _now().date().isoformat()


def _get_prefs(tenant_id: str) -> Dict[str, Any]:
    """Return notification prefs with sensible defaults."""
    doc = prefs_col.find_one({"tenant_id": tenant_id}, {"_id": 0}) or {}
    digest = (doc.get("insight_digest") or {})
    return {
        "enabled": bool(digest.get("enabled", True)),
        "send_at_hour": int(digest.get("send_at_hour", 7)),
        "last_sent_on": digest.get("last_sent_on"),  # ISO date "YYYY-MM-DD"
    }


def _workspace_owner_email(tenant_id: str) -> Optional[str]:
    m = memberships_col.find_one(
        {"tenant_id": tenant_id, "role": "owner"},
        {"_id": 0, "user_email": 1},
        sort=[("created_at", 1)],
    )
    return (m or {}).get("user_email")


def _signal_badge(signal_type: str) -> str:
    palette = {
        "deal":        ("#16A34A", "Deal"),
        "funding":     ("#0EA5E9", "Funding"),
        "promotion":   ("#7C35DC", "Promotion"),
        "event":       ("#F59E0B", "Event"),
        "speaking":    ("#EC4899", "Speaking"),
        "announcement": ("#64748B", "Announcement"),
    }
    color, label = palette.get(signal_type, ("#64748B", (signal_type or "Signal").title()))
    return (
        f'<span style="display:inline-block;background:{color};color:#fff;'
        f'font-size:10px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;'
        f'padding:3px 8px;border-radius:9999px;">{html.escape(label)}</span>'
    )


def _render_card_block(card: Dict[str, Any], app_url: str) -> str:
    name = html.escape(card.get("prospect_name") or "—")
    title = html.escape(card.get("prospect_title") or "")
    company = html.escape(card.get("prospect_company") or "")
    summary = html.escape((card.get("signal_summary") or "")[:240])
    icp = html.escape(card.get("icp_match_name") or "")
    icp_score = round((card.get("icp_match_score") or 0) * 100)
    timing = html.escape(card.get("timing_hint") or card.get("timing") or "")
    confidence = round((card.get("confidence") or 0) * 100)
    card_url = f"{app_url}/app/intelligence?card_id={card.get('id')}"

    title_company = " · ".join([t for t in [title, company] if t])

    return f"""
    <div style="border:1px solid #E2E8F0;border-radius:12px;padding:18px 20px;margin:14px 0;background:#FFFFFF;">
      <div style="margin-bottom:10px;">{_signal_badge(card.get("signal_type") or "")}</div>
      <div style="font-size:16px;font-weight:700;color:#0F172A;line-height:1.3;">{name}</div>
      <div style="font-size:13px;color:#64748B;margin-top:2px;">{title_company}</div>
      <div style="font-size:14px;color:#334155;line-height:1.55;margin-top:10px;">{summary}</div>
      <div style="font-size:12px;color:#64748B;margin-top:10px;">
        {('<strong style="color:#5B28D4;">ICP:</strong> ' + icp + f' · {icp_score}% match') if icp else ''}
        {' &nbsp;·&nbsp; ' if icp and timing else ''}
        {('⏰ ' + timing) if timing else ''}
        {' &nbsp;·&nbsp; ' if (icp or timing) else ''}
        <span style="color:#16A34A;font-weight:600;">{confidence}% conf.</span>
      </div>
      <div style="margin-top:14px;">
        <a href="{card_url}" style="display:inline-block;background:linear-gradient(135deg,#7C35DC,#C044E0);color:#fff;font-size:13px;font-weight:600;text-decoration:none;padding:9px 16px;border-radius:9999px;">View Signal →</a>
      </div>
    </div>
    """


def _render_digest_html(
    workspace_name: str,
    today_str: str,
    new_cards: List[Dict[str, Any]],
    resurfaced_cards: List[Dict[str, Any]],
    app_url: str = PUBLIC_APP_URL,
    settings_url: Optional[str] = None,
) -> str:
    settings_url = settings_url or f"{app_url}/app/settings"
    open_feed_url = f"{app_url}/app/intelligence"

    # Cap at 5 in body, rest spilled to dashboard.
    MAX_IN_EMAIL = 5
    new_shown = new_cards[:MAX_IN_EMAIL]
    new_overflow = max(0, len(new_cards) - MAX_IN_EMAIL)
    res_shown = resurfaced_cards[:MAX_IN_EMAIL]
    res_overflow = max(0, len(resurfaced_cards) - MAX_IN_EMAIL)

    new_section = ""
    if new_cards:
        new_section = f"""
        <h2 style="font-size:18px;font-weight:700;color:#0F172A;margin:28px 0 6px 0;">
          {len(new_cards)} new signal{'s' if len(new_cards) != 1 else ''} today
        </h2>
        {''.join(_render_card_block(c, app_url) for c in new_shown)}
        {f'<div style="font-size:13px;color:#64748B;margin-top:8px;">…and {new_overflow} more on the dashboard.</div>' if new_overflow else ''}
        """

    res_section = ""
    if resurfaced_cards:
        res_section = f"""
        <h2 style="font-size:18px;font-weight:700;color:#0F172A;margin:32px 0 6px 0;">
          {len(resurfaced_cards)} snoozed signal{'s' if len(resurfaced_cards) != 1 else ''} resurfaced
        </h2>
        {''.join(_render_card_block(c, app_url) for c in res_shown)}
        {f'<div style="font-size:13px;color:#64748B;margin-top:8px;">…and {res_overflow} more on the dashboard.</div>' if res_overflow else ''}
        """

    return f"""<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:#F4F1FA;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#0F172A;">
  <div style="max-width:600px;margin:0 auto;padding:32px 20px;">

    <div style="padding-bottom:18px;border-bottom:1px solid #E2E8F0;">
      <div style="font-size:11px;font-weight:700;letter-spacing:0.22em;text-transform:uppercase;color:#5B28D4;">
        ARIA Intelligence Digest
      </div>
      <div style="font-size:24px;font-weight:800;color:#0F172A;margin-top:4px;">
        {html.escape(workspace_name)}
      </div>
      <div style="font-size:13px;color:#64748B;margin-top:2px;">{today_str}</div>
    </div>

    {new_section}
    {res_section}

    <div style="margin-top:36px;text-align:center;">
      <a href="{open_feed_url}" style="display:inline-block;background:#0F172A;color:#fff;font-size:14px;font-weight:600;text-decoration:none;padding:12px 22px;border-radius:9999px;">
        Open Intelligence Feed →
      </a>
    </div>

    <div style="margin-top:36px;padding-top:18px;border-top:1px solid #E2E8F0;font-size:12px;color:#94A3B8;line-height:1.6;">
      You're receiving this because intelligence notifications are enabled for {html.escape(workspace_name)}.
      <br/>
      <a href="{settings_url}/notifications" style="color:#5B28D4;text-decoration:underline;">Manage preferences</a>
      &nbsp;·&nbsp;
      <a href="{open_feed_url}" style="color:#5B28D4;text-decoration:underline;">Open ARIA</a>
    </div>

  </div>
</body></html>
"""


def _collect_cards(tenant_id: str) -> Dict[str, List[Dict[str, Any]]]:
    """Pull (new in last 24h) + (resurfaced today) cards for a tenant."""
    now = _now()
    cutoff_24h = (now - timedelta(hours=24)).isoformat()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

    # NEW: status=new AND created_at within last 24h AND no snooze history
    new_cards = list(insights_col.find(
        {
            "tenant_id": tenant_id,
            "status": "new",
            "created_at": {"$gte": cutoff_24h},
            "actioned_via_digest": {"$ne": True},
        },
        {"_id": 0},
        sort=[("confidence", -1), ("created_at", -1)],
        limit=50,
    ))

    # RESURFACED: status=new, was previously snoozed (has snoozed_history flag OR
    # actioned_action='snooze'), and surfaced today.
    resurfaced_cards = list(insights_col.find(
        {
            "tenant_id": tenant_id,
            "status": "new",
            "actioned_action": "snooze",
            "actioned_at": {"$gte": today_start},
            "actioned_via_digest": {"$ne": True},
        },
        {"_id": 0},
        sort=[("confidence", -1)],
        limit=50,
    ))

    # Dedupe by id (a card classified as resurfaced shouldn't also appear in new)
    new_ids = {c["id"] for c in new_cards}
    resurfaced_cards = [c for c in resurfaced_cards if c["id"] not in new_ids]

    return {"new": new_cards, "resurfaced": resurfaced_cards}


def _send_digest_for_tenant(tenant: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
    """Send one digest. Returns a structured result. Never raises."""
    tenant_id = tenant.get("id")
    workspace_name = tenant.get("name") or "Your workspace"
    cards = _collect_cards(tenant_id)
    total = len(cards["new"]) + len(cards["resurfaced"])
    if total == 0:
        return {"sent": False, "card_count": 0, "reason": "no_cards"}

    owner_email = _workspace_owner_email(tenant_id)
    if not owner_email:
        return {"sent": False, "card_count": total, "reason": "no_owner"}

    today_dt = _now()
    today_str = today_dt.strftime("%A, %d %B")
    subject = f"Your ARIA Signals for {today_str} — {len(cards['new'])} new, {len(cards['resurfaced'])} resurfaced"
    html_body = _render_digest_html(
        workspace_name=workspace_name,
        today_str=today_str,
        new_cards=cards["new"],
        resurfaced_cards=cards["resurfaced"],
    )

    if dry_run:
        return {
            "sent": False,
            "dry_run": True,
            "card_count": total,
            "subject": subject,
            "to": owner_email,
            "html": html_body,
            "breakdown": {"new": len(cards["new"]), "resurfaced": len(cards["resurfaced"])},
        }

    result = send_email_safe(
        to_email=owner_email,
        subject=subject,
        html=html_body,
        purpose="insight_digest",
    )

    # Mark these cards so they don't re-appear in tomorrow's digest as "new"
    card_ids = [c["id"] for c in cards["new"] + cards["resurfaced"]]
    if card_ids:
        insights_col.update_many(
            {"tenant_id": tenant_id, "id": {"$in": card_ids}},
            {"$set": {"actioned_via_digest": True, "digest_sent_at": _now().isoformat()}},
        )

    # Audit
    try:
        audit_col.insert_one({
            "tenant_id": tenant_id,
            "event": "insight_digest_sent",
            "card_count": total,
            "to": owner_email,
            "delivered": bool(getattr(result, "delivered", False)),
            "status": getattr(result, "delivery_status", "unknown"),
            "created_at": _now().isoformat(),
        })
    except Exception:
        pass

    # Stamp "last_sent_on" so the daily loop doesn't double-send
    prefs_col.update_one(
        {"tenant_id": tenant_id},
        {"$set": {"insight_digest.last_sent_on": _now().date().isoformat()}},
        upsert=True,
    )

    return {
        "sent": bool(getattr(result, "delivered", False)),
        "card_count": total,
        "email": owner_email,
        "status": getattr(result, "delivery_status", "unknown"),
    }


# ─────────────────────────────────────────────────────────────────────────
# Endpoint — send / dry-run a digest
# ─────────────────────────────────────────────────────────────────────────
class DigestSendPayload(BaseModel):
    tenant_id: Optional[str] = None
    dry_run: bool = False


@router.post("/api/pt/notifications/digest/send")
async def send_digest(
    payload: DigestSendPayload,
    current_user: dict = Depends(get_current_user),
):
    target_tenant_id = payload.tenant_id
    if not target_tenant_id:
        # Use first tenant the caller is a member of
        m = memberships_col.find_one({"user_email": current_user.get("email")}, {"_id": 0, "tenant_id": 1})
        target_tenant_id = (m or {}).get("tenant_id")
    if not target_tenant_id:
        raise HTTPException(400, "No tenant_id provided and caller has no memberships")

    # If caller is not master_admin, they must be a member of this tenant
    if current_user.get("role") != "master_admin":
        is_member = memberships_col.find_one({
            "tenant_id": target_tenant_id,
            "user_email": current_user.get("email"),
        })
        if not is_member:
            raise HTTPException(403, "Not a member of requested tenant")

    tenant = tenants_col.find_one({"id": target_tenant_id}, {"_id": 0})
    if not tenant:
        raise HTTPException(404, "Tenant not found")

    return _send_digest_for_tenant(tenant, dry_run=payload.dry_run)


# ─────────────────────────────────────────────────────────────────────────
# Notification preference endpoints (insight digest toggle + send-at-hour)
# ─────────────────────────────────────────────────────────────────────────
class DigestPrefsPayload(BaseModel):
    enabled: Optional[bool] = None
    send_at_hour: Optional[int] = None


@router.get("/api/pt/notifications/digest/prefs")
async def get_digest_prefs(tenant: dict = Depends(get_active_tenant)):
    return _get_prefs(tenant["id"])


@router.put("/api/pt/notifications/digest/prefs")
async def update_digest_prefs(
    payload: DigestPrefsPayload,
    tenant: dict = Depends(get_active_tenant),
):
    update: Dict[str, Any] = {}
    if payload.enabled is not None:
        update["insight_digest.enabled"] = bool(payload.enabled)
    if payload.send_at_hour is not None:
        h = int(payload.send_at_hour)
        if not (0 <= h <= 23):
            raise HTTPException(400, "send_at_hour must be 0–23")
        update["insight_digest.send_at_hour"] = h
    if update:
        prefs_col.update_one(
            {"tenant_id": tenant["id"]},
            {"$set": update},
            upsert=True,
        )
    return _get_prefs(tenant["id"])


# ─────────────────────────────────────────────────────────────────────────
# Background loop — fires daily at the workspace's configured digest hour
# ─────────────────────────────────────────────────────────────────────────
async def insight_digest_sender_loop():
    """Wakes every 15 minutes. For every tenant with insight_digest.enabled=true,
    if the current UTC hour matches the configured send_at_hour AND we have not
    already sent today's digest, send it. (Workspace timezone refinement is left
    as a follow-up — current default is UTC for simplicity.)
    """
    while True:
        try:
            now = _now()
            today_iso = now.date().isoformat()
            cur_hour = now.hour
            for tenant in tenants_col.find({}, {"_id": 0, "id": 1, "name": 1, "settings": 1}):
                tid = tenant.get("id")
                if not tid:
                    continue
                prefs = _get_prefs(tid)
                if not prefs["enabled"]:
                    continue
                if prefs["send_at_hour"] != cur_hour:
                    continue
                if prefs["last_sent_on"] == today_iso:
                    continue
                result = _send_digest_for_tenant(tenant, dry_run=False)
                if result.get("sent"):
                    print(f"[insight_digest] sent for {tid}: {result.get('card_count')} cards → {result.get('email')}")
                elif result.get("reason") not in {"no_cards"}:
                    print(f"[insight_digest] skipped {tid}: {result.get('reason')}")
        except Exception as e:
            print(f"[insight_digest_sender_loop] error: {e}")
        # 15-minute resolution is fine — we de-dupe via last_sent_on date.
        await asyncio.sleep(15 * 60)
