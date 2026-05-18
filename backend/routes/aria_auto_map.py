"""AI Journey Auto Mapper — Iter 55.

Takes an uploaded GTM/ICP document and returns a structured workflow that
maps cleanly into:
  - Multi-ICP collection (one or more ICPs detected)
  - Lead source map
  - Touchpoints with conditional logic (uses the same conditions schema as
    routes.outreach.validate_conditions so it round-trips into both the
    32-touchpoint Journey and the Outreach Campaign builder)
  - Qualification logic + handoff rules
  - Recommended workflow summary (plain-English).

UX pattern:
  1. POST /api/aria/auto-map/analyze  ← upload doc, return preview JSON
  2. POST /api/aria/auto-map/publish  ← user confirms; we persist ICPs + touchpoints
  3. POST /api/aria/auto-map/improve  ← Claude suggests gaps in current workflow

This is purely additive — never overwrites a touchpoint map without the user
explicitly clicking "Publish Workflow", and never touches existing ICPs without
the user's go-ahead (publish creates new ICPs; it never deletes existing ones).
"""
from __future__ import annotations

import io
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from deps import db, leads_collection
from routes.tenants import get_active_tenant
from routes.icps import _new_id as _new_icp_id, icps_col
from routes.outreach import validate_conditions
from routes.touchpoints import _validate_touchpoints, Touchpoint, maps_col, templates_col
from routes.auth import get_current_user

router = APIRouter(prefix="/api/aria/auto-map", tags=["aria-auto-map"])

ALLOWED_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "text/plain",
    "text/csv",
}
MAX_BYTES = 10 * 1024 * 1024


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _scrub(doc: Optional[dict]) -> Optional[dict]:
    if not doc:
        return doc
    return {k: v for k, v in doc.items() if k != "_id"}


# ─── Document → text extraction ─────────────────────────────────────────────
def _extract_text(filename: str, content: bytes) -> str:
    """Best-effort text extraction. Returns "" on any failure — caller decides
    what to do with empty output. Logs the failure cause for ops debugging."""
    name = (filename or "").lower()
    try:
        if name.endswith(".pdf"):
            try:
                from pypdf import PdfReader
            except ImportError:
                from PyPDF2 import PdfReader  # type: ignore
            reader = PdfReader(io.BytesIO(content))
            if getattr(reader, "is_encrypted", False):
                try:
                    reader.decrypt("")  # try empty password
                except Exception:
                    print(f"[auto-map] PDF encrypted, cannot read: {filename}")
                    return ""
            return "\n".join((p.extract_text() or "") for p in reader.pages)
        if name.endswith(".docx"):
            from docx import Document
            doc = Document(io.BytesIO(content))
            return "\n".join(p.text for p in doc.paragraphs if p.text)
        if name.endswith(".xlsx") or name.endswith(".xls"):
            from openpyxl import load_workbook
            wb = load_workbook(io.BytesIO(content), data_only=True)
            chunks = []
            for sheet in wb.sheetnames:
                ws = wb[sheet]
                for row in ws.iter_rows(values_only=True):
                    line = " | ".join(str(c) for c in row if c is not None)
                    if line.strip():
                        chunks.append(line)
            return "\n".join(chunks)
        # txt / csv / unknown → decode best effort
        return content.decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"[auto-map] text extraction failed for {filename}: {e}")
        return ""


# Max text sent to Claude. Beyond this we truncate to keep the LLM call under
# the proxy's connection timeout (~60s in production). 12k chars ≈ 4-5 pages
# of dense text — plenty to extract ICPs + touchpoints from a GTM doc, and
# fast enough on Haiku to consistently come back in < 30s.
MAX_TEXT_CHARS = 12000


# ─── Claude prompt ──────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are Aria, an AI sales architect. The user uploads a GTM/sales/strategy/ICP document.
Your job: read it carefully and return a STRICT JSON object that maps the document to a working sales workflow.

