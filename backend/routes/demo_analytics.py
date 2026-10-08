"""Iter177 — Demo analytics.

Session-aware event stream for the public /aria-demo:
  POST /api/demo-analytics/view        — first-hit (per sessionId)
  POST /api/demo-analytics/heartbeat   — every 30s while on page → dwell
  POST /api/demo-analytics/identify    — prospect gave us their name/email
  POST /api/demo-analytics/event       — booking click, approve, etc.
  GET  /api/demo-analytics/pulse       — founder-facing feed (recent sessions)
  GET  /api/demo-analytics/recent      — legacy raw-row list (unchanged)

Session doc shape (`demo_sessions` collection) — one per prospect visit:
  _id          sessionId (uuid4 from browser, persisted in localStorage)
  started_at   ISO
  last_seen_at ISO
  dwell_sec    int
  company      Optional[str]       — last known enrichment company
  mode         Optional[str]
  scenario     Optional[str]
  source       str
  identify     { name, email, at } — once the prospect prefills
  events       list of { kind, at, data }
  ip_hash      day-salted SHA256
  ua           str

Legacy `demo_views` collection is untouched for backwards-compat.
"""
from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr, Field

from deps import db

router = APIRouter(prefix="/api/demo-analytics", tags=["demo-analytics"])
_col      = db["demo_views"]
_sessions = db["demo_sessions"]

_DAY_SALT_SECRET = os.environ.get("ANALYTICS_DAY_SALT", "aria-demo-2026")
_WARM_SECONDS    = 180  # 3 min


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


def _client_ip(request: Request) -> str:
    return ((request.headers.get("x-forwarded-for", "").split(",")[0].strip())
            or (request.client.host if request.client else "0.0.0.0"))


_SID_RE = re.compile(r"^[a-f0-9-]{8,64}$")


def _valid_sid(sid: Optional[str]) -> Optional[str]:
    if not sid: return None
    sid = sid.lower()
    return sid if _SID_RE.fullmatch(sid) else None


# ─── models ───────────────────────────────────────────────────────
class ViewReq(BaseModel):
    session_id: Optional[str] = None
    company:    Optional[str] = None
    mode:       Optional[str] = None
    scenario:   Optional[str] = None
    referrer:   Optional[str] = None
    path:       Optional[str] = None
    source:     Optional[str] = None


class HeartbeatReq(BaseModel):
    session_id: str
    company:    Optional[str] = None
    mode:       Optional[str] = None
    scenario:   Optional[str] = None
    tab:        Optional[str] = None


class IdentifyReq(BaseModel):
    session_id: str
    name:       Optional[str] = Field(None, max_length=120)
    email:      Optional[EmailStr] = None


class EventReq(BaseModel):
    session_id: str
    kind:       str = Field(..., max_length=40)   # e.g. 'book_clicked', 'approve', 'ask_aria'
    data:       Optional[dict] = None


# ─── /view ────────────────────────────────────────────────────────
@router.post("/view")
async def log_view(req: ViewReq, request: Request):
    ip = _client_ip(request)
    ua = (request.headers.get("user-agent") or "")[:220]
    now = datetime.now(timezone.utc).isoformat()
    sid = _valid_sid(req.session_id)

    doc = {
        "at":       now,
        "company":  (req.company  or None) and req.company.strip().lower()[:120],
        "mode":     req.mode if req.mode in {"b2c", "b2b", "hybrid"} else None,
        "scenario": (req.scenario or None) and req.scenario.strip()[:32],
        "path":     (req.path     or None) and req.path[:200],
        "referrer": _short_ref(req.referrer),
        "source":   req.source if req.source in {"gateway", "direct", "shared", "embed"} else "direct",
        "ip_hash":  _day_hash(ip),
        "ua":       ua,
        "session":  sid,
    }
    try:
        _col.insert_one(doc)
    except Exception:
        pass

    if sid:
        try:
            _sessions.update_one(
                {"_id": sid},
                {
                    "$setOnInsert": {
                        "_id":        sid,
                        "started_at": now,
                        "ip_hash":    _day_hash(ip),
                        "ua":         ua,
                        "source":     doc["source"],
                        "dwell_sec":  0,
                        "events":     [],
                    },
                    "$set": {
                        "last_seen_at": now,
                        "company":      doc["company"],
                        "mode":         doc["mode"],
                        "scenario":     doc["scenario"],
                    },
                },
                upsert=True,
            )
        except Exception:
            pass

    return {"ok": True, "session_id": sid}


