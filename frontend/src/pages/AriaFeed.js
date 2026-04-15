import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../config/api';
import { Robot, ChartLineUp, ArrowRight, Lightning, Clock, UserCircle } from '@phosphor-icons/react';

const AriaFeed = () => {
  const navigate = useNavigate();
  const [feed, setFeed] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([fetchFeed(), fetchAnalytics()]).finally(() => setLoading(false));
  }, []);

  const fetchFeed = async () => {
    try {
      const res = await api.get('/api/aria/feed');
      setFeed(res.data.feed || []);
    } catch (err) {
      console.error('Failed to fetch ARIA feed', err);
    }
  };

  const fetchAnalytics = async () => {
    try {
      const res = await api.get('/api/aria/analytics');
      setAnalytics(res.data);
    } catch (err) {
      console.error('Failed to fetch ARIA analytics', err);
    }
  };

  const stateColors = {
    PENDING_FIRST_TOUCH: { bg: 'bg-[#737373]/10', text: 'text-[#737373]', border: 'border-[#737373]/30' },
    AWAITING_REPLY_1: { bg: 'bg-[#F59E0B]/10', text: 'text-[#F59E0B]', border: 'border-[#F59E0B]/30' },
    AWAITING_REPLY_2: { bg: 'bg-[#F59E0B]/10', text: 'text-[#F59E0B]', border: 'border-[#F59E0B]/30' },
    CONVERSATION_ACTIVE: { bg: 'bg-[#10B981]/10', text: 'text-[#10B981]', border: 'border-[#10B981]/30' },
    BOOKING_ATTEMPTED: { bg: 'bg-[#0055FF]/10', text: 'text-[#0055FF]', border: 'border-[#0055FF]/30' },
    MEETING_BOOKED: { bg: 'bg-[#10B981]/10', text: 'text-[#10B981]', border: 'border-[#10B981]/30' },
    DO_NOT_CONTACT: { bg: 'bg-[#FF3B30]/10', text: 'text-[#FF3B30]', border: 'border-[#FF3B30]/30' },
    ESCALATED_TO_HUMAN: { bg: 'bg-[#8B5CF6]/10', text: 'text-[#8B5CF6]', border: 'border-[#8B5CF6]/30' },
  };

  const getStateStyle = (state) => stateColors[state] || stateColors.PENDING_FIRST_TOUCH;

  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-[#A3A3A3] font-mono text-sm">Loading ARIA feed...</div></div>;

  return (
    <div data-testid="aria-feed-page" className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: '#8B5CF6', boxShadow: 'inset 0 0 12px rgba(139,92,246,0.3)' }}>
            <Robot size={22} className="text-white" weight="fill" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-white tracking-tight">ARIA Agent</h1>
            <p className="text-sm text-[#A3A3A3] mt-0.5">Autonomous AI Sales Agent</p>
          </div>
        </div>
        <button onClick={() => navigate('/aria/analytics')} className="flex items-center gap-2 px-4 py-2 bg-transparent border border-[#262626] text-[#F5F5F5] rounded-md hover:bg-[#1E1E1E] transition-colors text-sm" data-testid="aria-analytics-link">
          <ChartLineUp size={16} /> View Analytics
        </button>
      </div>

      {/* Quick Stats */}
      {analytics && (
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          {[
            { label: 'Conversations', value: analytics.total_conversations, color: '#8B5CF6' },
            { label: 'Reply Rate', value: `${analytics.reply_rate}%`, color: '#0055FF' },
            { label: 'Qualification Rate', value: `${analytics.qualification_rate}%`, color: '#10B981' },
            { label: 'Booking Rate', value: `${analytics.booking_rate}%`, color: '#F59E0B' },
            { label: 'Meetings Booked', value: analytics.meetings_booked, color: '#10B981' },
          ].map(stat => (
            <div key={stat.label} className="bg-[#141414] border border-[#262626] rounded-lg p-4" data-testid={`aria-stat-${stat.label.toLowerCase().replace(' ', '-')}`}>
              <span className="text-xs font-semibold uppercase tracking-[0.2em] text-[#737373]">{stat.label}</span>
              <div className="text-2xl font-bold mt-1" style={{ color: stat.color }}>{stat.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Live Feed */}
      <div className="bg-[#141414] border border-[#262626] rounded-lg" data-testid="aria-live-feed">
        <div className="p-4 border-b border-[#262626] flex items-center justify-between">
          <h3 className="text-lg font-semibold text-white">Live Conversations</h3>
          <span className="text-xs text-[#737373]">{feed.length} active threads</span>
        </div>

        {feed.length === 0 ? (
          <div className="p-12 text-center">
            <Robot size={48} className="text-[#737373] mx-auto mb-4" weight="duotone" />
            <h3 className="text-lg font-semibold text-white mb-2">No active conversations</h3>
            <p className="text-sm text-[#A3A3A3]">ARIA will start conversations when new leads arrive. Go to a lead's detail page and trigger ARIA's first touch.</p>
          </div>
        ) : (
          <div className="divide-y divide-[#262626]">
            {feed.map(item => {
              const stateStyle = getStateStyle(item.aria_state);
              return (
                <div
                  key={item.lead_id}
                  className="p-4 hover:bg-[#1E1E1E] cursor-pointer transition-colors flex items-center justify-between"
                  onClick={() => navigate(`/leads/${item.lead_id}`)}
                  data-testid={`aria-feed-item-${item.lead_id}`}
                >
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 bg-[#262626] rounded-full flex items-center justify-center text-white text-sm font-medium">
                      {item.lead_name?.charAt(0) || 'L'}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-white">{item.lead_name}</span>
                        {item.company && <span className="text-xs text-[#737373]">@ {item.company}</span>}
                      </div>
                      <p className="text-xs text-[#A3A3A3] mt-0.5 max-w-md truncate">
                        {item.last_message_role === 'aria' && <span className="text-[#8B5CF6]">ARIA: </span>}
                        {item.last_message_role === 'lead' && <span className="text-[#0055FF]">Lead: </span>}
                        {item.last_message || 'No messages yet'}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={`px-2 py-0.5 text-xs font-medium uppercase tracking-wider rounded-sm border ${stateStyle.bg} ${stateStyle.text} ${stateStyle.border}`}>
                      {item.aria_state?.replace(/_/g, ' ')}
                    </span>
                    {item.handed_off && (
                      <span className="px-2 py-0.5 text-xs font-medium uppercase tracking-wider rounded-sm border bg-[#F59E0B]/10 text-[#F59E0B] border-[#F59E0B]/30">
                        Human
                      </span>
                    )}
                    <ArrowRight size={16} className="text-[#737373]" />
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
