"""Iter176 — Demo analytics.

Two public endpoints:
  POST /api/demo-analytics/view    — logged when the /aria-demo page loads
  GET  /api/demo-analytics/recent  — read the last N views (for the founder)

Deliberately minimal. No PII stored beyond what the prospect gives us via
the demo URL itself (their `?company=` domain). IP is hashed (SHA-256 with
a per-day salt so it can't be reversed but can dedupe within a day).
Referrer is truncated to origin + first path segment.
"""
from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from deps import db

router = APIRouter(prefix="/api/demo-analytics", tags=["demo-analytics"])
_col = db["demo_views"]

_DAY_SALT_SECRET = os.environ.get("ANALYTICS_DAY_SALT", "aria-demo-2026")


def _day_hash(ip: str) -> str:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return hashlib.sha256(f"{_DAY_SALT_SECRET}|{day}|{ip}".encode()).hexdigest()[:16]


def _short_ref(ref: Optional[str]) -> Optional[str]:
    if not ref or not isinstance(ref, str) or len(ref) > 400:
        return None
    try:
        p = urlparse(ref)
        if not p.netloc:
            return None
        seg = (p.path.split("/", 2) or [""])[1] if p.path else ""
        return f"{p.scheme}://{p.netloc}{('/' + seg) if seg else ''}"
    except Exception:
        return None


class ViewReq(BaseModel):
    company:  Optional[str] = None
    mode:     Optional[str] = None
    scenario: Optional[str] = None
    referrer: Optional[str] = None
    path:     Optional[str] = None
    # Where in the funnel — "gateway" if the visitor arrived from AriaGateway,
    # "direct" if they landed on /aria-demo without going through the gateway.
    source:   Optional[str] = None


@router.post("/view")
async def log_view(req: ViewReq, request: Request):
    ip = (request.headers.get("x-forwarded-for", "").split(",")[0].strip()
          or (request.client.host if request.client else "0.0.0.0"))
    ua = (request.headers.get("user-agent") or "")[:220]

    doc = {
        "at":       datetime.now(timezone.utc).isoformat(),
        "company":  (req.company  or None) and req.company.strip().lower()[:120],
        "mode":     req.mode if req.mode in {"b2c", "b2b", "hybrid"} else None,
        "scenario": (req.scenario or None) and req.scenario.strip()[:32],
        "path":     (req.path     or None) and req.path[:200],
        "referrer": _short_ref(req.referrer),
        "source":   req.source if req.source in {"gateway", "direct", "shared", "embed"} else "direct",
        "ip_hash":  _day_hash(ip),
        "ua":       ua,
    }
    try:
        _col.insert_one(doc)
    except Exception:
        pass
    return {"ok": True}


@router.get("/recent")
def recent_views(limit: int = Query(50, ge=1, le=500)):
    """Return the last `limit` views (newest first). No auth — public.
    In production you'd protect this with an admin token; the demo
    workspace keeps it open so the founder can eyeball it without login.
    """
    try:
        rows = list(_col.find({}, {"_id": 0}).sort("at", -1).limit(limit))
    except Exception:
        rows = []
    # de-dup on ip_hash + company within a session for cleaner reads
    seen: set = set()
    out = []
    for r in rows:
        k = (r.get("ip_hash"), r.get("company"), r.get("mode"))
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return {"count": len(out), "views": out}
