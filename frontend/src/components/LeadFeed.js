import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkle, Eye, BellSlash, CheckCircle, ArrowRight, Robot, Fire, Clock, FileText, ChatCircle, EnvelopeOpen, CalendarCheck, CurrencyCircleDollar, Snowflake, ArrowClockwise, Lightning } from '@phosphor-icons/react';
import api from '../config/api';
import AskAriaReplyModal from './AskAriaReplyModal';

const ICONS = { Fire, Clock, FileText, ChatCircle, EnvelopeOpen, CalendarCheck, CurrencyCircleDollar, Snowflake, ArrowClockwise, Lightning, Sparkle, Robot };

const TEMP_STYLES = {
  hot:  { cls: 'bg-[#FEE2E2] text-[#DC2626] border-[#DC2626]/30' },
  warm: { cls: 'bg-[#FEF3C7] text-[#D97706] border-[#D97706]/30' },
  cold: { cls: 'bg-[#F1F5F9] text-[#5A4A7A] border-[#94A3B8]/30' },
};

const LeadFeed = () => {
  const navigate = useNavigate();
  const [feed, setFeed] = useState([]);
  const [loading, setLoading] = useState(true);
  const [replyFor, setReplyFor] = useState(null);
  const [dismissed, setDismissed] = useState(() => {
    try { return new Set(JSON.parse(sessionStorage.getItem('aria_feed_dismissed') || '[]')); }
    catch { return new Set(); }
  });

  useEffect(() => {
    api.get('/api/aria-agent/workspace/feed?limit=20')
      .then(r => setFeed(r.data?.feed || []))
      .finally(() => setLoading(false));
  }, []);

  const markDone = (id) => {
    const next = new Set(dismissed); next.add(id); setDismissed(next);
    try { sessionStorage.setItem('aria_feed_dismissed', JSON.stringify([...next])); } catch { /* swallow */ }
  };

  const visible = feed.filter(c => !dismissed.has(c.id));

  if (loading) {
    return (
      <div className="bg-white border border-[#E8E0F5] rounded-2xl p-5 animate-pulse" style={{ boxShadow: 'var(--shadow-card)' }}>
        <div className="h-5 w-40 bg-[#F4F0FF] rounded mb-4" />
        <div className="space-y-3">{[1,2,3].map(i => <div key={i} className="h-24 bg-[#FAF7FF] rounded-xl" />)}</div>
      </div>
    );
  }

  return (
    <div className="bg-white border border-[#E8E0F5] rounded-2xl overflow-hidden aria-fade-up aria-fade-up-2" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="lead-feed-section">
      <div className="px-5 py-4 border-b border-[#F0ECF9] flex items-end justify-between">
        <div>
          <div className="inline-flex items-center gap-2 mb-1.5">
            <span className="block w-5 h-px bg-gradient-to-r from-[#C044E0] to-transparent" />
            <span className="text-[10px] font-bold uppercase tracking-[0.3em] text-[#7C35DC] numeric">LEAD FEED</span>
          </div>
          <h3 className="font-display text-xl md:text-2xl leading-tight text-[#1A0A2E]">Buying signals, ranked by urgency</h3>
          <p className="text-xs text-[#9B8AB0] mt-1 font-display-italic">Every card is one sales action away from closed.</p>
        </div>
        <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#9B8AB0] numeric">{visible.length} signals</div>
      </div>

      {visible.length === 0 && (
        <div className="px-5 py-12 text-center" data-testid="lead-feed-empty">
          <Sparkle size={24} weight="fill" className="text-[#7C35DC] mx-auto mb-3 aria-glow" />
          <div className="font-display text-lg text-[#1A0A2E]">You're all caught up.</div>
          <p className="text-xs text-[#9B8AB0] mt-1 max-w-sm mx-auto">ARIA will push the next signal to this feed the moment a lead moves.</p>
        </div>
      )}

      <div className="divide-y divide-[#F0ECF9]">
        {visible.map((c, idx) => {
          const Icon = ICONS[c.signal_icon] || Sparkle;
          const tempCls = TEMP_STYLES[c.temperature]?.cls || TEMP_STYLES.warm.cls;
          return (
            <div key={c.id} className={`px-5 py-4 aria-fade-up aria-fade-up-${(idx % 4) + 1} hover:bg-[#FAF7FF]/40 transition-colors`} data-testid={`feed-card-${idx}`}>
              <div className="flex items-start gap-3">
                <div className="w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 mt-0.5 relative" style={{ background: `${c.signal_accent}12`, border: `1px solid ${c.signal_accent}33` }}>
                  <Icon size={17} weight="fill" style={{ color: c.signal_accent }} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span className="text-[10px] font-extrabold uppercase tracking-[0.22em] numeric" style={{ color: c.signal_accent }}>{c.signal_label}</span>
                    <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-[0.15em] border numeric ${tempCls}`}>{c.temperature?.toUpperCase()}</span>
                    <span className="text-[10px] font-bold text-[#9B8AB0] numeric">ICP {c.icp_score}</span>
                  </div>
                  <div className="flex items-baseline gap-1.5 flex-wrap">
                    <span className="font-display text-[17px] text-[#1A0A2E] leading-tight">{c.lead_name}</span>
                    <span className="text-xs text-[#9B8AB0]">· {c.company}</span>
                    <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-[#9B8AB0] numeric">· via {c.channel}</span>
                  </div>
                  <p className="text-sm text-[#1A0A2E] mt-1.5 leading-relaxed">{c.summary}</p>
                  <div className="mt-2 flex items-start gap-1.5 p-2.5 rounded-lg bg-[#FAF7FF] border border-[#EDE5FA]">
                    <Robot size={12} weight="fill" className="text-[#7C35DC] flex-shrink-0 mt-0.5" />
                    <div className="text-xs text-[#1A0A2E] leading-relaxed"><span className="font-bold text-[#7C35DC]">ARIA recommends:</span> {c.aria_recommendation}</div>
                  </div>
                  <div className="mt-3 flex flex-wrap items-center gap-1.5">
                    <button onClick={() => setReplyFor({ id: c.lead_id, name: c.lead_name })} className="flex items-center gap-1.5 px-3 py-1.5 btn-gradient rounded-lg text-[10px] font-extrabold uppercase tracking-[0.18em] numeric" data-testid={`feed-ask-aria-${idx}`}>
                      <Sparkle size={11} weight="fill" /> Ask ARIA to Reply
                    </button>
                    <button onClick={() => navigate(`/leads/${c.lead_id}`)} className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-[#E8E0F5] text-[#5A4A7A] hover:bg-[#F4F0FF] hover:text-[#7C35DC] hover:border-[#7C35DC]/30 rounded-lg text-[10px] font-bold uppercase tracking-[0.15em] numeric" data-testid={`feed-view-lead-${idx}`}>
                      <Eye size={11} weight="fill" /> View Lead
                    </button>
                    <button onClick={() => markDone(c.id)} className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-[#E8E0F5] text-[#5A4A7A] hover:bg-[#DCFCE7] hover:text-[#16A34A] hover:border-[#16A34A]/30 rounded-lg text-[10px] font-bold uppercase tracking-[0.15em] numeric" data-testid={`feed-mark-done-${idx}`}>
                      <CheckCircle size={11} weight="fill" /> Done
                    </button>
                    <button onClick={() => markDone(c.id)} className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-[#E8E0F5] text-[#5A4A7A] hover:bg-[#F4F0FF] rounded-lg text-[10px] font-bold uppercase tracking-[0.15em] numeric" data-testid={`feed-snooze-${idx}`}>
                      <BellSlash size={11} weight="fill" /> Snooze
                    </button>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {visible.length > 0 && (
        <div className="px-5 py-3 border-t border-[#F0ECF9] bg-[#FAF7FF]/30 flex items-center justify-between">
          <button onClick={() => navigate('/leads')} className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC] hover:underline numeric flex items-center gap-1" data-testid="feed-view-all">
            See all leads <ArrowRight size={11} weight="bold" />
          </button>
          <div className="text-[10px] text-[#9B8AB0] font-display-italic">Your CRM stores leads. ARIA works them.</div>
        </div>
      )}

      {replyFor && <AskAriaReplyModal leadId={replyFor.id} leadName={replyFor.name} onClose={() => setReplyFor(null)} />}
    </div>
  );
};

export default LeadFeed;
