/**
 * Iter99 — V3 missing integrations panel.
 *
 * Surfaces 4 new lead sources on top of the existing
 * Saleshandy/Lemlist primary integrations:
 *
 *   - Google Ads  →  webhook URL generator (auto-rolled key)
 *   - Apollo      →  direct-pull (saved search id or keyword) + Test
 *   - Serper      →  web/news enrichment fallback for B2B Insights + Test
 *   - Website Pixel → one-tag JS snippet + public tracking endpoint
 *
 * Each card is self-contained and uses the existing `ptApi` axios
 * instance + sonner toasts.
 */
import { useEffect, useState } from 'react';
import { ArrowClockwise, Copy } from '@phosphor-icons/react';
import { toast } from 'sonner';
import { ptApi } from '../shared';

const Section = ({ children }) => (
  <div className="bg-white border border-[#E2E8F0] rounded-lg p-4">{children}</div>
);

const Label = ({ children }) => (
  <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#64748B] mb-1">{children}</div>
);

const Btn = ({ children, onClick, variant = 'primary', testid, disabled }) => (
  <button
    onClick={onClick}
    disabled={disabled}
    data-testid={testid}
    className={
      'text-xs font-semibold px-3 py-1.5 rounded-md disabled:opacity-50 inline-flex items-center gap-1.5 ' +
      (variant === 'primary'
        ? 'text-white'
        : 'text-[#7C35DC] border border-[#7C35DC]/30 bg-white')
    }
    style={variant === 'primary' ? { background: '#7C35DC' } : {}}
  >
    {children}
  </button>
);

const copyToClipboard = (txt) => {
  navigator.clipboard.writeText(txt);
  toast.success('Copied');
};

// ─── Connection-key persistence shared between Apollo & Serper ──────────────
const saveKey = async (integration_type, api_key) => {
  // POST to the V3 integrations hub connect endpoint
  await ptApi.post('/api/integrations/connect', {
    integration_type,
    config: { api_key },
  });
};

