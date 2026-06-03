/**
 * CommandCenter — iter109 Batch 2 rebuild.
 *
 * Matches the Aria_Dashboard_Layouts.html reference exactly:
 *   - Sticky topbar with dynamic Pull buttons + Aria rescore + ARIA · LISTENING
 *     pill + AI Summary + Add Lead/Prospect + bell (handled by AppLayout's
 *     own topbar; this page adds the Pull buttons row).
 *   - Mode bar — purple (B2B) / amber (B2C) / teal (Hybrid).
 *   - Purple gradient hero with mode-specific copy + 3 CTAs.
 *   - 4-column KPI grid — values come from /api/aria/command-center/kpis.
 *   - B2B: Today's Instinct Signals (top 2 cards) + Top Prospect strip.
 *   - B2C: Lead Pipeline table + "What lights up here" chips.
 *   - Hybrid: Split panel (Instinct B2B left / Automation B2C right) +
 *     Combined Pipeline KPI row.
 */
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import {
  ArrowRight, Clock, Lightning, PlayCircle, Plus, Upload, Sparkle, CompassTool,
  CircleNotch, Sun, Trophy, Fire,
} from '@phosphor-icons/react';
import { useAuth } from '../../context/AuthContext';
import { ptApi } from '../shared';
import api from '../../config/api';

// iter143 — Lemlist Pipeline Health card. Renders only on the Pietential workspace.
const LemlistPipelineHealthCard = () => {
  const [data, setData] = useState(null);
  const [active, setActive] = useState(null);

  useEffect(() => {
    try {
      const raw = localStorage.getItem('active_tenant');
      if (raw) setActive(JSON.parse(raw));
    } catch (e) { /* private mode */ }
    const onTenant = () => {
      try { setActive(JSON.parse(localStorage.getItem('active_tenant') || 'null')); } catch (e) { /* ignore */ }
    };
    window.addEventListener('aria:tenant-changed', onTenant);
    return () => window.removeEventListener('aria:tenant-changed', onTenant);
  }, []);

  const isPietential = active && (active.id === 'ten_pietential' || (active.name || '').toLowerCase().includes('pietential'));

  useEffect(() => {
    if (!isPietential) { setData(null); return undefined; }
    let alive = true;
    api.get('/api/pietential/pipeline-health')
      .then((r) => { if (alive) setData(r.data); })
      .catch(() => { if (alive) setData(null); });
    return () => { alive = false; };
  }, [isPietential]);

  if (!isPietential || !data) return null;

  const staleAlert = (data.high_intent_stale || 0) > 5;
  return (
    <div
      data-testid="lemlist-pipeline-health-card"
      className="rounded-xl border p-4 md:p-5"
      style={{
        background: 'linear-gradient(135deg, rgba(124,53,220,0.06) 0%, rgba(192,68,224,0.04) 100%)',
        borderColor: staleAlert ? '#D97706' : '#E8E0F5',
      }}
    >
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="text-[10px] font-extrabold uppercase tracking-[0.18em]" style={{ color: '#7C35DC' }}>
            Lemlist Pipeline Health
          </div>
          <div className="text-xs text-[#5A4A7A] mt-0.5">
            Pulled every 30 min · Daily scan 07:30 IST · Weekly report Mon 08:00 IST
          </div>
        </div>
        {staleAlert && (
          <span data-testid="lemlist-stale-alert" className="text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded-full bg-amber-100 text-amber-800">
            {data.high_intent_stale} hot leads untouched 48h+
          </span>
        )}
      </div>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <StatTile label="Active Lemlist leads" value={data.total_active_lemlist_leads} testid="lph-total-active" />
        <StatTile label="High intent" value={data.high_intent} testid="lph-high-intent" />
        <StatTile label="Awaiting enrichment" value={data.awaiting_enrichment} testid="lph-awaiting" />
        <StatTile label="Signals this week" value={data.signals_this_week} testid="lph-signals" />
        <StatTile
          label="Last weekly report"
          value={data.last_weekly_report ? new Date(data.last_weekly_report).toLocaleDateString() : '—'}
          testid="lph-last-report"
        />
      </div>
    </div>
  );
};

const StatTile = ({ label, value, testid }) => (
  <div data-testid={testid} className="bg-white border border-[#E8E0F5] rounded-lg px-3 py-2.5">
    <div className="text-[10px] uppercase tracking-wider text-[#9B8AB0] font-bold">{label}</div>
    <div className="text-xl md:text-2xl font-extrabold text-[#1A0A2E] mt-0.5">{value}</div>
  </div>
);

const greeting = () => {
  const h = new Date().getHours();
  if (h < 12) return 'Good morning';
  if (h < 17) return 'Good afternoon';
  return 'Good evening';
};

const firstNameOf = (u) => {
  if (!u) return 'founder';
  const n = (u.full_name || u.email || '').trim();
  return (n.split(/\s+/)[0] || n.split('@')[0] || 'founder').replace(/^./, (c) => c.toUpperCase());
};

const PROVIDER_LABEL = {
  saleshandy: 'Saleshandy', lemlist: 'Lemlist', instantly: 'Instantly',
  smartlead: 'Smartlead', meta_ads: 'Meta Ads', google_ads: 'Google Ads',
  linkedin_ads: 'LinkedIn Ads', gmail: 'Gmail', outlook: 'Outlook', apollo: 'Apollo',
};

