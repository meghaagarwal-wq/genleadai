/**
 * JourneyStagesHero — explainer banner for the 32-touchpoint journey page.
 *
 * Sits at the top of /touchpoint-journey to communicate the product story:
 *   First Contact → Education → Nurture → Conversion → Revival.
 *
 * Real progress is computed from the in-memory `draft` array — for each
 * stage we tag the touchpoint by index range and show how many the
 * founder has configured vs the recommended count.
 */
import React from 'react';
import { Sparkle, ChatCircle, BookOpen, Heart, CheckCircle, ArrowsClockwise } from '@phosphor-icons/react';

export const STAGES = [
  { key: 'first_contact', label: 'First Contact', range: [0, 3],  icon: ChatCircle,       tint: '#7C35DC', sub: 'Instant reply · introduction · first qualifier.' },
  { key: 'education',     label: 'Education',     range: [4, 9],  icon: BookOpen,         tint: '#0055FF', sub: 'Brochure · pitch deck · case study · proof.' },
  { key: 'nurture',       label: 'Nurture',       range: [10, 17], icon: Heart,           tint: '#C044E0', sub: 'Follow-ups · objection handling · social proof.' },
  { key: 'conversion',    label: 'Conversion',    range: [18, 25], icon: CheckCircle,     tint: '#16A34A', sub: 'Demo invite · pricing · calendar · founder handoff.' },
  { key: 'revival',       label: 'Revival',       range: [26, 31], icon: ArrowsClockwise, tint: '#D97706', sub: 'Re-engage · new offer · soft close · archive.' },
];

const JourneyStagesHero = ({ draft = [] }) => {
  const counts = STAGES.map((s) => {
    const [a, b] = s.range;
    const inRange = draft.filter((t, i) => i >= a && i <= b).length;
    const recommended = b - a + 1;
    return { ...s, configured: inRange, recommended };
  });

  return (
    <div
      className="relative overflow-hidden rounded-2xl border border-[#E8E0F5] p-5 md:p-6 aria-fade-up"
      style={{
        background: 'linear-gradient(135deg, #FFFFFF 0%, #FAF7FF 50%, #FFF8EA 100%)',
        boxShadow: '0 12px 32px rgba(124,53,220,0.06)',
      }}
      data-testid="journey-stages-hero"
    >
      <div className="relative flex items-start justify-between flex-wrap gap-3 mb-4">
        <div className="flex-1 min-w-0">
          <div className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC] mb-2">
            <Sparkle size={11} weight="fill" /> Aria's core engine
          </div>
          <h2 className="text-xl md:text-2xl font-extrabold text-[#1A0A2E] leading-tight" style={{ fontFamily: 'Plus Jakarta Sans', letterSpacing: '-0.01em' }}>
            The 32-touchpoint sales journey
          </h2>
          <p className="text-sm text-[#5A4A7A] mt-1.5 max-w-2xl leading-relaxed">
            Aria doesn't just reply once. She manages the full conversation from first interest to booked call across 5 stages — and you stay in control at every step.
          </p>
        </div>
        <div className="text-right">
          <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#9B8AB0]">Configured</div>
          <div className="text-2xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>
            {draft.length}<span className="text-base text-[#9B8AB0] font-bold"> / 32</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-2 relative">
        {counts.map((s, idx) => {
          const Icon = s.icon;
          const isFull = s.configured >= s.recommended;
          return (
            <div
              key={s.key}
              data-testid={`journey-stage-${s.key}`}
              className="relative bg-white/85 backdrop-blur rounded-xl p-3 border transition-all hover:shadow-md hover:-translate-y-0.5"
              style={{ borderColor: s.tint + '33', boxShadow: '0 4px 12px rgba(26,10,46,0.04)' }}
            >
              <div className="flex items-center gap-1.5 mb-1.5">
                <div
                  className="w-6 h-6 rounded-md flex items-center justify-center"
                  style={{ background: s.tint + '15', border: `1px solid ${s.tint}33` }}
                >
                  <Icon size={11} weight="fill" style={{ color: s.tint }} />
                </div>
                <span className="text-[9px] font-extrabold uppercase tracking-[0.18em] text-[#9B8AB0]" style={{ fontFamily: 'Plus Jakarta Sans' }}>
                  Stage {idx + 1}
                </span>
              </div>
              <div className="text-sm font-extrabold text-[#1A0A2E] leading-tight" style={{ fontFamily: 'Plus Jakarta Sans' }}>{s.label}</div>
              <p className="text-[10px] text-[#5A4A7A] mt-1 leading-snug line-clamp-2">{s.sub}</p>
              <div className="flex items-center justify-between mt-2 pt-2 border-t border-[#F0ECF9]">
                <span className="text-[9px] font-bold uppercase tracking-wider text-[#9B8AB0]">{s.range[0] + 1}–{s.range[1] + 1}</span>
                <span
                  className="text-[10px] font-extrabold px-1.5 py-0.5 rounded-full"
                  style={{
                    color: isFull ? '#16A34A' : s.tint,
                    background: (isFull ? '#16A34A' : s.tint) + '15',
                    border: `1px solid ${(isFull ? '#16A34A' : s.tint)}33`,
                  }}
                >
                  {s.configured}/{s.recommended}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default JourneyStagesHero;
