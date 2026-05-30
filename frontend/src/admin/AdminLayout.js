import React, { useEffect, useState, useCallback } from 'react';
import { Routes, Route, NavLink, useNavigate } from 'react-router-dom';
import api from '../config/api';
import { toast } from 'sonner';

const NAV = [
  { to: '/admin', label: 'Overview' },
  { to: '/admin/applications', label: 'Applications' },  // iter141 — V19 Batch 4
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

  // iter108 — Force-promote plan (CSAT lifesaver for stuck workspaces)
  const [forcePlan, setForcePlan] = useState(null); // { workspace_id, name }
  const [forcePlanId, setForcePlanId] = useState('pro');
  const [forcePlanReason, setForcePlanReason] = useState('');
  const [forcePlanBusy, setForcePlanBusy] = useState(false);

  const submitForcePlan = async () => {
    if (!forcePlan) return;
    setForcePlanBusy(true);
    try {
      const r = await api.post(`/api/admin/v3/workspaces/${forcePlan.workspace_id}/force-plan`, {
        plan_id: forcePlanId, reason: forcePlanReason,
      });
      toast.success(`${r.data.workspace_name} promoted to ${r.data.plan_name}`);
      setForcePlan(null);
      setForcePlanReason('');
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Force-plan failed');
    } finally {
      setForcePlanBusy(false);
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
                    <button
                      data-testid={`force-plan-${w.id}`}
                      onClick={() => { setForcePlan({ workspace_id: w.id, name: w.name }); setForcePlanReason(''); }}
                      className="px-2 py-1 border border-amber-300 text-amber-700 hover:bg-amber-50 text-xs font-semibold rounded"
                      title="Force-promote this workspace's plan"
                    >Force plan</button>
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

      {/* iter108 — Force-promote plan modal */}
      {forcePlan && (
        <div
          className="fixed inset-0 z-[80] bg-black/40 backdrop-blur-sm flex items-center justify-center p-4"
          data-testid="force-plan-modal"
          onClick={() => !forcePlanBusy && setForcePlan(null)}
        >
          <div
            className="bg-white rounded-xl shadow-2xl border border-slate-200 max-w-md w-full p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-lg font-bold text-slate-900 mb-1">Force-promote plan</h2>
            <p className="text-sm text-slate-600 mb-4">
              Stamp a new plan on <span className="font-semibold text-slate-900">{forcePlan.name}</span> directly. Bypasses Stripe — use only when a paid customer's workspace is stuck.
            </p>
            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">Plan</label>
            <select
              value={forcePlanId}
              onChange={(e) => setForcePlanId(e.target.value)}
              disabled={forcePlanBusy}
              data-testid="force-plan-select"
              className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm bg-white mb-3"
            >
              <option value="starter">Starter ($49)</option>
              <option value="growth">Growth ($149)</option>
              <option value="pro">Pro ($399)</option>
              <option value="custom">Custom (contact-sales)</option>
            </select>
            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">Reason (audited)</label>
            <textarea
              value={forcePlanReason}
              onChange={(e) => setForcePlanReason(e.target.value)}
              disabled={forcePlanBusy}
              data-testid="force-plan-reason"
              placeholder="e.g. Stripe webhook race — customer paid but workspace stuck on Starter"
              rows={3}
              className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm mb-4 resize-none"
            />
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setForcePlan(null)}
                disabled={forcePlanBusy}
                className="px-3 py-1.5 border border-slate-300 hover:bg-slate-100 text-slate-700 text-sm font-semibold rounded"
              >Cancel</button>
              <button
                onClick={submitForcePlan}
                disabled={forcePlanBusy || !forcePlanReason.trim()}
                data-testid="force-plan-submit"
                className="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white text-sm font-bold rounded"
              >{forcePlanBusy ? 'Promoting…' : `Force to ${forcePlanId}`}</button>
            </div>
            <div className="mt-3 text-[11px] text-slate-500">
              This is recorded in the audit log with your email + the reason above.
            </div>
          </div>
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

// iter141 — V19 Batch 4: /admin/applications review surface.
// Lists submissions from POST /api/applications with status filter tabs,
// row click opens a side-drawer detail panel, primary action "Create
// Workspace" provisions a tenant + invite token.
const STATUS_LABEL = {
  new: { label: 'New', cls: 'bg-blue-100 text-blue-700' },
  reviewing: { label: 'Reviewing', cls: 'bg-amber-100 text-amber-700' },
  qualified: { label: 'Qualified', cls: 'bg-emerald-100 text-emerald-700' },
  not_fit: { label: 'Not a Fit', cls: 'bg-rose-100 text-rose-700' },
  onboarded: { label: 'Onboarded', cls: 'bg-violet-100 text-violet-700' },
};
const STATUS_TABS = ['all', 'new', 'reviewing', 'qualified', 'not_fit', 'onboarded'];
const STATUS_TAB_LABEL = { all: 'All', new: 'New', reviewing: 'Reviewing', qualified: 'Qualified', not_fit: 'Not a Fit', onboarded: 'Onboarded' };
const TIMELINE_LABEL = { now: 'Yesterday — let\'s go', '1-3_months': '1–3 months', '3-6_months': '3–6 months', exploring: 'Exploring' };
const BUDGET_LABEL = { under_10k: '<$10K', '10k_50k': '$10K–$50K', '50k_500k': '$50K–$500K', '500k_plus': '$500K+' };

const StatusPill = ({ status }) => {
  const meta = STATUS_LABEL[status] || { label: status, cls: 'bg-slate-100 text-slate-700' };
  return <span className={`text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full ${meta.cls}`}>{meta.label}</span>;
};

const AdminApplications = () => {
  const [items, setItems] = useState([]);
  const [counts, setCounts] = useState({});
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('new');
  const [selected, setSelected] = useState(null);  // full app doc
  const [selectedLoading, setSelectedLoading] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);

  const refresh = useCallback(async (status = filter) => {
    setLoading(true);
    try {
      const r = await api.get(`/api/applications?status=${status}&limit=200`);
      setItems(r.data.items || []);
      setCounts(r.data.counts || {});
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not load applications');
    } finally { setLoading(false); }
  }, [filter]);
  useEffect(() => { refresh(filter); }, [filter, refresh]);

  // Esc to close drawer (V13)
  useEffect(() => {
    if (!selected) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') setSelected(null); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [selected]);

  const openDrawer = async (app) => {
    setSelected(app);  // optimistic
    setSelectedLoading(true);
    try {
      const r = await api.get(`/api/applications/${app.id}`);
      setSelected(r.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not load application');
    } finally { setSelectedLoading(false); }
  };

  const setStatus = async (app_id, status, note = null) => {
    try {
      const r = await api.patch(`/api/applications/${app_id}/status`, { status, note });
      toast.success(`Marked as ${STATUS_LABEL[status]?.label || status}`);
      setSelected(r.data);
      refresh(filter);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Update failed');
    }
  };

  return (
    <div data-testid="admin-applications-page">
      <div className="flex items-end justify-between mb-1">
        <h1 className="text-2xl font-bold text-slate-900">Applications</h1>
        <button
          onClick={() => refresh(filter)}
          data-testid="admin-applications-refresh"
          className="text-xs font-semibold text-violet-700 hover:underline"
        >Refresh</button>
      </div>
      <p className="text-sm text-slate-600 mb-5">Public /apply submissions from the marketing funnel.</p>

      {/* Status filter tabs (V19 spec) */}
      <div className="flex gap-1 mb-5 border-b border-slate-200" data-testid="admin-applications-tabs">
        {STATUS_TABS.map((s) => {
          const active = filter === s;
          const cnt = s === 'all' ? counts.all : counts[s];
          return (
            <button
              key={s}
              onClick={() => setFilter(s)}
              data-testid={`admin-applications-tab-${s}`}
              className={`px-3 py-2 text-sm font-semibold border-b-2 transition-colors ${active ? 'border-violet-600 text-violet-700' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
            >
              {STATUS_TAB_LABEL[s]}
              {typeof cnt === 'number' && cnt > 0 && (
                <span className={`ml-1.5 text-[10px] font-mono px-1.5 py-0.5 rounded-full ${active ? 'bg-violet-100 text-violet-700' : 'bg-slate-100 text-slate-600'}`}>
                  {cnt}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Table */}
      <div className="overflow-x-auto border border-slate-200 rounded-xl bg-white">
        {loading ? (
          <div className="p-8 text-slate-500 text-sm" data-testid="admin-applications-loading">Loading…</div>
        ) : items.length === 0 ? (
          <div className="p-12 text-center" data-testid="admin-applications-empty">
            <p className="text-sm text-slate-500">No applications in this view.</p>
            <p className="text-xs text-slate-400 mt-1">Submissions from <code>/apply</code> appear here.</p>
          </div>
        ) : (
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr className="text-left text-xs font-semibold text-slate-600 uppercase tracking-wide">
                <th className="px-4 py-3"></th>
                <th className="px-4 py-3">Applicant</th>
                <th className="px-4 py-3">Company</th>
                <th className="px-4 py-3">Timeline</th>
                <th className="px-4 py-3">Budget</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Received</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr
                  key={row.id}
                  className="border-b border-slate-100 hover:bg-violet-50/30 cursor-pointer transition-colors"
                  onClick={() => openDrawer(row)}
                  data-testid={`admin-application-row-${row.id}`}
                >
                  <td className="px-4 py-3 align-top">
                    {row.status === 'new' && <span className="inline-block w-2 h-2 rounded-full bg-blue-500" title="New" data-testid={`admin-application-new-dot-${row.id}`} />}
                  </td>
                  <td className="px-4 py-3">
                    <div className="font-semibold text-slate-900">{row.full_name}</div>
                    <div className="text-xs text-slate-500">{row.work_email}</div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="font-medium text-slate-800">{row.company_name}</div>
                    <div className="text-xs text-slate-500">{row.industry} · {row.country}</div>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-700">{TIMELINE_LABEL[row.timeline] || row.timeline}</td>
                  <td className="px-4 py-3 text-xs text-slate-700">{BUDGET_LABEL[row.budget_band] || row.budget_band}</td>
                  <td className="px-4 py-3"><StatusPill status={row.status} /></td>
                  <td className="px-4 py-3 text-xs text-slate-500 whitespace-nowrap">{row.created_at?.slice(0, 10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Detail drawer */}
      {selected && (
        <div
          className="fixed inset-0 z-[70] bg-black/40 backdrop-blur-sm flex justify-end"
          data-testid="admin-application-drawer"
          onClick={() => setSelected(null)}
        >
          <aside
            className="bg-white w-full max-w-xl h-full overflow-y-auto shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <header className="sticky top-0 bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between z-10">
              <div>
                <div className="text-xs uppercase tracking-wider text-slate-400 font-semibold">Application</div>
                <h2 className="text-lg font-bold text-slate-900">{selected.full_name}</h2>
                <div className="text-xs text-slate-500 mt-0.5">{selected.work_email}</div>
              </div>
              <div className="flex items-center gap-2">
                <StatusPill status={selected.status} />
                <button onClick={() => setSelected(null)} className="text-slate-400 hover:text-slate-700 text-xl leading-none px-2" data-testid="admin-application-close">×</button>
              </div>
            </header>

            <div className="p-6 space-y-5 text-sm">
              {selectedLoading && <div className="text-xs text-slate-400">Loading full record…</div>}

              <Section title="About">
                <Row k="Role">{selected.role}</Row>
                <Row k="Country">{selected.country}</Row>
              </Section>

              <Section title="Company">
                <Row k="Name">{selected.company_name}</Row>
                {selected.company_url && <Row k="URL"><a href={selected.company_url} target="_blank" rel="noreferrer" className="text-violet-700 underline">{selected.company_url}</a></Row>}
                <Row k="Industry">{selected.industry}</Row>
                <Row k="Team">{selected.employees}</Row>
                {selected.revenue && <Row k="Revenue">{selected.revenue}</Row>}
              </Section>

              <Section title="Current setup">
                <p className="text-slate-700 whitespace-pre-wrap">{selected.current_setup}</p>
                {selected.channels?.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {selected.channels.map((c) => <span key={c} className="text-[10px] font-semibold bg-slate-100 text-slate-700 px-2 py-0.5 rounded">{c}</span>)}
                  </div>
                )}
                <Row k="Volume">{selected.current_volume}</Row>
              </Section>

              <Section title="Pain & goal">
                <Row k="Biggest pain"><div className="text-slate-700 whitespace-pre-wrap">{selected.biggest_pain}</div></Row>
                <Row k="Goal"><div className="text-slate-700 whitespace-pre-wrap">{selected.goal}</div></Row>
                <Row k="Timeline">{TIMELINE_LABEL[selected.timeline] || selected.timeline}</Row>
                <Row k="Budget">{BUDGET_LABEL[selected.budget_band] || selected.budget_band}</Row>
                <Row k="Decision-maker ready">{selected.ready_to_start ? 'Yes' : 'No'}</Row>
              </Section>

              {selected.last_reviewed_by && (
                <div className="text-xs text-slate-500 italic border-l-2 border-slate-200 pl-3">
                  Last reviewed by {selected.last_reviewed_by} · {selected.last_review_note || 'no note'}
                </div>
              )}
            </div>

            {/* Sticky action bar */}
            <footer className="sticky bottom-0 bg-white border-t border-slate-200 px-6 py-3 flex flex-wrap items-center gap-2 z-10">
              <button
                onClick={() => setCreateOpen(true)}
                disabled={selected.status === 'onboarded'}
                data-testid="admin-application-create-workspace"
                className="px-3 py-1.5 bg-violet-600 hover:bg-violet-700 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-bold rounded"
              >
                {selected.status === 'onboarded' ? '✓ Workspace created' : 'Create Workspace →'}
              </button>
              <button
                onClick={() => setStatus(selected.id, 'qualified')}
                data-testid="admin-application-mark-qualified"
                className="px-3 py-1.5 border border-emerald-300 text-emerald-700 hover:bg-emerald-50 text-xs font-bold rounded"
              >Mark Qualified</button>
              <button
                onClick={() => setStatus(selected.id, 'reviewing')}
                data-testid="admin-application-mark-reviewing"
                className="px-3 py-1.5 border border-amber-300 text-amber-700 hover:bg-amber-50 text-xs font-bold rounded"
              >Reviewing</button>
              <button
                onClick={() => {
                  const note = window.prompt('Optional — why not a fit?');
                  setStatus(selected.id, 'not_fit', note);
                }}
                data-testid="admin-application-mark-not-fit"
                className="px-3 py-1.5 border border-rose-300 text-rose-700 hover:bg-rose-50 text-xs font-bold rounded"
              >Not a Fit</button>
            </footer>
          </aside>
        </div>
      )}

      {/* Create Workspace modal */}
      {createOpen && selected && (
        <CreateWorkspaceModal
          application={selected}
          onClose={() => setCreateOpen(false)}
          onCreated={(data) => {
            setCreateOpen(false);
            setSelected({ ...selected, status: 'onboarded' });
            refresh(filter);
            toast.success(`Workspace created · ${data.workspace_name}${data.invited_email_sent ? ' · invite emailed' : ''}`);
          }}
        />
      )}
    </div>
  );
};

const Section = ({ title, children }) => (
  <div>
    <div className="text-[10px] uppercase tracking-wider text-slate-400 font-bold mb-1.5">{title}</div>
    <div className="space-y-1.5">{children}</div>
  </div>
);
const Row = ({ k, children }) => (
  <div className="text-xs">
    <span className="text-slate-500">{k}: </span>
    <span className="text-slate-800 font-medium">{children}</span>
  </div>
);

const CreateWorkspaceModal = ({ application, onClose, onCreated }) => {
  const [name, setName] = useState(application?.company_name || '');
  const [mode, setMode] = useState('hybrid');
  const [inviteEmail, setInviteEmail] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape' && !busy) onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [busy, onClose]);

  const submit = async () => {
    if (!name.trim()) return;
    setBusy(true);
    try {
      const r = await api.post(`/api/applications/${application.id}/create-workspace`, {
        workspace_name: name.trim(),
        mode,
        invite_email: inviteEmail,
      });
      onCreated(r.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Workspace creation failed');
    } finally { setBusy(false); }
  };

  return (
    <div
      className="fixed inset-0 z-[80] bg-black/50 backdrop-blur-sm flex items-center justify-center p-4"
      data-testid="create-workspace-modal"
      onClick={() => !busy && onClose()}
    >
      <div className="bg-white rounded-xl shadow-2xl border border-slate-200 max-w-md w-full p-6" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-lg font-bold text-slate-900 mb-1">Create workspace for {application.company_name}</h3>
        <p className="text-xs text-slate-600 mb-4">Provisions a tenant + sends an invite to <strong>{application.work_email}</strong>.</p>

        <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">Workspace name</label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={busy}
          data-testid="create-workspace-name"
          className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm mb-3"
        />

        <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">Mode</label>
        <div className="grid grid-cols-3 gap-2 mb-3">
          {['b2b', 'b2c', 'hybrid'].map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              disabled={busy}
              data-testid={`create-workspace-mode-${m}`}
              className={`px-2 py-1.5 rounded border text-xs font-bold ${mode === m ? 'bg-violet-600 text-white border-violet-600' : 'bg-white border-slate-300 text-slate-700 hover:bg-slate-50'}`}
            >{m.toUpperCase()}</button>
          ))}
        </div>

        <label className="flex items-start gap-2 text-xs text-slate-700 mb-4 cursor-pointer">
          <input
            type="checkbox"
            checked={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.checked)}
            disabled={busy}
            data-testid="create-workspace-invite-email"
            className="mt-0.5"
          />
          <span>Send invite email to {application.work_email}</span>
        </label>

        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            disabled={busy}
            className="px-3 py-1.5 border border-slate-300 hover:bg-slate-100 text-slate-700 text-sm font-semibold rounded"
          >Cancel</button>
          <button
            onClick={submit}
            disabled={busy || !name.trim()}
            data-testid="create-workspace-submit"
            className="px-3 py-1.5 bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white text-sm font-bold rounded"
          >{busy ? 'Creating…' : 'Create & invite →'}</button>
        </div>
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
            <Route path="/applications" element={<AdminApplications />} />
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