const MODE_THEME = {
  b2b:    { dot: '#a78bfa', color: '#a78bfa', label: 'B2B Instinct Mode',
            desc: 'ARIA researches your prospects daily and surfaces the right moment to reach out' },
  b2c:    { dot: '#f59e0b', color: '#f59e0b', label: 'B2C Automation Mode',
            desc: 'ARIA qualifies, nurtures and books calls automatically across WhatsApp, email and LinkedIn' },
  hybrid: { dot: '#14b8a6', color: '#14b8a6', label: 'Hybrid Mode',
            desc: 'Instinct for your B2B prospects · Automation for your B2C leads · Both running simultaneously' },
};


// ── PullBar: dynamic Pull-from-X buttons + Aria rescore ─────────────────
const PullBar = ({ onChange }) => {
  const [connected, setConnected] = useState(null);
  const [busy, setBusy] = useState({});

  useEffect(() => {
    let alive = true;
    ptApi.get('/api/pt/integrations').then((r) => {
      if (!alive) return;
      const all = [...(r.data.primary || []), ...(r.data.future || [])];
      setConnected(all.filter((x) => x.connected && PROVIDER_LABEL[x.name]));
    }).catch(() => { if (alive) setConnected([]); });
    return () => { alive = false; };
  }, []);

  const isFresh = (last_sync) => {
    if (!last_sync) return false;
    try {
      const diff = (Date.now() - new Date(last_sync).getTime()) / 1000 / 60 / 60;
      return diff < 1;
    } catch { return false; }
  };

  const doPull = async (provider) => {
    setBusy((b) => ({ ...b, [provider]: true }));
    try {
      await ptApi.post(`/api/pt/integrations/${provider}/pull-leads`, { max_prospects: 50, auto_score: true });
      toast.success(`Pulled from ${PROVIDER_LABEL[provider]}`);
      onChange?.();
    } catch (e) {
      toast.info(`Pull from ${PROVIDER_LABEL[provider]} — coming soon`);
    } finally { setBusy((b) => ({ ...b, [provider]: false })); }
  };

  const rescore = async () => {
    setBusy((b) => ({ ...b, _rescore: true }));
    try {
      await ptApi.post('/api/pt/leads/rescore-all', {});
      toast.success('Aria rescored your leads');
      onChange?.();
    } catch (_) {
      toast.info('Aria rescore — coming soon');
    } finally { setBusy((b) => ({ ...b, _rescore: false })); }
  };

  if (connected === null) return <div data-testid="cmd-pullbar-loading" className="h-9" />;

  return (
    <div className="flex items-center gap-2 flex-wrap" data-testid="cmd-pullbar">
      {connected.length === 0 ? (
        <Link
          to="/app/integrations"
          data-testid="cmd-pullbar-connect-integration"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border text-xs font-semibold transition-colors"
          style={{ borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text-muted)' }}
        >
          <CompassTool size={14} /> Connect an integration <ArrowRight size={10} weight="bold" />
        </Link>
      ) : (
        connected.map((p) => {
          const fresh = isFresh(p.last_sync || p.connected_at);
          return (
            <button
              key={p.name}
              onClick={() => doPull(p.name)}
              disabled={!!busy[p.name]}
              data-testid={`cmd-pullbar-${p.name}`}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border text-xs font-medium disabled:opacity-50 transition-colors hover:border-violet-500 hover:text-violet-300"
              style={{ borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text-muted)' }}
            >
              <span className="w-1.5 h-1.5 rounded-full" style={{ background: fresh ? '#22c55e' : '#f59e0b' }} />
              {busy[p.name] ? 'Pulling…' : `Pull from ${PROVIDER_LABEL[p.name]}`}
            </button>
          );
        })
      )}
      <button
        onClick={rescore}
        disabled={!!busy._rescore}
        data-testid="cmd-pullbar-rescore"
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border text-xs font-semibold disabled:opacity-50 transition-colors"
        style={{ background: 'var(--theme-purple-dim)', borderColor: 'var(--theme-purple)', color: 'var(--theme-purple-light)' }}
      >
        {busy._rescore ? <CircleNotch size={12} className="animate-spin" /> : <Lightning size={12} weight="fill" />}
        Aria rescore leads
      </button>
    </div>
  );
};


// ── CommandCenter ───────────────────────────────────────────────────────
const CommandCenter = () => {
  const { user } = useAuth();
  const [mode, setMode] = useState('hybrid');
  const [kpi, setKpi] = useState(null);
  const [signals, setSignals] = useState({ signals: [], total_pending: 0 });
  const [pipeline, setPipeline] = useState({ leads: [] });
  const [nextScan, setNextScan] = useState(null);
  const [health, setHealth] = useState(null);
  const [today, setToday] = useState(null);
  const [pipelineSnapshot, setPipelineSnapshot] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [wt, k, s, p, ns, hl, td, ps] = await Promise.all([
        api.get('/api/aria/workspace-type').catch(() => ({ data: { workspace_type: 'hybrid' } })),
        api.get('/api/aria/command-center/kpis').catch(() => ({ data: null })),
        api.get('/api/aria/command-center/signals').catch(() => ({ data: { signals: [], total_pending: 0 } })),
        api.get('/api/aria/command-center/pipeline').catch(() => ({ data: { leads: [] } })),
        api.get('/api/aria/command-center/next-scan').catch(() => ({ data: null })),
        ptApi.get('/api/pt/setup/health').catch(() => ({ data: null })),
        api.get('/api/aria/today').catch(() => ({ data: null })),
        api.get('/api/leads/counts').catch(() => ({ data: null })),
      ]);
      setMode(wt.data?.workspace_type || 'hybrid');
      setKpi(k.data);
      setSignals(s.data);
      setPipeline(p.data);
      setNextScan(ns.data);
      setHealth(hl.data);
      setToday(td.data);
      setPipelineSnapshot(ps.data?.pipeline_snapshot || null);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);
  useEffect(() => {
    const onTenant = () => load();
    window.addEventListener('aria:tenant-changed', onTenant);
    return () => window.removeEventListener('aria:tenant-changed', onTenant);
  }, []);

  const theme = MODE_THEME[mode] || MODE_THEME.hybrid;
  const setupPct = health ? Math.round(((health.ready_count || 0) / Math.max(1, health.total || 1)) * 100) : null;
  const setupComplete = health ? !!health.live : true;
  const hasAnyLeads = (pipeline.leads || []).length > 0 || (kpi?.items?.[0]?.value || 0) > 0;

  const subtextLines = useMemo(() => {
    const lines = [];
    // Static fallback: literally nothing happening yet
    if (!hasAnyLeads && (setupComplete || setupPct === null)) {
      lines.push("Aria's ready — let's get her some leads to work.");
      return lines;
    }
    if (!hasAnyLeads && !setupComplete) {
      lines.push(`Your workspace is ${setupPct}% ready. Let's finish setup.`);
      return lines;
    }
    // Cycling lines — only when we have real signal/lead/scan data
    if (mode === 'b2b' || mode === 'hybrid') {
      if (signals?.total_pending > 0) {
        const top = signals.signals?.[0];
        if (top?.prospect_name) {
          lines.push(`${top.prospect_name}${top.prospect_company ? ' at ' + top.prospect_company : ''} just triggered a ${(top.signal_type || 'signal').replace(/_/g, ' ')} — within outreach window.`);
        }
        lines.push(`${signals.total_pending} instinct signal${signals.total_pending === 1 ? '' : 's'} pending action.`);
      }
    }
    if (mode === 'b2c' || mode === 'hybrid') {
      const activeConv = kpi?.items?.find((i) => i.key === 'active_conversations')?.value ?? kpi?.items?.[1]?.value ?? 0;
      const calls = kpi?.items?.find((i) => i.key === 'calls_booked_today')?.value ?? kpi?.items?.[2]?.value ?? 0;
      const totalLeads = kpi?.items?.find((i) => i.key === 'total_leads_plus_prospects')?.value ?? 0;
      if (activeConv > 0) {
        lines.push(`ARIA is handling ${activeConv} active conversation${activeConv === 1 ? '' : 's'}${calls > 0 ? ` — ${calls} call${calls === 1 ? '' : 's'} booked today.` : '.'}`);
      } else if (totalLeads > 0) {
        lines.push(`${totalLeads} lead${totalLeads === 1 ? '' : 's'} in pipeline. ARIA is qualifying.`);
      }
    }
    if (nextScan?.next_scan_time) {
      lines.push(`Next prospect scan: ${nextScan.next_scan_time} ${nextScan.timezone || 'IST'}.`);
    }
    // If setup isn't complete but data IS flowing, slot the nudge into the cycle
    if (!setupComplete && setupPct !== null) {
      lines.push(`Workspace ${setupPct}% configured — a few items left to unlock everything.`);
    }
    if (lines.length === 0) {
      lines.push("ARIA is running both tracks. Quiet day so far.");
    }
    return lines.slice(0, 4);
  }, [setupComplete, setupPct, hasAnyLeads, signals, kpi, mode, nextScan]);

  // iter109b — cycle through subtextLines every 6s with fade.
  const [subIdx, setSubIdx] = useState(0);
  const [subVisible, setSubVisible] = useState(true);
  useEffect(() => {
    setSubIdx(0);
    if (subtextLines.length <= 1) return;
    const id = setInterval(() => {
      setSubVisible(false);
      setTimeout(() => {
        setSubIdx((i) => (i + 1) % subtextLines.length);
        setSubVisible(true);
      }, 350);
    }, 6000);
    return () => clearInterval(id);
  }, [subtextLines]);

  return (
    <div data-testid="command-center-page" className="space-y-5" style={{ color: 'var(--theme-text)' }}>
      {/* TOP: dynamic pull bar */}
      <div className="flex items-center justify-between flex-wrap gap-3 -mt-2 -mx-2 px-2 pb-3 border-b" style={{ borderColor: 'var(--theme-border)' }}>
        <PullBar onChange={load} />
        <div className="flex items-center gap-2 ml-auto">
          <Link
            to={mode === 'b2b' ? '/app/leads?action=add' : '/app/leads?action=add'}
            data-testid="cmd-add-lead-btn"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold text-white"
            style={{ background: 'var(--theme-purple)' }}
          >
            <Plus size={12} weight="bold" /> {mode === 'b2b' ? 'Add Prospect' : 'Add Lead'}
          </Link>
        </div>
      </div>

      {/* MODE BAR */}
      <div
        className="flex items-center gap-3 px-4 py-2.5 rounded-lg border"
        style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }}
        data-testid="cmd-mode-bar"
      >
        <span className="w-2 h-2 rounded-full" style={{ background: theme.dot }} />
        <span className="text-sm font-semibold" style={{ color: theme.color }}>{theme.label}</span>
        <span className="text-xs" style={{ color: 'var(--theme-text-muted)' }}>· {theme.desc}</span>
      </div>

      {/* HERO */}
      <div
        className="relative rounded-xl overflow-hidden p-7 md:p-9 text-white"
        style={{ background: 'linear-gradient(135deg, #5b21b6 0%, #7c3aed 40%, #6d28d9 100%)' }}
        data-testid="cmd-hero"
      >
        <div className="absolute -top-12 -right-12 w-52 h-52 rounded-full" style={{ background: 'rgba(255,255,255,0.05)' }} />
        <div className="absolute -bottom-16 right-20 w-44 h-44 rounded-full" style={{ background: 'rgba(255,255,255,0.04)' }} />
        <div className="relative z-10 max-w-3xl">
          <div className="text-[10px] font-bold uppercase tracking-[0.28em] text-white/80 mb-3" style={{ fontFamily: 'Plus Jakarta Sans' }}>
            ✦ ARIA · YOUR FIRST AI SALES HIRE
          </div>
          <h1 className="text-3xl md:text-4xl font-extrabold mb-2" style={{ fontFamily: 'Space Grotesk, Inter', letterSpacing: '-0.02em' }}>
            {greeting()}, {firstNameOf(user)}..
          </h1>
          <p
            className="text-sm text-white/80 mb-6 transition-opacity duration-300 min-h-[24px]"
            style={{ fontFamily: 'Plus Jakarta Sans', opacity: subVisible ? 1 : 0 }}
            data-testid="cmd-hero-subtext"
          >
            {loading ? 'Spinning up…' : (subtextLines[subIdx] || '')}
          </p>
          <div className="flex flex-wrap gap-2.5">
            {(mode === 'b2b' || mode === 'hybrid') && (
              <Link
                to="/app/instinct"
                data-testid="cmd-hero-cta-instinct"
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md bg-white text-violet-800 text-xs font-bold hover:bg-white/95"
              >
                ◈ View Instinct Feed
              </Link>
            )}
            {(mode === 'b2c' || mode === 'hybrid') && (
              <Link
                to="/app/automation"
                data-testid="cmd-hero-cta-automation"
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md text-xs font-bold border"
                style={{ background: mode === 'b2c' ? '#fff' : 'rgba(255,255,255,0.12)', color: mode === 'b2c' ? '#5b21b6' : '#fff', borderColor: mode === 'b2c' ? 'transparent' : 'rgba(255,255,255,0.2)' }}
              >
                ◫ View Automation
              </Link>
            )}
            {mode === 'b2b' && (
              <Link to="/app/leads?action=add" data-testid="cmd-hero-cta-add-prospect" className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md text-xs font-bold border" style={{ background: 'rgba(255,255,255,0.12)', borderColor: 'rgba(255,255,255,0.2)', color: '#fff' }}>
                <Plus size={12} weight="bold" /> Add Prospect
              </Link>
            )}
            {mode === 'b2c' && (
              <Link to="/app/leads" data-testid="cmd-hero-cta-import" className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md text-xs font-bold border" style={{ background: 'rgba(255,255,255,0.12)', borderColor: 'rgba(255,255,255,0.2)', color: '#fff' }}>
                <Upload size={12} weight="bold" /> Import CSV
              </Link>
            )}
            <a
              href="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
              target="_blank" rel="noopener noreferrer"
              data-testid="cmd-hero-cta-demo"
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md text-xs font-bold border"
              style={{ background: 'rgba(255,255,255,0.12)', borderColor: 'rgba(255,255,255,0.2)', color: '#fff' }}
            >
              <PlayCircle size={12} weight="fill" /> Watch 2-min demo
            </a>
          </div>
        </div>
      </div>

      {/* DAILY ARIA BRIEF — today's headline + key totals + tomorrow's top 3 */}
      {today && <DailyBriefCard today={today} />}

      {/* KPI GRID */}
      {kpi?.items && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3" data-testid="cmd-kpi-grid">
          {kpi.items.map((it) => <KPICard key={it.key} item={it} />)}
        </div>
      )}

      {/* iter126 — Pipeline Snapshot row (live, clickable chips → /app/leads with filter) */}
      {pipelineSnapshot && <PipelineSnapshotRow snapshot={pipelineSnapshot} />}

      {/* iter143 — Lemlist Pipeline Health (Pietential workspace only) */}
      <LemlistPipelineHealthCard />

      {/* MODE-SPECIFIC LOWER CONTENT */}
      {mode === 'b2b' && (
        <B2BLowerBlock signals={signals} nextScan={nextScan} />
      )}
      {mode === 'b2c' && (
        <B2CLowerBlock leads={pipeline.leads} />
      )}
      {mode === 'hybrid' && (
        <HybridLowerBlock signals={signals} kpi={kpi} />
      )}
    </div>
  );
};


