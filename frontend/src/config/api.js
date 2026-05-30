import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_BACKEND_URL;

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    // Multi-tenant: forward active tenant id so backend can scope data.
    try {
      const activeTenant = localStorage.getItem('active_tenant');
      if (activeTenant) {
        const parsed = JSON.parse(activeTenant);
        if (parsed?.id) config.headers['X-Tenant-Id'] = parsed.id;
      }
    } catch (e) { /* ignore parse errors */ }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // iter140 — guard the hard-redirect so it doesn't fire on:
    //   (a) the login request itself (Login.js shows its own error toast/inline)
    //   (b) when the user is already on /login (would wipe React error state)
    //   (c) public endpoints that may transiently 401 during onboarding
    const url = error.config?.url || '';
    const onLogin = typeof window !== 'undefined' && window.location.pathname === '/login';
    const isLoginCall = url.endsWith('/api/auth/login') || url.includes('/api/auth/email-code/') || url.includes('/api/auth/password/');
    if (error.response?.status === 401 && !isLoginCall && !onLogin) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default api;