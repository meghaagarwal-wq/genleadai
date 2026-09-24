"""Iter174 — Demo recording upload + share.

`POST /api/demo-recording/upload` — accepts a WebM/MP4 blob from the
browser's MediaRecorder capture of the /aria-demo walkthrough. Stores it
in Emergent Object Storage. Returns a public share URL the presenter can
send in one click.

`POST /api/demo-recording/send` — takes { recording_id, to_email, brand,
message } and sends a "Here's your ARIA in action" email via Resend
containing the share URL. Never blocks the UI: returns immediately with
`queued` even if email delivery is deferred.

Storage limits: 200 MB per upload (a 15-minute session recorded at low
bit-rate lands well under this).
"""
from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

import requests
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, EmailStr

from deps import db

router = APIRouter(prefix="/api/demo-recording", tags=["demo-recording"])
_col = db["demo_recordings"]

MAX_BYTES = 200 * 1024 * 1024   # 200 MB
ALLOWED_MIME = {
    "video/webm", "video/webm;codecs=vp8,opus", "video/webm;codecs=vp9,opus",
    "video/mp4", "audio/webm", "application/octet-stream",
}

# ── Emergent Object Storage client (shared style with aria_resources) ──
STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL  = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME     = "aria-lms"
_STORAGE_PREFIX = f"{APP_NAME}/demo-recordings"

_storage_key: Optional[str] = None

def _init_storage() -> str:
    global _storage_key
    if _storage_key:
        return _storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    return _storage_key


def _put(rec_id: str, data: bytes, content_type: str) -> None:
    key = _init_storage()
    r = requests.put(
        f"{STORAGE_URL}/objects/{_STORAGE_PREFIX}/{rec_id}",
        headers={"X-Storage-Key": key, "Content-Type": content_type or "application/octet-stream"},
        data=data, timeout=180,
    )
    r.raise_for_status()


def _get(rec_id: str) -> tuple[bytes, str]:
    key = _init_storage()
    r = requests.get(
        f"{STORAGE_URL}/objects/{_STORAGE_PREFIX}/{rec_id}",
        headers={"X-Storage-Key": key}, timeout=60,
    )
    r.raise_for_status()
    return r.content, r.headers.get("Content-Type", "video/webm")


def _public_backend() -> str:
    """Best-effort public origin so we can construct share links.

    In the emergent preview/prod pod, PUBLIC_URL / EXTERNAL_URL is set by
    the platform. In dev we fall back to REACT_APP_BACKEND_URL. This is
    read-only in-request so the URL always matches the current caller.
    """
    for k in ("PUBLIC_URL", "EXTERNAL_URL", "REACT_APP_BACKEND_URL"):
        v = os.environ.get(k)
        if v and v.startswith("http"):
            return v.rstrip("/")
    return ""


# ─── upload ────────────────────────────────────────────────────────
@router.post("/upload")
async def upload_recording(
    file: UploadFile = File(...),
    brand: str = Form(""),
    duration_sec: int = Form(0),
):
    content = await file.read()
    if not content:
        raise HTTPException(400, "Empty recording.")
    if len(content) > MAX_BYTES:
        raise HTTPException(413, f"Recording too large (max {MAX_BYTES // (1024*1024)} MB).")
    ct = (file.content_type or "").lower()
    if ct and not any(ct.startswith(a.split(";")[0]) for a in ALLOWED_MIME):
        raise HTTPException(415, f"Unsupported media type: {file.content_type}")

    ext = ".webm" if "webm" in ct or (file.filename or "").endswith(".webm") else ".mp4"
    rec_id = f"{uuid.uuid4().hex}{ext}"
    try:
        _put(rec_id, content, ct or "video/webm")
    except Exception as e:
        raise HTTPException(502, f"Storage upload failed: {e}")

    doc = {
        "_id":          rec_id,
        "brand":        (brand or "").strip()[:120],
        "duration_sec": int(duration_sec or 0),
        "size_bytes":   len(content),
        "content_type": ct or "video/webm",
        "created_at":   datetime.now(timezone.utc).isoformat(),
    }
    try:
        _col.insert_one(doc)
    except Exception:
        pass

    share_url = f"{_public_backend()}/api/demo-recording/{rec_id}"
    return {
        "ok":           True,
        "recording_id": rec_id,
        "share_url":    share_url,
        "size_bytes":   len(content),
    }


@router.get("/{rec_id}")
def serve_recording(rec_id: str):
    from fastapi.responses import Response
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", rec_id):
        raise HTTPException(404, "Not found")
    try:
        data, ct = _get(rec_id)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            raise HTTPException(404, "Not found")
        raise HTTPException(502, f"Storage read failed: {e}")
    return Response(content=data, media_type=ct, headers={"Content-Disposition": f'inline; filename="{rec_id}"'})


# ─── email share ───────────────────────────────────────────────────
class SendReq(BaseModel):
    recording_id: str
    to_email:     EmailStr
    brand:        Optional[str] = None
    message:      Optional[str] = None


@router.post("/send")
def send_recording(req: SendReq):
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", req.recording_id):
        raise HTTPException(400, "Bad recording id.")
    share_url = f"{_public_backend()}/api/demo-recording/{req.recording_id}"
    brand = (req.brand or "your team").strip()[:80]
    note  = (req.message or "").strip()[:600]

    subject = f"Here's your ARIA walkthrough — {brand}"
    html = f"""
<div style="font-family: -apple-system, 'Plus Jakarta Sans', sans-serif; color:#17181C; line-height:1.55;">
  <p>Hi,</p>
  <p>Thanks for making time — a quick recap of what ARIA looked like for <strong>{brand}</strong>:</p>
  <p><a href="{share_url}" style="display:inline-block; background:#7C35DC; color:#fff; padding:12px 20px; border-radius:10px; text-decoration:none; font-weight:600;">▶ Watch the walkthrough</a></p>
  {f'<p style="border-left:3px solid #A46FE8; padding:8px 12px; color:#4a4a55;">{note}</p>' if note else ''}
  <p>You can share this with your team — no login needed. Reply here with any questions.</p>
  <p style="color:#8B849E; font-size:12px; margin-top:32px;">Sent by ARIA · aria.emergentagent.com</p>
</div>
""".strip()

    # Send via Resend if configured, else queue-only (return ok anyway).
    resend_key = os.environ.get("RESEND_API_KEY")
    delivered = False
    if resend_key:
        try:
            import resend  # noqa
            resend.api_key = resend_key
            resend.Emails.send({
                "from":    os.environ.get("RESEND_FROM", "ARIA Demo <demo@aria.emergentagent.com>"),
                "to":      [req.to_email],
                "subject": subject,
                "html":    html,
            })
            delivered = True
        except Exception:
            delivered = False

    try:
        _col.update_one(
            {"_id": req.recording_id},
            {"$push": {"shared_with": {
                "email": req.to_email, "at": datetime.now(timezone.utc).isoformat(), "delivered": delivered,
            }}},
        )
    except Exception:
        pass

    return {"ok": True, "delivered": delivered, "share_url": share_url}
