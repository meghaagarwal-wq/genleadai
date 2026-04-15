import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../config/api';
import { Robot, ArrowLeft } from '@phosphor-icons/react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

const AriaAnalytics = () => {
  const navigate = useNavigate();
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { api.get('/api/aria/analytics').then(r => setAnalytics(r.data)).catch(console.error).finally(() => setLoading(false)); }, []);

  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-[#9B8AB0] text-sm">Loading analytics...</div></div>;
  if (!analytics) return null;

  const stateData = Object.entries(analytics.state_distribution||{}).map(([k,v]) => ({ name:k.replace(/_/g,' '), value:v }));
  const funnelData = [
    { stage:'Started', value:analytics.total_conversations },
    { stage:'Replied', value:analytics.total_lead_replies },
    { stage:'Qualified', value:Math.round(analytics.total_conversations*analytics.qualification_rate/100) },
    { stage:'Booked', value:analytics.meetings_booked },
  ];
  const COLORS = ['#7C35DC','#C044E0','#A855F7','#16A34A','#D97706','#94A3B8'];
  const tooltipStyle = { background:'#fff', border:'1px solid #E8E0F5', borderRadius:'12px', color:'#1A0A2E', boxShadow:'var(--shadow-card)' };

  return (
    <div data-testid="aria-analytics-page" className="space-y-6">
      <button onClick={() => navigate('/aria')} className="flex items-center gap-2 text-[#5A4A7A] hover:text-[#7C35DC] transition-colors text-sm" data-testid="back-to-aria-btn"><ArrowLeft size={16} /> Back to ARIA</button>

      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background:'var(--gradient-brand)' }}>
          <Robot size={22} className="text-white" weight="fill" />
        </div>
        <div>
          <h1 className="text-3xl font-extrabold text-[#1A0A2E] tracking-tight" style={{ fontFamily:'Plus Jakarta Sans' }}>ARIA Analytics</h1>
          <p className="text-sm text-[#5A4A7A] mt-0.5">Performance metrics and conversion analysis</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[
          { label:'Total Conversations', value:analytics.total_conversations, color:'#7C35DC', sub:`${analytics.total_aria_messages} messages sent` },
          { label:'Reply Rate', value:`${analytics.reply_rate}%`, color:'#C044E0', sub:`${analytics.total_lead_replies} replies` },
          { label:'Booking Rate', value:`${analytics.booking_rate}%`, color:'#D97706', sub:`${analytics.meetings_booked} meetings` },
          { label:'Escalations', value:analytics.escalations, color:'#DC2626', sub:`${analytics.do_not_contact} DNC` },
        ].map(kpi => (
          <div key={kpi.label} className="bg-white border border-[#E8E0F5] rounded-xl p-6" style={{ boxShadow:'var(--shadow-card)' }} data-testid={`aria-kpi-${kpi.label.toLowerCase().replace(' ','-')}`}>
            <span className="text-xs font-semibold uppercase tracking-[0.15em] text-[#9B8AB0]" style={{ fontFamily:'Plus Jakarta Sans' }}>{kpi.label}</span>
            <div className="text-3xl font-extrabold mt-2" style={{ color:kpi.color, fontFamily:'Plus Jakarta Sans' }}>{kpi.value}</div>
            <div className="text-xs text-[#9B8AB0] mt-1">{kpi.sub}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white border border-[#E8E0F5] rounded-xl p-6" style={{ boxShadow:'var(--shadow-card)' }} data-testid="aria-chart-funnel">
          <h3 className="text-lg font-bold text-[#1A0A2E] mb-4" style={{ fontFamily:'Plus Jakarta Sans' }}>Conversion Funnel</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={funnelData}><CartesianGrid strokeDasharray="3 3" stroke="#E8E0F5" /><XAxis dataKey="stage" tick={{ fill:'#9B8AB0', fontSize:12 }} /><YAxis tick={{ fill:'#9B8AB0', fontSize:12 }} /><Tooltip contentStyle={tooltipStyle} /><Bar dataKey="value" fill="#7C35DC" radius={[6,6,0,0]} /></BarChart>
          </ResponsiveContainer>
        </div>
        <div className="bg-white border border-[#E8E0F5] rounded-xl p-6" style={{ boxShadow:'var(--shadow-card)' }} data-testid="aria-chart-states">
          <h3 className="text-lg font-bold text-[#1A0A2E] mb-4" style={{ fontFamily:'Plus Jakarta Sans' }}>Thread State Distribution</h3>
          {stateData.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <PieChart><Pie data={stateData} cx="50%" cy="50%" innerRadius={60} outerRadius={90} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>{stateData.map((e,i) => <Cell key={i} fill={COLORS[i%COLORS.length]} />)}</Pie><Tooltip contentStyle={tooltipStyle} /></PieChart>
            </ResponsiveContainer>
          ) : <div className="flex items-center justify-center h-64 text-[#9B8AB0]">No data yet</div>}
        </div>
      </div>
    </div>
  );
};

export default AriaAnalytics;
