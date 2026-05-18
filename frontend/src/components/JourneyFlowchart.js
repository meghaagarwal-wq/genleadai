import React, { useMemo, useState, useEffect } from 'react';
import ReactFlow, {
  Background, Controls, MiniMap, Handle, Position, useReactFlow, ReactFlowProvider,
} from 'reactflow';
import 'reactflow/dist/style.css';
import dagre from 'dagre';
import {
  WhatsappLogo, EnvelopeSimple, LinkedinLogo, Phone, ChatCircle,
  Clock, Lightning, Sparkle, Warning, StopCircle, FlagBanner, Bell, Tag, ArrowRight,
  CornersOut, Broom,
} from '@phosphor-icons/react';
import { useChannelEnabled } from '../hooks/useChannelEnabled';

// Touchpoint `channel` slug → top-level sales-channel preference key.
// Used to flag nodes whose channel the tenant hasn't actually enabled.
const TP_CHANNEL_TO_PREF = {
  whatsapp: 'whatsapp',
  email: 'email',
  linkedin_nudge: 'linkedin',
  linkedin: 'linkedin',
  call_reminder: 'phone',
  call: 'phone',
  sms: 'sms',
};

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

// Approximate node footprints — used by Dagre to leave breathing room.
const NODE_W = { message: 280, condition: 220, terminal: 220, start: 120 };
const NODE_H = { message: 100, condition: 90, terminal: 80, start: 44 };

// ─── Custom node types ──────────────────────────────────────────────────────
function MessageNode({ data }) {
  const ch = CHANNEL_META[data.channel] || CHANNEL_META.whatsapp;
  const { Icon } = ch;
  return (
    <div
      data-testid={`flow-node-step-${data.step}`}
      className={`bg-white border-2 rounded-xl shadow-sm w-[260px] hover:shadow-md transition-shadow ${data.channelDisabled ? 'opacity-60' : ''}`}
      style={{ borderColor: ch.color + '40' }}
    >
      <Handle type="target" position={Position.Left} style={{ background: ch.color, width: 8, height: 8 }} />
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
        {data.channelDisabled && (
          <div
            className="mt-1.5 inline-flex items-center gap-0.5 text-[9px] font-bold uppercase tracking-wider text-rose-700 bg-rose-50 border border-rose-200 px-1.5 py-0.5 rounded"
            data-testid={`flow-node-disabled-${data.step}`}
            title="This channel is not in your saved Sales Channel Preferences"
          >
            <Warning size={9} weight="fill" /> Channel off
          </div>
        )}
      </div>
      <Handle type="source" position={Position.Right} style={{ background: ch.color, width: 8, height: 8 }} />
    </div>
  );
}

