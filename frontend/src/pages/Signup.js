import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Buildings, Envelope, Lock, User, Eye, EyeSlash, Sparkle } from '@phosphor-icons/react';

const Signup = () => {
  const navigate = useNavigate();
  const { signup } = useAuth();
  const [form, setForm] = useState({ workspace_name: '', full_name: '', email: '', password: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handle = async (e) => {
    e.preventDefault();
    setError('');
    if (form.password.length < 8) { setError('Password must be at least 8 characters.'); return; }
    if (!form.workspace_name.trim() || !form.full_name.trim()) { setError('All fields are required.'); return; }
    setLoading(true);
    try {
      await signup(form.email, form.password, form.full_name, form.workspace_name);
      navigate('/onboarding');
    } catch (err) {
      setError(err.response?.data?.detail || 'Signup failed. Please try again.');
    } finally { setLoading(false); }
  };

  const inputCls = "w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] pl-10 pr-3 py-2.5 rounded-lg text-sm focus:border-[#7C35DC] focus:ring-2 focus:ring-[#7C35DC]/15 outline-none transition";

  return (
    <div className="min-h-screen flex items-center justify-center p-4" style={{ background: 'linear-gradient(135deg, #FAFAFA 0%, #F4F0FF 100%)' }} data-testid="signup-page">
      <div className="w-full max-w-md">
        <div className="flex justify-center mb-6">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #4C1D95 0%, #7C35DC 100%)' }}>
              <Sparkle size={20} weight="fill" className="text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-[#1A0A2E]">GenLeadAI <span style={{ color: '#7C35DC' }}>Aria</span></h1>
              <p className="text-[11px] text-[#9B8AB0] -mt-0.5">Your first AI sales hire</p>
            </div>
          </div>
        </div>

        <div className="bg-white border border-[#E8E0F5] rounded-2xl p-7 shadow-[0_24px_64px_-12px_rgba(76,29,149,0.18)]">
          <div className="h-1 w-12 rounded-full mb-5" style={{ background: 'linear-gradient(90deg, #4C1D95, #7C35DC)' }} />
          <h2 className="text-2xl font-bold text-[#1A0A2E]">Create your workspace</h2>
          <p className="text-[#5A4A7A] mb-5 text-sm">Spin up Aria in 60 seconds. No credit card.</p>

          {error && (
            <div className="bg-red-50 border border-red-200 text-[#DC2626] rounded-lg px-3 py-2 mb-4 text-sm" data-testid="signup-error">
              {error}
            </div>
          )}

          <form onSubmit={handle} className="space-y-3" data-testid="signup-form">
            <div className="relative">
              <Buildings size={16} className="absolute left-3 top-3.5 text-[#9B8AB0]" />
              <input data-testid="signup-workspace-name" type="text" placeholder="Workspace name (e.g. Acme Corp)"
                value={form.workspace_name} onChange={(e) => setForm({ ...form, workspace_name: e.target.value })}
                className={inputCls} required />
            </div>

            <div className="relative">
              <User size={16} className="absolute left-3 top-3.5 text-[#9B8AB0]" />
              <input data-testid="signup-full-name" type="text" placeholder="Your full name"
                value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                className={inputCls} required />
            </div>

            <div className="relative">
              <Envelope size={16} className="absolute left-3 top-3.5 text-[#9B8AB0]" />
              <input data-testid="signup-email" type="email" placeholder="Work email"
                value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
                className={inputCls} required />
            </div>

            <div className="relative">
              <Lock size={16} className="absolute left-3 top-3.5 text-[#9B8AB0]" />
              <input data-testid="signup-password" type={showPassword ? 'text' : 'password'} placeholder="Password (min 8 chars)"
                value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })}
                className={inputCls} minLength={8} required />
              <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-3 text-[#9B8AB0] hover:text-[#7C35DC]">
                {showPassword ? <EyeSlash size={16} /> : <Eye size={16} />}
              </button>
            </div>

            <button type="submit" disabled={loading} data-testid="signup-submit"
              className="w-full mt-2 py-3 rounded-lg text-white font-bold text-sm tracking-wide disabled:opacity-50"
              style={{ background: 'linear-gradient(135deg, #4C1D95 0%, #7C35DC 100%)' }}>
              {loading ? 'Creating workspace…' : 'Create workspace & start'}
            </button>
          </form>

          <p className="text-xs text-[#5A4A7A] mt-5 text-center">
            Already have an account? <Link to="/login" className="font-bold text-[#7C35DC] hover:underline" data-testid="signup-login-link">Sign in</Link>
          </p>
        </div>

        <p className="text-[11px] text-center text-[#9B8AB0] mt-5">
          By signing up, you agree to our Terms and Privacy Policy.
        </p>
      </div>
    </div>
  );
};

export default Signup;
