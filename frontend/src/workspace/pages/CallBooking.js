/**
 * CallBooking — iter109c Batch 2 (replaces stub).
 *
 * Gated by Google OAuth connection with Calendar scope.
 * Two tabs:
 *   - Settings: availability, duration, buffer, max/day, confirmation msg, pre-call Qs
 *   - Bookings: upcoming list with cancel action
 *
 * If Google isn't connected, renders the connect-prompt card pointing to
 * /app/integrations. If Calendly is connected instead, the alternate flow
 * shows the workspace's Calendly link as the booking surface.
 */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import {
  CalendarBlank, Clock, Plug, ArrowRight, FloppyDisk, X as XIcon,
  VideoCamera, CircleNotch, Plus, Trash,
} from '@phosphor-icons/react';
import api from '../../config/api';

const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const DURATIONS = [15, 30, 45, 60, 90];
const BUFFERS = [0, 15, 30];

const CallBooking = () => {
  const [tab, setTab] = useState('settings');
  const [settings, setSettings] = useState(null);
  const [bookings, setBookings] = useState([]);
  const [providerStatus, setProviderStatus] = useState(null);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  const loadSettings = async () => {
    try {
      const { data } = await api.get('/api/call-booking/settings');
      setSettings({ ...data });
      setProviderStatus(data.provider_status);
    } catch (e) {
      toast.error('Could not load Call Booking settings');
    } finally { setLoading(false); }
  };

  const loadBookings = async () => {
    try {
      const { data } = await api.get('/api/call-booking/bookings');
      setBookings(data.bookings || []);
    } catch { /* ignore */ }
  };

  useEffect(() => { loadSettings(); loadBookings(); }, []);

  const save = async () => {
    setSaving(true);
    try {
      const payload = {
        timezone: settings.timezone,
        availability: settings.availability,
        durations: settings.durations,
        default_duration: settings.default_duration,
        buffer_minutes: settings.buffer_minutes,
        max_calls_per_day: settings.max_calls_per_day,
        confirmation_message: settings.confirmation_message,
        pre_call_questions: settings.pre_call_questions || [],
        reminder_minutes_before: settings.reminder_minutes_before,
        provider: settings.provider,
        calendly_link: settings.calendly_link || null,
      };
      const { data } = await api.put('/api/call-booking/settings', payload);
      toast.success('Saved');
      setSettings((s) => ({ ...s, ...data }));
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Save failed');
    } finally { setSaving(false); }
  };

  const cancelBooking = async (id) => {
    if (!window.confirm('Cancel this booking?')) return;
    try {
      await api.post(`/api/call-booking/bookings/${id}/cancel`);
      toast.success('Booking cancelled');
      loadBookings();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Cancel failed');
    }
  };

  if (loading) return <div className="p-6 text-sm" style={{ color: 'var(--theme-text-muted)' }}>Loading…</div>;
  if (!settings) return null;

  const hasGoogleCalendar = providerStatus?.google_has_calendar_scope;
  const hasCalendly = providerStatus?.calendly_connected;

  return (
    <div className="p-6 md:p-8 max-w-5xl mx-auto" data-testid="call-booking-page" style={{ color: 'var(--theme-text)' }}>
      <header className="mb-6 flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-3xl font-extrabold mb-1" style={{ fontFamily: 'Space Grotesk, Inter', letterSpacing: '-0.02em' }}>
            Call Booking
          </h1>
          <p className="text-sm" style={{ color: 'var(--theme-text-muted)' }}>
            ARIA books qualified leads onto your calendar with a Meet link, automatically.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs px-2.5 py-1 rounded-full font-bold uppercase tracking-wider"
                style={{
                  background: hasGoogleCalendar ? 'rgba(34,197,94,0.13)' : hasCalendly ? 'rgba(245,158,11,0.13)' : 'rgba(239,68,68,0.13)',
                  color: hasGoogleCalendar ? '#22c55e' : hasCalendly ? '#f59e0b' : '#ef4444',
                }}
                data-testid="call-booking-provider-status">
            {hasGoogleCalendar ? '● Google Calendar' : hasCalendly ? '● Calendly' : '○ No provider connected'}
          </span>
        </div>
      </header>

      {!hasGoogleCalendar && !hasCalendly && <ConnectPrompt />}

      {(hasGoogleCalendar || hasCalendly) && (
        <>
          <div className="flex items-center gap-1.5 mb-5 border-b" style={{ borderColor: 'var(--theme-border)' }} data-testid="call-booking-tabs">
            <TabButton active={tab === 'settings'} onClick={() => setTab('settings')} testId="tab-settings">Settings</TabButton>
            <TabButton active={tab === 'bookings'} onClick={() => setTab('bookings')} testId="tab-bookings">
              Upcoming ({bookings.length})
            </TabButton>
          </div>

          {tab === 'settings' && (
            <SettingsForm settings={settings} setSettings={setSettings} save={save} saving={saving} />
          )}
          {tab === 'bookings' && (
            <BookingsList bookings={bookings} onCancel={cancelBooking} />
          )}
        </>
      )}
    </div>
  );
};


