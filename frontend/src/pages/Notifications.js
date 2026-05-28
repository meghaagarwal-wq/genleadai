/**
 * Settings → Notifications
 *
 * Single page that drives three configs from the same form:
 *   1. Morning Brief (8 AM cron)
 *   2. Approval Digest (8 PM cron)
 *   3. Auto-approve rule (fit_score + intent + channel + daily cap)
 *
 * Backend:
 *   GET  /api/aria/settings/notifications  → { morning_brief, approval_digest, auto_approve }
 *   POST /api/aria/settings/notifications  → save any subset
 *
 * + Test buttons:
 *   POST /api/aria/morning-brief/send-now
 *   POST /api/aria/approval-digest/send-now
 */
import { useEffect, useState } from 'react';
import {
  Sun, Moon, Robot, FloppyDisk, PaperPlaneRight, Brain, Sparkle, Warning,
} from '@phosphor-icons/react';
import { toast } from 'sonner';
import api from '../config/api';

const INTENT_OPTIONS = ['positive', 'interested', 'neutral_followup', 'objection'];
const CHANNEL_OPTIONS = ['email', 'whatsapp', 'linkedin'];

const TZ_OPTIONS = [
  { label: 'UTC',          value: 0.0 },
  { label: 'IST (+5:30)',  value: 5.5 },
  { label: 'EST (-5:00)',  value: -5.0 },
  { label: 'PST (-8:00)',  value: -8.0 },
  { label: 'GMT (+0)',     value: 0.0 },
  { label: 'CET (+1)',     value: 1.0 },
  { label: 'SGT/HKT (+8)', value: 8.0 },
];

