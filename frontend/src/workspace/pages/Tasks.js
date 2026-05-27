import { useEffect, useState } from 'react';
import { Plus, Check, X, Trash } from '@phosphor-icons/react';
import { toast } from 'sonner';
import { ptApi, PageHeader, EmptyState, Pill, fmtDate } from '../shared';

const STATUS_META = {
  open:        { label: 'Open',        color: '#475569' },
  in_progress: { label: 'In progress', color: '#F59E0B' },
  done:        { label: 'Done',        color: '#7C35DC' },
  blocked:     { label: 'Blocked',     color: '#DC2626' },
};

const PRIORITY_META = {
  low:    { label: 'Low',    color: '#94A3B8' },
  normal: { label: 'Normal', color: '#475569' },
  high:   { label: 'High',   color: '#F59E0B' },
  urgent: { label: 'Urgent', color: '#DC2626' },
};

const PtTasks = () => {
  const [data, setData] = useState({ tasks: [], counts: {} });
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({ status: '', owner: '' });
  const [showAdd, setShowAdd] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const params = {};
      if (filter.status) params.status = filter.status;
      if (filter.owner) params.owner = filter.owner;
      const r = await ptApi.get('/api/pt/tasks', { params });
      setData(r.data);
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [filter.status, filter.owner]);

  const updateStatus = async (id, status) => {
    try { await ptApi.patch(`/api/pt/tasks/${id}`, { status }); load(); }
    catch { toast.error('Could not update'); }
  };

  const remove = async (id) => {
    if (!window.confirm('Delete this task?')) return;
    try { await ptApi.delete(`/api/pt/tasks/${id}`); toast.success('Deleted'); load(); }
    catch { toast.error('Could not delete'); }
  };

  return (
    <div data-testid="pt-tasks-page">
      <PageHeader title="Tasks" subtitle={`${data.counts?.open || 0} open · ${data.counts?.in_progress || 0} in progress · ${data.counts?.done || 0} done`}
        right={
          <button onClick={() => setShowAdd(true)} data-testid="pt-task-add-btn"
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-semibold text-white" style={{ background: '#7C35DC' }}>
            <Plus size={14} /> New task
          </button>
        }
      />

      {/* Filters */}
      <div className="flex items-center gap-2 mb-4 flex-wrap" data-testid="pt-task-filters">
        <select value={filter.status} onChange={(e) => setFilter({ ...filter, status: e.target.value })} className="text-sm border border-[#E2E8F0] rounded-md px-2 py-1.5">
          <option value="">All status</option>
          {Object.entries(STATUS_META).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
        <select value={filter.owner} onChange={(e) => setFilter({ ...filter, owner: e.target.value })} className="text-sm border border-[#E2E8F0] rounded-md px-2 py-1.5">
          <option value="">All owners</option>
          <option>Content Vista</option><option>John</option><option>Pratheepa</option><option>Megha</option><option>Harshit</option>
        </select>
      </div>

      {loading ? (
        <div className="text-sm text-[#64748B]">Loading…</div>
      ) : data.tasks.length === 0 ? (
        <EmptyState title="No tasks pending." message="Tasks auto-create when a lead crosses Hot or replies positively. You can also create manual tasks." />
      ) : (
        <div className="bg-white border border-[#E2E8F0] rounded-lg overflow-hidden">
          {data.tasks.map(t => {
            const sm = STATUS_META[t.status] || STATUS_META.open;
            const pm = PRIORITY_META[t.priority] || PRIORITY_META.normal;
            return (
              <div key={t.id} className="flex items-center gap-3 px-4 py-3 border-b border-[#F1F5F9] last:border-0 hover:bg-[#F8FAFC]" data-testid={`pt-task-${t.id}`}>
                <button onClick={() => updateStatus(t.id, t.status === 'done' ? 'open' : 'done')}
                  data-testid={`pt-task-toggle-${t.id}`}
                  className={`w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 ${t.status === 'done' ? 'bg-[#7C35DC] border-[#7C35DC]' : 'border-[#CBD5E1]'}`}>
                  {t.status === 'done' && <Check size={12} weight="bold" className="text-white" />}
                </button>
                <div className="flex-1 min-w-0">
                  <div className={`text-sm font-medium ${t.status === 'done' ? 'line-through text-[#94A3B8]' : 'text-[#0F172A]'}`}>{t.title}</div>
                  <div className="flex items-center gap-2 flex-wrap mt-1">
                    <Pill label={pm.label} color={pm.color} />
                    <Pill label={sm.label} color={sm.color} />
                    <span className="text-[10px] text-[#64748B]">Owner: {t.owner}</span>
                    {t.due_date && <span className="text-[10px] text-[#64748B]">Due: {fmtDate(t.due_date)}</span>}
                    {t.source_trigger && <span className="text-[10px] text-[#94A3B8]">Trigger: {t.source_trigger}</span>}
                  </div>
                </div>
                <select value={t.status} onChange={(e) => updateStatus(t.id, e.target.value)}
                  data-testid={`pt-task-status-${t.id}`}
                  onClick={(e) => e.stopPropagation()}
                  className="text-xs border border-[#E2E8F0] rounded-md px-2 py-1">
                  {Object.entries(STATUS_META).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
                </select>
                <button onClick={() => remove(t.id)} data-testid={`pt-task-delete-${t.id}`}
                  className="p-1 text-[#94A3B8] hover:text-[#DC2626]"><Trash size={13} weight="fill" /></button>
              </div>
            );
          })}
        </div>
      )}

      {showAdd && <AddTaskModal onClose={() => setShowAdd(false)} onSaved={() => { setShowAdd(false); load(); }} />}
    </div>
  );
};

const AddTaskModal = ({ onClose, onSaved }) => {
  const [f, setF] = useState({ title: '', owner: 'Content Vista', priority: 'normal', due_date: '' });
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    if (!f.title.trim()) { toast.error('Title required'); return; }
    setBusy(true);
    try {
      const payload = { ...f };
      if (!payload.due_date) delete payload.due_date;
      await ptApi.post('/api/pt/tasks', payload);
      toast.success('Task created');
      onSaved();
    } catch (err) { toast.error(err.response?.data?.detail || 'Could not create'); }
    finally { setBusy(false); }
  };
  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={onClose} data-testid="pt-task-modal">
      <div className="bg-white rounded-xl border border-[#E2E8F0] w-full max-w-md" onClick={(e) => e.stopPropagation()}>
        <div className="px-5 py-4 border-b border-[#E2E8F0] flex items-center justify-between">
          <h3 className="text-base font-bold text-[#0F172A]" style={{ fontFamily: 'Space Grotesk, Inter' }}>New task</h3>
          <button onClick={onClose}><X size={16} /></button>
        </div>
        <div className="p-5 space-y-3">
          <div>
            <label className="block text-[10px] font-bold uppercase tracking-[0.16em] text-[#64748B] mb-1">Title</label>
            <input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} data-testid="pt-task-title-input"
              className="w-full text-sm border border-[#E2E8F0] rounded-md px-2 py-1.5 outline-none" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-[0.16em] text-[#64748B] mb-1">Owner</label>
              <select value={f.owner} onChange={(e) => setF({ ...f, owner: e.target.value })} className="w-full text-sm border border-[#E2E8F0] rounded-md px-2 py-1.5">
                <option>Content Vista</option><option>John</option><option>Pratheepa</option><option>Megha</option><option>Harshit</option>
              </select>
            </div>
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-[0.16em] text-[#64748B] mb-1">Priority</label>
              <select value={f.priority} onChange={(e) => setF({ ...f, priority: e.target.value })} className="w-full text-sm border border-[#E2E8F0] rounded-md px-2 py-1.5">
                {Object.entries(PRIORITY_META).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-[10px] font-bold uppercase tracking-[0.16em] text-[#64748B] mb-1">Due date</label>
            <input type="date" value={f.due_date} onChange={(e) => setF({ ...f, due_date: e.target.value })}
              className="w-full text-sm border border-[#E2E8F0] rounded-md px-2 py-1.5 outline-none" />
          </div>
        </div>
        <div className="px-5 py-3 border-t border-[#E2E8F0] flex justify-end gap-2 bg-[#F8FAFC]">
          <button onClick={onClose} className="px-3 py-1.5 text-sm font-semibold text-[#475569]">Cancel</button>
          <button onClick={submit} disabled={busy} data-testid="pt-task-save-btn"
            className="px-4 py-1.5 text-sm font-semibold text-white rounded-md disabled:opacity-50" style={{ background: '#7C35DC' }}>
            {busy ? 'Saving…' : 'Save task'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default PtTasks;
