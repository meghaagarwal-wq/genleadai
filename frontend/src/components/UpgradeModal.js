import React, { useState } from 'react';
import { usePlan } from '../context/PlanContext';
import { Sparkle, Lock, X, ArrowRight, CheckCircle } from '@phosphor-icons/react';
import { toast } from 'sonner';

const PLAN_LABEL = {
  starter: 'ARIA Starter',
  growth: 'ARIA Growth',
  pro: 'ARIA Pro',
  custom: 'ARIA Custom',
};

const UpgradeModal = () => {
  const { upgrade, closeUpgrade, planId, allPlans, requestUpgrade } = usePlan();
  const [note, setNote] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  if (!upgrade.open) return null;

  const target = upgrade.targetPlan || 'pro';
  const targetPlan = allPlans.find(p => p.id === target);
  const featureKey = upgrade.featureKey;

  const handleRequest = async () => {
    setSubmitting(true);
    const res = await requestUpgrade(target, featureKey, note);
    setSubmitting(false);
    if (res.ok) {
      setDone(true);
      toast.success('Upgrade request sent!', { description: 'Our team will reach out shortly.' });
    } else {
      toast.error(res.error || 'Request failed');
    }
  };

  const handleClose = () => {
    setNote('');
    setDone(false);
    closeUpgrade();
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-[#1A0A2E]/60 backdrop-blur-sm" onClick={handleClose} data-testid="upgrade-modal">
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <button onClick={handleClose} className="absolute top-4 right-4 text-[#9B8AB0] hover:text-[#1A0A2E] transition-colors" data-testid="upgrade-modal-close">
          <X size={20} />
        </button>
        <div className="p-6 border-b border-[#F0ECF9]" style={{ background: 'linear-gradient(135deg, #F9F5FF 0%, #FFFFFF 100%)' }}>
          <div className="flex items-center gap-3 mb-3">
            <div className="w-11 h-11 rounded-xl flex items-center justify-center" style={{ background: 'var(--gradient-brand)' }}>
              {done ? <CheckCircle size={22} className="text-white" weight="fill" /> : <Sparkle size={22} className="text-white" weight="fill" />}
            </div>
            <div>
              <h2 className="text-lg font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>
                {done ? 'Request sent!' : `Unlock with ${PLAN_LABEL[target] || target}`}
              </h2>
              <p className="text-xs text-[#5A4A7A] mt-0.5">
                {done ? 'Our team will be in touch within 1 business day.' : `You're on ${PLAN_LABEL[planId] || 'Starter'} — let's level up`}
              </p>
            </div>
          </div>
          {!done && featureKey && (
            <div className="flex items-center gap-2 px-3 py-2 bg-white border border-[#E8E0F5] rounded-lg text-xs text-[#5A4A7A]">
              <Lock size={12} /> Feature: <span className="font-mono text-[#1A0A2E] font-medium">{featureKey}</span>
            </div>
          )}
        </div>
        {!done ? (
          <>
            {targetPlan && (
              <div className="p-6 space-y-3">
                <div className="flex items-baseline justify-between">
                  <h3 className="text-base font-bold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{targetPlan.name}</h3>
                  <div className="text-right">
                    {targetPlan.contact_sales ? (
                      <span className="text-sm font-bold text-[#7C35DC]">Contact Sales</span>
                    ) : (
                      <span className="text-2xl font-extrabold text-[#1A0A2E]">${targetPlan.amount}<span className="text-xs font-medium text-[#9B8AB0]">/mo</span></span>
                    )}
                  </div>
                </div>
                <p className="text-xs text-[#5A4A7A]">{targetPlan.tagline}</p>
                <ul className="space-y-1.5 mt-3">
                  {(targetPlan.headline_features || []).slice(0, 5).map((f, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-[#1A0A2E]">
                      <CheckCircle size={14} className="text-[#16A34A] mt-0.5 flex-shrink-0" weight="fill" /> {f}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div className="p-6 pt-0 space-y-3">
              <textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Anything we should know? (optional)" rows={2} className="w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-2.5 rounded-lg text-sm resize-none focus:border-[#7C35DC]" data-testid="upgrade-note-input" />
              <button onClick={handleRequest} disabled={submitting} className="w-full flex items-center justify-center gap-2 btn-gradient px-5 py-3 rounded-lg text-sm font-semibold disabled:opacity-50" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid="upgrade-request-btn">
                {submitting ? 'Sending…' : <>Request Upgrade <ArrowRight size={14} weight="bold" /></>}
              </button>
            </div>
          </>
        ) : (
          <div className="p-8 text-center">
            <p className="text-sm text-[#5A4A7A] mb-4">We've notified our team. You'll hear back within 24 hours.</p>
            <button onClick={handleClose} className="px-5 py-2 bg-[#F4F0FF] text-[#7C35DC] rounded-lg text-sm font-semibold hover:bg-[#E0D4F7] transition-colors" data-testid="upgrade-modal-done-btn">Got it</button>
          </div>
        )}
      </div>
    </div>
  );
};

export default UpgradeModal;
