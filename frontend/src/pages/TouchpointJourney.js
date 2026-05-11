/**
 * TouchpointJourney — post-onboarding editor at /touchpoint-journey.
 *
 * Features beyond the onboarding step:
 *   • Document upload (PDF / DOCX / XLSX → Claude → preview → apply)
 *   • Version history (last 5 saves with restore)
 *   • Template library (8 universal templates)
 *   • Duplicate touchpoint
 *   • 32 max enforced visually (counter turns gold at 28, red at 32)
 */
import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../config/api';
import { toast } from 'sonner';
import {
  ChatCircle, EnvelopeSimple, Phone, LinkedinLogo, Sparkle, CheckCircle,
  PencilSimple, Trash, Plus, ArrowsClockwise, ArrowUp, ArrowDown, Copy,
  ClockCounterClockwise, BookOpen, UploadSimple, X, FileText, Warning,
  FileArrowUp, ArrowLeft,
} from '@phosphor-icons/react';

const MAX_TOUCHPOINTS = 32;

const CHANNEL_META = {
  whatsapp: { label: 'WhatsApp', color: '#25D366', icon: ChatCircle },
  email: { label: 'Email', color: '#0055FF', icon: EnvelopeSimple },
  call_reminder: { label: 'Call', color: '#F97316', icon: Phone },
  linkedin_nudge: { label: 'LinkedIn', color: '#7C35DC', icon: LinkedinLogo },
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

const fmt = (iso) => { try { return new Date(iso).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }); } catch { return '—'; } };

