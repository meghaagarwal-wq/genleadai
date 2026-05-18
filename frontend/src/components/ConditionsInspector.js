import React from 'react';
import {
  ChatCircle, Sparkle, Warning, Clock, Lightning,
} from '@phosphor-icons/react';

/**
 * ConditionsInspector — shared 4-branch conditional logic editor.
 *
 * Used by both:
 *   - /outreach — Outreach Campaign builder (per-step branching)
 *   - /touchpoint-journey — the 32-step master journey (per-touchpoint branching)
 *
 * Schema mirrors backend `routes.outreach.validate_conditions`:
 *   {
 *     on_reply: {action: 'move_to_step'|'notify_user'|'tag_contact'|'stop', target_step?, tag?},
 *     on_keyword_match: {keywords: [...], action: 'tag_contact'|'move_to_step'|..., tag?, target_step?},
 *     on_negative_keyword: {keywords: [...], action: 'stop'|'tag_contact', tag?},
 *     on_no_reply: {after_hours: N, action: 'move_to_step'|'stop', target_step?},
 *   }
 */
const BRANCH_DEFS = [
  { key: 'on_reply', label: 'When lead replies', tint: 'border-sky-300 bg-sky-50', icon: <ChatCircle size={14} className="text-sky-600" /> },
  { key: 'on_keyword_match', label: 'When reply contains keyword', tint: 'border-emerald-300 bg-emerald-50', icon: <Sparkle size={14} className="text-emerald-600" />, hasKeywords: true },
  { key: 'on_negative_keyword', label: 'When reply is negative', tint: 'border-rose-300 bg-rose-50', icon: <Warning size={14} className="text-rose-600" />, hasKeywords: true, restrictedActions: ['stop', 'tag_contact'] },
  { key: 'on_no_reply', label: 'If no reply within hours', tint: 'border-amber-300 bg-amber-50', icon: <Clock size={14} className="text-amber-600" />, hasAfterHours: true, restrictedActions: ['move_to_step', 'stop'] },
];

