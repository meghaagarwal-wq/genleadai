import React from 'react';
import { Sparkle, ArrowRight } from '@phosphor-icons/react';
import { useNavigate } from 'react-router-dom';

/**
 * "ARIA says ..." premium insight card — matches genleadai.com hero treatment.
 * Used on Dashboard, Follow-Ups, etc. to surface AI-generated guidance.
 */
const AriaInsightCard = ({ title = 'ARIA Daily Brief', message, ctaLabel, ctaTo, onCtaClick, tone = 'default' }) => {
  const navigate = useNavigate();
  const toneStyles = {
    default: { bgFrom: '#0E0820', bgTo: '#2A155A', accent: '#C044E0' },
    urgent: { bgFrom: '#1A0820', bgTo: '#3A1024', accent: '#DC2626' },
  }[tone] || {};

  const handleClick = () => {
    if (onCtaClick) return onCtaClick();
    if (ctaTo) navigate(ctaTo);
  };

  return (
    <div
      className="relative rounded-2xl overflow-hidden p-5 md:p-6 text-white"
      style={{
        background: `linear-gradient(135deg, ${toneStyles.bgFrom} 0%, ${toneStyles.bgTo} 100%)`,
        boxShadow: '0 8px 32px rgba(20,8,40,0.25)',
      }}
      data-testid="aria-insight-card"
    >
      {/* Subtle gradient accent */}
      <div className="absolute top-0 left-0 right-0 h-px" style={{ background: `linear-gradient(90deg, transparent 0%, ${toneStyles.accent} 50%, transparent 100%)`, opacity: 0.6 }} />
      <div className="absolute -top-12 -right-12 w-48 h-48 rounded-full opacity-30" style={{ background: `radial-gradient(circle, ${toneStyles.accent} 0%, transparent 70%)` }} />

      <div className="relative flex items-start gap-4">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: 'linear-gradient(135deg, #C044E0 0%, #7C35DC 100%)' }}>
          <Sparkle size={18} weight="fill" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] font-bold uppercase tracking-[0.25em]" style={{ color: toneStyles.accent }}>ARIA says</span>
          </div>
          <h3 className="text-lg md:text-xl font-extrabold mb-1" style={{ fontFamily: 'Plus Jakarta Sans' }}>{title}</h3>
          <p className="text-sm md:text-[15px] text-white/80 leading-relaxed">{message}</p>
          {(ctaLabel && (ctaTo || onCtaClick)) && (
            <button
              onClick={handleClick}
              className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold border border-white/15 hover:bg-white/10 transition-colors"
              style={{ fontFamily: 'Plus Jakarta Sans', color: '#fff' }}
              data-testid="aria-insight-cta"
            >
              {ctaLabel} <ArrowRight size={12} weight="bold" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default AriaInsightCard;
