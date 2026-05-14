import React, { useState, useEffect } from 'react';
import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { usePlan } from '../context/PlanContext';
import { Toaster } from 'sonner';
import { useTtvMilestoneWatcher } from '../hooks/useTtvMilestoneWatcher';
import {
  House, Tray, ChartBar, MegaphoneSimple, ChartLineUp, UsersThree,
  SignOut, MagnifyingGlass, Robot, Moon, List, Lightning, X,
  ClockCounterClockwise, ListChecks, Plug, CreditCard, Sparkle,
  GraduationCap, BookOpen, MapTrifold, FileText, ShieldCheck, ArrowClockwise, Brain,
  Stack, CalendarCheck, Wrench, AddressBook, ChatCircle,
} from '@phosphor-icons/react';
import AriaAvatar from './AriaAvatar';
import NotificationsBell from './NotificationsBell';
import AriaToastWatcher from './AriaToastWatcher';
import BetaFeedbackButton from './BetaFeedbackButton';
import TrialBanner from './TrialBanner';
import AriaModeChip from './AriaModeChip';
import AriaTourModal from './AriaTourModal';
import { useWorkspace, WORKSPACES } from '../context/WorkspaceContext';
import api from '../config/api';

const AriaWorkspaceSwitcher = () => {
  const { active, setActive } = useWorkspace();
  const navigate = useNavigate();
  const [tenants, setTenants] = useState([]);
  const [activeTenantId, setActiveTenantId] = useState(() => {
    try { return JSON.parse(localStorage.getItem('active_tenant') || 'null')?.id || ''; }
    catch { return ''; }
  });

  // Fetch all tenants the current user belongs to
  useEffect(() => {
    let alive = true;
    api.get('/api/tenants/me').then((r) => {
      if (!alive) return;
      const list = r.data?.tenants || [];
      setTenants(list);
      // If no active tenant stored yet, use the first one
      if (!activeTenantId && list[0]?.id) {
        setActiveTenantId(list[0].id);
        localStorage.setItem('active_tenant', JSON.stringify(list[0]));
      }
    }).catch(() => {});
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const switchTenant = (tenantId) => {
    const t = tenants.find((x) => x.id === tenantId);
    if (!t) return;
    setActiveTenantId(tenantId);
    localStorage.setItem('active_tenant', JSON.stringify(t));
    // Special routing: Pietential tenant uses the legacy /pt UI, others use legacy ARIA
    if (t.id === 'ten_pietential') {
      setActive(WORKSPACES.find((w) => w.slug === 'pietential'));
      window.location.replace('/pt');
    } else {
      setActive(WORKSPACES.find((w) => w.slug === 'aria_crm'));
      window.location.replace('/');
    }
  };

  // Multi-tenant users: show real tenant dropdown
  if (tenants.length > 1) {
    return (
      <div className="px-3 py-2 border-b border-[var(--sidebar-divider)]" data-testid="tenant-switcher">
        <div className="text-[8px] font-bold uppercase tracking-[0.22em] text-[var(--sidebar-text-muted)] mb-1">Workspace</div>
        <select
          value={activeTenantId}
          onChange={(e) => switchTenant(e.target.value)}
          data-testid="tenant-select"
          className="w-full text-xs font-semibold text-white bg-white/5 border border-white/10 rounded-md px-2 py-1.5 outline-none focus:ring-1 focus:ring-white/20"
        >
          {tenants.map((t) => (
            <option key={t.id} value={t.id} className="bg-[#1A0A2E]">
              {t.name}{t.role === 'owner' ? ' · Owner' : ''}
            </option>
          ))}
        </select>
      </div>
    );
  }

  // Single-tenant users: show static workspace name (no switcher needed)
  if (tenants.length === 1) {
    return (
      <div className="px-3 py-2 border-b border-[var(--sidebar-divider)]" data-testid="tenant-single">
        <div className="text-[8px] font-bold uppercase tracking-[0.22em] text-[var(--sidebar-text-muted)] mb-1">Workspace</div>
        <div className="text-xs font-semibold text-white truncate" title={tenants[0].name}>
          {tenants[0].name}
        </div>
      </div>
    );
  }

  // Loading or legacy fallback — keep the original static switcher
  const switchTo = (slug) => {
    const ws = WORKSPACES.find(w => w.slug === slug);
    if (!ws) return;
    setActive(ws);
    navigate(ws.home);
  };
  return (
    <div className="px-3 py-2 border-b border-[var(--sidebar-divider)]" data-testid="aria-workspace-switcher">
      <div className="text-[8px] font-bold uppercase tracking-[0.22em] text-[var(--sidebar-text-muted)] mb-1">Workspace</div>
      <select
        value={active.slug}
        onChange={(e) => switchTo(e.target.value)}
        data-testid="aria-workspace-select"
        className="w-full text-xs font-semibold text-white bg-white/5 border border-white/10 rounded-md px-2 py-1.5 outline-none focus:ring-1 focus:ring-white/20"
      >
        {WORKSPACES.map(w => (
          <option key={w.slug} value={w.slug} className="bg-[#1A0A2E]">{w.label}</option>
        ))}
      </select>
    </div>
  );
};

const Layout = ({ children }) => {
  const { user, logout } = useAuth();
  const { planName, planId, openUpgrade } = usePlan();
  const navigate = useNavigate();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(() => {
    try { const v = localStorage.getItem('aria_sidebar_open'); return v === null ? true : v === '1'; }
    catch { return true; }
  });
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const toggleSidebar = () => {
    setSidebarOpen(prev => {
      const next = !prev;
      try { localStorage.setItem('aria_sidebar_open', next ? '1' : '0'); } catch { /* swallow */ }
      return next;
    });
  };

  useTtvMilestoneWatcher(!!user);

  const handleLogout = () => { logout(); navigate('/login'); };

  // ── Founder-friendly 9-item navigation ─────────────────────────────────
  // Consolidated per Aria UX spec — legacy items remain accessible via direct URL
  // (Pipeline/Contacts open inside Lead Inbox tabs; AI Assistant → Conversations;
  //  Sales Engagement + Touchpoint Mapping → 32-Touchpoint Journey; Plan & Billing → Settings).
  const navItems = [
    { icon: House,         label: 'Command Center',       path: '/' },
    { icon: Tray,          label: 'Lead Inbox',           path: '/leads' },
    { icon: ChatCircle,    label: 'Conversations',        path: '/conversations' },
    { icon: MapTrifold,    label: '32-Touchpoint Journey',path: '/touchpoint-journey' },
    { icon: GraduationCap, label: 'Train Aria',           path: '/aria-agent/train' },
    { icon: Plug,          label: 'Integrations',         path: '/integrations' },
    { icon: CalendarCheck, label: 'Call Booking',         path: '/follow-ups' },
    { icon: ChartLineUp,   label: 'Reports',              path: '/reports' },
    { icon: UsersThree,    label: 'Settings',             path: '/settings' },
  ];

  // ── Advanced Aria surfaces (kept available but collapsed under one group) ──
  const ariaAgentItems = [
    { icon: FileText, label: 'Founder Briefs', path: '/aria-agent/briefs' },
    { icon: ShieldCheck, label: 'Human Handoff', path: '/aria-agent/handoff' },
    { icon: ArrowClockwise, label: 'Revival Engine', path: '/aria-agent/revival' },
    { icon: Stack, label: 'Sales Assets', path: '/aria-agent/assets' },
    { icon: Brain, label: 'ARIA Brain', path: '/aria-agent/brain' },
    { icon: Brain, label: 'ARIA Insights', path: '/aria-agent/insights' },
    { icon: BookOpen, label: 'Sales Playbooks', path: '/aria-agent/playbooks' },
    { icon: CalendarCheck, label: 'Weekly Recap', path: '/aria-agent/weekly-recap' },
    { icon: Wrench, label: 'Troubleshooting', path: '/troubleshooting' },
    { icon: GraduationCap, label: 'Tutorials', path: '/tutorials' },
  ];

  const NavContent = ({ mobile = false }) => (
    <>
      <nav className="flex-1 px-3 py-4 overflow-y-auto">
        <div className="space-y-0.5">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              onClick={() => mobile && setMobileMenuOpen(false)}
              data-testid={`nav-${item.label.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')}`}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 ${
                  isActive
                    ? 'text-white font-semibold'
                    : 'text-[var(--sidebar-text)] hover:bg-[var(--sidebar-hover-bg)] hover:text-white'
                }`
              }
              style={({ isActive }) => isActive ? { background: 'var(--sidebar-active-bg)', borderLeft: '3px solid var(--sidebar-active-border)', paddingLeft: 'calc(0.75rem - 3px)', fontFamily: 'Plus Jakarta Sans' } : { fontFamily: 'Plus Jakarta Sans' }}
            >
              <item.icon size={18} weight="duotone" />
              <span className="text-sm">{item.label}</span>
            </NavLink>
          ))}
        </div>

        <div className="mt-5 mb-2 px-3 flex items-center gap-2" data-testid="nav-section-aria-agent">
          <div className="h-px flex-1 bg-white/10" />
          <span className="text-[9px] font-extrabold uppercase tracking-[0.25em] text-[#C9B6FF]/70" style={{ fontFamily: 'Plus Jakarta Sans' }}>ADVANCED · ARIA TOOLS</span>
          <div className="h-px flex-1 bg-white/10" />
        </div>

        <div className="space-y-0.5">
          {ariaAgentItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              onClick={() => mobile && setMobileMenuOpen(false)}
              data-testid={`nav-${item.label.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')}`}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 ${
                  isActive
                    ? 'text-white font-semibold'
                    : 'text-[var(--sidebar-text)] hover:bg-[var(--sidebar-hover-bg)] hover:text-white'
                }`
              }
              style={({ isActive }) => isActive ? { background: 'var(--sidebar-active-bg)', borderLeft: '3px solid var(--sidebar-active-border)', paddingLeft: 'calc(0.75rem - 3px)', fontFamily: 'Plus Jakarta Sans' } : { fontFamily: 'Plus Jakarta Sans' }}
            >
              <item.icon size={18} weight="duotone" />
              <span className="text-sm">{item.label}</span>
            </NavLink>
          ))}
        </div>

        {(user?.role || '').toLowerCase() === 'admin' && (
          <>
            <div className="mt-5 mb-2 px-3 flex items-center gap-2" data-testid="nav-section-master-admin">
              <div className="h-px flex-1 bg-white/10" />
              <span className="text-[9px] font-extrabold uppercase tracking-[0.25em] text-[#E2B96F]/80" style={{ fontFamily: 'Plus Jakarta Sans' }}>PLATFORM</span>
              <div className="h-px flex-1 bg-white/10" />
            </div>
            <div className="space-y-0.5">
              <NavLink
                to="/master-admin"
                onClick={() => mobile && setMobileMenuOpen(false)}
                data-testid="nav-master-admin"
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 ${
                    isActive
                      ? 'text-white font-semibold'
                      : 'text-[var(--sidebar-text)] hover:bg-[var(--sidebar-hover-bg)] hover:text-white'
                  }`
                }
                style={({ isActive }) => isActive ? { background: 'var(--sidebar-active-bg)', borderLeft: '3px solid var(--sidebar-active-border)', paddingLeft: 'calc(0.75rem - 3px)', fontFamily: 'Plus Jakarta Sans' } : { fontFamily: 'Plus Jakarta Sans' }}
              >
                <ShieldCheck size={18} weight="duotone" />
                <span className="text-sm">Master Admin</span>
              </NavLink>
              <NavLink
                to="/admin/failed-messages"
                onClick={() => mobile && setMobileMenuOpen(false)}
                data-testid="nav-failed-messages"
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 ${
                    isActive
                      ? 'text-white font-semibold'
                      : 'text-[var(--sidebar-text)] hover:bg-[var(--sidebar-hover-bg)] hover:text-white'
                  }`
                }
                style={({ isActive }) => isActive ? { background: 'var(--sidebar-active-bg)', borderLeft: '3px solid var(--sidebar-active-border)', paddingLeft: 'calc(0.75rem - 3px)', fontFamily: 'Plus Jakarta Sans' } : { fontFamily: 'Plus Jakarta Sans' }}
              >
                <Wrench size={18} weight="duotone" />
                <span className="text-sm">Failed Messages</span>
              </NavLink>
            </div>
          </>
        )}
      </nav>
      <div className="p-4 border-t border-[var(--sidebar-divider)]">
        {/* Plan badge */}
        <button
          onClick={() => planId === 'custom' ? navigate('/billing') : openUpgrade(null, planId === 'starter' ? 'growth' : planId === 'growth' ? 'pro' : 'custom')}
          className="w-full flex items-center justify-between gap-2 mb-3 px-3 py-2 rounded-lg border border-white/10 hover:bg-white/5 transition-all text-left"
          style={{ background: 'rgba(192,68,224,0.08)' }}
          data-testid="plan-badge"
          title="Click to manage plan"
        >
          <div className="flex items-center gap-2 min-w-0">
            <Sparkle size={14} className="text-[#C044E0]" weight="fill" />
            <div className="min-w-0">
              <div className="text-[10px] font-bold uppercase tracking-wider text-[var(--sidebar-text-muted)]">Current plan</div>
              <div className="text-xs font-bold text-white truncate" style={{ fontFamily: 'Plus Jakarta Sans' }}>{planName}</div>
            </div>
          </div>
          {planId !== 'custom' && (
            <span className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded text-white flex-shrink-0" style={{ background: 'var(--gradient-brand)' }}>Upgrade</span>
          )}
        </button>
        <div className="flex items-center gap-3">
          <img src={user?.avatar_url || 'https://ui-avatars.com/api/?name=User&background=7C35DC&color=fff'} alt="User" className="w-9 h-9 rounded-full" />
          <div className="flex-1 min-w-0">
            <div className="text-sm font-semibold text-white truncate" style={{ fontFamily: 'Plus Jakarta Sans' }}>{user?.full_name}</div>
            <div className="text-xs text-[var(--sidebar-text-muted)] truncate">{user?.role}</div>
          </div>
        </div>
        <button onClick={handleLogout} data-testid="logout-button"
          className="mt-3 w-full flex items-center justify-center gap-2 px-3 py-2 border border-white/10 text-[var(--sidebar-text)] rounded-lg hover:bg-white/5 hover:text-white transition-all text-sm"
          style={{ fontFamily: 'Plus Jakarta Sans' }}>
          <SignOut size={16} /> Sign Out
        </button>
        <div className="mt-2">
          <BetaFeedbackButton variant="sidebar" />
        </div>
      </div>
    </>
  );

  return (
    <div className="min-h-screen bg-[#FAFAFA] flex">
      {/* Desktop Sidebar — Dark Premium */}
      <aside className={`hidden md:flex ${sidebarOpen ? 'w-64' : 'w-16'} flex-col transition-all duration-300 shrink-0`} style={{ background: 'linear-gradient(180deg, var(--sidebar-bg) 0%, var(--sidebar-bg-end) 100%)' }} data-testid="sidebar">
        <div className="h-16 flex items-center justify-between px-4 border-b border-[var(--sidebar-divider)]">
          <div className="flex items-center gap-2.5 min-w-0">
            <AriaAvatar size={32} tone="default" />
            {sidebarOpen && (
              <div className="min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="text-white font-extrabold text-base leading-none" style={{ fontFamily: 'Plus Jakarta Sans', letterSpacing: '0.02em' }}>ARIA</span>
                  <span data-testid="beta-badge-sidebar" className="px-1.5 py-[1px] rounded-[4px] text-[8px] font-bold uppercase tracking-[0.18em] text-[#FDE68A] border border-[#F59E0B]/40" style={{ background: 'rgba(245,158,11,0.12)' }}>Beta</span>
                </div>
                <div className="text-[9px] font-medium uppercase tracking-[0.2em] text-[var(--sidebar-text-muted)] mt-0.5">AI Sales PA · GenLeadAI</div>
              </div>
            )}
          </div>
          <button onClick={toggleSidebar} className="p-1 text-[var(--sidebar-text-muted)] hover:text-white transition-colors" title={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'} data-testid="sidebar-toggle-inner"><List size={16} /></button>
        </div>
        {sidebarOpen && <AriaWorkspaceSwitcher />}
        {sidebarOpen ? <NavContent /> : (
          <nav className="flex-1 px-2 py-4">
            <div className="space-y-1">
              {navItems.map((item) => (
                <NavLink key={item.path} to={item.path} end={item.path === '/'} title={item.label}
                  className={({ isActive }) => `flex items-center justify-center p-2.5 rounded-lg transition-all ${isActive ? 'text-white' : 'text-[var(--sidebar-text-muted)] hover:bg-white/5 hover:text-white'}`}
                  style={({ isActive }) => isActive ? { background: 'var(--sidebar-active-bg)' } : {}}>
                  <item.icon size={18} weight="duotone" />
                </NavLink>
              ))}
            </div>
            <div className="my-3 mx-2 h-px bg-white/10" />
            <div className="space-y-1">
              {ariaAgentItems.map((item) => (
                <NavLink key={item.path} to={item.path} title={item.label}
                  className={({ isActive }) => `flex items-center justify-center p-2.5 rounded-lg transition-all ${isActive ? 'text-white' : 'text-[var(--sidebar-text-muted)] hover:bg-white/5 hover:text-white'}`}
                  style={({ isActive }) => isActive ? { background: 'var(--sidebar-active-bg)' } : {}}>
                  <item.icon size={18} weight="duotone" />
                </NavLink>
              ))}
            </div>
          </nav>
        )}
      </aside>

      {/* Mobile Overlay */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setMobileMenuOpen(false)} />
          <aside className="absolute left-0 top-0 bottom-0 w-72 flex flex-col z-10" style={{ background: 'linear-gradient(180deg, var(--sidebar-bg) 0%, var(--sidebar-bg-end) 100%)' }}>
            <div className="h-16 flex items-center justify-between px-4 border-b border-[var(--sidebar-divider)]">
              <div className="flex items-center gap-2.5">
                <AriaAvatar size={32} tone="default" />
                <div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-white font-extrabold text-base leading-none" style={{ fontFamily: 'Plus Jakarta Sans' }}>ARIA</span>
                    <span data-testid="beta-badge-mobile" className="px-1.5 py-[1px] rounded-[4px] text-[8px] font-bold uppercase tracking-[0.18em] text-[#FDE68A] border border-[#F59E0B]/40" style={{ background: 'rgba(245,158,11,0.12)' }}>Beta</span>
                  </div>
                  <div className="text-[9px] font-medium uppercase tracking-[0.2em] text-[var(--sidebar-text-muted)] mt-0.5">AI Sales PA · GenLeadAI</div>
                </div>
              </div>
              <button onClick={() => setMobileMenuOpen(false)} className="p-1 text-[var(--sidebar-text-muted)] hover:text-white"><X size={20} /></button>
            </div>
            <NavContent mobile />
          </aside>
        </div>
      )}

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-16 bg-white border-b border-[#E8E0F5] flex items-center justify-between px-4 md:px-6 shrink-0">
          <div className="flex items-center gap-3 flex-1">
            <button onClick={() => setMobileMenuOpen(true)} className="md:hidden p-1.5 text-[#5A4A7A] hover:text-[#7C35DC]" aria-label="Open menu" data-testid="mobile-menu-btn"><List size={22} /></button>
            <button onClick={toggleSidebar} className="hidden md:flex items-center justify-center p-2 text-[#5A4A7A] hover:text-[#7C35DC] hover:bg-[#F4F0FF] rounded-lg transition-all" title={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'} aria-label={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'} data-testid="sidebar-toggle">
              <List size={18} weight="bold" />
            </button>
            <div className="relative flex-1 max-w-md hidden sm:block">
              <MagnifyingGlass size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9B8AB0]" />
              <input type="text" placeholder="Search leads, follow-ups, campaigns…" className="w-full bg-[#FAFAFA] border border-[#E8E0F5] text-[#1A0A2E] pl-9 pr-4 py-2 rounded-lg focus:border-[#7C35DC] focus:ring-2 focus:ring-[rgba(124,53,220,0.12)] transition-all text-sm" style={{ fontFamily: 'Inter' }} data-testid="global-search" />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <AriaModeChip />
            <button onClick={() => navigate('/leads')} className="hidden md:flex items-center gap-1.5 px-3 py-2 text-[#7C35DC] border border-[#7C35DC]/30 hover:bg-[#F4F0FF] rounded-lg transition-all text-xs font-bold" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid="topbar-ai-summary">
              <Sparkle size={14} weight="fill" /> AI Summary
            </button>
            <button onClick={() => navigate('/leads')} className="hidden md:flex items-center gap-1.5 btn-gradient px-4 py-2 rounded-lg text-xs font-bold" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid="topbar-add-lead">
              + Add Lead
            </button>
            <NotificationsBell />
          </div>
        </header>
        <main className="flex-1 overflow-auto"><TrialBanner /><div className="p-4 md:p-6">{children}</div></main>
      </div>
      <AriaToastWatcher />
      <AriaTourModal />
    </div>
  );
};

export default Layout;
