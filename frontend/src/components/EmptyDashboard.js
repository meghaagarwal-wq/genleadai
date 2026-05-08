import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Plus, FileArrowUp, PlayCircle, Sparkle, Lightning, Target,
  ChartLineUp, Users, ChatTeardropDots, Robot, ArrowRight,
} from '@phosphor-icons/react';

/**
 * EmptyDashboard — shown when a fresh tenant has zero leads.
 *
 * Replaces the noisy fake-data widgets with a clean welcome screen + 3 ways
 * to get started + a "Browse demo" link so the user can see what the dashboard
 * looks like populated.
 */
const EmptyDashboard = ({ workspaceName, founderName }) => {
  const navigate = useNavigate();
  const [showDemoVideo, setShowDemoVideo] = useState(false);

  const greeting = () => {
    const h = new Date().getHours();
    if (h < 12) return 'Good morning';
    if (h < 17) return 'Good afternoon';
    return 'Good evening';
  };

  return (
    <div className="space-y-6 max-w-[1400px] mx-auto" data-testid="empty-dashboard">
      {/* Hero */}
      <div
        className="relative overflow-hidden rounded-3xl p-8 sm:p-10"
        style={{ background: 'linear-gradient(135deg, #1A0A2E 0%, #4C1D95 55%, #7C35DC 100%)' }}
      >
        <div className="absolute -top-20 -right-20 w-64 h-64 rounded-full opacity-20" style={{ background: 'radial-gradient(circle, #C9B6FF 0%, transparent 70%)' }} />
        <div className="relative">
          <div className="flex items-center gap-2 mb-3">
            <Sparkle size={12} weight="fill" className="text-[#C9B6FF]" />
            <span className="text-[10px] font-bold uppercase tracking-[0.3em] text-[#C9B6FF]">
              ARIA · YOUR FIRST AI SALES HIRE
            </span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-bold text-white leading-tight" style={{ fontFamily: 'Space Grotesk, Inter' }}>
            {greeting()}{founderName ? `, ${founderName.split(' ')[0]}` : ''}.
          </h1>
          <p className="text-lg text-[#C9B6FF] mt-2">
            Welcome to <span className="font-bold text-white">{workspaceName || 'your new workspace'}</span>.
            Aria's ready — let's get her some leads to work.
          </p>

          <div className="flex flex-wrap gap-3 mt-6">
            <button
              onClick={() => navigate('/leads')}
              data-testid="empty-add-lead-btn"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-white text-[#4C1D95] font-bold text-sm hover:bg-[#F4F0FF] transition"
            >
              <Plus size={16} weight="bold" /> Add your first lead
            </button>
            <button
              onClick={() => navigate('/leads')}
              data-testid="empty-import-csv-btn"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-white/10 text-white font-bold text-sm border border-white/30 backdrop-blur-sm hover:bg-white/20 transition"
            >
              <FileArrowUp size={16} weight="bold" /> Import CSV
            </button>
            <button
              onClick={() => setShowDemoVideo(true)}
              data-testid="empty-demo-video-btn"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-white/10 text-white font-bold text-sm border border-white/30 backdrop-blur-sm hover:bg-white/20 transition"
            >
              <PlayCircle size={16} weight="fill" /> Watch 2-min demo
            </button>
          </div>
        </div>
      </div>

      {/* 3-up: how Aria works */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Step
          n="01"
          icon={Users}
          title="Add your leads"
          body="Manually, via CSV upload, or auto-capture from website forms, WhatsApp, and email."
        />
        <Step
          n="02"
          icon={Robot}
          title="Aria qualifies them"
          body="She scores ICP fit, engages over WhatsApp, asks qualifying questions, and books calls — all on autopilot."
        />
        <Step
          n="03"
          icon={Target}
          title="You close the deals"
          body="Aria hands you the qualified ones with full context. Hot leads. No cold-call grind."
        />
      </div>

      {/* What you get */}
      <div className="bg-white border border-[#E8E0F5] rounded-2xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <Lightning size={14} weight="fill" className="text-[#7C35DC]" />
          <h2 className="text-sm font-bold uppercase tracking-[0.18em] text-[#5A4A7A]">
            What lights up here once leads start flowing
          </h2>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <FeaturePill icon={ChartLineUp} label="Live KPI cards" />
          <FeaturePill icon={Sparkle} label="Daily Aria brief" />
          <FeaturePill icon={ChatTeardropDots} label="Conversation feed" />
          <FeaturePill icon={Target} label="Pipeline mood" />
        </div>
      </div>

      {/* Browse demo CTA */}
      <div className="bg-[#F4F0FF] border border-[#7C35DC]/20 rounded-2xl p-6 flex items-center justify-between flex-wrap gap-4">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#7C35DC]">
            CURIOUS WHAT IT LOOKS LIKE WITH DATA?
          </div>
          <div className="text-base font-bold text-[#1A0A2E] mt-1" style={{ fontFamily: 'Space Grotesk, Inter' }}>
            Browse the demo dashboard with sample leads.
          </div>
          <p className="text-sm text-[#5A4A7A] mt-1">
            See exactly what your dashboard will look like once Aria is working real leads.
          </p>
        </div>
        <a
          href="/aria/demo-dashboard"
          target="_blank"
          rel="noopener noreferrer"
          data-testid="empty-browse-demo-btn"
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-white font-bold text-sm"
          style={{ background: 'linear-gradient(135deg, #4C1D95, #7C35DC)' }}
        >
          Browse demo <ArrowRight size={14} weight="bold" />
        </a>
      </div>

      {/* Demo video modal */}
      {showDemoVideo && (
        <div
          className="fixed inset-0 z-[80] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
          onClick={() => setShowDemoVideo(false)}
          data-testid="empty-demo-video-modal"
        >
          <div
            className="relative w-full max-w-3xl bg-[#1A0A2E] rounded-2xl overflow-hidden border border-white/10"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={() => setShowDemoVideo(false)}
              data-testid="empty-demo-video-close"
              className="absolute top-3 right-3 z-10 px-3 py-1.5 rounded-md bg-white/10 text-white text-xs font-bold hover:bg-white/20"
            >
              Close
            </button>
            {/* Placeholder — when you upload a real Loom/YouTube embed, swap the iframe src */}
            <div className="aspect-video bg-[#2D1B4E] flex flex-col items-center justify-center gap-3 text-center px-6">
              <PlayCircle size={48} weight="fill" className="text-[#C9B6FF]" />
              <div className="text-white text-lg font-bold" style={{ fontFamily: 'Space Grotesk, Inter' }}>
                Demo video coming soon
              </div>
              <p className="text-sm text-[#C9B6FF] max-w-md">
                Drop us a Loom or YouTube link in <span className="font-mono">/admin → Settings → Demo Video URL</span> and we'll embed it here automatically.
              </p>
              <a
                href="https://genleadai.com/aria"
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-white text-[#4C1D95] font-bold text-sm"
              >
                Visit genleadai.com/aria <ArrowRight size={14} weight="bold" />
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const Step = ({ n, icon: Icon, title, body }) => (
  <div className="bg-white border border-[#E8E0F5] rounded-2xl p-5">
    <div className="flex items-center gap-2 mb-2">
      <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#7C35DC]">{n}</span>
      <div className="w-7 h-7 rounded-md flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #4C1D95, #7C35DC)' }}>
        <Icon size={14} weight="fill" className="text-white" />
      </div>
    </div>
    <div className="text-base font-bold text-[#1A0A2E]" style={{ fontFamily: 'Space Grotesk, Inter' }}>{title}</div>
    <p className="text-sm text-[#5A4A7A] mt-1 leading-relaxed">{body}</p>
  </div>
);

const FeaturePill = ({ icon: Icon, label }) => (
  <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#FAF7FF] border border-[#E8E0F5]">
    <Icon size={14} weight="fill" className="text-[#7C35DC]" />
    <span className="text-xs font-semibold text-[#1A0A2E]">{label}</span>
  </div>
);

export default EmptyDashboard;
