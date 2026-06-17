"""ARIA — Unified Dashboard router.

iter150 — Three workspace-mode-aware dashboards:
  • POST /api/dashboard/b2c           — B2C Automation Command Center
  • POST /api/dashboard/b2b-founder   — B2B Founder Intelligence Overview
  • POST /api/dashboard/b2b-sales     — B2B Sales Pipeline (action-first)

Each endpoint returns ALL sections for that dashboard in one response so
the React page loads in a single fetch. Sections with insufficient data
return `coming_soon: True` + an empty payload so the UI can render a
"connect X" empty state instead of a fake zero.

All data is tenant-isolated via `get_current_user.tenant_id`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from deps import db, get_current_user, leads_collection
from .dashboard_data import (
    get_tenant_mode, get_tenant_currency, get_tenant_hourly_rate,
    latest_score_changes,
)
from .lead_query import count_tenant_leads, iter_tenant_leads

router = APIRouter(prefix="/api/dashboard", tags=["iter150-dashboards"])

pt_leads_col       = db["pt_leads"]
pt_insights_col    = db["pt_insights"]
outbound_log       = db["outbound_log"]
inbound_msgs       = db["inbound_messages"]
aria_conv          = db["aria_conversations"]
booking_events     = db["booking_events"]
asset_clicks_col   = db["asset_clicks"]
score_history      = db["score_history"]

# Channel colours — kept stable across all dashboards (spec line 95).
CHANNEL_COLOURS = {
    "instagram": "#0E9F86", "whatsapp": "#7C35DC", "website": "#F59E0B",
    "referral": "#6366F1", "youtube": "#EF4444", "facebook": "#3B82F6",
    "google": "#10B981", "linkedin": "#1E3A8A", "email": "#94A3B8",
    "lemlist": "#7C35DC", "saleshandy": "#0E9F86", "manual": "#94A3B8",
}


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _today_range(tz_offset: int = 0):
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return day_start.isoformat(), now.isoformat()


def _greet(now_iso_hour: int) -> str:
    if now_iso_hour < 12:
        return "Good morning"
    if now_iso_hour < 18:
        return "Good afternoon"
    return "Good evening"


def _trend(curr: int, prev: int) -> Dict[str, Any]:
    if not prev:
        return {"direction": "flat", "pct": None}
    pct = round(((curr - prev) / prev) * 100, 1)
    return {"direction": "up" if curr > prev else "down" if curr < prev else "flat", "pct": pct}


# ─── ARIA time-saved calc (shared across all 3 dashboards) ────────
TIME_PER_TASK_MIN = {"conversation": 8, "research": 12, "insight": 20, "draft": 6}


def _aria_time_saved(tenant_id: str, days: int = 7, hourly_rate: int = 45):
    since_iso = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    convos = aria_conv.count_documents({"tenant_id": tenant_id, "created_at": {"$gte": since_iso}})
    drafts = outbound_log.count_documents({"tenant_id": tenant_id, "ai_powered": True, "created_at": {"$gte": since_iso}})
    insights = pt_insights_col.count_documents({"tenant_id": tenant_id, "created_at": {"$gte": since_iso}})
    research = pt_leads_col.count_documents({"tenant_id": tenant_id, "enrichment_status": "enriched", "updated_at": {"$gte": since_iso}})
    total_min = (convos * TIME_PER_TASK_MIN["conversation"]
                 + drafts * TIME_PER_TASK_MIN["draft"]
                 + insights * TIME_PER_TASK_MIN["insight"]
                 + research * TIME_PER_TASK_MIN["research"])
    hours = round(total_min / 60, 1)
    return {
        "hours": hours,
        "money_equivalent": round(hours * hourly_rate),
        "breakdown": {
            "conversations": convos, "drafts": drafts,
            "insights": insights, "researched": research,
        },
        "days": days,
    }


def _momentum(tenant_id: str, weights: Dict[str, float]) -> Dict[str, Any]:
    """Score 0-100 + label using current vs previous-14d comparison."""
    now = datetime.now(timezone.utc)
    cur_start = (now - timedelta(days=14)).isoformat()
    prev_start = (now - timedelta(days=28)).isoformat()
    cur_end = cur_start
    base = {"tenant_id": tenant_id}

    def _delta_ratio(curr, prev):
        if curr == 0 and prev == 0:
            return 0.5
        if prev == 0:
            return 1.0
        return max(0.0, min(1.0, (curr - prev) / prev / 2 + 0.5))

    metrics = {}
    metrics["leads"] = _delta_ratio(
        pt_leads_col.count_documents({**base, "created_at": {"$gte": cur_start}}),
        pt_leads_col.count_documents({**base, "created_at": {"$gte": prev_start, "$lt": cur_end}}),
    )
    metrics["high_intent"] = _delta_ratio(
        pt_leads_col.count_documents({**base, "created_at": {"$gte": cur_start}, "score": {"$gte": 70}}),
        pt_leads_col.count_documents({**base, "created_at": {"$gte": prev_start, "$lt": cur_end}, "score": {"$gte": 70}}),
    )
    metrics["bookings"] = _delta_ratio(
        booking_events.count_documents({**base, "when": {"$gte": cur_start}}),
        booking_events.count_documents({**base, "when": {"$gte": prev_start, "$lt": cur_end}}),
    )
    raw = sum(metrics[k] * weights.get(k, 0) for k in metrics)
    score = round(raw * 100)
    if score >= 70:
        label, direction = "Accelerating", "up"
    elif score >= 40:
        label, direction = "Steady", "flat"
    else:
        label, direction = "Slowing", "down"

    # Identify primary driver.
    primary = max(metrics, key=metrics.get)
    driver_map = {
        "leads": "lead volume",
        "high_intent": "high-intent share",
        "bookings": "bookings booked",
    }
    if metrics[primary] >= 0.6:
        driver_text = f"Driven by stronger {driver_map[primary]} this fortnight."
    elif metrics[primary] <= 0.3:
        driver_text = f"Held back by softer {driver_map[primary]} this fortnight."
    else:
        driver_text = "All inputs roughly steady vs the prior fortnight."

    return {"score": score, "label": label, "direction": direction, "driver_text": driver_text}


# ───────────────────────── B2C ──────────────────────────────────
@router.get("/b2c")
async def dashboard_b2c(current_user: dict = Depends(get_current_user)):
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        return {"error": "no_tenant"}
    currency = get_tenant_currency(tenant_id)
    hourly = get_tenant_hourly_rate(tenant_id)

    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    week_start = (now - timedelta(days=now.isoweekday() - 1)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    prev_week_start = (now - timedelta(days=now.isoweekday() - 1 + 7)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    last_month_start = (now.replace(day=1) - timedelta(days=1)).replace(day=1).isoformat()

    base = {"tenant_id": tenant_id}

    # ── KPIs ──────────────────────────────────────────────────────
    leads_today = pt_leads_col.count_documents({**base, "created_at": {"$gte": day_start}})
    leads_same_day_last_week = pt_leads_col.count_documents({
        **base,
        "created_at": {
            "$gte": (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
            "$lt": (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
        },
    })
    two_hours_ago = (now - timedelta(hours=2)).isoformat()
    active_convos = outbound_log.count_documents({**base, "created_at": {"$gte": two_hours_ago}})
    bookings_week = booking_events.count_documents({**base, "when": {"$gte": week_start}})
    bookings_last_week = booking_events.count_documents({**base, "when": {"$gte": prev_week_start, "$lt": week_start}})
    leads_this_month = pt_leads_col.count_documents({**base, "created_at": {"$gte": month_start}})
    bookings_this_month = booking_events.count_documents({**base, "when": {"$gte": month_start}})
    conv_rate = round((bookings_this_month / leads_this_month) * 100, 1) if leads_this_month else 0
    leads_last_month = pt_leads_col.count_documents({**base, "created_at": {"$gte": last_month_start, "$lt": month_start}})
    bookings_last_month = booking_events.count_documents({**base, "when": {"$gte": last_month_start, "$lt": month_start}})
    last_conv_rate = round((bookings_last_month / leads_last_month) * 100, 1) if leads_last_month else 0
    pipeline_value = sum(lead.get("deal_value") or 0 for lead in pt_leads_col.find(
        {**base, "stage": {"$nin": ["lost", "dnc"]}, "score": {"$gte": 35}},
        {"_id": 0, "deal_value": 1},
    ))

    # ── Live conversations feed (last 6 by recent activity) ───────
    recent_msgs = list(outbound_log.find(
        {**base, "created_at": {"$gte": (now - timedelta(days=2)).isoformat()}},
        {"_id": 0, "lead_id": 1, "created_at": 1, "message_preview": 1, "channel": 1},
    ).sort("created_at", -1).limit(20))
    seen_ids = set()
    conv_rows = []
    for m in recent_msgs:
        if m["lead_id"] in seen_ids:
            continue
        lead = pt_leads_col.find_one({**base, "id": m["lead_id"]}, {"_id": 0, "first_name": 1, "last_name": 1, "stage": 1})
        if not lead:
            continue
        seen_ids.add(m["lead_id"])
        ts = m["created_at"]
        try:
            mins = int((now - datetime.fromisoformat(ts)).total_seconds() / 60)
        except Exception:
            mins = 999
        if mins < 15:
            status = "live"
        elif lead.get("stage") == "session_pilot":
            status = "booked"
        elif lead.get("stage") in ("hot", "engaged"):
            status = "qualified"
        else:
            status = "waiting"
        name = f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip() or "Unknown"
        conv_rows.append({
            "lead_id": m["lead_id"], "name": name,
            "initials": "".join([p[0] for p in name.split()[:2]]).upper() or "?",
            "status": status,
            "snippet": (m.get("message_preview") or "")[:120],
            "minutes_ago": mins,
        })
        if len(conv_rows) >= 6:
            break

    # ── Lead sources today ────────────────────────────────────────
    source_pipeline = list(pt_leads_col.aggregate([
        {"$match": {**base, "created_at": {"$gte": day_start}}},
        {"$group": {"_id": "$source", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]))
    lead_sources = [{
        "channel": row["_id"] or "manual",
        "count": row["count"],
        "colour": CHANNEL_COLOURS.get((row["_id"] or "manual").lower(), "#94A3B8"),
    } for row in source_pipeline]

    # ── Booking funnel this week ──────────────────────────────────
    week_leads = pt_leads_col.count_documents({**base, "created_at": {"$gte": week_start}})
    week_replied = inbound_msgs.count_documents({**base, "received_at": {"$gte": week_start}})
    week_qualified = pt_leads_col.count_documents({**base, "created_at": {"$gte": week_start}, "score": {"$gte": 40}})
    week_offered = outbound_log.count_documents({**base, "created_at": {"$gte": week_start}, "subject": {"$regex": "book", "$options": "i"}})
    week_booked = booking_events.count_documents({**base, "when": {"$gte": week_start}})

    def _stage(n, prev, label):
        pct = round((n / prev) * 100, 1) if prev else 0
        return {"stage": label, "count": n, "pct_of_prev": pct, "drop_flag": prev and pct < 60}

    funnel = [
        {"stage": "Lead entered", "count": week_leads, "pct_of_prev": 100, "drop_flag": False},
        _stage(week_replied, week_leads, "Replied to ARIA"),
        _stage(week_qualified, week_replied, "Qualified"),
        _stage(week_offered, week_qualified, "Booking offered"),
        _stage(week_booked, week_offered, "Booked"),
    ]
    biggest_drop = None
    for i in range(1, len(funnel)):
        if funnel[i]["drop_flag"]:
            biggest_drop = {
                "from": funnel[i - 1]["stage"], "to": funnel[i]["stage"],
                "loss_pct": round(100 - funnel[i]["pct_of_prev"], 1),
            }
            break

    # ── Sequence perf (lemlist campaigns active) ─────────────────
    seqs = list(pt_leads_col.aggregate([
        {"$match": {**base, "lemlist_data.campaign": {"$exists": True, "$ne": None}}},
        {"$group": {
            "_id": "$lemlist_data.campaign",
            "active": {"$sum": 1},
            "booked": {"$sum": {"$cond": [{"$eq": ["$stage", "session_pilot"]}, 1, 0]}},
        }},
        {"$limit": 10},
    ]))
    sequences = [{
        "name": s["_id"] or "Unnamed sequence",
        "active": s["active"], "booked": s["booked"],
        "rate": round((s["booked"] / s["active"]) * 100, 1) if s["active"] else 0,
    } for s in seqs]

    # ── Ghost lead recovery ──────────────────────────────────────
    two_weeks_ago = (now - timedelta(days=14)).isoformat()
    ghost_candidates = list(pt_leads_col.find(
        {**base,
         "$or": [{"last_activity_at": {"$lt": two_weeks_ago}},
                 {"last_contacted_at": {"$lt": two_weeks_ago}}],
         "score": {"$gte": 40}},
        {"_id": 0, "id": 1, "first_name": 1, "last_name": 1, "company_name": 1, "last_activity_at": 1, "score": 1},
    ).limit(5))
    ghost_leads = []
    for g in ghost_candidates:
        try:
            days_silent = (now - datetime.fromisoformat(g.get("last_activity_at") or now.isoformat())).days
        except Exception:
            days_silent = 99
        ghost_leads.append({
            "id": g["id"],
            "name": f"{g.get('first_name', '')} {g.get('last_name', '')}".strip(),
            "company": g.get("company_name"),
            "days_silent": days_silent,
            "trigger": "Returned to your channel · score > 40",
        })

    return {
        "header": {
            "workspace_name": (db["tenants"].find_one({"id": tenant_id}, {"_id": 0, "name": 1}) or {}).get("name"),
            "owner_name": current_user.get("full_name") or current_user.get("email"),
            "greeting": _greet(now.hour),
            "mode": "B2C Automation",
            "currency": currency,
            "last_refresh": _iso(now),
        },
        "kpis": {
            "leads_today":      {"value": leads_today,      "trend": _trend(leads_today, leads_same_day_last_week),
                                 "spark": _timeseries_count(pt_leads_col, base, "created_at", now)},
            "active_convos":    {"value": active_convos,    "label": "ARIA is handling all of them",
                                 "spark": _timeseries_count(outbound_log, base, "created_at", now)},
            "bookings_week":    {"value": bookings_week,    "trend": _trend(bookings_week, bookings_last_week),
                                 "spark": _timeseries_count(booking_events, base, "when", now)},
            "conversion_rate":  {"value": conv_rate, "unit": "%", "trend": _trend(int(conv_rate * 10), int(last_conv_rate * 10))},
            "revenue_pipeline": {"value": round(pipeline_value), "currency": currency,
                                 "spark": _timeseries_sum(booking_events, base, "when", "deal_value", now)},
        },
        "aria_time_saved": _aria_time_saved(tenant_id, 7, hourly),
        "momentum": _momentum(tenant_id, {"leads": 0.4, "high_intent": 0.4, "bookings": 0.2}),
        "revenue_forecast": _b2c_revenue_forecast(tenant_id, currency),
        "conversations": conv_rows,
        "lead_sources": lead_sources,
        "asset_performance": _asset_performance(tenant_id, day_start),
        "funnel": funnel,
        "biggest_drop": biggest_drop,
        "sequences": sequences,
        "channel_overlap": _channel_overlap(tenant_id),
        "ghost_leads": ghost_leads,
        "cost_per_qualified_lead": _cost_per_qualified_lead(tenant_id, currency, month_start),
    }


def _channel_overlap(tenant_id: str) -> Dict[str, Any]:
    """Leads touched by 2+ channels — they convert higher. Reads `source_channels`
    (array) on pt_leads; falls back to single-channel rows when array missing."""
    rows = list(pt_leads_col.aggregate([
        {"$match": {"tenant_id": tenant_id, "source_channels": {"$exists": True, "$type": "array"}}},
        {"$project": {"_id": 0, "channels": "$source_channels", "score": 1,
                      "is_meeting": {"$cond": [{"$gte": ["$score", 70]}, 1, 0]}}},
    ]))
    if not rows:
        return {"coming_soon": True, "rows": []}
    overlap_buckets: Dict[str, Dict[str, int]] = {}
    for r in rows:
        chs = sorted(set(r.get("channels") or []))
        if len(chs) < 2:
            continue
        key = " + ".join(chs[:3])
        b = overlap_buckets.setdefault(key, {"leads": 0, "meetings": 0})
        b["leads"] += 1
        b["meetings"] += r.get("is_meeting") or 0
    if not overlap_buckets:
        return {"coming_soon": True, "rows": []}
    out_rows = sorted(
        [{"channels": k, "leads": v["leads"], "meetings": v["meetings"],
          "conv_rate": round((v["meetings"] / v["leads"]) * 100, 1) if v["leads"] else 0}
         for k, v in overlap_buckets.items()],
        key=lambda r: r["leads"], reverse=True,
    )[:5]
    return {"coming_soon": False, "rows": out_rows}


def _cost_per_qualified_lead(tenant_id: str, currency: str, month_start: str) -> Dict[str, Any]:
    """Per-channel ad-spend / qualified-lead ratio. Reads `ad_spend` collection
    when present; returns coming_soon when no spend recorded."""
    spend_col = db["ad_spend"]
    spend_rows = list(spend_col.aggregate([
        {"$match": {"tenant_id": tenant_id, "month": month_start[:7]}},
        {"$group": {"_id": "$channel", "spend": {"$sum": "$amount"}}},
    ]))
    if not spend_rows:
        return {"coming_soon": True, "rows": []}
    out = []
    for s in spend_rows:
        qualified = pt_leads_col.count_documents({
            "tenant_id": tenant_id, "source": s["_id"],
            "created_at": {"$gte": month_start}, "score": {"$gte": 40},
        })
        cpql = round(s["spend"] / qualified, 0) if qualified else None
        out.append({"channel": s["_id"], "spend": round(s["spend"]),
                    "qualified": qualified, "cpql": cpql, "currency": currency})
    return {"coming_soon": False, "rows": sorted(out, key=lambda r: (r["cpql"] or 1e9))}


def _b2c_revenue_forecast(tenant_id: str, currency: str) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_start = (month_start - timedelta(days=1)).replace(day=1)

    actual = sum(b.get("deal_value") or 0 for b in booking_events.find(
        {"tenant_id": tenant_id, "when": {"$gte": month_start.isoformat()}},
        {"_id": 0, "deal_value": 1},
    ))
    last_month = sum(b.get("deal_value") or 0 for b in booking_events.find(
        {"tenant_id": tenant_id, "when": {"$gte": last_month_start.isoformat(), "$lt": month_start.isoformat()}},
        {"_id": 0, "deal_value": 1},
    ))
    day_of_month = now.day
    days_in_month = 30
    projected = round((actual / max(1, day_of_month)) * days_in_month)
    pct_of_last = round((actual / last_month) * 100, 1) if last_month else 0
    return {
        "currency": currency,
        "actual_to_date": round(actual),
        "projected_end_of_month": projected,
        "last_month_actual": round(last_month),
        "pct_of_last_month": pct_of_last,
        "coming_soon": last_month == 0 and actual == 0,
    }


def _asset_performance(tenant_id: str, day_start_iso: str):
    rows = list(asset_clicks_col.aggregate([
        {"$match": {"tenant_id": tenant_id, "created_at": {"$gte": day_start_iso}}},
        {"$group": {"_id": "$asset_name", "clicks": {"$sum": 1}}},
        {"$sort": {"clicks": -1}}, {"$limit": 5},
    ]))
    if not rows:
        return {"coming_soon": True, "rows": []}
    return {"coming_soon": False, "rows": [{"name": r["_id"], "clicks": r["clicks"]} for r in rows]}


def _timeseries_count(collection, base_filter: Dict[str, Any], date_field: str, now: datetime, days: int = 7) -> list[int]:
    """Return a list of daily counts for the last `days` days (oldest → newest).
    Used to feed KPI sparkline charts. Reads cheap via single $bucket aggregate."""
    start = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    boundaries = [(start + timedelta(days=i)).isoformat() for i in range(days + 1)]
    pipeline = [
        {"$match": {**base_filter, date_field: {"$gte": boundaries[0]}}},
        {"$bucket": {
            "groupBy": f"${date_field}",
            "boundaries": boundaries,
            "default": "other",
            "output": {"count": {"$sum": 1}},
        }},
    ]
    rows = {r["_id"]: r["count"] for r in collection.aggregate(pipeline)}
    return [rows.get(boundaries[i], 0) for i in range(days)]


def _timeseries_sum(collection, base_filter: Dict[str, Any], date_field: str, value_field: str, now: datetime, days: int = 7) -> list[float]:
    """Same as _timeseries_count but sums `value_field` per day. Used for $-tracking."""
    start = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    boundaries = [(start + timedelta(days=i)).isoformat() for i in range(days + 1)]
    pipeline = [
        {"$match": {**base_filter, date_field: {"$gte": boundaries[0]}}},
        {"$bucket": {
            "groupBy": f"${date_field}",
            "boundaries": boundaries,
            "default": "other",
            "output": {"total": {"$sum": f"${value_field}"}},
        }},
    ]
    rows = {r["_id"]: r["total"] for r in collection.aggregate(pipeline)}
    return [round(rows.get(boundaries[i], 0) or 0) for i in range(days)]


def _signal_attribution(tenant_id: str, days_present: int) -> Dict[str, Any]:
    """Which signal types actually predict meetings — aggregates pt_insights by
    signal_type and joins booking_events on lead_id. Unlocks once we have
    ≥3 signal-sourced leads in any signal type so demos and early workspaces
    can show real numbers without waiting 90 days."""
    base = {"tenant_id": tenant_id}
    rows = list(pt_insights_col.aggregate([
        {"$match": base},
        {"$lookup": {"from": "booking_events", "localField": "lead_id", "foreignField": "lead_id", "as": "b"}},
        {"$group": {
            "_id": "$signal_type",
            "leads": {"$sum": 1},
            "meetings": {"$sum": {"$cond": [{"$gt": [{"$size": "$b"}, 0]}, 1, 0]}},
        }},
        {"$match": {"leads": {"$gte": 3}}},
    ]))
    if not rows:
        return {"coming_soon": days_present < 90, "rows": []}
    out = []
    for r in rows:
        rate = round((r["meetings"] / r["leads"]) * 100, 1) if r["leads"] else 0
        out.append({"signal_type": r["_id"] or "unknown", "leads": r["leads"],
                    "meetings": r["meetings"], "conv_rate": rate})
    out.sort(key=lambda x: x["conv_rate"], reverse=True)
    return {"coming_soon": False, "rows": out[:6]}


# ───────────────────────── B2B FOUNDER ───────────────────────────
@router.get("/b2b-founder")
async def dashboard_b2b_founder(current_user: dict = Depends(get_current_user)):
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        return {"error": "no_tenant"}
    currency = get_tenant_currency(tenant_id)
    hourly = get_tenant_hourly_rate(tenant_id)
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    last_month_start = (now.replace(day=1) - timedelta(days=1)).replace(day=1).isoformat()
    base = {"tenant_id": tenant_id}

    # KPIs.
    leads_month = pt_leads_col.count_documents({**base, "created_at": {"$gte": month_start}})
    leads_last_month = pt_leads_col.count_documents({**base, "created_at": {"$gte": last_month_start, "$lt": month_start}})
    high_intent = pt_leads_col.count_documents({**base, "created_at": {"$gte": month_start}, "score": {"$gte": 70}})
    high_intent_last = pt_leads_col.count_documents({**base, "created_at": {"$gte": last_month_start, "$lt": month_start}, "score": {"$gte": 70}})
    meetings = booking_events.count_documents({**base, "when": {"$gte": month_start}})
    meetings_last = booking_events.count_documents({**base, "when": {"$gte": last_month_start, "$lt": month_start}})
    signals = pt_insights_col.count_documents({**base, "created_at": {"$gte": month_start}})
    signals_last = pt_insights_col.count_documents({**base, "created_at": {"$gte": last_month_start, "$lt": month_start}})
    conv_rate = round((meetings / leads_month) * 100, 1) if leads_month else 0
    last_conv_rate = round((meetings_last / leads_last_month) * 100, 1) if leads_last_month else 0

    # ICP Drift detection.
    icp_pipeline = list(pt_leads_col.aggregate([
        {"$match": {**base, "created_at": {"$gte": (now - timedelta(days=30)).isoformat()}}},
        {"$group": {"_id": "$icp_segment", "count": {"$sum": 1}}},
    ]))
    total = sum(r["count"] for r in icp_pipeline) or 1
    icp_dist = {r["_id"] or "icp_unknown": r["count"] for r in icp_pipeline}
    unknown_pct = round(((icp_dist.get("icp_unknown", 0) + icp_dist.get("icp_not_fit", 0)) / total) * 100, 1)
    primary_pct = round(((icp_dist.get("icp_a", 0) + icp_dist.get("icp_b", 0)) / total) * 100, 1)
    drift_detected_raw = unknown_pct > 30 or primary_pct < 40
    primary_label = max(icp_dist, key=icp_dist.get) if icp_dist else "icp_a"

    # iter158 Phase B Step 5 — snooze: if tenant has a non-expired
    # icp_drift_snooze_until timestamp, suppress the banner regardless of
    # underlying numbers. Lets founders dismiss the alert for 7 days.
    tenant_doc = db["tenants"].find_one({"id": tenant_id}, {"_id": 0, "icp_drift_snooze_until": 1}) or {}
    snooze_until = tenant_doc.get("icp_drift_snooze_until")
    snoozed = False
    if snooze_until:
        try:
            snoozed = datetime.fromisoformat(snooze_until.replace("Z", "+00:00")) > now
        except Exception:
            snoozed = False
    drift_detected = drift_detected_raw and not snoozed

    # iter158 Phase B Step 5 — drift breakdown by channel (which sources are
    # bringing in unknown-ICP leads). Powers the ICP Drift Modal drill-down.
    by_channel_rows = list(pt_leads_col.aggregate([
        {"$match": {**base, "created_at": {"$gte": (now - timedelta(days=30)).isoformat()}}},
        {"$group": {
            "_id": "$source",
            "total":   {"$sum": 1},
            "unknown": {"$sum": {"$cond": [{"$in": ["$icp_segment", [None, "", "icp_unknown", "icp_not_fit"]]}, 1, 0]}},
        }},
        {"$sort": {"total": -1}},
    ]))
    by_channel = [{
        "channel": r["_id"] or "manual",
        "total":   r["total"],
        "unknown": r["unknown"],
        "unknown_pct": round((r["unknown"] / r["total"]) * 100, 1) if r["total"] else 0,
    } for r in by_channel_rows]


    # Channel performance.
    channel_rows = list(pt_leads_col.aggregate([
        {"$match": {**base, "created_at": {"$gte": month_start}}},
        {"$group": {
            "_id": "$source",
            "leads": {"$sum": 1},
            "high": {"$sum": {"$cond": [{"$gte": ["$score", 70]}, 1, 0]}},
            "medium": {"$sum": {"$cond": [{"$and": [{"$gte": ["$score", 40]}, {"$lt": ["$score", 70]}]}, 1, 0]}},
        }},
        {"$sort": {"leads": -1}},
    ]))
    channel_perf = []
    for r in channel_rows:
        ch = r["_id"] or "manual"
        leads = r["leads"]
        high_pct = round((r["high"] / leads) * 100, 1) if leads else 0
        # bookings per channel
        ch_meetings = booking_events.count_documents({**base, "channel": ch, "when": {"$gte": month_start}})
        conv = round((ch_meetings / leads) * 100, 1) if leads else 0
        if leads == 0:
            health = "inactive"
        elif conv >= 10 and high_pct >= 40:
            health = "working_well"
        elif conv < 5 and high_pct < 20:
            health = "needs_attention"
        else:
            health = "moderate"
        channel_perf.append({
            "channel": ch,
            "colour": CHANNEL_COLOURS.get(ch.lower(), "#94A3B8"),
            "leads": leads, "high": r["high"], "medium": r["medium"], "low": leads - r["high"] - r["medium"],
            "high_pct": high_pct, "meetings": ch_meetings, "conv_rate": conv, "health": health,
        })

    # Why Now Feed.
    yesterday = (now - timedelta(days=1)).isoformat()
    score_changes = latest_score_changes(tenant_id, since_iso=yesterday, min_delta=10, limit=20)
    why_now: list[dict] = []
    seen_lead_ids: set[str] = set()  # dedup: keep only the most recent score-change per lead
    for sh in score_changes:
        if sh["lead_id"] in seen_lead_ids:
            continue
        lead = pt_leads_col.find_one({"id": sh["lead_id"]}, {"_id": 0, "first_name": 1, "last_name": 1, "company_name": 1})
        if not lead:
            continue
        seen_lead_ids.add(sh["lead_id"])
        why_now.append({
            "lead_id": sh["lead_id"],
            "name": f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip(),
            "company": lead.get("company_name"),
            "score_before": sh["prev_score"], "score_after": sh["new_score"],
            "delta": sh["delta"],
            "reason": sh.get("reason") or "Score updated by ARIA",
            "when": sh["created_at"],
        })
        if len(why_now) >= 10:
            break

    # Founder flags (pt_insights with founder_flag true).
    founder_flags = list(pt_insights_col.find(
        {**base, "founder_flag": True, "status": {"$ne": "dismissed"}},
        {"_id": 0, "id": 1, "lead_id": 1, "prospect_name": 1, "prospect_company": 1, "lead_score": 1,
         "signal_summary": 1, "suggested_message": 1, "confidence": 1, "outreach_recommendation": 1},
    ).sort("created_at", -1).limit(8))

    # Buying Committee Radar (top 10 companies × 5 roles).
    roles_map = {
        "ceo_md": ["ceo", "founder", "managing director"],
        "chro_cpo": ["chro", "cpo", "chief people"],
        "cfo": ["cfo"],
        "people_analytics": ["people analytics", "hr analytics"],
        "hr_ops": ["hr operations", "head of hr"],
    }
    company_rows = list(pt_leads_col.aggregate([
        {"$match": base},
        {"$group": {"_id": "$company_name", "total_score": {"$sum": "$score"}, "leads": {"$push": "$job_title"}}},
        {"$sort": {"total_score": -1}}, {"$limit": 10},
    ]))
    radar = []
    for c in company_rows:
        if not c["_id"]:
            continue
        coverage = {}
        for role, kws in roles_map.items():
            coverage[role] = any(
                any(kw in (title or "").lower() for kw in kws)
                for title in c["leads"]
            )
        radar.append({"company": c["_id"], "coverage": coverage, "total_score": c["total_score"]})

    days_of_data = pt_leads_col.aggregate([
        {"$match": base},
        {"$group": {"_id": None, "min": {"$min": "$created_at"}}},
    ])
    days_present = 0
    for row in days_of_data:
        try:
            days_present = (now - datetime.fromisoformat(row["min"])).days
        except Exception:
            pass

    return {
        "header": {
            "workspace_name": (db["tenants"].find_one({"id": tenant_id}, {"_id": 0, "name": 1}) or {}).get("name"),
            "mode": "B2B Founder",
            "currency": currency,
            "last_refresh": _iso(now),
        },
        "kpis": {
            "leads_month": {"value": leads_month, "trend": _trend(leads_month, leads_last_month),
                             "spark": _timeseries_count(pt_leads_col, base, "created_at", now)},
            "high_intent": {"value": high_intent, "trend": _trend(high_intent, high_intent_last),
                             "spark": _timeseries_count(pt_leads_col, {**base, "score": {"$gte": 70}}, "rescored_at", now)},
            "meetings": {"value": meetings, "trend": _trend(meetings, meetings_last),
                          "spark": _timeseries_count(booking_events, base, "when", now)},
            "signals": {"value": signals, "trend": _trend(signals, signals_last),
                         "spark": _timeseries_count(pt_insights_col, base, "created_at", now)},
            "conv_rate": {"value": conv_rate, "unit": "%", "trend": _trend(int(conv_rate * 10), int(last_conv_rate * 10))},
        },
        "aria_time_saved": _aria_time_saved(tenant_id, 30, hourly),
        "momentum": _momentum(tenant_id, {"leads": 0.4, "high_intent": 0.3, "bookings": 0.3}),
        "icp_drift": {
            "drift_detected": drift_detected,
            "unknown_pct": unknown_pct,
            "primary_pct": primary_pct,
            "actual_primary": primary_label,
            "icp_distribution": [{"icp": k, "count": v, "pct": round(v / total * 100, 1)} for k, v in icp_dist.items()],
            "by_channel": by_channel,
            "snoozed_until": snooze_until if snoozed else None,
        },
        "channel_performance": channel_perf,
        "signal_attribution": _signal_attribution(tenant_id, days_present),
        "why_now": why_now,
        "founder_flags": founder_flags,
        "buying_committee": radar,
        "deal_risk_flags": _deal_risk(tenant_id, now),
        "ghost_leads": _ghost_leads(tenant_id, now),
        "monday_brief_preview": _monday_brief_preview(tenant_id, hourly, currency),
    }


def _deal_risk(tenant_id: str, now: datetime):
    fortnight_ago = (now - timedelta(days=14)).isoformat()
    rows = list(pt_leads_col.find(
        {"tenant_id": tenant_id, "score": {"$gte": 60},
         "$or": [{"last_activity_at": {"$lt": fortnight_ago}}, {"reply_sentiment": "NEGATIVE"}]},
        {"_id": 0, "id": 1, "first_name": 1, "last_name": 1, "company_name": 1,
         "last_activity_at": 1, "reply_sentiment": 1, "score": 1},
    ).limit(5))
    out = []
    for r in rows:
        try:
            days = (now - datetime.fromisoformat(r.get("last_activity_at") or now.isoformat())).days
        except Exception:
            days = 99
        risk = "negative_reply" if r.get("reply_sentiment") == "NEGATIVE" else "silent_14_plus"
        out.append({
            "lead_id": r["id"],
            "name": f"{r.get('first_name', '')} {r.get('last_name', '')}".strip(),
            "company": r.get("company_name"), "days_silent": days,
            "risk_type": risk, "score": r["score"],
        })
    return out


def _ghost_leads(tenant_id: str, now: datetime):
    """Warm leads (score >= 40) cold for 14+ days."""
    fortnight_ago = (now - timedelta(days=14)).isoformat()
    rows = list(pt_leads_col.find(
        {"tenant_id": tenant_id, "score": {"$gte": 40},
         "$or": [{"last_activity_at": {"$lt": fortnight_ago}}, {"last_activity_at": None}]},
        {"_id": 0, "id": 1, "first_name": 1, "last_name": 1, "company_name": 1, "score": 1, "last_activity_at": 1},
    ).sort("score", -1).limit(5))
    out = []
    for r in rows:
        try:
            days = (now - datetime.fromisoformat(r.get("last_activity_at") or now.isoformat())).days
        except Exception:
            days = 99
        out.append({
            "lead_id": r["id"],
            "name": f"{r.get('first_name', '')} {r.get('last_name', '')}".strip(),
            "company": r.get("company_name"), "days_silent": days, "score": r["score"],
            "trigger": "Recent activity detected",
        })
    return out


def _monday_brief_preview(tenant_id: str, hourly: int, currency: str):
    now = datetime.now(timezone.utc)
    week_start = (now - timedelta(days=now.isoweekday() - 1)).isoformat()
    base = {"tenant_id": tenant_id}
    # Best channel by leads.
    ch_rows = list(pt_leads_col.aggregate([
        {"$match": {**base, "created_at": {"$gte": week_start}}},
        {"$group": {"_id": "$source", "n": {"$sum": 1}}},
        {"$sort": {"n": -1}}, {"$limit": 1},
    ]))
    best_channel = ch_rows[0]["_id"] if ch_rows else "—"
    top_signals = list(pt_insights_col.aggregate([
        {"$match": {**base, "created_at": {"$gte": week_start}}},
        {"$group": {"_id": "$signal_type", "n": {"$sum": 1}}},
        {"$sort": {"n": -1}}, {"$limit": 3},
    ]))
    saved = _aria_time_saved(tenant_id, 7, hourly)
    return {
        "lines": [
            "Momentum: see dashboard",
            f"Top signals this week: {', '.join(s['_id'] for s in top_signals) or '—'}",
            f"ARIA time saved: {saved['hours']}h (~{currency} {saved['money_equivalent']})",
            f"Best performing channel: {best_channel}",
            "One thing to fix: see Channel Performance table",
        ],
    }


# ───────────────────────── B2B SALES ─────────────────────────────
@router.get("/b2b-sales")
async def dashboard_b2b_sales(current_user: dict = Depends(get_current_user)):
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        return {"error": "no_tenant"}
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    last_month_start = (now.replace(day=1) - timedelta(days=1)).replace(day=1).isoformat()
    base = {"tenant_id": tenant_id}
    hourly = get_tenant_hourly_rate(tenant_id)

    # KPIs.
    followups_today = pt_leads_col.count_documents({**base, "next_followup_at": {"$gte": day_start, "$lt": (now + timedelta(days=1)).isoformat()}})
    meetings_today = booking_events.count_documents({**base, "when": {"$gte": day_start, "$lt": (now + timedelta(days=1)).isoformat()}})
    approvals = pt_insights_col.count_documents({**base, "status": "pending"})
    pipeline_value = sum((lead.get("deal_value") or 0) for lead in pt_leads_col.find({**base, "score": {"$gte": 40}}, {"_id": 0, "deal_value": 1}))
    pipeline_value_last = sum((lead.get("deal_value") or 0) for lead in pt_leads_col.find({**base, "score": {"$gte": 40}, "created_at": {"$lt": month_start}}, {"_id": 0, "deal_value": 1}))

    # Top 3 hot leads.
    hot_leads = list(pt_leads_col.find(
        {**base, "score": {"$gte": 60}},
        {"_id": 0, "id": 1, "first_name": 1, "last_name": 1, "company_name": 1, "job_title": 1,
         "score": 1, "icp_segment_name": 1, "lemlist_intent": 1, "source": 1, "lemlist_data": 1},
    ).sort("score", -1).limit(3))
    hot_lead_cards = []
    for lead in hot_leads:
        sig = pt_insights_col.find_one({**base, "lead_id": lead["id"]}, {"_id": 0, "signal_type": 1}, sort=[("created_at", -1)])
        ldata = lead.get("lemlist_data") or {}
        hot_lead_cards.append({
            "id": lead["id"],
            "name": f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip(),
            "company": lead.get("company_name"), "title": lead.get("job_title"),
            "score": lead.get("score"),
            "signal_type": (sig or {}).get("signal_type"),
            "intent": lead.get("lemlist_intent"), "icp": lead.get("icp_segment_name"),
            "source": lead.get("source"),
            "lemlist_summary": f"Opened {ldata.get('opens', 0)}× · Replied {ldata.get('replies', 0)} · Clicked {ldata.get('clicks', 0)}",
        })

    # Pipeline table (top 50).
    pipeline_rows = list(iter_tenant_leads(tenant_id, limit=50))
    for row in pipeline_rows:
        try:
            row["pipeline_stage"] = _classify_pipeline_stage(row, booking_events, now)
        except Exception:
            row["pipeline_stage"] = "Cold"

    # Today's agenda — meetings + followups today.
    agenda_meetings = list(booking_events.find(
        {**base, "when": {"$gte": day_start, "$lt": (now + timedelta(days=1)).isoformat()}},
        {"_id": 0, "lead_id": 1, "when": 1, "channel": 1},
    ).sort("when", 1))
    for meeting in agenda_meetings:
        lead = pt_leads_col.find_one({**base, "id": meeting["lead_id"]}, {"_id": 0, "first_name": 1, "last_name": 1, "company_name": 1})
        if lead:
            meeting["lead_name"] = f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip()
            meeting["company"] = lead.get("company_name")

    # Approval queue (top 3).
    approval_queue = list(pt_insights_col.find(
        {**base, "status": "pending"},
        {"_id": 0, "id": 1, "lead_id": 1, "prospect_name": 1, "suggested_message": 1, "signal_summary": 1},
    ).sort("created_at", -1).limit(3))

    # Why Now Feed.
    yesterday = (now - timedelta(days=1)).isoformat()
    score_changes = latest_score_changes(tenant_id, since_iso=yesterday, min_delta=10, limit=10)
    why_now: list[dict] = []
    seen_lead_ids: set[str] = set()
    for sh in score_changes:
        if sh["lead_id"] in seen_lead_ids:
            continue
        lead = pt_leads_col.find_one({"id": sh["lead_id"]}, {"_id": 0, "first_name": 1, "last_name": 1, "company_name": 1})
        if not lead:
            continue
        seen_lead_ids.add(sh["lead_id"])
        why_now.append({
            "lead_id": sh["lead_id"],
            "name": f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip(),
            "company": lead.get("company_name"),
            "score_before": sh["prev_score"], "score_after": sh["new_score"], "delta": sh["delta"],
            "reason": sh.get("reason") or "Score updated", "when": sh["created_at"],
        })
        if len(why_now) >= 10:
            break

    # Signal-to-revenue attribution (compact — top 3).
    attr_rows = list(pt_insights_col.aggregate([
        {"$match": base},
        {"$lookup": {"from": "booking_events", "localField": "lead_id", "foreignField": "lead_id", "as": "b"}},
        {"$group": {
            "_id": "$signal_type",
            "leads": {"$sum": 1},
            "meetings": {"$sum": {"$cond": [{"$gt": [{"$size": "$b"}, 0]}, 1, 0]}},
        }},
        {"$match": {"leads": {"$gte": 3}}},
    ]))
    attribution_top3 = []
    for row in attr_rows:
        rate = round((row["meetings"] / row["leads"]) * 100, 1) if row["leads"] else 0
        attribution_top3.append({"signal_type": row["_id"], "conv_rate": rate, "leads": row["leads"]})
    attribution_top3.sort(key=lambda x: x["conv_rate"], reverse=True)
    attribution_top3 = attribution_top3[:3]

    return {
        "header": {
            "first_name": (current_user.get("full_name") or "").split(" ")[0] or current_user.get("email", "").split("@")[0],
            "mode": "Sales View",
            "last_refresh": _iso(now),
        },
        "top_actions": await _sales_coach_top3(tenant_id, current_user.get("email") or "anon", hot_lead_cards, _deal_risk(tenant_id, now), approval_queue, agenda_meetings, score_changes),
        "kpis": {
            "followups_today":   {"value": followups_today,  "spark": _timeseries_count(pt_leads_col,     base, "next_followup_at", now)},
            "meetings_today":    {"value": meetings_today,   "spark": _timeseries_count(booking_events,    base, "when",             now)},
            "approvals_pending": {"value": approvals,        "spark": _timeseries_count(pt_insights_col,   {**base, "status": "pending"}, "created_at", now)},
            "pipeline_value":    {"value": round(pipeline_value), "trend": _trend(int(pipeline_value), int(pipeline_value_last)),
                                  "spark": _timeseries_sum(booking_events, base, "when", "deal_value", now)},
        },
        "hot_leads": hot_lead_cards,
        "pipeline": pipeline_rows,
        "agenda": agenda_meetings,
        "approval_queue": approval_queue,
        "aria_time_saved": _aria_time_saved(tenant_id, 7, hourly),
        "deal_risk_flags": _deal_risk(tenant_id, now),
        "ghost_leads": _ghost_leads(tenant_id, now),
        "attribution_top3": attribution_top3 or {"coming_soon": True, "rows": []} if not attribution_top3 else attribution_top3,
        "why_now": why_now,
    }


def _classify_pipeline_stage(lead: Dict[str, Any], bookings_col, now: datetime) -> str:
    """Per spec: Hot ≥70 · Meeting Set if booking in calendar · Replied/Warm/Nurture/Cold/At Risk."""
    lid = lead.get("id")
    if lid and bookings_col.count_documents({"lead_id": lid, "when": {"$gte": now.isoformat()}}, limit=1):
        return "Meeting Set"
    score = lead.get("score") or lead.get("icp_score") or 0
    if score >= 70:
        return "Hot"
    if score >= 40:
        return "Warm"
    return "Cold"


# ───────────────────────── SALES_COACH (Top 3 Actions) ───────────
# iter150-B — Claude Haiku generates 3 specific actions for today,
# cached per (tenant_id, user_email, date). Regenerate via the
# /top-actions/regenerate endpoint.
_sales_coach_cache = db["sales_coach_cache"]
try:
    _sales_coach_cache.create_index([("tenant_id", 1), ("user_email", 1), ("date", 1)], unique=True)
except Exception:
    pass


async def _sales_coach_top3(tenant_id: str, user_email: str, hot_leads, deal_risks, approvals, agenda, why_now):
    """Returns {rows: [...]} from Claude. Cache hit: returns the same rows for the rest of today."""
    if not hot_leads and not deal_risks and not approvals:
        return {"coming_soon": True, "reason": "Need ≥1 hot lead OR deal risk OR pending approval to generate actions.", "rows": []}

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cached = _sales_coach_cache.find_one(
        {"tenant_id": tenant_id, "user_email": user_email, "date": today},
        {"_id": 0, "rows": 1, "generated_at": 1},
    )
    if cached:
        return {"rows": cached["rows"], "generated_at": cached["generated_at"], "cache": "hit"}

    # Build a compact context summary for Claude.
    summary_lines = []
    for lead in (hot_leads or [])[:5]:
        summary_lines.append(f"HOT · {lead.get('name')} · {lead.get('company')} · score {lead.get('score')} · signal {lead.get('signal_type') or 'n/a'}")
    for d in (deal_risks or [])[:5]:
        summary_lines.append(f"AT-RISK · {d.get('name')} · {d.get('company')} · {d.get('risk_type')} · {d.get('days_silent')}d silent")
    for a in (approvals or [])[:3]:
        summary_lines.append(f"APPROVAL · {a.get('prospect_name')} · {(a.get('suggested_message') or '')[:80]}")
    for m in (agenda or [])[:3]:
        summary_lines.append(f"MEETING TODAY · {m.get('lead_name')} · {m.get('company')} · {m.get('when')}")
    for w in (why_now or [])[:3]:
        summary_lines.append(f"WHY-NOW · score moved {w.get('prev_score')}→{w.get('new_score')}")
    pipeline_text = "\n".join(summary_lines) or "Empty pipeline."

    prompt = f"""You are a B2B sales coach. Based on this pipeline snapshot, give EXACTLY 3 specific actions for today, ordered by revenue impact.

