import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Receipt, FloppyDisk, ShieldCheck, Warning, XCircle, CheckCircle, ArrowsClockwise } from '@phosphor-icons/react';
import api from '../../config/api';

/**
 * Master Admin → Billing config (Iter 58)
 *
 * Two stacked panels:
 *   1. Seller GST profile  — DB-stored overrides for invoice header (name, GSTIN, address,
 *      state, billing email), plus founder notify email + Slack webhook.
 *   2. Production-readiness panel — green/yellow/red lights for the things you have to
 *      flip before launch (Resend domain, Stripe live key, GSTIN, founder email, Slack).
 */
export default function BillingConfigTab() {
  const [profile, setProfile] = useState(null);
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [readiness, setReadiness] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const loadReadiness = async () => {
    setRefreshing(true);
    try {
      const r = await api.get('/api/admin/production-readiness');
      setReadiness(r.data);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    api.get('/api/admin/seller-profile')
      .then((r) => { setProfile(r.data); setForm(r.data); })
      .catch(() => toast.error('Could not load seller profile'));
    loadReadiness();
  }, []);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const save = async () => {
    setSaving(true);
    try {
      const r = await api.put('/api/admin/seller-profile', form);
      setProfile(r.data.profile);
      setForm(r.data.profile);
      toast.success('Seller profile saved. Future invoices will use this info.');
      loadReadiness();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not save');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6" data-testid="billing-config-tab">
      {/* Production-readiness */}
      <section className="bg-white border border-[#E8E0F5] rounded-2xl p-5" style={{ boxShadow: 'var(--shadow-card)' }}>
        <div className="flex items-start justify-between gap-3 mb-4">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <ShieldCheck size={18} weight="duotone" />
            </div>
            <div>
              <h3 className="text-base font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Production readiness</h3>
              <p className="text-xs text-[#5A4A7A] mt-0.5">Flip these to green before flipping the “live” switch.</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {readiness && <OverallPill status={readiness.overall} />}
            <button
              data-testid="readiness-refresh"
              onClick={loadReadiness}
              disabled={refreshing}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 text-[11px] font-semibold uppercase tracking-wider disabled:opacity-50"
            >
              <ArrowsClockwise size={12} weight="bold" className={refreshing ? 'animate-spin' : ''} /> Refresh
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-2" data-testid="readiness-checks">
          {(readiness?.checks || []).map((c) => (
            <ReadinessRow key={c.key} check={c} />
          ))}
          {!readiness && <div className="text-slate-400 text-xs py-3">Loading readiness…</div>}
        </div>
      </section>

      {/* Seller profile form */}
      <section className="bg-white border border-[#E8E0F5] rounded-2xl p-5" style={{ boxShadow: 'var(--shadow-card)' }}>
        <div className="flex items-start gap-3 mb-4">
          <div className="w-9 h-9 rounded-xl bg-violet-50 text-violet-600 flex items-center justify-center">
            <Receipt size={18} weight="duotone" />
          </div>
          <div>
            <h3 className="text-base font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Seller GST profile</h3>
            <p className="text-xs text-[#5A4A7A] mt-0.5">
              Goes on every invoice header. DB-stored so you can fill your GSTIN without a redeploy.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Field label="Seller legal name">
            <input data-testid="seller-name" value={form.seller_name || ''} onChange={set('seller_name')} className={inputCls} />
          </Field>
          <Field label="Seller GSTIN">
            <input data-testid="seller-gstin" value={form.seller_gstin || ''} onChange={set('seller_gstin')} className={`${inputCls} font-mono`} placeholder="29ABCDE1234F1Z5" maxLength={15} />
          </Field>
          <Field label="State">
            <input data-testid="seller-state" value={form.seller_state || ''} onChange={set('seller_state')} className={inputCls} />
          </Field>
          <Field label="State code">
            <input data-testid="seller-state-code" value={form.seller_state_code || ''} onChange={set('seller_state_code')} className={`${inputCls} font-mono`} maxLength={2} />
          </Field>
          <Field label="Billing email (reply-to on invoices)">
            <input data-testid="seller-email" type="email" value={form.seller_email || ''} onChange={set('seller_email')} className={inputCls} />
          </Field>
          <Field label="Founder upgrade notification email">
            <input data-testid="founder-notify-email" type="email" value={form.founder_notify_email || ''} onChange={set('founder_notify_email')} className={inputCls} placeholder="you@yourdomain.com" />
          </Field>
          <Field label="Seller address" wide>
            <textarea data-testid="seller-address" value={form.seller_address || ''} onChange={set('seller_address')} rows={2} className={inputCls} />
          </Field>
          <Field label="Slack incoming webhook (optional)" wide>
            <input
              data-testid="slack-webhook"
              value={form.slack_webhook_url || ''}
              onChange={set('slack_webhook_url')}
              className={`${inputCls} font-mono text-[11px]`}
              placeholder="https://hooks.slack.com/services/T.../B.../..."
            />
            <span className="text-[11px] text-slate-500 mt-1 block">
              Optional. Get a real-time ping in #revenue every time someone upgrades.
            </span>
          </Field>
        </div>

        <div className="flex justify-end mt-4">
          <button
            data-testid="seller-save-btn"
            onClick={save}
            disabled={saving}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-900 text-white text-xs font-bold uppercase tracking-wider hover:bg-slate-800 disabled:opacity-50"
          >
            <FloppyDisk size={14} weight="bold" /> {saving ? 'Saving…' : 'Save seller profile'}
          </button>
        </div>
      </section>
    </div>
  );
}

function ReadinessRow({ check }) {
  const { Icon, bg, fg, ring } = pillForStatus(check.status);
  return (
    <div
      data-testid={`readiness-${check.key}`}
      className={`flex items-start gap-3 p-3 rounded-xl border ${ring} bg-white`}
    >
      <div className={`shrink-0 w-8 h-8 rounded-lg ${bg} ${fg} flex items-center justify-center`}>
        <Icon size={16} weight="bold" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold text-slate-900">{check.label}</span>
          <StatusBadge status={check.status} />
        </div>
        <p className="text-xs text-slate-600 mt-0.5">{check.detail}</p>
      </div>
    </div>
  );
}

function StatusBadge({ status }) {
  const map = {
    green: { label: 'Ready', cls: 'bg-emerald-100 text-emerald-700 border-emerald-200' },
    yellow: { label: 'Action needed', cls: 'bg-amber-100 text-amber-800 border-amber-200' },
    red: { label: 'Blocking', cls: 'bg-rose-100 text-rose-700 border-rose-200' },
  };
  const m = map[status] || map.yellow;
  return <span className={`text-[10px] font-extrabold uppercase tracking-wider px-2 py-0.5 rounded-full border ${m.cls}`}>{m.label}</span>;
}

function OverallPill({ status }) {
  const m = {
    green: { label: 'Production ready', cls: 'bg-emerald-100 text-emerald-700 border-emerald-200' },
    yellow: { label: 'Almost there', cls: 'bg-amber-100 text-amber-800 border-amber-200' },
    red: { label: 'Not ready', cls: 'bg-rose-100 text-rose-700 border-rose-200' },
  }[status] || { label: '—', cls: 'bg-slate-100 text-slate-700' };
  return <span data-testid="readiness-overall" className={`text-[11px] font-extrabold uppercase tracking-wider px-2.5 py-1 rounded-full border ${m.cls}`}>{m.label}</span>;
}

function pillForStatus(status) {
  if (status === 'green') return { Icon: CheckCircle, bg: 'bg-emerald-50', fg: 'text-emerald-600', ring: 'border-emerald-100' };
  if (status === 'red') return { Icon: XCircle, bg: 'bg-rose-50', fg: 'text-rose-600', ring: 'border-rose-100' };
  return { Icon: Warning, bg: 'bg-amber-50', fg: 'text-amber-600', ring: 'border-amber-100' };
}

const inputCls = "w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-sm text-slate-900 focus:outline-none focus:border-violet-500 focus:ring-2 focus:ring-violet-100 placeholder-slate-400";

function Field({ label, wide, children }) {
  return (
    <label className={`block ${wide ? 'md:col-span-2' : ''}`}>
      <span className="block text-[11px] uppercase tracking-wider font-bold text-slate-500 mb-1">{label}</span>
      {children}
    </label>
  );
}
