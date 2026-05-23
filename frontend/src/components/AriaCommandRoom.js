/**
 * AriaCommandRoom — the new dashboard hero.
 *
 * Premium, founder-friendly, AI-first workspace welcome:
 *  - Personal welcome + greeting
 *  - ARIA live status (Active / Listening / Following up / Drafting / Nurturing)
 *  - Today's lead summary (real backend data from /api/analytics/dashboard
 *    + /api/health/stale-leads + /api/aria/analytics)
 *  - Quick action buttons
 *  - ARIA Personality Panel — calm sales-operator vibe with next best action
 *
 * Visual direction: warm light off-white surface, deep navy text,
 * soft purple→cream gradients, glassmorphism cards, animated status dots,
 * gentle pulse for "ARIA Active", subtle ring glow on Hot Leads card.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../config/api';
import {
  Sparkle, Fire, CalendarCheck, Clock, ArrowRight, Lightning, Robot,
  ChatCircleDots, Plus, Sun, Moon, Coffee, ShieldCheck, Headset,
  Users, ArrowUpRight,
} from '@phosphor-icons/react';

const greeting = () => {
  const h = new Date().getHours();
  if (h < 5) return { text: 'Burning the midnight oil', icon: Moon };
  if (h < 12) return { text: 'Good morning', icon: Sun };
  if (h < 17) return { text: 'Good afternoon', icon: Coffee };
  if (h < 21) return { text: 'Good evening', icon: Sun };
  return { text: 'Quiet night, founder', icon: Moon };
};

// Decide ARIA's current mode based on real signals. Order matters — first match wins.
function deriveAriaMode({ hotCount, staleCount, pendingFollowUps, recentOpensCount }) {
  if (hotCount > 0) return { key: 'drafting', label: 'Drafting replies', tint: '#DC2626', bg: '#FEE2E2', note: `Working on ${hotCount} hot lead${hotCount === 1 ? '' : 's'} right now.` };
  if (staleCount > 5) return { key: 'nurturing', label: 'Reviving cold leads', tint: '#D97706', bg: '#FEF3C7', note: `${staleCount} leads gone cold — Aria is reaching back out.` };
  if (recentOpensCount > 0) return { key: 'following', label: 'Following up', tint: '#0055FF', bg: '#DCEEFE', note: `${recentOpensCount} lead${recentOpensCount === 1 ? ' just opened your message' : 's just opened your messages'}.` };
  if (pendingFollowUps > 0) return { key: 'listening', label: 'Listening', tint: '#7C35DC', bg: '#F4E6FD', note: `${pendingFollowUps} touchpoint${pendingFollowUps === 1 ? '' : 's'} queued for today.` };
  return { key: 'listening', label: 'Listening', tint: '#16A34A', bg: '#DCFCE7', note: 'Pipeline is calm. Aria is watching for new inbound.' };
}

const AriaCommandRoom = ({ userName }) => {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [stale, setStale] = useState(0);
  const [hot, setHot] = useState(0);
  const [todayConvos, setTodayConvos] = useState(0);
  const [nextAction, setNextAction] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    Promise.all([
      api.get('/api/analytics/dashboard').catch(() => ({ data: null })),
      api.get('/api/health/stale-leads?limit=1').catch(() => ({ data: null })),
      api.get('/api/leads?icp_tier=hot&limit=1').catch(() => ({ data: { leads: [] } })),
    ]).then(([a, s, h]) => {
      if (!mounted) return;
      setStats(a.data);
      setStale(s.data?.count || s.data?.total || (Array.isArray(s.data?.leads) ? s.data.leads.length : 0) || 0);
      const hotLeads = (a.data?.leads_by_tier?.hot) ?? (h.data?.total ?? (Array.isArray(h.data?.leads) ? h.data.leads.length : 0));
      setHot(hotLeads || 0);
      setTodayConvos(a.data?.conversations_today ?? a.data?.todays_conversations ?? 0);
      // Next best action heuristic from analytics
      setNextAction(buildNextAction(a.data, s.data));
      setLoading(false);
    });
    return () => { mounted = false; };
  }, []);

  const g = greeting();
  const GreetIcon = g.icon;
  const firstName = (userName || 'there').split(' ')[0];

  const mode = useMemo(() => deriveAriaMode({
    hotCount: hot,
    staleCount: stale,
    pendingFollowUps: stats?.pending_follow_ups || 0,
    recentOpensCount: stats?.recent_opens || 0,
  }), [hot, stale, stats]);

  if (loading) {
    return (
      <div className="rounded-2xl overflow-hidden animate-pulse" style={{ background: '#FAF7FF', border: '1px solid #E8E0F5', minHeight: 220 }} data-testid="aria-command-room-skeleton" />
    );
  }

  return (
    <div
      className="rounded-2xl overflow-hidden relative aria-fade-in"
      style={{
        background: 'linear-gradient(135deg, #FFFFFF 0%, #FAF7FF 50%, #FFF8EA 100%)',
        border: '1px solid #E8E0F5',
        boxShadow: '0 12px 32px rgba(124,53,220,0.06)',
      }}
      data-testid="aria-command-room"
    >
      {/* Soft brand ribbon */}
      <div
        aria-hidden
        style={{
          position: 'absolute', inset: 0, pointerEvents: 'none',
          background: 'radial-gradient(circle at 90% -10%, rgba(192,68,224,0.10), transparent 45%), radial-gradient(circle at -5% 110%, rgba(226,185,111,0.12), transparent 40%)',
        }}
      />

      {/* Top row — greeting + ARIA status pill */}
      <div className="relative px-6 md:px-8 pt-6 pb-3 flex items-start justify-between flex-wrap gap-4">
        <div className="flex-1 min-w-0">
          <div className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC] mb-2">
            <GreetIcon size={11} weight="fill" /> {g.text}, {firstName}
          </div>
          <h1 className="text-2xl md:text-3xl lg:text-4xl font-extrabold text-[#1A0A2E] leading-tight" style={{ fontFamily: 'Plus Jakarta Sans', letterSpacing: '-0.01em' }}>
            Your AI sales command room
          </h1>
          <p className="text-sm md:text-[15px] text-[#5A4A7A] mt-2 max-w-xl leading-relaxed">
            Aria is responding to leads, qualifying them, nurturing slow movers, and booking calls — so warm leads never go cold while you build your business.
          </p>
        </div>

        {/* ARIA Active pill — animated pulse */}
        <div className="flex flex-col items-end gap-2" data-testid="aria-status-pill">
          <div
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full backdrop-blur"
            style={{ background: 'rgba(255,255,255,0.85)', border: '1px solid #C9F2D9', boxShadow: '0 4px 14px rgba(22,163,74,0.12)' }}
          >
            <span className="relative flex items-center">
              <span className="absolute w-2.5 h-2.5 rounded-full bg-[#16A34A] opacity-60 aria-ping"></span>
              <span className="w-2 h-2 rounded-full bg-[#16A34A]"></span>
            </span>
            <span className="text-[11px] font-extrabold uppercase tracking-wider text-[#16A34A]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Aria active</span>
          </div>
          <div className="inline-flex items-center gap-1.5 text-[10px] text-[#5A4A7A]">
            <ShieldCheck size={11} weight="fill" className="text-[#16A34A]" /> Multi-tenant · DPDP-ready
          </div>
        </div>
      </div>

      {/* Stats row — today's pipeline at a glance */}
      <div className="relative px-6 md:px-8 pb-5 grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="today-summary">
        <StatCard
          icon={Fire}
          label="Hot leads"
          value={hot}
          tint="#DC2626"
          glow={hot > 0}
          onClick={() => navigate('/leads?tier=hot')}
          testid="stat-hot"
        />
        <StatCard
          icon={ChatCircleDots}
          label="Conversations today"
          value={todayConvos}
          tint="#7C35DC"
          onClick={() => navigate('/conversations')}
          testid="stat-convos"
        />
        <StatCard
          icon={Clock}
          label="Going cold"
          value={stale}
          tint="#D97706"
          onClick={() => navigate('/leads?stale=true')}
          testid="stat-stale"
        />
        <StatCard
          icon={CalendarCheck}
          label="Meetings this week"
          value={stats?.meetings_this_week ?? stats?.meetings_booked_this_week ?? 0}
          tint="#16A34A"
          onClick={() => navigate('/calendar')}
          testid="stat-meetings"
        />
      </div>

      {/* Bottom row — Aria personality panel + quick actions */}
      <div className="relative px-6 md:px-8 pb-6 grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-4">
        {/* Personality panel */}
        <div
          className="relative rounded-2xl p-5 overflow-hidden"
          style={{
            background: 'linear-gradient(135deg, #FFFFFF 0%, #FAFAFA 100%)',
            border: `1px solid ${mode.tint}33`,
            boxShadow: `0 8px 24px ${mode.tint}10`,
          }}
          data-testid="aria-personality-panel"
        >
          <div className="flex items-start gap-4">
            <div className="relative flex-shrink-0">
              <div
                className="w-12 h-12 rounded-2xl flex items-center justify-center"
                style={{ background: `linear-gradient(135deg, ${mode.tint} 0%, ${mode.tint}88 100%)`, boxShadow: `0 6px 16px ${mode.tint}33` }}
              >
                <Robot size={22} weight="fill" className="text-white" />
              </div>
              <span className="absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 rounded-full border-2 border-white" style={{ background: mode.tint }}></span>
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap mb-1">
                <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#5A4A7A]">Aria is watching your pipeline</span>
                <span
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-extrabold border"
                  style={{ background: mode.bg, borderColor: mode.tint + '55', color: mode.tint }}
                  data-testid="aria-mode-chip"
                >
                  <span className="w-1.5 h-1.5 rounded-full aria-soft-pulse" style={{ background: mode.tint }}></span>
                  {mode.label}
                </span>
              </div>
              <p className="text-sm text-[#1A0A2E] font-semibold leading-snug" style={{ fontFamily: 'Plus Jakarta Sans' }}>
                {nextAction?.title || mode.note}
              </p>
              {nextAction?.subtitle && (
                <p className="text-xs text-[#5A4A7A] mt-1 leading-relaxed">{nextAction.subtitle}</p>
              )}
              <div className="flex items-center gap-2 mt-3 flex-wrap">
                {nextAction?.cta && (
                  <button
                    onClick={() => navigate(nextAction.cta.to)}
                    data-testid="aria-cta-primary"
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-extrabold text-white transition-all hover:scale-[1.02]"
                    style={{ background: 'var(--gradient-brand)', fontFamily: 'Plus Jakarta Sans' }}
                  >
                    {nextAction.cta.label} <ArrowRight size={12} weight="bold" />
                  </button>
                )}
                <button
                  onClick={() => navigate('/ai-assistant')}
                  data-testid="ask-aria-btn"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold text-[#7C35DC] bg-white border border-[#7C35DC]/30 hover:bg-[#F4F0FF] transition-all"
                  style={{ fontFamily: 'Plus Jakarta Sans' }}
                >
                  <Sparkle size={11} weight="fill" /> Ask Aria what to do next
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Quick actions */}
        <div className="grid grid-cols-2 gap-2" data-testid="quick-actions">
          <QuickAction icon={Plus} label="Add lead" tint="#7C35DC" onClick={() => navigate('/leads?action=new')} testid="qa-add-lead" />
          <QuickAction icon={Lightning} label="Your 5 today" tint="#E2B96F" onClick={() => navigate('/your-5-today')} testid="qa-five-today" />
          <QuickAction icon={Users} label="Pipeline" tint="#0055FF" onClick={() => navigate('/pipeline')} testid="qa-pipeline" />
          <QuickAction icon={Headset} label="Conversations" tint="#16A34A" onClick={() => navigate('/conversations')} testid="qa-conversations" />
        </div>
      </div>

      <style>{`
        @keyframes aria-ping {
          0%   { transform: scale(1); opacity: 0.6; }
          75%, 100% { transform: scale(2.4); opacity: 0; }
        }
        @keyframes aria-soft-pulse {
          0%,100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(0.85); }
        }
        @keyframes aria-fade-in {
          from { opacity: 0; transform: translateY(6px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .aria-ping { animation: aria-ping 1.8s cubic-bezier(0,0,0.2,1) infinite; }
        .aria-soft-pulse { animation: aria-soft-pulse 2.4s ease-in-out infinite; }
        .aria-fade-in { animation: aria-fade-in 480ms ease-out both; }
        .aria-stat-card { transition: transform 200ms ease, box-shadow 200ms ease, border-color 200ms ease; }
        .aria-stat-card:hover { transform: translateY(-2px); box-shadow: 0 10px 24px rgba(26,10,46,0.08); }
        .aria-stat-hot { box-shadow: 0 0 0 4px rgba(220,38,38,0.10), 0 8px 18px rgba(220,38,38,0.18); }
        .aria-stat-hot:hover { box-shadow: 0 0 0 6px rgba(220,38,38,0.14), 0 12px 26px rgba(220,38,38,0.24); }
        .aria-quick-btn { transition: transform 160ms ease, background 160ms ease, border-color 160ms ease; }
        .aria-quick-btn:hover { transform: translateY(-1px); }
        .aria-quick-btn:active { transform: scale(0.98); }
      `}</style>
    </div>
  );
};

