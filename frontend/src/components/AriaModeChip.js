/**
 * AriaModeChip — persistent topbar indicator that surfaces ARIA's current
 * working mode on every page.
 *
 * Modes (first match wins, derived from real backend signals — no fake data):
 *   • drafting   → hot leads > 0 (highest priority — replies in flight)
 *   • nurturing  → stale leads > 5
 *   • following  → recent opens > 0
 *   • listening  → default calm state
 *
 * Hover reveals a rich tooltip explaining all 4 modes + the live counters
 * that drive the current state. Polls every 90s.
 */
import React, { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../config/api';
import { Sparkle, Fire, Thermometer, Eye, Heart, ArrowRight } from '@phosphor-icons/react';

const MODES = {
  drafting:  { label: 'Drafting',  tint: '#DC2626', bg: '#FEE2E2', icon: Fire,
               headline: 'Drafting replies right now',
               body: 'Aria is queuing personalized first replies for new hot leads.' },
  nurturing: { label: 'Nurturing', tint: '#D97706', bg: '#FEF3C7', icon: Heart,
               headline: 'Nurturing stale prospects',
               body: 'Aria is reviving leads that have gone quiet so they don\'t slip.' },
  following: { label: 'Following', tint: '#0055FF', bg: '#DCEEFE', icon: Eye,
               headline: 'Following up on recent opens',
               body: 'Aria is sending warm follow-ups to leads who just engaged.' },
  listening: { label: 'Listening', tint: '#16A34A', bg: '#DCFCE7', icon: Thermometer,
               headline: 'Listening — pipeline is calm',
               body: 'Nothing urgent. Aria is monitoring every channel in the background.' },
};

const derive = ({ hot, stale, opens }) => {
  if (hot > 0) return 'drafting';
  if (stale > 5) return 'nurturing';
  if (opens > 0) return 'following';
  return 'listening';
};

const AriaModeChip = () => {
  const navigate = useNavigate();
  const [mode, setMode] = useState('listening');
  const [counters, setCounters] = useState({ hot: 0, stale: 0, opens: 0 });
  const [open, setOpen] = useState(false);
  const closeT = useRef(null);

  useEffect(() => {
    let alive = true;
    const refresh = async () => {
      try {
        const [a, s] = await Promise.all([
          api.get('/api/analytics/dashboard').catch(() => ({ data: null })),
          api.get('/api/health/stale-leads?limit=1').catch(() => ({ data: null })),
        ]);
        if (!alive) return;
        const hot = a.data?.icp_distribution?.hot ?? a.data?.leads_by_tier?.hot ?? 0;
        const stale = s.data?.count ?? s.data?.total ?? (Array.isArray(s.data?.leads) ? s.data.leads.length : 0) ?? 0;
        const opens = a.data?.recent_opens ?? 0;
        setCounters({ hot, stale, opens });
        setMode(derive({ hot, stale, opens }));
      } catch { /* keep last mode */ }
    };
    refresh();
    const t = setInterval(refresh, 90_000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  const m = MODES[mode];
  const Icon = m.icon;

  const handleEnter = () => { clearTimeout(closeT.current); setOpen(true); };
  const handleLeave = () => { closeT.current = setTimeout(() => setOpen(false), 200); };

  return (
    <div className="hidden md:inline-block relative" onMouseEnter={handleEnter} onMouseLeave={handleLeave}>
      <button
        onClick={() => navigate('/')}
        data-testid="topbar-aria-mode-chip"
        aria-label={`Aria mode: ${m.label}. ${m.headline}.`}
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border transition-all hover:shadow-sm"
        style={{ background: m.bg, borderColor: m.tint + '55' }}
      >
        <span className="relative flex items-center">
          <span className="absolute w-2 h-2 rounded-full opacity-60 aria-ping" style={{ background: m.tint }} />
          <span className="w-1.5 h-1.5 rounded-full" style={{ background: m.tint }} />
        </span>
        <span className="text-[10px] font-extrabold uppercase tracking-wider" style={{ color: m.tint, fontFamily: 'Plus Jakarta Sans' }}>
          Aria · {m.label}
        </span>
      </button>

      {open && (
        <div
          className="absolute right-0 top-full mt-2 w-[320px] bg-white border border-[#E0D4F7] rounded-2xl p-4 z-50 aria-fade-up"
          style={{ boxShadow: '0 18px 48px rgba(124, 53, 220, 0.22), 0 4px 14px rgba(26, 10, 46, 0.08)' }}
          data-testid="aria-mode-tooltip"
          onMouseEnter={handleEnter}
          onMouseLeave={handleLeave}
        >
          {/* Current mode header */}
          <div className="flex items-start gap-2.5 pb-3 border-b border-[#F0ECF9]">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: m.tint + '18', border: `1px solid ${m.tint}33` }}>
              <Icon size={16} weight="fill" style={{ color: m.tint }} />
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-[10px] font-extrabold uppercase tracking-[0.22em] text-[#9B8AB0]">Right now</div>
              <div className="text-sm font-extrabold text-[#1A0A2E] leading-tight" style={{ fontFamily: 'Plus Jakarta Sans' }}>{m.headline}</div>
              <p className="text-[11px] text-[#5A4A7A] mt-0.5 leading-snug">{m.body}</p>
            </div>
          </div>

          {/* Live counters that drive the mode */}
          <div className="grid grid-cols-3 gap-1.5 mt-3">
            <Counter label="Hot" value={counters.hot} tint="#DC2626" active={mode === 'drafting'} />
            <Counter label="Stale" value={counters.stale} tint="#D97706" active={mode === 'nurturing'} />
            <Counter label="Opens" value={counters.opens} tint="#0055FF" active={mode === 'following'} />
          </div>

          {/* Mode legend */}
          <div className="mt-3 pt-3 border-t border-[#F0ECF9]">
            <div className="text-[9px] font-extrabold uppercase tracking-[0.18em] text-[#9B8AB0] mb-1.5">All 4 modes</div>
            <div className="space-y-1.5">
              {Object.entries(MODES).map(([k, mm]) => {
                const I = mm.icon;
                const isCurrent = k === mode;
                return (
                  <div key={k} className={`flex items-start gap-2 text-[11px] ${isCurrent ? 'opacity-100' : 'opacity-60'}`}>
                    <I size={11} weight="fill" style={{ color: mm.tint, marginTop: 2 }} />
                    <div className="min-w-0 flex-1">
                      <span className="font-extrabold" style={{ color: mm.tint }}>{mm.label}</span>
                      <span className="text-[#5A4A7A]"> · {mm.body}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <button
            onClick={() => { setOpen(false); navigate('/'); }}
            data-testid="aria-mode-tooltip-cta"
            className="w-full mt-3 inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-[11px] font-extrabold text-[#7C35DC] bg-[#F4F0FF] hover:bg-[#7C35DC] hover:text-white border border-[#7C35DC]/20 transition-colors"
            style={{ fontFamily: 'Plus Jakarta Sans' }}
          >
            <Sparkle size={11} weight="fill" /> Open Aria's Command Center <ArrowRight size={11} weight="bold" />
          </button>
        </div>
      )}

      <style>{`
        @keyframes aria-ping-tb { 0% { transform: scale(1); opacity: 0.6; } 75%, 100% { transform: scale(2.4); opacity: 0; } }
        .aria-ping { animation: aria-ping-tb 1.8s cubic-bezier(0,0,0.2,1) infinite; }
      `}</style>
    </div>
  );
};

const Counter = ({ label, value, tint, active }) => (
  <div className={`rounded-lg px-2 py-1.5 border text-center ${active ? '' : 'opacity-70'}`}
    style={{ background: tint + '12', borderColor: tint + (active ? '55' : '22') }}>
    <div className="text-base font-extrabold" style={{ color: tint, fontFamily: 'Plus Jakarta Sans' }}>{value}</div>
    <div className="text-[9px] font-bold uppercase tracking-wider text-[#5A4A7A]">{label}</div>
  </div>
);

export default AriaModeChip;
