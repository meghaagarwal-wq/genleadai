"""Aria Master Training Profile + Dynamic System Prompt Assembly (Phase 1).

Implements the v2 master prompt described in /app/memory/ARIA_MASTER_SPEC.md.
The workspace owner trains Aria once (via document upload or manual edits);
this module turns that training data into a fully-assembled system prompt
that's stored Fernet-encrypted on the tenant and injected as the system
message on every Aria conversation.

Endpoints
─────────
GET  /api/aria/training-profile     — current training data (decrypted)
PUT  /api/aria/training-profile     — replace training fields, re-assemble + encrypt
GET  /api/aria/system-prompt-preview — preview the assembled prompt as plain text
POST /api/aria/training-profile/reassemble — force a re-assembly (no data change)
GET  /api/aria/workspace-type       — current workspace_type
PUT  /api/aria/workspace-type       — set b2b | b2c | hybrid

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
