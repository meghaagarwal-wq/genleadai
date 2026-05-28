/**
 * Integrations page — iter109c Batch 1 rebuild.
 *
 * Universal OAuth + API-key UX:
 *   • Provider registry comes from /app/frontend/src/config/integrations.js
 *   • Status comes from GET /api/integrations/{id}/status
 *   • OAuth flow: POST /configure → GET /auth-url → open popup → GET /callback
 *   • API-key flow: POST /configure-api-key (auto-marks as connected)
 *
 * Zero CLIENT_ID/CLIENT_SECRET ever sits in the .env — all per-workspace.
 */
import { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import {
  MagnifyingGlass, CheckCircle, Circle, Warning,
  Plug, ArrowSquareOut, X as XIcon, CircleNotch,
  Trash, Lightning, Eye, EyeSlash,
} from '@phosphor-icons/react';
import api from '../../config/api';
import { INTEGRATIONS, CATEGORIES, getIntegration } from '../../config/integrations';

const STATUS_TONE = {
  connected:     { color: '#22c55e', label: 'Connected',     dot: '●' },
  configured:    { color: '#f59e0b', label: 'Configured',    dot: '●' },
  not_connected: { color: '#94a3b8', label: 'Not connected', dot: '○' },
  error:         { color: '#ef4444', label: 'Error',         dot: '⚠' },
};


const IntegrationsPage = () => {
  const [statuses, setStatuses] = useState({});
  const [loading, setLoading] = useState(true);
  const [category, setCategory] = useState('all');
  const [query, setQuery] = useState('');
  const [activeProvider, setActiveProvider] = useState(null);  // open modal
  const [refreshCount, setRefreshCount] = useState(0);

  const refresh = async () => {
    setLoading(true);
    try {
      const results = await Promise.all(
        INTEGRATIONS.map((p) =>
          api.get(`/api/integrations/${p.id}/status`).then((r) => [p.id, r.data]).catch(() => [p.id, null])
        )
      );
      setStatuses(Object.fromEntries(results));
    } finally { setLoading(false); }
  };

  useEffect(() => { refresh(); }, [refreshCount]);

  // Detect ?connected=<provider> on return from OAuth callback
  useEffect(() => {
    const u = new URLSearchParams(window.location.search);
    const connected = u.get('connected');
    const errProvider = u.get('error');
    const reason = u.get('reason');
    if (connected) {
      const meta = getIntegration(connected);
      toast.success(`${meta?.name || connected} connected ✓`);
      // Clean URL
      window.history.replaceState({}, '', '/app/integrations');
      setRefreshCount((c) => c + 1);
    }
    if (errProvider) {
      const meta = getIntegration(errProvider);
      toast.error(`${meta?.name || errProvider} failed: ${reason || 'unknown'}`);
      window.history.replaceState({}, '', '/app/integrations');
    }
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return INTEGRATIONS.filter((p) => {
      if (category !== 'all' && p.category !== category) return false;
      if (q && !p.name.toLowerCase().includes(q) && !(p.services || []).some((s) => s.toLowerCase().includes(q))) return false;
      return true;
    });
  }, [category, query]);

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto" data-testid="integrations-page" style={{ color: 'var(--theme-text)' }}>
      <header className="mb-6">
        <h1 className="text-3xl font-extrabold mb-1" style={{ color: 'var(--theme-text)', fontFamily: 'Space Grotesk, Inter', letterSpacing: '-0.02em' }}>
          Integrations
        </h1>
        <p className="text-sm" style={{ color: 'var(--theme-text-muted)' }}>
          Connect your tools. Everything flows into ARIA automatically.
        </p>
      </header>

      {/* Category filter + search */}
      <div className="flex flex-col md:flex-row md:items-center gap-3 mb-5">
        <div className="flex flex-wrap gap-1.5" data-testid="integrations-category-tabs">
          {CATEGORIES.map((c) => (
            <button
              key={c.id}
              onClick={() => setCategory(c.id)}
              data-testid={`integrations-cat-${c.id}`}
              className="px-3 py-1.5 text-xs font-semibold rounded-md border transition-colors"
              style={{
                background: category === c.id ? 'var(--theme-purple-dim)' : 'var(--theme-surface)',
                borderColor: category === c.id ? 'var(--theme-purple)' : 'var(--theme-border-strong)',
                color: category === c.id ? 'var(--theme-purple-light)' : 'var(--theme-text-muted)',
              }}
            >{c.label}</button>
          ))}
        </div>
        <div className="relative ml-auto w-full md:w-64">
          <MagnifyingGlass size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--theme-text-muted)' }} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search integrations…"
            data-testid="integrations-search"
            className="w-full pl-8 pr-3 py-1.5 rounded-md text-sm outline-none border"
            style={{
              background: 'var(--theme-surface)',
              borderColor: 'var(--theme-border-strong)',
              color: 'var(--theme-text)',
            }}
          />
        </div>
      </div>

      {/* Cards grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3" data-testid="integrations-grid">
        {filtered.map((p) => (
          <IntegrationCard
            key={p.id}
            provider={p}
            status={statuses[p.id]}
            loading={loading}
            onConnect={() => setActiveProvider(p)}
            onDisconnect={async () => {
              if (!window.confirm(`Disconnect ${p.name}?`)) return;
              try {
                await api.delete(`/api/integrations/${p.id}`);
                toast.success(`${p.name} disconnected`);
                setRefreshCount((c) => c + 1);
              } catch (e) {
                toast.error(`Disconnect failed: ${e?.response?.data?.detail || e.message}`);
              }
            }}
            onTest={async () => {
              try {
                const { data } = await api.post(`/api/integrations/${p.id}/test`);
                toast[data.valid ? 'success' : 'error'](data.message || (data.valid ? 'OK' : 'Test failed'));
              } catch (e) {
                toast.error(`Test failed: ${e?.response?.data?.detail || e.message}`);
              }
            }}
          />
        ))}
        {filtered.length === 0 && (
          <div className="col-span-full text-center py-12 text-sm" style={{ color: 'var(--theme-text-muted)' }}>
            No integrations match.
          </div>
        )}
      </div>

      {activeProvider && (
        <ConnectModal
          provider={activeProvider}
          status={statuses[activeProvider.id]}
          onClose={() => setActiveProvider(null)}
          onComplete={() => { setActiveProvider(null); setRefreshCount((c) => c + 1); }}
        />
      )}
    </div>
  );
};


// ── IntegrationCard ─────────────────────────────────────────────────────
const IntegrationCard = ({ provider, status, loading, onConnect, onDisconnect, onTest }) => {
  const s = status || { status: 'not_connected' };
  const tone = STATUS_TONE[s.status] || STATUS_TONE.not_connected;
  const isConnected = s.status === 'connected';
  const isConfigured = s.status === 'configured';
  return (
    <div
      className="rounded-lg border p-4 flex flex-col"
      style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }}
      data-testid={`integration-card-${provider.id}`}
    >
      <div className="flex items-start gap-3 mb-2">
        <div className="w-10 h-10 rounded-md flex items-center justify-center text-base font-bold flex-shrink-0"
             style={{ background: 'var(--theme-surface2)', color: 'var(--theme-purple-light)' }}>
          {provider.name[0]}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <div className="text-sm font-bold truncate" style={{ color: 'var(--theme-text)' }}>{provider.name}</div>
            <span className="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded"
                  style={{ background: 'var(--theme-surface2)', color: 'var(--theme-text-muted)' }}>
              {provider.category}
            </span>
          </div>
          <div className="text-[11px] flex items-center gap-1.5" style={{ color: tone.color }}>
            <span>{tone.dot}</span>
            <span data-testid={`integration-status-${provider.id}`}>{tone.label}</span>
            {s.last_sync_at && <span style={{ color: 'var(--theme-text-muted)' }}>· last sync {formatRel(s.last_sync_at)}</span>}
          </div>
        </div>
      </div>
      <div className="text-[11px] mb-3 line-clamp-2 min-h-[28px]" style={{ color: 'var(--theme-text-muted)' }}>
        {(provider.services || []).join(' · ')}
      </div>
      {/* iter109c Batch 2 — audit footer on connected cards */}
      {s.connected && (
        <div className="text-[10px] mb-2 italic" style={{ color: 'var(--theme-text-dim)' }} data-testid={`integration-audit-${provider.id}`}>
          Connected by <strong style={{ color: 'var(--theme-text-muted)' }}>{s.connected_by_name || 'workspace owner'}</strong>
          {s.connected_at && <> · {formatRel(s.connected_at)}</>}
        </div>
      )}
      <div className="flex gap-1.5 mt-auto">
        {!isConnected && !isConfigured && (
          <button onClick={onConnect} data-testid={`integration-connect-${provider.id}`}
                  className="flex-1 px-3 py-1.5 rounded-md text-xs font-bold text-white"
                  style={{ background: 'var(--theme-purple)' }}>
            <Plug size={11} weight="bold" className="inline -mt-0.5 mr-1" /> Connect
          </button>
        )}
        {isConfigured && !isConnected && (
          <button onClick={onConnect} data-testid={`integration-resume-${provider.id}`}
                  className="flex-1 px-3 py-1.5 rounded-md text-xs font-bold text-white"
                  style={{ background: 'var(--theme-amber)' }}>
            Continue setup
          </button>
        )}
        {isConnected && (
          <>
            <button onClick={onTest} data-testid={`integration-test-${provider.id}`}
                    className="flex-1 px-3 py-1.5 rounded-md text-xs font-semibold border"
                    style={{ borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text)' }}>
              <Lightning size={11} weight="bold" className="inline -mt-0.5 mr-1" /> Test
            </button>
            <button onClick={onConnect} data-testid={`integration-settings-${provider.id}`}
                    className="px-3 py-1.5 rounded-md text-xs font-semibold border"
                    style={{ borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text-muted)' }}>
              Settings
            </button>
            <button onClick={onDisconnect} data-testid={`integration-disconnect-${provider.id}`}
                    className="px-2 py-1.5 rounded-md text-xs font-semibold border"
                    style={{ borderColor: 'var(--theme-border-strong)', color: '#ef4444' }}
                    aria-label="Disconnect">
              <Trash size={12} weight="bold" />
            </button>
          </>
        )}
      </div>
    </div>
  );
};


// Google-only scope picker — workspace owner can narrow which services they
// grant before authorizing.
const GOOGLE_SCOPE_GROUPS = [
  { id: 'gmail',    label: 'Gmail (read + send)',         scopes: ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.send'] },
  { id: 'calendar', label: 'Calendar + Meet (book calls)', scopes: ['https://www.googleapis.com/auth/calendar.events', 'https://www.googleapis.com/auth/calendar.readonly'] },
  { id: 'ads',      label: 'Google Ads (lead forms)',     scopes: ['https://www.googleapis.com/auth/adwords'] },
];


// ── ConnectModal — OAuth or API-key ─────────────────────────────────────
const ConnectModal = ({ provider, status, onClose, onComplete }) => {
  const [clientId, setClientId] = useState('');
  const [clientSecret, setClientSecret] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [extra, setExtra] = useState({});
  const [busy, setBusy] = useState(false);
  const [showSecret, setShowSecret] = useState(false);
  const [showWhy, setShowWhy] = useState(false);
  const [googleScopeOn, setGoogleScopeOn] = useState({ gmail: true, calendar: true, ads: true });
  const isOAuth = !!provider.oauth;
  const isGoogle = provider.id === 'google';

  const handleSubmit = async () => {
    setBusy(true);
    try {
      if (isOAuth) {
        if (!clientId || !clientSecret) {
          toast.error('Both CLIENT_ID and CLIENT_SECRET are required');
          setBusy(false); return;
        }
        // For Google: build the narrowed scope list from the toggles.
        let scopes;
        if (isGoogle) {
          scopes = GOOGLE_SCOPE_GROUPS
            .filter((g) => googleScopeOn[g.id])
            .flatMap((g) => g.scopes)
            .concat(['openid', 'email', 'profile']);
          if (scopes.length <= 3) {
            toast.error('Pick at least one Google service to connect.');
            setBusy(false); return;
          }
        }
        await api.post(`/api/integrations/${provider.id}/configure`, {
          client_id: clientId,
          client_secret: clientSecret,
          scopes,
        });
        const { data } = await api.get(`/api/integrations/${provider.id}/auth-url`);
        const w = window.open(data.auth_url, '_blank', 'width=560,height=720');
        if (!w) {
          toast.warning('Popup blocked — opening in this tab');
          window.location.href = data.auth_url;
          return;
        }
        const poll = setInterval(async () => {
          if (w.closed) {
            clearInterval(poll);
            onComplete();
          }
        }, 1000);
      } else {
        if (!apiKey) { toast.error('API key required'); setBusy(false); return; }
        await api.post(`/api/integrations/${provider.id}/configure-api-key`, {
          api_key: apiKey,
          extra_config: extra,
        });
        toast.success(`${provider.name} connected ✓`);
        onComplete();
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Connect failed');
    } finally { setBusy(false); }
  };

  const extraFields = (provider.requires || []).filter((f) => !['api_key', 'client_id', 'client_secret'].includes(f));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4"
         data-testid={`connect-modal-${provider.id}`}
         style={{ background: 'rgba(0,0,0,0.6)' }}>
      <div className="rounded-xl border w-full max-w-md p-5 relative"
           style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text)' }}>
        <button onClick={onClose} className="absolute top-3 right-3 p-1 rounded-md hover:bg-[var(--theme-surface2)]"
                aria-label="Close" data-testid="connect-modal-close">
          <XIcon size={16} style={{ color: 'var(--theme-text-muted)' }} />
        </button>
        <div className="flex items-center gap-3 mb-3">
          <div className="w-12 h-12 rounded-md flex items-center justify-center text-xl font-bold"
               style={{ background: 'var(--theme-surface2)', color: 'var(--theme-purple-light)' }}>
            {provider.name[0]}
          </div>
          <div>
            <h2 className="text-lg font-bold" style={{ color: 'var(--theme-text)' }}>{provider.name}</h2>
            <div className="text-[11px]" style={{ color: 'var(--theme-text-muted)' }}>{(provider.services || []).join(' · ')}</div>
          </div>
        </div>

        {/* What this unlocks */}
        {provider.what_this_unlocks && (
          <ul className="mb-4 space-y-1 text-xs" style={{ color: 'var(--theme-text-muted)' }}>
            {provider.what_this_unlocks.map((b, i) => (
              <li key={i} className="flex items-start gap-2">
                <span style={{ color: 'var(--theme-purple-light)' }}>•</span>
                <span>{b}</span>
              </li>
            ))}
          </ul>
        )}

        {/* Setup instructions + console link */}
        <div className="rounded-md p-2.5 mb-4 text-xs border"
             style={{ background: 'var(--theme-surface2)', borderColor: 'var(--theme-border)' }}>
          <div style={{ color: 'var(--theme-text-muted)' }}>{provider.setup_instructions}</div>
          {provider.console_url && (
            <a href={provider.console_url} target="_blank" rel="noopener noreferrer"
               className="inline-flex items-center gap-1 text-xs font-semibold mt-1.5"
               style={{ color: 'var(--theme-purple-light)' }}
               data-testid="connect-modal-console-link">
              Get my credentials <ArrowSquareOut size={11} weight="bold" />
            </a>
          )}
        </div>

        {/* Inputs */}
        {isOAuth ? (
          <>
            {isGoogle && (
              <div className="mb-4 p-3 rounded-md border" style={{ background: 'var(--theme-surface2)', borderColor: 'var(--theme-border)' }} data-testid="google-scope-picker">
                <div className="text-[10px] uppercase tracking-wider font-bold mb-2" style={{ color: 'var(--theme-text-muted)' }}>
                  Which Google services should ARIA connect?
                </div>
                {GOOGLE_SCOPE_GROUPS.map((g) => (
                  <label key={g.id} className="flex items-start gap-2 mb-1.5 text-xs cursor-pointer">
                    <input
                      type="checkbox"
                      checked={!!googleScopeOn[g.id]}
                      onChange={() => setGoogleScopeOn((s) => ({ ...s, [g.id]: !s[g.id] }))}
                      data-testid={`google-scope-${g.id}`}
                      className="mt-0.5 accent-violet-500"
                    />
                    <span style={{ color: 'var(--theme-text)' }}>{g.label}</span>
                  </label>
                ))}
              </div>
            )}
            <Field label="CLIENT_ID" value={clientId} onChange={setClientId} testId="connect-input-client-id" />
            <Field label="CLIENT_SECRET" value={clientSecret} onChange={setClientSecret}
                   type={showSecret ? 'text' : 'password'} testId="connect-input-client-secret"
                   rightSlot={
                     <button type="button" onClick={() => setShowSecret((v) => !v)}
                             className="text-[10px]" style={{ color: 'var(--theme-text-muted)' }}
                             aria-label={showSecret ? 'Hide secret' : 'Show secret'}>
                       {showSecret ? <EyeSlash size={14} /> : <Eye size={14} />}
                     </button>
                   } />
            <button onClick={() => setShowWhy((v) => !v)} className="text-[11px] mb-3" style={{ color: 'var(--theme-purple-light)' }}>
              Why do I need these? {showWhy ? '▴' : '▾'}
            </button>
            {showWhy && (
              <div className="text-xs mb-3 p-2.5 rounded-md" style={{ background: 'var(--theme-surface2)', color: 'var(--theme-text-muted)' }}>
                Your OAuth app's CLIENT_ID and CLIENT_SECRET let ARIA make authorized calls to {provider.name} on your behalf. They're encrypted at rest with Fernet and never leave your workspace.
              </div>
            )}
          </>
        ) : (
          <>
            <Field label="API key" value={apiKey} onChange={setApiKey}
                   type={showSecret ? 'text' : 'password'} testId="connect-input-api-key"
                   rightSlot={
                     <button type="button" onClick={() => setShowSecret((v) => !v)}
                             className="text-[10px]" style={{ color: 'var(--theme-text-muted)' }}>
                       {showSecret ? <EyeSlash size={14} /> : <Eye size={14} />}
                     </button>
                   } />
            {extraFields.map((f) => (
              <Field key={f} label={f.replace(/_/g, ' ')} value={extra[f] || ''} onChange={(v) => setExtra({ ...extra, [f]: v })}
                     testId={`connect-input-${f}`} />
            ))}
          </>
        )}

        <button onClick={handleSubmit} disabled={busy} data-testid="connect-modal-submit"
                className="w-full mt-3 px-4 py-2 rounded-md font-bold text-sm text-white disabled:opacity-50"
                style={{ background: 'var(--theme-purple)' }}>
          {busy ? <CircleNotch size={14} className="animate-spin inline -mt-0.5 mr-1" /> : null}
          {isOAuth ? (busy ? 'Opening OAuth…' : 'Save & Connect') : (busy ? 'Saving…' : 'Save credentials')}
        </button>
      </div>
    </div>
  );
};

const Field = ({ label, value, onChange, type = 'text', testId, rightSlot }) => (
  <label className="block mb-2.5">
    <span className="text-[10px] uppercase tracking-wider font-bold" style={{ color: 'var(--theme-text-muted)' }}>{label}</span>
    <div className="relative mt-1">
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        data-testid={testId}
        className="w-full px-3 py-2 rounded-md text-sm outline-none border"
        style={{
          background: 'var(--theme-surface2)',
          borderColor: 'var(--theme-border-strong)',
          color: 'var(--theme-text)',
          paddingRight: rightSlot ? '34px' : undefined,
          fontFamily: 'monospace',
        }}
      />
      {rightSlot && <span className="absolute right-2 top-1/2 -translate-y-1/2">{rightSlot}</span>}
    </div>
  </label>
);

const formatRel = (iso) => {
  try {
    const diff = (Date.now() - new Date(iso).getTime()) / 60000;
    if (diff < 1) return 'just now';
    if (diff < 60) return `${Math.floor(diff)} min ago`;
    if (diff < 1440) return `${Math.floor(diff / 60)}h ago`;
    return `${Math.floor(diff / 1440)}d ago`;
  } catch { return iso; }
};

export default IntegrationsPage;
