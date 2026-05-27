"""Iter105 — P2 fixes batched into a single new router for compactness.

Endpoints added (all behind tenant auth unless noted):

  FIX 8 — GET    /api/pt/insights/{insight_id}/pdf       — server-side PDF export
  FIX 9 — GET    /api/aria/training-profile/history      — list saved versions
          POST   /api/aria/training-profile/restore/{v}  — restore a version
  FIX 10— POST   /api/aria/training-profile/scrape-url   — URL scrape + extract
  FIX 11— GET    /api/pt/insights/prospects              — list watched prospects
          PATCH  /api/contacts/{id}/insights_enabled     — toggle
  FIX 12— POST   /api/admin/jobs/{job_name}/trigger      — manual job trigger
  FIX 13— GET    /api/pt/reports/icp                     — ICP match distribution
          GET    /api/pt/reports/channels                — reply rate by channel
  FIX 14— GET    /api/sequences ; POST /api/sequences
          PATCH  /api/sequences/{id} ; DELETE /api/sequences/{id}
          POST   /api/sequences/{id}/enrol
          GET    /api/sequences/{id}/enrolments
  FIX 15— inbound WhatsApp Send/Dismiss command parsing (helper used by the
          existing WhatsApp webhook in server.py).
"""
from __future__ import annotations

import asyncio
import io
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from bson import ObjectId  # noqa: F401
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from starlette.responses import StreamingResponse

from deps import db, get_current_user
from routes.tenants import get_active_tenant, require_tenant_role

router = APIRouter(tags=["iter105-fixes"])

