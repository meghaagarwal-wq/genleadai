import { useEffect, useRef } from 'react';
import { toast } from 'sonner';
import api from '../config/api';

const MILESTONE_COPY = {
  signup: { emoji: '🎉', title: 'Welcome aboard!', share: 'Just spun up GenLeadAI — let\'s see how fast ARIA gets me to my first booked call.' },
  first_lead: { emoji: '🌱', title: 'First lead captured!', share: 'Got my first lead into GenLeadAI in {time}. ARIA, do your thing.' },
  first_aria: { emoji: '🤖', title: 'ARIA just had her first conversation!', share: 'ARIA had her first AI conversation with a lead {time} after I signed up. Wild.' },
  first_meeting: { emoji: '📅', title: 'First meeting booked!', share: 'GenLeadAI booked my first discovery call {time} after signup. ARIA is unreal.' },
  first_won: { emoji: '🏆', title: 'First deal won!', share: 'Closed my first deal {time} after signing up to GenLeadAI. ARIA paid for itself.' },
};

const STORAGE_KEY = 'genleadai:ttv-celebrated';

const loadCelebrated = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch { return {}; }
};

const saveCelebrated = (obj) => {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(obj)); } catch {}
};

export const useTtvMilestoneWatcher = (enabled = true) => {
  const intervalRef = useRef(null);
  const initialisedRef = useRef(false);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    const celebrated = loadCelebrated();

    const check = async () => {
      try {
        const res = await api.get('/api/ttv/milestones');
        if (cancelled) return;
        const milestones = res.data?.milestones || [];

        // Skip celebrations on the very first poll (so we don't blast toasts on every page load)
        if (!initialisedRef.current) {
          milestones.forEach(m => { if (m.completed) celebrated[m.id] = true; });
          saveCelebrated(celebrated);
          initialisedRef.current = true;
          return;
        }

        milestones.forEach(m => {
          if (m.completed && !celebrated[m.id] && m.id !== 'signup') {
            const copy = MILESTONE_COPY[m.id] || { emoji: '✨', title: m.label, share: '' };
            const timeStr = m.time_from_start || 'now';
            toast.success(`${copy.emoji}  ${copy.title}`, {
              description: `${m.time_from_start ? `${m.time_from_start} from signup` : 'Just unlocked'} — share this win?`,
              duration: 9000,
              action: {
                label: 'Copy share',
                onClick: () => {
                  const text = (copy.share || '').replace('{time}', timeStr);
                  navigator.clipboard?.writeText(text).catch(() => {});
                  toast('Copied to clipboard');
                },
              },
            });
            celebrated[m.id] = true;
            saveCelebrated(celebrated);
          }
        });
      } catch (e) {
        // silent — TTV is non-critical
      }
    };

    // Run once on mount, then every 25s
    check();
    intervalRef.current = setInterval(check, 25000);

    return () => {
      cancelled = true;
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [enabled]);
};
