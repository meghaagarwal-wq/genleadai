import React, { useState, useEffect } from 'react';
import api from '../config/api';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, AreaChart, Area } from 'recharts';
import { ChartBar, TrendUp, Users, Target } from '@phosphor-icons/react';

const Analytics = () => {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => { api.get('/api/analytics/dashboard').then(r => setAnalytics(r.data)).catch(console.error).finally(() => setLoading(false)); }, []);

  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-[#9B8AB0] text-sm">Loading analytics...</div></div>;
  if (!analytics) return null;

  const channelData = Object.entries(analytics.channel_distribution).filter(([,v]) => v>0).map(([k,v]) => ({ name:k.replace('_',' '), value:v })).sort((a,b) => b.value-a.value);
  const statusData = Object.entries(analytics.status_distribution).filter(([,v]) => v>0).map(([k,v]) => ({ name:k.replace('_',' '), value:v }));
  const typeData = [{ name:'B2B', value:analytics.lead_type_distribution.B2B }, { name:'B2C', value:analytics.lead_type_distribution.B2C }];
  const icpData = [{ name:'Hot', value:analytics.icp_distribution.hot }, { name:'Warm', value:analytics.icp_distribution.warm }, { name:'Cold', value:analytics.icp_distribution.cold }];
  const funnelData = [{ stage:'New', value:analytics.status_distribution.new||0 }, { stage:'Contacted', value:analytics.status_distribution.contacted||0 }, { stage:'Qualified', value:analytics.status_distribution.qualified||0 }, { stage:'Proposal', value:analytics.status_distribution.proposal_sent||0 }, { stage:'Won', value:analytics.status_distribution.won||0 }];
  const COLORS = ['#7C35DC','#C044E0','#A855F7','#D97706','#DC2626'];
  const ICP_COLORS = ['#7C35DC','#D97706','#94A3B8'];
  const tooltipStyle = { background:'#fff', border:'1px solid #E8E0F5', borderRadius:'12px', color:'#1A0A2E', boxShadow:'var(--shadow-card)' };

  return (
    <div data-testid="analytics-page" className="space-y-6">
      <div>
        <h1 className="text-3xl font-extrabold text-[#1A0A2E] tracking-tight" style={{ fontFamily:'Plus Jakarta Sans' }}>Analytics</h1>
        <p className="text-sm text-[#5A4A7A] mt-1">Performance metrics and insights</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[
          { label:'Total Leads', value:analytics.total_leads, icon:Users, color:'#7C35DC' },
          { label:'Qualified', value:analytics.status_distribution.qualified||0, icon:Target, color:'#16A34A' },
          { label:'Won', value:analytics.status_distribution.won||0, icon:TrendUp, color:'#D97706' },
          { label:'Conversion', value:`${analytics.total_leads>0?Math.round(((analytics.status_distribution.won||0)/analytics.total_leads)*100):0}%`, icon:ChartBar, color:'#7C35DC' },
        ].map(kpi => (
          <div key={kpi.label} className="bg-white border border-[#E8E0F5] rounded-xl p-6" style={{ boxShadow:'var(--shadow-card)' }} data-testid={`analytics-${kpi.label.toLowerCase()}`}>
            <div className="flex items-center gap-2 mb-2"><kpi.icon size={16} style={{ color:kpi.color }} weight="duotone" /><span className="text-xs font-semibold uppercase tracking-[0.15em] text-[#9B8AB0]" style={{ fontFamily:'Plus Jakarta Sans' }}>{kpi.label}</span></div>
            <div className="text-3xl font-extrabold" style={{ color:kpi.color, fontFamily:'Plus Jakarta Sans' }}>{kpi.value}</div>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white border border-[#E8E0F5] rounded-xl p-6" style={{ boxShadow:'var(--shadow-card)' }} data-testid="chart-channel-dist">
          <h3 className="text-lg font-bold text-[#1A0A2E] mb-4" style={{ fontFamily:'Plus Jakarta Sans' }}>Leads by Channel</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={channelData} layout="vertical"><CartesianGrid strokeDasharray="3 3" stroke="#E8E0F5" /><XAxis type="number" tick={{ fill:'#9B8AB0', fontSize:12 }} /><YAxis type="category" dataKey="name" tick={{ fill:'#5A4A7A', fontSize:11 }} width={100} /><Tooltip contentStyle={tooltipStyle} /><Bar dataKey="value" fill="#7C35DC" radius={[0,6,6,0]} /></BarChart>
          </ResponsiveContainer>
        </div>
        <div className="bg-white border border-[#E8E0F5] rounded-xl p-6" style={{ boxShadow:'var(--shadow-card)' }} data-testid="chart-funnel">
          <h3 className="text-lg font-bold text-[#1A0A2E] mb-4" style={{ fontFamily:'Plus Jakarta Sans' }}>Conversion Funnel</h3>
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={funnelData}><CartesianGrid strokeDasharray="3 3" stroke="#E8E0F5" /><XAxis dataKey="stage" tick={{ fill:'#9B8AB0', fontSize:12 }} /><YAxis tick={{ fill:'#9B8AB0', fontSize:12 }} /><Tooltip contentStyle={tooltipStyle} /><Area type="monotone" dataKey="value" stroke="#7C35DC" fill="rgba(124,53,220,0.1)" strokeWidth={2} /></AreaChart>
          </ResponsiveContainer>
        </div>
        <div className="bg-white border border-[#E8E0F5] rounded-xl p-6" style={{ boxShadow:'var(--shadow-card)' }} data-testid="chart-type-dist">
          <h3 className="text-lg font-bold text-[#1A0A2E] mb-4" style={{ fontFamily:'Plus Jakarta Sans' }}>B2B vs B2C</h3>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart><Pie data={typeData} cx="50%" cy="50%" innerRadius={60} outerRadius={90} dataKey="value" label={({ name, percent }) => `${name} ${(percent*100).toFixed(0)}%`}>{typeData.map((e,i) => <Cell key={i} fill={['#7C35DC','#16A34A'][i]} />)}</Pie><Tooltip contentStyle={tooltipStyle} /></PieChart>
          </ResponsiveContainer>
        </div>
        <div className="bg-white border border-[#E8E0F5] rounded-xl p-6" style={{ boxShadow:'var(--shadow-card)' }} data-testid="chart-icp-dist">
          <h3 className="text-lg font-bold text-[#1A0A2E] mb-4" style={{ fontFamily:'Plus Jakarta Sans' }}>ICP Tier Distribution</h3>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart><Pie data={icpData} cx="50%" cy="50%" innerRadius={60} outerRadius={90} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>{icpData.map((e,i) => <Cell key={i} fill={ICP_COLORS[i]} />)}</Pie><Tooltip contentStyle={tooltipStyle} /></PieChart>
          </ResponsiveContainer>
        </div>
        <div className="lg:col-span-2 bg-white border border-[#E8E0F5] rounded-xl p-6" style={{ boxShadow:'var(--shadow-card)' }} data-testid="chart-status-dist">
          <h3 className="text-lg font-bold text-[#1A0A2E] mb-4" style={{ fontFamily:'Plus Jakarta Sans' }}>Status Distribution</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={statusData}><CartesianGrid strokeDasharray="3 3" stroke="#E8E0F5" /><XAxis dataKey="name" tick={{ fill:'#9B8AB0', fontSize:12 }} /><YAxis tick={{ fill:'#9B8AB0', fontSize:12 }} /><Tooltip contentStyle={tooltipStyle} /><Bar dataKey="value" radius={[6,6,0,0]}>{statusData.map((e,i) => <Cell key={i} fill={COLORS[i%COLORS.length]} />)}</Bar></BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};

export default Analytics;
