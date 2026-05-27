/* eslint-disable react-hooks/exhaustive-deps */
/* ─────────────────────────────────────────────────────────────────────
   ARIA by GenLeadAI — public landing page
   Converted from the user's Tailwind v4 / `motion/react` `.tsx` artifacts
   to JSX + framer-motion. All brand styles are scoped via `.aria-landing`
   so nothing leaks into the rest of the app.
   ───────────────────────────────────────────────────────────────────── */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Check, X, ChevronDown, Star, Sparkles, ArrowRight,
  Linkedin, Instagram, Mail, Phone, MessageCircle, ExternalLink,
} from 'lucide-react';
import { AgentOrb, TypingWord, SignalBars } from './AiFlourishes';
import { AriaBot } from './AriaBot';
import './aria-landing.css';

const integrations = [
  'LinkedIn', 'Meta Ads', 'Google Ads', 'YouTube Ads', 'LinkedIn Ads',
  'WhatsApp', 'Saleshandy', 'Lemlist', 'Instantly', 'Smartlead',
  'Calendly', 'Gmail', 'Outlook', 'Typeform', 'Webflow', 'Stripe',
  'HubSpot', 'Pipedrive', 'Apollo.io', 'Proxycurl', 'Website Pixel', 'Webhook API',
];

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.22, 1, 0.36, 1] } },
};

function Reveal({ children, delay = 0, className = '' }) {
  return (
    <motion.div
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, margin: '-80px' }}
      transition={{ delay }}
      variants={fadeUp}
      className={className}
    >
      {children}
    </motion.div>
  );
}

function Container({ children, className = '' }) {
  return <div className={`mx-auto w-full max-w-[1160px] px-6 ${className}`}>{children}</div>;
}

function SectionLabel({ children }) {
  return <div className="section-label">{children}</div>;
}

function Logo() {
  return (
    <div className="flex items-center gap-2" data-testid="aria-logo">
      <motion.div
        className="flex h-8 w-8 items-center justify-center rounded-lg pill-gradient"
        whileHover={{ rotate: 12, scale: 1.05 }}
        transition={{ type: 'spring', stiffness: 300 }}
      >
        <Sparkles className="h-4 w-4 text-white" />
      </motion.div>
      <span className="font-display text-lg font-extrabold tracking-tight text-foreground">
        ARIA<span className="text-gradient"> ·</span>
        <span className="ml-1 font-semibold text-muted-foreground">GenLeadAI</span>
      </span>
    </div>
  );
}

function PillButton({ children, onClick, href = '#', variant = 'primary', className = '', testId }) {
  const base = 'inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-semibold transition-all cursor-pointer';
  const cls =
    variant === 'primary'
      ? `${base} pill-gradient pill-gradient-hover ${className}`
      : `${base} border border-border bg-card text-foreground hover:bg-muted ${className}`;
  if (onClick) {
    return (
      <button type="button" onClick={onClick} className={cls} data-testid={testId}>
        {children}
      </button>
    );
  }
  return <a href={href} className={cls} data-testid={testId}>{children}</a>;
}

function Nav({ onSignup, onLogin }) {
  return (
    <header className="sticky top-0 z-50 border-b border-border/60 backdrop-blur-xl"
            style={{ backgroundColor: 'rgba(250, 250, 255, 0.8)' }}>
      <Container className="flex h-16 items-center justify-between">
        <Logo />
        <nav className="hidden items-center gap-8 text-sm font-medium text-muted-foreground md:flex">
          {['Features', 'How it works', 'Integrations', 'Pricing'].map((l) => (
            <a
              key={l}
              href={`#${l.toLowerCase().replace(/\s/g, '')}`}
              className="group relative transition-colors hover:text-foreground"
            >
              {l}
              <span className="absolute -bottom-1 left-0 h-px w-0 transition-all group-hover:w-full"
                    style={{ backgroundColor: 'var(--aria-primary)' }} />
            </a>
          ))}
        </nav>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onLogin}
            className="hidden rounded-full px-4 py-2 text-sm font-medium text-foreground hover:bg-muted sm:inline-flex"
            data-testid="nav-login-btn"
          >
            Log in
          </button>
          <PillButton onClick={onSignup} testId="nav-signup-btn">
            Start free <ArrowRight className="h-4 w-4" />
          </PillButton>
        </div>
      </Container>
    </header>
  );
}

function ModeTile({ active, onClick, title, desc, testId }) {
  return (
    <motion.button
      type="button"
      onClick={onClick}
      whileTap={{ scale: 0.97 }}
      data-testid={testId}
      className={`relative overflow-hidden rounded-xl border p-4 text-left transition-all ${
        active ? 'border-primary bg-accent shadow-sm' : 'border-border bg-card hover:border-primary/40'
      }`}
    >
      {active && (
        <motion.span
          layoutId="mode-glow"
          className="pointer-events-none absolute inset-0 -z-0 opacity-60"
          style={{ background: 'radial-gradient(circle at 30% 20%, oklch(0.7 0.27 335 / 0.25), transparent 70%)' }}
        />
      )}
      <div className="relative text-sm font-semibold">{title}</div>
      <div className="relative mt-1 text-xs text-muted-foreground">{desc}</div>
    </motion.button>
  );
}

function Field({ label, ...rest }) {
  return (
    <div>
      <label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </label>
      <input
        {...rest}
        className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm outline-none transition-colors focus:border-primary"
        style={{ color: 'var(--aria-fg)' }}
      />
    </div>
  );
}

