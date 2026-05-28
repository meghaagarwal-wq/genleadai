"""Aria Master Training Profile + Dynamic System Prompt Assembly (Phase 1 + 2).

Implements the v2 master prompt described in /app/memory/ARIA_MASTER_SPEC.md.
The workspace owner trains Aria once (via document upload or manual edits);
this module turns that training data into a fully-assembled system prompt
that's stored Fernet-encrypted on the tenant and injected as the system
message on every Aria conversation.

Endpoints
─────────
GET  /api/aria/training-profile                    — current training data (decrypted)
PUT  /api/aria/training-profile                    — replace training fields, re-assemble + encrypt
GET  /api/aria/system-prompt-preview               — preview the assembled prompt as plain text
POST /api/aria/training-profile/reassemble         — force a re-assembly (no data change)
POST /api/aria/training-profile/extract-from-document — upload a doc, extract fields via Claude (strict JSON), merge into profile
POST /api/aria/training-profile/auto-train-from-workspace — seed profile from existing business_profile + icps collection
GET  /api/aria/workspace-type                      — current workspace_type
PUT  /api/aria/workspace-type                      — set b2b | b2c | hybrid

Storage
───────
tenants.settings.workspace_type       — "b2b" | "b2c" | "hybrid"
tenants.settings.aria_training_profile = {
    "data": { ... extracted fields ... },     # raw training data
    "assembled_prompt": "enc::...",            # Fernet-encrypted full prompt
    "assembled_at": ISO,
    "version": 1
}
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import db
from security.encryption import encrypt, decrypt
from routes.tenants import get_active_tenant, require_tenant_role

router = APIRouter(prefix="/api/aria", tags=["aria-training"])

tenants_col = db["tenants"]

WORKSPACE_TYPES = ("b2b", "b2c", "hybrid")


# ─── Default profile shape ──────────────────────────────────────────────
def _empty_profile() -> Dict[str, Any]:
    """A blank training profile with every field present and typed.

    Fields default to empty strings / empty lists so the assembler can
    decide whether to render or comment out each section.
    """
    return {
        # Section 1 — Business Identity
        "what_you_sell": "",
        "who_you_sell_to": "",
        "problem_you_solve": "",
        "differentiator": "",
        "services_or_products": [],
        # Section 2 — ICPs (list of dicts — see _empty_icp())
        "icp_profiles": [],
        # Section 3 — Qualification
        "qualification_questions": [],
        "qualified_criteria": [],
        "low_priority_criteria": [],
        "book_call_trigger": "",
        "instinct_trigger": "",
        "automation_trigger": "",
        # Section 4 — Voice
        "brand_voice_style": "",
        "custom_tone_instructions": "",
        "founder_sample_message": "",
        # Section 5 — Objections
        "pricing_objection_responses": [],
        "timing_objection_responses": [],
        "trust_objection_responses": [],
        "competitor_responses": [],
        "custom_faq": [],  # [{question, answer}]
        # Section 6 — Booking
        "calendar_link": "",
        "booking_criteria": "",
        "pre_call_questions": [],
        "reminder_timing": "",
        "no_show_message": "",
        # Section 7 — B2B Insights config
        "auto_signal_actions": [],
        "approval_required_signals": [],
        "email_insights_enabled": False,
        "whatsapp_insights_enabled": False,
        "digest_time": "08:00",
        "digest_timezone": "Asia/Kolkata",
        # Section 9 — Knowledge base (free-form chunks)
        "knowledge_base_chunks": [],
    }


def _empty_icp() -> Dict[str, Any]:
    return {
        "icp_name": "",
        "target_industries": [],
        "target_titles_or_roles": [],
        "company_size": "",
        "geography": "",
        "budget_range": "",
        "high_intent_signals": [],
        "disqualification_signals": [],
        "relevant_resources": [],
    }


# ─── Prompt assembler ───────────────────────────────────────────────────
def _bullet(items: List[str], indent: str = "  - ") -> str:
    """Render a list as bullets; returns 'NOT_CONFIGURED' if empty."""
    cleaned = [str(x).strip() for x in (items or []) if str(x).strip()]
    if not cleaned:
        return "NOT_CONFIGURED"
    return "\n".join(f"{indent}{c}" for c in cleaned)


def _val(s: Optional[str]) -> str:
    s = (s or "").strip()
    return s if s else "NOT_CONFIGURED"


def _render_icp_block(icps: List[Dict[str, Any]]) -> str:
    """Render the ICP block from a list of ICP dicts."""
    if not icps:
        return "  - No ICPs configured yet."
    out: List[str] = []
    for i, icp in enumerate(icps, 1):
        out.append(f"ICP #{i}")
        out.append(f"  Name: {_val(icp.get('icp_name'))}")
        out.append(f"  Target industries: {', '.join(icp.get('target_industries') or []) or 'NOT_CONFIGURED'}")
        out.append(f"  Target titles/roles: {', '.join(icp.get('target_titles_or_roles') or []) or 'NOT_CONFIGURED'}")
        out.append(f"  Company size: {_val(icp.get('company_size'))}")
        out.append(f"  Geography: {_val(icp.get('geography'))}")
        out.append(f"  Budget range: {_val(icp.get('budget_range'))}")
        out.append(f"  High-intent signals: {', '.join(icp.get('high_intent_signals') or []) or 'NOT_CONFIGURED'}")
        out.append(f"  Disqualification signals: {', '.join(icp.get('disqualification_signals') or []) or 'NOT_CONFIGURED'}")
        out.append(f"  Relevant resources: {', '.join(icp.get('relevant_resources') or []) or 'NOT_CONFIGURED'}")
        out.append("")
    return "\n".join(out).rstrip()


def _render_faq(faq: List[Dict[str, str]]) -> str:
    cleaned = [
        (q.get("question", "").strip(), q.get("answer", "").strip())
        for q in (faq or [])
        if q.get("question") and q.get("answer")
    ]
    if not cleaned:
        return "NOT_CONFIGURED"
    return "\n".join(f"  Q: {q}\n  A: {a}" for q, a in cleaned)


def _render_kb(chunks: List[str]) -> str:
    cleaned = [str(c).strip() for c in (chunks or []) if str(c).strip()]
    if not cleaned:
        return "(No knowledge base content uploaded yet. Workspace owner will be alerted when leads ask out-of-scope questions.)"
    return "\n\n".join(f"--- KB chunk {i+1} ---\n{c}" for i, c in enumerate(cleaned))


def assemble_aria_prompt(
    workspace_name: str,
    founder_name: str,
    aria_name: str,
    workspace_type: str,
    profile: Dict[str, Any],
) -> str:
    """Build the full Aria system prompt from training data + workspace context.

    Implements the master template from ARIA_MASTER_SPEC.md. Section 7
    (B2B Insights Engine) is included only for `b2b` and `hybrid`
    workspaces; B2C workspaces get a streamlined prompt.
    """
    p = profile or _empty_profile()
    icps = p.get("icp_profiles") or []
    show_insights = workspace_type in ("b2b", "hybrid")

    sections: List[str] = []

    sections.append(
        f"You are {aria_name} — an AI Sales Intelligence Agent operating exclusively on behalf of {workspace_name}."
        f"\n\nYou are not a generic assistant. You think, qualify, respond, score, and act like {founder_name} "
        f"would — with precision, intent, and zero wasted words."
        f"\n\nCRITICAL — Brand integrity:"
        f"\n- You ALWAYS represent {workspace_name}. Never mention any other company by name as your employer."
        f"\n- Never call yourself 'a platform' or 'an AI sales platform' — you are {founder_name}'s assistant at {workspace_name}."
        f"\n- Never say 'GenLeadAI' unless that IS literally the workspace name above."
    )

    # ─── Section 1: Business Identity ───────────────────────────────────
    sections.append(
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "SECTION 1 — BUSINESS IDENTITY\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"What this business sells:         {_val(p.get('what_you_sell'))}\n"
        f"Who this business sells to:       {_val(p.get('who_you_sell_to'))}\n"
        f"Core problem solved:              {_val(p.get('problem_you_solve'))}\n"
        f"What makes this offer different:  {_val(p.get('differentiator'))}\n"
        f"Main services / products:         {', '.join(p.get('services_or_products') or []) or 'NOT_CONFIGURED'}"
    )

    # ─── Section 2: ICPs ────────────────────────────────────────────────
    sections.append(
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "SECTION 2 — IDEAL CUSTOMER PROFILES\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"This business has {len(icps)} defined ICP(s). Silently score every new lead "
        "against each ICP and assign the closest match. Use this to decide tone, "
        "resources, and next action.\n\n"
        f"{_render_icp_block(icps)}"
    )

    # ─── Section 3: Qualification ───────────────────────────────────────
    sections.append(
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "SECTION 3 — QUALIFICATION LOGIC\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Qualify every lead before any action is taken. Never book a call with an "
        "unqualified lead. Never send a proposal to a cold lead.\n\n"
        f"Questions ARIA asks to qualify:\n{_bullet(p.get('qualification_questions'))}\n\n"
        f"A lead is QUALIFIED when:\n{_bullet(p.get('qualified_criteria'))}\n\n"
        f"A lead is LOW-PRIORITY when:\n{_bullet(p.get('low_priority_criteria'))}\n\n"
        f"ARIA books a call when: {_val(p.get('book_call_trigger'))}\n"
        f"ARIA triggers INSTINCT when: {_val(p.get('instinct_trigger'))}\n"
        f"ARIA triggers AUTOMATION when: {_val(p.get('automation_trigger'))}\n\n"
        "INSTINCT actions are automated responses executed independently: send a resource, "
        "drop a nurture message, tag for sequence, trigger a workflow.\n"
        "AUTOMATION actions are pre-configured workflow triggers: enrol in sequence, "
        "update CRM, send webhook, tag and route.\n"
        "Aria never escalates to a human by default — she either acts (instinct) or "
        "automates (workflow). The workspace owner is alerted only when explicitly configured."
    )

    # ─── Section 4: Voice ───────────────────────────────────────────────
    sections.append(
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "SECTION 4 — BRAND VOICE\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Voice style:               {_val(p.get('brand_voice_style'))}\n"
        f"Custom tone instructions:  {_val(p.get('custom_tone_instructions'))}\n\n"
        f"Sample message approved by {founder_name}:\n{_val(p.get('founder_sample_message'))}\n\n"
        f"Write like {founder_name} would write. Avoid corporate filler. Avoid "
        "over-explanation. Match energy to the lead's communication style once detected."
    )

    # ─── Section 5: Objections ──────────────────────────────────────────
    sections.append(
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "SECTION 5 — OBJECTION HANDLING\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "When a lead raises an objection, never freeze, deflect, or over-apologise. "
        "Address it with confidence.\n\n"
        f"Pricing objections:\n{_bullet(p.get('pricing_objection_responses'))}\n\n"
        f"Timing objections:\n{_bullet(p.get('timing_objection_responses'))}\n\n"
        f"Trust concerns:\n{_bullet(p.get('trust_objection_responses'))}\n\n"
        f"Competitor comparisons:\n{_bullet(p.get('competitor_responses'))}\n\n"
        f"Custom FAQ:\n{_render_faq(p.get('custom_faq'))}"
    )

    # ─── Section 6: Booking ─────────────────────────────────────────────
    sections.append(
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "SECTION 6 — BOOKING RULES\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Calendar link:     {_val(p.get('calendar_link'))}\n"
        f"Booking criteria:  {_val(p.get('booking_criteria'))}\n\n"
        f"Pre-call questions ARIA asks before confirming a booking:\n"
        f"{_bullet(p.get('pre_call_questions'))}\n\n"
        f"Reminder timing:    {_val(p.get('reminder_timing'))}\n"
        f"No-show message:    {_val(p.get('no_show_message'))}"
    )

    # ─── Section 7: B2B Insights Engine (conditional) ────────────────────
    if show_insights:
        sections.append(
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"SECTION 7 — B2B INSIGHTS ENGINE ({workspace_type.upper()} workspace)\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "You operate a daily intelligence layer over insights-enabled prospects.\n"
            "Surface the right moment, the right message, and the right resource to "
            f"{founder_name} so they can act with precision.\n\n"
            "Signal types you classify into (confidence ≥ 0.70 to surface):\n"
            "  deal_closed | funding_round | event_attending | job_change |\n"
            "  hiring_signal | content_published | company_news | social_activity\n\n"
            "ICP match weights for insights: Title 35% + Industry 30% + Company size 20% + Pain signal 15%.\n"
            "Surface only matches with score ≥ 0.65; below that, omit resource suggestion.\n\n"
            "Resource map by signal type:\n"
            "  deal_closed       → case study / social proof\n"
            "  funding_round     → ROI or growth capability overview\n"
            "  event_attending   → thought leadership / relevant whitepaper\n"
            "  job_change        → quick-win guide for that role\n"
            "  content_published → resource responding to their POV\n"
            "  company_news      → capability overview or case study\n"
            "  hiring_signal     → scalability / growth-stage resource\n"
            "  social_activity   → most directly relevant KB piece\n\n"
            f"Auto-instinct signals (no approval needed): {', '.join(p.get('auto_signal_actions') or []) or 'NONE — all require approval'}\n"
            f"Approval-required signals: {', '.join(p.get('approval_required_signals') or []) or 'all signals by default'}\n\n"
            f"Email digest enabled: {p.get('email_insights_enabled', False)} "
            f"({p.get('digest_time') or '08:00'} {p.get('digest_timezone') or 'Asia/Kolkata'})\n"
            f"WhatsApp alert enabled: {p.get('whatsapp_insights_enabled', False)} "
            "(only for signals ≥ 0.85 confidence)\n\n"
            "The insights engine NEVER contacts a prospect without owner approval, "
            "never surfaces signals < 0.70, never re-surfaces a 30-day-old signal, "
            "never fabricates intel, and never overrides do-not-contact flags."
        )

    # ─── Section 8: Never-do rules ──────────────────────────────────────
    sections.append(
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "SECTION 8 — WHAT ARIA NEVER DOES\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "- Never make up pricing, timelines, or capabilities not in the knowledge base.\n"
        "- Never book a call with a lead who hasn't cleared qualification criteria.\n"
        "- Never override a suppression / do-not-contact flag.\n"
        "- Never share confidential workspace data with leads.\n"
        "- Never pretend to be human if directly and sincerely asked.\n"
        "- Never act outside configured rules — when unsure, send a holding message, "
        "log the interaction, trigger an instinct or automation rule. Do not guess."
    )

    # ─── Section 9: Knowledge Base ──────────────────────────────────────
    sections.append(
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "SECTION 9 — KNOWLEDGE BASE\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "All answers about this business must come from the knowledge base below or "
        "the sections above. If a lead asks something not covered, say: "
        "\"Great question — let me get the right answer for you\" and trigger a "
        "notification to the workspace owner.\n\n"
        f"{_render_kb(p.get('knowledge_base_chunks'))}"
    )

    # ─── Output contract — preserved from legacy aria_agent.py ──────────
    sections.append(
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "OUTPUT CONTRACT\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "When you need to take an action, describe it clearly. Available actions:\n"
        "  SEND_EMAIL | UPDATE_STATUS | BOOK_MEETING | MARK_DNC | ESCALATE | LOG_QUALIFICATION\n\n"
        "Always respond with a JSON object:\n"
        "{\n"
        "  \"message\": \"Your response to the lead\",\n"
        "  \"action\": \"NONE|SEND_EMAIL|UPDATE_STATUS|BOOK_MEETING|MARK_DNC|ESCALATE|LOG_QUALIFICATION\",\n"
        "  \"action_data\": {}\n"
        "}"
    )

    return "\n\n".join(sections)


# ─── Tenant context resolution ──────────────────────────────────────────
def _resolve_persona(tenant: Dict[str, Any]) -> Dict[str, str]:
    """Pull workspace_name, founder_name, aria_name out of tenant.settings."""
    settings = tenant.get("settings") or {}
    bp = settings.get("business_profile") or {}
    persona = settings.get("aria_persona") or {}
    return {
        "workspace_name": (bp.get("business_name") or "").strip() or (tenant.get("name") or "").strip() or "your workspace",
        "founder_name": (bp.get("founder_name") or "").strip() or (tenant.get("owner_name") or "").strip() or "the founder",
        "aria_name": (persona.get("aria_name") or "").strip() or "Aria",
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_workspace_type(tenant: Dict[str, Any]) -> str:
    """Return the workspace type — defaults to 'hybrid' if unset."""
    wt = ((tenant or {}).get("settings") or {}).get("workspace_type") or "hybrid"
    return wt if wt in WORKSPACE_TYPES else "hybrid"


def reassemble_for_tenant(tenant_id: str) -> Dict[str, Any]:
    """Reassemble the system prompt for a tenant after a training change.

    Returns the new `aria_training_profile` dict (with encrypted prompt).
    Raises if the tenant doesn't exist.
    """
    tenant = tenants_col.find_one({"id": tenant_id}, {"_id": 0})
    if not tenant:
        raise HTTPException(404, "Tenant not found")

    settings = tenant.get("settings") or {}
    profile = (settings.get("aria_training_profile") or {}).get("data") or _empty_profile()
    persona = _resolve_persona(tenant)
    wt = get_workspace_type(tenant)

    assembled = assemble_aria_prompt(
        workspace_name=persona["workspace_name"],
        founder_name=persona["founder_name"],
        aria_name=persona["aria_name"],
        workspace_type=wt,
        profile=profile,
    )

    payload = {
        "data": profile,
        "assembled_prompt": encrypt(assembled),
        "assembled_at": _now_iso(),
        "workspace_type_at_assembly": wt,
        "version": ((settings.get("aria_training_profile") or {}).get("version") or 0) + 1,
    }
    tenants_col.update_one(
        {"id": tenant_id},
        {"$set": {"settings.aria_training_profile": payload}},
    )
    # iter105 — snapshot this version into aria_training_versions so the
    # Version History modal has restorable entries. We store the raw profile
    # data (not the encrypted prompt) so a future restore can re-assemble.
    try:
        db["aria_training_versions"].insert_one({
            "tenant_id": tenant_id,
            "version": payload["version"],
            "saved_at": payload["assembled_at"],
            "payload": profile,
            "summary": (profile.get("what_you_sell") or profile.get("business_name") or "")[:120],
            "workspace_type": wt,
        })
    except Exception as _e:
        print(f"[reassemble_for_tenant] snapshot insert failed: {_e}")
    return payload


def get_assembled_prompt(tenant: Dict[str, Any]) -> Optional[str]:
    """Return the cached, decrypted assembled prompt for a tenant.

    Returns None if no training profile has been saved yet — callers
    should fall back to the legacy `get_aria_system_prompt` from
    aria_agent.py.
    """
    if not tenant:
        return None
    profile = ((tenant.get("settings") or {}).get("aria_training_profile") or {})
    enc = profile.get("assembled_prompt")
    if not enc:
        return None
    return decrypt(enc)


# ─── Pydantic models ────────────────────────────────────────────────────
class IcpProfile(BaseModel):
    icp_name: str = ""
    target_industries: List[str] = Field(default_factory=list)
    target_titles_or_roles: List[str] = Field(default_factory=list)
    company_size: str = ""
    geography: str = ""
    budget_range: str = ""
    high_intent_signals: List[str] = Field(default_factory=list)
    disqualification_signals: List[str] = Field(default_factory=list)
    relevant_resources: List[str] = Field(default_factory=list)


class FaqEntry(BaseModel):
    question: str
    answer: str


class TrainingProfilePayload(BaseModel):
    # Section 1
    what_you_sell: str = ""
    who_you_sell_to: str = ""
    problem_you_solve: str = ""
    differentiator: str = ""
    services_or_products: List[str] = Field(default_factory=list)
    # Section 2
    icp_profiles: List[IcpProfile] = Field(default_factory=list)
    # Section 3
    qualification_questions: List[str] = Field(default_factory=list)
    qualified_criteria: List[str] = Field(default_factory=list)
    low_priority_criteria: List[str] = Field(default_factory=list)
    book_call_trigger: str = ""
    instinct_trigger: str = ""
    automation_trigger: str = ""
    # Section 4
    brand_voice_style: str = ""
    custom_tone_instructions: str = ""
    founder_sample_message: str = ""
    # Section 5
    pricing_objection_responses: List[str] = Field(default_factory=list)
    timing_objection_responses: List[str] = Field(default_factory=list)
    trust_objection_responses: List[str] = Field(default_factory=list)
    competitor_responses: List[str] = Field(default_factory=list)
    custom_faq: List[FaqEntry] = Field(default_factory=list)
    # Section 6
    calendar_link: str = ""
    booking_criteria: str = ""
    pre_call_questions: List[str] = Field(default_factory=list)
    reminder_timing: str = ""
    no_show_message: str = ""
    # Section 7
    auto_signal_actions: List[str] = Field(default_factory=list)
    approval_required_signals: List[str] = Field(default_factory=list)
    email_insights_enabled: bool = False
    whatsapp_insights_enabled: bool = False
    digest_time: str = "08:00"
    digest_timezone: str = "Asia/Kolkata"
    # Section 9
    knowledge_base_chunks: List[str] = Field(default_factory=list)


class WorkspaceTypePayload(BaseModel):
    workspace_type: str = Field(pattern="^(b2b|b2c|hybrid)$")


# ─── Endpoints ──────────────────────────────────────────────────────────
@router.get("/training-profile")
async def get_training_profile(tenant: dict = Depends(get_active_tenant)):
    """Return the current training data (decrypted) + assembled-at marker."""
    settings = tenant.get("settings") or {}
    tp = settings.get("aria_training_profile") or {}
    data = tp.get("data") or _empty_profile()
    return {
        "data": data,
        "assembled_at": tp.get("assembled_at"),
        "version": tp.get("version", 0),
        "workspace_type": get_workspace_type(tenant),
        "has_assembled_prompt": bool(tp.get("assembled_prompt")),
    }


@router.put("/training-profile")
async def put_training_profile(
    payload: TrainingProfilePayload,
    tenant: dict = Depends(require_tenant_role(["owner", "admin", "master_admin"])),
):
    """Replace the training profile and re-assemble the system prompt."""
    new_data = payload.model_dump()
    tenants_col.update_one(
        {"id": tenant["id"]},
        {"$set": {"settings.aria_training_profile.data": new_data}},
    )
    assembled = reassemble_for_tenant(tenant["id"])
    return {
        "ok": True,
        "assembled_at": assembled["assembled_at"],
        "version": assembled["version"],
        "prompt_length": len(decrypt(assembled["assembled_prompt"]) or ""),
    }


@router.get("/system-prompt-preview")
async def system_prompt_preview(tenant: dict = Depends(get_active_tenant)):
    """Plain-text preview of the assembled prompt — workspace owners use this
    to verify Aria has the right instructions before launching."""
    prompt = get_assembled_prompt(tenant)
    if not prompt:
        # Build an on-the-fly preview from an empty profile so the owner can
        # still see the section structure.
        persona = _resolve_persona(tenant)
        wt = get_workspace_type(tenant)
        prompt = assemble_aria_prompt(
            persona["workspace_name"], persona["founder_name"],
            persona["aria_name"], wt, _empty_profile(),
        )
        return {"prompt": prompt, "is_stub": True, "workspace_type": wt}
    return {
        "prompt": prompt,
        "is_stub": False,
        "workspace_type": get_workspace_type(tenant),
        "length": len(prompt),
    }


@router.post("/training-profile/reassemble")
async def reassemble_endpoint(
    tenant: dict = Depends(require_tenant_role(["owner", "admin", "master_admin"])),
):
    out = reassemble_for_tenant(tenant["id"])
    return {
        "ok": True,
        "assembled_at": out["assembled_at"],
        "version": out["version"],
    }


# ─── Test Aria — live chat against the assembled prompt ─────────────────
class TestChatPayload(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: List[Dict[str, str]] = Field(default_factory=list, max_length=20)


@router.post("/test-chat")
async def test_chat(
    payload: TestChatPayload,
    tenant: dict = Depends(get_active_tenant),
):
    """Run a single Aria response against the workspace's assembled prompt.

    Lets the workspace owner verify training quality before going live —
    paste a sample prospect message, see exactly how trained-Aria responds.

    No leads or conversations are stored. Pure dry-run.
    """
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(503, "Aria's brain is not configured.")

    system_prompt = get_assembled_prompt(tenant)
    if not system_prompt:
        # Fall back to a stub built from the empty profile
        persona = _resolve_persona(tenant)
        system_prompt = assemble_aria_prompt(
            persona["workspace_name"], persona["founder_name"],
            persona["aria_name"], get_workspace_type(tenant), _empty_profile(),
        )

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except ImportError:
        raise HTTPException(500, "Claude SDK not installed.")

    chat = LlmChat(
        api_key=api_key,
        session_id=f"aria-test-{tenant['id']}-{_now_iso()}",
        system_message=system_prompt,
    ).with_model("anthropic", "claude-haiku-4-5-20251001")

    # Replay history so the test feels like a real conversation
    for turn in (payload.history or []):
        role = (turn.get("role") or "user").lower()
        text = (turn.get("text") or "").strip()
        if not text:
            continue
        # We only feed user turns into the LlmChat (assistant turns are
        # surfaced as Aria's own prior responses; emergentintegrations
        # handles them via session_id continuity within this single call).
        if role == "user":
            try:
                await chat.send_message(UserMessage(text=text))
            except Exception:
                pass

    try:
        resp = await chat.send_message(UserMessage(text=payload.message))
    except Exception as e:
        raise HTTPException(502, f"Aria didn't respond: {str(e)[:160]}")

    raw = (resp or "").strip()
    # Aria's output contract returns JSON. Try parsing; if it fails, surface raw.
    parsed_msg = raw
    action = "NONE"
    try:
        import json as _json
        import re as _re
        cleaned = _re.sub(r"^```(?:json)?\s*", "", raw)
        cleaned = _re.sub(r"\s*```$", "", cleaned).strip()
        obj = _json.loads(cleaned)
        if isinstance(obj, dict):
            parsed_msg = obj.get("message") or raw
            action = obj.get("action") or "NONE"
    except Exception:
        pass

    return {
        "ok": True,
        "message": parsed_msg,
        "action": action,
        "raw": raw,
    }


@router.get("/workspace-type")
async def get_workspace_type_endpoint(tenant: dict = Depends(get_active_tenant)):
    return {"workspace_type": get_workspace_type(tenant)}


@router.put("/workspace-type")
async def set_workspace_type_endpoint(
    payload: WorkspaceTypePayload,
    tenant: dict = Depends(require_tenant_role(["owner", "admin", "master_admin"])),
):
    tenants_col.update_one(
        {"id": tenant["id"]},
        {"$set": {"settings.workspace_type": payload.workspace_type}},
    )
    # Re-assemble immediately so the Insights Engine section toggles on/off.
    out = reassemble_for_tenant(tenant["id"])
    return {
        "ok": True,
        "workspace_type": payload.workspace_type,
        "reassembled_at": out["assembled_at"],
    }


# ─── Phase 2: Document extraction (zero-hallucination JSON) ──────────────
# Implements PROMPT 2 from ARIA_MASTER_SPEC.md. Rules:
#   1. Only extract what's explicitly stated or clearly implied.
#   2. Missing field → exactly "NOT_FOUND".
#   3. No fabrication, no general knowledge filler.
#   4. Concise summaries — never copy paragraphs verbatim.

_EXTRACTION_SYSTEM_PROMPT = """You are a structured data extraction agent. Your job is to read the document provided and extract specific fields to populate a workspace training profile.

