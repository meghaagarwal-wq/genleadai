/**
 * CommandCenterScreen — iter173
 *
 * Hero surface for the demo. Combines:
 *   1) A live-updating "ARIA saved you" counter tile (money + hours).
 *   2) The Approvals queue — "ARIA did this for you" cards with real,
 *      good, personalised drafted messages. Approve = satisfying tap,
 *      slide-out, counter tick. Edit = inline.
 *   3) A compact KPI strip for context.
 *
 * Content flows in via props so the parent controls persona + brand.
 */
import React, { useState } from 'react';
import {
  Sparkles, Check, X, Edit3, ChevronDown, ChevronUp, ArrowRight, Clock,
  DollarSign, Mail, MessageSquare, Send, Zap, TrendingUp,
} from 'lucide-react';
import { personaliseText } from '../../demoData/liveContent';

const CHANNEL_ICONS = {
  Email:      Mail,
  SMS:        MessageSquare,
  LinkedIn:   Send,
  Internal:   Zap,
};

export default function CommandCenterScreen({ persona, approvals, brand, savedMoney, savedHours, onApprove, T }) {
  const kpis = persona.header.kpis.slice(0, 4);

  return (
    <div className="pt-6 space-y-6" data-testid="screen-command-center">
      {/* Hero saved counter */}
      <SavedTile brand={brand} savedMoney={savedMoney} savedHours={savedHours} approvalsCount={approvals.length} T={T} />

      {/* Compact KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {kpis.map((k) => (
          <MiniKpi key={k.key} item={k} T={T} />
        ))}
      </div>

      {/* Approvals — the hero */}
      <div>
        <div className="flex items-end justify-between mb-4 flex-wrap gap-3">
          <div>
            <div className="uppercase text-[11px] tracking-[0.14em] mb-2" style={{ color: T.accent, fontWeight: 600 }}>
              ARIA did this for you
            </div>
            <h2 className="text-[24px] leading-tight tracking-tight font-semibold"
              style={{ fontFamily: T.fontDisplay, color: T.ink }}>
              {approvals.length} action{approvals.length === 1 ? '' : 's'} waiting on you
            </h2>
            <p className="text-sm mt-1" style={{ color: T.muted }}>
              Each one is drafted. Approve to send · Edit inline · Skip to defer.
            </p>
          </div>
          <button className="text-xs px-3 py-1.5 rounded-full inline-flex items-center gap-1.5 transition-colors"
            style={{ background: T.accent, color: '#fff', fontWeight: 600 }}
            data-testid="approve-all-btn"
            onClick={() => approvals.forEach((a) => onApprove(a.id))}
          >
            <Check size={12} strokeWidth={2.5} /> Approve all
          </button>
        </div>

        <div className="space-y-3">
          {approvals.map((a) => (
            <ApprovalCard key={a.id} approval={a} brand={brand} onApprove={() => onApprove(a.id)} T={T} />
          ))}
          {approvals.length === 0 && (
            <div
              className="rounded-2xl px-5 py-8 text-center text-sm"
              style={{ background: T.card, border: `1px solid ${T.line}`, color: T.muted }}
              data-testid="approvals-empty"
            >
              <div className="inline-flex items-center justify-center w-10 h-10 rounded-full mb-3"
                style={{ background: T.accentSoft, color: T.accent }}>
                <Sparkles size={18} />
              </div>
              <div style={{ color: T.ink, fontWeight: 600 }}>You're clear.</div>
              <div>ARIA has nothing waiting on you right now. New drafts will land as signals arrive.</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ───────────────────────── Saved-counter tile ─────────────────────────
function SavedTile({ brand, savedMoney, savedHours, approvalsCount, T }) {
  return (
    <div
      className="rounded-2xl relative overflow-hidden"
      style={{
        background: `linear-gradient(135deg, ${T.card} 0%, ${T.cardElev} 100%)`,
        border: `1px solid ${T.line}`,
        padding: 24,
      }}
      data-testid="saved-tile"
    >
      <div aria-hidden className="absolute -top-24 -right-24 w-64 h-64 rounded-full"
        style={{ background: 'radial-gradient(closest-side, rgba(164,111,232,0.22), transparent 70%)' }} />
      <div className="relative flex items-center justify-between gap-6 flex-wrap">
        <div>
          <div className="uppercase text-[11px] tracking-[0.14em] mb-2 inline-flex items-center gap-2"
            style={{ color: T.accent, fontWeight: 600 }}>
            <Sparkles size={12} /> ARIA impact · this month
          </div>
          <div className="text-[42px] leading-none font-semibold tabular-nums tracking-tight"
            style={{ fontFamily: T.fontDisplay, color: T.ink, letterSpacing: '-0.02em' }}
            data-testid="saved-money">
            {formatMoney(savedMoney)}
          </div>
          <div className="text-sm mt-2 max-w-[560px]" style={{ color: T.muted }}>
            ARIA caught <span style={{ color: T.ink, fontWeight: 600 }}>{approvalsCount}</span> lead{approvalsCount === 1 ? '' : 's'} <span style={{ color: T.ink, fontWeight: 600 }}>{brand?.companyName || 'your team'}</span> would have dropped this week.
            {' '}Approve to send · every tap sends the draft ARIA already wrote.
          </div>
        </div>
        <div className="flex gap-6">
          <MiniStat label="hours saved" value={savedHours.toFixed(1)} icon={Clock} T={T} testid="saved-hours" />
          <MiniStat label="drafts written" value={approvalsCount} icon={Zap} T={T} />
        </div>
      </div>
    </div>
  );
}

function MiniStat({ label, value, icon: Icon, T, testid }) {
  return (
    <div className="text-right">
      <div className="inline-flex items-center gap-1.5 text-[10px] uppercase tracking-[0.14em]"
        style={{ color: T.muted, fontWeight: 600 }}>
        <Icon size={11} /> {label}
      </div>
      <div className="text-[22px] font-semibold tabular-nums mt-1"
        style={{ fontFamily: T.fontDisplay, color: T.ink }}
        data-testid={testid}>
        {value}
      </div>
    </div>
  );
}

function MiniKpi({ item, T }) {
  return (
    <div className="rounded-xl p-3.5" style={{ background: T.card, border: `1px solid ${T.line}` }}>
      <div className="text-[10px] uppercase tracking-[0.14em]" style={{ color: T.muted, fontWeight: 600 }}>
        {item.label}
      </div>
      <div className="mt-1.5 text-[20px] font-semibold tabular-nums"
        style={{ fontFamily: T.fontDisplay, color: T.ink }}>
        {item.value}
      </div>
      <div className="mt-1 text-[11px] inline-flex items-center gap-1" style={{ color: item.tone === 'up' ? T.success : T.danger }}>
        <TrendingUp size={11} /> {item.delta}
      </div>
    </div>
  );
}

// ───────────────────────── Approval card ─────────────────────────
function ApprovalCard({ approval, brand, onApprove, T }) {
  const [expanded, setExpanded] = useState(false);
  const [approved, setApproved] = useState(false);
  const [editingIdx, setEditingIdx] = useState(-1);
  const [editText, setEditText] = useState('');
  const vars = { brand: brand?.companyName || 'the team' };

  const urgencyColor = {
    high:   T.danger,
    medium: T.warn,
    low:    T.muted,
  }[approval.urgency] || T.muted;

  const handleApprove = () => {
    if (approved) return;
    setApproved(true);
    setTimeout(() => onApprove(), 450);
  };

  return (
    <div
      className="rounded-2xl overflow-hidden transition-all"
      style={{
        background: T.card,
        border: `1px solid ${approved ? T.success : T.line}`,
        transform: approved ? 'translateX(24px)' : 'translateX(0)',
        opacity: approved ? 0.5 : 1,
      }}
      data-testid={`approval-${approval.id}`}
    >
      <div className="p-5 flex items-start gap-4">
        {/* Urgency bar */}
        <div className="w-1 self-stretch rounded-full shrink-0" style={{ background: urgencyColor, opacity: 0.6 }} />

        <div className="flex-1 min-w-0">
          <div className="inline-flex items-center gap-2 mb-2">
            <span className="uppercase text-[10px] tracking-[0.14em] px-2 py-0.5 rounded-full"
              style={{ background: T.accentSoft, color: T.accent, fontWeight: 600 }}>
              {approval.tag}
            </span>
            <span className="text-[11px]" style={{ color: T.muted }}>{approval.value}</span>
          </div>
          <div className="text-[15px] font-semibold" style={{ color: T.ink }}>
            {personaliseText(approval.title, vars)}
          </div>
          <div className="text-sm mt-1" style={{ color: T.muted }}>
            {personaliseText(approval.why, vars)}
          </div>

          {expanded && (
            <div className="mt-4 space-y-3">
              {approval.drafts.map((d, i) => {
                const Icon = CHANNEL_ICONS[d.channel?.split(' ')[0]] || Mail;
                const showEditor = editingIdx === i;
                const body = showEditor ? editText : personaliseText(d.body, vars);
                return (
                  <div key={i} className="rounded-xl p-4" style={{ background: T.canvas, border: `1px solid ${T.line}` }}>
                    <div className="flex items-center justify-between mb-2 gap-3 flex-wrap">
                      <div className="flex items-center gap-2 text-[11px]" style={{ color: T.muted }}>
                        <Icon size={12} style={{ color: T.accent }} />
                        <span style={{ color: T.ink }}>{d.channel}</span>
                        <span>·</span>
                        <span>To: {d.to}</span>
                      </div>
                      {!showEditor && (
                        <button
                          onClick={(e) => { e.stopPropagation(); setEditingIdx(i); setEditText(personaliseText(d.body, vars)); }}
                          className="text-[11px] inline-flex items-center gap-1"
                          style={{ color: T.accent }}
                          data-testid={`approval-${approval.id}-edit-${i}`}
                        >
                          <Edit3 size={11} /> Edit
                        </button>
                      )}
                    </div>
                    {d.subject && !showEditor && (
                      <div className="text-sm font-medium mb-2" style={{ color: T.ink }}>
                        {personaliseText(d.subject, vars)}
                      </div>
                    )}
                    {showEditor ? (
                      <textarea
                        value={editText}
                        onChange={(e) => setEditText(e.target.value)}
                        className="w-full text-sm rounded-lg p-3 outline-none resize-y"
                        rows={6}
                        style={{ background: T.card, color: T.ink, border: `1px solid ${T.line}`, fontFamily: T.fontUi }}
                        data-testid={`approval-${approval.id}-editor-${i}`}
                      />
                    ) : (
                      <div className="text-sm whitespace-pre-line" style={{ color: T.ink, lineHeight: 1.55 }}>
                        {body}
                      </div>
                    )}
                    {showEditor && (
                      <div className="mt-2 flex gap-2 justify-end">
                        <button
                          onClick={(e) => { e.stopPropagation(); setEditingIdx(-1); }}
                          className="text-xs px-3 py-1.5 rounded-lg"
                          style={{ color: T.muted, background: T.card, border: `1px solid ${T.line}` }}
                        >
                          Cancel
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); setEditingIdx(-1); }}
                          className="text-xs px-3 py-1.5 rounded-lg font-semibold"
                          style={{ background: T.accent, color: '#fff' }}
                        >
                          Save edit
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right rail actions */}
        <div className="shrink-0 flex flex-col items-end gap-2">
          {approved ? (
            <div className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-full"
              style={{ background: 'rgba(74,222,128,0.15)', color: T.success, fontWeight: 600 }}
              data-testid={`approval-${approval.id}-approved`}>
              <Check size={12} strokeWidth={3} /> Sent · ARIA handled it
            </div>
          ) : (
            <button
              onClick={handleApprove}
              className="inline-flex items-center gap-1.5 text-sm px-3 py-2 rounded-lg transition-all active:scale-95"
              style={{ background: T.accent, color: '#fff', fontWeight: 600, boxShadow: '0 4px 14px rgba(124,53,220,0.28)' }}
              data-testid={`approval-${approval.id}-approve`}
            >
              <Check size={14} strokeWidth={2.5} /> Approve
            </button>
          )}
          <button
            onClick={() => setExpanded((v) => !v)}
            className="text-xs inline-flex items-center gap-1 transition-colors"
            style={{ color: T.muted }}
            data-testid={`approval-${approval.id}-toggle`}
          >
            {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            {expanded ? 'Hide' : `Review ${approval.drafts.length}`}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────── helpers ───────────────────────
function formatMoney(v) {
  if (v >= 1000000) return `$${(v / 1000000).toFixed(2)}M`;
  if (v >= 1000)    return `$${(v / 1000).toFixed(1)}K`;
  return `$${Math.round(v).toLocaleString()}`;
}
