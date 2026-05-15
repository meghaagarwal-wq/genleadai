import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { DragDropContext, Droppable, Draggable } from 'react-beautiful-dnd';
import { toast } from 'sonner';
import {
  Megaphone, Plus, DotsSixVertical, WhatsappLogo, EnvelopeSimple, LinkedinLogo,
  ChatCircle, ArrowLeft, PencilSimple, Trash, FloppyDisk, Pause, Play,
  Clock, Lightning, Target, X, CaretRight, ChartLineUp, UsersFour,
  Sparkle, Check, Warning,
} from '@phosphor-icons/react';
import api from '../config/api';

const CHANNEL_ICONS = {
  whatsapp: { icon: WhatsappLogo, color: 'text-emerald-600', bg: 'bg-emerald-50', border: 'border-emerald-200' },
  email: { icon: EnvelopeSimple, color: 'text-sky-600', bg: 'bg-sky-50', border: 'border-sky-200' },
  linkedin: { icon: LinkedinLogo, color: 'text-blue-700', bg: 'bg-blue-50', border: 'border-blue-200' },
  sms: { icon: ChatCircle, color: 'text-violet-600', bg: 'bg-violet-50', border: 'border-violet-200' },
};

const TOKEN_CHIPS = ['{first_name}', '{last_name}', '{company}', '{pain_point}', '{value_prop}', '{industry}'];

const EMPTY_TP = {
  step_number: 1,
  channel: 'whatsapp',
  message_template: '',
  delay_hours: 0,
  conditions: {},
};

export default function OutreachCampaigns() {
  const { campaignId } = useParams();

  if (campaignId) return <CampaignDetail campaignId={campaignId} />;
  return <CampaignList />;
}