RULES — READ BEFORE EXTRACTING:
1. Extract only what is explicitly stated or clearly implied in the document.
2. If a field is not present or not inferable, return exactly the string "NOT_FOUND".
3. Do not infer, assume, fabricate, or fill gaps with general knowledge.
4. Do not copy entire paragraphs. Summarise concisely in your own words.
5. For array fields, return a JSON array (empty [] is fine if no items found).
6. For text fields, return a string (use "NOT_FOUND" if missing, never empty string).
7. Return ONLY the JSON object. No preamble, no explanation, no markdown fences.

Output schema (every field must be present):
{
  "what_you_sell": "string",
  "who_you_sell_to": "string",
  "problem_you_solve": "string",
  "differentiator": "string",
  "services_or_products": ["array of strings"],
  "icp_profiles": [{
    "icp_name": "string",
    "target_industries": ["array"],
    "target_titles_or_roles": ["array"],
    "company_size": "string",
    "geography": "string",
    "budget_range": "string",
    "high_intent_signals": ["array"],
    "disqualification_signals": ["array"]
  }],
  "qualification_questions": ["array"],
  "qualified_criteria": ["array"],
  "low_priority_criteria": ["array"],
  "book_call_trigger": "string",
  "instinct_trigger": "string",
  "automation_trigger": "string",
  "brand_voice_style": "string",
  "custom_tone_instructions": "string",
  "founder_sample_message": "string",
  "pricing_objection_responses": ["array"],
  "timing_objection_responses": ["array"],
  "trust_objection_responses": ["array"],
  "competitor_responses": ["array"],
  "custom_faq": [{"question": "string", "answer": "string"}],
  "calendar_link": "string",
  "booking_criteria": "string",
  "pre_call_questions": ["array"],
  "reminder_timing": "string",
  "no_show_message": "string",
  "knowledge_base_notes": "string"
}"""


def _strip_not_found(value):
    """Recursively convert "NOT_FOUND" sentinels to empty defaults."""
    if isinstance(value, str):
        return "" if value.strip().upper() == "NOT_FOUND" else value.strip()
    if isinstance(value, list):
        out = []
        for v in value:
            cleaned = _strip_not_found(v)
            # Drop empty strings from lists (NOT_FOUND items should disappear)
            if cleaned != "" or isinstance(v, dict):
                out.append(cleaned)
        return out
    if isinstance(value, dict):
        return {k: _strip_not_found(v) for k, v in value.items()}
    return value


def _merge_into_profile(existing: dict, extracted: dict) -> dict:
    """Merge extracted JSON into the existing training profile.

    Rules:
    - Non-empty extracted scalar → overwrites existing (most recent wins).
    - Extracted lists → APPENDED to existing, deduped (preserves order).
    - ICP profiles → APPENDED if the icp_name doesn't already exist; if
      it does, the existing ICP wins (no silent overwrite of curated data).
    """
    out = dict(existing)  # shallow copy
    # Scalar fields
    for k in (
        "what_you_sell", "who_you_sell_to", "problem_you_solve",
        "differentiator", "book_call_trigger", "instinct_trigger",
        "automation_trigger", "brand_voice_style", "custom_tone_instructions",
        "founder_sample_message", "calendar_link", "booking_criteria",
        "reminder_timing", "no_show_message",
    ):
        v = extracted.get(k)
        if isinstance(v, str) and v.strip():
            out[k] = v.strip()

    # Simple string lists — append + dedupe (case-insensitive)
    for k in (
        "services_or_products", "qualification_questions", "qualified_criteria",
        "low_priority_criteria", "pricing_objection_responses",
        "timing_objection_responses", "trust_objection_responses",
        "competitor_responses", "pre_call_questions",
    ):
        new_items = [str(x).strip() for x in (extracted.get(k) or []) if str(x).strip()]
        if not new_items:
            continue
        existing_items = list(out.get(k) or [])
        seen = {x.lower() for x in existing_items}
        for ni in new_items:
            if ni.lower() not in seen:
                existing_items.append(ni)
                seen.add(ni.lower())
        out[k] = existing_items

    # ICP profiles — append by icp_name, never overwrite curated ones
    new_icps = extracted.get("icp_profiles") or []
    if new_icps:
        existing_icps = list(out.get("icp_profiles") or [])
        existing_names = {(i.get("icp_name") or "").strip().lower() for i in existing_icps}
        for icp in new_icps:
            nm = (icp.get("icp_name") or "").strip()
            if nm and nm.lower() not in existing_names:
                # Fill in any missing keys with empty defaults
                full = {**_empty_icp(), **icp}
                existing_icps.append(full)
                existing_names.add(nm.lower())
        out["icp_profiles"] = existing_icps

    # FAQ — append by question, never overwrite an existing answer
    new_faq = extracted.get("custom_faq") or []
    if new_faq:
        existing_faq = list(out.get("custom_faq") or [])
        existing_qs = {(f.get("question") or "").strip().lower() for f in existing_faq}
        for f in new_faq:
            q = (f.get("question") or "").strip()
            a = (f.get("answer") or "").strip()
            if q and a and q.lower() not in existing_qs:
                existing_faq.append({"question": q, "answer": a})
                existing_qs.add(q.lower())
        out["custom_faq"] = existing_faq

    # Knowledge base notes — append as a new chunk if non-trivial
    kb_note = (extracted.get("knowledge_base_notes") or "").strip()
    if kb_note and len(kb_note) > 20:
        chunks = list(out.get("knowledge_base_chunks") or [])
        chunks.append(kb_note)
        out["knowledge_base_chunks"] = chunks

    return out


async def _extract_with_claude(text: str) -> Dict[str, Any]:
    """Run the strict extraction prompt against Claude Haiku.

    Returns the parsed JSON dict. Raises HTTPException on extraction error.
    """
    import os as _os
    import re as _re
    import json as _json
    api_key = _os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(503, "Aria's brain is not configured (missing EMERGENT_LLM_KEY).")

    # Cap input size for predictable latency.
    max_chars = 12000
    excerpt = text[:max_chars]
    if len(text) > max_chars:
        excerpt += "\n\n[...truncated for length...]"

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except ImportError:
        raise HTTPException(500, "Claude SDK not installed.")

    chat = LlmChat(
        api_key=api_key,
        session_id=f"aria-train-extract-{_now_iso()}",
        system_message=_EXTRACTION_SYSTEM_PROMPT,
    ).with_model("anthropic", "claude-haiku-4-5-20251001")

    try:
        resp = await chat.send_message(UserMessage(text=excerpt))
    except Exception as e:
        raise HTTPException(502, f"Aria's brain didn't respond: {str(e)[:160]}")

    raw = (resp or "").strip()
    # Strip code fences if present
    raw = _re.sub(r"^```(?:json)?\s*", "", raw)
    raw = _re.sub(r"\s*```$", "", raw).strip()
    try:
        parsed = _json.loads(raw)
    except _json.JSONDecodeError as e:
        # Try to salvage the first {...} block from the response
        m = _re.search(r"\{[\s\S]+\}", raw)
        if m:
            try:
                parsed = _json.loads(m.group(0))
            except Exception:
                raise HTTPException(502, f"Aria returned malformed JSON: {str(e)[:120]}")
        else:
            raise HTTPException(502, f"Aria returned malformed JSON: {str(e)[:120]}")

    if not isinstance(parsed, dict):
        raise HTTPException(502, "Aria returned non-object JSON.")
    return _strip_not_found(parsed)


_ALLOWED_EXTRACT_MIMES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "text/plain",
    "text/csv",
    "application/octet-stream",  # some browsers
}
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


from fastapi import UploadFile, File  # noqa: E402

# iter108 Batch B — async extraction jobs + content-hash cache
import asyncio as _asyncio  # noqa: E402
import hashlib as _hashlib  # noqa: E402
import uuid as _uuid  # noqa: E402
from datetime import datetime as _dt, timezone as _tz  # noqa: E402

# iter109 Section 4d — bump this string when the extraction prompt / output
# schema changes. Cache entries are keyed by (tenant_id, file_hash,
# prompt_version) so stale results are invalidated automatically.
EXTRACTION_PROMPT_VERSION = "v1"

_extraction_jobs_col = db["training_extraction_jobs"]
# Composite index: cache hits are looked up by (tenant_id, file_hash,
# prompt_version, status="done"). TTL on finished_at expires done/error
# jobs after 30 days so the collection stays bounded (iter109 Section 4c).
try:
    _extraction_jobs_col.create_index([("tenant_id", 1), ("file_hash", 1), ("prompt_version", 1), ("status", 1)])
    _extraction_jobs_col.create_index([("job_id", 1)], unique=True)
    _extraction_jobs_col.create_index(
        [("finished_at_dt", 1)],
        expireAfterSeconds=30 * 24 * 60 * 60,  # 30 days
        name="ttl_finished_at_30d",
    )
except Exception:
    pass


def _image_or_ppt(filename: str) -> bool:
    f = (filename or "").lower()
    return f.endswith((".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".ppt", ".pptx"))


async def _run_extraction_job(job_id: str, tenant_id: str, filename: str, content: bytes):
    """Background worker — does the same pipeline as the sync endpoint
    but writes status into _extraction_jobs_col so the frontend can poll."""
    from routes.aria_auto_map import _extract_text
    try:
        text = _extract_text(filename or "", content)
        if not text or len(text.strip()) < 50:
            _extraction_jobs_col.update_one({"job_id": job_id}, {"$set": {
                "status": "error",
                "error": "Couldn't read enough text from this file. Accepted: PDF, DOCX, PPT, PPTX, XLSX, JPG, PNG, WEBP, TXT.",
                "finished_at": _dt.now(_tz.utc).isoformat(),
            }})
            return

        _extraction_jobs_col.update_one({"job_id": job_id}, {"$set": {
            "status": "extracting",
            "text_chars": len(text),
            "phase": "claude",
        }})

        extracted = await _extract_with_claude(text)

        settings = (tenants_col.find_one({"id": tenant_id}, {"_id": 0}) or {}).get("settings") or {}
        existing = ((settings.get("aria_training_profile") or {}).get("data")) or _empty_profile()
        merged = _merge_into_profile(existing, extracted)
        tenants_col.update_one(
            {"id": tenant_id},
            {"$set": {"settings.aria_training_profile.data": merged}},
        )
        assembled = reassemble_for_tenant(tenant_id)
        fields_filled = sum(1 for k, v in extracted.items() if v and v != "NOT_FOUND" and v != [])

        result = {
            "ok": True,
            "filename": filename,
            "text_chars": len(text),
            "fields_extracted": fields_filled,
            "icps_extracted": len(extracted.get("icp_profiles") or []),
            "icps_merged_total": len(merged.get("icp_profiles") or []),
            "version": assembled["version"],
            "assembled_at": assembled["assembled_at"],
            "prompt_version": EXTRACTION_PROMPT_VERSION,
            "extracted_preview": {
                "what_you_sell": (extracted.get("what_you_sell") or "")[:120],
                "who_you_sell_to": (extracted.get("who_you_sell_to") or "")[:120],
                "icp_names": [i.get("icp_name") for i in (extracted.get("icp_profiles") or [])],
            },
            "extracted_fields": {
                # Stream-friendly per-field map — frontend can render as fields
                # populate. Stored on completion only (we don't truly stream
                # mid-Claude, since the API is single-shot).
                k: (v if isinstance(v, (str, list, dict)) else str(v))
                for k, v in extracted.items()
                if v and v != "NOT_FOUND" and v != []
            },
        }
        _extraction_jobs_col.update_one({"job_id": job_id}, {"$set": {
            "status": "done",
            "result": result,
            "finished_at": _dt.now(_tz.utc).isoformat(),
            "finished_at_dt": _dt.now(_tz.utc),
        }})
    except HTTPException as he:
        _extraction_jobs_col.update_one({"job_id": job_id}, {"$set": {
            "status": "error", "error": str(he.detail)[:280],
            "finished_at": _dt.now(_tz.utc).isoformat(),
            "finished_at_dt": _dt.now(_tz.utc),
        }})
    except Exception as e:
        _extraction_jobs_col.update_one({"job_id": job_id}, {"$set": {
            "status": "error", "error": f"Internal: {str(e)[:200]}",
            "finished_at": _dt.now(_tz.utc).isoformat(),
            "finished_at_dt": _dt.now(_tz.utc),
        }})


@router.post("/training-profile/extract-from-document")
async def extract_from_document(
    file: UploadFile = File(...),
    tenant: dict = Depends(require_tenant_role(["owner", "admin", "master_admin"])),
):
    """iter108 Batch B — async + content-hash cached extraction.

    Flow:
      1. Hash the upload (sha256). If a `done` job exists for this tenant +
         hash, return its cached result instantly (`cached=true`).
      2. Else create a job doc + kick off background extraction.
      3. Return `{job_id, status: "queued", eta_seconds, hint}` so the
         frontend can show progress UI immediately and poll
         `/training-profile/extract-job/{job_id}`.
    """
    content = await file.read()
    if not content:
        raise HTTPException(400, "Empty file.")
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File too large (max {_MAX_UPLOAD_BYTES // (1024 * 1024)}MB).")

    # iter109 Section 4d — include the extraction-prompt version in the
    # cache key so a future prompt bump invalidates stale results cleanly.
    file_hash = _hashlib.sha256(content).hexdigest()

    # Cache lookup
    cached = _extraction_jobs_col.find_one(
        {
            "tenant_id": tenant["id"],
            "file_hash": file_hash,
            "prompt_version": EXTRACTION_PROMPT_VERSION,
            "status": "done",
        },
        {"_id": 0, "result": 1, "job_id": 1, "finished_at": 1},
        sort=[("finished_at", -1)],
    )
    if cached and cached.get("result"):
        return {
            "cached": True,
            "job_id": cached.get("job_id"),
            "status": "done",
            "finished_at": cached.get("finished_at"),
            **cached["result"],
        }

    # Create job + kick off worker
    job_id = _uuid.uuid4().hex
    eta = 45 if _image_or_ppt(file.filename or "") else 25
    hint = (
        "Images & slides typically take 45–60 seconds — OCR is the slow part."
        if _image_or_ppt(file.filename or "")
        else "Most docs land in 20–30 seconds."
    )
    _extraction_jobs_col.insert_one({
        "job_id": job_id,
        "tenant_id": tenant["id"],
        "file_hash": file_hash,
        "prompt_version": EXTRACTION_PROMPT_VERSION,
        "filename": file.filename,
        "size_bytes": len(content),
        "is_ocr": _image_or_ppt(file.filename or ""),
        "status": "queued",
        "phase": "text_extraction",
        "started_at": _dt.now(_tz.utc).isoformat(),
        "finished_at": None,
        "finished_at_dt": None,
        "result": None,
        "error": None,
    })
    _asyncio.create_task(_run_extraction_job(job_id, tenant["id"], file.filename or "upload", content))
    return {
        "cached": False,
        "job_id": job_id,
        "status": "queued",
        "eta_seconds": eta,
        "hint": hint,
        "is_ocr": _image_or_ppt(file.filename or ""),
    }


@router.get("/training-profile/extract-job/{job_id}")
async def extract_job_status(
    job_id: str,
    tenant: dict = Depends(require_tenant_role(["owner", "admin", "master_admin"])),
):
    """Poll an extraction job. Returns:
      - `{status: "queued"|"extracting", phase, elapsed_seconds, eta_seconds, slow_warn}` while running
      - `{status: "done", ...full result fields}` on completion
      - `{status: "error", error}` on failure
    """
    job = _extraction_jobs_col.find_one(
        {"job_id": job_id, "tenant_id": tenant["id"]},
        {"_id": 0},
    )
    if not job:
        raise HTTPException(404, "Extraction job not found")

    started = job.get("started_at")
    elapsed = 0
    if started:
        try:
            d = _dt.fromisoformat(started.replace("Z", "+00:00"))
            elapsed = int((_dt.now(_tz.utc) - d).total_seconds())
        except Exception:
            pass

    base = {
        "job_id": job_id,
        "filename": job.get("filename"),
        "status": job.get("status"),
        "phase": job.get("phase"),
        "elapsed_seconds": elapsed,
        "is_ocr": job.get("is_ocr", False),
        "slow_warn": elapsed > 90 and job.get("status") in ("queued", "extracting"),
    }
    if job.get("status") == "done":
        return {**base, **(job.get("result") or {}), "status": "done"}
    if job.get("status") == "error":
        return {**base, "error": job.get("error")}
    return base


# ─── Phase 2: Auto-train from existing workspace data ────────────────────
@router.get("/training-profile/completeness")
async def training_profile_completeness(tenant: dict = Depends(get_active_tenant)):
    """iter109 Section 4a — Profile completeness %.

    Returns the percentage of "key training fields" populated, plus the
    next missing field so the UI can nudge the founder toward 100%.
    """
    settings = tenant.get("settings") or {}
    profile = (settings.get("aria_training_profile") or {}).get("data") or _empty_profile()

    # Fields that count toward training completeness (one point each).
    checks = [
        ("what_you_sell",          "Business Identity — what you sell",     "identity"),
        ("who_you_sell_to",        "Business Identity — who you sell to",   "identity"),
        ("problem_you_solve",      "Business Identity — problem solved",    "identity"),
        ("differentiator",         "Business Identity — differentiator",    "identity"),
        ("icp_profiles",           "Ideal Customer Profiles — add at least 1 ICP", "icps"),
        ("qualification_questions", "Qualification — questions Aria asks",  "qualify"),
        ("brand_voice_style",      "Brand Voice — voice style",             "voice"),
        ("pricing_objection_responses", "Objections — pricing pushback",    "objections"),
        ("calendar_link",          "Booking — calendar link",               "booking"),
    ]
    filled = []
    missing = []
    for field, label, section in checks:
        val = profile.get(field)
        is_filled = bool(val) if not isinstance(val, list) else len(val) > 0
        (filled if is_filled else missing).append({"field": field, "label": label, "section": section})

    total = len(checks)
    pct = int(round((len(filled) / total) * 100)) if total else 0
    nudge = None
    if missing:
        m = missing[0]
        nudge = {
            "field": m["field"],
            "label": m["label"],
            "section": m["section"],
            "message": f"Next: {m['label']}",
        }
    return {
        "percent": pct,
        "filled_count": len(filled),
        "total": total,
        "missing": missing,
        "nudge": nudge,
    }


@router.post("/training-profile/auto-train-from-workspace")
async def auto_train_from_workspace(
    tenant: dict = Depends(require_tenant_role(["owner", "admin", "master_admin"])),
):
    """Seed the training profile from data already in the workspace.

    Sources (in priority order — non-empty wins):
      1. `tenants.settings.business_profile`  → identity fields
      2. `tenants.settings.aria_persona`      → tone hints
      3. `icps` collection (filtered by tenant) → ICP profiles
      4. `tenants.settings.calendly` / `calendar_link` → booking
      5. `tenants.settings.sales_channels`    → channel preferences (kb chunk)

    Non-destructive: only fills empty fields. If a field is already
    populated in the existing training profile, it's left alone.
    """
    settings = tenant.get("settings") or {}
    bp = settings.get("business_profile") or {}
    persona = settings.get("aria_persona") or {}
    existing = (settings.get("aria_training_profile") or {}).get("data") or _empty_profile()

    seeded: List[str] = []
    out = dict(existing)

    def _fill(field: str, value: str):
        if value and value.strip() and not (out.get(field) or "").strip():
            out[field] = value.strip()
            seeded.append(field)

    _fill("what_you_sell", bp.get("offering") or bp.get("description") or "")
    _fill("who_you_sell_to", bp.get("target_audience") or bp.get("primary_market") or "")
    _fill("problem_you_solve", bp.get("problem_solved") or bp.get("value_prop") or "")
    _fill("differentiator", bp.get("unique_value") or bp.get("differentiator") or "")
    _fill("brand_voice_style", persona.get("tone") or "")
    _fill("calendar_link", (settings.get("calendly") or {}).get("link") or settings.get("calendar_link") or "")

    # Services / products list — only fill if empty
    services = bp.get("services") or bp.get("products") or []
    if isinstance(services, list) and services and not out.get("services_or_products"):
        out["services_or_products"] = [str(s).strip() for s in services if str(s).strip()]
        seeded.append("services_or_products")

    # ICPs from the icps collection
    icp_docs = list(db["icps"].find({"tenant_id": tenant["id"]}, {"_id": 0}).limit(20))
    if icp_docs:
        existing_names = {
            (i.get("icp_name") or "").strip().lower()
            for i in (out.get("icp_profiles") or [])
        }
        appended = 0
        for icp in icp_docs:
            label = (icp.get("label") or "").strip()
            if not label or label.lower() in existing_names:
                continue
            mapped = {**_empty_icp(),
                      "icp_name": label,
                      "target_industries": [icp.get("industry")] if icp.get("industry") else [],
                      "target_titles_or_roles": list(icp.get("title_targets") or []),
                      "company_size": icp.get("company_size") or "",
                      "budget_range": icp.get("deal_size") or "",
                      "high_intent_signals": [icp.get("pain_point")] if icp.get("pain_point") else [],
                      }
            out.setdefault("icp_profiles", []).append(mapped)
            existing_names.add(label.lower())
            appended += 1
        if appended:
            seeded.append(f"icp_profiles (+{appended})")

    # Knowledge base chunk from sales_channels prefs
    sc = settings.get("sales_channels") or {}
    if sc and not (out.get("knowledge_base_chunks")):
        primary = sc.get("primary_channel") or "—"
        order = ", ".join(sc.get("priority_order") or [])
        chunk = f"Sales channel preferences: primary={primary}; order={order}."
        out["knowledge_base_chunks"] = [chunk]
        seeded.append("knowledge_base_chunks")

    if not seeded:
        return {
            "ok": True,
            "seeded": [],
            "message": "Nothing to seed — your workspace doesn't have business_profile or icps populated yet, or the training profile is already filled.",
        }

    tenants_col.update_one(
        {"id": tenant["id"]},
        {"$set": {"settings.aria_training_profile.data": out}},
    )
    assembled = reassemble_for_tenant(tenant["id"])
    return {
        "ok": True,
        "seeded": seeded,
        "version": assembled["version"],
        "message": f"Seeded {len(seeded)} field(s) from existing workspace data.",
    }
