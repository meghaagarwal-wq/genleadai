import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { ChartLineUp, ShieldCheck, Users, Heartbeat, Clock } from '@phosphor-icons/react';
import RevenueTab from '../components/admin/RevenueTab';
import WorkspacesTab from '../components/admin/WorkspacesTab';
import HealthMonitorTab from '../components/admin/HealthMonitorTab';
import TrialExpiriesTab from '../components/admin/TrialExpiriesTab';
import PlatformStatsTab from '../components/admin/PlatformStatsTab';
import ContactRequestsTab from '../components/admin/ContactRequestsTab';

const TABS = [
  { key: 'revenue', label: 'Revenue', icon: ChartLineUp, component: RevenueTab },
  { key: 'workspaces', label: 'All Workspaces', icon: Users, component: WorkspacesTab },
  { key: 'trials', label: 'Trial Expiries', icon: Clock, component: TrialExpiriesTab },
  { key: 'health', label: 'Health Monitor', icon: Heartbeat, component: HealthMonitorTab },
  { key: 'platform-stats', label: 'Platform Stats', icon: ChartLineUp, component: PlatformStatsTab },
  { key: 'contact-requests', label: 'Contact Inbox', icon: Users, component: ContactRequestsTab },
];

const MasterAdmin = () => {
  const { user } = useAuth();
  const [active, setActive] = useState('revenue');

  if ((user?.role || '').toLowerCase() !== 'admin') {
    return (
      <div className="p-8" data-testid="master-admin-denied">
        <div className="bg-[#FEE2E2] border border-[#DC2626]/30 rounded-xl p-6 max-w-xl">
          <h2 className="font-bold text-[#1A0A2E] text-lg mb-1">Access denied</h2>
          <p className="text-sm text-[#5A4A7A]">Master Admin is reserved for GenLeadAI platform owners.</p>
        </div>
      </div>
    );
  }

  const ActiveCmp = TABS.find((t) => t.key === active)?.component;

  return (
    <div data-testid="master-admin-page" className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-extrabold text-[#1A0A2E] tracking-tight" style={{ fontFamily: 'Plus Jakarta Sans' }}>
            Master Admin
          </h1>
          <p className="text-sm text-[#5A4A7A] mt-1">Platform-wide controls for GenLeadAI operators.</p>
        </div>
        <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#7C35DC]/10 text-[#7C35DC] text-[10px] font-bold uppercase tracking-[0.18em]">
          <ShieldCheck size={12} weight="fill" /> Admin
        </div>
      </div>

      <div className="border-b border-[#E8E0F5]">
        <div className="flex gap-1" data-testid="master-admin-tabs">
          {TABS.map((t) => {
            const Icon = t.icon;
            const enabled = !!t.component;
            const isActive = active === t.key;
            return (
              <button
                key={t.key}
                disabled={!enabled}
                onClick={() => enabled && setActive(t.key)}
                data-testid={`tab-${t.key}`}
                className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold rounded-t-lg border-b-2 transition-all ${
                  isActive
                    ? 'border-[#7C35DC] text-[#7C35DC] bg-[#F4F0FF]'
                    : enabled
                    ? 'border-transparent text-[#5A4A7A] hover:text-[#7C35DC] hover:bg-[#F9F5FF]'
                    : 'border-transparent text-[#C4B5D8] cursor-not-allowed'
                }`}
                style={{ fontFamily: 'Plus Jakarta Sans' }}
              >
                <Icon size={16} weight="duotone" />
                {t.label}
                {!enabled && <span className="text-[9px] font-bold ml-1 px-1.5 py-0.5 rounded bg-[#E8E0F5] text-[#9B8AB0]">soon</span>}
              </button>
            );
          })}
        </div>
      </div>

      <div>{ActiveCmp ? <ActiveCmp /> : null}</div>
    </div>
  );
};

export default MasterAdmin;
