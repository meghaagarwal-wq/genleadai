/**
 * Automation — unified page combining Lead Inbox + Campaigns + Touchpoints
 * (for B2C / hybrid workspaces).
 *
 * Spec section 5: replaces standalone Lead Inbox, Outreach Campaigns, and
 * 32-Touchpoint Journey nav items. They now live as tabs here.
 */
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ChatCircleText, Lightning, Path } from '@phosphor-icons/react';
import LeadFeed from './LeadFeed';
import Campaigns from './Campaigns';
import TouchpointMap from './TouchpointMap';
import WorkspacePullBar from '../../components/WorkspacePullBar';

const TABS = [
  { id: 'inbox',       label: 'Lead Inbox',  icon: ChatCircleText },
  { id: 'campaigns',   label: 'Campaigns',   icon: Lightning },
  { id: 'touchpoints', label: 'Touchpoints', icon: Path },
];

const Automation = () => {
  const [tab, setTab] = useState('inbox');

  return (
    <div data-testid="automation-page" className="space-y-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-[#7C35DC]">Automation</div>
          <h1 className="text-2xl font-extrabold text-[#0F172A]" style={{ fontFamily: 'Space Grotesk, Inter' }}>
            One place to capture, message, and follow up
          </h1>
        </div>
        <WorkspacePullBar />
      </div>

      <div className="flex items-center gap-1 border-b border-[#E2E8F0]">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            data-testid={`automation-tab-${t.id}`}
            className={`px-4 py-2.5 text-sm font-semibold inline-flex items-center gap-1.5 border-b-2 -mb-px ${
              tab === t.id
                ? 'border-[#7C35DC] text-[#7C35DC]'
                : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
            }`}
          >
            <t.icon size={14} weight="duotone" /> {t.label}
          </button>
        ))}
      </div>

      <div data-testid={`automation-tab-content-${tab}`}>
        {tab === 'inbox' && <LeadFeed embedded />}
        {tab === 'campaigns' && <Campaigns embedded />}
        {tab === 'touchpoints' && (
          <div className="space-y-4" data-testid="automation-touchpoints-tab">
            <div className="flex items-center justify-between gap-3 flex-wrap rounded-lg border p-4"
                 style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }}>
              <div>
                <div className="text-sm font-semibold" style={{ color: 'var(--theme-text)' }}>32-Touchpoint Journey</div>
                <div className="text-xs" style={{ color: 'var(--theme-text-muted)' }}>
                  Full visual builder: flowchart · timeline · pipeline · conditional logic
                </div>
              </div>
              <Link
                to="/app/touchpoints"
                data-testid="automation-touchpoints-open-builder"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold text-white"
                style={{ background: 'var(--theme-purple)' }}
              >
                Open Full Journey Builder →
              </Link>
            </div>
            <TouchpointMap embedded />
          </div>
        )}
      </div>

      <div className="text-[11px] text-[#94A3B8] pt-3 border-t border-[#F1F5F9]">
        Looking for the old Automation Rules builder? It moved to{' '}
        <Link to="/app/automation-rules" className="text-[#7C35DC] hover:underline font-semibold">Settings → Automation rules</Link>.
      </div>
    </div>
  );
};

export default Automation;
