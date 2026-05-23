"""ARIA — SalesHandy + Lemlist integration routes.

Bring-your-own-key model: each workspace stores its own encrypted API keys.
Inbound: Lemlist via webhook (real-time) + SalesHandy via 5-min poller.
Outbound: list sequences/campaigns + push leads from ARIA into them.
"""
import os
import asyncio
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


def _humanise_provider_error(platform: str, raw: str, status_code: int) -> str:
    """Convert a noisy provider JSON error into a founder-friendly hint.

    iter82 — Saleshandy returns `{"error":true,"type":"auth","code":1001,"message":"Invalid token"}`
    which is jargon-heavy. We map the most common failure modes to a single
    actionable sentence so the founder knows exactly what to do next.
    """
    raw_low = (raw or "").lower()
    name = platform.title()
    # Auth failures — the most common case.
    if any(needle in raw_low for needle in ("invalid token", "invalid api key", "unauthor", "401", "code\":1001", "code\":1003")):
        return (
            f"{name} rejected the API key. Double-check you copied the FULL key from "
            f"{name}'s API settings page and that it hasn't been revoked. Paste a fresh key, "
            "click Update, then Test connection again."
        )
    if "rate" in raw_low and ("limit" in raw_low or "429" in raw_low):
        return f"{name} is rate-limiting this workspace. Wait 60 seconds and try again."
    if "forbidden" in raw_low or "403" in raw_low:
        return (
            f"The {name} key is valid but lacks the right permissions/workspace scope. "
            "Open the API key settings in {name} and grant access to the sequences/campaigns endpoint."
        )
    if status_code >= 500:
        return f"{name} is having a server issue right now ({status_code}). Try again in a minute."
    # Fallback — keep the raw message but trim provider scaffolding.
    return f"{name} returned an error ({status_code}). {raw[:200]}"


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
                # iter82 — detect Saleshandy's auth-in-400 quirk and emit a clean
                # detail instead of dumping their raw JSON. The outer caller
                # (_humanise_provider_error) still gets first dibs, but this is
                # the inner safety net.
                body_low = (r.text or "").lower()
                if (
                    r.status_code in (401, 403)
                    or "\"type\":\"auth\"" in body_low
                    or "invalid token" in body_low
                    or "invalid api key" in body_low
                ):
                    raise HTTPException(400, "Saleshandy rejected the API key (auth). Paste a fresh key from Saleshandy → Settings → API.")
                raise HTTPException(r.status_code, f"Saleshandy returned {r.status_code}.")
            return r.json() if r.content else {}

    async def list_sequences(self) -> List[Dict]:
        # iter82 — Saleshandy migrated to GET /v1/sequences with no params
        # (POST /sequences/get-list is deprecated and returns 404). Match the
        # canonical implementation in routes/outreach_import.py to keep both
        # call paths in sync.
        data = await self._req("GET", "/sequences")
        if isinstance(data, dict):
            items = (data.get("data") or {}).get("sequences") if isinstance(data.get("data"), dict) else None
            if items is None:
                items = data.get("sequences") or data.get("data") or []
            return items if isinstance(items, list) else []
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
                # Use BACKEND_URL (backend convention) instead of
                # REACT_APP_BACKEND_URL (frontend env var) so this works
                # correctly in production where only BACKEND_URL is set on the
                # backend side.
                base = os.environ.get("BACKEND_URL", "")
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
            raise HTTPException(400, f"No {platform.title()} API key saved yet. Paste the key, click Update, then Test connection.")
        try:
            if platform == "saleshandy":
                seqs = await SalesHandyClient(key).list_sequences()
            elif platform == "lemlist":
                seqs = await LemlistClient(key).list_campaigns()
            else:
                raise HTTPException(400, "Invalid platform")
            return {"ok": True, "found": len(seqs)}
        except HTTPException as e:
            # iter82 — convert raw provider JSON into a founder-friendly message.
            raw = str(e.detail or "")
            friendly = _humanise_provider_error(platform, raw, e.status_code)
            raise HTTPException(e.status_code, friendly)
        except Exception as e:
            raise HTTPException(502, f"Could not reach {platform.title()}. Network error: {str(e)[:120]}")

    # ─── Sequences / campaigns ───────────────────────────
    @router.get("/sequences/{platform}")
    async def list_sequences(platform: str, current_user: dict = Depends(get_current_user)):
        s = _get_settings()
        enc = (s.get("integrations") or {}).get(f"{platform}_api_key")
        key = _dec(enc) if enc else ""
        if not key:
            raise HTTPException(400, f"{platform.title()} not connected — paste an API key first.")
        try:
            if platform == "saleshandy":
                data = await SalesHandyClient(key).list_sequences()
                seqs = [{"id": d.get("id") or d.get("_id") or d.get("sequenceId"), "name": d.get("name") or d.get("title") or "Untitled"} for d in (data or [])]
            elif platform == "lemlist":
                data = await LemlistClient(key).list_campaigns()
                seqs = [{"id": d.get("_id") or d.get("id"), "name": d.get("name") or "Untitled"} for d in (data or [])]
            else:
                raise HTTPException(400, "Invalid platform")
        except HTTPException as e:
            # iter82 — humanise upstream provider errors so the founder sees
            # a clear next step instead of raw JSON.
            raw = str(e.detail or "")
            friendly = _humanise_provider_error(platform, raw, e.status_code)
            raise HTTPException(e.status_code, friendly)
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

    # ─── Automation rules ───────────────────────────────
    rules_collection = db["integration_automation_rules"]
    rules_collection.create_index([("workspace_id", 1), ("active", 1)])

    class AutomationRule(BaseModel):
        platform: str          # 'saleshandy' | 'lemlist'
        sequence_id: str
        sequence_name: Optional[str] = None
        trigger: str           # 'status' | 'source' | 'icp_tier'
        trigger_value: str     # e.g. 'qualified', 'website_form', 'hot'
        active: bool = True

    @router.get("/automation/rules")
    async def list_rules(current_user: dict = Depends(get_current_user)):
        rules = list(rules_collection.find({"workspace_id": _ws_key()}, {"_id": 0}).sort("created_at", -1))
        return {"rules": rules}

    @router.post("/automation/rules")
    async def create_rule(rule: AutomationRule, current_user: dict = Depends(get_current_user)):
        if rule.platform not in ("saleshandy", "lemlist"):
            raise HTTPException(400, "Invalid platform")
        if rule.trigger not in ("status", "source", "icp_tier"):
            raise HTTPException(400, "Invalid trigger")
        from uuid import uuid4
        doc = rule.dict()
        doc["id"] = str(uuid4())
        doc["workspace_id"] = _ws_key()
        doc["created_at"] = datetime.now(timezone.utc).isoformat()
        doc["created_by"] = current_user.get("email", "system")
        doc["last_run_at"] = None
        doc["runs"] = 0
        rules_collection.insert_one(dict(doc))
        return {k: v for k, v in doc.items() if k != "_id"}

    @router.patch("/automation/rules/{rule_id}")
    async def toggle_rule(rule_id: str, current_user: dict = Depends(get_current_user)):
        r = rules_collection.find_one({"id": rule_id, "workspace_id": _ws_key()}, {"_id": 0})
        if not r:
            raise HTTPException(404, "Rule not found")
        rules_collection.update_one({"id": rule_id}, {"$set": {"active": not r.get("active", True)}})
        return {"ok": True, "active": not r.get("active", True)}

    @router.delete("/automation/rules/{rule_id}")
    async def delete_rule(rule_id: str, current_user: dict = Depends(get_current_user)):
        rules_collection.delete_one({"id": rule_id, "workspace_id": _ws_key()})
        return {"ok": True}

    # ─── Auto-apply rules to a single lead (called from lead-status routes) ───
    async def apply_rules_to_lead(lead: Dict, trigger_change: Dict):
        """trigger_change: {'status': 'qualified'} or {'source': 'linkedin'} etc."""
        if not lead or not lead.get("email"):
            return
        rules = list(rules_collection.find({"workspace_id": _ws_key(), "active": True}, {"_id": 0}))
        if not rules:
            return
        s = _get_settings()
        for rule in rules:
            trigger = rule.get("trigger")
            value = rule.get("trigger_value")
            if trigger not in trigger_change:
                continue
            if trigger_change[trigger] != value:
                continue
            # Match — push the lead
            platform = rule["platform"]
            enc = (s.get("integrations") or {}).get(f"{platform}_api_key")
            key = _dec(enc) if enc else ""
            if not key:
                continue
            # Skip if already synced to this sequence
            if synced_prospects.find_one({"aria_lead_id": lead["id"], "platform": platform, "sequence_id": rule["sequence_id"]}):
                continue
            try:
                client = SalesHandyClient(key) if platform == "saleshandy" else LemlistClient(key)
                if platform == "saleshandy":
                    await client.add_prospect(rule["sequence_id"], lead)
                else:
                    await client.add_lead(rule["sequence_id"], lead)
                now_iso = datetime.now(timezone.utc).isoformat()
                synced_prospects.insert_one({
                    "workspace_id": _ws_key(), "aria_lead_id": lead["id"],
                    "platform": platform, "email": lead["email"].lower().strip(),
                    "sequence_id": rule["sequence_id"], "synced_at": now_iso,
                    "via_rule": rule["id"],
                })
                activities_collection.insert_one({
                    "id": f"act_rule_{datetime.now(timezone.utc).timestamp()}",
                    "lead_id": lead["id"],
                    "activity_type": f"auto_pushed_to_{platform}",
                    "description": f"Auto-pushed via rule: {trigger}={value} → {platform} {rule.get('sequence_name', rule['sequence_id'])}",
                    "created_at": now_iso, "created_by": "automation",
                    "metadata": {"rule_id": rule["id"], "platform": platform},
                })
                rules_collection.update_one({"id": rule["id"]}, {"$set": {"last_run_at": now_iso}, "$inc": {"runs": 1}})
            except Exception as e:
                print(f"[AutomationRule] {rule['id']} failed for lead {lead['id']}: {e}")

    # Expose the helper so other routers (server.py lead status update) can call it
    app.state.apply_integration_rules = apply_rules_to_lead

    @router.post("/automation/rules/{rule_id}/test")
    async def test_rule(rule_id: str, current_user: dict = Depends(get_current_user)):
        """Dry-run a rule against a recent matching lead — show what WOULD happen."""
        rule = rules_collection.find_one({"id": rule_id, "workspace_id": _ws_key()}, {"_id": 0})
        if not rule:
            raise HTTPException(404, "Rule not found")
        # Find a recent lead matching the trigger
        match_field = "status" if rule["trigger"] == "status" else ("source_channel" if rule["trigger"] == "source" else "icp_tier")
        sample = leads_collection.find_one(
            {match_field: rule["trigger_value"]},
            {"_id": 0, "id": 1, "first_name": 1, "last_name": 1, "email": 1, "company_name": 1, "status": 1, match_field: 1},
            sort=[("created_at", -1)],
        )
        if not sample:
            return {
                "would_run": False,
                "reason": f"No leads currently match {rule['trigger']}={rule['trigger_value']}.",
                "sample": None,
                "rule": rule,
            }
        # Check if would actually push (not already synced)
        already = synced_prospects.find_one({
            "aria_lead_id": sample.get("id"),
            "platform": rule["platform"],
            "sequence_id": rule["sequence_id"],
        })
        s = _get_settings()
        enc = (s.get("integrations") or {}).get(f"{rule['platform']}_api_key")
        connected = bool(_dec(enc) if enc else "")
        return {
            "would_run": connected and not already,
            "reason": (
                "Would push this lead now." if connected and not already
                else f"{rule['platform']} not connected." if not connected
                else "Already pushed to this sequence — would skip."
            ),
            "sample": {
                "id": sample.get("id"),
                "name": f"{sample.get('first_name', '')} {sample.get('last_name', '')}".strip() or sample.get("email"),
                "email": sample.get("email"),
                "company": sample.get("company_name"),
            },
            "rule": rule,
        }

    # ─── SalesHandy background auto-poll loop (every 5 min) ───
    async def _saleshandy_poll_loop():
        """Background loop: every 5 minutes, poll SalesHandy for activity."""
        while True:
            try:
                s = _get_settings()
                enc = (s.get("integrations") or {}).get("saleshandy_api_key")
                key = _dec(enc) if enc else ""
                if key:
                    last_iso = (s.get("integrations") or {}).get("saleshandy_last_polled_at") or (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
                    client = SalesHandyClient(key)
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
                    synced = 0
                    for evt in activity or []:
                        email = ((evt.get("prospect") or {}).get("email") or evt.get("email") or "").lower().strip()
                        if not email:
                            continue
                        evt_type = SH_EVENT_MAP.get((evt.get("activityType") or evt.get("type") or "").upper(), "saleshandy_event")
                        lead = leads_collection.find_one({"email": email}, {"_id": 0, "id": 1})
                        if not lead:
                            continue
                        activities_collection.insert_one({
                            "id": f"act_sh_auto_{datetime.now(timezone.utc).timestamp()}_{synced}",
                            "lead_id": lead["id"], "activity_type": evt_type,
                            "description": f"SalesHandy {evt_type}",
                            "created_at": now_iso, "created_by": "saleshandy_auto",
                            "metadata": {"platform": "saleshandy"},
                        })
                        synced += 1
                    settings_collection.update_one(
                        {"scope": _ws_key()},
                        {"$set": {"integrations.saleshandy_last_polled_at": now_iso}},
                        upsert=True,
                    )
                    if synced > 0:
                        print(f"[SalesHandyAutoPoll] synced {synced} events")
            except Exception as e:
                print(f"[SalesHandyAutoPoll] loop error: {e}")
            await asyncio.sleep(300)  # 5 min

    @app.on_event("startup")
    async def _start_saleshandy_poll_loop():
        asyncio.create_task(_saleshandy_poll_loop())
        print("[SalesHandyAutoPoll] Background loop started (5 min tick)")

    @router.get("/digest/today")
    async def digest_today(current_user: dict = Depends(get_current_user)):
        """
        Today's sequence activity digest — powers the Dashboard 'Sync Activity Digest' card.
        Counts today's (UTC) activities coming from Lemlist / SalesHandy (auto-poll + webhooks)
        plus pushes from automation rules or manual push.
        """
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

        # Activity types we care about for the digest
        EVENT_TYPES = [
            "email_sent", "email_opened", "email_clicked", "replied",
            "bounced", "meeting_scheduled", "interested",
            "pushed_to_lemlist", "pushed_to_saleshandy",
            "auto_pushed_to_lemlist", "auto_pushed_to_saleshandy",
        ]

        pipeline = [
            {"$match": {
                "created_at": {"$gte": today_start},
                "activity_type": {"$in": EVENT_TYPES},
            }},
            {"$group": {"_id": "$activity_type", "count": {"$sum": 1}}},
        ]
        rows = {row["_id"]: row["count"] for row in activities_collection.aggregate(pipeline)}

        opened = rows.get("email_opened", 0)
        clicked = rows.get("email_clicked", 0)
        replied = rows.get("replied", 0)
        bounced = rows.get("bounced", 0)
        meetings = rows.get("meeting_scheduled", 0) + rows.get("interested", 0)
        pushed = (
            rows.get("pushed_to_lemlist", 0)
            + rows.get("pushed_to_saleshandy", 0)
            + rows.get("auto_pushed_to_lemlist", 0)
            + rows.get("auto_pushed_to_saleshandy", 0)
        )
        auto_pushed = rows.get("auto_pushed_to_lemlist", 0) + rows.get("auto_pushed_to_saleshandy", 0)
        sent = rows.get("email_sent", 0)

        # Connection state for empty-state messaging
        s = _get_settings()
        integ = s.get("integrations") or {}
        lemlist_connected = bool(_dec(integ.get("lemlist_api_key")) if integ.get("lemlist_api_key") else "")
        saleshandy_connected = bool(_dec(integ.get("saleshandy_api_key")) if integ.get("saleshandy_api_key") else "")

        # Last 5 recent events for the activity list
        recent_cursor = activities_collection.find(
            {"created_at": {"$gte": today_start}, "activity_type": {"$in": EVENT_TYPES}},
            {"_id": 0, "id": 1, "lead_id": 1, "activity_type": 1, "created_at": 1, "metadata": 1, "created_by": 1, "description": 1},
        ).sort("created_at", -1).limit(5)
        recent = list(recent_cursor)

        # Hydrate recent events with lead name
        lead_ids = list({r["lead_id"] for r in recent if r.get("lead_id")})
        leads_by_id = {}
        if lead_ids:
            from bson import ObjectId as _OID
            object_ids = []
            string_ids = []
            for lid in lead_ids:
                try:
                    object_ids.append(_OID(lid))
                except Exception:
                    string_ids.append(lid)
            if object_ids:
                for doc in leads_collection.find(
                    {"_id": {"$in": object_ids}},
                    {"_id": 1, "first_name": 1, "last_name": 1, "company_name": 1, "email": 1},
                ):
                    leads_by_id[str(doc["_id"])] = {
                        "name": f"{doc.get('first_name', '')} {doc.get('last_name', '')}".strip() or doc.get("email"),
                        "company": doc.get("company_name"),
                    }
            if string_ids:
                for doc in leads_collection.find(
                    {"id": {"$in": string_ids}},
                    {"_id": 0, "id": 1, "first_name": 1, "last_name": 1, "company_name": 1, "email": 1},
                ):
                    leads_by_id[doc["id"]] = {
                        "name": f"{doc.get('first_name', '')} {doc.get('last_name', '')}".strip() or doc.get("email"),
                        "company": doc.get("company_name"),
                    }
        for r in recent:
            info = leads_by_id.get(r.get("lead_id") or "", {})
            r["lead_name"] = info.get("name")
            r["company"] = info.get("company")

        return {
            "today_start": today_start,
            "connected": {"lemlist": lemlist_connected, "saleshandy": saleshandy_connected},
            "any_connected": lemlist_connected or saleshandy_connected,
            "counts": {
                "emails_sent": sent,
                "emails_opened": opened,
                "links_clicked": clicked,
                "replies": replied,
                "meetings_booked": meetings,
                "bounced": bounced,
                "pushed_to_sequences": pushed,
                "auto_pushed": auto_pushed,
            },
            "recent": recent,
        }

    app.include_router(router)
    return router
