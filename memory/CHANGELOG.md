# ARIA / GenLeadAI — Changelog


## 2026-02 — Iter 86 (Setup health + multi-attach + workspace identity in lead-magnet sends)
- **New `GET /api/pt/setup/health`** — 5-bullet workspace completeness check
  (email sender, Saleshandy, Lemlist, lead magnet, touchpoints) with
  status/detail/CTA per item + `live` flag (true when ≥3 ok). Surfaced as a
  banner on Pietential Overview.
- **Multi-attachment** on `/api/pt/email/test-send`: `attachment_file_ids:
  List[str]` added. Merges + dedupes the single + list inputs preserving
  order. Missing files silently dropped (no 404/500).
- **Workspace identity in lead-magnet sends**: `_send_lead_magnet_via_email`
  now routes through `send_workspace_email` — from-name / from-address /
  signature all apply to auto-sent magnets. File-type magnets are now
  attached inline (base64) instead of just linked.
- **Tests**: 17/17 backend pass, zero issues. 3 real Resend test sends +
  1 real lead-magnet manual send all confirmed provider_id.



## 2026-02 — Iter 85 (Email signatures + lead-magnet attachments + auto-handshake)
- **New shared helper `routes/pt_email.py`**: `send_workspace_email()`
  resolves workspace from-name/from-address/Resend-key/signature in one
  place, with a concurrent-safe key swap. `_resolve_attachment` includes
  a path-traversal guard (verified live).
- **Per-workspace HTML signature**: new `signature_html` field on
  `pt_integrations.email`. Auto-appended to every send (styled `<div>`
  with top-border divider). Founder can clear by passing empty string.
- **Lead-magnet attachments on test send**: PDF/PPTX from
  `/api/lead-magnets/upload` (existing endpoint) can be attached to test
  sends via `attachment_file_id`. Resend `attachments[]` carries the file
  base64-encoded. Path-traversal silently dropped. Nonexistent file silently
  dropped (send still succeeds).
- **Auto-handshake on save**: `POST /api/pt/email/config` now returns a
  `handshake` object (`{ok, message, domains[]}`) from a live Resend
  `GET /domains` ping. Detects auth failures across HTTP 400/401/403 with
  body substring matching (Resend returns 400 for invalid keys).
- **FE Settings UI**: signature textarea + attachment picker + handshake
  status panel. Existing test-send button stays.
- **Tests**: 31/31 backend pass + 1 skip (env-bound) across iter84+iter85.
  5+ real Resend sends confirmed (provider_id returned).



## 2026-02 — Iter 84 (Pietential email-send flow + AI Setup nav)
- **Per-workspace email sender config**: 3 new endpoints on the Pietential
  router — `GET /api/pt/email/config`, `POST /api/pt/email/config`,
  `POST /api/pt/email/test-send`. From-name / from-address persisted to
  `pt_integrations` (name='email'); Resend API key encrypted via Fernet.
  Falls back to platform `RESEND_API_KEY` + `SENDER_EMAIL` until a workspace
  key is set.
- **Real Resend test send**: workspace-admin clicks "Send test email", we
  hit Resend's API for real, return `provider_id` on success and friendly
  errors (sandbox / unverified domain / bad key) on failure.
- **New role gate `_can_admin_workspace`**: admin / master_admin / owner /
  pietential_owner only. sales_rep + content_vista are deliberately blocked
  from rotating Resend keys or triggering outbound test emails.
- **AI Setup nav** added to Pietential sidebar → links to existing
  `/ai-setup` (AISetupAssistant) so the GTM doc → touchpoints flow is one
  click from the dashboard.
- **PtSettings rebuilt** with Email Sender card on top featuring inputs +
  test-send sub-row. Shows USING PLATFORM DEFAULT vs WORKSPACE KEY chip.
- **Tests**: 15/16 pass + 1 skip (env-var process-bound). 1 real Resend
  call confirmed `provider_id` returned for account-owner inbox.



