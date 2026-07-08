/**
 * Conversations — Reply Triage Queue (iter165)
 * ────────────────────────────────────────────────────────────────────
 * A Superhuman-inspired split-pane approval queue. Each item is an
 * AI-drafted response awaiting founder sign-off. Left pane lists the
 * pending items with an AI classification chip (stage + confidence).
 * Right pane shows the full draft + inline edit + approve/reject.
 *
 * Backend: /api/approvals returns pending_outreach with lead_snapshot,
 *          confidence, reason_for_review, channel, subject, draft.
 * Actions:
 *   POST /api/approvals/{id}/approve
 *   POST /api/approvals/{id}/edit-send  { subject?, body }
 *   POST /api/approvals/{id}/reject     { reason? }
 *
 * Keyboard: J/K navigate · E approve · R reject · / search · Esc close
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import {
  ChatCircleText, EnvelopeSimple, LinkedinLogo,
  Lightning, CheckCircle, X as XIcon, PencilSimple,
  MagnifyingGlass, Sparkle, Warning, Fire, ThermometerSimple,
  ChatDots, ArrowRight, Command, Robot,
} from '@phosphor-icons/react';
import api from '../config/api';

const CHANNEL_META = {
  whatsapp: { icon: ChatCircleText, label: 'WhatsApp', color: '#25D366' },
  email:    { icon: EnvelopeSimple, label: 'Email',    color: '#3B82F6' },
  linkedin: { icon: LinkedinLogo,   label: 'LinkedIn', color: '#0A66C2' },
  sms:      { icon: ChatDots,       label: 'SMS',      color: '#A855F7' },
};

const STAGE_META = {
  hot:     { color: '#DC2626', bg: 'rgba(220,38,38,0.10)',   label: 'HOT',     icon: Fire },
  warm:    { color: '#F59E0B', bg: 'rgba(245,158,11,0.12)',  label: 'WARM',    icon: ThermometerSimple },
  engaged: { color: '#10B981', bg: 'rgba(16,185,129,0.12)',  label: 'ENGAGED', icon: Sparkle },
  cold:    { color: '#6B7280', bg: 'rgba(107,114,128,0.14)', label: 'COLD',    icon: null },
};

const relTime = (iso) => {
  if (!iso) return '';
  const ms = Date.now() - new Date(iso).getTime();
  const m = Math.floor(ms / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h`;
  return `${Math.floor(h / 24)}d`;
};

const initials = (name) =>
  (name || 'PP').split(/\s+/).slice(0, 2).map((w) => w[0] || '').join('').toUpperCase();

const confidenceLabel = (c) => {
  if (c == null) return { label: 'Review', color: 'var(--theme-text-muted)', pct: 50 };
  const pct = Math.round(c * 100);
  if (c >= 0.75) return { label: 'High confidence', color: '#10B981', pct };
  if (c >= 0.5)  return { label: 'Medium confidence', color: '#F59E0B', pct };
  return { label: 'Low confidence', color: '#DC2626', pct };
};


// ─── Left pane row ───────────────────────────────────────────────────
const TriageRow = ({ item, active, onClick }) => {
  const ChannelIcon = (CHANNEL_META[item.channel] || CHANNEL_META.email).icon;
  const chColor = (CHANNEL_META[item.channel] || {}).color || 'var(--theme-primary)';
  const stage = STAGE_META[(item.lead_snapshot?.stage || 'cold').toLowerCase()] || STAGE_META.cold;
  const conf = confidenceLabel(item.confidence);
  const name = item.lead_snapshot?.name || 'Prospect';
  const company = item.lead_snapshot?.company;

  return (
    <button
      onClick={onClick}
      data-testid={`triage-row-${item.id}`}
      aria-selected={active}
      className="w-full text-left px-3 py-3 border-b flex gap-3 transition-colors focus:outline-none"
      style={{
        background: active ? 'var(--theme-primary-dim)' : 'transparent',
        borderColor: 'var(--theme-border)',
        borderLeft: active ? '3px solid var(--theme-primary)' : '3px solid transparent',
      }}
    >
      <div
        className="shrink-0 w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold text-white"
        style={{ background: 'var(--theme-primary)' }}
        aria-hidden="true"
      >
        {initials(name)}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5 mb-0.5">
          <div className="text-sm font-semibold truncate" style={{ color: 'var(--theme-text)' }}>{name}</div>
          <span className="ml-auto text-[10px] shrink-0" style={{ color: 'var(--theme-text-muted)' }}>{relTime(item.created_at)}</span>
        </div>
        <div className="text-[11px] truncate mb-1" style={{ color: 'var(--theme-text-muted)' }}>
          {company || item.lead_snapshot?.email || '—'}
        </div>
        <div className="text-xs line-clamp-2 mb-1.5" style={{ color: 'var(--theme-text)' }}>
          {item.draft_preview || item.body || item.draft || item.subject}
        </div>
        <div className="flex items-center gap-1.5 flex-wrap">
          <span
            className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider"
            style={{ background: stage.bg, color: stage.color }}
          >
            {stage.icon ? <stage.icon size={9} weight="fill" /> : null} {stage.label}
          </span>
          <span
            className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[9px] font-semibold"
            style={{ background: 'var(--theme-surface2)', color: chColor }}
          >
            <ChannelIcon size={9} weight="fill" /> {(CHANNEL_META[item.channel] || {}).label || item.channel}
          </span>
          <span
            className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[9px] font-semibold"
            style={{ background: 'var(--theme-surface2)', color: conf.color }}
            title={`${conf.pct}% AI confidence`}
          >
            <Sparkle size={9} weight="fill" /> {conf.pct}%
          </span>
        </div>
      </div>
    </button>
  );
};


// ─── Right pane detail ───────────────────────────────────────────────
const TriageDetail = ({ item, onApprove, onReject, onEditSend, busy }) => {
  const [editing, setEditing] = useState(false);
  const [subject, setSubject] = useState(item?.subject || '');
  const [body, setBody] = useState(item?.body || item?.draft || '');
  const [rejecting, setRejecting] = useState(false);
  const [rejectReason, setRejectReason] = useState('');

  useEffect(() => {
    setEditing(false);
    setRejecting(false);
    setSubject(item?.subject || '');
    setBody(item?.body || item?.draft || '');
    setRejectReason('');
  }, [item?.id]);

  if (!item) {
    return (
      <div className="flex-1 flex items-center justify-center p-10">
        <div className="text-center">
          <div className="mx-auto w-14 h-14 rounded-full flex items-center justify-center mb-3"
               style={{ background: 'var(--theme-primary-dim)', color: 'var(--theme-primary)' }}>
            <Robot size={28} weight="duotone" />
          </div>
          <div className="text-sm font-semibold" style={{ color: 'var(--theme-text)', fontFamily: 'var(--font-display)' }}>
            Pick a draft to review.
          </div>
          <div className="text-xs mt-1" style={{ color: 'var(--theme-text-muted)' }}>
            Use <kbd className="px-1 mx-0.5 rounded border text-[10px]" style={{ borderColor: 'var(--theme-border)' }}>J</kbd> and
            <kbd className="px-1 mx-0.5 rounded border text-[10px]" style={{ borderColor: 'var(--theme-border)' }}>K</kbd> to navigate.
          </div>
        </div>
      </div>
    );
  }

  const stage = STAGE_META[(item.lead_snapshot?.stage || 'cold').toLowerCase()] || STAGE_META.cold;
  const ChannelIcon = (CHANNEL_META[item.channel] || CHANNEL_META.email).icon;
  const chColor = (CHANNEL_META[item.channel] || {}).color || 'var(--theme-primary)';
  const conf = confidenceLabel(item.confidence);
  const name = item.lead_snapshot?.name || 'Prospect';
  const company = item.lead_snapshot?.company;
  const showSubject = item.channel === 'email';

  return (
    <div className="flex-1 flex flex-col overflow-hidden" data-testid={`triage-detail-${item.id}`}>
      {/* Lead header */}
      <div className="px-6 py-4 border-b flex items-start gap-4" style={{ borderColor: 'var(--theme-border)' }}>
        <div
          className="shrink-0 w-11 h-11 rounded-full flex items-center justify-center text-sm font-bold text-white"
          style={{ background: 'var(--theme-primary)' }}
        >
          {initials(name)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <div className="text-lg font-semibold" style={{ color: 'var(--theme-text)', fontFamily: 'var(--font-display)' }}>{name}</div>
            <span
              className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider"
              style={{ background: stage.bg, color: stage.color }}
            >
              {stage.icon ? <stage.icon size={10} weight="fill" /> : null} {stage.label}
            </span>
            {item.lead_snapshot?.score != null && (
              <span
                className="text-[11px] font-semibold px-1.5 py-0.5 rounded-full"
                style={{ background: 'var(--theme-surface2)', color: 'var(--theme-text)' }}
              >
                Score {item.lead_snapshot.score}
              </span>
            )}
          </div>
          <div className="text-xs mt-0.5" style={{ color: 'var(--theme-text-muted)' }}>
            {company || item.lead_snapshot?.email || '—'} · Queued {relTime(item.created_at)} ago
          </div>
        </div>
      </div>

      {/* AI reasoning callout */}
      <div className="px-6 py-3 border-b" style={{ borderColor: 'var(--theme-border)', background: 'var(--theme-primary-dim)' }}>
        <div className="flex items-start gap-2">
          <Sparkle size={14} weight="fill" style={{ color: 'var(--theme-primary)', marginTop: 2 }} />
          <div className="flex-1">
            <div className="text-[11px] font-bold uppercase tracking-[0.14em]" style={{ color: 'var(--theme-primary)' }}>
              ARIA · {item.ai_model || 'draft'}
            </div>
            <div className="text-xs mt-0.5 leading-relaxed" style={{ color: 'var(--theme-text)' }}>
              {item.reason_for_review || 'AI drafted this reply and would like your sign-off before sending.'}
            </div>
            <div className="mt-2 flex items-center gap-3">
              <div className="flex-1 max-w-[240px] h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--theme-surface2)' }}>
                <div className="h-full transition-all" style={{ width: `${conf.pct}%`, background: conf.color }} />
              </div>
              <span className="text-[11px] font-semibold" style={{ color: conf.color }}>{conf.label} · {conf.pct}%</span>
            </div>
          </div>
        </div>
      </div>

      {/* Draft body — read or edit */}
      <div className="flex-1 overflow-y-auto px-6 py-5">
        <div className="text-[10px] uppercase tracking-[0.18em] font-bold mb-2 flex items-center gap-1.5" style={{ color: 'var(--theme-text-muted)' }}>
          <ChannelIcon size={11} weight="fill" style={{ color: chColor }} /> AI-drafted {(CHANNEL_META[item.channel] || {}).label || 'reply'}
        </div>
        {showSubject && (editing ? (
          <input
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="Subject"
            className="w-full mb-3 px-3 py-2 rounded-lg text-sm outline-none border"
            style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text)', fontFamily: 'var(--font-display)' }}
            data-testid="triage-subject-input"
          />
        ) : (
          <div className="mb-3 text-sm font-semibold" style={{ color: 'var(--theme-text)', fontFamily: 'var(--font-display)' }}>
            {item.subject || <span className="italic" style={{ color: 'var(--theme-text-muted)' }}>(no subject)</span>}
          </div>
        ))}
        {editing ? (
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={10}
            className="w-full px-4 py-3 rounded-xl text-sm outline-none border leading-relaxed resize-none"
            style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text)' }}
            data-testid="triage-body-input"
          />
        ) : (
          <div
            className="text-sm leading-relaxed whitespace-pre-wrap rounded-xl border p-4"
            style={{ color: 'var(--theme-text)', background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }}
          >
            {item.body || item.draft || '(no draft body)'}
          </div>
        )}

        {rejecting && (
          <div className="mt-4">
            <div className="text-[10px] uppercase tracking-[0.18em] font-bold mb-2" style={{ color: 'var(--theme-text-muted)' }}>Reject reason (optional)</div>
            <input
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="e.g. Not the right time, wrong angle…"
              className="w-full px-3 py-2 rounded-lg text-sm outline-none border"
              style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text)' }}
              data-testid="triage-reject-reason"
            />
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="px-6 py-4 border-t flex items-center gap-2" style={{ borderColor: 'var(--theme-border)', background: 'var(--theme-surface)' }}>
        {rejecting ? (
          <>
            <button
              onClick={() => { setRejecting(false); setRejectReason(''); }}
              className="px-3 py-2 rounded-lg text-xs font-semibold border"
              style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)', color: 'var(--theme-text)' }}
              data-testid="triage-cancel-reject"
            >Cancel</button>
            <button
              onClick={() => onReject(item, rejectReason)}
              disabled={busy}
              className="ml-auto px-4 py-2 rounded-lg text-xs font-bold text-white disabled:opacity-50"
              style={{ background: '#DC2626' }}
              data-testid="triage-confirm-reject"
            >Confirm reject</button>
          </>
        ) : editing ? (
          <>
            <button
              onClick={() => { setEditing(false); setBody(item.body || item.draft || ''); setSubject(item.subject || ''); }}
              className="px-3 py-2 rounded-lg text-xs font-semibold border"
              style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)', color: 'var(--theme-text)' }}
            >Cancel</button>
            <span className="text-[10px]" style={{ color: 'var(--theme-text-muted)' }}>Editing draft…</span>
            <button
              onClick={() => onEditSend(item, { subject, body })}
              disabled={busy || !body.trim()}
              className="ml-auto px-4 py-2 rounded-lg text-xs font-bold text-white disabled:opacity-50 inline-flex items-center gap-1.5"
              style={{ background: 'var(--theme-primary)' }}
              data-testid="triage-save-send"
            >
              <CheckCircle size={12} weight="fill" /> Save & send
            </button>
          </>
        ) : (
          <>
            <button
              onClick={() => setRejecting(true)}
              className="px-3 py-2 rounded-lg text-xs font-semibold border"
              style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)', color: '#DC2626' }}
              data-testid="triage-reject-btn"
            >
              <XIcon size={11} weight="bold" className="inline -mt-0.5 mr-1" /> Reject
            </button>
            <button
              onClick={() => setEditing(true)}
              className="px-3 py-2 rounded-lg text-xs font-semibold border"
              style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)', color: 'var(--theme-text)' }}
              data-testid="triage-edit-btn"
            >
              <PencilSimple size={11} weight="bold" className="inline -mt-0.5 mr-1" /> Edit
            </button>
            <button
              onClick={() => onApprove(item)}
              disabled={busy}
              className="ml-auto px-4 py-2 rounded-lg text-xs font-bold text-white disabled:opacity-50 inline-flex items-center gap-1.5"
              style={{ background: 'var(--theme-primary)' }}
              data-testid="triage-approve-btn"
            >
              <Lightning size={12} weight="fill" /> Approve & send
            </button>
          </>
        )}
      </div>
    </div>
  );
};


