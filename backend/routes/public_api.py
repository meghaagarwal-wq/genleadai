"""Public lead-capture API + embeddable web form.

Extracted from server.py during iter125 refactor.

Endpoints:
- POST /api/v1/leads             — Public (X-API-Key) lead create.
- POST /api/form/submit          — Public web-form submission (no auth).
- GET  /api/form/embed-code      — Authed; returns HTML snippet to paste.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from deps import (
    db,
    leads_collection,
    activities_collection,
    campaigns_collection,
    get_current_user,
)

router = APIRouter()

API_KEYS_COLLECTION = db["api_keys"]


def verify_api_key(x_api_key: str = Header(None)):
    """Verify API key for public endpoints."""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key header required")
    key_doc = API_KEYS_COLLECTION.find_one({"key": x_api_key, "is_active": True})
    if not key_doc:
        raise HTTPException(status_code=401, detail="Invalid API key")
    API_KEYS_COLLECTION.update_one(
        {"key": x_api_key},
        {"$inc": {"usage_count": 1}, "$set": {"last_used_at": datetime.now(timezone.utc).isoformat()}},
    )
    return key_doc


class PublicLeadCreate(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    lead_type: str = "B2C"
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    industry: Optional[str] = None
    source_channel: str = "other"
    campaign_id: Optional[str] = None
    notes: Optional[str] = None
    tags: List[str] = []
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    custom_fields: Dict[str, Any] = {}


@router.post("/api/v1/leads")
async def public_create_lead(lead: PublicLeadCreate, api_key_doc: dict = Depends(verify_api_key)):
    """Public API endpoint for external integrations (Zapier, Make, ad platforms)."""
    existing = leads_collection.find_one({"email": lead.email}, {"_id": 1})
    if existing:
        return {"status": "duplicate", "message": f"Lead with email {lead.email} already exists", "lead_id": str(existing["_id"])}

    lead_doc = lead.dict()
    lead_doc["created_at"] = datetime.now(timezone.utc).isoformat()
    lead_doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    lead_doc["created_by"] = f"api:{api_key_doc.get('name', 'external')}"
    lead_doc["icp_score"] = 0
    lead_doc["icp_tier"] = "cold"
    lead_doc["assigned_to"] = None
    lead_doc["status"] = "new"
    lead_doc["last_contacted_at"] = None
    lead_doc["next_followup_at"] = None

    if lead.utm_campaign:
        campaign = campaigns_collection.find_one({"utm_campaign": lead.utm_campaign})
        if campaign:
            lead_doc["campaign_id"] = str(campaign["_id"])

    result = leads_collection.insert_one(lead_doc)
    lead_id = str(result.inserted_id)

    activities_collection.insert_one({
        "lead_id": lead_id,
        "user_id": "api",
        "activity_type": "note_added",
        "subject": f"Lead created via API ({lead.source_channel})",
        "body": f"UTM: {lead.utm_source}/{lead.utm_medium}/{lead.utm_campaign}" if lead.utm_source else None,
        "outcome": None, "duration_minutes": None,
        "metadata": {"source": "public_api", "utm_source": lead.utm_source, "utm_medium": lead.utm_medium, "utm_campaign": lead.utm_campaign},
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    return {"status": "created", "lead_id": lead_id, "message": "Lead created successfully"}


class WebFormLead(BaseModel):
    first_name: str
    last_name: str = ""
    email: str
    phone: Optional[str] = None
    company_name: Optional[str] = None
    message: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None


@router.post("/api/form/submit")
async def web_form_submit(lead: WebFormLead):
    """Public endpoint for embeddable web form. No auth required."""
    if not lead.email or "@" not in lead.email:
        raise HTTPException(status_code=400, detail="Valid email required")

    existing = leads_collection.find_one({"email": lead.email}, {"_id": 1})
    if existing:
        return {"status": "success", "message": "Thank you! We'll be in touch soon."}

    lead_doc = {
        "first_name": lead.first_name,
        "last_name": lead.last_name or "",
        "email": lead.email,
        "phone": lead.phone,
        "lead_type": "B2B" if lead.company_name else "B2C",
        "company_name": lead.company_name,
        "job_title": None,
        "industry": None,
        "revenue_range": None,
        "city": None, "state": None, "country": None,
        "source_channel": "website_form",
        "campaign_id": None,
        "status": "new",
        "icp_score": 0,
        "icp_tier": "cold",
        "assigned_to": None,
        "notes": lead.message,
        "tags": ["website-form"],
        "custom_fields": {},
        "last_contacted_at": None,
        "next_followup_at": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "created_by": "web_form",
    }

    if lead.utm_campaign:
        campaign = campaigns_collection.find_one({"utm_campaign": lead.utm_campaign})
        if campaign:
            lead_doc["campaign_id"] = str(campaign["_id"])

    result = leads_collection.insert_one(lead_doc)
    lead_id = str(result.inserted_id)

    activities_collection.insert_one({
        "lead_id": lead_id, "user_id": "web_form",
        "activity_type": "note_added",
        "subject": "Lead submitted via website form",
        "body": lead.message[:200] if lead.message else None,
        "outcome": None, "duration_minutes": None,
        "metadata": {"source": "web_form", "utm_source": lead.utm_source, "utm_medium": lead.utm_medium, "utm_campaign": lead.utm_campaign},
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    return {"status": "success", "message": "Thank you! We'll be in touch soon."}


@router.get("/api/form/embed-code")
async def get_embed_code(current_user: dict = Depends(get_current_user)):
    """Generate embeddable HTML form snippet."""
    embed_code = """<!-- GenLeadAI Lead Capture Form -->
