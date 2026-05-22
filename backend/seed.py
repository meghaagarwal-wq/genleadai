"""Seed database with realistic demo data."""
import os
import random
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
from passlib.context import CryptContext
from dotenv import load_dotenv

load_dotenv()

mongo_client = MongoClient(os.getenv("MONGO_URL"))
db = mongo_client[os.getenv("DB_NAME")]

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Clear existing data
for collection_name in ["users", "leads", "activities", "campaigns", "pipelines"]:
    db[collection_name].drop()

# Users
users = [
    {
        "email": "admin@demo.com",
        "password_hash": pwd_context.hash("Demo1234!"),
        "full_name": "Megha Agarwal",
        "role": "master_admin",
        "avatar_url": "https://images.unsplash.com/photo-1576558656222-ba66febe3dec?w=100&h=100&fit=crop&crop=face",
        "team": "Leadership",
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    },
    {
        "email": "sarah@demo.com",
        "password_hash": pwd_context.hash("Demo1234!"),
        "full_name": "Sarah Chen",
        "role": "sales_rep",
        "avatar_url": "https://images.unsplash.com/photo-1672685667592-0392f458f46f?w=100&h=100&fit=crop&crop=face",
        "team": "Sales",
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    },
    {
        "email": "james@demo.com",
        "password_hash": pwd_context.hash("Demo1234!"),
        "full_name": "James Rodriguez",
        "role": "sales_rep",
        "avatar_url": "https://images.unsplash.com/photo-1769636929388-99eff95d3bf1?w=100&h=100&fit=crop&crop=face",
        "team": "Sales",
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    },
]
db["users"].insert_many(users)
print(f"Seeded {len(users)} users")

# Campaigns
campaigns = [
    {
        "name": "LinkedIn B2B Outreach Q1",
        "description": "Targeted B2B campaign for SaaS decision makers on LinkedIn",
        "channel": "linkedin",
        "lead_type": "B2B",
        "status": "active",
        "start_date": "2026-01-01",
        "end_date": "2026-03-31",
        "budget": 5000.0,
        "spend": 2340.0,
        "target_audience": "SaaS CTOs and VPs of Growth in US/UK",
        "utm_source": "linkedin",
        "utm_medium": "sponsored",
        "utm_campaign": "b2b-q1-2026",
        "goal_leads": 200,
        "goal_conversions": 20,
        "created_by": "admin@demo.com",
        "created_at": datetime.now(timezone.utc).isoformat()
    },
    {
        "name": "Instagram DTC Brand Campaign",
        "description": "B2C campaign targeting DTC brand founders on Instagram",
        "channel": "instagram",
        "lead_type": "B2C",
        "status": "active",
        "start_date": "2026-01-15",
        "end_date": "2026-04-15",
        "budget": 3000.0,
        "spend": 1200.0,
        "target_audience": "DTC brand founders and e-commerce managers",
        "utm_source": "instagram",
        "utm_medium": "reels",
        "utm_campaign": "dtc-spring-2026",
        "goal_leads": 300,
        "goal_conversions": 30,
        "created_by": "admin@demo.com",
        "created_at": datetime.now(timezone.utc).isoformat()
    },
    {
        "name": "Growth Webinar Series",
        "description": "Monthly webinar on growth systems — captures both B2B and B2C leads",
        "channel": "webinar",
        "lead_type": "both",
        "status": "active",
        "start_date": "2026-02-01",
        "end_date": "2026-06-30",
        "budget": 2000.0,
        "spend": 600.0,
        "target_audience": "Marketing leaders and founders looking to scale",
        "utm_source": "webinar",
        "utm_medium": "organic",
        "utm_campaign": "growth-webinar-2026",
        "goal_leads": 500,
        "goal_conversions": 50,
        "created_by": "admin@demo.com",
        "created_at": datetime.now(timezone.utc).isoformat()
    },
]
campaign_results = db["campaigns"].insert_many(campaigns)
campaign_ids = [str(cid) for cid in campaign_results.inserted_ids]
print(f"Seeded {len(campaigns)} campaigns")

