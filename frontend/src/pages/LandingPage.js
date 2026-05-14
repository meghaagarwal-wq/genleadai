/**
 * LandingPage — public marketing surface at `/` for unauthenticated visitors.
 *
 * Same brand language as the Signup screen but with a stronger storytelling
 * arc: hero → product chips → Problem→ARIA→Result card → "How Aria works"
 * 4-step strip → plans → contact strip → footer. Every CTA drives toward
 * /signup (or opens the Plans/Contact modals reused from Signup).
 *
 * This page is shown ONLY when the visitor is logged out — App.js routing
 * sends authenticated users straight to the Dashboard.
 */
import React, { useState, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Sparkle, ArrowRight, ChatCircle, Lightning, MapTrifold, ShieldCheck,
  CheckCircle, Robot, Plug, GraduationCap, CalendarCheck, X,
} from '@phosphor-icons/react';

const API = process.env.REACT_APP_BACKEND_URL;

const CHIPS = [
  { icon: MapTrifold,   label: '32-Touchpoint Journey' },
  { icon: Lightning,    label: 'AI-Personalized Follow-ups' },
  { icon: ChatCircle,   label: 'Multi-Channel Lead Capture' },
  { icon: ShieldCheck,  label: 'Founder Handoff' },
  { icon: CheckCircle,  label: 'Call Booking Assistant' },
];

const PSR_ROWS = [
  { problem: 'Leads come from too many places', aria: 'One AI sales workspace',  result: 'No scattered follow-ups' },
  { problem: 'Founders miss follow-ups',         aria: 'Automated nurturing',     result: 'Warm leads stay active'  },
  { problem: 'Prospects need many nudges',       aria: '32-touchpoint journey',   result: 'More booked calls'       },
];

const HOW_IT_WORKS = [
  { icon: Plug,          step: '01', title: 'Connect your channels', body: 'WhatsApp, website forms, ads, outreach platforms — every inbound lead lands in one place.' },
  { icon: GraduationCap, step: '02', title: 'Train Aria on your business', body: 'Tell Aria what you sell, who you sell to, your pricing, and your voice. 15 minutes.' },
  { icon: Robot,         step: '03', title: 'Aria runs the 32-touchpoint journey', body: 'Personalized replies, follow-ups, brochures, pitch decks, and qualifiers — across every channel.' },
  { icon: CalendarCheck, step: '04', title: 'You close the booked calls', body: 'Qualified leads land on your calendar with a pre-call brief from Aria. You focus on closing.' },
];

const PLANS = [
  { key: 'starter', name: 'Starter', tag: 'For one lead source',
    points: ['Basic AI follow-up', 'Founder handoff'],
    cta: 'Start Starter', recommended: false },
  { key: 'growth',  name: 'Growth',  tag: 'For active ads + outreach',
    points: ['32-touchpoint journey', 'Asset sharing + call booking'],
    cta: 'Request Growth', recommended: true },
  { key: 'custom',  name: 'Custom',  tag: 'For complex funnels',
    points: ['Custom integrations', 'Saleshandy / Lemlist / CRM support'],
    cta: 'Contact Us', recommended: false },
];

