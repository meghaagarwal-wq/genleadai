/**
 * ARIA Universal Demo Dashboard — iter173 (dark/violet)
 *
 * Public sales demo. Zero backend calls except optional /api/enrich.
 *
 * Iter173 upgrades:
 *   - Theme migrated to dark/violet to match marketing + real product.
 *   - Personalisation overlay: prospect pastes their domain → theatrical
 *     scan → dashboard rebuilds around their company.
 *   - Deep-link support: ?company=<domain>&mode=<b2c|b2b|hybrid>&scenario=
 *   - Command Center tab: hero saved-counter + Approvals queue.
 *   - Instinct Feed tab: live-streaming signal cards (every 15–25 s).
 *   - Approvals + streaming feed increment a live "ARIA saved you" tile.
 */
import React, { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ResponsiveSankey } from '@nivo/sankey';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
  LineChart, Line, Area, AreaChart, Legend,
} from 'recharts';
import {
  ArrowRight, TrendingUp, TrendingDown, CircleDot, Sparkles, Zap, Calendar,
  Database, Activity, Users, DollarSign, ChevronRight, Play, Pause,
  CheckCircle2, AlertTriangle, Clock, GitBranch, ArrowUpRight, Download,
  ChevronDown, Home, Radar, Edit2, Link2, CalendarClock,
} from 'lucide-react';
import html2canvas from 'html2canvas';
import jsPDF from 'jspdf';
import { PERSONAS, PERSONA_ORDER, AUTOMATION_FLOWS } from '../demoData/mockPersonas';
import {
  APPROVALS, INSTINCT_TEMPLATES, inferModeFromKeywords, inferICPFromKeywords,
} from '../demoData/liveContent';
import PersonalizationOverlay from './demo/PersonalizationOverlay';
import CommandCenterScreen  from './demo/CommandCenterScreen';
import InstinctFeedScreen   from './demo/InstinctFeedScreen';
import AskAriaBar           from './demo/AskAriaBar';
import RecordDemoButton     from './demo/RecordDemoButton';
import { openCalendlyPopup } from '../../lib/calendlyPopup';

// ───── dark/violet design tokens ─────
const T = {
  canvas:     '#0B0A14',
  card:       '#16151F',
  cardElev:   '#1F1D2E',
  accent:     '#A46FE8',
  accentDeep: '#7C35DC',
  accentSoft: 'rgba(124,53,220,0.15)',
  ink:        '#EAE7F5',
  muted:      '#8B849E',
  line:       '#28243A',
  success:    '#4ADE80',
  warn:       '#FBBF24',
  danger:     '#F87171',
  chartPalette: ['#A46FE8', '#7BC58F', '#F2B84B', '#F87171', '#5FB1B8', '#E38FB0', '#EA9A54'],
  fontDisplay: '"Fraunces", "Plus Jakarta Sans", ui-serif, serif',
  fontUi:      '"Plus Jakarta Sans", "Inter", system-ui, sans-serif',
};

const TABS = [
  { key: 'command',    label: 'Command Center', icon: Home },
  { key: 'instinct',   label: 'Instinct Feed',  icon: Radar },
  { key: 'overview',   label: 'Overview',       icon: Sparkles },
  { key: 'channels',   label: 'Channels',       icon: Activity },
  { key: 'journey',    label: 'Journey',        icon: GitBranch },
  { key: 'automation', label: 'Automation',     icon: Zap },
  { key: 'revenue',    label: 'Revenue',        icon: DollarSign },
  { key: 'health',     label: 'Data Health',    icon: Database },
];

// ─── Scenario presets (revenue/orders multipliers per persona) ─────────
const SCENARIOS = {
  default:        { key: 'default',        label: 'Default',        blurb: 'Baseline numbers'         },
  'just-launched': { key: 'just-launched', label: 'Just launched',  blurb: 'Small volume · high delta' },
  scaling:        { key: 'scaling',        label: 'Scaling',        blurb: 'Growing · strong ROAS'     },
  plateaued:      { key: 'plateaued',      label: 'Plateaued',      blurb: 'Flat · needs unlock'       },
};

// Multipliers applied to numeric-looking KPI values by matching the leading
// unit ($, k, M, x, %, digits) and rescaling. Non-numeric strings pass through.
const SCENARIO_TRANSFORMS = {
  default:        { mul: 1.00, deltaMul: 1.00, tone: null },
  'just-launched': { mul: 0.18, deltaMul: 1.8, tone: 'up' },
  scaling:        { mul: 1.35, deltaMul: 1.4, tone: 'up' },
  plateaued:      { mul: 0.92, deltaMul: 0.2, tone: 'down' },
};

function rescaleNumericString(s, mul) {
  if (typeof s !== 'string') return s;
  const m = s.match(/^(-?)(\$)?([\d,.]+)\s*(K|M|k|m|x|%|pt)?(.*)$/);
  if (!m) return s;
  const [, sign, dollar, num, unit, rest] = m;
  const n = parseFloat(num.replace(/,/g, ''));
  if (!isFinite(n)) return s;
  const scaled = n * mul;
  const formatted = scaled >= 1000
    ? scaled.toLocaleString(undefined, { maximumFractionDigits: 0 })
    : scaled.toLocaleString(undefined, { maximumFractionDigits: scaled < 10 ? 1 : 0 });
  return `${sign || ''}${dollar || ''}${formatted}${unit || ''}${rest || ''}`;
}

function applyScenario(persona, scenarioKey) {
  const t = SCENARIO_TRANSFORMS[scenarioKey] || SCENARIO_TRANSFORMS.default;
  if (scenarioKey === 'default') return persona;
  return {
    ...persona,
    header: {
      ...persona.header,
      kpis: persona.header.kpis.map((k) => ({
        ...k,
        value: rescaleNumericString(k.value, t.mul),
        delta: t.tone === 'down' ? '−2%' : rescaleNumericString(k.delta, t.deltaMul),
        tone: t.tone || k.tone,
      })),
      revenueSpark: persona.header.revenueSpark.map((p) => ({
        ...p,
        value: Math.round(p.value * t.mul),
      })),
    },
  };
}

// Random within a range — used for initial saved-counter seed
function randomBase(min, max) {
  return min + Math.random() * (max - min);
}

