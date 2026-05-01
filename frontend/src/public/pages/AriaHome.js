import React from 'react';
import PublicLayout from '../PublicLayout';
import useSEO, { BASE_URL } from '../useSEO';
import {
  SEOHero, Section, FeatureGrid, FAQAccordion, BottomCTA, CTAButtons,
  softwareAppSchema, faqSchema, webPageSchema,
} from '../shared';
import { ChatText, Stack, Lightning, Sparkle, Brain, PhoneCall, TrendUp, ShieldCheck, Users } from '@phosphor-icons/react';

const URL = `${BASE_URL}/aria`;

const FAQ = [
  { q: 'What is ARIA?', a: 'ARIA is an AI sales assistant for founders and startups that manages leads, follow-ups, replies, demo booking, sales reports, and revenue signals from one sales workspace.' },
  { q: 'Who is ARIA for?', a: 'ARIA is built for founders, startups, agencies, consultants, and small sales teams that cannot yet hire a full-time sales team but still need predictable pipeline, follow-ups, and booked calls.' },
  { q: 'How is ARIA different from a CRM?', a: 'A CRM stores leads. ARIA works them. CRMs record pipeline data; ARIA reads every conversation, detects buying signals, drafts replies in your voice, books demos, and tells founders what to do next.' },
  { q: 'Can ARIA help with follow-ups?', a: 'Yes. ARIA writes and sends follow-ups across WhatsApp, email, and LinkedIn, and escalates to you only when a human touch is needed — like pricing, objections, or hot leads ready to buy.' },
  { q: 'Can ARIA write replies?', a: 'Yes. ARIA drafts replies in your tone (founder-led, consultative, premium, closer, nurture) grounded in your workspace training and each lead\'s conversation history. You approve, edit or send.' },
  { q: 'Can ARIA track revenue at risk?', a: 'Yes. ARIA surfaces stuck proposals, silent high-ICP leads, unactioned hot leads, and conversations at risk of going cold — quantified in pipeline value.' },
  { q: 'Can ARIA help book demos?', a: 'Yes. ARIA qualifies leads against your ICP, then books calls on your Calendly with suggested time slots tailored to each lead\'s intent level.' },
  { q: 'What does ARIA\'s dashboard show?', a: 'ARIA\'s workspace shows a Morning Brief, ARIA Stories (Instagram-style rings of leads that need attention today), a Lead Feed of buying signals, Pipeline Mood, hot leads, follow-ups due, and live revenue at risk.' },
];

const FEATURES = [
  { title: 'Lead Feed', body: 'Every buying signal, ranked by urgency. Proposal opens, pricing questions, silent threads and follow-ups due — all in one living feed.' },
  { title: 'ARIA Stories', body: 'Instagram-style rings of the 10 leads that need attention today. Tap one and ARIA tells you why, what to say, and drafts a reply.' },
  { title: 'Ask ARIA to Reply', body: 'Pick a channel (WhatsApp, email, LinkedIn, call script) and a tone (founder-led, closer, nurture). ARIA writes the message grounded in lead context.' },
  { title: 'Daily Sales Brief', body: 'A 3-sentence morning brief: what\'s hot, what\'s stuck, what to ship first. Claude-powered, grounded in your workspace data.' },
  { title: 'Sales Reports', body: 'Pipeline intelligence, channel performance, follow-up gaps, top objections, lost reasons, and ARIA-recommended actions.' },
  { title: 'Revenue at Risk', body: 'Quantified pipeline at risk — stuck proposals, silent ICP-80+ leads, unactioned hot leads — with one-tap revival playbooks.' },
];

