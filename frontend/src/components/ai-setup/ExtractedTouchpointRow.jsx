// Inline editor row for a single doc-shape touchpoint.
// Extracted from AISetupAssistant.js (iter73 + iter75 split).
// data-testid contracts preserved.
import React, { useEffect, useState } from 'react';
import { Subhead, FieldInput } from './atoms';

export default function ExtractedTouchpointRow({ index, tp, onUpdate, onRemove }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(tp);

  useEffect(() => {
    // If parent reloads the extraction (e.g. user re-uploads), refresh the draft.
    // Guard: don't clobber the user's in-progress edits while editor is open.
    if (!editing) setDraft(tp);
  }, [tp, editing]);

  const save = () => {
    const cleanedSteps = (draft.flow_steps || []).map((s) => String(s).trim()).filter(Boolean);
    onUpdate({ ...draft, flow_steps: cleanedSteps });
    setEditing(false);
  };
  const cancel = () => {
    setDraft(tp);
    setEditing(false);
  };

  if (!editing) {
    return (
      <div data-testid={`tp-extracted-${index}`} className="border border-violet-200 bg-white rounded-lg p-3 group">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="font-semibold text-violet-900 text-sm">{tp.entry_point || <em className="text-slate-400 font-normal">Unnamed touchpoint</em>}</div>
          <div className="flex items-center gap-1">
            {tp.channel_or_tool && (
              <span className="text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-violet-100 text-violet-700">{tp.channel_or_tool}</span>
            )}
            <button
              type="button"
              onClick={() => setEditing(true)}
              data-testid={`tp-extracted-${index}-edit`}
              className="text-[10px] font-bold text-violet-700 hover:text-violet-900 hover:underline px-1.5 py-0.5"
            >
              Edit
            </button>
          </div>
        </div>
        {tp.timeline && <div className="text-[11px] text-slate-500 mt-0.5">{tp.timeline}</div>}
        {tp.flow_steps?.length > 0 && (
          <ul className="mt-1.5 list-disc list-inside text-xs text-slate-700 space-y-0.5">
            {tp.flow_steps.map((s, j) => <li key={j}>{s}</li>)}
          </ul>
        )}
        {tp.outcome && <p className="text-[11px] text-slate-600 italic mt-2">Outcome: {tp.outcome}</p>}
      </div>
    );
  }

  // Edit view
  return (
    <div data-testid={`tp-extracted-${index}-editor`} className="border border-violet-300 bg-violet-50/40 rounded-lg p-3 space-y-2">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        <FieldInput
          label="Entry point"
          value={draft.entry_point || ''}
          onChange={(v) => setDraft({ ...draft, entry_point: v })}
          testid={`tp-extracted-${index}-entry`}
          placeholder="e.g. Cold email - Saleshandy"
        />
        <FieldInput
          label="Channel or tool"
          value={draft.channel_or_tool || ''}
          onChange={(v) => setDraft({ ...draft, channel_or_tool: v })}
          testid={`tp-extracted-${index}-channel`}
          placeholder="e.g. Saleshandy"
        />
      </div>
      <FieldInput
        label="Timeline"
        value={draft.timeline || ''}
        onChange={(v) => setDraft({ ...draft, timeline: v })}
        testid={`tp-extracted-${index}-timeline`}
        placeholder="e.g. Day 1-12"
      />
      <div>
        <Subhead label="Flow steps" />
        <div className="space-y-1.5">
          {(draft.flow_steps || []).map((step, j) => (
            <div key={j} className="flex items-center gap-1.5">
              <input
                type="text"
                value={step}
                onChange={(e) => {
                  const next = [...(draft.flow_steps || [])];
                  next[j] = e.target.value;
                  setDraft({ ...draft, flow_steps: next });
                }}
                data-testid={`tp-extracted-${index}-step-${j}`}
                className="flex-1 text-xs bg-white border border-violet-200 rounded px-2 py-1.5 focus:outline-none focus:border-violet-500"
                placeholder={`Step ${j + 1}`}
              />
              <button
                type="button"
                onClick={() => {
                  const next = (draft.flow_steps || []).filter((_, k) => k !== j);
                  setDraft({ ...draft, flow_steps: next });
                }}
                data-testid={`tp-extracted-${index}-step-${j}-remove`}
                className="text-[10px] text-rose-600 hover:text-rose-800 px-1.5 py-1"
                title="Remove this step"
              >
                ×
              </button>
            </div>
          ))}
          <button
            type="button"
            onClick={() => setDraft({ ...draft, flow_steps: [...(draft.flow_steps || []), ''] })}
            data-testid={`tp-extracted-${index}-add-step`}
            className="text-[11px] font-bold text-violet-700 hover:text-violet-900"
          >
            + Add step
          </button>
        </div>
      </div>
      <div>
        <Subhead label="Outcome" />
        <textarea
          value={draft.outcome || ''}
          onChange={(e) => setDraft({ ...draft, outcome: e.target.value })}
          data-testid={`tp-extracted-${index}-outcome`}
          rows={2}
          className="w-full text-xs bg-white border border-violet-200 rounded px-2 py-1.5 focus:outline-none focus:border-violet-500"
          placeholder="What happens after this flow runs"
        />
      </div>
      <div className="flex items-center justify-between pt-1">
        <button
          type="button"
          onClick={onRemove}
          data-testid={`tp-extracted-${index}-delete`}
          className="text-[11px] font-bold text-rose-600 hover:text-rose-800"
        >
          Delete touchpoint
        </button>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={cancel}
            data-testid={`tp-extracted-${index}-cancel`}
            className="text-[11px] font-bold text-slate-600 hover:bg-slate-100 px-3 py-1.5 rounded"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={save}
            data-testid={`tp-extracted-${index}-save`}
            className="text-[11px] font-bold bg-violet-600 text-white hover:bg-violet-700 px-3 py-1.5 rounded"
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
}
