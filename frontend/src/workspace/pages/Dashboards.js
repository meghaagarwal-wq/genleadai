/**
 * ARIA Dashboard skeletons — iter150.
 *
 * Three dashboards in one file so the import surface stays tiny:
 *   - <B2CDashboard />       — Automation Command Center
 *   - <B2BFounderDashboard /> — Intelligence Overview
 *   - <B2BSalesDashboard />   — Sales pipeline (action-first)
 *
 * <DashboardRouter /> picks the right one based on GET /api/dashboard/_mode.
 *
 * Skeletons load real data where available (KPIs, lead sources, funnel,
 * founder flags, ARIA time saved, momentum, channel performance, why-now,
 * deal risk, ghost leads, agenda, pipeline table). Sections backed by
 * collections that don't exist in production yet render a clean
 * "Coming soon — connect [X]" empty state via `coming_soon: true` from
 * the backend.
 */
/* eslint-disable react-hooks/exhaustive-deps */
import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import {
  TrendUp, TrendDown, Sparkle, Clock, ChartLine, Lightning, ArrowsClockwise,
  Buildings, ArrowRight, Warning, Robot,
} from '@phosphor-icons/react';
import api from '../../config/api';

// ─── Shared tiny components ───────────────────────────────────────
const KpiTile = ({ label, value, trend, unit, sub, testid }) => {
  const dir = trend?.direction;
  return (
    <div className="rounded-xl border p-4" data-testid={testid}
      style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }}>
      <div className="text-[10px] uppercase tracking-[0.16em]" style={{ color: 'var(--theme-text-muted)' }}>{label}</div>
      <div className="mt-1.5 flex items-baseline gap-1.5">
        <div className="text-2xl font-bold" style={{ color: 'var(--theme-text)' }}>{value ?? '—'}</div>
        {unit && <div className="text-sm" style={{ color: 'var(--theme-text-muted)' }}>{unit}</div>}
      </div>
      {trend?.pct != null && (
        <div className={`mt-1 inline-flex items-center gap-0.5 text-[11px] font-semibold ${
          dir === 'up' ? 'text-emerald-500' : dir === 'down' ? 'text-rose-500' : 'text-slate-400'
        }`}>
          {dir === 'up' ? <TrendUp size={12} weight="bold" /> : dir === 'down' ? <TrendDown size={12} weight="bold" /> : null}
          {Math.abs(trend.pct)}% vs prev
        </div>
      )}
      {sub && <div className="mt-1 text-[11px]" style={{ color: 'var(--theme-text-muted)' }}>{sub}</div>}
    </div>
  );
};

const ComingSoon = ({ what, why }) => (
  <div className="rounded-xl border-2 border-dashed p-6 text-center"
    style={{ borderColor: 'var(--theme-border)', background: 'var(--theme-surface)' }}>
    <Sparkle size={20} weight="duotone" className="mx-auto mb-2" style={{ color: 'var(--theme-purple-light)' }} />
    <div className="text-sm font-semibold" style={{ color: 'var(--theme-text)' }}>Coming soon — {what}</div>
    {why && <div className="mt-1 text-xs" style={{ color: 'var(--theme-text-muted)' }}>{why}</div>}
  </div>
);

const SectionCard = ({ title, sub, action, children, testid }) => (
  <div className="rounded-xl border p-5" data-testid={testid}
    style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }}>
    <div className="flex items-start justify-between gap-3 mb-4">
      <div>
        <h3 className="text-sm font-bold" style={{ color: 'var(--theme-text)' }}>{title}</h3>
        {sub && <div className="text-[11px] mt-0.5" style={{ color: 'var(--theme-text-muted)' }}>{sub}</div>}
      </div>
      {action}
    </div>
    {children}
  </div>
);