## 2026-02 — Iter 82–83 (Bug fixes from user screenshots + Pietential wiring)
- **AI Setup publish robustness**: `/api/aria/auto-map/publish` wrapped with
  catch-all so unexpected 500s become structured detail; per-touchpoint
  Pydantic failures drop individually instead of failing the whole publish.
- **Friendly provider errors**: Saleshandy returns its auth failures as 400s
  with `{"type":"auth","code":1001,"message":"Invalid token"}` JSON. We now
  detect that pattern inside both `routes/outreach_import._saleshandy_list_sequences`
  AND `integrations_routes.SalesHandyClient._req`, and emit:
  > "Saleshandy rejected the API key. Double-check you copied the FULL key
  > from Saleshandy → Settings → API and that it hasn't been revoked."
  Lemlist gets symmetric treatment for 401/403.
- **SalesHandyClient SDK drift fixed**: switched from deprecated
  `POST /v1/sequences/get-list` (404 since Saleshandy migrated) to canonical
  `GET /v1/sequences`. Eliminates a raw-JSON leak path.
- **Pietential write access**: `_can_write` + `_is_admin` now include
  `master_admin` and `owner` so GenLeadAI operators can manage every client
  workspace (was a 403 blocker on POST `/api/pt/integrations` and the
  `/test` endpoint).
- **Pietential test integration is now real**: `POST /api/pt/integrations/{name}/test`
  does a live Saleshandy/Lemlist API handshake (via lazy import of the
  outreach_import helpers). Failures set `pt_integrations.status = needs_setup`
  with `error_log` so the FE can prompt reconnect.
- **SaaS UI cleanup**:
  • Removed `CURRENT PLAN / ARIA Starter / UPGRADE` block from main sidebar.
  • Removed all `BETA` badges (Pietential dashboard, login, public layout,
    Aria Command Room).
- **Tests**: 27/27 backend pass (18 iter82 + 9 iter83 acceptance).



## 2026-02 — Iter 81 (S10 Regression Sweep + 400→404 ObjectId consistency)
- **400 → 404 consistency** on six endpoints that previously returned 400 for
  invalid ObjectId format. They now uniformly return `404 Lead not found`:
  • `POST /api/aria-agent/founder-brief/{lead_id}`
  • `GET  /api/aria-agent/aria-read/{lead_id}`
  • `POST /api/aria-agent/workspace/ask-reply/{lead_id}`
  • `GET  /api/aria-agent/workspace/story-card/{lead_id}`
  • `POST /api/leads/{lead_id}/send-lead-magnet`
  • `GET  /api/aria/best-time-to-call/{lead_id}`
  Matches the existing `DELETE /api/leads/{lead_id}` pattern (already 404) so
  attackers can't probe id-format vs id-existence.
- **S10 full regression sweep**: 72/72 backend tests PASS (27 new S10 + 28
  prior iter78/79 + 17 iter80 S9.5 smoke). Zero regressions across all 11
  transformation sections (S1–S9.5).
- **Canonical paths captured** in PRD (corrects two iter80 doc misalignments):
  ICP create is `/api/icps/create` with `label` field; weekly recap PDF is
  `/api/aria-agent/weekly-recap/export.pdf`. Touchpoint pipeline 5-stage
  Kanban renders FE-side from `day` attribute on `/api/touchpoints/map`.



## 2026-02 — Iter 80 (S9.5 Security Sweep COMPLETE)
- **Rate limiting via slowapi** — completed wiring across all sensitive endpoints:
  • `POST /api/auth/login` — 10/min per IP (already shipped in iter79)
  • `POST /api/aria-agent/founder-brief/{lead_id}` — 10/min (LLM-heavy)
  • `GET  /api/aria-agent/aria-read/{lead_id}` — 20/min
  • `POST /api/aria-agent/workspace/ask-reply/{lead_id}` — 30/min
  • All return `429 Too Many Requests` after the threshold; verified via the
    testing agent against the k8s preview URL.