// ─── 1. Google Ads ──────────────────────────────────────────────────────────
const GoogleAdsCard = () => {
  const [info, setInfo] = useState(null);
  const load = async () => {
    try {
      const r = await ptApi.get('/api/integrations/google-ads/webhook-info');
      setInfo(r.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Could not load Google Ads info');
    }
  };
  useEffect(() => { load(); }, []);

  if (!info) return null;
  return (
    <Section>
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm font-bold text-[#0F172A]">Google Ads · Lead Form webhook</div>
        <span className="text-[10px] uppercase tracking-[0.14em] font-bold text-[#7C35DC]">V3</span>
      </div>
      <p className="text-xs text-[#64748B] mb-3">
        Paste these two values into the Lead Form extension of your Google Ads campaign.
        Aria will capture every form-fill as a lead automatically.
      </p>
      <div className="space-y-2">
        <div>
          <Label>Webhook URL</Label>
          <div className="flex items-center gap-2 bg-[#F8FAFC] rounded px-2 py-1.5">
            <span className="flex-1 text-xs font-mono text-[#475569] truncate" data-testid="pt-gads-webhook-url">{info.webhook_url}</span>
            <button onClick={() => copyToClipboard(info.webhook_url)} className="text-[#7C35DC]" data-testid="pt-gads-copy-url"><Copy size={12} weight="bold" /></button>
          </div>
        </div>
        <div>
          <Label>Webhook Key</Label>
          <div className="flex items-center gap-2 bg-[#F8FAFC] rounded px-2 py-1.5">
            <span className="flex-1 text-xs font-mono text-[#475569] truncate" data-testid="pt-gads-webhook-key">{info.webhook_key}</span>
            <button onClick={() => copyToClipboard(info.webhook_key)} className="text-[#7C35DC]" data-testid="pt-gads-copy-key"><Copy size={12} weight="bold" /></button>
          </div>
        </div>
      </div>
    </Section>
  );
};

// ─── 2. Apollo ──────────────────────────────────────────────────────────────
const ApolloCard = () => {
  const [apiKey, setApiKey] = useState('');
  const [keyword, setKeyword] = useState('founder');
  const [savedId, setSavedId] = useState('');
  const [pulling, setPulling] = useState(false);

  const test = async () => {
    try { const r = await ptApi.post('/api/integrations/apollo/test-connection'); toast.success(r.data.ok ? 'Apollo connection OK' : `Apollo: HTTP ${r.data.status}`); }
    catch (e) { toast.error(e.response?.data?.detail || 'Apollo test failed'); }
  };

  const pull = async () => {
    setPulling(true);
    try {
      const body = savedId ? { saved_search_id: savedId } : { keyword };
      const r = await ptApi.post('/api/integrations/apollo/pull', body);
      toast.success(`Apollo pull: ${r.data.imported} new · ${r.data.deduplicated} deduped · ${r.data.fetched} fetched`);
    } catch (e) { toast.error(e.response?.data?.detail || 'Apollo pull failed'); }
    finally { setPulling(false); }
  };

  return (
    <Section>
      <div className="text-sm font-bold text-[#0F172A] mb-2">Apollo · direct pull</div>
      <p className="text-xs text-[#64748B] mb-3">
        Pull leads on-demand from a saved search id or a free-text keyword.
        Imported via the standard dedup + scoring pipeline.
      </p>
      <div className="space-y-2">
        <div>
          <Label>API key</Label>
          <div className="flex items-center gap-1.5">
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Paste Apollo API key"
              data-testid="pt-apollo-key"
              className="flex-1 text-sm border border-[#E2E8F0] rounded-md px-2 py-1.5 outline-none"
            />
            <Btn testid="pt-apollo-save" disabled={!apiKey} onClick={async () => {
              try { await saveKey('apollo', apiKey); setApiKey(''); toast.success('Apollo key saved'); }
              catch (e) { toast.error(e.response?.data?.detail || 'Save failed'); }
            }}>Save</Btn>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <Label>Saved search id (optional)</Label>
            <input value={savedId} onChange={(e) => setSavedId(e.target.value)} placeholder="6512abc…"
              data-testid="pt-apollo-saved-id"
              className="w-full text-sm border border-[#E2E8F0] rounded-md px-2 py-1.5 outline-none" />
          </div>
          <div>
            <Label>Keyword fallback</Label>
            <input value={keyword} onChange={(e) => setKeyword(e.target.value)} placeholder="founder, CTO…"
              data-testid="pt-apollo-keyword"
              className="w-full text-sm border border-[#E2E8F0] rounded-md px-2 py-1.5 outline-none" />
          </div>
        </div>
        <div className="flex items-center gap-2 pt-1">
          <Btn variant="ghost" testid="pt-apollo-test" onClick={test}><ArrowClockwise size={11} /> Test</Btn>
          <Btn testid="pt-apollo-pull" onClick={pull} disabled={pulling}>{pulling ? 'Pulling…' : 'Pull leads now'}</Btn>
        </div>
      </div>
    </Section>
  );
};

// ─── 3. Serper ──────────────────────────────────────────────────────────────
const SerperCard = () => {
  const [apiKey, setApiKey] = useState('');
  const test = async () => {
    try { const r = await ptApi.post('/api/integrations/serper/test-connection'); toast.success(r.data.ok ? 'Serper connection OK' : `Serper: HTTP ${r.data.status}`); }
    catch (e) { toast.error(e.response?.data?.detail || 'Serper test failed'); }
  };
  return (
    <Section>
      <div className="text-sm font-bold text-[#0F172A] mb-2">Serper · web/news enrichment</div>
      <p className="text-xs text-[#64748B] mb-3">
        Used by the B2B Insights Engine as a fallback when NewsAPI returns no results.
        Cheap. Recommended for B2B workspaces.
      </p>
      <div className="space-y-2">
        <Label>API key</Label>
        <div className="flex items-center gap-1.5">
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="Paste Serper API key"
            data-testid="pt-serper-key"
            className="flex-1 text-sm border border-[#E2E8F0] rounded-md px-2 py-1.5 outline-none"
          />
          <Btn testid="pt-serper-save" disabled={!apiKey} onClick={async () => {
            try { await saveKey('serper', apiKey); setApiKey(''); toast.success('Serper key saved'); }
            catch (e) { toast.error(e.response?.data?.detail || 'Save failed'); }
          }}>Save</Btn>
          <Btn variant="ghost" testid="pt-serper-test" onClick={test}><ArrowClockwise size={11} /> Test</Btn>
        </div>
      </div>
    </Section>
  );
};

// ─── 4. Website Pixel ───────────────────────────────────────────────────────
const WebsitePixelCard = () => {
  const [info, setInfo] = useState(null);
  useEffect(() => {
    (async () => {
      try { const r = await ptApi.get('/api/integrations/website-pixel/snippet'); setInfo(r.data); }
      catch (e) { /* silent */ }
    })();
  }, []);
  if (!info) return null;
  return (
    <Section>
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm font-bold text-[#0F172A]">Website Pixel</div>
        <Btn variant="ghost" testid="pt-pixel-copy" onClick={() => copyToClipboard(info.snippet)}>
          <Copy size={11} weight="bold" /> Copy snippet
        </Btn>
      </div>
      <p className="text-xs text-[#64748B] mb-2">
        Paste this one-line snippet into your website's <code className="bg-[#F8FAFC] px-1 rounded">&lt;head&gt;</code>.
        Tracks pageviews and auto-captures form submissions that include an email or phone field.
      </p>
      <pre className="bg-[#0F172A] text-[#E2E8F0] text-[10px] font-mono p-3 rounded overflow-x-auto max-h-44" data-testid="pt-pixel-snippet">
        {info.snippet}
      </pre>
      <div className="mt-2 text-[10px] text-[#94A3B8]">
        Tracks to: <span className="font-mono">{info.track_endpoint}</span>
      </div>
    </Section>
  );
};

const PtIntegrationsExtras = () => (
  <div data-testid="pt-integrations-extras" className="mt-8">
    <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-[#7C35DC] mb-2">
      V3 lead sources
    </div>
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
      <GoogleAdsCard />
      <ApolloCard />
      <SerperCard />
      <WebsitePixelCard />
    </div>
  </div>
);

export default PtIntegrationsExtras;
