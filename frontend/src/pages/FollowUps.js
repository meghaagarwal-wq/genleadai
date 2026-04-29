import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../config/api';
import { ListChecks, Clock, Check, ArrowRight, Sparkle, Phone, EnvelopeSimple, WhatsappLogo, CalendarBlank } from '@phosphor-icons/react';
import { usePlan } from '../context/PlanContext';
import LockBadge from '../components/LockBadge';
import PageHeader from '../components/PageHeader';
import AriaInsightCard from '../components/AriaInsightCard';

const TYPE_ICONS = { call: Phone, email: EnvelopeSimple, whatsapp: WhatsappLogo, meeting: CalendarBlank };

const FollowUps = () => {
  const navigate = useNavigate();
  const { hasFeature } = usePlan();
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [bucket, setBucket] = useState('today');
  const [busyId, setBusyId] = useState(null);

  useEffect(() => {
    api.get('/api/leads?limit=200').then(res => setLeads(res.data?.leads || [])).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const refreshLeads = async () => {
    try { const res = await api.get('/api/leads?limit=200'); setLeads(res.data?.leads || []); } catch (err) { /* swallow */ }
  };

  const markComplete = async (e, lead) => {
    e.stopPropagation();
    if (busyId) return;
    setBusyId(lead.id);
    try {
      await api.post('/api/activities', { lead_id: lead.id, activity_type: 'note_added', subject: 'Follow-up completed', body: 'Marked complete from Follow-Up Command Center.' });
      await api.patch(`/api/leads/${lead.id}`, { next_followup_at: null });
      await refreshLeads();
    } catch (err) {
      alert(err?.response?.data?.detail || 'Failed to mark complete');
    } finally { setBusyId(null); }
  };

  const reschedule = async (e, lead, days) => {
    e.stopPropagation();
    if (busyId) return;
    setBusyId(lead.id);
    try {
      const next = new Date(Date.now() + days * 86400000).toISOString();
      await api.patch(`/api/leads/${lead.id}`, { next_followup_at: next });
      await refreshLeads();
    } catch (err) {
      alert(err?.response?.data?.detail || 'Failed to reschedule');
    } finally { setBusyId(null); }
  };

  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const endOfToday = startOfToday + 24 * 3600 * 1000;

  const buckets = {
    today: leads.filter(l => l.next_followup_at && new Date(l.next_followup_at).getTime() >= startOfToday && new Date(l.next_followup_at).getTime() < endOfToday),
    overdue: leads.filter(l => l.next_followup_at && new Date(l.next_followup_at).getTime() < startOfToday && !['won', 'lost', 'unqualified'].includes(l.status)),
    upcoming: leads.filter(l => l.next_followup_at && new Date(l.next_followup_at).getTime() >= endOfToday),
    completed: leads.filter(l => ['won', 'lost'].includes(l.status)),
  };

  const tabs = [
    { id: 'today', label: 'Due today', icon: Clock, count: buckets.today.length, color: '#7C35DC' },
    { id: 'overdue', label: 'Overdue', icon: ListChecks, count: buckets.overdue.length, color: '#DC2626' },
    { id: 'upcoming', label: 'Upcoming', icon: Sparkle, count: buckets.upcoming.length, color: '#D97706' },
    { id: 'completed', label: 'Completed', icon: Check, count: buckets.completed.length, color: '#16A34A' },
  ];

  const visible = buckets[bucket] || [];

  return (
    <div className="space-y-6" data-testid="follow-ups-page">
      <PageHeader
        eyebrow="Daily Action Engine"
        title="Follow-Up Command Center"
        subtitle="The place where no lead is allowed to quietly go cold. Follow-up discipline = revenue movement."
        actions={!hasFeature('overdue_alerts') ? <LockBadge featureKey="overdue_alerts" label="Overdue alerts on Growth+" size="lg" /> : null}
      />

      {buckets.overdue.length > 0 && (
        <AriaInsightCard
          title="ARIA Priority Queue"
          message={`${buckets.overdue.length} ${buckets.overdue.length === 1 ? 'lead' : 'leads'} ${buckets.overdue.length === 1 ? 'is' : 'are'} most likely to go cold if not contacted today. Hit them first.`}
          ctaLabel="View Overdue Leads"
          onCtaClick={() => setBucket('overdue')}
          tone="urgent"
        />
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {tabs.map(t => {
          const Icon = t.icon;
          const active = bucket === t.id;
          return (
            <button key={t.id} onClick={() => setBucket(t.id)} className={`bg-white border rounded-xl p-4 text-left transition-all ${active ? 'border-[#7C35DC] ring-2 ring-[#7C35DC]/20' : 'border-[#E8E0F5] hover:border-[#7C35DC]/30'}`} style={{ boxShadow: active ? 'var(--shadow-card)' : 'none' }} data-testid={`follow-bucket-${t.id}`}>
              <div className="flex items-center gap-2 mb-2">
                <Icon size={16} weight="fill" style={{ color: t.color }} />
                <span className="text-xs font-bold uppercase tracking-wider text-[#5A4A7A]">{t.label}</span>
              </div>
              <span className="text-2xl font-extrabold text-[#1A0A2E]">{t.count}</span>
            </button>
          );
        })}
      </div>

      <div className="bg-white border border-[#E8E0F5] rounded-xl overflow-hidden" style={{ boxShadow: 'var(--shadow-card)' }}>
        {loading ? (
          <div className="p-12 text-center text-sm text-[#9B8AB0]">Loading…</div>
        ) : visible.length === 0 ? (
          <div className="p-16 text-center">
            <ListChecks size={36} className="text-[#D4C5E8] mx-auto mb-3" weight="duotone" />
            <p className="text-sm font-semibold text-[#1A0A2E]">All clear in this bucket</p>
            <p className="text-xs text-[#9B8AB0] mt-1">Beautiful follow-up discipline. Keep going.</p>
          </div>
        ) : (
          <div className="divide-y divide-[#F0ECF9]">
            {visible.map(l => {
              const due = l.next_followup_at ? new Date(l.next_followup_at) : null;
              const overdueDays = due ? Math.floor((Date.now() - due.getTime()) / 86400000) : 0;
              const channel = (l.metadata?.last_channel) || 'call';
              const Icon = TYPE_ICONS[channel] || Phone;
              return (
                <div key={l.id} onClick={() => navigate(`/leads/${l.id}`)} role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter') navigate(`/leads/${l.id}`); }} className="w-full flex items-center gap-3 px-5 py-3.5 hover:bg-[#F9F5FF] transition-colors text-left cursor-pointer" data-testid={`followup-row-${l.id}`}>
                  <div className="w-9 h-9 rounded-full bg-[#F4F0FF] border border-[#E0D4F7] flex items-center justify-center flex-shrink-0">
                    <Icon size={14} className="text-[#7C35DC]" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-semibold text-[#1A0A2E] truncate">{l.first_name} {l.last_name}</span>
                      <span className="text-xs text-[#9B8AB0] truncate">· {l.company_name || '—'}</span>
                      {bucket === 'overdue' && overdueDays > 0 && (
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-bold uppercase bg-[#FEE2E2] text-[#DC2626]" data-testid={`overdue-badge-${l.id}`}>{overdueDays}d overdue</span>
                      )}
                    </div>
                    <div className="text-xs text-[#5A4A7A] mt-0.5">
                      {due ? `Due ${due.toLocaleDateString()}` : 'No date set'} · ICP {l.icp_score} · {l.status?.replace('_', ' ')}
                    </div>
                  </div>
                  {bucket !== 'completed' && (
                    <div className="flex items-center gap-1.5 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
                      <button onClick={(e) => reschedule(e, l, 1)} disabled={busyId === l.id} className="px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-wider rounded-md bg-white border border-[#E8E0F5] text-[#5A4A7A] hover:bg-[#F4F0FF] hover:text-[#7C35DC] hover:border-[#7C35DC]/30 transition-colors disabled:opacity-50" data-testid={`followup-reschedule-1d-${l.id}`} title="Reschedule by 1 day">+1d</button>
                      <button onClick={(e) => reschedule(e, l, 3)} disabled={busyId === l.id} className="px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-wider rounded-md bg-white border border-[#E8E0F5] text-[#5A4A7A] hover:bg-[#F4F0FF] hover:text-[#7C35DC] hover:border-[#7C35DC]/30 transition-colors disabled:opacity-50" data-testid={`followup-reschedule-3d-${l.id}`} title="Reschedule by 3 days">+3d</button>
                      <button onClick={(e) => markComplete(e, l)} disabled={busyId === l.id} className="px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-wider rounded-md bg-[#DCFCE7] border border-[#16A34A]/30 text-[#16A34A] hover:bg-[#16A34A] hover:text-white transition-colors disabled:opacity-50 flex items-center gap-1" data-testid={`followup-complete-${l.id}`} title="Mark follow-up complete"><Check size={11} weight="bold" />Done</button>
                    </div>
                  )}
                  <ArrowRight size={14} className="text-[#7C35DC] flex-shrink-0 ml-1" />
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default FollowUps;
