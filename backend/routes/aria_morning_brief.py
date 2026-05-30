"""ARIA — Morning Brief (Batch 5).

Weekday 8 AM (workspace-local) cron that:
  1. Auto-runs `/batch/hot-leads` style enrichment on every hot/engaged
     lead with no fresh intel.
  2. Picks the top 3 NEW signals across the workspace (highest fit_score
     + signal confidence).
  3. Composes a draft opening message for each via Claude.
  4. Sends a single Founder Brief email via Resend with subject
     "Your ARIA Morning Brief — {Date}".

Mirrors the architecture of `routes/aria_eod_wrap.py` so it slots into
the existing startup-loop pattern in `server.py`.

Endpoints
─────────
  GET  /api/aria/morning-brief/config            — fetch tenant config
  POST /api/aria/morning-brief/config            — save tenant config
  POST /api/aria/morning-brief/send-now          — manual trigger (preview/test)
  GET  /api/aria/morning-brief/preview           — last sent brief JSON
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import resend
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import db, get_current_user
from security.encryption import decrypt as _dec
from services.crawl_service import crawl_prospect, MissingCredential, CrawlLimitExceeded
from services.intel_service import synthesise_intel, compose_message

logger = logging.getLogger("aria_morning_brief")

router = APIRouter(prefix="/api/aria/morning-brief", tags=["aria-morning-brief"])

config_col = db["aria_morning_brief_config"]
intel_profiles_col = db["intel_profiles"]
pt_leads_col = db["pt_leads"]
sent_briefs_col = db["aria_morning_brief_sent"]
integrations_col = db["pt_integrations"]


# ─── Config schema ──────────────────────────────────────────────────────
class MorningBriefConfig(BaseModel):
    enabled: bool = False
    send_to_email: str = Field("", description="Founder's email.")
    send_hour_local: int = Field(8, ge=0, le=23)
    timezone_offset_hours: float = Field(0.0, ge=-12.0, le=14.0)
    weekdays_only: bool = True
    max_new_intel: int = Field(20, ge=1, le=50, description="Cap per cron run.")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_cfg(tenant_id: str) -> Dict[str, Any]:
    return config_col.find_one({"tenant_id": tenant_id}, {"_id": 0}) or {}


# ─── Tenant context helper ──────────────────────────────────────────────
def _tenant_meta(tenant_id: str) -> Dict[str, Any]:
    """Light tenant lookup for personalising the brief — founder name etc."""
    t = db["tenants"].find_one({"id": tenant_id}, {"_id": 0, "name": 1, "settings": 1}) or {}
    settings = t.get("settings") or {}
    return {
        "tenant_id": tenant_id,
        "workspace_name": t.get("name") or "your workspace",
        "founder_name": (settings.get("aria_persona") or {}).get("founder_name") or "there",
    }


# ─── Lead picker ────────────────────────────────────────────────────────
def _pick_hot_leads_needing_intel(tenant_id: str, limit: int) -> List[Dict[str, Any]]:
    """Hot/engaged/session_pilot leads in this workspace that don't already
    have an intel_profile."""
    hot = list(
        pt_leads_col.find(
            {
                "tenant_id": tenant_id,
                "stage": {"$in": ["hot", "engaged", "session_pilot"]},
            },
            {"_id": 0},
        )
        .sort("score", -1)
        .limit(limit * 2)
    )
    if not hot:
        return []
    existing = {
        d["lead_id"]
        for d in intel_profiles_col.find(
            {"tenant_id": tenant_id, "lead_id": {"$in": [h["id"] for h in hot]}},
            {"_id": 0, "lead_id": 1},
        )
    }
    return [h for h in hot if h["id"] not in existing][:limit]


async def _enrich_lead(tenant_id: str, lead: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Run crawl + synthesis for a single lead. Returns the intel profile
    on success, None on graceful failure."""
    lead_id = lead.get("id")
    email = (lead.get("email") or "").strip()
    domain = email.split("@")[1].lower() if "@" in email else None
    first = lead.get("first_name") or "there"
    last = lead.get("last_name") or ""
    company = lead.get("company_name") or lead.get("company")
    try:
        crawl = await crawl_prospect(
            tenant_id=tenant_id,
            lead_id=lead_id,
            first_name=first,
            last_name=last,
            email=email,
            company_name=company,
            company_domain=domain,
            linkedin_url=lead.get("linkedin_url"),
            industry=lead.get("industry"),
        )
        profile = await synthesise_intel(
            tenant_id=tenant_id,
            lead_id=lead_id,
            lead_meta={
                "name": f"{first} {last}".strip() or email,
                "first_name": first,
                "company": company or domain,
                "domain": domain,
                "icp": lead.get("icp_fit") or lead.get("icp_tier"),
            },
            crawl=crawl,
        )
        return profile
    except (MissingCredential, CrawlLimitExceeded):
        return None
    except Exception:  # noqa: BLE001
        logger.exception("morning_brief: enrichment failed for lead=%s", lead_id)
        return None


