import React, { useState, useEffect, useRef } from 'react';
import api from '../config/api';
import { Robot, PaperPlaneRight, Lightning, ArrowsClockwise, HandPalm, Play, Sparkle } from '@phosphor-icons/react';

const AriaConversationPanel = ({ leadId, leadName }) => {
  const [conversation, setConversation] = useState([]);
  const [ariaState, setAriaState] = useState('PENDING_FIRST_TOUCH');
  const [handedOff, setHandedOff] = useState(false);
  const [replyText, setReplyText] = useState('');
  const [loading, setLoading] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => { fetchConversation(); }, [leadId]);
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior:'smooth' }); }, [conversation]);

  const fetchConversation = async () => {
    try {
      const res = await api.get(`/api/aria/conversation/${leadId}`);
      setConversation(res.data.conversation || []);
      setAriaState(res.data.aria_state || 'PENDING_FIRST_TOUCH');
      setHandedOff(res.data.handed_off || false);
    } catch(err) { console.error(err); }
  };

  const triggerAria = async (touchType) => {
    setTriggering(true);
    try { await api.post('/api/aria/trigger', { lead_id:leadId, touch_type:touchType }); await fetchConversation(); }
    catch(err) { console.error(err); }
    finally { setTriggering(false); }
  };

  const sendReply = async () => {
    if(!replyText.trim()) return;
    setLoading(true);
    try { await api.post('/api/aria/reply', { lead_id:leadId, message:replyText }); setReplyText(''); await fetchConversation(); }
    catch(err) { console.error(err); }
    finally { setLoading(false); }
  };

  const takeover = async () => { try { await api.post(`/api/aria/takeover/${leadId}`); await fetchConversation(); } catch(e) {} };
  const resumeAria = async () => { try { await api.post(`/api/aria/resume/${leadId}`); await fetchConversation(); } catch(e) {} };

  const stateColors = { PENDING_FIRST_TOUCH:'#9B8AB0', AWAITING_REPLY_1:'#D97706', AWAITING_REPLY_2:'#D97706', CONVERSATION_ACTIVE:'#16A34A', BOOKING_ATTEMPTED:'#7C35DC', MEETING_BOOKED:'#16A34A', DO_NOT_CONTACT:'#DC2626', ESCALATED_TO_HUMAN:'#7C35DC', SEQUENCE_ENDED:'#9B8AB0', DISQUALIFIED:'#DC2626' };

  return (
    <div className="bg-white border border-[#E8E0F5] rounded-xl overflow-hidden" style={{ boxShadow:'var(--shadow-card)' }} data-testid="aria-conversation-panel">
      <div className="p-4 border-b border-[#E8E0F5] flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background:'var(--gradient-brand)' }}>
            <Robot size={16} className="text-white" weight="fill" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-[#1A0A2E]" style={{ fontFamily:'Plus Jakarta Sans' }}>ARIA Agent</h3>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full" style={{ backgroundColor:stateColors[ariaState]||'#9B8AB0' }}></div>
              <span className="text-xs text-[#9B8AB0]">{ariaState?.replace(/_/g,' ')}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {!handedOff ? (
            <button onClick={takeover} className="flex items-center gap-1 px-3 py-1.5 bg-[#FEF3C7] text-[#D97706] border border-[#D97706]/30 rounded-lg text-xs font-medium hover:bg-[#FEF3C7]/80 transition-all" data-testid="aria-takeover-btn"><HandPalm size={14} /> Take Over</button>
          ) : (
            <button onClick={resumeAria} className="flex items-center gap-1 px-3 py-1.5 bg-[#F4F0FF] text-[#7C35DC] border border-[#7C35DC]/20 rounded-lg text-xs font-medium hover:bg-[#F4F0FF]/80 transition-all" data-testid="aria-resume-btn"><Play size={14} /> Resume ARIA</button>
          )}
        </div>
      </div>

      <div className="h-80 overflow-y-auto p-4 space-y-3 scrollbar-hide bg-[#FAFAFA]" data-testid="aria-messages">
        {conversation.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <Robot size={32} className="text-[#7C35DC] mb-3" weight="duotone" />
            <p className="text-sm text-[#9B8AB0]">No conversation yet</p>
            <button onClick={() => triggerAria('first_touch')} disabled={triggering}
              className="mt-3 flex items-center gap-2 px-4 py-2 btn-gradient rounded-lg text-sm font-semibold disabled:opacity-50"
              style={{ fontFamily:'Plus Jakarta Sans' }} data-testid="aria-first-touch-btn">
              <Sparkle size={16} weight="fill" /> {triggering ? 'Sending...' : 'Send First Touch'}
            </button>
          </div>
        ) : (
          <>
            {conversation.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === 'lead' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[80%] rounded-xl px-4 py-2.5 ${
                  msg.role === 'aria' ? 'bg-[#F4F0FF] border border-[#E0D4F7] text-[#1A0A2E]' :
                  msg.role === 'lead' ? 'bg-white border border-[#E8E0F5] text-[#1A0A2E]' :
                  'bg-[#F4F0FF] text-[#9B8AB0] border border-[#E8E0F5]'
                }`}>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-bold" style={{ color: msg.role === 'aria' ? '#7C35DC' : msg.role === 'lead' ? '#1A0A2E' : '#9B8AB0', fontFamily:'Plus Jakarta Sans' }}>
                      {msg.role === 'aria' ? 'ARIA' : msg.role === 'lead' ? leadName : 'System'}
                    </span>
                    <span className="text-xs text-[#9B8AB0]">{new Date(msg.created_at).toLocaleTimeString()}</span>
                  </div>
                  <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                  {msg.action && msg.action !== 'NONE' && (
                    <div className="mt-2 flex items-center gap-1 text-xs text-[#9B8AB0]"><Lightning size={12} /> Action: {msg.action}</div>
                  )}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      <div className="p-4 border-t border-[#E8E0F5] bg-white">
        {conversation.length > 0 && ariaState === 'AWAITING_REPLY_1' && (
          <div className="mb-3">
            <button onClick={() => triggerAria('followup')} disabled={triggering}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-[#F4F0FF] text-[#7C35DC] border border-[#7C35DC]/20 rounded-lg text-xs font-medium hover:bg-[#F4F0FF]/80 transition-all disabled:opacity-50"
              data-testid="aria-followup-btn">
              <ArrowsClockwise size={14} /> {triggering ? 'Sending...' : 'Send Follow-up'}
            </button>
          </div>
        )}
        <div className="flex items-center gap-2">
          <input type="text" value={replyText} onChange={(e) => setReplyText(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && sendReply()}
            placeholder="Simulate lead reply..."
            className="flex-1 bg-[#FAFAFA] border border-[#E8E0F5] text-[#1A0A2E] px-3 py-2 rounded-lg text-sm focus:border-[#7C35DC] focus:ring-2 focus:ring-[rgba(124,53,220,0.12)] transition-all"
            data-testid="aria-reply-input" />
          <button onClick={sendReply} disabled={loading || !replyText.trim()} className="p-2 btn-gradient rounded-lg disabled:opacity-50" data-testid="aria-send-reply-btn">
            <PaperPlaneRight size={18} />
          </button>
        </div>
      </div>
    </div>
  );
};

export default AriaConversationPanel;
