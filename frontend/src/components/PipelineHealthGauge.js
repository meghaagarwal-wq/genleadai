/**
 * PipelineHealthGauge — circular SVG 0-100 gauge for the dashboard.
 * Renders nothing when /api/health/pipeline-score is unreachable (graceful).
 */
import React, { useEffect, useState } from 'react';
import api from '../config/api';
import { Heart, Warning, CheckCircle } from '@phosphor-icons/react';

const STATUS_META = {
  good: { label: 'Healthy', color: '#16A34A', icon: CheckCircle },
  warning: { label: 'Needs attention', color: '#D97706', icon: Warning },
  critical: { label: 'Critical', color: '#DC2626', icon: Warning },
};

const FACTOR_LABELS = {
  stale_leads: 'Stale leads',
  no_touchpoints: 'Leads with no touchpoints',
  unresolved_failures: 'Unresolved failures',
  recent_replies_7d: 'Replies in last 7 days',
  meetings_this_month: 'Meetings booked this month',
};

const PipelineHealthGauge = () => {
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get('/api/health/pipeline-score')
      .then((r) => setData(r.data))
      .catch(() => setData(null));
  }, []);

  if (!data) return null;
  const meta = STATUS_META[data.status] || STATUS_META.good;
  const Icon = meta.icon;
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  const dash = (data.score / 100) * circumference;

  return (
    <div className="aria-card-lift bg-white border border-[#E8E0F5] rounded-2xl p-5" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="pipeline-health-gauge">
      <div className="flex items-center gap-2 mb-3">
        <Heart size={16} weight="duotone" className="text-[#7C35DC]" />
        <h3 className="font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Pipeline Health</h3>
      </div>
      <div className="flex items-center gap-5">
        <svg width="120" height="120" viewBox="0 0 120 120" className="flex-shrink-0">
          <circle cx="60" cy="60" r={radius} fill="none" stroke="#F0ECF9" strokeWidth="10" />
          <circle
            cx="60" cy="60" r={radius} fill="none" stroke={meta.color} strokeWidth="10"
            strokeLinecap="round" strokeDasharray={`${dash} ${circumference}`}
            transform="rotate(-90 60 60)" style={{ transition: 'stroke-dasharray 0.6s ease' }}
          />
          <text x="60" y="58" textAnchor="middle" fontSize="28" fontWeight="800" fill="#1A0A2E" style={{ fontFamily: 'Plus Jakarta Sans' }}>{data.score}</text>
          <text x="60" y="78" textAnchor="middle" fontSize="9" fill="#9B8AB0" fontWeight="700" letterSpacing="2">/ 100</text>
        </svg>
        <div className="flex-1 min-w-0">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-xs font-bold" style={{ background: `${meta.color}15`, borderColor: `${meta.color}40`, color: meta.color }} data-testid="health-status-badge">
            <Icon size={12} weight="fill" /> {meta.label}
          </span>
          <div className="mt-3 space-y-1">
            {(data.breakdown || []).slice(0, 4).map((b) => (
              <div key={b.factor} className="flex items-center justify-between text-xs" data-testid={`health-factor-${b.factor}`}>
                <span className="text-[#5A4A7A]">{FACTOR_LABELS[b.factor] || b.factor}</span>
                <span className={`font-mono font-bold ${b.delta >= 0 ? 'text-[#16A34A]' : 'text-[#DC2626]'}`}>{b.delta >= 0 ? '+' : ''}{b.delta}</span>
              </div>
            ))}
            {(data.breakdown || []).length === 0 && (
              <div className="text-xs text-[#9B8AB0]">Everything is healthy — keep going 💪</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default PipelineHealthGauge;
