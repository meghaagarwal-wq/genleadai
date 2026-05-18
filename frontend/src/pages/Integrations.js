/**
 * Integration Hub — /integrations
 *
 * The single source-of-truth for all third-party connectors.
 * Reads `/api/integrations/catalog` to merge live + coming-soon entries.
 *
 * Page sections (top → bottom):
 *   1. Header + Connect/Request CTAs
 *   2. Stat cards
 *   3. Setup progress bar + stepper
 *   4. Category tabs + integration cards (live = Connect/Manage, coming-soon = Join Waitlist)
 *   5. Data flow preview
 *   6. Send Test Lead block
 *   7. Integration health table
 *   8. Custom integration request form
 *
 * Connect/manage modal for live integrations preserved from the previous design.
 */
import React, { useEffect, useMemo, useState } from 'react';
import api from '../config/api';
import { toast } from 'sonner';
import {
  ChartLineUp, Lightning, Globe, Plug, CheckCircle, Warning, Copy, X,
  LinkSimple, ArrowsClockwise, TestTube, BookOpen, Sparkle, ArrowRight,
  Users, Database, CalendarBlank, ChatCircle, Buildings,
} from '@phosphor-icons/react';
import {
  HubStatCards, SetupProgress, DataFlowPreview, IntegrationHealthTable, SendTestLeadButton,
} from '../components/integrations/HubSections';
import { WaitlistModal, CustomRequestForm } from '../components/integrations/WaitlistAndRequest';

