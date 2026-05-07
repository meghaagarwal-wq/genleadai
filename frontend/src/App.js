import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { PlanProvider } from './context/PlanContext';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import LeadInbox from './pages/LeadInbox';
import LeadDetail from './pages/LeadDetail';
import Pipeline from './pages/Pipeline';
import Campaigns from './pages/Campaigns';
import Analytics from './pages/Analytics';
import Settings from './pages/Settings';
import AriaFeed from './pages/AriaFeed';
import AriaAnalytics from './pages/AriaAnalytics';
import YourFiveToday from './pages/YourFiveToday';
import SleepingLeads from './pages/SleepingLeads';
import AuditLog from './pages/AuditLog';
import OnboardingWizard from './pages/OnboardingWizard';
import Billing from './pages/Billing';
import FollowUps from './pages/FollowUps';
import AIAssistant from './pages/AIAssistant';
import Integrations from './pages/Integrations';
import TrainAria from './pages/TrainAria';
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
import './App.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0A0A0A]">
        <div className="text-[#A3A3A3]">Loading...</div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return children;
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <PlanProvider>
          <Router>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />

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
              <Route
                path="/onboarding"
                element={
                  <ProtectedRoute>
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
                        <Route path="/your-5-today" element={<YourFiveToday />} />
                        <Route path="/leads" element={<LeadInbox />} />
                        <Route path="/leads/:id" element={<LeadDetail />} />
                        <Route path="/sleeping-leads" element={<SleepingLeads />} />
                        <Route path="/pipeline" element={<Pipeline />} />
                        <Route path="/follow-ups" element={<FollowUps />} />
                        <Route path="/ai-assistant" element={<AIAssistant />} />
                        <Route path="/integrations" element={<Integrations />} />
                        <Route path="/campaigns" element={<Campaigns />} />
                        <Route path="/reports" element={<Analytics />} />
                        <Route path="/analytics" element={<Analytics />} />
                        <Route path="/aria" element={<AriaFeed />} />
                        <Route path="/aria/analytics" element={<AriaAnalytics />} />
                        <Route path="/audit-log" element={<AuditLog />} />
                        <Route path="/billing" element={<Billing />} />
                        <Route path="/settings" element={<Settings />} />
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
                      </Routes>
                      <UpgradeModal />
                    </Layout>
                  </ProtectedRoute>
                }
              />
            </Routes>
          </Router>
        </PlanProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