// ── PipelineSnapshotRow ─────────────────────────────────────────────────
// Live snapshot strip below the KPI grid. Each chip navigates to
// /app/leads with a pre-applied filter (encoded as ?tab= or ?status=).
const PipelineSnapshotRow = ({ snapshot }) => {
  const chips = [
    { key: 'total',             label: 'Total leads',        value: snapshot.total,             to: '/app/leads',                    accent: '#1A0A2E' },
    { key: 'qualified',         label: 'Qualified',          value: snapshot.qualified,         to: '/app/leads?tab=qualified',      accent: '#16A34A' },
    { key: 'nurturing',         label: 'Nurturing',          value: snapshot.nurturing,         to: '/app/leads?tab=contacted',      accent: '#F59E0B' },
    { key: 'needs_attention',   label: 'Needs attention',    value: snapshot.needs_attention,   to: '/app/leads?tab=high_intent',    accent: '#DC2626' },
    { key: 'calls_booked_week', label: 'Calls this week',    value: snapshot.calls_booked_week, to: '/app/calls',                    accent: '#7C35DC' },
  ];
  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-2.5" data-testid="cmd-pipeline-snapshot">
      {chips.map((c) => (
        <Link
          key={c.key}
          to={c.to}
          data-testid={`cmd-pipeline-snapshot-${c.key}`}
          className="rounded-xl border px-4 py-3 transition-all hover:-translate-y-0.5"
          style={{
            background: 'var(--theme-surface)',
            borderColor: 'var(--theme-border)',
            boxShadow: '0 1px 0 rgba(0,0,0,0.02)',
          }}
        >
          <div className="text-[10px] font-bold uppercase tracking-[0.14em]" style={{ color: 'var(--theme-text-muted)' }}>
            {c.label}
          </div>
          <div className="mt-1 text-2xl font-extrabold numeric" style={{ color: c.accent, fontFamily: 'Space Grotesk, Inter' }}>
            {(c.value ?? 0).toLocaleString()}
          </div>
        </Link>
      ))}
    </div>
  );
};


