/**
 * 32-Touchpoint Journey Builder — replaces the old 64-line grid.
 *
 * Four views on the same data:
 *   • Flowchart  — channel-coloured nodes with conditional-logic edges
 *   • Timeline   — vertical day-axis with chips per touchpoint
 *   • Pipeline   — kanban-style columns per channel
 *   • Conditional — list of conditional_logic rules per touchpoint
 *
 * Top toolbar:
 *   ✦ Generate Journey with AI (claude-sonnet-4-5)
 *   + Add Touchpoint
 *   ↕ Reorder mode (drag-and-drop)
 *   View tabs: Flowchart | Timeline | Pipeline | Conditional
 *
 * Each touchpoint card:
 *   • Inline-editable number, channel, timing, goal, conditional_logic, body
 *   • ✦ Regenerate (single-touchpoint Claude refresh)
 *   • 🗑 Delete
 *
 * Backend: /api/journey/* (see routes/journey.py)
 */
import { useEffect, useMemo, useState } from 'react';
import {
  Sparkle, Plus, Trash, ArrowsClockwise, FlowArrow, Clock, Kanban,
  GitBranch, FloppyDisk, CircleNotch, Robot, EnvelopeSimple, WhatsappLogo,
  LinkedinLogo, ChatCircleText, PhoneCall, CaretUp, CaretDown, PencilSimple,
  CheckCircle, X as XIcon,
} from '@phosphor-icons/react';
import { toast } from 'sonner';
import api from '../../config/api';

const CHANNELS = ['whatsapp', 'email', 'linkedin', 'sms', 'call'];

const CHANNEL_STYLE = {
  whatsapp: { color: '#25D366', Icon: WhatsappLogo,    label: 'WhatsApp' },
  email:    { color: '#7C35DC', Icon: EnvelopeSimple,  label: 'Email'    },
  linkedin: { color: '#0A66C2', Icon: LinkedinLogo,    label: 'LinkedIn' },
  sms:      { color: '#f59e0b', Icon: ChatCircleText,  label: 'SMS'      },
  call:     { color: '#ef4444', Icon: PhoneCall,       label: 'Call'     },
};

const VIEWS = [
  { id: 'flowchart',    label: 'Flowchart',   Icon: FlowArrow },
  { id: 'timeline',     label: 'Timeline',    Icon: Clock     },
  { id: 'pipeline',     label: 'Pipeline',    Icon: Kanban    },
  { id: 'conditional',  label: 'Conditional', Icon: GitBranch },
];


