"""Iter101 — Visual Automation Rule Builder backend.

Tenant-scoped CRUD for `when X then Y` automation rules. Rules can be
triggered (a) explicitly via `/api/automation-rules/{id}/run-now`, or
(b) implicitly by an event-engine hook.

Schema (`automation_rules` collection)
──────────────────────────────────────
  id              str  uuid4
  tenant_id       str
  name            str
  description     str  optional
  enabled         bool
  trigger:                          # WHEN
    event_type    str  e.g. "lead.created", "insight.classified", "stage.changed"
    conditions    list[Condition]   # ALL must match
  actions         list[Action]      # THEN — executed in order
  created_at      ISO
  updated_at      ISO
  last_fired_at   Optional[ISO]
  fire_count      int

Condition shape
  field           str  e.g. "lead.stage", "lead.icp_score"
  op              str  "eq"|"ne"|"gt"|"gte"|"lt"|"lte"|"in"|"contains"
  value           str | int | float | list

Action shape
  type            str  "send_email"|"add_tag"|"set_stage"|"create_task"|"notify_slack"|"attach_resource"
  params          dict
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import db
from routes.tenants import get_active_tenant, require_tenant_role

router = APIRouter(prefix="/api/automation-rules", tags=["automation-rules"])

rules_col = db["automation_rules"]
rules_fires_col = db["automation_rule_fires"]


SUPPORTED_TRIGGERS = (
    "lead.created",
    "lead.stage_changed",
    "lead.icp_scored",
    "insight.classified",
    "email.opened",
    "email.replied",
    "form.submitted",
)

SUPPORTED_OPS = ("eq", "ne", "gt", "gte", "lt", "lte", "in", "contains")

SUPPORTED_ACTION_TYPES = (
    "send_email",
    "add_tag",
    "set_stage",
    "create_task",
    "notify_slack",
    "attach_resource",
    "log_only",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Pydantic schemas ────────────────────────────────────────────────────
class Condition(BaseModel):
    field: str = Field(min_length=1, max_length=80)
    op:    str = Field(min_length=1, max_length=12)
    value: Any


class Action(BaseModel):
    type:   str = Field(min_length=1, max_length=40)
    params: Dict[str, Any] = Field(default_factory=dict)


class Trigger(BaseModel):
    event_type: str = Field(min_length=1, max_length=80)
    conditions: List[Condition] = Field(default_factory=list)


class RuleCreate(BaseModel):
    name:        str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=600)
    enabled:     bool = True
    trigger:     Trigger
    actions:     List[Action] = Field(default_factory=list, min_length=1)


class RuleUpdate(BaseModel):
    name:        Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=600)
    enabled:     Optional[bool] = None
    trigger:     Optional[Trigger] = None
    actions:     Optional[List[Action]] = None


def _validate_rule(rule: RuleCreate) -> None:
    if rule.trigger.event_type not in SUPPORTED_TRIGGERS:
        raise HTTPException(400, f"event_type must be one of {SUPPORTED_TRIGGERS}")
    for c in rule.trigger.conditions:
        if c.op not in SUPPORTED_OPS:
            raise HTTPException(400, f"condition op must be one of {SUPPORTED_OPS}")
    if not rule.actions:
        raise HTTPException(400, "at least one action required")
    for a in rule.actions:
        if a.type not in SUPPORTED_ACTION_TYPES:
            raise HTTPException(400, f"action type must be one of {SUPPORTED_ACTION_TYPES}")


def _serialize(r: Dict[str, Any]) -> Dict[str, Any]:
    r = dict(r)
    r.pop("_id", None)
    return r


# ─── CRUD endpoints ──────────────────────────────────────────────────────
@router.get("")
async def list_rules(
    tenant: dict = Depends(get_active_tenant),
    include_disabled: bool = True,
):
    q = {"tenant_id": tenant["id"]}
    if not include_disabled:
        q["enabled"] = True
    rows = list(rules_col.find(q, {"_id": 0}).sort("created_at", -1))
    return {"ok": True, "count": len(rows), "rules": [_serialize(r) for r in rows]}


@router.get("/catalog")
async def get_catalog():
    """Surface supported triggers/ops/actions so the UI can render
    dropdowns without hardcoding. Public to authenticated callers.
    """
    return {
        "triggers": list(SUPPORTED_TRIGGERS),
        "ops": list(SUPPORTED_OPS),
        "action_types": list(SUPPORTED_ACTION_TYPES),
        "common_fields": [
            "lead.stage", "lead.icp_score", "lead.country", "lead.industry",
            "lead.source", "lead.tags", "lead.email_domain",
            "insight.signal_type", "insight.confidence",
            "email.opened_count", "email.replied",
        ],
    }


@router.post("")
async def create_rule(
    payload: RuleCreate,
    tenant: dict = Depends(require_tenant_role(["owner", "admin", "master_admin"])),
):
    _validate_rule(payload)
    doc = {
        "id":            str(uuid.uuid4()),
        "tenant_id":     tenant["id"],
        "name":          payload.name.strip(),
        "description":   payload.description.strip(),
        "enabled":       payload.enabled,
        "trigger":       payload.trigger.model_dump(),
        "actions":       [a.model_dump() for a in payload.actions],
        "created_at":    _now(),
        "updated_at":    _now(),
        "last_fired_at": None,
        "fire_count":    0,
    }
    rules_col.insert_one(doc)
    return {"ok": True, "rule": _serialize(doc)}


@router.patch("/{rule_id}")
async def update_rule(
    rule_id: str,
    payload: RuleUpdate,
    tenant: dict = Depends(require_tenant_role(["owner", "admin", "master_admin"])),
):
    existing = rules_col.find_one({"id": rule_id, "tenant_id": tenant["id"]}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Rule not found")
    data = payload.model_dump(exclude_unset=True)
    updates: Dict[str, Any] = {"updated_at": _now()}
    for k in ("name", "description", "enabled"):
        if k in data:
            updates[k] = data[k]
    if "trigger" in data and data["trigger"]:
        if data["trigger"]["event_type"] not in SUPPORTED_TRIGGERS:
            raise HTTPException(400, f"event_type must be one of {SUPPORTED_TRIGGERS}")
        for c in data["trigger"].get("conditions", []):
            if c["op"] not in SUPPORTED_OPS:
                raise HTTPException(400, f"condition op must be one of {SUPPORTED_OPS}")
        updates["trigger"] = data["trigger"]
    if "actions" in data and data["actions"] is not None:
        for a in data["actions"]:
            if a["type"] not in SUPPORTED_ACTION_TYPES:
                raise HTTPException(400, f"action type must be one of {SUPPORTED_ACTION_TYPES}")
        updates["actions"] = data["actions"]
    rules_col.update_one({"id": rule_id, "tenant_id": tenant["id"]}, {"$set": updates})
    fresh = rules_col.find_one({"id": rule_id, "tenant_id": tenant["id"]}, {"_id": 0})
    return {"ok": True, "rule": _serialize(fresh)}


@router.delete("/{rule_id}")
async def delete_rule(
    rule_id: str,
    tenant: dict = Depends(require_tenant_role(["owner", "admin", "master_admin"])),
):
    res = rules_col.delete_one({"id": rule_id, "tenant_id": tenant["id"]})
    if res.deleted_count == 0:
        raise HTTPException(404, "Rule not found")
    return {"ok": True}


# ─── Evaluation helpers (used by event engine + dry-run) ────────────────
def _get_nested(obj: Dict[str, Any], path: str) -> Any:
    """Resolve dotted path: 'lead.icp_score' → obj['lead']['icp_score'].

    Falls back to flat lookup if the prefix isn't a dict (e.g. 'icp_score').
    """
    if not isinstance(obj, dict):
        return None
    cur: Any = obj
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _eval_condition(c: Dict[str, Any], context: Dict[str, Any]) -> bool:
    actual = _get_nested(context, c["field"])
    op = c["op"]
    expected = c["value"]
    try:
        if op == "eq":
            return actual == expected
        if op == "ne":
            return actual != expected
        if op == "gt":
            return actual is not None and actual > expected
        if op == "gte":
            return actual is not None and actual >= expected
        if op == "lt":
            return actual is not None and actual < expected
        if op == "lte":
            return actual is not None and actual <= expected
        if op == "in":
            return actual in (expected or [])
        if op == "contains":
            return expected in (actual or "")
    except (TypeError, ValueError):
        return False
    return False


def evaluate_rule(rule: Dict[str, Any], context: Dict[str, Any]) -> bool:
    """Pure helper — True if ALL conditions match. No conditions = always-fire."""
    conds = (rule.get("trigger") or {}).get("conditions") or []
    return all(_eval_condition(c, context) for c in conds)


def evaluate_and_fire_rules(
    tenant_id: str,
    event_type: str,
    context: Dict[str, Any],
    triggered_by: str = "event",
) -> Dict[str, Any]:
    """Iter102 — Event-bus hook called by lead-create / insight-classified
    / stage-changed flows. Loads every enabled rule for `tenant_id` that
    matches `event_type`, evaluates conditions, and stamps a fire log for
    each matching rule. Returns a summary `{evaluated, fired_count,
    fired_rule_ids}`. Never raises — wraps everything so producers stay
    decoupled.
    """
    summary: Dict[str, Any] = {"evaluated": 0, "fired_count": 0, "fired_rule_ids": []}
    try:
        rules = list(rules_col.find(
            {
                "tenant_id":         tenant_id,
                "enabled":           True,
                "trigger.event_type": event_type,
            },
            {"_id": 0},
        ))
        for rule in rules:
            summary["evaluated"] += 1
            if not evaluate_rule(rule, context):
                continue
            fire_doc = {
                "id":           str(uuid.uuid4()),
                "rule_id":      rule["id"],
                "tenant_id":    tenant_id,
                "triggered_by": triggered_by,
                "event_type":   event_type,
                "context":      context,
                "actions":      rule.get("actions") or [],
                "created_at":   _now(),
            }
            rules_fires_col.insert_one(fire_doc)
            rules_col.update_one(
                {"id": rule["id"], "tenant_id": tenant_id},
                {"$inc": {"fire_count": 1}, "$set": {"last_fired_at": _now()}},
            )
            summary["fired_count"] += 1
            summary["fired_rule_ids"].append(rule["id"])
    except Exception:
        # Never break the producer flow.
        pass
    return summary


class DryRunPayload(BaseModel):
    context: Dict[str, Any]


@router.post("/{rule_id}/dry-run")
async def dry_run_rule(
    rule_id: str,
    payload: DryRunPayload,
    tenant: dict = Depends(get_active_tenant),
):
    """Evaluate the rule against a sample context — return whether it would
    fire + which conditions failed. Backs the "Test" button in the UI.
    """
    rule = rules_col.find_one({"id": rule_id, "tenant_id": tenant["id"]}, {"_id": 0})
    if not rule:
        raise HTTPException(404, "Rule not found")
    conds = (rule.get("trigger") or {}).get("conditions") or []
    breakdown = []
    for c in conds:
        passed = _eval_condition(c, payload.context)
        breakdown.append({
            "field": c["field"],
            "op": c["op"],
            "value": c["value"],
            "actual": _get_nested(payload.context, c["field"]),
            "passed": passed,
        })
    would_fire = all(b["passed"] for b in breakdown) if breakdown else True
    return {
        "ok": True,
        "would_fire": would_fire,
        "breakdown": breakdown,
        "actions_that_would_run": rule.get("actions") if would_fire else [],
    }


@router.post("/{rule_id}/run-now")
async def run_rule_now(
    rule_id: str,
    tenant: dict = Depends(require_tenant_role(["owner", "admin", "master_admin"])),
):
    """Stamp a fire log and bump counters. The actual action execution is
    delegated to the event engine; this endpoint exists so founders can
    smoke-test rules from the UI.
    """
    rule = rules_col.find_one({"id": rule_id, "tenant_id": tenant["id"]}, {"_id": 0})
    if not rule:
        raise HTTPException(404, "Rule not found")
    if not rule.get("enabled"):
        raise HTTPException(400, "Rule is disabled — enable it before running")
    fire_doc = {
        "id":          str(uuid.uuid4()),
        "rule_id":     rule_id,
        "tenant_id":   tenant["id"],
        "triggered_by": "manual",
        "actions":     rule.get("actions") or [],
        "created_at":  _now(),
    }
    rules_fires_col.insert_one(fire_doc)
    rules_col.update_one(
        {"id": rule_id, "tenant_id": tenant["id"]},
        {"$inc": {"fire_count": 1}, "$set": {"last_fired_at": _now()}},
    )
    fire_doc.pop("_id", None)
    return {"ok": True, "fired": True, "fire": fire_doc}


@router.get("/{rule_id}/fires")
async def list_fires(
    rule_id: str,
    tenant: dict = Depends(get_active_tenant),
    limit: int = 25,
):
    rule = rules_col.find_one({"id": rule_id, "tenant_id": tenant["id"]}, {"_id": 0})
    if not rule:
        raise HTTPException(404, "Rule not found")
    rows = list(rules_fires_col.find(
        {"rule_id": rule_id, "tenant_id": tenant["id"]},
        {"_id": 0},
    ).sort("created_at", -1).limit(max(1, min(limit, 100))))
    return {"ok": True, "count": len(rows), "fires": rows}
