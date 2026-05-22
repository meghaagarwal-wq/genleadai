// Iter78 — S4: Touchpoint Pipeline view (5 fixed stages).
// Replaces the Timeline as the default `/touchpoint-journey` rendering.
// Stage segmentation is by 1-indexed `day` field: 1-4 / 5-10 / 11-18 / 19-26 / 27-32.
import React from 'react';
import {
  EnvelopeSimple, ChatTeardropText, LinkedinLogo, Phone, PhoneCall, Globe, ChartLine,
  Lightning, Plus, Sparkle,
} from '@phosphor-icons/react';

const STAGES = [
  { key: 'first_contact',  label: 'First Contact', range: [1, 4],   tint: 'from-violet-50 to-violet-100/40', border: 'border-violet-200', accent: 'text-violet-700' },
  { key: 'education',      label: 'Education',     range: [5, 10],  tint: 'from-sky-50 to-sky-100/40',       border: 'border-sky-200',    accent: 'text-sky-700' },
  { key: 'nurture',        label: 'Nurture',       range: [11, 18], tint: 'from-amber-50 to-amber-100/40',   border: 'border-amber-200',  accent: 'text-amber-700' },
  { key: 'conversion',     label: 'Conversion',    range: [19, 26], tint: 'from-emerald-50 to-emerald-100/40', border: 'border-emerald-200', accent: 'text-emerald-700' },
  { key: 'revival',        label: 'Revival',       range: [27, 32], tint: 'from-rose-50 to-rose-100/40',     border: 'border-rose-200',   accent: 'text-rose-700' },
];

const CHANNEL_ICON = {
  email:    EnvelopeSimple,
  whatsapp: ChatTeardropText,
  linkedin: LinkedinLogo,
  sms:      Phone,
  call:     PhoneCall,
  ads:      Globe,
  analytics:ChartLine,
};

function PipelineCard({ tp, idx, onSelect, isSelected, onDragStart }) {
  const Icon = CHANNEL_ICON[tp.channel] || EnvelopeSimple;
  const condCount = Object.keys(tp.conditions || {}).length || (tp.condition_count || 0);
  const preview = (tp.message_template || tp.subject || '').slice(0, 80);
  return (
    <button
      type="button"
      draggable
      onDragStart={(e) => {
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', String(idx));
        if (onDragStart) onDragStart(idx);
      }}
      onClick={() => onSelect(idx)}
      data-testid={`pipeline-tp-${idx}`}
      className={`w-full text-left bg-white border rounded-xl p-3 hover:shadow-md transition-all cursor-grab active:cursor-grabbing ${
        isSelected ? 'border-violet-500 ring-2 ring-violet-300' : 'border-slate-200'
      }`}
    >
      <div className="flex items-center justify-between mb-1.5 gap-2">
        <div className="flex items-center gap-1.5">
          <span className="w-6 h-6 rounded-full bg-violet-50 text-violet-700 text-[10px] font-bold flex items-center justify-center">
            {idx + 1}
          </span>
          <span className="text-[10px] uppercase tracking-wider font-bold text-slate-600">
            Day {tp.day}
          </span>
        </div>
        <Icon size={14} weight="duotone" className="text-slate-500" />
      </div>
      <div className="text-xs text-slate-700 line-clamp-2 leading-relaxed mb-1.5">
        {preview || <em className="text-slate-400">No message yet</em>}
      </div>
      {condCount > 0 && (
        <div className="inline-flex items-center gap-1 text-[10px] font-bold text-violet-700 bg-violet-50 px-1.5 py-0.5 rounded">
          <Lightning size={9} weight="fill" /> {condCount} branch{condCount === 1 ? '' : 'es'}
        </div>
      )}
    </button>
  );
}

export default function JourneyPipelineView({ touchpoints, selectedIdx, onSelect, onAddAtDay, onMoveTpToStage }) {
  const [dragOverStage, setDragOverStage] = React.useState(null);
  return (
    <div data-testid="pipeline-view" className="grid grid-cols-1 lg:grid-cols-5 gap-3">
      {STAGES.map((stage) => {
        const [from, to] = stage.range;
        const stageCards = (touchpoints || [])
          .map((tp, originalIdx) => ({ tp, originalIdx }))
          .filter(({ tp }) => (tp.day || 1) >= from && (tp.day || 1) <= to)
          .sort((a, b) => (a.tp.day || 0) - (b.tp.day || 0));

        return (
          <div
            key={stage.key}
            data-testid={`pipeline-stage-${stage.key}`}
            onDragOver={(e) => { e.preventDefault(); setDragOverStage(stage.key); }}
            onDragLeave={() => setDragOverStage((s) => s === stage.key ? null : s)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOverStage(null);
              const movedIdx = Number(e.dataTransfer.getData('text/plain'));
              if (!Number.isNaN(movedIdx) && onMoveTpToStage) {
                const targetDay = from + Math.floor((to - from) / 2);
                onMoveTpToStage(movedIdx, targetDay);
              }
            }}
            className={`rounded-2xl border ${stage.border} bg-gradient-to-b ${stage.tint} p-3 flex flex-col min-h-[200px] transition-all ${dragOverStage === stage.key ? 'ring-4 ring-violet-400 ring-offset-1' : ''}`}
          >
            <div className="flex items-center justify-between mb-3 pb-2 border-b border-white/40">
              <div>
                <div className={`text-xs font-extrabold uppercase tracking-wider ${stage.accent}`}>
                  {stage.label}
                </div>
                <div className="text-[10px] text-slate-500">
                  Day {from}–{to} · {stageCards.length} card{stageCards.length === 1 ? '' : 's'}
                </div>
              </div>
            </div>

            <div className="space-y-2 flex-1 overflow-y-auto max-h-[60vh] pr-1">
              {stageCards.length === 0 ? (
                <div className="text-[11px] text-slate-400 italic text-center py-4">
                  No touchpoints in this stage yet.
                </div>
              ) : (
                stageCards.map(({ tp, originalIdx }) => (
                  <PipelineCard
                    key={originalIdx}
                    tp={tp}
                    idx={originalIdx}
                    onSelect={onSelect}
                    isSelected={selectedIdx === originalIdx}
                  />
                ))
              )}
            </div>

            <button
              type="button"
              onClick={() => onAddAtDay && onAddAtDay(from + Math.floor((to - from) / 2))}
              data-testid={`pipeline-add-${stage.key}`}
              className="mt-3 w-full inline-flex items-center justify-center gap-1 text-[11px] font-bold text-violet-700 hover:text-violet-900 hover:bg-white/60 rounded-lg py-2 border border-dashed border-violet-300"
            >
              <Plus size={11} weight="bold" /> Add to {stage.label}
            </button>
          </div>
        );
      })}
    </div>
  );
}

JourneyPipelineView.Sparkle = Sparkle;
