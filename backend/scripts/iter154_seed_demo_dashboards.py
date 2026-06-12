"""iter154 — Seed `ten_demo` with rich data so every dashboard widget renders
real numbers (no "Coming soon" placeholders) and the sidebar feels alive.

Run with:
    cd /app/backend && python -m scripts.iter154_seed_demo_dashboards

Idempotent: re-running deletes the previously seeded rows (matched by
`source: 'demo_seed_v154'`) before re-inserting fresh ones, so the demo
always looks current relative to the system clock.

Coverage (per dashboard spec):
  * 10 pt_leads across all stages, mixed scores, source_channels (multi-touch)
  * 8 pt_insights (Instinct cards) — 3 founder_flag, 2 pending approvals
  * 6 outbound_log rows (last 2h) → Live Conversations widget
  * 4 inbound_messages → Funnel "Replied" stage
  * 5 booking_events (this month + last month, deal_value set) → Revenue Forecast + agenda
  * 8 score_history rows (last 24h) → Why-Now feed + Momentum
  * 6 asset_clicks → Asset Performance widget
  * 3 lemlist_sequences → Sequences widget
  * 4 ad_spend rows → Cost-per-Qualified-Lead widget
  * Backdated lead created_at across 95 days → unlocks Signal Attribution
"""
from __future__ import annotations

import os
import random
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from deps import db  # noqa: E402

TENANT = "ten_demo"
SOURCE_TAG = "demo_seed_v154"
NOW = datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _seeded_leads() -> list[dict]:
    """10 leads across all pipeline stages with diverse scores and channels."""
    cfg = [
        # (first, last, company, title, score, stage, source, channels, days_ago_created, last_activity_hours_ago, deal_value, sentiment)
        ("Sarah",   "Chen",        "Acme HR Tech",        "VP People",        92, "session_pilot",  "linkedin",  ["linkedin", "email"],                  3,    2,    85000,  None),
        ("Arjun",   "Mehta",       "TechCorp India",      "Director, People", 88, "discovery_call", "website",   ["website", "linkedin"],                7,    4,    65000,  None),
        ("James",   "Whitfield",   "GlobalManu Ltd",      "CHRO",             82, "discovery_call", "referral",  ["referral", "email", "linkedin"],     12,   18,   120000, None),
        ("Priya",   "Sharma",      "FinSecure Bank",      "Head of L&D",      76, "qualified",      "email",     ["email", "whatsapp"],                 18,  360,   45000,  None),  # ghost candidate (15d silent)
        ("Marcus",  "O'Brien",     "Helix Pharma",        "People Analytics", 71, "qualified",      "linkedin",  ["linkedin"],                          22,  408,   90000,  "NEGATIVE"),  # deal_risk: negative reply
        ("Aisha",   "Patel",       "Quantum Logistics",   "VP HR",            64, "engaged",        "lemlist",   ["lemlist", "email"],                  28,  528,   55000,  None),  # ghost (22d silent)
        ("David",   "Müller",      "EcoBuild GmbH",       "Founder",          58, "engaged",        "website",   ["website"],                           35,   36,   30000,  None),
        ("Lin",     "Zhao",        "Asia Pay Group",      "CFO",              42, "contacted",      "linkedin",  ["linkedin", "referral"],              48,  720,   None,   None),  # ghost (30d silent, score≥40)
        ("Olivia",  "Tremblay",    "NordicWell Co",       "Head of People",   34, "contacted",      "whatsapp",  ["whatsapp", "instagram"],              0,   12,   None,   None),  # created today
        ("Yusuf",   "Rahman",      "Sahara Energy",       "Chief People",     22, "new",            "instagram", ["instagram", "facebook"],              0,    3,   None,   None),  # created today
    ]
    signal_map = {
        "session_pilot":  ["culture"],
        "discovery_call": ["culture", "leadership_change"],
        "qualified":      ["restructuring", "growth"],
        "engaged":        ["growth", "wellbeing"],
        "contacted":      ["wellbeing"],
        "new":            ["unknown"],
    }
    rows = []
    for (fn, ln, co, title, score, stage, source, channels, days_ago, hrs_ago, deal_value, sentiment) in cfg:
        created = NOW - timedelta(days=days_ago)
        last_act = NOW - timedelta(hours=hrs_ago)
        rows.append({
            "id": f"ptl_demo_{fn.lower()}_{ln.lower().replace(chr(39), '').replace(chr(252), 'u')}",
            "tenant_id": TENANT,
            "first_name": fn, "last_name": ln,
            "email": f"{fn.lower()}.{ln.lower().replace(chr(39), '')}@{co.lower().split()[0]}.com",
            "company_name": co, "title": title, "job_title": title,
            "source": source, "source_channels": channels,
            "score": score, "icp_score": score,
            "stage": stage,
            "automation_status": "auto" if score < 60 else "manual",
            "owner": "demo@genleadai.com",
            "last_activity_at": _iso(last_act),
            "last_contacted_at": _iso(last_act),
            "created_at": _iso(created),
            "updated_at": _iso(NOW),
            "latest_signal": random.choice(signal_map.get(stage, ["unknown"])),
            "icp_segment_name": "Enterprise HR" if score >= 70 else "Mid-Market HR" if score >= 40 else "SMB",
            "lemlist_intent": "high" if score >= 70 else "medium" if score >= 40 else "low",
            "deal_value": deal_value,
            "reply_sentiment": sentiment,
            "lemlist_data": {
                "campaign": random.choice(["Pilot-Q1", "Mid-Market-Outreach", "Enterprise-Founder"]),
                "opens": random.randint(2, 12), "replies": random.randint(0, 3), "clicks": random.randint(0, 5),
            } if score >= 40 else None,
            "rescored_at": _iso(NOW - timedelta(days=random.randint(0, 2))),
            "scoring_source": "demo_seed",
            "last_decay_at": _iso(NOW),
            "lead_score_delta": random.randint(-15, 25),
            "next_followup_at": _iso(NOW + timedelta(days=random.randint(0, 3))),
            "_seed_source": SOURCE_TAG,
        })
    return rows


