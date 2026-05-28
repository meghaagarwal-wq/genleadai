"""ARIA — Knowledge-base RAG retrieval at query time.

Wires the workspace's `knowledge_base_chunks` (stored on the training
profile) into B2C conversational responses. Flow:

  1. Claude haiku turns the user question into 3-6 search keywords.
  2. We rank workspace KB chunks by keyword overlap (token-set Jaccard).
  3. Top 3 chunks are returned as grounding context for the answering call.

If no chunks match well enough (best score < 0.05), the caller should
fall back to a polite handoff message and notify the workspace owner.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

from deps import db
from services.claude_service import claude_call, TaskType, ClaudeServiceError

logger = logging.getLogger("kb_rag")

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
_STOP = {
    "the", "a", "an", "is", "are", "was", "were", "of", "and", "or", "to",
    "for", "in", "on", "at", "with", "by", "from", "as", "be", "this",
    "that", "it", "we", "you", "your", "our", "i", "me", "my", "they",
}


def _tokens(text: str) -> set:
    if not text:
        return set()
    return {t.lower() for t in _TOKEN_RE.findall(text) if t.lower() not in _STOP and len(t) > 2}


def _profile_chunks(tenant_id: str) -> List[str]:
    tdoc = db["tenants"].find_one({"id": tenant_id}, {"_id": 0, "settings": 1}) or {}
    prof = ((tdoc.get("settings") or {}).get("aria_training_profile") or {}).get("data") or {}
    chunks = prof.get("knowledge_base_chunks") or []
    return [c for c in chunks if isinstance(c, str) and c.strip()]


async def _extract_keywords(question: str, tenant_id: Optional[str]) -> List[str]:
    """Claude haiku → 3-6 search keywords from the user question."""
    try:
        data = await claude_call(
            task_type=TaskType.KNOWLEDGE_RETRIEVAL,
            system=(
                "You extract search keywords. Output STRICT JSON only. "
                'Schema: {"keywords":[string,...]}. Return 3-6 keywords drawn '
                "from the user question — lowercase, single tokens or short "
                "noun-phrases, no stop words."
            ),
            prompt=f"USER QUESTION:\n{question}",
            tenant_id=tenant_id,
            session_id=f"kb-keywords-{tenant_id or 'anon'}",
            response_format="json",
            sanitize_user_input=True,
        )
        kws = data.get("keywords") if isinstance(data, dict) else None
        if isinstance(kws, list):
            return [str(k).lower().strip() for k in kws if str(k).strip()][:6]
    except ClaudeServiceError:
        pass
    # Fallback: keyword-extract the question ourselves.
    return list(_tokens(question))[:6]


def _score(keywords: List[str], chunk: str) -> float:
    """Jaccard over keyword tokens vs chunk tokens. Cheap, deterministic,
    good enough for a few-dozen-chunks RAG corpus."""
    if not chunk:
        return 0.0
    chunk_tokens = _tokens(chunk)
    if not chunk_tokens:
        return 0.0
    kset = {k.lower() for k in keywords if k}
    if not kset:
        return 0.0
    overlap = len(kset & chunk_tokens)
    if overlap == 0:
        return 0.0
    return overlap / float(len(kset | chunk_tokens))


async def retrieve_context(
    *, tenant_id: str, question: str, top_k: int = 3, min_score: float = 0.05,
) -> Dict:
    """Public entry point. Returns:
        {
          "matched": bool,
          "context": "<rendered prompt block ready to prepend>",
          "chunks": [{"text","score"}, ...],
          "keywords": [...]
        }
    """
    chunks = _profile_chunks(tenant_id)
    if not chunks:
        return {"matched": False, "context": "", "chunks": [], "keywords": [], "reason": "empty_kb"}

    keywords = await _extract_keywords(question, tenant_id)
    scored = sorted(
        ({"text": c, "score": _score(keywords, c)} for c in chunks),
        key=lambda x: x["score"],
        reverse=True,
    )[:top_k]
    best = scored[0]["score"] if scored else 0.0
    matched = best >= min_score

    if not matched:
        return {
            "matched": False, "context": "", "chunks": scored,
            "keywords": keywords, "reason": "no_match",
        }

    context_block = (
        "KNOWLEDGE BASE CONTEXT (use to ground your answer; cite specifics):\n"
        + "\n---\n".join(f"[KB#{i+1}] {c['text']}" for i, c in enumerate(scored) if c["score"] > 0)
    )
    return {
        "matched": True,
        "context": context_block,
        "chunks": scored,
        "keywords": keywords,
        "reason": "ok",
    }


def notify_owner_missing_kb(tenant_id: str, question: str) -> None:
    """Log a no-match event so the workspace owner can be nudged to expand
    the KB. We use a dedicated collection so the Notifications bell can
    surface it later."""
    try:
        db["kb_missing_log"].insert_one({
            "tenant_id": tenant_id,
            "question": (question or "")[:600],
            "created_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
            "status": "open",
        })
    except Exception:
        logger.exception("kb_rag: failed to write kb_missing_log")


__all__ = ["retrieve_context", "notify_owner_missing_kb"]
