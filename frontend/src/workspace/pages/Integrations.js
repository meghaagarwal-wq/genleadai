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
import { INTEGRATIONS, getIntegration } from '../../config/integrations';

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
  const [showcase, setShowcase] = useState(null);  // iter161 — unified catalog

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

  // iter161 — fetch the full showcase catalog so we can render every
  // integration (connectable + roadmap) inside one unified grid.
  useEffect(() => {
    api.get('/api/dashboard/integration-showcase')
      .then((r) => setShowcase(r.data))
      .catch(() => setShowcase({ categories: [], integrations: [], counts: {} }));
  }, []);

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

  // iter161 — unified merge: showcase catalog augmented with live
  // connect state from INTEGRATIONS registry. Every item shares one
  // card style; only cards with a matching registry entry get action
  // buttons (Connect / Test / Settings / Disconnect).
  const providerById = useMemo(() => {
    const m = {};
    INTEGRATIONS.forEach((p) => { m[p.id] = p; });
    return m;
  }, []);

  const unified = useMemo(() => {
    if (!showcase) return [];
    const q = query.trim().toLowerCase();
    return showcase.integrations
      .map((row) => ({
        ...row,
        provider: providerById[row.id] || null,
        status: statuses[row.id] || null,
      }))
      .filter((row) => {
        if (category !== 'all' && !row.cats.includes(category)) return false;
        if (q) {
          const hay = `${row.label} ${row.cats.join(' ')} ${(row.provider?.services || []).join(' ')}`.toLowerCase();
          if (!hay.includes(q)) return false;
        }
        return true;
      });
  }, [showcase, query, category, statuses, providerById]);

  // Counts per category — recomputed from showcase so pills reflect
  // the union (registry + roadmap) not just the registry subset.
  const counts = useMemo(() => {
    if (!showcase) return { all: 0 };
    const c = { all: showcase.integrations.length };
    showcase.categories.forEach((cat) => {
      c[cat.key] = showcase.integrations.filter((r) => r.cats.includes(cat.key)).length;
    });
    return c;
  }, [showcase]);

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

      {/* Category pills + search (unified iter161) */}
      <div className="flex flex-col md:flex-row md:items-center gap-3 mb-5">
        <div className="flex flex-wrap gap-2" data-testid="integrations-category-tabs">
          <CategoryPill active={category === 'all'} onClick={() => setCategory('all')} label="All" count={counts.all} testid="integrations-cat-all" />
          {(showcase?.categories || []).map((c) => (
            <CategoryPill
              key={c.key}
              active={category === c.key}
              onClick={() => setCategory(c.key)}
              label={c.label}
              count={counts[c.key] || 0}
              color={c.color}
              testid={`integrations-cat-${c.key}`}
            />
          ))}
        </div>
        <div className="relative ml-auto w-full md:w-64">
          <MagnifyingGlass size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--theme-text-muted)' }} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search integrations…"
            data-testid="integrations-search"
            className="w-full pl-8 pr-3 py-1.5 rounded-full text-sm outline-none border"
            style={{
              background: 'var(--theme-surface)',
              borderColor: 'var(--theme-border-strong)',
              color: 'var(--theme-text)',
            }}
          />
        </div>
      </div>

      {/* Unified cards grid (iter161) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3" data-testid="integrations-grid">
        {unified.map((row) => (
          <UnifiedIntegrationCard
            key={row.id}
            row={row}
            loading={loading}
            onConnect={() => row.provider && setActiveProvider(row.provider)}
            onDisconnect={async () => {
              if (!row.provider) return;
              if (!window.confirm(`Disconnect ${row.provider.name}?`)) return;
              try {
                await api.delete(`/api/integrations/${row.provider.id}`);
                toast.success(`${row.provider.name} disconnected`);
                setRefreshCount((c) => c + 1);
              } catch (e) {
                toast.error(`Disconnect failed: ${e?.response?.data?.detail || e.message}`);
              }
            }}
            onTest={async () => {
              if (!row.provider) return;
              try {
                const { data } = await api.post(`/api/integrations/${row.provider.id}/test`);
                if (data.ok && data.warning) {
                  toast(data.message || 'Could not run a live test');
                } else if (data.ok) {
                  toast.success(data.message || `${row.provider.name} OK`);
                } else {
                  toast.error(data.message || 'Test failed');
                }
              } catch (e) {
                toast.error(`Test failed: ${e?.response?.data?.detail || e.message}`);
              }
            }}
          />
        ))}
        {unified.length === 0 && showcase && (
          <div className="col-span-full text-center py-12 text-sm" style={{ color: 'var(--theme-text-muted)' }}>
            No integrations match.
          </div>
        )}
        {!showcase && (
          <div className="col-span-full text-center py-12 text-sm" style={{ color: 'var(--theme-text-muted)' }}>
            Loading integrations…
          </div>
        )}
      </div>

      <div className="mt-6 text-[11px] text-center" style={{ color: 'var(--theme-text-muted)' }}>
        Don&apos;t see one you need? Request it via <strong style={{ color: 'var(--theme-purple-light)' }}>Settings → Integrations</strong>.
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


// ── CategoryPill (iter161 — unified rounded pill with count) ─────────────
const CategoryPill = ({ active, label, count, color = '#7C35DC', onClick, testid }) => (
  <button
    type="button"
    onClick={onClick}
    data-testid={testid}
    aria-pressed={active}
    className="px-3 py-1.5 rounded-full text-xs font-bold transition-all active:scale-95 focus:outline-none focus:ring-2 focus:ring-offset-1"
    style={{
      background: active ? color : 'var(--theme-surface2)',
      color: active ? '#fff' : 'var(--theme-text)',
      boxShadow: active ? `0 2px 12px ${color}66` : 'none',
      border: active ? 'none' : '1px solid var(--theme-border)',
    }}
  >
    {label} <span className="opacity-70 ml-1 tabular-nums">{count ?? ''}</span>
  </button>
);


// ── UnifiedIntegrationCard (iter161) ─────────────────────────────────────
// Single card style used for every integration:
//  • Colored initials avatar + name + category tag
//  • Status pill (Live / Available / Coming soon / Connected)
//  • If provider is in INTEGRATIONS registry, inline mini action buttons
//    (Connect / Test / Settings / Disconnect) — driven off real status
const STATUS_PILL = {
  live:         { bg: 'rgba(16,185,129,0.15)',  color: '#10B981', label: 'Live',        icon: '●' },
  connected:    { bg: 'rgba(16,185,129,0.15)',  color: '#10B981', label: 'Connected',   icon: '●' },
  configured:   { bg: 'rgba(245,158,11,0.15)',  color: '#F59E0B', label: 'Configured',  icon: '●' },
  available:    { bg: 'rgba(124,53,220,0.15)',  color: '#7C35DC', label: 'Available',   icon: '⚡' },
  coming_soon:  { bg: 'rgba(148,163,184,0.18)', color: '#94A3B8', label: 'Coming soon', icon: '✦' },
  error:        { bg: 'rgba(239,68,68,0.15)',   color: '#EF4444', label: 'Error',       icon: '⚠' },
  not_connected:{ bg: 'rgba(124,53,220,0.15)',  color: '#7C35DC', label: 'Available',   icon: '⚡' },
};

const UnifiedIntegrationCard = ({ row, loading, onConnect, onDisconnect, onTest }) => {
  const { provider, status: liveStatus } = row;

  // Determine effective status:
  // - If we have a real registry provider with liveStatus, use that (connected/configured/error/not_connected)
  // - Otherwise fall back to showcase status (live/available/coming_soon)
  const effective = provider && liveStatus?.status
    ? liveStatus.status
    : row.status;
  const pill = STATUS_PILL[effective] || STATUS_PILL.coming_soon;
  const isConnected = effective === 'connected' || effective === 'live';
  const isConfigured = effective === 'configured';
  const isConnectable = !!provider && effective !== 'coming_soon';

  const initials = row.label.split(/\s+/).slice(0, 2).map(w => w[0]).join('').toUpperCase();

  return (
    <div
      className="rounded-xl border p-3 flex flex-col gap-2.5 hover:-translate-y-0.5 hover:border-[var(--theme-purple-light)] transition-all"
      style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }}
      data-testid={`integration-card-${row.id}`}
      title={row.label}
    >
      {/* Top: avatar + name + status pill */}
      <div className="flex items-center gap-2.5">
        <div
          className="shrink-0 w-10 h-10 rounded-lg flex items-center justify-center text-xs font-extrabold text-white"
          style={{ background: row.brand, boxShadow: `0 4px 12px ${row.brand}55` }}
          aria-hidden="true"
        >
          {initials}
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-bold truncate" style={{ color: 'var(--theme-text)' }}>{row.label}</div>
          <span
            className="inline-flex items-center gap-1 mt-0.5 px-1.5 py-0.5 rounded-full text-[10px] font-bold"
            style={{ background: pill.bg, color: pill.color }}
            data-testid={`integration-status-${row.id}`}
          >
            <span>{pill.icon}</span> {pill.label}
          </span>
        </div>
      </div>

      {/* Services / category tags */}
      {provider?.services?.length ? (
        <div className="text-[10px] line-clamp-1" style={{ color: 'var(--theme-text-muted)' }}>
          {provider.services.slice(0, 4).join(' · ')}
        </div>
      ) : (
        <div className="text-[10px]" style={{ color: 'var(--theme-text-dim)' }}>
          {row.cats.slice(0, 3).map((c) => c[0].toUpperCase() + c.slice(1)).join(' · ')}
        </div>
      )}

      {/* Action row — only for cards with a real provider */}
      {isConnectable && (
        <div className="flex gap-1.5 mt-auto pt-1">
          {!isConnected && !isConfigured && (
            <button onClick={onConnect} data-testid={`integration-connect-${row.id}`}
                    disabled={loading}
                    className="flex-1 px-2 py-1.5 rounded-md text-[11px] font-bold text-white disabled:opacity-50"
                    style={{ background: 'var(--theme-purple)' }}>
              <Plug size={10} weight="bold" className="inline -mt-0.5 mr-1" /> Connect
            </button>
          )}
          {isConfigured && !isConnected && (
            <button onClick={onConnect} data-testid={`integration-resume-${row.id}`}
                    className="flex-1 px-2 py-1.5 rounded-md text-[11px] font-bold text-white"
                    style={{ background: 'var(--theme-amber, #F59E0B)' }}>
              Continue setup
            </button>
          )}
          {isConnected && (
            <>
              <button onClick={onTest} data-testid={`integration-test-${row.id}`}
                      className="flex-1 px-2 py-1.5 rounded-md text-[11px] font-semibold border"
                      style={{ borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text)' }}>
                <Lightning size={10} weight="bold" className="inline -mt-0.5 mr-1" /> Test
              </button>
              <button onClick={onConnect} data-testid={`integration-settings-${row.id}`}
                      className="px-2 py-1.5 rounded-md text-[11px] font-semibold border"
                      style={{ borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text-muted)' }}
                      aria-label="Settings">
                ⚙
              </button>
              <button onClick={onDisconnect} data-testid={`integration-disconnect-${row.id}`}
                      className="px-2 py-1.5 rounded-md text-[11px] font-semibold border"
                      style={{ borderColor: 'var(--theme-border-strong)', color: '#ef4444' }}
                      aria-label="Disconnect">
                <Trash size={10} weight="bold" />
              </button>
            </>
          )}
        </div>
      )}
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
  // iter124 — real-time API-key validation (onBlur).
  const [validating, setValidating] = useState(false);
  const [validation, setValidation] = useState(null); // null | { valid, message }
  const isOAuth = !!provider.oauth;
  const isGoogle = provider.id === 'google';

  const validateKey = async () => {
    if (!apiKey || !apiKey.trim()) { setValidation(null); return; }
    setValidating(true);
    setValidation(null);
    try {
      const { data } = await api.post(`/api/integrations/${provider.id}/validate-key`, {
        api_key: apiKey,
        extra_config: extra,
      });
      setValidation({ valid: !!data.valid, message: data.message || (data.valid ? 'Key valid' : 'Key invalid') });
    } catch (e) {
      // Backend may not yet have provider-specific /validate-key — fall back to /test on POST-save.
      // Surface as "couldn't verify" rather than blocking the user.
      setValidation({ valid: null, message: e?.response?.data?.detail || 'Could not verify key (will validate on Save).' });
    } finally { setValidating(false); }
  };

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
            <Field label="API key" value={apiKey} onChange={(v) => { setApiKey(v); setValidation(null); }}
                   onBlur={validateKey}
                   type={showSecret ? 'text' : 'password'} testId="connect-input-api-key"
                   rightSlot={
                     <button type="button" onClick={() => setShowSecret((v) => !v)}
                             className="text-[10px]" style={{ color: 'var(--theme-text-muted)' }}>
                       {showSecret ? <EyeSlash size={14} /> : <Eye size={14} />}
                     </button>
                   } />
            {/* iter124 — real-time validation chip */}
            {(validating || validation) && (
              <div className="text-[11px] -mt-1 mb-2.5 flex items-center gap-1.5" data-testid="connect-input-api-key-validation">
                {validating ? (
                  <>
                    <CircleNotch size={11} className="animate-spin" style={{ color: 'var(--theme-text-muted)' }} />
                    <span style={{ color: 'var(--theme-text-muted)' }}>Validating key…</span>
                  </>
                ) : validation?.valid === true ? (
                  <>
                    <CheckCircle size={12} weight="fill" style={{ color: '#22c55e' }} />
                    <span style={{ color: '#22c55e' }}>{validation.message}</span>
                  </>
                ) : validation?.valid === false ? (
                  <>
                    <Warning size={12} weight="fill" style={{ color: '#ef4444' }} />
                    <span style={{ color: '#ef4444' }}>{validation.message}</span>
                  </>
                ) : (
                  <>
                    <Warning size={12} style={{ color: '#f59e0b' }} />
                    <span style={{ color: '#f59e0b' }}>{validation?.message}</span>
                  </>
                )}
              </div>
            )}
            {extraFields.map((f) => (
              <Field key={f} label={f.replace(/_/g, ' ')} value={extra[f] || ''} onChange={(v) => setExtra({ ...extra, [f]: v })}
                     testId={`connect-input-${f}`} />
            ))}
          </>
        )}

        <button onClick={handleSubmit} disabled={busy || (!isOAuth && validation?.valid === false)} data-testid="connect-modal-submit"
                className="w-full mt-3 px-4 py-2 rounded-md font-bold text-sm text-white disabled:opacity-50"
                style={{ background: 'var(--theme-purple)' }}>
          {busy ? <CircleNotch size={14} className="animate-spin inline -mt-0.5 mr-1" /> : null}
          {isOAuth ? (busy ? 'Opening OAuth…' : 'Save & Connect') : (busy ? 'Saving…' : 'Save credentials')}
        </button>
      </div>
    </div>
  );
};

const Field = ({ label, value, onChange, onBlur, type = 'text', testId, rightSlot }) => (
  <label className="block mb-2.5">
    <span className="text-[10px] uppercase tracking-wider font-bold" style={{ color: 'var(--theme-text-muted)' }}>{label}</span>
    <div className="relative mt-1">
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onBlur}
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
