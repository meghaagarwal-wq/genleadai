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
 * Polls every 90s, hits the same dashboard analytics endpoint already used
 * by AriaCommandRoom so there's no extra backend work.
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../config/api';

const MODES = {
  drafting:  { label: 'Drafting',  tint: '#DC2626', bg: '#FEE2E2', tip: 'Aria is drafting replies for hot leads.' },
  nurturing: { label: 'Nurturing', tint: '#D97706', bg: '#FEF3C7', tip: 'Aria is reviving cold leads.' },
  following: { label: 'Following', tint: '#0055FF', bg: '#DCEEFE', tip: 'Aria is following up on recent opens.' },
  listening: { label: 'Listening', tint: '#16A34A', bg: '#DCFCE7', tip: 'Aria is watching your pipeline.' },
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
        setMode(derive({ hot, stale, opens }));
      } catch { /* keep last mode */ }
    };
    refresh();
    const t = setInterval(refresh, 90_000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  const m = MODES[mode];

  return (
    <button
      onClick={() => navigate('/')}
      data-testid="topbar-aria-mode-chip"
      title={m.tip}
      className="hidden md:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border transition-all hover:shadow-sm"
      style={{ background: m.bg, borderColor: m.tint + '55' }}
    >
      <span className="relative flex items-center">
        <span className="absolute w-2 h-2 rounded-full opacity-60 aria-ping" style={{ background: m.tint }} />
        <span className="w-1.5 h-1.5 rounded-full" style={{ background: m.tint }} />
      </span>
      <span className="text-[10px] font-extrabold uppercase tracking-wider" style={{ color: m.tint, fontFamily: 'Plus Jakarta Sans' }}>
        Aria · {m.label}
      </span>
      <style>{`
        @keyframes aria-ping-tb { 0% { transform: scale(1); opacity: 0.6; } 75%, 100% { transform: scale(2.4); opacity: 0; } }
        .aria-ping { animation: aria-ping-tb 1.8s cubic-bezier(0,0,0.2,1) infinite; }
      `}</style>
    </button>
  );
};

export default AriaModeChip;
