/**
 * AuditLogAdminTab — Master Admin cross-tenant audit log viewer.
 *
 * Surfaces every sensitive action across every workspace: failed logins,
 * IP/email lockouts, data purges, member changes, CRM (dis)connects, plan
 * changes, settings updates, API-key rotations, workspace deletions.
 *
 * Backend: GET /api/admin/workspaces/audit-log
 *   query: action, user_email, tenant_id, sensitive_only, limit, skip
 */
import React, { useEffect, useState, useMemo } from 'react';
import { toast } from 'sonner';
import api from '../../config/api';
import {
  ShieldCheck, ArrowsClockwise, Funnel, MagnifyingGlass,
  Warning, Lock, Sparkle,
} from '@phosphor-icons/react';

// Map common audit actions to a colour + friendly label for the badge.
const ACTION_META = {
  'auth.login_failed':    { tint: '#DC2626', bg: '#FEE2E2', label: 'Login failed' },
  'auth.login_blocked':   { tint: '#DC2626', bg: '#FEE2E2', label: 'Login blocked' },
  'auth.login_success':   { tint: '#16A34A', bg: '#DCFCE7', label: 'Login OK' },
  'lead.data_purged':     { tint: '#DC2626', bg: '#FEE2E2', label: 'Data purged' },
  'workspace.deleted':    { tint: '#DC2626', bg: '#FEE2E2', label: 'Workspace deleted' },
  'member.removed':       { tint: '#D97706', bg: '#FEF3C7', label: 'Member removed' },
  'member.role_changed':  { tint: '#D97706', bg: '#FEF3C7', label: 'Role changed' },
  'api_key.rotated':      { tint: '#7C35DC', bg: '#F4F0FF', label: 'API key rotated' },
  'settings.updated':     { tint: '#0055FF', bg: '#DCEEFE', label: 'Settings updated' },
  'crm.connected':        { tint: '#16A34A', bg: '#DCFCE7', label: 'CRM connected' },
  'crm.disconnected':     { tint: '#D97706', bg: '#FEF3C7', label: 'CRM disconnected' },
  'plan.changed':         { tint: '#7C35DC', bg: '#F4F0FF', label: 'Plan changed' },
  'payment.recorded':     { tint: '#16A34A', bg: '#DCFCE7', label: 'Payment recorded' },
};

const fallbackMeta = (action) => ({
  tint: '#5A4A7A', bg: '#F0ECF9', label: action.split('.').pop().replace(/_/g, ' '),
});