# ─── /heartbeat ───────────────────────────────────────────────────
@router.post("/heartbeat")
async def heartbeat(req: HeartbeatReq):
    sid = _valid_sid(req.session_id)
    if not sid:
        raise HTTPException(400, "Bad session id.")
    now = datetime.now(timezone.utc)
    doc = _sessions.find_one({"_id": sid})
    if not doc:
        # Allow heartbeat to bootstrap a session if /view was dropped
        _sessions.update_one(
            {"_id": sid},
            {"$setOnInsert": {"_id": sid, "started_at": now.isoformat(), "dwell_sec": 0, "events": []}},
            upsert=True,
        )
        doc = _sessions.find_one({"_id": sid})

    try:
        prev = datetime.fromisoformat((doc or {}).get("last_seen_at", now.isoformat()).replace("Z", "+00:00"))
    except Exception:
        prev = now
    delta = max(0, min(90, int((now - prev).total_seconds())))  # cap per-tick at 90s to prevent inflation

    _sessions.update_one(
        {"_id": sid},
        {
            "$set": {
                "last_seen_at": now.isoformat(),
                "company":  (req.company  or (doc or {}).get("company")),
                "mode":     (req.mode     or (doc or {}).get("mode")),
                "scenario": (req.scenario or (doc or {}).get("scenario")),
                "tab":      (req.tab      or (doc or {}).get("tab")),
            },
            "$inc": {"dwell_sec": delta},
        },
    )
    return {"ok": True, "dwell_sec_added": delta}


# ─── /identify ────────────────────────────────────────────────────
@router.post("/identify")
async def identify(req: IdentifyReq):
    sid = _valid_sid(req.session_id)
    if not sid:
        raise HTTPException(400, "Bad session id.")
    name = (req.name or "").strip()[:120] or None
    _sessions.update_one(
        {"_id": sid},
        {"$set": {"identify": {"name": name, "email": req.email, "at": datetime.now(timezone.utc).isoformat()}}},
        upsert=True,
    )
    return {"ok": True}


# ─── /event ───────────────────────────────────────────────────────
@router.post("/event")
async def event(req: EventReq):
    sid = _valid_sid(req.session_id)
    if not sid:
        raise HTTPException(400, "Bad session id.")
    kind = re.sub(r"[^a-z0-9_-]", "", req.kind.lower())[:40] or "unknown"
    now = datetime.now(timezone.utc).isoformat()
    _sessions.update_one(
        {"_id": sid},
        {"$push": {"events": {"kind": kind, "at": now, "data": req.data or {}}}},
        upsert=True,
    )
    return {"ok": True}


# ─── /pulse — founder-facing feed ────────────────────────────────
@router.get("/pulse")
def pulse(limit: int = Query(50, ge=1, le=500)):
    """Session digest for the founder dashboard. Newest first."""
    try:
        rows = list(_sessions.find({}, {"_id": 1, "started_at": 1, "last_seen_at": 1,
                                        "dwell_sec": 1, "company": 1, "mode": 1,
                                        "scenario": 1, "source": 1, "identify": 1,
                                        "events": 1, "tab": 1})
                    .sort("last_seen_at", -1).limit(limit))
    except Exception:
        rows = []
    out = []
    for r in rows:
        events = r.get("events") or []
        has_book = any(e.get("kind") in {"book_clicked", "booked"} for e in events)
        dwell = int(r.get("dwell_sec") or 0)
        warm = (dwell >= _WARM_SECONDS) and not has_book
        out.append({
            "session_id":  r.get("_id"),
            "started_at":  r.get("started_at"),
            "last_seen_at":r.get("last_seen_at"),
            "dwell_sec":   dwell,
            "company":     r.get("company"),
            "mode":        r.get("mode"),
            "scenario":    r.get("scenario"),
            "source":      r.get("source"),
            "tab":         r.get("tab"),
            "identify":    r.get("identify"),
            "events":      events[-6:],   # last 6 events only
            "book_clicked":has_book,
            "warm":        warm,
        })
    totals = {
        "sessions":      len(out),
        "warm":          sum(1 for s in out if s["warm"]),
        "booked":        sum(1 for s in out if s["book_clicked"]),
        "identified":    sum(1 for s in out if s["identify"]),
    }
    return {"totals": totals, "sessions": out}


# ─── legacy /recent (unchanged shape; kept for any existing callers) ─
@router.get("/recent")
def recent_views(limit: int = Query(50, ge=1, le=500)):
    try:
        rows = list(_col.find({}, {"_id": 0}).sort("at", -1).limit(limit))
    except Exception:
        rows = []
    seen: set = set()
    out = []
    for r in rows:
        k = (r.get("ip_hash"), r.get("company"), r.get("mode"))
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return {"count": len(out), "views": out}

