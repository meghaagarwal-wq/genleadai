import React, { useState, useEffect } from 'react';
import api from '../config/api';
import { Buildings, Robot, Target, ChatTeardropDots, UsersThree, ArrowRight, ArrowLeft, CheckCircle, Sparkle, WarningCircle, GitBranch } from '@phosphor-icons/react';
import { Toaster, toast } from 'sonner';
import TouchpointMappingStep from '../components/onboarding/TouchpointMappingStep';

const STEPS = [
  { id: 'business', title: 'Business Profile', icon: Buildings },
  { id: 'persona', title: "Aria's Persona", icon: Robot },
  { id: 'sales', title: 'Sales Process', icon: Target },
  { id: 'touchpoints', title: 'Lead Journey', icon: GitBranch },
  { id: 'whatsapp', title: 'WhatsApp', icon: ChatTeardropDots },
  { id: 'team', title: 'Team', icon: UsersThree },
];

const INDUSTRIES = ['SaaS', 'Real Estate', 'E-commerce', 'Healthcare', 'Finance', 'Events', 'Wellbeing', 'Other'];
const TONES = [
  { id: 'formal', label: 'Formal' },
  { id: 'friendly_professional', label: 'Friendly-Professional' },
  { id: 'casual', label: 'Casual' },
  { id: 'aggressive_sales', label: 'Aggressive Sales' },
];
const FALLBACKS = [
  { id: 'ask_clarifying', label: 'Ask clarifying question' },
  { id: 'escalate_to_human', label: 'Escalate to human' },
  { id: 'generic_response', label: 'Give generic response' },
];
const DEAL_SIZES = ['< 50K', '50K - 5L', '5L - 50L', '50L+'];
const SALES_CYCLES = ['< 1 week', '1-4 weeks', '1-3 months', '3+ months'];
const QUAL_CRITERIA = [
  { id: 'budget_confirmed', label: 'Budget confirmed' },
  { id: 'decision_maker_identified', label: 'Decision-maker identified' },
  { id: 'timeline_defined', label: 'Timeline defined' },
  { id: 'need_established', label: 'Need established' },
];
const DEFAULT_PIPELINE = ['New Lead', 'Contacted', 'Qualified', 'Proposal Sent', 'Negotiation', 'Closed Won', 'Closed Lost'];

