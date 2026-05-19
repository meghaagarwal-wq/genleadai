"""Saleshandy + Lemlist pull-based campaign/lead import.

Until now we only consumed Saleshandy/Lemlist webhook *push* events (see
`integrations_hub.py:saleshandy_webhook` / `lemlist_webhook`). Tenants asked
for an *active pull* so they can:

  1. Test their pasted API key really works.
  2. Fetch a list of campaigns/sequences from the remote tool.
  3. Pick specific campaigns and pull all leads/prospects into Aria.
  4. See import logs (counts, dedup, errors) per run.

Wire-up:
  - Stores API key in the *existing* `integration_configs.config.api_key`
    field already populated by the Integrations Hub "Manage" modal.
  - New collection `integration_import_logs` records every import run.
  - Re-uses `_normalize_and_capture` from integrations_hub to keep dedup +
    capture flow identical to the webhook path.
"""
from __future__ import annotations

import base64
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import db
from routes.tenants import get_active_tenant
from routes.integrations_hub import (
    configs_col,
    events_col,
    _normalize_and_capture,
    leads_col,
)

router = APIRouter(prefix="/api/integrations", tags=["integrations-import"])

import_logs_col = db["integration_import_logs"]


SALESHANDY_BASE = "https://open-api.saleshandy.com/v1"
LEMLIST_BASE = "https://api.lemlist.com/api"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_cfg(tenant_id: str, tool: str) -> dict:
    doc = configs_col.find_one(
        {"tenant_id": tenant_id, "integration_type": tool},
        {"_id": 0, "config": 1},
    )
    if not doc:
        raise HTTPException(
            status_code=400,
            detail=f"{tool.title()} is not connected. Paste your API key in Integrations Hub first.",
        )
    cfg = doc.get("config") or {}
    if not cfg.get("api_key"):
        raise HTTPException(
            status_code=400,
            detail=f"{tool.title()} API key is missing. Reconnect to add one.",
        )
    return cfg


# ─── Saleshandy helpers ─────────────────────────────────────────────────────
def _saleshandy_headers(api_key: str) -> dict:
    # Saleshandy Open API uses an `x-api-key` header (confirmed in their public docs).
    return {"x-api-key": api_key, "Content-Type": "application/json", "Accept": "application/json"}


async def _saleshandy_list_sequences(api_key: str) -> List[dict]:
    """Saleshandy calls their outreach flows 'sequences' in their API.

    NOTE: Saleshandy's `GET /v1/sequences` endpoint takes NO pagination params
    (confirmed via their public docs + their own 400 response "property limit
    should not exist"). We get the whole list in one call.
    """
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(
            f"{SALESHANDY_BASE}/sequences",
            headers=_saleshandy_headers(api_key),
        )
        if r.status_code in (401, 403):
            raise HTTPException(status_code=400, detail="Saleshandy API key invalid or missing permissions.")
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Saleshandy returned {r.status_code}: {r.text[:160]}")
        data = r.json() or {}
        # Response shapes seen in the wild: {data: {sequences: [...]}}, {sequences: [...]},
        # {data: [...]}, or bare [...].
        if isinstance(data, list):
            return data
        items = (data.get("data") or {}).get("sequences") if isinstance(data.get("data"), dict) else None
        if items is None:
            items = data.get("sequences") or data.get("data") or []
        return items if isinstance(items, list) else []


