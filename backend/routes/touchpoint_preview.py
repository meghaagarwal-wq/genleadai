"""Claude-powered preview of touchpoint messages for onboarding Step 4.

Renders the first N touchpoints of a chosen template with real, founder-
specific copy using the in-memory onboarding form state. Used to make the
abstract template tangible during signup.

Uses Emergent Universal Key via `emergentintegrations`.
"""
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import get_current_user
from routes.tenants import get_active_tenant
from touchpoint_templates_seed import TEMPLATES

router = APIRouter(prefix="/api/touchpoints", tags=["touchpoints-preview"])


class PreviewBusiness(BaseModel):
    business_name: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    primary_market: Optional[str] = None


class PreviewPersona(BaseModel):
    aria_name: Optional[str] = "Aria"
    tone: Optional[str] = "friendly_professional"
    language: Optional[str] = "English"


class PreviewSales(BaseModel):
    product_description: Optional[str] = ""
    deal_size: Optional[str] = ""
    sales_cycle: Optional[str] = ""


class PreviewRequest(BaseModel):
    template_id: str
    business: PreviewBusiness = Field(default_factory=PreviewBusiness)
    persona: PreviewPersona = Field(default_factory=PreviewPersona)
    sales: PreviewSales = Field(default_factory=PreviewSales)
    limit: int = Field(default=2, ge=1, le=4)


class PreviewItem(BaseModel):
    index: int
    channel: str
    message_type: str
    rendered_message: str
    ai_powered: bool


def _template_by_id(tid: str) -> Optional[dict]:
    return next((t for t in TEMPLATES if t["id"] == tid), None)


def _heuristic_render(tp: dict, business: dict, persona: dict) -> str:
    """Deterministic token-substitution fallback when Claude isn't available."""
    msg = tp.get("message_template", "")
    aria_name = (persona.get("aria_name") or "Aria")
    business_name = (business.get("business_name") or "your team")
    return (
        msg.replace("{{first_name}}", "{{first_name}}")
        .replace("{{aria_name}}", aria_name)
        .replace("{{company}}", business_name)
        .replace("{{product}}", (business.get("description") or "our offering")[:80])
    )


async def _claude_render(tp: dict, business: dict, persona: dict, sales: dict) -> Optional[str]:
    """Use Claude (via Emergent Universal Key) to rewrite the template into
    real founder-specific copy. Returns None on any failure → caller falls back
    to heuristic substitution.
    """
    try:
        from services.claude_service import claude_call, TaskType
        product = (sales.get("product_description") or business.get("description") or "the product").strip()
        biz_name = business.get("business_name") or "the company"
        industry = business.get("industry") or "B2B"
        tone = persona.get("tone") or "friendly_professional"
        aria_name = persona.get("aria_name") or "Aria"
        intent = tp.get("message_template", "")
        msg_type = tp.get("message_type", "intro")
        channel = tp.get("channel", "whatsapp")

        system_prompt = (
            f"You are {aria_name}, an AI sales assistant for {biz_name} (industry: {industry}). "
            f"Tone: {tone}. Speak directly to the lead. "
            "When referencing the lead's name, use EXACTLY the token {{first_name}} with double curly braces — do NOT use {first_name}, [name], or any other format. "
            "Output ONLY the message body — no preamble, no markdown, no quotes."
        )
        user_msg = (
            f"Product/service offered: {product}\n\n"
            f"Channel: {channel}\n"
            f"Touchpoint intent: {msg_type}\n"
            f"Base template (for reference, rewrite using the founder's actual product):\n{intent}\n\n"
            "Generate the message in 1-3 sentences max. Reference what {{first_name}} likely cares about given the product. "
            "Keep it conversational, end with one open question. No emojis unless tone is casual or aggressive_sales."
        )
        resp = await claude_call(
            task_type=TaskType.TOUCHPOINT_GENERATION,
            system=system_prompt,
            prompt=user_msg,
            session_id=f"preview-{tp.get('index', 0)}",
        )
        text = (resp or "").strip()
        # Strip leading/trailing quotes that Claude sometimes wraps in
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]
        return text or None
    except Exception as e:
        print(f"[touchpoint-preview] Claude error: {e}")
        return None


@router.post("/preview")
async def preview_touchpoints(
    payload: PreviewRequest,
    _user: dict = Depends(get_current_user),
    _tenant: dict = Depends(get_active_tenant),
):
    """Return Claude-rendered copy for the first `limit` touchpoints of the
    chosen template using the supplied (in-progress) onboarding form state.

    Falls back to heuristic token-substitution for any touchpoint where Claude
    errors or the key isn't configured. Each item has `ai_powered: true|false`
    so the UI can badge the rendered copy accordingly.
    """
    tpl = _template_by_id(payload.template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    items: List[PreviewItem] = []
    for tp in (tpl.get("touchpoints") or [])[: payload.limit]:
        ai_text = await _claude_render(tp, payload.business.model_dump(), payload.persona.model_dump(), payload.sales.model_dump())
        if ai_text:
            items.append(PreviewItem(
                index=tp["index"], channel=tp["channel"], message_type=tp["message_type"],
                rendered_message=ai_text, ai_powered=True,
            ))
        else:
            items.append(PreviewItem(
                index=tp["index"], channel=tp["channel"], message_type=tp["message_type"],
                rendered_message=_heuristic_render(tp, payload.business.model_dump(), payload.persona.model_dump()),
                ai_powered=False,
            ))
    return {"template_id": payload.template_id, "items": [i.model_dump() for i in items]}
