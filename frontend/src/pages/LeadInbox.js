import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../config/api';
import { MagnifyingGlass, Plus, Funnel, X } from '@phosphor-icons/react';

const CHANNELS = ['whatsapp','email','linkedin','instagram','facebook','website_form','cold_call','referral','webinar','organic_search','paid_ads','other'];
const STATUSES = ['new','contacted','qualified','unqualified','proposal_sent','negotiation','won','lost','nurture'];
const TIERS = ['hot','warm','cold'];

const LeadInbox = () => {
  const navigate = useNavigate();
  const [leads, setLeads] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState({ lead_type:'', status:'', source_channel:'', icp_tier:'' });
  const [showFilters, setShowFilters] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [page, setPage] = useState(0);
  const limit = 20;

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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-extrabold text-[#1A0A2E] tracking-tight" style={{ fontFamily:'Plus Jakarta Sans' }}>Lead Inbox</h1>
          <p className="text-sm text-[#5A4A7A] mt-1">{total} leads total</p>
        </div>
        <button onClick={() => setShowAddModal(true)} data-testid="add-lead-btn" className="flex items-center gap-2 btn-gradient px-4 py-2 rounded-lg text-sm font-semibold" style={{ fontFamily:'Plus Jakarta Sans' }}>
          <Plus size={16} weight="bold" /> Add Lead
        </button>
      </div>

      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-lg">
          <MagnifyingGlass size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9B8AB0]" />
          <input type="text" value={search} onChange={(e) => { setSearch(e.target.value); setPage(0); }} placeholder="Search by name, email, company..." data-testid="lead-search-input" className={`w-full pl-10 pr-4 ${inputCls}`} />
        </div>
        <button onClick={() => setShowFilters(!showFilters)} data-testid="toggle-filters-btn"
          className={`flex items-center gap-2 px-4 py-2 border rounded-lg transition-all text-sm font-medium ${showFilters ? 'bg-[#F4F0FF] border-[#7C35DC]/30 text-[#7C35DC]' : 'bg-white border-[#E8E0F5] text-[#5A4A7A] hover:bg-[#F9F5FF] hover:text-[#7C35DC]'}`} style={{ fontFamily:'Plus Jakarta Sans' }}>
          <Funnel size={16} /> Filters
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
                {['Name','Company','Type','Status','ICP','Score','Channel','Created'].map(h => (
                  <th key={h} className="px-6 py-3 text-xs font-semibold uppercase tracking-[0.15em] text-[#5A4A7A]" style={{ fontFamily:'Plus Jakarta Sans' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={8} className="px-6 py-12 text-center text-[#9B8AB0]">Loading...</td></tr>
              ) : leads.length === 0 ? (
                <tr><td colSpan={8} className="px-6 py-12 text-center text-[#9B8AB0]">No leads found</td></tr>
              ) : leads.map(lead => (
                <tr key={lead.id} className="border-b border-[#F0ECF9] hover:bg-[#F9F5FF] cursor-pointer transition-colors" onClick={() => navigate(`/leads/${lead.id}`)} data-testid={`lead-row-${lead.id}`}>
                  <td className="px-6 py-4">
                    <div className="font-semibold text-[#1A0A2E]">{lead.first_name} {lead.last_name}</div>
                    <div className="text-xs text-[#9B8AB0] font-mono">{lead.email}</div>
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
                  <td className="px-6 py-4 text-[#5A4A7A] text-xs">{lead.source_channel?.replace('_',' ')}</td>
                  <td className="px-6 py-4 text-[#9B8AB0] text-xs font-mono">{new Date(lead.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
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
    </div>
  );
};

const AddLeadModal = ({ onClose, onSuccess }) => {
  const [formData, setFormData] = useState({ lead_type:'B2B', first_name:'', last_name:'', email:'', phone:'', company_name:'', job_title:'', industry:'', source_channel:'website_form', notes:'' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault(); setLoading(true); setError('');
    try { await api.post('/api/leads', formData); onSuccess(); }
    catch(err) { setError(err.response?.data?.detail || 'Failed to create lead'); }
    finally { setLoading(false); }
  };

  const inputCls = "w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-2.5 rounded-lg text-sm focus:border-[#7C35DC] focus:ring-2 focus:ring-[rgba(124,53,220,0.12)] transition-all";

  return (
    <div className="fixed inset-0 bg-black/20 backdrop-blur-sm flex items-center justify-center z-50 p-4" data-testid="add-lead-modal">
      <div className="bg-white border border-[#E8E0F5] rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto" style={{ boxShadow:'var(--shadow-hover)' }}>
        <div className="flex items-center justify-between p-6 border-b border-[#E8E0F5]">
          <h2 className="text-xl font-bold text-[#1A0A2E]" style={{ fontFamily:'Plus Jakarta Sans' }}>Add New Lead</h2>
          <button onClick={onClose} className="text-[#9B8AB0] hover:text-[#7C35DC] transition-colors" data-testid="close-modal-btn"><X size={24} /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
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
      </div>
    </div>
  );
};

export default LeadInbox;