const Notifications = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [mb, setMb] = useState(null);
  const [ad, setAd] = useState(null);
  const [aa, setAa] = useState(null);
  // Pristine snapshot used to compute dirty-state for the Save button.
  const [pristine, setPristine] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await api.get('/api/aria/settings/notifications');
        setMb(r.data.morning_brief);
        setAd(r.data.approval_digest);
        setAa(r.data.auto_approve);
        setPristine(JSON.stringify({
          morning_brief: r.data.morning_brief,
          approval_digest: r.data.approval_digest,
          auto_approve: r.data.auto_approve,
        }));
      } catch {
        toast.error('Could not load notification settings');
      } finally { setLoading(false); }
    })();
  }, []);

  const isDirty = pristine !== null && JSON.stringify({
    morning_brief: mb, approval_digest: ad, auto_approve: aa,
  }) !== pristine;

  const save = async () => {
    setSaving(true);
    try {
      await api.post('/api/aria/settings/notifications', {
        morning_brief: mb,
        approval_digest: ad,
        auto_approve: aa,
      });
      toast.success('Notification settings saved');
      // Re-baseline so Save disables again until the next change.
      setPristine(JSON.stringify({
        morning_brief: mb, approval_digest: ad, auto_approve: aa,
      }));
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Save failed');
    } finally { setSaving(false); }
  };

  const sendMorningNow = async () => {
    try {
      const r = await api.post('/api/aria/morning-brief/send-now');
      if (r.data.sent) toast.success('Morning brief sent');
      else toast.info(r.data.error || 'Sent (preview) — check inbox');
    } catch (err) { toast.error(err.response?.data?.detail || 'Send failed'); }
  };
  const sendDigestNow = async () => {
    try {
      const r = await api.post('/api/aria/approval-digest/send-now');
      if (r.data.skipped) toast.info(`Skipped — ${r.data.reason}`);
      else if (r.data.sent) toast.success('Digest sent');
      else toast.info(r.data.error || 'Sent (preview) — check inbox');
    } catch (err) { toast.error(err.response?.data?.detail || 'Send failed'); }
  };

  if (loading || !mb || !ad || !aa) {
    return <div className="p-8 text-center text-sm text-[#64748B]">Loading…</div>;
  }

  return (
    <div className="p-6 max-w-3xl mx-auto" data-testid="notifications-page">
      <div className="mb-6">
        <div className="flex items-center gap-2 mb-1">
          <Brain size={18} weight="duotone" className="text-[#7C35DC]" />
          <span className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#7C35DC]">Settings → Notifications</span>
        </div>
        <h1 className="text-2xl font-extrabold text-[#0F172A]" style={{ fontFamily: 'Space Grotesk, Inter' }}>
          Tell ARIA when to talk to you
        </h1>
        <p className="text-sm text-[#64748B] mt-1 max-w-xl">
          Two daily emails and one autonomous rule. Together they make ARIA usable with a single touch in the morning, a single click at night, and zero clicks when she's confident.
        </p>
      </div>

      {/* Morning Brief */}
      <Card icon={Sun} title="Morning Brief" testid="card-morning-brief"
        subtitle="8 AM digest: top 3 hot prospects · signals · draft openers.">
        <Toggle label="Enabled" checked={mb.enabled} onChange={(v) => setMb({ ...mb, enabled: v })} testid="mb-toggle" />
        <Input label="Send to email" value={mb.send_to_email} onChange={(v) => setMb({ ...mb, send_to_email: v })} testid="mb-email" />
        <Row>
          <NumInput label="Hour (local)" min={0} max={23} value={mb.send_hour_local} onChange={(v) => setMb({ ...mb, send_hour_local: v })} testid="mb-hour" />
          <TzSelect label="Timezone" value={mb.timezone_offset_hours} onChange={(v) => setMb({ ...mb, timezone_offset_hours: v })} testid="mb-tz" />
        </Row>
        <Toggle label="Weekdays only" checked={mb.weekdays_only} onChange={(v) => setMb({ ...mb, weekdays_only: v })} testid="mb-weekdays" />
        <NumInput label="Max new intel per run" min={1} max={50} value={mb.max_new_intel} onChange={(v) => setMb({ ...mb, max_new_intel: v })} testid="mb-max-intel" />
        <TestButton label="Send a brief now" onClick={sendMorningNow} testid="mb-send-now" />
      </Card>

      {/* Approval Digest */}
      <Card icon={Moon} title="Approval Digest" testid="card-approval-digest"
        subtitle="8 PM email of every pending draft. One-click approve from inbox.">
        <Toggle label="Enabled" checked={ad.enabled} onChange={(v) => setAd({ ...ad, enabled: v })} testid="ad-toggle" />
        <Input label="Send to email" value={ad.send_to_email} onChange={(v) => setAd({ ...ad, send_to_email: v })} testid="ad-email" />
        <Row>
          <NumInput label="Hour (local)" min={0} max={23} value={ad.send_hour_local} onChange={(v) => setAd({ ...ad, send_hour_local: v })} testid="ad-hour" />
          <TzSelect label="Timezone" value={ad.timezone_offset_hours} onChange={(v) => setAd({ ...ad, timezone_offset_hours: v })} testid="ad-tz" />
        </Row>
        <Toggle label="Weekdays only" checked={ad.weekdays_only} onChange={(v) => setAd({ ...ad, weekdays_only: v })} testid="ad-weekdays" />
        <TestButton label="Send a digest now" onClick={sendDigestNow} testid="ad-send-now" />
      </Card>

      {/* Auto-Approve Rule */}
      <Card icon={Robot} title="Auto-Approve Rule" testid="card-auto-approve"
        subtitle="When confidence is high, skip the approval queue and let ARIA send immediately.">
        <Toggle label="Enabled" checked={aa.enabled} onChange={(v) => setAa({ ...aa, enabled: v })} testid="aa-toggle" />
        <NumInput label="Min ICP fit score (0-100)" min={0} max={100} value={aa.min_fit_score} onChange={(v) => setAa({ ...aa, min_fit_score: v })} testid="aa-fit" />

        <div className="mb-3">
          <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#475569] mb-1">Allowed intents</div>
          <div className="flex flex-wrap gap-1.5">
            {INTENT_OPTIONS.map((it) => {
              const on = (aa.allowed_intents || []).includes(it);
              return (
                <button key={it} type="button"
                  onClick={() => setAa({
                    ...aa,
                    allowed_intents: on
                      ? aa.allowed_intents.filter((x) => x !== it)
                      : [...aa.allowed_intents, it],
                  })}
                  data-testid={`aa-intent-${it}`}
                  className={`px-2.5 py-1 rounded-md text-xs font-semibold capitalize border ${on ? 'border-transparent text-white' : 'border-[#E2E8F0] text-[#475569] hover:bg-[#F8FAFC]'}`}
                  style={on ? { background: 'linear-gradient(135deg, #4C1D95 0%, #7C35DC 100%)' } : {}}
                >{it.replace(/_/g, ' ')}</button>
              );
            })}
          </div>
        </div>

        <div className="mb-3">
          <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#475569] mb-1">Allowed channels</div>
          <div className="flex flex-wrap gap-1.5">
            {CHANNEL_OPTIONS.map((c) => {
              const on = (aa.allowed_channels || []).includes(c);
              return (
                <button key={c} type="button"
                  onClick={() => setAa({
                    ...aa,
                    allowed_channels: on
                      ? aa.allowed_channels.filter((x) => x !== c)
                      : [...aa.allowed_channels, c],
                  })}
                  data-testid={`aa-channel-${c}`}
                  className={`px-2.5 py-1 rounded-md text-xs font-semibold capitalize border ${on ? 'border-transparent text-white' : 'border-[#E2E8F0] text-[#475569] hover:bg-[#F8FAFC]'}`}
                  style={on ? { background: 'linear-gradient(135deg, #4C1D95 0%, #7C35DC 100%)' } : {}}
                >{c}</button>
              );
            })}
          </div>
        </div>

        <NumInput label="Daily cap (safety)" min={0} max={500} value={aa.max_per_day} onChange={(v) => setAa({ ...aa, max_per_day: v })} testid="aa-cap" />

        <div className="mt-2 p-2.5 rounded-md text-xs border border-amber-200" style={{ background: '#FFFBEB' }}>
          <div className="flex items-start gap-1.5">
            <Warning size={11} weight="fill" className="text-amber-600 mt-0.5 flex-shrink-0" />
            <div className="text-amber-900">
              Auto-approved sends bypass your review. They appear in <b>Conversations → Thread</b> and the <b>outbound_log</b> with actor <code>aria-auto-approve</code>. Daily cap is a hard limit.
            </div>
          </div>
        </div>
      </Card>

      <div className="mt-6 flex items-center justify-end gap-2">
        <button onClick={save} disabled={saving || !isDirty} data-testid="notifications-save"
          className="inline-flex items-center gap-1.5 px-5 py-2.5 rounded-md text-sm font-bold text-white disabled:opacity-50"
          style={{ background: 'linear-gradient(135deg, #4C1D95 0%, #7C35DC 100%)' }}>
          <FloppyDisk size={13} weight="fill" /> {saving ? 'Saving…' : 'Save changes'}
        </button>
      </div>
    </div>
  );
};

