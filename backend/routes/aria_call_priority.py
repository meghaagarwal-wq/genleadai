"""iter108 — ACTION 3 (continued): ARIA call-priority + daily call-plan.

Two related features extracted as one module:

1. **Best Time to Call** — given a lead, compute a 0-100 `call_score` blending:
   - Brochure-open recency
   - Lead timezone (resolved from country + phone country code)
   - Reply-hour heatmap (when the lead has historically replied)
   Returns urgency `now`/`soon`/`later` + suggested-action string.

2. **Daily Call Plan** — for the founder's workspace, every morning email
   the top 5 leads to call today (with tel: links + reason chips).
   Includes a background loop ticking every 60s that checks each workspace's
   configured local hour-of-day against UTC and fires once per day.

Endpoints:
  GET  /api/aria/best-time-to-call/{lead_id}
  GET  /api/aria/call-priority
  GET  /api/aria/daily-call-plan/config
  PUT  /api/aria/daily-call-plan/config
  POST /api/aria/daily-call-plan/send-now
  GET  /api/aria/daily-call-plan/preview

Public helpers (used by EOD-wrap):
  - `_compute_call_priority(limit, tenant_id)` — top-N priority leads
  - `_compute_best_time_to_call_for_lead(lead)` — score one lead
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import List, Optional

import resend
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from pymongo import DESCENDING

from deps import (
    activities_collection,
    aria_settings_collection,
    db,
    get_current_user,
    leads_collection,
)

router = APIRouter(tags=["iter108-aria-call-priority"])

# Re-use the lead-magnet collection for brochure-open recency. Importing
# the constant rather than re-declaring keeps them in lockstep.
from routes.lead_magnets import lead_magnet_views_collection  # noqa: E402

daily_call_plan_collection = db["daily_call_plan_settings"]


# ── Timezone resolution ─────────────────────────────────────────────────
_COUNTRY_TZ = {
    "india": ("IST", 5.5), "in": ("IST", 5.5),
    "united states": ("EST", -5.0), "usa": ("EST", -5.0), "us": ("EST", -5.0),
    "united kingdom": ("GMT", 0.0), "uk": ("GMT", 0.0), "gb": ("GMT", 0.0),
    "canada": ("EST", -5.0), "ca": ("EST", -5.0),
    "australia": ("AEDT", 11.0), "au": ("AEDT", 11.0),
    "germany": ("CET", 1.0), "de": ("CET", 1.0),
    "france": ("CET", 1.0), "fr": ("CET", 1.0),
    "spain": ("CET", 1.0), "es": ("CET", 1.0),
    "italy": ("CET", 1.0), "it": ("CET", 1.0),
    "netherlands": ("CET", 1.0), "nl": ("CET", 1.0),
    "singapore": ("SGT", 8.0), "sg": ("SGT", 8.0),
    "japan": ("JST", 9.0), "jp": ("JST", 9.0),
    "uae": ("GST", 4.0), "ae": ("GST", 4.0),
    "brazil": ("BRT", -3.0), "br": ("BRT", -3.0),
    "mexico": ("CST", -6.0), "mx": ("CST", -6.0),
}


def _resolve_lead_timezone(lead: dict):
    country = (lead.get("country") or "").strip().lower()
    if country in _COUNTRY_TZ:
        return _COUNTRY_TZ[country]
    digits = "".join(c for c in (lead.get("phone") or "") if c.isdigit())
    if digits.startswith("91"):
        return _COUNTRY_TZ["india"]
    if digits.startswith("1") and len(digits) >= 10:
        return _COUNTRY_TZ["united states"]
    if digits.startswith("44"):
        return _COUNTRY_TZ["united kingdom"]
    if digits.startswith("61"):
        return _COUNTRY_TZ["australia"]
    if digits.startswith("971"):
        return _COUNTRY_TZ["uae"]
    return ("UTC", 0.0)


def _local_hour_now(utc_offset_hours: float) -> int:
    now_utc = datetime.now(timezone.utc)
    return int((now_utc.hour + now_utc.minute / 60.0 + utc_offset_hours) % 24)


def _format_local_window(start_hour: int, end_hour: int) -> str:
    def fmt(h):
        h = h % 24
        suffix = "AM" if h < 12 else "PM"
        h12 = ((h - 1) % 12) + 1
        return f"{h12}{suffix}"
    return f"{fmt(start_hour)}–{fmt(end_hour)}"


def _compute_reply_window_hours(lead_id: str) -> Optional[List[int]]:
    activities = list(activities_collection.find(
        {"lead_id": lead_id, "activity_type": {"$in": ["whatsapp_received", "email_received"]}},
        {"_id": 0, "created_at": 1},
    ).limit(50))
    if not activities:
        return None
    hours = set()
    for a in activities:
        ca = a.get("created_at")
        if not ca:
            continue
        try:
            hours.add(datetime.fromisoformat(ca.replace("Z", "+00:00")).hour)
        except Exception:
            pass
    return sorted(hours) if hours else None


# ── Per-lead scoring ────────────────────────────────────────────────────
def _compute_best_time_to_call_for_lead(lead: dict) -> dict:
    lead_id = lead.get("id") or lead.get("_id_str")
    tz_label, utc_off = _resolve_lead_timezone(lead)
    local_hour = _local_hour_now(utc_off)
    reply_hours = _compute_reply_window_hours(lead_id) if lead_id else None
    if reply_hours:
        start_h = max(0, min(reply_hours) - 1)
        end_h = min(23, max(reply_hours) + 1)
    else:
        start_h, end_h = 10, 16
    in_window = start_h <= local_hour <= end_h

    last_view = (lead_magnet_views_collection.find_one(
        {"lead_id": lead_id, "kind": "view"},
        {"_id": 0, "created_at": 1},
        sort=[("created_at", DESCENDING)],
    ) if lead_id else None)
    minutes_since_view = None
    if last_view and last_view.get("created_at"):
        try:
            dt = datetime.fromisoformat(last_view["created_at"].replace("Z", "+00:00"))
            minutes_since_view = max(0, int((datetime.now(timezone.utc) - dt).total_seconds() / 60))
        except Exception:
            pass

    score = 0
    reasons: List[str] = []
    if minutes_since_view is not None and minutes_since_view <= 30:
        score += 60
        reasons.append(f"opened brochure {minutes_since_view}m ago")
    elif minutes_since_view is not None and minutes_since_view <= 240:
        score += 30
        reasons.append(f"opened brochure {minutes_since_view}m ago")
    if in_window:
        score += 30
        reasons.append(f"in {tz_label} active hours")
    else:
        reasons.append(f"outside {tz_label} active hours ({_format_local_window(start_h, end_h)})")
    icp = lead.get("icp_score") or 0
    if icp >= 70:
        score += 20
        reasons.append(f"hot ICP ({icp})")
    elif icp >= 40:
        score += 10

    if score >= 75:
        urgency, suggested_action = "now", "Call now"
    elif score >= 45:
        urgency = "soon"
        suggested_action = f"Good window now ({tz_label})" if in_window else f"Wait for their {tz_label} window"
    else:
        urgency = "later"
        if in_window:
            suggested_action = f"Available now ({tz_label})"
        else:
            hours_to_window = start_h - local_hour if local_hour < start_h else (24 - local_hour) + start_h
            suggested_action = f"Best in ~{hours_to_window}h ({_format_local_window(start_h, end_h)} {tz_label})"

    return {
        "tz_label": tz_label,
        "utc_offset_hours": utc_off,
        "lead_local_hour": local_hour,
        "active_window_local": _format_local_window(start_h, end_h),
        "active_start_hour": start_h,
        "active_end_hour": end_h,
        "in_window": in_window,
        "minutes_since_brochure_open": minutes_since_view,
        "call_score": min(100, score),
        "urgency": urgency,
        "suggested_action": suggested_action,
        "reasons": reasons,
        "data_source": "reply_heatmap" if reply_hours else "default_business_hours",
    }


# ── Top-N priority across workspace ─────────────────────────────────────
def _compute_call_priority(limit: int = 3, tenant_id: Optional[str] = None) -> dict:
    limit = max(1, min(limit, 50))
    tf = {"tenant_id": tenant_id} if tenant_id else {}

    candidate_ids = set()
    for v in lead_magnet_views_collection.find(
        {"kind": "view", **tf},
        {"_id": 0, "lead_id": 1, "created_at": 1},
    ).sort("created_at", DESCENDING).limit(50):
        if v.get("lead_id"):
            candidate_ids.add(v["lead_id"])
    for d in leads_collection.find(
        {"icp_score": {"$gte": 60}, "status": {"$nin": ["won", "lost", "unqualified"]}, **tf},
        {"_id": 1},
    ).limit(30):
        candidate_ids.add(str(d["_id"]))

    results = []
    for lid in candidate_ids:
        try:
            lead_doc = leads_collection.find_one(
                {"_id": ObjectId(lid), **tf},
                {"_id": 0, "first_name": 1, "last_name": 1, "company_name": 1, "country": 1, "phone": 1, "icp_score": 1, "icp_tier": 1, "status": 1, "email": 1},
            )
        except Exception:
            continue
        if not lead_doc:
            continue
        lead_doc["id"] = lid
        score_data = _compute_best_time_to_call_for_lead(lead_doc)
        results.append({
            "lead_id": lid,
            "first_name": lead_doc.get("first_name"),
            "last_name": lead_doc.get("last_name"),
            "company_name": lead_doc.get("company_name"),
            "phone": lead_doc.get("phone"),
            "email": lead_doc.get("email"),
            "icp_score": lead_doc.get("icp_score"),
            "icp_tier": lead_doc.get("icp_tier"),
            **score_data,
        })

    results.sort(key=lambda x: (x["call_score"], x.get("icp_score") or 0), reverse=True)
    return {"priority": results[:limit], "checked_count": len(candidate_ids)}


# ── Endpoints — best-time + priority ────────────────────────────────────
@router.get("/api/aria/best-time-to-call/{lead_id}")
async def best_time_to_call_for_lead(lead_id: str, current_user: dict = Depends(get_current_user)):
    try:
        lead_doc = leads_collection.find_one(
            {"_id": ObjectId(lead_id)},
            {"_id": 0, "first_name": 1, "last_name": 1, "country": 1, "phone": 1, "icp_score": 1, "icp_tier": 1},
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Lead not found")
    if not lead_doc:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead_doc["id"] = lead_id
    return _compute_best_time_to_call_for_lead(lead_doc)


@router.get("/api/aria/call-priority")
async def aria_call_priority(limit: int = 3, current_user: dict = Depends(get_current_user)):
    return _compute_call_priority(limit, tenant_id=current_user.get("tenant_id"))


# ── Daily Call Plan ─────────────────────────────────────────────────────
class DailyCallPlanConfig(BaseModel):
    enabled: bool = False
    send_to_email: Optional[EmailStr] = None
    send_hour_local: int = Field(8, ge=0, le=23)
    timezone_offset_hours: float = Field(0.0, ge=-12.0, le=14.0)
    plan_size: int = Field(5, ge=1, le=10)


def _get_daily_call_plan_config() -> dict:
    return daily_call_plan_collection.find_one({"scope": "workspace"}, {"_id": 0}) or {}


def _render_daily_call_plan_html(priority: List[dict], founder_name: str, plan_date: str) -> str:
    if not priority:
        rows_html = '<tr><td style="padding:24px;text-align:center;color:#9B8AB0;font-size:14px;">No high-priority leads today. Pipeline is calm — perfect time for outbound.</td></tr>'
    else:
        rows_html = ""
        for i, p in enumerate(priority, 1):
            urgency = p.get("urgency", "later")
            urg_color = {"now": "#16A34A", "soon": "#D97706", "later": "#7C35DC"}.get(urgency, "#7C35DC")
            urg_bg = {"now": "#DCFCE7", "soon": "#FEF3C7", "later": "#F4F0FF"}.get(urgency, "#F4F0FF")
            urg_label = {"now": "CALL NOW", "soon": "SOON", "later": "LATER"}.get(urgency, urgency.upper())
            phone = p.get("phone") or ""
            phone_html = f'<a href="tel:{phone}" style="display:inline-block;background:linear-gradient(135deg,#7C35DC 0%,#C044E0 100%);color:#fff;padding:8px 16px;border-radius:8px;text-decoration:none;font-weight:600;font-size:13px;">📞 Call</a>' if phone else '<span style="color:#9B8AB0;font-size:12px;">No phone</span>'
            company = p.get("company_name") or "—"
            reasons_text = " · ".join((p.get("reasons") or [])[:2])
            rows_html += f"""
            <tr>
              <td style="padding:14px 16px;border-bottom:1px solid #F0ECF9;">
                <table cellpadding="0" cellspacing="0" border="0" width="100%">
                  <tr>
                    <td style="vertical-align:top;width:32px;color:#9B8AB0;font-weight:700;font-size:14px;">#{i}</td>
                    <td style="vertical-align:top;">
                      <div style="margin-bottom:4px;">
                        <span style="font-size:15px;font-weight:700;color:#1A0A2E;">{p.get('first_name','')} {p.get('last_name','')}</span>
                        <span style="display:inline-block;margin-left:6px;padding:2px 6px;border-radius:4px;background:{urg_bg};color:{urg_color};font-size:10px;font-weight:700;letter-spacing:0.5px;">{urg_label}</span>
                        <span style="display:inline-block;margin-left:4px;padding:2px 6px;border-radius:4px;background:#F4F0FF;color:#7C35DC;font-size:10px;font-weight:700;">ICP {p.get('icp_score', 0)}</span>
                      </div>
                      <div style="font-size:12px;color:#5A4A7A;margin-bottom:2px;">{company}</div>
                      <div style="font-size:11px;color:#9B8AB0;font-style:italic;">{reasons_text}</div>
                    </td>
                    <td style="vertical-align:top;text-align:right;width:90px;">{phone_html}</td>
                  </tr>
                </table>
              </td>
            </tr>"""

    return f"""<!DOCTYPE html><html><body style="margin:0;padding:0;background:#FAFAFA;font-family:'Plus Jakarta Sans',Arial,sans-serif;">