const LandingPage = () => {
  const navigate = useNavigate();
  const heroRef = useRef(null);
  const [showPlans, setShowPlans]   = useState(false);
  const [showContact, setShowContact] = useState(false);

  const goSignup = () => navigate('/signup');
  const scrollToTop = () => heroRef.current?.scrollIntoView({ behavior: 'smooth' });

  return (
    <div className="min-h-screen relative" data-testid="landing-page"
      style={{
        background:
          'radial-gradient(1200px 600px at 80% -10%, rgba(124,53,220,0.10), transparent 60%), radial-gradient(900px 500px at -10% 110%, rgba(255,200,120,0.10), transparent 60%), linear-gradient(135deg, #FCFAFF 0%, #FAFAFA 60%, #FFF8EA 100%)',
      }}
    >
      {/* ─── Navbar ───────────────────────────────────────────────────── */}
      <nav className="sticky top-0 z-30 backdrop-blur-md bg-white/70 border-b border-[#E8E0F5]" data-testid="landing-navbar">
        <div className="max-w-[1200px] mx-auto px-5 lg:px-7 h-14 flex items-center justify-between">
          <button onClick={scrollToTop} className="flex items-center gap-2.5" data-testid="landing-nav-brand">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #C044E0 0%, #7C35DC 50%, #5B28D4 100%)' }}>
              <Sparkle size={16} weight="fill" className="text-white" />
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-sm font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>
                ARIA<span className="text-[#9B8AB0] font-bold"> by GenLeadAI</span>
              </span>
              <span className="px-1.5 py-[1px] rounded text-[8px] font-extrabold uppercase tracking-[0.16em] text-[#B45309] border border-[#F59E0B]/50" style={{ background: 'rgba(245,158,11,0.12)' }}>Beta</span>
            </div>
          </button>
          <div className="flex items-center gap-1.5 md:gap-2.5">
            <button onClick={() => setShowPlans(true)} data-testid="landing-nav-plans" className="hidden sm:inline-flex items-center text-xs font-bold text-[#5A4A7A] hover:text-[#1A0A2E] px-2.5 py-2 rounded-lg transition-colors" style={{ fontFamily: 'Plus Jakarta Sans' }}>Plans</button>
            <button onClick={() => setShowContact(true)} data-testid="landing-nav-contact" className="hidden sm:inline-flex items-center text-xs font-bold text-[#5A4A7A] hover:text-[#1A0A2E] px-2.5 py-2 rounded-lg transition-colors" style={{ fontFamily: 'Plus Jakarta Sans' }}>Contact Us</button>
            <Link to="/login" data-testid="landing-nav-login" className="text-xs font-bold text-[#5A4A7A] hover:text-[#1A0A2E] px-2.5 py-2 rounded-lg transition-colors" style={{ fontFamily: 'Plus Jakarta Sans' }}>Login</Link>
            <button onClick={goSignup} data-testid="landing-nav-get-started" className="inline-flex items-center gap-1 px-3.5 py-2 btn-gradient rounded-lg text-xs font-extrabold text-white shadow-sm" style={{ fontFamily: 'Plus Jakarta Sans' }}>
              Get started <ArrowRight size={11} weight="bold" />
            </button>
          </div>
        </div>
      </nav>

      <div ref={heroRef} className="max-w-[1200px] mx-auto px-5 lg:px-7 py-10 lg:py-16 aria-fade-up">
        {/* ─── Hero ─────────────────────────────────────────────────────── */}
        <div className="text-center max-w-[760px] mx-auto" data-testid="landing-hero">
          <div className="inline-flex items-center gap-1.5 text-[10px] font-extrabold uppercase tracking-[0.25em] text-[#7C35DC] mb-3">
            <Sparkle size={11} weight="fill" /> Your AI Sales PA
          </div>
          <h1 className="text-4xl md:text-[52px] lg:text-[58px] leading-[1.05] font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans', letterSpacing: '-0.02em' }} data-testid="landing-headline">
            Turn scattered leads into <span className="gradient-text">booked calls</span>.
          </h1>
          <p className="text-[15px] md:text-base text-[#5A4A7A] mt-4 max-w-[600px] mx-auto leading-relaxed" data-testid="landing-subheadline">
            ARIA captures, qualifies, nurtures, follows up, and books calls with your prospects — before warm leads go cold. Built for founders who need a sales system before they can hire a sales team.
          </p>
          <div className="flex flex-wrap justify-center gap-2 mt-7">
            <button onClick={goSignup} data-testid="landing-hero-primary"
              className="inline-flex items-center gap-1.5 px-5 py-3 btn-gradient text-white rounded-lg text-sm font-extrabold shadow-md hover:-translate-y-0.5 transition-transform" style={{ fontFamily: 'Plus Jakarta Sans' }}>
              Create my workspace <ArrowRight size={13} weight="bold" />
            </button>
            <button onClick={() => setShowContact(true)} data-testid="landing-hero-contact"
              className="inline-flex items-center gap-1.5 px-5 py-3 bg-white border border-[#E0D4F7] text-[#1A0A2E] rounded-lg text-sm font-extrabold hover:border-[#7C35DC]/40 transition-colors" style={{ fontFamily: 'Plus Jakarta Sans' }}>
              Talk to our team
            </button>
          </div>
          <p className="text-[11px] text-[#9B8AB0] mt-3" data-testid="landing-no-cc">60-second setup · No credit card · Free during beta</p>
        </div>

        {/* ─── Feature chips ────────────────────────────────────────────── */}
        <div className="flex flex-wrap justify-center gap-1.5 mt-8 aria-fade-up aria-fade-up-1" data-testid="landing-feature-chips">
          {CHIPS.map(({ icon: Icon, label }) => (
            <span key={label} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white border border-[#E0D4F7] text-[11.5px] font-bold text-[#1A0A2E] shadow-[0_2px_8px_rgba(124,53,220,0.05)] hover:-translate-y-0.5 transition-transform" style={{ fontFamily: 'Plus Jakarta Sans' }}>
              <Icon size={11} weight="fill" className="text-[#7C35DC]" />
              {label}
            </span>
          ))}
        </div>

        {/* ─── Problem → ARIA → Result card ─────────────────────────────── */}
        <div className="mt-10 rounded-2xl bg-white/85 backdrop-blur border border-[#E8E0F5] p-4 md:p-5 shadow-[0_12px_36px_rgba(26,10,46,0.05)] max-w-[920px] mx-auto aria-fade-up aria-fade-up-2" data-testid="landing-psr-card">
          <div className="hidden md:grid grid-cols-[1.1fr_1fr_1fr] gap-3 text-[9px] font-extrabold uppercase tracking-[0.2em] text-[#9B8AB0] px-2 pb-2 border-b border-[#F0ECF9]">
            <span>Problem</span>
            <span>ARIA handles</span>
            <span>Result</span>
          </div>
          {PSR_ROWS.map((r, i) => (
            <div key={i} className="grid grid-cols-1 md:grid-cols-[1.1fr_1fr_1fr] gap-2 md:gap-3 py-3 border-b border-[#F0ECF9] last:border-0 items-center" data-testid={`landing-psr-row-${i}`}>
              <div className="text-sm text-[#1A0A2E] leading-snug">{r.problem}</div>
              <div className="text-sm text-[#1A0A2E] leading-snug inline-flex items-center gap-1.5">
                <ArrowRight size={12} weight="bold" className="text-[#7C35DC] md:hidden" />
                <span className="font-bold text-[#7C35DC] md:text-[#1A0A2E]">{r.aria}</span>
              </div>
              <div className="text-sm leading-snug inline-flex items-center gap-1.5">
                <CheckCircle size={12} weight="fill" className="text-[#16A34A] md:hidden" />
                <span className="font-bold text-[#16A34A]">{r.result}</span>
              </div>
            </div>
          ))}
        </div>

        <p className="text-sm text-center text-[#5A4A7A] mt-5 italic aria-fade-up aria-fade-up-2">
          Not a CRM. Not just a chatbot. <span className="font-extrabold text-[#1A0A2E] not-italic">ARIA is your first AI sales assistant.</span>
        </p>

        {/* ─── How it works ─────────────────────────────────────────────── */}
        <div className="mt-14 aria-fade-up aria-fade-up-3" data-testid="landing-how">
          <div className="text-center mb-6">
            <div className="text-[10px] font-extrabold uppercase tracking-[0.25em] text-[#7C35DC] mb-1">How Aria works</div>
            <h2 className="text-2xl md:text-3xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans', letterSpacing: '-0.015em' }}>From scattered leads to booked calls — in 4 steps</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            {HOW_IT_WORKS.map((s) => {
              const Icon = s.icon;
              return (
                <div key={s.step} className="aria-card-lift rounded-2xl bg-white border border-[#E8E0F5] p-4" style={{ boxShadow: 'var(--shadow-card)' }} data-testid={`landing-how-step-${s.step}`}>
                  <div className="flex items-center justify-between mb-3">
                    <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #C044E0 0%, #5B28D4 100%)' }}>
                      <Icon size={16} weight="fill" className="text-white" />
                    </div>
                    <span className="text-[10px] font-extrabold tracking-[0.18em] text-[#9B8AB0]">{s.step}</span>
                  </div>
                  <div className="text-sm font-extrabold text-[#1A0A2E] leading-tight" style={{ fontFamily: 'Plus Jakarta Sans' }}>{s.title}</div>
                  <p className="text-xs text-[#5A4A7A] mt-1 leading-relaxed">{s.body}</p>
                </div>
              );
            })}
          </div>
        </div>

        {/* ─── Plans strip ───────────────────────────────────────────────── */}
        <div className="mt-14" data-testid="landing-plans-strip">
          <div className="flex items-end justify-between flex-wrap gap-2 mb-3">
            <div>
              <div className="text-[10px] font-extrabold uppercase tracking-[0.22em] text-[#7C35DC] mb-0.5">Compact plans</div>
              <h3 className="text-xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Pick the right ARIA for your stage</h3>
            </div>
            <button onClick={() => setShowPlans(true)} data-testid="landing-plans-details-btn" className="text-xs font-bold text-[#7C35DC] hover:text-[#5B28D4] inline-flex items-center gap-1">
              See details <ArrowRight size={11} weight="bold" />
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {PLANS.map(p => (
              <PlanCard key={p.key} plan={p}
                onCta={() => { if (p.key === 'starter') goSignup(); else setShowContact(true); }} />
            ))}
          </div>
        </div>

        {/* ─── Final CTA / Contact strip ─────────────────────────────────── */}
        <div className="mt-12 rounded-2xl border border-[#E0D4F7] p-6 md:p-7 flex items-center justify-between flex-wrap gap-3 bg-gradient-to-r from-white via-[#FAF7FF] to-[#FFF8EA] aria-fade-up aria-fade-up-4" data-testid="landing-final-cta">
          <div className="max-w-[640px]">
            <h3 className="text-xl md:text-2xl font-extrabold text-[#1A0A2E] leading-tight" style={{ fontFamily: 'Plus Jakarta Sans', letterSpacing: '-0.01em' }}>Ready to turn your leads into booked calls?</h3>
            <p className="text-sm text-[#5A4A7A] mt-1">Start free. Or have our team set ARIA up for your business.</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button onClick={goSignup} data-testid="landing-final-primary"
              className="inline-flex items-center gap-1.5 px-5 py-3 btn-gradient text-white rounded-lg text-sm font-extrabold shadow-md hover:-translate-y-0.5 transition-transform" style={{ fontFamily: 'Plus Jakarta Sans' }}>
              Create my workspace <ArrowRight size={13} weight="bold" />
            </button>
            <button onClick={() => setShowContact(true)} data-testid="landing-final-contact"
              className="inline-flex items-center gap-1.5 px-5 py-3 bg-white border border-[#E0D4F7] text-[#1A0A2E] rounded-lg text-sm font-extrabold hover:border-[#7C35DC]/40 transition-colors" style={{ fontFamily: 'Plus Jakarta Sans' }}>
              Contact us
            </button>
          </div>
        </div>

        {/* ─── Footer ────────────────────────────────────────────────────── */}
        <footer className="mt-12 flex items-center justify-between flex-wrap gap-3 pt-6 border-t border-[#E8E0F5]" data-testid="landing-footer">
          <p className="text-[11px] text-[#9B8AB0]">© {new Date().getFullYear()} GenLeadAI · Aria is your first AI sales hire</p>
          <div className="flex items-center gap-4 text-[11px] text-[#5A4A7A]">
            <Link to="/privacy" className="hover:text-[#1A0A2E]">Privacy</Link>
            <Link to="/terms" className="hover:text-[#1A0A2E]">Terms</Link>
            <Link to="/dpa" className="hover:text-[#1A0A2E]">DPA</Link>
            <Link to="/login" className="hover:text-[#1A0A2E]">Login</Link>
          </div>
        </footer>
      </div>

      {showPlans && <PlansModal onClose={() => setShowPlans(false)} onContact={() => { setShowPlans(false); setShowContact(true); }} onStart={() => { setShowPlans(false); goSignup(); }} />}
      {showContact && <ContactModal onClose={() => setShowContact(false)} />}
    </div>
  );
};

