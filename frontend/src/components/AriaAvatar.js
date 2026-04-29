import React from 'react';

/**
 * ARIA — Custom SVG robot avatar with idle animations.
 *
 * Animations:
 *  - Soft outer halo pulse (faster when tone='urgent')
 *  - Subtle breathing scale on the head (4s loop)
 *  - Eye blink every ~4s
 *  - Antenna LED twinkle
 *
 * Props:
 *  - size: pixel size (default 40)
 *  - tone: 'default' | 'urgent' | 'soft' — controls halo color & pulse cadence
 *  - showHalo: boolean — enable pulsing glow ring
 */
const AriaAvatar = ({ size = 40, tone = 'default', showHalo = true, className = '' }) => {
  const palette = {
    default: { from: '#C044E0', to: '#7C35DC', halo: '#C044E0', pulseDur: '3.6s' },
    urgent: { from: '#FF5566', to: '#C044E0', halo: '#FF5566', pulseDur: '1.8s' },
    soft: { from: '#E0D4F7', to: '#7C35DC', halo: '#7C35DC', pulseDur: '4.8s' },
  }[tone] || {};

  const id = React.useId();

  return (
    <span className={`aria-avatar ${className}`} style={{ display: 'inline-block', width: size, height: size, position: 'relative' }} data-testid="aria-avatar">
      <style>{`
        @keyframes aria-halo-${id} {
          0%, 100% { transform: scale(0.95); opacity: 0.45; }
          50% { transform: scale(1.18); opacity: 0; }
        }
        @keyframes aria-breathe-${id} {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.025); }
        }
        @keyframes aria-blink-${id} {
          0%, 92%, 100% { transform: scaleY(1); }
          94%, 98% { transform: scaleY(0.05); }
        }
        @keyframes aria-led-${id} {
          0%, 100% { opacity: 0.4; }
          50% { opacity: 1; }
        }
        .aria-halo-${id} { animation: aria-halo-${id} ${palette.pulseDur} cubic-bezier(0.4,0,0.6,1) infinite; transform-origin: center; }
        .aria-head-${id} { animation: aria-breathe-${id} 4.2s ease-in-out infinite; transform-origin: center; }
        .aria-eye-${id} { animation: aria-blink-${id} 5.2s ease-in-out infinite; transform-origin: center; transform-box: fill-box; }
        .aria-led-${id} { animation: aria-led-${id} 1.6s ease-in-out infinite; }
      `}</style>
      <svg viewBox="0 0 100 100" width={size} height={size} style={{ overflow: 'visible' }}>
        <defs>
          <linearGradient id={`grad-${id}`} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={palette.from} />
            <stop offset="100%" stopColor={palette.to} />
          </linearGradient>
          <radialGradient id={`shine-${id}`} cx="35%" cy="30%" r="40%">
            <stop offset="0%" stopColor="rgba(255,255,255,0.55)" />
            <stop offset="100%" stopColor="rgba(255,255,255,0)" />
          </radialGradient>
          <filter id={`glow-${id}`} x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="2.5" />
          </filter>
        </defs>

        {/* Halo pulse */}
        {showHalo && (
          <circle cx="50" cy="50" r="46" fill="none" stroke={palette.halo} strokeWidth="1.5" className={`aria-halo-${id}`} opacity="0.4" />
        )}

        {/* Antenna stalk */}
        <line x1="50" y1="14" x2="50" y2="22" stroke={`url(#grad-${id})`} strokeWidth="2.5" strokeLinecap="round" />
        {/* Antenna LED with twinkle */}
        <circle cx="50" cy="11" r="3" fill={palette.halo} className={`aria-led-${id}`} filter={`url(#glow-${id})`} />
        <circle cx="50" cy="11" r="2" fill="#fff" opacity="0.9" />

        {/* Head */}
        <g className={`aria-head-${id}`}>
          {/* Outer head shape */}
          <rect x="22" y="22" width="56" height="56" rx="20" fill={`url(#grad-${id})`} />
          {/* Glassy shine */}
          <rect x="22" y="22" width="56" height="56" rx="20" fill={`url(#shine-${id})`} />

          {/* Eye sockets */}
          <ellipse cx="40" cy="50" rx="6" ry="7" fill="rgba(0,0,0,0.18)" />
          <ellipse cx="60" cy="50" rx="6" ry="7" fill="rgba(0,0,0,0.18)" />

          {/* Eyes (with blink) */}
          <ellipse cx="40" cy="50" rx="3.2" ry="4.5" fill="#fff" className={`aria-eye-${id}`} />
          <ellipse cx="60" cy="50" rx="3.2" ry="4.5" fill="#fff" className={`aria-eye-${id}`} />
          {/* Eye sparkle */}
          <circle cx="41.2" cy="48.5" r="0.9" fill={palette.from} opacity="0.9" />
          <circle cx="61.2" cy="48.5" r="0.9" fill={palette.from} opacity="0.9" />

          {/* Mouth — minimal smile */}
          <path d="M 42 64 Q 50 67 58 64" stroke="rgba(255,255,255,0.85)" strokeWidth="1.8" strokeLinecap="round" fill="none" />

          {/* Side bolts */}
          <circle cx="20" cy="42" r="2" fill="rgba(255,255,255,0.4)" />
          <circle cx="80" cy="42" r="2" fill="rgba(255,255,255,0.4)" />
          <circle cx="20" cy="58" r="2" fill="rgba(255,255,255,0.4)" />
          <circle cx="80" cy="58" r="2" fill="rgba(255,255,255,0.4)" />
        </g>
      </svg>
    </span>
  );
};

export default AriaAvatar;
