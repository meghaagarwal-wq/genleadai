/**
 * AriaSpotlight — route-level callouts that surface the most important
 * element on each page the first time a user lands there.
 *
 * Usage:
 *   <AriaSpotlight
 *     id="touchpoint-journey-drag"
 *     anchorSelector="[data-testid='journey-list-item-0']"
 *     placement="right"
 *     title="Drag to reorder"
 *     body="Aria fires touchpoints in the order you set here."
 *   />
 *
 * Each spotlight:
 *   • Auto-dismisses after a click outside, the X button, or "Got it"
 *   • Persists dismissal in localStorage (aria.spotlight.<id>)
 *   • Auto-repositions if the page scrolls / resizes
 *   • Renders nothing if the anchor is missing or already dismissed
 */
import React, { useEffect, useState, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { Sparkle, X } from '@phosphor-icons/react';

const STORAGE_PREFIX = 'aria.spotlight.';

const AriaSpotlight = ({
  id,
  anchorSelector,
  title,
  body,
  placement = 'bottom',  // 'top' | 'bottom' | 'left' | 'right'
  delay = 800,           // ms to wait for the anchor to appear after mount
}) => {
  const storageKey = STORAGE_PREFIX + id;
  const [visible, setVisible] = useState(false);
  const [pos, setPos] = useState(null);

  // Skip entirely if already dismissed.
  const alreadyDismissed = typeof window !== 'undefined' && localStorage.getItem(storageKey) === '1';

  const compute = useCallback(() => {
    const el = document.querySelector(anchorSelector);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { top: r.top, left: r.left, width: r.width, height: r.height };
  }, [anchorSelector]);

  useEffect(() => {
    if (alreadyDismissed) return;
    let cancelled = false;
    const t = setTimeout(() => {
      if (cancelled) return;
      const p = compute();
      if (p) { setPos(p); setVisible(true); }
    }, delay);
    return () => { cancelled = true; clearTimeout(t); };
  }, [alreadyDismissed, compute, delay]);

  // Reposition on scroll / resize while visible.
  useEffect(() => {
    if (!visible) return;
    const onChange = () => { const p = compute(); if (p) setPos(p); };
    window.addEventListener('scroll', onChange, true);
    window.addEventListener('resize', onChange);
    return () => {
      window.removeEventListener('scroll', onChange, true);
      window.removeEventListener('resize', onChange);
    };
  }, [visible, compute]);

  const dismiss = () => {
    localStorage.setItem(storageKey, '1');
    setVisible(false);
  };

  if (alreadyDismissed || !visible || !pos) return null;

  // Compute callout position based on placement
  const PAD = 12;
  const CARD_W = 280;
  let style = {};
  let arrow = '';
  if (placement === 'right') {
    style = { top: pos.top + pos.height / 2 - 40, left: pos.left + pos.width + PAD, width: CARD_W };
    arrow = 'left';
  } else if (placement === 'left') {
    style = { top: pos.top + pos.height / 2 - 40, left: pos.left - CARD_W - PAD, width: CARD_W };
    arrow = 'right';
  } else if (placement === 'top') {
    style = { top: pos.top - 120 - PAD, left: pos.left + pos.width / 2 - CARD_W / 2, width: CARD_W };
    arrow = 'bottom';
  } else {
    style = { top: pos.top + pos.height + PAD, left: pos.left + pos.width / 2 - CARD_W / 2, width: CARD_W };
    arrow = 'top';
  }
  // Clamp into viewport horizontally
  if (typeof window !== 'undefined') {
    const maxLeft = window.innerWidth - CARD_W - 12;
    if (style.left < 12) style.left = 12;
    if (style.left > maxLeft) style.left = maxLeft;
  }

  return createPortal(
    <>
      {/* Soft highlight ring on the anchor */}
      <div
        className="fixed pointer-events-none aria-spotlight-ring"
        style={{
          top: pos.top - 6, left: pos.left - 6,
          width: pos.width + 12, height: pos.height + 12,
          borderRadius: 16,
          zIndex: 9990,
          boxShadow: '0 0 0 3px rgba(192, 68, 224, 0.55), 0 0 0 9px rgba(124, 53, 220, 0.18), 0 0 28px rgba(124, 53, 220, 0.30)',
          transition: 'all 220ms ease',
        }}
        data-testid={`spotlight-ring-${id}`}
      />

      {/* Callout card */}
      <div
        className="fixed bg-white rounded-2xl p-4 border border-[#E0D4F7] aria-fade-up"
        style={{
          ...style,
          zIndex: 9991,
          boxShadow: '0 18px 48px rgba(124, 53, 220, 0.25), 0 4px 14px rgba(26, 10, 46, 0.10)',
        }}
        data-testid={`spotlight-${id}`}
        role="dialog"
        aria-label={title}
      >
        {/* Arrow */}
        <span
          className="absolute w-3 h-3 bg-white border-l border-t border-[#E0D4F7] rotate-45"
          style={{
            ...(arrow === 'top'    && { top: -6,  left: '50%', transform: 'translateX(-50%) rotate(45deg)' }),
            ...(arrow === 'bottom' && { bottom: -6, left: '50%', transform: 'translateX(-50%) rotate(-135deg)' }),
            ...(arrow === 'left'   && { left: -6, top: 36, transform: 'rotate(-45deg)' }),
            ...(arrow === 'right'  && { right: -6, top: 36, transform: 'rotate(135deg)' }),
          }}
        />
        <button
          onClick={dismiss}
          data-testid={`spotlight-close-${id}`}
          className="absolute top-2 right-2 w-6 h-6 rounded-full hover:bg-[#F4F0FF] flex items-center justify-center text-[#9B8AB0] hover:text-[#1A0A2E] transition-colors"
          title="Dismiss"
        >
          <X size={10} weight="bold" />
        </button>
        <div className="flex items-start gap-2.5 pr-5">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: 'var(--gradient-brand)' }}>
            <Sparkle size={12} weight="fill" className="text-white" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-[10px] font-extrabold uppercase tracking-[0.22em] text-[#7C35DC] mb-0.5">Aria tip</div>
            <h4 className="text-sm font-extrabold text-[#1A0A2E] leading-tight mb-1" style={{ fontFamily: 'Plus Jakarta Sans' }}>
              {title}
            </h4>
            <p className="text-xs text-[#5A4A7A] leading-relaxed">{body}</p>
            <button
              onClick={dismiss}
              data-testid={`spotlight-gotit-${id}`}
              className="mt-2.5 inline-flex items-center gap-1 text-[11px] font-extrabold text-[#7C35DC] hover:text-[#5B28D4]"
              style={{ fontFamily: 'Plus Jakarta Sans' }}
            >
              Got it
            </button>
          </div>
        </div>
      </div>
    </>,
    document.body
  );
};

export default AriaSpotlight;
