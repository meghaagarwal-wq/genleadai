import React, { useEffect, useState, useCallback } from 'react';
import { Routes, Route, NavLink, useNavigate } from 'react-router-dom';
import api from '../config/api';
import { toast } from 'sonner';

const NAV = [
  { to: '/admin', label: 'Overview' },
  { to: '/admin/workspaces', label: 'Workspaces' },
  { to: '/admin/usage', label: 'Usage & Billing' },
  { to: '/admin/system', label: 'System Health' },
  { to: '/admin/key-validation', label: 'Key Validation' },  // iter108
  { to: '/admin/settings', label: 'Settings' },
];

const Stat = ({ label, value, hint }) => (
  <div className="bg-white border border-slate-200 rounded-xl p-5">
    <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">{label}</div>
    <div className="text-2xl font-bold text-slate-900">{value}</div>
    {hint && <div className="text-xs text-slate-500 mt-1">{hint}</div>}
  </div>
);

const AdminOverview = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    (async () => {
      try {
        const r = await api.get('/api/admin/v3/overview');
        setData(r.data);
      } catch (e) {
        toast.error('Could not load overview');
      } finally {
        setLoading(false);
      }
    })();
  }, []);
  if (loading) return <div className="p-8 text-slate-500 text-sm">Loading…</div>;
  if (!data) return <div className="p-8 text-rose-600 text-sm">Failed to load.</div>;
  return (
    <div data-testid="admin-overview">
      <h1 className="text-2xl font-bold text-slate-900 mb-1">Platform Overview</h1>
      <p className="text-sm text-slate-600 mb-6">Across all workspaces and tenants.</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <Stat label="Workspaces total" value={data.workspaces.total} hint={`${data.workspaces.active} active`} />
        <Stat label="Tenants" value={data.tenants_total} />
        <Stat label="Leads today" value={data.leads_today} />
        <Stat label="Active conversations" value={data.active_conversations} hint="last 24h" />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Stat label="Insights generated today" value={data.insights_today} />
        <Stat label="API cost today" value={`$${data.api_cost_today_usd.toFixed(4)}`} hint="USD, est." />
        <Stat label="Errors last 24h" value={data.errors_24h} hint="from audit log" />
      </div>
    </div>
  );
};

const ModeBadge = ({ mode }) => {
  const map = {
    b2b:    'bg-violet-100 text-violet-700',
    b2c:    'bg-sky-100 text-sky-700',
    hybrid: 'bg-emerald-100 text-emerald-700',
  };
  return (
    <span className={`text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full ${map[mode] || 'bg-slate-100 text-slate-700'}`}>
      {mode}
    </span>
  );
};