async def _saleshandy_list_prospects(api_key: str, sequence_id: str) -> List[dict]:
    """List prospects inside a Saleshandy sequence.

    Saleshandy v1 uses `pageSize` + `cursor` (cursor-based pagination). We do
    NOT pass `limit` — their API rejects it with 400 "property limit should
    not exist". If both paginated shapes fail, we fall back to a paramless
    GET so smaller accounts still work.
    """
    out: List[dict] = []
    cursor: Optional[str] = None
    PAGE_SIZE = 100
    async with httpx.AsyncClient(timeout=25) as client:
        for _attempt in range(20):  # 20 * 100 = 2,000-prospect safety cap
            params: dict = {"pageSize": PAGE_SIZE}
            if cursor:
                params["cursor"] = cursor

            r = await client.get(
                f"{SALESHANDY_BASE}/sequences/{sequence_id}/prospects",
                headers=_saleshandy_headers(api_key),
                params=params,
            )
            if r.status_code in (401, 403):
                raise HTTPException(status_code=400, detail="Saleshandy API key invalid or missing permissions.")
            if r.status_code == 404:
                # Endpoint variant — fall back to /prospects?sequenceId=...
                r = await client.get(
                    f"{SALESHANDY_BASE}/prospects",
                    headers=_saleshandy_headers(api_key),
                    params={**params, "sequenceId": sequence_id},
                )
            if r.status_code == 400 and "limit" not in r.text and "pageSize" in r.text:
                # Last-resort: try with no pagination params (some Saleshandy plans
                # return the full prospect list in one shot, no pagination at all).
                r = await client.get(
                    f"{SALESHANDY_BASE}/sequences/{sequence_id}/prospects",
                    headers=_saleshandy_headers(api_key),
                )
            if r.status_code != 200:
                raise HTTPException(status_code=502, detail=f"Saleshandy prospects {r.status_code}: {r.text[:160]}")
            data = r.json() or {}
            items = (data.get("data") or {}).get("prospects") if isinstance(data.get("data"), dict) else None
            if items is None:
                items = data.get("prospects") or data.get("data") or []
            if isinstance(items, list):
                out.extend(items)

            # Read next cursor (Saleshandy may return at top level or under data.).
            next_cursor = data.get("nextCursor") or data.get("next_cursor")
            if not next_cursor and isinstance(data.get("data"), dict):
                next_cursor = data["data"].get("nextCursor") or data["data"].get("next_cursor")
            if not next_cursor:
                break
            cursor = next_cursor
    return out


def _saleshandy_normalize(p: dict, seq: dict) -> dict:
    """Saleshandy prospect → Aria raw lead payload."""
    return {
        "first_name": p.get("firstName") or p.get("first_name") or "Lead",
        "last_name": p.get("lastName") or p.get("last_name") or "",
        "email": p.get("email"),
        "phone": p.get("phone") or p.get("phoneNumber"),
        "company": p.get("companyName") or p.get("company") or "",
        "job_title": p.get("jobTitle") or p.get("title"),
        "linkedin_url": p.get("linkedinUrl") or p.get("linkedin_url"),
        "country": p.get("country"),
        "industry": p.get("industry"),
        "message": f"Imported from Saleshandy sequence: {seq.get('name') or seq.get('title') or seq.get('id')}",
        "utm_source": "saleshandy",
        "utm_campaign": seq.get("name") or seq.get("title"),
        "external_id": p.get("id") or p.get("_id") or p.get("prospectId"),
    }


# ─── Lemlist helpers ────────────────────────────────────────────────────────
def _lemlist_headers(api_key: str) -> dict:
    # Lemlist auth: HTTP Basic with empty user + apiKey as password (":<api_key>" b64).
    token = base64.b64encode(f":{api_key}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Accept": "application/json"}


async def _lemlist_list_campaigns(api_key: str) -> List[dict]:
    out: List[dict] = []
    offset = 0
    limit = 100
    async with httpx.AsyncClient(timeout=20) as client:
        while True:
            r = await client.get(
                f"{LEMLIST_BASE}/campaigns",
                headers=_lemlist_headers(api_key),
                params={"offset": offset, "limit": limit},
            )
            if r.status_code in (401, 403):
                raise HTTPException(status_code=400, detail="Lemlist API key invalid or missing permissions.")
            if r.status_code != 200:
                raise HTTPException(status_code=502, detail=f"Lemlist returned {r.status_code}: {r.text[:160]}")
            data = r.json()
            if not isinstance(data, list) or not data:
                break
            out.extend(data)
            if len(data) < limit:
                break
            offset += limit
            if offset >= 1000:  # safety cap
                break
    return out


