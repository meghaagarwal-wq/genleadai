/**
 * Login — three flows in one screen.
 *
 *   1. mode='password'     →  classic email + password JWT
 *   2. mode='email-code'   →  passwordless: email → 6-digit code → JWT
 *   3. mode='forgot'       →  forgot password: email → code → new password
 *
 * The forgot + email-code flows hit the new /api/auth/password/* and
 * /api/auth/email-code/* endpoints. All flows resolve to the same JWT shape
 * the AuthContext expects, so the rest of the app is unchanged.
 */
import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { toast } from 'sonner';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { Envelope, Lock, Eye, EyeSlash, Key, ArrowLeft, ShieldCheck } from '@phosphor-icons/react';

const API = process.env.REACT_APP_BACKEND_URL;

const Login = () => {
  const navigate = useNavigate();
  const { login, setSession } = useAuth();
  const [mode, setMode] = useState('password');  // 'password' | 'email-code' | 'forgot'

  // Shared
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Code-based steps
  const [codeSent, setCodeSent] = useState(false);
  const [code, setCode] = useState('');
  const [newPassword, setNewPassword] = useState('');

  const reset = () => {
    setError(''); setCode(''); setNewPassword(''); setCodeSent(false); setPassword('');
  };

  const switchMode = (next) => {
    reset();
    setMode(next);
  };

  // ─── Flow 1: classic password ────────────────────────────────────────
  const handlePassword = async (e) => {
    e.preventDefault();
    setError(''); setLoading(true);
    try {
      await login(email, password);
      navigate('/');
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid credentials');
    } finally { setLoading(false); }
  };

  // ─── Flow 2: passwordless email-code ─────────────────────────────────
  const requestEmailCode = async (e) => {
    e?.preventDefault?.();
    setError(''); setLoading(true);
    try {
      await axios.post(`${API}/api/auth/email-code/request`, { email });
      setCodeSent(true);
      toast.success('Check your inbox — code expires in 10 minutes.');
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not send code. Please try again.');
    } finally { setLoading(false); }
  };

  const verifyEmailCode = async (e) => {
    e.preventDefault();
    setError(''); setLoading(true);
    try {
      const { data } = await axios.post(`${API}/api/auth/email-code/verify`, { email, code });
      if (setSession) setSession(data);
      else {
        // Fallback: persist + navigate (AuthContext may not expose setSession yet)
        localStorage.setItem('token', data.token);
        localStorage.setItem('user', JSON.stringify(data.user));
      }
      toast.success('Signed in.');
      navigate('/');
      // Force a hard refresh if context didn't pick up the new token automatically
      setTimeout(() => { if (!localStorage.getItem('token')) window.location.reload(); }, 50);
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid or expired code.');
    } finally { setLoading(false); }
  };

  // ─── Flow 3: forgot password ─────────────────────────────────────────
  const requestForgot = async (e) => {
    e?.preventDefault?.();
    setError(''); setLoading(true);
    try {
      await axios.post(`${API}/api/auth/password/forgot`, { email });
      setCodeSent(true);
      toast.success('If that email is registered, a reset code is on its way.');
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not send reset code.');
    } finally { setLoading(false); }
  };

  const submitForgot = async (e) => {
    e.preventDefault();
    setError(''); setLoading(true);
    try {
      const { data } = await axios.post(`${API}/api/auth/password/reset`, { email, code, new_password: newPassword });
      if (setSession) setSession(data);
      else {
        localStorage.setItem('token', data.token);
        localStorage.setItem('user', JSON.stringify(data.user));
      }
      toast.success('Password updated. Signed in.');
      navigate('/');
      setTimeout(() => { if (!localStorage.getItem('token')) window.location.reload(); }, 50);
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid code or weak password (min 8 characters).');
    } finally { setLoading(false); }
  };

  const isCodeMode = mode !== 'password';

  return (
    <div className="min-h-screen bg-[#FAFAFA] flex items-center justify-center p-4" data-testid="login-page">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="flex justify-center mb-8">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ background: 'var(--gradient-brand)' }}>
              <span className="text-white font-bold text-xl" style={{ fontFamily: 'Plus Jakarta Sans' }}>G</span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>GenLead<span className="gradient-text">AI</span></h1>
                <span data-testid="beta-badge-login" className="px-1.5 py-[1px] rounded-[4px] text-[9px] font-bold uppercase tracking-[0.18em] text-[#B45309] border border-[#F59E0B]/50" style={{ background: 'rgba(245,158,11,0.12)' }}>Beta</span>
              </div>
              <p className="text-sm text-[#9B8AB0]">Lead Management System</p>
            </div>
          </div>
        </div>

        {/* Card */}
        <div className="bg-white border border-[#E8E0F5] rounded-2xl p-8" style={{ boxShadow: 'var(--shadow-card)' }}>
          <div className="h-1 w-16 rounded-full mb-6" style={{ background: 'var(--gradient-brand)' }}></div>

          {mode === 'password' && (
            <>
              <h2 className="text-2xl font-bold text-[#1A0A2E] mb-1" style={{ fontFamily: 'Plus Jakarta Sans' }}>Welcome back</h2>
              <p className="text-[#5A4A7A] mb-6 text-sm">Sign in to your account to continue.</p>
            </>
          )}
          {mode === 'email-code' && (
            <>
              <h2 className="text-2xl font-bold text-[#1A0A2E] mb-1" style={{ fontFamily: 'Plus Jakarta Sans' }}>Sign in with email code</h2>
              <p className="text-[#5A4A7A] mb-6 text-sm">No password needed — we'll email you a 6-digit code.</p>
            </>
          )}
          {mode === 'forgot' && (
            <>
              <h2 className="text-2xl font-bold text-[#1A0A2E] mb-1" style={{ fontFamily: 'Plus Jakarta Sans' }}>Reset your password</h2>
              <p className="text-[#5A4A7A] mb-6 text-sm">{codeSent ? 'Enter the code we emailed you and a new password.' : 'Enter your account email — we\'ll send a code.'}</p>
            </>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 text-[#DC2626] rounded-lg p-3 mb-4 text-sm" data-testid="login-error">{error}</div>
          )}

          {/* ── Password form ── */}
          {mode === 'password' && (
            <form onSubmit={handlePassword} data-testid="login-form">
              <div className="space-y-4">
                <EmailField email={email} setEmail={setEmail} />
                <PasswordField password={password} setPassword={setPassword} showPassword={showPassword} setShowPassword={setShowPassword} />
              </div>
              <button type="submit" disabled={loading} data-testid="login-submit-button"
                className="w-full mt-6 btn-gradient font-semibold py-2.5 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed text-sm" style={{ fontFamily: 'Plus Jakarta Sans' }}>
                {loading ? 'Signing in…' : 'Sign in'}
              </button>
              <div className="flex items-center justify-between mt-4 text-xs">
                <button type="button" onClick={() => switchMode('email-code')} data-testid="switch-email-code" className="text-[#7C35DC] hover:text-[#6B28C8] font-bold inline-flex items-center gap-1">
                  <Key size={11} weight="fill" /> Use email code instead
                </button>
                <button type="button" onClick={() => switchMode('forgot')} data-testid="forgot-password-link" className="text-[#5A4A7A] hover:text-[#1A0A2E] font-semibold">
                  Forgot password?
                </button>
              </div>
            </form>
          )}

          {/* ── Email code flow ── */}
          {mode === 'email-code' && !codeSent && (
            <form onSubmit={requestEmailCode} data-testid="email-code-request-form">
              <EmailField email={email} setEmail={setEmail} />
              <button type="submit" disabled={loading || !email} data-testid="send-email-code-btn"
                className="w-full mt-6 btn-gradient font-semibold py-2.5 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed text-sm" style={{ fontFamily: 'Plus Jakarta Sans' }}>
                {loading ? 'Sending…' : 'Email me a code'}
              </button>
            </form>
          )}
          {mode === 'email-code' && codeSent && (
            <form onSubmit={verifyEmailCode} data-testid="email-code-verify-form">
              <CodeBanner email={email} />
              <CodeField code={code} setCode={setCode} testid="email-code-input" />
              <button type="submit" disabled={loading || code.length !== 6} data-testid="verify-email-code-btn"
                className="w-full mt-6 btn-gradient font-semibold py-2.5 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed text-sm" style={{ fontFamily: 'Plus Jakarta Sans' }}>
                {loading ? 'Verifying…' : 'Verify & sign in'}
              </button>
              <button type="button" onClick={() => { setCodeSent(false); setCode(''); }} className="w-full mt-2 text-xs text-[#5A4A7A] hover:text-[#1A0A2E]" data-testid="resend-email-code">
                Didn't get it? Re-enter email
              </button>
            </form>
          )}

          {/* ── Forgot password flow ── */}
          {mode === 'forgot' && !codeSent && (
            <form onSubmit={requestForgot} data-testid="forgot-request-form">
              <EmailField email={email} setEmail={setEmail} />
              <button type="submit" disabled={loading || !email} data-testid="send-reset-code-btn"
                className="w-full mt-6 btn-gradient font-semibold py-2.5 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed text-sm" style={{ fontFamily: 'Plus Jakarta Sans' }}>
                {loading ? 'Sending…' : 'Send reset code'}
              </button>
            </form>
          )}
          {mode === 'forgot' && codeSent && (
            <form onSubmit={submitForgot} data-testid="forgot-reset-form">
              <CodeBanner email={email} />
              <CodeField code={code} setCode={setCode} testid="reset-code-input" />
              <div className="mt-4">
                <label className="block text-sm font-medium text-[#1A0A2E] mb-2" style={{ fontFamily: 'Plus Jakarta Sans' }}>New password</label>
                <div className="relative">
                  <Lock size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9B8AB0]" />
                  <input type={showPassword ? 'text' : 'password'} value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required minLength={8} data-testid="new-password-input"
                    className="w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] pl-10 pr-12 py-2.5 rounded-lg focus:border-[#7C35DC] focus:ring-2 focus:ring-[rgba(124,53,220,0.12)] transition-all text-sm"
                    placeholder="At least 8 characters" />
                  <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#9B8AB0] hover:text-[#7C35DC]">
                    {showPassword ? <EyeSlash size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>
              <button type="submit" disabled={loading || code.length !== 6 || newPassword.length < 8} data-testid="reset-password-btn"
                className="w-full mt-6 btn-gradient font-semibold py-2.5 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed text-sm" style={{ fontFamily: 'Plus Jakarta Sans' }}>
                {loading ? 'Updating…' : 'Reset & sign in'}
              </button>
              <button type="button" onClick={() => { setCodeSent(false); setCode(''); setNewPassword(''); }} className="w-full mt-2 text-xs text-[#5A4A7A] hover:text-[#1A0A2E]" data-testid="resend-reset-code">
                Didn't get it? Re-enter email
              </button>
            </form>
          )}

          {/* Back to password */}
          {mode !== 'password' && (
            <button type="button" onClick={() => switchMode('password')} className="mt-5 inline-flex items-center gap-1 text-xs font-bold text-[#5A4A7A] hover:text-[#7C35DC]" data-testid="back-to-password">
              <ArrowLeft size={11} weight="bold" /> Back to password sign-in
            </button>
          )}

          <div className="mt-6 text-center">
            <p className="text-[#5A4A7A] text-sm">
              Don't have an account?{' '}
              <Link to="/register" className="text-[#7C35DC] hover:text-[#6B28C8] font-semibold" data-testid="register-link">Sign up</Link>
            </p>
          </div>
        </div>

        <p className="text-[10px] text-center text-[#A0A8C0] mt-6 tracking-[0.18em] uppercase font-bold" data-testid="genleadai-footer">
          Powered by Aria · GenLeadAI
        </p>
      </div>
    </div>
  );
};

