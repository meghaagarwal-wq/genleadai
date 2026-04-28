import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
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
import Layout from './components/Layout';
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
        <Router>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
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
                      <Route path="/campaigns" element={<Campaigns />} />
                      <Route path="/analytics" element={<Analytics />} />
                      <Route path="/aria" element={<AriaFeed />} />
                      <Route path="/aria/analytics" element={<AriaAnalytics />} />
                      <Route path="/audit-log" element={<AuditLog />} />
                      <Route path="/settings" element={<Settings />} />
                    </Routes>
                  </Layout>
                </ProtectedRoute>
              }
            />
          </Routes>
        </Router>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;