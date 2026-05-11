import React, { useState } from 'react';
import { GraduationCap, FileText, PlayCircle, Clock, X } from '@phosphor-icons/react';
import PageHeader from '../components/PageHeader';

const SECTIONS = [
  {
    title: 'Getting Started',
    items: [
      { id: 1, title: 'Setting Up Your Aria Workspace', minutes: 5, format: 'guide', body: 'Create your workspace from /signup, complete the 6-step onboarding wizard (Business Profile → Aria Persona → Sales Process → Lead Journey → WhatsApp → Team). Each step takes about a minute. The Lead Journey step auto-generates a 7-touchpoint sequence based on your industry and sales cycle — you can accept it as-is or customise.' },
      { id: 2, title: 'Connecting Your WhatsApp Number via 360dialog', minutes: 8, format: 'guide', body: 'Go to Settings → Workspace → WhatsApp provider. Switch to the "360dialog" tab. Paste your D360-API-KEY (from your 360dialog Hub) and the sender phone number. Click "Save credentials" then "Test connection" to confirm it. Aria will start using this provider for all outbound WhatsApp messages on this workspace.' },
      { id: 3, title: 'Full Onboarding Walkthrough', minutes: 12, format: 'video', loomId: 'placeholder-loom-id-1', body: 'Video walkthrough — replace this Loom embed with your recorded walkthrough URL.' },
    ],
  },
  {
    title: 'Using Aria',
    items: [
      { id: 4, title: 'How Aria Qualifies Leads', minutes: 4, format: 'guide', body: 'Aria scores every new lead against your ICP definition (Settings → Workspace) and qualification criteria from onboarding. Scores feed into the lead temperature: Hot (>=80), Warm (50-79), Cold (<50). Hot leads trigger human-escalation touchpoints automatically.' },
      { id: 5, title: 'Understanding Your Touchpoint Map', minutes: 6, format: 'guide', body: 'Your touchpoint map is the auto-generated journey Aria runs for every new lead. View and edit it in Settings → Lead Journey. Each touchpoint has a channel (WhatsApp/Email/Call/LinkedIn), a day+hour offset, a message type, and a role (Aria handles or Alert you).' },
      { id: 6, title: 'How to Take Over a Conversation from Aria', minutes: 3, format: 'guide', body: 'Open the lead detail drawer, scroll to the Conversation thread, and click "Take over". Aria stops auto-replying for that lead and you become the responder. Click "Hand back to Aria" to resume.' },
      { id: 7, title: 'Live Demo: Aria handling a B2B sales conversation', minutes: 8, format: 'video', loomId: 'placeholder-loom-id-2', body: 'Video — replace with your recorded demo URL.' },
    ],
  },
  {
    title: 'Managing Your Pipeline',
    items: [
      { id: 8, title: 'Adding and Importing Leads', minutes: 4, format: 'guide', body: 'Add a single lead via Lead Inbox → "Add Lead". For bulk imports, switch to the CSV tab — drag a file (max 5,000 rows), map your columns to Aria fields, preview, and confirm. Required: first_name, email, phone.' },
      { id: 9, title: 'Using the Kanban Pipeline View', minutes: 3, format: 'guide', body: 'The Pipeline page renders all your leads as cards across your configured stages. Drag-and-drop a card between columns to update stage. Stage changes trigger touchpoint rules automatically.' },
      { id: 10, title: 'Setting Up Custom Pipeline Stages', minutes: 3, format: 'guide', body: 'Edit your pipeline stages in onboarding (Step 3 Sales Process) or later from Settings → Aria Agent → Pipeline. Need at least 2 stages.' },
    ],
  },
  {
    title: 'Team & Settings',
    items: [
      { id: 11, title: 'Inviting Team Members and Setting Roles', minutes: 4, format: 'guide', body: 'Open Settings → Team → "Invite teammate". Pick a role (Admin / Member / Viewer), optionally enter an email — invites with email are auto-sent via Resend. Without an email, copy the magic link and share manually.' },
      { id: 12, title: "Customising Aria's Persona and Tone", minutes: 5, format: 'guide', body: 'Settings → Aria Agent → Persona. Edit Aria\'s display name, communication tone (Formal / Friendly-Professional / Casual / Aggressive Sales), primary language, and fallback behavior when she\'s unsure. Changes take effect on the next lead reply.' },
      { id: 13, title: 'Configuring Fallback Behaviour', minutes: 3, format: 'guide', body: 'Fallback behaviour controls what Aria does when she can\'t generate a confident reply. Options: Ask clarifying question (default), Escalate to human (alerts the team), or Give generic response. Tune this in Settings → Aria Agent → Persona.' },
    ],
  },
  {
    title: 'Troubleshooting',
    items: [
      { id: 14, title: 'What To Do When Aria Stops Responding', minutes: 5, format: 'guide', body: 'First check: is the workspace Aria status set to Active? Then verify your WhatsApp provider credentials in Settings → Workspace. If still silent, go to /troubleshooting for more diagnostic steps.' },
      { id: 15, title: 'Understanding Failed Touchpoints', minutes: 4, format: 'guide', body: 'A touchpoint can fail if (a) the recipient phone number is invalid, (b) your WhatsApp provider rejected the message, or (c) the customer-service window expired (no inbound message in 24hr). Failed touchpoints surface in the lead Journey tab with retry options.' },
    ],
  },
];

