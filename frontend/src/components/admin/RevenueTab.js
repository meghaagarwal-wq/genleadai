import React, { useEffect, useState } from 'react';
import api from '../../config/api';
import { toast } from 'sonner';
import {
  CurrencyInr, TrendUp, TrendDown, Users, Clock, ArrowUpRight, ArrowDownRight,
  Receipt, Warning, X, DownloadSimple, Plus, ChartLineDown, Funnel
} from '@phosphor-icons/react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RTooltip, ResponsiveContainer,
  LineChart, Line, Legend
} from 'recharts';

const PLANS = ['diy', 'dwy', 'dfy', 'trial', 'free', 'suspended'];
const STATUSES = ['active', 'pending', 'overdue', 'cancelled', 'suspended', 'trial'];
const METHODS = ['manual', 'bank_transfer', 'upi', 'stripe'];
const CANCEL_REASONS = [
  { id: 'price', label: 'Price' },
  { id: 'no_longer_needed', label: 'No longer needed' },
  { id: 'competitor', label: 'Competitor' },
  { id: 'support_issue', label: 'Support issue' },
  { id: 'other', label: 'Other' },
];

const PLAN_COLORS = { diy: '#4F8EF7', dwy: '#E2B96F', dfy: '#7C35DC' };

const fmtINR = (v) => new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(Math.round(v || 0));
const fmtDate = (iso) => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }); }
  catch { return '—'; }
};

// ─── KPI Card ────────────────────────────────────────────────────────────────
const Kpi = ({ label, value, suffix, delta, icon: Icon, testid }) => {
  const up = (delta || 0) >= 0;
  const Trend = up ? ArrowUpRight : ArrowDownRight;
  return (
    <div className="bg-white border border-[#E8E0F5] rounded-xl p-4" style={{ boxShadow: 'var(--shadow-card)' }} data-testid={testid}>
      <div className="flex items-start justify-between">
        <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#9B8AB0]">{label}</div>
        {Icon && <Icon size={16} weight="duotone" className="text-[#7C35DC]" />}
      </div>
      <div className="mt-2 flex items-baseline gap-1">
        <span className="text-3xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{value}</span>
        {suffix && <span className="text-sm font-semibold text-[#5A4A7A]">{suffix}</span>}
      </div>
      {delta !== null && delta !== undefined && (
        <div className={`mt-1 inline-flex items-center gap-0.5 text-[11px] font-bold ${up ? 'text-[#16A34A]' : 'text-[#DC2626]'}`}>
          <Trend size={11} weight="bold" /> {Math.abs(delta).toFixed(1)}% vs last month
        </div>
      )}
    </div>
  );
};

// ─── KPI Row ─────────────────────────────────────────────────────────────────
const KpiRow = () => {
  const [data, setData] = useState(null);
  useEffect(() => {
    api.get('/api/admin/revenue/summary')
      .then((r) => setData(r.data))
      .catch(() => toast.error('Could not load revenue summary'));
  }, []);
  if (!data) return <div className="text-sm text-[#9B8AB0]" data-testid="kpi-loading">Loading KPIs…</div>;
  const k = data.kpis; const t = data.trends;
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3" data-testid="kpi-row">
      <Kpi testid="kpi-mrr" label="MRR" value={`₹${fmtINR(k.mrr)}`} delta={t.mrr_delta_pct} icon={CurrencyInr} />
      <Kpi testid="kpi-arr" label="ARR" value={`₹${fmtINR(k.arr)}`} delta={t.arr_delta_pct} icon={TrendUp} />
      <Kpi testid="kpi-paying" label="Paying Clients" value={k.total_paying_clients} delta={null} icon={Users} />
      <Kpi testid="kpi-trials" label="Active Trials" value={k.active_trials} delta={null} icon={Clock} />
      <Kpi testid="kpi-conv" label="Trial → Paid" value={k.trial_to_paid_pct} suffix="%" delta={null} icon={TrendUp} />
      <Kpi testid="kpi-churn" label="Monthly Churn" value={k.monthly_churn_pct} suffix="%" delta={null} icon={ChartLineDown} />
    </div>
  );
};

