/**
 * AriaTourModal — 30-second first-login product tour.
 *
 * Walks new tenants through Aria's 4 pillars in 5 short steps:
 *   1. Welcome  →  what Aria is, in one sentence
 *   2. Command Center   →  daily workspace
 *   3. 32-Touchpoint Journey  →  the sales engine
 *   4. Train Aria        →  giving Aria a voice + brain
 *   5. Integrations      →  plug in lead sources
 *
 * Triggered automatically once per user (localStorage gate). User can
 * skip any time, restart from the AriaModeChip context menu (future), or
 * trigger manually via `?tour=1` query param for re-runs.
 *
 * No backend — purely a client-side guided walkthrough overlay.
 */
import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Sparkle, ArrowRight, ArrowLeft, X, House, MapTrifold,
  GraduationCap, Plug, Rocket,
} from '@phosphor-icons/react';
import { useAuth } from '../context/AuthContext';
import api from '../config/api';

const STORAGE_KEY = 'aria.tour.completed.v1';
// iter109 — accept either localStorage key so e2e tests can pre-seed without
// knowing the internal versioned name. Both are honored as "tour seen".
const STORAGE_KEY_ALIAS = 'aria_tour_completed';

const STEPS = [
  {
    key: 'welcome',
    icon: Rocket,
    eyebrow: 'Welcome to Aria',
    title: 'Your AI sales PA — built for founders.',
    body: 'Aria captures leads from every channel, qualifies them, drafts replies, follows up, and books calls — so you can focus on closing instead of chasing.',
    illustration: 'sparkle',
  },
  {
    key: 'command_center',
    icon: House,
    eyebrow: 'Step 1 · Command Center',
    title: 'See what needs attention today.',
    body: 'Your homepage is the daily Aria brief: hot leads, conversations in flight, what\'s gone cold, and what Aria recommends you do next. Check it every morning.',
    cta: { label: 'Open Command Center', to: '/' },
    illustration: 'home',
  },
  {
    key: 'journey',
    icon: MapTrifold,
    eyebrow: 'Step 2 · 32-Touchpoint Journey',
    title: 'Aria runs a 32-step sales sequence per lead.',
    body: 'From first reply to booked call — across 5 stages (First Contact → Education → Nurture → Conversion → Revival). You customize each touch; Aria fires them on schedule.',
    cta: { label: 'See the journey', to: '/touchpoint-journey' },
    illustration: 'map',
  },
  {
    key: 'train',
    icon: GraduationCap,
    eyebrow: 'Step 3 · Train Aria',
    title: 'Teach Aria your voice, ICP, and pricing.',
    body: 'The more context you give, the sharper every reply. Aim for 80%+ training completion before going live — most founders finish this in 15 minutes.',
    cta: { label: 'Train Aria now', to: '/aria-agent/train' },
    illustration: 'brain',
  },
  {
    key: 'integrations',
    icon: Plug,
    eyebrow: 'Step 4 · Connect lead sources',
    title: 'Plug in WhatsApp, your website, and ad accounts.',
    body: 'Aria reads inbound leads from every channel you connect. Most founders start with WhatsApp + website form and add Meta/Google Ads later.',
    cta: { label: 'Open Integrations', to: '/integrations' },
    illustration: 'plug',
    isFinal: true,
  },
];

