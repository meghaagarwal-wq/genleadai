#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────
# V10 architectural rule guard — Batch 3 (Claude Deep Integration).
#
# Fails the commit / CI run if any file under /app/backend reintroduces
# a direct Claude SDK call OUTSIDE the centralised wrapper at
# `services/claude_service.py`.
#
# Rule recap
# ──────────
#   • All Claude traffic MUST route through `claude_call(task_type=…)`
#     in `services/claude_service.py`.
#   • Any direct `LlmChat(...)`, `with_model(...)`, `UserMessage(...)`,
#     `emergentintegrations.llm.chat`, or `anthropic.messages.create`
#     usage elsewhere is a regression — block it.
#
# Usage
# ─────
#   • Manual / CI:   bash scripts/check_v10.sh
#   • Pre-commit:    ln -s ../../scripts/check_v10.sh .git/hooks/pre-commit
#                    chmod +x .git/hooks/pre-commit
# ─────────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="${REPO_ROOT:-/app}"
TARGET_DIR="${TARGET_DIR:-${ROOT}/backend}"
PATTERN='LlmChat\(|with_model\(|emergentintegrations\.llm\.chat|anthropic\.messages\.create|UserMessage\('

# Build the grep
if command -v rg >/dev/null 2>&1; then
  HITS=$(rg -n -e "${PATTERN}" "${TARGET_DIR}" -g '*.py' \
           -g '!**/__pycache__/**' \
           -g '!**/tests/**' \
           -g '!**/services/claude_service.py' || true)
else
  # GNU grep fallback. Note: grep -E does NOT understand --include with \( in
  # an env var on some platforms, so we run the pattern via stdin.
  HITS=$(find "${TARGET_DIR}" -type f -name '*.py' \
           ! -path '*/__pycache__/*' \
           ! -path '*/tests/*' \
           ! -name 'claude_service.py' \
           -print0 \
         | xargs -0 grep -nE "${PATTERN}" || true)
fi

if [[ -n "${HITS}" ]]; then
  echo "──────────────────────────────────────────────────────────────────────"
  echo "🚫 V10 architectural rule violation"
  echo ""
  echo "Direct Claude SDK calls found OUTSIDE services/claude_service.py."
  echo "All Claude traffic must route through services.claude_service.claude_call()."
  echo ""
  echo "Offending lines:"
  echo "${HITS}"
  echo ""
  echo "Fix: import from services.claude_service and use claude_call(task_type=…)."
  echo "──────────────────────────────────────────────────────────────────────"
  exit 1
fi

echo "✅ V10 OK — no direct LlmChat / with_model / anthropic.messages outside the wrapper."
