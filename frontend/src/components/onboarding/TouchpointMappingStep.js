/**
 * TouchpointMappingStep — onboarding Step 3B.
 *
 * Auto-generates a lead touchpoint journey from the in-progress onboarding
 * form state, lets the user accept it as-is or customise (drag/edit/add/remove)
 * before continuing to WhatsApp setup.
 *
 * Saves the chosen map to /api/touchpoints/map on confirm.
 */
import React, { useEffect, useMemo, useState } from 'react';
import api from '../../config/api';
import {
  ChatCircle, EnvelopeSimple, Phone, LinkedinLogo, Sparkle,
  CheckCircle, PencilSimple, Trash, Plus, ArrowsClockwise,
} from '@phosphor-icons/react';
import { toast } from 'sonner';

// ─── Channel + role visual config ────────────────────────────────────────────
const CHANNEL_META = {
  whatsapp: { label: 'WhatsApp', color: '#25D366', icon: ChatCircle },
  email: { label: 'Email', color: '#0055FF', icon: EnvelopeSimple },
  call_reminder: { label: 'Call', color: '#F97316', icon: Phone },
  linkedin_nudge: { label: 'LinkedIn', color: '#7C35DC', icon: LinkedinLogo },
};

const TYPE_LABELS = {
  intro: 'Intro', qualifier: 'Qualifier', value_drop: 'Value Drop',
  follow_up: 'Follow-up', social_proof: 'Social Proof', soft_cta: 'Soft CTA',
  budget_probe: 'Budget Probe', meeting_cta: 'Meeting CTA',
  human_escalation: 'Human Escalation', re_engagement: 'Re-engagement',
  urgency: 'Urgency', closure: 'Closure',
};

// ─── Client-side selection mirroring backend logic ───────────────────────────
function clientSelect(business, sales) {
  const industry = (business?.industry || '').trim();
  const market = (business?.primary_market || 'B2B').trim();
  const cycle = (sales?.sales_cycle || '1-4 weeks').trim();
  const dealSize = (sales?.deal_size || '50K - 5L').trim();

  if (industry === 'Events') return 'tpl_urgency_led';
  if (industry === 'Real Estate') return 'tpl_high_intent_qualifier';
  if (industry === 'E-commerce' && market === 'B2C') return 'tpl_abandoned_interest';
  if (market === 'B2C' && cycle === '< 1 week' && dealSize === '< 50K') return 'tpl_fast_conversion';
  if (market === 'B2C' && (cycle === '< 1 week' || cycle === '1-4 weeks')) return 'tpl_warm_nurture';
  if ((market === 'B2B' || market === 'Both') && (cycle === '1-4 weeks' || cycle === '1-3 months')) return 'tpl_considered_sale';
  if ((market === 'B2B' || market === 'Both') && cycle === '3+ months') return 'tpl_enterprise_track';
  return 'tpl_standard';
}

const CHANNELS = ['whatsapp', 'email', 'call_reminder', 'linkedin_nudge'];
const TYPES = Object.keys(TYPE_LABELS);
const ROLES = ['autonomous', 'alert_human'];