// ── DailyBriefCard ──────────────────────────────────────────────────────
// Renders /api/aria/today: momentum headline, today's totals, tomorrow's
// top 3 prospects. Surfaces the existing EOD wrap data on the dashboard
// itself so the founder doesn't have to wait for the 8 PM email.
const DailyBriefCard = ({ today }) => {
  const t = today.totals || {};
  const momentum = today.momentum || 'quiet'; // 'wins' | 'busy' | 'quiet'
  const momentumStyle = {
    wins:  { color: '#16a34a', dim: 'rgba(22,163,74,0.10)',  Icon: Trophy,    label: 'Wins logged' },
    busy:  { color: '#7C35DC', dim: 'rgba(124,53,220,0.10)', Icon: Fire,      label: 'Busy day'    },
    quiet: { color: '#94a3b8', dim: 'rgba(148,163,184,0.10)', Icon: Sun,       label: 'Quiet day'   },
  }[momentum] || { color: '#94a3b8', dim: 'rgba(148,163,184,0.10)', Icon: Sun, label: '' };
  const MIcon = momentumStyle.Icon;

  const tomorrow = (today.tomorrow_top_3 || []).slice(0, 3);

  return (
    <div
      className="rounded-xl border p-5 md:p-6"
      style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }}
      data-testid="cmd-daily-brief"
    >
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div className="flex items-center gap-2.5">
          <div
            className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
            style={{ background: momentumStyle.dim, color: momentumStyle.color }}
          >
            <MIcon size={16} weight="duotone" />
          </div>
          <div>
            <div className="text-[10px] font-bold uppercase tracking-[0.22em]" style={{ color: 'var(--theme-text-muted)', fontFamily: 'Plus Jakarta Sans' }}>
              Daily Aria Brief · {today.date_label}
            </div>
            <div className="text-base font-bold mt-0.5" style={{ color: 'var(--theme-text)', fontFamily: 'Space Grotesk, Inter' }} data-testid="cmd-brief-headline">
              {today.headline}
            </div>
          </div>
        </div>
        <span
          className="text-[10px] font-bold uppercase tracking-[0.16em] px-2 py-1 rounded-full"
          style={{ background: momentumStyle.dim, color: momentumStyle.color, fontFamily: 'Plus Jakarta Sans' }}
        >
          {momentumStyle.label}
        </span>
      </div>

      {/* Totals strip */}
      <div className="grid grid-cols-3 md:grid-cols-6 gap-3 mb-4" data-testid="cmd-brief-totals">
        <BriefStat label="Touches"  value={t.total_touches ?? 0} testid="brief-stat-touches" />
        <BriefStat label="New leads" value={t.new_leads ?? 0}    testid="brief-stat-new-leads" />
        <BriefStat label="Booked"   value={t.meetings_booked ?? 0} testid="brief-stat-booked" />
        <BriefStat label="Wins"     value={t.wins ?? 0}          accent="#16a34a" testid="brief-stat-wins" />
        <BriefStat label="Overdue"  value={t.overdue_pending ?? 0} accent={(t.overdue_pending ?? 0) > 0 ? '#dc2626' : undefined} testid="brief-stat-overdue" />
        <BriefStat label="Hot untouched" value={today.hot_untouched_count ?? 0} accent="#7C35DC" testid="brief-stat-hot-untouched" />
      </div>

      {/* Tomorrow's top 3 */}
      {tomorrow.length > 0 && (
        <div className="pt-3 border-t" style={{ borderColor: 'var(--theme-border)' }} data-testid="cmd-brief-tomorrow">
          <div className="text-[10px] font-bold uppercase tracking-[0.18em] mb-2" style={{ color: 'var(--theme-text-muted)', fontFamily: 'Plus Jakarta Sans' }}>
            Tomorrow · top 3
          </div>
          <div className="flex flex-wrap gap-2">
            {tomorrow.map((row, i) => (
              <Link
                key={i}
                to="/app/leads"
                data-testid={`cmd-brief-tomorrow-${i}`}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs border transition-colors hover:bg-[var(--theme-surface2)]"
                style={{ borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text)', fontFamily: 'Plus Jakarta Sans' }}
                title={row.phone || ''}
              >
                <span className="font-semibold">{row.name}</span>
                {row.company && <span style={{ color: 'var(--theme-text-muted)' }}>· {row.company}</span>}
                <span
                  className="text-[10px] font-bold px-1.5 py-0.5 rounded ml-1"
                  style={{ background: 'rgba(124,53,220,0.12)', color: 'var(--theme-purple-light, #7C35DC)' }}
                >
                  {row.icp_score}
                </span>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

const BriefStat = ({ label, value, accent, testid }) => (
  <div data-testid={testid}>
    <div className="text-[10px] font-bold uppercase tracking-[0.14em]" style={{ color: 'var(--theme-text-muted)', fontFamily: 'Plus Jakarta Sans' }}>{label}</div>
    <div className="text-xl font-extrabold mt-0.5" style={{ color: accent || 'var(--theme-text)', fontFamily: 'Space Grotesk, Inter' }}>{value}</div>
  </div>
);


// ── KPI Card ────────────────────────────────────────────────────────────
const KPICard = ({ item }) => {
  const accent = {
    purple: 'var(--theme-purple-light)',
    amber:  'var(--theme-amber)',
    green:  'var(--theme-green)',
    red:    'var(--theme-red)',
  }[item.accent] || 'var(--theme-text)';
  const delta = item.delta_label || '';
  const isUp = (item.delta ?? 0) > 0;
  return (
    <div
      className="rounded-lg p-4 border"
      style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }}
      data-testid={`cmd-kpi-${item.key}`}
    >
      <div className="text-[11px] font-medium mb-1.5" style={{ color: 'var(--theme-text-muted)' }}>{item.label}</div>
      <div className="text-3xl font-extrabold mb-1" style={{ color: accent, fontFamily: 'Space Grotesk, Inter', letterSpacing: '-0.03em' }} data-testid={`cmd-kpi-${item.key}-value`}>
        {item.value}
      </div>
      {delta && (
        <div className="text-[11px]" style={{ color: isUp ? 'var(--theme-green)' : 'var(--theme-text-muted)' }}>{delta}</div>
      )}
    </div>
  );
};


// ── B2B lower block ─────────────────────────────────────────────────────
const B2BLowerBlock = ({ signals, nextScan }) => (
  <>
    <SectionLabel icon="⚡" label="Today's Instinct Signals" />
    {(signals.signals || []).length === 0 ? (
      <EmptySignals />
    ) : (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3" data-testid="cmd-instinct-cards">
        {signals.signals.slice(0, 2).map((s, i) => <InsightCard key={s.id || i} signal={s} />)}
      </div>
    )}

    <SectionLabel icon="⚡" label="Top Prospect to Engage Today" />
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3" data-testid="cmd-top-prospect-grid">
      <div className="rounded-lg p-4 border" style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-purple)' }}>
        <div className="text-[11px] font-medium mb-1.5" style={{ color: 'var(--theme-text-muted)' }}>Recommended First</div>
        <div className="text-sm font-bold" style={{ color: 'var(--theme-text)' }}>
          {signals.signals?.[0]?.prospect_name || 'No prospect yet'}
        </div>
        <div className="text-xs mt-1" style={{ color: 'var(--theme-text-muted)' }}>
          {signals.signals?.[0] ? `${signals.signals[0].signal_type || 'signal'} · ICP match` : 'Waiting for first scan'}
        </div>
      </div>
      <div className="rounded-lg p-4 border" style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }}>
        <div className="text-[11px] font-medium mb-1.5" style={{ color: 'var(--theme-text-muted)' }}>Prospects Pending Action</div>
        <div className="text-3xl font-extrabold" style={{ color: 'var(--theme-amber)', fontFamily: 'Space Grotesk, Inter' }}>
          {signals.total_pending || 0}
        </div>
        <div className="text-xs mt-1" style={{ color: 'var(--theme-text-muted)' }}>cards waiting in Instinct Feed</div>
      </div>
      <div className="rounded-lg p-4 border" style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }}>
        <div className="text-[11px] font-medium mb-1.5" style={{ color: 'var(--theme-text-muted)' }}>Next Scan</div>
        <div className="text-xl font-extrabold" style={{ color: 'var(--theme-text)', fontFamily: 'Space Grotesk, Inter' }}>
          {nextScan?.next_scan_time || '07:00'}
        </div>
        <div className="text-xs mt-1" style={{ color: 'var(--theme-text-muted)' }}>daily scan · {nextScan?.timezone || 'IST'}</div>
      </div>
    </div>
  </>
);


