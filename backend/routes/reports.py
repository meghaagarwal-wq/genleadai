"""Reports endpoints — funnel, KPIs, source performance, activity, PDF export."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional
from io import BytesIO

from fastapi import APIRouter, Depends, Response

from deps import db, get_current_user
from routes.tenants import get_active_tenant

router = APIRouter(prefix="/api/reports", tags=["reports"])

leads_col = db["leads"]
activities_col = db["activities"]
log_col = db["lead_touchpoint_log"]


def _range(period: str) -> tuple[datetime, datetime]:
    """Return (start, end) UTC datetimes for the given period key."""
    now = datetime.now(timezone.utc)
    if period == "last_month":
        start = (now.replace(day=1) - timedelta(days=1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "last_3_months":
        start = now - timedelta(days=90)
        end = now
    elif period == "custom":
        start = now - timedelta(days=30)
        end = now
    else:  # this_month default
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now
    return start, end


def _previous_range(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    delta = end - start
    return start - delta, start


def _change(now: int, prev: int) -> float:
    if prev == 0:
        return 100.0 if now > 0 else 0.0
    return round(((now - prev) / prev) * 100, 1)


@router.get("/summary")
async def summary(period: str = "this_month", tenant: dict = Depends(get_active_tenant)):
    tenant_id = tenant["id"]
    start, end = _range(period)
    pstart, pend = _previous_range(start, end)

    def kpis(s: datetime, e: datetime) -> dict:
        leads_handled = leads_col.count_documents({"tenant_id": tenant_id, "created_at": {"$gte": s.isoformat(), "$lt": e.isoformat()}})
        qualified = leads_col.count_documents({"tenant_id": tenant_id, "icp_score": {"$gte": 70}, "created_at": {"$gte": s.isoformat(), "$lt": e.isoformat()}})
        meetings = activities_col.count_documents({"tenant_id": tenant_id, "type": "meeting_scheduled", "created_at": {"$gte": s.isoformat(), "$lt": e.isoformat()}})
        won = leads_col.count_documents({"tenant_id": tenant_id, "status": "closed_won", "updated_at": {"$gte": s.isoformat(), "$lt": e.isoformat()}})
        return {"leads_handled": leads_handled, "qualified": qualified, "meetings": meetings, "won": won}

    now_k = kpis(start, end)
    prev_k = kpis(pstart, pend)

    return {
        "period": period,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "kpis": {
            "leads_handled": {"value": now_k["leads_handled"], "change": _change(now_k["leads_handled"], prev_k["leads_handled"])},
            "qualified": {"value": now_k["qualified"], "change": _change(now_k["qualified"], prev_k["qualified"])},
            "meetings": {"value": now_k["meetings"], "change": _change(now_k["meetings"], prev_k["meetings"])},
            "won": {"value": now_k["won"], "change": _change(now_k["won"], prev_k["won"])},
        },
    }


@router.get("/funnel")
async def funnel(period: str = "this_month", tenant: dict = Depends(get_active_tenant)):
    tenant_id = tenant["id"]
    start, end = _range(period)
    base = {"tenant_id": tenant_id, "created_at": {"$gte": start.isoformat(), "$lt": end.isoformat()}}

    entered = leads_col.count_documents(base)
    contacted = leads_col.count_documents({**base, "status": {"$in": ["contacted", "qualified", "proposal_sent", "negotiating", "closed_won", "closed_lost"]}})
    replied = leads_col.count_documents({**base, "$or": [{"replied": True}, {"status": {"$in": ["qualified", "proposal_sent", "negotiating", "closed_won", "closed_lost"]}}]})
    qualified = leads_col.count_documents({**base, "$or": [{"icp_score": {"$gte": 70}}, {"status": {"$in": ["qualified", "proposal_sent", "negotiating", "closed_won"]}}]})
    meeting = activities_col.count_documents({"tenant_id": tenant_id, "type": "meeting_scheduled", "created_at": {"$gte": start.isoformat(), "$lt": end.isoformat()}})
    won = leads_col.count_documents({**base, "status": "closed_won"})

    stages = [
        {"stage": "Leads Entered", "value": entered},
        {"stage": "Contacted", "value": contacted},
        {"stage": "Replied", "value": replied},
        {"stage": "Qualified", "value": qualified},
        {"stage": "Meeting Booked", "value": meeting},
        {"stage": "Closed Won", "value": won},
    ]

    # Compute drop-off % between consecutive stages
    for i, st in enumerate(stages):
        if i == 0:
            st["drop_off"] = 0.0
        else:
            prev = stages[i - 1]["value"]
            st["drop_off"] = round(((prev - st["value"]) / prev) * 100, 1) if prev else 0.0

    return {"stages": stages}


@router.get("/activity")
async def activity(period: str = "this_month", tenant: dict = Depends(get_active_tenant)):
    tenant_id = tenant["id"]
    start, end = _range(period)

    # Per day conversation count for the last 30 days inside range
    days = []
    cur = (end - timedelta(days=29)).replace(hour=0, minute=0, second=0, microsecond=0)
    cur = max(cur, start)
    while cur < end:
        nxt = cur + timedelta(days=1)
        n = activities_col.count_documents({"tenant_id": tenant_id, "created_at": {"$gte": cur.isoformat(), "$lt": nxt.isoformat()}})
        days.append({"day": cur.strftime("%b %d"), "conversations": n})
        cur = nxt

    tp_sent = log_col.count_documents({"tenant_id": tenant_id, "status": "sent", "fired_at": {"$gte": start.isoformat(), "$lt": end.isoformat()}})
    tp_failed = log_col.count_documents({"tenant_id": tenant_id, "status": "failed", "fired_at": {"$gte": start.isoformat(), "$lt": end.isoformat()}})
    tp_skipped = log_col.count_documents({"tenant_id": tenant_id, "status": "skipped", "fired_at": {"$gte": start.isoformat(), "$lt": end.isoformat()}})

    return {
        "daily_conversations": days,
        "touchpoints": {"sent": tp_sent, "failed": tp_failed, "skipped": tp_skipped},
    }


@router.get("/sources")
async def sources(period: str = "this_month", tenant: dict = Depends(get_active_tenant)):
    tenant_id = tenant["id"]
    start, end = _range(period)
    base = {"tenant_id": tenant_id, "created_at": {"$gte": start.isoformat(), "$lt": end.isoformat()}}

    pipeline = [
        {"$match": base},
        {"$group": {
            "_id": {"$ifNull": ["$source_channel", "manual"]},
            "leads": {"$sum": 1},
            "qualified": {"$sum": {"$cond": [{"$gte": ["$icp_score", 70]}, 1, 0]}},
            "won": {"$sum": {"$cond": [{"$eq": ["$status", "closed_won"]}, 1, 0]}},
        }},
        {"$sort": {"leads": -1}},
    ]
    rows = []
    for r in leads_col.aggregate(pipeline):
        leads = r["leads"]
        qualified = r["qualified"]
        rows.append({
            "source": r["_id"] or "manual",
            "leads": leads,
            "qualified": qualified,
            "conversion_pct": round((qualified / leads) * 100, 1) if leads else 0,
            "won": r["won"],
        })

    return {"sources": rows}


@router.get("/export")
async def export_pdf(period: str = "this_month", tenant: dict = Depends(get_active_tenant), current_user: dict = Depends(get_current_user)):
    """Generate a branded PDF report (reportlab)."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    except Exception:
        return Response(content=b"reportlab not installed", status_code=500, media_type="text/plain")

    summary_data = await summary(period, tenant)
    funnel_data = await funnel(period, tenant)
    sources_data = await sources(period, tenant)

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('title', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=22, textColor=colors.HexColor('#1A0A2E'), spaceAfter=6)
    h2 = ParagraphStyle('h2', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=13, textColor=colors.HexColor('#7C35DC'), spaceAfter=8)
    muted = ParagraphStyle('muted', parent=styles['Normal'], fontName='Helvetica', fontSize=9, textColor=colors.HexColor('#5A4A7A'))

    story = []
    story.append(Paragraph("GenLeadAI · Aria Report", title_style))
    story.append(Paragraph(f"Workspace: <b>{tenant.get('name', '—')}</b> · Period: {period.replace('_', ' ').title()}", muted))
    story.append(Paragraph(f"Generated: {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M UTC')}", muted))
    story.append(Spacer(1, 14))

    story.append(Paragraph("KPI Summary", h2))
    kpi_rows = [["Metric", "Value", "Change"]]
    for label, key in [("Leads Handled", "leads_handled"), ("Qualified", "qualified"), ("Meetings Booked", "meetings"), ("Closed Won", "won")]:
        v = summary_data["kpis"][key]
        kpi_rows.append([label, str(v["value"]), f"{v['change']:+.1f}%"])
    kpi_tbl = Table(kpi_rows, colWidths=[6 * cm, 4 * cm, 4 * cm])
    kpi_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F4F0FF')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#7C35DC')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E8E0F5')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(kpi_tbl)
    story.append(Spacer(1, 18))

    story.append(Paragraph("Pipeline Funnel", h2))
    funnel_rows = [["Stage", "Leads", "Drop-off"]]
    for st in funnel_data["stages"]:
        funnel_rows.append([st["stage"], str(st["value"]), f"{st['drop_off']:.1f}%"])
    f_tbl = Table(funnel_rows, colWidths=[7 * cm, 4 * cm, 4 * cm])
    f_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F4F0FF')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#7C35DC')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E8E0F5')),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(f_tbl)
    story.append(Spacer(1, 18))

    if sources_data["sources"]:
        story.append(Paragraph("Lead Source Performance", h2))
        s_rows = [["Source", "Leads", "Qualified", "Conv %", "Won"]]
        for r in sources_data["sources"][:10]:
            s_rows.append([str(r["source"])[:24], str(r["leads"]), str(r["qualified"]), f"{r['conversion_pct']:.1f}%", str(r["won"])])
        s_tbl = Table(s_rows, colWidths=[5 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm])
        s_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F4F0FF')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#7C35DC')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E8E0F5')),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(s_tbl)
        story.append(Spacer(1, 18))

    story.append(Spacer(1, 24))
    story.append(Paragraph("<i>Powered by Aria · GenLeadAI · genleadai.com</i>", muted))

    doc.build(story)
    buf.seek(0)
    fname = f"aria-report-{tenant.get('id', 'workspace')}-{period}.pdf"
    return Response(content=buf.read(), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{fname}"'})
