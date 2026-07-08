/**
 * AppLayout — the ONE client-dashboard layout.
 *
 * Single source of truth for /app/* (every workspace, regardless of tenant id).
 * Replaces:
 *   - components/Layout.js     (old legacy dark sidebar)
 *   - pietential/PtLayout.js   (old Pietential-branded layout)
 *
 * Visual: dark sidebar + purple accents (the look the founder approved).
 * Header: workspace switcher (Linear/Notion style, top-left), notifications,
 *         user menu.
 * Nav:    Mode-driven — Intelligence Feed shows for B2B + Hybrid, Lead Inbox
 *         shows for B2C + Hybrid. Everything else is always visible.
 *
 * Workspace switching is purely client-side: pick a tenant → write it to
 * localStorage.active_tenant → broadcast `aria:tenant-changed` → child pages
 * react via the WorkspaceContext / their own refetch hooks.
 */
import { useEffect, useState } from 'react';
import { NavLink, Outlet, useNavigate, useLocation, Link } from 'react-router-dom';
import {
  House, Brain, ChatCircle, Target, GraduationCap, Lightning,
  Plug, ChartLineUp, GearSix, SignOut, List, X, MagnifyingGlass,
  CaretDown, Buildings, CalendarBlank, Robot, Sun, Moon, MapTrifold, CheckCircle,
  Sparkle, ArrowsClockwise,
} from '@phosphor-icons/react';
import { toast } from 'sonner';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import NotificationsBell from './NotificationsBell';
import AriaAvatar from './AriaAvatar';
import AriaToastWatcher from './AriaToastWatcher';
import AriaTourModal from './AriaTourModal';
import AiSummaryDrawer from './AiSummaryDrawer';
import AriaCompanionDrawer from './AriaCompanionDrawer';
import api from '../config/api';

// ── Nav definition ──────────────────────────────────────────────────────
// iter141 — Reordered per UX spec V6:
//   Command Center → Instinct → Automation → Conversations → ICPs →
//   Train ARIA → Integrations → Reports → Settings
// Approvals is rendered SEPARATELY (V11) — only shown when pending > 0.
const NAV_PRIMARY = [
  { to: '/app',                label: 'Command Center', icon: House },
  { to: '/app/sales-view',     label: 'Sales View',     icon: ChartLineUp,  modes: ['b2b', 'hybrid'] },
  { to: '/app/instinct',       label: 'Instinct Feed',  icon: Brain,        modes: ['b2b', 'hybrid'] },
  { to: '/app/automation',     label: 'Automation',     icon: Lightning,    modes: ['b2c', 'hybrid'] },
  { to: '/app/conversations',  label: 'Conversations',  icon: ChatCircle },
  { to: '/app/icps',           label: 'ICPs',           icon: Target },
  { to: '/app/train-aria',     label: 'Train ARIA',     icon: GraduationCap },
  { to: '/app/integrations',   label: 'Integrations',   icon: Plug },
  { to: '/app/reports',        label: 'Reports',        icon: ChartLineUp },
  { to: '/app/settings',       label: 'Settings',       icon: GearSix },
];

// Approvals — V11: only render in sidebar when pending count > 0. Always reachable
// via the bell, but the sidebar entry stays hidden when there's nothing to do.
const NAV_APPROVALS = { to: '/app/approvals', label: 'Approvals', icon: CheckCircle, badge: 'approvals' };

const NAV_ADVANCED = [
  { to: '/app/touchpoints',     label: '32-Touchpoint Journey', icon: MapTrifold },
  { to: '/app/call-booking',    label: 'Call Booking',          icon: CalendarBlank },
  { to: '/app/voice-training',  label: 'Voice Training',        icon: Sparkle },
  { to: '/app/ai-setup',        label: 'AI Setup Assistant',    icon: Robot },
];


