import React, { useEffect, useState } from 'react';
import { Robot, Fire, ChartLineUp, Clock, Target, ChatCircle, Lightning, Warning, FileText, CheckCircle, Copy, X } from '@phosphor-icons/react';
import api from '../config/api';

const TEMP_STYLES = {
  hot:  { label: 'HOT',  cls: 'bg-[#FEE2E2] text-[#DC2626] border-[#DC2626]/30' },
  warm: { label: 'WARM', cls: 'bg-[#FEF3C7] text-[#D97706] border-[#D97706]/30' },
  cold: { label: 'COLD', cls: 'bg-[#F1F5F9] text-[#5A4A7A] border-[#94A3B8]/30' },
};

const INTENT_STYLES = {
  high:   'bg-[#DCFCE7] text-[#16A34A] border-[#16A34A]/30',
  medium: 'bg-[#F4F0FF] text-[#7C35DC] border-[#7C35DC]/30',
  low:    'bg-[#F1F5F9] text-[#5A4A7A] border-[#94A3B8]/30',
};

const URGENCY_LABEL = { this_week: 'THIS WEEK', this_month: 'THIS MONTH', exploring: 'EXPLORING' };

const KV = ({ icon: Icon, label, value, accent = '#7C35DC' }) => (
  <div className="flex items-start gap-2.5">
    <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5" style={{ background: `${accent}15`, border: `1px solid ${accent}33` }}>
      <Icon size={13} weight="fill" style={{ color: accent }} />
    </div>
    <div className="min-w-0 flex-1">
      <div className="text-[10px] font-bold uppercase tracking-[0.15em] text-[#9B8AB0]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{label}</div>
      <div className="text-xs text-[#1A0A2E] mt-0.5 leading-relaxed">{value}</div>
    </div>
  </div>
);

