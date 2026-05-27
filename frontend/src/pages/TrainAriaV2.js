import React, { useEffect, useState, useCallback, useRef } from 'react';
import api from '../config/api';
import { toast } from 'sonner';

const SECTIONS = [
  { id: 'identity',    label: '01 — Business Identity' },
  { id: 'icps',        label: '02 — Ideal Customers' },
  { id: 'qualify',     label: '03 — Qualification' },
  { id: 'voice',       label: '04 — Brand Voice' },
  { id: 'objections',  label: '05 — Objections + FAQ' },
  { id: 'booking',     label: '06 — Booking Rules' },
  { id: 'insights',    label: '07 — Insights Engine' },
  { id: 'knowledge',   label: '08 — Knowledge Base' },
];

const WORKSPACE_TYPES = [
  { id: 'hybrid', label: 'Hybrid', desc: 'Inbound + B2B intelligence (recommended)' },
  { id: 'b2b',    label: 'B2B',    desc: 'Outbound + insights engine only' },
  { id: 'b2c',    label: 'B2C',    desc: 'Inbound only — no insights engine' },
];

const TextInput = ({ label, value, onChange, placeholder, testid, multiline }) => {
  const Tag = multiline ? 'textarea' : 'input';
  return (
    <label className="block mb-4">
      <span className="text-sm font-medium text-slate-700 mb-1.5 block">{label}</span>
      <Tag
        data-testid={testid}
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        rows={multiline ? 3 : undefined}
        className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
      />
    </label>
  );
};

