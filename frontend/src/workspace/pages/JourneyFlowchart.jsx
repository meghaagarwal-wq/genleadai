/**
 * JourneyFlowchart — visual 3-column flowchart for the 32-touchpoint journey.
 *
 * Layout
 *   ┌────────────────────────────────────────────────────────────────────┐
 *   │  STAGE BANNER  · First Contact (1-4) · Education · Nurture · …    │
 *   ├────────────────────────────────────────────────────────────────────┤
 *   │  JOURNEY STRENGTH · grade · touchpoints · sent · replies · score   │
 *   ├────────────────────────────────────────────────────────────────────┤
 *   │  Legend     ─ Linear   ─ Branch (yes)   ─ Branch (stop/tag)        │
 *   │                                                                    │
 *   │   [START]                                                          │
 *   │      │                                                             │
 *   │   ┌──▼──┐   ┌─────────┐    ┌────────┐                              │
 *   │   │STEP │──▶│ COND    │───▶│ ACTION │                              │
 *   │   │ 1   │   │ if-no-… │    │ alert  │                              │
 *   │   └──┬──┘   └─────────┘    └────────┘                              │
 *   │      │ yes                                                         │
 *   │   ┌──▼──┐   ┌─────────┐    ┌────────┐                              │
 *   │   │STEP │──▶│ COND    │───▶│ ACTION │                              │
 *   │   │ 2   │   │         │    │        │                              │
 *   │   └─────┘   └─────────┘    └────────┘                              │
 *   │                                                                    │
 *   │                                              [ mini-map ]          │
 *   │                                          ┌──────────────┐          │
 *   │                                          │ ▌▌▌▌  ━━━    │          │
 *   │                                          └──────────────┘          │
 *   │                                                ⊕ ⊖ ⛶               │
 *   └────────────────────────────────────────────────────────────────────┘
 *
 * Renders the same `touchpoints` array used by the other views — derives
 * the condition and action chips from `conditional_logic` text.
 */
import { useMemo, useRef, useState, useEffect } from 'react';
import {
  EnvelopeSimple, WhatsappLogo, LinkedinLogo, ChatCircleText, PhoneCall,
  Lightning, Bell, Tag, StopCircle, Sparkle, Plus, Minus, ArrowsOut, Download,
  Share, DotsThree, MagnifyingGlass, DotsSixVertical,
} from '@phosphor-icons/react';

// ─── Static config ──────────────────────────────────────────────────────
const CHANNEL_STYLE = {
  whatsapp: { color: '#16A34A', dim: 'rgba(22,163,74,0.10)', Icon: WhatsappLogo,    label: 'WhatsApp' },
  email:    { color: '#3B82F6', dim: 'rgba(59,130,246,0.10)', Icon: EnvelopeSimple,  label: 'Email'    },
  linkedin: { color: '#0A66C2', dim: 'rgba(10,102,194,0.10)', Icon: LinkedinLogo,    label: 'LinkedIn' },
  sms:      { color: '#f59e0b', dim: 'rgba(245,158,11,0.12)', Icon: ChatCircleText,  label: 'SMS'      },
  call:     { color: '#f97316', dim: 'rgba(249,115,22,0.12)', Icon: PhoneCall,       label: 'Call'     },
};

// Touchpoint number → stage. Matches the reference layout.
const STAGES = [
  { id: 'first_contact', label: 'First Contact',  range: [1, 4],   sub: 'Instant reply · introduction · first qualifier.',     accent: '#3B82F6' },
  { id: 'education',     label: 'Education',      range: [5, 10],  sub: 'Brochure · pitch deck · case study · proof.',         accent: '#06B6D4' },
  { id: 'nurture',       label: 'Nurture',        range: [11, 18], sub: 'Follow-ups · objection handling · social proof.',     accent: '#8B5CF6' },
  { id: 'conversion',    label: 'Conversion',     range: [19, 26], sub: 'Demo invite · pricing · calendar · founder handoff.', accent: '#16A34A' },
  { id: 'revival',       label: 'Revival',        range: [27, 32], sub: 'Re-engage · new offer · soft close · archive.',       accent: '#EF4444' },
];

