import React, { useState, useEffect, useRef } from 'react';
import api from '../config/api';
import { Robot, PaperPlaneRight, Lightning, ArrowsClockwise, HandPalm, Play, Sparkle, Phone, Microphone, PaperPlaneTilt, Notepad, CheckCircle } from '@phosphor-icons/react';

const AriaConversationPanel = ({ leadId, leadName }) => {
  const [conversation, setConversation] = useState([]);
  const [ariaState, setAriaState] = useState('PENDING_FIRST_TOUCH');
  const [handedOff, setHandedOff] = useState(false);
  const [phaseInfo, setPhaseInfo] = useState(null);
  const [replyText, setReplyText] = useState('');
  const [instructionText, setInstructionText] = useState('');
  const [showInstruction, setShowInstruction] = useState(false);
  const [loading, setLoading] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => { fetchAll(); }, [leadId]);
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [conversation]);

  const fetchAll = async () => {
    try {
      const [convoRes, phaseRes] = await Promise.all([
        api.get(`/api/aria/conversation/${leadId}`),
        api.get(`/api/aria/lead-phase/${leadId}`)
      ]);
      setConversation(convoRes.data.conversation || []);
      setAriaState(convoRes.data.aria_state || 'PENDING_FIRST_TOUCH');
      setHandedOff(convoRes.data.handed_off || false);
      setPhaseInfo(phaseRes.data);
    } catch (err) { console.error(err); }
  };

  const triggerAria = async (touchType) => {
    setTriggering(true);
    try { await api.post('/api/aria/trigger', { lead_id: leadId, touch_type: touchType }); await fetchAll(); }
    catch (err) { console.error(err); } finally { setTriggering(false); }
  };

  const sendReply = async () => {
    if (!replyText.trim()) return;
    setLoading(true);
    try { await api.post('/api/aria/reply', { lead_id: leadId, message: replyText }); setReplyText(''); await fetchAll(); }
    catch (err) { console.error(err); } finally { setLoading(false); }
  };

  const takeover = async () => { try { await api.post(`/api/aria/takeover/${leadId}`); await fetchAll(); } catch (e) {} };
  const resumeAria = async () => { try { await api.post(`/api/aria/resume/${leadId}`); await fetchAll(); } catch (e) {} };
  const pauseForCall = async () => { try { await api.post(`/api/aria/pause-for-call/${leadId}`); await fetchAll(); } catch (e) {} };

  const sendInstruction = async () => {
    if (!instructionText.trim()) return;
    try { await api.post('/api/aria/founder-instruction', { lead_id: leadId, instruction: instructionText }); setInstructionText(''); setShowInstruction(false); await fetchAll(); }
    catch (e) { console.error(e); }
  };

  const runResearch = async () => {
    setTriggering(true);
    try { await api.post('/api/aria/research', { lead_id: leadId }); await fetchAll(); }
    catch (e) { console.error(e); } finally { setTriggering(false); }
  };

  const sendBrief = async () => {
    try { await api.post(`/api/aria/pre-call-brief/${leadId}`); await fetchAll(); }
    catch (e) { console.error(e); }
  };

  const recordOutcome = async (outcome) => {
    try { await api.post('/api/aria/call-outcome', { lead_id: leadId, outcome }); await fetchAll(); }
    catch (e) { console.error(e); }
  };

  const triggerProposalFollowup = async (step) => {
    try { await api.post('/api/aria/proposal-followup', { lead_id: leadId, step }); await fetchAll(); }
    catch (e) { console.error(e); }
  };

  const markProposalSent = async () => {
    try { await api.post(`/api/aria/mark-proposal-sent/${leadId}`); await fetchAll(); }
    catch (e) { console.error(e); }
  };

  const stateColors = {
    PENDING_FIRST_TOUCH: '#9B8AB0', AWAITING_REPLY_1: '#D97706', AWAITING_REPLY_2: '#D97706',
    CONVERSATION_ACTIVE: '#16A34A', BOOKING_ATTEMPTED: '#7C35DC', MEETING_BOOKED: '#16A34A',
    ON_HOLD_DURING_CALL: '#D97706', PROPOSAL_PENDING: '#7C35DC', PROPOSAL_FOLLOW_UP: '#7C35DC',
    FOUNDER_ACTIVE: '#D97706', WAITING_FOR_CHECK_IN: '#9B8AB0',
    DO_NOT_CONTACT: '#DC2626', ESCALATED_TO_HUMAN: '#7C35DC', DISQUALIFIED: '#DC2626', SEQUENCE_ENDED: '#9B8AB0',
  };
  const phase = phaseInfo?.phase || 0;

  return (
    <div className="bg-white border border-[#E8E0F5] rounded-xl overflow-hidden" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="aria-conversation-panel">
      {/* Header */}
      <div className="p-4 border-b border-[#E8E0F5] flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'var(--gradient-brand)' }}>
            <Robot size={16} className="text-white" weight="fill" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>ARIA Sales PA</h3>
              {phase > 0 && <span className="text-xs px-1.5 py-0.5 rounded bg-[#F4F0FF] text-[#7C35DC] font-semibold border border-[#7C35DC]/10">Phase {phase}</span>}
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full" style={{ backgroundColor: stateColors[ariaState] || '#9B8AB0' }}></div>
              <span className="text-xs text-[#9B8AB0]">{ariaState?.replace(/_/g, ' ')}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {!handedOff && ariaState !== 'FOUNDER_ACTIVE' ? (
            <button onClick={takeover} className="flex items-center gap-1 px-3 py-1.5 bg-[#FEF3C7] text-[#D97706] border border-[#D97706]/30 rounded-lg text-xs font-medium hover:bg-[#FEF3C7]/80 transition-all" data-testid="aria-takeover-btn"><HandPalm size={14} /> Take Over</button>
          ) : (handedOff || ariaState === 'FOUNDER_ACTIVE') && (
            <button onClick={resumeAria} className="flex items-center gap-1 px-3 py-1.5 bg-[#F4F0FF] text-[#7C35DC] border border-[#7C35DC]/20 rounded-lg text-xs font-medium hover:bg-[#F4F0FF]/80 transition-all" data-testid="aria-resume-btn"><Play size={14} /> Hand Back to Aria</button>
          )}
          <button onClick={() => setShowInstruction(!showInstruction)} className="flex items-center gap-1 px-3 py-1.5 bg-white text-[#5A4A7A] border border-[#E8E0F5] rounded-lg text-xs font-medium hover:bg-[#F9F5FF] hover:text-[#7C35DC] transition-all" data-testid="aria-instruction-btn" title="Give Aria an instruction"><Notepad size={14} /></button>
        </div>
      </div>

      {/* Phase Banners */}
      {ariaState === 'ON_HOLD_DURING_CALL' && (
        <div className="p-4 bg-[#FEF3C7] border-b border-[#D97706]/20" data-testid="call-in-progress-banner">
          <p className="text-sm font-semibold text-[#92400E] mb-3">Call in progress — Aria is paused. How did it go?</p>
          <div className="flex flex-wrap gap-2">
            {[
              { id: 'interested', label: 'Interested', color: '#16A34A' },
              { id: 'proposal_sent', label: 'Sending Proposal', color: '#7C35DC' },
              { id: 'not_a_fit', label: 'Not a Fit', color: '#DC2626' },
              { id: 'needs_more_time', label: 'Needs More Time', color: '#D97706' },
              { id: 'rescheduled', label: 'Rescheduled', color: '#5A4A7A' },
            ].map(o => (
              <button key={o.id} onClick={() => recordOutcome(o.id)} className="px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all hover:opacity-80" style={{ color: o.color, borderColor: `${o.color}40`, background: `${o.color}10` }} data-testid={`outcome-${o.id}`}>{o.label}</button>
            ))}
          </div>
        </div>
      )}

      {ariaState === 'PROPOSAL_PENDING' && (
        <div className="p-4 bg-[#F4F0FF] border-b border-[#E0D4F7]" data-testid="proposal-pending-banner">
          <p className="text-sm text-[#7C35DC] font-semibold mb-2">Waiting for you to send the proposal</p>
          <button onClick={markProposalSent} className="btn-gradient px-4 py-1.5 rounded-lg text-xs font-semibold" data-testid="mark-proposal-sent-btn">Mark Proposal as Sent</button>
        </div>
      )}

      {ariaState === 'PROPOSAL_FOLLOW_UP' && (
        <div className="p-4 bg-[#F4F0FF] border-b border-[#E0D4F7]" data-testid="proposal-followup-banner">
          <p className="text-sm text-[#7C35DC]">Proposal follow-up <span className="font-bold">{phaseInfo?.proposal_follow_up_count || 0}/4</span> sent</p>
          <div className="flex gap-2 mt-2">
            <button onClick={() => triggerProposalFollowup((phaseInfo?.proposal_follow_up_count || 0) + 1)} className="px-3 py-1.5 bg-[#F4F0FF] text-[#7C35DC] border border-[#7C35DC]/20 rounded-lg text-xs font-medium" data-testid="send-next-followup-btn">Send Next Follow-up</button>
            <button onClick={() => recordOutcome('interested')} className="px-3 py-1.5 bg-[#DCFCE7] text-[#16A34A] border border-[#16A34A]/20 rounded-lg text-xs font-medium" data-testid="mark-won-btn"><CheckCircle size={14} className="inline mr-1" />Mark as Won</button>
          </div>
        </div>
      )}

      {(handedOff || ariaState === 'FOUNDER_ACTIVE') && (
        <div className="p-3 bg-[#FEF3C7] border-b border-[#D97706]/20 text-center">
          <p className="text-xs font-semibold text-[#92400E]">You are handling this conversation</p>
        </div>
      )}

      {/* Instruction Panel */}
      {showInstruction && (
        <div className="p-3 bg-[#F4F0FF] border-b border-[#E0D4F7]" data-testid="instruction-panel">
          <p className="text-xs font-semibold text-[#7C35DC] mb-2" style={{ fontFamily: 'Plus Jakarta Sans' }}>Give Aria a private instruction:</p>
          <div className="flex gap-2">
            <input type="text" value={instructionText} onChange={(e) => setInstructionText(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && sendInstruction()}
              placeholder="e.g. Don't mention pricing yet" className="flex-1 bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-1.5 rounded-lg text-xs" data-testid="instruction-input" />
            <button onClick={sendInstruction} className="px-3 py-1.5 btn-gradient rounded-lg text-xs font-semibold" data-testid="send-instruction-btn">Send</button>
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="h-72 overflow-y-auto p-4 space-y-3 scrollbar-hide bg-[#FAFAFA]" data-testid="aria-messages">
        {conversation.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <Robot size={32} className="text-[#7C35DC] mb-3" weight="duotone" />
            <p className="text-sm text-[#9B8AB0]">No conversation yet</p>
            <button onClick={() => triggerAria('first_touch')} disabled={triggering}
              className="mt-3 flex items-center gap-2 px-4 py-2 btn-gradient rounded-lg text-sm font-semibold disabled:opacity-50" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid="aria-first-touch-btn">
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
                  'bg-[#F4F0FF] text-[#9B8AB0] border border-[#E8E0F5] text-xs italic'
                }`}>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-bold" style={{ color: msg.role === 'aria' ? '#7C35DC' : msg.role === 'lead' ? '#1A0A2E' : '#9B8AB0', fontFamily: 'Plus Jakarta Sans' }}>
                      {msg.role === 'aria' ? 'Aria' : msg.role === 'lead' ? leadName : 'System'}
                    </span>
                    <span className="text-xs text-[#9B8AB0]">{new Date(msg.created_at).toLocaleTimeString()}</span>
                  </div>
                  <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                  {msg.action && msg.action !== 'NONE' && msg.action !== 'INSTRUCTION' && (
                    <div className="mt-2 flex items-center gap-1 text-xs text-[#9B8AB0]"><Lightning size={12} /> {msg.action}</div>
                  )}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Actions & Input */}
      <div className="p-4 border-t border-[#E8E0F5] bg-white">
        {/* Phase 1 actions */}
        {conversation.length > 0 && ariaState === 'MEETING_BOOKED' && !phaseInfo?.pre_call_brief_sent && (
          <div className="flex gap-2 mb-3">
            <button onClick={runResearch} disabled={triggering} className="flex items-center gap-1.5 px-3 py-1.5 bg-[#F4F0FF] text-[#7C35DC] border border-[#7C35DC]/20 rounded-lg text-xs font-medium disabled:opacity-50" data-testid="run-research-btn">
              <Sparkle size={14} weight="fill" /> {triggering ? 'Researching...' : 'Run Pre-Call Research'}
            </button>
            <button onClick={sendBrief} className="flex items-center gap-1.5 px-3 py-1.5 bg-[#F4F0FF] text-[#7C35DC] border border-[#7C35DC]/20 rounded-lg text-xs font-medium" data-testid="send-brief-btn">Send Brief to Founder</button>
            <button onClick={pauseForCall} className="flex items-center gap-1.5 px-3 py-1.5 bg-[#FEF3C7] text-[#D97706] border border-[#D97706]/30 rounded-lg text-xs font-medium" data-testid="pause-for-call-btn"><Phone size={14} /> Call Starting</button>
          </div>
        )}

        {conversation.length > 0 && ariaState === 'AWAITING_REPLY_1' && (
          <div className="mb-3">
            <button onClick={() => triggerAria('followup')} disabled={triggering} className="flex items-center gap-1.5 px-3 py-1.5 bg-[#F4F0FF] text-[#7C35DC] border border-[#7C35DC]/20 rounded-lg text-xs font-medium disabled:opacity-50" data-testid="aria-followup-btn">
              <ArrowsClockwise size={14} /> {triggering ? 'Sending...' : 'Send Follow-up'}
            </button>
          </div>
        )}

        {/* Reply input */}
        <div className="flex items-center gap-2">
          <input type="text" value={replyText} onChange={(e) => setReplyText(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && sendReply()}
            placeholder="Simulate lead reply..." className="flex-1 bg-[#FAFAFA] border border-[#E8E0F5] text-[#1A0A2E] px-3 py-2 rounded-lg text-sm focus:border-[#7C35DC] focus:ring-2 focus:ring-[rgba(124,53,220,0.12)] transition-all" data-testid="aria-reply-input" />
          <button onClick={sendReply} disabled={loading || !replyText.trim()} className="p-2 btn-gradient rounded-lg disabled:opacity-50" data-testid="aria-send-reply-btn"><PaperPlaneRight size={18} /></button>
        </div>
      </div>
    </div>
  );
};

export default AriaConversationPanel;
