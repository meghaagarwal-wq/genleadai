"""Pietential workspace-scoped email sending helper.

Iter85 — wraps Resend so all outbound mail for a workspace uses:
  • The workspace's encrypted Resend API key (falls back to platform default)
  • The workspace's from_address + from_name
  • The workspace's HTML signature (auto-appended to every send)
  • Optional file attachments resolved from UPLOADS_DIR

Other endpoints (test-send, Aria-drafted reply, lead-magnet send) should
call `send_workspace_email()` instead of `resend.Emails.send()` directly so
we have a single chokepoint for sender identity + signature + attachments.
"""
from __future__ import annotations

import base64
import os
import asyncio
from typing import Any, Dict, List, Optional

import resend
from fastapi import HTTPException

from deps import db
from security.encryption import decrypt as _dec

integrations_col = db["pt_integrations"]


# ────────────────────────────────────────────────────────────────────────
# Config resolution
# ────────────────────────────────────────────────────────────────────────
def get_workspace_email_config() -> Dict[str, Any]:
    """Return the active sender config (decrypted) for the Pietential workspace.

    Falls back gracefully:
      1. Workspace-saved Resend key + from_address
      2. Platform RESEND_API_KEY + SENDER_EMAIL env vars
      3. Resend sandbox sender (onboarding@resend.dev)
    """
    integ = integrations_col.find_one({"name": "email"}) or {}
    workspace_key = _dec(integ.get("api_key") or "") if integ.get("api_key") else ""
    return {
        "from_name": (integ.get("from_name") or "").strip(),
        "from_address": integ.get("from_address") or os.environ.get("SENDER_EMAIL") or "onboarding@resend.dev",
        "resend_api_key": workspace_key or os.environ.get("RESEND_API_KEY") or "",
        "signature_html": (integ.get("signature_html") or "").strip(),
        "using_global_fallback": not bool(integ.get("api_key")),
        "using_workspace_signature": bool(integ.get("signature_html")),
    }


# ────────────────────────────────────────────────────────────────────────
# Attachment loading
# ────────────────────────────────────────────────────────────────────────
def _resolve_attachment(file_id: str, uploads_dir: str) -> Optional[Dict[str, Any]]:
    """Read a file from UPLOADS_DIR and return Resend-shaped attachment dict.

    Resend expects: {filename: str, content: base64-encoded str}
    """
    if not file_id:
        return None
    safe_path = os.path.join(uploads_dir, file_id)
    real = os.path.realpath(safe_path)
    if not real.startswith(os.path.realpath(uploads_dir) + os.sep) and real != os.path.realpath(uploads_dir):
        return None  # path-traversal guard
    if not os.path.isfile(real):
        return None
    with open(real, "rb") as f:
        raw = f.read()
    return {
        "filename": os.path.basename(real),
        "content": base64.b64encode(raw).decode("ascii"),
    }


# ────────────────────────────────────────────────────────────────────────
# Signature rendering
# ────────────────────────────────────────────────────────────────────────
def _append_signature(html_body: str, signature_html: str) -> str:
    if not signature_html:
        return html_body
    sep = "<br><br><div style='margin-top:24px;padding-top:16px;border-top:1px solid #E2E8F0;color:#475569;font-size:13px;line-height:1.5;'>"
    return f"{html_body}{sep}{signature_html}</div>"


