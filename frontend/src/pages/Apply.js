/**
 * /apply — 4-section qualification form (V3 of UX flow standardisation, iter140).
 *
 * Sections:
 *   1. About You          — full_name, work_email, role, country
 *   2. Your Business      — company_name, company_url, industry, employees, revenue
 *   3. Your Current Setup — current_setup, channels[], current_volume, biggest_pain
 *   4. Fit & Readiness    — goal, timeline, budget_band, ready_to_start
 *
 * Behavior:
 *   • Top progress indicator (Step N of 4) + bar.
 *   • Next button only — submit appears on Section 4.
 *   • Inline validation on attempted advance.
 *   • POST /api/applications → redirect to /apply/thank-you?id=...
 *   • No login or signup CTAs anywhere on this page.
 */
import React, { useState, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';

const API = process.env.REACT_APP_BACKEND_URL;

const SECTIONS = [
  { id: 1, title: 'About You', sub: 'So we know who we\'re talking to.' },
  { id: 2, title: 'Your Business', sub: 'Helps us see fit at a glance.' },
  { id: 3, title: 'Your Current Setup', sub: 'Where ARIA would actually plug in.' },
  { id: 4, title: 'Fit & Readiness', sub: 'Last 4 questions, promise.' },
];

const CHANNELS = [
  'WhatsApp', 'Email', 'LinkedIn', 'Instagram DMs', 'Facebook Ads', 'Google Ads',
  'Cold calling', 'Saleshandy', 'Lemlist', 'Apollo', 'Referrals', 'Inbound only',
];

const EMPTY = {
  full_name: '', work_email: '', role: '', country: '',
  company_name: '', company_url: '', industry: '', employees: '', revenue: '',
  current_setup: '', channels: [], current_volume: '', biggest_pain: '',
  goal: '', timeline: '', budget_band: '', ready_to_start: true,
};

const Apply = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [form, setForm] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);

  const set = (k) => (e) => {
    const v = e?.target?.type === 'checkbox' ? e.target.checked : e?.target?.value ?? e;
    setForm((f) => ({ ...f, [k]: v }));
    setErrors((er) => ({ ...er, [k]: undefined }));
  };

  const toggleChannel = (ch) => {
    setForm((f) => ({
      ...f,
      channels: f.channels.includes(ch) ? f.channels.filter((c) => c !== ch) : [...f.channels, ch],
    }));
  };

  const required = useMemo(() => ({
    1: ['full_name', 'work_email', 'role', 'country'],
    2: ['company_name', 'industry', 'employees'],
    3: ['current_setup', 'current_volume', 'biggest_pain'],
    4: ['goal', 'timeline', 'budget_band'],
  }), []);

  const validate = (n) => {
    const errs = {};
    (required[n] || []).forEach((k) => {
      if (!String(form[k] || '').trim()) errs[k] = 'Required';
    });
    if (n === 1 && form.work_email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.work_email)) {
      errs.work_email = 'Please enter a valid email';
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const next = () => {
    if (!validate(step)) return;
    setStep((s) => Math.min(4, s + 1));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };
  const back = () => setStep((s) => Math.max(1, s - 1));

  const submit = async (e) => {
    e.preventDefault();
    if (!validate(4)) return;
    setSubmitting(true);
    try {
      const { data } = await axios.post(`${API}/api/applications`, form);
      navigate(`/apply/thank-you?id=${encodeURIComponent(data.id)}`);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Something went wrong submitting your application. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const pct = Math.round((step / 4) * 100);

  return (
    <div className="min-h-screen bg-[#FAFAFA]" data-testid="apply-page">
      <TopBar />

      <main className="mx-auto w-full max-w-2xl px-4 py-10 md:py-16">
        {/* Progress */}
        <div className="mb-8" data-testid="apply-progress">
          <div className="flex items-end justify-between mb-2">
            <div>
              <div className="text-[11px] font-extrabold uppercase tracking-[0.18em] text-[#7C35DC]">
                Step {step} of 4
              </div>
              <h1 className="text-2xl md:text-3xl font-extrabold text-[#1A0A2E] mt-1" style={{ fontFamily: 'Plus Jakarta Sans' }}>
                {SECTIONS[step - 1].title}
              </h1>
              <p className="text-sm text-[#5A4A7A] mt-1">{SECTIONS[step - 1].sub}</p>
            </div>
            <div className="text-xs font-mono font-bold text-[#5A4A7A]">{pct}%</div>
          </div>
          <div className="h-1.5 rounded-full bg-[#E8E0F5] overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{ width: `${pct}%`, background: 'linear-gradient(90deg, #7C35DC 0%, #C044E0 100%)' }}
              data-testid="apply-progress-bar"
            />
          </div>
        </div>

        <form onSubmit={submit} className="bg-white border border-[#E8E0F5] rounded-2xl p-6 md:p-8 space-y-5" style={{ boxShadow: '0 8px 24px rgba(26,10,46,0.06)' }}>
          {step === 1 && (
            <div className="space-y-5" data-testid="apply-section-1">
              <Field label="Full name" value={form.full_name} onChange={set('full_name')} error={errors.full_name} placeholder="Megha Agarwal" testid="apply-full_name" />
              <Field label="Work email" type="email" value={form.work_email} onChange={set('work_email')} error={errors.work_email} placeholder="you@yourcompany.com" testid="apply-work_email" />
              <Field label="Your role" value={form.role} onChange={set('role')} error={errors.role} placeholder="Founder, Head of Sales, Operations Lead…" testid="apply-role" />
              <Select label="Country" value={form.country} onChange={set('country')} error={errors.country} testid="apply-country"
                options={['', 'India', 'United States', 'United Kingdom', 'United Arab Emirates', 'Singapore', 'Canada', 'Australia', 'Other']}
              />
            </div>
          )}

          {step === 2 && (
            <div className="space-y-5" data-testid="apply-section-2">
              <Field label="Company name" value={form.company_name} onChange={set('company_name')} error={errors.company_name} placeholder="Pietential" testid="apply-company_name" />
              <Field label="Website" value={form.company_url} onChange={set('company_url')} error={errors.company_url} placeholder="pietential.com (optional)" testid="apply-company_url" />
              <Field label="Industry" value={form.industry} onChange={set('industry')} error={errors.industry} placeholder="SaaS · D2C · Consulting · Healthcare…" testid="apply-industry" />
              <Select label="Team size" value={form.employees} onChange={set('employees')} error={errors.employees} testid="apply-employees"
                options={['', 'Just me', '2–5', '6–20', '21–50', '51–200', '200+']}
              />
              <Select label="Annual revenue (USD, optional)" value={form.revenue} onChange={set('revenue')} testid="apply-revenue"
                options={['', 'Pre-revenue', '<$100K', '$100K–$500K', '$500K–$2M', '$2M–$10M', '$10M+']}
              />
            </div>
          )}

          {step === 3 && (
            <div className="space-y-5" data-testid="apply-section-3">
              <Textarea label="What does your sales process look like today?" value={form.current_setup} onChange={set('current_setup')} error={errors.current_setup} placeholder="Who handles leads · what tools you use · how outreach gets sent · where it breaks down…" rows={4} testid="apply-current_setup" />
              <div>
                <label className="block text-xs font-extrabold uppercase tracking-[0.18em] text-[#5A4A7A] mb-2">Channels you use today</label>
                <div className="flex flex-wrap gap-2" data-testid="apply-channels">
                  {CHANNELS.map((ch) => {
                    const active = form.channels.includes(ch);
                    return (
                      <button key={ch} type="button" onClick={() => toggleChannel(ch)}
                        className="px-3 py-1.5 rounded-full text-xs font-bold transition-all"
                        style={{
                          background: active ? '#7C35DC' : 'transparent',
                          color: active ? '#fff' : '#5A4A7A',
                          border: `1px solid ${active ? '#7C35DC' : '#E8E0F5'}`,
                        }}
                        data-testid={`apply-channel-${ch.toLowerCase().replace(/\W+/g, '-')}`}
                      >
                        {ch}
                      </button>
                    );
                  })}
                </div>
              </div>
              <Field label="Roughly how many new leads / inquiries per month?" value={form.current_volume} onChange={set('current_volume')} error={errors.current_volume} placeholder="~150 inbound, ~50 outbound" testid="apply-current_volume" />
              <Textarea label="Biggest bottleneck in your current pipeline?" value={form.biggest_pain} onChange={set('biggest_pain')} error={errors.biggest_pain} placeholder="Founder-led replies don't scale · Leads go cold · No follow-up rhythm · Spreadsheet hell…" rows={3} testid="apply-biggest_pain" />
            </div>
          )}

          {step === 4 && (
            <div className="space-y-5" data-testid="apply-section-4">
              <Textarea label="What does success with ARIA look like in 90 days?" value={form.goal} onChange={set('goal')} error={errors.goal} placeholder="3x reply rate · Book 20 qualified calls/week · Free 12 founder hours/week…" rows={3} testid="apply-goal" />
              <Select label="When would you ideally start?" value={form.timeline} onChange={set('timeline')} error={errors.timeline} testid="apply-timeline"
                options={[
                  ['', 'Choose one…'],
                  ['now', 'Yesterday — let\'s go'],
                  ['1-3_months', 'Within 1–3 months'],
                  ['3-6_months', '3–6 months out'],
                  ['exploring', 'Just exploring for now'],
                ]}
              />
              <Select label="Engagement budget" value={form.budget_band} onChange={set('budget_band')} error={errors.budget_band} testid="apply-budget_band"
                options={[
                  ['', 'Choose a range…'],
                  ['under_10k', 'Under $10K total'],
                  ['10k_50k', '$10K–$50K'],
                  ['50k_500k', '$50K–$500K'],
                  ['500k_plus', '$500K+'],
                ]}
              />
              <label className="flex items-start gap-3 text-sm text-[#1A0A2E] cursor-pointer">
                <input type="checkbox" checked={form.ready_to_start} onChange={set('ready_to_start')} className="mt-1 accent-[#7C35DC]" data-testid="apply-ready_to_start" />
                <span>I have decision-making authority for this engagement and can move forward within my stated timeline.</span>
              </label>
            </div>
          )}

          {/* Nav buttons */}
          <div className="flex items-center justify-between pt-2">
            <button type="button" onClick={back} disabled={step === 1}
              className="text-sm font-bold text-[#5A4A7A] hover:text-[#1A0A2E] disabled:opacity-30 disabled:cursor-not-allowed"
              data-testid="apply-back-btn"
            >
              ← Back
            </button>
            {step < 4 ? (
              <button type="button" onClick={next}
                className="px-6 py-2.5 rounded-full text-sm font-extrabold text-white transition-all hover:opacity-90"
                style={{ background: 'linear-gradient(90deg, #7C35DC 0%, #C044E0 100%)' }}
                data-testid="apply-next-btn"
              >
                Next →
              </button>
            ) : (
              <button type="submit" disabled={submitting}
                className="px-6 py-2.5 rounded-full text-sm font-extrabold text-white transition-all hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
                style={{ background: 'linear-gradient(90deg, #7C35DC 0%, #C044E0 100%)' }}
                data-testid="apply-submit-btn"
              >
                {submitting ? 'Submitting…' : 'Submit Application →'}
              </button>
            )}
          </div>
        </form>

        <p className="text-center text-xs text-[#9B8AB0] mt-6">
          We review every application personally. If we see a fit, you'll hear from us within 48 hours.
        </p>
      </main>
    </div>
  );
};

// ───────────── primitives ─────────────

const TopBar = () => (
  <header className="border-b border-[#E8E0F5] bg-white">
    <div className="mx-auto w-full max-w-5xl px-4 h-14 flex items-center justify-between">
      <Link to="/" className="text-base font-extrabold tracking-tight" style={{
        background: 'linear-gradient(90deg, #7C35DC, #E2B96F)',
        WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
      }} data-testid="apply-logo-home">
        ARIA by GenLeadAI
      </Link>
      <Link to="/demo" className="text-xs font-bold text-[#5A4A7A] hover:text-[#7C35DC]" data-testid="apply-see-demo-link">
        See ARIA in action →
      </Link>
    </div>
  </header>
);

const Field = ({ label, error, testid, ...rest }) => (
  <div>
    <label className="block text-xs font-extrabold uppercase tracking-[0.18em] text-[#5A4A7A] mb-2">{label}</label>
    <input {...rest} data-testid={testid}
      className="w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-4 py-2.5 rounded-lg focus:border-[#7C35DC] focus:ring-2 focus:ring-[rgba(124,53,220,0.12)] outline-none transition-all text-sm"
    />
    {error && <p className="text-xs text-[#DC2626] mt-1.5 font-bold" data-testid={`${testid}-error`}>{error}</p>}
  </div>
);

const Textarea = ({ label, error, testid, ...rest }) => (
  <div>
    <label className="block text-xs font-extrabold uppercase tracking-[0.18em] text-[#5A4A7A] mb-2">{label}</label>
    <textarea {...rest} data-testid={testid}
      className="w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-4 py-2.5 rounded-lg focus:border-[#7C35DC] focus:ring-2 focus:ring-[rgba(124,53,220,0.12)] outline-none transition-all text-sm"
    />
    {error && <p className="text-xs text-[#DC2626] mt-1.5 font-bold" data-testid={`${testid}-error`}>{error}</p>}
  </div>
);

const Select = ({ label, options, error, testid, ...rest }) => (
  <div>
    <label className="block text-xs font-extrabold uppercase tracking-[0.18em] text-[#5A4A7A] mb-2">{label}</label>
    <select {...rest} data-testid={testid}
      className="w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-4 py-2.5 rounded-lg focus:border-[#7C35DC] focus:ring-2 focus:ring-[rgba(124,53,220,0.12)] outline-none transition-all text-sm"
    >
      {options.map((opt) => {
        if (Array.isArray(opt)) return <option key={opt[0]} value={opt[0]}>{opt[1]}</option>;
        return <option key={opt} value={opt}>{opt || 'Choose one…'}</option>;
      })}
    </select>
    {error && <p className="text-xs text-[#DC2626] mt-1.5 font-bold" data-testid={`${testid}-error`}>{error}</p>}
  </div>
);

export default Apply;