OUTPUT FORMAT — return ONLY this JSON, nothing else:
{
  "icps": [
    {
      "label": "short name like 'CFO at Series B SaaS'",
      "title_targets": ["CFO", "VP Finance"],
      "industry": "string or empty",
      "company_size": "string or empty (e.g. '50-200 employees')",
      "geography": "string or empty",
      "pain_point": "1-2 sentences of the buyer's biggest pain",
      "value_prop": "1-2 sentences of what you sell them",
      "tone": "professional | casual | bold",
      "deal_size": "string or empty"
    }
  ],
  "lead_sources": ["Website Form", "Meta Ads", "LinkedIn", "..."],
  "recommended_integrations": ["saleshandy", "lemlist", "zoho_crm", "calendly", "..."],
  "sales_channels": ["email", "linkedin", "whatsapp", "phone"],
  "touchpoints": [
    {
      "step": 1,
      "channel": "whatsapp | email | linkedin_nudge | call_reminder",
      "message_type": "intro | qualifier | value_drop | follow_up | social_proof | soft_cta | hard_cta",
      "day": 0,
      "hour": 9,
      "aria_role": "autonomous | alert_human",
      "message_template": "the actual message text with {{first_name}} {{company}} {{value_prop}} tokens",
      "conditions": {
        "on_reply": {"action": "notify_user"},
        "on_keyword_match": {"keywords": ["interested","pricing"], "action": "tag_contact", "tag": "hot_lead"},
        "on_negative_keyword": {"keywords": ["not interested","stop"], "action": "stop"},
        "on_no_reply": {"after_hours": 72, "action": "move_to_step", "target_step": 2}
      }
    }
  ],
  "qualification": {
    "must_have_criteria": ["Budget > $X", "Decision-maker title"],
    "disqualifiers": ["Outside geo", "<10 employees"],
    "qualifying_questions": ["What's your timeline?", "Who decides?"]
  },
  "handoff": {
    "trigger": "When lead replies positively AND mentions pricing",
    "alert_channels": ["whatsapp", "email"],
    "info_passed": ["lead name", "company", "last reply", "intent score"]
  },
  "summary": "Aria found N ICPs, M lead sources, K touchpoints, J branches. One-paragraph plain-English overview."
}

