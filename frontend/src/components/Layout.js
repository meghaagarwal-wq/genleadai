import React, { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  House, Tray, ChartBar, MegaphoneSimple, ChartLineUp, UsersThree,
  Gear, SignOut, Bell, MagnifyingGlass, Robot, Moon, List,
} from '@phosphor-icons/react';

const Layout = ({ children }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const handleLogout = () => { logout(); navigate('/login'); };

  const navItems = [
    { icon: House, label: 'Dashboard', path: '/' },
    { icon: Tray, label: 'Lead Inbox', path: '/leads' },
    { icon: ChartBar, label: 'Pipeline', path: '/pipeline' },
    { icon: MegaphoneSimple, label: 'Campaigns', path: '/campaigns' },
    { icon: Robot, label: 'ARIA Agent', path: '/aria' },
    { icon: ChartLineUp, label: 'Analytics', path: '/analytics' },
    { icon: UsersThree, label: 'Team', path: '/settings' },
  ];

  return (
    <div className="min-h-screen bg-[#FAFAFA] flex">
      {/* Sidebar */}
      <aside
        className={`${sidebarOpen ? 'w-64' : 'w-20'} bg-white border-r border-[#E8E0F5] flex flex-col transition-all duration-300 shrink-0`}
        data-testid="sidebar"
      >
        {/* Logo */}
        <div className="h-16 flex items-center justify-between px-5 border-b border-[#E8E0F5]">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'var(--gradient-brand)' }}>
              <span className="text-white font-bold text-sm" style={{ fontFamily: 'Plus Jakarta Sans' }}>G</span>
            </div>
            {sidebarOpen && (
              <span className="text-[#1A0A2E] font-bold text-lg" style={{ fontFamily: 'Plus Jakarta Sans' }}>GenLead<span className="gradient-text">AI</span></span>
            )}
          </div>
          <button onClick={() => setSidebarOpen(!sidebarOpen)} className="p-1 text-[#9B8AB0] hover:text-[#7C35DC] transition-colors">
            <List size={18} />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4">
          <div className="space-y-0.5">
            {navItems.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === '/'}
                data-testid={`nav-${item.label.toLowerCase().replace(/\s/g, '-')}`}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 ${
                    isActive
                      ? 'bg-[#F4F0FF] text-[#7C35DC] font-semibold border-l-[3px] border-[#C044E0]'
                      : 'text-[#5A4A7A] hover:bg-[#F9F5FF] hover:text-[#7C35DC]'
                  }`
                }
                style={{ fontFamily: 'Plus Jakarta Sans' }}
              >
                <item.icon size={20} weight="duotone" />
                {sidebarOpen && <span className="text-sm">{item.label}</span>}
              </NavLink>
            ))}
          </div>
        </nav>

        {/* User */}
        <div className="p-4 border-t border-[#E8E0F5]">
          <div className="flex items-center gap-3">
            <img src={user?.avatar_url || 'https://ui-avatars.com/api/?name=User&background=7C35DC&color=fff'} alt="User" className="w-9 h-9 rounded-full" />
            {sidebarOpen && (
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold text-[#1A0A2E] truncate" style={{ fontFamily: 'Plus Jakarta Sans' }}>{user?.full_name}</div>
                <div className="text-xs text-[#9B8AB0] truncate">{user?.role}</div>
              </div>
            )}
          </div>
          {sidebarOpen && (
            <button
              onClick={handleLogout}
              data-testid="logout-button"
              className="mt-3 w-full flex items-center justify-center gap-2 px-3 py-2 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-lg hover:bg-[#F9F5FF] hover:text-[#7C35DC] transition-all text-sm"
              style={{ fontFamily: 'Plus Jakarta Sans' }}
            >
              <SignOut size={16} /> Sign Out
            </button>
          )}
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Bar */}
        <header className="h-16 bg-white border-b border-[#E8E0F5] flex items-center justify-between px-6 shrink-0">
          <div className="flex items-center gap-4 flex-1">
            <div className="relative flex-1 max-w-md">
              <MagnifyingGlass size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9B8AB0]" />
              <input
                type="text"
                placeholder="Search leads, campaigns..."
                className="w-full bg-[#FAFAFA] border border-[#E8E0F5] text-[#1A0A2E] pl-10 pr-4 py-2 rounded-lg focus:border-[#7C35DC] focus:ring-2 focus:ring-[rgba(124,53,220,0.12)] transition-all text-sm"
                data-testid="global-search"
              />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button className="relative p-2 text-[#5A4A7A] hover:text-[#7C35DC] hover:bg-[#F4F0FF] rounded-lg transition-all" data-testid="notifications-button">
              <Bell size={20} weight="duotone" />
              <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-[#DC2626] rounded-full"></span>
            </button>
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-auto p-6">{children}</main>
      </div>
    </div>
  );
};

export default Layout;
