import React, { useState, useEffect } from 'react';
import api from '../config/api';
import { Plus, X, Rocket, CurrencyDollar, Users, TrendUp } from '@phosphor-icons/react';

const CHANNELS = ['whatsapp', 'email', 'linkedin', 'instagram', 'facebook', 'website_form', 'cold_call', 'referral', 'webinar', 'organic_search', 'paid_ads', 'other'];

const Campaigns = () => {
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);

  useEffect(() => { fetchCampaigns(); }, []);

  const fetchCampaigns = async () => {
    try {
      const res = await api.get('/api/campaigns');
      setCampaigns(res.data.campaigns);
    } catch (err) {
      console.error('Failed to fetch campaigns', err);
    } finally {
      setLoading(false);
    }
  };

  const statusColor = (s) => {
    const c = { active: 'bg-[#10B981]/10 text-[#10B981] border-[#10B981]/30', draft: 'bg-[#737373]/10 text-[#737373] border-[#737373]/30', paused: 'bg-[#F59E0B]/10 text-[#F59E0B] border-[#F59E0B]/30', ended: 'bg-[#FF3B30]/10 text-[#FF3B30] border-[#FF3B30]/30' };
    return `px-2 py-0.5 text-xs font-medium uppercase tracking-wider rounded-sm border ${c[s] || c.draft}`;
  };

  return (
    <div data-testid="campaigns-page" className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Campaigns</h1>
          <p className="text-sm text-[#A3A3A3] mt-1">Manage acquisition campaigns</p>
        </div>
        <button onClick={() => setShowCreate(true)} data-testid="create-campaign-btn" className="flex items-center gap-2 bg-[#0055FF] text-white px-4 py-2 rounded-md hover:bg-[#0044CC] transition-colors text-sm font-medium">
          <Plus size={16} weight="bold" /> New Campaign
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64"><div className="text-[#A3A3A3] font-mono text-sm">Loading campaigns...</div></div>
      ) : campaigns.length === 0 ? (
        <div className="bg-[#141414] border border-[#262626] rounded-lg p-12 text-center">
          <Rocket size={48} className="text-[#737373] mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-white mb-2">No campaigns yet</h3>
          <p className="text-sm text-[#A3A3A3]">Create your first campaign to start tracking lead acquisition.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {campaigns.map(campaign => (
            <div key={campaign.id} className="bg-[#141414] border border-[#262626] rounded-lg p-6 hover:border-white/20 hover:-translate-y-0.5 transition-all" data-testid={`campaign-card-${campaign.id}`}>
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="text-lg font-semibold text-white">{campaign.name}</h3>
                  <span className={statusColor(campaign.status)}>{campaign.status}</span>
                </div>
                <span className={`px-2 py-0.5 text-xs font-medium uppercase tracking-wider rounded-sm border ${campaign.lead_type === 'B2B' ? 'bg-[#0055FF]/10 text-[#0055FF] border-[#0055FF]/30' : campaign.lead_type === 'B2C' ? 'bg-[#10B981]/10 text-[#10B981] border-[#10B981]/30' : 'bg-[#8B5CF6]/10 text-[#8B5CF6] border-[#8B5CF6]/30'}`}>
                  {campaign.lead_type}
                </span>
              </div>
              
              {campaign.description && <p className="text-sm text-[#A3A3A3] mb-4 line-clamp-2">{campaign.description}</p>}

              <div className="grid grid-cols-2 gap-3">
                <div className="bg-[#0A0A0A] rounded p-3">
                  <div className="flex items-center gap-1 text-xs text-[#737373] mb-1"><Users size={12} /> Leads</div>
                  <div className="text-lg font-bold text-white">{campaign.total_leads || 0}</div>
                </div>
                <div className="bg-[#0A0A0A] rounded p-3">
                  <div className="flex items-center gap-1 text-xs text-[#737373] mb-1"><TrendUp size={12} /> Qualified</div>
                  <div className="text-lg font-bold text-[#10B981]">{campaign.qualified_leads || 0}</div>
                </div>
                {campaign.budget && (
                  <div className="bg-[#0A0A0A] rounded p-3">
                    <div className="flex items-center gap-1 text-xs text-[#737373] mb-1"><CurrencyDollar size={12} /> Budget</div>
                    <div className="text-lg font-bold text-white">${campaign.budget?.toLocaleString()}</div>
                  </div>
                )}
                {campaign.spend !== undefined && (
                  <div className="bg-[#0A0A0A] rounded p-3">
                    <div className="flex items-center gap-1 text-xs text-[#737373] mb-1"><CurrencyDollar size={12} /> Spent</div>
                    <div className="text-lg font-bold text-[#F59E0B]">${campaign.spend?.toLocaleString()}</div>
                  </div>
                )}
              </div>

              <div className="mt-4 pt-4 border-t border-[#262626] flex items-center justify-between text-xs text-[#737373]">
                <span>{campaign.channel?.replace('_', ' ')}</span>
                {campaign.start_date && <span>{campaign.start_date} — {campaign.end_date || 'ongoing'}</span>}
              </div>
            </div>
          ))}
        </div>
      )}

      {showCreate && <CreateCampaignModal onClose={() => setShowCreate(false)} onSuccess={() => { setShowCreate(false); fetchCampaigns(); }} />}
    </div>
  );
};

