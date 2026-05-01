import React from 'react';
import CompareTemplate from '../../CompareTemplate';

const AriaVsCrm = () => (
  <CompareTemplate
    slug="aria-vs-crm"
    title="ARIA vs CRM"
    metaTitle="ARIA vs CRM | AI Sales Assistant vs Traditional CRM"
    metaDescription="Compare ARIA — an AI sales assistant for founders — with traditional CRMs. CRMs store pipeline data. ARIA tells founders what to do next with that pipeline."
    eyebrow="COMPARE · ARIA vs CRM"
    heroSubtitle="Both tools have a place in modern sales. Here's a clear, respectful look at what each is great at — and when founder-led teams outgrow CRMs on day one."
    coreLine="CRMs store pipeline data. ARIA tells founders what to do next with that pipeline."
    otherLabel="Traditional CRM"
    rows={[
      { label: 'Stores leads and contacts', aria: true, other: true },
      { label: 'Logs activity and stage changes', aria: true, other: true },
      { label: 'Reads every conversation automatically', aria: true, other: false },
      { label: 'Detects buying signals in real time', aria: true, other: false },
      { label: 'Drafts replies in your voice', aria: true, other: false },
      { label: 'Books demos on your Calendly', aria: true, other: 'Via integrations' },
      { label: 'Runs multi-channel follow-ups', aria: true, other: 'Needs add-ons' },
      { label: 'Morning Brief / action-first daily focus', aria: true, other: false },
      { label: 'Revenue at risk surfaced live', aria: true, other: 'Needs BI / manual reports' },
      { label: 'Deep multi-stage forecasting', aria: 'Basic', other: true },
      { label: 'Enterprise sales ops customisation', aria: 'Lightweight', other: true },
      { label: 'Set up without a RevOps team', aria: true, other: false },
      { label: 'Day-one value for founder-led sales', aria: true, other: 'After months of setup' },
    ]}
    whenToUseAria={[
      'You\'re founder-led or 2–10 people in sales',
      'You want action, not pipeline storage',
      'You sell with personality — WhatsApp, voice notes, founder intros',
      'You need replies drafted, demos booked, follow-ups run — not just tracked',
      'You can\'t spend 3 months implementing sales ops',
    ]}
    whenToUseOther={[
      'You have a 20+ person sales org with RevOps',
      'You need deep multi-stage forecasting and complex territory logic',
      'You\'re enterprise with heavy finance/compliance reporting',
      'You already have SDRs/BDRs handling first-reply and qualification',
      'You\'ve budgeted for 3–6 month CRM implementation',
    ]}
    whyFoundersNeedAction={[
      'A CRM is a filing cabinet. It\'s great if you\'re already running sales at scale and need pipeline-of-record for 50 reps. For a founder-led team, it becomes the thing that takes 30 minutes a day to update — and still tells you nothing about what to do next.',
      'An action-first sales workspace (like ARIA) flips the model. Instead of "here\'s the list, go figure out who to call", it says "Priya at GrowthNest is hot — here\'s the reply, ready to send". The cognitive overhead goes from decision fatigue to one-tap execution.',
      'Many startups run ARIA alongside a CRM — ARIA is the daily working layer, the CRM is the long-term storage layer. You don\'t have to rip and replace. You just stop opening the CRM 15× a day.',
    ]}
    faq={[
      { q: 'Can I use ARIA and a CRM together?', a: 'Yes. Many teams use ARIA as their daily working layer and sync core data to HubSpot, Salesforce, or Pipedrive for long-term reporting and forecasting.' },
      { q: 'Do I need to migrate off my CRM to try ARIA?', a: 'No. ARIA works independently. Connect your channels (WhatsApp, email, LinkedIn), run the Train ARIA wizard, and start working leads. Sync to your CRM whenever you\'re ready.' },
      { q: 'Is ARIA cheaper than a CRM?', a: 'For small teams, yes — often significantly. You also save on CRM add-ons (sequencing tools, reporting, RevOps time).' },
      { q: 'What happens to my pipeline data in ARIA?', a: 'It\'s yours. Export anytime as CSV. No lock-in.' },
      { q: 'Does ARIA have an API?', a: 'Yes. ARIA exposes an API for lead sync, activity sync, and webhook events. Documentation available on request.' },
    ]}
  />
);

export default AriaVsCrm;
