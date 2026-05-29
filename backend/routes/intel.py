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

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

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
from services.outreach_dispatch import dispatch_outreach

logger = logging.getLogger("intel_routes")
router = APIRouter(prefix="/api/intel", tags=["intel"])

# Collections we may need to read leads from. Pietential workspace uses
# pt_leads (string `id`); legacy ARIA leads live in `leads` with ObjectId.
pt_leads_col = db["pt_leads"]
leads_col = db["leads"]
intel_profiles_col = db["intel_profiles"]


# ─── iter134 — Scan all hot leads progress tracking ─────────────────────
# In-memory batch state keyed by batch_id. Survives only the lifetime of
# the backend process (which is fine — a fresh deploy abandons in-flight
# batches anyway). GC'd opportunistically when older than 1 hour.
_SCAN_BATCHES: Dict[str, Dict[str, Any]] = {}


def _gc_scan_batches():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    stale = []
    for bid, b in _SCAN_BATCHES.items():
        try:
            ts = b.get("finished_at") or b.get("started_at")
            if ts and datetime.fromisoformat(ts.replace("Z", "+00:00")) < cutoff:
                stale.append(bid)
        except Exception:
            stale.append(bid)
    for bid in stale:
        _SCAN_BATCHES.pop(bid, None)


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


class ComposeAndSendRequest(ComposeRequest):
    auto_send: bool = Field(default=True, description="If false, returns the composed message without sending.")


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


# ─── POST /api/intel/scan-hot ───────────────────────────────────────────
# Batch action invoked from the Lead Inbox top bar. Queues an intel scan
# for every lead in the active tenant whose ICP score (or tier) clears
# the configured threshold. Returns the candidate count immediately and
# fires the actual crawls in the background — the founder sees results
# trickle into the Intel tab as each scan finishes.
class ScanHotRequest(BaseModel):
    min_icp_score: int = Field(default=80, ge=0, le=100, description="ICP score floor. Default 80 ≈ 'hot' leads.")
    refresh: bool = Field(default=False, description="If true, re-scan even leads that already have a cached profile.")
    max_leads: int = Field(default=50, ge=1, le=200, description="Hard cap so a single click cannot blow the crawl budget.")