const StatCard = ({ icon: Icon, label, value, tint, glow, onClick, testid }) => (
  <button
    onClick={onClick}
    data-testid={testid}
    className={`aria-stat-card text-left rounded-xl p-4 bg-white/85 backdrop-blur ${glow ? 'aria-stat-hot' : ''}`}
    style={{ border: `1px solid ${glow ? tint + '55' : '#E8E0F5'}`, boxShadow: glow ? undefined : '0 4px 12px rgba(26,10,46,0.04)' }}
  >
    <div className="flex items-center justify-between mb-1">
      <span className="text-[9px] font-bold uppercase tracking-[0.18em] text-[#5A4A7A]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{label}</span>
      <Icon size={14} weight="fill" style={{ color: tint }} />
    </div>
    <div className="flex items-baseline gap-1">
      <span className="text-2xl md:text-3xl font-extrabold leading-none" style={{ color: tint, fontFamily: 'Plus Jakarta Sans' }}>{value}</span>
      <ArrowUpRight size={12} weight="bold" className="ml-auto text-[#9B8AB0]" />
    </div>
  </button>
);

const QuickAction = ({ icon: Icon, label, tint, onClick, testid }) => (
  <button
    onClick={onClick}
    data-testid={testid}
    className="aria-quick-btn flex flex-col items-start gap-2 rounded-xl p-3 bg-white/90 backdrop-blur"
    style={{ border: '1px solid #E8E0F5' }}
  >
    <div
      className="w-8 h-8 rounded-lg flex items-center justify-center"
      style={{ background: tint + '15', border: `1px solid ${tint}33` }}
    >
      <Icon size={14} weight="fill" style={{ color: tint }} />
    </div>
    <span className="text-xs font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{label}</span>
  </button>
);

