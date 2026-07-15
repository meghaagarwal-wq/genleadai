/**
 * AriaCompanionDrawer — iter164
 * ─────────────────────────────────────────────────────────────────────
 * A persistent, ChatGPT-style companion drawer that lives on the right
 * edge of every workspace page. It's ARIA's "friend on the right":
 *   • Pulsing floating orb bottom-right (Notion-calm, coral accent)
 *   • Cmd+J / Ctrl+J opens the drawer instantly
 *   • Inside: brief "Aria noticed / drafted / suggests" cards driven off
 *     the tenant's founder-command-center intelligence data
 *   • Each card has a subtle color accent (coral = noticed, green =
 *     drafted, primary green = suggested) matching the iter163 palette
 *   • The drawer is dismissible; state persists in localStorage under
 *     `aria.companion.open` so returning founders see it in their last
 *     preferred position
 *
 * Wow-factor: this is what turns a first-time visitor into an obsessed
 * daily user. ARIA feels like a collaborator, not a dashboard.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Sparkle, X as XIcon, Command, Lightbulb, Warning, EnvelopeSimple,
  ArrowRight, Robot,
} from '@phosphor-icons/react';
import { useNavigate } from 'react-router-dom';
import api from '../config/api';

const STORAGE_KEY = 'aria.companion.open';

const CARD_TYPES = {
  noticed:   { label: 'Aria noticed',   color: 'var(--theme-secondary)',   icon: Warning },
  drafted:   { label: 'Aria drafted',   color: 'var(--theme-primary-light)', icon: EnvelopeSimple },
  suggests:  { label: 'Aria suggests',  color: 'var(--theme-primary)',      icon: Lightbulb },
};

/** Small pill "Aria noticed" style header inside each card */
const CardHeader = ({ type }) => {
  const t = CARD_TYPES[type] || CARD_TYPES.suggests;
  const Icon = t.icon;
  return (
    <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-[0.14em]"
         style={{ color: t.color }}>
      <Icon size={12} weight="fill" />
      {t.label}
    </div>
  );
};

const Card = ({ type, title, body, cta, onCta, testid }) => {
  const t = CARD_TYPES[type] || CARD_TYPES.suggests;
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.24, ease: [0.2, 0.8, 0.2, 1] }}
      className="rounded-2xl border p-4 space-y-2"
      style={{
        background: 'var(--theme-surface)',
        borderColor: 'var(--theme-border)',
        boxShadow: '0 1px 3px rgba(28,25,23,0.04)',
        borderLeft: `3px solid ${t.color}`,
      }}
      data-testid={testid}
    >
      <CardHeader type={type} />
      <div className="text-sm font-semibold leading-snug" style={{ color: 'var(--theme-text)', fontFamily: 'var(--font-display)' }}>
        {title}
      </div>
      {body && (
        <div className="text-xs leading-relaxed" style={{ color: 'var(--theme-text-muted)' }}>
          {body}
        </div>
      )}
      {cta && (
        <button
          onClick={onCta}
          data-testid={`${testid}-cta`}
          className="inline-flex items-center gap-1 text-xs font-semibold hover:underline"
          style={{ color: t.color }}
        >
          {cta} <ArrowRight size={11} weight="bold" />
        </button>
      )}
    </motion.div>
  );
};

/** Empty state — friendly & founder-calm */
const EmptyState = () => (
  <div className="text-center py-12 px-4">
    <div className="mx-auto w-14 h-14 rounded-full flex items-center justify-center mb-3"
         style={{ background: 'var(--theme-primary-dim)', color: 'var(--theme-primary)' }}>
      <Robot size={28} weight="duotone" />
    </div>
    <div className="text-sm font-semibold" style={{ color: 'var(--theme-text)', fontFamily: 'var(--font-display)' }}>
      All caught up.
    </div>
    <div className="text-xs mt-1" style={{ color: 'var(--theme-text-muted)' }}>
      I'll ping you the moment something needs attention.
    </div>
  </div>
);

