"""Auth endpoints: register, login, /me."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from deps import (
    users_collection,
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


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
async def login(credentials: UserLogin):
    user = users_collection.find_one({"email": credentials.email})
    if not user or not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({"sub": credentials.email})
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
