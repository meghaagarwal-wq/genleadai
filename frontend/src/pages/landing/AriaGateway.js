/**
 * AriaGateway — iter171
 * ──────────────────────────────────────────────────────────
 * Replaces the old purple AriaLanding marketing page with a
 * calm, warm, single-purpose gateway: Sign in · Sign up · Book
 * a call. Full-viewport split layout matching the iter163 palette.
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkle, ArrowRight, LinkedinLogo, EnvelopeSimple, ChatCircleText, CheckCircle } from '@phosphor-icons/react';

const HIGHLIGHTS = [
  { icon: Sparkle,          text: 'Drafts every outreach in your voice · human-approved by default' },
  { icon: EnvelopeSimple,   text: 'Plugs into 54 tools — LinkedIn, Gmail, WhatsApp, Calendly, Stripe' },
  { icon: ChatCircleText,   text: 'Cmd+J opens ARIA anywhere in the app' },
  { icon: CheckCircle,      text: 'Tenant-isolated · audit-logged · SOC 2-ready' },
];

const AriaGateway = () => {
  const navigate = useNavigate();
  const [hover, setHover] = useState(null);

  const goto = (path) => navigate(path);

  return (
    <div
      className="min-h-screen w-full flex flex-col md:flex-row"
      style={{ background: 'var(--theme-bg, #FDFBF7)', color: 'var(--theme-text, #1C1917)', fontFamily: 'var(--font-sans, Manrope)' }}
      data-testid="aria-gateway"
    >
      {/* ── LEFT: Brand + Highlights ─────────────────────────────── */}
      <aside
        className="hidden md:flex md:w-1/2 flex-col justify-between p-10 lg:p-14 relative overflow-hidden"
        style={{ background: 'linear-gradient(180deg, #0F4C3A 0%, #1F6B5C 100%)', color: '#FDFBF7' }}
      >
        {/* Ambient glow */}
        <div className="absolute -top-40 -right-40 w-96 h-96 rounded-full aria-glow"
             style={{ background: 'radial-gradient(closest-side, rgba(224,109,83,0.25), transparent 70%)' }} />

        {/* Logo */}
        <div className="flex items-center gap-3 relative">
          <div className="w-10 h-10 rounded-full flex items-center justify-center" style={{ background: 'rgba(255,255,255,0.14)' }}>
            <Sparkle size={20} weight="fill" style={{ color: '#FDFBF7' }} />
          </div>
          <div>
            <div className="font-extrabold text-lg tracking-tight" style={{ fontFamily: 'var(--font-display, Outfit)', letterSpacing: '0.02em' }}>ARIA</div>
            <div className="text-[10px] uppercase tracking-[0.24em] opacity-70">GenLeadAI</div>
          </div>
        </div>

        {/* Hero copy */}
        <div className="relative">
          <div className="text-[10px] uppercase tracking-[0.28em] opacity-70 mb-4">Powered by ARIA · live</div>
          <h1 className="text-[44px] lg:text-[54px] leading-[1.05] font-semibold tracking-tight"
              style={{ fontFamily: 'var(--font-display, Outfit)' }}>
            The AI sales PA<br />that runs your pipeline<br />
            <span style={{ color: '#E06D53' }}>while you sleep.</span>
          </h1>
          <p className="mt-6 max-w-[440px] text-[15px] leading-relaxed opacity-85">
            She notices what you&apos;d miss. Drafts what you&apos;d write. Nudges what you&apos;d forget.
            And only wakes you when a deal needs a human.
          </p>

          <div className="mt-8 space-y-3 max-w-[440px]">
            {HIGHLIGHTS.map((h, i) => (
              <div key={i} className="flex items-start gap-3 text-sm opacity-90">
                <h.icon size={16} weight="duotone" style={{ color: '#E06D53', marginTop: 3, flexShrink: 0 }} />
                <span>{h.text}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Testimonial */}
        <div className="relative">
          <blockquote className="text-sm italic opacity-85 max-w-[440px] border-l-2 pl-4"
                      style={{ borderColor: '#E06D53' }}>
            &ldquo;I stopped chasing follow-ups the day ARIA arrived. Now I approve 20 drafts before 9am and my week is mine.&rdquo;
          </blockquote>
          <div className="mt-2 text-xs opacity-60">— Founder, mid-market SaaS</div>
        </div>
      </aside>

      {/* ── RIGHT: Action panel ─────────────────────────────────── */}
      <main className="flex-1 flex items-center justify-center p-8 lg:p-14">
        <div className="w-full max-w-[440px]">
          {/* Mobile logo */}
          <div className="md:hidden flex items-center gap-2 mb-8">
            <div className="w-9 h-9 rounded-full flex items-center justify-center" style={{ background: '#0F4C3A' }}>
              <Sparkle size={18} weight="fill" style={{ color: '#FDFBF7' }} />
            </div>
            <div>
              <div className="font-extrabold text-lg tracking-tight" style={{ fontFamily: 'var(--font-display, Outfit)' }}>ARIA</div>
              <div className="text-[10px] uppercase tracking-[0.2em]" style={{ color: 'var(--theme-text-muted, #57534E)' }}>GenLeadAI</div>
            </div>
          </div>

          <div className="text-[11px] uppercase tracking-[0.28em] mb-3" style={{ color: 'var(--theme-primary, #0F4C3A)', fontFamily: 'var(--font-display, Outfit)' }}>
            Start here
          </div>
          <h2 className="text-[32px] leading-tight font-semibold tracking-tight mb-2"
              style={{ fontFamily: 'var(--font-display, Outfit)', color: 'var(--theme-text, #1C1917)' }}>
            Pick your door.
          </h2>
          <p className="text-sm mb-8" style={{ color: 'var(--theme-text-muted, #57534E)' }}>
            Sign in to your workspace, start a fresh one, or book a founder-to-founder walkthrough.
          </p>

          {/* Primary — Sign in */}
          <button
            onClick={() => goto('/login')}
            onMouseEnter={() => setHover('login')}
            onMouseLeave={() => setHover(null)}
            data-testid="gateway-signin-btn"
            className="w-full mb-3 px-5 py-4 rounded-2xl flex items-center justify-between text-white font-semibold transition-all active:scale-[0.98]"
            style={{
              background: '#0F4C3A',
              boxShadow: hover === 'login' ? '0 12px 28px rgba(15,76,58,0.30)' : '0 6px 18px rgba(15,76,58,0.18)',
              transform: hover === 'login' ? 'translateY(-1px)' : 'translateY(0)',
              fontFamily: 'var(--font-display, Outfit)',
            }}
          >
            <span className="flex items-center gap-3">
              <span className="w-8 h-8 rounded-full flex items-center justify-center" style={{ background: 'rgba(255,255,255,0.14)' }}>
                <Sparkle size={14} weight="fill" />
              </span>
              <span>
                <span className="block text-[15px]">Sign in</span>
                <span className="block text-[11px] font-normal opacity-75">Existing workspace · admin login</span>
              </span>
            </span>
            <ArrowRight size={18} weight="bold" />
          </button>

          {/* Secondary — Sign up */}
          <button
            onClick={() => goto('/signup')}
            onMouseEnter={() => setHover('signup')}
            onMouseLeave={() => setHover(null)}
            data-testid="gateway-signup-btn"
            className="w-full mb-3 px-5 py-4 rounded-2xl flex items-center justify-between font-semibold border transition-all active:scale-[0.98]"
            style={{
              background: 'var(--theme-surface, #ffffff)',
              borderColor: hover === 'signup' ? '#0F4C3A' : 'var(--theme-border, #E7E5E4)',
              color: 'var(--theme-text, #1C1917)',
              boxShadow: hover === 'signup' ? '0 8px 22px rgba(28,25,23,0.08)' : '0 2px 8px rgba(28,25,23,0.04)',
              transform: hover === 'signup' ? 'translateY(-1px)' : 'translateY(0)',
              fontFamily: 'var(--font-display, Outfit)',
            }}
          >
            <span className="flex items-center gap-3">
              <span className="w-8 h-8 rounded-full flex items-center justify-center" style={{ background: 'var(--theme-primary-dim, rgba(15,76,58,0.10))', color: 'var(--theme-primary, #0F4C3A)' }}>
                <ArrowRight size={14} weight="bold" />
              </span>
              <span>
                <span className="block text-[15px]">Start a new workspace</span>
                <span className="block text-[11px] font-normal" style={{ color: 'var(--theme-text-muted, #57534E)' }}>5-min setup · trained on your site in the first hour</span>
              </span>
            </span>
            <ArrowRight size={18} weight="bold" style={{ color: 'var(--theme-text-muted, #57534E)' }} />
          </button>

          {/* Tertiary — Book a call */}
          <button
            onClick={() => goto('/apply')}
            onMouseEnter={() => setHover('call')}
            onMouseLeave={() => setHover(null)}
            data-testid="gateway-bookcall-btn"
            className="w-full px-5 py-4 rounded-2xl flex items-center justify-between font-semibold border-2 border-dashed transition-all active:scale-[0.98]"
            style={{
              background: 'transparent',
              borderColor: hover === 'call' ? '#E06D53' : 'var(--theme-border-strong, #D6D3D1)',
              color: hover === 'call' ? '#E06D53' : 'var(--theme-text, #1C1917)',
              fontFamily: 'var(--font-display, Outfit)',
            }}
          >
            <span className="flex items-center gap-3">
              <span className="w-8 h-8 rounded-full flex items-center justify-center"
                    style={{ background: 'rgba(224,109,83,0.12)', color: '#E06D53' }}>
                <ChatCircleText size={14} weight="fill" />
              </span>
              <span>
                <span className="block text-[15px]">Book a walkthrough</span>
                <span className="block text-[11px] font-normal" style={{ color: 'var(--theme-text-muted, #57534E)' }}>Founder-to-founder demo · 15 min · 48-hr response</span>
              </span>
            </span>
            <ArrowRight size={18} weight="bold" />
          </button>

          {/* Footer meta */}
          <div className="mt-8 pt-6 border-t flex items-center justify-between text-[11px]"
               style={{ borderColor: 'var(--theme-border, #E7E5E4)', color: 'var(--theme-text-muted, #57534E)' }}>
            <span>Human-in-the-loop by default</span>
            <span className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full" style={{ background: '#10B981' }} />
              Live · 99.5% uptime
            </span>
          </div>

          {/* Legal */}
          <div className="mt-4 text-[10px]" style={{ color: 'var(--theme-text-dim, #A8A29E)' }}>
            By continuing, you agree to our <a href="/terms" className="underline">Terms</a> · <a href="/privacy" className="underline">Privacy</a> · <a href="/dpa" className="underline">DPA</a>.
          </div>
        </div>
      </main>
    </div>
  );
};

export default AriaGateway;
