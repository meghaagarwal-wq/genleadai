import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Users, Fire, ThermometerSimple, Buildings, CalendarBlank, Pause, EnvelopeOpen, Download, ChatCircleDots, ArrowRight, Plugs } from '@phosphor-icons/react';
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
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    ptApi.get('/api/pt/overview').then(r => setData(r.data)).catch(() => {}).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-sm text-[#64748B]">Loading…</div>;
  const m = data?.metrics || {};
  const c = data?.connections || {};

  return (
    <div data-testid="pt-overview-page">
      <PageHeader title="Overview" subtitle={data?.last_updated_at ? `Last activity ${fmtDateTime(data.last_updated_at)}` : 'Live engagement intelligence layer'} />

      {/* Connection state banner */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-6">
        <ConnBanner connected={c.saleshandy_connected} platform="Saleshandy"
          msg={c.saleshandy_connected ? 'Connected · receiving events' : 'No Saleshandy data connected yet.'} />
        <ConnBanner connected={c.lemlist_connected} platform="Lemlist"
          msg={c.lemlist_connected ? 'Connected · receiving events' : 'No Lemlist data connected yet.'} />
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 mb-6">
        <Tile testid="metric-engaged-leads"   icon={Users}            label="Engaged leads"     value={m.total_engaged_leads} />
        <Tile testid="metric-warm-leads"      icon={ThermometerSimple} label="Warm"             value={m.warm_leads}              accent="#F59E0B" />
        <Tile testid="metric-hot-leads"       icon={Fire}             label="Hot"              value={m.hot_leads}               accent="#DC2626" />
        <Tile testid="metric-engaged-accts"   icon={Buildings}        label="Engaged accounts" value={m.engaged_accounts_total} />
        <Tile testid="metric-sessions"        icon={CalendarBlank}    label="Sessions booked"  value={m.sessions_booked}         accent="#7C3AED" />
        <Tile testid="metric-pause"           icon={Pause}            label="Pause required"   value={m.accounts_requiring_pause} accent="#DC2626" />
        <Tile testid="metric-good-slice"      icon={EnvelopeOpen}     label="Good Slice subs"  value={m.good_slice_subscribers}  accent="#F59E0B" />
        <Tile testid="metric-magnet-claims"   icon={Download}         label="Magnet claims"    value={m.lead_magnet_claims}      accent="#F59E0B" />
        <Tile testid="metric-pos-replies"     icon={ChatCircleDots}   label="Positive replies" value={m.positive_replies}        accent="#7C35DC" />
        <Tile testid="metric-accts-total"     icon={Buildings}        label="Accounts mapped"  value={m.accounts_total}          accent="#475569" />
      </div>

      {data?.is_empty && (
        <div className="bg-white border border-dashed border-[#CBD5E1] rounded-xl p-10 text-center" data-testid="pt-overview-empty">
          <div className="text-base font-semibold text-[#0F172A]" style={{ fontFamily: 'Space Grotesk, Inter' }}>No engaged leads yet</div>
          <p className="text-sm text-[#64748B] mt-1.5 max-w-md mx-auto">
            Connect Saleshandy or Lemlist, configure webhooks, or upload a CSV to start tracking engagement.
          </p>
          <div className="mt-4 flex items-center justify-center gap-2">
            <Link to="/pt/leads" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-semibold text-white" style={{ background: '#7C35DC' }} data-testid="overview-cta-upload">
              Upload CSV <ArrowRight size={14} weight="bold" />
            </Link>
            <Link to="/pt/integrations" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-semibold text-[#7C35DC] border border-[#7C35DC]/30" data-testid="overview-cta-connect">
              Configure integrations
            </Link>
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
      <Link to="/pt/integrations" className="text-xs font-semibold text-[#7C35DC] hover:underline">Connect</Link>
    )}
  </div>
);

export default PtOverview;
