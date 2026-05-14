/**
 * TrainingCompletionCard — sticky progress strip for the /train-aria page.
 *
 * Computes a completion % from the training payload by counting how many of
 * the 18 core fields are filled. Shows which sections still need attention
 * so the founder knows what to fill next.
 *
 * Pure derivation — no extra backend call. Single prop: the live `data` state.
 */
import React from 'react';
import { CheckCircle, Warning, GraduationCap } from '@phosphor-icons/react';

const SECTIONS = [
  { key: 'business', label: 'Business Context', fields: ['what_you_sell','who_you_sell_to','problem_you_solve','differentiator','main_offerings'] },
  { key: 'icp',      label: 'ICP',              fields: ['target_industries','target_roles','company_size','geography','intent_signals'] },
  { key: 'qual',     label: 'Qualification',    fields: ['qualifying_questions','qualified_definition','when_to_book_call'] },
  { key: 'voice',    label: 'Brand Voice',      fields: ['tone','custom_voice'] },
  { key: 'objections', label: 'Objections',     fields: ['pricing_objections','timing_objections','custom_faq'] },
  { key: 'booking',  label: 'Booking',          fields: ['calendar_link'] },
];

const isFilled = (v) => v !== undefined && v !== null && String(v).trim().length > 0;

const TrainingCompletionCard = ({ data }) => {
  if (!data) return null;

  const sectionStatus = SECTIONS.map((s) => {
    const filled = s.fields.filter((f) => isFilled(data[f])).length;
    return { ...s, filled, total: s.fields.length, complete: filled === s.fields.length };
  });

  const totalFields = SECTIONS.reduce((n, s) => n + s.fields.length, 0);
  const filledFields = sectionStatus.reduce((n, s) => n + s.filled, 0);
  const pct = Math.round((filledFields / totalFields) * 100);

  // Find the first incomplete section for a friendly nudge
  const missing = sectionStatus.find((s) => !s.complete);
  const nudge = missing
    ? `Add details to ${missing.label} so Aria can ${missing.key === 'business' ? 'speak about your business confidently' : missing.key === 'icp' ? 'score every new lead' : missing.key === 'qual' ? 'know which leads deserve your time' : missing.key === 'voice' ? 'sound like you, not a bot' : missing.key === 'objections' ? 'handle tough questions without freezing' : 'book calls on your calendar'}.`
    : 'Aria is fully trained. Re-edit anytime to refine her replies.';

  // Gradient bar fill
  const tint = pct >= 80 ? '#16A34A' : pct >= 50 ? '#7C35DC' : '#D97706';

  return (
    <div
      className="aria-card-lift bg-white border border-[#E8E0F5] rounded-2xl p-5 mb-6"
      style={{ boxShadow: 'var(--shadow-card)' }}
      data-testid="training-completion-card"
    >
      <div className="flex items-center justify-between flex-wrap gap-3 mb-3">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: 'var(--gradient-brand)' }}>
            <GraduationCap size={16} weight="fill" className="text-white" />
          </div>
          <div>
            <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#9B8AB0]">Aria Training</div>
            <div className="text-base font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>
              {pct}% complete
              <span className="text-xs text-[#9B8AB0] font-bold ml-1.5">· {filledFields} of {totalFields} fields</span>
            </div>
          </div>
        </div>
        <span
          className="text-[10px] font-extrabold uppercase tracking-[0.18em] px-2.5 py-1 rounded-full"
          style={{ color: tint, background: tint + '15', border: `1px solid ${tint}33` }}
          data-testid="training-tier-badge"
        >
          {pct >= 80 ? 'Aria is sharp' : pct >= 50 ? 'Getting there' : 'Needs more context'}
        </span>
      </div>

      <div className="h-2 rounded-full bg-[#F0ECF9] overflow-hidden" data-testid="training-progress-bar">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: 'linear-gradient(90deg, #C044E0 0%, #7C35DC 50%, #5B28D4 100%)' }}
        />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-6 gap-1.5 mt-4">
        {sectionStatus.map((s) => (
          <div
            key={s.key}
            data-testid={`training-section-${s.key}`}
            className={`rounded-lg border px-2 py-1.5 flex items-center gap-1.5 transition-all ${
              s.complete ? 'bg-[#DCFCE7]/40 border-[#16A34A]/30' : 'bg-[#FEF3C7]/30 border-[#D97706]/25'
            }`}
          >
            {s.complete ? (
              <CheckCircle size={11} weight="fill" className="text-[#16A34A] flex-shrink-0" />
            ) : (
              <Warning size={11} weight="fill" className="text-[#D97706] flex-shrink-0" />
            )}
            <div className="min-w-0">
              <div className="text-[10px] font-extrabold uppercase tracking-wider text-[#5A4A7A] truncate" style={{ fontFamily: 'Plus Jakarta Sans' }}>{s.label}</div>
              <div className="text-[9px] font-bold text-[#9B8AB0]">{s.filled}/{s.total}</div>
            </div>
          </div>
        ))}
      </div>

      <p className="text-[11px] text-[#5A4A7A] mt-3 leading-relaxed" data-testid="training-aria-nudge">
        <span className="font-bold text-[#7C35DC]">Aria says:</span> {nudge}
      </p>
    </div>
  );
};

export default TrainingCompletionCard;
