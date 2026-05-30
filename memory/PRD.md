## Iter 137 — P1 Fixes from iter136 Audit (Mar 1, 2026)

Surgical fix-batch for the 3 P1 bugs surfaced in the iter136 full backend
audit. All verified live + by testing agent (12/12 iter137 PASS +
36/36 sprint regression PASS).

### Fixes
1. **`POST /api/aria/eod-wrap/send-now`** — was leaking uncaught
   `resend.exceptions.ResendError` as a 500 traceback. Added
   `_classify_send_error()` helper in `routes/aria_eod_wrap.py` that
   regex-matches Resend sandbox/unverified-domain errors and returns a
   structured **503** with `{code, user_message, status}`. Belt-and-
   suspenders outer try/except around `_send_eod_wrap` guards against
   any rogue exception escaping the inner SDK call.
2. **`GET /api/aria/eod-wrap/last`** — new endpoint added for UI parity
   with `/api/aria/morning-brief/last` and `/api/aria/approval-digest/last`.
   Returns `{last_sent_at, last_sent_date, last_sent_touches,
   last_sent_manual}` from the eod_wrap_settings doc.
3. **`POST /api/journey/generate`** — was timing out at the 60s ingress
   ceiling on synchronous multi-step Claude calls. Converted to async
   job pattern:
   - Kickoff returns `{job_id, status:'queued', eta_seconds, hint}` in
     <0.2s.
   - `asyncio.create_task` runs `_run_generate_job` in background,
     writing progress to a new `journey_generate_jobs` collection.
   - New `GET /api/journey/generate/job/{job_id}` returns
     `{status, phase, elapsed_seconds, slow_warn, result|error}` —
     phases: `queued → building_prompt → claude_generating → persisting → done`.
   - Tenant isolation enforced via compound `{job_id, tenant_id}` lookup.
   - `frontend/src/workspace/pages/TouchpointMap.js` updated to poll
     every 2.5s for up to 5 min.

### Verification
- Live curl: send-now → 503 with `code='resend_sandbox_or_unverified_domain'`;
  /last → 200 with correct shape; /generate → 0.16s kickoff;
  job completes in ~20s with 3 real Claude touchpoints.
- testing_agent_v3_fork iteration_137: 12/12 PASS · 36/36 sprint
  regression PASS · V10 guard exit 0 · frontend zero pageerrors.

### Files changed
- `/app/backend/routes/aria_eod_wrap.py` (helper + wrapped route + /last)
- `/app/backend/routes/journey.py` (async-job rewrite of /generate +
  new /generate/job/{job_id})
- `/app/frontend/src/workspace/pages/TouchpointMap.js` (poll loop)
- `/app/backend/tests/test_iter137_p1_fixes.py` (new)

### Status
**READY TO REDEPLOY** to `app.genleadai.com`.

### Carry-over backlog (cosmetic, non-blocking)
- Port `_classify_send_error` helper to `aria_morning_brief.py` +
  `aria_approval_digest.py` so they don't spam tracebacks in
  backend.err.log when Resend rejects sandbox sends.
- Add TTL index on `journey_generate_jobs.created_at` (7d) so jobs
  don't accumulate forever.

---


## Iter 136 — Full Backend Audit (Mar 1, 2026)

User-triggered after hitting "Send failed" on production Morning Brief.
Exhaustive audit on 130+ endpoints across 30 categories surfaced:
- **3 P1 bugs** (fixed in iter137): eod-wrap/send-now 500 leak,
  eod-wrap/last missing, journey/generate 60s timeout.
- **6 OAuth providers** + **1 Intel research** degrade cleanly with 503
  (missing keys — expected on preview).
- **V10 guard PASS** · `_id` leak guard PASS · tenant isolation PASS.
- Confirmed production root cause: Resend sandbox mode only allows
  sending to the verified Resend owner email until a domain is verified
  at resend.com/domains.

---


## Iter 135 — Pre-Deploy Full Regression (Mar 1, 2026)

**Trigger:** User asked: "Run the full regression first. Then deploy. Then I'll do the production walkthrough."

### What was verified
Full unified regression on the iter125–iter134 sprint surface:
- **V10 architectural guard PASS** — `scripts/check_v10.sh` exit 0. Zero direct
  Anthropic calls outside `services/claude_service.py`. Hard invariant holds.
- **All 8 sprint pytest suites PASS individually — 36/36 tests green:**
  `test_iter125_refactor_and_drag`, `test_iter126_lead360_and_csv`,
  `test_iter127_scan_hot`, `test_iter128_reply_box`,
  `test_iter129_draft_with_aria`, `test_iter130_draft_variants`,
  `test_iter131_voice_training`, `test_iter134_scan_progress`.
