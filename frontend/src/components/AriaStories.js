import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { X, Sparkle, ArrowRight, PaperPlaneTilt, WhatsappLogo, EnvelopeSimple, Eye, BellSlash, CheckCircle, Robot } from '@phosphor-icons/react';
import api from '../config/api';
import AskAriaReplyModal from './AskAriaReplyModal';

const TEMP_STYLES = {
  hot:  { cls: 'bg-[#FEE2E2] text-[#DC2626] border-[#DC2626]/30' },
  warm: { cls: 'bg-[#FEF3C7] text-[#D97706] border-[#D97706]/30' },
  cold: { cls: 'bg-[#F1F5F9] text-[#5A4A7A] border-[#94A3B8]/30' },
};

const gradientForAccent = (accent) => `linear-gradient(135deg, ${accent} 0%, #7C35DC 100%)`;

const Ring = ({ story, onClick }) => {
  const tempCls = TEMP_STYLES[story.temperature]?.cls || TEMP_STYLES.warm.cls;
  return (
    <button onClick={() => onClick(story)} className="group flex flex-col items-center min-w-[84px] aria-fade-up" data-testid={`story-ring-${story.lead_id}`}>
      <div className="relative w-[72px] h-[72px] rounded-full p-[3px] transition-transform group-hover:scale-105" style={{ background: gradientForAccent(story.signal_accent) }}>
        <div className="w-full h-full rounded-full bg-white flex items-center justify-center relative overflow-hidden">
          <div className="w-[58px] h-[58px] rounded-full flex items-center justify-center font-display text-xl text-white numeric" style={{ background: gradientForAccent(story.signal_accent) }}>
            {story.initials}
          </div>
          <span className="absolute -top-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-white aria-pulse-ring" style={{ background: story.signal_accent }} />
        </div>
      </div>
      <div className="mt-2 max-w-[88px] text-center">
        <div className="text-[11px] font-bold text-[#1A0A2E] truncate" style={{ fontFamily: 'Plus Jakarta Sans' }}>{story.first_name || story.name}</div>
        <div className={`mt-1 inline-flex px-1.5 py-0.5 rounded text-[8px] font-extrabold uppercase tracking-[0.15em] border numeric ${tempCls}`}>
          {story.temperature?.toUpperCase()}
        </div>
        <div className="text-[9px] text-[#9B8AB0] mt-1 truncate">{story.signal_label}</div>
      </div>
    </button>
  );
};

