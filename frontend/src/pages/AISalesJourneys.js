import React, { useEffect, useState } from 'react';
import { Lightning, ChatCircle, EnvelopeSimple, WhatsappLogo, CalendarCheck, ArrowRight, Sparkle } from '@phosphor-icons/react';
import api from '../config/api';
import PageHeader from '../components/PageHeader';

const CHANNEL_ICONS = {
  WhatsApp: WhatsappLogo, Email: EnvelopeSimple, 'Email + WhatsApp': EnvelopeSimple,
  Calendar: CalendarCheck, 'WhatsApp + Calendar': CalendarCheck, 'Website Chat': ChatCircle, 'In-app': ChatCircle,
  LinkedIn: ChatCircle,
};

const AISalesJourneys = () => {
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get('/api/aria-agent/journeys/default').then(r => setData(r.data)).catch(() => setData(null));
  }, []);

  return (
    <div className="space-y-6" data-testid="ai-sales-journeys-page">
      <PageHeader
        eyebrow="ARIA · Sales Journeys"
        title="From first message to qualified call"
        subtitle="Design how ARIA guides each lead from capture to booked call. Up to 26 personalised touchpoints, switching channels based on lead behavior."
        actions={(
          <button className="btn-gradient px-4 py-2 rounded-xl text-xs font-bold uppercase tracking-[0.15em]" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid="journey-new-btn">
            <Sparkle size={14} weight="fill" className="inline mr-1" /> Create AI Sales Journey
          </button>
        )}
      />

      {/* Templates */}
      <div className="bg-white border border-[#E8E0F5] rounded-2xl p-5" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="journey-templates">
        <div className="flex items-center justify-between mb-3">
          <div>
            <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC]" style={{ fontFamily: 'Plus Jakarta Sans' }}>JOURNEY TEMPLATES</div>
            <h3 className="text-base font-extrabold text-[#1A0A2E] mt-0.5" style={{ fontFamily: 'Plus Jakarta Sans' }}>Start from a proven journey</h3>
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          {(data?.templates || []).map(t => (
            <div key={t.id} className="bg-[#FAF7FF] border border-[#EDE5FA] rounded-xl px-3 py-3 hover:border-[#7C35DC]/30 transition-colors cursor-pointer" data-testid={`journey-template-${t.id}`}>
              <div className="text-xs font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{t.name}</div>
              <div className="text-[10px] text-[#9B8AB0] mt-1">{t.touchpoints} touchpoints</div>
              <div className="text-[10px] font-medium text-[#7C35DC] mt-1.5">{t.best_for}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Default journey timeline */}
      <div className="bg-white border border-[#E8E0F5] rounded-2xl overflow-hidden" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="journey-default-timeline">
        <div className="px-5 py-4 border-b border-[#F0ECF9] flex items-center justify-between">
          <div>
            <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC]" style={{ fontFamily: 'Plus Jakarta Sans' }}>DEFAULT ARIA JOURNEY</div>
            <h3 className="text-lg font-extrabold text-[#1A0A2E] mt-0.5" style={{ fontFamily: 'Plus Jakarta Sans' }}>17-touchpoint nurture flow</h3>
            <p className="text-xs text-[#9B8AB0] mt-0.5">ARIA can extend this to {data?.max_touchpoints || 26} touchpoints based on lead behavior.</p>
          </div>
          <Lightning size={28} weight="fill" className="text-[#7C35DC]" />
        </div>
        <ol className="divide-y divide-[#F0ECF9]" data-testid="journey-steps">
          {(data?.journey || []).map(step => {
            const ChannelIcon = CHANNEL_ICONS[step.channel] || ChatCircle;
            return (
              <li key={step.step} className="px-5 py-4 flex items-start gap-4" data-testid={`journey-step-${step.step}`}>
                <div className="flex-shrink-0 w-9 h-9 rounded-full flex items-center justify-center text-sm font-extrabold border-2" style={{ background: '#F4F0FF', color: '#7C35DC', borderColor: '#7C35DC', fontFamily: 'Plus Jakarta Sans' }}>
                  {step.step}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span className="text-sm font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{step.name}</span>
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-[#F4F0FF] text-[#7C35DC] border border-[#7C35DC]/20 flex items-center gap-1">
                      <ChannelIcon size={10} weight="fill" /> {step.channel}
                    </span>
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-[#FEF3C7] text-[#D97706] border border-[#D97706]/30">{step.timing}</span>
                  </div>
                  <div className="text-xs text-[#5A4A7A] leading-relaxed">
                    <span className="font-semibold text-[#1A0A2E]">Goal:</span> {step.goal} · <span className="font-semibold text-[#1A0A2E]">Trigger:</span> {step.trigger}
                  </div>
                  <div className="text-[11px] text-[#9B8AB0] mt-1">
                    Personalises with <span className="font-mono text-[#7C35DC]">{step.personalisation}</span>{step.handoff_rule !== '—' && <> · Handoff: <span className="text-[#DC2626]">{step.handoff_rule}</span></>}
                  </div>
                </div>
                <ArrowRight size={14} className="text-[#D4C5E8] mt-2" />
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
};

export default AISalesJourneys;
