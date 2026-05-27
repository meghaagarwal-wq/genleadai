/**
 * Iter101 — Visual Automation Rule Builder.
 *
 * Form-based "when X then Y" composer. Lists existing rules as cards,
 * supports create/edit/delete/toggle-enabled, plus a sample-context
 * dry-run that highlights which conditions failed.
 *
 * Mounted under /pt/automations and /app/automations.
 */
import { useEffect, useState, useCallback } from 'react';
import { Lightning, PencilSimple, TrashSimple, Play, Plus, ToggleLeft, ToggleRight } from '@phosphor-icons/react';
import { toast } from 'sonner';
import { ptApi, PageHeader } from '../shared';

const PRETTY_EVENT = {
  'lead.created':         'When a new lead is created',
  'lead.stage_changed':   'When a lead changes stage',
  'lead.icp_scored':      'When a lead gets an ICP score',
  'insight.classified':   'When ARIA classifies an insight',
  'email.opened':         'When an email is opened',
  'email.replied':        'When a lead replies to an email',
  'form.submitted':       'When a website form is submitted',
};

const PRETTY_OP = {
  eq: 'equals', ne: 'does not equal', gt: 'is greater than', gte: '≥',
  lt: 'is less than', lte: '≤', in: 'is one of', contains: 'contains',
};

const PRETTY_ACTION = {
  send_email:       'Send email',
  add_tag:          'Add tag',
  set_stage:        'Set lead stage',
  create_task:      'Create task',
  notify_slack:     'Notify Slack',
  attach_resource:  'Attach resource',
  log_only:         'Log only (no side-effect)',
};

const PtAutomations = () => {
  const [rules, setRules] = useState([]);
  const [catalog, setCatalog] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);  // rule object or { isNew: true }

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [r1, r2] = await Promise.all([
        ptApi.get('/api/automation-rules'),
        ptApi.get('/api/automation-rules/catalog'),
      ]);
      setRules(r1.data.rules || []);
      setCatalog(r2.data);
    } catch (e) {
      toast.error('Could not load rules');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const toggle = async (r) => {
    try {
      await ptApi.patch(`/api/automation-rules/${r.id}`, { enabled: !r.enabled });
      load();
    } catch (e) { toast.error('Could not toggle'); }
  };

  const remove = async (r) => {
    if (!window.confirm(`Delete "${r.name}"?`)) return;
    try {
      await ptApi.delete(`/api/automation-rules/${r.id}`);
      toast.success('Rule deleted');
      load();
    } catch (e) { toast.error('Delete failed'); }
  };

  const runNow = async (r) => {
    try {
      await ptApi.post(`/api/automation-rules/${r.id}/run-now`);
      toast.success(`"${r.name}" fired`);
      load();
    } catch (e) { toast.error(e.response?.data?.detail || 'Run failed'); }
  };

  return (
    <div data-testid="pt-automations-page">
      <PageHeader
        title="Automation Rules"
        subtitle='Build "when X then Y" rules without code. ARIA evaluates them on every relevant event.'
      />

      <div className="mb-4">
        <button
          onClick={() => setEditing({ isNew: true })}
          data-testid="pt-automations-new"
          className="text-sm font-semibold text-white bg-[#7C35DC] hover:bg-[#6928BC] px-3 py-2 rounded-md inline-flex items-center gap-1.5"
        >
          <Plus size={14} weight="bold" /> New rule
        </button>
      </div>

      {loading ? (
        <div className="text-sm text-[#64748B]">Loading…</div>
      ) : rules.length === 0 ? (
        <div className="text-sm text-[#64748B] bg-[#F8FAFC] border border-dashed border-[#E2E8F0] rounded-lg p-8 text-center" data-testid="pt-automations-empty">
          <Lightning size={32} weight="duotone" className="mx-auto text-[#7C35DC] mb-2" />
          No automation rules yet. Click <span className="font-semibold text-[#7C35DC]">+ New rule</span> to
          create your first one.
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3" data-testid="pt-automations-grid">
          {rules.map(r => (
            <RuleCard key={r.id} rule={r} onEdit={() => setEditing(r)} onToggle={() => toggle(r)} onDelete={() => remove(r)} onRun={() => runNow(r)} />
          ))}
        </div>
      )}

      {editing && catalog && (
        <RuleEditor
          rule={editing.isNew ? null : editing}
          catalog={catalog}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); load(); }}
        />
      )}
    </div>
  );
};