- **`security/limiter.py` hardened**:
  • Custom `_client_key` reads `X-Forwarded-For` so the *actual* client IP is
    rate-limited through the k8s ingress (the default `get_remote_address`
    returns the proxy IP, which collapses every user into one bucket).
  • Switched `headers_enabled=True → False` to bypass slowapi's
    response-header injection (it raises when endpoints return a `dict` rather
    than a `Response`, which was a 500 regression on the new limits).
- **Prompt-injection sanitiser (`security/helpers.py`)**:
  • Expanded `_INJECTION_PATTERNS` to catch `<system>/<assistant>/<user>` tags
    AND any of `ignore|disregard|forget … (all|the|your|previous|prior|earlier|above)? (instructions|prompts|directives|rules|context)`.
  • Applied to `ask-reply` user_note and to lead-metadata fields in
    `founder-brief` (notes/need/pain/objection).
- **NoSQL-injection guards**:
  • `/api/broadcasts` + `/api/broadcasts/preview` — wrap user-controlled
    `request.filters` with `safe_filter_value()` so any `$where / $ne / $regex`
    operator keys are stripped before being merged into the Mongo query.
  • `/api/leads?search=…` + `/api/conversations/threads?search=…` — wrap with
    `safe_query_param()` + `re.escape()` so regex meta-chars can't trigger
    ReDoS or smuggle Mongo operators.
- **Fernet encryption** (existing in iter79) verified end-to-end via unit
  tests — idempotent encrypt, graceful decrypt of legacy plaintext, masked
  display via `mask_key()`.
- **Tests**:
  • New `/app/backend/tests/test_iter80_s95_security.py` — 13 unit tests
    covering sanitiser, NoSQL guard, encryption.
  • Testing agent added `/app/backend/tests/test_iter80_s95_integration.py`
    — 20 integration tests against the live preview URL.
  • **Result: 67/67 backend tests PASS** (33 S9.5 + 34 prior regression).
- Known minor (non-exploitable, REST consistency only): invalid-ObjectId on
  `/founder-brief/{id}` and `/aria-read/{id}` returns 400 instead of 404. Matches
  the iter78 note for `DELETE /api/leads/{id}`. Tracked, not blocking.


## 2026-02 — Iter 79 (S8 + S6 enhancement + S4 enhancement + S9.5 focused slice)
- **S8 — Master Admin Deployments tab** *(largest item in this iter)*:
  • New `/api/admin/deployments` router with `GET /` (rollup + grid),
    `GET /{tenant_id}` (single, masked API keys), `POST /{tenant_id}/toggle`
    (pause/resume + audit log), `POST /onboard` (4-step wizard launches a
    tenant + ICP + default 3-step touchpoint map), `GET /_/sidebar-status`
    (cheap per-tenant status indicator).
  • Status logic: **LIVE** when ≥1 channel + ≥1 ICP + ≥1 touchpoint;
    **PAUSED** when the operator hit pause; otherwise **SETUP**.
  • New `MasterAdmin → Deployments` tab (default tab) with rollup tiles,
    cards (status chip, channel chips, leads/touchpoints/last-activity,
    Pause / Manage), and a new `OnboardingWizard` modal.
  • Sidebar — new `AriaStatusIndicator` shows live status under the
    ARIA logo on every page (green/amber/red pulsing dot + popover with
    leads_today, touchpoints_today, last activity, and a master-admin-only
    pause toggle).
  • Seed data: `admin@demo.com` promoted to `master_admin` role.
- **S4 enhancement — drag-drop across pipeline stages**: every
  `PipelineCard` is now HTML5-draggable; each `pipeline-stage-*` column
  is a drop target. Dropping a card resnaps its `day` to the middle of
  the target stage's range, sorts the journey, and follows selection.
- **S6 enhancement — Suggested Asset widget**: new
  `GET /api/aria-agent/suggested-assets/{lead_id}?q=...` returns up to 3
  workspace assets keyword-matched to the lead's last inbound message.
  New `SuggestedAssetWidget` rendered under `AriaReadPanel` on Lead
  Detail. Each match surfaces the trigger keyword so founders see *why*
  Aria leans on that asset.
