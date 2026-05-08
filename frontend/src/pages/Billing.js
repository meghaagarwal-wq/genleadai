import React, { useState, useEffect, useCallback } from 'react';
import { CheckCircle, X as XIcon, Sparkle, Crown, Rocket, Buildings, ArrowRight } from '@phosphor-icons/react';
import { usePlan } from '../context/PlanContext';
import api from '../config/api';
import { toast } from 'sonner';
import PageHeader from '../components/PageHeader';

const FEATURE_GROUPS = [
  {
    label: 'Core lead control',
    keys: [
      ['lead_inbox', 'Lead inbox & profiles'],
      ['manual_lead_entry', 'Manual lead entry'],
      ['follow_up_reminders', 'Follow-up reminders'],
      ['source_tagging', 'Source tagging'],
      ['manual_temperature', 'Manual Hot/Warm/Cold tagging'],
      ['daily_task_list', 'Daily task list'],
      ['basic_reports', 'Basic reports'],
    ],
  },
  {
    label: 'Lead capture & pipeline',
    keys: [
      ['csv_import', 'CSV import'],
      ['multi_source_capture', 'Multi-source lead capture'],
      ['form_integration', 'Website form integration'],
      ['stage_pipeline', 'Stage-wise pipeline'],
      ['lead_aging_tracker', 'Lead-ageing tracker'],
      ['overdue_alerts', 'Overdue follow-up alerts'],
    ],
  },
  {
    label: 'Sales accountability',
    keys: [
      ['rep_dashboard', 'Sales-rep dashboard'],
      ['rep_performance', 'Rep performance dashboard'],
      ['founder_summary', 'Founder summary dashboard'],
      ['daily_founder_report', 'Daily founder report'],
      ['weekly_sales_summary', 'Weekly sales summary'],
      ['rbac', 'Role-based access control'],
    ],
  },
  {
    label: 'AI superpowers',
    keys: [
      ['ai_followup_basic', 'AI follow-up suggestions'],
      ['ai_lead_scoring', 'AI lead scoring'],
      ['ai_qualification', 'AI lead qualification'],
      ['ai_followup_drafts', 'AI follow-up drafts (email/WhatsApp)'],
      ['ai_call_scheduling', 'AI call scheduling agent'],
      ['custom_scoring', 'Custom scoring logic'],
    ],
  },
  {
    label: 'Channels & integrations',
    keys: [
      ['whatsapp_click_to_msg', 'WhatsApp click-to-message'],
      ['whatsapp_workflow', 'WhatsApp workflow integration'],
      ['advanced_whatsapp', 'Advanced WhatsApp automation'],
      ['calendar_integration', 'Calendar/booking integration'],
      ['limited_crm_sync', 'Limited CRM sync'],
      ['crm_sync_full', 'Full CRM sync'],
      ['advanced_crm', 'Advanced CRM integration'],
      ['api_integrations', 'API integrations'],
    ],
  },
  {
    label: 'Pipeline value & deals',
    keys: [
      ['proposal_tracking', 'Proposal stage tracking'],
      ['deal_value', 'Deal value tracking'],
      ['pipeline_value_dashboard', 'Pipeline value dashboard'],
      ['lost_reason_tracking', 'Lost reason tracking'],
      ['automated_tasks', 'Automated task creation'],
    ],
  },
  {
    label: 'Custom plan power',
    keys: [
      ['custom_stages', 'Custom sales stages'],
      ['custom_workflows', 'Custom workflows'],
      ['multi_brand', 'Multi-brand & multi-branch setup'],
      ['client_dashboards', 'Client-specific dashboards'],
      ['advanced_attribution', 'Advanced attribution reporting'],
      ['custom_reports', 'Custom founder/management reports'],
      ['sla_alerts', 'SLA alerts'],
      ['training_section', 'Team training section'],
      ['dedicated_support', 'Dedicated implementation support'],
    ],
  },
];

const PLAN_ICONS = { starter: Sparkle, growth: Rocket, pro: Crown, custom: Buildings };

