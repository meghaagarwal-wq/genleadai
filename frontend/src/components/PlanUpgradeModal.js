import React, { useState, useEffect } from 'react';
import { Crown, Check, X, ArrowRight, Sparkle, CurrencyInr } from '@phosphor-icons/react';
import { toast } from 'sonner';
import api from '../config/api';

/**
 * UpgradeModal — surfaced from any tier_limit_reached banner.
 *
 * Props:
 *   open: bool
 *   onClose: () => void
 *   targetPlan: 'dwy' | 'dfy' (default 'dwy')
 *   reason: short string describing why the user hit the upgrade prompt
 */
export default function UpgradeModal({ open, onClose, targetPlan = 'dwy', reason }) {
  const [packages, setPackages] = useState(null);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!open) return;
    let alive = true;
    api.get('/api/billing/upgrade-packages').then((r) => {
      if (alive) setPackages(r.data?.packages || {});
    }).catch(() => { if (alive) setPackages({}); });
    return () => { alive = false; };
  }, [open]);

  if (!open) return null;

  // Find best-fit package for the target plan.
  const candidates = Object.values(packages || {}).filter((p) => p.plan_target === targetPlan);

  const handleCheckout = async (packageId) => {
    setCreating(true);
    try {
      const r = await api.post('/api/billing/checkout/session', {
        package_id: packageId,
        origin_url: window.location.origin,
      });
      if (r.data?.url) window.location.href = r.data.url;
      else throw new Error('No checkout URL');
    } catch (e) {
      const detail = e?.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Could not start checkout');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div data-testid="upgrade-modal" className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-white rounded-3xl shadow-2xl max-w-lg w-full my-8 overflow-hidden">
        <div className="px-7 py-5 bg-gradient-to-br from-violet-600 to-indigo-700 text-white relative">
          <button type="button" onClick={onClose} className="absolute top-4 right-4 p-1.5 rounded-lg hover:bg-white/10">
            <X size={16} />
          </button>
          <div className="inline-flex items-center gap-1.5 text-xs font-semibold bg-white/15 px-2.5 py-1 rounded-full mb-3 uppercase tracking-wider">
            <Crown size={12} weight="fill" /> Upgrade required
          </div>
          <h2 className="text-2xl font-semibold leading-tight">Unlock unlimited {targetPlan === 'dfy' ? 'DFY' : 'DWY'} features</h2>
          {reason && <p className="text-sm text-violet-100 mt-2">{reason}</p>}
        </div>

        <div className="px-7 py-6">
          {packages === null ? (
            <div className="text-sm text-slate-400 text-center py-6">Loading plans…</div>
          ) : candidates.length === 0 ? (
            <div className="text-sm text-slate-500 text-center py-6">
              No upgrade path available right now.
            </div>
          ) : (
            <div className="space-y-3">
              {candidates.map((pkg) => (
                <div
                  key={pkg.package_id}
                  data-testid={`upgrade-package-${pkg.package_id}`}
                  className="border-2 border-violet-200 bg-gradient-to-br from-violet-50/40 to-white rounded-2xl p-5"
                >
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="min-w-0">
                      <h3 className="text-base font-semibold text-slate-900">{pkg.label}</h3>
                      <p className="text-xs text-slate-600 mt-1">{pkg.description}</p>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <div className="text-2xl font-semibold text-slate-900 flex items-center justify-end">
                        <CurrencyInr size={20} weight="bold" className="text-violet-600" />
                        {pkg.amount.toLocaleString('en-IN')}
                      </div>
                      <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">/ month</div>
                    </div>
                  </div>

                  <ul className="space-y-1 mb-4 text-xs text-slate-700">
                    {(pkg.plan_target === 'dwy' ? [
                      'Unlimited ICPs', 'Unlimited touchpoints', 'Multi-channel automation', 'Priority support',
                    ] : [
                      'Everything in DWY', 'Dedicated success manager', 'Custom integrations', 'White-glove onboarding',
                    ]).map((feat) => (
                      <li key={feat} className="flex items-center gap-2">
                        <Check size={12} weight="bold" className="text-emerald-600 flex-shrink-0" />
                        {feat}
                      </li>
                    ))}
                  </ul>

                  <button
                    type="button"
                    onClick={() => handleCheckout(pkg.package_id)}
                    disabled={creating}
                    data-testid={`upgrade-checkout-${pkg.package_id}`}
                    className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-slate-900 text-white text-sm font-semibold hover:bg-slate-800 disabled:opacity-50"
                  >
                    <Sparkle size={14} weight="fill" />
                    {creating ? 'Redirecting to Stripe…' : 'Upgrade now'}
                    <ArrowRight size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}
          <p className="text-[10px] text-slate-400 text-center mt-4">
            Secured by Stripe · Cancel anytime · GST invoice on every charge
          </p>
        </div>
      </div>
    </div>
  );
}
