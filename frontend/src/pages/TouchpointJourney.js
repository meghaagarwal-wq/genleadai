/**
 * TouchpointJourney — the most important workspace in Aria.
 *
 * Vertical timeline + right-side detail/edit drawer + drag-to-reorder + 3-tab scoring:
 *   1. Performance — live metrics from lead_touchpoint_log (sent, replies, skips, effectiveness grade)
 *   2. Lead-fit — hot/warm/cold distribution per touchpoint
 *   3. AI Quality — Claude scoring (clarity, personalisation, CTA, tone-fit)
 *
 * Plus: document upload, template library, version history, 32-touchpoint cap.
 */
import React, { useEffect, useMemo, useState } from 'react';
import api from '../config/api';
import { toast } from 'sonner';
import { DragDropContext, Droppable, Draggable } from 'react-beautiful-dnd';
import JourneyStagesHero from '../components/JourneyStagesHero';
import AriaSpotlight from '../components/AriaSpotlight';
import {
  ChatCircle, EnvelopeSimple, Phone, LinkedinLogo, Sparkle, CheckCircle,
  PencilSimple, Trash, Plus, ArrowsClockwise, Copy,
  ClockCounterClockwise, BookOpen, UploadSimple, X, FileText, Warning,
  FileArrowUp, ArrowLeft, DotsSixVertical, ChartLineUp, Target, Brain,
  Fire, Snowflake, ThumbsUp, ThumbsDown, ArrowsCounterClockwise, Lightning,
} from '@phosphor-icons/react';
import ConditionsInspector from '../components/ConditionsInspector';
import JourneyFlowchart from '../components/JourneyFlowchart';

const MAX_TOUCHPOINTS = 32;

const CHANNEL_META = {
  whatsapp: { label: 'WhatsApp', color: '#25D366', bg: '#DCFCE7', icon: ChatCircle },
  email: { label: 'Email', color: '#0055FF', bg: '#DCEEFE', icon: EnvelopeSimple },
  call_reminder: { label: 'Call', color: '#F97316', bg: '#FEF3C7', icon: Phone },
  linkedin_nudge: { label: 'LinkedIn', color: '#7C35DC', bg: '#F4F0FF', icon: LinkedinLogo },
};
const TYPE_LABELS = {
  intro: 'Intro', qualifier: 'Qualifier', value_drop: 'Value Drop', value_add: 'Value Add',
  follow_up: 'Follow-up', social_proof: 'Social Proof', soft_cta: 'Soft CTA',
  budget_probe: 'Budget Probe', meeting_cta: 'Meeting CTA',
  human_escalation: 'Human Escalation', re_engagement: 'Re-engagement',
  urgency: 'Urgency', closure: 'Closure',
};
const CONDITIONS = [
  { value: '', label: 'Always send' },
  { value: 'if_no_reply', label: 'If lead has not replied' },
  { value: 'if_qualified', label: 'If lead score ≥ 70 (qualified)' },
  { value: 'if_stage_negotiation', label: 'If lead stage = Negotiation' },
  { value: 'if_sentiment_negative', label: 'If sentiment is negative' },
  { value: 'if_prev_sent', label: 'If previous touchpoint sent OK' },
];

const TOKENS = ['{{first_name}}', '{{company}}', '{{product}}', '{{last_message}}', '{{score}}', '{{assigned_rep}}'];

const GRADE_COLOR = {
  A: { color: '#16A34A', bg: '#DCFCE7', border: '#16A34A' },
  B: { color: '#0055FF', bg: '#DCEEFE', border: '#0055FF' },
  C: { color: '#D97706', bg: '#FEF3C7', border: '#D97706' },
  D: { color: '#DC2626', bg: '#FEE2E2', border: '#DC2626' },
  '—': { color: '#9B8AB0', bg: '#F1F5F9', border: '#CBD5E1' },
};

const fmt = (iso) => { try { return new Date(iso).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }); } catch { return '—'; } };

// ──────────────────────────────────────────────────────────────────────────
// Journey Score Header — big number + grade + key counters
// ──────────────────────────────────────────────────────────────────────────
const JourneyScoreBanner = ({ journey, onScoreAI, aiBusy }) => {
  if (!journey) return null;
  const grade = journey.grade || '—';
  const g = GRADE_COLOR[grade] || GRADE_COLOR['—'];
  return (
    <div className="rounded-2xl p-5 border" style={{ background: 'linear-gradient(135deg, #FAF7FF 0%, #FFFFFF 50%, #F0FDF4 100%)', borderColor: '#E8E0F5', boxShadow: 'var(--shadow-card)' }} data-testid="journey-score-banner">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-5">
          <div className="relative flex-shrink-0">
            <svg width="84" height="84" viewBox="0 0 84 84">
              <circle cx="42" cy="42" r="36" fill="none" stroke="#F0ECF9" strokeWidth="8" />
              <circle
                cx="42" cy="42" r="36" fill="none" stroke={g.color} strokeWidth="8"
                strokeLinecap="round"
                strokeDasharray={`${(journey.score / 100) * 2 * Math.PI * 36} ${2 * Math.PI * 36}`}
                transform="rotate(-90 42 42)" style={{ transition: 'stroke-dasharray 0.6s' }}
              />
              <text x="42" y="40" textAnchor="middle" fontSize="22" fontWeight="800" fill="#1A0A2E" style={{ fontFamily: 'Plus Jakarta Sans' }}>{journey.score || 0}</text>
              <text x="42" y="56" textAnchor="middle" fontSize="9" fill="#9B8AB0" fontWeight="700" letterSpacing="1">/ 100</text>
            </svg>
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h2 className="text-lg font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Journey strength</h2>
              <span className="px-2 py-0.5 rounded-md text-xs font-extrabold border" style={{ background: g.bg, borderColor: g.border + '55', color: g.color }} data-testid="journey-grade">Grade {grade}</span>
            </div>
            <p className="text-xs text-[#5A4A7A] max-w-md">
              Live score combining delivery, reply rate and skip rate across all leads who passed through your journey.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {[
            { label: 'Touchpoints', value: journey.touchpoint_count, color: '#7C35DC' },
            { label: 'Sent', value: journey.total_sent, color: '#0055FF' },
            { label: 'Replies', value: journey.total_replies, color: '#16A34A' },
            { label: 'Reply rate', value: `${journey.reply_rate || 0}%`, color: '#C044E0' },
          ].map((s) => (
            <div key={s.label} className="px-3 py-2 bg-white rounded-lg border border-[#E8E0F5]">
              <div className="text-[9px] font-bold uppercase tracking-[0.18em] text-[#9B8AB0]">{s.label}</div>
              <div className="text-base font-extrabold mt-0.5" style={{ color: s.color, fontFamily: 'Plus Jakarta Sans' }}>{s.value ?? 0}</div>
            </div>
          ))}
          <button onClick={onScoreAI} disabled={aiBusy} data-testid="ai-score-btn"
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-bold text-white disabled:opacity-50"
            style={{ background: 'var(--gradient-brand)', fontFamily: 'Plus Jakarta Sans' }}>
            <Brain size={12} weight="fill" /> {aiBusy ? 'Aria is scoring…' : 'Score with AI'}
          </button>
        </div>
      </div>
    </div>
  );
};