const AdminWorkspaces = () => {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get('/api/admin/v3/workspaces');
      setRows(r.data.workspaces || []);
    } catch (e) {
      toast.error('Could not load workspaces');
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const impersonate = async (workspace_id) => {
    try {
      const r = await api.post(`/api/admin/v3/workspaces/${workspace_id}/impersonate`);
      // Set the active tenant locally + show banner-routing breadcrumb
      localStorage.setItem('X-Tenant-Id', workspace_id);
      localStorage.setItem('impersonating', JSON.stringify({
        workspace_id,
        workspace_name: r.data.workspace_name,
        mode: r.data.mode,
      }));
      toast.success(`Impersonating ${r.data.workspace_name}`);
      // Route to the client dashboard root — banner will appear via App-level read of localStorage
      navigate('/');
      // Give the navigation a tick then full reload to ensure all components pick up the new tenant
      setTimeout(() => window.location.reload(), 100);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Impersonate failed');
    }
  };

  const doAction = async (workspace_id, action) => {
    if (!window.confirm(`Confirm ${action} on ${workspace_id}?`)) return;
    try {
      await api.post(`/api/admin/v3/workspaces/${workspace_id}/action`, { action });
      toast.success(`${action} applied to ${workspace_id}`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Action failed');
    }
  };

  return (
    <div data-testid="admin-workspaces">
      <h1 className="text-2xl font-bold text-slate-900 mb-1">Workspaces</h1>
      <p className="text-sm text-slate-600 mb-6">All workspaces on the platform.</p>
      {loading ? (
        <div className="text-slate-500 text-sm">Loading…</div>
      ) : (
        <div className="overflow-x-auto border border-slate-200 rounded-xl bg-white">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr className="text-left text-xs font-semibold text-slate-600 uppercase tracking-wide">
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Mode</th>
                <th className="px-4 py-3">Owner</th>
                <th className="px-4 py-3">Leads</th>
                <th className="px-4 py-3">Trained</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((w) => (
                <tr key={w.id} className="border-b border-slate-100 hover:bg-slate-50" data-testid={`workspace-row-${w.id}`}>
                  <td className="px-4 py-3 font-semibold text-slate-900">{w.name}<div className="text-xs text-slate-400 font-normal">{w.id}</div></td>
                  <td className="px-4 py-3"><ModeBadge mode={w.mode} /></td>
                  <td className="px-4 py-3 text-slate-600">{w.owner_email || '—'}</td>
                  <td className="px-4 py-3 text-slate-700 font-medium">{w.lead_volume}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-semibold ${w.has_aria_training ? 'text-emerald-600' : 'text-slate-400'}`}>
                      {w.has_aria_training ? '✓ Yes' : '—'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-semibold ${w.is_active ? 'text-emerald-600' : 'text-rose-600'}`}>
                      {w.is_active ? 'Active' : 'Suspended'}
                    </span>
                  </td>
                  <td className="px-4 py-3 flex gap-1 flex-wrap">
                    <button
                      data-testid={`impersonate-${w.id}`}
                      onClick={() => impersonate(w.id)}
                      className="px-2 py-1 bg-violet-600 hover:bg-violet-700 text-white text-xs font-semibold rounded"
                    >Impersonate</button>
                    {w.is_active ? (
                      <button onClick={() => doAction(w.id, 'suspend')} className="px-2 py-1 border border-slate-300 hover:bg-slate-100 text-slate-700 text-xs font-semibold rounded">Suspend</button>
                    ) : (
                      <button onClick={() => doAction(w.id, 'activate')} className="px-2 py-1 border border-slate-300 hover:bg-slate-100 text-slate-700 text-xs font-semibold rounded">Activate</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

const AdminUsage = () => {
  const [data, setData] = useState(null);
  useEffect(() => {
    (async () => {
      try {
        const r = await api.get('/api/admin/v3/usage');
        setData(r.data);
      } catch (e) {
        toast.error('Could not load usage');
      }
    })();
  }, []);
  if (!data) return <div className="p-8 text-slate-500 text-sm">Loading…</div>;
  return (
    <div data-testid="admin-usage">
      <h1 className="text-2xl font-bold text-slate-900 mb-1">Usage & Billing</h1>
      <p className="text-sm text-slate-600 mb-6">API spend per workspace this month.</p>
      <div className="overflow-x-auto border border-slate-200 rounded-xl bg-white">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50">
            <tr className="text-left text-xs font-semibold text-slate-600 uppercase tracking-wide">
              <th className="px-4 py-3">Workspace</th>
              <th className="px-4 py-3">Plan</th>
              <th className="px-4 py-3">Providers</th>
              <th className="px-4 py-3">Total this month</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row) => (
              <tr key={row.workspace_id} className="border-b border-slate-100">
                <td className="px-4 py-3 font-semibold text-slate-900">{row.workspace_name}</td>
                <td className="px-4 py-3 text-slate-600">{row.plan}</td>
                <td className="px-4 py-3 text-xs text-slate-600">
                  {Object.keys(row.providers).length === 0
                    ? <span className="text-slate-400">no usage</span>
                    : Object.entries(row.providers).map(([p, v]) => (
                        <span key={p} className="inline-block mr-2 bg-slate-100 rounded px-2 py-0.5">
                          {p}: {v.calls} ({`$${v.cost_usd.toFixed(4)}`})
                        </span>
                      ))}
                </td>
                <td className="px-4 py-3 font-medium text-slate-700">${row.total_cost_usd_month.toFixed(4)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

const AdminSystem = () => {
  const [data, setData] = useState(null);
  useEffect(() => {
    (async () => {
      try {
        const r = await api.get('/api/admin/v3/system-health');
        setData(r.data);
      } catch (e) {
        toast.error('Could not load system health');
      }
    })();
  }, []);
  if (!data) return <div className="p-8 text-slate-500 text-sm">Loading…</div>;
  return (
    <div data-testid="admin-system">
      <h1 className="text-2xl font-bold text-slate-900 mb-1">System Health</h1>
      <p className="text-sm text-slate-600 mb-6">Background jobs and integration errors — last 24 hours.</p>

      <div className="border border-slate-200 rounded-xl p-5 bg-white mb-4">
        <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Recent actions (audit log)</div>
        {Object.keys(data.job_status).length === 0 ? (
          <div className="text-sm text-slate-400">No activity in the last 24h.</div>
        ) : (
          <div className="space-y-1.5">
            {Object.entries(data.job_status).map(([action, s]) => (
              <div key={action} className="flex justify-between text-xs">
                <span className="text-slate-700 font-mono">{action}</span>
                <span className="text-slate-500">{s.count_24h}× · {s.latest_at?.slice(0, 19).replace('T', ' ')}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="border border-slate-200 rounded-xl p-5 bg-white">
        <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Integration errors</div>
        {data.integration_errors.length === 0 ? (
          <div className="text-sm text-emerald-600">✓ No integration errors in the last 24h.</div>
        ) : (
          <div className="space-y-2">
            {data.integration_errors.map((e, i) => (
              <div key={i} className="text-xs text-slate-700 border-l-2 border-rose-400 pl-3">
                <div className="font-semibold">{e.action}</div>
                <div className="text-slate-500">{e.tenant_id} · {e.timestamp?.slice(0, 19).replace('T', ' ')}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

const AdminSettings = () => (
  <div data-testid="admin-settings">
    <h1 className="text-2xl font-bold text-slate-900 mb-1">Global Settings</h1>
    <p className="text-sm text-slate-600 mb-6">Platform-wide configuration.</p>
    <div className="border border-slate-200 rounded-xl p-5 bg-white text-sm text-slate-600">
      Platform settings UI (default onboarding mode, notification defaults,
      Stripe webhook config, environment status) — Phase 5b.
    </div>
  </div>
);

// iter108 — Admin debug surface for the pre-save API-key validator. Shows
// the last 50 attempts across the platform with elapsed_ms + masked key
// + which user pasted it.
const AdminKeyValidation = () => {
  const [items, setItems] = useState([]);
  const [providers, setProviders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [testProvider, setTestProvider] = useState('');
  const [testKey, setTestKey] = useState('');
  const [testResult, setTestResult] = useState(null);
  const [testBusy, setTestBusy] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [h, p] = await Promise.all([
        api.get('/api/integrations/validate-key/history'),
        api.get('/api/integrations/validate-key/providers'),
      ]);
      setItems(h.data.items || []);
      setProviders(p.data.providers || []);
      if (!testProvider && (p.data.providers || []).length) setTestProvider(p.data.providers[0]);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to load key-validation history');
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  const runTest = async () => {
    if (!testProvider || !testKey) return;
    setTestBusy(true);
    setTestResult(null);
    try {
      const { data } = await api.post('/api/integrations/validate-key', {
        provider: testProvider, api_key: testKey,
      });
      setTestResult(data);
      refresh();
    } catch (e) {
      setTestResult({ valid: false, message: e?.response?.data?.detail || 'Request failed' });
    } finally {
      setTestBusy(false);
    }
  };

  return (
    <div data-testid="admin-key-validation">
      <h1 className="text-2xl font-bold text-slate-900 mb-1">Key Validation</h1>
      <p className="text-sm text-slate-600 mb-6">
        Live debug of every API-key paste across all workspaces (last 50, in-memory).
      </p>

      <div className="border border-slate-200 rounded-xl p-5 bg-white mb-6">
        <div className="text-sm font-semibold text-slate-900 mb-3">Try a key</div>
        <div className="flex flex-wrap gap-2 items-center">
          <select
            value={testProvider}
            onChange={(e) => setTestProvider(e.target.value)}
            data-testid="admin-key-test-provider"
            className="border border-slate-300 rounded-md px-2 py-1.5 text-sm bg-white"
          >
            {providers.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
          <input
            type="password"
            value={testKey}
            placeholder="Paste a key to test…"
            onChange={(e) => setTestKey(e.target.value)}
            data-testid="admin-key-test-input"
            className="flex-1 min-w-[260px] border border-slate-300 rounded-md px-2 py-1.5 text-sm"
          />
          <button
            onClick={runTest}
            disabled={!testKey || testBusy}
            data-testid="admin-key-test-run"
            className="text-sm font-semibold bg-slate-900 text-white px-3 py-1.5 rounded-md disabled:opacity-50"
          >{testBusy ? 'Testing…' : 'Validate'}</button>
        </div>
        {testResult && (
          <div
            data-testid="admin-key-test-result"
            className={`mt-3 text-sm ${testResult.valid ? 'text-emerald-700' : 'text-rose-700'}`}
          >
            {testResult.valid ? '✓ Valid — ' : '✕ Rejected — '}{testResult.message}
            {typeof testResult.elapsed_ms === 'number' && (
              <span className="text-slate-500 ml-2">({testResult.elapsed_ms} ms)</span>
            )}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between mb-3">
        <div className="text-sm font-semibold text-slate-900">Recent attempts ({items.length})</div>
        <button
          onClick={refresh}
          data-testid="admin-key-history-refresh"
          className="text-xs font-semibold text-violet-700 hover:underline"
        >Refresh</button>
      </div>
      <div className="border border-slate-200 rounded-xl bg-white overflow-hidden">
        {loading ? (
          <div className="p-6 text-sm text-slate-500">Loading…</div>
        ) : items.length === 0 ? (
          <div className="p-6 text-sm text-slate-500">No attempts yet. Paste any key into an integration card to populate this list.</div>
        ) : (
          <table className="w-full text-sm" data-testid="admin-key-history-table">
            <thead className="bg-slate-50 text-slate-600 text-xs uppercase tracking-wide">
              <tr>
                <th className="text-left px-4 py-2">When</th>
                <th className="text-left px-4 py-2">Provider</th>
                <th className="text-left px-4 py-2">Result</th>
                <th className="text-left px-4 py-2">Latency</th>
                <th className="text-left px-4 py-2">Key (masked)</th>
                <th className="text-left px-4 py-2">User</th>
                <th className="text-left px-4 py-2">Message</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it, i) => (
                <tr key={i} className="border-t border-slate-100">
                  <td className="px-4 py-2 text-slate-500 whitespace-nowrap">{new Date(it.at).toLocaleString()}</td>
                  <td className="px-4 py-2 font-medium text-slate-900">{it.provider}</td>
                  <td className={`px-4 py-2 font-semibold ${it.valid ? 'text-emerald-700' : 'text-rose-700'}`}>
                    {it.valid ? '✓ valid' : '✕ rejected'}
                  </td>
                  <td className="px-4 py-2 text-slate-500">{it.elapsed_ms != null ? `${it.elapsed_ms} ms` : '—'}</td>
                  <td className="px-4 py-2 font-mono text-xs text-slate-700">{it.key_masked}</td>
                  <td className="px-4 py-2 text-slate-600">{it.by_user_email || '—'}</td>
                  <td className="px-4 py-2 text-slate-600 max-w-[420px] truncate" title={it.message}>{it.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

const AdminLayout = () => {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen bg-slate-100" data-testid="admin-dashboard">
      <header className="bg-slate-900 text-white px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="text-base font-bold">ARIA · Admin</div>
          <div className="text-xs text-slate-400">GenLeadAI internal</div>
        </div>
        <button
          data-testid="admin-back-to-client"
          onClick={() => navigate('/')}
          className="text-xs font-semibold text-slate-300 hover:text-white"
        >← Back to client dashboard</button>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-[220px_1fr] gap-0 min-h-[calc(100vh-52px)]">
        <aside className="bg-white border-r border-slate-200 p-4">
          <nav className="space-y-1">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/admin'}
                data-testid={`admin-nav-${item.label.toLowerCase().replace(/[^a-z]/g, '-')}`}
                className={({ isActive }) =>
                  `block px-3 py-2 rounded-lg text-sm font-medium ${isActive ? 'bg-slate-900 text-white' : 'text-slate-700 hover:bg-slate-100'}`
                }
              >{item.label}</NavLink>
            ))}
          </nav>
        </aside>

        <main className="p-6 lg:p-10">
          <Routes>
            <Route path="/" element={<AdminOverview />} />
            <Route path="/workspaces" element={<AdminWorkspaces />} />
            <Route path="/usage" element={<AdminUsage />} />
            <Route path="/system" element={<AdminSystem />} />
            <Route path="/key-validation" element={<AdminKeyValidation />} />
            <Route path="/settings" element={<AdminSettings />} />
          </Routes>
        </main>
      </div>
    </div>
  );
};

export default AdminLayout;
