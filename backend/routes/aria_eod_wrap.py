"""iter108 — ACTION 3 (continued): EOD-wrap module extracted from server.py.

Six endpoints + background loop that emails the founder a 6pm summary of
the day's outbound activity. Self-contained except for two helpers that
still live in server.py:
  - `_compute_call_priority` (used to render tomorrow's top-3 calls)
  - `_fmt_inr`               (currency formatter)
Both are imported lazily inside the compute function to avoid a circular
import at module load.

Endpoints:
  - GET    /api/aria/eod-wrap/config
  - PUT    /api/aria/eod-wrap/config
  - POST   /api/aria/eod-wrap/send-now
  - GET    /api/aria/eod-wrap/preview
  - GET    /api/aria/today                (light snapshot for dashboard)

Background loop `eod_wrap_loop` runs every 60s; fires once per local-day
when the founder's local clock matches `send_hour_local` ±5min.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import resend
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from deps import (
    activities_collection,
    aria_settings_collection,
    db,
    get_current_user,
    leads_collection,
)

router = APIRouter(tags=["iter108-eod-wrap"])

eod_wrap_collection = db["eod_wrap_settings"]


class EndOfDayWrapConfig(BaseModel):
    enabled: bool = False
    send_to_email: Optional[EmailStr] = None
    send_hour_local: int = Field(18, ge=0, le=23)
    timezone_offset_hours: float = Field(0.0, ge=-12.0, le=14.0)


def _get_eod_wrap_config() -> dict:
    return eod_wrap_collection.find_one({"scope": "workspace"}, {"_id": 0}) or {}


def _compute_eod_wrap(tz_off_hours: float = 0.0) -> dict:
    """Compute today's wrap data. 'Today' = the founder's local calendar day."""
    # Late imports — these helpers live in server.py / new modules.
    from server import _fmt_inr  # noqa: WPS433
    from routes.aria_call_priority import _compute_call_priority  # noqa: WPS433

    now_utc = datetime.now(timezone.utc)
    local_now = now_utc + timedelta(hours=tz_off_hours)
    local_day_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_start_utc = local_day_start - timedelta(hours=tz_off_hours)
    day_start_iso = day_start_utc.isoformat()
    now_iso = now_utc.isoformat()

    today_activities = list(activities_collection.find(
        {"created_at": {"$gte": day_start_iso, "$lte": now_iso}},
        {"_id": 0, "lead_id": 1, "activity_type": 1, "subject": 1, "user_id": 1, "created_at": 1, "outcome": 1},
    ))

    def _count(types):
        return sum(1 for a in today_activities if a.get("activity_type") in types)

    calls_logged = _count(["call_made", "meeting_done", "call"])
    emails_sent = _count(["email_sent"])
    whatsapps_sent = _count(["whatsapp_sent"])
    notes_added = _count(["note_added"])
    meetings_booked = _count(["meeting_scheduled"])
    status_changes_today = [a for a in today_activities if a.get("activity_type") == "status_changed"]

    new_leads_today = list(leads_collection.find(
        {"created_at": {"$gte": day_start_iso, "$lte": now_iso}},
        {"_id": 1, "first_name": 1, "last_name": 1, "company_name": 1, "icp_score": 1, "source_channel": 1},
    ))
    new_leads_count = len(new_leads_today)

    wins_today = list(leads_collection.find(
        {"status": "won", "updated_at": {"$gte": day_start_iso, "$lte": now_iso}},
        {"_id": 1, "first_name": 1, "last_name": 1, "company_name": 1, "deal_value": 1},
    ))
    losses_today = list(leads_collection.find(
        {"status": "lost", "updated_at": {"$gte": day_start_iso, "$lte": now_iso}},
        {"_id": 1, "first_name": 1, "last_name": 1, "company_name": 1, "lost_reason": 1},
    ))

    won_value = sum((w.get("deal_value") or 0) for w in wins_today)

    rep_map = {}
    for a in today_activities:
        u = a.get("user_id") or "unknown"
        bucket = rep_map.setdefault(u, {"name": u, "calls": 0, "emails": 0, "whatsapps": 0, "notes": 0, "total": 0})
        t = a.get("activity_type")
        if t in ("call_made", "meeting_done", "call"):
            bucket["calls"] += 1
        elif t == "email_sent":
            bucket["emails"] += 1
        elif t == "whatsapp_sent":
            bucket["whatsapps"] += 1
        elif t == "note_added":
            bucket["notes"] += 1
        bucket["total"] += 1
    rep_rows = sorted(rep_map.values(), key=lambda r: r["total"], reverse=True)[:5]

    hot_untouched = list(leads_collection.find(
        {"icp_score": {"$gte": 80}, "status": "new", "last_contacted_at": {"$in": [None]}},
        {"_id": 1, "first_name": 1, "last_name": 1, "company_name": 1, "icp_score": 1, "source_channel": 1},
    ).limit(5))

    overdue_pending = leads_collection.count_documents({
        "next_followup_at": {"$lt": now_iso},
        "status": {"$nin": ["won", "lost", "unqualified"]},
    })

    try:
        tomorrow_plan = _compute_call_priority(limit=3).get("priority", [])[:3]
    except Exception:
        tomorrow_plan = []

    total_touches = calls_logged + emails_sent + whatsapps_sent
    momentum = "strong" if total_touches >= 15 else "steady" if total_touches >= 5 else "quiet"

    return {
        "date_label": local_now.strftime("%A, %b %d"),
        "totals": {
            "calls": calls_logged,
            "emails": emails_sent,
            "whatsapps": whatsapps_sent,
            "notes": notes_added,
            "meetings_booked": meetings_booked,
            "status_changes": len(status_changes_today),
            "total_touches": total_touches,
            "new_leads": new_leads_count,
            "wins": len(wins_today),
            "losses": len(losses_today),
            "won_value": won_value,
            "won_value_label": _fmt_inr(won_value) if won_value else "—",
            "overdue_pending": overdue_pending,
        },
        "momentum": momentum,
        "wins": [{"name": (w.get("company_name") or f"{w.get('first_name','')} {w.get('last_name','')}".strip()), "value": w.get("deal_value"), "value_label": _fmt_inr(w.get("deal_value")) if w.get("deal_value") else "—"} for w in wins_today[:5]],
        "losses": [{"name": (loss.get("company_name") or f"{loss.get('first_name','')} {loss.get('last_name','')}".strip()), "reason": (loss.get("lost_reason") or "—").replace("_", " ").title()} for loss in losses_today[:5]],
        "rep_rows": rep_rows,
        "hot_untouched": [{"name": f"{h.get('first_name','')} {h.get('last_name','')}".strip() or h.get("company_name", "Lead"), "company": h.get("company_name"), "score": h.get("icp_score"), "source": (h.get("source_channel") or "—").replace("_", " ").title()} for h in hot_untouched],
        "tomorrow_plan": [{"name": f"{p.get('first_name','')} {p.get('last_name','')}".strip(), "company": p.get("company_name"), "icp_score": p.get("icp_score"), "phone": p.get("phone")} for p in tomorrow_plan],
    }


def _render_eod_wrap_html(wrap: dict, founder_name: str) -> str:
    t = wrap["totals"]
    momentum = wrap["momentum"]
    momentum_color = {"strong": "#16A34A", "steady": "#7C35DC", "quiet": "#D97706"}.get(momentum, "#7C35DC")
    momentum_bg = {"strong": "#DCFCE7", "steady": "#F4F0FF", "quiet": "#FEF3C7"}.get(momentum, "#F4F0FF")
    momentum_label = {"strong": "STRONG DAY", "steady": "STEADY DAY", "quiet": "QUIET DAY"}.get(momentum, "STEADY DAY")

    def _tile(label, value, accent="#7C35DC"):
        return f"""
        <td style="padding:6px;width:25%;vertical-align:top;">
          <div style="background:#FAF7FF;border:1px solid #E8E0F5;border-radius:12px;padding:14px;text-align:center;">
            <div style="font-size:24px;font-weight:800;color:{accent};line-height:1;">{value}</div>
            <div style="font-size:10px;font-weight:700;color:#5A4A7A;letter-spacing:0.5px;text-transform:uppercase;margin-top:6px;">{label}</div>
          </div>
        </td>"""

    kpi_row1 = _tile("Calls", t["calls"], "#7C35DC") + _tile("Emails", t["emails"], "#7C35DC") + _tile("WhatsApps", t["whatsapps"], "#16A34A") + _tile("New Leads", t["new_leads"], "#C044E0")
    kpi_row2 = _tile("Wins", t["wins"], "#16A34A") + _tile("Losses", t["losses"], "#FF3B30") + _tile("Meetings", t["meetings_booked"], "#7C35DC") + _tile("Overdue", t["overdue_pending"], "#D97706")

    if wrap["wins"]:
        wins_html = "".join([f'<div style="padding:10px 14px;border-bottom:1px solid #F0ECF9;"><span style="font-weight:700;color:#1A0A2E;font-size:13px;">🏆 {w["name"]}</span><span style="float:right;color:#16A34A;font-weight:700;font-size:13px;">{w["value_label"]}</span></div>' for w in wrap["wins"]])
        wins_block = f'<div style="background:#fff;border:1px solid #16A34A22;border-radius:12px;overflow:hidden;margin-bottom:16px;"><div style="padding:12px 14px;background:#DCFCE7;font-size:11px;font-weight:800;color:#16A34A;letter-spacing:1px;text-transform:uppercase;">Wins today · {t["won_value_label"]}</div>{wins_html}</div>'
    else:
        wins_block = ""

    if wrap["hot_untouched"]:
        hot_html = "".join([f'<div style="padding:10px 14px;border-bottom:1px solid #F0ECF9;"><span style="font-weight:700;color:#1A0A2E;font-size:13px;">🔥 {h["name"]}</span> <span style="color:#9B8AB0;font-size:12px;">· {h["source"]} · ICP {h["score"]}</span></div>' for h in wrap["hot_untouched"]])
        hot_block = f'<div style="background:#fff;border:1px solid #FF3B3022;border-radius:12px;overflow:hidden;margin-bottom:16px;"><div style="padding:12px 14px;background:#FEE2E2;font-size:11px;font-weight:800;color:#FF3B30;letter-spacing:1px;text-transform:uppercase;">Hot leads still untouched</div>{hot_html}</div>'
    else:
        hot_block = ""

    if wrap["rep_rows"]:
        rep_rows_html = "".join([f'<tr><td style="padding:8px 14px;border-bottom:1px solid #F0ECF9;font-size:12px;color:#1A0A2E;">{r["name"]}</td><td style="padding:8px 14px;border-bottom:1px solid #F0ECF9;font-size:12px;color:#5A4A7A;text-align:right;">{r["calls"]} calls · {r["emails"]} emails · {r["whatsapps"]} WA</td><td style="padding:8px 14px;border-bottom:1px solid #F0ECF9;font-size:12px;color:#7C35DC;font-weight:700;text-align:right;">{r["total"]}</td></tr>' for r in wrap["rep_rows"]])
        rep_block = f'<div style="background:#fff;border:1px solid #E8E0F5;border-radius:12px;overflow:hidden;margin-bottom:16px;"><div style="padding:12px 14px;background:#FAF7FF;font-size:11px;font-weight:800;color:#7C35DC;letter-spacing:1px;text-transform:uppercase;">Rep activity</div><table cellpadding="0" cellspacing="0" border="0" width="100%">{rep_rows_html}</table></div>'
    else:
        rep_block = ""

    if wrap["tomorrow_plan"]:
        tom_html = "".join([f'<div style="padding:10px 14px;border-bottom:1px solid #F0ECF9;"><span style="font-weight:700;color:#1A0A2E;font-size:13px;">☀️ {p["name"]}</span> <span style="color:#9B8AB0;font-size:12px;">· {p.get("company") or "—"} · ICP {p.get("icp_score") or "—"}</span></div>' for p in wrap["tomorrow_plan"]])
        tom_block = f'<div style="background:#fff;border:1px solid #E8E0F5;border-radius:12px;overflow:hidden;"><div style="padding:12px 14px;background:linear-gradient(135deg,#7C35DC 0%,#C044E0 100%);font-size:11px;font-weight:800;color:#fff;letter-spacing:1px;text-transform:uppercase;">Tomorrow\'s top 3 calls</div>{tom_html}</div>'
    else:
        tom_block = ""

    return f"""<!DOCTYPE html><html><body style="margin:0;padding:0;background:#FAFAFA;font-family:'Plus Jakarta Sans',Arial,sans-serif;">
