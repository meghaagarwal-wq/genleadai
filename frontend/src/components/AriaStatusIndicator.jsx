// Iter79 — S8: persistent sidebar ARIA status indicator.
// Green = LIVE, Amber = SETUP, Red = PAUSED. Clicking opens a tiny popover
// with leads_today / touchpoints_today / last_activity_at and pause toggle.
import React, { useEffect, useRef, useState } from 'react';
import { Pulse, Pause, Play } from '@phosphor-icons/react';
import { toast } from 'sonner';
import api from '../config/api';

const STATUS_META = {
  LIVE:   { dot: 'bg-emerald-500',  ring: 'ring-emerald-300', label: 'ARIA Live' },
  SETUP:  { dot: 'bg-amber-500',    ring: 'ring-amber-300',   label: 'ARIA in Setup' },
  PAUSED: { dot: 'bg-rose-500',     ring: 'ring-rose-300',    label: 'ARIA Paused' },
};

export default function AriaStatusIndicator({ collapsed }) {
  const [data, setData] = useState(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const popoverRef = useRef(null);

  const load = async () => {
    try {
      const r = await api.get('/api/admin/deployments/_/sidebar-status');
      setData(r.data);
    } catch (_e) { setData(null); }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 60_000);   // refresh every minute
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const onClick = (e) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target)) setOpen(false);
    };
    if (open) document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [open]);

  if (!data) return null;
  const meta = STATUS_META[data.status] || STATUS_META.SETUP;
  const tenantId = JSON.parse(localStorage.getItem('active_tenant') || '{}')?.id;

  const toggle = async () => {
    if (!tenantId) return;
    setBusy(true);
    try {
      await api.post(`/api/admin/deployments/${tenantId}/toggle`, { pause: data.status !== 'PAUSED' });
      await load();
      toast.success(data.status === 'PAUSED' ? 'ARIA resumed' : 'ARIA paused');
    } catch (_e) {
      toast.error('Could not toggle — master admin only');
    } finally { setBusy(false); }
  };

  return (
    <div className="relative" ref={popoverRef}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        data-testid="aria-status-indicator"
        title={meta.label}
        className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider text-white/90 hover:text-white hover:bg-white/10 transition-colors ${collapsed ? 'justify-center w-full' : ''}`}
      >
        <span className={`w-2 h-2 rounded-full ${meta.dot} ring-2 ${meta.ring} ring-opacity-50 animate-pulse`} />
        {!collapsed && <span>{data.status}</span>}
      </button>

      {open && (
        <div
          data-testid="aria-status-popover"
          className="absolute left-full top-0 ml-2 w-64 bg-white rounded-xl shadow-xl border border-slate-200 p-3 z-50"
        >
          <div className="flex items-center gap-2 mb-3">
            <Pulse size={16} weight="duotone" className="text-violet-600" />
            <div className="text-xs font-extrabold text-slate-900">{meta.label}</div>
          </div>
          <dl className="space-y-1.5 text-xs">
            <div className="flex justify-between"><dt className="text-slate-500">Leads today</dt><dd className="font-bold text-slate-900" data-testid="aria-status-leads-today">{data.leads_today}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-500">Touchpoints today</dt><dd className="font-bold text-slate-900" data-testid="aria-status-touchpoints-today">{data.touchpoints_today}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-500">Last activity</dt><dd className="font-bold text-slate-900">{data.last_activity_at ? new Date(data.last_activity_at).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' }) : '—'}</dd></div>
          </dl>
          <button
            type="button"
            onClick={toggle}
            disabled={busy}
            data-testid="aria-status-toggle"
            className={`mt-3 w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-xs font-bold ${data.status === 'PAUSED' ? 'bg-emerald-600 text-white hover:bg-emerald-700' : 'bg-amber-600 text-white hover:bg-amber-700'} disabled:opacity-50`}
          >
            {data.status === 'PAUSED' ? <><Play size={12} weight="fill" /> Resume Aria</> : <><Pause size={12} weight="fill" /> Pause Aria</>}
          </button>
          <p className="text-[10px] text-slate-400 mt-2 italic text-center">Master admin only.</p>
        </div>
      )}
    </div>
  );
}
