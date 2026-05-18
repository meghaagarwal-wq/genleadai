"""Email delivery wrapper — single chokepoint for all outbound mail.

Why this exists
---------------
Resend in dev mode only allows the owner address to receive mail. Without a
verified domain, every `to:` other than the verified owner returns:

    ResendError: You can only send testing emails to your own email address...

That kills password reset / email-code login for every other user. This
wrapper:

  1. Always tries the real send first.
  2. On the test-mode rejection, **rewrites the To: to the verified
     fallback address** (CONTACT_FORWARD_EMAIL / MASTER_ADMIN_EMAIL) and
     re-sends, so the founder still receives the message and can manually
     relay it. The subject gets a `[for: <original_to>]` prefix so they
     know who it was intended for.
  3. Records the attempt + outcome in `email_delivery_log` so the master
     admin Health Monitor can flag delivery problems.
  4. Returns a structured DeliveryResult the caller can surface to the UI.

Once the founder verifies a domain at resend.com/domains and sets
SENDER_EMAIL=noreply@<their-verified-domain>, the wrapper passes through
unmodified.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import resend

from deps import db

log_col = db["email_delivery_log"]
try:
    log_col.create_index([("created_at", -1)])
except Exception:
    pass


@dataclass
class DeliveryResult:
    delivered: bool
    delivery_status: str   # "sent" | "test_mode_forwarded" | "failed" | "skipped"
    detail: Optional[str] = None
    forwarded_to: Optional[str] = None


def _record(to_email: str, subject: str, result: DeliveryResult) -> None:
    try:
        log_col.insert_one({
            "to": to_email,
            "subject": subject,
            "delivery_status": result.delivery_status,
            "forwarded_to": result.forwarded_to,
            "detail": (result.detail or "")[:600],
            "created_at": datetime.utcnow(),
        })
    except Exception:
        pass


def send_email_safe(
    *,
    to_email: str,
    subject: str,
    html: str,
    reply_to: Optional[str] = None,
    purpose: str = "generic",
    attachments: Optional[list] = None,
) -> DeliveryResult:
    """Best-effort email send with test-mode fallback. Never raises.

    attachments: list of dicts like
        {"filename": "invoice.pdf", "content": <bytes>}
    """
    api_key = os.getenv("RESEND_API_KEY")
    sender = os.getenv("SENDER_EMAIL", "onboarding@resend.dev")
    if not api_key:
        result = DeliveryResult(delivered=False, delivery_status="skipped", detail="RESEND_API_KEY not set")
        _record(to_email, subject, result)
        return result

    resend.api_key = api_key
    params = {"from": sender, "to": [to_email], "subject": subject, "html": html}
    if reply_to:
        params["reply_to"] = reply_to
    if attachments:
        # Resend expects {filename, content (base64 OR bytes)}.
        import base64
        params["attachments"] = [
            {"filename": a["filename"],
             "content": base64.b64encode(a["content"]).decode() if isinstance(a.get("content"), (bytes, bytearray)) else a["content"]}
            for a in attachments
        ]

    # 1. Try the real send.
    try:
        resend.Emails.send(params)
        result = DeliveryResult(delivered=True, delivery_status="sent")
        _record(to_email, subject, result)
        return result
    except Exception as e:
        msg = str(e)

    # 2. Test-mode fallback — only triggers on the very specific Resend dev rejection.
    if "testing emails" in msg or "verify a domain" in msg:
        fallback = os.getenv("CONTACT_FORWARD_EMAIL") or os.getenv("MASTER_ADMIN_EMAIL")
        if fallback and fallback.lower() != to_email.lower():
            forwarded_subject = f"[for: {to_email}] {subject}"
            forward_params = {**params, "to": [fallback], "subject": forwarded_subject}
            try:
                resend.Emails.send(forward_params)
                result = DeliveryResult(
                    delivered=True,
                    delivery_status="test_mode_forwarded",
                    detail="Resend domain not verified — forwarded to admin inbox.",
                    forwarded_to=fallback,
                )
                _record(to_email, subject, result)
                print(f"[email] test-mode fallback: forwarded '{subject}' (intended for {to_email}) to {fallback}")
                return result
            except Exception as e2:
                msg = f"primary failed: {msg!r} | fallback failed: {e2!r}"

    # 3. Hard failure.
    result = DeliveryResult(delivered=False, delivery_status="failed", detail=msg)
    _record(to_email, subject, result)
    print(f"[email] send failed for {to_email}: {msg}")
    return result


def email_health_summary(limit: int = 50) -> dict:
    """Used by master-admin Health Monitor to show send-health at a glance."""
    cursor = log_col.find({}, {"_id": 0}).sort("created_at", -1).limit(limit)
    rows = list(cursor)
    total = len(rows)
    by_status: dict[str, int] = {}
    for r in rows:
        k = r.get("delivery_status", "unknown")
        by_status[k] = by_status.get(k, 0) + 1
    return {
        "samples": total,
        "by_status": by_status,
        "is_test_mode": (by_status.get("test_mode_forwarded", 0) > 0 and by_status.get("sent", 0) == 0),
        "sender": os.getenv("SENDER_EMAIL"),
        "fallback": os.getenv("CONTACT_FORWARD_EMAIL") or os.getenv("MASTER_ADMIN_EMAIL"),
    }
