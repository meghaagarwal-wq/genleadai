import React, { useEffect, useState } from 'react';
import { Robot, ShieldCheck, Lightning, ChatCircle, ArrowRight, CheckCircle } from '@phosphor-icons/react';
import api from '../config/api';
import PageHeader from '../components/PageHeader';

const HumanHandoff = () => {
  const [rules, setRules] = useState([]);
  const [alerts, setAlerts] = useState([]);

  useEffect(() => {
    Promise.all([
      api.get('/api/aria-agent/handoff/rules'),
      api.get('/api/aria-agent/handoff/alerts'),
    ]).then(([r, a]) => {
      setRules(r.data?.rules || []);
      setAlerts(a.data?.alerts || []);
    }).catch(() => {});
  }, []);

  return (
    <div className="space-y-6" data-testid="human-handoff-page">
      <PageHeader
        eyebrow="ARIA · Smart Handoff"
        title="ARIA knows when to bring you in"
        subtitle="ARIA handles the first layer of every conversation. The moment a lead needs a real human — pricing, custom scope, founder ask — ARIA escalates with full context."
      />

      {/* Live alerts */}
      <div className="bg-white border border-[#E8E0F5] rounded-2xl overflow-hidden" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="handoff-alerts-card">
        <div className="px-5 py-4 border-b border-[#F0ECF9] flex items-center justify-between">
          <div>
            <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#DC2626]" style={{ fontFamily: 'Plus Jakarta Sans' }}>FOUNDER ATTENTION NEEDED</div>
            <h3 className="text-lg font-extrabold text-[#1A0A2E] mt-0.5" style={{ fontFamily: 'Plus Jakarta Sans' }}>{alerts.length} live escalations</h3>
          </div>
          <Lightning size={28} weight="fill" className="text-[#DC2626]" />
        </div>
        <div className="divide-y divide-[#F0ECF9]">
          {alerts.length === 0 && <div className="p-12 text-center text-sm text-[#9B8AB0]">All clear — ARIA is handling everything right now.</div>}
          {alerts.map((a, idx) => (
            <div key={a.id || idx} className="px-5 py-5 grid grid-cols-1 md:grid-cols-[1fr_auto] gap-4 items-start" data-testid={`handoff-alert-${idx}`}>
              <div>
                <div className="flex items-center gap-2 flex-wrap mb-2">
                  <span className="text-base font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{a.first_name} {a.last_name}</span>
                  {a.company_name && <span className="text-sm text-[#9B8AB0]">· {a.company_name}</span>}
                  <span className="px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-[0.15em] bg-[#FEE2E2] text-[#DC2626] border border-[#DC2626]/30">{a.trigger_label}</span>
                  {a.icp_score && <span className="px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-[0.15em] bg-[#F4F0FF] text-[#7C35DC] border border-[#7C35DC]/20">ICP {a.icp_score}</span>}
                </div>
                <div className="text-sm text-[#1A0A2E] font-semibold mb-1" style={{ fontFamily: 'Plus Jakarta Sans' }}>Why ARIA escalated</div>
                <p className="text-sm text-[#5A4A7A] mb-3">{a.why}</p>
                <div className="text-sm text-[#1A0A2E] font-semibold mb-1" style={{ fontFamily: 'Plus Jakarta Sans' }}>Recommended action</div>
                <p className="text-sm text-[#5A4A7A] mb-3">{a.recommended_action}</p>
                <div className="rounded-xl p-3 bg-[#FAF7FF] border border-[#EDE5FA]">
                  <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#7C35DC] mb-1" style={{ fontFamily: 'Plus Jakarta Sans' }}>Suggested founder message</div>
                  <div className="text-sm text-[#1A0A2E] italic">"{a.suggested_message}"</div>
                </div>
              </div>
              <div className="flex flex-row md:flex-col gap-2 flex-wrap md:flex-nowrap">
                <button className="px-3 py-2 rounded-xl text-xs font-bold uppercase tracking-[0.1em] bg-white border border-[#E8E0F5] text-[#5A4A7A] hover:bg-[#F4F0FF] hover:text-[#7C35DC] hover:border-[#7C35DC]/30" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid={`handoff-aria-reply-${idx}`}>Let ARIA reply</button>
                <button className="px-3 py-2 rounded-xl text-xs font-bold uppercase tracking-[0.1em] bg-white border border-[#7C35DC]/30 text-[#7C35DC] hover:bg-[#F4F0FF]" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid={`handoff-take-over-${idx}`}>Take over</button>
                <button className="px-3 py-2 rounded-xl text-xs font-bold uppercase tracking-[0.1em] btn-gradient" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid={`handoff-send-note-${idx}`}>Send founder note</button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Rules */}
      <div className="bg-white border border-[#E8E0F5] rounded-2xl p-5" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="handoff-rules-card">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: 'var(--gradient-brand)' }}>
            <ShieldCheck size={18} weight="fill" className="text-white" />
          </div>
          <div>
            <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC]" style={{ fontFamily: 'Plus Jakarta Sans' }}>HANDOFF RULES</div>
            <h3 className="text-base font-extrabold text-[#1A0A2E] mt-0.5" style={{ fontFamily: 'Plus Jakarta Sans' }}>When ARIA hands a lead to a human</h3>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
          {rules.map(r => (
            <div key={r.id} className="flex items-center gap-2 px-3 py-2 rounded-xl bg-[#FAF7FF] border border-[#EDE5FA] text-sm text-[#1A0A2E]" data-testid={`handoff-rule-${r.id}`}>
              <CheckCircle size={14} weight="fill" className="text-[#7C35DC] flex-shrink-0" />
              {r.label}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default HumanHandoff;
