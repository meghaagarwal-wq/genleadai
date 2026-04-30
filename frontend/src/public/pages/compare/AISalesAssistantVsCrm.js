import React from 'react';
import CompareTemplate from '../../CompareTemplate';

const AISalesAssistantVsCrm = () => (
  <CompareTemplate
    slug="ai-sales-assistant-vs-crm"
    title="AI Sales Assistant vs CRM"
    metaTitle="AI Sales Assistant vs CRM | What's the difference?"
    metaDescription="An AI sales assistant works your leads. A CRM stores them. Learn when to use each — and how founder-led teams use AI sales assistants like ARIA to replace or augment their CRM."
    eyebrow="COMPARE · AI Sales Assistant vs CRM"
    heroSubtitle="They sound similar but solve different problems. Here's a respectful, practical breakdown — so you pick the right tool for where you are today."
    coreLine="A CRM is a pipeline ledger. An AI sales assistant is the operator that works that pipeline."
    otherLabel="Traditional CRM"
    rows={[
      { label: 'Definition', aria: 'Action layer — reads, replies, books, briefs', other: 'Storage layer — records contacts and stages' },
      { label: 'Uses AI to detect buying signals', aria: true, other: 'Add-on only' },
      { label: 'Writes messages in founder voice', aria: true, other: false },
      { label: 'Runs multi-channel follow-ups natively', aria: true, other: 'Needs sequencing tools' },
      { label: 'Prepares pre-call briefs', aria: true, other: false },
      { label: 'Tracks revenue at risk in real time', aria: true, other: 'Via BI layer' },
      { label: 'Built for founder-led teams (1–10 people)', aria: true, other: false },
      { label: 'Built for enterprise RevOps (50+ reps)', aria: false, other: true },
      { label: 'Time to first value', aria: 'Same day', other: '3–6 months typical' },
      { label: 'Needs dedicated admin', aria: false, other: true },
    ]}
    whenToUseAria={[
      'You're founder-led or small-team and need action today',
      'You want AI that thinks, not AI that summarises',
      'You sell across WhatsApp, email, LinkedIn and need replies drafted',
      'You want Morning Briefs, Founder Briefs, Weekly Recaps',
      'You want revenue at risk surfaced live, not in monthly reports',
    ]}
    whenToUseOther={[
      'You have 20+ reps and need territory + quota logic',
      'You need complex multi-stage forecasting',
      'You have a RevOps team to configure and maintain',
      'You need finance-grade pipeline reporting',
      'You have legacy integrations that require a CRM of record',
    ]}
    whyFoundersNeedAction={[
      'AI sales assistants are a new category — different from CRMs, different from chatbots. The simplest way to understand them: an AI sales assistant is an operator, not a database. It reads, thinks, writes, and ships — in your voice, grounded in your data.',
      'CRMs will always have a place for large, process-heavy sales orgs. They're the source of truth, the reporting spine, the forecasting system. But for the first 10 people in sales, opening a CRM is a tax on momentum.',
      'The pattern we see: founders deploy ARIA first, hit $1–5M ARR on ARIA alone, then layer a CRM underneath when the team hits 10+ reps. The CRM becomes the storage; ARIA stays the daily workspace.',
    ]}
    faq={[
      { q: 'Is an AI sales assistant the same as a chatbot?', a: 'No. Chatbots answer customer questions on your website. AI sales assistants like ARIA handle the full sales motion — capture, qualify, follow up, book, brief, report — across every channel, with context grounded in your workspace training.' },
      { q: 'Can I keep my CRM and use an AI sales assistant?', a: 'Yes. Most teams do. ARIA runs as the daily workspace; your CRM stays as the pipeline ledger. ARIA can sync data back to HubSpot, Salesforce, or Pipedrive.' },
      { q: 'What's the ROI of switching from CRM-only to AI sales assistant?', a: 'Time savings are the fastest — most teams save 30–90 minutes per salesperson per day. Revenue uplift comes from faster first-replies (60 minutes vs 12 hours), better follow-up consistency, and zero "I'll circle back next week" drops.' },
      { q: 'Will AI replies sound generic?', a: 'Only if you train them generically. ARIA is trained on your voice, offer, objection handling, and every past conversation — so replies are specific, personal, and sound like you.' },
      { q: 'Is AI sales assistant a real category?', a: 'Yes. The category is emerging alongside agentic AI — Gartner, Forrester, and others have named it in 2025–2026 research. ARIA is one of the earliest purpose-built entrants for founder-led teams.' },
    ]}
  />
);

export default AISalesAssistantVsCrm;