<table cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#FAFAFA;padding:32px 16px;">
  <tr><td align="center">
    <table cellpadding="0" cellspacing="0" border="0" width="600" style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 20px rgba(124,53,220,0.08);">
      <tr><td style="background:linear-gradient(135deg,#7C35DC 0%,#C044E0 100%);padding:28px 24px;color:#fff;">
        <div style="font-size:12px;font-weight:600;opacity:0.85;letter-spacing:1px;text-transform:uppercase;">ARIA · Daily Call Plan</div>
        <div style="font-size:24px;font-weight:800;margin-top:4px;">Good morning, {founder_name}</div>
        <div style="font-size:13px;margin-top:6px;opacity:0.9;">Your top {len(priority) or 0} leads to call today — {plan_date}</div>
      </td></tr>
      <tr><td>
        <table cellpadding="0" cellspacing="0" border="0" width="100%">{rows_html}</table>
      </td></tr>
      <tr><td style="padding:20px 24px;border-top:1px solid #F0ECF9;background:#FAFAFA;">
        <div style="font-size:12px;color:#9B8AB0;text-align:center;">ARIA scored these by brochure opens, ICP, and timezone fit. Tap a number to call directly from your phone.</div>
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>"""


async def _send_daily_call_plan(recipient_email: str, plan_size: int = 5, manual: bool = False) -> dict:
    if not recipient_email:
        return {"sent": False, "error": "no_recipient"}
    if not manual:
        try:
            from routes.notifications import should_notify_email
            if not should_notify_email(recipient_email, "daily_brief"):
                print(f"[DailyCallPlan] Skipped {recipient_email} — daily_brief email muted or quiet hours")
                return {"sent": False, "error": "muted_by_pref"}
        except Exception as e:
            print(f"[DailyCallPlan] pref-gate error (allowing send): {e}")
    plan = _compute_call_priority(limit=plan_size)
    priority = plan.get("priority", [])
    founder_name = (aria_settings_collection.find_one({}) or {}).get("founder_name") or "founder"
    plan_date = datetime.now(timezone.utc).strftime("%A, %b %d")
    html = _render_daily_call_plan_html(priority, founder_name, plan_date)
    subject = f"☀️ {len(priority)} leads to call today" if priority else "☀️ Pipeline is calm today — outbound time"
    params = {
        "from": os.getenv("SENDER_EMAIL", "onboarding@resend.dev"),
        "to": [recipient_email],
        "subject": subject,
        "html": html,
    }
    try:
        await asyncio.to_thread(resend.Emails.send, params)
        now_iso = datetime.now(timezone.utc).isoformat()
        daily_call_plan_collection.update_one(
            {"scope": "workspace"},
            {"$set": {
                "last_sent_at": now_iso,
                "last_sent_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "last_sent_count": len(priority),
                "last_sent_manual": manual,
            }},
            upsert=True,
        )
        return {"sent": True, "count": len(priority), "recipient": recipient_email}
    except Exception as e:
        print(f"Daily call plan email failed: {e}")
        return {"sent": False, "error": str(e)}


@router.get("/api/aria/daily-call-plan/config")
async def get_daily_call_plan_config(current_user: dict = Depends(get_current_user)):
    cfg = _get_daily_call_plan_config()
    if not cfg:
        return {
            "enabled": False,
            "send_to_email": current_user.get("email"),
            "send_hour_local": 8,
            "timezone_offset_hours": 5.5,
            "plan_size": 5,
            "last_sent_at": None,
            "last_sent_date": None,
            "last_sent_count": 0,
        }
    cfg.pop("scope", None)
    return cfg


@router.put("/api/aria/daily-call-plan/config")
async def save_daily_call_plan_config(cfg: DailyCallPlanConfig, current_user: dict = Depends(get_current_user)):
    payload = cfg.dict()
    payload["scope"] = "workspace"
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    payload["updated_by"] = current_user["email"]
    daily_call_plan_collection.update_one({"scope": "workspace"}, {"$set": payload}, upsert=True)
    payload.pop("scope", None)
    return payload


@router.post("/api/aria/daily-call-plan/send-now")
async def send_daily_call_plan_now(current_user: dict = Depends(get_current_user)):
    cfg = _get_daily_call_plan_config()
    recipient = (cfg or {}).get("send_to_email") or current_user.get("email")
    plan_size = int((cfg or {}).get("plan_size") or 5)
    if not recipient:
        raise HTTPException(status_code=400, detail="No recipient email configured.")
    res = await _send_daily_call_plan(recipient, plan_size=plan_size, manual=True)
    if not res.get("sent"):
        raise HTTPException(status_code=500, detail=f"Failed to send: {res.get('error')}")
    return res


@router.get("/api/aria/daily-call-plan/preview")
async def daily_call_plan_preview(current_user: dict = Depends(get_current_user)):
    cfg = _get_daily_call_plan_config()
    plan_size = int((cfg or {}).get("plan_size") or 5)
    plan = _compute_call_priority(limit=plan_size)
    founder_name = (aria_settings_collection.find_one({}) or {}).get("founder_name") or "founder"
    plan_date = datetime.now(timezone.utc).strftime("%A, %b %d")
    html = _render_daily_call_plan_html(plan.get("priority", []), founder_name, plan_date)
    return {"html": html, "count": len(plan.get("priority", []))}


# ── Background loop ────────────────────────────────────────────────────
async def daily_call_plan_loop():
    """Every 60s, check if it's time to fire today's plan (DST-safe via UTC math)."""
    while True:
        try:
            cfg = _get_daily_call_plan_config()
            if cfg and cfg.get("enabled") and cfg.get("send_to_email"):
                send_hour_local = int(cfg.get("send_hour_local", 8))
                tz_off = float(cfg.get("timezone_offset_hours", 0.0))
                target_minute_of_day_utc = int(((send_hour_local * 60) - (tz_off * 60)) % 1440)
                now_utc = datetime.now(timezone.utc)
                current_minute_of_day_utc = now_utc.hour * 60 + now_utc.minute
                in_window = 0 <= (current_minute_of_day_utc - target_minute_of_day_utc) <= 5
                today_str = now_utc.strftime("%Y-%m-%d")
                last_date = cfg.get("last_sent_date")
                if in_window and last_date != today_str:
                    print(f"[DailyCallPlan] Triggering send to {cfg['send_to_email']}")
                    await _send_daily_call_plan(
                        cfg["send_to_email"],
                        plan_size=int(cfg.get("plan_size", 5)),
                        manual=False,
                    )
        except Exception as e:
            print(f"[DailyCallPlan] loop error: {e}")
        await asyncio.sleep(60)
