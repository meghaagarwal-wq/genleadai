import React, { useMemo } from 'react';
import ReactFlow, {
  Background, Controls, MiniMap, Handle, Position,
} from 'reactflow';
import 'reactflow/dist/style.css';
import {
  WhatsappLogo, EnvelopeSimple, LinkedinLogo, Phone, ChatCircle,
  Clock, Lightning, ChatTeardropDots, Sparkle, Warning, StopCircle, FlagBanner, Bell, Tag, ArrowRight,
} from '@phosphor-icons/react';

/**
 * JourneyFlowchart — Expandi-style visual flowchart of the 32-touchpoint journey.
 *
 * Inputs: touchpoints array (with optional `conditions` per item, schema from
 * routes.outreach.validate_conditions). Renders each touchpoint as a "message
 * node" plus a "condition diamond" if any branches are enabled, with arrows to
 * branch targets.
 *
 * Layout: pure vertical for the linear path + side-branches that veer right
 * for keyword/no-reply jumps, and terminal pink cards for stop/tag/notify.
 */

const CHANNEL_META = {
  whatsapp: { Icon: WhatsappLogo, color: '#25D366', bg: '#DCFCE7' },
  email: { Icon: EnvelopeSimple, color: '#0055FF', bg: '#DCEEFE' },
  linkedin_nudge: { Icon: LinkedinLogo, color: '#0A66C2', bg: '#DCEEFE' },
  linkedin: { Icon: LinkedinLogo, color: '#0A66C2', bg: '#DCEEFE' },
  call_reminder: { Icon: Phone, color: '#F97316', bg: '#FED7AA' },
  call: { Icon: Phone, color: '#F97316', bg: '#FED7AA' },
  sms: { Icon: ChatCircle, color: '#7C35DC', bg: '#F4F0FF' },
};

const STEP_X = 360;          // horizontal canvas center
const STEP_Y_GAP = 140;      // vertical gap between consecutive steps
const BRANCH_DX = 360;       // horizontal jump for side branches
const TERMINAL_DX = 360;     // horizontal jump for pink terminal cards

// ─── Custom node types ──────────────────────────────────────────────────────
function MessageNode({ data }) {
  const ch = CHANNEL_META[data.channel] || CHANNEL_META.whatsapp;
  const { Icon } = ch;
  return (
    <div
      data-testid={`flow-node-step-${data.step}`}
      className="bg-white border-2 rounded-xl shadow-sm w-[260px] hover:shadow-md transition-shadow"
      style={{ borderColor: ch.color + '40' }}
    >
      <Handle type="target" position={Position.Top} style={{ background: ch.color, width: 8, height: 8 }} />
      <div className="px-3 py-2 flex items-center gap-2 border-b" style={{ borderColor: ch.color + '20', background: ch.bg }}>
        <Icon size={16} weight="duotone" color={ch.color} />
        <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: ch.color }}>
          Step {data.step} · {data.channelLabel || data.channel}
        </span>
        <span className="ml-auto text-[10px] font-medium text-slate-500 flex items-center gap-0.5">
          <Clock size={9} /> Day {data.day}
        </span>
      </div>
      <div className="px-3 py-2.5">
        <div className="text-xs text-slate-700 line-clamp-2 leading-snug">
          {data.message || <em className="text-slate-400">Empty message</em>}
        </div>
        {data.role === 'alert_human' && (
          <div className="mt-1.5 inline-flex items-center gap-0.5 text-[9px] font-bold uppercase tracking-wider text-amber-700 bg-amber-50 border border-amber-200 px-1.5 py-0.5 rounded">
            <Bell size={9} /> Alert me
          </div>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: ch.color, width: 8, height: 8 }} />
    </div>
  );
}

function ConditionNode({ data }) {
  return (
    <div
      data-testid={`flow-condition-step-${data.step}`}
      className="bg-slate-900 text-white rounded-lg shadow-md w-[200px]"
    >
      <Handle type="target" position={Position.Top} style={{ background: '#0EA5E9', width: 8, height: 8 }} />
      <div className="px-3 py-2 flex items-center gap-2">
        <Lightning size={14} weight="duotone" className="text-amber-300" />
        <div className="text-[11px] font-semibold leading-tight">{data.label}</div>
      </div>
      {data.keywords?.length > 0 && (
        <div className="px-3 pb-2 flex flex-wrap gap-1">
          {data.keywords.slice(0, 3).map((kw) => (
            <span key={kw} className="text-[9px] px-1.5 py-0.5 rounded bg-slate-700 text-slate-200 font-mono">{kw}</span>
          ))}
        </div>
      )}
      {data.after_hours != null && (
        <div className="px-3 pb-2 text-[10px] text-slate-300">After {data.after_hours}h silence</div>
      )}
      <Handle type="source" position={Position.Bottom} id="yes" style={{ background: '#10B981', width: 8, height: 8 }} />
      <Handle type="source" position={Position.Right} id="no" style={{ background: '#F43F5E', width: 8, height: 8 }} />
    </div>
  );
}

