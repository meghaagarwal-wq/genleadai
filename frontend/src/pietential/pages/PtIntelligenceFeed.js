import React, { useEffect, useState, useCallback } from 'react';
import api from '../../config/api';
import { toast } from 'sonner';

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
  };
  return (
    <span className={`text-xs font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full ring-1 ${map[status] || map.new}`}>
      {status || 'new'}
    </span>
  );
};

const IntegrationsCard = ({ status, onSave }) => {
  const [proxy, setProxy] = useState('');
  const [news, setNews] = useState('');
  const [saving, setSaving] = useState(false);

  const save = async () => {
    if (!proxy && !news) {
      toast.info('Paste a key first');
      return;
    }
    setSaving(true);
    try {
      const payload = {};
      if (proxy) payload.proxycurl_api_key = proxy;
      if (news)  payload.newsapi_key = news;
      const { data } = await api.put('/api/pt/insights/integrations', payload);
      toast.success('Saved');
      setProxy('');
      setNews('');
      onSave?.(data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="border border-slate-200 rounded-xl p-5 bg-white" data-testid="pt-insights-integrations-card">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Enrichment sources</div>
        <div className="flex items-center gap-3 text-xs">
          <span className={`flex items-center gap-1 ${status?.proxycurl?.connected ? 'text-emerald-600' : 'text-slate-400'}`}>
            <span className={`w-2 h-2 rounded-full ${status?.proxycurl?.connected ? 'bg-emerald-500' : 'bg-slate-300'}`}/>
            Proxycurl
          </span>
          <span className={`flex items-center gap-1 ${status?.newsapi?.connected ? 'text-emerald-600' : 'text-slate-400'}`}>
            <span className={`w-2 h-2 rounded-full ${status?.newsapi?.connected ? 'bg-emerald-500' : 'bg-slate-300'}`}/>
            NewsAPI
          </span>
        </div>
      </div>
      <p className="text-sm text-slate-600 mb-3">
        Keys are stored encrypted (Fernet AES-128). Without them, Aria
        classifies signals from prospect data only — most scans will
        return no insights.
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <input
          data-testid="pt-insights-proxycurl-input"
          type="password"
          value={proxy}
          onChange={(e) => setProxy(e.target.value)}
          placeholder={status?.proxycurl?.connected ? '••• connected (paste to replace)' : 'Proxycurl API key'}
          className="border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
        />
        <input
          data-testid="pt-insights-newsapi-input"
          type="password"
          value={news}
          onChange={(e) => setNews(e.target.value)}
          placeholder={status?.newsapi?.connected ? '••• connected (paste to replace)' : 'NewsAPI key'}
          className="border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
        />
      </div>
      <div className="flex justify-end mt-3">
        <button
          data-testid="pt-insights-save-keys-btn"
          disabled={saving}
          onClick={save}
          className="px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white text-sm font-semibold rounded-lg disabled:opacity-50"
        >{saving ? 'Saving…' : 'Save keys'}</button>
      </div>
    </div>
  );
};

const InsightCard = ({ card, onAction }) => {
  const sig = SIGNAL_LABELS[card.signal_type] || { label: card.signal_type, color: 'bg-slate-100 text-slate-700' };
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

      {card.suggested_message && (
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 mb-3">
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">Suggested message</div>
          <pre className="text-sm text-slate-700 whitespace-pre-wrap font-sans">{card.suggested_message}</pre>
        </div>
      )}

      {card.status === 'new' && (
        <div className="flex gap-2 flex-wrap">
          <button data-testid={`insight-${card.id}-send-btn`} onClick={send} className="px-3 py-1.5 bg-violet-600 hover:bg-violet-700 text-white text-xs font-semibold rounded-lg">Send via Aria</button>
          <button data-testid={`insight-${card.id}-copy-btn`} onClick={copy} className="px-3 py-1.5 border border-slate-300 hover:bg-slate-50 text-slate-700 text-xs font-semibold rounded-lg">Copy</button>
          <button data-testid={`insight-${card.id}-dismiss-btn`} onClick={dismiss} className="px-3 py-1.5 border border-slate-300 hover:bg-slate-50 text-slate-500 text-xs font-semibold rounded-lg">Dismiss</button>
        </div>
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

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [feed, integ] = await Promise.all([
        api.get('/api/pt/insights/feed', { params: filter === 'all' ? {} : { status: filter } }),
        api.get('/api/pt/insights/integrations'),
      ]);
      setCards(feed.data.cards || []);
      setIntegrationsStatus(integ.data);
    } catch (e) {
      toast.error('Could not load Intelligence Feed');
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => { load(); }, [load]);

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

  const onAction = async (id, action) => {
    try {
      await api.post(`/api/pt/insights/${id}/action`, { action });
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Action failed');
    }
  };

  return (
    <div className="max-w-6xl mx-auto p-6 lg:p-10" data-testid="pt-intelligence-feed-page">
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between mb-6 gap-4">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 mb-2">Intelligence Feed</h1>
          <p className="text-sm text-slate-600 max-w-2xl">
            New buying signals, funding rounds, hiring moves, and other moments worth
            acting on. Aria classifies them with confidence ≥ 70% and drafts the
            outreach for you.
          </p>
        </div>
        <button
          data-testid="pt-insights-scan-btn"
          onClick={runScan}
          disabled={scanning}
          className="px-5 py-2.5 bg-violet-600 hover:bg-violet-700 text-white text-sm font-semibold rounded-lg disabled:opacity-50"
        >{scanning ? 'Scanning prospects…' : 'Run scan now'}</button>
      </div>

      <div className="mb-6">
        <IntegrationsCard status={integrationsStatus} onSave={(s) => setIntegrationsStatus(s)} />
      </div>

      <div className="flex items-center gap-2 mb-4">
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
      </div>

      {loading ? (
        <div className="text-slate-500 text-sm p-4">Loading…</div>
      ) : cards.length === 0 ? (
        <div className="border border-dashed border-slate-300 rounded-xl p-10 text-center bg-slate-50" data-testid="pt-insights-empty">
          <div className="text-base font-semibold text-slate-700 mb-1">No new signals yet</div>
          <div className="text-sm text-slate-500">
            Hit <strong>Run scan now</strong> to fetch signals across your prospects. Without
            Proxycurl + NewsAPI keys, Aria runs in conservative mode — connect them above
            for richer enrichment.
          </div>
        </div>
      ) : (
        <div className="space-y-3" data-testid="pt-insights-feed-list">
          {cards.map((c) => (
            <InsightCard key={c.id} card={c} onAction={onAction} />
          ))}
        </div>
      )}
    </div>
  );
};

export default PtIntelligenceFeed;
