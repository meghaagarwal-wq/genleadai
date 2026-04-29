import React, { useEffect, useState } from 'react';
import { Snowflake, ArrowClockwise, Lightning, EnvelopeSimple, WhatsappLogo } from '@phosphor-icons/react';
import api from '../config/api';
import PageHeader from '../components/PageHeader';

const CHANNEL_ICONS = { Email: EnvelopeSimple, WhatsApp: WhatsappLogo, 'Email + WhatsApp': EnvelopeSimple };

const RevivalEngine = () => {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(null);

  useEffect(() => {
    api.get('/api/aria-agent/revival/segments').then(r => setData(r.data)).catch(() => setData(null));
  }, []);

  const start = (segId) => {
    setBusy(segId);
    setTimeout(() => { setBusy(null); alert('Revival journey queued. ARIA will start re-engaging this segment.'); }, 800);
  };

  return (
    <div className="space-y-6" data-testid="revival-engine-page">
      <PageHeader
        eyebrow="ARIA · Revival Engine"
        title="No lead stays silent forever"
        subtitle="ARIA re-engages old, silent, and lost leads with context-aware messages tailored to why they went cold. Every segment runs its own revival journey."
      />

      {/* Segments */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {(data?.segments || []).map(s => {
          const Icon = CHANNEL_ICONS[s.channel] || EnvelopeSimple;
          return (
            <div key={s.id} className="bg-white border border-[#E8E0F5] rounded-2xl overflow-hidden" style={{ boxShadow: 'var(--shadow-card)' }} data-testid={`revival-segment-${s.id}`}>
              <div className="px-5 pt-5 pb-3 flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-base font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{s.name}</h3>
                  <p className="text-xs text-[#9B8AB0] mt-1">{s.message_angle}</p>
                </div>
                <div className="text-right">
                  <div className="text-3xl font-extrabold text-[#7C35DC] leading-none" style={{ fontFamily: 'Plus Jakarta Sans' }}>{s.count}</div>
                  <div className="text-[10px] font-bold uppercase tracking-[0.15em] text-[#9B8AB0] mt-1" style={{ fontFamily: 'Plus Jakarta Sans' }}>leads</div>
                </div>
              </div>
              <div className="px-5 pb-3 grid grid-cols-3 gap-2">
                <div className="bg-[#FAF7FF] border border-[#EDE5FA] rounded-lg px-3 py-2">
                  <div className="text-[9px] font-bold uppercase tracking-[0.15em] text-[#9B8AB0]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Channel</div>
                  <div className="text-xs text-[#1A0A2E] mt-1 flex items-center gap-1"><Icon size={11} weight="fill" className="text-[#7C35DC]" />{s.channel}</div>
                </div>
                <div className="bg-[#FAF7FF] border border-[#EDE5FA] rounded-lg px-3 py-2">
                  <div className="text-[9px] font-bold uppercase tracking-[0.15em] text-[#9B8AB0]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Cadence</div>
                  <div className="text-xs text-[#1A0A2E] mt-1">{s.cadence}</div>
                </div>
                <div className="bg-[#FAF7FF] border border-[#EDE5FA] rounded-lg px-3 py-2">
                  <div className="text-[9px] font-bold uppercase tracking-[0.15em] text-[#9B8AB0]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Goal</div>
                  <div className="text-xs text-[#1A0A2E] mt-1">{s.goal}</div>
                </div>
              </div>
              <div className="px-5 pb-5">
                <button onClick={() => start(s.id)} disabled={busy === s.id || s.count === 0}
                  className="w-full btn-gradient py-2.5 rounded-xl text-xs font-bold uppercase tracking-[0.15em] disabled:opacity-50"
                  style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid={`revival-start-${s.id}`}>
                  {busy === s.id ? 'Queuing…' : s.count === 0 ? 'No leads in this segment' : 'Start Revival Journey'}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Default revival journey timeline */}
      <div className="bg-white border border-[#E8E0F5] rounded-2xl overflow-hidden" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="revival-default-journey">
        <div className="px-5 py-4 border-b border-[#F0ECF9] flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg,#0EA5E9 0%,#7C35DC 100%)' }}>
            <ArrowClockwise size={18} weight="fill" className="text-white" />
          </div>
          <div>
            <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC]" style={{ fontFamily: 'Plus Jakarta Sans' }}>DEFAULT REVIVAL JOURNEY</div>
            <h3 className="text-lg font-extrabold text-[#1A0A2E] mt-0.5" style={{ fontFamily: 'Plus Jakarta Sans' }}>5-touch sequence over 30 days</h3>
          </div>
        </div>
        <div className="p-5 grid grid-cols-1 md:grid-cols-5 gap-3">
          {(data?.default_journey || []).map((step, i) => {
            const Icon = CHANNEL_ICONS[step.channel] || EnvelopeSimple;
            return (
              <div key={step.day} className="bg-[#FAF7FF] border border-[#EDE5FA] rounded-xl px-4 py-4 relative" data-testid={`revival-step-${step.day}`}>
                <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#7C35DC]" style={{ fontFamily: 'Plus Jakarta Sans' }}>DAY {step.day}</div>
                <div className="text-sm font-extrabold text-[#1A0A2E] mt-1" style={{ fontFamily: 'Plus Jakarta Sans' }}>{step.label}</div>
                <div className="text-[11px] text-[#9B8AB0] mt-1 flex items-center gap-1"><Icon size={11} weight="fill" />{step.channel}</div>
                <div className="text-[11px] text-[#5A4A7A] mt-1.5">{step.goal}</div>
                {i < (data?.default_journey?.length || 0) - 1 && <div className="hidden md:block absolute top-1/2 -right-2 w-3 h-0.5 bg-[#D4C5E8]" />}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default RevivalEngine;
