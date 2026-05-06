import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { CheckCircle, Warning, Plug, Eye, EyeSlash, ArrowSquareOut, Trash, ArrowsClockwise, Sparkle } from '@phosphor-icons/react';
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
    </div>
  );
};

export default SalesEngagement;
