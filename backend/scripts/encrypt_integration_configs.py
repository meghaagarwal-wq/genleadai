"""Iter102 — Encrypt-at-rest migration for integration_configs.

Idempotent. Scans every doc in `integration_configs`; for each
secret-looking field whose value is NOT already prefixed with the
Fernet `enc::` marker, encrypts in-place.

Run from `/app/backend`:
    python scripts/encrypt_integration_configs.py

Also auto-invoked on backend startup so existing prod data is
migrated transparently on the next deploy.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deps import db  # noqa: E402
from security.encryption import encrypt  # noqa: E402

_SECRET_KEY_HINTS = ("token", "secret", "key", "password", "access", "pixel")

_ENC_PREFIX = "enc::"


def _is_secret_field(k: str) -> bool:
    kl = (k or "").lower()
    return any(s in kl for s in _SECRET_KEY_HINTS)


def run() -> dict:
    col = db["integration_configs"]
    scanned = 0
    encrypted = 0
    docs_touched = 0
    for doc in col.find({}, {"_id": 1, "config": 1}):
        scanned += 1
        cfg = doc.get("config") or {}
        updates = {}
        for k, v in cfg.items():
            if not _is_secret_field(k):
                continue
            if not isinstance(v, str) or not v:
                continue
            if v.startswith(_ENC_PREFIX):
                continue  # already encrypted
            updates[f"config.{k}"] = encrypt(v)
        if updates:
            col.update_one({"_id": doc["_id"]}, {"$set": updates})
            docs_touched += 1
            encrypted += len(updates)
    summary = {"scanned": scanned, "docs_touched": docs_touched, "fields_encrypted": encrypted}
    return summary


if __name__ == "__main__":
    out = run()
    print(f"[encrypt_integration_configs] {out}")