const StoryCardModal = ({ leadId, onClose }) => {
  const navigate = useNavigate();
  const [card, setCard] = useState(null);
  const [replyOpen, setReplyOpen] = useState(false);

  useEffect(() => {
    api.get(`/api/aria-agent/workspace/story-card/${leadId}`).then(r => setCard(r.data)).catch(() => {});
  }, [leadId]);

  if (!card) {
    return (
      <div className="fixed inset-0 z-[60] flex items-center justify-center p-4" data-testid="story-card-loading">
        <div className="absolute inset-0 bg-black/55 backdrop-blur-sm" onClick={onClose} />
        <div className="relative bg-white rounded-3xl px-8 py-10 text-sm text-[#5A4A7A]">Loading story…</div>
      </div>
    );
  }

  const tempCls = TEMP_STYLES[card.temperature]?.cls || TEMP_STYLES.warm.cls;

  return (
    <>
      <div className="fixed inset-0 z-[60] flex items-center justify-center p-4" data-testid="story-card-modal">
        <div className="absolute inset-0 bg-black/55 backdrop-blur-sm" onClick={onClose} />
        <div className="relative w-full max-w-[480px] max-h-[88vh] overflow-y-auto rounded-3xl bg-white overflow-hidden aria-fade-up" style={{ boxShadow: '0 24px 64px -12px rgba(26,15,56,0.35)' }}>
          {/* Hero */}
          <div className="relative px-6 py-6 overflow-hidden aria-grain" style={{ background: gradientForAccent(card.signal_accent) }}>
            <button onClick={onClose} className="absolute top-4 right-4 p-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white border border-white/20 backdrop-blur-sm transition-colors" data-testid="story-card-close"><X size={16} /></button>
            <div className="relative flex items-center gap-3 mb-3">
              <div className="w-14 h-14 rounded-full bg-white/15 border border-white/25 flex items-center justify-center font-display text-xl text-white">
                {(card.first_name || card.name || 'LD')[0]}{(card.name?.split(' ')[1] || '')[0] || ''}
              </div>
              <div>
                <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-white/80 numeric">{card.signal_label}</div>
                <div className="font-display text-2xl text-white leading-tight">{card.name}</div>
                <div className="text-[13px] text-white/85">{card.company}{card.role ? ` · ${card.role}` : ''}</div>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-1.5 mt-3">
              <span className={`px-2 py-0.5 rounded text-[9px] font-extrabold uppercase tracking-[0.18em] border numeric ${tempCls}`}>{card.temperature?.toUpperCase()}</span>
              <span className="px-2 py-0.5 rounded text-[9px] font-extrabold uppercase tracking-[0.18em] bg-white/15 text-white border border-white/20 numeric">ICP {card.icp_score}</span>
            </div>
          </div>

          <div className="px-6 py-5 space-y-4">
            <div>
              <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#9B8AB0] numeric">WHAT HAPPENED</div>
              <div className="text-sm text-[#1A0A2E] mt-1 leading-relaxed">{card.what_happened}</div>
            </div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#9B8AB0] numeric">WHY IT MATTERS</div>
              <div className="text-sm text-[#1A0A2E] mt-1 leading-relaxed">{card.why_it_matters}</div>
            </div>
            <div className="rounded-xl p-3 bg-[#FAF7FF] border border-[#EDE5FA]">
              <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#9B8AB0] numeric">LAST INTERACTION</div>
              <div className="text-xs text-[#5A4A7A] mt-1 leading-relaxed">{card.last_interaction}</div>
            </div>
            <div className="rounded-xl p-4 border border-[#7C35DC]/25" style={{ background: 'linear-gradient(135deg, rgba(124,53,220,0.07) 0%, rgba(192,68,224,0.05) 100%)' }}>
              <div className="flex items-center gap-1.5 mb-1.5">
                <Robot size={12} weight="fill" className="text-[#7C35DC]" />
                <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#7C35DC] numeric">ARIA RECOMMENDS</div>
              </div>
              <div className="text-sm text-[#1A0A2E] leading-relaxed font-display-italic">"{card.aria_recommendation}"</div>
            </div>
          </div>

          {/* Actions */}
          <div className="px-6 pb-5 pt-1 grid grid-cols-2 gap-2">
            <button onClick={() => setReplyOpen(true)} className="col-span-2 btn-gradient py-3 rounded-xl text-[11px] font-extrabold uppercase tracking-[0.2em] flex items-center justify-center gap-2 numeric" data-testid="story-card-ask-aria">
              <Sparkle size={13} weight="fill" /> Ask ARIA to Reply
            </button>
            <button onClick={() => { onClose(); navigate(`/leads/${card.lead_id}`); }} className="flex items-center justify-center gap-2 py-2.5 rounded-xl bg-white border border-[#E8E0F5] text-[#5A4A7A] hover:bg-[#F4F0FF] hover:text-[#7C35DC] hover:border-[#7C35DC]/30 text-[10px] font-bold uppercase tracking-[0.15em] numeric" data-testid="story-card-view-lead">
              <Eye size={12} weight="fill" /> View Lead
            </button>
            <button onClick={onClose} className="flex items-center justify-center gap-2 py-2.5 rounded-xl bg-white border border-[#E8E0F5] text-[#5A4A7A] hover:bg-[#F4F0FF] hover:text-[#7C35DC] hover:border-[#7C35DC]/30 text-[10px] font-bold uppercase tracking-[0.15em] numeric" data-testid="story-card-snooze">
              <BellSlash size={12} weight="fill" /> Snooze
            </button>
          </div>
        </div>
      </div>

      {replyOpen && <AskAriaReplyModal leadId={card.lead_id} leadName={card.name} onClose={() => setReplyOpen(false)} />}
    </>
  );
};

const AriaStories = () => {
  const [stories, setStories] = useState([]);
  const [openLeadId, setOpenLeadId] = useState(null);

  useEffect(() => {
    api.get('/api/aria-agent/workspace/stories?limit=10').then(r => setStories(r.data?.stories || [])).catch(() => {});
  }, []);

  if (stories.length === 0) return null;

  return (
    <div className="bg-white border border-[#E8E0F5] rounded-2xl p-5 aria-fade-up aria-fade-up-1" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="aria-stories-section">
      <div className="flex items-end justify-between mb-4">
        <div>
          <div className="inline-flex items-center gap-2 mb-1.5">
            <span className="block w-5 h-px bg-gradient-to-r from-[#C044E0] to-transparent" />
            <span className="text-[10px] font-bold uppercase tracking-[0.3em] text-[#7C35DC] numeric">ARIA STORIES</span>
          </div>
          <h3 className="font-display text-xl md:text-2xl leading-tight text-[#1A0A2E]">Leads that need your attention today</h3>
          <p className="text-xs text-[#9B8AB0] mt-1 font-display-italic">Tap a ring to see why ARIA flagged them.</p>
        </div>
      </div>
      <div className="flex gap-4 overflow-x-auto pb-2 scrollbar-hide" data-testid="aria-stories-rings">
        {stories.map(s => <Ring key={s.lead_id} story={s} onClick={() => setOpenLeadId(s.lead_id)} />)}
      </div>

      {openLeadId && <StoryCardModal leadId={openLeadId} onClose={() => setOpenLeadId(null)} />}
    </div>
  );
};

export default AriaStories;
