/**
 * InstinctFeedScreen — iter173
 *
 * A LIVE stream. Cards on load, then a new one slides in every 15–25 s
 * (throttled while the tab is hidden). Card kinds map to accent colors
 * and icons. Prospects can dismiss cards to feel like they're pruning.
 */
import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Sparkles, TrendingUp, Users, Award, Snowflake, AlertTriangle, Radar,
  DollarSign, Building2, Zap, CheckCircle2, ArrowUpRight, X,
} from 'lucide-react';
import { personaliseText } from '../../demoData/liveContent';

const KIND_META = {
  intent:     { label: 'Intent',      icon: TrendingUp,   hue: '#A46FE8' },
  hiring:     { label: 'Hiring',      icon: Users,        hue: '#7BC58F' },
  funding:    { label: 'Funding',     icon: DollarSign,   hue: '#F2B84B' },
  competitor: { label: 'Competitor',  icon: Radar,        hue: '#EA9A54' },
  drift:      { label: 'ICP drift',   icon: AlertTriangle,hue: '#F87171' },
  cold:       { label: 'Cold lead',   icon: Snowflake,    hue: '#5FB1B8' },
  signal:     { label: 'Signal',      icon: Sparkles,     hue: '#B892E8' },
  success:    { label: 'Win',         icon: Award,        hue: '#4ADE80' },
  trade:      { label: 'Field',       icon: Building2,    hue: '#E38FB0' },
};

// Deterministic seeded random so demos feel curated
function seedRand(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 0x100000000;
  };
}

export default function InstinctFeedScreen({ templates, brand, mode, T, onNewCard }) {
  const initialSeed = useMemo(() => hashSeed(brand?.companyName + mode), [brand, mode]);
  const [cards, setCards] = useState(() => initialCards(templates, brand, initialSeed));
  const [flashId, setFlashId] = useState(null);
  const timerRef = useRef(null);
  const seqRef = useRef(cards.length);

  // Stream loop — 15–25 s cadence, throttled while hidden
  useEffect(() => {
    const schedule = () => {
      const delay = 15000 + Math.floor(Math.random() * 10000);
      timerRef.current = setTimeout(() => {
        if (!document.hidden) {
          const t = templates[Math.floor(Math.random() * templates.length)];
          const card = enrich(t, brand, ++seqRef.current);
          setCards((prev) => [card, ...prev].slice(0, 40));
          setFlashId(card.id);
          onNewCard && onNewCard(card);
          setTimeout(() => setFlashId(null), 1200);
        }
        schedule();
      }, delay);
    };
    schedule();
    return () => clearTimeout(timerRef.current);
  }, [templates, brand, onNewCard]);

  // On brand/mode change, reset feed to fresh initial batch
  useEffect(() => {
    seqRef.current = 0;
    setCards(initialCards(templates, brand, hashSeed(brand?.companyName + mode)));
  }, [brand, mode, templates]);

  const dismiss = (id) => setCards((prev) => prev.filter((c) => c.id !== id));

  return (
    <div className="pt-6 space-y-6" data-testid="screen-instinct">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <div className="uppercase text-[11px] tracking-[0.14em] mb-2" style={{ color: T.accent, fontWeight: 600 }}>
            Instinct Feed · live
          </div>
          <h2 className="text-[22px] leading-tight tracking-tight font-semibold"
              style={{ fontFamily: T.fontDisplay, color: T.ink }}>
            Signals ARIA is reading right now
          </h2>
          <p className="text-sm mt-1" style={{ color: T.muted }}>
            New signals arrive continuously · each one is a lead your team would have missed.
          </p>
        </div>
        <div className="inline-flex items-center gap-2 text-xs px-3 py-1.5 rounded-full"
          style={{ background: T.accentSoft, color: T.accent, fontWeight: 600 }}
          data-testid="instinct-live-badge">
          <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: T.accent }} />
          {cards.length} signals · streaming
        </div>
      </div>

      <div className="space-y-3">
        {cards.map((c) => (
          <SignalCard
            key={c.id}
            card={c}
            flash={c.id === flashId}
            onDismiss={() => dismiss(c.id)}
            T={T}
          />
        ))}
      </div>
    </div>
  );
}

function SignalCard({ card, flash, onDismiss, T }) {
  const meta = KIND_META[card.kind] || KIND_META.signal;
  const Icon = meta.icon;
  return (
    <div
      className="rounded-2xl p-4 relative"
      style={{
        background: T.card,
        border: `1px solid ${flash ? meta.hue : T.line}`,
        boxShadow: flash ? `0 0 0 3px ${meta.hue}22, 0 8px 24px rgba(124,53,220,0.16)` : 'none',
        transition: 'border-color 300ms ease, box-shadow 300ms ease, transform 300ms ease',
      }}
      data-testid={`signal-${card.id}`}
    >
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
          style={{ background: `${meta.hue}1F`, color: meta.hue }}>
          <Icon size={18} />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="uppercase text-[10px] tracking-[0.14em]"
              style={{ color: meta.hue, fontWeight: 700 }}>
              {meta.label}
            </span>
            {flash && (
              <span className="uppercase text-[10px] tracking-[0.14em] px-1.5 py-0.5 rounded"
                style={{ background: meta.hue, color: '#0B0A14', fontWeight: 700 }}>
                New signal
              </span>
            )}
            <span className="text-[11px]" style={{ color: T.muted }}>
              · confidence {card.weight}%
            </span>
          </div>
          <div className="text-sm font-semibold" style={{ color: T.ink }}>
            {card.title}
          </div>
          <div className="text-sm mt-1" style={{ color: T.muted }}>
            {card.body}
          </div>
          <div className="mt-3 flex items-center gap-3 flex-wrap">
            <button className="text-xs inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-semibold transition-all active:scale-95"
              style={{ background: meta.hue, color: '#0B0A14' }}
              data-testid={`signal-${card.id}-cta`}
            >
              {card.cta} <ArrowUpRight size={12} strokeWidth={2.5} />
            </button>
            <button
              onClick={onDismiss}
              className="text-xs px-2.5 py-1.5 rounded-lg"
              style={{ color: T.muted, background: 'transparent' }}
              data-testid={`signal-${card.id}-dismiss`}
            >
              Dismiss
            </button>
          </div>
        </div>

        <div className="shrink-0 text-[11px]" style={{ color: T.muted }}>
          {card.timeAgo}
        </div>
      </div>
    </div>
  );
}

// ────── data helpers ──────
function hashSeed(s) {
  let h = 2166136261;
  for (const c of s || '') h = ((h ^ c.charCodeAt(0)) * 16777619) >>> 0;
  return h;
}

function enrich(template, brand, seq) {
  const vars = { brand: brand?.companyName || 'your team' };
  return {
    ...template,
    id: `sig-${seq}-${Math.random().toString(36).slice(2, 7)}`,
    title: personaliseText(template.title, vars),
    body: personaliseText(template.body, vars),
    timeAgo: 'just now',
  };
}

function initialCards(templates, brand, seed) {
  const rand = seedRand(seed);
  const shuffled = [...templates].sort(() => rand() - 0.5);
  const take = shuffled.slice(0, 5);
  return take.map((t, i) => ({
    ...enrich(t, brand, i + 1),
    id: `sig-init-${i}`,
    timeAgo: ['1 min ago', '4 min ago', '11 min ago', '22 min ago', '38 min ago'][i] || 'earlier',
  }));
}