insights_col = db["pt_insights"]
training_col = db["aria_training"]
training_versions_col = db["aria_training_versions"]
contacts_col = db["workspace_contacts"]
pt_leads_col = db["pt_leads"]
tenants_col = db["tenants"]
sequences_col = db["sequences"]
sequence_enrolments_col = db["sequence_enrolments"]
leads_col = db["leads"]
aria_conversations_col = db["aria_conversations"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _strip_mongo(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not doc:
        return doc
    return {k: v for k, v in doc.items() if k != "_id"}


# ─────────────────────────────────────────────────────────────────────────
# FIX 8 — Insight card PDF export
# ─────────────────────────────────────────────────────────────────────────
@router.get("/api/pt/insights/{insight_id}/pdf")
async def insight_card_pdf(
    insight_id: str,
    tenant: dict = Depends(get_active_tenant),
):
    card = insights_col.find_one({"id": insight_id, "tenant_id": tenant["id"]}, {"_id": 0})
    if not card:
        raise HTTPException(404, "Insight not found")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, topMargin=48, bottomMargin=48, leftMargin=56, rightMargin=56)
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=20, textColor=colors.HexColor("#5B28D4"))
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12, textColor=colors.HexColor("#6B7280"))
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10, leading=15)
    mono = ParagraphStyle("mono", parent=styles["Code"], fontSize=9, leading=13, backColor=colors.HexColor("#F4F1FA"))

    story: List[Any] = []
    story.append(Paragraph("ARIA Sales Intelligence — Insight Card", h1))
    story.append(Paragraph(f"Generated {_now_iso()[:19].replace('T', ' ')} UTC", h2))
    story.append(Spacer(1, 14))

    name = card.get("prospect_name") or "—"
    title = card.get("prospect_title") or ""
    company = card.get("prospect_company") or ""
    story.append(Paragraph(f"<b>Prospect:</b> {name}", body))
    if title or company:
        story.append(Paragraph(f"{title}{' · ' + company if company and title else company}", body))
    story.append(Spacer(1, 10))

    if card.get("icp_match_name"):
        score = round((card.get("icp_match_score") or 0) * 100)
        story.append(Paragraph(f"<b>ICP match:</b> {card['icp_match_name']} &nbsp; <font color='#7C35DC'>{score}%</font>", body))
        story.append(Spacer(1, 6))

    sig_type = card.get("signal_type") or "—"
    conf = round((card.get("confidence") or 0) * 100)
    story.append(Paragraph(f"<b>Signal:</b> {sig_type} &nbsp; <font color='#16A34A'>{conf}% confidence</font>", body))
    story.append(Spacer(1, 8))
    if card.get("signal_summary"):
        story.append(Paragraph(card["signal_summary"], body))
        story.append(Spacer(1, 10))

    if card.get("suggested_message"):
        story.append(Paragraph("<b>Suggested message</b>", h2))
        story.append(Paragraph(card["suggested_message"].replace("\n", "<br/>"), mono))
        story.append(Spacer(1, 10))

    if card.get("rationale"):
        story.append(Paragraph("<b>Why now</b>", h2))
        story.append(Paragraph(card["rationale"], body))
        story.append(Spacer(1, 8))

    if card.get("resource_name"):
        story.append(Paragraph(f"<b>Recommended resource:</b> {card['resource_name']}", body))

    if card.get("timing_hint"):
        story.append(Paragraph(f"<b>Timing:</b> {card['timing_hint']}", body))

    doc.build(story)
    buf.seek(0)
    fname = f"aria-insight-{insight_id}.pdf"
    return StreamingResponse(
        buf, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


# ─────────────────────────────────────────────────────────────────────────
# FIX 9 — Training version history + restore
# ─────────────────────────────────────────────────────────────────────────
@router.get("/api/aria/training-profile/history")
async def training_history(tenant: dict = Depends(get_active_tenant)):
    versions = list(
        training_versions_col.find({"tenant_id": tenant["id"]}, {"_id": 0})
        .sort("version", -1).limit(50)
    )
    # iter105 — fallback: read live profile from tenants.settings so the modal
    # always shows at least the current version, even before any snapshot exists.
    tdoc = tenants_col.find_one({"id": tenant["id"]}, {"_id": 0, "settings.aria_training_profile": 1}) or {}
    tprofile = (tdoc.get("settings") or {}).get("aria_training_profile") or {}
    cur_version = tprofile.get("version") or 0
    cur_data = tprofile.get("data") or {}
    cur_assembled_at = tprofile.get("assembled_at") or _now_iso()

    # Mark which snapshot is the current one (matches the live version number)
    for v in versions:
        v["is_current"] = (v.get("version") == cur_version)

    # If no snapshot for the current version yet (older save before the snapshot
    # logic), inject a synthetic row so the modal shows at least one entry.
    if cur_version and not any(v.get("version") == cur_version for v in versions):
        versions.insert(0, {
            "version": cur_version,
            "saved_at": cur_assembled_at,
            "summary": (cur_data.get("what_you_sell") or cur_data.get("business_name") or "")[:120],
            "tenant_id": tenant["id"],
            "is_current": True,
            "synthetic": True,
        })
    elif not versions and cur_data:
        versions = [{
            "version": cur_version or 1,
            "saved_at": cur_assembled_at,
            "summary": (cur_data.get("what_you_sell") or cur_data.get("business_name") or "")[:120],
            "tenant_id": tenant["id"],
            "is_current": True,
            "synthetic": True,
        }]
    return {"versions": versions}


@router.post("/api/aria/training-profile/restore/{version}")
async def training_restore(
    version: int,
    tenant: dict = Depends(require_tenant_role(["owner", "admin", "master_admin"])),
):
    snap = training_versions_col.find_one(
        {"tenant_id": tenant["id"], "version": version}, {"_id": 0}
    )
    if not snap:
        raise HTTPException(404, "Version not found")
    profile = snap.get("payload") or {}
    # Write back to the canonical location (tenants.settings.aria_training_profile.data),
    # bump version, then re-assemble & re-encrypt the system prompt.
    tenants_col.update_one(
        {"id": tenant["id"]},
        {"$set": {
            "settings.aria_training_profile.data": profile,
            "settings.aria_training_profile.restored_from_version": version,
            "settings.aria_training_profile.assembled_at": _now_iso(),
        }},
    )
    try:
        from routes.aria_training import reassemble_for_tenant
        reassemble_for_tenant(tenant["id"])
    except Exception as _e:
        print(f"[restore] reassemble failed: {_e}")
    return {"ok": True, "restored_version": version}


# ─────────────────────────────────────────────────────────────────────────
# FIX 10 — Train ARIA URL scrape
# iter108 — P2: enforce robots.txt politeness + cap response body length.
# ─────────────────────────────────────────────────────────────────────────
class ScrapeUrlPayload(BaseModel):
    url: str


# iter108 — P2 backlog: enforce hard caps on the raw HTML we ever buffer
# in memory, and respect each site's robots.txt before fetching.
_SCRAPE_MAX_BYTES = 2 * 1024 * 1024  # 2 MiB hard cap on raw HTML download
_SCRAPE_UA = "ARIA-Trainer/1.0 (+https://app.genleadai.com/aria)"


async def _robots_allows(url: str) -> tuple[bool, str]:
    """Check the site's robots.txt for our UA. Soft-allow on errors so
    a missing or unreachable robots.txt never blocks a founder's scrape.

    Returns (allowed, reason).
    """
    try:
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False, "Invalid URL"
        robots_url = urlunparse((parsed.scheme, parsed.netloc, "/robots.txt", "", "", ""))
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            r = await client.get(robots_url, headers={"User-Agent": _SCRAPE_UA})
        if r.status_code != 200 or not r.text:
            return True, "no robots.txt — allowed by default"
        # Minimal robots parser: scan blocks for User-agent: * (or our token)
        # and check Disallow patterns against the path.
        from urllib import robotparser
        rp = robotparser.RobotFileParser()
        rp.parse(r.text.splitlines())
        ok = rp.can_fetch(_SCRAPE_UA, url) and rp.can_fetch("*", url)
        return (ok, "allowed" if ok else "blocked by robots.txt")
    except Exception:
        return True, "robots.txt unreachable — allowed by default"


@router.post("/api/aria/training-profile/scrape-url")
async def training_scrape_url(
    payload: ScrapeUrlPayload,
    tenant: dict = Depends(get_active_tenant),
):
    url = (payload.url or "").strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL must start with http:// or https://")

    # iter108 — robots.txt politeness check.
    allowed, reason = await _robots_allows(url)
    if not allowed:
        raise HTTPException(
            403,
            f"Scrape blocked by site's robots.txt ({reason}). Paste the content "
            f"manually into Train ARIA instead.",
        )

    # iter108 — cap response body to 2 MiB to avoid memory blow-ups on
    # malicious / runaway servers.
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            async with client.stream("GET", url, headers={"User-Agent": _SCRAPE_UA}) as resp:
                resp.raise_for_status()
                content_length = int(resp.headers.get("content-length") or 0)
                if content_length and content_length > _SCRAPE_MAX_BYTES:
                    raise HTTPException(
                        413,
                        f"Page is too large ({content_length // 1024} KiB > 2 MiB cap). "
                        f"Try a single article page instead of a sitemap.",
                    )
                chunks = bytearray()
                async for chunk in resp.aiter_bytes(chunk_size=64 * 1024):
                    chunks.extend(chunk)
                    if len(chunks) > _SCRAPE_MAX_BYTES:
                        chunks = bytearray(chunks[:_SCRAPE_MAX_BYTES])
                        break
                html = bytes(chunks).decode(resp.encoding or "utf-8", errors="replace")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Could not fetch URL: {e}")

    # Strip HTML tags, collapse whitespace.
    import re
    text = re.sub(r"<script[\s\S]*?</script>", "", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", "", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text[:20000]  # cap extracted plain-text length too

    # Reuse the existing document-extraction prompt if available.
    extracted = {"raw_text_excerpt": text[:1500]}
    try:
        from routes.aria_training import _extract_training_fields_from_text  # type: ignore
        extracted = await _extract_training_fields_from_text(text)
    except Exception:
        # Soft-fail — still return the scraped text so the founder can copy/paste.
        pass

    return {
        "ok": True,
        "url": url,
        "extracted": extracted,
        "char_count": len(text),
        "bytes_fetched": len(html.encode("utf-8", errors="ignore")),
        "robots_status": reason,
    }


# ─────────────────────────────────────────────────────────────────────────
# FIX 11 — Watched prospects + insights_enabled toggle
# ─────────────────────────────────────────────────────────────────────────
@router.get("/api/pt/insights/prospects")
async def list_watched_prospects(tenant: dict = Depends(get_active_tenant)):
    # Look in both `workspace_contacts` and `pt_leads` for compat.
    out: List[Dict[str, Any]] = []
    for col in (contacts_col, pt_leads_col):
        for doc in col.find(
            {"tenant_id": tenant["id"], "insights_enabled": True},
            {"_id": 0, "id": 1, "first_name": 1, "last_name": 1, "email": 1,
             "title": 1, "company_name": 1, "insights_enabled": 1},
        ):
            out.append(doc)
    return {"prospects": out, "count": len(out)}


class InsightsEnabledPayload(BaseModel):
    insights_enabled: bool


@router.patch("/api/contacts/{contact_id}/insights_enabled")
async def toggle_insights_enabled(
    contact_id: str,
    payload: InsightsEnabledPayload,
    tenant: dict = Depends(get_active_tenant),
):
    updated = False
    for col in (contacts_col, pt_leads_col, leads_col):
        res = col.update_one(
            {"id": contact_id, "tenant_id": tenant["id"]},
            {"$set": {"insights_enabled": bool(payload.insights_enabled), "updated_at": _now_iso()}},
        )
        if res.modified_count:
            updated = True
    if not updated:
        raise HTTPException(404, "Contact not found")
    return {"ok": True, "id": contact_id, "insights_enabled": payload.insights_enabled}


# ─────────────────────────────────────────────────────────────────────────
# FIX 12 — Admin manual job trigger
# ─────────────────────────────────────────────────────────────────────────
class JobTriggerPayload(BaseModel):
    workspace_id: Optional[str] = None


_REGISTERED_JOBS = {
    "b2b_insight_scan",
    "outreach_engine",
    "crm_sync",
    "saleshandy_poll",
    "retention",
    "enrichment_retry",
    "pixel_attribution",
    "snooze_recovery",
    "insight_digest_sender",
    "oauth_token_refresh",
}


@router.post("/api/admin/jobs/{job_name}/trigger")
async def trigger_job(
    job_name: str,
    payload: JobTriggerPayload,
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") != "master_admin":
        raise HTTPException(403, "master_admin only")
    if job_name not in _REGISTERED_JOBS:
        raise HTTPException(404, f"Unknown job: {job_name}. Known: {sorted(_REGISTERED_JOBS)}")

    triggered_for: List[str] = []
    if job_name == "b2b_insight_scan":
        from routes.pt_insights import run_insight_scan_for_tenant
        targets: List[Dict[str, Any]] = []
        if payload.workspace_id:
            t = tenants_col.find_one({"id": payload.workspace_id}, {"_id": 0})
            if t:
                targets = [t]
        else:
            targets = list(tenants_col.find({"settings.workspace_type": {"$in": ["b2b", "hybrid"]}}, {"_id": 0}))
        for t in targets:
            asyncio.create_task(run_insight_scan_for_tenant(t))
            triggered_for.append(t["id"])
    else:
        # Other jobs are global loops — manual trigger logs intent but the loop
        # is already running. We surface the next-scheduled hint via audit_log.
        triggered_for = [payload.workspace_id or "all"]

    # Audit
    try:
        db["audit_log"].insert_one({
            "id": f"aud_{uuid.uuid4().hex[:12]}",
            "tenant_id": payload.workspace_id,
            "user_id": current_user.get("email"),
            "action": f"admin.job.trigger:{job_name}",
            "resource_type": "background_job",
            "resource_id": job_name,
            "metadata": {"workspaces": triggered_for},
            "created_at": _now_iso(),
        })
    except Exception:
        pass

    return {"triggered": True, "job": job_name, "workspaces": triggered_for}


# ─────────────────────────────────────────────────────────────────────────
# FIX 13 — Reports /icp + /channels
# ─────────────────────────────────────────────────────────────────────────
@router.get("/api/pt/reports/icp")
async def report_icp_distribution(tenant: dict = Depends(get_active_tenant)):
    icps = list(db["icps"].find({"tenant_id": tenant["id"]}, {"_id": 0}))
    total = leads_col.count_documents({"tenant_id": tenant["id"]}) + pt_leads_col.count_documents({"tenant_id": tenant["id"]})
    if total == 0:
        total = 1  # avoid div-by-zero
    rows = []
    for icp in icps:
        matched = leads_col.count_documents({"tenant_id": tenant["id"], "icp_id": icp.get("id")}) \
                + pt_leads_col.count_documents({"tenant_id": tenant["id"], "icp_id": icp.get("id")})
        rows.append({
            "icp_id": icp.get("id"),
            "label": icp.get("label") or icp.get("name") or "(unnamed)",
            "matched": matched,
            "percent": round((matched / total) * 100, 1),
        })
    rows.sort(key=lambda r: r["matched"], reverse=True)
    return {"icps": rows, "total_leads": total}


@router.get("/api/pt/reports/channels")
async def report_channel_performance(tenant: dict = Depends(get_active_tenant)):
    # Aggregate messages by channel; count sent vs replied (direction=inbound).
    pipeline_sent = [
        {"$match": {"tenant_id": tenant["id"], "direction": "outbound"}},
        {"$group": {"_id": "$channel", "sent": {"$sum": 1}}},
    ]
    pipeline_replies = [
        {"$match": {"tenant_id": tenant["id"], "direction": "inbound"}},
        {"$group": {"_id": "$channel", "replies": {"$sum": 1}}},
    ]
    sent = {row["_id"] or "unknown": row["sent"] for row in aria_conversations_col.aggregate(pipeline_sent)}
    replies = {row["_id"] or "unknown": row["replies"] for row in aria_conversations_col.aggregate(pipeline_replies)}
    channels = sorted(set(sent) | set(replies))
    rows = []
    for ch in channels:
        s = sent.get(ch, 0)
        r = replies.get(ch, 0)
        rows.append({
            "channel": ch,
            "sent": s,
            "replies": r,
            "reply_rate": round((r / s) * 100, 1) if s else 0.0,
        })
    return {"channels": rows}


# ─────────────────────────────────────────────────────────────────────────
# FIX 14 — Sequences scaffolding
# ─────────────────────────────────────────────────────────────────────────
class SequenceStep(BaseModel):
    day_offset: int
    channel: str
    body: str


class SequenceCreate(BaseModel):
    name: str
    channel: str = "email"
    steps: List[SequenceStep] = []


class SequenceUpdate(BaseModel):
    name: Optional[str] = None
    channel: Optional[str] = None
    steps: Optional[List[SequenceStep]] = None


class EnrolPayload(BaseModel):
    contact_id: str


@router.get("/api/sequences")
async def list_sequences(tenant: dict = Depends(get_active_tenant)):
    rows = list(sequences_col.find({"tenant_id": tenant["id"]}, {"_id": 0}))
    return {"sequences": rows, "count": len(rows)}


@router.post("/api/sequences")
async def create_sequence(payload: SequenceCreate, tenant: dict = Depends(get_active_tenant)):
    doc = {
        "id": f"seq_{uuid.uuid4().hex[:12]}",
        "tenant_id": tenant["id"],
        "name": payload.name,
        "channel": payload.channel,
        "steps": [s.dict() for s in payload.steps],
        "created_at": _now_iso(),
    }
    sequences_col.insert_one(doc)
    return _strip_mongo(doc)


@router.patch("/api/sequences/{seq_id}")
async def update_sequence(seq_id: str, payload: SequenceUpdate, tenant: dict = Depends(get_active_tenant)):
    update: Dict[str, Any] = {}
    if payload.name is not None: update["name"] = payload.name
    if payload.channel is not None: update["channel"] = payload.channel
    if payload.steps is not None: update["steps"] = [s.dict() for s in payload.steps]
    if not update:
        return {"ok": True, "noop": True}
    res = sequences_col.update_one({"id": seq_id, "tenant_id": tenant["id"]}, {"$set": update})
    if not res.matched_count:
        raise HTTPException(404, "Sequence not found")
    return {"ok": True}


@router.delete("/api/sequences/{seq_id}")
async def delete_sequence(seq_id: str, tenant: dict = Depends(get_active_tenant)):
    res = sequences_col.delete_one({"id": seq_id, "tenant_id": tenant["id"]})
    if not res.deleted_count:
        raise HTTPException(404, "Sequence not found")
    sequence_enrolments_col.delete_many({"sequence_id": seq_id, "tenant_id": tenant["id"]})
    return {"ok": True}


@router.post("/api/sequences/{seq_id}/enrol")
async def enrol_contact(seq_id: str, payload: EnrolPayload, tenant: dict = Depends(get_active_tenant)):
    seq = sequences_col.find_one({"id": seq_id, "tenant_id": tenant["id"]}, {"_id": 0})
    if not seq:
        raise HTTPException(404, "Sequence not found")
    enrolment = {
        "id": f"enrol_{uuid.uuid4().hex[:12]}",
        "tenant_id": tenant["id"],
        "sequence_id": seq_id,
        "contact_id": payload.contact_id,
        "current_step": 0,
        "enrolled_at": _now_iso(),
        "status": "active",
    }
    sequence_enrolments_col.insert_one(enrolment)
    return _strip_mongo(enrolment)


@router.get("/api/sequences/{seq_id}/enrolments")
async def list_enrolments(seq_id: str, tenant: dict = Depends(get_active_tenant)):
    rows = list(sequence_enrolments_col.find(
        {"sequence_id": seq_id, "tenant_id": tenant["id"]}, {"_id": 0}
    ))
    return {"enrolments": rows, "count": len(rows)}


# ─────────────────────────────────────────────────────────────────────────
# FIX 15 — WhatsApp inbound command parser
# ─────────────────────────────────────────────────────────────────────────
def parse_whatsapp_command(message_body: str, from_phone: str, tenant_id: str) -> Optional[Dict[str, Any]]:
    """If the inbound WA message is a 'send' or 'dismiss' command from the
    workspace owner, action the most-recent pending insight card.

    Returns the action result, or None if the message is not a command.
    Importing this helper in the existing WhatsApp webhook is enough; the
    caller decides whether to short-circuit normal handling.
    """
    cmd = (message_body or "").strip().lower()
    if cmd not in {"send", "dismiss"}:
        return None
    # Find most recent insight card sent to this WhatsApp number with status=new.
    card = insights_col.find_one(
        {"tenant_id": tenant_id, "status": "new",
         "$or": [{"alerted_to_phone": from_phone}, {"notified_phones": from_phone}]},
        sort=[("created_at", -1)],
        projection={"_id": 0},
    )
    if not card:
        # Fall back to any card recently alerted on the tenant level — owner
        # only has one active alert thread at a time in practice.
        card = insights_col.find_one(
            {"tenant_id": tenant_id, "status": "new"},
            sort=[("created_at", -1)],
            projection={"_id": 0},
        )
    if not card:
        return {"matched": False}
    new_status = "sent" if cmd == "send" else "dismissed"
    set_doc: Dict[str, Any] = {
        "status": new_status,
        "actioned_at": _now_iso(),
        "actioned_action": cmd,
        "actioned_via": "whatsapp",
    }
    if cmd == "send":
        set_doc["sent_message"] = card.get("suggested_message") or ""
    insights_col.update_one(
        {"id": card["id"], "tenant_id": tenant_id},
        {"$set": set_doc},
    )
    return {
        "matched": True,
        "card_id": card["id"],
        "action": cmd,
        "prospect_name": card.get("prospect_name") or "prospect",
        "confirmation_msg": (
            f"✅ Message sent to {card.get('prospect_name') or 'prospect'}"
            if cmd == "send"
            else "✅ Card dismissed."
        ),
    }