RULES:
- Generate 3-12 touchpoints (not just 1). Stagger days realistically (Day 0, 1, 3, 7, 14, etc.).
- At least 2 touchpoints MUST have meaningful conditions (on_reply / on_keyword_match / on_no_reply).
- Use the EXACT condition schema above (action values must be one of: move_to_step, notify_user, tag_contact, stop; on_no_reply only allows move_to_step or stop).
- If the doc doesn't mention some field, infer a sensible default — never invent numbers (e.g. don't say "$500k ARR" if the doc didn't say it).
- channel must be one of: whatsapp, email, linkedin_nudge, call_reminder.
- All message_template strings must use {{first_name}}, {{company}}, {{value_prop}}, {{pain_point}} tokens where natural.
- Return AT MOST 3 ICPs. If only one buyer type is mentioned, return 1.
- recommended_integrations — name specific tools you saw in the doc (saleshandy, lemlist, zoho_crm, hubspot, salesforce, calendly, slack, gmail, outlook, zoom, instantly, apollo, phantombuster). Use lowercase keys.
- sales_channels — top-level channel preferences this team will use, from: email, linkedin, whatsapp, sms, phone, website_chat.
- DO NOT wrap the JSON in ```json blocks. Output the raw JSON object directly."""


async def _claude_analyze(text: str) -> Dict[str, Any]:
    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Aria's brain is offline (EMERGENT_LLM_KEY missing)")
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Could not extract any text from the document")
    # Truncate to keep within token budget (caller already truncates to MAX_TEXT_CHARS;
    # this is a defensive second cap).
    excerpt = text[:MAX_TEXT_CHARS]
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except ImportError:
        raise HTTPException(status_code=503, detail="LLM library not available")

    # Use Haiku 4.5 — ~3-5x faster than Sonnet for structured JSON extraction
    # and well within the 60s production-ingress budget. Sonnet was timing out
    # on production for docs near MAX_TEXT_CHARS.
    chat = LlmChat(
        api_key=api_key,
        session_id=f"automap-{uuid.uuid4().hex[:10]}",
        system_message=SYSTEM_PROMPT,
    ).with_model("anthropic", "claude-haiku-4-5-20251001")

    user_msg = f"Here is the document content. Build the workflow JSON:\n\n---DOC START---\n{excerpt}\n---DOC END---"
    try:
        raw = await chat.send_message(UserMessage(text=user_msg))
    except Exception as e:
        print(f"[auto-map] Claude error: {e}")
        raise HTTPException(
            status_code=502,
            detail="Aria's brain took too long to respond. Try uploading a shorter document or retry in a moment.",
        )
    raw = (raw or "").strip()
    if raw.startswith("```"):
        # Strip code fence if Claude wraps anyway
        raw = raw.split("```", 2)[1] if raw.count("```") >= 2 else raw
        if raw.startswith("json"):
            raw = raw[4:].strip()
        raw = raw.rstrip("`").strip()
    # Find the first { and last } to be extra robust
    s = raw.find("{")
    e = raw.rfind("}")
    if s == -1 or e == -1:
        raise HTTPException(status_code=502, detail="Aria couldn't structure the document — try a cleaner doc.")
    try:
        return json.loads(raw[s:e + 1])
    except json.JSONDecodeError as ex:
        raise HTTPException(status_code=502, detail=f"Aria returned malformed JSON: {ex}")


def _sanitize_touchpoints(raw_tps: List[dict]) -> List[dict]:
    """Apply schema clamps so Pydantic Touchpoint accepts whatever Claude returns."""
    ALLOWED_CHANNELS = {"whatsapp", "email", "linkedin_nudge", "call_reminder"}
    ALLOWED_TYPES_TP = {
        "intro", "qualifier", "value_drop", "value_add", "follow_up",
        "social_proof", "soft_cta", "hard_cta", "objection_handle",
        "demo_invite", "calendar_nudge", "founder_handoff", "re_engage",
        "new_offer", "archive",
    }
    ALLOWED_ROLES = {"autonomous", "alert_human"}
    out = []
    for i, tp in enumerate(raw_tps[:32]):
        channel = tp.get("channel") or "whatsapp"
        if channel not in ALLOWED_CHANNELS:
            channel = "whatsapp"
        message_type = tp.get("message_type") or "intro"
        if message_type not in ALLOWED_TYPES_TP:
            message_type = "intro"
        aria_role = tp.get("aria_role") or "autonomous"
        if aria_role not in ALLOWED_ROLES:
            aria_role = "autonomous"
        try:
            day = float(tp.get("day", i))
        except (TypeError, ValueError):
            day = float(i)
        try:
            hour = int(tp.get("hour", 9))
            hour = max(0, min(23, hour))
        except (TypeError, ValueError):
            hour = 9
        try:
            conditions = validate_conditions(tp.get("conditions") or {})
        except HTTPException:
            # If Claude returned slightly off conditions, drop them rather than fail the whole map
            conditions = {}
        out.append({
            "index": i,
            "day": day,
            "hour": hour,
            "channel": channel,
            "message_type": message_type,
            "aria_role": aria_role,
            "trigger": tp.get("trigger") or "",
            "message_template": (tp.get("message_template") or "").strip() or f"Day {int(day)}: Hi {{{{first_name}}}}, …",
            "conditions": conditions,
        })
    return out