const AriaTourModal = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { user } = useAuth();
  const forceTour = searchParams.get('tour') === '1';
  // Capture forceTour at mount — once true, stays true for the lifetime of this
  // modal session so the URL-strip effect can't accidentally re-trigger the
  // auto-dismiss path (iter151 race fix).
  const forceTourLockedRef = useRef(forceTour);
  // iter150-B (P1) — gate first on the backend-persisted `tour_completed_at`
  // so returning founders (fresh browser/device, no localStorage) don't see
  // the welcome modal again and have the sidebar blocked. localStorage stays
  // as a fast secondary gate (no flicker before /auth/me hydrates).
  const [open, setOpen] = useState(() => {
    if (forceTour) return true;
    const localSeen = localStorage.getItem(STORAGE_KEY) === '1' ||
                      localStorage.getItem(STORAGE_KEY_ALIAS) === 'true';
    return !localSeen;
  });
  const [idx, setIdx] = useState(0);

  // When the auth context hydrates, close the tour if the backend says it
  // was already completed (covers fresh-browser logins where localStorage
  // is empty but the user finished the tour previously). Skipped when the
  // tour was force-launched via ?tour=1 — the user explicitly wants to re-run.
  useEffect(() => {
    if (forceTourLockedRef.current) return;
    if (user?.tour_completed_at) {
      localStorage.setItem(STORAGE_KEY, '1');
      localStorage.setItem(STORAGE_KEY_ALIAS, 'true');
      setOpen(false);
    }
  }, [user?.tour_completed_at]);

  // Strip ?tour=1 from URL once we open it, so refresh doesn't re-trigger
  useEffect(() => {
    if (forceTour && open) {
      setSearchParams((sp) => { const next = new URLSearchParams(sp); next.delete('tour'); return next; }, { replace: true });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [forceTour]);

  // Lock body scroll while open
  useEffect(() => {
    if (open) {
      const orig = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      return () => { document.body.style.overflow = orig; };
    }
  }, [open]);

  if (!open) return null;

  const step = STEPS[idx];
  const Icon = step.icon;
  const isFirst = idx === 0;
  const isLast = idx === STEPS.length - 1;

  const complete = (navigateTo) => {
    localStorage.setItem(STORAGE_KEY, '1');
    localStorage.setItem(STORAGE_KEY_ALIAS, 'true');
    setOpen(false);
    // Persist on the backend so other devices/browsers don't re-show the tour.
    // Fire-and-forget — UI never blocks on this.
    api.post('/api/auth/me/tour-complete').catch(() => {});
    if (navigateTo) navigate(navigateTo);
  };

  const next = () => {
    if (isLast) {
      complete(step.cta?.to);
    } else {
      setIdx((i) => i + 1);
    }
  };

  const skip = () => complete();

  return (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4 aria-fade-up"
      style={{ background: 'rgba(20, 8, 42, 0.55)', backdropFilter: 'blur(8px)' }}
      data-testid="aria-tour-modal"
      role="dialog"
      aria-modal="true"
    >
      <div
        className="relative w-full max-w-lg rounded-3xl overflow-hidden bg-white shadow-2xl border border-white/40"
        style={{ boxShadow: '0 30px 80px rgba(124, 53, 220, 0.35)' }}
      >
        {/* Top hero band */}
        <div
          className="relative h-32 flex items-center justify-center overflow-hidden"
          style={{
            background: 'linear-gradient(135deg, #C044E0 0%, #7C35DC 50%, #5B28D4 100%)',
          }}
        >
          {/* Sparkly grain texture */}
          <div className="absolute inset-0 opacity-40" style={{
            backgroundImage: 'radial-gradient(circle at 20% 30%, rgba(255,255,255,0.4) 1px, transparent 2px), radial-gradient(circle at 80% 60%, rgba(255,255,255,0.3) 1px, transparent 2px), radial-gradient(circle at 50% 90%, rgba(255,255,255,0.35) 1px, transparent 2px)',
            backgroundSize: '60px 60px, 90px 90px, 70px 70px',
          }} />
          <div className="w-16 h-16 rounded-2xl flex items-center justify-center backdrop-blur-md border border-white/30 shadow-lg" style={{ background: 'rgba(255,255,255,0.15)' }}>
            <Icon size={32} weight="fill" className="text-white" data-testid={`tour-icon-${step.key}`} />
          </div>
          <button
            onClick={skip}
            data-testid="aria-tour-close"
            title="Skip tour"
            className="absolute top-3 right-3 w-8 h-8 rounded-full flex items-center justify-center backdrop-blur-md bg-white/15 hover:bg-white/30 transition-colors border border-white/30 text-white"
          >
            <X size={13} weight="bold" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 md:p-7" data-testid={`tour-step-${step.key}`}>
          <div className="text-[10px] font-extrabold uppercase tracking-[0.22em] text-[#7C35DC] mb-1.5">
            {step.eyebrow}
          </div>
          <h2 className="text-xl md:text-2xl font-extrabold text-[#1A0A2E] leading-tight" style={{ fontFamily: 'Plus Jakarta Sans', letterSpacing: '-0.01em' }}>
            {step.title}
          </h2>
          <p className="text-sm text-[#5A4A7A] mt-2.5 leading-relaxed">
            {step.body}
          </p>

          {/* Step pips */}
          <div className="flex items-center gap-1.5 mt-5" data-testid="tour-progress">
            {STEPS.map((s, i) => (
              <button
                key={s.key}
                onClick={() => setIdx(i)}
                data-testid={`tour-pip-${i}`}
                className={`h-1.5 rounded-full transition-all ${
                  i === idx ? 'w-7' : i < idx ? 'w-3' : 'w-3'
                }`}
                style={{
                  background: i === idx
                    ? 'linear-gradient(90deg, #C044E0 0%, #5B28D4 100%)'
                    : i < idx ? '#C9B6FF' : '#E8E0F5',
                }}
              />
            ))}
          </div>

          {/* Footer actions */}
          <div className="flex items-center justify-between gap-3 mt-6">
            <div>
              {!isFirst && (
                <button
                  onClick={() => setIdx((i) => i - 1)}
                  data-testid="aria-tour-back"
                  className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-bold text-[#5A4A7A] hover:text-[#1A0A2E] transition-colors"
                  style={{ fontFamily: 'Plus Jakarta Sans' }}
                >
                  <ArrowLeft size={11} weight="bold" /> Back
                </button>
              )}
            </div>
            <div className="flex items-center gap-2">
              {!isLast && (
                <button
                  onClick={skip}
                  data-testid="aria-tour-skip"
                  className="px-3 py-2 text-xs font-bold text-[#9B8AB0] hover:text-[#1A0A2E] transition-colors"
                  style={{ fontFamily: 'Plus Jakarta Sans' }}
                >
                  Skip tour
                </button>
              )}
              <button
                onClick={next}
                data-testid="aria-tour-next"
                className="inline-flex items-center gap-1.5 px-4 py-2 btn-gradient rounded-lg text-xs font-extrabold text-white shadow-md"
                style={{ fontFamily: 'Plus Jakarta Sans' }}
              >
                {isLast ? (step.cta?.label || 'Get started') : 'Next'} <ArrowRight size={11} weight="bold" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AriaTourModal;