const TouchpointMap = () => {
  const [tps, setTps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState('flowchart');
  const [generating, setGenerating] = useState(false);
  const [genCount, setGenCount] = useState(32);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/api/journey/touchpoints');
      setTps((data.touchpoints || []).sort((a, b) => a.number - b.number));
    } catch (e) {
      toast.error('Could not load journey');
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);
  useEffect(() => {
    const onTenant = () => load();
    window.addEventListener('aria:tenant-changed', onTenant);
    return () => window.removeEventListener('aria:tenant-changed', onTenant);
  }, []);

  const generateAll = async () => {
    if (tps.length > 0 && !window.confirm(`Generate a fresh ${genCount}-touchpoint journey? This will REPLACE the current ${tps.length} touchpoints.`)) return;
    setGenerating(true);
    try {
      const { data } = await api.post('/api/journey/generate', { count: genCount, replace: true });
      setTps((data.touchpoints || []).sort((a, b) => a.number - b.number));
      toast.success(`Generated ${data.count} touchpoints with Claude`);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Generation failed');
    } finally { setGenerating(false); }
  };

  const addBlank = async () => {
    const number = (tps[tps.length - 1]?.number || 0) + 1;
    try {
      const { data } = await api.post('/api/journey/touchpoints', {
        number, channel: 'email', timing: `Day ${number}`, message_body: '', goal: '', conditional_logic: '',
      });
      setTps((arr) => [...arr, data].sort((a, b) => a.number - b.number));
    } catch (e) {
      toast.error('Add failed');
    }
  };

  const patchTouchpoint = async (id, patch) => {
    // Optimistic update
    setTps((arr) => arr.map((t) => (t.id === id ? { ...t, ...patch } : t)));
    try {
      const { data } = await api.patch(`/api/journey/touchpoints/${id}`, patch);
      setTps((arr) => arr.map((t) => (t.id === id ? data : t)).sort((a, b) => a.number - b.number));
    } catch (e) {
      toast.error('Save failed — reloading');
      load();
    }
  };

  const remove = async (id) => {
    if (!window.confirm('Delete this touchpoint?')) return;
    try {
      await api.delete(`/api/journey/touchpoints/${id}`);
      setTps((arr) => arr.filter((t) => t.id !== id));
      toast.success('Deleted');
    } catch (e) {
      toast.error('Delete failed');
    }
  };

  const regenerate = async (id) => {
    try {
      const { data } = await api.post(`/api/journey/touchpoints/${id}/regenerate`);
      setTps((arr) => arr.map((t) => (t.id === id ? data : t)).sort((a, b) => a.number - b.number));
      toast.success('Touchpoint regenerated');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Regenerate failed');
    }
  };

  const move = async (id, direction) => {
    const idx = tps.findIndex((t) => t.id === id);
    const swapIdx = direction === 'up' ? idx - 1 : idx + 1;
    if (idx < 0 || swapIdx < 0 || swapIdx >= tps.length) return;
    const next = [...tps];
    const a = next[idx], b = next[swapIdx];
    next[idx] = { ...b, number: a.number };
    next[swapIdx] = { ...a, number: b.number };
    setTps(next.sort((a, b) => a.number - b.number));
    try {
      await api.post('/api/journey/touchpoints/reorder', {
        order: next.map((t) => ({ id: t.id, number: t.number })),
      });
    } catch { toast.error('Reorder failed'); load(); }
  };

  return (
    <div className="space-y-4" data-testid="touchpoint-journey-page" style={{ color: 'var(--theme-text)' }}>
      {/* Header */}
      <div className="flex flex-wrap items-end justify-between gap-3 mb-2">
        <div>
          <h1 className="text-2xl font-extrabold" style={{ fontFamily: 'Space Grotesk, Inter', letterSpacing: '-0.02em' }}>
            32-Touchpoint Journey
          </h1>
          <p className="text-sm" style={{ color: 'var(--theme-text-muted)' }}>
            ARIA's outreach sequence. Edit any step, drag to reorder, or regenerate with Claude.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="number" min={1} max={64} value={genCount}
            onChange={(e) => setGenCount(Math.max(1, Math.min(64, parseInt(e.target.value || '32'))))}
            data-testid="journey-gen-count"
            className="w-14 px-2 py-1.5 rounded-md text-sm border outline-none text-center"
            style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text)' }}
          />
          <button
            onClick={generateAll}
            disabled={generating}
            data-testid="journey-generate-with-ai"
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-md text-xs font-bold text-white disabled:opacity-50"
            style={{ background: 'linear-gradient(135deg, #5b21b6 0%, #7c3aed 60%)' }}
          >
            {generating ? <CircleNotch size={13} className="animate-spin" /> : <Sparkle size={13} weight="fill" />}
            {generating ? 'Generating…' : 'Generate Journey with AI'}
          </button>
          <button
            onClick={addBlank}
            data-testid="journey-add-blank"
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-xs font-bold border"
            style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text)' }}
          >
            <Plus size={12} weight="bold" /> Add
          </button>
        </div>
      </div>

      {/* View tabs */}
      <div className="flex flex-wrap gap-1.5" data-testid="journey-view-tabs">
        {VIEWS.map((v) => {
          const Icon = v.Icon;
          const active = view === v.id;
          return (
            <button
              key={v.id}
              onClick={() => setView(v.id)}
              data-testid={`journey-view-${v.id}`}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold border transition-colors"
              style={{
                background: active ? 'var(--theme-purple-dim)' : 'var(--theme-surface)',
                borderColor: active ? 'var(--theme-purple)' : 'var(--theme-border-strong)',
                color: active ? 'var(--theme-purple-light)' : 'var(--theme-text-muted)',
              }}
            >
              <Icon size={12} weight="duotone" /> {v.label}
            </button>
          );
        })}
      </div>

      {/* Empty state */}
      {!loading && tps.length === 0 && (
        <div
          className="rounded-xl border p-10 text-center"
          style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }}
          data-testid="journey-empty"
        >
          <Robot size={36} weight="duotone" className="mx-auto mb-3" style={{ color: 'var(--theme-purple-light)' }} />
          <div className="text-lg font-bold mb-1" style={{ color: 'var(--theme-text)' }}>No journey yet.</div>
          <div className="text-sm mb-4" style={{ color: 'var(--theme-text-muted)' }}>
            Let Claude draft a {genCount}-touchpoint sequence in your workspace's brand voice.
          </div>
          <button
            onClick={generateAll}
            disabled={generating}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-bold text-white disabled:opacity-50"
            style={{ background: 'linear-gradient(135deg, #5b21b6 0%, #7c3aed 60%)' }}
            data-testid="journey-empty-generate"
          >
            {generating ? <CircleNotch size={14} className="animate-spin" /> : <Sparkle size={14} weight="fill" />}
            {generating ? 'Generating…' : 'Generate with AI'}
          </button>
        </div>
      )}

      {loading && (
        <div className="text-sm" style={{ color: 'var(--theme-text-muted)' }} data-testid="journey-loading">
          Loading journey…
        </div>
      )}

      {/* Views */}
      {!loading && tps.length > 0 && view === 'flowchart' && (
        <FlowchartView tps={tps} onPatch={patchTouchpoint} onRemove={remove} onRegenerate={regenerate} onMove={move} />
      )}
      {!loading && tps.length > 0 && view === 'timeline' && (
        <TimelineView tps={tps} onPatch={patchTouchpoint} onRemove={remove} onRegenerate={regenerate} />
      )}
      {!loading && tps.length > 0 && view === 'pipeline' && (
        <PipelineView tps={tps} onPatch={patchTouchpoint} onRemove={remove} onRegenerate={regenerate} />
      )}
      {!loading && tps.length > 0 && view === 'conditional' && (
        <ConditionalView tps={tps} onPatch={patchTouchpoint} />
      )}
    </div>
  );
};


