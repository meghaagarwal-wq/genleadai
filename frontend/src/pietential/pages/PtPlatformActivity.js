import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowsClockwise, EnvelopeOpen, MouseSimple, ChatCircleDots } from '@phosphor-icons/react';
import { ptApi, PageHeader, EmptyState, StageBadge, fmtDate, fmtDateTime } from '../shared';

const PlatformActivity = ({ platform, label, color, accent, icon: Icon, eventLabels }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const load = async () => {
    setLoading(true);
    try {
      const r = await ptApi.get(`/api/pt/${platform}/activity`);
      setData(r.data);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  if (loading) return <div className="text-sm text-[#64748B]">Loading…</div>;
  const rows = data?.rows || [];

  const totals = rows.reduce((acc, r) => ({
    opens: acc.opens + (r.opens || 0),
    clicks: acc.clicks + (r.clicks || 0),
    replies: acc.replies + (r.replies || 0),
    connections: acc.connections + (r.linkedin_connections || 0),
  }), { opens: 0, clicks: 0, replies: 0, connections: 0 });

  return (
    <div data-testid={`pt-${platform}-page`}>
      <PageHeader title={`${label} Activity`}
        subtitle={data?.connected ? `Connected · last sync ${fmtDateTime(data.last_sync_at)}` : `Not connected — ${label} data appears here once you connect or upload via CSV`}
      />

      {/* Top stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <Stat icon={Icon} label="Leads tracked" value={rows.length} accent={accent} />
        {platform === 'saleshandy' ? (
          <>
            <Stat icon={EnvelopeOpen} label="Opens" value={totals.opens} accent={accent} />
            <Stat icon={MouseSimple} label="Clicks" value={totals.clicks} accent={accent} />
            <Stat icon={ChatCircleDots} label="Positive replies" value={totals.replies} accent={accent} />
          </>
        ) : (
          <>
            <Stat icon={ArrowsClockwise} label="Connections" value={totals.connections} accent={accent} />
            <Stat icon={ChatCircleDots} label="DM positive replies" value={totals.replies} accent={accent} />
            <Stat icon={MouseSimple} label="Post engagement" value={totals.clicks} accent={accent} />
          </>
        )}
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title={`No ${label} activity yet`}
          message={`Connect ${label} or upload your campaign CSV to start tracking. Aria scores every signal automatically.`}
        />
      ) : (
        <div className="bg-white border border-[#E2E8F0] rounded-lg overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0]">
              <tr>
                {['Lead', 'Company', 'Title', ...eventLabels, 'Score', 'Stage', 'Last event', 'When'].map(h => (
                  <th key={h} className="px-3 py-2 text-left text-[10px] font-bold uppercase tracking-[0.14em] text-[#64748B]">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.id} onClick={() => navigate(`/pt/leads/${r.id}`)}
                  data-testid={`${platform}-row-${r.id}`}
                  className="border-b border-[#F1F5F9] hover:bg-[#F8FAFC] cursor-pointer">
                  <td className="px-3 py-2.5">
                    <div className="font-semibold text-[#0F172A]">{r.first_name} {r.last_name}</div>
                    <div className="text-xs text-[#64748B]">{r.email}</div>
                  </td>
                  <td className="px-3 py-2.5 text-[#0F172A]">{r.company_name || '—'}</td>
                  <td className="px-3 py-2.5 text-[#475569]">{r.title || '—'}</td>
                  {platform === 'saleshandy' ? (
                    <>
                      <td className="px-3 py-2.5 text-[#475569]">{r.opens || 0}</td>
                      <td className="px-3 py-2.5 text-[#475569]">{r.clicks || 0}</td>
                      <td className="px-3 py-2.5 text-[#475569]">{r.replies || 0}</td>
                    </>
                  ) : (
                    <>
                      <td className="px-3 py-2.5 text-[#475569]">{r.linkedin_connections || 0}</td>
                      <td className="px-3 py-2.5 text-[#475569]">{r.replies || 0}</td>
                      <td className="px-3 py-2.5 text-[#475569]">{r.clicks || 0}</td>
                    </>
                  )}
                  <td className="px-3 py-2.5 font-bold text-[#0F172A]">{r.score ?? 0}</td>
                  <td className="px-3 py-2.5"><StageBadge stage={r.stage} /></td>
                  <td className="px-3 py-2.5 text-[#475569]">{r.last_event_label || '—'}</td>
                  <td className="px-3 py-2.5 text-xs text-[#64748B]">{fmtDate(r.last_event_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

const Stat = ({ icon: Icon, label, value, accent }) => (
  <div className="bg-white border border-[#E2E8F0] rounded-xl p-4">
    <div className="flex items-center gap-2.5">
      <div className="w-8 h-8 rounded-md flex items-center justify-center" style={{ background: `${accent}14`, color: accent }}><Icon size={16} weight="duotone" /></div>
      <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#64748B]">{label}</div>
    </div>
    <div className="mt-2.5 text-3xl font-extrabold text-[#0F172A]" style={{ fontFamily: 'Space Grotesk, Inter' }}>{value}</div>
  </div>
);

export const PtSaleshandy = () => (
  <PlatformActivity platform="saleshandy" label="Saleshandy" color="#7C35DC" accent="#7C35DC" icon={EnvelopeOpen}
    eventLabels={['Opens', 'Clicks', 'Replies']} />
);

export const PtLemlist = () => (
  <PlatformActivity platform="lemlist" label="Lemlist" color="#C044E0" accent="#C044E0" icon={ChatCircleDots}
    eventLabels={['Connections', 'DM replies', 'Post engagement']} />
);

export default PlatformActivity;
