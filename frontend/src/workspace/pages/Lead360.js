/**
 * Lead360 — iter126 unified 5-tab Lead view.
 *
 * Route: /app/leads/:id
 *
 * Layout
 * ──────
 *  ┌────────────────────────────────────────────────────────────────────┐
 *  │  HEADER (sticky)                                                   │
 *  │  avatar · name + title + company · ICP badge · stage · source     │
 *  │  Quick actions: [Send Message ▾] [Run Intel Scan] [Book Call]     │
 *  │                 [Change Stage ▾] [Connect ▾]                       │
 *  ├────────────────────────────────────────────────────────────────────┤
 *  │  TABS:  Overview · Intel · Automation · Conversations · Activity   │
 *  └────────────────────────────────────────────────────────────────────┘
 *
 * Backend contract (already wired)
 *   GET  /api/leads/:id              — base lead doc
 *   GET  /api/leads/:id/activities   — activity timeline
 *   PATCH /api/leads/:id             — stage change + notes save
 *   GET  /api/aria/conversation/:id  — conversation history (used by ConversationThread)
 *   /api/intel/:id/*                 — IntelTab handles its own calls
 */
import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate, useSearchParams, Link } from 'react-router-dom';
import {
  ArrowLeft, Brain, Calendar, Lightning, PaperPlaneTilt, CaretDown, Sparkle,
  Robot, CheckCircle, Clock, EnvelopeSimple, ChatCircleText, LinkedinLogo, Phone,
  Copy, Note, Pulse as ActivityIcon, Buildings, MapPin, Tag, Plus, X,
} from '@phosphor-icons/react';
import { toast } from 'sonner';
import api from '../../config/api';
import IntelTab from './IntelTab';
import ConversationThread from './ConversationThread';

const STAGE_COLOR = {
  qualified:     { bg: '#DCFCE7', text: '#166534', dot: '#16A34A', label: 'Qualified' },
  proposal_sent: { bg: '#DCFCE7', text: '#166534', dot: '#16A34A', label: 'Proposal sent' },
  negotiation:   { bg: '#DCFCE7', text: '#166534', dot: '#16A34A', label: 'Negotiating' },
  won:           { bg: '#DCFCE7', text: '#166534', dot: '#16A34A', label: 'Won' },
  contacted:     { bg: '#FEF3C7', text: '#92400E', dot: '#F59E0B', label: 'Nurturing' },
  nurture:       { bg: '#FEF3C7', text: '#92400E', dot: '#F59E0B', label: 'Nurturing' },
  new:           { bg: '#DBEAFE', text: '#1E3A8A', dot: '#3B82F6', label: 'New' },
  unqualified:   { bg: '#F1F5F9', text: '#475569', dot: '#64748B', label: 'Cold' },
  lost:          { bg: '#FEE2E2', text: '#991B1B', dot: '#DC2626', label: 'Lost' },
};

const SOURCE_ICON = {
  whatsapp:       { Icon: ChatCircleText,  color: '#16A34A', label: 'WhatsApp' },
  email:          { Icon: EnvelopeSimple,  color: '#3B82F6', label: 'Email' },
  linkedin:       { Icon: LinkedinLogo,    color: '#0A66C2', label: 'LinkedIn' },
  cold_call:      { Icon: Phone,           color: '#F97316', label: 'Cold Call' },
  website_form:   { Icon: Buildings,       color: '#7C35DC', label: 'Website Form' },
  csv_import:     { Icon: ActivityIcon,    color: '#94A3B8', label: 'CSV Import' },
  api:            { Icon: Lightning,       color: '#F59E0B', label: 'API' },
  referral:       { Icon: Sparkle,         color: '#EC4899', label: 'Referral' },
  webinar:        { Icon: ChatCircleText,  color: '#06B6D4', label: 'Webinar' },
  organic_search: { Icon: ActivityIcon,    color: '#10B981', label: 'Organic' },
  paid_ads:       { Icon: Lightning,       color: '#F59E0B', label: 'Paid Ads' },
  meta_webhook:   { Icon: ActivityIcon,    color: '#3B82F6', label: 'Meta Ads' },
  instagram:      { Icon: ChatCircleText,  color: '#E4405F', label: 'Instagram' },
  facebook:       { Icon: ChatCircleText,  color: '#1877F2', label: 'Facebook' },
  other:          { Icon: ActivityIcon,    color: '#94A3B8', label: 'Other' },
};

