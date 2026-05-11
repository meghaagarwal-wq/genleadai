"""Data retention cron — Phase 8.7 of master spec.

Runs daily at 02:00 UTC. Deletes:
  - Conversation message content older than 365 days (keeps metadata stub).
  - classification_log older than 180 days.
  - api_usage_log older than 90 days.
  - failed_message_log entries that are resolved AND older than 30 days.
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone, timedelta

from deps import db

aria_conversations = db["aria_conversations"]
classification_log = db["classification_log"]
api_usage_log = db["api_usage_log"]
failed_message_log = db["failed_message_log"]


def _cut(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


async def run_retention_once() -> dict:
    """Run one retention pass — returns counts for logging."""
    counts = {}

    # 1. Conversation message content (anonymise — keep _id + role + created_at)
    cutoff = _cut(365)
    res = aria_conversations.update_many(
        {"created_at": {"$lt": cutoff}, "message": {"$exists": True, "$ne": "[redacted]"}},
        {"$set": {"message": "[redacted]", "message_redacted_at": datetime.now(timezone.utc).isoformat()}},
    )
    counts["conversation_content_redacted"] = res.modified_count

    # 2. Classification log (hard delete)
    res = classification_log.delete_many({"created_at": {"$lt": _cut(180)}})
    counts["classification_log_deleted"] = res.deleted_count

    # 3. API usage log (hard delete)
    res = api_usage_log.delete_many({"created_at": {"$lt": _cut(90)}})
    counts["api_usage_log_deleted"] = res.deleted_count

    # 4. Failed message log — resolved only (hard delete)
    res = failed_message_log.delete_many({"resolved": True, "created_at": {"$lt": _cut(30)}})
    counts["failed_messages_deleted"] = res.deleted_count

    counts["ran_at"] = datetime.now(timezone.utc).isoformat()
    return counts


async def retention_loop() -> None:
    """Background loop — runs every 24 hours (idempotent)."""
    while True:
        try:
            await run_retention_once()
        except Exception as e:
            # Best-effort — never crash the loop
            import logging
            logging.getLogger("retention").exception("retention_loop error: %s", e)
        # Sleep 24h
        await asyncio.sleep(24 * 60 * 60)