const TabButton = ({ active, onClick, children, testId }) => (
  <button
    onClick={onClick}
    data-testid={`call-booking-${testId}`}
    className="px-4 py-2.5 text-sm font-semibold border-b-2 transition-colors -mb-px"
    style={{
      borderColor: active ? 'var(--theme-purple)' : 'transparent',
      color: active ? 'var(--theme-text)' : 'var(--theme-text-muted)',
    }}
  >{children}</button>
);


const ConnectPrompt = () => (
  <div className="rounded-xl p-6 border" style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }} data-testid="call-booking-connect-prompt">
    <div className="flex items-start gap-4">
      <div className="w-12 h-12 rounded-lg flex items-center justify-center" style={{ background: 'var(--theme-purple-dim)' }}>
        <CalendarBlank size={22} weight="duotone" style={{ color: 'var(--theme-purple-light)' }} />
      </div>
      <div className="flex-1">
        <h2 className="text-lg font-bold mb-1">Connect a scheduling provider</h2>
        <p className="text-sm mb-3" style={{ color: 'var(--theme-text-muted)' }}>
          Call Booking needs Google (Calendar + Meet) or Calendly connected. ARIA will create events on your calendar with a Meet link and send the link to the lead on their preferred channel.
        </p>
        <Link to="/app/integrations" data-testid="call-booking-go-integrations"
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-bold text-white"
              style={{ background: 'var(--theme-purple)' }}>
          <Plug size={13} weight="bold" /> Go to Integrations <ArrowRight size={11} weight="bold" />
        </Link>
      </div>
    </div>
  </div>
);