// ── B2C lower block ─────────────────────────────────────────────────────
const STATUS_TAG = {
  qualified: { bg: 'rgba(34,197,94,0.13)', color: '#22c55e' },
  nurturing: { bg: 'rgba(245,158,11,0.13)', color: '#f59e0b' },
  new:       { bg: 'rgba(96,165,250,0.13)', color: '#60a5fa' },
  cold:      { bg: 'rgba(255,255,255,0.07)', color: 'var(--theme-text-dim)' },
  stalled:   { bg: 'rgba(245,158,11,0.13)', color: '#f59e0b' },
};

const CHANNEL_ICON = {
  whatsapp: '💬', email: '📧', linkedin: '💼', webform: '🌐',
};

const B2CLowerBlock = ({ leads }) => (
  <>
    <SectionLabel icon="⚡" label="Lead Pipeline" />
    {(leads || []).length === 0 ? (
      <ChipsEmptyState />
    ) : (
      <div className="rounded-lg overflow-hidden border" style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }} data-testid="cmd-lead-pipeline">
        <div className="grid grid-cols-5 gap-3 px-4 py-2.5 text-[10px] font-bold uppercase tracking-wider"
             style={{ background: 'var(--theme-surface2)', color: 'var(--theme-text-dim)', borderBottom: '1px solid var(--theme-border)' }}>
          <div>Lead</div><div>Source</div><div>ICP Match</div><div>Status</div><div>Channel</div>
        </div>
        {leads.slice(0, 6).map((l) => {
          const tag = STATUS_TAG[(l.status || 'new').toLowerCase()] || STATUS_TAG.new;
          const score = l.icp_score ?? l.icp_fit_score ?? 0;
          return (
            <div
              key={l.id}
              className="grid grid-cols-5 gap-3 px-4 py-2.5 items-center text-xs border-b last:border-b-0"
              style={{ borderColor: 'var(--theme-border)' }}
              data-testid={`cmd-pipeline-row-${l.id}`}
            >
              <div>
                <div className="font-semibold" style={{ color: 'var(--theme-text)' }}>{l.name || 'Unnamed Lead'}</div>
                <div className="text-[11px]" style={{ color: 'var(--theme-text-muted)' }}>{l.company || ''}</div>
              </div>
              <div style={{ color: 'var(--theme-text-muted)' }}>{l.source || '—'}</div>
              <div className="flex items-center gap-2">
                <div className="flex-1 h-1 rounded-full" style={{ background: 'var(--theme-surface2)' }}>
                  <div className="h-full rounded-full" style={{ width: `${Math.min(100, score)}%`, background: 'var(--theme-purple)' }} />
                </div>
                <span className="text-[11px] font-semibold w-9 text-right" style={{ color: 'var(--theme-text-muted)' }}>{Math.round(score)}%</span>
              </div>
              <div>
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider" style={{ background: tag.bg, color: tag.color }}>
                  {(l.status || 'new').replace(/_/g, ' ')}
                </span>
              </div>
              <div className="text-xs" style={{ color: 'var(--theme-text-muted)' }}>
                <span className="mr-1">{CHANNEL_ICON[(l.channel || '').toLowerCase()] || '·'}</span>
                {l.channel || 'Inbound'}
              </div>
            </div>
          );
        })}
      </div>
    )}
  </>
);


