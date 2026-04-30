import React from 'react';
import PublicLayout from './PublicLayout';
import useSEO, { BASE_URL } from './useSEO';
import {
  SEOHero, Section, FAQAccordion, BottomCTA, Breadcrumbs, ComparisonTable,
  softwareAppSchema, faqSchema, webPageSchema, breadcrumbSchema,
} from './shared';

const CompareTemplate = ({
  slug,
  title,
  metaTitle,
  metaDescription,
  eyebrow,
  heroSubtitle,
  coreLine,
  otherLabel,
  rows,
  whenToUseAria,
  whenToUseOther,
  whyFoundersNeedAction,
  faq,
}) => {
  const url = `${BASE_URL}/aria/compare/${slug}`;
  useSEO({
    title: metaTitle,
    description: metaDescription,
    canonical: url,
    jsonLd: [
      softwareAppSchema({ description: metaDescription, url }),
      faqSchema(faq),
      webPageSchema({ name: metaTitle, description: metaDescription, url }),
      breadcrumbSchema([{ label: 'ARIA', to: '/aria' }, { label: 'Compare' }, { label: title }]),
    ],
  });

  return (
    <PublicLayout>
      <SEOHero eyebrow={eyebrow} title={title} subtitle={heroSubtitle} />

      <Section tone="light">
        <Breadcrumbs items={[{ label: 'ARIA', to: '/aria' }, { label: 'Compare' }, { label: title }]} />

        <div className="bg-[#F4F0FF] border border-[#E0D4F7] rounded-2xl p-6 max-w-4xl">
          <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC] mb-3">CORE DIFFERENCE</div>
          <blockquote className="font-display text-2xl md:text-3xl font-extrabold text-[#1A0A2E] leading-[1.15]" data-testid="core-line">
            "{coreLine}"
          </blockquote>
        </div>
      </Section>

      <Section eyebrow="FEATURE COMPARISON" title="Feature-by-feature comparison" tone="muted">
        <ComparisonTable columns={['Capability', 'ARIA', otherLabel]} rows={rows} />
      </Section>

      <Section eyebrow="WHEN TO USE WHICH" title="When to use ARIA — and when to use a CRM / spreadsheet">
        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-[#F4F0FF] border border-[#E0D4F7] rounded-2xl p-6" data-testid="when-aria">
            <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC] mb-3">CHOOSE ARIA WHEN</div>
            <ul className="space-y-2 text-sm text-[#1A0A2E]">
              {whenToUseAria.map((l, i) => (
                <li key={i} className="flex items-start gap-2"><span className="text-[#7C35DC] font-bold">•</span>{l}</li>
              ))}
            </ul>
          </div>
          <div className="bg-white border border-[#E8E0F5] rounded-2xl p-6" data-testid="when-other">
            <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#5A4A7A] mb-3">CHOOSE {otherLabel.toUpperCase()} WHEN</div>
            <ul className="space-y-2 text-sm text-[#1A0A2E]">
              {whenToUseOther.map((l, i) => (
                <li key={i} className="flex items-start gap-2"><span className="text-[#5A4A7A] font-bold">•</span>{l}</li>
              ))}
            </ul>
          </div>
        </div>
      </Section>

      <Section eyebrow="ACTION-FIRST SALES" title="Why founders need action-first sales workspaces" tone="muted">
        <div className="space-y-4 text-base text-[#1A0A2E] leading-relaxed max-w-3xl">
          {whyFoundersNeedAction.map((p, i) => <p key={i}>{p}</p>)}
        </div>
      </Section>

      <Section eyebrow="COMMON QUESTIONS" title="FAQs">
        <FAQAccordion items={faq} />
      </Section>

      <BottomCTA title="Ready to stop storing pipeline and start working it?" subtitle="20-min demo. Bring your 5 hardest leads — we'll show you what ARIA would do next." />
    </PublicLayout>
  );
};

export default CompareTemplate;
