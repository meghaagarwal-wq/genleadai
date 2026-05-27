/* Iter104 — AriaBot mascot (converted from .tsx → .jsx, framer-motion). */
import { motion, useReducedMotion } from 'framer-motion';
import { useEffect, useState } from 'react';

export function AriaBot({ size = 220, withBubble = true, waving = false }) {
  const reduce = useReducedMotion();
  const [blink, setBlink] = useState(false);
  const [msgIdx, setMsgIdx] = useState(0);
  const messages = [
    'Scanning 47 prospects…',
    'New signal: funding round 🎯',
    'Drafting reply on WhatsApp',
    'Booked a call for you ✨',
    'Watching LinkedIn for you',
  ];

  useEffect(() => {
    if (reduce) return;
    const id = setInterval(() => {
      setBlink(true);
      setTimeout(() => setBlink(false), 140);
    }, 3200);
    return () => clearInterval(id);
  }, [reduce]);

  useEffect(() => {
    const id = setInterval(() => setMsgIdx((i) => (i + 1) % messages.length), 3000);
    return () => clearInterval(id);
  }, [messages.length]);

  return (
    <div className="relative" style={{ width: size, height: size }} data-testid="aria-bot">
      <div
        className="absolute left-1/2 top-[78%] h-6 w-3/5 -translate-x-1/2 rounded-full bg-black/25 blur-xl"
        style={{ animation: reduce ? undefined : 'aria-float 6s ease-in-out infinite' }}
      />

      {withBubble && (
        <motion.div
          key={msgIdx}
          initial={{ opacity: 0, y: 8, scale: 0.9 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0 }}
          transition={{ type: 'spring', stiffness: 280, damping: 22 }}
          className="absolute -right-2 top-2 max-w-[180px] rounded-2xl rounded-br-sm border border-white/40 bg-white px-3 py-2 text-[11px] font-medium shadow-lg shadow-purple-900/20"
          style={{ color: '#1A103A' }}
        >
          {messages[msgIdx]}
          <span className="absolute -bottom-1 right-3 size-2 rotate-45 border-b border-r border-white/40 bg-white" />
        </motion.div>
      )}

      <motion.div
        className="absolute inset-0 flex items-center justify-center"
        animate={reduce ? {} : { y: [0, -10, 0] }}
        transition={{ duration: 4.5, repeat: Infinity, ease: 'easeInOut' }}
      >
        <BotSVG blink={blink} size={size * 0.78} waving={waving} />
      </motion.div>
    </div>
  );
}

