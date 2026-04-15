import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Envelope, Lock, Eye, EyeSlash } from '@phosphor-icons/react';

const Login = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email, password);
      navigate('/');
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid credentials');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#FAFAFA] flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="flex justify-center mb-8">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ background: 'var(--gradient-brand)' }}>
              <span className="text-white font-bold text-xl" style={{ fontFamily: 'Plus Jakarta Sans' }}>G</span>
            </div>
            <div>
              <h1 className="text-2xl font-bold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>GenLead<span className="gradient-text">AI</span></h1>
              <p className="text-sm text-[#9B8AB0]">Lead Management System</p>
            </div>
          </div>
        </div>

        {/* Card */}
        <div className="bg-white border border-[#E8E0F5] rounded-2xl p-8" style={{ boxShadow: 'var(--shadow-card)' }}>
          {/* Purple accent line */}
          <div className="h-1 w-16 rounded-full mb-6" style={{ background: 'var(--gradient-brand)' }}></div>
          <h2 className="text-2xl font-bold text-[#1A0A2E] mb-1" style={{ fontFamily: 'Plus Jakarta Sans' }}>Welcome back</h2>
          <p className="text-[#5A4A7A] mb-6 text-sm">Sign in to your account to continue</p>

          {error && (
            <div className="bg-red-50 border border-red-200 text-[#DC2626] rounded-lg p-3 mb-4 text-sm" data-testid="login-error">{error}</div>
          )}

          <form onSubmit={handleSubmit} data-testid="login-form">
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-[#1A0A2E] mb-2" style={{ fontFamily: 'Plus Jakarta Sans' }}>Email</label>
                <div className="relative">
                  <Envelope size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9B8AB0]" />
                  <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required data-testid="email-input"
                    className="w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] pl-10 pr-4 py-2.5 rounded-lg focus:border-[#7C35DC] focus:ring-2 focus:ring-[rgba(124,53,220,0.12)] transition-all text-sm"
                    placeholder="you@company.com" />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-[#1A0A2E] mb-2" style={{ fontFamily: 'Plus Jakarta Sans' }}>Password</label>
                <div className="relative">
                  <Lock size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9B8AB0]" />
                  <input type={showPassword ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)} required data-testid="password-input"
                    className="w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] pl-10 pr-12 py-2.5 rounded-lg focus:border-[#7C35DC] focus:ring-2 focus:ring-[rgba(124,53,220,0.12)] transition-all text-sm"
                    placeholder="Enter your password" />
                  <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#9B8AB0] hover:text-[#7C35DC] transition-colors" data-testid="toggle-password">
                    {showPassword ? <EyeSlash size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>
            </div>
            <button type="submit" disabled={loading} data-testid="login-submit-button"
              className="w-full mt-6 btn-gradient font-semibold py-2.5 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed text-sm"
              style={{ fontFamily: 'Plus Jakarta Sans' }}>
              {loading ? 'Signing in...' : 'Sign in'}
            </button>
          </form>

          <div className="mt-6 text-center">
            <p className="text-[#5A4A7A] text-sm">
              Don't have an account?{' '}
              <Link to="/register" className="text-[#7C35DC] hover:text-[#6B28C8] font-semibold" data-testid="register-link">Sign up</Link>
            </p>
          </div>

          <div className="mt-6 pt-6 border-t border-[#E8E0F5]">
            <p className="text-xs text-[#9B8AB0] text-center mb-1.5">Demo Account:</p>
            <p className="text-xs text-[#5A4A7A] text-center font-mono">admin@demo.com / Demo1234!</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;
