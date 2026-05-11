import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../config/api';
import { useAuth } from '../context/AuthContext';
import { Clock, ArrowRight, X } from '@phosphor-icons/react';

/**
 * TrialBanner — persistent top banner during trial / paywall when expired.
 *
 * - On active trial: gold banner "Your free trial ends in X days. Choose a plan."
 * - On expired trial w/ no plan: full-screen paywall (not dismissible).
 *
 * Retries on auth user change so a fresh signup picks up the trial state
 * once localStorage.active_tenant has been hydrated by the auth flow.
 */
const TrialBanner = () => {
  const { user } = useAuth();
  const [status, setStatus] = useState(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (!user) return;
    let alive = true;
    const fetchStatus = (attempt = 0) => {
      api.get('/api/plans/status')
        .then((r) => { if (alive) setStatus(r.data); })
        .catch((err) => {
          // Retry once if the first call fires before localStorage.active_tenant is hydrated.
          if (attempt === 0) {
            console.warn('[TrialBanner] status fetch failed, retrying once', err?.response?.status);
            setTimeout(() => fetchStatus(1), 800);
          } else {
            console.warn('[TrialBanner] giving up after retry', err?.response?.status);
          }
        });
    };
    fetchStatus();
    return () => { alive = false; };
  }, [user]);

  if (!status) return null;
  if (status.plan !== 'trial' || dismissed) return null;

  // Locked state — full screen paywall
  if (status.locked) {
    return <TrialPaywall status={status} />;
  }

  // Active trial — top banner
  const days = status.trial_days_left ?? 0;
  return (
    <div
      data-testid="trial-banner"
      className="w-full flex items-center justify-between gap-3 px-5 py-2.5 border-b"
      style={{ background: 'linear-gradient(90deg, #FCD34D, #E2B96F)', borderColor: '#B45309' }}
    >
      <div className="flex items-center gap-2 text-[#1F1305] text-sm font-semibold">
        <Clock size={14} weight="fill" />
        <span data-testid="trial-banner-text">
          Your free trial ends in <strong>{days}</strong> day{days === 1 ? '' : 's'}. Choose a plan to keep Aria running.
        </span>
      </div>
      <div className="flex items-center gap-2">
        <Link
          to="/billing"
          data-testid="trial-banner-upgrade"
          className="inline-flex items-center gap-1 px-3 py-1 rounded-md bg-[#0D0D1A] text-white text-xs font-bold tracking-wide hover:bg-[#1A1A2E]"
        >
          Upgrade now <ArrowRight size={11} weight="bold" />
        </Link>
        <button
          onClick={() => setDismissed(true)}
          data-testid="trial-banner-dismiss"
          className="p-1 rounded text-[#1F1305]/60 hover:text-[#1F1305]"
          title="Dismiss"
        >
          <X size={12} weight="bold" />
        </button>
      </div>
    </div>
  );
};

const TrialPaywall = ({ status }) => (
  <div
    data-testid="trial-paywall"
    className="fixed inset-0 z-[100] flex items-center justify-center p-4"
    style={{ background: 'rgba(13, 13, 26, 0.92)', backdropFilter: 'blur(8px)' }}
  >
    <div className="bg-white max-w-2xl w-full rounded-2xl p-8 text-center shadow-2xl">
      <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#FEF3C7] border border-[#F59E0B]/40 text-[#92400E] text-xs font-bold uppercase tracking-[0.18em] mb-4">
        <Clock size={12} weight="fill" /> Trial expired
      </div>
      <h2 className="text-3xl font-extrabold text-[#1A0A2E] mb-2">Your 14-day free trial has ended</h2>
      <p className="text-sm text-[#5A4A7A] mb-6">Choose a plan to keep Aria running, your leads moving, and your team logged in.</p>
      <Link
        to="/billing"
        data-testid="paywall-upgrade-cta"
        className="inline-flex items-center gap-1.5 px-6 py-3 rounded-lg text-white text-sm font-bold tracking-wide"
        style={{ background: 'linear-gradient(135deg, #4C1D95, #7C35DC)' }}
      >
        See plans <ArrowRight size={14} weight="bold" />
      </Link>
      <p className="text-[11px] text-[#A0A8C0] mt-6 tracking-[0.18em] uppercase font-bold">
        Powered by Aria · GenLeadAI
      </p>
    </div>
  </div>
);

export default TrialBanner;
