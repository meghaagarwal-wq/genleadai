import React, { useEffect, useState } from 'react';
import api from '../config/api';
import { toast } from 'sonner';
import {
  Database, Plug, CheckCircle, X, ArrowRight, ArrowsClockwise,
  Lightning, LinkSimple, ListChecks, Warning, GearSix, TestTube, Copy,
} from '@phosphor-icons/react';

// CRMs metadata
const CRMS = [
  { id: 'hubspot', name: 'HubSpot', auth: 'oauth', color: '#FF7A59', description: 'Lead/deal sync via HubSpot CRM v3 API' },
  { id: 'pipedrive', name: 'Pipedrive', auth: 'api_key', color: '#1F8DDD', description: 'API-key based, fastest setup' },
  { id: 'zoho', name: 'Zoho CRM', auth: 'oauth', color: '#D43E1F', description: 'Zoho CRM v2 OAuth integration' },
  { id: 'salesforce', name: 'Salesforce', auth: 'oauth', color: '#00A1E0', description: 'Salesforce REST API via OAuth 2' },
  { id: 'custom_webhook', name: 'Custom Webhook', auth: 'webhook', color: '#7C35DC', description: 'Push every event to any URL as JSON' },
];

const EVENT_GROUPS = [
  { label: 'Lead lifecycle', events: ['lead.created', 'lead.stage_changed', 'lead.qualified', 'lead.assigned', 'lead.closed_won', 'lead.closed_lost', 'lead.re_engaged', 'lead.data_deleted'] },
  { label: 'Aria activity', events: ['aria.paused', 'aria.resumed', 'conversation.takeover', 'touchpoint.sent'] },
  { label: 'Signals', events: ['meeting.booked', 'sentiment.negative', 'sentiment.urgent'] },
];

const STATUS_BADGE = {
  success: { cls: 'bg-[#DCFCE7] text-[#16A34A] border-[#16A34A]/30', label: 'Success' },
  pending: { cls: 'bg-[#FEF3C7] text-[#D97706] border-[#D97706]/30', label: 'Pending' },
  retrying: { cls: 'bg-[#FEF3C7] text-[#D97706] border-[#D97706]/30', label: 'Retrying' },
  failed: { cls: 'bg-[#FEE2E2] text-[#DC2626] border-[#DC2626]/30', label: 'Failed' },
};

const fmtDate = (iso) => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }); } catch { return '—'; }
};

