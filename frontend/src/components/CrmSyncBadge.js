import React, { useEffect, useState } from 'react';
import api from '../config/api';
import { Database, ArrowsClockwise, Warning, CheckCircle } from '@phosphor-icons/react';

/**
 * Tiny inline badge showing the CRM sync state of a single lead.
 *
 * Behaviour:
 *  • Hidden when workspace has no CRM connected (no chrome at all).
 *  • Green "Synced to {CRM} · {time-ago}" when latest sync entry is success.
 *  • Yellow "Sync pending" if latest is pending/retrying.
 *  • Red "Sync failed" with retry action otherwise.
 */
const ago = (iso) => {
  if (!iso) return '—';
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
};

const CRM_LABEL = {
  hubspot: 'HubSpot',
  pipedrive: 'Pipedrive',
  zoho: 'Zoho',
  salesforce: 'Salesforce',
  custom_webhook: 'Webhook',
};

const CrmSyncBadge = ({ leadId, compact = false }) => {
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = () => {
    if (!leadId) return;
    api.get(`/api/crm/leads/${leadId}/status`)
      .then((r) => setState(r.data))
      .catch(() => setState({ connected: false }));
  };
  useEffect(load, [leadId]);

  if (!state || state.connected === false) return null;

  const latest = state.latest;
  const status = latest?.status || 'idle';
  const isSuccess = status === 'success';
  const isPending = status === 'pending' || status === 'retrying';
  const isFailed = status === 'failed';
  const crmLabel = CRM_LABEL[state.crm_type] || state.crm_type;

  const retry = async () => {
    if (!latest?.id) return;
    setBusy(true);
    try { await api.post(`/api/crm/sync-log/${latest.id}/retry`); load(); }
    catch { /* */ }
    finally { setBusy(false); }
  };

  // Compact (used in list rows)
  if (compact) {
    const dot = isSuccess ? '#16A34A' : isPending ? '#D97706' : isFailed ? '#DC2626' : '#9B8AB0';
    return (
      <span className="inline-flex items-center gap-1 text-[11px] font-bold" data-testid={`crm-badge-compact-${leadId}`} title={`${crmLabel} · ${status}`}>
        <span className="w-1.5 h-1.5 rounded-full" style={{ background: dot }} />
        <Database size={10} weight="fill" className="text-[#9B8AB0]" />
      </span>
    );
  }

  // Full version
  const wrap = `inline-flex items-center gap-2 px-2.5 py-1 rounded-md border text-[11px] font-bold`;
  if (isSuccess) {
    return (
      <span data-testid={`crm-badge-${leadId}`} className={`${wrap} bg-[#DCFCE7] text-[#16A34A] border-[#16A34A]/30`} title={`Synced ${ago(latest.synced_at)}`}>
        <CheckCircle size={12} weight="fill" />
        Synced to {crmLabel} · {ago(latest.synced_at)}
      </span>
    );
  }
  if (isPending) {
    return (
      <span data-testid={`crm-badge-${leadId}`} className={`${wrap} bg-[#FEF3C7] text-[#D97706] border-[#D97706]/30`}>
        <ArrowsClockwise size={12} weight="bold" className="animate-spin" />
        Sync pending
      </span>
    );
  }
  if (isFailed) {
    return (
      <span data-testid={`crm-badge-${leadId}`} className={`${wrap} bg-[#FEE2E2] text-[#DC2626] border-[#DC2626]/30`} title={latest?.error_message || 'Failed'}>
        <Warning size={12} weight="fill" />
        Sync failed
        <button onClick={retry} disabled={busy} data-testid={`crm-retry-${leadId}`} className="underline hover:no-underline ml-1">{busy ? '…' : 'retry'}</button>
      </span>
    );
  }
  return (
    <span data-testid={`crm-badge-${leadId}`} className={`${wrap} bg-[#F1F5F9] text-[#5A4A7A] border-[#94A3B8]/30`}>
      <Database size={11} weight="fill" /> {crmLabel}
    </span>
  );
};

export default CrmSyncBadge;
