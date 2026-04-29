import React from 'react';

/**
 * Premium page header for ARIA — large title, subhead, optional right-side actions.
 * Use on every page for consistent rhythm with the GenLeadAI brand.
 */
const PageHeader = ({ title, subtitle, eyebrow, actions, children }) => {
  return (
    <div className="flex items-end justify-between flex-wrap gap-4 pb-2">
      <div className="min-w-0">
        {eyebrow && (
          <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC] mb-2" style={{ fontFamily: 'Plus Jakarta Sans' }}>{eyebrow}</div>
        )}
        <h1 className="text-3xl md:text-4xl font-extrabold text-[#1A0A2E] leading-tight" style={{ fontFamily: 'Plus Jakarta Sans', letterSpacing: '-0.01em' }}>
          {title}
        </h1>
        {subtitle && (
          <p className="text-sm md:text-base text-[#5A4A7A] mt-2 max-w-2xl">{subtitle}</p>
        )}
        {children}
      </div>
      {actions && <div className="flex items-center gap-2 flex-wrap">{actions}</div>}
    </div>
  );
};

export default PageHeader;
