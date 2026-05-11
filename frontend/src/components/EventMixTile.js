/**
 * EventMixTile — dashboard tile showing outbound integration events fired
 * over the last 7 days. Demonstrates to the user that Aria is delivering
 * signal to their GA4 / Meta CAPI / Zapier / Make destinations.
 *
 * Auto-hides when no outbound integrations are configured or no events fired.
 */
import React, { useEffect, useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import api from '../config/api';
import { Lightning, CheckCircle, Warning, ArrowRight } from '@phosphor-icons/react';

const TYPE_COLORS = {
  ga4: '#F4B400',
  meta_capi: '#1877F2',
  zapier: '#FF4A00',
  make: '#6D00CC',
};

const EventMixTile = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/api/integrations/event-mix?days=7')
      .then((r) => setData(r.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  const spark = useMemo(() => {
    if (!data?.sparkline?.length) return null;
    const max = Math.max(...data.sparkline.map((d) => d.count), 1);
    return data.sparkline.map((d) => ({ ...d, pct: (d.count / max) * 100 }));
  }, [data]);

  if (loading) {
    return (
      <div className="bg-white border border-[#E8E0F5] rounded-xl p-4" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="event-mix-tile-loading">
        <div className="h-3 w-24 bg-[#F0ECF9] rounded mb-3 animate-pulse"></div>
        <div className="h-12 bg-[#F9F5FF] rounded animate-pulse"></div>
      </div>
    );
  }

  // Hide tile entirely if no events
  if (!data || data.total_events === 0) {
    return (
      <div className="bg-gradient-to-br from-[#FAF7FF] to-white border border-[#E0D4F7] rounded-xl p-4" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="event-mix-tile-empty">
        <div className="flex items-center gap-2 mb-2">
          <Lightning size={14} weight="fill" className="text-[#7C35DC]" />
          <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#7C35DC]">Event Mix</span>
        </div>
        <p className="text-xs text-[#5A4A7A] mb-2 leading-relaxed">Connect GA4, Meta CAPI, Zapier or Make — Aria will fire lead lifecycle events to all of them automatically.</p>
        <Link to="/integrations" data-testid="event-mix-connect-cta" className="inline-flex items-center gap-1 text-[11px] font-bold text-[#7C35DC] hover:text-[#6B28C8]">
          Connect integrations <ArrowRight size={11} weight="bold" />
        </Link>
      </div>
    );
  }

  const healthy = data.overall_success_rate >= 95;

  return (
    <div className="bg-white border border-[#E8E0F5] rounded-xl overflow-hidden" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="event-mix-tile">
      <div className="p-4 border-b border-[#F0ECF9]">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Lightning size={14} weight="fill" className="text-[#7C35DC]" />
            <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#7C35DC]">Event Mix · last {data.days}d</span>
          </div>
          <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-bold rounded ${healthy ? 'bg-[#DCFCE7] text-[#16A34A] border border-[#16A34A]/30' : 'bg-[#FEF3C7] text-[#D97706] border border-[#D97706]/30'}`} data-testid="event-mix-health">
            {healthy ? <CheckCircle size={10} weight="fill" /> : <Warning size={10} weight="fill" />}
            {data.overall_success_rate}%
          </span>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{data.total_events}</span>
          <span className="text-xs font-medium text-[#5A4A7A]">events fired</span>
        </div>

        {/* Sparkline bars */}
        {spark && spark.length > 1 && (
          <div className="flex items-end gap-1 mt-3 h-8" data-testid="event-mix-spark">
            {spark.map((d, i) => (
              <div key={i} className="flex-1 bg-[#F0ECF9] rounded-sm relative overflow-hidden" style={{ height: '100%' }} title={`${d.day}: ${d.count} events`}>
                <div className="absolute bottom-0 left-0 right-0 rounded-sm transition-all"
                  style={{ height: `${d.pct}%`, background: 'linear-gradient(180deg, #7C35DC, #C044E0)' }}></div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="p-3 space-y-1.5">
        {data.integrations.map((it) => {
          const color = TYPE_COLORS[it.type] || '#7C35DC';
          const ok = it.success_rate >= 95;
          return (
            <div key={it.type} className="flex items-center gap-2 text-xs" data-testid={`event-mix-row-${it.type}`}>
              <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: color }}></span>
              <span className="flex-1 truncate text-[#5A4A7A] font-medium">{it.label}</span>
              <span className="font-mono font-bold text-[#1A0A2E]">{it.total}</span>
              <span className={`text-[10px] font-bold w-10 text-right ${ok ? 'text-[#16A34A]' : 'text-[#D97706]'}`}>{it.success_rate}%</span>
            </div>
          );
        })}
      </div>

      <Link to="/integrations" className="block px-4 py-2 border-t border-[#F0ECF9] text-[11px] font-bold text-[#7C35DC] hover:bg-[#FAF7FF] text-center" data-testid="event-mix-view-all">
        View Integration Hub →
      </Link>
    </div>
  );
};

export default EventMixTile;