// ─── Tiny sub-components ──
const Card = ({ icon: Icon, title, subtitle, testid, children }) => (
  <div className="bg-white border border-[#E2E8F0] rounded-lg overflow-hidden mb-4" data-testid={testid}>
    <div className="px-4 py-3 border-b border-[#E2E8F0] bg-[#FAFAFA] flex items-center gap-2">
      {Icon && <Icon size={16} weight="duotone" className="text-[#7C35DC]" />}
      <div>
        <h3 className="text-sm font-bold text-[#0F172A]" style={{ fontFamily: 'Space Grotesk, Inter' }}>{title}</h3>
        {subtitle && <p className="text-xs text-[#64748B]">{subtitle}</p>}
      </div>
    </div>
    <div className="p-4">{children}</div>
  </div>
);
const Row = ({ children }) => <div className="grid grid-cols-2 gap-3 mb-3">{children}</div>;
const Toggle = ({ label, checked, onChange, testid }) => (
  <label className="flex items-center gap-2 mb-3 cursor-pointer">
    <input type="checkbox" checked={!!checked} onChange={(e) => onChange(e.target.checked)} className="rounded text-[#7C35DC]" data-testid={testid} />
    <span className="text-sm text-[#0F172A]">{label}</span>
  </label>
);
const Input = ({ label, value, onChange, testid }) => (
  <div className="mb-3">
    <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#475569] mb-1">{label}</div>
    <input type="text" value={value || ''} onChange={(e) => onChange(e.target.value)} data-testid={testid}
      className="w-full text-sm border border-[#E2E8F0] rounded-md px-2.5 py-1.5 outline-none focus:border-[#7C35DC]" />
  </div>
);
const NumInput = ({ label, value, min, max, onChange, testid }) => (
  <div className="mb-3">
    <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#475569] mb-1">{label}</div>
    <input type="number" min={min} max={max} value={value ?? 0} onChange={(e) => onChange(Number(e.target.value))} data-testid={testid}
      className="w-full text-sm border border-[#E2E8F0] rounded-md px-2.5 py-1.5 outline-none focus:border-[#7C35DC]" />
  </div>
);
const TzSelect = ({ label, value, onChange, testid }) => (
  <div className="mb-3">
    <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#475569] mb-1">{label}</div>
    <select value={value ?? 0} onChange={(e) => onChange(Number(e.target.value))} data-testid={testid}
      className="w-full text-sm border border-[#E2E8F0] rounded-md px-2.5 py-1.5 outline-none focus:border-[#7C35DC] bg-white">
      {TZ_OPTIONS.map((o) => <option key={o.label} value={o.value}>{o.label}</option>)}
    </select>
  </div>
);
const TestButton = ({ label, onClick, testid }) => (
  <button onClick={onClick} data-testid={testid}
    className="mt-1 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold text-[#7C35DC] border border-[#7C35DC]/40 hover:bg-[#FAF7FF]">
    <PaperPlaneRight size={11} weight="bold" /> {label}
  </button>
);

export default Notifications;
