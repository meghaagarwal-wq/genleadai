/**
 * PrefillPrompt — iter177
 *
 * A soft, delayed in-demo modal asking for the prospect's name + email
 * so booking is one click (we prefill Calendly). Shows after 120s of
 * dwell when the prospect hasn't yet given us their identity.
 *
 * Not aggressive: dismiss persists for 7 days.
 */
import React, { useState } from 'react';
import { Sparkles, X, ArrowRight, Check } from 'lucide-react';

export default function PrefillPrompt({ open, onClose, onSubmit, brand, T }) {
  const [name, setName]   = useState('');
  const [email, setEmail] = useState('');
  const [done, setDone]   = useState(false);
  if (!open) return null;

  const submit = (e) => {
    e?.preventDefault();
    const em = email.trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(em)) return;
    const ident = { name: name.trim(), email: em };
    setDone(true);
    onSubmit(ident);
    setTimeout(() => onClose(true), 900);
  };

  return (
    <div
      className="fixed inset-0 z-[57] flex items-end sm:items-center justify-center p-4"
      style={{ background: 'rgba(11,10,20,0.4)', backdropFilter: 'blur(4px)' }}
      data-testid="prefill-prompt"
    >
      <div
        className="w-full max-w-[420px] rounded-3xl overflow-hidden"
        style={{
          background: T.card, border: `1px solid ${T.line}`,
          boxShadow: '0 30px 80px rgba(124,53,220,0.22), 0 8px 24px rgba(0,0,0,0.15)',
        }}
      >
        <div className="relative p-6">
          <div aria-hidden className="absolute -top-20 -right-20 w-56 h-56 rounded-full pointer-events-none"
            style={{ background: 'radial-gradient(closest-side, rgba(164,111,232,0.22), transparent 70%)' }} />
          <button
            onClick={() => onClose(false)}
            className="absolute top-3 right-3 w-8 h-8 rounded-full flex items-center justify-center transition-colors hover:bg-black/5"
            style={{ color: T.muted }}
            aria-label="Dismiss"
            data-testid="prefill-dismiss"
          >
            <X size={16} />
          </button>
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full text-[10px] uppercase tracking-[0.14em] mb-4"
            style={{ background: T.accentSoft, color: T.accent, fontWeight: 700 }}>
            <Sparkles size={11} /> One-tap booking
          </div>
          {done ? (
            <div className="py-8 text-center">
              <div className="inline-flex items-center justify-center w-12 h-12 rounded-full mb-3"
                style={{ background: 'rgba(74,222,128,0.15)', color: T.success }}>
                <Check size={22} strokeWidth={3} />
              </div>
              <div className="text-[18px] font-semibold" style={{ color: T.ink, fontFamily: T.fontDisplay }}>
                Thanks{name ? `, ${name.split(' ')[0]}` : ''}.
              </div>
              <div className="text-sm mt-1" style={{ color: T.muted }}>
                Booking is now one tap when you're ready.
              </div>
            </div>
          ) : (
            <>
              <h3 className="text-[20px] leading-tight font-semibold tracking-tight"
                style={{ color: T.ink, fontFamily: T.fontDisplay, letterSpacing: '-0.01em' }}>
                Who's exploring today?
              </h3>
              <p className="text-sm mt-1" style={{ color: T.muted }}>
                Tell me your name and email once — booking a walkthrough with {brand?.companyName ? <strong style={{ color: T.ink }}>{brand.companyName}</strong> : 'your team'} becomes a single click, nothing to retype on Calendly.
              </p>
              <form onSubmit={submit} className="mt-5 space-y-2">
                <input
                  autoFocus
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Your name"
                  className="w-full px-3 py-2.5 rounded-lg text-sm outline-none"
                  style={{ background: T.canvas, color: T.ink, border: `1px solid ${T.line}` }}
                  data-testid="prefill-name"
                />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Your email"
                  className="w-full px-3 py-2.5 rounded-lg text-sm outline-none"
                  style={{ background: T.canvas, color: T.ink, border: `1px solid ${T.line}` }}
                  data-testid="prefill-email"
                />
                <button
                  type="submit"
                  disabled={!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())}
                  data-testid="prefill-submit"
                  className="w-full mt-2 inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all active:scale-95 disabled:opacity-50"
                  style={{ background: T.accent, color: '#fff' }}
                >
                  Save & keep exploring <ArrowRight size={14} strokeWidth={2.5} />
                </button>
                <button
                  type="button"
                  onClick={() => onClose(false)}
                  className="w-full text-xs mt-1 py-1"
                  style={{ color: T.muted }}
                >
                  Maybe later
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
