import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Robot, ChatCircle, Target, EnvelopeSimple, CalendarCheck, Fire, Snowflake, ArrowRight, Sparkle } from '@phosphor-icons/react';
import api from '../config/api';

const TILES = [
  { key: 'responded_today',    label: 'Leads ARIA responded to today', icon: ChatCircle,    color: '#7C35DC' },
  { key: 'qualified_today',    label: 'Leads ARIA qualified',           icon: Target,        color: '#16A34A' },
  { key: 'followups_sent',     label: 'Follow-ups ARIA sent',           icon: EnvelopeSimple, color: '#7C35DC' },
  { key: 'calls_booked',       label: 'Calls ARIA helped book',         icon: CalendarCheck, color: '#C044E0' },
  { key: 'hot_escalated',      label: 'Hot leads needing founder',      icon: Fire,          color: '#DC2626' },
  { key: 'silent_revived',     label: 'Silent leads ARIA is reviving',  icon: Snowflake,     color: '#0EA5E9' },
];

const AriaAgentActivitySection = () => {
  const navigate = useNavigate();
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get('/api/aria-agent/agent-activity').then(r => setData(r.data)).catch(() => setData(null));
  }, []);

  if (!data) {
    return (
      <div className="rounded-2xl p-5 animate-pulse bg-white border border-[#E8E0F5]" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="aria-agent-activity-loading">
        <div className="h-5 w-64 bg-[#F4F0FF] rounded mb-3" />
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">{[1,2,3,4,5,6].map(i => <div key={i} className="h-20 bg-[#FAF7FF] rounded-xl" />)}</div>
      </div>
    );
  }

  return (
    <section className="space-y-4" data-testid="aria-agent-activity-section">
      {/* Positioning banner */}
      <div className="rounded-2xl px-5 py-4 flex flex-wrap items-center justify-between gap-3" style={{ background: 'linear-gradient(135deg,#1A0F38 0%,#2B1860 60%,#7C35DC 100%)' }} data-testid="aria-positioning-banner">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center bg-white/10 border border-white/15">
            <Robot size={18} weight="fill" className="text-white" />
          </div>
          <div>
            <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#C9B6FF]" style={{ fontFamily: 'Plus Jakarta Sans' }}>ARIA · YOUR FIRST AI SALES HIRE</div>
            <div className="text-base md:text-lg font-extrabold text-white mt-0.5" style={{ fontFamily: 'Plus Jakarta Sans' }}>Your CRM stores leads. ARIA works them.</div>
          </div>
        </div>
        <button onClick={() => navigate('/aria-agent/playbooks')} className="hidden md:flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold uppercase tracking-[0.15em] bg-white/10 hover:bg-white/20 text-white border border-white/20 transition-colors" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid="positioning-banner-cta">
          <Sparkle size={14} weight="fill" /> Activate a sales playbook
        </button>
      </div>

      {/* Section card */}
      <div className="bg-white border border-[#E8E0F5] rounded-2xl overflow-hidden" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="aria-agent-activity-card">
        <div className="px-5 pt-5 pb-3 flex flex-wrap items-end justify-between gap-3">
          <div>
            <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC]" style={{ fontFamily: 'Plus Jakarta Sans' }}>ARIA SALES AGENT · ACTIVITY</div>
            <h2 className="text-lg md:text-xl font-extrabold text-[#1A0A2E] mt-1" style={{ fontFamily: 'Plus Jakarta Sans' }}>{data.headline}</h2>
            <p className="text-xs text-[#5A4A7A] mt-1">{data.subline}</p>
          </div>
          <button onClick={() => navigate('/aria-agent/conversations')} className="text-xs font-bold uppercase tracking-[0.15em] text-[#7C35DC] flex items-center gap-1 hover:underline" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid="agent-activity-view-conversations">
            See conversations <ArrowRight size={12} />
          </button>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-px bg-[#F0ECF9] border-t border-[#F0ECF9]">
          {TILES.map(t => {
            const Icon = t.icon;
            return (
              <div key={t.key} className="bg-white px-4 py-4" data-testid={`agent-activity-${t.key}`}>
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: `${t.color}15`, border: `1px solid ${t.color}33` }}>
                    <Icon size={14} weight="fill" style={{ color: t.color }} />
                  </div>
                  <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-[#5A4A7A]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{t.label}</span>
                </div>
                <div className="text-3xl font-extrabold leading-none" style={{ color: t.color, fontFamily: 'Plus Jakarta Sans' }}>{data[t.key] ?? 0}</div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};

export default AriaAgentActivitySection;
