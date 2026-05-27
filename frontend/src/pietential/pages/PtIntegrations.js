import { useEffect, useState } from 'react';
import { Plugs, ArrowClockwise, Copy } from '@phosphor-icons/react';
import { toast } from 'sonner';
import { ptApi, PageHeader, fmtDateTime } from '../shared';
import PtIntegrationsExtras from './PtIntegrationsExtras';

const PRETTY = {
  saleshandy: 'Saleshandy',
  lemlist: 'Lemlist',
  apollo: 'Apollo',
  apify: 'Apify',
  the_boomernag: 'The Boomernag',
  make_com: 'Make.com',
  n8n: 'n8n',
  calendly: 'Calendly',
  ga4: 'Google Analytics 4',
  linkedin_pixel: 'LinkedIn Pixel',
  newsletter_platform: 'Newsletter platform',
  lead_magnet_form: 'Lead magnet form',
  pietential_website_forms: 'Pietential website forms',
};

const STATUS_META = {
  not_connected: { label: 'Not connected', color: '#94A3B8' },
  needs_setup:   { label: 'Needs setup',    color: '#F59E0B' },
  connected:     { label: 'Connected',      color: '#7C35DC' },
};

// Source-specific webhook routes that Make.com / n8n should hit
const WEBHOOK_HINTS = {
  saleshandy: ['/api/pt/webhooks/saleshandy/open', '/api/pt/webhooks/saleshandy/click', '/api/pt/webhooks/saleshandy/reply'],
  lemlist: ['/api/pt/webhooks/lemlist/connection-accepted', '/api/pt/webhooks/lemlist/dm-reply'],
  newsletter_platform: ['/api/pt/webhooks/newsletter/subscribe', '/api/pt/webhooks/newsletter/open', '/api/pt/webhooks/newsletter/click'],
  lead_magnet_form: ['/api/pt/webhooks/lead-magnet/claim', '/api/pt/webhooks/job-satisfaction-analysis/claim', '/api/pt/webhooks/job-satisfaction-analysis/complete'],
  calendly: ['/api/pt/webhooks/calendly/booked'],
  ga4: ['/api/pt/webhooks/ga4/high-intent-page-visit'],
};

// iter106 — OAuth integrations panel
const OAUTH_PROVIDERS = [
  { id: 'calendly',  label: 'Calendly',     desc: 'Auto-register no-show + booked + cancelled webhooks.' },
  { id: 'gmail',     label: 'Gmail',        desc: 'Track replies on outbound email threads.' },
  { id: 'outlook',   label: 'Outlook',      desc: 'Track replies on outbound email threads.' },
  { id: 'meta',      label: 'Meta Ads',     desc: 'Pull Lead Gen Form submissions every 15 min.' },
  { id: 'linkedin',  label: 'LinkedIn',     desc: 'Organic posting + profile data.' },
  { id: 'googleads', label: 'Google Ads',   desc: 'Pull lead form conversions every 15 min.' },
];

