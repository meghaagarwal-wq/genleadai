import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../config/api';
import { Robot, ChartLineUp, ArrowRight } from '@phosphor-icons/react';

const AriaFeed = () => {
  const navigate = useNavigate();
  const [feed, setFeed] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { Promise.all([fetchFeed(), fetchAnalytics()]).finally(() => setLoading(false)); }, []);
  const fetchFeed = async () => { try { const res = await api.get('/api/aria/feed'); setFeed(res.data.feed||[]); } catch(e) {} };
  const fetchAnalytics = async () => { try { const res = await api.get('/api/aria/analytics'); setAnalytics(res.data); } catch(e) {} };

  const stateStyles = {
    PENDING_FIRST_TOUCH: { bg:'bg-[#F1F5F9]', text:'text-[#64748B]', border:'border-[#94A3B8]/30' },
    AWAITING_REPLY_1: { bg:'bg-[#FEF3C7]', text:'text-[#D97706]', border:'border-[#D97706]/30' },
    AWAITING_REPLY_2: { bg:'bg-[#FEF3C7]', text:'text-[#D97706]', border:'border-[#D97706]/30' },
    CONVERSATION_ACTIVE: { bg:'bg-[#DCFCE7]', text:'text-[#16A34A]', border:'border-[#16A34A]/30' },
    BOOKING_ATTEMPTED: { bg:'bg-[#F4F0FF]', text:'text-[#7C35DC]', border:'border-[#7C35DC]/20' },
    MEETING_BOOKED: { bg:'bg-[#DCFCE7]', text:'text-[#16A34A]', border:'border-[#16A34A]/30' },
    DO_NOT_CONTACT: { bg:'bg-[#FEE2E2]', text:'text-[#DC2626]', border:'border-[#DC2626]/30' },
    ESCALATED_TO_HUMAN: { bg:'bg-[#F4F0FF]', text:'text-[#7C35DC]', border:'border-[#7C35DC]/20' },
  };
  const getStyle = (s) => stateStyles[s] || stateStyles.PENDING_FIRST_TOUCH;

  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-[#9B8AB0] text-sm">Loading ARIA feed...</div></div>;

  return (
    <div data-testid="aria-feed-page" className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background:'var(--gradient-brand)' }}>
            <Robot size={22} className="text-white" weight="fill" />
          </div>
          <div>
            <h1 className="text-3xl font-extrabold text-[#1A0A2E] tracking-tight" style={{ fontFamily:'Plus Jakarta Sans' }}>ARIA Agent</h1>
            <p className="text-sm text-[#5A4A7A] mt-0.5">Autonomous AI Sales Agent</p>
          </div>
        </div>
        <button onClick={() => navigate('/aria/analytics')} className="flex items-center gap-2 px-4 py-2 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-lg hover:bg-[#F9F5FF] hover:text-[#7C35DC] transition-all text-sm font-medium" style={{ fontFamily:'Plus Jakarta Sans' }} data-testid="aria-analytics-link">
          <ChartLineUp size={16} /> View Analytics
        </button>
      </div>

      {analytics && (
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          {[
            { label:'Conversations', value:analytics.total_conversations, color:'#7C35DC' },
            { label:'Reply Rate', value:`${analytics.reply_rate}%`, color:'#C044E0' },
            { label:'Qualification', value:`${analytics.qualification_rate}%`, color:'#16A34A' },
            { label:'Booking Rate', value:`${analytics.booking_rate}%`, color:'#D97706' },
            { label:'Meetings', value:analytics.meetings_booked, color:'#16A34A' },
          ].map(stat => (
            <div key={stat.label} className="bg-white border border-[#E8E0F5] rounded-xl p-4" style={{ boxShadow:'var(--shadow-card)' }} data-testid={`aria-stat-${stat.label.toLowerCase().replace(' ','-')}`}>
              <span className="text-xs font-semibold uppercase tracking-[0.15em] text-[#9B8AB0]" style={{ fontFamily:'Plus Jakarta Sans' }}>{stat.label}</span>
              <div className="text-2xl font-extrabold mt-1" style={{ color:stat.color, fontFamily:'Plus Jakarta Sans' }}>{stat.value}</div>
            </div>
          ))}
        </div>
      )}

      <div className="bg-white border border-[#E8E0F5] rounded-xl" style={{ boxShadow:'var(--shadow-card)' }} data-testid="aria-live-feed">
        <div className="p-4 border-b border-[#E8E0F5] flex items-center justify-between">
          <h3 className="text-lg font-bold text-[#1A0A2E]" style={{ fontFamily:'Plus Jakarta Sans' }}>Live Conversations</h3>
          <span className="text-xs text-[#9B8AB0]">{feed.length} active threads</span>
        </div>
        {feed.length === 0 ? (
          <div className="p-12 text-center">
            <Robot size={48} className="text-[#9B8AB0] mx-auto mb-4" weight="duotone" />
            <h3 className="text-lg font-bold text-[#1A0A2E] mb-2" style={{ fontFamily:'Plus Jakarta Sans' }}>No active conversations</h3>
            <p className="text-sm text-[#5A4A7A]">Go to a lead's detail page and trigger ARIA's first touch.</p>
          </div>
        ) : (
          <div className="divide-y divide-[#F0ECF9]">
            {feed.map(item => {
              const st = getStyle(item.aria_state);
              return (
                <div key={item.lead_id} className="p-4 hover:bg-[#F9F5FF] cursor-pointer transition-all flex items-center justify-between"
                  onClick={() => navigate(`/leads/${item.lead_id}`)} data-testid={`aria-feed-item-${item.lead_id}`}>
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-full flex items-center justify-center text-white text-sm font-bold" style={{ background:'var(--gradient-brand)', fontFamily:'Plus Jakarta Sans' }}>
                      {item.lead_name?.charAt(0)||'L'}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-[#1A0A2E]">{item.lead_name}</span>
                        {item.company && <span className="text-xs text-[#9B8AB0]">@ {item.company}</span>}
                      </div>
                      <p className="text-xs text-[#5A4A7A] mt-0.5 max-w-md truncate">
                        {item.last_message_role === 'aria' && <span className="text-[#7C35DC] font-medium">ARIA: </span>}
                        {item.last_message_role === 'lead' && <span className="text-[#1A0A2E] font-medium">Lead: </span>}
                        {item.last_message||'No messages yet'}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={`px-2 py-0.5 text-xs font-semibold uppercase tracking-wider rounded border ${st.bg} ${st.text} ${st.border}`}>
                      {item.aria_state?.replace(/_/g,' ')}
                    </span>
                    {item.handed_off && <span className="px-2 py-0.5 text-xs font-semibold uppercase rounded border bg-[#FEF3C7] text-[#D97706] border-[#D97706]/30">Human</span>}
                    <ArrowRight size={16} className="text-[#9B8AB0]" />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default AriaFeed;