<div id="genleadai-form" style="max-width:480px;margin:0 auto;font-family:'Plus Jakarta Sans',sans-serif;">
  <form id="glai-form" style="background:#fff;border:1px solid #E8E0F5;border-radius:16px;padding:32px;box-shadow:0 1px 3px rgba(124,53,220,0.08),0 4px 16px rgba(124,53,220,0.04);">
    <div style="text-align:center;margin-bottom:24px;">
      <div style="width:40px;height:40px;background:linear-gradient(135deg,#C044E0,#5B28D4);border-radius:10px;display:inline-flex;align-items:center;justify-content:center;margin-bottom:12px;">
        <span style="color:white;font-weight:800;font-size:16px;">G</span>
      </div>
      <h3 style="margin:0;color:#1A0A2E;font-size:20px;font-weight:700;">Let's Talk Growth</h3>
      <p style="margin:4px 0 0;color:#5A4A7A;font-size:14px;">Fill in your details and we'll reach out</p>
    </div>
    <div style="margin-bottom:16px;">
      <input type="text" name="first_name" placeholder="Your Name *" required style="width:100%;padding:12px 16px;border:1px solid #E8E0F5;border-radius:10px;font-size:14px;color:#1A0A2E;box-sizing:border-box;outline:none;" onfocus="this.style.borderColor='#7C35DC';this.style.boxShadow='0 0 0 3px rgba(124,53,220,0.12)'" onblur="this.style.borderColor='#E8E0F5';this.style.boxShadow='none'" />
    </div>
    <div style="margin-bottom:16px;">
      <input type="email" name="email" placeholder="Email Address *" required style="width:100%;padding:12px 16px;border:1px solid #E8E0F5;border-radius:10px;font-size:14px;color:#1A0A2E;box-sizing:border-box;outline:none;" onfocus="this.style.borderColor='#7C35DC';this.style.boxShadow='0 0 0 3px rgba(124,53,220,0.12)'" onblur="this.style.borderColor='#E8E0F5';this.style.boxShadow='none'" />
    </div>
    <div style="margin-bottom:16px;">
      <input type="tel" name="phone" placeholder="Phone (optional)" style="width:100%;padding:12px 16px;border:1px solid #E8E0F5;border-radius:10px;font-size:14px;color:#1A0A2E;box-sizing:border-box;outline:none;" onfocus="this.style.borderColor='#7C35DC';this.style.boxShadow='0 0 0 3px rgba(124,53,220,0.12)'" onblur="this.style.borderColor='#E8E0F5';this.style.boxShadow='none'" />
    </div>
    <div style="margin-bottom:16px;">
      <input type="text" name="company_name" placeholder="Company (optional)" style="width:100%;padding:12px 16px;border:1px solid #E8E0F5;border-radius:10px;font-size:14px;color:#1A0A2E;box-sizing:border-box;outline:none;" onfocus="this.style.borderColor='#7C35DC';this.style.boxShadow='0 0 0 3px rgba(124,53,220,0.12)'" onblur="this.style.borderColor='#E8E0F5';this.style.boxShadow='none'" />
    </div>
    <div style="margin-bottom:20px;">
      <textarea name="message" placeholder="What are you looking for?" rows="3" style="width:100%;padding:12px 16px;border:1px solid #E8E0F5;border-radius:10px;font-size:14px;color:#1A0A2E;box-sizing:border-box;resize:none;outline:none;" onfocus="this.style.borderColor='#7C35DC';this.style.boxShadow='0 0 0 3px rgba(124,53,220,0.12)'" onblur="this.style.borderColor='#E8E0F5';this.style.boxShadow='none'"></textarea>
    </div>
    <button type="submit" style="width:100%;padding:14px;background:linear-gradient(135deg,#C044E0,#7C35DC,#5B28D4);color:white;border:none;border-radius:10px;font-size:15px;font-weight:700;cursor:pointer;font-family:'Plus Jakarta Sans',sans-serif;">Get in Touch</button>
    <div id="glai-msg" style="text-align:center;margin-top:12px;font-size:13px;display:none;"></div>
  </form>
</div>
<script>
(function(){
  var BACKEND='{BACKEND_URL}';
  var form=document.getElementById('glai-form');
  var msg=document.getElementById('glai-msg');
  var params=new URLSearchParams(window.location.search);
  form.addEventListener('submit',function(e){
    e.preventDefault();
    var btn=form.querySelector('button');
    btn.textContent='Sending...';btn.disabled=true;
    var data={
      first_name:form.first_name.value,
      email:form.email.value,
      phone:form.phone.value||null,
      company_name:form.company_name.value||null,
      message:form.message.value||null,
      utm_source:params.get('utm_source')||null,
      utm_medium:params.get('utm_medium')||null,
      utm_campaign:params.get('utm_campaign')||null
    };
    fetch(BACKEND+'/api/form/submit',{
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)
    }).then(function(r){return r.json()}).then(function(d){
      msg.style.display='block';msg.style.color='#16A34A';msg.textContent=d.message||'Thank you!';
      form.reset();btn.textContent='Sent!';
      setTimeout(function(){btn.textContent='Get in Touch';btn.disabled=false;},3000);
    }).catch(function(){
      msg.style.display='block';msg.style.color='#DC2626';msg.textContent='Something went wrong. Please try again.';
      btn.textContent='Get in Touch';btn.disabled=false;
    });
  });
})();
</script>"""

    return {"embed_code": embed_code, "instructions": "Replace {BACKEND_URL} with your deployed backend URL (e.g., https://app.genleadai.com). Paste the HTML anywhere on your website."}