def _sanitize_icps(raw_icps: List[dict]) -> List[dict]:
    ALLOWED_TONES = {"professional", "casual", "bold"}
    out = []
    for icp in (raw_icps or [])[:3]:
        tone = (icp.get("tone") or "professional").lower()
        if tone not in ALLOWED_TONES:
            tone = "professional"
        out.append({
            "label": (icp.get("label") or "Untitled ICP").strip()[:120],
            "title_targets": [str(t).strip() for t in (icp.get("title_targets") or []) if str(t).strip()][:20],
            "industry": (icp.get("industry") or "").strip(),
            "company_size": (icp.get("company_size") or "").strip(),
            "geography": (icp.get("geography") or "").strip(),
            "pain_point": (icp.get("pain_point") or "").strip(),
            "value_prop": (icp.get("value_prop") or "").strip(),
            "tone": tone,
            "deal_size": (icp.get("deal_size") or "").strip(),
        })
    return out


# ─── Endpoints ──────────────────────────────────────────────────────────────
@router.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    tenant: dict = Depends(get_active_tenant),
):
    """Upload a GTM/ICP doc and return a structured PREVIEW (no persistence).

    User reviews/edits the preview, then calls /publish to commit.
    """
    role = tenant.get("_member_role")
    if role not in ("owner", "admin", "member"):
        raise HTTPException(status_code=403, detail="Not allowed")

    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=400, detail=f"File over {MAX_BYTES // (1024 * 1024)}MB")
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")
    name = file.filename.lower()
    if not (name.endswith(".pdf") or name.endswith(".docx") or name.endswith(".xlsx")
            or name.endswith(".xls") or name.endswith(".txt") or name.endswith(".csv")):
        raise HTTPException(status_code=400, detail="Unsupported file format. Use PDF, DOCX, XLSX, TXT, or CSV.")

    text = _extract_text(file.filename, content)
    char_count = len(text.strip())
    if char_count < 50:
        # Helpful per-format guidance — most common cause is scanned PDFs
        name = file.filename.lower()
        if name.endswith(".pdf"):
            hint = (
                "Aria couldn't read any text from this PDF. It looks like a scanned image or password-protected file. "
                "Try one of: (1) export your doc as DOCX or TXT, (2) copy-paste the content into a .txt file, "
                "or (3) run OCR on the PDF first."
            )
        elif name.endswith(".docx") or name.endswith(".xlsx") or name.endswith(".xls"):
            hint = (
                f"Aria couldn't read text from this {name.rsplit('.', 1)[-1].upper()} — only "
                f"{char_count} chars extracted. The file may be empty or use unusual formatting. "
                "Try saving it as plain text (.txt) and re-uploading."
            )
        else:
            hint = (
                f"Aria only found {char_count} chars in this file. Make sure it contains GTM/sales content — "
                "ICPs, lead sources, follow-up sequences."
            )
        raise HTTPException(status_code=400, detail=hint)

    # Cap to keep Claude under the 60s proxy budget. Take the head — GTM docs
    # usually lead with the most important content.
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS] + "\n\n[...truncated for length...]"

    parsed = await _claude_analyze(text)

    icps = _sanitize_icps(parsed.get("icps") or [])
    touchpoints = _sanitize_touchpoints(parsed.get("touchpoints") or [])
    lead_sources = [str(s).strip() for s in (parsed.get("lead_sources") or []) if str(s).strip()][:20]
    # New (iter 69): integration & channel recommendations Aria infers from the doc.
    recommended_integrations = [str(s).strip().lower() for s in (parsed.get("recommended_integrations") or []) if str(s).strip()][:15]
    sales_channels = [str(s).strip().lower() for s in (parsed.get("sales_channels") or []) if str(s).strip()][:10]
    # Whitelist to keys our /api/tenant/sales-channels endpoint understands.
    valid_channel_keys = {"email", "linkedin", "whatsapp", "sms", "phone", "website_chat"}
    sales_channels = [c for c in sales_channels if c in valid_channel_keys]
    qualification = parsed.get("qualification") or {}
    handoff = parsed.get("handoff") or {}
    summary = (parsed.get("summary") or "").strip()

    # If Claude found nothing actionable, surface that clearly instead of returning
    # a hollow success that confuses the user. (Resolves: "Aria is not able to map
    # the touchpoints".)
    if not touchpoints and not icps:
        raise HTTPException(
            status_code=422,
            detail=(
                "Aria read the document but couldn't find any sales touchpoints or ICPs to map. "
                "Make sure the doc describes your buyer (titles/industry/pain) and a follow-up sequence "
                "(channels, days, message types). A short bulleted GTM brief usually works best."
            ),
        )

    return {
        "source_filename": file.filename,
        "extracted": {
            "icps": icps,
            "lead_sources": lead_sources,
            "recommended_integrations": recommended_integrations,
            "sales_channels": sales_channels,
            "touchpoints": touchpoints,
            "qualification": qualification,
            "handoff": handoff,
            "summary": summary or f"Aria found {len(icps)} ICP(s), {len(lead_sources)} lead source(s), {len(touchpoints)} touchpoints.",
        },
        "doc_excerpt_chars": len(text),
    }


