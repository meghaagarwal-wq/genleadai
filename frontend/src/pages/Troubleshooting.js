import React, { useState } from 'react';
import { Wrench, CaretDown, EnvelopeSimple, Calendar } from '@phosphor-icons/react';
import PageHeader from '../components/PageHeader';

const ISSUES = [
  {
    q: 'Aria is not responding to WhatsApp messages',
    a: (
      <ul className="list-disc pl-5 space-y-1 text-sm text-[#1A0A2E]">
        <li>Is your 360dialog (or Meta) API key active? Check Settings → Workspace → WhatsApp provider.</li>
        <li>Is your webhook URL correctly set to <code className="bg-[#F4F0FF] px-1 rounded">https://app.genleadai.com/api/webhook/&#123;workspace_id&#125;</code>?</li>
        <li>Is Aria status set to <strong>Active</strong> (not Paused) on your dashboard?</li>
      </ul>
    ),
  },
  {
    q: 'Messages are being sent but not delivered',
    a: <p className="text-sm text-[#1A0A2E]">Verify your WhatsApp Business number is approved and active on 360dialog. Check your 360dialog dashboard for delivery errors and rate limits.</p>,
  },
  {
    q: 'Aria gave a wrong or irrelevant response',
    a: <p className="text-sm text-[#1A0A2E]">This usually happens when the Aria persona or product description is too vague. Go to <strong>Settings → Aria Agent</strong> and add more detail to your product description and qualification criteria. Specifics like industry, deal size, and target persona make Aria's replies sharper.</p>,
  },
  {
    q: 'A lead stopped receiving touchpoints',
    a: <p className="text-sm text-[#1A0A2E]">Check the lead's stage — if it was manually changed to Closed Won or Closed Lost, all future touchpoints are automatically paused. Also check the lead's <strong>Journey</strong> tab for any failed touchpoint statuses.</p>,
  },
  {
    q: "Team member can't access the dashboard",
    a: <p className="text-sm text-[#1A0A2E]">Ensure their invite was accepted and that the assigned role has the required permissions. Open the <strong>Team</strong> tab in Settings to verify pending invite status — re-send the email if the link expired.</p>,
  },
  {
    q: 'I want to pause Aria for all leads temporarily',
    a: <p className="text-sm text-[#1A0A2E]">Go to <strong>Dashboard</strong> and toggle the Aria Status switch to <strong>Paused</strong>. All auto-responses and outbound touchpoints stop immediately and resume on resume.</p>,
  },
];

const Troubleshooting = () => {
  const [open, setOpen] = useState(0);

  return (
    <div className="space-y-6" data-testid="troubleshooting-page">
      <PageHeader
        eyebrow="Help center"
        title="Troubleshooting"
        subtitle="Quick fixes for the most common Aria issues."
        icon={Wrench}
      />

      <div className="bg-white border border-[#E8E0F5] rounded-2xl divide-y divide-[#F0ECF9]" data-testid="troubleshooting-accordion">
        {ISSUES.map((it, i) => (
          <div key={i} data-testid={`ts-row-${i}`}>
            <button
              onClick={() => setOpen(open === i ? -1 : i)}
              className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-[#FBF9FE]"
              data-testid={`ts-toggle-${i}`}
            >
              <span className="text-sm font-bold text-[#1A0A2E]">{it.q}</span>
              <CaretDown size={14} weight="bold" className={`text-[#7C35DC] transition-transform ${open === i ? 'rotate-180' : ''}`} />
            </button>
            {open === i && (
              <div className="px-5 pb-4" data-testid={`ts-answer-${i}`}>
                {it.a}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Contact section */}
      <div className="bg-[#0D0D1A] text-white rounded-2xl p-6" data-testid="ts-contact">
        <h3 className="text-lg font-extrabold mb-1">Still stuck? Talk to us.</h3>
        <p className="text-sm text-[#A0A8C0] mb-4">Response times depend on your plan: DIY 48hr · DWY 12hr · DFY 4hr.</p>
        <div className="flex flex-wrap gap-3">
          <a
            href="mailto:support@genleadai.com"
            data-testid="ts-email-link"
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-bold bg-[#4F8EF7] hover:bg-[#3E7AE2]"
          >
            <EnvelopeSimple size={14} weight="fill" /> support@genleadai.com
          </a>
          <a
            href="https://calendly.com/genleadai/support"
            target="_blank" rel="noopener noreferrer"
            data-testid="ts-calendly-link"
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-bold bg-[#E2B96F] text-[#1F1305] hover:bg-[#D4A85E]"
          >
            <Calendar size={14} weight="fill" /> Book a support call
          </a>
        </div>
      </div>
    </div>
  );
};

export default Troubleshooting;
