import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Sparkle, ArrowRight, ChatTeardropDots, FlagBanner,
  Robot, ChartLineUp, CheckCircle, X, Fire, Calendar,
  Users, Clock, Lock,
} from '@phosphor-icons/react';

/**
 * Public, read-only interactive demo sandbox at `/demo`.
 *
 * Visually mirrors the real Dashboard.js so prospects see exactly what their
 * workspace will look like with real data. No auth, no API — pure sample data.
 * Linked from EmptyDashboard's "Browse demo" CTA.
 */

const SAMPLE_LEADS = [
  { initials: 'SR', name: 'Sasha Rao', tier: 'hot', stage: 'Proposal Viewed', color: '#7C35DC' },
  { initials: 'FM', name: 'Finley Marsh', tier: 'hot', stage: 'Hot Lead', color: '#7C35DC' },
  { initials: 'QV', name: 'Quinn Velasquez', tier: 'hot', stage: 'Hot Lead', color: '#7C35DC' },
  { initials: 'BS', name: 'Ben Schiller', tier: 'warm', stage: 'Follow-up Due', color: '#D97706' },
  { initials: 'TN', name: 'Theo Naidu', tier: 'hot', stage: 'Proposal Viewed', color: '#7C35DC' },
  { initials: 'OT', name: 'Olivia Tran', tier: 'warm', stage: 'Hot Lead', color: '#D97706' },
  { initials: 'DJ', name: 'Diana Joshi', tier: 'hot', stage: 'Hot Lead', color: '#7C35DC' },
  { initials: 'AK', name: 'Aisha Khan', tier: 'warm', stage: 'Proposal Viewed', color: '#D97706' },
];

const SAMPLE_SIGNALS = [
  { lead: 'Sasha Rao', co: 'Northwind Co', evt: 'Opened proposal 3x in 24h', tier: 'hot', icp: 92, when: '12m ago', recommends: 'Send the financial-services case study — proposal-stage opens convert at 38% when followed up within 1 hour.' },
  { lead: 'Finley Marsh', co: 'Halo Studios', evt: 'Replied "Send me pricing"', tier: 'hot', icp: 88, when: '34m ago', recommends: 'Auto-draft pricing reply with the pilot offer. Speed-to-reply <1h converts 4x better.' },
  { lead: 'Quinn Velasquez', co: 'Latch Labs', evt: 'Booked discovery call (Tue 3pm)', tier: 'hot', icp: 86, when: '1h ago', recommends: 'Pre-call brief drafted: pain points, 3 talking points, 1 differentiator. Open in Calendar.' },
  { lead: 'Theo Naidu', co: 'Sandbar AI', evt: 'Forwarded thread to CFO', tier: 'hot', icp: 84, when: '2h ago', recommends: 'Multi-stakeholder pattern detected — drop the ROI one-pager + invite CFO to demo.' },
];

const SAMPLE_AGENT_ACTIVITY = [
  { time: '12m', action: 'Drafted reply to Sasha Rao', detail: 'Approved by you · Sent via Email' },
  { time: '28m', action: 'Booked discovery call', detail: 'Quinn Velasquez · Tue 3pm IST' },
  { time: '45m', action: 'Qualified inbound lead', detail: 'Forge & Co · ICP score 81' },
  { time: '1h', action: 'Sent follow-up sequence', detail: '4 leads in "warm" tier — open rate 67%' },
  { time: '2h', action: 'Flagged for handoff', detail: 'Theo Naidu — CFO involvement detected' },
];

const SAMPLE_KPIS = [
  { label: 'Active Leads', value: '127', delta: '+8 today', icon: Users, color: '#7C35DC' },
  { label: 'Hot Tier', value: '14', delta: '+3 this week', icon: Fire, color: '#DC2626' },
  { label: 'Conversations Today', value: '38', delta: '12 awaiting', icon: ChatTeardropDots, color: '#0EA5E9' },
  { label: 'Meetings Booked', value: '6', delta: '+2 vs yesterday', icon: Calendar, color: '#10B981' },
];