// ─── Timeline card (read-only summary) ──────────────────────────────────────
const TimelineCard = ({ tp, onEdit, onDelete }) => {
  const meta = CHANNEL_META[tp.channel] || CHANNEL_META.whatsapp;
  const Icon = meta.icon;
  const isHuman = tp.aria_role === 'alert_human';
  return (
    <div className="flex-shrink-0 w-64 bg-white border border-[#E8E0F5] rounded-xl p-4 group hover:border-[#7C35DC]/40 transition-all" style={{ boxShadow: 'var(--shadow-card)' }} data-testid={`tl-card-${tp.index}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#9B8AB0] font-mono">TP-{String(tp.index + 1).padStart(2, '0')}</span>
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button onClick={() => onEdit(tp.index)} className="p-1 text-[#5A4A7A] hover:text-[#7C35DC]" data-testid={`tl-edit-${tp.index}`}><PencilSimple size={12} /></button>
          <button onClick={() => onDelete(tp.index)} className="p-1 text-[#5A4A7A] hover:text-[#DC2626]" data-testid={`tl-del-${tp.index}`}><Trash size={12} /></button>
        </div>
      </div>
      <div className="text-xs text-[#9B8AB0] mb-1">Day {tp.day} · {String(tp.hour).padStart(2, '0')}:00</div>
      <div className="flex items-center gap-2 mb-2">
        <div className="w-7 h-7 rounded-md flex items-center justify-center" style={{ background: `${meta.color}15` }}>
          <Icon size={14} weight="fill" style={{ color: meta.color }} />
        </div>
        <span className="text-xs font-bold text-[#1A0A2E]">{TYPE_LABELS[tp.message_type] || tp.message_type}</span>
      </div>
      <span className={`inline-block px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider rounded ${isHuman ? 'bg-[#FEF3C7] text-[#D97706] border border-[#D97706]/30' : 'bg-[#DCEEFE] text-[#0055FF] border border-[#0055FF]/30'}`}>{isHuman ? 'Alert you' : 'Aria handles'}</span>
      <p className="mt-2 text-xs text-[#5A4A7A] line-clamp-2">{tp.message_template}</p>
    </div>
  );
};

// ─── Edit row ────────────────────────────────────────────────────────────────
const EditRow = ({ tp, onChange, onDelete, onDuplicate, onMoveUp, onMoveDown, isFirst, isLast }) => {
  const updateField = (field, value) => onChange({ ...tp, [field]: value });
  return (
    <div className="bg-white border border-[#E8E0F5] rounded-xl p-3 grid grid-cols-12 gap-2 items-start" data-testid={`edit-row-${tp.index}`}>
      <div className="col-span-1 flex flex-col items-center gap-1 pt-2">
        <span className="text-[10px] font-mono text-[#9B8AB0]">TP-{String(tp.index + 1).padStart(2, '0')}</span>
        <button disabled={isFirst} onClick={onMoveUp} data-testid={`edit-up-${tp.index}`} className="p-0.5 text-[#5A4A7A] hover:text-[#7C35DC] disabled:opacity-30"><ArrowUp size={12} /></button>
        <button disabled={isLast} onClick={onMoveDown} data-testid={`edit-down-${tp.index}`} className="p-0.5 text-[#5A4A7A] hover:text-[#7C35DC] disabled:opacity-30"><ArrowDown size={12} /></button>
      </div>
      <div className="col-span-1">
        <label className="text-[9px] font-bold uppercase tracking-wider text-[#9B8AB0]">Day</label>
        <input type="number" min="0" max="365" value={tp.day} onChange={(e) => updateField('day', Number(e.target.value))} data-testid={`edit-day-${tp.index}`} className="w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-2 py-1.5 rounded-md text-sm" />
      </div>
      <div className="col-span-1">
        <label className="text-[9px] font-bold uppercase tracking-wider text-[#9B8AB0]">Hour</label>
        <input type="number" min="0" max="23" value={tp.hour} onChange={(e) => updateField('hour', Number(e.target.value))} data-testid={`edit-hour-${tp.index}`} className="w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-2 py-1.5 rounded-md text-sm" />
      </div>
      <div className="col-span-2">
        <label className="text-[9px] font-bold uppercase tracking-wider text-[#9B8AB0]">Channel</label>
        <select value={tp.channel} onChange={(e) => updateField('channel', e.target.value)} data-testid={`edit-channel-${tp.index}`} className="w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-2 py-1.5 rounded-md text-sm">
          {Object.entries(CHANNEL_META).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
      </div>
      <div className="col-span-2">
        <label className="text-[9px] font-bold uppercase tracking-wider text-[#9B8AB0]">Type</label>
        <select value={tp.message_type} onChange={(e) => updateField('message_type', e.target.value)} data-testid={`edit-type-${tp.index}`} className="w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-2 py-1.5 rounded-md text-sm">
          {Object.entries(TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>
      <div className="col-span-2">
        <label className="text-[9px] font-bold uppercase tracking-wider text-[#9B8AB0]">Role</label>
        <select value={tp.aria_role} onChange={(e) => updateField('aria_role', e.target.value)} data-testid={`edit-role-${tp.index}`} className="w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-2 py-1.5 rounded-md text-sm">
          <option value="autonomous">Aria handles</option>
          <option value="alert_human">Alert me</option>
        </select>
      </div>
      <div className="col-span-2">
        <label className="text-[9px] font-bold uppercase tracking-wider text-[#9B8AB0]">Condition</label>
        <select value={tp.trigger || ''} onChange={(e) => updateField('trigger', e.target.value)} data-testid={`edit-trigger-${tp.index}`} className="w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-2 py-1.5 rounded-md text-sm">
          {CONDITIONS.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
      </div>
      <div className="col-span-1 flex flex-col gap-1 pt-4">
        <button onClick={onDuplicate} data-testid={`edit-dup-${tp.index}`} title="Duplicate" className="p-1 text-[#5A4A7A] hover:text-[#7C35DC]"><Copy size={14} /></button>
        <button onClick={onDelete} data-testid={`edit-del-${tp.index}`} title="Delete" className="p-1 text-[#5A4A7A] hover:text-[#DC2626]"><Trash size={14} /></button>
      </div>
      <div className="col-span-12">
        <textarea
          rows={2}
          value={tp.message_template}
          onChange={(e) => updateField('message_template', e.target.value)}
          data-testid={`edit-msg-${tp.index}`}
          placeholder="Message Aria should send, or describe the intent…"
          className="w-full bg-[#FAFAFA] border border-[#E8E0F5] text-[#1A0A2E] px-2.5 py-2 rounded-md text-sm resize-none"
        />
        <div className="flex items-center gap-1.5 mt-1 flex-wrap">
          {['{{first_name}}', '{{company}}', '{{product}}', '{{last_message}}', '{{score}}', '{{assigned_rep}}'].map((tok) => (
            <button key={tok} type="button" onClick={() => updateField('message_template', (tp.message_template || '') + ' ' + tok)} className="text-[10px] px-1.5 py-0.5 bg-[#F4F0FF] text-[#7C35DC] rounded font-mono hover:bg-[#E0D4F7]">{tok}</button>
          ))}
        </div>
      </div>
    </div>
  );
};

// ─── Template Library Modal ─────────────────────────────────────────────────
const TemplateLibraryModal = ({ onClose, onApply }) => {
  const [tpls, setTpls] = useState([]);
  const [previewing, setPreviewing] = useState(null);
  useEffect(() => { api.get('/api/touchpoints/templates').then((r) => setTpls(r.data?.templates || [])); }, []);

  return (
    <div className="fixed inset-0 bg-black/30 backdrop-blur-sm z-50 flex items-center justify-center p-4" data-testid="template-library-modal">
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

// ─── Version History Modal ──────────────────────────────────────────────────
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
    <div className="fixed inset-0 bg-black/30 backdrop-blur-sm z-50 flex items-center justify-center p-4" data-testid="version-history-modal">
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

// ─── Document Upload Modal ──────────────────────────────────────────────────
const DocumentUploadModal = ({ onClose, onApply }) => {
  const [stage, setStage] = useState('upload'); // upload | parsing | preview
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
      const r = await api.post('/api/touchpoints/import-document', form);
      setPreview(r.data?.preview || []);
      setMeta({ filename: r.data?.source_filename, count: r.data?.extracted_count, truncated: r.data?.truncated });
      setStage('preview');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Import failed');
      setStage('upload');
    } finally { setBusy(false); }
  };

  const updateRow = (idx, field, value) => setPreview(preview.map((p, i) => i === idx ? { ...p, [field]: value } : p));
  const deleteRow = (idx) => setPreview(preview.filter((_, i) => i !== idx).map((p, i) => ({ ...p, index: i })));

  const apply = () => { onApply(preview); onClose(); };

  return (
    <div className="fixed inset-0 bg-black/30 backdrop-blur-sm z-50 flex items-center justify-center p-4" data-testid="doc-upload-modal">
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
              <table className="w-full text-sm" data-testid="doc-preview-table">
                <thead>
                  <tr className="bg-[#F4F0FF] text-left">
                    {['#', 'Day', 'Hr', 'Channel', 'Type', 'Role', 'Message', ''].map((h) => (
                      <th key={h} className="px-2 py-1.5 text-[10px] font-bold uppercase tracking-[0.15em] text-[#5A4A7A]">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.map((tp, i) => (
                    <tr key={i} className="border-b border-[#F0ECF9]" data-testid={`doc-row-${i}`}>
                      <td className="px-2 py-1.5 font-mono text-xs text-[#9B8AB0]">{i + 1}</td>
                      <td className="px-2 py-1.5"><input type="number" value={tp.day} onChange={(e) => updateRow(i, 'day', Number(e.target.value))} className="w-12 bg-white border border-[#E8E0F5] px-1.5 py-1 rounded text-xs" /></td>
                      <td className="px-2 py-1.5"><input type="number" value={tp.hour} onChange={(e) => updateRow(i, 'hour', Number(e.target.value))} className="w-12 bg-white border border-[#E8E0F5] px-1.5 py-1 rounded text-xs" /></td>
                      <td className="px-2 py-1.5">
                        <select value={tp.channel} onChange={(e) => updateRow(i, 'channel', e.target.value)} className="bg-white border border-[#E8E0F5] px-1.5 py-1 rounded text-xs">
                          {Object.entries(CHANNEL_META).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
                        </select>
                      </td>
                      <td className="px-2 py-1.5">
                        <select value={tp.message_type} onChange={(e) => updateRow(i, 'message_type', e.target.value)} className="bg-white border border-[#E8E0F5] px-1.5 py-1 rounded text-xs">
                          {Object.entries(TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                        </select>
                      </td>
                      <td className="px-2 py-1.5">
                        <select value={tp.aria_role} onChange={(e) => updateRow(i, 'aria_role', e.target.value)} className="bg-white border border-[#E8E0F5] px-1.5 py-1 rounded text-xs">
                          <option value="autonomous">Aria</option>
                          <option value="alert_human">Alert</option>
                        </select>
                      </td>
                      <td className="px-2 py-1.5"><input value={tp.message_template} onChange={(e) => updateRow(i, 'message_template', e.target.value)} className="w-full bg-white border border-[#E8E0F5] px-1.5 py-1 rounded text-xs" /></td>
                      <td className="px-2 py-1.5"><button onClick={() => deleteRow(i)} className="text-[#DC2626] hover:bg-[#FEE2E2] p-1 rounded"><Trash size={12} /></button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
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

// ─── Top-level Page ──────────────────────────────────────────────────────────
const TouchpointJourney = () => {
  const [map, setMap] = useState(null);
  const [draft, setDraft] = useState([]);
  const [mode, setMode] = useState('timeline'); // timeline | edit
  const [saving, setSaving] = useState(false);
  const [showLibrary, setShowLibrary] = useState(false);
  const [showVersions, setShowVersions] = useState(false);
  const [showUpload, setShowUpload] = useState(false);

  const load = () => {
    api.get('/api/touchpoints/map').then((r) => {
      const m = r.data?.map;
      setMap(m);
      setDraft((m?.touchpoints || []).map((tp, i) => ({ ...tp, index: i })));
    });
  };
  useEffect(() => { load(); }, []);

  const counterTone = useMemo(() => {
    const n = draft.length;
    if (n >= MAX_TOUCHPOINTS) return 'text-[#DC2626]';
    if (n >= 28) return 'text-[#D97706]';
    return 'text-[#1A0A2E]';
  }, [draft.length]);

  const reindex = (arr) => arr.map((tp, i) => ({ ...tp, index: i }));
  const addRow = () => {
    if (draft.length >= MAX_TOUCHPOINTS) { toast.error(`Max ${MAX_TOUCHPOINTS} touchpoints`); return; }
    const last = draft[draft.length - 1];
    setDraft(reindex([...draft, {
      index: draft.length,
      day: (last ? Number(last.day) + 2 : 0),
      hour: 9,
      channel: 'whatsapp',
      message_type: 'follow_up',
      aria_role: 'autonomous',
      trigger: '',
      message_template: '',
    }]));
  };
  const updateRow = (idx, next) => setDraft(reindex(draft.map((tp, i) => i === idx ? next : tp)));
  const deleteRow = (idx) => setDraft(reindex(draft.filter((_, i) => i !== idx)));
  const duplicateRow = (idx) => {
    if (draft.length >= MAX_TOUCHPOINTS) { toast.error(`Max ${MAX_TOUCHPOINTS} touchpoints`); return; }
    const copy = { ...draft[idx], day: Number(draft[idx].day) + 1 };
    const next = [...draft.slice(0, idx + 1), copy, ...draft.slice(idx + 1)];
    setDraft(reindex(next));
  };
  const moveRow = (idx, dir) => {
    const j = idx + dir;
    if (j < 0 || j >= draft.length) return;
    const next = [...draft]; [next[idx], next[j]] = [next[j], next[idx]];
    setDraft(reindex(next));
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
        })),
      };
      await api.post('/api/touchpoints/map', payload);
      toast.success('Touchpoint map saved');
      load();
      setMode('timeline');
    } catch (e) { toast.error(e.response?.data?.detail || 'Save failed'); }
    finally { setSaving(false); }
  };

  const applyTemplate = (tpl) => {
    setDraft(reindex(tpl.touchpoints || []));
    setMode('edit');
    setMap({ ...(map || {}), template_id: tpl.id, template_name: tpl.name });
    toast.success(`Loaded "${tpl.name}" — review and save to apply`);
  };

  const applyImport = (rows) => {
    setDraft(reindex(rows));
    setMode('edit');
    toast.success('Document imported — review and save to apply');
  };

  return (
    <div className="space-y-6" data-testid="touchpoint-journey-page">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-3xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Touchpoint Journey</h1>
          <p className="text-sm text-[#5A4A7A] mt-1">{map?.template_name || 'No template'} · saved {fmt(map?.updated_at)} by {map?.saved_by || '—'}</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button onClick={() => setShowLibrary(true)} data-testid="open-library-btn" className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-[#7C35DC]/30 text-[#7C35DC] rounded-lg text-xs font-bold hover:bg-[#F4F0FF]">
            <BookOpen size={12} weight="fill" /> Template library
          </button>
          <button onClick={() => setShowUpload(true)} data-testid="open-upload-btn" className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-[#E2B96F]/40 text-[#9A6F1A] rounded-lg text-xs font-bold hover:bg-[#FEF3C7]">
            <UploadSimple size={12} weight="bold" /> Import from document
          </button>
          <button onClick={() => setShowVersions(true)} data-testid="open-versions-btn" className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-lg text-xs font-bold hover:bg-[#F9F5FF]">
            <ClockCounterClockwise size={12} weight="fill" /> Version history
          </button>
          {mode === 'timeline' ? (
            <button onClick={() => setMode('edit')} data-testid="enter-edit-mode" className="inline-flex items-center gap-1.5 px-4 py-1.5 btn-gradient rounded-lg text-xs font-bold" style={{ fontFamily: 'Plus Jakarta Sans' }}><PencilSimple size={12} weight="bold" /> Customise</button>
          ) : (
            <>
              <button onClick={() => setMode('timeline')} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-lg text-xs font-bold">Discard</button>
              <button onClick={save} disabled={saving || draft.length === 0} data-testid="save-map-btn" className="inline-flex items-center gap-1.5 px-4 py-1.5 btn-gradient rounded-lg text-xs font-bold disabled:opacity-40" style={{ fontFamily: 'Plus Jakarta Sans' }}>{saving ? 'Saving…' : 'Save my journey'}</button>
            </>
          )}
        </div>
      </div>

      <div className="bg-[#F4F0FF] border border-[#E0D4F7] rounded-xl px-5 py-3 flex items-center justify-between flex-wrap gap-3" data-testid="tp-counter-bar">
        <div className="flex items-center gap-2 text-sm text-[#5A4A7A]">
          <Sparkle size={16} weight="fill" className="text-[#7C35DC]" />
          <span><strong className={counterTone}>{draft.length}</strong> / {MAX_TOUCHPOINTS} touchpoints used</span>
        </div>
        {draft.length >= 28 && draft.length < MAX_TOUCHPOINTS && (
          <span className="text-xs font-bold text-[#D97706] inline-flex items-center gap-1"><Warning size={12} weight="fill" /> Nearing the {MAX_TOUCHPOINTS}-touchpoint limit</span>
        )}
        {draft.length >= MAX_TOUCHPOINTS && (
          <span className="text-xs font-bold text-[#DC2626] inline-flex items-center gap-1"><Warning size={12} weight="fill" /> Maximum {MAX_TOUCHPOINTS} touchpoints reached</span>
        )}
      </div>

      {mode === 'timeline' && (
        <div data-testid="timeline-view">
          {draft.length === 0 ? (
            <div className="bg-white border border-[#E8E0F5] rounded-xl p-10 text-center text-sm text-[#9B8AB0]">No touchpoints yet. Pick a template, import from a document, or customise from scratch.</div>
          ) : (
            <div className="bg-white border border-[#E8E0F5] rounded-xl p-5 overflow-x-auto" style={{ boxShadow: 'var(--shadow-card)' }}>
              <div className="flex items-center gap-3" style={{ minWidth: 'max-content' }}>
                {draft.map((tp, i) => (
                  <React.Fragment key={tp.index}>
                    <TimelineCard tp={tp} onEdit={() => setMode('edit')} onDelete={() => deleteRow(i)} />
                    {i < draft.length - 1 && <div className="flex-shrink-0 w-6 h-px border-t-2 border-dashed border-[#E0D4F7]"></div>}
                  </React.Fragment>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {mode === 'edit' && (
        <div className="space-y-3" data-testid="edit-view">
          {draft.map((tp, i) => (
            <EditRow
              key={tp.index}
              tp={tp}
              onChange={(next) => updateRow(i, next)}
              onDelete={() => deleteRow(i)}
              onDuplicate={() => duplicateRow(i)}
              onMoveUp={() => moveRow(i, -1)}
              onMoveDown={() => moveRow(i, 1)}
              isFirst={i === 0}
              isLast={i === draft.length - 1}
            />
          ))}
          <button onClick={addRow} disabled={draft.length >= MAX_TOUCHPOINTS} data-testid="add-row-btn" className="w-full border-2 border-dashed border-[#E0D4F7] hover:border-[#7C35DC]/50 rounded-xl p-4 text-sm font-bold text-[#7C35DC] hover:bg-[#FAF7FF] disabled:opacity-40 disabled:cursor-not-allowed inline-flex items-center justify-center gap-2">
            <Plus size={14} weight="bold" /> Add touchpoint
          </button>
        </div>
      )}

      {showLibrary && <TemplateLibraryModal onClose={() => setShowLibrary(false)} onApply={applyTemplate} />}
      {showVersions && <VersionHistoryModal onClose={() => setShowVersions(false)} onRestored={load} />}
      {showUpload && <DocumentUploadModal onClose={() => setShowUpload(false)} onApply={applyImport} />}
    </div>
  );
};

export default TouchpointJourney;
