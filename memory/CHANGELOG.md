# ARIA / GenLeadAI — Changelog

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
