import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../config/api';
import {
  EnvelopeOpen, MouseSimple, ChatCircleDots, CalendarBlank,
  PaperPlaneTilt, Lightning, ArrowUpRight, PlugsConnected,
} from '@phosphor-icons/react';

const TILE = ({ icon: Icon, label, value, accent }) => (
  <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-white border border-[#F0ECF9]" data-testid={`digest-tile-${label.toLowerCase().replace(/\s+/g, '-')}`}>
    <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
      style={{ background: `${accent}14`, color: accent, border: `1px solid ${accent}33` }}>
      <Icon size={18} weight="duotone" />
    </div>
    <div className="min-w-0">
      <div className="text-2xl font-bold text-[#1A0A2E] leading-none" style={{ fontFamily: 'Space Grotesk, Inter' }}>{value}</div>
      <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#9B8AB0] mt-1">{label}</div>
    </div>
  </div>
);

const labelOf = (type) => ({
  email_sent: 'sent', email_opened: 'opened', email_clicked: 'clicked',
  replied: 'replied', bounced: 'bounced', meeting_scheduled: 'meeting',
  interested: 'interested',
  pushed_to_lemlist: 'pushed → Lemlist', pushed_to_saleshandy: 'pushed → SalesHandy',
  auto_pushed_to_lemlist: 'auto-pushed → Lemlist', auto_pushed_to_saleshandy: 'auto-pushed → SalesHandy',
}[type] || type.replace(/_/g, ' '));

const dotOf = (type) => {
  if (['replied', 'interested', 'meeting_scheduled', 'email_opened', 'email_clicked'].includes(type)) return '#16A34A';
  if (type === 'bounced') return '#DC2626';
  if (type.includes('saleshandy')) return '#16A34A';
  if (type.includes('lemlist')) return '#7C35DC';
  return '#7C35DC';
};

const SyncActivityDigest = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const r = await api.get('/api/integrations/digest/today');
        if (mounted) setData(r.data);
      } catch {
        // silent — card shows empty state
      } finally {
        if (mounted) setLoading(false);
      }
    };
    load();
    const interval = setInterval(load, 90000); // refresh every 90s
    return () => { mounted = false; clearInterval(interval); };
  }, []);

  if (loading) return null; // don't flicker on first load

  const counts = data?.counts || {};
  const connected = data?.connected || {};
  const anyConnected = data?.any_connected;
  const totalToday =
    (counts.emails_sent || 0) + (counts.emails_opened || 0) + (counts.replies || 0) +
    (counts.meetings_booked || 0) + (counts.pushed_to_sequences || 0);

  return (
    <div
      className="bg-white border border-[#E8E0F5] rounded-2xl overflow-hidden"
      style={{ boxShadow: 'var(--shadow-card)' }}
      data-testid="sync-activity-digest"
    >
      {/* Header */}
      <div className="px-6 py-4 border-b border-[#F0ECF9] flex items-center justify-between gap-3 flex-wrap"
        style={{ background: 'linear-gradient(135deg, #FAF7FF 0%, #FFFFFF 100%)' }}>
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-9 h-9 rounded-lg bg-[#F4F0FF] border border-[#E0D4F7] flex items-center justify-center flex-shrink-0">
            <PlugsConnected size={18} weight="duotone" className="text-[#7C35DC]" />
          </div>
          <div className="min-w-0">
            <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-[#7C35DC]">Today · sync activity</div>
            <h3 className="text-base font-bold text-[#1A0A2E] truncate" style={{ fontFamily: 'Space Grotesk, Inter' }}>
              ARIA's sequences are working {totalToday > 0 ? `— ${totalToday} ${totalToday === 1 ? 'event' : 'events'}` : 'for you'}
            </h3>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {connected.lemlist && (
            <span className="px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-[0.15em] text-white" style={{ background: '#7C35DC' }}>Lemlist</span>
          )}
          {connected.saleshandy && (
            <span className="px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-[0.15em] text-white" style={{ background: '#16A34A' }}>SalesHandy</span>
          )}
          <Link to="/sales-engagement" className="text-xs text-[#7C35DC] hover:text-[#5B28D4] flex items-center gap-1 font-semibold" data-testid="digest-manage-link">
            Manage <ArrowUpRight size={12} weight="bold" />
          </Link>
        </div>
      </div>

      {/* Body */}
      {totalToday === 0 && !anyConnected ? (
        <div className="px-6 py-8 text-center" data-testid="digest-empty-state">
          <p className="text-sm text-[#5A4A7A]">Connect Lemlist or SalesHandy to see today's email opens, replies, and meetings booked from your sequences.</p>
          <Link to="/sales-engagement" className="inline-block mt-3 px-3 py-1.5 rounded-lg bg-[#F4F0FF] text-[#7C35DC] border border-[#7C35DC]/25 text-xs font-bold uppercase tracking-[0.15em] hover:bg-[#EDE4FF]" data-testid="digest-connect-cta">
            Connect a sequencer
          </Link>
        </div>
      ) : totalToday === 0 ? (
        <div className="px-6 py-8 text-center" data-testid="digest-quiet-state">
          <p className="text-sm text-[#5A4A7A]">No sequence activity yet today. ARIA will notify you here as opens, replies, and meetings come in.</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 p-4">
            <TILE icon={PaperPlaneTilt} label="Sent"     value={counts.emails_sent     || 0} accent="#7C35DC" />
            <TILE icon={EnvelopeOpen}   label="Opened"   value={counts.emails_opened   || 0} accent="#16A34A" />
            <TILE icon={MouseSimple}    label="Clicked"  value={counts.links_clicked   || 0} accent="#0891B2" />
            <TILE icon={ChatCircleDots} label="Replies"  value={counts.replies         || 0} accent="#16A34A" />
            <TILE icon={CalendarBlank}  label="Meetings" value={counts.meetings_booked || 0} accent="#7C35DC" />
            <TILE icon={Lightning}      label="Pushed"   value={counts.pushed_to_sequences || 0} accent="#D97706" />
          </div>

          {data.recent && data.recent.length > 0 && (
            <div className="px-6 pb-5">
              <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#9B8AB0] mb-2">Latest events</div>
              <div className="space-y-1.5">
                {data.recent.map((evt, i) => (
                  <div key={evt.id || i} className="flex items-center gap-2.5 text-sm" data-testid={`digest-recent-${i}`}>
                    <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: dotOf(evt.activity_type) }} />
                    <span className="text-[#1A0A2E] font-semibold truncate min-w-0">{evt.lead_name || 'Unknown lead'}</span>
                    {evt.company && <span className="text-[#9B8AB0] text-xs truncate min-w-0">· {evt.company}</span>}
                    <span className="text-[#5A4A7A] text-xs ml-auto whitespace-nowrap">{labelOf(evt.activity_type)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default SyncActivityDigest;
