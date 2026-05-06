import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { X, Plug, ArrowRight, Sparkle } from '@phosphor-icons/react';
import { Link } from 'react-router-dom';
import api from '../config/api';

/**
 * PushToSequenceModal — push selected ARIA leads into a SalesHandy sequence
 * or Lemlist campaign. Loads sequences/campaigns from each connected platform
 * and lets the founder pick where to send.
 */
const PushToSequenceModal = ({ leadIds, onClose, onSuccess }) => {
  const [status, setStatus] = useState({ saleshandy: { connected: false }, lemlist: { connected: false } });
  const [platform, setPlatform] = useState('lemlist');
  const [sequences, setSequences] = useState([]);
  const [seqId, setSeqId] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);

  useEffect(() => {
    api.get('/api/integrations/status').then(r => {
      setStatus(r.data);
      // Auto-pick the first connected platform
      if (r.data.lemlist?.connected) setPlatform('lemlist');
      else if (r.data.saleshandy?.connected) setPlatform('saleshandy');
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!status[platform]?.connected) { setSequences([]); return; }
    setSequences([]); setSeqId('');
    api.get(`/api/integrations/sequences/${platform}`).then(r => {
      setSequences(r.data.sequences || []);
      if (r.data.sequences?.[0]) setSeqId(r.data.sequences[0].id);
    }).catch(err => {
      toast.error(err.response?.data?.detail || 'Could not load sequences');
    });
  }, [platform, status]);

  const submit = async () => {
    if (!seqId) { toast.error('Pick a sequence first'); return; }
    setSubmitting(true);
    try {
      const r = await api.post('/api/integrations/push', {
        lead_ids: leadIds,
        sequence_id: seqId,
        platform,
      });
      setResult(r.data);
      if (r.data.pushed > 0) toast.success(`${r.data.pushed} lead${r.data.pushed === 1 ? '' : 's'} pushed to ${platform === 'saleshandy' ? 'SalesHandy' : 'Lemlist'}`);
      if (r.data.failed === 0 && r.data.pushed > 0 && onSuccess) {
        setTimeout(() => onSuccess(), 1200);
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Push failed');
    } finally {
      setSubmitting(false);
    }
  };

  const platformInfo = {
    saleshandy: { name: 'SalesHandy', term: 'sequence', color: '#16A34A' },
    lemlist: { name: 'Lemlist', term: 'campaign', color: '#7C35DC' },
  };
  const info = platformInfo[platform];

  const noConnection = !status.saleshandy?.connected && !status.lemlist?.connected;

  return (
    <div className="fixed inset-0 bg-black/30 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={onClose} data-testid="push-modal">
      <div className="bg-white border border-[#E8E0F5] rounded-2xl w-full max-w-lg" onClick={e => e.stopPropagation()} style={{ boxShadow: 'var(--shadow-deep)' }}>
        <div className="flex items-center justify-between p-6 border-b border-[#E8E0F5]">
          <div>
            <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC]" style={{ fontFamily: 'Plus Jakarta Sans' }}>SEND TO SEQUENCE</div>
            <h2 className="text-xl font-extrabold text-[#1A0A2E] mt-0.5" style={{ fontFamily: 'Plus Jakarta Sans' }}>
              Push {leadIds.length} lead{leadIds.length === 1 ? '' : 's'}
            </h2>
          </div>
          <button onClick={onClose} className="text-[#9B8AB0] hover:text-[#7C35DC]" data-testid="push-close-btn"><X size={22} /></button>
        </div>

        <div className="p-6 space-y-4">
          {loading ? (
            <div className="text-sm text-[#9B8AB0]">Loading…</div>
          ) : noConnection ? (
            <div className="text-center py-8" data-testid="push-no-connection">
              <div className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-3" style={{ background: 'var(--gradient-subtle)', border: '1px solid #E0D4F7' }}>
                <Plug size={22} weight="duotone" className="text-[#7C35DC]" />
              </div>
              <h3 className="text-base font-extrabold text-[#1A0A2E]">No engagement tools connected yet</h3>
              <p className="text-sm text-[#5A4A7A] mt-2 max-w-sm mx-auto">Connect SalesHandy or Lemlist to push leads into your cold-email sequences.</p>
              <Link to="/sales-engagement" onClick={onClose} className="inline-flex items-center gap-1 mt-4 px-4 py-2 rounded-xl text-sm font-bold text-white" style={{ background: 'var(--gradient-brand)' }} data-testid="push-go-connect-btn">
                Connect now <ArrowRight size={14} weight="bold" />
              </Link>
            </div>
          ) : result ? (
            <div className="space-y-3" data-testid="push-result">
              <div className="bg-[#DCFCE7] border border-[#16A34A]/30 rounded-xl px-4 py-3 flex items-start gap-3">
                <Sparkle size={18} weight="fill" className="text-[#16A34A] mt-0.5" />
                <div>
                  <div className="font-extrabold text-[#1A0A2E]" data-testid="push-pushed-count">{result.pushed} lead{result.pushed === 1 ? '' : 's'} pushed to {info.name}</div>
                  <div className="text-xs text-[#5A4A7A]">{info.name} will start the {info.term} on its next send window.</div>
                </div>
              </div>
              {result.failed > 0 && (
                <div className="bg-[#FEF3C7] border border-[#FDE68A] rounded-xl px-4 py-3" data-testid="push-failed-block">
                  <div className="text-xs font-extrabold text-[#1A0A2E] mb-2">{result.failed} skipped</div>
                  <ul className="text-xs text-[#5A4A7A] space-y-1 max-h-40 overflow-y-auto">
                    {(result.errors || []).map((e, i) => (
                      <li key={i}><span className="font-mono text-[#D97706]">{e.lead_id?.slice(0, 8)}</span> · {e.error}</li>
                    ))}
                  </ul>
                </div>
              )}
              <button onClick={onClose} className="w-full px-4 py-2.5 rounded-xl text-sm font-bold text-white" style={{ background: 'var(--gradient-brand)' }} data-testid="push-done-btn">Done</button>
            </div>
          ) : (
            <>
              {/* Platform tabs */}
              <div>
                <label className="block text-[10px] font-bold uppercase tracking-[0.2em] text-[#7B6D9C] mb-2">Send to</label>
                <div className="grid grid-cols-2 gap-2">
                  {['lemlist', 'saleshandy'].map(p => {
                    const conn = status[p]?.connected;
                    const meta = platformInfo[p];
                    return (
                      <button key={p} onClick={() => conn && setPlatform(p)} disabled={!conn}
                        data-testid={`push-tab-${p}`}
                        className={`px-3 py-2.5 rounded-xl text-sm font-bold border transition-all ${platform === p && conn ? 'text-white border-transparent' : conn ? 'text-[#1A0A2E] bg-white border-[#E8E0F5] hover:bg-[#FAF7FF]' : 'text-[#9B8AB0] bg-[#F1F5F9] border-[#E2E8F0] cursor-not-allowed'}`}
                        style={platform === p && conn ? { background: 'var(--gradient-brand)' } : {}}>
                        {meta.name}{!conn && ' · not connected'}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Sequence picker */}
              {status[platform]?.connected && (
                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-[0.2em] text-[#7B6D9C] mb-2">{info.name} {info.term}</label>
                  {sequences.length === 0 ? (
                    <div className="text-xs text-[#9B8AB0] bg-[#FAF7FF] border border-[#EDE5FA] rounded-xl px-3 py-2.5">Loading {info.term}s…</div>
                  ) : (
                    <select value={seqId} onChange={(e) => setSeqId(e.target.value)} data-testid="push-sequence-select"
                      className="w-full px-3 py-2.5 rounded-xl border border-[#E8E0F5] focus:border-[#7C35DC] focus:ring-2 focus:ring-[#7C35DC]/20 text-sm">
                      {sequences.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                    </select>
                  )}
                </div>
              )}

              <div className="bg-[#F4F0FF] border border-[#E0D4F7] rounded-xl px-3 py-2.5 text-[11px] text-[#5A4A7A] leading-relaxed">
                <span className="font-bold text-[#1A0A2E]">Heads up:</span> ARIA dedupes — leads already in the same {info.term} are skipped automatically. Engagement events from {info.name} will flow back into the Lead Feed.
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-[#F0ECF9]">
                <button onClick={onClose} className="px-4 py-2 rounded-xl text-sm font-semibold text-[#5A4A7A] hover:bg-[#F4F0FF]" data-testid="push-cancel-btn">Cancel</button>
                <button onClick={submit} disabled={submitting || !seqId} data-testid="push-submit-btn"
                  className="px-5 py-2 rounded-xl text-sm font-bold text-white disabled:opacity-50"
                  style={{ background: 'var(--gradient-brand)' }}>
                  {submitting ? 'Pushing…' : `Push ${leadIds.length} lead${leadIds.length === 1 ? '' : 's'}`}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default PushToSequenceModal;
