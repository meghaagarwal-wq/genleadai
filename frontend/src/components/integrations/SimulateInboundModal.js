/**
 * SimulateInboundModal — the "see Aria work" demo.
 *
 * Opens from the Integration Hub. Lets the user pick a source, tweak a lead's
 * fields, and walks them through the 5-step intelligence loop with animated
 * step reveals (captured → enriched → scored → channel → message drafted).
 *
 * The lead is NEVER persisted — it's a pure walkthrough.
 */
import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import {
  X, MagicWand, Sparkle, CheckCircle, ArrowRight, Lightning, ChartLineUp,
  ChatTeardropDots, Envelope, LinkedinLogo, ChatCircle, Phone, DeviceMobile,
  Buildings, Globe, Target, ListChecks, Eye,
} from '@phosphor-icons/react';
import api from '../../config/api';

const CHANNEL_ICON = {
  whatsapp: ChatTeardropDots,
  email: Envelope,
  linkedin: LinkedinLogo,
  sms: DeviceMobile,
  phone: Phone,
  website_chat: ChatCircle,
};

const STEP_ICONS = {
  captured: ListChecks,
  enriched: Buildings,
  icp_scored: ChartLineUp,
  channel_chosen: Target,
  message_drafted: Sparkle,
};

const TIER_STYLE = {
  hot:      { bg: 'bg-rose-50',    text: 'text-rose-700',    border: 'border-rose-200',    label: 'Hot' },
  warm:     { bg: 'bg-amber-50',   text: 'text-amber-800',   border: 'border-amber-200',   label: 'Warm' },
  cold:     { bg: 'bg-sky-50',     text: 'text-sky-700',     border: 'border-sky-200',     label: 'Cold' },
  poor_fit: { bg: 'bg-slate-100',  text: 'text-slate-700',   border: 'border-slate-200',   label: 'Poor fit' },
};

