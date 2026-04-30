import React from 'react';
import UseCaseTemplate from '../../UseCaseTemplate';

const Startups = () => (
  <UseCaseTemplate
    slug="startups"
    title="ARIA for Startups"
    metaTitle="AI Sales Assistant for Startups | ARIA by GenLeadAI"
    metaDescription="ARIA helps early-stage startups move from founder-led sales to predictable pipeline. Capture, qualify, follow up, book demos, and track revenue at risk — before hiring a sales team."
    eyebrow="USE CASE · STARTUPS"
    heroSubtitle="Pre-sales-team startups need pipeline, not another CRM. ARIA plugs the leak between founder attention and inbound demand — so your first 100 demos don't slip through the cracks."
    persona="Pre-seed to Series A startups with 1–2 people covering sales, often the founder + a generalist. You need velocity and consistency before hiring a full sales function."
    problem="You raised to grow, but you're still manually chasing leads. You tried a CRM and it became another thing to update. You tried Zapier automations that send 'Hey {first_name}' messages — and they bombed. You need a system that actually thinks."
    howAriaHelps={[
      'Replaces the "founder chasing leads on WhatsApp at midnight" pattern',
      'Builds a pipeline system that keeps working when you're in investor meetings',
      'Qualifies against your ICP so you don't burn time on the wrong logos',
      'Turns every demo into a Founder Brief in your inbox 30 min before the call',
      'Surfaces channel performance so you double down on what works',
    ]}
    dailyWorkflow={[
      'Morning: ARIA Brief + Lead Feed — 5 minutes to set the day's priorities',
      'Midday: ARIA handles follow-ups across channels while you're pitching or building',
      'Before demos: Founder Brief drops in Slack / email 30 min before every call',
      'Afternoon: Human Handoff alerts — only for leads that truly need you',
      'Friday: Weekly Recap — what moved, what leaked, what to double down on',
    ]}
    toolsReduced={['Generic CRM', 'Zapier follow-up hacks', 'Spreadsheet pipelines', 'Manual demo prep docs', 'Separate reporting tools']}
    keyFeatures={[
      { title: 'Train ARIA wizard', body: 'Under 15 min to load ICP, voice, offer, qualifying logic, objection handling.' },
      { title: 'Sales Playbooks', body: 'Preset motions: inbound qualification, outbound, webinar follow-up, revival.' },
      { title: 'AI Sales Journeys', body: '17-step default journey + 5 templates. Customise touchpoints and channels.' },
      { title: 'Founder Briefs', body: 'Pre-call brief with lead context, likely objections, opening lines — Claude-powered.' },
      { title: 'Weekly Recap', body: 'Narrative summary + KPIs + next-week focus. Ready to share with your board.' },
      { title: 'Revival Engine', body: '7 revival segments + Day 1/4/9/15/30 cadences for silent and past leads.' },
    ]}
    faq={[
      { q: 'We're too early for sales ops. Is ARIA too much?', a: 'ARIA is built for exactly this stage. No RevOps team needed, no multi-month implementation. You connect WhatsApp and Calendly, run the 15-min Train ARIA wizard, and ship.' },
      { q: 'We already have HubSpot / Salesforce. Why ARIA?', a: 'Keep your CRM if you have one — ARIA can plug in. CRMs store pipeline; ARIA works it. Many startups keep ARIA as the daily workspace and the CRM as long-term data warehouse.' },
      { q: 'Does ARIA support multiple teammates?', a: 'Yes. Invite your co-founder or first sales hire. ARIA assigns leads by rules you define and keeps each teammate's Morning Brief specific to their assigned leads.' },
      { q: 'What about multilingual leads?', a: 'ARIA drafts replies in the language of the incoming message. Supported: English, Hindi, Spanish, Portuguese, Arabic — with more rolling out.' },
      { q: 'How does ARIA help with fundraising-era sales?', a: 'ARIA becomes your pipeline continuity layer. When you're in investor meetings, ARIA keeps leads warm, drafts replies, and books demos — so you don't lose the 4 weeks of commercial momentum.' },
    ]}
  />
);

export default Startups;