def _seeded_insights(leads: list[dict]) -> list[dict]:
    """12 pt_insights — ≥3 per major signal_type so signal_attribution unlocks; mix of founder_flag + pending approvals."""
    templates = [
        ("culture",           "leadership team announced flat-hierarchy restructure",
         "Headcount cut 12% while pushing culture-first messaging — classic 'culture vs cost' moment our pilot has solved before.",
         "Saw your team's note on flat-hierarchy — happy to share our 6-week framework for keeping culture intact during restructures.",
         0.86, True),
        ("culture",           "Glassdoor culture rating dropped 0.6 points in Q4",
         "Culture-pulse degradation signals retention risk — our 14-day diagnostic captures the root cause cleanly.",
         "Noticed the Glassdoor shift — would a quick benchmark vs your peer set help frame next steps?",
         0.74, False),
        ("culture",           "internal memo on 'culture reset' leaked",
         "Public culture intervention announcement = ready buyer for diagnostic-led approach.",
         "Saw the memo coverage — we've helped 3 companies translate culture-reset intent into a 90-day roadmap.",
         0.69, False),
        ("leadership_change", "promoted CHRO last week",
         "New CHRO will want quick wins in first 90 days — our diagnostic delivers measurable culture-pulse in 14 days.",
         "Congrats on the CHRO role — most new HR leaders we work with want a clean 90-day baseline.",
         0.78, True),
        ("leadership_change", "CEO transition announced for Q2",
         "CEO change means culture-alignment audit becomes board-level priority.",
         "Saw the CEO announcement — board-aligned culture data tends to be useful in the first 60 days.",
         0.72, False),
        ("leadership_change", "VP People exited; interim from Big-4 in place",
         "Interim leadership often outsources diagnostic work — high-fit engagement window.",
         "Caught the VP People news — happy to support the interim with a quick read on the engagement baseline.",
         0.65, False),
        ("restructuring",     "filed for layoffs of 8% (3 rounds in 6 months)",
         "Survivor-engagement is the #1 risk after rolling layoffs. We've helped 4 logos protect retention.",
         "Saw the latest workforce update — happy to share retention-after-RIF playbook (anonymised, real data).",
         0.91, True),
        ("restructuring",     "M&A rumour — Bloomberg item Tuesday",
         "M&A means integration risk on culture/comp — high-urgency window for diagnostic.",
         "Saw the Bloomberg piece — if the M&A happens, culture-integration is the #1 retention lever. Worth a chat?",
         0.66, False),
        ("restructuring",     "spinning off division — new entity Q3",
         "Spin-off needs fresh culture/comp framework — green-field opportunity.",
         "Saw the spin-off plans — building culture from day-one is dramatically easier than retrofitting.",
         0.70, False),
        ("growth",            "Series B closed, 200→500 headcount target",
         "Scaling 2.5× in 12 months breaks most engagement systems — we onboarded a similar Series B at month 9 last cycle.",
         "Congrats on the Series B — when you start the hiring sprint, would a 30-min ride-along on retention be useful?",
         0.74, False),
        ("growth",            "opening 3 new offices APAC",
         "Multi-region expansion = ICP fit for our regional culture diagnostic.",
         "Saw the APAC expansion — we have an MNC-ready regional culture diagnostic worth 20 min.",
         0.68, False),
        ("wellbeing",         "Glassdoor reviews flag burnout (15 mentions in 30d)",
         "Burnout signal + their existing benefits stack is a perfect overlap for our wellbeing-ROI module.",
         "Spotted the recent reviews — would you have 20 min to compare your wellbeing stack vs benchmark?",
         0.81, False),
    ]
    rows = []
    for i, ((sig_type, summary, why_rel, msg, conf, founder)) in enumerate(templates):
        lead = leads[i % len(leads)]
        status = "pending" if i < 2 else ("new" if i < 7 else "actioned")
        rows.append({
            "id": f"ins_demo_{sig_type}_{i:02d}",
            "tenant_id": TENANT,
            "lead_id": lead["id"],
            "signal_type": sig_type,
            "signal_summary": f"{lead['company_name']} {summary}",
            "why_relevant_for_pietential": why_rel,
            "outreach_recommendation": {
                "channel": lead["source"],
                "channel_reason": f"Lead engaged most recently via {lead['source']}.",
                "timing": "Tuesday 10am IST",
                "timing_reason": "Highest mid-week response rate for HR personas.",
                "opening_message": msg,
            },
            "icp_segment": lead["icp_segment_name"],
            "lemlist_intent": lead["lemlist_intent"],
            "lead_score": lead["score"],
            "account_tier": "enterprise" if lead["score"] >= 70 else "mid-market",
            "signal_dedup_hash": f"hash_{sig_type}_{i}",
            "prospect_name": f"{lead['first_name']} {lead['last_name']}",
            "prospect_title": lead["title"],
            "prospect_company": lead["company_name"],
            "suggested_message": msg,
            "confidence": conf,
            "icp_match_name": lead["icp_segment_name"],
            "icp_match_score": int(conf * 100),
            "status": status,
            "founder_flag": founder,
            "source": SOURCE_TAG,
            "created_at": _iso(NOW - timedelta(hours=i * 4 + 1)),
            "week_of": NOW.strftime("%Y-W%V"),
        })
    return rows


