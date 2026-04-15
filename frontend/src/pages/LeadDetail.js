import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../config/api';
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
} from '@phosphor-icons/react';

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

  useEffect(() => {
    fetchLead();
    fetchActivities();
  }, [id]);

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

  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-[#A3A3A3] font-mono text-sm">Loading lead...</div></div>;
  if (!lead) return <div className="text-[#A3A3A3]">Lead not found</div>;

  const tierColor = { hot: '#FF3B30', warm: '#F59E0B', cold: '#0055FF' };
  const STATUSES = ['new', 'contacted', 'qualified', 'unqualified', 'proposal_sent', 'negotiation', 'won', 'lost', 'nurture'];

  const activityIcon = (type) => {
    const icons = { call: Phone, email_sent: EnvelopeSimple, email_received: EnvelopeSimple, whatsapp_sent: WhatsappLogo, whatsapp_received: WhatsappLogo, meeting_scheduled: CalendarBlank, meeting_done: CalendarBlank, note_added: NoteBlank, status_changed: Lightning, score_updated: Sparkle };
    const Icon = icons[type] || NoteBlank;
    return <Icon size={16} weight="duotone" />;
  };

  return (
    <div data-testid="lead-detail-page" className="space-y-6">
      {/* Back button */}
      <button onClick={() => navigate('/leads')} className="flex items-center gap-2 text-[#A3A3A3] hover:text-white transition-colors text-sm" data-testid="back-to-leads-btn">
        <ArrowLeft size={16} /> Back to Leads
      </button>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Lead Profile */}
        <div className="lg:col-span-1 space-y-4">
          {/* Profile Card */}
          <div className="bg-[#141414] border border-[#262626] rounded-lg p-6" data-testid="lead-profile-card">
            <div className="flex items-start justify-between mb-4">
              <div>
                {editing ? (
                  <div className="space-y-2">
                    <input value={editData.first_name} onChange={(e) => setEditData({...editData, first_name: e.target.value})} className="bg-[#0A0A0A] border border-[#262626] text-white px-2 py-1 rounded text-lg font-bold w-full" />
                    <input value={editData.last_name} onChange={(e) => setEditData({...editData, last_name: e.target.value})} className="bg-[#0A0A0A] border border-[#262626] text-white px-2 py-1 rounded text-lg font-bold w-full" />
                  </div>
                ) : (
                  <h2 className="text-2xl font-bold text-white">{lead.first_name} {lead.last_name}</h2>
                )}
                <span className={`inline-block mt-2 px-2 py-0.5 text-xs font-medium uppercase tracking-wider rounded-sm border ${lead.lead_type === 'B2B' ? 'bg-[#0055FF]/10 text-[#0055FF] border-[#0055FF]/30' : 'bg-[#10B981]/10 text-[#10B981] border-[#10B981]/30'}`}>
                  {lead.lead_type}
                </span>
              </div>
              <button
                onClick={() => editing ? handleUpdateLead() : setEditing(true)}
                className="text-sm text-[#0055FF] hover:text-[#0044CC] transition-colors"
                data-testid="edit-lead-btn"
              >
                {editing ? 'Save' : 'Edit'}
              </button>
            </div>

            {/* ICP Score */}
            <div className="mb-6 p-4 rounded-lg" style={{ boxShadow: `inset 0 0 12px ${tierColor[lead.icp_tier]}25`, border: `1px solid ${tierColor[lead.icp_tier]}30` }}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold uppercase tracking-[0.2em] text-[#737373]">ICP Score</span>
                <span className="text-xs font-medium uppercase px-2 py-0.5 rounded-sm" style={{ color: tierColor[lead.icp_tier], background: `${tierColor[lead.icp_tier]}15` }}>
                  {lead.icp_tier}
                </span>
              </div>
              <div className="flex items-end gap-2">
                <span className="text-4xl font-bold font-mono" style={{ color: tierColor[lead.icp_tier] }}>{lead.icp_score}</span>
                <span className="text-sm text-[#737373] mb-1">/ 100</span>
              </div>
              <div className="w-full h-2 bg-[#262626] rounded-full mt-3 overflow-hidden">
                <div className="h-full rounded-full transition-all duration-500" style={{ width: `${lead.icp_score}%`, backgroundColor: tierColor[lead.icp_tier] }}></div>
              </div>
              {lead.icp_reasoning && lead.icp_reasoning.length > 0 && (
                <ul className="mt-3 space-y-1">
                  {lead.icp_reasoning.map((r, i) => (
                    <li key={i} className="text-xs text-[#A3A3A3] flex items-start gap-1.5">
                      <span className="text-[#737373] mt-0.5">-</span> {r}
                    </li>
                  ))}
                </ul>
              )}
              <button
                onClick={handleScore}
                disabled={scoring}
                className="mt-3 w-full flex items-center justify-center gap-2 px-3 py-2 bg-[#8B5CF6]/10 text-[#8B5CF6] border border-[#8B5CF6]/30 rounded-md hover:bg-[#8B5CF6]/20 transition-colors text-sm disabled:opacity-50"
                data-testid="ai-score-btn"
              >
                <Sparkle size={16} weight="fill" />
                {scoring ? 'Scoring...' : 'Re-score with AI'}
              </button>
            </div>

            {/* Contact Info */}
            <div className="space-y-3">
              <div className="flex items-center gap-3 text-sm">
                <EnvelopeSimple size={16} className="text-[#737373]" />
                <span className="text-[#A3A3A3] font-mono text-xs">{lead.email}</span>
              </div>
              {lead.phone && (
                <div className="flex items-center gap-3 text-sm">
                  <Phone size={16} className="text-[#737373]" />
                  <span className="text-[#A3A3A3]">{lead.phone}</span>
                </div>
              )}
              {lead.company_name && (
                <div className="flex items-center gap-3 text-sm">
                  <Buildings size={16} className="text-[#737373]" />
                  <span className="text-[#A3A3A3]">{lead.company_name}</span>
                </div>
              )}
              {lead.job_title && (
                <div className="flex items-center gap-3 text-sm">
                  <Briefcase size={16} className="text-[#737373]" />
                  <span className="text-[#A3A3A3]">{lead.job_title}</span>
                </div>
              )}
              {(lead.city || lead.country) && (
                <div className="flex items-center gap-3 text-sm">
                  <MapPin size={16} className="text-[#737373]" />
                  <span className="text-[#A3A3A3]">{[lead.city, lead.country].filter(Boolean).join(', ')}</span>
                </div>
              )}
              {lead.tags && lead.tags.length > 0 && (
                <div className="flex items-start gap-3 text-sm">
                  <Tag size={16} className="text-[#737373] mt-0.5" />
                  <div className="flex flex-wrap gap-1">
                    {lead.tags.map(tag => (
                      <span key={tag} className="px-2 py-0.5 text-xs bg-[#262626] text-[#A3A3A3] rounded">{tag}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Status */}
            <div className="mt-4 pt-4 border-t border-[#262626]">
              <label className="block text-xs font-semibold uppercase tracking-[0.2em] text-[#737373] mb-2">Status</label>
              <select
                value={editing ? editData.status : lead.status}
                onChange={(e) => editing ? setEditData({...editData, status: e.target.value}) : api.patch(`/api/leads/${id}`, { status: e.target.value }).then(fetchLead).then(fetchActivities)}
                className="w-full bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2 rounded-md text-sm"
                data-testid="lead-status-select"
              >
                {STATUSES.map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
              </select>
            </div>

            {/* Notes */}
            {lead.notes && (
              <div className="mt-4 pt-4 border-t border-[#262626]">
                <label className="block text-xs font-semibold uppercase tracking-[0.2em] text-[#737373] mb-2">Notes</label>
                <p className="text-sm text-[#A3A3A3]">{lead.notes}</p>
              </div>
            )}
          </div>

          {/* Quick Actions */}
          <div className="bg-[#141414] border border-[#262626] rounded-lg p-4" data-testid="quick-actions">
            <h4 className="text-xs font-semibold uppercase tracking-[0.2em] text-[#737373] mb-3">Quick Actions</h4>
            <div className="grid grid-cols-2 gap-2">
              <button onClick={() => setShowLogActivity(true)} className="flex items-center gap-2 px-3 py-2 bg-transparent border border-[#262626] text-[#F5F5F5] rounded-md hover:bg-[#1E1E1E] transition-colors text-xs" data-testid="log-call-btn">
                <Phone size={14} /> Log Call
              </button>
              <button onClick={() => setShowLogActivity(true)} className="flex items-center gap-2 px-3 py-2 bg-transparent border border-[#262626] text-[#F5F5F5] rounded-md hover:bg-[#1E1E1E] transition-colors text-xs" data-testid="send-email-btn">
                <EnvelopeSimple size={14} /> Email
              </button>
              <button onClick={() => setShowLogActivity(true)} className="flex items-center gap-2 px-3 py-2 bg-transparent border border-[#262626] text-[#F5F5F5] rounded-md hover:bg-[#1E1E1E] transition-colors text-xs" data-testid="send-whatsapp-btn">
                <WhatsappLogo size={14} /> WhatsApp
              </button>
              <button onClick={() => setShowLogActivity(true)} className="flex items-center gap-2 px-3 py-2 bg-transparent border border-[#262626] text-[#F5F5F5] rounded-md hover:bg-[#1E1E1E] transition-colors text-xs" data-testid="add-note-btn">
                <NoteBlank size={14} /> Add Note
              </button>
            </div>
          </div>
        </div>

        {/* Right Column - Activity & Details */}
        <div className="lg:col-span-2 space-y-4">
          {/* Tabs */}
          <div className="flex gap-1 bg-[#141414] border border-[#262626] rounded-lg p-1" data-testid="detail-tabs">
            {['timeline', 'details'].map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${activeTab === tab ? 'bg-[#0055FF] text-white' : 'text-[#A3A3A3] hover:text-white'}`}
                data-testid={`tab-${tab}`}
              >
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </div>

          {activeTab === 'timeline' && (
            <div className="bg-[#141414] border border-[#262626] rounded-lg p-6" data-testid="activity-timeline">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-white">Activity Timeline</h3>
                <button
                  onClick={() => setShowLogActivity(true)}
                  className="flex items-center gap-2 px-3 py-1.5 bg-[#0055FF] text-white rounded-md hover:bg-[#0044CC] transition-colors text-sm"
                  data-testid="log-activity-btn"
                >
                  <Plus size={14} /> Log Activity
                </button>
              </div>

              {activities.length === 0 ? (
                <div className="text-center py-12 text-[#737373]">No activities yet</div>
              ) : (
                <div className="space-y-4">
                  {activities.map((activity, index) => (
                    <div key={activity.id || index} className="flex gap-4" data-testid={`activity-${activity.id || index}`}>
                      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-[#262626] flex items-center justify-center text-[#A3A3A3]">
                        {activityIcon(activity.activity_type)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-white">{activity.subject || activity.activity_type.replace('_', ' ')}</span>
                          <span className="text-xs text-[#737373]">{activity.user_id}</span>
                        </div>
                        {activity.body && <p className="text-sm text-[#A3A3A3] mt-1">{activity.body}</p>}
                        {activity.outcome && <p className="text-xs text-[#8B5CF6] mt-1">Outcome: {activity.outcome}</p>}
                        <span className="text-xs text-[#737373] mt-1 block">
                          <Clock size={12} className="inline mr-1" />
                          {new Date(activity.created_at).toLocaleString()}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'details' && (
            <div className="bg-[#141414] border border-[#262626] rounded-lg p-6" data-testid="lead-details-tab">
              <h3 className="text-lg font-semibold text-white mb-4">Lead Details</h3>
              <div className="grid grid-cols-2 gap-4">
                {[
                  ['Lead Type', lead.lead_type],
                  ['Source Channel', lead.source_channel?.replace('_', ' ')],
                  ['Industry', lead.industry],
                  ['Revenue Range', lead.revenue_range],
                  ['City', lead.city],
                  ['Country', lead.country],
                  ['Assigned To', lead.assigned_to],
                  ['Created', new Date(lead.created_at).toLocaleDateString()],
                  ['Last Contacted', lead.last_contacted_at ? new Date(lead.last_contacted_at).toLocaleDateString() : 'Never'],
                  ['Next Follow-up', lead.next_followup_at ? new Date(lead.next_followup_at).toLocaleDateString() : 'Not set'],
                ].map(([label, value]) => (
                  <div key={label}>
                    <dt className="text-xs font-semibold uppercase tracking-[0.2em] text-[#737373]">{label}</dt>
                    <dd className="text-sm text-[#A3A3A3] mt-1">{value || '—'}</dd>
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
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4" data-testid="log-activity-modal">
      <div className="bg-[#141414] border border-[#262626] rounded-lg w-full max-w-lg">
        <div className="p-6 border-b border-[#262626] flex items-center justify-between">
          <h2 className="text-lg font-bold text-white">Log Activity</h2>
          <button onClick={onClose} className="text-[#737373] hover:text-white transition-colors">X</button>
        </div>
        <div className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-[#F5F5F5] mb-1.5">Type</label>
            <select value={data.activity_type} onChange={(e) => setData({...data, activity_type: e.target.value})} className="w-full bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2 rounded-md text-sm" data-testid="activity-type-select">
              {['call', 'email_sent', 'whatsapp_sent', 'linkedin_message', 'meeting_scheduled', 'meeting_done', 'note_added'].map(t => <option key={t} value={t}>{t.replace('_', ' ')}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-[#F5F5F5] mb-1.5">Subject</label>
            <input type="text" value={data.subject} onChange={(e) => setData({...data, subject: e.target.value})} className="w-full bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2 rounded-md text-sm" data-testid="activity-subject-input" />
          </div>
          <div>
            <label className="block text-sm font-medium text-[#F5F5F5] mb-1.5">Notes</label>
            <textarea value={data.body} onChange={(e) => setData({...data, body: e.target.value})} rows={3} className="w-full bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2 rounded-md text-sm resize-none" data-testid="activity-body-input" />
          </div>
          <div className="flex justify-end gap-3">
            <button onClick={onClose} className="px-4 py-2 bg-transparent border border-[#262626] text-[#F5F5F5] rounded-md hover:bg-[#1E1E1E] text-sm">Cancel</button>
            <button onClick={() => onSubmit(data)} className="px-4 py-2 bg-[#0055FF] text-white rounded-md hover:bg-[#0044CC] text-sm font-medium" data-testid="submit-activity-btn">Log Activity</button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LeadDetail;