// ─── Re-usable input fields ─────────────────────────────────────────────
const EmailField = ({ email, setEmail }) => (
  <div>
    <label className="block text-sm font-medium text-[#1A0A2E] mb-2" style={{ fontFamily: 'Plus Jakarta Sans' }}>Email</label>
    <div className="relative">
      <Envelope size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9B8AB0]" />
      <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required data-testid="email-input" autoComplete="email"
        className="w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] pl-10 pr-4 py-2.5 rounded-lg focus:border-[#7C35DC] focus:ring-2 focus:ring-[rgba(124,53,220,0.12)] transition-all text-sm"
        placeholder="you@company.com" />
    </div>
  </div>
);

const PasswordField = ({ password, setPassword, showPassword, setShowPassword }) => (
  <div>
    <label className="block text-sm font-medium text-[#1A0A2E] mb-2" style={{ fontFamily: 'Plus Jakarta Sans' }}>Password</label>
    <div className="relative">
      <Lock size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9B8AB0]" />
      <input type={showPassword ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)} required data-testid="password-input" autoComplete="current-password"
        className="w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] pl-10 pr-12 py-2.5 rounded-lg focus:border-[#7C35DC] focus:ring-2 focus:ring-[rgba(124,53,220,0.12)] transition-all text-sm"
        placeholder="Enter your password" />
      <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#9B8AB0] hover:text-[#7C35DC]" data-testid="toggle-password">
        {showPassword ? <EyeSlash size={18} /> : <Eye size={18} />}
      </button>
    </div>
  </div>
);