// ─── Campaign list page ─────────────────────────────────────────────────────
function CampaignList() {
  const navigate = useNavigate();
  const [campaigns, setCampaigns] = useState([]);
  const [icps, setIcps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [newIcp, setNewIcp] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [c, i] = await Promise.all([
        api.get('/api/outreach/campaigns'),
        api.get('/api/icps/list'),
      ]);
      setCampaigns(c.data.campaigns || []);
      setIcps(i.data.icps || []);
    } catch (e) {
      toast.error('Could not load campaigns');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!newName.trim()) return;
    try {
      const r = await api.post('/api/outreach/campaigns', {
        name: newName.trim(),
        icp_id: newIcp || null,
      });
      toast.success('Campaign created');
      setCreating(false);
      setNewName('');
      setNewIcp('');
      navigate(`/outreach/${r.data.id}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Could not create campaign');
    }
  };

  return (
    <div data-testid="outreach-list-page" className="max-w-6xl mx-auto px-6 py-8">
      <div className="flex items-start justify-between mb-8 gap-4 flex-wrap">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-violet-600 font-semibold mb-2">Outreach Campaigns</p>
          <h1 className="text-3xl font-semibold text-slate-900 mb-2">Multi-step outbound sequences</h1>
          <p className="text-slate-600 text-sm max-w-2xl">
            Build conditional WhatsApp + email journeys. Define what happens when a contact replies,
            mentions a keyword, or stays silent. Aria fires every step at the right time.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setCreating(true)}
          data-testid="outreach-new-campaign-btn"
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-900 text-white text-sm font-medium hover:bg-slate-800 transition-colors"
        >
          <Plus size={16} weight="bold" /> New campaign
        </button>
      </div>

      {creating && (
        <form onSubmit={handleCreate} data-testid="outreach-create-form" className="bg-white/80 backdrop-blur-md border border-slate-200 rounded-2xl p-5 mb-6 space-y-3">
          <input
            autoFocus
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Campaign name — e.g. Q1 Outbound to CFOs"
            data-testid="outreach-create-name"
            className="w-full px-3 py-2 rounded-lg border border-slate-300 focus:border-violet-500 focus:ring-2 focus:ring-violet-100 outline-none text-sm"
          />
          <select
            value={newIcp}
            onChange={(e) => setNewIcp(e.target.value)}
            data-testid="outreach-create-icp"
            className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white"
          >
            <option value="">No ICP (use lead-level ICP if assigned)</option>
            {icps.map((i) => (<option key={i.id} value={i.id}>{i.label}</option>))}
          </select>
          <div className="flex items-center justify-end gap-2">
            <button type="button" onClick={() => setCreating(false)} className="px-4 py-2 rounded-lg text-sm text-slate-600 hover:bg-slate-100">Cancel</button>
            <button type="submit" data-testid="outreach-create-submit" className="px-5 py-2 rounded-lg bg-slate-900 text-white text-sm font-medium">Create</button>
          </div>
        </form>
      )}

      {loading ? (
        <div className="text-center py-16 text-slate-400">Loading…</div>
      ) : campaigns.length === 0 ? (
        <div data-testid="outreach-empty-state" className="bg-white/70 backdrop-blur-md border border-slate-200 rounded-3xl p-12 text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-600 text-white mb-4">
            <Megaphone size={32} weight="duotone" />
          </div>
          <h3 className="text-xl font-semibold text-slate-900 mb-2">No outreach campaigns yet</h3>
          <p className="text-slate-600 text-sm max-w-md mx-auto mb-6">
            Create your first sequence. Add steps. Define branches. Aria runs the whole thing.
          </p>
          <button onClick={() => setCreating(true)} data-testid="outreach-empty-create-btn" className="inline-flex items-center gap-2 px-5 py-3 rounded-xl bg-slate-900 text-white text-sm font-medium">
            <Plus size={16} weight="bold" /> Create your first campaign
          </button>
        </div>
      ) : (
        <div data-testid="outreach-campaign-grid" className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {campaigns.map((c) => {
            const icp = icps.find((i) => i.id === c.icp_id);
            return (
              <button
                key={c.id}
                type="button"
                onClick={() => navigate(`/outreach/${c.id}`)}
                data-testid={`outreach-campaign-${c.id}`}
                className="text-left bg-white/80 backdrop-blur-sm border border-slate-200 rounded-2xl p-5 hover:shadow-lg hover:-translate-y-0.5 transition-all"
              >
                <div className="flex items-center justify-between mb-3">
                  <StatusPill status={c.status} />
                  <CaretRight size={14} className="text-slate-400" />
                </div>
                <h3 className="text-base font-semibold text-slate-900 mb-2 leading-tight">{c.name}</h3>
                {icp && <div className="text-xs text-violet-600 flex items-center gap-1"><Target size={10} /> {icp.label}</div>}
                <div className="text-[10px] text-slate-400 mt-3">Created {new Date(c.created_at).toLocaleDateString()}</div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function StatusPill({ status }) {
  const map = {
    draft: { tint: 'bg-slate-100 text-slate-600 border-slate-200', label: 'Draft' },
    active: { tint: 'bg-emerald-100 text-emerald-700 border-emerald-200', label: 'Active' },
    paused: { tint: 'bg-amber-100 text-amber-700 border-amber-200', label: 'Paused' },
    archived: { tint: 'bg-slate-200 text-slate-500 border-slate-300', label: 'Archived' },
  };
  const m = map[status] || map.draft;
  return <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-md border font-semibold ${m.tint}`}>{m.label}</span>;
}

// ─── Campaign detail / builder ──────────────────────────────────────────────
function CampaignDetail({ campaignId }) {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedStep, setSelectedStep] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [tab, setTab] = useState('builder'); // builder | analytics

  const load = useCallback(async () => {
    try {
      const r = await api.get(`/api/outreach/campaigns/${campaignId}/map`);
      setData(r.data);
      if (r.data.touchpoints.length && selectedStep === null) {
        setSelectedStep(r.data.touchpoints[0].step_number);
      }
    } catch (e) {
      toast.error('Could not load campaign');
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaignId]);

  const loadAnalytics = useCallback(async () => {
    try {
      const r = await api.get(`/api/outreach/campaigns/${campaignId}/analytics`);
      setAnalytics(r.data);
    } catch (e) { /* silent */ }
  }, [campaignId]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (tab === 'analytics') loadAnalytics(); }, [tab, loadAnalytics]);

  const handleAddStep = async () => {
    const nextStep = (data?.touchpoints?.length || 0) + 1;
    try {
      await api.post(`/api/outreach/campaigns/${campaignId}/touchpoints`, {
        ...EMPTY_TP,
        step_number: nextStep,
        message_template: `Step ${nextStep}: Hi {first_name}, …`,
      });
      toast.success(`Step ${nextStep} added`);
      setSelectedStep(nextStep);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Could not add step');
    }
  };

  const handleSaveStep = async (tp) => {
    try {
      await api.post(`/api/outreach/campaigns/${campaignId}/touchpoints`, {
        step_number: tp.step_number,
        channel: tp.channel,
        message_template: tp.message_template,
        delay_hours: tp.delay_hours,
        conditions: tp.conditions || {},
      });
      toast.success('Step saved');
      load();
    } catch (e) {
      const detail = e.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Could not save step');
    }
  };

  const handleDeleteStep = async (step) => {
    if (!window.confirm(`Delete step ${step}? This cannot be undone.`)) return;
    try {
      await api.delete(`/api/outreach/campaigns/${campaignId}/touchpoints/${step}`);
      toast.success(`Step ${step} deleted`);
      if (selectedStep === step) setSelectedStep(null);
      load();
    } catch (e) {
      toast.error('Could not delete step');
    }
  };

  const handleDragEnd = async (result) => {
    if (!result.destination || result.destination.index === result.source.index) return;
    const ordered = Array.from(data.touchpoints);
    const [moved] = ordered.splice(result.source.index, 1);
    ordered.splice(result.destination.index, 0, moved);
    // Reassign step numbers based on new order.
    // Save sequentially by deleting then re-adding under new step numbers.
    // To avoid step-conflicts, first delete then insert.
    try {
      // Optimistic UI
      const renumbered = ordered.map((t, idx) => ({ ...t, step_number: idx + 1 }));
      setData({ ...data, touchpoints: renumbered });

      // Two-phase: shift each touched row to step + 1000 (sentinel), then assign final.
      for (const oldStep of data.touchpoints.map((t) => t.step_number)) {
        await api.delete(`/api/outreach/campaigns/${campaignId}/touchpoints/${oldStep}`);
      }
      for (const t of renumbered) {
        await api.post(`/api/outreach/campaigns/${campaignId}/touchpoints`, {
          step_number: t.step_number,
          channel: t.channel,
          message_template: t.message_template,
          delay_hours: t.delay_hours,
          conditions: t.conditions || {},
        });
      }
      toast.success('Steps reordered');
      load();
    } catch (e) {
      toast.error('Reorder failed — reloading…');
      load();
    }
  };

  const handlePauseToggle = async () => {
    try {
      const action = data.campaign.status === 'paused' ? 'resume' : 'pause';
      await api.post(`/api/outreach/campaigns/${campaignId}/${action}`);
      toast.success(`Campaign ${action}d`);
      load();
    } catch (e) {
      toast.error('Could not toggle status');
    }
  };

  if (loading) return <div className="p-8 text-center text-slate-400">Loading campaign…</div>;
  if (!data) return null;

  const currentTp = data.touchpoints.find((t) => t.step_number === selectedStep) || null;
  const paused = data.campaign.status === 'paused';

  return (
    <div data-testid="outreach-detail-page" className="max-w-7xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between gap-4 flex-wrap">
        <div className="min-w-0">
          <button onClick={() => navigate('/outreach')} className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-900 mb-2">
            <ArrowLeft size={12} /> All campaigns
          </button>
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl font-semibold text-slate-900">{data.campaign.name}</h1>
            <StatusPill status={data.campaign.status} />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handlePauseToggle}
            data-testid="outreach-toggle-status-btn"
            className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium border ${
              paused ? 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100' : 'bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100'
            }`}
          >
            {paused ? <Play size={12} weight="bold" /> : <Pause size={12} weight="bold" />}
            {paused ? 'Resume' : 'Pause'}
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 mb-6 border-b border-slate-200">
        {[
          { key: 'builder', label: 'Builder', icon: <Sparkle size={12} /> },
          { key: 'analytics', label: 'Analytics', icon: <ChartLineUp size={12} /> },
        ].map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            data-testid={`outreach-tab-${t.key}`}
            className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t.key ? 'border-violet-600 text-violet-700' : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {tab === 'builder' ? (
        <div className="grid grid-cols-1 lg:grid-cols-[420px,1fr] gap-6">
          {/* Left — vertical timeline of steps */}
          <div data-testid="outreach-timeline">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs uppercase tracking-wider font-semibold text-slate-600">Timeline</h3>
              <button
                type="button"
                onClick={handleAddStep}
                data-testid="outreach-add-step-btn"
                className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs bg-slate-900 text-white hover:bg-slate-800"
              >
                <Plus size={12} weight="bold" /> Add step
              </button>
            </div>

            {data.touchpoints.length === 0 ? (
              <div className="bg-white/70 border border-dashed border-slate-300 rounded-2xl p-8 text-center text-sm text-slate-500">
                No steps yet. Click <strong>Add step</strong> to start your sequence.
              </div>
            ) : (
              <DragDropContext onDragEnd={handleDragEnd}>
                <Droppable droppableId="outreach-tp-list">
                  {(provided) => (
                    <div {...provided.droppableProps} ref={provided.innerRef} className="space-y-2 relative">
                      {/* dashed connector line */}
                      <div className="absolute left-[24px] top-2 bottom-2 w-px border-l-2 border-dashed border-violet-200 pointer-events-none" />
                      {data.touchpoints.map((tp, idx) => (
                        <Draggable key={tp.id} draggableId={String(tp.id)} index={idx}>
                          {(p, snap) => (
                            <div
                              ref={p.innerRef}
                              {...p.draggableProps}
                              data-testid={`outreach-tp-card-${tp.step_number}`}
                              onClick={() => setSelectedStep(tp.step_number)}
                              className={`relative pl-10 pr-3 py-3 rounded-xl border bg-white cursor-pointer transition-all ${
                                snap.isDragging ? 'shadow-xl' : 'shadow-sm'
                              } ${selectedStep === tp.step_number ? 'border-violet-400 ring-2 ring-violet-100' : 'border-slate-200 hover:border-violet-300'}`}
                            >
                              <div {...p.dragHandleProps} className="absolute left-1 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-700 cursor-grab active:cursor-grabbing">
                                <DotsSixVertical size={14} />
                              </div>
                              <div className="absolute left-[16px] top-1/2 -translate-y-1/2 w-4 h-4 rounded-full bg-white border-2 border-violet-400 flex items-center justify-center text-[9px] font-bold text-violet-700">
                                {tp.step_number}
                              </div>
                              <div className="flex items-start justify-between gap-2">
                                <div className="min-w-0 flex-1">
                                  <div className="flex items-center gap-2 mb-1">
                                    <ChannelChip channel={tp.channel} />
                                    <span className="text-[10px] text-slate-500 flex items-center gap-0.5">
                                      <Clock size={9} /> +{tp.delay_hours}h
                                    </span>
                                    {tp.conditions && Object.keys(tp.conditions).length > 0 && (
                                      <span className="text-[10px] text-violet-600 flex items-center gap-0.5 font-medium">
                                        <Lightning size={9} /> {Object.keys(tp.conditions).length}
                                      </span>
                                    )}
                                  </div>
                                  <div className="text-xs text-slate-600 line-clamp-2 leading-snug">
                                    {tp.message_template || <em className="text-slate-400">Empty message</em>}
                                  </div>
                                </div>
                                <button
                                  type="button"
                                  onClick={(e) => { e.stopPropagation(); handleDeleteStep(tp.step_number); }}
                                  className="text-slate-400 hover:text-rose-600 p-1"
                                  data-testid={`outreach-tp-delete-${tp.step_number}`}
                                >
                                  <Trash size={12} />
                                </button>
                              </div>
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
          </div>

          {/* Right — editor for the selected step */}
          <div data-testid="outreach-editor">
            {currentTp ? (
              <StepEditor
                key={currentTp.id}
                tp={currentTp}
                onSave={handleSaveStep}
                maxStep={Math.max(...data.touchpoints.map((t) => t.step_number), 1)}
              />
            ) : (
              <div className="bg-white/70 border border-dashed border-slate-300 rounded-2xl p-12 text-center">
                <PencilSimple size={32} className="text-slate-300 mx-auto mb-3" />
                <p className="text-sm text-slate-500">Select a step to edit it, or add a new one.</p>
              </div>
            )}
          </div>
        </div>
      ) : (
        <AnalyticsPanel analytics={analytics} touchpoints={data.touchpoints} />
      )}
    </div>
  );
}

function ChannelChip({ channel }) {
  const cfg = CHANNEL_ICONS[channel] || CHANNEL_ICONS.whatsapp;
  const Icon = cfg.icon;
  return (
    <span className={`inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded ${cfg.bg} ${cfg.color} border ${cfg.border}`}>
      <Icon size={9} weight="bold" /> {channel}
    </span>
  );
}

// ─── Step editor with conditions inspector ──────────────────────────────────
function StepEditor({ tp, onSave, maxStep }) {
  const [draft, setDraft] = useState(tp);
  const [dirty, setDirty] = useState(false);
  const [showJson, setShowJson] = useState(false);

  useEffect(() => { setDraft(tp); setDirty(false); }, [tp]);

  const update = (patch) => { setDraft({ ...draft, ...patch }); setDirty(true); };

  const insertToken = (token) => {
    const el = document.getElementById('tp-message-template');
    const pos = el?.selectionStart ?? draft.message_template.length;
    const next = draft.message_template.slice(0, pos) + token + draft.message_template.slice(pos);
    update({ message_template: next });
    setTimeout(() => { el?.focus(); el?.setSelectionRange(pos + token.length, pos + token.length); }, 0);
  };

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-3">
        <h2 className="text-base font-semibold text-slate-900">
          Step {draft.step_number} <span className="text-slate-400 font-normal">· editor</span>
        </h2>
        <button
          type="button"
          onClick={() => onSave(draft)}
          disabled={!dirty}
          data-testid="outreach-step-save-btn"
          className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium ${
            dirty ? 'bg-slate-900 text-white hover:bg-slate-800' : 'bg-slate-100 text-slate-400 cursor-not-allowed'
          }`}
        >
          <FloppyDisk size={12} weight="bold" /> {dirty ? 'Save changes' : 'Saved'}
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs font-semibold text-slate-700 mb-1.5 block">Channel</label>
          <select
            value={draft.channel}
            onChange={(e) => update({ channel: e.target.value })}
            data-testid="outreach-step-channel"
            className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white"
          >
            <option value="whatsapp">WhatsApp</option>
            <option value="email">Email</option>
            <option value="linkedin">LinkedIn</option>
            <option value="sms">SMS</option>
          </select>
        </div>
        <div>
          <label className="text-xs font-semibold text-slate-700 mb-1.5 block">Delay (hours after previous step)</label>
          <input
            type="number"
            min={0}
            max={8760}
            value={draft.delay_hours}
            onChange={(e) => update({ delay_hours: parseInt(e.target.value, 10) || 0 })}
            data-testid="outreach-step-delay"
            className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
          />
        </div>
      </div>

      <div>
        <label className="text-xs font-semibold text-slate-700 mb-1.5 flex items-center justify-between">
          <span>Message template</span>
          <div className="flex flex-wrap gap-1">
            {TOKEN_CHIPS.map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => insertToken(t)}
                data-testid={`outreach-token-${t.replace(/[{}]/g, '')}`}
                className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-violet-50 text-violet-700 border border-violet-200 hover:bg-violet-100"
              >
                {t}
              </button>
            ))}
          </div>
        </label>
        <textarea
          id="tp-message-template"
          rows={5}
          value={draft.message_template}
          onChange={(e) => update({ message_template: e.target.value })}
          data-testid="outreach-step-message"
          placeholder="Hi {first_name}, saw {company} is scaling — quick question?"
          className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:border-violet-500 focus:ring-2 focus:ring-violet-100 outline-none font-mono"
        />
      </div>

      <ConditionsInspector
        conditions={draft.conditions || {}}
        maxStep={maxStep}
        currentStep={draft.step_number}
        onChange={(next) => update({ conditions: next })}
      />

      <button
        type="button"
        onClick={() => setShowJson(!showJson)}
        className="text-[10px] text-slate-400 hover:text-slate-700 uppercase tracking-wider font-semibold"
      >
        {showJson ? 'Hide' : 'Show'} raw JSON
      </button>
      {showJson && (
        <pre data-testid="outreach-conditions-json" className="text-[11px] bg-slate-900 text-emerald-300 p-3 rounded-lg overflow-auto font-mono">
          {JSON.stringify(draft.conditions || {}, null, 2)}
        </pre>
      )}
    </div>
  );
}

