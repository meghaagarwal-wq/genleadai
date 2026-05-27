import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { Users, Fire, ThermometerSimple, Buildings, CalendarBlank, Pause, EnvelopeOpen, Download, ChatCircleDots, ArrowRight, Plugs, Lightning, MouseSimple, LinkedinLogo, Crown, CheckCircle, Warning, XCircle, CircleNotch } from '@phosphor-icons/react';
import { ptApi, PageHeader, fmtDateTime } from '../shared';

const Tile = ({ icon: Icon, label, value, accent = '#7C35DC', testid }) => (
  <div className="bg-white border border-[#E2E8F0] rounded-xl p-4" data-testid={testid}>
    <div className="flex items-center gap-2.5">
      <div className="w-8 h-8 rounded-md flex items-center justify-center" style={{ background: `${accent}12`, color: accent }}>
        <Icon size={16} weight="duotone" />
      </div>
      <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#64748B]">{label}</div>
    </div>
    <div className="mt-2.5 text-3xl font-extrabold text-[#0F172A]" style={{ fontFamily: 'Space Grotesk, Inter' }}>{value ?? 0}</div>
  </div>
);

const PtOverview = () => {
  const [data, setData] = useState(null);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [replaying, setReplaying] = useState(false);
  const [pulling, setPulling] = useState(false);
  const [pullingSh, setPullingSh] = useState(false);
  const [rescoring, setRescoring] = useState(false);

  const load = () => {
    ptApi.get('/api/pt/overview').then(r => setData(r.data)).catch(() => {}).finally(() => setLoading(false));
    ptApi.get('/api/pt/setup/health').then(r => setHealth(r.data)).catch(() => setHealth(null));
  };
  useEffect(() => { load(); }, []);

  const replayDemo = async () => {
    if (!window.confirm('Replay demo flow? This creates one demo lead and applies 4 events (subscribe → click → reply → session) to show the full cascade.')) return;
    setReplaying(true);
    try {
      const r = await ptApi.post('/api/pt/demo/replay');
      toast.success(`Demo lead created · final score ${r.data.lead.score} · ${r.data.tasks_created} tasks`);
      load();
    } catch (err) { toast.error(err.response?.data?.detail || 'Replay failed'); }
    finally { setReplaying(false); }
  };

  const pullFromLemlist = async () => {
    if (!window.confirm('Pull leads from Lemlist now? Fetches up to 5 campaigns × 25 leads each, auto-scored by Aria. Duplicates are skipped automatically.')) return;
    setPulling(true);
    try {
      const r = await ptApi.post('/api/pt/integrations/lemlist/pull-leads', { max_campaigns: 5, max_per_campaign: 25, auto_score: true });
      const d = r.data;
      toast.success(`Imported ${d.imported} new lead(s) from ${d.campaigns_processed} Lemlist campaign(s)${d.skipped ? ` · ${d.skipped} skipped (dedupe)` : ''}`, { duration: 6000 });
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Lemlist pull failed', { duration: 8000 });
    } finally { setPulling(false); }
  };

  const pullFromSaleshandy = async () => {
    if (!window.confirm('Pull prospects from Saleshandy now? Fetches up to 50 prospects, auto-scored by Aria. Duplicates are skipped automatically.')) return;
    setPullingSh(true);
    try {
      const r = await ptApi.post('/api/pt/integrations/saleshandy/pull-leads', { max_prospects: 50, auto_score: true });
      const d = r.data;
      toast.success(d.message || `Imported ${d.imported} new prospect(s) from Saleshandy${d.scored ? ` · ${d.scored} scored by Aria` : ''}`, { duration: 6000 });
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Saleshandy pull failed', { duration: 8000 });
    } finally { setPullingSh(false); }
  };

  const rescoreLeads = async () => {
    if (!window.confirm('Rescore your cold leads with Aria? Aria re-evaluates each cold lead against Pietential\'s ICP (HR leadership) and promotes matches to warm/hot.')) return;
    setRescoring(true);
    try {
      const r = await ptApi.post('/api/pt/leads/rescore', { max_leads: 100, only_stage: 'cold', only_score_zero: false });
      const d = r.data;
      toast.success(`Aria rescored ${d.rescored} leads — ${d.by_tier.hot} hot · ${d.by_tier.warm} warm · ${d.by_tier.cold} cold`, { duration: 7000 });
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Rescore failed', { duration: 8000 });
    } finally { setRescoring(false); }
  };

  if (loading) return <div className="text-sm text-[#64748B]">Loading…</div>;
  const m = data?.metrics || {};
  const c = data?.connections || {};

  return (
    <div data-testid="pt-overview-page">
      <PageHeader
        title="Overview"
        subtitle={data?.last_updated_at ? `Last activity ${fmtDateTime(data.last_updated_at)}` : 'Live engagement intelligence layer'}
        right={
          <div className="flex items-center gap-2 flex-wrap">
            <button onClick={pullFromLemlist} disabled={pulling} data-testid="pt-pull-lemlist-btn"
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-semibold border border-[#7C35DC] text-[#7C35DC] hover:bg-[#7C35DC]/8 disabled:opacity-50">
              <Download size={14} weight="fill" /> {pulling ? 'Pulling…' : 'Pull from Lemlist'}
            </button>
            <button onClick={pullFromSaleshandy} disabled={pullingSh} data-testid="pt-pull-saleshandy-btn"
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-semibold border border-[#7C35DC] text-[#7C35DC] hover:bg-[#7C35DC]/8 disabled:opacity-50">
              <EnvelopeOpen size={14} weight="fill" /> {pullingSh ? 'Pulling…' : 'Pull from Saleshandy'}
            </button>
            <button onClick={rescoreLeads} disabled={rescoring} data-testid="pt-rescore-btn"
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-semibold border border-[#16A34A] text-[#16A34A] hover:bg-[#16A34A]/8 disabled:opacity-50">
              <Lightning size={14} weight="fill" /> {rescoring ? 'Scoring…' : 'Aria rescore cold leads'}
            </button>
            <button onClick={replayDemo} disabled={replaying} data-testid="pt-replay-demo-btn"
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-semibold text-white disabled:opacity-50" style={{ background: '#7C35DC' }}>
              <Lightning size={14} weight="fill" /> {replaying ? 'Replaying…' : 'Replay demo'}
            </button>
          </div>
        }
      />

      {/* iter86 — Setup health panel: 5-line "is this workspace live?" check */}
      {health && <SetupHealthPanel health={health} />}

      {/* Connection state banner */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-6">
        <ConnBanner connected={c.saleshandy_connected} platform="Saleshandy"
          msg={c.saleshandy_connected ? `Connected · ${m.saleshandy_leads || 0} leads tracked` : 'No Saleshandy data connected yet.'} />
        <ConnBanner connected={c.lemlist_connected} platform="Lemlist"
          msg={c.lemlist_connected ? `Connected · ${m.lemlist_leads || 0} leads tracked` : 'No Lemlist data connected yet.'} />
      </div>

      {/* Primary platform metrics — Saleshandy + Lemlist focus */}
      <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-[#64748B] mb-2">Primary platforms</div>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 mb-6">
        <Tile testid="metric-email-opens"     icon={EnvelopeOpen}   label="Email opens"      value={m.email_opens} accent="#7C35DC" />
        <Tile testid="metric-email-clicks"    icon={MouseSimple}    label="Email clicks"     value={m.email_clicks} accent="#7C35DC" />
        <Tile testid="metric-sh-replies"      icon={ChatCircleDots} label="SH +ve replies"   value={m.saleshandy_positive_replies} accent="#7C35DC" />
        <Tile testid="metric-li-connections"  icon={LinkedinLogo}   label="LI connections"   value={m.linkedin_connections} accent="#C044E0" />
        <Tile testid="metric-ll-replies"      icon={ChatCircleDots} label="LL DM +ve"        value={m.lemlist_dm_replies} accent="#C044E0" />
      </div>

      {/* Pipeline health */}
      <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-[#64748B] mb-2">Pipeline health</div>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 mb-6">
        <Tile testid="metric-engaged-leads"   icon={Users}            label="Engaged leads"     value={m.total_engaged_leads} />
        <Tile testid="metric-warm-leads"      icon={ThermometerSimple} label="Warm"             value={m.warm_leads}              accent="#F59E0B" />
        <Tile testid="metric-hot-leads"       icon={Fire}             label="Hot"              value={m.hot_leads}               accent="#DC2626" />
        <Tile testid="metric-engaged-accts"   icon={Buildings}        label="Engaged accounts" value={m.engaged_accounts_total} />
        <Tile testid="metric-sessions"        icon={CalendarBlank}    label="Sessions booked"  value={m.sessions_booked}         accent="#7C3AED" />
        <Tile testid="metric-pause"           icon={Pause}            label="Pause required"   value={m.accounts_requiring_pause} accent="#DC2626" />
        <Tile testid="metric-john-owned"      icon={Crown}            label="John-owned"       value={m.john_owned_conversations} accent="#C044E0" />
        <Tile testid="metric-good-slice"      icon={EnvelopeOpen}     label="Good Slice subs"  value={m.good_slice_subscribers}  accent="#F59E0B" />
        <Tile testid="metric-magnet-claims"   icon={Download}         label="Magnet claims"    value={m.lead_magnet_claims}      accent="#475569" />
        <Tile testid="metric-pos-replies"     icon={ChatCircleDots}   label="Positive replies" value={m.positive_replies}        accent="#7C35DC" />
      </div>

      {data?.is_empty && (
        <div className="bg-white border border-dashed border-[#CBD5E1] rounded-xl p-10 text-center" data-testid="pt-overview-empty">
          <div className="text-base font-semibold text-[#0F172A]" style={{ fontFamily: 'Space Grotesk, Inter' }}>No engaged leads yet</div>
          <p className="text-sm text-[#64748B] mt-1.5 max-w-md mx-auto">
            Connect Saleshandy or Lemlist, configure webhooks, or upload a CSV to start tracking engagement.
          </p>
          <div className="mt-4 flex items-center justify-center gap-2 flex-wrap">
            <Link to="/app/leads" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-semibold text-white" style={{ background: '#7C35DC' }} data-testid="overview-cta-upload">
              Upload CSV <ArrowRight size={14} weight="bold" />
            </Link>
            <Link to="/app/integrations" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-semibold text-[#7C35DC] border border-[#7C35DC]/30" data-testid="overview-cta-connect">
              Configure integrations
            </Link>
            <button onClick={replayDemo} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-semibold text-[#7C35DC] border border-[#7C35DC]/30">
              <Lightning size={12} weight="fill" /> Or replay demo
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

const ConnBanner = ({ connected, platform, msg }) => (
  <div className="flex items-center gap-3 p-3 rounded-lg border" style={{ borderColor: connected ? '#7C35DC33' : '#CBD5E1', background: connected ? '#FAF7FF' : '#FFFFFF' }}>
    <Plugs size={18} weight="duotone" className={connected ? 'text-[#7C35DC]' : 'text-[#94A3B8]'} />
    <div className="flex-1">
      <div className="text-xs font-bold uppercase tracking-[0.16em]" style={{ color: connected ? '#7C35DC' : '#475569' }}>{platform}</div>
      <div className="text-sm text-[#0F172A]">{msg}</div>
    </div>
    {!connected && (
      <Link to="/app/integrations" className="text-xs font-semibold text-[#7C35DC] hover:underline">Connect</Link>
    )}
  </div>
);

// iter86 — Setup health: surfaces a single "is Pietential live?" panel.
const StatusIcon = ({ status }) => {
  if (status === 'ok') return <CheckCircle size={16} weight="fill" className="text-[#16A34A] flex-shrink-0" />;
  if (status === 'warn') return <Warning size={16} weight="fill" className="text-[#F59E0B] flex-shrink-0" />;
  if (status === 'fail') return <XCircle size={16} weight="fill" className="text-[#DC2626] flex-shrink-0" />;
  return <CircleNotch size={16} weight="bold" className="text-[#94A3B8] flex-shrink-0 animate-spin" />;
};

const SetupHealthPanel = ({ health }) => {
  const pct = Math.round((health.ready_count / health.total) * 100);
  const liveColor = health.live ? '#16A34A' : '#F59E0B';
  return (
    <div className="mb-6 bg-white border border-[#E2E8F0] rounded-xl overflow-hidden" data-testid="pt-setup-health">
      <div className="flex items-center gap-3 px-4 py-3 border-b border-[#E2E8F0]" style={{ background: health.live ? '#F0FDF4' : '#FEFCE8' }}>
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full" style={{ background: liveColor, boxShadow: `0 0 12px ${liveColor}` }} />
          <span className="text-xs font-extrabold uppercase tracking-[0.18em]" style={{ color: liveColor, fontFamily: 'Space Grotesk, Inter' }}>
            {health.live ? 'Workspace is live' : 'Setup incomplete'}
          </span>
        </div>
        <div className="ml-auto text-[11px] font-bold uppercase tracking-wider text-[#475569]">{health.ready_count}/{health.total} ready · {pct}%</div>
      </div>
      <div className="divide-y divide-[#F1F5F9]">
        {health.items.map((it) => (
          <div key={it.id} className="flex items-start gap-3 px-4 py-2.5" data-testid={`pt-setup-${it.id}`}>
            <StatusIcon status={it.status} />
            <div className="min-w-0 flex-1">
              <div className="text-sm font-semibold text-[#0F172A]" style={{ fontFamily: 'Space Grotesk, Inter' }}>{it.label}</div>
              <div className="text-[11px] text-[#64748B] mt-0.5 line-clamp-2">{it.detail}</div>
            </div>
            {it.status !== 'ok' && it.cta_path && (
              <Link to={it.cta_path} className="text-[11px] font-bold uppercase tracking-wider text-[#7C35DC] hover:underline flex-shrink-0">
                {it.cta}
              </Link>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default PtOverview;