- **S9.5 focused — safe validation errors**: new
  `RequestValidationError` handler returns a single human-readable
  string instead of the Pydantic error array, eliminating the leak of
  field types / model structure to the frontend.
- **Tests**: `test_iter79_managed_deployment.py` (8 tests) covering
  S8 happy path + cross-tenant + S6 endpoint + S9.5 safe-error shape.
  Full regression: 54/54 backend tests passing including iter73 / iter74
  / iter78 suites.

## 2026-02 — Iter 78 (S2 + S3 + S5 + S6 + S4 + S9.5 focused slice)
- **S2 — Lead + Conversation cascade delete**: `DELETE /api/leads/{id}`
  now hard-cascades activities, conversations, touchpoint_logs,
  classification_logs (all tenant-scoped). New `POST /api/leads/bulk-delete`
  for batch delete. New `DELETE /api/conversations/{lead_id}` removes the
  Aria thread without touching the lead. All three are owner/admin only
  and write to audit_log. Lead Inbox UI gained a `Delete selected` bulk
  button (`data-testid='bulk-delete-btn'`).
- **S3 — ICP ↔ Campaign linking**: new `POST /api/icps/{icp_id}/link-campaign`
  sets `icp.icp_campaign_id` AND mirrors `campaign.linked_icp_id` (clears
  the old reverse link on rebinds). `IcpCreate` / `IcpUpdate` accept the
  new field. ICPManager UI shows a green "Linked: <campaign>" chip on
  each card + `Link a campaign` button → modal w/ campaign dropdown.
- **S5 — Train Aria ← AI Setup merge**: new
  `POST /api/aria-agent/training/import-from-automap` pulls
  `tenants.settings.automap_summary` and fills BLANK Train Aria fields
  only — never clobbers founder-supplied answers. 404 with
  `no_automap_summary` when nothing has been published yet.
- **S6 — Playbook + assets injection into Claude**: playbook activation
  now (a) single-active-per-tenant semantics, (b) mirrors onto
  `tenant.settings.active_playbook`. New `_shared.get_active_playbook_block()`
  + `get_relevant_assets_block()` helpers inject the playbook + matching
  objection/pricing/case-study assets into every Aria conversational
  Claude system prompt (`founder-brief`, `workspace/ask-reply`).
- **S4 — Touchpoint Pipeline view (5 stages)**: new
  `JourneyPipelineView` swimlane component (First Contact 1-4 / Education
  5-10 / Nurture 11-18 / Conversion 19-26 / Revival 27-32). Now the
  default `/touchpoint-journey` rendering. Timeline + Flowchart remain
  via 3-way toggle. `Add to <stage>` buttons drop a new touchpoint
  pre-anchored to that stage's day range.
- **S9.5 focused slice — audit_log everywhere**: `audit_write()` called
  on `lead.delete`, `lead.bulk_delete`, `conversation.delete`,
  `playbook.activate`, `playbook.deactivate`. Owner/admin role gating
  added on all destructive endpoints (`403 forbidden` for non-owners).
  Invalid-ObjectId on lead delete now returns 404 (was 400) to avoid
  cross-tenant existence probes.
- **Tests**: new `test_iter78_managed_deployment.py` (12 tests) +
  `test_iter78_supplemental.py` (9 tests covering audit_log + cross-
  tenant safety + `get_active_playbook_block()`). 70/70 backend tests
  passing including iter52/iter73/iter74 regression.

## 2026-02 — Iter 77 (Quick-win subset of the 11-section managed-deployment spec)
- **S1 — Tutorials + Billing UI removal**: `/tutorials` route + sidebar
  nav item removed; `TrialBanner` ripped out of `Layout.js`; BETA badge
  removed from desktop + mobile sidebar headers.
