import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import Papa from 'papaparse';
import { toast } from 'sonner';
import api from '../config/api';
import { MagnifyingGlass, Plus, Funnel, X, Fire, Sparkle, UploadSimple, FileCsv, CheckCircle, Warning, DownloadSimple, PaperPlaneTilt } from '@phosphor-icons/react';
import PushToSequenceModal from '../components/PushToSequenceModal';
import AriaConfidenceDial from '../components/AriaConfidenceDial';
import AriaSpotlight from '../components/AriaSpotlight';

const NEXT_BEST_ACTION = (lead) => {
  const s = lead.status;
  const icp = lead.icp_score || 0;
  if (s === 'new' && icp >= 80) return { label: 'Call within 30 min', tone: 'urgent' };
  if (s === 'new') return { label: 'Send first-touch message', tone: 'default' };
  if (s === 'contacted' && icp >= 70) return { label: 'Qualify and book demo', tone: 'default' };
  if (s === 'contacted') return { label: 'Send pricing context', tone: 'default' };
  if (s === 'qualified') return { label: 'Book discovery call', tone: 'default' };
  if (s === 'call_booked') return { label: 'Send pre-call brief', tone: 'default' };
  if (s === 'proposal_sent') return { label: 'Follow up with case study', tone: 'urgent' };
  if (s === 'negotiation') return { label: 'Handle pricing objection', tone: 'urgent' };
  if (s === 'unqualified') return { label: 'Move to nurture sequence', tone: 'soft' };
  return { label: '—', tone: 'soft' };
};

const CHANNELS = ['whatsapp','email','linkedin','instagram','facebook','website_form','cold_call','referral','webinar','organic_search','paid_ads','other'];
const STATUSES = ['new','contacted','qualified','unqualified','proposal_sent','negotiation','won','lost','nurture'];
const TIERS = ['hot','warm','cold'];

// Founder-friendly status pivots — each one maps to either a backend status filter
// or a derived bucket. `key='all'` clears the filter. Order matters — leftmost = highest urgency.
const LEAD_TABS = [
  { key: 'all',           label: 'All Leads',          status: '',              tier: '' },
  { key: 'new',           label: 'New Leads',          status: 'new',           tier: '' },
  { key: 'high_intent',   label: 'High Intent',        status: '',              tier: 'hot' },
  { key: 'warm',          label: 'Warm Leads',         status: '',              tier: 'warm' },
  { key: 'contacted',     label: 'In Conversation',    status: 'contacted',     tier: '' },
  { key: 'qualified',     label: 'Qualified',          status: 'qualified',     tier: '' },
  { key: 'proposal_sent', label: 'Proposal Sent',      status: 'proposal_sent', tier: '' },
  { key: 'negotiation',   label: 'Negotiating',        status: 'negotiation',   tier: '' },
  { key: 'won',           label: 'Won',                status: 'won',           tier: '' },
  { key: 'nurture',       label: 'Cold / Nurture',     status: 'nurture',       tier: '' },
  { key: 'lost',          label: 'Lost',               status: 'lost',          tier: '' },
];

