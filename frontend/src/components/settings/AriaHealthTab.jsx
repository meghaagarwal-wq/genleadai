// Iter 76 — Aria Health badges tab. Shows founders which Aria capabilities
// are warmed up vs. need attention. Data sourced from GET /api/aria-agent/health.
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Heartbeat, Sparkle, CheckCircle, Warning, XCircle, ArrowRight } from '@phosphor-icons/react';
import api from '../../config/api';

const LEVEL_META = {
  green: {
    badge: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    dot: 'bg-emerald-500',
    icon: CheckCircle,
    label: 'Active',
  },
  amber: {
    badge: 'bg-amber-100 text-amber-700 border-amber-200',
    dot: 'bg-amber-500',
    icon: Warning,
    label: 'Needs attention',
  },
  red: {
    badge: 'bg-rose-100 text-rose-700 border-rose-200',
    dot: 'bg-rose-500',
    icon: XCircle,
    label: 'Not set up',
  },
};

const OVERALL_META = {
  green: { bg: 'from-emerald-500 to-teal-600', label: 'Aria is firing on all cylinders' },
  amber: { bg: 'from-amber-500 to-orange-600', label: "Aria's ready to learn more" },
  red: { bg: 'from-rose-500 to-pink-600', label: 'Set Aria up to start qualifying leads' },
};

export default function AriaHealthTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get('/api/aria-agent/health');
      setData(r.data);
    } catch (_e) {
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  if (loading) {
    return (
      <div data-testid="aria-health-loading" className="bg-white border border-[#E8E0F5] rounded-2xl p-8 text-center text-sm text-[#5A4A7A]">
        Reading Aria's vitals…
      </div>
    );
  }
  if (!data) {
    return (
      <div data-testid="aria-health-error" className="bg-white border border-rose-200 rounded-2xl p-8 text-center text-sm text-rose-700">
        Couldn't load Aria health right now.
        <button onClick={load} className="ml-2 underline">Retry</button>
      </div>
    );
  }

  const overall = OVERALL_META[data.overall] || OVERALL_META.amber;

  return (
    <div data-testid="aria-health-tab" className="space-y-5">
      {/* Hero score card */}
      <div className={`bg-gradient-to-br ${overall.bg} text-white rounded-2xl p-6 shadow-lg`} data-testid="aria-health-hero">
        <div className="flex items-center gap-3 flex-wrap">
          <div className="w-14 h-14 rounded-2xl bg-white/15 backdrop-blur flex items-center justify-center">
            <Heartbeat size={28} weight="duotone" />
          </div>
          <div className="flex-1 min-w-[180px]">
            <p className="text-xs uppercase tracking-[0.18em] font-bold opacity-90">Aria Health</p>
            <h2 className="text-xl font-extrabold mt-0.5" style={{ fontFamily: 'Plus Jakarta Sans' }}>
              {overall.label}
            </h2>
            <p className="text-xs opacity-90 mt-1">{data.score}</p>
          </div>
          <button
            onClick={load}
            data-testid="aria-health-refresh"
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-bold bg-white/15 hover:bg-white/25 backdrop-blur"
          >
            <Sparkle size={14} weight="duotone" /> Refresh
          </button>
        </div>
      </div>

      {/* Cards grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3" data-testid="aria-health-cards">
        {data.cards.map((c) => {
          const meta = LEVEL_META[c.level] || LEVEL_META.amber;
          const Icon = meta.icon;
          return (
            <div
              key={c.key}
              data-testid={`aria-health-card-${c.key}`}
              className="bg-white border border-[#E8E0F5] rounded-2xl p-4 flex flex-col gap-2 hover:shadow-md transition-shadow"
              style={{ boxShadow: 'var(--shadow-card)' }}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className={`w-2.5 h-2.5 rounded-full ${meta.dot}`} aria-hidden />
                  <h3 className="text-sm font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>
                    {c.label}
                  </h3>
                </div>
                <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border ${meta.badge}`}>
                  <Icon size={10} weight="bold" className="inline mr-0.5" />
                  {meta.label}
                </span>
              </div>
              <div className="text-base font-bold text-[#1A0A2E]" data-testid={`aria-health-value-${c.key}`}>{c.value}</div>
              {c.hint && (
                <p className="text-xs text-[#5A4A7A] leading-relaxed">{c.hint}</p>
              )}
              {c.action_path && c.action_label && (
                <button
                  onClick={() => navigate(c.action_path)}
                  data-testid={`aria-health-action-${c.key}`}
                  className="inline-flex items-center gap-1 text-xs font-bold text-[#7C35DC] hover:text-[#5A23B5] mt-1 self-start"
                >
                  {c.action_label} <ArrowRight size={12} weight="bold" />
                </button>
              )}
            </div>
          );
        })}
      </div>

      <p className="text-[10px] text-[#5A4A7A] text-center italic">
        Tip: cards stay amber until each capability has at least one signal. Click any card's action link to set it up.
      </p>
    </div>
  );
}
