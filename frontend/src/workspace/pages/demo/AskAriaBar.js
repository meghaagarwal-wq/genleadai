/**
 * AskAriaBar — iter174
 *
 * A canned-but-smart Q&A bar on the demo. Prospect picks one of 3
 * questions, ARIA responds with a rich, data-backed reply, and a
 * matching drafted-action card is added to Approvals.
 *
 * Scope is deliberately tight — canned questions only — so it never
 * flops on stage.
 */
import React, { useState } from 'react';
import { Sparkles, MessageSquare, Plus, Check, X, ChevronRight } from 'lucide-react';
import { ASK_ARIA_QUESTIONS, askAria } from '../../demoData/askAriaQA';

export default function AskAriaBar({ mode, onAddAction, T }) {
  const [open, setOpen] = useState(false);
  const [reply, setReply] = useState(null);       // { question, ...answer }
  const [added, setAdded] = useState(false);

  const ask = (q) => {
    const answer = askAria(q.id, mode);
    if (!answer) return;
    setReply({ question: q.label, ...answer });
    setAdded(false);
    setOpen(true);
  };

  const addAction = () => {
    if (!reply || added) return;
    const card = {
      id: `ask-${Date.now()}`,
      ...reply.action,
    };
    onAddAction && onAddAction(card);
    setAdded(true);
    // Auto-close after 900ms so the "sent" feedback is felt
    setTimeout(() => setOpen(false), 900);
  };

  return (
    <>
      <div className="rounded-2xl p-4" style={{ background: T.card, border: `1px solid ${T.line}` }} data-testid="ask-aria-bar">
        <div className="flex items-center gap-3 flex-wrap">
          <div className="inline-flex items-center gap-2 text-sm px-2.5 py-1 rounded-full font-medium shrink-0"
            style={{ background: T.accentSoft, color: T.accent, fontWeight: 600 }}>
            <Sparkles size={12} /> Ask ARIA
          </div>
          <div className="flex items-center gap-2 flex-wrap flex-1">
            {ASK_ARIA_QUESTIONS.map((q) => (
              <button
                key={q.id}
                onClick={() => ask(q)}
                data-testid={`ask-aria-q-${q.id}`}
                className="text-sm px-3 py-2 rounded-lg text-left inline-flex items-center gap-2 transition-colors"
                style={{ background: T.canvas, color: T.ink, border: `1px solid ${T.line}` }}
              >
                <MessageSquare size={12} style={{ color: T.muted }} /> {q.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {open && reply && (
        <div
          className="fixed inset-0 z-[55] flex items-center justify-center p-6"
          style={{ background: 'rgba(11,10,20,0.65)', backdropFilter: 'blur(8px)' }}
          onClick={() => setOpen(false)}
          data-testid="ask-aria-modal"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-[620px] rounded-3xl overflow-hidden"
            style={{ background: T.card, border: `1px solid ${T.line}`, boxShadow: '0 40px 120px rgba(124,53,220,0.24)' }}
          >
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="inline-flex items-center gap-2 text-xs px-2.5 py-1 rounded-full uppercase tracking-[0.14em]"
                  style={{ background: T.accentSoft, color: T.accent, fontWeight: 700 }}>
                  <Sparkles size={11} /> ARIA
                </div>
                <button onClick={() => setOpen(false)} className="w-8 h-8 rounded-full flex items-center justify-center hover:bg-white/5" style={{ color: T.muted }} data-testid="ask-aria-close">
                  <X size={16} />
                </button>
              </div>
              <div className="text-xs mb-2" style={{ color: T.muted }}>Q: {reply.question}</div>
              <h3 className="text-[20px] font-semibold tracking-tight leading-snug"
                style={{ fontFamily: T.fontDisplay, color: T.ink }}
                data-testid="ask-aria-headline">
                {reply.headline}
              </h3>
              <ul className="mt-4 space-y-2">
                {reply.bullets.map((b, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm" style={{ color: T.ink }}>
                    <span className="w-1.5 h-1.5 mt-2 rounded-full shrink-0" style={{ background: T.accent }} />
                    <span>{b}</span>
                  </li>
                ))}
              </ul>

              <div className="mt-6 rounded-xl p-4"
                style={{ background: T.canvas, border: `1px solid ${T.line}` }}>
                <div className="text-[11px] uppercase tracking-[0.14em] mb-2" style={{ color: T.muted, fontWeight: 600 }}>
                  I drafted this action for you
                </div>
                <div className="text-sm font-semibold" style={{ color: T.ink }}>{reply.action.title}</div>
                <div className="text-xs mt-1" style={{ color: T.muted }}>{reply.action.why}</div>
                <div className="mt-3 flex items-center justify-between gap-3 flex-wrap">
                  <div className="text-xs" style={{ color: T.accent, fontWeight: 600 }}>{reply.action.value}</div>
                  <button
                    onClick={addAction}
                    disabled={added}
                    data-testid="ask-aria-add-action"
                    className="text-sm inline-flex items-center gap-1.5 px-3 py-2 rounded-lg font-semibold transition-all active:scale-95 disabled:opacity-70"
                    style={{ background: added ? T.success : T.accent, color: '#fff' }}
                  >
                    {added ? <><Check size={14} strokeWidth={3} /> Added to Approvals</> : <><Plus size={14} strokeWidth={2.5} /> Add to Approvals</>}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
