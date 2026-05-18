/**
 * Shared Sales Channels picker — used by both the Onboarding wizard step
 * and the Settings → Sales Channels tab.
 *
 * Props:
 *   - value: current prefs object ({selected_channels, priority_order, conversation_style, selected_preset})
 *   - onChange(newValue): called whenever any field changes
 *   - showRecommendations (bool, default true): show the post-selection integration list
 *
 * Drag-and-drop reorder uses native HTML5 DnD (no extra deps).
 */
import React, { useEffect, useState } from 'react';
import {
  ChatTeardropDots, Envelope, LinkedinLogo, ChatCircle, Phone, DeviceMobile,
  ArrowsClockwise, Lightning, ArrowRight, CheckCircle, ListBullets, Sparkle,
} from '@phosphor-icons/react';
import api from '../../config/api';

const CHANNEL_ICON = {
  whatsapp: ChatTeardropDots,
  email: Envelope,
  linkedin: LinkedinLogo,
  sms: DeviceMobile,
  phone: Phone,
  website_chat: ChatCircle,
};

export default function SalesChannelsPicker({ value, onChange, showRecommendations = true }) {
  const [catalog, setCatalog] = useState({ channels: [], styles: [], presets: [] });
  const [recs, setRecs] = useState(null);
  const [dragKey, setDragKey] = useState(null);

  useEffect(() => {
    api.get('/api/sales-channels/catalog').then((r) => setCatalog(r.data)).catch(() => {});
  }, []);

  // Preview recommendations as the user picks channels (debounced via React state)
  useEffect(() => {
    if (!showRecommendations) return;
    // Computed client-side so it works before any PUT; the server-side endpoint
    // is for post-save use (touchpoint generator etc.)
    const order = value?.priority_order || value?.selected_channels || [];
    const primary = order[0];
    setRecs({
      primary_channel: primary,
      priority_order: order,
      recommendations: deriveRecommendations(order),
    });
  }, [value, showRecommendations]);

  const selected = value?.selected_channels || [];
  const priority = value?.priority_order || selected;
  const style = value?.conversation_style || null;
  const preset = value?.selected_preset || null;

  const toggleChannel = (key) => {
    const isOn = selected.includes(key);
    let nextSelected = isOn ? selected.filter((c) => c !== key) : [...selected, key];
    let nextPriority = priority.filter((c) => nextSelected.includes(c));
    if (!isOn && !nextPriority.includes(key)) nextPriority.push(key);
    onChange({
      ...value,
      selected_channels: nextSelected,
      priority_order: nextPriority,
      selected_preset: null,  // user is editing manually
    });
  };

  const applyPreset = (p) => {
    const allowed = new Set(catalog.channels.map((c) => c.key));
    const order = p.priority_order.filter((c) => allowed.has(c));
    onChange({
      ...value,
      selected_channels: order,
      priority_order: order,
      conversation_style: p.style,
      selected_preset: p.key,
    });
  };

  const setStyle = (k) => onChange({ ...value, conversation_style: k });

  // Drag-and-drop reorder
  const onDragStart = (key) => setDragKey(key);
  const onDragOver = (e) => e.preventDefault();
  const onDrop = (overKey) => {
    if (!dragKey || dragKey === overKey) return;
    const next = [...priority];
    const from = next.indexOf(dragKey);
    const to = next.indexOf(overKey);
    if (from < 0 || to < 0) return;
    next.splice(to, 0, next.splice(from, 1)[0]);
    onChange({ ...value, priority_order: next, selected_preset: null });
    setDragKey(null);
  };

  return (
    <div className="space-y-6" data-testid="sales-channels-picker">
      {/* Preset shortcuts */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <div>
            <h4 className="text-sm font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Not sure what to choose? Start with a preset.</h4>
            <p className="text-[11px] text-[#5A4A7A] mt-0.5">Pick a recommended setup based on your market — you can edit anytime.</p>
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2" data-testid="channel-presets">
          {(catalog.presets || []).map((p) => {
            const active = preset === p.key;
            return (
              <button
                key={p.key}
                type="button"
                data-testid={`preset-${p.key}`}
                onClick={() => applyPreset(p)}
                className={`text-left p-3 rounded-xl border transition-all ${
                  active
                    ? 'bg-violet-50 border-violet-400 ring-2 ring-violet-200'
                    : 'bg-white border-slate-200 hover:border-violet-300'
                }`}
              >
                <div className="text-xs font-extrabold text-slate-900">{p.label}</div>
                <div className="mt-1 flex items-center gap-1 flex-wrap">
                  {p.priority_order.map((c, i) => (
                    <React.Fragment key={c}>
                      <span className="text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-slate-100 text-slate-700">{labelFor(catalog.channels, c)}</span>
                      {i < p.priority_order.length - 1 && <ArrowRight size={9} className="text-slate-400" />}
                    </React.Fragment>
                  ))}
                </div>
              </button>
            );
          })}
        </div>
      </section>

      {/* Channel selection */}
      <section>
        <div className="mb-3">
          <h4 className="text-sm font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Where should Aria talk to your leads?</h4>
          <p className="text-[11px] text-[#5A4A7A] mt-0.5">Choose the sales channels your audience actually responds to. You can pick more than one — Aria will prioritise based on your selected order.</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2" data-testid="channel-grid">
          {(catalog.channels || []).map((c) => {
            const Icon = CHANNEL_ICON[c.key] || ChatCircle;
            const isOn = selected.includes(c.key);
            return (
              <button
                key={c.key}
                type="button"
                data-testid={`channel-${c.key}`}
                onClick={() => toggleChannel(c.key)}
                className={`text-left p-3 rounded-xl border transition-all flex items-start gap-3 ${
                  isOn
                    ? 'bg-violet-50 border-violet-400 ring-2 ring-violet-200'
                    : 'bg-white border-slate-200 hover:border-violet-300'
                }`}
              >
                <div className={`shrink-0 w-9 h-9 rounded-lg flex items-center justify-center ${isOn ? 'bg-violet-100 text-violet-600' : 'bg-slate-100 text-slate-500'}`}>
                  <Icon size={16} weight="duotone" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm font-bold text-slate-900">{c.label}</span>
                    {isOn && <CheckCircle size={12} weight="fill" className="text-emerald-500" />}
                  </div>
                  <div className="text-[11px] text-slate-600 mt-0.5 leading-snug">{c.blurb}</div>
                </div>
              </button>
            );
          })}
        </div>
      </section>

      {/* Priority drag-reorder */}
      {priority.length > 1 && (
        <section data-testid="priority-section">
          <div className="mb-3">
            <h4 className="text-sm font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Set channel priority</h4>
            <p className="text-[11px] text-[#5A4A7A] mt-0.5">Aria will try the first channel. If the lead doesn't respond, she'll move to the next. Drag to reorder.</p>
          </div>
          <ol className="space-y-2" data-testid="priority-list">
            {priority.map((k, idx) => {
              const Icon = CHANNEL_ICON[k] || ChatCircle;
              const isDragging = dragKey === k;
              return (
                <li
                  key={k}
                  draggable
                  onDragStart={() => onDragStart(k)}
                  onDragOver={onDragOver}
                  onDrop={() => onDrop(k)}
                  data-testid={`priority-item-${k}`}
                  className={`flex items-center gap-3 p-3 rounded-xl border bg-white cursor-grab active:cursor-grabbing ${
                    isDragging ? 'opacity-50 border-violet-400' : 'border-slate-200 hover:border-violet-300'
                  }`}
                >
                  <ListBullets size={12} className="text-slate-400" />
                  <span className={`shrink-0 w-7 h-7 rounded-full text-[11px] font-extrabold flex items-center justify-center ${
                    idx === 0 ? 'bg-violet-500 text-white' : 'bg-slate-100 text-slate-600'
                  }`}>{idx + 1}</span>
                  <Icon size={16} weight="duotone" className="text-violet-600" />
                  <span className="text-sm font-bold text-slate-900">{labelFor(catalog.channels, k)}</span>
                  {idx === 0 && (
                    <span className="ml-auto text-[10px] uppercase tracking-wider font-extrabold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                      Primary
                    </span>
                  )}
                </li>
              );
            })}
          </ol>
        </section>
      )}

      {/* Conversation style */}
      <section>
        <div className="mb-3">
          <h4 className="text-sm font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>How should Aria communicate?</h4>
          <p className="text-[11px] text-[#5A4A7A] mt-0.5">Sets the default tone across every message Aria sends.</p>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2" data-testid="style-grid">
          {(catalog.styles || []).map((s) => {
            const active = style === s.key;
            return (
              <button
                key={s.key}
                type="button"
                data-testid={`style-${s.key}`}
                onClick={() => setStyle(s.key)}
                className={`text-left p-3 rounded-xl border transition-all ${
                  active
                    ? 'bg-violet-50 border-violet-400 ring-2 ring-violet-200'
                    : 'bg-white border-slate-200 hover:border-violet-300'
                }`}
              >
                <div className="text-xs font-extrabold text-slate-900">{s.label}</div>
                <div className="text-[11px] text-slate-600 mt-0.5 leading-snug">{s.blurb}</div>
              </button>
            );
          })}
        </div>
      </section>

      {/* Recommended integrations preview */}
      {showRecommendations && recs && recs.recommendations.length > 0 && (
        <section
          data-testid="channel-recommendations"
          className="bg-gradient-to-br from-violet-50 to-fuchsia-50 border border-violet-200 rounded-2xl p-4"
        >
          <div className="flex items-center gap-2 mb-2">
            <Sparkle size={14} weight="duotone" className="text-violet-600" />
            <h4 className="text-sm font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Recommended integrations for your sales flow</h4>
          </div>
          <p className="text-[11px] text-[#5A4A7A] mb-3">Based on your channels, Aria recommends these tools. You'll connect them in the Integration Hub.</p>
          <div className="flex flex-wrap gap-1.5">
            {recs.recommendations.slice(0, 10).map((r) => (
              <span
                key={r.type}
                data-testid={`rec-${r.type}`}
                className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold border ${
                  r.live
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    : 'bg-white text-slate-700 border-slate-200'
                }`}
              >
                {r.label}
                {r.live && <span className="text-[9px] font-extrabold uppercase tracking-wider text-emerald-600">Live</span>}
              </span>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function labelFor(channels, key) {
  return (channels.find((c) => c.key === key) || {}).label || key;
}

// Client-side mirror of the backend's channel→integrations mapping. Used to
// show a *preview* of recommendations before the user clicks save.
const CHANNEL_INTEGRATIONS_PREVIEW = {
  whatsapp: [{ type: 'whatsapp_biz', label: 'WhatsApp Business API', live: false }],
  email: [
    { type: 'gmail', label: 'Gmail', live: false },
    { type: 'outlook', label: 'Outlook', live: false },
    { type: 'zoho_mail', label: 'Zoho Mail', live: false },
    { type: 'saleshandy', label: 'Saleshandy', live: true },
    { type: 'instantly', label: 'Instantly.ai', live: true },
    { type: 'smartlead', label: 'Smartlead', live: false },
  ],
  linkedin: [
    { type: 'lemlist', label: 'Lemlist', live: true },
    { type: 'phantombuster', label: 'PhantomBuster', live: false },
    { type: 'sales_navigator', label: 'LinkedIn Sales Navigator', live: false },
  ],
  sms: [
    { type: 'twilio_sms', label: 'SMS (Twilio)', live: false },
    { type: 'msg91_sms', label: 'SMS (MSG91)', live: false },
  ],
  phone: [
    { type: 'twilio_sms', label: 'Twilio Voice (via Twilio)', live: false },
    { type: 'exotel', label: 'Exotel', live: false },
  ],
  website_chat: [{ type: 'website_chat', label: 'Website Chat', live: false }],
};

function deriveRecommendations(priority) {
  const seen = new Set();
  const out = [];
  for (const ch of priority) {
    for (const r of (CHANNEL_INTEGRATIONS_PREVIEW[ch] || [])) {
      if (seen.has(r.type)) continue;
      seen.add(r.type);
      out.push({ ...r, channel: ch });
    }
  }
  return out;
}
