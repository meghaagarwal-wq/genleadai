import React, { useEffect, useState } from 'react';
import {
  CalendarCheck, TrendUp, TrendDown, Trophy, Snowflake, Lightning,
  ArrowRight, Sparkle, Target, ChatCircle, PhoneCall, CheckCircle, DownloadSimple,
} from '@phosphor-icons/react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import api from '../config/api';
import PageHeader from '../components/PageHeader';

const STAT_ICONS = {
  'New leads': Target, 'Qualified': Sparkle, 'Replies sent': ChatCircle,
  'Calls booked': PhoneCall, 'Deals won': Trophy, 'Deals lost': Snowflake,
};

const WeeklyRecap = () => {
  const [data, setData] = useState(null);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    api.get('/api/aria-agent/weekly-recap').then(r => setData(r.data)).catch(() => setData(null));
  }, []);

  const downloadPdf = async () => {
    setDownloading(true);
    try {
      const r = await api.get('/api/aria-agent/weekly-recap/export.pdf', { responseType: 'blob' });
      const blob = new Blob([r.data], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Aria-Weekly-Recap-${new Date().toISOString().slice(0, 10)}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success('Weekly recap downloaded');
    } catch (e) {
      toast.error("Couldn't generate the PDF — try again in a moment.");
    } finally {
      setDownloading(false);
    }
  };

  if (!data) return <div className="text-sm text-[#9B8AB0] p-6">Loading weekly recap…</div>;

  return (
    <div className="space-y-6" data-testid="weekly-recap-page">
      <PageHeader
        eyebrow="ARIA · Weekly recap"
        title="Your sales week at a glance"
        subtitle="What ARIA ran, what moved, what's at risk. Read this before your Monday planning — it's faster than scrolling the pipeline."
        actions={
          <button
            type="button"
            onClick={downloadPdf}
            disabled={downloading}
            data-testid="weekly-recap-download-btn"
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-gradient-to-r from-[#7C35DC] to-[#C044E0] text-white text-sm font-bold shadow-sm hover:opacity-95 disabled:opacity-50"
          >
            <DownloadSimple size={14} weight="bold" /> {downloading ? 'Generating…' : 'Download Report'}
          </button>
        }
      />

      {/* Hero narrative */}
      <div className="rounded-2xl p-6 relative overflow-hidden" data-testid="recap-hero"
        style={{ background: 'linear-gradient(135deg,#0E0820 0%,#1A0F38 45%,#2B1860 100%)' }}>
        <div className="absolute inset-0 opacity-50 pointer-events-none" style={{ background: 'var(--gradient-aria-glow)' }} />
        <div className="relative flex items-start gap-4 flex-wrap">
          <div className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0"
            style={{ background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.15)' }}>
            <CalendarCheck size={20} weight="fill" className="text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#C9B6FF]">{data.headline}</div>
            <p className="text-xl md:text-2xl font-extrabold text-white mt-2 leading-snug" style={{ fontFamily: 'Plus Jakarta Sans' }}>
              {data.narrative}
            </p>
            {data.top_channel && data.top_channel !== '—' && (
              <div className="inline-flex items-center gap-2 mt-4 px-3 py-1.5 rounded-full bg-white/10 border border-white/15">
                <Lightning size={12} weight="fill" className="text-[#C044E0]" />
                <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-white">Top channel · {data.top_channel}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3" data-testid="recap-stats">
        {(data.stats || []).map(s => {
          const Icon = STAT_ICONS[s.label] || Sparkle;
          const delta = s.delta || 0;
          const DeltaIcon = delta > 0 ? TrendUp : delta < 0 ? TrendDown : null;
          const deltaColor = delta > 0 ? '#16A34A' : delta < 0 ? '#DC2626' : '#9B8AB0';
          return (
            <div key={s.label} className="bg-white border border-[#E8E0F5] rounded-2xl p-4" style={{ boxShadow: 'var(--shadow-card)' }} data-testid={`recap-stat-${s.label.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`}>
              <div className="flex items-center justify-between mb-3">
                <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: '#F4F0FF', border: '1px solid #E0D4F7' }}>
                  <Icon size={14} weight="fill" className="text-[#7C35DC]" />
                </div>
                {DeltaIcon && (
                  <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold"
                    style={{ color: deltaColor, background: `${deltaColor}14`, border: `1px solid ${deltaColor}33` }}>
                    <DeltaIcon size={10} weight="bold" />{Math.abs(delta)}%
                  </div>
                )}
              </div>
              <div className="text-3xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{s.value}</div>
              <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#7B6D9C] mt-1">{s.label}</div>
              <div className="text-[10px] text-[#9B8AB0] mt-1">vs {s.prev} last week</div>
            </div>
          );
        })}
      </div>

      {/* Biggest win / miss */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <HighlightCard
          testId="biggest-win"
          tone="win"
          eyebrow="BIGGEST WIN"
          title={data.biggest_win ? `${data.biggest_win.first_name || ''} ${data.biggest_win.last_name || ''}`.trim() || 'Lead' : 'No wins logged yet'}
          company={data.biggest_win?.company_name}
          meta={data.biggest_win ? [
            data.biggest_win.deal_value ? `Deal: $${Number(data.biggest_win.deal_value).toLocaleString()}` : null,
            data.biggest_win.icp_score ? `ICP ${data.biggest_win.icp_score}` : null,
          ].filter(Boolean) : ['Close one this week — ARIA has hot leads ready.']}
          icon={Trophy}
        />
        <HighlightCard
          testId="biggest-miss"
          tone="miss"
          eyebrow="AT RISK"
          title={data.biggest_miss ? `${data.biggest_miss.first_name || ''} ${data.biggest_miss.last_name || ''}`.trim() || 'Silent lead' : 'Nothing silent. Clean pipeline.'}
          company={data.biggest_miss?.company_name}
          meta={data.biggest_miss ? [
            data.biggest_miss.icp_score ? `ICP ${data.biggest_miss.icp_score}` : null,
            'Silent — needs founder touch',
          ].filter(Boolean) : ['Keep the cadence going.']}
          icon={Snowflake}
        />
      </div>

      {/* Next week focus */}
      <div className="bg-white border border-[#E8E0F5] rounded-2xl overflow-hidden" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="recap-next-week">
        <div className="px-5 py-4 border-b border-[#F0ECF9] flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: 'var(--gradient-brand)' }}>
            <Sparkle size={18} weight="fill" className="text-white" />
          </div>
          <div>
            <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC]" style={{ fontFamily: 'Plus Jakarta Sans' }}>ARIA'S FOCUS FOR NEXT WEEK</div>
            <h3 className="text-lg font-extrabold text-[#1A0A2E] mt-0.5" style={{ fontFamily: 'Plus Jakarta Sans' }}>Three things that will move the number</h3>
          </div>
        </div>
        <div className="divide-y divide-[#F0ECF9]">
          {(data.next_week_focus || []).map((f, idx) => (
            <div key={idx} className="px-5 py-4 flex items-center gap-3" data-testid={`recap-focus-${idx}`}>
              <div className="w-7 h-7 rounded-lg flex items-center justify-center bg-[#F4F0FF] border border-[#E0D4F7] flex-shrink-0">
                <span className="text-[11px] font-extrabold text-[#7C35DC]">{idx + 1}</span>
              </div>
              <div className="flex-1 text-sm font-semibold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{f}</div>
              <CheckCircle size={16} weight="duotone" className="text-[#7C35DC] flex-shrink-0" />
            </div>
          ))}
        </div>
        <div className="px-5 py-3 bg-[#FAF7FF] border-t border-[#F0ECF9] flex items-center justify-between">
          <span className="text-xs text-[#5A4A7A]">ARIA will work these in the background.</span>
          <Link to="/" className="inline-flex items-center gap-1 text-xs font-bold text-[#7C35DC] hover:underline" data-testid="recap-back-to-dashboard">
            Back to dashboard <ArrowRight size={12} weight="bold" />
          </Link>
        </div>
      </div>
    </div>
  );
};

const HighlightCard = ({ eyebrow, title, company, meta = [], icon: Icon, tone, testId }) => {
  const palette = tone === 'win'
    ? { bg: '#DCFCE7', border: '#16A34A33', text: '#16A34A', iconBg: '#16A34A' }
    : { bg: '#FEF3C7', border: '#D9770633', text: '#D97706', iconBg: '#D97706' };
  return (
    <div className="bg-white border border-[#E8E0F5] rounded-2xl p-5 flex items-start gap-4" style={{ boxShadow: 'var(--shadow-card)' }} data-testid={testId}>
      <div className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0"
        style={{ background: palette.iconBg }}>
        <Icon size={20} weight="fill" className="text-white" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="inline-flex items-center gap-2 px-2 py-0.5 rounded-full mb-2"
          style={{ background: palette.bg, border: `1px solid ${palette.border}` }}>
          <span className="text-[9px] font-bold uppercase tracking-[0.2em]" style={{ color: palette.text }}>{eyebrow}</span>
        </div>
        <div className="text-lg font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{title}</div>
        {company && <div className="text-sm text-[#5A4A7A]">{company}</div>}
        <div className="flex flex-wrap gap-1.5 mt-2">
          {meta.map((m, i) => (
            <span key={i} className="text-[10px] font-semibold text-[#5A4A7A] bg-[#F4F0FF] border border-[#E0D4F7] px-2 py-0.5 rounded-md">{m}</span>
          ))}
        </div>
      </div>
    </div>
  );
};

export default WeeklyRecap;