// ── Hybrid lower block ──────────────────────────────────────────────────
const HybridLowerBlock = ({ signals, kpi }) => {
  const b2cLeads = kpi?.items?.[0]?.value || 0;
  const calls = kpi?.items?.[2]?.value || 0;
  return (
    <>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3" data-testid="cmd-hybrid-split">
        <div className="rounded-lg p-4 border" style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-purple)' }}>
          <div className="flex items-center justify-between mb-3 pb-3 border-b" style={{ borderColor: 'var(--theme-border)' }}>
            <div className="text-xs font-bold uppercase tracking-wider" style={{ color: 'var(--theme-purple-light)' }}>◈ Instinct — B2B Track</div>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold" style={{ background: 'var(--theme-purple-dim)', color: 'var(--theme-purple-light)' }}>
              {signals.total_pending || 0} signals
            </span>
          </div>
          {(signals.signals || []).slice(0, 2).map((s, i) => <HybridMiniCard key={s.id || i} signal={s} />)}
          {(signals.signals || []).length === 0 && (
            <div className="text-xs" style={{ color: 'var(--theme-text-muted)' }}>No instinct signals yet. Connect your B2B sources.</div>
          )}
        </div>
        <div className="rounded-lg p-4 border" style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-amber)' }}>
          <div className="flex items-center justify-between mb-3 pb-3 border-b" style={{ borderColor: 'var(--theme-border)' }}>
            <div className="text-xs font-bold uppercase tracking-wider" style={{ color: 'var(--theme-amber)' }}>◫ Automation — B2C Track</div>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold" style={{ background: 'var(--theme-amber-dim)', color: 'var(--theme-amber)' }}>
              {b2cLeads} active
            </span>
          </div>
          <div className="grid grid-cols-3 gap-2 mb-3">
            <MiniStat value={b2cLeads} label="Leads" color="var(--theme-amber)" />
            <MiniStat value={calls} label="Calls Booked" color="var(--theme-green)" />
            <MiniStat value={kpi?.items?.[3]?.value || 0} label="ARIA Actions" color="var(--theme-text)" />
          </div>
        </div>
      </div>

      {/* Combined pipeline row (already covered by KPI grid above) */}
      <SectionLabel icon="⚡" label="Combined Pipeline" />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm" style={{ color: 'var(--theme-text-muted)' }}>
        Aria is running both tracks in parallel — see Instinct Feed for B2B signals and Automation for the B2C lead inbox.
      </div>
    </>
  );
};


