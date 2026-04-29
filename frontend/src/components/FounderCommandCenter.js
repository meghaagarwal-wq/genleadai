import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../config/api';
import AriaInsightCard from './AriaInsightCard';
import AriaAvatar from './AriaAvatar';
import { Warning, Fire, Clock, ChartLineDown, Coins, ArrowRight, GraduationCap, Sparkle, User, UsersThree, Briefcase, CheckCircle, Robot } from '@phosphor-icons/react';

const ROLES = [
  { id: 'founder', label: 'Founder', icon: Briefcase },
  { id: 'manager', label: 'Sales Manager', icon: UsersThree },
  { id: 'rep', label: 'Sales Rep', icon: User },
];

const ROLE_SECTIONS = {
  founder: ['leakage', 'money_risk', 'brief', 'hot_untouched', 'response', 'graveyard', 'source', 'lost'],
  manager: ['hot_untouched', 'response', 'graveyard', 'source', 'lost', 'money_risk'],
  rep:     ['brief', 'hot_untouched', 'money_risk', 'graveyard'],
};

const SectionCard = ({ children, className = '', testId, tone }) => (
  <div className={`relative bg-white border rounded-2xl ${className}`} style={{ borderColor: tone === 'urgent' ? 'rgba(220,38,38,0.2)' : '#E8E0F5', boxShadow: 'var(--shadow-card)' }} data-testid={testId}>
    {children}
  </div>
);

