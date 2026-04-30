import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Minus, ArrowRight, Sparkle, CheckCircle, XCircle } from '@phosphor-icons/react';
import { DEMO_URL } from './PublicLayout';

export const SEOHero = ({ eyebrow, title, subtitle, children }) => (
  <section className="relative overflow-hidden" data-testid="seo-hero"
    style={{ background: 'linear-gradient(135deg, #0E0820 0%, #1A0F38 35%, #2B1860 75%, #7C35DC 100%)' }}>
    <div className="absolute inset-0 pointer-events-none opacity-60" style={{ background: 'var(--gradient-aria-glow)' }} />
    <div className="relative max-w-7xl mx-auto px-4 sm:px-6 py-20 md:py-28">
      {eyebrow && (
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/10 border border-white/20 mb-6">
          <Sparkle size={12} weight="fill" className="text-[#C044E0]" />
          <span className="text-[10px] font-bold uppercase tracking-[0.25em] text-white">{eyebrow}</span>
        </div>
      )}
      <h1 className="font-display text-4xl md:text-5xl lg:text-6xl font-extrabold text-white leading-[1.05] tracking-tight max-w-4xl">
        {title}
      </h1>
      {subtitle && (
        <p className="text-base md:text-lg text-[#C9B6FF] mt-6 max-w-3xl leading-relaxed">{subtitle}</p>
      )}
      {children && <div className="mt-8">{children}</div>}
    </div>
  </section>
);

export const CTAButtons = ({ primaryLabel = 'Book a demo', secondary, testId = 'seo-cta' }) => (
  <div className="flex flex-wrap gap-3" data-testid={testId}>
    <a href={DEMO_URL} target="_blank" rel="noopener noreferrer" data-testid={`${testId}-primary`}
      className="inline-flex items-center gap-2 px-6 py-3 rounded-full text-white font-bold text-sm md:text-base"
      style={{ background: 'linear-gradient(135deg,#C044E0 0%,#7C35DC 50%,#5B28D4 100%)', boxShadow: '0 8px 32px rgba(192,68,224,0.4)' }}>
      {primaryLabel} <ArrowRight size={16} weight="bold" />
    </a>
    {secondary && (
      <Link to={secondary.to} data-testid={`${testId}-secondary`}
        className="inline-flex items-center gap-2 px-6 py-3 rounded-full text-white font-bold text-sm md:text-base bg-white/10 border border-white/20 backdrop-blur-xl hover:bg-white/15">
        {secondary.label} <ArrowRight size={16} weight="bold" />
      </Link>
    )}
  </div>
);

export const Section = ({ eyebrow, title, subtitle, children, id, tone = 'light' }) => {
  const bg = tone === 'dark' ? 'bg-[#0E0820] text-white' : tone === 'muted' ? 'bg-[#F4F0FF]' : 'bg-white';
  return (
    <section id={id} className={`${bg} py-16 md:py-20`} data-testid={`section-${id || 'default'}`}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        {eyebrow && (
          <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC] mb-3">{eyebrow}</div>
        )}
        {title && (
          <h2 className="font-display text-3xl md:text-4xl lg:text-5xl font-extrabold text-[#1A0A2E] tracking-tight leading-[1.1] max-w-4xl">
            {tone === 'dark' ? <span className="text-white">{title}</span> : title}
          </h2>
        )}
        {subtitle && (
          <p className={`text-base md:text-lg mt-4 max-w-3xl leading-relaxed ${tone === 'dark' ? 'text-[#C9B6FF]' : 'text-[#5A4A7A]'}`}>{subtitle}</p>
        )}
        {children && <div className="mt-10">{children}</div>}
      </div>
    </section>
  );
};

export const FeatureGrid = ({ features }) => (
  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="feature-grid">
    {features.map((f, i) => (
      <article key={i} className="bg-white border border-[#E8E0F5] rounded-2xl p-6" style={{ boxShadow: 'var(--shadow-card)' }} data-testid={`feature-${i}`}>
        <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-4" style={{ background: 'var(--gradient-brand)' }}>
          <Sparkle size={16} weight="fill" className="text-white" />
        </div>
        <h3 className="text-lg font-extrabold text-[#1A0A2E] tracking-tight">{f.title}</h3>
        <p className="text-sm text-[#5A4A7A] mt-2 leading-relaxed">{f.body}</p>
      </article>
    ))}
  </div>
);

export const FAQAccordion = ({ items }) => {
  const [open, setOpen] = useState(0);
  return (
    <div className="space-y-3" data-testid="faq-accordion">
      {items.map((f, i) => (
        <div key={i} className="bg-white border border-[#E8E0F5] rounded-2xl overflow-hidden" data-testid={`faq-item-${i}`}>
          <button onClick={() => setOpen(open === i ? -1 : i)}
            data-testid={`faq-toggle-${i}`}
            className="w-full flex items-center justify-between gap-4 px-5 py-4 text-left hover:bg-[#FAF7FF]">
            <h3 className="text-base font-extrabold text-[#1A0A2E]">{f.q}</h3>
            {open === i ? <Minus size={16} weight="bold" className="text-[#7C35DC]" /> : <Plus size={16} weight="bold" className="text-[#7C35DC]" />}
          </button>
          {open === i && (
            <div className="px-5 pb-5 text-sm text-[#5A4A7A] leading-relaxed border-t border-[#F0ECF9] pt-4" data-testid={`faq-answer-${i}`}>
              {f.a}
            </div>
          )}
        </div>
      ))}
    </div>
  );
};

