/**
 * CallBooking — stub page in the ADVANCED · ARIA TOOLS section.
 *
 * Per spec choice 3-stub: shows a configure-Calendly hint. Real flow
 * uses /api/integrations/calendly/connect once the workspace pastes
 * its Calendly client ID/secret in backend/.env.
 */
import { Link } from 'react-router-dom';
import { CalendarBlank, ArrowRight, CheckCircle } from '@phosphor-icons/react';

const CallBooking = () => (
  <div data-testid="call-booking-page" className="space-y-5">
    <div>
      <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-[#7C35DC]">Advanced · Aria Tools</div>
      <h1 className="text-2xl font-extrabold text-[#0F172A]" style={{ fontFamily: 'Space Grotesk, Inter' }}>Call Booking</h1>
      <p className="text-sm text-[#475569] mt-1">Let Aria book qualified calls directly into your calendar — Calendly + Google/Outlook supported.</p>
    </div>

    <div className="bg-white border border-[#E8E0F5] rounded-2xl p-6" data-testid="call-booking-stub">
      <CalendarBlank size={32} weight="duotone" className="text-[#7C35DC] mb-3" />
      <div className="text-lg font-bold text-[#0F172A] mb-2" style={{ fontFamily: 'Space Grotesk, Inter' }}>Connect your scheduling tool</div>
      <p className="text-sm text-[#475569] mb-5 max-w-prose">
        Aria will detect "is next Tuesday at 2pm okay?" replies and confirm them against your live calendar — no
        ping-pong. Once you connect Calendly (or Google / Outlook), this page will become your
        booking control room: routing rules, buffer time, no-show rescue.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-6">
        <Feature title="Auto-detect booking intent" body="ARIA reads inbound emails and WhatsApp replies for time mentions." />
        <Feature title="Round-robin or solo" body="Route discovery calls to whichever rep is least loaded today." />
        <Feature title="No-show rescue" body="If they don't show up, ARIA opens the recovery sequence automatically." />
      </div>

      <Link
        to="/app/integrations"
        data-testid="call-booking-connect-link"
        className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-lg text-sm font-extrabold text-white"
        style={{ background: '#7C35DC' }}
      >
        Connect in Integrations <ArrowRight size={14} weight="bold" />
      </Link>
    </div>
  </div>
);

const Feature = ({ title, body }) => (
  <div className="border border-[#E8E0F5] rounded-xl p-4 bg-[#FAFAFA]">
    <CheckCircle size={14} weight="fill" className="text-[#7C35DC] mb-2" />
    <div className="text-sm font-bold text-[#0F172A] mb-1">{title}</div>
    <div className="text-xs text-[#64748B] leading-relaxed">{body}</div>
  </div>
);

export default CallBooking;
