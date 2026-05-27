import { useEffect, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  Gauge, Users, Buildings, ListChecks, ChartBar, Plugs, GearSix, SignOut, ArrowsLeftRight,
  EnvelopeOpen, LinkedinLogo, MapTrifold, UsersThree, Megaphone, Pulse, Sparkle, GraduationCap, Brain,
} from '@phosphor-icons/react';
import { useAuth } from '../context/AuthContext';
import { useWorkspace, WORKSPACES } from '../context/WorkspaceContext';
import api from '../config/api';

// PART C.2 v3.0 — 8-item nav max, mode-adaptive.
// - Intelligence Feed: B2B + Hybrid only
// - Lead Inbox: B2C + Hybrid only
const NAV = [
  { to: '/pt',                  label: 'Home',              icon: Gauge },
  { to: '/pt/intelligence',     label: 'Intelligence Feed', icon: Brain,        modes: ['b2b', 'hybrid'] },
  { to: '/pt/leads',            label: 'Lead Inbox',        icon: Users,        modes: ['b2c', 'hybrid'] },
  { to: '/pt/conversations',    label: 'Conversations',     icon: EnvelopeOpen },
  { to: '/pt/icps',             label: 'ICPs',              icon: UsersThree },
  { to: '/pt/train-aria',       label: 'Train ARIA',        icon: GraduationCap },
  { to: '/pt/integrations',     label: 'Integrations',      icon: Plugs },
  { to: '/pt/reports',          label: 'Reports',           icon: ChartBar },
  { to: '/pt/settings',         label: 'Settings',          icon: GearSix },
];

const WorkspaceSwitcher = () => {
  const { active, setActive } = useWorkspace();
  const navigate = useNavigate();
  const switchTo = (slug) => {
    const ws = WORKSPACES.find(w => w.slug === slug);
    if (!ws) return;
    setActive(ws);
    navigate(ws.home);
  };
  return (
    <div className="px-3 py-2.5 border-b border-[#E2E8F0]" data-testid="pt-workspace-switcher">
      <div className="text-[9px] font-bold uppercase tracking-[0.22em] text-[#64748B] mb-1.5">Workspace</div>
      <div className="flex items-center gap-2">
        <select
          value={active.slug}
          onChange={(e) => switchTo(e.target.value)}
          data-testid="pt-workspace-select"
          className="flex-1 text-sm font-semibold text-[#0F172A] bg-white border border-[#CBD5E1] rounded-md px-2 py-1.5 outline-none focus:ring-2 focus:ring-[#C044E0]/20"
        >
          {WORKSPACES.map(w => (
            <option key={w.slug} value={w.slug}>{w.label}</option>
          ))}
        </select>
        <ArrowsLeftRight size={14} className="text-[#64748B]" weight="bold" />
      </div>
    </div>
  );
};

