"""ARIA — Batch 4 Intelligence Routes.

Multi-platform crawl + Claude synthesis + outreach playbook + channel
composer. Mounted under `/api/intel/*`.

All endpoints are tenant-scoped via `get_current_user`. Crawl credentials
are pulled from the encrypted `integration_configs` collection set up by
the Batch 1 Universal OAuth UI — never from `.env`.

Endpoints
─────────
  POST  /api/intel/{lead_id}/research   — crawl + synthesise
  GET   /api/intel/{lead_id}            — fetch stored intel profile
  POST  /api/intel/{lead_id}/playbook   — generate outreach playbook
  POST  /api/intel/{lead_id}/compose    — channel-adaptive message
  GET   /api/intel/{lead_id}/budget     — crawl-call budget snapshot
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import db, get_current_user
from services.crawl_service import (
    crawl_prospect,
    get_budget_snapshot,
    MissingCredential,
    CrawlLimitExceeded,
)
from services.intel_service import (
    synthesise_intel,
    generate_playbook,
    compose_message,
)

logger = logging.getLogger("intel_routes")
router = APIRouter(prefix="/api/intel", tags=["intel"])

# Collections we may need to read leads from. Pietential workspace uses
# pt_leads (string `id`); legacy ARIA leads live in `leads` with ObjectId.
pt_leads_col = db["pt_leads"]
leads_col = db["leads"]
intel_profiles_col = db["intel_profiles"]


# ─── Lead resolution helper ─────────────────────────────────────────────
def _load_lead(tenant_id: str, lead_id: str) -> Dict[str, Any]:
    """Look up a lead across the pietential + legacy collections.
    Returns a normalised dict with the fields the crawler needs."""
    doc = pt_leads_col.find_one({"id": lead_id, "tenant_id": tenant_id}, {"_id": 0})
    src = "pt"
    if not doc:
        # Fallback to legacy CRM leads. Tolerate string OR ObjectId in `_id`.
        from bson import ObjectId  # local import to avoid global cost
        try:
            doc = leads_col.find_one({"_id": ObjectId(lead_id), "tenant_id": tenant_id})
        except Exception:
            doc = None
        if doc:
            doc = {k: v for k, v in doc.items() if k != "_id"}
            src = "legacy"
    if not doc:
        raise HTTPException(status_code=404, detail="Lead not found in this workspace")

    first = doc.get("first_name") or (doc.get("name") or "").split()[0] if doc.get("name") else doc.get("first_name") or ""
    last = doc.get("last_name") or ""
    email = (doc.get("email") or "").strip()
    domain = email.split("@")[1].lower() if "@" in email else (doc.get("company_domain") or None)
    company = doc.get("company_name") or doc.get("company") or doc.get("employer") or None
    linkedin_url = doc.get("linkedin_url") or doc.get("linkedin")
    return {
        "_source": src,
        "lead_id": lead_id,
        "first_name": first or "there",
        "last_name": last,
        "name": (f"{first} {last}".strip()) or doc.get("name") or email or "Prospect",
        "email": email,
        "company": company,
        "domain": domain,
        "linkedin_url": linkedin_url,
        "industry": doc.get("industry"),
        "icp": doc.get("icp_fit") or doc.get("icp_tier"),
        "raw": doc,
    }


# ─── Schemas ────────────────────────────────────────────────────────────
class ResearchRequest(BaseModel):
    refresh: bool = Field(default=False, description="If true, ignore cached intel and re-crawl.")


class PlaybookRequest(BaseModel):
    refresh: bool = False


class ComposeRequest(BaseModel):
    channel: str = Field(default="email", description="whatsapp | email | linkedin")
    user_steer: Optional[str] = Field(default=None, description="Founder note to bias the message.")


# ─── POST /api/intel/{lead_id}/research ─────────────────────────────────
@router.post("/{lead_id}/research")
async def research_lead(
    lead_id: str,
    body: ResearchRequest,
    current_user: dict = Depends(get_current_user),
):
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Active tenant required")

    # Cache hit (unless refresh)
    if not body.refresh:
        existing = intel_profiles_col.find_one(
            {"tenant_id": tenant_id, "lead_id": lead_id},
            {"_id": 0},
        )
        if existing and existing.get("signals"):
            return {"cached": True, "profile": existing}

    lead = _load_lead(tenant_id, lead_id)

    try:
        crawl = await crawl_prospect(
            tenant_id=tenant_id,
            lead_id=lead_id,
            first_name=lead["first_name"],
            last_name=lead["last_name"],
            email=lead["email"],
            company_name=lead["company"],
            company_domain=lead["domain"],
            linkedin_url=lead["linkedin_url"],
            industry=lead["industry"],
        )
    except MissingCredential as e:
        raise HTTPException(status_code=503, detail=str(e))
    except CrawlLimitExceeded as e:
        raise HTTPException(status_code=429, detail=str(e))

    profile = await synthesise_intel(
        tenant_id=tenant_id,
        lead_id=lead_id,
        lead_meta={
            "name": lead["name"],
            "first_name": lead["first_name"],
            "company": lead["company"] or lead["domain"],
            "domain": lead["domain"],
            "icp": lead["icp"],
        },
        crawl=crawl,
    )
    return {"cached": False, "profile": profile, "crawl_meta": profile.get("crawl_meta")}


# ─── GET /api/intel/{lead_id} ───────────────────────────────────────────
@router.get("/{lead_id}")
async def get_intel(lead_id: str, current_user: dict = Depends(get_current_user)):
    tenant_id = current_user.get("tenant_id")
    doc = intel_profiles_col.find_one(
        {"tenant_id": tenant_id, "lead_id": lead_id}, {"_id": 0}
    )
    if not doc:
        return {"profile": None, "exists": False}
    return {"profile": doc, "exists": True}


# ─── POST /api/intel/{lead_id}/playbook ─────────────────────────────────
@router.post("/{lead_id}/playbook")
async def build_playbook(
    lead_id: str,
    body: PlaybookRequest,
    current_user: dict = Depends(get_current_user),
):
    tenant_id = current_user.get("tenant_id")
    profile = intel_profiles_col.find_one(
        {"tenant_id": tenant_id, "lead_id": lead_id}, {"_id": 0}
    )
    if not profile:
        raise HTTPException(
            status_code=400,
            detail="No intel profile yet — call POST /api/intel/{lead_id}/research first.",
        )

    if not body.refresh and profile.get("playbook"):
        return {"cached": True, "playbook": profile["playbook"]}

    lead = _load_lead(tenant_id, lead_id)
    playbook = await generate_playbook(
        tenant_id=tenant_id,
        lead_id=lead_id,
        lead_meta={
            "name": lead["name"],
            "first_name": lead["first_name"],
            "company": lead["company"] or lead["domain"],
        },
        profile=profile,
    )
    return {"cached": False, "playbook": playbook}


# ─── POST /api/intel/{lead_id}/compose ──────────────────────────────────
@router.post("/{lead_id}/compose")
async def compose(
    lead_id: str,
    body: ComposeRequest,
    current_user: dict = Depends(get_current_user),
):
    tenant_id = current_user.get("tenant_id")
    profile = intel_profiles_col.find_one(
        {"tenant_id": tenant_id, "lead_id": lead_id}, {"_id": 0}
    )
    if not profile:
        raise HTTPException(
            status_code=400,
            detail="No intel profile yet — call POST /api/intel/{lead_id}/research first.",
        )
    lead = _load_lead(tenant_id, lead_id)
    return await compose_message(
        tenant_id=tenant_id,
        lead_id=lead_id,
        channel=body.channel,
        lead_meta={
            "name": lead["name"],
            "first_name": lead["first_name"],
            "company": lead["company"] or lead["domain"],
        },
        profile=profile,
        user_steer=body.user_steer,
    )


# ─── GET /api/intel/{lead_id}/budget ────────────────────────────────────
@router.get("/{lead_id}/budget")
async def budget(lead_id: str, current_user: dict = Depends(get_current_user)):
    tenant_id = current_user.get("tenant_id")
    return get_budget_snapshot(tenant_id, lead_id)
