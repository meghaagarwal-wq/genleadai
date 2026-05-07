import { useState } from 'react';
import { useLocation } from 'react-router-dom';
import { toast } from 'sonner';
import { Bug, Lightbulb, Heart, ChatText, X, PaperPlaneRight } from '@phosphor-icons/react';
import api from '../config/api';

const CATEGORIES = [
  { id: 'bug',    label: 'Bug',      icon: Bug,       accent: '#DC2626' },
  { id: 'idea',   label: 'Idea',     icon: Lightbulb, accent: '#F59E0B' },
  { id: 'praise', label: 'Love it',  icon: Heart,     accent: '#EC4899' },
  { id: 'other',  label: 'Other',    icon: ChatText,  accent: '#7C35DC' },
];

const BetaFeedbackButton = ({ variant = 'sidebar' }) => {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState('');
  const [category, setCategory] = useState('idea');
  const [includeUrl, setIncludeUrl] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const location = useLocation();

  const submit = async () => {
    if (message.trim().length < 3) {
      toast.error('Write a little more so we can action it');
      return;
    }
    setSubmitting(true);
    try {
      await api.post('/api/beta-feedback', {
        message: message.trim(),
        category,
        page_url: includeUrl ? (typeof window !== 'undefined' ? window.location.origin + location.pathname : location.pathname) : null,
      });
      toast.success('Thanks — your feedback reached the team');
      setMessage('');
      setCategory('idea');
      setOpen(false);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Could not send feedback');
    } finally {
      setSubmitting(false);
    }
  };

  const triggerClasses = variant === 'sidebar'
    ? 'w-full flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-[0.18em] text-[#FDE68A] border border-[#F59E0B]/40 hover:bg-[#F59E0B]/10 transition-colors'
    : 'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-[0.18em] text-[#B45309] border border-[#F59E0B]/50 hover:bg-[#F59E0B]/12 transition-colors';

  return (
    <>
      <button onClick={() => setOpen(true)} data-testid="beta-feedback-btn" className={triggerClasses}>
        <ChatText size={12} weight="bold" /> Beta feedback
      </button>

      {open && (
        <div className="fixed inset-0 z-[100] flex items-end sm:items-center justify-center bg-black/50 backdrop-blur-sm p-4" onClick={() => !submitting && setOpen(false)} data-testid="beta-feedback-modal">
          <div
            className="w-full max-w-md bg-white rounded-2xl border border-[#E8E0F5] overflow-hidden"
            style={{ boxShadow: '0 24px 48px -12px rgba(26,10,46,0.35)' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-5 py-4 border-b border-[#F0ECF9] flex items-center justify-between"
              style={{ background: 'linear-gradient(135deg, rgba(245,158,11,0.08) 0%, #FFFFFF 100%)' }}>
              <div>
                <div className="text-[9px] font-bold uppercase tracking-[0.22em] text-[#B45309]">ARIA · Beta</div>
                <h3 className="text-base font-bold text-[#1A0A2E]" style={{ fontFamily: 'Space Grotesk, Inter' }}>Tell us what to fix next</h3>
              </div>
              <button onClick={() => setOpen(false)} disabled={submitting} className="text-[#9B8AB0] hover:text-[#1A0A2E] p-1" data-testid="beta-feedback-close">
                <X size={18} />
              </button>
            </div>

            <div className="p-5 space-y-4">
              {/* Category picker */}
              <div>
                <label className="block text-[10px] font-bold uppercase tracking-[0.2em] text-[#7B6D9C] mb-2">Type</label>
                <div className="grid grid-cols-4 gap-2">
                  {CATEGORIES.map(c => {
                    const Icon = c.icon;
                    const active = category === c.id;
                    return (
                      <button
                        key={c.id}
                        onClick={() => setCategory(c.id)}
                        data-testid={`beta-feedback-cat-${c.id}`}
                        className={`flex flex-col items-center gap-1 py-2.5 rounded-lg border transition-all ${active ? 'border-transparent' : 'border-[#E8E0F5] hover:border-[#C9B6FF]'}`}
                        style={active ? { background: `${c.accent}14`, borderColor: `${c.accent}40`, color: c.accent } : { color: '#5A4A7A' }}
                      >
                        <Icon size={16} weight={active ? 'fill' : 'duotone'} />
                        <span className="text-[10px] font-bold uppercase tracking-[0.1em]">{c.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Message */}
              <div>
                <label className="block text-[10px] font-bold uppercase tracking-[0.2em] text-[#7B6D9C] mb-2">What happened / what would make this better?</label>
                <textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder={category === 'bug' ? 'Briefly: what did you click, what went wrong?' : category === 'idea' ? 'Tell us what you wish ARIA could do…' : category === 'praise' ? 'What worked really well?' : 'Share your thoughts'}
                  rows={4}
                  maxLength={2000}
                  data-testid="beta-feedback-textarea"
                  className="w-full px-3 py-2 rounded-lg border border-[#E8E0F5] focus:ring-2 focus:ring-[#7C35DC]/20 focus:border-[#7C35DC] text-sm outline-none resize-none"
                />
                <div className="mt-1 flex items-center justify-between text-[10px] text-[#9B8AB0]">
                  <span>{message.length} / 2000</span>
                  <label className="flex items-center gap-1.5 cursor-pointer">
                    <input type="checkbox" checked={includeUrl} onChange={(e) => setIncludeUrl(e.target.checked)} data-testid="beta-feedback-include-url" className="accent-[#7C35DC]" />
                    Attach current page URL
                  </label>
                </div>
              </div>
            </div>

            <div className="px-5 py-3 border-t border-[#F0ECF9] bg-[#FAF7FF] flex items-center justify-end gap-2">
              <button onClick={() => setOpen(false)} disabled={submitting} data-testid="beta-feedback-cancel"
                className="px-4 py-2 rounded-lg text-sm font-semibold text-[#5A4A7A] hover:bg-white">
                Cancel
              </button>
              <button onClick={submit} disabled={submitting || message.trim().length < 3} data-testid="beta-feedback-submit"
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-bold text-white disabled:opacity-50"
                style={{ background: 'var(--gradient-brand)' }}>
                <PaperPlaneRight size={14} weight="fill" />
                {submitting ? 'Sending…' : 'Send feedback'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default BetaFeedbackButton;
