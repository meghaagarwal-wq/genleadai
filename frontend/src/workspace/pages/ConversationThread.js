/**
 * ConversationThread — chat-style rollup of every interaction with a lead.
 *
 * Reads GET /api/conversations/lead/{leadId} which combines outbound_log,
 * inbound_messages, and activities into one chronological timeline.
 *
 * Keyboard shortcuts (active when this tab is open):
 *   j / ArrowDown   → next message
 *   k / ArrowUp     → previous message
 *   Home            → first message
 *   End / G         → last message
 *   /               → focus filter input
 *   Esc             → clear filter / drop focus
 */
import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import {
  ChatCircleText, EnvelopeSimple, LinkedinLogo, ArrowsClockwise,
  Robot, User, Gear, MagnifyingGlass, CheckCircle, Warning, ArrowBendUpLeft, ArrowBendUpRight,
} from '@phosphor-icons/react';
import { toast } from 'sonner';
import { ptApi } from '../shared';

const CHANNEL_ICONS = { whatsapp: ChatCircleText, email: EnvelopeSimple, linkedin: LinkedinLogo };
const CHANNEL_COLORS = {
  whatsapp: '#10B981', email: '#6366F1', linkedin: '#0EA5E9',
};

const dt = (iso) => {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    return `${d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })} · ${d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}`;
  } catch { return iso; }
};