// ─── Main page ───────────────────────────────────────────────────────
const Conversations = () => {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState('');
  const [confFilter, setConfFilter] = useState('all'); // all | high | medium | low
  const [activeId, setActiveId] = useState(null);
  const searchRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get('/api/approvals');
      const list = r.data?.items || [];
      setItems(list);
      // Auto-select first item on load
      setActiveId((cur) => cur && list.some((x) => x.id === cur) ? cur : list[0]?.id || null);
    } catch (_e) {
      toast.error('Could not load approvals');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return items.filter((it) => {
      // Confidence filter
      const c = it.confidence ?? 0;
      if (confFilter === 'high'   && c < 0.75) return false;
      if (confFilter === 'medium' && (c < 0.5 || c >= 0.75)) return false;
      if (confFilter === 'low'    && c >= 0.5) return false;
      // Search filter
      if (q) {
        const hay = `${it.lead_snapshot?.name || ''} ${it.lead_snapshot?.company || ''} ${it.subject || ''} ${it.body || it.draft || ''}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [items, query, confFilter]);

  const active = filtered.find((it) => it.id === activeId) || null;
  const activeIdx = filtered.findIndex((it) => it.id === activeId);

  // Auto-adjust active if filter changes and current is filtered out
  useEffect(() => {
    if (filtered.length > 0 && !filtered.some((x) => x.id === activeId)) {
      setActiveId(filtered[0].id);
    } else if (filtered.length === 0) {
      setActiveId(null);
    }
  }, [filtered, activeId]);

  // ─── Actions ───
  const doApprove = async (item) => {
    setBusy(true);
    try {
      await api.post(`/api/approvals/${item.id}/approve`);
      toast.success(`Approved & sent to ${item.lead_snapshot?.name || 'lead'}`);
      setItems((xs) => xs.filter((x) => x.id !== item.id));
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Approve failed');
    } finally { setBusy(false); }
  };

  const doReject = async (item, reason) => {
    setBusy(true);
    try {
      await api.post(`/api/approvals/${item.id}/reject`, { reason });
      toast.success('Draft rejected');
      setItems((xs) => xs.filter((x) => x.id !== item.id));
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Reject failed');
    } finally { setBusy(false); }
  };

  const doEditSend = async (item, patch) => {
    setBusy(true);
    try {
      await api.post(`/api/approvals/${item.id}/edit-send`, patch);
      toast.success('Sent with your edits');
      setItems((xs) => xs.filter((x) => x.id !== item.id));
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Send failed');
    } finally { setBusy(false); }
  };

  // ─── Keyboard shortcuts ───
  useEffect(() => {
    const handler = (e) => {
      // Ignore inputs / editable text
      const tag = (e.target?.tagName || '').toLowerCase();
      if (tag === 'input' || tag === 'textarea' || e.target?.isContentEditable) {
        if (e.key === 'Escape') e.target.blur();
        return;
      }
      if (e.key === 'j' || e.key === 'J' || e.key === 'ArrowDown') {
        e.preventDefault();
        if (filtered.length === 0) return;
        const nxt = filtered[(activeIdx + 1) % filtered.length];
        setActiveId(nxt.id);
      } else if (e.key === 'k' || e.key === 'K' || e.key === 'ArrowUp') {
        e.preventDefault();
        if (filtered.length === 0) return;
        const prv = filtered[(activeIdx - 1 + filtered.length) % filtered.length];
        setActiveId(prv.id);
      } else if (e.key === 'e' || e.key === 'E') {
        if (active) { e.preventDefault(); doApprove(active); }
      } else if (e.key === 'r' || e.key === 'R') {
        if (active) { e.preventDefault(); doReject(active, ''); }
      } else if (e.key === '/') {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtered, activeIdx, active]);

  return (
    <div className="max-w-[1400px] mx-auto" data-testid="conversations-page" style={{ color: 'var(--theme-text)' }}>
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-3 mb-4">
        <div>
          <div className="eyebrow" style={{ color: 'var(--theme-primary)' }}>Reply Triage</div>
          <h1 className="text-[28px] leading-tight tracking-tight font-semibold" style={{ color: 'var(--theme-text)', fontFamily: 'var(--font-display)' }}>
            Conversations
          </h1>
          <p className="text-sm mt-1" style={{ color: 'var(--theme-text-muted)' }}>
            ARIA drafts replies. You review, edit, or approve. Fast.
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <div className="relative">
            <MagnifyingGlass size={13} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--theme-text-dim)' }} />
            <input
              ref={searchRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search leads or drafts…"
              className="pl-8 pr-3 py-2 rounded-full text-xs w-56 outline-none border"
              style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)', color: 'var(--theme-text)' }}
              data-testid="triage-search"
            />
          </div>
          <button
            onClick={load}
            className="px-3 py-2 rounded-full text-xs font-semibold border transition-colors hover:bg-[var(--theme-surface2)]"
            style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)', color: 'var(--theme-text)' }}
            data-testid="triage-refresh"
          >Refresh</button>
        </div>
      </div>

      {/* Filter + kbd hints */}
      <div className="flex items-center gap-2 flex-wrap mb-3">
        {[
          { k: 'all', label: `All (${items.length})` },
          { k: 'high', label: `High conf` },
          { k: 'medium', label: `Medium` },
          { k: 'low', label: `Low` },
        ].map((f) => {
          const active = confFilter === f.k;
          return (
            <button
              key={f.k}
              onClick={() => setConfFilter(f.k)}
              data-testid={`triage-filter-${f.k}`}
              className="px-3 py-1.5 rounded-full text-xs font-semibold border transition-colors"
              style={{
                background: active ? 'var(--theme-primary)' : 'var(--theme-surface)',
                borderColor: active ? 'var(--theme-primary)' : 'var(--theme-border)',
                color: active ? '#fff' : 'var(--theme-text-muted)',
              }}
            >{f.label}</button>
          );
        })}
        <div className="ml-auto hidden md:flex items-center gap-3 text-[10px]" style={{ color: 'var(--theme-text-dim)' }}>
          <Hint k="J" desc="next" />
          <Hint k="K" desc="prev" />
          <Hint k="E" desc="approve" />
          <Hint k="R" desc="reject" />
          <Hint k="/" desc="search" />
          <Hint k={<><Command size={10} weight="bold" className="inline -mt-0.5" />J</>} desc="Aria" />
        </div>
      </div>

      {/* Split-pane container */}
      <div
        className="rounded-2xl border overflow-hidden flex"
        style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)', height: 'calc(100vh - 240px)', minHeight: 480 }}
        data-testid="triage-split-pane"
      >
        {/* Left list */}
        <div className="w-[380px] shrink-0 border-r flex flex-col" style={{ borderColor: 'var(--theme-border)' }}>
          <div className="px-4 py-2.5 border-b text-[10px] uppercase tracking-[0.16em] font-bold flex items-center justify-between" style={{ borderColor: 'var(--theme-border)', color: 'var(--theme-text-muted)' }}>
            <span>{filtered.length} to review</span>
            <span>Newest first</span>
          </div>
          <div className="flex-1 overflow-y-auto" data-testid="triage-list">
            {loading && (
              <div className="text-center py-10 text-xs" style={{ color: 'var(--theme-text-muted)' }}>Loading…</div>
            )}
            {!loading && filtered.length === 0 && (
              <div className="text-center py-14 px-4">
                <div className="mx-auto w-12 h-12 rounded-full flex items-center justify-center mb-2"
                     style={{ background: 'var(--theme-primary-dim)', color: 'var(--theme-primary)' }}>
                  <CheckCircle size={22} weight="duotone" />
                </div>
                <div className="text-sm font-semibold" style={{ color: 'var(--theme-text)', fontFamily: 'var(--font-display)' }}>
                  Inbox zero.
                </div>
                <div className="text-xs mt-1" style={{ color: 'var(--theme-text-muted)' }}>
                  No drafts waiting on you.
                </div>
              </div>
            )}
            {!loading && filtered.map((it) => (
              <TriageRow key={it.id} item={it} active={it.id === activeId} onClick={() => setActiveId(it.id)} />
            ))}
          </div>
        </div>

        {/* Right detail */}
        <TriageDetail
          item={active}
          busy={busy}
          onApprove={doApprove}
          onReject={doReject}
          onEditSend={doEditSend}
        />
      </div>
    </div>
  );
};

const Hint = ({ k, desc }) => (
  <span className="inline-flex items-center gap-1">
    <kbd
      className="px-1.5 py-0.5 rounded border text-[10px] font-semibold"
      style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)', color: 'var(--theme-text)' }}
    >{k}</kbd>
    {desc}
  </span>
);

export default Conversations;
