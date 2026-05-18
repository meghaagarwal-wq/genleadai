import React, { useEffect, useState } from 'react';
import api from '../config/api';
import { toast } from 'sonner';
import { ShieldCheck, ShieldWarning } from '@phosphor-icons/react';
import { useChannelEnabled } from '../hooks/useChannelEnabled';

/**
 * LeadOptInBanner — yellow warning banner shown when a lead has not opted in
 * to WhatsApp messaging. Only relevant for tenants who actually use WhatsApp
 * as a follow-up channel.
 */
const LeadOptInBanner = ({ lead, onUpdated }) => {
  const [loading, setLoading] = useState(false);
  const { isEnabled, isLoading: prefsLoading } = useChannelEnabled();

  if (!lead) return null;
  // Hide entirely if the tenant didn't pick WhatsApp — opt-in is a WhatsApp
  // compliance construct, irrelevant for email-only / linkedin-only flows.
  if (!prefsLoading && !isEnabled('whatsapp')) return null;
  const isOptedIn = !!lead.opted_in;

  if (isOptedIn) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#ECFDF5] border border-[#16A34A]/30 text-[#15803D] text-xs font-semibold" data-testid="lead-opt-in-ok">
        <ShieldCheck size={12} weight="fill" /> Opted in
        {lead.opted_in_source && <span className="text-[10px] text-[#16A34A]/70 ml-1">· {lead.opted_in_source}</span>}
      </div>
    );
  }

  const markOptedIn = async () => {
    setLoading(true);
    try {
      await api.post('/api/compliance/lead/opt-in', { lead_id: lead.id, source: 'manual_confirmed' });
      toast.success('Lead marked as opted in');
      onUpdated?.();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Could not mark opt-in');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-[#FEF3C7] border border-[#F59E0B]/40 rounded-lg p-3 flex items-start gap-2" data-testid="lead-opt-in-warning">
      <ShieldWarning size={14} weight="fill" className="text-[#B45309] flex-shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <div className="text-xs font-bold text-[#92400E]">This lead has not confirmed WhatsApp opt-in.</div>
        <div className="text-[11px] text-[#92400E]/80 mt-0.5">
          Aria will <strong>not</strong> message them automatically. Confirm consent before manual outreach.
        </div>
      </div>
      <button onClick={markOptedIn} disabled={loading} data-testid="lead-opt-in-mark"
        className="flex-shrink-0 px-3 py-1.5 rounded-md text-[11px] font-bold bg-[#B45309] text-white hover:bg-[#92400E] disabled:opacity-50">
        {loading ? '…' : 'Mark as opted in'}
      </button>
    </div>
  );
};

export default LeadOptInBanner;
