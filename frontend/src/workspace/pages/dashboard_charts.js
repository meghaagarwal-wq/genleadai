/**
 * Dashboard chart primitives (iter157).
 *
 * Single home for reusable visual pieces — sparklines, radial gauge,
 * tapered funnel, horizontal bars. Keeps `Dashboards.js` lean and prevents
 * each widget from re-inventing chart styling.
 *
 * Rule: charts REPLACE the text/numbers they visualise — never duplicate.
 */
import React from 'react';
import {
  ResponsiveContainer, AreaChart, Area, LineChart, Line,
  BarChart, Bar, XAxis, YAxis, Tooltip, Cell, RadialBarChart, RadialBar, PolarAngleAxis,
} from 'recharts';

// ───────────────────────── Sparkline ─────────────────────────────
// Tiny area-line that sits inside a KPI tile. `data` is a list of numbers
// (oldest → newest) OR a list of {date, value} points. Tooltip shows
// the per-bucket date + value on hover.
export const Sparkline = ({ data, color, height = 32, valueLabel = '' }) => {
  if (!data || data.length < 2) return null;
  // Normalise — accept both number[] and {date, value}[].
  const points = data.map((d, i) => {
    if (typeof d === 'number') {
      const dt = new Date();
      dt.setUTCDate(dt.getUTCDate() - (data.length - 1 - i));
      return { i, v: d, date: dt.toISOString().slice(0, 10) };
    }
    return { i, v: d.value ?? d.v ?? 0, date: d.date };
  });
  const delta = points[points.length - 1].v - points[0].v;
  const stroke = color || (delta > 0 ? '#10B981' : delta < 0 ? '#EF4444' : '#94A3B8');
  const gradId = `spk-${stroke.replace('#', '')}-${Math.floor(Math.random() * 1000)}`;
  return (
    <div style={{ width: '100%', height }} data-testid="sparkline">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={points} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"  stopColor={stroke} stopOpacity={0.35} />
              <stop offset="100%" stopColor={stroke} stopOpacity={0} />
            </linearGradient>
          </defs>
          <Tooltip
            cursor={{ stroke, strokeWidth: 1, strokeDasharray: '3 3', opacity: 0.4 }}
            contentStyle={{ fontSize: 10, padding: '4px 8px', background: 'var(--theme-surface, #fff)', border: '1px solid var(--theme-border, #E5E7EB)', borderRadius: 4 }}
            labelStyle={{ display: 'none' }}
            formatter={(value, _name, ctx) => [
              <span key="v"><strong style={{ color: stroke }}>{value}{valueLabel ? ` ${valueLabel}` : ''}</strong> on <span style={{ color: 'var(--theme-text-muted)' }}>{ctx?.payload?.date}</span></span>,
              '',
            ]}
          />
          <Area type="monotone" dataKey="v" stroke={stroke} strokeWidth={1.75} fill={`url(#${gradId})`} dot={false} isAnimationActive />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};

// ───────────────────────── Radial gauge ──────────────────────────
// Replaces the "78 / 100" momentum number — a single-arc radial chart
// from 0–100. Color shifts with score band.
export const RadialGauge = ({ score = 0, label, sub, size = 160 }) => {
  const v = Math.max(0, Math.min(100, score));
  const color = v >= 70 ? '#10B981' : v >= 40 ? '#F59E0B' : '#EF4444';
  const data = [{ name: 'score', value: v, fill: color }];
  return (
    <div className="flex items-center gap-4" data-testid="radial-gauge">
      <div style={{ width: size, height: size, position: 'relative' }}>
        <ResponsiveContainer>
          <RadialBarChart cx="50%" cy="50%" innerRadius="68%" outerRadius="100%" barSize={14} data={data} startAngle={90} endAngle={-270}>
            <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
            <RadialBar background={{ fill: 'var(--theme-surface2, #F3F4F6)' }} dataKey="value" cornerRadius={8} isAnimationActive />
          </RadialBarChart>
        </ResponsiveContainer>
        <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          <div className="text-3xl font-bold" style={{ color }}>{v}</div>
          <div className="text-[10px] uppercase tracking-[0.18em]" style={{ color: 'var(--theme-text-muted)' }}>/ 100</div>
        </div>
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-base font-bold" style={{ color }}>{label}</div>
        {sub && <div className="text-xs mt-0.5" style={{ color: 'var(--theme-text-muted)' }}>{sub}</div>}
      </div>
    </div>
  );
};

// ───────────────────────── Tapered Funnel ───────────────────────
// Real funnel — each stage gets a trapezoid whose width = count/maxCount.
// `steps`: [{ stage, count, pct_of_prev }]
export const TaperedFunnel = ({ steps = [] }) => {
  if (!steps.length) return null;
  const max = Math.max(...steps.map(s => s.count || 0), 1);
  const palette = ['#6366F1', '#7C35DC', '#EC4899', '#F59E0B', '#10B981'];
  return (
    <div className="space-y-1" data-testid="tapered-funnel">
      {steps.map((s, i) => {
        const widthPct = Math.max(15, Math.round((s.count / max) * 100));
        const colour = palette[i % palette.length];
        return (
          <div key={s.stage} className="relative" style={{ marginLeft: `${(100 - widthPct) / 2}%`, width: `${widthPct}%` }}>
            <div className="rounded-md text-white px-3 py-2 flex items-center justify-between text-xs font-semibold transition-all hover:scale-[1.02]" style={{ background: colour, boxShadow: `0 6px 18px ${colour}40` }}>
              <span>{s.stage}</span>
              <span className="font-bold">{s.count}</span>
            </div>
            {i > 0 && (
              <div className="text-[10px] text-center mt-0.5" style={{ color: 'var(--theme-text-muted)' }}>
                {s.pct_of_prev}% of {steps[i - 1].stage}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

// ───────────────────────── Horizontal Bars ──────────────────────
// Compact horizontal bars — used for asset performance, signal attribution,
// sequences. `rows`: [{ label, value, sub, color }]. `maxValue` is the
// scale ceiling (defaults to max of values).
export const HBars = ({ rows = [], unit = '', maxValue, height = 12, color, valueFmt }) => {
  if (!rows.length) return null;
  const max = maxValue ?? Math.max(...rows.map(r => r.value || 0), 1);
  return (
    <div className="space-y-2.5" data-testid="h-bars">
      {rows.map((r, i) => {
        const widthPct = Math.max(4, Math.round((r.value / max) * 100));
        const c = r.color || color || '#7C35DC';
        return (
          <div key={r.label + i}>
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="font-semibold truncate" style={{ color: 'var(--theme-text)' }}>{r.label}</span>
              <span className="font-bold tabular-nums" style={{ color: c }}>{valueFmt ? valueFmt(r) : `${r.value}${unit}`}</span>
            </div>
            <div className="rounded-full overflow-hidden" style={{ height, background: 'var(--theme-surface2)' }}>
              <div className="h-full rounded-full transition-all" style={{ width: `${widthPct}%`, background: `linear-gradient(90deg, ${c}aa, ${c})` }} />
            </div>
            {r.sub && <div className="text-[10px] mt-0.5" style={{ color: 'var(--theme-text-muted)' }}>{r.sub}</div>}
          </div>
        );
      })}
    </div>
  );
};

// ───────────────────────── Vertical mini bar chart ──────────────
// 5–10 bars. Used for channel performance where stacking on horizontal
// would be cramped. `data`: [{ name, value, [secondaryValue] }].
export const MiniBarChart = ({ data = [], dataKey = 'value', secondaryKey, height = 140, color = '#7C35DC' }) => {
  if (!data.length) return null;
  return (
    <div style={{ width: '100%', height }} data-testid="mini-bar-chart">
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 8, right: 4, bottom: 0, left: -22 }}>
          <XAxis dataKey="name" tick={{ fontSize: 10, fill: 'var(--theme-text-muted)' }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 10, fill: 'var(--theme-text-muted)' }} axisLine={false} tickLine={false} />
          <Tooltip
            cursor={{ fill: 'var(--theme-surface2)' }}
            contentStyle={{ fontSize: 11, background: 'var(--theme-surface)', border: '1px solid var(--theme-border)', borderRadius: 6 }}
          />
          <Bar dataKey={dataKey} radius={[4, 4, 0, 0]} fill={color} isAnimationActive>
            {data.map((d, i) => (
              <Cell key={i} fill={d.color || color} />
            ))}
          </Bar>
          {secondaryKey && (
            <Bar dataKey={secondaryKey} radius={[4, 4, 0, 0]} fill="#10B981" isAnimationActive />
          )}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

// ───────────────────────── Score Trajectory (inline sparkline) ──
// Tiny inline sparkline that sits to the right of a lead row in the
// Why-Now feed. Shows the lead's last 5 score points.
export const InlineSparkline = ({ values = [], width = 56, height = 18, color = '#7C35DC' }) => {
  if (!values || values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const stepX = width / (values.length - 1);
  const points = values.map((v, i) => `${i * stepX},${height - ((v - min) / range) * height}`).join(' ');
  return (
    <svg width={width} height={height} data-testid="inline-sparkline" style={{ overflow: 'visible' }}>
      <polyline fill="none" stroke={color} strokeWidth="1.5" points={points} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={(values.length - 1) * stepX} cy={height - ((values[values.length - 1] - min) / range) * height} r={2.2} fill={color} />
    </svg>
  );
};
