import { useEffect, useState } from 'react';
import { ptApi, PageHeader } from '../shared';

const PtSettings = () => {
  const [data, setData] = useState(null);
  useEffect(() => { ptApi.get('/api/pt/scoring-rules').then(r => setData(r.data)).catch(() => {}); }, []);
  if (!data) return <div className="text-sm text-[#64748B]">Loading…</div>;

  return (
    <div data-testid="pt-settings-page">
      <PageHeader title="Settings" subtitle="Scoring rules, stage boundaries, and decay logic." />

      {/* Stage boundaries */}
      <div className="bg-white border border-[#E2E8F0] rounded-lg overflow-hidden mb-4">
        <div className="px-4 py-2.5 bg-[#F8FAFC] border-b border-[#E2E8F0]">
          <h3 className="text-xs font-bold uppercase tracking-[0.16em] text-[#475569]">Stage thresholds</h3>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-[#FAFBFC] border-b border-[#E2E8F0]">
            <tr>
              <th className="px-3 py-1.5 text-left text-[10px] font-bold uppercase tracking-[0.14em] text-[#64748B]">Stage</th>
              <th className="px-3 py-1.5 text-left text-[10px] font-bold uppercase tracking-[0.14em] text-[#64748B]">Range</th>
              <th className="px-3 py-1.5 text-left text-[10px] font-bold uppercase tracking-[0.14em] text-[#64748B]">Automation</th>
            </tr>
          </thead>
          <tbody>
            {data.stages.map(s => (
              <tr key={s.id} className="border-b border-[#F1F5F9] last:border-0">
                <td className="px-3 py-2 font-semibold text-[#0F172A]">{s.label}</td>
                <td className="px-3 py-2 text-[#475569]">{s.min} – {s.max === 9999 ? '∞' : s.max}</td>
                <td className="px-3 py-2 text-[#475569]">{s.auto}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Scoring rules */}
      <div className="bg-white border border-[#E2E8F0] rounded-lg overflow-hidden mb-4">
        <div className="px-4 py-2.5 bg-[#F8FAFC] border-b border-[#E2E8F0]">
          <h3 className="text-xs font-bold uppercase tracking-[0.16em] text-[#475569]">Scoring rules</h3>
        </div>
        <table className="w-full text-sm" data-testid="pt-settings-rules">
          <thead className="bg-[#FAFBFC] border-b border-[#E2E8F0]">
            <tr>
              {['Source', 'Event', 'Score', 'Triggers pause'].map(h => <th key={h} className="px-3 py-1.5 text-left text-[10px] font-bold uppercase tracking-[0.14em] text-[#64748B]">{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {data.rules.map(r => (
              <tr key={r.event_type} className="border-b border-[#F1F5F9] last:border-0">
                <td className="px-3 py-2 text-[#475569]">{r.source}</td>
                <td className="px-3 py-2 text-[#0F172A]"><span className="font-medium">{r.label}</span> <span className="text-[10px] text-[#94A3B8] font-mono ml-1">{r.event_type}</span></td>
                <td className={`px-3 py-2 font-bold ${r.score >= 0 ? 'text-[#0F766E]' : 'text-[#DC2626]'}`}>{r.score >= 0 ? '+' : ''}{r.score}</td>
                <td className="px-3 py-2 text-[#475569]">{r.trigger_pause ? 'Yes' : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Decay */}
      <div className="bg-white border border-[#E2E8F0] rounded-lg overflow-hidden">
        <div className="px-4 py-2.5 bg-[#F8FAFC] border-b border-[#E2E8F0]">
          <h3 className="text-xs font-bold uppercase tracking-[0.16em] text-[#475569]">Score decay</h3>
        </div>
        <div className="p-4 space-y-2">
          {data.decay.map((d, i) => (
            <div key={i} className="flex items-center justify-between text-sm">
              <span className="text-[#475569]">{d.trigger.replace(/_/g, ' ')}</span>
              <span className={`font-bold ${d.score_change >= 0 ? 'text-[#0F766E]' : 'text-[#DC2626]'}`}>{d.score_change}{d.side_effect && <span className="text-xs text-[#94A3B8] ml-2">+ {d.side_effect.replace(/_/g, ' ')}</span>}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-4 text-xs text-[#94A3B8]">
        Editable scoring rules will be available in a future iteration. Today's values match Pietential's touchpoint roadmap.
      </div>
    </div>
  );
};

export default PtSettings;