const ListInput = ({ label, items, onChange, placeholder, testid }) => {
  const [draft, setDraft] = useState('');
  const add = () => {
    const v = draft.trim();
    if (!v) return;
    onChange([...(items || []), v]);
    setDraft('');
  };
  const remove = (i) => onChange((items || []).filter((_, idx) => idx !== i));
  return (
    <div className="mb-5">
      <div className="text-sm font-medium text-slate-700 mb-1.5">{label}</div>
      <div className="flex gap-2 mb-2">
        <input
          data-testid={`${testid}-input`}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add(); } }}
          placeholder={placeholder}
          className="flex-1 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
        />
        <button
          data-testid={`${testid}-add`}
          onClick={add}
          className="px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white text-sm font-semibold rounded-lg"
        >Add</button>
      </div>
      {(items || []).length > 0 && (
        <ul className="space-y-1.5" data-testid={`${testid}-list`}>
          {(items || []).map((it, i) => (
            <li key={i} className="flex items-start justify-between gap-3 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm">
              <span className="flex-1">{it}</span>
              <button
                data-testid={`${testid}-remove-${i}`}
                onClick={() => remove(i)}
                className="text-rose-500 hover:text-rose-700 text-xs font-semibold"
              >Remove</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

const FaqEditor = ({ faq, onChange }) => {
  const add = () => onChange([...(faq || []), { question: '', answer: '' }]);
  const remove = (i) => onChange((faq || []).filter((_, idx) => idx !== i));
  const update = (i, patch) => onChange((faq || []).map((it, idx) => idx === i ? { ...it, ...patch } : it));
  return (
    <div className="mt-5">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-slate-700">Custom FAQ</span>
        <button data-testid="faq-add-btn" onClick={add} className="px-3 py-1.5 border border-slate-300 hover:bg-slate-100 text-xs font-semibold rounded-lg">+ Add Q&A</button>
      </div>
      {(faq || []).map((f, i) => (
        <div key={i} className="border border-slate-200 rounded-lg p-3 mb-2 bg-slate-50" data-testid={`faq-entry-${i}`}>
          <div className="flex justify-end mb-1">
            <button data-testid={`faq-remove-${i}`} onClick={() => remove(i)} className="text-rose-500 hover:text-rose-700 text-xs font-semibold">Remove</button>
          </div>
          <TextInput label="Question" value={f.question} onChange={(v) => update(i, { question: v })} placeholder="e.g. What's your refund policy?" testid={`faq-${i}-q`} />
          <TextInput label="Answer" value={f.answer} onChange={(v) => update(i, { answer: v })} placeholder="30 days, no questions asked." multiline testid={`faq-${i}-a`} />
        </div>
      ))}
    </div>
  );
};

const IcpEditor = ({ icps, onChange }) => {
  const emptyIcp = () => ({
    icp_name: '', target_industries: [], target_titles_or_roles: [],
    company_size: '', geography: '', budget_range: '',
    high_intent_signals: [], disqualification_signals: [], relevant_resources: [],
  });
  const addIcp = () => onChange([...(icps || []), emptyIcp()]);
  const removeIcp = (i) => onChange((icps || []).filter((_, idx) => idx !== i));
  const updateIcp = (i, patch) => onChange((icps || []).map((it, idx) => idx === i ? { ...it, ...patch } : it));
  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold text-slate-900">Ideal Customer Profiles</h2>
        <button data-testid="icp-add-btn" onClick={addIcp} className="px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white text-sm font-semibold rounded-lg">+ Add ICP</button>
      </div>
      {(icps || []).length === 0 && (
        <div className="text-sm text-slate-500 bg-slate-50 border border-slate-200 rounded-lg p-4">
          No ICPs yet. Add at least one so Aria knows who your ideal customer is.
        </div>
      )}
      <div className="space-y-4" data-testid="icp-list">
        {(icps || []).map((icp, i) => (
          <div key={i} className="border border-slate-200 rounded-lg p-5 bg-slate-50" data-testid={`icp-card-${i}`}>
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">ICP #{i + 1}</span>
              <button data-testid={`icp-remove-${i}`} onClick={() => removeIcp(i)} className="text-rose-500 hover:text-rose-700 text-xs font-semibold">Remove ICP</button>
            </div>
            <TextInput label="Name" value={icp.icp_name} onChange={(v) => updateIcp(i, { icp_name: v })} placeholder="CHRO at Mid-Market SaaS" testid={`icp-${i}-name`} />
            <ListInput label="Target industries" items={icp.target_industries} onChange={(v) => updateIcp(i, { target_industries: v })} placeholder="SaaS" testid={`icp-${i}-industries`} />
            <ListInput label="Target titles / roles" items={icp.target_titles_or_roles} onChange={(v) => updateIcp(i, { target_titles_or_roles: v })} placeholder="CHRO" testid={`icp-${i}-titles`} />
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <TextInput label="Company size" value={icp.company_size} onChange={(v) => updateIcp(i, { company_size: v })} placeholder="100-1000" testid={`icp-${i}-size`} />
              <TextInput label="Geography" value={icp.geography} onChange={(v) => updateIcp(i, { geography: v })} placeholder="USA, EU" testid={`icp-${i}-geo`} />
              <TextInput label="Budget range" value={icp.budget_range} onChange={(v) => updateIcp(i, { budget_range: v })} placeholder="$30k-150k/yr" testid={`icp-${i}-budget`} />
            </div>
            <ListInput label="High-intent signals" items={icp.high_intent_signals} onChange={(v) => updateIcp(i, { high_intent_signals: v })} placeholder="Recent funding" testid={`icp-${i}-intent`} />
            <ListInput label="Disqualification signals" items={icp.disqualification_signals} onChange={(v) => updateIcp(i, { disqualification_signals: v })} placeholder="<50 employees" testid={`icp-${i}-disqualify`} />
          </div>
        ))}
      </div>
    </div>
  );
};

const TrainAriaV2 = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [section, setSection] = useState('identity');
  const [workspaceType, setWorkspaceType] = useState('hybrid');
  const [profile, setProfile] = useState(null);
  const [version, setVersion] = useState(0);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewText, setPreviewText] = useState('');
  const [extracting, setExtracting] = useState(false);
  const [testMessages, setTestMessages] = useState([]);  // [{role, text}]
  const [testInput, setTestInput] = useState('');
  const [testSending, setTestSending] = useState(false);
  const fileRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/api/aria/training-profile');
      setProfile(data.data);
      setVersion(data.version || 0);
      setWorkspaceType(data.workspace_type || 'hybrid');
    } catch (e) {
      toast.error('Could not load training profile');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const update = (patch) => setProfile((p) => ({ ...p, ...patch }));

  const save = async () => {
    setSaving(true);
    try {
      const { data } = await api.put('/api/aria/training-profile', profile);
      setVersion(data.version);
      toast.success(`Saved — Aria prompt re-assembled (v${data.version}, ${data.prompt_length} chars)`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const setWorkspaceTypeRemote = async (wt) => {
    try {
      await api.put('/api/aria/workspace-type', { workspace_type: wt });
      setWorkspaceType(wt);
      toast.success(`Workspace type set to ${wt.toUpperCase()}`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not update workspace type');
    }
  };

  const openPreview = async () => {
    try {
      const { data } = await api.get('/api/aria/system-prompt-preview');
      setPreviewText(data.prompt || '');
      setPreviewOpen(true);
    } catch (e) {
      toast.error('Preview failed');
    }
  };

  const autoTrain = async () => {
    setSaving(true);
    try {
      const { data } = await api.post('/api/aria/training-profile/auto-train-from-workspace');
      if ((data.seeded || []).length === 0) {
        toast.info(data.message || 'Nothing new to seed.');
      } else {
        toast.success(`Seeded ${data.seeded.length} field(s) from existing data`);
        load();
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Auto-train failed');
    } finally {
      setSaving(false);
    }
  };

  const onFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setExtracting(true);
    const form = new FormData();
    form.append('file', file);
    try {
      const { data } = await api.post(
        '/api/aria/training-profile/extract-from-document', form,
        { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 120000 },
      );
      toast.success(`Extracted ${data.fields_extracted} fields · ${data.icps_extracted} ICP(s) · v${data.version}`);
      load();
    } catch (err) {
      const det = err?.response?.data?.detail;
      toast.error(typeof det === 'string' ? det : 'Extraction failed');
    } finally {
      setExtracting(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const sendTest = async () => {
    const msg = testInput.trim();
    if (!msg) return;
    setTestSending(true);
    const newHistory = [...testMessages, { role: 'user', text: msg }];
    setTestMessages(newHistory);
    setTestInput('');
    try {
      const { data } = await api.post('/api/aria/test-chat', {
        message: msg,
        history: testMessages,  // prior turns (without current msg)
      }, { timeout: 60000 });
      setTestMessages([...newHistory, { role: 'aria', text: data.message, action: data.action }]);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Aria did not respond');
    } finally {
      setTestSending(false);
    }
  };

  if (loading || !profile) {
    return <div className="p-8 text-slate-500 text-sm">Loading training profile…</div>;
  }

  return (
    <div className="max-w-6xl mx-auto p-6 lg:p-10" data-testid="train-aria-v2-page">
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between mb-8 gap-4">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 mb-2">Train Aria</h1>
          <p className="text-sm text-slate-600 max-w-2xl">
            Aria represents your business, your voice, your rules. Train her once
            here — every conversation, email, and signal will follow these
            instructions exactly.
          </p>
          <div className="mt-2 text-xs text-slate-500">
            Profile version <span className="font-semibold text-slate-700">v{version}</span>
            {version > 0 && ' · prompt assembled and active'}
          </div>
        </div>
        <div className="flex gap-2 flex-wrap">
          <button data-testid="train-aria-auto-train-btn" onClick={autoTrain} disabled={saving} className="px-4 py-2 border border-slate-300 hover:bg-slate-50 text-sm font-semibold rounded-lg disabled:opacity-50">Seed from existing</button>
          <button data-testid="train-aria-preview-btn" onClick={openPreview} className="px-4 py-2 border border-slate-300 hover:bg-slate-50 text-sm font-semibold rounded-lg">Preview Aria prompt</button>
          <button data-testid="train-aria-save-btn" onClick={save} disabled={saving} className="px-5 py-2 bg-violet-600 hover:bg-violet-700 text-white text-sm font-semibold rounded-lg disabled:opacity-50">{saving ? 'Saving…' : 'Save & re-assemble'}</button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-8">
        <div className="border border-slate-200 rounded-xl p-5 bg-white" data-testid="train-aria-workspace-type-card">
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Workspace type</div>
          <div className="flex gap-2 flex-wrap">
            {WORKSPACE_TYPES.map((wt) => {
              const active = workspaceType === wt.id;
              return (
                <button
                  key={wt.id}
                  data-testid={`workspace-type-${wt.id}`}
                  onClick={() => setWorkspaceTypeRemote(wt.id)}
                  className={`flex-1 min-w-[110px] border rounded-lg p-3 text-left transition-colors ${active ? 'border-violet-500 bg-violet-50' : 'border-slate-200 hover:bg-slate-50'}`}
                >
                  <div className={`text-sm font-bold ${active ? 'text-violet-700' : 'text-slate-700'}`}>{wt.label}</div>
                  <div className="text-xs text-slate-500 mt-0.5">{wt.desc}</div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="border border-slate-200 rounded-xl p-5 bg-white" data-testid="train-aria-doc-upload-card">
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Train from a document</div>
          <p className="text-sm text-slate-600 mb-3">
            Upload a GTM brief, pitch deck, or sales playbook (PDF, DOCX, TXT, XLSX).
            Aria extracts strictly — never invents content.
          </p>
          <input
            ref={fileRef}
            type="file"
            data-testid="train-aria-doc-input"
            onChange={onFile}
            accept=".pdf,.docx,.txt,.xlsx,.xls,.csv"
            disabled={extracting}
            className="block text-sm text-slate-600 file:mr-3 file:px-4 file:py-2 file:rounded-lg file:border-0 file:bg-violet-600 file:text-white file:text-xs file:font-semibold file:cursor-pointer hover:file:bg-violet-700 disabled:opacity-50"
          />
          {extracting && (
            <div className="mt-2 text-xs text-violet-600 font-medium">Aria is reading your document…</div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[220px_1fr] gap-6">
        <aside className="space-y-1" data-testid="train-aria-section-list">
          {SECTIONS.map((s) => (
            <button
              key={s.id}
              data-testid={`section-tab-${s.id}`}
              onClick={() => setSection(s.id)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm font-medium transition-colors ${section === s.id ? 'bg-violet-100 text-violet-700' : 'text-slate-700 hover:bg-slate-100'}`}
            >{s.label}</button>
          ))}
        </aside>

        <div className="border border-slate-200 rounded-xl p-6 bg-white" data-testid={`section-content-${section}`}>
          {section === 'identity' && (
            <div>
              <h2 className="text-lg font-bold text-slate-900 mb-4">Business Identity</h2>
              <TextInput label="What do you sell?" value={profile.what_you_sell} onChange={(v) => update({ what_you_sell: v })} placeholder="AI-powered HR automation platform" multiline testid="field-what-you-sell" />
              <TextInput label="Who do you sell to?" value={profile.who_you_sell_to} onChange={(v) => update({ who_you_sell_to: v })} placeholder="CHROs at mid-market SaaS companies" multiline testid="field-who-you-sell-to" />
              <TextInput label="Core problem you solve" value={profile.problem_you_solve} onChange={(v) => update({ problem_you_solve: v })} placeholder="Disengaged employees, slow HR ops" multiline testid="field-problem-you-solve" />
              <TextInput label="What makes you different?" value={profile.differentiator} onChange={(v) => update({ differentiator: v })} placeholder="Combines engagement + AI workflows" multiline testid="field-differentiator" />
              <ListInput label="Main services / products" items={profile.services_or_products} onChange={(v) => update({ services_or_products: v })} placeholder="Employee Pulse" testid="field-services" />
            </div>
          )}
          {section === 'icps' && <IcpEditor icps={profile.icp_profiles} onChange={(v) => update({ icp_profiles: v })} />}
          {section === 'qualify' && (
            <div>
              <h2 className="text-lg font-bold text-slate-900 mb-4">Qualification Logic</h2>
              <ListInput label="Questions Aria asks to qualify" items={profile.qualification_questions} onChange={(v) => update({ qualification_questions: v })} placeholder="How many employees do you have?" testid="field-qualification-questions" />
              <ListInput label="A lead is QUALIFIED when…" items={profile.qualified_criteria} onChange={(v) => update({ qualified_criteria: v })} placeholder="100+ employees AND CHRO title" testid="field-qualified-criteria" />
              <ListInput label="A lead is LOW-PRIORITY when…" items={profile.low_priority_criteria} onChange={(v) => update({ low_priority_criteria: v })} placeholder="<50 employees, no HR function" testid="field-low-priority-criteria" />
              <TextInput label="Book a call when…" value={profile.book_call_trigger} onChange={(v) => update({ book_call_trigger: v })} placeholder="Lead asks about pricing or requests a demo" multiline testid="field-book-call-trigger" />
              <TextInput label="Trigger an INSTINCT action when…" value={profile.instinct_trigger} onChange={(v) => update({ instinct_trigger: v })} placeholder="Lead engages with case study email twice" multiline testid="field-instinct-trigger" />
              <TextInput label="Trigger AUTOMATION when…" value={profile.automation_trigger} onChange={(v) => update({ automation_trigger: v })} placeholder="Lead replies with buying intent" multiline testid="field-automation-trigger" />
            </div>
          )}
          {section === 'voice' && (
            <div>
              <h2 className="text-lg font-bold text-slate-900 mb-4">Brand Voice</h2>
              <TextInput label="Voice style" value={profile.brand_voice_style} onChange={(v) => update({ brand_voice_style: v })} placeholder="Warm and consultative" testid="field-brand-voice-style" />
              <TextInput label="Custom tone instructions" value={profile.custom_tone_instructions} onChange={(v) => update({ custom_tone_instructions: v })} placeholder="Never use exclamation points." multiline testid="field-custom-tone" />
              <TextInput label="Founder sample message (Aria mirrors this tone)" value={profile.founder_sample_message} onChange={(v) => update({ founder_sample_message: v })} placeholder="Paste a real message you'd send…" multiline testid="field-founder-sample" />
            </div>
          )}
          {section === 'objections' && (
            <div>
              <h2 className="text-lg font-bold text-slate-900 mb-4">Objections + FAQ</h2>
              <ListInput label="Pricing objection responses" items={profile.pricing_objection_responses} onChange={(v) => update({ pricing_objection_responses: v })} placeholder="How to respond when leads push back on price" testid="field-pricing-responses" />
              <ListInput label="Timing objection responses" items={profile.timing_objection_responses} onChange={(v) => update({ timing_objection_responses: v })} placeholder="How to respond when leads delay" testid="field-timing-responses" />
              <ListInput label="Trust concern responses" items={profile.trust_objection_responses} onChange={(v) => update({ trust_objection_responses: v })} placeholder="How to respond to credibility doubts" testid="field-trust-responses" />
              <ListInput label="Competitor comparison responses" items={profile.competitor_responses} onChange={(v) => update({ competitor_responses: v })} placeholder="How to position vs alternatives" testid="field-competitor-responses" />
              <FaqEditor faq={profile.custom_faq} onChange={(v) => update({ custom_faq: v })} />
            </div>
          )}
          {section === 'booking' && (
            <div>
              <h2 className="text-lg font-bold text-slate-900 mb-4">Booking Rules</h2>
              <TextInput label="Calendar link" value={profile.calendar_link} onChange={(v) => update({ calendar_link: v })} placeholder="https://calendly.com/your-handle" testid="field-calendar-link" />
              <TextInput label="Booking criteria" value={profile.booking_criteria} onChange={(v) => update({ booking_criteria: v })} placeholder="Lead is QUALIFIED AND budget confirmed" multiline testid="field-booking-criteria" />
              <ListInput label="Pre-call questions" items={profile.pre_call_questions} onChange={(v) => update({ pre_call_questions: v })} placeholder="Questions Aria asks before confirming" testid="field-pre-call-questions" />
              <TextInput label="Reminder timing" value={profile.reminder_timing} onChange={(v) => update({ reminder_timing: v })} placeholder="24h and 1h before the call" testid="field-reminder-timing" />
              <TextInput label="No-show recovery message" value={profile.no_show_message} onChange={(v) => update({ no_show_message: v })} placeholder="Message Aria sends if lead doesn't show" multiline testid="field-no-show-message" />
            </div>
          )}
          {section === 'insights' && (
            <div>
              <h2 className="text-lg font-bold text-slate-900 mb-4">Insights Engine</h2>
              {workspaceType === 'b2c' ? (
                <div className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-4">
                  Insights Engine is disabled for <strong>B2C</strong> workspaces. Switch to <strong>B2B</strong> or <strong>Hybrid</strong> above to configure.
                </div>
              ) : (
                <>
                  <ListInput label="Auto-instinct signals (no approval needed)" items={profile.auto_signal_actions} onChange={(v) => update({ auto_signal_actions: v })} placeholder="funding_round, event_attending" testid="field-auto-signals" />
                  <ListInput label="Approval-required signals" items={profile.approval_required_signals} onChange={(v) => update({ approval_required_signals: v })} placeholder="deal_closed, job_change" testid="field-approval-signals" />
                  <label className="flex items-center gap-2 mb-3 text-sm">
                    <input type="checkbox" data-testid="field-email-insights-enabled" checked={!!profile.email_insights_enabled} onChange={(e) => update({ email_insights_enabled: e.target.checked })} className="rounded border-slate-300" />
                    Send a daily email digest
                  </label>
                  <label className="flex items-center gap-2 mb-3 text-sm">
                    <input type="checkbox" data-testid="field-whatsapp-insights-enabled" checked={!!profile.whatsapp_insights_enabled} onChange={(e) => update({ whatsapp_insights_enabled: e.target.checked })} className="rounded border-slate-300" />
                    WhatsApp alert for ≥ 0.85 confidence signals
                  </label>
                  <div className="grid grid-cols-2 gap-3 mt-3">
                    <TextInput label="Digest time" value={profile.digest_time} onChange={(v) => update({ digest_time: v })} placeholder="08:00" testid="field-digest-time" />
                    <TextInput label="Digest timezone" value={profile.digest_timezone} onChange={(v) => update({ digest_timezone: v })} placeholder="Asia/Kolkata" testid="field-digest-tz" />
                  </div>
                </>
              )}
            </div>
          )}
          {section === 'knowledge' && (
            <div>
              <h2 className="text-lg font-bold text-slate-900 mb-4">Knowledge Base</h2>
              <p className="text-sm text-slate-600 mb-4">
                FAQ, product details, or context not covered elsewhere. Aria quotes
                from this when leads ask out-of-scope questions. One chunk per topic.
              </p>
              <ListInput label="Knowledge base chunks" items={profile.knowledge_base_chunks} onChange={(v) => update({ knowledge_base_chunks: v })} placeholder="Pietential was founded in 2024 by Megha. SOC2-compliant." testid="field-kb-chunks" />
            </div>
          )}
        </div>
      </div>

      {previewOpen && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" data-testid="preview-modal">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-4xl max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between p-5 border-b border-slate-200">
              <div>
                <h3 className="text-lg font-bold text-slate-900">Assembled Aria Prompt</h3>
                <div className="text-xs text-slate-500 mt-0.5">
                  {previewText.length.toLocaleString()} chars · v{version}
                </div>
              </div>
              <button data-testid="preview-close" onClick={() => setPreviewOpen(false)} className="text-slate-500 hover:text-slate-900 text-2xl leading-none">×</button>
            </div>
            <pre className="flex-1 overflow-auto p-5 text-xs text-slate-700 font-mono whitespace-pre-wrap">
              {previewText}
            </pre>
          </div>
        </div>
      )}

      {/* Test Aria chat panel — floating widget bottom-right */}
      <TestAriaPanel
        messages={testMessages}
        input={testInput}
        onInput={setTestInput}
        onSend={sendTest}
        sending={testSending}
        onClear={() => setTestMessages([])}
      />
    </div>
  );
};

// ─── Test Aria chat panel — floating widget ──────────────────────────────
const TestAriaPanel = ({ messages, input, onInput, onSend, sending, onClear }) => {
  const [open, setOpen] = useState(false);
  if (!open) {
    return (
      <button
        data-testid="test-aria-open-btn"
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-40 px-5 py-3 bg-slate-900 hover:bg-slate-800 text-white text-sm font-semibold rounded-full shadow-lg flex items-center gap-2"
      >
        <span className="text-base">💬</span> Test Aria
      </button>
    );
  }
  return (
    <div className="fixed bottom-6 right-6 z-40 w-[420px] max-w-[calc(100vw-3rem)] h-[560px] max-h-[80vh] bg-white border border-slate-200 rounded-2xl shadow-2xl flex flex-col" data-testid="test-aria-panel">
      <div className="flex items-center justify-between p-4 border-b border-slate-200">
        <div>
          <div className="text-sm font-bold text-slate-900">Test Aria</div>
          <div className="text-xs text-slate-500">Live response using your trained prompt</div>
        </div>
        <div className="flex items-center gap-2">
          <button data-testid="test-aria-clear-btn" onClick={onClear} className="text-xs text-slate-500 hover:text-slate-900">Clear</button>
          <button data-testid="test-aria-close-btn" onClick={() => setOpen(false)} className="text-slate-500 hover:text-slate-900 text-2xl leading-none">×</button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-3" data-testid="test-aria-messages">
        {messages.length === 0 && (
          <div className="text-xs text-slate-400 text-center pt-12">
            Paste a sample prospect message below to see how trained Aria responds.
          </div>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            data-testid={`test-msg-${i}-${m.role}`}
            className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm ${
              m.role === 'user'
                ? 'ml-auto bg-violet-600 text-white'
                : 'mr-auto bg-slate-100 text-slate-800'
            }`}
          >
            <div className="whitespace-pre-wrap">{m.text}</div>
            {m.role === 'aria' && m.action && m.action !== 'NONE' && (
              <div className="mt-1.5 text-[10px] uppercase tracking-wide font-semibold text-violet-600">
                action: {m.action}
              </div>
            )}
          </div>
        ))}
        {sending && (
          <div className="mr-auto bg-slate-100 text-slate-500 rounded-2xl px-3 py-2 text-sm">Aria is thinking…</div>
        )}
      </div>
      <div className="p-3 border-t border-slate-200 flex gap-2">
        <input
          data-testid="test-aria-input"
          value={input}
          onChange={(e) => onInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSend(); } }}
          placeholder="Hi, I'm the CHRO at a 400-person SaaS…"
          disabled={sending}
          className="flex-1 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500 disabled:bg-slate-50"
        />
        <button
          data-testid="test-aria-send-btn"
          onClick={onSend}
          disabled={sending || !input.trim()}
          className="px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white text-sm font-semibold rounded-lg disabled:opacity-50"
        >Send</button>
      </div>
    </div>
  );
};

export default TrainAriaV2;