// ─── Connect flow (modal-style inline panel) ─────────────────────────────────
const ConnectPanel = ({ selectedCrm, onConnected, onCancel }) => {
  const [apiKey, setApiKey] = useState('');
  const [apiDomain, setApiDomain] = useState('');
  const [webhookUrl, setWebhookUrl] = useState('');
  const [busy, setBusy] = useState(false);
  const meta = CRMS.find((c) => c.id === selectedCrm);

  const connect = async () => {
    setBusy(true);
    try {
      const body = { crm_type: selectedCrm };
      if (meta.auth === 'api_key') { body.api_key = apiKey; if (apiDomain) body.api_domain = apiDomain; }
      if (meta.auth === 'webhook') body.webhook_url = webhookUrl;
      if (meta.auth === 'oauth') body.api_key = apiKey; // paste-in token in placeholder mode
      const r = await api.post('/api/crm/connect', body);
      toast.success(`Connected to ${meta.name}`);
      onConnected(r.data?.integration);
    } catch (e) { toast.error(e.response?.data?.detail || 'Connect failed'); }
    finally { setBusy(false); }
  };

  const openOAuth = async () => {
    try {
      const r = await api.get(`/api/crm/oauth/${selectedCrm}/start`);
      if (r.data?.placeholder) {
        toast.warning(`${meta.name} OAuth client ID is not configured yet. Paste a temporary access token below for testing.`);
      } else {
        window.open(r.data?.url, '_blank');
      }
    } catch (e) { toast.error('Could not get OAuth URL'); }
  };

  return (
    <div className="bg-white border border-[#E8E0F5] rounded-xl p-5" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="crm-connect-panel">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: `${meta.color}15` }}>
            <Database size={20} weight="fill" style={{ color: meta.color }} />
          </div>
          <div>
            <h3 className="font-extrabold text-[#1A0A2E] text-base" style={{ fontFamily: 'Plus Jakarta Sans' }}>Connect {meta.name}</h3>
            <p className="text-xs text-[#5A4A7A]">{meta.description}</p>
          </div>
        </div>
        <button onClick={onCancel} data-testid="connect-cancel"><X size={18} className="text-[#9B8AB0]" /></button>
      </div>

      {meta.auth === 'oauth' && (
        <div className="space-y-3">
          <button onClick={openOAuth} data-testid="oauth-start-btn" className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-bold text-white" style={{ background: meta.color }}>
            <LinkSimple size={14} weight="bold" /> Authorize {meta.name}
          </button>
          <div className="text-center text-[10px] uppercase tracking-[0.2em] font-bold text-[#9B8AB0]">— or paste a personal access token —</div>
          <input
            data-testid="oauth-paste-token"
            type="password"
            placeholder={`Paste ${meta.name} access token (test mode)`}
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            className="w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-2 rounded-lg text-sm font-mono"
          />
        </div>
      )}

      {meta.auth === 'api_key' && (
        <div className="space-y-3">
          <div>
            <label className="text-xs font-bold uppercase tracking-[0.15em] text-[#5A4A7A]">API Token</label>
            <input data-testid="apikey-input" type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} className="mt-1 w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-2 rounded-lg text-sm font-mono" />
            <p className="text-[10px] text-[#9B8AB0] mt-1">Find your token at Pipedrive → Settings → Personal preferences → API.</p>
          </div>
          <div>
            <label className="text-xs font-bold uppercase tracking-[0.15em] text-[#5A4A7A]">Domain (optional)</label>
            <input data-testid="apidomain-input" value={apiDomain} onChange={(e) => setApiDomain(e.target.value)} placeholder="https://yourcompany.pipedrive.com" className="mt-1 w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-2 rounded-lg text-sm" />
          </div>
        </div>
      )}

      {meta.auth === 'webhook' && (
        <div>
          <label className="text-xs font-bold uppercase tracking-[0.15em] text-[#5A4A7A]">Webhook URL</label>
          <input data-testid="webhookurl-input" value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)} placeholder="https://your-endpoint.example.com/aria-webhook" className="mt-1 w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-2 rounded-lg text-sm font-mono" />
          <p className="text-[10px] text-[#9B8AB0] mt-1">Aria POSTs JSON with the event type, lead snapshot, and event data.</p>
        </div>
      )}

      <div className="flex items-center justify-end gap-2 mt-5">
        <button onClick={onCancel} className="px-4 py-2 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-lg text-sm font-medium">Cancel</button>
        <button data-testid="crm-connect-submit" onClick={connect} disabled={busy} className="px-5 py-2 btn-gradient rounded-lg text-sm font-bold disabled:opacity-40" style={{ fontFamily: 'Plus Jakarta Sans' }}>
          {busy ? 'Connecting…' : 'Connect'}
        </button>
      </div>
    </div>
  );
};

