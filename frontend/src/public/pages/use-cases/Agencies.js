import React from 'react';
import UseCaseTemplate from '../../UseCaseTemplate';

const Agencies = () => (
  <UseCaseTemplate
    slug="agencies"
    title="ARIA for Agencies"
    metaTitle="AI Sales Assistant for Agencies | ARIA by GenLeadAI"
    metaDescription="ARIA helps agencies run a tight inbound + referral sales motion. Qualify leads against retainer-fit ICP, follow up across WhatsApp and email, and book discovery calls — without a full-time BDR."
    eyebrow="USE CASE · AGENCIES"
    heroSubtitle="Agencies sell high-trust, high-consideration retainers. ARIA handles the qualification grind so founders and strategists only show up for fit calls."
    persona="Boutique to mid-size agencies (marketing, growth, consulting, design, dev) running inbound + referral sales, often founder-led or strategist-led."
    problem="Your best leads come from founders and strategists doing Twitter/LinkedIn content and hitting inboxes at scale. But someone still has to reply to every DM, separate tire-kickers from real retainer leads, and schedule the right fit call. That someone is currently the wrong person."
    howAriaHelps={[
      'Qualifies inbound against retainer-fit ICP (industry, budget, scope, urgency)',
      'Replies in your agency voice across WhatsApp, email, LinkedIn DMs',
      'Books fit-calls only when a lead passes qualification',
      'Prepares a Founder/Strategist Brief before every call',
      'Tracks which referral partners and channels send the best leads',
    ]}
    dailyWorkflow={[
      'ARIA captures every DM, email, form submission',
      'Qualifies — flags tire-kickers, escalates retainer-fit only',
      'Drafts the fit-call booking reply in your agency tone',
      'Prepares a pre-call brief with lead context and scope signals',
      'Weekly Recap shows which referral partner or content piece converted best',
    ]}
    toolsReduced={['Generic CRM', 'Inbox triage', 'Manual qualification forms', 'Separate proposal trackers', 'Multiple Calendly links']}
    keyFeatures={[
      { title: 'ICP scoring', body: 'Score every inbound against your retainer-fit ICP and surface only the qualified.' },
      { title: 'Objection handling', body: 'Pre-loaded responses for "I need a one-off project" and scope-creep asks.' },
      { title: 'Founder Briefs', body: 'Pre-call context: industry, past touchpoints, scope signals, likely objections.' },
      { title: 'Referral tracking', body: 'See which partner, content, or platform sent each qualified lead.' },
      { title: 'Proposal graveyard', body: 'Watchlist of stuck proposals — ARIA drafts a deadline-framed founder note to unstick.' },
      { title: 'Human Handoff', body: 'Only ping the founder/strategist when the lead is scope-fit and ready to buy.' },
    ]}
    faq={[
      { q: 'Does ARIA handle scope-creep asks well?', a: 'Yes. Train ARIA with your minimum retainer, preferred scope, and disqualifiers. ARIA politely redirects one-off project requests, and escalates retainer-fit conversations only.' },
      { q: 'Can ARIA manage multiple agency brands?', a: 'Each ARIA workspace is brand-scoped. If you run multiple agency brands, each gets its own workspace with its own training, voice, and Calendly.' },
      { q: 'How does ARIA handle referral intros?', a: 'Tag referral source on capture. ARIA replies with a warm "intro received via [partner]" opener and tracks conversion by source in the Channel Performance report.' },
      { q: 'Do you integrate with proposal tools?', a: 'ARIA tracks proposal status (sent/opened/viewed) and surfaces stuck ones in the Lead Feed. We have read integrations for common proposal tools — contact us for specifics.' },
      { q: 'Can ARIA generate discovery questions?', a: 'Yes. Train ARIA with your standard discovery framework and ARIA will surface custom discovery questions in the Founder Brief before each call.' },
    ]}
  />
);

export default Agencies;
