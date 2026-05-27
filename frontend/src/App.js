/**
 * App.js — iter108 NUCLEAR CONSOLIDATION
 *
 * The ONLY surfaces that exist after this commit:
 *   - /app/*            — client dashboard (every workspace, single AppLayout)
 *   - /admin/*          — super-admin panel (master_admin only)
 *   - /login /signup /onboarding /invite
 *   - /aria/* /privacy /terms /dpa     — public marketing / legal
 *   - /pt/* and any legacy /dashboard, /leads, etc.  → redirect to /app/...
 *
 * Layout files:
 *   - components/AppLayout.js      — THE ONE client layout
 *   - admin/AdminLayout.js         — admin panel
 *   - public/PublicLayout.js       — public marketing
 *   (DELETED: components/Layout.js, pietential/PtLayout.js)
 */
import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { PlanProvider } from './context/PlanContext';
import { WorkspaceProvider } from './context/WorkspaceContext';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';

// Public & auth
import Login from './pages/Login';
import Signup from './pages/Signup';
import AriaLanding from './pages/landing/AriaLanding';
import InviteAccept from './pages/InviteAccept';
import { Privacy, Terms, DPA } from './pages/legal/Legal';
import AriaHome from './public/pages/AriaHome';
import DemoDashboard from './public/pages/DemoDashboard';
import LeadFeedSEO from './public/pages/LeadFeedSEO';
import SalesReportsSEO from './public/pages/SalesReportsSEO';
import UseFounders from './public/pages/use-cases/Founders';
import UseStartups from './public/pages/use-cases/Startups';
import UseAgencies from './public/pages/use-cases/Agencies';
import UseConsultants from './public/pages/use-cases/Consultants';
import UseSalesTeams from './public/pages/use-cases/SalesTeams';
import CompareAriaVsCrm from './public/pages/compare/AriaVsCrm';
import CompareAriaVsSpreadsheets from './public/pages/compare/AriaVsSpreadsheets';
import CompareAiVsCrm from './public/pages/compare/AISalesAssistantVsCrm';
import OnboardingWizard from './pages/OnboardingWizard';
import OnboardingWizardV3 from './pages/OnboardingWizardV3';
import InteractiveDemo from './pages/InteractiveDemo';
import DemoSandbox from './pages/DemoSandbox';

// Admin
import AdminLayout from './admin/AdminLayout';

// Client app shell + pages (the unified /app/* tree)
import AppLayout from './components/AppLayout';
import PtOverview from './pietential/pages/PtOverview';
import PtLeadFeed from './pietential/pages/PtLeadFeed';
import PtLeadDetail from './pietential/pages/PtLeadDetail';
import PtIntelligenceFeed from './pietential/pages/PtIntelligenceFeed';
import PtReports from './pietential/pages/PtReports';
import PtIntegrations from './pietential/pages/PtIntegrations';
import PtAutomations from './pietential/pages/PtAutomations';
import PtAutomationLogs from './pietential/pages/PtAutomationLogs';
import PtCampaigns from './pietential/pages/PtCampaigns';
import PtAccounts from './pietential/pages/PtAccounts';
import PtTouchpointMap from './pietential/pages/PtTouchpointMap';
import PtTasks from './pietential/pages/PtTasks';
import PtTeam from './pietential/pages/PtTeam';
import PtSettings from './pietential/pages/PtSettings';
import { PtSaleshandy, PtLemlist } from './pietential/pages/PtPlatformActivity';
import AISetupAssistant from './pages/AISetupAssistant';
import TrainAriaV2 from './pages/TrainAriaV2';
import Conversations from './pages/Conversations';
import ICPManager from './pages/ICPManager';
import { BillingSuccess, BillingCancel } from './pages/BillingReturn';
import NotFound from './pages/NotFound';

import ErrorBoundary from './components/ErrorBoundary';
import api from './config/api';
import './App.css';

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1 } },
});

function ProtectedRoute({ children, requireOnboarded = true, requireRole = null }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  const [gateState, setGateState] = React.useState({ checked: false, completed: true, tenantId: null });

  React.useEffect(() => {
    if (!user) { setGateState({ checked: true, completed: true, tenantId: null }); return; }
    let alive = true;
    api.get('/api/onboarding/status')
      .then((r) => {
        if (!alive) return;
        const t = r.data?.tenant;
        try {
          const stored = JSON.parse(localStorage.getItem('active_tenant') || 'null');
          const merged = { ...(stored || {}), id: t?.id, name: t?.name, onboarding_completed: !!r.data?.completed };
          if (merged.id) localStorage.setItem('active_tenant', JSON.stringify(merged));
        } catch (e) { /* ignore */ }
        setGateState({ checked: true, completed: !!r.data?.completed, tenantId: t?.id || null });
      })
      .catch(() => setGateState({ checked: true, completed: true, tenantId: null }));
    return () => { alive = false; };
  }, [user]);

  if (requireRole && user && user.role !== requireRole) return <Navigate to="/app" replace />;
  if (loading || (user && !gateState.checked)) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0A0A0A]">
        <div className="text-[#A3A3A3]">Loading…</div>
      </div>
    );
  }
  if (!user) {
    if (location.pathname === '/' || location.pathname === '') return <AriaLanding />;
    return <Navigate to="/login" replace />;
  }
  if (requireOnboarded && !gateState.completed) return <Navigate to="/onboarding" replace />;
  return children;
}

