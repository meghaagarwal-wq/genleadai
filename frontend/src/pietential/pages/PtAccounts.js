import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Pause, Buildings, MagnifyingGlass } from '@phosphor-icons/react';
import { ptApi, PageHeader, EmptyState, StageBadge, SequenceBadge, fmtDate } from '../shared';

const PtAccounts = () => {
  const [companies, setCompanies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({ pause_required: '', account_stage: '', q: '' });
  const navigate = useNavigate();

  const load = async () => {
    setLoading(true);
    try {
      const params = {};
      if (filter.pause_required !== '') params.pause_required = filter.pause_required;
      if (filter.account_stage) params.account_stage = filter.account_stage;
      if (filter.q) params.q = filter.q;
      const r = await ptApi.get('/api/pt/companies', { params });
      setCompanies(r.data.companies || []);
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [filter.pause_required, filter.account_stage, filter.q]);

  const pauseCount = companies.filter(c => c.pause_required).length;

  return (
    <div data-testid="pt-accounts-page">
      <PageHeader title="Accounts" subtitle="Account-level engagement intelligence with auto pause-required flag." />

      {pauseCount > 0 && (
        <div className="mb-4 flex items-center gap-3 p-3 rounded-lg border border-[#DC2626]/30" style={{ background: '#FEF2F2' }} data-testid="pt-accounts-pause-banner">
          <Pause size={18} weight="fill" className="text-[#DC2626]" />
          <div className="flex-1">
            <div className="text-xs font-bold uppercase tracking-[0.16em] text-[#DC2626]">Pause required</div>
            <div className="text-sm text-[#0F172A]">{pauseCount} {pauseCount === 1 ? 'account needs' : 'accounts need'} sequence pause. Tasks have been auto-created in <span className="font-semibold">Tasks</span>.</div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="bg-white border border-[#E2E8F0] rounded-lg p-3 flex items-center gap-2 flex-wrap mb-4" data-testid="pt-accounts-filters">
        <div className="relative flex-1 min-w-[200px]">
          <MagnifyingGlass size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#94A3B8]" />
          <input value={filter.q} onChange={(e) => setFilter({ ...filter, q: e.target.value })} placeholder="Search company"
            className="w-full pl-7 pr-3 py-1.5 text-sm border border-[#E2E8F0] rounded-md outline-none" />
        </div>
        <select value={filter.account_stage} onChange={(e) => setFilter({ ...filter, account_stage: e.target.value })}
          data-testid="pt-accounts-filter-stage"
          className="text-sm border border-[#E2E8F0] rounded-md px-2 py-1.5 outline-none">
          <option value="">All stages</option>
          <option value="cold">Cold</option><option value="warm">Warm</option><option value="hot">Hot</option><option value="engaged">Engaged</option><option value="session_pilot">Session/Pilot</option>
        </select>
        <select value={filter.pause_required} onChange={(e) => setFilter({ ...filter, pause_required: e.target.value })}
          data-testid="pt-accounts-filter-pause"
          className="text-sm border border-[#E2E8F0] rounded-md px-2 py-1.5 outline-none">
          <option value="">All accounts</option>
          <option value="true">Pause required</option>
          <option value="false">No pause</option>
        </select>
      </div>

      {loading ? (
        <div className="text-sm text-[#64748B]">Loading…</div>
      ) : companies.length === 0 ? (
        <EmptyState
          title="No accounts mapped yet."
          message="Accounts auto-form when you upload leads or events arrive. Add a few leads to bootstrap accounts."
        />
      ) : (
        <div className="bg-white border border-[#E2E8F0] rounded-lg overflow-x-auto">
          <table className="w-full text-sm" data-testid="pt-accounts-table">
            <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0]">
              <tr>
                {['Company', 'Industry', 'Employees', 'Geography', 'ICP', 'Contacts', 'Highest score', 'Stage', 'Sequence', 'Owner', 'Updated'].map(h => (
                  <th key={h} className="px-3 py-2 text-left text-[10px] font-bold uppercase tracking-[0.14em] text-[#64748B]">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {companies.map(c => (
                <tr key={c.id} onClick={() => navigate(`/pt/leads?company_id=${c.id}`)}
                  data-testid={`account-row-${c.id}`}
                  className="border-b border-[#F1F5F9] hover:bg-[#F8FAFC] cursor-pointer">
                  <td className="px-3 py-2.5">
                    <div className="flex items-center gap-2 font-semibold text-[#0F172A]">
                      <Buildings size={14} weight="duotone" className="text-[#7C35DC]" />
                      {c.name}
                      {c.pause_required && <span className="text-[9px] font-bold uppercase tracking-[0.15em] px-1.5 py-0.5 rounded bg-[#DC2626] text-white">Pause</span>}
                    </div>
                    {c.exec_status && Object.keys(c.exec_status).length > 0 && (
                      <div className="text-[10px] text-[#64748B] mt-0.5">
                        {Object.entries(c.exec_status).slice(0, 3).map(([role, name]) => <span key={role} className="mr-2">{role.toUpperCase()}: {name}</span>)}
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-[#475569]">{c.industry || '—'}</td>
                  <td className="px-3 py-2.5 text-[#475569]">{c.employee_count || '—'}</td>
                  <td className="px-3 py-2.5 text-[#475569]">{c.geography || '—'}</td>
                  <td className="px-3 py-2.5 text-[#475569]">{c.icp_fit || '—'}</td>
                  <td className="px-3 py-2.5 text-[#475569]">{c.contacts_mapped || 0}</td>
                  <td className="px-3 py-2.5 font-bold text-[#0F172A]">{c.highest_score ?? 0}</td>
                  <td className="px-3 py-2.5"><StageBadge stage={c.account_stage} /></td>
                  <td className="px-3 py-2.5"><SequenceBadge status={c.sequence_status} /></td>
                  <td className="px-3 py-2.5 text-[#475569]">{c.owner || '—'}</td>
                  <td className="px-3 py-2.5 text-xs text-[#64748B]">{fmtDate(c.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default PtAccounts;