- **Live HTTP smoke** on REACT_APP_BACKEND_URL: auth, tenants/me, leads,
  leads/counts (with embedded pipeline_snapshot), leads/{id}/activities,
  conversations/lead/{id}, conversations/lead/{id}/draft (per-attempt
  contract), voice-seeds CRUD, intel/scan-hot, intel/scan-progress,
  journey/touchpoints/reorder, approvals — all 200 (where applicable).
- **Frontend smoke 100% PASS** — login, sidebar lead-strip + chips render
  with live counts, `/app/leads`, `/app/leads/{id}` (Lead 360 5 tabs),
  `/app/voice-training`, `/app/touchpoints` (drag-and-drop), zero JS
  pageerrors.
- **MongoDB `_id` leak guard** — spot-checked /api/leads, /api/voice-seeds,
  /api/conversations/lead/{id}, /api/intel/{id}/profile, /api/approvals
  — no `_id` leaked.
- **Tenant isolation** — voice-seeds + conversations correctly scoped;
  cross-tenant returns 404, not data leak.

### Findings (all non-blocking)
- **False alarm**: testing-agent flagged `GET /api/activities?lead_id=…`
  as 405. Lead 360 actually uses the existing
  `GET /api/leads/{id}/activities` endpoint, which works (200, list).
- Bulk `pytest test_iter125..134` in one invocation has fixture
  contamination (per-file runs all pass). P3 cleanup.
- `/api/leads/pipeline-snapshot` doesn't exist as a standalone endpoint —
  data is embedded in `/api/leads/counts.pipeline_snapshot` (frontend uses
  the embedded shape). Working as designed.
- Onboarding "Welcome to ARIA" modal overlays first-login pages until
  dismissed — pre-existing UX, not a regression.

### Deployment readiness
- `.env` clean (MONGO_URL, DB_NAME, REACT_APP_BACKEND_URL untouched).
- CORS includes `https://app.genleadai.com`.
- `PUBLIC_API_BASE_URL=https://app.genleadai.com` set → OAuth callbacks
  resolve correctly on production.
- All new modular routes (journey, conversations, intel, voice_seeds)
  registered via `routes/__init__.py` and import cleanly on cold start.
- Supervisor: backend + frontend + mongodb all RUNNING.
- **Verdict: ✅ GREEN LIGHT TO DEPLOY**

### Post-deploy reminder for user
Production keys do NOT sync from Preview. After deploy, re-paste:
- RapidAPI / Proxycurl key (for live LinkedIn crawl)
- Serper key (for web/news/IG/FB search)
- Resend domain key (for outbound email dispatch)
…via Production `/app/integrations` UI.

Then run the 10-point production walkthrough manually on
`https://app.genleadai.com`.

### Backlog (P2/P3 carried forward)
- P2: Embedding-based RAG upgrade (blocked — Emergent universal proxy
  key does not expose embedding models). User deferred.
- P3: LinkedIn Sales Navigator integration.
- P3: Cleanup legacy flake8 errors in
  `/app/backend/aria_agent_routes/brain.py`.
- P3: Further `server.py` thinning (still ~2,380 lines).
- P3: Make sprint pytest suites isolatable for bulk runs.

---


## Iter 134 — Scan Progress Toast (Feb 2026)

Persistent toast at the bottom of the screen showing live progress of
the "Scan all hot leads" batch action (per-lead status, X/Y processed,
auto-dismiss on completion).

### What shipped
- Backend: `scan_progress` collection keyed by `(tenant_id, batch_id)`
  written incrementally by `routes/intel.py` scan-hot loop.
- `GET /api/intel/scan-progress` returns latest in-flight or last-finished
  batch progress for the tenant.
- Frontend `ScanProgressToast.js` polls every 2s while batch is active,
  shows per-lead PASS/FAIL chips, total counts, ETA.
- Verified: 5-lead scan ran end-to-end with toast updating live, then
  auto-dismissed 3s after completion.

---


## Iter 133 — Embedding RAG (DEFERRED)

Discovered the Emergent universal LLM proxy key does NOT expose embedding
models (`text-embedding-3-large` etc). Iteration paused with user consent.
Current keyword-based RAG retrieval (Jaccard scoring) remains in
`services/kb_rag_service.py` and is sufficient for the founder demo.

---


## Iter 132 — Voice Training Auto-Learn (Feb 2026)

When a founder edits an ARIA-drafted message before sending, the edited
final body is appended to `voice_seeds` (channel='email' or 'whatsapp')
with `auto_learned=true`. Subsequent drafts inject up to 5 most-recent
auto-learned seeds + all manual seeds into the Claude system prompt for
tone matching.

### What shipped
- `routes/conversations.py` `_record_voice_seed_from_edit()` helper
  fires on the send endpoint when `edited_body != original_body`.
- `services/intel_service.py compose_message` now ALWAYS calls
  `_load_voice_seeds(tenant_id, channel)` and injects them.
- Voice Training UI shows two sections: "Manual seeds" + "Auto-learned
  from your edits" with delete buttons.
