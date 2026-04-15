import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../config/api';
import { Robot, ArrowLeft } from '@phosphor-icons/react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

const AriaAnalytics = () => {
  const navigate = useNavigate();
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { fetchAnalytics(); }, []);

  const fetchAnalytics = async () => {
    try {
      const res = await api.get('/api/aria/analytics');
      setAnalytics(res.data);
    } catch (err) {
      console.error('Failed to fetch ARIA analytics', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-[#A3A3A3] font-mono text-sm">Loading analytics...</div></div>;
  if (!analytics) return null;

  const stateData = Object.entries(analytics.state_distribution || {}).map(([key, value]) => ({
    name: key.replace(/_/g, ' '),
    value
  }));

  const funnelData = [
    { stage: 'Started', value: analytics.total_conversations },
    { stage: 'Replied', value: analytics.total_lead_replies },
    { stage: 'Qualified', value: Math.round(analytics.total_conversations * analytics.qualification_rate / 100) },
    { stage: 'Booked', value: analytics.meetings_booked },
  ];

  const COLORS = ['#8B5CF6', '#0055FF', '#10B981', '#F59E0B', '#FF3B30', '#737373'];

  return (
    <div data-testid="aria-analytics-page" className="space-y-6">
      <button onClick={() => navigate('/aria')} className="flex items-center gap-2 text-[#A3A3A3] hover:text-white transition-colors text-sm" data-testid="back-to-aria-btn">
        <ArrowLeft size={16} /> Back to ARIA
      </button>

      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: '#8B5CF6', boxShadow: 'inset 0 0 12px rgba(139,92,246,0.3)' }}>
          <Robot size={22} className="text-white" weight="fill" />
        </div>
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight">ARIA Analytics</h1>
          <p className="text-sm text-[#A3A3A3] mt-0.5">Performance metrics and conversion analysis</p>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-[#141414] border border-[#262626] rounded-lg p-6" data-testid="aria-kpi-conversations">
          <span className="text-xs font-semibold uppercase tracking-[0.2em] text-[#737373]">Total Conversations</span>
          <div className="text-3xl font-bold text-[#8B5CF6] mt-2">{analytics.total_conversations}</div>
          <div className="text-xs text-[#737373] mt-1">{analytics.total_aria_messages} ARIA messages sent</div>
        </div>
        <div className="bg-[#141414] border border-[#262626] rounded-lg p-6" data-testid="aria-kpi-reply-rate">
          <span className="text-xs font-semibold uppercase tracking-[0.2em] text-[#737373]">Reply Rate</span>
          <div className="text-3xl font-bold text-[#0055FF] mt-2">{analytics.reply_rate}%</div>
          <div className="text-xs text-[#737373] mt-1">{analytics.total_lead_replies} lead replies</div>
        </div>
        <div className="bg-[#141414] border border-[#262626] rounded-lg p-6" data-testid="aria-kpi-booking-rate">
          <span className="text-xs font-semibold uppercase tracking-[0.2em] text-[#737373]">Booking Rate</span>
          <div className="text-3xl font-bold text-[#F59E0B] mt-2">{analytics.booking_rate}%</div>
          <div className="text-xs text-[#737373] mt-1">{analytics.meetings_booked} meetings booked</div>
        </div>
        <div className="bg-[#141414] border border-[#262626] rounded-lg p-6" data-testid="aria-kpi-escalations">
          <span className="text-xs font-semibold uppercase tracking-[0.2em] text-[#737373]">Escalations</span>
          <div className="text-3xl font-bold text-[#FF3B30] mt-2">{analytics.escalations}</div>
          <div className="text-xs text-[#737373] mt-1">{analytics.do_not_contact} marked DNC</div>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Conversion Funnel */}
        <div className="bg-[#141414] border border-[#262626] rounded-lg p-6" data-testid="aria-chart-funnel">
          <h3 className="text-lg font-semibold text-white mb-4">Conversion Funnel</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={funnelData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
              <XAxis dataKey="stage" tick={{ fill: '#737373', fontSize: 12 }} />
              <YAxis tick={{ fill: '#737373', fontSize: 12 }} />
              <Tooltip contentStyle={{ background: '#141414', border: '1px solid #262626', borderRadius: '8px', color: '#F5F5F5' }} />
              <Bar dataKey="value" fill="#8B5CF6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* State Distribution */}
        <div className="bg-[#141414] border border-[#262626] rounded-lg p-6" data-testid="aria-chart-states">
          <h3 className="text-lg font-semibold text-white mb-4">Thread State Distribution</h3>
          {stateData.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie data={stateData} cx="50%" cy="50%" innerRadius={60} outerRadius={90} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                  {stateData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ background: '#141414', border: '1px solid #262626', borderRadius: '8px', color: '#F5F5F5' }} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-64 text-[#737373]">No data yet</div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AriaAnalytics;
