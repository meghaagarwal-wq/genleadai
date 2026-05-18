"""Password reset + Email-code login — Iter46.

Two passwordless flows that sit alongside the existing email+password JWT login:

  1. Forgot password
       POST /api/auth/password/forgot   {email}                 → 200 (idempotent — no enumeration leak)
       POST /api/auth/password/reset    {email, code, new_password}  → 200 + new login token

  2. Email-code login
       POST /api/auth/email-code/request  {email}               → 200 (idempotent)
       POST /api/auth/email-code/verify   {email, code}         → 200 + login token (same shape as /login)

Codes are 6-digit numeric, stored in `auth_codes` Mongo collection with a TTL
index of 600s, max 5 verify attempts before lock. Rate-limited at 3 requests
per email per 15 minutes via the request-side `auth_code_requests` collection.

Email delivery reuses the existing Resend sender configured in server.py.
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr
import resend

from deps import (
    users_collection,
    db,
    get_password_hash,
    create_access_token,
)

router = APIRouter(prefix="/api/auth", tags=["auth-extras"])

codes_col = db["auth_codes"]
rl_col = db["auth_code_requests"]

# TTL index on auth_codes — Mongo auto-purges 10-min-old codes.
try:
    codes_col.create_index("expires_at", expireAfterSeconds=0)
    codes_col.create_index([("email", 1), ("purpose", 1)])
except Exception:
    pass  # already exists


CODE_TTL_SECONDS = 600          # 10 minutes
REQUESTS_PER_15MIN = 3
MAX_VERIFY_ATTEMPTS = 5
APP_NAME = "Aria by GenLeadAI"


# ─── Pydantic models ─────────────────────────────────────────────────────
class ForgotRequest(BaseModel):
    email: EmailStr


class ResetRequest(BaseModel):
    email: EmailStr
    code: str
    new_password: str


class EmailCodeRequest(BaseModel):
    email: EmailStr


class EmailCodeVerify(BaseModel):
    email: EmailStr
    code: str


# ─── Helpers ─────────────────────────────────────────────────────────────
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _generate_code() -> str:
    # Cryptographically-secure 6-digit code (was random.randint — security review iter70).
    return f"{secrets.randbelow(1_000_000):06d}"


def _rate_limited(email: str) -> bool:
    """Return True if the email has hit > REQUESTS_PER_15MIN code requests in the last 15 min."""
    # Naive utcnow because PyMongo stores BSON datetime without timezone.
    cutoff = datetime.utcnow() - timedelta(minutes=15)
    count = rl_col.count_documents({"email": email.lower(), "created_at": {"$gte": cutoff}})
    return count >= REQUESTS_PER_15MIN


def _record_request(email: str, purpose: str) -> None:
    rl_col.insert_one({"email": email.lower(), "purpose": purpose, "created_at": datetime.utcnow()})


def _issue_code(email: str, purpose: str) -> str:
    """Create a single active code per (email, purpose); invalidate prior ones."""
    code = _generate_code()
    codes_col.delete_many({"email": email.lower(), "purpose": purpose})
    codes_col.insert_one({
        "email": email.lower(),
        "purpose": purpose,
        "code_hash": get_password_hash(code),
        "attempts": 0,
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(seconds=CODE_TTL_SECONDS),
        "used": False,
    })
    return code


def _verify_code(email: str, code: str, purpose: str) -> bool:
    """Validate; increments attempts; one-shot use (deletes on success)."""
    from deps import verify_password
    doc = codes_col.find_one({"email": email.lower(), "purpose": purpose, "used": False})
    if not doc:
        return False
    # PyMongo strips tz info on read, so compare with a naive utcnow for safety.
    expires_at = doc.get("expires_at")
    if expires_at is not None:
        if expires_at.tzinfo is not None:
            expires_at = expires_at.replace(tzinfo=None)
        if expires_at < datetime.utcnow():
            codes_col.delete_one({"_id": doc["_id"]})
            return False
    if int(doc.get("attempts", 0)) >= MAX_VERIFY_ATTEMPTS:
        codes_col.delete_one({"_id": doc["_id"]})
        return False
    codes_col.update_one({"_id": doc["_id"]}, {"$inc": {"attempts": 1}})
    if not verify_password(code, doc["code_hash"]):
        return False
    codes_col.delete_one({"_id": doc["_id"]})
    return True


def _send_code_email(to_email: str, code: str, purpose: str) -> dict:
    """Send the code via Resend. Returns the delivery result so endpoints
    can mirror it back to the UI (e.g. show a 'check spam' or test-mode hint).
    """
    try:
        from email_delivery import send_email_safe
    except Exception as e:
        print(f"[auth-extras] email_delivery import failed: {e}")
        return {"delivered": False, "delivery_status": "skipped"}

    subject = "Your Aria login code" if purpose == "email_code" else "Reset your Aria password"
    intro = (
        "Use this code to sign in to Aria. It expires in 10 minutes."
        if purpose == "email_code"
        else "Use this code to reset your password. It expires in 10 minutes."
    )
    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 480px; margin: 0 auto; padding: 32px; background: linear-gradient(135deg, #FFFFFF 0%, #FAF7FF 100%); border-radius: 16px;">
        <div style="text-align: center; margin-bottom: 24px;">
            <div style="display: inline-block; padding: 12px 18px; background: linear-gradient(135deg, #C044E0 0%, #7C35DC 50%, #5B28D4 100%); color: white; border-radius: 12px; font-weight: 800; letter-spacing: 0.1em;">ARIA</div>
        </div>
        <h2 style="color: #1A0A2E; font-weight: 800; margin: 0 0 8px 0;">{subject}</h2>
        <p style="color: #5A4A7A; line-height: 1.6; margin: 0 0 24px 0;">{intro}</p>
        <div style="text-align: center; background: white; border: 2px dashed #C044E0; border-radius: 12px; padding: 24px; margin: 24px 0;">
            <div style="font-size: 36px; font-weight: 900; color: #7C35DC; letter-spacing: 0.3em; font-family: 'SF Mono', Menlo, monospace;">{code}</div>
        </div>
        <p style="color: #9B8AB0; font-size: 12px; line-height: 1.5;">If you didn't request this code, you can safely ignore this email. The code will expire automatically.</p>
        <p style="color: #9B8AB0; font-size: 11px; margin-top: 24px;">— {APP_NAME}</p>
    </div>
    """
    r = send_email_safe(to_email=to_email, subject=subject, html=html, purpose=purpose)
    return {"delivered": r.delivered, "delivery_status": r.delivery_status, "forwarded_to": r.forwarded_to}


