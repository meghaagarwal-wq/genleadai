import React from 'react';
import { ArrowRight } from '@phosphor-icons/react';
import { useNavigate } from 'react-router-dom';
import AriaAvatar from './AriaAvatar';

/**
 * "ARIA says ..." premium insight card — matches genleadai.com hero treatment.
 * Now includes an animated robot avatar and a subtle ambient pulse-glow.
 */
const AriaInsightCard = ({ title = 'ARIA Daily Brief', message, ctaLabel, ctaTo, onCtaClick, tone = 'default' }) => {
  const navigate = useNavigate();
  const toneStyles = {
    default: { bgFrom: '#0E0820', bgTo: '#2A155A', accent: '#C044E0', glow: 'rgba(192,68,224,0.35)', pulseDur: '4.2s' },
    urgent: { bgFrom: '#1A0820', bgTo: '#3A1024', accent: '#FF5566', glow: 'rgba(255,85,102,0.45)', pulseDur: '2.4s' },
  }[tone] || {};

  const handleClick = () => {
    if (onCtaClick) return onCtaClick();
    if (ctaTo) navigate(ctaTo);
  };

  const id = React.useId();

  return (
    <div
      className="relative rounded-2xl overflow-hidden p-5 md:p-6 text-white"
      style={{
        background: `linear-gradient(135deg, ${toneStyles.bgFrom} 0%, ${toneStyles.bgTo} 100%)`,
        boxShadow: `0 8px 32px rgba(20,8,40,0.25), 0 0 0 1px rgba(192,68,224,0.08)`,
      }}
      data-testid="aria-insight-card"
    >
      <style>{`
        @keyframes aria-card-pulse-${id} {
          0%, 100% { box-shadow: 0 0 0 rgba(0,0,0,0), inset 0 0 0 1px rgba(255,255,255,0.04); opacity: 0.5; }
          50% { box-shadow: 0 0 60px ${toneStyles.glow}, inset 0 0 0 1px rgba(255,255,255,0.08); opacity: 1; }
        }
        @keyframes aria-orb-${id} {
          0%, 100% { transform: translate(0, 0) scale(1); opacity: 0.25; }
          50% { transform: translate(8px, -6px) scale(1.15); opacity: 0.45; }
        }
        .aria-card-pulse-${id} {
          position: absolute;
          inset: 0;
          border-radius: 1rem;
          pointer-events: none;
          animation: aria-card-pulse-${id} ${toneStyles.pulseDur} cubic-bezier(0.4,0,0.6,1) infinite;
        }
        .aria-orb-${id} {
          animation: aria-orb-${id} ${toneStyles.pulseDur} cubic-bezier(0.4,0,0.6,1) infinite;
        }
      `}</style>

      {/* Pulse glow layer */}
      <div className={`aria-card-pulse-${id}`} />

      {/* Subtle gradient accent line at top */}
      <div className="absolute top-0 left-0 right-0 h-px" style={{ background: `linear-gradient(90deg, transparent 0%, ${toneStyles.accent} 50%, transparent 100%)`, opacity: 0.7 }} />

      {/* Floating accent orb (decorative) */}
      <div className={`absolute -top-12 -right-12 w-48 h-48 rounded-full pointer-events-none aria-orb-${id}`} style={{ background: `radial-gradient(circle, ${toneStyles.accent} 0%, transparent 70%)` }} />

      <div className="relative flex items-start gap-4">
        <AriaAvatar size={48} tone={tone} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] font-bold uppercase tracking-[0.25em]" style={{ color: toneStyles.accent }}>ARIA says</span>
            <span className="inline-flex items-center gap-1 text-[9px] font-semibold uppercase tracking-wider text-white/50" data-testid="aria-status">
              <span className="w-1.5 h-1.5 rounded-full" style={{ background: '#16D67D', boxShadow: '0 0 6px #16D67D' }} />Online
            </span>
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