function ImpersonationBanner() {
  const [info, setInfo] = React.useState(null);
  React.useEffect(() => {
    try { const raw = localStorage.getItem('impersonating'); if (raw) setInfo(JSON.parse(raw)); } catch (e) { /* ignore */ }
  }, []);
  if (!info) return null;
  const stop = () => {
    localStorage.removeItem('impersonating');
    localStorage.removeItem('X-Tenant-Id');
    window.location.href = '/admin/workspaces';
  };
  return (
    <div className="fixed top-0 inset-x-0 z-[100] bg-amber-500 text-amber-950 px-4 py-2 flex items-center justify-between text-sm shadow-md" data-testid="impersonation-banner">
      <div><strong>Admin view:</strong> impersonating <strong>{info.workspace_name}</strong> ({info.mode})</div>
      <button data-testid="stop-impersonation-btn" onClick={stop} className="px-3 py-1 bg-amber-900 hover:bg-amber-800 text-white rounded text-xs font-semibold">
        Stop & return to admin
      </button>
    </div>
  );
}

/**
 * Preserves the trailing path when redirecting a legacy URL to its /app/*
 * equivalent. Used for /pt/* and a few legacy single-page paths.
 */
const PathRedirect = ({ from }) => {
  const loc = useLocation();
  const tail = (loc.pathname || '').replace(new RegExp('^' + from), '');
  const target = `/app${tail || ''}${loc.search || ''}`;
  return <Navigate to={target} replace />;
};

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ErrorBoundary>
        <AuthProvider>
          <PlanProvider>
            <WorkspaceProvider>
              <Router>
                <ImpersonationBanner />
                <Routes>
                  {/* ── Public / auth ─────────────────────────────────── */}
                  <Route path="/login" element={<Login />} />
                  <Route path="/register" element={<Navigate to="/signup" replace />} />
                  <Route path="/signup" element={<Signup />} />
                  <Route path="/demo" element={<InteractiveDemo />} />
                  <Route path="/demo-sandbox" element={<DemoSandbox />} />
                  <Route path="/invite/:token" element={<InviteAccept />} />
                  <Route path="/privacy" element={<Privacy />} />
                  <Route path="/terms" element={<Terms />} />
                  <Route path="/dpa" element={<DPA />} />

                  {/* Public ARIA marketing / SEO */}
                  <Route path="/aria" element={<AriaHome />} />
                  <Route path="/aria/demo-dashboard" element={<DemoDashboard />} />
                  <Route path="/aria/lead-feed" element={<LeadFeedSEO />} />
                  <Route path="/aria/sales-reports" element={<SalesReportsSEO />} />
                  <Route path="/aria/use-cases/founders" element={<UseFounders />} />
                  <Route path="/aria/use-cases/startups" element={<UseStartups />} />
                  <Route path="/aria/use-cases/agencies" element={<UseAgencies />} />
                  <Route path="/aria/use-cases/consultants" element={<UseConsultants />} />
                  <Route path="/aria/use-cases/sales-teams" element={<UseSalesTeams />} />
                  <Route path="/aria/compare/aria-vs-crm" element={<CompareAriaVsCrm />} />
                  <Route path="/aria/compare/aria-vs-spreadsheets" element={<CompareAriaVsSpreadsheets />} />
                  <Route path="/aria/compare/ai-sales-assistant-vs-crm" element={<CompareAiVsCrm />} />

                  {/* ── Admin panel ───────────────────────────────────── */}
                  <Route
                    path="/admin/*"
                    element={
                      <ProtectedRoute requireRole="master_admin">
                        <AdminLayout />
                      </ProtectedRoute>
                    }
                  />

                  {/* ── Onboarding ────────────────────────────────────── */}
                  <Route
                    path="/onboarding"
                    element={<ProtectedRoute requireOnboarded={false}><OnboardingWizard /></ProtectedRoute>}
                  />
                  <Route
                    path="/onboarding-v3"
                    element={<ProtectedRoute requireOnboarded={false}><OnboardingWizardV3 /></ProtectedRoute>}
                  />

                  {/* ── Legacy redirects (kept working, no UI) ────────── */}
                  <Route path="/pt" element={<Navigate to="/app" replace />} />
                  <Route path="/pt/*" element={<PathRedirect from="/pt" />} />
                  <Route path="/dashboard" element={<Navigate to="/app" replace />} />
                  <Route path="/dashboard-demo" element={<Navigate to="/app" replace />} />
                  <Route path="/leads" element={<Navigate to="/app/leads" replace />} />
                  <Route path="/leads/:id" element={<PathRedirect from="" />} />
                  <Route path="/pipeline" element={<Navigate to="/app/leads" replace />} />
                  <Route path="/conversations" element={<Navigate to="/app/conversations" replace />} />
                  <Route path="/icps" element={<Navigate to="/app/icps" replace />} />
                  <Route path="/integrations" element={<Navigate to="/app/integrations" replace />} />
                  <Route path="/reports" element={<Navigate to="/app/reports" replace />} />
                  <Route path="/settings" element={<Navigate to="/app/settings" replace />} />
                  <Route path="/aria-agent/*" element={<Navigate to="/app/intelligence" replace />} />
                  <Route path="/contacts" element={<Navigate to="/app/leads" replace />} />
                  <Route path="/follow-ups" element={<Navigate to="/app" replace />} />
                  <Route path="/sleeping-leads" element={<Navigate to="/app/leads" replace />} />
                  <Route path="/your-5-today" element={<Navigate to="/app" replace />} />
                  <Route path="/audit-log" element={<Navigate to="/app/settings" replace />} />
                  <Route path="/troubleshooting" element={<Navigate to="/app/settings" replace />} />
                  <Route path="/limits" element={<Navigate to="/app/settings" replace />} />
                  <Route path="/billing" element={<Navigate to="/app/settings" replace />} />
                  <Route path="/billing/invoices" element={<Navigate to="/app/settings" replace />} />
                  <Route path="/billing/success" element={<BillingSuccess />} />
                  <Route path="/billing/cancel" element={<BillingCancel />} />
                  <Route path="/master-admin" element={<Navigate to="/admin" replace />} />
                  <Route path="/admin/feedback" element={<Navigate to="/admin" replace />} />
                  <Route path="/admin/failed-messages" element={<Navigate to="/admin/system" replace />} />
                  <Route path="/touchpoint-journey" element={<Navigate to="/app/touchpoints" replace />} />
                  <Route path="/outreach" element={<Navigate to="/app/campaigns" replace />} />
                  <Route path="/outreach/:campaignId" element={<Navigate to="/app/campaigns" replace />} />
                  <Route path="/sales-engagement" element={<Navigate to="/app/campaigns" replace />} />

                  {/* ── THE ONLY CLIENT DASHBOARD: /app/* ─────────────── */}
                  <Route
                    path="/app/*"
                    element={
                      <ProtectedRoute>
                        <AppLayout>
                          <Routes>
                            <Route path="/" element={<PtOverview />} />
                            <Route path="/intelligence" element={<PtIntelligenceFeed />} />
                            <Route path="/leads" element={<PtLeadFeed />} />
                            <Route path="/leads/:id" element={<PtLeadDetail />} />
                            <Route path="/conversations" element={<Conversations />} />
                            <Route path="/icps" element={<ICPManager />} />
                            <Route path="/train-aria" element={<TrainAriaV2 />} />
                            <Route path="/ai-setup" element={<AISetupAssistant />} />
                            <Route path="/automations" element={<PtAutomations />} />
                            <Route path="/integrations" element={<PtIntegrations />} />
                            <Route path="/reports" element={<PtReports />} />
                            <Route path="/settings" element={<PtSettings />} />
                            {/* Sub-routes kept reachable but absent from main nav */}
                            <Route path="/saleshandy" element={<PtSaleshandy />} />
                            <Route path="/lemlist" element={<PtLemlist />} />
                            <Route path="/campaigns" element={<PtCampaigns />} />
                            <Route path="/accounts" element={<PtAccounts />} />
                            <Route path="/touchpoints" element={<PtTouchpointMap />} />
                            <Route path="/tasks" element={<PtTasks />} />
                            <Route path="/logs" element={<PtAutomationLogs />} />
                            <Route path="/team" element={<PtTeam />} />
                            <Route path="*" element={<NotFound />} />
                          </Routes>
                        </AppLayout>
                      </ProtectedRoute>
                    }
                  />

                  {/* Root: public marketing for guests, /app for users */}
                  <Route
                    path="/"
                    element={
                      <ProtectedRoute>
                        <Navigate to="/app" replace />
                      </ProtectedRoute>
                    }
                  />

                  <Route path="*" element={<NotFound />} />
                </Routes>
                <Toaster position="bottom-right" richColors closeButton toastOptions={{ style: { fontFamily: 'Plus Jakarta Sans, sans-serif' } }} />
              </Router>
            </WorkspaceProvider>
          </PlanProvider>
        </AuthProvider>
      </ErrorBoundary>
    </QueryClientProvider>
  );
}

export default App;
