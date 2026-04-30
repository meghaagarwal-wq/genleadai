import React, { useState } from 'react';
import PublicLayout from '../PublicLayout';
import useSEO, { BASE_URL } from '../useSEO';
import {
  SEOHero, Section, BottomCTA, Breadcrumbs, softwareAppSchema, webPageSchema, breadcrumbSchema,
} from '../shared';
import {
  Fire, Clock, ChartLineUp, ChatCircle, Warning, Sparkle, ArrowRight, PhoneCall,
  TrendUp, Funnel, Brain, CheckCircle, EnvelopeOpen, Lightning, FileText,
} from '@phosphor-icons/react';

const URL = `${BASE_URL}/aria/demo-dashboard`;

// === FAKE / DEMO DATA ONLY — NO REAL USER INFO ===
const STORIES = [
  { name: 'Priya', company: 'GrowthNest', signal: 'Hot lead', accent: '#DC2626', initials: 'PR', icp: 92 },
  { name: 'Rohit', company: 'SaaSWorks', signal: 'Proposal viewed', accent: '#D97706', initials: 'RO', icp: 87 },
  { name: 'Ananya', company: 'ScaleHive', signal: 'Follow-up due', accent: '#7C35DC', initials: 'AN', icp: 81 },
  { name: 'Karan', company: 'CloudNest', signal: 'Pricing asked', accent: '#16A34A', initials: 'KA', icp: 78 },
  { name: 'Meera', company: 'OrbitLabs', signal: 'Silent 14d', accent: '#9B8AB0', initials: 'ME', icp: 73 },
  { name: 'Arjun', company: 'PixelForge', signal: 'New inbound', accent: '#C044E0', initials: 'AR', icp: 69 },
];

const FEED = [
  { signal: 'Hot lead · ICP 92', lead: 'Priya', company: 'GrowthNest', channel: 'WhatsApp', why: 'Asked pricing twice in 48h. Competitor shortlisted. Needs founder reply today.', reco: 'Send founder voice note + two call slots.', tone: 'urgent' },
  { signal: 'Proposal opened 3×', lead: 'Rohit', company: 'SaaSWorks', channel: 'Email', why: 'Opened proposal 3× but has not replied. Decision window is closing.', reco: 'Specific deadline message + 15-min unblock call.', tone: 'high' },
  { signal: 'Follow-up due', lead: 'Ananya', company: 'ScaleHive', channel: 'WhatsApp', why: 'Last touch 5 days ago. Thread was warm. Ready for a soft nudge.', reco: 'ARIA drafted a reply. Approve to send.', tone: 'medium' },
  { signal: 'Pricing question', lead: 'Karan', company: 'CloudNest', channel: 'Email', why: 'Asked for a 50-seat pricing. High commercial intent.', reco: 'Founder-led reply, position ROI, schedule a walkthrough.', tone: 'high' },
  { signal: 'Silent 14+ days', lead: 'Meera', company: 'OrbitLabs', channel: 'LinkedIn', why: 'Was ICP-fit and warm. Went silent after demo.', reco: 'Revival journey Day 1 — empathy + curiosity message.', tone: 'medium' },
];

const STATS = [
  { label: 'Hot leads', value: 3, icon: Fire, accent: '#DC2626', subtitle: 'ICP ≥ 80, needs reply today' },
  { label: 'Follow-ups due', value: 12, icon: Clock, accent: '#D97706', subtitle: 'Scheduled within next 24h' },
  { label: 'Revenue at risk', value: '$84K', icon: Warning, accent: '#DC2626', subtitle: '4 stuck proposals, 7 silent leads' },
  { label: 'Demos booked', value: 4, icon: PhoneCall, accent: '#16A34A', subtitle: 'This week via Calendly' },
];

const REPLY_TONES = ['Founder-led', 'Consultative', 'Closer', 'Nurture', 'Premium'];
const REPLY_CHANNELS = ['WhatsApp', 'Email', 'LinkedIn', 'Call script'];

