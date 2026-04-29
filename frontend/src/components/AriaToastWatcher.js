import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { Robot, Fire, Lightning, X, ArrowRight } from '@phosphor-icons/react';
import api from '../config/api';

/**
 * AriaToastWatcher — polls /handoff/alerts and fires a desktop toast
 * the moment a NEW high-priority escalation appears between polls.
 *
 * Logic:
 *  - First poll on mount = baseline (no toasts, just record "seen" keys).
 *  - Every 45s after that, diff the alert list with the seen Set.
 *  - For each net-new alert, fire one elegant brand toast.
 *  - Persist seen keys in sessionStorage so a tab refresh doesn't re-spam.
 *  - Click the toast → navigates to the lead detail (or /aria-agent/handoff).
 */

const STORAGE_KEY = 'aria_toast_seen_v1';
const POLL_INTERVAL_MS = 45_000;

const TRIGGER_ICON = {
  high_value: Fire,
  competitor_question: Lightning,
  wants_founder: Robot,
  proposal_opens: Robot,
};

const TRIGGER_TONE = {
  high_value: { accent: '#DC2626', bg: 'rgba(220,38,38,0.12)' },
  competitor_question: { accent: '#D97706', bg: 'rgba(217,119,6,0.12)' },
  wants_founder: { accent: '#7C35DC', bg: 'rgba(124,53,220,0.12)' },
  proposal_opens: { accent: '#7C35DC', bg: 'rgba(124,53,220,0.12)' },
};

const alertKey = (a) => a.id || `${a.trigger}|${a.first_name || ''}|${a.last_name || ''}|${a.company_name || ''}`;

const loadSeen = () => {
  try { return new Set(JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '[]')); }
  catch { return new Set(); }
};
const saveSeen = (set) => {
  try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify([...set].slice(-200))); } catch { /* swallow */ }
};

const AriaToastWatcher = () => {
  const navigate = useNavigate();
  const seenRef = useRef(loadSeen());
  const baselineDoneRef = useRef(false);

  useEffect(() => {
    let cancelled = false;

    const fireToast = (a) => {
      const Icon = TRIGGER_ICON[a.trigger] || Robot;
      const tone = TRIGGER_TONE[a.trigger] || TRIGGER_TONE.wants_founder;
      const name = `${a.first_name || ''} ${a.last_name || ''}`.trim() || 'New lead';
      const company = a.company_name ? ` · ${a.company_name}` : '';

      toast.custom((t) => (
        <div
          role="button"
          tabIndex={0}
          onClick={() => { toast.dismiss(t); a.id ? navigate(`/leads/${a.id}`) : navigate('/aria-agent/handoff'); }}
          onKeyDown={(e) => { if (e.key === 'Enter') { toast.dismiss(t); a.id ? navigate(`/leads/${a.id}`) : navigate('/aria-agent/handoff'); } }}
          className="aria-fade-up cursor-pointer w-[360px] max-w-[calc(100vw-32px)] rounded-2xl border bg-white overflow-hidden flex"
          style={{ boxShadow: '0 24px 48px -12px rgba(26,15,56,0.18), 0 8px 24px rgba(124,53,220,0.10)', borderColor: tone.bg.replace('0.12', '0.30') }}
          data-testid={`aria-toast-${a.trigger}`}
        >
          <div className="w-1 flex-shrink-0" style={{ background: `linear-gradient(180deg, ${tone.accent} 0%, transparent 100%)` }} />
          <div className="flex-1 p-3.5 flex items-start gap-3">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 mt-0.5 relative" style={{ background: tone.bg, border: `1px solid ${tone.accent}33` }}>
              <Icon size={16} weight="fill" style={{ color: tone.accent }} />
              <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-[#16A34A] aria-pulse-ring" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5 mb-0.5">
                <span className="text-[9px] font-extrabold uppercase tracking-[0.25em] numeric" style={{ color: tone.accent }}>ARIA · ESCALATION</span>
                {a.icp_score && <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-[#F4F0FF] text-[#7C35DC] numeric">ICP {a.icp_score}</span>}
              </div>
              <div className="font-display text-[15px] leading-tight text-[#1A0A2E]">
                {name}{company}
              </div>
              <div className="text-[11px] text-[#5A4A7A] mt-1 line-clamp-2 leading-snug">{a.why}</div>
              <div className="mt-2 inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-[0.18em] text-[#7C35DC] numeric">
                Open lead <ArrowRight size={11} weight="bold" />
              </div>
            </div>
            <button
              onClick={(e) => { e.stopPropagation(); toast.dismiss(t); }}
              className="p-1 text-[#9B8AB0] hover:text-[#1A0A2E] hover:bg-[#F4F0FF] rounded-md transition-colors flex-shrink-0"
              aria-label="Dismiss"
              data-testid="aria-toast-dismiss"
            >
              <X size={14} />
            </button>
          </div>
        </div>
      ), {
        duration: 12_000,
        position: 'bottom-right',
      });
    };

    const poll = async () => {
      try {
        const res = await api.get('/api/aria-agent/handoff/alerts');
        if (cancelled) return;
        const alerts = res.data?.alerts || [];
        if (!baselineDoneRef.current) {
          // First poll = baseline. Mark all current alerts as seen but don't fire toasts.
          alerts.forEach(a => seenRef.current.add(alertKey(a)));
          saveSeen(seenRef.current);
          baselineDoneRef.current = true;
          return;
        }
        // Subsequent poll: fire toasts only for new keys (max 3 per cycle to avoid spam)
        const fresh = alerts.filter(a => !seenRef.current.has(alertKey(a))).slice(0, 3);
        fresh.forEach((a, idx) => {
          setTimeout(() => fireToast(a), idx * 600);
          seenRef.current.add(alertKey(a));
        });
        if (fresh.length > 0) saveSeen(seenRef.current);
      } catch { /* swallow — silent watcher */ }
    };

    // Stagger initial baseline poll a few seconds after mount so the page can settle
    const initialTimeout = setTimeout(poll, 3_000);
    const intervalId = setInterval(poll, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearTimeout(initialTimeout);
      clearInterval(intervalId);
    };
  }, [navigate]);

  return null;
};

export default AriaToastWatcher;
