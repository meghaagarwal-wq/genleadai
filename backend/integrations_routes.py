"""ARIA — SalesHandy + Lemlist integration routes.

Bring-your-own-key model: each workspace stores its own encrypted API keys.
Inbound: Lemlist via webhook (real-time) + SalesHandy via 5-min poller.
Outbound: list sequences/campaigns + push leads from ARIA into them.
"""
import os
import base64
import hmac
import hashlib
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Encryption helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_ENC_KEY = os.environ.get("ENCRYPTION_KEY")
_cipher = Fernet(_ENC_KEY.encode()) if _ENC_KEY else None


def _enc(s: str) -> str:
    if not s or not _cipher:
        return ""
    return _cipher.encrypt(s.encode()).decode()


def _dec(s: str) -> str:
    if not s or not _cipher:
        return ""
    try:
        return _cipher.decrypt(s.encode()).decode()
    except InvalidToken:
        return ""


def _mask(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    return f"••••{s[-4:]}" if len(s) >= 4 else "••••"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API clients
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SalesHandyClient:
    BASE = "https://open-api.saleshandy.com/v1"

    def __init__(self, api_key: str):
        self.headers = {"x-api-key": api_key, "Content-Type": "application/json", "Accept": "application/json"}

    async def _req(self, method: str, path: str, **kw) -> Any:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.request(method, f"{self.BASE}{path}", headers=self.headers, **kw)
            if r.status_code >= 400:
                raise HTTPException(r.status_code, f"SalesHandy: {r.text[:200]}")
            return r.json() if r.content else {}

    async def list_sequences(self) -> List[Dict]:
        # SalesHandy v1 lists sequences via POST with filter — fall back to GET if available.
        try:
            data = await self._req("GET", "/sequences?limit=200")
        except HTTPException:
            data = await self._req("POST", "/sequences/get-list", json={"limit": 200, "page": 1})
        if isinstance(data, dict):
            return data.get("data", {}).get("data") or data.get("data") or []
        return data or []

    async def add_prospect(self, sequence_id: str, lead: Dict) -> Dict:
        # SalesHandy supports importing prospects directly into a sequence
        payload = {
            "sequenceId": sequence_id,
            "prospects": [{
                "email": lead["email"],
                "firstName": lead.get("first_name") or "",
                "lastName": lead.get("last_name") or "",
                "phoneNumber": lead.get("phone") or "",
                "companyName": lead.get("company_name") or "",
                "jobTitle": lead.get("job_title") or "",
            }],
            "verifyProspects": False,
        }
        return await self._req("POST", "/prospects/import", json=payload)

    async def list_prospect_activity(self, since_iso: str) -> List[Dict]:
        # Generic activity endpoint — implementations vary; we read recent prospects
        try:
            data = await self._req("GET", f"/activities?since={since_iso}&limit=200")
            return data.get("data", []) if isinstance(data, dict) else (data or [])
        except HTTPException:
            return []


class LemlistClient:
    BASE = "https://api.lemlist.com/api"

    def __init__(self, api_key: str):
        # Lemlist requires HTTP Basic with leading colon: ":APIKEY"
        token = base64.b64encode(f":{api_key}".encode()).decode()
        self.headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

    async def _req(self, method: str, path: str, **kw) -> Any:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.request(method, f"{self.BASE}{path}", headers=self.headers, **kw)
            if r.status_code >= 400:
                raise HTTPException(r.status_code, f"Lemlist: {r.text[:200]}")
            return r.json() if r.content else {}

    async def list_campaigns(self) -> List[Dict]:
        data = await self._req("GET", "/campaigns?limit=100&offset=0")
        return data if isinstance(data, list) else (data.get("data") or [])

    async def add_lead(self, campaign_id: str, lead: Dict) -> Dict:
        payload = {
            "email": lead["email"],
            "firstName": lead.get("first_name") or "",
            "lastName": lead.get("last_name") or "",
            "phone": lead.get("phone") or "",
            "companyName": lead.get("company_name") or "",
            "jobTitle": lead.get("job_title") or "",
        }
        # POST /campaigns/{id}/leads/{email}
        return await self._req("POST", f"/campaigns/{campaign_id}/leads/{lead['email']}", json=payload)

    async def register_webhook(self, target_url: str) -> Dict:
        events = ["contacted", "opened", "clicked", "replied", "bounced", "unsubscribed", "interested", "notInterested", "meetingBooked"]
        return await self._req("POST", "/hooks", json={"targetUrl": target_url, "type": events})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Routes
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class IntegrationKeysPayload(BaseModel):
    saleshandy_api_key: Optional[str] = None
    lemlist_api_key: Optional[str] = None


class SyncPushPayload(BaseModel):
    lead_ids: List[str]
    sequence_id: str  # SalesHandy sequence_id OR Lemlist campaign_id
    platform: str  # "saleshandy" | "lemlist"


def attach_integrations_routes(app, get_current_user, db):
    router = APIRouter(prefix="/api/integrations", tags=["integrations"])

    settings_collection = db["workspace_settings"]
    leads_collection = db["leads"]
    activities_collection = db["activities"]
    synced_prospects = db["integration_synced_prospects"]
    synced_prospects.create_index([("workspace_id", 1), ("platform", 1), ("email", 1)])
    synced_prospects.create_index([("aria_lead_id", 1), ("platform", 1)])

    def _ws_key():
        return "workspace"  # single-workspace deployment for now

    def _get_settings():
        doc = settings_collection.find_one({"scope": _ws_key()}, {"_id": 0}) or {}
        return doc

    # ─── Status / settings ───────────────────────────────
    @router.get("/status")
    async def get_status(current_user: dict = Depends(get_current_user)):
        s = _get_settings()
        sh_enc = (s.get("integrations") or {}).get("saleshandy_api_key")
        ll_enc = (s.get("integrations") or {}).get("lemlist_api_key")
        sh = _dec(sh_enc) if sh_enc else ""
        ll = _dec(ll_enc) if ll_enc else ""
        return {
            "saleshandy": {"connected": bool(sh), "key_preview": _mask(sh)},
            "lemlist": {"connected": bool(ll), "key_preview": _mask(ll)},
        }

    @router.post("/keys")
    async def save_keys(payload: IntegrationKeysPayload, current_user: dict = Depends(get_current_user)):
        s = _get_settings()
        integrations = (s.get("integrations") or {}).copy()
        if payload.saleshandy_api_key is not None:
            integrations["saleshandy_api_key"] = _enc(payload.saleshandy_api_key.strip()) if payload.saleshandy_api_key.strip() else ""
        if payload.lemlist_api_key is not None:
            integrations["lemlist_api_key"] = _enc(payload.lemlist_api_key.strip()) if payload.lemlist_api_key.strip() else ""
        settings_collection.update_one(
            {"scope": _ws_key()},
            {"$set": {"integrations": integrations, "integrations_updated_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        # Auto-register Lemlist webhook on save
        if payload.lemlist_api_key and payload.lemlist_api_key.strip():
            try:
                base = os.environ.get("REACT_APP_BACKEND_URL", "")
                if base:
                    target = f"{base.rstrip('/')}/api/integrations/lemlist/webhook"
                    await LemlistClient(payload.lemlist_api_key.strip()).register_webhook(target)
            except Exception:
                pass  # Don't fail key save if webhook reg has issues
        return {"ok": True}

    @router.delete("/keys/{platform}")
    async def disconnect(platform: str, current_user: dict = Depends(get_current_user)):
        if platform not in ("saleshandy", "lemlist"):
            raise HTTPException(400, "Invalid platform")
        field = f"integrations.{platform}_api_key"
        settings_collection.update_one({"scope": _ws_key()}, {"$set": {field: ""}}, upsert=True)
        return {"ok": True}

    @router.post("/test/{platform}")
    async def test_connection(platform: str, current_user: dict = Depends(get_current_user)):
        s = _get_settings()
        enc = (s.get("integrations") or {}).get(f"{platform}_api_key")
        key = _dec(enc) if enc else ""
        if not key:
            raise HTTPException(400, "API key not set")
        try:
            if platform == "saleshandy":
                seqs = await SalesHandyClient(key).list_sequences()
            elif platform == "lemlist":
                seqs = await LemlistClient(key).list_campaigns()
            else:
                raise HTTPException(400, "Invalid platform")
            return {"ok": True, "found": len(seqs)}
        except HTTPException as e:
            raise HTTPException(e.status_code, e.detail)
        except Exception as e:
            raise HTTPException(502, f"Connection failed: {str(e)[:160]}")

    # ─── Sequences / campaigns ───────────────────────────
    @router.get("/sequences/{platform}")
    async def list_sequences(platform: str, current_user: dict = Depends(get_current_user)):
        s = _get_settings()
        enc = (s.get("integrations") or {}).get(f"{platform}_api_key")
        key = _dec(enc) if enc else ""
        if not key:
            raise HTTPException(400, f"{platform} not connected")
        if platform == "saleshandy":
            data = await SalesHandyClient(key).list_sequences()
            seqs = [{"id": d.get("id") or d.get("_id") or d.get("sequenceId"), "name": d.get("name") or d.get("title") or "Untitled"} for d in (data or [])]
        elif platform == "lemlist":
            data = await LemlistClient(key).list_campaigns()
            seqs = [{"id": d.get("_id") or d.get("id"), "name": d.get("name") or "Untitled"} for d in (data or [])]
        else:
            raise HTTPException(400, "Invalid platform")
        # Drop entries without id
        seqs = [s for s in seqs if s.get("id")]
        return {"sequences": seqs, "platform": platform}

    # ─── Push leads (outbound) ───────────────────────────
    @router.post("/push")
    async def push_leads(payload: SyncPushPayload, current_user: dict = Depends(get_current_user)):
        if payload.platform not in ("saleshandy", "lemlist"):
            raise HTTPException(400, "Invalid platform")
        s = _get_settings()
        enc = (s.get("integrations") or {}).get(f"{payload.platform}_api_key")
        key = _dec(enc) if enc else ""
        if not key:
            raise HTTPException(400, f"{payload.platform} not connected")

        client = SalesHandyClient(key) if payload.platform == "saleshandy" else LemlistClient(key)
        pushed, errors = 0, []
        now_iso = datetime.now(timezone.utc).isoformat()

        for lid in payload.lead_ids:
            lead = leads_collection.find_one({"id": lid}, {"_id": 0})
            if not lead:
                errors.append({"lead_id": lid, "error": "Lead not found"}); continue
            if not lead.get("email"):
                errors.append({"lead_id": lid, "error": "Missing email"}); continue
            email_lc = lead["email"].lower().strip()

            # Skip if already synced to this sequence
            if synced_prospects.find_one({"aria_lead_id": lid, "platform": payload.platform, "sequence_id": payload.sequence_id}):
                errors.append({"lead_id": lid, "error": "Already synced to this sequence"}); continue

            try:
                if payload.platform == "saleshandy":
                    res = await client.add_prospect(payload.sequence_id, lead)
                else:
                    res = await client.add_lead(payload.sequence_id, lead)
                synced_prospects.insert_one({
                    "workspace_id": _ws_key(),
                    "aria_lead_id": lid,
                    "platform": payload.platform,
                    "email": email_lc,
                    "sequence_id": payload.sequence_id,
                    "synced_at": now_iso,
                    "platform_response": str(res)[:500],
                })
                # Log activity
                activities_collection.insert_one({
                    "id": f"act_{datetime.now(timezone.utc).timestamp()}_{lid}",
                    "lead_id": lid,
                    "activity_type": f"pushed_to_{payload.platform}",
                    "description": f"Lead pushed to {payload.platform} sequence {payload.sequence_id}",
                    "created_at": now_iso,
                    "created_by": current_user.get("email", "system"),
                    "metadata": {"sequence_id": payload.sequence_id, "platform": payload.platform},
                })
                pushed += 1
            except HTTPException as e:
                errors.append({"lead_id": lid, "error": str(e.detail)[:160]})
            except Exception as e:
                errors.append({"lead_id": lid, "error": str(e)[:160]})

        return {"pushed": pushed, "failed": len(errors), "errors": errors[:50]}

    # ─── Lemlist webhook ─────────────────────────────────
    LEMLIST_EVENT_MAP = {
        "contacted": "email_sent", "opened": "email_opened", "clicked": "email_clicked",
        "replied": "replied", "bounced": "bounced", "unsubscribed": "unsubscribed",
        "interested": "interested", "notInterested": "not_interested", "meetingBooked": "meeting_scheduled",
    }

    @router.post("/lemlist/webhook")
    async def lemlist_webhook(request: Request):
        try:
            payload = await request.json()
        except Exception:
            raise HTTPException(400, "Invalid JSON")

        evt_type = (payload.get("type") or "").strip()
        email = (payload.get("email") or payload.get("leadEmail") or "").lower().strip()
        if not email:
            return {"ignored": True, "reason": "no email"}

        # Skip bot-detected events
        meta = payload.get("metadata") or {}
        if meta.get("isBot") or meta.get("bot_detected"):
            return {"ignored": True, "reason": "bot"}

        aria_evt = LEMLIST_EVENT_MAP.get(evt_type, f"lemlist_{evt_type}")
        now_iso = datetime.now(timezone.utc).isoformat()

        # Find or create ARIA lead
        lead = leads_collection.find_one({"email": email}, {"_id": 0})
        lead_id = None
        if lead:
            lead_id = lead.get("id")
        else:
            # Create lightweight lead from webhook
            from uuid import uuid4
            lead_id = str(uuid4())
            leads_collection.insert_one({
                "id": lead_id,
                "lead_type": "B2B",
                "first_name": (payload.get("firstName") or "").strip() or "Lead",
                "last_name": (payload.get("lastName") or "").strip() or "",
                "email": email,
                "phone": (payload.get("phone") or "").strip() or None,
                "company_name": (payload.get("companyName") or "").strip() or None,
                "source_channel": "email",
                "source_subchannel": "lemlist",
                "status": "new",
                "icp_score": 0,
                "icp_tier": "cold",
                "tags": ["lemlist"],
                "custom_fields": {"lemlist_campaign_id": payload.get("campaignId")},
                "created_at": now_iso, "updated_at": now_iso,
                "created_by": "lemlist_webhook",
            })

        # Log activity
        activities_collection.insert_one({
            "id": f"act_lemlist_{datetime.now(timezone.utc).timestamp()}",
            "lead_id": lead_id,
            "activity_type": aria_evt,
            "description": f"Lemlist {evt_type} on campaign {payload.get('campaignId', '?')}",
            "created_at": now_iso,
            "created_by": "lemlist",
            "metadata": {"platform": "lemlist", "campaign_id": payload.get("campaignId"), "raw_type": evt_type},
        })
        # Bump engagement on lead
        if aria_evt in ("replied", "interested", "meeting_scheduled"):
            leads_collection.update_one({"id": lead_id}, {"$set": {"updated_at": now_iso, "last_engagement_at": now_iso}})
        return {"ok": True, "lead_id": lead_id, "event": aria_evt}

    # ─── SalesHandy poller (manual trigger / cron) ────────
    @router.post("/saleshandy/poll")
    async def saleshandy_poll(current_user: dict = Depends(get_current_user)):
        """Trigger a manual sync of recent SalesHandy activity into ARIA."""
        s = _get_settings()
        enc = (s.get("integrations") or {}).get("saleshandy_api_key")
        key = _dec(enc) if enc else ""
        if not key:
            raise HTTPException(400, "SalesHandy not connected")

        last_iso = (s.get("integrations") or {}).get("saleshandy_last_polled_at") or (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        client = SalesHandyClient(key)
        synced = 0
        try:
            activity = await client.list_prospect_activity(last_iso)
        except Exception:
            activity = []

        SH_EVENT_MAP = {
            "EMAIL_SENT": "email_sent", "EMAIL_OPENED": "email_opened",
            "LINK_CLICKED": "email_clicked", "REPLIED": "replied",
            "BOUNCED": "bounced", "UNSUBSCRIBED": "unsubscribed",
        }
        now_iso = datetime.now(timezone.utc).isoformat()
        for evt in activity:
            email = ((evt.get("prospect") or {}).get("email") or evt.get("email") or "").lower().strip()
            if not email:
                continue
            evt_type = SH_EVENT_MAP.get((evt.get("activityType") or evt.get("type") or "").upper(), "saleshandy_event")
            lead = leads_collection.find_one({"email": email}, {"_id": 0, "id": 1})
            if not lead:
                continue
            activities_collection.insert_one({
                "id": f"act_sh_{datetime.now(timezone.utc).timestamp()}_{synced}",
                "lead_id": lead["id"], "activity_type": evt_type,
                "description": f"SalesHandy {evt_type}",
                "created_at": now_iso, "created_by": "saleshandy",
                "metadata": {"platform": "saleshandy", "raw": str(evt)[:500]},
            })
            synced += 1

        settings_collection.update_one(
            {"scope": _ws_key()},
            {"$set": {"integrations.saleshandy_last_polled_at": now_iso}},
            upsert=True,
        )
        return {"polled": True, "events_synced": synced, "since": last_iso}

    app.include_router(router)
    return router