// ──────────────────────────────────────────────────────────────────────────
// Next best action heuristic — uses real backend stats, never invents data
// ──────────────────────────────────────────────────────────────────────────
function buildNextAction(analytics, staleData) {
  const hot = analytics?.leads_by_tier?.hot || 0;
  const meetings = analytics?.meetings_this_week || analytics?.meetings_booked_this_week || 0;
  const pending = analytics?.pending_follow_ups || 0;
  const stale = staleData?.count || staleData?.total || 0;

  if (hot >= 3) {
    return {
      title: `${hot} hot leads ready to act on now.`,
      subtitle: 'Aria has surfaced your highest-intent prospects — start with the top one.',
      cta: { label: 'Open hot leads', to: '/leads?tier=hot' },
    };
  }
  if (stale >= 5) {
    return {
      title: `${stale} leads have gone cold.`,
      subtitle: 'Aria is preparing re-engagement messages. Review the queue and approve.',
      cta: { label: 'Review cold leads', to: '/leads?stale=true' },
    };
  }
  if (pending > 0) {
    return {
      title: `${pending} follow-ups queued for today.`,
      subtitle: 'Aria will fire them on schedule — or you can send one now.',
      cta: { label: 'Open Your 5 Today', to: '/your-5-today' },
    };
  }
  if (meetings > 0) {
    return {
      title: `${meetings} meeting${meetings === 1 ? '' : 's'} on your calendar this week.`,
      subtitle: 'Review the brief Aria prepared for each one before you walk in.',
      cta: { label: 'View briefs', to: '/aria-agent/briefs' },
    };
  }
  return {
    title: 'Pipeline is calm — perfect time to bring in new leads.',
    subtitle: 'Aria is listening. Drop in a CSV, connect an integration, or share your widget.',
    cta: { label: 'Add a lead', to: '/leads?action=new' },
  };
}

export default AriaCommandRoom;
