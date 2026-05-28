// Review stage of the AI Setup Assistant — extracted from AISetupAssistant.js
// (iter75 split). All data-testid attrs preserved verbatim.
import React from 'react';
import {
  Sparkle, ArrowRight, Target, MapTrifold, Lightning, Bell, Warning,
  X, Rocket, ChatTeardropDots, FunnelSimple, CheckCircle,
} from '@phosphor-icons/react';
import { Card, FieldInline, Subhead, ChipList } from './atoms';
import ExtractedTouchpointRow from './ExtractedTouchpointRow';

export default function ReviewPanel({
  extracted, diff, onChange, onPublish, onAskAria, askingAria, suggestions,
  showSuggestions,
  publishing, overwriteJourney, setOverwriteJourney, filename, onStartOver,
  overwriteWarning, onDismissWarning,
}) {
  const updateField = (path, val) => {
    const next = JSON.parse(JSON.stringify(extracted));
    let ref = next;
    const keys = path.slice(0, -1);
    for (const k of keys) ref = ref[k];
    ref[path[path.length - 1]] = val;
    onChange(next);
  };

  return (
    <div className="space-y-5">
      {/* Aria summary */}
      <div className="bg-gradient-to-br from-violet-50 to-indigo-50 border border-violet-200 rounded-2xl p-5 flex items-start gap-3">
        <Sparkle size={20} weight="duotone" className="text-violet-600 flex-shrink-0 mt-0.5" />
        <div className="flex-1">
          <p className="text-xs uppercase tracking-wider text-violet-700 font-semibold mb-1">Aria says</p>
          <p className="text-sm text-slate-700 leading-relaxed">{extracted.summary || 'Review the extracted sections below, then publish.'}</p>
          <p className="text-[10px] text-slate-500 mt-2">From: <strong>{filename}</strong></p>
        </div>
        <button onClick={onStartOver} className="text-xs text-slate-500 hover:text-rose-600 px-2 py-1 rounded">
          <X size={14} /> Start over
        </button>
      </div>

      {/* Diff vs. current workspace */}
      {diff && (diff.icp_changes?.length > 0 || diff.touchpoint_diff) && (
        <div data-testid="auto-map-diff-card" className="bg-white border border-sky-200 bg-sky-50/40 rounded-2xl p-4 flex items-start gap-3">
          <ChatTeardropDots size={18} weight="duotone" className="text-sky-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1 text-xs text-slate-700">
            <div className="text-[10px] uppercase tracking-wider text-sky-700 font-semibold mb-1">What will change if you publish</div>
            <p>{diff.summary}</p>
            <div className="flex flex-wrap gap-1.5 mt-2">
              {diff.icp_changes?.filter((c) => c.action === 'create').map((c, i) => (
                <span key={i} className="text-[10px] px-2 py-0.5 rounded bg-emerald-100 text-emerald-700 border border-emerald-200">+ {c.label}</span>
              ))}
              {diff.icp_changes?.filter((c) => c.action === 'skip_exists').map((c, i) => (
                <span key={`s${i}`} className="text-[10px] px-2 py-0.5 rounded bg-slate-100 text-slate-500 border border-slate-200">= {c.label}</span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Not-found banner */}
      {(extracted.not_found || []).length > 0 && (
        <div
          data-testid="auto-map-not-found-banner"
          className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex gap-3"
        >
          <div className="text-amber-700">
            <Warning size={18} weight="duotone" />
          </div>
          <div className="flex-1">
            <div className="text-xs font-bold uppercase tracking-wider text-amber-700 mb-1">
              Not found in uploaded document
            </div>
            <p className="text-xs text-amber-900 leading-relaxed">
              Aria couldn't extract these sections because the document didn't mention them:&nbsp;
              <strong>{extracted.not_found.join(', ')}</strong>. You can fill these in manually
              after publishing — Aria will not guess.
            </p>
          </div>
        </div>
      )}

      {/* CARD 1: ICPs */}
      <Card
        testid="auto-map-card-icps"
        icon={<Target size={16} weight="duotone" />}
        title={`${(extracted.icps || []).length} ICP${(extracted.icps || []).length === 1 ? '' : 's'} detected`}
        tint="violet"
      >
        {(extracted.icps || []).length === 0 ? (
          <p className="text-xs text-slate-400">No ICPs detected — Aria couldn't infer a buyer persona from the doc.</p>
        ) : (
          <div className="space-y-3">
            {extracted.icps.map((icp, i) => (
              <div key={i} className="bg-white border border-slate-200 rounded-xl p-3" data-testid={`auto-map-icp-${i}`}>
                <div className="grid grid-cols-2 gap-3 mb-2">
                  <FieldInline label="Label" value={icp.label} onChange={(v) => updateField(['icps', i, 'label'], v)} />
                  <FieldInline label="Industry" value={icp.industry} onChange={(v) => updateField(['icps', i, 'industry'], v)} />
                  <FieldInline label="Company size" value={icp.company_size} onChange={(v) => updateField(['icps', i, 'company_size'], v)} />
                  <FieldInline label="Geography" value={icp.geography} onChange={(v) => updateField(['icps', i, 'geography'], v)} />
                </div>
                <FieldInline label="Pain point" value={icp.pain_point} onChange={(v) => updateField(['icps', i, 'pain_point'], v)} multiline />
                <FieldInline label="Value prop" value={icp.value_prop} onChange={(v) => updateField(['icps', i, 'value_prop'], v)} multiline />
                <div className="mt-2 flex flex-wrap gap-1">
                  {(icp.title_targets || []).map((t) => (
                    <span key={t} className="text-[10px] px-2 py-0.5 rounded bg-violet-50 text-violet-700 border border-violet-200">{t}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* CARD 2: Lead sources */}
      <Card
        testid="auto-map-card-sources"
        icon={<FunnelSimple size={16} weight="duotone" />}
        title={`${(extracted.lead_sources || []).length} lead source${(extracted.lead_sources || []).length === 1 ? '' : 's'} detected`}
        tint="emerald"
      >
        {(extracted.lead_sources || []).length === 0 ? (
          <p className="text-xs text-slate-400">No lead sources detected in the document.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {extracted.lead_sources.map((s, i) => (
              <span key={i} className="text-xs px-3 py-1.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">{s}</span>
            ))}
          </div>
        )}
      </Card>

      {/* CARD 2b: Recommended integrations */}
      <Card
        testid="auto-map-card-integrations"
        icon={<FunnelSimple size={16} weight="duotone" />}
        title={`${(extracted.recommended_integrations || []).length} integration${(extracted.recommended_integrations || []).length === 1 ? '' : 's'} recommended`}
        tint="indigo"
      >
        {(extracted.recommended_integrations || []).length === 0 ? (
          <p className="text-xs text-slate-400">Aria didn't spot any specific tools (Saleshandy, Lemlist, Zoho, Calendly, etc.) in the document. You can connect any tool from the Integration Hub later.</p>
        ) : (
          <div className="space-y-2">
            <div className="flex flex-wrap gap-2">
              {extracted.recommended_integrations.map((s, i) => (
                <span
                  key={i}
                  data-testid={`auto-map-integration-${s}`}
                  className="text-xs px-3 py-1.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200 font-mono"
                >
                  {s}
                </span>
              ))}
            </div>
            <p className="text-[11px] text-slate-500">Head to <strong>Integration Hub</strong> after publishing to paste API keys + import campaigns/leads from these tools.</p>
          </div>
        )}
      </Card>

      {/* CARD 2c: Sales channels */}
      <Card
        testid="auto-map-card-sales-channels"
        icon={<FunnelSimple size={16} weight="duotone" />}
        title={`${(extracted.sales_channels || []).length} sales channel${(extracted.sales_channels || []).length === 1 ? '' : 's'} suggested`}
        tint="violet"
      >
        {(extracted.sales_channels || []).length === 0 ? (
          <p className="text-xs text-slate-400">Aria didn't infer specific channels (email / linkedin / whatsapp) from the document.</p>
        ) : (
          <div className="space-y-2">
            <div className="flex flex-wrap gap-2">
              {extracted.sales_channels.map((s, i) => (
                <span
                  key={i}
                  data-testid={`auto-map-sales-channel-${s}`}
                  className={`text-xs px-3 py-1.5 rounded-full border font-mono ${i === 0 ? 'bg-violet-100 text-violet-800 border-violet-300' : 'bg-violet-50 text-violet-700 border-violet-200'}`}
                >
                  {i === 0 ? '★ ' : ''}{s}
                </span>
              ))}
            </div>
            <p className="text-[11px] text-slate-500">★ = primary channel. Publishing will save this to your Sales Channel Preferences (overrides any prior selection).</p>
          </div>
        )}
      </Card>

      {/* CARD 3: Touchpoints */}
      <Card
        testid="auto-map-card-touchpoints"
        icon={<MapTrifold size={16} weight="duotone" />}
        title={`${(extracted.touchpoints || []).length} touchpoints mapped`}
        tint="sky"
      >
        {(extracted.touchpoints || []).length === 0 ? (
          <p className="text-xs text-slate-400">No touchpoints generated.</p>
        ) : (
          <div className="space-y-2">
            {extracted.touchpoints.map((tp, i) => (
              <div key={i} className="bg-white border border-slate-200 rounded-lg p-3 flex items-start gap-3" data-testid={`auto-map-tp-${i}`}>
                <div className="w-7 h-7 rounded-full bg-sky-100 text-sky-700 text-xs font-bold flex items-center justify-center flex-shrink-0">{i + 1}</div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className="text-[10px] uppercase tracking-wider font-bold text-slate-700 bg-slate-100 px-2 py-0.5 rounded">{tp.channel}</span>
                    <span className="text-[10px] text-slate-500">{tp.message_type}</span>
                    <span className="text-[10px] text-slate-400">Day {tp.day} · {tp.hour}:00</span>
                    {Object.keys(tp.conditions || {}).length > 0 && (
                      <span className="text-[10px] font-semibold text-violet-700 inline-flex items-center gap-0.5"><Lightning size={9} /> {Object.keys(tp.conditions).length} branch</span>
                    )}
                  </div>
                  <textarea
                    value={tp.message_template || ''}
                    onChange={(e) => updateField(['touchpoints', i, 'message_template'], e.target.value)}
                    rows={2}
                    data-testid={`auto-map-tp-message-${i}`}
                    className="w-full text-xs text-slate-700 bg-slate-50 border border-slate-200 rounded p-2 font-mono resize-none"
                  />
                </div>
              </div>
            ))}
          </div>
        )}

        <label className="flex items-center gap-2 mt-4 text-xs text-slate-700 cursor-pointer">
          <input
            type="checkbox"
            checked={overwriteJourney}
            onChange={(e) => setOverwriteJourney(e.target.checked)}
            data-testid="auto-map-overwrite-toggle"
            className="rounded"
          />
          <span>On publish, replace my current 32-touchpoint journey with this sequence</span>
        </label>
      </Card>

      {/* CARD 4: Qualification + Handoff */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <Card testid="auto-map-card-qualification" icon={<CheckCircle size={16} weight="duotone" />} title="Qualification logic" tint="amber" small>
          <Subhead label="Must-have criteria" />
          <ChipList values={extracted.qualification?.must_have_criteria || []} tint="amber" />
          <Subhead label="Disqualifiers" />
          <ChipList values={extracted.qualification?.disqualifiers || []} tint="rose" />
          <Subhead label="Qualifying questions" />
          <ChipList values={extracted.qualification?.qualifying_questions || []} tint="slate" />
        </Card>

        <Card testid="auto-map-card-handoff" icon={<Bell size={16} weight="duotone" />} title="Sales handoff" tint="rose" small>
          <Subhead label="Trigger" />
          <p className="text-xs text-slate-700">{extracted.handoff?.trigger || <em className="text-slate-400">Not detected</em>}</p>
          <Subhead label="Alert channels" />
          <ChipList values={extracted.handoff?.alert_channels || []} tint="rose" />
          <Subhead label="Info passed" />
          <ChipList values={extracted.handoff?.info_passed || []} tint="slate" />
        </Card>
      </div>

      {/* Touchpoints detected from doc — inline editor */}
      {(extracted.touchpoints_extracted || []).length > 0 && (
        <Card
          testid="auto-map-card-touchpoints-extracted"
          icon={<MapTrifold size={16} weight="duotone" />}
          title={`Touchpoints detected from document (${extracted.touchpoints_extracted.length})`}
          tint="violet"
        >
          <div className="space-y-3">
            {extracted.touchpoints_extracted.map((tp, i) => (
              <ExtractedTouchpointRow
                key={i}
                index={i}
                tp={tp}
                onUpdate={(next) => {
                  const arr = [...(extracted.touchpoints_extracted || [])];
                  arr[i] = next;
                  onChange({ ...extracted, touchpoints_extracted: arr });
                }}
                onRemove={() => {
                  const arr = (extracted.touchpoints_extracted || []).filter((_, j) => j !== i);
                  onChange({ ...extracted, touchpoints_extracted: arr });
                }}
              />
            ))}
          </div>
        </Card>
      )}

      {/* Conditional logic */}
      {(extracted.conditional_logic || []).length > 0 && (
        <Card
          testid="auto-map-card-conditional-logic"
          icon={<Lightning size={16} weight="duotone" />}
          title={`Conditional logic (${extracted.conditional_logic.length})`}
          tint="indigo"
        >
          <div className="space-y-2">
            {extracted.conditional_logic.map((c, i) => (
              <div key={i} data-testid={`cond-logic-${i}`} className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] items-center gap-2 bg-white border border-indigo-200 rounded-lg p-3 text-xs">
                <div><span className="text-[10px] uppercase font-bold text-indigo-700">Trigger</span><div className="text-slate-800">{c.trigger}</div></div>
                <ArrowRight size={14} className="text-indigo-400 mx-auto" />
                <div><span className="text-[10px] uppercase font-bold text-indigo-700">Action</span><div className="text-slate-800">{c.action}</div></div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Scoring + signals */}
      {((extracted.scoring_thresholds || []).length > 0 || (extracted.signal_scores || []).length > 0) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {(extracted.scoring_thresholds || []).length > 0 && (
            <Card testid="auto-map-card-scoring-thresholds" icon={<Target size={16} weight="duotone" />} title="Scoring thresholds" tint="emerald" small>
              <div className="space-y-1.5">
                {extracted.scoring_thresholds.map((s, i) => (
                  <div key={i} data-testid={`scoring-threshold-${i}`} className="flex items-center justify-between gap-2 text-xs">
                    <span className="font-mono text-emerald-700">{s.score_range}</span>
                    <span className="font-semibold text-slate-800">{s.stage}</span>
                    <span className="text-slate-600 text-right flex-1 truncate" title={s.action}>{s.action}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}
          {(extracted.signal_scores || []).length > 0 && (
            <Card testid="auto-map-card-signal-scores" icon={<Lightning size={16} weight="duotone" />} title="Key signal scores" tint="amber" small>
              <div className="space-y-1.5">
                {extracted.signal_scores.map((s, i) => (
                  <div key={i} data-testid={`signal-score-${i}`} className="flex items-center justify-between gap-2 text-xs">
                    <span className="text-slate-700">{s.signal}</span>
                    <span className="font-mono font-bold text-amber-700">{s.score_or_rule}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}

      {/* Sales handoff (from doc) */}
      {extracted.sales_handoff && (extracted.sales_handoff.handoff_triggers?.length > 0 || extracted.sales_handoff.handoff_owner?.length > 0) && (
        <Card testid="auto-map-card-sales-handoff" icon={<Bell size={16} weight="duotone" />} title="Sales handoff (from doc)" tint="rose" small>
          {extracted.sales_handoff.handoff_triggers?.length > 0 && (<><Subhead label="Triggers" /><ChipList values={extracted.sales_handoff.handoff_triggers} tint="rose" /></>)}
          {extracted.sales_handoff.handoff_owner?.length > 0 && (<><Subhead label="Owner(s)" /><ChipList values={extracted.sales_handoff.handoff_owner} tint="violet" /></>)}
          {extracted.sales_handoff.handoff_timeline?.length > 0 && (<><Subhead label="Timeline" /><ChipList values={extracted.sales_handoff.handoff_timeline} tint="slate" /></>)}
          {extracted.sales_handoff.manual_takeover_rules?.length > 0 && (<><Subhead label="Manual takeover" /><ChipList values={extracted.sales_handoff.manual_takeover_rules} tint="slate" /></>)}
        </Card>
      )}

      {/* Needs review */}
      {(extracted.needs_review || []).length > 0 && (
        <Card testid="auto-map-card-needs-review" icon={<Warning size={16} weight="duotone" />} title={`Needs review (${extracted.needs_review.length})`} tint="amber" small>
          <ul className="text-xs text-slate-700 space-y-1">
            {extracted.needs_review.map((nr, i) => (
              <li key={i} data-testid={`needs-review-${i}`}><strong>{nr.field}:</strong> {nr.reason}</li>
            ))}
          </ul>
        </Card>
      )}

      {/* Suggestions */}
      {showSuggestions && suggestions.length > 0 && (
        <Card testid="auto-map-suggestions" icon={<Warning size={16} weight="duotone" />} title={`Aria's improvement suggestions (${suggestions.length})`} tint="amber">
          <div className="space-y-2">
            {suggestions.map((s, i) => (
              <div key={i} className="bg-amber-50 border border-amber-200 rounded-lg p-3" data-testid={`auto-map-suggestion-${i}`}>
                <div className="text-[10px] uppercase tracking-wider font-bold text-amber-700 mb-1">{(s.type || 'tip').replace(/_/g, ' ')}</div>
                <p className="text-sm text-slate-800">{s.message}</p>
                {s.fix_hint && <p className="text-xs text-slate-600 mt-1 italic">→ {s.fix_hint}</p>}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Empty-overwrite warning modal */}
      {overwriteWarning && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" data-testid="empty-overwrite-modal">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl">
            <div className="flex items-start gap-3">
              <Warning size={24} weight="duotone" className="text-rose-600 flex-shrink-0" />
              <div className="flex-1">
                <h3 className="text-base font-bold text-slate-900">Existing journey detected</h3>
                <p className="text-sm text-slate-700 mt-2 leading-relaxed">{overwriteWarning.message}</p>
                <p className="text-xs text-slate-500 mt-2">Recommended: cancel, retry extraction, or pick a doc that contains a Touchpoint Mapping section.</p>
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 mt-5">
              <button onClick={onDismissWarning} data-testid="empty-overwrite-cancel" className="px-4 py-2 rounded-lg text-xs font-bold text-slate-600 hover:bg-slate-100">
                Cancel
              </button>
              <button onClick={() => { onDismissWarning(); onPublish(true); }} data-testid="empty-overwrite-confirm" className="px-4 py-2 rounded-lg text-xs font-bold bg-rose-600 text-white hover:bg-rose-700">
                Publish anyway
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Sticky action bar */}
      <div className="sticky bottom-4 bg-white border border-slate-200 shadow-xl rounded-2xl p-4 flex items-center justify-between gap-3 flex-wrap">
        <button
          type="button"
          onClick={onAskAria}
          disabled={askingAria}
          data-testid="auto-map-ask-aria-btn"
          className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-lg text-xs font-medium bg-amber-50 border border-amber-200 text-amber-700 hover:bg-amber-100 disabled:opacity-50"
        >
          <Sparkle size={14} weight="duotone" /> {askingAria ? 'Aria is thinking…' : 'Ask Aria to Improve This Journey'}
        </button>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onStartOver}
            className="px-4 py-2.5 rounded-lg text-xs text-slate-600 hover:bg-slate-100"
          >Cancel</button>
          <button
            type="button"
            onClick={() => onPublish()}
            disabled={publishing}
            data-testid="auto-map-publish-btn"
            className="inline-flex items-center gap-1.5 px-5 py-2.5 rounded-lg bg-slate-900 text-white text-sm font-medium hover:bg-slate-800 disabled:opacity-50"
          >
            <Rocket size={14} weight="bold" /> {publishing ? 'Publishing…' : 'Publish Workflow'} <ArrowRight size={12} />
          </button>
        </div>
      </div>
    </div>
  );
}
