import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../config/api';
import { Users, TrendUp, Fire, Target, ArrowRight, Lightning } from '@phosphor-icons/react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

const Dashboard = () => {
  const navigate = useNavigate();
  const [analytics, setAnalytics] = useState(null);
  const [recentLeads, setRecentLeads] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { fetchData(); }, []);
  const fetchData = async () => {
    try {
      const [aRes, lRes] = await Promise.all([api.get('/api/analytics/dashboard'), api.get('/api/leads?limit=5')]);
      setAnalytics(aRes.data);
      setRecentLeads(lRes.data.leads);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-[#9B8AB0] text-sm">Loading dashboard...</div></div>;

  const channelData = analytics ? Object.entries(analytics.channel_distribution).filter(([,v]) => v > 0).map(([k,v]) => ({ name: k.replace('_',' '), value: v })).sort((a,b) => b.value - a.value) : [];
  const typeData = analytics ? [{ name: 'B2B', value: analytics.lead_type_distribution.B2B }, { name: 'B2C', value: analytics.lead_type_distribution.B2C }] : [];
  const icpData = analytics ? [{ name: 'Hot', value: analytics.icp_distribution.hot, color: '#7C35DC' }, { name: 'Warm', value: analytics.icp_distribution.warm, color: '#D97706' }, { name: 'Cold', value: analytics.icp_distribution.cold, color: '#94A3B8' }] : [];
  const PIE_COLORS = ['#7C35DC', '#16A34A'];

  const tierBadge = (tier) => {
    const s = { hot: 'bg-[#F4E6FD] text-[#7C35DC] border-[#C044E0]', warm: 'bg-[#FEF3C7] text-[#D97706] border-[#D97706]/30', cold: 'bg-[#F1F5F9] text-[#64748B] border-[#94A3B8]/30' };
    return `px-2 py-0.5 text-xs font-semibold uppercase tracking-wider rounded border ${s[tier] || s.cold}`;
  };
  const statusBadge = (status) => {
    const s = { new: 'bg-[#F4F0FF] text-[#7C35DC] border-[#7C35DC]/20', contacted: 'bg-[#F4F0FF] text-[#A855F7] border-[#A855F7]/20', qualified: 'bg-[#DCFCE7] text-[#16A34A] border-[#16A34A]/20', won: 'bg-[#DCFCE7] text-[#16A34A] border-[#16A34A]/20', lost: 'bg-[#FEE2E2] text-[#DC2626] border-[#DC2626]/20', proposal_sent: 'bg-[#FEF3C7] text-[#D97706] border-[#D97706]/20', negotiation: 'bg-[#FEF3C7] text-[#D97706] border-[#D97706]/20' };
    return `px-2 py-0.5 text-xs font-semibold uppercase tracking-wider rounded border ${s[status] || s.new}`;
  };

  return (
    <div data-testid="dashboard-page" className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-extrabold text-[#1A0A2E] tracking-tight" style={{ fontFamily: 'Plus Jakarta Sans' }}>Dashboard</h1>
          <p className="text-sm text-[#5A4A7A] mt-1">Growth pipeline overview</p>
        </div>
        <button onClick={() => navigate('/leads')} data-testid="view-all-leads-btn" className="flex items-center gap-2 btn-gradient px-4 py-2 rounded-lg text-sm font-semibold" style={{ fontFamily: 'Plus Jakarta Sans' }}>
          View All Leads <ArrowRight size={16} />
        </button>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Total Leads', value: analytics?.total_leads || 0, icon: Users, color: '#7C35DC', sub: 'Active pipeline', subColor: '#16A34A' },
          { label: 'Hot Leads', value: analytics?.icp_distribution?.hot || 0, icon: Fire, color: '#C044E0', sub: 'ICP Score 70+', subColor: '#D97706' },
          { label: 'Won Deals', value: analytics?.status_distribution?.won || 0, icon: Target, color: '#16A34A', sub: 'Closed successfully', subColor: '#16A34A' },
          { label: 'Qualified', value: analytics?.status_distribution?.qualified || 0, icon: Lightning, color: '#A855F7', sub: 'Ready for outreach', subColor: '#7C35DC' },
        ].map(kpi => (
          <div key={kpi.label} className="bg-white border border-[#E8E0F5] rounded-xl p-6 hover:shadow-[var(--shadow-hover)] transition-all" style={{ boxShadow: 'var(--shadow-card)' }} data-testid={`kpi-${kpi.label.toLowerCase().replace(' ','-')}`}>
            <div className="flex items-center justify-between mb-4">
              <span className="text-xs font-semibold uppercase tracking-[0.15em] text-[#9B8AB0]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{kpi.label}</span>
              <kpi.icon size={20} style={{ color: kpi.color }} weight="duotone" />
            </div>
            <div className="text-3xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{kpi.value}</div>
            <div className="text-xs mt-1 flex items-center gap-1" style={{ color: kpi.subColor }}>
              <TrendUp size={12} /> {kpi.sub}
            </div>
          </div>
        ))}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-white border border-[#E8E0F5] rounded-xl p-6" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="chart-channels">
          <h3 className="text-lg font-bold text-[#1A0A2E] mb-4" style={{ fontFamily: 'Plus Jakarta Sans' }}>Leads by Channel</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={channelData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E8E0F5" />
              <XAxis dataKey="name" tick={{ fill: '#9B8AB0', fontSize: 12 }} />
              <YAxis tick={{ fill: '#9B8AB0', fontSize: 12 }} />
              <Tooltip contentStyle={{ background: '#fff', border: '1px solid #E8E0F5', borderRadius: '12px', color: '#1A0A2E', boxShadow: 'var(--shadow-card)' }} />
              <Bar dataKey="value" fill="#7C35DC" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white border border-[#E8E0F5] rounded-xl p-6" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="chart-lead-type">
          <h3 className="text-lg font-bold text-[#1A0A2E] mb-4" style={{ fontFamily: 'Plus Jakarta Sans' }}>B2B vs B2C</h3>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={typeData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                {typeData.map((e, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
              </Pie>
              <Tooltip contentStyle={{ background: '#fff', border: '1px solid #E8E0F5', borderRadius: '12px', color: '#1A0A2E' }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="mt-4 space-y-2">
            <h4 className="text-xs font-semibold uppercase tracking-[0.15em] text-[#9B8AB0]" style={{ fontFamily: 'Plus Jakarta Sans' }}>ICP Distribution</h4>
            {icpData.map(item => (
              <div key={item.name} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded" style={{ backgroundColor: item.color }}></div>
                  <span className="text-sm text-[#5A4A7A]">{item.name}</span>
                </div>
                <span className="text-sm font-semibold text-[#1A0A2E]">{item.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Recent Leads */}
      <div className="bg-white border border-[#E8E0F5] rounded-xl" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="recent-leads-table">
        <div className="p-6 border-b border-[#E8E0F5] flex items-center justify-between">
          <h3 className="text-lg font-bold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Recent Leads</h3>
          <button onClick={() => navigate('/leads')} className="text-sm text-[#7C35DC] hover:text-[#6B28C8] font-semibold">View all</button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead>
              <tr className="bg-[#F4F0FF]">
                {['Name', 'Email', 'Type', 'Status', 'ICP', 'Channel'].map(h => (
                  <th key={h} className="px-6 py-3 text-xs font-semibold uppercase tracking-[0.15em] text-[#5A4A7A]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {recentLeads.map(lead => (
                <tr key={lead.id} className="border-b border-[#F0ECF9] hover:bg-[#F9F5FF] cursor-pointer transition-colors" onClick={() => navigate(`/leads/${lead.id}`)} data-testid={`lead-row-${lead.id}`}>
                  <td className="px-6 py-4 font-semibold text-[#1A0A2E]">{lead.first_name} {lead.last_name}</td>
                  <td className="px-6 py-4 text-[#5A4A7A] font-mono text-xs">{lead.email}</td>
                  <td className="px-6 py-4"><span className={`px-2 py-0.5 text-xs font-semibold rounded border ${lead.lead_type === 'B2B' ? 'bg-[#F4F0FF] text-[#7C35DC] border-[#7C35DC]/20' : 'bg-[#DCFCE7] text-[#16A34A] border-[#16A34A]/20'}`}>{lead.lead_type}</span></td>
                  <td className="px-6 py-4"><span className={statusBadge(lead.status)}>{lead.status}</span></td>
                  <td className="px-6 py-4"><span className={tierBadge(lead.icp_tier)}>{lead.icp_tier}</span></td>
                  <td className="px-6 py-4 text-[#5A4A7A]">{lead.source_channel}</td>
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