// ── Helpers ─────────────────────────────────────────────────────────────
const SectionLabel = ({ icon, label }) => (
  <div className="text-[10px] font-bold uppercase tracking-[0.16em] flex items-center gap-2" style={{ color: 'var(--theme-text-dim)' }}>
    <span>{icon}</span> {label}
  </div>
);

const EmptySignals = () => (
  <div className="rounded-lg p-6 text-center text-sm border border-dashed"
       style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)', color: 'var(--theme-text-muted)' }}
       data-testid="cmd-signals-empty">
    No signals yet — prospects are being scanned daily at the configured time.
  </div>
);

const ChipsEmptyState = () => (
  <div className="rounded-lg p-5 border" style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }} data-testid="cmd-chips-empty">
    <div className="text-[10px] font-bold uppercase tracking-[0.16em] mb-3" style={{ color: 'var(--theme-purple-light)' }}>
      What lights up here once leads flow
    </div>
    <div className="flex flex-wrap gap-2">
      {[
        { icon: '📊', label: 'Live KPI cards' },
        { icon: '✦',  label: 'Daily Aria brief' },
        { icon: '◎',  label: 'Conversation feed' },
        { icon: '⚡', label: 'Pipeline mood' },
        { icon: '📅', label: 'Calls today' },
      ].map((c) => (
        <span key={c.label} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs border"
              style={{ background: 'var(--theme-surface2)', borderColor: 'var(--theme-border)', color: 'var(--theme-text-muted)' }}
              data-testid={`cmd-chip-${c.label.toLowerCase().replace(/\s+/g, '-')}`}>
          <span>{c.icon}</span> {c.label}
        </span>
      ))}
    </div>
  </div>
);