def _seeded_outbound(leads: list[dict]) -> list[dict]:
    """6 active conversations in the last 2 hours."""
    rows = []
    snippets = [
        ("WhatsApp", "whatsapp", "Sounds good — what time on Thursday works for the demo?"),
        ("LinkedIn", "linkedin", "Yes, share the case study. Especially the retention metrics."),
        ("Email",    "email",    "Booking the call for Wed 3pm IST — sending invite shortly."),
        ("Email",    "email",    "Thanks for the resource pack. Sharing with my team."),
        ("WhatsApp", "whatsapp", "Have a question about the methodology — call me when free."),
        ("LinkedIn", "linkedin", "Connecting — talked to your team last quarter. Open to revisit."),
    ]
    for i, (label, ch, body) in enumerate(snippets):
        lead = leads[i]
        rows.append({
            "tenant_id": TENANT, "lead_id": lead["id"],
            "channel": ch, "provider": ch, "provider_id": f"msg_demo_{i}",
            "sent": True, "logged_only": False,
            "to": lead["email"], "subject": f"Follow-up · {label}",
            "message_preview": body,
            "ai_powered": True, "actor_user_id": "ARIA",
            "error": None,
            "created_at": _iso(NOW - timedelta(minutes=10 + i * 18)),
            "_seed_source": SOURCE_TAG,
        })
    return rows


