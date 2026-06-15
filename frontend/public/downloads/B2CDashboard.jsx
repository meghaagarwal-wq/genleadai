/**
 * B2C Demo Dashboard — standalone export from ARIA (GenLeadAI).
 *
 * Self-contained React component. Drop into any React 18/19 project and
 * point `API_BASE` to your backend. The backend must implement
 * `GET /api/dashboard/b2c` and return the JSON shape documented in
 * `./b2c_dashboard.schema.json` (see README).
 *
 * Dependencies (yarn add):
 *   react react-dom @phosphor-icons/react
 *
 * Optional (uses your CSS variables — see "Theming" in README):
 *   tailwindcss (recommended — the markup uses Tailwind utility classes)
 *
 * No router required — uses plain <a> tags. Swap for <Link> if you wire
 * react-router yourself.
 *
 * ─────────────────────────────────────────────────────────────────────
 * Author: ARIA / GenLeadAI · Exported Feb 2026
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  TrendUp, TrendDown, Sparkle, Clock, ArrowsClockwise,
} from '@phosphor-icons/react';

// ─── Config ──────────────────────────────────────────────────────────
// Replace with your own backend base URL (no trailing slash).
const API_BASE = process.env.REACT_APP_API_BASE || '';

// Bearer token reader — replace with your own auth integration.
// e.g. read from localStorage, a cookie, or a context provider.
const getAuthToken = () => {
  try { return localStorage.getItem('auth_token') || ''; }
  catch { return ''; }
};

// ─── Tiny network helper ─────────────────────────────────────────────
const fetchDashboard = async () => {
  const token = getAuthToken();
  const r = await fetch(`${API_BASE}/api/dashboard/b2c`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
};

// ─── Formatters ──────────────────────────────────────────────────────
const fmtMoney = (v, currency) => {
  if (v == null) return '—';
  const symbol = { INR: '₹', USD: '$', GBP: '£', AED: 'د.إ', EUR: '€' }[currency] || '$';
  return `${symbol}${Number(v).toLocaleString()}`;
};

const CHANNEL_COLOUR = {
  whatsapp: '#25D366', linkedin: '#0A66C2',
  email: '#7C35DC', website: '#0E9F86',
  instagram: '#EC4899', facebook: '#1877F2',
  google: '#4285F4', referral: '#F59E0B',
};

// ─── Sub-components ──────────────────────────────────────────────────
const KpiTile = ({ label, value, trend, unit, sub, testid }) => {
  const dir = trend?.direction;
  return (
    <div
      className="rounded-xl border p-4"
      data-testid={testid}
      style={{ background: 'var(--theme-surface, #fff)', borderColor: 'var(--theme-border, #E5E7EB)' }}
    >
      <div className="text-[10px] uppercase tracking-[0.16em]" style={{ color: 'var(--theme-text-muted, #6B7280)' }}>
        {label}
      </div>
      <div className="mt-1.5 flex items-baseline gap-1.5">
        <div className="text-2xl font-bold" style={{ color: 'var(--theme-text, #111827)' }}>
          {value ?? '—'}
        </div>
        {unit && <div className="text-sm" style={{ color: 'var(--theme-text-muted, #6B7280)' }}>{unit}</div>}
      </div>
      {trend?.pct != null && (
        <div
          className="mt-1 inline-flex items-center gap-0.5 text-[11px] font-semibold"
          style={{
            color: dir === 'up' ? '#10B981' : dir === 'down' ? '#EF4444' : '#94A3B8',
          }}
        >
          {dir === 'up' ? <TrendUp size={12} weight="bold" /> : dir === 'down' ? <TrendDown size={12} weight="bold" /> : null}
          {Math.abs(trend.pct)}% vs prev
        </div>
      )}
      {sub && <div className="mt-1 text-[11px]" style={{ color: 'var(--theme-text-muted, #6B7280)' }}>{sub}</div>}
    </div>
  );
};

const ComingSoon = ({ what, why }) => (
  <div
    className="rounded-xl border-2 border-dashed p-6 text-center"
    style={{ borderColor: 'var(--theme-border, #E5E7EB)', background: 'var(--theme-surface, #fff)' }}
  >
    <Sparkle size={20} weight="duotone" className="mx-auto mb-2" style={{ color: 'var(--theme-purple-light, #A78BFA)' }} />
    <div className="text-sm font-semibold" style={{ color: 'var(--theme-text, #111827)' }}>
      Coming soon — {what}
    </div>
    {why && <div className="mt-1 text-xs" style={{ color: 'var(--theme-text-muted, #6B7280)' }}>{why}</div>}
  </div>
);

const SectionCard = ({ title, sub, action, children, testid }) => (
  <div
    className="rounded-xl border p-5"
    data-testid={testid}
    style={{ background: 'var(--theme-surface, #fff)', borderColor: 'var(--theme-border, #E5E7EB)' }}
  >
    <div className="flex items-start justify-between gap-3 mb-4">
      <div>
        <h3 className="text-sm font-bold" style={{ color: 'var(--theme-text, #111827)' }}>{title}</h3>
        {sub && <div className="text-[11px] mt-0.5" style={{ color: 'var(--theme-text-muted, #6B7280)' }}>{sub}</div>}
      </div>
      {action}
    </div>
    {children}
  </div>
);

const StatusPill = ({ status }) => {
  const cfg = {
    live:      { bg: 'rgba(236,72,153,0.15)', color: '#EC4899', text: '● Live' },
    waiting:   { bg: 'rgba(245,158,11,0.15)', color: '#F59E0B', text: 'Waiting' },
    booked:    { bg: 'rgba(16,185,129,0.15)', color: '#10B981', text: '✓ Booked' },
    qualified: { bg: 'rgba(59,130,246,0.15)', color: '#3B82F6', text: 'Qualified' },
  }[status] || { bg: 'var(--theme-surface2, #F3F4F6)', color: 'var(--theme-text-muted, #6B7280)', text: status };
  return (
    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold" style={{ background: cfg.bg, color: cfg.color }}>
      {cfg.text}
    </span>
  );
};

// ─── Main component ─────────────────────────────────────────────────
export const B2CDashboard = ({ onLeadClick, onViewAllConversations }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await fetchDashboard();
      setData(d);
    } catch (e) {
      setError(e.message || 'Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return <div className="p-8 text-sm" style={{ color: 'var(--theme-text-muted, #6B7280)' }}>Loading B2C dashboard…</div>;
  }
  if (error || !data) {
    return (
      <div className="p-8 text-sm rounded-xl border-2 border-dashed text-center" style={{ color: '#EF4444', borderColor: '#FCA5A5' }}>
        Failed to load: {error || 'no data'}
        <button onClick={load} className="ml-2 underline">retry</button>
      </div>
    );
  }

  const c = data.header.currency;

  return (
    <div className="p-6 space-y-6 max-w-[1600px] mx-auto" data-testid="b2c-dashboard">
      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--theme-text, #111827)' }}>
            {data.header.greeting}, {data.header.owner_name}
          </h1>
          <div className="text-sm mt-1" style={{ color: 'var(--theme-text-muted, #6B7280)' }}>
            {data.header.workspace_name}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span
            className="px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider"
            style={{ background: 'rgba(14,159,134,0.15)', color: '#0E9F86' }}
          >
            B2C Automation
          </span>
          <button
            onClick={load}
            className="text-xs px-3 py-1.5 rounded-md flex items-center gap-1.5"
            style={{ background: 'var(--theme-surface2, #F3F4F6)', color: 'var(--theme-text, #111827)' }}
            data-testid="b2c-refresh"
          >
            <ArrowsClockwise size={12} /> Refresh
          </button>
        </div>
      </div>

      {/* ── KPI strip ──────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <KpiTile label="Leads today"          value={data.kpis.leads_today.value}      trend={data.kpis.leads_today.trend}      testid="kpi-leads-today" />
        <KpiTile label="Active conversations" value={data.kpis.active_convos.value}    sub={data.kpis.active_convos.label}      testid="kpi-active-convos" />
        <KpiTile label="Bookings this week"   value={data.kpis.bookings_week.value}    trend={data.kpis.bookings_week.trend}    testid="kpi-bookings-week" />
        <KpiTile label="Lead → booking"       value={data.kpis.conversion_rate.value}  unit="%" trend={data.kpis.conversion_rate.trend} testid="kpi-conv-rate" />
        <KpiTile label="Pipeline value"       value={fmtMoney(data.kpis.revenue_pipeline.value, c)} testid="kpi-pipeline-value" />
      </div>

      {/* ── ARIA time-saved banner ─────────────────────────────── */}
      <div
        className="rounded-xl px-6 py-4 flex items-center justify-between"
        style={{ background: 'linear-gradient(135deg, #0F172A 0%, #1E293B 100%)', color: '#F1F5F9' }}
        data-testid="aria-time-saved-banner"
      >
        <div className="flex items-center gap-3">
          <Clock size={22} weight="duotone" />
          <div>
            <div className="text-sm font-bold">ARIA saved you {data.aria_time_saved.hours} hours this week</div>
            <div className="text-xs opacity-80 mt-0.5">
              ~{fmtMoney(data.aria_time_saved.money_equivalent, c)} in research + outreach work
            </div>
          </div>
        </div>
        <div className="hidden md:flex gap-4 text-[11px] opacity-80">
          <span>{data.aria_time_saved.breakdown.conversations} convos</span>
          <span>{data.aria_time_saved.breakdown.drafts} drafts</span>
          <span>{data.aria_time_saved.breakdown.insights} insights</span>
          <span>{data.aria_time_saved.breakdown.researched} researched</span>
        </div>
      </div>

      {/* ── Momentum + Revenue Forecast ────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <SectionCard title="Momentum" sub={data.momentum.driver_text} testid="momentum-card">
          <div className="flex items-center gap-4">
            <div className="text-5xl">
              {data.momentum.direction === 'up' ? '🚀' : data.momentum.direction === 'down' ? '🔻' : '→'}
            </div>
            <div>
              <div className="text-3xl font-bold" style={{ color: 'var(--theme-text, #111827)' }}>
                {data.momentum.score}
                <span className="text-base" style={{ color: 'var(--theme-text-muted, #6B7280)' }}> / 100</span>
              </div>
              <div
                className="text-sm mt-0.5 font-semibold"
                style={{ color: data.momentum.direction === 'up' ? '#10B981' : data.momentum.direction === 'down' ? '#EF4444' : '#94A3B8' }}
              >
                {data.momentum.label}
              </div>
            </div>
          </div>
        </SectionCard>

        <SectionCard title="Revenue Forecast" testid="revenue-forecast">
          {data.revenue_forecast.coming_soon ? (
            <ComingSoon what="revenue tracking" why="Connect a booking flow to see month-over-month projections." />
          ) : (
            <>
              <div className="text-sm" style={{ color: 'var(--theme-text, #111827)' }}>
                At current pace, you&apos;re on track for{' '}
                <strong>{fmtMoney(data.revenue_forecast.projected_end_of_month, c)}</strong> this month
              </div>
              <div className="mt-2 h-2 rounded-full overflow-hidden" style={{ background: 'var(--theme-surface2, #F3F4F6)' }}>
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${Math.min(100, data.revenue_forecast.pct_of_last_month || 0)}%`,
                    background: 'linear-gradient(90deg, #4C1D95, #7C35DC)',
                  }}
                />
              </div>
              <div className="text-[11px] mt-1.5" style={{ color: 'var(--theme-text-muted, #6B7280)' }}>
                {data.revenue_forecast.pct_of_last_month}% of last month ({fmtMoney(data.revenue_forecast.last_month_actual, c)})
              </div>
            </>
          )}
        </SectionCard>
      </div>

      {/* ── Live Conversations + Lead Sources + Asset Performance ── */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-3">
          <SectionCard
            title="Live Conversations"
            sub={`${data.conversations.length} active · ARIA is handling all of them`}
            testid="live-conversations"
            action={
              <button
                onClick={onViewAllConversations}
                className="text-xs font-semibold"
                style={{ color: 'var(--theme-purple-light, #A78BFA)' }}
              >
                View all →
              </button>
            }
          >
            {data.conversations.length === 0 ? (
              <div className="text-sm py-6 text-center" style={{ color: 'var(--theme-text-muted, #6B7280)' }}>
                No conversations in the last 2 hours.
              </div>
            ) : (
              <div className="divide-y" style={{ borderColor: 'var(--theme-border, #E5E7EB)' }}>
                {data.conversations.map((cv) => (
                  <button
                    key={cv.lead_id}
                    onClick={() => onLeadClick?.(cv.lead_id)}
                    className="flex items-center gap-3 py-2.5 hover:bg-[var(--theme-surface2,#F3F4F6)] px-2 -mx-2 rounded w-full text-left"
                  >
                    <div
                      className="w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold text-white shrink-0"
                      style={{ background: 'linear-gradient(135deg, #4C1D95, #7C35DC)' }}
                    >
                      {cv.initials}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-semibold truncate" style={{ color: 'var(--theme-text, #111827)' }}>
                        {cv.name}
                      </div>
                      <div className="text-xs truncate" style={{ color: 'var(--theme-text-muted, #6B7280)' }}>
                        {cv.snippet}
                      </div>
                    </div>
                    <StatusPill status={cv.status} />
                    <div className="text-[10px]" style={{ color: 'var(--theme-text-muted, #6B7280)' }}>{cv.minutes_ago}m</div>
                  </button>
                ))}
              </div>
            )}
          </SectionCard>
        </div>

        <div className="lg:col-span-2 space-y-4">
          <SectionCard title="Where leads came from today" testid="lead-sources">
            {data.lead_sources.length === 0 ? (
              <div className="text-xs py-4 text-center" style={{ color: 'var(--theme-text-muted, #6B7280)' }}>
                No leads today yet.
              </div>
            ) : (
              data.lead_sources.map((s) => (
                <div key={s.channel} className="mb-2 last:mb-0">
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="capitalize font-semibold" style={{ color: 'var(--theme-text, #111827)' }}>{s.channel}</span>
                    <span style={{ color: 'var(--theme-text-muted, #6B7280)' }}>{s.count}</span>
                  </div>
                  <div className="h-2 rounded-full" style={{ background: 'var(--theme-surface2, #F3F4F6)' }}>
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${Math.min(100, s.count * 10)}%`,
                        background: s.colour || CHANNEL_COLOUR[s.channel?.toLowerCase()] || '#94A3B8',
                      }}
                    />
                  </div>
                </div>
              ))
            )}
          </SectionCard>

          <SectionCard title="Asset performance" testid="asset-performance">
            {data.asset_performance.coming_soon ? (
              <ComingSoon what="asset tracking" why="Add tracked links to your lead magnets to see clicks here." />
            ) : (
              <div className="space-y-2">
                {data.asset_performance.rows.map((a) => (
                  <div key={a.name} className="flex justify-between text-xs">
                    <span className="truncate" style={{ color: 'var(--theme-text, #111827)' }}>{a.name}</span>
                    <span className="font-semibold" style={{ color: 'var(--theme-purple-light, #A78BFA)' }}>{a.clicks}</span>
                  </div>
                ))}
              </div>
            )}
          </SectionCard>
        </div>
      </div>

      {/* ── Funnel ─────────────────────────────────────────────── */}
      <SectionCard
        title="Booking Funnel — This Week"
        sub={`${data.funnel[0]?.count ?? 0} leads entered top of funnel`}
        testid="booking-funnel"
      >
        <div className="grid grid-cols-5 gap-2">
          {data.funnel.map((step, i) => {
            const palette = ['#6366F1', '#7C35DC', '#0E9F86', '#F59E0B', '#10B981'];
            return (
              <div key={step.stage} className="rounded-md p-3 text-center" style={{ background: palette[i % palette.length], color: 'white' }}>
                <div className="text-2xl font-bold">{step.count}</div>
                <div className="text-[10px] opacity-90 mt-0.5">{step.stage}</div>
                {i > 0 && <div className="text-[10px] mt-1 opacity-80">{step.pct_of_prev}% of prev</div>}
              </div>
            );
          })}
        </div>
        {data.biggest_drop && (
          <div className="mt-3 text-xs rounded-md px-3 py-2" style={{ background: 'rgba(245,158,11,0.15)', color: '#F59E0B' }}>
            ⚠ Biggest drop-off: {data.biggest_drop.from} → {data.biggest_drop.to} ({data.biggest_drop.loss_pct}% lost)
          </div>
        )}
      </SectionCard>

      {/* ── Bottom row: Sequences + Multi-touch + Ghost leads ──── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <SectionCard title="Active sequences" testid="sequences">
          {data.sequences.length === 0 ? (
            <ComingSoon what="sequence data" why="Connect Lemlist (or equivalent) to populate." />
          ) : (
            <table className="w-full text-xs">
              <thead>
                <tr style={{ color: 'var(--theme-text-muted, #6B7280)' }}>
                  <th className="text-left font-semibold pb-1">Name</th>
                  <th className="text-right font-semibold pb-1">Active</th>
                  <th className="text-right font-semibold pb-1">Booked</th>
                  <th className="text-right font-semibold pb-1">Rate</th>
                </tr>
              </thead>
              <tbody>
                {data.sequences.map((s) => (
                  <tr key={s.name}>
                    <td className="py-1 truncate" style={{ color: 'var(--theme-text, #111827)' }}>{s.name}</td>
                    <td className="text-right" style={{ color: 'var(--theme-text, #111827)' }}>{s.active}</td>
                    <td className="text-right" style={{ color: 'var(--theme-text, #111827)' }}>{s.booked}</td>
                    <td
                      className="text-right font-bold"
                      style={{ color: s.rate >= 15 ? '#10B981' : s.rate >= 5 ? '#F59E0B' : '#EF4444' }}
                    >
                      {s.rate}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </SectionCard>

        <SectionCard
          title="Multi-touch leads"
          sub="Leads from 2+ channels convert higher"
          testid="channel-overlap"
        >
          {data.channel_overlap?.coming_soon || !(data.channel_overlap?.rows?.length) ? (
            <ComingSoon what="multi-touch tracking" why="Tag lead source on every channel to see overlap." />
          ) : (
            <div className="space-y-2">
              {data.channel_overlap.rows.map((r) => (
                <div key={r.channels} className="flex items-center justify-between text-xs gap-2">
                  <span className="capitalize font-semibold truncate flex-1" style={{ color: 'var(--theme-text, #111827)' }}>
                    {r.channels}
                  </span>
                  <span style={{ color: 'var(--theme-text-muted, #6B7280)' }}>{r.leads} leads</span>
                  <span
                    className="font-bold"
                    style={{ color: r.conv_rate >= 30 ? '#10B981' : r.conv_rate >= 10 ? '#F59E0B' : '#94A3B8' }}
                  >
                    {r.conv_rate}%
                  </span>
                </div>
              ))}
            </div>
          )}
        </SectionCard>

        <SectionCard
          title="Leads to recover"
          sub={`${data.ghost_leads.length} warm leads gone quiet`}
          testid="ghost-leads"
        >
          {data.ghost_leads.length === 0 ? (
            <div className="text-xs text-center py-4" style={{ color: 'var(--theme-text-muted, #6B7280)' }}>
              No ghost leads — nice.
            </div>
          ) : (
            data.ghost_leads.map((g) => (
              <button
                key={g.id}
                onClick={() => onLeadClick?.(g.id)}
                className="block w-full text-left py-2 border-b last:border-b-0 hover:bg-[var(--theme-surface2,#F3F4F6)] -mx-2 px-2 rounded"
                style={{ borderColor: 'var(--theme-border, #E5E7EB)' }}
              >
                <div className="text-xs font-semibold" style={{ color: 'var(--theme-text, #111827)' }}>{g.name}</div>
                <div className="text-[11px]" style={{ color: 'var(--theme-text-muted, #6B7280)' }}>
                  {g.company} · {g.days_silent}d silent
                </div>
              </button>
            ))
          )}
        </SectionCard>
      </div>
    </div>
  );
};

export default B2CDashboard;
