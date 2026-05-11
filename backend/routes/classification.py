"""Three-layer inbound WhatsApp message classification.

Layer 1: trigger phrases (workspace-customizable)
Layer 2: phone lookup → leads / workspace_contacts / opted_out
Layer 3: Claude AI intent classification

Used by the webhook handler to route inbound messages correctly. Returns a
classification dict; webhook then takes the appropriate side-effect.
"""
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import db, get_current_user
from routes.tenants import get_active_tenant
from routes.contacts import lookup_contact
from routes.compliance import is_opted_out, is_stop_keyword

router = APIRouter(prefix="/api/classification", tags=["classification"])

triggers_col = db["classification_triggers"]
log_col = db["classification_log"]
leads_col = db["leads"]
tenants_col = db["tenants"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(phone: str) -> str:
    return "".join(c for c in (phone or "") if c.isdigit())


# ─── Default trigger phrases (per-tenant override possible) ─────────────────
DEFAULT_TRIGGERS = [
    "i'm interested in", "pricing please", "i saw your ad", "tell me about your",
    "i want to know more", "hi, i found you on", "how much does", "can you send me",
    "i'd like to learn more", "interested in your",
]


CATEGORIES = {
    "LEAD", "EXISTING_CLIENT", "VENDOR", "OPERATIONAL", "JOB_APPLICANT",
    "UNCLEAR", "SPAM", "WRONG_NUMBER",
}


# ─── Layer 1: trigger phrases ───────────────────────────────────────────────
def _check_triggers(tenant_id: str, body: str) -> Optional[dict]:
    text = (body or "").lower().strip()
    if not text:
        return None
    # Custom tenant triggers first
    custom = list(triggers_col.find({"tenant_id": tenant_id, "active": True}, {"_id": 0}))
    for t in custom:
        phrase = (t.get("phrase") or "").lower().strip()
        if phrase and phrase in text:
            return {"matched": phrase, "source_tag": t.get("source_tag")}
    for phrase in DEFAULT_TRIGGERS:
        if phrase in text:
            return {"matched": phrase, "source_tag": "default"}
    return None


# ─── Layer 3: Claude classification ─────────────────────────────────────────
async def _classify_with_claude(tenant: dict, body: str) -> dict:
    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        return {"category": "UNCLEAR", "confidence": 0.0, "reason": "llm_key_missing"}
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        biz = (tenant.get("settings") or {}).get("business_profile") or {}
        biz_name = tenant.get("name") or "the company"
        industry = biz.get("industry") or "B2B"
        system = (
            f"You classify inbound WhatsApp messages for {biz_name} (industry: {industry}).\n"
            "Output ONLY a single JSON object with keys: category, confidence (0..1), reason (short string).\n"
            "category MUST be one of: LEAD, EXISTING_CLIENT, VENDOR, OPERATIONAL, JOB_APPLICANT, UNCLEAR, SPAM, WRONG_NUMBER.\n"
            "Heuristics: LEAD = expresses buying interest, asks pricing, wants demo. EXISTING_CLIENT = mentions an order, account, contract, ticket. VENDOR = pitches services to us, sells us tools, offers partnership. OPERATIONAL = courier, delivery, scheduling, internal logistics. JOB_APPLICANT = resume, application, looking for work. UNCLEAR = ambiguous or just 'hi'. SPAM = bulk promo, crypto, phishing. WRONG_NUMBER = mentions another person/business by name."
        )
        chat = LlmChat(api_key=api_key, session_id="classify", system_message=system).with_model("anthropic", "claude-sonnet-4-5-20250929")
        resp = await chat.send_message(UserMessage(text=f"Message: {body!r}\n\nReturn JSON only."))
        import json
        import re
        text = (resp or "").strip()
        # Strip ```json fences if present
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
        data = json.loads(text)
        cat = (data.get("category") or "UNCLEAR").upper()
        if cat not in CATEGORIES:
            cat = "UNCLEAR"
        return {
            "category": cat,
            "confidence": float(data.get("confidence") or 0.0),
            "reason": (data.get("reason") or "")[:200],
        }
    except Exception as e:
        print(f"[classify] claude error: {e}")
        return {"category": "UNCLEAR", "confidence": 0.0, "reason": f"claude_error: {e}"}


# ─── Public entry point ─────────────────────────────────────────────────────
async def classify_inbound(tenant_id: str, phone: str, body: str) -> dict:
    """Run all 3 layers on an inbound message. Returns a classification dict
    and writes a row to classification_log. Does NOT take side-effects
    (lead create / canned response) — the webhook owns those.
    """
    tenant = tenants_col.find_one({"id": tenant_id}, {"_id": 0})
    if not tenant:
        return {"category": "UNCLEAR", "layer": 0, "confidence": 0.0, "reason": "no_tenant"}

    # STOP keyword always wins.
    if is_stop_keyword(body):
        result = {"category": "OPT_OUT", "layer": 0, "confidence": 1.0, "reason": "stop_keyword", "action": "opt_out"}
        _log(tenant_id, phone, body, result)
        return result

    norm = _normalize(phone)

    # Tenant blocklist short-circuit
    if is_opted_out(tenant_id, phone):
        result = {"category": "SPAM", "layer": 2, "confidence": 1.0, "reason": "tenant_blocklist", "action": "ignore"}
        _log(tenant_id, phone, body, result)
        return result

    # Layer 1: trigger phrases
    t1 = _check_triggers(tenant_id, body)
    if t1:
        result = {"category": "LEAD", "layer": 1, "confidence": 0.95, "reason": f"trigger:{t1['matched']}", "source_tag": t1.get("source_tag"), "action": "create_lead_or_continue"}
        _log(tenant_id, phone, body, result)
        return result

    # Layer 2: phone lookup
    last10 = norm[-10:] if len(norm) >= 10 else norm
    existing_lead = leads_col.find_one(
        {"tenant_id": tenant_id, "$or": [{"phone": {"$regex": f"{last10}$"}}, {"phone": norm}]},
        {"_id": 0, "id": 1, "stage": 1},
    )
    if existing_lead:
        result = {"category": "LEAD", "layer": 2, "confidence": 1.0, "reason": "existing_lead", "lead_id": existing_lead.get("id"), "action": "continue_lead"}
        _log(tenant_id, phone, body, result, lead_id=existing_lead.get("id"))
        return result

    contact = lookup_contact(tenant_id, phone)
    if contact:
        ctype = contact.get("contact_type")
        cat_map = {
            "existing_client": "EXISTING_CLIENT",
            "vendor": "VENDOR",
            "personal": "OPERATIONAL",
            "press": "OPERATIONAL",
            "job_applicant": "JOB_APPLICANT",
            "blocked": "SPAM",
        }
        category = cat_map.get(ctype, "UNCLEAR")
        result = {"category": category, "layer": 2, "confidence": 1.0, "reason": f"contact:{ctype}", "action": "canned_response"}
        _log(tenant_id, phone, body, result)
        return result

    # Layer 3: Claude
    cls = await _classify_with_claude(tenant, body)
    action = _action_from_classification(cls)
    result = {**cls, "layer": 3, "action": action}
    _log(tenant_id, phone, body, result)
    return result


def _action_from_classification(cls: dict) -> str:
    cat = cls.get("category", "UNCLEAR")
    conf = float(cls.get("confidence") or 0.0)
    if cat == "LEAD" and conf >= 0.80:
        return "create_lead"
    if cat == "LEAD" and conf >= 0.50:
        return "create_lead_needs_review"
    if cat == "LEAD":
        return "neutral_opener"
    if cat == "SPAM":
        return "ignore"
    if cat == "UNCLEAR":
        return "neutral_opener"
    if cat == "WRONG_NUMBER":
        return "wrong_number_response"
    return "canned_response"


def _log(tenant_id: str, phone: str, body: str, result: dict, lead_id: Optional[str] = None) -> None:
    log_col.insert_one({
        "id": _new_log_id(),
        "tenant_id": tenant_id,
        "phone": phone,
        "inbound_message": (body or "")[:500],
        "layer_resolved": result.get("layer"),
        "category": result.get("category"),
        "confidence": result.get("confidence"),
        "reason": result.get("reason"),
        "action_taken": result.get("action"),
        "lead_id": lead_id,
        "overridden": False,
        "override_category": None,
        "created_at": _now(),
    })


def _new_log_id() -> str:
    import uuid
    return f"clog_{uuid.uuid4().hex[:12]}"


# ─── HTTP endpoints (triggers + log + canned responses) ─────────────────────
class TriggerPayload(BaseModel):
    phrase: str
    source_tag: Optional[str] = ""
    active: bool = True


@router.get("/triggers")
async def list_triggers(tenant: dict = Depends(get_active_tenant)):
    rows = list(triggers_col.find({"tenant_id": tenant["id"]}, {"_id": 0}).sort("created_at", -1))
    return {"triggers": rows, "defaults": DEFAULT_TRIGGERS}


@router.post("/triggers")
async def add_trigger(payload: TriggerPayload, tenant: dict = Depends(get_active_tenant)):
    if tenant.get("_member_role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")
    phrase = (payload.phrase or "").strip().lower()
    if not phrase:
        raise HTTPException(status_code=400, detail="phrase required")
    import uuid
    doc = {
        "id": f"trg_{uuid.uuid4().hex[:12]}",
        "tenant_id": tenant["id"],
        "phrase": phrase,
        "source_tag": (payload.source_tag or "").strip(),
        "active": bool(payload.active),
        "created_at": _now(),
    }
    triggers_col.insert_one(doc)
    return {"trigger": {k: v for k, v in doc.items() if k != "_id"}}


@router.delete("/triggers/{trigger_id}")
async def delete_trigger(trigger_id: str, tenant: dict = Depends(get_active_tenant)):
    if tenant.get("_member_role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")
    triggers_col.delete_one({"id": trigger_id, "tenant_id": tenant["id"]})
    return {"status": "ok"}


@router.get("/log")
async def list_log(limit: int = 100, tenant: dict = Depends(get_active_tenant)):
    limit = max(1, min(limit, 500))
    rows = list(log_col.find({"tenant_id": tenant["id"]}, {"_id": 0}).sort("created_at", -1).limit(limit))
    return {"log": rows}


@router.post("/log/{log_id}/override")
async def override_log(log_id: str, payload: dict, tenant: dict = Depends(get_active_tenant)):
    """Override a misclassified message — flips category and marks for retraining."""
    if tenant.get("_member_role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner/Admin only")
    new_cat = (payload.get("category") or "").upper()
    if new_cat not in CATEGORIES:
        raise HTTPException(status_code=400, detail="invalid category")
    log_col.update_one(
        {"id": log_id, "tenant_id": tenant["id"]},
        {"$set": {"overridden": True, "override_category": new_cat, "overridden_at": _now()}},
    )
    return {"status": "ok"}
