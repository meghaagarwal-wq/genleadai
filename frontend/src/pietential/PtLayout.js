import { NavLink, useNavigate } from 'react-router-dom';
import {
  Gauge, Users, Buildings, ListChecks, ChartBar, Plugs, GearSix, SignOut, ArrowsLeftRight,
} from '@phosphor-icons/react';
import { useAuth } from '../context/AuthContext';
import { useWorkspace, WORKSPACES } from '../context/WorkspaceContext';

const NAV = [
  { to: '/pt',                label: 'Overview',     icon: Gauge },
  { to: '/pt/leads',          label: 'Lead Feed',    icon: Users },
  { to: '/pt/accounts',       label: 'Accounts',     icon: Buildings },
  { to: '/pt/tasks',          label: 'Tasks',        icon: ListChecks },
  { to: '/pt/reports',        label: 'Reports',      icon: ChartBar },
  { to: '/pt/integrations',   label: 'Integrations', icon: Plugs },
  { to: '/pt/settings',       label: 'Settings',     icon: GearSix },
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
  const handleLogout = () => { logout(); navigate('/login'); };

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
              <span className="text-sm font-extrabold text-[#0F172A] leading-none tracking-tight" style={{ fontFamily: 'Space Grotesk, Inter' }}>Aria</span>
              <span className="px-1.5 py-[1px] rounded-[4px] text-[8px] font-bold uppercase tracking-[0.18em] text-[#B45309] border border-[#F59E0B]/50" style={{ background: 'rgba(245,158,11,0.12)' }}>Beta</span>
            </div>
            <div className="text-[10px] text-[#64748B] uppercase tracking-[0.16em] mt-0.5">for Pietential</div>
          </div>
        </div>

        <WorkspaceSwitcher />

        {/* Nav */}
        <nav className="flex-1 px-2 py-3" data-testid="pt-nav">
          <div className="space-y-0.5">
            {NAV.map(item => (
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