/** Build cards from the founder-command-center payload */
const buildCards = (fcc, navigate) => {
  if (!fcc) return [];
  const cards = [];

  // Card 1 — Aria noticed: pipeline risk
  if (fcc.revenue_leakage?.score_pct > 0) {
    cards.push({
      type: 'noticed',
      title: fcc.revenue_leakage.headline || `${fcc.revenue_leakage.score_pct}% of pipeline at risk.`,
      body: fcc.revenue_leakage.subhead,
      cta: 'Show me the leaks',
      onCta: () => navigate('/app/instinct'),
      testid: 'aria-card-noticed-leakage',
    });
  }

  // Card 2 — Aria drafted: any recent draft
  const draftCount =
    (fcc.aria_activity?.drafts_ready || 0) ||
    (fcc.aria_time_saved?.drafts_written || 0);
  if (draftCount > 0) {
    cards.push({
      type: 'drafted',
      title: `${draftCount} outreach draft${draftCount === 1 ? '' : 's'} ready for review.`,
      body: 'I wrote them in your tone. One click to send.',
      cta: 'Review drafts',
      onCta: () => navigate('/app/approvals'),
      testid: 'aria-card-drafted',
    });
  }

  // Card 3 — Aria suggests: the top action
  const topAction = fcc.top_actions?.[0] || fcc.action_of_the_day;
  if (topAction) {
    cards.push({
      type: 'suggests',
      title: topAction.title || topAction.headline || topAction.action,
      body: topAction.rationale || topAction.reason || topAction.subtitle,
      cta: 'Do it now',
      onCta: () => navigate(topAction.link || '/app'),
      testid: 'aria-card-suggests-top',
    });
  }

  // Card 4 — Aria suggests: overdue follow-ups (from breakdown)
  const overdueRow = fcc.revenue_leakage?.breakdown?.find(b => b.key === 'overdue');
  if (overdueRow && overdueRow.count > 0) {
    cards.push({
      type: 'suggests',
      title: `${overdueRow.count} follow-ups are overdue.`,
      body: 'Batch-send a soft nudge — I can auto-draft in your voice.',
      cta: 'Open follow-ups',
      onCta: () => navigate('/app/conversations'),
      testid: 'aria-card-suggests-overdue',
    });
  }

  return cards;
};