def _seeded_inbound(leads: list[dict]) -> list[dict]:
    """4 inbound messages → Funnel "Replied to ARIA" stage."""
    rows = []
    for i, lead in enumerate(leads[:4]):
        rows.append({
            "tenant_id": TENANT, "lead_id": lead["id"],
            "channel": lead["source"], "from": lead["email"],
            "body": "Thanks — yes, interested. What's the typical onboarding timeline?",
            "received_at": _iso(NOW - timedelta(hours=i + 1)),
            "_seed_source": SOURCE_TAG,
        })
    return rows


def _seeded_bookings(leads: list[dict]) -> list[dict]:
    """5 booking events — 3 this month, 2 last month, deal_value set."""
    rows = []
    this_month_start = NOW.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)
    schedule = [
        (leads[0], NOW + timedelta(hours=2),  90000,  "video",    "booked"),
        (leads[1], NOW + timedelta(hours=6),  75000,  "video",    "booked"),
        (leads[2], this_month_start + timedelta(days=2),  120000, "in-person", "completed"),
        (leads[3], last_month_start + timedelta(days=10), 50000,  "video",     "completed"),
        (leads[4], last_month_start + timedelta(days=20), 65000,  "video",     "completed"),
    ]
    for i, (lead, when, deal, ch, status) in enumerate(schedule):
        rows.append({
            "id": f"book_demo_{i:02d}",
            "tenant_id": TENANT, "lead_id": lead["id"],
            "when": _iso(when), "channel": ch, "deal_value": deal,
            "booked_by": "ARIA", "status": status,
            "created_at": _iso(when - timedelta(days=1)),
            "_seed_source": SOURCE_TAG,
        })
    return rows


def _seeded_score_history(leads: list[dict]) -> list[dict]:
    """8 score changes in the last 24h → Why-Now feed + Momentum."""
    rows = []
    moves = [
        (leads[0], 80, 92, "ARIA detected high-intent reply"),
        (leads[1], 75, 88, "Booked discovery call via WhatsApp"),
        (leads[2], 70, 82, "Forwarded ICP playbook to CFO"),
        (leads[3], 60, 76, "Replied positively to nurture sequence"),
        (leads[4], 65, 71, "Visited pricing page 3× this week"),
        (leads[5], 70, 58, "No-show on yesterday's call"),  # downward
        (leads[6], 50, 34, "Reply: 'Not the right time'"),  # downward
        (leads[7], 30, 42, "Engaged with new LinkedIn post"),
    ]
    for i, (lead, prev, new, reason) in enumerate(moves):
        rows.append({
            "id": f"sh_demo_{i:02d}",
            "tenant_id": TENANT, "lead_id": lead["id"],
            "prev_score": prev, "new_score": new, "delta": new - prev,
            "reason": reason, "source": SOURCE_TAG,
            "created_at": _iso(NOW - timedelta(hours=i + 1)),
        })
    return rows


def _seeded_asset_clicks() -> list[dict]:
    """6 asset clicks today → Asset Performance widget."""
    today = NOW.replace(hour=0, minute=0, second=0, microsecond=0)
    rows = []
    assets = [
        ("ICP Diagnostic Playbook",   12, "linkedin"),
        ("Retention ROI Calculator",   9, "email"),
        ("Culture Index Sample Report", 7, "website"),
        ("CHRO 90-Day Plan PDF",        5, "linkedin"),
        ("Wellbeing Benchmark 2026",    3, "whatsapp"),
        ("Founder Toolkit",             2, "referral"),
    ]
    for asset_name, count, channel in assets:
        for j in range(count):
            rows.append({
                "id": f"ac_demo_{asset_name.replace(' ', '_').lower()}_{j}",
                "tenant_id": TENANT, "asset_name": asset_name,
                "channel": channel, "lead_id": None,
                "created_at": _iso(today + timedelta(hours=random.randint(1, 18), minutes=random.randint(0, 59))),
                "_seed_source": SOURCE_TAG,
            })
    return rows