const SIGNAL_BADGE = {
  funding_round:     { label: 'Funding Round', bg: 'rgba(245,158,11,0.13)', color: '#f59e0b' },
  event_attending:   { label: 'Event Attending', bg: 'rgba(96,165,250,0.13)', color: '#60a5fa' },
  deal_closed:       { label: 'Deal Closed',    bg: 'rgba(34,197,94,0.13)',  color: '#22c55e' },
  job_change:        { label: 'Job Change',     bg: 'rgba(167,139,250,0.13)', color: 'var(--theme-purple-light)' },
  hiring_signal:     { label: 'Hiring',         bg: 'rgba(99,102,241,0.13)',  color: '#a5b4fc' },
  content_published: { label: 'Content',        bg: 'rgba(244,114,182,0.13)', color: '#f472b6' },
  social_activity:   { label: 'Social',         bg: 'rgba(20,184,166,0.13)',  color: '#2dd4bf' },
};

const InsightCard = ({ signal }) => {
  const b = SIGNAL_BADGE[signal.signal_type] || { label: signal.signal_type || 'Signal', bg: 'var(--theme-purple-dim)', color: 'var(--theme-purple-light)' };
  const score = signal.icp_match_score || signal.icp_score || signal.confidence || 0;
  const scorePct = score > 1 ? score : Math.round(score * 100);
  return (
    <div className="rounded-lg p-4 border" style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }} data-testid={`cmd-insight-card-${signal.id || signal.prospect_name || ''}`}>
      <div className="flex items-start justify-between mb-2.5">
        <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider"
              style={{ background: b.bg, color: b.color }}>{b.label}</span>
        <span className="px-2 py-0.5 rounded text-[10px] font-semibold"
              style={{ background: 'var(--theme-purple-dim)', color: 'var(--theme-purple-light)' }}>
          {signal.icp_name ? `${signal.icp_name} · ` : ''}{scorePct}%
        </span>
      </div>
      <div className="text-sm font-semibold mb-0.5" style={{ color: 'var(--theme-text)' }}>{signal.prospect_name || 'Prospect'}</div>
      <div className="text-[11px] mb-2" style={{ color: 'var(--theme-text-muted)' }}>
        {signal.prospect_title || ''}{signal.prospect_company ? ` · ${signal.prospect_company}` : ''}
      </div>
      <p className="text-xs leading-relaxed mb-2.5" style={{ color: 'var(--theme-text-muted)' }}>
        {signal.summary || signal.message_preview || ''}
      </p>
      {signal.timing_note && (
        <div className="text-[10.5px] flex items-center gap-1.5" style={{ color: 'var(--theme-amber)' }}>
          <Clock size={11} weight="duotone" /> {signal.timing_note}
        </div>
      )}
      <div className="flex gap-1.5 mt-3">
        <Link to="/app/instinct" data-testid="cmd-insight-card-cta"
              className="px-2.5 py-1 rounded text-[11px] font-semibold border"
              style={{ background: 'var(--theme-purple-dim)', borderColor: 'var(--theme-purple)', color: 'var(--theme-purple-light)' }}>
          Send via ARIA
        </Link>
        <Link to="/app/instinct" className="px-2.5 py-1 rounded text-[11px] font-semibold border"
              style={{ borderColor: 'var(--theme-border)', color: 'var(--theme-text-muted)' }}>
          Edit + Send
        </Link>
      </div>
    </div>
  );
};

const HybridMiniCard = ({ signal }) => (
  <div className="border rounded-md p-2.5 mb-2" style={{ borderColor: 'var(--theme-border)' }} data-testid={`cmd-hybrid-mini-${signal.id || signal.prospect_name || ''}`}>
    <div className="flex justify-between items-start mb-1.5">
      <div>
        <div className="text-xs font-semibold" style={{ color: 'var(--theme-text)' }}>{signal.prospect_name || 'Prospect'} · {signal.prospect_title || ''}</div>
        <div className="text-[10.5px]" style={{ color: 'var(--theme-text-muted)' }}>{signal.signal_type || 'signal'}</div>
      </div>
      <Link to="/app/instinct" className="text-[10px] font-semibold" style={{ color: 'var(--theme-purple-light)' }}>View →</Link>
    </div>
    <div className="text-[10.5px]" style={{ color: 'var(--theme-text-dim)' }}>{signal.summary || ''}</div>
  </div>
);

const MiniStat = ({ value, label, color }) => (
  <div className="text-center p-2.5 rounded-md" style={{ background: 'var(--theme-surface2)' }}>
    <div className="text-lg font-extrabold" style={{ color }}>{value}</div>
    <div className="text-[10px]" style={{ color: 'var(--theme-text-muted)' }}>{label}</div>
  </div>
);

export default CommandCenter;
