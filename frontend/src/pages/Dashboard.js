/**
 * Aria workspace dashboard — iter 71 simplification.
 *
 * Down from ~15 stacked sections (Command Room, Stories, Setup Checklist,
 * Lead Feed, Pipeline Mood, Pipeline Health, Event Mix, Founder Command Center,
 * Aria Today, Aria Agent Activity, Sync Activity Digest, sleeping banner,
 * brochure-opens banner, call-priority widget, KPIs, 4 charts, Recent Leads)
 * to the 5 sections requested:
 *
 *   1. Today's Priority Leads     ← real hot/warm leads only
 *   2. Lead Pipeline Snapshot     ← five simple counts
 *   3. Active Lead Sources        ← connected integrations + sync state
 *   4. Aria Recommendations       ← real next-best-actions only
 *   5. Recent Activity            ← real lead/integration events
 *
 * Empty states never show fake names. Fake / demo data lives in /demo only.
 */
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import api from '../config/api';
import EmptyDashboard from '../components/EmptyDashboard';
import {
  Users, TrendUp, Fire, Target, ArrowRight, Lightning,
  Sparkle, Clock, Warning, CheckCircle, Plug, ChartLineUp,
  PaperPlaneTilt, BellSimple,
} from '@phosphor-icons/react';

const greeting = () => {
  const h = new Date().getHours();
  if (h < 12) return 'Good morning';
  if (h < 17) return 'Good afternoon';
  return 'Good evening';
};

const SOURCE_LABEL = {
  saleshandy: 'Saleshandy', lemlist: 'Lemlist', website_form: 'Website Form',
  meta_ads: 'Meta Ads', google_ads: 'Google Ads', linkedin: 'LinkedIn',
  whatsapp: 'WhatsApp', email: 'Email', referral: 'Referral', webinar: 'Webinar',
  manual: 'Manual', csv: 'CSV Import', zoho_crm: 'Zoho CRM',
};