// ─── Conditions Inspector — 4 branch editor ─────────────────────────────────
const BRANCH_DEFS = [
  { key: 'on_reply', label: 'When lead replies', tint: 'border-sky-300 bg-sky-50', icon: <ChatCircle size={14} className="text-sky-600" /> },
  { key: 'on_keyword_match', label: 'When reply contains keyword', tint: 'border-emerald-300 bg-emerald-50', icon: <Sparkle size={14} className="text-emerald-600" />, hasKeywords: true },
  { key: 'on_negative_keyword', label: 'When reply is negative', tint: 'border-rose-300 bg-rose-50', icon: <Warning size={14} className="text-rose-600" />, hasKeywords: true, restrictedActions: ['stop', 'tag_contact'] },
  { key: 'on_no_reply', label: 'If no reply within hours', tint: 'border-amber-300 bg-amber-50', icon: <Clock size={14} className="text-amber-600" />, hasAfterHours: true, restrictedActions: ['move_to_step', 'stop'] },
];

function ConditionsInspector({ conditions, maxStep, currentStep, onChange }) {
  const toggle = (key, defaults) => {
    if (conditions[key]) {
      const { [key]: _, ...rest } = conditions;
      onChange(rest);
    } else {
      onChange({ ...conditions, [key]: defaults });
    }
  };

  return (
    <div data-testid="outreach-conditions" className="space-y-2">
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
            data-testid={`outreach-branch-${b.key}`}
            className={`rounded-xl border-2 transition-all ${enabled ? b.tint : 'border-slate-200 bg-white'}`}
          >
            <button
              type="button"
              onClick={() => toggle(b.key, defaultsForBranch)}
              data-testid={`outreach-branch-toggle-${b.key}`}
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
                      data-testid={`outreach-branch-${b.key}-hours`}
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
                      data-testid={`outreach-branch-${b.key}-keywords`}
                      placeholder="interested, pricing, demo"
                      className="flex-1 px-2 py-1 rounded border border-slate-300 text-xs bg-white"
                    />
                  </Inline>
                )}

                <Inline label="Then">
                  <select
                    value={value.action || 'notify_user'}
                    onChange={(e) => onChange({ ...conditions, [b.key]: { ...value, action: e.target.value } })}
                    data-testid={`outreach-branch-${b.key}-action`}
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
                        data-testid={`outreach-branch-${b.key}-target`}
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
                        data-testid={`outreach-branch-${b.key}-tag`}
                        placeholder="hot_lead"
                        className="w-32 px-2 py-1 rounded border border-slate-300 text-xs bg-white font-mono"
                      />
                    </>
                  )}
                </Inline>
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

