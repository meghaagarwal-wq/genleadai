/**
 * Iter101 — V3 5-step onboarding wizard.
 *
 * Replaces the legacy 7-step wizard with a focused V3 flow:
 *   1. Workspace identity     — business name + mode (B2B / B2C / Hybrid)
 *   2. Train ARIA             — upload pitch doc (or skip)
 *   3. Connect a lead source  — Saleshandy / Lemlist / Apollo / skip
 *   4. Configure ICPs         — quick add 1–3 ICPs
 *   5. Ready                  — summary + go to dashboard
 *
 * All steps are skippable (except step 1) so founders can ship fast and
 * tune later inside Train ARIA. Persists to the same training-profile
 * endpoint TrainAriaV2 uses.
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, ArrowLeft, Check, CheckCircle } from '@phosphor-icons/react';
import { toast } from 'sonner';
import api from '../config/api';

const STEPS = [
  { id: 'identity',   label: 'Workspace' },
  { id: 'train',      label: 'Train ARIA' },
  { id: 'leads',      label: 'Lead source' },
  { id: 'icps',       label: 'ICPs' },
  { id: 'ready',      label: 'Ready' },
];

const MODES = [
  { id: 'b2b',    label: 'B2B',    desc: 'Outbound + Insights Engine. For sales-led businesses.' },
  { id: 'b2c',    label: 'B2C',    desc: 'Inbound only — Aria handles leads from your forms.' },
  { id: 'hybrid', label: 'Hybrid', desc: 'Both. Recommended for most workspaces.' },
];

const LEAD_SOURCES = [
  { id: 'saleshandy', label: 'Saleshandy',   desc: 'Outbound email sequences' },
  { id: 'lemlist',    label: 'Lemlist',      desc: 'LinkedIn + email outreach' },
  { id: 'apollo',     label: 'Apollo',       desc: 'Active lead pulling from saved searches' },
  { id: 'pixel',      label: 'Website Pixel', desc: 'Auto-capture from your website forms' },
];

const Stepper = ({ active }) => (
  <div className="flex items-center justify-center gap-1.5 mb-8" data-testid="onboard5-stepper">
    {STEPS.map((s, i) => (
      <div key={s.id} className="flex items-center gap-1.5">
        <div
          data-testid={`onboard5-step-pill-${s.id}`}
          className={`h-1.5 w-12 rounded-full transition-all ${
            i < active ? 'bg-[#7C35DC]' : i === active ? 'bg-[#7C35DC]' : 'bg-[#E2E8F0]'
          }`}
        />
        {i < STEPS.length - 1 && <span className="w-2 h-px bg-transparent" />}
      </div>
    ))}
  </div>
);

const OnboardingWizardV3 = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [stateLoaded, setStateLoaded] = useState(false);

  // Form state
  const [businessName, setBusinessName] = useState('');
  const [mode, setMode] = useState('hybrid');
  const [trainFile, setTrainFile] = useState(null);
  const [trainSummary, setTrainSummary] = useState(null);
  const [leadSource, setLeadSource] = useState(null);
  const [leadApiKey, setLeadApiKey] = useState('');
  const [icps, setIcps] = useState([{ name: '', industry: '', pain: '' }]);

  // iter103 — Resume from persisted state on first mount.
  useState(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await api.get('/api/onboarding/state');
        if (cancelled) return;
        const s = r.data?.state || {};
        if (s.business_name) setBusinessName(s.business_name);
        if (s.mode)          setMode(s.mode);
        if (s.lead_source)   setLeadSource(s.lead_source);
        if (typeof s.step === 'number' && !s.completed) setStep(Math.min(s.step, STEPS.length - 1));
      } catch (e) { /* first visit / not authed yet */ }
      setStateLoaded(true);
    })();
    return () => { cancelled = true; };
  });

  // iter103 — Persist state on every step change (after initial load).
  const persistState = (partial = {}) => {
    if (!stateLoaded) return;
    const body = {
      step, business_name: businessName, mode, lead_source: leadSource,
      completed: false, payload: {},
      ...partial,
    };
    api.put('/api/onboarding/state', body).catch(() => {});
  };

  const canAdvance = () => {
    if (step === 0) return businessName.trim().length >= 2;
    return true;  // every other step is skippable
  };

  const next = () => { const s = Math.min(STEPS.length - 1, step + 1); setStep(s); persistState({ step: s }); };
  const back = () => { const s = Math.max(0, step - 1); setStep(s); persistState({ step: s }); };

  // ─── Persist helpers ──────────────────────────────────────────────────
  const saveWorkspaceMode = async () => {
    try {
      await api.put('/api/aria/workspace-type', { workspace_type: mode });
    } catch (e) {
      // best-effort — the dashboard defaults to hybrid if missing
    }
  };

  const uploadAndExtract = async () => {
    if (!trainFile) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append('file', trainFile);
      const r = await api.post('/api/aria/training-profile/extract-from-document', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setTrainSummary(r.data);
      toast.success(`Extracted ${r.data.fields_extracted} fields · ${r.data.icps_extracted} ICPs`);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Extraction failed');
    } finally { setBusy(false); }
  };

  const saveIcps = async () => {
    const cleaned = icps
      .map(i => ({
        icp_name: (i.name || '').trim(),
        target_industries: i.industry ? [i.industry.trim()] : [],
        pain_points: i.pain ? [i.pain.trim()] : [],
      }))
      .filter(i => i.icp_name);
    if (cleaned.length === 0) return;
    try {
      // Read current → merge → put
      const cur = await api.get('/api/aria/training-profile');
      const data = cur.data?.data || {};
      data.icp_profiles = [...(data.icp_profiles || []), ...cleaned];
      await api.put('/api/aria/training-profile', { data });
    } catch (e) { /* non-fatal */ }
  };

  const finish = async () => {
    setBusy(true);
    try {
      await saveWorkspaceMode();
      if (icps.some(i => i.name)) await saveIcps();
      // iter103 — mark wizard completed so user lands directly on dashboard
      // on next login instead of being looped back into onboarding.
      try { await api.put('/api/onboarding/state', { step: STEPS.length - 1, business_name: businessName, mode, lead_source: leadSource, completed: true, payload: {} }); } catch { /* ignore */ }
      toast.success("You're all set — Aria is live.");
      navigate('/pt');
    } catch (e) { toast.error('Could not finalize'); }
    finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex flex-col items-center justify-center px-4 py-8" data-testid="onboard5-wizard">
      <div className="w-full max-w-2xl">
        <div className="text-center mb-2">
          <div className="inline-flex items-center gap-2">
            <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #7C35DC, #C044E0)' }}>
              <span className="text-white font-extrabold text-lg">A</span>
            </div>
            <span className="text-lg font-extrabold text-[#0F172A]" style={{ fontFamily: 'Space Grotesk, Inter' }}>GenLeadAI Aria</span>
          </div>
        </div>
        <p className="text-center text-sm text-[#64748B] mb-6">5 steps · about 3 minutes</p>

        <Stepper active={step} />

        <div className="bg-white border border-[#E2E8F0] rounded-xl p-6 shadow-sm">
          {/* STEP 1 — Identity */}
          {step === 0 && (
            <div data-testid="onboard5-step-identity">
              <h1 className="text-xl font-extrabold text-[#0F172A] mb-1">What should we call your workspace?</h1>
              <p className="text-sm text-[#64748B] mb-5">Your business name. You can change it anytime.</p>
              <input
                data-testid="onboard5-business-name"
                value={businessName} onChange={(e) => setBusinessName(e.target.value)}
                placeholder="Acme Co"
                className="w-full text-base border border-[#E2E8F0] rounded-md px-3 py-2.5 mb-5"
              />
              <div className="text-sm font-semibold text-[#475569] mb-2">How will you use ARIA?</div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                {MODES.map(m => (
                  <button
                    key={m.id}
                    data-testid={`onboard5-mode-${m.id}`}
                    onClick={() => setMode(m.id)}
                    className={`text-left p-3 rounded-md border transition ${mode === m.id ? 'border-[#7C35DC] bg-violet-50' : 'border-[#E2E8F0] bg-white hover:bg-[#F8FAFC]'}`}
                  >
                    <div className="text-sm font-bold text-[#0F172A]">{m.label}</div>
                    <div className="text-xs text-[#64748B] mt-0.5">{m.desc}</div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* STEP 2 — Train ARIA */}
          {step === 1 && (
            <div data-testid="onboard5-step-train">
              <h1 className="text-xl font-extrabold text-[#0F172A] mb-1">Train ARIA on your business</h1>
              <p className="text-sm text-[#64748B] mb-5">
                Upload a pitch deck, GTM brief, or one-pager. ARIA will extract your offering, ICPs, and brand voice automatically. Skip if you'd rather fill it in manually later.
              </p>
              {!trainSummary ? (
                <>
                  <label className="block">
                    <span className="text-xs font-semibold text-[#475569] mb-1 block">PDF, DOCX, or TXT</span>
                    <input
                      type="file"
                      accept=".pdf,.docx,.txt"
                      onChange={(e) => setTrainFile(e.target.files?.[0] || null)}
                      data-testid="onboard5-train-file"
                      className="block w-full text-sm border border-[#E2E8F0] rounded-md p-2"
                    />
                  </label>
                  <button
                    onClick={uploadAndExtract}
                    disabled={!trainFile || busy}
                    data-testid="onboard5-train-extract"
                    className="mt-3 text-sm font-semibold text-white bg-[#7C35DC] hover:bg-[#6928BC] px-4 py-2 rounded-md disabled:opacity-50"
                  >
                    {busy ? 'Extracting…' : 'Extract with ARIA'}
                  </button>
                </>
              ) : (
                <div className="bg-violet-50 border border-violet-200 rounded-md p-4" data-testid="onboard5-train-summary">
                  <div className="text-sm font-bold text-[#7C35DC] mb-1">
                    <Check size={14} weight="bold" className="inline mr-1" />
                    Extracted {trainSummary.fields_extracted} fields · {trainSummary.icps_extracted} ICPs
                  </div>
                  {trainSummary.extracted_preview?.what_you_sell && (
                    <div className="text-xs text-[#475569] mt-2">
                      <strong>What you sell:</strong> {trainSummary.extracted_preview.what_you_sell}
                    </div>
                  )}
                  {trainSummary.extracted_preview?.who_you_sell_to && (
                    <div className="text-xs text-[#475569] mt-1">
                      <strong>Who you sell to:</strong> {trainSummary.extracted_preview.who_you_sell_to}
                    </div>
                  )}
                  <button onClick={() => { setTrainFile(null); setTrainSummary(null); }} className="text-xs text-[#7C35DC] font-semibold mt-2">Re-upload</button>
                </div>
              )}
            </div>
          )}

          {/* STEP 3 — Lead source */}
          {step === 2 && (
            <div data-testid="onboard5-step-leads">
              <h1 className="text-xl font-extrabold text-[#0F172A] mb-1">Where will leads come from?</h1>
              <p className="text-sm text-[#64748B] mb-5">Pick one to start. You can add more in Integrations later.</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mb-4">
                {LEAD_SOURCES.map(s => (
                  <button
                    key={s.id}
                    data-testid={`onboard5-leadsource-${s.id}`}
                    onClick={() => setLeadSource(s.id)}
                    className={`text-left p-3 rounded-md border transition ${leadSource === s.id ? 'border-[#7C35DC] bg-violet-50' : 'border-[#E2E8F0] bg-white hover:bg-[#F8FAFC]'}`}
                  >
                    <div className="text-sm font-bold text-[#0F172A]">{s.label}</div>
                    <div className="text-xs text-[#64748B] mt-0.5">{s.desc}</div>
                  </button>
                ))}
              </div>
              {leadSource && leadSource !== 'pixel' && (
                <div>
                  <label className="block text-xs font-semibold text-[#475569] mb-1">{LEAD_SOURCES.find(x => x.id === leadSource)?.label} API key (optional — add later in Integrations)</label>
                  <input
                    type="password" value={leadApiKey} onChange={(e) => setLeadApiKey(e.target.value)}
                    placeholder="Paste API key"
                    data-testid="onboard5-leadsource-key"
                    className="w-full text-sm border border-[#E2E8F0] rounded-md px-2 py-1.5"
                  />
                </div>
              )}
            </div>
          )}

          {/* STEP 4 — ICPs */}
          {step === 3 && (
            <div data-testid="onboard5-step-icps">
              <h1 className="text-xl font-extrabold text-[#0F172A] mb-1">Who are your ideal customers?</h1>
              <p className="text-sm text-[#64748B] mb-5">
                Add 1–3 ICPs. ARIA uses them to score every new lead and pick the right resources from your library.
              </p>
              {icps.map((icp, i) => (
                <div key={i} className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-md p-3 mb-2" data-testid={`onboard5-icp-${i}`}>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                    <input value={icp.name} onChange={(e) => setIcps(icps.map((x, idx) => idx === i ? { ...x, name: e.target.value } : x))}
                      placeholder="ICP name (e.g. SaaS founders)" className="text-sm border border-[#E2E8F0] rounded-md px-2 py-1.5" />
                    <input value={icp.industry} onChange={(e) => setIcps(icps.map((x, idx) => idx === i ? { ...x, industry: e.target.value } : x))}
                      placeholder="Industry" className="text-sm border border-[#E2E8F0] rounded-md px-2 py-1.5" />
                    <input value={icp.pain} onChange={(e) => setIcps(icps.map((x, idx) => idx === i ? { ...x, pain: e.target.value } : x))}
                      placeholder="Main pain-point" className="text-sm border border-[#E2E8F0] rounded-md px-2 py-1.5" />
                  </div>
                </div>
              ))}
              {icps.length < 3 && (
                <button onClick={() => setIcps([...icps, { name: '', industry: '', pain: '' }])} data-testid="onboard5-icp-add" className="text-xs font-semibold text-[#7C35DC]">+ Add another ICP</button>
              )}
            </div>
          )}

          {/* STEP 5 — Ready */}
          {step === 4 && (
            <div className="text-center" data-testid="onboard5-step-ready">
              <CheckCircle size={48} weight="duotone" className="text-[#16A34A] mx-auto mb-3" />
              <h1 className="text-xl font-extrabold text-[#0F172A] mb-1">{businessName || 'Your workspace'} is ready</h1>
              <p className="text-sm text-[#64748B] mb-5">
                ARIA is trained and watching for new leads. You can refine your setup anytime in <strong>Train ARIA</strong>.
              </p>
              <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-md p-3 text-left text-xs text-[#475569] space-y-1.5 max-w-md mx-auto">
                <div><Check size={11} className="inline text-[#16A34A] mr-1" /> Workspace mode: <strong>{MODES.find(m => m.id === mode)?.label}</strong></div>
                <div><Check size={11} className="inline text-[#16A34A] mr-1" /> ARIA training: <strong>{trainSummary ? `${trainSummary.fields_extracted} fields extracted` : 'will fill in later'}</strong></div>
                <div><Check size={11} className="inline text-[#16A34A] mr-1" /> Lead source: <strong>{leadSource ? LEAD_SOURCES.find(x => x.id === leadSource)?.label : 'will set up later'}</strong></div>
                <div><Check size={11} className="inline text-[#16A34A] mr-1" /> ICPs added: <strong>{icps.filter(i => i.name).length}</strong></div>
              </div>
            </div>
          )}
        </div>

        {/* Nav */}
        <div className="flex items-center justify-between mt-5">
          <button
            onClick={back} disabled={step === 0}
            data-testid="onboard5-back"
            className="text-sm font-semibold text-[#475569] inline-flex items-center gap-1 disabled:opacity-30"
          >
            <ArrowLeft size={14} /> Back
          </button>
          {step < STEPS.length - 1 ? (
            <button
              onClick={next} disabled={!canAdvance() || busy}
              data-testid="onboard5-next"
              className="text-sm font-semibold text-white bg-[#7C35DC] hover:bg-[#6928BC] px-4 py-2 rounded-md disabled:opacity-50 inline-flex items-center gap-1.5"
            >
              {step === 0 ? 'Continue' : 'Continue'} <ArrowRight size={14} />
            </button>
          ) : (
            <button
              onClick={finish} disabled={busy}
              data-testid="onboard5-finish"
              className="text-sm font-semibold text-white bg-[#16A34A] hover:bg-[#15803D] px-5 py-2 rounded-md disabled:opacity-50 inline-flex items-center gap-1.5"
            >
              {busy ? 'Finalizing…' : 'Go to dashboard'} <ArrowRight size={14} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default OnboardingWizardV3;
