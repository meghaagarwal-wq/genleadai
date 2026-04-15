import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../config/api';
import { Lightning, Phone, EnvelopeSimple, WhatsappLogo, ArrowRight, Sparkle, Clock, Target, CheckCircle } from '@phosphor-icons/react';

const YourFiveToday = () => {
  const navigate = useNavigate();
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [doneIds, setDoneIds] = useState(new Set());

  useEffect(() => { fetchToday(); }, []);
  const fetchToday = async () => {
    try { const res = await api.get('/api/leads/your-five-today'); setLeads(res.data.leads || []); }
    catch(err) { console.error(err); }
    finally { setLoading(false); }
  };

  const markDone = (id) => { setDoneIds(prev => new Set([...prev, id])); };

  const tierColor = { hot: '#7C35DC', warm: '#D97706', cold: '#94A3B8' };
  const actionIcons = { call: Phone, email: EnvelopeSimple, whatsapp: WhatsappLogo };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-[#9B8AB0] text-sm">Loading your top leads...</div></div>;

  return (
    <div data-testid="your-five-today-page" className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: 'var(--gradient-brand)' }}>
          <Lightning size={22} className="text-white" weight="fill" />
        </div>
        <div>
          <h1 className="text-3xl font-extrabold text-[#1A0A2E] tracking-tight" style={{ fontFamily: 'Plus Jakarta Sans' }}>Your 5 Today</h1>
          <p className="text-sm text-[#5A4A7A] mt-0.5">AI-picked leads you should personally touch today</p>
        </div>
      </div>

      {leads.length === 0 ? (
        <div className="bg-white border border-[#E8E0F5] rounded-xl p-12 text-center" style={{ boxShadow: 'var(--shadow-card)' }}>
          <Target size={48} className="text-[#9B8AB0] mx-auto mb-4" weight="duotone" />
          <h3 className="text-lg font-bold text-[#1A0A2E] mb-2" style={{ fontFamily: 'Plus Jakarta Sans' }}>All clear for today!</h3>
          <p className="text-sm text-[#5A4A7A]">ARIA is handling the rest of your pipeline.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {leads.map((lead, idx) => {
            const done = doneIds.has(lead.id);
            const ActionIcon = actionIcons[lead._suggested_action?.type] || Phone;
            return (
              <div key={lead.id} className={`bg-white border rounded-xl p-6 transition-all ${done ? 'border-[#16A34A]/30 opacity-60' : 'border-[#E8E0F5] hover:shadow-[var(--shadow-hover)]'}`} style={{ boxShadow: done ? 'none' : 'var(--shadow-card)' }} data-testid={`today-lead-${idx}`}>
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-4">
                    <div className="w-12 h-12 rounded-xl flex items-center justify-center text-white text-lg font-bold shrink-0" style={{ background: 'var(--gradient-brand)', fontFamily: 'Plus Jakarta Sans' }}>
                      {idx + 1}
                    </div>
                    <div>
                      <div className="flex items-center gap-3 mb-1">
                        <h3 className="text-lg font-bold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{lead.first_name} {lead.last_name}</h3>
                        {lead.company_name && <span className="text-sm text-[#5A4A7A]">@ {lead.company_name}</span>}
                        <span className={`px-2 py-0.5 text-xs font-semibold uppercase rounded border ${lead.lead_type === 'B2B' ? 'bg-[#F4F0FF] text-[#7C35DC] border-[#7C35DC]/20' : 'bg-[#DCFCE7] text-[#16A34A] border-[#16A34A]/20'}`}>{lead.lead_type}</span>
                      </div>

                      {/* AI Reason - the key insight */}
                      <div className="flex items-start gap-2 mb-3 p-3 bg-[#F4F0FF] rounded-lg border border-[#E0D4F7]">
                        <Sparkle size={16} className="text-[#7C35DC] shrink-0 mt-0.5" weight="fill" />
                        <p className="text-sm font-semibold text-[#7C35DC]">{lead._reason}</p>
                      </div>

                      {/* Quick Info */}
                      <div className="flex items-center gap-4 text-xs text-[#5A4A7A]">
                        <span className="flex items-center gap-1"><Target size={12} /> ICP: <span className="font-mono font-bold" style={{ color: tierColor[lead.icp_tier] }}>{lead.icp_score}</span></span>
                        <span className="flex items-center gap-1"><Clock size={12} /> {lead._days_since_contact === 999 ? 'Never contacted' : `${lead._days_since_contact}d since contact`}</span>
                        <span>{lead.source_channel?.replace('_', ' ')}</span>
                        {lead.aria_state && <span className="text-[#9B8AB0]">ARIA: {lead.aria_state?.replace(/_/g, ' ')}</span>}
                      </div>

                      {/* Suggested Action */}
                      {lead._suggested_action && (
                        <div className="mt-3 flex items-center gap-2">
                          <span className="text-xs font-semibold text-[#9B8AB0] uppercase tracking-wider" style={{ fontFamily: 'Plus Jakarta Sans' }}>Suggested:</span>
                          <span className="text-xs text-[#5A4A7A]">{lead._suggested_action.reason}</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex flex-col items-end gap-2 shrink-0">
                    {!done ? (
                      <>
                        <div className="flex items-center gap-2">
                          <button className="p-2 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-lg hover:bg-[#F9F5FF] hover:text-[#7C35DC] hover:border-[#7C35DC]/20 transition-all" title="Call" data-testid={`today-call-${idx}`}><Phone size={16} /></button>
                          <button className="p-2 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-lg hover:bg-[#F9F5FF] hover:text-[#7C35DC] hover:border-[#7C35DC]/20 transition-all" title="WhatsApp" data-testid={`today-whatsapp-${idx}`}><WhatsappLogo size={16} /></button>
                          <button className="p-2 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-lg hover:bg-[#F9F5FF] hover:text-[#7C35DC] hover:border-[#7C35DC]/20 transition-all" title="Email" data-testid={`today-email-${idx}`}><EnvelopeSimple size={16} /></button>
                        </div>
                        <button onClick={() => navigate(`/leads/${lead.id}`)} className="flex items-center gap-1 text-xs text-[#7C35DC] hover:text-[#6B28C8] font-semibold" data-testid={`today-view-${idx}`}>
                          View Profile <ArrowRight size={12} />
                        </button>
                        <button onClick={() => markDone(lead.id)} className="flex items-center gap-1 text-xs text-[#16A34A] hover:text-[#16A34A]/80 font-medium mt-1" data-testid={`today-done-${idx}`}>
                          <CheckCircle size={14} /> Mark Done
                        </button>
                      </>
                    ) : (
                      <div className="flex items-center gap-1 text-[#16A34A]">
                        <CheckCircle size={20} weight="fill" />
                        <span className="text-sm font-semibold">Done</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Footer */}
      <div className="bg-[#F4F0FF] border border-[#E0D4F7] rounded-xl p-4 text-center">
        <p className="text-sm text-[#7C35DC] font-medium">ARIA is handling the rest of your pipeline. These {leads.length} are yours for today.</p>
      </div>
    </div>
  );
};

export default YourFiveToday;
