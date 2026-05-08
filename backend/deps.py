"""Shared dependencies for GenLeadAI backend.

Centralises DB handle, collections, auth utilities, and common helpers so that
modular routers under /app/backend/routes/ can import them without circular
dependencies on server.py.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

# ─── Database ────────────────────────────────────────────────────────────────
mongo_client = MongoClient(os.getenv("MONGO_URL"))
db = mongo_client[os.getenv("DB_NAME")]

# ─── Core collections ────────────────────────────────────────────────────────
leads_collection = db["leads"]
activities_collection = db["activities"]
campaigns_collection = db["campaigns"]
users_collection = db["users"]
pipelines_collection = db["pipelines"]
aria_conversations_collection = db["aria_conversations"]
workspace_assets_collection = db["workspace_assets"]
aria_settings_collection = db["aria_settings"]

# ─── Security ────────────────────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 10080))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-Id"),
):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = users_collection.find_one({"email": email}, {"_id": 0})
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        # Attach the user's active tenant_id for cross-cutting isolation.
        # Resolution order:
        #   1. Honour X-Tenant-Id header IF user is a member of that tenant.
        #   2. Else fall back to user's primary (oldest) membership.
        try:
            mem_col = db["tenant_memberships"]
            chosen = None
            if x_tenant_id:
                chosen = mem_col.find_one(
                    {"user_email": email, "tenant_id": x_tenant_id},
                    {"_id": 0, "tenant_id": 1, "role": 1},
                )
            if not chosen:
                chosen = mem_col.find_one(
                    {"user_email": email},
                    {"_id": 0, "tenant_id": 1, "role": 1},
                    sort=[("joined_at", 1)],
                )
            if chosen:
                user["tenant_id"] = chosen.get("tenant_id")
                user["tenant_role"] = chosen.get("role")
        except Exception:
            # Never fail auth because of tenant lookup
            pass
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def serialize_doc(doc):
    if doc and "_id" in doc:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
    return doc