// ─── Analytics panel ────────────────────────────────────────────────────────
function AnalyticsPanel({ analytics, touchpoints }) {
  if (!analytics) return <div className="text-sm text-slate-400">Loading analytics…</div>;

  const enrolled = analytics.enrolled_total || 0;
  const breakdown = analytics.status_breakdown || {};

  return (
    <div data-testid="outreach-analytics-panel" className="space-y-5">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatTile label="Enrolled" value={enrolled} icon={<UsersFour size={18} />} />
        <StatTile label="Active" value={breakdown.active || 0} tint="emerald" />
        <StatTile label="Hot leads" value={breakdown.hot_lead || 0} tint="rose" />
        <StatTile label="Completed" value={breakdown.completed || 0} tint="slate" />
      </div>

      <div className="bg-white border border-slate-200 rounded-2xl p-5">
        <h3 className="text-sm font-semibold text-slate-900 mb-3">Per-step funnel</h3>
        {analytics.by_step?.length === 0 ? (
          <p className="text-xs text-slate-400">No steps yet.</p>
        ) : (
          <table className="w-full text-xs">
            <thead className="text-slate-500 uppercase tracking-wider">
              <tr><th className="text-left py-2">Step</th><th className="text-right py-2">Sent</th><th className="text-right py-2">Replied</th><th className="text-right py-2">Reply %</th><th className="text-right py-2">Stopped</th><th className="text-right py-2">→ next</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {analytics.by_step?.map((s) => (
                <tr key={s.step_number} data-testid={`outreach-analytics-step-${s.step_number}`}>
                  <td className="py-2 font-medium text-slate-900">#{s.step_number} <span className="text-slate-400 font-normal">· {s.channel}</span></td>
                  <td className="text-right text-slate-700">{s.sent}</td>
                  <td className="text-right text-slate-700">{s.replied}</td>
                  <td className="text-right text-emerald-600 font-medium">{s.reply_rate_pct}%</td>
                  <td className="text-right text-rose-600">{s.stopped}</td>
                  <td className="text-right text-slate-500">{s.conversion_to_next_pct == null ? '—' : `${s.conversion_to_next_pct}%`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function StatTile({ label, value, icon, tint = 'violet' }) {
  const tints = {
    violet: 'from-violet-50 to-indigo-50 border-violet-200 text-violet-700',
    emerald: 'from-emerald-50 to-teal-50 border-emerald-200 text-emerald-700',
    rose: 'from-rose-50 to-pink-50 border-rose-200 text-rose-700',
    slate: 'from-slate-50 to-zinc-50 border-slate-200 text-slate-700',
  };
  return (
    <div className={`bg-gradient-to-br ${tints[tint]} border rounded-2xl px-4 py-3`}>
      <div className="text-[10px] uppercase tracking-wider opacity-80 font-semibold">{label}</div>
      <div className="text-2xl font-semibold mt-1">{value}</div>
    </div>
  );
}
