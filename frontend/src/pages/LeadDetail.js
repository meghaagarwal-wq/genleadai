import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../config/api';
import AriaConversationPanel from '../components/AriaConversationPanel';
import AriaReadPanel from '../components/AriaReadPanel';
import LeadJourneyTab from '../components/LeadJourneyTab';
import TouchpointProgressCard from '../components/TouchpointProgressCard';
import LeadOptInBanner from '../components/LeadOptInBanner';
import IcpPickerForLead from '../components/IcpPickerForLead';
import AriaConfidenceDial from '../components/AriaConfidenceDial';
import CrmSyncBadge from '../components/CrmSyncBadge';
import DpdpDeleteButton from '../components/DpdpDeleteButton';
import {
  ArrowLeft,
  Phone,
  EnvelopeSimple,
  WhatsappLogo,
  CalendarBlank,
  NoteBlank,
  Lightning,
  Sparkle,
  Clock,
  MapPin,
  Buildings,
  Briefcase,
  Tag,
  Paperclip,
  Eye,
  Fire,
  CheckCircle,
} from '@phosphor-icons/react';
import { toast } from 'sonner';

const LeadDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [lead, setLead] = useState(null);
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [scoring, setScoring] = useState(false);
  const [activeTab, setActiveTab] = useState('timeline');
  const [showLogActivity, setShowLogActivity] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editData, setEditData] = useState({});
  const [engagement, setEngagement] = useState(null);
  const [sendingMagnet, setSendingMagnet] = useState(false);
  const [bestTime, setBestTime] = useState(null);
  const [confidence, setConfidence] = useState(null);

  useEffect(() => {
    fetchLead();
    fetchActivities();
    fetchEngagement();
    fetchBestTime();
    fetchConfidence();
  }, [id]);

  const fetchConfidence = async () => {
    try {
      const r = await api.get(`/api/aria/confidence/${id}`);
      setConfidence(r.data);
    } catch {
      setConfidence(null);
    }
  };

  const fetchLead = async () => {
    try {
      const res = await api.get(`/api/leads/${id}`);
      setLead(res.data);
      setEditData(res.data);
    } catch (err) {
      console.error('Failed to fetch lead', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchActivities = async () => {
    try {
      const res = await api.get(`/api/leads/${id}/activities`);
      setActivities(res.data.activities);
    } catch (err) {
      console.error('Failed to fetch activities', err);
    }
  };

  const handleScore = async () => {
    setScoring(true);
    try {
      const res = await api.post('/api/ai/score', { lead_id: id });
      await fetchLead();
      await fetchActivities();
    } catch (err) {
      console.error('Scoring failed', err);
    } finally {
      setScoring(false);
    }
  };

  const handleUpdateLead = async () => {
    try {
      const updates = {};
      ['first_name', 'last_name', 'email', 'phone', 'company_name', 'job_title', 'industry', 'status', 'notes'].forEach(k => {
        if (editData[k] !== lead[k]) updates[k] = editData[k];
      });
      if (Object.keys(updates).length > 0) {
        await api.patch(`/api/leads/${id}`, updates);
        await fetchLead();
        if (updates.status) await fetchActivities();
      }
      setEditing(false);
    } catch (err) {
      console.error('Update failed', err);
    }
  };

  const handleLogActivity = async (activityData) => {
    try {
      await api.post('/api/activities', { lead_id: id, ...activityData });
      await fetchActivities();
      setShowLogActivity(false);
    } catch (err) {
      console.error('Failed to log activity', err);
    }
  };

  const fetchEngagement = async () => {
    try {
      const res = await api.get(`/api/lead-magnets/engagement/${id}`);
      setEngagement(res.data);
    } catch (err) {
      // silent — engagement is optional
    }
  };

  const fetchBestTime = async () => {
    try {
      const res = await api.get(`/api/aria/best-time-to-call/${id}`);
      setBestTime(res.data);
    } catch (err) {
      // silent
    }
  };

  const handleSendMagnet = async () => {
    setSendingMagnet(true);
    try {
      const res = await api.post(`/api/leads/${id}/send-lead-magnet`);
      toast.success(`Brochure sent via ${res.data.channel === 'whatsapp' ? 'WhatsApp' : 'Email'}`, {
        description: 'You\'ll see opens here as soon as they engage.',
      });
      await fetchActivities();
      await fetchEngagement();
    } catch (err) {
      const msg = err?.response?.data?.detail || 'Failed to send brochure';
      toast.error(msg, { description: msg.includes('not enabled') ? 'Configure it in Settings → Lead Magnet.' : '' });
    } finally {
      setSendingMagnet(false);
    }
  };

  const formatRelative = (iso) => {
    if (!iso) return '—';
    try {
      const d = new Date(iso);
      const diff = (Date.now() - d.getTime()) / 1000;
      if (diff < 60) return 'just now';
      if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
      if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
      return `${Math.round(diff / 86400)}d ago`;
    } catch { return iso; }
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-[#9B8AB0] text-sm">Loading lead...</div></div>;
  if (!lead) return <div className="text-[#5A4A7A]">Lead not found</div>;

  const tierColor = { hot: '#7C35DC', warm: '#D97706', cold: '#94A3B8' };
  const STATUSES = ['new', 'contacted', 'qualified', 'unqualified', 'proposal_sent', 'negotiation', 'won', 'lost', 'nurture'];

  const INTEGRATION_EVENT_META = {
    email_sent: { label: 'Email sent', color: '#7C35DC' },
    email_opened: { label: 'Email opened', color: '#16A34A' },
    email_clicked: { label: 'Link clicked', color: '#16A34A' },
    replied: { label: 'Replied', color: '#16A34A' },
    bounced: { label: 'Bounced', color: '#DC2626' },
    unsubscribed: { label: 'Unsubscribed', color: '#9B8AB0' },
    interested: { label: 'Interested', color: '#16A34A' },
    not_interested: { label: 'Not interested', color: '#9B8AB0' },
    meeting_scheduled: { label: 'Meeting booked', color: '#7C35DC' },
    pushed_to_lemlist: { label: 'Pushed to Lemlist', color: '#7C35DC' },
    pushed_to_saleshandy: { label: 'Pushed to SalesHandy', color: '#16A34A' },
    auto_pushed_to_lemlist: { label: 'Auto-pushed (rule) → Lemlist', color: '#7C35DC' },
    auto_pushed_to_saleshandy: { label: 'Auto-pushed (rule) → SalesHandy', color: '#16A34A' },
  };
  const platformOf = (act) => {
    const meta = act.metadata || {};
    if (meta.platform === 'lemlist') return 'Lemlist';
    if (meta.platform === 'saleshandy') return 'SalesHandy';
    if ((act.created_by || '').includes('lemlist')) return 'Lemlist';
    if ((act.created_by || '').includes('saleshandy')) return 'SalesHandy';
    return null;
  };

  const activityIcon = (type) => {
    const icons = { call: Phone, email_sent: EnvelopeSimple, email_received: EnvelopeSimple, email_opened: EnvelopeSimple, email_clicked: EnvelopeSimple, replied: EnvelopeSimple, bounced: EnvelopeSimple, whatsapp_sent: WhatsappLogo, whatsapp_received: WhatsappLogo, meeting_scheduled: CalendarBlank, meeting_done: CalendarBlank, note_added: NoteBlank, status_changed: Lightning, score_updated: Sparkle, pushed_to_lemlist: Sparkle, pushed_to_saleshandy: Sparkle, auto_pushed_to_lemlist: Lightning, auto_pushed_to_saleshandy: Lightning, interested: Sparkle, meeting_booked: CalendarBlank };
    const Icon = icons[type] || NoteBlank;
    return <Icon size={16} weight="duotone" />;
  };

  return (
    <div data-testid="lead-detail-page" className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <button onClick={() => navigate('/leads')} className="flex items-center gap-2 text-[#5A4A7A] hover:text-[#7C35DC] transition-colors text-sm" data-testid="back-to-leads-btn">
          <ArrowLeft size={16} /> Back to Leads
        </button>
        <DpdpDeleteButton leadId={id} leadName={`${lead.first_name} ${lead.last_name}`} onDeleted={() => navigate('/leads')} />
      </div>

      {/* Compliance opt-in banner */}
      <LeadOptInBanner lead={lead} onUpdated={fetchLead} />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Lead Profile */}
        <div className="lg:col-span-1 space-y-4">
          {/* Profile Card */}
          <div className="bg-white border border-[#E8E0F5] rounded-xl p-6" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="lead-profile-card">
            <div className="flex items-start justify-between mb-4">
              <div>
                {editing ? (
                  <div className="space-y-2">
                    <input value={editData.first_name} onChange={(e) => setEditData({...editData, first_name: e.target.value})} className="bg-[#FAFAFA] border border-[#E8E0F5] text-[#1A0A2E] px-2 py-1 rounded-lg text-lg font-bold w-full" />
                    <input value={editData.last_name} onChange={(e) => setEditData({...editData, last_name: e.target.value})} className="bg-[#FAFAFA] border border-[#E8E0F5] text-[#1A0A2E] px-2 py-1 rounded-lg text-lg font-bold w-full" />
                  </div>
                ) : (
                  <h2 className="text-2xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{lead.first_name} {lead.last_name}</h2>
                )}
                <div className="mt-2 flex items-center gap-2 flex-wrap">
                  <span className={`inline-block px-2 py-0.5 text-xs font-semibold uppercase tracking-wider rounded border ${lead.lead_type === 'B2B' ? 'bg-[#F4F0FF] text-[#7C35DC] border-[#7C35DC]/20' : 'bg-[#DCFCE7] text-[#16A34A] border-[#16A34A]/20'}`}>{lead.lead_type}</span>
                  <CrmSyncBadge leadId={lead.id || id} />
                </div>
              </div>
              <button onClick={() => editing ? handleUpdateLead() : setEditing(true)} className="text-sm text-[#7C35DC] hover:text-[#6B28C8] font-semibold transition-colors" data-testid="edit-lead-btn">{editing ? 'Save' : 'Edit'}</button>
            </div>

            {/* Aria Confidence Dial */}
            {confidence && (
              <div className="mb-4 p-4 rounded-xl bg-white border border-[#E8E0F5] flex items-center gap-4" data-testid="lead-aria-confidence">
                <AriaConfidenceDial
                  score={confidence.score}
                  color={confidence.color}
                  factors={confidence.factors}
                  size="lg"
                />
                <div className="flex-1 min-w-0">
                  <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#9B8AB0]">Aria confidence</div>
                  <div className="text-base font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>
                    {confidence.label === 'hot' ? 'Hot lead — act now' : confidence.label === 'warm' ? 'Warming up' : 'Cold — nurture'}
                  </div>
                  <ul className="mt-1 space-y-0.5">
                    {(confidence.factors || []).map((f, i) => (
                      <li key={i} className="text-[11px] text-[#5A4A7A] flex items-center gap-1">
                        <span className={`inline-block w-1.5 h-1.5 rounded-full ${f.delta > 0 ? 'bg-[#16A34A]' : f.delta < 0 ? 'bg-[#DC2626]' : 'bg-[#9B8AB0]'}`} />
                        <span className="font-mono text-[10px] text-[#9B8AB0] w-7">{f.delta > 0 ? '+' : ''}{f.delta}</span>
                        {f.label}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}

            {/* ICP Score */}
            <div className="mb-6 p-4 rounded-xl bg-[#F4F0FF] border border-[#E0D4F7]">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold uppercase tracking-[0.15em] text-[#9B8AB0]" style={{ fontFamily: 'Plus Jakarta Sans' }}>ICP Score</span>
                <span className="text-xs font-semibold uppercase px-2 py-0.5 rounded" style={{ color: tierColor[lead.icp_tier], background: lead.icp_tier === 'hot' ? '#F4E6FD' : lead.icp_tier === 'warm' ? '#FEF3C7' : '#F1F5F9' }}>{lead.icp_tier}</span>
              </div>
              <div className="flex items-end gap-2">
                <span className="text-4xl font-extrabold font-mono" style={{ color: tierColor[lead.icp_tier], fontFamily: 'JetBrains Mono' }}>{lead.icp_score}</span>
                <span className="text-sm text-[#9B8AB0] mb-1">/ 100</span>
              </div>
              <div className="w-full h-2 bg-[#E8E0F5] rounded-full mt-3 overflow-hidden">
                <div className="h-full rounded-full transition-all duration-500" style={{ width: `${lead.icp_score}%`, background: lead.icp_score >= 70 ? 'var(--gradient-brand-horizontal)' : tierColor[lead.icp_tier] }}></div>
              </div>
              {lead.icp_reasoning && lead.icp_reasoning.length > 0 && (
                <ul className="mt-3 space-y-1">
                  {lead.icp_reasoning.map((r, i) => (
                    <li key={i} className="text-xs text-[#5A4A7A] flex items-start gap-1.5"><span className="text-[#9B8AB0] mt-0.5">-</span> {r}</li>
                  ))}
                </ul>
              )}
              <button onClick={handleScore} disabled={scoring}
                className="mt-3 w-full flex items-center justify-center gap-2 px-3 py-2 bg-[#F4F0FF] text-[#7C35DC] border border-[#7C35DC]/20 rounded-lg hover:bg-[#F4F0FF]/80 transition-all text-sm font-medium disabled:opacity-50"
                data-testid="ai-score-btn" style={{ fontFamily: 'Plus Jakarta Sans' }}>
                <Sparkle size={16} weight="fill" /> {scoring ? 'Scoring...' : 'Re-score with AI'}
              </button>
            </div>

            {/* Contact Info */}
            <div className="space-y-3">
              <div className="flex items-center gap-3 text-sm"><EnvelopeSimple size={16} className="text-[#9B8AB0]" /><span className="text-[#5A4A7A] font-mono text-xs">{lead.email}</span></div>
              {lead.phone && <div className="flex items-center gap-3 text-sm"><Phone size={16} className="text-[#9B8AB0]" /><span className="text-[#5A4A7A]">{lead.phone}</span></div>}
              {lead.company_name && <div className="flex items-center gap-3 text-sm"><Buildings size={16} className="text-[#9B8AB0]" /><span className="text-[#5A4A7A]">{lead.company_name}</span></div>}
              {lead.job_title && <div className="flex items-center gap-3 text-sm"><Briefcase size={16} className="text-[#9B8AB0]" /><span className="text-[#5A4A7A]">{lead.job_title}</span></div>}
              {(lead.city || lead.country) && <div className="flex items-center gap-3 text-sm"><MapPin size={16} className="text-[#9B8AB0]" /><span className="text-[#5A4A7A]">{[lead.city, lead.country].filter(Boolean).join(', ')}</span></div>}
              {lead.tags && lead.tags.length > 0 && (
                <div className="flex items-start gap-3 text-sm"><Tag size={16} className="text-[#9B8AB0] mt-0.5" /><div className="flex flex-wrap gap-1">{lead.tags.map(tag => <span key={tag} className="px-2 py-0.5 text-xs bg-[#F4F0FF] text-[#7C35DC] rounded-md border border-[#7C35DC]/10">{tag}</span>)}</div></div>
              )}
            </div>

            {/* Status */}
            <div className="mt-4 pt-4 border-t border-[#E8E0F5]">
              <label className="block text-xs font-semibold uppercase tracking-[0.15em] text-[#9B8AB0] mb-2" style={{ fontFamily: 'Plus Jakarta Sans' }}>Status</label>
              <select value={editing ? editData.status : lead.status}
                onChange={(e) => editing ? setEditData({...editData, status: e.target.value}) : api.patch(`/api/leads/${id}`, { status: e.target.value }).then(fetchLead).then(fetchActivities)}
                className="w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-2 rounded-lg text-sm focus:border-[#7C35DC]" data-testid="lead-status-select">
                {STATUSES.map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
              </select>
            </div>

            {lead.notes && (
              <div className="mt-4 pt-4 border-t border-[#E8E0F5]">
                <label className="block text-xs font-semibold uppercase tracking-[0.15em] text-[#9B8AB0] mb-2" style={{ fontFamily: 'Plus Jakarta Sans' }}>Notes</label>
                <p className="text-sm text-[#5A4A7A]">{lead.notes}</p>
              </div>
            )}
          </div>

          {/* Quick Actions */}
          <div className="bg-white border border-[#E8E0F5] rounded-xl p-4" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="quick-actions">
            <h4 className="text-xs font-semibold uppercase tracking-[0.15em] text-[#9B8AB0] mb-3" style={{ fontFamily: 'Plus Jakarta Sans' }}>Quick Actions</h4>
            <div className="grid grid-cols-2 gap-2">
              {[
                { icon: Phone, label: 'Log Call', testId: 'log-call-btn' },
                { icon: EnvelopeSimple, label: 'Email', testId: 'send-email-btn' },
                { icon: WhatsappLogo, label: 'WhatsApp', testId: 'send-whatsapp-btn' },
                { icon: NoteBlank, label: 'Add Note', testId: 'add-note-btn' },
              ].map(action => (
                <button key={action.testId} onClick={() => setShowLogActivity(true)} className="flex items-center gap-2 px-3 py-2 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-lg hover:bg-[#F9F5FF] hover:text-[#7C35DC] hover:border-[#7C35DC]/20 transition-all text-xs font-medium" data-testid={action.testId}>
                  <action.icon size={14} /> {action.label}
                </button>
              ))}
            </div>
          </div>

          {/* ARIA's Read — conversation intelligence (additive) */}
          <AriaReadPanel leadId={lead.id} />

          {/* Touchpoint Progress (X of 32) — pairs with the Journey tab in the main column */}
          <TouchpointProgressCard leadId={lead.id} onOpenJourney={() => setActiveTab('journey')} />

          {/* ICP picker — Multi-ICP support */}
          <IcpPickerForLead leadId={lead.id} currentIcpId={lead.icp_id} onAssigned={fetchLead} />


          {/* Lead Magnet / Brochure */}
          <div className="bg-white border border-[#E8E0F5] rounded-xl p-4" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="lead-magnet-card">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-xs font-semibold uppercase tracking-[0.15em] text-[#9B8AB0] flex items-center gap-1.5" style={{ fontFamily: 'Plus Jakarta Sans' }}>
                <Paperclip size={12} /> Pre-Call Brochure
              </h4>
              {engagement?.is_hot && (
                <span className="flex items-center gap-1 text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-[#FEE2E2] text-[#DC2626] border border-[#DC2626]/20" data-testid="lead-magnet-hot-badge">
                  <Fire size={10} weight="fill" /> Hot
                </span>
              )}
            </div>
            <button
              onClick={handleSendMagnet}
              disabled={sendingMagnet}
              className="w-full flex items-center justify-center gap-2 btn-gradient px-3 py-2.5 rounded-lg text-sm font-semibold disabled:opacity-50"
              style={{ fontFamily: 'Plus Jakarta Sans' }}
              data-testid="send-brochure-btn"
            >
              <Paperclip size={14} weight="fill" /> {sendingMagnet ? 'Sending...' : engagement?.sent_count > 0 ? 'Send again' : 'Send brochure'}
            </button>

            {engagement && engagement.sent_count > 0 && (
              <div className="mt-3 pt-3 border-t border-[#E8E0F5] space-y-1.5" data-testid="lead-magnet-engagement">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-[#9B8AB0]">Sent</span>
                  <span className="text-[#1A0A2E] font-medium">{engagement.sent_count}× · {formatRelative(engagement.last_sent)}</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-[#9B8AB0] flex items-center gap-1"><Eye size={12} /> Opens</span>
                  <span className={`font-bold ${engagement.view_count > 0 ? 'text-[#7C35DC]' : 'text-[#9B8AB0]'}`}>
                    {engagement.view_count}{engagement.last_viewed ? ` · ${formatRelative(engagement.last_viewed)}` : ''}
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Best Time to Call */}
          {bestTime && (
            <div className="bg-white border border-[#E8E0F5] rounded-xl p-4" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="best-time-to-call-card">
              <h4 className="text-xs font-semibold uppercase tracking-[0.15em] text-[#9B8AB0] mb-3 flex items-center gap-1.5" style={{ fontFamily: 'Plus Jakarta Sans' }}>
                <Clock size={12} /> ARIA's Best Time to Call
              </h4>
              <div className="space-y-2.5">
                {/* Big call score */}
                <div className="flex items-center justify-between p-3 rounded-lg" style={{ background: bestTime.urgency === 'now' ? '#DCFCE7' : bestTime.urgency === 'soon' ? '#FEF3C7' : '#F4F0FF' }}>
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-wider" style={{ color: bestTime.urgency === 'now' ? '#16A34A' : bestTime.urgency === 'soon' ? '#D97706' : '#7C35DC' }}>
                      {bestTime.urgency === 'now' ? 'Call now' : bestTime.urgency === 'soon' ? 'Soon' : 'Later'}
                    </div>
                    <div className="text-sm font-semibold text-[#1A0A2E] mt-0.5">{bestTime.suggested_action}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-xl font-extrabold font-mono" style={{ color: bestTime.urgency === 'now' ? '#16A34A' : bestTime.urgency === 'soon' ? '#D97706' : '#7C35DC' }}>{bestTime.call_score}</div>
                    <div className="text-[10px] text-[#9B8AB0] uppercase tracking-wider">/100</div>
                  </div>
                </div>
                {/* Timezone & window */}
                <div className="grid grid-cols-2 gap-2">
                  <div className="p-2 rounded-lg bg-[#F9F5FF] border border-[#E8E0F5]">
                    <div className="text-[10px] font-semibold uppercase tracking-wider text-[#9B8AB0]">Their time</div>
                    <div className="text-sm font-bold text-[#1A0A2E] font-mono mt-0.5">{bestTime.tz_label} {String(bestTime.lead_local_hour).padStart(2, '0')}:00</div>
                  </div>
                  <div className="p-2 rounded-lg bg-[#F9F5FF] border border-[#E8E0F5]">
                    <div className="text-[10px] font-semibold uppercase tracking-wider text-[#9B8AB0]">Active window</div>
                    <div className={`text-sm font-bold font-mono mt-0.5 ${bestTime.in_window ? 'text-[#16A34A]' : 'text-[#5A4A7A]'}`}>{bestTime.active_window_local}</div>
                  </div>
                </div>
                {/* Reasons */}
                {bestTime.reasons?.length > 0 && (
                  <ul className="space-y-1 pt-1" data-testid="best-time-reasons">
                    {bestTime.reasons.map((r, i) => (
                      <li key={i} className="text-xs text-[#5A4A7A] flex items-start gap-1.5">
                        <CheckCircle size={11} className="text-[#7C35DC] mt-0.5 flex-shrink-0" weight="fill" /> {r}
                      </li>
                    ))}
                  </ul>
                )}
                {lead?.phone && bestTime.urgency === 'now' && (
                  <a href={`tel:${lead.phone}`} className="w-full flex items-center justify-center gap-2 btn-gradient px-3 py-2.5 rounded-lg text-sm font-semibold mt-2" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid="best-time-call-now-btn">
                    <Phone size={14} weight="fill" /> Call {lead.first_name}
                  </a>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Right Column - Activity & Details */}
        <div className="lg:col-span-2 space-y-4">
          {/* Tabs */}
          <div className="flex gap-1 bg-white border border-[#E8E0F5] rounded-xl p-1" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="detail-tabs">
            {['timeline', 'aria', 'journey', 'details'].map(tab => (
              <button key={tab} onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all ${activeTab === tab ? (tab === 'aria' ? 'text-white' : 'text-white') : 'text-[#5A4A7A] hover:text-[#7C35DC] hover:bg-[#F9F5FF]'}`}
                style={activeTab === tab ? { background: tab === 'aria' ? 'var(--gradient-brand)' : '#7C35DC', fontFamily: 'Plus Jakarta Sans' } : { fontFamily: 'Plus Jakarta Sans' }}
                data-testid={`tab-${tab}`}>
                {tab === 'aria' ? 'ARIA Agent' : tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </div>

          {activeTab === 'aria' && (
            <AriaConversationPanel leadId={id} leadName={`${lead.first_name} ${lead.last_name}`} />
          )}

          {activeTab === 'journey' && (
            <LeadJourneyTab leadId={id} />
          )}

          {activeTab === 'timeline' && (
            <div className="bg-white border border-[#E8E0F5] rounded-xl p-6" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="activity-timeline">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Activity Timeline</h3>
                <button onClick={() => setShowLogActivity(true)} className="flex items-center gap-2 px-3 py-1.5 btn-gradient rounded-lg text-sm font-medium" data-testid="log-activity-btn">
                  <Plus size={14} /> Log Activity
                </button>
              </div>

              {activities.length === 0 ? (
                <div className="text-center py-12 text-[#9B8AB0]">No activities yet</div>
              ) : (
                <div className="space-y-4">
                  {activities.map((activity, index) => {
                    const meta = INTEGRATION_EVENT_META[activity.activity_type];
                    const platform = platformOf(activity);
                    return (
                      <div key={activity.id || index} className="flex gap-4" data-testid={`activity-${activity.id || index}`}>
                        <div className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center"
                          style={meta ? { background: `${meta.color}14`, color: meta.color, border: `1px solid ${meta.color}33` } : { background: '#F4F0FF', color: '#7C35DC' }}>
                          {activityIcon(activity.activity_type)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-sm font-semibold text-[#1A0A2E]">{meta?.label || activity.subject || activity.activity_type.replace(/_/g, ' ')}</span>
                            {platform && (
                              <span className="px-1.5 py-0.5 rounded-md text-[9px] font-bold uppercase tracking-[0.18em] text-white" style={{ background: platform === 'SalesHandy' ? '#16A34A' : '#7C35DC' }}>
                                {platform}
                              </span>
                            )}
                            {activity.user_id && <span className="text-xs text-[#9B8AB0]">{activity.user_id}</span>}
                          </div>
                          {(activity.body || activity.description) && <p className="text-sm text-[#5A4A7A] mt-1">{activity.body || activity.description}</p>}
                          {activity.outcome && <p className="text-xs text-[#7C35DC] mt-1">Outcome: {activity.outcome}</p>}
                          <span className="text-xs text-[#9B8AB0] mt-1 block">
                            <Clock size={12} className="inline mr-1" />
                            {new Date(activity.created_at).toLocaleString()}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {activeTab === 'details' && (
            <div className="bg-white border border-[#E8E0F5] rounded-xl p-6" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="lead-details-tab">
              <h3 className="text-lg font-bold text-[#1A0A2E] mb-4" style={{ fontFamily: 'Plus Jakarta Sans' }}>Lead Details</h3>
              <div className="grid grid-cols-2 gap-4">
                {[
                  ['Lead Type', lead.lead_type], ['Source Channel', lead.source_channel?.replace('_', ' ')],
                  ['Industry', lead.industry], ['Revenue Range', lead.revenue_range],
                  ['City', lead.city], ['Country', lead.country],
                  ['Assigned To', lead.assigned_to], ['Created', new Date(lead.created_at).toLocaleDateString()],
                  ['Last Contacted', lead.last_contacted_at ? new Date(lead.last_contacted_at).toLocaleDateString() : 'Never'],
                  ['Next Follow-up', lead.next_followup_at ? new Date(lead.next_followup_at).toLocaleDateString() : 'Not set'],
                ].map(([label, value]) => (
                  <div key={label}>
                    <dt className="text-xs font-semibold uppercase tracking-[0.15em] text-[#9B8AB0]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{label}</dt>
                    <dd className="text-sm text-[#5A4A7A] mt-1">{value || '—'}</dd>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Log Activity Modal */}
      {showLogActivity && <LogActivityModal onClose={() => setShowLogActivity(false)} onSubmit={handleLogActivity} />}
    </div>
  );
};

const Plus = ({ size, ...props }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
);

const LogActivityModal = ({ onClose, onSubmit }) => {
  const [data, setData] = useState({ activity_type: 'call', subject: '', body: '', outcome: '', duration_minutes: null });

  return (
    <div className="fixed inset-0 bg-black/20 backdrop-blur-sm flex items-center justify-center z-50 p-4" data-testid="log-activity-modal">
      <div className="bg-white border border-[#E8E0F5] rounded-2xl w-full max-w-lg" style={{ boxShadow: 'var(--shadow-hover)' }}>
        <div className="p-6 border-b border-[#E8E0F5] flex items-center justify-between">
          <h2 className="text-lg font-bold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Log Activity</h2>
          <button onClick={onClose} className="text-[#9B8AB0] hover:text-[#7C35DC] transition-colors">X</button>
        </div>
        <div className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-[#1A0A2E] mb-1.5" style={{ fontFamily: 'Plus Jakarta Sans' }}>Type</label>
            <select value={data.activity_type} onChange={(e) => setData({...data, activity_type: e.target.value})} className="w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-2 rounded-lg text-sm" data-testid="activity-type-select">
              {['call', 'email_sent', 'whatsapp_sent', 'linkedin_message', 'meeting_scheduled', 'meeting_done', 'note_added'].map(t => <option key={t} value={t}>{t.replace('_', ' ')}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-[#1A0A2E] mb-1.5" style={{ fontFamily: 'Plus Jakarta Sans' }}>Subject</label>
            <input type="text" value={data.subject} onChange={(e) => setData({...data, subject: e.target.value})} className="w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-2 rounded-lg text-sm" data-testid="activity-subject-input" />
          </div>
          <div>
            <label className="block text-sm font-medium text-[#1A0A2E] mb-1.5" style={{ fontFamily: 'Plus Jakarta Sans' }}>Notes</label>
            <textarea value={data.body} onChange={(e) => setData({...data, body: e.target.value})} rows={3} className="w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-2 rounded-lg text-sm resize-none" data-testid="activity-body-input" />
          </div>
          <div className="flex justify-end gap-3">
            <button onClick={onClose} className="px-4 py-2 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-lg hover:bg-[#F9F5FF] text-sm font-medium">Cancel</button>
            <button onClick={() => onSubmit(data)} className="px-4 py-2 btn-gradient rounded-lg text-sm font-semibold" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid="submit-activity-btn">Log Activity</button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LeadDetail;
