/**
 * Shared dashboard primitives (extracted iter158 — Phase B Step 4 split).
 *
 * KpiTile, ComingSoon, SectionCard, StatusPill, HealthBadge, useDashboard,
 * fmtMoney. Used by B2C, B2B Founder, and B2B Sales dashboards.
 */
/* eslint-disable react-hooks/exhaustive-deps */
import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { TrendUp, TrendDown, Sparkle, CheckCircle, WarningOctagon, Pause } from '@phosphor-icons/react';
import api from '../../config/api';
import { Sparkline } from './dashboard_charts';

// ─── KPI tile with sparkline ──────────────────────────────────────
export const KpiTile = ({ label, value, trend, unit, sub, spark, testid, ariaLabel }) => {
  const dir = trend?.direction;
  const sparkColor = dir === 'up' ? '#10B981' : dir === 'down' ? '#EF4444' : '#7C35DC';
  return (
    <div
      className="rounded-xl border p-4 group hover:border-[var(--theme-purple-light)] hover:-translate-y-0.5 transition-all duration-200 focus-within:ring-2 focus-within:ring-purple-400"
      data-testid={testid}
      role="group"
      aria-label={ariaLabel || `${label}: ${value}${unit || ''}`}
      style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }}
    >
      <div className="text-[10px] uppercase tracking-[0.16em]" style={{ color: 'var(--theme-text-muted)' }}>{label}</div>
      <div className="mt-1.5 flex items-baseline gap-1.5">
        <div className="text-2xl font-bold tabular-nums" style={{ color: 'var(--theme-text)' }}>{value ?? '—'}</div>
        {unit && <div className="text-sm" style={{ color: 'var(--theme-text-muted)' }}>{unit}</div>}
        {trend?.pct != null && (
          <span
            className={`ml-auto inline-flex items-center gap-0.5 text-[10px] font-semibold ${
              dir === 'up' ? 'text-emerald-500' : dir === 'down' ? 'text-rose-500' : 'text-slate-400'
            }`}
            aria-label={`${dir} ${Math.abs(trend.pct)} percent versus previous period`}
          >
            {dir === 'up' ? <TrendUp size={11} weight="bold" /> : dir === 'down' ? <TrendDown size={11} weight="bold" /> : null}
            {Math.abs(trend.pct)}%
          </span>
        )}
      </div>
      {/* Sparkline REPLACES the "vs prev" text — actual trajectory visible at a glance */}
      {spark?.length >= 2 ? (
        <div className="mt-1.5" aria-hidden="true"><Sparkline data={spark} color={sparkColor} height={28} /></div>
      ) : sub ? (
        <div className="mt-1 text-[11px]" style={{ color: 'var(--theme-text-muted)' }}>{sub}</div>
      ) : null}
    </div>
  );
};

// ─── Empty state ──────────────────────────────────────────────────
export const ComingSoon = ({ what, why }) => (
  <div
    className="rounded-xl border-2 border-dashed p-6 text-center"
    style={{ borderColor: 'var(--theme-border)', background: 'var(--theme-surface)' }}
    role="status"
  >
    <Sparkle size={20} weight="duotone" className="mx-auto mb-2" style={{ color: 'var(--theme-purple-light)' }} />
    <div className="text-sm font-semibold" style={{ color: 'var(--theme-text)' }}>Coming soon — {what}</div>
    {why && <div className="mt-1 text-xs" style={{ color: 'var(--theme-text-muted)' }}>{why}</div>}
  </div>
);

// ─── Section card ────────────────────────────────────────────────
export const SectionCard = ({ title, sub, action, children, testid }) => (
  <section
    className="rounded-xl border p-5"
    data-testid={testid}
    style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }}
    aria-label={title}
  >
    <div className="flex items-start justify-between gap-3 mb-4 flex-wrap">
      <div>
        <h3 className="text-sm font-bold" style={{ color: 'var(--theme-text)' }}>{title}</h3>
        {sub && <div className="text-[11px] mt-0.5" style={{ color: 'var(--theme-text-muted)' }}>{sub}</div>}
      </div>
      {action}
    </div>
    {children}
  </section>
);

// ─── Status pill ─────────────────────────────────────────────────
export const StatusPill = ({ status }) => {
  const cfg = {
    live:      { bg: 'rgba(236,72,153,0.15)', color: '#EC4899', text: '● Live' },
    waiting:   { bg: 'rgba(245,158,11,0.15)', color: '#F59E0B', text: 'Waiting' },
    booked:    { bg: 'rgba(16,185,129,0.15)', color: '#10B981', text: '✓ Booked' },
    qualified: { bg: 'rgba(59,130,246,0.15)', color: '#3B82F6', text: 'Qualified' },
  }[status] || { bg: 'var(--theme-surface2)', color: 'var(--theme-text-muted)', text: status };
  return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold" style={{ background: cfg.bg, color: cfg.color }}>{cfg.text}</span>;
};

// ─── Health badge ────────────────────────────────────────────────
export const HealthBadge = ({ h }) => {
  const cfg = {
    healthy:         { color: '#10B981', icon: CheckCircle,    text: 'Healthy' },
    working_well:    { color: '#10B981', icon: CheckCircle,    text: 'Working' },
    moderate:        { color: '#F59E0B', icon: WarningOctagon, text: 'Moderate' },
    warning:         { color: '#F59E0B', icon: WarningOctagon, text: 'Watch' },
    needs_attention: { color: '#EF4444', icon: WarningOctagon, text: 'Critical' },
    inactive:        { color: '#94A3B8', icon: Pause,           text: 'Inactive' },
  }[h] || { color: '#94A3B8', icon: Pause, text: h || '—' };
  const I = cfg.icon;
  return (
    <span className="inline-flex items-center gap-1 text-[10px] font-bold" style={{ color: cfg.color }}>
      <I size={10} weight="fill" /> {cfg.text}
    </span>
  );
};

// ─── Data hook ───────────────────────────────────────────────────
export const useDashboard = (endpoint) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get(endpoint);
      setData(r.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  }, [endpoint]);
  useEffect(() => { load(); }, [load]);
  return { data, loading, refresh: load };
};

// ─── Currency formatter ─────────────────────────────────────────
export const fmtMoney = (v, currency) => {
  if (v == null) return '—';
  const symbol = { INR: '₹', USD: '$', GBP: '£', AED: 'د.إ', EUR: '€' }[currency] || '$';
  return `${symbol}${Number(v).toLocaleString()}`;
};

// ─── Loading skeleton ────────────────────────────────────────────
export const DashboardSkeleton = ({ title = 'Loading dashboard…' }) => (
  <div className="p-6 space-y-6 max-w-[1600px] mx-auto animate-pulse" aria-busy="true" aria-label={title}>
    <div className="h-8 w-72 rounded" style={{ background: 'var(--theme-surface2)' }} />
    <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="h-24 rounded-xl border" style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }} />
      ))}
    </div>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className="h-48 rounded-xl border" style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }} />
      <div className="h-48 rounded-xl border" style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }} />
    </div>
  </div>
);
