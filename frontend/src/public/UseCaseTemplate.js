import React from 'react';
import PublicLayout from './PublicLayout';
import useSEO, { BASE_URL } from './useSEO';
import {
  SEOHero, Section, FAQAccordion, BottomCTA, Breadcrumbs, FeatureGrid,
  softwareAppSchema, faqSchema, webPageSchema, breadcrumbSchema,
} from './shared';

const UseCaseTemplate = ({
  slug,
  title,
  metaTitle,
  metaDescription,
  eyebrow,
  heroSubtitle,
  persona,
  problem,
  howAriaHelps,
  dailyWorkflow,
  toolsReduced,
  keyFeatures,
  faq,
}) => {
  const url = `${BASE_URL}/aria/use-cases/${slug}`;
  useSEO({
    title: metaTitle,
    description: metaDescription,
    canonical: url,
    jsonLd: [
      softwareAppSchema({ description: metaDescription, url }),
      faqSchema(faq),
      webPageSchema({ name: metaTitle, description: metaDescription, url }),
      breadcrumbSchema([
        { label: 'ARIA', to: '/aria' },
        { label: 'Use Cases' },
        { label: title },
      ]),
    ],
  });

  return (
    <PublicLayout>
      <SEOHero eyebrow={eyebrow} title={title} subtitle={heroSubtitle} />

      <Section tone="light">
        <Breadcrumbs items={[
          { label: 'ARIA', to: '/aria' },
          { label: 'Use cases' },
          { label: title },
        ]} />

        <div className="grid md:grid-cols-2 gap-10" data-testid="persona-problem">
          <div className="space-y-3 text-base text-[#1A0A2E] leading-relaxed">
            <h2 className="font-display text-2xl md:text-3xl font-extrabold tracking-tight">Who this is for</h2>
            <p>{persona}</p>
            <h2 className="font-display text-2xl md:text-3xl font-extrabold tracking-tight mt-6">The problem</h2>
            <p>{problem}</p>
          </div>
          <div className="bg-[#F4F0FF] border border-[#E0D4F7] rounded-2xl p-6">
            <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC] mb-3">HOW ARIA HELPS</div>
            <ul className="space-y-3 text-sm text-[#1A0A2E]">
              {howAriaHelps.map((l, i) => (
                <li key={i} className="flex items-start gap-2"><span className="text-[#7C35DC] font-bold">•</span>{l}</li>
              ))}
            </ul>
          </div>
        </div>
      </Section>

      <Section eyebrow="DAILY WORKFLOW" title={`A day with ARIA`} tone="muted">
        <ol className="max-w-3xl mx-auto space-y-4" data-testid="daily-workflow">
          {dailyWorkflow.map((step, i) => (
            <li key={i} className="flex items-start gap-4 bg-white border border-[#E8E0F5] rounded-2xl px-5 py-4" data-testid={`workflow-${i}`}>
              <span className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 text-sm font-extrabold text-white" style={{ background: 'var(--gradient-brand)' }}>{i + 1}</span>
              <div className="text-base text-[#1A0A2E]">{step}</div>
            </li>
          ))}
        </ol>
      </Section>

      <Section eyebrow="TOOLS ARIA REPLACES" title="What ARIA reduces dependence on">
        <div className="flex flex-wrap gap-2 max-w-3xl" data-testid="tools-reduced">
          {toolsReduced.map((t, i) => (
            <span key={i} className="px-4 py-2 rounded-full bg-[#F4F0FF] border border-[#E0D4F7] text-sm font-semibold text-[#5A4A7A]" data-testid={`tool-${i}`}>{t}</span>
          ))}
        </div>
      </Section>

      <Section eyebrow="KEY FEATURES" title="Dashboard features you'll live in" tone="muted">
        <FeatureGrid features={keyFeatures} />
      </Section>

      <Section eyebrow="COMMON QUESTIONS" title="FAQs">
        <FAQAccordion items={faq} />
      </Section>

      <BottomCTA />
    </PublicLayout>
  );
};

export default UseCaseTemplate;
