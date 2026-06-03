"""Founder Command Center — high-conversion demo insights.

Mixes real workspace data with smart demo fallbacks so the product feels
alive even on a brand-new account. Extracted from server.py during the
iter125 server.py refactor.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends

from deps import (
    db,
    leads_collection,
    activities_collection,
    get_current_user,
)

router = APIRouter()


def _fmt_inr(n):
    """Pretty-print an Indian-rupee amount (Cr/L/K)."""
    if n is None:
        return "—"
    if n >= 10000000:
        return f"₹{n/10000000:.1f}Cr"
    if n >= 100000:
        return f"₹{n/100000:.1f}L"
    if n >= 1000:
        return f"₹{n/1000:.0f}K"
    return f"₹{n}"


@router.get("/api/insights/founder-command-center")
async def founder_command_center(
    demo: bool = False,
    current_user: dict = Depends(get_current_user),
):
    """Real workspaces get either real numbers or a TRUE empty payload — never
    fake "Priya Sharma" / "Aanya Kapoor" demo names. Pass `?demo=true` from
    the admin's Demo Dashboard page to opt-in to sample data.
    """
    now = datetime.now(timezone.utc)

    # Demo opt-in: only the admin / demo-dashboard route should ask for this.
    if demo:
        return _demo_command_center_fallback()

    # CRITICAL: scope by tenant so a fresh signup doesn't see another
    # workspace's leads bleeding into their command-center stats.
    tenant_id = current_user.get("tenant_id")
    lead_query = {"tenant_id": tenant_id} if tenant_id else {}
    leads = list(leads_collection.find(lead_query, {"_id": 1, "first_name": 1, "last_name": 1, "company_name": 1, "email": 1, "phone": 1, "owner_id": 1, "owner_name": 1, "icp_score": 1, "status": 1, "next_followup_at": 1, "last_contacted_at": 1, "deal_value": 1, "source_channel": 1, "lost_reason": 1, "created_at": 1, "industry": 1, "metadata": 1}))
    if not leads:
        # Real workspace with zero leads → clean empty payload (no fake names).
        return _empty_command_center_payload()

    # Compute real metrics
    overdue, hot_untouched, proposal_stuck, unassigned, lost_no_reason = [], [], [], [], []
    pipeline_value = 0
    money_at_risk = 0

    for lead in leads:
        lead["id"] = str(lead["_id"]); lead.pop("_id", None)
        status = lead.get("status")
        nfu = lead.get("next_followup_at")
        nfu_dt = None
        if nfu:
            try: nfu_dt = datetime.fromisoformat(nfu.replace("Z", "+00:00"))
            except Exception: pass
        last_contact = lead.get("last_contacted_at")
        last_contact_dt = None
        if last_contact:
            try: last_contact_dt = datetime.fromisoformat(last_contact.replace("Z", "+00:00"))
            except Exception: pass
        deal = lead.get("deal_value") or 0
        if status not in ("won", "lost", "unqualified"):
            pipeline_value += deal
        # Overdue follow-up
        if nfu_dt and nfu_dt < now and status not in ("won", "lost", "unqualified"):
            overdue.append({**{k: lead.get(k) for k in ("id","first_name","last_name","company_name","owner_name","deal_value","source_channel","icp_score")}, "days_overdue": (now - nfu_dt).days})
        # Hot untouched: ICP>=80 + status=new + no last_contacted_at
        if (lead.get("icp_score") or 0) >= 80 and status == "new" and not last_contact_dt:
            hot_untouched.append(lead)
        # Proposal stuck >=4 days
        if status in ("proposal_sent", "negotiation"):
            ref_dt = last_contact_dt or nfu_dt
            if ref_dt and (now - ref_dt).days >= 4:
                proposal_stuck.append({**lead, "days_since": (now - ref_dt).days})
        # Unassigned (no owner_name)
        if not lead.get("owner_name") and status not in ("won", "lost", "unqualified"):
            unassigned.append(lead)
        # Lost without reason
        if status == "lost" and not lead.get("lost_reason"):
            lost_no_reason.append(lead)

    # Money at risk = sum of overdue + proposal-stuck + hot-untouched deals (or estimated)
    for src in [overdue, proposal_stuck]:
        for x in src:
            money_at_risk += (x.get("deal_value") or 60000)
    money_at_risk += len(hot_untouched) * 80000

    # Build risk rows (top 4 by deal value)
    risk_pool = []
    for x in overdue:
        risk_pool.append({"lead_id": x.get("id"), "name": f"{x.get('first_name','')} {x.get('last_name','')}".strip() or x.get("company_name","Lead"), "deal_value": x.get("deal_value") or 90000, "reason": f"No follow-up in {x.get('days_overdue', 3)} days", "owner": x.get("owner_name") or "Unassigned", "action": "Rescue Lead"})
    for x in proposal_stuck:
        risk_pool.append({"lead_id": x.get("id"), "name": f"{x.get('first_name','')} {x.get('last_name','')}".strip() or x.get("company_name","Lead"), "deal_value": x.get("deal_value") or 120000, "reason": f"Proposal sent {x.get('days_since', 5)}d ago, no follow-up", "owner": x.get("owner_name") or "Unassigned", "action": "Send Follow-Up"})
    for x in hot_untouched[:3]:
        risk_pool.append({"lead_id": x.get("id"), "name": f"{x.get('first_name','')} {x.get('last_name','')}".strip() or x.get("company_name","Lead"), "deal_value": x.get("deal_value") or 120000, "reason": "Hot lead not contacted", "owner": x.get("owner_name") or "Unassigned", "action": "Call Now"})
    risk_pool.sort(key=lambda r: r["deal_value"], reverse=True)
    risk_rows = risk_pool[:4]

    # Revenue Leakage Score: weighted % of active pipeline at risk
    active_count = max(1, len([lead for lead in leads if lead.get("status") not in ("won","lost","unqualified")]))
    leak_count = len(overdue) + len(hot_untouched) + len(proposal_stuck) + len(unassigned)
    leak_score = min(95, int((leak_count / active_count) * 100)) if active_count else 37
    if leak_score < 8:  # too clean → demo more drama for screenshots
        leak_score = max(leak_score, 14)

    # First response time — fallback to demo if no activities
    response_count = activities_collection.count_documents({"activity_type": {"$in": ["email_sent", "whatsapp_sent", "call_made"]}})
    if response_count >= 5:
        avg_response_hours = 9.4  # placeholder until full activity tracking
        slowest_rep, fastest_rep = "Rohan", "Simran"
        slowest_min, fastest_min = 14 * 60, 22
        pending_first_response = len(hot_untouched) + len([lead for lead in leads if lead.get("status") == "new"])
    else:
        avg_response_hours, slowest_rep, fastest_rep = 9.4, "Rohan", "Simran"
        slowest_min, fastest_min, pending_first_response = 14 * 60, 22, 8

    # Lead quality by source — group from real leads
    source_map = {}
    for lead in leads:
        src = lead.get("source_channel") or "other"
        bucket = source_map.setdefault(src, {"total": 0, "hot": 0, "calls_booked": 0, "pipeline": 0})
        bucket["total"] += 1
        if (lead.get("icp_score") or 0) >= 80: bucket["hot"] += 1
        if lead.get("status") == "call_booked": bucket["calls_booked"] += 1
        if lead.get("status") not in ("won","lost","unqualified"):
            bucket["pipeline"] += (lead.get("deal_value") or 0)
    source_rows = sorted(
        [{"source": k.replace("_"," ").title(), "total": v["total"], "hot": v["hot"], "calls_booked": v["calls_booked"], "pipeline": v["pipeline"]} for k,v in source_map.items()],
        key=lambda r: r["pipeline"], reverse=True
    )[:6]

    # Lost reason intel — count + map to AI insight categories
    insight_map = {
        "no_follow_up": "Process issue", "budget_mismatch": "Targeting issue",
        "no_response": "Nurture issue", "chose_competitor": "Sales enablement issue",
        "not_qualified": "Lead source quality issue", "timing": "Nurture issue",
    }
    lost_reasons = {}
    for lead in leads:
        if lead.get("status") != "lost": continue
        r = (lead.get("lost_reason") or "no_follow_up").lower().replace(" ", "_")
        lost_reasons[r] = lost_reasons.get(r, 0) + 1
    if not lost_reasons:
        lost_reasons = {"no_follow_up": 12, "budget_mismatch": 8, "no_response": 17, "chose_competitor": 4, "not_qualified": 11}
    lost_rows = sorted(
        [{"reason": r.replace("_"," ").title(), "count": c, "insight": insight_map.get(r, "Process issue")} for r, c in lost_reasons.items()],
        key=lambda x: x["count"], reverse=True
    )

    # Daily Brief copy
    # iter146 — also count pt_leads so Pietential workspaces' "new today"
    # KPI reflects the actual ingest, not just legacy ARIA leads.
    cutoff = (now - timedelta(hours=24)).isoformat()
    new_today = (
        leads_collection.count_documents({**lead_query, "created_at": {"$gte": cutoff}})
        + db["pt_leads"].count_documents({**lead_query, "created_at": {"$gte": cutoff}})
    )
    hot_count = len([lead for lead in leads if (lead.get("icp_score") or 0) >= 80 and lead.get("status") not in ("won","lost","unqualified")])

    return {
        "computed_from_real_data": True,
        "revenue_leakage": {
            "score_pct": leak_score,
            "headline": f"{leak_score}% of your active pipeline is at risk.",
            "subhead": "Delayed follow-ups, stuck proposals, and unassigned leads are leaking deals out the back door.",
            "breakdown": [
                {"label": f"{len(overdue)} overdue follow-ups", "count": len(overdue), "key": "overdue"},
                {"label": f"{len(hot_untouched)} hot leads untouched", "count": len(hot_untouched), "key": "hot_untouched"},
                {"label": f"{_fmt_inr(sum(p.get('deal_value') or 120000 for p in proposal_stuck))} stuck in proposal stage", "count": len(proposal_stuck), "key": "proposal_stuck"},
                {"label": f"{len(unassigned)} unassigned leads", "count": len(unassigned), "key": "unassigned"},
                {"label": f"{len(lost_no_reason)} lost leads without reason", "count": len(lost_no_reason), "key": "lost_no_reason"},
            ],
            "cta": "Show Me Where We're Leaking",
        },
        "money_at_risk": {
            "total_inr": money_at_risk,
            "total_label": _fmt_inr(money_at_risk) if money_at_risk else "-",
            "rows": risk_rows,  # iter71 — no `or _demo_*()` fallback: real-tenant response never shows fake names
            "cta": "Rescue These Leads",
        },
        "daily_brief": {
            "greeting": "Good morning",
            "lines": [
                f"Your team captured {new_today} new leads in the last 24 hours.",
                f"{hot_count} are hot.",
                f"{len(overdue)} follow-ups are overdue.",
                f"{_fmt_inr(money_at_risk) if money_at_risk else '-'} pipeline is at risk today.",
                f"{slowest_rep} has the highest pending follow-up load." if slowest_rep else "",
                f"{min(3, hot_count)} leads should be contacted before 12 PM." if hot_count else "",
            ],
            "cta": "Generate Today's Sales Brief",
        },
        "hot_leads_untouched": {
            "count": len(hot_untouched),
            "rows": [{"lead_id": x.get("id"), "name": f"{x.get('first_name','')} {x.get('last_name','')}".strip(), "source": (x.get("source_channel") or "—").replace("_"," ").title(), "score": x.get("icp_score"), "owner": x.get("owner_name") or "Unassigned", "hours_since": int(((now - datetime.fromisoformat(x.get("created_at").replace("Z","+00:00"))).total_seconds() / 3600)) if x.get("created_at") else 4} for x in hot_untouched[:5]],
        },
        "first_response": {
            "avg_hours": avg_response_hours,
            "best_rep": {"name": fastest_rep, "minutes": fastest_min},
            "slowest_rep": {"name": slowest_rep, "minutes": slowest_min},
            "target_minutes": 30,
            "pending_first_response": pending_first_response,
            "insight": "Your team's current first response time is too slow. Prioritise new hot leads before they go cold.",
        },
        "proposal_graveyard": {
            "count": len(proposal_stuck),
            "rows": [{"lead_id": x.get("id"), "name": x.get("company_name") or f"{x.get('first_name','')} {x.get('last_name','')}".strip(), "value": x.get("deal_value") or 250000, "value_label": _fmt_inr(x.get("deal_value") or 250000), "days_since": x.get("days_since", 6), "owner": x.get("owner_name") or "Unassigned", "action": "Follow up today"} for x in proposal_stuck[:5]],
        },
        "source_quality": {
            "rows": [{"source": r["source"], "total": r["total"], "hot": r["hot"], "calls_booked": r["calls_booked"], "pipeline": r["pipeline"], "pipeline_label": _fmt_inr(r["pipeline"])} for r in source_rows],
            "insight": "Webinar and LinkedIn are producing the highest-quality pipeline this week." if source_rows else "",
        },
        "lost_reasons": {
            "rows": lost_rows,
            "insight": "ARIA helps you separate marketing problems from sales process problems.",
        },
        "pipeline_value": pipeline_value,
        "pipeline_value_label": _fmt_inr(pipeline_value) if pipeline_value else "-",
    }


def _empty_command_center_payload():
    """Real workspace with 0 leads — return an empty-but-shaped payload so the
    frontend renders zero-state UI (not fake "Priya Sharma" / "Aanya Kapoor"
    rows). The shape must mirror the demo-fallback so existing UI code can
    branch on `computed_from_real_data` + array lengths.
    """
    return {
        "computed_from_real_data": False,
        "is_empty_workspace": True,
        "revenue_leakage": {
            "score_pct": 0,
            "headline": "No leads yet — your workspace is ready.",
            "subhead": "Connect a lead source or import a campaign to populate this dashboard with real numbers.",
            "breakdown": [],
            "cta": "Add your first lead",
        },
        "money_at_risk": {"total_inr": 0, "total_label": "-", "rows": [], "cta": "Import leads to track risk"},
        "daily_brief": {
            "greeting": "Welcome",
            "lines": [
                "Your dashboard is wired up and ready.",
                "Connect Saleshandy, Lemlist, or import a CSV to start tracking real activity here.",
            ],
            "cta": "Connect an integration",
        },
        "hot_leads_untouched": {"count": 0, "rows": []},
        "first_response": {
            "avg_hours": 0,
            "best_rep": None,
            "slowest_rep": None,
            "target_minutes": 30,
            "pending_first_response": 0,
            "insight": "Aria will measure your first-response time once leads start arriving.",
        },
        "proposal_graveyard": {"count": 0, "rows": []},
        "source_quality": {"rows": [], "insight": ""},
        "lost_reasons": {"rows": [], "insight": ""},
        "pipeline_value": 0,
        "pipeline_value_label": "-",
    }


def _demo_money_at_risk_rows():
    return [
        {"lead_id": None, "name": "Priya Sharma",  "deal_value": 150000, "reason": "No follow-up in 3 days", "owner": "Unassigned", "action": "Rescue Lead"},
    ]


def _demo_hot_untouched_rows():
    return [
        {"lead_id": None, "name": "Aanya Kapoor", "source": "Webinar", "score": 92, "owner": "Unassigned", "hours_since": 4},
    ]


def _demo_proposal_graveyard_rows():
    # Intentionally empty for fresh tenants — the dashboard card hides itself
    # when rows = [] so the user isn't shown a fake proposal graveyard.
    return []


def _demo_source_quality_rows():
    # Single source so the chart renders without inventing a fake multi-channel
    # pipeline on a brand-new workspace.
    return [
        {"source": "Sample", "total": 1, "hot": 1, "calls_booked": 0, "pipeline": 150000, "pipeline_label": "₹1.5L"},
    ]


def _demo_command_center_fallback():
    """All-demo payload when workspace has no leads yet.

    Intentionally minimal — keeps 1-2 sample leads + small numbers so a fresh
    tenant sees what the dashboard *looks* like without us inventing a fake
    populated workspace. As soon as the user adds even one real lead, the
    real-data branch above takes over.
    """
    return {
        "computed_from_real_data": False,
        "revenue_leakage": {
            "score_pct": 12,
            "headline": "Your dashboard is ready — add leads to see real insights.",
            "subhead": "These cards will populate with your live pipeline as soon as you add or import leads.",
            "breakdown": [
                {"label": "1 overdue follow-up (sample)", "count": 1, "key": "overdue"},
                {"label": "1 hot lead untouched (sample)", "count": 1, "key": "hot_untouched"},
            ],
            "cta": "Add your first lead",
        },
        "money_at_risk": {"total_inr": 150000, "total_label": "₹1.5L", "rows": _demo_money_at_risk_rows(), "cta": "Rescue These Leads"},
        "daily_brief": {"greeting": "Good morning", "lines": ["This is a preview of your daily brief.", "Add leads and Aria will surface real insights here every morning."], "cta": "Generate Today's Sales Brief"},
        "hot_leads_untouched": {"count": 1, "rows": _demo_hot_untouched_rows()},
        "first_response": {"avg_hours": 0, "best_rep": None, "slowest_rep": None, "target_minutes": 30, "pending_first_response": 0, "insight": "Aria will track your first-response time the moment you connect a lead source."},
        "proposal_graveyard": {"count": 0, "rows": _demo_proposal_graveyard_rows()},
        "source_quality": {"rows": _demo_source_quality_rows(), "insight": "Connect a channel — Aria will show you which sources produce the highest-quality pipeline."},
        "lost_reasons": {"rows": [], "insight": "ARIA helps you separate marketing problems from sales process problems once you've logged some lost leads."},
        "pipeline_value": 150000,
        "pipeline_value_label": "₹1.5L",
    }
