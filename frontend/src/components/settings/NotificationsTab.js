/**
 * NotificationsTab — Settings → Notifications.
 *
 * Per-tenant matrix of (event × channel) toggles + quiet hours.
 * Saves via PUT /api/notifications/preferences (owner/admin only).
 */
import React, { useEffect, useState } from 'react';
import api from '../../config/api';
import { toast } from 'sonner';
import { Bell, EnvelopeSimple, Moon, FloppyDisk } from '@phosphor-icons/react';

const EVENT_META = {
  new_hot_lead:     { label: 'New hot lead',          blurb: 'Aria flags a brand-new ICP-fit lead.' },
  stale_lead_alert: { label: 'Stale lead alert',      blurb: 'A lead has gone quiet for 14+ days.' },
  failed_message:   { label: 'Failed message',        blurb: 'Outbound WhatsApp/email failed to send.' },
  weekly_recap:     { label: 'Weekly recap',          blurb: 'Mon 9am — last week\'s sales summary.' },
  daily_brief:      { label: 'Daily brief',           blurb: '8am — today\'s priority calls.' },
  aria_escalation:  { label: 'Aria escalation',       blurb: 'Aria handed a lead back to you.' },
  meeting_booked:   { label: 'Meeting booked',        blurb: 'A lead booked time on your calendar.' },
};

