import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../config/api';
import { toast } from 'sonner';
import { CheckCircle, X as XIcon, Crown, Sparkle, ArrowRight, Star, Receipt } from '@phosphor-icons/react';
import PageHeader from '../components/PageHeader';

/**
 * Billing — DIY / DWY / DFY pricing with 14-day trial.
 *
 * Replaces the legacy Starter/Pro/Growth/Custom Stripe-only model.
 */
const Billing = () => {
  const [plans, setPlans] = useState([]);
  const [status, setStatus] = useState(null);
  const [selecting, setSelecting] = useState(null);

  useEffect(() => {
    Promise.all([
      api.get('/api/plans/catalog').then((r) => setPlans(r.data?.plans || [])),
      api.get('/api/plans/status').then((r) => setStatus(r.data)),
    ]).catch(() => {});
  }, []);

  const selectPlan = async (plan) => {
    if (plan.id === 'dfy') {
      // Talk-to-us path
      try {
        await api.post('/api/plans/contact-sales', { note: 'Clicked from billing page' });
      } catch {}
      window.location.href = `mailto:${plan.contact_email || 'support@genleadai.com'}?subject=DFY%20Plan%20Inquiry%20%E2%80%94%20${encodeURIComponent(status?.plan_meta?.name || '')}`;
      return;
    }
    setSelecting(plan.id);
    try {
      const r = await api.post('/api/plans/select', { plan_id: plan.id });
      setStatus((s) => ({ ...s, plan: r.data.plan, locked: false, on_trial: false }));
      toast.success(`You're on ${plan.name}`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Could not select plan');
    } finally {
      setSelecting(null);
    }
  };

  const isCurrentPlan = (pid) => status?.plan === pid;

  return (
    <div className="space-y-6" data-testid="billing-page">
      <PageHeader
        eyebrow="ARIA Plans"
        title="Choose your sales operating layer"
        subtitle="Pick the plan that fits your team's growth stage. Every plan begins with a 14-day free trial."
        actions={
          <div className="flex items-center gap-2">
            <Link
              to="/billing/invoices"
              data-testid="view-invoices-link"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-slate-700 text-xs font-semibold uppercase tracking-wider hover:bg-slate-50 hover:border-slate-300 transition-colors"
            >
              <Receipt size={12} weight="duotone" /> Tax invoices
            </Link>
            {status && (
              <div
                data-testid="current-plan-pill"
                className="px-3 py-1.5 rounded-lg border border-[#7C35DC]/30 bg-[#F4F0FF] text-[#7C35DC] text-xs font-bold uppercase tracking-wider"
              >
                {status.plan === 'trial' ? `Trial · ${status.trial_days_left ?? 0}d left` : `You're on ${status.plan_meta?.name || status.plan}`}
              </div>
            )}
          </div>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {plans.map((plan) => {
          const isCurrent = isCurrentPlan(plan.id);
          const isDwy = plan.id === 'dwy';
          const isDfy = plan.id === 'dfy';
          const borderStyle = isDfy
            ? { borderImage: 'linear-gradient(135deg, #4F8EF7, #E2B96F) 1', borderWidth: '2px', borderStyle: 'solid' }
            : isDwy
              ? { borderColor: '#E2B96F', borderWidth: '2px', borderStyle: 'solid' }
              : { borderColor: '#4F8EF7', borderWidth: '2px', borderStyle: 'solid' };
          return (
            <div
              key={plan.id}
              data-testid={`plan-card-${plan.id}`}
              className="relative bg-white rounded-2xl p-6 transition-all hover:shadow-xl"
              style={{ ...borderStyle, boxShadow: 'var(--shadow-card)' }}
            >
              {isDwy && (
                <div className="absolute -top-3 left-6 px-3 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider text-[#1F1305]" style={{ background: '#E2B96F' }}>
                  <Star size={10} weight="fill" className="inline mr-1 -mt-0.5" /> Most Popular
                </div>
              )}
              {isDfy && (
                <div className="absolute -top-3 left-6 px-3 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider text-white" style={{ background: 'linear-gradient(135deg, #4F8EF7, #E2B96F)' }}>
                  <Crown size={10} weight="fill" className="inline mr-1 -mt-0.5" /> Managed
                </div>
              )}

              <div className="flex items-center gap-2 mb-2">
                <h3 className="text-2xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{plan.name}</h3>
                <span className="text-xs text-[#9B8AB0] uppercase tracking-[0.16em] font-bold">{plan.tagline}</span>
              </div>
              <p className="text-sm text-[#5A4A7A] mb-4 italic">{plan.subtitle}</p>

              <div className="mb-4">
                <div className="text-3xl font-extrabold text-[#1A0A2E]" data-testid={`plan-price-${plan.id}`}>{plan.price_label}</div>
              </div>

              <ul className="space-y-2 mb-5 min-h-[280px]">
                {plan.features.map((f, i) => (
                  <li key={`f-${i}`} className="flex items-start gap-2 text-xs text-[#1A0A2E]">
                    <CheckCircle size={13} className="text-[#16A34A] mt-0.5 flex-shrink-0" weight="fill" />
                    <span>{f}</span>
                  </li>
                ))}
                {plan.excluded.map((f, i) => (
                  <li key={`x-${i}`} className="flex items-start gap-2 text-xs text-[#9B8AB0]">
                    <XIcon size={13} className="text-[#D4C5E8] mt-0.5 flex-shrink-0" />
                    <span className="line-through">{f}</span>
                  </li>
                ))}
              </ul>

              {isCurrent ? (
                <button
                  disabled
                  data-testid={`plan-current-${plan.id}`}
                  className="w-full py-3 rounded-lg bg-[#F4F0FF] text-[#7C35DC] text-sm font-bold cursor-default"
                >
                  Current plan
                </button>
              ) : (
                <button
                  onClick={() => selectPlan(plan)}
                  disabled={selecting === plan.id}
                  data-testid={`plan-cta-${plan.id}`}
                  className="w-full flex items-center justify-center gap-1.5 py-3 rounded-lg text-white text-sm font-bold disabled:opacity-50"
                  style={{ background: isDfy ? 'linear-gradient(135deg, #4F8EF7, #E2B96F)' : isDwy ? '#1A1A2E' : 'linear-gradient(135deg, #4C1D95, #7C35DC)' }}
                >
                  {selecting === plan.id ? 'Loading…' : <>{plan.cta} <ArrowRight size={13} weight="bold" /></>}
                </button>
              )}
            </div>
          );
        })}
      </div>

      <p className="text-xs text-[#9B8AB0] text-center" data-testid="trial-disclaimer">
        All plans begin with a 14-day free trial. No credit card required to start.
      </p>

      <div className="bg-[#F9F5FF] border border-[#7C35DC]/20 rounded-2xl p-5 text-center text-xs text-[#5A4A7A]">
        Need help deciding?{' '}
        <a href="mailto:support@genleadai.com" className="font-bold text-[#7C35DC] hover:underline">Email support@genleadai.com</a>{' '}
        and we'll walk you through it.
      </div>
    </div>
  );
};

export default Billing;
