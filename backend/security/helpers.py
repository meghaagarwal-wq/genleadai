"""Iter80 — S9.5 security helpers.

Centralised utilities for:
  • NoSQL-injection guards on user-controlled filter dicts
  • Prompt-injection sanitisation for Claude callers
  • Webhook replay protection (timestamp window check)
  • Masked key responses for API key fields
"""
from __future__ import annotations

import re
import time
from typing import Any, Optional


# ─── 1. NoSQL guard ─────────────────────────────────────────────────────────
_FORBIDDEN_PREFIXES = ("$",)


def safe_filter_value(v: Any) -> Any:
    """Recursively strip Mongo operator keys ($where, $gt, $ne, $regex, …)
    from any user-controlled value. Use BEFORE passing user input into a
    Mongo `find()` / `update()` filter dict.

    Returns:
        - scalars unchanged
        - lists/tuples → recursively cleaned list
        - dicts → recursively cleaned dict with $-keys removed
    """
    if isinstance(v, dict):
        return {
            k: safe_filter_value(val)
            for k, val in v.items()
            if isinstance(k, str) and not any(k.startswith(p) for p in _FORBIDDEN_PREFIXES)
        }
    if isinstance(v, (list, tuple)):
        return [safe_filter_value(x) for x in v]
    return v


def safe_query_param(s: Optional[str], max_len: int = 256) -> str:
    """Coerce a user-supplied query-string value into a plain string of
    bounded length and strip leading `$` so it can never become a Mongo
    operator if accidentally spread into a filter."""
    if s is None:
        return ""
    s = str(s)[:max_len]
    while s.startswith("$"):
        s = s[1:]
    return s


# ─── 2. Prompt-injection sanitiser ──────────────────────────────────────────
_INJECTION_PATTERNS = [
    re.compile(r"<\s*/?\s*system\s*>", re.IGNORECASE),
    re.compile(r"<\s*/?\s*assistant\s*>", re.IGNORECASE),
    re.compile(r"<\s*/?\s*user\s*>", re.IGNORECASE),
    re.compile(r"\b(?:ignore|disregard|forget)\s+(?:all\s+|the\s+|your\s+)?(?:previous|prior|earlier|above)?\s*(?:instructions?|prompts?|directives?|rules?|context)\b", re.IGNORECASE),
    re.compile(r"###\s*new\s+instructions\b", re.IGNORECASE),
    re.compile(r"\[\[\s*SYSTEM\s*\]\]", re.IGNORECASE),
]


def sanitise_for_prompt(text: Optional[str], max_len: int = 4000) -> str:
    """Neutralise common prompt-injection payloads before slotting user
    content into a Claude prompt. Tags are replaced with a visible
    placeholder so the LLM still sees the user's intent without being
    able to issue a fake instruction."""
    if not text:
        return ""
    cleaned = str(text)[:max_len]
    for pat in _INJECTION_PATTERNS:
        cleaned = pat.sub("[redacted-tag]", cleaned)
    return cleaned


# ─── 3. Webhook replay window ───────────────────────────────────────────────
def is_replay(timestamp_ms: Optional[int | str], window_seconds: int = 300) -> bool:
    """Returns True if the webhook's claimed timestamp is older than the
    allowed window (default 5 min) OR more than 60s in the future. We
    treat both as replay attempts.

    Accepts ms (number or string). If unparsable / missing, treat as
    replay = True (fail closed)."""
    if timestamp_ms in (None, ""):
        return True
    try:
        ts_ms = int(str(timestamp_ms))
    except Exception:
        return True
    now_ms = int(time.time() * 1000)
    age = now_ms - ts_ms
    if age > window_seconds * 1000:
        return True
    if age < -60 * 1000:    # > 60s in the future
        return True
    return False


# ─── 4. Mask API key for safe display ───────────────────────────────────────
def mask_key(value: Optional[str]) -> Optional[str]:
    """Render an API key as `abcd••••••wxyz`. Returns None unchanged."""
    if not value:
        return None
    v = str(value)
    if v.startswith("enc::"):
        return "•" * 12  # fully hidden; never expose ciphertext shape
    if len(v) <= 8:
        return "•" * len(v)
    return f"{v[:4]}{'•' * 6}{v[-4:]}"
