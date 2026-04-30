import React from 'react';
import PublicLayout from '../PublicLayout';
import useSEO, { BASE_URL } from '../useSEO';
import {
  SEOHero, Section, FeatureGrid, FAQAccordion, BottomCTA, Breadcrumbs,
  softwareAppSchema, faqSchema, webPageSchema, breadcrumbSchema,
} from '../shared';

const URL = `${BASE_URL}/aria/lead-feed`;

const FAQ = [
  { q: 'What is a Lead Feed?', a: 'A Lead Feed is a living stream of sales signals — hot leads, follow-ups due, proposal opens, pricing questions, silent threads — ranked by urgency. Unlike a spreadsheet, it tells you which lead to contact first and what to say.' },
  { q: 'How does ARIA detect buying signals?', a: 'ARIA reads every conversation across WhatsApp, email, and LinkedIn, and looks for intent markers: pricing questions, proposal re-opens, deadline mentions, competitor mentions, multi-reply threads, and silent-but-ICP-fit patterns.' },
  { q: 'How does ARIA prioritise hot leads?', a: 'ARIA scores every lead against your ICP, combines it with activity signals (recency, response velocity, intent markers), and surfaces the top signals in the Feed first — hot and ready-to-close at the top, revival candidates lower.' },
  { q: 'How does ARIA recommend replies?', a: 'For every card in the Feed, ARIA generates a next-best-action with an AI-drafted message in your founder tone — grounded in the lead's conversation history and your workspace training.' },
  { q: 'Why does a Lead Feed work better than spreadsheets?', a: 'Spreadsheets are storage. A Lead Feed is action. You scroll urgency, not alphabet. Every card has a signal, a reason, and a drafted reply — so you never wonder who to contact next.' },
  { q: 'Can ARIA replace a CRM for lead management?', a: 'For founder-led teams, yes. ARIA captures, qualifies, follows up, and reports — without the 6-month CRM implementation. If you need deep multi-stage pipeline reporting for enterprise sales ops, pair ARIA with a CRM.' },
];

const FEATURES = [
  { title: 'Proposal opens', body: 'ARIA watches proposal views. Opened 3×? Decision is close — ARIA drafts a founder nudge.' },
  { title: 'Pricing questions', body: 'Pricing questions are commercial intent. ARIA surfaces them in red and drafts an ROI-first reply.' },
  { title: 'Silent high-ICP', body: 'Silent 14+ days but ICP-fit? ARIA starts a Day 1/4/9/15/30 revival journey.' },
  { title: 'Follow-ups due', body: 'Every due follow-up lands in the Feed with an ARIA-drafted reply ready to approve.' },
  { title: 'Competitor mentioned', body: 'ARIA detects competitor mentions and surfaces them with positioning-first copy.' },
  { title: 'Next best action', body: 'Every card tells you the signal, why it matters, and what to do. No decision fatigue.' },
];

const LeadFeedSEO = () => {
  useSEO({
    title: 'ARIA Lead Feed | AI Lead Management Dashboard',
    description: 'ARIA Lead Feed shows hot leads, buying signals, follow-ups due, proposal views, pricing objections, and next best actions in one AI-powered sales workspace.',
    canonical: URL,
    jsonLd: [
      softwareAppSchema({ description: 'ARIA Lead Feed — AI lead management dashboard.', url: URL }),
      faqSchema(FAQ),
      webPageSchema({ name: 'ARIA Lead Feed | AI Lead Management Dashboard', description: 'AI lead management dashboard with buying signals and next best actions.', url: URL }),
      breadcrumbSchema([{ label: 'ARIA', to: '/aria' }, { label: 'Lead Feed' }]),
    ],
  });

  return (
    <PublicLayout>
      <SEOHero
        eyebrow="LEAD FEED"
        title="Lead Feed for Sales Teams"
        subtitle="Every buying signal, ranked by urgency. Proposal opens, pricing questions, silent threads, and follow-ups due — in one living feed with ARIA-drafted replies for each."
      />

      <Section tone="light">
        <Breadcrumbs items={[{ label: 'ARIA', to: '/aria' }, { label: 'Lead Feed' }]} />

        <div className="grid md:grid-cols-2 gap-10 items-start">
          <div className="space-y-4 text-base text-[#1A0A2E] leading-relaxed max-w-2xl">
            <h2 className="font-display text-2xl md:text-3xl font-extrabold text-[#1A0A2E] tracking-tight">What is a Lead Feed?</h2>
            <p>A Lead Feed is a living stream of sales signals — ranked by urgency, not by alphabet. Every card shows a lead, a detected signal (hot lead, proposal opened, pricing asked, silent after demo), why it matters, and what ARIA recommends doing next.</p>
            <p>Think of it as your sales radar: you open ARIA in the morning and immediately see the 5 leads most likely to convert today. No scrolling, no scanning, no "who should I call first?"</p>
          </div>
          <div className="bg-[#F4F0FF] border border-[#E0D4F7] rounded-2xl p-6">
            <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC] mb-3">ANSWER-FIRST</div>
            <blockquote className="font-display text-xl md:text-2xl font-extrabold text-[#1A0A2E] leading-tight">
              ARIA Lead Feed is an AI-ranked stream of buying signals — hot leads, follow-ups due, proposal opens, pricing questions — with a drafted reply for each.
            </blockquote>
          </div>
        </div>
      </Section>

      <Section eyebrow="HOW IT WORKS" title="How ARIA detects buying signals" tone="muted">
        <FeatureGrid features={FEATURES} />
      </Section>

      <Section eyebrow="WHY IT'S BETTER" title="Why Lead Feed beats spreadsheets and CRM lists">
        <div className="grid md:grid-cols-3 gap-4">
          {[
            { h: 'Ranked by urgency', p: 'Urgency-ranked means you never scroll past a hot lead to reach a stale one.' },
            { h: 'Drafted replies included', p: 'Every signal has a one-tap reply ready — no blank-page staring.' },
            { h: 'Grounded in your voice', p: 'Replies use your tone, training, and past conversations — not generic templates.' },
          ].map((b, i) => (
            <div key={i} className="bg-white border border-[#E8E0F5] rounded-2xl p-5" data-testid={`lf-why-${i}`}>
              <h3 className="text-lg font-extrabold text-[#1A0A2E]">{b.h}</h3>
              <p className="text-sm text-[#5A4A7A] mt-2 leading-relaxed">{b.p}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section eyebrow="COMMON QUESTIONS" title="Lead Feed FAQs" tone="muted">
        <FAQAccordion items={FAQ} />
      </Section>

      <BottomCTA title="See ARIA Lead Feed in action" subtitle="Open the demo dashboard to see buying signals ranked by urgency — with sample data." />
    </PublicLayout>
  );
};

export default LeadFeedSEO;
