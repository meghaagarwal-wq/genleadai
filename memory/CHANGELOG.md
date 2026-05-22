# ARIA / GenLeadAI — Changelog

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