def _rank_signals(profiles: List[Dict[str, Any]], top_n: int = 3) -> List[Dict[str, Any]]:
    """Across all freshly-enriched profiles, pick the top N signals by:
       1) fit_score (desc),
       2) signal confidence (high > med > low),
       3) signal type weight (intent / trigger_event > others)."""
    conf_w = {"high": 3, "med": 2, "low": 1}
    type_w = {
        "intent": 3, "trigger_event": 3, "growth": 2, "buying_authority": 2,
        "engagement": 1, "pain": 2, "competitive": 2, "risk": 0,
    }
    ranked: List[Dict[str, Any]] = []
    for p in profiles:
        fit = int(p.get("fit_score") or 0)
        for s in (p.get("signals") or []):
            if s.get("type") == "risk":
                continue  # skip negatives in the founder brief
            score = fit * 10 + conf_w.get(s.get("confidence", "med"), 2) * 5 + type_w.get(s.get("type", ""), 1)
            ranked.append({
                "score": score,
                "signal": s,
                "lead_id": p["lead_id"],
                "fit_score": fit,
                "best_hook": p.get("best_hook"),
                "summary": p.get("summary", ""),
            })
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:top_n]


# ─── Draft openings (channel = email by default) ────────────────────────
async def _draft_openings(tenant_id: str, top_signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Generate a single opening message draft per top signal."""
    out: List[Dict[str, Any]] = []
    for s in top_signals:
        lead_id = s["lead_id"]
        lead = pt_leads_col.find_one({"id": lead_id, "tenant_id": tenant_id}, {"_id": 0}) or {}
        profile = intel_profiles_col.find_one(
            {"tenant_id": tenant_id, "lead_id": lead_id}, {"_id": 0}
        ) or {}
        first = lead.get("first_name") or "there"
        name = f"{first} {lead.get('last_name','')}".strip() or lead.get("email", "Lead")
        try:
            composed = await compose_message(
                tenant_id=tenant_id,
                lead_id=lead_id,
                channel="email",  # brief shows email draft; founder can change channel in app
                lead_meta={
                    "name": name,
                    "first_name": first,
                    "company": lead.get("company_name") or lead.get("company") or "",
                },
                profile=profile,
            )
        except Exception:
            composed = {"channel": "email", "message": {"subject": "Quick idea", "body": ""}, "ai_powered": False}
        msg = composed.get("message") or {}
        out.append({
            "lead_id": lead_id,
            "lead_name": name,
            "company": lead.get("company_name") or lead.get("company") or "",
            "signal_type": s["signal"].get("type"),
            "signal_label": s["signal"].get("label"),
            "signal_evidence": s["signal"].get("evidence"),
            "fit_score": s["fit_score"],
            "opening_subject": (msg.get("subject") if isinstance(msg, dict) else None) or "Quick idea",
            "opening_body": (msg.get("body") if isinstance(msg, dict) else str(msg)) or "",
        })
    return out


# ─── HTML render ────────────────────────────────────────────────────────
def _signal_label(stype: str) -> str:
    return {
        "intent": "Buying Intent",
        "growth": "Growth Signal",
        "trigger_event": "Trigger Event",
        "buying_authority": "Decision Maker",
        "engagement": "Engagement Signal",
        "pain": "Pain Point",
        "competitive": "Competitive Signal",
    }.get(stype or "", "Signal")


def _render_brief_html(meta: Dict[str, Any], drafts: List[Dict[str, Any]], enriched_count: int) -> str:
    today = datetime.now(timezone.utc).strftime("%a, %b %d")
    cards = ""
    for i, d in enumerate(drafts, start=1):
        cards += f"""
        <div style="border:1px solid #E2E8F0;border-radius:8px;padding:18px;margin-bottom:14px;background:#FFFFFF;">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;">
            <div>
              <div style="font-size:11px;font-weight:bold;text-transform:uppercase;letter-spacing:1.4px;color:#7C35DC;margin-bottom:4px;">#{i} · {_signal_label(d['signal_type'])}</div>
              <div style="font-size:16px;font-weight:bold;color:#0F172A;font-family:'Space Grotesk',Inter,sans-serif;">{d['lead_name']}</div>
              <div style="font-size:13px;color:#64748B;">{d['company'] or '—'}</div>
            </div>
            <div style="text-align:right;">
              <div style="font-size:10px;font-weight:bold;text-transform:uppercase;letter-spacing:1.4px;color:#64748B;">ICP Fit</div>
              <div style="font-size:22px;font-weight:800;color:#10B981;font-family:'Space Grotesk',Inter,sans-serif;line-height:1;">{d['fit_score']}</div>
            </div>
          </div>
          <div style="background:#FAF7FF;border-left:3px solid #7C35DC;padding:10px 12px;border-radius:4px;margin-bottom:12px;">
            <div style="font-size:13px;font-weight:600;color:#0F172A;">{d['signal_label']}</div>
            <div style="font-size:12px;color:#64748B;font-style:italic;margin-top:4px;">"{d['signal_evidence']}"</div>
          </div>
          <div style="font-size:10px;font-weight:bold;text-transform:uppercase;letter-spacing:1.4px;color:#475569;margin-bottom:4px;">Draft opening — Subject</div>
          <div style="font-size:14px;font-weight:600;color:#0F172A;margin-bottom:8px;">{d['opening_subject']}</div>
          <div style="font-size:10px;font-weight:bold;text-transform:uppercase;letter-spacing:1.4px;color:#475569;margin-bottom:4px;">Body</div>
          <div style="font-size:13px;color:#0F172A;white-space:pre-wrap;line-height:1.5;background:#FAFAFA;padding:10px 12px;border-radius:4px;border:1px solid #F1F5F9;">{d['opening_body']}</div>
        </div>
        """

    if not drafts:
        cards = """
        <div style="border:1px solid #E2E8F0;border-radius:8px;padding:24px;text-align:center;color:#64748B;font-size:14px;">
          No new hot-lead intel today. ARIA will keep watching.
        </div>
        """

    return f"""
    <div style="font-family:Inter,-apple-system,sans-serif;max-width:640px;margin:0 auto;color:#0F172A;background:#F8FAFC;padding:24px;">
      <div style="text-align:center;margin-bottom:24px;">
        <div style="display:inline-flex;align-items:center;gap:8px;background:linear-gradient(135deg,#4C1D95 0%,#7C35DC 100%);padding:8px 16px;border-radius:999px;">
          <span style="color:white;font-size:11px;font-weight:bold;letter-spacing:1.4px;text-transform:uppercase;">ARIA Morning Brief</span>
        </div>
        <div style="font-size:28px;font-weight:800;color:#0F172A;font-family:'Space Grotesk',Inter,sans-serif;margin-top:12px;">Good morning, {meta['founder_name']}.</div>
        <div style="font-size:14px;color:#64748B;margin-top:4px;">{today} · {meta['workspace_name']}</div>
      </div>

      <div style="background:#FFFFFF;border:1px solid #E2E8F0;border-radius:8px;padding:14px 18px;margin-bottom:18px;text-align:center;">
        <span style="font-size:13px;color:#475569;">Overnight, ARIA enriched </span>
        <span style="font-size:13px;font-weight:bold;color:#7C35DC;">{enriched_count} hot lead{'s' if enriched_count != 1 else ''}</span>
        <span style="font-size:13px;color:#475569;"> and surfaced these top signals 👇</span>
      </div>

      {cards}

      <div style="text-align:center;margin-top:24px;padding-top:18px;border-top:1px solid #E2E8F0;">
        <a href="{_app_url()}/app/leads" style="display:inline-block;padding:11px 22px;border-radius:6px;background:linear-gradient(135deg,#4C1D95 0%,#7C35DC 100%);color:white;text-decoration:none;font-weight:bold;font-size:13px;letter-spacing:0.6px;">Open Lead Feed →</a>
        <div style="font-size:11px;color:#94A3B8;margin-top:14px;">Disable this brief in Settings → Notifications.</div>
      </div>
    </div>
    """


def _app_url() -> str:
    import os as _os
    return (_os.environ.get("FRONTEND_URL") or "https://app.genleadai.com").rstrip("/")


# ─── Resend send ────────────────────────────────────────────────────────
async def _send_brief_email(*, tenant_id: str, recipient: str, html: str, subject: str) -> Dict[str, Any]:
    """Send via the workspace's Resend identity (encrypted in pt_integrations)
    with graceful fallback to the platform default RESEND_API_KEY."""
    import os as _os

    integ = integrations_col.find_one({"name": "email"}) or {}
    workspace_key = _dec(integ.get("api_key") or "") if integ.get("api_key") else ""
    api_key = workspace_key or _os.environ.get("RESEND_API_KEY") or ""
    if not api_key:
        return {"sent": False, "error": "no_resend_key"}

    from_addr = integ.get("from_address") or _os.environ.get("SENDER_EMAIL") or "onboarding@resend.dev"
    from_name = (integ.get("from_name") or "").strip() or "ARIA"
    params = {
        "from": f"{from_name} <{from_addr}>",
        "to": [recipient],
        "subject": subject,
        "html": html,
    }
    saved = resend.api_key
    resend.api_key = api_key
    try:
        result = await asyncio.to_thread(resend.Emails.send, params)
        return {"sent": True, "provider_id": (result or {}).get("id") if isinstance(result, dict) else None}
    except Exception as e:  # noqa: BLE001
        # iter138 — quieter log line; full traceback only at DEBUG level.
        logger.warning("morning_brief: resend send failed: %s", str(e)[:200])
        return {"sent": False, "error": str(e)[:200]}
    finally:
        resend.api_key = saved


# ─── Public job ─────────────────────────────────────────────────────────
async def run_morning_brief(tenant_id: str, recipient: Optional[str] = None, manual: bool = False) -> Dict[str, Any]:
    """End-to-end: enrich top hot leads → rank signals → draft openings →
    render → send. Persists the result to `aria_morning_brief_sent`."""
    cfg = _get_cfg(tenant_id)
    target = recipient or cfg.get("send_to_email") or ""
    if not target:
        return {"sent": False, "error": "no_recipient"}

    meta = _tenant_meta(tenant_id)
    limit = int(cfg.get("max_new_intel") or 20)

    leads = _pick_hot_leads_needing_intel(tenant_id, limit)
    enriched: List[Dict[str, Any]] = []
    for lead in leads:
        profile = await _enrich_lead(tenant_id, lead)
        if profile:
            enriched.append(profile)
        await asyncio.sleep(0)  # cooperative yield

    # If no new intel today, still pull recent profiles so the brief isn't empty
    if not enriched:
        recent = list(
            intel_profiles_col.find(
                {"tenant_id": tenant_id},
                {"_id": 0},
            )
            .sort("updated_at", -1)
            .limit(10)
        )
        enriched = recent

    top_signals = _rank_signals(enriched, top_n=3)
    drafts = await _draft_openings(tenant_id, top_signals)

    today_label = datetime.now(timezone.utc).strftime("%a, %b %d")
    subject = f"Your ARIA Morning Brief — {today_label}"
    html = _render_brief_html(meta, drafts, enriched_count=len(leads))

    result = await _send_brief_email(tenant_id=tenant_id, recipient=target, html=html, subject=subject)

    sent_briefs_col.insert_one({
        "tenant_id": tenant_id,
        "recipient": target,
        "subject": subject,
        "manual": manual,
        "enriched_count": len(leads),
        "draft_count": len(drafts),
        "sent": bool(result.get("sent")),
        "provider_id": result.get("provider_id"),
        "error": result.get("error"),
        "drafts": drafts,
        "created_at": _now_iso(),
    })

    # Update last_sent_date so the cron doesn't double-fire
    local_today = (datetime.now(timezone.utc) + timedelta(hours=float(cfg.get("timezone_offset_hours") or 0.0))).strftime("%Y-%m-%d")
    config_col.update_one(
        {"tenant_id": tenant_id},
        {"$set": {"last_sent_date": local_today, "last_sent_at": _now_iso()}},
        upsert=True,
    )

    return {
        "sent": bool(result.get("sent")),
        "subject": subject,
        "enriched_count": len(leads),
        "draft_count": len(drafts),
        "provider_id": result.get("provider_id"),
        "error": result.get("error"),
    }


# ─── REST endpoints ─────────────────────────────────────────────────────
@router.get("/config")
async def get_config(current_user: dict = Depends(get_current_user)):
    tenant_id = current_user.get("tenant_id")
    return _get_cfg(tenant_id) or {
        "enabled": False, "send_to_email": current_user.get("email", ""),
        "send_hour_local": 8, "timezone_offset_hours": 5.5,
        "weekdays_only": True, "max_new_intel": 20,
    }


@router.post("/config")
async def save_config(body: MorningBriefConfig, current_user: dict = Depends(get_current_user)):
    tenant_id = current_user.get("tenant_id")
    payload = body.model_dump()
    payload["tenant_id"] = tenant_id
    payload["updated_at"] = _now_iso()
    config_col.update_one(
        {"tenant_id": tenant_id},
        {"$set": payload, "$setOnInsert": {"created_at": _now_iso()}},
        upsert=True,
    )
    return {"saved": True, "config": payload}


@router.post("/send-now")
async def send_now(current_user: dict = Depends(get_current_user)):
    tenant_id = current_user.get("tenant_id")
    cfg = _get_cfg(tenant_id) or {}
    recipient = cfg.get("send_to_email") or current_user.get("email")
    if not recipient:
        raise HTTPException(status_code=400, detail="Set a recipient email in the Morning Brief config first.")
    res = await run_morning_brief(tenant_id, recipient=recipient, manual=True)
    # iter138 — convert send failures into structured 503 (matches eod-wrap pattern).
    # Skip-as-success (e.g. no_recipient handled above; future skip flags) is NOT an error.
    if isinstance(res, dict) and res.get("sent") is False and not res.get("skipped"):
        from services.notification_errors import classify_send_error
        info = classify_send_error(res.get("error", ""))
        raise HTTPException(status_code=info["status"], detail=info)
    return res


@router.get("/last")
async def last_sent(current_user: dict = Depends(get_current_user)):
    tenant_id = current_user.get("tenant_id")
    doc = sent_briefs_col.find_one(
        {"tenant_id": tenant_id},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    return doc or {}


# ─── Background loop ────────────────────────────────────────────────────
async def morning_brief_loop():
    """Tick every 60s. For each tenant with `enabled=true`, if current
    local time matches `send_hour_local` (±5 min window) and we haven't
    already sent today, fire the brief."""
    while True:
        try:
            for cfg in config_col.find({"enabled": True}, {"_id": 0}):
                tenant_id = cfg.get("tenant_id")
                recipient = cfg.get("send_to_email")
                if not (tenant_id and recipient):
                    continue
                send_hour = int(cfg.get("send_hour_local") or 8)
                tz_off = float(cfg.get("timezone_offset_hours") or 0.0)
                weekdays_only = bool(cfg.get("weekdays_only", True))
                now_utc = datetime.now(timezone.utc)
                local_dt = now_utc + timedelta(hours=tz_off)
                # Mon=0 … Sun=6
                if weekdays_only and local_dt.weekday() >= 5:
                    continue
                target_min_utc = int(((send_hour * 60) - (tz_off * 60)) % 1440)
                cur_min_utc = now_utc.hour * 60 + now_utc.minute
                in_window = 0 <= (cur_min_utc - target_min_utc) <= 5
                local_today = local_dt.strftime("%Y-%m-%d")
                if in_window and cfg.get("last_sent_date") != local_today:
                    print(f"[MorningBrief] tenant={tenant_id} → sending to {recipient}")
                    try:
                        await run_morning_brief(tenant_id, recipient=recipient, manual=False)
                    except Exception:
                        logger.exception("morning_brief: cron send failed")
        except Exception:
            logger.exception("morning_brief: loop iteration failed")
        await asyncio.sleep(60)


__all__ = ["router", "run_morning_brief", "morning_brief_loop"]
