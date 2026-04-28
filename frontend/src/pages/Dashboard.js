import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import api from '../config/api';
import {
  Users, TrendUp, Fire, Target, ArrowRight, Lightning, Robot,
  CalendarCheck, Moon, Sparkle, Clock, Phone, EnvelopeSimple,
  CurrencyCircleDollar, ChartLineUp, ArrowUpRight, Warning,
  CheckCircle, Trophy, User, Tray,
} from '@phosphor-icons/react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, AreaChart, Area,
} from 'recharts';

const Dashboard = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [analytics, setAnalytics] = useState(null);
  const [recentLeads, setRecentLeads] = useState([]);
  const [ariaStats, setAriaStats] = useState(null);
  const [topLeads, setTopLeads] = useState([]);
  const [sleepingCount, setSleepingCount] = useState(0);
  const [ttv, setTtv] = useState(null);
  const [recentOpens, setRecentOpens] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { fetchAll(); }, []);

  const fetchAll = async () => {
    try {
      const [aRes, lRes, arRes, tRes, sRes, ttvRes, opensRes] = await Promise.all([
        api.get('/api/analytics/dashboard'),
        api.get('/api/leads?limit=5'),
        api.get('/api/aria/analytics').catch(() => ({ data: null })),
        api.get('/api/leads/your-five-today').catch(() => ({ data: { leads: [] } })),
        api.get('/api/leads/sleeping?threshold_days=14').catch(() => ({ data: { total: 0 } })),
        api.get('/api/ttv/milestones').catch(() => ({ data: null })),
        api.get('/api/lead-magnets/recent-opens?limit=5').catch(() => ({ data: { opens: [] } })),
      ]);
      setAnalytics(aRes.data);
      setRecentLeads(lRes.data.leads);
      setAriaStats(arRes.data);
      setTopLeads(tRes.data.leads?.slice(0, 3) || []);
      setSleepingCount(sRes.data.total || 0);
      setTtv(ttvRes.data);
      setRecentOpens(opensRes.data?.opens || []);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  };

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="flex flex-col items-center gap-3">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center animate-pulse" style={{ background: 'var(--gradient-brand)' }}>
          <Sparkle size={20} className="text-white" weight="fill" />
        </div>
        <span className="text-sm text-[#9B8AB0]">Loading your dashboard...</span>
      </div>
    </div>
  );

  const channelData = analytics ? Object.entries(analytics.channel_distribution).filter(([, v]) => v > 0).map(([k, v]) => ({ name: k.replace('_', ' '), value: v })).sort((a, b) => b.value - a.value).slice(0, 6) : [];
  const typeData = analytics ? [{ name: 'B2B', value: analytics.lead_type_distribution.B2B }, { name: 'B2C', value: analytics.lead_type_distribution.B2C }] : [];
  const icpData = analytics ? [{ name: 'Hot', value: analytics.icp_distribution.hot, color: '#7C35DC' }, { name: 'Warm', value: analytics.icp_distribution.warm, color: '#D97706' }, { name: 'Cold', value: analytics.icp_distribution.cold, color: '#CBD5E1' }] : [];
  const funnelData = analytics ? [
    { stage: 'New', value: analytics.status_distribution.new || 0 },
    { stage: 'Contacted', value: analytics.status_distribution.contacted || 0 },
    { stage: 'Qualified', value: analytics.status_distribution.qualified || 0 },
    { stage: 'Proposal', value: analytics.status_distribution.proposal_sent || 0 },
    { stage: 'Won', value: analytics.status_distribution.won || 0 },
  ] : [];
  const tooltipStyle = { background: '#fff', border: '1px solid #E8E0F5', borderRadius: '12px', color: '#1A0A2E', boxShadow: 'var(--shadow-card)', fontSize: 12 };

  const greeting = () => {
    const h = new Date().getHours();
    if (h < 12) return 'Good morning';
    if (h < 17) return 'Good afternoon';
    return 'Good evening';
  };

  const tierBadge = (tier) => {
    const s = { hot: 'bg-[#F4E6FD] text-[#7C35DC] border-[#C044E0]', warm: 'bg-[#FEF3C7] text-[#D97706] border-[#D97706]/30', cold: 'bg-[#F1F5F9] text-[#64748B] border-[#94A3B8]/30' };
    return `px-1.5 py-0.5 text-[10px] font-bold uppercase rounded border ${s[tier] || s.cold}`;
  };

  return (
    <div data-testid="dashboard-page" className="space-y-5 max-w-[1400px] mx-auto">
      {/* Greeting Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-[#1A0A2E] tracking-tight" style={{ fontFamily: 'Plus Jakarta Sans' }}>
            {greeting()}, {user?.full_name?.split(' ')[0] || 'there'}
          </h1>
          <p className="text-sm text-[#5A4A7A] mt-1">Here's what's happening with your leads today</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => navigate('/your-5-today')} className="flex items-center gap-2 px-4 py-2 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-xl hover:bg-[#F9F5FF] hover:text-[#7C35DC] hover:border-[#7C35DC]/20 transition-all text-sm font-medium" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid="your5-shortcut">
            <Lightning size={16} weight="fill" className="text-[#7C35DC]" /> Your 5 Today
          </button>
          <button onClick={() => navigate('/leads')} data-testid="view-all-leads-btn" className="flex items-center gap-2 btn-gradient px-4 py-2 rounded-xl text-sm font-semibold" style={{ fontFamily: 'Plus Jakarta Sans' }}>
            View All Leads <ArrowRight size={14} />
          </button>
        </div>
      </div>

      {/* Sleeping Leads Alert Banner */}
      {sleepingCount > 5 && (
        <div className="flex items-center justify-between p-4 rounded-xl border" style={{ background: 'linear-gradient(135deg, rgba(192,68,224,0.06) 0%, rgba(91,40,212,0.06) 100%)', borderColor: 'rgba(124,53,220,0.15)' }} data-testid="sleeping-alert-banner">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[#F4F0FF] flex items-center justify-center border border-[#E0D4F7]">
              <CurrencyCircleDollar size={20} className="text-[#7C35DC]" weight="fill" />
            </div>
            <div>
              <p className="text-sm font-semibold text-[#1A0A2E]"><span className="text-[#7C35DC]">{sleepingCount} leads</span> are sitting untouched for 14+ days</p>
              <p className="text-xs text-[#5A4A7A]">ARIA can re-engage them with personalized messages right now</p>
            </div>
          </div>
          <button onClick={() => navigate('/sleeping-leads')} className="flex items-center gap-2 px-4 py-2 bg-[#F4F0FF] text-[#7C35DC] border border-[#7C35DC]/20 rounded-xl text-sm font-semibold hover:bg-[#7C35DC] hover:text-white transition-all" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid="activate-revival-btn">
            <Moon size={16} weight="fill" /> Revive Leads <ArrowRight size={14} />
          </button>
        </div>
      )}

      {/* Brochure Opens Alert — leads who opened your lead magnet */}
      {recentOpens.length > 0 && (
        <div className="rounded-xl border overflow-hidden" style={{ background: 'linear-gradient(135deg, rgba(220,38,38,0.05) 0%, rgba(192,68,224,0.06) 100%)', borderColor: 'rgba(220,38,38,0.2)' }} data-testid="brochure-opens-alert">
          <div className="flex items-center justify-between p-4 border-b" style={{ borderColor: 'rgba(220,38,38,0.15)' }}>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #DC2626 0%, #C044E0 100%)' }}>
                <Fire size={18} className="text-white" weight="fill" />
              </div>
              <div>
                <p className="text-sm font-semibold text-[#1A0A2E]">
                  <span className="text-[#DC2626]">{recentOpens.length} {recentOpens.length === 1 ? 'lead' : 'leads'}</span> just opened your brochure
                </p>
                <p className="text-xs text-[#5A4A7A]">They're warm right now — perfect time to reach out</p>
              </div>
            </div>
          </div>
          <div className="px-4 py-2 divide-y divide-[#F4E6F0]">
            {recentOpens.slice(0, 3).map(o => (
              <button
                key={o.lead_id}
                onClick={() => navigate(`/leads/${o.lead_id}`)}
                className="w-full flex items-center justify-between py-2.5 px-2 rounded-lg hover:bg-white/50 transition-colors text-left"
                data-testid={`brochure-open-row-${o.lead_id}`}
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-7 h-7 rounded-full bg-white border border-[#E8E0F5] flex items-center justify-center flex-shrink-0">
                    <span className="text-[10px] font-bold text-[#7C35DC]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{(o.first_name?.[0] || '?').toUpperCase()}</span>
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-[#1A0A2E] truncate">{o.first_name} {o.last_name}</span>
                      {o.is_hot && (
                        <span className="flex items-center gap-0.5 text-[9px] font-bold uppercase px-1.5 py-0.5 rounded bg-[#FEE2E2] text-[#DC2626] border border-[#DC2626]/20">
                          <Fire size={9} weight="fill" /> {o.view_count}× hot
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-[#9B8AB0] truncate block">{o.company_name || o.email}</span>
                  </div>
                </div>
                <ArrowRight size={14} className="text-[#7C35DC] flex-shrink-0" />
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Time to Value Tracker */}
      {ttv && ttv.progress_pct < 100 && (
        <div className="bg-white border border-[#E8E0F5] rounded-xl p-5" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="ttv-tracker">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-bold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Your Progress</h3>
              <p className="text-xs text-[#5A4A7A] mt-0.5">{ttv.completed_count} of {ttv.total_milestones} milestones completed</p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-2xl font-extrabold text-[#7C35DC]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{ttv.progress_pct}%</span>
            </div>
          </div>
          {/* Progress bar */}
          <div className="w-full h-2 bg-[#F0ECF9] rounded-full mb-5 overflow-hidden">
            <div className="h-full rounded-full transition-all duration-700" style={{ width: `${ttv.progress_pct}%`, background: 'var(--gradient-brand-horizontal)' }}></div>
          </div>
          {/* Milestone steps */}
          <div className="flex items-start justify-between relative">
            {/* Connector line */}
            <div className="absolute top-4 left-6 right-6 h-0.5 bg-[#F0ECF9]" style={{ zIndex: 0 }}></div>
            <div className="absolute top-4 left-6 h-0.5 transition-all duration-700" style={{ width: `${Math.max(0, (ttv.completed_count - 1) / (ttv.total_milestones - 1) * 100)}%`, background: 'var(--gradient-brand-horizontal)', zIndex: 1 }}></div>
            {ttv.milestones.map((m, i) => {
              const IconMap = { user: User, tray: Tray, robot: Robot, calendar: CalendarCheck, trophy: Trophy };
              const MIcon = IconMap[m.icon] || CheckCircle;
              return (
                <div key={m.id} className="flex flex-col items-center relative z-10" style={{ flex: 1 }}>
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center transition-all ${
                    m.completed
                      ? 'text-white shadow-md'
                      : 'bg-[#F0ECF9] text-[#9B8AB0] border-2 border-[#E8E0F5]'
                  }`} style={m.completed ? { background: 'var(--gradient-brand)', boxShadow: '0 0 12px rgba(124,53,220,0.3)' } : {}}>
                    {m.completed ? <CheckCircle size={16} weight="fill" /> : <MIcon size={14} />}
                  </div>
                  <span className={`text-[10px] mt-2 font-semibold text-center leading-tight max-w-[80px] ${m.completed ? 'text-[#7C35DC]' : 'text-[#9B8AB0]'}`} style={{ fontFamily: 'Plus Jakarta Sans' }}>{m.label}</span>
                  {m.time_from_start && (
                    <span className="text-[9px] mt-0.5 font-mono text-[#16A34A] bg-[#DCFCE7] px-1.5 py-0.5 rounded">{m.time_from_start}</span>
                  )}
                </div>
              );
            })}
          </div>
          {ttv.ttv_to_meeting && (
            <div className="mt-4 pt-4 border-t border-[#F0ECF9] text-center">
              <span className="text-xs text-[#5A4A7A]">Time to first meeting: </span>
              <span className="text-sm font-bold text-[#7C35DC] font-mono">{ttv.ttv_to_meeting}</span>
            </div>
          )}
        </div>
      )}

      {/* KPI Cards — 5 columns */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        {[
          { label: 'Total Leads', value: analytics?.total_leads || 0, icon: Users, color: '#7C35DC', sub: 'In pipeline', onClick: () => navigate('/leads') },
          { label: 'Hot Leads', value: analytics?.icp_distribution?.hot || 0, icon: Fire, color: '#C044E0', sub: 'ICP 70+', onClick: () => navigate('/leads') },
          { label: 'Meetings', value: ariaStats?.meetings_booked || 0, icon: CalendarCheck, color: '#16A34A', sub: 'Booked by ARIA', onClick: () => navigate('/aria') },
          { label: 'Won Deals', value: analytics?.status_distribution?.won || 0, icon: Target, color: '#16A34A', sub: 'Closed', onClick: () => navigate('/pipeline') },
          { label: 'ARIA Convos', value: ariaStats?.total_conversations || 0, icon: Robot, color: '#7C35DC', sub: `${ariaStats?.reply_rate || 0}% reply rate`, onClick: () => navigate('/aria') },
        ].map(kpi => (
          <button key={kpi.label} onClick={kpi.onClick} className="bg-white border border-[#E8E0F5] rounded-xl p-4 hover:shadow-[var(--shadow-hover)] hover:-translate-y-0.5 transition-all text-left group" style={{ boxShadow: 'var(--shadow-card)' }} data-testid={`kpi-${kpi.label.toLowerCase().replace(/\s/g, '-')}`}>
            <div className="flex items-center justify-between mb-3">
              <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-[#9B8AB0]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{kpi.label}</span>
              <kpi.icon size={18} style={{ color: kpi.color }} weight="duotone" />
            </div>
            <div className="text-2xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{kpi.value}</div>
            <div className="flex items-center gap-1 mt-1">
              <span className="text-[11px] text-[#5A4A7A]">{kpi.sub}</span>
              <ArrowUpRight size={10} className="text-[#9B8AB0] opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
          </button>
        ))}
      </div>

      {/* Main Grid: 3 columns */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* Left: Top Leads to Act On + ARIA Summary */}
        <div className="space-y-4">
          {/* Your Top 3 */}
          <div className="bg-white border border-[#E8E0F5] rounded-xl" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="top-leads-widget">
            <div className="p-4 border-b border-[#E8E0F5] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Lightning size={16} className="text-[#7C35DC]" weight="fill" />
                <h3 className="text-sm font-bold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Priority Leads</h3>
              </div>
              <button onClick={() => navigate('/your-5-today')} className="text-xs text-[#7C35DC] font-semibold hover:text-[#6B28C8]">See all 5</button>
            </div>
            {topLeads.length === 0 ? (
              <div className="p-6 text-center text-sm text-[#9B8AB0]">No priority leads today</div>
            ) : (
              <div className="divide-y divide-[#F0ECF9]">
                {topLeads.map((lead, i) => (
                  <button key={lead.id} onClick={() => navigate(`/leads/${lead.id}`)} className="w-full p-4 hover:bg-[#F9F5FF] transition-all text-left" data-testid={`top-lead-${i}`}>
                    <div className="flex items-start gap-3">
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center text-white text-xs font-bold shrink-0" style={{ background: 'var(--gradient-brand)' }}>{i + 1}</div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-semibold text-[#1A0A2E] truncate">{lead.first_name} {lead.last_name}</span>
                          <span className={tierBadge(lead.icp_tier)}>{lead.icp_tier}</span>
                        </div>
                        <p className="text-xs text-[#7C35DC] mt-1 font-medium truncate">{lead._reason}</p>
                        {lead.company_name && <p className="text-[11px] text-[#9B8AB0] mt-0.5">{lead.company_name}</p>}
                      </div>
                      <span className="text-xs font-mono font-bold text-[#7C35DC] shrink-0">{lead.icp_score}</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* ARIA Activity */}
          {ariaStats && (
            <div className="bg-white border border-[#E8E0F5] rounded-xl p-4" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="aria-summary-widget">
              <div className="flex items-center gap-2 mb-4">
                <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: 'var(--gradient-brand)' }}>
                  <Robot size={14} className="text-white" weight="fill" />
                </div>
                <h3 className="text-sm font-bold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>ARIA Activity</h3>
              </div>
              <div className="grid grid-cols-2 gap-3">
                {[
                  { label: 'Messages', value: ariaStats.total_aria_messages, color: '#7C35DC' },
                  { label: 'Replies', value: ariaStats.total_lead_replies, color: '#C044E0' },
                  { label: 'Booking %', value: `${ariaStats.booking_rate}%`, color: '#D97706' },
                  { label: 'Escalated', value: ariaStats.escalations, color: '#DC2626' },
                ].map(s => (
                  <div key={s.label} className="bg-[#FAFAFA] rounded-lg p-3 border border-[#F0ECF9]">
                    <div className="text-[10px] font-bold uppercase tracking-wider text-[#9B8AB0]">{s.label}</div>
                    <div className="text-lg font-extrabold mt-0.5" style={{ color: s.color, fontFamily: 'Plus Jakarta Sans' }}>{s.value}</div>
                  </div>
                ))}
              </div>
              <button onClick={() => navigate('/aria')} className="w-full mt-3 flex items-center justify-center gap-2 py-2 bg-[#F4F0FF] text-[#7C35DC] rounded-lg text-xs font-semibold border border-[#7C35DC]/10 hover:bg-[#7C35DC] hover:text-white transition-all">
                Open ARIA Dashboard <ArrowRight size={12} />
              </button>
            </div>
          )}
        </div>

        {/* Center: Charts */}
        <div className="space-y-4">
          {/* Channel Chart */}
          <div className="bg-white border border-[#E8E0F5] rounded-xl p-4" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="chart-channels">
            <h3 className="text-sm font-bold text-[#1A0A2E] mb-3" style={{ fontFamily: 'Plus Jakarta Sans' }}>Leads by Channel</h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={channelData} barSize={24}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F0ECF9" vertical={false} />
                <XAxis dataKey="name" tick={{ fill: '#9B8AB0', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#9B8AB0', fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(124,53,220,0.04)' }} />
                <Bar dataKey="value" fill="#7C35DC" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Funnel */}
          <div className="bg-white border border-[#E8E0F5] rounded-xl p-4" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="chart-funnel">
            <h3 className="text-sm font-bold text-[#1A0A2E] mb-3" style={{ fontFamily: 'Plus Jakarta Sans' }}>Conversion Funnel</h3>
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={funnelData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F0ECF9" vertical={false} />
                <XAxis dataKey="stage" tick={{ fill: '#9B8AB0', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#9B8AB0', fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={tooltipStyle} />
                <defs>
                  <linearGradient id="funnelGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#7C35DC" stopOpacity={0.2} />
                    <stop offset="100%" stopColor="#7C35DC" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <Area type="monotone" dataKey="value" stroke="#7C35DC" fill="url(#funnelGrad)" strokeWidth={2.5} dot={{ r: 4, fill: '#7C35DC', stroke: '#fff', strokeWidth: 2 }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Right: Donut Charts + Quick Actions */}
        <div className="space-y-4">
          {/* B2B vs B2C */}
          <div className="bg-white border border-[#E8E0F5] rounded-xl p-4" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="chart-lead-type">
            <h3 className="text-sm font-bold text-[#1A0A2E] mb-2" style={{ fontFamily: 'Plus Jakarta Sans' }}>Lead Split</h3>
            <div className="flex items-center gap-4">
              <ResponsiveContainer width={120} height={120}>
                <PieChart>
                  <Pie data={typeData} cx="50%" cy="50%" innerRadius={35} outerRadius={55} dataKey="value" paddingAngle={3}>
                    {typeData.map((e, i) => <Cell key={i} fill={['#7C35DC', '#16A34A'][i]} />)}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
              <div className="flex-1 space-y-2">
                {typeData.map((d, i) => (
                  <div key={d.name} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded" style={{ backgroundColor: ['#7C35DC', '#16A34A'][i] }}></div>
                      <span className="text-sm text-[#5A4A7A]">{d.name}</span>
                    </div>
                    <span className="text-sm font-bold text-[#1A0A2E]">{d.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* ICP Distribution */}
          <div className="bg-white border border-[#E8E0F5] rounded-xl p-4" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="chart-icp">
            <h3 className="text-sm font-bold text-[#1A0A2E] mb-2" style={{ fontFamily: 'Plus Jakarta Sans' }}>ICP Distribution</h3>
            <div className="flex items-center gap-4">
              <ResponsiveContainer width={120} height={120}>
                <PieChart>
                  <Pie data={icpData} cx="50%" cy="50%" innerRadius={35} outerRadius={55} dataKey="value" paddingAngle={3}>
                    {icpData.map((e, i) => <Cell key={i} fill={e.color} />)}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
              <div className="flex-1 space-y-2">
                {icpData.map(d => (
                  <div key={d.name} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded" style={{ backgroundColor: d.color }}></div>
                      <span className="text-sm text-[#5A4A7A]">{d.name}</span>
                    </div>
                    <span className="text-sm font-bold text-[#1A0A2E]">{d.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="bg-white border border-[#E8E0F5] rounded-xl p-4" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="quick-actions-widget">
            <h3 className="text-sm font-bold text-[#1A0A2E] mb-3" style={{ fontFamily: 'Plus Jakarta Sans' }}>Quick Actions</h3>
            <div className="space-y-2">
              {[
                { icon: Lightning, label: 'Your 5 Today', path: '/your-5-today', color: '#7C35DC' },
                { icon: Moon, label: `Sleeping Leads (${sleepingCount})`, path: '/sleeping-leads', color: '#D97706' },
                { icon: ChartLineUp, label: 'Full Analytics', path: '/analytics', color: '#16A34A' },
                { icon: Robot, label: 'ARIA Conversations', path: '/aria', color: '#C044E0' },
              ].map(action => (
                <button key={action.label} onClick={() => navigate(action.path)} className="w-full flex items-center gap-3 px-3 py-2.5 bg-[#FAFAFA] border border-[#F0ECF9] rounded-lg hover:bg-[#F9F5FF] hover:border-[#7C35DC]/20 transition-all text-left group">
                  <action.icon size={16} style={{ color: action.color }} weight="duotone" />
                  <span className="text-sm text-[#5A4A7A] group-hover:text-[#7C35DC] font-medium flex-1">{action.label}</span>
                  <ArrowRight size={12} className="text-[#9B8AB0] opacity-0 group-hover:opacity-100 transition-opacity" />
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Recent Leads Table */}
      <div className="bg-white border border-[#E8E0F5] rounded-xl" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="recent-leads-table">
        <div className="p-4 border-b border-[#E8E0F5] flex items-center justify-between">
          <h3 className="text-sm font-bold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Recent Leads</h3>
          <button onClick={() => navigate('/leads')} className="text-xs text-[#7C35DC] hover:text-[#6B28C8] font-semibold">View all</button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead>
              <tr className="bg-[#F9F5FF]">
                {['Name', 'Email', 'Type', 'Status', 'ICP', 'Channel'].map(h => (
                  <th key={h} className="px-4 py-2.5 text-[10px] font-bold uppercase tracking-[0.15em] text-[#5A4A7A]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {recentLeads.map(lead => (
                <tr key={lead.id} className="border-b border-[#F0ECF9] hover:bg-[#F9F5FF] cursor-pointer transition-colors" onClick={() => navigate(`/leads/${lead.id}`)} data-testid={`lead-row-${lead.id}`}>
                  <td className="px-4 py-3 font-semibold text-[#1A0A2E] text-sm">{lead.first_name} {lead.last_name}</td>
                  <td className="px-4 py-3 text-[#5A4A7A] font-mono text-xs">{lead.email}</td>
                  <td className="px-4 py-3"><span className={`px-1.5 py-0.5 text-[10px] font-bold rounded border ${lead.lead_type === 'B2B' ? 'bg-[#F4F0FF] text-[#7C35DC] border-[#7C35DC]/20' : 'bg-[#DCFCE7] text-[#16A34A] border-[#16A34A]/20'}`}>{lead.lead_type}</span></td>
                  <td className="px-4 py-3"><span className="px-1.5 py-0.5 text-[10px] font-bold uppercase rounded border bg-[#F4F0FF] text-[#7C35DC] border-[#7C35DC]/10">{lead.status}</span></td>
                  <td className="px-4 py-3"><span className={tierBadge(lead.icp_tier)}>{lead.icp_tier}</span></td>
                  <td className="px-4 py-3 text-xs text-[#5A4A7A]">{lead.source_channel?.replace('_', ' ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
