import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, Robot, Fire, Lightning, Snowflake, ArrowRight, Sparkle } from '@phosphor-icons/react';
import api from '../config/api';

/**
 * ARIA Notifications Bell — top bar dropdown that surfaces:
 *   1. Live handoff alerts ("Founder attention needed" — escalations from /handoff/alerts)
 *   2. Hot leads still untouched (from agent activity)
 *   3. Today's ARIA momentum summary
 *
 * Polls every 60s. Red dot only shows when there are real, unread items.
 * Click outside or Escape to close.
 */

const NotificationsBell = () => {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [alerts, setAlerts] = useState([]);
  const [activity, setActivity] = useState(null);
  const [unread, setUnread] = useState(0);
  const ref = useRef(null);

  const load = async () => {
    try {
      const [alertsRes, activityRes] = await Promise.all([
        api.get('/api/aria-agent/handoff/alerts'),
        api.get('/api/aria-agent/agent-activity'),
      ]);
      const a = alertsRes.data?.alerts || [];
      setAlerts(a);
      setActivity(activityRes.data || null);
      // unread = handoff alerts + hot escalated count (capped) — only if user hasn't opened dropdown this session for that count
      const total = a.length + (activityRes.data?.hot_escalated || 0);
      const seen = parseInt(sessionStorage.getItem('aria_notif_seen') || '0', 10);
      setUnread(Math.max(0, total - seen));
    } catch (e) { /* swallow */ }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 60000);
    return () => clearInterval(id);
  }, []);

  // Close on outside click + Escape
  useEffect(() => {
    if (!open) return;
    const onClick = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('mousedown', onClick); document.removeEventListener('keydown', onKey); };
  }, [open]);

  const handleOpen = () => {
    setOpen(prev => {
      const next = !prev;
      if (next) {
        // Mark current count as seen
        const total = (alerts?.length || 0) + (activity?.hot_escalated || 0);
        sessionStorage.setItem('aria_notif_seen', String(total));
        setUnread(0);
      }
      return next;
    });
  };

  const totalCount = alerts.length;
  const overdueCount = activity?.hot_escalated || 0;

  return (
    <div className="relative" ref={ref}>
      <button onClick={handleOpen} aria-label="ARIA notifications" className="relative p-2 text-[#5A4A7A] hover:text-[#7C35DC] hover:bg-[#F4F0FF] rounded-lg transition-all" data-testid="notifications-button">
        <Bell size={18} weight="duotone" />
        {unread > 0 && (
          <span className="absolute top-1 right-1 min-w-[16px] h-4 px-1 rounded-full text-[9px] font-extrabold text-white flex items-center justify-center numeric" style={{ background: 'linear-gradient(135deg,#DC2626 0%,#C044E0 100%)', boxShadow: '0 0 0 2px #fff' }} data-testid="notifications-badge">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-[380px] max-w-[calc(100vw-32px)] rounded-2xl bg-white border border-[#E8E0F5] overflow-hidden z-50 aria-fade-up" style={{ boxShadow: '0 24px 48px -12px rgba(26,15,56,0.18), 0 8px 24px rgba(124,53,220,0.08)' }} data-testid="notifications-dropdown">
          {/* Header */}
          <div className="relative px-5 py-4 overflow-hidden aria-grain" style={{ background: 'var(--gradient-aria-deep)' }}>
            <div className="relative flex items-center gap-3">
              <div className="relative w-9 h-9 rounded-xl flex items-center justify-center bg-white/10 border border-white/15 flex-shrink-0">
                <Robot size={16} weight="fill" className="text-white" />
                <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-[#16A34A] aria-pulse-ring" />
              </div>
              <div>
                <div className="text-[10px] font-bold uppercase tracking-[0.3em] text-[#C9B6FF] numeric">ARIA · LIVE FEED</div>
                <div className="font-display text-lg leading-tight text-white mt-0.5">
                  {totalCount > 0 ? `${totalCount} need${totalCount === 1 ? 's' : ''} your attention` : 'All clear — ARIA is working.'}
                </div>
              </div>
            </div>
          </div>

          {/* Activity strip */}
          {activity && (
            <div className="px-5 py-3 border-b border-[#F0ECF9] grid grid-cols-3 gap-2" data-testid="notifications-activity-strip">
              {[
                { label: 'Responded', value: activity.responded_today, color: '#7C35DC' },
                { label: 'Calls booked', value: activity.calls_booked, color: '#C044E0' },
                { label: 'Hot escalated', value: activity.hot_escalated, color: '#DC2626' },
              ].map(s => (
                <div key={s.label} className="text-center">
                  <div className="font-display text-2xl leading-none numeric" style={{ color: s.color }}>{s.value || 0}</div>
                  <div className="text-[9px] font-bold uppercase tracking-[0.18em] text-[#9B8AB0] mt-1 numeric">{s.label}</div>
                </div>
              ))}
            </div>
          )}

          {/* Alerts list */}
          <div className="max-h-[320px] overflow-y-auto divide-y divide-[#F0ECF9]" data-testid="notifications-alerts-list">
            {alerts.length === 0 && (
              <div className="px-5 py-8 text-center" data-testid="notifications-empty">
                <Sparkle size={20} weight="fill" className="text-[#7C35DC] mx-auto mb-2 aria-glow" />
                <div className="font-display text-base text-[#1A0A2E]">No escalations right now.</div>
                <p className="text-xs text-[#9B8AB0] mt-1">ARIA will ping you the moment a human is needed.</p>
              </div>
            )}
            {alerts.map((a, idx) => {
              const TriggerIcon = a.trigger === 'high_value' ? Fire : a.trigger === 'competitor_question' ? Lightning : a.trigger === 'wants_founder' ? Robot : Snowflake;
              return (
                <button
                  key={a.id || idx}
                  onClick={() => { setOpen(false); a.id ? navigate(`/leads/${a.id}`) : navigate('/aria-agent/handoff'); }}
                  className="w-full text-left px-5 py-3.5 hover:bg-[#FAF7FF] transition-colors flex items-start gap-3 group"
                  data-testid={`notifications-alert-${idx}`}
                >
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5" style={{ background: '#FEE2E2', border: '1px solid rgba(220,38,38,0.2)' }}>
                    <TriggerIcon size={14} weight="fill" className="text-[#DC2626]" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{a.first_name} {a.last_name}</span>
                      {a.company_name && <span className="text-xs text-[#9B8AB0] truncate">· {a.company_name}</span>}
                    </div>
                    <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#DC2626] mt-0.5 numeric">{a.trigger_label}</div>
                    <p className="text-xs text-[#5A4A7A] mt-1 line-clamp-2 leading-relaxed">{a.why}</p>
                  </div>
                  <ArrowRight size={14} className="text-[#7C35DC] flex-shrink-0 mt-1 group-hover:translate-x-0.5 transition-transform" />
                </button>
              );
            })}
          </div>

          {/* Footer */}
          <div className="px-5 py-3 border-t border-[#F0ECF9] flex items-center justify-between bg-[#FAF7FF]/40">
            <button onClick={() => { setOpen(false); navigate('/aria-agent/handoff'); }} className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#7C35DC] hover:underline numeric" data-testid="notifications-view-all">
              View all escalations →
            </button>
            <div className="text-[10px] text-[#9B8AB0] font-display-italic">refreshes every minute</div>
          </div>
        </div>
      )}
    </div>
  );
};

export default NotificationsBell;