// ──────────────────────────────────────────────────────────────────────────
// Vertical timeline card (compact row in the left column)
// ──────────────────────────────────────────────────────────────────────────
const TimelineRow = ({ tp, scoring, ai, selected, onSelect, dragHandleProps }) => {
  const meta = CHANNEL_META[tp.channel] || CHANNEL_META.whatsapp;
  const Icon = meta.icon;
  const isHuman = tp.aria_role === 'alert_human';
  const perf = scoring?.performance;
  const grade = perf?.grade || '—';
  const g = GRADE_COLOR[grade] || GRADE_COLOR['—'];
  const aiAvg = ai?.average;

  return (
    <button
      onClick={() => onSelect(tp.index)}
      data-testid={`vtl-card-${tp.index}`}
      className={`w-full text-left rounded-xl border transition-all p-4 group ${selected ? 'border-[#7C35DC] ring-2 ring-[#7C35DC]/20 bg-[#FAF7FF]' : 'bg-white border-[#E8E0F5] hover:border-[#7C35DC]/40'}`}
      style={{ boxShadow: selected ? '0 8px 24px rgba(124,53,220,0.15)' : 'var(--shadow-card)' }}
    >
      <div className="flex items-start gap-3">
        {/* Drag handle */}
        <span {...dragHandleProps} onClick={(e) => e.stopPropagation()} data-testid={`drag-${tp.index}`} className="flex-shrink-0 cursor-grab active:cursor-grabbing text-[#9B8AB0] hover:text-[#7C35DC] pt-1">
          <DotsSixVertical size={16} weight="bold" />
        </span>

        {/* Day/Hour pill */}
        <div className="flex-shrink-0 flex flex-col items-center min-w-[58px] py-1">
          <span className="text-[9px] font-bold uppercase tracking-[0.18em] text-[#9B8AB0] font-mono">TP-{String(tp.index + 1).padStart(2, '0')}</span>
          <div className="mt-1 px-2 py-1 rounded-md text-center" style={{ background: 'var(--gradient-brand)' }}>
            <div className="text-[10px] font-bold uppercase tracking-wider text-white/80 leading-none">Day</div>
            <div className="text-lg font-extrabold text-white leading-tight" style={{ fontFamily: 'Plus Jakarta Sans' }}>{tp.day}</div>
          </div>
          <span className="text-[9px] font-mono text-[#9B8AB0] mt-0.5">{String(tp.hour).padStart(2, '0')}:00</span>
        </div>

        {/* Main body */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
            <div className="w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0" style={{ background: meta.bg }}>
              <Icon size={12} weight="fill" style={{ color: meta.color }} />
            </div>
            <span className="text-xs font-bold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{TYPE_LABELS[tp.message_type] || tp.message_type}</span>
            <span className={`px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider rounded ${isHuman ? 'bg-[#FEF3C7] text-[#D97706] border border-[#D97706]/30' : 'bg-[#DCEEFE] text-[#0055FF] border border-[#0055FF]/30'}`}>
              {isHuman ? 'Alert me' : 'Aria'}
            </span>
            {tp.trigger && (
              <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-[#F4F0FF] text-[#7C35DC] border border-[#7C35DC]/20">
                {(CONDITIONS.find((c) => c.value === tp.trigger)?.label || tp.trigger).replace('If ', '')}
              </span>
            )}
          </div>
          <p className="text-xs text-[#5A4A7A] line-clamp-2 leading-relaxed">{tp.message_template || <span className="italic text-[#9B8AB0]">No message yet</span>}</p>
        </div>

        {/* Scoring chips */}
        <div className="flex-shrink-0 flex flex-col items-end gap-1.5">
          <span className="px-2 py-1 rounded-md text-[10px] font-extrabold border" style={{ background: g.bg, borderColor: g.border + '55', color: g.color }} data-testid={`grade-${tp.index}`}>
            {grade}
          </span>
          {perf && (
            <span className="text-[10px] text-[#5A4A7A] font-mono">
              {perf.sent || 0}↑ · {perf.replies || 0}↩
            </span>
          )}
          {aiAvg !== undefined && (
            <span className="inline-flex items-center gap-0.5 text-[10px] text-[#7C35DC] font-bold">
              <Brain size={9} weight="fill" /> {aiAvg}/10
            </span>
          )}
        </div>
      </div>
    </button>
  );
};

// ──────────────────────────────────────────────────────────────────────────
// Side drawer — full details + 3 tabs + inline edit
// ──────────────────────────────────────────────────────────────────────────
const ScoreBar = ({ label, value, max = 10, color = '#7C35DC' }) => (
  <div className="space-y-1" data-testid={`scorebar-${label.toLowerCase().replace(/[^a-z]/g, '-')}`}>
    <div className="flex items-center justify-between text-xs">
      <span className="text-[#5A4A7A] font-medium">{label}</span>
      <span className="font-mono font-bold text-[#1A0A2E]">{value}/{max}</span>
    </div>
    <div className="h-1.5 bg-[#F0ECF9] rounded-full overflow-hidden">
      <div className="h-full rounded-full transition-all" style={{ width: `${(value / max) * 100}%`, background: color }}></div>
    </div>
  </div>
);

const DetailDrawer = ({ tp, scoring, ai, onChange, onDelete, onDuplicate, onClose, isFirst, isLast, onMove, total }) => {
  const [tab, setTab] = useState('details');
  if (!tp) return null;
  const meta = CHANNEL_META[tp.channel] || CHANNEL_META.whatsapp;
  const Icon = meta.icon;
  const perf = scoring?.performance;
  const fit = scoring?.lead_fit;
  const grade = perf?.grade || '—';
  const g = GRADE_COLOR[grade] || GRADE_COLOR['—'];

  return (
    <div className="bg-white border border-[#E8E0F5] rounded-2xl flex flex-col sticky top-4" style={{ maxHeight: 'calc(100vh - 100px)', boxShadow: 'var(--shadow-card)' }} data-testid="detail-drawer">
      {/* Header */}
      <div className="p-5 border-b border-[#E8E0F5] flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: meta.bg }}>
            <Icon size={20} weight="fill" style={{ color: meta.color }} />
          </div>
          <div className="min-w-0">
            <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#9B8AB0] font-mono">TP-{String(tp.index + 1).padStart(2, '0')} of {total}</div>
            <h3 className="text-base font-extrabold text-[#1A0A2E] truncate" style={{ fontFamily: 'Plus Jakarta Sans' }}>
              {TYPE_LABELS[tp.message_type] || tp.message_type} · Day {tp.day}
            </h3>
          </div>
        </div>
        <button onClick={onClose} data-testid="drawer-close" className="text-[#9B8AB0] hover:text-[#1A0A2E] p-1"><X size={18} /></button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-[#E8E0F5] px-3 gap-1 flex-shrink-0">
        {[
          { id: 'details', label: 'Details', icon: PencilSimple },
          { id: 'performance', label: 'Performance', icon: ChartLineUp },
          { id: 'fit', label: 'Lead-fit', icon: Target },
          { id: 'ai', label: 'AI Quality', icon: Brain },
        ].map((t) => {
          const active = tab === t.id;
          return (
            <button key={t.id} onClick={() => setTab(t.id)} data-testid={`tab-${t.id}`}
              className={`flex items-center gap-1.5 px-3 py-2.5 text-xs font-bold border-b-2 transition-all ${active ? 'border-[#7C35DC] text-[#7C35DC]' : 'border-transparent text-[#9B8AB0] hover:text-[#5A4A7A]'}`}
              style={{ fontFamily: 'Plus Jakarta Sans' }}>
              <t.icon size={12} weight={active ? 'fill' : 'regular'} />
              {t.label}
            </button>
          );
        })}
      </div>

      {/* Body — scroll area */}
      <div className="flex-1 overflow-y-auto p-5 space-y-4">
        {tab === 'details' && (
          <>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[9px] font-bold uppercase tracking-wider text-[#9B8AB0]">Day</label>
                <input type="number" min="0" max="365" value={tp.day} onChange={(e) => onChange({ ...tp, day: Number(e.target.value) })} data-testid="drawer-day"
                  className="w-full bg-white border border-[#E8E0F5] px-3 py-2 rounded-md text-sm mt-1" />
              </div>
              <div>
                <label className="text-[9px] font-bold uppercase tracking-wider text-[#9B8AB0]">Hour (0-23)</label>
                <input type="number" min="0" max="23" value={tp.hour} onChange={(e) => onChange({ ...tp, hour: Number(e.target.value) })} data-testid="drawer-hour"
                  className="w-full bg-white border border-[#E8E0F5] px-3 py-2 rounded-md text-sm mt-1" />
              </div>
              <div>
                <label className="text-[9px] font-bold uppercase tracking-wider text-[#9B8AB0]">Channel</label>
                <select value={tp.channel} onChange={(e) => onChange({ ...tp, channel: e.target.value })} data-testid="drawer-channel"
                  className="w-full bg-white border border-[#E8E0F5] px-3 py-2 rounded-md text-sm mt-1">
                  {Object.entries(CHANNEL_META).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
                </select>
              </div>
              <div>
                <label className="text-[9px] font-bold uppercase tracking-wider text-[#9B8AB0]">Type</label>
                <select value={tp.message_type} onChange={(e) => onChange({ ...tp, message_type: e.target.value })} data-testid="drawer-type"
                  className="w-full bg-white border border-[#E8E0F5] px-3 py-2 rounded-md text-sm mt-1">
                  {Object.entries(TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </div>
              <div>
                <label className="text-[9px] font-bold uppercase tracking-wider text-[#9B8AB0]">Role</label>
                <select value={tp.aria_role} onChange={(e) => onChange({ ...tp, aria_role: e.target.value })} data-testid="drawer-role"
                  className="w-full bg-white border border-[#E8E0F5] px-3 py-2 rounded-md text-sm mt-1">
                  <option value="autonomous">Aria handles</option>
                  <option value="alert_human">Alert me</option>
                </select>
              </div>
              <div>
                <label className="text-[9px] font-bold uppercase tracking-wider text-[#9B8AB0]">Condition</label>
                <select value={tp.trigger || ''} onChange={(e) => onChange({ ...tp, trigger: e.target.value })} data-testid="drawer-trigger"
                  className="w-full bg-white border border-[#E8E0F5] px-3 py-2 rounded-md text-sm mt-1">
                  {CONDITIONS.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
                </select>
              </div>
            </div>

            <div>
              <label className="text-[9px] font-bold uppercase tracking-wider text-[#9B8AB0]">Message Aria will send</label>
              <textarea
                rows={6}
                value={tp.message_template}
                onChange={(e) => onChange({ ...tp, message_template: e.target.value })}
                data-testid="drawer-message"
                placeholder="Hi {{first_name}}, I noticed you…"
                className="w-full bg-[#FAFAFA] border border-[#E8E0F5] text-[#1A0A2E] px-3 py-2.5 rounded-md text-sm mt-1 leading-relaxed resize-y"
              />
              <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                <span className="text-[9px] font-bold uppercase tracking-wider text-[#9B8AB0] mr-1">Insert:</span>
                {TOKENS.map((tok) => (
                  <button key={tok} type="button" onClick={() => onChange({ ...tp, message_template: (tp.message_template || '') + ' ' + tok })}
                    className="text-[10px] px-2 py-0.5 bg-[#F4F0FF] text-[#7C35DC] rounded font-mono hover:bg-[#E0D4F7]">{tok}</button>
                ))}
              </div>
            </div>

            {/* Iter 54 — Per-touchpoint branching logic (shared with /outreach builder) */}
            <div className="pt-2 border-t border-[#F0ECF9]">
              <ConditionsInspector
                conditions={tp.conditions || {}}
                currentStep={(tp.index || 0) + 1}
                maxStep={32}
                onChange={(next) => onChange({ ...tp, conditions: next })}
              />
            </div>

            <div className="flex items-center gap-2 pt-2 border-t border-[#F0ECF9]">
              <button onClick={() => onMove(tp.index, -1)} disabled={isFirst} data-testid="drawer-move-up"
                className="px-3 py-1.5 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-md text-xs font-bold disabled:opacity-30">↑ Move up</button>
              <button onClick={() => onMove(tp.index, 1)} disabled={isLast} data-testid="drawer-move-down"
                className="px-3 py-1.5 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-md text-xs font-bold disabled:opacity-30">↓ Move down</button>
              <button onClick={onDuplicate} data-testid="drawer-duplicate"
                className="inline-flex items-center gap-1 px-3 py-1.5 bg-white border border-[#7C35DC]/30 text-[#7C35DC] rounded-md text-xs font-bold hover:bg-[#F4F0FF]">
                <Copy size={11} /> Duplicate
              </button>
              <button onClick={onDelete} data-testid="drawer-delete"
                className="ml-auto inline-flex items-center gap-1 px-3 py-1.5 bg-white border border-[#DC2626]/30 text-[#DC2626] rounded-md text-xs font-bold hover:bg-[#FEE2E2]">
                <Trash size={11} /> Delete
              </button>
            </div>
          </>
        )}

        {tab === 'performance' && (
          <>
            <div className="flex items-center justify-between p-4 rounded-xl border" style={{ background: g.bg, borderColor: g.border + '55' }}>
              <div>
                <div className="text-[10px] font-bold uppercase tracking-[0.18em]" style={{ color: g.color }}>Effectiveness</div>
                <div className="text-3xl font-extrabold mt-0.5" style={{ color: g.color, fontFamily: 'Plus Jakarta Sans' }}>{perf?.effectiveness ?? 0}</div>
                <div className="text-xs font-bold mt-0.5" style={{ color: g.color }}>Grade {grade}</div>
              </div>
              <div className="text-right space-y-0.5">
                <div className="text-[10px] font-bold uppercase tracking-wider text-[#5A4A7A]">Composite of</div>
                <div className="text-[10px] text-[#5A4A7A]">60% reply rate · 30% delivery</div>
                <div className="text-[10px] text-[#5A4A7A]">10% (low) skip rate</div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2" data-testid="perf-grid">
              {[
                { label: 'Scheduled', value: perf?.total_scheduled || 0, color: '#7C35DC', icon: Lightning },
                { label: 'Sent', value: perf?.sent || 0, color: '#0055FF', icon: ChatCircle },
                { label: 'Replies', value: perf?.replies || 0, color: '#16A34A', icon: ThumbsUp },
                { label: 'Skipped', value: perf?.skipped || 0, color: '#D97706', icon: ArrowsCounterClockwise },
                { label: 'Failed', value: perf?.failed || 0, color: '#DC2626', icon: Warning },
                { label: 'Pending', value: perf?.pending || 0, color: '#5A4A7A', icon: ClockCounterClockwise },
              ].map((s) => (
                <div key={s.label} className="p-3 bg-[#FAFAFA] border border-[#F0ECF9] rounded-lg">
                  <div className="flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-wider text-[#9B8AB0]">
                    <s.icon size={10} weight="fill" style={{ color: s.color }} /> {s.label}
                  </div>
                  <div className="text-xl font-extrabold mt-1" style={{ color: s.color, fontFamily: 'Plus Jakarta Sans' }}>{s.value}</div>
                </div>
              ))}
            </div>

            <div className="space-y-2">
              <ScoreBar label="Reply rate" value={perf?.reply_rate || 0} max={100} color="#16A34A" />
              <ScoreBar label="Delivery rate" value={perf?.delivery_rate || 0} max={100} color="#0055FF" />
              <ScoreBar label="Skip rate" value={perf?.skip_rate || 0} max={100} color="#D97706" />
            </div>

            {(perf?.total_scheduled || 0) === 0 && (
              <div className="text-xs text-[#9B8AB0] italic text-center py-3 border-t border-[#F0ECF9]">
                No leads have reached this touchpoint yet. Metrics appear once Aria starts firing it.
              </div>
            )}
          </>
        )}

        {tab === 'fit' && (
          <>
            <div className="p-4 rounded-xl bg-[#FAF7FF] border border-[#E0D4F7]">
              <h4 className="text-sm font-bold text-[#1A0A2E] mb-1" style={{ fontFamily: 'Plus Jakarta Sans' }}>Lead fit at this step</h4>
              <p className="text-xs text-[#5A4A7A]">Distribution of leads (by ICP tier) who have received this touchpoint.</p>
            </div>

            <div className="space-y-2" data-testid="fit-bars">
              {[
                { key: 'hot', label: 'Hot leads', icon: Fire, color: '#DC2626', val: fit?.hot || 0 },
                { key: 'warm', label: 'Warm leads', icon: Sparkle, color: '#D97706', val: fit?.warm || 0 },
                { key: 'cold', label: 'Cold leads', icon: Snowflake, color: '#0055FF', val: fit?.cold || 0 },
              ].map((row) => {
                const total = fit?.total || 0;
                const pct = total ? Math.round((row.val / total) * 100) : 0;
                return (
                  <div key={row.key} className="p-3 bg-white border border-[#E8E0F5] rounded-lg">
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2">
                        <row.icon size={14} weight="fill" style={{ color: row.color }} />
                        <span className="text-sm font-bold text-[#1A0A2E]">{row.label}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-extrabold" style={{ color: row.color }}>{row.val}</span>
                        <span className="text-[10px] font-bold text-[#9B8AB0]">({pct}%)</span>
                      </div>
                    </div>
                    <div className="h-1.5 bg-[#F0ECF9] rounded-full overflow-hidden">
                      <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: row.color }}></div>
                    </div>
                  </div>
                );
              })}
            </div>

            {(fit?.total || 0) === 0 && (
              <div className="text-xs text-[#9B8AB0] italic text-center py-3 border-t border-[#F0ECF9]">
                No leads have reached this step yet.
              </div>
            )}
          </>
        )}

        {tab === 'ai' && (
          <>
            {!ai ? (
              <div className="p-6 text-center">
                <Brain size={28} weight="duotone" className="text-[#7C35DC] mx-auto mb-2" />
                <p className="text-sm text-[#5A4A7A]">Hit <strong>"Score with AI"</strong> at the top to let Claude rate this touchpoint.</p>
              </div>
            ) : (
              <>
                <div className="flex items-center justify-between p-4 rounded-xl border border-[#7C35DC]/30" style={{ background: 'linear-gradient(135deg, #FAF7FF 0%, #FFFFFF 100%)' }}>
                  <div>
                    <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#7C35DC]">AI Quality</div>
                    <div className="text-3xl font-extrabold text-[#7C35DC] mt-0.5" style={{ fontFamily: 'Plus Jakarta Sans' }}>{ai.average}<span className="text-base text-[#9B8AB0]">/10</span></div>
                  </div>
                  <Brain size={36} weight="duotone" className="text-[#7C35DC]/40" />
                </div>

                <div className="space-y-3" data-testid="ai-scorebars">
                  <ScoreBar label="Clarity" value={ai.clarity} />
                  <ScoreBar label="Personalisation" value={ai.personalisation} color="#C044E0" />
                  <ScoreBar label="CTA strength" value={ai.cta} color="#16A34A" />
                  <ScoreBar label="Tone-fit" value={ai.tone_fit} color="#D97706" />
                </div>

                {ai.verdict && (
                  <div className="p-3 rounded-lg bg-[#FEF3C7] border border-[#D97706]/30">
                    <div className="text-[9px] font-bold uppercase tracking-wider text-[#92400E] mb-1">Aria's verdict</div>
                    <p className="text-xs text-[#92400E] leading-relaxed">{ai.verdict}</p>
                  </div>
                )}

                {!ai.ai_powered && (
                  <p className="text-[10px] text-[#9B8AB0] italic text-center">Heuristic fallback — Claude key not configured.</p>
                )}
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
};

// ──────────────────────────────────────────────────────────────────────────
// Template Library Modal — unchanged from previous version
// ──────────────────────────────────────────────────────────────────────────
const TemplateLibraryModal = ({ onClose, onApply }) => {
  const [tpls, setTpls] = useState([]);
  const [previewing, setPreviewing] = useState(null);
  useEffect(() => { api.get('/api/touchpoints/templates').then((r) => setTpls(r.data?.templates || [])); }, []);

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4" data-testid="template-library-modal">
      <div className="bg-white border border-[#E8E0F5] rounded-2xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
        <div className="flex items-center justify-between p-5 border-b border-[#E8E0F5]">
          <div>
            <h3 className="text-lg font-bold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Template Library</h3>
            <p className="text-xs text-[#9B8AB0]">8 universal sequences. Pick one to replace your current map.</p>
          </div>
          <button onClick={onClose}><X size={20} className="text-[#9B8AB0]" /></button>
        </div>
        <div className="p-5 overflow-y-auto flex-1">
          {previewing ? (
            <div>
              <button onClick={() => setPreviewing(null)} className="text-xs font-bold text-[#7C35DC] mb-3 inline-flex items-center gap-1"><ArrowLeft size={12} /> Back to library</button>
              <h4 className="font-bold text-[#1A0A2E]">{previewing.name}</h4>
              <p className="text-xs text-[#5A4A7A] mb-3">{previewing.description}</p>
              <div className="space-y-1.5 max-h-80 overflow-y-auto">
                {(previewing.touchpoints || []).map((tp, i) => (
                  <div key={i} className="text-xs px-3 py-2 border border-[#F0ECF9] rounded bg-[#FAF7FF]">
                    <span className="font-mono font-bold text-[#7C35DC]">TP-{String(i + 1).padStart(2, '0')}</span> · Day {tp.day} · {CHANNEL_META[tp.channel]?.label || tp.channel} · {TYPE_LABELS[tp.message_type] || tp.message_type}
                    <div className="text-[#5A4A7A] mt-1 line-clamp-2">{tp.message_template}</div>
                  </div>
                ))}
              </div>
              <button onClick={() => { if (window.confirm(`Replace your current touchpoint map with "${previewing.name}" (${previewing.touchpoints?.length} touchpoints)?`)) { onApply(previewing); onClose(); } }} data-testid="apply-template-btn"
                className="mt-4 w-full px-4 py-2.5 btn-gradient rounded-lg text-sm font-bold" style={{ fontFamily: 'Plus Jakarta Sans' }}>Apply this template</button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {tpls.map((t) => (
                <button key={t.id} onClick={() => setPreviewing(t)} data-testid={`tpl-card-${t.id}`}
                  className="text-left p-4 bg-white border border-[#E8E0F5] hover:border-[#7C35DC]/40 rounded-xl transition-all group">
                  <div className="flex items-center gap-2 mb-2">
                    <Sparkle size={16} weight="fill" className="text-[#7C35DC]" />
                    <h4 className="font-bold text-[#1A0A2E]">{t.name}</h4>
                  </div>
                  <p className="text-xs text-[#5A4A7A] mb-3 line-clamp-2">{t.description}</p>
                  <div className="flex items-center gap-3 text-[10px] font-bold text-[#9B8AB0]">
                    <span>{t.touchpoint_count || (t.touchpoints?.length || 0)} touchpoints</span>
                    <span>·</span>
                    <span>{t.duration_days}d</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// ──────────────────────────────────────────────────────────────────────────
// Version History Modal — unchanged
// ──────────────────────────────────────────────────────────────────────────
const VersionHistoryModal = ({ onClose, onRestored }) => {
  const [versions, setVersions] = useState([]);
  const [busy, setBusy] = useState(null);
  useEffect(() => { api.get('/api/touchpoints/map/versions').then((r) => setVersions(r.data?.versions || [])); }, []);

  const restore = async (id) => {
    if (!window.confirm('Restore this version? Your current map will be snapshotted first.')) return;
    setBusy(id);
    try { await api.post(`/api/touchpoints/map/versions/${id}/restore`); toast.success('Version restored'); onRestored(); onClose(); }
    catch (e) { toast.error(e.response?.data?.detail || 'Restore failed'); }
    finally { setBusy(null); }
  };

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4" data-testid="version-history-modal">
      <div className="bg-white border border-[#E8E0F5] rounded-2xl w-full max-w-lg max-h-[90vh] overflow-hidden flex flex-col">
        <div className="flex items-center justify-between p-5 border-b border-[#E8E0F5]">
          <h3 className="text-lg font-bold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Version History</h3>
          <button onClick={onClose}><X size={20} className="text-[#9B8AB0]" /></button>
        </div>
        <div className="p-5 overflow-y-auto flex-1 space-y-2">
          {versions.length === 0 ? (
            <div className="text-sm text-[#9B8AB0] py-8 text-center">No previous versions yet. They'll appear here every time you save.</div>
          ) : versions.map((v) => (
            <div key={v.id} className="flex items-center justify-between p-3 border border-[#E8E0F5] rounded-lg hover:border-[#7C35DC]/40" data-testid={`ver-row-${v.id}`}>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-bold text-[#1A0A2E]">{v.template_name || 'Custom map'} · {v.touchpoint_count} touchpoints</div>
                <div className="text-xs text-[#9B8AB0]">Saved {fmt(v.created_at)} by {v.saved_by || '—'}</div>
              </div>
              <button onClick={() => restore(v.id)} disabled={busy === v.id} data-testid={`restore-${v.id}`} className="px-3 py-1.5 bg-white border border-[#7C35DC]/30 text-[#7C35DC] rounded-md text-xs font-bold hover:bg-[#F4F0FF] disabled:opacity-40">{busy === v.id ? '…' : 'Restore'}</button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

// ──────────────────────────────────────────────────────────────────────────
// Document Upload Modal — unchanged
// ──────────────────────────────────────────────────────────────────────────
const DocumentUploadModal = ({ onClose, onApply }) => {
  const [stage, setStage] = useState('upload');
  const [preview, setPreview] = useState([]);
  const [meta, setMeta] = useState(null);
  const [busy, setBusy] = useState(false);

  const handleFile = async (file) => {
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) { toast.error('File over 10MB'); return; }
    setStage('parsing');
    setBusy(true);
    try {
      const form = new FormData();
      form.append('file', file);
      // CRITICAL: force multipart content-type (axios instance default is application/json,
      // which makes FastAPI reject the upload with a 422 Pydantic error array → renders
      // crash the React tree if surfaced as a toast).
      const r = await api.post('/api/touchpoints/import-document', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setPreview(r.data?.preview || []);
      setMeta({ filename: r.data?.source_filename, count: r.data?.extracted_count, truncated: r.data?.truncated });
      setStage('preview');
    } catch (e) {
      // Defensive: FastAPI 422 returns detail as an Array<object>; convert to a string
      // so Sonner doesn't choke trying to render an object as a React child.
      const detail = e?.response?.data?.detail;
      let msg = 'Import failed';
      if (typeof detail === 'string') msg = detail;
      else if (Array.isArray(detail)) msg = detail.map((d) => d?.msg || JSON.stringify(d)).join('; ');
      else if (detail && typeof detail === 'object') msg = detail.message || detail.error || JSON.stringify(detail);
      else if (e?.message) msg = e.message;
      toast.error(msg);
      setStage('upload');
    } finally { setBusy(false); }
  };

  const apply = () => { onApply(preview); onClose(); };

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4" data-testid="doc-upload-modal">
      <div className="bg-white border border-[#E8E0F5] rounded-2xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
        <div className="flex items-center justify-between p-5 border-b border-[#E8E0F5]">
          <div>
            <h3 className="text-lg font-bold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Import Your Touchpoint Sequence</h3>
            <p className="text-xs text-[#9B8AB0]">Upload your existing sales sequence — Aria reads it and extracts each step.</p>
          </div>
          <button onClick={onClose}><X size={20} className="text-[#9B8AB0]" /></button>
        </div>

        {stage === 'upload' && (
          <div className="p-5 overflow-y-auto">
            <label className="block border-2 border-dashed border-[#E8E0F5] hover:border-[#7C35DC]/40 rounded-2xl p-10 text-center cursor-pointer transition-all" data-testid="doc-dropzone">
              <FileArrowUp size={32} weight="duotone" className="text-[#7C35DC] mx-auto mb-3" />
              <div className="text-sm font-bold text-[#1A0A2E] mb-1">Drag your sequence document here, or click to browse</div>
              <div className="text-xs text-[#9B8AB0]">Max 10MB</div>
              <div className="flex items-center justify-center gap-1.5 mt-3">
                {['PDF', 'DOCX', 'XLSX'].map((f) => <span key={f} className="text-[10px] font-bold px-2 py-0.5 rounded bg-[#F4F0FF] text-[#7C35DC]">{f}</span>)}
              </div>
              <input type="file" accept=".pdf,.docx,.doc,.xlsx,.xls" className="hidden" onChange={(e) => handleFile(e.target.files?.[0])} data-testid="doc-file-input" />
            </label>
          </div>
        )}

        {stage === 'parsing' && (
          <div className="p-10 text-center">
            <ArrowsClockwise size={28} className="text-[#7C35DC] mx-auto mb-3 animate-spin" />
            <div className="text-sm font-bold text-[#1A0A2E]">Aria is reading your document…</div>
            <div className="text-xs text-[#9B8AB0]">This usually takes 5-15 seconds.</div>
          </div>
        )}

        {stage === 'preview' && (
          <>
            <div className="px-5 pt-3 pb-2 border-b border-[#F0ECF9] flex items-center gap-2">
              <FileText size={14} className="text-[#7C35DC]" />
              <span className="text-xs font-bold text-[#1A0A2E]">{meta?.filename}</span>
              <span className="text-xs text-[#9B8AB0]">· {meta?.count} touchpoints extracted</span>
              {meta?.truncated && (
                <span className="ml-auto inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-bold rounded bg-[#FEF3C7] text-[#D97706] border border-[#D97706]/30">
                  <Warning size={10} weight="fill" /> Document had &gt; 32 touchpoints — first 32 imported
                </span>
              )}
            </div>
            <div className="overflow-y-auto flex-1 p-5">
              <div className="space-y-1.5">
                {preview.map((tp, i) => (
                  <div key={i} className="text-xs px-3 py-2 border border-[#F0ECF9] rounded bg-[#FAF7FF]" data-testid={`doc-row-${i}`}>
                    <span className="font-mono font-bold text-[#7C35DC]">TP-{String(i + 1).padStart(2, '0')}</span> · Day {tp.day} · {CHANNEL_META[tp.channel]?.label || tp.channel} · {TYPE_LABELS[tp.message_type] || tp.message_type}
                    <div className="text-[#5A4A7A] mt-1 line-clamp-2">{tp.message_template}</div>
                  </div>
                ))}
              </div>
            </div>
            <div className="px-5 py-4 border-t border-[#E8E0F5] flex items-center justify-end gap-2">
              <button onClick={() => { setStage('upload'); setPreview([]); }} className="px-4 py-2 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-lg text-sm font-medium">Upload different file</button>
              <button onClick={apply} data-testid="doc-apply-btn" disabled={busy || preview.length === 0} className="px-5 py-2 btn-gradient rounded-lg text-sm font-bold disabled:opacity-40" style={{ fontFamily: 'Plus Jakarta Sans' }}>Apply to my journey</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

// ──────────────────────────────────────────────────────────────────────────
// Top-level page
// ──────────────────────────────────────────────────────────────────────────
const TouchpointJourney = () => {
  const [map, setMap] = useState(null);
  const [draft, setDraft] = useState([]);
  const [selectedIdx, setSelectedIdx] = useState(null);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showLibrary, setShowLibrary] = useState(false);
  const [showVersions, setShowVersions] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [viewMode, setViewMode] = useState('timeline');   // 'timeline' | 'flowchart'

  const [scoring, setScoring] = useState(null);   // { items: [...], journey: {...} }
  const [ai, setAi] = useState(null);             // { items: [...] }
  const [aiBusy, setAiBusy] = useState(false);

  const load = async () => {
    const r = await api.get('/api/touchpoints/map');
    const m = r.data?.map;
    setMap(m);
    setDraft((m?.touchpoints || []).map((tp, i) => ({ ...tp, index: i })));
    setDirty(false);
  };

  const loadScoring = async () => {
    try {
      const r = await api.get('/api/touchpoints/scoring');
      setScoring(r.data);
    } catch { /* graceful */ }
  };

  useEffect(() => { load(); loadScoring(); }, []);

  // Auto-select first touchpoint when map loads if nothing selected
  useEffect(() => {
    if (draft.length > 0 && selectedIdx === null) setSelectedIdx(0);
    if (draft.length > 0 && selectedIdx !== null && selectedIdx >= draft.length) setSelectedIdx(draft.length - 1);
  }, [draft.length, selectedIdx]);

  const counterTone = useMemo(() => {
    const n = draft.length;
    if (n >= MAX_TOUCHPOINTS) return 'text-[#DC2626]';
    if (n >= 28) return 'text-[#D97706]';
    return 'text-[#1A0A2E]';
  }, [draft.length]);

  const reindex = (arr) => arr.map((tp, i) => ({ ...tp, index: i }));
  const markDirty = () => setDirty(true);

  const addRow = () => {
    if (draft.length >= MAX_TOUCHPOINTS) { toast.error(`Max ${MAX_TOUCHPOINTS} touchpoints`); return; }
    const last = draft[draft.length - 1];
    const next = reindex([...draft, {
      index: draft.length,
      day: last ? Number(last.day) + 2 : 0,
      hour: 9,
      channel: 'whatsapp',
      message_type: 'follow_up',
      aria_role: 'autonomous',
      trigger: '',
      message_template: '',
    }]);
    setDraft(next);
    setSelectedIdx(next.length - 1);
    markDirty();
  };
  const updateRow = (idx, nextTp) => { setDraft(reindex(draft.map((tp, i) => i === idx ? nextTp : tp))); markDirty(); };
  const deleteRow = (idx) => {
    if (!window.confirm('Delete this touchpoint?')) return;
    const next = reindex(draft.filter((_, i) => i !== idx));
    setDraft(next);
    markDirty();
    setSelectedIdx(next.length === 0 ? null : Math.min(idx, next.length - 1));
  };
  const duplicateRow = (idx) => {
    if (draft.length >= MAX_TOUCHPOINTS) { toast.error(`Max ${MAX_TOUCHPOINTS} touchpoints`); return; }
    const copy = { ...draft[idx], day: Number(draft[idx].day) + 1 };
    const next = reindex([...draft.slice(0, idx + 1), copy, ...draft.slice(idx + 1)]);
    setDraft(next);
    setSelectedIdx(idx + 1);
    markDirty();
  };
  const moveRow = (idx, dir) => {
    const j = idx + dir;
    if (j < 0 || j >= draft.length) return;
    const next = [...draft]; [next[idx], next[j]] = [next[j], next[idx]];
    setDraft(reindex(next));
    setSelectedIdx(j);
    markDirty();
  };

  const onDragEnd = (result) => {
    if (!result.destination) return;
    if (result.source.index === result.destination.index) return;
    const next = Array.from(draft);
    const [moved] = next.splice(result.source.index, 1);
    next.splice(result.destination.index, 0, moved);
    setDraft(reindex(next));
    setSelectedIdx(result.destination.index);
    markDirty();
  };

  const save = async () => {
    setSaving(true);
    try {
      const payload = {
        template_id: map?.template_id || 'tpl_standard',
        is_customised: true,
        touchpoints: draft.map((tp) => ({
          index: tp.index, day: Number(tp.day), hour: Number(tp.hour),
          channel: tp.channel, message_type: tp.message_type, aria_role: tp.aria_role,
          trigger: tp.trigger || '', message_template: tp.message_template,
          conditions: tp.conditions || {},
        })),
      };
      await api.post('/api/touchpoints/map', payload);
      toast.success('Touchpoint map saved');
      await load();
      loadScoring();
    } catch (e) { toast.error(e.response?.data?.detail || 'Save failed'); }
    finally { setSaving(false); }
  };

  const applyTemplate = (tpl) => {
    setDraft(reindex(tpl.touchpoints || []));
    setMap({ ...(map || {}), template_id: tpl.id, template_name: tpl.name });
    setSelectedIdx(0);
    markDirty();
    toast.success(`Loaded "${tpl.name}" — review and save to apply`);
  };

  const applyImport = (rows) => {
    setDraft(reindex(rows));
    setSelectedIdx(0);
    markDirty();
    toast.success('Document imported — review and save to apply');
  };

  const scoreWithAI = async () => {
    setAiBusy(true);
    try {
      const r = await api.post('/api/touchpoints/ai-quality');
      setAi(r.data);
      toast.success('Aria scored your touchpoints');
    } catch (e) { toast.error('AI scoring failed'); }
    finally { setAiBusy(false); }
  };

  const scoringByIdx = useMemo(() => {
    const m = {};
    (scoring?.items || []).forEach((it) => { m[it.index] = it; });
    return m;
  }, [scoring]);
  const aiByIdx = useMemo(() => {
    const m = {};
    (ai?.items || []).forEach((it) => { m[it.index] = it; });
    return m;
  }, [ai]);

  const selectedTp = selectedIdx !== null && selectedIdx >= 0 && selectedIdx < draft.length ? draft[selectedIdx] : null;

  return (
    <div className="space-y-5 max-w-[1400px] mx-auto pb-10" data-testid="touchpoint-journey-page">
      <AriaSpotlight
        id="touchpoint-journey-drag-v1"
        anchorSelector='[data-testid="drag-0"]'
        placement="right"
        title="Drag to reorder"
        body="Aria fires touchpoints in the exact order you set here. Drag any card up or down to change the sequence."
      />
      {/* ─── Header ───────────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC]">Aria's core engine</span>
          </div>
          <h1 className="text-3xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Touchpoint Mapping</h1>
          <p className="text-sm text-[#5A4A7A] mt-1">
            {map?.template_name || 'No template'} · saved {fmt(map?.updated_at)} by {map?.saved_by || '—'}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button onClick={() => setShowLibrary(true)} data-testid="open-library-btn" className="inline-flex items-center gap-1.5 px-3 py-2 bg-white border border-[#7C35DC]/30 text-[#7C35DC] rounded-lg text-xs font-bold hover:bg-[#F4F0FF]">
            <BookOpen size={12} weight="fill" /> Templates
          </button>
          <button onClick={() => setShowUpload(true)} data-testid="open-upload-btn" className="inline-flex items-center gap-1.5 px-3 py-2 bg-white border border-[#E2B96F]/40 text-[#9A6F1A] rounded-lg text-xs font-bold hover:bg-[#FEF3C7]">
            <UploadSimple size={12} weight="bold" /> Import doc
          </button>
          <button onClick={() => setShowVersions(true)} data-testid="open-versions-btn" className="inline-flex items-center gap-1.5 px-3 py-2 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-lg text-xs font-bold hover:bg-[#F9F5FF]">
            <ClockCounterClockwise size={12} weight="fill" /> History
          </button>
          <button
            onClick={save}
            disabled={saving || draft.length === 0 || !dirty}
            data-testid="save-map-btn"
            className="inline-flex items-center gap-1.5 px-4 py-2 btn-gradient rounded-lg text-xs font-bold disabled:opacity-40"
            style={{ fontFamily: 'Plus Jakarta Sans' }}>
            {saving ? 'Saving…' : dirty ? 'Save changes' : 'Saved'}
          </button>
        </div>
      </div>

      {/* ─── 5-Stage explainer hero ─────────────────────────────────────── */}
      <JourneyStagesHero draft={draft} />

      {/* ─── Journey score banner ─────────────────────────────────────────── */}
      <JourneyScoreBanner journey={scoring?.journey} onScoreAI={scoreWithAI} aiBusy={aiBusy} />

      {/* ─── Counter bar ──────────────────────────────────────────────────── */}
      <div className="bg-[#F4F0FF] border border-[#E0D4F7] rounded-xl px-5 py-3 flex items-center justify-between flex-wrap gap-3" data-testid="tp-counter-bar">
        <div className="flex items-center gap-2 text-sm text-[#5A4A7A]">
          <Sparkle size={16} weight="fill" className="text-[#7C35DC]" />
          <span><strong className={counterTone}>{draft.length}</strong> / {MAX_TOUCHPOINTS} touchpoints — drag to reorder, click any card to edit</span>
        </div>
        <div className="flex items-center gap-3">
          {/* View mode toggle — Timeline / Flowchart */}
          <div className="inline-flex bg-white border border-[#E0D4F7] rounded-lg p-0.5" data-testid="view-mode-toggle">
            <button
              type="button"
              onClick={() => setViewMode('timeline')}
              data-testid="view-mode-timeline"
              className={`px-3 py-1.5 text-xs font-semibold rounded ${viewMode === 'timeline' ? 'bg-[#7C35DC] text-white shadow-sm' : 'text-[#5A4A7A] hover:bg-[#F4F0FF]'}`}
            >
              Timeline
            </button>
            <button
              type="button"
              onClick={() => setViewMode('flowchart')}
              data-testid="view-mode-flowchart"
              className={`px-3 py-1.5 text-xs font-semibold rounded ${viewMode === 'flowchart' ? 'bg-[#7C35DC] text-white shadow-sm' : 'text-[#5A4A7A] hover:bg-[#F4F0FF]'}`}
            >
              Flowchart
            </button>
          </div>
          {draft.length >= 28 && draft.length < MAX_TOUCHPOINTS && (
            <span className="text-xs font-bold text-[#D97706] inline-flex items-center gap-1"><Warning size={12} weight="fill" /> Nearing the {MAX_TOUCHPOINTS}-touchpoint limit</span>
          )}
          {draft.length >= MAX_TOUCHPOINTS && (
            <span className="text-xs font-bold text-[#DC2626] inline-flex items-center gap-1"><Warning size={12} weight="fill" /> Max {MAX_TOUCHPOINTS} reached</span>
          )}
        </div>
      </div>

      {/* ─── Flowchart view (Expandi-style branching) ────────────────────── */}
      {viewMode === 'flowchart' && (
        <div className="bg-white border border-[#E8E0F5] rounded-2xl p-3 relative">
          <JourneyFlowchart touchpoints={draft} />
        </div>
      )}

      {/* ─── Two-column layout: vertical timeline + side detail drawer ────── */}
      {viewMode === 'timeline' && (
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_440px] gap-5">

        {/* LEFT: Vertical timeline with drag-and-drop */}
        <div data-testid="vertical-timeline">
          {draft.length === 0 ? (
            <div className="bg-white border border-[#E8E0F5] rounded-xl p-10 text-center">
              <Sparkle size={32} weight="duotone" className="text-[#7C35DC] mx-auto mb-3" />
              <p className="text-sm text-[#5A4A7A]">No touchpoints yet. Start with a template, import from a document, or build from scratch.</p>
            </div>
          ) : (
            <DragDropContext onDragEnd={onDragEnd}>
              <Droppable droppableId="touchpoints" isDropDisabled={false} isCombineEnabled={false} ignoreContainerClipping={false}>
                {(provided) => (
                  <div {...provided.droppableProps} ref={provided.innerRef} className="space-y-3 relative">
                    {/* Vertical connector line behind cards */}
                    <div className="absolute left-[42px] top-4 bottom-4 w-px border-l-2 border-dashed border-[#E0D4F7] -z-10"></div>

                    {draft.map((tp, idx) => (
                      <Draggable key={tp.index} draggableId={`tp-${tp.index}`} index={idx}>
                        {(prov, snapshot) => (
                          <div
                            ref={prov.innerRef}
                            {...prov.draggableProps}
                            style={{
                              ...prov.draggableProps.style,
                              opacity: snapshot.isDragging ? 0.85 : 1,
                            }}
                          >
                            <TimelineRow
                              tp={tp}
                              scoring={scoringByIdx[tp.index]}
                              ai={aiByIdx[tp.index]}
                              selected={selectedIdx === idx}
                              onSelect={setSelectedIdx}
                              dragHandleProps={prov.dragHandleProps}
                            />
                          </div>
                        )}
                      </Draggable>
                    ))}
                    {provided.placeholder}
                  </div>
                )}
              </Droppable>
            </DragDropContext>
          )}

          <button onClick={addRow} disabled={draft.length >= MAX_TOUCHPOINTS} data-testid="add-row-btn"
            className="w-full mt-3 border-2 border-dashed border-[#E0D4F7] hover:border-[#7C35DC]/50 rounded-xl p-4 text-sm font-bold text-[#7C35DC] hover:bg-[#FAF7FF] disabled:opacity-40 disabled:cursor-not-allowed inline-flex items-center justify-center gap-2">
            <Plus size={14} weight="bold" /> Add a touchpoint
          </button>
        </div>

        {/* RIGHT: Side drawer */}
        <div>
          {selectedTp ? (
            <DetailDrawer
              tp={selectedTp}
              scoring={scoringByIdx[selectedTp.index]}
              ai={aiByIdx[selectedTp.index]}
              total={draft.length}
              isFirst={selectedIdx === 0}
              isLast={selectedIdx === draft.length - 1}
              onChange={(next) => updateRow(selectedIdx, next)}
              onDelete={() => deleteRow(selectedIdx)}
              onDuplicate={() => duplicateRow(selectedIdx)}
              onMove={moveRow}
              onClose={() => setSelectedIdx(null)}
            />
          ) : (
            <div className="bg-white border border-[#E8E0F5] rounded-2xl p-8 text-center sticky top-4" data-testid="drawer-empty">
              <Sparkle size={28} weight="duotone" className="text-[#7C35DC] mx-auto mb-2" />
              <p className="text-sm text-[#5A4A7A]">Click any touchpoint to edit it and view its performance, lead-fit and AI quality scores.</p>
            </div>
          )}
        </div>
      </div>
      )}

      {showLibrary && <TemplateLibraryModal onClose={() => setShowLibrary(false)} onApply={applyTemplate} />}
      {showVersions && <VersionHistoryModal onClose={() => setShowVersions(false)} onRestored={() => { load(); loadScoring(); }} />}
      {showUpload && <DocumentUploadModal onClose={() => setShowUpload(false)} onApply={applyImport} />}
    </div>
  );
};

export default TouchpointJourney;
