import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Lightning, FileText, Fire, Clock, Sparkle, Bell } from '@phosphor-icons/react';
import api from '../config/api';

/**
 * WorkspaceHero — the first thing a founder sees when opening ARIA.
 * Not a product page, not a greeting card — a workspace cockpit header.
 * Shows notification badge ("N updates waiting for you") and two primary CTAs.
 */
const WorkspaceHero = ({ userName }) => {
  const navigate = useNavigate();
  const [brief, setBrief] = useState(null);

  useEffect(() => {
    api.get('/api/aria-agent/workspace/morning-brief').then(r => setBrief(r.data)).catch(() => {});
  }, []);

  const b = brief?.badges || {};
  const updatesCount = (b.hot_leads || 0) + (b.followups_due || 0) + (b.proposals || 0);

  return (
    <div className="relative rounded-3xl overflow-hidden aria-grain aria-fade-up" style={{ background: 'var(--gradient-aria-deep)', boxShadow: 'var(--shadow-deep)' }} data-testid="workspace-hero">
      <div className="absolute inset-0 pointer-events-none" style={{ background: 'var(--gradient-aria-glow)' }} />
      <div className="relative px-6 md:px-8 py-7 md:py-9">
        {/* Notification badge row */}
        {updatesCount > 0 && (
          <div className="inline-flex items-center gap-2 mb-5 px-3 py-1.5 rounded-full bg-white/10 border border-white/20 backdrop-blur-sm" data-testid="workspace-hero-badge">
            <div className="relative">
              <Bell size={12} weight="fill" className="text-[#C9B6FF]" />
              <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-[#16A34A] aria-pulse-ring" />
            </div>
            <span className="text-[10px] font-extrabold uppercase tracking-[0.25em] text-white numeric">
              ARIA has {updatesCount} {updatesCount === 1 ? 'update' : 'updates'} waiting for you
            </span>
          </div>
        )}

        {/* Eyebrow */}
        <div className="inline-flex items-center gap-2 mb-2">
          <span className="block w-6 h-px bg-gradient-to-r from-[#C044E0] to-transparent" />
          <span className="text-[10px] font-bold uppercase tracking-[0.3em] text-[#C9B6FF] numeric">
            {brief?.greeting || 'Good morning'}{userName ? `, ${userName.split(' ')[0]}` : ''}
          </span>
        </div>

        {/* Hero */}
        <h1 className="font-display text-[2.4rem] md:text-[3rem] lg:text-[3.4rem] leading-[1.05] text-white max-w-3xl">
          Your sales workspace is ready.
        </h1>
        <p className="font-display-italic text-[17px] md:text-lg text-[#C9B6FF] mt-2 max-w-2xl">
          ARIA has reviewed your leads, conversations, follow-ups, and buying signals.
        </p>

        {/* Stats strip */}
        <div className="mt-6 flex flex-wrap items-center gap-2">
          {b.hot_leads > 0 && (
            <span className="px-3 py-1.5 rounded-full text-[11px] font-bold uppercase tracking-[0.18em] bg-[#FEE2E2] text-[#DC2626] border border-[#DC2626]/30 flex items-center gap-1.5 numeric" data-testid="hero-badge-hot">
              <Fire size={11} weight="fill" /> {b.hot_leads} Hot {b.hot_leads === 1 ? 'Lead' : 'Leads'}
            </span>
          )}
          {b.followups_due > 0 && (
            <span className="px-3 py-1.5 rounded-full text-[11px] font-bold uppercase tracking-[0.18em] bg-white/10 text-white border border-white/20 flex items-center gap-1.5 numeric" data-testid="hero-badge-followups">
              <Clock size={11} weight="fill" /> {b.followups_due} Follow-ups Due
            </span>
          )}
          {b.proposals > 0 && (
            <span className="px-3 py-1.5 rounded-full text-[11px] font-bold uppercase tracking-[0.18em] bg-white/10 text-white border border-white/20 flex items-center gap-1.5 numeric" data-testid="hero-badge-proposals">
              <FileText size={11} weight="fill" /> {b.proposals} Active Proposals
            </span>
          )}
        </div>

        {/* CTAs */}
        <div className="mt-6 flex flex-wrap gap-2.5">
          <button onClick={() => navigate('/follow-ups')} className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-extrabold uppercase tracking-[0.2em] bg-white text-[#1A0A2E] hover:bg-[#F4F0FF] transition-all shadow-lg numeric" data-testid="hero-cta-primary">
            <Fire size={13} weight="fill" className="text-[#DC2626]" /> Start with hot leads <ArrowRight size={12} weight="bold" />
          </button>
          <button onClick={() => navigate('/aria-agent/briefs')} className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-extrabold uppercase tracking-[0.2em] bg-white/10 hover:bg-white/20 text-white border border-white/20 backdrop-blur-sm transition-all numeric" data-testid="hero-cta-secondary">
            <Sparkle size={13} weight="fill" /> View today's brief
          </button>
        </div>
      </div>
    </div>
  );
};

export default WorkspaceHero;