const TABS = [
  { id: 'overview',      label: 'Overview',      Icon: Note },
  { id: 'intel',         label: 'Intel',         Icon: Brain },
  { id: 'automation',    label: 'Automation',    Icon: Robot },
  { id: 'conversations', label: 'Conversations', Icon: ChatCircleText },
  { id: 'activity',      label: 'Activity',      Icon: ActivityIcon },
];

const initials = (lead) => {
  const f = (lead?.first_name || '').trim();
  const l = (lead?.last_name || '').trim();
  const ini = (f[0] || '') + (l[0] || '');
  return ini.toUpperCase() || (lead?.email || '?')[0].toUpperCase();
};

const fullName = (lead) => `${lead?.first_name || ''} ${lead?.last_name || ''}`.trim() || lead?.email || 'Lead';

const relativeTime = (iso) => {
  if (!iso) return '—';
  try {
    const dt = new Date(iso);
    const diff = Date.now() - dt.getTime();
    if (diff < 0) return dt.toLocaleString();
    const m = Math.floor(diff / 60000);
    if (m < 1) return 'just now';
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h ago`;
    const d = Math.floor(h / 24);
    if (d < 30) return `${d}d ago`;
    return dt.toLocaleDateString();
  } catch { return iso; }
};


// ─── Component ──────────────────────────────────────────────────────────
const Lead360 = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  // iter141 — V7: tab state lives in the URL (?tab=intel) so browser
  // back/forward correctly steps through tabs. Default is 'overview'.
  const [searchParams, setSearchParams] = useSearchParams();
  const ALLOWED_TABS = ['overview', 'intel', 'automation', 'conversations', 'activity'];
  const initialTab = ALLOWED_TABS.includes(searchParams.get('tab')) ? searchParams.get('tab') : 'overview';
  const [activeTab, setActiveTabState] = useState(initialTab);
  const setActiveTab = (t) => {
    setActiveTabState(t);
    const next = new URLSearchParams(searchParams);
    if (t === 'overview') next.delete('tab'); else next.set('tab', t);
    setSearchParams(next, { replace: false });
  };
  // Sync state if the URL changes externally (back/forward).
  useEffect(() => {
    const t = searchParams.get('tab');
    const want = ALLOWED_TABS.includes(t) ? t : 'overview';
    if (want !== activeTab) setActiveTabState(want);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);
  const [lead, setLead] = useState(null);
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [connectOpen, setConnectOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      // Try the global ARIA endpoint first; if the workspace stores leads
      // under /api/pt/leads (Pietential B2B workspace) we transparently
      // fall back so the same Lead 360 view works for both pipelines.
      let leadDoc = null;
      try {
        const r = await api.get(`/api/leads/${id}`);
        leadDoc = r.data;
      } catch (e) {
        if (e?.response?.status === 404) {
          const r2 = await api.get(`/api/pt/leads/${id}`);
          // Pietential wraps the lead under .lead — flatten so we keep the
          // same UI bindings.
          leadDoc = r2.data?.lead ? { ...r2.data.lead, _pt_extras: r2.data } : r2.data;
        } else { throw e; }
      }
      const ar = await api.get(`/api/leads/${id}/activities`).catch(() => ({ data: { activities: [] } }));
      setLead(leadDoc);
      setActivities(ar.data?.activities || ar.data || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Could not load lead');
      navigate('/app/leads');
    } finally { setLoading(false); }
  }, [id, navigate]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const onClose = () => setConnectOpen(false);
    window.addEventListener('click', onClose);
    return () => window.removeEventListener('click', onClose);
  }, []);

  const changeStage = async (newStatus) => {
    try {
      const r = await api.patch(`/api/leads/${id}`, { status: newStatus });
      setLead(r.data);
      toast.success(`Stage → ${newStatus}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Stage update failed');
    }
  };

  const runIntelScan = async () => {
    try {
      await api.post(`/api/intel/${id}/research`, { refresh: true });
      toast.success('Intel scan started');
      setActiveTab('intel');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Scan failed');
    }
  };

  if (loading) return <div className="text-sm" style={{ color: 'var(--theme-text-muted)' }} data-testid="lead360-loading">Loading lead…</div>;
  if (!lead) return null;

  const stage = STAGE_COLOR[(lead.status || 'new').toLowerCase()] || STAGE_COLOR.new;
  const source = SOURCE_ICON[lead.source_channel || 'other'] || SOURCE_ICON.other;
  const SourceIcon = source.Icon;
  const icpScore = lead.icp_score || 0;
  const icpTier = lead.icp_tier || 'cold';
  const icpColor = icpScore >= 80 ? '#7C35DC' : icpScore >= 60 ? '#F59E0B' : '#64748B';

  return (
    <div className="space-y-5 max-w-[1400px] mx-auto" data-testid="lead360-page" style={{ color: 'var(--theme-text)' }}>
      <button
        onClick={() => navigate('/app/leads')}
        data-testid="lead360-back"
        className="inline-flex items-center gap-1.5 text-xs font-semibold"
        style={{ color: 'var(--theme-text-muted)' }}
      >
        <ArrowLeft size={12} weight="bold" /> Back to Leads
      </button>

      {/* ─── Header ──────────────────────────────────────────────── */}
      <div
        className="rounded-2xl border p-5 flex flex-wrap items-start gap-4"
        style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }}
        data-testid="lead360-header"
      >
        {/* Avatar */}
        <div
          className="shrink-0 w-14 h-14 rounded-2xl flex items-center justify-center text-white font-extrabold text-lg shadow"
          style={{ background: 'linear-gradient(135deg, #5b21b6 0%, #7c3aed 60%)', fontFamily: 'Space Grotesk, Inter' }}
          data-testid="lead360-avatar"
        >
          {initials(lead)}
        </div>

        {/* Name + meta */}
        <div className="flex-1 min-w-[280px]">
          <h1 className="text-xl font-extrabold leading-tight" style={{ fontFamily: 'Space Grotesk, Inter', letterSpacing: '-0.01em' }} data-testid="lead360-name">
            {fullName(lead)}
          </h1>
          <div className="text-sm mt-0.5" style={{ color: 'var(--theme-text-muted)' }} data-testid="lead360-title-company">
            {[lead.job_title, lead.company_name].filter(Boolean).join(' · ') || 'No company info yet'}
          </div>

          {/* Badge row */}
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider"
              style={{ background: icpColor + '15', color: icpColor, border: `1px solid ${icpColor}30` }}
              data-testid="lead360-icp-badge"
            >
              <Sparkle size={10} weight="fill" /> ICP {icpTier} · {icpScore}
            </span>
            <span
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider"
              style={{ background: stage.bg, color: stage.text }}
              data-testid="lead360-stage-badge"
            >
              <span className="w-1.5 h-1.5 rounded-full" style={{ background: stage.dot }} /> {stage.label}
            </span>
            <span
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider"
              style={{ background: source.color + '15', color: source.color, border: `1px solid ${source.color}30` }}
              data-testid="lead360-source-badge"
            >
              <SourceIcon size={10} weight="duotone" /> {source.label}
            </span>
            <span className="text-[10px] font-semibold" style={{ color: 'var(--theme-text-muted)' }} data-testid="lead360-meta-times">
              Added {relativeTime(lead.created_at)} · Last activity {relativeTime(lead.last_contacted_at || lead.updated_at)}
            </span>
          </div>
        </div>

        {/* Quick actions */}
        <div className="flex flex-wrap items-center gap-2" data-testid="lead360-quick-actions">
          <button
            onClick={() => setActiveTab('conversations')}
            data-testid="lead360-action-send-message"
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-xs font-bold text-white"
            style={{ background: 'linear-gradient(135deg, #5b21b6 0%, #7c3aed 60%)' }}
          >
            <PaperPlaneTilt size={12} weight="fill" /> Send Message
          </button>
          <button
            onClick={runIntelScan}
            data-testid="lead360-action-run-scan"
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-xs font-bold border"
            style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text)' }}
          >
            <Brain size={12} weight="duotone" /> Run Intel Scan
          </button>
          <button
            onClick={() => navigate('/app/call-booking')}
            data-testid="lead360-action-book-call"
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-xs font-bold border"
            style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text)' }}
          >
            <Calendar size={12} weight="duotone" /> Book Call
          </button>

          {/* Change Stage dropdown */}
          <StageDropdown current={lead.status} onPick={changeStage} />

          {/* Connect dropdown */}
          <div className="relative" onClick={(e) => e.stopPropagation()} data-testid="lead360-connect-wrap">
            <button
              onClick={() => setConnectOpen((v) => !v)}
              data-testid="lead360-action-connect"
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-xs font-bold border"
              style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text)' }}
            >
              <Plus size={12} weight="bold" /> Connect <CaretDown size={10} />
            </button>
            {connectOpen && (
              <div
                className="absolute right-0 mt-1.5 w-64 rounded-xl shadow-xl z-50 overflow-hidden border"
                style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border-strong)' }}
                data-testid="lead360-connect-menu"
              >
                {[
                  { id: 'journey',     label: '+ Add to Touchpoint Journey', to: '/app/touchpoints', icon: Lightning },
                  { id: 'sequence',    label: '+ Enrol in Sequence',         to: '/app/automation',  icon: Robot },
                  { id: 'book',        label: 'Book a Call',                 to: '/app/call-booking', icon: Calendar },
                  { id: 'approval',    label: 'Send to Approval Queue',      to: '/app/approvals',   icon: CheckCircle },
                  { id: 'suppress',    label: 'Suppress Lead',               action: 'suppress',     icon: X },
                ].map((opt) => (
                  <button
                    key={opt.id}
                    onClick={async () => {
                      setConnectOpen(false);
                      if (opt.action === 'suppress') {
                        if (!window.confirm('Suppress this lead? Removes from all sequences and scans.')) return;
                        try {
                          await api.patch(`/api/leads/${id}`, { status: 'unqualified', notes: 'Suppressed by user' });
                          toast.success('Lead suppressed');
                          load();
                        } catch (e) { toast.error('Suppress failed'); }
                      } else if (opt.to) {
                        navigate(opt.to);
                      }
                    }}
                    data-testid={`lead360-connect-${opt.id}`}
                    className="w-full flex items-center gap-2 px-3 py-2.5 text-sm text-left transition-colors hover:bg-[var(--theme-surface2)]"
                    style={{ color: 'var(--theme-text)' }}
                  >
                    <opt.icon size={13} weight="duotone" style={{ color: 'var(--theme-text-muted)' }} />
                    {opt.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ─── Tabs ────────────────────────────────────────────────── */}
      <div className="flex flex-wrap gap-1.5" data-testid="lead360-tabs">
        {TABS.map((t) => {
          const Icon = t.Icon;
          const active = activeTab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              data-testid={`lead360-tab-${t.id}`}
              className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-md text-xs font-semibold border transition-colors"
              style={{
                background: active ? 'var(--theme-purple-dim)' : 'var(--theme-surface)',
                borderColor: active ? 'var(--theme-purple)' : 'var(--theme-border-strong)',
                color: active ? 'var(--theme-purple-light)' : 'var(--theme-text-muted)',
              }}
            >
              <Icon size={12} weight="duotone" /> {t.label}
            </button>
          );
        })}
      </div>

      {/* ─── Tab content ─────────────────────────────────────────── */}
      {activeTab === 'overview'      && <OverviewTab lead={lead} setLead={setLead} reload={load} />}
      {activeTab === 'intel'         && <IntelTab leadId={id} lead={lead} />}
      {activeTab === 'automation'    && <AutomationTab lead={lead} onConnect={() => setConnectOpen(true)} />}
      {activeTab === 'conversations' && <ConversationThread leadId={id} lead={lead} />}
      {activeTab === 'activity'      && <ActivityTab activities={activities} />}
    </div>
  );
};


// ─── Stage dropdown ─────────────────────────────────────────────────────
const StageDropdown = ({ current, onPick }) => {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const onClose = () => setOpen(false);
    window.addEventListener('click', onClose);
    return () => window.removeEventListener('click', onClose);
  }, []);
  const stages = ['new', 'contacted', 'qualified', 'proposal_sent', 'negotiation', 'won', 'lost', 'nurture', 'unqualified'];
  return (
    <div className="relative" onClick={(e) => e.stopPropagation()}>
      <button
        onClick={() => setOpen((v) => !v)}
        data-testid="lead360-action-change-stage"
        className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-xs font-bold border"
        style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text)' }}
      >
        <Tag size={12} weight="duotone" /> Change Stage <CaretDown size={10} />
      </button>
      {open && (
        <div
          className="absolute right-0 mt-1.5 w-48 rounded-xl shadow-xl z-50 overflow-hidden border"
          style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border-strong)' }}
          data-testid="lead360-stage-menu"
        >
          {stages.map((s) => (
            <button
              key={s}
              onClick={() => { setOpen(false); onPick(s); }}
              data-testid={`lead360-stage-opt-${s}`}
              className="w-full px-3 py-2 text-sm text-left transition-colors hover:bg-[var(--theme-surface2)]"
              style={{
                background: current === s ? 'var(--theme-purple-dim)' : undefined,
                color: 'var(--theme-text)',
              }}
            >
              {s.replace(/_/g, ' ')}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};


// ─── Overview tab ───────────────────────────────────────────────────────
const OverviewTab = ({ lead, setLead, reload }) => {
  const [notes, setNotes] = useState(lead.notes || '');
  const [saving, setSaving] = useState(false);

  const saveNotes = async () => {
    setSaving(true);
    try {
      const r = await api.patch(`/api/leads/${lead.id}`, { notes });
      setLead(r.data);
      toast.success('Notes saved');
    } catch (e) {
      toast.error('Save failed');
    } finally { setSaving(false); }
  };

  const copy = async (label, value) => {
    if (!value) return;
    try { await navigator.clipboard.writeText(value); toast.success(`${label} copied`); }
    catch { toast.error('Copy failed'); }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4" data-testid="lead360-tab-overview-content">
      {/* Left — contact + company + source */}
      <div className="lg:col-span-2 space-y-4">
        <Card title="Contact details">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Field label="Email"    value={lead.email}    onCopy={() => copy('Email', lead.email)} />
            <Field label="Phone"    value={lead.phone}    onCopy={() => copy('Phone', lead.phone)} />
            <Field label="LinkedIn" value={lead.linkedin_url} onCopy={() => copy('LinkedIn', lead.linkedin_url)} />
            <Field label="Website"  value={lead.website || lead.company_website} onCopy={() => copy('Website', lead.website || lead.company_website)} />
          </div>
        </Card>

        <Card title="Company">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Field label="Company"  value={lead.company_name} />
            <Field label="Industry" value={lead.industry} />
            <Field label="Job title" value={lead.job_title} />
            <Field label="Country"  value={lead.country || lead.city} />
          </div>
        </Card>

        <Card title="ICP match">
          <div className="flex items-center gap-3">
            <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ background: 'var(--theme-border)' }}>
              <div className="h-full rounded-full" style={{ width: `${Math.min(100, lead.icp_score || 0)}%`, background: 'linear-gradient(90deg, #16A34A, #7C35DC)' }} />
            </div>
            <span className="text-sm font-extrabold numeric" style={{ fontFamily: 'Space Grotesk, Inter' }}>{lead.icp_score || 0}/100</span>
          </div>
          {(lead.icp_match_reason || lead.icp_reason) && (
            <p className="text-xs mt-2" style={{ color: 'var(--theme-text-muted)' }}>{lead.icp_match_reason || lead.icp_reason}</p>
          )}
        </Card>

        <Card title="Source">
          <div className="text-sm space-y-1">
            <div>Channel: <b>{(lead.source_channel || 'other').replace(/_/g, ' ')}</b></div>
            <div>Date added: <b>{lead.created_at ? new Date(lead.created_at).toLocaleString() : '—'}</b></div>
            {(lead.utm_source || lead.utm_campaign || lead.utm_medium) && (
              <div>UTM: <b>{[lead.utm_source, lead.utm_medium, lead.utm_campaign].filter(Boolean).join(' / ')}</b></div>
            )}
          </div>
        </Card>
      </div>

      {/* Right — notes + tags + assigned */}
      <div className="space-y-4">
        <Card title="Notes">
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            onBlur={saveNotes}
            data-testid="lead360-notes-textarea"
            rows={6}
            className="w-full rounded-lg border px-3 py-2 text-sm outline-none"
            style={{ background: 'var(--theme-surface2)', borderColor: 'var(--theme-border)', color: 'var(--theme-text)' }}
            placeholder="Add a note — auto-saves on blur."
          />
          {saving && <div className="text-[10px] mt-1" style={{ color: 'var(--theme-text-muted)' }}>Saving…</div>}
        </Card>

        <Card title="Tags">
          <div className="flex flex-wrap gap-1.5">
            {(lead.tags || []).length === 0 && <span className="text-xs" style={{ color: 'var(--theme-text-muted)' }}>No tags</span>}
            {(lead.tags || []).map((t) => (
              <span key={t} className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded" style={{ background: 'var(--theme-purple-dim)', color: 'var(--theme-purple-light)' }}>{t}</span>
            ))}
          </div>
        </Card>

        <Card title="Assigned to">
          <div className="text-sm">{lead.assigned_to || lead.owner_name || <span style={{ color: 'var(--theme-text-muted)' }}>Unassigned</span>}</div>
        </Card>
      </div>
    </div>
  );
};


// ─── Automation tab ─────────────────────────────────────────────────────
const AutomationTab = ({ lead, onConnect }) => {
  // Placeholder data — wired to real touchpoint engine state in a follow-up
  // pass. The CTA row at the top is always visible per the spec (V13/V30).
  const [activeSequences, setActiveSequences] = useState([]);
  const [journeyState, setJourneyState] = useState(null);
  const [rulesFired, setRulesFired] = useState([]);

  useEffect(() => {
    api.get(`/api/touchpoints/lead/${lead.id}/state`)
      .then((r) => setJourneyState(r.data))
      .catch(() => setJourneyState(null));
    api.get(`/api/outreach/lead/${lead.id}/active-sequences`)
      .then((r) => setActiveSequences(r.data?.sequences || []))
      .catch(() => setActiveSequences([]));
    api.get(`/api/automation-rules/lead/${lead.id}/fired`)
      .then((r) => setRulesFired(r.data?.fired || []))
      .catch(() => setRulesFired([]));
  }, [lead.id]);

  return (
    <div className="space-y-4" data-testid="lead360-tab-automation-content">
      {/* CTA row — always visible per spec V13/V30 */}
      <div className="flex flex-wrap items-center gap-2" data-testid="lead360-automation-cta-row">
        <Link
          to="/app/touchpoints"
          data-testid="lead360-cta-add-to-journey"
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-xs font-bold border"
          style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-purple)', color: 'var(--theme-purple-light)' }}
        >
          <Plus size={12} weight="bold" /> Add to Touchpoint Journey
        </Link>
        <Link
          to="/app/automation"
          data-testid="lead360-cta-enrol-sequence"
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-xs font-bold border"
          style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-purple)', color: 'var(--theme-purple-light)' }}
        >
          <Plus size={12} weight="bold" /> Enrol in Sequence
        </Link>
      </div>

      {/* Section A — active sequences */}
      <Card title="Active sequences">
        {activeSequences.length === 0 ? (
          <EmptyHint text="No active sequences yet — enrol this lead via the button above." />
        ) : (
          <div className="space-y-2">
            {activeSequences.map((s) => (
              <div key={s.id} className="text-sm flex justify-between items-center border rounded-md px-3 py-2" style={{ borderColor: 'var(--theme-border)' }}>
                <div>
                  <div className="font-semibold">{s.name}</div>
                  <div className="text-[10px]" style={{ color: 'var(--theme-text-muted)' }}>Step {s.current_step} · next {relativeTime(s.next_at)}</div>
                </div>
                <div className="text-[10px] font-bold uppercase" style={{ color: 'var(--theme-text-muted)' }}>{s.status}</div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Section B — touchpoint journey */}
      <Card title="Touchpoint Journey">
        {!journeyState ? (
          <EmptyHint text="No journey for this lead yet — open the Journey page to start one." />
        ) : (
          <>
            <div className="text-sm font-semibold">Current: Step {journeyState.current_number || 1}</div>
            <div className="text-[11px] mt-0.5" style={{ color: 'var(--theme-text-muted)' }}>
              {journeyState.next_preview || 'Next touchpoint coming soon.'}
            </div>
            <div className="mt-2 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--theme-border)' }}>
              <div className="h-full rounded-full" style={{ width: `${(journeyState.progress_pct || 0)}%`, background: '#7C35DC' }} />
            </div>
          </>
        )}
      </Card>

      {/* Section C — automation rules fired */}
      <Card title="Automation rules fired">
        {rulesFired.length === 0 ? (
          <EmptyHint text="No automation rules have fired for this lead yet." />
        ) : (
          <ul className="text-sm space-y-1">
            {rulesFired.map((r) => (
              <li key={r.id} className="flex justify-between">
                <span><b>{r.rule_name}</b> — {r.action}</span>
                <span className="text-[10px]" style={{ color: 'var(--theme-text-muted)' }}>{relativeTime(r.fired_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
};


// ─── Activity tab ───────────────────────────────────────────────────────
const ACTIVITY_ICON = {
  email_sent:        { Icon: EnvelopeSimple, color: '#3B82F6', label: 'Email sent' },
  whatsapp_sent:     { Icon: ChatCircleText, color: '#16A34A', label: 'WhatsApp sent' },
  call_made:         { Icon: Phone,          color: '#F97316', label: 'Call made' },
  call_booked:       { Icon: Calendar,       color: '#7C35DC', label: 'Call booked' },
  status_changed:    { Icon: Tag,            color: '#F59E0B', label: 'Stage changed' },
  note_added:        { Icon: Note,           color: '#94A3B8', label: 'Note added' },
  scan_completed:    { Icon: Brain,          color: '#7C35DC', label: 'Intel scan' },
  lead_captured:     { Icon: Plus,           color: '#7C35DC', label: 'Lead captured' },
  icp_matched:       { Icon: Sparkle,        color: '#7C35DC', label: 'ICP matched' },
  reply_received:    { Icon: ChatCircleText, color: '#16A34A', label: 'Reply received' },
};

const ActivityTab = ({ activities }) => {
  const [filter, setFilter] = useState('all');
  const filtered = activities.filter((a) => {
    if (filter === 'all') return true;
    if (filter === 'aria') return (a.user_id || '').toLowerCase().includes('aria');
    if (filter === 'owner') return a.user_id && !['aria', 'system', 'web_form', 'api'].includes(a.user_id);
    if (filter === 'lead') return a.activity_type === 'reply_received';
    if (filter === 'system') return ['web_form', 'api', 'system'].includes(a.user_id);
    return true;
  });

  return (
    <div className="space-y-3" data-testid="lead360-tab-activity-content">
      <div className="flex flex-wrap gap-1.5">
        {['all', 'aria', 'owner', 'lead', 'system'].map((k) => (
          <button
            key={k}
            onClick={() => setFilter(k)}
            data-testid={`lead360-activity-filter-${k}`}
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-semibold border"
            style={{
              background: filter === k ? 'var(--theme-purple-dim)' : 'var(--theme-surface)',
              borderColor: filter === k ? 'var(--theme-purple)' : 'var(--theme-border-strong)',
              color: filter === k ? 'var(--theme-purple-light)' : 'var(--theme-text-muted)',
            }}
          >
            {k.charAt(0).toUpperCase() + k.slice(1)}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <EmptyHint text="No activity yet for this lead." />
      ) : (
        <ol className="space-y-2" data-testid="lead360-activity-list">
          {filtered.map((a, i) => {
            const meta = ACTIVITY_ICON[a.activity_type] || { Icon: ActivityIcon, color: '#94A3B8', label: a.activity_type };
            const Icon = meta.Icon;
            return (
              <li
                key={a.id || i}
                className="flex gap-3 items-start rounded-lg border px-3 py-2"
                style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }}
                data-testid={`lead360-activity-${a.activity_type}`}
              >
                <span className="shrink-0 w-7 h-7 rounded-md flex items-center justify-center" style={{ background: meta.color + '15' }}>
                  <Icon size={13} weight="duotone" style={{ color: meta.color }} />
                </span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold" style={{ color: 'var(--theme-text)' }}>
                    {a.subject || meta.label}
                  </div>
                  {a.body && <div className="text-xs mt-0.5 line-clamp-2" style={{ color: 'var(--theme-text-muted)' }}>{a.body}</div>}
                  <div className="text-[10px] mt-1 uppercase tracking-wider font-bold" style={{ color: 'var(--theme-text-muted)' }}>
                    {a.user_id || 'system'} · {relativeTime(a.created_at)}
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
};


// ─── Tiny atoms ─────────────────────────────────────────────────────────
const Card = ({ title, children }) => (
  <section
    className="rounded-xl border p-4"
    style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }}
    data-testid={`lead360-card-${(title || '').toLowerCase().replace(/[^a-z0-9]+/g, '-')}`}
  >
    <h3 className="text-[10px] font-extrabold uppercase tracking-[0.18em] mb-2" style={{ color: 'var(--theme-text-muted)', fontFamily: 'Plus Jakarta Sans' }}>{title}</h3>
    {children}
  </section>
);

const Field = ({ label, value, onCopy }) => (
  <div>
    <div className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--theme-text-muted)' }}>{label}</div>
    <div className="text-sm font-medium flex items-center gap-1.5 min-h-[20px]" style={{ color: 'var(--theme-text)' }}>
      <span className="truncate">{value || <span style={{ color: 'var(--theme-text-muted)' }}>—</span>}</span>
      {value && onCopy && (
        <button onClick={onCopy} className="opacity-50 hover:opacity-100 transition-opacity" aria-label={`Copy ${label}`}>
          <Copy size={11} />
        </button>
      )}
    </div>
  </div>
);

const EmptyHint = ({ text }) => (
  <div className="text-xs italic" style={{ color: 'var(--theme-text-muted)' }}>{text}</div>
);


export default Lead360;
