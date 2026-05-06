import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { CheckCircle, Warning, Plug, Eye, EyeSlash, ArrowSquareOut, Trash, ArrowsClockwise, Sparkle, Lightning, Plus, Toggle } from '@phosphor-icons/react';
import api from '../config/api';
import PageHeader from '../components/PageHeader';

const PLATFORMS = [
  {
    id: 'saleshandy',
    name: 'SalesHandy',
    blurb: 'Two-way sync with SalesHandy sequences. Push leads from ARIA, pull engagement events back into the Lead Feed.',
    keyHelp: 'Settings → API Key in your SalesHandy dashboard. SalesHandy shows it once — copy it immediately.',
    docsUrl: 'https://docs.saleshandy.com/en/articles/8154265-saleshandy-api',
    color: '#16A34A',
    inboundMode: 'Polled every 5 min',
  },
  {
    id: 'lemlist',
    name: 'Lemlist',
    blurb: 'Two-way sync with Lemlist campaigns. Real-time webhook events (opens, clicks, replies, meetings booked) land in ARIA.',
    keyHelp: 'Profile picture (bottom-left) → Settings → Integrations → Generate a new API key.',
    docsUrl: 'https://developer.lemlist.com/api-reference/getting-started/authentication',
    color: '#7C35DC',
    inboundMode: 'Real-time webhook',
  },
];

