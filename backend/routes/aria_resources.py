"""Iter100 — Aria Resource Library.

A tenant-scoped library of sales collateral (PDFs, decks, case studies,
one-pagers, blog links) that Aria can attach to outbound based on the
lead's ICP and the resource's tags.

Model (`aria_resources` collection)
────────────────────────────────────
  id              str       — uuid4
  tenant_id       str
  title           str
  description     str
  category        str       — case_study | deck | one_pager | blog | demo | other
  type            "file" | "url"
  url             Optional[str]
  file_id         Optional[str]  — stored under /app/backend/uploads
  file_name       Optional[str]
  size            Optional[int]
  tags            list[str]
  target_icp_ids  list[str]      — IDs from settings.aria_training_profile.data.icp_profiles
  created_at      ISO
  updated_at      ISO
  archived        bool
  send_count      int            — incremented when ARIA attaches it
"""
from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from deps import db
from routes.tenants import get_active_tenant, require_tenant_role

router = APIRouter(prefix="/api/aria/resources", tags=["aria-resources"])

resources_col = db["aria_resources"]
tenants_col = db["tenants"]
leads_col = db["leads"]

UPLOADS_DIR = "/app/backend/uploads/aria_resources"
os.makedirs(UPLOADS_DIR, exist_ok=True)

MAX_FILE_BYTES = 25 * 1024 * 1024  # 25 MB
ALLOWED_CATEGORIES = ("case_study", "deck", "one_pager", "blog", "demo", "other")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_filename(name: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9._-]", "_", (name or "file"))[:80]
    return f"{uuid.uuid4().hex[:10]}__{base}"


def _serialize(r: Dict[str, Any]) -> Dict[str, Any]:
    r = dict(r)
    r.pop("_id", None)
    # Public file_url for clients
    if r.get("file_id"):
        r["file_url"] = f"/api/aria/resources/file/{r['file_id']}"
    return r


# ─── Schemas ─────────────────────────────────────────────────────────────
class ResourceCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    category: str = Field(default="other")
    type: str = Field(default="url")  # "url" or "file"
    url: Optional[str] = Field(default=None, max_length=2000)
    file_id: Optional[str] = None
    file_name: Optional[str] = None
    size: Optional[int] = None
    tags: List[str] = Field(default_factory=list)
    target_icp_ids: List[str] = Field(default_factory=list)


class ResourceUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=1000)
    category: Optional[str] = None
    url: Optional[str] = Field(default=None, max_length=2000)
    tags: Optional[List[str]] = None
    target_icp_ids: Optional[List[str]] = None
    archived: Optional[bool] = None


def _validate_category(c: Optional[str]) -> str:
    if c is None:
        return "other"
    if c not in ALLOWED_CATEGORIES:
        raise HTTPException(400, f"category must be one of {ALLOWED_CATEGORIES}")
    return c


# ─── CRUD ────────────────────────────────────────────────────────────────
@router.get("")
async def list_resources(
    tenant: dict = Depends(get_active_tenant),
    include_archived: bool = False,
    category: Optional[str] = None,
    tag: Optional[str] = None,
):
    """List resources for the active tenant.

    Filters: `include_archived`, `category`, `tag` (single-tag match).
    """
    q: Dict[str, Any] = {"tenant_id": tenant["id"]}
    if not include_archived:
        q["archived"] = {"$ne": True}
    if category:
        q["category"] = category
    if tag:
        q["tags"] = tag
    rows = list(resources_col.find(q, {"_id": 0}).sort("created_at", -1))
    return {"ok": True, "count": len(rows), "resources": [_serialize(r) for r in rows]}


@router.post("")
async def create_resource(
    payload: ResourceCreate,
    tenant: dict = Depends(require_tenant_role(["owner", "admin", "master_admin"])),
):
    """Create a new resource. For URL-type just paste the link;
    for file-type, upload first via `/upload` then pass the returned
    `file_id` here.
    """
    category = _validate_category(payload.category)
    if payload.type not in ("url", "file"):
        raise HTTPException(400, "type must be 'url' or 'file'")
    if payload.type == "url" and not payload.url:
        raise HTTPException(400, "url required for url-type resources")
    if payload.type == "file" and not payload.file_id:
        raise HTTPException(400, "file_id required for file-type resources (upload first)")

    doc = {
        "id":              str(uuid.uuid4()),
        "tenant_id":       tenant["id"],
        "title":           payload.title.strip(),
        "description":     payload.description.strip(),
        "category":        category,
        "type":            payload.type,
        "url":             payload.url,
        "file_id":         payload.file_id,
        "file_name":       payload.file_name,
        "size":            payload.size,
        "tags":            [t.strip().lower() for t in (payload.tags or []) if t.strip()],
        "target_icp_ids":  payload.target_icp_ids or [],
        "created_at":      _now(),
        "updated_at":      _now(),
        "archived":        False,
        "send_count":      0,
    }
    resources_col.insert_one(doc)
    return {"ok": True, "resource": _serialize(doc)}


