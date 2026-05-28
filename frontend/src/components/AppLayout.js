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
import { NavLink, Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  House, Brain, ChatCircle, Target, GraduationCap, Lightning,
  Plug, ChartLineUp, GearSix, SignOut, List, X, MagnifyingGlass,
  CaretDown, Buildings, CalendarBlank, Robot,
} from '@phosphor-icons/react';
import { useAuth } from '../context/AuthContext';
import NotificationsBell from './NotificationsBell';
import AriaAvatar from './AriaAvatar';
import AriaToastWatcher from './AriaToastWatcher';
import AriaTourModal from './AriaTourModal';
import api from '../config/api';

// ── Nav definition ──────────────────────────────────────────────────────
// `modes` (optional): when present, the item is only shown when the active
// workspace's mode is in the list. Same rule for every workspace.
const NAV_PRIMARY = [
  { to: '/app',                label: 'Command Center', icon: House },
  { to: '/app/instinct',       label: 'Instinct Feed',  icon: Brain,        modes: ['b2b', 'hybrid'] },
  { to: '/app/automation',     label: 'Automation',     icon: Lightning,    modes: ['b2c', 'hybrid'] },
  { to: '/app/conversations',  label: 'Conversations',  icon: ChatCircle },
  { to: '/app/icps',           label: 'ICPs',           icon: Target },
  { to: '/app/train-aria',     label: 'Train ARIA',     icon: GraduationCap },
  { to: '/app/integrations',   label: 'Integrations',   icon: Plug },
  { to: '/app/reports',        label: 'Reports',        icon: ChartLineUp },
  { to: '/app/settings',       label: 'Settings',       icon: GearSix },
];

const NAV_ADVANCED = [
  { to: '/app/call-booking',   label: 'Call Booking',       icon: CalendarBlank },
  { to: '/app/ai-setup',       label: 'AI Setup Assistant', icon: Robot },
];


