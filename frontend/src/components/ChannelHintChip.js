import React, { useState, useEffect } from 'react';
import {
  ChatTeardropDots, Envelope, LinkedinLogo, ChatCircle, Phone, DeviceMobile,
  Sparkle, Info,
} from '@phosphor-icons/react';
import api from '../config/api';

/**
 * Small "Why this channel?" explainer chip for Lead Inbox rows.
 *
 * Fetches /api/tenant/sales-channels/recommendations ONCE at app-level via
 * the `useChannelRecommendations()` hook, then renders a per-row chip showing
 * the primary channel icon + tooltip explaining the reasoning.
 *
 * Turns Aria from black-box into an auditable copilot:
 *   "Starting with Email because your USA B2B SaaS preset says
 *    Email → LinkedIn → Phone."
 */
const CHANNEL_ICON = {
  whatsapp: ChatTeardropDots,
  email: Envelope,
  linkedin: LinkedinLogo,
  sms: DeviceMobile,
  phone: Phone,
  website_chat: ChatCircle,
};

const CHANNEL_LABEL = {
  whatsapp: 'WhatsApp',
  email: 'Email',
  linkedin: 'LinkedIn',
  sms: 'SMS',
  phone: 'Phone / AI Call',
  website_chat: 'Website Chat',
};

const CHANNEL_VERB = {
  whatsapp: 'WhatsApp message',
  email: 'email',
  linkedin: 'LinkedIn touch',
  sms: 'SMS',
  phone: 'phone call',
  website_chat: 'website chat',
};

const PRESET_LABEL = {
  india_founder_led: 'India Founder-Led Sales',
  usa_b2b_saas: 'USA B2B SaaS',
  uae_high_ticket: 'UAE High-Ticket Sales',
  d2c_ecom: 'D2C / E-commerce',
  enterprise: 'Enterprise Sales',
  webinar_funnel: 'Webinar Funnel',
  outbound_sales: 'Outbound Sales',
};


/** Hook — returns the channel recommendations (or null while loading). */
export function useChannelRecommendations() {
  const [data, setData] = useState(null);
  const [preset, setPreset] = useState(null);
  useEffect(() => {
    Promise.all([
      api.get('/api/tenant/sales-channels/recommendations').then((r) => r.data).catch(() => null),
      api.get('/api/tenant/sales-channels').then((r) => r.data?.selected_preset || null).catch(() => null),
    ]).then(([rec, p]) => { setData(rec); setPreset(p); });
  }, []);
  return { recs: data, preset };
}


/** Inline chip — primary channel icon + hover tooltip. */
export function ChannelHintChip({ recs, preset, leadId }) {
  const [open, setOpen] = useState(false);
  const primary = recs?.primary_channel;
  if (!primary) {
    return (
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); window.location.href = '/settings'; }}
        data-testid={`channel-hint-${leadId}`}
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border bg-slate-50 text-slate-500 border-slate-200 hover:bg-slate-100"
        title="No sales channel preference set yet — click to configure in Settings"
      >
        <Sparkle size={9} weight="duotone" /> Set channel
      </button>
    );
  }
  const Icon = CHANNEL_ICON[primary] || ChatCircle;
  const order = (recs.priority_order || []).map((k) => CHANNEL_LABEL[k] || k).join(' → ');
  const presetLabel = preset && PRESET_LABEL[preset];
  const why = presetLabel
    ? `Aria starts with ${CHANNEL_LABEL[primary]} because your ${presetLabel} preset says ${order}.`
    : `Aria starts with ${CHANNEL_LABEL[primary]} based on your channel priority: ${order}.`;
  const action = recs.workflow_rule?.primary_action || `Open with a ${CHANNEL_VERB[primary] || 'message'}.`;

  return (
    <span className="relative inline-flex">
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); setOpen((o) => !o); }}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        data-testid={`channel-hint-${leadId}`}
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border bg-violet-50 text-violet-700 border-violet-200 hover:bg-violet-100"
      >
        <Icon size={11} weight="duotone" /> {CHANNEL_LABEL[primary]} first
      </button>
      {open && (
        <div
          data-testid={`channel-hint-popover-${leadId}`}
          className="absolute z-30 left-0 top-full mt-1 w-72 p-3 rounded-xl bg-white border border-violet-200 shadow-xl text-left"
          onMouseEnter={() => setOpen(true)}
          onMouseLeave={() => setOpen(false)}
        >
          <div className="flex items-center gap-2 mb-2">
            <div className="w-6 h-6 rounded-lg bg-violet-100 text-violet-600 flex items-center justify-center">
              <Icon size={12} weight="duotone" />
            </div>
            <span className="text-xs font-extrabold text-slate-900">Why {CHANNEL_LABEL[primary]} first?</span>
          </div>
          <p className="text-[11px] text-slate-700 leading-relaxed mb-2">{why}</p>
          <div className="mt-2 p-2 rounded-lg bg-violet-50 border border-violet-100">
            <div className="text-[9px] uppercase tracking-wider font-extrabold text-violet-700 mb-0.5">Aria's first move</div>
            <div className="text-[11px] text-slate-900">{action}</div>
            {recs.workflow_rule?.fallback_chain?.length > 0 && (
              <div className="text-[10px] text-slate-600 mt-1 flex items-start gap-1">
                <Info size={10} className="mt-0.5 shrink-0" />
                <span>If no reply: {recs.workflow_rule.fallback_chain.join(' → ')}</span>
              </div>
            )}
          </div>
          <a
            href="/settings"
            onClick={(e) => e.stopPropagation()}
            className="block mt-2 text-[10px] font-extrabold uppercase tracking-wider text-violet-600 hover:text-violet-700"
          >
            Edit in Settings →
          </a>
        </div>
      )}
    </span>
  );
}
