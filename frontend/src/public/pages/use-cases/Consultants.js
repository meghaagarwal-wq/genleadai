import React from 'react';
import UseCaseTemplate from '../../UseCaseTemplate';

const Consultants = () => (
  <UseCaseTemplate
    slug="consultants"
    title="ARIA for Consultants"
    metaTitle="AI Sales Assistant for Consultants | ARIA by GenLeadAI"
    metaDescription="Independent consultants and solo operators use ARIA to capture inbound, qualify, follow up on WhatsApp and email, and book discovery calls — without becoming an admin."
    eyebrow="USE CASE · CONSULTANTS"
    heroSubtitle="You're the product. Your time is the constraint. ARIA is the sales assistant that keeps pipeline moving while you do the work you're actually paid for."
    persona="Independent consultants, fractional executives, coaches, and advisory-led operators who sell their own time and expertise."
    problem="Every inbound is exciting. Every inbound is also a 15-minute qualification conversation you cannot afford. Your calendar is your product — and you're burning half of it on lead triage, follow-ups, and 'circling back' messages."
    howAriaHelps={[
      'Captures inquiries from every channel into one feed',
      'Qualifies against your engagement ICP (budget, role, problem fit)',
      'Drafts fit-call booking replies in your consultative voice',
      'Prepares a briefing before every discovery call',
      'Handles "just checking in" follow-ups on autopilot',
    ]}
    dailyWorkflow={[
      'Open ARIA between client calls — 3-minute scan of the Lead Feed',
      'Approve ARIA's drafted replies for tire-kickers and fit leads alike',
      'Before every discovery call, open the Founder Brief in your inbox',
      'Let ARIA handle "still thinking?" follow-ups on Day 3, 7, 14',
      'Weekly Recap shows which content or referral partner booked your best call',
    ]}
    toolsReduced={['Inbox triage', 'Spreadsheet follow-up trackers', 'Manual Calendly booking links', 'Reminder apps', 'Generic CRM']}
    keyFeatures={[
      { title: 'Solo-operator UX', body: 'No sales team needed. ARIA is your sales ops layer — one workspace, no RevOps.' },
      { title: 'Discovery Brief', body: 'Before every call: lead context, likely objections, suggested opening, pricing anchor.' },
      { title: 'Silent-lead revival', body: 'Day 1/4/9/15/30 revival journey for leads who ghosted after a discovery call.' },
      { title: 'Calendar-aware replies', body: 'ARIA offers two real slots from your Calendly, not "when works for you?".' },
      { title: 'Weekly Recap', body: 'Narrative week: what booked, what cooled, what to focus on Monday.' },
      { title: 'ARIA Brain', body: 'Knowledge map of your practice: offers, ICP, qualifiers, voice, FAQs.' },
    ]}
    faq={[
      { q: 'Can ARIA handle high-touch advisory sales?', a: 'Yes. Consultants use ARIA for triage and qualification, not closing. ARIA handles the first 3–4 touchpoints, briefs you before the discovery call, and steps back when you take over.' },
      { q: 'How does ARIA price / pitch my offers?', a: 'You train ARIA with your offer tiers, anchor price, and positioning. ARIA will surface pricing when asked, position value-first, and escalate pricing objections to you.' },
      { q: 'I charge by retainer — does ARIA know that?', a: 'Yes. ARIA learns your engagement model (retainer, project, advisory) and qualifies accordingly — filtering one-off asks out of your Feed.' },
      { q: 'Can ARIA reschedule no-shows?', a: 'Yes. If a lead no-shows, ARIA sends a warm-reschedule message 30 min after and again on Day 2. No shame, no guilt — just warm follow-up.' },
      { q: 'Does ARIA work in email only?', a: 'Email, WhatsApp, LinkedIn DMs. Many consultants run WhatsApp-first sales and love that ARIA handles it natively.' },
    ]}
  />
);

export default Consultants;
