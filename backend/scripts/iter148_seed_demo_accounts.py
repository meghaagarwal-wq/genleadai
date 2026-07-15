"""iter148 — Provision Pietential client + Demo viewer accounts with
strict workspace isolation, and seed the 6 demo leads (3 B2B Instinct +
3 B2C Automation).

Run: cd /app/backend && python -m scripts.iter148_seed_demo_accounts
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from passlib.context import CryptContext

from deps import db

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
NOW = datetime.now(timezone.utc)


def iso(dt):
    return dt.isoformat()


# ─────────────── ACCOUNT 1 — Megha@contentvista.com ────────────────
# iter160 — Pietential workspace + owner permanently retired. This
# function is intentionally a no-op so any legacy caller (e.g. running
# `python -m scripts.iter148_seed_demo_accounts` standalone) doesn't
# recreate the retired tenant.
def setup_pietential_owner():
    return None


# ─────────────── ACCOUNT 2 — meghaagarwaljain2015@gmail.com ────────
def setup_demo_viewer():
    email = "meghaagarwaljain2015@gmail.com"
    new_hash = pwd.hash("DemoView2026!")
    db.users.update_one(
        {"email": email},
        {"$set": {
            "password_hash": new_hash,
            "tenant_id": "ten_demo",
            "role": "workspace_viewer",
            "full_name": "Megha Agarwal",
            "is_active": True,
            "updated_at": iso(NOW),
        }},
        upsert=True,
    )
    db.tenant_memberships.update_one(
        {"tenant_id": "ten_demo", "user_email": email},
        {"$set": {
            "id": "mem_demo_megha_viewer",
            "tenant_id": "ten_demo",
            "user_email": email,
            "role": "viewer",
            "joined_at": iso(NOW),
        }},
        upsert=True,
    )
    other = db.tenant_memberships.delete_many({
        "user_email": email,
        "tenant_id": {"$ne": "ten_demo"},
    }).deleted_count
    print(f"✓ ACCOUNT 2 {email} provisioned as workspace_viewer of ten_demo (removed {other} stray memberships)")


# ─────────────────────── DEMO LEAD SEEDING ─────────────────────────
TENANT = "ten_demo"
B2B_DOMAINS = ["novabridge.io", "kestrelfinancial.com", "alveron.com"]


def cleanup_existing_demo_seeds():
    """Idempotent — remove any prior iter148 seeded data so the script
    is safely re-runnable."""
    n_leads = db.pt_leads.delete_many({"tenant_id": TENANT, "seed_source": "iter148"}).deleted_count
    n_ins = db.pt_insights.delete_many({"tenant_id": TENANT, "seed_source": "iter148"}).deleted_count
    n_out = db.outbound_log.delete_many({"tenant_id": TENANT, "seed_source": "iter148"}).deleted_count
    n_in = db.inbound_messages.delete_many({"tenant_id": TENANT, "seed_source": "iter148"}).deleted_count
    n_act = db.activities.delete_many({"tenant_id": TENANT, "seed_source": "iter148"}).deleted_count
    print(f"  ↻ cleaned: pt_leads={n_leads}, pt_insights={n_ins}, outbound={n_out}, inbound={n_in}, activities={n_act}")


def seed_b2b_lead(lead_data, insight_data):
    """Insert ONE pt_lead + matching pt_insight card."""
    lead = {
        "id": lead_data["id"],
        "tenant_id": TENANT,
        "seed_source": "iter148",
        "first_name": lead_data["first_name"],
        "last_name": lead_data["last_name"],
        "email": lead_data["email"],
        "job_title": lead_data["title"],
        "title": lead_data["title"],
        "company_name": lead_data["company_name"],
        "company_size": lead_data["company_size"],
        "linkedin_url": lead_data.get("linkedin_url"),
        "source": "lemlist",
        "stage": lead_data["stage"],
        "score": lead_data["score"],
        "icp_segment": lead_data["icp_id"],
        "icp_segment_name": lead_data["icp_name"],
        "icp_score": lead_data["score"],
        "lemlist_intent": lead_data["intent"],
        "reply_sentiment": lead_data.get("reply_sentiment"),
        "lemlist_data": lead_data.get("lemlist_data", {}),
        "automation_status": "active",
        "owner": "demo-viewer",
        "scoring_source": "iter148_seed",
        "lead_score": lead_data["score"],
        "account_tier": lead_data["account_tier"],
        "founder_flag": lead_data["account_tier"] == "tier_1",
        "created_at": iso(NOW - timedelta(days=lead_data["age_days"])),
        "updated_at": iso(NOW - timedelta(hours=lead_data.get("updated_hours_ago", 4))),
        "last_activity_at": iso(NOW - timedelta(hours=lead_data.get("updated_hours_ago", 4))),
    }
    db.pt_leads.insert_one(lead.copy())

    insight = {
        "id": insight_data["id"],
        "tenant_id": TENANT,
        "seed_source": "iter148",
        "lead_id": lead["id"],
        "signal_type": insight_data["signal_type"],
        "signal_summary": insight_data["signal_summary"],
        "signal_date": insight_data["signal_date"],
        "why_relevant_for_pietential": insight_data["why_relevant"],
        "confidence": insight_data["confidence"],
        "source_url": insight_data.get("source_url"),
        "outreach_recommendation": {
            "channel": insight_data["channel"],
            "timing": insight_data["timing"],
            "opening_message": insight_data["opening_message"],
            "tone": "consultative",
        },
        "icp_segment": lead_data["icp_id"],
        "lemlist_intent": lead_data["intent"],
        "lead_score": lead_data["score"],
        "account_tier": lead_data["account_tier"],
        "founder_flag": lead_data["account_tier"] == "tier_1",
        "signal_dedup_hash": f"demo_seed_{lead['id']}",
        # UI-compat fields (mirror iter143 IntelligenceFeed mapping)
        "prospect_name": f"{lead['first_name']} {lead['last_name']}",
        "prospect_title": lead["job_title"],
        "prospect_company": lead["company_name"],
        "suggested_message": insight_data["opening_message"],
        "icp_match_name": lead_data["icp_name"],
        "icp_match_score": lead_data["score"] / 100.0,
        "status": "new",
        "source": "pietential_engine",
        "created_at": iso(NOW - timedelta(hours=insight_data.get("hours_ago", 6))),
        "week_of": NOW.strftime("%G-W%V"),
    }
    db.pt_insights.insert_one(insight.copy())


# ── B2B Lead 1 — Sarah Chen ───────────────────────────────────────
LEAD_SARAH = {
    "id": "ptl_demo_sarah_chen",
    "first_name": "Sarah", "last_name": "Chen",
    "email": "sarah.chen@novabridge.io",
    "title": "Chief People Officer",
    "company_name": "NovaBridge Technologies",
    "company_size": 2400,
    "linkedin_url": "https://linkedin.com/in/sarahchen-cpo",
    "stage": "hot", "score": 84,
    "icp_id": "icp_b", "icp_name": "CHRO/CPO Enterprise",
    "intent": "HIGH_INTENT",
    "account_tier": "tier_1",
    "age_days": 14, "updated_hours_ago": 2,
    "lemlist_data": {"opens": 4, "clicks": 0, "replies": 0, "campaign": "demo-CPO-Q2"},
}
INSIGHT_SARAH = {
    "id": "ins_demo_sarah_chen",
    "signal_type": "new_people_leader",
    "signal_date": "2 weeks ago",
    "signal_summary": "Sarah Chen appointed as new CPO at NovaBridge Technologies following a 40% headcount expansion in Q1 2026.",
    "why_relevant": "New CPO during 40% growth = textbook moment to assess employee experience tooling. They will be evaluating their HR-tech stack in the first 90 days.",
    "confidence": 0.93,
    "source_url": "https://novabridge.io/press/new-cpo-appointment",
    "channel": "linkedin",
    "timing": "Tuesday 10am IST",
    "opening_message": "Congrats on the new role at NovaBridge — stepping into a CPO seat during a growth phase is a different challenge entirely. Curious how you're thinking about employee experience at scale?",
    "hours_ago": 5,
}

# ── B2B Lead 2 — Arjun Mehta ──────────────────────────────────────
LEAD_ARJUN = {
    "id": "ptl_demo_arjun_mehta",
    "first_name": "Arjun", "last_name": "Mehta",
    "email": "arjun.mehta@kestrelfinancial.com",
    "title": "VP People & Culture",
    "company_name": "Kestrel Financial Group",
    "company_size": 1800,
    "stage": "engaged", "score": 71,
    "icp_id": "icp_e", "icp_name": "VP People Growth-Stage",
    "intent": "HIGH_INTENT",
    "reply_sentiment": "POSITIVE",
    "account_tier": "tier_1",
    "age_days": 21, "updated_hours_ago": 18,
    "lemlist_data": {"opens": 6, "clicks": 1, "replies": 1, "campaign": "demo-VPpeople-Q2"},
}
INSIGHT_ARJUN = {
    "id": "ins_demo_arjun_mehta",
    "signal_type": "layoffs",
    "signal_date": "3 weeks ago",
    "signal_summary": "Kestrel Financial Group announced a 12% workforce reduction across operations and back-office functions in March 2026.",
    "why_relevant": "Layoffs of this scale create acute morale and retention risk for the surviving 88% — Pietential's pulse engine is built for exactly this aftermath.",
    "confidence": 0.91,
    "source_url": "https://kestrelfinancial.com/investor-relations/march-2026-update",
    "channel": "email",
    "timing": "Within 48 hours",
    "opening_message": "The restructuring at Kestrel is significant — 12% reductions always create culture and morale pressure that's hard to measure from the outside. How is the people team navigating the aftermath?",
    "hours_ago": 20,
}

# ── B2B Lead 3 — James Whitfield ──────────────────────────────────
LEAD_JAMES = {
    "id": "ptl_demo_james_whitfield",
    "first_name": "James", "last_name": "Whitfield",
    "email": "j.whitfield@alveron.com",
    "title": "Head of HR Transformation",
    "company_name": "Alveron Consulting",
    "company_size": 3200,
    "stage": "warm", "score": 58,
    "icp_id": "icp_d", "icp_name": "People Analytics",
    "intent": "MEDIUM_INTENT",
    "account_tier": "tier_2",
    "age_days": 9, "updated_hours_ago": 36,
    "lemlist_data": {"opens": 2, "clicks": 1, "replies": 0, "campaign": "demo-analytics-Q2"},
}
INSIGHT_JAMES = {
    "id": "ins_demo_james_whitfield",
    "signal_type": "benefits_hr_transformation",
    "signal_date": "Last week",
    "signal_summary": "Alveron Consulting launched an enterprise-wide HR transformation programme with investment in people analytics tools.",
    "why_relevant": "Active people-analytics initiative = data-curious buyer. Pietential's quantified employee-health metrics translate directly into the dashboards their programme already plans to build.",
    "confidence": 0.84,
    "source_url": "https://alveron.com/blog/hr-transformation-launch",
    "channel": "linkedin",
    "timing": "This week",
    "opening_message": "The HR transformation initiative at Alveron caught my attention — people analytics investment at that scale usually surfaces questions about what the data is actually telling you about employee health. What's driving the programme?",
    "hours_ago": 30,
}


# ── B2C Automation seeders ────────────────────────────────────────
def seed_b2c_lead(lead, msgs):
    """B2C automation lead — pt_lead + conversation messages."""
    db.pt_leads.insert_one({
        "id": lead["id"],
        "tenant_id": TENANT,
        "seed_source": "iter148",
        "first_name": lead["first_name"],
        "last_name": lead.get("last_name", ""),
        "email": lead["email"],
        "phone": lead.get("phone"),
        "company_name": lead.get("company_name", ""),
        "job_title": lead.get("job_title", ""),
        "title": lead.get("job_title", ""),
        "source": lead["channel"],
        "stage": lead["stage"],
        "score": lead["score"],
        "lemlist_intent": lead["intent"],
        "automation_status": "active",
        "lead_type": "B2C",
        "journey_step": lead["journey_step"],
        "journey_total": 7,
        "next_action": lead["next_action"],
        "owner": "aria",
        "scoring_source": "iter148_seed",
        "lead_score": lead["score"],
        "account_tier": "tier_3",
        "founder_flag": False,
        "created_at": iso(NOW - timedelta(days=lead.get("age_days", 3))),
        "updated_at": iso(NOW - timedelta(hours=lead.get("updated_hours_ago", 2))),
        "last_activity_at": iso(NOW - timedelta(hours=lead.get("updated_hours_ago", 2))),
    })
    base_ts = NOW - timedelta(hours=len(msgs) * 4 + 2)
    for i, m in enumerate(msgs):
        ts = base_ts + timedelta(hours=i * 4)
        if m["direction"] == "outbound":
            db.outbound_log.insert_one({
                "id": f"ob_{uuid.uuid4().hex[:14]}",
                "tenant_id": TENANT,
                "seed_source": "iter148",
                "lead_id": lead["id"],
                "channel": lead["channel"],
                "provider": lead["channel"],
                "provider_id": f"demo-{uuid.uuid4().hex[:10]}",
                "actor_user_id": "aria",
                "subject": m.get("subject", ""),
                "message_preview": m["text"],
                "ai_powered": True,
                "sent": True,
                "created_at": iso(ts),
            })
        else:
            db.inbound_messages.insert_one({
                "id": f"in_{uuid.uuid4().hex[:14]}",
                "tenant_id": TENANT,
                "seed_source": "iter148",
                "lead_id": lead["id"],
                "channel": lead["channel"],
                "from": lead["email"],
                "external_id": f"demo-{uuid.uuid4().hex[:10]}",
                "text": m["text"],
                "received_at": iso(ts + timedelta(minutes=12)),
                "unmatched": False,
            })


PRIYA = {
    "id": "ptl_demo_priya_nair",
    "first_name": "Priya", "last_name": "Nair",
    "email": "priya.nair@designlab.example",
    "phone": "+91-98202-12345",
    "channel": "whatsapp",
    "company_name": "DesignLab Studio",
    "job_title": "Founder",
    "stage": "warm", "score": 45,
    "intent": "MEDIUM_INTENT",
    "journey_step": 2,
    "next_action": "Awaiting reply · ARIA will qualify on response",
    "age_days": 1, "updated_hours_ago": 2,
}
PRIYA_MSGS = [
    {"direction": "outbound", "text": "Hi Priya! Thanks for reaching out. Quick question — are you looking for support for yourself or your team?"},
    {"direction": "inbound", "text": "For my team — I run a 12-person design agency."},
    {"direction": "outbound", "text": "Got it! And what's the biggest challenge you're facing with the team right now?"},
]

RAHUL = {
    "id": "ptl_demo_rahul_desai",
    "first_name": "Rahul", "last_name": "Desai",
    "email": "rahul.desai@brightlogic.example",
    "channel": "email",
    "company_name": "BrightLogic Software",
    "job_title": "Co-founder",
    "stage": "hot", "score": 78,
    "intent": "HIGH_INTENT",
    "journey_step": 5,
    "next_action": "Call booked — 14 June 2026 11am IST",
    "age_days": 6, "updated_hours_ago": 8,
}
RAHUL_MSGS = [
    {"direction": "outbound", "subject": "Quick intro from ARIA — your team wellbeing query",
     "text": "Hi Rahul — saw your enquiry on the contact form. ARIA here (Pietential's AI lead assistant). Could you tell me a bit more about what prompted the search? Happy to share resources before any call."},
    {"direction": "inbound", "text": "Hey — we're at 28 people and engineer attrition is biting. Two seniors quit last quarter. Looking for a wellbeing solution that actually moves the needle, not another survey tool."},
    {"direction": "outbound", "subject": "Two quick questions to point you to the right resources",
     "text": "Two qualifying questions: (1) Are you currently using any pulse / engagement platform? (2) Do you have a rough budget range in mind for this cycle?"},
    {"direction": "inbound", "text": "Currently using Officevibe but engagement is poor. Budget around $15-25k/year for the right thing. Need to move quickly — Q3 plan being finalised."},
    {"direction": "outbound", "subject": "Booking link — 30-minute call with our founder",
     "text": "Perfect fit. I'd love to set up a quick 30-minute call with our founder John to walk you through how Pietential complements Officevibe. Here's a link to book a time that works for you: https://cal.pietential.ai/founder/30min"},
]

ANANYA = {
    "id": "ptl_demo_ananya_sharma",
    "first_name": "Ananya", "last_name": "Sharma",
    "email": "ananya.sharma@retailco.example",
    "phone": "+91-99876-54321",
    "channel": "whatsapp",
    "company_name": "RetailCo (Referral)",
    "job_title": "HR Manager",
    "stage": "warm", "score": 35,
    "intent": "MEDIUM_INTENT",
    "journey_step": 3,
    "next_action": "ARIA sending follow-up in 3 days with lead magnet",
    "age_days": 4, "updated_hours_ago": 50,
}
ANANYA_MSGS = [
    {"direction": "outbound", "text": "Hi Ananya — Jaya from RoseBud Consulting passed along your details. Could you tell me a bit about what's prompting the conversation about employee wellbeing?"},
    {"direction": "inbound", "text": "Interesting — can you send me more information first?"},
]


# ─────────────────────── Run all ──────────────────────────────────
if __name__ == "__main__":
    print(f"iter148 — provisioning accounts + seeding {TENANT} demo leads @ {iso(NOW)}")
    setup_pietential_owner()
    setup_demo_viewer()
    print("---")
    cleanup_existing_demo_seeds()
    # B2B
    seed_b2b_lead(LEAD_SARAH, INSIGHT_SARAH)
    print(f"  ✓ seeded B2B Sarah Chen ({LEAD_SARAH['email']}) + insight {INSIGHT_SARAH['id']}")
    seed_b2b_lead(LEAD_ARJUN, INSIGHT_ARJUN)
    print(f"  ✓ seeded B2B Arjun Mehta ({LEAD_ARJUN['email']}) + insight {INSIGHT_ARJUN['id']}")
    seed_b2b_lead(LEAD_JAMES, INSIGHT_JAMES)
    print(f"  ✓ seeded B2B James Whitfield ({LEAD_JAMES['email']}) + insight {INSIGHT_JAMES['id']}")
    # B2C
    seed_b2c_lead(PRIYA, PRIYA_MSGS)
    print(f"  ✓ seeded B2C Priya Nair ({PRIYA['email']}) + {len(PRIYA_MSGS)} msgs")
    seed_b2c_lead(RAHUL, RAHUL_MSGS)
    print(f"  ✓ seeded B2C Rahul Desai ({RAHUL['email']}) + {len(RAHUL_MSGS)} msgs")
    seed_b2c_lead(ANANYA, ANANYA_MSGS)
    print(f"  ✓ seeded B2C Ananya Sharma ({ANANYA['email']}) + {len(ANANYA_MSGS)} msgs")
    print(f"\n✅ Done. 6 demo leads + 3 insight cards seeded in {TENANT}.")