function TerminalNode({ data }) {
  const TINT = {
    stop: { bg: '#FEE2E2', border: '#FCA5A5', text: '#B91C1C', Icon: StopCircle, label: 'Stop journey' },
    tag_contact: { bg: '#FCE7F3', border: '#F9A8D4', text: '#9D174D', Icon: Tag, label: 'Tag contact' },
    notify_user: { bg: '#FEF3C7', border: '#FCD34D', text: '#92400E', Icon: Bell, label: 'Notify me' },
  }[data.action] || { bg: '#FEE2E2', border: '#FCA5A5', text: '#B91C1C', Icon: StopCircle, label: data.action };
  const { Icon } = TINT;
  return (
    <div
      data-testid={`flow-terminal-${data.id}`}
      className="rounded-lg shadow-sm w-[200px] border-2"
      style={{ background: TINT.bg, borderColor: TINT.border }}
    >
      <Handle type="target" position={Position.Top} style={{ background: TINT.text, width: 8, height: 8 }} />
      <div className="px-3 py-2 flex items-center gap-2">
        <Icon size={14} weight="duotone" color={TINT.text} />
        <div className="text-[11px] font-semibold" style={{ color: TINT.text }}>{TINT.label}</div>
      </div>
      {data.tag && (
        <div className="px-3 pb-2 text-[10px] font-mono" style={{ color: TINT.text }}>
          tag: {data.tag}
        </div>
      )}
    </div>
  );
}

function StartNode() {
  return (
    <div className="bg-violet-600 text-white rounded-full shadow-lg px-5 py-2 flex items-center gap-1.5">
      <FlagBanner size={14} weight="bold" />
      <span className="text-xs font-bold uppercase tracking-wider">Start</span>
      <Handle type="source" position={Position.Bottom} style={{ background: '#fff', width: 8, height: 8 }} />
    </div>
  );
}

const nodeTypes = {
  message: MessageNode,
  condition: ConditionNode,
  terminal: TerminalNode,
  start: StartNode,
};

// ─── Layout calculation ─────────────────────────────────────────────────────
const CHANNEL_LABEL = {
  whatsapp: 'WhatsApp', email: 'Email', linkedin_nudge: 'LinkedIn', linkedin: 'LinkedIn',
  call_reminder: 'Call', call: 'Call', sms: 'SMS',
};

const BRANCH_LABEL = {
  on_reply: 'When lead replies',
  on_keyword_match: 'When reply matches keyword',
  on_negative_keyword: 'When reply is negative',
  on_no_reply: 'If no reply',
};

