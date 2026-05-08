import { useEffect, useState } from 'react';
import { Plugs, Check, X, ArrowClockwise, Copy } from '@phosphor-icons/react';
import { toast } from 'sonner';
import { ptApi, PageHeader, fmtDateTime } from '../shared';

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

const PtIntegrations = () => {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const base = process.env.REACT_APP_BACKEND_URL;

  const load = async () => {
    setLoading(true);
    try { const r = await ptApi.get('/api/pt/integrations'); setRows(r.data.integrations || []); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const save = async (name, body) => {
    try { await ptApi.post('/api/pt/integrations', { name, ...body }); load(); toast.success('Saved'); }
    catch (err) { toast.error(err.response?.data?.detail || 'Could not save'); }
  };

  const test = async (name) => {
    try { await ptApi.post(`/api/pt/integrations/${name}/test`); load(); toast.success('Marked as connected'); }
    catch (err) { toast.error(err.response?.data?.detail || 'Test failed'); }
  };

  const copy = (txt) => { navigator.clipboard.writeText(txt); toast.success('Copied'); };

  return (
    <div data-testid="pt-integrations-page">
      <PageHeader title="Integrations" subtitle="Connect Saleshandy, Lemlist, newsletter, lead magnet forms, Calendly, GA4 and more." />

      {loading ? (
        <div className="text-sm text-[#64748B]">Loading…</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {rows.map(r => (
            <IntegrationCard
              key={r.name} integ={r} base={base}
              hints={WEBHOOK_HINTS[r.name] || []}
              onSave={save} onTest={test} onCopy={copy}
            />
          ))}
        </div>
      )}
    </div>
  );
};

const IntegrationCard = ({ integ, base, hints, onSave, onTest, onCopy }) => {
  const sm = STATUS_META[integ.status] || STATUS_META.not_connected;
  const [apiKey, setApiKey] = useState('');
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
        <div className="flex items-center gap-1">
          <button onClick={() => onTest(integ.name)} data-testid={`pt-integ-test-${integ.name}`}
            className="text-xs font-semibold text-[#7C35DC] hover:underline inline-flex items-center gap-1"><ArrowClockwise size={11} /> Test</button>
        </div>
      </div>

      <div className="space-y-2.5">
        <div>
          <label className="block text-[10px] font-bold uppercase tracking-[0.16em] text-[#64748B] mb-1">API key</label>
          <div className="flex items-center gap-1.5">
            <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder={integ.status === 'connected' ? '•••• already saved ••••' : 'Paste API key'}
              data-testid={`pt-integ-key-${integ.name}`}
              className="flex-1 text-sm border border-[#E2E8F0] rounded-md px-2 py-1.5 outline-none" />
            <button onClick={() => apiKey && onSave(integ.name, { api_key: apiKey, status: 'connected' })} disabled={!apiKey}
              data-testid={`pt-integ-save-${integ.name}`}
              className="text-xs font-semibold text-white px-3 py-1.5 rounded-md disabled:opacity-50" style={{ background: '#7C35DC' }}>Save</button>
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

        {integ.last_sync_at && (
          <div className="text-[10px] text-[#64748B]">Last sync: {fmtDateTime(integ.last_sync_at)}</div>
        )}
      </div>
    </div>
  );
};

export default PtIntegrations;
