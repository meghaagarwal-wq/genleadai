/**
 * ICP Drift Modal (iter158 Phase B Step 5).
 *
 * Triggered from the ICP Drift banner on the B2B Founder dashboard.
 * Shows: 30-day ICP distribution donut, per-channel drift breakdown,
 * snooze button, and a deep-link to channel settings.
 */
import React, { useState } from 'react';
import { X, Warning, Pause, ArrowRight } from '@phosphor-icons/react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import {
  ResponsiveContainer, PieChart, Pie, Cell, Legend, Tooltip,
} from 'recharts';
import api from '../../config/api';
import { HBars } from './dashboard_charts';

const ICP_COLOURS = {
  icp_a:        '#7C35DC',
  icp_b:        '#0E9F86',
  icp_c:        '#3B82F6',
  icp_unknown:  '#EF4444',
  icp_not_fit:  '#F59E0B',
};

const ICP_LABEL = {
  icp_a:        'Primary ICP',
  icp_b:        'Secondary ICP',
  icp_c:        'Tertiary ICP',
  icp_unknown:  'Unknown',
  icp_not_fit:  'Not-fit',
};

export const ICPDriftModal = ({ open, onClose, drift, onSnoozed }) => {
  const [snoozing, setSnoozing] = useState(false);

  // a11y — close on Escape, lock body scroll while open.
  React.useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') onClose?.(); };
    document.addEventListener('keydown', onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [open, onClose]);

  if (!open || !drift) return null;

  const pieData = (drift.icp_distribution || []).map((d) => ({
    name: ICP_LABEL[d.icp] || d.icp || 'Unknown',
    value: d.count,
    key:   d.icp || 'unknown',
  }));
  const byChannel = (drift.by_channel || []).slice(0, 6);
  const worstChannels = byChannel
    .filter((r) => r.unknown_pct >= 30 && r.total >= 3)
    .sort((a, b) => b.unknown_pct - a.unknown_pct);

  const handleSnooze = async () => {
    setSnoozing(true);
    try {
      const r = await api.post('/api/dashboard/icp-drift/snooze', null, { params: { days: 7 } });
      toast.success(`Snoozed until ${new Date(r.data.snoozed_until).toLocaleDateString()}`);
      onSnoozed?.();
      onClose?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not snooze');
    } finally {
      setSnoozing(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-in fade-in duration-200"
      style={{ background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(6px)' }}
      data-testid="icp-drift-modal-backdrop"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="icp-drift-title"
    >
      <div
        className="relative rounded-2xl border max-w-3xl w-full max-h-[90vh] overflow-auto shadow-2xl"
        style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }}
        data-testid="icp-drift-modal"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-3 p-6 border-b" style={{ borderColor: 'var(--theme-border)' }}>
          <div className="flex items-start gap-3">
            <div className="rounded-lg p-2" style={{ background: 'rgba(245,158,11,0.15)' }}>
              <Warning size={22} weight="fill" color="#F59E0B" />
            </div>
            <div>
              <h2 id="icp-drift-title" className="text-base font-bold" style={{ color: 'var(--theme-text)' }}>
                ICP Drift detected
              </h2>
              <p className="text-xs mt-0.5" style={{ color: 'var(--theme-text-muted)' }}>
                Last 30 days · {drift.primary_pct}% primary ICP · {drift.unknown_pct}% unknown
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded hover:bg-[var(--theme-surface2)]"
            data-testid="icp-drift-modal-close"
            aria-label="Close ICP drift modal"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-6">
          {/* 30-day distribution donut */}
          <section>
            <h3 className="text-xs uppercase tracking-[0.16em] font-bold mb-3" style={{ color: 'var(--theme-text-muted)' }}>
              ICP distribution · last 30 days
            </h3>
            <div style={{ width: '100%', height: 220 }}>
              <ResponsiveContainer>
                <PieChart>
                  <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={90} paddingAngle={2} isAnimationActive>
                    {pieData.map((d, i) => (
                      <Cell key={i} fill={ICP_COLOURS[d.key] || '#94A3B8'} />
                    ))}
                  </Pie>
                  <Legend verticalAlign="middle" align="right" layout="vertical" iconSize={9} wrapperStyle={{ fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{ fontSize: 11, background: 'var(--theme-surface)', border: '1px solid var(--theme-border)', borderRadius: 6 }}
                    formatter={(value, name) => [`${value} leads`, name]}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </section>

          {/* Per-channel drift breakdown */}
          <section>
            <h3 className="text-xs uppercase tracking-[0.16em] font-bold mb-3" style={{ color: 'var(--theme-text-muted)' }}>
              Where the drift is coming from · % unknown ICP per channel
            </h3>
            {byChannel.length === 0 ? (
              <div className="text-xs py-4 text-center" style={{ color: 'var(--theme-text-muted)' }}>
                No channel data in the last 30 days.
              </div>
            ) : (
              <HBars
                rows={byChannel.map((c) => ({
                  label: c.channel,
                  value: c.unknown_pct,
                  sub:   `${c.unknown} unknown of ${c.total} leads`,
                  color: c.unknown_pct >= 50 ? '#EF4444' : c.unknown_pct >= 25 ? '#F59E0B' : '#10B981',
                }))}
                unit="%"
                maxValue={100}
              />
            )}
          </section>

          {/* Recommended actions */}
          {worstChannels.length > 0 && (
            <section className="rounded-lg p-4" style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.3)' }}>
              <div className="text-xs font-bold mb-2" style={{ color: '#D97706' }}>
                ARIA recommends
              </div>
              <ul className="text-xs space-y-1.5" style={{ color: 'var(--theme-text)' }}>
                {worstChannels.slice(0, 2).map((c) => (
                  <li key={c.channel} className="flex items-start gap-2">
                    <span className="font-bold capitalize">{c.channel}</span>
                    <span style={{ color: 'var(--theme-text-muted)' }}>
                      — {c.unknown_pct}% unknown. Consider tightening your ICP filter or pausing this source until you re-tune targeting.
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between gap-3 p-4 border-t" style={{ borderColor: 'var(--theme-border)', background: 'var(--theme-surface2)' }}>
          <button
            onClick={handleSnooze}
            disabled={snoozing}
            className="text-xs px-3 py-2 rounded-md font-semibold flex items-center gap-1.5 disabled:opacity-50"
            style={{ background: 'var(--theme-surface)', color: 'var(--theme-text)', border: '1px solid var(--theme-border)' }}
            data-testid="icp-drift-modal-snooze"
          >
            <Pause size={12} weight="bold" /> {snoozing ? 'Snoozing…' : 'Snooze 7 days'}
          </button>
          <Link
            to="/app/integrations"
            onClick={onClose}
            className="text-xs px-4 py-2 rounded-md font-bold flex items-center gap-1.5 text-white"
            style={{ background: 'linear-gradient(135deg, #4C1D95, #7C35DC)' }}
            data-testid="icp-drift-modal-review"
          >
            Review channel settings <ArrowRight size={12} weight="bold" />
          </Link>
        </div>
      </div>
    </div>
  );
};

export default ICPDriftModal;
