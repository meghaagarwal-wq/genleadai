/**
 * B2B Founder Dashboard — per-mode entry point (iter159 split).
 *
 * This file exists so callers can do `import B2BFounderDashboard from './B2BFounderDashboard'`
 * instead of the legacy `import { B2BFounderDashboard } from './Dashboards'`.
 *
 * The component body lives in `Dashboards.js` for now (~170 LOC + InstinctFeedWidget).
 */
export { B2BFounderDashboard, B2BFounderDashboard as default } from './Dashboards';