- **S3 partial — ICP cap removal**: `ICP_LIMIT_BY_PLAN` + `_icp_limit()` +
  `_icp_count()` helpers deleted from `routes/icps.py`; `POST /create` no
  longer 403s on tier cap; `GET /list` always returns
  `{limit: null, can_create_more: true}`. `PlanUpgradeModal` import +
  tier-limit banner stripped from `ICPManager.js`. ICP-campaign linking
  (`icp_campaign_id`) is deferred to a follow-up iteration.
- **S7 — Weekly Recap PDF**: new `GET /api/aria-agent/weekly-recap/export.pdf`
  (ReportLab-rendered A4 with header band, narrative, 6 KPI tiles, 3
  highlight boxes, focus plan, footer). `WeeklyRecap.js` now has a
  "Download Report" button (`data-testid='weekly-recap-download-btn'`).
- **S9 partial — Dashboard personalization**: subheading now reads
  "Aria is working your leads for **<workspace>**", pulling the name from
  `localStorage.active_tenant.name`. BETA badge gone.
- **Test housekeeping**: `test_iter52_multi_icp_outreach.test_icp_tier_limit_starter_capped_at_2`
  updated to assert the new no-cap behavior. New
  `test_iter77_quickwin.py` adds 4 tests for the iter77 surfaces.
- Verified: 59/59 backend tests pass; frontend smoke confirms all four
  S1/S3/S7/S9 acceptance criteria.
- **NOT in scope this turn (queued):** S2 (conversation delete + cascade),
  S3 remainder (campaign linking), S4 (touchpoint kanban view), S5
  (Train Aria merge — spec needed), S6 (playbook injection into Claude),
  S8 (Master Admin Deployments tab + simplified onboarding + sidebar
  ARIA status), S9.5 (full security sweep).

## 2026-02 — Iter 76 (Backlog wrap-up + Aria Health badges)
- **Route alias**: `/ai-setup-assistant` now resolves to the AISetupAssistant
  page (alongside the canonical `/ai-setup`) — fixes the share-link friction
  flagged in iter73.
- **Resume last edit**: new GET `/api/aria/auto-map/summary` returns the
  tenant's last-published automap_summary including the user-edited
  `touchpoints_extracted`. The AI Setup Assistant now shows a "Resume last
  edit" banner above the upload panel when a previous workflow exists, and
  one click re-hydrates the Review stage with the editable rows — no
  re-upload required.
- **Aria Health tab**: new Settings → Aria Health surface backed by GET
  `/api/aria-agent/health` (new submodule `aria_agent_routes/health.py`).
  Renders a hero score (`N/7 muscles warmed up`) + 7 capability cards
  (training, playbooks, journey, auto_setup, integrations, sales_channels,
  brain) each with green/amber/red badge, hint text, and a deep-link button
  to the relevant setup page. Soft orange→rose gradient for the partial
  state so the empty-tenant case doesn't read as an error.
- Verified: 33/33 backend tests pass (7 new iter76 + 22 iter74 + 4 iter73).
  Frontend smoke + testing agent confirmed all 7 cards, banner, refresh,
  and deep-links render with zero console errors.

## 2026-02 — Iter 75 (P2 organizational refactors)
- **Backend split**: `aria_agent_routes.py` (1464 lines) → package
  `aria_agent_routes/` with 12 feature submodules
  (training, playbooks, journeys, briefs, workspace, handoff, revival,
  agent_activity, insights, assets, brain, weekly_recap) + `_shared.py`
  (router, collections, AriaTrainingPayload, deps import) +
  `__init__.py` (orchestrator, exposes `attach_aria_agent_routes`).
  Public surface preserved — `from aria_agent_routes import attach_aria_agent_routes`
  still works for `server.py:5245`. Largest submodule = 424 lines (workspace).
- **Frontend split**: `AISetupAssistant.js` (1010 lines) → 227-line
  orchestrator + `frontend/src/components/ai-setup/`
  (`UploadPanel`, `ExtractingPanel`, `ReviewPanel`, `DonePanel`,
  `ExtractedTouchpointRow`, `atoms`). Largest component = 425 lines
  (ReviewPanel). All data-testid attributes preserved.
