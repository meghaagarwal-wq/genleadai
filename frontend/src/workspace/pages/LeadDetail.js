import { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, LinkSimple, Trash, Lightning, Note, Plus, Brain, Copy, Sparkle } from '@phosphor-icons/react';
import { toast } from 'sonner';
import { ptApi, PageHeader, StageBadge, SOURCE_LABELS, fmtDateTime } from '../shared';
import AskAriaModal from '../components/AskAriaModal';
import IntelTab from './IntelTab';

const PtLeadDetail = () => {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [newNote, setNewNote] = useState('');
  const [simEvent, setSimEvent] = useState('saleshandy.email_clicked');
  const [rules, setRules] = useState([]);
  const [askOpen, setAskOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');
  const navigate = useNavigate();

  const load = async () => {
    setLoading(true);
    try {
      const [r, sr] = await Promise.all([
        ptApi.get(`/api/pt/leads/${id}`),
        ptApi.get('/api/pt/scoring-rules'),
      ]);
      setData(r.data);
      setRules(sr.data.rules || []);
    } catch { toast.error('Could not load lead'); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [id]);

  const addNote = async () => {
    if (newNote.trim().length < 1) return;
    try {
      await ptApi.post('/api/pt/notes', { lead_id: id, note: newNote.trim() });
      toast.success('Note added');
      setNewNote('');
      load();
    } catch { toast.error('Could not add note'); }
  };

  const simulate = async () => {
    try {
      await ptApi.post('/api/pt/events', { lead_id: id, event_type: simEvent });
      toast.success('Event applied · score updated');
      load();
    } catch (err) { toast.error(err.response?.data?.detail || 'Failed'); }
  };

  const remove = async () => {
    if (!window.confirm('Delete this lead permanently?')) return;
    try {
      await ptApi.delete(`/api/pt/leads/${id}`);
      toast.success('Deleted');
      navigate('/app/leads');
    } catch { toast.error('Could not delete'); }
  };

  if (loading) return <div className="text-sm text-[#64748B]">Loading…</div>;
  if (!data?.lead) return <div className="text-sm text-[#DC2626]">Lead not found</div>;

  const { lead, company, events, notes, score_breakdown, recommendation } = data;
  return (
    <div data-testid="pt-lead-detail-page">
      <button onClick={() => navigate('/app/leads')} className="flex items-center gap-1.5 text-sm text-[#64748B] hover:text-[#0F172A] mb-4" data-testid="pt-detail-back">
        <ArrowLeft size={14} /> Back to Lead Feed
      </button>

      <PageHeader
        title={`${lead.first_name} ${lead.last_name}`.trim()}
        subtitle={`${lead.title || '—'} · ${lead.company_name || 'No company'}`}
        right={
          <div className="flex items-center gap-2">
            <button onClick={() => setAskOpen(true)} data-testid="pt-detail-ask-aria"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-semibold text-white"
              style={{ background: 'linear-gradient(135deg, #4C1D95 0%, #7C35DC 100%)' }}>
              <Sparkle size={13} weight="fill" /> Ask Aria to Reply
            </button>
            <button onClick={remove} data-testid="pt-detail-delete"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-semibold text-[#DC2626] border border-[#DC2626]/30 hover:bg-[#FEF2F2]">
              <Trash size={14} /> Delete
            </button>
          </div>
        }
      />

      {/* iter113 Batch 4 — Overview / Intel tab strip */}
      <div className="flex items-center gap-1 mb-4 border-b border-[#E2E8F0]" data-testid="pt-detail-tabs">
        {[
          { id: 'overview', label: 'Overview' },
          { id: 'intel', label: 'Intel' },
        ].map((t) => {
          const active = activeTab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              data-testid={`pt-detail-tab-${t.id}`}
              className={`relative px-4 py-2 text-sm font-semibold transition-colors ${active ? 'text-[#7C35DC]' : 'text-[#64748B] hover:text-[#0F172A]'}`}
            >
              {t.id === 'intel' && <Brain size={12} weight="duotone" className="inline mr-1 -mt-0.5" />}
              {t.label}
              {active && (
                <span
                  className="absolute left-0 right-0 -bottom-px h-[2px]"
                  style={{ background: 'linear-gradient(90deg, #4C1D95 0%, #7C35DC 100%)' }}
                />
              )}
            </button>
          );
        })}
      </div>

      {activeTab === 'intel' ? (
        <IntelTab leadId={id} lead={lead} />
      ) : (
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left col — Identity + Status */}
        <div className="space-y-4">
          {/* Identity */}
          <Card title="Identity">
            <KV label="Email" value={
              <div className="flex items-center gap-1">
                <span>{lead.email}</span>
                <button onClick={() => { navigator.clipboard.writeText(lead.email); toast.success('Email copied'); }} data-testid="pt-detail-copy-email" className="text-[#94A3B8] hover:text-[#7C35DC]"><Copy size={11} weight="bold" /></button>
              </div>
            } />
            <KV label="LinkedIn" value={lead.linkedin_url ? (
              <div className="flex items-center gap-1">
                <a href={lead.linkedin_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-[#7C35DC] hover:underline">profile <LinkSimple size={11} /></a>
                <button onClick={() => { navigator.clipboard.writeText(lead.linkedin_url); toast.success('LinkedIn URL copied'); }} data-testid="pt-detail-copy-linkedin" className="text-[#94A3B8] hover:text-[#7C35DC]"><Copy size={11} weight="bold" /></button>
              </div>
            ) : '—'} />
            <KV label="Industry" value={lead.industry || '—'} />
            <KV label="Employees" value={lead.employee_count || '—'} />
            <KV label="Geography" value={lead.geography || '—'} />
            <KV label="ICP fit" value={lead.icp_fit || '—'} />
          </Card>

          {/* Status */}
          <Card title="Status">
            <div className="flex items-center gap-2 mb-2">
              <StageBadge stage={lead.stage} />
              <span className="text-2xl font-extrabold text-[#0F172A]" style={{ fontFamily: 'Space Grotesk, Inter' }}>{lead.score ?? 0}</span>
            </div>
            <KV label="Automation" value={lead.automation_status || '—'} />
            <KV label="Owner" value={lead.owner || '—'} />
            <KV label="Source" value={SOURCE_LABELS[lead.source] || lead.source || '—'} />
            <KV label="Latest signal" value={lead.latest_signal || '—'} />
            <KV label="Last activity" value={fmtDateTime(lead.last_activity_at)} />
            {recommendation && (
              <div className="mt-3 p-2.5 rounded-md border border-[#7C35DC]/30" style={{ background: '#FAF7FF' }} data-testid="pt-detail-recommendation">
                <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#7C35DC] mb-0.5">Aria recommendation</div>
                <div className="text-sm text-[#0F172A]">{recommendation}</div>
              </div>
            )}
          </Card>

          {/* Score breakdown */}
          {score_breakdown.length > 0 && (
            <Card title="Score breakdown">
              <div className="space-y-1.5">
                {score_breakdown.map((b, i) => (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <span className="text-[#475569]">{b.label || b.event_type} {b.count > 1 && <span className="text-[10px] text-[#94A3B8]">×{b.count}</span>}</span>
                    <span className={`font-bold ${b.total >= 0 ? 'text-[#7C35DC]' : 'text-[#DC2626]'}`}>{b.total >= 0 ? '+' : ''}{b.total}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Train Aria */}
          <TrainAriaCard leadId={id} currentICP={lead.icp_fit} onChanged={load} />
        </div>

        {/* Middle col — Timeline */}
        <div className="lg:col-span-2 space-y-4">
          <Card title="Engagement timeline" right={
            <div className="flex items-center gap-2">
              <select value={simEvent} onChange={(e) => setSimEvent(e.target.value)} data-testid="pt-detail-sim-event"
                className="text-xs border border-[#E2E8F0] rounded-md px-2 py-1 max-w-[180px]">
                {rules.map(r => <option key={r.event_type} value={r.event_type}>{r.label} ({r.score >= 0 ? '+' : ''}{r.score})</option>)}
              </select>
              <button onClick={simulate} data-testid="pt-detail-sim-btn"
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold text-white" style={{ background: '#7C35DC' }}>
                <Lightning size={12} weight="bold" /> Apply
              </button>
            </div>
          }>
            {events.length === 0 ? (
              <div className="text-sm text-[#64748B] text-center py-6">No engagement events yet.</div>
            ) : (
              <div className="space-y-2.5">
                {events.map(e => (
                  <div key={e.id} className="flex items-start gap-3 pb-2.5 border-b border-[#F1F5F9] last:border-0" data-testid={`pt-event-${e.id}`}>
                    <div className="w-1.5 h-1.5 rounded-full mt-2 flex-shrink-0" style={{ background: e.score_change >= 0 ? '#7C35DC' : '#DC2626' }} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-semibold text-[#0F172A]">{e.label || e.event_type}</span>
                        <span className="text-[10px] font-bold uppercase tracking-[0.14em] px-1.5 py-0.5 rounded-md text-[#7C35DC] border border-[#7C35DC]/30">{SOURCE_LABELS[e.source] || e.source}</span>
                        <span className={`text-xs font-bold ${e.score_change >= 0 ? 'text-[#7C35DC]' : 'text-[#DC2626]'}`}>{e.score_change >= 0 ? '+' : ''}{e.score_change}</span>
                      </div>
                      <div className="text-xs text-[#64748B] mt-0.5">{fmtDateTime(e.created_at)} · score after: {e.score_after} · stage: {e.stage_after}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Notes */}
          <Card title="Notes" icon={Note}>
            <div className="flex gap-2 mb-3">
              <input value={newNote} onChange={(e) => setNewNote(e.target.value)} placeholder="Add a note (e.g., Routed to John, ICP checked)…"
                data-testid="pt-detail-note-input"
                className="flex-1 text-sm border border-[#E2E8F0] rounded-md px-2.5 py-1.5 outline-none" />
              <button onClick={addNote} data-testid="pt-detail-note-add"
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-sm font-semibold text-white" style={{ background: '#7C35DC' }}>
                <Plus size={12} weight="bold" /> Add
              </button>
            </div>
            {notes.length === 0 ? (
              <div className="text-sm text-[#64748B] text-center py-3">No notes yet.</div>
            ) : (
              <div className="space-y-2">
                {notes.map(n => (
                  <div key={n.id} className="bg-[#F8FAFC] rounded-md p-2.5 border border-[#E2E8F0]" data-testid={`pt-note-${n.id}`}>
                    <div className="text-sm text-[#0F172A]">{n.note}</div>
                    <div className="text-[10px] text-[#64748B] mt-1">{n.created_by_name || n.created_by} · {fmtDateTime(n.created_at)}</div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {company && (
            <Card title="Account">
              <KV label="Company" value={<Link to="/app/accounts" className="text-[#7C35DC] hover:underline">{company.name}</Link>} />
              <KV label="Stage" value={<StageBadge stage={company.account_stage} />} />
              <KV label="Sequence" value={company.sequence_status} />
              <KV label="Pause required" value={company.pause_required ? 'Yes' : 'No'} />
              <KV label="Highest score" value={company.highest_score} />
            </Card>
          )}
        </div>
      </div>
      )}

      {askOpen && (
        <AskAriaModal
          leadId={id}
          leadName={`${lead.first_name} ${lead.last_name}`.trim() || lead.email}
          paused={!!company?.pause_required}
          onClose={() => setAskOpen(false)}
        />
      )}
    </div>
  );
};

const Card = ({ title, icon: Icon, right, children }) => (
  <div className="bg-white border border-[#E2E8F0] rounded-lg overflow-hidden">
    <div className="px-4 py-2.5 border-b border-[#E2E8F0] flex items-center justify-between bg-[#F8FAFC]">
      <div className="flex items-center gap-1.5">
        {Icon && <Icon size={14} weight="duotone" className="text-[#475569]" />}
        <h3 className="text-xs font-bold uppercase tracking-[0.16em] text-[#475569]">{title}</h3>
      </div>
      {right}
    </div>
    <div className="p-4">{children}</div>
  </div>
);

const KV = ({ label, value }) => (
  <div className="flex items-center justify-between py-1 border-b border-[#F1F5F9] last:border-0">
    <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#64748B]">{label}</span>
    <span className="text-sm text-[#0F172A] font-medium">{value || '—'}</span>
  </div>
);

const TrainAriaCard = ({ leadId, currentICP, onChanged }) => {
  const [busy, setBusy] = useState(false);
  const [recentSignals, setRecentSignals] = useState([]);

  useEffect(() => {
    ptApi.get(`/api/pt/training/signals?lead_id=${leadId}`)
      .then(r => setRecentSignals(r.data.signals || [])).catch(() => {});
  }, [leadId]);

  const send = async (signal_type, value) => {
    setBusy(true);
    try {
      await ptApi.post('/api/pt/training/signal', { lead_id: leadId, signal_type, value });
      toast.success('Aria learned this');
      onChanged();
    } catch (err) { toast.error(err.response?.data?.detail || 'Could not save'); }
    finally { setBusy(false); }
  };

  return (
    <div className="bg-white border border-[#7C35DC]/20 rounded-lg overflow-hidden" data-testid="pt-train-aria-card" style={{ background: 'linear-gradient(135deg, #FAF7FF 0%, #FFFFFF 100%)' }}>
      <div className="px-4 py-2.5 border-b border-[#F0ECF9] flex items-center gap-2">
        <Brain size={14} weight="duotone" className="text-[#7C35DC]" />
        <h3 className="text-xs font-bold uppercase tracking-[0.16em] text-[#7C35DC]">Train Aria</h3>
      </div>
      <div className="p-4 space-y-3">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#64748B] mb-1.5">ICP fit (current: {currentICP || '—'})</div>
          <div className="grid grid-cols-3 gap-1.5">
            {['match', 'partial', 'outside'].map(v => (
              <button key={v} onClick={() => send('icp_fit', v)} disabled={busy}
                data-testid={`train-icp-${v}`}
                className={`text-xs font-semibold py-1.5 rounded-md border ${currentICP === v ? 'bg-[#7C35DC] text-white border-[#7C35DC]' : 'border-[#E2E8F0] text-[#475569] hover:bg-[#F8FAFC]'}`}>
                {v}
              </button>
            ))}
          </div>
        </div>
        <div>
          <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#64748B] mb-1.5">Latest reply was</div>
          <div className="grid grid-cols-3 gap-1.5">
            {[
              { v: 'positive', color: '#7C35DC' },
              { v: 'neutral',  color: '#94A3B8' },
              { v: 'negative', color: '#DC2626' },
            ].map(o => (
              <button key={o.v} onClick={() => send('reply_class', o.v)} disabled={busy}
                data-testid={`train-reply-${o.v}`}
                className="text-xs font-semibold py-1.5 rounded-md border hover:bg-[#F8FAFC]"
                style={{ borderColor: `${o.color}33`, color: o.color }}>
                {o.v}
              </button>
            ))}
          </div>
        </div>
        <div className="pt-2 border-t border-[#F0ECF9]">
          <button onClick={() => send('positive_conversation', 'yes')} disabled={busy}
            data-testid="train-positive-conversation"
            className="w-full text-xs font-bold uppercase tracking-[0.14em] py-2 rounded-md text-white"
            style={{ background: 'linear-gradient(135deg, #7C35DC 0%, #C044E0 100%)' }}>
            Mark "Positive conversation" → +40 score
          </button>
          <div className="text-[10px] text-[#94A3B8] mt-1.5">Use when John has had a real conversation that wasn't captured by automation.</div>
        </div>
        {recentSignals.length > 0 && (
          <div className="pt-2 border-t border-[#F0ECF9]">
            <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#64748B] mb-1">Recent training</div>
            <div className="space-y-0.5">
              {recentSignals.slice(0, 3).map(s => (
                <div key={s.id} className="text-[10px] text-[#475569]">
                  <span className="font-mono">{s.signal_type}</span> = <span className="font-bold">{s.value}</span> · {fmtDateTime(s.created_at)}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default PtLeadDetail;
