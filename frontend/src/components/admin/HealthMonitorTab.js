/**
 * HealthMonitorTab — platform service status pings (master admin).
 */
import React, { useEffect, useState } from 'react';
import api from '../../config/api';
import { CheckCircle, Warning, X, ArrowsClockwise, Lightning } from '@phosphor-icons/react';

const STATUS_META = {
  ok: { color: '#16A34A', bg: '#DCFCE7', icon: CheckCircle, label: 'Operational' },
  idle: { color: '#0055FF', bg: '#DCEEFE', icon: Lightning, label: 'Idle' },
  unconfigured: { color: '#D97706', bg: '#FEF3C7', icon: Warning, label: 'Not configured' },
  down: { color: '#DC2626', bg: '#FEE2E2', icon: X, label: 'Down' },
};

const HealthMonitorTab = () => {
  const [data, setData] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    setRefreshing(true);
    try { const r = await api.get('/api/admin/workspaces/health/services'); setData(r.data); }
    finally { setRefreshing(false); }
  };

  useEffect(() => { load(); const id = setInterval(load, 30000); return () => clearInterval(id); }, []);

  return (
    <div className="space-y-4" data-testid="health-monitor-tab">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Service Health</h2>
          <p className="text-xs text-[#5A4A7A]">Live status of every critical infrastructure dependency. Auto-refreshes every 30s.</p>
        </div>
        <button onClick={load} disabled={refreshing} data-testid="health-refresh"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-[#E8E0F5] rounded-lg text-xs font-bold text-[#5A4A7A] hover:bg-[#F9F5FF]">
          <ArrowsClockwise size={12} weight="bold" className={refreshing ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {(data?.services || []).map((s) => {
          const meta = STATUS_META[s.status] || STATUS_META.ok;
          const Icon = meta.icon;
          return (
            <div key={s.name} data-testid={`service-${s.name.toLowerCase().replace(/[^a-z]/g, '-')}`}
              className="bg-white border border-[#E8E0F5] rounded-xl p-4"
              style={{ boxShadow: 'var(--shadow-card)' }}>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-bold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{s.name}</h3>
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold border" style={{ background: meta.bg, borderColor: meta.color + '55', color: meta.color }}>
                  <Icon size={10} weight="fill" /> {meta.label}
                </span>
              </div>
              <div className="space-y-1 text-xs text-[#5A4A7A]">
                {s.latency_ms !== null && s.latency_ms !== undefined && (
                  <div>Latency: <span className="font-mono font-bold text-[#1A0A2E]">{s.latency_ms}ms</span></div>
                )}
                {s.configured_tenants !== undefined && (
                  <div>Configured workspaces: <span className="font-bold text-[#1A0A2E]">{s.configured_tenants}</span></div>
                )}
                {s.error && <div className="text-[#DC2626] font-mono text-[10px]">{s.error}</div>}
                {s.note && <div className="text-[10px] text-[#9B8AB0] italic">{s.note}</div>}
              </div>
            </div>
          );
        })}
      </div>

      {data?.checked_at && (
        <p className="text-[10px] text-[#9B8AB0] text-center">Last checked: {new Date(data.checked_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}</p>
      )}
    </div>
  );
};

export default HealthMonitorTab;