# Leads
first_names = ["Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Drew", "Avery", "Blake", "Cameron", "Dakota", "Emery", "Finley", "Harper", "Jamie", "Kai", "Logan", "Mason", "Noah", "Olivia", "Parker", "Quinn", "Reese", "Sage", "Tyler", "Uma", "Val", "Wren", "Xander", "Yael", "Zara", "Aiden", "Brooke", "Chris", "Diana", "Ethan", "Faith", "Grace", "Henry", "Iris", "Jack", "Kira", "Leo", "Maya", "Nora", "Omar", "Priya", "Rosa", "Sam", "Tara"]
last_names = ["Anderson", "Brown", "Chen", "Davis", "Evans", "Foster", "Garcia", "Harris", "Ibrahim", "Johnson", "Kumar", "Lee", "Mitchell", "Nguyen", "O'Brien", "Patel", "Quinn", "Roberts", "Smith", "Thompson", "Usman", "Varma", "Wilson", "Xu", "Young", "Zhang", "Baker", "Clark", "Diaz", "Edwards", "Fisher", "Green", "Hall", "Ivanov", "Jones", "Khan", "Lopez", "Martin", "Nelson", "Owens", "Price", "Reed", "Scott", "Taylor", "Underwood", "Vasquez", "White", "Yang", "Zimmerman", "Adams"]
companies = ["TechFlow", "ScaleUp HQ", "DataDriven Co", "GrowthStack", "MarketPulse", "CloudNine Solutions", "RevOps Inc", "Pixel Perfect", "SaaS Metrics", "LeadGen Labs", "Funnel Pro", "ContentVista", "BrandSpark", "DigitalNest", "PipelinePro", "ConvertIQ", "EngageMore", "RetentionAI", "ChurnZero Plus", "Amplify Digital"]
industries = ["SaaS", "E-commerce", "Healthcare", "FinTech", "EdTech", "Real Estate", "Marketing Agency", "Consulting", "Manufacturing", "Retail"]
job_titles = ["CEO", "CTO", "VP of Growth", "Head of Marketing", "CMO", "Director of Sales", "Growth Lead", "Marketing Manager", "Founder", "Product Manager"]
channels = ["whatsapp", "email", "linkedin", "instagram", "facebook", "website_form", "cold_call", "referral", "webinar", "organic_search", "paid_ads"]
statuses = ["new", "contacted", "qualified", "unqualified", "proposal_sent", "negotiation", "won", "lost", "nurture"]
revenue_ranges = ["$0-$100K", "$100K-$500K", "$500K-$1M", "$1M-$5M", "$5M-$10M", "$10M+"]
cities = ["New York", "San Francisco", "London", "Mumbai", "Dubai", "Austin", "Chicago", "Toronto", "Berlin", "Singapore"]
countries = ["USA", "UK", "India", "UAE", "Canada", "Germany", "Singapore", "Australia"]
reps = ["sarah@demo.com", "james@demo.com", None]

leads_data = []
for i in range(50):
    is_b2b = random.random() > 0.4
    lead_type = "B2B" if is_b2b else "B2C"
    status = random.choice(statuses)
    score = random.randint(10, 95)
    tier = "hot" if score >= 70 else ("warm" if score >= 40 else "cold")
    
    days_ago = random.randint(0, 60)
    created = datetime.now(timezone.utc) - timedelta(days=days_ago)
    
    lead = {
        "lead_type": lead_type,
        "first_name": first_names[i],
        "last_name": last_names[i],
        "email": f"{first_names[i].lower()}.{last_names[i].lower()}@{random.choice(['gmail.com', 'outlook.com', 'company.io', 'work.co'])}",
        "phone": f"+1{random.randint(2000000000, 9999999999)}",
        "company_name": random.choice(companies) if is_b2b else None,
        "job_title": random.choice(job_titles) if is_b2b else None,
        "industry": random.choice(industries) if is_b2b else None,
        "revenue_range": random.choice(revenue_ranges) if is_b2b else None,
        "city": random.choice(cities),
        "state": None,
        "country": random.choice(countries),
        "source_channel": random.choice(channels),
        "campaign_id": random.choice(campaign_ids + [None, None]),
        "status": status,
        "icp_score": score,
        "icp_tier": tier,
        "icp_reasoning": [
            "Profile matches target demographics",
            f"{'Strong' if score > 60 else 'Moderate'} industry alignment",
            f"{'Decision-maker' if is_b2b and score > 50 else 'Individual contributor'} role"
        ],
        "assigned_to": random.choice(reps),
        "notes": random.choice([None, "Interested in growth audit", "Referred by existing client", "Saw our webinar", "Downloaded whitepaper"]),
        "tags": random.sample(["high-priority", "webinar-attendee", "demo-requested", "enterprise", "startup", "follow-up", "hot-lead"], k=random.randint(0, 3)),
        "custom_fields": {},
        "last_contacted_at": (created + timedelta(days=random.randint(1, 10))).isoformat() if status != "new" else None,
        "next_followup_at": (datetime.now(timezone.utc) + timedelta(days=random.randint(1, 14))).isoformat() if status in ["contacted", "qualified", "proposal_sent", "negotiation"] else None,
        "created_at": created.isoformat(),
        "updated_at": created.isoformat(),
        "created_by": "admin@demo.com",
    }
    leads_data.append(lead)

