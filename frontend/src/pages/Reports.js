/**
 * Reports — /reports
 *
 * KPI summary · Pipeline funnel · Aria activity · Lead source performance · PDF export.
 */
import React, { useEffect, useState, useMemo } from 'react';
import api from '../config/api';
import { toast } from 'sonner';
import {
  ChartLineUp, Users, Target, CalendarCheck, Trophy, ArrowUpRight, ArrowDownRight,
  Download, ChartBar, ChartPie, Funnel,
} from '@phosphor-icons/react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts';

const PERIOD_LABELS = {
  this_month: 'This Month',
  last_month: 'Last Month',
  last_3_months: 'Last 3 Months',
};

const KPI_META = {
  leads_handled: { label: 'Leads Handled', icon: Users, color: '#7C35DC' },
  qualified: { label: 'Qualified', icon: Target, color: '#C044E0' },
  meetings: { label: 'Meetings Booked', icon: CalendarCheck, color: '#0055FF' },
  won: { label: 'Closed Won', icon: Trophy, color: '#16A34A' },
};

const Reports = () => {
  const [period, setPeriod] = useState('this_month');
  const [summary, setSummary] = useState(null);
  const [funnel, setFunnel] = useState(null);
  const [activity, setActivity] = useState(null);
  const [sources, setSources] = useState(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  const load = async (p) => {
    setLoading(true);
    try {
      const [s, f, a, src] = await Promise.all([
        api.get(`/api/reports/summary?period=${p}`),
        api.get(`/api/reports/funnel?period=${p}`),
        api.get(`/api/reports/activity?period=${p}`),
        api.get(`/api/reports/sources?period=${p}`),
      ]);
      setSummary(s.data);
      setFunnel(f.data);
      setActivity(a.data);
      setSources(src.data);
    } catch (e) { toast.error('Failed to load reports'); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(period); }, [period]);

  const exportPdf = async () => {
    setExporting(true);
    try {
      const r = await api.get(`/api/reports/export?period=${period}`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `aria-report-${period}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success('Report downloaded');
    } catch (e) { toast.error('Export failed'); }
    finally { setExporting(false); }
  };

  const touchpointData = useMemo(() => {
    if (!activity?.touchpoints) return [];
    return [
      { name: 'Sent', value: activity.touchpoints.sent, color: '#16A34A' },
      { name: 'Failed', value: activity.touchpoints.failed, color: '#DC2626' },
      { name: 'Skipped', value: activity.touchpoints.skipped, color: '#D97706' },
    ].filter((d) => d.value > 0);
  }, [activity]);

  const tooltipStyle = { background: '#fff', border: '1px solid #E8E0F5', borderRadius: '12px', color: '#1A0A2E', fontSize: 12, boxShadow: 'var(--shadow-card)' };

  if (loading && !summary) return (
    <div className="flex items-center justify-center h-64">
      <div className="text-sm text-[#9B8AB0]">Loading reports…</div>
    </div>
  );

  return (
    <div className="space-y-6 max-w-[1400px] mx-auto" data-testid="reports-page">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC] mb-1">Aria's Performance</div>
          <h1 className="text-3xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Reports</h1>
          <p className="text-sm text-[#5A4A7A] mt-1">KPI summary, conversion funnel, lead source performance, and downloadable PDF.</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {Object.entries(PERIOD_LABELS).map(([k, lbl]) => (
            <button
              key={k}
              onClick={() => setPeriod(k)}
              data-testid={`period-${k}`}
              className={`px-3 py-2 text-xs font-bold rounded-lg border ${period === k ? 'bg-[#7C35DC] text-white border-[#7C35DC]' : 'bg-white text-[#5A4A7A] border-[#E8E0F5] hover:bg-[#F9F5FF]'}`}
              style={{ fontFamily: 'Plus Jakarta Sans' }}
            >
              {lbl}
            </button>
          ))}
          <button onClick={exportPdf} disabled={exporting} data-testid="export-pdf-btn"
            className="inline-flex items-center gap-1.5 px-3 py-2 btn-gradient rounded-lg text-xs font-bold disabled:opacity-40"
            style={{ fontFamily: 'Plus Jakarta Sans' }}>
            <Download size={12} weight="bold" /> {exporting ? 'Generating…' : 'Export PDF'}
          </button>
        </div>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="kpi-grid">
        {summary && Object.entries(summary.kpis).map(([key, kpi]) => {
          const meta = KPI_META[key];
          const up = kpi.change >= 0;
          return (
            <div key={key} data-testid={`kpi-${key}`}
              className="aria-card-lift bg-white border border-[#E8E0F5] rounded-2xl p-4"
              style={{ boxShadow: 'var(--shadow-card)' }}>
              <div className="flex items-center justify-between mb-3">
                <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-[#9B8AB0]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{meta.label}</span>
                <meta.icon size={18} style={{ color: meta.color }} weight="duotone" />
              </div>
              <div className="text-2xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{kpi.value}</div>
              <div className={`flex items-center gap-1 mt-1 text-[11px] font-bold ${up ? 'text-[#16A34A]' : 'text-[#DC2626]'}`}>
                {up ? <ArrowUpRight size={11} weight="bold" /> : <ArrowDownRight size={11} weight="bold" />}
                {Math.abs(kpi.change)}%
                <span className="text-[#9B8AB0] font-normal ml-1">vs previous</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Funnel */}
      <div className="aria-card-lift bg-white border border-[#E8E0F5] rounded-2xl p-5" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="funnel-chart">
        <div className="flex items-center gap-2 mb-4">
          <Funnel size={18} weight="duotone" className="text-[#7C35DC]" />
          <h2 className="text-base font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Pipeline Funnel</h2>
        </div>
        <div className="space-y-2">
          {(funnel?.stages || []).map((st, i) => {
            const max = funnel.stages[0]?.value || 1;
            const widthPct = max ? Math.max(8, (st.value / max) * 100) : 8;
            const dropOff = st.drop_off;
            return (
              <div key={st.stage} className="flex items-center gap-3" data-testid={`funnel-row-${i}`}>
                <div className="w-40 flex-shrink-0 text-xs font-semibold text-[#5A4A7A]">{st.stage}</div>
                <div className="flex-1 h-9 bg-[#F0ECF9] rounded-lg overflow-hidden relative">
                  <div className="h-full rounded-lg flex items-center px-3 transition-all" style={{ width: `${widthPct}%`, background: `linear-gradient(90deg, #7C35DC ${100 - i * 12}%, #C044E0)` }}>
                    <span className="text-white text-xs font-extrabold">{st.value}</span>
                  </div>
                </div>
                {i > 0 && dropOff > 0 && (
                  <span className="w-16 flex-shrink-0 text-right text-[11px] font-bold text-[#DC2626]">-{dropOff}%</span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Activity charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 aria-card-lift bg-white border border-[#E8E0F5] rounded-2xl p-5" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="daily-chart">
          <div className="flex items-center gap-2 mb-4">
            <ChartBar size={18} weight="duotone" className="text-[#7C35DC]" />
            <h2 className="text-base font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Conversations by Day</h2>
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={activity?.daily_conversations || []}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F0ECF9" vertical={false} />
              <XAxis dataKey="day" tick={{ fill: '#9B8AB0', fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
              <YAxis tick={{ fill: '#9B8AB0', fontSize: 10 }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(124,53,220,0.04)' }} />
              <Bar dataKey="conversations" fill="#7C35DC" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="aria-card-lift bg-white border border-[#E8E0F5] rounded-2xl p-5" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="touchpoint-pie">
          <div className="flex items-center gap-2 mb-4">
            <ChartPie size={18} weight="duotone" className="text-[#7C35DC]" />
            <h2 className="text-base font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Touchpoints</h2>
          </div>
          {touchpointData.length === 0 ? (
            <div className="text-xs text-[#9B8AB0] text-center py-12">No touchpoints fired in this period.</div>
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={touchpointData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} dataKey="value" paddingAngle={3}>
                  {touchpointData.map((d, i) => <Cell key={i} fill={d.color} />)}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={{ fontSize: 11, paddingTop: 8 }} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Source performance */}
      <div className="aria-card-lift bg-white border border-[#E8E0F5] rounded-2xl overflow-hidden" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="source-table">
        <div className="p-5 border-b border-[#E8E0F5]">
          <div className="flex items-center gap-2">
            <ChartLineUp size={18} weight="duotone" className="text-[#7C35DC]" />
            <h2 className="text-base font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Lead Source Performance</h2>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[#F9F5FF]">
              <tr>
                {['Source', 'Leads', 'Qualified', 'Conversion %', 'Won'].map((h) => (
                  <th key={h} className="px-4 py-2.5 text-left text-[10px] font-bold uppercase tracking-[0.15em] text-[#5A4A7A]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(sources?.sources || []).length === 0 ? (
                <tr><td colSpan="5" className="p-8 text-center text-sm text-[#9B8AB0]">No leads in this period</td></tr>
              ) : (sources?.sources || []).map((row, i) => (
                <tr key={i} className="border-t border-[#F0ECF9] hover:bg-[#F9F5FF]" data-testid={`source-row-${i}`}>
                  <td className="px-4 py-3 font-semibold text-[#1A0A2E] capitalize">{(row.source || '—').replace(/_/g, ' ')}</td>
                  <td className="px-4 py-3 text-[#5A4A7A]">{row.leads}</td>
                  <td className="px-4 py-3 text-[#5A4A7A]">{row.qualified}</td>
                  <td className="px-4 py-3"><span className={`px-2 py-0.5 text-[10px] font-bold rounded border ${row.conversion_pct >= 30 ? 'bg-[#DCFCE7] text-[#16A34A] border-[#16A34A]/20' : row.conversion_pct >= 15 ? 'bg-[#FEF3C7] text-[#D97706] border-[#D97706]/20' : 'bg-[#FEE2E2] text-[#DC2626] border-[#DC2626]/20'}`}>{row.conversion_pct}%</span></td>
                  <td className="px-4 py-3 font-bold text-[#16A34A]">{row.won}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default Reports;