def _seeded_sequences() -> list[dict]:
    """3 lemlist sequence rollups for the Sequences widget."""
    return [
        {"id": "seq_demo_pilot",    "tenant_id": TENANT, "name": "Pilot-Q1 Outreach",        "active": 18, "booked": 4, "rate": 22.2, "_seed_source": SOURCE_TAG},
        {"id": "seq_demo_midmkt",   "tenant_id": TENANT, "name": "Mid-Market Re-engagement", "active": 32, "booked": 3, "rate": 9.4,  "_seed_source": SOURCE_TAG},
        {"id": "seq_demo_enterpr",  "tenant_id": TENANT, "name": "Enterprise Founder Touch", "active": 9,  "booked": 2, "rate": 22.2, "_seed_source": SOURCE_TAG},
    ]


def _seeded_ad_spend() -> list[dict]:
    """4 ad-spend rows for current month → Cost-per-Qualified-Lead widget."""
    month = NOW.strftime("%Y-%m")
    return [
        {"id": "ads_demo_li",   "tenant_id": TENANT, "channel": "linkedin",  "amount": 4500, "month": month, "_seed_source": SOURCE_TAG},
        {"id": "ads_demo_meta", "tenant_id": TENANT, "channel": "facebook",  "amount": 1800, "month": month, "_seed_source": SOURCE_TAG},
        {"id": "ads_demo_goog", "tenant_id": TENANT, "channel": "google",    "amount": 2200, "month": month, "_seed_source": SOURCE_TAG},
        {"id": "ads_demo_inst", "tenant_id": TENANT, "channel": "instagram", "amount": 900,  "month": month, "_seed_source": SOURCE_TAG},
    ]


def main() -> None:
    random.seed(42)
    print(f"=== iter154 demo seed @ {NOW.isoformat()} ===")

    # 1. Wipe any prior seeded rows for `ten_demo` matching SOURCE_TAG.
    targets = {
        "pt_leads":        {"tenant_id": TENANT, "_seed_source": SOURCE_TAG},
        "pt_insights":     {"tenant_id": TENANT, "source": SOURCE_TAG},
        "outbound_log":    {"tenant_id": TENANT, "_seed_source": SOURCE_TAG},
        "inbound_messages":{"tenant_id": TENANT, "_seed_source": SOURCE_TAG},
        "booking_events":  {"tenant_id": TENANT, "_seed_source": SOURCE_TAG},
        "score_history":   {"tenant_id": TENANT, "source": SOURCE_TAG},
        "asset_clicks":    {"tenant_id": TENANT, "_seed_source": SOURCE_TAG},
        "lemlist_sequences": {"tenant_id": TENANT, "_seed_source": SOURCE_TAG},
        "ad_spend":        {"tenant_id": TENANT, "_seed_source": SOURCE_TAG},
    }
    for col, q in targets.items():
        n = db[col].delete_many(q).deleted_count
        print(f"  cleared {col}: {n}")

    # Also delete any leftover demo leads from prior iterations (no _seed_source).
    # Keep ten_demo's non-iter154 leads if any human-added — match by company list.
    demo_companies = {"Acme HR Tech", "TechCorp India", "GlobalManu Ltd", "FinSecure Bank",
                      "Helix Pharma", "Quantum Logistics", "EcoBuild GmbH", "Asia Pay Group",
                      "NordicWell Co", "Sahara Energy"}
    db["pt_leads"].delete_many({"tenant_id": TENANT, "company_name": {"$in": list(demo_companies)}})

    # 2. Seed.
    leads = _seeded_leads()
    insights = _seeded_insights(leads)
    outbound = _seeded_outbound(leads)
    inbound = _seeded_inbound(leads)
    bookings = _seeded_bookings(leads)
    history = _seeded_score_history(leads)
    clicks = _seeded_asset_clicks()
    seqs = _seeded_sequences()
    spends = _seeded_ad_spend()

    inserts = [
        ("pt_leads",         leads),
        ("pt_insights",      insights),
        ("outbound_log",     outbound),
        ("inbound_messages", inbound),
        ("booking_events",   bookings),
        ("score_history",    history),
        ("asset_clicks",     clicks),
        ("lemlist_sequences", seqs),
        ("ad_spend",         spends),
    ]
    for col, rows in inserts:
        if rows:
            db[col].insert_many(rows)
            print(f"  inserted {col}: {len(rows)}")

    print(f"=== done · 10 leads, {len(insights)} insights, {len(bookings)} bookings, "
          f"{len(history)} score moves, {len(clicks)} asset clicks ===")


if __name__ == "__main__":
    main()