// ─── Rule card ─────────────────────────────────────────────────────────────
const RuleCard = ({ rule, onEdit, onToggle, onDelete, onRun }) => (
  <div className={`bg-white border rounded-lg p-4 ${rule.enabled ? 'border-[#E2E8F0]' : 'border-[#E2E8F0] bg-[#FAFAFA] opacity-75'}`} data-testid={`pt-rule-${rule.id}`}>
    <div className="flex items-start justify-between gap-2 mb-2">
      <div className="flex-1 min-w-0">
        <div className="text-sm font-bold text-[#0F172A] truncate" data-testid={`pt-rule-name-${rule.id}`}>{rule.name}</div>
        {rule.description && <div className="text-xs text-[#64748B] mt-0.5 line-clamp-2">{rule.description}</div>}
      </div>
      <div className="flex items-center gap-1.5">
        <button onClick={onToggle} title={rule.enabled ? 'Disable' : 'Enable'} data-testid={`pt-rule-toggle-${rule.id}`} className={rule.enabled ? 'text-[#16A34A]' : 'text-[#94A3B8]'}>
          {rule.enabled ? <ToggleRight size={20} weight="fill" /> : <ToggleLeft size={20} />}
        </button>
        <button onClick={onRun} title="Run now" data-testid={`pt-rule-run-${rule.id}`} className="text-[#7C35DC]"><Play size={14} weight="fill" /></button>
        <button onClick={onEdit} title="Edit" data-testid={`pt-rule-edit-${rule.id}`} className="text-[#475569]"><PencilSimple size={14} /></button>
        <button onClick={onDelete} title="Delete" data-testid={`pt-rule-delete-${rule.id}`} className="text-[#94A3B8] hover:text-red-600"><TrashSimple size={14} /></button>
      </div>
    </div>

    <div className="space-y-1 text-xs">
      <div className="flex items-start gap-2">
        <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#7C35DC] shrink-0 mt-0.5">When</span>
        <span className="text-[#0F172A]">{PRETTY_EVENT[rule.trigger?.event_type] || rule.trigger?.event_type}</span>
      </div>
      {(rule.trigger?.conditions || []).map((c, i) => (
        <div key={i} className="flex items-start gap-2 pl-12">
          <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#64748B] shrink-0 mt-0.5">And</span>
          <span className="text-[#475569]"><code className="bg-[#F1F5F9] px-1 rounded text-[10px]">{c.field}</code> {PRETTY_OP[c.op]} <code className="bg-[#F1F5F9] px-1 rounded text-[10px]">{JSON.stringify(c.value)}</code></span>
        </div>
      ))}
      <div className="flex items-start gap-2 mt-2">
        <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#C044E0] shrink-0 mt-0.5">Then</span>
        <div className="flex-1 flex flex-wrap gap-1">
          {(rule.actions || []).map((a, i) => (
            <span key={i} className="bg-violet-100 text-violet-800 rounded-full px-2 py-0.5 font-semibold text-[10px]">
              {PRETTY_ACTION[a.type] || a.type}
            </span>
          ))}
        </div>
      </div>
    </div>

    {rule.fire_count > 0 && (
      <div className="mt-2 pt-2 border-t border-[#F1F5F9] text-[10px] text-[#64748B]">
        Fired {rule.fire_count} time(s){rule.last_fired_at ? ` · last ${new Date(rule.last_fired_at).toLocaleString()}` : ''}
      </div>
    )}
  </div>
);