function SignupCard({ onSubmit }) {
  const [mode, setMode] = useState('b2b');
  const [email, setEmail] = useState('');
  const [pwd, setPwd] = useState('');
  return (
    <div
      id="signup"
      className="relative rounded-3xl border p-7 backdrop-blur md:p-8"
      style={{
        borderColor: 'rgba(255,255,255,0.4)',
        backgroundColor: 'rgba(255,255,255,0.95)',
        boxShadow: '0 25px 50px -12px rgba(88, 28, 135, 0.30)',
      }}
      data-testid="hero-signup-card"
    >
      <div className="absolute -top-3 right-6 flex items-center gap-2 rounded-full pill-gradient px-3 py-1 text-[10px] font-bold tracking-wider text-white">
        <SignalBars className="text-white" />
        ARIA ONLINE
      </div>
      <h3 className="text-2xl">Start your free workspace</h3>
      <p className="mt-1 text-sm text-muted-foreground">No credit card. Ready in 5 minutes.</p>

      <form
        className="mt-6 space-y-4"
        onSubmit={(e) => { e.preventDefault(); onSubmit?.({ email, mode }); }}
      >
        <Field
          label="Work email"
          type="email"
          required
          placeholder="you@company.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          data-testid="hero-signup-email"
        />
        <Field
          label="Password"
          type="password"
          required
          minLength={8}
          placeholder="Min. 8 characters"
          value={pwd}
          onChange={(e) => setPwd(e.target.value)}
          data-testid="hero-signup-password"
        />

        <div>
          <label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Choose your mode
          </label>
          <div className="grid grid-cols-2 gap-3">
            <ModeTile
              active={mode === 'b2b'}
              onClick={() => setMode('b2b')}
              title="B2B Instinct"
              desc="10–100 high-value prospects"
              testId="hero-mode-b2b"
            />
            <ModeTile
              active={mode === 'b2c'}
              onClick={() => setMode('b2c')}
              title="B2C Automation"
              desc="High-volume lead handling"
              testId="hero-mode-b2c"
            />
          </div>
        </div>

        <motion.button
          type="submit"
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          className="w-full rounded-full pill-gradient pill-gradient-hover px-5 py-3.5 font-semibold text-white"
          data-testid="hero-signup-submit"
        >
          Create my ARIA workspace →
        </motion.button>

        <p className="text-center text-xs text-muted-foreground">
          Already have an account?{' '}
          <a href="/login" className="font-medium text-primary underline">Log in</a>
          {' '}· 14-day free trial
        </p>
      </form>
    </div>
  );
}

function Hero({ onSignup }) {
  return (
    <section className="relative overflow-hidden brand-gradient">
      <div className="pointer-events-none absolute inset-0 grid-bg" />

      <motion.div
        className="pointer-events-none absolute -left-32 top-10 rounded-full blur-3xl"
        style={{ width: 520, height: 520, backgroundColor: 'oklch(0.7 0.27 335 / 0.4)' }}
        animate={{ x: [0, 40, -20, 0], y: [0, 30, -10, 0] }}
        transition={{ duration: 16, repeat: Infinity, ease: 'easeInOut' }}
      />
      <motion.div
        className="pointer-events-none absolute right-0 top-40 rounded-full blur-3xl"
        style={{ width: 560, height: 560, backgroundColor: 'oklch(0.55 0.27 260 / 0.45)' }}
        animate={{ x: [0, -50, 20, 0], y: [0, -20, 30, 0] }}
        transition={{ duration: 18, repeat: Infinity, ease: 'easeInOut' }}
      />

      {[...Array(12)].map((_, i) => (
        <motion.span
          key={i}
          className="pointer-events-none absolute h-1 w-1 rounded-full bg-white/70"
          style={{ left: `${(i * 83) % 100}%`, top: `${(i * 47) % 100}%` }}
          animate={{ y: [0, -20, 0], opacity: [0.2, 0.9, 0.2] }}
          transition={{ duration: 4 + (i % 4), delay: i * 0.3, repeat: Infinity, ease: 'easeInOut' }}
        />
      ))}

      <Container className="relative py-24 md:py-32">
        <div className="grid gap-14 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
          <div className="text-white">
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
              className="chip-on-brand"
            >
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-75"
                      style={{ backgroundColor: 'oklch(0.85 0.18 75)' }} />
                <span className="relative inline-flex h-2 w-2 rounded-full"
                      style={{ backgroundColor: 'oklch(0.85 0.18 75)' }} />
              </span>
              POWERED BY ARIA — AI SALES AGENT, LIVE
            </motion.div>

            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.1 }}
              className="mt-6 text-5xl leading-[0.98] text-white md:text-[5.25rem]"
              data-testid="hero-headline"
            >
              We make{' '}
              <TypingWord
                words={['sales intelligence', 'lead handling', 'outreach timing', 'prospect signals']}
                className="shimmer-text font-extrabold"
              />
              <br />
              <span className="italic">f*cking useful</span>
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.25 }}
              className="mt-6 max-w-xl text-lg"
              style={{ color: 'rgba(255,255,255,0.85)' }}
            >
              ARIA crawls every signal across LinkedIn, news, and 15+ lead platforms. B2B? It tells
              you exactly when to strike — and drafts the message. B2C? It handles the full
              conversation itself. You just close.
            </motion.p>

            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.6, delay: 0.4 }}
              className="mt-8 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm"
              style={{ color: 'rgba(255,255,255,0.80)' }}
            >
              <div className="flex items-center gap-1">
                {[...Array(5)].map((_, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, scale: 0 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.5 + i * 0.08, type: 'spring' }}
                  >
                    <Star className="h-4 w-4 fill-current" style={{ color: 'oklch(0.85 0.18 75)' }} />
                  </motion.div>
                ))}
              </div>
              <span className="font-medium">Used by 200+ growth teams</span>
              <span style={{ color: 'rgba(255,255,255,0.30)' }}>|</span>
              <span style={{ color: 'rgba(255,255,255,0.70)' }}>
                Pietential · BlueGroup · Deshwal · Dwella · iSaveFirst
              </span>
            </motion.div>
          </div>

          <div className="relative">
            <div className="absolute -right-10 -top-10 hidden lg:block opacity-40"
                 style={{ width: 320, height: 320 }}>
              <AgentOrb />
            </div>
            <motion.div
              initial={{ opacity: 0, x: 40, rotate: 8 }}
              animate={{ opacity: 1, x: 0, rotate: 0 }}
              transition={{ duration: 0.8, delay: 0.4, type: 'spring', stiffness: 120 }}
              className="pointer-events-none absolute -right-6 -top-14 z-10 hidden md:block"
            >
              <AriaBot size={220} />
            </motion.div>
            <motion.div
              initial={{ opacity: 0, y: 24, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ duration: 0.7, delay: 0.15, ease: [0.22, 1, 0.36, 1] }}
              className="relative"
            >
              <SignupCard onSubmit={onSignup} />
            </motion.div>
          </div>
        </div>
      </Container>
    </section>
  );
}

