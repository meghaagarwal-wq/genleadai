"""iter90 — lightweight ICP scoring for newly-imported leads.

Used by the Lemlist + Saleshandy pull endpoints (and any future bulk
imports) to set `stage` (cold/warm/hot) and `score` (0-100) on each lead
*before* it lands in `pt_leads`. The goal is to give the founder an
immediately-prioritised list instead of a sea of zeros.

Two levels of intelligence, picked at runtime:
  1. **Aria (Claude)** — when EMERGENT_LLM_KEY is set and the lead has
     enough metadata (email + title + company), we send a tight prompt
     asking for {score, tier, why}. Fast (Haiku) and bounded.
  2. **Heuristic** — fallback when no LLM is available or the lead is
     metadata-thin. Uses the persona keywords + engagement signals.

`score_lead()` is sync-fast: 1 LLM call per lead, no retries beyond the
SDK default.
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, Optional, Tuple


# ────────────────────────────────────────────────────────────────────────
# Pietential's ICP — strong match on HR leadership roles.
# Future: make this read from `tenant.settings.icp_keywords` so each
# workspace gets its own persona match without code edits.
# ────────────────────────────────────────────────────────────────────────
_HOT_TITLE_PATTERNS = [
    r"\bchro\b", r"chief\s+(human|people)\s+resources?\s+officer",
    r"\bvp\s+(of\s+)?(hr|human\s+resources|people)",
    r"\bsvp\s+(of\s+)?(hr|human\s+resources|people)",
    r"\bhead\s+of\s+(hr|people|talent|culture)",
    r"\bchief\s+people\s+officer\b",
]
_WARM_TITLE_PATTERNS = [
    r"\bdirector\s+(of\s+)?(hr|human\s+resources|people|talent|culture)",
    r"\bsenior\s+(director|manager)\s+(of\s+)?(hr|people|talent)",
    r"\bhr\s+(director|manager|leader|business\s+partner)",
    r"\bpeople\s+ops?\s+(director|manager|leader)",
    r"\btalent\s+(director|acquisition\s+leader)",
]


def _title_score(title: str) -> Tuple[int, str]:
    """Returns (score, tier) based on title heuristic alone."""
    t = (title or "").lower()
    if not t:
        return 35, "cold"
    for p in _HOT_TITLE_PATTERNS:
        if re.search(p, t):
            return 78, "hot"
    for p in _WARM_TITLE_PATTERNS:
        if re.search(p, t):
            return 58, "warm"
    return 35, "cold"


def _engagement_bonus(lead: Dict[str, Any]) -> int:
    """Add bonus points for explicit engagement signals from the source."""
    bonus = 0
    raw = lead.get("_lemlist_raw") or {}
    state = (raw.get("lead_state") or raw.get("state") or "").lower()
    if "opened" in state:
        bonus += 8
    if "clicked" in state or "replied" in state:
        bonus += 15
    if "unsubscribed" in state or "bounced" in state:
        bonus -= 25  # not a fit / unreachable
    return bonus


def heuristic_score(lead: Dict[str, Any]) -> Dict[str, Any]:
    """Fast, no-LLM scoring. Always returns a result."""
    title = lead.get("title") or ""
    score, tier = _title_score(title)
    score = max(0, min(100, score + _engagement_bonus(lead)))
    # Demote slightly if no company or no industry
    if not lead.get("company_name"):
        score = max(0, score - 5)
    if score >= 70:
        tier = "hot"
    elif score >= 45:
        tier = "warm"
    else:
        tier = "cold"
    return {
        "score": score,
        "stage": tier,
        "why": f"Heuristic match on title='{title or '(none)'}' + source engagement.",
        "source": "heuristic",
    }


async def score_lead_with_aria(lead: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """LLM-based scoring via the Emergent LLM key (Claude Haiku).

    Returns None if no LLM key, the lead lacks fields to reason about, or
    the API call fails. The caller falls back to `heuristic_score`.
    """
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        return None
    email = lead.get("email") or ""
    title = lead.get("title") or ""
    company = lead.get("company_name") or ""
    if not email or not (title or company):
        return None
    try:
        # Lazy import — emergentintegrations is optional at module load time.
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=api_key,
            session_id=f"score-{lead.get('id') or email}",
            system_message=(
                "You are Aria, Pietential's lead-scoring engine. Pietential sells AI-powered "
                "growth + employee-experience automation to mid-market HR leaders. The ICP is "
                "CHROs, VPs of HR/People, Directors of HR or Talent at 50–2000-employee companies. "
                "Return ONLY a JSON object: {score: int 0-100, tier: 'hot'|'warm'|'cold', why: short reason}."
            ),
        ).with_model("anthropic", "claude-haiku-4-5")
        msg = UserMessage(text=(
            f"Lead:\n  email: {email}\n  title: {title}\n  company: {company}\n"
            f"  industry: {lead.get('industry') or '—'}\n  country: {lead.get('geography') or '—'}\n"
            f"  engagement: {(lead.get('_lemlist_raw') or {}).get('lead_state') or '—'}\n"
            "Score 0-100 (hot ≥ 70, warm 45-69, cold < 45). Return JSON only."
        ))
        resp = await chat.send_message(msg)
        text = (resp or "").strip()
        # Strip code fences
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
        import json as _json
        data = _json.loads(text)
        score = int(data.get("score") or 0)
        score = max(0, min(100, score))
        tier_raw = (data.get("tier") or "").lower().strip()
        tier = tier_raw if tier_raw in ("hot", "warm", "cold") else (
            "hot" if score >= 70 else "warm" if score >= 45 else "cold"
        )
        return {
            "score": score,
            "stage": tier,
            "why": (data.get("why") or "")[:200],
            "source": "aria",
        }
    except Exception:
        return None


async def score_lead(lead: Dict[str, Any], use_aria: bool = True) -> Dict[str, Any]:
    """Score a single lead. Prefers Aria; falls back to heuristic."""
    if use_aria:
        result = await score_lead_with_aria(lead)
        if result:
            return result
    return heuristic_score(lead)
