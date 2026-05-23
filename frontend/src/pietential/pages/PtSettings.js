import { useEffect, useState } from 'react';
import { EnvelopeSimple, PaperPlaneTilt, CheckCircle, ShieldCheck } from '@phosphor-icons/react';
import { toast } from 'sonner';
import { ptApi, PageHeader } from '../shared';

const PtSettings = () => {
  const [data, setData] = useState(null);
  const [emailCfg, setEmailCfg] = useState(null);
  const [fromName, setFromName] = useState('');
  const [fromAddr, setFromAddr] = useState('');
  const [resendKey, setResendKey] = useState('');
  const [saving, setSaving] = useState(false);
  const [testTo, setTestTo] = useState('');
  const [sending, setSending] = useState(false);

  useEffect(() => {
    ptApi.get('/api/pt/scoring-rules').then((r) => setData(r.data)).catch(() => {});
    loadEmail();
  }, []);

  const loadEmail = async () => {
    try {
      const r = await ptApi.get('/api/pt/email/config');
      setEmailCfg(r.data);
      setFromName(r.data?.from_name || '');
      setFromAddr(r.data?.from_address || '');
    } catch (e) {
      setEmailCfg(null);
    }
  };

  const saveEmail = async () => {
    setSaving(true);
    try {
      await ptApi.post('/api/pt/email/config', {
        from_name: fromName.trim() || null,
        from_address: fromAddr.trim() || null,
        resend_api_key: resendKey.trim() || null,
      });
      setResendKey('');
      toast.success('Sender config saved');
      loadEmail();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not save sender config', { duration: 8000 });
    } finally {
      setSaving(false);
    }
  };

  const testSend = async () => {
    if (!testTo.trim()) {
      toast.error('Add a recipient email first');
      return;
    }
    setSending(true);
    try {
      const r = await ptApi.post('/api/pt/email/test-send', { to: testTo.trim() });
      toast.success(r.data?.message || 'Test email sent', { duration: 6000 });
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Test send failed', { duration: 8000 });
    } finally {
      setSending(false);
    }
  };

  if (!data) return <div className="text-sm text-[#64748B]">Loading…</div>;

  return (
    <div data-testid="pt-settings-page">
      <PageHeader title="Settings" subtitle="Email sender, scoring rules, stage boundaries, and decay logic." />

      {/* Email sender */}
      <div className="bg-white border border-[#E2E8F0] rounded-lg overflow-hidden mb-6" data-testid="pt-email-sender-card">
        <div className="px-4 py-2.5 bg-[#F8FAFC] border-b border-[#E2E8F0] flex items-center gap-2">
          <EnvelopeSimple size={14} className="text-[#7C35DC]" weight="duotone" />
          <h3 className="text-xs font-bold uppercase tracking-[0.16em] text-[#475569]">Email sender</h3>
          {emailCfg?.using_global_fallback ? (
            <span className="ml-auto text-[10px] font-semibold uppercase tracking-wider text-[#B45309] bg-[#FEF3C7] px-2 py-0.5 rounded">Using platform default</span>
          ) : (
            <span className="ml-auto text-[10px] font-semibold uppercase tracking-wider text-[#16A34A] bg-[#DCFCE7] px-2 py-0.5 rounded inline-flex items-center gap-1"><CheckCircle size={11} weight="fill" /> Workspace key</span>
          )}
        </div>
        <div className="p-4 space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <label className="block">
              <div className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#64748B] mb-1">From name</div>
              <input
                value={fromName}
                onChange={(e) => setFromName(e.target.value)}
                placeholder="John from Pietential"
                data-testid="pt-email-from-name"
                className="w-full text-sm border border-[#CBD5E1] rounded-md px-3 py-2 outline-none focus:ring-2 focus:ring-[#C044E0]/20"
              />
            </label>
            <label className="block">
              <div className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#64748B] mb-1">From address</div>
              <input
                value={fromAddr}
                onChange={(e) => setFromAddr(e.target.value)}
                placeholder="john@pietential.com"
                data-testid="pt-email-from-address"
                className="w-full text-sm border border-[#CBD5E1] rounded-md px-3 py-2 outline-none focus:ring-2 focus:ring-[#C044E0]/20"
              />
            </label>
          </div>
          <label className="block">
            <div className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#64748B] mb-1 flex items-center gap-1.5">
              Resend API key <ShieldCheck size={11} weight="duotone" className="text-[#16A34A]" />
              {emailCfg?.resend_api_key_masked && <span className="text-[#94A3B8] font-mono normal-case tracking-normal ml-1">current: {emailCfg.resend_api_key_masked}</span>}
            </div>
            <input
              type="password"
              value={resendKey}
              onChange={(e) => setResendKey(e.target.value)}
              placeholder={emailCfg?.resend_api_key_masked ? 'Leave blank to keep existing key' : 'Paste your Resend API key'}
              data-testid="pt-email-resend-key"
              className="w-full text-sm border border-[#CBD5E1] rounded-md px-3 py-2 outline-none focus:ring-2 focus:ring-[#C044E0]/20 font-mono"
            />
          </label>
          <div className="flex items-center gap-2">
            <button
              onClick={saveEmail}
              disabled={saving}
              data-testid="pt-email-save-btn"
              className="text-xs font-bold uppercase tracking-wider px-4 py-2 rounded-md bg-[#7C35DC] hover:bg-[#6325B8] text-white disabled:opacity-50"
            >
              {saving ? 'Saving…' : 'Save sender'}
            </button>
            <div className="text-[11px] text-[#94A3B8]">Stored encrypted at rest. Falls back to platform default until you set a workspace key.</div>
          </div>
        </div>
        <div className="border-t border-[#E2E8F0] bg-[#FAFBFC] px-4 py-3 flex items-center gap-3 flex-wrap">
          <input
            type="email"
            value={testTo}
            onChange={(e) => setTestTo(e.target.value)}
            placeholder="founder@yourdomain.com"
            data-testid="pt-email-test-to"
            className="flex-1 min-w-[220px] text-sm border border-[#CBD5E1] rounded-md px-3 py-2 outline-none focus:ring-2 focus:ring-[#C044E0]/20"
          />
          <button
            onClick={testSend}
            disabled={sending || !testTo.trim()}
            data-testid="pt-email-test-send-btn"
            className="text-xs font-bold uppercase tracking-wider px-4 py-2 rounded-md border border-[#7C35DC] text-[#7C35DC] hover:bg-[#7C35DC]/8 disabled:opacity-50 inline-flex items-center gap-1.5"
          >
            <PaperPlaneTilt size={12} weight="fill" /> {sending ? 'Sending…' : 'Send test email'}
          </button>
        </div>
      </div>

      {/* Stage boundaries */}
      <div className="bg-white border border-[#E2E8F0] rounded-lg overflow-hidden mb-4">
        <div className="px-4 py-2.5 bg-[#F8FAFC] border-b border-[#E2E8F0]">
          <h3 className="text-xs font-bold uppercase tracking-[0.16em] text-[#475569]">Stage thresholds</h3>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-[#FAFBFC] border-b border-[#E2E8F0]">
            <tr>
              <th className="px-3 py-1.5 text-left text-[10px] font-bold uppercase tracking-[0.14em] text-[#64748B]">Stage</th>
              <th className="px-3 py-1.5 text-left text-[10px] font-bold uppercase tracking-[0.14em] text-[#64748B]">Range</th>
              <th className="px-3 py-1.5 text-left text-[10px] font-bold uppercase tracking-[0.14em] text-[#64748B]">Automation</th>
            </tr>
          </thead>
          <tbody>
            {data.stages.map((s) => (
              <tr key={s.id} className="border-b border-[#F1F5F9] last:border-0">
                <td className="px-3 py-2 font-semibold text-[#0F172A]">{s.label}</td>
                <td className="px-3 py-2 text-[#475569]">{s.min} – {s.max === 9999 ? '∞' : s.max}</td>
                <td className="px-3 py-2 text-[#475569]">{s.auto}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Scoring rules */}
      <div className="bg-white border border-[#E2E8F0] rounded-lg overflow-hidden mb-4">
        <div className="px-4 py-2.5 bg-[#F8FAFC] border-b border-[#E2E8F0]">
          <h3 className="text-xs font-bold uppercase tracking-[0.16em] text-[#475569]">Scoring rules</h3>
        </div>
        <table className="w-full text-sm" data-testid="pt-settings-rules">
          <thead className="bg-[#FAFBFC] border-b border-[#E2E8F0]">
            <tr>
              {['Source', 'Event', 'Score', 'Triggers pause'].map((h) => (
                <th key={h} className="px-3 py-1.5 text-left text-[10px] font-bold uppercase tracking-[0.14em] text-[#64748B]">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rules.map((r) => (
              <tr key={r.event_type} className="border-b border-[#F1F5F9] last:border-0">
                <td className="px-3 py-2 text-[#475569]">{r.source}</td>
                <td className="px-3 py-2 text-[#0F172A]"><span className="font-medium">{r.label}</span> <span className="text-[10px] text-[#94A3B8] font-mono ml-1">{r.event_type}</span></td>
                <td className={`px-3 py-2 font-bold ${r.score >= 0 ? 'text-[#7C35DC]' : 'text-[#DC2626]'}`}>{r.score >= 0 ? '+' : ''}{r.score}</td>
                <td className="px-3 py-2 text-[#475569]">{r.trigger_pause ? 'Yes' : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Decay */}
      <div className="bg-white border border-[#E2E8F0] rounded-lg overflow-hidden">
        <div className="px-4 py-2.5 bg-[#F8FAFC] border-b border-[#E2E8F0]">
          <h3 className="text-xs font-bold uppercase tracking-[0.16em] text-[#475569]">Score decay</h3>
        </div>
        <div className="p-4 space-y-2">
          {data.decay.map((d, i) => (
            <div key={i} className="flex items-center justify-between text-sm">
              <span className="text-[#475569]">{d.trigger.replace(/_/g, ' ')}</span>
              <span className={`font-bold ${d.score_change >= 0 ? 'text-[#7C35DC]' : 'text-[#DC2626]'}`}>{d.score_change}{d.side_effect && <span className="text-xs text-[#94A3B8] ml-2">+ {d.side_effect.replace(/_/g, ' ')}</span>}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-4 text-xs text-[#94A3B8]">
        Editable scoring rules will be available in a future iteration. Today's values match Pietential's touchpoint roadmap.
      </div>
    </div>
  );
};

export default PtSettings;
