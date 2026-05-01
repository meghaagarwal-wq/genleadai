import React from 'react';
import PublicLayout from '../PublicLayout';
import useSEO, { BASE_URL } from '../useSEO';
import {
  SEOHero, Section, FeatureGrid, FAQAccordion, BottomCTA, Breadcrumbs,
  softwareAppSchema, faqSchema, webPageSchema, breadcrumbSchema,
} from '../shared';

const URL = `${BASE_URL}/aria/sales-reports`;

const FAQ = [
  { q: 'What does the ARIA sales reporting dashboard show?', a: 'ARIA sales reports show pipeline intelligence, channel performance, follow-up gaps, lead quality, top objections, lost reasons, revenue at risk, and ARIA-recommended actions.' },
  { q: 'How does ARIA calculate revenue at risk?', a: 'ARIA identifies stuck proposals (opened, not decided), silent high-ICP leads (14+ days no touch), hot leads without recent response, and quantifies the pipeline value at risk so you can act.' },
  { q: 'What is the Follow-up Performance report?', a: 'It tracks reply times, channel response rates, and follow-up gaps — so you see where leads go cold and which channels convert fastest.' },
  { q: 'What is the Channel Performance report?', a: 'It shows which sources (WhatsApp, email, LinkedIn, website, paid, webinar) give you the highest reply rate, qualification rate, and close rate.' },
  { q: 'What does the Lead Quality report track?', a: 'Lead Quality ranks every lead against your ICP score, shows source quality distribution, and highlights your 90+ ICP "golden" leads.' },
  { q: 'What is the Objection Report?', a: 'ARIA tags every objection detected across conversations — pricing, timing, trust, competitor — and aggregates them so you can refine positioning and enablement.' },
  { q: 'What are ARIA Recommended Actions?', a: 'ARIA turns every report insight into a one-tap action — "Send founder voice note to Priya", "Start revival for 7 silent leads", "Add case study to nurture journey".' },
];

const REPORTS = [
  { title: 'Sales Intelligence Report', body: 'One-page pipeline overview: active leads, hot count, stuck proposals, booked calls, and what ARIA thinks you should ship first.' },
  { title: 'Revenue at Risk', body: 'Quantified pipeline value in stuck proposals, silent ICP-80+ leads, unactioned hot leads. One-tap revival playbooks.' },
  { title: 'Follow-up Performance', body: 'Reply times, response rates, and follow-up gaps by channel. See where leads go cold.' },
  { title: 'Channel Performance', body: 'Source-by-source conversion: reply rate, qualification rate, close rate, cost-per-qualified lead.' },
  { title: 'Lead Quality', body: 'ICP score distribution, source quality, golden-lead (90+ ICP) watchlist.' },
  { title: 'Objection Report', body: 'Aggregated objections across conversations. Refine positioning, not just pitch.' },
  { title: 'Lost Reasons', body: 'Why deals die — pricing, timing, fit, competitor — so you fix the real leak.' },
  { title: 'ARIA Recommended Actions', body: 'Every insight becomes a one-tap action. Always answer-first.' },
];

const SalesReportsSEO = () => {
  useSEO({
    title: 'AI Sales Reporting Dashboard | ARIA by GenLeadAI',
    description: 'ARIA\'s sales reports help founders understand pipeline movement, channel performance, follow-up gaps, lead quality, revenue at risk, and next best actions.',
    canonical: URL,
    jsonLd: [
      softwareAppSchema({ description: 'ARIA AI sales reporting dashboard — pipeline intelligence, revenue at risk, channel performance, and recommended actions.', url: URL }),
      faqSchema(FAQ),
      webPageSchema({ name: 'AI Sales Reporting Dashboard | ARIA by GenLeadAI', description: 'AI sales reporting dashboard.', url: URL }),
      breadcrumbSchema([{ label: 'ARIA', to: '/aria' }, { label: 'Sales Reports' }]),
    ],
  });

  return (
    <PublicLayout>
      <SEOHero
        eyebrow="SALES REPORTS"
        title="AI Sales Reporting Dashboard"
        subtitle="Pipeline intelligence, revenue at risk, channel performance, follow-up gaps, lead quality, objection tracking, and ARIA-recommended actions — in one founder-friendly report hub."
      />
      <Section tone="light">
        <Breadcrumbs items={[{ label: 'ARIA', to: '/aria' }, { label: 'Sales Reports' }]} />
        <div className="grid md:grid-cols-2 gap-10">
          <div className="space-y-4 text-base text-[#1A0A2E] leading-relaxed">
            <h2 className="font-display text-2xl md:text-3xl font-extrabold tracking-tight">Answer-first sales intelligence</h2>
            <p>ARIA sales reports are built for founders, not analysts. Every report ends with a one-tap action — "Revive 7 silent ICP leads", "Send founder voice note to Rohit", "Fix the pricing reply that's losing 18% of warm leads".</p>
            <p>You don't need a BI tool. You need to know what to ship before lunch.</p>
          </div>
          <div className="bg-[#F4F0FF] border border-[#E0D4F7] rounded-2xl p-6">
            <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC] mb-3">WHAT YOU SEE</div>
            <ul className="space-y-2 text-sm text-[#1A0A2E]">
              {['Pipeline intelligence snapshot', 'Revenue at risk (quantified in $)', 'Follow-up performance by channel', 'Channel performance by source', 'Top objections + lost reasons', 'ARIA recommended next actions'].map((l, i) => (
                <li key={i} className="flex items-start gap-2"><span className="text-[#7C35DC] font-bold">•</span>{l}</li>
              ))}
            </ul>
          </div>
        </div>
      </Section>

      <Section eyebrow="THE REPORTS" title="Eight founder-ready reports" tone="muted">
        <FeatureGrid features={REPORTS} />
      </Section>

      <Section eyebrow="COMMON QUESTIONS" title="Sales reports FAQs">
        <FAQAccordion items={FAQ} />
      </Section>

      <BottomCTA title="See ARIA reports on your real pipeline" subtitle="20-minute demo. We'll walk through revenue at risk on a sample workspace and show how it computes live from your leads." />
    </PublicLayout>
  );
};

export default SalesReportsSEO;