const Dashboard = ({ demo = false }) => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [analytics, setAnalytics] = useState(null);
  const [topLeads, setTopLeads] = useState([]);
  const [integrations, setIntegrations] = useState([]);
  const [recentActivity, setRecentActivity] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const params = demo ? { demo: 1 } : {};
        // Fire requests in parallel — each one independently catches its own
        // 404/500 so a single dead endpoint doesn't blank the entire dashboard.
        const [aRes, tRes, iRes, actRes] = await Promise.all([
          api.get('/api/analytics/dashboard', { params }).catch(() => ({ data: null })),
          api.get('/api/leads', { params: { ...params, limit: 5, status: 'hot' } }).catch(() => ({ data: { leads: [] } })),
          api.get('/api/integrations/list').catch(() => ({ data: { integrations: [] } })),
          api.get('/api/integrations/import-logs', { params: { limit: 5 } }).catch(() => ({ data: { logs: [] } })),
        ]);
        if (cancelled) return;
        setAnalytics(aRes.data);
        setTopLeads((tRes.data?.leads || []).slice(0, 5));
        setIntegrations((iRes.data?.integrations || []).filter((x) => x.status === 'connected'));
        setRecentActivity((actRes.data?.logs || []).slice(0, 5));
        // Recommendations are derived from the real data we already loaded — no
        // separate endpoint, so they're never fake.
        setRecommendations(buildRecommendations(aRes.data, iRes.data?.integrations || [], tRes.data?.leads || []));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [demo]);

  if (loading) return (
    <div className="flex items-center justify-center h-64" data-testid="dashboard-loading">
      <div className="flex flex-col items-center gap-3">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center animate-pulse" style={{ background: 'var(--gradient-brand)' }}>
          <Sparkle size={20} className="text-white" weight="fill" />
        </div>
        <span className="text-sm text-[#9B8AB0]">Loading your dashboard...</span>
      </div>
    </div>
  );

  const totalLeads = analytics?.total_leads ?? 0;
  const isEmpty = totalLeads === 0 && integrations.length === 0;

  // Brand new workspace with no leads + no integrations → guided empty state.
  if (isEmpty && !demo) {
    return <EmptyDashboard workspaceName={user?.tenant_name} founderName={user?.full_name} />;
  }

  const firstName = user?.full_name?.split(' ')[0] || 'there';
  // Iter77 fix — workspace name comes from active_tenant in localStorage, not from /auth/me.
  let workspaceName = user?.tenant_name;
  if (!workspaceName) {
    try {
      const activeTenant = JSON.parse(localStorage.getItem('active_tenant') || 'null');
      workspaceName = activeTenant?.name;
    } catch (_e) { /* ignore */ }
  }
  workspaceName = workspaceName || 'your business';

  return (
    <div data-testid="dashboard-page" className="space-y-6 max-w-[1280px] mx-auto aria-fade-up">
      {/* Header */}
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          {demo && (
            <div
              data-testid="demo-dashboard-banner"
              className="inline-flex items-center gap-1.5 mb-3 px-2.5 py-1 rounded-full bg-amber-100 border border-amber-300 text-amber-800 text-[10px] font-bold uppercase tracking-wider"
            >
              <Sparkle size={11} weight="fill" /> Demo Dashboard — sample data only
            </div>
          )}
          <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC] mb-2">
            {greeting()}, {firstName}
          </div>
          <h1 className="text-3xl md:text-4xl font-extrabold text-[#1A0A2E] leading-tight" style={{ letterSpacing: '-0.01em' }}>
            Your workspace today
          </h1>
          <p className="text-sm md:text-base text-[#5A4A7A] mt-2 max-w-2xl" data-testid="dashboard-subheading">
            Aria is working your leads for <strong className="text-[#1A0A2E]">{workspaceName}</strong> — who needs attention, what's happening, and what to do next.
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => navigate('/leads')} data-testid="view-all-leads-btn" className="flex items-center gap-2 btn-gradient px-4 py-2 rounded-xl text-sm font-semibold">
            View all leads <ArrowRight size={14} />
          </button>
        </div>
      </div>

      {/* ── SECTION 1 · Today's Priority Leads ─────────────────────────── */}
      <Section
        title="Today's priority leads"
        testid="section-priority-leads"
        icon={<Fire size={16} weight="duotone" className="text-rose-600" />}
        action={topLeads.length > 0 ? { label: 'View all', onClick: () => navigate('/leads') } : null}
      >
        {topLeads.length === 0 ? (
          <EmptyState
            testid="empty-priority-leads"
            title="No priority leads yet"
            subtitle="Once real leads are imported or captured, Aria will show the ones that need attention here."
            cta={{ label: 'Import leads', onClick: () => navigate('/integrations') }}
          />
        ) : (
          <div className="divide-y divide-[#F0ECF9]">
            {topLeads.map((l) => (
              <button
                key={l.id}
                onClick={() => navigate(`/leads/${l.id}`)}
                data-testid={`priority-lead-${l.id}`}
                className="w-full flex items-center justify-between px-4 py-3 hover:bg-[#F9F5FF] transition-colors text-left"
              >
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  <div className="w-9 h-9 rounded-full bg-white border border-[#E8E0F5] flex items-center justify-center flex-shrink-0">
                    <span className="text-xs font-bold text-[#7C35DC]">{(l.first_name?.[0] || '?').toUpperCase()}</span>
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-semibold text-[#1A0A2E] truncate">{l.first_name} {l.last_name}</span>
                      <span className="text-xs text-[#9B8AB0]">·</span>
                      <span className="text-xs text-[#5A4A7A] truncate">{l.company_name || '—'}</span>
                      {l.icp_tier === 'hot' && (
                        <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-rose-50 text-rose-700 border border-rose-200">Hot</span>
                      )}
                      {l.icp_tier === 'warm' && (
                        <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200">Warm</span>
                      )}
                      {(l.external_source === 'saleshandy' || l.external_source === 'lemlist') && (
                        <span className={`text-[9px] font-bold uppercase px-1.5 py-0.5 rounded border ${l.external_source === 'saleshandy' ? 'bg-orange-50 text-orange-700 border-orange-200' : 'bg-pink-50 text-pink-700 border-pink-200'}`}>
                          {l.external_source}
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-[#5A4A7A] mt-0.5 truncate">
                      {l.next_action_label || l.source_channel?.replace('_', ' ') || 'Awaiting follow-up'}
                    </div>
                  </div>
                </div>
                <ArrowRight size={14} className="text-[#9B8AB0] flex-shrink-0" />
              </button>
            ))}
          </div>
        )}
      </Section>

      {/* ── SECTION 2 · Lead Pipeline Snapshot ─────────────────────────── */}
      <Section
        title="Lead pipeline snapshot"
        testid="section-pipeline-snapshot"
        icon={<ChartLineUp size={16} weight="duotone" className="text-violet-600" />}
      >
        {!analytics || totalLeads === 0 ? (
          <EmptyState
            testid="empty-pipeline"
            title="No pipeline data yet"
            subtitle="Connect a lead source or import campaign data to see your pipeline."
            cta={{ label: 'Connect integration', onClick: () => navigate('/integrations') }}
          />
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 p-4">
            <PipelineMetric
              testid="pipeline-new"
              label="New"
              value={analytics?.status_distribution?.new || 0}
              tone="violet"
              icon={Users}
            />
            <PipelineMetric
              testid="pipeline-warm"
              label="Warm"
              value={analytics?.icp_distribution?.warm || 0}
              tone="amber"
              icon={TrendUp}
            />
            <PipelineMetric
              testid="pipeline-hot"
              label="Hot"
              value={analytics?.icp_distribution?.hot || 0}
              tone="rose"
              icon={Fire}
            />
            <PipelineMetric
              testid="pipeline-booked"
              label="Demo booked"
              value={analytics?.status_distribution?.qualified || 0}
              tone="emerald"
              icon={CheckCircle}
            />
            <PipelineMetric
              testid="pipeline-followup"
              label="Needs follow-up"
              value={analytics?.status_distribution?.contacted || 0}
              tone="sky"
              icon={Clock}
            />
          </div>
        )}
      </Section>

      {/* ── SECTION 3 · Active Lead Sources ─────────────────────────────── */}
      <Section
        title="Active lead sources"
        testid="section-active-sources"
        icon={<Plug size={16} weight="duotone" className="text-emerald-600" />}
        action={{ label: 'Manage all', onClick: () => navigate('/integrations') }}
      >
        {integrations.length === 0 ? (
          <EmptyState
            testid="empty-sources"
            title="No lead sources connected yet"
            subtitle="Connect Saleshandy, Lemlist, forms, ads, or CRM tools to start tracking leads."
            cta={{ label: 'Connect a source', onClick: () => navigate('/integrations') }}
          />
        ) : (
          <div className="divide-y divide-[#F0ECF9]">
            {integrations.map((src) => (
              <div key={src.type} data-testid={`active-source-${src.type}`} className="flex items-center justify-between px-4 py-3">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-9 h-9 rounded-lg bg-[#FAFAFA] border border-[#E8E0F5] flex items-center justify-center flex-shrink-0">
                    <Plug size={14} weight="duotone" className="text-[#7C35DC]" />
                  </div>
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-[#1A0A2E]">{SOURCE_LABEL[src.type] || src.label || src.type}</div>
                    <div className="text-[11px] text-[#5A4A7A]">
                      Status: <span className={src.status === 'connected' ? 'text-emerald-700 font-semibold' : 'text-amber-700 font-semibold'}>{src.status === 'connected' ? 'Connected' : src.status}</span>
                      {src.last_sync_at && <> · Last sync: {relative(src.last_sync_at)}</>}
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => navigate('/integrations')}
                  className="text-xs font-bold text-[#7C35DC] hover:underline"
                >
                  Manage
                </button>
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* ── SECTION 4 · Aria Recommendations ────────────────────────────── */}
      <Section
        title="Aria recommendations"
        testid="section-recommendations"
        icon={<Sparkle size={16} weight="duotone" className="text-violet-600" />}
      >
        {recommendations.length === 0 ? (
          <EmptyState
            testid="empty-recs"
            title="No recommendations yet"
            subtitle="Aria will show next steps once real lead activity comes in."
          />
        ) : (
          <div className="divide-y divide-[#F0ECF9]">
            {recommendations.map((rec, i) => (
              <button
                key={i}
                onClick={() => rec.onClick?.()}
                data-testid={`recommendation-${i}`}
                className="w-full flex items-center justify-between px-4 py-3 hover:bg-[#F9F5FF] transition-colors text-left"
              >
                <div className="flex items-start gap-3 min-w-0">
                  <div className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 ${rec.tone === 'urgent' ? 'bg-rose-50' : rec.tone === 'warn' ? 'bg-amber-50' : 'bg-violet-50'}`}>
                    {rec.tone === 'urgent' ? <Warning size={13} weight="fill" className="text-rose-600" />
                      : rec.tone === 'warn' ? <BellSimple size={13} weight="fill" className="text-amber-600" />
                      : <Lightning size={13} weight="fill" className="text-violet-600" />}
                  </div>
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-[#1A0A2E]">{rec.title}</div>
                    {rec.subtitle && <div className="text-xs text-[#5A4A7A] mt-0.5">{rec.subtitle}</div>}
                  </div>
                </div>
                {rec.cta && <span className="text-xs font-bold text-[#7C35DC] flex-shrink-0">{rec.cta} →</span>}
              </button>
            ))}
          </div>
        )}
      </Section>

      {/* ── SECTION 5 · Recent Activity ─────────────────────────────────── */}
      <Section
        title="Recent activity"
        testid="section-recent-activity"
        icon={<Clock size={16} weight="duotone" className="text-slate-600" />}
      >
        {recentActivity.length === 0 ? (
          <EmptyState
            testid="empty-activity"
            title="No recent activity"
            subtitle="Your workspace activity will appear here."
          />
        ) : (
          <div className="divide-y divide-[#F0ECF9]">
            {recentActivity.map((log, i) => (
              <div key={log.id || i} data-testid={`activity-${log.id || i}`} className="flex items-center justify-between px-4 py-3">
                <div className="flex items-center gap-3 min-w-0">
                  <PaperPlaneTilt size={13} weight="duotone" className="text-[#7C35DC] flex-shrink-0" />
                  <div className="min-w-0">
                    <div className="text-sm text-[#1A0A2E]">
                      <strong>{SOURCE_LABEL[log.tool] || log.tool}</strong> imported {log.totals?.imported || 0} lead{(log.totals?.imported || 0) === 1 ? '' : 's'}
                      {(log.totals?.failed || 0) > 0 && <span className="text-rose-600"> · {log.totals.failed} failed</span>}
                    </div>
                    <div className="text-[11px] text-[#9B8AB0]">{relative(log.created_at)}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>
    </div>
  );
};

// ─── Helpers ───────────────────────────────────────────────────────────────

function buildRecommendations(analytics, integrations, leads) {
  const recs = [];
  const connectedTools = (integrations || []).filter((i) => i.status === 'connected');
  const hotLeads = (leads || []).filter((l) => l.icp_tier === 'hot').length;

  // 1. Hot leads waiting → urgent
  if (hotLeads >= 1) {
    recs.push({
      tone: 'urgent',
      title: `${hotLeads} hot lead${hotLeads === 1 ? '' : 's'} need follow-up.`,
      subtitle: 'Reach out today while intent is high.',
      cta: 'Open Lead Inbox',
      onClick: () => (window.location.href = '/leads?icp_tier=hot'),
    });
  }

  // 2. Saleshandy/Lemlist connected but no imports yet → warn
  connectedTools.forEach((tool) => {
    if ((tool.type === 'saleshandy' || tool.type === 'lemlist') && !tool.last_sync_at) {
      recs.push({
        tone: 'warn',
        title: `${SOURCE_LABEL[tool.type]} is connected, but no leads imported yet.`,
        subtitle: 'Fetch campaigns and import to start tracking outbound activity.',
        cta: 'Open integration',
        onClick: () => (window.location.href = '/integrations'),
      });
    }
  });

  // 3. Errored integrations → urgent
  (integrations || []).filter((i) => i.status === 'error').forEach((tool) => {
    recs.push({
      tone: 'urgent',
      title: `${SOURCE_LABEL[tool.type] || tool.type} connection failed.`,
      subtitle: tool.error_message || 'Reconnect to resume syncing.',
      cta: 'Reconnect',
      onClick: () => (window.location.href = '/integrations'),
    });
  });

  // 4. No integrations connected → info
  if (connectedTools.length === 0 && (analytics?.total_leads || 0) === 0) {
    recs.push({
      tone: 'info',
      title: 'Connect your first lead source.',
      subtitle: 'Saleshandy, Lemlist, website forms, or CRM tools — any one gets the dashboard live.',
      cta: 'Set up',
      onClick: () => (window.location.href = '/integrations'),
    });
  }

  return recs.slice(0, 5);
}

function relative(iso) {
  if (!iso) return '—';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '—';
  const diff = Math.max(0, Date.now() - then);
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

// ─── Sub-components ────────────────────────────────────────────────────────

const Section = ({ title, icon, action, testid, children }) => (
  <section
    data-testid={testid}
    className="bg-white border border-[#E8E0F5] rounded-2xl overflow-hidden"
    style={{ boxShadow: 'var(--shadow-card)' }}
  >
    <div className="flex items-center justify-between px-4 py-3 border-b border-[#F0ECF9]">
      <div className="flex items-center gap-2">
        {icon}
        <h2 className="text-sm font-bold text-[#1A0A2E]">{title}</h2>
      </div>
      {action && (
        <button onClick={action.onClick} className="text-xs font-bold text-[#7C35DC] hover:underline">
          {action.label} →
        </button>
      )}
    </div>
    {children}
  </section>
);

const PipelineMetric = ({ label, value, tone, icon: Icon, testid }) => {
  const TONES = {
    violet: { bg: 'bg-violet-50', text: 'text-violet-700', border: 'border-violet-100' },
    amber:  { bg: 'bg-amber-50',  text: 'text-amber-700',  border: 'border-amber-100' },
    rose:   { bg: 'bg-rose-50',   text: 'text-rose-700',   border: 'border-rose-100' },
    emerald:{ bg: 'bg-emerald-50',text: 'text-emerald-700',border: 'border-emerald-100' },
    sky:    { bg: 'bg-sky-50',    text: 'text-sky-700',    border: 'border-sky-100' },
  }[tone] || { bg: 'bg-slate-50', text: 'text-slate-700', border: 'border-slate-100' };
  return (
    <div
      data-testid={testid}
      className={`${TONES.bg} border ${TONES.border} rounded-xl px-3 py-3 flex flex-col gap-1`}
    >
      <div className="flex items-center gap-1.5">
        <Icon size={12} weight="fill" className={TONES.text} />
        <span className="text-[10px] font-bold uppercase tracking-wider text-[#5A4A7A]">{label}</span>
      </div>
      <div className={`text-2xl font-extrabold ${TONES.text}`} style={{ letterSpacing: '-0.02em' }}>{value}</div>
    </div>
  );
};

const EmptyState = ({ title, subtitle, cta, testid }) => (
  <div data-testid={testid} className="px-6 py-8 text-center">
    <div className="text-sm font-semibold text-[#1A0A2E]">{title}</div>
    <div className="text-xs text-[#5A4A7A] mt-1 max-w-md mx-auto">{subtitle}</div>
    {cta && (
      <button
        onClick={cta.onClick}
        className="mt-3 inline-flex items-center gap-1.5 px-4 py-2 btn-gradient rounded-lg text-xs font-bold text-white"
      >
        <Target size={11} weight="fill" /> {cta.label}
      </button>
    )}
  </div>
);

export default Dashboard;