const AriaReadPanel = ({ leadId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [briefOpen, setBriefOpen] = useState(false);
  const [brief, setBrief] = useState(null);
  const [briefLoading, setBriefLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!leadId) return;
    setLoading(true);
    api.get(`/api/aria-agent/aria-read/${leadId}`)
      .then(r => setData(r.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [leadId]);

  const generateBrief = async () => {
    setBriefOpen(true);
    setBriefLoading(true);
    setBrief(null);
    try {
      const res = await api.post(`/api/aria-agent/founder-brief/${leadId}`);
      setBrief(res.data);
    } catch (err) {
      setBrief(null);
    } finally { setBriefLoading(false); }
  };

  const copyBrief = () => {
    if (!brief) return;
    const text = [
      `FOUNDER BRIEF · ${brief.lead_name}`,
      `Company: ${brief.company} · Role: ${brief.role}`,
      `Source: ${brief.source}`, ``,
      `What they need: ${brief.what_they_need}`,
      `Pain point: ${brief.main_pain_point}`,
      `Urgency: ${brief.urgency} · Budget: ${brief.budget_signal}`,
      `Objection: ${brief.objection}`, ``,
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

  const copyResponse = () => {
    if (!data?.suggested_response) return;
    navigator.clipboard.writeText(data.suggested_response);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading) {
    return (
      <div className="bg-white border border-[#E8E0F5] rounded-xl p-4 animate-pulse" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="aria-read-panel-loading">
        <div className="h-4 w-32 bg-[#F4F0FF] rounded mb-3" />
        <div className="space-y-2">{[1,2,3,4].map(i => <div key={i} className="h-10 bg-[#FAF7FF] rounded-lg" />)}</div>
      </div>
    );
  }
  if (!data) return null;

  const temp = TEMP_STYLES[data.temperature] || TEMP_STYLES.warm;
  const intentCls = INTENT_STYLES[data.intent] || INTENT_STYLES.medium;

  return (
    <>
      <div className="bg-white border-2 rounded-xl overflow-hidden" style={{ boxShadow: 'var(--shadow-card)', borderColor: data.handoff_needed ? '#DC2626' : '#7C35DC' }} data-testid="aria-read-panel">
        <div className="px-4 py-3 flex items-center gap-2.5" style={{ background: 'linear-gradient(135deg,#1A0F38 0%,#7C35DC 100%)' }}>
          <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-white/15 border border-white/20 flex-shrink-0">
            <Robot size={15} weight="fill" className="text-white" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-[9px] font-bold uppercase tracking-[0.25em] text-[#C9B6FF]" style={{ fontFamily: 'Plus Jakarta Sans' }}>ARIA'S READ · LIVE</div>
            <div className="text-xs font-extrabold text-white" style={{ fontFamily: 'Plus Jakarta Sans' }}>Conversation intelligence</div>
          </div>
          {data.handoff_needed && (
            <span className="px-2 py-0.5 rounded-md text-[9px] font-extrabold uppercase tracking-[0.15em] bg-[#FEE2E2] text-[#DC2626] border border-[#DC2626]/40 flex items-center gap-1" data-testid="aria-read-handoff-needed">
              <Warning size={10} weight="fill" /> NEEDS FOUNDER
            </span>
          )}
        </div>

        <div className="p-4 space-y-3">
          {/* Status badges */}
          <div className="flex flex-wrap gap-1.5">
            <span className={`px-2 py-0.5 rounded-md text-[10px] font-extrabold uppercase tracking-[0.15em] border ${temp.cls}`} data-testid="aria-read-temperature">{temp.label}</span>
            <span className={`px-2 py-0.5 rounded-md text-[10px] font-extrabold uppercase tracking-[0.15em] border ${intentCls}`} data-testid="aria-read-intent">{(data.intent || 'low').toUpperCase()} INTENT</span>
            <span className="px-2 py-0.5 rounded-md text-[10px] font-extrabold uppercase tracking-[0.15em] bg-[#FAF7FF] text-[#7C35DC] border border-[#7C35DC]/20" data-testid="aria-read-urgency">{URGENCY_LABEL[data.urgency] || data.urgency}</span>
            <span className="px-2 py-0.5 rounded-md text-[10px] font-extrabold uppercase tracking-[0.15em] bg-[#FAF7FF] text-[#7C35DC] border border-[#7C35DC]/20" data-testid="aria-read-fit">FIT {data.fit_score}/10</span>
          </div>

          {/* ARIA thinks */}
          <div className="rounded-lg p-3 bg-[#FAF7FF] border border-[#EDE5FA]" data-testid="aria-read-thinks">
            <div className="text-[10px] font-bold uppercase tracking-[0.15em] text-[#7C35DC] mb-1" style={{ fontFamily: 'Plus Jakarta Sans' }}>ARIA THINKS</div>
            <p className="text-xs text-[#1A0A2E] italic leading-relaxed">"{data.aria_thinks}"</p>
          </div>

          {/* KV intel */}
          <div className="space-y-2.5 pt-1">
            <KV icon={Target} label="Main need" value={data.main_need} accent="#7C35DC" />
            <KV icon={Fire} label="Main pain" value={data.main_pain} accent="#DC2626" />
            <KV icon={ChatCircle} label="Current objection" value={data.current_objection} accent="#D97706" />
            <KV icon={Lightning} label="Best next action" value={data.best_next_action} accent="#16A34A" />
          </div>

          {/* Suggested response */}
          <div className="rounded-lg p-3 border border-[#7C35DC]/25" style={{ background: 'linear-gradient(135deg, rgba(124,53,220,0.04) 0%, rgba(192,68,224,0.03) 100%)' }} data-testid="aria-read-suggested-response">
            <div className="flex items-center justify-between mb-1.5">
              <div className="text-[10px] font-bold uppercase tracking-[0.15em] text-[#7C35DC]" style={{ fontFamily: 'Plus Jakarta Sans' }}>SUGGESTED RESPONSE</div>
              <button onClick={copyResponse} className="text-[10px] font-bold uppercase tracking-[0.1em] text-[#7C35DC] hover:underline flex items-center gap-1" data-testid="aria-read-copy-response">
                {copied ? <CheckCircle size={11} weight="fill" /> : <Copy size={11} weight="fill" />}{copied ? 'Copied' : 'Copy'}
              </button>
            </div>
            <p className="text-xs text-[#1A0A2E] italic leading-relaxed">"{data.suggested_response}"</p>
          </div>

          <button onClick={generateBrief} className="w-full btn-gradient py-2.5 rounded-xl text-xs font-extrabold uppercase tracking-[0.1em] flex items-center justify-center gap-1.5" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid="aria-read-generate-brief">
            <FileText size={13} weight="fill" /> Generate Founder Brief
          </button>
          <p className="text-[10px] text-[#9B8AB0] text-center">Your CRM stores leads. ARIA works them.</p>
        </div>
      </div>

      {/* Founder Brief Modal */}
      {briefOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" data-testid="founder-brief-modal">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setBriefOpen(false)} />
          <div className="relative bg-white rounded-2xl max-w-2xl w-full max-h-[85vh] overflow-y-auto" style={{ boxShadow: '0 20px 60px rgba(0,0,0,0.3)' }}>
            <div className="sticky top-0 z-10 flex items-center justify-between px-6 py-4 border-b border-[#F0ECF9] bg-white">
              <div>
                <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC]" style={{ fontFamily: 'Plus Jakarta Sans' }}>ARIA · FOUNDER BRIEF</div>
                <h3 className="text-xl font-extrabold text-[#1A0A2E] mt-0.5" style={{ fontFamily: 'Plus Jakarta Sans' }}>{brief?.lead_name || 'Generating brief…'}</h3>
              </div>
              <button onClick={() => setBriefOpen(false)} className="p-2 text-[#9B8AB0] hover:text-[#1A0A2E] rounded-lg hover:bg-[#F4F0FF]" data-testid="founder-brief-modal-close">
                <X size={18} />
              </button>
            </div>
            {briefLoading && <div className="p-12 text-center text-sm text-[#9B8AB0]">ARIA is preparing the brief…</div>}
            {brief && !briefLoading && (
              <div className="p-6 space-y-4">
                <div className="text-xs text-[#5A4A7A]">{brief.company} · {brief.role} · {brief.source}</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {[
                    { k: 'What they need', v: brief.what_they_need },
                    { k: 'Pain point', v: brief.main_pain_point },
                    { k: 'Current process', v: brief.current_process },
                    { k: 'Objection', v: brief.objection },
                    { k: 'Urgency', v: brief.urgency },
                    { k: 'Budget', v: brief.budget_signal },
                  ].map(f => (
                    <div key={f.k} className="bg-[#FAF7FF] border border-[#EDE5FA] rounded-xl p-3">
                      <div className="text-[10px] font-bold uppercase tracking-[0.15em] text-[#9B8AB0]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{f.k}</div>
                      <div className="text-sm text-[#1A0A2E] mt-1">{f.v}</div>
                    </div>
                  ))}
                </div>
                <div className="rounded-2xl p-4" style={{ background: 'linear-gradient(135deg,#1A0F38 0%,#7C35DC 100%)' }}>
                  <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#C9B6FF]" style={{ fontFamily: 'Plus Jakarta Sans' }}>RECOMMENDED PITCH</div>
                  <div className="text-sm font-extrabold text-white mt-1" style={{ fontFamily: 'Plus Jakarta Sans' }}>{brief.recommended_pitch}</div>
                  <div className="mt-2.5 px-3 py-2 rounded-lg bg-white/10 border border-white/15">
                    <div className="text-[10px] font-bold uppercase tracking-[0.15em] text-[#C9B6FF] mb-1">Suggested opening</div>
                    <div className="text-xs italic text-white">"{brief.suggested_opening}"</div>
                  </div>
                </div>
                <div>
                  <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC] mb-2" style={{ fontFamily: 'Plus Jakarta Sans' }}>QUESTIONS TO ASK</div>
                  <ol className="space-y-1.5">
                    {(brief.questions_to_ask || []).map((q, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-[#1A0A2E]"><span className="text-[#7C35DC] font-extrabold">{i + 1}.</span>{q}</li>
                    ))}
                  </ol>
                </div>
                <div className="rounded-xl p-3 bg-[#FAF7FF] border border-[#EDE5FA] flex items-start gap-2">
                  <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: 'var(--gradient-brand)' }}>
                    <Robot size={12} weight="fill" className="text-white" />
                  </div>
                  <div>
                    <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#7C35DC]" style={{ fontFamily: 'Plus Jakarta Sans' }}>ARIA'S RECOMMENDATION</div>
                    <div className="text-xs text-[#1A0A2E] mt-1 leading-relaxed">{brief.aria_recommendation}</div>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2 pt-2">
                  <button onClick={copyBrief} className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white border border-[#E8E0F5] text-[#5A4A7A] hover:bg-[#F4F0FF] hover:text-[#7C35DC] hover:border-[#7C35DC]/30 text-xs font-bold uppercase tracking-[0.1em]" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid="modal-brief-copy">
                    {copied ? <CheckCircle size={13} weight="fill" /> : <Copy size={13} weight="fill" />}{copied ? 'Copied' : 'Copy Brief'}
                  </button>
                  <button className="flex items-center gap-2 btn-gradient px-4 py-2 rounded-xl text-xs font-bold uppercase tracking-[0.1em]" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid="modal-brief-mark-reviewed">
                    <CheckCircle size={13} weight="fill" /> Mark as Reviewed
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
};

export default AriaReadPanel;