// ── WorkspaceSwitcher ───────────────────────────────────────────────────
// Lives in the top header. Lists every workspace the current user belongs
// to. Picking one updates localStorage.active_tenant + dispatches a window
// event so child pages can refetch. NEVER hardcodes a tenant id.
const WorkspaceSwitcher = ({ onSwitch }) => {
  const [open, setOpen] = useState(false);
  const [tenants, setTenants] = useState([]);
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

  return (
    <div className="relative" onClick={(e) => e.stopPropagation()} data-testid="workspace-switcher">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-[#E8E0F5] hover:bg-[#F4F0FF] transition-colors"
        data-testid="workspace-switcher-trigger"
      >
        <Buildings size={16} weight="duotone" className="text-[#7C35DC]" />
        <span className="text-sm font-semibold text-[#1A0A2E] max-w-[180px] truncate">
          {active?.name || 'Choose workspace'}
        </span>
        <CaretDown size={12} className="text-[#5A4A7A]" />
      </button>
      {open && (
        <div
          className="absolute left-0 mt-1.5 w-72 bg-white border border-[#E8E0F5] rounded-xl shadow-xl z-50 overflow-hidden"
          data-testid="workspace-switcher-menu"
        >
          <div className="px-3 py-2 text-[10px] font-bold uppercase tracking-[0.16em] text-[#9B8AB0] border-b border-[#F0ECF9]">
            Switch workspace
          </div>
          {tenants.length === 0 && (
            <div className="px-3 py-3 text-xs text-[#9B8AB0]">No workspaces yet.</div>
          )}
          {tenants.map((t) => (
            <button
              key={t.id}
              onClick={() => pick(t)}
              data-testid={`workspace-switcher-option-${t.id}`}
              className={`w-full flex items-center justify-between gap-2 px-3 py-2 text-sm hover:bg-[#FAF7FF] text-left ${active?.id === t.id ? 'bg-[#F4F0FF]' : ''}`}
            >
              <div className="min-w-0">
                <div className="font-semibold text-[#1A0A2E] truncate">{t.name}</div>
                <div className="text-[10px] uppercase tracking-[0.14em] text-[#9B8AB0] mt-0.5">
                  {t.mode ? `${t.mode}` : 'workspace'}{t.role ? ` · ${t.role}` : ''}
                </div>
              </div>
              {active?.id === t.id && (
                <span className="text-[10px] font-bold text-[#7C35DC]">ACTIVE</span>
              )}
            </button>
          ))}
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


// ── AppLayout ───────────────────────────────────────────────────────────
const AppLayout = ({ children }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [workspaceType, setWorkspaceType] = useState('hybrid');

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

  const visibleNav = NAV_PRIMARY.filter((item) => !item.modes || item.modes.includes(workspaceType));

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
              <span className="text-white font-extrabold text-base leading-none" style={{ fontFamily: 'Plus Jakarta Sans', letterSpacing: '0.02em' }}>
                ARIA
              </span>
            </div>
            <div className="text-[9px] font-medium uppercase tracking-[0.2em] text-[var(--sidebar-text-muted)] mt-0.5">
              AI Sales PA · GenLeadAI
            </div>
          </div>
        </div>
        {mobile && (
          <button onClick={() => setMobileOpen(false)} className="p-1 text-[var(--sidebar-text-muted)] hover:text-white">
            <X size={20} />
          </button>
        )}
      </div>

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
                    ? 'text-white font-semibold'
                    : 'text-[var(--sidebar-text)] hover:bg-[var(--sidebar-hover-bg)] hover:text-white'
                }`
              }
              style={({ isActive }) =>
                isActive
                  ? { background: 'var(--sidebar-active-bg)', borderLeft: '3px solid var(--sidebar-active-border)', paddingLeft: 'calc(0.75rem - 3px)', fontFamily: 'Plus Jakarta Sans' }
                  : { fontFamily: 'Plus Jakarta Sans' }
              }
            >
              <item.icon size={18} weight="duotone" />
              <span className="text-sm">{item.label}</span>
            </NavLink>
          ))}
        </div>

        {/* ADVANCED · ARIA TOOLS */}
        <div className="mt-5 mb-2 px-3 flex items-center gap-2">
          <div className="h-px flex-1 bg-white/10" />
          <span className="text-[9px] font-extrabold uppercase tracking-[0.25em] text-[var(--sidebar-text-muted)]" style={{ fontFamily: 'Plus Jakarta Sans' }}>ADVANCED · ARIA TOOLS</span>
          <div className="h-px flex-1 bg-white/10" />
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
                    ? 'text-white font-semibold'
                    : 'text-[var(--sidebar-text)] hover:bg-[var(--sidebar-hover-bg)] hover:text-white'
                }`
              }
              style={({ isActive }) =>
                isActive
                  ? { background: 'var(--sidebar-active-bg)', borderLeft: '3px solid var(--sidebar-active-border)', paddingLeft: 'calc(0.75rem - 3px)', fontFamily: 'Plus Jakarta Sans' }
                  : { fontFamily: 'Plus Jakarta Sans' }
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
              <div className="h-px flex-1 bg-white/10" />
              <span className="text-[9px] font-extrabold uppercase tracking-[0.25em] text-[#E2B96F]/80" style={{ fontFamily: 'Plus Jakarta Sans' }}>PLATFORM</span>
              <div className="h-px flex-1 bg-white/10" />
            </div>
            <NavLink
              to="/admin"
              onClick={() => mobile && setMobileOpen(false)}
              data-testid="nav-master-admin"
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-[var(--sidebar-text)] hover:bg-[var(--sidebar-hover-bg)] hover:text-white transition-all"
              style={{ fontFamily: 'Plus Jakarta Sans' }}
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
    <div className="min-h-screen bg-[#FAFAFA] flex">
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
        <header className="h-16 bg-white border-b border-[#E8E0F5] flex items-center justify-between px-4 md:px-6 shrink-0">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileOpen(true)}
              className="md:hidden p-1.5 text-[#5A4A7A] hover:text-[#7C35DC]"
              aria-label="Open menu"
              data-testid="mobile-menu-btn"
            >
              <List size={22} />
            </button>
            <WorkspaceSwitcher onSwitch={handleWorkspaceSwitch} />
            <span className="hidden lg:inline-flex items-center gap-1.5 px-2.5 py-1 bg-[#F4F0FF] text-[#7C35DC] rounded-full text-[10px] font-bold uppercase tracking-[0.12em]" data-testid="mode-chip">
              {workspaceType}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <div className="relative hidden sm:block">
              <MagnifyingGlass size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9B8AB0]" />
              <input
                type="text"
                placeholder="Search…"
                className="w-56 bg-[#FAFAFA] border border-[#E8E0F5] text-[#1A0A2E] pl-8 pr-3 py-1.5 rounded-lg focus:border-[#7C35DC] focus:ring-2 focus:ring-[rgba(124,53,220,0.12)] text-sm"
                data-testid="global-search"
              />
            </div>
            <NotificationsBell />
          </div>
        </header>
        <main className="flex-1 overflow-auto">
          <div className="p-4 md:p-6">{children || <Outlet />}</div>
        </main>
      </div>

      <AriaToastWatcher />
      <AriaTourModal />
    </div>
  );
};

export default AppLayout;