export default function SimulateInboundModal({ onClose }) {
  const [meta, setMeta] = useState({ sources: [], channels: [] });
  const [form, setForm] = useState({
    source: 'meta_lead_ad',
    first_name: 'Priya',
    last_name: 'Mehta',
    email: 'priya@acme.com',
    phone: '+919876500001',
    company: 'Acme Co',
    utm_campaign: 'demo-request-q1-2026',
    form_answers: 'Looking for an AI sales PA for our 20-person SaaS team. Budget approved.',
  });
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [revealedUpTo, setRevealedUpTo] = useState(0);

  useEffect(() => {
    api.get('/api/integrations/simulate-inbound/sources').then((r) => setMeta(r.data)).catch(() => {});
  }, []);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const run = async () => {
    setRunning(true); setResult(null); setRevealedUpTo(0);
    try {
      const r = await api.post('/api/integrations/simulate-inbound', form);
      setResult(r.data);
      // Animate step reveal — 1 step every 380ms
      const total = r.data.steps?.length || 0;
      for (let i = 1; i <= total; i++) {
        // eslint-disable-next-line no-loop-func
        setTimeout(() => setRevealedUpTo(i), i * 380);
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Simulation failed');
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4" data-testid="simulate-inbound-modal">
      <div className="bg-white border border-[#E8E0F5] rounded-2xl w-full max-w-4xl max-h-[92vh] overflow-hidden flex flex-col">
        <div className="flex items-start justify-between p-5 border-b border-[#E8E0F5]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-500 text-white flex items-center justify-center">
              <MagicWand size={18} weight="duotone" />
            </div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-violet-600">See Aria work</div>
              <h3 className="text-lg font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Simulate an inbound lead</h3>
              <p className="text-[11px] text-[#5A4A7A] mt-0.5">Walk a hypothetical lead through Aria's intelligence layer — capture → enrich → score → channel → draft. Nothing is saved to your inbox.</p>
            </div>
          </div>
          <button onClick={onClose} data-testid="sim-modal-close" className="text-[#9B8AB0] hover:text-[#1A0A2E]"><X size={20} /></button>
        </div>

        <div className="flex-1 overflow-y-auto">
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-0">
            {/* LEFT — form */}
            <div className="lg:col-span-2 p-5 border-r border-[#F0ECF9] space-y-3 bg-slate-50/40" data-testid="sim-form">
              <Field label="Source">
                <select data-testid="sim-source" value={form.source} onChange={set('source')} className={inputCls}>
                  {(meta.sources || []).map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
                </select>
              </Field>
              <div className="grid grid-cols-2 gap-2">
                <Field label="First name">
                  <input data-testid="sim-first-name" value={form.first_name} onChange={set('first_name')} className={inputCls} />
                </Field>
                <Field label="Last name">
                  <input data-testid="sim-last-name" value={form.last_name} onChange={set('last_name')} className={inputCls} />
                </Field>
              </div>
              <Field label="Email">
                <input data-testid="sim-email" value={form.email} onChange={set('email')} className={inputCls} />
              </Field>
              <div className="grid grid-cols-2 gap-2">
                <Field label="Phone">
                  <input data-testid="sim-phone" value={form.phone || ''} onChange={set('phone')} className={inputCls} />
                </Field>
                <Field label="Company">
                  <input data-testid="sim-company" value={form.company || ''} onChange={set('company')} className={inputCls} />
                </Field>
              </div>
              <Field label="UTM campaign">
                <input data-testid="sim-utm" value={form.utm_campaign || ''} onChange={set('utm_campaign')} className={`${inputCls} font-mono text-[11px]`} />
              </Field>
              <Field label="Form answers / qualification text">
                <textarea data-testid="sim-answers" rows={3} value={form.form_answers || ''} onChange={set('form_answers')} className={inputCls} />
              </Field>
              <button
                onClick={run}
                disabled={running}
                data-testid="sim-run-btn"
                className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-violet-600 text-white text-xs font-bold uppercase tracking-wider hover:bg-violet-700 disabled:opacity-50 transition-all"
              >
                <Lightning size={14} weight="fill" />
                {running ? 'Running Aria…' : result ? 'Run again' : 'Simulate the journey'}
              </button>
              <p className="text-[10px] text-slate-500 text-center mt-1 flex items-center justify-center gap-1">
                <Eye size={10} weight="duotone" /> Lead is NEVER saved — pure walkthrough.
              </p>
            </div>

            {/* RIGHT — animated step output */}
            <div className="lg:col-span-3 p-5" data-testid="sim-output">
              {!result && !running && (
                <EmptyState />
              )}
              {running && !result && (
                <div className="flex flex-col items-center justify-center h-full min-h-[300px] text-slate-400">
                  <div className="w-10 h-10 border-4 border-violet-200 border-t-violet-600 rounded-full animate-spin mb-3"></div>
                  <p className="text-sm font-bold text-slate-600">Aria is reading the lead…</p>
                  <p className="text-[11px] text-slate-400 mt-1">Capturing → enriching → scoring → choosing channel → drafting</p>
                </div>
              )}
              {result && (
                <div className="space-y-3" data-testid="sim-steps">
                  {result.steps.map((step, idx) => (
                    <StepCard key={step.key} step={step} idx={idx} revealed={revealedUpTo > idx} />
                  ))}
                  {revealedUpTo >= result.steps.length && (
                    <div className="mt-2 p-3 rounded-xl border border-emerald-200 bg-emerald-50 flex items-start gap-2" data-testid="sim-complete-banner">
                      <CheckCircle size={16} weight="fill" className="text-emerald-600 mt-0.5" />
                      <div>
                        <div className="text-xs font-extrabold text-emerald-700">That's Aria, end-to-end.</div>
                        <div className="text-[11px] text-emerald-700/80 mt-0.5">When a real lead hits any connected source, this exact loop runs in &lt; 60 seconds.</div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StepCard({ step, idx, revealed }) {
  const Icon = STEP_ICONS[step.key] || Sparkle;
  // ICP-tier styling for the scored step
  const tier = step.key === 'icp_scored' ? step.detail?.tier : null;
  const tierStyle = tier ? TIER_STYLE[tier] : null;
  const channel = step.key === 'channel_chosen' ? step.detail?.primary_channel : null;
  const ChannelIcon = channel ? CHANNEL_ICON[channel] : null;
  const isMessage = step.key === 'message_drafted';

  return (
    <div
      data-testid={`sim-step-${step.key}`}
      className={`relative pl-9 transition-all duration-500 ${revealed ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'}`}
    >
      {/* vertical timeline rail */}
      <div className="absolute left-3 top-3 bottom-[-12px] w-px bg-violet-200" aria-hidden="true" />
      <div className={`absolute left-0 top-0 w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-extrabold ${revealed ? 'bg-violet-500 text-white' : 'bg-slate-200 text-slate-500'}`}>
        {idx + 1}
      </div>

      <div className="p-3 rounded-xl border border-[#E8E0F5] bg-white" style={{ boxShadow: 'var(--shadow-card)' }}>
        <div className="flex items-start gap-2 mb-1.5">
          <Icon size={14} weight="duotone" className="text-violet-600 mt-0.5 shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="text-xs font-extrabold text-slate-900">{step.title}</div>
            <div className="text-[11px] text-slate-600 mt-0.5">{step.summary}</div>
          </div>
        </div>

        {/* Step-specific detail */}
        {step.key === 'icp_scored' && step.detail && (
          <div className="mt-2 space-y-1.5">
            <div className="flex items-center gap-2">
              <div className={`px-2 py-0.5 rounded text-[10px] font-extrabold uppercase tracking-wider border ${tierStyle.bg} ${tierStyle.text} ${tierStyle.border}`}>
                {tierStyle.label} · {step.detail.score}/100
              </div>
            </div>
            <ul className="space-y-0.5">
              {(step.detail.reasons || []).map((r, k) => (
                <li key={k} className="text-[11px] text-slate-700 pl-3 relative">
                  <span className="absolute left-0 top-1.5 w-1 h-1 rounded-full bg-violet-400"></span>
                  {r}
                </li>
              ))}
            </ul>
          </div>
        )}

        {step.key === 'channel_chosen' && channel && (
          <div className="mt-2 flex items-center gap-2 p-2 rounded-lg bg-violet-50 border border-violet-100">
            {ChannelIcon && <ChannelIcon size={14} weight="duotone" className="text-violet-600" />}
            <div className="text-[11px] text-slate-800 font-bold">{step.detail.primary_channel.toUpperCase()}</div>
            {step.detail.priority_order?.length > 0 && (
              <div className="text-[10px] text-slate-500">Fallback: {step.detail.priority_order.slice(1).join(' → ') || 'none'}</div>
            )}
          </div>
        )}

        {isMessage && step.detail && (
          <div className="mt-2 p-3 rounded-lg bg-gradient-to-br from-violet-50 to-fuchsia-50 border border-violet-200">
            <div className="text-[9px] uppercase tracking-wider font-extrabold text-violet-700 mb-1 flex items-center gap-1">
              First-touch message
              {step.detail.ai_powered && (
                <span className="text-[8px] font-extrabold uppercase tracking-wider px-1.5 py-0.5 rounded bg-violet-600 text-white">AI</span>
              )}
            </div>
            <p className="text-xs text-slate-900 whitespace-pre-wrap leading-relaxed">{step.detail.rendered_message}</p>
          </div>
        )}

        {step.key === 'captured' && step.detail?.form_answers && (
          <div className="mt-2 p-2 rounded-lg bg-slate-50 border border-slate-200">
            <div className="text-[9px] uppercase tracking-wider font-extrabold text-slate-500 mb-0.5">Form answers</div>
            <div className="text-[11px] text-slate-700 italic">"{step.detail.form_answers}"</div>
          </div>
        )}
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[300px] text-center px-6">
      <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-violet-100 to-fuchsia-100 text-violet-600 flex items-center justify-center mb-3">
        <MagicWand size={22} weight="duotone" />
      </div>
      <h4 className="text-sm font-extrabold text-slate-900" style={{ fontFamily: 'Plus Jakarta Sans' }}>Press "Simulate the journey"</h4>
      <p className="text-[11px] text-slate-600 max-w-sm mt-1 leading-relaxed">
        Aria will read this lead's signals, score their intent, pick the best follow-up channel based on your saved preferences, and draft the first-touch message — all in under 60 seconds.
      </p>
    </div>
  );
}

const inputCls = "w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-sm text-slate-900 focus:outline-none focus:border-violet-500 focus:ring-2 focus:ring-violet-100 placeholder-slate-400";

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="block text-[10px] uppercase tracking-wider font-bold text-slate-500 mb-1">{label}</span>
      {children}
    </label>
  );
}