// ────────────────────────────────────────────────────────────────────────────
//  Per-integration metadata for the LIVE connectors. Drives the ConfigModal.
//  (Identical to the previous Integrations.js — preserved verbatim.)
// ────────────────────────────────────────────────────────────────────────────
const INTEGRATION_META = {
  ga4: {
    name: 'Google Analytics 4',
    blurb: 'Fire server-side events for every Aria lead lifecycle: created · qualified · meeting · won.',
    fields: [
      { key: 'measurement_id', label: 'Measurement ID', placeholder: 'G-XXXXXXXXXX', required: true },
      { key: 'api_secret', label: 'API Secret', placeholder: 'Your Measurement Protocol secret', required: true, secret: true },
    ],
    docs: 'https://developers.google.com/analytics/devguides/collection/protocol/ga4',
  },
  meta_capi: {
    name: 'Meta Conversions API',
    blurb: 'Server-side pixel events for Lead, Schedule, CompleteRegistration. Boost campaign signal post-iOS 14.5.',
    fields: [
      { key: 'pixel_id', label: 'Pixel ID', placeholder: '123456789012345', required: true },
      { key: 'access_token', label: 'CAPI Access Token', placeholder: 'EAAxxxx...', required: true, secret: true },
      { key: 'test_event_code', label: 'Test event code (optional)', placeholder: 'TEST12345' },
    ],
    docs: 'https://developers.facebook.com/docs/marketing-api/conversions-api',
  },
  zapier: {
    name: 'Zapier',
    blurb: 'Send every Aria event to a Zap. Create a "Catch Hook" Zap, paste the URL below.',
    fields: [{ key: 'webhook_url', label: 'Zapier Hook URL', placeholder: 'https://hooks.zapier.com/...', required: true }],
    docs: 'https://zapier.com/help/create/code-webhooks/trigger-zaps-from-webhooks',
  },
  make: {
    name: 'Make.com',
    blurb: 'Same as Zapier — pipe Aria events into any Make scenario.',
    fields: [{ key: 'webhook_url', label: 'Make Hook URL', placeholder: 'https://hook.eu1.make.com/...', required: true }],
    docs: 'https://www.make.com/en/help/tools/webhooks',
  },
  typeform: {
    name: 'Typeform',
    blurb: 'Auto-create leads from Typeform submissions. Each form: webhook → POST → endpoint below.',
    inbound: true,
    webhook_path: '/api/integrations/typeform/webhook/{tenant_id}',
    docs: 'https://developer.typeform.com/webhooks/',
  },
  instantly: {
    name: 'Instantly.ai',
    blurb: 'When a prospect replies to an Instantly campaign, auto-create the lead in Aria for WhatsApp follow-up.',
    inbound: true,
    webhook_path: '/api/integrations/instantly/webhook/{tenant_id}',
    docs: 'https://developer.instantly.ai/',
  },
  google_ads: {
    name: 'Google Ads Lead Form',
    blurb: 'Paste this URL + key into Google Ads → Lead Form → Webhook integration.',
    inbound: true,
    webhook_path: '/api/integrations/google-ads/webhook/{tenant_id}',
    docs: 'https://support.google.com/google-ads/answer/9023460',
  },
  apollo: {
    name: 'Apollo.io',
    blurb: 'Bulk import leads from an Apollo.io export. Paste an array of leads, Aria de-dupes + starts touchpoints.',
    inbound: true,
    fields: [{ key: 'apollo_workspace', label: 'Apollo workspace (note only)', placeholder: 'apollo-team-name' }],
    apolloImport: true,
    docs: 'https://docs.apollo.io/reference',
  },
  saleshandy: {
    name: 'Saleshandy',
    blurb: 'When a Saleshandy prospect opens, clicks, or replies positively, the lead lands in Aria and the sequence auto-pauses on a hot reply.',
    inbound: true,
    webhook_path: '/api/integrations/saleshandy/webhook/{tenant_id}',
    fields: [
      { key: 'api_key', label: 'Saleshandy API Key', placeholder: 'Paste your Saleshandy Open API key', required: true, secret: true },
      { key: 'default_sequence_id', label: 'Default Sequence ID (optional)', placeholder: 'e.g. 6512a...  — used by Aria to auto-pause when a lead replies' },
      { key: 'webhook_secret', label: 'Webhook signing secret (optional)', placeholder: 'Aria verifies HMAC-SHA256 if you set one', secret: true },
    ],
    docs: 'https://open-api.saleshandy.com/docs',
  },
  lemlist: {
    name: 'Lemlist',
    blurb: 'Capture every Lemlist reply + LinkedIn connection acceptance as a lead in Aria. Aria pauses the campaign automatically when a prospect goes hot.',
    inbound: true,
    webhook_path: '/api/integrations/lemlist/webhook/{tenant_id}',
    fields: [
      { key: 'api_key', label: 'Lemlist API Key', placeholder: 'Paste your Lemlist API key', required: true, secret: true },
      { key: 'default_campaign_id', label: 'Default Campaign ID (optional)', placeholder: 'e.g. cam_abc...' },
      { key: 'webhook_secret', label: 'Webhook signing secret (optional)', placeholder: 'Aria verifies HMAC-SHA256 if you set one', secret: true },
    ],
    docs: 'https://developer.lemlist.com/',
  },
};

// ────────────────────────────────────────────────────────────────────────────
//  Category visual treatment
// ────────────────────────────────────────────────────────────────────────────
const CATEGORY_ICONS = {
  lead_source: Globe, outreach: Plug, crm: Database,
  communication: ChatCircle, booking: CalendarBlank, analytics: ChartLineUp,
  automation: Lightning,
};