// ─── Reusable PlanCard ────────────────────────────────────────────────────
const PlanCard = ({ plan, onCta }) => (
  <div
    data-testid={`landing-plan-${plan.key}`}
    className={`relative bg-white rounded-2xl border p-5 transition-all hover:-translate-y-0.5 ${
      plan.recommended ? 'border-[#7C35DC]/40 shadow-[0_12px_36px_rgba(124,53,220,0.18)]' : 'border-[#E8E0F5] shadow-[0_6px_18px_rgba(26,10,46,0.04)]'
    }`}
  >
    {plan.recommended && (
      <span className="absolute -top-2.5 left-5 px-2 py-0.5 rounded-full text-[9px] font-extrabold uppercase tracking-[0.18em] text-white" style={{ background: 'var(--gradient-brand)' }}>Recommended</span>
    )}
    <div className="text-xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{plan.name}</div>
    <div className="text-[11px] text-[#9B8AB0] font-bold uppercase tracking-wider mt-0.5">{plan.tag}</div>
    <ul className="mt-3 space-y-1.5">
      {plan.points.map(pt => (
        <li key={pt} className="text-xs text-[#1A0A2E] inline-flex items-start gap-1.5">
          <CheckCircle size={11} weight="fill" className="text-[#16A34A] mt-0.5 flex-shrink-0" /> {pt}
        </li>
      ))}
    </ul>
    <button onClick={onCta} data-testid={`landing-plan-${plan.key}-cta`} className={`w-full mt-4 py-2 rounded-lg text-xs font-extrabold transition-all ${
      plan.recommended ? 'btn-gradient text-white' : 'bg-[#F4F0FF] text-[#7C35DC] hover:bg-[#7C35DC] hover:text-white border border-[#7C35DC]/20'
    }`} style={{ fontFamily: 'Plus Jakarta Sans' }}>
      {plan.cta}
    </button>
  </div>
);

