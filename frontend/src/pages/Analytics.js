import React, { useState, useEffect } from 'react';
import api from '../config/api';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line, AreaChart, Area,
} from 'recharts';
import { ChartBar, TrendUp, Users, Target } from '@phosphor-icons/react';

const Analytics = () => {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { fetchAnalytics(); }, []);

  const fetchAnalytics = async () => {
    try {
      const res = await api.get('/api/analytics/dashboard');
      setAnalytics(res.data);
    } catch (err) {
      console.error('Failed to fetch analytics', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-[#A3A3A3] font-mono text-sm">Loading analytics...</div></div>;
  if (!analytics) return null;

  const channelData = Object.entries(analytics.channel_distribution)
    .filter(([, v]) => v > 0)
    .map(([key, value]) => ({ name: key.replace('_', ' '), value }))
    .sort((a, b) => b.value - a.value);

  const statusData = Object.entries(analytics.status_distribution)
    .filter(([, v]) => v > 0)
    .map(([key, value]) => ({ name: key.replace('_', ' '), value }));

  const typeData = [
    { name: 'B2B', value: analytics.lead_type_distribution.B2B },
    { name: 'B2C', value: analytics.lead_type_distribution.B2C },
  ];

  const icpData = [
    { name: 'Hot', value: analytics.icp_distribution.hot },
    { name: 'Warm', value: analytics.icp_distribution.warm },
    { name: 'Cold', value: analytics.icp_distribution.cold },
  ];

  const COLORS = ['#0055FF', '#10B981', '#F59E0B', '#8B5CF6', '#FF3B30'];
  const ICP_COLORS = ['#FF3B30', '#F59E0B', '#0055FF'];

  const funnelData = [
    { stage: 'New', value: analytics.status_distribution.new || 0 },
    { stage: 'Contacted', value: analytics.status_distribution.contacted || 0 },
    { stage: 'Qualified', value: analytics.status_distribution.qualified || 0 },
    { stage: 'Proposal', value: analytics.status_distribution.proposal_sent || 0 },
    { stage: 'Won', value: analytics.status_distribution.won || 0 },
  ];

  return (
    <div data-testid="analytics-page" className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white tracking-tight">Analytics</h1>
        <p className="text-sm text-[#A3A3A3] mt-1">Performance metrics and insights</p>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-[#141414] border border-[#262626] rounded-lg p-6" data-testid="analytics-total-leads">
          <div className="flex items-center gap-2 mb-2">
            <Users size={16} className="text-[#0055FF]" weight="duotone" />
            <span className="text-xs font-semibold uppercase tracking-[0.2em] text-[#737373]">Total Leads</span>
          </div>
          <div className="text-3xl font-bold text-white">{analytics.total_leads}</div>
        </div>
        <div className="bg-[#141414] border border-[#262626] rounded-lg p-6" data-testid="analytics-qualified">
          <div className="flex items-center gap-2 mb-2">
            <Target size={16} className="text-[#10B981]" weight="duotone" />
            <span className="text-xs font-semibold uppercase tracking-[0.2em] text-[#737373]">Qualified</span>
          </div>
          <div className="text-3xl font-bold text-[#10B981]">{analytics.status_distribution.qualified || 0}</div>
        </div>
        <div className="bg-[#141414] border border-[#262626] rounded-lg p-6" data-testid="analytics-won">
          <div className="flex items-center gap-2 mb-2">
            <TrendUp size={16} className="text-[#F59E0B]" weight="duotone" />
            <span className="text-xs font-semibold uppercase tracking-[0.2em] text-[#737373]">Won</span>
          </div>
          <div className="text-3xl font-bold text-[#F59E0B]">{analytics.status_distribution.won || 0}</div>
        </div>
        <div className="bg-[#141414] border border-[#262626] rounded-lg p-6" data-testid="analytics-conversion">
          <div className="flex items-center gap-2 mb-2">
            <ChartBar size={16} className="text-[#8B5CF6]" weight="duotone" />
            <span className="text-xs font-semibold uppercase tracking-[0.2em] text-[#737373]">Conversion Rate</span>
          </div>
          <div className="text-3xl font-bold text-[#8B5CF6]">
            {analytics.total_leads > 0 ? Math.round(((analytics.status_distribution.won || 0) / analytics.total_leads) * 100) : 0}%
          </div>
        </div>
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Channel Distribution */}
        <div className="bg-[#141414] border border-[#262626] rounded-lg p-6" data-testid="chart-channel-dist">
          <h3 className="text-lg font-semibold text-white mb-4">Leads by Channel</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={channelData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
              <XAxis type="number" tick={{ fill: '#737373', fontSize: 12 }} />
              <YAxis type="category" dataKey="name" tick={{ fill: '#737373', fontSize: 11 }} width={100} />
              <Tooltip contentStyle={{ background: '#141414', border: '1px solid #262626', borderRadius: '8px', color: '#F5F5F5' }} />
              <Bar dataKey="value" fill="#0055FF" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Conversion Funnel */}
        <div className="bg-[#141414] border border-[#262626] rounded-lg p-6" data-testid="chart-funnel">
          <h3 className="text-lg font-semibold text-white mb-4">Conversion Funnel</h3>
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={funnelData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
              <XAxis dataKey="stage" tick={{ fill: '#737373', fontSize: 12 }} />
              <YAxis tick={{ fill: '#737373', fontSize: 12 }} />
              <Tooltip contentStyle={{ background: '#141414', border: '1px solid #262626', borderRadius: '8px', color: '#F5F5F5' }} />
              <Area type="monotone" dataKey="value" stroke="#0055FF" fill="#0055FF" fillOpacity={0.1} strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Lead Type Distribution */}
        <div className="bg-[#141414] border border-[#262626] rounded-lg p-6" data-testid="chart-type-dist">
          <h3 className="text-lg font-semibold text-white mb-4">B2B vs B2C Split</h3>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie data={typeData} cx="50%" cy="50%" innerRadius={60} outerRadius={90} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                {typeData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ background: '#141414', border: '1px solid #262626', borderRadius: '8px', color: '#F5F5F5' }} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* ICP Distribution */}
        <div className="bg-[#141414] border border-[#262626] rounded-lg p-6" data-testid="chart-icp-dist">
          <h3 className="text-lg font-semibold text-white mb-4">ICP Tier Distribution</h3>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie data={icpData} cx="50%" cy="50%" innerRadius={60} outerRadius={90} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                {icpData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={ICP_COLORS[index % ICP_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ background: '#141414', border: '1px solid #262626', borderRadius: '8px', color: '#F5F5F5' }} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Status Distribution */}
        <div className="lg:col-span-2 bg-[#141414] border border-[#262626] rounded-lg p-6" data-testid="chart-status-dist">
          <h3 className="text-lg font-semibold text-white mb-4">Lead Status Distribution</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={statusData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
              <XAxis dataKey="name" tick={{ fill: '#737373', fontSize: 12 }} />
              <YAxis tick={{ fill: '#737373', fontSize: 12 }} />
              <Tooltip contentStyle={{ background: '#141414', border: '1px solid #262626', borderRadius: '8px', color: '#F5F5F5' }} />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {statusData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};

export default Analytics;