// ────────────────────────────────────────────────────────────────────────────
//  Page
// ────────────────────────────────────────────────────────────────────────────
const Integrations = () => {
  const [catalog, setCatalog] = useState(null);
  const [health, setHealth] = useState({ healthy_percent: 100, healthy: 0, total: 0, rows: [] });
  const [loading, setLoading] = useState(true);
  const [category, setCategory] = useState('all');
  const [modal, setModal] = useState(null);
  const [waitlist, setWaitlist] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const [c, h] = await Promise.all([
        api.get('/api/integrations/catalog'),
        api.get('/api/integrations/health').catch(() => ({ data: { healthy_percent: 100, healthy: 0, total: 0, rows: [] } })),
      ]);
      setCatalog(c.data);
      setHealth(h.data);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const allItems = catalog?.integrations || [];
  const filtered = useMemo(() => {
    if (category === 'all') return allItems;
    return allItems.filter((i) => i.category === category);
  }, [allItems, category]);

  return (
    <div className="space-y-6 max-w-[1300px] mx-auto pb-12" data-testid="integrations-hub-page">
      {/* 1. Header */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC] mb-1">One layer to rule them all</div>
          <h1 className="text-3xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Integration Hub</h1>
          <p className="text-sm text-[#5A4A7A] mt-1 max-w-2xl">
            Connect every lead source. Let Aria handle the follow-up. Bring your forms, ads, outbound tools, CRM, WhatsApp, calendar, and analytics into one AI-led sales workspace — Aria reads every signal, scores every lead, and tells you who needs attention.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <a href="#category-tabs" data-testid="hub-connect-cta" className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-600 text-white text-xs font-bold uppercase tracking-wider hover:bg-violet-700">
            <Plug size={14} weight="bold" /> Connect new integration
          </a>
          <a href="#custom-request-form" data-testid="hub-request-cta" className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-200 bg-white text-slate-700 text-xs font-bold uppercase tracking-wider hover:bg-slate-50">
            <Sparkle size={14} weight="duotone" /> Request custom
          </a>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-12 text-sm text-[#9B8AB0]">Loading hub…</div>
      ) : (
        <>
          {/* 2. Stat cards */}
          <HubStatCards integrations={allItems} health={health} />

          {/* 3. Setup progress */}
          <SetupProgress />

          {/* 4. Category tabs + cards */}
          <section data-testid="category-section" id="category-tabs">
            <div className="flex items-center gap-2 flex-wrap mb-4" data-testid="category-filter">
              <CategoryPill active={category === 'all'} onClick={() => setCategory('all')} label="All" tint="#7C35DC" count={allItems.length} testId="cat-all" />
              {(catalog?.categories || []).map((c) => {
                const count = allItems.filter((i) => i.category === c.key).length;
                return (
                  <CategoryPill
                    key={c.key}
                    active={category === c.key}
                    onClick={() => setCategory(c.key)}
                    label={c.label}
                    tint={c.color}
                    count={count}
                    testId={`cat-${c.key}`}
                  />
                );
              })}
            </div>

            {category !== 'all' && (
              <CategoryBlurb cat={(catalog?.categories || []).find((x) => x.key === category)} />
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {filtered.map((it) => (
                <IntegrationCard
                  key={`${it.type}-${it.live ? 'live' : 'soon'}`}
                  item={it}
                  onOpen={() => it.live ? setModal(it) : setWaitlist(it)}
                />
              ))}
            </div>
          </section>

          {/* 5. Data flow preview */}
          <DataFlowPreview />

          {/* 6. Test lead */}
          <SendTestLeadButton />

          {/* 7. Health monitor */}
          <IntegrationHealthTable />

          {/* 8. Custom integration request */}
          <div id="custom-request-form">
            <CustomRequestForm />
          </div>
        </>
      )}

      {modal && <ConfigModal item={modal} onClose={() => setModal(null)} onSaved={() => { setModal(null); load(); }} />}
      {waitlist && <WaitlistModal integration={waitlist} onClose={() => setWaitlist(null)} onJoined={load} />}
    </div>
  );
};

function CategoryPill({ active, onClick, label, tint, count, testId }) {
  return (
    <button
      onClick={onClick}
      data-testid={testId}
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold border transition-colors ${
        active ? 'text-white' : 'bg-white text-[#5A4A7A] border-[#E8E0F5] hover:bg-[#F9F5FF]'
      }`}
      style={active ? { background: tint, borderColor: tint } : {}}
    >
      {label}
      <span className={`text-[10px] font-extrabold px-1.5 py-0.5 rounded-full ${
        active ? 'bg-white/25 text-white' : 'bg-slate-100 text-slate-500'
      }`}>{count}</span>
    </button>
  );
}

function CategoryBlurb({ cat }) {
  if (!cat) return null;
  return (
    <div className="mb-4 p-3 rounded-xl border-l-4 bg-slate-50" style={{ borderColor: cat.color }} data-testid={`cat-blurb-${cat.key}`}>
      <p className="text-xs text-slate-700 leading-relaxed"><b className="text-slate-900">{cat.label}.</b> {cat.blurb}</p>
    </div>
  );
}

function IntegrationCard({ item, onOpen }) {
  const meta = INTEGRATION_META[item.type] || {};
  const Icon = CATEGORY_ICONS[item.category] || Plug;
  const isLive = !!item.live;
  const connected = item.status === 'connected';
  const waitlisted = item.status === 'waitlist_joined';

  return (
    <button
      onClick={onOpen}
      data-testid={`integration-${item.type}`}
      className="text-left bg-white border border-[#E8E0F5] hover:border-violet-300 rounded-xl p-4 transition-all group relative overflow-hidden"
      style={{ boxShadow: 'var(--shadow-card)' }}
    >
      {!isLive && (
        <div className="absolute top-0 right-0 px-2 py-0.5 text-[9px] font-extrabold uppercase tracking-wider bg-gradient-to-r from-violet-500 to-fuchsia-500 text-white rounded-bl-lg">
          Coming Soon
        </div>
      )}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-9 h-9 rounded-lg flex items-center justify-center bg-violet-50 text-violet-600">
            <Icon size={16} weight="duotone" />
          </div>
          <div>
            <div className="text-sm font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{meta.name || item.label}</div>
            <div className="text-[9px] font-bold uppercase tracking-wider text-slate-400">{(item.category || '').replace('_', ' ')}</div>
          </div>
        </div>
        <StatusBadge connected={connected} waitlisted={waitlisted} live={isLive} testId={`status-${item.type}`} />
      </div>
      <p className="text-xs text-[#5A4A7A] leading-relaxed line-clamp-3">{meta.blurb || item.use_case}</p>
      {item.last_sync_at && (
        <p className="text-[10px] text-slate-400 mt-2">Last sync: {relative(item.last_sync_at)}</p>
      )}
      {item.error_message && (
        <p className="mt-2 text-[10px] font-mono text-rose-600 truncate"><Warning size={10} weight="fill" className="inline" /> {item.error_message}</p>
      )}
      <div className="mt-3 flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-wider font-bold text-violet-600 inline-flex items-center gap-1">
          {!isLive ? (waitlisted ? 'You\'re on the list' : 'Join waitlist') :
            connected ? 'Manage' :
            (meta.fields?.length || meta.webhook_path || meta.apolloImport) ? 'Connect' : 'Open'}
          <ArrowRight size={11} weight="bold" />
        </span>
      </div>
    </button>
  );
}

function StatusBadge({ connected, waitlisted, live, testId }) {
  if (connected) {
    return (
      <span data-testid={testId} className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold border bg-emerald-50 text-emerald-700 border-emerald-200">
        <CheckCircle size={10} weight="fill" /> Connected
      </span>
    );
  }
  if (!live) {
    return (
      <span data-testid={testId} className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold border ${
        waitlisted ? 'bg-violet-50 text-violet-700 border-violet-200' : 'bg-slate-50 text-slate-600 border-slate-200'
      }`}>
        {waitlisted ? 'Waitlisted' : 'Soon'}
      </span>
    );
  }
  return (
    <span data-testid={testId} className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold border bg-slate-50 text-slate-600 border-slate-200">
      Not connected
    </span>
  );
}

