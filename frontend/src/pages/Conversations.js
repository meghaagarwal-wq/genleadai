/**
 * Conversations — /conversations
 *
 * Thread list with urgent/negative leads floating to top.
 * Each row → Lead Inbox for takeover/reply.
 */
import React, { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../config/api';
import { ChatCircle, Warning, Fire, Heart, Smiley, Question, MagnifyingGlass, Sparkle } from '@phosphor-icons/react';

const SENTIMENT_META = {
  urgent: { color: '#DC2626', bg: '#FEE2E2', label: 'Urgent', icon: Warning },
  negative: { color: '#D97706', bg: '#FEF3C7', label: 'Negative', icon: Fire },
  neutral: { color: '#5A4A7A', bg: '#F1F5F9', label: 'Neutral', icon: Question },
  positive: { color: '#16A34A', bg: '#DCFCE7', label: 'Positive', icon: Smiley },
};

const fmtRel = (iso) => {
  if (!iso) return '—';
  const d = Date.now() - new Date(iso).getTime();
  if (d < 60000) return 'just now';
  if (d < 3600000) return `${Math.round(d / 60000)}m ago`;
  if (d < 86400000) return `${Math.round(d / 3600000)}h ago`;
  return `${Math.round(d / 86400000)}d ago`;
};

const Conversations = () => {
  const nav = useNavigate();
  const [threads, setThreads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('');  // sentiment filter

  const load = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filter) params.set('sentiment', filter);
      if (search) params.set('search', search);
      const r = await api.get(`/api/conversations/threads?${params.toString()}`);
      setThreads(r.data?.threads || []);
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [filter]);  // eslint-disable-line

  const counts = useMemo(() => {
    const c = { all: threads.length, urgent: 0, negative: 0, positive: 0, neutral: 0 };
    threads.forEach((t) => { const s = (t.latest_sentiment || 'neutral').toLowerCase(); if (c[s] !== undefined) c[s]++; });
    return c;
  }, [threads]);

  return (
    <div className="space-y-5 max-w-[1100px] mx-auto" data-testid="conversations-page">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC] mb-1">Live Threads</div>
          <h1 className="text-3xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Conversations</h1>
          <p className="text-sm text-[#5A4A7A] mt-1">Urgent and negative sentiment leads float to the top automatically.</p>
        </div>
        <div className="flex items-center gap-2">
          <form onSubmit={(e) => { e.preventDefault(); load(); }} className="flex items-center gap-2">
            <div className="relative">
              <MagnifyingGlass size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9B8AB0]" />
              <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search name or phone…" data-testid="conv-search"
                className="pl-8 pr-3 py-2 bg-white border border-[#E8E0F5] rounded-lg text-xs w-60" />
            </div>
          </form>
        </div>
      </div>

      {/* Sentiment filter pills */}
      <div className="flex items-center gap-2 flex-wrap" data-testid="sentiment-filters">
        {[
          { key: '', label: `All (${counts.all})`, color: '#7C35DC' },
          { key: 'urgent', label: `Urgent (${counts.urgent})`, color: '#DC2626' },
          { key: 'negative', label: `Negative (${counts.negative})`, color: '#D97706' },
          { key: 'positive', label: `Positive (${counts.positive})`, color: '#16A34A' },
          { key: 'neutral', label: `Neutral (${counts.neutral})`, color: '#5A4A7A' },
        ].map((p) => (
          <button key={p.key} onClick={() => setFilter(p.key)} data-testid={`filter-${p.key || 'all'}`}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold border transition-all ${filter === p.key ? 'text-white' : 'bg-white text-[#5A4A7A] border-[#E8E0F5] hover:bg-[#F9F5FF]'}`}
            style={filter === p.key ? { background: p.color, borderColor: p.color } : {}}>
            {p.label}
          </button>
        ))}
      </div>

      {/* Threads list */}
      {loading ? (
        <div className="bg-white border border-[#E8E0F5] rounded-xl p-10 text-center text-sm text-[#9B8AB0]">Loading…</div>
      ) : threads.length === 0 ? (
        <div className="bg-white border border-[#E8E0F5] rounded-xl p-12 text-center" data-testid="no-conversations">
          <Sparkle size={28} weight="duotone" className="text-[#7C35DC] mx-auto mb-2" />
          <h3 className="text-base font-bold text-[#1A0A2E] mb-1" style={{ fontFamily: 'Plus Jakarta Sans' }}>No conversations yet</h3>
          <p className="text-xs text-[#5A4A7A]">When leads start replying to Aria, threads will appear here.</p>
        </div>
      ) : (
        <div className="bg-white border border-[#E8E0F5] rounded-xl overflow-hidden" style={{ boxShadow: 'var(--shadow-card)' }}>
          {threads.map((t, idx) => {
            const sm = SENTIMENT_META[(t.latest_sentiment || 'neutral').toLowerCase()] || SENTIMENT_META.neutral;
            const Icon = sm.icon;
            const urgent = ['urgent', 'negative'].includes((t.latest_sentiment || '').toLowerCase());
            return (
              <button key={t.lead_id} onClick={() => nav(`/lead-inbox?lead=${t.lead_id}`)} data-testid={`thread-${t.lead_id}`}
                className={`w-full text-left px-5 py-3 border-b border-[#F0ECF9] hover:bg-[#FAF7FF] transition-all flex items-center gap-4 ${idx === threads.length - 1 ? 'border-b-0' : ''} ${urgent ? 'bg-gradient-to-r from-[#FEE2E2]/30 to-transparent' : ''}`}>
                {/* Avatar */}
                <div className="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold text-white" style={{ background: 'var(--gradient-brand)' }}>
                  {(t.first_name || 'L').slice(0, 1).toUpperCase()}
                </div>

                {/* Name + last msg */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-bold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{t.first_name || 'Lead'} {t.last_name || ''}</span>
                    {!t.aria_active && <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-[#FEF3C7] text-[#D97706] border border-[#D97706]/30">Human</span>}
                    <span className="text-[10px] font-mono text-[#9B8AB0]">{t.phone}</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-xs text-[#5A4A7A] mt-0.5">
                    {t.last_message_role === 'aria' && <span className="text-[10px] font-bold text-[#7C35DC]">Aria:</span>}
                    {t.last_message_role === 'lead' && <span className="text-[10px] font-bold text-[#0055FF]">Lead:</span>}
                    <span className="truncate">{t.last_message || <span className="italic text-[#9B8AB0]">No messages yet</span>}</span>
                  </div>
                </div>

                {/* Right: sentiment + score + time */}
                <div className="flex-shrink-0 flex items-center gap-3">
                  {t.aria_confidence !== null && t.aria_confidence !== undefined && (
                    <div className="text-right">
                      <div className="text-[9px] font-bold uppercase tracking-wider text-[#9B8AB0]">Confidence</div>
                      <div className="text-xs font-extrabold text-[#7C35DC]">{Math.round((t.aria_confidence || 0) * 100)}%</div>
                    </div>
                  )}
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold border" style={{ background: sm.bg, borderColor: sm.color + '55', color: sm.color }}>
                    <Icon size={10} weight="fill" /> {sm.label}
                  </span>
                  <span className="text-[10px] text-[#9B8AB0] font-mono w-16 text-right">{fmtRel(t.last_message_at)}</span>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default Conversations;