// ─── Field mapping editor ───────────────────────────────────────────────────
const FieldMappingEditor = ({ integration, onSaved }) => {
  const [mapping, setMapping] = useState({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get('/api/crm/field-mapping').then((r) => setMapping(r.data?.field_mapping || {}));
  }, [integration?.id]);

  const save = async () => {
    setBusy(true);
    try {
      await api.put('/api/crm/field-mapping', { field_mapping: mapping });
      toast.success('Mapping saved'); onSaved && onSaved();
    } catch (e) { toast.error(e.response?.data?.detail || 'Save failed'); }
    finally { setBusy(false); }
  };

  return (
    <div className="bg-white border border-[#E8E0F5] rounded-xl" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="field-mapping">
      <div className="px-5 py-4 border-b border-[#E8E0F5] flex items-center justify-between">
        <div>
          <h3 className="font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Field mapping</h3>
          <p className="text-xs text-[#9B8AB0]">Aria field → {CRMS.find((c) => c.id === integration.crm_type)?.name} field</p>
        </div>
        <button data-testid="mapping-save" onClick={save} disabled={busy} className="px-4 py-1.5 btn-gradient rounded-lg text-xs font-bold disabled:opacity-40" style={{ fontFamily: 'Plus Jakarta Sans' }}>
          {busy ? 'Saving…' : 'Save mapping'}
        </button>
      </div>
      <div className="divide-y divide-[#F0ECF9]">
        {Object.entries(mapping).map(([aria, crm]) => (
          <div key={aria} className="grid grid-cols-2 gap-4 px-5 py-2.5 items-center" data-testid={`map-row-${aria}`}>
            <div className="text-sm font-mono text-[#1A0A2E] font-semibold">{aria}</div>
            <div className="flex items-center gap-2">
              <ArrowRight size={12} className="text-[#9B8AB0]" />
              <input
                data-testid={`map-input-${aria}`}
                value={crm}
                onChange={(e) => setMapping({ ...mapping, [aria]: e.target.value })}
                className="flex-1 bg-white border border-[#E8E0F5] text-[#5A4A7A] px-2 py-1.5 rounded-md text-sm font-mono"
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

// ─── Sync rules ──────────────────────────────────────────────────────────────
const SyncRulesEditor = ({ integration, onSaved }) => {
  const [rules, setRules] = useState(integration.sync_rules || {});
  const [busy, setBusy] = useState(false);

  const toggle = (evt) => setRules({ ...rules, [evt]: !rules[evt] });
  const save = async () => {
    setBusy(true);
    try {
      await api.put('/api/crm/sync-rules', { sync_rules: rules });
      toast.success('Sync rules saved'); onSaved && onSaved();
    } catch (e) { toast.error(e.response?.data?.detail || 'Save failed'); }
    finally { setBusy(false); }
  };

  return (
    <div className="bg-white border border-[#E8E0F5] rounded-xl" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="sync-rules">
      <div className="px-5 py-4 border-b border-[#E8E0F5] flex items-center justify-between">
        <div>
          <h3 className="font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Sync rules</h3>
          <p className="text-xs text-[#9B8AB0]">Toggle which Aria events get pushed to the CRM.</p>
        </div>
        <button data-testid="rules-save" onClick={save} disabled={busy} className="px-4 py-1.5 btn-gradient rounded-lg text-xs font-bold disabled:opacity-40" style={{ fontFamily: 'Plus Jakarta Sans' }}>
          {busy ? 'Saving…' : 'Save rules'}
        </button>
      </div>
      <div className="p-5 space-y-4">
        {EVENT_GROUPS.map((group) => (
          <div key={group.label}>
            <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#9B8AB0] mb-2">{group.label}</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {group.events.map((evt) => (
                <label key={evt} className="flex items-center gap-2.5 px-3 py-2 rounded-lg border border-[#E8E0F5] hover:border-[#7C35DC]/40 cursor-pointer" data-testid={`rule-${evt}`}>
                  <input type="checkbox" checked={rules[evt] !== false} onChange={() => toggle(evt)} className="w-4 h-4 accent-[#7C35DC]" />
                  <span className="text-sm font-mono text-[#1A0A2E]">{evt}</span>
                </label>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

// ─── Sync log ────────────────────────────────────────────────────────────────
const SyncLog = ({ refreshTick, onRefresh }) => {
  const [data, setData] = useState({ entries: [], total: 0 });
  const [filter, setFilter] = useState({ status: '' });

  const load = () => {
    const params = filter.status ? { status: filter.status } : {};
    api.get('/api/crm/sync-log', { params }).then((r) => setData(r.data));
  };
  useEffect(load, [filter, refreshTick]);

  const retry = async (id) => {
    try { await api.post(`/api/crm/sync-log/${id}/retry`); toast.success('Queued for retry'); load(); }
    catch (e) { toast.error(e.response?.data?.detail || 'Retry failed'); }
  };
  const retryAll = async () => {
    try { const r = await api.post('/api/crm/sync-log/retry-all-failed'); toast.success(`${r.data.retried} entries queued`); load(); onRefresh && onRefresh(); }
    catch (e) { toast.error(e.response?.data?.detail || 'Retry-all failed'); }
  };

  return (
    <div className="bg-white border border-[#E8E0F5] rounded-xl" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="sync-log">
      <div className="px-5 py-4 border-b border-[#E8E0F5] flex items-center justify-between flex-wrap gap-2">
        <div>
          <h3 className="font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Sync log <span className="text-[#9B8AB0] font-normal text-sm ml-1.5">({data.total})</span></h3>
          <p className="text-xs text-[#9B8AB0]">Latest CRM sync events. Failed entries can be retried.</p>
        </div>
        <div className="flex items-center gap-2">
          <select data-testid="log-filter-status" value={filter.status} onChange={(e) => setFilter({ status: e.target.value })} className="bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-1.5 rounded-lg text-sm">
            <option value="">All</option>
            <option value="pending">Pending</option>
            <option value="success">Success</option>
            <option value="failed">Failed</option>
            <option value="retrying">Retrying</option>
          </select>
          <button data-testid="retry-all-btn" onClick={retryAll} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-[#7C35DC]/30 text-[#7C35DC] rounded-lg text-xs font-bold hover:bg-[#F4F0FF]">
            <ArrowsClockwise size={12} weight="bold" /> Retry failed
          </button>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[#F4F0FF]">
            <tr>
              {['Time', 'Event', 'Lead', 'Status', 'Retries', 'Error', 'Action'].map((h) => (
                <th key={h} className="px-5 py-2.5 text-left text-[10px] font-bold uppercase tracking-[0.15em] text-[#5A4A7A]">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.entries.length === 0 ? (
              <tr><td colSpan={7} className="px-5 py-10 text-center text-[#9B8AB0]">No sync events yet</td></tr>
            ) : data.entries.map((e) => {
              const meta = STATUS_BADGE[e.status] || STATUS_BADGE.pending;
              return (
                <tr key={e.id} className="border-b border-[#F0ECF9] hover:bg-[#FAF7FF]" data-testid={`log-row-${e.id}`}>
                  <td className="px-5 py-2.5 text-[#5A4A7A] text-xs">{fmtDate(e.created_at)}</td>
                  <td className="px-5 py-2.5"><span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded bg-[#F4F0FF] text-[#7C35DC] border border-[#7C35DC]/20 font-mono">{e.event_type}</span></td>
                  <td className="px-5 py-2.5 text-[#5A4A7A] text-xs">{(e.lead_snapshot?.name || e.lead_id || '—').slice(0, 24)}</td>
                  <td className="px-5 py-2.5"><span className={`px-2 py-0.5 text-[10px] font-bold uppercase rounded border ${meta.cls}`}>{meta.label}</span></td>
                  <td className="px-5 py-2.5 text-[#5A4A7A] text-xs font-mono">{e.retry_count || 0}</td>
                  <td className="px-5 py-2.5 text-[#DC2626] text-[11px] max-w-[260px] truncate font-mono">{e.error_message || '—'}</td>
                  <td className="px-5 py-2.5">
                    {(e.status === 'failed' || e.status === 'retrying') && (
                      <button onClick={() => retry(e.id)} data-testid={`retry-${e.id}`} className="text-xs font-bold text-[#7C35DC] hover:underline">Retry</button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// ─── Top-level CRM tab ───────────────────────────────────────────────────────
const CrmSettingsTab = () => {
  const [integration, setIntegration] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selecting, setSelecting] = useState(null); // crm id being connected
  const [section, setSection] = useState('setup'); // setup | log
  const [refreshTick, setRefreshTick] = useState(0);

  const load = async () => {
    setLoading(true);
    try { const r = await api.get('/api/crm/integrations'); setIntegration(r.data?.integration); }
    catch { /* */ }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const disconnect = async () => {
    if (!window.confirm('Disconnect CRM? Aria will stop syncing events.')) return;
    try { await api.delete('/api/crm/disconnect'); toast.success('Disconnected'); setIntegration(null); }
    catch (e) { toast.error(e.response?.data?.detail || 'Disconnect failed'); }
  };

  const testConnection = async () => {
    try {
      const r = await api.post('/api/crm/test-connection');
      toast.success(r.data?.message || 'Connection OK');
      setRefreshTick((t) => t + 1);
    } catch (e) { toast.error(e.response?.data?.detail || 'Test failed'); }
  };

  if (loading) return <div className="text-sm text-[#9B8AB0]" data-testid="crm-loading">Loading…</div>;

  // ── No integration yet → CRM picker
  if (!integration) {
    return (
      <div className="space-y-5" data-testid="crm-empty-state">
        <div className="bg-[#F4F0FF] border border-[#E0D4F7] rounded-xl px-5 py-4 flex items-start gap-3">
          <Lightning size={20} weight="fill" className="text-[#7C35DC] mt-0.5" />
          <div className="text-sm text-[#5A4A7A]">
            <span className="font-bold text-[#1A0A2E]">Aria is the engagement layer. Your CRM is the system of record.</span><br />
            Connect one CRM to keep Aria's pipeline mirrored in HubSpot, Pipedrive, Zoho or Salesforce — every stage change, takeover, and meeting booked syncs automatically.
          </div>
        </div>

        {selecting ? (
          <ConnectPanel selectedCrm={selecting} onConnected={(i) => { setIntegration(i); setSelecting(null); }} onCancel={() => setSelecting(null)} />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="crm-picker">
            {CRMS.map((c) => (
              <button key={c.id} onClick={() => setSelecting(c.id)} data-testid={`crm-card-${c.id}`}
                className="bg-white border border-[#E8E0F5] hover:border-[#7C35DC]/40 rounded-xl p-5 text-left transition-all hover:shadow-md group">
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-11 h-11 rounded-xl flex items-center justify-center" style={{ background: `${c.color}15` }}>
                    <Database size={22} weight="fill" style={{ color: c.color }} />
                  </div>
                  <div>
                    <h3 className="font-bold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{c.name}</h3>
                    <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-[#9B8AB0]">{c.auth === 'oauth' ? 'OAuth' : c.auth === 'api_key' ? 'API Key' : 'Webhook'}</p>
                  </div>
                </div>
                <p className="text-xs text-[#5A4A7A]">{c.description}</p>
                <div className="mt-3 text-xs font-bold text-[#7C35DC] inline-flex items-center gap-1 group-hover:gap-1.5 transition-all">
                  Connect <ArrowRight size={12} weight="bold" />
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  const meta = CRMS.find((c) => c.id === integration.crm_type);

  // ── Connected → show status + sub-tabs
  return (
    <div className="space-y-5" data-testid="crm-connected-state">
      <div className="bg-white border border-[#E8E0F5] rounded-xl p-5 flex items-center justify-between flex-wrap gap-3" style={{ boxShadow: 'var(--shadow-card)' }}>
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ background: `${meta?.color || '#7C35DC'}15` }}>
            <Database size={24} weight="fill" style={{ color: meta?.color || '#7C35DC' }} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-extrabold text-[#1A0A2E] text-lg" style={{ fontFamily: 'Plus Jakarta Sans' }}>{meta?.name}</h3>
              <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider rounded bg-[#DCFCE7] text-[#16A34A] border border-[#16A34A]/30">
                <CheckCircle size={10} weight="fill" /> Connected
              </span>
            </div>
            <p className="text-xs text-[#9B8AB0]">{integration.account_email} · last sync {fmtDate(integration.last_sync_at)}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button data-testid="test-connection-btn" onClick={testConnection} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-[#7C35DC]/30 text-[#7C35DC] rounded-lg text-xs font-bold hover:bg-[#F4F0FF]">
            <TestTube size={12} weight="fill" /> Test connection
          </button>
          <button data-testid="disconnect-btn" onClick={disconnect} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-[#DC2626]/30 text-[#DC2626] rounded-lg text-xs font-bold hover:bg-[#FEE2E2]">
            <X size={12} weight="bold" /> Disconnect
          </button>
        </div>
      </div>

      <div className="flex gap-1 border-b border-[#E8E0F5]" data-testid="crm-subtabs">
        {[
          { id: 'setup', label: 'Field mapping & rules', icon: GearSix },
          { id: 'log', label: 'Sync log', icon: ListChecks },
        ].map((t) => {
          const Icon = t.icon;
          const isActive = section === t.id;
          return (
            <button key={t.id} onClick={() => setSection(t.id)} data-testid={`crm-subtab-${t.id}`}
              className={`flex items-center gap-2 px-4 py-2 text-sm font-semibold border-b-2 transition-all ${isActive ? 'border-[#7C35DC] text-[#7C35DC] bg-[#F4F0FF]' : 'border-transparent text-[#5A4A7A] hover:text-[#7C35DC]'}`}>
              <Icon size={14} weight="duotone" /> {t.label}
            </button>
          );
        })}
      </div>

      {section === 'setup' && (
        <div className="space-y-5">
          <FieldMappingEditor integration={integration} onSaved={load} />
          <SyncRulesEditor integration={integration} onSaved={load} />
        </div>
      )}
      {section === 'log' && <SyncLog refreshTick={refreshTick} onRefresh={() => setRefreshTick((t) => t + 1)} />}
    </div>
  );
};

export default CrmSettingsTab;