function buildGraph(touchpoints) {
  const nodes = [];
  const edges = [];

  // Start node
  nodes.push({
    id: 'start',
    type: 'start',
    position: { x: STEP_X + 60, y: 0 },
    data: {},
  });

  const sortedTps = [...touchpoints].sort((a, b) => (a.index || 0) - (b.index || 0));
  // Map index → y position for routing branch arrows back to existing message nodes
  const stepYByIndex = {};

  sortedTps.forEach((tp, i) => {
    const stepNum = (tp.index ?? i) + 1;
    const y = STEP_Y_GAP * (i + 1);
    stepYByIndex[stepNum] = y;

    nodes.push({
      id: `step-${stepNum}`,
      type: 'message',
      position: { x: STEP_X, y },
      data: {
        step: stepNum,
        channel: tp.channel,
        channelLabel: CHANNEL_LABEL[tp.channel] || tp.channel,
        day: tp.day,
        hour: tp.hour,
        message: tp.message_template,
        role: tp.aria_role,
      },
    });

    // Edge from previous step (or start) → this step
    const prevId = i === 0 ? 'start' : `step-${stepNum - 1}`;
    edges.push({
      id: `e-${prevId}-step-${stepNum}`,
      source: prevId,
      target: `step-${stepNum}`,
      type: 'smoothstep',
      animated: i === 0,
      style: { stroke: '#94A3B8', strokeWidth: 1.5 },
    });
  });

  // Now process conditions — emit condition nodes + branch edges
  sortedTps.forEach((tp, i) => {
    const stepNum = (tp.index ?? i) + 1;
    const conditions = tp.conditions || {};
    if (!Object.keys(conditions).length) return;
    const tpY = stepYByIndex[stepNum];

    let branchOffsetIdx = 0;

    Object.entries(conditions).forEach(([key, val]) => {
      if (!val || typeof val !== 'object') return;

      // Place the condition diamond to the right of the message node
      const condId = `cond-${stepNum}-${key}`;
      const condX = STEP_X + BRANCH_DX + (branchOffsetIdx * 40);
      const condY = tpY + 20;
      nodes.push({
        id: condId,
        type: 'condition',
        position: { x: condX, y: condY },
        data: {
          step: stepNum,
          label: BRANCH_LABEL[key] || key,
          keywords: val.keywords || [],
          after_hours: val.after_hours ?? null,
        },
      });

      // Edge: message node → condition diamond
      edges.push({
        id: `e-step-${stepNum}-${condId}`,
        source: `step-${stepNum}`,
        target: condId,
        type: 'smoothstep',
        style: { stroke: '#94A3B8', strokeWidth: 1.5, strokeDasharray: '4 4' },
      });

      // Outgoing edge depending on action
      const action = val.action;
      if (action === 'move_to_step' && val.target_step) {
        const tgtY = stepYByIndex[val.target_step];
        if (tgtY != null) {
          edges.push({
            id: `e-${condId}-yes-step-${val.target_step}`,
            source: condId,
            sourceHandle: 'yes',
            target: `step-${val.target_step}`,
            type: 'smoothstep',
            label: 'yes →',
            labelStyle: { fontSize: 9, fontWeight: 700, fill: '#059669' },
            labelBgStyle: { fill: '#D1FAE5' },
            style: { stroke: '#10B981', strokeWidth: 1.8 },
            animated: true,
          });
        }
      } else {
        // Terminal node: stop / tag_contact / notify_user
        const termId = `term-${stepNum}-${key}`;
        const termY = condY + 20;
        const termX = condX + TERMINAL_DX;
        nodes.push({
          id: termId,
          type: 'terminal',
          position: { x: termX, y: termY },
          data: { id: termId, action, tag: val.tag },
        });
        edges.push({
          id: `e-${condId}-no-${termId}`,
          source: condId,
          sourceHandle: 'no',
          target: termId,
          type: 'smoothstep',
          label: action === 'stop' ? 'stop' : action === 'tag_contact' ? 'tag' : 'alert',
          labelStyle: { fontSize: 9, fontWeight: 700, fill: '#B91C1C' },
          labelBgStyle: { fill: '#FEE2E2' },
          style: { stroke: '#F43F5E', strokeWidth: 1.8 },
        });
      }

      branchOffsetIdx += 1;
    });
  });

  return { nodes, edges };
}

// ─── Main exported component ────────────────────────────────────────────────
export default function JourneyFlowchart({ touchpoints }) {
  const { nodes, edges } = useMemo(() => buildGraph(touchpoints || []), [touchpoints]);

  return (
    <div
      data-testid="journey-flowchart"
      className="w-full h-[800px] bg-slate-50 border border-slate-200 rounded-2xl overflow-hidden"
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2, minZoom: 0.4, maxZoom: 1.4 }}
        proOptions={{ hideAttribution: true }}
        nodesDraggable={true}
        nodesConnectable={false}
      >
        <Background gap={16} size={1} color="#CBD5E1" />
        <Controls position="bottom-right" />
        <MiniMap
          position="top-right"
          nodeColor={(n) => {
            if (n.type === 'condition') return '#0F172A';
            if (n.type === 'terminal') return '#F43F5E';
            if (n.type === 'start') return '#7C3AED';
            return '#94A3B8';
          }}
          pannable
          zoomable
          style={{ background: 'white' }}
        />
      </ReactFlow>

      {/* Legend */}
      <div className="absolute left-4 top-4 bg-white border border-slate-200 rounded-lg px-3 py-2 shadow-sm text-[10px] flex items-center gap-3 z-10">
        <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-slate-400" /> Linear</span>
        <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-emerald-500" /> Branch (yes)</span>
        <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-rose-500" /> Branch (stop/tag)</span>
        <span className="flex items-center gap-1"><ArrowRight size={10} /> Auto-fit zoom in bottom-right</span>
      </div>
    </div>
  );
}