// Geometry — kept constants so SVG edges line up with cards.
const COL_X = { step: 32,  cond: 360, action: 660 };
const COL_W = { step: 260, cond: 230, action: 200 };
const ROW_H = 130;
const ROW_GAP = 16;
const CANVAS_PAD_TOP = 80;
const CANVAS_PAD_BOTTOM = 60;


// ─── Helpers ────────────────────────────────────────────────────────────
const stageForNumber = (n) => STAGES.find((s) => n >= s.range[0] && n <= s.range[1]) || STAGES[0];

const deriveCondition = (tp) => {
  // Parse the conditional_logic string for a short trigger label.
  const cl = (tp.conditional_logic || '').toLowerCase();
  if (!cl) return null;
  if (cl.includes('no reply') || cl.includes('no response')) {
    return { label: 'If no reply', detail: /(\d+\s*(h|hours|hrs|days?))/i.exec(tp.conditional_logic)?.[0] || `After ${tp.timing || 'silence'}` };
  }
  if (cl.includes('negative') || cl.includes('not interested') || cl.includes('unsubscrib')) {
    return { label: 'When reply is negative', detail: 'not interested · stop' };
  }
  if (cl.includes('positive') || cl.includes('interested') || cl.includes('reply')) {
    return { label: 'When reply is positive', detail: 'qualified · book call' };
  }
  if (cl.includes('opened')) {
    return { label: 'If opened, no reply', detail: tp.timing || 'follow up' };
  }
  return { label: 'Continue', detail: tp.timing || '' };
};

const deriveAction = (tp) => {
  const cl = (tp.conditional_logic || '').toLowerCase();
  if (cl.includes('stop') || cl.includes('end') || cl.includes('unsubscrib')) {
    return { kind: 'stop',   label: 'Stop journey', color: '#EF4444', dim: 'rgba(239,68,68,0.10)', Icon: StopCircle };
  }
  if (cl.includes('tag') || cl.includes('warm') || cl.includes('hot') || cl.includes('mark qualified')) {
    const tag = /tag[:\s]+(\w+)/i.exec(tp.conditional_logic)?.[1]
            || (cl.includes('hot') ? 'hot_lead' : cl.includes('warm') ? 'warm_lead' : 'qualified');
    return { kind: 'tag', label: 'Tag contact', sub: `tag: ${tag}`, color: '#EC4899', dim: 'rgba(236,72,153,0.10)', Icon: Tag };
  }
  if (cl.includes('notify') || cl.includes('alert') || cl.includes('founder')) {
    return { kind: 'notify', label: 'Notify me', color: '#F59E0B', dim: 'rgba(245,158,11,0.12)', Icon: Bell };
  }
  return null;
};