const useDashboard = (endpoint) => {
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

const fmtMoney = (v, currency) => {
  if (v == null) return '—';
  const symbol = { INR: '₹', USD: '$', GBP: '£', AED: 'د.إ', EUR: '€' }[currency] || '$';
  return `${symbol}${Number(v).toLocaleString()}`;
};

// ───────────────────────── B2C DASHBOARD ──────────────────────────
export const B2CDashboard = () => {
  const { data, loading, refresh } = useDashboard('/api/dashboard/b2c');
  if (loading || !data) return <div className="p-8 text-sm" style={{ color: 'var(--theme-text-muted)' }}>Loading B2C dashboard…</div>;
  const c = data.header.currency;

  return (
    <div className="p-6 space-y-6 max-w-[1600px] mx-auto" data-testid="b2c-dashboard">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--theme-text)' }}>{data.header.greeting}, {data.header.owner_name}</h1>
          <div className="text-sm mt-1" style={{ color: 'var(--theme-text-muted)' }}>{data.header.workspace_name}</div>
        </div>
        <div className="flex items-center gap-3">
          <span className="px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider" style={{ background: 'rgba(14,159,134,0.15)', color: '#0E9F86' }}>B2C Automation</span>
          <button onClick={refresh} className="text-xs px-3 py-1.5 rounded-md flex items-center gap-1.5" style={{ background: 'var(--theme-surface2)', color: 'var(--theme-text)' }} data-testid="b2c-refresh">
            <ArrowsClockwise size={12} /> Refresh
          </button>
        </div>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <KpiTile label="Leads today" value={data.kpis.leads_today.value} trend={data.kpis.leads_today.trend} testid="kpi-leads-today" />
        <KpiTile label="Active conversations" value={data.kpis.active_convos.value} sub={data.kpis.active_convos.label} testid="kpi-active-convos" />
        <KpiTile label="Bookings this week" value={data.kpis.bookings_week.value} trend={data.kpis.bookings_week.trend} testid="kpi-bookings-week" />
        <KpiTile label="Lead → booking" value={data.kpis.conversion_rate.value} unit="%" trend={data.kpis.conversion_rate.trend} testid="kpi-conv-rate" />
        <KpiTile label="Pipeline value" value={fmtMoney(data.kpis.revenue_pipeline.value, c)} testid="kpi-pipeline-value" />
      </div>

      {/* ARIA Time Saved banner */}
      <div className="rounded-xl px-6 py-4 flex items-center justify-between"
        style={{ background: 'linear-gradient(135deg, #0F172A 0%, #1E293B 100%)', color: '#F1F5F9' }} data-testid="aria-time-saved-banner">
        <div className="flex items-center gap-3">
          <Clock size={22} weight="duotone" />
          <div>
            <div className="text-sm font-bold">ARIA saved you {data.aria_time_saved.hours} hours this week</div>
            <div className="text-xs opacity-80 mt-0.5">~{fmtMoney(data.aria_time_saved.money_equivalent, c)} in research + outreach work</div>
          </div>
        </div>
        <div className="hidden md:flex gap-4 text-[11px] opacity-80">
          <span>{data.aria_time_saved.breakdown.conversations} convos</span>
          <span>{data.aria_time_saved.breakdown.drafts} drafts</span>
          <span>{data.aria_time_saved.breakdown.insights} insights</span>
          <span>{data.aria_time_saved.breakdown.researched} researched</span>
        </div>
      </div>

      {/* Momentum + Revenue Forecast */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <SectionCard title="Momentum" sub={data.momentum.driver_text} testid="momentum-card">
          <div className="flex items-center gap-4">
            <div className="text-5xl">
              {data.momentum.direction === 'up' ? '🚀' : data.momentum.direction === 'down' ? '🔻' : '→'}
            </div>
            <div>
              <div className="text-3xl font-bold" style={{ color: 'var(--theme-text)' }}>{data.momentum.score}<span className="text-base" style={{ color: 'var(--theme-text-muted)' }}> / 100</span></div>
              <div className="text-sm mt-0.5 font-semibold" style={{ color: data.momentum.direction === 'up' ? '#10B981' : data.momentum.direction === 'down' ? '#EF4444' : '#94A3B8' }}>{data.momentum.label}</div>
            </div>
          </div>
        </SectionCard>
        <SectionCard title="Revenue Forecast" testid="revenue-forecast">
          {data.revenue_forecast.coming_soon ? (
            <ComingSoon what="revenue tracking" why="Connect a booking flow to see month-over-month projections." />
          ) : (
            <>
              <div className="text-sm" style={{ color: 'var(--theme-text)' }}>
                At current pace, you&apos;re on track for <strong>{fmtMoney(data.revenue_forecast.projected_end_of_month, c)}</strong> this month
              </div>
              <div className="mt-2 h-2 rounded-full overflow-hidden" style={{ background: 'var(--theme-surface2)' }}>
                <div className="h-full rounded-full" style={{ width: `${Math.min(100, data.revenue_forecast.pct_of_last_month || 0)}%`, background: 'linear-gradient(90deg, #4C1D95, #7C35DC)' }} />
              </div>
              <div className="text-[11px] mt-1.5" style={{ color: 'var(--theme-text-muted)' }}>{data.revenue_forecast.pct_of_last_month}% of last month ({fmtMoney(data.revenue_forecast.last_month_actual, c)})</div>
            </>
          )}
        </SectionCard>
      </div>

      {/* Live Conversations + Lead Sources */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-3">
          <SectionCard title="Live Conversations" sub={`${data.conversations.length} active · ARIA is handling all of them`} testid="live-conversations" action={<Link to="/app/conversations" className="text-xs font-semibold" style={{ color: 'var(--theme-purple-light)' }}>View all →</Link>}>
            {data.conversations.length === 0 ? (
              <div className="text-sm py-6 text-center" style={{ color: 'var(--theme-text-muted)' }}>No conversations in the last 2 hours.</div>
            ) : (
              <div className="divide-y" style={{ borderColor: 'var(--theme-border)' }}>
                {data.conversations.map((c) => (
                  <Link key={c.lead_id} to={`/app/leads/${c.lead_id}`} className="flex items-center gap-3 py-2.5 hover:bg-[var(--theme-surface2)] px-2 -mx-2 rounded">
                    <div className="w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold text-white shrink-0" style={{ background: 'linear-gradient(135deg, #4C1D95, #7C35DC)' }}>{c.initials}</div>
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-semibold truncate" style={{ color: 'var(--theme-text)' }}>{c.name}</div>
                      <div className="text-xs truncate" style={{ color: 'var(--theme-text-muted)' }}>{c.snippet}</div>
                    </div>
                    <StatusPill status={c.status} />
                    <div className="text-[10px]" style={{ color: 'var(--theme-text-muted)' }}>{c.minutes_ago}m</div>
                  </Link>
                ))}
              </div>
            )}
          </SectionCard>
        </div>
        <div className="lg:col-span-2 space-y-4">
          <SectionCard title="Where leads came from today" testid="lead-sources">
            {data.lead_sources.length === 0 ? (
              <div className="text-xs py-4 text-center" style={{ color: 'var(--theme-text-muted)' }}>No leads today yet.</div>
            ) : data.lead_sources.map((s) => (
              <div key={s.channel} className="mb-2 last:mb-0">
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="capitalize font-semibold" style={{ color: 'var(--theme-text)' }}>{s.channel}</span>
                  <span style={{ color: 'var(--theme-text-muted)' }}>{s.count}</span>
                </div>
                <div className="h-2 rounded-full" style={{ background: 'var(--theme-surface2)' }}>
                  <div className="h-full rounded-full" style={{ width: `${Math.min(100, s.count * 10)}%`, background: s.colour }} />
                </div>
              </div>
            ))}
          </SectionCard>
          <SectionCard title="Asset performance" testid="asset-performance">
            {data.asset_performance.coming_soon ? <ComingSoon what="asset tracking" why="Add tracked links to your lead magnets to see clicks here." /> : (
              <div className="space-y-2">
                {data.asset_performance.rows.map((a) => (
                  <div key={a.name} className="flex justify-between text-xs"><span className="truncate" style={{ color: 'var(--theme-text)' }}>{a.name}</span><span className="font-semibold" style={{ color: 'var(--theme-purple-light)' }}>{a.clicks}</span></div>
                ))}
              </div>
            )}
          </SectionCard>
        </div>
      </div>

      {/* Funnel */}
      <SectionCard title="Booking Funnel — This Week" sub={`${data.funnel[0]?.count ?? 0} leads entered top of funnel`} testid="booking-funnel">
        <div className="grid grid-cols-5 gap-2">
          {data.funnel.map((step, i) => {
            const palette = ['#6366F1', '#7C35DC', '#0E9F86', '#F59E0B', '#10B981'];
            return (
              <div key={step.stage} className="rounded-md p-3 text-center" style={{ background: palette[i], color: 'white' }}>
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

      {/* Bottom row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <SectionCard title="Active sequences" testid="sequences">
          {data.sequences.length === 0 ? <ComingSoon what="sequence data" why="Connect Lemlist to populate." /> : (
            <table className="w-full text-xs">
              <thead><tr style={{ color: 'var(--theme-text-muted)' }}><th className="text-left font-semibold pb-1">Name</th><th className="text-right font-semibold pb-1">Active</th><th className="text-right font-semibold pb-1">Booked</th><th className="text-right font-semibold pb-1">Rate</th></tr></thead>
              <tbody>
                {data.sequences.map((s) => (
                  <tr key={s.name}><td className="py-1 truncate" style={{ color: 'var(--theme-text)' }}>{s.name}</td><td className="text-right" style={{ color: 'var(--theme-text)' }}>{s.active}</td><td className="text-right" style={{ color: 'var(--theme-text)' }}>{s.booked}</td><td className="text-right font-bold" style={{ color: s.rate >= 15 ? '#10B981' : s.rate >= 5 ? '#F59E0B' : '#EF4444' }}>{s.rate}%</td></tr>
                ))}
              </tbody>
            </table>
          )}
        </SectionCard>
        <SectionCard title="Multi-touch leads" sub="Leads from 2+ channels convert higher" testid="channel-overlap">
          <ComingSoon what="multi-touch tracking" why="Connect more channels + tag lead source on every channel to see overlap." />
        </SectionCard>
        <SectionCard title="Leads to recover" sub={`${data.ghost_leads.length} warm leads gone quiet`} testid="ghost-leads">
          {data.ghost_leads.length === 0 ? <div className="text-xs text-center py-4" style={{ color: 'var(--theme-text-muted)' }}>No ghost leads — nice.</div> : data.ghost_leads.map((g) => (
            <Link to={`/app/leads/${g.id}`} key={g.id} className="block py-2 border-b last:border-b-0 hover:bg-[var(--theme-surface2)] -mx-2 px-2 rounded" style={{ borderColor: 'var(--theme-border)' }}>
              <div className="text-xs font-semibold" style={{ color: 'var(--theme-text)' }}>{g.name}</div>
              <div className="text-[11px]" style={{ color: 'var(--theme-text-muted)' }}>{g.company} · {g.days_silent}d silent</div>
            </Link>
          ))}
        </SectionCard>
      </div>
    </div>
  );
};

const StatusPill = ({ status }) => {
  const cfg = {
    live: { bg: 'rgba(236,72,153,0.15)', color: '#EC4899', text: '● Live' },
    waiting: { bg: 'rgba(245,158,11,0.15)', color: '#F59E0B', text: 'Waiting' },
    booked: { bg: 'rgba(16,185,129,0.15)', color: '#10B981', text: '✓ Booked' },
    qualified: { bg: 'rgba(59,130,246,0.15)', color: '#3B82F6', text: 'Qualified' },
  }[status] || { bg: 'var(--theme-surface2)', color: 'var(--theme-text-muted)', text: status };
  return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold" style={{ background: cfg.bg, color: cfg.color }}>{cfg.text}</span>;
};

// ───────────────────────── B2B FOUNDER ────────────────────────────
export const B2BFounderDashboard = () => {
  const { data, loading, refresh } = useDashboard('/api/dashboard/b2b-founder');
  if (loading || !data) return <div className="p-8 text-sm" style={{ color: 'var(--theme-text-muted)' }}>Loading B2B Founder dashboard…</div>;
  const c = data.header.currency;
  return (
    <div className="p-6 space-y-6 max-w-[1600px] mx-auto" data-testid="b2b-founder-dashboard">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--theme-text)' }}>{data.header.workspace_name} · Intelligence Overview</h1>
          <div className="text-xs mt-1" style={{ color: 'var(--theme-text-muted)' }}>Last refresh: {new Date(data.header.last_refresh).toLocaleTimeString()}</div>
        </div>
        <div className="flex items-center gap-3">
          <span className="px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider" style={{ background: 'rgba(124,53,220,0.15)', color: '#7C35DC' }}>B2B Founder</span>
          <Link to="/app/sales-view" className="text-xs font-semibold" style={{ color: 'var(--theme-purple-light)' }}>Switch to Sales View →</Link>
          <button onClick={refresh} className="text-xs px-3 py-1.5 rounded-md flex items-center gap-1.5" style={{ background: 'var(--theme-surface2)', color: 'var(--theme-text)' }} data-testid="b2b-founder-refresh"><ArrowsClockwise size={12} /> Refresh</button>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <KpiTile label="Leads this month" value={data.kpis.leads_month.value} trend={data.kpis.leads_month.trend} testid="kpi-leads-month" />
        <KpiTile label="High intent (≥70)" value={data.kpis.high_intent.value} trend={data.kpis.high_intent.trend} testid="kpi-high-intent" />
        <KpiTile label="Meetings" value={data.kpis.meetings.value} trend={data.kpis.meetings.trend} testid="kpi-meetings" />
        <KpiTile label="Signals" value={data.kpis.signals.value} trend={data.kpis.signals.trend} testid="kpi-signals" />
        <KpiTile label="Conversion" value={data.kpis.conv_rate.value} unit="%" trend={data.kpis.conv_rate.trend} testid="kpi-b2b-conv" />
      </div>

      {/* Momentum + ARIA Time Saved */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <div className="md:col-span-3">
          <SectionCard title="Momentum" sub={data.momentum.driver_text} testid="b2b-momentum">
            <div className="flex items-center gap-4">
              <div className="text-5xl">{data.momentum.direction === 'up' ? '🚀' : data.momentum.direction === 'down' ? '🔻' : '→'}</div>
              <div>
                <div className="text-3xl font-bold" style={{ color: 'var(--theme-text)' }}>{data.momentum.score}<span className="text-base" style={{ color: 'var(--theme-text-muted)' }}> / 100</span></div>
                <div className="text-sm mt-0.5 font-semibold" style={{ color: data.momentum.direction === 'up' ? '#10B981' : data.momentum.direction === 'down' ? '#EF4444' : '#94A3B8' }}>{data.momentum.label}</div>
              </div>
            </div>
          </SectionCard>
        </div>
        <div className="md:col-span-2">
          <SectionCard title="ARIA Time Saved" sub={`This month · ${data.aria_time_saved.hours} hours`} testid="b2b-time-saved">
            <div className="text-2xl font-bold" style={{ color: 'var(--theme-purple-light)' }}>{fmtMoney(data.aria_time_saved.money_equivalent, c)}</div>
            <div className="text-[10px] mt-2 space-y-0.5" style={{ color: 'var(--theme-text-muted)' }}>
              <div>{data.aria_time_saved.breakdown.researched} companies researched</div>
              <div>{data.aria_time_saved.breakdown.insights} insight cards generated</div>
              <div>{data.aria_time_saved.breakdown.drafts} outreach drafts written</div>
            </div>
          </SectionCard>
        </div>
      </div>

      {/* ICP Drift */}
      {data.icp_drift.drift_detected && (
        <div className="rounded-xl px-4 py-3 text-sm flex items-center gap-3" style={{ background: 'rgba(245,158,11,0.12)', color: '#D97706', border: '1px solid rgba(245,158,11,0.3)' }} data-testid="icp-drift-banner">
          <Warning size={20} weight="bold" />
          <div className="flex-1">
            <strong>ICP Drift detected.</strong> Your last 30 days of leads are {data.icp_drift.primary_pct}% primary ICP / {data.icp_drift.unknown_pct}% unknown. Channel targeting may have shifted.
          </div>
          <Link to="/app/integrations" className="text-xs font-semibold underline">Review channel settings →</Link>
        </div>
      )}

      {/* Channel Performance Table */}
      <SectionCard title="Channel Performance" sub="Which channels are working — and which aren't" testid="channel-performance-table">
        {data.channel_performance.length === 0 ? <ComingSoon what="channel data" why="Connect a lead source to populate." /> : (
          <table className="w-full text-xs">
            <thead><tr style={{ color: 'var(--theme-text-muted)' }}>
              <th className="text-left font-semibold pb-2">Channel</th><th className="text-right font-semibold">Leads</th>
              <th className="text-right font-semibold">High %</th><th className="text-right font-semibold">Meetings</th>
              <th className="text-right font-semibold">Conv %</th><th className="text-center font-semibold">Health</th>
            </tr></thead>
            <tbody>
              {data.channel_performance.map((ch) => (
                <tr key={ch.channel} className="border-t" style={{ borderColor: 'var(--theme-border)' }}>
                  <td className="py-2 font-semibold capitalize" style={{ color: 'var(--theme-text)' }}><span className="inline-block w-2 h-2 rounded-full mr-2" style={{ background: ch.colour }} />{ch.channel}</td>
                  <td className="text-right" style={{ color: 'var(--theme-text)' }}>{ch.leads}</td>
                  <td className="text-right" style={{ color: 'var(--theme-text)' }}>{ch.high_pct}%</td>
                  <td className="text-right" style={{ color: 'var(--theme-text)' }}>{ch.meetings}</td>
                  <td className="text-right font-bold" style={{ color: ch.conv_rate >= 10 ? '#10B981' : ch.conv_rate >= 5 ? '#F59E0B' : '#EF4444' }}>{ch.conv_rate}%</td>
                  <td className="text-center"><HealthBadge h={ch.health} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </SectionCard>

      {/* Signal Attribution */}
      <SectionCard title="What signals actually predict meetings" sub="Workspace-specific — needs 90+ days of data" testid="signal-attribution">
        {data.signal_attribution.coming_soon ? <ComingSoon what="attribution data" why="Need 90+ days of pipeline data + ≥3 meetings booked from signal-sourced leads." /> : null}
      </SectionCard>

      {/* Why Now + Founder Flags + Buying Committee */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <SectionCard title="Why Now — Pipeline movements (24h)" testid="why-now-feed">
          {data.why_now.length === 0 ? <div className="text-xs py-4 text-center" style={{ color: 'var(--theme-text-muted)' }}>No significant pipeline movements today.</div> : data.why_now.map((m) => (
            <Link to={`/app/leads/${m.lead_id}`} key={m.lead_id} className="block py-2 border-b last:border-b-0 hover:bg-[var(--theme-surface2)] -mx-2 px-2 rounded" style={{ borderColor: 'var(--theme-border)' }}>
              <div className="flex justify-between items-baseline">
                <div className="text-xs font-semibold" style={{ color: 'var(--theme-text)' }}>{m.name} <span className="text-[10px] font-normal" style={{ color: 'var(--theme-text-muted)' }}>· {m.company}</span></div>
                <div className={`text-xs font-bold ${m.delta > 0 ? 'text-emerald-500' : 'text-rose-500'}`}>{m.score_before} → {m.score_after} {m.delta > 0 ? '▲' : '▼'}{Math.abs(m.delta)}</div>
              </div>
              <div className="text-[11px] mt-0.5" style={{ color: 'var(--theme-text-muted)' }}>{m.reason}</div>
            </Link>
          ))}
        </SectionCard>
        <SectionCard title="Founder Flags" sub={`${data.founder_flags.length} leads need your personal attention`} testid="founder-flags">
          {data.founder_flags.length === 0 ? <div className="text-xs py-4 text-center" style={{ color: 'var(--theme-text-muted)' }}>No flags right now — clean queue.</div> : data.founder_flags.map((f) => (
            <Link to={`/app/leads/${f.lead_id}`} key={f.id} className="block py-2 border-b last:border-b-0 hover:bg-[var(--theme-surface2)] -mx-2 px-2 rounded" style={{ borderColor: 'var(--theme-border)' }}>
              <div className="text-xs font-semibold" style={{ color: 'var(--theme-text)' }}>{f.prospect_name} · <span className="font-normal" style={{ color: 'var(--theme-text-muted)' }}>{f.prospect_company}</span></div>
              <div className="text-[11px] mt-0.5 line-clamp-2" style={{ color: 'var(--theme-text-muted)' }}>{f.signal_summary}</div>
            </Link>
          ))}
        </SectionCard>
      </div>

      {/* Bottom row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <SectionCard title="Ghost lead recovery" testid="founder-ghost-leads">
          {data.ghost_leads.length === 0 ? <div className="text-xs text-center py-4" style={{ color: 'var(--theme-text-muted)' }}>No ghost leads — nice.</div> : data.ghost_leads.map((g) => (
            <Link to={`/app/leads/${g.lead_id}`} key={g.lead_id} className="block py-2 border-b last:border-b-0 hover:bg-[var(--theme-surface2)] -mx-2 px-2 rounded" style={{ borderColor: 'var(--theme-border)' }}>
              <div className="text-xs font-semibold" style={{ color: 'var(--theme-text)' }}>{g.name}</div>
              <div className="text-[11px]" style={{ color: 'var(--theme-text-muted)' }}>{g.company} · {g.days_silent}d silent · score {g.score}</div>
            </Link>
          ))}
        </SectionCard>
        <SectionCard title="Deals at risk" testid="deal-risk-flags">
          {data.deal_risk_flags.length === 0 ? <div className="text-xs text-center py-4" style={{ color: 'var(--theme-text-muted)' }}>No at-risk deals.</div> : data.deal_risk_flags.map((d) => (
            <Link to={`/app/leads/${d.lead_id}`} key={d.lead_id} className="block py-2 border-b last:border-b-0 hover:bg-[var(--theme-surface2)] -mx-2 px-2 rounded" style={{ borderColor: 'var(--theme-border)' }}>
              <div className="text-xs font-semibold" style={{ color: 'var(--theme-text)' }}>{d.name}</div>
              <div className="text-[11px]" style={{ color: 'var(--theme-text-muted)' }}>{d.company} · {d.risk_type === 'negative_reply' ? '⚠ Negative reply' : `${d.days_silent}d silent`} · score {d.score}</div>
            </Link>
          ))}
        </SectionCard>
        <SectionCard title="Monday brief preview" sub="Will land on your WhatsApp Monday 8am" testid="monday-brief">
          {(data.monday_brief_preview?.lines || []).map((l) => (
            <div key={l} className="py-1 text-xs" style={{ color: 'var(--theme-text)' }}>• {l}</div>
          ))}
        </SectionCard>
      </div>
    </div>
  );
};

const HealthBadge = ({ h }) => {
  const cfg = {
    working_well: { color: '#10B981', label: 'Working' },
    moderate: { color: '#F59E0B', label: 'Moderate' },
    needs_attention: { color: '#EF4444', label: 'Attention' },
    inactive: { color: '#94A3B8', label: 'Inactive' },
  }[h] || { color: '#94A3B8', label: h };
  return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold" style={{ background: `${cfg.color}22`, color: cfg.color }}>{cfg.label}</span>;
};

// ───────────────────────── B2B SALES ─────────────────────────────
const TopActionsCard = ({ top, onRegenerate }) => {
  const [regenerating, setRegenerating] = useState(false);
  const rows = Array.isArray(top?.rows) ? top.rows : [];
  const hasRows = rows.length > 0;
  const cacheTag = top?.cache === 'hit' ? 'cached today' : top?.cache === 'miss' ? 'just generated' : null;

  const handleRegen = async () => {
    setRegenerating(true);
    try {
      await api.post('/api/dashboard/top-actions/regenerate');
      toast.success('Regenerating today’s plan…');
      await onRegenerate?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not regenerate.');
    } finally {
      setRegenerating(false);
    }
  };

  return (
    <SectionCard
      title="ARIA's top 3 things for you to do today"
      sub={cacheTag ? `Claude Haiku · ${cacheTag}` : 'Generated daily by ARIA'}
      testid="top-3-actions"
      action={
        <button
          onClick={handleRegen}
          disabled={regenerating}
          className="text-[11px] px-2.5 py-1 rounded-md flex items-center gap-1 disabled:opacity-50"
          style={{ background: 'var(--theme-surface2)', color: 'var(--theme-text)' }}
          data-testid="top-3-regenerate"
        >
          <ArrowsClockwise size={11} weight="bold" /> {regenerating ? 'Regenerating…' : 'Regenerate'}
        </button>
      }
    >
      {top?.coming_soon || !hasRows ? (
        <ComingSoon what="Claude-generated daily plan" why={top?.reason || 'Need ≥1 hot lead OR deal risk OR pending approval to generate actions.'} />
      ) : (
        <ol className="space-y-2.5">
          {rows.map((r, i) => (
            <li key={i} className="flex gap-3 items-start" data-testid={`top-action-${i + 1}`}>
              <div className="shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white" style={{ background: 'linear-gradient(135deg, #4C1D95, #7C35DC)' }}>{i + 1}</div>
              <div className="min-w-0 flex-1">
                <div className="text-sm font-semibold" style={{ color: 'var(--theme-text)' }}>{r.action}</div>
                <div className="text-[11px] mt-0.5" style={{ color: 'var(--theme-text-muted)' }}>
                  {r.lead && <span><strong style={{ color: 'var(--theme-text)' }}>{r.lead}</strong>{r.company ? ` · ${r.company}` : ''}</span>}
                  {r.why_now && <span className="ml-2 italic">— {r.why_now}</span>}
                </div>
              </div>
            </li>
          ))}
        </ol>
      )}
    </SectionCard>
  );
};

export const B2BSalesDashboard = () => {
  const { data, loading, refresh } = useDashboard('/api/dashboard/b2b-sales');
  if (loading || !data) return <div className="p-8 text-sm" style={{ color: 'var(--theme-text-muted)' }}>Loading Sales dashboard…</div>;
  return (
    <div className="p-6 space-y-6 max-w-[1600px] mx-auto" data-testid="b2b-sales-dashboard">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--theme-text)' }}>Good morning, {data.header.first_name}</h1>
          <div className="text-xs mt-1" style={{ color: 'var(--theme-text-muted)' }}>{new Date(data.header.last_refresh).toDateString()}</div>
        </div>
        <div className="flex items-center gap-3">
          <span className="px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider" style={{ background: 'rgba(245,158,11,0.15)', color: '#F59E0B' }}>Sales View</span>
          <Link to="/app" className="text-xs font-semibold" style={{ color: 'var(--theme-purple-light)' }}>Switch to Founder View →</Link>
          <button onClick={refresh} className="text-xs px-3 py-1.5 rounded-md flex items-center gap-1.5" style={{ background: 'var(--theme-surface2)', color: 'var(--theme-text)' }} data-testid="b2b-sales-refresh"><ArrowsClockwise size={12} /> Refresh</button>
        </div>
      </div>

      {/* Top 3 actions */}
      <TopActionsCard top={data.top_actions} onRegenerate={refresh} />

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiTile label="Follow-ups due" value={data.kpis.followups_today} testid="kpi-followups" />
        <KpiTile label="Meetings today" value={data.kpis.meetings_today} testid="kpi-meetings-today" />
        <KpiTile label="Approvals pending" value={data.kpis.approvals_pending} testid="kpi-approvals" />
        <KpiTile label="Pipeline value" value={`$${(data.kpis.pipeline_value.value || 0).toLocaleString()}`} trend={data.kpis.pipeline_value.trend} testid="kpi-sales-pipeline" />
      </div>

      {/* Hot leads */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {data.hot_leads.length === 0 ? (
          <div className="md:col-span-3"><ComingSoon what="hot leads" why="No leads scoring ≥60 yet — add lemlist or import leads to populate." /></div>
        ) : data.hot_leads.map((l) => (
          <Link to={`/app/leads/${l.id}`} key={l.id} className="rounded-xl border p-4 hover:shadow-lg transition" style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }} data-testid={`hot-lead-${l.id}`}>
            <div className="flex justify-between items-start">
              <div>
                <div className="text-sm font-bold" style={{ color: 'var(--theme-text)' }}>{l.name}</div>
                <div className="text-[11px]" style={{ color: 'var(--theme-text-muted)' }}>{l.title} · {l.company}</div>
              </div>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold" style={{ background: l.score >= 70 ? 'rgba(16,185,129,0.15)' : 'rgba(245,158,11,0.15)', color: l.score >= 70 ? '#10B981' : '#F59E0B' }}>{l.score}</span>
            </div>
            {l.signal_type && <div className="mt-2"><span className="px-2 py-0.5 rounded-full text-[10px] font-bold" style={{ background: 'rgba(124,53,220,0.15)', color: '#7C35DC' }}>{l.signal_type}</span></div>}
            <div className="mt-2 text-[10px]" style={{ color: 'var(--theme-text-muted)' }}>{l.lemlist_summary} · via {l.source}</div>
          </Link>
        ))}
      </div>

      {/* Pipeline + Agenda + Approvals */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-3">
          <SectionCard title="Your pipeline" testid="pipeline-table" action={<Link to="/app/leads" className="text-xs font-semibold" style={{ color: 'var(--theme-purple-light)' }}>Full view →</Link>}>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead><tr style={{ color: 'var(--theme-text-muted)' }}><th className="text-left font-semibold pb-1">Name</th><th className="text-left font-semibold">Company</th><th className="text-right font-semibold">Score</th><th className="text-center font-semibold">Stage</th></tr></thead>
                <tbody>
                  {data.pipeline.slice(0, 12).map((lead) => (
                    <tr key={lead.id} className="border-t" style={{ borderColor: 'var(--theme-border)' }}>
                      <td className="py-1.5 truncate"><Link to={`/app/leads/${lead.id}`} style={{ color: 'var(--theme-text)' }} className="font-semibold hover:text-purple-400">{lead.first_name} {lead.last_name}</Link></td>
                      <td className="truncate" style={{ color: 'var(--theme-text-muted)' }}>{lead.company_name}</td>
                      <td className="text-right" style={{ color: 'var(--theme-text)' }}>{lead.score}</td>
                      <td className="text-center"><PipelineStagePill s={lead.pipeline_stage} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </SectionCard>
        </div>
        <div className="lg:col-span-2 space-y-4">
          <SectionCard title="Today's agenda" testid="agenda">
            {data.agenda.length === 0 ? <div className="text-xs text-center py-4" style={{ color: 'var(--theme-text-muted)' }}>No meetings or follow-ups today.</div> : data.agenda.map((a) => (
              <div key={a.lead_id + a.when} className="py-1.5 text-xs">
                <span className="font-bold mr-2" style={{ color: 'var(--theme-purple-light)' }}>{new Date(a.when).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}</span>
                <span style={{ color: 'var(--theme-text)' }}>{a.lead_name}</span>
                <span style={{ color: 'var(--theme-text-muted)' }}> · {a.company}</span>
              </div>
            ))}
          </SectionCard>
          <SectionCard title="Approval queue" sub={`${data.approval_queue.length} pending`} testid="approval-queue" action={<Link to="/app/approvals" className="text-xs font-semibold" style={{ color: 'var(--theme-purple-light)' }}>All →</Link>}>
            {data.approval_queue.length === 0 ? <div className="text-xs text-center py-4" style={{ color: 'var(--theme-text-muted)' }}>Queue empty.</div> : data.approval_queue.map((a) => (
              <Link to={`/app/leads/${a.lead_id}`} key={a.id} className="block py-2 border-b last:border-b-0 hover:bg-[var(--theme-surface2)] -mx-2 px-2 rounded" style={{ borderColor: 'var(--theme-border)' }}>
                <div className="text-xs font-semibold" style={{ color: 'var(--theme-text)' }}>{a.prospect_name}</div>
                <div className="text-[11px] mt-0.5 line-clamp-2" style={{ color: 'var(--theme-text-muted)' }}>{a.suggested_message}</div>
              </Link>
            ))}
          </SectionCard>
        </div>
      </div>

      {/* Bottom row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <SectionCard title="Deal risk flags" testid="sales-deal-risk">
          {data.deal_risk_flags.length === 0 ? <div className="text-xs text-center py-4" style={{ color: 'var(--theme-text-muted)' }}>No flagged deals.</div> : data.deal_risk_flags.map((d) => (
            <Link to={`/app/leads/${d.lead_id}`} key={d.lead_id} className="block py-2 border-b last:border-b-0 -mx-2 px-2 rounded hover:bg-[var(--theme-surface2)]" style={{ borderColor: 'var(--theme-border)' }}>
              <div className="text-xs font-semibold" style={{ color: 'var(--theme-text)' }}>{d.name} · <span style={{ color: 'var(--theme-text-muted)' }}>{d.company}</span></div>
              <div className="text-[11px]" style={{ color: '#EF4444' }}>{d.days_silent}d silent</div>
            </Link>
          ))}
        </SectionCard>
        <SectionCard title="What's actually closing deals" testid="sales-attribution">
          {Array.isArray(data.attribution_top3) && data.attribution_top3.length > 0 ? (
            <div className="space-y-1.5">
              {data.attribution_top3.map((a, i) => (
                <div key={a.signal_type} className="flex justify-between text-xs"><span style={{ color: 'var(--theme-text)' }}>{i + 1}. {a.signal_type}</span><span className="font-bold" style={{ color: '#7C35DC' }}>{a.conv_rate}%</span></div>
              ))}
            </div>
          ) : <ComingSoon what="signal attribution" why="Need ≥3 leads per signal type with booked meetings." />}
        </SectionCard>
        <SectionCard title="Ghost lead recovery" testid="sales-ghost-leads">
          {data.ghost_leads.length === 0 ? <div className="text-xs text-center py-4" style={{ color: 'var(--theme-text-muted)' }}>No ghosts.</div> : data.ghost_leads.map((g) => (
            <Link to={`/app/leads/${g.lead_id}`} key={g.lead_id} className="block py-2 border-b last:border-b-0 -mx-2 px-2 rounded hover:bg-[var(--theme-surface2)]" style={{ borderColor: 'var(--theme-border)' }}>
              <div className="text-xs font-semibold" style={{ color: 'var(--theme-text)' }}>{g.name}</div>
              <div className="text-[11px]" style={{ color: 'var(--theme-text-muted)' }}>{g.company} · {g.days_silent}d</div>
            </Link>
          ))}
        </SectionCard>
      </div>
    </div>
  );
};

const PipelineStagePill = ({ s }) => {
  const cfg = {
    'Hot': { bg: 'rgba(16,185,129,0.15)', color: '#10B981' },
    'Meeting Set': { bg: 'rgba(124,53,220,0.15)', color: '#7C35DC' },
    'Warm': { bg: 'rgba(245,158,11,0.15)', color: '#F59E0B' },
    'Cold': { bg: 'rgba(148,163,184,0.15)', color: '#94A3B8' },
  }[s] || { bg: 'var(--theme-surface2)', color: 'var(--theme-text-muted)' };
  return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold" style={{ background: cfg.bg, color: cfg.color }}>{s}</span>;
};

// ───────────────────────── Router ───────────────────────────────
export const DashboardRouter = ({ forceMode }) => {
  const [mode, setMode] = useState(null);
  useEffect(() => {
    if (forceMode) { setMode(forceMode); return; }
    api.get('/api/dashboard/_mode')
      .then(r => setMode(r.data?.mode || 'hybrid'))
      .catch(() => setMode('hybrid'));
  }, [forceMode]);
  if (!mode) return <div className="p-8 text-sm" style={{ color: 'var(--theme-text-muted)' }}>Loading dashboard…</div>;
  if (mode === 'b2c') return <B2CDashboard />;
  if (mode === 'b2b') return <B2BFounderDashboard />;
  // hybrid → default to founder view (richest signal density). Sales view available as /app/sales-view.
  return <B2BFounderDashboard />;
};

export default DashboardRouter;
