import { useEffect, useState } from 'react';
import { Pulse, CheckCircle, Warning, XCircle, Funnel } from '@phosphor-icons/react';
import { ptApi, PageHeader, EmptyState, fmtDateTime } from '../shared';

const KIND_META = {
  webhook:    { label: 'Webhook',     color: '#7C35DC' },
  sync:       { label: 'Manual sync', color: '#C044E0' },
  csv_import: { label: 'CSV import',  color: '#F59E0B' },
  decay:      { label: 'Decay',       color: '#94A3B8' },
  rule:       { label: 'Rule',        color: '#475569' },
};

const LEVEL_ICON = { info: CheckCircle, warn: Warning, error: XCircle };
const LEVEL_COLOR = { info: '#16A34A', warn: '#F59E0B', error: '#DC2626' };

const PtAutomationLogs = () => {
  const [data, setData] = useState({ logs: [], counts: { total: 0, by_kind: {}, errors: 0 } });
  const [loading, setLoading] = useState(true);
  const [kindFilter, setKindFilter] = useState('');
  const [levelFilter, setLevelFilter] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const params = {};
      if (kindFilter) params.kind = kindFilter;
      if (levelFilter) params.level = levelFilter;
      const r = await ptApi.get('/api/pt/logs', { params });
      setData(r.data);
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [kindFilter, levelFilter]);

  return (
    <div data-testid="pt-logs-page">
      <PageHeader title="Automation Logs" subtitle="Every webhook, sync, decay run, and CSV import. The receipts." />

      {/* Counts */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mb-4" data-testid="pt-logs-counts">
        <Stat label="Total" value={data.counts.total} color="#7C35DC" />
        {Object.entries(KIND_META).map(([k, m]) => (
          <Stat key={k} label={m.label} value={data.counts.by_kind?.[k] || 0} color={m.color} />
        ))}
      </div>

      <div className="flex items-center gap-2 mb-4 flex-wrap" data-testid="pt-logs-filters">
        <Funnel size={14} className="text-[#64748B]" weight="duotone" />
        <select value={kindFilter} onChange={(e) => setKindFilter(e.target.value)} data-testid="pt-logs-filter-kind"
          className="text-sm border border-[#E2E8F0] rounded-md px-2 py-1.5">
          <option value="">All kinds</option>
          {Object.entries(KIND_META).map(([k, m]) => <option key={k} value={k}>{m.label}</option>)}
        </select>
        <select value={levelFilter} onChange={(e) => setLevelFilter(e.target.value)} data-testid="pt-logs-filter-level"
          className="text-sm border border-[#E2E8F0] rounded-md px-2 py-1.5">
          <option value="">All levels</option>
          <option value="info">Info</option>
          <option value="warn">Warning</option>
          <option value="error">Error</option>
        </select>
      </div>

      {loading ? (
        <div className="text-sm text-[#64748B]">Loading…</div>
      ) : data.logs.length === 0 ? (
        <EmptyState title="No automation activity yet" message="Aria's logs will fill in here as webhooks fire, CSVs import, and decay runs nightly." />
      ) : (
        <div className="bg-white border border-[#E2E8F0] rounded-lg overflow-hidden" data-testid="pt-logs-table">
          {data.logs.map(log => {
            const kindMeta = KIND_META[log.kind] || { label: log.kind, color: '#475569' };
            const Icon = LEVEL_ICON[log.level] || Pulse;
            const color = LEVEL_COLOR[log.level] || '#94A3B8';
            return (
              <div key={log.id} className="flex items-start gap-3 px-4 py-3 border-b border-[#F1F5F9] last:border-0" data-testid={`log-${log.id}`}>
                <Icon size={14} weight="fill" style={{ color }} className="mt-0.5 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[10px] font-bold uppercase tracking-[0.14em] px-1.5 py-0.5 rounded-md text-white" style={{ background: kindMeta.color }}>{kindMeta.label}</span>
                    <span className="text-sm text-[#0F172A]">{log.message}</span>
                  </div>
                  <div className="text-[10px] text-[#94A3B8] mt-0.5">{fmtDateTime(log.created_at)}</div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

const Stat = ({ label, value, color }) => (
  <div className="bg-white border border-[#E2E8F0] rounded-lg p-3">
    <div className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#64748B]">{label}</div>
    <div className="text-2xl font-extrabold mt-1" style={{ color, fontFamily: 'Space Grotesk, Inter' }}>{value}</div>
  </div>
);

export default PtAutomationLogs;