// ─── Component ──────────────────────────────────────────────────────────
const JourneyFlowchart = ({ tps, journeyStrength, onScoreWithAI, onPatch, onRegenerate, onReorder }) => {
  const [zoom, setZoom] = useState(1);
  const [dragId, setDragId] = useState(null);     // id of card being dragged
  const [dragOverId, setDragOverId] = useState(null); // id of card hovered
  const containerRef = useRef(null);

  // Pre-compute per-touchpoint geometry so edges and minimap share coords.
  const rows = useMemo(() => tps.map((tp, i) => {
    const y = CANVAS_PAD_TOP + i * (ROW_H + ROW_GAP);
    return {
      tp,
      y,
      cond: deriveCondition(tp),
      action: deriveAction(tp),
      stage: stageForNumber(tp.number),
    };
  }), [tps]);

  const canvasH = CANVAS_PAD_TOP + rows.length * (ROW_H + ROW_GAP) + CANVAS_PAD_BOTTOM;
  const canvasW = COL_X.action + COL_W.action + 60;

  // Stage progress chips (top banner)
  const stageCounts = useMemo(() => STAGES.map((s) => {
    const planned = s.range[1] - s.range[0] + 1;
    const have = tps.filter((t) => t.number >= s.range[0] && t.number <= s.range[1]).length;
    return { ...s, have, planned };
  }), [tps]);

  const grade = journeyStrength?.grade || (tps.length >= 24 ? 'A' : tps.length >= 16 ? 'B' : tps.length >= 8 ? 'C' : 'D');
  const score = journeyStrength?.score ?? Math.min(99.9, tps.length * 3.1);

  // Drag-and-drop reorder: swap source.number ↔ target.number, then
  // rebuild a sequential numbering and bubble up to the parent.
  const handleDragStart = (id) => (e) => {
    setDragId(id);
    try { e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', id); } catch { /* ignore */ }
  };
  const handleDragOver = (id) => (e) => {
    e.preventDefault();
    try { e.dataTransfer.dropEffect = 'move'; } catch { /* ignore */ }
    if (id !== dragOverId) setDragOverId(id);
  };
  const handleDragLeave = () => setDragOverId(null);
  const handleDrop = (targetId) => (e) => {
    e.preventDefault();
    const sourceId = dragId || (() => { try { return e.dataTransfer.getData('text/plain'); } catch { return null; } })();
    setDragId(null); setDragOverId(null);
    if (!sourceId || sourceId === targetId || !onReorder) return;

    const ordered = [...tps].sort((a, b) => (a.number || 0) - (b.number || 0));
    const srcIdx = ordered.findIndex((t) => t.id === sourceId);
    const dstIdx = ordered.findIndex((t) => t.id === targetId);
    if (srcIdx < 0 || dstIdx < 0) return;
    // Move the source card into the destination slot, shifting others.
    const [moved] = ordered.splice(srcIdx, 1);
    ordered.splice(dstIdx, 0, moved);
    // Renumber 1..N sequentially.
    const renumbered = ordered.map((t, i) => ({ ...t, number: i + 1 }));
    onReorder(renumbered);
  };
  const handleDragEnd = () => { setDragId(null); setDragOverId(null); };

  return (
    <div className="space-y-4" data-testid="journey-flowchart-v2">
      {/* ─── Stage banner ─────────────────────────────────────────── */}
      <div
        className="grid grid-cols-2 md:grid-cols-5 gap-3 rounded-xl p-3"
        style={{ background: 'var(--theme-surface)' }}
        data-testid="journey-stage-banner"
      >
        {stageCounts.map((s) => {
          const pct = s.planned ? Math.round((s.have / s.planned) * 100) : 0;
          const tone = s.have === 0 ? '#94a3b8' : s.have >= s.planned ? '#16A34A' : s.accent;
          return (
            <div
              key={s.id}
              className="rounded-lg border p-3 flex flex-col"
              style={{ background: 'var(--theme-surface2)', borderColor: 'var(--theme-border)' }}
              data-testid={`stage-${s.id}`}
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="text-sm font-bold" style={{ color: 'var(--theme-text)', fontFamily: 'Space Grotesk, Inter' }}>{s.label}</div>
                  <div className="text-[10px] mt-0.5 leading-snug" style={{ color: 'var(--theme-text-muted)' }}>{s.sub}</div>
                </div>
                <span
                  className="shrink-0 text-[10px] font-extrabold px-1.5 py-0.5 rounded"
                  style={{ background: tone + '20', color: tone }}
                >
                  {s.have}/{s.planned}
                </span>
              </div>
              <div className="mt-2 h-1 rounded-full overflow-hidden" style={{ background: 'var(--theme-border)' }}>
                <div className="h-full rounded-full" style={{ width: `${pct}%`, background: tone, transition: 'width 0.4s' }} />
              </div>
              <div className="mt-1 text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--theme-text-muted)' }}>
                {s.range[0]}–{s.range[1]}
              </div>
            </div>
          );
        })}
      </div>

      {/* ─── Journey Strength widget ─────────────────────────────── */}
      <div
        className="rounded-xl border p-4 flex flex-wrap items-center gap-4"
        style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }}
        data-testid="journey-strength"
      >
        {/* Score ring */}
        <div className="flex items-center gap-3">
          <ScoreRing score={score} grade={grade} />
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-bold" style={{ color: 'var(--theme-text)', fontFamily: 'Space Grotesk, Inter' }}>Journey strength</h3>
              <span
                className="text-[10px] font-extrabold px-1.5 py-0.5 rounded"
                style={{ background: gradeColor(grade) + '20', color: gradeColor(grade) }}
                data-testid="journey-grade"
              >Grade {grade}</span>
            </div>
            <div className="text-xs mt-0.5 max-w-md" style={{ color: 'var(--theme-text-muted)' }}>
              Live score combining delivery, reply rate and skip rate across all leads who passed through your journey.
            </div>
          </div>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-4">
          <Stat label="Touchpoints" value={tps.length} testid="stat-touchpoints" />
          <Stat label="Sent" value={journeyStrength?.sent ?? 0} testid="stat-sent" />
          <Stat label="Replies" value={journeyStrength?.replies ?? 0} testid="stat-replies" accent="#16A34A" />
          <Stat label="Reply rate" value={`${journeyStrength?.reply_rate_pct ?? 0}%`} testid="stat-reply-rate" />
          <button
            onClick={() => onScoreWithAI?.()}
            data-testid="journey-score-with-ai"
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-xs font-bold text-white"
            style={{ background: 'linear-gradient(135deg, #5b21b6 0%, #7c3aed 60%)' }}
          >
            <Sparkle size={12} weight="fill" /> Score with AI
          </button>
        </div>
      </div>

      {/* ─── Sub-header ──────────────────────────────────────────── */}
      <div className="flex items-center justify-between text-xs" style={{ color: 'var(--theme-text-muted)' }}>
        <div className="flex items-center gap-2">
          <Sparkle size={12} weight="fill" style={{ color: 'var(--theme-purple-light, #7C35DC)' }} />
          <span><b style={{ color: 'var(--theme-text)' }}>{tps.length}</b> / 32 touchpoints — drag to reorder, click any card to edit</span>
        </div>
      </div>

      {/* ─── Legend ──────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-3 text-[10px] uppercase tracking-wider font-bold" style={{ color: 'var(--theme-text-muted)' }}>
        <LegendKey color="#94a3b8" label="Linear" />
        <LegendKey color="#16A34A" label="Branch (yes)" />
        <LegendKey color="#EF4444" label="Branch (stop/tag)" />
        <span className="ml-auto opacity-70">→ Auto-fit zoom in bottom-right</span>
      </div>

      {/* ─── Canvas ──────────────────────────────────────────────── */}
      <div
        ref={containerRef}
        className="relative overflow-auto rounded-xl border"
        style={{
          background: 'var(--theme-surface)',
          borderColor: 'var(--theme-border)',
          maxHeight: 720,
        }}
        data-testid="journey-canvas"
      >
        <div style={{ width: canvasW, height: canvasH, position: 'relative', transform: `scale(${zoom})`, transformOrigin: 'top left' }}>
          {/* SVG edge layer */}
          <svg
            width={canvasW}
            height={canvasH}
            style={{ position: 'absolute', top: 0, left: 0, pointerEvents: 'none' }}
          >
            {/* Start node → first step */}
            {rows.length > 0 && (
              <Edge x1={COL_X.step + COL_W.step / 2} y1={20} x2={COL_X.step + COL_W.step / 2} y2={rows[0].y + 12} color="#94a3b8" />
            )}
            {rows.map((r, i) => (
              <g key={r.tp.id}>
                {/* Step → Cond (horizontal) */}
                {r.cond && (
                  <Edge x1={COL_X.step + COL_W.step} y1={r.y + ROW_H / 2} x2={COL_X.cond} y2={r.y + ROW_H / 2} color="#94a3b8" />
                )}
                {/* Cond → Action (horizontal, coloured by action kind) */}
                {r.cond && r.action && (
                  <Edge
                    x1={COL_X.cond + COL_W.cond}
                    y1={r.y + ROW_H / 2}
                    x2={COL_X.action}
                    y2={r.y + ROW_H / 2}
                    color={r.action.color}
                    label={r.action.kind === 'stop' ? 'alert · stop' : r.action.kind === 'tag' ? 'alert · tag' : 'alert'}
                  />
                )}
                {/* Step i → Step i+1 (yes branch) */}
                {i < rows.length - 1 && (
                  <Edge
                    x1={COL_X.step + COL_W.step / 2}
                    y1={r.y + ROW_H}
                    x2={COL_X.step + COL_W.step / 2}
                    y2={rows[i + 1].y}
                    color="#16A34A"
                    dashed
                    label="yes →"
                  />
                )}
              </g>
            ))}
          </svg>

          {/* Start node */}
          <div
            className="absolute rounded-md flex items-center justify-center text-xs font-extrabold text-white shadow-md"
            style={{
              top: 4, left: COL_X.step + COL_W.step / 2 - 50, width: 100, height: 28,
              background: 'linear-gradient(135deg, #5b21b6 0%, #7c3aed 60%)',
              fontFamily: 'Plus Jakarta Sans',
            }}
            data-testid="journey-start-node"
          >
            ▼ START
          </div>

          {/* Rows */}
          {rows.map((r) => (
            <FlowRow
              key={r.tp.id}
              row={r}
              onPatch={onPatch}
              onRegenerate={onRegenerate}
              draggable={!!onReorder}
              isDragging={dragId === r.tp.id}
              isDragOver={dragOverId === r.tp.id && dragId !== r.tp.id}
              onDragStart={handleDragStart(r.tp.id)}
              onDragOver={handleDragOver(r.tp.id)}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop(r.tp.id)}
              onDragEnd={handleDragEnd}
            />
          ))}
        </div>

        {/* Mini-map */}
        <MiniMap rows={rows} canvasH={canvasH} canvasW={canvasW} containerRef={containerRef} />

        {/* Zoom controls */}
        <div className="absolute right-3 bottom-3 flex flex-col gap-1" data-testid="journey-zoom-controls">
          <CtrlBtn onClick={() => setZoom((z) => Math.min(1.4, z + 0.1))} testid="zoom-in"><Plus size={12} weight="bold" /></CtrlBtn>
          <CtrlBtn onClick={() => setZoom((z) => Math.max(0.5, z - 0.1))} testid="zoom-out"><Minus size={12} weight="bold" /></CtrlBtn>
          <CtrlBtn onClick={() => setZoom(1)} testid="zoom-reset"><ArrowsOut size={12} weight="bold" /></CtrlBtn>
          <CtrlBtn onClick={() => exportJSON(rows)} testid="export-json"><Download size={12} weight="bold" /></CtrlBtn>
        </div>
      </div>
    </div>
  );
};