@router.post("/scan-hot")
async def scan_hot_leads(
    body: ScanHotRequest,
    current_user: dict = Depends(get_current_user),
):
    """Find every hot lead in the active tenant + queue intel scans for
    each one. Returns the queued list synchronously; crawls run in the
    background so the request returns instantly.
    """
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Active tenant required")

    # Pull candidates from both lead stores (pt_leads + legacy leads)
    # so the batch covers Pietential workspaces too.
    candidates: List[Dict[str, Any]] = []

    def _add(doc: Dict[str, Any], src: str):
        if not doc:
            return
        candidates.append({
            "lead_id": str(doc.get("id") or doc.get("_id")),
            "name": (f"{doc.get('first_name', '')} {doc.get('last_name', '')}").strip() or doc.get("name") or doc.get("email") or "Lead",
            "icp_score": doc.get("icp_score") or 0,
            "icp_tier": doc.get("icp_tier"),
            "source": src,
        })

    # Legacy CRM leads — sort by score desc + apply cap.
    for d in leads_col.find(
        {
            "tenant_id": tenant_id,
            "$or": [
                {"icp_score": {"$gte": body.min_icp_score}},
                {"icp_tier": "hot"},
            ],
        },
        {"_id": 1, "id": 1, "first_name": 1, "last_name": 1, "name": 1, "email": 1, "icp_score": 1, "icp_tier": 1},
    ).sort([("icp_score", -1)]).limit(body.max_leads):
        _add(d, "legacy")

    # Pietential pt_leads — covers Pietential workspaces.
    remaining = max(0, body.max_leads - len(candidates))
    if remaining > 0:
        for d in pt_leads_col.find(
            {
                "tenant_id": tenant_id,
                "$or": [
                    {"icp_score": {"$gte": body.min_icp_score}},
                    {"icp_tier": "hot"},
                ],
            },
            {"_id": 0, "id": 1, "first_name": 1, "last_name": 1, "name": 1, "email": 1, "icp_score": 1, "icp_tier": 1},
        ).sort([("icp_score", -1)]).limit(remaining):
            _add(d, "pt")

    if not candidates:
        return {"queued": 0, "leads": [], "message": "No hot leads matched. Try lowering the score threshold."}

    # iter134 — track progress so the UI can poll for a live "X / N done" toast.
    batch_id = uuid.uuid4().hex
    _SCAN_BATCHES[batch_id] = {
        "tenant_id": tenant_id,
        "total": len(candidates),
        "completed": 0,
        "failed": 0,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "leads": [{"lead_id": c["lead_id"], "name": c["name"], "status": "pending"} for c in candidates],
    }
    # Garbage-collect stale batches (>1h) so the in-memory dict can't grow.
    _gc_scan_batches()

    # Fire each scan in the background. Failures (missing creds, budget
    # exceeded) are logged but never block the response — the Intel tab
    # surfaces per-lead errors when the founder opens that lead.
    async def _run_one(lead_id: str):
        ok = True
        try:
            lead = _load_lead(tenant_id, lead_id)
            crawl = await crawl_prospect(
                tenant_id=tenant_id, lead_id=lead_id,
                first_name=lead["first_name"], last_name=lead["last_name"],
                email=lead["email"], company_name=lead["company"],
                company_domain=lead["domain"], linkedin_url=lead["linkedin_url"],
                industry=lead["industry"],
            )
            await synthesise_intel(
                tenant_id=tenant_id, lead_id=lead_id,
                lead_meta={
                    "name": lead["name"], "first_name": lead["first_name"],
                    "company": lead["company"] or lead["domain"],
                    "domain": lead["domain"], "icp": lead["icp"],
                },
                crawl=crawl,
            )
        except Exception as e:
            ok = False
            logger.warning("[scan-hot] %s failed: %s", lead_id, str(e)[:160])
        finally:
            batch = _SCAN_BATCHES.get(batch_id)
            if batch:
                if ok:
                    batch["completed"] += 1
                else:
                    batch["failed"] += 1
                for row in batch["leads"]:
                    if row["lead_id"] == lead_id:
                        row["status"] = "done" if ok else "failed"
                        break
                if batch["completed"] + batch["failed"] >= batch["total"]:
                    batch["finished_at"] = datetime.now(timezone.utc).isoformat()

    # Detached background tasks — survives the response.
    for c in candidates:
        asyncio.create_task(_run_one(c["lead_id"]))

    return {
        "queued": len(candidates),
        "leads": candidates,
        "threshold": body.min_icp_score,
        "batch_id": batch_id,
        "message": f"Queued intel scans for {len(candidates)} hot lead(s). Results appear in each lead's Intel tab as they complete.",
    }


# ─── GET /api/intel/scan-hot/status/{batch_id} ──────────────────────────
# Polled by the Scan all hot leads toast so it can show "12/28 done" and
# auto-dismiss when the batch finishes.
@router.get("/scan-hot/status/{batch_id}")
async def scan_hot_status(batch_id: str, current_user: dict = Depends(get_current_user)):
    batch = _SCAN_BATCHES.get(batch_id)
    if not batch or batch.get("tenant_id") != current_user.get("tenant_id"):
        raise HTTPException(status_code=404, detail="Batch not found")
    total = batch["total"]
    completed = batch["completed"]
    failed = batch["failed"]
    done = completed + failed
    return {
        "batch_id": batch_id,
        "total": total,
        "completed": completed,
        "failed": failed,
        "in_progress": max(0, total - done),
        "progress_pct": int((done / total) * 100) if total else 100,
        "is_finished": done >= total,
        "started_at": batch["started_at"],
        "finished_at": batch["finished_at"],
    }


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