function Marquee() {
  const items = [
    'LINKEDIN', 'META ADS', 'GOOGLE ADS', 'YOUTUBE ADS', 'LINKEDIN ADS', 'WHATSAPP',
    'SALESHANDY', 'LEMLIST', 'INSTANTLY', 'SMARTLEAD', 'CALENDLY', 'GMAIL', 'OUTLOOK',
    'TYPEFORM', 'WEBFLOW', 'STRIPE', 'HUBSPOT', 'PIPEDRIVE', 'APOLLO.IO', 'PROXYCURL',
    'WEBSITE PIXEL', 'WEBHOOK API',
  ];
  return (
    <section className="overflow-hidden border-y border-border bg-card py-6">
      <div className="relative">
        <div className="pointer-events-none absolute inset-y-0 left-0 z-10 w-24"
             style={{ background: 'linear-gradient(to right, var(--aria-card), transparent)' }} />
        <div className="pointer-events-none absolute inset-y-0 right-0 z-10 w-24"
             style={{ background: 'linear-gradient(to left, var(--aria-card), transparent)' }} />
        <div className="flex w-max animate-marquee gap-12 whitespace-nowrap font-mono text-xs font-medium tracking-[0.2em] text-muted-foreground">
          {[...items, ...items].map((it, i) => (
            <span key={i} className="flex items-center gap-12">
              {it}
              <span className="h-1 w-1 rounded-full"
                    style={{ backgroundColor: 'color-mix(in oklch, var(--aria-primary) 60%, transparent)' }} />
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

function ModeCard({ tag, tagColor, headline, body, features }) {
  const accentStyle =
    tagColor === 'primary'
      ? {
          borderColor: 'color-mix(in oklch, var(--aria-primary) 30%, transparent)',
          background: 'linear-gradient(180deg, oklch(0.96 0.04 295) 0%, #ffffff 60%)',
        }
      : {
          borderColor: 'oklch(0.62 0.17 152 / 0.3)',
          background: 'linear-gradient(180deg, oklch(0.96 0.04 152) 0%, #ffffff 60%)',
        };
  const tagBgClass = tagColor === 'primary' ? 'pill-gradient text-white' : 'bg-success text-white';
  const checkColorClass = tagColor === 'primary' ? 'text-primary' : 'text-success';
  return (
    <motion.div
      whileHover={{ y: -6 }}
      transition={{ type: 'spring', stiffness: 300, damping: 25 }}
      className="group relative h-full overflow-hidden rounded-3xl border p-8"
      style={accentStyle}
    >
      <div className="pointer-events-none absolute -right-10 -top-10 h-40 w-40 rounded-full blur-3xl"
           style={{ backgroundColor: 'color-mix(in oklch, var(--aria-primary) 10%, transparent)' }} />
      <span className={`inline-block rounded-full px-3 py-1 font-mono text-[10px] font-semibold tracking-[0.2em] ${tagBgClass}`}>
        {tag}
      </span>
      <h3 className="mt-5 text-3xl">{headline}</h3>
      <p className="mt-4 text-muted-foreground">{body}</p>
      <ul className="mt-6 space-y-3">
        {features.map((f, i) => (
          <motion.li
            key={f}
            initial={{ opacity: 0, x: -10 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.05 * i }}
            className="flex items-start gap-3 text-sm"
          >
            <Check className={`mt-0.5 h-4 w-4 shrink-0 ${checkColorClass}`} />
            <span className="text-foreground/85">{f}</span>
          </motion.li>
        ))}
      </ul>
    </motion.div>
  );
}

function TwoModes() {
  return (
    <section id="features" className="py-24">
      <Container>
        <Reveal><SectionLabel>Two modes. One platform.</SectionLabel></Reveal>
        <Reveal delay={0.05}>
          <h2 className="mt-4 max-w-3xl text-4xl md:text-5xl">
            Built for how B2B and B2C<br />actually work
          </h2>
        </Reveal>
        <Reveal delay={0.1}>
          <p className="mt-4 max-w-2xl text-lg text-muted-foreground">
            High-value accounts need intelligence. High-volume leads need automation. ARIA handles
            both — same workspace, one dashboard.
          </p>
        </Reveal>

        <div className="mt-12 grid gap-6 lg:grid-cols-2">
          <Reveal>
            <ModeCard
              tag="B2B INSTINCT"
              tagColor="primary"
              headline="Know exactly when to strike"
              body="ARIA scans your 10–100 high-value prospects daily across LinkedIn, news, and the web. The moment something relevant happens — a deal, a promotion, a summit — you get a drafted message, the right resource, and the exact timing to send it."
              features={[
                'Daily LinkedIn + news + web scan per prospect',
                '8 signal types: deals, funding, events, promotions',
                'ICP-matched message drafted + resource attached',
                'Send via ARIA, edit in dashboard, or copy to Gmail',
                'Dashboard cards + email digest + WhatsApp alerts',
              ]}
            />
          </Reveal>
          <Reveal delay={0.1}>
            <ModeCard
              tag="B2C AUTOMATION"
              tagColor="success"
              headline="Handle every lead. Without lifting a finger."
              body="Train ARIA on your business. Connect your sources. ARIA qualifies leads, runs full conversations on WhatsApp, email, and LinkedIn, books calls, handles objections — 24/7, fully autonomous."
              features={[
                'Ingests leads from 15+ platforms automatically',
                'Full conversations on WhatsApp, email, LinkedIn',
                'Qualifies, objects, books calls autonomously',
                'Hands off to you only when it actually matters',
                'Trained on your docs, ICPs, voice, and playbook',
              ]}
            />
          </Reveal>
        </div>
      </Container>
    </section>
  );
}

function HowItWorks() {
  const steps = [
    { n: '01', title: 'Connect your sources', body: 'LinkedIn, Meta Ads, website forms, email outreach tools, WhatsApp — all from one integrations page. No backend work, no dev needed.' },
    { n: '02', title: 'Train ARIA on your business', body: 'Upload your brochure, pricing sheet, or any doc. ARIA extracts your ICPs, offer, objection playbook, and brand voice automatically.' },
    { n: '03', title: 'ARIA starts scanning and talking', body: 'Daily prospect intelligence for B2B. Autonomous lead conversations for B2C. Signals surface. Leads qualify. Calendar fills.' },
    { n: '04', title: 'You act on what matters', body: 'Review insight cards, send with one click, or let automation run. You stay in control of everything — or nothing. Your call.' },
  ];
  return (
    <section id="howitworks" className="bg-muted/40 py-24">
      <Container>
        <Reveal><SectionLabel>How it works</SectionLabel></Reveal>
        <Reveal delay={0.05}>
          <h2 className="mt-4 max-w-3xl text-4xl md:text-5xl">
            From setup to your first signal<br />in 4 steps
          </h2>
        </Reveal>
        <div className="mt-12 grid gap-5 md:grid-cols-2 lg:grid-cols-4">
          {steps.map((s, i) => (
            <Reveal key={s.n} delay={i * 0.08}>
              <motion.div
                whileHover={{ y: -6 }}
                transition={{ type: 'spring', stiffness: 300, damping: 25 }}
                className="soft-card group relative h-full overflow-hidden p-6"
              >
                <div className="inline-flex h-9 w-9 items-center justify-center rounded-lg pill-gradient font-mono text-xs font-semibold text-white">
                  {s.n}
                </div>
                <h3 className="mt-4 text-xl">{s.title}</h3>
                <p className="mt-3 text-sm text-muted-foreground">{s.body}</p>
              </motion.div>
            </Reveal>
          ))}
        </div>
      </Container>
    </section>
  );
}

function Comparison() {
  const before = [
    "Manual prospect research stealing hours from your day",
    "Missing signals — deals, promotions, events — entirely",
    "Generic outreach with zero timing intelligence",
    "Leads going cold while you're doing everything else",
    "5 disconnected tools that don't talk to each other",
    "CRM as a graveyard of forgotten contacts",
  ];
  const after = [
    'Daily intelligence scan — zero effort from you',
    'Every signal caught, classified, and acted on',
    'Message drafted, timed, and resource-matched for you',
    'B2C leads auto-qualified and nurtured while you sleep',
    'One workspace. Everything alive. One dashboard.',
    'Trained on your business. Works like your best rep.',
  ];
  return (
    <section className="py-24">
      <Container>
        <Reveal><SectionLabel>The honest comparison</SectionLabel></Reveal>
        <Reveal delay={0.05}>
          <h2 className="mt-4 text-4xl md:text-5xl">The old way vs the ARIA way</h2>
        </Reveal>
        <div className="mt-12 grid gap-6 lg:grid-cols-2">
          <Reveal>
            <div className="soft-card h-full p-8">
              <h3 className="text-2xl text-muted-foreground">The old way</h3>
              <ul className="mt-6 space-y-4">
                {before.map((b) => (
                  <li key={b} className="flex items-start gap-3 text-sm text-muted-foreground">
                    <X className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
                    <span>{b}</span>
                  </li>
                ))}
              </ul>
            </div>
          </Reveal>
          <Reveal delay={0.1}>
            <div
              className="relative h-full overflow-hidden rounded-2xl border border-primary/30 p-8"
              style={{ background: 'linear-gradient(180deg, oklch(0.96 0.04 295) 0%, #ffffff 60%)' }}
            >
              <motion.div
                className="pointer-events-none absolute -right-16 -top-16 h-64 w-64 rounded-full blur-3xl"
                style={{ backgroundColor: 'color-mix(in oklch, var(--aria-primary) 20%, transparent)' }}
                animate={{ scale: [1, 1.1, 1], opacity: [0.6, 0.9, 0.6] }}
                transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut' }}
              />
              <h3 className="relative text-2xl text-gradient">The ARIA way</h3>
              <ul className="relative mt-6 space-y-4">
                {after.map((a, i) => (
                  <motion.li
                    key={a}
                    initial={{ opacity: 0, x: -10 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.05 }}
                    className="flex items-start gap-3 text-sm"
                  >
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                    <span className="text-foreground/90">{a}</span>
                  </motion.li>
                ))}
              </ul>
            </div>
          </Reveal>
        </div>
      </Container>
    </section>
  );
}

function WhoItsFor() {
  const cards = [
    { emoji: '🎯', title: 'B2B Founders & Sales Leaders', body: "You have 20 high-value accounts you're trying to crack. ARIA watches them daily and tells you exactly when the window opens — and what to say." },
    { emoji: '⚡', title: 'B2C Growth Teams', body: 'Your lead volume is too high to handle manually. ARIA qualifies, converses, and books — so your team focuses only on the closes that matter.' },
    { emoji: '🧠', title: 'Fractional CMOs & Agencies', body: "Running growth for multiple clients? ARIA's multi-workspace setup means every client gets their own trained agent. One dashboard, full control." },
  ];
  return (
    <section className="bg-muted/40 py-24">
      <Container>
        <Reveal><SectionLabel>Who it's for</SectionLabel></Reveal>
        <Reveal delay={0.05}>
          <h2 className="mt-4 max-w-3xl text-4xl md:text-5xl">
            If this sounds like you, you're in the right place
          </h2>
        </Reveal>
        <div className="mt-12 grid gap-5 md:grid-cols-3">
          {cards.map((c, i) => (
            <Reveal key={c.title} delay={i * 0.1}>
              <motion.div
                whileHover={{ y: -6 }}
                transition={{ type: 'spring', stiffness: 300, damping: 25 }}
                className="soft-card group h-full p-7"
              >
                <motion.div
                  whileHover={{ rotate: [0, -8, 8, 0] }}
                  transition={{ duration: 0.6 }}
                  className="inline-flex h-12 w-12 items-center justify-center rounded-xl pill-gradient text-2xl"
                >
                  <span>{c.emoji}</span>
                </motion.div>
                <h3 className="mt-5 text-xl">{c.title}</h3>
                <p className="mt-3 text-sm text-muted-foreground">{c.body}</p>
              </motion.div>
            </Reveal>
          ))}
        </div>
      </Container>
    </section>
  );
}

function Testimonials() {
  const t = [
    { q: 'ARIA surfaced a signal about our top prospect attending a summit and drafted a message for us. We sent it, got a reply same day, and closed a contract 2 weeks later.', name: 'Rohan Khanna', role: 'CEO, B2B SaaS — Mumbai' },
    { q: 'We plugged in our Meta Ads and website form. ARIA started qualifying leads on WhatsApp overnight. Our team now only speaks to warm, pre-qualified prospects.', name: 'Priya Sharma', role: 'Head of Growth, D2C Brand — Delhi' },
    { q: 'Training took 10 minutes — I uploaded our deck and ARIA understood our entire ICP, pricing, and objections. It sounds more like us than our actual reps.', name: 'Ananya Verma', role: 'Founder, Consulting Firm — Bangalore' },
  ];
  return (
    <section className="py-24">
      <Container>
        <Reveal><SectionLabel>What they're saying</SectionLabel></Reveal>
        <Reveal delay={0.05}>
          <h2 className="mt-4 text-4xl md:text-5xl">Real results from real workspaces</h2>
        </Reveal>
        <div className="mt-12 grid gap-5 md:grid-cols-3">
          {t.map((x, i) => (
            <Reveal key={x.name} delay={i * 0.08}>
              <motion.div whileHover={{ y: -4 }} className="soft-card flex h-full flex-col p-7">
                <div className="flex gap-0.5" style={{ color: 'oklch(0.78 0.16 75)' }}>
                  {[...Array(5)].map((_, k) => <Star key={k} className="h-4 w-4 fill-current" />)}
                </div>
                <p className="mt-5 flex-1 text-sm leading-relaxed text-foreground/85">"{x.q}"</p>
                <div className="mt-6 border-t border-border pt-4">
                  <div className="text-sm font-semibold">{x.name}</div>
                  <div className="text-xs text-muted-foreground">{x.role}</div>
                </div>
              </motion.div>
            </Reveal>
          ))}
        </div>
      </Container>
    </section>
  );
}

function Integrations() {
  return (
    <section id="integrations" className="bg-muted/40 py-24">
      <Container>
        <Reveal><SectionLabel>Integrations</SectionLabel></Reveal>
        <Reveal delay={0.05}>
          <h2 className="mt-4 max-w-3xl text-4xl md:text-5xl">
            Connected to everything<br />you already use
          </h2>
        </Reveal>
        <Reveal delay={0.1}>
          <p className="mt-4 max-w-2xl text-lg text-muted-foreground">
            ARIA connects to every lead source and communication channel — no dev work, no APIs to
            configure manually.
          </p>
        </Reveal>
        <div className="mt-10 flex flex-wrap gap-2.5">
          {integrations.map((it, i) => (
            <motion.span
              key={it}
              initial={{ opacity: 0, scale: 0.85 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.025, type: 'spring', stiffness: 200 }}
              whileHover={{ y: -3, scale: 1.05 }}
              className="cursor-default rounded-full border border-border bg-card px-4 py-2 text-sm font-medium text-foreground/80 transition-colors hover:border-primary hover:text-primary"
            >
              {it}
            </motion.span>
          ))}
        </div>
      </Container>
    </section>
  );
}

function FAQ() {
  const faqs = [
    { q: 'What is ARIA?', a: 'ARIA is an AI sales intelligence and automation platform by GenLeadAI. It has two modes: B2B Instinct — daily prospect scanning, signal detection, and drafted outreach for human review — and B2C Automation, which handles the full lead conversation on WhatsApp, email, and LinkedIn on your behalf.' },
    { q: 'Does ARIA contact my prospects without my approval?', a: 'In B2B Instinct mode — no. ARIA surfaces insight cards with drafted messages. You decide to send, edit, or copy. In B2C Automation mode — yes, ARIA handles the full conversation autonomously, but you can step in and take over any thread at any time.' },
    { q: 'How do I train ARIA on my business?', a: 'Upload any document — brochure, pricing sheet, deck, case study — or paste a website URL and ARIA extracts your offer, ICPs, objection playbook, and brand voice automatically. You can also fill in training fields manually and preview the assembled AI prompt before saving.' },
    { q: 'Can I run multiple clients or businesses from one account?', a: 'Yes. ARIA is built for multi-workspace use. Each workspace has its own ICPs, training data, integrations, and notification settings. Switch between workspaces from one dashboard.' },
    { q: 'What lead sources can ARIA connect to?', a: 'LinkedIn, Meta Ads, Google Ads, YouTube Ads, LinkedIn Ads, website forms via webhook, website pixel, Saleshandy, Lemlist, Instantly, Smartlead, WhatsApp inbound, Gmail/Outlook, Calendly, CSV import, and a custom API endpoint. All connected from the Integrations page — no backend work needed.' },
    { q: 'Is my data secure?', a: "All API keys are encrypted at rest using Fernet symmetric encryption. Workspace data is fully isolated by tenant ID. TLS on all traffic. Passwords bcrypt-hashed. ARIA operates under Anthropic's commercial API terms — your data is never used to train AI models." },
  ];
  const [open, setOpen] = useState(0);
  return (
    <section className="py-24">
      <Container>
        <Reveal><SectionLabel>FAQ</SectionLabel></Reveal>
        <Reveal delay={0.05}><h2 className="mt-4 text-4xl md:text-5xl">Questions we get a lot</h2></Reveal>
        <Reveal delay={0.1}>
          <p className="mt-4 text-sm text-muted-foreground">
            Can't find what you need? Write to us at{' '}
            <a href="mailto:meghaagarwal@genleadai.com" className="font-medium text-primary underline">
              meghaagarwal@genleadai.com
            </a>
          </p>
        </Reveal>
        <div className="mt-10 space-y-3">
          {faqs.map((f, i) => (
            <Reveal key={i} delay={i * 0.04}>
              <div className="soft-card overflow-hidden transition-colors hover:border-primary/40">
                <button
                  type="button"
                  onClick={() => setOpen(open === i ? null : i)}
                  className="flex w-full items-center justify-between gap-4 p-6 text-left"
                  data-testid={`faq-toggle-${i}`}
                >
                  <span className="font-display text-lg font-bold">{f.q}</span>
                  <ChevronDown
                    className={`h-5 w-5 shrink-0 text-muted-foreground transition-transform ${open === i ? 'rotate-180' : ''}`}
                  />
                </button>
                <div className={`grid transition-all duration-300 ${open === i ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'}`}>
                  <div className="overflow-hidden">
                    <p className="px-6 pb-6 text-sm text-muted-foreground">{f.a}</p>
                  </div>
                </div>
              </div>
            </Reveal>
          ))}
        </div>
      </Container>
    </section>
  );
}

function CTABand({ onSignup }) {
  const [email, setEmail] = useState('');
  return (
    <section id="pricing" className="py-12">
      <Container>
        <div className="relative overflow-hidden rounded-3xl brand-gradient p-10 md:p-16">
          <div className="pointer-events-none absolute inset-0 grid-bg" />
          <motion.div
            className="pointer-events-none absolute -right-20 -top-20 rounded-full blur-3xl"
            style={{ width: 400, height: 400, backgroundColor: 'oklch(0.7 0.27 335 / 0.4)' }}
            animate={{ scale: [1, 1.15, 1], x: [0, -20, 0] }}
            transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
          />
          <div className="absolute -bottom-16 -left-16 hidden opacity-30 md:block"
               style={{ width: 280, height: 280 }}>
            <AgentOrb />
          </div>
          <div className="relative text-white">
            <h2 className="text-4xl text-white md:text-6xl">
              Start for free.<br />Deploy today.
            </h2>
            <p className="mt-5 max-w-xl text-lg" style={{ color: 'rgba(255,255,255,0.85)' }}>
              No credit card. No sales call. Your ARIA workspace is live in 5 minutes.
            </p>
            <form
              onSubmit={(e) => { e.preventDefault(); onSignup?.({ email }); }}
              className="mt-8 flex max-w-xl flex-col gap-3 sm:flex-row"
            >
              <input
                type="email"
                placeholder="Your work email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="flex-1 rounded-full border px-5 py-3.5 text-sm text-white outline-none backdrop-blur"
                style={{
                  borderColor: 'rgba(255,255,255,0.30)',
                  backgroundColor: 'rgba(255,255,255,0.15)',
                }}
                data-testid="cta-email"
              />
              <motion.button
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                className="rounded-full bg-white px-6 py-3.5 font-semibold"
                style={{ color: 'var(--aria-primary)' }}
                type="submit"
                data-testid="cta-submit"
              >
                Get started →
              </motion.button>
            </form>
            <p className="mt-4 text-xs" style={{ color: 'rgba(255,255,255,0.70)' }}>
              14-day free trial · Cancel anytime
            </p>
          </div>
        </div>
      </Container>
    </section>
  );
}

function ColLabel({ children }) {
  return (
    <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.2em] text-foreground">
      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: 'var(--aria-primary)' }} />
      {children}
    </div>
  );
}

function Footer() {
  return (
    <footer className="relative overflow-hidden border-t border-border py-20"
            style={{ backgroundColor: 'oklch(0.97 0.02 295)' }}>
      <div className="pointer-events-none absolute -left-32 -top-20 h-[400px] w-[400px] rounded-full blur-3xl"
           style={{ backgroundColor: 'color-mix(in oklch, var(--aria-primary) 10%, transparent)' }} />
      <div className="pointer-events-none absolute -right-32 bottom-0 h-[400px] w-[400px] rounded-full blur-3xl"
           style={{ backgroundColor: 'oklch(0.7 0.27 335 / 0.12)' }} />

      <Container className="relative">
        <div className="grid gap-12 lg:grid-cols-[1.4fr_0.8fr_0.8fr_1.1fr]">
          <div>
            <a href="https://genleadai.com" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl pill-gradient">
                <Sparkles className="h-5 w-5 text-white" />
              </div>
              <span className="font-display text-2xl font-extrabold tracking-tight text-foreground">
                GenLeadAI
              </span>
            </a>
            <p className="mt-5 max-w-sm text-sm leading-relaxed text-muted-foreground">
              GenLeadAI architects revenue systems — from market truth to sales continuity — for B2B
              and B2C companies that need clarity, structure, and pipeline that moves.
            </p>
            <div className="mt-5 inline-flex items-center gap-2 rounded-full border border-primary/30 bg-accent px-3 py-1.5 text-xs font-semibold text-primary">
              <Sparkles className="h-3.5 w-3.5" />
              Strategy-first revenue system architects
            </div>
            <div className="mt-6 flex gap-2.5">
              {[
                { Icon: Linkedin, href: 'https://linkedin.com/company/genleadai', label: 'LinkedIn' },
                { Icon: Instagram, href: '#', label: 'Instagram' },
                { Icon: Mail, href: 'mailto:meghaagarwal@genleadai.com', label: 'Email' },
              ].map(({ Icon, href, label }) => (
                <a
                  key={label}
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={label}
                  className="flex h-10 w-10 items-center justify-center rounded-full border border-border bg-card text-muted-foreground transition-all hover:-translate-y-0.5 hover:border-primary hover:text-primary"
                >
                  <Icon className="h-4 w-4" />
                </a>
              ))}
            </div>
          </div>

          <div>
            <ColLabel>Company</ColLabel>
            <ul className="mt-5 space-y-3 text-sm text-muted-foreground">
              {[
                { label: 'About', href: 'https://genleadai.com/about' },
                { label: 'Services', href: 'https://genleadai.com/services' },
                { label: 'Case Studies', href: 'https://genleadai.com/case-studies' },
                { label: 'Contact', href: 'https://genleadai.com/contact' },
              ].map((l) => (
                <li key={l.label}>
                  <a href={l.href} target="_blank" rel="noopener noreferrer" className="transition-colors hover:text-primary">
                    {l.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          <div className="space-y-8">
            <div>
              <ColLabel>Product</ColLabel>
              <ul className="mt-5 space-y-3 text-sm text-muted-foreground">
                <li><a href="#features" className="inline-flex items-center gap-2 transition-colors hover:text-primary">ARIA AI Sales PA</a></li>
                <li>
                  <a href="#signup" className="inline-flex items-center gap-2 transition-colors hover:text-primary">
                    Launch ARIA
                    <span className="rounded-full bg-accent px-1.5 py-0.5 text-[9px] font-bold tracking-wider text-primary">BETA</span>
                  </a>
                </li>
              </ul>
            </div>
            <div>
              <ColLabel>Resources</ColLabel>
              <ul className="mt-5 space-y-3 text-sm text-muted-foreground">
                <li><a href="https://genleadai.com" target="_blank" rel="noopener noreferrer" className="transition-colors hover:text-primary">Free Instant Audit</a></li>
                <li><a href="https://genleadai.com" target="_blank" rel="noopener noreferrer" className="transition-colors hover:text-primary">Lead Gen Playbook</a></li>
              </ul>
            </div>
          </div>

          <div>
            <ColLabel>Get in touch</ColLabel>
            <div className="mt-5 rounded-2xl border border-border bg-card p-5">
              <a href="mailto:meghaagarwal@genleadai.com" className="flex items-start gap-3 text-sm text-foreground transition-colors hover:text-primary">
                <Mail className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                <span className="break-all">meghaagarwal@genleadai.com</span>
              </a>
              <a href="tel:+917035303514" className="mt-3 flex items-center gap-3 text-sm text-foreground transition-colors hover:text-primary">
                <Phone className="h-4 w-4 shrink-0 text-primary" />
                +91 7035303514
              </a>
              <div className="mt-5 flex flex-col gap-2.5">
                <a
                  href="https://genleadai.com"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex w-full items-center justify-center gap-2 rounded-full pill-gradient pill-gradient-hover px-4 py-2.5 text-sm font-semibold text-white"
                >
                  Book Growth Audit <ArrowRight className="h-4 w-4" />
                </a>
                <a
                  href="https://wa.me/917035303514"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex w-full items-center justify-center gap-2 rounded-full px-4 py-2.5 text-sm font-semibold text-white transition-all hover:-translate-y-0.5"
                  style={{ backgroundColor: 'oklch(0.62 0.17 152)' }}
                >
                  <MessageCircle className="h-4 w-4" />
                  WhatsApp
                </a>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-16 border-t border-border pt-8">
          <p className="text-center font-display text-2xl font-extrabold tracking-tight md:text-3xl">
            GenLeadAI <span className="text-gradient">·</span> We Build Systems That Move Revenue.
          </p>
        </div>

        <div className="mt-8 flex flex-col items-start justify-between gap-3 text-xs text-muted-foreground sm:flex-row sm:items-center">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span>© 2026 GenLeadAI. All rights reserved.</span>
            <span className="hidden sm:inline">·</span>
            <a href="https://genleadai.com" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 font-semibold text-primary hover:underline">
              genleadai.com <ExternalLink className="h-3 w-3" />
            </a>
          </div>
          <div className="flex gap-5">
            <a href="/privacy" className="hover:text-foreground">Privacy Policy</a>
            <a href="/terms" className="hover:text-foreground">Terms of Service</a>
          </div>
        </div>
      </Container>
    </footer>
  );
}

function FloatingBot({ onSignup }) {
  const [open, setOpen] = useState(false);
  const [paused, setPaused] = useState(false);
  const [vw, setVw] = useState(1200);
  const [vh, setVh] = useState(800);
  const BOT = 150;
  const M = 16;

  const [target, setTarget] = useState({ x: 800, y: 600, dur: 4, flip: -1 });
  const prevX = useState({ v: 800 })[0];

  useEffect(() => {
    const update = () => {
      setVw(window.innerWidth);
      setVh(window.innerHeight);
    };
    update();
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, []);

  const pickNext = () => {
    const maxX = Math.max(M, vw - BOT - M);
    const maxY = Math.max(M, vh - BOT - M);
    const nx = M + Math.random() * (maxX - M);
    const ny = M + Math.random() * (maxY - M);
    const dx = Math.abs(nx - prevX.v);
    const dur = Math.max(2.5, Math.min(7, dx / 180 + 2 + Math.random() * 2));
    const flip = nx < prevX.v ? -1 : 1;
    prevX.v = nx;
    setTarget({ x: nx, y: ny, dur, flip });
  };

  useEffect(() => {
    if (vw && vh) pickNext();
  }, [vw, vh]);

  return (
    <motion.div
      className="fixed left-0 top-0 z-[60] hidden sm:block"
      style={{ width: BOT, height: BOT }}
      initial={{ x: vw - BOT - M, y: vh - BOT - M }}
      animate={paused || open ? {} : { x: target.x, y: target.y }}
      transition={{ duration: target.dur, ease: 'easeInOut' }}
      onAnimationComplete={() => {
        if (!paused && !open) pickNext();
      }}
      data-testid="floating-bot"
    >
      {open && (
        <motion.div
          initial={{ opacity: 0, y: 10, scale: 0.9 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          className="absolute -top-2 right-full mr-3 w-64 rounded-2xl border border-border bg-card p-4 shadow-2xl"
          style={{ boxShadow: '0 25px 50px -12px rgba(88, 28, 135, 0.20)' }}
        >
          <div className="text-xs font-semibold text-primary">ARIA · Sales Agent</div>
          <p className="mt-1 text-sm text-foreground">
            Hey 👋 I'm ARIA. Want me to scan a prospect for you right now?
          </p>
          <button
            type="button"
            onClick={() => onSignup?.()}
            className="mt-3 inline-flex items-center gap-1 rounded-full pill-gradient px-3 py-1.5 text-xs font-semibold text-white"
          >
            Try it free <ArrowRight className="h-3 w-3" />
          </button>
        </motion.div>
      )}
      <motion.button
        type="button"
        onClick={() => setOpen((o) => !o)}
        onMouseEnter={() => setPaused(true)}
        onMouseLeave={() => setPaused(false)}
        aria-label="Open ARIA chat"
        className="relative block rounded-full"
        style={{
          boxShadow: '0 0 40px rgba(168, 85, 247, 0.55)',
          outline: '4px solid rgba(168, 85, 247, 0.30)',
        }}
        animate={{ scaleX: target.flip }}
        transition={{ duration: 0.4 }}
        data-testid="floating-bot-btn"
      >
        <span className="absolute -inset-2 rounded-full blur-lg"
              style={{ backgroundColor: 'rgba(168, 85, 247, 0.20)' }} />
        <AriaBot size={BOT} withBubble={false} waving />
      </motion.button>
    </motion.div>
  );
}

export default function AriaLanding() {
  const navigate = useNavigate();
  const goSignup = (payload) => {
    // Push the form values into the existing /signup flow via query params so we
    // can pre-fill once that page supports it. Today they're harmless extras.
    const params = new URLSearchParams();
    if (payload?.email) params.set('email', payload.email);
    if (payload?.mode) params.set('mode', payload.mode);
    const qs = params.toString();
    navigate(`/signup${qs ? `?${qs}` : ''}`);
  };
  const goLogin = () => navigate('/login');

  // SEO meta
  useEffect(() => {
    const prevTitle = document.title;
    document.title = 'ARIA by GenLeadAI — AI Sales Intelligence & Automation';
    const meta = document.querySelector('meta[name="description"]');
    const prevDesc = meta?.getAttribute('content') || '';
    if (meta) {
      meta.setAttribute(
        'content',
        'ARIA crawls every signal across LinkedIn, news, and 15+ lead platforms. B2B: know when to strike. B2C: full autonomous lead handling.'
      );
    }
    return () => {
      document.title = prevTitle;
      if (meta && prevDesc) meta.setAttribute('content', prevDesc);
    };
  }, []);

  return (
    <div className="aria-landing min-h-screen" data-testid="aria-landing-root">
      <Nav onSignup={() => goSignup()} onLogin={goLogin} />
      <Hero onSignup={goSignup} />
      <Marquee />
      <TwoModes />
      <HowItWorks />
      <Comparison />
      <WhoItsFor />
      <Testimonials />
      <Integrations />
      <FAQ />
      <CTABand onSignup={goSignup} />
      <Footer />
      <FloatingBot onSignup={() => goSignup()} />
    </div>
  );
}
