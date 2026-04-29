import React, { useEffect, useState } from 'react';
import { Sparkle, CheckCircle, ChatCircle, CalendarCheck, Buildings, GraduationCap, Megaphone, FileText, Snowflake, Trophy, WhatsappLogo, EnvelopeSimple, Crown } from '@phosphor-icons/react';
import api from '../config/api';
import PageHeader from '../components/PageHeader';

const ICONS = {
  inbound_qualification: ChatCircle,
  demo_booking: CalendarCheck,
  founder_led: Crown,
  agency_nurture: Buildings,
  saas_trial: Sparkle,
  webinar_followup: Megaphone,
  proposal_followup: FileText,
  lead_revival: Snowflake,
  high_ticket: Trophy,
  whatsapp_first: WhatsappLogo,
};

const Playbooks = () => {
  const [playbooks, setPlaybooks] = useState([]);
  const [busy, setBusy] = useState(null);

  const load = () => api.get('/api/aria-agent/playbooks').then(r => setPlaybooks(r.data.playbooks || [])).catch(() => {});
  useEffect(() => { load(); }, []);

  const toggle = async (p) => {
    setBusy(p.id);
    try {
      if (p.active) await api.post(`/api/aria-agent/playbooks/${p.id}/deactivate`);
      else await api.post(`/api/aria-agent/playbooks/${p.id}/activate`);
      await load();
    } catch (err) {
      alert(err?.response?.data?.detail || 'Failed');
    } finally { setBusy(null); }
  };

  return (
    <div className="space-y-6" data-testid="playbooks-page">
      <PageHeader
        eyebrow="ARIA · Sales Playbooks"
        title="Choose how ARIA runs your sales motion"
        subtitle="Each playbook is a proven AI sales behavior. Activate one and ARIA will start handling leads using that motion immediately."
      />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {playbooks.map((p, idx) => {
          const Icon = ICONS[p.id] || ChatCircle;
          return (
            <div key={p.id} className={`bg-white border rounded-2xl overflow-hidden flex flex-col aria-card-lift aria-fade-up aria-fade-up-${(idx % 4) + 1}`} style={{ boxShadow: 'var(--shadow-card)', borderColor: p.active ? '#7C35DC' : '#E8E0F5' }} data-testid={`playbook-card-${p.id}`}>
              {p.active && <div className="h-1 w-full" style={{ background: 'var(--gradient-brand-horizontal)' }} />}
              <div className="px-5 pt-5 pb-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="w-12 h-12 rounded-2xl flex items-center justify-center flex-shrink-0 relative" style={{ background: p.active ? 'var(--gradient-brand)' : '#F4F0FF' }}>
                    <Icon size={22} weight="fill" className={p.active ? 'text-white' : 'text-[#7C35DC]'} />
                    {p.active && <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-[#16A34A] border-2 border-white aria-pulse-ring" />}
                  </div>
                  {p.active && (
                    <span className="px-2.5 py-1 rounded-md text-[10px] font-extrabold uppercase tracking-[0.2em] bg-[#DCFCE7] text-[#16A34A] border border-[#16A34A]/30 flex items-center gap-1 numeric" data-testid={`playbook-active-${p.id}`}>
                      <CheckCircle size={11} weight="fill" /> ACTIVE
                    </span>
                  )}
                </div>
                <h3 className="font-display text-[1.5rem] leading-[1.1] text-[#1A0A2E] mt-4">{p.name}</h3>
                <p className="text-xs text-[#9B8AB0] mt-1.5 numeric uppercase tracking-[0.1em]">{p.best_for}</p>
              </div>
              <div className="px-5 pb-5 flex-1 flex flex-col">
                <p className="text-[14px] text-[#5A4A7A] leading-relaxed mb-5">{p.what_aria_does}</p>

                <div className="mt-auto space-y-3">
                  <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-[0.2em] numeric">
                    <span className="text-[#9B8AB0]">Touchpoints</span>
                    <span className="font-display text-2xl text-[#7C35DC] numeric leading-none">{p.touchpoints}</span>
                  </div>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {p.channels.slice(0, 4).map(c => (
                      <span key={c} className="px-2.5 py-1 rounded-md text-[10px] font-bold bg-[#F4F0FF] text-[#7C35DC] border border-[#7C35DC]/15 numeric uppercase tracking-[0.1em]">{c}</span>
                    ))}
                  </div>
                  <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#9B8AB0] pt-2 numeric">Handoff triggers</div>
                  <ul className="space-y-1">
                    {(p.handoff_triggers || []).slice(0, 3).map((h, i) => (
                      <li key={i} className="text-xs text-[#5A4A7A] flex items-start gap-1.5">
                        <span className="text-[#7C35DC] mt-0.5">•</span>{h}
                      </li>
                    ))}
                  </ul>
                </div>

                <button onClick={() => toggle(p)} disabled={busy === p.id}
                  className={`mt-6 w-full py-3 rounded-xl text-[11px] font-extrabold uppercase tracking-[0.2em] numeric transition-all disabled:opacity-50 ${p.active ? 'bg-white border border-[#7C35DC]/30 text-[#7C35DC] hover:bg-[#F4F0FF]' : 'btn-gradient text-white aria-card-lift'}`}
                  data-testid={`playbook-toggle-${p.id}`}>
                  {busy === p.id ? '…' : p.active ? 'Deactivate Playbook' : 'Activate Playbook'}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default Playbooks;
