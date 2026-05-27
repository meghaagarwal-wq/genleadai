/* Iter104 — Aria landing flourishes (converted from .tsx → .jsx). */
import { motion, useReducedMotion } from 'framer-motion';
import { Sparkles, Brain, Radio, Zap } from 'lucide-react';
import { useEffect, useState } from 'react';

export function AgentOrb({ className = '' }) {
  const reduce = useReducedMotion();
  return (
    <div className={`pointer-events-none relative ${className}`}>
      {[0, 0.6, 1.2].map((d) => (
        <span key={d} className="absolute inset-0 rounded-full border border-white/40"
          style={{ animation: reduce ? undefined : `pulse-ring 2.8s ${d}s cubic-bezier(0.4,0,0.2,1) infinite` }} />
      ))}
      <motion.div className="absolute inset-3 rounded-full"
        style={{ background: 'conic-gradient(from 0deg, #c084fc, #f0abfc, #a78bfa, #c084fc)', filter: 'blur(2px)' }}
        animate={reduce ? {} : { rotate: 360 }}
        transition={{ duration: 14, ease: 'linear', repeat: Infinity }} />
      <div className="absolute inset-6 rounded-full bg-white/95 backdrop-blur" />
      <motion.div className="absolute inset-0 flex items-center justify-center"
        animate={reduce ? {} : { scale: [1, 1.08, 1] }}
        transition={{ duration: 2.2, repeat: Infinity, ease: 'easeInOut' }}>
        <Sparkles className="size-7" style={{ color: '#7c3aed' }} />
      </motion.div>
      {[
        { Icon: Brain, label: 'Train', angle: -30 },
        { Icon: Radio, label: 'Scan',  angle: 90 },
        { Icon: Zap,   label: 'Act',   angle: 210 },
      ].map(({ Icon, label, angle }, i) => (
        <motion.div key={label} className="absolute left-1/2 top-1/2 origin-center"
          style={{ transform: `rotate(${angle}deg) translateX(120px) rotate(${-angle}deg)` }}
          animate={reduce ? {} : { y: [0, -6, 0] }}
          transition={{ duration: 3, delay: i * 0.4, repeat: Infinity, ease: 'easeInOut' }}>
          <div className="flex -translate-x-1/2 -translate-y-1/2 items-center gap-1.5 rounded-full border border-white/30 bg-white/15 px-2.5 py-1 text-[10px] font-semibold text-white backdrop-blur">
            <Icon className="size-3" />
            {label}
          </div>
        </motion.div>
      ))}
    </div>
  );
}

export function TypingWord({ words, className = '' }) {
  const [wi, setWi] = useState(0);
  const [text, setText] = useState('');
  const [phase, setPhase] = useState('type');

  useEffect(() => {
    const word = words[wi];
    let t;
    if (phase === 'type') {
      if (text.length < word.length) {
        t = setTimeout(() => setText(word.slice(0, text.length + 1)), 70);
      } else {
        t = setTimeout(() => setPhase('hold'), 1400);
      }
    } else if (phase === 'hold') {
      t = setTimeout(() => setPhase('delete'), 800);
    } else {
      if (text.length > 0) {
        t = setTimeout(() => setText(word.slice(0, text.length - 1)), 35);
      } else {
        setPhase('type');
        setWi((wi + 1) % words.length);
      }
    }
    return () => clearTimeout(t);
  }, [text, phase, wi, words]);

  return (
    <span className={className}>
      {text}
      <span className="ml-0.5 inline-block h-[0.9em] w-[3px] translate-y-1 rounded-sm bg-current align-middle"
        style={{ animation: 'caret 1s steps(1) infinite' }} />
    </span>
  );
}

export function SignalBars({ className = '' }) {
  return (
    <div className={`flex items-end gap-0.5 ${className}`}>
      {[0, 0.15, 0.3, 0.45, 0.2].map((d, i) => (
        <span key={i} className="block w-[3px] origin-bottom rounded-full bg-current"
          style={{ height: `${10 + i * 3}px`, animation: `signal 1.6s ${d}s ease-in-out infinite` }} />
      ))}
    </div>
  );
}
