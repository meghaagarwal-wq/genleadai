import React from 'react';
import { Plug, CheckCircle, Globe, FacebookLogo, GoogleLogo, LinkedinLogo, WhatsappLogo, CalendarBlank, EnvelopeSimple, Database, FileText } from '@phosphor-icons/react';
import { usePlan } from '../context/PlanContext';
import LockBadge from '../components/LockBadge';
import PageHeader from '../components/PageHeader';

const INTEGRATIONS = [
  { id: 'website_forms', name: 'Website Forms', icon: Globe, status: 'connected', feature: 'form_integration', desc: 'Embed a public form & receive leads instantly.' },
  { id: 'meta_ads', name: 'Meta Lead Ads', icon: FacebookLogo, status: 'available', feature: 'multi_source_capture', desc: 'Sync Facebook & Instagram lead-gen forms.' },
  { id: 'google_ads', name: 'Google Ads', icon: GoogleLogo, status: 'coming_soon', feature: 'multi_source_capture', desc: 'Pull conversion-API leads automatically.' },
  { id: 'linkedin', name: 'LinkedIn Lead Gen', icon: LinkedinLogo, status: 'coming_soon', feature: 'multi_source_capture', desc: 'Direct sync from LinkedIn campaigns.' },
  { id: 'whatsapp', name: 'WhatsApp Business API', icon: WhatsappLogo, status: 'connected', feature: 'whatsapp_click_to_msg', desc: 'Native Meta Cloud API — outbound + inbound.' },
  { id: 'calendly', name: 'Calendly', icon: CalendarBlank, status: 'connected', feature: 'calendar_integration', desc: 'ARIA books meetings on your behalf.' },
  { id: 'gcal', name: 'Google Calendar', icon: CalendarBlank, status: 'coming_soon', feature: 'calendar_integration', desc: 'Two-way sync with Google Calendar.' },
  { id: 'email', name: 'Email (Resend)', icon: EnvelopeSimple, status: 'connected', feature: 'multi_source_capture', desc: 'Transactional + outbound email at scale.' },
  { id: 'zoho', name: 'Zoho CRM', icon: Database, status: 'request', feature: 'crm_sync_full', desc: 'Bi-directional Zoho sync.' },
  { id: 'hubspot', name: 'HubSpot CRM', icon: Database, status: 'request', feature: 'crm_sync_full', desc: 'Lead, contact & deal sync with HubSpot.' },
  { id: 'gsheets', name: 'Google Sheets', icon: FileText, status: 'coming_soon', feature: 'multi_source_capture', desc: 'Push every lead row into a workbook.' },
];

const STATUS_BADGE = {
  connected: { label: 'Connected', className: 'bg-[#DCFCE7] text-[#16A34A] border-[#16A34A]/30' },
  available: { label: 'Available', className: 'bg-[#F4F0FF] text-[#7C35DC] border-[#7C35DC]/30' },
  coming_soon: { label: 'Coming soon', className: 'bg-[#FEF3C7] text-[#D97706] border-[#D97706]/30' },
  request: { label: 'Request', className: 'bg-[#F1F5F9] text-[#5A4A7A] border-[#94A3B8]/30' },
};

const Integrations = () => {
  const { hasFeature, openUpgrade } = usePlan();
  return (
    <div className="space-y-6" data-testid="integrations-page">
      <PageHeader
        eyebrow="Growth Stack"
        title="Connect ARIA With Your Growth Stack"
        subtitle="Bring your marketing channels, CRM, calendar, and WhatsApp workflows into one sales command center."
      />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {INTEGRATIONS.map(i => {
          const unlocked = hasFeature(i.feature);
          const badge = STATUS_BADGE[i.status];
          const Icon = i.icon;
          return (
            <div key={i.id} className="bg-white border border-[#E8E0F5] rounded-xl p-5 flex flex-col" style={{ boxShadow: 'var(--shadow-card)' }} data-testid={`integration-card-${i.id}`}>
              <div className="flex items-start justify-between mb-3">
                <div className="w-11 h-11 rounded-xl flex items-center justify-center" style={{ background: '#F4F0FF' }}>
                  <Icon size={22} className="text-[#7C35DC]" weight="fill" />
                </div>
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${badge.className}`}>{badge.label}</span>
              </div>
              <h3 className="text-sm font-bold text-[#1A0A2E] mb-1" style={{ fontFamily: 'Plus Jakarta Sans' }}>{i.name}</h3>
              <p className="text-xs text-[#5A4A7A] mb-4 flex-1">{i.desc}</p>
              {!unlocked && i.status !== 'coming_soon' && i.status !== 'request' ? (
                <button onClick={() => openUpgrade(i.feature)} className="w-full px-3 py-2 bg-[#F4F0FF] text-[#7C35DC] rounded-lg text-xs font-bold uppercase tracking-wider border border-[#7C35DC]/20 hover:bg-[#E0D4F7] transition-colors" data-testid={`integration-upgrade-${i.id}`}>Upgrade to unlock</button>
              ) : i.status === 'connected' ? (
                <div className="flex items-center gap-1.5 text-xs text-[#16A34A] font-medium"><CheckCircle size={12} weight="fill" /> Active</div>
              ) : i.status === 'available' ? (
                <button className="w-full px-3 py-2 bg-white border border-[#7C35DC]/30 text-[#7C35DC] rounded-lg text-xs font-bold uppercase tracking-wider hover:bg-[#F4F0FF] transition-colors" data-testid={`integration-connect-${i.id}`}>Connect</button>
              ) : i.status === 'request' ? (
                <button className="w-full px-3 py-2 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-lg text-xs font-bold uppercase tracking-wider hover:bg-[#F9F5FF] transition-colors" data-testid={`integration-request-${i.id}`}>Request integration</button>
              ) : (
                <div className="flex items-center gap-1.5 text-xs text-[#9B8AB0]"><Plug size={12} /> Coming soon</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default Integrations;