export default function ConditionsInspector({
  conditions = {},
  maxStep = 32,
  currentStep = 1,
  onChange,
}) {
  const toggle = (key, defaults) => {
    if (conditions[key]) {
      const { [key]: _omit, ...rest } = conditions;
      onChange(rest);
    } else {
      onChange({ ...conditions, [key]: defaults });
    }
  };

  return (
    <div data-testid="conditions-inspector" className="space-y-2">
      <h3 className="text-xs font-semibold text-slate-700 mb-1.5 flex items-center gap-1.5">
        <Lightning size={12} /> Branching logic
        <span className="text-slate-400 font-normal normal-case">— Aria fires the first matching branch</span>
      </h3>

      {BRANCH_DEFS.map((b) => {
        const enabled = !!conditions[b.key];
        const value = conditions[b.key] || {};
        const defaultsForBranch = b.key === 'on_no_reply'
          ? { after_hours: 72, action: 'move_to_step', target_step: Math.min(currentStep + 1, maxStep) }
          : b.key === 'on_keyword_match'
          ? { keywords: ['interested', 'pricing'], action: 'tag_contact', tag: 'hot_lead' }
          : b.key === 'on_negative_keyword'
          ? { keywords: ['not interested', 'stop'], action: 'stop' }
          : { action: 'notify_user' };

        return (
          <div
            key={b.key}
            data-testid={`conditions-branch-${b.key}`}
            className={`rounded-xl border-2 transition-all ${enabled ? b.tint : 'border-slate-200 bg-white'}`}
          >
            <button
              type="button"
              onClick={() => toggle(b.key, defaultsForBranch)}
              data-testid={`conditions-branch-toggle-${b.key}`}
              className="w-full flex items-center justify-between px-4 py-2.5 text-left"
            >
              <div className="flex items-center gap-2 text-sm">
                {b.icon}
                <span className="font-medium text-slate-900">{b.label}</span>
              </div>
              <div className={`w-9 h-5 rounded-full transition-colors ${enabled ? 'bg-violet-600' : 'bg-slate-300'} relative`}>
                <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all ${enabled ? 'left-[18px]' : 'left-0.5'}`} />
              </div>
            </button>

            {enabled && (
              <div className="px-4 pb-3 pt-1 space-y-2 border-t border-white/60">
                {b.hasAfterHours && (
                  <Inline label="After">
                    <input
                      type="number"
                      min={1}
                      value={value.after_hours || 72}
                      onChange={(e) => onChange({ ...conditions, [b.key]: { ...value, after_hours: parseInt(e.target.value, 10) || 1 } })}
                      data-testid={`conditions-branch-${b.key}-hours`}
                      className="w-20 px-2 py-1 rounded border border-slate-300 text-xs bg-white"
                    />
                    <span className="text-xs text-slate-600">hours of silence</span>
                  </Inline>
                )}

                {b.hasKeywords && (
                  <Inline label="Keywords">
                    <input
                      type="text"
                      value={(value.keywords || []).join(', ')}
                      onChange={(e) => onChange({ ...conditions, [b.key]: { ...value, keywords: e.target.value.split(',').map((k) => k.trim()).filter(Boolean) } })}
                      data-testid={`conditions-branch-${b.key}-keywords`}
                      placeholder="interested, pricing, demo"
                      className="flex-1 px-2 py-1 rounded border border-slate-300 text-xs bg-white"
                    />
                  </Inline>
                )}

                <Inline label="Then">
                  <select
                    value={value.action || 'notify_user'}
                    onChange={(e) => onChange({ ...conditions, [b.key]: { ...value, action: e.target.value } })}
                    data-testid={`conditions-branch-${b.key}-action`}
                    className="px-2 py-1 rounded border border-slate-300 text-xs bg-white"
                  >
                    {(b.restrictedActions || ['move_to_step', 'notify_user', 'tag_contact', 'stop']).map((a) => (
                      <option key={a} value={a}>{a}</option>
                    ))}
                  </select>

                  {value.action === 'move_to_step' && (
                    <>
                      <span className="text-xs text-slate-600">to step</span>
                      <input
                        type="number"
                        min={1}
                        max={maxStep}
                        value={value.target_step || 2}
                        onChange={(e) => onChange({ ...conditions, [b.key]: { ...value, target_step: parseInt(e.target.value, 10) || 1 } })}
                        data-testid={`conditions-branch-${b.key}-target`}
                        className="w-16 px-2 py-1 rounded border border-slate-300 text-xs bg-white"
                      />
                    </>
                  )}

                  {value.action === 'tag_contact' && (
                    <>
                      <span className="text-xs text-slate-600">with tag</span>
                      <input
                        type="text"
                        value={value.tag || ''}
                        onChange={(e) => onChange({ ...conditions, [b.key]: { ...value, tag: e.target.value } })}
                        data-testid={`conditions-branch-${b.key}-tag`}
                        placeholder="hot_lead"
                        className="w-32 px-2 py-1 rounded border border-slate-300 text-xs bg-white font-mono"
                      />
                    </>
                  )}
                </Inline>

                {/* Plain-English summary — helps founders read the branch back without scanning JSON */}
                <PlainEnglishSummary branchKey={b.key} value={value} />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function Inline({ label, children }) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold w-16">{label}</span>
      {children}
    </div>
  );
}

function PlainEnglishSummary({ branchKey, value }) {
  const sentence = describe(branchKey, value);
  if (!sentence) return null;
  return (
    <div data-testid={`conditions-summary-${branchKey}`} className="text-[11px] text-slate-600 italic pt-1 border-t border-white/60">
      <span className="not-italic mr-1">→</span>{sentence}
    </div>
  );
}

function describe(branchKey, v) {
  const action = v?.action;
  const tag = v?.tag;
  const target = v?.target_step;
  const keywords = (v?.keywords || []).slice(0, 3);
  const kwText = keywords.length ? `"${keywords.join('", "')}"` : 'a keyword';
  const hours = v?.after_hours;

  if (branchKey === 'on_reply') {
    if (action === 'stop') return 'When the lead replies, stop the journey.';
    if (action === 'notify_user') return 'When the lead replies, notify me.';
    if (action === 'tag_contact') return `When the lead replies, tag them ${tag ? `"${tag}"` : '...'}.`;
    if (action === 'move_to_step') return `When the lead replies, jump to step ${target}.`;
  }
  if (branchKey === 'on_keyword_match') {
    if (action === 'tag_contact') return `If the reply contains ${kwText}, tag the contact ${tag ? `"${tag}"` : '...'}.`;
    if (action === 'move_to_step') return `If the reply contains ${kwText}, jump to step ${target}.`;
    if (action === 'notify_user') return `If the reply contains ${kwText}, notify me.`;
    if (action === 'stop') return `If the reply contains ${kwText}, stop the journey.`;
  }
  if (branchKey === 'on_negative_keyword') {
    if (action === 'stop') return `If the reply contains ${kwText}, stop the journey (lead is not interested).`;
    if (action === 'tag_contact') return `If the reply contains ${kwText}, tag the contact ${tag ? `"${tag}"` : '...'}.`;
  }
  if (branchKey === 'on_no_reply') {
    if (action === 'stop') return `If no reply within ${hours} hours, stop the journey.`;
    if (action === 'move_to_step') return `If no reply within ${hours} hours, jump to step ${target}.`;
  }
  return null;
}
