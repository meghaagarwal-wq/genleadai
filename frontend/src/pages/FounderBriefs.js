import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileText, Copy, PaperPlaneTilt, CheckCircle, ArrowRight, Robot, Lightning, Sparkle } from '@phosphor-icons/react';
import api from '../config/api';
import PageHeader from '../components/PageHeader';

const TEMP_BADGE = {
  hot: { label: 'HOT', cls: 'bg-[#FEE2E2] text-[#DC2626] border-[#DC2626]/30' },
  warm: { label: 'WARM', cls: 'bg-[#FEF3C7] text-[#D97706] border-[#D97706]/30' },
  cold: { label: 'COLD', cls: 'bg-[#F1F5F9] text-[#5A4A7A] border-[#94A3B8]/30' },
};

const FounderBriefs = () => {
  const navigate = useNavigate();
  const [leads, setLeads] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [brief, setBrief] = useState(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api.get('/api/leads?limit=20').then(r => {
      const ranked = (r.data?.leads || []).slice().sort((a, b) => (b.icp_score || 0) - (a.icp_score || 0));
      setLeads(ranked);
      if (ranked.length > 0) selectLead(ranked[0].id);
    }).catch(() => {});
  }, []);

  const selectLead = async (leadId) => {
    setActiveId(leadId);
    setLoading(true);
    setBrief(null);
    try {
      const res = await api.post(`/api/aria-agent/founder-brief/${leadId}`);
      setBrief(res.data);
    } catch (err) {
      setBrief(null);
    } finally { setLoading(false); }
  };

  const copyBrief = () => {
    if (!brief) return;
    const text = [
      `FOUNDER BRIEF · ${brief.lead_name}`,
      `Company: ${brief.company} · Role: ${brief.role}`,
      `Source: ${brief.source}`, ``,
      `What they need: ${brief.what_they_need}`,
      `Pain point: ${brief.main_pain_point}`,
      `Current process: ${brief.current_process}`,
      `Urgency: ${brief.urgency} · Budget: ${brief.budget_signal}`,
      `Objection: ${brief.objection}`,
      `Temperature: ${brief.lead_temperature?.toUpperCase()}`, ``,
      `Recommended pitch: ${brief.recommended_pitch}`,
      `Suggested opening: ${brief.suggested_opening}`, ``,
      `Questions to ask:`,
      ...(brief.questions_to_ask || []).map((q, i) => `${i + 1}. ${q}`), ``,
      `ARIA's recommendation: ${brief.aria_recommendation}`,
    ].join('\n');
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6" data-testid="founder-briefs-page">
      <PageHeader
        eyebrow="ARIA · Founder Briefs"
        title="Pre-call briefs, written by ARIA"
        subtitle="Before every sales call, ARIA prepares everything you need to know — the lead's pain, urgency, objections, and the exact opening line that will land."
      />

      <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-4">
        {/* Lead list */}
        <div className="bg-white border border-[#E8E0F5] rounded-2xl overflow-hidden" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="founder-briefs-lead-list">
          <div className="px-4 py-3 border-b border-[#F0ECF9]">
            <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC]" style={{ fontFamily: 'Plus Jakarta Sans' }}>UPCOMING + HIGH-INTENT</div>
            <div className="text-sm font-extrabold text-[#1A0A2E] mt-0.5" style={{ fontFamily: 'Plus Jakarta Sans' }}>Pick a lead</div>
          </div>
          <div className="divide-y divide-[#F0ECF9] max-h-[70vh] overflow-y-auto">
            {leads.map(l => {
              const temp = (l.lead_temperature || (l.icp_score >= 80 ? 'hot' : l.icp_score >= 50 ? 'warm' : 'cold'));
              const t = TEMP_BADGE[temp] || TEMP_BADGE.warm;
              return (
                <button key={l.id} onClick={() => selectLead(l.id)}
                  className={`w-full text-left px-4 py-3 transition-colors ${activeId === l.id ? 'bg-[#F9F5FF]' : 'hover:bg-[#FAF7FF]'}`}
                  data-testid={`founder-brief-lead-${l.id}`}>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-extrabold text-[#1A0A2E]">{l.first_name} {l.last_name}</span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${t.cls}`}>{t.label}</span>
                  </div>
                  <div className="text-xs text-[#9B8AB0] mt-1 truncate">{l.company_name || '—'} · ICP {l.icp_score || '—'}</div>
                </button>
              );
            })}
            {leads.length === 0 && (
              <div className="p-6 text-xs text-[#9B8AB0] text-center">No leads yet.</div>
            )}
          </div>
        </div>

        {/* Brief panel */}
        <div className="bg-white border border-[#E8E0F5] rounded-2xl overflow-hidden" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="founder-brief-panel">
          {loading && (
            <div className="p-12 text-center" data-testid="founder-brief-loading">
              <div className="inline-flex items-center gap-2 text-sm text-[#7C35DC] font-semibold">
                <Sparkle size={16} weight="fill" className="animate-pulse" />
                ARIA is reading the lead's history and preparing your brief…
              </div>
              <p className="text-xs text-[#9B8AB0] mt-2">Usually takes 4–8 seconds.</p>
            </div>
          )}
          {!loading && !brief && <div className="p-12 text-center text-sm text-[#9B8AB0]">Select a lead to see ARIA's founder brief.</div>}
          {brief && (
            <>
              <div className="px-6 py-5 border-b border-[#F0ECF9] flex items-start justify-between gap-3" style={{ background: 'linear-gradient(135deg, rgba(124,53,220,0.06) 0%, rgba(192,68,224,0.04) 100%)' }}>
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC]" style={{ fontFamily: 'Plus Jakarta Sans' }}>FOUNDER BRIEF</div>
                    {brief.ai_powered && (
                      <span className="px-1.5 py-0.5 rounded text-[9px] font-extrabold uppercase tracking-[0.15em] bg-[#DCFCE7] text-[#16A34A] border border-[#16A34A]/30 flex items-center gap-1" data-testid="founder-brief-ai-badge">
                        <Sparkle size={9} weight="fill" /> AI-POWERED
                      </span>
                    )}
                  </div>
                  <h2 className="text-2xl font-extrabold text-[#1A0A2E] mt-1" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid="founder-brief-name">{brief.lead_name}</h2>
                  <p className="text-sm text-[#5A4A7A]">{brief.company} · {brief.role} · {brief.source}</p>
                </div>
                <span className={`px-2 py-1 rounded-md text-[11px] font-bold border ${TEMP_BADGE[brief.lead_temperature]?.cls || TEMP_BADGE.warm.cls}`}>{(brief.lead_temperature || 'warm').toUpperCase()}</span>
              </div>

              <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-4">
                {[
                  { label: 'What they need', value: brief.what_they_need },
                  { label: 'Main pain point', value: brief.main_pain_point },
                  { label: 'Current process', value: brief.current_process },
                  { label: 'Objection', value: brief.objection },
                  { label: 'Urgency', value: brief.urgency },
                  { label: 'Budget signal', value: brief.budget_signal },
                ].map(f => (
                  <div key={f.label} className="bg-[#FAF7FF] border border-[#EDE5FA] rounded-xl p-3">
                    <div className="text-[10px] font-bold uppercase tracking-[0.15em] text-[#9B8AB0]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{f.label}</div>
                    <div className="text-sm text-[#1A0A2E] mt-1.5 leading-relaxed">{f.value}</div>
                  </div>
                ))}
              </div>

              <div className="mx-6 mb-4 rounded-2xl p-5" style={{ background: 'linear-gradient(135deg,#1A0F38 0%,#7C35DC 100%)' }} data-testid="founder-brief-pitch">
                <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#C9B6FF]" style={{ fontFamily: 'Plus Jakarta Sans' }}>RECOMMENDED PITCH</div>
                <div className="text-base font-extrabold text-white mt-1" style={{ fontFamily: 'Plus Jakarta Sans' }}>{brief.recommended_pitch}</div>
                <div className="mt-3 px-3 py-2 rounded-lg bg-white/10 border border-white/15">
                  <div className="text-[10px] font-bold uppercase tracking-[0.15em] text-[#C9B6FF] mb-1">Suggested opening line</div>
                  <div className="text-sm italic text-white">"{brief.suggested_opening}"</div>
                </div>
              </div>

              <div className="px-6 pb-4">
                <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC] mb-2" style={{ fontFamily: 'Plus Jakarta Sans' }}>QUESTIONS TO ASK ON THE CALL</div>
                <ol className="space-y-1.5">
                  {(brief.questions_to_ask || []).map((q, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-[#1A0A2E]"><span className="text-[#7C35DC] font-extrabold">{i + 1}.</span>{q}</li>
                  ))}
                </ol>
              </div>

              <div className="mx-6 mb-6 rounded-xl p-4 bg-[#FAF7FF] border border-[#EDE5FA] flex items-start gap-3" data-testid="founder-brief-aria-rec">
                <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: 'var(--gradient-brand)' }}>
                  <Robot size={14} weight="fill" className="text-white" />
                </div>
                <div>
                  <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#7C35DC]" style={{ fontFamily: 'Plus Jakarta Sans' }}>ARIA's recommendation</div>
                  <div className="text-sm text-[#1A0A2E] mt-1 leading-relaxed">{brief.aria_recommendation}</div>
                </div>
              </div>

              <div className="px-6 pb-6 flex flex-wrap gap-2">
                <button onClick={copyBrief} className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white border border-[#E8E0F5] text-[#5A4A7A] hover:bg-[#F4F0FF] hover:text-[#7C35DC] hover:border-[#7C35DC]/30 text-xs font-bold uppercase tracking-[0.1em]" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid="founder-brief-copy">
                  {copied ? <CheckCircle size={13} weight="fill" /> : <Copy size={13} weight="fill" />}{copied ? 'Copied' : 'Copy Brief'}
                </button>
                <button className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white border border-[#E8E0F5] text-[#5A4A7A] hover:bg-[#F4F0FF] hover:text-[#7C35DC] hover:border-[#7C35DC]/30 text-xs font-bold uppercase tracking-[0.1em]" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid="founder-brief-send">
                  <PaperPlaneTilt size={13} weight="fill" /> Send to Founder
                </button>
                <button onClick={() => navigate(`/leads/${brief.lead_id}`)} className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white border border-[#E8E0F5] text-[#5A4A7A] hover:bg-[#F4F0FF] hover:text-[#7C35DC] hover:border-[#7C35DC]/30 text-xs font-bold uppercase tracking-[0.1em]" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid="founder-brief-view-lead">
                  Open Lead <ArrowRight size={13} />
                </button>
                <button className="flex items-center gap-2 btn-gradient px-4 py-2 rounded-xl text-xs font-bold uppercase tracking-[0.1em]" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid="founder-brief-followup">
                  <Lightning size={13} weight="fill" /> Generate Follow-up
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default FounderBriefs;
