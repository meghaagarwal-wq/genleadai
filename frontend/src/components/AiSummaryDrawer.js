/**
 * AiSummaryDrawer — slide-over panel with the Claude-generated 7-day
 * executive briefing.
 *
 * Backend: GET /api/aria/command-center/ai-summary[?force_refresh=true]
 *   → { summary, generated_at, facts, cached }
 *
 * The endpoint is per-tenant + cached for 1 hour. A "Refresh" button bypasses
 * the cache. We render the summary as plain prose, split on blank lines so
 * the three paragraphs (What happened / What's working / What needs
 * attention) stack nicely.
 */
import { useEffect, useRef, useState } from 'react';
import { X, ArrowsClockwise, Sparkle, Lightning } from '@phosphor-icons/react';
import { toast } from 'sonner';
import api from '../config/api';

const fmtWhen = (iso) => {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    const diff = Math.max(0, (Date.now() - d.getTime()) / 1000);
    if (diff < 60) return 'moments ago';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return d.toLocaleString();
  } catch { return ''; }
};

const AiSummaryDrawer = ({ open, onClose }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const fetchedOnce = useRef(false);

  const fetchSummary = async (force = false) => {
    const setter = force ? setRefreshing : setLoading;
    setter(true);
    try {
      const r = await api.get('/api/aria/command-center/ai-summary', {
        params: force ? { force_refresh: true } : {},
      });
      setData(r.data || null);
      if (force) toast.success('Brief refreshed');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Could not load AI summary');
    } finally { setter(false); }
  };

  // Lazy-load: only hit the endpoint when the drawer opens for the first time
  // in a given session. Subsequent opens reuse the in-memory copy until the
  // user hits Refresh.
  useEffect(() => {
    if (open && !fetchedOnce.current) {
      fetchedOnce.current = true;
      fetchSummary(false);
    }
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === 'Escape') onClose?.(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  const paragraphs = (data?.summary || '').split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);

  return (
    <div
      className="fixed inset-0 z-[60] flex justify-end"
      data-testid="ai-summary-drawer"
      role="dialog"
      aria-modal="true"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
        data-testid="ai-summary-backdrop"
      />

      {/* Panel */}
      <aside
        className="relative w-full sm:w-[480px] h-full overflow-y-auto shadow-2xl flex flex-col"
        style={{ background: 'var(--theme-surface)', borderLeft: '1px solid var(--theme-border-strong)' }}
      >
        {/* Header */}
        <div
          className="px-5 py-4 flex items-center justify-between border-b shrink-0"
          style={{ borderColor: 'var(--theme-border)', background: 'linear-gradient(135deg, #5b21b6 0%, #7c3aed 60%)', color: '#fff' }}
        >
          <div className="flex items-center gap-2">
            <Sparkle size={18} weight="duotone" />
            <div>
              <div className="text-[10px] font-bold uppercase tracking-[0.22em] opacity-80" style={{ fontFamily: 'Plus Jakarta Sans' }}>
                ARIA · 7-day briefing
              </div>
              <div className="text-sm font-bold" style={{ fontFamily: 'Space Grotesk, Inter' }}>
                AI Summary
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            data-testid="ai-summary-close"
            className="w-8 h-8 rounded-lg flex items-center justify-center hover:bg-white/15 transition-colors"
            aria-label="Close AI Summary"
          >
            <X size={16} weight="bold" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 px-5 py-5">
          {loading && !data && (
            <div className="text-sm" style={{ color: 'var(--theme-text-muted)' }} data-testid="ai-summary-loading">
              ARIA is reading the past 7 days…
            </div>
          )}

          {!loading && !data && (
            <div className="text-sm" style={{ color: 'var(--theme-text-muted)' }}>
              No briefing available. Hit refresh to generate one.
            </div>
          )}

          {data && (
            <>
              <div className="text-[10px] uppercase tracking-[0.18em] mb-3 flex items-center gap-2" style={{ color: 'var(--theme-text-muted)', fontFamily: 'Plus Jakarta Sans' }}>
                <span data-testid="ai-summary-generated">{data.cached ? 'cached · ' : ''}generated {fmtWhen(data.generated_at)}</span>
              </div>
              <div className="space-y-4" data-testid="ai-summary-body">
                {paragraphs.length > 0 ? paragraphs.map((p, i) => (
                  <p key={i} className="text-sm leading-relaxed" style={{ color: 'var(--theme-text)', fontFamily: 'Plus Jakarta Sans' }}>
                    {p}
                  </p>
                )) : (
                  <p className="text-sm" style={{ color: 'var(--theme-text-muted)' }}>
                    {data.summary || 'No summary yet.'}
                  </p>
                )}
              </div>

              {/* Raw facts (collapsed) — what Claude was given */}
              {data.facts && (
                <details className="mt-6 text-xs" data-testid="ai-summary-facts">
                  <summary className="cursor-pointer font-semibold" style={{ color: 'var(--theme-text-muted)' }}>
                    <Lightning size={11} weight="fill" className="inline mr-1" />
                    Show the raw 7-day facts ARIA saw
                  </summary>
                  <pre
                    className="mt-2 rounded p-3 whitespace-pre-wrap"
                    style={{ background: 'var(--theme-surface2)', color: 'var(--theme-text-muted)', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: 11 }}
                  >
                    {data.facts}
                  </pre>
                </details>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div
          className="px-5 py-3 border-t flex items-center justify-between shrink-0"
          style={{ borderColor: 'var(--theme-border)', background: 'var(--theme-surface)' }}
        >
          <div className="text-[10px]" style={{ color: 'var(--theme-text-muted)' }}>
            Claude Sonnet · cached 1 hour
          </div>
          <button
            onClick={() => fetchSummary(true)}
            disabled={refreshing}
            data-testid="ai-summary-refresh"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-bold text-white disabled:opacity-50"
            style={{ background: 'var(--theme-purple, #7C35DC)' }}
          >
            <ArrowsClockwise size={12} weight="bold" className={refreshing ? 'animate-spin' : ''} />
            {refreshing ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>
      </aside>
    </div>
  );
};

export default AiSummaryDrawer;