- Test hygiene: `test_iter73_touchpoints_extracted_persistence.py` default
  `DB_NAME` corrected from `aria_db` → `genleadai_lms` (matches real env).
- Verified: 26/26 backend regression tests still pass (22 iter74 + 4 iter73).
  All 27 `/api/aria-agent/*` routes resolve. Frontend `/ai-setup` renders
  with no console errors. Zero behavior change.

## 2026-02 — Iter 74 (P1 refactor: aria_agent_routes.py)
- Eliminated the 1392-line `_aria_agent_endpoints(app, get_current_user, db)`
  wrapper. All 27 `/api/aria-agent/*` routes lifted to module level on a
  single `APIRouter`. `db` + `get_current_user` imported directly from
  `deps`.
- `attach_aria_agent_routes(app, get_current_user, db)` kept as a thin
  compatibility shim.
- Removed redundant `training_collection_ref` alias.
- Tests: `/app/backend/tests/test_iter74_aria_agent_refactor.py` (22 tests,
  100% pass). Zero regressions.

## 2026-02 — Iter 73 (AI Setup Assistant: inline edit before publish)
- Added `ExtractedTouchpointRow` inline editor to `AISetupAssistant.js` so
  founders can correct Aria's `touchpoints_extracted` rows (entry_point /
  channel_or_tool / timeline / flow_steps / outcome) before clicking Publish.
- Frontend `handlePublish` now sends `touchpoints_extracted` in the POST
  payload to `/api/aria/auto-map/publish`.
- Backend `PublishPayload` already declared the field; publish handler now
  actually persists it to `tenants.settings.automap_summary.touchpoints_extracted`
  and returns `touchpoints_extracted_saved` in the response.
- Safety: `useEffect` no longer overwrites the in-edit draft while editor is
  open (guarded with `!editing`).
- Tests: `/app/backend/tests/test_iter73_touchpoints_extracted_persistence.py`
  (4 tests, all passing). Frontend playwright validated edit/save/cancel/delete
  flow on `/ai-setup`.

## Earlier iterations (summary)
- Iter 71 — Strict-mode AI extraction (no hallucination), empty-overwrite
  guard, "Not found" banner, suggestions hidden by default.
- Iter 70 — Dagre auto-layout for Touchpoint Journey flowchart.
- Iter 69 — Saleshandy + Lemlist pull-based lead import.
- Iter 68 — Workspace-scoped `/api/users`, simplified 5-section Dashboard,
  fake leads removed from `/api/insights/founder-command-center`.
- Added `ExtractedTouchpointRow` inline editor to `AISetupAssistant.js` so
  founders can correct Aria's `touchpoints_extracted` rows (entry_point /
  channel_or_tool / timeline / flow_steps / outcome) before clicking Publish.
- Frontend `handlePublish` now sends `touchpoints_extracted` in the POST
  payload to `/api/aria/auto-map/publish`.
- Backend `PublishPayload` already declared the field; publish handler now
  actually persists it to `tenants.settings.automap_summary.touchpoints_extracted`
  and returns `touchpoints_extracted_saved` in the response.
- Safety: `useEffect` no longer overwrites the in-edit draft while editor is
  open (guarded with `!editing`).
- Tests: `/app/backend/tests/test_iter73_touchpoints_extracted_persistence.py`
  (4 tests, all passing). Frontend playwright validated edit/save/cancel/delete
  flow on `/ai-setup`.

## Earlier iterations (summary)
- Iter 71 — Strict-mode AI extraction (no hallucination), empty-overwrite
  guard, "Not found" banner, suggestions hidden by default.
- Iter 70 — Dagre auto-layout for Touchpoint Journey flowchart.
- Iter 69 — Saleshandy + Lemlist pull-based lead import.
- Iter 68 — Workspace-scoped `/api/users`, simplified 5-section Dashboard,
  fake leads removed from `/api/insights/founder-command-center`.
