import React, { useState, useEffect } from 'react';
import api from '../config/api';
import { ClockCounterClockwise, Download } from '@phosphor-icons/react';

const AuditLog = () => {
  const [entries, setEntries] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);

  useEffect(() => { fetchLog(); }, [page]);
  const fetchLog = async () => {
    setLoading(true);
    try { const res = await api.get(`/api/audit-log?skip=${page * 50}&limit=50`); setEntries(res.data.entries); setTotal(res.data.total); }
    catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const actionColor = (action) => {
    if (action?.includes('create') || action?.includes('add')) return 'text-[#16A34A]';
    if (action?.includes('delete') || action?.includes('remove')) return 'text-[#DC2626]';
    if (action?.includes('update') || action?.includes('edit')) return 'text-[#D97706]';
    return 'text-[#7C35DC]';
  };

  return (
    <div data-testid="audit-log-page" className="space-y-6 max-w-[1200px] mx-auto">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#F4F0FF] flex items-center justify-center border border-[#E0D4F7]">
            <ClockCounterClockwise size={22} className="text-[#7C35DC]" weight="duotone" />
          </div>
          <div>
            <h1 className="text-3xl font-extrabold text-[#1A0A2E] tracking-tight" style={{ fontFamily: 'Plus Jakarta Sans' }}>Audit Log</h1>
            <p className="text-sm text-[#5A4A7A] mt-0.5">Full activity trail for compliance and review</p>
          </div>
        </div>
      </div>

      <div className="bg-white border border-[#E8E0F5] rounded-xl overflow-hidden" style={{ boxShadow: 'var(--shadow-card)' }}>
        {loading ? <div className="p-12 text-center text-[#9B8AB0]">Loading...</div> : entries.length === 0 ? (
          <div className="p-12 text-center text-[#9B8AB0]">No audit entries yet</div>
        ) : (
          <>
            <table className="w-full text-sm text-left">
              <thead>
                <tr className="bg-[#F9F5FF]">
                  {['Timestamp', 'User', 'Action', 'Resource', 'Details'].map(h => (
                    <th key={h} className="px-4 py-3 text-[10px] font-bold uppercase tracking-[0.15em] text-[#5A4A7A]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {entries.map((entry, i) => (
                  <tr key={i} className="border-b border-[#F0ECF9] hover:bg-[#F9F5FF] transition-colors">
                    <td className="px-4 py-3 text-xs font-mono text-[#9B8AB0]">{new Date(entry.timestamp).toLocaleString()}</td>
                    <td className="px-4 py-3 text-sm text-[#1A0A2E]">{entry.user_email}</td>
                    <td className="px-4 py-3"><span className={`text-sm font-semibold ${actionColor(entry.action)}`}>{entry.action}</span></td>
                    <td className="px-4 py-3 text-sm text-[#5A4A7A]">{entry.resource_type}</td>
                    <td className="px-4 py-3 text-xs text-[#9B8AB0] max-w-xs truncate">{entry.details}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="px-4 py-3 border-t border-[#E8E0F5] flex items-center justify-between">
              <span className="text-xs text-[#9B8AB0]">{total} total entries</span>
              <div className="flex gap-2">
                <button onClick={() => setPage(Math.max(0, page - 1))} disabled={page === 0} className="px-3 py-1 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-lg text-xs disabled:opacity-30">Prev</button>
                <button onClick={() => setPage(page + 1)} disabled={(page + 1) * 50 >= total} className="px-3 py-1 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-lg text-xs disabled:opacity-30">Next</button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default AuditLog;
