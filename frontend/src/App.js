import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { PlanProvider } from './context/PlanContext';
import { WorkspaceProvider } from './context/WorkspaceContext';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import Login from './pages/Login';
import Register from './pages/Register';
import Signup from './pages/Signup';
import LandingPage from './pages/LandingPage';
import DemoSandbox from './pages/DemoSandbox';
import InviteAccept from './pages/InviteAccept';
import Dashboard from './pages/Dashboard';
import LeadInbox from './pages/LeadInbox';
import LeadDetail from './pages/LeadDetail';
import Pipeline from './pages/Pipeline';
import Campaigns from './pages/Campaigns';
import Analytics from './pages/Analytics';
import Reports from './pages/Reports';
import FailedMessages from './pages/FailedMessages';
import Conversations from './pages/Conversations';
import InteractiveDemo from './pages/InteractiveDemo';
import Settings from './pages/Settings';
import AriaFeed from './pages/AriaFeed';
import AriaAnalytics from './pages/AriaAnalytics';
import YourFiveToday from './pages/YourFiveToday';
import SleepingLeads from './pages/SleepingLeads';
import AuditLog from './pages/AuditLog';
import OnboardingWizard from './pages/OnboardingWizard';
import Billing from './pages/Billing';
import Invoices from './pages/Invoices';
import Troubleshooting from './pages/Troubleshooting';
import AISetupAssistant from './pages/AISetupAssistant';
import Limits from './pages/Limits';
import Contacts from './pages/Contacts';
import FollowUps from './pages/FollowUps';
import AIAssistant from './pages/AIAssistant';
import Integrations from './pages/Integrations';
import TrainAria from './pages/TrainAria';
import TrainAriaV2 from './pages/TrainAriaV2';
import PtIntelligenceFeed from './pietential/pages/PtIntelligenceFeed';
import Playbooks from './pages/Playbooks';
import AISalesJourneys from './pages/AISalesJourneys';
import FounderBriefs from './pages/FounderBriefs';
import HumanHandoff from './pages/HumanHandoff';
import RevivalEngine from './pages/RevivalEngine';
import AriaInsightsPage from './pages/AriaInsightsPage';
import SalesAssets from './pages/SalesAssets';
import AriaBrain from './pages/AriaBrain';
import WeeklyRecap from './pages/WeeklyRecap';
import SalesEngagement from './pages/SalesEngagement';
import AdminFeedback from './pages/AdminFeedback';
import MasterAdmin from './pages/MasterAdmin';
import TouchpointJourney from './pages/TouchpointJourney';
import ICPManager from './pages/ICPManager';
import OutreachCampaigns from './pages/OutreachCampaigns';
import { BillingSuccess, BillingCancel } from './pages/BillingReturn';
import NotFound from './pages/NotFound';
import { Privacy, Terms, DPA } from './pages/legal/Legal';

// Pietential workspace
import PtLayout from './pietential/PtLayout';
import PtOverview from './pietential/pages/PtOverview';

