/**
 * PlatformStatsTab — Master Admin Phase 5.6 platform-wide stats panel.
 * Reads from /api/admin/workspaces/platform/stats (already exists).
 */
import React, { useEffect, useState } from 'react';
import api from '../../config/api';
import {
  Buildings, Users, Lightning, Robot, EnvelopeSimple, Warning,
  ChartLineUp, CurrencyDollar, ArrowsClockwise,
} from '@phosphor-icons/react';

const TILES = [
  { key: 'total_workspaces',     label: 'Total Workspaces',  icon: Buildings,       tint: '#7C35DC' },
  { key: 'active_paying_clients',label: 'Paying Clients',    icon: CurrencyDollar,  tint: '#16A34A' },
  { key: 'trial_workspaces',     label: 'Active Trials',     icon: ChartLineUp,     tint: '#D97706' },
  { key: 'total_leads',          label: 'Total Leads',       icon: Users,           tint: '#0055FF' },
  { key: 'total_conversations',  label: 'Total Conversations', icon: Robot,         tint: '#C044E0' },
  { key: 'messages_sent_24h',    label: 'Messages Sent (24h)', icon: EnvelopeSimple,tint: '#16A34A' },
  { key: 'failed_messages_24h',  label: 'Failed (24h)',      icon: Warning,         tint: '#DC2626' },
  { key: 'claude_calls_today',   label: 'Claude Calls Today',icon: Lightning,       tint: '#7C35DC' },
];

const PlatformStatsTab = () => {
  const [data, setData] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    setRefreshing(true);
    try { const r = await api.get('/api/admin/workspaces/platform/stats'); setData(r.data); }
    finally { setRefreshing(false); }
  };

  useEffect(() => { load(); const id = setInterval(load, 60_000); return () => clearInterval(id); }, []);

  if (!data) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="platform-stats-loading">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="bg-white border border-[#E8E0F5] rounded-2xl p-4 h-28 animate-pulse" style={{ boxShadow: 'var(--shadow-card)' }} />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="platform-stats-tab">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Platform Stats</h2>
          <p className="text-xs text-[#5A4A7A]">Live counters across every GenLeadAI workspace. Auto-refreshes every 60s.</p>
        </div>
        <button onClick={load} disabled={refreshing} data-testid="platform-stats-refresh"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-[#E8E0F5] rounded-lg text-xs font-bold text-[#5A4A7A] hover:bg-[#F9F5FF]">
          <ArrowsClockwise size={12} weight="bold" className={refreshing ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {TILES.map(t => {
          const Icon = t.icon;
          const value = data[t.key] ?? 0;
          return (
            <div key={t.key} className="aria-card-lift bg-white border border-[#E8E0F5] rounded-2xl p-4" style={{ boxShadow: 'var(--shadow-card)' }} data-testid={`platform-stat-${t.key}`}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#5A4A7A]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{t.label}</span>
                <Icon size={16} weight="duotone" style={{ color: t.tint }} />
              </div>
              <div className="text-2xl font-extrabold" style={{ color: t.tint, fontFamily: 'Plus Jakarta Sans' }}>{value.toLocaleString?.() ?? value}</div>
            </div>
          );
        })}
      </div>

      <div className="aria-card-lift bg-white border border-[#E8E0F5] rounded-2xl p-5" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="platform-cost-card">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#5A4A7A]">Claude cost today</span>
            <div className="text-3xl font-extrabold text-[#1A0A2E] mt-1" style={{ fontFamily: 'Plus Jakarta Sans' }}>
              ${(data.claude_cost_today_usd || 0).toFixed(4)}
            </div>
            <p className="text-xs text-[#9B8AB0] mt-1">Sum of estimated LLM cost across all tenants since midnight UTC.</p>
          </div>
          <div className="w-12 h-12 rounded-2xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #7C35DC 0%, #C044E0 100%)' }}>
            <CurrencyDollar size={22} className="text-white" weight="fill" />
          </div>
        </div>
      </div>
    </div>
  );
};

export default PlatformStatsTab;