async def _lemlist_list_leads(api_key: str, campaign_id: str) -> List[dict]:
    """List leads in a Lemlist campaign.

    Tries multiple endpoint shapes Lemlist ships across plans:
      1. /api/campaigns/{id}/leads          (current v1, no slash)
      2. /api/campaigns/{id}/leads/         (older v1 — strict-slash plans)
      3. /api/v2/campaigns/{id}/leads       (newer v2 endpoint)
      4. /api/campaigns/{id}/exports?type=leads (some plans only expose via export)
    """
    candidate_urls = [
        f"{LEMLIST_BASE}/campaigns/{campaign_id}/leads",
        f"{LEMLIST_BASE}/campaigns/{campaign_id}/leads/",
        f"{LEMLIST_BASE}/v2/campaigns/{campaign_id}/leads",
    ]
    out: List[dict] = []
    chosen_url: Optional[str] = None
    async with httpx.AsyncClient(timeout=25) as client:
        # Pick the first URL that doesn't 404 with an empty result.
        for url in candidate_urls:
            r0 = await client.get(
                url,
                headers=_lemlist_headers(api_key),
                params={"offset": 0, "limit": 100},
            )
            if r0.status_code in (401, 403):
                raise HTTPException(status_code=400, detail="Lemlist API key invalid or missing permissions.")
            if r0.status_code == 404:
                continue
            if r0.status_code != 200:
                # Try next candidate on 400/5xx; only surface if all fail.
                continue
            data0 = r0.json()
            if isinstance(data0, dict) and "leads" in data0:
                data0 = data0["leads"]
            if isinstance(data0, list):
                chosen_url = url
                out.extend(data0)
                if len(data0) < 100:
                    return out
                break

        if not chosen_url:
            # All candidate URLs failed. Surface a clear error.
            raise HTTPException(
                status_code=502,
                detail=(
                    "Lemlist returned no usable leads endpoint for this campaign. "
                    "Confirm your API key has lead-read scope (Settings → Integrations → API key permissions)."
                ),
            )

        # Continue paginating from the URL that worked.
        offset = 100
        while True:
            r = await client.get(
                chosen_url,
                headers=_lemlist_headers(api_key),
                params={"offset": offset, "limit": 100},
            )
            if r.status_code in (401, 403):
                raise HTTPException(status_code=400, detail="Lemlist API key invalid or missing permissions.")
            if r.status_code == 404:
                return out
            if r.status_code != 200:
                raise HTTPException(status_code=502, detail=f"Lemlist leads {r.status_code}: {r.text[:160]}")
            data = r.json()
            if isinstance(data, dict) and "leads" in data:
                data = data["leads"]
            if not isinstance(data, list) or not data:
                break
            out.extend(data)
            if len(data) < 100:
                break
            offset += 100
            if offset >= 2000:
                break
    return out


def _lemlist_normalize(lead: dict, camp: dict) -> dict:
    return {
        "first_name": lead.get("firstName") or lead.get("first_name") or "Lead",
        "last_name": lead.get("lastName") or lead.get("last_name") or "",
        "email": lead.get("email"),
        "phone": lead.get("phone") or lead.get("phoneNumber"),
        "company": lead.get("companyName") or lead.get("company") or "",
        "job_title": lead.get("jobTitle") or lead.get("title"),
        "linkedin_url": lead.get("linkedinUrl") or lead.get("linkedin_url"),
        "country": lead.get("country"),
        "industry": lead.get("industry"),
        "message": f"Imported from Lemlist campaign: {camp.get('name') or camp.get('_id')}",
        "utm_source": "lemlist",
        "utm_campaign": camp.get("name"),
        "external_id": lead.get("_id") or lead.get("id"),
    }


# ─── Test connection ────────────────────────────────────────────────────────
class _Empty(BaseModel):
    pass


@router.post("/{tool}/test-connection")
async def test_connection(tool: str, tenant: dict = Depends(get_active_tenant)):
    if tool not in ("saleshandy", "lemlist"):
        raise HTTPException(status_code=404, detail="Unsupported tool")
    cfg = _get_cfg(tenant["id"], tool)
    try:
        if tool == "saleshandy":
            seqs = await _saleshandy_list_sequences(cfg["api_key"])
            return {"ok": True, "tool": tool, "campaigns_found": len(seqs)}
        else:
            camps = await _lemlist_list_campaigns(cfg["api_key"])
            return {"ok": True, "tool": tool, "campaigns_found": len(camps)}
    except HTTPException as e:
        # Update integration status to reflect the auth failure so the Manage modal
        # can surface a "reconnect" prompt without us swallowing the original detail.
        configs_col.update_one(
            {"tenant_id": tenant["id"], "integration_type": tool},
            {"$set": {"status": "error", "error_message": e.detail[:240], "updated_at": _now_iso()}},
        )
        return {"ok": False, "tool": tool, "error": e.detail}