function BotSVG({ blink, size, waving = false }) {
  return (
    <svg viewBox="0 0 200 220" width={size} height={size} fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="bot-body" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffffff" />
          <stop offset="1" stopColor="#f3e8ff" />
        </linearGradient>
        <linearGradient id="bot-screen" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0"   stopColor="#3b0764" />
          <stop offset="0.5" stopColor="#6d28d9" />
          <stop offset="1"   stopColor="#831843" />
        </linearGradient>
        <linearGradient id="bot-accent" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#a855f7" />
          <stop offset="1" stopColor="#ec4899" />
        </linearGradient>
        <radialGradient id="eye-glow" cx="0.5" cy="0.45" r="0.55">
          <stop offset="0"    stopColor="#ffffff" />
          <stop offset="0.55" stopColor="#ffffff" />
          <stop offset="0.85" stopColor="#fdf4ff" />
          <stop offset="1"    stopColor="#7e22ce" />
        </radialGradient>
        <radialGradient id="eye-pupil" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0"   stopColor="#1a103a" />
          <stop offset="0.7" stopColor="#3b0764" />
          <stop offset="1"   stopColor="#581c87" />
        </radialGradient>
        <filter id="bot-shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="6" stdDeviation="6" floodColor="#581c87" floodOpacity="0.35" />
        </filter>
      </defs>

      <line x1="100" y1="38" x2="100" y2="20" stroke="#a855f7" strokeWidth="3" strokeLinecap="round" />
      <motion.circle cx="100" cy="16" r="6" fill="url(#bot-accent)"
        animate={{ scale: [1, 1.3, 1], opacity: [0.7, 1, 0.7] }}
        transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
        style={{ transformOrigin: '100px 16px' }} />
      <motion.circle cx="100" cy="16" r="12" fill="none" stroke="#ec4899" strokeWidth="1.5"
        animate={{ scale: [0.6, 2, 0.6], opacity: [0.6, 0, 0.6] }}
        transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
        style={{ transformOrigin: '100px 16px' }} />

      <g filter="url(#bot-shadow)">
        <rect x="38" y="38" width="124" height="100" rx="32" fill="url(#bot-body)" stroke="#e9d5ff" strokeWidth="2" />
        <rect x="54" y="58" width="92" height="62" rx="20" fill="url(#bot-screen)" />
        <motion.g animate={{ x: [0, 4, -4, 0] }} transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut' }}>
          {blink ? (
            <>
              <rect x="69" y="86" width="20" height="4" rx="2" fill="#ffffff" />
              <rect x="111" y="86" width="20" height="4" rx="2" fill="#ffffff" />
            </>
          ) : (
            <>
              {/* sclera (white of the eye) */}
              <circle cx="81"  cy="86" r="11" fill="url(#eye-glow)" />
              <circle cx="119" cy="86" r="11" fill="url(#eye-glow)" />
              {/* iris / pupil */}
              <circle cx="81"  cy="87" r="6"   fill="url(#eye-pupil)" />
              <circle cx="119" cy="87" r="6"   fill="url(#eye-pupil)" />
              <circle cx="81"  cy="87" r="3.2" fill="#0b0420" />
              <circle cx="119" cy="87" r="3.2" fill="#0b0420" />
              {/* primary catch-lights */}
              <circle cx="83.5" cy="84.5" r="2.2" fill="#ffffff" />
              <circle cx="121.5" cy="84.5" r="2.2" fill="#ffffff" />
              {/* secondary tiny sparkles */}
              <circle cx="78.5" cy="89"   r="1"   fill="#ffffff" opacity="0.85" />
              <circle cx="116.5" cy="89"  r="1"   fill="#ffffff" opacity="0.85" />
            </>
          )}
        </motion.g>

        {/* nose — a small rounded triangle between the eyes */}
        <path
          d="M 96 96 Q 100 92 104 96 Q 100 101 96 96 Z"
          fill="#fbcfe8"
          stroke="#ffffff"
          strokeWidth="1"
          strokeLinejoin="round"
        />
        <circle cx="100" cy="96" r="1" fill="#ffffff" opacity="0.8" />

        {/* smile — thicker, with a subtle shadow underneath for depth */}
        <path d="M 82 106 Q 100 119 118 106" stroke="#3b0764" strokeWidth="4.5" strokeLinecap="round" fill="none" opacity="0.35" />
        <path d="M 82 105 Q 100 118 118 105" stroke="#ffffff" strokeWidth="3.5" strokeLinecap="round" fill="none" />
        {/* tiny tongue dot for warmth */}
        <circle cx="100" cy="113" r="2" fill="#fb7185" opacity="0.9" />
        <circle cx="64" cy="100" r="4" fill="#f0abfc" opacity="0.7" />
        <circle cx="136" cy="100" r="4" fill="#f0abfc" opacity="0.7" />
        <circle cx="38" cy="88" r="6" fill="url(#bot-accent)" />
        <circle cx="162" cy="88" r="6" fill="url(#bot-accent)" />
      </g>

      <g filter="url(#bot-shadow)">
        <rect x="58" y="138" width="84" height="50" rx="18" fill="url(#bot-body)" stroke="#e9d5ff" strokeWidth="2" />
        <motion.circle cx="100" cy="163" r="6" fill="url(#bot-accent)"
          animate={{ scale: [1, 1.25, 1] }}
          transition={{ duration: 1.4, repeat: Infinity, ease: 'easeInOut' }}
          style={{ transformOrigin: '100px 163px' }} />
        <g>
          {[0, 0.2, 0.4].map((d, i) => (
            <motion.rect key={i} x={78 + i * 6} y={170} width="3" height={4 + i * 2} rx="1" fill="#a855f7"
              animate={{ scaleY: [0.4, 1, 0.4] }}
              transition={{ duration: 1.2, delay: d, repeat: Infinity, ease: 'easeInOut' }}
              style={{ transformOrigin: `${79.5 + i * 6}px ${170 + (4 + i * 2)}px` }} />
          ))}
          {[0.1, 0.3, 0.5].map((d, i) => (
            <motion.rect key={`r-${i}`} x={113 + i * 6} y={170} width="3" height={4 + i * 2} rx="1" fill="#ec4899"
              animate={{ scaleY: [0.4, 1, 0.4] }}
              transition={{ duration: 1.2, delay: d, repeat: Infinity, ease: 'easeInOut' }}
              style={{ transformOrigin: `${114.5 + i * 6}px ${170 + (4 + i * 2)}px` }} />
          ))}
        </g>
      </g>

      <motion.rect x="28" y="150" width="10" height="28" rx="5" fill="url(#bot-body)" stroke="#e9d5ff" strokeWidth="1.5"
        animate={{ rotate: [-6, 6, -6] }}
        transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
        style={{ transformOrigin: '33px 150px' }} />
      <motion.rect x="162" y="150" width="10" height="28" rx="5" fill="url(#bot-body)" stroke="#e9d5ff" strokeWidth="1.5"
        animate={waving ? { rotate: [0, -85, -65, -85, -65, -85, 0] } : { rotate: [6, -6, 6] }}
        transition={waving
          ? { duration: 1.6, repeat: Infinity, repeatDelay: 1.2, ease: 'easeInOut' }
          : { duration: 3, repeat: Infinity, ease: 'easeInOut' }}
        style={{ transformOrigin: '167px 152px' }} />
      {waving && (
        <motion.g animate={{ opacity: [0, 1, 0] }} transition={{ duration: 1.6, repeat: Infinity, repeatDelay: 1.2 }}>
          <text x="184" y="120" fontSize="22" fontWeight="700" fill="#ec4899" fontFamily="system-ui">Hi!</text>
        </motion.g>
      )}
    </svg>
  );
}
