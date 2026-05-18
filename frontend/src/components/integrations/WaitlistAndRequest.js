import React, { useState } from 'react';
import { toast } from 'sonner';
import { X, BellRinging, Sparkle, ArrowRight, CheckCircle } from '@phosphor-icons/react';
import api from '../../config/api';

/** Modal for "Join Waitlist" on a coming-soon integration. */
export function WaitlistModal({ integration, onClose, onJoined }) {
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [joined, setJoined] = useState(false);

  const join = async () => {
    setBusy(true);
    try {
      const r = await api.post(`/api/integrations/waitlist/${integration.type}`, { note });
      setJoined(true);
      toast.success(`On the waitlist for ${integration.label}. We'll email you when it ships.`);
      onJoined?.(r.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not join waitlist');
    } finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4" data-testid="waitlist-modal">
      <div className="bg-white border border-[#E8E0F5] rounded-2xl w-full max-w-md overflow-hidden">
        <div className="flex items-start justify-between p-5 border-b border-[#E8E0F5]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-violet-50 text-violet-600 flex items-center justify-center">
              <Sparkle size={18} weight="duotone" />
            </div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-violet-600">Coming soon</div>
              <h3 className="text-lg font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{integration.label}</h3>
            </div>
          </div>
          <button onClick={onClose} data-testid="waitlist-modal-close" className="text-[#9B8AB0] hover:text-[#1A0A2E]"><X size={20} /></button>
        </div>

        {joined ? (
          <div className="p-6 text-center" data-testid="waitlist-joined">
            <CheckCircle size={42} weight="duotone" className="text-emerald-500 mx-auto mb-3" />
            <h4 className="text-base font-extrabold text-[#1A0A2E] mb-1">You're on the list.</h4>
            <p className="text-xs text-[#5A4A7A]">We'll email you the moment {integration.label} goes live. Demand also bumps it up our build queue.</p>
            <button onClick={onClose} className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-slate-900 text-white text-xs font-bold uppercase tracking-wider">
              Got it
            </button>
          </div>
        ) : (
          <div className="p-5 space-y-3">
            <p className="text-xs text-[#5A4A7A] leading-relaxed">
              <BellRinging size={12} weight="duotone" className="inline -mt-0.5 mr-1 text-violet-500" />
              Tell us what you'd use it for. We prioritise integrations by user demand and use-case clarity.
            </p>
            <label className="block">
              <span className="block text-[10px] uppercase tracking-wider font-bold text-slate-500 mb-1">What would you use it for? (optional)</span>
              <textarea
                data-testid="waitlist-note"
                rows={3}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-sm placeholder-slate-400 focus:outline-none focus:border-violet-500 focus:ring-2 focus:ring-violet-100"
                placeholder={`e.g. We run all ICP scoring inside ${integration.label} — would love auto-sync of qualified leads.`}
              />
            </label>
            <div className="flex justify-end gap-2 pt-1">
              <button onClick={onClose} className="px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-700 text-xs font-bold uppercase tracking-wider hover:bg-slate-50">Cancel</button>
              <button
                data-testid="waitlist-join-btn"
                onClick={join}
                disabled={busy}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-violet-600 text-white text-xs font-bold uppercase tracking-wider hover:bg-violet-700 disabled:opacity-50"
              >
                {busy ? 'Joining…' : <>Join waitlist <ArrowRight size={11} weight="bold" /></>}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}


/** Inline custom-integration request form (lives at the bottom of the hub). */
export function CustomRequestForm() {
  const [form, setForm] = useState({
    tool_name: '', website_url: '', use_case: '',
    data_to_pull: '', data_to_push: '', priority: 'nice_to_have',
  });
  const [busy, setBusy] = useState(false);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async () => {
    if (form.tool_name.trim().length < 2) return toast.error('Add a tool name');
    if (form.use_case.trim().length < 10) return toast.error('Add a one-line use case');
    setBusy(true);
    try {
      await api.post('/api/integrations/custom-request', form);
      toast.success('Request received. We\'ll review and reach out within 48 hours.');
      setForm({ tool_name: '', website_url: '', use_case: '', data_to_pull: '', data_to_push: '', priority: 'nice_to_have' });
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not submit request');
    } finally { setBusy(false); }
  };

  return (
    <section
      data-testid="custom-request-form"
      className="bg-white border border-[#E8E0F5] rounded-2xl p-6"
      style={{ boxShadow: 'var(--shadow-card)' }}
    >
      <div className="flex items-start gap-3 mb-4">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-500 text-white flex items-center justify-center">
          <Sparkle size={18} weight="duotone" />
        </div>
        <div>
          <h3 className="text-lg font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Need a tool we don't support yet?</h3>
          <p className="text-xs text-[#5A4A7A] mt-0.5">Tell us what you want to connect. Aria can support custom APIs, webhooks, Zapier, Make, and n8n workflows.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Field label="Tool name *">
          <input data-testid="cr-tool-name" value={form.tool_name} onChange={set('tool_name')} className={inputCls} placeholder="e.g. Close.com" />
        </Field>
        <Field label="Website URL">
          <input data-testid="cr-website" value={form.website_url} onChange={set('website_url')} className={inputCls} placeholder="https://close.com" />
        </Field>
        <Field label="Use case *" wide>
          <textarea data-testid="cr-use-case" value={form.use_case} onChange={set('use_case')} rows={2} className={inputCls} placeholder="Why this integration matters for your sales workflow." />
        </Field>
        <Field label="Data to pull from the tool">
          <input data-testid="cr-data-pull" value={form.data_to_pull} onChange={set('data_to_pull')} className={inputCls} placeholder="e.g. deal stage changes, replies" />
        </Field>
        <Field label="Data to push to the tool">
          <input data-testid="cr-data-push" value={form.data_to_push} onChange={set('data_to_push')} className={inputCls} placeholder="e.g. qualified leads with Aria score" />
        </Field>
        <Field label="Priority">
          <select data-testid="cr-priority" value={form.priority} onChange={set('priority')} className={inputCls}>
            <option value="blocker">Blocker — we can't launch without it</option>
            <option value="nice_to_have">Nice to have — would improve our flow</option>
          </select>
        </Field>
      </div>

      <div className="flex justify-end mt-4">
        <button
          data-testid="cr-submit-btn"
          onClick={submit}
          disabled={busy}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-900 text-white text-xs font-bold uppercase tracking-wider hover:bg-slate-800 disabled:opacity-50"
        >
          {busy ? 'Submitting…' : <>Request integration <ArrowRight size={11} weight="bold" /></>}
        </button>
      </div>
    </section>
  );
}

const inputCls = "w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-sm text-slate-900 focus:outline-none focus:border-violet-500 focus:ring-2 focus:ring-violet-100 placeholder-slate-400";

function Field({ label, wide, children }) {
  return (
    <label className={`block ${wide ? 'md:col-span-2' : ''}`}>
      <span className="block text-[10px] uppercase tracking-wider font-bold text-slate-500 mb-1">{label}</span>
      {children}
    </label>
  );
}