// ─── Revenue by Plan ────────────────────────────────────────────────────────
const RevenueByPlanChart = () => {
  const [data, setData] = useState([]);
  useEffect(() => { api.get('/api/admin/revenue/by-plan?months=6').then((r) => setData(r.data?.data || [])); }, []);
  return (
    <div className="bg-white border border-[#E8E0F5] rounded-xl p-5" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="revenue-by-plan">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Revenue by Plan</h3>
        <div className="flex items-center gap-3 text-[11px] font-semibold">
          {['diy', 'dwy', 'dfy'].map((p) => (
            <span key={p} className="inline-flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm" style={{ background: PLAN_COLORS[p] }} />
              <span className="uppercase text-[#5A4A7A]">{p}</span>
            </span>
          ))}
        </div>
      </div>
      <div style={{ width: '100%', height: 280 }}>
        <ResponsiveContainer>
          <BarChart data={data}>
            <CartesianGrid stroke="#F0ECF9" vertical={false} />
            <XAxis dataKey="month" tick={{ fontSize: 11, fill: '#5A4A7A' }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 11, fill: '#5A4A7A' }} axisLine={false} tickLine={false} tickFormatter={(v) => `₹${fmtINR(v)}`} />
            <RTooltip formatter={(v) => `₹${fmtINR(v)}`} cursor={{ fill: '#F4F0FF' }} />
            <Bar dataKey="diy" name="DIY" fill={PLAN_COLORS.diy} radius={[4, 4, 0, 0]} />
            <Bar dataKey="dwy" name="DWY" fill={PLAN_COLORS.dwy} radius={[4, 4, 0, 0]} />
            <Bar dataKey="dfy" name="DFY" fill={PLAN_COLORS.dfy} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

// ─── Manage Subscription Modal ──────────────────────────────────────────────
const ManageModal = ({ sub, onClose, onChanged }) => {
  const [plan, setPlan] = useState(sub.plan);
  const [customPrice, setCustomPrice] = useState(sub.custom_price || '');
  const [notes, setNotes] = useState(sub.notes || '');
  const [cancelReason, setCancelReason] = useState('price');
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    try {
      await api.put(`/api/admin/revenue/subscriptions/${sub.tenant_id}`, {
        plan, custom_price: customPrice === '' ? null : Number(customPrice), notes,
      });
      toast.success('Subscription updated'); onChanged(); onClose();
    } catch (e) { toast.error(e.response?.data?.detail || 'Save failed'); }
    finally { setBusy(false); }
  };
  const extend = async () => {
    setBusy(true);
    try { await api.post(`/api/admin/revenue/subscriptions/${sub.tenant_id}/extend`, { days: 30 }); toast.success('Extended 30 days'); onChanged(); onClose(); }
    catch (e) { toast.error(e.response?.data?.detail || 'Extend failed'); }
    finally { setBusy(false); }
  };
  const cancel = async () => {
    if (!window.confirm('Cancel this subscription?')) return;
    setBusy(true);
    try { await api.post(`/api/admin/revenue/subscriptions/${sub.tenant_id}/cancel`, { reason: cancelReason }); toast.success('Cancelled'); onChanged(); onClose(); }
    catch (e) { toast.error(e.response?.data?.detail || 'Cancel failed'); }
    finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/30 backdrop-blur-sm z-50 flex items-center justify-center p-4" data-testid="manage-sub-modal">
      <div className="bg-white border border-[#E8E0F5] rounded-2xl w-full max-w-xl" style={{ boxShadow: 'var(--shadow-hover)' }}>
        <div className="flex items-center justify-between p-5 border-b border-[#E8E0F5]">
          <div>
            <h3 className="text-lg font-bold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Manage subscription</h3>
            <p className="text-xs text-[#9B8AB0] mt-0.5">{sub.tenant_name} · {sub.owner_email || 'no owner'}</p>
          </div>
          <button onClick={onClose} data-testid="manage-close-btn"><X size={20} className="text-[#9B8AB0]" /></button>
        </div>
        <div className="p-5 space-y-4">
          <div>
            <label className="text-xs font-bold uppercase tracking-[0.15em] text-[#5A4A7A]">Plan</label>
            <select data-testid="manage-plan-select" value={plan} onChange={(e) => setPlan(e.target.value)} className="mt-1 w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-2 rounded-lg text-sm">
              {PLANS.map((p) => <option key={p} value={p}>{p.toUpperCase()}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs font-bold uppercase tracking-[0.15em] text-[#5A4A7A]">Custom price (INR/month, blank = use plan default)</label>
            <input data-testid="manage-custom-price" type="number" value={customPrice} onChange={(e) => setCustomPrice(e.target.value)} className="mt-1 w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-2 rounded-lg text-sm" />
          </div>
          <div>
            <label className="text-xs font-bold uppercase tracking-[0.15em] text-[#5A4A7A]">Internal note</label>
            <textarea data-testid="manage-notes" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} className="mt-1 w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-2 rounded-lg text-sm resize-none" />
          </div>

          <div className="border-t border-[#F0ECF9] pt-4">
            <div className="text-xs font-bold uppercase tracking-[0.15em] text-[#DC2626] mb-2">Danger zone</div>
            <div className="flex items-center gap-2 mb-2">
              <select data-testid="manage-cancel-reason" value={cancelReason} onChange={(e) => setCancelReason(e.target.value)} className="bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-2 rounded-lg text-sm flex-1">
                {CANCEL_REASONS.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
              </select>
              <button data-testid="manage-cancel-btn" onClick={cancel} disabled={busy} className="px-3 py-2 text-sm font-bold text-[#DC2626] border border-[#DC2626]/30 rounded-lg hover:bg-[#FEE2E2] disabled:opacity-40">Cancel subscription</button>
            </div>
          </div>
        </div>
        <div className="px-5 py-4 border-t border-[#E8E0F5] flex items-center justify-between">
          <button data-testid="manage-extend-btn" onClick={extend} disabled={busy} className="px-3 py-2 text-sm font-semibold text-[#7C35DC] border border-[#7C35DC]/30 rounded-lg hover:bg-[#F4F0FF] disabled:opacity-40">Extend 30 days</button>
          <div className="flex gap-2">
            <button onClick={onClose} className="px-4 py-2 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-lg text-sm font-medium">Close</button>
            <button data-testid="manage-save-btn" onClick={save} disabled={busy} className="px-5 py-2 btn-gradient rounded-lg text-sm font-bold disabled:opacity-40" style={{ fontFamily: 'Plus Jakarta Sans' }}>{busy ? 'Saving…' : 'Save'}</button>
          </div>
        </div>
      </div>
    </div>
  );
};

// ─── Subscriptions Table ────────────────────────────────────────────────────
const StatusBadge = ({ s }) => {
  const map = {
    active: 'bg-[#DCFCE7] text-[#16A34A] border-[#16A34A]/30',
    trial: 'bg-[#F4F0FF] text-[#7C35DC] border-[#7C35DC]/30',
    pending: 'bg-[#FEF3C7] text-[#D97706] border-[#D97706]/30',
    overdue: 'bg-[#FEF3C7] text-[#D97706] border-[#D97706]/30',
    cancelled: 'bg-[#F1F5F9] text-[#64748B] border-[#94A3B8]/30',
    suspended: 'bg-[#FEE2E2] text-[#DC2626] border-[#DC2626]/30',
  };
  return <span className={`px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider rounded border ${map[s] || map.cancelled}`}>{s}</span>;
};

const SubscriptionsTable = ({ refreshTick, onRefresh }) => {
  const [data, setData] = useState({ subscriptions: [], total: 0 });
  const [filters, setFilters] = useState({ status: '', plan: '', search: '' });
  const [editing, setEditing] = useState(null);

  const load = () => {
    const params = {};
    if (filters.status) params.status = filters.status;
    if (filters.plan) params.plan = filters.plan;
    if (filters.search) params.search = filters.search;
    api.get('/api/admin/revenue/subscriptions', { params }).then((r) => setData(r.data));
  };
  useEffect(load, [filters, refreshTick]);

  return (
    <div className="bg-white border border-[#E8E0F5] rounded-xl" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="subscriptions-section">
      <div className="px-5 py-4 border-b border-[#E8E0F5] flex items-center justify-between flex-wrap gap-3">
        <h3 className="font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Subscriptions <span className="text-[#9B8AB0] font-normal text-sm ml-2">({data.total})</span></h3>
        <div className="flex items-center gap-2">
          <input data-testid="subs-search" placeholder="Search workspace…" value={filters.search} onChange={(e) => setFilters({ ...filters, search: e.target.value })} className="bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-1.5 rounded-lg text-sm" />
          <select data-testid="subs-filter-plan" value={filters.plan} onChange={(e) => setFilters({ ...filters, plan: e.target.value })} className="bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-1.5 rounded-lg text-sm">
            <option value="">All plans</option>
            {PLANS.map((p) => <option key={p} value={p}>{p.toUpperCase()}</option>)}
          </select>
          <select data-testid="subs-filter-status" value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })} className="bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-1.5 rounded-lg text-sm">
            <option value="">All statuses</option>
            {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-[#F4F0FF]">
              {['Workspace', 'Owner', 'Plan', 'Monthly Value', 'Start', 'Next Renewal', 'Status', 'Actions'].map((h) => (
                <th key={h} className="px-5 py-2.5 text-left text-[10px] font-bold uppercase tracking-[0.15em] text-[#5A4A7A]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.subscriptions.length === 0 ? (
              <tr><td colSpan={8} className="px-5 py-10 text-center text-[#9B8AB0]">No subscriptions</td></tr>
            ) : data.subscriptions.map((s) => (
              <tr key={s.id} className="border-b border-[#F0ECF9] hover:bg-[#FAF7FF]" data-testid={`sub-row-${s.tenant_id}`}>
                <td className="px-5 py-2.5 font-semibold text-[#1A0A2E]">{s.tenant_name || '—'}</td>
                <td className="px-5 py-2.5 text-[#5A4A7A] text-xs font-mono">{s.owner_email || '—'}</td>
                <td className="px-5 py-2.5"><span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded bg-[#F4F0FF] text-[#7C35DC] border border-[#7C35DC]/20">{s.plan}</span></td>
                <td className="px-5 py-2.5 text-[#1A0A2E] font-mono">₹{fmtINR(s.monthly_value)}</td>
                <td className="px-5 py-2.5 text-[#5A4A7A] text-xs">{fmtDate(s.started_at)}</td>
                <td className="px-5 py-2.5 text-[#5A4A7A] text-xs">{fmtDate(s.current_period_end)}</td>
                <td className="px-5 py-2.5"><StatusBadge s={s.status} /></td>
                <td className="px-5 py-2.5">
                  <button onClick={() => setEditing(s)} data-testid={`manage-${s.tenant_id}`} className="text-xs font-bold text-[#7C35DC] hover:underline">Manage</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {editing && <ManageModal sub={editing} onClose={() => setEditing(null)} onChanged={() => { load(); onRefresh && onRefresh(); }} />}
    </div>
  );
};

// ─── Add Manual Payment Modal ───────────────────────────────────────────────
const AddPaymentModal = ({ onClose, onAdded, tenantOptions }) => {
  const [tenantId, setTenantId] = useState(tenantOptions[0]?.tenant_id || '');
  const [amount, setAmount] = useState('');
  const [method, setMethod] = useState('manual');
  const [paidAt, setPaidAt] = useState(new Date().toISOString().slice(0, 10));
  const [ref, setRef] = useState('');
  const [note, setNote] = useState('');
  const [plan, setPlan] = useState('diy');
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!tenantId || !amount) { toast.error('Workspace + amount required'); return; }
    setBusy(true);
    try {
      const r = await api.post('/api/admin/revenue/payments/manual', {
        tenant_id: tenantId, amount: Number(amount), method, plan,
        paid_at: new Date(paidAt).toISOString(), reference_number: ref, note,
      });
      toast.success(`Recorded · ${r.data?.payment?.invoice_number}`);
      onAdded(); onClose();
    } catch (e) { toast.error(e.response?.data?.detail || 'Save failed'); }
    finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/30 backdrop-blur-sm z-50 flex items-center justify-center p-4" data-testid="add-payment-modal">
      <div className="bg-white border border-[#E8E0F5] rounded-2xl w-full max-w-lg" style={{ boxShadow: 'var(--shadow-hover)' }}>
        <div className="flex items-center justify-between p-5 border-b border-[#E8E0F5]">
          <h3 className="text-lg font-bold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Record manual payment</h3>
          <button onClick={onClose} data-testid="pay-close-btn"><X size={20} className="text-[#9B8AB0]" /></button>
        </div>
        <div className="p-5 space-y-3">
          <div>
            <label className="text-xs font-bold uppercase tracking-[0.15em] text-[#5A4A7A]">Workspace</label>
            <select data-testid="pay-workspace" value={tenantId} onChange={(e) => setTenantId(e.target.value)} className="mt-1 w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-2 rounded-lg text-sm">
              {tenantOptions.map((t) => <option key={t.tenant_id} value={t.tenant_id}>{t.tenant_name} · {t.owner_email}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-bold uppercase tracking-[0.15em] text-[#5A4A7A]">Amount (INR)</label>
              <input data-testid="pay-amount" type="number" value={amount} onChange={(e) => setAmount(e.target.value)} className="mt-1 w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-2 rounded-lg text-sm" />
            </div>
            <div>
              <label className="text-xs font-bold uppercase tracking-[0.15em] text-[#5A4A7A]">Plan</label>
              <select data-testid="pay-plan" value={plan} onChange={(e) => setPlan(e.target.value)} className="mt-1 w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-2 rounded-lg text-sm">
                <option value="diy">DIY</option>
                <option value="dwy">DWY</option>
                <option value="dfy">DFY</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-bold uppercase tracking-[0.15em] text-[#5A4A7A]">Method</label>
              <select data-testid="pay-method" value={method} onChange={(e) => setMethod(e.target.value)} className="mt-1 w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-2 rounded-lg text-sm">
                {METHODS.map((m) => <option key={m} value={m}>{m.replace('_', ' ')}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-bold uppercase tracking-[0.15em] text-[#5A4A7A]">Date</label>
              <input data-testid="pay-date" type="date" value={paidAt} onChange={(e) => setPaidAt(e.target.value)} className="mt-1 w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-2 rounded-lg text-sm" />
            </div>
          </div>
          <div>
            <label className="text-xs font-bold uppercase tracking-[0.15em] text-[#5A4A7A]">Reference (UTR / Txn ID)</label>
            <input data-testid="pay-ref" value={ref} onChange={(e) => setRef(e.target.value)} className="mt-1 w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-2 rounded-lg text-sm font-mono" />
          </div>
          <div>
            <label className="text-xs font-bold uppercase tracking-[0.15em] text-[#5A4A7A]">Note</label>
            <textarea data-testid="pay-note" rows={2} value={note} onChange={(e) => setNote(e.target.value)} className="mt-1 w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-2 rounded-lg text-sm resize-none" />
          </div>
        </div>
        <div className="px-5 py-4 border-t border-[#E8E0F5] flex items-center justify-end gap-2">
          <button onClick={onClose} className="px-4 py-2 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-lg text-sm font-medium">Cancel</button>
          <button data-testid="pay-submit-btn" onClick={submit} disabled={busy} className="px-5 py-2 btn-gradient rounded-lg text-sm font-bold disabled:opacity-40" style={{ fontFamily: 'Plus Jakarta Sans' }}>{busy ? 'Saving…' : 'Save & generate invoice'}</button>
        </div>
      </div>
    </div>
  );
};

// ─── Payments Table ─────────────────────────────────────────────────────────
const PaymentsTable = ({ tenantOptions, refreshTick, onRefresh }) => {
  const [pays, setPays] = useState([]);
  const [showAdd, setShowAdd] = useState(false);

  const load = () => { api.get('/api/admin/revenue/payments?limit=50').then((r) => setPays(r.data?.payments || [])); };
  useEffect(load, [refreshTick]);

  const download = async (id, invoiceNo) => {
    try {
      const r = await api.get(`/api/admin/invoices/${id}/pdf`, { responseType: 'blob' });
      const blob = new Blob([r.data], { type: 'application/pdf' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `${invoiceNo || id}.pdf`;
      a.click(); URL.revokeObjectURL(a.href);
    } catch { toast.error('Could not download invoice'); }
  };

  return (
    <div className="bg-white border border-[#E8E0F5] rounded-xl" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="payments-section">
      <div className="px-5 py-4 border-b border-[#E8E0F5] flex items-center justify-between">
        <h3 className="font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Payment History</h3>
        <button data-testid="add-payment-btn" onClick={() => setShowAdd(true)} className="inline-flex items-center gap-1.5 px-3 py-1.5 btn-gradient rounded-lg text-sm font-bold" style={{ fontFamily: 'Plus Jakarta Sans' }}>
          <Plus size={14} weight="bold" /> Add manual payment
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-[#F4F0FF]">
              {['Date', 'Workspace', 'Plan', 'Amount', 'Method', 'Reference', 'Status', 'Invoice'].map((h) => (
                <th key={h} className="px-5 py-2.5 text-left text-[10px] font-bold uppercase tracking-[0.15em] text-[#5A4A7A]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pays.length === 0 ? (
              <tr><td colSpan={8} className="px-5 py-10 text-center text-[#9B8AB0]">No payments recorded yet</td></tr>
            ) : pays.map((p) => (
              <tr key={p.id} className="border-b border-[#F0ECF9] hover:bg-[#FAF7FF]" data-testid={`pay-row-${p.id}`}>
                <td className="px-5 py-2.5 text-[#5A4A7A] text-xs">{fmtDate(p.paid_at)}</td>
                <td className="px-5 py-2.5 font-semibold text-[#1A0A2E]">{p.tenant_name || '—'}</td>
                <td className="px-5 py-2.5"><span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded bg-[#F4F0FF] text-[#7C35DC] border border-[#7C35DC]/20">{p.plan}</span></td>
                <td className="px-5 py-2.5 text-[#1A0A2E] font-mono font-bold">₹{fmtINR(p.amount)}</td>
                <td className="px-5 py-2.5 text-[#5A4A7A] text-xs">{(p.method || '').replace('_', ' ')}</td>
                <td className="px-5 py-2.5 text-[#9B8AB0] text-xs font-mono">{p.reference_number || '—'}</td>
                <td className="px-5 py-2.5"><span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded bg-[#DCFCE7] text-[#16A34A] border border-[#16A34A]/30">{p.status}</span></td>
                <td className="px-5 py-2.5">
                  <button onClick={() => download(p.id, p.invoice_number)} data-testid={`download-${p.id}`} className="inline-flex items-center gap-1 text-xs font-bold text-[#7C35DC] hover:underline">
                    <DownloadSimple size={12} weight="bold" /> {p.invoice_number || 'PDF'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {showAdd && <AddPaymentModal onClose={() => setShowAdd(false)} onAdded={() => { load(); onRefresh && onRefresh(); }} tenantOptions={tenantOptions} />}
    </div>
  );
};

// ─── Churn Panel ────────────────────────────────────────────────────────────
const ChurnPanel = () => {
  const [data, setData] = useState(null);
  useEffect(() => { api.get('/api/admin/revenue/churn').then((r) => setData(r.data)); }, []);
  if (!data) return null;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" data-testid="churn-panel">
      <div className="bg-white border border-[#E8E0F5] rounded-xl p-5" style={{ boxShadow: 'var(--shadow-card)' }}>
        <h3 className="font-extrabold text-[#1A0A2E] mb-3" style={{ fontFamily: 'Plus Jakarta Sans' }}>Monthly Churn (12 months)</h3>
        <div style={{ width: '100%', height: 220 }}>
          <ResponsiveContainer>
            <LineChart data={data.series}>
              <CartesianGrid stroke="#F0ECF9" vertical={false} />
              <XAxis dataKey="month" tick={{ fontSize: 10, fill: '#5A4A7A' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: '#5A4A7A' }} axisLine={false} tickLine={false} tickFormatter={(v) => `${v}%`} />
              <RTooltip formatter={(v) => `${v}%`} />
              <Line type="monotone" dataKey="rate" stroke="#DC2626" strokeWidth={2} dot={{ fill: '#DC2626', r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="bg-white border border-[#E8E0F5] rounded-xl p-5" style={{ boxShadow: 'var(--shadow-card)' }}>
        <h3 className="font-extrabold text-[#1A0A2E] mb-3" style={{ fontFamily: 'Plus Jakarta Sans' }}>Retention Cohort</h3>
        <table className="w-full text-xs" data-testid="retention-table">
          <thead>
            <tr className="text-[#9B8AB0]">
              <th className="text-left py-1.5">Cohort</th>
              <th className="text-right">Size</th>
              <th className="text-right">M+1</th>
              <th className="text-right">M+2</th>
              <th className="text-right">M+3</th>
            </tr>
          </thead>
          <tbody>
            {data.cohort.map((c) => (
              <tr key={c.cohort} className="border-t border-[#F0ECF9]">
                <td className="py-1.5 font-semibold text-[#1A0A2E]">{c.cohort}</td>
                <td className="text-right text-[#5A4A7A] font-mono">{c.size}</td>
                <td className="text-right text-[#5A4A7A] font-mono">{c.m1}%</td>
                <td className="text-right text-[#5A4A7A] font-mono">{c.m2}%</td>
                <td className="text-right text-[#5A4A7A] font-mono">{c.m3}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="lg:col-span-2 bg-white border border-[#E8E0F5] rounded-xl p-5" style={{ boxShadow: 'var(--shadow-card)' }}>
        <h3 className="font-extrabold text-[#1A0A2E] mb-3" style={{ fontFamily: 'Plus Jakarta Sans' }}>Churned Accounts</h3>
        {data.churned.length === 0 ? (
          <div className="text-sm text-[#9B8AB0] py-8 text-center">No churned accounts. Nice 🎉</div>
        ) : (
          <table className="w-full text-sm" data-testid="churned-table">
            <thead className="text-[10px] uppercase tracking-[0.15em] text-[#9B8AB0]">
              <tr><th className="text-left py-1.5">Workspace</th><th className="text-left">Plan</th><th className="text-right">Value Lost</th><th className="text-left">Date</th><th className="text-left">Reason</th></tr>
            </thead>
            <tbody>
              {data.churned.map((c) => (
                <tr key={c.id} className="border-t border-[#F0ECF9]">
                  <td className="py-1.5 font-semibold text-[#1A0A2E]">{c.tenant_name}</td>
                  <td className="text-[#5A4A7A]">{(c.plan || '').toUpperCase()}</td>
                  <td className="text-right text-[#DC2626] font-bold font-mono">₹{fmtINR(c.monthly_value_lost)}</td>
                  <td className="text-[#5A4A7A] text-xs">{fmtDate(c.cancelled_at)}</td>
                  <td className="text-[#5A4A7A] text-xs">{(c.cancel_reason || '').replace('_', ' ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

// ─── Trial Funnel ───────────────────────────────────────────────────────────
const TrialFunnel = () => {
  const [data, setData] = useState(null);
  const [openStage, setOpenStage] = useState(null);
  useEffect(() => { api.get('/api/admin/revenue/trial-funnel').then((r) => setData(r.data)); }, []);
  if (!data) return null;
  const maxCount = Math.max(...data.stages.map((s) => s.count), 1);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" data-testid="trial-funnel">
      <div className="bg-white border border-[#E8E0F5] rounded-xl p-5" style={{ boxShadow: 'var(--shadow-card)' }}>
        <h3 className="font-extrabold text-[#1A0A2E] mb-4" style={{ fontFamily: 'Plus Jakarta Sans' }}>Trial Pipeline (this month)</h3>
        <div className="space-y-2">
          {data.stages.map((s, i) => {
            const pct = (s.count / maxCount) * 100;
            return (
              <div key={s.key}>
                <button
                  onClick={() => setOpenStage(openStage === s.key ? null : s.key)}
                  data-testid={`funnel-stage-${s.key}`}
                  className="w-full flex items-center justify-between gap-3 px-3 py-2 rounded-lg hover:bg-[#F9F5FF] transition-colors text-left"
                >
                  <div className="flex items-center gap-3 flex-1">
                    <span className="text-[11px] font-mono text-[#9B8AB0] w-4">{i + 1}</span>
                    <span className="text-sm font-semibold text-[#1A0A2E] flex-1">{s.label}</span>
                  </div>
                  <span className="text-xl font-extrabold text-[#7C35DC] font-mono" style={{ fontFamily: 'JetBrains Mono' }}>{s.count}</span>
                </button>
                <div className="h-2 bg-[#F0ECF9] rounded-full overflow-hidden mx-3">
                  <div className="h-full transition-all duration-500" style={{ width: `${pct}%`, background: 'var(--gradient-brand-horizontal)' }}></div>
                </div>
                {openStage === s.key && s.tenants.length > 0 && (
                  <div className="mt-2 ml-7 mr-3 bg-[#FAF7FF] border border-[#E0D4F7] rounded-lg p-2 max-h-40 overflow-y-auto" data-testid={`funnel-list-${s.key}`}>
                    {s.tenants.slice(0, 20).map((t) => (
                      <div key={t.id} className="text-xs py-1 flex items-center gap-2">
                        <span className="font-semibold text-[#1A0A2E]">{t.name || '—'}</span>
                        <span className="text-[#9B8AB0] font-mono">{t.owner_email}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="bg-white border border-[#E8E0F5] rounded-xl p-5" style={{ boxShadow: 'var(--shadow-card)' }}>
        <h3 className="font-extrabold text-[#1A0A2E] mb-3 flex items-center gap-2" style={{ fontFamily: 'Plus Jakarta Sans' }}>
          <Warning size={16} weight="fill" className="text-[#D97706]" />
          Trials Expiring Soon (≤3 days)
        </h3>
        {data.expiring_soon.length === 0 ? (
          <div className="text-sm text-[#9B8AB0] py-8 text-center">No trials expiring in the next 3 days.</div>
        ) : (
          <div className="space-y-2" data-testid="expiring-list">
            {data.expiring_soon.map((s) => (
              <div key={s.id} className="border border-[#E0D4F7] rounded-lg p-3 flex items-center justify-between gap-3" data-testid={`expiring-${s.tenant_id}`}>
                <div className="flex-1">
                  <div className="font-bold text-[#1A0A2E] text-sm">{s.tenant_name}</div>
                  <div className="text-[11px] text-[#9B8AB0] font-mono">{s.owner_email}</div>
                  <div className="flex items-center gap-3 mt-1 text-[10px]">
                    <span className={s.onboarding_completed ? 'text-[#16A34A]' : 'text-[#94A3B8]'}>{s.onboarding_completed ? '✓ Onboarded' : '✗ Not onboarded'}</span>
                    <span className={s.whatsapp_connected ? 'text-[#16A34A]' : 'text-[#94A3B8]'}>{s.whatsapp_connected ? '✓ WA' : '✗ WA'}</span>
                    <span className="text-[#5A4A7A]">{s.lead_count} leads</span>
                  </div>
                </div>
                <div className="text-right text-[10px]">
                  <div className="text-[#D97706] font-bold">Ends {fmtDate(s.current_period_end)}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

// ─── Top-level Tab ──────────────────────────────────────────────────────────
const RevenueTab = () => {
  const [refreshTick, setRefreshTick] = useState(0);
  const [tenants, setTenants] = useState([]);
  useEffect(() => {
    api.get('/api/admin/revenue/subscriptions').then((r) => setTenants(r.data?.subscriptions || []));
  }, [refreshTick]);
  const refresh = () => setRefreshTick((x) => x + 1);

  return (
    <div className="space-y-5" data-testid="revenue-tab">
      <KpiRow key={refreshTick} />
      <RevenueByPlanChart key={`bp-${refreshTick}`} />
      <SubscriptionsTable refreshTick={refreshTick} onRefresh={refresh} />
      <PaymentsTable tenantOptions={tenants} refreshTick={refreshTick} onRefresh={refresh} />
      <ChurnPanel key={`cp-${refreshTick}`} />
      <TrialFunnel key={`tf-${refreshTick}`} />
    </div>
  );
};

export default RevenueTab;