const CreateCampaignModal = ({ onClose, onSuccess }) => {
  const [data, setData] = useState({
    name: '', description: '', channel: 'linkedin', lead_type: 'B2B', status: 'draft',
    start_date: '', end_date: '', budget: '', target_audience: '', utm_source: '', utm_medium: '', utm_campaign: '',
    goal_leads: '', goal_conversions: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const payload = { ...data };
      if (payload.budget) payload.budget = parseFloat(payload.budget);
      if (payload.goal_leads) payload.goal_leads = parseInt(payload.goal_leads);
      if (payload.goal_conversions) payload.goal_conversions = parseInt(payload.goal_conversions);
      await api.post('/api/campaigns', payload);
      onSuccess();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create campaign');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4" data-testid="create-campaign-modal">
      <div className="bg-[#141414] border border-[#262626] rounded-lg w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-6 border-b border-[#262626]">
          <h2 className="text-xl font-bold text-white">Create Campaign</h2>
          <button onClick={onClose} className="text-[#737373] hover:text-white"><X size={24} /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && <div className="bg-[#FF3B30]/10 border border-[#FF3B30]/30 text-[#FF3B30] rounded-md p-3 text-sm">{error}</div>}
          
          <div>
            <label className="block text-sm font-medium text-[#F5F5F5] mb-1.5">Campaign Name *</label>
            <input type="text" value={data.name} onChange={(e) => setData({...data, name: e.target.value})} required className="w-full bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2.5 rounded-md text-sm" data-testid="campaign-name-input" />
          </div>

          <div>
            <label className="block text-sm font-medium text-[#F5F5F5] mb-1.5">Description</label>
            <textarea value={data.description} onChange={(e) => setData({...data, description: e.target.value})} rows={2} className="w-full bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2.5 rounded-md text-sm resize-none" data-testid="campaign-description-input" />
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-[#F5F5F5] mb-1.5">Channel</label>
              <select value={data.channel} onChange={(e) => setData({...data, channel: e.target.value})} className="w-full bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2.5 rounded-md text-sm" data-testid="campaign-channel-select">
                {CHANNELS.map(c => <option key={c} value={c}>{c.replace('_', ' ')}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-[#F5F5F5] mb-1.5">Lead Type</label>
              <select value={data.lead_type} onChange={(e) => setData({...data, lead_type: e.target.value})} className="w-full bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2.5 rounded-md text-sm" data-testid="campaign-type-select">
                <option value="B2B">B2B</option>
                <option value="B2C">B2C</option>
                <option value="both">Both</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-[#F5F5F5] mb-1.5">Budget ($)</label>
              <input type="number" value={data.budget} onChange={(e) => setData({...data, budget: e.target.value})} className="w-full bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2.5 rounded-md text-sm" data-testid="campaign-budget-input" />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-[#F5F5F5] mb-1.5">Start Date</label>
              <input type="date" value={data.start_date} onChange={(e) => setData({...data, start_date: e.target.value})} className="w-full bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2.5 rounded-md text-sm" data-testid="campaign-start-date" />
            </div>
            <div>
              <label className="block text-sm font-medium text-[#F5F5F5] mb-1.5">End Date</label>
              <input type="date" value={data.end_date} onChange={(e) => setData({...data, end_date: e.target.value})} className="w-full bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2.5 rounded-md text-sm" data-testid="campaign-end-date" />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-[#F5F5F5] mb-1.5">Target Audience</label>
            <input type="text" value={data.target_audience} onChange={(e) => setData({...data, target_audience: e.target.value})} className="w-full bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2.5 rounded-md text-sm" data-testid="campaign-audience-input" />
          </div>

          <div className="flex justify-end gap-3 pt-4">
            <button type="button" onClick={onClose} className="px-4 py-2 bg-transparent border border-[#262626] text-[#F5F5F5] rounded-md hover:bg-[#1E1E1E] text-sm">Cancel</button>
            <button type="submit" disabled={loading} className="px-6 py-2 bg-[#0055FF] text-white rounded-md hover:bg-[#0044CC] text-sm font-medium disabled:opacity-50" data-testid="submit-campaign-btn">
              {loading ? 'Creating...' : 'Create Campaign'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Campaigns;