export const ComparisonTable = ({ rows, columns }) => (
  <div className="bg-white border border-[#E8E0F5] rounded-2xl overflow-hidden" data-testid="comparison-table" style={{ boxShadow: 'var(--shadow-card)' }}>
    <table className="w-full">
      <thead className="bg-[#F4F0FF]">
        <tr>
          {columns.map((c, i) => (
            <th key={i} className={`px-5 py-4 text-left text-[10px] font-bold uppercase tracking-[0.2em] ${i === 1 ? 'text-[#7C35DC]' : 'text-[#5A4A7A]'}`}>{c}</th>
          ))}
        </tr>
      </thead>
      <tbody className="divide-y divide-[#F0ECF9]">
        {rows.map((r, i) => (
          <tr key={i} data-testid={`compare-row-${i}`}>
            <td className="px-5 py-4 text-sm font-semibold text-[#1A0A2E]">{r.label}</td>
            <td className="px-5 py-4 text-sm text-[#1A0A2E]">
              <div className="flex items-center gap-2">
                {r.aria === true ? <CheckCircle size={14} weight="fill" className="text-[#16A34A]" /> : r.aria === false ? <XCircle size={14} weight="fill" className="text-[#DC2626]" /> : null}
                <span>{typeof r.aria === 'string' ? r.aria : r.aria === true ? 'Yes' : 'No'}</span>
              </div>
            </td>
            <td className="px-5 py-4 text-sm text-[#5A4A7A]">
              <div className="flex items-center gap-2">
                {r.other === true ? <CheckCircle size={14} weight="fill" className="text-[#16A34A]" /> : r.other === false ? <XCircle size={14} weight="fill" className="text-[#DC2626]" /> : null}
                <span>{typeof r.other === 'string' ? r.other : r.other === true ? 'Yes' : 'No'}</span>
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

export const BottomCTA = ({ title = 'Deploy your first AI sales hire', subtitle = 'Book a 20-min demo and see ARIA working your leads in under 60 seconds.', testId = 'bottom-cta' }) => (
  <section className="py-20 px-4" data-testid={testId}>
    <div className="max-w-4xl mx-auto rounded-3xl p-10 md:p-14 text-center relative overflow-hidden"
      style={{ background: 'linear-gradient(135deg, #0E0820 0%, #1A0F38 45%, #2B1860 100%)' }}>
      <div className="absolute inset-0 opacity-50 pointer-events-none" style={{ background: 'var(--gradient-aria-glow)' }} />
      <div className="relative">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/10 border border-white/20 mb-4">
          <Sparkle size={12} weight="fill" className="text-[#C044E0]" />
          <span className="text-[10px] font-bold uppercase tracking-[0.25em] text-white">See ARIA in action</span>
        </div>
        <h2 className="font-display text-3xl md:text-4xl font-extrabold text-white tracking-tight leading-[1.1]">{title}</h2>
        <p className="text-sm md:text-base text-[#C9B6FF] mt-4 max-w-xl mx-auto">{subtitle}</p>
        <div className="mt-8 flex justify-center">
          <CTAButtons testId={`${testId}-buttons`} secondary={{ label: 'Try demo dashboard', to: '/aria/demo-dashboard' }} />
        </div>
      </div>
    </div>
  </section>
);

export const Breadcrumbs = ({ items }) => (
  <nav className="text-xs text-[#9B8AB0] mb-6" aria-label="Breadcrumb" data-testid="breadcrumbs">
    <ol className="flex items-center gap-2 flex-wrap">
      {items.map((item, i) => (
        <li key={i} className="flex items-center gap-2">
          {i > 0 && <span className="text-[#9B8AB0]/50">/</span>}
          {item.to ? (
            <Link to={item.to} className="hover:text-[#7C35DC] font-semibold">{item.label}</Link>
          ) : (
            <span className="text-[#5A4A7A] font-semibold">{item.label}</span>
          )}
        </li>
      ))}
    </ol>
  </nav>
);

// Helpers for JSON-LD schema
export const softwareAppSchema = ({ name = 'ARIA by GenLeadAI', description, url }) => ({
  '@context': 'https://schema.org',
  '@type': 'SoftwareApplication',
  name,
  applicationCategory: 'BusinessApplication',
  applicationSubCategory: 'Sales',
  operatingSystem: 'Web',
  url,
  description,
  creator: { '@type': 'Organization', name: 'GenLeadAI', url: 'https://genleadai.com' },
  offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD', availability: 'https://schema.org/InStock' },
  aggregateRating: { '@type': 'AggregateRating', ratingValue: '4.9', reviewCount: '42' },
});

export const faqSchema = (items) => ({
  '@context': 'https://schema.org',
  '@type': 'FAQPage',
  mainEntity: items.map(f => ({
    '@type': 'Question',
    name: f.q,
    acceptedAnswer: { '@type': 'Answer', text: typeof f.a === 'string' ? f.a : (f.a?.props?.children || '').toString() },
  })),
});

export const breadcrumbSchema = (items) => ({
  '@context': 'https://schema.org',
  '@type': 'BreadcrumbList',
  itemListElement: items.map((it, i) => ({
    '@type': 'ListItem',
    position: i + 1,
    name: it.label,
    item: it.to ? `https://app.genleadai.com${it.to}` : undefined,
  })),
});

export const webPageSchema = ({ name, description, url, datePublished = '2026-02-01' }) => ({
  '@context': 'https://schema.org',
  '@type': 'WebPage',
  name,
  description,
  url,
  datePublished,
  isPartOf: { '@type': 'WebSite', name: 'GenLeadAI · ARIA', url: 'https://app.genleadai.com' },
});
