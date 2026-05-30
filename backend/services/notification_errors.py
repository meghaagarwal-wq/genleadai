"""iter138 — Shared helper for classifying Resend/Email send errors.

Originally introduced in iter137 inside routes/aria_eod_wrap.py to convert
uncaught resend.exceptions.ResendError into structured 503 responses.
Now extracted here so morning_brief, approval_digest, and any future
notification sender can reuse it instead of duplicating the regex.

Usage:
    from services.notification_errors import classify_send_error
    info = classify_send_error(str(e))
    raise HTTPException(status_code=info["status"], detail=info)
"""
from __future__ import annotations

import re

_RESEND_SANDBOX_RE = re.compile(
    r"verify a domain at resend\.com/domains|testing emails to your own|sandbox|not verified",
    re.I,
)


def classify_send_error(err: str) -> dict:
    """Classify a Resend (or generic) send error into a UI-friendly payload.

    Returns a dict with keys: code, user_message, status.
    Always returns 503 — these are integration-config issues, not server bugs.
    """
    if not err:
        return {
            "code": "unknown",
            "user_message": "Send failed for an unknown reason.",
            "status": 503,
        }
    if _RESEND_SANDBOX_RE.search(err):
        return {
            "code": "resend_sandbox_or_unverified_domain",
            "user_message": (
                "Resend is in sandbox mode (free tier) or your sending domain isn't verified. "
                "Verify a domain at resend.com/domains and set SENDER_EMAIL on that domain to send to any recipient."
            ),
            "status": 503,
        }
    if "no_resend_key" in err or "no_recipient" in err:
        return {
            "code": err,
            "user_message": "Resend isn't connected for this workspace. Add your Resend API key under Integrations.",
            "status": 503,
        }
    return {
        "code": "send_failed",
        "user_message": err[:200],
        "status": 503,
    }


__all__ = ["classify_send_error"]