const AriaCompanionDrawer = () => {
  const navigate = useNavigate();
  const [open, setOpen] = useState(() => {
    try { return localStorage.getItem(STORAGE_KEY) === '1'; } catch { return false; }
  });
  const [fcc, setFcc] = useState(null);
  const [loading, setLoading] = useState(false);
  const [hasNew, setHasNew] = useState(false);
  const firstLoadRef = useRef(true);

  // Persist open state
  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, open ? '1' : '0'); } catch (_e) { /* ignore */ }
    // On open, clear "new" indicator
    if (open) setHasNew(false);
  }, [open]);

  // Load founder-command-center data (used to build cards)
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/api/insights/founder-command-center');
      setFcc(data);
      // Blip the pulse if there's actionable content on next open
      if (!firstLoadRef.current && (data?.revenue_leakage?.score_pct > 0)) {
        setHasNew(true);
      }
      firstLoadRef.current = false;
    } catch (_e) {
      // silent — this drawer is best-effort
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    // Refresh every 5 minutes so the founder sees fresh insights
    const id = setInterval(load, 5 * 60 * 1000);
    // Also refresh on tenant switch
    const onTenant = () => load();
    window.addEventListener('aria:tenant-changed', onTenant);
    return () => { clearInterval(id); window.removeEventListener('aria:tenant-changed', onTenant); };
  }, [load]);

  // Cmd/Ctrl + J shortcut
  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'j') {
        e.preventDefault();
        setOpen((o) => !o);
      } else if (e.key === 'Escape' && open) {
        setOpen(false);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open]);

  const cards = useMemo(() => buildCards(fcc, navigate), [fcc, navigate]);

  return (
    <>
      {/* Floating orb trigger */}
      <button
        onClick={() => setOpen((o) => !o)}
        data-testid="aria-drawer-toggle"
        aria-label={open ? 'Close ARIA companion' : 'Open ARIA companion'}
        title="ARIA companion · Cmd+J"
        className="fixed bottom-6 right-6 z-40 h-14 w-14 rounded-full flex items-center justify-center text-white transition-transform hover:scale-105 active:scale-95"
        style={{
          background: 'var(--theme-primary)',
          boxShadow: '0 10px 30px rgba(15,76,58,0.35), 0 4px 12px rgba(15,76,58,0.2)',
        }}
      >
        {/* subtle pulse ring when new insights present */}
        {hasNew && !open && (
          <span
            className="absolute inset-0 rounded-full aria-pulse-ring"
            aria-hidden="true"
          />
        )}
        <Sparkle size={22} weight="fill" />
      </button>

      {/* Drawer */}
      <AnimatePresence>
        {open && (
          <>
            {/* Overlay */}
            <motion.div
              key="aria-overlay"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-0 z-40"
              style={{ background: 'rgba(28,25,23,0.20)', backdropFilter: 'blur(4px)' }}
              onClick={() => setOpen(false)}
              data-testid="aria-drawer-overlay"
            />

            {/* Panel */}
            <motion.aside
              key="aria-panel"
              initial={{ x: '100%' }}
              animate={{ x: 0 }}
              exit={{ x: '100%' }}
              transition={{ duration: 0.32, ease: [0.32, 0.72, 0, 1] }}
              className="fixed top-0 right-0 bottom-0 z-50 w-full max-w-[400px] flex flex-col"
              style={{
                background: 'var(--theme-surface)',
                borderLeft: '1px solid var(--theme-border)',
                boxShadow: 'var(--shadow-drawer)',
              }}
              data-testid="aria-companion-drawer"
              role="dialog"
              aria-label="ARIA companion"
            >
              {/* Header */}
              <div className="flex items-center justify-between px-5 py-4 border-b" style={{ borderColor: 'var(--theme-border)' }}>
                <div className="flex items-center gap-3">
                  <div
                    className="h-9 w-9 rounded-full flex items-center justify-center text-white"
                    style={{ background: 'var(--theme-primary)' }}
                  >
                    <Sparkle size={16} weight="fill" />
                  </div>
                  <div>
                    <div className="text-sm font-bold" style={{ color: 'var(--theme-text)', fontFamily: 'var(--font-display)' }}>ARIA</div>
                    <div className="text-[10px] uppercase tracking-[0.14em]" style={{ color: 'var(--theme-text-muted)' }}>
                      Your AI companion
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className="hidden sm:inline-flex items-center gap-1 text-[10px] px-2 py-1 rounded-md font-semibold"
                    style={{ background: 'var(--theme-surface2)', color: 'var(--theme-text-muted)' }}
                    title="Keyboard shortcut"
                  >
                    <Command size={10} weight="bold" /> J
                  </span>
                  <button
                    onClick={() => setOpen(false)}
                    aria-label="Close"
                    data-testid="aria-drawer-close"
                    className="p-1.5 rounded-md hover:bg-[var(--theme-surface2)] transition-colors"
                    style={{ color: 'var(--theme-text-muted)' }}
                  >
                    <XIcon size={16} weight="bold" />
                  </button>
                </div>
              </div>

              {/* Cards feed */}
              <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
                {loading && cards.length === 0 && (
                  <div className="text-center py-12 text-xs" style={{ color: 'var(--theme-text-muted)' }}>
                    ARIA is thinking…
                  </div>
                )}
                {!loading && cards.length === 0 && <EmptyState />}
                <AnimatePresence>
                  {cards.map((c, i) => (
                    <Card
                      key={c.testid || i}
                      type={c.type}
                      title={c.title}
                      body={c.body}
                      cta={c.cta}
                      onCta={() => { c.onCta && c.onCta(); setOpen(false); }}
                      testid={c.testid || `aria-card-${i}`}
                    />
                  ))}
                </AnimatePresence>
              </div>

              {/* Footer hint */}
              <div className="px-5 py-3 border-t text-[11px] leading-snug" style={{ borderColor: 'var(--theme-border)', color: 'var(--theme-text-muted)' }}>
                I refresh every 5 minutes. Press <strong style={{ color: 'var(--theme-text)' }}>Cmd+J</strong> anytime to bring me back.
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
};

export default AriaCompanionDrawer;