function ConditionNode({ data }) {
  return (
    <div
      data-testid={`flow-condition-step-${data.step}`}
      className="bg-slate-900 text-white rounded-lg shadow-md w-[200px]"
    >
      <Handle type="target" position={Position.Left} style={{ background: '#0EA5E9', width: 8, height: 8 }} />
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
      <Handle type="source" position={Position.Right} id="yes" style={{ top: '30%', background: '#10B981', width: 8, height: 8 }} />
      <Handle type="source" position={Position.Right} id="no" style={{ top: '70%', background: '#F43F5E', width: 8, height: 8 }} />
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
      <Handle type="target" position={Position.Left} style={{ background: TINT.text, width: 8, height: 8 }} />
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
      <Handle type="source" position={Position.Right} style={{ background: '#fff', width: 8, height: 8 }} />
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

function buildGraph(touchpoints, isEnabledFn) {
  const nodes = [];
  const edges = [];

  // Start node
  nodes.push({ id: 'start', type: 'start', position: { x: 0, y: 0 }, data: {} });

  const sortedTps = [...touchpoints].sort((a, b) => (a.index || 0) - (b.index || 0));

  sortedTps.forEach((tp, i) => {
    const stepNum = (tp.index ?? i) + 1;
    const prefKey = TP_CHANNEL_TO_PREF[tp.channel];
    const channelDisabled = !!(isEnabledFn && prefKey && !isEnabledFn(prefKey));

    nodes.push({
      id: `step-${stepNum}`,
      type: 'message',
      position: { x: 0, y: 0 }, // Dagre fills this in.
      data: {
        step: stepNum,
        channel: tp.channel,
        channelLabel: CHANNEL_LABEL[tp.channel] || tp.channel,
        day: tp.day,
        hour: tp.hour,
        message: tp.message_template,
        role: tp.aria_role,
        channelDisabled,
      },
    });

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

  // Conditions — emit diamond + branch edge(s)
  sortedTps.forEach((tp, i) => {
    const stepNum = (tp.index ?? i) + 1;
    const conditions = tp.conditions || {};
    if (!Object.keys(conditions).length) return;

    Object.entries(conditions).forEach(([key, val]) => {
      if (!val || typeof val !== 'object') return;

      const condId = `cond-${stepNum}-${key}`;
      nodes.push({
        id: condId,
        type: 'condition',
        position: { x: 0, y: 0 },
        data: {
          step: stepNum,
          label: BRANCH_LABEL[key] || key,
          keywords: val.keywords || [],
          after_hours: val.after_hours ?? null,
        },
      });

      edges.push({
        id: `e-step-${stepNum}-${condId}`,
        source: `step-${stepNum}`,
        target: condId,
        type: 'smoothstep',
        style: { stroke: '#94A3B8', strokeWidth: 1.5, strokeDasharray: '4 4' },
      });

      const action = val.action;
      if (action === 'move_to_step' && val.target_step) {
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
      } else {
        const termId = `term-${stepNum}-${key}`;
        nodes.push({
          id: termId,
          type: 'terminal',
          position: { x: 0, y: 0 },
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
    });
  });

  return { nodes, edges };
}

// ─── Dagre auto-layout pass ────────────────────────────────────────────────
// Runs a directed-graph layout so cards never overlap and branches stay tidy.
// Direction: LR (left → right). The main path runs along the centre, condition
// branches naturally veer above/below depending on Dagre's rank assignment.
function layoutWithDagre(nodes, edges, opts = {}) {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({
    rankdir: opts.rankdir || 'LR',
    nodesep: opts.nodesep ?? 60,    // gap between sibling nodes on the same rank
    ranksep: opts.ranksep ?? 100,   // gap between ranks (= columns when LR)
    marginx: 30,
    marginy: 30,
  });

  nodes.forEach((n) => {
    g.setNode(n.id, {
      width: NODE_W[n.type] || 240,
      height: NODE_H[n.type] || 80,
    });
  });
  edges.forEach((e) => g.setEdge(e.source, e.target));

  dagre.layout(g);

  return nodes.map((n) => {
    const pos = g.node(n.id);
    if (!pos) return n;
    return {
      ...n,
      // Dagre returns the centre; React Flow needs the top-left corner.
      position: { x: pos.x - (NODE_W[n.type] || 240) / 2, y: pos.y - (NODE_H[n.type] || 80) / 2 },
      // Hint React Flow about source/target handles after rotation so edge endpoints look natural.
      sourcePosition: opts.rankdir === 'TB' ? Position.Bottom : Position.Right,
      targetPosition: opts.rankdir === 'TB' ? Position.Top : Position.Left,
    };
  });
}

// ─── Main exported component ────────────────────────────────────────────────
function FlowchartInner({ touchpoints }) {
  const { isEnabled } = useChannelEnabled();
  const { fitView, zoomIn, zoomOut } = useReactFlow();
  const [rankdir, setRankdir] = useState('LR'); // 'LR' (default) | 'TB'
  // Bumping this key forces React Flow to remount + re-run fitView, which we
  // need after Auto-clean / direction toggle because Dagre changes positions.
  const [layoutKey, setLayoutKey] = useState(0);

  const { nodes, edges } = useMemo(() => {
    const raw = buildGraph(touchpoints || [], isEnabled);
    return {
      nodes: layoutWithDagre(raw.nodes, raw.edges, { rankdir }),
      edges: raw.edges,
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [touchpoints, isEnabled, rankdir, layoutKey]);

  // Re-fit the viewport whenever the layout key changes (Auto-clean / direction).
  useEffect(() => {
    const t = setTimeout(() => fitView({ padding: 0.2, duration: 500, minZoom: 0.3, maxZoom: 1.4 }), 60);
    return () => clearTimeout(t);
  }, [layoutKey, rankdir, fitView]);

  return (
    <div
      data-testid="journey-flowchart"
      className="w-full h-[800px] bg-slate-50 border border-slate-200 rounded-2xl overflow-hidden relative"
    >
      <ReactFlow
        key={`rf-${layoutKey}-${rankdir}`}
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2, minZoom: 0.3, maxZoom: 1.4 }}
        proOptions={{ hideAttribution: true }}
        nodesDraggable
        nodesConnectable={false}
        elevateEdgesOnSelect
      >
        <Background gap={16} size={1} color="#CBD5E1" />
        <Controls position="bottom-right" showInteractive={false} />
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

      {/* Toolbar — auto-clean, direction toggle, fit/zoom */}
      <div
        className="absolute right-4 top-4 flex items-center gap-1.5 bg-white border border-slate-200 rounded-lg p-1 shadow-sm z-10"
        data-testid="flowchart-toolbar"
      >
        <button
          type="button"
          onClick={() => setLayoutKey((k) => k + 1)}
          title="Re-run auto-layout to remove any overlap"
          data-testid="flowchart-auto-clean"
          className="inline-flex items-center gap-1 px-2.5 py-1 text-[10px] font-bold text-[#7C35DC] hover:bg-[#F4F0FF] rounded"
        >
          <Broom size={11} weight="duotone" /> Auto-clean
        </button>
        <button
          type="button"
          onClick={() => setRankdir((d) => (d === 'LR' ? 'TB' : 'LR'))}
          title={rankdir === 'LR' ? 'Switch to top-to-bottom' : 'Switch to left-to-right'}
          data-testid="flowchart-direction-toggle"
          className="inline-flex items-center gap-1 px-2.5 py-1 text-[10px] font-bold text-slate-700 hover:bg-slate-100 rounded"
        >
          <ArrowRight size={11} weight={rankdir === 'LR' ? 'bold' : 'regular'} /> {rankdir === 'LR' ? 'L→R' : 'T→B'}
        </button>
        <button
          type="button"
          onClick={() => fitView({ padding: 0.2, duration: 400 })}
          title="Fit to screen"
          data-testid="flowchart-fit"
          className="inline-flex items-center gap-1 px-2.5 py-1 text-[10px] font-bold text-slate-700 hover:bg-slate-100 rounded"
        >
          <CornersOut size={11} weight="bold" /> Fit
        </button>
        <button
          type="button"
          onClick={() => zoomIn({ duration: 200 })}
          title="Zoom in"
          data-testid="flowchart-zoom-in"
          className="px-2 py-1 text-xs font-bold text-slate-700 hover:bg-slate-100 rounded"
        >
          +
        </button>
        <button
          type="button"
          onClick={() => zoomOut({ duration: 200 })}
          title="Zoom out"
          data-testid="flowchart-zoom-out"
          className="px-2 py-1 text-xs font-bold text-slate-700 hover:bg-slate-100 rounded"
        >
          −
        </button>
      </div>

      {/* Legend */}
      <div className="absolute left-4 top-4 bg-white border border-slate-200 rounded-lg px-3 py-2 shadow-sm text-[10px] flex items-center gap-3 z-10">
        <span className="flex items-center gap-1"><Sparkle size={10} weight="fill" className="text-violet-500" /> Main path</span>
        <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-emerald-500" /> Branch (yes)</span>
        <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-rose-500" /> Branch (stop/tag)</span>
      </div>
    </div>
  );
}

export default function JourneyFlowchart({ touchpoints }) {
  // ReactFlowProvider gives FlowchartInner access to fitView/zoomIn/zoomOut.
  return (
    <ReactFlowProvider>
      <FlowchartInner touchpoints={touchpoints} />
    </ReactFlowProvider>
  );
}