const AuditLogAdminTab = () => {
  const [rows, setRows] = useState([]);
  const [byAction, setByAction] = useState({});
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [sensitiveOnly, setSensitiveOnly] = useState(true);
  const [actionFilter, setActionFilter] = useState('');
  const [search, setSearch] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const params = { sensitive_only: sensitiveOnly, limit: 200 };
      if (actionFilter) params.action = actionFilter;
      const r = await api.get('/api/admin/audit-log', { params });
      setRows(r.data?.entries || []);
      setByAction(r.data?.by_action || {});
      setTotal(r.data?.total || 0);
    } catch (e) {
      toast.error('Could not load audit log');
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [sensitiveOnly, actionFilter]);  // eslint-disable-line

  // Client-side search across user_id / tenant_id / metadata so the master admin
  // can quickly find one suspect actor without a fresh round-trip.
  const filtered = useMemo(() => {
    if (!search.trim()) return rows;
    const q = search.toLowerCase();
    return rows.filter((r) => {
      const haystack = [
        r.user_id, r.tenant_id, r.action, r.resource_id, r.ip_address,
        JSON.stringify(r.metadata || {}),
      ].filter(Boolean).join(' ').toLowerCase();
      return haystack.includes(q);
    });
  }, [rows, search]);

  // Top-5 most frequent actions in the current filter for chip-style nav.
  const topActions = useMemo(() => {
    return Object.entries(byAction)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 6);
  }, [byAction]);

  return (
    <div className="space-y-4" data-testid="audit-log-admin-tab">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-lg font-extrabold text-[#1A0A2E] inline-flex items-center gap-2" style={{ fontFamily: 'Plus Jakarta Sans' }}>
            <ShieldCheck size={16} weight="fill" className="text-[#7C35DC]" /> Audit Log
          </h2>
          <p className="text-xs text-[#5A4A7A]">Cross-workspace audit trail. Toggle 'Sensitive only' to focus on auth + role + data events.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setSensitiveOnly((v) => !v)} data-testid="audit-sensitive-toggle"
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold border transition-colors ${
              sensitiveOnly ? 'bg-[#7C35DC] text-white border-[#7C35DC]' : 'bg-white border-[#E8E0F5] text-[#5A4A7A] hover:border-[#7C35DC]/30'
            }`}>
            <Lock size={11} weight="fill" /> Sensitive only
          </button>
          <button onClick={load} data-testid="audit-refresh"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-[#E8E0F5] rounded-lg text-xs font-bold text-[#5A4A7A] hover:bg-[#F9F5FF]">
            <ArrowsClockwise size={12} weight="bold" className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
        </div>
      </div>

      {/* Top-action pills as a quick filter */}
      <div className="flex items-center gap-1.5 flex-wrap" data-testid="audit-action-pills">
        <button onClick={() => setActionFilter('')} data-testid="audit-action-all"
          className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-[11px] font-bold border ${
            !actionFilter ? 'text-white border-transparent' : 'bg-white text-[#5A4A7A] border-[#E8E0F5]'
          }`}
          style={!actionFilter ? { background: 'var(--gradient-brand)', fontFamily: 'Plus Jakarta Sans' } : { fontFamily: 'Plus Jakarta Sans' }}>
          All <span className={`text-[9px] font-extrabold ml-0.5 px-1 rounded ${!actionFilter ? 'bg-white/25' : 'bg-[#F4F0FF] text-[#7C35DC]'}`}>{total}</span>
        </button>
        {topActions.map(([a, n]) => {
          const m = ACTION_META[a] || fallbackMeta(a);
          const isActive = actionFilter === a;
          return (
            <button key={a} onClick={() => setActionFilter(a)} data-testid={`audit-action-${a}`}
              className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-[11px] font-bold border transition-all ${
                isActive ? 'text-white border-transparent' : 'hover:-translate-y-0.5'
              }`}
              style={isActive
                ? { background: m.tint, fontFamily: 'Plus Jakarta Sans' }
                : { background: m.bg, color: m.tint, borderColor: m.tint + '33', fontFamily: 'Plus Jakarta Sans' }}>
              {m.label}
              <span className={`text-[9px] font-extrabold ml-0.5 px-1 rounded ${isActive ? 'bg-white/25' : 'bg-white/60'}`}>{n}</span>
            </button>
          );
        })}
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <MagnifyingGlass size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9B8AB0]" />
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search by user, tenant, IP, or resource..."
          data-testid="audit-search"
          className="w-full pl-9 pr-3 py-2 bg-white border border-[#E8E0F5] rounded-lg text-xs text-[#1A0A2E] focus:border-[#7C35DC] focus:ring-2 focus:ring-[#7C35DC]/15 outline-none transition" />
      </div>

      {filtered.length === 0 && !loading && (
        <div className="bg-white border border-[#E8E0F5] rounded-2xl p-10 text-center" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="audit-empty">
          <Sparkle size={24} weight="duotone" className="mx-auto text-[#9B8AB0] mb-2" />
          <p className="text-sm text-[#5A4A7A]">No matching audit entries.</p>
        </div>
      )}

      {filtered.length > 0 && (
        <div className="bg-white border border-[#E8E0F5] rounded-2xl overflow-hidden" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="audit-list">
          <div className="grid grid-cols-[140px_1fr_180px_160px_120px] gap-2 px-4 py-2 bg-[#FAF7FF] border-b border-[#F0ECF9] text-[10px] font-extrabold uppercase tracking-[0.18em] text-[#5A4A7A]">
            <span>When</span>
            <span>Action</span>
            <span>Actor</span>
            <span>Tenant / Resource</span>
            <span>IP</span>
          </div>
          {filtered.slice(0, 200).map((r) => {
            const m = ACTION_META[r.action] || fallbackMeta(r.action);
            const meta = r.metadata || {};
            const isAttack = ['auth.login_failed', 'auth.login_blocked'].includes(r.action);
            return (
              <div key={r.id} className={`grid grid-cols-[140px_1fr_180px_160px_120px] gap-2 px-4 py-3 border-b border-[#F0ECF9] last:border-0 text-xs items-center ${isAttack ? 'bg-red-50/30' : ''}`} data-testid={`audit-row-${r.id}`}>
                <span className="text-[#9B8AB0] tracking-wider text-[11px]">{new Date(r.created_at).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' })}</span>
                <span>
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold border" style={{ background: m.bg, color: m.tint, borderColor: m.tint + '33' }}>
                    {isAttack && <Warning size={9} weight="fill" />} {m.label}
                  </span>
                  {meta?.reason && <span className="text-[10px] text-[#5A4A7A] ml-2">· {meta.reason}</span>}
                </span>
                <span className="text-[#1A0A2E] font-bold truncate">{r.user_id || '—'}</span>
                <span className="text-[#5A4A7A] truncate" title={r.tenant_id || ''}>
                  {r.tenant_id || '—'}{r.resource_type ? ` · ${r.resource_type}` : ''}
                </span>
                <span className="text-[#5A4A7A] font-mono text-[10px] truncate" title={r.ip_address || ''}>{r.ip_address || '—'}</span>
              </div>
            );
          })}
          {total > filtered.length && (
            <div className="px-4 py-2 text-[10px] text-center text-[#9B8AB0] bg-[#FAF7FF] border-t border-[#F0ECF9]">
              Showing {filtered.length} of {total} entries
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default AuditLogAdminTab;
