import { useEffect, useState } from 'react';
import { ptApi, PageHeader } from '../shared';

const TABS = [
  { id: 'weekly', label: 'Weekly · last 7 days' },
  { id: 'monthly', label: 'Monthly · last 30 days' },
];

const PtReports = () => {
  const [tab, setTab] = useState('weekly');
  const [weekly, setWeekly] = useState(null);
  const [monthly, setMonthly] = useState(null);

  useEffect(() => {
    ptApi.get('/api/pt/reports/weekly').then(r => setWeekly(r.data)).catch(() => {});
    ptApi.get('/api/pt/reports/monthly').then(r => setMonthly(r.data)).catch(() => {});
  }, []);

  return (
    <div data-testid="pt-reports-page">
      <PageHeader title="Reports" subtitle="Plain operational reporting. Real numbers only." />

      <div className="flex items-center gap-2 mb-4 border-b border-[#E2E8F0]">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} data-testid={`pt-reports-tab-${t.id}`}
            className={`px-3 py-2 text-sm font-semibold border-b-2 -mb-px ${tab === t.id ? 'border-[#0F766E] text-[#0F766E]' : 'border-transparent text-[#64748B] hover:text-[#0F172A]'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'weekly' && weekly && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3" data-testid="pt-reports-weekly-grid">
          {Object.entries(weekly.metrics || {}).map(([k, v]) => (
            <div key={k} className="bg-white border border-[#E2E8F0] rounded-lg p-4">
              <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#64748B]">{k.replace(/_/g, ' ')}</div>
              <div className="text-3xl font-extrabold text-[#0F172A] mt-2" style={{ fontFamily: 'Space Grotesk, Inter' }}>{v}</div>
            </div>
          ))}
        </div>
      )}

      {tab === 'monthly' && monthly && (
        <div className="space-y-4" data-testid="pt-reports-monthly">
          <Section title="Channel performance" rows={monthly.channel_performance || []} keys={['source', 'events', 'score_total']} />
          <Section title="Title performance (top 20)" rows={monthly.title_performance || []} keys={['title', 'events']} />
          <Section title="Industry performance" rows={monthly.industry_performance || []} keys={['industry', 'events']} />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <Tile label="Best touchpoint" value={monthly.best_touchpoint?.event_type || '—'} hint={monthly.best_touchpoint ? `${monthly.best_touchpoint.events} events` : ''} />
            <Tile label="Accounts moved to John" value={monthly.accounts_to_john || 0} />
            <Tile label="Sessions created" value={monthly.sessions_created || 0} />
          </div>
        </div>
      )}
    </div>
  );
};

const Tile = ({ label, value, hint }) => (
  <div className="bg-white border border-[#E2E8F0] rounded-lg p-4">
    <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#64748B]">{label}</div>
    <div className="text-2xl font-extrabold text-[#0F172A] mt-1.5" style={{ fontFamily: 'Space Grotesk, Inter' }}>{value}</div>
    {hint && <div className="text-xs text-[#94A3B8] mt-1">{hint}</div>}
  </div>
);

const Section = ({ title, rows, keys }) => (
  <div className="bg-white border border-[#E2E8F0] rounded-lg overflow-hidden">
    <div className="px-4 py-2.5 border-b border-[#E2E8F0] bg-[#F8FAFC]">
      <h3 className="text-xs font-bold uppercase tracking-[0.16em] text-[#475569]">{title}</h3>
    </div>
    {rows.length === 0 ? (
      <div className="p-4 text-sm text-[#64748B]">No data yet for this window.</div>
    ) : (
      <table className="w-full text-sm">
        <thead className="bg-[#FAFBFC] border-b border-[#E2E8F0]">
          <tr>{keys.map(k => <th key={k} className="px-3 py-1.5 text-left text-[10px] font-bold uppercase tracking-[0.14em] text-[#64748B]">{k.replace(/_/g, ' ')}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-[#F1F5F9] last:border-0">
              {keys.map(k => <td key={k} className="px-3 py-2 text-[#0F172A]">{r[k] ?? '—'}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    )}
  </div>
);

export default PtReports;