// ── ThemeToggle ─────────────────────────────────────────────────────────
// Segmented Light/Dark pill in the topbar — both options always visible.
// Persists choice via ThemeContext.
const ThemeToggle = () => {
  const { theme, setTheme, toggle } = useTheme();
  const isDark = theme === 'dark';
  // Some ThemeContext exports `setTheme` directly; if not, fall back to toggle.
  const goTo = (next) => {
    if (typeof setTheme === 'function') {
      setTheme(next);
    } else if (next !== theme) {
      toggle();
    }
  };
  const base = "inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-bold uppercase tracking-wider transition-colors";
  return (
    <div
      role="group"
      aria-label="Theme switcher"
      data-testid="theme-toggle"
      className="inline-flex items-center p-0.5 rounded-full border"
      style={{
        borderColor: 'var(--theme-border-strong)',
        background: 'var(--theme-surface)',
        fontFamily: 'Plus Jakarta Sans',
      }}
    >
      <button
        type="button"
        onClick={() => goTo('light')}
        data-testid="theme-toggle-light"
        aria-pressed={!isDark}
        title="Switch to light mode"
        className={base}
        style={{
          background: !isDark ? 'var(--theme-purple, #7C35DC)' : 'transparent',
          color: !isDark ? '#fff' : 'var(--theme-text-muted)',
        }}
      >
        <Sun size={12} weight={!isDark ? 'fill' : 'duotone'} />
        Light
      </button>
      <button
        type="button"
        onClick={() => goTo('dark')}
        data-testid="theme-toggle-dark"
        aria-pressed={isDark}
        title="Switch to dark mode"
        className={base}
        style={{
          background: isDark ? 'var(--theme-purple, #7C35DC)' : 'transparent',
          color: isDark ? '#fff' : 'var(--theme-text-muted)',
        }}
      >
        <Moon size={12} weight={isDark ? 'fill' : 'duotone'} />
        Dark
      </button>
    </div>
  );
};


