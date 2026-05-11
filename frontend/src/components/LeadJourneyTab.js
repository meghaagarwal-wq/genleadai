import React, { useEffect, useState } from 'react';
import api from '../config/api';
import { toast } from 'sonner';
import {
  CheckCircle, Clock, X as XIcon, ArrowsClockwise, Pause, Play,
  ChatCircle, EnvelopeSimple, Phone, LinkedinLogo, Lightning, Sparkle,
} from '@phosphor-icons/react';

const CHANNEL_META = {
  whatsapp: { label: 'WhatsApp', color: '#25D366', icon: ChatCircle },
  email: { label: 'Email', color: '#0055FF', icon: EnvelopeSimple },
  call_reminder: { label: 'Call', color: '#F97316', icon: Phone },
  linkedin_nudge: { label: 'LinkedIn', color: '#7C35DC', icon: LinkedinLogo },
};

const STATUS_META = {
  pending: { color: '#9B8AB0', label: 'Pending', icon: Clock },
  paused: { color: '#F59E0B', label: 'Paused', icon: Pause },
  sent: { color: '#16A34A', label: 'Sent', icon: CheckCircle },
  skipped: { color: '#A0A8C0', label: 'Skipped', icon: ArrowsClockwise },
  failed: { color: '#DC2626', label: 'Failed', icon: XIcon },
  cancelled: { color: '#737373', label: 'Cancelled', icon: XIcon },
  alert_sent: { color: '#D97706', label: 'Alert sent', icon: Lightning },
};

/**
 * LeadJourneyTab — Phase B Journey view inside the lead drawer.
 *
 * Shows the full touchpoint timeline for this lead. Each row has a status
 * indicator, expandable sent-message preview, "Send now" override on pending
 * rows, and a Pause/Resume/Cancel switch at the top.
 */
