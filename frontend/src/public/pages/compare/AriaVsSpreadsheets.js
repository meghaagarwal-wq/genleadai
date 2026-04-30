import React from 'react';
import CompareTemplate from '../../CompareTemplate';

const AriaVsSpreadsheets = () => (
  <CompareTemplate
    slug="aria-vs-spreadsheets"
    title="ARIA vs Spreadsheets"
    metaTitle="ARIA vs Spreadsheets | AI Sales Assistant vs Excel / Google Sheets"
    metaDescription="Compare ARIA — an AI sales assistant — with spreadsheet-based lead tracking. Spreadsheets record leads. ARIA works them — with AI-drafted replies, reminders, and next best actions."
    eyebrow="COMPARE · ARIA vs SPREADSHEETS"
    heroSubtitle="Spreadsheets are honest tools — most founders start with them. Here's when they break, and what to move to when they do."
    coreLine="Spreadsheets store rows. ARIA tells founders what to do next with those rows."
    otherLabel="Spreadsheet"
    rows={[
      { label: 'Stores lead info in rows', aria: true, other: true },
      { label: 'Free / low cost', aria: 'Free tier', other: true },
      { label: 'Captures leads automatically from website/WhatsApp/email', aria: true, other: false },
      { label: 'Reads conversations and detects signals', aria: true, other: false },
      { label: 'Reminds you when to follow up', aria: true, other: 'Manual formula hacks' },
      { label: 'Drafts replies in your voice', aria: true, other: false },
      { label: 'Books demos on your Calendly', aria: true, other: false },
      { label: 'Shows revenue at risk live', aria: true, other: false },
      { label: 'Morning Brief / daily priorities', aria: true, other: false },
      { label: 'Team access with roles', aria: true, other: 'Basic sharing' },
      { label: 'Fully customisable columns', aria: 'Some', other: true },
      { label: 'Works offline', aria: false, other: true },
    ]}
    whenToUseAria={[
      'You're past 30–50 leads per month — the spreadsheet is slowing you down',
      'You need follow-ups to actually happen without setting reminders',
      'You want replies drafted in your voice across channels',
      'You need demos booked, not just rows updated',
      'You want to track revenue at risk live, not at month-end',
    ]}
    whenToUseOther={[
      'You're pre-first-lead and building the shape of your funnel',
      'You have 1–10 leads total and want zero setup',
      'You need very custom column logic (tracking metrics no product supports)',
      'You need offline access consistently',
      'You're doing a one-off campaign, not an ongoing motion',
    ]}
    whyFoundersNeedAction={[
      'Spreadsheets are the first tool every founder reaches for — and honestly, that's fine. The pain starts at around 30–50 leads, when "Follow up next Tue" becomes a ritual you skip three weeks in a row.',
      'A spreadsheet cannot read your WhatsApp. It cannot see that Priya opened the proposal three times last week. It cannot draft a founder voice note. It just holds rows.',
      'ARIA was built for the moment you look at your sheet and realise it's a list of leads you're losing. The jump from spreadsheet to ARIA is small — you keep the same simplicity, but now the tool tells you what to do next.',
    ]}
    faq={[
      { q: 'Can I import my spreadsheet into ARIA?', a: 'Yes. CSV import is one-click. Map your columns to ARIA fields (name, company, source, notes, ICP), and your existing leads land in the Lead Feed.' },
      { q: 'Will I lose my spreadsheet history?', a: 'No. Keep the spreadsheet as archive. ARIA takes over forward-motion; the spreadsheet stays as your historical log.' },
      { q: 'Do I need to stop using spreadsheets entirely?', a: 'No. Many founders keep a simple deal log or forecast sheet alongside ARIA. ARIA is the working layer; spreadsheets can stay as reporting extras.' },
      { q: 'How much time does ARIA save vs a spreadsheet?', a: 'Most founders tell us they save 30–90 minutes a day on lead triage, reminders, reply drafting, and follow-up admin.' },
      { q: 'What if I only have 10 leads a month?', a: 'Honestly? Stay on spreadsheets. Come to ARIA when you hit ~30/month or when your reply time starts slipping past an hour.' },
    ]}
  />
);

export default AriaVsSpreadsheets;