// ─── Sub-components ─────────────────────────────────────────────────────
const Stat = ({ label, value, testid, accent }) => (
  <div className="text-center" data-testid={testid}>
    <div className="text-[10px] uppercase tracking-wider font-bold" style={{ color: 'var(--theme-text-muted)' }}>{label}</div>
    <div className="text-xl font-extrabold mt-0.5 numeric" style={{ color: accent || 'var(--theme-text)', fontFamily: 'Space Grotesk, Inter' }}>{value}</div>
  </div>
);

const ScoreRing = ({ score, grade }) => {
  const pct = Math.max(0, Math.min(100, Number(score) || 0));
  const r = 28, c = 2 * Math.PI * r;
  const off = c * (1 - pct / 100);
  const col = gradeColor(grade);
  return (
    <div className="relative" style={{ width: 68, height: 68 }}>
      <svg width="68" height="68" viewBox="0 0 68 68" style={{ transform: 'rotate(-90deg)' }}>
        <circle cx="34" cy="34" r={r} fill="none" stroke="var(--theme-border)" strokeWidth="6" />
        <circle cx="34" cy="34" r={r} fill="none" stroke={col} strokeWidth="6" strokeLinecap="round" strokeDasharray={c} strokeDashoffset={off} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center" style={{ fontFamily: 'Space Grotesk, Inter' }}>
        <span className="text-base font-extrabold numeric" style={{ color: 'var(--theme-text)' }}>{Number(score).toFixed(1)}</span>
        <span className="text-[8px] uppercase tracking-wider font-bold" style={{ color: 'var(--theme-text-muted)' }}>/ 100</span>
      </div>
    </div>
  );
};