// ── WorkspaceSwitcher ───────────────────────────────────────────────────
// Lives in the top header. Lists every workspace the current user belongs
// to. Picking one updates localStorage.active_tenant + dispatches a window
// event so child pages can refetch. NEVER hardcodes a tenant id.
const WorkspaceSwitcher = ({ onSwitch, user }) => {
  const [open, setOpen] = useState(false);
  const [tenants, setTenants] = useState([]);
  const [resetting, setResetting] = useState(false);
  const [active, setActiveLocal] = useState(() => {
    try { return JSON.parse(localStorage.getItem('active_tenant') || 'null'); }
    catch { return null; }
  });

  useEffect(() => {
    let alive = true;
    api.get('/api/tenants/me').then((r) => {
      if (!alive) return;
      const list = r.data?.tenants || [];
      setTenants(list);
      if (!active && list[0]) {
        setActiveLocal(list[0]);
        localStorage.setItem('active_tenant', JSON.stringify(list[0]));
      }
    }).catch(() => {});
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const onClose = () => setOpen(false);
    window.addEventListener('click', onClose);
    return () => window.removeEventListener('click', onClose);
  }, []);

  const pick = (t) => {
    setOpen(false);
    if (!t || t.id === active?.id) return;
    setActiveLocal(t);
    localStorage.setItem('active_tenant', JSON.stringify(t));
    window.dispatchEvent(new CustomEvent('aria:tenant-changed', { detail: t }));
    onSwitch?.(t);
  };

  // iter149 — Reset Demo seeds. Visible only when active workspace is the
  // demo tenant AND caller is master_admin. One click → POST /api/demo/reset
  // → toast result. Useful between back-to-back live demos.
  const isDemoTenant = active?.id === 'ten_demo';
  const canResetDemo = isDemoTenant && user?.role === 'master_admin';
  const handleResetDemo = async () => {
    if (resetting) return;
    if (!window.confirm('Reset the Demo workspace?\n\nThis will wipe all walkthrough annotations and re-seed:\n  • 6 demo leads (3 B2B Instinct + 3 B2C Automation)\n  • 3 insight cards\n  • 10 conversation messages\n\nFresh timestamps anchored to now.')) return;
    setResetting(true);
    try {
      const r = await api.post('/api/demo/reset');
      const s = r.data?.reseeded || {};
      toast.success(`Demo reset · ${(s.b2b_leads || 0) + (s.b2c_leads || 0)} leads · ${s.insight_cards || 0} cards · ${s.messages || 0} messages`);
      // Broadcast so all child pages refetch (insight feed, lead inbox, etc.)
      window.dispatchEvent(new CustomEvent('aria:tenant-changed', { detail: active }));
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Demo reset failed');
    } finally {
      setResetting(false);
      setOpen(false);
    }
  };

  return (
    <div className="relative" onClick={(e) => e.stopPropagation()} data-testid="workspace-switcher">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg border transition-colors"
        style={{
          borderColor: 'var(--theme-border-strong)',
          background: 'var(--theme-surface2)',
          color: 'var(--theme-text)',
        }}
        data-testid="workspace-switcher-trigger"
      >
        <Buildings size={16} weight="duotone" className="text-[#7C35DC]" />
        <span className="text-sm font-semibold max-w-[180px] truncate" style={{ color: 'var(--theme-text)' }}>
          {active?.name || 'Choose workspace'}
        </span>
        <CaretDown size={12} style={{ color: 'var(--theme-text-muted)' }} />
      </button>
      {open && (
        <div
          className="absolute left-0 mt-1.5 w-72 rounded-xl shadow-xl z-50 overflow-hidden border"
          style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border-strong)' }}
          data-testid="workspace-switcher-menu"
        >
          <div className="px-3 py-2 text-[10px] font-bold uppercase tracking-[0.16em] border-b" style={{ color: 'var(--theme-text-muted)', borderColor: 'var(--theme-border)' }}>
            Switch workspace
          </div>
          {tenants.length === 0 && (
            <div className="px-3 py-3 text-xs" style={{ color: 'var(--theme-text-muted)' }}>No workspaces yet.</div>
          )}
          {tenants.map((t) => (
            <button
              key={t.id}
              onClick={() => pick(t)}
              data-testid={`workspace-switcher-option-${t.id}`}
              className="w-full flex items-center justify-between gap-2 px-3 py-2 text-sm text-left transition-colors hover:bg-[var(--theme-surface2)]"
              style={active?.id === t.id ? { background: 'var(--theme-purple-dim)' } : {}}
            >
              <div className="min-w-0">
                <div className="font-semibold truncate" style={{ color: 'var(--theme-text)' }}>{t.name}</div>
                <div className="text-[10px] uppercase tracking-[0.14em] mt-0.5" style={{ color: 'var(--theme-text-muted)' }}>
                  {t.mode ? `${t.mode}` : 'workspace'}{t.role ? ` · ${t.role}` : ''}
                </div>
              </div>
              {active?.id === t.id && (
                <span className="text-[10px] font-bold" style={{ color: 'var(--theme-purple-light)' }}>ACTIVE</span>
              )}
            </button>
          ))}
          {canResetDemo && (
            <div className="border-t" style={{ borderColor: 'var(--theme-border)' }}>
              <button
                onClick={handleResetDemo}
                disabled={resetting}
                data-testid="workspace-switcher-reset-demo"
                className="w-full flex items-center gap-2 px-3 py-2.5 text-xs font-semibold text-left transition-colors hover:bg-[var(--theme-surface2)] disabled:opacity-50"
                style={{ color: 'var(--theme-purple-light)' }}
              >
                <ArrowsClockwise size={14} weight="bold" className={resetting ? 'animate-spin' : ''} />
                {resetting ? 'Resetting demo…' : 'Reset demo data'}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};


// ── Sidebar user block ──────────────────────────────────────────────────
const sidebarInitials = (name = '', email = '') => {
  const s = (name || email || '?').trim();
  const parts = s.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return s.slice(0, 2).toUpperCase();
};

const SidebarUser = ({ user, onLogout }) => (
  <div className="p-4 border-t border-[var(--sidebar-divider)]">
    <div className="flex items-center gap-3 mb-3">
      <span
        className="w-9 h-9 rounded-full flex items-center justify-center text-white font-extrabold text-xs border border-white/15"
        style={{ background: 'var(--gradient-brand)', fontFamily: 'Plus Jakarta Sans' }}
      >
        {sidebarInitials(user?.full_name, user?.email)}
      </span>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold text-white truncate" style={{ fontFamily: 'Plus Jakarta Sans' }}>
          {user?.full_name || user?.email}
        </div>
        <div className="text-xs text-[var(--sidebar-text-muted)] truncate">{user?.role}</div>
      </div>
    </div>
    <button
      onClick={onLogout}
      data-testid="logout-button"
      className="w-full flex items-center justify-center gap-2 px-3 py-2 border border-white/10 text-[var(--sidebar-text)] rounded-lg hover:bg-white/5 hover:text-white transition-all text-sm"
      style={{ fontFamily: 'Plus Jakarta Sans' }}
    >
      <SignOut size={16} /> Sign Out
    </button>
  </div>
);


// ── SidebarLeadStrip ────────────────────────────────────────────────────
// Live tenant-aware lead count strip rendered directly below the ARIA
// brand header. Click navigates to /app/leads. Stage chips: Qualified,
// Nurturing, New, Cold.
const SidebarLeadStrip = ({ leadCounts, onClick }) => {
  const total = leadCounts?.total || 0;
  const stages = leadCounts?.by_stage || {};
  const hasLeads = total > 0;
  return (
    <Link
      to="/app/leads"
      onClick={onClick}
      data-testid="sidebar-lead-strip"
      className="block px-3 py-3 border-b border-[var(--sidebar-divider)] transition-colors hover:bg-[var(--sidebar-hover-bg)]"
    >
      <div className="flex items-center gap-2">
        <span
          aria-hidden
          className="w-2 h-2 rounded-full shrink-0"
          style={{
            background: hasLeads ? '#16A34A' : '#64748B',
            boxShadow: hasLeads ? '0 0 8px rgba(22,163,74,0.6)' : 'none',
          }}
          data-testid={`sidebar-lead-strip-dot-${hasLeads ? 'active' : 'empty'}`}
        />
        <span className="text-xs font-extrabold text-white tracking-wide" style={{ fontFamily: 'Plus Jakarta Sans' }}>
          {total.toLocaleString()} Lead{total === 1 ? '' : 's'}
        </span>
      </div>
      <div className="mt-2 flex flex-wrap gap-1">
        {[
          { key: 'qualified', label: 'Qualified', dot: '#16A34A' },
          { key: 'nurturing', label: 'Nurturing', dot: '#F59E0B' },
          { key: 'new',       label: 'New',       dot: '#3B82F6' },
          { key: 'cold',      label: 'Cold',      dot: '#64748B' },
        ].map((s) => (
          <span
            key={s.key}
            data-testid={`sidebar-lead-chip-${s.key}`}
            className="inline-flex items-center gap-1 text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded"
            style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--sidebar-text)' }}
          >
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: s.dot }} />
            {s.label} <span className="text-white">{stages[s.key] || 0}</span>
          </span>
        ))}
      </div>
    </Link>
  );
};


// ── AppLayout ───────────────────────────────────────────────────────────
const AppLayout = ({ children }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [workspaceType, setWorkspaceType] = useState('hybrid');
  const [aiSummaryOpen, setAiSummaryOpen] = useState(false);

  // Refetch workspace mode whenever the active tenant changes.
  useEffect(() => {
    let cancelled = false;
    const fetchMode = async () => {
      try {
        const r = await api.get('/api/aria/workspace-type');
        if (!cancelled) setWorkspaceType(r.data?.workspace_type || 'hybrid');
      } catch {
        if (!cancelled) setWorkspaceType('hybrid');
      }
    };
    fetchMode();
    const onTenantChange = () => fetchMode();
    window.addEventListener('aria:tenant-changed', onTenantChange);
    return () => { cancelled = true; window.removeEventListener('aria:tenant-changed', onTenantChange); };
  }, []);

  // Mode guard — block direct-URL bypass of nav-hidden routes.
  useEffect(() => {
    const guarded = NAV_PRIMARY.find(n => n.modes && location.pathname === n.to);
    if (guarded && !guarded.modes.includes(workspaceType)) {
      navigate('/app', { replace: true });
    }
  }, [location.pathname, workspaceType, navigate]);

  const handleLogout = () => { logout(); navigate('/login'); };
  const handleWorkspaceSwitch = (t) => {
    // Soft reload to /app so any in-memory state belonging to the old
    // tenant is dropped cleanly. The X-Tenant-Id header on api calls
    // picks up the new tenant from localStorage on the next request.
    navigate('/app');
    // Best-effort: trigger a React refetch of any tenant-scoped queries.
    window.dispatchEvent(new Event('aria:tenant-changed-route'));
  };

  // iter119 — pending approval count for the sidebar badge (polled every 60s)
  const [approvalsCount, setApprovalsCount] = useState(0);

  // iter141 — V6/V11: Approvals nav item only injected when pending > 0.
  // Inserted right after Conversations (index 3 in the spec order).
  const visibleNav = (() => {
    const base = NAV_PRIMARY.filter((item) => !item.modes || item.modes.includes(workspaceType));
    if (approvalsCount > 0) {
      const idx = base.findIndex((n) => n.to === '/app/conversations');
      const insertAt = idx >= 0 ? idx + 1 : 4;
      return [...base.slice(0, insertAt), NAV_APPROVALS, ...base.slice(insertAt)];
    }
    return base;
  })();
  useEffect(() => {
    let cancelled = false;
    const fetchCount = async () => {
      try {
        const r = await api.get('/api/approvals/count');
        if (!cancelled) setApprovalsCount(r.data?.count || 0);
      } catch {
        if (!cancelled) setApprovalsCount(0);
      }
    };
    fetchCount();
    const id = setInterval(fetchCount, 60000);
    const onTenant = () => fetchCount();
    window.addEventListener('aria:tenant-changed', onTenant);
    return () => { cancelled = true; clearInterval(id); window.removeEventListener('aria:tenant-changed', onTenant); };
  }, []);

  // iter126 — sidebar lead count strip (polled every 30s, tenant-aware)
  const [leadCounts, setLeadCounts] = useState({ total: 0, by_stage: { qualified: 0, nurturing: 0, new: 0, cold: 0 } });
  useEffect(() => {
    let cancelled = false;
    const fetchLeads = async () => {
      try {
        const r = await api.get('/api/leads/counts');
        if (!cancelled) setLeadCounts(r.data || { total: 0, by_stage: {} });
      } catch {
        if (!cancelled) setLeadCounts({ total: 0, by_stage: { qualified: 0, nurturing: 0, new: 0, cold: 0 } });
      }
    };
    fetchLeads();
    const id = setInterval(fetchLeads, 30000);
    const onTenant = () => fetchLeads();
    window.addEventListener('aria:tenant-changed', onTenant);
    return () => { cancelled = true; clearInterval(id); window.removeEventListener('aria:tenant-changed', onTenant); };
  }, []);

  const Sidebar = ({ mobile = false }) => (
    <aside
      className={`${mobile ? 'w-72' : 'hidden md:flex w-60'} flex-col shrink-0`}
      style={{ background: 'linear-gradient(180deg, var(--sidebar-bg) 0%, var(--sidebar-bg-end) 100%)' }}
      data-testid={mobile ? 'app-sidebar-mobile' : 'app-sidebar'}
    >
      <div className="h-16 flex items-center justify-between px-4 border-b border-[var(--sidebar-divider)]">
        <div className="flex items-center gap-2.5 min-w-0">
          <AriaAvatar size={32} tone="default" />
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="font-extrabold text-base leading-none" style={{ fontFamily: 'var(--font-display)', letterSpacing: '0.02em', color: 'var(--sidebar-text)' }}>
                ARIA
              </span>
            </div>
            <div className="text-[9px] font-medium uppercase tracking-[0.2em] text-[var(--sidebar-text-muted)] mt-0.5">
              AI Sales PA · GenLeadAI
            </div>
          </div>
        </div>
        {mobile && (
          <button onClick={() => setMobileOpen(false)} className="p-1 text-[var(--sidebar-text-muted)] hover:opacity-70">
            <X size={20} />
          </button>
        )}
      </div>

      {/* iter126 — Lead count strip (live, polls every 30s, click to leads page) */}
      <SidebarLeadStrip leadCounts={leadCounts} onClick={() => { if (mobile) setMobileOpen(false); }} />

      <nav className="flex-1 px-3 py-4 overflow-y-auto">
        <div className="space-y-0.5">
          {visibleNav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/app'}
              onClick={() => mobile && setMobileOpen(false)}
              data-testid={`nav-${item.label.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')}`}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 ${
                  isActive
                    ? 'font-semibold'
                    : 'text-[var(--sidebar-text)] hover:bg-[var(--sidebar-hover-bg)]'
                }`
              }
              style={({ isActive }) =>
                isActive
                  ? { background: 'var(--sidebar-active-bg)', borderLeft: '3px solid var(--sidebar-active-border)', paddingLeft: 'calc(0.75rem - 3px)', fontFamily: 'var(--font-display)', color: 'var(--sidebar-active-border)' }
                  : { fontFamily: 'var(--font-display)' }
              }
            >
              <item.icon size={18} weight="duotone" />
              <span className="text-sm">{item.label}</span>
              {item.badge === 'approvals' && approvalsCount > 0 && (
                <span
                  data-testid="nav-approvals-badge"
                  className="ml-auto inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full text-[10px] font-extrabold text-white"
                  style={{ background: 'var(--theme-secondary)' }}
                >
                  {approvalsCount > 99 ? '99+' : approvalsCount}
                </span>
              )}
            </NavLink>
          ))}
        </div>

        {/* ADVANCED · ARIA TOOLS */}
        <div className="mt-5 mb-2 px-3 flex items-center gap-2">
          <div className="h-px flex-1" style={{ background: 'var(--sidebar-divider)' }} />
          <span className="text-[9px] font-extrabold uppercase tracking-[0.25em] text-[var(--sidebar-text-muted)]" style={{ fontFamily: 'var(--font-display)' }}>ADVANCED · ARIA TOOLS</span>
          <div className="h-px flex-1" style={{ background: 'var(--sidebar-divider)' }} />
        </div>
        <div className="space-y-0.5">
          {NAV_ADVANCED.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={() => mobile && setMobileOpen(false)}
              data-testid={`nav-${item.label.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')}`}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 ${
                  isActive
                    ? 'font-semibold'
                    : 'text-[var(--sidebar-text)] hover:bg-[var(--sidebar-hover-bg)]'
                }`
              }
              style={({ isActive }) =>
                isActive
                  ? { background: 'var(--sidebar-active-bg)', borderLeft: '3px solid var(--sidebar-active-border)', paddingLeft: 'calc(0.75rem - 3px)', fontFamily: 'var(--font-display)', color: 'var(--sidebar-active-border)' }
                  : { fontFamily: 'var(--font-display)' }
              }
            >
              <item.icon size={18} weight="duotone" />
              <span className="text-sm">{item.label}</span>
            </NavLink>
          ))}
        </div>

        {user?.role === 'master_admin' && (
          <>
            <div className="mt-5 mb-2 px-3 flex items-center gap-2">
              <div className="h-px flex-1" style={{ background: 'var(--sidebar-divider)' }} />
              <span className="text-[9px] font-extrabold uppercase tracking-[0.25em]" style={{ fontFamily: 'var(--font-display)', color: 'var(--theme-secondary)' }}>PLATFORM</span>
              <div className="h-px flex-1" style={{ background: 'var(--sidebar-divider)' }} />
            </div>
            <NavLink
              to="/admin"
              onClick={() => mobile && setMobileOpen(false)}
              data-testid="nav-master-admin"
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-[var(--sidebar-text)] hover:bg-[var(--sidebar-hover-bg)] transition-all"
              style={{ fontFamily: 'var(--font-display)' }}
            >
              <GearSix size={18} weight="duotone" />
              <span className="text-sm">Admin Panel</span>
            </NavLink>
          </>
        )}
      </nav>
      <SidebarUser user={user} onLogout={handleLogout} />
    </aside>
  );

  return (
    <div
      className="min-h-screen flex"
      style={{ background: 'var(--theme-bg)' }}
      data-theme-bg
    >
      <Sidebar />

      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setMobileOpen(false)} />
          <div className="absolute left-0 top-0 bottom-0 z-10 flex">
            <Sidebar mobile />
          </div>
        </div>
      )}

      <div className="flex-1 flex flex-col min-w-0">
        <header
          className="h-16 border-b flex items-center justify-between px-4 md:px-6 shrink-0"
          style={{ background: 'var(--theme-surface)', borderColor: 'var(--theme-border)' }}
          data-theme-surface
        >
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileOpen(true)}
              className="md:hidden p-1.5"
              style={{ color: 'var(--theme-text-muted)' }}
              aria-label="Open menu"
              data-testid="mobile-menu-btn"
            >
              <List size={22} />
            </button>
            <WorkspaceSwitcher onSwitch={handleWorkspaceSwitch} user={user} />
            <span
              className="hidden lg:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-[0.12em]"
              style={{ background: 'var(--theme-primary-dim)', color: 'var(--theme-primary)' }}
              data-testid="mode-chip"
            >
              {workspaceType}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <div className="relative hidden sm:block">
              <MagnifyingGlass size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--theme-text-muted)' }} />
              <input
                type="text"
                placeholder="Search…"
                className="w-56 pl-8 pr-3 py-1.5 rounded-lg focus:ring-2 text-sm border outline-none"
                style={{
                  background: 'var(--theme-surface2)',
                  borderColor: 'var(--theme-border-strong)',
                  color: 'var(--theme-text)',
                  fontFamily: 'var(--font-sans)',
                }}
                data-testid="global-search"
              />
            </div>
            <ThemeToggle />
            <button
              onClick={() => setAiSummaryOpen(true)}
              data-testid="topbar-ai-summary-btn"
              aria-label="Open ARIA's 7-day AI summary"
              title="ARIA's 7-day briefing"
              className="hidden md:inline-flex items-center gap-1.5 h-9 px-3 rounded-lg text-xs font-bold text-white transition-colors"
              style={{ background: 'var(--theme-primary)', fontFamily: 'var(--font-display)' }}
            >
              <Sparkle size={13} weight="fill" />
              AI Summary
            </button>
            <NotificationsBell />
          </div>
        </header>
        <main className="flex-1 overflow-auto">
          <div className="p-4 md:p-6">{children || <Outlet />}</div>
        </main>
      </div>

      <AriaToastWatcher />
      <AriaTourModal />
      <AiSummaryDrawer open={aiSummaryOpen} onClose={() => setAiSummaryOpen(false)} />
      <AriaCompanionDrawer />
    </div>
  );
};

export default AppLayout;
