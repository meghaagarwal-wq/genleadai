import React, { useState } from 'react';
import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { usePlan } from '../context/PlanContext';
import { Toaster } from 'sonner';
import { useTtvMilestoneWatcher } from '../hooks/useTtvMilestoneWatcher';
import {
  House, Tray, ChartBar, MegaphoneSimple, ChartLineUp, UsersThree,
  SignOut, Bell, MagnifyingGlass, Robot, Moon, List, Lightning, X,
  ClockCounterClockwise, ListChecks, Plug, CreditCard, Sparkle,
} from '@phosphor-icons/react';

const Layout = ({ children }) => {
  const { user, logout } = useAuth();
  const { planName, planId, openUpgrade } = usePlan();
  const navigate = useNavigate();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useTtvMilestoneWatcher(!!user);

  const handleLogout = () => { logout(); navigate('/login'); };

  const navItems = [
    { icon: House, label: 'Dashboard', path: '/' },
    { icon: Tray, label: 'Lead Inbox', path: '/leads' },
    { icon: ChartBar, label: 'Pipeline', path: '/pipeline' },
    { icon: ListChecks, label: 'Follow-Ups', path: '/follow-ups' },
    { icon: Robot, label: 'AI Assistant', path: '/ai-assistant' },
    { icon: ChartLineUp, label: 'Reports', path: '/reports' },
    { icon: Plug, label: 'Integrations', path: '/integrations' },
    { icon: CreditCard, label: 'Plan & Billing', path: '/billing' },
    { icon: UsersThree, label: 'Settings', path: '/settings' },
  ];

  const NavContent = ({ mobile = false }) => (
    <>
      <nav className="flex-1 px-3 py-4">
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
                    ? 'bg-[#F4F0FF] text-[#7C35DC] font-semibold border-l-[3px] border-[#C044E0]'
                    : 'text-[#5A4A7A] hover:bg-[#F9F5FF] hover:text-[#7C35DC]'
                }`
              }
              style={{ fontFamily: 'Plus Jakarta Sans' }}
            >
              <item.icon size={18} weight="duotone" />
              <span className="text-sm">{item.label}</span>
            </NavLink>
          ))}
        </div>
      </nav>
      <div className="p-4 border-t border-[#E8E0F5]">
        {/* Plan badge */}
        <button
          onClick={() => planId === 'custom' ? navigate('/billing') : openUpgrade(null, planId === 'starter' ? 'growth' : planId === 'growth' ? 'pro' : 'custom')}
          className="w-full flex items-center justify-between gap-2 mb-3 px-3 py-2 rounded-lg border border-[#E0D4F7] bg-gradient-to-r from-[#F4F0FF] to-white hover:from-[#E0D4F7] transition-all text-left"
          data-testid="plan-badge"
          title="Click to manage plan"
        >
          <div className="flex items-center gap-2 min-w-0">
            <Sparkle size={14} className="text-[#7C35DC]" weight="fill" />
            <div className="min-w-0">
              <div className="text-[10px] font-bold uppercase tracking-wider text-[#9B8AB0]">Current plan</div>
              <div className="text-xs font-bold text-[#1A0A2E] truncate" style={{ fontFamily: 'Plus Jakarta Sans' }}>{planName}</div>
            </div>
          </div>
          {planId !== 'custom' && (
            <span className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded bg-[#7C35DC] text-white flex-shrink-0">Upgrade</span>
          )}
        </button>
        <div className="flex items-center gap-3">
          <img src={user?.avatar_url || 'https://ui-avatars.com/api/?name=User&background=7C35DC&color=fff'} alt="User" className="w-9 h-9 rounded-full" />
          <div className="flex-1 min-w-0">
            <div className="text-sm font-semibold text-[#1A0A2E] truncate" style={{ fontFamily: 'Plus Jakarta Sans' }}>{user?.full_name}</div>
            <div className="text-xs text-[#9B8AB0] truncate">{user?.role}</div>
          </div>
        </div>
        <button onClick={handleLogout} data-testid="logout-button"
          className="mt-3 w-full flex items-center justify-center gap-2 px-3 py-2 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-lg hover:bg-[#F9F5FF] hover:text-[#7C35DC] transition-all text-sm"
          style={{ fontFamily: 'Plus Jakarta Sans' }}>
          <SignOut size={16} /> Sign Out
        </button>
      </div>
    </>
  );

  return (
    <div className="min-h-screen bg-[#FAFAFA] flex">
      {/* Desktop Sidebar */}
      <aside className={`hidden md:flex ${sidebarOpen ? 'w-60' : 'w-16'} bg-white border-r border-[#E8E0F5] flex-col transition-all duration-300 shrink-0`} data-testid="sidebar">
        <div className="h-14 flex items-center justify-between px-4 border-b border-[#E8E0F5]">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0" style={{ background: 'var(--gradient-brand)' }}>
              <span className="text-white font-bold text-xs" style={{ fontFamily: 'Plus Jakarta Sans' }}>G</span>
            </div>
            {sidebarOpen && <span className="text-[#1A0A2E] font-bold text-base" style={{ fontFamily: 'Plus Jakarta Sans' }}>GenLead<span className="gradient-text">AI</span></span>}
          </div>
          <button onClick={() => setSidebarOpen(!sidebarOpen)} className="p-1 text-[#9B8AB0] hover:text-[#7C35DC] transition-colors"><List size={16} /></button>
        </div>
        {sidebarOpen ? <NavContent /> : (
          <nav className="flex-1 px-2 py-4">
            <div className="space-y-1">
              {navItems.map((item) => (
                <NavLink key={item.path} to={item.path} end={item.path === '/'} title={item.label}
                  className={({ isActive }) => `flex items-center justify-center p-2.5 rounded-lg transition-all ${isActive ? 'bg-[#F4F0FF] text-[#7C35DC]' : 'text-[#5A4A7A] hover:bg-[#F9F5FF] hover:text-[#7C35DC]'}`}>
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
          <div className="absolute inset-0 bg-black/20 backdrop-blur-sm" onClick={() => setMobileMenuOpen(false)} />
          <aside className="absolute left-0 top-0 bottom-0 w-72 bg-white border-r border-[#E8E0F5] flex flex-col z-10">
            <div className="h-14 flex items-center justify-between px-4 border-b border-[#E8E0F5]">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: 'var(--gradient-brand)' }}>
                  <span className="text-white font-bold text-xs">G</span>
                </div>
                <span className="text-[#1A0A2E] font-bold text-base" style={{ fontFamily: 'Plus Jakarta Sans' }}>GenLead<span className="gradient-text">AI</span></span>
              </div>
              <button onClick={() => setMobileMenuOpen(false)} className="p-1 text-[#9B8AB0]"><X size={20} /></button>
            </div>
            <NavContent mobile />
          </aside>
        </div>
      )}

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 bg-white border-b border-[#E8E0F5] flex items-center justify-between px-4 md:px-6 shrink-0">
          <div className="flex items-center gap-3 flex-1">
            <button onClick={() => setMobileMenuOpen(true)} className="md:hidden p-1.5 text-[#5A4A7A] hover:text-[#7C35DC]" data-testid="mobile-menu-btn"><List size={22} /></button>
            <div className="relative flex-1 max-w-md hidden sm:block">
              <MagnifyingGlass size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9B8AB0]" />
              <input type="text" placeholder="Search leads, campaigns..." className="w-full bg-[#FAFAFA] border border-[#E8E0F5] text-[#1A0A2E] pl-9 pr-4 py-1.5 rounded-lg focus:border-[#7C35DC] focus:ring-2 focus:ring-[rgba(124,53,220,0.12)] transition-all text-sm" data-testid="global-search" />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button className="relative p-2 text-[#5A4A7A] hover:text-[#7C35DC] hover:bg-[#F4F0FF] rounded-lg transition-all" data-testid="notifications-button">
              <Bell size={18} weight="duotone" />
              <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 bg-[#DC2626] rounded-full"></span>
            </button>
          </div>
        </header>
        <main className="flex-1 overflow-auto p-4 md:p-6">{children}</main>
      </div>
      <Toaster position="bottom-right" richColors closeButton toastOptions={{ style: { fontFamily: 'Plus Jakarta Sans, sans-serif' } }} />
    </div>
  );
};

export default Layout;
