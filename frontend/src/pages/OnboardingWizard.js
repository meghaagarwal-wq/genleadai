import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../config/api';
import { ArrowRight, ArrowLeft, Buildings, User, CalendarBlank, Target, Sparkle, CheckCircle, Rocket } from '@phosphor-icons/react';

const steps = [
  { id: 'company', title: 'Your Company', subtitle: 'Tell us about your business', icon: Buildings },
  { id: 'founder', title: 'About You', subtitle: 'How should ARIA represent you?', icon: User },
  { id: 'calendly', title: 'Calendar', subtitle: 'Connect your booking calendar', icon: CalendarBlank },
  { id: 'icp', title: 'Ideal Customer', subtitle: 'Who are you trying to reach?', icon: Target },
  { id: 'ready', title: 'All Set!', subtitle: 'Your workspace is ready', icon: Sparkle },
];

const OnboardingWizard = ({ onComplete }) => {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [data, setData] = useState({
    company_name: '', founder_name: '', industry: '', team_size: '',
    calendly_link: '', icp_description: '',
  });
  const [saving, setSaving] = useState(false);

  const inputCls = "w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-4 py-3 rounded-xl text-sm focus:border-[#7C35DC] focus:ring-2 focus:ring-[rgba(124,53,220,0.12)] transition-all";

  const handleComplete = async () => {
    setSaving(true);
    try {
      await api.post('/api/onboarding/complete', { ...data, completed: true });
      if (onComplete) onComplete();
      else navigate('/');
    } catch (e) { console.error(e); }
    finally { setSaving(false); }
  };

  const canNext = () => {
    if (step === 0) return data.company_name.trim().length > 0;
    if (step === 1) return data.founder_name.trim().length > 0;
    return true;
  };

  const CurrentIcon = steps[step].icon;

  return (
    <div className="min-h-screen bg-[#FAFAFA] flex items-center justify-center p-4" data-testid="onboarding-wizard">
      <div className="w-full max-w-lg">
        {/* Progress */}
        <div className="flex items-center justify-center gap-2 mb-8">
          {steps.map((s, i) => (
            <div key={s.id} className={`h-1.5 rounded-full transition-all ${i < step ? 'w-8 bg-[#7C35DC]' : i === step ? 'w-12 bg-[#7C35DC]' : 'w-8 bg-[#E8E0F5]'}`} />
          ))}
        </div>

        {/* Card */}
        <div className="bg-white border border-[#E8E0F5] rounded-2xl overflow-hidden" style={{ boxShadow: 'var(--shadow-hover)' }}>
          {/* Header */}
          <div className="p-6 border-b border-[#E8E0F5] bg-[#F9F5FF]">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: 'var(--gradient-brand)' }}>
                <CurrentIcon size={20} className="text-white" weight="fill" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{steps[step].title}</h2>
                <p className="text-sm text-[#5A4A7A]">{steps[step].subtitle}</p>
              </div>
            </div>
          </div>

          {/* Content */}
          <div className="p-6">
            {step === 0 && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-semibold text-[#1A0A2E] mb-2" style={{ fontFamily: 'Plus Jakarta Sans' }}>Company Name *</label>
                  <input type="text" value={data.company_name} onChange={(e) => setData({...data, company_name: e.target.value})} className={inputCls} placeholder="e.g., GenLeadAI" data-testid="onb-company-name" />
                </div>
                <div>
                  <label className="block text-sm font-semibold text-[#1A0A2E] mb-2" style={{ fontFamily: 'Plus Jakarta Sans' }}>Industry</label>
                  <select value={data.industry} onChange={(e) => setData({...data, industry: e.target.value})} className={inputCls} data-testid="onb-industry">
                    <option value="">Select industry</option>
                    {['SaaS', 'E-commerce', 'Healthcare', 'FinTech', 'EdTech', 'Marketing Agency', 'Consulting', 'Real Estate', 'Manufacturing', 'Retail', 'Other'].map(i => <option key={i} value={i}>{i}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-semibold text-[#1A0A2E] mb-2" style={{ fontFamily: 'Plus Jakarta Sans' }}>Team Size</label>
                  <div className="grid grid-cols-4 gap-2">
                    {['1-5', '6-20', '21-50', '50+'].map(size => (
                      <button key={size} onClick={() => setData({...data, team_size: size})} className={`py-2.5 rounded-xl border text-sm font-medium transition-all ${data.team_size === size ? 'bg-[#F4F0FF] text-[#7C35DC] border-[#7C35DC]/30' : 'bg-white text-[#5A4A7A] border-[#E8E0F5] hover:bg-[#F9F5FF]'}`} data-testid={`onb-size-${size}`}>{size}</button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {step === 1 && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-semibold text-[#1A0A2E] mb-2" style={{ fontFamily: 'Plus Jakarta Sans' }}>Your Name *</label>
                  <input type="text" value={data.founder_name} onChange={(e) => setData({...data, founder_name: e.target.value})} className={inputCls} placeholder="e.g., Megha" data-testid="onb-founder-name" />
                </div>
                <div className="bg-[#F4F0FF] border border-[#E0D4F7] rounded-xl p-4">
                  <p className="text-sm text-[#7C35DC] font-medium">ARIA will represent you in all communications — using your name, your tone, your energy. Every message will sound like it came from you personally.</p>
                </div>
              </div>
            )}

            {step === 2 && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-semibold text-[#1A0A2E] mb-2" style={{ fontFamily: 'Plus Jakarta Sans' }}>Calendly Link (optional)</label>
                  <input type="url" value={data.calendly_link} onChange={(e) => setData({...data, calendly_link: e.target.value})} className={inputCls} placeholder="https://calendly.com/your-name/discovery" data-testid="onb-calendly" />
                </div>
                <p className="text-xs text-[#9B8AB0]">ARIA will use this to book discovery calls on your behalf. You can also connect Calendly API later in Settings.</p>
              </div>
            )}

            {step === 3 && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-semibold text-[#1A0A2E] mb-2" style={{ fontFamily: 'Plus Jakarta Sans' }}>Describe your ideal customer</label>
                  <textarea value={data.icp_description} onChange={(e) => setData({...data, icp_description: e.target.value})} rows={4} className={`${inputCls} resize-none`} placeholder="e.g., B2B SaaS founders with $1M-$10M ARR who are struggling to convert inbound leads into booked calls..." data-testid="onb-icp" />
                </div>
                <p className="text-xs text-[#9B8AB0]">ARIA uses this to score and qualify leads. You can refine this anytime in Settings.</p>
              </div>
            )}

            {step === 4 && (
              <div className="text-center py-6">
                <div className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4" style={{ background: 'var(--gradient-brand)' }}>
                  <Rocket size={32} className="text-white" weight="fill" />
                </div>
                <h3 className="text-xl font-bold text-[#1A0A2E] mb-2" style={{ fontFamily: 'Plus Jakarta Sans' }}>You're all set!</h3>
                <p className="text-sm text-[#5A4A7A] mb-4">ARIA is ready to start working for {data.company_name || 'your company'}</p>
                <div className="bg-[#F4F0FF] border border-[#E0D4F7] rounded-xl p-4 text-left space-y-2">
                  {[
                    { check: true, text: `Company: ${data.company_name}` },
                    { check: true, text: `Founder: ${data.founder_name}` },
                    { check: !!data.calendly_link, text: data.calendly_link ? 'Calendly connected' : 'Calendly — set up later' },
                    { check: !!data.icp_description, text: data.icp_description ? 'ICP defined' : 'ICP — define later' },
                  ].map((item, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <CheckCircle size={16} className={item.check ? 'text-[#16A34A]' : 'text-[#9B8AB0]'} weight="fill" />
                      <span className={`text-sm ${item.check ? 'text-[#1A0A2E]' : 'text-[#9B8AB0]'}`}>{item.text}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="p-6 border-t border-[#E8E0F5] flex items-center justify-between">
            {step > 0 && step < 4 ? (
              <button onClick={() => setStep(step - 1)} className="flex items-center gap-2 px-4 py-2.5 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-xl hover:bg-[#F9F5FF] text-sm font-medium" data-testid="onb-back-btn">
                <ArrowLeft size={14} /> Back
              </button>
            ) : <div />}

            {step < 4 ? (
              <button onClick={() => setStep(step + 1)} disabled={!canNext()} className="flex items-center gap-2 btn-gradient px-6 py-2.5 rounded-xl text-sm font-semibold disabled:opacity-40" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid="onb-next-btn">
                {step === 3 ? 'Finish Setup' : 'Continue'} <ArrowRight size={14} />
              </button>
            ) : (
              <button onClick={handleComplete} disabled={saving} className="flex items-center gap-2 btn-gradient px-6 py-2.5 rounded-xl text-sm font-semibold disabled:opacity-50" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid="onb-launch-btn">
                {saving ? 'Setting up...' : 'Launch Dashboard'} <Rocket size={14} />
              </button>
            )}
          </div>
        </div>

        {/* Skip */}
        {step < 4 && (
          <button onClick={() => setStep(4)} className="block mx-auto mt-4 text-xs text-[#9B8AB0] hover:text-[#7C35DC] transition-colors" data-testid="onb-skip-btn">Skip for now</button>
        )}
      </div>
    </div>
  );
};

export default OnboardingWizard;