// ─── Editor modal ──────────────────────────────────────────────────────────
const RuleEditor = ({ rule, catalog, onClose, onSaved }) => {
  const [name, setName] = useState(rule?.name || '');
  const [description, setDescription] = useState(rule?.description || '');
  const [enabled, setEnabled] = useState(rule?.enabled ?? true);
  const [eventType, setEventType] = useState(rule?.trigger?.event_type || catalog.triggers[0]);
  const [conditions, setConditions] = useState(rule?.trigger?.conditions || []);
  const [actions, setActions] = useState(rule?.actions || [{ type: 'log_only', params: {} }]);
  const [saving, setSaving] = useState(false);
  const [dryRun, setDryRun] = useState(null);

  const addCond = () => setConditions([...conditions, { field: catalog.common_fields[0], op: 'eq', value: '' }]);
  const updCond = (i, k, v) => setConditions(conditions.map((c, idx) => idx === i ? { ...c, [k]: v } : c));
  const rmCond = (i) => setConditions(conditions.filter((_, idx) => idx !== i));

  const addAction = () => setActions([...actions, { type: 'add_tag', params: { tag: '' } }]);
  const updAction = (i, k, v) => setActions(actions.map((a, idx) => idx === i ? { ...a, [k]: v } : a));
  const rmAction = (i) => setActions(actions.filter((_, idx) => idx !== i));

  // Cast condition values to number when the op is numeric-ish
  const castValue = (op, v) => {
    if (['gt', 'gte', 'lt', 'lte'].includes(op) && v !== '' && !isNaN(Number(v))) return Number(v);
    if (op === 'in' && typeof v === 'string') return v.split(',').map(x => x.trim()).filter(Boolean);
    return v;
  };

  const save = async () => {
    if (!name.trim()) { toast.error('Name required'); return; }
    if (actions.length === 0) { toast.error('At least one action required'); return; }
    setSaving(true);
    try {
      const body = {
        name: name.trim(),
        description: description.trim(),
        enabled,
        trigger: {
          event_type: eventType,
          conditions: conditions.map(c => ({ ...c, value: castValue(c.op, c.value) })),
        },
        actions,
      };
      if (rule?.id) {
        await ptApi.patch(`/api/automation-rules/${rule.id}`, body);
      } else {
        await ptApi.post('/api/automation-rules', body);
      }
      toast.success(rule?.id ? 'Rule updated' : 'Rule created');
      onSaved();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Save failed');
    } finally { setSaving(false); }
  };

  const test = async () => {
    if (!rule?.id) { toast.error('Save first, then test'); return; }
    const raw = window.prompt('Paste a sample JSON context to test against (e.g. {"lead": {"icp_score": 85, "stage": "hot"}}):',
      '{\n  "lead": {\n    "icp_score": 85,\n    "stage": "hot"\n  }\n}');
    if (!raw) return;
    try {
      const ctx = JSON.parse(raw);
      const r = await ptApi.post(`/api/automation-rules/${rule.id}/dry-run`, { context: ctx });
      setDryRun(r.data);
    } catch (e) {
      toast.error('Invalid JSON or dry-run failed');
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" data-testid="pt-rule-editor">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-3xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-[#E2E8F0]">
          <div className="text-base font-bold text-[#0F172A]">{rule?.id ? 'Edit rule' : 'New rule'}</div>
          <button onClick={onClose} className="text-2xl leading-none text-[#94A3B8]" data-testid="pt-rule-editor-close">×</button>
        </div>

        <div className="flex-1 overflow-auto p-5 space-y-5">
          {/* Identity */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="md:col-span-2">
              <label className="block text-xs font-semibold text-[#475569] mb-1">Name</label>
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Notify on hot inbound lead"
                data-testid="pt-rule-name-input"
                className="w-full text-sm border border-[#E2E8F0] rounded-md px-2 py-1.5" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-[#475569] mb-1">Enabled</label>
              <button onClick={() => setEnabled(!enabled)} data-testid="pt-rule-enabled-toggle"
                className={`text-sm font-semibold px-3 py-1.5 rounded-md border ${enabled ? 'bg-[#7C35DC] text-white border-[#7C35DC]' : 'bg-white text-[#475569] border-[#E2E8F0]'}`}>
                {enabled ? 'On' : 'Off'}
              </button>
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold text-[#475569] mb-1">Description</label>
            <textarea rows={2} value={description} onChange={(e) => setDescription(e.target.value)}
              data-testid="pt-rule-description-input"
              className="w-full text-sm border border-[#E2E8F0] rounded-md px-2 py-1.5" />
          </div>

          {/* WHEN */}
          <div className="bg-violet-50 border border-violet-200 rounded-lg p-3">
            <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#7C35DC] mb-2">When</div>
            <select value={eventType} onChange={(e) => setEventType(e.target.value)} data-testid="pt-rule-event-type"
              className="w-full text-sm border border-[#E2E8F0] rounded-md px-2 py-1.5 mb-2">
              {catalog.triggers.map(t => <option key={t} value={t}>{PRETTY_EVENT[t] || t}</option>)}
            </select>

            {conditions.map((c, i) => (
              <div key={i} className="flex items-center gap-1.5 mb-1.5" data-testid={`pt-rule-cond-${i}`}>
                <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#64748B]">And</span>
                <select value={c.field} onChange={(e) => updCond(i, 'field', e.target.value)} className="flex-1 text-xs border border-[#E2E8F0] rounded-md px-2 py-1.5">
                  {catalog.common_fields.map(f => <option key={f} value={f}>{f}</option>)}
                </select>
                <select value={c.op} onChange={(e) => updCond(i, 'op', e.target.value)} className="text-xs border border-[#E2E8F0] rounded-md px-2 py-1.5">
                  {catalog.ops.map(o => <option key={o} value={o}>{PRETTY_OP[o]}</option>)}
                </select>
                <input value={c.value} onChange={(e) => updCond(i, 'value', e.target.value)} placeholder="value"
                  className="w-32 text-xs border border-[#E2E8F0] rounded-md px-2 py-1.5" />
                <button onClick={() => rmCond(i)} className="text-[#94A3B8] hover:text-red-600 text-lg leading-none">×</button>
              </div>
            ))}
            <button onClick={addCond} data-testid="pt-rule-add-cond" className="text-xs font-semibold text-[#7C35DC] hover:underline">+ Add condition</button>
          </div>

          {/* THEN */}
          <div className="bg-pink-50 border border-pink-200 rounded-lg p-3">
            <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#C044E0] mb-2">Then</div>
            {actions.map((a, i) => (
              <div key={i} className="flex items-center gap-1.5 mb-1.5" data-testid={`pt-rule-action-${i}`}>
                <select value={a.type} onChange={(e) => updAction(i, 'type', e.target.value)} className="text-xs border border-[#E2E8F0] rounded-md px-2 py-1.5">
                  {catalog.action_types.map(t => <option key={t} value={t}>{PRETTY_ACTION[t] || t}</option>)}
                </select>
                <input
                  value={a.params ? JSON.stringify(a.params) : '{}'}
                  onChange={(e) => {
                    try { updAction(i, 'params', JSON.parse(e.target.value || '{}')); }
                    catch { /* keep typing */ }
                  }}
                  placeholder='params, e.g. {"tag":"hot"}'
                  className="flex-1 text-xs font-mono border border-[#E2E8F0] rounded-md px-2 py-1.5"
                />
                <button onClick={() => rmAction(i)} className="text-[#94A3B8] hover:text-red-600 text-lg leading-none">×</button>
              </div>
            ))}
            <button onClick={addAction} data-testid="pt-rule-add-action" className="text-xs font-semibold text-[#C044E0] hover:underline">+ Add action</button>
          </div>

          {dryRun && (
            <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg p-3 text-xs" data-testid="pt-rule-dryrun-result">
              <div className={`font-bold mb-2 ${dryRun.would_fire ? 'text-[#16A34A]' : 'text-[#DC2626]'}`}>
                {dryRun.would_fire ? '✓ Rule would fire' : '✗ Rule would NOT fire'}
              </div>
              {dryRun.breakdown.map((b, i) => (
                <div key={i} className={b.passed ? 'text-[#16A34A]' : 'text-[#DC2626]'}>
                  {b.passed ? '✓' : '✗'} <code className="bg-white px-1 rounded">{b.field}</code> {PRETTY_OP[b.op]} <code className="bg-white px-1 rounded">{JSON.stringify(b.value)}</code>
                  {' '}<span className="text-[#64748B]">(actual: {JSON.stringify(b.actual)})</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between p-4 border-t border-[#E2E8F0]">
          {rule?.id ? (
            <button onClick={test} data-testid="pt-rule-test-btn" className="text-xs font-semibold text-[#7C35DC] border border-[#7C35DC]/30 px-3 py-1.5 rounded-md">Test against sample context…</button>
          ) : <div />}
          <div className="flex items-center gap-2">
            <button onClick={onClose} className="text-xs font-semibold text-[#475569] px-3 py-1.5">Cancel</button>
            <button onClick={save} disabled={saving} data-testid="pt-rule-save-btn" className="text-xs font-semibold text-white bg-[#7C35DC] hover:bg-[#6928BC] px-4 py-1.5 rounded-md disabled:opacity-50">
              {saving ? 'Saving…' : (rule?.id ? 'Update rule' : 'Create rule')}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PtAutomations;