const SalesEngagement = () => {
  const [status, setStatus] = useState({ saleshandy: {}, lemlist: {} });
  const [loading, setLoading] = useState(true);
  const [keys, setKeys] = useState({ saleshandy: '', lemlist: '' });
  const [show, setShow] = useState({ saleshandy: false, lemlist: false });
  const [busy, setBusy] = useState({});

  const refresh = async () => {
    try {
      const r = await api.get('/api/integrations/status');
      setStatus(r.data);
    } catch { /* ignore */ } finally { setLoading(false); }
  };
  useEffect(() => { refresh(); }, []);

  const save = async (platform) => {
    const k = (keys[platform] || '').trim();
    if (!k) { toast.error('Paste your API key first'); return; }
    setBusy(b => ({ ...b, [platform]: 'save' }));
    try {
      await api.post('/api/integrations/keys', { [`${platform}_api_key`]: k });
      toast.success(`${platform === 'saleshandy' ? 'SalesHandy' : 'Lemlist'} connected`);
      setKeys(p => ({ ...p, [platform]: '' }));
      await refresh();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save key');
    } finally { setBusy(b => ({ ...b, [platform]: null })); }
  };

  const test = async (platform) => {
    setBusy(b => ({ ...b, [platform]: 'test' }));
    try {
      const r = await api.post(`/api/integrations/test/${platform}`);
      toast.success(`Connection good · ${r.data.found} ${platform === 'saleshandy' ? 'sequence' : 'campaign'}${r.data.found === 1 ? '' : 's'} found`);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Test failed');
    } finally { setBusy(b => ({ ...b, [platform]: null })); }
  };

  const disconnect = async (platform) => {
    if (!window.confirm(`Disconnect ${platform === 'saleshandy' ? 'SalesHandy' : 'Lemlist'}? Your API key will be removed from ARIA.`)) return;
    setBusy(b => ({ ...b, [platform]: 'disconnect' }));
    try {
      await api.delete(`/api/integrations/keys/${platform}`);
      toast.success('Disconnected');
      await refresh();
    } catch { toast.error('Failed to disconnect'); }
    finally { setBusy(b => ({ ...b, [platform]: null })); }
  };

  const pollSalesHandy = async () => {
    setBusy(b => ({ ...b, saleshandy_poll: true }));
    try {
      const r = await api.post('/api/integrations/saleshandy/poll');
      toast.success(`Synced ${r.data.events_synced} new event${r.data.events_synced === 1 ? '' : 's'}`);
    } catch (err) { toast.error(err.response?.data?.detail || 'Sync failed'); }
    finally { setBusy(b => ({ ...b, saleshandy_poll: false })); }
  };

  if (loading) return <div className="text-sm text-[#9B8AB0] p-6">Loading integrations…</div>;

  return (
    <div className="space-y-6" data-testid="sales-engagement-page">
      <PageHeader
        eyebrow="ARIA · Sales engagement"
        title="Connect SalesHandy and Lemlist"
        subtitle="Bring your cold outreach replies, opens and meetings into ARIA's Lead Feed — and push hot ARIA leads into your sequences in one tap. Bring-your-own-key, encrypted at rest."
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="se-grid">
        {PLATFORMS.map(p => {
          const s = status[p.id] || {};
          const connected = !!s.connected;
          return (
            <div key={p.id} className="bg-white border border-[#E8E0F5] rounded-2xl p-6" style={{ boxShadow: 'var(--shadow-card)' }} data-testid={`se-card-${p.id}`}>
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: `${p.color}14`, border: `1px solid ${p.color}33` }}>
                  <Plug size={20} weight="fill" style={{ color: p.color }} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <h3 className="text-lg font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{p.name}</h3>
                    {connected ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-[#DCFCE7] text-[#16A34A] border border-[#16A34A]/30">
                        <CheckCircle size={10} weight="fill" /> CONNECTED
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-[#FEF3C7] text-[#D97706] border border-[#FDE68A]">NOT CONNECTED</span>
                    )}
                  </div>
                  <p className="text-sm text-[#5A4A7A] leading-relaxed">{p.blurb}</p>
                  <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#7B6D9C] mt-2">Inbound · {p.inboundMode}</div>
                </div>
              </div>

              {connected ? (
                <div className="mt-4 space-y-3">
                  <div className="flex items-center justify-between bg-[#FAF7FF] border border-[#EDE5FA] rounded-xl px-3 py-2 flex-wrap gap-2">
                    <div className="text-xs">
                      <span className="text-[#9B8AB0]">API key:</span>
                      <span className="ml-2 font-mono text-[#1A0A2E]" data-testid={`${p.id}-key-preview`}>{s.key_preview || '••••'}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <button onClick={() => test(p.id)} disabled={!!busy[p.id]} data-testid={`${p.id}-test-btn`}
                        className="text-xs font-bold text-[#7C35DC] hover:underline disabled:opacity-50">
                        {busy[p.id] === 'test' ? 'Testing…' : 'Test connection'}
                      </button>
                      <span className="text-[#E0D4F7]">·</span>
                      <button onClick={() => disconnect(p.id)} disabled={!!busy[p.id]} data-testid={`${p.id}-disconnect-btn`}
                        className="text-xs font-bold text-[#DC2626] hover:underline disabled:opacity-50 inline-flex items-center gap-1">
                        <Trash size={12} weight="fill" /> Disconnect
                      </button>
                    </div>
                  </div>
                  {p.id === 'saleshandy' && (
                    <button onClick={pollSalesHandy} disabled={!!busy.saleshandy_poll} data-testid="saleshandy-poll-btn"
                      className="w-full inline-flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-xs font-bold text-[#7C35DC] bg-white border border-[#7C35DC]/30 hover:bg-[#F4F0FF]">
                      <ArrowsClockwise size={14} weight="bold" />{busy.saleshandy_poll ? 'Syncing…' : 'Sync recent activity now'}
                    </button>
                  )}
                  {p.id === 'lemlist' && (
                    <div className="text-[11px] text-[#5A4A7A] bg-[#F4F0FF] border border-[#E0D4F7] rounded-xl px-3 py-2">
                      <Sparkle size={11} weight="fill" className="inline text-[#7C35DC] mr-1" />
                      Webhook auto-registered. Replies, opens, clicks, and meetings will arrive in real time.
                    </div>
                  )}
                </div>
              ) : (
                <div className="mt-4 space-y-3">
                  <div className="text-xs text-[#5A4A7A]"><span className="font-bold text-[#1A0A2E]">Where to get the key:</span> {p.keyHelp}</div>
                  <div className="relative">
                    <input
                      type={show[p.id] ? 'text' : 'password'}
                      value={keys[p.id] || ''}
                      onChange={(e) => setKeys(k => ({ ...k, [p.id]: e.target.value }))}
                      placeholder={`Paste ${p.name} API key`}
                      data-testid={`${p.id}-key-input`}
                      className="w-full px-3 py-2.5 pr-10 rounded-xl border border-[#E8E0F5] focus:border-[#7C35DC] focus:ring-2 focus:ring-[#7C35DC]/20 text-sm font-mono"
                    />
                    <button type="button" onClick={() => setShow(s => ({ ...s, [p.id]: !s[p.id] }))}
                      className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-[#9B8AB0] hover:text-[#7C35DC]"
                      data-testid={`${p.id}-toggle-show`}>
                      {show[p.id] ? <EyeSlash size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <a href={p.docsUrl} target="_blank" rel="noopener noreferrer" className="text-xs font-bold text-[#7C35DC] hover:underline inline-flex items-center gap-1">
                      Open API docs <ArrowSquareOut size={11} weight="bold" />
                    </a>
                    <button onClick={() => save(p.id)} disabled={!!busy[p.id]} data-testid={`${p.id}-save-btn`}
                      className="px-4 py-2 rounded-xl text-xs font-bold text-white disabled:opacity-50"
                      style={{ background: 'var(--gradient-brand)' }}>
                      {busy[p.id] === 'save' ? 'Connecting…' : 'Connect'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="bg-[#F4F0FF] border border-[#E0D4F7] rounded-2xl px-5 py-4 flex items-start gap-3" data-testid="se-help">
        <Warning size={16} weight="fill" className="text-[#7C35DC] mt-0.5 flex-shrink-0" />
        <div className="text-xs text-[#5A4A7A] leading-relaxed">
          <span className="font-extrabold text-[#1A0A2E]">Privacy:</span> API keys are encrypted (Fernet AES-128) before being saved to MongoDB and never logged. Each workspace stores its own keys — perfect for client deployments.
        </div>
      </div>

      <AutomationRules status={status} />
    </div>
  );
};

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// Automation rules — auto-push leads to sequences when triggers fire
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

const TRIGGERS = [
  { id: 'status', label: 'Status changes to', values: ['new', 'contacted', 'qualified', 'proposal_sent', 'negotiation', 'won', 'lost'] },
  { id: 'source', label: 'Source channel is', values: ['website_form', 'whatsapp', 'linkedin', 'email', 'referral', 'webinar', 'paid', 'other'] },
  { id: 'icp_tier', label: 'ICP tier is', values: ['hot', 'warm', 'cold'] },
];

const AutomationRules = ({ status }) => {
  const [rules, setRules] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ platform: 'lemlist', trigger: 'status', trigger_value: 'qualified', sequence_id: '', sequence_name: '' });
  const [sequences, setSequences] = useState([]);
  const [busy, setBusy] = useState(false);

  const refresh = async () => {
    try { const r = await api.get('/api/integrations/automation/rules'); setRules(r.data.rules || []); } catch { /* */ }
  };
  useEffect(() => { refresh(); }, []);

  // Load sequences when platform changes in the form
  useEffect(() => {
    if (!showForm || !status[form.platform]?.connected) { setSequences([]); return; }
    api.get(`/api/integrations/sequences/${form.platform}`).then(r => {
      setSequences(r.data.sequences || []);
      if (r.data.sequences?.[0]) setForm(f => ({ ...f, sequence_id: r.data.sequences[0].id, sequence_name: r.data.sequences[0].name }));
    }).catch(() => setSequences([]));
  }, [form.platform, showForm, status]);

  const submit = async () => {
    if (!form.sequence_id) { toast.error('Pick a sequence'); return; }
    setBusy(true);
    try {
      await api.post('/api/integrations/automation/rules', form);
      toast.success('Rule created · ARIA will auto-push when this trigger fires');
      setShowForm(false); setForm({ platform: 'lemlist', trigger: 'status', trigger_value: 'qualified', sequence_id: '', sequence_name: '' });
      refresh();
    } catch (err) { toast.error(err.response?.data?.detail || 'Could not save rule'); }
    finally { setBusy(false); }
  };

  const toggle = async (id) => { try { await api.patch(`/api/integrations/automation/rules/${id}`); refresh(); } catch { toast.error('Could not toggle'); } };
  const remove = async (id) => { if (!window.confirm('Delete this rule?')) return; try { await api.delete(`/api/integrations/automation/rules/${id}`); refresh(); } catch { toast.error('Could not delete'); } };

  const [testResults, setTestResults] = useState({});
  const [testing, setTesting] = useState(null);
  const testRule = async (id) => {
    setTesting(id);
    try {
      const r = await api.post(`/api/integrations/automation/rules/${id}/test`);
      setTestResults(prev => ({ ...prev, [id]: r.data }));
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Test failed');
    } finally { setTesting(null); }
  };

  const noConnection = !status.saleshandy?.connected && !status.lemlist?.connected;
  const triggerMeta = TRIGGERS.find(t => t.id === form.trigger);

  return (
    <div className="bg-white border border-[#E8E0F5] rounded-2xl overflow-hidden" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="automation-rules">
      <div className="px-6 py-4 border-b border-[#F0ECF9] flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: 'var(--gradient-brand)' }}>
            <Lightning size={18} weight="fill" className="text-white" />
          </div>
          <div>
            <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC]" style={{ fontFamily: 'Plus Jakarta Sans' }}>AUTOMATION RULES</div>
            <h3 className="text-lg font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Auto-push leads when triggers fire</h3>
          </div>
        </div>
        <button onClick={() => setShowForm(true)} disabled={noConnection} data-testid="add-rule-btn"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold text-white disabled:opacity-40"
          style={{ background: 'var(--gradient-brand)' }}>
          <Plus size={14} weight="bold" /> New rule
        </button>
      </div>

      {noConnection ? (
        <div className="px-6 py-8 text-center text-sm text-[#9B8AB0]">Connect SalesHandy or Lemlist above to create automation rules.</div>
      ) : rules.length === 0 && !showForm ? (
        <div className="px-6 py-8 text-center" data-testid="rules-empty-state">
          <p className="text-sm text-[#5A4A7A]">No rules yet. Set ARIA to auto-push leads to a sequence when status changes, source matches, or ICP tier hits hot.</p>
        </div>
      ) : (
        <div className="divide-y divide-[#F0ECF9]">
          {rules.map(r => (
            <div key={r.id} className="px-6 py-4" data-testid={`rule-${r.id}`}>
              <div className="flex items-center gap-3 flex-wrap">
              <span className="px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-[0.18em] text-white" style={{ background: r.platform === 'saleshandy' ? '#16A34A' : '#7C35DC' }}>
                {r.platform === 'saleshandy' ? 'SalesHandy' : 'Lemlist'}
              </span>
              <div className="flex-1 min-w-0 text-sm">
                <span className="text-[#5A4A7A]">When</span> <span className="font-bold text-[#1A0A2E]">{r.trigger.replace('_', ' ')}</span> <span className="text-[#5A4A7A]">=</span> <span className="font-bold text-[#7C35DC]">{r.trigger_value}</span> <span className="text-[#5A4A7A]">→ push to</span> <span className="font-bold text-[#1A0A2E]">{r.sequence_name || r.sequence_id.slice(0, 12)}</span>
              </div>
              {r.runs > 0 && <span className="text-[10px] text-[#9B8AB0]">{r.runs} run{r.runs === 1 ? '' : 's'}</span>}
              <button onClick={() => testRule(r.id)} disabled={testing === r.id} data-testid={`rule-test-${r.id}`}
                className="px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-[0.15em] bg-[#F4F0FF] text-[#7C35DC] border border-[#7C35DC]/25 hover:bg-[#EDE4FF] disabled:opacity-50">
                {testing === r.id ? 'Testing…' : 'Test'}
              </button>
              <button onClick={() => toggle(r.id)} data-testid={`rule-toggle-${r.id}`}
                className={`px-2 py-1 rounded-md text-[10px] font-bold uppercase tracking-[0.15em] ${r.active ? 'bg-[#DCFCE7] text-[#16A34A] border border-[#16A34A]/30' : 'bg-[#F1F5F9] text-[#9B8AB0] border border-[#E2E8F0]'}`}>
                {r.active ? 'ON' : 'OFF'}
              </button>
              <button onClick={() => remove(r.id)} data-testid={`rule-delete-${r.id}`}
                className="text-[#9B8AB0] hover:text-[#DC2626]">
                <Trash size={14} weight="fill" />
              </button>
              </div>
              {testResults[r.id] && (
                <div className="mt-3 p-3 rounded-lg bg-[#FAF7FF] border border-[#E8E0F5]" data-testid={`rule-test-result-${r.id}`}>
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-[10px] font-bold uppercase tracking-[0.15em] px-2 py-0.5 rounded-md ${testResults[r.id].would_run ? 'bg-[#DCFCE7] text-[#16A34A]' : 'bg-[#FEF3C7] text-[#D97706]'}`}>
                      {testResults[r.id].would_run ? 'Would push' : 'Would skip'}
                    </span>
                    <span className="text-xs text-[#5A4A7A]">{testResults[r.id].reason}</span>
                  </div>
                  {testResults[r.id].sample && (
                    <div className="text-xs text-[#1A0A2E]">
                      Sample lead: <span className="font-bold">{testResults[r.id].sample.name}</span>
                      {testResults[r.id].sample.company && <span className="text-[#5A4A7A]"> · {testResults[r.id].sample.company}</span>}
                      <span className="text-[#9B8AB0]"> · {testResults[r.id].sample.email}</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {showForm && (
        <div className="border-t border-[#F0ECF9] bg-[#FAF7FF] px-6 py-5 space-y-3" data-testid="rule-form">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-[0.2em] text-[#7B6D9C] mb-1.5">Push to</label>
              <select value={form.platform} onChange={(e) => setForm({ ...form, platform: e.target.value })} data-testid="rule-platform-select"
                className="w-full px-3 py-2 rounded-lg border border-[#E8E0F5] focus:ring-2 focus:ring-[#7C35DC]/20 text-sm">
                {status.lemlist?.connected && <option value="lemlist">Lemlist</option>}
                {status.saleshandy?.connected && <option value="saleshandy">SalesHandy</option>}
              </select>
            </div>
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-[0.2em] text-[#7B6D9C] mb-1.5">{form.platform === 'saleshandy' ? 'Sequence' : 'Campaign'}</label>
              <select value={form.sequence_id} onChange={(e) => {
                const seq = sequences.find(s => s.id === e.target.value);
                setForm({ ...form, sequence_id: e.target.value, sequence_name: seq?.name || '' });
              }} data-testid="rule-sequence-select" className="w-full px-3 py-2 rounded-lg border border-[#E8E0F5] focus:ring-2 focus:ring-[#7C35DC]/20 text-sm">
                {sequences.length === 0 ? <option value="">Loading…</option> : sequences.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-[0.2em] text-[#7B6D9C] mb-1.5">Trigger</label>
              <select value={form.trigger} onChange={(e) => setForm({ ...form, trigger: e.target.value, trigger_value: TRIGGERS.find(t => t.id === e.target.value).values[0] })}
                data-testid="rule-trigger-select" className="w-full px-3 py-2 rounded-lg border border-[#E8E0F5] focus:ring-2 focus:ring-[#7C35DC]/20 text-sm">
                {TRIGGERS.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-[0.2em] text-[#7B6D9C] mb-1.5">Value</label>
              <select value={form.trigger_value} onChange={(e) => setForm({ ...form, trigger_value: e.target.value })}
                data-testid="rule-value-select" className="w-full px-3 py-2 rounded-lg border border-[#E8E0F5] focus:ring-2 focus:ring-[#7C35DC]/20 text-sm">
                {triggerMeta.values.map(v => <option key={v} value={v}>{v}</option>)}
              </select>
            </div>
          </div>
          <div className="text-[11px] text-[#5A4A7A] bg-white border border-[#E8E0F5] rounded-xl px-3 py-2">
            <span className="font-bold text-[#1A0A2E]">Preview:</span> When a lead's <span className="font-bold text-[#7C35DC]">{form.trigger.replace('_', ' ')}</span> changes to <span className="font-bold text-[#7C35DC]">{form.trigger_value}</span>, ARIA will push it to <span className="font-bold text-[#1A0A2E]">{form.sequence_name || '—'}</span> on {form.platform === 'saleshandy' ? 'SalesHandy' : 'Lemlist'}.
          </div>
          <div className="flex justify-end gap-2">
            <button onClick={() => setShowForm(false)} className="px-4 py-2 rounded-lg text-sm font-semibold text-[#5A4A7A] hover:bg-white" data-testid="rule-cancel-btn">Cancel</button>
            <button onClick={submit} disabled={busy || !form.sequence_id} data-testid="rule-save-btn"
              className="px-4 py-2 rounded-lg text-sm font-bold text-white disabled:opacity-50"
              style={{ background: 'var(--gradient-brand)' }}>
              {busy ? 'Saving…' : 'Save rule'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default SalesEngagement;