Each action must be ONE concrete next step tied to a NAMED lead/deal in the data below. Do not invent leads or companies — only reference names actually present in the snapshot.

Output STRICT JSON array of 3 objects, no prose:
[
  {{"action": "Send the signed proposal v3 to ...", "lead": "Lead Name", "company": "Company Name", "why_now": "One short sentence."}}
]

Pipeline snapshot:
{pipeline_text}
"""
    try:
        from services.claude_service import claude_call, TaskType
        rows = await claude_call(
            task_type=TaskType.SALES_COACH,
            tenant_id=tenant_id,
            session_id=f"sales-coach-{user_email}-{today}",
            prompt=prompt,
            system="You are a precise B2B sales coach. Output strict JSON only.",
            response_format="json",
        )
        if isinstance(rows, dict):
            rows = rows.get("actions") or rows.get("rows") or [rows]
        if not isinstance(rows, list):
            rows = []
        rows = rows[:3]
    except Exception as e:  # noqa: BLE001
        import logging
        logging.getLogger("dashboards").warning("sales_coach claude_call failed: %s", e, exc_info=True)
        return {"coming_soon": True, "reason": f"Claude call failed: {e}", "rows": []}

    _sales_coach_cache.update_one(
        {"tenant_id": tenant_id, "user_email": user_email, "date": today},
        {"$set": {"rows": rows, "generated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return {"rows": rows, "cache": "miss"}


@router.post("/top-actions/regenerate")
async def regenerate_top_actions(current_user: dict = Depends(get_current_user)):
    """Bust the daily cache so the next /b2b-sales call fetches fresh rows."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    _sales_coach_cache.delete_one({
        "tenant_id": current_user.get("tenant_id"),
        "user_email": current_user.get("email"),
        "date": today,
    })
    return {"ok": True, "cache_cleared": True}


# ───────────────────────── Misc helpers ──────────────────────────
@router.post("/icp-drift/snooze")
async def snooze_icp_drift(days: int = 7, current_user: dict = Depends(get_current_user)):
    """iter158 Phase B Step 5 — snooze the ICP drift banner for N days
    (default 7). Stored on the tenant doc so all team members see the same
    snoozed state."""
    tenant_id = current_user.get("tenant_id") or ""
    if not tenant_id:
        return {"ok": False, "error": "no tenant"}
    days = max(1, min(int(days or 7), 30))
    until = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    db["tenants"].update_one(
        {"id": tenant_id},
        {"$set": {"icp_drift_snooze_until": until, "icp_drift_snoozed_by": current_user.get("email")}},
    )
    return {"ok": True, "snoozed_until": until, "days": days}


@router.get("/_mode")
async def dashboard_mode(current_user: dict = Depends(get_current_user)):
    """Tells the frontend which dashboard to load based on tenant.mode."""
    tenant_id = current_user.get("tenant_id") or ""
    return {
        "tenant_id": tenant_id,
        "mode": get_tenant_mode(tenant_id),
        "currency": get_tenant_currency(tenant_id),
        "hourly_rate": get_tenant_hourly_rate(tenant_id),
    }
