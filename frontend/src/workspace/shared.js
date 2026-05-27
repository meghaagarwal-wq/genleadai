// Shared helpers + tokens for Pietential pages.
import api from '../config/api';

export const ptApi = api;

export const STAGE_META = {
  cold:           { label: 'Cold',          color: '#64748B', bg: 'rgba(100,116,139,0.08)' },
  warm:           { label: 'Warm',          color: '#F59E0B', bg: 'rgba(245,158,11,0.08)' },
  hot:            { label: 'Hot',           color: '#DC2626', bg: 'rgba(220,38,38,0.08)' },
  engaged:        { label: 'Engaged',       color: '#7C35DC', bg: 'rgba(124,53,220,0.08)' },
  session_pilot:  { label: 'Session/Pilot', color: '#7C3AED', bg: 'rgba(124,58,237,0.08)' },
};

export const SOURCE_LABELS = {
  saleshandy: 'Saleshandy',
  lemlist: 'Lemlist',
  good_slice: 'Good Slice',
  newsletter: 'Newsletter',
  lead_magnet: 'Lead Magnet',
  website: 'Website',
  calendly: 'Calendly',
  manual: 'Manual',
};

export const SEQUENCE_STATUS_META = {
  not_started:           { label: 'Not started',           color: '#64748B' },
  active_in_saleshandy:  { label: 'Active · Saleshandy',   color: '#F59E0B' },
  active_in_lemlist:     { label: 'Active · Lemlist',      color: '#7C35DC' },
  warm_nurture:          { label: 'Warm nurture',          color: '#F59E0B' },
  pause_required:        { label: 'Pause required',        color: '#DC2626' },
  paused:                { label: 'Paused',                color: '#475569' },
  john_owns:             { label: 'John owns',             color: '#7C35DC' },
  dnc:                   { label: 'DNC / unsubscribed',    color: '#DC2626' },
};

export const fmtDate = (iso) => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleDateString(); } catch { return iso; }
};
export const fmtDateTime = (iso) => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
};

export const Pill = ({ label, color, bg }) => (
  <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-[0.12em]"
    style={{ color, background: bg || `${color}14`, border: `1px solid ${color}33` }}>
    {label}
  </span>
);

export const StageBadge = ({ stage }) => {
  const meta = STAGE_META[stage] || STAGE_META.cold;
  return <Pill label={meta.label} color={meta.color} bg={meta.bg} />;
};

export const SequenceBadge = ({ status }) => {
  const meta = SEQUENCE_STATUS_META[status] || SEQUENCE_STATUS_META.not_started;
  return <Pill label={meta.label} color={meta.color} />;
};

export const PageHeader = ({ title, subtitle, right }) => (
  <div className="flex items-start justify-between gap-4 mb-6">
    <div>
      <h1 className="text-2xl font-extrabold text-[#0F172A] tracking-tight" style={{ fontFamily: 'Space Grotesk, Inter' }}>{title}</h1>
      {subtitle && <p className="text-sm text-[#64748B] mt-1">{subtitle}</p>}
    </div>
    {right && <div className="flex-shrink-0">{right}</div>}
  </div>
);

export const EmptyState = ({ title, message, cta }) => (
  <div className="bg-white border border-dashed border-[#CBD5E1] rounded-xl p-10 text-center" data-testid="pt-empty-state">
    <div className="text-base font-semibold text-[#0F172A]" style={{ fontFamily: 'Space Grotesk, Inter' }}>{title}</div>
    <p className="text-sm text-[#64748B] mt-1.5 max-w-md mx-auto">{message}</p>
    {cta && <div className="mt-4">{cta}</div>}
  </div>
);
