import React, { useEffect, useState } from 'react';
import api from '../config/api';
import { toast } from 'sonner';
import { DownloadSimple, MagnifyingGlass, Shield } from '@phosphor-icons/react';

const fmt = (iso) => { try { return new Date(iso).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }); } catch { return '—'; } };

const ACTION_COLOR = (a) => {
  if (a.startsWith('lead.data_purged') || a.startsWith('workspace.deleted')) return 'bg-[#FEE2E2] text-[#DC2626] border-[#DC2626]/30';
  if (a.startsWith('crm.') || a.startsWith('member.')) return 'bg-[#F4F0FF] text-[#7C35DC] border-[#7C35DC]/30';
  if (a.startsWith('trial.') || a.startsWith('plan.')) return 'bg-[#FEF3C7] text-[#D97706] border-[#D97706]/30';
  return 'bg-[#F1F5F9] text-[#5A4A7A] border-[#94A3B8]/30';
};

const AuditLogPanel = () => {
  const [data, setData] = useState({ entries: [], total: 0, known_actions: [] });
  const [filter, setFilter] = useState({ action: '', user_email: '' });
  const [expanded, setExpanded] = useState({});

  const load = () => {
    const params = {};
    if (filter.action) params.action = filter.action;
    if (filter.user_email) params.user_email = filter.user_email;
    api.get('/api/audit-log', { params })
      .then((r) => setData(r.data))
      .catch((e) => {
        if (e.response?.status === 403) toast.error('Owner/Admin only');
        else toast.error('Could not load audit log');
      });
  };
  useEffect(load, [filter]);

  const exportCsv = async () => {
    try {
      const r = await api.get('/api/audit-log/export.csv', { responseType: 'blob' });
      const blob = new Blob([r.data], { type: 'text/csv' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `aria-audit-log-${new Date().toISOString().slice(0, 10)}.csv`;
      a.click(); URL.revokeObjectURL(a.href);
    } catch { toast.error('Export failed'); }
  };

  return (
    <div className="bg-white border border-[#E8E0F5] rounded-xl" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="audit-log-panel">
      <div className="px-5 py-4 border-b border-[#E8E0F5] flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <Shield size={16} weight="duotone" className="text-[#7C35DC]" />
          <h3 className="font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Audit Log <span className="text-[#9B8AB0] font-normal text-sm ml-1">({data.total})</span></h3>
        </div>
        <div className="flex items-center gap-2">
          <select data-testid="audit-action-filter" value={filter.action} onChange={(e) => setFilter({ ...filter, action: e.target.value })} className="bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-1.5 rounded-lg text-sm">
            <option value="">All actions</option>
            {data.known_actions.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
          <button onClick={exportCsv} data-testid="audit-export-btn" className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-[#7C35DC]/30 text-[#7C35DC] rounded-lg text-xs font-bold hover:bg-[#F4F0FF]">
            <DownloadSimple size={12} weight="bold" /> Export CSV
          </button>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[#F4F0FF]">
            <tr>
              {['Time', 'User', 'Action', 'Resource', 'IP', ''].map((h) => (
                <th key={h} className="px-4 py-2.5 text-left text-[10px] font-bold uppercase tracking-[0.15em] text-[#5A4A7A]">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.entries.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-10 text-center text-[#9B8AB0]">No audit events yet — actions will appear here as they happen.</td></tr>
            ) : data.entries.map((e) => (
              <React.Fragment key={e.id}>
                <tr className="border-b border-[#F0ECF9] hover:bg-[#FAF7FF]" data-testid={`audit-row-${e.id}`}>
                  <td className="px-4 py-2 text-[#5A4A7A] text-xs">{fmt(e.created_at)}</td>
                  <td className="px-4 py-2 text-[#5A4A7A] text-xs font-mono">{e.user_id || '—'}</td>
                  <td className="px-4 py-2"><span className={`px-2 py-0.5 text-[10px] font-bold uppercase rounded border ${ACTION_COLOR(e.action)} font-mono`}>{e.action}</span></td>
                  <td className="px-4 py-2 text-[#5A4A7A] text-xs font-mono">{e.resource_type ? `${e.resource_type}/${(e.resource_id || '').slice(0, 12)}` : '—'}</td>
                  <td className="px-4 py-2 text-[#9B8AB0] text-xs font-mono">{e.ip_address || '—'}</td>
                  <td className="px-4 py-2">
                    {Object.keys(e.metadata || {}).length > 0 && (
                      <button onClick={() => setExpanded({ ...expanded, [e.id]: !expanded[e.id] })} className="text-xs font-bold text-[#7C35DC] hover:underline">{expanded[e.id] ? 'Hide' : 'Details'}</button>
                    )}
                  </td>
                </tr>
                {expanded[e.id] && (
                  <tr className="border-b border-[#F0ECF9] bg-[#FAF7FF]">
                    <td colSpan={6} className="px-4 py-2">
                      <pre className="text-[11px] text-[#5A4A7A] font-mono whitespace-pre-wrap">{JSON.stringify(e.metadata || {}, null, 2)}</pre>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default AuditLogPanel;
