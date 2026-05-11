/**
 * TrialExpiriesTab — workspaces with trials expiring soon (≤3 days).
 */
import React, { useEffect, useState } from 'react';
import api from '../../config/api';
import { toast } from 'sonner';
import { Clock, Rocket, EnvelopeSimple, CheckCircle } from '@phosphor-icons/react';

const fmtDate = (iso) => { if (!iso) return '—'; try { return new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }); } catch { return '—'; } };
const daysUntil = (iso) => { if (!iso) return null; return Math.round((new Date(iso) - Date.now()) / 86400000); };

const TrialExpiriesTab = () => {
  const [trials, setTrials] = useState([]);
  const [days, setDays] = useState(3);
  const [busy, setBusy] = useState(null);

  const load = async () => {
    try { const r = await api.get(`/api/admin/workspaces/trials/expiring?days=${days}`); setTrials(r.data?.trials || []); }
    catch (e) { toast.error('Failed to load'); }
  };
  useEffect(() => { load(); }, [days]);

  const extend = async (tenantId) => {
    if (!window.confirm('Extend this trial by 7 days?')) return;
    setBusy(tenantId);
    try { await api.post(`/api/admin/workspaces/${tenantId}/extend-trial`, { days: 7 }); toast.success('Trial extended +7 days'); load(); }
    catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    finally { setBusy(null); }
  };

  const markConverted = async (tenantId) => {
    if (!window.confirm('Mark this workspace as converted? (Use after they pay manually)')) return;
    setBusy(tenantId);
    try {
      await api.put(`/api/admin/revenue/subscriptions/${tenantId}`, { plan: 'diy', status: 'active' });
      toast.success('Marked as converted'); load();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    finally { setBusy(null); }
  };

  return (
    <div className="space-y-4" data-testid="trial-expiries-tab">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-lg font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Trial Expiries</h2>
          <p className="text-xs text-[#5A4A7A]">Workspaces with trials ending within the selected window. Reach out before they churn.</p>
        </div>
        <select value={days} onChange={(e) => setDays(Number(e.target.value))} data-testid="trials-window"
          className="bg-white border border-[#E8E0F5] px-3 py-1.5 rounded-lg text-xs font-bold text-[#5A4A7A]">
          {[1, 3, 7, 14].map((d) => <option key={d} value={d}>≤ {d} day{d === 1 ? '' : 's'}</option>)}
        </select>
      </div>

      {trials.length === 0 ? (
        <div className="bg-white border border-[#E8E0F5] rounded-xl p-10 text-center text-sm text-[#9B8AB0]">
          No trials expiring in the next {days} day{days === 1 ? '' : 's'} 🎉
        </div>
      ) : (
        <div className="bg-white border border-[#E8E0F5] rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[#F9F5FF]">
              <tr>
                {['Workspace', 'Owner', 'Trial Ends', 'Days Left', 'Onboarded', 'Leads', 'Actions'].map((h) => (
                  <th key={h} className="px-4 py-2.5 text-left text-[10px] font-bold uppercase tracking-[0.15em] text-[#5A4A7A]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {trials.map((t) => {
                const d = daysUntil(t.trial_ends_at);
                const danger = d !== null && d <= 1;
                return (
                  <tr key={t.tenant_id} className="border-t border-[#F0ECF9]" data-testid={`trial-row-${t.tenant_id}`}>
                    <td className="px-4 py-3 font-semibold text-[#1A0A2E]">{t.tenant_name || '—'}</td>
                    <td className="px-4 py-3 text-xs text-[#5A4A7A] font-mono">{t.owner_email || '—'}</td>
                    <td className="px-4 py-3 text-xs text-[#5A4A7A]">{fmtDate(t.trial_ends_at)}</td>
                    <td className="px-4 py-3"><span className={`px-2 py-0.5 text-[10px] font-bold rounded border ${danger ? 'bg-[#FEE2E2] text-[#DC2626] border-[#DC2626]/30' : 'bg-[#FEF3C7] text-[#D97706] border-[#D97706]/30'}`}>{d ?? '—'}d</span></td>
                    <td className="px-4 py-3">{t.onboarding_completed ? <CheckCircle size={14} weight="fill" className="text-[#16A34A]" /> : <Clock size={14} className="text-[#D97706]" />}</td>
                    <td className="px-4 py-3 text-xs text-[#5A4A7A]">{t.lead_count}</td>
                    <td className="px-4 py-3 flex items-center gap-1.5">
                      <button onClick={() => extend(t.tenant_id)} disabled={busy === t.tenant_id} data-testid={`extend-${t.tenant_id}`} className="inline-flex items-center gap-1 px-2 py-1 bg-white border border-[#7C35DC]/30 text-[#7C35DC] rounded text-[10px] font-bold hover:bg-[#F4F0FF] disabled:opacity-40"><Clock size={10} weight="bold" /> +7d</button>
                      <a href={`mailto:${t.owner_email}?subject=Your%20Aria%20trial%20ends%20${fmtDate(t.trial_ends_at)}`} className="inline-flex items-center gap-1 px-2 py-1 bg-white border border-[#0055FF]/30 text-[#0055FF] rounded text-[10px] font-bold hover:bg-[#DCEEFE]"><EnvelopeSimple size={10} weight="bold" /> Email</a>
                      <button onClick={() => markConverted(t.tenant_id)} disabled={busy === t.tenant_id} className="inline-flex items-center gap-1 px-2 py-1 bg-white border border-[#16A34A]/30 text-[#16A34A] rounded text-[10px] font-bold hover:bg-[#DCFCE7] disabled:opacity-40"><Rocket size={10} weight="bold" /> Converted</button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default TrialExpiriesTab;