const ConversationThread = ({ leadId }) => {
  const [thread, setThread] = useState([]);
  const [counts, setCounts] = useState({ outbound: 0, inbound: 0, activity: 0, total: 0 });
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const [filterFocused, setFilterFocused] = useState(false);
  const [activeIdx, setActiveIdx] = useState(-1);
  const filterRef = useRef(null);
  const listRef = useRef(null);

  const fetchThread = useCallback(async () => {
    try {
      const r = await ptApi.get(`/api/conversations/lead/${leadId}`);
      setThread(r.data.thread || []);
      setCounts(r.data.counts || {});
    } catch {
      toast.error('Could not load thread');
    } finally {
      setLoading(false);
    }
  }, [leadId]);

  useEffect(() => { fetchThread(); }, [fetchThread]);

  // Filter
  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return thread;
    return thread.filter((t) =>
      (t.body || '').toLowerCase().includes(q)
      || (t.title || '').toLowerCase().includes(q)
      || (t.channel || '').toLowerCase().includes(q)
      || (t.actor || '').toLowerCase().includes(q),
    );
  }, [thread, filter]);

  // ─── Keyboard shortcuts ──
  useEffect(() => {
    const handler = (e) => {
      const isInputFocused = ['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName);
      if (e.key === '/' && !isInputFocused) {
        e.preventDefault();
        filterRef.current?.focus();
        return;
      }
      if (e.key === 'Escape') {
        if (filterFocused) { setFilter(''); filterRef.current?.blur(); }
        else setActiveIdx(-1);
        return;
      }
      if (isInputFocused) return;
      if (!filtered.length) return;
      if (e.key === 'j' || e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveIdx((i) => Math.min((i < 0 ? -1 : i) + 1, filtered.length - 1));
      } else if (e.key === 'k' || e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIdx((i) => Math.max(i - 1, 0));
      } else if (e.key === 'Home') {
        setActiveIdx(0);
      } else if (e.key === 'End' || e.key === 'G') {
        setActiveIdx(filtered.length - 1);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [filtered.length, filterFocused]);

  // Scroll active into view
  useEffect(() => {
    if (activeIdx < 0 || !listRef.current) return;
    const el = listRef.current.querySelector(`[data-thread-row="${activeIdx}"]`);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [activeIdx]);

  if (loading) {
    return <div className="p-6 text-center text-sm text-[#64748B]" data-testid="thread-loading">Loading conversation…</div>;
  }

  return (
    <div className="bg-white border border-[#E2E8F0] rounded-lg overflow-hidden" data-testid="thread-tab">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[#E2E8F0] flex items-center justify-between gap-3 bg-[#FAFAFA]">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <ChatCircleText size={16} weight="duotone" className="text-[#7C35DC]" />
            <span className="text-xs font-bold uppercase tracking-[0.16em] text-[#7C35DC]">Conversation</span>
          </div>
          <div className="text-xs text-[#64748B]">
            <span className="font-bold text-[#0F172A]">{counts.total}</span> events ·{' '}
            <span className="text-emerald-600">↗ {counts.outbound}</span>{' · '}
            <span className="text-blue-600">↘ {counts.inbound}</span>{' · '}
            <span className="text-[#64748B]">⚙ {counts.activity}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <MagnifyingGlass size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-[#94A3B8]" />
            <input
              ref={filterRef}
              type="text"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              onFocus={() => setFilterFocused(true)}
              onBlur={() => setFilterFocused(false)}
              placeholder="Filter (/)"
              data-testid="thread-filter"
              className="pl-7 pr-2 py-1 text-xs border border-[#E2E8F0] rounded-md outline-none w-44 bg-white focus:border-[#7C35DC]"
            />
          </div>
          <button onClick={fetchThread} className="text-[#94A3B8] hover:text-[#0F172A]" data-testid="thread-refresh">
            <ArrowsClockwise size={13} weight="bold" />
          </button>
        </div>
      </div>

      {/* Body */}
      {filtered.length === 0 ? (
        <div className="p-10 text-center text-sm text-[#64748B]" data-testid="thread-empty">
          {filter ? 'No matches in this conversation.' : 'No conversation yet — once ARIA sends or receives anything, it’ll appear here.'}
        </div>
      ) : (
        <div ref={listRef} className="divide-y divide-[#F1F5F9] max-h-[640px] overflow-y-auto">
          {filtered.map((t, i) => {
            const ChannelIcon = CHANNEL_ICONS[t.channel] || EnvelopeSimple;
            const isInbound = t.direction === 'inbound';
            const isSystem = t.direction === 'system';
            const accent = isSystem
              ? '#94A3B8'
              : (CHANNEL_COLORS[t.channel] || '#7C35DC');
            const active = i === activeIdx;
            return (
              <div
                key={t.id || `${t.ts}-${i}`}
                data-thread-row={i}
                data-testid={`thread-row-${i}`}
                className={`px-4 py-3 transition-colors ${active ? 'bg-[#FAF7FF]' : 'hover:bg-[#FAFAFA]'}`}
              >
                <div className={`flex items-start gap-3 ${isInbound ? 'flex-row-reverse text-right' : 'flex-row'}`}>
                  {/* Avatar */}
                  <div className="flex-shrink-0 mt-0.5">
                    <div className="w-8 h-8 rounded-full flex items-center justify-center"
                         style={{ background: isInbound ? '#FFEDD5' : isSystem ? '#F1F5F9' : '#EDE9FE' }}>
                      {isInbound ? <User size={14} weight="duotone" className="text-amber-700" />
                        : isSystem ? <Gear size={14} weight="duotone" className="text-[#64748B]" />
                        : <Robot size={14} weight="duotone" className="text-[#7C35DC]" />}
                    </div>
                  </div>
                  {/* Bubble */}
                  <div className={`max-w-[78%] ${isInbound ? 'items-end' : 'items-start'} flex flex-col gap-1`}>
                    <div className="flex items-center gap-1.5 text-[10px] text-[#94A3B8]">
                      {!isSystem && (
                        <span className="inline-flex items-center gap-0.5" style={{ color: accent }}>
                          {isInbound ? <ArrowBendUpLeft size={9} weight="bold" /> : <ArrowBendUpRight size={9} weight="bold" />}
                          <ChannelIcon size={10} weight="duotone" />
                          <span className="capitalize font-semibold">{t.channel}</span>
                        </span>
                      )}
                      <span>·</span>
                      <span className="font-mono">{dt(t.ts)}</span>
                      {t.meta?.provider && !isSystem && (
                        <>
                          <span>·</span>
                          <span className="text-[#94A3B8]">{t.meta.provider}</span>
                        </>
                      )}
                    </div>
                    <div
                      className="px-3 py-2 rounded-lg text-sm leading-relaxed"
                      style={{
                        background: isInbound ? '#FEF3C7'
                          : isSystem ? '#F8FAFC'
                          : 'linear-gradient(135deg, #FAF7FF 0%, #EDE9FE 100%)',
                        borderTop: isInbound ? '1px solid #F59E0B' : (isSystem ? '1px solid #E2E8F0' : '1px solid #7C35DC30'),
                      }}
                    >
                      {t.title && t.channel === 'email' && t.direction === 'outbound' && (
                        <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#7C35DC] mb-1">
                          {t.title}
                        </div>
                      )}
                      <div className="whitespace-pre-wrap text-[#0F172A]">
                        {t.body || <span className="text-[#94A3B8]">{t.title}</span>}
                      </div>
                      {/* Meta — only show on outbound failures / inbound matched ids */}
                      {t.direction === 'outbound' && t.meta?.sent === false && t.meta?.error && (
                        <div className="mt-1.5 text-[10px] text-red-700 flex items-center gap-1">
                          <Warning size={10} weight="fill" /> {t.meta.error.slice(0, 100)}
                        </div>
                      )}
                      {t.direction === 'outbound' && t.meta?.sent && (
                        <div className="mt-1.5 text-[10px] text-emerald-700 flex items-center gap-1">
                          <CheckCircle size={10} weight="fill" /> Delivered
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Keyboard shortcuts hint */}
      <div className="px-4 py-2 border-t border-[#E2E8F0] bg-[#FAFAFA] text-[10px] text-[#94A3B8] flex items-center gap-3">
        <kbd className="px-1.5 py-0.5 rounded border border-[#E2E8F0] bg-white font-mono">j</kbd>/<kbd className="px-1.5 py-0.5 rounded border border-[#E2E8F0] bg-white font-mono">k</kbd> navigate
        <span>·</span>
        <kbd className="px-1.5 py-0.5 rounded border border-[#E2E8F0] bg-white font-mono">/</kbd> filter
        <span>·</span>
        <kbd className="px-1.5 py-0.5 rounded border border-[#E2E8F0] bg-white font-mono">G</kbd> end
      </div>
    </div>
  );
};

export default ConversationThread;