# ────────────────────────────────────────────────────────────────────────
# Public send
# ────────────────────────────────────────────────────────────────────────
async def send_workspace_email(
    *,
    to: str,
    subject: str,
    html_body: str,
    attachment_file_ids: Optional[List[str]] = None,
    uploads_dir: str,
    reply_to: Optional[str] = None,
    append_signature: bool = True,
) -> Dict[str, Any]:
    """Send a Resend email using the workspace's sender identity.

    Returns: {ok, provider_id, from, to, attachments_count}
    Raises HTTPException(400) with a friendly message on common failures.
    """
    cfg = get_workspace_email_config()
    if not cfg["resend_api_key"]:
        raise HTTPException(
            status_code=400,
            detail=(
                "No Resend API key available. Paste one in Settings → Email Sender, "
                "or ask the platform admin to set RESEND_API_KEY."
            ),
        )

    # Build from field
    from_addr = cfg["from_address"]
    from_name = cfg["from_name"] or "ARIA"
    from_field = f"{from_name} <{from_addr}>"

    # Append signature
    body = _append_signature(html_body, cfg["signature_html"]) if append_signature else html_body

    # Resolve attachments
    attachments: List[Dict[str, Any]] = []
    for fid in (attachment_file_ids or []):
        att = _resolve_attachment(fid, uploads_dir)
        if att:
            attachments.append(att)

    params: Dict[str, Any] = {
        "from": from_field,
        "to": [to],
        "subject": subject,
        "html": body,
    }
    if reply_to:
        params["reply_to"] = [reply_to]
    if attachments:
        params["attachments"] = attachments

    # Use the workspace's key (NOT the global resend.api_key) so concurrent
    # tenants don't trample on each other. We set + reset around the call.
    saved_key = resend.api_key
    resend.api_key = cfg["resend_api_key"]
    try:
        result = await asyncio.to_thread(resend.Emails.send, params)
    finally:
        resend.api_key = saved_key

    return {
        "ok": True,
        "provider_id": (result or {}).get("id") if isinstance(result, dict) else None,
        "from": from_field,
        "to": to,
        "attachments_count": len(attachments),
        "signature_appended": append_signature and bool(cfg["signature_html"]),
    }


def humanise_resend_error(exc: Exception) -> HTTPException:
    """Convert a Resend SDK exception into a friendly HTTPException."""
    msg = str(exc)[:240]
    low = msg.lower()
    if "you can only send testing emails to your own email" in low or "verify a domain at resend.com/domains" in low:
        return HTTPException(
            400,
            (
                "Resend is in sandbox mode for this account — it only delivers to your verified "
                "account email. Verify a sending domain at resend.com/domains and set the from_address "
                "to that domain (e.g. john@yourdomain.com) to send to anyone."
            ),
        )
    if "domain" in low and ("not verified" in low or "unverified" in low):
        return HTTPException(400, "The from_address domain is not verified in Resend. Verify it in Resend → Domains, then retry.")
    if "api key" in low or "unauthorized" in low or "401" in low:
        return HTTPException(400, "Resend rejected the API key. Paste a fresh key from Resend → API Keys and retry.")
    return HTTPException(502, f"Could not send email: {msg}")


async def verify_resend_handshake(api_key: str) -> Dict[str, Any]:
    """Lightweight Resend ping — list domains to confirm the key works.

    Returns {ok: bool, message: str, domains: list[str]}.
    """
    import httpx
    if not api_key:
        return {"ok": False, "message": "No API key provided.", "domains": []}
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(
                "https://api.resend.com/domains",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        if r.status_code == 401:
            return {"ok": False, "message": "Resend rejected the API key. Paste a fresh key and retry.", "domains": []}
        if r.status_code == 403:
            return {"ok": False, "message": "API key is valid but lacks domain-read permission.", "domains": []}
        if r.status_code >= 400:
            return {"ok": False, "message": f"Resend returned {r.status_code}.", "domains": []}
        data = r.json() or {}
        domain_list = []
        for d in (data.get("data") or data.get("domains") or []):
            name = d.get("name") if isinstance(d, dict) else None
            status = d.get("status") if isinstance(d, dict) else None
            if name:
                domain_list.append(f"{name}{' (' + status + ')' if status else ''}")
        if not domain_list:
            return {"ok": True, "message": "Connected to Resend (no custom domains verified yet — only the account-owner inbox can receive).", "domains": []}
        return {"ok": True, "message": f"Connected to Resend. {len(domain_list)} domain(s) ready.", "domains": domain_list}
    except Exception as e:
        return {"ok": False, "message": f"Could not reach Resend: {str(e)[:160]}", "domains": []}
