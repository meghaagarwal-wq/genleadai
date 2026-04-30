import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Buildings, Crosshair, Funnel, Waveform, ShieldCheck, CalendarCheck,
  Brain, CheckCircle, Warning, Sparkle, TrendUp, ArrowRight, GraduationCap,
} from '@phosphor-icons/react';
import api from '../config/api';
import PageHeader from '../components/PageHeader';

const ICON_MAP = { Buildings, Crosshair, Funnel, Waveform, ShieldCheck, CalendarCheck };

const AriaBrain = () => {
  const [data, setData] = useState(null);
  const [expanded, setExpanded] = useState(null);

  useEffect(() => {
    api.get('/api/aria-agent/brain').then(r => setData(r.data)).catch(() => setData(null));
  }, []);

  if (!data) return <div className="text-sm text-[#9B8AB0] p-6">Loading ARIA's brain…</div>;

  const pct = data.completion_pct || 0;
  const completionTone =
    pct >= 85 ? { color: '#16A34A', bg: '#DCFCE7', border: '#16A34A33', label: 'Fully trained' }
    : pct >= 50 ? { color: '#7C35DC', bg: '#F4F0FF', border: '#7C35DC33', label: 'Partially trained' }
    : { color: '#D97706', bg: '#FEF3C7', border: '#D9770633', label: 'Needs training' };

  return (
    <div className="space-y-6" data-testid="aria-brain-page">
      <PageHeader
        eyebrow="ARIA · Brain"
        title="Everything ARIA knows about your business"
        subtitle="This is ARIA's memory — the business context, ICP, voice and objection handling she uses on every reply. Fill the gaps and she gets sharper every day."
      />

      {/* Completion hero */}
      <div className="rounded-2xl p-6 overflow-hidden relative" data-testid="brain-hero"
        style={{ background: 'linear-gradient(135deg,#0E0820 0%,#1A0F38 45%,#2B1860 100%)' }}>
        <div className="absolute inset-0 opacity-60 pointer-events-none"
          style={{ background: 'var(--gradient-aria-glow)' }} />
        <div className="relative flex items-start gap-5 flex-wrap">
          <div className="relative w-24 h-24 rounded-full flex items-center justify-center flex-shrink-0"
            style={{ background: `conic-gradient(#C044E0 ${pct * 3.6}deg, rgba(255,255,255,0.08) 0deg)` }}>
            <div className="w-[84px] h-[84px] rounded-full bg-[#0E0820] flex flex-col items-center justify-center">
              <div className="text-2xl font-extrabold text-white" style={{ fontFamily: 'Plus Jakarta Sans' }}>{pct}%</div>
              <div className="text-[9px] font-bold uppercase tracking-[0.2em] text-[#C9B6FF]">trained</div>
            </div>
          </div>
          <div className="flex-1 min-w-0">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full"
              style={{ background: completionTone.bg, border: `1px solid ${completionTone.border}` }}>
              <Sparkle size={12} weight="fill" style={{ color: completionTone.color }} />
              <span className="text-[10px] font-bold uppercase tracking-[0.2em]" style={{ color: completionTone.color }}>
                {completionTone.label}
              </span>
            </div>
            <h2 className="text-2xl md:text-3xl font-extrabold text-white mt-2 leading-tight" style={{ fontFamily: 'Plus Jakarta Sans' }}>
              {data.headline}
            </h2>
            <p className="text-sm text-[#C9B6FF] mt-2 max-w-2xl">
              {data.filled_fields} of {data.total_fields} fields filled across {data.sections.length} sections.
              The more ARIA knows, the more human her replies sound.
            </p>
            <Link to="/aria-agent/train" data-testid="brain-train-cta"
              className="inline-flex items-center gap-2 mt-4 px-4 py-2 rounded-xl text-sm font-semibold text-white"
              style={{ background: 'var(--gradient-brand)', boxShadow: 'var(--shadow-glow)' }}>
              <GraduationCap size={16} weight="fill" /> Open Train ARIA
              <ArrowRight size={14} weight="bold" />
            </Link>
          </div>
        </div>
      </div>

      {/* Knowledge sections */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="brain-sections">
        {data.sections.map(sec => {
          const Icon = ICON_MAP[sec.icon] || Brain;
          const isOpen = expanded === sec.id;
          return (
            <div key={sec.id} className="bg-white border border-[#E8E0F5] rounded-2xl overflow-hidden"
              style={{ boxShadow: 'var(--shadow-card)' }} data-testid={`brain-section-${sec.id}`}>
              <button onClick={() => setExpanded(isOpen ? null : sec.id)} className="w-full px-5 py-4 flex items-center gap-3 text-left hover:bg-[#FAF7FF] transition-colors">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
                  style={{ background: '#F4F0FF', border: '1px solid #E0D4F7' }}>
                  <Icon size={18} weight="fill" className="text-[#7C35DC]" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-base font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{sec.label}</div>
                  <div className="text-xs text-[#7B6D9C] mt-0.5">{sec.filled}/{sec.total} filled · {sec.completion_pct}%</div>
                </div>
                <div className="w-20 flex-shrink-0">
                  <div className="h-1.5 rounded-full bg-[#F0ECF9] overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${sec.completion_pct}%`, background: 'var(--gradient-brand-horizontal)' }} />
                  </div>
                </div>
              </button>
              {isOpen && (
                <div className="border-t border-[#F0ECF9] px-5 py-4 space-y-3 bg-[#FAFAFC]">
                  {sec.items.map(item => (
                    <div key={item.key} className="flex items-start gap-3" data-testid={`brain-field-${item.key}`}>
                      {item.filled ? (
                        <CheckCircle size={16} weight="fill" className="text-[#16A34A] mt-0.5 flex-shrink-0" />
                      ) : (
                        <Warning size={16} weight="fill" className="text-[#D97706] mt-0.5 flex-shrink-0" />
                      )}
                      <div className="min-w-0 flex-1">
                        <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#7B6D9C]">{item.label}</div>
                        <div className={`text-sm mt-0.5 ${item.filled ? 'text-[#1A0A2E]' : 'text-[#9B8AB0] italic'}`}>
                          {item.filled ? item.value : 'Not filled yet — ARIA will improvise here.'}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Gaps + Live learnings */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Gaps */}
        <div className="bg-white border border-[#E8E0F5] rounded-2xl overflow-hidden" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="brain-gaps">
          <div className="px-5 py-4 border-b border-[#F0ECF9] flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: '#FEF3C7', border: '1px solid #FDE68A' }}>
              <Warning size={18} weight="fill" className="text-[#D97706]" />
            </div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#D97706]" style={{ fontFamily: 'Plus Jakarta Sans' }}>KNOWLEDGE GAPS</div>
              <h3 className="text-lg font-extrabold text-[#1A0A2E] mt-0.5" style={{ fontFamily: 'Plus Jakarta Sans' }}>Where ARIA is guessing</h3>
            </div>
          </div>
          {data.gaps.length === 0 ? (
            <div className="px-5 py-8 text-center">
              <CheckCircle size={32} weight="fill" className="text-[#16A34A] mx-auto" />
              <p className="text-sm text-[#5A4A7A] mt-2">No gaps. ARIA has everything she needs.</p>
            </div>
          ) : (
            <div className="divide-y divide-[#F0ECF9]">
              {data.gaps.map(g => (
                <Link key={`${g.section}-${g.field}`} to="/aria-agent/train" data-testid={`gap-${g.field}`}
                  className="px-5 py-3 flex items-center justify-between gap-3 hover:bg-[#FAF7FF] transition-colors">
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-[#1A0A2E] truncate" style={{ fontFamily: 'Plus Jakarta Sans' }}>{g.label}</div>
                    <div className="text-[10px] font-bold uppercase tracking-[0.15em] text-[#7B6D9C] mt-0.5">{g.section_label}</div>
                  </div>
                  <ArrowRight size={14} weight="bold" className="text-[#7C35DC] flex-shrink-0" />
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Live learnings */}
        <div className="bg-white border border-[#E8E0F5] rounded-2xl overflow-hidden" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="brain-learnings">
          <div className="px-5 py-4 border-b border-[#F0ECF9] flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: 'var(--gradient-brand)' }}>
              <TrendUp size={18} weight="fill" className="text-white" />
            </div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC]" style={{ fontFamily: 'Plus Jakarta Sans' }}>LIVE MEMORY</div>
              <h3 className="text-lg font-extrabold text-[#1A0A2E] mt-0.5" style={{ fontFamily: 'Plus Jakarta Sans' }}>What ARIA learned on the job</h3>
            </div>
          </div>
          <div className="divide-y divide-[#F0ECF9]">
            {data.learnings.map(l => (
              <div key={l.label} className="px-5 py-3 flex items-center justify-between gap-3" data-testid={`learning-${l.label.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`}>
                <div className="min-w-0">
                  <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#7B6D9C]">{l.label}</div>
                  <div className="text-sm text-[#5A4A7A] mt-0.5">{l.hint}</div>
                </div>
                <div className="text-base font-extrabold text-[#1A0A2E] flex-shrink-0" style={{ fontFamily: 'Plus Jakarta Sans' }}>{l.value}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AriaBrain;