const NotificationsTab = () => {
  const [prefs, setPrefs] = useState(null);
  const [eventKeys, setEventKeys] = useState([]);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get('/api/notifications/preferences')
      .then(r => { setPrefs(r.data.preferences); setEventKeys(r.data.event_keys); })
      .catch(() => toast.error('Could not load notification preferences'));
  }, []);

  const toggle = (eventKey, channel) => {
    setPrefs(p => {
      const next = { ...p, events: { ...p.events, [eventKey]: { ...p.events[eventKey], [channel]: !p.events[eventKey][channel] } } };
      return next;
    });
    setDirty(true);
  };

  const setField = (k, v) => { setPrefs(p => ({ ...p, [k]: v })); setDirty(true); };

  const save = async () => {
    if (!prefs) return;
    setSaving(true);
    try {
      const r = await api.put('/api/notifications/preferences', {
        events: prefs.events,
        quiet_hours_enabled: prefs.quiet_hours_enabled,
        quiet_start_hour: prefs.quiet_start_hour,
        quiet_end_hour: prefs.quiet_end_hour,
      });
      setPrefs(r.data.preferences);
      setDirty(false);
      toast.success('Notification preferences saved');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  if (!prefs) return <div className="p-6 text-sm text-[#9B8AB0]">Loading…</div>;

  return (
    <div className="space-y-5" data-testid="notifications-tab-panel">
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h2 className="text-lg font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Notification preferences</h2>
          <p className="text-sm text-[#5A4A7A]">Choose which Aria events reach you in-app and via email.</p>
        </div>
        <button
          onClick={save}
          disabled={!dirty || saving}
          data-testid="notif-save-btn"
          className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-extrabold transition-all ${
            dirty ? 'btn-gradient text-white' : 'bg-[#F0ECF9] text-[#9B8AB0] cursor-not-allowed'
          }`}
          style={{ fontFamily: 'Plus Jakarta Sans' }}
        >
          <FloppyDisk size={13} weight="fill" /> {saving ? 'Saving…' : (dirty ? 'Save changes' : 'Saved')}
        </button>
      </div>

      <div className="aria-card-lift bg-white border border-[#E8E0F5] rounded-2xl overflow-hidden" style={{ boxShadow: 'var(--shadow-card)' }}>
        <div className="grid grid-cols-[1fr_72px_72px] gap-4 px-5 py-3 border-b border-[#F0ECF9] bg-[#FAF7FF]">
          <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#5A4A7A]">Event</span>
          <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#5A4A7A] text-center inline-flex items-center justify-center gap-1"><Bell size={11} weight="fill" /> In-app</span>
          <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#5A4A7A] text-center inline-flex items-center justify-center gap-1"><EnvelopeSimple size={11} weight="fill" /> Email</span>
        </div>
        {eventKeys.map(k => {
          const meta = EVENT_META[k] || { label: k, blurb: '' };
          const p = prefs.events[k] || { in_app: false, email: false };
          return (
            <div key={k} className="grid grid-cols-[1fr_72px_72px] gap-4 px-5 py-4 border-b border-[#F0ECF9] last:border-0 items-center" data-testid={`notif-row-${k}`}>
              <div>
                <div className="text-sm font-bold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{meta.label}</div>
                <div className="text-xs text-[#9B8AB0] mt-0.5">{meta.blurb}</div>
              </div>
              <Toggle on={p.in_app} onClick={() => toggle(k, 'in_app')} testid={`notif-${k}-in_app`} />
              <Toggle on={p.email} onClick={() => toggle(k, 'email')} testid={`notif-${k}-email`} />
            </div>
          );
        })}
      </div>

      <div className="aria-card-lift bg-white border border-[#E8E0F5] rounded-2xl p-5" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="quiet-hours-card">
        <div className="flex items-center gap-2 mb-3">
          <Moon size={16} weight="fill" className="text-[#7C35DC]" />
          <h3 className="text-sm font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Quiet hours</h3>
        </div>
        <p className="text-xs text-[#5A4A7A] mb-3">Email notifications pause inside this window. In-app alerts still arrive.</p>
        <div className="flex items-center gap-4 flex-wrap">
          <Toggle on={prefs.quiet_hours_enabled} onClick={() => setField('quiet_hours_enabled', !prefs.quiet_hours_enabled)} testid="notif-quiet-toggle" />
          <div className={`flex items-center gap-2 text-xs ${prefs.quiet_hours_enabled ? 'text-[#1A0A2E]' : 'text-[#9B8AB0]'}`}>
            <span>From</span>
            <select disabled={!prefs.quiet_hours_enabled} value={prefs.quiet_start_hour} onChange={(e) => setField('quiet_start_hour', parseInt(e.target.value))} className="border border-[#E8E0F5] rounded-lg px-2 py-1 text-sm bg-white disabled:bg-[#FAFAFA]" data-testid="notif-quiet-start">
              {Array.from({ length: 24 }).map((_, h) => <option key={h} value={h}>{String(h).padStart(2, '0')}:00</option>)}
            </select>
            <span>to</span>
            <select disabled={!prefs.quiet_hours_enabled} value={prefs.quiet_end_hour} onChange={(e) => setField('quiet_end_hour', parseInt(e.target.value))} className="border border-[#E8E0F5] rounded-lg px-2 py-1 text-sm bg-white disabled:bg-[#FAFAFA]" data-testid="notif-quiet-end">
              {Array.from({ length: 24 }).map((_, h) => <option key={h} value={h}>{String(h).padStart(2, '0')}:00</option>)}
            </select>
          </div>
        </div>
      </div>

      {/* iter105 — Insight Digest card */}
      <InsightDigestCard />
    </div>
  );
};

// iter105 — Settings → Insight Digest toggle + send-at-hour + Send now (dry run)
const InsightDigestCard = () => {
  const [cfg, setCfg] = useState({ enabled: true, send_at_hour: 7 });
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    api.get('/api/pt/notifications/digest/prefs')
      .then((r) => setCfg(r.data))
      .catch(() => toast.error('Could not load digest preferences'))
      .finally(() => setLoading(false));
  }, []);

  const update = async (patch) => {
    const next = { ...cfg, ...patch };
    setCfg(next);
    try {
      await api.put('/api/pt/notifications/digest/prefs', patch);
      toast.success('Digest preferences saved');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Save failed');
    }
  };

  const sendNow = async () => {
    setSending(true);
    try {
      const { data } = await api.post('/api/pt/notifications/digest/send', { dry_run: false });
      if (data.sent) toast.success(`Digest sent (${data.card_count} cards) → ${data.email}`);
      else if (data.reason === 'no_cards') toast.info('No new or resurfaced cards to digest right now');
      else toast.error(data.reason || 'Digest could not be sent');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Send failed');
    } finally {
      setSending(false);
    }
  };

  if (loading) return null;
  return (
    <div className="aria-card-lift bg-white border border-[#E8E0F5] rounded-2xl p-5" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="insight-digest-card">
      <div className="flex items-center gap-2 mb-3">
        <EnvelopeSimple size={16} weight="fill" className="text-[#7C35DC]" />
        <h3 className="text-sm font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Daily Insight Digest Email</h3>
      </div>
      <p className="text-xs text-[#5A4A7A] mb-4">
        One email per day bundling new + resurfaced signals from the last 24 hours.
        Uses your workspace's timezone (defaults to UTC).
      </p>
      <div className="flex items-center gap-4 flex-wrap">
        <Toggle on={!!cfg.enabled} onClick={() => update({ enabled: !cfg.enabled })} testid="digest-enabled-toggle" />
        <div className={`flex items-center gap-2 text-xs ${cfg.enabled ? 'text-[#1A0A2E]' : 'text-[#9B8AB0]'}`}>
          <span>Send at</span>
          <select
            disabled={!cfg.enabled}
            value={cfg.send_at_hour ?? 7}
            onChange={(e) => update({ send_at_hour: parseInt(e.target.value) })}
            data-testid="digest-send-at-hour"
            className="border border-[#E8E0F5] rounded-lg px-2 py-1 text-sm bg-white disabled:bg-[#FAFAFA]"
          >
            {Array.from({ length: 24 }).map((_, h) => <option key={h} value={h}>{String(h).padStart(2, '0')}:00</option>)}
          </select>
        </div>
        <button
          type="button"
          onClick={sendNow}
          disabled={sending || !cfg.enabled}
          data-testid="digest-send-now-btn"
          className="ml-auto px-4 py-1.5 bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white text-xs font-semibold rounded-lg"
        >
          {sending ? 'Sending…' : 'Send now'}
        </button>
      </div>
    </div>
  );
};

const Toggle = ({ on, onClick, testid }) => (
  <button
    type="button"
    onClick={onClick}
    data-testid={testid}
    className="relative w-12 h-6 rounded-full transition-colors mx-auto"
    style={{ background: on ? 'var(--gradient-brand)' : '#E8E0F5' }}
  >
    <span className="absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-all" style={{ left: on ? 'calc(100% - 22px)' : '2px' }} />
  </button>
);

export default NotificationsTab;