const LeadInbox = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [leads, setLeads] = useState([]);
  const [confidenceMap, setConfidenceMap] = useState({});
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState({ lead_type:'', status:'', source_channel:'', icp_tier:'' });
  const [showFilters, setShowFilters] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showPushModal, setShowPushModal] = useState(false);
  const [page, setPage] = useState(0);
  const [engagementMap, setEngagementMap] = useState({});
  const [activeTab, setActiveTab] = useState(searchParams.get('tab') || 'all');
  const [tabCounts, setTabCounts] = useState({});
  const limit = 20;

  // Apply tab → filter shortcuts (preserves any orthogonal filters the user set manually).
  const applyTab = (tab) => {
    setActiveTab(tab.key);
    setFilters((f) => ({ ...f, status: tab.status, icp_tier: tab.tier }));
    setPage(0);
    // Persist into URL so the filter is shareable + browser-back works.
    setSearchParams((sp) => {
      const next = new URLSearchParams(sp);
      if (tab.key === 'all') next.delete('tab'); else next.set('tab', tab.key);
      return next;
    }, { replace: true });
  };

  // On mount: if a tab was deep-linked, apply it once so filters hydrate.
  useEffect(() => {
    const t = searchParams.get('tab');
    if (!t || t === activeTab) return;
    const found = LEAD_TABS.find((x) => x.key === t);
    if (found) {
      setActiveTab(found.key);
      setFilters((f) => ({ ...f, status: found.status, icp_tier: found.tier }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Tab badge counts come from /api/analytics/dashboard (already tenant-scoped).
  useEffect(() => {
    api.get('/api/analytics/dashboard')
      .then((r) => {
        const sd = r.data?.status_distribution || {};
        const td = r.data?.icp_distribution || {};
        setTabCounts({
          all: r.data?.total_leads ?? 0,
          new: sd.new ?? 0,
          high_intent: td.hot ?? 0,
          warm: td.warm ?? 0,
          contacted: sd.contacted ?? 0,
          qualified: sd.qualified ?? 0,
          proposal_sent: sd.proposal_sent ?? 0,
          negotiation: sd.negotiation ?? 0,
          won: sd.won ?? 0,
          nurture: sd.nurture ?? 0,
          lost: sd.lost ?? 0,
        });
      })
      .catch(() => setTabCounts({}));
  }, []);

  const fetchLeads = useCallback(async () => {
    setLoading(true);
    try {
      const params = { skip: page*limit, limit, search: search||undefined };
      Object.entries(filters).forEach(([k,v]) => { if(v) params[k]=v; });
      const res = await api.get('/api/leads', { params });
      setLeads(res.data.leads); setTotal(res.data.total);
    } catch(err) { console.error(err); }
    finally { setLoading(false); }
  }, [page, search, filters]);

  useEffect(() => { fetchLeads(); }, [fetchLeads]);

  // Batch-fetch Aria confidence scores whenever the leads list changes.
  useEffect(() => {
    if (!leads.length) { setConfidenceMap({}); return; }
    const ids = leads.map((l) => l.id).filter(Boolean);
    api.post('/api/aria/confidence/batch', { lead_ids: ids })
      .then((r) => setConfidenceMap(r.data?.scores || {}))
      .catch(() => setConfidenceMap({}));
  }, [leads]);

  useEffect(() => {
    api.get('/api/lead-magnets/engagement-map')
      .then(res => setEngagementMap(res.data?.leads || {}))
      .catch(() => {});
  }, []);

  const tierBadge = (tier) => {
    const s = { hot:'bg-[#F4E6FD] text-[#7C35DC] border-[#C044E0]', warm:'bg-[#FEF3C7] text-[#D97706] border-[#D97706]/30', cold:'bg-[#F1F5F9] text-[#64748B] border-[#94A3B8]/30' };
    return `px-2 py-0.5 text-xs font-semibold uppercase tracking-wider rounded border ${s[tier]||s.cold}`;
  };
  const statusBadge = (status) => {
    const s = { new:'bg-[#F4F0FF] text-[#7C35DC] border-[#7C35DC]/20', contacted:'bg-[#F4F0FF] text-[#A855F7] border-[#A855F7]/20', qualified:'bg-[#DCFCE7] text-[#16A34A] border-[#16A34A]/20', won:'bg-[#DCFCE7] text-[#16A34A] border-[#16A34A]/20', lost:'bg-[#FEE2E2] text-[#DC2626] border-[#DC2626]/20', proposal_sent:'bg-[#FEF3C7] text-[#D97706] border-[#D97706]/20', negotiation:'bg-[#FEF3C7] text-[#D97706] border-[#D97706]/20', nurture:'bg-[#F4F0FF] text-[#A855F7] border-[#A855F7]/20', unqualified:'bg-[#F1F5F9] text-[#64748B] border-[#94A3B8]/30' };
    return `px-2 py-0.5 text-xs font-semibold uppercase tracking-wider rounded border ${s[status]||s.new}`;
  };

  const inputCls = "bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-2 rounded-lg text-sm focus:border-[#7C35DC] focus:ring-2 focus:ring-[rgba(124,53,220,0.12)] transition-all";

  return (
    <div data-testid="lead-inbox-page" className="space-y-6">
      <AriaSpotlight
        id="lead-inbox-tabs-v1"
        anchorSelector='[data-testid="lead-status-tabs"]'
        placement="bottom"
        title="Filter by stage"
        body="Tap any pivot to focus on a single bucket — Hot, New, In Conversation, etc. The URL updates so you can bookmark or share it."
      />
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-extrabold text-[#1A0A2E] tracking-tight" style={{ fontFamily:'Plus Jakarta Sans' }}>Lead Inbox</h1>
          <p className="text-sm text-[#5A4A7A] mt-1">Every prospect Aria is handling, sorted by intent and next action.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowPushModal(true)} disabled={!leads.length} data-testid="push-to-sequence-btn"
            className="flex items-center gap-2 bg-white border border-[#E8E0F5] hover:border-[#7C35DC]/40 text-[#5A4A7A] hover:text-[#7C35DC] px-4 py-2 rounded-lg text-sm font-semibold transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            style={{ fontFamily:'Plus Jakarta Sans' }}>
            <PaperPlaneTilt size={16} weight="fill" /> Send to sequence
          </button>
          <button onClick={() => setShowAddModal(true)} data-testid="add-lead-btn" className="flex items-center gap-2 btn-gradient px-4 py-2 rounded-lg text-sm font-semibold" style={{ fontFamily:'Plus Jakarta Sans' }}>
            <Plus size={16} weight="bold" /> Add Lead
          </button>
        </div>
      </div>

      {/* Status pivots — founder-friendly tabs that map to backend status/tier filters */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-hide" data-testid="lead-status-tabs">
        {LEAD_TABS.map((tab) => {
          const isActive = activeTab === tab.key;
          const count = tabCounts[tab.key];
          return (
            <button
              key={tab.key}
              onClick={() => applyTab(tab)}
              data-testid={`lead-tab-${tab.key}`}
              className={`flex-shrink-0 inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-bold transition-all border ${
                isActive
                  ? 'text-white border-transparent shadow-[0_4px_12px_rgba(124,53,220,0.25)]'
                  : 'bg-white text-[#5A4A7A] border-[#E8E0F5] hover:border-[#7C35DC]/30 hover:text-[#7C35DC]'
              }`}
              style={isActive ? { background: 'var(--gradient-brand)', fontFamily: 'Plus Jakarta Sans' } : { fontFamily: 'Plus Jakarta Sans' }}
            >
              {tab.label}
              {typeof count === 'number' && (
                <span className={`text-[10px] font-extrabold px-1.5 py-0.5 rounded-full ${
                  isActive ? 'bg-white/25 text-white' : 'bg-[#F4F0FF] text-[#7C35DC]'
                }`}>{count}</span>
              )}
            </button>
          );
        })}
      </div>

      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-lg">
          <MagnifyingGlass size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9B8AB0]" />
          <input type="text" value={search} onChange={(e) => { setSearch(e.target.value); setPage(0); }} placeholder="Search by name, email, company..." data-testid="lead-search-input" className={`w-full pl-10 pr-4 ${inputCls}`} />
        </div>
        <button onClick={() => setShowFilters(!showFilters)} data-testid="toggle-filters-btn"
          className={`flex items-center gap-2 px-4 py-2 border rounded-lg transition-all text-sm font-medium ${showFilters ? 'bg-[#F4F0FF] border-[#7C35DC]/30 text-[#7C35DC]' : 'bg-white border-[#E8E0F5] text-[#5A4A7A] hover:bg-[#F9F5FF] hover:text-[#7C35DC]'}`} style={{ fontFamily:'Plus Jakarta Sans' }}>
          <Funnel size={16} /> More filters
        </button>
      </div>

      {showFilters && (
        <div className="bg-white border border-[#E8E0F5] rounded-xl p-4 flex flex-wrap gap-4" style={{ boxShadow:'var(--shadow-card)' }} data-testid="filter-bar">
          <select value={filters.lead_type} onChange={(e) => { setFilters({...filters, lead_type:e.target.value}); setPage(0); }} className={inputCls} data-testid="filter-lead-type">
            <option value="">All Types</option><option value="B2B">B2B</option><option value="B2C">B2C</option>
          </select>
          <select value={filters.status} onChange={(e) => { setFilters({...filters, status:e.target.value}); setPage(0); }} className={inputCls} data-testid="filter-status">
            <option value="">All Statuses</option>{STATUSES.map(s => <option key={s} value={s}>{s.replace('_',' ')}</option>)}
          </select>
          <select value={filters.source_channel} onChange={(e) => { setFilters({...filters, source_channel:e.target.value}); setPage(0); }} className={inputCls} data-testid="filter-channel">
            <option value="">All Channels</option>{CHANNELS.map(c => <option key={c} value={c}>{c.replace('_',' ')}</option>)}
          </select>
          <select value={filters.icp_tier} onChange={(e) => { setFilters({...filters, icp_tier:e.target.value}); setPage(0); }} className={inputCls} data-testid="filter-tier">
            <option value="">All Tiers</option>{TIERS.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          <button onClick={() => { setFilters({ lead_type:'', status:'', source_channel:'', icp_tier:'' }); setPage(0); }} className="text-sm text-[#DC2626] hover:text-[#DC2626]/80 font-medium" data-testid="clear-filters-btn">Clear All</button>
        </div>
      )}

      <div className="bg-white border border-[#E8E0F5] rounded-xl overflow-hidden" style={{ boxShadow:'var(--shadow-card)' }} data-testid="leads-table">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead>
              <tr className="bg-[#F4F0FF]">
                {['Name','Company','Type','Status','ICP','Score','Aria','Channel','Next Best Action','Created'].map(h => (
                  <th key={h} data-testid={`th-${h.toLowerCase().replace(/\s+/g,'-')}`} className="px-6 py-3 text-xs font-semibold uppercase tracking-[0.15em] text-[#5A4A7A]" style={{ fontFamily:'Plus Jakarta Sans' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={10} className="px-6 py-12 text-center text-[#9B8AB0]">Loading...</td></tr>
              ) : leads.length === 0 ? (
                <tr><td colSpan={10} className="px-6 py-12 text-center text-[#9B8AB0]">No leads found</td></tr>
              ) : leads.map(lead => {
                const eng = engagementMap[lead.id];
                const isHot = eng?.is_hot;
                return (
                <tr key={lead.id} className={`border-b border-[#F0ECF9] hover:bg-[#F9F5FF] cursor-pointer transition-colors relative ${isHot ? 'bg-gradient-to-r from-[#FEE2E2]/30 to-transparent' : ''}`} onClick={() => navigate(`/leads/${lead.id}`)} data-testid={`lead-row-${lead.id}`}>
                  {isHot && <td className="absolute left-0 top-0 bottom-0 w-1" style={{ background: 'linear-gradient(180deg, #DC2626 0%, #C044E0 100%)' }} aria-hidden="true"></td>}
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <div>
                        <div className="font-semibold text-[#1A0A2E]">{lead.first_name} {lead.last_name}</div>
                        <div className="text-xs text-[#9B8AB0] font-mono">{lead.email}</div>
                      </div>
                      {isHot && (
                        <span className="flex items-center gap-1 text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-[#FEE2E2] text-[#DC2626] border border-[#DC2626]/20" data-testid={`row-hot-${lead.id}`} title={`Opened brochure ${eng.view_count}× — last ${eng.last_viewed ? new Date(eng.last_viewed).toLocaleString() : 'recently'}`}>
                          <Fire size={10} weight="fill" /> {eng.view_count}× hot
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 text-[#5A4A7A]">{lead.company_name || '—'}</td>
                  <td className="px-6 py-4"><span className={`px-2 py-0.5 text-xs font-semibold rounded border ${lead.lead_type === 'B2B' ? 'bg-[#F4F0FF] text-[#7C35DC] border-[#7C35DC]/20' : 'bg-[#DCFCE7] text-[#16A34A] border-[#16A34A]/20'}`}>{lead.lead_type}</span></td>
                  <td className="px-6 py-4"><span className={statusBadge(lead.status)}>{lead.status.replace('_',' ')}</span></td>
                  <td className="px-6 py-4"><span className={tierBadge(lead.icp_tier)}>{lead.icp_tier}</span></td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <div className="w-12 h-1.5 bg-[#F0ECF9] rounded-full overflow-hidden">
                        <div className="h-full rounded-full" style={{ width:`${lead.icp_score}%`, background: lead.icp_score >= 70 ? 'var(--gradient-brand-horizontal)' : lead.icp_score >= 40 ? '#D97706' : '#94A3B8' }}></div>
                      </div>
                      <span className="text-xs font-mono text-[#5A4A7A]">{lead.icp_score}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4" data-testid={`aria-cell-${lead.id}`}>
                    {(() => {
                      const c = confidenceMap[lead.id];
                      return (
                        <AriaConfidenceDial
                          score={c?.score ?? lead.icp_score ?? 0}
                          color={c?.color || (lead.icp_score >= 70 ? 'green' : lead.icp_score >= 50 ? 'yellow' : 'red')}
                          size="sm"
                          factors={c?.factors || []}
                        />
                      );
                    })()}
                  </td>
                  <td className="px-6 py-4 text-[#5A4A7A] text-xs">{lead.source_channel?.replace('_',' ')}</td>
                  <td className="px-6 py-4">
                    {(() => {
                      const nba = NEXT_BEST_ACTION(lead);
                      const cls = nba.tone === 'urgent' ? 'text-[#DC2626] bg-[#FEE2E2] border-[#DC2626]/20' : nba.tone === 'soft' ? 'text-[#9B8AB0] bg-[#F4F0FF] border-[#E0D4F7]' : 'text-[#7C35DC] bg-[#F4F0FF] border-[#7C35DC]/20';
                      return <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${cls}`} data-testid={`nba-${lead.id}`}><Sparkle size={9} weight="fill" /> {nba.label}</span>;
                    })()}
                  </td>
                  <td className="px-6 py-4 text-[#9B8AB0] text-xs font-mono">{new Date(lead.created_at).toLocaleDateString()}</td>
                </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="px-6 py-4 border-t border-[#E8E0F5] flex items-center justify-between">
          <span className="text-sm text-[#9B8AB0]">Showing {page*limit+1}–{Math.min((page+1)*limit, total)} of {total}</span>
          <div className="flex items-center gap-2">
            <button onClick={() => setPage(Math.max(0,page-1))} disabled={page===0} data-testid="prev-page-btn" className="px-3 py-1 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-lg hover:bg-[#F9F5FF] transition-all text-sm disabled:opacity-30">Previous</button>
            <button onClick={() => setPage(page+1)} disabled={(page+1)*limit>=total} data-testid="next-page-btn" className="px-3 py-1 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-lg hover:bg-[#F9F5FF] transition-all text-sm disabled:opacity-30">Next</button>
          </div>
        </div>
      </div>

      {showAddModal && <AddLeadModal onClose={() => setShowAddModal(false)} onSuccess={() => { setShowAddModal(false); fetchLeads(); }} />}
      {showPushModal && <PushToSequenceModal leadIds={leads.map(l => l.id)} onClose={() => setShowPushModal(false)} onSuccess={() => { setShowPushModal(false); fetchLeads(); }} />}
    </div>
  );
};

const AddLeadModal = ({ onClose, onSuccess }) => {
  const [mode, setMode] = useState('manual'); // 'manual' | 'csv'
  return (
    <div className="fixed inset-0 bg-black/20 backdrop-blur-sm flex items-center justify-center z-50 p-4" data-testid="add-lead-modal">
      <div className="bg-white border border-[#E8E0F5] rounded-2xl w-full max-w-3xl max-h-[90vh] overflow-y-auto" style={{ boxShadow:'var(--shadow-hover)' }}>
        <div className="flex items-center justify-between p-6 border-b border-[#E8E0F5]">
          <div>
            <h2 className="text-xl font-bold text-[#1A0A2E]" style={{ fontFamily:'Plus Jakarta Sans' }}>Add Leads</h2>
            <p className="text-xs text-[#9B8AB0] mt-0.5">Add one lead manually or upload a CSV with hundreds.</p>
          </div>
          <button onClick={onClose} className="text-[#9B8AB0] hover:text-[#7C35DC] transition-colors" data-testid="close-modal-btn"><X size={24} /></button>
        </div>

        <div className="px-6 pt-4">
          <div className="inline-flex p-1 bg-[#F4F0FF] rounded-xl border border-[#E8E0F5]" data-testid="add-lead-mode-tabs">
            <button onClick={() => setMode('manual')} data-testid="mode-tab-manual"
              className={`flex items-center gap-2 px-4 py-1.5 rounded-lg text-sm font-semibold transition-all ${mode === 'manual' ? 'bg-white text-[#7C35DC] shadow-sm' : 'text-[#5A4A7A] hover:text-[#7C35DC]'}`}>
              <Plus size={14} weight="bold" /> Single lead
            </button>
            <button onClick={() => setMode('csv')} data-testid="mode-tab-csv"
              className={`flex items-center gap-2 px-4 py-1.5 rounded-lg text-sm font-semibold transition-all ${mode === 'csv' ? 'bg-white text-[#7C35DC] shadow-sm' : 'text-[#5A4A7A] hover:text-[#7C35DC]'}`}>
              <FileCsv size={14} weight="fill" /> CSV upload
            </button>
          </div>
        </div>

        {mode === 'manual'
          ? <ManualLeadForm onClose={onClose} onSuccess={onSuccess} />
          : <CSVUploadForm onClose={onClose} onSuccess={onSuccess} />}
      </div>
    </div>
  );
};

const ManualLeadForm = ({ onClose, onSuccess }) => {
  const [formData, setFormData] = useState({ lead_type:'B2B', first_name:'', last_name:'', email:'', phone:'', company_name:'', job_title:'', industry:'', source_channel:'website_form', notes:'' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault(); setLoading(true); setError('');
    try { await api.post('/api/leads', formData); toast.success('Lead created'); onSuccess(); }
    catch(err) { setError(err.response?.data?.detail || 'Failed to create lead'); }
    finally { setLoading(false); }
  };

  const inputCls = "w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-2.5 rounded-lg text-sm focus:border-[#7C35DC] focus:ring-2 focus:ring-[rgba(124,53,220,0.12)] transition-all";

  return (
    <form onSubmit={handleSubmit} className="p-6 space-y-4" data-testid="manual-lead-form">
      {error && <div className="bg-red-50 border border-red-200 text-[#DC2626] rounded-lg p-3 text-sm">{error}</div>}
      <div className="grid grid-cols-2 gap-4">
        <div><label className="block text-sm font-medium text-[#1A0A2E] mb-1.5" style={{ fontFamily:'Plus Jakarta Sans' }}>Lead Type</label><select value={formData.lead_type} onChange={(e) => setFormData({...formData, lead_type:e.target.value})} className={inputCls} data-testid="form-lead-type"><option value="B2B">B2B</option><option value="B2C">B2C</option></select></div>
        <div><label className="block text-sm font-medium text-[#1A0A2E] mb-1.5" style={{ fontFamily:'Plus Jakarta Sans' }}>Source Channel</label><select value={formData.source_channel} onChange={(e) => setFormData({...formData, source_channel:e.target.value})} className={inputCls} data-testid="form-channel">{CHANNELS.map(c => <option key={c} value={c}>{c.replace('_',' ')}</option>)}</select></div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div><label className="block text-sm font-medium text-[#1A0A2E] mb-1.5" style={{ fontFamily:'Plus Jakarta Sans' }}>First Name *</label><input type="text" value={formData.first_name} onChange={(e) => setFormData({...formData, first_name:e.target.value})} required className={inputCls} data-testid="form-first-name" /></div>
        <div><label className="block text-sm font-medium text-[#1A0A2E] mb-1.5" style={{ fontFamily:'Plus Jakarta Sans' }}>Last Name *</label><input type="text" value={formData.last_name} onChange={(e) => setFormData({...formData, last_name:e.target.value})} required className={inputCls} data-testid="form-last-name" /></div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div><label className="block text-sm font-medium text-[#1A0A2E] mb-1.5" style={{ fontFamily:'Plus Jakarta Sans' }}>Email *</label><input type="email" value={formData.email} onChange={(e) => setFormData({...formData, email:e.target.value})} required className={inputCls} data-testid="form-email" /></div>
        <div><label className="block text-sm font-medium text-[#1A0A2E] mb-1.5" style={{ fontFamily:'Plus Jakarta Sans' }}>Phone</label><input type="text" value={formData.phone} onChange={(e) => setFormData({...formData, phone:e.target.value})} className={inputCls} data-testid="form-phone" /></div>
      </div>
      {formData.lead_type === 'B2B' && (
        <div className="grid grid-cols-2 gap-4">
          <div><label className="block text-sm font-medium text-[#1A0A2E] mb-1.5" style={{ fontFamily:'Plus Jakarta Sans' }}>Company</label><input type="text" value={formData.company_name} onChange={(e) => setFormData({...formData, company_name:e.target.value})} className={inputCls} data-testid="form-company" /></div>
          <div><label className="block text-sm font-medium text-[#1A0A2E] mb-1.5" style={{ fontFamily:'Plus Jakarta Sans' }}>Job Title</label><input type="text" value={formData.job_title} onChange={(e) => setFormData({...formData, job_title:e.target.value})} className={inputCls} data-testid="form-job-title" /></div>
        </div>
      )}
      <div><label className="block text-sm font-medium text-[#1A0A2E] mb-1.5" style={{ fontFamily:'Plus Jakarta Sans' }}>Notes</label><textarea value={formData.notes} onChange={(e) => setFormData({...formData, notes:e.target.value})} rows={3} className={`${inputCls} resize-none`} data-testid="form-notes" /></div>
      <div className="flex justify-end gap-3 pt-4">
        <button type="button" onClick={onClose} className="px-4 py-2 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-lg hover:bg-[#F9F5FF] text-sm font-medium" data-testid="cancel-add-lead-btn">Cancel</button>
        <button type="submit" disabled={loading} className="px-6 py-2 btn-gradient rounded-lg text-sm font-semibold disabled:opacity-50" style={{ fontFamily:'Plus Jakarta Sans' }} data-testid="submit-lead-btn">{loading ? 'Creating...' : 'Create Lead'}</button>
      </div>
    </form>
  );
};

// === CSV upload mode ===
const REQUIRED_HEADERS = ['first_name', 'last_name', 'email'];
const OPTIONAL_HEADERS = ['lead_type', 'phone', 'company_name', 'job_title', 'industry', 'source_channel', 'notes', 'tags'];
const ALL_HEADERS = [...REQUIRED_HEADERS, ...OPTIONAL_HEADERS];

// Common header synonyms across HubSpot, Pipedrive, Salesforce, spreadsheets
const HEADER_SYNONYMS = {
  first_name: ['first_name', 'firstname', 'first', 'fname', 'given_name', 'givenname'],
  last_name: ['last_name', 'lastname', 'last', 'lname', 'surname', 'family_name', 'familyname'],
  email: ['email', 'email_address', 'emailaddress', 'e_mail', 'mail', 'work_email', 'workemail', 'business_email'],
  phone: ['phone', 'phone_number', 'phonenumber', 'mobile', 'mobile_number', 'cell', 'cell_phone', 'contact_number', 'work_phone', 'whatsapp'],
  company_name: ['company', 'company_name', 'companyname', 'organization', 'organisation', 'org', 'account', 'account_name', 'business', 'employer'],
  job_title: ['job_title', 'jobtitle', 'title', 'role', 'position', 'designation'],
  industry: ['industry', 'sector', 'vertical', 'category'],
  source_channel: ['source_channel', 'source', 'channel', 'lead_source', 'leadsource', 'origin', 'utm_source'],
  lead_type: ['lead_type', 'leadtype', 'type', 'segment', 'b2b_or_b2c'],
  notes: ['notes', 'note', 'comments', 'comment', 'description', 'remark', 'remarks', 'message'],
  tags: ['tags', 'tag', 'labels', 'label', 'categories'],
};

// Build a flat lookup: normalized synonym → ARIA field
const SYNONYM_LOOKUP = (() => {
  const m = {};
  for (const [aria, syns] of Object.entries(HEADER_SYNONYMS)) {
    for (const s of syns) m[s.replace(/[^a-z0-9]/g, '')] = aria;
  }
  return m;
})();

const FIELD_LABELS = {
  first_name: 'First name *', last_name: 'Last name *', email: 'Email *',
  lead_type: 'Lead type', phone: 'Phone', company_name: 'Company',
  job_title: 'Job title', industry: 'Industry', source_channel: 'Source channel',
  notes: 'Notes', tags: 'Tags',
};

const CSVUploadForm = ({ onClose, onSuccess }) => {
  const fileRef = useRef(null);
  const [step, setStep] = useState('upload'); // 'upload' | 'map' | 'preview' | 'result'
  const [fileName, setFileName] = useState('');
  const [rawRows, setRawRows] = useState([]);     // rows keyed by CSV header (raw)
  const [csvHeaders, setCsvHeaders] = useState([]); // CSV column names as-uploaded
  const [mapping, setMapping] = useState({});     // { csvHeader: ariaField | '__skip__' }
  const [parseError, setParseError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [dragOver, setDragOver] = useState(false);

  // Auto-suggest mapping based on synonym lookup
  const autoSuggest = (cols) => {
    const m = {};
    const used = new Set();
    for (const c of cols) {
      const key = String(c).toLowerCase().replace(/[^a-z0-9]/g, '');
      const guess = SYNONYM_LOOKUP[key];
      if (guess && !used.has(guess)) {
        m[c] = guess;
        used.add(guess);
      } else {
        m[c] = '__skip__';
      }
    }
    return m;
  };

  const onFile = (file) => {
    if (!file) return;
    setParseError(''); setResult(null); setMapping({});
    setFileName(file.name);
    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      // Keep raw header so user sees their actual column names
      transformHeader: (h) => String(h || '').trim(),
      complete: (res) => {
        const fatal = (res.errors || []).filter(e => e.code !== 'TooFewFields' && e.code !== 'TooManyFields');
        if (fatal.length) {
          setParseError(fatal.slice(0, 3).map(e => `Row ${e.row}: ${e.message}`).join(' · '));
          return;
        }
        const detected = (res.meta?.fields || []).filter(Boolean);
        if (!detected.length) { setParseError('No columns detected. Make sure your CSV has a header row.'); return; }
        const data = res.data.slice(0, 5000);
        if (!data.length) { setParseError('CSV has headers but no data rows.'); return; }
        setCsvHeaders(detected);
        setRawRows(data);
        setMapping(autoSuggest(detected));
        setStep('map');
      },
      error: (err) => setParseError(err.message || 'Failed to parse CSV'),
    });
  };

  // Build "mapped rows" (ARIA-field keyed) using current mapping
  const mappedRows = (() => {
    if (!rawRows.length) return [];
    return rawRows.map(raw => {
      const out = {};
      for (const [csvCol, ariaField] of Object.entries(mapping)) {
        if (ariaField && ariaField !== '__skip__') out[ariaField] = raw[csvCol];
      }
      return out;
    });
  })();

  const validateRow = (r) => {
    if (!r.first_name || !String(r.first_name).trim()) return 'first_name missing';
    if (!r.last_name || !String(r.last_name).trim()) return 'last_name missing';
    const email = String(r.email || '').trim();
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return 'invalid email';
    return null;
  };

  const stats = (() => {
    let valid = 0, invalid = 0;
    for (const r of mappedRows) { if (validateRow(r)) invalid++; else valid++; }
    return { valid, invalid, total: mappedRows.length };
  })();

  // Mapping completeness — required fields must be mapped to a CSV column
  const mappingStatus = (() => {
    const mappedTo = new Set(Object.values(mapping).filter(v => v && v !== '__skip__'));
    const missing = REQUIRED_HEADERS.filter(h => !mappedTo.has(h));
    // Detect duplicate ARIA field assignments
    const counts = {};
    for (const v of Object.values(mapping)) {
      if (v && v !== '__skip__') counts[v] = (counts[v] || 0) + 1;
    }
    const duplicates = Object.entries(counts).filter(([_, n]) => n > 1).map(([f]) => f);
    return { missing, duplicates, ready: missing.length === 0 && duplicates.length === 0 };
  })();

  const handleSubmit = async () => {
    if (!mappedRows.length) return;
    setSubmitting(true); setResult(null);
    const payload = {
      leads: mappedRows
        .filter(r => !validateRow(r))
        .map(r => ({
          lead_type: ['B2B', 'B2C'].includes(String(r.lead_type || '').toUpperCase()) ? String(r.lead_type).toUpperCase() : 'B2B',
          first_name: String(r.first_name).trim(),
          last_name: String(r.last_name).trim(),
          email: String(r.email).trim(),
          phone: r.phone ? String(r.phone).trim() : null,
          company_name: r.company_name ? String(r.company_name).trim() : null,
          job_title: r.job_title ? String(r.job_title).trim() : null,
          industry: r.industry ? String(r.industry).trim() : null,
          source_channel: CHANNELS.includes(String(r.source_channel || '').toLowerCase()) ? String(r.source_channel).toLowerCase() : 'other',
          notes: r.notes ? String(r.notes).trim() : null,
          tags: r.tags ? String(r.tags).split(',').map(t => t.trim()).filter(Boolean) : [],
          status: 'new',
        })),
    };
    if (!payload.leads.length) {
      setResult({ created: 0, failed: stats.invalid, errors: [] });
      setStep('result'); setSubmitting(false); return;
    }
    try {
      const r = await api.post('/api/leads/bulk', payload);
      setResult(r.data); setStep('result');
      if (r.data.created > 0) toast.success(`${r.data.created} lead${r.data.created !== 1 ? 's' : ''} added`);
      if (r.data.failed === 0 && r.data.created > 0) {
        setTimeout(() => onSuccess(), 1500);
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Bulk upload failed');
    } finally {
      setSubmitting(false);
    }
  };

  const downloadTemplate = () => {
    const csv = ALL_HEADERS.join(',') + '\n'
      + 'B2B,Priya,Sharma,priya@example.com,+919999999999,GrowthNest,VP Growth,SaaS,linkedin,Asked about pricing twice,"hot,enterprise"\n'
      + 'B2B,Rohit,Verma,rohit@example.com,,SaaSWorks,Founder,SaaS,whatsapp,Demo booked,\n'
      + 'B2C,Ananya,Iyer,ananya@example.com,+919876543210,,,,website_form,Newsletter signup,';
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'aria-leads-template.csv';
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const reset = () => {
    setStep('upload'); setFileName(''); setRawRows([]); setCsvHeaders([]);
    setMapping({}); setParseError(''); setResult(null);
    if (fileRef.current) fileRef.current.value = '';
  };

  // Drag & drop handlers
  const onDragOver = (e) => { e.preventDefault(); setDragOver(true); };
  const onDragLeave = () => setDragOver(false);
  const onDrop = (e) => { e.preventDefault(); setDragOver(false); const f = e.dataTransfer.files?.[0]; if (f) onFile(f); };

  // ===== STEP: RESULT =====
  if (step === 'result' && result) {
    return (
      <div className="p-6 space-y-4" data-testid="csv-result-screen">
        <div className="flex items-start gap-3 bg-[#DCFCE7] border border-[#16A34A]/30 rounded-xl px-4 py-3">
          <CheckCircle size={20} weight="fill" className="text-[#16A34A] mt-0.5 flex-shrink-0" />
          <div>
            <div className="font-extrabold text-[#1A0A2E]" style={{ fontFamily:'Plus Jakarta Sans' }} data-testid="csv-created-count">{result.created} lead{result.created !== 1 ? 's' : ''} added to ARIA</div>
            <div className="text-xs text-[#5A4A7A]">ARIA will start working them in the next sync.</div>
          </div>
        </div>
        {result.failed > 0 && (
          <div className="bg-[#FEF3C7] border border-[#FDE68A] rounded-xl px-4 py-3" data-testid="csv-failed-block">
            <div className="flex items-center gap-2 mb-2">
              <Warning size={16} weight="fill" className="text-[#D97706]" />
              <span className="font-extrabold text-[#1A0A2E]">{result.failed} skipped</span>
            </div>
            <ul className="text-xs text-[#5A4A7A] space-y-1 max-h-44 overflow-y-auto">
              {(result.errors || []).map((e, i) => (
                <li key={i} className="flex gap-2"><span className="text-[#D97706] font-mono">row {e.row}</span><span className="truncate">{e.email || '—'}</span><span className="text-[#9B8AB0]">·</span><span>{e.error}</span></li>
              ))}
            </ul>
          </div>
        )}
        <div className="flex justify-end gap-3 pt-2">
          <button onClick={reset} className="px-4 py-2 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-lg hover:bg-[#F9F5FF] text-sm font-medium" data-testid="csv-upload-another-btn">Upload another</button>
          <button onClick={onSuccess} className="px-6 py-2 btn-gradient rounded-lg text-sm font-semibold" style={{ fontFamily:'Plus Jakarta Sans' }} data-testid="csv-done-btn">Done</button>
        </div>
      </div>
    );
  }

  // Step indicator
  const Steps = () => (
    <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.2em]" data-testid="csv-stepper">
      {['Upload', 'Map fields', 'Preview'].map((label, i) => {
        const active = (step === 'upload' && i === 0) || (step === 'map' && i === 1) || (step === 'preview' && i === 2);
        const done = (step === 'map' && i < 1) || (step === 'preview' && i < 2);
        return (
          <React.Fragment key={label}>
            {i > 0 && <span className="text-[#E0D4F7]">—</span>}
            <span className={`px-2 py-1 rounded-md ${active ? 'bg-[#7C35DC] text-white' : done ? 'text-[#16A34A]' : 'text-[#9B8AB0]'}`}>
              {done ? '✓ ' : `${i + 1}. `}{label}
            </span>
          </React.Fragment>
        );
      })}
    </div>
  );

  // ===== STEP: UPLOAD =====
  if (step === 'upload') {
    return (
      <div className="p-6 space-y-4" data-testid="csv-upload-form">
        <Steps />
        <div className="flex items-center justify-between flex-wrap gap-2 bg-[#F4F0FF] border border-[#E0D4F7] rounded-xl px-4 py-3">
          <div className="text-xs text-[#5A4A7A] leading-relaxed">
            Map any CSV — HubSpot, Pipedrive, Salesforce, Google Sheets. Required: <code className="bg-white px-1.5 py-0.5 rounded text-[#7C35DC] text-[11px] font-mono">first_name, last_name, email</code> (or any column you can map to them).
          </div>
          <button onClick={downloadTemplate} type="button" data-testid="csv-template-btn"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold text-[#7C35DC] bg-white border border-[#7C35DC]/30 hover:bg-[#F4F0FF]">
            <DownloadSimple size={14} weight="bold" /> Download template
          </button>
        </div>

        {!parseError && (
          <div onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={onDrop} data-testid="csv-dropzone"
            className={`border-2 border-dashed rounded-2xl p-10 text-center transition-all cursor-pointer ${dragOver ? 'border-[#7C35DC] bg-[#F4F0FF]' : 'border-[#E0D4F7] bg-[#FAF7FF] hover:bg-[#F4F0FF]'}`}
            onClick={() => fileRef.current?.click()}>
            <div className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-3" style={{ background:'var(--gradient-brand)', boxShadow:'var(--shadow-glow)' }}>
              <UploadSimple size={22} weight="bold" className="text-white" />
            </div>
            <div className="text-base font-extrabold text-[#1A0A2E]" style={{ fontFamily:'Plus Jakarta Sans' }}>Drop your CSV here</div>
            <div className="text-xs text-[#5A4A7A] mt-1">or click to browse · max 5,000 rows</div>
            <input ref={fileRef} type="file" accept=".csv,text/csv" className="hidden" data-testid="csv-file-input"
              onChange={(e) => onFile(e.target.files?.[0])} />
          </div>
        )}

        {parseError && (
          <div className="bg-[#FEE2E2] border border-[#DC2626]/30 text-[#DC2626] rounded-xl px-4 py-3 text-sm flex items-start gap-2" data-testid="csv-parse-error">
            <Warning size={16} weight="fill" className="flex-shrink-0 mt-0.5" />
            <div>
              <div className="font-bold">Couldn't read this CSV</div>
              <div className="text-xs mt-1">{parseError}</div>
              <button onClick={reset} className="text-xs font-bold underline mt-2">Try another file</button>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ===== STEP: MAP =====
  if (step === 'map') {
    const ariaOptions = ALL_HEADERS;
    const sampleRow = rawRows[0] || {};
    return (
      <div className="p-6 space-y-4" data-testid="csv-mapping-form">
        <Steps />
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2 text-sm">
            <FileCsv size={16} weight="fill" className="text-[#7C35DC]" />
            <span className="font-bold text-[#1A0A2E]">{fileName}</span>
            <span className="text-[#9B8AB0]">·</span>
            <span className="text-[#5A4A7A]">{rawRows.length} rows · {csvHeaders.length} columns</span>
          </div>
          <button onClick={reset} className="text-xs font-bold text-[#7C35DC] hover:underline" data-testid="mapping-change-file-btn">Choose different file</button>
        </div>

        <div className="bg-[#F4F0FF] border border-[#E0D4F7] rounded-xl px-4 py-3 text-xs text-[#5A4A7A]">
          <span className="font-bold text-[#1A0A2E]">Map your columns to ARIA fields.</span> ARIA auto-suggested matches for common synonyms — review and adjust below. Required fields: <code className="bg-white px-1.5 py-0.5 rounded text-[#7C35DC] font-mono">first_name</code>, <code className="bg-white px-1.5 py-0.5 rounded text-[#7C35DC] font-mono">last_name</code>, <code className="bg-white px-1.5 py-0.5 rounded text-[#7C35DC] font-mono">email</code>.
        </div>

        <div className="border border-[#E8E0F5] rounded-xl overflow-hidden" data-testid="mapping-table">
          <div className="grid grid-cols-12 gap-0 bg-[#F4F0FF] border-b border-[#E8E0F5] px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-[#5A4A7A]">
            <div className="col-span-4">Your CSV column</div>
            <div className="col-span-4">Sample value</div>
            <div className="col-span-4">→ ARIA field</div>
          </div>
          <div className="divide-y divide-[#F0ECF9] max-h-72 overflow-y-auto">
            {csvHeaders.map((col) => {
              const current = mapping[col] || '__skip__';
              const isReq = REQUIRED_HEADERS.includes(current);
              const sample = String(sampleRow[col] ?? '').slice(0, 50);
              // Available options: skip + ARIA fields not used by other columns (or current value)
              const usedByOthers = new Set(
                Object.entries(mapping).filter(([c, _]) => c !== col).map(([_, v]) => v).filter(v => v && v !== '__skip__')
              );
              return (
                <div key={col} className="grid grid-cols-12 gap-2 items-center px-3 py-2.5" data-testid={`mapping-row-${col}`}>
                  <div className="col-span-4 text-sm font-semibold text-[#1A0A2E] truncate" title={col}>{col}</div>
                  <div className="col-span-4 text-xs text-[#5A4A7A] truncate font-mono bg-[#FAF7FF] px-2 py-1 rounded" title={sample}>{sample || <span className="text-[#9B8AB0] italic">empty</span>}</div>
                  <div className="col-span-4 flex items-center gap-2">
                    <select value={current}
                      onChange={(e) => setMapping({ ...mapping, [col]: e.target.value })}
                      data-testid={`mapping-select-${col}`}
                      className={`w-full text-sm px-2.5 py-1.5 rounded-lg border focus:ring-2 focus:ring-[#7C35DC]/30 focus:outline-none ${isReq ? 'border-[#7C35DC]/40 bg-[#F4F0FF] text-[#7C35DC] font-bold' : 'border-[#E8E0F5] bg-white text-[#1A0A2E]'}`}>
                      <option value="__skip__">— Skip this column —</option>
                      {ariaOptions.map(f => (
                        <option key={f} value={f} disabled={usedByOthers.has(f)}>
                          {FIELD_LABELS[f]}{usedByOthers.has(f) ? ' (used)' : ''}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Required field status */}
        <div className="flex flex-wrap gap-2" data-testid="mapping-required-status">
          {REQUIRED_HEADERS.map(req => {
            const ok = Object.values(mapping).includes(req);
            return (
              <span key={req} className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-bold ${ok ? 'bg-[#DCFCE7] text-[#16A34A] border border-[#16A34A]/30' : 'bg-[#FEE2E2] text-[#DC2626] border border-[#DC2626]/30'}`}>
                {ok ? <CheckCircle size={12} weight="fill" /> : <Warning size={12} weight="fill" />}
                {FIELD_LABELS[req]}
              </span>
            );
          })}
        </div>
        {!mappingStatus.ready && mappingStatus.missing.length > 0 && (
          <div className="text-xs text-[#DC2626] font-semibold" data-testid="mapping-missing-msg">
            Map a column to: {mappingStatus.missing.map(f => FIELD_LABELS[f]).join(', ')}
          </div>
        )}

        <div className="flex items-center justify-between gap-3 pt-2">
          <button type="button" onClick={reset}
            className="px-4 py-2 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-lg hover:bg-[#F9F5FF] text-sm font-medium" data-testid="mapping-back-btn">
            Back
          </button>
          <button type="button" onClick={() => setStep('preview')}
            disabled={!mappingStatus.ready} data-testid="mapping-continue-btn"
            className="px-6 py-2 btn-gradient rounded-lg text-sm font-semibold disabled:opacity-50" style={{ fontFamily:'Plus Jakarta Sans' }}>
            Continue → Preview
          </button>
        </div>
      </div>
    );
  }

  // ===== STEP: PREVIEW =====
  return (
    <div className="p-6 space-y-4" data-testid="csv-preview">
      <Steps />
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2 text-sm">
          <FileCsv size={16} weight="fill" className="text-[#7C35DC]" />
          <span className="font-bold text-[#1A0A2E]">{fileName}</span>
          <span className="text-[#9B8AB0]">·</span>
          <span className="text-[#16A34A] font-semibold" data-testid="csv-valid-count">{stats.valid} valid</span>
          {stats.invalid > 0 && (<><span className="text-[#9B8AB0]">·</span><span className="text-[#D97706] font-semibold" data-testid="csv-invalid-count">{stats.invalid} skipped (validation)</span></>)}
        </div>
        <button onClick={() => setStep('map')} className="text-xs font-bold text-[#7C35DC] hover:underline" data-testid="preview-back-to-map-btn">
          Back to mapping
        </button>
      </div>

      <div className="border border-[#E8E0F5] rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-[#F4F0FF]">
              <tr>
                <th className="px-3 py-2 text-left font-bold uppercase tracking-wider text-[#7C35DC]">#</th>
                {ALL_HEADERS.filter(h => Object.values(mapping).includes(h)).map(h => (
                  <th key={h} className="px-3 py-2 text-left font-bold uppercase tracking-wider text-[#5A4A7A]">{FIELD_LABELS[h]}</th>
                ))}
                <th className="px-3 py-2 text-left font-bold uppercase tracking-wider text-[#5A4A7A]">status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#F0ECF9]">
              {mappedRows.slice(0, 6).map((r, i) => {
                const err = validateRow(r);
                return (
                  <tr key={i} className={err ? 'bg-[#FEF3C7]/40' : ''} data-testid={`csv-preview-row-${i}`}>
                    <td className="px-3 py-2 text-[#9B8AB0] font-mono">{i + 1}</td>
                    {ALL_HEADERS.filter(h => Object.values(mapping).includes(h)).map(h => (
                      <td key={h} className="px-3 py-2 text-[#1A0A2E] truncate max-w-[140px]">{String(r[h] ?? '')}</td>
                    ))}
                    <td className="px-3 py-2">
                      {err ? <span className="text-[#D97706] font-bold">{err}</span> : <span className="text-[#16A34A] font-bold">ready</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {mappedRows.length > 6 && <div className="px-3 py-2 text-[10px] uppercase tracking-wider font-bold text-[#9B8AB0] bg-[#FAF7FF] border-t border-[#F0ECF9]">+ {mappedRows.length - 6} more rows ready to upload</div>}
      </div>

      <div className="flex items-center justify-between gap-3 pt-2">
        <button type="button" onClick={() => setStep('map')}
          className="px-4 py-2 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-lg hover:bg-[#F9F5FF] text-sm font-medium" data-testid="preview-back-btn">
          ← Back to mapping
        </button>
        <div className="flex gap-2">
          <button type="button" onClick={onClose} className="px-4 py-2 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-lg hover:bg-[#F9F5FF] text-sm font-medium" data-testid="csv-cancel-btn">Cancel</button>
          <button type="button" onClick={handleSubmit} disabled={submitting || stats.valid === 0} data-testid="csv-submit-btn"
            className="px-6 py-2 btn-gradient rounded-lg text-sm font-semibold disabled:opacity-50" style={{ fontFamily:'Plus Jakarta Sans' }}>
            {submitting ? 'Uploading…' : `Upload ${stats.valid} lead${stats.valid !== 1 ? 's' : ''}`}
          </button>
        </div>
      </div>
    </div>
  );
};

export default LeadInbox;