# ─── List campaigns ─────────────────────────────────────────────────────────
@router.get("/{tool}/campaigns")
async def list_campaigns(tool: str, tenant: dict = Depends(get_active_tenant)):
    """Return a normalized list of campaigns/sequences with stats for the import UI."""
    if tool not in ("saleshandy", "lemlist"):
        raise HTTPException(status_code=404, detail="Unsupported tool")
    cfg = _get_cfg(tenant["id"], tool)

    if tool == "saleshandy":
        seqs = await _saleshandy_list_sequences(cfg["api_key"])
        rows = []
        for s in seqs:
            stats = s.get("stats") or s.get("analytics") or {}
            rows.append({
                "id": str(s.get("id") or s.get("_id") or s.get("sequenceId") or ""),
                "name": s.get("name") or s.get("title") or "Untitled sequence",
                "status": (s.get("status") or "").lower() or "unknown",
                "created_at": s.get("createdAt") or s.get("created_at"),
                "leads": s.get("totalProspects") or stats.get("totalProspects") or stats.get("prospects") or 0,
                "opens": stats.get("opens") or stats.get("openCount") or 0,
                "clicks": stats.get("clicks") or stats.get("clickCount") or 0,
                "replies": stats.get("replies") or stats.get("replyCount") or 0,
                "last_activity": s.get("lastActivityAt") or s.get("updatedAt"),
            })
        return {"tool": tool, "campaigns": rows}

    # Lemlist
    camps = await _lemlist_list_campaigns(cfg["api_key"])
    rows = []
    for c in camps:
        rows.append({
            "id": str(c.get("_id") or c.get("id") or ""),
            "name": c.get("name") or "Untitled campaign",
            "status": (c.get("status") or "").lower() or "unknown",
            "created_at": c.get("createdAt") or c.get("created_at"),
            "leads": c.get("nbLeads") or c.get("totalLeads") or 0,
            "opens": (c.get("stats") or {}).get("emailsOpened") or 0,
            "clicks": (c.get("stats") or {}).get("emailsClicked") or 0,
            "replies": (c.get("stats") or {}).get("emailsReplied") or 0,
            "last_activity": c.get("updatedAt") or c.get("modifiedAt"),
        })
    return {"tool": tool, "campaigns": rows}


# ─── Import leads ───────────────────────────────────────────────────────────
class ImportPayload(BaseModel):
    campaign_ids: List[str] = Field(default_factory=list, description="Campaigns to import. Empty = all.")
    import_mode: str = Field(default="selected", description="selected | all | active_only")