const LeadJourneyTab = ({ leadId }) => {
  const [touchpoints, setTouchpoints] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyAction, setBusyAction] = useState(false);
  const [expanded, setExpanded] = useState({});
  const [firing, setFiring] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get(`/api/touchpoints/lead/${leadId}/journey`);
      setTouchpoints(r.data?.touchpoints || []);
    } catch {
      setTouchpoints([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [leadId]);

  const doAction = async (action) => {
    setBusyAction(true);
    try {
      await api.post(`/api/touchpoints/lead/${leadId}/action`, { action });
      const labels = { pause_lead: 'Paused', resume_lead: 'Resumed', cancel_remaining: 'Cancelled' };
      toast.success(`${labels[action]} pending touchpoints`);
      await load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Action failed');
    } finally {
      setBusyAction(false);
    }
  };

  const sendNow = async (tpId) => {
    setFiring(tpId);
    try {
      await api.post(`/api/touchpoints/touchpoint/${tpId}/send-now`);
      toast.success('Touchpoint fired');
      await load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Send failed');
    } finally {
      setFiring(null);
    }
  };

  const pendingCount = touchpoints.filter((t) => t.status === 'pending').length;
  const pausedCount = touchpoints.filter((t) => t.status === 'paused').length;
  const isPaused = pendingCount === 0 && pausedCount > 0;

  if (loading) return <div className="p-6 text-sm text-[#5A4A7A]">Loading journey…</div>;

  if (touchpoints.length === 0) {
    return (
      <div className="bg-white border border-[#E8E0F5] rounded-xl p-8 text-center text-sm text-[#5A4A7A]" data-testid="journey-empty">
        <Sparkle size={20} weight="fill" className="text-[#7C35DC] mx-auto mb-2" />
        No touchpoint journey for this lead.<br />
        <span className="text-xs text-[#9B8AB0]">Save a touchpoint map in onboarding or Settings, then create the lead.</span>
      </div>
    );
  }

  return (
    <div className="space-y-3" data-testid="journey-tab">
      {/* Header + Pause toggle */}
      <div className="bg-white border border-[#E8E0F5] rounded-xl p-4 flex items-center justify-between">
        <div>
          <div className="text-sm font-bold text-[#1A0A2E]">
            {touchpoints.length} touchpoints · {pendingCount} pending · {touchpoints.filter((t) => t.status === 'sent').length} sent
          </div>
          <div className="text-[10px] text-[#9B8AB0] uppercase tracking-[0.14em] font-bold mt-0.5">Aria journey</div>
        </div>
        <div className="flex items-center gap-1.5">
          {isPaused ? (
            <button onClick={() => doAction('resume_lead')} disabled={busyAction} data-testid="journey-resume"
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-bold bg-[#16A34A] text-white disabled:opacity-50">
              <Play size={11} weight="fill" /> Resume
            </button>
          ) : (
            <button onClick={() => doAction('pause_lead')} disabled={busyAction || pendingCount === 0} data-testid="journey-pause"
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-bold bg-[#F59E0B] text-white disabled:opacity-50">
              <Pause size={11} weight="fill" /> Pause Aria
            </button>
          )}
          <button onClick={() => doAction('cancel_remaining')} disabled={busyAction || (pendingCount + pausedCount) === 0}
            data-testid="journey-cancel"
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-bold border border-[#DC2626]/40 text-[#DC2626] hover:bg-[#DC2626]/10 disabled:opacity-50">
            Cancel remaining
          </button>
        </div>
      </div>

      {/* Touchpoint timeline */}
      <div className="space-y-2">
        {touchpoints.map((t) => {
          const ch = CHANNEL_META[t.channel] || CHANNEL_META.whatsapp;
          const ChIcon = ch.icon;
          const st = STATUS_META[t.status] || STATUS_META.pending;
          const StIcon = st.icon;
          const isExpanded = expanded[t.id];
          const canSendNow = t.status === 'pending' || t.status === 'paused' || t.status === 'failed';
          return (
            <div key={t.id} className="bg-white border border-[#E8E0F5] rounded-lg p-3" data-testid={`journey-row-${t.touchpoint_index}`}>
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-md flex-shrink-0 flex items-center justify-center" style={{ background: `${ch.color}1A`, color: ch.color }}>
                  <ChIcon size={14} weight="fill" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center flex-wrap gap-1.5">
                    <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#7C35DC]">#{t.touchpoint_index + 1}</span>
                    <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#5A4A7A]">· {ch.label}</span>
                    <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#5A4A7A]">· {t.message_type}</span>
                    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-[0.1em]" style={{ background: `${st.color}1A`, color: st.color, border: `1px solid ${st.color}40` }}>
                      <StIcon size={9} weight="fill" /> {st.label}
                    </span>
                  </div>
                  <div className="text-xs text-[#5A4A7A] mt-1">
                    {t.fired_at ? `Sent ${new Date(t.fired_at).toLocaleString()}` : t.scheduled_for ? `Scheduled for ${new Date(t.scheduled_for).toLocaleString()}` : '—'}
                  </div>
                  {(t.message_sent || isExpanded) && (
                    <div className="mt-2 bg-[#FBF9FE] border border-[#F0ECF9] rounded-md p-2 text-xs text-[#1A0A2E]" data-testid={`journey-msg-${t.touchpoint_index}`}>
                      {t.message_sent || t.message_template}
                    </div>
                  )}
                  {t.error && <div className="mt-1 text-[10px] text-[#DC2626]">Error: {t.error}</div>}
                </div>
                <div className="flex flex-col gap-1.5 flex-shrink-0">
                  {canSendNow && (
                    <button onClick={() => sendNow(t.id)} disabled={firing === t.id} data-testid={`journey-send-now-${t.touchpoint_index}`}
                      className="px-2 py-1 rounded text-[10px] font-bold uppercase tracking-[0.14em] bg-[#7C35DC] text-white hover:bg-[#6A2CC8] disabled:opacity-50">
                      {firing === t.id ? '…' : 'Send now'}
                    </button>
                  )}
                  {t.message_sent && !isExpanded && (
                    <button onClick={() => setExpanded({ ...expanded, [t.id]: true })}
                      className="px-2 py-1 rounded text-[10px] font-bold uppercase tracking-[0.14em] text-[#7C35DC] hover:bg-[#F4F0FF]">
                      View
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default LeadJourneyTab;
