"""ARIA — Tenant leads unification helper.

iter146 — The backend has TWO lead collections with different field shapes:

  • `leads`     (legacy ARIA / CRM) — status, icp_score, icp_tier, _id=ObjectId
  • `pt_leads`  (Pietential / Lemlist) — stage, score, source, id=UUID str

Every aggregation endpoint historically only queried one of them, which is
why Pietential workspaces consistently showed 0 / empty for sidebar counts,
your-five-today, sleeping leads, EOD wrap, Command Center, onboarding
milestones, ICP contact counts, etc.

This helper normalises both shapes into ONE unified-lead dict with stable
field names that legacy + Pietential UI components can both consume:

    {
      id:              str            (str(_id) for legacy, .id for pt)
      tenant_id:       str
      first_name, last_name, email, phone, company_name, job_title
      source_channel:  str            (source for pt)
      status:          str            (status for legacy, mapped from stage for pt)
      stage_native:    str | None     (pt stage if available, else None)
      icp_score:       int            (icp_score for legacy, score for pt)
      icp_tier:        str | None     (icp_tier for legacy, derived from stage for pt)
      score:           int            (same as icp_score — alias for UIs that read .score)
      created_at, updated_at, last_contacted_at: ISO str
      _origin:         "legacy" | "pt"
    }

Usage
─────
    from routes.lead_query import iter_tenant_leads, count_tenant_leads

    for lead in iter_tenant_leads(tenant_id, status_in={"new", "contacted"}):
        ...

    n = count_tenant_leads(tenant_id, stage_in={"hot", "warm"})
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Iterator, Optional, Set

from deps import db, leads_collection

pt_leads_col = db["pt_leads"]


# pt_leads.stage → legacy `status` bucket so a single `status` filter
# works across both collections.
_PT_STAGE_TO_STATUS = {
    "cold":          "new",
    "warm":          "contacted",
    "hot":           "qualified",
    "engaged":       "qualified",
    "replied":       "qualified",
    "session_pilot": "negotiation",
    "john_owns":     "contacted",
    "dnc":           "unqualified",
}

_PT_STAGE_TO_ICP_TIER = {
    "cold": "cold", "warm": "warm",
    "hot": "hot", "engaged": "hot",
    "session_pilot": "hot", "replied": "warm",
    "john_owns": "warm", "dnc": "cold",
}


def _legacy_to_unified(d: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id":               str(d.get("_id")) if d.get("_id") else d.get("id"),
        "tenant_id":        d.get("tenant_id"),
        "first_name":       d.get("first_name") or "",
        "last_name":        d.get("last_name") or "",
        "email":            d.get("email") or "",
        "phone":            d.get("phone"),
        "company_name":     d.get("company_name"),
        "job_title":        d.get("job_title"),
        "source_channel":   d.get("source_channel") or "manual",
        "status":           d.get("status") or "new",
        "stage_native":     None,
        "icp_score":        int(d.get("icp_score") or 0),
        "icp_tier":         d.get("icp_tier"),
        "score":            int(d.get("icp_score") or 0),
        "created_at":       d.get("created_at"),
        "updated_at":       d.get("updated_at"),
        "last_contacted_at": d.get("last_contacted_at"),
        "_origin":          "legacy",
    }


def _pt_to_unified(d: Dict[str, Any]) -> Dict[str, Any]:
    stage = (d.get("stage") or "cold").lower()
    return {
        "id":               d.get("id"),
        "tenant_id":        d.get("tenant_id"),
        "first_name":       d.get("first_name") or "",
        "last_name":        d.get("last_name") or "",
        "email":            d.get("email") or "",
        "phone":            d.get("phone"),
        "company_name":     d.get("company_name"),
        "job_title":        d.get("title") or d.get("job_title"),
        "source_channel":   d.get("source") or "lemlist",
        "status":           _PT_STAGE_TO_STATUS.get(stage, "new"),
        "stage_native":     stage,
        "icp_score":        int(d.get("score") or 0),
        "icp_tier":         _PT_STAGE_TO_ICP_TIER.get(stage),
        "score":            int(d.get("score") or 0),
        "created_at":       d.get("created_at"),
        "updated_at":       d.get("updated_at"),
        "last_contacted_at": d.get("last_activity_at") or d.get("last_contacted_at"),
        "_origin":          "pt",
    }


def iter_tenant_leads(
    tenant_id: str,
    *,
    status_in: Optional[Set[str]] = None,
    stage_in: Optional[Set[str]] = None,
    icp_tier_in: Optional[Set[str]] = None,
    min_score: Optional[int] = None,
    limit: Optional[int] = None,
) -> Iterator[Dict[str, Any]]:
    """Yield unified-shape lead dicts from BOTH `leads` + `pt_leads`."""
    if not tenant_id:
        return
    base = {"tenant_id": tenant_id}
    yielded = 0

    # Legacy leads.
    legacy_q = dict(base)
    if status_in:
        legacy_q["status"] = {"$in": list(status_in)}
    if icp_tier_in:
        legacy_q["icp_tier"] = {"$in": list(icp_tier_in)}
    if min_score is not None:
        legacy_q["icp_score"] = {"$gte": min_score}
    for d in leads_collection.find(legacy_q):
        yield _legacy_to_unified(d)
        yielded += 1
        if limit and yielded >= limit:
            return

    # pt_leads.
    pt_q = dict(base)
    or_clauses = []
    if status_in:
        # Map requested legacy statuses back to pt stages.
        target_stages = {
            stage for stage, status in _PT_STAGE_TO_STATUS.items() if status in status_in
        }
        if target_stages:
            or_clauses.append({"stage": {"$in": list(target_stages)}})
    if stage_in:
        or_clauses.append({"stage": {"$in": list(stage_in)}})
    if min_score is not None:
        or_clauses.append({"score": {"$gte": min_score}})
    if or_clauses:
        if len(or_clauses) == 1:
            pt_q.update(or_clauses[0])
        else:
            pt_q["$or"] = or_clauses
    for d in pt_leads_col.find(pt_q, {"_id": 0}):
        yield _pt_to_unified(d)
        yielded += 1
        if limit and yielded >= limit:
            return


def count_tenant_leads(
    tenant_id: str,
    *,
    status_in: Optional[Set[str]] = None,
    stage_in: Optional[Set[str]] = None,
    icp_tier_in: Optional[Set[str]] = None,
    min_score: Optional[int] = None,
) -> int:
    """Combined count across both collections, with the same filter semantics
    as iter_tenant_leads. Useful for sidebar counts + KPI tiles."""
    if not tenant_id:
        return 0
    base = {"tenant_id": tenant_id}

    legacy_q = dict(base)
    if status_in:
        legacy_q["status"] = {"$in": list(status_in)}
    if icp_tier_in:
        legacy_q["icp_tier"] = {"$in": list(icp_tier_in)}
    if min_score is not None:
        legacy_q["icp_score"] = {"$gte": min_score}
    legacy_n = leads_collection.count_documents(legacy_q)

    pt_q = dict(base)
    or_clauses = []
    if status_in:
        target_stages = {
            stage for stage, status in _PT_STAGE_TO_STATUS.items() if status in status_in
        }
        if target_stages:
            or_clauses.append({"stage": {"$in": list(target_stages)}})
    if stage_in:
        or_clauses.append({"stage": {"$in": list(stage_in)}})
    if min_score is not None:
        or_clauses.append({"score": {"$gte": min_score}})
    if or_clauses:
        if len(or_clauses) == 1:
            pt_q.update(or_clauses[0])
        else:
            pt_q["$or"] = or_clauses
    pt_n = pt_leads_col.count_documents(pt_q)

    return legacy_n + pt_n


def find_tenant_lead_by_id(tenant_id: str, lead_id: str) -> Optional[Dict[str, Any]]:
    """Resolve a lead by id across both collections — returns unified dict
    or None. The id may be a Mongo ObjectId string or a pt_leads UUID."""
    if not tenant_id or not lead_id:
        return None
    # Try pt_leads first (UUID-style ids never coerce to ObjectId).
    pt = pt_leads_col.find_one({"tenant_id": tenant_id, "id": lead_id}, {"_id": 0})
    if pt:
        return _pt_to_unified(pt)
    try:
        from bson import ObjectId
        oid = ObjectId(lead_id)
    except Exception:
        return None
    legacy = leads_collection.find_one({"_id": oid, "tenant_id": tenant_id})
    return _legacy_to_unified(legacy) if legacy else None


__all__ = [
    "iter_tenant_leads",
    "count_tenant_leads",
    "find_tenant_lead_by_id",
    "_legacy_to_unified",
    "_pt_to_unified",
]
