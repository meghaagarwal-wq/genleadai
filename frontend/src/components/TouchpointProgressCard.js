/**
 * TouchpointProgressCard — left-column visual for the Lead Profile page.
 *
 * At-a-glance "Touchpoint N of M" with a soft progress ring, completed/sent
 * count, current touchpoint label, and next scheduled action. Real data from
 * /api/touchpoints/lead/{leadId}/journey.
 *
 * Pairs with the existing LeadJourneyTab in the main column.
 */
import React, { useEffect, useState } from 'react';
import api from '../config/api';
import { MapTrifold, ArrowRight, Sparkle } from '@phosphor-icons/react';

const STATUS_META = {
  sent:        { color: '#16A34A', label: 'Sent' },
  pending:     { color: '#0055FF', label: 'Scheduled' },
  paused:      { color: '#D97706', label: 'Paused' },
  skipped:     { color: '#9B8AB0', label: 'Skipped' },
  failed:      { color: '#DC2626', label: 'Failed' },
  cancelled:   { color: '#9B8AB0', label: 'Cancelled' },
  alert_sent:  { color: '#D97706', label: 'Alert' },
};

const TouchpointProgressCard = ({ leadId, onOpenJourney }) => {
  const [tps, setTps] = useState(null);

  useEffect(() => {
    if (!leadId) return;
    api.get(`/api/touchpoints/lead/${leadId}/journey`)
      .then((r) => setTps(r.data?.touchpoints || []))
      .catch(() => setTps([]));
  }, [leadId]);

  if (tps === null) {
    return (
      <div className="bg-white border border-[#E8E0F5] rounded-2xl p-5 animate-pulse h-44" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="touchpoint-progress-loading" />
    );
  }

  // Empty state — no journey yet.
  if (!tps.length) {
    return (
      <div className="aria-card-lift bg-gradient-to-br from-[#FAF7FF] to-white border border-[#E8E0F5] rounded-2xl p-5" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="touchpoint-progress-empty">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: 'var(--gradient-brand)' }}>
            <MapTrifold size={14} className="text-white" weight="fill" />
          </div>
          <h4 className="text-sm font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Touchpoint Journey</h4>
        </div>
        <p className="text-xs text-[#5A4A7A]">No journey scheduled yet. Save a touchpoint map in Settings to start Aria's 32-step sequence for new leads.</p>
      </div>
    );
  }

  const total = tps.length;
  const sent = tps.filter((t) => t.status === 'sent').length;
  const pending = tps.filter((t) => t.status === 'pending').length;
  const currentIdx = tps.findIndex((t) => t.status === 'pending');
  const current = currentIdx >= 0 ? tps[currentIdx] : tps[tps.length - 1];
  const pct = Math.round((sent / total) * 100);

  // Ring math
  const r = 32;
  const c = 2 * Math.PI * r;
  const dash = (sent / total) * c;
  const status = STATUS_META[current?.status] || STATUS_META.pending;

  return (
    <div
      className="aria-card-lift bg-white border border-[#E8E0F5] rounded-2xl p-5"
      style={{ boxShadow: 'var(--shadow-card)' }}
      data-testid="touchpoint-progress-card"
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: 'var(--gradient-brand)' }}>
            <MapTrifold size={14} className="text-white" weight="fill" />
          </div>
          <h4 className="text-sm font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Touchpoint Journey</h4>
        </div>
        <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#7C35DC] bg-[#F4F0FF] px-2 py-0.5 rounded-full border border-[#7C35DC]/15">{pct}%</span>
      </div>

      <div className="flex items-center gap-4">
        <svg width="80" height="80" viewBox="0 0 80 80" className="flex-shrink-0" data-testid="touchpoint-progress-ring">
          <circle cx="40" cy="40" r={r} fill="none" stroke="#F0ECF9" strokeWidth="7" />
          <circle
            cx="40" cy="40" r={r}
            fill="none" stroke="url(#tpGrad)"
            strokeWidth="7" strokeLinecap="round"
            strokeDasharray={`${dash} ${c}`}
            transform="rotate(-90 40 40)"
          />
          <defs>
            <linearGradient id="tpGrad" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#C044E0" />
              <stop offset="100%" stopColor="#5B28D4" />
            </linearGradient>
          </defs>
          <text x="40" y="38" textAnchor="middle" className="font-extrabold" fill="#1A0A2E" style={{ fontSize: 16, fontFamily: 'Plus Jakarta Sans' }}>{sent}</text>
          <text x="40" y="52" textAnchor="middle" fill="#9B8AB0" style={{ fontSize: 9, fontFamily: 'Plus Jakarta Sans', letterSpacing: '0.05em' }}>of {total}</text>
        </svg>
        <div className="min-w-0 flex-1">
          <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#9B8AB0] mb-1">Currently</div>
          <div className="text-sm font-extrabold text-[#1A0A2E] truncate" style={{ fontFamily: 'Plus Jakarta Sans' }}>
            #{(current?.touchpoint_index ?? 0) + 1} · {current?.channel || 'auto'}
          </div>
          <span className="inline-flex items-center gap-1 mt-1 px-1.5 py-0.5 rounded text-[10px] font-bold border" style={{ color: status.color, borderColor: status.color + '55', background: status.color + '14' }}>
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: status.color }} />
            {status.label}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 mt-4">
        <Stat label="Sent" value={sent} tint="#16A34A" />
        <Stat label="Scheduled" value={pending} tint="#0055FF" />
        <Stat label="Remaining" value={total - sent - pending} tint="#9B8AB0" />
      </div>

      <div className="mt-3 p-2.5 rounded-lg bg-gradient-to-r from-[#F4F0FF] to-[#FAFAFA] border border-[#E0D4F7] flex items-start gap-2" data-testid="touchpoint-aria-says">
        <Sparkle size={12} weight="fill" className="text-[#7C35DC] mt-0.5 flex-shrink-0" />
        <p className="text-[11px] text-[#5A4A7A] leading-relaxed">
          <span className="font-bold text-[#7C35DC]">Aria says:</span>{' '}
          {sent === 0
            ? 'Journey starts soon. The first touch will fire on schedule.'
            : sent === total
            ? 'Journey complete. Move this lead to the next stage or revive.'
            : `${total - sent} touchpoints remaining. Aria handles the next one automatically — open the Journey tab to override.`}
        </p>
      </div>

      <button
        onClick={onOpenJourney}
        data-testid="open-journey-tab-btn"
        className="w-full mt-3 inline-flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-extrabold text-[#7C35DC] bg-[#F4F0FF] border border-[#7C35DC]/20 rounded-lg hover:bg-[#7C35DC] hover:text-white transition-all"
        style={{ fontFamily: 'Plus Jakarta Sans' }}
      >
        Open full journey <ArrowRight size={11} weight="bold" />
      </button>
    </div>
  );
};

const Stat = ({ label, value, tint }) => (
  <div className="rounded-lg bg-[#FAFAFA] border border-[#F0ECF9] px-2 py-1.5 text-center">
    <div className="text-base font-extrabold" style={{ color: tint, fontFamily: 'Plus Jakarta Sans' }}>{value}</div>
    <div className="text-[9px] font-bold uppercase tracking-wider text-[#9B8AB0]">{label}</div>
  </div>
);

export default TouchpointProgressCard;
