import React, { useEffect, useState } from 'react';
import { Brain, ChatCircle, EnvelopeOpen, Lightning, Trophy, Snowflake, Clock, User, Sparkle, ChartLineUp } from '@phosphor-icons/react';
import api from '../config/api';
import PageHeader from '../components/PageHeader';

const ICON_MAP = { Brain, ChatCircle, EnvelopeOpen, Lightning, Trophy, Snowflake, Clock, User };

const AriaInsightsPage = () => {
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get('/api/aria-agent/insights').then(r => setData(r.data)).catch(() => setData(null));
  }, []);

  if (!data) return <div className="text-sm text-[#9B8AB0] p-6">Loading insights…</div>;

  return (
    <div className="space-y-6" data-testid="aria-insights-page">
      <PageHeader
        eyebrow="ARIA · Insights"
        title="What ARIA learned from your conversations"
        subtitle="ARIA reads every reply, every objection, every win and loss — and surfaces patterns you'd miss in a spreadsheet."
      />

      {/* Live observation */}
      <div className="rounded-2xl px-5 py-5 flex items-start gap-3" style={{ background: 'linear-gradient(135deg,#1A0F38 0%,#7C35DC 100%)' }} data-testid="insights-live-observation">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-white/10 border border-white/15 flex-shrink-0">
          <Sparkle size={18} weight="fill" className="text-white" />
        </div>
        <div>
          <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#C9B6FF]" style={{ fontFamily: 'Plus Jakarta Sans' }}>ARIA NOTICED</div>
          <p className="text-base font-extrabold text-white mt-1 leading-relaxed" style={{ fontFamily: 'Plus Jakarta Sans' }}>{data.live_observation}</p>
        </div>
      </div>

      {/* Insight cards grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {(data.headline_insights || []).map((insight, idx) => {
          const Icon = ICON_MAP[insight.icon] || Brain;
          return (
            <div key={idx} className="bg-white border border-[#E8E0F5] rounded-2xl p-5" style={{ boxShadow: 'var(--shadow-card)' }} data-testid={`insight-card-${idx}`}>
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: '#F4F0FF', border: '1px solid #E0D4F7' }}>
                  <Icon size={18} weight="fill" className="text-[#7C35DC]" />
                </div>
                <h3 className="text-base font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{insight.title}</h3>
              </div>
              <ul className="space-y-2">
                {insight.items.map((item, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-[#5A4A7A]">
                    <span className="text-[#7C35DC] mt-0.5">•</span>{item}
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>

      {/* Recommendations */}
      <div className="bg-white border border-[#E8E0F5] rounded-2xl overflow-hidden" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="insights-recommendations">
        <div className="px-5 py-4 border-b border-[#F0ECF9] flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: 'var(--gradient-brand)' }}>
            <ChartLineUp size={18} weight="fill" className="text-white" />
          </div>
          <div>
            <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC]" style={{ fontFamily: 'Plus Jakarta Sans' }}>ARIA'S RECOMMENDATIONS</div>
            <h3 className="text-lg font-extrabold text-[#1A0A2E] mt-0.5" style={{ fontFamily: 'Plus Jakarta Sans' }}>What to ship next</h3>
          </div>
        </div>
        <div className="divide-y divide-[#F0ECF9]">
          {(data.recommendations || []).map(rec => (
            <div key={rec.id} className="px-5 py-4 flex items-center justify-between gap-3" data-testid={`insights-rec-${rec.id}`}>
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-[#FAF7FF] border border-[#EDE5FA]">
                  <Lightning size={14} weight="fill" className="text-[#7C35DC]" />
                </div>
                <div className="text-sm font-semibold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{rec.title}</div>
              </div>
              <span className="px-2 py-1 rounded-md text-[10px] font-bold uppercase tracking-[0.15em] bg-[#DCFCE7] text-[#16A34A] border border-[#16A34A]/30 flex-shrink-0" style={{ fontFamily: 'Plus Jakarta Sans' }}>{rec.impact}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default AriaInsightsPage;
