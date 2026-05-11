import React, { useEffect, useState } from 'react';
import api from '../config/api';
import { ChartBar, CheckCircle, X as XIcon } from '@phosphor-icons/react';
import PageHeader from '../components/PageHeader';

const IN_SCOPE = [
  'Responding to inbound WhatsApp messages',
  'Running qualification conversations',
  'Sending scheduled touchpoint sequences',
  'Escalating qualified leads to your team',
  'Logging all conversations to your dashboard',
  'Sending WhatsApp broadcast campaigns',
  'Managing your lead pipeline stages',
  'Multi-user team access and role management',
];
const OUT_OF_SCOPE = [
  'Making outbound phone calls',
  'Sending SMS (WhatsApp only)',
  'Scraping or sourcing new leads independently',
  'Posting on social media',
  'Writing or sending emails autonomously (email touchpoints require your SMTP setup)',
  'Guaranteeing lead conversion or sales outcomes',
  'Operating without an active 360dialog WhatsApp Business API connection',
];

const SLA_ROWS = [
  ['Support response', '48hr', '12hr', '4hr'],
  ['Onboarding support', 'Self-serve', '1 setup call', 'Fully managed'],
  ['Uptime commitment', 'Best effort', 'Best effort', '99.5%'],
  ['Conversation monitoring', 'Self', 'Self', 'GenLeadAI team'],
];

const UsageBar = ({ label, used, total }) => {
  const isUnlimited = total === -1;
  const pct = isUnlimited ? 0 : Math.min(100, Math.round((used / Math.max(1, total)) * 100));
  const colour = pct >= 95 ? '#DC2626' : pct >= 80 ? '#E2B96F' : '#7C35DC';
  return (
    <div data-testid={`usage-${label.toLowerCase().replace(/\s+/g, '-')}`}>
      <div className="flex justify-between items-baseline mb-1">
        <span className="text-xs font-bold text-[#1A0A2E]">{label}</span>
        <span className="text-xs text-[#5A4A7A]">{used}{isUnlimited ? ' · unlimited' : ` / ${total}`}</span>
      </div>
      <div className="h-2 bg-[#F4F0FF] rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{ width: `${isUnlimited ? 100 : pct}%`, background: isUnlimited ? '#16A34A' : colour }} />
      </div>
    </div>
  );
};

const Limits = () => {
  const [status, setStatus] = useState(null);

  useEffect(() => {
    api.get('/api/plans/status').then((r) => setStatus(r.data)).catch(() => {});
  }, []);

  if (!status) return <div className="p-6 text-sm text-[#5A4A7A]">Loading…</div>;
  const plan = status.plan_meta;
  const limits = plan?.limits || { active_leads: 500, team_seats: 5, monthly_conversations: 2000 };

  return (
    <div className="space-y-6" data-testid="limits-page">
      <PageHeader
        eyebrow="Workspace"
        title="Plan limits & scope"
        subtitle="What's included, what's not, and where you are right now."
        icon={ChartBar}
      />

      <div className="bg-white border border-[#E8E0F5] rounded-2xl p-6" data-testid="current-plan-summary">
        <div className="flex flex-wrap items-baseline justify-between gap-2 mb-5">
          <div>
            <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-[#7C35DC]">Current plan</div>
            <h2 className="text-2xl font-extrabold text-[#1A0A2E]">{status.plan === 'trial' ? `Trial · ${status.trial_days_left ?? 0} days left` : (plan?.name || status.plan)}</h2>
          </div>
          {plan && <div className="text-sm text-[#5A4A7A] italic">{plan.subtitle}</div>}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <UsageBar label="Active leads" used={status.usage?.active_leads || 0} total={limits.active_leads} />
          <UsageBar label="Team seats" used={status.usage?.team_seats || 0} total={limits.team_seats} />
          <UsageBar label="Conversations this month" used={0} total={limits.monthly_conversations} />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white border border-[#E8E0F5] rounded-2xl p-6" data-testid="scope-in">
          <h3 className="text-sm font-extrabold text-[#1A0A2E] mb-3 flex items-center gap-2">
            <CheckCircle size={14} weight="fill" className="text-[#16A34A]" /> What Aria does
          </h3>
          <ul className="space-y-2">
            {IN_SCOPE.map((s, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-[#1A0A2E]"><CheckCircle size={11} weight="fill" className="text-[#16A34A] mt-0.5 flex-shrink-0" />{s}</li>
            ))}
          </ul>
        </div>
        <div className="bg-white border border-[#E8E0F5] rounded-2xl p-6" data-testid="scope-out">
          <h3 className="text-sm font-extrabold text-[#1A0A2E] mb-3 flex items-center gap-2">
            <XIcon size={14} weight="bold" className="text-[#DC2626]" /> What Aria doesn't do
          </h3>
          <ul className="space-y-2">
            {OUT_OF_SCOPE.map((s, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-[#5A4A7A]"><XIcon size={11} weight="bold" className="text-[#DC2626] mt-0.5 flex-shrink-0" />{s}</li>
            ))}
          </ul>
        </div>
      </div>

      <div className="bg-white border border-[#E8E0F5] rounded-2xl overflow-hidden" data-testid="sla-table">
        <div className="p-5 border-b border-[#E8E0F5]">
          <h2 className="text-base font-extrabold text-[#1A0A2E]">SLA by plan</h2>
        </div>
        <table className="w-full">
          <thead className="bg-[#F9F5FF]">
            <tr>
              <th className="text-left px-5 py-3 text-[10px] font-bold uppercase tracking-wider text-[#5A4A7A]"></th>
              <th className="text-center px-3 py-3 text-[10px] font-bold uppercase tracking-wider text-[#5A4A7A]">DIY</th>
              <th className="text-center px-3 py-3 text-[10px] font-bold uppercase tracking-wider text-[#5A4A7A]">DWY</th>
              <th className="text-center px-3 py-3 text-[10px] font-bold uppercase tracking-wider text-[#5A4A7A]">DFY</th>
            </tr>
          </thead>
          <tbody>
            {SLA_ROWS.map(([label, ...cells]) => (
              <tr key={label} className="border-b border-[#F4F0FF]">
                <td className="px-5 py-3 text-xs font-bold text-[#1A0A2E]">{label}</td>
                {cells.map((c, i) => <td key={i} className="text-center px-3 py-3 text-xs text-[#5A4A7A]">{c}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Limits;
