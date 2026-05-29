/**
 * ConversationThread — chat-style rollup of every interaction with a lead.
 *
 * Reads GET /api/conversations/lead/{leadId} which combines outbound_log,
 * inbound_messages, and activities into one chronological timeline.
 *
 * Reply box (iter128)
 *   POST /api/conversations/lead/{leadId}/send routes through the
 *   shared dispatch_outreach chokepoint. The Send-as toggle controls
 *   whether the outbound is attributed to ARIA or the founder.
 *
 * Keyboard shortcuts (active when this tab is open):
 *   j / ArrowDown   → next message
 *   k / ArrowUp     → previous message
 *   Home            → first message
 *   End / G         → last message
 *   /               → focus filter input
 *   r               → focus reply box                    (iter128)
 *   e               → toggle Send-as ARIA ⇄ me           (iter128)
 *   ⌘/Ctrl + Enter  → send reply                          (iter128)
 *   Esc             → clear filter / blur inputs / drop active row
 */
import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import {
  ChatCircleText, EnvelopeSimple, LinkedinLogo, ArrowsClockwise,
  Robot, User, Gear, MagnifyingGlass, CheckCircle, Warning, ArrowBendUpLeft, ArrowBendUpRight,
  PaperPlaneTilt, Sparkle,
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

  // iter128 — Reply box state
  const [replyChannel, setReplyChannel] = useState('email'); // 'whatsapp' | 'email' | 'linkedin'
  const [replyBody, setReplyBody] = useState('');
  const [sendAs, setSendAs] = useState('aria');             // 'aria' | 'me'
  const [sending, setSending] = useState(false);
  const replyRef = useRef(null);

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

  // iter128 — default reply channel to the last outbound channel used.
  useEffect(() => {
    if (!thread.length) return;
    const lastOut = [...thread].reverse().find((t) => t.direction === 'outbound' && t.channel);
    if (lastOut?.channel && ['whatsapp', 'email', 'linkedin'].includes(lastOut.channel)) {
      setReplyChannel(lastOut.channel);
    }
  }, [thread]);

  // iter128 — send the reply via the unified dispatch endpoint.
  // iter132 — auto-learn voice: if the founder edited an ARIA draft before
  // sending, offer a one-click toast to save the edited version as a new
  // voice seed. We compare the final body against the last draft ARIA
  // produced; if they differ AND a draft was produced this session, the
  // edit is treated as a "this is how I would have written it" signal.
  const learnFromEdit = async (text, channel) => {
    try {
      const labelStub = new Date().toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
      await ptApi.post('/api/voice-seeds', {
        channel,
        text,
        label: `Auto-learned ${labelStub}`,
        active: true,
      });
      toast.success('ARIA learned from your edit — future drafts will sound more like you.');
    } catch (e) {
      // Most common rejection: tenant hit the 10-seed cap.
      toast.error(e.response?.data?.detail || 'Could not save voice sample');
    }
  };

  const sendReply = async () => {
    const text = replyBody.trim();
    if (!text) { toast.error('Type a message first'); return; }
    setSending(true);
    // Snapshot the edit-vs-draft delta *before* we clear state so the
    // toast prompt below has clean values to work with.
    const editedFromAriaDraft = (
      lastDraftTextRef.current
      && text !== lastDraftTextRef.current.trim()
      && text.length >= 20
    );
    const channelAtSend = replyChannel;
    try {
      const r = await ptApi.post(`/api/conversations/lead/${leadId}/send`, {
        channel: channelAtSend,
        body: text,
        send_as: sendAs,
      });
      if (r.data?.sent) {
        toast.success(`Sent via ${r.data.provider || channelAtSend}`);
      } else if (r.data?.logged_only) {
        toast.info(`Saved as draft — ${channelAtSend} provider not connected yet`);
      }
      // iter132 — friction-free auto-learn prompt. Auto-dismisses after 5s.
      if (editedFromAriaDraft) {
        toast('Want ARIA to learn from this edit?', {
          duration: 5000,
          action: {
            label: 'Learn ✓',
            onClick: () => learnFromEdit(text, channelAtSend === 'whatsapp' || channelAtSend === 'email' || channelAtSend === 'linkedin' ? channelAtSend : 'any'),
          },
          // data-testid surfaced via the action button for E2E hooks.
          className: 'aria-auto-learn-toast',
        });
      }
      setReplyBody('');
      setAttempt(0);            // iter130 — reset variant counter after send
      setLastDraft('');
      // Refresh the thread so the new message appears at the bottom.
      fetchThread();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Send failed');
    } finally {
      setSending(false);
    }
  };

  // iter129 — "Draft with ARIA" button.
  // iter130 — Draft variants: track which attempt we're on. On the first
  // press it's a fresh draft; on subsequent presses ARIA varies the angle
  // (contrarian hook, then radically shorter direct ask). The counter
  // resets when the textarea is manually edited or after a successful send.
  // We mirror the attempt counter in a ref so the keyboard-shortcut handler
  // sees the latest value even when React batches re-renders.
  const [drafting, setDrafting] = useState(false);
  const [draftAttempt, setDraftAttempt] = useState(0);
  const draftAttemptRef = useRef(0);
  const [lastDraftText, setLastDraftText] = useState('');
  const lastDraftTextRef = useRef('');

  const setAttempt = (n) => { draftAttemptRef.current = n; setDraftAttempt(n); };
  const setLastDraft = (s) => { lastDraftTextRef.current = s; setLastDraftText(s); };

  const draftWithAria = async () => {
    setDrafting(true);
    try {
      const currentAttempt = draftAttemptRef.current;
      const nextAttempt = Math.min(3, currentAttempt + 1);
      const r = await ptApi.post(`/api/conversations/lead/${leadId}/draft`, {
        channel: replyChannel,
        user_steer: (replyBody.trim() && replyBody.trim() !== lastDraftTextRef.current) ? replyBody.trim() : undefined,
        attempt: nextAttempt,
      });
      const draft = r.data?.draft || '';
      if (!draft) {
        toast.error('ARIA had nothing to draft. Run an Intel scan first to give her context.');
        return;
      }
      setReplyBody(draft);
      setLastDraft(draft);
      setAttempt(nextAttempt);
      if (r.data?.has_intel) {
        toast.success(nextAttempt === 1
          ? 'Draft ready — grounded in this lead\'s intel profile'
          : `Variant ${nextAttempt} ready — different angle, same intel`);
      } else {
        toast.info(nextAttempt === 1
          ? 'Draft ready — no intel profile yet, so it\'s a generic opener. Run Intel scan for sharper drafts.'
          : `Variant ${nextAttempt} ready — try a scan for sharper drafts`);
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Draft failed');
    } finally {
      setDrafting(false);
    }
  };

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
      const tag = document.activeElement?.tagName;
      const isInputFocused = ['INPUT', 'TEXTAREA'].includes(tag);

      // ⌘/Ctrl+Enter inside the reply textarea → send.
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && document.activeElement === replyRef.current) {
        e.preventDefault();
        sendReply();
        return;
      }
      // "/" anywhere outside an input → focus filter.
      if (e.key === '/' && !isInputFocused) {
        e.preventDefault();
        filterRef.current?.focus();
        return;
      }
      // Esc handles the deepest focus state first.
      if (e.key === 'Escape') {
        if (document.activeElement === replyRef.current) {
          replyRef.current.blur();
        } else if (filterFocused) {
          setFilter(''); filterRef.current?.blur();
        } else {
          setActiveIdx(-1);
        }
        return;
      }
      // Below shortcuts only fire when no input owns focus.
      if (isInputFocused) return;

      // r → focus reply box.
      if (e.key === 'r' || e.key === 'R') {
        e.preventDefault();
        replyRef.current?.focus();
        return;
      }
      // e → toggle Send-as ARIA ⇄ me.
      if (e.key === 'e' || e.key === 'E') {
        e.preventDefault();
        setSendAs((v) => (v === 'aria' ? 'me' : 'aria'));
        toast(`Send as ${sendAs === 'aria' ? 'me' : 'ARIA'}`, { duration: 1200 });
        return;
      }
      // d → draft with ARIA.
      if (e.key === 'd' || e.key === 'D') {
        e.preventDefault();
        draftWithAria();
        return;
      }
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
  }, [filtered.length, filterFocused, sendAs]); // eslint-disable-line react-hooks/exhaustive-deps

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

      {/* iter128 — Reply box */}
      <div className="px-4 py-3 border-t border-[#E2E8F0] bg-white" data-testid="thread-reply-box">
        <div className="flex items-center gap-2 mb-2">
          {/* Channel selector */}
          <div className="inline-flex rounded-md border border-[#E2E8F0] overflow-hidden" data-testid="thread-reply-channel-group">
            {[
              { id: 'whatsapp', label: 'WhatsApp', Icon: ChatCircleText },
              { id: 'email',    label: 'Email',    Icon: EnvelopeSimple },
              { id: 'linkedin', label: 'LinkedIn', Icon: LinkedinLogo },
            ].map((c) => {
              const Icon = c.Icon;
              const active = replyChannel === c.id;
              return (
                <button
                  key={c.id}
                  onClick={() => setReplyChannel(c.id)}
                  data-testid={`thread-reply-channel-${c.id}`}
                  className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold transition-colors"
                  style={{
                    background: active ? '#7C35DC' : '#FFFFFF',
                    color: active ? '#FFFFFF' : '#475569',
                  }}
                >
                  <Icon size={11} weight="duotone" /> {c.label}
                </button>
              );
            })}
          </div>

          {/* Send-as toggle */}
          <button
            onClick={() => setSendAs((v) => (v === 'aria' ? 'me' : 'aria'))}
            data-testid="thread-reply-send-as-toggle"
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-semibold border"
            style={{
              borderColor: sendAs === 'aria' ? '#7C35DC' : '#94A3B8',
              background: sendAs === 'aria' ? '#FAF7FF' : '#F8FAFC',
              color: sendAs === 'aria' ? '#7C35DC' : '#475569',
            }}
            title="Press e to toggle"
          >
            {sendAs === 'aria' ? (
              <><Robot size={11} weight="duotone" /> Send as ARIA</>
            ) : (
              <><User size={11} weight="duotone" /> Send as me</>
            )}
          </button>
        </div>

        <div className="flex items-end gap-2">
          <textarea
            ref={replyRef}
            value={replyBody}
            onChange={(e) => {
              const v = e.target.value;
              setReplyBody(v);
              // iter130 — manual edit invalidates the variant chain so the
              // next press starts fresh at attempt #1.
              if (v !== lastDraftTextRef.current) setAttempt(0);
            }}
            placeholder={`Type a message — ⌘/Ctrl + Enter to send (or press r to focus, e to toggle Send-as, d to draft with ARIA).`}
            rows={2}
            data-testid="thread-reply-textarea"
            className="flex-1 px-3 py-2 text-sm border border-[#E2E8F0] rounded-md outline-none focus:border-[#7C35DC] resize-none"
          />
          <div className="flex flex-col gap-1.5">
            <button
              onClick={draftWithAria}
              disabled={drafting || draftAttempt >= 3}
              data-testid="thread-reply-draft-btn"
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-xs font-bold border disabled:opacity-50"
              style={{
                borderColor: '#7C35DC',
                color: '#7C35DC',
                background: '#FAF7FF',
              }}
              title={
                draftAttempt === 0 ? 'Press d to draft with ARIA'
                : draftAttempt >= 3 ? 'Max 3 variants — edit or send to start over'
                : 'Press d for another variant'
              }
            >
              <Sparkle size={11} weight="fill" />{' '}
              {drafting
                ? 'Drafting…'
                : draftAttempt === 0
                  ? 'Draft with ARIA'
                  : draftAttempt >= 3
                    ? `Variant 3/3`
                    : `Try another (${draftAttempt}/3)`}
            </button>
            <button
              onClick={sendReply}
              disabled={sending || !replyBody.trim()}
              data-testid="thread-reply-send-btn"
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-xs font-bold text-white disabled:opacity-50"
              style={{ background: 'linear-gradient(135deg, #4C1D95 0%, #7C35DC 100%)' }}
            >
              <PaperPlaneTilt size={12} weight="fill" /> {sending ? 'Sending…' : 'Send'}
            </button>
          </div>
        </div>
      </div>

      {/* Keyboard shortcuts hint */}
      <div className="px-4 py-2 border-t border-[#E2E8F0] bg-[#FAFAFA] text-[10px] text-[#94A3B8] flex flex-wrap items-center gap-x-3 gap-y-1" data-testid="thread-shortcuts-hint">
        <kbd className="px-1.5 py-0.5 rounded border border-[#E2E8F0] bg-white font-mono">j</kbd>/<kbd className="px-1.5 py-0.5 rounded border border-[#E2E8F0] bg-white font-mono">k</kbd> navigate
        <span>·</span>
        <kbd className="px-1.5 py-0.5 rounded border border-[#E2E8F0] bg-white font-mono">/</kbd> filter
        <span>·</span>
        <kbd className="px-1.5 py-0.5 rounded border border-[#E2E8F0] bg-white font-mono">r</kbd> reply
        <span>·</span>
        <kbd className="px-1.5 py-0.5 rounded border border-[#E2E8F0] bg-white font-mono">d</kbd> draft with ARIA
        <span>·</span>
        <kbd className="px-1.5 py-0.5 rounded border border-[#E2E8F0] bg-white font-mono">e</kbd> toggle send-as
        <span>·</span>
        <kbd className="px-1.5 py-0.5 rounded border border-[#E2E8F0] bg-white font-mono">⌘/Ctrl</kbd>+<kbd className="px-1.5 py-0.5 rounded border border-[#E2E8F0] bg-white font-mono">Enter</kbd> send
        <span>·</span>
        <kbd className="px-1.5 py-0.5 rounded border border-[#E2E8F0] bg-white font-mono">Esc</kbd> close
      </div>
    </div>
  );
};

export default ConversationThread;