// ─────────────────────────────────────────────────────────────────
// Root
// ─────────────────────────────────────────────────────────────────
export default function UniversalDemoDashboard() {
  const [params, setParams] = useSearchParams();
  // ── URL params: ?company=<domain>&brand=&tagline=&mode=&scenario= ──
  const companyParam    = params.get('company') || null;
  const brandOverride   = params.get('brand')   || null;
  const taglineOverride = params.get('tagline') || null;
  const initialMode     = ['b2c', 'b2b', 'hybrid'].includes(params.get('mode')) ? params.get('mode') : 'b2c';
  const initialScenario = Object.keys(SCENARIOS).includes(params.get('scenario')) ? params.get('scenario') : 'default';

  const [mode, setMode]         = useState(initialMode);
  const [scenario, setScenario] = useState(initialScenario);
  const [tab, setTab]           = useState('command');
  const [exporting, setExporting] = useState(false);
  const [showOverlay, setShowOverlay] = useState(!companyParam && !brandOverride);
  // enrichment holds the prospect's { companyName, tagline, logoUrl, keywords }.
  const [enrichment, setEnrichment] = useState(null);
  const captureRef = useRef(null);
  const apiUrl = process.env.REACT_APP_BACKEND_URL || '';

  // Deep-link: if ?company=<domain> is present, hit /api/enrich silently.
  // Skip if enrichment already came from a sample click (source==='sample'),
  // so we don't clobber preset data with lower-quality scraped data.
  useEffect(() => {
    if (!companyParam) return;
    if (enrichment?.source === 'sample' && enrichment?.domain === companyParam) return;
    let cancelled = false;
    const ctrl = new AbortController();
    const timeout = setTimeout(() => ctrl.abort(), 4000);
    fetch(`${apiUrl}/api/enrich?domain=${encodeURIComponent(companyParam)}`, { signal: ctrl.signal })
      .then((r) => r.json())
      .then((data) => { if (!cancelled) setEnrichment(data); })
      .catch(() => {
        if (cancelled) return;
        const clean = companyParam.replace(/^https?:\/\//, '').replace(/^www\./, '').split('/')[0].toLowerCase();
        const root = clean.split('.')[0].replace(/-/g, ' ');
        setEnrichment({
          domain: clean,
          companyName: root.replace(/\b\w/g, (c) => c.toUpperCase()) || 'Your Company',
          tagline: null,
          logoUrl: `https://www.google.com/s2/favicons?domain=${clean}&sz=128`,
          keywords: [],
          source: 'fallback',
        });
      })
      .finally(() => clearTimeout(timeout));
    return () => { cancelled = true; ctrl.abort(); clearTimeout(timeout); };
  }, [companyParam, apiUrl]);

  // On enrichment, auto-infer mode from keywords if user hasn't set one via URL.
  useEffect(() => {
    if (!enrichment || params.get('mode')) return;
    const inferred = inferModeFromKeywords(enrichment.keywords);
    if (inferred && inferred !== mode) setMode(inferred);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enrichment]);

  // Compose brand: enrichment → URL overrides → persona defaults
  const brand = useMemo(() => {
    const p = PERSONAS[mode].brand;
    return {
      companyName: enrichment?.companyName || brandOverride   || p.name,
      tagline:     enrichment?.tagline     || taglineOverride || p.tagline,
      logoUrl:     enrichment?.logoUrl     || null,
      inferredICP: enrichment ? inferICPFromKeywords(enrichment.keywords, mode) : null,
    };
  }, [enrichment, brandOverride, taglineOverride, mode]);

  // Compose persona: base → scenario → brand overlay
  const persona = useMemo(() => {
    const base = PERSONAS[mode];
    const scen = applyScenario(base, scenario);
    return {
      ...scen,
      brand: { ...scen.brand, name: brand.companyName, tagline: brand.tagline },
    };
  }, [mode, scenario, brand]);

  // ── Approvals state + live saved counter ──────────────────────────
  const [approvals, setApprovals] = useState(() => APPROVALS[initialMode] || []);
  useEffect(() => { setApprovals(APPROVALS[mode] || []); }, [mode]);
  const [savedMoney, setSavedMoney] = useState(() => randomBase(2400, 8200));
  const [savedHours, setSavedHours] = useState(() => randomBase(6.4, 18.2));
  // Slow ambient increment so the tile feels alive
  useEffect(() => {
    const t = setInterval(() => {
      setSavedMoney((v) => v + Math.round(3 + Math.random() * 12));
      setSavedHours((v) => v + 0.02);
    }, 3200);
    return () => clearInterval(t);
  }, []);

  const handleApprove = useCallback((id) => {
    setApprovals((prev) => prev.filter((a) => a.id !== id));
    setSavedMoney((v) => v + Math.round(180 + Math.random() * 320));
    setSavedHours((v) => v + 0.4 + Math.random() * 0.6);
  }, []);

  // iter174 — Ask ARIA injects a drafted-action card at the top of Approvals.
  const handleAddAction = useCallback((card) => {
    setApprovals((prev) => [{ ...card, _new: true }, ...prev]);
    setTab('command');
    setSavedMoney((v) => v + Math.round(40 + Math.random() * 80));
    setSavedHours((v) => v + 0.1);
  }, []);

  // iter174 — Copy shareable demo link with current mode/scenario/company.
  const [linkCopied, setLinkCopied] = useState(false);
  const handleCopyLink = useCallback(() => {
    const u = new URL(window.location.href);
    // Ensure current state is captured even if the URL is stale
    u.searchParams.set('mode', mode);
    if (scenario && scenario !== 'default') u.searchParams.set('scenario', scenario);
    else u.searchParams.delete('scenario');
    if (enrichment?.domain) u.searchParams.set('company', enrichment.domain);
    else if (companyParam) u.searchParams.set('company', companyParam);
    navigator.clipboard.writeText(u.toString());
    setLinkCopied(true);
    setTimeout(() => setLinkCopied(false), 1600);
  }, [mode, scenario, enrichment, companyParam]);

  // iter176 — Book a walkthrough, passing the current demo URL to Calendly
  // as UTM params so the founder sees the personalized dashboard on the
  // Calendly booking notification.
  const calendlyBase = process.env.REACT_APP_CALENDLY_URL;
  const handleBookWalkthrough = useCallback(() => {
    if (!calendlyBase) return;
    const u = new URL(window.location.href);
    u.searchParams.set('mode', mode);
    if (scenario && scenario !== 'default') u.searchParams.set('scenario', scenario);
    if (enrichment?.domain) u.searchParams.set('company', enrichment.domain);
    openCalendlyPopup(calendlyBase, {
      source:   'aria-demo',
      demoUrl:  u.toString(),
      company:  enrichment?.domain || brand?.companyName,
      mode,
      scenario,
    });
  }, [calendlyBase, mode, scenario, enrichment, brand]);

  // iter176 — Log a demo view on mount + whenever mode/scenario/company changes.
  // Deliberately fire-and-forget; never block the UI on this.
  const lastLoggedRef = useRef('');
  useEffect(() => {
    const source = params.get('source') || 'direct';
    const sig = `${enrichment?.domain || companyParam || ''}|${mode}|${scenario}|${source}`;
    if (sig === lastLoggedRef.current) return;
    lastLoggedRef.current = sig;
    try {
      fetch(`${apiUrl}/api/demo-analytics/view`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company:  enrichment?.domain || companyParam || null,
          mode, scenario,
          source,
          path:     '/aria-demo',
          referrer: (typeof document !== 'undefined' ? document.referrer : '') || null,
        }),
        keepalive: true,
      }).catch(() => {});
    } catch (_) { /* noop */ }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, scenario, enrichment, companyParam]);

  const handleNewSignal = useCallback(() => {
    // A streamed signal is small credit — reads as "ARIA caught this for you"
    setSavedMoney((v) => v + Math.round(24 + Math.random() * 60));
    setSavedHours((v) => v + 0.05 + Math.random() * 0.1);
  }, []);

  const handleExportPDF = async () => {
    if (!captureRef.current || exporting) return;
    setExporting(true);
    try {
      const node = captureRef.current;
      const canvas = await html2canvas(node, {
        backgroundColor: T.canvas,
        scale: 2,
        useCORS: true,
        logging: false,
        windowWidth: node.scrollWidth,
        windowHeight: node.scrollHeight,
      });
      const imgData = canvas.toDataURL('image/jpeg', 0.92);
      const pdf = new jsPDF({ orientation: 'landscape', unit: 'pt', format: 'a4' });
      const pageW = pdf.internal.pageSize.getWidth();
      const pageH = pdf.internal.pageSize.getHeight();
      const imgW = pageW - 40;
      const imgH = (canvas.height * imgW) / canvas.width;
      if (imgH <= pageH - 40) {
        pdf.addImage(imgData, 'JPEG', 20, 20, imgW, imgH);
      } else {
        let sy = 0;
        const pxPerPage = ((pageH - 40) * canvas.width) / imgW;
        while (sy < canvas.height) {
          const sliceH = Math.min(pxPerPage, canvas.height - sy);
          const slice = document.createElement('canvas');
          slice.width = canvas.width;
          slice.height = sliceH;
          slice.getContext('2d').drawImage(canvas, 0, sy, canvas.width, sliceH, 0, 0, canvas.width, sliceH);
          pdf.addImage(slice.toDataURL('image/jpeg', 0.92), 'JPEG', 20, 20, imgW, (sliceH * imgW) / canvas.width);
          sy += sliceH;
          if (sy < canvas.height) pdf.addPage();
        }
      }
      const safe = (persona.brand.name || 'aria-demo').replace(/[^a-z0-9]+/gi, '-').toLowerCase();
      pdf.save(`${safe}-demo-${new Date().toISOString().slice(0, 10)}.pdf`);
    } finally {
      setExporting(false);
    }
  };

  const handleOverlayComplete = (payload) => {
    setEnrichment(payload);
    // If overlay ships a mode (e.g. from a sample click), honour it.
    if (payload?.mode && ['b2c', 'b2b', 'hybrid'].includes(payload.mode)) {
      setMode(payload.mode);
    }
    setShowOverlay(false);
    // Reflect the choice in the URL so the demo is now a shareable deep-link.
    if (payload?.domain) {
      const next = new URLSearchParams(params);
      next.set('company', payload.domain);
      if (payload.mode) next.set('mode', payload.mode);
      setParams(next, { replace: true });
    }
  };

  return (
    <div
      className="min-h-screen"
      style={{ background: T.canvas, color: T.ink, fontFamily: T.fontUi }}
      data-testid="universal-demo-dashboard"
    >
      <PersonalizationOverlay
        open={showOverlay}
        onCancel={() => setShowOverlay(false)}
        onComplete={handleOverlayComplete}
        apiUrl={apiUrl}
        T={T}
      />

      <TopBar
        mode={mode} setMode={setMode}
        scenario={scenario} setScenario={setScenario}
        brand={brand}
        onExport={handleExportPDF}
        exporting={exporting}
        onPersonalise={() => setShowOverlay(true)}
        onCopyLink={handleCopyLink}
        linkCopied={linkCopied}
        onBook={calendlyBase ? handleBookWalkthrough : null}
        apiUrl={apiUrl}
      />
      <TabBar tab={tab} setTab={setTab} />
      <main ref={captureRef} className="max-w-[1400px] mx-auto px-6 pb-16">
        {tab === 'command'    && (
          <>
            <div className="pt-6"><AskAriaBar mode={mode} onAddAction={handleAddAction} T={T} /></div>
            <CommandCenterScreen
              persona={persona}
              approvals={approvals}
              brand={brand}
              savedMoney={savedMoney}
              savedHours={savedHours}
              onApprove={handleApprove}
              T={T}
            />
          </>
        )}
        {tab === 'instinct'   && (
          <InstinctFeedScreen
            templates={INSTINCT_TEMPLATES[mode] || INSTINCT_TEMPLATES.b2c}
            brand={brand}
            mode={mode}
            onNewCard={handleNewSignal}
            T={T}
          />
        )}
        {tab === 'overview'   && <OverviewScreen persona={persona} />}
        {tab === 'channels'   && <ChannelsScreen persona={persona} />}
        {tab === 'journey'    && <JourneyScreen persona={persona} />}
        {tab === 'automation' && <AutomationScreen persona={persona} />}
        {tab === 'revenue'    && <RevenueScreen persona={persona} />}
        {tab === 'health'     && <HealthScreen persona={persona} />}
      </main>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────
// Top bar — brand + Industry Mode pill + Scenario + Export PDF
// ─────────────────────────────────────────────────────────────────
function TopBar({ mode, setMode, scenario, setScenario, brand, onExport, exporting, onPersonalise, onCopyLink, linkCopied, onBook, apiUrl }) {
  const today = new Date().toLocaleDateString('en-US', {
    weekday: 'long', month: 'long', day: 'numeric',
  });
  return (
    <header
      className="w-full border-b sticky top-0 z-30 backdrop-blur"
      style={{ background: 'rgba(11,10,20,0.72)', borderColor: T.line }}
    >
      <div className="max-w-[1400px] mx-auto px-6 py-4 flex items-center justify-between gap-6 flex-wrap">
        <div className="flex items-center gap-4 min-w-0">
          {brand.logoUrl ? (
            <img
              src={brand.logoUrl}
              alt=""
              className="w-10 h-10 rounded-xl shrink-0 object-cover"
              style={{ background: T.card, border: `1px solid ${T.line}` }}
              onError={(e) => { e.currentTarget.style.display = 'none'; }}
              data-testid="brand-logo"
            />
          ) : (
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
              style={{ background: T.accentDeep, color: '#fff' }}
            >
              <Sparkles size={18} strokeWidth={2.2} />
            </div>
          )}
          <div className="min-w-0">
            <div
              className="text-[22px] leading-none tracking-tight font-semibold truncate"
              style={{ fontFamily: T.fontDisplay, letterSpacing: '-0.01em', color: T.ink }}
              data-testid="demo-brand-name"
            >
              {brand.companyName}
            </div>
            <div className="text-xs mt-1 truncate max-w-[420px]" style={{ color: T.muted }}>
              {brand.tagline || 'Sample demo workspace'} · Live demo · sample data
            </div>
          </div>
          <button
            onClick={onPersonalise}
            data-testid="personalise-btn"
            className="ml-2 hidden sm:inline-flex items-center gap-1.5 text-[11px] px-2.5 py-1 rounded-full transition-colors"
            style={{ background: T.accentSoft, color: T.accent, border: `1px solid ${T.line}`, fontWeight: 600 }}
            title="Personalise this demo to your company"
          >
            <Edit2 size={10} /> Personalise
          </button>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <ScenarioPicker scenario={scenario} setScenario={setScenario} />
          <IndustryModePill mode={mode} setMode={setMode} />
          <button
            onClick={onCopyLink}
            data-testid="copy-link-btn"
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium transition-colors"
            style={{ background: T.card, color: T.ink, border: `1px solid ${T.line}` }}
            title="Copy a shareable demo link with current mode, scenario, and brand"
          >
            {linkCopied
              ? <><CheckCircle2 size={12} strokeWidth={2.5} style={{ color: T.success }} /> Copied</>
              : <><Link2 size={12} strokeWidth={2.5} /> Copy link</>}
          </button>
          <RecordDemoButton brand={brand} apiUrl={apiUrl} T={T} />
          {onBook && (
            <button
              onClick={onBook}
              data-testid="demo-book-btn"
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold transition-all active:scale-95"
              style={{ background: '#E06D53', color: '#fff', boxShadow: '0 4px 14px rgba(224,109,83,0.35)' }}
              title="Book a walkthrough — your personalized demo URL is included"
            >
              <CalendarClock size={12} strokeWidth={2.5} /> Book a walkthrough
            </button>
          )}
          <button
            data-testid="export-pdf-btn"
            onClick={onExport}
            disabled={exporting}
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium transition-all active:scale-95 disabled:opacity-60"
            style={{
              background: T.accentDeep, color: '#fff',
              boxShadow: '0 4px 14px rgba(124,53,220,0.28)',
              cursor: exporting ? 'wait' : 'pointer',
            }}
            aria-label="Export dashboard as PDF"
          >
            <Download size={12} strokeWidth={2.5} />
            {exporting ? 'Exporting…' : 'Export PDF'}
          </button>
          <div
            className="hidden lg:inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium"
            style={{ background: 'rgba(74,222,128,0.12)', color: T.success, border: `1px solid ${T.line}` }}
          >
            <CircleDot size={10} strokeWidth={3} /> Live demo · sample data
          </div>
        </div>
      </div>
    </header>
  );
}

function ScenarioPicker({ scenario, setScenario }) {
  const [open, setOpen] = useState(false);
  const active = SCENARIOS[scenario] || SCENARIOS.default;
  return (
    <div className="relative" data-testid="scenario-picker">
      <button
        onClick={() => setOpen((v) => !v)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium transition-colors"
        style={{ background: T.card, color: T.ink, border: `1px solid ${T.line}` }}
        data-testid="scenario-toggle"
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="uppercase text-[10px] tracking-[0.14em]" style={{ color: T.muted, fontWeight: 700 }}>
          Scenario
        </span>
        <span>{active.label}</span>
        <ChevronDown size={12} strokeWidth={2.5} style={{ color: T.muted }} />
      </button>
      {open && (
        <div
          className="absolute right-0 mt-1.5 rounded-xl overflow-hidden z-40"
          style={{
            background: T.card, border: `1px solid ${T.line}`,
            boxShadow: '0 10px 30px rgba(23,24,28,0.12)', minWidth: 220,
          }}
          role="listbox"
        >
          {Object.values(SCENARIOS).map((s) => {
            const on = s.key === scenario;
            return (
              <button
                key={s.key}
                onMouseDown={(e) => { e.preventDefault(); setScenario(s.key); setOpen(false); }}
                role="option"
                aria-selected={on}
                data-testid={`scenario-${s.key}`}
                className="w-full text-left px-3 py-2.5 flex items-start gap-2 text-sm transition-colors hover:opacity-90"
                style={{ color: T.ink }}
              >
                <div className="w-1.5 h-1.5 mt-2 rounded-full shrink-0" style={{ background: on ? T.accent : T.line }} />
                <div className="min-w-0">
                  <div className="font-medium">{s.label}</div>
                  <div className="text-xs" style={{ color: T.muted }}>{s.blurb}</div>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function IndustryModePill({ mode, setMode }) {
  return (
    <div
      className="inline-flex items-center rounded-full p-1"
      style={{ background: T.card, border: `1px solid ${T.line}` }}
      role="tablist"
      aria-label="Industry mode"
      data-testid="industry-mode-toggle"
    >
      {PERSONA_ORDER.map((k) => {
        const active = k === mode;
        return (
          <button
            key={k}
            onClick={() => setMode(k)}
            role="tab"
            aria-selected={active}
            aria-pressed={active}
            data-active={active ? 'true' : 'false'}
            data-testid={`mode-${k}`}
            className="px-4 py-1.5 rounded-full text-sm font-medium transition-all"
            style={{
              background: active ? T.accentDeep : 'transparent',
              color: active ? '#fff' : T.muted,
              boxShadow: active ? '0 1px 2px rgba(0,0,0,0.2)' : 'none',
              fontWeight: active ? 600 : 500,
            }}
          >
            {PERSONAS[k].label}
          </button>
        );
      })}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────
// Tab bar
// ─────────────────────────────────────────────────────────────────
function TabBar({ tab, setTab }) {
  return (
    <div className="w-full border-b" style={{ borderColor: T.line, background: T.canvas }}>
      <div className="max-w-[1400px] mx-auto px-6 flex items-center gap-1 overflow-x-auto">
        {TABS.map(({ key, label, icon: Icon }) => {
          const active = tab === key;
          return (
            <button
              key={key}
              onClick={() => setTab(key)}
              data-testid={`tab-${key}`}
              className="relative px-4 py-3 text-sm inline-flex items-center gap-2 whitespace-nowrap transition-colors"
              style={{
                color: active ? T.ink : T.muted,
                fontWeight: active ? 600 : 500,
              }}
            >
              <Icon size={14} strokeWidth={2} /> {label}
              {active && (
                <span
                  className="absolute left-2 right-2 -bottom-px h-[2px] rounded-full"
                  style={{ background: T.accent }}
                />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────
// Shared UI primitives
// ─────────────────────────────────────────────────────────────────
function Card({ children, className = '', style = {}, padded = true, testid }) {
  return (
    <div
      data-testid={testid}
      className={`rounded-2xl ${className}`}
      style={{
        background: T.card,
        border: `1px solid ${T.line}`,
        boxShadow: '0 1px 2px rgba(23,24,28,0.04)',
        padding: padded ? 20 : 0,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

function SectionTitle({ eyebrow, title, sub, right }) {
  return (
    <div className="flex items-end justify-between gap-4 mb-4 flex-wrap">
      <div>
        {eyebrow && (
          <div className="uppercase text-[11px] tracking-[0.14em] mb-2" style={{ color: T.accent, fontWeight: 600 }}>
            {eyebrow}
          </div>
        )}
        <h2
          className="text-[22px] leading-tight tracking-tight font-semibold"
          style={{ fontFamily: T.fontDisplay }}
        >
          {title}
        </h2>
        {sub && <p className="text-sm mt-1" style={{ color: T.muted }}>{sub}</p>}
      </div>
      {right}
    </div>
  );
}

function Kpi({ item }) {
  const up = item.tone === 'up';
  const Ico = up ? TrendingUp : TrendingDown;
  return (
    <Card testid={`kpi-${item.key}`} className="h-full">
      <div className="text-xs" style={{ color: T.muted, letterSpacing: '0.02em' }}>{item.label}</div>
      <div
        className="mt-2 text-[28px] leading-none font-semibold tabular-nums"
        style={{ fontFamily: T.fontDisplay, letterSpacing: '-0.01em' }}
      >
        {item.value}
      </div>
      <div className="mt-3 flex items-center gap-2 text-xs">
        <span
          className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md"
          style={{ background: up ? 'rgba(74,222,128,0.15)' : 'rgba(248,113,113,0.15)', color: up ? T.success : T.danger, fontWeight: 600 }}
        >
          <Ico size={12} strokeWidth={2.5} /> {item.delta}
        </span>
        <span style={{ color: T.muted }}>{item.sub}</span>
      </div>
    </Card>
  );
}

// ─────────────────────────────────────────────────────────────────
// Screen 1 — Overview (KPIs + Sankey + top movers)
// ─────────────────────────────────────────────────────────────────
function OverviewScreen({ persona }) {
  return (
    <div className="pt-6 space-y-6" data-testid="screen-overview">
      {/* KPI grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {persona.header.kpis.map((k) => <Kpi key={k.key} item={k} />)}
      </div>

      {/* Sankey — Source → Revenue */}
      <Card padded={false}>
        <div className="p-5 pb-0">
          <SectionTitle
            eyebrow="Attribution"
            title="Source → Revenue flow"
            sub="Every acquisition path, from first touch to booked revenue."
            right={
              <div className="flex items-center gap-1.5 text-xs" style={{ color: T.muted }}>
                <Sparkles size={12} /> ARIA-attributed · last 30 days
              </div>
            }
          />
        </div>
        <div style={{ height: 460 }} data-testid="sankey-chart">
          <ResponsiveSankey
            data={persona.sankey}
            margin={{ top: 20, right: 160, bottom: 20, left: 60 }}
            align="justify"
            colors={T.chartPalette}
            nodeOpacity={1}
            nodeThickness={14}
            nodeInnerPadding={3}
            nodeSpacing={16}
            nodeBorderWidth={0}
            nodeBorderRadius={3}
            linkOpacity={0.35}
            linkHoverOpacity={0.6}
            linkContract={2}
            enableLinkGradient
            labelPosition="outside"
            labelPadding={12}
            labelTextColor={T.ink}
            theme={{
              labels: { text: { fontFamily: T.fontUi, fontSize: 12, fontWeight: 500 } },
              tooltip: { container: { fontFamily: T.fontUi, fontSize: 12 } },
            }}
          />
        </div>
      </Card>

      {/* Two-up: revenue trend + top movers */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2">
          <SectionTitle eyebrow="Revenue" title="Trailing 30 days" sub="Daily booked revenue." />
          <div style={{ height: 220 }}>
            <ResponsiveContainer>
              <AreaChart data={persona.header.revenueSpark}>
                <defs>
                  <linearGradient id="revfill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={T.accent} stopOpacity={0.24} />
                    <stop offset="100%" stopColor={T.accent} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke={T.line} strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="day" tick={{ fill: T.muted, fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: T.muted, fontSize: 11 }} axisLine={false} tickLine={false} width={44} />
                <Tooltip
                  contentStyle={{ fontFamily: T.fontUi, fontSize: 12, borderRadius: 8, border: `1px solid ${T.line}`, background: T.card, color: T.ink }}
                  formatter={(v) => [`$${Number(v).toLocaleString()}`, 'Revenue']}
                  labelFormatter={(l) => `Day ${l}`}
                />
                <Area type="monotone" dataKey="value" stroke={T.accent} strokeWidth={2} fill="url(#revfill)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <SectionTitle eyebrow="Top movers" title="This week" />
          <ul className="space-y-3">
            {persona.channels.slice(0, 5).map((c, i) => (
              <li key={c.name} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-3 min-w-0">
                  <div
                    className="w-1.5 h-8 rounded-full shrink-0"
                    style={{ background: T.chartPalette[i % T.chartPalette.length] }}
                  />
                  <div className="min-w-0">
                    <div className="font-medium truncate">{c.name}</div>
                    <div className="text-xs" style={{ color: T.muted }}>ROAS {c.roas} · {c.orders} conv</div>
                  </div>
                </div>
                <div className="tabular-nums font-medium">${Number(c.revenue).toLocaleString()}</div>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────
// Screen 2 — Channel & Ad Performance
// ─────────────────────────────────────────────────────────────────
function ChannelsScreen({ persona }) {
  const barData = persona.channels.map((c) => ({
    name: c.name,
    Spend: c.spend,
    Revenue: c.revenue,
  }));

  return (
    <div className="pt-6 space-y-6" data-testid="screen-channels">
      <SectionTitle
        eyebrow="Acquisition"
        title="Channel & ad performance"
        sub="Spend, revenue, ROAS and CAC by channel."
      />

      <Card>
        <div style={{ height: 320 }}>
          <ResponsiveContainer>
            <BarChart data={barData} barGap={4}>
              <CartesianGrid stroke={T.line} strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="name" tick={{ fill: T.muted, fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: T.muted, fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${(v/1000).toFixed(0)}k`} />
              <Tooltip
                contentStyle={{ fontFamily: T.fontUi, fontSize: 12, borderRadius: 8, border: `1px solid ${T.line}`, background: T.card, color: T.ink }}
                formatter={(v) => `$${Number(v).toLocaleString()}`}
              />
              <Legend wrapperStyle={{ fontFamily: T.fontUi, fontSize: 12 }} />
              <Bar dataKey="Spend" fill={T.chartPalette[2]} radius={[6, 6, 0, 0]} />
              <Bar dataKey="Revenue" fill={T.accent} radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <Card padded={false}>
        <table className="w-full text-sm" data-testid="channels-table">
          <thead>
            <tr style={{ borderBottom: `1px solid ${T.line}` }}>
              {['Channel', 'Spend', 'Revenue', 'ROAS', 'CAC', 'Conversions'].map((h) => (
                <th
                  key={h}
                  className="text-left px-5 py-3 text-[11px] uppercase tracking-[0.12em]"
                  style={{ color: T.muted, fontWeight: 600 }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {persona.channels.map((c, i) => (
              <tr key={c.name} style={{ borderBottom: `1px solid ${T.line}` }}>
                <td className="px-5 py-3 font-medium">
                  <span
                    className="inline-block w-1.5 h-1.5 rounded-full mr-2 align-middle"
                    style={{ background: T.chartPalette[i % T.chartPalette.length] }}
                  />
                  {c.name}
                </td>
                <td className="px-5 py-3 tabular-nums">${c.spend.toLocaleString()}</td>
                <td className="px-5 py-3 tabular-nums font-medium">${c.revenue.toLocaleString()}</td>
                <td className="px-5 py-3 tabular-nums" style={{ color: T.accent, fontWeight: 600 }}>{c.roas}</td>
                <td className="px-5 py-3 tabular-nums">{c.cac === 0 ? '—' : `$${c.cac}`}</td>
                <td className="px-5 py-3 tabular-nums">{c.orders}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────
// Screen 3 — Journey (32-touchpoint timeline)
// ─────────────────────────────────────────────────────────────────
function JourneyScreen({ persona }) {
  const stages = useMemo(() => {
    const map = new Map();
    persona.journey.forEach((t) => {
      if (!map.has(t.stage)) map.set(t.stage, []);
      map.get(t.stage).push(t);
    });
    return Array.from(map.entries()).map(([k, v]) => ({ stage: k, items: v }));
  }, [persona]);

  return (
    <div className="pt-6 space-y-6" data-testid="screen-journey">
      <SectionTitle
        eyebrow="Account journey"
        title="32 touchpoints, first touch to advocacy"
        sub="Every signal ARIA reads or emits across the buyer path."
      />

      <Card>
        <div className="flex items-center gap-3 flex-wrap text-xs mb-4">
          {stages.map((s, i) => (
            <div key={s.stage} className="inline-flex items-center gap-2">
              <span
                className="inline-block w-2.5 h-2.5 rounded-full"
                style={{ background: T.chartPalette[i % T.chartPalette.length] }}
              />
              <span style={{ color: T.muted }}>{s.stage} · {s.items.length}</span>
            </div>
          ))}
        </div>

        <div className="space-y-6">
          {stages.map((s, si) => (
            <div key={s.stage}>
              <div
                className="uppercase text-[11px] tracking-[0.14em] mb-3"
                style={{ color: T.accent, fontWeight: 600 }}
              >
                {s.stage}
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-2">
                {s.items.map((t) => (
                  <div
                    key={t.idx}
                    className="rounded-xl px-3 py-2.5 flex items-start gap-3"
                    style={{ background: T.canvas, border: `1px solid ${T.line}` }}
                    data-testid={`touchpoint-${t.idx}`}
                  >
                    <div
                      className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0 text-[11px] font-semibold tabular-nums"
                      style={{ background: T.accentSoft, color: T.accent }}
                    >
                      {t.idx}
                    </div>
                    <div className="min-w-0">
                      <div className="text-sm font-medium truncate">{t.name}</div>
                      <div className="text-xs mt-0.5 flex items-center gap-1.5" style={{ color: T.muted }}>
                        <span>{t.channel}</span>
                        <span>·</span>
                        <span>day +{t.dayOffset}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────
// Screen 4 — Automation
// ─────────────────────────────────────────────────────────────────
function AutomationScreen({ persona }) {
  const flow = AUTOMATION_FLOWS[persona.key];

  return (
    <div className="pt-6 space-y-6" data-testid="screen-automation">
      <SectionTitle
        eyebrow="Automation"
        title="Flows currently running"
        sub="ARIA-managed sequences with live volumes and outcomes."
      />

      {/* Flow builder */}
      <Card>
        <SectionTitle
          eyebrow="Flow"
          title={flow.title}
          right={
            <div className="inline-flex items-center gap-2 text-xs px-2.5 py-1 rounded-full"
              style={{ background: 'rgba(74,222,128,0.15)', color: T.success, fontWeight: 600 }}>
              <Play size={11} strokeWidth={3} /> Running
            </div>
          }
        />
        <FlowCanvas flow={flow} />
      </Card>

      {/* Automation list */}
      <Card padded={false}>
        <table className="w-full text-sm">
          <thead>
            <tr style={{ borderBottom: `1px solid ${T.line}` }}>
              {['Automation', 'Status', 'Sent', 'Opened', 'Clicked', 'Revenue', ''].map((h) => (
                <th key={h} className="text-left px-5 py-3 text-[11px] uppercase tracking-[0.12em]"
                    style={{ color: T.muted, fontWeight: 600 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {persona.automations.map((a) => {
              const live = a.status === 'live';
              return (
                <tr key={a.id} style={{ borderBottom: `1px solid ${T.line}` }} data-testid={`auto-${a.id}`}>
                  <td className="px-5 py-3 font-medium">{a.name}</td>
                  <td className="px-5 py-3">
                    <span className="inline-flex items-center gap-1.5 text-xs px-2 py-1 rounded-full"
                      style={{
                        background: live ? 'rgba(74,222,128,0.15)' : T.canvas,
                        color: live ? T.success : T.muted,
                        fontWeight: 600,
                      }}>
                      {live ? <Play size={10} strokeWidth={3} /> : <Pause size={10} strokeWidth={3} />}
                      {live ? 'Live' : 'Draft'}
                    </span>
                  </td>
                  <td className="px-5 py-3 tabular-nums">{a.sent.toLocaleString()}</td>
                  <td className="px-5 py-3 tabular-nums">{a.opened}</td>
                  <td className="px-5 py-3 tabular-nums">{a.clicked}</td>
                  <td className="px-5 py-3 tabular-nums font-medium" style={{ color: T.accent }}>{a.revenue}</td>
                  <td className="px-5 py-3 text-right">
                    <ChevronRight size={14} style={{ color: T.muted }} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

function FlowCanvas({ flow }) {
  const W = 1080, H = 200;
  const nodeW = 132, nodeH = 56;
  const nodeById = Object.fromEntries(flow.nodes.map((n) => [n.id, n]));
  const style = (type) => ({
    trigger: { bg: T.accentDeep,             fg: '#fff',   border: T.accentDeep },
    action:  { bg: T.card,                   fg: T.ink,    border: T.line },
    wait:    { bg: T.canvas,                 fg: T.muted,  border: T.line },
    branch:  { bg: 'rgba(251,191,36,0.12)',  fg: T.warn,   border: 'rgba(251,191,36,0.35)' },
    end:     { bg: 'rgba(74,222,128,0.12)',  fg: T.success,border: 'rgba(74,222,128,0.35)' },
  }[type] || { bg: T.card, fg: T.ink, border: T.line });

  return (
    <div className="overflow-x-auto -mx-2 px-2" data-testid="flow-canvas">
      <svg width={W + nodeW} height={H} style={{ minWidth: W + nodeW }}>
        {/* edges */}
        {flow.edges.map((e, i) => {
          const a = nodeById[e.from], b = nodeById[e.to];
          const x1 = a.x + nodeW, y1 = a.y + nodeH / 2;
          const x2 = b.x,          y2 = b.y + nodeH / 2;
          const mx = (x1 + x2) / 2;
          const d = `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`;
          return (
            <g key={i}>
              <path d={d} fill="none" stroke={T.line} strokeWidth={1.5} />
              {e.label && (
                <text x={(x1 + x2) / 2} y={(y1 + y2) / 2 - 4} textAnchor="middle"
                  fontSize="10" fontFamily={T.fontUi} fill={T.muted}>
                  {e.label}
                </text>
              )}
            </g>
          );
        })}
        {/* nodes */}
        {flow.nodes.map((n) => {
          const s = style(n.type);
          return (
            <g key={n.id} transform={`translate(${n.x}, ${n.y})`}>
              <rect width={nodeW} height={nodeH} rx="10" fill={s.bg} stroke={s.border} />
              <text x="12" y="20" fontSize="11" fontFamily={T.fontUi} fill={s.fg} fontWeight="600">
                {n.label}
              </text>
              <text x="12" y="38" fontSize="10" fontFamily={T.fontUi} fill={s.fg} opacity="0.75">
                {n.sub}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────
// Screen 5 — Revenue & Outcomes
// ─────────────────────────────────────────────────────────────────
function RevenueScreen({ persona }) {
  return (
    <div className="pt-6 space-y-6" data-testid="screen-revenue">
      <SectionTitle
        eyebrow="Outcomes"
        title="Revenue & retention"
        sub="Cohort retention, LTV expansion, and product mix."
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Cohort */}
        <Card className="lg:col-span-2" padded={false}>
          <div className="p-5 pb-3">
            <SectionTitle eyebrow="Cohort" title="Retention by month" />
          </div>
          <table className="w-full text-sm" data-testid="cohort-table">
            <thead>
              <tr style={{ borderTop: `1px solid ${T.line}`, borderBottom: `1px solid ${T.line}` }}>
                <th className="text-left px-5 py-2 text-[11px] uppercase tracking-[0.12em]" style={{ color: T.muted }}>Cohort</th>
                {['M0', 'M1', 'M2', 'M3', 'M4', 'M5'].map((h) => (
                  <th key={h} className="text-center px-3 py-2 text-[11px] uppercase tracking-[0.12em]" style={{ color: T.muted }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {persona.revenue.cohorts.map((row) => (
                <tr key={row.cohort} style={{ borderBottom: `1px solid ${T.line}` }}>
                  <td className="px-5 py-2 font-medium">{row.cohort}</td>
                  {[row.m0, row.m1, row.m2, row.m3, row.m4, row.m5].map((v, i) => (
                    <td key={i} className="text-center px-3 py-2">
                      {v === null || v === undefined ? (
                        <span style={{ color: T.line }}>—</span>
                      ) : (
                        <span
                          className="inline-block px-2 py-1 rounded-md tabular-nums text-xs font-medium"
                          style={{
                            background: `rgba(164,111,232,${Math.min(0.85, v / 100)})`,
                            color: v > 45 ? '#0B0A14' : T.ink,
                          }}
                        >
                          {v}%
                        </span>
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </Card>

        {/* LTV curve */}
        <Card>
          <SectionTitle eyebrow="LTV" title="Customer lifetime value" />
          <div style={{ height: 240 }}>
            <ResponsiveContainer>
              <LineChart data={persona.revenue.ltvCurve}>
                <CartesianGrid stroke={T.line} strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="day" tick={{ fill: T.muted, fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: T.muted, fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${v >= 1000 ? (v/1000).toFixed(0) + 'k' : v}`} />
                <Tooltip
                  contentStyle={{ fontFamily: T.fontUi, fontSize: 12, borderRadius: 8, border: `1px solid ${T.line}`, background: T.card, color: T.ink }}
                  formatter={(v) => `$${Number(v).toLocaleString()}`}
                  labelFormatter={(l) => `Day ${l}`}
                />
                <Line type="monotone" dataKey="ltv" stroke={T.accent} strokeWidth={2.5} dot={{ r: 3, fill: T.accent }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      {/* Products */}
      <Card padded={false}>
        <div className="p-5 pb-3">
          <SectionTitle eyebrow="Mix" title="Top products / plans" />
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr style={{ borderTop: `1px solid ${T.line}`, borderBottom: `1px solid ${T.line}` }}>
              {['Product', 'Units', 'Revenue', 'Margin'].map((h) => (
                <th key={h} className="text-left px-5 py-2 text-[11px] uppercase tracking-[0.12em]" style={{ color: T.muted }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {persona.revenue.products.map((p, i) => (
              <tr key={p.name} style={{ borderBottom: `1px solid ${T.line}` }}>
                <td className="px-5 py-3 font-medium">
                  <span
                    className="inline-block w-1.5 h-1.5 rounded-full mr-2 align-middle"
                    style={{ background: T.chartPalette[i % T.chartPalette.length] }}
                  />
                  {p.name}
                </td>
                <td className="px-5 py-3 tabular-nums">{p.units.toLocaleString()}</td>
                <td className="px-5 py-3 tabular-nums font-medium">{p.revenue}</td>
                <td className="px-5 py-3 tabular-nums" style={{ color: T.accent, fontWeight: 600 }}>{p.margin}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────
// Screen 6 — Data Health
// ─────────────────────────────────────────────────────────────────
function HealthScreen({ persona }) {
  return (
    <div className="pt-6 space-y-6" data-testid="screen-health">
      <SectionTitle
        eyebrow="Foundation"
        title="Data health"
        sub="Freshness, completeness, and integration status."
        right={
          <div className="text-sm" style={{ color: T.muted }}>
            Overall <span className="font-semibold" style={{ color: T.accent }}>{persona.dataHealth.overall}%</span>
          </div>
        }
      />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {persona.dataHealth.dials.map((d) => (
          <Card key={d.label} testid={`health-${d.label}`}>
            <div className="flex items-center gap-4">
              <HealthDial value={d.health} />
              <div className="min-w-0">
                <div className="text-sm font-semibold truncate">{d.label}</div>
                <div className="text-xs mt-0.5 flex items-center gap-1.5" style={{ color: T.muted }}>
                  <Clock size={11} /> Synced {d.sync}
                </div>
                <div className="text-xs mt-1.5 flex items-center gap-1.5"
                  style={{ color: d.health >= 90 ? T.success : d.health >= 80 ? T.warn : T.danger }}>
                  {d.health >= 90 ? <CheckCircle2 size={12} /> : <AlertTriangle size={12} />}
                  {d.note}
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>

      <Card>
        <SectionTitle eyebrow="Recommendations" title="Next best actions" />
        <ul className="space-y-3 text-sm">
          {persona.dataHealth.dials
            .filter((d) => d.health < 95)
            .slice(0, 4)
            .map((d, i) => (
              <li key={i} className="flex items-start gap-3">
                <ArrowUpRight size={16} style={{ color: T.accent, marginTop: 2 }} />
                <div>
                  <span className="font-medium">Refresh {d.label}</span>
                  <span style={{ color: T.muted }}> — {d.note}. Reconnecting takes under 30 seconds.</span>
                </div>
              </li>
            ))}
          {persona.dataHealth.dials.filter((d) => d.health < 95).length === 0 && (
            <li className="text-sm" style={{ color: T.muted }}>All integrations are healthy. Nothing to fix.</li>
          )}
        </ul>
      </Card>
    </div>
  );
}

function HealthDial({ value }) {
  const size = 56, stroke = 6, r = (size - stroke) / 2, c = 2 * Math.PI * r;
  const dash = (value / 100) * c;
  const color = value >= 90 ? T.success : value >= 80 ? T.warn : T.danger;
  return (
    <svg width={size} height={size} className="shrink-0" style={{ transform: 'rotate(-90deg)' }}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={T.line} strokeWidth={stroke} />
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth={stroke}
        strokeDasharray={`${dash} ${c}`} strokeLinecap="round" />
      <text
        x={size/2} y={size/2}
        textAnchor="middle" dominantBaseline="central"
        fontSize="12" fontWeight="700" fill={T.ink}
        fontFamily={T.fontUi}
        transform={`rotate(90 ${size/2} ${size/2})`}
      >
        {value}
      </text>
    </svg>
  );
}