@router.patch("/{resource_id}")
async def update_resource(
    resource_id: str,
    payload: ResourceUpdate,
    tenant: dict = Depends(require_tenant_role(["owner", "admin", "master_admin"])),
):
    existing = resources_col.find_one({"id": resource_id, "tenant_id": tenant["id"]}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Resource not found")
    updates: Dict[str, Any] = {"updated_at": _now()}
    data = payload.model_dump(exclude_unset=True)
    if "category" in data:
        updates["category"] = _validate_category(data["category"])
    for k in ("title", "description", "url", "archived"):
        if k in data:
            updates[k] = data[k]
    if "tags" in data:
        updates["tags"] = [t.strip().lower() for t in (data["tags"] or []) if t.strip()]
    if "target_icp_ids" in data:
        updates["target_icp_ids"] = data["target_icp_ids"] or []
    resources_col.update_one({"id": resource_id, "tenant_id": tenant["id"]}, {"$set": updates})
    fresh = resources_col.find_one({"id": resource_id, "tenant_id": tenant["id"]}, {"_id": 0})
    return {"ok": True, "resource": _serialize(fresh)}


@router.delete("/{resource_id}")
async def delete_resource(
    resource_id: str,
    tenant: dict = Depends(require_tenant_role(["owner", "admin", "master_admin"])),
):
    """Soft-archive a resource (toggle `archived=True`)."""
    res = resources_col.update_one(
        {"id": resource_id, "tenant_id": tenant["id"]},
        {"$set": {"archived": True, "updated_at": _now()}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Resource not found")
    return {"ok": True, "archived": True}


# ─── File upload + serve ─────────────────────────────────────────────────
@router.post("/upload")
async def upload_resource_file(
    file: UploadFile = File(...),
    tenant: dict = Depends(require_tenant_role(["owner", "admin", "master_admin"])),
):
    """Step 1 of file-type resource creation. Returns a `file_id` the
    caller then passes to `POST /api/aria/resources`.
    """
    content = await file.read()
    if not content:
        raise HTTPException(400, "Empty file.")
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(413, f"File too large (max {MAX_FILE_BYTES // (1024 * 1024)}MB).")

    safe_name = _safe_filename(file.filename or "resource")
    path = os.path.join(UPLOADS_DIR, safe_name)
    with open(path, "wb") as f:
        f.write(content)
    return {
        "ok":           True,
        "file_id":      safe_name,
        "file_name":    file.filename,
        "size":         len(content),
        "content_type": file.content_type,
    }


@router.get("/file/{file_id}")
async def serve_resource_file(file_id: str):
    """Public serve — resources are linked from emails so don't require auth.

    Path-traversal guard via realpath + commonpath.
    """
    full_path = os.path.join(UPLOADS_DIR, file_id)
    real_uploads = os.path.realpath(UPLOADS_DIR)
    real_full = os.path.realpath(full_path)
    if not os.path.isfile(full_path) or os.path.commonpath([real_uploads, real_full]) != real_uploads:
        raise HTTPException(404, "File not found")
    return FileResponse(full_path)


# ─── ARIA matcher — pick the best resource for a lead ────────────────────
def _lead_icp_id(lead: Dict[str, Any]) -> Optional[str]:
    """Best-effort ICP id from any of the common lead fields."""
    return lead.get("icp_id") or lead.get("matched_icp_id") or (lead.get("icp") or {}).get("id")


@router.get("/match-for-lead/{lead_id}")
async def match_for_lead(
    lead_id: str,
    tenant: dict = Depends(get_active_tenant),
    limit: int = 3,
):
    """Return the top-N resources Aria should attach for this lead,
    ranked by ICP match → tag overlap → recency → send_count.

    Useful for outbound composition + the test-chat panel.
    """
    lead = leads_col.find_one(
        {"$or": [{"id": lead_id}, {"_id": lead_id}], "tenant_id": tenant["id"]},
        {"_id": 0},
    )
    if not lead:
        raise HTTPException(404, "Lead not found")

    icp_id = _lead_icp_id(lead)
    lead_industry = (lead.get("industry") or "").lower().strip()
    lead_pain = " ".join(str(v).lower() for v in [
        lead.get("pain_point"), lead.get("notes"), lead.get("message"),
    ] if v)

    rows = list(resources_col.find(
        {"tenant_id": tenant["id"], "archived": {"$ne": True}},
        {"_id": 0},
    ))

    def score(r: Dict[str, Any]) -> float:
        s = 0.0
        if icp_id and icp_id in (r.get("target_icp_ids") or []):
            s += 100
        tag_hits = sum(1 for t in (r.get("tags") or []) if t and (t in lead_pain or t in lead_industry))
        s += tag_hits * 12
        s += min((r.get("send_count") or 0), 10) * 0.5
        return s

    ranked = sorted(rows, key=score, reverse=True)
    top = [_serialize(r) for r in ranked[:max(1, min(limit, 10))] if score(r) > 0 or icp_id is None][:limit]
    return {"ok": True, "count": len(top), "lead_icp_id": icp_id, "resources": top}


# ─── Send-count increment (for Aria to stamp when she attaches one) ─────
class AttachPayload(BaseModel):
    resource_id: str


@router.post("/attach")
async def increment_send_count(
    payload: AttachPayload,
    tenant: dict = Depends(get_active_tenant),
):
    """ARIA (or the founder) calls this when a resource is attached to an
    outbound. Keeps the popularity counter accurate for ranking.
    """
    res = resources_col.update_one(
        {"id": payload.resource_id, "tenant_id": tenant["id"]},
        {"$inc": {"send_count": 1}, "$set": {"last_used_at": _now()}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Resource not found")
    return {"ok": True}