const FounderCommandCenter = () => {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [role, setRole] = useState('founder');

  useEffect(() => {
    api.get('/api/insights/founder-command-center')
      .then(res => setData(res.data))
      .catch(() => {});
  }, []);

  if (!data) return null;
  const visible = ROLE_SECTIONS[role];
  const show = (k) => visible.includes(k);

  return (
    <div className="space-y-5" data-testid="founder-command-center">
      {/* Role tabs */}
      <div className="flex items-center gap-1 p-1 bg-white border border-[#E8E0F5] rounded-xl w-fit shadow-sm" data-testid="role-tabs">
        {ROLES.map(r => {
          const Icon = r.icon;
          const active = role === r.id;
          return (
            <button key={r.id} onClick={() => setRole(r.id)} className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider transition-all ${active ? 'text-white' : 'text-[#5A4A7A] hover:text-[#7C35DC]'}`} style={active ? { background: 'var(--gradient-brand)' } : {}} data-testid={`role-tab-${r.id}`}>
              <Icon size={13} weight="fill" /> {r.label} View
            </button>
          );
        })}
      </div>

      {/* Revenue Leakage Score — flagship card */}
      {show('leakage') && (
        <SectionCard tone="urgent" testId="leakage-card" className="overflow-hidden">
          <div className="absolute top-0 left-0 right-0 h-1" style={{ background: 'linear-gradient(90deg, #DC2626 0%, #C044E0 50%, #7C35DC 100%)' }} />
          <div className="p-5 md:p-6 grid grid-cols-1 md:grid-cols-[auto_1fr] gap-5 items-center">
            <div className="flex items-center justify-center w-32 h-32 rounded-full relative" style={{ background: 'conic-gradient(#DC2626 0%, #C044E0 ' + data.revenue_leakage.score_pct + '%, #F4F0FF ' + data.revenue_leakage.score_pct + '%, #F4F0FF 100%)' }}>
              <div className="absolute inset-2 rounded-full bg-white flex items-center justify-center flex-col">
                <span className="text-3xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{data.revenue_leakage.score_pct}%</span>
                <span className="text-[9px] font-bold uppercase tracking-wider text-[#9B8AB0]">Leakage</span>
              </div>
            </div>
            <div>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#DC2626]">Revenue Leakage Score</span>
                <Warning size={14} className="text-[#DC2626]" weight="fill" />
              </div>
              <h3 className="text-xl md:text-2xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{data.revenue_leakage.headline}</h3>
              <p className="text-sm text-[#5A4A7A] mt-1">{data.revenue_leakage.subhead}</p>
              <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                {data.revenue_leakage.breakdown.map((b, i) => (
                  <div key={i} className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#FFF8F8] border border-[#FEE2E2]" data-testid={`leakage-breakdown-${b.key}`}>
                    <span className="w-1.5 h-1.5 rounded-full bg-[#DC2626]" />
                    <span className="text-xs font-medium text-[#1A0A2E]">{b.label}</span>
                  </div>
                ))}
              </div>
              <button onClick={() => navigate('/follow-ups')} className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-bold text-white" style={{ fontFamily: 'Plus Jakarta Sans', background: 'linear-gradient(135deg, #DC2626 0%, #C044E0 100%)' }} data-testid="leakage-cta">
                {data.revenue_leakage.cta} <ArrowRight size={13} weight="bold" />
              </button>
            </div>
          </div>
        </SectionCard>
      )}

      {/* Two-column: Money at Risk + Daily Brief */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {show('money_risk') && (
          <SectionCard className="lg:col-span-2" testId="money-at-risk-card">
            <div className="p-5 border-b border-[#F0ECF9] flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #DC2626 0%, #C044E0 100%)' }}>
                  <Coins size={16} className="text-white" weight="fill" />
                </div>
                <div>
                  <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#DC2626]">Today's Money At Risk</div>
                  <h3 className="text-2xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{data.money_at_risk.total_label} Pipeline At Risk</h3>
                </div>
              </div>
              <button onClick={() => navigate('/follow-ups')} className="hidden md:inline-flex items-center gap-1.5 btn-gradient px-3 py-1.5 rounded-lg text-xs font-bold" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid="money-risk-cta">{data.money_at_risk.cta} <ArrowRight size={11} /></button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-[#FAFAFA]">
                  <tr className="text-left text-[10px] font-bold uppercase tracking-wider text-[#9B8AB0]">
                    <th className="px-5 py-2.5">Lead</th><th className="px-3 py-2.5">Deal</th><th className="px-3 py-2.5">Risk Reason</th><th className="px-3 py-2.5">Owner</th><th className="px-3 py-2.5"></th>
                  </tr>
                </thead>
                <tbody>
                  {data.money_at_risk.rows.map((r, i) => (
                    <tr key={i} className="border-t border-[#F4F0FF] hover:bg-[#FFF8F8] transition-colors" data-testid={`money-risk-row-${i}`}>
                      <td className="px-5 py-3 font-semibold text-[#1A0A2E]">{r.name}</td>
                      <td className="px-3 py-3 font-mono font-bold text-[#DC2626]">₹{(r.deal_value/100000).toFixed(1)}L</td>
                      <td className="px-3 py-3 text-xs text-[#5A4A7A]">{r.reason}</td>
                      <td className="px-3 py-3 text-xs text-[#5A4A7A]">{r.owner}</td>
                      <td className="px-3 py-3"><button onClick={() => r.lead_id ? navigate(`/leads/${r.lead_id}`) : navigate('/leads')} className="text-[10px] font-bold uppercase tracking-wider text-[#7C35DC] hover:text-[#1A0A2E] transition-colors">{r.action} →</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </SectionCard>
        )}
        {show('brief') && (
          <SectionCard className="overflow-hidden" testId="daily-brief-card">
            <div className="p-5 text-white relative overflow-hidden" style={{ background: 'linear-gradient(135deg, #0E0820 0%, #2A155A 100%)' }}>
              <div className="absolute -top-12 -right-12 w-40 h-40 rounded-full opacity-30" style={{ background: 'radial-gradient(circle, #C044E0 0%, transparent 70%)' }} />
              <div className="relative">
                <div className="flex items-center gap-2.5 mb-3">
                  <AriaAvatar size={36} tone="default" />
                  <div>
                    <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#C044E0]">ARIA says</div>
                    <h4 className="text-base font-extrabold" style={{ fontFamily: 'Plus Jakarta Sans' }}>Daily Brief</h4>
                  </div>
                </div>
                <ul className="space-y-1.5 text-[13px] text-white/85">
                  {data.daily_brief.lines.map((l, i) => (<li key={i} className="flex items-start gap-2"><span className="text-[#C044E0] mt-1">•</span> {l}</li>))}
                </ul>
                <button className="mt-4 w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-xs font-bold border border-white/20 hover:bg-white/10 transition-colors" data-testid="daily-brief-cta"><Sparkle size={11} weight="fill" /> {data.daily_brief.cta}</button>
              </div>
            </div>
          </SectionCard>
        )}
      </div>

      {/* Hot Leads Untouched */}
      {show('hot_untouched') && (
        <SectionCard tone="urgent" testId="hot-untouched-card">
          <div className="p-5 border-b border-[#FEE2E2] flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #DC2626 0%, #C044E0 100%)' }}>
                <Fire size={16} className="text-white" weight="fill" />
              </div>
              <div>
                <h3 className="text-base font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{data.hot_leads_untouched.count} Hot Leads Untouched</h3>
                <p className="text-xs text-[#5A4A7A] mt-0.5">High intent, zero recorded action. Every hour cools them off.</p>
              </div>
            </div>
            <button onClick={() => navigate('/leads')} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold border border-[#DC2626]/30 text-[#DC2626] hover:bg-[#FFF8F8] transition-colors" data-testid="hot-untouched-cta">Assign & Follow Up Now <ArrowRight size={11} /></button>
          </div>
          <div className="divide-y divide-[#F4F0FF]">
            {data.hot_leads_untouched.rows.map((r, i) => (
              <div key={i} className="px-5 py-3 flex items-center justify-between gap-3 hover:bg-[#FFF8F8] transition-colors" data-testid={`hot-untouched-row-${i}`}>
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-9 h-9 rounded-full bg-white border border-[#FEE2E2] flex items-center justify-center flex-shrink-0">
                    <span className="text-xs font-bold text-[#DC2626]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{(r.name?.[0] || '?').toUpperCase()}</span>
                  </div>
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-[#1A0A2E] truncate">{r.name}</div>
                    <div className="text-xs text-[#9B8AB0] truncate">{r.source} · {r.hours_since}h since captured · Owner: {r.owner}</div>
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-[#FEE2E2] text-[#DC2626] border border-[#DC2626]/20">ICP {r.score}</span>
                  <button onClick={() => r.lead_id ? navigate(`/leads/${r.lead_id}`) : navigate('/leads')} className="text-[10px] font-bold uppercase tracking-wider text-[#7C35DC] hover:text-[#1A0A2E]">Open →</button>
                </div>
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {/* First Response + Proposal Graveyard side-by-side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {show('response') && (
          <SectionCard testId="first-response-card">
            <div className="p-5">
              <div className="flex items-center gap-2.5 mb-3">
                <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: 'var(--gradient-brand)' }}>
                  <Clock size={16} className="text-white" weight="fill" />
                </div>
                <div>
                  <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#7C35DC]">First Response Time</div>
                  <h3 className="text-2xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{data.first_response.avg_hours}h <span className="text-sm text-[#9B8AB0] font-medium">avg · target {data.first_response.target_minutes}min</span></h3>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2 mt-3">
                <div className="p-3 rounded-lg bg-[#DCFCE7] border border-[#16A34A]/20">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-[#16A34A]">Best rep</div>
                  <div className="text-sm font-bold text-[#1A0A2E] mt-0.5">{data.first_response.best_rep.name}</div>
                  <div className="text-xs text-[#5A4A7A]">{data.first_response.best_rep.minutes} min</div>
                </div>
                <div className="p-3 rounded-lg bg-[#FFF8F8] border border-[#DC2626]/20">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-[#DC2626]">Slowest rep</div>
                  <div className="text-sm font-bold text-[#1A0A2E] mt-0.5">{data.first_response.slowest_rep.name}</div>
                  <div className="text-xs text-[#5A4A7A]">{Math.round(data.first_response.slowest_rep.minutes/60)}h</div>
                </div>
              </div>
              <div className="mt-3 p-3 rounded-lg bg-[#F9F5FF] border border-[#E0D4F7] text-xs text-[#5A4A7A] flex items-start gap-2">
                <Robot size={14} className="text-[#7C35DC] mt-0.5 flex-shrink-0" weight="fill" /> {data.first_response.insight}
              </div>
              <div className="mt-2 text-[11px] text-[#9B8AB0]">{data.first_response.pending_first_response} leads pending first response</div>
            </div>
          </SectionCard>
        )}
        {show('graveyard') && (
          <SectionCard testId="proposal-graveyard-card">
            <div className="p-5 border-b border-[#F0ECF9] flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #5A4A7A 0%, #1A0A2E 100%)' }}>
                <GraduationCap size={16} className="text-white" weight="fill" />
              </div>
              <div>
                <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#5A4A7A]">Proposal Graveyard</div>
                <h3 className="text-base font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{data.proposal_graveyard.count} proposals waiting too long</h3>
              </div>
            </div>
            <div className="divide-y divide-[#F4F0FF]">
              {data.proposal_graveyard.rows.map((r, i) => (
                <div key={i} className="px-5 py-3 flex items-center justify-between gap-3" data-testid={`graveyard-row-${i}`}>
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-[#1A0A2E] truncate">{r.name}</div>
                    <div className="text-[11px] text-[#9B8AB0]">{r.value_label} · {r.days_since}d ago · {r.owner}</div>
                  </div>
                  <button onClick={() => r.lead_id ? navigate(`/leads/${r.lead_id}`) : navigate('/leads')} className="text-[10px] font-bold uppercase tracking-wider text-[#7C35DC] hover:text-[#1A0A2E] flex-shrink-0">{r.action} →</button>
                </div>
              ))}
            </div>
            <div className="p-3 border-t border-[#F0ECF9]">
              <button onClick={() => navigate('/leads')} className="w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-xs font-bold border border-[#7C35DC]/30 text-[#7C35DC] hover:bg-[#F4F0FF]" data-testid="graveyard-cta">Revive Stuck Proposals <ArrowRight size={11} /></button>
            </div>
          </SectionCard>
        )}
      </div>

      {/* Source Quality + Lost Reasons side-by-side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {show('source') && (
          <SectionCard testId="source-quality-card">
            <div className="p-5 border-b border-[#F0ECF9]">
              <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#7C35DC]">Lead Quality by Source</div>
              <h3 className="text-base font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Where your best pipeline is born</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-[#FAFAFA]">
                  <tr className="text-left text-[10px] font-bold uppercase tracking-wider text-[#9B8AB0]">
                    <th className="px-5 py-2.5">Source</th><th className="px-3 py-2.5">Total</th><th className="px-3 py-2.5">Hot</th><th className="px-3 py-2.5">Calls</th><th className="px-3 py-2.5">Pipeline</th>
                  </tr>
                </thead>
                <tbody>
                  {data.source_quality.rows.map((r, i) => (
                    <tr key={i} className="border-t border-[#F4F0FF]" data-testid={`source-row-${i}`}>
                      <td className="px-5 py-2.5 font-semibold text-[#1A0A2E]">{r.source}</td>
                      <td className="px-3 py-2.5 font-mono text-[#5A4A7A]">{r.total}</td>
                      <td className="px-3 py-2.5"><span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-[#FEE2E2] text-[#DC2626]">{r.hot}</span></td>
                      <td className="px-3 py-2.5 font-mono text-[#5A4A7A]">{r.calls_booked}</td>
                      <td className="px-3 py-2.5 font-mono font-bold text-[#7C35DC]">{r.pipeline_label}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="p-3 bg-[#F9F5FF] border-t border-[#E0D4F7] text-xs text-[#5A4A7A] flex items-start gap-2">
              <Sparkle size={12} className="text-[#7C35DC] mt-0.5 flex-shrink-0" weight="fill" /> {data.source_quality.insight}
            </div>
          </SectionCard>
        )}
        {show('lost') && (
          <SectionCard testId="lost-reasons-card">
            <div className="p-5 border-b border-[#F0ECF9]">
              <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#7C35DC]">Why Leads Are Being Lost</div>
              <h3 className="text-base font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Marketing problem or sales problem?</h3>
            </div>
            <div className="divide-y divide-[#F4F0FF]">
              {data.lost_reasons.rows.map((r, i) => (
                <div key={i} className="px-5 py-3 flex items-center justify-between" data-testid={`lost-row-${i}`}>
                  <div>
                    <div className="text-sm font-semibold text-[#1A0A2E]">{r.reason}</div>
                    <div className="text-[11px] text-[#9B8AB0]">{r.insight}</div>
                  </div>
                  <span className="text-lg font-extrabold text-[#7C35DC]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{r.count}</span>
                </div>
              ))}
            </div>
            <div className="p-3 bg-[#F9F5FF] border-t border-[#E0D4F7] text-xs text-[#5A4A7A] flex items-start gap-2">
              <Robot size={12} className="text-[#7C35DC] mt-0.5 flex-shrink-0" weight="fill" /> {data.lost_reasons.insight}
            </div>
          </SectionCard>
        )}
      </div>
    </div>
  );
};

export default FounderCommandCenter;
