import React, { createContext, useContext, useState, useEffect } from 'react';
import api from '../config/api';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('token');
    const storedUser = localStorage.getItem('user');
    
    if (token && storedUser) {
      setUser(JSON.parse(storedUser));
    }
    setLoading(false);
  }, []);

  const login = async (email, password) => {
    const response = await api.post('/api/auth/login', { email, password });
    const { token, user } = response.data;
    
    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify(user));
    setUser(user);
    
    return user;
  };

  const register = async (email, password, full_name) => {
    const response = await api.post('/api/auth/register', { email, password, full_name });
    const { token, user } = response.data;
    
    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify(user));
    setUser(user);
    
    return user;
  };

  // Multi-tenant self-service signup: creates user + tenant + owner membership.
  // Returns { user, tenant }. Tenant is fresh → onboarding required.
  const signup = async (email, password, full_name, workspace_name) => {
    const response = await api.post('/api/auth/signup', { email, password, full_name, workspace_name });
    const { token, user, tenant } = response.data;

    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify(user));
    if (tenant) localStorage.setItem('active_tenant', JSON.stringify(tenant));
    setUser(user);

    return { user, tenant };
  };

  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    localStorage.removeItem('active_tenant');
    setUser(null);
  };

  // Used by passwordless flows (email-code login + password reset) — the
  // caller already has the {token, user} payload from the backend; we just
  // need to mirror it into localStorage + state.
  const setSession = ({ token, user }) => {
    if (!token || !user) return;
    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify(user));
    setUser(user);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, signup, logout, setSession }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};