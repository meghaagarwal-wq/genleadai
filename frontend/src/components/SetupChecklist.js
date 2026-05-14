/**
 * SetupChecklist — guided onboarding for new / under-configured tenants.
 *
 * Computes setup progress from real backend signals (no fake data) and shows
 * a 5-step checklist with a percent bar. Auto-hides itself once everything
 * is checked OR when the user dismisses it (persisted in localStorage).
 *
 * Each step has:
 *   • A truthy check function fed live signals
 *   • A friendly label + sub-copy
 *   • A click target (route or scroll anchor)
 *
 * Signals pulled in parallel from:
 *   GET /api/aria-agent/training            → check Train Aria %
 *   GET /api/touchpoints/map                → check touchpoint map exists
 *   GET /api/integrations/hub               → check ≥1 connected
 *   GET /api/leads?limit=1                  → check at least 1 lead exists
 *   GET /api/aria-agent/training (reuses)   → check calendar_link is set
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../config/api';
import { CheckCircle, Circle, X, Sparkle, ArrowRight } from '@phosphor-icons/react';

const STORAGE_KEY = 'aria.setup_checklist.dismissed';

const SetupChecklist = () => {
  const navigate = useNavigate();
  const [signals, setSignals] = useState(null);
  const [dismissed, setDismissed] = useState(() => localStorage.getItem(STORAGE_KEY) === '1');

  useEffect(() => {
    if (dismissed) return;
    let alive = true;
    (async () => {
      try {
        const [t, m, h, l] = await Promise.all([
          api.get('/api/aria-agent/training').catch(() => ({ data: {} })),
          api.get('/api/touchpoints/map').catch(() => ({ data: null })),
          api.get('/api/integrations/list').catch(() => ({ data: { integrations: [] } })),
          api.get('/api/leads?limit=1').catch(() => ({ data: { leads: [] } })),
        ]);
        if (!alive) return;
        const training = t.data || {};
        const fieldsFilled = ['what_you_sell','who_you_sell_to','problem_you_solve','differentiator','target_industries']
          .filter((k) => training[k] && String(training[k]).trim().length > 0).length;
        const connectedCount = (h.data?.integrations || []).filter((i) => i.status === 'connected').length;
        const tpCount = (m.data?.map?.touchpoints || []).length;
        const leadsCount = (l.data?.leads || l.data || []).length;
        setSignals({
          trained: fieldsFilled >= 3,
          touchpoints: tpCount >= 4,
          integrations: connectedCount >= 1,
          leads: leadsCount >= 1,
          calendar: !!(training.calendar_link && String(training.calendar_link).trim().length > 0),
        });
      } catch { /* ignore — leave loading */ }
    })();
    return () => { alive = false; };
  }, [dismissed]);

  if (dismissed || !signals) return null;

  const steps = [
    { key: 'trained',      done: signals.trained,      label: 'Train Aria',                  sub: 'Tell Aria what you sell, who you sell to, and what makes you different.', to: '/aria-agent/train' },
    { key: 'integrations', done: signals.integrations, label: 'Connect a lead source',       sub: 'Plug in WhatsApp, your website form, Meta/Google Ads or a CRM.',         to: '/integrations' },
    { key: 'touchpoints',  done: signals.touchpoints,  label: 'Customize the 32-touchpoint journey', sub: 'Aria will run leads through this sequence automatically.',     to: '/touchpoint-journey' },
    { key: 'calendar',     done: signals.calendar,     label: 'Set your calendar link',       sub: 'So Aria can book qualified leads onto your calendar.',                  to: '/aria-agent/train' },
    { key: 'leads',        done: signals.leads,        label: 'Add or import a lead',         sub: 'Test Aria with one real lead before going live.',                       to: '/leads' },
  ];

  const completed = steps.filter((s) => s.done).length;
  const pct = Math.round((completed / steps.length) * 100);

  // Auto-hide once fully complete — no need to keep nagging the founder.
  if (pct === 100) return null;

  const dismiss = () => {
    localStorage.setItem(STORAGE_KEY, '1');
    setDismissed(true);
  };

  return (
    <div
      className="aria-card-lift relative rounded-2xl border border-[#E0D4F7] overflow-hidden aria-fade-up"
      style={{
        background: 'linear-gradient(135deg, #FFFFFF 0%, #FAF7FF 50%, #FFF8EA 100%)',
        boxShadow: '0 10px 28px rgba(124,53,220,0.08)',
      }}
      data-testid="setup-checklist"
    >
      <button
        onClick={dismiss}
        data-testid="setup-checklist-dismiss"
        title="Hide for now"
        className="absolute top-3 right-3 w-7 h-7 rounded-full bg-white/70 hover:bg-white border border-[#E8E0F5] flex items-center justify-center text-[#9B8AB0] hover:text-[#1A0A2E] transition-colors z-10"
      >
        <X size={11} weight="bold" />
      </button>

      <div className="p-5 md:p-6">
        <div className="flex items-start gap-3 mb-4">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: 'var(--gradient-brand)' }}>
            <Sparkle size={16} weight="fill" className="text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-[#7C35DC]">Aria setup</div>
            <h3 className="text-base font-extrabold text-[#1A0A2E] leading-tight" style={{ fontFamily: 'Plus Jakarta Sans' }}>
              {completed} of {steps.length} steps complete · <span className="text-[#7C35DC]">{pct}%</span>
            </h3>
            <p className="text-xs text-[#5A4A7A] mt-1 leading-relaxed">
              {completed === 0
                ? 'Welcome to Aria. Five quick steps and your AI sales PA is live.'
                : completed >= 3
                ? 'You\'re almost there. Finish the last few steps to unlock Aria\'s full sales engine.'
                : 'Keep going — each step makes Aria sharper at handling your leads.'}
            </p>
          </div>
        </div>

        <div className="h-1.5 rounded-full bg-[#F0ECF9] overflow-hidden mb-4">
          <div className="h-full transition-all duration-700 rounded-full"
            style={{ width: `${pct}%`, background: 'linear-gradient(90deg, #C044E0 0%, #7C35DC 50%, #5B28D4 100%)' }} />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {steps.map((s) => (
            <button
              key={s.key}
              onClick={() => navigate(s.to)}
              data-testid={`setup-step-${s.key}`}
              className={`group flex items-start gap-2.5 p-3 rounded-xl border text-left transition-all hover:-translate-y-0.5 ${
                s.done
                  ? 'bg-[#DCFCE7]/40 border-[#16A34A]/30'
                  : 'bg-white/80 border-[#E8E0F5] hover:border-[#7C35DC]/40 hover:bg-white'
              }`}
            >
              {s.done ? (
                <CheckCircle size={16} weight="fill" className="text-[#16A34A] flex-shrink-0 mt-0.5" />
              ) : (
                <Circle size={16} weight="duotone" className="text-[#9B8AB0] flex-shrink-0 mt-0.5" />
              )}
              <div className="min-w-0 flex-1">
                <div className={`text-sm font-extrabold ${s.done ? 'text-[#16A34A] line-through' : 'text-[#1A0A2E]'}`} style={{ fontFamily: 'Plus Jakarta Sans' }}>
                  {s.label}
                </div>
                <p className="text-[11px] text-[#5A4A7A] mt-0.5 leading-snug">{s.sub}</p>
              </div>
              {!s.done && (
                <ArrowRight size={12} weight="bold" className="text-[#9B8AB0] mt-1 flex-shrink-0 group-hover:text-[#7C35DC] group-hover:translate-x-0.5 transition-all" />
              )}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

export default SetupChecklist;
