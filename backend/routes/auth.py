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
    if users_collection.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email already registered")

    user_doc = {
        "email": user.email,
        "password_hash": get_password_hash(user.password),
        "full_name": user.full_name,
        "role": user.role,
        "avatar_url": f"https://ui-avatars.com/api/?name={user.full_name.replace(' ', '+')}&background=0055FF&color=fff",
        "team": "Sales",
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    users_collection.insert_one(user_doc)
    token = create_access_token({"sub": user.email})
    return {
        "token": token,
        "user": {"email": user.email, "full_name": user.full_name, "role": user.role},
    }


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
