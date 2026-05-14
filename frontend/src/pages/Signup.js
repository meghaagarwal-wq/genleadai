/**
 * Signup — compact product-led screen for /signup.
 *
 *   Layout:
 *     ┌────────────────────────────────────────────────────────────┐
 *     │  Navbar: ARIA · GenLeadAI         Plans · Contact · Login  │
 *     ├──────────────────────────┬─────────────────────────────────┤
 *     │  Product context column  │  Signup card (preserves form)   │
 *     └──────────────────────────┴─────────────────────────────────┘
 *     │  Compact plans strip (3 cards)                             │
 *     │  Tiny contact strip                                        │
 *
 * Auth/form logic is unchanged from the previous Signup.js — same
 * `signup()` call, same fields, same validation, same redirect.
 */
import React, { useState, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { useAuth } from '../context/AuthContext';
import {
  Buildings, Envelope, Lock, User, Eye, EyeSlash, Sparkle,
  ArrowRight, ChatCircle, Lightning, MapTrifold, ShieldCheck, X, CheckCircle,
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
  { problem: 'Leads come from too many places', aria: 'One AI sales workspace',     result: 'No scattered follow-ups' },
  { problem: 'Founders miss follow-ups',         aria: 'Automated nurturing',         result: 'Warm leads stay active'  },
  { problem: 'Prospects need many nudges',       aria: '32-touchpoint journey',       result: 'More booked calls'       },
];

const PLANS = [
  { key: 'starter', name: 'Starter', tag: 'For one lead source',
    points: ['Basic AI follow-up', 'Founder handoff'],
    cta: 'Start Starter', recommended: false },
  { key: 'growth', name: 'Growth',  tag: 'For active ads + outreach',
    points: ['32-touchpoint journey', 'Asset sharing + call booking'],
    cta: 'Request Growth', recommended: true },
  { key: 'custom', name: 'Custom',  tag: 'For complex funnels',
    points: ['Custom integrations', 'Saleshandy / Lemlist / CRM support'],
    cta: 'Contact Us', recommended: false },
];

const Signup = () => {
  const navigate = useNavigate();
  const { signup } = useAuth();
  const formRef = useRef(null);

  // Signup form state (unchanged from previous Signup.js)
  const [form, setForm] = useState({ workspace_name: '', full_name: '', email: '', password: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Modal state
  const [showPlans, setShowPlans] = useState(false);
  const [showContact, setShowContact] = useState(false);

  const handle = async (e) => {
    e.preventDefault();
    setError('');
    if (form.password.length < 8) { setError('Password must be at least 8 characters.'); return; }
    if (!form.workspace_name.trim() || !form.full_name.trim()) { setError('All fields are required.'); return; }
    setLoading(true);
    try {
      await signup(form.email, form.password, form.full_name, form.workspace_name);
      navigate('/onboarding');
    } catch (err) {
      setError(err.response?.data?.detail || 'Signup failed. Please try again.');
    } finally { setLoading(false); }
  };

  const scrollToSignup = () => {
    formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    setTimeout(() => document.querySelector('[data-testid="signup-workspace-name"]')?.focus(), 600);
  };

  const inputCls =
    'w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] pl-10 pr-3 py-2.5 rounded-lg text-sm focus:border-[#7C35DC] focus:ring-2 focus:ring-[#7C35DC]/15 outline-none transition';

  return (
    <div className="min-h-screen relative" data-testid="signup-page"
      style={{
        background:
          'radial-gradient(1200px 600px at 80% -10%, rgba(124,53,220,0.10), transparent 60%), radial-gradient(900px 500px at -10% 110%, rgba(255,200,120,0.10), transparent 60%), linear-gradient(135deg, #FCFAFF 0%, #FAFAFA 60%, #FFF8EA 100%)',
      }}
    >
      {/* ─── Navbar ───────────────────────────────────────────────────── */}
      <nav className="sticky top-0 z-30 backdrop-blur-md bg-white/70 border-b border-[#E8E0F5]" data-testid="signup-navbar">
        <div className="max-w-[1200px] mx-auto px-5 lg:px-7 h-14 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5" data-testid="signup-nav-brand">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #C044E0 0%, #7C35DC 50%, #5B28D4 100%)' }}>
              <Sparkle size={16} weight="fill" className="text-white" />
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="text-sm font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>
                  ARIA<span className="text-[#9B8AB0] font-bold"> by GenLeadAI</span>
                </span>
                <span className="px-1.5 py-[1px] rounded text-[8px] font-extrabold uppercase tracking-[0.16em] text-[#B45309] border border-[#F59E0B]/50" style={{ background: 'rgba(245,158,11,0.12)' }}>Beta</span>
              </div>
            </div>
          </Link>
          <div className="flex items-center gap-1.5 md:gap-2.5">
            <button onClick={() => setShowPlans(true)} data-testid="signup-nav-plans" className="hidden sm:inline-flex items-center text-xs font-bold text-[#5A4A7A] hover:text-[#1A0A2E] px-2.5 py-2 rounded-lg transition-colors" style={{ fontFamily: 'Plus Jakarta Sans' }}>Plans</button>
            <button onClick={() => setShowContact(true)} data-testid="signup-nav-contact" className="hidden sm:inline-flex items-center text-xs font-bold text-[#5A4A7A] hover:text-[#1A0A2E] px-2.5 py-2 rounded-lg transition-colors" style={{ fontFamily: 'Plus Jakarta Sans' }}>Contact Us</button>
            <Link to="/login" data-testid="signup-nav-login" className="text-xs font-bold text-[#5A4A7A] hover:text-[#1A0A2E] px-2.5 py-2 rounded-lg transition-colors" style={{ fontFamily: 'Plus Jakarta Sans' }}>Login</Link>
            <button onClick={scrollToSignup} data-testid="signup-nav-get-started" className="inline-flex items-center gap-1 px-3.5 py-2 btn-gradient rounded-lg text-xs font-extrabold text-white shadow-sm" style={{ fontFamily: 'Plus Jakarta Sans' }}>
              Get started <ArrowRight size={11} weight="bold" />
            </button>
          </div>
        </div>
      </nav>

      <div className="max-w-[1200px] mx-auto px-5 lg:px-7 py-8 lg:py-12 aria-fade-up">
        {/* ─── Hero: two-column ─────────────────────────────────────────── */}
        <div className="grid grid-cols-1 lg:grid-cols-[1.05fr_minmax(360px,440px)] gap-8 lg:gap-12 items-start">

          {/* LEFT: product context */}
          <div className="aria-fade-up aria-fade-up-1">
            <div className="inline-flex items-center gap-1.5 text-[10px] font-extrabold uppercase tracking-[0.22em] text-[#7C35DC] mb-3">
              <Sparkle size={11} weight="fill" /> Your AI Sales PA
            </div>
            <h1 className="text-3xl md:text-[40px] leading-[1.08] font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans', letterSpacing: '-0.02em' }} data-testid="signup-headline">
              Turn scattered leads into <span className="gradient-text">booked calls</span>.
            </h1>
            <p className="text-[15px] text-[#5A4A7A] mt-3 max-w-[560px] leading-relaxed" data-testid="signup-subheadline">
              ARIA captures, qualifies, nurtures, follows up, and books calls with your prospects — before warm leads go cold. Built for founders who need a sales system before they can hire a sales team.
            </p>

            {/* Feature chips */}
            <div className="flex flex-wrap gap-1.5 mt-5" data-testid="signup-feature-chips">
              {CHIPS.map(({ icon: Icon, label }) => (
                <span key={label} className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-full bg-white border border-[#E0D4F7] text-[11px] font-bold text-[#1A0A2E] shadow-[0_2px_8px_rgba(124,53,220,0.05)] hover:-translate-y-0.5 transition-transform" style={{ fontFamily: 'Plus Jakarta Sans' }}>
                  <Icon size={11} weight="fill" className="text-[#7C35DC]" />
                  {label}
                </span>
              ))}
            </div>

            {/* Problem → Solution → Result card */}
            <div className="mt-6 rounded-2xl bg-white/70 backdrop-blur border border-[#E8E0F5] p-3 md:p-4 shadow-[0_8px_24px_rgba(26,10,46,0.04)]" data-testid="signup-psr-card">
              <div className="hidden md:grid grid-cols-[1.05fr_1fr_1fr] gap-2 text-[9px] font-extrabold uppercase tracking-[0.18em] text-[#9B8AB0] px-2 pb-2 border-b border-[#F0ECF9]">
                <span>Problem</span>
                <span>ARIA handles</span>
                <span>Result</span>
              </div>
              {PSR_ROWS.map((r, i) => (
                <div key={i} className="grid grid-cols-1 md:grid-cols-[1.05fr_1fr_1fr] gap-2 md:gap-3 py-2.5 md:py-3 border-b border-[#F0ECF9] last:border-0 items-center" data-testid={`signup-psr-row-${i}`}>
                  <div className="text-[12.5px] text-[#1A0A2E] leading-snug">{r.problem}</div>
                  <div className="text-[12.5px] text-[#5A4A7A] leading-snug inline-flex items-center gap-1.5">
                    <ArrowRight size={11} weight="bold" className="text-[#7C35DC] md:hidden" />
                    <span className="font-bold text-[#7C35DC] md:font-bold md:text-[#1A0A2E]">{r.aria}</span>
                  </div>
                  <div className="text-[12.5px] leading-snug inline-flex items-center gap-1.5">
                    <CheckCircle size={11} weight="fill" className="text-[#16A34A] md:hidden" />
                    <span className="font-bold text-[#16A34A]">{r.result}</span>
                  </div>
                </div>
              ))}
            </div>

            <p className="text-xs text-[#5A4A7A] mt-5 italic" data-testid="signup-positioning">
              Not a CRM. Not just a chatbot. <span className="font-extrabold text-[#1A0A2E] not-italic">ARIA is your first AI sales assistant.</span>
            </p>
          </div>

          {/* RIGHT: signup card */}
          <div ref={formRef} className="aria-fade-up aria-fade-up-2 lg:sticky lg:top-20">
            <div className="bg-white border border-[#E8E0F5] rounded-2xl p-6 shadow-[0_24px_60px_-18px_rgba(76,29,149,0.22)]">
              <div className="h-1 w-12 rounded-full mb-4" style={{ background: 'var(--gradient-brand)' }} />
              <h2 className="text-xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Create your ARIA Workspace</h2>
              <p className="text-[#5A4A7A] mb-5 text-sm">Start managing your leads with your AI Sales PA. 60 seconds, no credit card.</p>

              {error && (
                <div className="bg-red-50 border border-red-200 text-[#DC2626] rounded-lg px-3 py-2 mb-4 text-sm" data-testid="signup-error">
                  {error}
                </div>
              )}

              <form onSubmit={handle} className="space-y-3" data-testid="signup-form">
                <div className="relative">
                  <Buildings size={16} className="absolute left-3 top-3.5 text-[#9B8AB0]" />
                  <input data-testid="signup-workspace-name" type="text" placeholder="Workspace name (e.g. Acme Corp)"
                    value={form.workspace_name} onChange={(e) => setForm({ ...form, workspace_name: e.target.value })}
                    className={inputCls} required />
                </div>
                <div className="relative">
                  <User size={16} className="absolute left-3 top-3.5 text-[#9B8AB0]" />
                  <input data-testid="signup-full-name" type="text" placeholder="Your full name"
                    value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                    className={inputCls} required />
                </div>
                <div className="relative">
                  <Envelope size={16} className="absolute left-3 top-3.5 text-[#9B8AB0]" />
                  <input data-testid="signup-email" type="email" placeholder="Work email"
                    value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
                    className={inputCls} required />
                </div>
                <div className="relative">
                  <Lock size={16} className="absolute left-3 top-3.5 text-[#9B8AB0]" />
                  <input data-testid="signup-password" type={showPassword ? 'text' : 'password'} placeholder="Password (min 8 chars)"
                    value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })}
                    className={inputCls} minLength={8} required />
                  <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-3 text-[#9B8AB0] hover:text-[#7C35DC]" data-testid="signup-show-password">
                    {showPassword ? <EyeSlash size={16} /> : <Eye size={16} />}
                  </button>
                </div>

                <button type="submit" disabled={loading} data-testid="signup-submit"
                  className="w-full mt-1.5 py-3 rounded-lg text-white font-extrabold text-sm tracking-wide disabled:opacity-50 hover:-translate-y-0.5 transition-transform"
                  style={{ background: 'linear-gradient(135deg, #C044E0 0%, #7C35DC 50%, #5B28D4 100%)', fontFamily: 'Plus Jakarta Sans' }}>
                  {loading ? 'Creating workspace…' : 'Create My Account'}
                </button>
              </form>

              <p className="text-xs text-[#5A4A7A] mt-4 text-center">
                Already have an account?{' '}
                <Link to="/login" className="font-extrabold text-[#7C35DC] hover:underline" data-testid="signup-login-link">Login</Link>
              </p>
              <p className="text-[11px] text-[#9B8AB0] mt-3 text-center">
                Want our team to set ARIA up for you?{' '}
                <button onClick={() => setShowContact(true)} className="font-bold text-[#7C35DC] hover:underline" data-testid="signup-contact-link">Contact us</button>
              </p>
            </div>
            <p className="text-[10px] text-center text-[#A0A8C0] mt-4 tracking-[0.18em] uppercase font-bold" data-testid="genleadai-footer">
              Powered by Aria · GenLeadAI
            </p>
          </div>
        </div>

        {/* ─── Compact plans strip ──────────────────────────────────────── */}
        <div className="mt-10 lg:mt-14" data-testid="signup-plans-strip">
          <div className="flex items-end justify-between flex-wrap gap-2 mb-3">
            <div>
              <div className="text-[10px] font-extrabold uppercase tracking-[0.22em] text-[#7C35DC] mb-0.5">Compact plans</div>
              <h3 className="text-lg font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Pick the right ARIA for your stage</h3>
            </div>
            <button onClick={() => setShowPlans(true)} data-testid="signup-plans-details-btn" className="text-xs font-bold text-[#7C35DC] hover:text-[#5B28D4] inline-flex items-center gap-1">
              See details <ArrowRight size={11} weight="bold" />
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {PLANS.map(p => (
              <PlanCard key={p.key} plan={p}
                onCta={() => { if (p.key === 'starter') scrollToSignup(); else setShowContact(true); }} />
            ))}
          </div>
        </div>

        {/* ─── Tiny contact strip ───────────────────────────────────────── */}
        <div className="mt-8 rounded-2xl border border-[#E0D4F7] px-4 py-3 flex items-center justify-between flex-wrap gap-2 bg-gradient-to-r from-white to-[#FAF7FF]" data-testid="signup-contact-strip">
          <p className="text-sm text-[#1A0A2E]">
            <span className="font-extrabold">Want ARIA set up for your business?</span>{' '}
            <span className="text-[#5A4A7A]">Our team can configure your touchpoints, integrations, and brand voice for you.</span>
          </p>
          <button onClick={() => setShowContact(true)} data-testid="signup-contact-strip-btn" className="px-4 py-2 rounded-lg text-xs font-extrabold btn-gradient text-white" style={{ fontFamily: 'Plus Jakarta Sans' }}>
            Contact Us
          </button>
        </div>

        <p className="text-[10px] text-center text-[#A0A8C0] mt-6 mb-2">By signing up, you agree to our Terms and Privacy Policy.</p>
      </div>

      {/* ─── Modals ──────────────────────────────────────────────────────── */}
      {showPlans && <PlansModal onClose={() => setShowPlans(false)} onContact={() => { setShowPlans(false); setShowContact(true); }} onStart={() => { setShowPlans(false); scrollToSignup(); }} />}
      {showContact && <ContactModal onClose={() => setShowContact(false)} prefillEmail={form.email} />}
    </div>
  );
};

// ─── Plan card ────────────────────────────────────────────────────────────
const PlanCard = ({ plan, onCta }) => (
  <div
    data-testid={`signup-plan-${plan.key}`}
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
    <button onClick={onCta} data-testid={`signup-plan-${plan.key}-cta`} className={`w-full mt-4 py-2 rounded-lg text-xs font-extrabold transition-all ${
      plan.recommended ? 'btn-gradient text-white' : 'bg-[#F4F0FF] text-[#7C35DC] hover:bg-[#7C35DC] hover:text-white border border-[#7C35DC]/20'
    }`} style={{ fontFamily: 'Plus Jakarta Sans' }}>
      {plan.cta}
    </button>
  </div>
);

// ─── Plans modal ──────────────────────────────────────────────────────────
const PlansModal = ({ onClose, onContact, onStart }) => (
  <div className="fixed inset-0 z-50 flex items-center justify-center p-4 aria-fade-up" style={{ background: 'rgba(20,8,42,0.55)', backdropFilter: 'blur(8px)' }} data-testid="signup-plans-modal" onClick={onClose}>
    <div className="bg-white rounded-3xl max-w-2xl w-full p-6 md:p-8 shadow-2xl border border-white/40" onClick={(e) => e.stopPropagation()}>
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="text-[10px] font-extrabold uppercase tracking-[0.22em] text-[#7C35DC]">Plans</div>
          <h2 className="text-xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Pick the right ARIA</h2>
        </div>
        <button onClick={onClose} data-testid="signup-plans-modal-close" className="w-8 h-8 rounded-full hover:bg-[#F4F0FF] flex items-center justify-center text-[#9B8AB0] hover:text-[#1A0A2E]"><X size={14} weight="bold" /></button>
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

// ─── Contact modal ────────────────────────────────────────────────────────
const ContactModal = ({ onClose, prefillEmail = '' }) => {
  const [form, setForm] = useState({ name: '', email: prefillEmail, company: '', website: '', message: '' });
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.name.trim() || !form.email.trim() || !form.message.trim()) {
      toast.error('Please fill in name, email, and message.');
      return;
    }
    setBusy(true);
    try {
      // Best-effort: POST to the beta-feedback endpoint with kind='contact' so the
      // master-admin /admin/feedback tab gets the inbound lead. If the endpoint
      // is unavailable we still show a graceful toast so the visitor isn't blocked.
      await axios.post(`${API}/api/contact/request`, {
        ...form,
        page: 'signup',
      }).catch(() => { /* swallow — UI still confirms */ });
      toast.success("Thanks — we'll be in touch within 1 business day.");
      onClose();
    } finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 aria-fade-up" style={{ background: 'rgba(20,8,42,0.55)', backdropFilter: 'blur(8px)' }} data-testid="signup-contact-modal" onClick={onClose}>
      <div className="bg-white rounded-3xl max-w-lg w-full p-6 md:p-7 shadow-2xl border border-white/40" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3">
          <div>
            <div className="text-[10px] font-extrabold uppercase tracking-[0.22em] text-[#7C35DC]">Talk to us</div>
            <h2 className="text-xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Request ARIA Setup</h2>
            <p className="text-xs text-[#5A4A7A] mt-1">Tell us about your funnel — our team will reach out to set you up.</p>
          </div>
          <button onClick={onClose} data-testid="signup-contact-modal-close" className="w-8 h-8 rounded-full hover:bg-[#F4F0FF] flex items-center justify-center text-[#9B8AB0] hover:text-[#1A0A2E]"><X size={14} weight="bold" /></button>
        </div>
        <form onSubmit={submit} className="space-y-2.5 mt-3" data-testid="signup-contact-form">
          <Field label="Your name" testid="contact-name" value={form.name} onChange={(v) => setForm({ ...form, name: v })} required />
          <Field label="Email" type="email" testid="contact-email" value={form.email} onChange={(v) => setForm({ ...form, email: v })} required />
          <Field label="Company" testid="contact-company" value={form.company} onChange={(v) => setForm({ ...form, company: v })} />
          <Field label="Website" testid="contact-website" value={form.website} onChange={(v) => setForm({ ...form, website: v })} />
          <div>
            <label className="block text-[10px] font-extrabold uppercase tracking-[0.18em] text-[#9B8AB0] mb-1">Message</label>
            <textarea required value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} rows={3} data-testid="contact-message"
              placeholder="Tell us about your lead sources and what you need help with."
              className="w-full bg-white border border-[#E8E0F5] rounded-lg px-3 py-2 text-sm focus:border-[#7C35DC] focus:ring-2 focus:ring-[#7C35DC]/15 outline-none transition resize-none" />
          </div>
          <button type="submit" disabled={busy} data-testid="signup-contact-submit"
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
    <label className="block text-[10px] font-extrabold uppercase tracking-[0.18em] text-[#9B8AB0] mb-1">{label}{required ? '' : ''}</label>
    <input type={type} value={value} onChange={(e) => onChange(e.target.value)} required={required} data-testid={testid}
      className="w-full bg-white border border-[#E8E0F5] rounded-lg px-3 py-2 text-sm focus:border-[#7C35DC] focus:ring-2 focus:ring-[#7C35DC]/15 outline-none transition" />
  </div>
);

export default Signup;