const LegendKey = ({ color, label }) => (
  <span className="inline-flex items-center gap-1.5">
    <span style={{ width: 18, height: 2, background: color, borderRadius: 1 }} />
    {label}
  </span>
);

const Edge = ({ x1, y1, x2, y2, color, dashed, label }) => {
  const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
  return (
    <g>
      <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={color} strokeWidth={1.5} strokeDasharray={dashed ? '4 3' : undefined} />
      {label && (
        <g transform={`translate(${mx - 18},${my - 10})`}>
          <rect width="46" height="14" rx="7" fill={color} fillOpacity="0.18" />
          <text x="23" y="10" textAnchor="middle" fontSize="9" fontFamily="Plus Jakarta Sans" fontWeight="700" fill={color}>{label}</text>
        </g>
      )}
    </g>
  );
};

const FlowRow = ({
  row, onPatch, onRegenerate,
  draggable, isDragging, isDragOver,
  onDragStart, onDragOver, onDragLeave, onDrop, onDragEnd,
}) => {
  const { tp, y, cond, action } = row;
  const style = CHANNEL_STYLE[tp.channel] || CHANNEL_STYLE.email;
  const ChIcon = style.Icon;

  return (
    <>
      {/* Step card (left col) */}
      <div
        className="absolute rounded-lg border shadow-sm transition-all cursor-pointer"
        style={{
          top: y, left: COL_X.step, width: COL_W.step, minHeight: ROW_H - 8,
          background: 'var(--theme-surface)',
          borderColor: isDragOver ? '#7C35DC' : 'var(--theme-border-strong)',
          borderWidth: isDragOver ? 2 : 1,
          opacity: isDragging ? 0.4 : 1,
          boxShadow: isDragOver
            ? '0 8px 24px rgba(124,53,220,0.30)'
            : isDragging
              ? '0 12px 28px rgba(0,0,0,0.20)'
              : undefined,
          transform: isDragging ? 'scale(0.98)' : undefined,
        }}
        data-testid={`flow-step-${tp.id}`}
        draggable={!!draggable}
        onDragStart={onDragStart}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onDragEnd={onDragEnd}
        onClick={() => onPatch?.(tp.id, {})}
      >
        <div className="flex items-center justify-between px-2.5 py-1.5 rounded-t-lg" style={{ background: style.dim }}>
          <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider" style={{ color: style.color, fontFamily: 'Plus Jakarta Sans' }}>
            {draggable && (
              <DotsSixVertical
                size={12}
                weight="bold"
                className="cursor-grab active:cursor-grabbing"
                style={{ color: 'var(--theme-text-muted)', marginRight: 2 }}
                data-testid={`flow-step-drag-handle-${tp.id}`}
                aria-label="Drag to reorder"
              />
            )}
            <ChIcon size={11} weight="duotone" /> Step {tp.number} · {style.label}
          </span>
          <span className="text-[10px] font-semibold" style={{ color: 'var(--theme-text-muted)' }}>
            {tp.timing || `Day ${tp.number}`}
          </span>
        </div>
        <div className="px-2.5 py-2">
          <div className="text-[11px] line-clamp-3" style={{ color: 'var(--theme-text)', fontFamily: 'Plus Jakarta Sans' }}>
            {tp.message_body || tp.goal || '(empty)'}
          </div>
          {action?.kind === 'notify' && (
            <span
              className="mt-2 inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider"
              style={{ background: '#fef3c7', color: '#92400e' }}
            >
              <Bell size={9} weight="fill" /> Alert me
            </span>
          )}
        </div>
      </div>

      {/* Condition node (middle col) */}
      {cond && (
        <div
          className="absolute rounded-lg shadow-md"
          style={{
            top: y + (ROW_H - 70) / 2, left: COL_X.cond, width: COL_W.cond, minHeight: 70,
            background: '#0F172A',
            color: '#E2E8F0',
            border: '1px solid rgba(148,163,184,0.2)',
          }}
          data-testid={`flow-cond-${tp.id}`}
        >
          <div className="px-2.5 py-1.5 flex items-center gap-1.5 border-b" style={{ borderColor: 'rgba(148,163,184,0.15)' }}>
            <Lightning size={11} weight="fill" style={{ color: '#F59E0B' }} />
            <span className="text-[11px] font-bold" style={{ fontFamily: 'Plus Jakarta Sans' }}>{cond.label}</span>
          </div>
          <div className="px-2.5 py-2 text-[10px]" style={{ color: '#94a3b8', fontFamily: 'Plus Jakarta Sans' }}>
            {cond.detail}
          </div>
        </div>
      )}

      {/* Action chip (right col) */}
      {action && (
        <div
          className="absolute rounded-lg border-2 px-3 py-2"
          style={{
            top: y + (ROW_H - 56) / 2, left: COL_X.action, width: COL_W.action, minHeight: 56,
            background: action.dim,
            borderColor: action.color,
          }}
          data-testid={`flow-action-${tp.id}`}
        >
          <div className="flex items-center gap-1.5" style={{ color: action.color, fontFamily: 'Plus Jakarta Sans' }}>
            <action.Icon size={12} weight="duotone" />
            <span className="text-[11px] font-bold">{action.label}</span>
          </div>
          {action.sub && (
            <code className="block text-[10px] mt-1" style={{ color: 'var(--theme-text-muted)', fontFamily: 'ui-monospace, monospace' }}>{action.sub}</code>
          )}
        </div>
      )}
    </>
  );
};