<table cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#FAFAFA;padding:32px 16px;">
  <tr><td align="center">
    <table cellpadding="0" cellspacing="0" border="0" width="600" style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 20px rgba(124,53,220,0.08);">
      <tr><td style="background:linear-gradient(135deg,#1A0F38 0%,#0E0820 100%);padding:28px 24px;color:#fff;">
        <div style="font-size:11px;font-weight:600;opacity:0.85;letter-spacing:1.5px;text-transform:uppercase;color:#C9B6FF;">ARIA · End-of-Day Wrap</div>
        <div style="font-size:24px;font-weight:800;margin-top:6px;">Wrap-up, {founder_name}</div>
        <div style="font-size:13px;margin-top:6px;opacity:0.85;">{wrap["date_label"]} — here's what your team shipped today.</div>
        <div style="margin-top:14px;display:inline-block;padding:6px 14px;border-radius:999px;background:{momentum_bg};color:{momentum_color};font-size:11px;font-weight:800;letter-spacing:1px;text-transform:uppercase;">{momentum_label} · {t["total_touches"]} touches</div>
      </td></tr>
      <tr><td style="padding:18px 18px 8px 18px;">
        <table cellpadding="0" cellspacing="0" border="0" width="100%"><tr>{kpi_row1}</tr><tr>{kpi_row2}</tr></table>
      </td></tr>
      <tr><td style="padding:8px 18px 18px 18px;">
        {wins_block}
        {hot_block}
        {rep_block}
        {tom_block}
      </td></tr>
      <tr><td style="padding:20px 24px;border-top:1px solid #F0ECF9;background:#FAFAFA;">
        <div style="font-size:12px;color:#9B8AB0;text-align:center;">ARIA tallied today's activity from your Lead Inbox. Tomorrow's morning call plan lands at 8 AM.</div>
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>"""


async def _send_eod_wrap(recipient_email: str, tz_off_hours: float = 0.0, manual: bool = False) -> dict:
    if not recipient_email:
        return {"sent": False, "error": "no_recipient"}
    if not manual:
        try:
            from routes.notifications import should_notify_email
            if not should_notify_email(recipient_email, "weekly_recap", tz_off_hours):
                print(f"[EODWrap] Skipped {recipient_email} — weekly_recap email muted or quiet hours")
                return {"sent": False, "error": "muted_by_pref"}
        except Exception as e:
            print(f"[EODWrap] pref-gate error (allowing send): {e}")
    wrap = _compute_eod_wrap(tz_off_hours=tz_off_hours)
    founder_name = (aria_settings_collection.find_one({}) or {}).get("founder_name") or "founder"
    html = _render_eod_wrap_html(wrap, founder_name)
    t = wrap["totals"]
    if t["wins"] > 0:
        subject = f"🏆 {t['wins']} won · {t['total_touches']} touches today"
    elif t["total_touches"] >= 10:
        subject = f"📞 {t['total_touches']} touches · {wrap['date_label']}"
    elif t["total_touches"] == 0:
        subject = "😴 Quiet day — 0 outreach logged"
    else:
        subject = f"📊 {t['total_touches']} touches · {t['new_leads']} new leads"
    params = {
        "from": os.getenv("SENDER_EMAIL", "onboarding@resend.dev"),
        "to": [recipient_email],
        "subject": subject,
        "html": html,
    }
    try:
        await asyncio.to_thread(resend.Emails.send, params)
        now_iso = datetime.now(timezone.utc).isoformat()
        eod_wrap_collection.update_one(
            {"scope": "workspace"},
            {"$set": {
                "last_sent_at": now_iso,
                "last_sent_date": (datetime.now(timezone.utc) + timedelta(hours=tz_off_hours)).strftime("%Y-%m-%d"),
                "last_sent_touches": t["total_touches"],
                "last_sent_manual": manual,
            }},
            upsert=True,
        )
        return {"sent": True, "touches": t["total_touches"], "recipient": recipient_email}
    except Exception as e:
        print(f"EOD wrap email failed: {e}")
        return {"sent": False, "error": str(e)}


@router.get("/api/aria/eod-wrap/config")
async def get_eod_wrap_config(current_user: dict = Depends(get_current_user)):
    cfg = _get_eod_wrap_config()
    if not cfg:
        return {
            "enabled": False,
            "send_to_email": current_user.get("email"),
            "send_hour_local": 18,
            "timezone_offset_hours": 5.5,
            "last_sent_at": None,
            "last_sent_date": None,
            "last_sent_touches": 0,
        }
    cfg.pop("scope", None)
    return cfg


@router.put("/api/aria/eod-wrap/config")
async def save_eod_wrap_config(cfg: EndOfDayWrapConfig, current_user: dict = Depends(get_current_user)):
    payload = cfg.dict()
    payload["scope"] = "workspace"
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    payload["updated_by"] = current_user["email"]
    eod_wrap_collection.update_one({"scope": "workspace"}, {"$set": payload}, upsert=True)
    payload.pop("scope", None)
    return payload


@router.post("/api/aria/eod-wrap/send-now")
async def send_eod_wrap_now(current_user: dict = Depends(get_current_user)):
    cfg = _get_eod_wrap_config()
    recipient = (cfg or {}).get("send_to_email") or current_user.get("email")
    tz_off = float((cfg or {}).get("timezone_offset_hours") or 0.0)
    if not recipient:
        raise HTTPException(status_code=400, detail="No recipient email configured. Set it in Settings → ARIA → End-of-Day Wrap.")
    res = await _send_eod_wrap(recipient, tz_off_hours=tz_off, manual=True)
    if not res.get("sent"):
        raise HTTPException(status_code=500, detail=f"Failed to send: {res.get('error')}")
    return res


@router.get("/api/aria/eod-wrap/preview")
async def eod_wrap_preview(current_user: dict = Depends(get_current_user)):
    cfg = _get_eod_wrap_config()
    tz_off = float((cfg or {}).get("timezone_offset_hours") or 0.0)
    wrap = _compute_eod_wrap(tz_off_hours=tz_off)
    founder_name = (aria_settings_collection.find_one({}) or {}).get("founder_name") or "founder"
    html = _render_eod_wrap_html(wrap, founder_name)
    return {"html": html, "wrap": wrap}


@router.get("/api/aria/today")
async def aria_today(current_user: dict = Depends(get_current_user)):
    """Lightweight live snapshot of today's wrap totals — for the Dashboard widget."""
    from server import _fmt_inr  # late import (circular avoidance)
    cfg = _get_eod_wrap_config()
    tz_off = float((cfg or {}).get("timezone_offset_hours") or 0.0)
    wrap = _compute_eod_wrap(tz_off_hours=tz_off)
    t = wrap["totals"]
    momentum = wrap["momentum"]
    if t["wins"] > 0:
        headline = f"{t['wins']} won today · {_fmt_inr(t['won_value']) if t['won_value'] else 'value pending'}"
    elif t["total_touches"] >= 15:
        headline = f"Strong day — {t['total_touches']} touches logged"
    elif t["total_touches"] >= 5:
        headline = f"Steady momentum — {t['total_touches']} touches"
    elif t["total_touches"] > 0:
        headline = f"Slow start — only {t['total_touches']} touches so far"
    else:
        headline = "No outreach logged yet today"
    return {
        "date_label": wrap["date_label"],
        "momentum": momentum,
        "headline": headline,
        "totals": t,
        "hot_untouched_count": len(wrap["hot_untouched"]),
        "tomorrow_top_3": wrap["tomorrow_plan"][:3],
    }


async def eod_wrap_loop():
    """Background loop: every 60s, fire the wrap when local time matches."""
    while True:
        try:
            cfg = _get_eod_wrap_config()
            if cfg and cfg.get("enabled") and cfg.get("send_to_email"):
                send_hour_local = int(cfg.get("send_hour_local", 18))
                tz_off = float(cfg.get("timezone_offset_hours", 0.0))
                target_minute_of_day_utc = int(((send_hour_local * 60) - (tz_off * 60)) % 1440)
                now_utc = datetime.now(timezone.utc)
                current_minute_of_day_utc = now_utc.hour * 60 + now_utc.minute
                in_window = 0 <= (current_minute_of_day_utc - target_minute_of_day_utc) <= 5
                local_today_str = (now_utc + timedelta(hours=tz_off)).strftime("%Y-%m-%d")
                last_date = cfg.get("last_sent_date")
                if in_window and last_date != local_today_str:
                    print(f"[EODWrap] Triggering send to {cfg['send_to_email']} (local {send_hour_local}:00, tz_off={tz_off})")
                    await _send_eod_wrap(cfg["send_to_email"], tz_off_hours=tz_off, manual=False)
        except Exception as e:
            print(f"[EODWrap] loop error: {e}")
        await asyncio.sleep(60)
