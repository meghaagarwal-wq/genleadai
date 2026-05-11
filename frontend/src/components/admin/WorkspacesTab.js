import React, { useEffect, useState } from 'react';
import api from '../../config/api';
import { toast } from 'sonner';
import {
  CheckCircle, Warning, Buildings, Users, MagnifyingGlass, ArrowsClockwise,
  Rocket, Clock, X, EnvelopeSimple,
} from '@phosphor-icons/react';

const fmtDate = (iso) => { if (!iso) return '—'; try { return new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }); } catch { return '—'; } };
const daysUntil = (iso) => { if (!iso) return null; const d = Math.round((new Date(iso) - Date.now()) / 86400000); return d; };

// ─── Pre-Launch Checklist modal ─────────────────────────────────────────────
const ChecklistModal = ({ tenantId, tenantName, onClose, onSaved }) => {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.get(`/api/admin/workspaces/${tenantId}/launch-checklist`).then((r) => setData(r.data)); }, [tenantId]);
  if (!data) return null;

  const toggle = (key) => setData({ ...data, state: { ...(data.state || {}), [key]: !(data.state || {})[key] } });
  const save = async () => {
    setBusy(true);
    try {
      const r = await api.put(`/api/admin/workspaces/${tenantId}/launch-checklist`, { state: data.state || {} });
      toast.success(r.data?.is_launch_ready ? 'Workspace marked launch-ready 🚀' : 'Checklist saved');
      onSaved && onSaved(); onClose();
    } catch (e) { toast.error(e.response?.data?.detail || 'Save failed'); }
    finally { setBusy(false); }
  };
  const markReady = async () => {
    if (!window.confirm(`Mark ${tenantName} as launch-ready? This skips the remaining checklist items.`)) return;
    try { await api.post(`/api/admin/workspaces/${tenantId}/mark-launch-ready`); toast.success('Marked launch-ready'); onSaved && onSaved(); onClose(); }
    catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
  };

  const grouped = {};
  for (const it of data.items) { grouped[it.group] = grouped[it.group] || []; grouped[it.group].push(it); }
  const checkedCount = Object.values(data.state || {}).filter(Boolean).length;
  const totalCount = data.items.length;

  return (
    <div className="fixed inset-0 bg-black/30 backdrop-blur-sm z-50 flex items-center justify-center p-4" data-testid="checklist-modal">
      <div className="bg-white border border-[#E8E0F5] rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col" style={{ boxShadow: 'var(--shadow-hover)' }}>
        <div className="flex items-center justify-between p-5 border-b border-[#E8E0F5]">
          <div>
            <h3 className="text-lg font-bold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Pre-Launch Checklist</h3>
            <p className="text-xs text-[#9B8AB0]">{tenantName} · {checkedCount}/{totalCount} complete</p>
          </div>
          <button onClick={onClose}><X size={20} className="text-[#9B8AB0]" /></button>
        </div>
        <div className="p-5 overflow-y-auto space-y-5">
          {Object.entries(grouped).map(([group, items]) => (
            <div key={group}>
              <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#9B8AB0] mb-2">{group}</div>
              <div className="space-y-1.5">
                {items.map((it) => {
                  const checked = !!(data.state || {})[it.key];
                  return (
                    <label key={it.key} data-testid={`check-${it.key}`} className={`flex items-center gap-3 px-3 py-2 rounded-lg border cursor-pointer ${checked ? 'border-[#16A34A]/30 bg-[#DCFCE7]/40' : 'border-[#E8E0F5] hover:border-[#7C35DC]/40'}`}>
                      <input type="checkbox" checked={checked} onChange={() => toggle(it.key)} className="w-4 h-4 accent-[#7C35DC]" />
                      <span className="text-sm text-[#1A0A2E]">{it.label}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
        <div className="px-5 py-4 border-t border-[#E8E0F5] flex items-center justify-between">
          <button data-testid="mark-ready-btn" onClick={markReady} className="text-xs font-bold text-[#16A34A] hover:underline">Force-mark launch-ready</button>
          <div className="flex gap-2">
            <button onClick={onClose} className="px-4 py-2 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-lg text-sm font-medium">Cancel</button>
            <button data-testid="save-checklist-btn" onClick={save} disabled={busy} className="px-5 py-2 btn-gradient rounded-lg text-sm font-bold disabled:opacity-40" style={{ fontFamily: 'Plus Jakarta Sans' }}>{busy ? 'Saving…' : 'Save'}</button>
          </div>
        </div>
      </div>
    </div>
  );
};

// ─── Platform Stats panel ──────────────────────────────────────────────────
const PlatformStats = () => {
  const [s, setS] = useState(null);
  useEffect(() => { api.get('/api/admin/workspaces/platform/stats').then((r) => setS(r.data)); }, []);
  if (!s) return null;
  const cells = [
    { l: 'Total Workspaces', v: s.total_workspaces },
    { l: 'Paying Clients', v: s.active_paying_clients },
    { l: 'Trial Workspaces', v: s.trial_workspaces },
    { l: 'Total Leads', v: s.total_leads },
    { l: 'Conversations', v: s.total_conversations },
    { l: 'Messages 24h', v: s.messages_sent_24h },
    { l: 'Failed 24h', v: s.failed_messages_24h, tone: s.failed_messages_24h > 0 ? 'red' : null },
    { l: 'Claude Cost Today', v: `$${(s.claude_cost_today_usd || 0).toFixed(2)}` },
  ];
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="platform-stats">
      {cells.map((c) => (
        <div key={c.l} className="bg-white border border-[#E8E0F5] rounded-xl p-3" style={{ boxShadow: 'var(--shadow-card)' }} data-testid={`stat-${c.l.toLowerCase().replace(/\s+/g, '-')}`}>
          <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#9B8AB0]">{c.l}</div>
          <div className={`mt-1 text-2xl font-extrabold ${c.tone === 'red' ? 'text-[#DC2626]' : 'text-[#1A0A2E]'}`} style={{ fontFamily: 'Plus Jakarta Sans' }}>{c.v}</div>
        </div>
      ))}
    </div>
  );
};

// ─── Trials Expiring panel ─────────────────────────────────────────────────
const TrialsExpiring = ({ refreshTick }) => {
  const [list, setList] = useState([]);
  const [busy, setBusy] = useState({});
  const load = () => { api.get('/api/admin/workspaces/trials/expiring?days=3').then((r) => setList(r.data?.trials || [])); };
  useEffect(load, [refreshTick]);

  const extend = async (tid) => {
    setBusy({ ...busy, [tid]: true });
    try { await api.post(`/api/admin/workspaces/${tid}/extend-trial`, { days: 7 }); toast.success('Trial extended 7 days'); load(); }
    catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    finally { setBusy({ ...busy, [tid]: false }); }
  };

  return (
    <div className="bg-white border border-[#E8E0F5] rounded-xl p-5" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="trials-expiring-panel">
      <div className="flex items-center gap-2 mb-3">
        <Clock size={16} weight="fill" className="text-[#D97706]" />
        <h3 className="font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Trials Expiring Soon</h3>
        <span className="text-xs text-[#9B8AB0]">≤ 3 days</span>
      </div>
      {list.length === 0 ? <div className="text-sm text-[#9B8AB0] py-4">No trials expiring in the next 3 days.</div> : (
        <div className="space-y-2">
          {list.map((t) => (
            <div key={t.tenant_id} className="border border-[#E0D4F7] rounded-lg p-3 flex items-center justify-between gap-3" data-testid={`trial-row-${t.tenant_id}`}>
              <div className="flex-1 min-w-0">
                <div className="font-bold text-[#1A0A2E] text-sm truncate">{t.tenant_name}</div>
                <div className="text-[11px] text-[#9B8AB0] font-mono truncate">{t.owner_email}</div>
                <div className="flex items-center gap-3 mt-1 text-[10px]">
                  <span className={t.onboarding_completed ? 'text-[#16A34A]' : 'text-[#94A3B8]'}>{t.onboarding_completed ? '✓ Onboarded' : '✗ Not onboarded'}</span>
                  <span className="text-[#5A4A7A]">{t.lead_count} leads</span>
                </div>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <div className="text-right text-[10px]">
                  <div className="text-[#D97706] font-bold">Ends {fmtDate(t.trial_ends_at)}</div>
                </div>
                <button data-testid={`extend-trial-${t.tenant_id}`} onClick={() => extend(t.tenant_id)} disabled={busy[t.tenant_id]} className="px-2.5 py-1 bg-white border border-[#7C35DC]/30 text-[#7C35DC] rounded text-[10px] font-bold hover:bg-[#F4F0FF] disabled:opacity-40">{busy[t.tenant_id] ? '…' : '+7 days'}</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ─── Workspaces Table ──────────────────────────────────────────────────────
const WorkspacesTab = () => {
  const [data, setData] = useState({ workspaces: [], total: 0 });
  const [search, setSearch] = useState('');
  const [plan, setPlan] = useState('');
  const [checklistFor, setChecklistFor] = useState(null);
  const [refreshTick, setRefreshTick] = useState(0);

  const load = () => {
    const params = {};
    if (search) params.search = search;
    if (plan) params.plan = plan;
    api.get('/api/admin/workspaces', { params }).then((r) => setData(r.data));
  };
  useEffect(load, [search, plan, refreshTick]);

  return (
    <div className="space-y-5" data-testid="workspaces-tab">
      <PlatformStats />
      <TrialsExpiring refreshTick={refreshTick} />

      <div className="bg-white border border-[#E8E0F5] rounded-xl" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="all-workspaces-table">
        <div className="px-5 py-4 border-b border-[#E8E0F5] flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-2">
            <Buildings size={18} weight="duotone" className="text-[#7C35DC]" />
            <h3 className="font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>All Workspaces <span className="text-[#9B8AB0] font-normal text-sm">({data.total})</span></h3>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <MagnifyingGlass size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#9B8AB0]" />
              <input data-testid="ws-search" placeholder="Search workspace…" value={search} onChange={(e) => setSearch(e.target.value)} className="pl-7 pr-3 py-1.5 bg-white border border-[#E8E0F5] rounded-lg text-sm" />
            </div>
            <select data-testid="ws-plan-filter" value={plan} onChange={(e) => setPlan(e.target.value)} className="bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-1.5 rounded-lg text-sm">
              <option value="">All plans</option>
              <option value="trial">Trial</option>
              <option value="diy">DIY</option>
              <option value="dwy">DWY</option>
              <option value="dfy">DFY</option>
            </select>
            <button onClick={() => setRefreshTick((t) => t + 1)} className="p-1.5 text-[#5A4A7A] hover:text-[#7C35DC]" data-testid="ws-refresh"><ArrowsClockwise size={14} weight="bold" /></button>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-[#F4F0FF]">
                {['Workspace', 'Owner', 'Plan', 'Trial Ends', 'Seats', 'Leads', 'Last Active', 'Launch', 'Actions'].map((h) => (
                  <th key={h} className="px-4 py-2.5 text-left text-[10px] font-bold uppercase tracking-[0.15em] text-[#5A4A7A]">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.workspaces.length === 0 ? (
                <tr><td colSpan={9} className="px-4 py-10 text-center text-[#9B8AB0]">No workspaces</td></tr>
              ) : data.workspaces.map((w) => {
                const trialDays = daysUntil(w.trial_ends_at);
                return (
                <tr key={w.id} className="border-b border-[#F0ECF9] hover:bg-[#FAF7FF]" data-testid={`ws-row-${w.id}`}>
                  <td className="px-4 py-2 font-semibold text-[#1A0A2E]">{w.name}</td>
                  <td className="px-4 py-2 text-[#5A4A7A] text-xs font-mono">{w.owner_email || '—'}</td>
                  <td className="px-4 py-2"><span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded bg-[#F4F0FF] text-[#7C35DC] border border-[#7C35DC]/20">{w.plan}</span></td>
                  <td className="px-4 py-2 text-[#5A4A7A] text-xs">
                    {w.plan === 'trial' && trialDays !== null ? (
                      <span className={trialDays <= 3 ? 'text-[#DC2626] font-bold' : ''}>{trialDays}d</span>
                    ) : fmtDate(w.trial_ends_at)}
                  </td>
                  <td className="px-4 py-2 text-[#5A4A7A] font-mono">{w.seats}</td>
                  <td className="px-4 py-2 text-[#5A4A7A] font-mono">{w.leads}</td>
                  <td className="px-4 py-2 text-[#9B8AB0] text-xs">{fmtDate(w.last_active_at)}</td>
                  <td className="px-4 py-2">
                    {w.is_launch_ready ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-bold uppercase rounded bg-[#DCFCE7] text-[#16A34A] border border-[#16A34A]/30"><CheckCircle size={10} weight="fill" /> Ready</span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-bold uppercase rounded bg-[#FEF3C7] text-[#D97706] border border-[#D97706]/30"><Warning size={10} weight="fill" /> Pending</span>
                    )}
                  </td>
                  <td className="px-4 py-2">
                    <button onClick={() => setChecklistFor({ id: w.id, name: w.name })} data-testid={`checklist-${w.id}`} className="text-xs font-bold text-[#7C35DC] hover:underline inline-flex items-center gap-1">
                      <Rocket size={10} weight="fill" /> Checklist
                    </button>
                  </td>
                </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {checklistFor && <ChecklistModal tenantId={checklistFor.id} tenantName={checklistFor.name} onClose={() => setChecklistFor(null)} onSaved={() => setRefreshTick((t) => t + 1)} />}
    </div>
  );
};

export default WorkspacesTab;
