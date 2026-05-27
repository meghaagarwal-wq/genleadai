import { useEffect, useState } from 'react';
import { Megaphone, EnvelopeOpen, LinkedinLogo } from '@phosphor-icons/react';
import { ptApi, PageHeader, EmptyState, fmtDate } from '../shared';

const PtCampaigns = () => {
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');

  useEffect(() => {
    setLoading(true);
    const params = filter ? { platform: filter } : {};
    ptApi.get('/api/pt/campaigns', { params }).then(r => setCampaigns(r.data.campaigns || [])).catch(() => {}).finally(() => setLoading(false));
  }, [filter]);

  return (
    <div data-testid="pt-campaigns-page">
      <PageHeader title="Campaigns" subtitle="Saleshandy and Lemlist campaigns rolled up — every campaign synced or imported lives here." />

      <div className="flex items-center gap-2 mb-4" data-testid="pt-campaigns-filters">
        <button onClick={() => setFilter('')} data-testid="pt-camp-filter-all"
          className={`px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-[0.15em] ${filter === '' ? 'bg-[#7C35DC] text-white' : 'bg-white text-[#475569] border border-[#E2E8F0]'}`}>
          All
        </button>
        <button onClick={() => setFilter('saleshandy')} data-testid="pt-camp-filter-saleshandy"
          className={`px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-[0.15em] ${filter === 'saleshandy' ? 'bg-[#7C35DC] text-white' : 'bg-white text-[#475569] border border-[#E2E8F0]'}`}>
          Saleshandy
        </button>
        <button onClick={() => setFilter('lemlist')} data-testid="pt-camp-filter-lemlist"
          className={`px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-[0.15em] ${filter === 'lemlist' ? 'bg-[#C044E0] text-white' : 'bg-white text-[#475569] border border-[#E2E8F0]'}`}>
          Lemlist
        </button>
      </div>

      {loading ? (
        <div className="text-sm text-[#64748B]">Loading…</div>
      ) : campaigns.length === 0 ? (
        <EmptyState
          title="No campaigns yet"
          message="Import a Saleshandy or Lemlist CSV from their respective pages — Aria will roll up campaigns automatically."
        />
      ) : (
        <div className="bg-white border border-[#E2E8F0] rounded-lg overflow-x-auto" data-testid="pt-campaigns-table">
          <table className="w-full text-sm">
            <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0]">
              <tr>
                {['Platform', 'Campaign', 'Status', 'Leads', 'Opens', 'Clicks', 'Connections', '+ve replies', 'Updated'].map(h => (
                  <th key={h} className="px-3 py-2 text-left text-[10px] font-bold uppercase tracking-[0.14em] text-[#64748B]">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {campaigns.map(c => (
                <tr key={c.id} className="border-b border-[#F1F5F9] last:border-0 hover:bg-[#F8FAFC]" data-testid={`campaign-${c.id}`}>
                  <td className="px-3 py-2.5">
                    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-[0.12em] text-white"
                      style={{ background: c.platform === 'saleshandy' ? '#7C35DC' : '#C044E0' }}>
                      {c.platform === 'saleshandy' ? <EnvelopeOpen size={11} weight="fill" /> : <LinkedinLogo size={11} weight="fill" />}
                      {c.platform}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 font-semibold text-[#0F172A]">
                    <Megaphone size={12} weight="duotone" className="inline mr-1.5 text-[#7C35DC]" />{c.campaign_name}
                  </td>
                  <td className="px-3 py-2.5 text-[#475569]">{c.status}</td>
                  <td className="px-3 py-2.5 text-[#0F172A] font-bold">{c.lead_count ?? 0}</td>
                  <td className="px-3 py-2.5 text-[#475569]">{c.opens ?? 0}</td>
                  <td className="px-3 py-2.5 text-[#475569]">{c.clicks ?? 0}</td>
                  <td className="px-3 py-2.5 text-[#475569]">{c.connections ?? 0}</td>
                  <td className="px-3 py-2.5 text-[#7C35DC] font-bold">{c.replies_pos ?? 0}</td>
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

export default PtCampaigns;
