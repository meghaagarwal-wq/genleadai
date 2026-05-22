"""Submodule of aria_agent_routes — registers routes on the shared router.
Auto-split from aria_agent_routes.py (iter75).
"""
from ._shared import (
    router, training_collection, playbooks_collection, leads_collection,
    activities_collection, db, get_current_user, AriaTrainingPayload,
)
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from emergentintegrations.llm.chat import LlmChat, UserMessage
import os
import json


# 11. Weekly Recap
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/weekly-recap")
async def weekly_recap(current_user: dict = Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    week_start = now - timedelta(days=7)
    prev_start = now - timedelta(days=14)
    ws_iso = week_start.isoformat()
    ps_iso = prev_start.isoformat()

    def _between(col, field, start, end):
        return col.count_documents({field: {"$gte": start, "$lt": end}})

    # This week
    now_iso = now.isoformat()
    new_leads = _between(leads_collection, "created_at", ws_iso, now_iso)
    qualified = leads_collection.count_documents({"status": "qualified", "updated_at": {"$gte": ws_iso}})
    replies_sent = activities_collection.count_documents({"activity_type": {"$in": ["email_sent", "whatsapp_sent"]}, "created_at": {"$gte": ws_iso}})
    calls_booked = activities_collection.count_documents({"activity_type": "meeting_scheduled", "created_at": {"$gte": ws_iso}})
    deals_won = leads_collection.count_documents({"status": "won", "updated_at": {"$gte": ws_iso}})
    deals_lost = leads_collection.count_documents({"status": "lost", "updated_at": {"$gte": ws_iso}})

    # Previous week
    prev_new = leads_collection.count_documents({"created_at": {"$gte": ps_iso, "$lt": ws_iso}})
    prev_qualified = leads_collection.count_documents({"status": "qualified", "updated_at": {"$gte": ps_iso, "$lt": ws_iso}})
    prev_replies = activities_collection.count_documents({"activity_type": {"$in": ["email_sent", "whatsapp_sent"]}, "created_at": {"$gte": ps_iso, "$lt": ws_iso}})
    prev_booked = activities_collection.count_documents({"activity_type": "meeting_scheduled", "created_at": {"$gte": ps_iso, "$lt": ws_iso}})
    prev_won = leads_collection.count_documents({"status": "won", "updated_at": {"$gte": ps_iso, "$lt": ws_iso}})

    def _delta(cur, prev):
        if prev == 0 and cur == 0: return 0
        if prev == 0: return 100
        return round((cur - prev) / prev * 100)

    # Biggest win / miss
    win_cursor = list(leads_collection.find({"status": "won", "updated_at": {"$gte": ws_iso}}, {
        "_id": 0, "first_name": 1, "last_name": 1, "company_name": 1, "icp_score": 1, "deal_value": 1,
    }).sort([("deal_value", -1), ("icp_score", -1)]).limit(1))
    biggest_win = win_cursor[0] if win_cursor else None

    miss_cursor = list(leads_collection.find({
        "icp_score": {"$gte": 75},
        "status": {"$in": ["contacted", "qualified", "proposal_sent"]},
        "last_contacted_at": {"$lt": ws_iso},
    }, {"_id": 0, "first_name": 1, "last_name": 1, "company_name": 1, "icp_score": 1, "last_contacted_at": 1})
        .sort("icp_score", -1).limit(1))
    biggest_miss = miss_cursor[0] if miss_cursor else None

    # Top signal of the week
    src_week = {}
    for l in leads_collection.find({"created_at": {"$gte": ws_iso}}, {"_id": 0, "source_channel": 1}):
        s = (l.get("source_channel") or "other").replace("_", " ").title()
        src_week[s] = src_week.get(s, 0) + 1
    top_channel = max(src_week, key=src_week.get) if src_week else "—"

    # Build narrative
    if new_leads == 0 and replies_sent == 0 and calls_booked == 0 and deals_won == 0:
        narrative = (
            "This week was quiet on the wire — no new leads, replies, or bookings logged yet. "
            "That's a refill signal, not a red flag. Use tomorrow to run a revival sweep on silent leads "
            "and trigger fresh capture — ARIA will handle the conversations as they come in."
        )
    else:
        parts = []
        parts.append(f"ARIA handled {replies_sent} conversations this week")
        if calls_booked > 0:
            parts.append(f"booked {calls_booked} call{'s' if calls_booked != 1 else ''}")
        if qualified > 0:
            parts.append(f"qualified {qualified} lead{'s' if qualified != 1 else ''}")
        if deals_won > 0:
            parts.append(f"closed {deals_won} deal{'s' if deals_won != 1 else ''}")
        narrative = ", ".join(parts) + "."
        if top_channel and top_channel != "—":
            narrative += f" Your strongest source was {top_channel}."
        if biggest_miss:
            narrative += f" Watch out — {biggest_miss.get('first_name','a high-ICP lead')} ({biggest_miss.get('company_name','—')}) has gone silent."

    # Next week focus — heuristic 3 bullets
    focus = []
    if biggest_miss:
        miss_name = biggest_miss.get('first_name') or f"your silent ICP-{biggest_miss.get('icp_score', 80)}+"
        focus.append(f"Revive {miss_name} lead at {biggest_miss.get('company_name','—')} with a founder voice note.")
    if _delta(replies_sent, prev_replies) < 0:
        focus.append("Reply volume dropped vs last week — audit your automations and triggers.")
    if _delta(calls_booked, prev_booked) < 0 and calls_booked < 3:
        focus.append("Calls booked are trending down — tighten the booking CTA on warm replies.")
    while len(focus) < 3:
        fallback = [
            "Push one proposal to decision with a specific deadline message.",
            "Add one more case study to the nurture journey — ARIA will weave it into objections.",
            "Ship one founder voice note this week to your top 3 hot leads.",
            "Clean qualifier answers in Train ARIA so ARIA escalates to you faster.",
        ]
        for f in fallback:
            if f not in focus:
                focus.append(f)
                break
        if len(focus) >= 3:
            break

    return {
        "week_start": ws_iso,
        "week_end": now.isoformat(),
        "headline": f"Week of {week_start.strftime('%b %d')} → {now.strftime('%b %d')}",
        "narrative": narrative,
        "stats": [
            {"label": "New leads", "value": new_leads, "delta": _delta(new_leads, prev_new), "prev": prev_new},
            {"label": "Qualified", "value": qualified, "delta": _delta(qualified, prev_qualified), "prev": prev_qualified},
            {"label": "Replies sent", "value": replies_sent, "delta": _delta(replies_sent, prev_replies), "prev": prev_replies},
            {"label": "Calls booked", "value": calls_booked, "delta": _delta(calls_booked, prev_booked), "prev": prev_booked},
            {"label": "Deals won", "value": deals_won, "delta": _delta(deals_won, prev_won), "prev": prev_won},
            {"label": "Deals lost", "value": deals_lost, "delta": 0, "prev": 0},
        ],
        "top_channel": top_channel,
        "biggest_win": biggest_win,
        "biggest_miss": biggest_miss,
        "next_week_focus": focus[:3],
    }



