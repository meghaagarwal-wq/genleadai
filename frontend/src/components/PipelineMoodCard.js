import React, { useEffect, useState } from 'react';
import { Sparkle, TrendUp, Warning, Compass } from '@phosphor-icons/react';
import api from '../config/api';

const TONE_STYLE = {
  positive: { border: 'border-[#16A34A]/30', bg: 'bg-[#DCFCE7]', icon: TrendUp, color: '#16A34A' },
  warning:  { border: 'border-[#D97706]/30', bg: 'bg-[#FEF3C7]', icon: Warning, color: '#D97706' },
  neutral:  { border: 'border-[#7C35DC]/30', bg: 'bg-[#F4F0FF]', icon: Compass, color: '#7C35DC' },
};

const PipelineMoodCard = () => {
  const [mood, setMood] = useState(null);

  useEffect(() => {
    api.get('/api/aria-agent/workspace/pipeline-mood').then(r => setMood(r.data)).catch(() => {});
  }, []);

  if (!mood) {
    return <div className="bg-white border border-[#E8E0F5] rounded-2xl p-5 h-[168px] animate-pulse" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="pipeline-mood-loading" />;
  }

  const tone = TONE_STYLE[mood.tone] || TONE_STYLE.neutral;
  const Icon = tone.icon;

  return (
    <div className="bg-white border border-[#E8E0F5] rounded-2xl p-5 aria-fade-up aria-fade-up-2" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="pipeline-mood-card">
      <div className="flex items-center gap-2 mb-3">
        <span className="block w-5 h-px bg-gradient-to-r from-[#C044E0] to-transparent" />
        <span className="text-[10px] font-bold uppercase tracking-[0.3em] text-[#7C35DC] numeric">PIPELINE MOOD</span>
      </div>
      <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full ${tone.bg} ${tone.border} border`}>
        <Icon size={13} weight="fill" style={{ color: tone.color }} />
        <span className="text-[10px] font-extrabold uppercase tracking-[0.18em] numeric" style={{ color: tone.color }}>{mood.mood}</span>
      </div>
      <p className="font-display-italic text-base md:text-[17px] text-[#1A0A2E] leading-snug mt-3" data-testid="pipeline-mood-line">"{mood.line}"</p>
      <div className="grid grid-cols-3 gap-2 mt-4 pt-3 border-t border-[#F0ECF9]">
        {[
          { k: 'active', label: 'Active' },
          { k: 'hot', label: 'Hot' },
          { k: 'silent', label: 'Silent' },
        ].map(s => (
          <div key={s.k} className="text-center">
            <div className="font-display text-xl leading-none numeric text-[#1A0A2E]">{mood.counts?.[s.k] ?? 0}</div>
            <div className="text-[9px] font-bold uppercase tracking-[0.18em] text-[#9B8AB0] mt-1 numeric">{s.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default PipelineMoodCard;
