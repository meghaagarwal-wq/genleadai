import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import api from '../config/api';
import { useAuth } from './AuthContext';

const PlanContext = createContext(null);

export const PlanProvider = ({ children }) => {
  const { user } = useAuth();
  const [planId, setPlanId] = useState('starter');
  const [planName, setPlanName] = useState('ARIA Starter');
  const [features, setFeatures] = useState({});
  const [loading, setLoading] = useState(true);
  const [allPlans, setAllPlans] = useState([]);
  const [upgrade, setUpgrade] = useState({ open: false, featureKey: null, targetPlan: null });

  const refreshPlan = useCallback(async () => {
    if (!user) { setLoading(false); return; }
    try {
      const [curRes, allRes] = await Promise.all([
        api.get('/api/billing/current-plan'),
        api.get('/api/billing/plans'),
      ]);
      setPlanId(curRes.data?.plan_id || 'starter');
      setPlanName(curRes.data?.name || 'ARIA Starter');
      setFeatures(curRes.data?.features || {});
      setAllPlans(allRes.data?.plans || []);
    } catch (err) {
      console.error('Plan fetch failed', err);
    } finally { setLoading(false); }
  }, [user]);

  useEffect(() => { refreshPlan(); }, [refreshPlan]);

  const hasFeature = useCallback((key) => !!features[key], [features]);

  const requestUpgrade = useCallback(async (targetPlan, featureKey, note) => {
    try {
      await api.post('/api/billing/request-upgrade', { target_plan_id: targetPlan, feature_key: featureKey, note: note || '' });
      return { ok: true };
    } catch (err) {
      return { ok: false, error: err?.response?.data?.detail || 'Request failed' };
    }
  }, []);

  // Default target plan: lowest tier that unlocks the feature
  const recommendedPlanForFeature = useCallback((featureKey) => {
    const order = ['starter', 'growth', 'pro', 'custom'];
    for (const pid of order) {
      const plan = allPlans.find(p => p.id === pid);
      if (plan?.features?.[featureKey]) return pid;
    }
    return 'pro';
  }, [allPlans]);

  const openUpgrade = useCallback((featureKey, targetPlan) => {
    const target = targetPlan || recommendedPlanForFeature(featureKey) || 'pro';
    setUpgrade({ open: true, featureKey, targetPlan: target });
  }, [recommendedPlanForFeature]);

  const closeUpgrade = useCallback(() => setUpgrade({ open: false, featureKey: null, targetPlan: null }), []);

  return (
    <PlanContext.Provider value={{ planId, planName, features, loading, allPlans, hasFeature, requestUpgrade, openUpgrade, closeUpgrade, upgrade, refreshPlan }}>
      {children}
    </PlanContext.Provider>
  );
};

export const usePlan = () => {
  const ctx = useContext(PlanContext);
  if (!ctx) throw new Error('usePlan must be used within PlanProvider');
  return ctx;
};