// ── FlowchartView ───────────────────────────────────────────────────────
// Stacked nodes connected by vertical edges. Each node shows channel
// colour, number, goal, and (if present) its outgoing branch label.
const FlowchartView = ({ tps, onPatch, onRemove, onRegenerate, onMove }) => (
  <div className="space-y-3" data-testid="journey-flowchart">
    {tps.map((tp, i) => (
      <div key={tp.id}>
        <TouchpointNode tp={tp} onPatch={onPatch} onRemove={onRemove} onRegenerate={onRegenerate} onMove={onMove} index={i} total={tps.length} />
        {i < tps.length - 1 && (
          <div className="flex justify-center my-1">
            <div
              className="rounded-md px-3 py-1 text-[11px] font-semibold border"
              style={{
                background: 'var(--theme-surface2)',
                borderColor: 'var(--theme-border-strong)',
                color: 'var(--theme-text-muted)',
              }}
              data-testid={`journey-edge-${tp.id}`}
            >
              ↓ {tp.conditional_logic ? `if · ${shorten(tp.conditional_logic)}` : 'continue'}
            </div>
          </div>
        )}
      </div>
    ))}
  </div>
);


// ── TimelineView ────────────────────────────────────────────────────────
// Vertical day-axis where each touchpoint sits at its `timing` row.
const TimelineView = ({ tps, onPatch, onRemove, onRegenerate }) => (
  <div
    className="rounded-xl border p-4 space-y-2"
    style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }}
    data-testid="journey-timeline"
  >
    {tps.map((tp) => {
      const style = CHANNEL_STYLE[tp.channel] || CHANNEL_STYLE.email;
      const Icon = style.Icon;
      return (
        <div key={tp.id} className="flex items-start gap-3 pb-2 border-b last:border-b-0" style={{ borderColor: 'var(--theme-border)' }} data-testid={`timeline-row-${tp.id}`}>
          <div
            className="shrink-0 w-24 text-[11px] font-bold uppercase tracking-[0.14em] pt-1.5"
            style={{ color: 'var(--theme-text-muted)' }}
          >
            {tp.timing || `Day ${tp.number}`}
          </div>
          <div
            className="shrink-0 w-8 h-8 rounded-md flex items-center justify-center"
            style={{ background: style.color + '20', color: style.color }}
          >
            <Icon size={14} weight="duotone" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              <span className="text-[10px] font-bold uppercase tracking-[0.14em]" style={{ color: 'var(--theme-text-muted)' }}>
                #{String(tp.number).padStart(2, '0')}
              </span>
              <span className="text-sm font-bold truncate" style={{ color: 'var(--theme-text)' }}>{tp.goal || '(no goal)'}</span>
            </div>
            <div className="text-xs line-clamp-2" style={{ color: 'var(--theme-text-muted)' }}>{tp.message_body || '(empty)'}</div>
          </div>
          <button
            onClick={() => onRegenerate(tp.id)}
            data-testid={`timeline-regen-${tp.id}`}
            className="text-[10px] font-bold px-2 py-1 rounded border"
            style={{ borderColor: 'var(--theme-border-strong)', color: 'var(--theme-purple-light, #7C35DC)' }}
          >
            <Sparkle size={9} weight="fill" className="inline mr-0.5" /> Regen
          </button>
        </div>
      );
    })}
  </div>
);


