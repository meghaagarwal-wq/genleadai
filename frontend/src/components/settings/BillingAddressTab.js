import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Receipt, FloppyDisk, Info } from '@phosphor-icons/react';
import api from '../../config/api';

const INDIAN_STATES = [
  'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh', 'Goa', 'Gujarat',
  'Haryana', 'Himachal Pradesh', 'Jharkhand', 'Karnataka', 'Kerala', 'Madhya Pradesh',
  'Maharashtra', 'Manipur', 'Meghalaya', 'Mizoram', 'Nagaland', 'Odisha', 'Punjab',
  'Rajasthan', 'Sikkim', 'Tamil Nadu', 'Telangana', 'Tripura', 'Uttar Pradesh',
  'Uttarakhand', 'West Bengal', 'Delhi', 'Chandigarh', 'Puducherry', 'Jammu and Kashmir',
  'Ladakh', 'Andaman and Nicobar Islands', 'Dadra and Nagar Haveli and Daman and Diu', 'Lakshadweep',
];

export default function BillingAddressTab() {
  const [form, setForm] = useState({
    legal_name: '', billing_email: '', billing_gstin: '',
    billing_state: '', billing_address: '',
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get('/api/billing/tenant-info')
      .then((r) => setForm((f) => ({ ...f, ...(r.data || {}) })))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const save = async () => {
    setSaving(true);
    try {
      await api.put('/api/billing/tenant-info', form);
      toast.success('Billing details saved. Future invoices will use this info.');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not save');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="text-slate-400 text-sm">Loading…</div>;

  return (
    <div data-testid="billing-address-tab" className="space-y-4">
      <div className="bg-white border border-[#E8E0F5] rounded-2xl p-5" style={{ boxShadow: 'var(--shadow-card)' }}>
        <div className="flex items-start gap-3 mb-4">
          <div className="w-9 h-9 rounded-xl bg-violet-50 text-violet-600 flex items-center justify-center">
            <Receipt size={18} weight="duotone" />
          </div>
          <div>
            <h3 className="text-base font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Billing address & GSTIN</h3>
            <p className="text-xs text-[#5A4A7A] mt-0.5">
              Filled into every tax invoice we issue for plan upgrades. Karnataka-based buyers get CGST+SGST automatically.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Field label="Legal name on invoice">
            <input data-testid="billing-legal-name" value={form.legal_name || ''} onChange={set('legal_name')} className={inputCls} placeholder="Acme Technologies Pvt Ltd" />
          </Field>
          <Field label="Billing email">
            <input data-testid="billing-email" type="email" value={form.billing_email || ''} onChange={set('billing_email')} className={inputCls} placeholder="finance@acme.com" />
          </Field>
          <Field label="GSTIN (optional)">
            <input data-testid="billing-gstin" value={form.billing_gstin || ''} onChange={set('billing_gstin')} className={`${inputCls} font-mono`} placeholder="29ABCDE1234F1Z5" maxLength={15} />
          </Field>
          <Field label="State">
            <select data-testid="billing-state" value={form.billing_state || ''} onChange={set('billing_state')} className={inputCls}>
              <option value="">— select state —</option>
              {INDIAN_STATES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </Field>
          <Field label="Address" wide>
            <textarea data-testid="billing-address" value={form.billing_address || ''} onChange={set('billing_address')} rows={2} className={inputCls} placeholder="Floor, building, street, city, PIN" />
          </Field>
        </div>

        <div className="flex items-start gap-2 mt-4 p-3 rounded-xl bg-slate-50 border border-slate-200">
          <Info size={14} className="text-slate-500 mt-0.5 shrink-0" />
          <p className="text-[11px] text-slate-600 leading-relaxed">
            We default to <b>IGST 18%</b> if your state isn't filled. Karnataka-registered buyers (matching the seller state) get <b>CGST 9% + SGST 9%</b> instead. Either way the total is the same — only the breakdown changes.
          </p>
        </div>

        <div className="flex justify-end mt-4">
          <button
            data-testid="billing-save-btn"
            onClick={save}
            disabled={saving}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-900 text-white text-xs font-bold uppercase tracking-wider hover:bg-slate-800 disabled:opacity-50"
          >
            <FloppyDisk size={14} weight="bold" /> {saving ? 'Saving…' : 'Save billing details'}
          </button>
        </div>
      </div>
    </div>
  );
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
