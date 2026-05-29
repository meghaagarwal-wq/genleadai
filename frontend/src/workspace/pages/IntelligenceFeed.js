import React, { useEffect, useState, useCallback, useMemo } from 'react';
import api from '../../config/api';
import { toast } from 'sonner';
import WorkspacePullBar from '../../components/WorkspacePullBar';

const SIGNAL_LABELS = {
  deal_closed:       { label: 'Deal closed',       color: 'bg-emerald-100 text-emerald-700' },
  funding_round:     { label: 'Funding round',     color: 'bg-violet-100 text-violet-700' },
  event_attending:   { label: 'Event',             color: 'bg-amber-100 text-amber-700' },
  job_change:        { label: 'Job change',        color: 'bg-sky-100 text-sky-700' },
  hiring_signal:     { label: 'Hiring',            color: 'bg-indigo-100 text-indigo-700' },
  content_published: { label: 'Content published', color: 'bg-pink-100 text-pink-700' },
  company_news:      { label: 'Company news',      color: 'bg-rose-100 text-rose-700' },
  social_activity:   { label: 'Social activity',   color: 'bg-teal-100 text-teal-700' },
};

const StatusBadge = ({ status }) => {
  const map = {
    new:       'bg-violet-50 text-violet-700 ring-violet-200',
    sent:      'bg-emerald-50 text-emerald-700 ring-emerald-200',
    copied:    'bg-sky-50 text-sky-700 ring-sky-200',
    dismissed: 'bg-slate-100 text-slate-500 ring-slate-200',
    snoozed:   'bg-amber-50 text-amber-700 ring-amber-200',
  };
  return (
    <span className={`text-xs font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full ring-1 ${map[status] || map.new}`}>
      {status || 'new'}
    </span>
  );
};

// ── ConnectedSourcesPill ────────────────────────────────────────────────
// iter125 — Replaces the legacy in-page Proxycurl / NewsAPI key inputs.
// Reads enrichment provider status from the UNIVERSAL store
// (`/api/integrations/status`), the same source Train ARIA / Intel Tab use,
// so there is only ever one place to manage keys: /app/integrations.
const ConnectedSourcesPill = ({ status }) => {
  // We surface the three enrichment providers the crawler actually uses
  // today: rapidapi (LinkedIn — replaces Proxycurl), serper (web + news),
  // proxycurl (legacy fallback, kept so existing tenants don't break).
  const providers = [
    { id: 'rapidapi',  label: 'RapidAPI · LinkedIn' },
    { id: 'serper',    label: 'Serper · Web/News'  },
    { id: 'proxycurl', label: 'Proxycurl · legacy' },
  ];
  return (
    <div className="border border-slate-200 rounded-xl p-4 bg-white flex flex-wrap items-center gap-4" data-testid="instinct-connected-sources">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Enrichment sources</div>
      <div className="flex flex-wrap items-center gap-3 text-xs">
        {providers.map((p) => {
          const connected = !!status?.[p.id]?.connected;
          return (
            <span
              key={p.id}
              className={`flex items-center gap-1.5 ${connected ? 'text-emerald-600' : 'text-slate-400'}`}
              data-testid={`instinct-source-${p.id}`}
              title={connected ? 'Connected' : 'Not connected — open /app/integrations to add a key'}
            >
              <span className={`w-2 h-2 rounded-full ${connected ? 'bg-emerald-500' : 'bg-slate-300'}`} />
              {p.label}
            </span>
          );
        })}
      </div>
      <a
        href="/app/integrations"
        className="ml-auto text-xs font-semibold text-violet-600 hover:text-violet-700"
        data-testid="instinct-manage-integrations-link"
      >Manage keys →</a>
    </div>
  );
};