- Verified: edit-send → seed appears → next draft matches the edit's
  tone in human eval.

---


## Iter 131 — Voice Training Page (Feb 2026)

CRUD page for founder to seed ARIA's voice manually before sending any
real outreach. Persists examples per channel + active toggle.

### What shipped
- Collection `voice_seeds`: `{id, tenant_id, channel, label, seed_text,
  is_active, auto_learned, created_at, created_by}`.
- `routes/voice_seeds.py` — list/create/update/delete with tenant scope.
- Frontend `VoiceTraining.js` — channel tabs (email/whatsapp/linkedin),
  add-seed form, list with toggle/delete, helper card explaining how
  seeds are used.
- Wired into `services/intel_service.compose_message` — active seeds for
  the requested channel are prepended to the system prompt under a
  `<voice_examples>` block.

---


## Iter 130 — Draft Variants (Feb 2026)

`POST /api/conversations/lead/{id}/draft` now accepts an `attempt` param
(1..3) and returns one variant per request, each with a different "angle"
(direct / curious / value-first). Frontend ConversationThread.js fires
3 parallel requests and shows them in a tabbed picker.

---


## Iter 129 — Draft with ARIA (Feb 2026)

New `Draft with ARIA` button in the conversation thread reply box. Pulls
intel profile + voice seeds + last 5 thread messages + suggested
next_action_hint and calls `claude_service.claude_call` (CONVERSATION
task) to produce a contextual reply. Returns `{subject, body, attempt}`.

---


## Iter 128 — Conversation Thread Keyboard Shortcuts + Reply Box (Feb 2026)

- `j/k` next/prev message, `Home/End/G` jumps, `/` focus filter, `Esc`
  clear+blur.
- New inline reply box at the bottom of the thread with channel selector
  (email/whatsapp/linkedin) and Send button. Calls
  `POST /api/conversations/lead/{id}/send`.
- Hint bar at the bottom explains shortcuts.

---


## Iter 127 — Scan All Hot Leads (Feb 2026)

New "Scan all hot leads" button on Lead Inbox. Posts to
`/api/intel/scan-hot` which iterates `pt_leads` where
`stage='hot' AND no intel_profile (or intel older than 30d) AND score >=
threshold`. Runs `crawl_prospect` + `synthesise_intel` per lead with
per-lead try/except, writes scan_progress doc. Returns `{queued,
leads[], threshold, batch_id, message}`.

---


## Iter 126 — Lead 360 + CSV Import (Feb 2026)

5-tab Lead 360 view at `/app/leads/{id}`:
1. **Overview** — name, company, score, stage, last contacted, owner,
   inline edit.
2. **Intel** — embeds IntelTab (signals, fit, playbook, composer).
3. **Automation** — touchpoint enrolment + queued outreach status.
4. **Conversations** — embeds ConversationThread.
5. **Activity** — chronological event timeline (uses
   /api/leads/{id}/activities).

Also: CSV Import button on Lead Inbox with field-mapping wizard.

---


## Iter 125 — server.py Refactor + Touchpoint Drag-and-Drop (Feb 2026)

- `server.py` reduced significantly via extraction of
  `routes/founder_command_center.py`, `routes/public_api.py`, and
  similar per-domain modules.
- Touchpoint Journey step cards now reorderable via native HTML5
  drag-and-drop in addition to the existing ↑/↓ buttons. Order persisted
  via `POST /api/journey/touchpoints/reorder`.
- Sidebar Lead Count strip + Pipeline Snapshot row added to AppLayout.

---


## Iter 124 — CLOSE IT OUT (Feb 28, 2026)

Massive sweep closing the highest-priority gaps from the May 28 audit.
Triggered by the user's "execute everything in one continuous run" prompt.

### 1. 32-Touchpoint Journey — Full Builder Rebuild
- `TouchpointMap.js` rebuilt end-to-end (the previous 64-line grid is gone).
- **4 views**: Flowchart (vertical chain with branch-edge labels),
  Timeline (vertical day-axis), Pipeline (kanban per channel), Conditional
  (editable branching-rule list).
- **Generate Journey with AI**: `claude-sonnet-4-5` produces an N-step
  sequence from the workspace training profile.
- **Per-touchpoint Regenerate** with surrounding context.
- **Inline edit** every field with dirty-state Save button.
- **Drag-style reorder** via ↑/↓ buttons (POST /api/journey/touchpoints/reorder).
- Backend: `routes/journey.py` — CRUD + generate + per-tp regenerate.

### 2. Prompt-injection Sanitiser — Wired across lead-sourced paths
### 3. Knowledge-base RAG at Query Time
### 4. Instagram + Facebook Crawl
### 5. Real-time API-key Validation (onBlur)
### 6. Conversation Thread — already shipped iter121, re-verified
### 7. Auto-approve Rule — already shipped iter121

(Full history of iter1–iter123 retained in git log + CHANGELOG.md.)
