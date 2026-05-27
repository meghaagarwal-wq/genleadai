import { useEffect, useState } from 'react';
import { ptApi, PageHeader } from '../shared';

const TABS = [
  { id: 'funnel',  label: 'Funnel · last 30 days' },
  { id: 'weekly',  label: 'Weekly · last 7 days' },
  { id: 'monthly', label: 'Monthly · last 30 days' },
  { id: 'matrix',  label: 'ICP × Channel matrix' },  // iter108 P2
];

const SIGNAL_LABELS = {
  deal_closed:       'Deal closed',
  funding_round:     'Funding round',
  event_attending:   'Event',
  job_change:        'Job change',
  hiring_signal:     'Hiring',
  content_published: 'Content published',
  company_news:      'Company news',
  social_activity:   'Social activity',
};

const PtReports = () => {
  const [tab, setTab] = useState('funnel');
  const [funnel, setFunnel] = useState(null);
  const [weekly, setWeekly] = useState(null);
  const [monthly, setMonthly] = useState(null);
  const [matrix, setMatrix] = useState(null);  // iter108 P2

  useEffect(() => {
    ptApi.get('/api/pt/reports/funnel?days=30').then(r => setFunnel(r.data)).catch(() => {});
    ptApi.get('/api/pt/reports/weekly').then(r => setWeekly(r.data)).catch(() => {});
    ptApi.get('/api/pt/reports/monthly').then(r => setMonthly(r.data)).catch(() => {});
    ptApi.get('/api/reports/icp-channel-matrix?period=this_month').then(r => setMatrix(r.data)).catch(() => {});
  }, []);

  return (
    <div data-testid="pt-reports-page">
      <PageHeader title="Reports" subtitle="Plain operational reporting. Real numbers only." />

      <div className="flex items-center gap-2 mb-4 border-b border-[#E2E8F0]">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} data-testid={`pt-reports-tab-${t.id}`}
            className={`px-3 py-2 text-sm font-semibold border-b-2 -mb-px ${tab === t.id ? 'border-[#7C35DC] text-[#7C35DC]' : 'border-transparent text-[#64748B] hover:text-[#0F172A]'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'funnel' && (funnel ? <FunnelTab funnel={funnel} /> : <Loading testid="pt-reports-funnel-loading" />)}

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

      {tab === 'matrix' && (matrix ? <IcpChannelMatrix matrix={matrix} /> : <Loading testid="pt-reports-matrix-loading" />)}
    </div>
  );
};

// iter108 P2 — ICP × Channel cross-tab. Shows where HOT leads actually come from.
const IcpChannelMatrix = ({ matrix }) => {
  const { rows, cols, cells, totals_by_row, totals_by_col, grand_total } = matrix;
  const tierColors = {
    hot:  { bg: '#FEE2E2', fg: '#B91C1C' },
    warm: { bg: '#FEF3C7', fg: '#92400E' },
    cold: { bg: '#E0E7FF', fg: '#3730A3' },
  };
  if (!cols.length) {
    return (
      <div className="bg-white border border-[#E2E8F0] rounded-lg p-8 text-center text-sm text-[#64748B]" data-testid="pt-reports-matrix-empty">
        No lead data in the current period yet — start an import or create leads to see this matrix.
      </div>
    );
  }
  return (
    <div className="bg-white border border-[#E2E8F0] rounded-lg overflow-hidden" data-testid="pt-reports-matrix">
      <div className="px-4 py-3 border-b border-[#E2E8F0] text-sm font-bold text-[#0F172A]">
        ICP tier × source channel · {matrix.period.replace(/_/g, ' ')}
        <span className="ml-2 text-xs text-[#64748B] font-normal">leads · qualified · won (conv %)</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm" data-testid="pt-reports-matrix-table">
          <thead className="bg-[#FAFAFA] text-[#64748B] text-[10px] uppercase tracking-[0.14em] font-bold">
            <tr>
              <th className="px-3 py-2 text-left">Tier ↓ · Channel →</th>
              {cols.map(c => (
                <th key={c} className="px-3 py-2 text-left whitespace-nowrap">{c.replace(/_/g, ' ')}</th>
              ))}
              <th className="px-3 py-2 text-left bg-[#F4F0FF]">Total</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(tier => (
              <tr key={tier} className="border-t border-[#E2E8F0]">
                <td className="px-3 py-2 font-bold" style={{ background: tierColors[tier].bg, color: tierColors[tier].fg }}>
                  {tier.toUpperCase()}
                </td>
                {cols.map(c => {
                  const v = (cells[tier] || {})[c];
                  return (
                    <td key={c} className="px-3 py-2 text-xs text-[#0F172A]" data-testid={`pt-reports-matrix-cell-${tier}-${c}`}>
                      {v ? `${v.leads} · ${v.qualified} · ${v.won} (${v.conversion_pct}%)` : '—'}
                    </td>
                  );
                })}
                <td className="px-3 py-2 text-xs font-bold text-[#0F172A] bg-[#F4F0FF]">
                  {totals_by_row[tier].leads} · {totals_by_row[tier].qualified} · {totals_by_row[tier].won} ({totals_by_row[tier].conversion_pct}%)
                </td>
              </tr>
            ))}
            <tr className="border-t-2 border-[#7C35DC] bg-[#FAF7FF]">
              <td className="px-3 py-2 font-extrabold text-[#7C35DC]">TOTAL</td>
              {cols.map(c => {
                const v = totals_by_col[c];
                return (
                  <td key={c} className="px-3 py-2 text-xs font-bold text-[#0F172A]">
                    {v.leads} · {v.qualified} · {v.won} ({v.conversion_pct}%)
                  </td>
                );
              })}
              <td className="px-3 py-2 text-xs font-extrabold text-[#7C35DC]">
                {grand_total.leads} · {grand_total.qualified} · {grand_total.won} ({grand_total.conversion_pct}%)
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
};

// ─── Funnel tab ────────────────────────────────────────────────────────
const FunnelTab = ({ funnel }) => {
  const stages = funnel.funnel || [];
  const maxCount = Math.max(...stages.map(s => s.count), 1);
  const conv = funnel.conversion || {};
  const sigTotals = funnel.signal_totals || {};
  const breakdown = funnel.signal_breakdown || [];
  const maxSig = Math.max(...breakdown.map(s => s.total), 1);

  return (
    <div className="space-y-6" data-testid="pt-reports-funnel">
      {/* Top headline tiles */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Tile label="Total leads" value={funnel.total_leads || 0} hint="across all stages" />
        <Tile
          label="New in window"
          value={conv.new_leads_in_window || 0}
          hint={`last ${funnel.window_days || 30} days`}
        />
        <Tile
          label="Progression rate"
          value={`${conv.progression_rate ?? 0}%`}
          hint={`${conv.progressed_to_hot_or_above || 0} reached hot+`}
        />
        <Tile
          label="Signal action rate"
          value={`${sigTotals.action_rate ?? 0}%`}
          hint={`${sigTotals.actioned || 0}/${sigTotals.total || 0} actioned`}
        />
      </div>

      {/* Lead funnel chart */}
      <div className="bg-white border border-[#E2E8F0] rounded-lg overflow-hidden">
        <div className="px-4 py-2.5 border-b border-[#E2E8F0] bg-[#F8FAFC]">
          <h3 className="text-xs font-bold uppercase tracking-[0.16em] text-[#475569]">
            Lead funnel · current snapshot
          </h3>
        </div>
        <div className="p-4 space-y-2" data-testid="pt-reports-funnel-chart">
          {stages.map(s => (
            <div key={s.stage} className="flex items-center gap-3" data-testid={`pt-reports-funnel-row-${s.stage}`}>
              <div className="w-32 text-xs font-semibold text-[#475569] uppercase tracking-wide">
                {s.stage.replace(/_/g, ' ')}
              </div>
              <div className="flex-1 bg-[#F1F5F9] rounded h-7 relative overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-[#7C35DC] to-[#C044E0] transition-all"
                  style={{ width: `${Math.max(2, Math.round((s.count / maxCount) * 100))}%` }}
                />
                <div className="absolute inset-0 flex items-center px-3">
                  <span className="text-xs font-bold text-[#0F172A]">{s.count}</span>
                </div>
              </div>
            </div>
          ))}
          {stages.every(s => s.count === 0) && (
            <div className="text-sm text-[#64748B] py-3">
              No leads yet. Import or sync prospects to populate the funnel.
            </div>
          )}
        </div>
      </div>

      {/* Signal-type breakdown */}
      <div className="bg-white border border-[#E2E8F0] rounded-lg overflow-hidden">
        <div className="px-4 py-2.5 border-b border-[#E2E8F0] bg-[#F8FAFC]">
          <h3 className="text-xs font-bold uppercase tracking-[0.16em] text-[#475569]">
            Signal breakdown · last {funnel.window_days || 30} days
          </h3>
        </div>
        <div className="p-4" data-testid="pt-reports-signal-breakdown">
          {breakdown.length === 0 ? (
            <div className="text-sm text-[#64748B] py-2">
              No insight signals classified yet. The B2B Insights cron runs daily —
              or hit “Run scan now” on the Intelligence Feed page.
            </div>
          ) : (
            <div className="space-y-2">
              {breakdown.map(row => (
                <div key={row.signal_type} className="flex items-center gap-3" data-testid={`pt-reports-signal-row-${row.signal_type}`}>
                  <div className="w-40 text-xs font-semibold text-[#475569]">
                    {SIGNAL_LABELS[row.signal_type] || row.signal_type}
                  </div>
                  <div className="flex-1 bg-[#F1F5F9] rounded h-6 relative overflow-hidden">
                    <div
                      className="h-full bg-violet-200"
                      style={{ width: `${Math.max(2, Math.round((row.total / maxSig) * 100))}%` }}
                    />
                    <div
                      className="absolute top-0 left-0 h-full bg-violet-500"
                      style={{ width: `${Math.max(0, Math.round((row.actioned / maxSig) * 100))}%` }}
                    />
                    <div className="absolute inset-0 flex items-center px-3 gap-2">
                      <span className="text-xs font-bold text-[#0F172A]">{row.total}</span>
                      <span className="text-xs text-emerald-700">
                        {row.actioned} acted · {row.action_rate}%
                      </span>
                    </div>
                  </div>
                </div>
              ))}
              <div className="flex items-center gap-3 text-[10px] text-[#64748B] pt-2">
                <span className="inline-flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-sm bg-violet-500 inline-block" /> actioned
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-sm bg-violet-200 inline-block" /> total signals
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Conversion to sessions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <Tile
          label="Sessions booked"
          value={conv.sessions_booked || 0}
          hint={`last ${funnel.window_days || 30} days`}
        />
        <Tile
          label="Lead → session rate"
          value={`${conv.leads_to_session_rate ?? 0}%`}
          hint="of new leads in window"
        />
        <Tile
          label="Signals classified"
          value={sigTotals.total || 0}
          hint="from B2B Insights"
        />
      </div>
    </div>
  );
};

const Loading = ({ testid }) => (
  <div className="text-sm text-[#64748B] p-4" data-testid={testid || 'loading'}>Loading…</div>
);

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