import PtLeadFeed from './pietential/pages/PtLeadFeed';
import PtLeadDetail from './pietential/pages/PtLeadDetail';
import PtAccounts from './pietential/pages/PtAccounts';
import PtTasks from './pietential/pages/PtTasks';
import PtReports from './pietential/pages/PtReports';
import PtIntegrations from './pietential/pages/PtIntegrations';
import PtSettings from './pietential/pages/PtSettings';
import { PtSaleshandy, PtLemlist } from './pietential/pages/PtPlatformActivity';
import PtTouchpointMap from './pietential/pages/PtTouchpointMap';
import PtTeam from './pietential/pages/PtTeam';
import PtCampaigns from './pietential/pages/PtCampaigns';
import PtAutomationLogs from './pietential/pages/PtAutomationLogs';
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
import Layout from './components/Layout';
import UpgradeModal from './components/UpgradeModal';
import ErrorBoundary from './components/ErrorBoundary';
import api from './config/api';
import './App.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function ProtectedRoute({ children, requireOnboarded = true }) {
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
        // Keep active_tenant in localStorage current
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

  if (loading || (user && !gateState.checked)) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0A0A0A]">
        <div className="text-[#A3A3A3]">Loading...</div>
      </div>
    );
  }

  // Unauthenticated visitors at the root URL land on the public marketing page
  // instead of bouncing to /login. Any other deep-link still requires sign-in.
  if (!user) {
    if (location.pathname === '/' || location.pathname === '') return <LandingPage />;
    return <Navigate to="/login" replace />;
  }

  if (requireOnboarded && !gateState.completed) {
    return <Navigate to="/onboarding" replace />;
  }

  return children;
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ErrorBoundary>
      <AuthProvider>
        <PlanProvider>
          <WorkspaceProvider>
          <Router>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Navigate to="/signup" replace />} />
              <Route path="/signup" element={<Signup />} />
              <Route path="/demo" element={<InteractiveDemo />} />
              <Route path="/demo-sandbox" element={<DemoSandbox />} />
              <Route path="/invite/:token" element={<InviteAccept />} />

              {/* Legal pages (public) */}
              <Route path="/privacy" element={<Privacy />} />
              <Route path="/terms" element={<Terms />} />
              <Route path="/dpa" element={<DPA />} />

              {/* Public ARIA content ecosystem (crawlable, no auth) */}
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

              {/* Pietential workspace — parallel protected app */}
              <Route
                path="/pt/*"
                element={
                  <ProtectedRoute>
                    <PtLayout>
                      <Routes>
                        <Route path="/" element={<PtOverview />} />
                        <Route path="/ai-setup" element={<AISetupAssistant />} />
                        <Route path="/train-aria" element={<TrainAriaV2 />} />
                        <Route path="/intelligence" element={<PtIntelligenceFeed />} />
                        <Route path="/leads" element={<PtLeadFeed />} />
                        <Route path="/leads/:id" element={<PtLeadDetail />} />
                        <Route path="/saleshandy" element={<PtSaleshandy />} />
                        <Route path="/lemlist" element={<PtLemlist />} />
                        <Route path="/campaigns" element={<PtCampaigns />} />
                        <Route path="/accounts" element={<PtAccounts />} />
                        <Route path="/touchpoints" element={<PtTouchpointMap />} />
                        <Route path="/tasks" element={<PtTasks />} />
                        <Route path="/logs" element={<PtAutomationLogs />} />
                        <Route path="/reports" element={<PtReports />} />
                        <Route path="/integrations" element={<PtIntegrations />} />
                        <Route path="/team" element={<PtTeam />} />
                        <Route path="/settings" element={<PtSettings />} />
                      </Routes>
                    </PtLayout>
                  </ProtectedRoute>
                }
              />
              <Route
                path="/onboarding"
                element={
                  <ProtectedRoute requireOnboarded={false}>
                    <OnboardingWizard />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/*"
                element={
                  <ProtectedRoute>
                    <Layout>
                      <Routes>
                        <Route path="/" element={<Dashboard />} />
                        <Route path="/dashboard" element={<Navigate to="/" replace />} />
                        {/* iter71 — protected demo dashboard with sample data.
                            Public marketing /demo route (InteractiveDemo) takes precedence
                            so we route the in-app demo to /dashboard-demo. */}
                        <Route path="/dashboard-demo" element={<Dashboard demo={true} />} />
                        <Route path="/your-5-today" element={<YourFiveToday />} />
                        <Route path="/leads" element={<LeadInbox />} />
                        <Route path="/leads/:id" element={<LeadDetail />} />
                        <Route path="/sleeping-leads" element={<SleepingLeads />} />
                        <Route path="/pipeline" element={<Pipeline />} />
                        <Route path="/follow-ups" element={<FollowUps />} />
                        <Route path="/conversations" element={<Conversations />} />
                        <Route path="/ai-assistant" element={<AIAssistant />} />
                        <Route path="/integrations" element={<Integrations />} />
                        <Route path="/campaigns" element={<Campaigns />} />
                        <Route path="/reports" element={<Reports />} />
                        <Route path="/admin/failed-messages" element={<FailedMessages />} />
                        <Route path="/analytics" element={<Analytics />} />
                        <Route path="/aria" element={<AriaFeed />} />
                        <Route path="/aria/analytics" element={<AriaAnalytics />} />
                        <Route path="/audit-log" element={<AuditLog />} />
                        <Route path="/billing" element={<Billing />} />
                        <Route path="/billing/invoices" element={<Invoices />} />
                        <Route path="/settings" element={<Settings />} />
                        <Route path="/troubleshooting" element={<Troubleshooting />} />
                        <Route path="/limits" element={<Limits />} />
                        <Route path="/contacts" element={<Contacts />} />
                        {/* AI Sales Agent additive routes */}
                        <Route path="/aria-agent/train" element={<TrainAria />} />
                        <Route path="/aria-agent/playbooks" element={<Playbooks />} />
                        <Route path="/aria-agent/journeys" element={<AISalesJourneys />} />
                        <Route path="/aria-agent/briefs" element={<FounderBriefs />} />
                        <Route path="/aria-agent/handoff" element={<HumanHandoff />} />
                        <Route path="/aria-agent/revival" element={<RevivalEngine />} />
                        <Route path="/aria-agent/insights" element={<AriaInsightsPage />} />
                        <Route path="/aria-agent/assets" element={<SalesAssets />} />
                        <Route path="/aria-agent/brain" element={<AriaBrain />} />
                        <Route path="/aria-agent/weekly-recap" element={<WeeklyRecap />} />
                        <Route path="/sales-engagement" element={<SalesEngagement />} />
                        <Route path="/admin/feedback" element={<AdminFeedback />} />
                        <Route path="/master-admin" element={<MasterAdmin />} />
                        <Route path="/touchpoint-journey" element={<TouchpointJourney />} />
                        <Route path="/icps" element={<ICPManager />} />
                        <Route path="/outreach" element={<OutreachCampaigns />} />
                        <Route path="/outreach/:campaignId" element={<OutreachCampaigns />} />
                        <Route path="/ai-setup" element={<AISetupAssistant />} />
                        <Route path="/ai-setup-assistant" element={<AISetupAssistant />} />
                        <Route path="/train-aria-v2" element={<TrainAriaV2 />} />
                        <Route path="/billing/success" element={<BillingSuccess />} />
                        <Route path="/billing/cancel" element={<BillingCancel />} />
                        <Route path="*" element={<NotFound />} />
                      </Routes>
                      <UpgradeModal />
                    </Layout>
                  </ProtectedRoute>
                }
              />
            </Routes>
            {/* Mounted at root so toasts work on public routes (Login, LandingPage, Signup) too */}
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