const DemoSandbox = () => {
  const [showCta, setShowCta] = useState(true);

  return (
    <div className="min-h-screen bg-[#FAFAFA]" data-testid="demo-sandbox">
      {/* Sticky banner */}
      {showCta && (
        <div
          className="sticky top-0 z-50 px-4 py-3 flex items-center justify-between gap-3 flex-wrap"
          style={{ background: 'linear-gradient(135deg, #1A0A2E 0%, #4C1D95 50%, #7C35DC 100%)' }}
          data-testid="demo-cta-banner"
        >
          <div className="flex items-center gap-2 text-white text-sm">
            <Lock size={14} weight="fill" className="text-[#C9B6FF]" />
            <span className="font-bold">DEMO MODE</span>
            <span className="opacity-80 hidden sm:inline">— this is a read-only sandbox with sample data. Your real workspace will look like this.</span>
            <span className="opacity-80 sm:hidden">read-only sandbox</span>
          </div>
          <div className="flex items-center gap-2">
            <Link
              to="/signup"
              data-testid="demo-cta-signup"
              className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-md bg-white text-[#4C1D95] font-bold text-sm hover:bg-[#F4F0FF] transition"
            >
              Start free <ArrowRight size={13} weight="bold" />
            </Link>
            <button
              onClick={() => setShowCta(false)}
              data-testid="demo-cta-close"
              className="p-1.5 rounded-md text-white/70 hover:text-white hover:bg-white/10"
              aria-label="Close banner"
            >
              <X size={14} weight="bold" />
            </button>
          </div>
        </div>
      )}

      <div className="max-w-[1400px] mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Hero */}
        <div className="relative overflow-hidden rounded-3xl p-7 sm:p-10" style={{ background: 'linear-gradient(135deg, #1A0A2E 0%, #4C1D95 55%, #7C35DC 100%)' }}>
          <div className="absolute -top-20 -right-20 w-80 h-80 rounded-full opacity-20" style={{ background: 'radial-gradient(circle, #C9B6FF 0%, transparent 70%)' }} />
          <div className="relative">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 border border-white/20 backdrop-blur-sm">
              <Sparkle size={11} weight="fill" className="text-[#C9B6FF]" />
              <span className="text-[10px] font-bold uppercase tracking-[0.22em] text-[#C9B6FF]">ARIA HAS 63 UPDATES WAITING FOR YOU</span>
            </div>
            <h1 className="mt-4 text-3xl sm:text-5xl font-bold text-white leading-tight" style={{ fontFamily: 'Space Grotesk, Inter' }}>
              Your sales workspace is alive.
            </h1>
            <p className="text-lg text-[#C9B6FF] mt-3 max-w-2xl">
              Aria reviewed 127 leads, qualified 14 as hot, drafted 38 replies, and booked 6 meetings — all while you slept.
            </p>
            <div className="flex flex-wrap gap-2 mt-6">
              <Pill icon={Fire} label="3 hot leads need you now" tone="urgent" />
              <Pill icon={Clock} label="49 follow-ups due" tone="info" />
              <Pill icon={ChartLineUp} label="11 active proposals" tone="success" />
            </div>
          </div>
        </div>

        {/* KPI cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {SAMPLE_KPIS.map((k) => (
            <div key={k.label} className="bg-white border border-[#E8E0F5] rounded-2xl p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#5A4A7A]">{k.label}</span>
                <div className="w-7 h-7 rounded-md flex items-center justify-center" style={{ background: `${k.color}15` }}>
                  <k.icon size={13} weight="fill" style={{ color: k.color }} />
                </div>
              </div>
              <div className="text-3xl font-bold text-[#1A0A2E]" style={{ fontFamily: 'Space Grotesk, Inter' }}>{k.value}</div>
              <div className="text-xs text-[#7C35DC] font-semibold mt-1">{k.delta}</div>
            </div>
          ))}
        </div>

        {/* Aria Stories */}
        <div className="bg-white border border-[#E8E0F5] rounded-2xl p-5">
          <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#7C35DC]">— ARIA STORIES</span>
          <h2 className="text-xl font-bold text-[#1A0A2E]" style={{ fontFamily: 'Space Grotesk, Inter' }}>Leads that need your attention today</h2>
          <p className="text-sm text-[#5A4A7A] mt-0.5">Tap a ring to see why ARIA flagged them.</p>
          <div className="flex flex-wrap gap-4 mt-5">
            {SAMPLE_LEADS.map((l) => (
              <div key={l.initials} className="text-center" style={{ width: 72 }}>
                <div className="w-14 h-14 rounded-full flex items-center justify-center text-white font-bold text-base mx-auto border-2"
                  style={{ background: `linear-gradient(135deg, ${l.color}, #1A0A2E)`, borderColor: l.color }}>
                  {l.initials}
                </div>
                <div className="text-xs font-bold text-[#1A0A2E] mt-2 truncate">{l.name.split(' ')[0]}</div>
                <span className={`inline-block mt-1 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-[0.1em] rounded ${l.tier === 'hot' ? 'bg-[#FEE2E2] text-[#DC2626]' : 'bg-[#FEF3C7] text-[#D97706]'}`}>
                  {l.tier}
                </span>
                <div className="text-[10px] text-[#5A4A7A] mt-1 truncate">{l.stage}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Two-column */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Lead feed (2/3) */}
          <div className="lg:col-span-2 bg-white border border-[#E8E0F5] rounded-2xl p-5">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#7C35DC]">— LEAD FEED</span>
              <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#5A4A7A]">{SAMPLE_SIGNALS.length} SIGNALS</span>
            </div>
            <h2 className="text-xl font-bold text-[#1A0A2E]" style={{ fontFamily: 'Space Grotesk, Inter' }}>Buying signals, ranked by urgency</h2>
            <p className="text-sm text-[#5A4A7A] mt-0.5">Every card is one sales action away from closed.</p>
            <div className="mt-5 space-y-3">
              {SAMPLE_SIGNALS.map((s, i) => (
                <div key={i} className="border border-[#E8E0F5] rounded-xl p-3 hover:bg-[#FAF7FF] transition">
                  <div className="flex items-start gap-3">
                    <div className="w-9 h-9 rounded-md flex-shrink-0 flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #4C1D95, #7C35DC)' }}>
                      <Robot size={15} weight="fill" className="text-white" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5 flex-wrap mb-1">
                        <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#7C35DC]">{s.evt.toUpperCase()}</span>
                        <span className={`px-1.5 py-0.5 text-[9px] font-bold uppercase rounded border ${s.tier === 'hot' ? 'bg-[#FEE2E2] text-[#DC2626] border-[#DC2626]/30' : 'bg-[#FEF3C7] text-[#D97706] border-[#D97706]/30'}`}>{s.tier}</span>
                        <span className="text-[10px] text-[#9B8AB0]">ICP {s.icp}</span>
                        <span className="text-[10px] text-[#9B8AB0]">· {s.when}</span>
                      </div>
                      <div className="text-sm font-bold text-[#1A0A2E]">{s.lead} <span className="text-[#5A4A7A] font-normal">· {s.co}</span></div>
                      <div className="bg-[#F4F0FF] border border-[#7C35DC]/20 rounded-md px-2.5 py-1.5 mt-2 flex items-start gap-1.5">
                        <Sparkle size={11} weight="fill" className="text-[#7C35DC] mt-0.5 flex-shrink-0" />
                        <div className="text-xs text-[#1A0A2E]"><span className="font-bold text-[#7C35DC]">ARIA recommends:</span> {s.recommends}</div>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Side */}
          <div className="space-y-4">
            <div className="bg-white border border-[#E8E0F5] rounded-2xl p-5">
              <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#7C35DC]">— PIPELINE MOOD</span>
              <div className="mt-2 flex items-center gap-2 px-3 py-2 rounded-lg bg-[#FEF3C7] border border-[#D97706]/20">
                <FlagBanner size={14} weight="fill" className="text-[#D97706]" />
                <span className="text-xs font-bold text-[#D97706] uppercase tracking-[0.1em]">Too many leads are sleeping</span>
              </div>
              <blockquote className="mt-3 text-sm italic text-[#1A0A2E] border-l-2 border-[#7C35DC] pl-3">
                "Revive 24 silent leads today — Aria has drafts ready for 5 segments."
              </blockquote>
              <div className="grid grid-cols-3 gap-2 mt-4">
                <Stat label="Active" value="43" />
                <Stat label="Hot" value="9" tone="hot" />
                <Stat label="Silent" value="24" tone="cold" />
              </div>
            </div>

            <div className="bg-white border border-[#E8E0F5] rounded-2xl p-5">
              <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#7C35DC]">— ARIA AGENT ACTIVITY</span>
              <div className="mt-3 space-y-2.5">
                {SAMPLE_AGENT_ACTIVITY.map((a, i) => (
                  <div key={i} className="flex items-start gap-2.5 text-sm">
                    <CheckCircle size={13} weight="fill" className="text-[#10B981] mt-0.5 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="font-semibold text-[#1A0A2E] truncate">{a.action}</div>
                      <div className="text-xs text-[#5A4A7A]">{a.detail}</div>
                    </div>
                    <span className="text-[10px] text-[#9B8AB0] flex-shrink-0">{a.time} ago</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Bottom CTA */}
        <div className="relative overflow-hidden rounded-3xl p-8 sm:p-10 text-center" style={{ background: 'linear-gradient(135deg, #1A0A2E 0%, #4C1D95 55%, #7C35DC 100%)' }}>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 border border-white/20 backdrop-blur-sm">
            <Sparkle size={11} weight="fill" className="text-[#C9B6FF]" />
            <span className="text-[10px] font-bold uppercase tracking-[0.22em] text-[#C9B6FF]">YOUR DASHBOARD WILL LOOK LIKE THIS IN 7 DAYS</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-bold text-white mt-3" style={{ fontFamily: 'Space Grotesk, Inter' }}>Ready to give Aria some real leads?</h2>
          <p className="text-[#C9B6FF] mt-2 max-w-xl mx-auto">No credit card. 60 seconds to spin up your workspace.</p>
          <div className="flex justify-center gap-3 mt-6 flex-wrap">
            <Link to="/signup" data-testid="demo-bottom-signup"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-white text-[#4C1D95] font-bold text-sm hover:bg-[#F4F0FF]">
              Start free <ArrowRight size={14} weight="bold" />
            </Link>
            <Link to="/login"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-white/10 text-white font-bold text-sm border border-white/30 backdrop-blur-sm hover:bg-white/20">
              I have an account
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};

const Pill = ({ icon: Icon, label, tone }) => {
  const map = {
    urgent: 'bg-[#DC2626]/15 border-[#DC2626]/30 text-white',
    info: 'bg-white/10 border-white/20 text-white',
    success: 'bg-[#10B981]/15 border-[#10B981]/30 text-white',
  };
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold border backdrop-blur-sm ${map[tone] || map.info}`}>
      <Icon size={12} weight="fill" />{label}
    </span>
  );
};

const Stat = ({ label, value, tone }) => {
  const c = tone === 'hot' ? 'text-[#DC2626]' : tone === 'cold' ? 'text-[#5A4A7A]' : 'text-[#7C35DC]';
  return (
    <div className="text-center">
      <div className={`text-2xl font-bold ${c}`} style={{ fontFamily: 'Space Grotesk, Inter' }}>{value}</div>
      <div className="text-[9px] font-bold uppercase tracking-[0.18em] text-[#5A4A7A] mt-0.5">{label}</div>
    </div>
  );
};

export default DemoSandbox;