const PtLayout = ({ children }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [workspaceType, setWorkspaceType] = useState('hybrid');
  const handleLogout = () => { logout(); navigate('/login'); };

  // Fetch workspace type for adaptive sidebar (Phase 4)
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await api.get('/api/aria/workspace-type');
        if (!cancelled) setWorkspaceType(r.data?.workspace_type || 'hybrid');
      } catch (e) {
        // default to hybrid (shows everything)
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const visibleNav = NAV.filter((item) => {
    if (!item.modes) return true;  // always visible
    return item.modes.includes(workspaceType);
  });

  // iter87-89 — pin the active tenant to ten_pietential whenever we're
  // inside /pt. Done SYNCHRONOUSLY first so the X-Tenant-Id header is set
  // before any child page fires its initial fetch.
  useEffect(() => {
    let cancelled = false;
    // Step 1 — synchronous fallback (always runs immediately).
    try {
      const stored = JSON.parse(localStorage.getItem('active_tenant') || 'null');
      if (stored?.id !== 'ten_pietential') {
        localStorage.setItem('active_tenant', JSON.stringify({ id: 'ten_pietential', name: 'Pietential' }));
      }
    } catch (e) {
      localStorage.setItem('active_tenant', JSON.stringify({ id: 'ten_pietential', name: 'Pietential' }));
    }
    // Step 2 — async upgrade with the full tenant object from the server.
    (async () => {
      try {
        const r = await api.get('/api/tenants/me');
        if (cancelled) return;
        const pietential = (r.data?.tenants || []).find(t => t.id === 'ten_pietential');
        if (pietential) localStorage.setItem('active_tenant', JSON.stringify(pietential));
      } catch (e) {
        // already wrote the synchronous fallback above
      }
    })();
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex">
      <aside className="hidden md:flex w-60 flex-col bg-white border-r border-[#E2E8F0] shrink-0" data-testid="pt-sidebar">
        {/* Brand */}
        <div className="h-16 flex items-center gap-2.5 px-4 border-b border-[#E2E8F0]">
          <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #7C35DC 0%, #C044E0 100%)' }}>
            <span className="text-white font-extrabold text-base" style={{ fontFamily: 'Space Grotesk, Inter' }}>A</span>
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="text-sm font-extrabold text-[#0F172A] leading-none tracking-tight" style={{ fontFamily: 'Space Grotesk, Inter' }}>GenLeadAI Aria</span>
            </div>
            <div className="text-[10px] text-[#64748B] uppercase tracking-[0.16em] mt-0.5">Pietential Growth Intelligence</div>
            {/* iter88 — pinned tenant indicator. Lets the founder + GenLeadAI
                operator confirm the workspace context is correct at a glance.
                If this ever shows the wrong tenant, the multi-tenant state
                has drifted and the dashboard data will be wrong. */}
            <div className="mt-1.5 inline-flex items-center gap-1 text-[9px] font-bold uppercase tracking-[0.18em] text-[#16A34A]" data-testid="pt-tenant-pin">
              <span className="w-1.5 h-1.5 rounded-full bg-[#16A34A]" />
              Tenant · Pietential
            </div>
          </div>
        </div>

        <WorkspaceSwitcher />

        {/* Nav */}
        <nav className="flex-1 px-2 py-3" data-testid="pt-nav">
          <div className="space-y-0.5">
            {visibleNav.map(item => (
              <NavLink key={item.to} to={item.to} end={item.to === '/pt'}
                data-testid={`pt-nav-${item.label.toLowerCase().replace(/\s+/g, '-')}`}
                className={({ isActive }) =>
                  `flex items-center gap-2.5 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-[#7C35DC]/8 text-[#7C35DC] border-l-2 border-[#7C35DC]'
                      : 'text-[#475569] hover:text-[#0F172A] hover:bg-[#F1F5F9] border-l-2 border-transparent'
                  }`
                }
              >
                <item.icon size={16} weight="duotone" />
                {item.label}
              </NavLink>
            ))}
          </div>
        </nav>

        {/* Footer */}
        <div className="border-t border-[#E2E8F0] p-3">
          <div className="flex items-center gap-2.5 mb-2">
            <img src={user?.avatar_url || `https://ui-avatars.com/api/?name=${encodeURIComponent(user?.full_name || 'User')}&background=7C35DC&color=fff`} alt="" className="w-8 h-8 rounded-full" />
            <div className="min-w-0">
              <div className="text-xs font-semibold text-[#0F172A] truncate">{user?.full_name}</div>
              <div className="text-[10px] text-[#64748B] truncate">{user?.role}</div>
            </div>
          </div>
          <button onClick={handleLogout} data-testid="pt-logout"
            className="w-full flex items-center justify-center gap-1.5 px-2.5 py-1.5 text-xs font-semibold text-[#475569] border border-[#E2E8F0] rounded-md hover:bg-[#F1F5F9]">
            <SignOut size={12} /> Sign out
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-x-hidden">
        <div className="px-6 lg:px-10 py-8 max-w-[1400px] mx-auto">{children}</div>
      </main>
    </div>
  );
};

export default PtLayout;