const Tutorials = () => {
  const [expanded, setExpanded] = useState(null);
  const [videoModal, setVideoModal] = useState(null);

  return (
    <div className="space-y-6" data-testid="tutorials-page">
      <PageHeader
        eyebrow="Help center"
        title="Tutorials & Documentation"
        subtitle="Step-by-step guides for every part of Aria — read-time stamped, no fluff."
        icon={GraduationCap}
      />

      {SECTIONS.map((section, sx) => (
        <div key={sx} data-testid={`tut-section-${sx}`}>
          <h2 className="text-[10px] font-bold uppercase tracking-[0.22em] text-[#7C35DC] mb-3">{section.title}</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {section.items.map((it) => (
              <div key={it.id} className="bg-white border border-[#E8E0F5] rounded-xl p-4 hover:border-[#7C35DC]/40 transition" data-testid={`tut-card-${it.id}`}>
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: it.format === 'video' ? '#FEE2E2' : '#F4F0FF' }}>
                    {it.format === 'video'
                      ? <PlayCircle size={18} weight="fill" className="text-[#DC2626]" />
                      : <FileText size={18} weight="fill" className="text-[#7C35DC]" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-sm font-bold text-[#1A0A2E]">{it.title}</h3>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider ${it.format === 'video' ? 'bg-[#FEE2E2] text-[#B91C1C]' : 'bg-[#F4F0FF] text-[#7C35DC]'}`}>
                        {it.format === 'video' ? '▶ Video' : '📄 Guide'}
                      </span>
                      <span className="text-[10px] text-[#9B8AB0] flex items-center gap-0.5"><Clock size={9} /> {it.minutes} min</span>
                    </div>
                    {expanded === it.id && it.format === 'guide' && (
                      <p className="text-xs text-[#5A4A7A] mt-3 leading-relaxed" data-testid={`tut-body-${it.id}`}>{it.body}</p>
                    )}
                    <button
                      onClick={() => {
                        if (it.format === 'video') setVideoModal(it);
                        else setExpanded(expanded === it.id ? null : it.id);
                      }}
                      data-testid={`tut-view-${it.id}`}
                      className="mt-2 text-xs font-bold uppercase tracking-[0.14em] text-[#7C35DC] hover:underline"
                    >
                      {it.format === 'video' ? 'Watch' : expanded === it.id ? 'Collapse' : 'View'}
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}

      {/* Video modal */}
      {videoModal && (
        <div className="fixed inset-0 z-[90] flex items-center justify-center p-4" data-testid="tut-video-modal">
          <div className="absolute inset-0 bg-black/70" onClick={() => setVideoModal(null)} />
          <div className="relative bg-white rounded-2xl overflow-hidden max-w-3xl w-full">
            <button onClick={() => setVideoModal(null)} className="absolute top-3 right-3 z-10 p-1.5 rounded bg-white/90 text-[#1A0A2E] hover:bg-white" data-testid="tut-video-close"><X size={14} weight="bold" /></button>
            <div className="aspect-video bg-[#0D0D1A] flex items-center justify-center text-white text-sm">
              <div className="text-center">
                <PlayCircle size={32} weight="fill" className="mx-auto mb-2 text-[#E2B96F]" />
                <div className="font-bold">{videoModal.title}</div>
                <div className="text-xs text-[#A0A8C0] mt-1">Loom embed placeholder · ID: {videoModal.loomId}</div>
              </div>
            </div>
            <div className="p-5">
              <h3 className="text-base font-extrabold text-[#1A0A2E]">{videoModal.title}</h3>
              <p className="text-xs text-[#5A4A7A] mt-1">{videoModal.body}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Tutorials;
