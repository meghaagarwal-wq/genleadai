import React, { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  House,
  Tray,
  ChartBar,
  MegaphoneSimple,
  ChartLineUp,
  UsersThree,
  Gear,
  SignOut,
  Bell,
  MagnifyingGlass,
} from '@phosphor-icons/react';

const Layout = ({ children }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const navItems = [
    { icon: House, label: 'Dashboard', path: '/' },
    { icon: Tray, label: 'Lead Inbox', path: '/leads' },
    { icon: ChartBar, label: 'Pipeline', path: '/pipeline' },
    { icon: MegaphoneSimple, label: 'Campaigns', path: '/campaigns' },
    { icon: ChartLineUp, label: 'Analytics', path: '/analytics' },
    { icon: UsersThree, label: 'Team', path: '/settings' },
  ];

  return (
    <div className="min-h-screen bg-[#0A0A0A] flex">
      {/* Sidebar */}
      <aside
        className={`${
          sidebarOpen ? 'w-64' : 'w-20'
        } bg-[#0A0A0A] border-r border-white/10 backdrop-blur-xl flex flex-col transition-all duration-300`}
        data-testid="sidebar"
      >
        {/* Logo */}
        <div className="h-16 flex items-center px-6 border-b border-white/10">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-[#0055FF] rounded flex items-center justify-center">
              <span className="text-white font-bold text-sm">GL</span>
            </div>
            {sidebarOpen && (
              <span className="text-white font-bold text-lg">GenLeadAI</span>
            )}
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-6">
          <div className="space-y-1">
            {navItems.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                data-testid={`nav-${item.label.toLowerCase().replace(' ', '-')}`}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-md transition-all duration-200 ${
                    isActive
                      ? 'bg-[#0055FF] text-white'
                      : 'text-[#A3A3A3] hover:bg-[#1E1E1E] hover:text-white'
                  }`
                }
              >
                <item.icon size={20} weight="duotone" />
                {sidebarOpen && <span className="text-sm font-medium">{item.label}</span>}
              </NavLink>
            ))}
          </div>
        </nav>

        {/* User Profile */}
        <div className="p-4 border-t border-white/10">
          <div className="flex items-center gap-3">
            <img
              src={user?.avatar_url || 'https://ui-avatars.com/api/?name=User'}
              alt="User"
              className="w-10 h-10 rounded-full"
            />
            {sidebarOpen && (
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-white truncate">
                  {user?.full_name}
                </div>
                <div className="text-xs text-[#737373] truncate">{user?.email}</div>
              </div>
            )}
          </div>
          {sidebarOpen && (
            <button
              onClick={handleLogout}
              data-testid="logout-button"
              className="mt-3 w-full flex items-center justify-center gap-2 px-3 py-2 bg-transparent border border-[#262626] text-[#F5F5F5] rounded-md hover:bg-[#1E1E1E] transition-colors text-sm"
            >
              <SignOut size={16} />
              Sign Out
            </button>
          )}
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Bar */}
        <header className="h-16 bg-[#0A0A0A]/70 backdrop-blur-xl border-b border-white/10 flex items-center justify-between px-6">
          <div className="flex items-center gap-4 flex-1">
            <div className="relative flex-1 max-w-md">
              <MagnifyingGlass
                size={20}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-[#737373]"
              />
              <input
                type="text"
                placeholder="Search leads, campaigns..."
                className="w-full bg-[#0A0A0A] border border-[#262626] text-white pl-10 pr-4 py-2 rounded-md focus:border-[#0055FF] focus:ring-1 focus:ring-[#0055FF] transition-all text-sm"
                data-testid="global-search"
              />
            </div>
          </div>

          <div className="flex items-center gap-4">
            <button
              className="relative p-2 text-[#A3A3A3] hover:text-white transition-colors"
              data-testid="notifications-button"
            >
              <Bell size={20} weight="duotone" />
              <span className="absolute top-1 right-1 w-2 h-2 bg-[#FF3B30] rounded-full"></span>
            </button>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-auto p-6">{children}</main>
      </div>
    </div>
  );
};

export default Layout;