const AriaHome = () => {
  useSEO({
    title: 'ARIA | AI Sales Assistant for Founders and Startups',
    description: 'ARIA is an AI sales assistant for founders and startups. Manage leads, follow-ups, WhatsApp replies, email nudges, demo booking, sales reports, and revenue signals from one AI-powered sales workspace.',
    canonical: URL,
    jsonLd: [
      softwareAppSchema({
        description: 'ARIA is an AI sales assistant for founders and startups that manages leads, follow-ups, replies, demo booking, sales reports, and revenue signals from one sales workspace.',
        url: URL,
      }),
      faqSchema(FAQ),
      webPageSchema({
        name: 'ARIA | AI Sales Assistant for Founders and Startups',
        description: 'ARIA is an AI sales assistant for founders and startups.',
        url: URL,
      }),
    ],
  });

  return (
    <PublicLayout>
      <SEOHero
        eyebrow="ARIA · YOUR FIRST AI SALES HIRE"
        title="AI Sales Assistant for Founders and Startups"
        subtitle="ARIA captures, qualifies, nurtures, replies, books demos, writes founder briefs, and revives silent leads — from one AI-powered sales workspace. Deploy your first AI sales hire before building a sales team."
      >
        <CTAButtons secondary={{ label: 'Explore demo dashboard', to: '/aria/demo-dashboard' }} testId="hero-cta" />
      </SEOHero>

      {/* Answer-first definition */}
      <Section eyebrow="WHAT IS ARIA" title="An AI sales assistant that works your leads — not just stores them.">
        <div className="grid md:grid-cols-2 gap-8 items-start">
          <div className="space-y-5 text-base text-[#1A0A2E] leading-relaxed">
            <p>
              <strong>ARIA is an AI sales assistant for founders, startups, agencies, consultants, and small teams</strong> that cannot yet hire a full-time sales ops person. ARIA captures every lead, qualifies against your ICP, follows up on WhatsApp, email and LinkedIn, books demos on your Calendly, and escalates to you only when a human touch is needed.
            </p>
            <p>
              Unlike a CRM, ARIA is action-first. It reads every reply, detects buying signals, drafts replies in your tone, prepares a founder brief before every call, and surfaces revenue at risk in your pipeline — so you always know what to do next.
            </p>
          </div>
          <div className="bg-[#F4F0FF] border border-[#E0D4F7] rounded-2xl p-6">
            <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC] mb-3">BRAND PROMISE</div>
            <blockquote className="font-display text-2xl md:text-3xl font-extrabold text-[#1A0A2E] leading-[1.15]">
              "Your CRM stores leads. ARIA works them."
            </blockquote>
            <p className="text-sm text-[#5A4A7A] mt-4">
              ARIA is not a CRM, not a chatbot, not an automation dashboard. It's an AI sales hire that ships replies in your voice while you sleep.
            </p>
          </div>
        </div>
      </Section>

      {/* Why not a CRM */}
      <Section eyebrow="WHY ARIA IS NOT A CRM" title="A CRM stores pipeline. ARIA tells founders what to do next." tone="muted">
        <div className="grid md:grid-cols-3 gap-4">
          {[
            { icon: Stack, h: 'A CRM is storage', p: 'CRMs record contacts, deals, and activity logs. They do not read conversations, draft messages, or decide next steps.' },
            { icon: Brain, h: 'ARIA is action', p: 'ARIA reads every thread, detects signals, and tells you exactly which lead to touch first and what to say.' },
            { icon: Lightning, h: 'Built for founder-led teams', p: 'No RevOps team, no 6-month implementation. ARIA ships value on day one.' },
          ].map((b, i) => (
            <div key={i} className="bg-white border border-[#E8E0F5] rounded-2xl p-6" data-testid={`not-crm-${i}`}>
              <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-4" style={{ background: 'var(--gradient-brand)' }}>
                <b.icon size={16} weight="fill" className="text-white" />
              </div>
              <h3 className="text-lg font-extrabold text-[#1A0A2E]">{b.h}</h3>
              <p className="text-sm text-[#5A4A7A] mt-2 leading-relaxed">{b.p}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* Feature sections */}
      <Section id="lead-feed" eyebrow="LEAD FEED" title="Every buying signal, ranked by urgency.">
        <div className="grid md:grid-cols-2 gap-8 items-start">
          <div className="space-y-4 text-base text-[#1A0A2E] leading-relaxed">
            <p>The ARIA <strong>Lead Feed</strong> is a living stream of sales signals — proposal opens, pricing questions, silent threads, hot leads, follow-ups due, and revival opportunities. Each card tells you the lead, the signal, why it matters, and what ARIA recommends as the next action.</p>
            <p>No more scrolling spreadsheets to find who to contact. The feed ranks by urgency, not by alphabet.</p>
          </div>
          <ul className="space-y-2 text-sm text-[#5A4A7A]">
            {['Proposal opened 3× — ready to decide', 'Pricing question — needs founder reply', 'Silent 14+ days — revival journey ready', 'Hot lead ICP 92 — book a call today', 'Follow-up due — ARIA drafted a reply'].map((s, i) => (
              <li key={i} className="flex items-start gap-2 bg-white border border-[#E8E0F5] rounded-xl px-4 py-3">
                <Sparkle size={14} weight="fill" className="text-[#7C35DC] mt-0.5 flex-shrink-0" />{s}
              </li>
            ))}
          </ul>
        </div>
      </Section>

      <Section id="aria-stories" eyebrow="ARIA STORIES" title="The 10 leads that need attention today — one tap away." tone="muted">
        <p className="text-base text-[#1A0A2E] leading-relaxed max-w-3xl mb-6">
          ARIA Stories are Instagram-style rings of the leads that matter today. Tap one and ARIA tells you what happened, why it matters, and drafts a reply in your voice.
        </p>
      </Section>

      <Section id="ask-reply" eyebrow="ASK ARIA TO REPLY" title="Pick a channel, pick a tone. ARIA writes the message.">
        <p className="text-base text-[#1A0A2E] leading-relaxed max-w-3xl">
          WhatsApp, email, LinkedIn, or call script. Founder-led, closer, consultative, premium, or nurture. ARIA writes a reply grounded in the lead's conversation history and your workspace training — so it sounds like you, not a bot.
        </p>
      </Section>

      {/* Core features grid */}
      <Section eyebrow="WHAT ARIA DOES" title="One workspace, seven sales hires in one." tone="muted">
        <FeatureGrid features={FEATURES} />
      </Section>

      {/* Who for */}
      <Section eyebrow="WHO ARIA IS FOR" title="Built for founder-led sales.">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {[
            { label: 'Founders', to: '/aria/use-cases/founders', icon: Users },
            { label: 'Startups', to: '/aria/use-cases/startups', icon: Lightning },
            { label: 'Agencies', to: '/aria/use-cases/agencies', icon: Stack },
            { label: 'Consultants', to: '/aria/use-cases/consultants', icon: Brain },
            { label: 'Sales teams', to: '/aria/use-cases/sales-teams', icon: PhoneCall },
          ].map((u, i) => (
            <a key={i} href={u.to} data-testid={`who-for-${u.label.toLowerCase()}`}
              className="bg-white border border-[#E8E0F5] rounded-2xl p-5 hover:border-[#7C35DC]/50 hover:shadow-lg transition-all text-center">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center mx-auto mb-3" style={{ background: 'var(--gradient-subtle)', border: '1px solid #E0D4F7' }}>
                <u.icon size={16} weight="duotone" className="text-[#7C35DC]" />
              </div>
              <div className="text-sm font-extrabold text-[#1A0A2E]">{u.label}</div>
            </a>
          ))}
        </div>
      </Section>

      {/* FAQ */}
      <Section eyebrow="COMMON QUESTIONS" title="Frequently asked questions about ARIA" tone="muted">
        <FAQAccordion items={FAQ} />
      </Section>

      <BottomCTA />
    </PublicLayout>
  );
};

export default AriaHome;
