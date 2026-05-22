// Iter79 — S8 4-step simplified onboarding wizard.
// 1. Client identity → 2. API keys → 3. Quick configure → 4. Launch summary.
import React, { useState } from 'react';
import { toast } from 'sonner';
import { ArrowRight, ArrowLeft, Rocket, CheckCircle, X, Buildings, Key, Target, Sparkle } from '@phosphor-icons/react';
import api from '../../config/api';

const STEPS = [
  { key: 'identity', label: 'Client Identity', icon: Buildings },
  { key: 'keys',     label: 'API Keys',       icon: Key },
  { key: 'config',   label: 'Quick Configure', icon: Target },
  { key: 'launch',   label: 'Launch',         icon: Rocket },
];

export default function OnboardingWizard({ onClose, onLaunched }) {
  const [stepIdx, setStepIdx] = useState(0);
  const [s1, setS1] = useState({ business_name: '', founder_name: '', founder_email: '', industry: '', primary_market: 'India', primary_language: 'en' });
  const [s2, setS2] = useState({ whatsapp_provider: 'meta_cloud_api', whatsapp_access_token: '', whatsapp_phone_number_id: '', whatsapp_display_phone: '', email_from_name: '', email_from_address: '', resend_api_key: '', crm_webhook_url: '', calendly_link: '' });
  const [s3, setS3] = useState({ icp_industry: '', icp_target_title: '', icp_pain_point: '', preferred_channel: 'email' });
  const [launching, setLaunching] = useState(false);
  const [launched, setLaunched] = useState(null);

  const valid1 = s1.business_name.trim().length >= 2 && s1.founder_name.trim().length >= 2 && /@/.test(s1.founder_email);
  const valid3 = !!s3.preferred_channel;

  const next = () => setStepIdx((i) => Math.min(i + 1, STEPS.length - 1));
  const back = () => setStepIdx((i) => Math.max(i - 1, 0));

  const launch = async () => {
    setLaunching(true);
    try {
      const r = await api.post('/api/admin/deployments/onboard', {
        step1: { ...s1, primary_language: s1.primary_language || 'en' },
        step2: { ...s2 },
        step3: { ...s3 },
      });
      setLaunched(r.data);
      toast.success(`Aria launched for ${s1.business_name} — status ${r.data.status}`);
    } catch (e) {
      const d = e?.response?.data?.detail;
      toast.error(typeof d === 'string' ? d : 'Onboarding failed');
    } finally { setLaunching(false); }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center z-50 p-4" data-testid="onboarding-wizard">
      <div className="bg-white rounded-3xl max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-2xl">
        <div className="sticky top-0 bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between rounded-t-3xl">
          <h2 className="text-lg font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Launch a new Aria deployment</h2>
          <button type="button" onClick={onClose} data-testid="wizard-close" className="text-slate-400 hover:text-slate-700"><X size={18} weight="bold" /></button>
        </div>

        {/* Stepper */}
        <ol className="px-6 pt-4 flex items-center justify-between gap-2 max-w-xl mx-auto">
          {STEPS.map((s, i) => {
            const Icon = s.icon;
            const isActive = i === stepIdx && !launched;
            const isDone = i < stepIdx || launched;
            return (
              <li key={s.key} className="flex items-center flex-1 min-w-0">
                <div className={`flex flex-col items-center text-center ${isActive || isDone ? 'opacity-100' : 'opacity-50'}`}>
                  <div className={`w-9 h-9 rounded-full flex items-center justify-center border-2 ${isDone ? 'bg-violet-600 border-violet-600 text-white' : isActive ? 'bg-white border-violet-600 text-violet-700' : 'bg-white border-slate-300 text-slate-400'}`}>
                    {isDone ? <CheckCircle size={14} weight="fill" /> : <Icon size={14} weight="duotone" />}
                  </div>
                  <div className={`text-[9px] mt-1 font-bold uppercase tracking-wider ${isActive ? 'text-violet-700' : isDone ? 'text-slate-700' : 'text-slate-400'}`}>{s.label}</div>
                </div>
                {i < STEPS.length - 1 && <div className={`flex-1 h-0.5 mx-1.5 ${isDone ? 'bg-violet-600' : 'bg-slate-200'}`} />}
              </li>
            );
          })}
        </ol>

        <div className="px-6 py-6 space-y-3">
          {launched ? (
            <SuccessPanel launched={launched} onDone={onLaunched} />
          ) : stepIdx === 0 ? (
            <>
              <FieldTxt label="Business name *" value={s1.business_name} onChange={(v) => setS1({ ...s1, business_name: v })} placeholder="Acme SaaS" testid="wiz-business-name" />
              <Field2Col>
                <FieldTxt label="Founder name *" value={s1.founder_name} onChange={(v) => setS1({ ...s1, founder_name: v })} placeholder="Jane Doe" testid="wiz-founder-name" />
                <FieldTxt label="Founder email *" value={s1.founder_email} onChange={(v) => setS1({ ...s1, founder_email: v })} placeholder="jane@acme.com" type="email" testid="wiz-founder-email" />
              </Field2Col>
              <Field2Col>
                <FieldTxt label="Industry" value={s1.industry} onChange={(v) => setS1({ ...s1, industry: v })} placeholder="SaaS" />
                <FieldTxt label="Primary market" value={s1.primary_market} onChange={(v) => setS1({ ...s1, primary_market: v })} placeholder="India" />
              </Field2Col>
              <FieldTxt label="Primary language" value={s1.primary_language} onChange={(v) => setS1({ ...s1, primary_language: v })} placeholder="en" />
            </>
          ) : stepIdx === 1 ? (
            <>
              <p className="text-xs text-slate-500">Skip any block you'll fill in later — Aria will mark the deployment as <strong>Setup</strong> until at least one channel is configured.</p>
              <div className="rounded-2xl border border-slate-200 p-4 space-y-2">
                <div className="flex items-center justify-between"><h4 className="text-xs font-extrabold uppercase tracking-wider text-slate-700">WhatsApp</h4></div>
                <Field2Col>
                  <FieldSelect label="Provider" value={s2.whatsapp_provider} onChange={(v) => setS2({ ...s2, whatsapp_provider: v })} options={[{ v: 'meta_cloud_api', l: 'Meta Cloud API' }, { v: '360dialog', l: '360dialog' }]} />
                  <FieldTxt label="Display phone" value={s2.whatsapp_display_phone} onChange={(v) => setS2({ ...s2, whatsapp_display_phone: v })} placeholder="+91 98XXXXXXXX" />
                </Field2Col>
                <FieldTxt label="Access token" value={s2.whatsapp_access_token} onChange={(v) => setS2({ ...s2, whatsapp_access_token: v })} placeholder="EAAxxxxx..." testid="wiz-wa-token" />
                <FieldTxt label="Phone Number ID" value={s2.whatsapp_phone_number_id} onChange={(v) => setS2({ ...s2, whatsapp_phone_number_id: v })} placeholder="123456789012345" />
              </div>
              <div className="rounded-2xl border border-slate-200 p-4 space-y-2">
                <h4 className="text-xs font-extrabold uppercase tracking-wider text-slate-700">Email</h4>
                <Field2Col>
                  <FieldTxt label="From name" value={s2.email_from_name} onChange={(v) => setS2({ ...s2, email_from_name: v })} placeholder="Jane @ Acme" />
                  <FieldTxt label="From address" value={s2.email_from_address} onChange={(v) => setS2({ ...s2, email_from_address: v })} placeholder="jane@acme.com" type="email" testid="wiz-email-from" />
                </Field2Col>
                <FieldTxt label="Resend API key" value={s2.resend_api_key} onChange={(v) => setS2({ ...s2, resend_api_key: v })} placeholder="re_..." testid="wiz-resend-key" />
              </div>
              <div className="rounded-2xl border border-slate-200 p-4 space-y-2">
                <h4 className="text-xs font-extrabold uppercase tracking-wider text-slate-700">Optional</h4>
                <FieldTxt label="CRM webhook URL" value={s2.crm_webhook_url} onChange={(v) => setS2({ ...s2, crm_webhook_url: v })} placeholder="https://hooks.crm.io/in/abc" />
                <FieldTxt label="Calendly link" value={s2.calendly_link} onChange={(v) => setS2({ ...s2, calendly_link: v })} placeholder="https://calendly.com/jane/intro" />
              </div>
            </>
          ) : stepIdx === 2 ? (
            <>
              <p className="text-xs text-slate-500">We'll auto-create one ICP and a 3-step default touchpoint sequence so the deployment can go LIVE immediately.</p>
              <Field2Col>
                <FieldTxt label="ICP industry" value={s3.icp_industry} onChange={(v) => setS3({ ...s3, icp_industry: v })} placeholder="SaaS" />
                <FieldTxt label="Target title" value={s3.icp_target_title} onChange={(v) => setS3({ ...s3, icp_target_title: v })} placeholder="CTO" testid="wiz-icp-title" />
              </Field2Col>
              <FieldTxt label="Pain point" value={s3.icp_pain_point} onChange={(v) => setS3({ ...s3, icp_pain_point: v })} placeholder="Manual lead qualification eats the founder's calendar" multiline />
              <FieldSelect label="Preferred outreach channel" value={s3.preferred_channel} onChange={(v) => setS3({ ...s3, preferred_channel: v })} options={[{ v: 'email', l: 'Email first' }, { v: 'whatsapp', l: 'WhatsApp first' }, { v: 'linkedin', l: 'LinkedIn first' }]} testid="wiz-preferred-channel" />
            </>
          ) : (
            // Step 4 — Launch summary
            <div className="space-y-3" data-testid="wiz-summary">
              <SummaryRow label="Business" value={s1.business_name} />
              <SummaryRow label="Founder" value={`${s1.founder_name} · ${s1.founder_email}`} />
              <SummaryRow label="Industry / market" value={`${s1.industry || '—'} · ${s1.primary_market || '—'}`} />
              <SummaryRow label="WhatsApp" value={s2.whatsapp_phone_number_id ? `${s2.whatsapp_provider} · ${s2.whatsapp_display_phone || s2.whatsapp_phone_number_id}` : 'Not configured'} />
              <SummaryRow label="Email" value={s2.email_from_address ? `${s2.email_from_name || ''} <${s2.email_from_address}>` : 'Not configured'} />
              <SummaryRow label="ICP" value={s3.icp_target_title ? `${s3.icp_target_title} @ ${s3.icp_industry || 'any industry'}` : 'Default'} />
              <SummaryRow label="Channel" value={s3.preferred_channel} />
            </div>
          )}
        </div>

        {/* Footer */}
        {!launched && (
          <div className="sticky bottom-0 bg-white border-t border-slate-200 px-6 py-3 flex items-center justify-between gap-2 rounded-b-3xl">
            <button type="button" onClick={back} disabled={stepIdx === 0} className="px-3 py-2 rounded-lg text-xs font-bold text-slate-600 hover:bg-slate-100 disabled:opacity-30 inline-flex items-center gap-1"><ArrowLeft size={12} weight="bold" /> Back</button>
            {stepIdx < STEPS.length - 1 ? (
              <button
                type="button"
                onClick={next}
                disabled={(stepIdx === 0 && !valid1) || (stepIdx === 2 && !valid3)}
                data-testid={`wiz-next-${STEPS[stepIdx].key}`}
                className="inline-flex items-center gap-1 px-4 py-2 rounded-lg bg-slate-900 text-white text-xs font-bold hover:bg-slate-800 disabled:opacity-40"
              >
                Next <ArrowRight size={12} weight="bold" />
              </button>
            ) : (
              <button
                type="button"
                onClick={launch}
                disabled={launching || !valid1}
                data-testid="wiz-launch-btn"
                className="inline-flex items-center gap-1 px-5 py-2 rounded-lg bg-gradient-to-r from-[#7C35DC] to-[#C044E0] text-white text-xs font-extrabold hover:opacity-95 disabled:opacity-50 shadow"
              >
                <Rocket size={12} weight="fill" /> {launching ? 'Launching…' : `Launch Aria for ${s1.business_name || 'this client'}`}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function SuccessPanel({ launched, onDone }) {
  return (
    <div className="text-center py-8 space-y-3" data-testid="wiz-success">
      <div className="inline-flex items-center justify-center w-16 h-16 rounded-3xl bg-gradient-to-br from-emerald-500 to-teal-600 text-white shadow-lg">
        <CheckCircle size={28} weight="fill" />
      </div>
      <h3 className="text-lg font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Deployment launched</h3>
      <p className="text-sm text-slate-600">Tenant <code className="text-xs bg-slate-100 px-1.5 py-0.5 rounded">{launched.tenant_id}</code> is now <strong className={launched.status === 'LIVE' ? 'text-emerald-700' : 'text-amber-700'}>{launched.status}</strong>.</p>
      <button type="button" onClick={onDone} data-testid="wiz-success-done" className="px-4 py-2 rounded-lg bg-violet-600 text-white text-xs font-bold hover:bg-violet-700">Back to deployments</button>
    </div>
  );
}

const FieldTxt = ({ label, value, onChange, placeholder, type = 'text', multiline = false, testid }) => (
  <label className="block">
    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-600">{label}</span>
    {multiline ? (
      <textarea value={value || ''} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} data-testid={testid} rows={2} className="mt-0.5 w-full text-xs bg-white border border-slate-200 rounded-lg px-2.5 py-2 focus:outline-none focus:border-violet-500 resize-none" />
    ) : (
      <input type={type} value={value || ''} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} data-testid={testid} className="mt-0.5 w-full text-xs bg-white border border-slate-200 rounded-lg px-2.5 py-2 focus:outline-none focus:border-violet-500" />
    )}
  </label>
);

const FieldSelect = ({ label, value, onChange, options, testid }) => (
  <label className="block">
    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-600">{label}</span>
    <select value={value} onChange={(e) => onChange(e.target.value)} data-testid={testid} className="mt-0.5 w-full text-xs bg-white border border-slate-200 rounded-lg px-2.5 py-2 focus:outline-none focus:border-violet-500">
      {options.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
    </select>
  </label>
);

const Field2Col = ({ children }) => <div className="grid grid-cols-2 gap-3">{children}</div>;

const SummaryRow = ({ label, value }) => (
  <div className="flex items-start justify-between gap-3 py-1.5 border-b border-slate-100">
    <dt className="text-[10px] font-bold uppercase tracking-wider text-slate-500 w-32 flex-shrink-0">{label}</dt>
    <dd className="text-xs text-slate-800 text-right">{value || <em className="text-slate-400">—</em>}</dd>
  </div>
);
