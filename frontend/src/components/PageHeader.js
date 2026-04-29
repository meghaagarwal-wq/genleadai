import React from 'react';

/**
 * Premium page header for ARIA — magazine-style display heading,
 * supporting serif accent for elegance, and a subtle gradient underline.
 */
const PageHeader = ({ title, subtitle, eyebrow, actions, children, accent }) => {
  return (
    <div className="flex items-end justify-between flex-wrap gap-4 pb-3 aria-fade-up">
      <div className="min-w-0">
        {eyebrow && (
          <div className="inline-flex items-center gap-2 mb-3" data-testid="page-header-eyebrow">
            <span className="block w-6 h-px bg-gradient-to-r from-[#C044E0] to-transparent" />
            <span className="text-[10px] font-bold uppercase tracking-[0.3em] text-[#7C35DC] numeric">{eyebrow}</span>
          </div>
        )}
        <h1 className="font-display text-[2.4rem] md:text-[2.75rem] lg:text-[3.25rem] leading-[1.05] text-[#1A0A2E]">
          {title}
        </h1>
        {accent && (
          <div className="text-base md:text-lg text-[#7C35DC] mt-1 font-display-italic">
            {accent}
          </div>
        )}
        {subtitle && (
          <p className="text-sm md:text-base text-[#5A4A7A] mt-3 max-w-2xl leading-relaxed">{subtitle}</p>
        )}
        {children}
      </div>
      {actions && <div className="flex items-center gap-2 flex-wrap">{actions}</div>}
    </div>
  );
};

export default PageHeader;