const MiniMap = ({ rows, canvasH, canvasW, containerRef }) => {
  const W = 140, H = 96;
  const sx = W / canvasW, sy = H / canvasH;
  const [vp, setVp] = useState({ y: 0, h: 1 });

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const onScroll = () => {
      const ratio = el.scrollTop / Math.max(1, el.scrollHeight);
      const h = el.clientHeight / Math.max(1, el.scrollHeight);
      setVp({ y: ratio, h });
    };
    onScroll();
    el.addEventListener('scroll', onScroll);
    return () => el.removeEventListener('scroll', onScroll);
  }, [containerRef, canvasH]);

  return (
    <div
      className="absolute right-3 top-3 rounded-md border shadow-md"
      style={{ width: W, height: H, background: 'var(--theme-surface)', borderColor: 'var(--theme-border-strong)' }}
      data-testid="journey-minimap"
    >
      <svg width={W} height={H}>
        {rows.map((r) => (
          <g key={r.tp.id}>
            <rect x={COL_X.step * sx} y={r.y * sy} width={COL_W.step * sx} height={ROW_H * sy * 0.85} rx="1" fill="#94a3b8" />
            {r.cond && <rect x={COL_X.cond * sx} y={r.y * sy} width={COL_W.cond * sx} height={ROW_H * sy * 0.65} rx="1" fill="#0F172A" />}
            {r.action && <rect x={COL_X.action * sx} y={r.y * sy} width={COL_W.action * sx} height={ROW_H * sy * 0.55} rx="1" fill={r.action.color} />}
          </g>
        ))}
        {/* Viewport indicator */}
        <rect
          x="2" y={vp.y * H} width={W - 4} height={Math.max(8, vp.h * H)}
          fill="none" stroke="#7C35DC" strokeWidth="1.5" rx="2"
        />
      </svg>
    </div>
  );
};

const CtrlBtn = ({ onClick, testid, children }) => (
  <button
    onClick={onClick}
    data-testid={testid}
    className="w-7 h-7 rounded-md border flex items-center justify-center"
    style={{
      background: 'var(--theme-surface)',
      borderColor: 'var(--theme-border-strong)',
      color: 'var(--theme-text-muted)',
    }}
  >
    {children}
  </button>
);


// ─── Utils ──────────────────────────────────────────────────────────────
const gradeColor = (g) => ({
  'A+': '#16A34A', A: '#16A34A',
  B: '#3B82F6',
  C: '#F59E0B',
  D: '#EF4444', F: '#991B1B',
}[g] || '#94a3b8');

const exportJSON = (rows) => {
  try {
    const blob = new Blob([JSON.stringify(rows.map((r) => r.tp), null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'journey.json'; a.click();
    URL.revokeObjectURL(url);
  } catch { /* ignore */ }
};


export default JourneyFlowchart;
