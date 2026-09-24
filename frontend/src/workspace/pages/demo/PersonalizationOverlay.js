/**
 * PersonalizationOverlay — iter173
 *
 * Entry moment for /aria-demo when no `?company=` deep-link is provided.
 * Prospect pastes a website / LinkedIn URL, we call /api/enrich, and
 * show a theatrical "ARIA is analysing…" scan overlay while we swap in
 * a fully personalised demo. Everything is bulletproof: the animation
 * always completes, enrichment failures fall through to a graceful
 * domain-derived profile, and the badge stays "Live demo · sample data".
 */
import React, { useEffect, useRef, useState } from 'react';
import { Sparkles, ArrowRight, Loader2, Globe, CheckCircle2, X } from 'lucide-react';
import { SAMPLE_COMPANIES } from '../../demoData/liveContent';

const SCAN_STEPS = [
  'Reading your site…',
  'Inferring your ICP…',
  'Mapping likely channels…',
  'Scanning for buying signals…',
  'Building your Command Center…',
];

export default function PersonalizationOverlay({ open, onCancel, onComplete, apiUrl, T }) {
  const [phase, setPhase]     = useState('input');   // 'input' | 'scanning' | 'done'
  const [domain, setDomain]   = useState('');
  const [stepIdx, setStepIdx] = useState(0);
  const enrichmentRef = useRef(null);
  const doneRef       = useRef(false);

  useEffect(() => {
    if (!open) {
      setPhase('input'); setDomain(''); setStepIdx(0);
      enrichmentRef.current = null; doneRef.current = false;
    }
  }, [open]);

  async function startScan(rawDomain) {
    if (!rawDomain || phase !== 'input') return;
    setPhase('scanning');
    setStepIdx(0);
    doneRef.current = false;

    // Start the animation — always runs to completion regardless of network.
    const totalMs = 4200;
    const perStep = totalMs / SCAN_STEPS.length;
    const startedAt = Date.now();
    const tick = () => {
      const elapsed = Date.now() - startedAt;
      const idx = Math.min(SCAN_STEPS.length - 1, Math.floor(elapsed / perStep));
      setStepIdx(idx);
      if (elapsed >= totalMs) {
        // Animation done — release control on next microtask.
        finalise();
      } else {
        requestAnimationFrame(tick);
      }
    };
    requestAnimationFrame(tick);

    // Fire enrichment in parallel — 4s hard timeout, graceful fallback.
    const ctrl = new AbortController();
    const timeout = setTimeout(() => ctrl.abort(), 4000);
    try {
      const res = await fetch(`${apiUrl}/api/enrich?domain=${encodeURIComponent(rawDomain)}`, {
        signal: ctrl.signal,
      });
      enrichmentRef.current = await res.json();
    } catch (e) {
      enrichmentRef.current = null; // triggers domain-only fallback below
    } finally {
      clearTimeout(timeout);
    }
  }

  // Sample click — skip live enrichment and play the scan with preset data.
  function pickSample(sample) {
    if (phase !== 'input') return;
    setDomain(sample.domain);
    enrichmentRef.current = {
      domain:      sample.domain,
      companyName: sample.companyName,
      tagline:     sample.tagline,
      logoUrl:     `https://www.google.com/s2/favicons?domain=${sample.domain}&sz=128`,
      keywords:    [sample.mode === 'b2b' ? 'saas' : sample.mode === 'b2c' ? 'skincare' : 'coffee'],
      mode:        sample.mode,
      source:      'sample',
    };
    setPhase('scanning');
    setStepIdx(0);
    doneRef.current = false;
    const totalMs = 3200; // shorter for pre-baked samples
    const perStep = totalMs / SCAN_STEPS.length;
    const startedAt = Date.now();
    const tick = () => {
      const elapsed = Date.now() - startedAt;
      const idx = Math.min(SCAN_STEPS.length - 1, Math.floor(elapsed / perStep));
      setStepIdx(idx);
      if (elapsed >= totalMs) finalise();
      else requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }

  function finalise() {
    if (doneRef.current) return;
    doneRef.current = true;
    setPhase('done');
    const payload = enrichmentRef.current || fallbackFromDomain(domain);
    // Give the "done" state a beat so the checkmark is felt.
    setTimeout(() => onComplete(payload), 320);
  }

  function fallbackFromDomain(raw) {
    const clean = raw.replace(/^https?:\/\//, '').replace(/^www\./, '').split('/')[0].toLowerCase();
    const root = clean.split('.')[0].replace(/-/g, ' ');
    const name = root.replace(/\b\w/g, (c) => c.toUpperCase()) || 'Your Company';
    return {
      domain:      clean,
      companyName: name,
      tagline:     null,
      logoUrl:     `https://www.google.com/s2/favicons?domain=${clean}&sz=128`,
      keywords:    [],
      source:      'fallback',
    };
  }

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center p-6"
      style={{ background: 'rgba(11,10,20,0.72)', backdropFilter: 'blur(12px)' }}
      data-testid="personalization-overlay"
    >
      <div
        className="relative w-full max-w-[560px] rounded-3xl overflow-hidden"
        style={{
          background: T.card, border: `1px solid ${T.line}`,
          boxShadow: '0 40px 120px rgba(124,53,220,0.28), 0 8px 32px rgba(0,0,0,0.4)',
        }}
      >
        {/* Ambient glow */}
        <div
          aria-hidden
          className="absolute -top-32 -right-32 w-80 h-80 rounded-full pointer-events-none"
          style={{ background: 'radial-gradient(closest-side, rgba(164,111,232,0.28), transparent 70%)' }}
        />

        {phase === 'input' && (
          <div className="relative p-8">
            <div className="flex items-center justify-between mb-6">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-[10px] uppercase tracking-[0.18em]"
                style={{ background: T.accentSoft, color: T.accent, fontWeight: 600 }}>
                <Sparkles size={11} /> Live demo · sample data
              </div>
              <button
                onClick={onCancel}
                className="w-8 h-8 rounded-full flex items-center justify-center transition-colors hover:bg-white/5"
                style={{ color: T.muted }}
                aria-label="Skip and use sample data"
                data-testid="overlay-skip"
              >
                <X size={16} />
              </button>
            </div>

            <h2
              className="text-[30px] leading-tight font-semibold tracking-tight"
              style={{ fontFamily: T.fontDisplay, color: T.ink, letterSpacing: '-0.02em' }}
            >
              See ARIA analyse{'\u00A0'}
              <span style={{ color: T.accent }}>your</span>{' '}company.
            </h2>
            <p className="text-sm mt-3" style={{ color: T.muted }}>
              Paste your website or LinkedIn URL. ARIA reads your site, infers your ICP,
              and rebuilds this dashboard around your business in six seconds.
            </p>

            <form
              className="mt-6"
              onSubmit={(e) => { e.preventDefault(); startScan(domain.trim()); }}
            >
              <label className="block relative">
                <span className="absolute left-4 top-1/2 -translate-y-1/2" style={{ color: T.muted }}>
                  <Globe size={16} />
                </span>
                <input
                  autoFocus
                  data-testid="overlay-domain-input"
                  type="text"
                  value={domain}
                  onChange={(e) => setDomain(e.target.value)}
                  placeholder="your-company.com"
                  className="w-full pl-11 pr-32 py-3.5 rounded-xl text-sm outline-none transition-colors"
                  style={{
                    background: T.canvas,
                    border: `1px solid ${T.line}`,
                    color: T.ink,
                  }}
                />
                <button
                  type="submit"
                  data-testid="overlay-analyse-btn"
                  disabled={!domain.trim()}
                  className="absolute right-1.5 top-1/2 -translate-y-1/2 px-4 py-2 rounded-lg text-sm font-semibold inline-flex items-center gap-1.5 transition-all disabled:opacity-40"
                  style={{ background: T.accent, color: '#fff' }}
                >
                  Analyse <ArrowRight size={14} strokeWidth={2.5} />
                </button>
              </label>
            </form>

            <div className="mt-8">
              <div className="text-[11px] uppercase tracking-[0.14em] mb-3" style={{ color: T.muted, fontWeight: 600 }}>
                or explore a sample
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                {SAMPLE_COMPANIES.map((s) => (
                  <button
                    key={s.domain}
                    onClick={() => pickSample(s)}
                    data-testid={`overlay-sample-${s.mode}`}
                    className="rounded-xl p-3 text-left transition-colors hover:border-white/20"
                    style={{ background: T.canvas, border: `1px solid ${T.line}`, color: T.ink }}
                  >
                    <div className="text-lg leading-none mb-1">{s.icon}</div>
                    <div className="text-sm font-semibold truncate">{s.companyName}</div>
                    <div className="text-[11px]" style={{ color: T.muted }}>{s.tagline}</div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {(phase === 'scanning' || phase === 'done') && (
          <div className="relative p-8 min-h-[360px] flex flex-col items-center justify-center text-center" data-testid="overlay-scan">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-[10px] uppercase tracking-[0.18em] mb-8"
              style={{ background: T.accentSoft, color: T.accent, fontWeight: 600 }}>
              <Sparkles size={11} /> Live demo · sample data
            </div>

            <div className="relative w-20 h-20 mb-6 flex items-center justify-center">
              <div className="absolute inset-0 rounded-full animate-ping"
                style={{ background: T.accent, opacity: 0.15 }} />
              <div className="absolute inset-2 rounded-full flex items-center justify-center"
                style={{ background: T.accentSoft, border: `1px solid ${T.line}` }}>
                {phase === 'done'
                  ? <CheckCircle2 size={28} style={{ color: T.success }} strokeWidth={2.2} />
                  : <Loader2 size={26} className="animate-spin" style={{ color: T.accent }} />}
              </div>
            </div>

            <div className="text-lg font-semibold tracking-tight" style={{ color: T.ink, fontFamily: T.fontDisplay }}>
              {phase === 'done' ? 'Ready.' : 'ARIA is analysing your business'}
            </div>
            <div className="text-sm mt-1" style={{ color: T.muted }}>
              {domain ? `Reading ${domain}` : 'Reading site…'}
            </div>

            <ul className="mt-8 space-y-2 text-left w-full max-w-[340px]">
              {SCAN_STEPS.map((s, i) => {
                const done    = i < stepIdx || phase === 'done';
                const current = i === stepIdx && phase === 'scanning';
                return (
                  <li key={s} className="flex items-center gap-3 text-sm" style={{ color: done ? T.ink : T.muted }}>
                    <span className="w-4 h-4 rounded-full flex items-center justify-center shrink-0"
                      style={{
                        background: done ? T.success : (current ? T.accent : T.line),
                      }}>
                      {done && <CheckCircle2 size={12} style={{ color: '#0B0A14' }} strokeWidth={3} />}
                    </span>
                    <span>{s}</span>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
