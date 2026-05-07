import React from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { Sparkle, ArrowRight, CaretDown } from '@phosphor-icons/react';

const NAV_LINKS = [
  { label: 'Product', to: '/aria' },
  { label: 'Demo dashboard', to: '/aria/demo-dashboard' },
  { label: 'Lead Feed', to: '/aria/lead-feed' },
  { label: 'Sales reports', to: '/aria/sales-reports' },
];

const USE_CASES = [
  { label: 'Founders', to: '/aria/use-cases/founders' },
  { label: 'Startups', to: '/aria/use-cases/startups' },
  { label: 'Agencies', to: '/aria/use-cases/agencies' },
  { label: 'Consultants', to: '/aria/use-cases/consultants' },
  { label: 'Sales teams', to: '/aria/use-cases/sales-teams' },
];

const COMPARE = [
  { label: 'ARIA vs CRM', to: '/aria/compare/aria-vs-crm' },
  { label: 'ARIA vs spreadsheets', to: '/aria/compare/aria-vs-spreadsheets' },
  { label: 'AI sales assistant vs CRM', to: '/aria/compare/ai-sales-assistant-vs-crm' },
];

const DEMO_URL = 'https://calendly.com/meghaagarwaljain2015/30min';

const PublicNav = () => {
  const [open, setOpen] = React.useState(null);
  return (
    <header className="sticky top-0 z-50 bg-[#0E0820]/90 backdrop-blur-xl border-b border-white/10" data-testid="public-nav">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
        <Link to="/aria" className="flex items-center gap-2" data-testid="public-nav-logo">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'var(--gradient-brand)' }}>
            <Sparkle size={16} weight="fill" className="text-white" />
          </div>
          <div className="flex items-baseline gap-1.5">
            <span className="text-base font-extrabold text-white tracking-tight" style={{ fontFamily: 'Space Grotesk, Inter, sans-serif' }}>ARIA</span>
            <span data-testid="beta-badge-public" className="px-1.5 py-[1px] rounded-[4px] text-[8px] font-bold uppercase tracking-[0.18em] text-[#FDE68A] border border-[#F59E0B]/40 relative -top-0.5" style={{ background: 'rgba(245,158,11,0.12)' }}>Beta</span>
            <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#C9B6FF]">by GenLeadAI</span>
          </div>
        </Link>

        <nav className="hidden lg:flex items-center gap-1">
          {NAV_LINKS.map(l => (
            <NavLink key={l.to} to={l.to} end data-testid={`public-nav-${l.label.toLowerCase().replace(/\s+/g, '-')}`}
              className={({ isActive }) => `px-3 py-2 text-sm font-semibold rounded-lg transition-colors ${isActive ? 'text-white bg-white/10' : 'text-[#C9B6FF] hover:text-white hover:bg-white/5'}`}>
              {l.label}
            </NavLink>
          ))}
          <DropdownNav label="Use cases" items={USE_CASES} open={open === 'uc'} onToggle={() => setOpen(open === 'uc' ? null : 'uc')} testId="public-nav-use-cases" />
          <DropdownNav label="Compare" items={COMPARE} open={open === 'cmp'} onToggle={() => setOpen(open === 'cmp' ? null : 'cmp')} testId="public-nav-compare" />
        </nav>

        <div className="flex items-center gap-2">
          <Link to="/login" className="hidden sm:inline-flex text-sm font-semibold text-[#C9B6FF] hover:text-white px-3 py-2" data-testid="public-nav-login">
            Sign in
          </Link>
          <a href={DEMO_URL} target="_blank" rel="noopener noreferrer" data-testid="public-nav-demo-cta"
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full text-sm font-bold text-white"
            style={{ background: 'var(--gradient-brand)', boxShadow: '0 8px 32px rgba(192,68,224,0.35)' }}>
            Book demo <ArrowRight size={14} weight="bold" />
          </a>
        </div>
      </div>
    </header>
  );
};

const DropdownNav = ({ label, items, open, onToggle, testId }) => {
  const location = useLocation();
  const active = items.some(i => i.to === location.pathname);
  return (
    <div className="relative">
      <button onClick={onToggle} data-testid={testId}
        className={`flex items-center gap-1 px-3 py-2 text-sm font-semibold rounded-lg transition-colors ${active ? 'text-white bg-white/10' : 'text-[#C9B6FF] hover:text-white hover:bg-white/5'}`}>
        {label} <CaretDown size={12} weight="bold" className={`transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="absolute left-0 mt-1 w-56 rounded-xl bg-[#1A0F38] border border-white/10 p-1.5 shadow-2xl" onMouseLeave={onToggle}>
          {items.map(i => (
            <Link key={i.to} to={i.to} onClick={onToggle} data-testid={`${testId}-${i.label.toLowerCase().replace(/\s+/g, '-')}`}
              className="block px-3 py-2 text-sm font-semibold text-[#C9B6FF] hover:text-white hover:bg-white/5 rounded-lg">
              {i.label}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
};

const PublicFooter = () => (
  <footer className="bg-[#0A0518] border-t border-white/10 mt-24" data-testid="public-footer">
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-12">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-8">
        <div className="col-span-2">
          <Link to="/aria" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'var(--gradient-brand)' }}>
              <Sparkle size={16} weight="fill" className="text-white" />
            </div>
            <span className="text-base font-extrabold text-white">ARIA</span>
          </Link>
          <p className="text-sm text-[#C9B6FF]/70 mt-4 max-w-sm leading-relaxed">
            ARIA is an AI sales assistant for founders and startups. Manage leads, follow-ups,
            replies, demo bookings, sales reports, and revenue signals from one AI-powered sales workspace.
          </p>
        </div>
        <FooterCol title="Product" items={NAV_LINKS} />
        <FooterCol title="Use cases" items={USE_CASES} />
        <FooterCol title="Compare" items={COMPARE} />
      </div>
      <div className="mt-10 pt-6 border-t border-white/10 flex items-center justify-between text-xs text-[#C9B6FF]/60 flex-wrap gap-3">
        <span>© {new Date().getFullYear()} GenLeadAI. ARIA — your AI sales assistant.</span>
        <div className="flex items-center gap-4">
          <a href="https://genleadai.com" target="_blank" rel="noopener noreferrer" className="hover:text-white">genleadai.com</a>
          <Link to="/login" className="hover:text-white">Sign in</Link>
        </div>
      </div>
    </div>
  </footer>
);

const FooterCol = ({ title, items }) => (
  <div>
    <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-white mb-3">{title}</div>
    <ul className="space-y-2">
      {items.map(i => (
        <li key={i.to}>
          <Link to={i.to} className="text-sm text-[#C9B6FF]/80 hover:text-white">{i.label}</Link>
        </li>
      ))}
    </ul>
  </div>
);

const PublicLayout = ({ children }) => (
  <div className="min-h-screen flex flex-col bg-[#FAFAFA]" data-testid="public-layout">
    <PublicNav />
    <main className="flex-1">{children}</main>
    <PublicFooter />
  </div>
);

export default PublicLayout;
export { DEMO_URL };
