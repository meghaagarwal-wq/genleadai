/**
 * AriaDemoPulse — iter177
 *
 * Founder-facing feed of recent demo sessions. Shows company, mode,
 * dwell time, source, prospect identity (if given), and whether they
 * clicked "Book". Auto-refreshes every 30s.
 *
 * Rendered on the light-mode brand palette (not the dark/violet dashboard)
 * because this is YOUR surface, not a prospect-facing one.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  RefreshCw, ArrowUpRight, Flame, CheckCircle2, Clock, Users, Globe, ExternalLink, Mail,
} from 'lucide-react';

const T = {
  canvas: '#F7F6F1',
  card:   '#FFFFFF',
  accent: '#7C35DC',
  ink:    '#1C1917',
  muted:  '#78716C',
  line:   '#E7E5DE',
  success:'#15803D',
  warn:   '#B45309',
  danger: '#B91C1C',
  fontDisplay: '"Fraunces", "Plus Jakarta Sans", ui-serif, serif',
  fontUi:      '"Plus Jakarta Sans", "Inter", system-ui, sans-serif',
};

export default function AriaDemoPulse() {
  const [data, setData]       = useState({ totals: {}, sessions: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');
  const [tab, setTab]         = useState('all'); // all | warm | identified | booked
  const apiUrl = process.env.REACT_APP_BACKEND_URL || '';

  async function load() {
    try {
      const res = await fetch(`${apiUrl}/api/demo-analytics/pulse?limit=200`);
      const j = await res.json();
      setData(j); setError('');
    } catch (e) { setError(e?.message || 'Failed to load'); }
    finally   { setLoading(false); }
  }

  useEffect(() => {
    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const sessions = useMemo(() => {
    const all = data.sessions || [];
    if (tab === 'warm')       return all.filter((s) => s.warm);
    if (tab === 'identified') return all.filter((s) => s.identify);
    if (tab === 'booked')     return all.filter((s) => s.book_clicked);
    return all;
  }, [data, tab]);

  return (
    <div className="min-h-screen" style={{ background: T.canvas, color: T.ink, fontFamily: T.fontUi }} data-testid="demo-pulse">
      <header className="w-full border-b sticky top-0 z-20 backdrop-blur"
        style={{ background: 'rgba(247,246,241,0.85)', borderColor: T.line }}>
        <div className="max-w-[1200px] mx-auto px-6 py-4 flex items-center justify-between gap-4 flex-wrap">
          <div className="min-w-0">
            <div className="uppercase text-[11px] tracking-[0.18em]" style={{ color: T.accent, fontWeight: 700 }}>
              Founder Pulse
            </div>
            <h1 className="text-[26px] leading-tight font-semibold tracking-tight"
              style={{ fontFamily: T.fontDisplay, letterSpacing: '-0.015em' }}>
              Who's exploring the demo?
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <Link
              to="/aria-demo"
              className="text-xs inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full"
              style={{ background: T.card, color: T.ink, border: `1px solid ${T.line}` }}
              data-testid="pulse-opendemo">
              <ExternalLink size={11} /> Open the demo
            </Link>
            <button onClick={() => { setLoading(true); load(); }}
              className="text-xs inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full"
              style={{ background: T.accent, color: '#fff', fontWeight: 600 }}
              data-testid="pulse-refresh">
              <RefreshCw size={11} className={loading ? 'animate-spin' : ''} /> Refresh
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-[1200px] mx-auto px-6 py-8">
        {/* Totals */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          <Totals label="Sessions"   value={data.totals?.sessions || 0}   icon={Users}      hue={T.accent} />
          <Totals label="Warm"       value={data.totals?.warm || 0}       icon={Flame}      hue={T.warn} />
          <Totals label="Identified" value={data.totals?.identified || 0} icon={Mail}       hue={T.ink} />
          <Totals label="Booked"     value={data.totals?.booked || 0}     icon={CheckCircle2} hue={T.success} />
        </div>

        {/* Filter pills */}
        <div className="flex items-center gap-1.5 mb-5 flex-wrap">
          {[
            ['all',        'All'],
            ['warm',       `Warm — ≥3 min, no book`],
            ['identified', 'Identified'],
            ['booked',     'Booked'],
          ].map(([k, label]) => {
            const on = tab === k;
            return (
              <button key={k} onClick={() => setTab(k)}
                className="text-xs px-3 py-1.5 rounded-full transition-colors"
                data-testid={`pulse-filter-${k}`}
                style={{
                  background: on ? T.ink : T.card,
                  color: on ? '#fff' : T.ink,
                  border: `1px solid ${on ? T.ink : T.line}`,
                  fontWeight: on ? 600 : 500,
                }}>
                {label}
              </button>
            );
          })}
        </div>

        {error && (
          <div className="rounded-xl px-4 py-3 mb-4 text-sm" style={{ background: 'rgba(185,28,28,0.08)', color: T.danger, border: `1px solid ${T.line}` }}>
            {error}
          </div>
        )}

        {/* Table */}
        <div className="rounded-2xl overflow-hidden" style={{ background: T.card, border: `1px solid ${T.line}` }}>
          <table className="w-full text-sm" data-testid="pulse-table">
            <thead>
              <tr style={{ borderBottom: `1px solid ${T.line}` }}>
                {['When', 'Company', 'Mode', 'Dwell', 'Source', 'Identity', 'Signals', ''].map((h) => (
                  <th key={h} className="text-left px-4 py-3 text-[11px] uppercase tracking-[0.12em]"
                    style={{ color: T.muted, fontWeight: 600 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <Row key={s.session_id} s={s} />
              ))}
              {sessions.length === 0 && (
                <tr><td colSpan={8} className="px-4 py-12 text-center text-sm" style={{ color: T.muted }}>
                  No sessions yet. When a prospect opens the demo, they'll land here within seconds.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>

        <p className="text-xs mt-4" style={{ color: T.muted }}>
          Auto-refreshes every 30 seconds · Last tick {new Date().toLocaleTimeString()}
        </p>
      </main>
    </div>
  );
}

function Totals({ label, value, icon: Icon, hue }) {
  return (
    <div className="rounded-xl p-4" style={{ background: T.card, border: `1px solid ${T.line}` }}>
      <div className="inline-flex items-center gap-1.5 text-[11px] uppercase tracking-[0.14em]"
        style={{ color: T.muted, fontWeight: 600 }}>
        <Icon size={11} style={{ color: hue }} /> {label}
      </div>
      <div className="text-[26px] font-semibold tabular-nums mt-1"
        style={{ fontFamily: T.fontDisplay, color: T.ink }}>
        {value}
      </div>
    </div>
  );
}

function Row({ s }) {
  const when   = s.last_seen_at ? new Date(s.last_seen_at) : null;
  const dwell  = fmtDwell(s.dwell_sec);
  const company = s.company || '—';
  const demoHref = s.company
    ? `/aria-demo?company=${encodeURIComponent(s.company)}${s.mode ? '&mode=' + s.mode : ''}${s.scenario && s.scenario !== 'default' ? '&scenario=' + s.scenario : ''}`
    : '/aria-demo';
  const sinceAgo = when ? timeAgo(when) : '—';
  return (
    <tr style={{ borderBottom: `1px solid ${T.line}` }} data-testid={`pulse-row-${s.session_id}`}>
      <td className="px-4 py-3 whitespace-nowrap text-xs" style={{ color: T.muted }}>{sinceAgo}</td>
      <td className="px-4 py-3 font-medium" style={{ color: T.ink }}>
        <div className="flex items-center gap-2">
          {s.company && <Globe size={12} style={{ color: T.muted }} />}
          <span className="truncate max-w-[220px]">{company}</span>
        </div>
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-1.5 text-xs">
          <span className="px-2 py-0.5 rounded-full" style={{ background: '#EEF0F7', color: '#1C1917', fontWeight: 600 }}>
            {(s.mode || '—').toUpperCase()}
          </span>
          {s.scenario && s.scenario !== 'default' && (
            <span className="text-[11px]" style={{ color: T.muted }}>· {s.scenario}</span>
          )}
        </div>
      </td>
      <td className="px-4 py-3 tabular-nums text-sm">
        <span className="inline-flex items-center gap-1.5">
          <Clock size={11} style={{ color: T.muted }} /> {dwell}
        </span>
      </td>
      <td className="px-4 py-3 text-xs" style={{ color: T.muted }}>{s.source || '—'}</td>
      <td className="px-4 py-3 text-xs">
        {s.identify ? (
          <div className="flex flex-col">
            <span style={{ color: T.ink, fontWeight: 600 }}>{s.identify.name || '—'}</span>
            <a href={`mailto:${s.identify.email}`} style={{ color: T.accent }}>{s.identify.email}</a>
          </div>
        ) : <span style={{ color: T.muted }}>—</span>}
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-1 flex-wrap">
          {s.warm && (
            <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full font-semibold"
              style={{ background: 'rgba(180,83,9,0.12)', color: T.warn }}>
              <Flame size={10} /> Warm
            </span>
          )}
          {s.book_clicked && (
            <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full font-semibold"
              style={{ background: 'rgba(21,128,61,0.12)', color: T.success }}>
              <CheckCircle2 size={10} /> Booked
            </span>
          )}
          {!s.warm && !s.book_clicked && (
            <span className="text-[11px]" style={{ color: T.muted }}>—</span>
          )}
        </div>
      </td>
      <td className="px-4 py-3 text-right">
        <Link to={demoHref} className="text-xs inline-flex items-center gap-1" style={{ color: T.accent, fontWeight: 600 }}
          data-testid={`pulse-open-${s.session_id}`}>
          Open <ArrowUpRight size={11} />
        </Link>
      </td>
    </tr>
  );
}

// ─── helpers ───
function fmtDwell(sec) {
  const s = Math.max(0, parseInt(sec || 0, 10));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60), r = s % 60;
  return r ? `${m}m ${r}s` : `${m}m`;
}
function timeAgo(d) {
  const diff = Math.max(0, Date.now() - d.getTime()) / 1000;
  if (diff < 60)       return 'just now';
  if (diff < 3600)     return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400)    return `${Math.floor(diff / 3600)}h ago`;
  return d.toLocaleDateString();
}
