"""Auth endpoints: register, login (with brute-force protection), /me.

Brute-force protection
----------------------
Login is rate-limited on two dimensions simultaneously, so an attacker can't
trivially rotate IPs OR emails:

  * per-email: max 5 failures in 15 min → 401 with normal "Invalid" detail,
                                          but on the 5th failure we lock the
                                          email for 15 min (returns 429).
  * per-ip:    max 20 failures in 15 min → 429 (slower lockout, allows
                                                shared-NAT founder offices).

Successful login clears the per-email counter immediately. Every failure
and lockout is audit-logged so the master admin can see attack patterns
in the Audit Log tab.
"""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr

from security.limiter import limiter as _limiter  # iter80 — S9.5 rate limits

from deps import (
    users_collection,
    db,
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Brute-force tracking collection — auto-pruned by TTL index below.
login_attempts_col = db["login_attempts"]
try:
    login_attempts_col.create_index([("created_at", 1)], expireAfterSeconds=3600)
    login_attempts_col.create_index([("email", 1)])
    login_attempts_col.create_index([("ip", 1)])
except Exception:
    pass

EMAIL_WINDOW_MIN = 15
EMAIL_MAX_FAILS = 5
IP_WINDOW_MIN = 15
IP_MAX_FAILS = 20


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: str = "sales_rep"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _utc_now() -> datetime:
    return datetime.utcnow()


def _record_attempt(email: str, ip: str, success: bool) -> None:
    try:
        login_attempts_col.insert_one({
            "email": (email or "").lower(),
            "ip": ip,
            "success": success,
            "created_at": _utc_now(),
        })
    except Exception:
        pass


def _failures_in_window(filter_query: dict, minutes: int) -> int:
    cutoff = _utc_now() - timedelta(minutes=minutes)
    return login_attempts_col.count_documents({**filter_query, "success": False, "created_at": {"$gte": cutoff}})


def _audit_login_event(email: str, action: str, ip: str, success: bool, reason: str = "") -> None:
    """Mirror to the existing audit_log so master admin can review."""
    try:
        from routes.audit_log import col as audit_col
        import uuid
        audit_col.insert_one({
            "id": f"aud_{uuid.uuid4().hex[:12]}",
            "tenant_id": None,
            "user_id": (email or "").lower() or None,
            "action": action,
            "resource_type": "auth",
            "resource_id": None,
            "metadata": {"ip": ip, "success": success, "reason": reason or None},
            "ip_address": ip,
            "user_agent": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass


@router.post("/register")
async def register(user: UserRegister):
    """[DISABLED on multi-tenant] Use /api/auth/signup instead — that endpoint
    creates user + tenant + owner membership atomically. Legacy register would
    leave users without a tenant and trigger 403s on every authenticated route.
    """
    raise HTTPException(
        status_code=410,
        detail="Use /api/auth/signup — legacy registration is disabled on this multi-tenant build.",
    )


@router.post("/login")
@_limiter.limit("10/minute")  # iter80 — S9.5: 10 login attempts per IP per minute
async def login(credentials: UserLogin, request: Request):
    email = (credentials.email or "").lower().strip()
    ip = _client_ip(request)

    # ── Pre-flight brute-force checks ────────────────────────────────────
    email_fails = _failures_in_window({"email": email}, EMAIL_WINDOW_MIN)
    if email_fails >= EMAIL_MAX_FAILS:
        _audit_login_event(email, "auth.login_blocked", ip, False, "email_locked")
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed attempts on this account. Try again in {EMAIL_WINDOW_MIN} minutes or use 'Forgot password'.",
        )
    ip_fails = _failures_in_window({"ip": ip}, IP_WINDOW_MIN)
    if ip_fails >= IP_MAX_FAILS:
        _audit_login_event(email, "auth.login_blocked", ip, False, "ip_locked")
        raise HTTPException(
            status_code=429,
            detail="Too many failed attempts from this network. Try again in 15 minutes.",
        )

    # ── Credential check ─────────────────────────────────────────────────
    user = users_collection.find_one({"email": email})
    if not user or not verify_password(credentials.password, user["password_hash"]):
        _record_attempt(email, ip, success=False)
        _audit_login_event(email, "auth.login_failed", ip, False, "bad_credentials")
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # ── Success: clear the email's failure history so legitimate users aren't punished
    try:
        login_attempts_col.delete_many({"email": email, "success": False})
    except Exception:
        pass
    _record_attempt(email, ip, success=True)
    _audit_login_event(email, "auth.login_success", ip, True)

    token = create_access_token({"sub": email})
    return {
        "token": token,
        "user": {
            "email": user["email"],
            "full_name": user["full_name"],
            "role": user["role"],
            "avatar_url": user.get("avatar_url"),
        },
    }


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return current_user


@router.post("/change-password")
async def change_password(payload: PasswordChange, current_user: dict = Depends(get_current_user)):
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
    user = users_collection.find_one({"email": current_user["email"]})
    if not user or not verify_password(payload.current_password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    if verify_password(payload.new_password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="New password must be different from current password")
    users_collection.update_one(
        {"email": current_user["email"]},
        {"$set": {
            "password_hash": get_password_hash(payload.new_password),
            "password_changed_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return {"status": "ok", "message": "Password updated successfully"}
