import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../config/api';
import {
  Users,
  TrendUp,
  Fire,
  Target,
  ArrowRight,
  Lightning,
} from '@phosphor-icons/react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';

const Dashboard = () => {
  const navigate = useNavigate();
  const [analytics, setAnalytics] = useState(null);
  const [recentLeads, setRecentLeads] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [analyticsRes, leadsRes] = await Promise.all([
        api.get('/api/analytics/dashboard'),
        api.get('/api/leads?limit=5'),
      ]);
      setAnalytics(analyticsRes.data);
      setRecentLeads(leadsRes.data.leads);
    } catch (err) {
      console.error('Failed to fetch dashboard data', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-[#A3A3A3] font-mono text-sm">Loading dashboard...</div>
      </div>
    );
  }

  const channelData = analytics
    ? Object.entries(analytics.channel_distribution)
        .filter(([, v]) => v > 0)
        .map(([key, value]) => ({ name: key, value }))
        .sort((a, b) => b.value - a.value)
    : [];

  const typeData = analytics
    ? [
        { name: 'B2B', value: analytics.lead_type_distribution.B2B },
        { name: 'B2C', value: analytics.lead_type_distribution.B2C },
      ]
    : [];

  const icpData = analytics
    ? [
        { name: 'Hot', value: analytics.icp_distribution.hot, color: '#FF3B30' },
        { name: 'Warm', value: analytics.icp_distribution.warm, color: '#F59E0B' },
        { name: 'Cold', value: analytics.icp_distribution.cold, color: '#0055FF' },
      ]
    : [];

  const PIE_COLORS = ['#0055FF', '#10B981'];

  const tierBadge = (tier) => {
    const styles = {
      hot: 'bg-[#FF3B30]/10 text-[#FF3B30] border-[#FF3B30]/30',
      warm: 'bg-[#F59E0B]/10 text-[#F59E0B] border-[#F59E0B]/30',
      cold: 'bg-[#0055FF]/10 text-[#0055FF] border-[#0055FF]/30',
    };
    return `px-2 py-0.5 text-xs font-medium uppercase tracking-wider rounded-sm border ${styles[tier] || styles.cold}`;
  };

  const statusBadge = (status) => {
    const styles = {
      new: 'bg-[#0055FF]/10 text-[#0055FF] border-[#0055FF]/30',
      contacted: 'bg-[#8B5CF6]/10 text-[#8B5CF6] border-[#8B5CF6]/30',
      qualified: 'bg-[#10B981]/10 text-[#10B981] border-[#10B981]/30',
      won: 'bg-[#10B981]/10 text-[#10B981] border-[#10B981]/30',
      lost: 'bg-[#FF3B30]/10 text-[#FF3B30] border-[#FF3B30]/30',
      proposal_sent: 'bg-[#F59E0B]/10 text-[#F59E0B] border-[#F59E0B]/30',
      negotiation: 'bg-[#F59E0B]/10 text-[#F59E0B] border-[#F59E0B]/30',
    };
    return `px-2 py-0.5 text-xs font-medium uppercase tracking-wider rounded-sm border ${styles[status] || styles.new}`;
  };

  return (
    <div data-testid="dashboard-page" className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Dashboard</h1>
          <p className="text-sm text-[#A3A3A3] mt-1">Growth pipeline overview</p>
        </div>
        <button
          onClick={() => navigate('/leads')}
          data-testid="view-all-leads-btn"
          className="flex items-center gap-2 bg-[#0055FF] text-white px-4 py-2 rounded-md hover:bg-[#0044CC] transition-colors text-sm font-medium"
        >
          View All Leads <ArrowRight size={16} />
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-[#141414] border border-[#262626] rounded-lg p-6 hover:border-white/20 hover:-translate-y-0.5 transition-all" data-testid="kpi-total-leads">
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs font-semibold uppercase tracking-[0.2em] text-[#737373]">Total Leads</span>
            <Users size={20} className="text-[#0055FF]" weight="duotone" />
          </div>
          <div className="text-3xl font-bold text-white">{analytics?.total_leads || 0}</div>
          <div className="text-sm text-[#10B981] mt-1 flex items-center gap-1">
            <TrendUp size={14} /> Active pipeline
          </div>
        </div>

        <div className="bg-[#141414] border border-[#262626] rounded-lg p-6 hover:border-white/20 hover:-translate-y-0.5 transition-all" data-testid="kpi-hot-leads">
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs font-semibold uppercase tracking-[0.2em] text-[#737373]">Hot Leads</span>
            <Fire size={20} className="text-[#FF3B30]" weight="duotone" />
          </div>
          <div className="text-3xl font-bold text-white">{analytics?.icp_distribution?.hot || 0}</div>
          <div className="text-sm text-[#F59E0B] mt-1">ICP Score 70+</div>
        </div>

        <div className="bg-[#141414] border border-[#262626] rounded-lg p-6 hover:border-white/20 hover:-translate-y-0.5 transition-all" data-testid="kpi-won">
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs font-semibold uppercase tracking-[0.2em] text-[#737373]">Won Deals</span>
            <Target size={20} className="text-[#10B981]" weight="duotone" />
          </div>
          <div className="text-3xl font-bold text-white">{analytics?.status_distribution?.won || 0}</div>
          <div className="text-sm text-[#10B981] mt-1">Closed successfully</div>
        </div>

        <div className="bg-[#141414] border border-[#262626] rounded-lg p-6 hover:border-white/20 hover:-translate-y-0.5 transition-all" data-testid="kpi-conversion">
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs font-semibold uppercase tracking-[0.2em] text-[#737373]">Qualified</span>
            <Lightning size={20} className="text-[#8B5CF6]" weight="duotone" />
          </div>
          <div className="text-3xl font-bold text-white">{analytics?.status_distribution?.qualified || 0}</div>
          <div className="text-sm text-[#8B5CF6] mt-1">Ready for outreach</div>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Channel Distribution */}
        <div className="lg:col-span-2 bg-[#141414] border border-[#262626] rounded-lg p-6" data-testid="chart-channels">
          <h3 className="text-lg font-semibold text-white mb-4">Leads by Channel</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={channelData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
              <XAxis dataKey="name" tick={{ fill: '#737373', fontSize: 12 }} />
              <YAxis tick={{ fill: '#737373', fontSize: 12 }} />
              <Tooltip
                contentStyle={{ background: '#141414', border: '1px solid #262626', borderRadius: '8px', color: '#F5F5F5' }}
              />
              <Bar dataKey="value" fill="#0055FF" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Lead Type Split */}
        <div className="bg-[#141414] border border-[#262626] rounded-lg p-6" data-testid="chart-lead-type">
          <h3 className="text-lg font-semibold text-white mb-4">B2B vs B2C</h3>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={typeData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                {typeData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ background: '#141414', border: '1px solid #262626', borderRadius: '8px', color: '#F5F5F5' }} />
            </PieChart>
          </ResponsiveContainer>
          {/* ICP Distribution */}
          <div className="mt-4 space-y-2">
            <h4 className="text-xs font-semibold uppercase tracking-[0.2em] text-[#737373]">ICP Distribution</h4>
            {icpData.map((item) => (
              <div key={item.name} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: item.color }}></div>
                  <span className="text-sm text-[#A3A3A3]">{item.name}</span>
                </div>
                <span className="text-sm font-medium text-white">{item.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Recent Leads Table */}
      <div className="bg-[#141414] border border-[#262626] rounded-lg" data-testid="recent-leads-table">
        <div className="p-6 border-b border-[#262626] flex items-center justify-between">
          <h3 className="text-lg font-semibold text-white">Recent Leads</h3>
          <button
            onClick={() => navigate('/leads')}
            className="text-sm text-[#0055FF] hover:text-[#0044CC] transition-colors"
          >
            View all
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead>
              <tr className="border-b border-[#262626]">
                <th className="px-6 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-[#737373]">Name</th>
                <th className="px-6 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-[#737373]">Email</th>
                <th className="px-6 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-[#737373]">Type</th>
                <th className="px-6 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-[#737373]">Status</th>
                <th className="px-6 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-[#737373]">ICP</th>
                <th className="px-6 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-[#737373]">Channel</th>
              </tr>
            </thead>
            <tbody>
              {recentLeads.map((lead) => (
                <tr
                  key={lead.id}
                  className="border-b border-[#262626] hover:bg-[#1E1E1E] cursor-pointer transition-colors"
                  onClick={() => navigate(`/leads/${lead.id}`)}
                  data-testid={`lead-row-${lead.id}`}
                >
                  <td className="px-6 py-4 text-white font-medium">
                    {lead.first_name} {lead.last_name}
                  </td>
                  <td className="px-6 py-4 text-[#A3A3A3] font-mono text-xs">{lead.email}</td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-0.5 text-xs font-medium rounded-sm border ${lead.lead_type === 'B2B' ? 'bg-[#0055FF]/10 text-[#0055FF] border-[#0055FF]/30' : 'bg-[#10B981]/10 text-[#10B981] border-[#10B981]/30'}`}>
                      {lead.lead_type}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span className={statusBadge(lead.status)}>{lead.status}</span>
                  </td>
                  <td className="px-6 py-4">
                    <span className={tierBadge(lead.icp_tier)}>{lead.icp_tier}</span>
                  </td>
                  <td className="px-6 py-4 text-[#A3A3A3]">{lead.source_channel}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
