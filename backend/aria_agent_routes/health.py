"""Iter76 — Aria health badges.

Returns a per-feature status snapshot the Workspace Settings page renders as
green / amber / red badges so founders see at a glance which Aria muscles are
warmed up. Strictly read-only.
"""
from ._shared import (
    router, training_collection, playbooks_collection, leads_collection,
    activities_collection, db, get_current_user, AriaTrainingPayload,
)
from fastapi import Depends
from datetime import datetime, timezone
from typing import Optional


def _scope_filter(current_user: dict) -> dict:
    """Workspace-scoped filter — falls back to a global filter if the user
    record doesn't carry a tenant_id (legacy demo accounts)."""
    tid = current_user.get("tenant_id") or current_user.get("active_tenant_id")
    return {"tenant_id": tid} if tid else {}


def _humanise_ts(ts: Optional[str]) -> str:
    if not ts:
        return "never"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return ts
    diff = datetime.now(timezone.utc) - dt
    secs = int(diff.total_seconds())
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    days = secs // 86400
    return f"{days}d ago"


@router.get("/health")
async def aria_health(current_user: dict = Depends(get_current_user)):
    """Snapshot of every Aria capability for the current workspace."""
    scope = _scope_filter(current_user)
    tid = scope.get("tenant_id")

    # 1. Training
    training = training_collection.find_one({"scope": "workspace"}, {"_id": 0}) or {}
    training_fields_filled = sum(1 for v in training.values() if isinstance(v, str) and v.strip())
    training_total_fields = len(AriaTrainingPayload().dict())
    training_pct = round((training_fields_filled / max(training_total_fields, 1)) * 100)

    # 2. Active playbooks
    active_playbooks = list(playbooks_collection.find(
        {**scope, "active": True}, {"_id": 0, "playbook_id": 1}
    )) if tid else list(playbooks_collection.find({"active": True}, {"_id": 0, "playbook_id": 1}))

    # 3. Touchpoint journey
    journey = db["workspace_touchpoint_maps"].find_one(scope or {}, {"_id": 0, "touchpoints": 1, "updated_at": 1}) or {}
    journey_tps = len(journey.get("touchpoints") or [])

    # 4. AI Setup Assistant — last published automap_summary
    tenant = db["tenants"].find_one({"id": tid} if tid else {}, {"_id": 0, "settings.automap_summary": 1, "integrations": 1, "settings.sales_channels": 1}) or {}
    automap = (tenant.get("settings") or {}).get("automap_summary") or {}
    auto_setup_applied_at = automap.get("applied_at")

    # 5. Integrations connected
    integrations = tenant.get("integrations") or {}
    connected = [k for k, v in integrations.items() if v and (isinstance(v, dict) and (v.get("api_key") or v.get("connected") or v.get("enabled")))]

    # 6. Sales channels configured
    sales_prefs = (tenant.get("settings") or {}).get("sales_channels") or {}
    selected_channels = sales_prefs.get("selected_channels") or []

    # 7. Brain — most recent activity timestamp
    last_activity = activities_collection.find_one(
        scope or {}, {"_id": 0, "created_at": 1}, sort=[("created_at", -1)]
    ) or {}
    brain_last_ts = last_activity.get("created_at")

    def card(key, label, value, level, hint=None, action_path=None, action_label=None):
        return {
            "key": key, "label": label, "value": value, "level": level,
            "hint": hint, "action_path": action_path, "action_label": action_label,
        }

    cards = [
        card(
            "training",
            "Aria training",
            f"{training_pct}% complete",
            "green" if training_pct >= 60 else "amber" if training_pct >= 20 else "red",
            hint=f"{training_fields_filled} of {training_total_fields} fields filled.",
            action_path="/settings", action_label="Train Aria",
        ),
        card(
            "playbooks",
            "Active playbooks",
            f"{len(active_playbooks)} active",
            "green" if len(active_playbooks) >= 1 else "amber",
            hint=("Activate at least one playbook so Aria knows when to qualify / book / alert."
                  if len(active_playbooks) == 0 else "Aria is following your activated playbooks."),
            action_path="/settings", action_label="Manage playbooks",
        ),
        card(
            "journey",
            "Touchpoint journey",
            f"{journey_tps} touchpoints",
            "green" if journey_tps >= 5 else "amber" if journey_tps >= 1 else "red",
            hint=("Build a touchpoint journey so Aria can schedule outreach."
                  if journey_tps == 0 else f"Last edited: {_humanise_ts(journey.get('updated_at'))}"),
            action_path="/touchpoint-journey", action_label="Edit journey",
        ),
        card(
            "auto_setup",
            "AI Setup Assistant",
            "Workflow published" if auto_setup_applied_at else "Not yet published",
            "green" if auto_setup_applied_at else "amber",
            hint=(f"Last published: {_humanise_ts(auto_setup_applied_at)}" if auto_setup_applied_at
                  else "Upload your GTM doc — Aria will auto-map your workflow."),
            action_path="/ai-setup", action_label="Open assistant",
        ),
        card(
            "integrations",
            "Integrations",
            f"{len(connected)} connected",
            "green" if len(connected) >= 1 else "amber",
            hint=(", ".join(connected[:3]) + ("…" if len(connected) > 3 else "")) if connected else "Connect Saleshandy / Lemlist / your CRM in the Integration Hub.",
            action_path="/integrations", action_label="Open hub",
        ),
        card(
            "sales_channels",
            "Sales channels",
            f"{len(selected_channels)} selected",
            "green" if len(selected_channels) >= 1 else "amber",
            hint=(", ".join(selected_channels) if selected_channels
                  else "Pick which channels Aria can speak on (email / linkedin / whatsapp)."),
            action_path="/settings", action_label="Configure channels",
        ),
        card(
            "brain",
            "Aria brain",
            _humanise_ts(brain_last_ts),
            "green" if brain_last_ts else "amber",
            hint=("Aria has activity to learn from." if brain_last_ts
                  else "No activity yet — Aria starts learning once leads flow in."),
            action_path="/dashboard", action_label="Open dashboard",
        ),
    ]

    green = sum(1 for c in cards if c["level"] == "green")
    overall = "green" if green >= 5 else "amber" if green >= 3 else "red"

    return {
        "overall": overall,
        "score": f"{green}/{len(cards)} muscles warmed up",
        "cards": cards,
    }
