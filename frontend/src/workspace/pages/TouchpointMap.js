import { useEffect, useState } from 'react';
import { MapTrifold } from '@phosphor-icons/react';
import { ptApi, PageHeader } from '../shared';

const PtTouchpointMap = ({ embedded = false }) => {
  const [tps, setTps] = useState([]);
  useEffect(() => { ptApi.get('/api/pt/touchpoints').then(r => setTps(r.data.touchpoints || [])).catch(() => {}); }, []);

  return (
    <div data-testid="pt-touchpoint-map-page">
      {!embedded && <PageHeader title="Touchpoint Map" subtitle="The 10 ways prospects engage — and what Aria does at each step." />}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3" data-testid="pt-touchpoints-grid">
        {tps.map((tp, i) => (
          <div key={tp.id} className="bg-white border border-[#E2E8F0] rounded-xl p-4" data-testid={`touchpoint-${tp.id}`}>
            <div className="flex items-start gap-3 mb-2">
              <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: '#7C35DC14', color: '#7C35DC' }}>
                <MapTrifold size={16} weight="duotone" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#94A3B8]">{String(i + 1).padStart(2, '0')}</span>
                  <h3 className="text-sm font-bold text-[#0F172A]" style={{ fontFamily: 'Space Grotesk, Inter' }}>{tp.title}</h3>
                </div>
                <div className="text-[10px] uppercase tracking-[0.14em] text-[#7C35DC] mt-0.5">{tp.platform}</div>
              </div>
              {tp.live_event_count > 0 && (
                <span className="text-[10px] font-bold uppercase tracking-[0.14em] px-1.5 py-0.5 rounded-md text-white" style={{ background: '#7C35DC' }}>
                  {tp.live_event_count} live
                </span>
              )}
            </div>
            <div className="grid grid-cols-3 gap-2 text-xs mt-3">
              <KV label="Touches" value={tp.touches} />
              <KV label="Timeline" value={tp.timeline} />
              <KV label="No reply →" value={tp.fallback} />
            </div>
            <div className="mt-3 pt-3 border-t border-[#F1F5F9]">
              <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#64748B] mb-1">Aria's role</div>
              <div className="text-xs text-[#475569]">{tp.aria_role}</div>
            </div>
            {tp.events && tp.events.length > 0 && (
              <div className="mt-2 flex items-center gap-1 flex-wrap">
                {tp.events.map(ev => (
                  <span key={ev} className="text-[9px] font-mono text-[#64748B] bg-[#F1F5F9] rounded px-1.5 py-0.5">{ev}</span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

const KV = ({ label, value }) => (
  <div>
    <div className="text-[9px] font-bold uppercase tracking-[0.14em] text-[#94A3B8]">{label}</div>
    <div className="text-xs text-[#0F172A] font-semibold mt-0.5">{value}</div>
  </div>
);

export default PtTouchpointMap;