@router.post("/{tool}/import-leads")
async def import_leads(tool: str, payload: ImportPayload, tenant: dict = Depends(get_active_tenant)):
    if tool not in ("saleshandy", "lemlist"):
        raise HTTPException(status_code=404, detail="Unsupported tool")
    cfg = _get_cfg(tenant["id"], tool)

    # 1. List campaigns + filter by user's selection.
    if tool == "saleshandy":
        all_campaigns = await _saleshandy_list_sequences(cfg["api_key"])

        def get_id(c: dict) -> str:
            return str(c.get("id") or c.get("_id") or c.get("sequenceId") or "")

        def get_status(c: dict) -> str:
            return (c.get("status") or "").lower()
    else:
        all_campaigns = await _lemlist_list_campaigns(cfg["api_key"])

        def get_id(c: dict) -> str:  # noqa: F811 — two branch-local defs are intentional
            return str(c.get("_id") or c.get("id") or "")

        def get_status(c: dict) -> str:  # noqa: F811
            return (c.get("status") or "").lower()

    if payload.import_mode == "all":
        selected = all_campaigns
    elif payload.import_mode == "active_only":
        selected = [c for c in all_campaigns if get_status(c) in ("running", "active", "scheduled")]
    else:  # selected
        wanted = set(payload.campaign_ids or [])
        selected = [c for c in all_campaigns if get_id(c) in wanted]

    if not selected:
        return {"ok": False, "reason": "No campaigns matched your selection.", "imported": 0}

    # 2. For each campaign, pull leads + normalize + insert via existing capture.
    log_id = uuid.uuid4().hex
    counts = {"fetched": 0, "imported": 0, "updated": 0, "duplicates_merged": 0, "failed": 0}
    per_campaign: List[dict] = []
    failures: List[dict] = []

    # We don't need a real Request object since _normalize_and_capture only uses
    # it for IP logging — pass a thin stub.
    class _StubRequest:
        client = type("c", (), {"host": "import"})()
        headers = {}
    stub_req = _StubRequest()

    for camp in selected:
        camp_id = get_id(camp)
        camp_name = camp.get("name") or camp.get("title") or camp_id
        try:
            if tool == "saleshandy":
                items = await _saleshandy_list_prospects(cfg["api_key"], camp_id)

                def normalize(x: dict, _c=camp) -> dict:
                    return _saleshandy_normalize(x, _c)
            else:
                items = await _lemlist_list_leads(cfg["api_key"], camp_id)

                def normalize(x: dict, _c=camp) -> dict:  # noqa: F811
                    return _lemlist_normalize(x, _c)
        except HTTPException as e:
            failures.append({"campaign": camp_name, "error": e.detail})
            counts["failed"] += 1
            continue

        camp_fetched = len(items)
        camp_imported = 0
        camp_updated = 0
        counts["fetched"] += camp_fetched

        for item in items:
            raw = normalize(item)
            external_id = raw.pop("external_id", None)
            # Skip rows with truly no identifiable handle. We allow leads with
            # name+company even if email is missing — Lemlist sometimes returns
            # LinkedIn-only enriched leads that lack an email but are still useful.
            has_handle = bool(raw.get("email") or raw.get("phone") or raw.get("linkedin_url"))
            has_name = bool((raw.get("first_name") or raw.get("last_name")) and raw.get("company"))
            if not has_handle and not has_name:
                counts["failed"] += 1
                failures.append({"campaign": camp_name, "external_id": external_id, "error": "no email/phone/linkedin/name+company"})
                continue

            # Dedupe: if a lead already exists for this tenant with same email/phone/external_id,
            # update last_contacted + source flags instead of inserting a new one.
            existing = None
            if external_id:
                existing = leads_col.find_one({
                    "tenant_id": tenant["id"],
                    "external_source": tool,
                    "external_id": external_id,
                })
            if not existing and raw.get("email"):
                existing = leads_col.find_one({"tenant_id": tenant["id"], "email": (raw.get("email") or "").lower()})
            if not existing and raw.get("phone"):
                existing = leads_col.find_one({"tenant_id": tenant["id"], "phone": raw.get("phone")})

            if existing:
                update_set = {
                    "external_source": tool,
                    "external_id": external_id or existing.get("external_id"),
                    "external_campaign_id": camp_id,
                    "external_campaign_name": camp_name,
                    "last_imported_at": _now_iso(),
                    "updated_at": _now_iso(),
                }
                leads_col.update_one({"_id": existing["_id"]}, {"$set": update_set})
                camp_updated += 1
                counts["updated"] += 1
                counts["duplicates_merged"] += 1
                continue

            try:
                res = await _normalize_and_capture(tenant["id"], raw, tool, stub_req)  # type: ignore[arg-type]
                lead_id = res.get("lead_id")
                if lead_id:
                    leads_col.update_one(
                        {"id": lead_id, "tenant_id": tenant["id"]},
                        {"$set": {
                            "external_source": tool,
                            "external_id": external_id,
                            "external_campaign_id": camp_id,
                            "external_campaign_name": camp_name,
                            "last_imported_at": _now_iso(),
                        }},
                    )
                camp_imported += 1
                counts["imported"] += 1
            except Exception as e:
                counts["failed"] += 1
                failures.append({"campaign": camp_name, "external_id": external_id, "error": str(e)[:160]})

        per_campaign.append({
            "campaign_id": camp_id,
            "campaign_name": camp_name,
            "fetched": camp_fetched,
            "imported": camp_imported,
            "updated": camp_updated,
        })

    # 3. Persist the import log.
    log_doc = {
        "id": log_id,
        "tenant_id": tenant["id"],
        "tool": tool,
        "import_mode": payload.import_mode,
        "campaigns_selected": len(selected),
        "per_campaign": per_campaign,
        "totals": counts,
        "failures": failures[:50],  # cap to avoid 16MB doc limit on noisy keys
        "created_at": _now_iso(),
        "status": "completed" if counts["failed"] == 0 else ("partial" if counts["imported"] > 0 else "failed"),
    }
    import_logs_col.insert_one(log_doc)

    # 4. Mark integration as last-synced.
    configs_col.update_one(
        {"tenant_id": tenant["id"], "integration_type": tool},
        {"$set": {"last_sync_at": _now_iso(), "status": "connected"}},
    )

    log_doc.pop("_id", None)
    return {"ok": True, "log": log_doc}


# ─── Import logs ────────────────────────────────────────────────────────────
@router.get("/import-logs")
async def list_import_logs(
    tool: Optional[str] = None,
    limit: int = 20,
    tenant: dict = Depends(get_active_tenant),
):
    q: dict = {"tenant_id": tenant["id"]}
    if tool:
        q["tool"] = tool
    rows = list(
        import_logs_col.find(q, {"_id": 0}).sort("created_at", -1).limit(min(max(limit, 1), 100))
    )
    return {"logs": rows}
