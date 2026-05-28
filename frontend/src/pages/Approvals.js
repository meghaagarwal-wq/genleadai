/**
 * Approvals — pending_outreach review queue.
 *
 * Lists every draft ARIA queued from inbound replies + the Morning Brief.
 * Founder actions per item: Approve & Send · Edit · Reject.
 * Bulk: Approve All · Reject All.
 *
 * Backend: /api/approvals (GET/POST under /approve|/edit-send|/reject|/bulk-*).
 */
import { useEffect, useState, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  ChatCircleText, EnvelopeSimple, LinkedinLogo, Lightning, PencilSimple,
  X, CheckCircle, Brain, Sparkle, Clock, Buildings, CaretDown, CaretRight, Warning,
} from '@phosphor-icons/react';
import { toast } from 'sonner';
import api from '../config/api';

const CHANNEL_ICONS = { whatsapp: ChatCircleText, email: EnvelopeSimple, linkedin: LinkedinLogo };
const CHANNEL_COLORS = {
  whatsapp: { bg: '#DCFCE7', text: '#166534' },
  email:    { bg: '#E0E7FF', text: '#3730A3' },
  linkedin: { bg: '#DBEAFE', text: '#1E40AF' },
};
const INTENT_COLORS = {
  positive: '#10B981', interested: '#10B981', neutral_followup: '#94A3B8',
  objection: '#F59E0B', not_interested: '#DC2626', unsubscribe: '#7F1D1D', unclear: '#94A3B8',
};

