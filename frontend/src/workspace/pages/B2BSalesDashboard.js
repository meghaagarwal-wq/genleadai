/**
 * B2B Sales Dashboard — per-mode entry point (iter159 split).
 *
 * This file exists so callers can do `import B2BSalesDashboard from './B2BSalesDashboard'`
 * instead of the legacy `import { B2BSalesDashboard } from './Dashboards'`.
 *
 * The component body lives in `Dashboards.js` for now (~130 LOC + TopActionsCard).
 */
export { B2BSalesDashboard, B2BSalesDashboard as default } from './Dashboards';
