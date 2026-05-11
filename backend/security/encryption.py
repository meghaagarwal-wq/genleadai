"""Symmetric encryption helper used to protect stored secrets.

Generates a per-process Fernet key from APP_SECRET_KEY (env). If APP_SECRET_KEY
is missing in dev, we derive a stable key from a fallback constant so existing
secrets remain decryptable across restarts. Production deployments MUST set
APP_SECRET_KEY to a 32-byte url-safe base64 string.
"""
from __future__ import annotations

import base64
import hashlib
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


def _derive_key(secret: str) -> bytes:
    # 32-byte SHA-256 digest → url-safe base64 = valid Fernet key
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


_SECRET = os.environ.get("APP_SECRET_KEY") or "aria-dev-fallback-secret-do-not-use-in-prod"
_FERNET = Fernet(_derive_key(_SECRET))

# Marker prefix so we know the value is encrypted (and to allow lazy migration
# of unencrypted legacy values).
_PREFIX = "enc::"


def encrypt(value: Optional[str]) -> Optional[str]:
    """Encrypt a string. Idempotent — already-encrypted values pass through."""
    if value is None or value == "":
        return value
    if isinstance(value, str) and value.startswith(_PREFIX):
        return value
    token = _FERNET.encrypt(str(value).encode("utf-8")).decode("utf-8")
    return _PREFIX + token


def decrypt(value: Optional[str]) -> Optional[str]:
    """Decrypt a previously-encrypted string. Returns the original value if it
    wasn't encrypted (graceful fallback for legacy unencrypted data)."""
    if value is None or value == "":
        return value
    if not isinstance(value, str) or not value.startswith(_PREFIX):
        return value
    try:
        return _FERNET.decrypt(value[len(_PREFIX):].encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return value


def encrypt_dict(d: dict, keys: list[str]) -> dict:
    """Encrypt specified keys inside a dict (in place). Returns the same dict."""
    if not d:
        return d
    for k in keys:
        if k in d and d[k]:
            d[k] = encrypt(d[k])
    return d


def decrypt_dict(d: dict, keys: list[str]) -> dict:
    """Decrypt specified keys inside a dict (in place). Returns the same dict."""
    if not d:
        return d
    for k in keys:
        if k in d and d[k]:
            d[k] = decrypt(d[k])
    return d
