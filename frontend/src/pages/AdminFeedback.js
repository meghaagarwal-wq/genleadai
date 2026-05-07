import { useState, useEffect } from 'react';
import { toast } from 'sonner';
import { CheckCircle, Circle, Trash, Bug, Lightbulb, Heart, ChatText, Link as LinkIcon, Funnel } from '@phosphor-icons/react';
import api from '../config/api';

const CAT_META = {
  bug:    { label: 'Bug',    icon: Bug,       color: '#DC2626' },
  idea:   { label: 'Idea',   icon: Lightbulb, color: '#F59E0B' },
  praise: { label: 'Praise', icon: Heart,     color: '#EC4899' },
  other:  { label: 'Other',  icon: ChatText,  color: '#7C35DC' },
};

const AdminFeedback = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filterCat, setFilterCat] = useState('');
  const [showResolved, setShowResolved] = useState(false);

  const load = async () => {
    try {
      const params = {};
      if (filterCat) params.category = filterCat;
      if (!showResolved) params.resolved = false;
      const r = await api.get('/api/beta-feedback', { params });
      setData(r.data);
    } catch (err) {
      if (err.response?.status === 403) {
        toast.error('Admin access only');
      } else {
        toast.error('Could not load feedback');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { setLoading(true); load(); /* eslint-disable-next-line */ }, [filterCat, showResolved]);

  const toggleResolved = async (item) => {
    try {
      await api.patch(`/api/beta-feedback/${item.id}`, { resolved: !item.resolved });
      toast.success(item.resolved ? 'Reopened' : 'Marked resolved');
      load();
    } catch { toast.error('Could not update'); }
  };

  const remove = async (id) => {
    if (!window.confirm('Delete this feedback permanently?')) return;
    try {
      await api.delete(`/api/beta-feedback/${id}`);
      toast.success('Deleted');
      load();
    } catch { toast.error('Could not delete'); }
  };

  if (loading && !data) return <div className="text-[#9B8AB0] text-sm p-8">Loading feedback…</div>;

  const feedback = data?.feedback || [];
  const counts = data?.counts || { total: 0, unresolved: 0, by_category: {} };

  return (
    <div className="space-y-6" data-testid="admin-feedback-page">
      {/* Header */}
      <div>
        <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-[#B45309]">ARIA · Beta</div>
        <h1 className="text-3xl font-bold text-[#1A0A2E] mt-1" style={{ fontFamily: 'Space Grotesk, Inter' }}>User feedback</h1>
        <p className="text-sm text-[#5A4A7A] mt-1">{counts.total} total · {counts.unresolved} unresolved</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="admin-feedback-stats">
        {['bug', 'idea', 'praise', 'other'].map(c => {
          const meta = CAT_META[c];
          const Icon = meta.icon;
          return (
            <div key={c} className="flex items-center gap-3 p-4 rounded-xl bg-white border border-[#E8E0F5]">
              <div className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                style={{ background: `${meta.color}14`, color: meta.color, border: `1px solid ${meta.color}33` }}>
                <Icon size={18} weight="duotone" />
              </div>
              <div>
                <div className="text-2xl font-bold text-[#1A0A2E] leading-none" style={{ fontFamily: 'Space Grotesk, Inter' }}>
                  {counts.by_category?.[c] || 0}
                </div>
                <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#9B8AB0] mt-1">{meta.label}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2 flex-wrap" data-testid="admin-feedback-filters">
        <Funnel size={14} className="text-[#9B8AB0]" weight="duotone" />
        <button onClick={() => setFilterCat('')}
          data-testid="filter-all"
          className={`px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-[0.15em] ${filterCat === '' ? 'bg-[#7C35DC] text-white' : 'bg-white text-[#5A4A7A] border border-[#E8E0F5]'}`}>
          All
        </button>
        {Object.entries(CAT_META).map(([k, m]) => (
          <button key={k} onClick={() => setFilterCat(filterCat === k ? '' : k)} data-testid={`filter-${k}`}
            className={`px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-[0.15em] ${filterCat === k ? 'text-white' : 'bg-white text-[#5A4A7A] border border-[#E8E0F5]'}`}
            style={filterCat === k ? { background: m.color } : {}}>
            {m.label}
          </button>
        ))}
        <div className="flex-1" />
        <label className="flex items-center gap-1.5 text-xs text-[#5A4A7A] cursor-pointer">
          <input type="checkbox" checked={showResolved} onChange={(e) => setShowResolved(e.target.checked)} data-testid="filter-show-resolved" className="accent-[#7C35DC]" />
          Show resolved
        </label>
      </div>

      {/* List */}
      {feedback.length === 0 ? (
        <div className="p-12 text-center bg-white border border-[#E8E0F5] rounded-xl" data-testid="admin-feedback-empty">
          <p className="text-sm text-[#5A4A7A]">No feedback yet. When beta users submit, it'll appear here.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {feedback.map(item => {
            const meta = CAT_META[item.category] || CAT_META.other;
            const Icon = meta.icon;
            return (
              <div key={item.id} className={`bg-white border rounded-xl p-4 ${item.resolved ? 'border-[#DCFCE7] opacity-75' : 'border-[#E8E0F5]'}`} data-testid={`feedback-${item.id}`}>
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
                    style={{ background: `${meta.color}14`, color: meta.color, border: `1px solid ${meta.color}33` }}>
                    <Icon size={16} weight="duotone" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className="text-[10px] font-bold uppercase tracking-[0.15em] px-1.5 py-0.5 rounded-md" style={{ background: `${meta.color}14`, color: meta.color }}>
                        {meta.label}
                      </span>
                      <span className="text-xs font-semibold text-[#1A0A2E]">{item.user_name || item.user_email}</span>
                      <span className="text-[10px] text-[#9B8AB0]">· {new Date(item.created_at).toLocaleString()}</span>
                      {item.resolved && (
                        <span className="text-[9px] font-bold uppercase tracking-[0.15em] px-1.5 py-0.5 rounded-md bg-[#DCFCE7] text-[#16A34A]">Resolved</span>
                      )}
                    </div>
                    <p className="text-sm text-[#1A0A2E] whitespace-pre-wrap" data-testid={`feedback-msg-${item.id}`}>{item.message}</p>
                    {item.page_url && (
                      <a href={item.page_url} target="_blank" rel="noopener noreferrer"
                        className="mt-2 inline-flex items-center gap-1 text-xs text-[#7C35DC] hover:underline">
                        <LinkIcon size={11} weight="bold" /> {item.page_url}
                      </a>
                    )}
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <button onClick={() => toggleResolved(item)} data-testid={`feedback-toggle-${item.id}`}
                      title={item.resolved ? 'Reopen' : 'Mark resolved'}
                      className={`p-2 rounded-lg ${item.resolved ? 'text-[#16A34A] hover:bg-[#DCFCE7]' : 'text-[#9B8AB0] hover:bg-[#F4F0FF] hover:text-[#7C35DC]'}`}>
                      {item.resolved ? <CheckCircle size={16} weight="fill" /> : <Circle size={16} weight="bold" />}
                    </button>
                    <button onClick={() => remove(item.id)} data-testid={`feedback-delete-${item.id}`}
                      className="p-2 rounded-lg text-[#9B8AB0] hover:bg-[#FEE2E2] hover:text-[#DC2626]">
                      <Trash size={14} weight="fill" />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default AdminFeedback;
