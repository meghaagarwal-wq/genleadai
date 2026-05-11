/**
 * FailedMessages — /admin/failed-messages
 *
 * Lists unresolved entries in failed_message_log and allows owner/admin to
 * retry or dismiss each one. Auto-refreshes every 30s.
 */
import React, { useEffect, useState } from 'react';
import api from '../config/api';
import { toast } from 'sonner';
import { useAuth } from '../context/AuthContext';
import { Warning, ArrowsClockwise, X, EnvelopeSimple, ChatCircle, ArrowClockwise } from '@phosphor-icons/react';

const CHANNEL_META = {
  whatsapp: { label: 'WhatsApp', color: '#25D366', icon: ChatCircle },
  email: { label: 'Email', color: '#0055FF', icon: EnvelopeSimple },
};

const fmt = (iso) => { try { return new Date(iso).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }); } catch { return '—'; } };

const FailedMessages = () => {
  const { user } = useAuth();
  const [failures, setFailures] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(null);

  const isOwnerAdmin = ['owner', 'admin'].includes((user?.role || '').toLowerCase()) || user?.tenant_role === 'owner' || user?.tenant_role === 'admin';

  const load = async () => {
    try { const r = await api.get('/api/failed-messages'); setFailures(r.data?.failures || []); }
    catch (e) { toast.error('Failed to load'); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); const id = setInterval(load, 30000); return () => clearInterval(id); }, []);

  const retry = async (id) => {
    setBusy(id);
    try { await api.post(`/api/failed-messages/${id}/retry`); toast.success('Retry scheduled'); load(); }
    catch (e) { toast.error(e.response?.data?.detail || 'Retry failed'); }
    finally { setBusy(null); }
  };

  const retryAll = async () => {
    if (!window.confirm(`Retry all ${failures.length} failed messages?`)) return;
    for (const f of failures) {
      try { await api.post(`/api/failed-messages/${f.id}/retry`); } catch { /* ignore */ }
    }
    toast.success('All retries scheduled');
    load();
  };

  const dismiss = async (id) => {
    if (!window.confirm('Dismiss this failure? It will be marked resolved.')) return;
    setBusy(id);
    try { await api.post(`/api/failed-messages/${id}/dismiss`); toast.success('Dismissed'); load(); }
    catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    finally { setBusy(null); }
  };

  return (
    <div className="space-y-5 max-w-[1200px] mx-auto" data-testid="failed-messages-page">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#DC2626] mb-1">Graceful Degradation</div>
          <h1 className="text-3xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Failed Message Log</h1>
          <p className="text-sm text-[#5A4A7A] mt-1">Messages that failed after 3 automatic retries. Investigate, retry, or dismiss.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={load} data-testid="refresh-failures" className="inline-flex items-center gap-1.5 px-3 py-2 bg-white border border-[#E8E0F5] rounded-lg text-xs font-bold text-[#5A4A7A] hover:bg-[#F9F5FF]">
            <ArrowsClockwise size={12} /> Refresh
          </button>
          {failures.length > 0 && isOwnerAdmin && (
            <button onClick={retryAll} data-testid="retry-all" className="inline-flex items-center gap-1.5 px-3 py-2 btn-gradient rounded-lg text-xs font-bold">
              <ArrowClockwise size={12} weight="bold" /> Retry all ({failures.length})
            </button>
          )}
        </div>
      </div>

      {loading ? (
        <div className="bg-white border border-[#E8E0F5] rounded-xl p-10 text-center text-sm text-[#9B8AB0]">Loading…</div>
      ) : failures.length === 0 ? (
        <div className="bg-white border border-[#E8E0F5] rounded-xl p-12 text-center" data-testid="no-failures">
          <div className="w-14 h-14 rounded-full bg-[#DCFCE7] flex items-center justify-center mx-auto mb-3"><Warning size={28} weight="duotone" className="text-[#16A34A]" /></div>
          <h3 className="text-base font-bold text-[#1A0A2E] mb-1" style={{ fontFamily: 'Plus Jakarta Sans' }}>No unresolved failures 🎉</h3>
          <p className="text-xs text-[#5A4A7A]">Aria's delivery layer is healthy.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {failures.map((f) => {
            const meta = CHANNEL_META[f.channel] || CHANNEL_META.whatsapp;
            const Icon = meta.icon;
            return (
              <div key={f.id} className="bg-white border border-[#E8E0F5] rounded-xl p-4" style={{ boxShadow: 'var(--shadow-card)' }} data-testid={`failure-${f.id}`}>
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      <div className="w-6 h-6 rounded-md flex items-center justify-center" style={{ background: meta.color + '20' }}>
                        <Icon size={12} weight="fill" style={{ color: meta.color }} />
                      </div>
                      <span className="text-sm font-bold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{meta.label}</span>
                      <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-[#FEE2E2] text-[#DC2626] border border-[#DC2626]/30">FAILED</span>
                      <span className="text-[10px] font-mono text-[#9B8AB0]">{f.retry_count || 0} retries</span>
                      <span className="text-[10px] text-[#9B8AB0]">{fmt(f.created_at)}</span>
                    </div>
                    <p className="text-xs text-[#DC2626] font-mono mb-2 break-all">{f.error_reason || 'Unknown error'}</p>
                    {f.payload?.body && <p className="text-xs text-[#5A4A7A] line-clamp-2 bg-[#FAFAFA] p-2 rounded border border-[#F0ECF9]">{f.payload.body}</p>}
                    {f.lead_id && (
                      <a href={`/leads/${f.lead_id}`} className="inline-flex items-center gap-1 text-[10px] font-bold text-[#7C35DC] hover:text-[#6B28C8] mt-2">View lead →</a>
                    )}
                  </div>
                  {isOwnerAdmin && (
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <button onClick={() => retry(f.id)} disabled={busy === f.id} data-testid={`retry-${f.id}`}
                        className="inline-flex items-center gap-1 px-2.5 py-1.5 bg-white border border-[#7C35DC]/30 text-[#7C35DC] rounded text-xs font-bold hover:bg-[#F4F0FF] disabled:opacity-40">
                        <ArrowClockwise size={11} weight="bold" /> Retry
                      </button>
                      <button onClick={() => dismiss(f.id)} disabled={busy === f.id} data-testid={`dismiss-${f.id}`}
                        className="inline-flex items-center gap-1 px-2.5 py-1.5 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded text-xs font-bold hover:bg-[#FEE2E2] hover:text-[#DC2626] hover:border-[#DC2626]/30 disabled:opacity-40">
                        <X size={11} weight="bold" /> Dismiss
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

export default FailedMessages;