lead_results = db["leads"].insert_many(leads_data)
lead_ids = [str(lid) for lid in lead_results.inserted_ids]
print(f"Seeded {len(leads_data)} leads")

# Activities
activity_types = ["call", "email_sent", "email_received", "whatsapp_sent", "linkedin_message", "meeting_scheduled", "meeting_done", "proposal_sent", "note_added", "status_changed"]
activity_subjects = {
    "call": ["Discovery call", "Follow-up call", "Qualification call", "Demo call"],
    "email_sent": ["Introduction email", "Follow-up email", "Proposal email", "Thank you email"],
    "email_received": ["Reply received", "Question about pricing", "Meeting confirmation"],
    "whatsapp_sent": ["Quick follow-up", "Shared case study", "Meeting reminder"],
    "linkedin_message": ["Connection request", "InMail sent", "Post engagement"],
    "meeting_scheduled": ["Discovery meeting", "Demo session", "Strategy call"],
    "meeting_done": ["Discovery completed", "Demo delivered", "Proposal review"],
    "proposal_sent": ["Growth audit proposal", "Retainer proposal", "Sprint proposal"],
    "note_added": ["Internal note", "Client feedback", "Research notes"],
    "status_changed": ["Moved to qualified", "Moved to proposal sent", "Moved to won"],
}

activities_data = []
for i in range(120):
    lead_id = random.choice(lead_ids)
    act_type = random.choice(activity_types)
    days_ago = random.randint(0, 45)
    
    activity = {
        "lead_id": lead_id,
        "user_id": random.choice(["admin@demo.com", "sarah@demo.com", "james@demo.com"]),
        "activity_type": act_type,
        "subject": random.choice(activity_subjects[act_type]),
        "body": random.choice([None, "Had a great conversation about their growth challenges.", "Shared our case studies and they were impressed.", "Need to follow up next week.", "Budget discussion went well."]),
        "outcome": random.choice([None, "Positive", "Needs follow-up", "No response", "Interested"]),
        "duration_minutes": random.randint(15, 60) if act_type in ["call", "meeting_done"] else None,
        "metadata": {},
        "created_at": (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    }
    activities_data.append(activity)

db["activities"].insert_many(activities_data)
print(f"Seeded {len(activities_data)} activities")

# Pipelines
pipelines = [
    {"lead_type": "B2B", "stages": [
        {"stage_name": "New", "stage_order": 1, "probability": 10, "expected_close_days": 90},
        {"stage_name": "Contacted", "stage_order": 2, "probability": 20, "expected_close_days": 75},
        {"stage_name": "Qualified", "stage_order": 3, "probability": 40, "expected_close_days": 60},
        {"stage_name": "Proposal Sent", "stage_order": 4, "probability": 60, "expected_close_days": 30},
        {"stage_name": "Negotiation", "stage_order": 5, "probability": 80, "expected_close_days": 14},
        {"stage_name": "Won", "stage_order": 6, "probability": 100, "expected_close_days": 0},
        {"stage_name": "Lost", "stage_order": 7, "probability": 0, "expected_close_days": 0},
    ], "created_at": datetime.now(timezone.utc).isoformat()},
    {"lead_type": "B2C", "stages": [
        {"stage_name": "New", "stage_order": 1, "probability": 10, "expected_close_days": 30},
        {"stage_name": "Contacted", "stage_order": 2, "probability": 30, "expected_close_days": 21},
        {"stage_name": "Qualified", "stage_order": 3, "probability": 50, "expected_close_days": 14},
        {"stage_name": "Proposal Sent", "stage_order": 4, "probability": 70, "expected_close_days": 7},
        {"stage_name": "Won", "stage_order": 5, "probability": 100, "expected_close_days": 0},
        {"stage_name": "Lost", "stage_order": 6, "probability": 0, "expected_close_days": 0},
    ], "created_at": datetime.now(timezone.utc).isoformat()},
]
db["pipelines"].insert_many(pipelines)
print(f"Seeded {len(pipelines)} pipelines")

print("\n✓ Database seeded successfully!")
print("  Admin: admin@demo.com / Demo1234!")
print("  Sales Rep: sarah@demo.com / Demo1234!")
print("  Sales Rep: james@demo.com / Demo1234!")
