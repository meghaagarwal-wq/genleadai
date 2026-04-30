import React from 'react';
import UseCaseTemplate from '../../UseCaseTemplate';

const SalesTeams = () => (
  <UseCaseTemplate
    slug="sales-teams"
    title="ARIA for Small Sales Teams"
    metaTitle="AI Sales Assistant for Sales Teams | ARIA by GenLeadAI"
    metaDescription="Small sales teams use ARIA as an AI BDR/SDR layer. Automate first replies, qualify inbound, follow up across channels, route hot leads, and give every AE a pre-call brief."
    eyebrow="USE CASE · SALES TEAMS"
    heroSubtitle="ARIA is the AI BDR / SDR layer your 2–10 person sales team needs. Qualify, follow up, route, and brief — so AEs only talk to ready-to-buy leads."
    persona="Small B2B sales teams (2–10 people), founder-led or led by a first sales hire, running inbound + light outbound motions."
    problem="Every AE has 200 leads in some sheet or CRM. 40 of them are actually worth a call this week. The rest are stale, silent, or tire-kickers. Your AEs spend 60% of their day on admin, not selling. Hiring an SDR takes 3 months. You need that SDR today."
    howAriaHelps={[
      'Handles first-reply within minutes of every inbound',
      'Qualifies against team-wide ICP and routes to the right AE',
      'Runs follow-up cadences across WhatsApp, email, LinkedIn',
      'Prepares a Founder Brief before every AE call',
      'Escalates hot leads via Human Handoff — not every reply',
      'Weekly performance recap per AE + team-wide report',
    ]}
    dailyWorkflow={[
      'Lead arrives → ARIA sends first reply in under 5 min',
      'Qualifies → routes to AE based on territory, size, or round-robin',
      'AE receives a Founder Brief 30 min before each call',
      'Follow-ups auto-shipped across channels — AE approves or skips',
      'Manager reviews Weekly Recap for team velocity + coaching moments',
    ]}
    toolsReduced={['Hiring an SDR (3-month lead time)', 'Cadence tool sprawl', 'Manual qualification forms', 'Separate reporting layer', 'Generic CRM data entry']}
    keyFeatures={[
      { title: 'Smart routing', body: 'Route leads to AEs by territory, ICP fit, round-robin, or custom rules.' },
      { title: 'AE dashboards', body: 'Every AE gets their own Morning Brief, Lead Feed, Pipeline Mood.' },
      { title: 'Team reports', body: 'Manager view: team velocity, per-AE close rates, channel performance, lost reasons.' },
      { title: 'Human Handoff', body: 'Hot leads, pricing asks, competitor mentions → escalated with context.' },
      { title: 'Playbooks library', body: 'Team-wide playbooks: inbound qualification, outbound sequence, revival, webinar follow-up.' },
      { title: 'Sales Assets', body: 'Shared library of approved messages, case studies, proposals, founder voice notes.' },
    ]}
    faq={[
      { q: 'Is ARIA a replacement for our SDR team?', a: 'For small teams (2–10 people), ARIA replaces most SDR work — first-reply, qualification, follow-up, briefing. For larger sales orgs, ARIA augments SDRs by handling the repetitive 80% of their workflow.' },
      { q: 'Does ARIA integrate with HubSpot / Salesforce?', a: 'ARIA can sync lead data with HubSpot / Salesforce for pipeline-of-record — contact us for the current integration list. Many teams use ARIA as the daily workspace and sync back to CRM nightly.' },
      { q: 'How does ARIA handle lead routing rules?', a: 'Rules-based routing by territory, company size, source, ICP tier, or round-robin. You configure them in Settings; ARIA enforces on every inbound.' },
      { q: 'Can managers review AE conversations?', a: 'Yes. Managers see every thread, every ARIA-drafted reply, every Human Handoff — with coaching notes for conversations that escalated or stalled.' },
      { q: 'How does pricing scale with team size?', a: 'Per-workspace pricing with tiers that unlock more seats, channels, and AI credits. See the Pricing page or book a demo for a team-sized quote.' },
    ]}
  />
);

export default SalesTeams;