const PlansModal = ({ onClose, onContact, onStart }) => (
  <div className="fixed inset-0 z-50 flex items-center justify-center p-4 aria-fade-up" style={{ background: 'rgba(20,8,42,0.55)', backdropFilter: 'blur(8px)' }} data-testid="landing-plans-modal" onClick={onClose}>
    <div className="bg-white rounded-3xl max-w-2xl w-full p-6 md:p-8 shadow-2xl border border-white/40" onClick={(e) => e.stopPropagation()}>
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="text-[10px] font-extrabold uppercase tracking-[0.22em] text-[#7C35DC]">Plans</div>
          <h2 className="text-xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Pick the right ARIA</h2>
        </div>
        <button onClick={onClose} data-testid="landing-plans-modal-close" className="w-8 h-8 rounded-full hover:bg-[#F4F0FF] flex items-center justify-center text-[#9B8AB0] hover:text-[#1A0A2E]"><X size={14} weight="bold" /></button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {PLANS.map(p => (
          <PlanCard key={p.key} plan={p} onCta={() => p.key === 'starter' ? onStart() : onContact()} />
        ))}
      </div>
      <p className="text-[11px] text-[#9B8AB0] mt-4 text-center">Need something tailored? <button onClick={onContact} className="font-extrabold text-[#7C35DC] hover:underline">Talk to us</button>.</p>
    </div>
  </div>
);

