/**
 * Integrations — /integrations
 *
 * Unified hub for all third-party connectors:
 *   - Analytics: GA4 (Measurement Protocol), Meta CAPI
 *   - Automation: Zapier, Make.com
 *   - Lead sources (inbound webhooks): Typeform, Instantly.ai, Google Ads Lead Form, Apollo.io
 *
 * Each card opens a config modal where the owner pastes credentials.
 */
import React, { useEffect, useMemo, useState } from 'react';
import api from '../config/api';
import { toast } from 'sonner';
import AriaSpotlight from '../components/AriaSpotlight';
import {
  ChartLineUp, Lightning, Globe, Plug, CheckCircle, Warning, Copy, X,
  LinkSimple, ArrowsClockwise, TestTube, BookOpen,
} from '@phosphor-icons/react';

const CATEGORY_META = {
  analytics: { label: 'Analytics', color: '#0055FF', icon: ChartLineUp },
  automation: { label: 'Automation', color: '#D97706', icon: Lightning },
  lead_source: { label: 'Lead Sources', color: '#16A34A', icon: Globe },
  outreach: { label: 'Outreach', color: '#7C35DC', icon: Plug },
};

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
};

const Integrations = () => {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState(null); // selected integration row
  const [category, setCategory] = useState('all');

  const load = async () => {
    setLoading(true);
    try { const r = await api.get('/api/integrations/list'); setItems(r.data?.integrations || []); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const filtered = useMemo(() => category === 'all' ? items : items.filter((i) => i.category === category), [items, category]);

  return (
    <div className="space-y-5 max-w-[1300px] mx-auto" data-testid="integrations-hub-page">
      <AriaSpotlight
        id="integrations-whatsapp-v1"
        anchorSelector='[data-testid="cat-all"]'
        placement="bottom"
        title="Connect your channels"
        body="Pick a category to see the integrations Aria can plug into. Start with WhatsApp or your website form — that's where most leads come from."
      />
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC] mb-1">One layer to rule them all</div>
          <h1 className="text-3xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Integration Hub</h1>
          <p className="text-sm text-[#5A4A7A] mt-1">Connect Aria to your ad platforms, automation tools, and lead sources.</p>
        </div>
      </div>

      {/* Category pills */}
      <div className="flex items-center gap-2 flex-wrap" data-testid="category-filter">
        {[
          { key: 'all', label: 'All', color: '#7C35DC' },
          ...Object.entries(CATEGORY_META).map(([k, v]) => ({ key: k, label: v.label, color: v.color })),
        ].map((c) => (
          <button key={c.key} onClick={() => setCategory(c.key)} data-testid={`cat-${c.key}`}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold border ${category === c.key ? 'text-white' : 'bg-white text-[#5A4A7A] border-[#E8E0F5] hover:bg-[#F9F5FF]'}`}
            style={category === c.key ? { background: c.color, borderColor: c.color } : {}}>
            {c.label}
          </button>
        ))}
      </div>

      {/* Cards grid */}
      {loading ? (
        <div className="text-center py-12 text-sm text-[#9B8AB0]">Loading integrations…</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {filtered.map((it) => {
            const meta = INTEGRATION_META[it.type] || { name: it.label, blurb: '' };
            const cm = CATEGORY_META[it.category] || CATEGORY_META.analytics;
            const Icon = cm.icon;
            const connected = it.status === 'connected';
            return (
              <button key={it.type} onClick={() => setModal(it)} data-testid={`integration-${it.type}`}
                className="text-left bg-white border border-[#E8E0F5] hover:border-[#7C35DC]/40 rounded-xl p-4 transition-all group"
                style={{ boxShadow: 'var(--shadow-card)' }}>
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: cm.color + '15' }}>
                      <Icon size={16} weight="duotone" style={{ color: cm.color }} />
                    </div>
                    <div>
                      <div className="text-sm font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{meta.name}</div>
                      <div className="text-[9px] font-bold uppercase tracking-wider" style={{ color: cm.color }}>{cm.label}</div>
                    </div>
                  </div>
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold border ${connected ? 'bg-[#DCFCE7] text-[#16A34A] border-[#16A34A]/30' : 'bg-[#F1F5F9] text-[#5A4A7A] border-[#CBD5E1]/30'}`} data-testid={`status-${it.type}`}>
                    {connected ? <><CheckCircle size={10} weight="fill" /> Connected</> : 'Not connected'}
                  </span>
                </div>
                <p className="text-xs text-[#5A4A7A] line-clamp-3 leading-relaxed">{meta.blurb}</p>
                {it.error_message && <p className="mt-2 text-[10px] font-mono text-[#DC2626] truncate"><Warning size={10} weight="fill" className="inline" /> {it.error_message}</p>}
              </button>
            );
          })}
        </div>
      )}

      {modal && <ConfigModal item={modal} onClose={() => setModal(null)} onSaved={() => { setModal(null); load(); }} />}
    </div>
  );
};

// ──────────────────────────────────────────────────────────────────────────
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
    catch (e) { toast.error('Failed'); }
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
    } catch (e) { toast.error('Import failed'); }
    finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4" data-testid="integration-config-modal">
      <div className="bg-white border border-[#E8E0F5] rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        <div className="flex items-start justify-between p-5 border-b border-[#E8E0F5]">
          <div>
            <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#7C35DC]">{(CATEGORY_META[item.category] || {}).label}</div>
            <h3 className="text-lg font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{meta.name}</h3>
            <p className="text-xs text-[#5A4A7A] mt-1 max-w-md">{meta.blurb}</p>
          </div>
          <button onClick={onClose} data-testid="modal-close" className="text-[#9B8AB0] hover:text-[#1A0A2E]"><X size={20} /></button>
        </div>

        <div className="p-5 overflow-y-auto flex-1 space-y-4">
          {/* Inbound webhook URL */}
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

          {/* Apollo bulk import */}
          {meta.apolloImport && (
            <div className="p-4 rounded-xl border border-[#E8E0F5] bg-[#FAFAFA]" data-testid="apollo-import-block">
              <div className="text-[10px] font-bold uppercase tracking-wider text-[#9B8AB0] mb-2">Paste Apollo leads JSON array</div>
              <textarea rows={6} value={apolloRaw} onChange={(e) => setApolloRaw(e.target.value)} data-testid="apollo-json"
                placeholder='[{"first_name":"Jane","email":"jane@acme.com","phone":"+1...","company":"Acme"}]'
                className="w-full font-mono text-[11px] bg-white border border-[#E8E0F5] px-3 py-2 rounded-md mt-1 resize-y" />
              <button onClick={runApolloImport} disabled={busy || !apolloRaw} data-testid="apollo-import-btn"
                className="mt-3 inline-flex items-center gap-1.5 px-3 py-2 btn-gradient rounded-lg text-xs font-bold disabled:opacity-40"
                style={{ fontFamily: 'Plus Jakarta Sans' }}>
                <ArrowsClockwise size={12} weight="bold" className={busy ? 'animate-spin' : ''} /> Import
              </button>
            </div>
          )}

          {/* Config fields */}
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

          {/* Test result */}
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
                className="px-4 py-2 btn-gradient rounded-lg text-xs font-bold disabled:opacity-40"
                style={{ fontFamily: 'Plus Jakarta Sans' }}>
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
