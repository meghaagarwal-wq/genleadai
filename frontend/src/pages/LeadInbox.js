import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../config/api';
import {
  MagnifyingGlass,
  Plus,
  Funnel,
  Export,
  CaretDown,
  X,
  UploadSimple,
} from '@phosphor-icons/react';

const CHANNELS = ['whatsapp', 'email', 'linkedin', 'instagram', 'facebook', 'website_form', 'cold_call', 'referral', 'webinar', 'organic_search', 'paid_ads', 'other'];
const STATUSES = ['new', 'contacted', 'qualified', 'unqualified', 'proposal_sent', 'negotiation', 'won', 'lost', 'nurture'];
const TIERS = ['hot', 'warm', 'cold'];

const LeadInbox = () => {
  const navigate = useNavigate();
  const [leads, setLeads] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState({ lead_type: '', status: '', source_channel: '', icp_tier: '' });
  const [showFilters, setShowFilters] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [page, setPage] = useState(0);
  const limit = 20;

  const fetchLeads = useCallback(async () => {
    setLoading(true);
    try {
      const params = { skip: page * limit, limit, search: search || undefined };
      Object.entries(filters).forEach(([k, v]) => { if (v) params[k] = v; });
      const res = await api.get('/api/leads', { params });
      setLeads(res.data.leads);
      setTotal(res.data.total);
    } catch (err) {
      console.error('Failed to fetch leads', err);
    } finally {
      setLoading(false);
    }
  }, [page, search, filters]);

  useEffect(() => { fetchLeads(); }, [fetchLeads]);

  const tierBadge = (tier) => {
    const s = { hot: 'bg-[#FF3B30]/10 text-[#FF3B30] border-[#FF3B30]/30', warm: 'bg-[#F59E0B]/10 text-[#F59E0B] border-[#F59E0B]/30', cold: 'bg-[#0055FF]/10 text-[#0055FF] border-[#0055FF]/30' };
    return `px-2 py-0.5 text-xs font-medium uppercase tracking-wider rounded-sm border ${s[tier] || s.cold}`;
  };

  const statusBadge = (status) => {
    const s = { new: 'bg-[#0055FF]/10 text-[#0055FF] border-[#0055FF]/30', contacted: 'bg-[#8B5CF6]/10 text-[#8B5CF6] border-[#8B5CF6]/30', qualified: 'bg-[#10B981]/10 text-[#10B981] border-[#10B981]/30', won: 'bg-[#10B981]/10 text-[#10B981] border-[#10B981]/30', lost: 'bg-[#FF3B30]/10 text-[#FF3B30] border-[#FF3B30]/30', proposal_sent: 'bg-[#F59E0B]/10 text-[#F59E0B] border-[#F59E0B]/30', negotiation: 'bg-[#F59E0B]/10 text-[#F59E0B] border-[#F59E0B]/30', nurture: 'bg-[#8B5CF6]/10 text-[#8B5CF6] border-[#8B5CF6]/30', unqualified: 'bg-[#737373]/10 text-[#737373] border-[#737373]/30' };
    return `px-2 py-0.5 text-xs font-medium uppercase tracking-wider rounded-sm border ${s[status] || s.new}`;
  };

  return (
    <div data-testid="lead-inbox-page" className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Lead Inbox</h1>
          <p className="text-sm text-[#A3A3A3] mt-1">{total} leads total</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowAddModal(true)}
            data-testid="add-lead-btn"
            className="flex items-center gap-2 bg-[#0055FF] text-white px-4 py-2 rounded-md hover:bg-[#0044CC] transition-colors text-sm font-medium"
          >
            <Plus size={16} weight="bold" /> Add Lead
          </button>
        </div>
      </div>

      {/* Search & Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-lg">
          <MagnifyingGlass size={20} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#737373]" />
          <input
            type="text"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(0); }}
            placeholder="Search by name, email, company..."
            data-testid="lead-search-input"
            className="w-full bg-[#0A0A0A] border border-[#262626] text-white pl-10 pr-4 py-2 rounded-md focus:border-[#0055FF] focus:ring-1 focus:ring-[#0055FF] transition-all text-sm"
          />
        </div>
        <button
          onClick={() => setShowFilters(!showFilters)}
          data-testid="toggle-filters-btn"
          className={`flex items-center gap-2 px-4 py-2 border rounded-md transition-colors text-sm ${showFilters ? 'bg-[#0055FF]/10 border-[#0055FF]/30 text-[#0055FF]' : 'bg-transparent border-[#262626] text-[#F5F5F5] hover:bg-[#1E1E1E]'}`}
        >
          <Funnel size={16} /> Filters
        </button>
      </div>

      {/* Filter Bar */}
      {showFilters && (
        <div className="bg-[#141414] border border-[#262626] rounded-lg p-4 flex flex-wrap gap-4" data-testid="filter-bar">
          <select value={filters.lead_type} onChange={(e) => { setFilters({...filters, lead_type: e.target.value}); setPage(0); }} className="bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2 rounded-md text-sm" data-testid="filter-lead-type">
            <option value="">All Types</option>
            <option value="B2B">B2B</option>
            <option value="B2C">B2C</option>
          </select>
          <select value={filters.status} onChange={(e) => { setFilters({...filters, status: e.target.value}); setPage(0); }} className="bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2 rounded-md text-sm" data-testid="filter-status">
            <option value="">All Statuses</option>
            {STATUSES.map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
          </select>
          <select value={filters.source_channel} onChange={(e) => { setFilters({...filters, source_channel: e.target.value}); setPage(0); }} className="bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2 rounded-md text-sm" data-testid="filter-channel">
            <option value="">All Channels</option>
            {CHANNELS.map(c => <option key={c} value={c}>{c.replace('_', ' ')}</option>)}
          </select>
          <select value={filters.icp_tier} onChange={(e) => { setFilters({...filters, icp_tier: e.target.value}); setPage(0); }} className="bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2 rounded-md text-sm" data-testid="filter-tier">
            <option value="">All Tiers</option>
            {TIERS.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          <button onClick={() => { setFilters({ lead_type: '', status: '', source_channel: '', icp_tier: '' }); setPage(0); }} className="text-sm text-[#FF3B30] hover:text-[#FF3B30]/80 transition-colors" data-testid="clear-filters-btn">
            Clear All
          </button>
        </div>
      )}

      {/* Leads Table */}
      <div className="bg-[#141414] border border-[#262626] rounded-lg overflow-hidden" data-testid="leads-table">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead>
              <tr className="border-b border-[#262626]">
                <th className="px-6 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-[#737373]">Name</th>
                <th className="px-6 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-[#737373]">Company</th>
                <th className="px-6 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-[#737373]">Type</th>
                <th className="px-6 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-[#737373]">Status</th>
                <th className="px-6 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-[#737373]">ICP</th>
                <th className="px-6 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-[#737373]">Score</th>
                <th className="px-6 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-[#737373]">Channel</th>
                <th className="px-6 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-[#737373]">Created</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={8} className="px-6 py-12 text-center text-[#737373]">Loading...</td></tr>
              ) : leads.length === 0 ? (
                <tr><td colSpan={8} className="px-6 py-12 text-center text-[#737373]">No leads found</td></tr>
              ) : (
                leads.map((lead) => (
                  <tr
                    key={lead.id}
                    className="border-b border-[#262626] hover:bg-[#1E1E1E] cursor-pointer transition-colors"
                    onClick={() => navigate(`/leads/${lead.id}`)}
                    data-testid={`lead-row-${lead.id}`}
                  >
                    <td className="px-6 py-4">
                      <div className="text-white font-medium">{lead.first_name} {lead.last_name}</div>
                      <div className="text-xs text-[#737373] font-mono">{lead.email}</div>
                    </td>
                    <td className="px-6 py-4 text-[#A3A3A3]">{lead.company_name || '—'}</td>
                    <td className="px-6 py-4">
                      <span className={`px-2 py-0.5 text-xs font-medium rounded-sm border ${lead.lead_type === 'B2B' ? 'bg-[#0055FF]/10 text-[#0055FF] border-[#0055FF]/30' : 'bg-[#10B981]/10 text-[#10B981] border-[#10B981]/30'}`}>
                        {lead.lead_type}
                      </span>
                    </td>
                    <td className="px-6 py-4"><span className={statusBadge(lead.status)}>{lead.status.replace('_', ' ')}</span></td>
                    <td className="px-6 py-4"><span className={tierBadge(lead.icp_tier)}>{lead.icp_tier}</span></td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <div className="w-12 h-1.5 bg-[#262626] rounded-full overflow-hidden">
                          <div className="h-full rounded-full" style={{ width: `${lead.icp_score}%`, backgroundColor: lead.icp_score >= 70 ? '#FF3B30' : lead.icp_score >= 40 ? '#F59E0B' : '#0055FF' }}></div>
                        </div>
                        <span className="text-xs font-mono text-[#A3A3A3]">{lead.icp_score}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-[#A3A3A3] text-xs">{lead.source_channel?.replace('_', ' ')}</td>
                    <td className="px-6 py-4 text-[#737373] text-xs font-mono">{new Date(lead.created_at).toLocaleDateString()}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="px-6 py-4 border-t border-[#262626] flex items-center justify-between">
          <span className="text-sm text-[#737373]">Showing {page * limit + 1}–{Math.min((page + 1) * limit, total)} of {total}</span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
              data-testid="prev-page-btn"
              className="px-3 py-1 bg-transparent border border-[#262626] text-[#F5F5F5] rounded-md hover:bg-[#1E1E1E] transition-colors text-sm disabled:opacity-30"
            >
              Previous
            </button>
            <button
              onClick={() => setPage(page + 1)}
              disabled={(page + 1) * limit >= total}
              data-testid="next-page-btn"
              className="px-3 py-1 bg-transparent border border-[#262626] text-[#F5F5F5] rounded-md hover:bg-[#1E1E1E] transition-colors text-sm disabled:opacity-30"
            >
              Next
            </button>
          </div>
        </div>
      </div>

      {/* Add Lead Modal */}
      {showAddModal && <AddLeadModal onClose={() => setShowAddModal(false)} onSuccess={() => { setShowAddModal(false); fetchLeads(); }} />}
    </div>
  );
};

const AddLeadModal = ({ onClose, onSuccess }) => {
  const [formData, setFormData] = useState({
    lead_type: 'B2B', first_name: '', last_name: '', email: '', phone: '',
    company_name: '', job_title: '', industry: '', source_channel: 'website_form',
    notes: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await api.post('/api/leads', formData);
      onSuccess();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create lead');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4" data-testid="add-lead-modal">
      <div className="bg-[#141414] border border-[#262626] rounded-lg w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-6 border-b border-[#262626]">
          <h2 className="text-xl font-bold text-white">Add New Lead</h2>
          <button onClick={onClose} className="text-[#737373] hover:text-white transition-colors" data-testid="close-modal-btn">
            <X size={24} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && <div className="bg-[#FF3B30]/10 border border-[#FF3B30]/30 text-[#FF3B30] rounded-md p-3 text-sm">{error}</div>}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-[#F5F5F5] mb-1.5">Lead Type</label>
              <select value={formData.lead_type} onChange={(e) => setFormData({...formData, lead_type: e.target.value})} className="w-full bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2.5 rounded-md text-sm" data-testid="form-lead-type">
                <option value="B2B">B2B</option>
                <option value="B2C">B2C</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-[#F5F5F5] mb-1.5">Source Channel</label>
              <select value={formData.source_channel} onChange={(e) => setFormData({...formData, source_channel: e.target.value})} className="w-full bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2.5 rounded-md text-sm" data-testid="form-channel">
                {['whatsapp','email','linkedin','instagram','facebook','website_form','cold_call','referral','webinar','organic_search','paid_ads','other'].map(c => <option key={c} value={c}>{c.replace('_', ' ')}</option>)}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-[#F5F5F5] mb-1.5">First Name *</label>
              <input type="text" value={formData.first_name} onChange={(e) => setFormData({...formData, first_name: e.target.value})} required className="w-full bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2.5 rounded-md text-sm" data-testid="form-first-name" />
            </div>
            <div>
              <label className="block text-sm font-medium text-[#F5F5F5] mb-1.5">Last Name *</label>
              <input type="text" value={formData.last_name} onChange={(e) => setFormData({...formData, last_name: e.target.value})} required className="w-full bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2.5 rounded-md text-sm" data-testid="form-last-name" />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-[#F5F5F5] mb-1.5">Email *</label>
              <input type="email" value={formData.email} onChange={(e) => setFormData({...formData, email: e.target.value})} required className="w-full bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2.5 rounded-md text-sm" data-testid="form-email" />
            </div>
            <div>
              <label className="block text-sm font-medium text-[#F5F5F5] mb-1.5">Phone</label>
              <input type="text" value={formData.phone} onChange={(e) => setFormData({...formData, phone: e.target.value})} className="w-full bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2.5 rounded-md text-sm" data-testid="form-phone" />
            </div>
          </div>

          {formData.lead_type === 'B2B' && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-[#F5F5F5] mb-1.5">Company</label>
                <input type="text" value={formData.company_name} onChange={(e) => setFormData({...formData, company_name: e.target.value})} className="w-full bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2.5 rounded-md text-sm" data-testid="form-company" />
              </div>
              <div>
                <label className="block text-sm font-medium text-[#F5F5F5] mb-1.5">Job Title</label>
                <input type="text" value={formData.job_title} onChange={(e) => setFormData({...formData, job_title: e.target.value})} className="w-full bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2.5 rounded-md text-sm" data-testid="form-job-title" />
              </div>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-[#F5F5F5] mb-1.5">Notes</label>
            <textarea value={formData.notes} onChange={(e) => setFormData({...formData, notes: e.target.value})} rows={3} className="w-full bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2.5 rounded-md text-sm resize-none" data-testid="form-notes" />
          </div>

          <div className="flex justify-end gap-3 pt-4">
            <button type="button" onClick={onClose} className="px-4 py-2 bg-transparent border border-[#262626] text-[#F5F5F5] rounded-md hover:bg-[#1E1E1E] transition-colors text-sm" data-testid="cancel-add-lead-btn">Cancel</button>
            <button type="submit" disabled={loading} className="px-6 py-2 bg-[#0055FF] text-white rounded-md hover:bg-[#0044CC] transition-colors text-sm font-medium disabled:opacity-50" data-testid="submit-lead-btn">
              {loading ? 'Creating...' : 'Create Lead'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default LeadInbox;