const ContactModal = ({ onClose }) => {
  const [form, setForm] = useState({ name: '', email: '', company: '', website: '', message: '' });
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.name.trim() || !form.email.trim() || !form.message.trim()) {
      toast.error('Please fill in name, email, and message.');
      return;
    }
    setBusy(true);
    try {
      await axios.post(`${API}/api/contact/request`, { ...form, page: 'landing' }).catch(() => {});
      toast.success("Thanks — we'll be in touch within 1 business day.");
      onClose();
    } finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 aria-fade-up" style={{ background: 'rgba(20,8,42,0.55)', backdropFilter: 'blur(8px)' }} data-testid="landing-contact-modal" onClick={onClose}>
      <div className="bg-white rounded-3xl max-w-lg w-full p-6 md:p-7 shadow-2xl border border-white/40" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3">
          <div>
            <div className="text-[10px] font-extrabold uppercase tracking-[0.22em] text-[#7C35DC]">Talk to us</div>
            <h2 className="text-xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Request ARIA Setup</h2>
            <p className="text-xs text-[#5A4A7A] mt-1">Tell us about your funnel — our team will reach out to set you up.</p>
          </div>
          <button onClick={onClose} data-testid="landing-contact-modal-close" className="w-8 h-8 rounded-full hover:bg-[#F4F0FF] flex items-center justify-center text-[#9B8AB0] hover:text-[#1A0A2E]"><X size={14} weight="bold" /></button>
        </div>
        <form onSubmit={submit} className="space-y-2.5 mt-3" data-testid="landing-contact-form">
          <Field label="Your name" testid="landing-contact-name" value={form.name} onChange={(v) => setForm({ ...form, name: v })} required />
          <Field label="Email" type="email" testid="landing-contact-email" value={form.email} onChange={(v) => setForm({ ...form, email: v })} required />
          <Field label="Company" testid="landing-contact-company" value={form.company} onChange={(v) => setForm({ ...form, company: v })} />
          <Field label="Website" testid="landing-contact-website" value={form.website} onChange={(v) => setForm({ ...form, website: v })} />
          <div>
            <label className="block text-[10px] font-extrabold uppercase tracking-[0.18em] text-[#9B8AB0] mb-1">Message</label>
            <textarea required value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} rows={3} data-testid="landing-contact-message"
              placeholder="Tell us about your lead sources and what you need help with."
              className="w-full bg-white border border-[#E8E0F5] rounded-lg px-3 py-2 text-sm focus:border-[#7C35DC] focus:ring-2 focus:ring-[#7C35DC]/15 outline-none transition resize-none" />
          </div>
          <button type="submit" disabled={busy} data-testid="landing-contact-submit"
            className="w-full mt-1 py-3 rounded-lg btn-gradient text-white text-xs font-extrabold disabled:opacity-50" style={{ fontFamily: 'Plus Jakarta Sans' }}>
            {busy ? 'Sending…' : 'Request ARIA Setup'}
          </button>
        </form>
      </div>
    </div>
  );
};

const Field = ({ label, type = 'text', testid, value, onChange, required = false }) => (
  <div>
    <label className="block text-[10px] font-extrabold uppercase tracking-[0.18em] text-[#9B8AB0] mb-1">{label}</label>
    <input type={type} value={value} onChange={(e) => onChange(e.target.value)} required={required} data-testid={testid}
      className="w-full bg-white border border-[#E8E0F5] rounded-lg px-3 py-2 text-sm focus:border-[#7C35DC] focus:ring-2 focus:ring-[#7C35DC]/15 outline-none transition" />
  </div>
);

export default LandingPage;