// ── PipelineView (kanban per channel) ───────────────────────────────────
const PipelineView = ({ tps, onPatch, onRemove, onRegenerate }) => {
  const cols = useMemo(() => {
    const grouped = CHANNELS.map((ch) => ({
      channel: ch,
      items: tps.filter((t) => t.channel === ch).sort((a, b) => a.number - b.number),
    }));
    return grouped;
  }, [tps]);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3" data-testid="journey-pipeline">
      {cols.map(({ channel, items }) => {
        const style = CHANNEL_STYLE[channel];
        const Icon = style.Icon;
        return (
          <div
            key={channel}
            className="rounded-xl border p-3 min-h-[200px]"
            style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }}
            data-testid={`pipeline-col-${channel}`}
          >
            <div className="flex items-center gap-2 mb-3 pb-2 border-b" style={{ borderColor: 'var(--theme-border)' }}>
              <div className="w-7 h-7 rounded-md flex items-center justify-center" style={{ background: style.color + '20', color: style.color }}>
                <Icon size={13} weight="duotone" />
              </div>
              <span className="text-xs font-bold" style={{ color: 'var(--theme-text)' }}>{style.label}</span>
              <span className="ml-auto text-[10px] font-bold px-1.5 py-0.5 rounded" style={{ background: 'var(--theme-surface2)', color: 'var(--theme-text-muted)' }}>
                {items.length}
              </span>
            </div>
            <div className="space-y-2">
              {items.length === 0 && (
                <div className="text-[11px] italic" style={{ color: 'var(--theme-text-muted)' }}>No steps in this channel.</div>
              )}
              {items.map((tp) => (
                <div
                  key={tp.id}
                  className="rounded-md p-2 border"
                  style={{ background: 'var(--theme-surface2)', borderColor: 'var(--theme-border)' }}
                  data-testid={`pipeline-card-${tp.id}`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--theme-text-muted)' }}>
                      #{tp.number} · {tp.timing || `Day ${tp.number}`}
                    </span>
                    <button
                      onClick={() => onRegenerate(tp.id)}
                      data-testid={`pipeline-regen-${tp.id}`}
                      className="text-[10px] font-bold opacity-70 hover:opacity-100"
                      style={{ color: 'var(--theme-purple-light, #7C35DC)' }}
                      title="Regenerate this touchpoint"
                    >
                      <Sparkle size={10} weight="fill" />
                    </button>
                  </div>
                  <div className="text-xs font-semibold mb-0.5 line-clamp-1" style={{ color: 'var(--theme-text)' }}>{tp.goal || '(no goal)'}</div>
                  <div className="text-[11px] line-clamp-2" style={{ color: 'var(--theme-text-muted)' }}>{tp.message_body || '(empty)'}</div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
};


// ── ConditionalView ─────────────────────────────────────────────────────
const ConditionalView = ({ tps, onPatch }) => {
  const branched = tps.filter((t) => (t.conditional_logic || '').trim());
  return (
    <div
      className="rounded-xl border p-4 space-y-3"
      style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }}
      data-testid="journey-conditional"
    >
      <div className="text-[11px] uppercase tracking-[0.2em] font-bold" style={{ color: 'var(--theme-text-muted)' }}>
        Branching rules — {branched.length} of {tps.length} touchpoints
      </div>
      {branched.length === 0 && (
        <div className="text-sm" style={{ color: 'var(--theme-text-muted)' }}>
          No conditional rules yet. Add a "conditional_logic" string on any touchpoint to branch the flow.
        </div>
      )}
      {branched.map((tp) => {
        const style = CHANNEL_STYLE[tp.channel] || CHANNEL_STYLE.email;
        return (
          <div
            key={tp.id}
            className="rounded-md p-3 border"
            style={{ background: 'var(--theme-surface2)', borderColor: 'var(--theme-border)' }}
            data-testid={`conditional-row-${tp.id}`}
          >
            <div className="flex items-center gap-2 mb-2">
              <span className="text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded" style={{ background: style.color + '20', color: style.color }}>
                #{tp.number} · {style.label}
              </span>
              <span className="text-xs" style={{ color: 'var(--theme-text-muted)' }}>{tp.timing}</span>
            </div>
            <textarea
              value={tp.conditional_logic || ''}
              onChange={(e) => onPatch(tp.id, { conditional_logic: e.target.value })}
              data-testid={`conditional-input-${tp.id}`}
              rows={2}
              className="w-full px-2 py-1.5 rounded text-xs border outline-none"
              style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text)' }}
              placeholder="e.g. If replied positively → skip to touchpoint 15. If unsubscribed → end."
            />
          </div>
        );
      })}
    </div>
  );
};


// ── TouchpointNode — the editable card used in Flowchart view ───────────
const TouchpointNode = ({ tp, onPatch, onRemove, onRegenerate, onMove, index, total }) => {
  const style = CHANNEL_STYLE[tp.channel] || CHANNEL_STYLE.email;
  const Icon = style.Icon;
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState({ ...tp });
  useEffect(() => { setDraft({ ...tp }); }, [tp]);
  const dirty = JSON.stringify({
    channel: draft.channel, timing: draft.timing, goal: draft.goal,
    message_body: draft.message_body, conditional_logic: draft.conditional_logic,
  }) !== JSON.stringify({
    channel: tp.channel, timing: tp.timing, goal: tp.goal,
    message_body: tp.message_body, conditional_logic: tp.conditional_logic,
  });

  const save = () => {
    onPatch(tp.id, {
      channel: draft.channel, timing: draft.timing, goal: draft.goal,
      message_body: draft.message_body, conditional_logic: draft.conditional_logic,
    });
    setOpen(false);
  };

  return (
    <div
      className="rounded-xl border p-4"
      style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }}
      data-testid={`touchpoint-card-${tp.id}`}
    >
      <div className="flex items-start gap-3">
        <div
          className="shrink-0 w-12 h-12 rounded-lg flex flex-col items-center justify-center"
          style={{ background: style.color + '20', color: style.color }}
        >
          <Icon size={16} weight="duotone" />
          <span className="text-[9px] font-extrabold mt-0.5">#{tp.number}</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <select
              value={draft.channel}
              onChange={(e) => setDraft((d) => ({ ...d, channel: e.target.value }))}
              data-testid={`tp-channel-${tp.id}`}
              className="text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded border outline-none"
              style={{ background: 'var(--theme-surface2)', borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text)' }}
            >
              {CHANNELS.map((c) => <option key={c} value={c}>{CHANNEL_STYLE[c].label}</option>)}
            </select>
            <input
              value={draft.timing || ''}
              onChange={(e) => setDraft((d) => ({ ...d, timing: e.target.value }))}
              data-testid={`tp-timing-${tp.id}`}
              placeholder="Day 1"
              className="text-xs px-2 py-0.5 rounded border outline-none"
              style={{ background: 'var(--theme-surface2)', borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text)', minWidth: 120 }}
            />
            <input
              value={draft.goal || ''}
              onChange={(e) => setDraft((d) => ({ ...d, goal: e.target.value }))}
              data-testid={`tp-goal-${tp.id}`}
              placeholder="Goal"
              className="flex-1 min-w-[140px] text-xs px-2 py-0.5 rounded border outline-none"
              style={{ background: 'var(--theme-surface2)', borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text)' }}
            />
          </div>
          {open ? (
            <>
              <textarea
                value={draft.message_body || ''}
                onChange={(e) => setDraft((d) => ({ ...d, message_body: e.target.value }))}
                data-testid={`tp-body-${tp.id}`}
                rows={4}
                placeholder="Message body — under 150 words, in your brand voice."
                className="w-full mt-1 px-2 py-1.5 rounded text-xs border outline-none"
                style={{ background: 'var(--theme-surface2)', borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text)' }}
              />
              <textarea
                value={draft.conditional_logic || ''}
                onChange={(e) => setDraft((d) => ({ ...d, conditional_logic: e.target.value }))}
                data-testid={`tp-cond-${tp.id}`}
                rows={2}
                placeholder="Conditional logic — e.g. If unsubscribed → end."
                className="w-full mt-2 px-2 py-1.5 rounded text-xs border outline-none"
                style={{ background: 'var(--theme-surface2)', borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text)' }}
              />
            </>
          ) : (
            <p className="text-xs mt-1 line-clamp-2" style={{ color: 'var(--theme-text-muted)' }}>
              {tp.message_body || '(empty — click Edit to write the message)'}
            </p>
          )}
        </div>
        <div className="flex flex-col gap-1 shrink-0">
          <button
            onClick={() => onMove(tp.id, 'up')}
            disabled={index === 0}
            data-testid={`tp-up-${tp.id}`}
            className="p-1 rounded border disabled:opacity-30"
            style={{ borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text-muted)' }}
            title="Move up"
          ><CaretUp size={10} /></button>
          <button
            onClick={() => onMove(tp.id, 'down')}
            disabled={index === total - 1}
            data-testid={`tp-down-${tp.id}`}
            className="p-1 rounded border disabled:opacity-30"
            style={{ borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text-muted)' }}
            title="Move down"
          ><CaretDown size={10} /></button>
        </div>
      </div>

      <div className="mt-3 flex items-center justify-end gap-1.5">
        {open && dirty && (
          <button
            onClick={save}
            data-testid={`tp-save-${tp.id}`}
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-bold text-white"
            style={{ background: 'var(--theme-purple, #7C35DC)' }}
          >
            <FloppyDisk size={10} weight="fill" /> Save
          </button>
        )}
        <button
          onClick={() => setOpen((v) => !v)}
          data-testid={`tp-edit-${tp.id}`}
          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-semibold border"
          style={{ borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text-muted)' }}
        >
          {open ? <XIcon size={10} /> : <PencilSimple size={10} />} {open ? 'Close' : 'Edit'}
        </button>
        <button
          onClick={() => onRegenerate(tp.id)}
          data-testid={`tp-regen-${tp.id}`}
          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-bold border"
          style={{ borderColor: 'var(--theme-purple, #7C35DC)', color: 'var(--theme-purple-light, #7C35DC)' }}
          title="Regenerate this touchpoint with Claude"
        >
          <Sparkle size={10} weight="fill" /> Regenerate
        </button>
        <button
          onClick={() => onRemove(tp.id)}
          data-testid={`tp-delete-${tp.id}`}
          className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-semibold border"
          style={{ borderColor: 'var(--theme-border-strong)', color: '#ef4444' }}
          title="Delete"
        >
          <Trash size={10} />
        </button>
      </div>
    </div>
  );
};


const shorten = (s, n = 60) => {
  const str = String(s || '');
  return str.length > n ? str.slice(0, n - 1) + '…' : str;
};


export default TouchpointMap;