const OnboardingWizard = () => {
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const [tenantName, setTenantName] = useState('');
  const [submitError, setSubmitError] = useState(null);
  const [touchpointSaved, setTouchpointSaved] = useState(false);

  const [form, setForm] = useState({
    business: {
      business_name: '', industry: 'SaaS', description: '',
      primary_market: 'B2B', country: '', timezone: '',
    },
    persona: {
      aria_name: 'Aria', tone: 'friendly_professional',
      language: 'English', fallback_behavior: 'ask_clarifying',
    },
    sales: {
      product_description: '', deal_size: '50K - 5L', sales_cycle: '1-4 weeks',
      qualification_criteria: ['budget_confirmed', 'decision_maker_identified'],
      pipeline_stages: [...DEFAULT_PIPELINE],
    },
    whatsapp: {
      provider: 'meta', api_key: '', whatsapp_number: '',
    },
  });

  // Load tenant context (active tenant name → seed business_name)
  useEffect(() => {
    let alive = true;
    api.get('/api/onboarding/status').then((r) => {
      if (!alive) return;
      const t = r.data?.tenant;
      if (t?.name) {
        setTenantName(t.name);
        setForm((prev) => ({ ...prev, business: { ...prev.business, business_name: prev.business.business_name || t.name } }));
      }
    }).catch(() => {});
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const update = (section, patch) => setForm((p) => ({ ...p, [section]: { ...p[section], ...patch } }));

  const toggleQual = (id) => {
    const cur = form.sales.qualification_criteria;
    update('sales', { qualification_criteria: cur.includes(id) ? cur.filter(x => x !== id) : [...cur, id] });
  };

  const updateStage = (idx, value) => {
    const next = [...form.sales.pipeline_stages];
    next[idx] = value;
    update('sales', { pipeline_stages: next });
  };
  const removeStage = (idx) => {
    if (form.sales.pipeline_stages.length <= 2) { toast.error('Need at least 2 stages'); return; }
    update('sales', { pipeline_stages: form.sales.pipeline_stages.filter((_, i) => i !== idx) });
  };
  const addStage = () => update('sales', { pipeline_stages: [...form.sales.pipeline_stages, 'New Stage'] });

  const canNext = () => {
    if (step === 0) return form.business.business_name.trim().length > 0;
    if (step === 1) return form.persona.aria_name.trim().length > 0;
    if (step === 2) return form.sales.product_description.trim().length > 0 && form.sales.pipeline_stages.length >= 2;
    if (step === 3) return touchpointSaved;
    if (step === 4) return !!form.whatsapp.compliance_agreed;
    return true;
  };

  const submit = async () => {
    setSaving(true);
    setSubmitError(null);
    try {
      await api.post('/api/onboarding/complete', {
        business_profile: form.business,
        aria_persona: form.persona,
        sales_process: form.sales,
        whatsapp_config: form.whatsapp,
        completed: true,
      });
      // Refresh stored tenant onboarding state
      try {
        const stored = JSON.parse(localStorage.getItem('active_tenant') || 'null');
        if (stored) {
          stored.onboarding_completed = true;
          localStorage.setItem('active_tenant', JSON.stringify(stored));
        }
      } catch (e) { /* ignore */ }
      toast.success('Workspace ready');
      // Hard reload to ensure ProtectedRoute re-fetches fresh onboarding state
      // and avoids any in-flight stale state from the gate's interceptor.
      window.location.replace('/');
    } catch (err) {
      const status = err.response?.status;
      const detail = err.response?.data?.detail;
      const msg = detail
        ? (typeof detail === 'string' ? detail : JSON.stringify(detail))
        : (err.message || 'Could not save onboarding');
      const full = status ? `${msg} (HTTP ${status})` : msg;
      setSubmitError(full);
      toast.error(full);
      // eslint-disable-next-line no-console
      console.error('[Onboarding submit failed]', err);
    } finally {
      setSaving(false);
    }
  };

  const Step = STEPS[step];

  return (
    <div className="min-h-screen flex items-center justify-center p-4" style={{ background: 'linear-gradient(135deg, #FAFAFA 0%, #F4F0FF 100%)' }} data-testid="onboarding-wizard">
      <Toaster position="top-center" richColors closeButton />
      <div className="w-full max-w-2xl">
        {/* Progress */}
        <div className="flex items-center gap-2 mb-6">
          {STEPS.map((s, i) => (
            <div key={s.id} className="flex-1">
              <div className={`h-1.5 rounded-full transition-all ${i < step ? 'bg-[#7C35DC]' : i === step ? 'bg-[#7C35DC]' : 'bg-[#E8E0F5]'}`} />
              <div className={`text-[10px] font-bold uppercase tracking-[0.16em] mt-1.5 text-center ${i <= step ? 'text-[#7C35DC]' : 'text-[#9B8AB0]'}`}>{s.title}</div>
            </div>
          ))}
        </div>

        <div className="bg-white border border-[#E8E0F5] rounded-2xl p-7 shadow-[0_24px_64px_-12px_rgba(76,29,149,0.18)]" data-testid={`onboarding-step-${Step.id}`}>
          <div className="flex items-center gap-3 mb-1">
            <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #4C1D95, #7C35DC)' }}>
              <Step.icon size={18} weight="fill" className="text-white" />
            </div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#7C35DC]">Step {step + 1} of {STEPS.length}</div>
              <h2 className="text-xl font-bold text-[#1A0A2E]">{Step.title}</h2>
            </div>
          </div>

          {tenantName && step === 0 && (
            <div className="text-sm text-[#5A4A7A] mb-4 mt-3">Setting up <span className="font-bold text-[#7C35DC]">{tenantName}</span>. This takes about a minute.</div>
          )}

          <div className="mt-5 space-y-4">
            {/* STEP 0: Business Profile */}
            {step === 0 && (
              <>
                <Field label="Business name" required>
                  <input data-testid="ob-biz-name" value={form.business.business_name}
                    onChange={(e) => update('business', { business_name: e.target.value })} className={inputCls} />
                </Field>
                <Field label="Industry">
                  <select data-testid="ob-biz-industry" value={form.business.industry}
                    onChange={(e) => update('business', { industry: e.target.value })} className={inputCls}>
                    {INDUSTRIES.map(i => <option key={i} value={i}>{i}</option>)}
                  </select>
                </Field>
                <Field label="Business description">
                  <textarea data-testid="ob-biz-description" rows={2} value={form.business.description}
                    onChange={(e) => update('business', { description: e.target.value })} className={inputCls + ' resize-y'}
                    placeholder="What you sell, who you sell to (2-3 lines)" />
                </Field>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Primary market">
                    <select data-testid="ob-biz-market" value={form.business.primary_market}
                      onChange={(e) => update('business', { primary_market: e.target.value })} className={inputCls}>
                      <option value="B2B">B2B</option>
                      <option value="B2C">B2C</option>
                      <option value="Both">Both</option>
                    </select>
                  </Field>
                  <Field label="Country / Timezone">
                    <input data-testid="ob-biz-country" value={form.business.country}
                      onChange={(e) => update('business', { country: e.target.value })} className={inputCls}
                      placeholder="e.g. India / IST" />
                  </Field>
                </div>
              </>
            )}

            {/* STEP 1: Aria Persona */}
            {step === 1 && (
              <>
                <Field label="What should Aria introduce herself as?">
                  <input data-testid="ob-persona-name" value={form.persona.aria_name}
                    onChange={(e) => update('persona', { aria_name: e.target.value })} className={inputCls} />
                </Field>
                <Field label="Communication tone">
                  <div className="grid grid-cols-2 gap-1.5">
                    {TONES.map(t => (
                      <button key={t.id} type="button" data-testid={`ob-persona-tone-${t.id}`}
                        onClick={() => update('persona', { tone: t.id })}
                        className={pillCls(form.persona.tone === t.id)}>{t.label}</button>
                    ))}
                  </div>
                </Field>
                <Field label="Primary language">
                  <input data-testid="ob-persona-language" value={form.persona.language}
                    onChange={(e) => update('persona', { language: e.target.value })} className={inputCls} placeholder="English" />
                </Field>
                <Field label="Fallback when Aria is unsure">
                  <div className="grid grid-cols-1 gap-1.5">
                    {FALLBACKS.map(f => (
                      <button key={f.id} type="button" data-testid={`ob-persona-fallback-${f.id}`}
                        onClick={() => update('persona', { fallback_behavior: f.id })}
                        className={pillCls(form.persona.fallback_behavior === f.id)}>{f.label}</button>
                    ))}
                  </div>
                </Field>
              </>
            )}

            {/* STEP 2: Sales Process */}
            {step === 2 && (
              <>
                <Field label="Product or service description" required>
                  <textarea data-testid="ob-sales-product" rows={2} value={form.sales.product_description}
                    onChange={(e) => update('sales', { product_description: e.target.value })} className={inputCls + ' resize-y'} />
                </Field>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Average deal size">
                    <select data-testid="ob-sales-deal-size" value={form.sales.deal_size}
                      onChange={(e) => update('sales', { deal_size: e.target.value })} className={inputCls}>
                      {DEAL_SIZES.map(d => <option key={d}>{d}</option>)}
                    </select>
                  </Field>
                  <Field label="Sales cycle length">
                    <select data-testid="ob-sales-cycle" value={form.sales.sales_cycle}
                      onChange={(e) => update('sales', { sales_cycle: e.target.value })} className={inputCls}>
                      {SALES_CYCLES.map(s => <option key={s}>{s}</option>)}
                    </select>
                  </Field>
                </div>
                <Field label="Key qualification criteria (multi-select)">
                  <div className="flex flex-wrap gap-1.5">
                    {QUAL_CRITERIA.map(q => (
                      <button key={q.id} type="button" data-testid={`ob-sales-qual-${q.id}`}
                        onClick={() => toggleQual(q.id)}
                        className={pillCls(form.sales.qualification_criteria.includes(q.id))}>{q.label}</button>
                    ))}
                  </div>
                </Field>
                <Field label="Pipeline stages (editable)">
                  <div className="space-y-1.5">
                    {form.sales.pipeline_stages.map((s, i) => (
                      <div key={i} className="flex items-center gap-1.5">
                        <input value={s} onChange={(e) => updateStage(i, e.target.value)} className={inputCls}
                          data-testid={`ob-sales-stage-${i}`} />
                        <button type="button" onClick={() => removeStage(i)}
                          className="px-2.5 py-2 rounded-lg border border-[#E8E0F5] text-[#9B8AB0] hover:text-[#DC2626] hover:border-[#DC2626]/40 text-xs">×</button>
                      </div>
                    ))}
                    <button type="button" onClick={addStage} data-testid="ob-sales-add-stage"
                      className="text-xs font-bold uppercase tracking-[0.14em] text-[#7C35DC] hover:underline">+ Add stage</button>
                  </div>
                </Field>
              </>
            )}

            {/* STEP 3: Touchpoint Mapping (auto-generated from steps 0-2) */}
            {step === 3 && (
              <TouchpointMappingStep
                form={form}
                onSaved={() => {
                  setTouchpointSaved(true);
                  setStep(4);
                }}
                onSkip={() => {
                  setTouchpointSaved(true);
                  setStep(4);
                }}
              />
            )}

            {/* STEP 4: WhatsApp */}
            {step === 4 && (
              <>
                <div className="text-sm text-[#5A4A7A] mb-2">
                  Aria primarily operates over WhatsApp. You can configure this now or later from Settings.
                </div>
                <Field label="Provider">
                  <select data-testid="ob-wa-provider" value={form.whatsapp.provider}
                    onChange={(e) => update('whatsapp', { provider: e.target.value })} className={inputCls}>
                    <option value="meta">Meta WhatsApp Cloud API</option>
                    <option value="360dialog">360dialog (coming soon)</option>
                  </select>
                </Field>
                <Field label="API key (optional now)">
                  <input data-testid="ob-wa-api-key" type="password" value={form.whatsapp.api_key}
                    onChange={(e) => update('whatsapp', { api_key: e.target.value })} className={inputCls}
                    placeholder="Paste later from Settings → Integrations" />
                </Field>
                <Field label="WhatsApp Business number (optional now)">
                  <input data-testid="ob-wa-number" value={form.whatsapp.whatsapp_number}
                    onChange={(e) => update('whatsapp', { whatsapp_number: e.target.value })} className={inputCls}
                    placeholder="+91…" />
                </Field>
                <div className="text-xs text-[#5A4A7A] bg-[#F4F0FF] border border-[#7C35DC]/20 rounded-lg p-3">
                  <span className="font-bold text-[#7C35DC]">Webhook URL:</span> auto-generated after onboarding.
                  Find it under Settings → Integrations once you're in.
                </div>

                {/* Compliance checkbox (Meta Business Messaging Policy) */}
                <div className="bg-[#FEF3C7] border border-[#F59E0B]/40 rounded-lg p-3 mt-3" data-testid="ob-wa-compliance">
                  <div className="text-xs text-[#92400E] font-bold mb-2">⚠ Meta Business Messaging Policy</div>
                  <div className="text-[11px] text-[#92400E]/85 mb-2 leading-relaxed">
                    WhatsApp Business API requires explicit opt-in from every lead before automated outreach. Aria will only message leads who have opted in via a website form, replied first, or been manually confirmed by you.
                  </div>
                  <label className="flex items-start gap-2 text-[11px] text-[#92400E] cursor-pointer">
                    <input type="checkbox" data-testid="ob-wa-compliance-checkbox"
                      checked={!!form.whatsapp.compliance_agreed}
                      onChange={(e) => update('whatsapp', { compliance_agreed: e.target.checked })}
                      className="mt-0.5" />
                    <span><strong>I agree to message only opted-in leads.</strong> I understand violations may result in suspension by Meta.</span>
                  </label>
                </div>
              </>
            )}

            {/* STEP 5: Team (skippable) */}
            {step === 5 && (
              <>
                <div className="text-sm text-[#5A4A7A]">
                  You can invite teammates right now or later from <span className="font-bold">Settings → Team</span>.
                </div>
                <div className="bg-[#F4F0FF] border border-[#7C35DC]/20 rounded-lg p-4 space-y-2">
                  <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-[#7C35DC]">PLAN LIMITS</div>
                  <div className="text-sm text-[#1A0A2E]">Free plan: <span className="font-bold">3 seats</span>, unlimited on paid plans.</div>
                  <div className="text-xs text-[#5A4A7A]">Skip this and ship — you can come back any time.</div>
                </div>
                <div className="flex items-center gap-2 mt-2">
                  <CheckCircle size={16} weight="fill" className="text-[#7C35DC]" />
                  <span className="text-sm text-[#1A0A2E]">Workspace ready to ship.</span>
                </div>
              </>
            )}
          </div>

          {/* Inline error (visible without depending on toast portal) */}
          {submitError && (
            <div className="mt-4 flex items-start gap-2 px-3 py-2.5 rounded-lg bg-red-50 border border-red-200 text-[#B91C1C] text-sm" data-testid="onboarding-submit-error">
              <WarningCircle size={16} weight="fill" className="mt-0.5 flex-shrink-0" />
              <div className="flex-1">
                <div className="font-bold">Couldn't launch workspace</div>
                <div className="text-xs opacity-90 mt-0.5">{submitError}</div>
              </div>
            </div>
          )}

          {/* Nav */}
          <div className="flex justify-between items-center pt-6 mt-6 border-t border-[#F0ECF9]">
            <button type="button" disabled={step === 0} onClick={() => setStep((s) => Math.max(0, s - 1))}
              data-testid="ob-back" className="flex items-center gap-1 text-sm font-bold text-[#5A4A7A] hover:text-[#7C35DC] disabled:opacity-40">
              <ArrowLeft size={14} /> Back
            </button>
            {/* Step 3 (touchpoints) handles its own Continue/Customise CTAs internally */}
            {step === 3 ? (
              <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#9B8AB0]">
                {touchpointSaved ? 'Saved · advancing…' : 'Choose to continue'}
              </span>
            ) : step < STEPS.length - 1 ? (
              <button type="button" disabled={!canNext()} onClick={() => setStep((s) => s + 1)}
                data-testid="ob-next"
                className="flex items-center gap-1.5 px-5 py-2.5 rounded-lg text-white text-sm font-bold disabled:opacity-50"
                style={{ background: 'linear-gradient(135deg, #4C1D95, #7C35DC)' }}>
                Next <ArrowRight size={14} />
              </button>
            ) : (
              <button type="button" disabled={saving} onClick={submit} data-testid="ob-finish"
                className="flex items-center gap-1.5 px-5 py-2.5 rounded-lg text-white text-sm font-bold disabled:opacity-50"
                style={{ background: 'linear-gradient(135deg, #4C1D95, #7C35DC)' }}>
                <Sparkle size={14} weight="fill" /> {saving ? 'Setting up…' : 'Launch workspace'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

const inputCls = "w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3.5 py-2.5 rounded-lg text-sm focus:border-[#7C35DC] focus:ring-2 focus:ring-[#7C35DC]/15 outline-none transition";
const pillCls = (active) => `px-3 py-2 rounded-lg text-xs font-bold uppercase tracking-[0.1em] border transition ${active ? 'bg-[#7C35DC] text-white border-[#7C35DC]' : 'bg-white text-[#5A4A7A] border-[#E8E0F5] hover:border-[#7C35DC]/40'}`;

const Field = ({ label, required, children }) => (
  <div>
    <label className="block text-[11px] font-bold uppercase tracking-[0.16em] text-[#5A4A7A] mb-1.5">
      {label} {required && <span className="text-[#DC2626]">*</span>}
    </label>
    {children}
  </div>
);

export default OnboardingWizard;
