/**
 * B2C Dashboard — per-mode entry point (iter159 split).
 *
 * This file exists so callers can do `import B2CDashboard from './B2CDashboard'`
 * instead of the legacy `import { B2CDashboard } from './Dashboards'`.
 *
 * The component body lives in `Dashboards.js` for now (~180 LOC) — see
 * PRD iter159 "Known follow-ups" for the deeper physical split plan.
 */
export { B2CDashboard, B2CDashboard as default } from './Dashboards';