const TouchpointMappingStep = ({ form, onSaved, onSkip }) => {
  const [allTemplates, setAllTemplates] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [touchpoints, setTouchpoints] = useState([]);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  // Load templates once on mount, then auto-select using form state
  useEffect(() => {
    let alive = true;
    api.get('/api/touchpoints/templates').then((r) => {
      if (!alive) return;
      const tpls = r.data?.templates || [];
      setAllTemplates(tpls);
      const id = clientSelect(form.business, form.sales);
      const tpl = tpls.find((t) => t.id === id) || tpls.find((t) => t.id === 'tpl_standard') || tpls[0];
      if (tpl) {
        setSelectedId(tpl.id);
        setTouchpoints(JSON.parse(JSON.stringify(tpl.touchpoints || [])));
      }
    }).catch(() => {
      toast.error('Could not load touchpoint templates');
    });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectedTemplate = useMemo(
    () => allTemplates.find((t) => t.id === selectedId),
    [allTemplates, selectedId],
  );

  const updateTp = (idx, patch) => {
    setTouchpoints((arr) => arr.map((t, i) => (i === idx ? { ...t, ...patch } : t)));
  };
  const removeTp = (idx) => {
    setTouchpoints((arr) => arr.filter((_, i) => i !== idx).map((t, i) => ({ ...t, index: i })));
  };
  const addTp = () => {
    setTouchpoints((arr) => [
      ...arr,
      {
        index: arr.length,
        day: arr.length > 0 ? Math.ceil(arr[arr.length - 1].day) + 1 : 0,
        hour: 0,
        channel: 'whatsapp',
        message_type: 'follow_up',
        aria_role: 'autonomous',
        trigger: '',
        message_template: 'Hi {{first_name}}, ',
      },
    ]);
  };
  const moveTp = (idx, dir) => {
    setTouchpoints((arr) => {
      const next = [...arr];
      const j = idx + dir;
      if (j < 0 || j >= next.length) return arr;
      [next[idx], next[j]] = [next[j], next[idx]];
      return next.map((t, i) => ({ ...t, index: i }));
    });
  };
  const resetToRecommended = () => {
    if (!selectedTemplate) return;
    setTouchpoints(JSON.parse(JSON.stringify(selectedTemplate.touchpoints || [])));
    setEditing(false);
    toast.success('Restored to recommended journey');
  };

  const save = async () => {
    setSaving(true);
    try {
      const isCustomised = editing && JSON.stringify(touchpoints) !== JSON.stringify(selectedTemplate?.touchpoints || []);
      const payload = {
        template_id: selectedId,
        is_customised: isCustomised,
        touchpoints: touchpoints.map((t, i) => ({
          index: i,
          day: Number(t.day) || 0,
          hour: Number(t.hour) || 0,
          channel: t.channel,
          message_type: t.message_type,
          aria_role: t.aria_role,
          trigger: t.trigger || '',
          message_template: t.message_template,
        })),
      };
      await api.post('/api/touchpoints/map', payload);
      toast.success(isCustomised ? 'Custom journey saved' : 'Journey activated');
      onSaved?.();
    } catch (err) {
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Could not save journey');
    } finally {
      setSaving(false);
    }
  };

  const dayLabel = (t) => {
    if (t.day === 0 && t.hour === 0) return 'Day 0 · Instant';
    if (t.day === 0) return `Day 0 · +${t.hour}h`;
    return `Day ${t.day}${t.hour ? ` · +${t.hour}h` : ''}`;
  };

  return (
    <>
      <div className="text-sm text-[#5A4A7A] mb-3 flex items-start gap-2" data-testid="ob-touchpoint-intro">
        <Sparkle size={14} weight="fill" className="text-[#7C35DC] flex-shrink-0 mt-0.5" />
        <div>
          <strong className="text-[#1A0A2E]">Aria has mapped your lead journey.</strong> Based on your business profile, here's how Aria will engage every new lead — automatically.
        </div>
      </div>

      {selectedTemplate && (
        <div className="flex flex-wrap items-center gap-2 mb-4" data-testid="ob-touchpoint-badge">
          <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold border"
            style={{ background: 'linear-gradient(135deg, #FFF7ED, #FEF3C7)', borderColor: '#F59E0B', color: '#92400E' }}>
            📋 Template: <span className="font-extrabold">{selectedTemplate.name}</span>
          </div>
          <span className="text-xs text-[#5A4A7A]">
            {touchpoints.length} touchpoints · {selectedTemplate.duration_days}-day journey
          </span>
        </div>
      )}

      {!editing && (
        <div className="space-y-2 max-h-[340px] overflow-y-auto pr-1" data-testid="ob-touchpoint-timeline">
          {touchpoints.map((t, idx) => {
            const meta = CHANNEL_META[t.channel] || CHANNEL_META.whatsapp;
            const Icon = meta.icon;
            return (
              <div key={idx} className="bg-white border border-[#E8E0F5] rounded-lg p-3 flex items-start gap-3 hover:border-[#7C35DC]/40 transition" data-testid={`ob-touchpoint-card-${idx}`}>
                <div className="w-9 h-9 rounded-md flex-shrink-0 flex items-center justify-center" style={{ background: `${meta.color}1A`, color: meta.color }}>
                  <Icon size={16} weight="fill" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center flex-wrap gap-1.5">
                    <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#7C35DC]">{dayLabel(t)}</span>
                    <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#5A4A7A]">· {meta.label}</span>
                    <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#5A4A7A]">· {TYPE_LABELS[t.message_type] || t.message_type}</span>
                    {t.aria_role === 'alert_human' ? (
                      <span className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-[0.1em]" style={{ background: '#FEF3C7', color: '#92400E', border: '1px solid #F59E0B' }}>Alert you</span>
                    ) : (
                      <span className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-[0.1em]" style={{ background: '#EFF6FF', color: '#1D4ED8', border: '1px solid #3B82F6' }}>Aria handles</span>
                    )}
                  </div>
                  <div className="text-xs text-[#1A0A2E] mt-1 line-clamp-2">{t.message_template}</div>
                  {t.trigger && <div className="text-[10px] text-[#9B8AB0] mt-0.5">Trigger: {t.trigger}</div>}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {editing && (
        <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1" data-testid="ob-touchpoint-editor">
          <div className="text-xs text-[#5A4A7A] mb-2">
            <strong>You're in control.</strong> Edit, reorder, add or remove any touchpoint. Tokens like <code>{'{{first_name}}'}</code>, <code>{'{{product}}'}</code>, <code>{'{{company}}'}</code> are auto-filled at send time.
          </div>
          {touchpoints.map((t, idx) => (
            <div key={idx} className="bg-white border border-[#E8E0F5] rounded-lg p-3 space-y-2" data-testid={`ob-touchpoint-edit-${idx}`}>
              <div className="flex items-center gap-1.5">
                <button type="button" onClick={() => moveTp(idx, -1)} disabled={idx === 0}
                  className="px-1.5 py-1 rounded text-[#5A4A7A] hover:text-[#7C35DC] disabled:opacity-30" title="Move up">↑</button>
                <button type="button" onClick={() => moveTp(idx, 1)} disabled={idx === touchpoints.length - 1}
                  className="px-1.5 py-1 rounded text-[#5A4A7A] hover:text-[#7C35DC] disabled:opacity-30" title="Move down">↓</button>
                <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#7C35DC]">#{idx + 1}</span>
                <div className="ml-auto" />
                <button type="button" onClick={() => removeTp(idx)} data-testid={`ob-touchpoint-remove-${idx}`}
                  className="px-1.5 py-1 rounded text-[#DC2626] hover:bg-[#DC2626]/10" title="Remove"><Trash size={12} /></button>
              </div>
              <div className="grid grid-cols-4 gap-1.5">
                <label className="text-[9px] font-bold uppercase tracking-[0.14em] text-[#5A4A7A] block">
                  Day
                  <input type="number" min={0} step={0.5} value={t.day}
                    onChange={(e) => updateTp(idx, { day: Number(e.target.value) })}
                    className="w-full mt-1 bg-white border border-[#E8E0F5] text-[#1A0A2E] px-2 py-1.5 rounded text-xs" />
                </label>
                <label className="text-[9px] font-bold uppercase tracking-[0.14em] text-[#5A4A7A] block">
                  Hour
                  <input type="number" min={0} max={23} value={t.hour}
                    onChange={(e) => updateTp(idx, { hour: Number(e.target.value) })}
                    className="w-full mt-1 bg-white border border-[#E8E0F5] text-[#1A0A2E] px-2 py-1.5 rounded text-xs" />
                </label>
                <label className="text-[9px] font-bold uppercase tracking-[0.14em] text-[#5A4A7A] block col-span-2">
                  Channel
                  <select value={t.channel} onChange={(e) => updateTp(idx, { channel: e.target.value })}
                    className="w-full mt-1 bg-white border border-[#E8E0F5] text-[#1A0A2E] px-2 py-1.5 rounded text-xs">
                    {CHANNELS.map((c) => <option key={c} value={c}>{CHANNEL_META[c].label}</option>)}
                  </select>
                </label>
              </div>
              <div className="grid grid-cols-2 gap-1.5">
                <label className="text-[9px] font-bold uppercase tracking-[0.14em] text-[#5A4A7A] block">
                  Type
                  <select value={t.message_type} onChange={(e) => updateTp(idx, { message_type: e.target.value })}
                    className="w-full mt-1 bg-white border border-[#E8E0F5] text-[#1A0A2E] px-2 py-1.5 rounded text-xs">
                    {TYPES.map((m) => <option key={m} value={m}>{TYPE_LABELS[m]}</option>)}
                  </select>
                </label>
                <label className="text-[9px] font-bold uppercase tracking-[0.14em] text-[#5A4A7A] block">
                  Aria role
                  <select value={t.aria_role} onChange={(e) => updateTp(idx, { aria_role: e.target.value })}
                    className="w-full mt-1 bg-white border border-[#E8E0F5] text-[#1A0A2E] px-2 py-1.5 rounded text-xs">
                    {ROLES.map((r) => <option key={r} value={r}>{r === 'autonomous' ? 'Aria handles' : 'Alert me'}</option>)}
                  </select>
                </label>
              </div>
              <textarea rows={2} value={t.message_template}
                onChange={(e) => updateTp(idx, { message_template: e.target.value })}
                placeholder="Message template — Aria uses this as the intent at send time"
                className="w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-2 py-1.5 rounded text-xs resize-y" />
            </div>
          ))}
          <div className="flex flex-wrap items-center gap-2 pt-2">
            <button type="button" onClick={addTp} data-testid="ob-touchpoint-add"
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-bold border border-dashed border-[#7C35DC]/40 text-[#7C35DC] hover:bg-[#7C35DC]/5">
              <Plus size={12} /> Add touchpoint
            </button>
            <button type="button" onClick={resetToRecommended} data-testid="ob-touchpoint-reset"
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-bold text-[#5A4A7A] hover:text-[#7C35DC]">
              <ArrowsClockwise size={12} /> Reset to recommended
            </button>
          </div>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t border-[#F0ECF9]">
        {!editing ? (
          <>
            <button type="button" onClick={save} disabled={saving} data-testid="ob-touchpoint-accept"
              className="flex items-center gap-1.5 px-4 py-2.5 rounded-lg text-white text-sm font-bold disabled:opacity-50"
              style={{ background: 'linear-gradient(135deg, #4C1D95, #7C35DC)' }}>
              <CheckCircle size={14} weight="fill" />
              {saving ? 'Saving…' : 'Looks good — use this'}
            </button>
            <button type="button" onClick={() => setEditing(true)} data-testid="ob-touchpoint-customise"
              className="flex items-center gap-1.5 px-4 py-2.5 rounded-lg text-sm font-bold border border-[#7C35DC] text-[#7C35DC] bg-white hover:bg-[#F4F0FF]">
              <PencilSimple size={14} weight="fill" /> Customise my journey
            </button>
          </>
        ) : (
          <>
            <button type="button" onClick={save} disabled={saving} data-testid="ob-touchpoint-save-custom"
              className="flex items-center gap-1.5 px-4 py-2.5 rounded-lg text-white text-sm font-bold disabled:opacity-50"
              style={{ background: 'linear-gradient(135deg, #4C1D95, #7C35DC)' }}>
              <CheckCircle size={14} weight="fill" />
              {saving ? 'Saving…' : 'Save my custom journey'}
            </button>
            <button type="button" onClick={() => setEditing(false)} data-testid="ob-touchpoint-cancel-edit"
              className="px-4 py-2.5 rounded-lg text-sm font-bold border border-[#E8E0F5] text-[#5A4A7A] bg-white hover:border-[#7C35DC]/40">
              Cancel
            </button>
          </>
        )}
        {onSkip && (
          <button type="button" onClick={onSkip} data-testid="ob-touchpoint-skip"
            className="ml-auto text-xs font-bold uppercase tracking-[0.14em] text-[#9B8AB0] hover:text-[#7C35DC]">
            Skip for now
          </button>
        )}
      </div>
    </>
  );
};

export default TouchpointMappingStep;
