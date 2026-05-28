"""iter108 — ACTION 3 (continued): Demo data seeder.

`POST /api/admin/load-demo-data` — seeds a workspace with 25 realistic leads
spanning every status, ICP tier, country, channel, and industry combination
the rest of the product knows how to render. The 25-row fixture is locked —
adding or reordering rows is fine but each row needs the same shape.

By default the endpoint refuses to run if the workspace already has leads.
`?force=true` deletes existing demo leads (those tagged `metadata.demo=true`)
and reseeds — real customer leads are NEVER touched.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from random import choice, randint

from fastapi import APIRouter, Depends

from deps import get_current_user, leads_collection

router = APIRouter(tags=["iter108-demo-seeder"])


DEMO_LEADS_FIXTURE = [
    {"first_name": "Quinn", "last_name": "Varma", "email": "quinn@apexsaas.io", "phone": "+919876512301", "company_name": "ApexSaaS", "job_title": "Head of Growth", "industry": "B2B SaaS", "country": "India", "source_channel": "linkedin", "lead_type": "B2B", "icp_score": 93, "status": "qualified"},
    {"first_name": "Amelia", "last_name": "Cordeiro", "email": "amelia@northglow.co", "phone": "+447700912334", "company_name": "Northglow Realty", "job_title": "Founder", "industry": "Real Estate", "country": "United Kingdom", "source_channel": "meta_ads", "lead_type": "B2B", "icp_score": 82, "status": "contacted"},
    {"first_name": "Diego", "last_name": "Fernandes", "email": "diego@finchedu.mx", "phone": "+525512345678", "company_name": "FinchEdu", "job_title": "COO", "industry": "Education", "country": "Mexico", "source_channel": "google_ads", "lead_type": "B2B", "icp_score": 71, "status": "new"},
    {"first_name": "Priya", "last_name": "Menon", "email": "priya@stratosconsult.in", "phone": "+918888412290", "company_name": "Stratos Consult", "job_title": "Partner", "industry": "Consulting", "country": "India", "source_channel": "website_form", "lead_type": "B2B", "icp_score": 88, "status": "proposal_sent"},
    {"first_name": "Tomás", "last_name": "Silva", "email": "tomas@vitabra.com", "phone": "+5511987650091", "company_name": "VitaBra", "job_title": "CMO", "industry": "Health Tech", "country": "Brazil", "source_channel": "linkedin", "lead_type": "B2B", "icp_score": 65, "status": "contacted"},
    {"first_name": "Hannah", "last_name": "Lipton", "email": "hannah@lifteq.io", "phone": "+15035551122", "company_name": "Lift EQ", "job_title": "CEO", "industry": "B2B SaaS", "country": "USA", "source_channel": "referral", "lead_type": "B2B", "icp_score": 95, "status": "won"},
    {"first_name": "Aarav", "last_name": "Khanna", "email": "aarav@gritlabs.in", "phone": "+919812346678", "company_name": "GritLabs", "job_title": "Owner", "industry": "Agency", "country": "India", "source_channel": "whatsapp", "lead_type": "B2B", "icp_score": 78, "status": "negotiation"},
    {"first_name": "Sofia", "last_name": "Russo", "email": "sofia@nimbushotel.it", "phone": "+393311234455", "company_name": "Nimbus Hotel Group", "job_title": "Director", "industry": "Hospitality", "country": "Italy", "source_channel": "meta_ads", "lead_type": "B2B", "icp_score": 58, "status": "qualified"},
    {"first_name": "Kwame", "last_name": "Boateng", "email": "kwame@savannapay.gh", "phone": "+233244781001", "company_name": "SavannaPay", "job_title": "CEO", "industry": "FinTech", "country": "Ghana", "source_channel": "linkedin", "lead_type": "B2B", "icp_score": 73, "status": "call_booked"},
    {"first_name": "Lin", "last_name": "Wei", "email": "lin@orchidwine.sg", "phone": "+6591238877", "company_name": "Orchid Wines", "job_title": "Marketing Lead", "industry": "D2C", "country": "Singapore", "source_channel": "google_ads", "lead_type": "B2B", "icp_score": 42, "status": "contacted"},
    {"first_name": "Ravi", "last_name": "Iyer", "email": "ravi@mosaicedtech.in", "phone": "+919900112233", "company_name": "Mosaic EdTech", "job_title": "Founder", "industry": "EdTech", "country": "India", "source_channel": "linkedin", "lead_type": "B2B", "icp_score": 84, "status": "qualified"},
    {"first_name": "Eva", "last_name": "Holm", "email": "eva@nordfit.no", "phone": "+4798765432", "company_name": "NordFit", "job_title": "Co-founder", "industry": "Wellness", "country": "Norway", "source_channel": "referral", "lead_type": "B2B", "icp_score": 67, "status": "new"},
    {"first_name": "Jamal", "last_name": "Ahmed", "email": "jamal@stridelearning.ae", "phone": "+971501234567", "company_name": "Stride Learning", "job_title": "Director", "industry": "EdTech", "country": "UAE", "source_channel": "webinar", "lead_type": "B2B", "icp_score": 81, "status": "contacted"},
    {"first_name": "Mira", "last_name": "Saito", "email": "mira@bonsaicx.jp", "phone": "+819011223344", "company_name": "Bonsai CX", "job_title": "Head of Sales", "industry": "B2B SaaS", "country": "Japan", "source_channel": "linkedin", "lead_type": "B2B", "icp_score": 90, "status": "call_booked"},
    {"first_name": "Rafael", "last_name": "Costa", "email": "rafael@sereia.com.br", "phone": "+5521911223344", "company_name": "Sereia Surf Co.", "job_title": "Owner", "industry": "D2C", "country": "Brazil", "source_channel": "meta_ads", "lead_type": "B2C", "icp_score": 36, "status": "unqualified"},
    {"first_name": "Olivia", "last_name": "Nairn", "email": "olivia@hearthrealty.uk", "phone": "+447789998877", "company_name": "Hearth Realty", "job_title": "Director", "industry": "Real Estate", "country": "United Kingdom", "source_channel": "website_form", "lead_type": "B2C", "icp_score": 55, "status": "contacted"},
    {"first_name": "Niko", "last_name": "Petrov", "email": "niko@arctigear.fi", "phone": "+358401234567", "company_name": "ArctiGear", "job_title": "CMO", "industry": "Outdoor / D2C", "country": "Finland", "source_channel": "linkedin", "lead_type": "B2B", "icp_score": 62, "status": "qualified"},
    {"first_name": "Lana", "last_name": "Stojkovic", "email": "lana@solvis.rs", "phone": "+381641234567", "company_name": "Solvis Consulting", "job_title": "Partner", "industry": "Consulting", "country": "Serbia", "source_channel": "referral", "lead_type": "B2B", "icp_score": 76, "status": "proposal_sent"},
    {"first_name": "Marcus", "last_name": "Adesina", "email": "marcus@palmtech.ng", "phone": "+2348012345678", "company_name": "PalmTech", "job_title": "Founder", "industry": "FinTech", "country": "Nigeria", "source_channel": "google_ads", "lead_type": "B2B", "icp_score": 70, "status": "new"},
    {"first_name": "Yara", "last_name": "Habib", "email": "yara@cedarluxe.lb", "phone": "+9613123456", "company_name": "Cedar Luxe", "job_title": "Director", "industry": "Real Estate", "country": "Lebanon", "source_channel": "meta_ads", "lead_type": "B2C", "icp_score": 48, "status": "lost"},
    {"first_name": "Carlos", "last_name": "Mendes", "email": "carlos@harborlogistics.br", "phone": "+5511933221100", "company_name": "Harbor Logistics", "job_title": "Founder", "industry": "Manufacturing", "country": "Brazil", "source_channel": "referral", "lead_type": "B2B", "icp_score": 68, "status": "qualified"},
    {"first_name": "Iris", "last_name": "Becker", "email": "iris@rubyclinics.de", "phone": "+4915112233445", "company_name": "Ruby Clinics", "job_title": "Practice Manager", "industry": "Healthcare", "country": "Germany", "source_channel": "meta_ads", "lead_type": "B2C", "icp_score": 45, "status": "lost"},
    {"first_name": "Ben", "last_name": "Sokolov", "email": "ben@stackbloom.com", "phone": "+14157771010", "company_name": "Stackbloom", "job_title": "Co-founder", "industry": "B2B SaaS", "country": "USA", "source_channel": "webinar", "lead_type": "B2B", "icp_score": 92, "status": "call_booked"},
    {"first_name": "Anu", "last_name": "Reddy", "email": "anu@petalboutique.in", "phone": "+918111222333", "company_name": "Petal Boutique", "job_title": "Owner", "industry": "D2C", "country": "India", "source_channel": "whatsapp", "lead_type": "B2C", "icp_score": 50, "status": "contacted"},
]


@router.post("/api/admin/load-demo-data")
async def load_demo_data(force: bool = False, current_user: dict = Depends(get_current_user)):
    """Seed 25 realistic leads. By default only runs if the leads collection
    is empty. Pass `?force=true` to delete existing `metadata.demo=true` rows
    and reseed (real customer leads are never touched)."""
    if force:
        result = leads_collection.delete_many({"metadata.demo": True})
        print(f"[DemoSeed] Deleted {result.deleted_count} existing demo leads")
    else:
        existing = leads_collection.count_documents({})
        if existing > 0:
            return {"seeded": 0, "skipped": True, "reason": f"Workspace already has {existing} leads. Use force=true to reseed."}

    now = datetime.now(timezone.utc)
    inserted = 0
    for fixture in DEMO_LEADS_FIXTURE:
        days_ago = randint(0, 30)
        created_at = (now - timedelta(days=days_ago)).isoformat()
        last_contact_days = randint(0, 14) if fixture["status"] != "new" else None
        last_contacted = (now - timedelta(days=last_contact_days)).isoformat() if last_contact_days is not None else None
        offset_days = choice([-5, -3, -1, 0, 0, 1, 2, 4, 7])
        next_followup = (now + timedelta(days=offset_days)).isoformat() if fixture["status"] not in ["won", "lost", "unqualified"] else None
        icp = fixture["icp_score"]
        tier = "hot" if icp >= 80 else "warm" if icp >= 50 else "cold" if icp >= 20 else "low_fit"
        deal_value = (
            randint(2000, 25000) * 100
            if fixture["status"] in ["proposal_sent", "negotiation", "won", "call_booked", "qualified"]
            else None
        )
        doc = {
            **fixture,
            "lead_temperature": tier,
            "icp_tier": "A" if tier == "hot" else "B" if tier == "warm" else "C" if tier == "cold" else "D",
            "deal_value": deal_value,
            "last_contacted_at": last_contacted,
            "next_followup_at": next_followup,
            "aria_state": "AWAITING_FIRST_TOUCH",
            "aria_handed_off": False,
            "created_at": created_at,
            "updated_at": created_at,
            "campaign_name": choice(["Q1 Outbound", "LinkedIn 2026", "Webinar Funnel", "Inbound", "Referral Engine"]),
            "metadata": {"demo": True, "industry": fixture.get("industry")},
        }
        leads_collection.insert_one(doc)
        inserted += 1

    return {"seeded": inserted, "skipped": False}
