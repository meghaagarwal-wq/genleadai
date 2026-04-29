import React, { useEffect, useState } from 'react';
import { Phone, EnvelopeSimple, WhatsappLogo, Trophy, Fire, Sun, Lightning } from '@phosphor-icons/react';
import api from '../config/api';

const MOMENTUM_TONE = {
  strong: { label: 'STRONG DAY', accent: '#16A34A', bg: 'rgba(22,163,74,0.12)', border: 'rgba(22,163,74,0.25)' },
  steady: { label: 'STEADY DAY', accent: '#7C35DC', bg: 'rgba(124,53,220,0.12)', border: 'rgba(124,53,220,0.25)' },
  quiet:  { label: 'QUIET DAY',  accent: '#D97706', bg: 'rgba(217,119,6,0.12)',  border: 'rgba(217,119,6,0.30)' },
};

const KPI_TILES = [
  { key: 'calls',      label: 'Calls',      icon: Phone,         color: '#7C35DC' },
  { key: 'emails',     label: 'Emails',     icon: EnvelopeSimple, color: '#7C35DC' },
  { key: 'whatsapps',  label: 'WhatsApps',  icon: WhatsappLogo,   color: '#16A34A' },
  { key: 'wins',       label: 'Wins',       icon: Trophy,         color: '#16A34A' },
];

const AriaTodayWidget = () => {
  const [today, setToday] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      api.get('/api/aria/today')
        .then(res => { if (!cancelled) { setToday(res.data); setLoading(false); } })
        .catch(() => { if (!cancelled) setLoading(false); });
    };
    load();
    // Refresh every 60s so the founder sees momentum live
    const id = setInterval(load, 60000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  if (loading || !today) {
    return (
      <div className="bg-white border border-[#E8E0F5] rounded-2xl p-5 animate-pulse" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="aria-today-widget-loading">
        <div className="h-4 w-32 bg-[#F4F0FF] rounded mb-3"></div>
        <div className="h-6 w-64 bg-[#F4F0FF] rounded mb-4"></div>
        <div className="grid grid-cols-4 gap-2">
          {[1,2,3,4].map(i => <div key={i} className="h-16 bg-[#FAF7FF] rounded-lg"></div>)}
        </div>
      </div>
    );
  }

  const tone = MOMENTUM_TONE[today.momentum] || MOMENTUM_TONE.steady;
  const t = today.totals || {};

  return (
    <div className="bg-white border border-[#E8E0F5] rounded-2xl overflow-hidden" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="aria-today-widget">
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 pt-5 pb-3">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg,#1A0F38 0%,#7C35DC 100%)' }}>
            <Sun size={16} weight="fill" className="text-white" />
          </div>
          <div>
            <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC]" style={{ fontFamily: 'Plus Jakarta Sans' }}>ARIA TODAY · LIVE</div>
            <div className="text-base font-extrabold text-[#1A0A2E] mt-0.5" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid="aria-today-headline">{today.headline}</div>
            <div className="text-xs text-[#9B8AB0] mt-0.5">{today.date_label} · auto-refreshes every minute</div>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <div className="px-3 py-1.5 rounded-full text-[10px] font-extrabold uppercase tracking-[0.15em]" style={{ background: tone.bg, color: tone.accent, border: `1px solid ${tone.border}`, fontFamily: 'Plus Jakarta Sans' }} data-testid="aria-today-momentum">
            {tone.label} · {t.total_touches || 0} TOUCHES
          </div>
          {today.hot_untouched_count > 0 && (
            <div className="px-3 py-1.5 rounded-full text-[10px] font-extrabold uppercase tracking-[0.15em] bg-[#FEE2E2] text-[#DC2626] border border-[#DC2626]/25 flex items-center gap-1" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid="aria-today-hot-untouched">
              <Fire size={11} weight="fill" /> {today.hot_untouched_count} HOT UNTOUCHED
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 px-5 pb-3">
        {KPI_TILES.map(tile => {
          const Icon = tile.icon;
          const value = t[tile.key] || 0;
          return (
            <div key={tile.key} className="bg-[#FAF7FF] border border-[#EDE5FA] rounded-xl px-3 py-3 flex items-center gap-3" data-testid={`aria-today-tile-${tile.key}`}>
              <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: 'rgba(255,255,255,0.85)', border: `1px solid ${tile.color}22` }}>
                <Icon size={16} weight="fill" style={{ color: tile.color }} />
              </div>
              <div className="min-w-0">
                <div className="text-2xl font-extrabold leading-none" style={{ color: tile.color, fontFamily: 'Plus Jakarta Sans' }}>{value}</div>
                <div className="text-[10px] font-bold uppercase tracking-[0.15em] text-[#5A4A7A] mt-1" style={{ fontFamily: 'Plus Jakarta Sans' }}>{tile.label}</div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-3 gap-px bg-[#F0ECF9] border-t border-[#F0ECF9]">
        <div className="bg-white px-5 py-3" data-testid="aria-today-secondary-newleads">
          <div className="text-[10px] font-bold uppercase tracking-[0.15em] text-[#9B8AB0]" style={{ fontFamily: 'Plus Jakarta Sans' }}>New leads</div>
          <div className="text-lg font-extrabold text-[#1A0A2E] mt-0.5" style={{ fontFamily: 'Plus Jakarta Sans' }}>{t.new_leads || 0}</div>
        </div>
        <div className="bg-white px-5 py-3" data-testid="aria-today-secondary-meetings">
          <div className="text-[10px] font-bold uppercase tracking-[0.15em] text-[#9B8AB0]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Meetings booked</div>
          <div className="text-lg font-extrabold text-[#1A0A2E] mt-0.5" style={{ fontFamily: 'Plus Jakarta Sans' }}>{t.meetings_booked || 0}</div>
        </div>
        <div className="bg-white px-5 py-3" data-testid="aria-today-secondary-overdue">
          <div className="text-[10px] font-bold uppercase tracking-[0.15em] text-[#9B8AB0]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Still overdue</div>
          <div className={`text-lg font-extrabold mt-0.5 ${(t.overdue_pending || 0) > 0 ? 'text-[#D97706]' : 'text-[#1A0A2E]'}`} style={{ fontFamily: 'Plus Jakarta Sans' }}>{t.overdue_pending || 0}</div>
        </div>
      </div>

      {(today.tomorrow_top_3 || []).length > 0 && (
        <div className="px-5 py-3 border-t border-[#F0ECF9] bg-[#FAF7FF]/50" data-testid="aria-today-tomorrow">
          <div className="flex items-center gap-2 mb-2">
            <Lightning size={12} weight="fill" className="text-[#7C35DC]" />
            <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#7C35DC]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Tomorrow's top 3 calls</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {today.tomorrow_top_3.map((p, idx) => (
              <span key={idx} className="px-2.5 py-1 rounded-md text-xs font-semibold text-[#1A0A2E] bg-white border border-[#E8E0F5]" data-testid={`aria-today-tomorrow-${idx}`}>
                {p.name || 'Lead'}{p.icp_score ? <span className="text-[#7C35DC] ml-1.5 font-mono">ICP {p.icp_score}</span> : null}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default AriaTodayWidget;