const relTime = (iso) => {
  if (!iso) return '—';
  const ms = Date.now() - new Date(iso).getTime();
  const m = Math.floor(ms / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
};

// Recognize Resend sandbox rejection so we can show a friendlier hint
const isSandboxRejection = (errorText) =>
  typeof errorText === 'string' &&
  /verify a domain at resend\.com\/domains|testing emails to your own/i.test(errorText);

const sandboxToastNote = () =>
  toast.info('Connect a verified Resend domain in Settings → Integrations to send to other recipients.', {
    duration: 8000, id: 'sandbox-resend-hint',
  });

const Approvals = () => {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [bulkBusy, setBulkBusy] = useState(false);
  const [expandedId, setExpandedId] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editDraft, setEditDraft] = useState({ subject: '', body: '' });
  const [rejectingId, setRejectingId] = useState(null);
  const [rejectReason, setRejectReason] = useState('');
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const fetchItems = useCallback(async () => {
    try {
      const r = await api.get('/api/approvals');
      setItems(r.data.items || []);
    } catch {
      toast.error('Could not load approval queue');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchItems(); }, [fetchItems]);

  // iter120 — Approval Queue digest email deep-link: /app/approvals?action=bulk-approve
  // We fire the bulk-approve once items are loaded, then clear the query param so a
  // reload doesn't double-trigger.
  useEffect(() => {
    const action = searchParams.get('action');
    if (action !== 'bulk-approve') return;
    if (loading || items.length === 0 || bulkBusy) return;
    setSearchParams({}, { replace: true });
    // Use a microtask so React commits the state update first
    setTimeout(() => { bulkApprove({ skipConfirm: true }); }, 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, items.length, searchParams]);

  // Approve
  const approve = async (id) => {
    setBusyId(id);
    try {
      const r = await api.post(`/api/approvals/${id}/approve`);
      const d = r.data.dispatch || {};
      if (d.sent) toast.success(`Sent via ${d.provider || 'channel'}`);
      else if (d.logged_only) toast.info(d.note || 'Queued for manual send');
      else {
        toast.error(d.error || 'Send failed');
        if (isSandboxRejection(d.error)) sandboxToastNote();
      }
      setItems((prev) => prev.filter((it) => it.id !== id));
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Approve failed');
    } finally {
      setBusyId(null);
    }
  };

  // Edit + Send
  const openEdit = (it) => {
    setEditingId(it.id);
    setEditDraft({ subject: it.subject || '', body: it.body || '' });
  };
  const saveEdit = async () => {
    if (!editingId) return;
    setBusyId(editingId);
    try {
      const payload = editDraft.subject !== undefined
        ? { subject: editDraft.subject, body: editDraft.body }
        : { body: editDraft.body };
      const r = await api.post(`/api/approvals/${editingId}/edit-send`, payload);
      const d = r.data.dispatch || {};
      if (d.sent) toast.success(`Sent via ${d.provider || 'channel'} after edit`);
      else if (d.logged_only) toast.info(d.note || 'Queued for manual send');
      else {
        toast.error(d.error || 'Send failed');
        if (isSandboxRejection(d.error)) sandboxToastNote();
      }
      setItems((prev) => prev.filter((it) => it.id !== editingId));
      setEditingId(null);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Edit-send failed');
    } finally {
      setBusyId(null);
    }
  };

  // Reject
  const openReject = (id) => { setRejectingId(id); setRejectReason(''); };
  const confirmReject = async () => {
    if (!rejectingId) return;
    setBusyId(rejectingId);
    try {
      await api.post(`/api/approvals/${rejectingId}/reject`, { reason: rejectReason || undefined });
      toast.success('Draft rejected');
      setItems((prev) => prev.filter((it) => it.id !== rejectingId));
      setRejectingId(null);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Reject failed');
    } finally {
      setBusyId(null);
    }
  };

  // Bulk
  const bulkApprove = async (opts = {}) => {
    if (items.length === 0) return;
    if (!opts.skipConfirm && !window.confirm(`Approve & send all ${items.length} drafts?`)) return;
    setBulkBusy(true);
    try {
      const r = await api.post('/api/approvals/bulk-approve', {});
      const { processed, succeeded, failed, results } = r.data;
      toast.success(`${succeeded}/${processed} sent${failed > 0 ? ` · ${failed} failed` : ''}`);
      // Sandbox hint if ANY row failed with a sandbox-style error
      if (failed > 0 && Array.isArray(results)) {
        const sandboxHit = results.some((row) => row && !row.sent && isSandboxRejection(row.error));
        if (sandboxHit) sandboxToastNote();
      }
      await fetchItems();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Bulk approve failed');
    } finally {
      setBulkBusy(false);
    }
  };
  const bulkReject = async () => {
    if (items.length === 0) return;
    if (!window.confirm(`Reject all ${items.length} drafts?`)) return;
    setBulkBusy(true);
    try {
      const r = await api.post('/api/approvals/bulk-reject', {});
      toast.success(`Rejected ${r.data.rejected}`);
      await fetchItems();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Bulk reject failed');
    } finally {
      setBulkBusy(false);
    }
  };

  // ─── Render ──
  if (loading) {
    return <div className="p-8 text-center text-sm text-[#64748B]" data-testid="approvals-loading">Loading queue…</div>;
  }

  return (
    <div className="p-6 max-w-5xl mx-auto" data-testid="approvals-page">
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Brain size={18} weight="duotone" className="text-[#7C35DC]" />
            <span className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#7C35DC]">Approval Queue</span>
          </div>
          <h1 className="text-3xl font-extrabold text-[#0F172A]" style={{ fontFamily: 'Space Grotesk, Inter' }}>
            ARIA drafts awaiting your review
          </h1>
          <p className="text-sm text-[#64748B] mt-1">
            Every draft below was generated from an inbound reply or your morning brief.
            Approve to send · Edit to tweak first · Reject to dismiss.
          </p>
        </div>
        {items.length > 0 && (
          <div className="flex items-center gap-2">
            <button
              onClick={bulkReject}
              disabled={bulkBusy}
              data-testid="approvals-bulk-reject"
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-xs font-semibold border border-[#E2E8F0] text-[#475569] hover:bg-[#F8FAFC] disabled:opacity-50"
            >
              <X size={12} /> Reject all
            </button>
            <button
              onClick={bulkApprove}
              disabled={bulkBusy}
              data-testid="approvals-bulk-approve"
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md text-xs font-bold text-white disabled:opacity-50"
              style={{ background: 'linear-gradient(135deg, #4C1D95 0%, #7C35DC 100%)' }}
            >
              <Sparkle size={12} weight="fill" /> Approve all ({items.length})
            </button>
          </div>
        )}
      </div>

      {/* Empty state */}
      {items.length === 0 ? (
        <div className="bg-white border border-[#E2E8F0] rounded-lg p-12 text-center" data-testid="approvals-empty">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-full mb-3"
               style={{ background: 'linear-gradient(135deg, #FAF7FF 0%, #EDE9FE 100%)' }}>
            <Brain size={28} weight="duotone" className="text-[#7C35DC]" />
          </div>
          <h3 className="text-base font-bold text-[#0F172A]" style={{ fontFamily: 'Space Grotesk, Inter' }}>
            No drafts waiting — ARIA is listening for replies.
          </h3>
          <p className="text-sm text-[#64748B] mt-1.5">
            When a prospect replies or your morning brief fires, drafted responses will appear here.
          </p>
          <button
            onClick={() => navigate('/app/leads')}
            className="mt-4 inline-flex items-center gap-1.5 text-xs font-semibold text-[#7C35DC] hover:text-[#4C1D95]"
            data-testid="approvals-go-to-leads"
          >
            Go to Lead Feed →
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((it) => {
            const ChannelIcon = CHANNEL_ICONS[it.channel] || EnvelopeSimple;
            const cc = CHANNEL_COLORS[it.channel] || CHANNEL_COLORS.email;
            const expanded = expandedId === it.id;
            const intent = it.qualification?.intent || 'unclear';
            const intentColor = INTENT_COLORS[intent] || '#94A3B8';
            const snap = it.lead_snapshot || {};
            return (
              <div key={it.id} data-testid={`approvals-item-${it.id}`}
                className="bg-white border border-[#E2E8F0] rounded-lg overflow-hidden">
                <div className="p-4">
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="flex items-start gap-3 flex-1 min-w-0">
                      <span className="inline-flex items-center justify-center w-9 h-9 rounded-md flex-shrink-0"
                            style={{ background: cc.bg, color: cc.text }}>
                        <ChannelIcon size={16} weight="duotone" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-sm font-bold text-[#0F172A]" style={{ fontFamily: 'Space Grotesk, Inter' }}>
                            {snap.name || 'Prospect'}
                          </span>
                          {snap.company && (
                            <span className="text-xs text-[#64748B] flex items-center gap-1">
                              <Buildings size={10} /> {snap.company}
                            </span>
                          )}
                          {snap.stage && (
                            <span className="text-[10px] font-bold uppercase tracking-[0.14em] px-1.5 py-0.5 rounded text-[#7C35DC] border border-[#7C35DC]/30">
                              {snap.stage}
                            </span>
                          )}
                          <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded capitalize"
                                style={{ background: cc.bg, color: cc.text }}>{it.channel}</span>
                        </div>
                        <div className="flex items-center gap-2 text-xs text-[#64748B] mt-1">
                          <span className="inline-flex items-center gap-1">
                            <Clock size={10} /> {relTime(it.created_at)}
                          </span>
                          {it.qualification?.summary && (
                            <>
                              <span>·</span>
                              <span className="inline-flex items-center gap-1">
                                <span className="w-1.5 h-1.5 rounded-full" style={{ background: intentColor }} />
                                <span className="capitalize">{intent.replace(/_/g, ' ')}</span>
                                <span className="text-[#94A3B8]">— {it.qualification.summary.slice(0, 80)}{it.qualification.summary.length > 80 ? '…' : ''}</span>
                              </span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={() => setExpandedId(expanded ? null : it.id)}
                      data-testid={`approvals-expand-${it.id}`}
                      className="text-[#94A3B8] hover:text-[#0F172A] flex-shrink-0 mt-0.5"
                    >
                      {expanded ? <CaretDown size={14} weight="bold" /> : <CaretRight size={14} weight="bold" />}
                    </button>
                  </div>

                  {/* Preview / Expanded body */}
                  {it.channel === 'email' && it.subject && (
                    <div className="text-xs font-semibold text-[#475569] mb-1">
                      <span className="text-[10px] uppercase tracking-[0.14em] text-[#94A3B8] mr-1.5">Subject</span>
                      {it.subject}
                    </div>
                  )}
                  <div
                    className={`text-sm text-[#0F172A] p-3 rounded-md border border-[#F1F5F9] ${expanded ? '' : 'overflow-hidden'}`}
                    style={{ background: '#FAFAFA', maxHeight: expanded ? 'none' : '64px' }}
                    data-testid={`approvals-body-${it.id}`}
                  >
                    <div className="whitespace-pre-wrap leading-relaxed">{it.body || '(empty)'}</div>
                  </div>

                  {/* Signal context */}
                  {expanded && it.qualification?.next_action_hint && (
                    <div className="mt-2 px-3 py-2 rounded-md text-xs border border-[#7C35DC]/20"
                         style={{ background: '#FAF7FF' }} data-testid={`approvals-hint-${it.id}`}>
                      <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#7C35DC] mr-1.5">Why this draft</span>
                      <span className="text-[#475569]">{it.qualification.next_action_hint}</span>
                    </div>
                  )}

                  {/* Inline editor */}
                  {editingId === it.id && (
                    <div className="mt-3 space-y-2 p-3 rounded-md border border-[#7C35DC]/30" style={{ background: '#FAF7FF' }} data-testid={`approvals-editor-${it.id}`}>
                      {it.channel === 'email' && (
                        <input
                          type="text"
                          value={editDraft.subject || ''}
                          onChange={(e) => setEditDraft((d) => ({ ...d, subject: e.target.value }))}
                          placeholder="Subject"
                          className="w-full text-sm border border-[#E2E8F0] rounded-md px-2.5 py-1.5 outline-none"
                          data-testid={`approvals-edit-subject-${it.id}`}
                        />
                      )}
                      <textarea
                        value={editDraft.body}
                        onChange={(e) => setEditDraft((d) => ({ ...d, body: e.target.value }))}
                        rows={6}
                        className="w-full text-sm border border-[#E2E8F0] rounded-md px-2.5 py-1.5 outline-none resize-y"
                        data-testid={`approvals-edit-body-${it.id}`}
                      />
                      <div className="flex items-center justify-end gap-2">
                        <button onClick={() => setEditingId(null)} data-testid={`approvals-edit-cancel-${it.id}`}
                          className="px-3 py-1.5 text-xs font-semibold text-[#475569] hover:bg-[#F8FAFC] rounded-md">Cancel</button>
                        <button onClick={saveEdit} disabled={busyId === editingId || !editDraft.body.trim()}
                          data-testid={`approvals-edit-send-${it.id}`}
                          className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-md text-xs font-bold text-white disabled:opacity-50"
                          style={{ background: 'linear-gradient(135deg, #4C1D95 0%, #7C35DC 100%)' }}>
                          <Lightning size={11} weight="fill" /> Save & send
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Inline reject reason */}
                  {rejectingId === it.id && (
                    <div className="mt-3 space-y-2 p-3 rounded-md border border-red-200 bg-red-50" data-testid={`approvals-reject-row-${it.id}`}>
                      <input
                        type="text"
                        value={rejectReason}
                        onChange={(e) => setRejectReason(e.target.value)}
                        placeholder="One-line reason (optional)"
                        className="w-full text-sm border border-red-200 rounded-md px-2.5 py-1.5 outline-none bg-white"
                        data-testid={`approvals-reject-reason-${it.id}`}
                      />
                      <div className="flex items-center justify-end gap-2">
                        <button onClick={() => setRejectingId(null)} className="px-3 py-1.5 text-xs font-semibold text-[#475569] hover:bg-white rounded-md"
                          data-testid={`approvals-reject-cancel-${it.id}`}>Cancel</button>
                        <button onClick={confirmReject} disabled={busyId === rejectingId}
                          data-testid={`approvals-reject-confirm-${it.id}`}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-bold text-white bg-[#DC2626] disabled:opacity-50">
                          <X size={11} weight="bold" /> Confirm reject
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Actions */}
                  {editingId !== it.id && rejectingId !== it.id && (
                    <div className="flex items-center justify-end gap-1.5 mt-3 pt-3 border-t border-[#F1F5F9]">
                      <button
                        onClick={() => openReject(it.id)}
                        disabled={busyId === it.id}
                        data-testid={`approvals-reject-${it.id}`}
                        className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-semibold text-[#475569] hover:bg-red-50 hover:text-[#DC2626] disabled:opacity-50"
                      >
                        <X size={11} weight="bold" /> Reject
                      </button>
                      <button
                        onClick={() => openEdit(it)}
                        disabled={busyId === it.id}
                        data-testid={`approvals-edit-${it.id}`}
                        className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-semibold text-[#7C35DC] border border-[#7C35DC]/30 hover:bg-[#FAF7FF] disabled:opacity-50"
                      >
                        <PencilSimple size={11} weight="bold" /> Edit
                      </button>
                      <button
                        onClick={() => approve(it.id)}
                        disabled={busyId === it.id}
                        data-testid={`approvals-approve-${it.id}`}
                        className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-md text-xs font-bold text-white disabled:opacity-50"
                        style={{ background: 'linear-gradient(135deg, #4C1D95 0%, #7C35DC 100%)' }}
                      >
                        <CheckCircle size={11} weight="fill" />
                        {busyId === it.id ? 'Sending…' : 'Approve & send'}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default Approvals;
