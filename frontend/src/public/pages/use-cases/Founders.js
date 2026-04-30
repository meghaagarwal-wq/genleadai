import React from 'react';
import UseCaseTemplate from '../../UseCaseTemplate';

const Founders = () => (
  <UseCaseTemplate
    slug="founders"
    title="ARIA for Founders"
    metaTitle="AI Sales Assistant for Founders | ARIA by GenLeadAI"
    metaDescription="ARIA is the AI sales assistant for founders running sales themselves. Capture leads, follow up on WhatsApp and email, book demos, and get a daily brief — without hiring a sales ops team."
    eyebrow="USE CASE · FOUNDERS"
    heroSubtitle="You're the founder, the closer, and the pipeline manager. ARIA handles capture, qualification, follow-up, and replies — so you only show up for the moments that matter."
    persona="Solo founders and founder-led teams selling their own product or service. You're the best salesperson in your company — but you can't reply to every WhatsApp and still build."
    problem="Leads come in on LinkedIn, WhatsApp, email, website forms. You miss the first 60 minutes. Warm leads go cold. Follow-ups slip. You tell yourself 'I'll do it Monday' — and you don't. The pipeline bleeds while you build."
    howAriaHelps={[
      'Captures every lead across website, WhatsApp, email, LinkedIn into one feed',
      'Qualifies against your ICP and escalates only the hot + human-touch ones',
      'Drafts replies in your founder voice — approve or edit in 15 seconds',
      'Books demos on your Calendly with smart slot offers',
      'Delivers a Morning Brief so you start the day with priorities, not a scramble',
      'Surfaces revenue at risk — stuck proposals, silent ICP-80+, unactioned hot',
    ]}
    dailyWorkflow={[
      'Morning: open ARIA → read the Morning Brief (3 sentences, what's hot, what's stuck, what to ship first)',
      'Scroll the Lead Feed → tap the 3 highest-urgency cards → approve or edit the ARIA-drafted replies',
      'Demos: ARIA books calls on your Calendly. A Founder Brief waits in your inbox 30 min before each call',
      'Afternoon: ARIA handles follow-ups across channels. You only get pinged when Human Handoff is needed',
      'Evening: End-of-Day Wrap email summarises the day — what moved, what's at risk, tomorrow's priorities',
    ]}
    toolsReduced={['Generic CRM', 'Spreadsheet lead tracker', 'Separate follow-up tools', 'Inbox chaos', 'Messaging apps for reminders', 'Manual Calendly round-robin']}
    keyFeatures={[
      { title: 'Morning Brief', body: '3-sentence Claude-powered brief that tells you what to ship first today.' },
      { title: 'Lead Feed', body: 'Every buying signal, ranked by urgency. No more scrolling spreadsheets.' },
      { title: 'Ask ARIA to Reply', body: 'WhatsApp, email, LinkedIn, call script. Founder-led tone. Ready in seconds.' },
      { title: 'Founder Briefs', body: 'Before every call, ARIA prepares a brief: lead context, likely objections, opening lines.' },
      { title: 'Revenue at Risk', body: 'Live $ figure of stuck proposals and silent leads you're losing right now.' },
      { title: 'Human Handoff', body: 'ARIA only pings you when a lead truly needs your voice — not for every reply.' },
    ]}
    faq={[
      { q: 'I'm the only salesperson. Will ARIA really help?', a: 'Yes. ARIA is designed for founder-led selling. It takes the repetitive 80% (first replies, follow-ups, qualification, scheduling) off your plate so you only show up for founder-only moments — pricing calls, custom scopes, closing conversations.' },
      { q: 'Will ARIA sound like me, or a generic bot?', a: 'ARIA is trained on your positioning, offer, voice, and objection handling. Every reply is grounded in your tone and lead context. You approve before anything goes out — nothing ships without your OK unless you allow auto-send.' },
      { q: 'How long to set up ARIA?', a: 'Under 15 minutes for the Train ARIA wizard (what you sell, ICP, voice, qualifying questions). WhatsApp and Calendly connect in one click each. You can start working real leads on day one.' },
      { q: 'Can I still take over a conversation manually?', a: 'Always. Tap "Take over manually" on any lead and ARIA steps back. When you want ARIA back in the loop, tap "Let ARIA reply" — she picks up right where you left off.' },
      { q: 'Does ARIA replace a CRM for me?', a: 'For most founder-led teams, yes. ARIA captures, qualifies, follows up, books, and reports. If you later hire a 3+ person sales team, pair ARIA with a CRM for stage-heavy pipeline reporting.' },
    ]}
  />
);

export default Founders;
