import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Robot, ChatCircle, Target, EnvelopeSimple, CalendarCheck, Fire, Snowflake, ArrowRight, Sparkle } from '@phosphor-icons/react';
import api from '../config/api';

const TILES = [
  { key: 'responded_today',    label: 'Leads ARIA responded to', icon: ChatCircle,    color: '#7C35DC', accent: 'rgba(124,53,220,0.10)' },
  { key: 'qualified_today',    label: 'Leads ARIA qualified',     icon: Target,        color: '#16A34A', accent: 'rgba(22,163,74,0.10)' },
  { key: 'followups_sent',     label: 'Follow-ups ARIA sent',     icon: EnvelopeSimple, color: '#7C35DC', accent: 'rgba(124,53,220,0.10)' },
  { key: 'calls_booked',       label: 'Calls ARIA helped book',   icon: CalendarCheck, color: '#C044E0', accent: 'rgba(192,68,224,0.10)' },
  { key: 'hot_escalated',      label: 'Hot leads escalated',      icon: Fire,          color: '#DC2626', accent: 'rgba(220,38,38,0.10)' },
  { key: 'silent_revived',     label: 'Silent leads ARIA is reviving', icon: Snowflake, color: '#0EA5E9', accent: 'rgba(14,165,233,0.10)' },
];

const AriaAgentActivitySection = () => {
  const navigate = useNavigate();
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get('/api/aria-agent/agent-activity').then(r => setData(r.data)).catch(() => setData(null));
  }, []);

  if (!data) {
    return (
      <div className="rounded-3xl p-6 animate-pulse bg-white border border-[#E8E0F5]" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="aria-agent-activity-loading">
        <div className="h-5 w-64 bg-[#F4F0FF] rounded mb-3" />
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">{[1,2,3,4,5,6].map(i => <div key={i} className="h-24 bg-[#FAF7FF] rounded-2xl" />)}</div>
      </div>
    );
  }

  return (
    <section className="space-y-5" data-testid="aria-agent-activity-section">
      {/* Premium positioning banner */}
      <div className="relative rounded-3xl px-6 py-7 overflow-hidden aria-grain aria-fade-up" style={{ background: 'var(--gradient-aria-deep)', boxShadow: 'var(--shadow-deep)' }} data-testid="aria-positioning-banner">
        <div className="absolute inset-0 pointer-events-none" style={{ background: 'var(--gradient-aria-glow)' }} />
        <div className="relative flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4 max-w-2xl">
            <div className="relative w-12 h-12 rounded-2xl flex items-center justify-center flex-shrink-0" style={{ background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.18)' }}>
              <Robot size={22} weight="fill" className="text-white" />
              <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-[#16A34A] aria-pulse-ring" />
            </div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-[0.3em] text-[#C9B6FF] numeric">ARIA · YOUR FIRST AI SALES HIRE</div>
              <div className="font-display text-[1.65rem] md:text-[2rem] leading-[1.1] mt-2 text-white">
                Your CRM stores leads.<br />
                <span className="aria-gradient-text-light font-display-italic">ARIA works them.</span>
              </div>
            </div>
          </div>
          <button onClick={() => navigate('/aria-agent/playbooks')} className="hidden md:flex items-center gap-2 px-5 py-2.5 rounded-xl text-[11px] font-bold uppercase tracking-[0.18em] bg-white/10 hover:bg-white/15 text-white border border-white/20 transition-all backdrop-blur-sm" data-testid="positioning-banner-cta">
            <Sparkle size={14} weight="fill" /> Activate a sales playbook
          </button>
        </div>
      </div>

      {/* Activity card */}
      <div className="bg-white border border-[#E8E0F5] rounded-3xl overflow-hidden aria-fade-up aria-fade-up-1" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="aria-agent-activity-card">
        <div className="px-6 pt-6 pb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <div className="inline-flex items-center gap-2 mb-2">
              <span className="block w-6 h-px bg-gradient-to-r from-[#C044E0] to-transparent" />
              <span className="text-[10px] font-bold uppercase tracking-[0.3em] text-[#7C35DC] numeric">ARIA SALES AGENT · ACTIVITY</span>
            </div>
            <h2 className="font-display text-[1.6rem] md:text-[1.85rem] leading-[1.1] text-[#1A0A2E]" data-testid="agent-activity-headline">{data.headline}</h2>
            <p className="text-sm text-[#5A4A7A] mt-1.5">{data.subline}</p>
          </div>
          <button onClick={() => navigate('/aria-agent/briefs')} className="text-[11px] font-bold uppercase tracking-[0.2em] text-[#7C35DC] flex items-center gap-1.5 hover:gap-2.5 transition-all numeric" data-testid="agent-activity-view-conversations">
            See briefs <ArrowRight size={12} weight="bold" />
          </button>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-px bg-[#F0ECF9] border-t border-[#F0ECF9]">
          {TILES.map((t, i) => {
            const Icon = t.icon;
            return (
              <div key={t.key} className={`bg-white px-5 py-5 aria-fade-up aria-fade-up-${(i % 4) + 1}`} data-testid={`agent-activity-${t.key}`}>
                <div className="flex items-center gap-2.5 mb-3">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: t.accent, border: `1px solid ${t.color}26` }}>
                    <Icon size={14} weight="fill" style={{ color: t.color }} />
                  </div>
                  <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#5A4A7A] numeric">{t.label}</span>
                </div>
                <div className="font-display text-[2.75rem] leading-none numeric" style={{ color: t.color }}>{data[t.key] ?? 0}</div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};

export default AriaAgentActivitySection;
