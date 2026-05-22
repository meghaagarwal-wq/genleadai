# ARIA / GenLeadAI — Changelog

## 2026-02 — Iter 74 (P1 refactor: aria_agent_routes.py)
- Eliminated the 1392-line `_aria_agent_endpoints(app, get_current_user, db)`
  wrapper. All 27 `/api/aria-agent/*` routes now live at module level on a
  single `APIRouter`. `db` + `get_current_user` are imported directly from
  `deps`.
- `attach_aria_agent_routes(app, get_current_user, db)` kept as a thin
  compatibility shim (positional args accepted & ignored) so `server.py`
  call site (`server.py:5246`) didn't need to change.
- Removed redundant `training_collection_ref` alias.
- Tests: `/app/backend/tests/test_iter74_aria_agent_refactor.py` (22 tests,
  100% pass) + iter73 suite re-validated (4/4 pass). Zero behavioral
  regressions — all routes return same status codes + shapes as iter71.

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