const OAuthIntegrations = () => {
  const [statuses, setStatuses] = useState({});
  const [busyId, setBusyId] = useState(null);
  const refresh = async () => {
    try {
      const { data } = await ptApi.get('/api/integrations/list');
      const map = {};
      for (const item of (data?.integrations || [])) {
        if (OAUTH_PROVIDERS.find(p => p.id === item.platform)) {
          map[item.platform] = item;
        }
      }
      setStatuses(map);
    } catch (e) { /* silent — list endpoint optional */ }
  };
  useEffect(() => { refresh(); }, []);

  const connect = async (id) => {
    setBusyId(id);
    try {
      const { data } = await ptApi.get(`/api/integrations/${id}/connect`);
      const w = window.open(data.auth_url, '_blank', 'width=520,height=720');
      const onMsg = (e) => {
        if (e?.data?.type === 'oauth_done' && e.data.provider === id) {
          window.removeEventListener('message', onMsg);
          refresh();
          toast.success(`${id} connected`);
          try { w && w.close(); } catch (_) {}
        }
      };
      window.addEventListener('message', onMsg);
    } catch (e) {
      toast.error(e?.response?.data?.detail || `Could not start ${id} OAuth — check provider credentials in backend env`);
    } finally {
      setBusyId(null);
    }
  };

  const disconnect = async (id) => {
    if (!window.confirm(`Disconnect ${id}? You'll need to reconnect to use this integration.`)) return;
    setBusyId(id);
    try {
      await ptApi.delete(`/api/integrations/${id}`);
      toast.success(`${id} disconnected`);
      refresh();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Disconnect failed');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="mb-6" data-testid="pt-integ-oauth-section">
      <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-[#7C35DC] mb-2">OAuth integrations</div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {OAUTH_PROVIDERS.map(p => {
          const cur = statuses[p.id];
          const connected = cur?.status === 'connected';
          return (
            <div key={p.id} className="border border-[#E2E8F0] rounded-xl p-4 bg-white" data-testid={`pt-integ-oauth-card-${p.id}`}>
              <div className="flex items-center justify-between gap-2 mb-1">
                <div className="font-semibold text-sm text-[#0F172A]">{p.label}</div>
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
                  style={{ background: connected ? '#DCFCE7' : '#F1F5F9', color: connected ? '#15803D' : '#64748B' }}>
                  {connected ? 'Connected' : 'Not connected'}
                </span>
              </div>
              <p className="text-xs text-[#64748B] mb-3">{p.desc}</p>
              {connected && cur?.last_sync && (
                <div className="text-[10px] text-[#64748B] mb-2">Last sync: {fmtDateTime(cur.last_sync)}</div>
              )}
              <div className="flex gap-2">
                {!connected && (
                  <button
                    onClick={() => connect(p.id)}
                    disabled={busyId === p.id}
                    data-testid={`pt-integ-oauth-connect-${p.id}`}
                    className="px-3 py-1.5 bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white text-xs font-semibold rounded-lg">
                    {busyId === p.id ? 'Opening…' : 'Connect'}
                  </button>
                )}
                {connected && (
                  <button
                    onClick={() => disconnect(p.id)}
                    disabled={busyId === p.id}
                    data-testid={`pt-integ-oauth-disconnect-${p.id}`}
                    className="px-3 py-1.5 border border-[#E2E8F0] hover:bg-slate-50 disabled:opacity-50 text-slate-700 text-xs font-semibold rounded-lg">
                    Disconnect
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};


const PtIntegrations = () => {
  const [primary, setPrimary] = useState([]);
  const [future, setFuture] = useState([]);
  const [loading, setLoading] = useState(true);
  const base = process.env.REACT_APP_BACKEND_URL;

  const load = async () => {
    setLoading(true);
    try {
      const r = await ptApi.get('/api/pt/integrations');
      setPrimary(r.data.primary || []);
      setFuture(r.data.future || []);
    }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const save = async (name, body) => {
    try { await ptApi.post('/api/pt/integrations', { name, ...body }); load(); toast.success('Saved'); }
    catch (err) { toast.error(err.response?.data?.detail || 'Could not save'); }
  };

  const test = async (name) => {
    try {
      const r = await ptApi.post(`/api/pt/integrations/${name}/test`);
      load();
      toast.success(r.data?.message || 'Connection verified');
    }
    catch (err) {
      const detail = err.response?.data?.detail || 'Test failed';
      toast.error(detail, { duration: 8000 });
    }
  };

  const copy = (txt) => { navigator.clipboard.writeText(txt); toast.success('Copied'); };

  return (
    <div data-testid="pt-integrations-page">
      <PageHeader title="Integrations" subtitle="Saleshandy and Lemlist are the two primary platforms for the Pietential demo. Everything else is future / optional." />

      {loading ? (
        <div className="text-sm text-[#64748B]">Loading…</div>
      ) : (
        <>
          {/* iter106 — OAuth integrations (Calendly / Gmail / Outlook / Meta / LinkedIn / Google Ads) */}
          <OAuthIntegrations />

          <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-[#7C35DC] mb-2" data-testid="pt-integ-primary-heading">Primary platforms</div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-6">
            {primary.map(r => (
              <IntegrationCard key={r.name} integ={r} base={base} hints={WEBHOOK_HINTS[r.name] || []} onSave={save} onTest={test} onCopy={copy} />
            ))}
          </div>

          <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-[#94A3B8] mb-2" data-testid="pt-integ-future-heading">Future / optional integrations</div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {future.map(r => (
              <IntegrationCard key={r.name} integ={r} base={base} hints={WEBHOOK_HINTS[r.name] || []} onSave={save} onTest={test} onCopy={copy} compact />
            ))}
          </div>

          <PtIntegrationsExtras />
        </>
      )}
    </div>
  );
};

const IntegrationCard = ({ integ, base, hints, onSave, onTest, onCopy, compact }) => {
  const sm = STATUS_META[integ.status] || STATUS_META.not_connected;
  const [apiKey, setApiKey] = useState('');
  const [webhookSecret, setWebhookSecret] = useState('');
  const [webhookUrl, setWebhookUrl] = useState(integ.webhook_url || '');

  return (
    <div className="bg-white border border-[#E2E8F0] rounded-lg p-4" data-testid={`pt-integ-${integ.name}`}>
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-md flex items-center justify-center" style={{ background: `${sm.color}14`, color: sm.color }}>
            <Plugs size={14} weight="duotone" />
          </div>
          <div>
            <div className="text-sm font-bold text-[#0F172A]">{PRETTY[integ.name] || integ.name}</div>
            <div className="text-[10px] uppercase tracking-[0.14em] font-bold" style={{ color: sm.color }}>{sm.label}</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => onTest(integ.name)} data-testid={`pt-integ-test-${integ.name}`}
            className="text-xs font-semibold text-[#7C35DC] hover:underline inline-flex items-center gap-1"><ArrowClockwise size={11} /> Test</button>
          {!compact && integ.api_key_masked && (
            <button onClick={async () => {
              try { const r = await ptApi.post(`/api/pt/integrations/${integ.name}/sync`); toast.success(r.data.message || 'Sync queued'); }
              catch (err) { toast.error(err.response?.data?.detail || 'Sync failed'); }
            }} data-testid={`pt-integ-sync-${integ.name}`}
              className="text-xs font-semibold text-white px-2 py-0.5 rounded-md inline-flex items-center gap-1" style={{ background: '#7C35DC' }}>
              Sync now
            </button>
          )}
        </div>
      </div>

      <div className="space-y-2.5">
        <div>
          <label className="block text-[10px] font-bold uppercase tracking-[0.16em] text-[#64748B] mb-1">API key {integ.api_key_masked && <span className="text-[#94A3B8] normal-case ml-1">· current: {integ.api_key_masked}</span>}</label>
          <div className="flex items-center gap-1.5">
            <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder={integ.api_key_masked ? 'Replace key…' : 'Paste API key'}
              data-testid={`pt-integ-key-${integ.name}`}
              className="flex-1 text-sm border border-[#E2E8F0] rounded-md px-2 py-1.5 outline-none" />
            <button onClick={() => apiKey && onSave(integ.name, { api_key: apiKey, status: 'connected' })} disabled={!apiKey}
              data-testid={`pt-integ-save-${integ.name}`}
              className="text-xs font-semibold text-white px-3 py-1.5 rounded-md disabled:opacity-50" style={{ background: '#7C35DC' }}>Save</button>
          </div>
        </div>

        {!compact && (
          <>
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-[0.16em] text-[#64748B] mb-1">
                Webhook secret {integ.webhook_secret_set && <span className="text-[#16A34A] normal-case ml-1">· set</span>}
              </label>
              <div className="flex items-center gap-1.5">
                <input type="password" value={webhookSecret} onChange={(e) => setWebhookSecret(e.target.value)}
                  placeholder={integ.webhook_secret_set ? 'Replace secret…' : 'Optional — verify X-Pt-Webhook-Secret header'}
                  data-testid={`pt-integ-secret-${integ.name}`}
                  className="flex-1 text-sm border border-[#E2E8F0] rounded-md px-2 py-1.5 outline-none" />
                <button onClick={() => webhookSecret && onSave(integ.name, { webhook_secret: webhookSecret })} disabled={!webhookSecret}
                  className="text-xs font-semibold text-[#7C35DC] border border-[#7C35DC]/30 px-3 py-1.5 rounded-md disabled:opacity-50">Save</button>
              </div>
            </div>

            <div>
              <label className="block text-[10px] font-bold uppercase tracking-[0.16em] text-[#64748B] mb-1">Outgoing webhook URL (optional)</label>
              <input value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)} placeholder="https://hooks.zapier.com/…"
                onBlur={() => webhookUrl !== integ.webhook_url && onSave(integ.name, { webhook_url: webhookUrl })}
                className="w-full text-sm border border-[#E2E8F0] rounded-md px-2 py-1.5 outline-none" />
            </div>

            {hints.length > 0 && (
              <div className="pt-2 border-t border-[#F1F5F9]">
                <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#64748B] mb-1">Inbound webhook endpoints</div>
                <div className="space-y-1">
                  {hints.map(h => (
                    <div key={h} className="flex items-center justify-between gap-2 bg-[#F8FAFC] rounded px-2 py-1 text-xs text-[#475569] font-mono">
                      <span className="truncate">{base}{h}</span>
                      <button onClick={() => onCopy(`${base}${h}`)} className="text-[#7C35DC]"><Copy size={11} weight="bold" /></button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {integ.last_sync_at && (
          <div className="text-[10px] text-[#64748B]">Last sync: {fmtDateTime(integ.last_sync_at)}</div>
        )}
      </div>
    </div>
  );
};

export default PtIntegrations;
