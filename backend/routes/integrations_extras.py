"""Iter99 — Missing V3 lead integrations.

Bundles four small but high-leverage integrations that complete the V3 spec
"lead-pulling/scoring" deliverable:

  1. **Google Ads** — per-tenant webhook-URL generator (the inbound webhook
     handler itself already lives in `routes/integrations_hub.py`).
  2. **Apollo direct pull** — call Apollo's `/v1/mixed_people/search` to
     actively pull leads from a saved search id, not just bulk-CSV import.
  3. **Serper API** — alternative web/news enrichment for the B2B Insights
     Engine (fallback when the tenant doesn't have NewsAPI).
  4. **Website Pixel** — public no-auth track endpoint + JS snippet
     generator so a client can paste one `<script>` on their site to
     capture pageviews and (optionally) form-fill events as leads.

All four share the existing `integration_configs` config-storage and the
existing event-log collections so the Health rollup + UI Hub list pick
them up automatically.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from deps import db, get_current_user
from routes.tenants import get_active_tenant
from routes.integrations_hub import (
    configs_col,
    events_col,
    _normalize_and_capture,
    SUPPORTED_TYPES,
)

router = APIRouter(prefix="/api/integrations", tags=["integrations-extras"])
public_router = APIRouter(prefix="/api/integrations", tags=["integrations-extras-public"])

leads_col = db["leads"]
tenants_col = db["tenants"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Helper: tenant-scoped config getter ────────────────────────────────────
def _get_cfg(tenant_id: str, integration_type: str) -> Dict[str, Any]:
    doc = configs_col.find_one(
        {"tenant_id": tenant_id, "integration_type": integration_type},
        {"_id": 0},
    )
    if not doc:
        raise HTTPException(
            status_code=400,
            detail=f"{integration_type.title()} is not connected — paste your API key in the Integrations Hub first.",
        )
    return doc.get("config") or {}


def _base_url(request: Request) -> str:
    """Best-effort public URL. Honours X-Forwarded-* headers from the
    Kubernetes ingress so we hand callers the correct external URL,
    not the internal pod URL.
    """
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    return f"{proto}://{host}".rstrip("/")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. GOOGLE ADS — Webhook URL generator
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.get("/google-ads/webhook-info")
async def google_ads_webhook_info(
    request: Request,
    tenant: dict = Depends(get_active_tenant),
):
    """Return the per-tenant webhook URL the client pastes into the
    Google Ads Lead Form extension "Webhook URL" field.

    Google Ads also expects a manually-set "Key" — we generate a random
    secret on first call and stash it in the integration config so the
    client can copy both fields without re-rolling them every visit.
    """
    cfg_doc = configs_col.find_one(
        {"tenant_id": tenant["id"], "integration_type": "google_ads"},
        {"_id": 0},
    ) or {}
    cfg = cfg_doc.get("config") or {}
    secret = cfg.get("webhook_key")
    if not secret:
        secret = uuid.uuid4().hex
        configs_col.update_one(
            {"tenant_id": tenant["id"], "integration_type": "google_ads"},
            {"$set": {
                "tenant_id": tenant["id"],
                "integration_type": "google_ads",
                "status": cfg_doc.get("status") or "not_connected",
                "config.webhook_key": secret,
                "updated_at": _now_iso(),
            }},
            upsert=True,
        )
    base = _base_url(request)
    return {
        "webhook_url": f"{base}/api/integrations/google-ads/webhook/{tenant['id']}",
        "webhook_key": secret,
        "instructions": [
            "Open Google Ads → Campaigns → Lead Form extension.",
            "Paste the webhook URL into the 'Webhook URL' field.",
            "Paste the webhook key into the 'Key' field.",
            "Save — Aria will start capturing leads automatically.",
        ],
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. APOLLO — Direct active pull from a saved search
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
APOLLO_BASE = "https://api.apollo.io/v1"


def _apollo_normalize(p: Dict[str, Any]) -> Dict[str, Any]:
    """Apollo person → Aria raw lead payload."""
    org = p.get("organization") or {}
    return {
        "first_name":   p.get("first_name") or "Lead",
        "last_name":    p.get("last_name") or "",
        "email":        p.get("email"),
        "phone":        p.get("sanitized_phone") or p.get("phone_number"),
        "company":      org.get("name") or p.get("organization_name"),
        "job_title":    p.get("title"),
        "linkedin_url": p.get("linkedin_url"),
        "country":      p.get("country"),
        "industry":     org.get("industry"),
        "message":      f"Imported from Apollo search · {p.get('id', 'unknown')}",
        "utm_source":   "apollo",
        "external_id":  p.get("id"),
    }


class ApolloPullPayload(BaseModel):
    saved_search_id: Optional[str] = Field(default=None, description="Apollo saved search id (preferred)")
    keyword: Optional[str] = Field(default=None, description="Free-text query fallback if no saved_search_id")
    page: int = Field(default=1, ge=1, le=20)
    per_page: int = Field(default=25, ge=1, le=100)


@router.post("/apollo/test-connection")
async def apollo_test_connection(tenant: dict = Depends(get_active_tenant)):
    """Verify the stored Apollo API key is valid by hitting the
    /auth/health endpoint (cheap, no quota burn)."""
    cfg = _get_cfg(tenant["id"], "apollo")
    api_key = cfg.get("api_key")
    if not api_key:
        raise HTTPException(400, "Apollo API key missing — paste it in the integration config first.")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{APOLLO_BASE}/auth/health",
                headers={"x-api-key": api_key, "Accept": "application/json"},
            )
            ok = r.status_code == 200
            return {"ok": ok, "status": r.status_code, "body": (r.json() if ok else r.text[:200])}
    except Exception as e:
        raise HTTPException(502, f"Apollo unreachable: {str(e)[:160]}")


@router.post("/apollo/pull")
async def apollo_pull_leads(
    payload: ApolloPullPayload,
    tenant: dict = Depends(get_active_tenant),
    request: Request = None,
):
    """Actively pull leads from Apollo's people-search and capture them.

    Uses the existing `_normalize_and_capture` helper so dedup, scoring,
    and event-log behaviour matches the inbound webhook path.
    """
    cfg = _get_cfg(tenant["id"], "apollo")
    api_key = cfg.get("api_key")
    if not api_key:
        raise HTTPException(400, "Apollo API key missing.")

    body: Dict[str, Any] = {
        "page": payload.page,
        "per_page": payload.per_page,
    }
    if payload.saved_search_id:
        body["saved_search_id"] = payload.saved_search_id
    elif payload.keyword:
        body["q_keywords"] = payload.keyword
    else:
        raise HTTPException(400, "Provide either saved_search_id or keyword.")

    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            r = await client.post(
                f"{APOLLO_BASE}/mixed_people/search",
                headers={"x-api-key": api_key, "Content-Type": "application/json"},
                json=body,
            )
    except Exception as e:
        raise HTTPException(502, f"Apollo request failed: {str(e)[:160]}")

    if r.status_code in (401, 403):
        raise HTTPException(400, "Apollo rejected the API key. Reconnect with a fresh key.")
    if r.status_code == 429:
        raise HTTPException(429, "Apollo rate-limited this workspace. Wait 60s and retry.")
    if r.status_code != 200:
        raise HTTPException(502, f"Apollo returned {r.status_code}: {r.text[:160]}")

    data = r.json() or {}
    people: List[Dict[str, Any]] = data.get("people") or data.get("contacts") or []

    imported = 0
    deduped = 0
    failed = 0
    for p in people:
        raw = _apollo_normalize(p)
        try:
            res = await _normalize_and_capture(tenant["id"], raw, "apollo", request)
            if res.get("deduplicated"):
                deduped += 1
            else:
                imported += 1
        except Exception:
            failed += 1

    # Stamp last-sync so the Health rollup shows it.
    configs_col.update_one(
        {"tenant_id": tenant["id"], "integration_type": "apollo"},
        {"$set": {"last_sync_at": _now_iso(), "status": "connected"}},
    )

    return {
        "ok": True,
        "fetched": len(people),
        "imported": imported,
        "deduplicated": deduped,
        "failed": failed,
        "apollo_pagination": data.get("pagination") or {},
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. SERPER API — Web/news enrichment for B2B Insights
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SERPER_BASE = "https://google.serper.dev"


class SerperTestPayload(BaseModel):
    pass


@router.post("/serper/test-connection")
async def serper_test_connection(tenant: dict = Depends(get_active_tenant)):
    cfg = _get_cfg(tenant["id"], "serper")
    api_key = cfg.get("api_key")
    if not api_key:
        raise HTTPException(400, "Serper API key missing.")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{SERPER_BASE}/search",
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                json={"q": "test", "num": 1},
            )
            return {"ok": r.status_code == 200, "status": r.status_code}
    except Exception as e:
        raise HTTPException(502, f"Serper unreachable: {str(e)[:160]}")


async def serper_company_news(api_key: str, company: str, num: int = 5) -> List[Dict[str, Any]]:
    """Pure helper — pull recent news for a company via Serper.

    Used by the B2B Insights Engine as a NewsAPI fallback. Returns a
    NewsAPI-compatible shape `[{title, description, published_at,
    source, url}]` so the existing pt_insights classifier doesn't care
    which source the news came from.
    """
    if not api_key or not company:
        return []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{SERPER_BASE}/news",
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                json={"q": f'"{company}"', "num": num},
            )
            if r.status_code != 200:
                return []
            news = (r.json() or {}).get("news") or []
            return [
                {
                    "title":        n.get("title"),
                    "description":  n.get("snippet"),
                    "published_at": n.get("date"),
                    "source":       n.get("source"),
                    "url":          n.get("link"),
                }
                for n in news[:num]
            ]
    except Exception:
        return []


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. WEBSITE PIXEL — JS snippet + public tracking endpoint
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.get("/website-pixel/snippet")
async def website_pixel_snippet(
    request: Request,
    tenant: dict = Depends(get_active_tenant),
):
    """Generate the `<script>` snippet the client pastes into their site's
    `<head>`. The snippet beacons pageviews to our public endpoint and
    auto-captures any form submission with a `data-aria-form` attribute
    or matching `email/phone` fields.
    """
    base = _base_url(request)
    tenant_id = tenant["id"]
    snippet = (
        '<!-- Aria Website Pixel -->\n'
        '<script>\n'
        '(function(){\n'
        '  var t="' + tenant_id + '";\n'
        '  var endpoint="' + base + '/api/integrations/website-pixel/track/' + tenant_id + '";\n'
        '  function beacon(payload){\n'
        '    try{\n'
        '      var data=JSON.stringify(payload);\n'
        '      if(navigator.sendBeacon){navigator.sendBeacon(endpoint,new Blob([data],{type:"application/json"}));}\n'
        '      else{fetch(endpoint,{method:"POST",mode:"no-cors",headers:{"Content-Type":"application/json"},body:data});}\n'
        '    }catch(e){}\n'
        '  }\n'
        '  // Pageview\n'
        '  beacon({event:"pageview",url:location.href,referrer:document.referrer,ts:Date.now()});\n'
        '  // Form submission capture — looks for forms with data-aria-form OR an email input\n'
        '  document.addEventListener("submit",function(ev){\n'
        '    try{\n'
        '      var f=ev.target;if(!(f instanceof HTMLFormElement))return;\n'
        '      var email=f.querySelector(\'input[type=email],input[name*="mail" i]\');\n'
        '      var phone=f.querySelector(\'input[type=tel],input[name*="phone" i]\');\n'
        '      var first=f.querySelector(\'input[name*="first" i],input[name="name"]\');\n'
        '      var last=f.querySelector(\'input[name*="last" i]\');\n'
        '      var company=f.querySelector(\'input[name*="company" i],input[name*="org" i]\');\n'
        '      var msg=f.querySelector(\'textarea\');\n'
        '      if(!email && !phone && !f.hasAttribute("data-aria-form"))return;\n'
        '      beacon({\n'
        '        event:"form_submit",\n'
        '        url:location.href,\n'
        '        first_name:first?first.value:undefined,\n'
        '        last_name:last?last.value:undefined,\n'
        '        email:email?email.value:undefined,\n'
        '        phone:phone?phone.value:undefined,\n'
        '        company:company?company.value:undefined,\n'
        '        message:msg?msg.value:undefined,\n'
        '        consent:true,\n'
        '        ts:Date.now()\n'
        '      });\n'
        '    }catch(e){}\n'
        '  },true);\n'
        '})();\n'
        '</script>\n'
    )
    return {
        "tenant_id": tenant_id,
        "track_endpoint": f"{base}/api/integrations/website-pixel/track/{tenant_id}",
        "snippet": snippet,
        "snippet_length": len(snippet),
    }


class PixelEvent(BaseModel):
    event: str = Field(default="pageview", max_length=40)
    url: Optional[str] = Field(default=None, max_length=2000)
    referrer: Optional[str] = Field(default=None, max_length=2000)
    ts: Optional[int] = None
    # Form-submit payload (only when event=form_submit)
    first_name: Optional[str] = Field(default=None, max_length=120)
    last_name:  Optional[str] = Field(default=None, max_length=120)
    email:      Optional[str] = Field(default=None, max_length=255)
    phone:      Optional[str] = Field(default=None, max_length=40)
    company:    Optional[str] = Field(default=None, max_length=200)
    message:    Optional[str] = Field(default=None, max_length=2000)
    consent:    bool = True


@public_router.post("/website-pixel/track/{tenant_id}")
async def website_pixel_track(tenant_id: str, payload: PixelEvent, request: Request):
    """Public no-auth tracking endpoint. Two event modes:

    - `pageview` → just logs into `integration_events` for analytics.
    - `form_submit` (or any event with email/phone) → also runs through
      the standard lead-capture pipeline (dedup + touchpoints).
    """
    # Always log the raw event
    events_col.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "integration_type": "website_pixel",
        "direction": "inbound",
        "event_type": payload.event or "pageview",
        "raw_payload": payload.model_dump(),
        "page_url": payload.url,
        "referrer": payload.referrer,
        "ua": request.headers.get("user-agent"),
        "ip": request.client.host if request.client else None,
        "processed": True,
        "created_at": _now_iso(),
    })

    # If it's a lead-bearing event, also create a lead
    has_lead = payload.event == "form_submit" or payload.email or payload.phone
    if has_lead:
        raw = {
            "first_name": payload.first_name,
            "last_name":  payload.last_name,
            "email":      payload.email,
            "phone":      payload.phone,
            "company":    payload.company,
            "message":    payload.message or f"Website pixel: {payload.event}",
            "consent":    payload.consent,
            "utm_source": "website_pixel",
        }
        try:
            res = await _normalize_and_capture(tenant_id, raw, "website_pixel", request)
            return {"ok": True, "captured": True, "lead_id": res.get("lead_id")}
        except Exception as e:
            return {"ok": True, "captured": False, "error": str(e)[:200]}
    return {"ok": True, "captured": False}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Register the new types into SUPPORTED_TYPES so the catalog/list endpoints
# pick them up automatically. Side-effect at module import.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SUPPORTED_TYPES.setdefault("serper", {
    "category": "analytics",
    "label": "Serper (Web/News Search)",
    "direction": "outbound",
})
SUPPORTED_TYPES.setdefault("website_pixel", {
    "category": "lead_source",
    "label": "Website Pixel",
    "direction": "inbound",
})