const CodeField = ({ code, setCode, testid }) => (
  <div>
    <label className="block text-sm font-medium text-[#1A0A2E] mb-2" style={{ fontFamily: 'Plus Jakarta Sans' }}>6-digit code</label>
    <input
      type="text" inputMode="numeric" autoComplete="one-time-code" maxLength={6} required
      value={code}
      onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
      data-testid={testid}
      className="w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-4 py-3 rounded-lg focus:border-[#7C35DC] focus:ring-2 focus:ring-[rgba(124,53,220,0.12)] transition-all text-center text-2xl font-mono tracking-[0.4em] font-extrabold"
      placeholder="••••••"
    />
    <p className="text-[10px] text-[#9B8AB0] mt-1.5 inline-flex items-center gap-1"><ShieldCheck size={11} weight="fill" /> Expires in 10 minutes · 5 attempts max</p>
  </div>
);

const CodeBanner = ({ email }) => (
  <div className="bg-gradient-to-r from-[#F4F0FF] to-[#FAFAFA] border border-[#E0D4F7] rounded-lg px-3 py-2.5 text-xs mb-4 text-[#5A4A7A]" data-testid="code-sent-banner">
    Code sent to <span className="font-extrabold text-[#1A0A2E]">{email}</span>. Check your inbox + spam folder.
  </div>
);

export default Login;