// ── Settings form ───────────────────────────────────────────────────────
const SettingsForm = ({ settings, setSettings, save, saving }) => {
  const setField = (k, v) => setSettings((s) => ({ ...s, [k]: v }));
  const toggleDay = (dow) => {
    const existing = settings.availability.find((a) => a.day_of_week === dow);
    if (existing) {
      setField('availability', settings.availability.filter((a) => a.day_of_week !== dow));
    } else {
      setField('availability', [...settings.availability, { day_of_week: dow, start: '09:00', end: '18:00' }]
        .sort((a, b) => a.day_of_week - b.day_of_week));
    }
  };
  const setDayWindow = (dow, key, val) => {
    setField('availability', settings.availability.map((a) => a.day_of_week === dow ? { ...a, [key]: val } : a));
  };
  const addQuestion = () => setField('pre_call_questions', [...(settings.pre_call_questions || []), '']);
  const setQuestion = (i, v) => setField('pre_call_questions',
    (settings.pre_call_questions || []).map((q, idx) => idx === i ? v : q));
  const removeQuestion = (i) => setField('pre_call_questions',
    (settings.pre_call_questions || []).filter((_, idx) => idx !== i));

  return (
    <div className="space-y-5">
      {/* Availability */}
      <Card title="Availability" subtitle="When can ARIA book calls?" testId="settings-availability">
        <div className="flex flex-wrap gap-1.5 mb-3" data-testid="day-picker">
          {DAY_NAMES.map((d, i) => {
            const on = !!settings.availability.find((a) => a.day_of_week === i);
            return (
              <button key={d} onClick={() => toggleDay(i)} data-testid={`day-${d.toLowerCase()}`}
                      className="px-3 py-1.5 text-xs font-semibold rounded-md border transition-colors"
                      style={{
                        background: on ? 'var(--theme-purple-dim)' : 'var(--theme-surface2)',
                        borderColor: on ? 'var(--theme-purple)' : 'var(--theme-border-strong)',
                        color: on ? 'var(--theme-purple-light)' : 'var(--theme-text-muted)',
                      }}>{d}</button>
            );
          })}
        </div>
        <div className="space-y-2">
          {settings.availability.map((a) => (
            <div key={a.day_of_week} className="flex items-center gap-2 text-xs">
              <span className="w-10 font-bold" style={{ color: 'var(--theme-text)' }}>{DAY_NAMES[a.day_of_week]}</span>
              <TimeInput value={a.start} onChange={(v) => setDayWindow(a.day_of_week, 'start', v)} testId={`avail-${a.day_of_week}-start`} />
              <span style={{ color: 'var(--theme-text-muted)' }}>to</span>
              <TimeInput value={a.end} onChange={(v) => setDayWindow(a.day_of_week, 'end', v)} testId={`avail-${a.day_of_week}-end`} />
            </div>
          ))}
        </div>
        <div className="mt-3">
          <Label>Timezone</Label>
          <input value={settings.timezone} onChange={(e) => setField('timezone', e.target.value)} data-testid="settings-timezone"
                 className="px-2 py-1.5 rounded-md border text-sm outline-none"
                 style={{ background: 'var(--theme-surface2)', borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text)' }} />
        </div>
      </Card>

      {/* Duration + Buffer + Max per day */}
      <Card title="Call format" subtitle="Length, buffer between calls, daily cap." testId="settings-format">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <Label>Default duration</Label>
            <div className="flex flex-wrap gap-1.5">
              {DURATIONS.map((d) => (
                <button key={d} onClick={() => setField('default_duration', d)} data-testid={`duration-${d}`}
                        className="px-3 py-1.5 text-xs font-semibold rounded-md border"
                        style={{
                          background: settings.default_duration === d ? 'var(--theme-purple-dim)' : 'var(--theme-surface2)',
                          borderColor: settings.default_duration === d ? 'var(--theme-purple)' : 'var(--theme-border-strong)',
                          color: settings.default_duration === d ? 'var(--theme-purple-light)' : 'var(--theme-text-muted)',
                        }}>{d} min</button>
              ))}
            </div>
          </div>
          <div>
            <Label>Buffer between calls</Label>
            <div className="flex flex-wrap gap-1.5">
              {BUFFERS.map((b) => (
                <button key={b} onClick={() => setField('buffer_minutes', b)} data-testid={`buffer-${b}`}
                        className="px-3 py-1.5 text-xs font-semibold rounded-md border"
                        style={{
                          background: settings.buffer_minutes === b ? 'var(--theme-purple-dim)' : 'var(--theme-surface2)',
                          borderColor: settings.buffer_minutes === b ? 'var(--theme-purple)' : 'var(--theme-border-strong)',
                          color: settings.buffer_minutes === b ? 'var(--theme-purple-light)' : 'var(--theme-text-muted)',
                        }}>{b} min</button>
              ))}
            </div>
          </div>
          <div>
            <Label>Max calls per day</Label>
            <input type="number" min={1} max={20} value={settings.max_calls_per_day}
                   onChange={(e) => setField('max_calls_per_day', parseInt(e.target.value, 10) || 1)}
                   data-testid="max-per-day"
                   className="px-2 py-1.5 rounded-md border text-sm outline-none w-24"
                   style={{ background: 'var(--theme-surface2)', borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text)' }} />
          </div>
        </div>
      </Card>

      {/* Confirmation message + Pre-call questions */}
      <Card title="Confirmation & pre-call" subtitle="What the lead sees when ARIA confirms a call." testId="settings-confirmation">
        <Label>Confirmation message — use {'{OWNER}'}, {'{WHEN}'}, {'{MEET_LINK}'}</Label>
        <textarea value={settings.confirmation_message} onChange={(e) => setField('confirmation_message', e.target.value)}
                  rows={3} data-testid="confirmation-message"
                  className="w-full px-3 py-2 rounded-md border text-sm outline-none mb-4"
                  style={{ background: 'var(--theme-surface2)', borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text)' }} />
        <Label>Pre-call questions (optional)</Label>
        <div className="space-y-2">
          {(settings.pre_call_questions || []).map((q, i) => (
            <div key={i} className="flex gap-2" data-testid={`precall-q-${i}`}>
              <input value={q} onChange={(e) => setQuestion(i, e.target.value)}
                     className="flex-1 px-3 py-1.5 rounded-md border text-sm outline-none"
                     style={{ background: 'var(--theme-surface2)', borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text)' }} />
              <button onClick={() => removeQuestion(i)} aria-label="Remove" data-testid={`precall-q-remove-${i}`}
                      className="px-2 rounded-md border" style={{ borderColor: 'var(--theme-border-strong)', color: '#ef4444' }}>
                <Trash size={12} />
              </button>
            </div>
          ))}
          <button onClick={addQuestion} data-testid="precall-q-add"
                  className="px-3 py-1.5 text-xs font-semibold rounded-md border"
                  style={{ borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text-muted)' }}>
            <Plus size={11} weight="bold" className="inline -mt-0.5 mr-1" /> Add question
          </button>
        </div>
      </Card>

      {/* Save */}
      <div className="flex justify-end sticky bottom-4 z-10">
        <button onClick={save} disabled={saving} data-testid="call-booking-save"
                className="px-5 py-2 rounded-md font-bold text-sm text-white disabled:opacity-50 shadow-lg"
                style={{ background: 'var(--theme-purple)' }}>
          {saving ? <CircleNotch size={13} className="animate-spin inline -mt-0.5 mr-1" /> : <FloppyDisk size={13} weight="fill" className="inline -mt-0.5 mr-1" />}
          {saving ? 'Saving…' : 'Save settings'}
        </button>
      </div>
    </div>
  );
};


// ── Bookings list ───────────────────────────────────────────────────────
const BookingsList = ({ bookings, onCancel }) => (
  <div className="space-y-2" data-testid="call-booking-list">
    {bookings.length === 0 && (
      <div className="rounded-lg p-6 text-center border border-dashed text-sm" style={{ borderColor: 'var(--theme-border)', color: 'var(--theme-text-muted)' }} data-testid="bookings-empty">
        No upcoming calls. ARIA will book them automatically as leads qualify.
      </div>
    )}
    {bookings.map((b) => (
      <div key={b.id} className="rounded-lg p-3 border flex items-center justify-between gap-3" style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }} data-testid={`booking-row-${b.id}`}>
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-9 h-9 rounded-md flex items-center justify-center" style={{ background: 'var(--theme-purple-dim)' }}>
            <VideoCamera size={16} weight="duotone" style={{ color: 'var(--theme-purple-light)' }} />
          </div>
          <div className="min-w-0">
            <div className="text-sm font-bold truncate" style={{ color: 'var(--theme-text)' }}>{b.lead_name}</div>
            <div className="text-[11px]" style={{ color: 'var(--theme-text-muted)' }}>
              <Clock size={10} weight="duotone" className="inline -mt-0.5 mr-1" />
              {new Date(b.scheduled_for).toLocaleString()} · {b.duration_minutes}m · via {b.lead_channel}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {b.meet_link && (
            <a href={b.meet_link} target="_blank" rel="noopener noreferrer" className="text-xs font-semibold" style={{ color: 'var(--theme-purple-light)' }}>
              Open Meet
            </a>
          )}
          <button onClick={() => onCancel(b.id)} data-testid={`booking-cancel-${b.id}`}
                  className="px-2 py-1 text-xs rounded-md border" style={{ borderColor: 'var(--theme-border-strong)', color: '#ef4444' }}>
            <XIcon size={11} className="inline" /> Cancel
          </button>
        </div>
      </div>
    ))}
  </div>
);


// ── Primitives ──────────────────────────────────────────────────────────
const Card = ({ title, subtitle, testId, children }) => (
  <div className="rounded-lg p-4 border" style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }} data-testid={`call-booking-${testId}`}>
    <div className="text-sm font-bold mb-1" style={{ color: 'var(--theme-text)' }}>{title}</div>
    <div className="text-xs mb-3" style={{ color: 'var(--theme-text-muted)' }}>{subtitle}</div>
    {children}
  </div>
);

const Label = ({ children }) => (
  <div className="text-[10px] uppercase tracking-wider font-bold mb-1.5" style={{ color: 'var(--theme-text-muted)' }}>{children}</div>
);

const TimeInput = ({ value, onChange, testId }) => (
  <input type="time" value={value} onChange={(e) => onChange(e.target.value)} data-testid={testId}
         className="px-2 py-1 rounded-md border text-xs outline-none"
         style={{ background: 'var(--theme-surface2)', borderColor: 'var(--theme-border-strong)', color: 'var(--theme-text)' }} />
);

export default CallBooking;
