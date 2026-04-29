import React from 'react';
import { Robot, Sparkle, EnvelopeSimple, WhatsappLogo, Brain, Lightning, ChartLineUp, ClockCounterClockwise } from '@phosphor-icons/react';
import { usePlan } from '../context/PlanContext';
import LockBadge from '../components/LockBadge';
import { useNavigate } from 'react-router-dom';

const TILES = [
  { key: 'ai_qualification', title: 'AI Lead Qualification', desc: 'ARIA reads each new lead, scores fit, and flags hot ones for you.', icon: Brain, route: '/leads' },
  { key: 'ai_lead_scoring', title: 'AI Lead Scoring', desc: 'Continuous scoring on source, urgency, engagement, and stage movement.', icon: ChartLineUp, route: '/leads' },
  { key: 'ai_followup_drafts', title: 'AI Follow-up Drafts', desc: 'Personalised email & WhatsApp drafts in seconds.', icon: EnvelopeSimple, route: '/leads' },
  { key: 'whatsapp_workflow', title: 'WhatsApp Workflows', desc: 'Sequences, replies, opt-out — all on autopilot.', icon: WhatsappLogo, route: '/integrations' },
  { key: 'ai_followup_basic', title: 'Next-Best-Action', desc: 'Tells reps the single highest-impact next step per lead.', icon: Lightning, route: '/leads' },
  { key: 'lost_reason_tracking', title: 'AI Lost-Lead Analysis', desc: 'Patterns across lost leads to fix the leaks.', icon: ClockCounterClockwise, route: '/reports' },
  { key: 'daily_founder_report', title: 'Daily Founder Summary', desc: 'A 1-screen morning briefing of pipeline movement.', icon: Sparkle, route: '/settings' },
  { key: 'weekly_sales_summary', title: 'Weekly Sales Summary', desc: 'Trends, momentum, and what needs attention this week.', icon: Sparkle, route: '/reports' },
];

const AIAssistant = () => {
  const { hasFeature, openUpgrade } = usePlan();
  const navigate = useNavigate();

  return (
    <div className="space-y-6" data-testid="ai-assistant-page">
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ background: 'var(--gradient-brand)' }}>
          <Robot size={24} className="text-white" weight="fill" />
        </div>
        <div>
          <h1 className="text-3xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>AI Assistant</h1>
          <p className="text-sm text-[#5A4A7A]">Your AI Sales PA — qualifying, drafting, summarising, and chasing leads while you sleep.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {TILES.map(t => {
          const unlocked = hasFeature(t.key);
          const Icon = t.icon;
          return (
            <button key={t.key} onClick={() => unlocked ? navigate(t.route) : openUpgrade(t.key)} className={`relative bg-white border rounded-xl p-5 text-left transition-all ${unlocked ? 'border-[#E8E0F5] hover:border-[#7C35DC]/40' : 'border-[#E8E0F5] hover:border-[#7C35DC]/30'}`} style={{ boxShadow: 'var(--shadow-card)' }} data-testid={`ai-tile-${t.key}`}>
              {!unlocked && (
                <div className="absolute top-3 right-3">
                  <LockBadge featureKey={t.key} label="Locked" />
                </div>
              )}
              <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-3" style={{ background: unlocked ? 'var(--gradient-brand)' : '#F4F0FF' }}>
                <Icon size={18} className={unlocked ? 'text-white' : 'text-[#7C35DC]'} weight="fill" />
              </div>
              <h3 className="text-sm font-bold text-[#1A0A2E] mb-1" style={{ fontFamily: 'Plus Jakarta Sans' }}>{t.title}</h3>
              <p className="text-xs text-[#5A4A7A]">{t.desc}</p>
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default AIAssistant;