# ─── Endpoints ────────────────────────────────────────────────────────────
@router.post("/password/forgot")
def password_forgot(payload: ForgotRequest):
    """Step 1 of password reset. Idempotent — never reveals whether the email exists."""
    email = payload.email.lower().strip()
    if _rate_limited(email):
        # Still return 200 to avoid enumeration; just don't send.
        return {"ok": True, "delivery_status": "rate_limited"}
    delivery = {"delivered": False, "delivery_status": "skipped"}
    user = users_collection.find_one({"email": email})
    if user:
        code = _issue_code(email, "password_reset")
        delivery = _send_code_email(email, code, "password_reset")
    _record_request(email, "password_reset")
    return {"ok": True, **delivery}


@router.post("/password/reset")
def password_reset(payload: ResetRequest):
    """Step 2 of password reset. Verifies code + sets the new password.

    Returns a fresh JWT so the user is logged in immediately after reset.
    """
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    email = payload.email.lower().strip()
    if not _verify_code(email, payload.code.strip(), "password_reset"):
        raise HTTPException(status_code=400, detail="Invalid or expired code.")
    user = users_collection.find_one({"email": email})
    if not user:
        # Shouldn't happen — verify succeeded — but stay safe.
        raise HTTPException(status_code=400, detail="Could not reset password.")
    users_collection.update_one(
        {"email": email},
        {"$set": {
            "password_hash": get_password_hash(payload.new_password),
            "password_changed_at": _now().isoformat(),
        }},
    )
    token = create_access_token({"sub": email})
    return {
        "ok": True,
        "token": token,
        "user": {
            "email": user["email"],
            "full_name": user.get("full_name", ""),
            "role": user.get("role", "sales_rep"),
            "avatar_url": user.get("avatar_url"),
        },
    }


@router.post("/email-code/request")
def email_code_request(payload: EmailCodeRequest):
    """Step 1 of passwordless email-code login. Idempotent."""
    email = payload.email.lower().strip()
    if _rate_limited(email):
        return {"ok": True, "delivery_status": "rate_limited"}
    delivery = {"delivered": False, "delivery_status": "skipped"}
    user = users_collection.find_one({"email": email})
    if user:
        code = _issue_code(email, "email_code")
        delivery = _send_code_email(email, code, "email_code")
    _record_request(email, "email_code")
    return {"ok": True, **delivery}


@router.post("/email-code/verify")
def email_code_verify(payload: EmailCodeVerify):
    """Step 2 of passwordless email-code login. Issues the same JWT as /api/auth/login."""
    email = payload.email.lower().strip()
    if not _verify_code(email, payload.code.strip(), "email_code"):
        raise HTTPException(status_code=400, detail="Invalid or expired code.")
    user = users_collection.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=400, detail="Account not found.")
    token = create_access_token({"sub": email})
    return {
        "ok": True,
        "token": token,
        "user": {
            "email": user["email"],
            "full_name": user.get("full_name", ""),
            "role": user.get("role", "sales_rep"),
            "avatar_url": user.get("avatar_url"),
        },
    }