const DemoDashboard = () => {
  const [channel, setChannel] = useState('WhatsApp');
  const [tone, setTone] = useState('Founder-led');

  useSEO({
    title: 'ARIA Demo Dashboard | AI Sales Workspace',
    description: 'Explore ARIA's demo dashboard with Lead Feed, ARIA Stories, Morning Brief, AI reply suggestions, hot leads, follow-ups due, revenue at risk, and sales intelligence reports.',
    canonical: URL,
    jsonLd: [
      softwareAppSchema({
        description: 'ARIA AI Sales Workspace demo — explore Lead Feed, ARIA Stories, Morning Brief, AI reply suggestions, hot leads, follow-ups, revenue at risk, and sales reports.',
        url: URL,
      }),
      webPageSchema({ name: 'ARIA Demo Dashboard | AI Sales Workspace', description: 'Public demo of ARIA AI Sales Workspace.', url: URL }),
      breadcrumbSchema([{ label: 'ARIA', to: '/aria' }, { label: 'Demo Dashboard' }]),
    ],
  });

  const sampleReply = `Hey Priya — quick one. Based on our last thread about GrowthNest's outbound motion, I think we can plug your follow-up gap in week one. Worth a 20-min call this week? Tuesday 4 PM or Wednesday 11 AM works on my side.`;

  return (
    <PublicLayout>
      <SEOHero
        eyebrow="DEMO WORKSPACE · SAMPLE DATA"
        title="AI Sales Dashboard for Founders and Startups"
        subtitle="This is a public preview of the ARIA workspace — Lead Feed, ARIA Stories, Morning Brief, AI-drafted replies, hot leads, follow-ups due, and revenue at risk. All data below is sample data to show how ARIA works."
      />

      <Section tone="muted">
        <Breadcrumbs items={[{ label: 'ARIA', to: '/aria' }, { label: 'Demo Dashboard' }]} />

        {/* Demo disclaimer */}
        <div className="bg-[#FEF3C7] border border-[#FDE68A] rounded-2xl px-5 py-4 mb-8 flex items-start gap-3" data-testid="demo-disclaimer">
          <Sparkle size={18} weight="fill" className="text-[#D97706] mt-0.5 flex-shrink-0" />
          <div>
            <div className="text-sm font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Space Grotesk, Inter, sans-serif' }}>Demo Workspace</div>
            <p className="text-sm text-[#5A4A7A] mt-1">This is sample data created to show how ARIA works. No real lead data is displayed. <a href="/login" className="font-bold text-[#7C35DC] hover:underline">Sign in</a> to use the real ARIA workspace.</p>
          </div>
        </div>

        {/* ARIA Morning Brief */}
        <div className="rounded-2xl p-6 relative overflow-hidden mb-8" data-testid="demo-morning-brief"
          style={{ background: 'linear-gradient(135deg,#0E0820 0%,#1A0F38 45%,#7C35DC 100%)' }}>
          <div className="absolute inset-0 opacity-50 pointer-events-none" style={{ background: 'var(--gradient-aria-glow)' }} />
          <div className="relative">
            <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#C9B6FF] mb-3">ARIA MORNING BRIEF · WEDNESDAY</div>
            <h2 className="font-display text-2xl md:text-3xl font-extrabold text-white leading-tight max-w-3xl">
              Good morning. You have 3 hot leads today and 12 follow-ups due. Your strongest signal is 4 active proposals — Rohit (SaaSWorks) opened yours 3× and is ready. ARIA recommends starting with Priya before any new outreach.
            </h2>
            <div className="mt-4 flex flex-wrap gap-2">
              {['3 hot', '12 follow-ups', '4 proposals', '7 silent'].map((b, i) => (
                <span key={i} className="text-[10px] font-bold uppercase tracking-[0.2em] px-2.5 py-1 rounded-full bg-white/15 border border-white/20 text-white">{b}</span>
              ))}
            </div>
          </div>
        </div>

        {/* Stats grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8" data-testid="demo-stats">
          {STATS.map((s, i) => (
            <div key={i} className="bg-white border border-[#E8E0F5] rounded-2xl p-4" data-testid={`demo-stat-${s.label.toLowerCase().replace(/\s+/g, '-')}`} style={{ boxShadow: 'var(--shadow-card)' }}>
              <div className="w-8 h-8 rounded-lg flex items-center justify-center mb-3" style={{ background: `${s.accent}14`, border: `1px solid ${s.accent}33` }}>
                <s.icon size={14} weight="fill" style={{ color: s.accent }} />
              </div>
              <div className="text-3xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Space Grotesk, Inter, sans-serif' }}>{s.value}</div>
              <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#7B6D9C] mt-1">{s.label}</div>
              <div className="text-[10px] text-[#9B8AB0] mt-1">{s.subtitle}</div>
            </div>
          ))}
        </div>

        {/* ARIA Stories */}
        <div className="bg-white border border-[#E8E0F5] rounded-2xl p-6 mb-8" data-testid="demo-stories" style={{ boxShadow: 'var(--shadow-card)' }}>
          <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC] mb-2">— ARIA STORIES</div>
          <h3 className="font-display text-xl md:text-2xl font-extrabold text-[#1A0A2E]">Leads that need your attention today</h3>
          <p className="text-xs text-[#7B6D9C] mt-1 mb-4">Tap a ring to see why ARIA flagged them. (Demo · read-only)</p>
          <div className="flex gap-4 overflow-x-auto pb-2">
            {STORIES.map((s, i) => (
              <div key={i} className="flex flex-col items-center gap-2 flex-shrink-0" data-testid={`demo-story-${s.name.toLowerCase()}`}>
                <div className="w-16 h-16 rounded-full p-[2px]" style={{ background: `conic-gradient(${s.accent} 0deg, ${s.accent}55 180deg, ${s.accent} 360deg)` }}>
                  <div className="w-full h-full rounded-full bg-white flex items-center justify-center">
                    <div className="w-[54px] h-[54px] rounded-full flex items-center justify-center text-sm font-extrabold text-white" style={{ background: `linear-gradient(135deg, ${s.accent}, ${s.accent}AA)` }}>{s.initials}</div>
                  </div>
                </div>
                <div className="text-xs font-bold text-[#1A0A2E]">{s.name}</div>
                <span className="text-[9px] font-bold uppercase tracking-[0.15em] px-1.5 py-0.5 rounded-md" style={{ background: `${s.accent}14`, color: s.accent, border: `1px solid ${s.accent}33` }}>{s.signal}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Lead Feed + Ask ARIA Reply */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          <div className="lg:col-span-2 bg-white border border-[#E8E0F5] rounded-2xl overflow-hidden" data-testid="demo-lead-feed" style={{ boxShadow: 'var(--shadow-card)' }}>
            <div className="px-6 py-4 border-b border-[#F0ECF9]">
              <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC]">— LEAD FEED</div>
              <h3 className="font-display text-xl md:text-2xl font-extrabold text-[#1A0A2E]">Buying signals, ranked by urgency</h3>
              <p className="text-xs text-[#7B6D9C] mt-1">Every card is one sales action away from closed.</p>
            </div>
            <div className="divide-y divide-[#F0ECF9]">
              {FEED.map((f, i) => (
                <article key={i} className="px-6 py-4" data-testid={`demo-feed-${i}`}>
                  <div className="flex items-center gap-2 mb-2 flex-wrap">
                    <span className={`text-[9px] font-bold uppercase tracking-[0.2em] px-2 py-0.5 rounded-md ${
                      f.tone === 'urgent' ? 'bg-[#FEE2E2] text-[#DC2626] border border-[#DC2626]/30' :
                      f.tone === 'high' ? 'bg-[#FEF3C7] text-[#D97706] border border-[#D97706]/30' :
                      'bg-[#F4F0FF] text-[#7C35DC] border border-[#7C35DC]/30'
                    }`}>{f.signal}</span>
                    <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#5A4A7A]">{f.channel}</span>
                  </div>
                  <div className="text-base font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Space Grotesk, Inter, sans-serif' }}>{f.lead} · <span className="text-[#5A4A7A] font-semibold">{f.company}</span></div>
                  <p className="text-sm text-[#5A4A7A] mt-1">{f.why}</p>
                  <div className="mt-2 flex items-start gap-2 text-sm text-[#1A0A2E] bg-[#FAF7FF] border border-[#EDE5FA] rounded-xl px-3 py-2">
                    <Sparkle size={12} weight="fill" className="text-[#7C35DC] mt-0.5 flex-shrink-0" />
                    <span><strong>ARIA recommends:</strong> {f.reco}</span>
                  </div>
                </article>
              ))}
            </div>
          </div>

          {/* Ask ARIA to Reply */}
          <aside className="bg-white border border-[#E8E0F5] rounded-2xl p-6" data-testid="demo-ask-reply" style={{ boxShadow: 'var(--shadow-card)' }}>
            <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC] mb-2">— ASK ARIA TO REPLY</div>
            <h3 className="font-display text-lg font-extrabold text-[#1A0A2E]">Reply for Priya · GrowthNest</h3>
            <div className="mt-4">
              <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#7B6D9C] mb-1.5">Channel</div>
              <div className="flex flex-wrap gap-1.5">
                {REPLY_CHANNELS.map(c => (
                  <button key={c} onClick={() => setChannel(c)} data-testid={`demo-channel-${c.toLowerCase().replace(/\s+/g, '-')}`}
                    className={`px-2.5 py-1 rounded-lg text-[11px] font-bold border ${channel === c ? 'bg-[#7C35DC] text-white border-[#7C35DC]' : 'bg-white text-[#5A4A7A] border-[#E8E0F5]'}`}>{c}</button>
                ))}
              </div>
              <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#7B6D9C] mb-1.5 mt-4">Tone</div>
              <div className="flex flex-wrap gap-1.5">
                {REPLY_TONES.map(t => (
                  <button key={t} onClick={() => setTone(t)} data-testid={`demo-tone-${t.toLowerCase().replace(/\s+/g, '-')}`}
                    className={`px-2.5 py-1 rounded-lg text-[11px] font-bold border ${tone === t ? 'bg-[#7C35DC] text-white border-[#7C35DC]' : 'bg-white text-[#5A4A7A] border-[#E8E0F5]'}`}>{t}</button>
                ))}
              </div>
              <div className="mt-4 rounded-xl p-4 text-sm text-[#1A0A2E] leading-relaxed" style={{ background: 'linear-gradient(135deg,#F4F0FF,#FAF7FF)', border: '1px solid #E0D4F7' }}>
                {sampleReply}
              </div>
              <div className="text-[10px] text-[#9B8AB0] mt-2">ARIA reply · {channel} · {tone} · demo output</div>
            </div>
          </aside>
        </div>

        {/* Pipeline Mood + Reports preview */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          <div className="bg-[#FEF3C7] border border-[#FDE68A] rounded-2xl p-6" data-testid="demo-pipeline-mood">
            <div className="inline-flex items-center gap-2 mb-2">
              <Warning size={14} weight="fill" className="text-[#D97706]" />
              <span className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#D97706]">PIPELINE MOOD</span>
            </div>
            <h3 className="font-display text-xl font-extrabold text-[#1A0A2E]">"Hot pipeline — needs sharper CTAs"</h3>
            <p className="text-sm text-[#5A4A7A] mt-2">You have 3 hot leads and 12 follow-ups due. Tighten your booking nudge — slot offers, not "when works?".</p>
            <div className="mt-4 grid grid-cols-3 gap-2 text-center">
              {[{ l: 'Active', v: 41 }, { l: 'Hot', v: 3 }, { l: 'Silent', v: 19 }].map((m, i) => (
                <div key={i}>
                  <div className="text-xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Space Grotesk, Inter, sans-serif' }}>{m.v}</div>
                  <div className="text-[9px] font-bold uppercase tracking-[0.2em] text-[#5A4A7A]">{m.l}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Reports preview */}
          <div className="lg:col-span-2 bg-white border border-[#E8E0F5] rounded-2xl p-6" data-testid="demo-reports-preview" style={{ boxShadow: 'var(--shadow-card)' }}>
            <div className="flex items-center gap-2 mb-2">
              <ChartLineUp size={14} weight="fill" className="text-[#7C35DC]" />
              <span className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC]">REPORTS PREVIEW</span>
            </div>
            <h3 className="font-display text-xl font-extrabold text-[#1A0A2E]">Sales intelligence snapshot</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
              {[
                { l: 'Reply time', v: '18m', icon: ChatCircle },
                { l: 'Book rate', v: '27%', icon: PhoneCall },
                { l: 'Top channel', v: 'WhatsApp', icon: Lightning },
                { l: 'Top objection', v: 'Pricing', icon: Funnel },
              ].map((r, i) => (
                <div key={i} className="bg-[#FAF7FF] border border-[#EDE5FA] rounded-xl p-3">
                  <r.icon size={14} weight="fill" className="text-[#7C35DC] mb-1" />
                  <div className="text-lg font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Space Grotesk, Inter, sans-serif' }}>{r.v}</div>
                  <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#7B6D9C]">{r.l}</div>
                </div>
              ))}
            </div>
            <a href="/aria/sales-reports" className="inline-flex items-center gap-1 text-xs font-bold text-[#7C35DC] hover:underline mt-4" data-testid="reports-deep-link">
              See full Sales Reports <ArrowRight size={12} weight="bold" />
            </a>
          </div>
        </div>
      </Section>

      <BottomCTA
        title="This is just the demo. Sign in to run ARIA on your real leads."
        subtitle="ARIA reads your actual conversations, drafts replies in your voice, and surfaces revenue at risk — from day one."
      />
    </PublicLayout>
  );
};

export default DemoDashboard;