class PublishPayload(BaseModel):
    icps: List[Dict[str, Any]] = []
    touchpoints: List[Dict[str, Any]] = []
    lead_sources: List[str] = []
    recommended_integrations: List[str] = []
    sales_channels: List[str] = []
    qualification: Optional[Dict[str, Any]] = None
    handoff: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None
    overwrite_journey: bool = True   # if true, replaces the 32-touchpoint map
    apply_sales_channels: bool = True  # if true, saves sales_channels to /tenant/sales-channels prefs


@router.post("/publish")
async def publish(
    payload: PublishPayload,
    tenant: dict = Depends(get_active_tenant),
    current_user: dict = Depends(get_current_user),
):
    """Persist the (possibly user-edited) workflow.

    - Creates any ICPs that don't already exist (matched by label, case-insensitive).
    - Optionally replaces the 32-touchpoint journey with the new sequence.
    - Stores the extracted lead_sources + qualification + handoff into the tenant's
      settings under `automap_summary` so the dashboard can render them.
    """
    role = tenant.get("_member_role")
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")

    tenant_id = tenant["id"]
    created_icp_ids: List[str] = []
    skipped_icps: List[str] = []

    # 1. ICPs — create if absent
    for icp in (payload.icps or []):
        label = (icp.get("label") or "").strip()
        if not label:
            continue
        existing = icps_col.find_one({
            "tenant_id": tenant_id,
            "label": {"$regex": f"^{label}$", "$options": "i"},
        })
        if existing:
            skipped_icps.append(label)
            continue
        doc = {
            "id": _new_icp_id(),
            "tenant_id": tenant_id,
            "label": label,
            "title_targets": icp.get("title_targets") or [],
            "industry": icp.get("industry") or "",
            "company_size": icp.get("company_size") or "",
            "pain_point": icp.get("pain_point") or "",
            "value_prop": icp.get("value_prop") or "",
            "tone": icp.get("tone") or "professional",
            "deal_size": icp.get("deal_size") or "",
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        icps_col.insert_one(doc)
        created_icp_ids.append(doc["id"])

    # 2. Touchpoints — replace the journey (if user said overwrite_journey=true)
    saved_touchpoint_count = 0
    if payload.overwrite_journey and payload.touchpoints:
        # Wrap in Pydantic model so the validator runs the same way as /api/touchpoints/map
        pydantic_tps = [Touchpoint(**tp) for tp in payload.touchpoints]
        _validate_touchpoints(pydantic_tps)
        cleaned = []
        for i, t in enumerate(pydantic_tps):
            cleaned.append({
                "index": i,
                "day": float(t.day),
                "hour": int(t.hour),
                "channel": t.channel,
                "message_type": t.message_type,
                "aria_role": t.aria_role,
                "trigger": (t.trigger or "").strip(),
                "message_template": t.message_template.strip(),
                "conditions": t.conditions or {},
            })
        template = templates_col.find_one({"id": "tpl_automap"}, {"_id": 0, "name": 1, "duration_days": 1}) or {
            "name": "AI Auto-Mapped",
            "duration_days": int(max((tp["day"] for tp in cleaned), default=0) + 1),
        }
        doc = {
            "tenant_id": tenant_id,
            "template_id": "tpl_automap",
            "template_name": template.get("name") or "AI Auto-Mapped",
            "is_customised": True,
            "touchpoints": cleaned,
            "touchpoint_count": len(cleaned),
            "duration_days": template.get("duration_days"),
            "saved_by": current_user.get("email"),
            "updated_at": _now_iso(),
            "created_at": _now_iso(),
        }
        maps_col.update_one({"tenant_id": tenant_id}, {"$set": doc}, upsert=True)
        saved_touchpoint_count = len(cleaned)

    # 3. Stash lead_sources + qualification + handoff + summary onto tenant.settings.automap_summary
    db["tenants"].update_one(
        {"id": tenant_id},
        {"$set": {
            "settings.automap_summary": {
                "lead_sources": payload.lead_sources or [],
                "recommended_integrations": payload.recommended_integrations or [],
                "qualification": payload.qualification or {},
                "handoff": payload.handoff or {},
                "summary": payload.summary or "",
                "applied_at": _now_iso(),
                "applied_by": current_user.get("email"),
            },
        }},
    )

    # 4. Optionally write Aria-inferred sales-channel preferences. Skips when the
    # user opted out OR Aria didn't extract any channels. Stored on the same
    # tenants.settings.sales_channels path the Settings UI reads.
    saved_channels: List[str] = []
    if payload.apply_sales_channels and payload.sales_channels:
        from routes.sales_channels import CHANNELS as _CH
        valid_keys = {c["key"] for c in _CH}
        saved_channels = [c for c in payload.sales_channels if c in valid_keys]
        if saved_channels:
            prefs = {
                "selected_channels": saved_channels,
                "priority_order": saved_channels,
                "primary_channel": saved_channels[0],
                "fallback_channels": saved_channels[1:],
                "conversation_style": None,
                "selected_preset": None,
                "disabled_channels": [k for k in valid_keys if k not in saved_channels],
                "updated_at": _now_iso(),
                "source": "automap",
            }
            db["tenants"].update_one(
                {"id": tenant_id},
                {"$set": {"settings.sales_channels": prefs}},
            )

    return {
        "ok": True,
        "icps_created": len(created_icp_ids),
        "icps_skipped": skipped_icps,
        "created_icp_ids": created_icp_ids,
        "touchpoints_saved": saved_touchpoint_count,
        "lead_sources_count": len(payload.lead_sources or []),
        "recommended_integrations": payload.recommended_integrations or [],
        "sales_channels_saved": saved_channels,
    }


class ImprovePayload(BaseModel):
    """The user-edited workflow snapshot (preview); we ask Claude for gaps."""
    icps: List[Dict[str, Any]] = []
    touchpoints: List[Dict[str, Any]] = []
    lead_sources: List[str] = []
    qualification: Optional[Dict[str, Any]] = None
    handoff: Optional[Dict[str, Any]] = None


@router.post("/diff")
async def diff(payload: ImprovePayload, tenant: dict = Depends(get_active_tenant)):
    """Compare the just-extracted preview against the workspace's CURRENT published
    workflow (existing ICPs + current touchpoint map). Returns a human-readable
    diff so the user can see exactly what would change if they re-publish.
    """
    tenant_id = tenant["id"]
    # Current ICPs
    current_icps = [_scrub(d) for d in icps_col.find({"tenant_id": tenant_id})]
    current_icp_labels = {(i.get("label") or "").lower() for i in current_icps}

    # Current touchpoint map
    tmap = db["workspace_touchpoint_maps"].find_one({"tenant_id": tenant_id}, {"_id": 0}) or {}
    current_tps = tmap.get("touchpoints", [])

    new_icps = payload.icps or []
    new_tps = payload.touchpoints or []

    icp_changes = []
    for icp in new_icps:
        lab = (icp.get("label") or "").lower()
        if lab and lab not in current_icp_labels:
            icp_changes.append({"action": "create", "label": icp.get("label")})
        else:
            icp_changes.append({"action": "skip_exists", "label": icp.get("label")})

    tp_diff = {
        "current_count": len(current_tps),
        "new_count": len(new_tps),
        "delta": len(new_tps) - len(current_tps),
        "current_channels": sorted({tp.get("channel") for tp in current_tps if tp.get("channel")}),
        "new_channels": sorted({tp.get("channel") for tp in new_tps if tp.get("channel")}),
        "new_with_conditions": sum(1 for tp in new_tps if tp.get("conditions")),
        "current_with_conditions": sum(1 for tp in current_tps if tp.get("conditions")),
    }

    return {
        "icp_changes": icp_changes,
        "touchpoint_diff": tp_diff,
        "summary": (
            f"{sum(1 for c in icp_changes if c['action'] == 'create')} new ICP(s), "
            f"{sum(1 for c in icp_changes if c['action'] == 'skip_exists')} already exist. "
            f"Touchpoint count changes from {tp_diff['current_count']} → {tp_diff['new_count']} "
            f"({'+' if tp_diff['delta'] >= 0 else ''}{tp_diff['delta']}). "
            f"Branching coverage: {tp_diff['current_with_conditions']} → {tp_diff['new_with_conditions']} steps with conditions."
        ),
    }


@router.post("/improve")
async def improve(payload: ImprovePayload, tenant: dict = Depends(get_active_tenant)):
    """Send the workflow back to Claude and ask for gap analysis.

    Returns a list of suggestions, each shaped:
      {"type": "missing_channel|missing_logic|missing_qualification|missing_handoff|missing_nurture",
       "message": "human-readable suggestion",
       "fix_hint": "optional concrete fix"}
    """
    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Aria's brain is offline")

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except ImportError:
        raise HTTPException(status_code=503, detail="LLM library not available")

    system = (
        "You are Aria, a senior B2B sales architect. Review the workflow JSON and find gaps. "
        "Return STRICT JSON: {\"suggestions\": [{\"type\":\"...\",\"message\":\"...\",\"fix_hint\":\"...\"}]}. "
        "Suggestion types: missing_channel, missing_logic, missing_qualification, missing_handoff, missing_nurture, message_quality. "
        "Output 3-7 suggestions max. No prose outside the JSON. Be specific and actionable."
    )
    user_msg = "Review this sales workflow and surface gaps:\n\n" + json.dumps({
        "icps": payload.icps,
        "touchpoints": payload.touchpoints,
        "lead_sources": payload.lead_sources,
        "qualification": payload.qualification,
        "handoff": payload.handoff,
    }, indent=2)[:14000]

    chat = LlmChat(
        api_key=api_key,
        session_id=f"improve-{uuid.uuid4().hex[:10]}",
        system_message=system,
    ).with_model("anthropic", "claude-haiku-4-5-20251001")

    try:
        raw = (await chat.send_message(UserMessage(text=user_msg)) or "").strip()
    except Exception as e:
        print(f"[auto-map/improve] Claude error: {e}")
        return {"suggestions": []}
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1] if raw.count("```") >= 2 else raw
        if raw.startswith("json"):
            raw = raw[4:].strip()
        raw = raw.rstrip("`").strip()
    s = raw.find("{")
    e = raw.rfind("}")
    if s == -1 or e == -1:
        return {"suggestions": []}
    try:
        parsed = json.loads(raw[s:e + 1])
        return {"suggestions": parsed.get("suggestions", [])[:10]}
    except json.JSONDecodeError:
        return {"suggestions": []}