# ─── POST /api/intel/{lead_id}/compose-and-send ─────────────────────────
@router.post("/{lead_id}/compose-and-send")
async def compose_and_send(
    lead_id: str,
    body: ComposeAndSendRequest,
    current_user: dict = Depends(get_current_user),
):
    """Closes the loop: compose via Claude, then dispatch through the
    right provider (Resend / WhatsApp / LinkedIn). Returns both the
    composed message and the send result so the UI can show what went
    out."""
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
    composed = await compose_message(
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

    if not body.auto_send:
        return {"composed": composed, "dispatch": None}

    dispatch = await dispatch_outreach(
        tenant_id=tenant_id,
        lead_id=lead_id,
        channel=body.channel,
        composed=composed,
        actor_user_id=current_user.get("email"),
    )
    return {"composed": composed, "dispatch": dispatch}


# ─── POST /api/intel/batch/hot-leads ────────────────────────────────────
class BatchHotLeadsRequest(BaseModel):
    stages: List[str] = Field(default_factory=lambda: ["hot", "engaged", "session_pilot"])
    min_score: int = Field(default=70, description="Lower bound on lead score.")
    limit: int = Field(default=25, ge=1, le=100, description="Cap per run.")
    skip_existing: bool = Field(default=True, description="Skip leads already synthesised.")


@router.post("/batch/hot-leads")
async def batch_intel_hot_leads(
    body: BatchHotLeadsRequest,
    current_user: dict = Depends(get_current_user),
):
    """One-click enrichment for every hot lead in the workspace.

    Iterates pt_leads matching the stage/score filters, runs crawl +
    Claude synthesis on each (sequentially to respect Claude rate limits),
    and returns a per-lead status array. Skips leads with an existing
    profile unless `skip_existing=False`.

    Failure of any single lead does NOT abort the batch — errors are
    collected and returned so the founder can fix and retry.
    """
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Active tenant required")

    # Build query for pt_leads (Pietential workspace). Fall back to legacy
    # `leads` collection only if pt_leads is empty for this tenant.
    query: Dict[str, Any] = {"tenant_id": tenant_id}
    if body.stages:
        query["stage"] = {"$in": body.stages}
    if body.min_score is not None:
        query["score"] = {"$gte": int(body.min_score)}

    candidates = list(
        db["pt_leads"]
        .find(query, {"_id": 0})
        .sort("score", -1)
        .limit(body.limit)
    )

    # Filter out leads that already have a profile if requested
    if body.skip_existing and candidates:
        existing_ids = {
            d["lead_id"]
            for d in db["intel_profiles"].find(
                {
                    "tenant_id": tenant_id,
                    "lead_id": {"$in": [c["id"] for c in candidates]},
                },
                {"_id": 0, "lead_id": 1},
            )
        }
        candidates = [c for c in candidates if c["id"] not in existing_ids]

    if not candidates:
        return {
            "tenant_id": tenant_id,
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
            "skipped_existing": body.skip_existing,
            "results": [],
            "message": "No hot leads needed enrichment.",
        }

    results: List[Dict[str, Any]] = []
    succeeded = failed = 0

    for lead_doc in candidates:
        lead_id = lead_doc.get("id")
        email = (lead_doc.get("email") or "").strip()
        domain = email.split("@")[1].lower() if "@" in email else None
        first = lead_doc.get("first_name") or "there"
        last = lead_doc.get("last_name") or ""
        company = lead_doc.get("company_name") or lead_doc.get("company")

        entry: Dict[str, Any] = {
            "lead_id": lead_id,
            "name": f"{first} {last}".strip() or email,
            "company": company,
            "status": "pending",
        }
        try:
            crawl = await crawl_prospect(
                tenant_id=tenant_id,
                lead_id=lead_id,
                first_name=first,
                last_name=last,
                email=email,
                company_name=company,
                company_domain=domain,
                linkedin_url=lead_doc.get("linkedin_url"),
                industry=lead_doc.get("industry"),
            )
            profile = await synthesise_intel(
                tenant_id=tenant_id,
                lead_id=lead_id,
                lead_meta={
                    "name": entry["name"],
                    "first_name": first,
                    "company": company or domain,
                    "domain": domain,
                    "icp": lead_doc.get("icp_fit") or lead_doc.get("icp_tier"),
                },
                crawl=crawl,
            )
            entry.update({
                "status": "ok",
                "fit_score": profile.get("fit_score", 0),
                "signal_count": len(profile.get("signals") or []),
                "risk_count": len(profile.get("risk_flags") or []),
            })
            succeeded += 1
        except MissingCredential as e:
            # No keys configured — abort the batch since every lead will fail.
            return {
                "tenant_id": tenant_id,
                "processed": len(results),
                "succeeded": succeeded,
                "failed": failed,
                "aborted": True,
                "reason": str(e),
                "results": results,
            }
        except CrawlLimitExceeded as e:
            entry.update({"status": "skipped", "reason": str(e)})
            failed += 1
        except Exception as e:  # noqa: BLE001 — per-lead isolation
            logger.exception("intel_routes: batch failure for lead=%s", lead_id)
            entry.update({"status": "error", "reason": str(e)[:200]})
            failed += 1
        results.append(entry)

        # Tiny cooperative yield so we don't monopolise the event loop
        await asyncio.sleep(0)

    return {
        "tenant_id": tenant_id,
        "processed": len(results),
        "succeeded": succeeded,
        "failed": failed,
        "skipped_existing": body.skip_existing,
        "results": results,
    }
