/**
 * CommandCenter — the new /app home for every workspace.
 *
 * Hero: purple gradient + greeting (uses logged-in user's first name per
 * spec choice 4a) + setup-state subtext + 3 mode-aware CTAs.
 * Below: 3 step cards (mode-aware copy).
 * Below: "WHAT LIGHTS UP HERE ONCE LEADS START FLOWING" chips OR live KPI
 *        tiles once leads exist.
 * Top: WorkspacePullBar (dynamic per connected integrations).
 */
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight, Plus, Upload, PlayCircle, Brain, UserPlus, Robot, Crown,
  ChartLineUp, ChatCircleDots, Lightning, Users,
} from '@phosphor-icons/react';
import { useAuth } from '../../context/AuthContext';
import { ptApi } from '../shared';
import WorkspacePullBar from '../../components/WorkspacePullBar';
import api from '../../config/api';

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


const CommandCenter = () => {
  const { user } = useAuth();
  const [overview, setOverview] = useState(null);
  const [health, setHealth] = useState(null);
  const [mode, setMode] = useState('hybrid');
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [ov, hl, wt] = await Promise.all([
        ptApi.get('/api/pt/overview').catch(() => ({ data: { metrics: {}, is_empty: true } })),
        ptApi.get('/api/pt/setup/health').catch(() => ({ data: null })),
        api.get('/api/aria/workspace-type').catch(() => ({ data: { workspace_type: 'hybrid' } })),
      ]);
      setOverview(ov.data);
      setHealth(hl.data);
      setMode(wt.data?.workspace_type || 'hybrid');
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);
  useEffect(() => {
    const onTenant = () => load();
    window.addEventListener('aria:tenant-changed', onTenant);
    return () => window.removeEventListener('aria:tenant-changed', onTenant);
  }, []);

  const isB2B = mode === 'b2b';
  const noun = isB2B ? 'prospect' : 'lead';
  const nounPlural = isB2B ? 'prospects' : 'leads';
  const leadCount = overview?.metrics?.total_engaged_leads || 0;
  const hasLeads = leadCount > 0;

  const setupPct = health ? Math.round(((health.ready_count || 0) / Math.max(1, health.total || 1)) * 100) : null;
  const setupComplete = health ? !!health.live : true;

  const subtext = useMemo(() => {
    if (!setupComplete && setupPct !== null) return `Your workspace is ${setupPct}% ready. Let's finish setup.`;
    if (!hasLeads) return "Aria's ready — let's get her some leads to work.";
    return `Aria is working on ${leadCount} ${nounPlural} across ${overview?.metrics?.active_conversations || 0} conversations.`;
  }, [setupComplete, setupPct, hasLeads, leadCount, nounPlural, overview]);

  return (
    <div data-testid="command-center-page" className="space-y-6">
      {/* Top action bar */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-[#7C35DC]">Command Center</div>
          <h1 className="text-2xl font-extrabold text-[#0F172A]" style={{ fontFamily: 'Space Grotesk, Inter' }}>Today at a glance</h1>
        </div>
        <WorkspacePullBar onPullSuccess={load} />
      </div>

      {/* HERO */}
      <div
        className="relative rounded-2xl overflow-hidden p-8 md:p-10 text-white"
        style={{ background: 'linear-gradient(135deg, #5B1FAA 0%, #7C35DC 45%, #C044E0 100%)' }}
        data-testid="command-center-hero"
      >
        <div className="absolute inset-0 opacity-20 pointer-events-none"
          style={{ backgroundImage: 'radial-gradient(circle at 80% 20%, rgba(255,255,255,0.35) 0%, transparent 50%)' }} />
        <div className="relative z-10 max-w-3xl">
          <div className="text-[10px] font-bold uppercase tracking-[0.28em] text-white/80 mb-3" style={{ fontFamily: 'Plus Jakarta Sans' }}>
            ARIA · YOUR FIRST AI SALES HIRE
          </div>
          <div className="text-3xl md:text-4xl font-extrabold mb-2" style={{ fontFamily: 'Space Grotesk, Inter', letterSpacing: '-0.02em' }}>
            {greeting()}, {firstNameOf(user)}..
          </div>
          <div className="text-base text-white/85 mb-6" style={{ fontFamily: 'Plus Jakarta Sans' }}>
            {loading ? 'Spinning up…' : subtext}
          </div>
          <div className="flex flex-wrap items-center gap-2.5">
            {hasLeads ? (
              <Link
                to="/app/leads"
                data-testid="cmd-cta-pipeline"
                className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-lg bg-white text-[#5B1FAA] text-sm font-extrabold hover:bg-white/95"
              >
                <ChartLineUp size={16} weight="fill" /> View Pipeline
              </Link>
            ) : (
              <Link
                to="/app/leads"
                data-testid="cmd-cta-add-lead"
                className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-lg bg-white text-[#5B1FAA] text-sm font-extrabold hover:bg-white/95"
              >
                <Plus size={16} weight="bold" /> Add your first {noun}
              </Link>
            )}
            <Link
              to="/app/leads"
              data-testid="cmd-cta-import"
              className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-lg border border-white/40 text-white text-sm font-bold hover:bg-white/10"
            >
              <Upload size={16} weight="bold" /> Import CSV
            </Link>
            <a
              href="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
              target="_blank"
              rel="noopener noreferrer"
              data-testid="cmd-cta-demo"
              className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-lg border border-white/30 text-white text-sm font-bold hover:bg-white/10"
            >
              <PlayCircle size={16} weight="fill" /> Watch 2-min demo
            </a>
          </div>
        </div>
      </div>

      {/* STEP CARDS */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4" data-testid="command-step-cards">
        <StepCard
          step="01"
          icon={UserPlus}
          title={isB2B ? 'Add your prospects' : 'Add your leads'}
          body={isB2B
            ? 'Import a list, paste a domain, or let Aria pull from your connected campaigns.'
            : 'Paste them in, drop a CSV, or wire up a webhook from your ads or forms.'}
        />
        <StepCard
          step="02"
          icon={Robot}
          title={isB2B ? 'Aria researches them' : 'Aria qualifies them'}
          body={isB2B
            ? 'Aria enriches each prospect with intent signals, role fit, and recent context.'
            : 'Aria scores against your ICP, scripts the first message, and waits for the reply.'}
        />
        <StepCard
          step="03"
          icon={Crown}
          title="You close the deals"
          body="Your top 5 calls each morning land in your inbox. Aria handles the rest in the background."
        />
      </div>

      {/* WHAT LIGHTS UP / LIVE KPIs */}
      {!hasLeads ? (
        <div className="bg-white border border-[#E8E0F5] rounded-2xl p-6" data-testid="cmd-lights-up">
          <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-[#7C35DC] mb-3">
            What lights up here once {nounPlural} start flowing
          </div>
          <div className="flex flex-wrap gap-2">
            {(isB2B ? [
              { icon: ChartLineUp, label: 'Live KPI cards' },
              { icon: Lightning, label: 'Daily Aria brief' },
              { icon: Brain, label: 'Insight feed' },
              { icon: ChatCircleDots, label: 'Signal alerts' },
            ] : [
              { icon: ChartLineUp, label: 'Live KPI cards' },
              { icon: Lightning, label: 'Daily Aria brief' },
              { icon: ChatCircleDots, label: 'Conversation feed' },
              { icon: Users, label: 'Pipeline mood' },
            ]).map((c) => (
              <span
                key={c.label}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#F4F0FF] text-[#7C35DC] text-xs font-semibold border border-[#E0D4F7]"
                data-testid={`cmd-lights-${c.label.toLowerCase().replace(/\s+/g, '-')}`}
              >
                <c.icon size={12} weight="duotone" /> {c.label}
              </span>
            ))}
          </div>
        </div>
      ) : (
        <KPIs mode={mode} metrics={overview?.metrics || {}} />
      )}

      {/* Setup health, kept from old Overview, only when not yet live */}
      {health && !health.live && <SetupHealthCompact health={health} />}
    </div>
  );
};

const StepCard = ({ step, icon: Icon, title, body }) => (
  <div className="bg-white border border-[#E8E0F5] rounded-2xl p-5 hover:border-[#7C35DC] transition-colors" data-testid={`step-card-${step}`}>
    <div className="flex items-center justify-between mb-3">
      <span className="text-[10px] font-extrabold uppercase tracking-[0.22em] text-[#7C35DC]">{step}</span>
      <Icon size={20} weight="duotone" className="text-[#7C35DC]" />
    </div>
    <div className="text-base font-bold text-[#0F172A] mb-1.5" style={{ fontFamily: 'Space Grotesk, Inter' }}>{title}</div>
    <div className="text-sm text-[#475569] leading-relaxed">{body}</div>
  </div>
);

const KPIs = ({ mode, metrics }) => {
  const items = mode === 'b2b'
    ? [
        { label: 'Signals today', value: metrics.signals_today ?? metrics.lead_magnet_claims ?? 0 },
        { label: 'Prospects scanned', value: metrics.total_engaged_leads ?? 0 },
        { label: 'High-confidence signals', value: metrics.hot_leads ?? 0 },
        { label: 'Top prospect ICP', value: metrics.top_prospect_score ?? '—' },
      ]
    : [
        { label: 'Leads today', value: metrics.leads_today ?? metrics.total_engaged_leads ?? 0 },
        { label: 'Active conversations', value: metrics.active_conversations ?? 0 },
        { label: 'Calls booked', value: metrics.sessions_booked ?? 0 },
        { label: 'Conversion rate', value: metrics.conversion_rate ? `${metrics.conversion_rate}%` : '—' },
      ];
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="cmd-live-kpis">
      {items.map((it) => (
        <div key={it.label} className="bg-white border border-[#E8E0F5] rounded-xl p-4">
          <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#64748B]">{it.label}</div>
          <div className="mt-2 text-2xl font-extrabold text-[#0F172A]" style={{ fontFamily: 'Space Grotesk, Inter' }}>{it.value}</div>
        </div>
      ))}
    </div>
  );
};

const SetupHealthCompact = ({ health }) => (
  <div className="bg-white border border-[#FCD34D]/60 bg-[#FEFCE8] rounded-xl p-4 flex items-center gap-3" data-testid="cmd-setup-incomplete">
    <Lightning size={20} weight="fill" className="text-[#D97706] flex-shrink-0" />
    <div className="flex-1 text-sm text-[#92400E]">
      <span className="font-bold">Setup is {Math.round((health.ready_count / health.total) * 100)}% complete.</span>{' '}
      Finish wiring integrations + ICPs so Aria has what she needs.
    </div>
    <Link to="/app/integrations" className="text-xs font-bold uppercase tracking-wide text-[#92400E] hover:underline whitespace-nowrap">
      Finish setup <ArrowRight size={10} weight="bold" className="inline" />
    </Link>
  </div>
);

export default CommandCenter;
