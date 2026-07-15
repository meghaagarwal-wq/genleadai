"""Minimal FastAPI starter that serves the B2C Demo Dashboard contract.

Run with:
    pip install fastapi uvicorn
    uvicorn b2c_starter:app --reload --port 8001

This returns the same JSON shape your React component expects. Replace
the hard-coded values with your real DB queries to ship.
"""
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="B2C Demo Dashboard Starter")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # tighten for prod
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/dashboard/b2c")
def b2c():
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "header": {
            "workspace_name": "Your Workspace",
            "owner_name":     "Demo User",
            "greeting":       "Good morning",
            "mode":           "B2C Automation",
            "currency":       "USD",
            "last_refresh":   now_iso,
        },
        "kpis": {
            "leads_today":     {"value": 12, "trend": {"direction": "up",   "pct": 33}},
            "active_convos":   {"value": 4,  "label": "incl. 1 booked"},
            "bookings_week":   {"value": 5,  "trend": {"direction": "up",   "pct": 25}},
            "conversion_rate": {"value": 18, "trend": {"direction": "flat", "pct": 0}},
            "revenue_pipeline":{"value": 142000, "currency": "USD"},
        },
        "aria_time_saved": {
            "hours": 12.4,
            "money_equivalent": 6200,
            "breakdown": {"conversations": 47, "drafts": 31, "insights": 9, "researched": 14},
        },
        "momentum": {
            "direction": "up",
            "score": 78,
            "label": "Accelerating",
            "driver_text": "Hot leads ↑ 30% vs last week",
        },
        "revenue_forecast": {
            "coming_soon": False,
            "projected_end_of_month": 285000,
            "last_month_actual":      210000,
            "pct_of_last_month":      67,
        },
        "conversations": [
            {"lead_id": "lead_001", "name": "Sarah Chen",     "initials": "SC", "status": "live",      "snippet": "Sounds great, can you share the deck?",   "minutes_ago": 4},
            {"lead_id": "lead_002", "name": "Arjun Mehta",    "initials": "AM", "status": "qualified", "snippet": "Booking Wed 3pm — sending invite",         "minutes_ago": 18},
            {"lead_id": "lead_003", "name": "Priya Sharma",   "initials": "PS", "status": "waiting",   "snippet": "Sent the pricing doc — waiting on team",   "minutes_ago": 62},
            {"lead_id": "lead_004", "name": "Marcus O'Brien", "initials": "MO", "status": "booked",    "snippet": "✓ Discovery call confirmed for Friday",    "minutes_ago": 95},
        ],
        "lead_sources": [
            {"channel": "linkedin",  "count": 7},
            {"channel": "whatsapp",  "count": 3},
            {"channel": "website",   "count": 2},
        ],
        "asset_performance": {
            "coming_soon": False,
            "rows": [
                {"name": "ICP Diagnostic Playbook",   "clicks": 12},
                {"name": "Retention ROI Calculator",  "clicks": 9},
                {"name": "Culture Index Sample",      "clicks": 7},
            ],
        },
        "funnel": [
            {"stage": "Discovered", "count": 120, "pct_of_prev": None, "drop_flag": False},
            {"stage": "Engaged",    "count": 60,  "pct_of_prev": 50,    "drop_flag": True},
            {"stage": "Qualified",  "count": 28,  "pct_of_prev": 47,    "drop_flag": False},
            {"stage": "Replied",    "count": 14,  "pct_of_prev": 50,    "drop_flag": False},
            {"stage": "Booked",     "count": 5,   "pct_of_prev": 36,    "drop_flag": False},
        ],
        "biggest_drop": {"from": "Discovered", "to": "Engaged", "loss_pct": 50},
        "sequences": [
            {"name": "Pilot-Q1 Outreach",        "active": 18, "booked": 4, "rate": 22.2},
            {"name": "Mid-Market Re-engagement", "active": 32, "booked": 3, "rate": 9.4},
            {"name": "Enterprise Founder Touch", "active": 9,  "booked": 2, "rate": 22.2},
        ],
        "channel_overlap": {
            "coming_soon": False,
            "rows": [
                {"channels": "linkedin + email",      "leads": 6, "conv_rate": 33.3},
                {"channels": "whatsapp + instagram",  "leads": 4, "conv_rate": 25.0},
                {"channels": "website + linkedin",    "leads": 3, "conv_rate": 0.0},
            ],
        },
        "ghost_leads": [
            {"id": "lead_g1", "name": "Lin Zhao",        "company": "Asia Pay Group", "days_silent": 30},
            {"id": "lead_g2", "name": "Aisha Patel",     "company": "Quantum Logistics", "days_silent": 22},
            {"id": "lead_g3", "name": "Priya Sharma",    "company": "FinSecure Bank",    "days_silent": 15},
        ],
        "cost_per_qualified_lead": {
            "coming_soon": False,
            "rows": [
                {"channel": "linkedin",  "spend": 4500, "qualified": 12, "cpql": 375, "currency": "USD"},
                {"channel": "google",    "spend": 2200, "qualified": 8,  "cpql": 275, "currency": "USD"},
                {"channel": "facebook",  "spend": 1800, "qualified": 5,  "cpql": 360, "currency": "USD"},
            ],
        },
    }
