/**
 * Conversations — /conversations
 *
 * Thread list with urgent/negative leads floating to top.
 * Each row → Lead Inbox for takeover/reply.
 */
import React, { useEffect, useState, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
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
  const [searchParams, setSearchParams] = useSearchParams();
  const [threads, setThreads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState(searchParams.get('tab') || '');  // sentiment filter

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

  // URL persistence helper.
  const applyFilter = (key) => {
    setFilter(key);
    setSearchParams((sp) => {
      const next = new URLSearchParams(sp);
      if (!key) next.delete('tab'); else next.set('tab', key);
      return next;
    }, { replace: true });
  };

  const counts = useMemo(() => {
    const c = { all: threads.length, urgent: 0, negative: 0, positive: 0, neutral: 0 };
    threads.forEach((t) => { const s = (t.latest_sentiment || 'neutral').toLowerCase(); if (c[s] !== undefined) c[s]++; });
    return c;
  }, [threads]);

  // Aria-says microcopy — adaptive based on what's in the queue.
  const ariaSays = useMemo(() => {
    if (loading) return null;
    if (counts.urgent > 0) return `${counts.urgent} urgent thread${counts.urgent === 1 ? '' : 's'} need your reply now. Aria has paused her replies on these and is waiting for you.`;
    if (counts.negative > 0) return `${counts.negative} lead${counts.negative === 1 ? ' is' : 's are'} showing negative signals. Open them first so the conversation doesn't slip further.`;
    if (counts.positive > 0) return `${counts.positive} thread${counts.positive === 1 ? '' : 's'} are warming up. Great time to send a soft nudge or share a case study.`;
    if (counts.all === 0) return 'No conversations yet. Connect your WhatsApp or website widget so Aria can start chatting with new leads.';
    return 'Pipeline is calm. Aria is keeping every thread alive in the background.';
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [counts, loading]);

  return (
    <div className="space-y-5 max-w-[1100px] mx-auto" data-testid="conversations-page">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[var(--theme-primary)] mb-1">Live Threads</div>
          <h1 className="text-3xl font-extrabold text-[var(--theme-text)]" style={{ fontFamily: 'var(--font-display)' }}>Conversations</h1>
          <p className="text-sm text-[var(--theme-text-muted)] mt-1">Urgent and negative sentiment leads float to the top automatically.</p>
        </div>
        <div className="flex items-center gap-2">
          <form onSubmit={(e) => { e.preventDefault(); load(); }} className="flex items-center gap-2">
            <div className="relative">
              <MagnifyingGlass size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--theme-text-dim)]" />
              <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search name or phone…" data-testid="conv-search"
                className="pl-8 pr-3 py-2 border rounded-full text-xs w-60 outline-none"
                style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)', color: 'var(--theme-text)' }} />
            </div>
          </form>
        </div>
      </div>

      {/* Keyboard hints strip (Superhuman-inspired) */}
      <div className="hidden md:flex items-center gap-3 text-[10px]" style={{ color: 'var(--theme-text-dim)' }}>
        <span className="inline-flex items-center gap-1"><kbd className="px-1.5 py-0.5 rounded border text-[10px] font-semibold" style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)', color: 'var(--theme-text)' }}>J</kbd>/<kbd className="px-1.5 py-0.5 rounded border text-[10px] font-semibold" style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)', color: 'var(--theme-text)' }}>K</kbd> navigate</span>
        <span className="inline-flex items-center gap-1"><kbd className="px-1.5 py-0.5 rounded border text-[10px] font-semibold" style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)', color: 'var(--theme-text)' }}>E</kbd> archive</span>
        <span className="inline-flex items-center gap-1"><kbd className="px-1.5 py-0.5 rounded border text-[10px] font-semibold" style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)', color: 'var(--theme-text)' }}>/</kbd> search</span>
        <span className="inline-flex items-center gap-1"><kbd className="px-1.5 py-0.5 rounded border text-[10px] font-semibold" style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)', color: 'var(--theme-text)' }}>⌘J</kbd> ask Aria</span>
      </div>

      {/* Sentiment filter pills */}
      <div className="flex items-center gap-2 flex-wrap" data-testid="sentiment-filters">        {[
          { key: '', label: `All (${counts.all})`, color: 'var(--theme-primary)' },
          { key: 'urgent', label: `Urgent (${counts.urgent})`, color: '#DC2626' },
          { key: 'negative', label: `Negative (${counts.negative})`, color: '#D97706' },
          { key: 'positive', label: `Positive (${counts.positive})`, color: '#16A34A' },
          { key: 'neutral', label: `Neutral (${counts.neutral})`, color: '#5A4A7A' },
        ].map((p) => (
          <button key={p.key} onClick={() => applyFilter(p.key)} data-testid={`filter-${p.key || 'all'}`}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition-all ${filter === p.key ? 'text-white' : 'bg-[var(--theme-surface)] text-[var(--theme-text-muted)] border-[var(--theme-border)] hover:bg-[var(--theme-surface2)]'}`}
            style={filter === p.key ? { background: p.color, borderColor: p.color } : {}}>
            {p.label}
          </button>
        ))}
      </div>

      {/* Aria-says microcopy */}
      {ariaSays && (
        <div className="aria-card-lift rounded-2xl border px-4 py-3 flex items-start gap-2.5" style={{ background: 'var(--theme-primary-dim)', borderColor: 'var(--theme-border)' }} data-testid="conversations-aria-says">
          <Sparkle size={14} weight="fill" className="text-[var(--theme-primary)] mt-0.5 flex-shrink-0" />
          <p className="text-xs text-[var(--theme-text)] leading-relaxed">
            <span className="font-extrabold text-[var(--theme-primary)]" style={{ fontFamily: 'var(--font-display)' }}>Aria says: </span>
            {ariaSays}
          </p>
        </div>
      )}

      {/* Threads list */}
      {loading ? (
        <div className="bg-[var(--theme-surface)] border border-[var(--theme-border)] rounded-xl p-10 text-center text-sm text-[var(--theme-text-dim)]">Loading…</div>
      ) : threads.length === 0 ? (
        <div className="bg-[var(--theme-surface)] border border-[var(--theme-border)] rounded-xl p-12 text-center" data-testid="no-conversations">
          <Sparkle size={28} weight="duotone" className="text-[var(--theme-primary)] mx-auto mb-2" />
          <h3 className="text-base font-bold text-[var(--theme-text)] mb-1" style={{ fontFamily: 'var(--font-display)' }}>No conversations yet</h3>
          <p className="text-xs text-[var(--theme-text-muted)]">When leads start replying to Aria, threads will appear here.</p>
        </div>
      ) : (
        <div className="bg-[var(--theme-surface)] border border-[var(--theme-border)] rounded-xl overflow-hidden" style={{ boxShadow: 'var(--shadow-card)' }}>
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
                    <span className="text-sm font-bold text-[var(--theme-text)]" style={{ fontFamily: 'var(--font-display)' }}>{t.first_name || 'Lead'} {t.last_name || ''}</span>
                    {!t.aria_active && <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-[#FEF3C7] text-[#D97706] border border-[#D97706]/30">Human</span>}
                    <span className="text-[10px] font-mono text-[var(--theme-text-dim)]">{t.phone}</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-xs text-[var(--theme-text-muted)] mt-0.5">
                    {t.last_message_role === 'aria' && <span className="text-[10px] font-bold text-[var(--theme-primary)]">Aria:</span>}
                    {t.last_message_role === 'lead' && <span className="text-[10px] font-bold text-[#0055FF]">Lead:</span>}
                    <span className="truncate">{t.last_message || <span className="italic text-[var(--theme-text-dim)]">No messages yet</span>}</span>
                  </div>
                </div>

                {/* Right: sentiment + score + time */}
                <div className="flex-shrink-0 flex items-center gap-3">
                  {t.aria_confidence !== null && t.aria_confidence !== undefined && (
                    <div className="text-right">
                      <div className="text-[9px] font-bold uppercase tracking-wider text-[var(--theme-text-dim)]">Confidence</div>
                      <div className="text-xs font-extrabold text-[var(--theme-primary)]">{Math.round((t.aria_confidence || 0) * 100)}%</div>
                    </div>
                  )}
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold border" style={{ background: sm.bg, borderColor: sm.color + '55', color: sm.color }}>
                    <Icon size={10} weight="fill" /> {sm.label}
                  </span>
                  <span className="text-[10px] text-[var(--theme-text-dim)] font-mono w-16 text-right">{fmtRel(t.last_message_at)}</span>
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