function relative(iso) {
  try {
    const d = new Date(iso);
    const sec = Math.round((Date.now() - d.getTime()) / 1000);
    if (sec < 60) return `${sec}s ago`;
    if (sec < 3600) return `${Math.round(sec / 60)} min ago`;
    if (sec < 86400) return `${Math.round(sec / 3600)} hr ago`;
    return `${Math.round(sec / 86400)} d ago`;
  } catch { return iso; }
}

// ────────────────────────────────────────────────────────────────────────────
//  ConfigModal — preserved from previous design (handles live connectors only)
// ────────────────────────────────────────────────────────────────────────────
const ConfigModal = ({ item, onClose, onSaved }) => {
  const meta = INTEGRATION_META[item.type] || { name: item.label };
  const [form, setForm] = useState({});
  const [busy, setBusy] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [copied, setCopied] = useState(false);
  const [apolloRaw, setApolloRaw] = useState('');

  const backendUrl = process.env.REACT_APP_BACKEND_URL || '';
  const tenantId = item.config?.tenant_id || (window.localStorage.getItem('active_tenant_id') || '');
  const webhookFull = meta.webhook_path ? `${backendUrl}${meta.webhook_path}`.replace('{tenant_id}', tenantId || '<your-tenant-id>') : '';

  const save = async () => {
    setBusy(true);
    try {
      await api.post(`/api/integrations/${item.type}/connect`, { config: form, status: 'connected' });
      toast.success(`${meta.name} connected`);
      onSaved();
    } catch (e) { toast.error(e.response?.data?.detail || 'Save failed'); }
    finally { setBusy(false); }
  };
  const disconnect = async () => {
    if (!window.confirm(`Disconnect ${meta.name}?`)) return;
    setBusy(true);
    try { await api.delete(`/api/integrations/${item.type}/disconnect`); toast.success('Disconnected'); onSaved(); }
    catch { toast.error('Failed'); }
    finally { setBusy(false); }
  };
  const test = async () => {
    setBusy(true); setTestResult(null);
    try { const r = await api.post(`/api/integrations/${item.type}/test`); setTestResult(r.data); }
    catch (e) { setTestResult({ ok: false, message: e.response?.data?.detail || 'Test failed' }); }
    finally { setBusy(false); }
  };
  const copy = async (txt) => {
    try { await navigator.clipboard.writeText(txt); setCopied(true); setTimeout(() => setCopied(false), 1500); toast.success('Copied'); } catch { /* ignore */ }
  };
  const runApolloImport = async () => {
    let parsed;
    try { parsed = JSON.parse(apolloRaw); } catch { toast.error('Invalid JSON'); return; }
    if (!Array.isArray(parsed)) { toast.error('Must be a JSON array'); return; }
    setBusy(true);
    try {
      const r = await api.post('/api/integrations/apollo/import', { tenant_id: tenantId, leads: parsed });
      toast.success(`Imported ${r.data.imported}, deduped ${r.data.deduplicated}, failed ${r.data.failed}`);
    } catch { toast.error('Import failed'); }
    finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4" data-testid="integration-config-modal">
      <div className="bg-white border border-[#E8E0F5] rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        <div className="flex items-start justify-between p-5 border-b border-[#E8E0F5]">
          <div>
            <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#7C35DC]">{(item.category || '').replace('_', ' ')}</div>
            <h3 className="text-lg font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{meta.name}</h3>
            <p className="text-xs text-[#5A4A7A] mt-1 max-w-md">{meta.blurb}</p>
          </div>
          <button onClick={onClose} data-testid="modal-close" className="text-[#9B8AB0] hover:text-[#1A0A2E]"><X size={20} /></button>
        </div>

        <div className="p-5 overflow-y-auto flex-1 space-y-4">
          {meta.webhook_path && (
            <div className="p-4 rounded-xl bg-[#F4F0FF] border border-[#E0D4F7]" data-testid="webhook-url-card">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-[#7C35DC]"><LinkSimple size={11} weight="bold" className="inline" /> Webhook URL</span>
                <button onClick={() => copy(webhookFull)} data-testid="copy-webhook" className="text-[10px] font-bold text-[#7C35DC] hover:text-[#6B28C8] inline-flex items-center gap-1">{copied ? <><CheckCircle size={10} weight="fill" /> Copied</> : <><Copy size={10} /> Copy</>}</button>
              </div>
              <code className="text-[11px] font-mono text-[#1A0A2E] break-all">{webhookFull}</code>
              <p className="text-[10px] text-[#5A4A7A] mt-2">Paste this URL into {meta.name} as your webhook endpoint. Submissions will create leads in Aria.</p>
            </div>
          )}

          {meta.apolloImport && (
            <div className="p-4 rounded-xl border border-[#E8E0F5] bg-[#FAFAFA]" data-testid="apollo-import-block">
              <div className="text-[10px] font-bold uppercase tracking-wider text-[#9B8AB0] mb-2">Paste Apollo leads JSON array</div>
              <textarea rows={6} value={apolloRaw} onChange={(e) => setApolloRaw(e.target.value)} data-testid="apollo-json"
                placeholder='[{"first_name":"Jane","email":"jane@acme.com","phone":"+1...","company":"Acme"}]'
                className="w-full font-mono text-[11px] bg-white border border-[#E8E0F5] px-3 py-2 rounded-md mt-1 resize-y" />
              <button onClick={runApolloImport} disabled={busy || !apolloRaw} data-testid="apollo-import-btn"
                className="mt-3 inline-flex items-center gap-1.5 px-3 py-2 bg-violet-600 text-white rounded-lg text-xs font-bold disabled:opacity-40">
                <ArrowsClockwise size={12} weight="bold" className={busy ? 'animate-spin' : ''} /> Import
              </button>
            </div>
          )}

          {(meta.fields || []).map((f) => (
            <div key={f.key}>
              <label className="text-[10px] font-bold uppercase tracking-wider text-[#9B8AB0]">{f.label}{f.required && <span className="text-[#DC2626]">*</span>}</label>
              <input
                type={f.secret ? 'password' : 'text'}
                value={form[f.key] || ''}
                onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
                placeholder={f.placeholder || ''}
                data-testid={`field-${f.key}`}
                className="w-full bg-white border border-[#E8E0F5] px-3 py-2 rounded-md text-sm mt-1 font-mono"
              />
              {item.config && item.config[f.key] && (
                <p className="text-[10px] text-[#9B8AB0] mt-1">Current: <code className="font-mono">{item.config[f.key]}</code></p>
              )}
            </div>
          ))}

          {testResult && (
            <div className={`p-3 rounded-lg border text-xs ${testResult.ok ? 'bg-[#DCFCE7] border-[#16A34A]/30 text-[#16A34A]' : 'bg-[#FEE2E2] border-[#DC2626]/30 text-[#DC2626]'}`} data-testid="test-result">
              <strong>{testResult.ok ? '✓ ' : '✗ '}</strong>{testResult.message}
            </div>
          )}

          {meta.docs && (
            <a href={meta.docs} target="_blank" rel="noreferrer" className="text-[11px] font-bold text-[#7C35DC] hover:text-[#6B28C8] inline-flex items-center gap-1">
              <BookOpen size={11} weight="bold" /> {meta.name} documentation
            </a>
          )}
        </div>

        {!meta.apolloImport && (
          <div className="p-4 border-t border-[#E8E0F5] flex items-center justify-end gap-2">
            {item.status === 'connected' && (
              <>
                <button onClick={disconnect} disabled={busy} data-testid="disconnect-btn" className="px-3 py-2 bg-white border border-[#DC2626]/30 text-[#DC2626] rounded-lg text-xs font-bold hover:bg-[#FEE2E2] disabled:opacity-40">Disconnect</button>
                <button onClick={test} disabled={busy} data-testid="test-btn" className="inline-flex items-center gap-1 px-3 py-2 bg-white border border-[#7C35DC]/30 text-[#7C35DC] rounded-lg text-xs font-bold hover:bg-[#F4F0FF] disabled:opacity-40">
                  <TestTube size={11} weight="bold" /> Test event
                </button>
              </>
            )}
            {(meta.fields || []).length > 0 && (
              <button onClick={save} disabled={busy} data-testid="save-integration"
                className="px-4 py-2 bg-violet-600 text-white rounded-lg text-xs font-bold disabled:opacity-40">
                {busy ? 'Saving…' : item.status === 'connected' ? 'Update' : 'Connect'}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default Integrations;
