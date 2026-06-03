"""Audit log + CSV export endpoints. Extracted from server.py during iter125 refactor."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from pymongo import DESCENDING

from deps import (
    db,
    leads_collection,
    activities_collection,
    get_current_user,
)

router = APIRouter()

audit_log_collection = db["audit_log"]


def log_audit(user_email: str, action: str, resource_type: str, resource_id: str = None, details: str = None):
    """Log an audit event."""
    audit_log_collection.insert_one({
        "user_email": user_email,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "details": details,
        "ip_address": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@router.get("/api/audit-log")
async def get_audit_log(skip: int = 0, limit: int = 50, current_user: dict = Depends(get_current_user)):
    """Get audit log entries."""
    if current_user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Admin or manager access required")
    entries = list(audit_log_collection.find({}, {"_id": 0}).sort("timestamp", DESCENDING).skip(skip).limit(limit))
    total = audit_log_collection.count_documents({})
    return {"entries": entries, "total": total}


@router.get("/api/export/leads")
async def export_leads_csv(current_user: dict = Depends(get_current_user)):
    """Export all leads (legacy + pt_leads) as CSV.

    iter146 — Uses the unified `iter_tenant_leads` helper so Pietential
    workspaces get their pt_leads in the CSV too.
    """
    from routes.lead_query import iter_tenant_leads
    tenant_id = current_user.get("tenant_id")
    leads = list(iter_tenant_leads(tenant_id, limit=5000)) if tenant_id else []
    output = io.StringIO()
    if leads:
        fields = ["first_name", "last_name", "email", "phone", "company_name", "job_title",
                  "source_channel", "status", "stage_native", "icp_score", "icp_tier", "score",
                  "created_at", "_origin"]
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for lead in leads:
            writer.writerow(lead)
    content = output.getvalue()
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=genleadai_leads_{datetime.now().strftime('%Y%m%d')}.csv"}
    )


@router.get("/api/export/activities/{lead_id}")
async def export_lead_activities(lead_id: str, current_user: dict = Depends(get_current_user)):
    """Export activities for a lead as CSV."""
    activities = list(activities_collection.find({"lead_id": lead_id}, {"_id": 0}).sort("created_at", DESCENDING))
    output = io.StringIO()
    if activities:
        fields = ["created_at", "activity_type", "subject", "body", "outcome", "user_id"]
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for act in activities:
            writer.writerow(act)
    content = output.getvalue()
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=lead_{lead_id}_activities.csv"}
    )


@router.get("/api/export/report")
async def export_analytics_report(current_user: dict = Depends(get_current_user)):
    """Export analytics report as CSV.

    iter146 — Uses `count_tenant_leads` so Pietential numbers include
    pt_leads (otherwise B2B founders downloading their analytics CSV see
    0 for every status bucket).
    """
    from routes.lead_query import count_tenant_leads
    tenant_id = current_user.get("tenant_id")
    total = count_tenant_leads(tenant_id) if tenant_id else 0
    status_counts = {}
    for s in ["new", "contacted", "qualified", "proposal_sent", "negotiation", "won", "lost"]:
        status_counts[s] = count_tenant_leads(tenant_id, status_in={s}) if tenant_id else 0
    channel_counts = {}
    for c in ["whatsapp", "email", "linkedin", "instagram", "facebook", "website_form", "cold_call", "referral", "webinar", "organic_search", "paid_ads"]:
        # source_channel filter is legacy-only — pt_leads doesn't carry it.
        channel_counts[c] = leads_collection.count_documents({"tenant_id": tenant_id, "source_channel": c}) if tenant_id else 0

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["GenLeadAI Analytics Report", datetime.now().strftime('%Y-%m-%d')])
    writer.writerow([])
    writer.writerow(["Metric", "Value"])
    writer.writerow(["Total Leads", total])
    writer.writerow(["B2B", leads_collection.count_documents({"tenant_id": tenant_id, "lead_type": "B2B"}) if tenant_id else 0])
    writer.writerow(["B2C", leads_collection.count_documents({"tenant_id": tenant_id, "lead_type": "B2C"}) if tenant_id else 0])
    writer.writerow([])
    writer.writerow(["Status", "Count"])
    for s, c in status_counts.items():
        writer.writerow([s, c])
    writer.writerow([])
    writer.writerow(["Channel", "Count"])
    for ch, c in channel_counts.items():
        if c > 0:
            writer.writerow([ch, c])

    content = output.getvalue()
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=genleadai_report_{datetime.now().strftime('%Y%m%d')}.csv"}
    )