const Billing = () => {
  const { planId, allPlans, refreshPlan } = usePlan();
  const [checkingOut, setCheckingOut] = useState(null);
  const [pollStatus, setPollStatus] = useState(null);  // {session_id, message, type}

  // Poll the backend up to N attempts to confirm payment on return from Stripe.
  const pollPayment = useCallback(async (sessionId, attempts = 0) => {
    const maxAttempts = 10;
    const delay = 2000;
    if (attempts >= maxAttempts) {
      setPollStatus({ type: 'warn', message: 'Payment is still processing — refresh in a minute. If your plan did not upgrade, contact support.' });
      return;
    }
    try {
      const res = await api.get(`/api/billing/status/${sessionId}`);
      const data = res.data || {};
      if (data.payment_status === 'paid') {
        setPollStatus({ type: 'ok', message: `Payment successful — you're now on the ${data.plan} plan!` });
        toast.success('Plan upgraded');
        try { await refreshPlan?.(); } catch (e) { /* best-effort */ }
        // Clean the session_id from URL so a refresh doesn't re-poll
        window.history.replaceState({}, '', window.location.pathname);
        return;
      }
      if (data.status === 'expired') {
        setPollStatus({ type: 'err', message: 'This checkout session expired. Please try again.' });
        return;
      }
      setPollStatus({ type: 'pending', message: 'Confirming your payment with Stripe…' });
      setTimeout(() => pollPayment(sessionId, attempts + 1), delay);
    } catch (err) {
      setPollStatus({ type: 'err', message: err?.response?.data?.detail || 'Could not verify payment — please refresh.' });
    }
  }, [refreshPlan]);

  // On mount: check if we returned from Stripe with ?session_id=
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const sid = params.get('session_id');
    const cancelled = params.get('cancelled');
    if (sid) {
      setPollStatus({ type: 'pending', message: 'Confirming your payment with Stripe…' });
      pollPayment(sid);
    } else if (cancelled) {
      toast.error('Checkout cancelled — no charge was made.');
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, [pollPayment]);

  const handleCheckout = async (targetPlanId) => {
    if (targetPlanId === planId) return;
    const target = allPlans.find(p => p.id === targetPlanId);
    if (!target) return;
    if (target.contact_sales) {
      // For Custom plan, use the request-upgrade flow
      setCheckingOut(targetPlanId);
      try {
        await api.post('/api/billing/request-upgrade', { target_plan_id: targetPlanId, note: 'Requested via billing page' });
        toast.success('Sales team notified', { description: 'Expect a call within 24 hours.' });
      } catch (err) {
        toast.error(err?.response?.data?.detail || 'Request failed');
      } finally { setCheckingOut(null); }
      return;
    }
    // Only starter + pro are real Stripe packages for now. Growth/Custom fall through.
    const packageId = ['starter', 'pro'].includes(targetPlanId) ? targetPlanId : null;
    if (!packageId) {
      toast.error('This plan is not available for self-service checkout yet. Contact sales.');
      return;
    }
    setCheckingOut(targetPlanId);
    try {
      const res = await api.post('/api/billing/checkout', { package_id: packageId, origin_url: window.location.origin });
      if (res.data?.url) window.location.href = res.data.url;
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Checkout failed');
    } finally { setCheckingOut(null); }
  };

  const featureValueFor = (plan, key) => !!plan.features?.[key];

  return (
    <div className="space-y-6" data-testid="billing-page">
      <PageHeader
        eyebrow="ARIA Plans"
        title="Choose your sales operating layer"
        subtitle="Pick the plan that fits your team's growth stage. Upgrade anytime — no contracts, no surprises."
        actions={
          <div className="px-3 py-1.5 rounded-lg border border-[#7C35DC]/30 bg-[#F4F0FF] text-[#7C35DC] text-xs font-bold uppercase tracking-wider" data-testid="current-plan-pill">
            You're on {allPlans.find(p => p.id === planId)?.name || 'Starter'}
          </div>
        }
      />

      {pollStatus && (
        <div
          data-testid="billing-poll-banner"
          className={`px-4 py-3 rounded-lg border flex items-start gap-2 text-sm ${
            pollStatus.type === 'ok' ? 'bg-[#10B981]/10 border-[#10B981]/30 text-[#047857]' :
            pollStatus.type === 'err' ? 'bg-red-50 border-red-200 text-[#B91C1C]' :
            pollStatus.type === 'warn' ? 'bg-[#FEF3C7] border-[#D97706]/30 text-[#92400E]' :
            'bg-[#F4F0FF] border-[#7C35DC]/30 text-[#4C1D95]'
          }`}
        >
          <span className="font-semibold">{pollStatus.message}</span>
        </div>
      )}

      {/* Plan cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {allPlans.map(plan => {
          const Icon = PLAN_ICONS[plan.id] || Sparkle;
          const isCurrent = plan.id === planId;
          const isUpgrade = ['starter', 'growth', 'pro', 'custom'].indexOf(plan.id) > ['starter', 'growth', 'pro', 'custom'].indexOf(planId);
          return (
            <div key={plan.id} className={`relative bg-white border rounded-2xl p-5 transition-all ${isCurrent ? 'border-[#7C35DC] ring-2 ring-[#7C35DC]/20' : 'border-[#E8E0F5] hover:border-[#7C35DC]/40'}`} style={{ boxShadow: 'var(--shadow-card)' }} data-testid={`plan-card-${plan.id}`}>
              {plan.id === 'pro' && !isCurrent && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider text-white" style={{ background: 'var(--gradient-brand)' }}>Most Popular</div>
              )}
              <div className="flex items-center gap-2 mb-3">
                <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: 'var(--gradient-brand)' }}>
                  <Icon size={18} className="text-white" weight="fill" />
                </div>
                <h3 className="text-base font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{plan.name}</h3>
              </div>
              <div className="mb-3 min-h-[36px]">
                {plan.contact_sales ? (
                  <span className="text-xl font-extrabold text-[#7C35DC]">Contact Sales</span>
                ) : (
                  <>
                    <span className="text-3xl font-extrabold text-[#1A0A2E]">${plan.amount}</span>
                    <span className="text-xs text-[#9B8AB0] ml-1">/mo</span>
                  </>
                )}
              </div>
              <p className="text-xs text-[#5A4A7A] mb-4 min-h-[36px]">{plan.tagline}</p>
              <ul className="space-y-1.5 mb-5 min-h-[160px]">
                {(plan.headline_features || []).map((f, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-[#1A0A2E]">
                    <CheckCircle size={12} className="text-[#16A34A] mt-0.5 flex-shrink-0" weight="fill" /> {f}
                  </li>
                ))}
              </ul>
              {isCurrent ? (
                <button disabled className="w-full px-4 py-2.5 bg-[#F4F0FF] text-[#7C35DC] rounded-lg text-sm font-semibold cursor-default" data-testid={`plan-current-${plan.id}`}>Current plan</button>
              ) : isUpgrade ? (
                <button onClick={() => handleCheckout(plan.id)} disabled={checkingOut === plan.id} className="w-full flex items-center justify-center gap-2 btn-gradient px-4 py-2.5 rounded-lg text-sm font-semibold disabled:opacity-50" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid={`plan-upgrade-${plan.id}`}>
                  {checkingOut === plan.id ? 'Loading…' : plan.contact_sales ? <>Contact Sales <ArrowRight size={14} weight="bold" /></> : <>Upgrade <ArrowRight size={14} weight="bold" /></>}
                </button>
              ) : (
                <button onClick={() => handleCheckout(plan.id)} disabled className="w-full px-4 py-2.5 bg-white border border-[#E8E0F5] text-[#9B8AB0] rounded-lg text-sm font-semibold cursor-default" data-testid={`plan-downgrade-${plan.id}`}>Contact us to downgrade</button>
              )}
            </div>
          );
        })}
      </div>

      {/* Feature matrix */}
      <div className="bg-white border border-[#E8E0F5] rounded-2xl overflow-hidden" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="feature-matrix">
        <div className="p-5 border-b border-[#E8E0F5]">
          <h2 className="text-lg font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Compare every feature</h2>
          <p className="text-xs text-[#5A4A7A] mt-0.5">All four ARIA tiers, side by side</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-[#F9F5FF]">
              <tr>
                <th className="text-left px-5 py-3 text-xs font-bold uppercase tracking-wider text-[#5A4A7A]">Feature</th>
                {allPlans.map(p => (
                  <th key={p.id} className="text-center px-3 py-3 text-xs font-bold uppercase tracking-wider text-[#5A4A7A] min-w-[100px]">{p.name.replace('ARIA ', '')}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {FEATURE_GROUPS.map(group => (
                <React.Fragment key={group.label}>
                  <tr><td colSpan={allPlans.length + 1} className="px-5 py-2 bg-[#FBF9FE] text-[10px] font-bold uppercase tracking-[0.2em] text-[#7C35DC]">{group.label}</td></tr>
                  {group.keys.map(([key, label]) => (
                    <tr key={key} className="border-b border-[#F4F0FF]">
                      <td className="px-5 py-3 text-sm text-[#1A0A2E]">{label}</td>
                      {allPlans.map(p => (
                        <td key={p.id} className="text-center px-3 py-3" data-testid={`matrix-${p.id}-${key}`}>
                          {featureValueFor(p, key) ? (
                            <CheckCircle size={16} className="text-[#16A34A] inline-block" weight="fill" />
                          ) : (
                            <XIcon size={14} className="text-[#D4C5E8] inline-block" />
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default Billing;
