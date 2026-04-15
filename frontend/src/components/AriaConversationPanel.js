import React, { useState, useEffect, useRef } from 'react';
import api from '../config/api';
import { Robot, PaperPlaneRight, Lightning, UserCircle, ArrowsClockwise, HandPalm, Play, Sparkle } from '@phosphor-icons/react';

const AriaConversationPanel = ({ leadId, leadName }) => {
  const [conversation, setConversation] = useState([]);
  const [ariaState, setAriaState] = useState('PENDING_FIRST_TOUCH');
  const [handedOff, setHandedOff] = useState(false);
  const [replyText, setReplyText] = useState('');
  const [loading, setLoading] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => { fetchConversation(); }, [leadId]);
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [conversation]);

  const fetchConversation = async () => {
    try {
      const res = await api.get(`/api/aria/conversation/${leadId}`);
      setConversation(res.data.conversation || []);
      setAriaState(res.data.aria_state || 'PENDING_FIRST_TOUCH');
      setHandedOff(res.data.handed_off || false);
    } catch (err) {
      console.error('Failed to fetch conversation', err);
    }
  };

  const triggerAria = async (touchType) => {
    setTriggering(true);
    try {
      await api.post('/api/aria/trigger', { lead_id: leadId, touch_type: touchType });
      await fetchConversation();
    } catch (err) {
      console.error('ARIA trigger failed', err);
    } finally {
      setTriggering(false);
    }
  };

  const sendReply = async () => {
    if (!replyText.trim()) return;
    setLoading(true);
    try {
      await api.post('/api/aria/reply', { lead_id: leadId, message: replyText });
      setReplyText('');
      await fetchConversation();
    } catch (err) {
      console.error('Reply failed', err);
    } finally {
      setLoading(false);
    }
  };

  const takeover = async () => {
    try {
      await api.post(`/api/aria/takeover/${leadId}`);
      await fetchConversation();
    } catch (err) {
      console.error('Takeover failed', err);
    }
  };

  const resumeAria = async () => {
    try {
      await api.post(`/api/aria/resume/${leadId}`);
      await fetchConversation();
    } catch (err) {
      console.error('Resume failed', err);
    }
  };

  const stateColors = {
    PENDING_FIRST_TOUCH: '#737373',
    AWAITING_REPLY_1: '#F59E0B',
    AWAITING_REPLY_2: '#F59E0B',
    CONVERSATION_ACTIVE: '#10B981',
    BOOKING_ATTEMPTED: '#0055FF',
    MEETING_BOOKED: '#10B981',
    SEQUENCE_ENDED: '#737373',
    DO_NOT_CONTACT: '#FF3B30',
    ESCALATED_TO_HUMAN: '#8B5CF6',
    DISQUALIFIED: '#FF3B30',
  };

  return (
    <div className="bg-[#141414] border border-[#262626] rounded-lg overflow-hidden" data-testid="aria-conversation-panel">
      {/* Header */}
      <div className="p-4 border-b border-[#262626] flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full flex items-center justify-center" style={{ background: '#8B5CF6', boxShadow: 'inset 0 0 12px rgba(139,92,246,0.3)' }}>
            <Robot size={16} className="text-white" weight="fill" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">ARIA Agent</h3>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full" style={{ backgroundColor: stateColors[ariaState] || '#737373' }}></div>
              <span className="text-xs text-[#737373]">{ariaState?.replace(/_/g, ' ')}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {!handedOff ? (
            <button onClick={takeover} className="flex items-center gap-1 px-3 py-1.5 bg-[#F59E0B]/10 text-[#F59E0B] border border-[#F59E0B]/30 rounded-md text-xs hover:bg-[#F59E0B]/20 transition-colors" data-testid="aria-takeover-btn">
              <HandPalm size={14} /> Take Over
            </button>
          ) : (
            <button onClick={resumeAria} className="flex items-center gap-1 px-3 py-1.5 bg-[#8B5CF6]/10 text-[#8B5CF6] border border-[#8B5CF6]/30 rounded-md text-xs hover:bg-[#8B5CF6]/20 transition-colors" data-testid="aria-resume-btn">
              <Play size={14} /> Resume ARIA
            </button>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="h-80 overflow-y-auto p-4 space-y-3 scrollbar-hide" data-testid="aria-messages">
        {conversation.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <Robot size={32} className="text-[#8B5CF6] mb-3" weight="duotone" />
            <p className="text-sm text-[#737373]">No conversation yet</p>
            <button
              onClick={() => triggerAria('first_touch')}
              disabled={triggering}
              className="mt-3 flex items-center gap-2 px-4 py-2 bg-[#8B5CF6]/10 text-[#8B5CF6] border border-[#8B5CF6]/30 rounded-md text-sm hover:bg-[#8B5CF6]/20 transition-colors disabled:opacity-50"
              data-testid="aria-first-touch-btn"
            >
              <Sparkle size={16} weight="fill" />
              {triggering ? 'Sending...' : 'Send First Touch'}
            </button>
          </div>
        ) : (
          <>
            {conversation.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === 'lead' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[80%] rounded-lg px-4 py-2.5 ${
                  msg.role === 'aria'
                    ? 'bg-[#8B5CF6]/10 border border-[#8B5CF6]/20 text-[#F5F5F5]'
                    : msg.role === 'lead'
                    ? 'bg-[#0055FF]/10 border border-[#0055FF]/20 text-[#F5F5F5]'
                    : 'bg-[#262626] text-[#737373] border border-[#262626]'
                }`}>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-medium" style={{ color: msg.role === 'aria' ? '#8B5CF6' : msg.role === 'lead' ? '#0055FF' : '#737373' }}>
                      {msg.role === 'aria' ? 'ARIA' : msg.role === 'lead' ? leadName : 'System'}
                    </span>
                    <span className="text-xs text-[#737373]">{new Date(msg.created_at).toLocaleTimeString()}</span>
                  </div>
                  <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                  {msg.action && msg.action !== 'NONE' && (
                    <div className="mt-2 flex items-center gap-1 text-xs text-[#737373]">
                      <Lightning size={12} /> Action: {msg.action}
                    </div>
                  )}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input / Actions */}
      <div className="p-4 border-t border-[#262626]">
        {conversation.length > 0 && ariaState !== 'DO_NOT_CONTACT' && ariaState !== 'MEETING_BOOKED' && (
          <div className="flex items-center gap-2 mb-3">
            {ariaState === 'AWAITING_REPLY_1' && (
              <button
                onClick={() => triggerAria('followup')}
                disabled={triggering}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-[#8B5CF6]/10 text-[#8B5CF6] border border-[#8B5CF6]/30 rounded-md text-xs hover:bg-[#8B5CF6]/20 transition-colors disabled:opacity-50"
                data-testid="aria-followup-btn"
              >
                <ArrowsClockwise size={14} /> {triggering ? 'Sending...' : 'Send Follow-up'}
              </button>
            )}
          </div>
        )}

        {/* Simulate lead reply input */}
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={replyText}
            onChange={(e) => setReplyText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && sendReply()}
            placeholder="Simulate lead reply..."
            className="flex-1 bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2 rounded-md text-sm focus:border-[#0055FF] focus:ring-1 focus:ring-[#0055FF] transition-all"
            data-testid="aria-reply-input"
          />
          <button
            onClick={sendReply}
            disabled={loading || !replyText.trim()}
            className="p-2 bg-[#0055FF] text-white rounded-md hover:bg-[#0044CC] transition-colors disabled:opacity-50"
            data-testid="aria-send-reply-btn"
          >
            <PaperPlaneRight size={18} />
          </button>
        </div>
      </div>
    </div>
  );
};

export default AriaConversationPanel;