const InsightCard = ({ card, onAction }) => {
  const sig = SIGNAL_LABELS[card.signal_type] || { label: card.signal_type, color: 'bg-slate-100 text-slate-700' };
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(card.suggested_message || '');
  const [showSnoozeMenu, setShowSnoozeMenu] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(card.suggested_message || '');
      onAction(card.id, 'copy');
      toast.success('Message copied');
    } catch (e) {
      toast.error('Copy failed');
    }
  };
  const send = () => onAction(card.id, 'send');
  const dismiss = () => onAction(card.id, 'dismiss');

  // iter105 — Edit + Send
  const sendEdited = () => {
    const body = (draft || '').trim();
    if (!body) { toast.error('Message cannot be empty'); return; }
    onAction(card.id, 'send', { message: body });
    setEditing(false);
  };

  // iter105 — Snooze (2d / 5d / custom)
  const snoozeFor = (days) => {
    const until = new Date(Date.now() + days * 86400 * 1000).toISOString();
    onAction(card.id, 'snooze', { snooze_until: until });
    setShowSnoozeMenu(false);
  };
  const snoozeCustom = () => {
    const v = window.prompt('Snooze until (YYYY-MM-DD):');
    if (!v) return;
    const parsed = new Date(v);
    if (Number.isNaN(parsed.getTime())) { toast.error('Invalid date'); return; }
    onAction(card.id, 'snooze', { snooze_until: parsed.toISOString() });
    setShowSnoozeMenu(false);
  };

  // iter105 — Download PDF
  const downloadPdf = async () => {
    try {
      const res = await api.get(`/api/pt/insights/${card.id}/pdf`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `aria-insight-${(card.prospect_name || 'card').replace(/\s+/g, '-').toLowerCase()}.pdf`;
      document.body.appendChild(a); a.click(); a.remove();
      window.URL.revokeObjectURL(url);
      toast.success('PDF downloaded');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'PDF download failed');
    }
  };

  return (
    <div className="border border-slate-200 rounded-xl p-5 bg-white" data-testid={`insight-card-${card.id}`}>
      <div className="flex items-start justify-between gap-3 mb-3 flex-wrap">
        <div>
          <div className="text-base font-bold text-slate-900">{card.prospect_name || '—'}</div>
          <div className="text-sm text-slate-600">{card.prospect_title || ''}{card.prospect_company ? ` · ${card.prospect_company}` : ''}</div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${sig.color}`}>{sig.label}</span>
          <span className="text-xs font-medium text-slate-500">{Math.round((card.confidence || 0) * 100)}% conf.</span>
          <StatusBadge status={card.status} />
        </div>
      </div>

      <p className="text-sm text-slate-700 mb-3 leading-relaxed">{card.signal_summary}</p>
      {card.icp_match_name && (
        <div className="text-xs text-slate-500 mb-3">
          ICP match: <span className="font-semibold text-slate-700">{card.icp_match_name}</span> · score {Math.round((card.icp_match_score || 0) * 100)}%
        </div>
      )}

      {card.suggested_message && !editing && (
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 mb-3">
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">Suggested message</div>
          <pre className="text-sm text-slate-700 whitespace-pre-wrap font-sans">{card.suggested_message}</pre>
        </div>
      )}

      {editing && (
        <div className="bg-violet-50 border border-violet-200 rounded-lg p-3 mb-3" data-testid={`insight-${card.id}-edit-pane`}>
          <div className="text-xs font-semibold text-violet-600 uppercase tracking-wide mb-1.5">Edit message before sending</div>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={5}
            className="w-full px-3 py-2 text-sm border border-violet-300 rounded-md focus:outline-none focus:ring-2 focus:ring-violet-400 font-sans"
            data-testid={`insight-${card.id}-edit-textarea`}
          />
          <div className="flex gap-2 mt-2">
            <button data-testid={`insight-${card.id}-edit-send-btn`} onClick={sendEdited}
                    className="px-3 py-1.5 bg-violet-600 hover:bg-violet-700 text-white text-xs font-semibold rounded-lg">
              Send now
            </button>
            <button data-testid={`insight-${card.id}-edit-cancel-btn`} onClick={() => { setEditing(false); setDraft(card.suggested_message || ''); }}
                    className="px-3 py-1.5 border border-slate-300 hover:bg-slate-50 text-slate-700 text-xs font-semibold rounded-lg">
              Cancel
            </button>
          </div>
        </div>
      )}

      {card.status === 'new' && !editing && (
        <div className="flex gap-2 flex-wrap relative">
          <button data-testid={`insight-${card.id}-send-btn`} onClick={send} className="px-3 py-1.5 bg-violet-600 hover:bg-violet-700 text-white text-xs font-semibold rounded-lg">Send via Aria</button>
          <button data-testid={`insight-${card.id}-edit-btn`} onClick={() => setEditing(true)} className="px-3 py-1.5 border border-violet-300 hover:bg-violet-50 text-violet-700 text-xs font-semibold rounded-lg">Edit + Send</button>
          <button data-testid={`insight-${card.id}-copy-btn`} onClick={copy} className="px-3 py-1.5 border border-slate-300 hover:bg-slate-50 text-slate-700 text-xs font-semibold rounded-lg">Copy</button>
          <button data-testid={`insight-${card.id}-snooze-btn`} onClick={() => setShowSnoozeMenu(v => !v)} className="px-3 py-1.5 border border-slate-300 hover:bg-slate-50 text-slate-500 text-xs font-semibold rounded-lg">Snooze</button>
          <button data-testid={`insight-${card.id}-pdf-btn`} onClick={downloadPdf} className="px-3 py-1.5 border border-slate-300 hover:bg-slate-50 text-slate-500 text-xs font-semibold rounded-lg">Download PDF</button>
          <button data-testid={`insight-${card.id}-dismiss-btn`} onClick={dismiss} className="px-3 py-1.5 border border-slate-300 hover:bg-slate-50 text-slate-500 text-xs font-semibold rounded-lg">Dismiss</button>
          {showSnoozeMenu && (
            <div className="absolute top-full mt-1 left-0 z-10 bg-white border border-slate-200 rounded-lg shadow-lg p-2 flex flex-col gap-1 min-w-[140px]" data-testid={`insight-${card.id}-snooze-menu`}>
              <button onClick={() => snoozeFor(2)} className="px-3 py-1.5 text-xs text-left hover:bg-slate-50 rounded">Snooze 2 days</button>
              <button onClick={() => snoozeFor(5)} className="px-3 py-1.5 text-xs text-left hover:bg-slate-50 rounded">Snooze 5 days</button>
              <button onClick={snoozeCustom} className="px-3 py-1.5 text-xs text-left hover:bg-slate-50 rounded">Pick date…</button>
            </div>
          )}
        </div>
      )}
      {card.status === 'snoozed' && card.snooze_until && (
        <div className="text-xs text-amber-700 mt-2">
          Snoozed until {new Date(card.snooze_until).toLocaleDateString()}
        </div>
      )}
    </div>
  );
};

const LastScanChip = ({ last_scan_at, last_scan_count, status_counts }) => {
  if (!last_scan_at) {
    return (
      <div
        data-testid="pt-insights-last-scan-chip-empty"
        className="mt-3 inline-flex items-center gap-2 text-xs font-medium text-slate-500 bg-slate-100 ring-1 ring-slate-200 rounded-full px-3 py-1"
      >
        <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
        Never scanned — hit “Run scan now” to start
      </div>
    );
  }
  // Pretty relative time
  let rel = '';
  try {
    const diff = (Date.now() - new Date(last_scan_at).getTime()) / 1000;
    if (diff < 60)         rel = 'just now';
    else if (diff < 3600)  rel = `${Math.round(diff / 60)}m ago`;
    else if (diff < 86400) rel = `${Math.round(diff / 3600)}h ago`;
    else                   rel = `${Math.round(diff / 86400)}d ago`;
  } catch { rel = '—'; }
  const newCount = (status_counts || {}).new || 0;
  return (
    <div
      data-testid="pt-insights-last-scan-chip"
      className="mt-3 inline-flex items-center gap-2 text-xs font-semibold text-violet-700 bg-violet-50 ring-1 ring-violet-200 rounded-full px-3 py-1"
    >
      <span className="w-1.5 h-1.5 rounded-full bg-violet-500 animate-pulse" />
      Last scanned · <span className="text-slate-700 font-normal">{rel}</span>
      <span className="text-slate-300">·</span>
      <span data-testid="pt-insights-last-scan-count">
        {last_scan_count} created this run
      </span>
      {newCount > 0 && (
        <>
          <span className="text-slate-300">·</span>
          <span className="text-emerald-700">
            {newCount} unread
          </span>
        </>
      )}
    </div>
  );
};

const PtIntelligenceFeed = () => {
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [cards, setCards] = useState([]);
  const [integrationsStatus, setIntegrationsStatus] = useState(null);
  const [filter, setFilter] = useState('new');
  const [signalType, setSignalType] = useState('all');
  const [sortBy, setSortBy] = useState('recency');
  const [scanMeta, setScanMeta] = useState({ last_scan_at: null, last_scan_count: 0, status_counts: {} });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [feed, integ] = await Promise.all([
        api.get('/api/pt/insights/feed', { params: filter === 'all' ? {} : { status: filter } }),
        api.get('/api/integrations/status'),
      ]);
      setCards(feed.data.cards || []);
      setScanMeta({
        last_scan_at: feed.data.last_scan_at || null,
        last_scan_count: feed.data.last_scan_count || 0,
        status_counts: feed.data.status_counts || {},
      });
      setIntegrationsStatus(integ.data || {});
    } catch (e) {
      toast.error('Could not load Intelligence Feed');
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  // iter109 Batch 2 — client-side signal-type filter + sort
  const visibleCards = useMemo(() => {
    let arr = cards.slice();
    if (signalType !== 'all') {
      arr = arr.filter((c) => c.signal_type === signalType);
    }
    if (sortBy === 'icp_match') {
      arr.sort((a, b) => (b.icp_match_score || 0) - (a.icp_match_score || 0));
    } else if (sortBy === 'confidence') {
      arr.sort((a, b) => (b.confidence || 0) - (a.confidence || 0));
    } else {
      arr.sort((a, b) => (new Date(b.created_at || 0).getTime()) - (new Date(a.created_at || 0).getTime()));
    }
    return arr;
  }, [cards, signalType, sortBy]);

  const runScan = async () => {
    setScanning(true);
    try {
      const { data } = await api.post('/api/pt/insights/scan/run-now', {}, { timeout: 180000 });
      const enrich = data.enrichment_status;
      const enrich_msg = `Proxycurl=${enrich.proxycurl ? '✓' : '—'} NewsAPI=${enrich.newsapi ? '✓' : '—'} Claude=${enrich.claude ? '✓' : '—'}`;
      if (data.insights_created === 0) {
        toast.info(`Scanned ${data.scanned} prospects · 0 new signals · ${enrich_msg}`);
      } else {
        toast.success(`Scanned ${data.scanned} · ${data.insights_created} new insights · ${enrich_msg}`);
      }
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Scan failed');
    } finally {
      setScanning(false);
    }
  };

  const onAction = async (id, action, extra = {}) => {
    try {
      await api.post(`/api/pt/insights/${id}/action`, { action, ...extra });
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Action failed');
    }
  };

  return (
    <div className="max-w-6xl mx-auto p-6 lg:p-10" data-testid="pt-intelligence-feed-page">
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between mb-6 gap-4">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-[#7C35DC]">Instinct</div>
          <h1 className="text-3xl font-bold text-slate-900 mb-2">Instinct Feed</h1>
          <p className="text-sm text-slate-600 max-w-2xl">
            New buying signals, funding rounds, hiring moves, and other moments worth
            acting on. Aria classifies them with confidence ≥ 70% and drafts the
            outreach for you.
          </p>
          <LastScanChip
            last_scan_at={scanMeta.last_scan_at}
            last_scan_count={scanMeta.last_scan_count}
            status_counts={scanMeta.status_counts}
          />
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <WorkspacePullBar />
          <button
            data-testid="pt-insights-scan-btn"
            onClick={runScan}
            disabled={scanning}
            className="px-5 py-2.5 bg-violet-600 hover:bg-violet-700 text-white text-sm font-semibold rounded-lg disabled:opacity-50"
          >{scanning ? 'Scanning prospects…' : 'Run scan now'}</button>
        </div>
      </div>

      <div className="mb-6">
        <ConnectedSourcesPill status={integrationsStatus} />
      </div>

      <div className="flex items-center justify-between gap-3 mb-4 flex-wrap" data-testid="instinct-filter-bar">
        <div className="flex items-center gap-2 flex-wrap">
          {['new', 'sent', 'dismissed', 'all'].map((f) => (
            <button
              key={f}
              data-testid={`pt-insights-filter-${f}`}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 text-xs font-semibold rounded-full transition-colors ${
                filter === f ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >{f.charAt(0).toUpperCase() + f.slice(1)}</button>
          ))}
          <select
            value={signalType}
            onChange={(e) => setSignalType(e.target.value)}
            data-testid="instinct-signal-type-filter"
            className="px-3 py-1.5 text-xs font-semibold border border-slate-200 rounded-full bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-violet-500"
          >
            <option value="all">All Signals</option>
            {Object.entries(SIGNAL_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v.label}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">Sort</span>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            data-testid="instinct-sort-by"
            className="px-3 py-1.5 text-xs font-semibold border border-slate-200 rounded-full bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-violet-500"
          >
            <option value="recency">Recency</option>
            <option value="icp_match">ICP Match Score</option>
            <option value="confidence">Confidence</option>
          </select>
        </div>
      </div>

      {loading ? (
        <div className="text-slate-500 text-sm p-4">Loading…</div>
      ) : visibleCards.length === 0 ? (
        <div className="border border-dashed border-slate-300 rounded-xl p-10 text-center bg-slate-50" data-testid="pt-insights-empty">
          <div className="text-base font-semibold text-slate-700 mb-1">No signals yet</div>
          <div className="text-sm text-slate-500">
            Prospects are being scanned daily at the configured time. Hit <strong>Run scan now</strong> to fetch immediately.
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3" data-testid="pt-insights-feed-list">
          {visibleCards.map((c) => (
            <InsightCard key={c.id} card={c} onAction={onAction} />
          ))}
        </div>
      )}
    </div>
  );
};

export default PtIntelligenceFeed;
