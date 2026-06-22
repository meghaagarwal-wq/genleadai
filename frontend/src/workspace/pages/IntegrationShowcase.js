/**
 * IntegrationShowcase — iter160.
 *
 * Pill-filtered grid of integrations available on the platform.
 * Rendered at the bottom of every demo dashboard (B2C / B2B Founder /
 * B2B Sales) so the founder can answer "what does it connect to?" mid-
 * sales-call without leaving the dashboard.
 *
 * Source of truth: GET /api/dashboard/integration-showcase
 */
import React, { useEffect, useMemo, useState } from 'react';
import { CheckCircle, Sparkle, Plug } from '@phosphor-icons/react';
import api from '../../config/api';
import { SectionCard } from './dashboard_shared';

const STATUS_COLOURS = {
  live:        { bg: 'rgba(16,185,129,0.15)',  color: '#10B981', label: 'Live',        Icon: CheckCircle },
  available:   { bg: 'rgba(168,139,250,0.15)', color: '#7C35DC', label: 'Available',   Icon: Plug },
  coming_soon: { bg: 'rgba(148,163,184,0.18)', color: '#94A3B8', label: 'Coming soon', Icon: Sparkle },
};

const Pill = ({ active, label, count, color, onClick, testid }) => (
  <button
    type="button"
    onClick={onClick}
    data-testid={testid}
    aria-pressed={active}
    className="px-3 py-1.5 rounded-full text-xs font-bold transition-all active:scale-95 focus:outline-none focus:ring-2 focus:ring-offset-1"
    style={{
      background: active ? color : 'var(--theme-surface2)',
      color: active ? '#fff' : 'var(--theme-text)',
      boxShadow: active ? `0 2px 12px ${color}66` : 'none',
      border: active ? 'none' : '1px solid var(--theme-border)',
    }}
  >
    {label} <span className="opacity-70 ml-1 tabular-nums">{count}</span>
  </button>
);

const IntegrationCard = ({ row }) => {
  const s = STATUS_COLOURS[row.status] || STATUS_COLOURS.coming_soon;
  const { Icon } = s;
  const initials = row.label.split(/\s+/).slice(0, 2).map(w => w[0]).join('').toUpperCase();
  return (
    <div
      className="rounded-xl border p-3 flex flex-col gap-2 hover:-translate-y-0.5 hover:border-[var(--theme-purple-light)] transition-all"
      style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }}
      data-testid={`integration-card-${row.id}`}
      title={row.label}
    >
      <div className="flex items-center gap-2">
        <div
          className="shrink-0 w-9 h-9 rounded-lg flex items-center justify-center text-[10px] font-extrabold text-white"
          style={{ background: row.brand, boxShadow: `0 4px 12px ${row.brand}55` }}
          aria-hidden="true"
        >
          {initials}
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-xs font-bold truncate" style={{ color: 'var(--theme-text)' }}>{row.label}</div>
          <span
            className="inline-flex items-center gap-1 mt-0.5 px-1.5 py-0.5 rounded-full text-[9px] font-bold"
            style={{ background: s.bg, color: s.color }}
          >
            <Icon size={9} weight="fill" /> {s.label}
          </span>
        </div>
      </div>
    </div>
  );
};

export const IntegrationShowcase = () => {
  const [data, setData] = useState(null);
  const [active, setActive] = useState('all');

  useEffect(() => {
    api.get('/api/dashboard/integration-showcase').then(r => setData(r.data)).catch(() => setData({ categories: [], integrations: [], counts: {} }));
  }, []);

  const filtered = useMemo(() => {
    if (!data) return [];
    if (active === 'all') return data.integrations;
    return data.integrations.filter(r => r.cats.includes(active));
  }, [data, active]);

  if (!data) {
    return (
      <SectionCard title="Integrations" sub="What ARIA can plug into" testid="integration-showcase">
        <div className="text-xs py-4 text-center" style={{ color: 'var(--theme-text-muted)' }}>Loading…</div>
      </SectionCard>
    );
  }

  const liveCount = data.integrations.filter(r => r.status === 'live').length;

  return (
    <SectionCard
      title="What ARIA plugs into"
      sub={`${liveCount} live integrations · ${data.integrations.length - liveCount} more on the roadmap`}
      testid="integration-showcase"
    >
      {/* Filter pills */}
      <div className="flex flex-wrap gap-2 mb-4" role="tablist" aria-label="Integration categories">
        <Pill
          active={active === 'all'}
          label="All"
          count={data.counts.all}
          color="#7C35DC"
          onClick={() => setActive('all')}
          testid="integration-pill-all"
        />
        {data.categories.map(c => (
          <Pill
            key={c.key}
            active={active === c.key}
            label={c.label}
            count={data.counts[c.key] || 0}
            color={c.color}
            onClick={() => setActive(c.key)}
            testid={`integration-pill-${c.key}`}
          />
        ))}
      </div>

      {/* Category blurb */}
      {active !== 'all' && (
        <div className="text-[11px] mb-3 italic" style={{ color: 'var(--theme-text-muted)' }}>
          {data.categories.find(c => c.key === active)?.blurb}
        </div>
      )}

      {/* Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2.5">
        {filtered.map(row => <IntegrationCard key={row.id} row={row} />)}
      </div>

      <div className="mt-4 text-[10px] text-center" style={{ color: 'var(--theme-text-muted)' }}>
        Don't see one you need? Request it in <strong style={{ color: 'var(--theme-purple-light)' }}>Settings → Integrations</strong>.
      </div>
    </SectionCard>
  );
};

export default IntegrationShowcase;
