import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import api from '../config/api';
import { useAuth } from '../context/AuthContext';
import { Buildings, Envelope, Lock, User, Sparkle, ShieldCheck, Warning, ArrowRight } from '@phosphor-icons/react';

/**
 * Public invite landing at `/invite/<token>`.
 *
 * Fetches invite details (workspace name, role, inviter), then asks the
 * recipient to either:
 *   - Sign in (if they already have an account → membership added on accept)
 *   - Create an account (new user → user + membership created on accept)
 *
 * On success → token + active_tenant stored, redirect to dashboard.
 */
const InviteAccept = () => {
  const { token } = useParams();
  const navigate = useNavigate();
  const { setUserManually } = useAuth() || {};
  const [invite, setInvite] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  // Form state
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  useEffect(() => {
    let alive = true;
    api.get(`/api/public/invitations/${token}`)
      .then((r) => {
        if (!alive) return;
        setInvite(r.data);
        if (r.data?.email_hint) setEmail(r.data.email_hint);
      })
      .catch((e) => {
        if (!alive) return;
        const msg = e.response?.data?.detail || 'This invite link is no longer valid.';
        setError(msg);
      })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [token]);

  const submit = async (e) => {
    e?.preventDefault?.();
    setSubmitError(null);
    if (password.length < 8) { setSubmitError('Password must be at least 8 characters.'); return; }
    if (!fullName.trim()) { setSubmitError('Please enter your name.'); return; }
    setSubmitting(true);
    try {
      const res = await api.post('/api/public/invitations/accept', {
        token, email, password, full_name: fullName,
      });
      const { token: jwt, user, tenant } = res.data;
      localStorage.setItem('token', jwt);
      localStorage.setItem('user', JSON.stringify(user));
      if (tenant) localStorage.setItem('active_tenant', JSON.stringify(tenant));
      // If AuthContext exposes a setter, use it; otherwise hard-reload.
      if (typeof setUserManually === 'function') setUserManually(user);
      // Hard reload guarantees ProtectedRoute picks up the new token + tenant.
      window.location.replace('/');
    } catch (err) {
      setSubmitError(err.response?.data?.detail || 'Could not accept invite.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return <Center><div className="text-[#5A4A7A]">Checking your invite…</div></Center>;
  }

  if (error) {
    return (
      <Center>
        <div className="w-full max-w-md bg-white border border-[#E8E0F5] rounded-2xl p-8 text-center" data-testid="invite-error">
          <div className="w-12 h-12 rounded-full mx-auto mb-3 flex items-center justify-center bg-[#FEE2E2]">
            <Warning size={20} weight="fill" className="text-[#DC2626]" />
          </div>
          <h2 className="text-xl font-bold text-[#1A0A2E]">This invite isn't usable</h2>
          <p className="text-sm text-[#5A4A7A] mt-2">{error}</p>
          <Link to="/signup" data-testid="invite-fallback-signup"
            className="inline-flex items-center gap-1.5 mt-5 px-4 py-2 rounded-lg text-white font-bold text-sm"
            style={{ background: 'linear-gradient(135deg, #4C1D95, #7C35DC)' }}
          >
            Create your own workspace <ArrowRight size={13} weight="bold" />
          </Link>
        </div>
      </Center>
    );
  }

  return (
    <Center>
      <div className="w-full max-w-md" data-testid="invite-accept-page">
        {/* Workspace badge */}
        <div className="bg-white border border-[#E8E0F5] rounded-2xl p-7 shadow-[0_24px_64px_-12px_rgba(76,29,149,0.18)]">
          <div className="text-center mb-5">
            <div
              className="w-12 h-12 rounded-xl mx-auto mb-3 flex items-center justify-center"
              style={{ background: 'linear-gradient(135deg, #4C1D95 0%, #7C35DC 100%)' }}
            >
              <Sparkle size={20} weight="fill" className="text-white" />
            </div>
            <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-[#7C35DC]">YOU'VE BEEN INVITED</div>
            <h1 className="text-2xl font-bold text-[#1A0A2E] mt-1" style={{ fontFamily: 'Space Grotesk, Inter' }}>
              Join <span style={{ color: '#7C35DC' }}>{invite.tenant_name}</span>
            </h1>
            <p className="text-sm text-[#5A4A7A] mt-1">
              {invite.invited_by_name} invited you as a{' '}
              <span className="font-bold text-[#7C35DC]">{invite.role}</span>.
            </p>
          </div>

          {submitError && (
            <div className="bg-red-50 border border-red-200 text-[#DC2626] rounded-lg px-3 py-2 mb-4 text-sm" data-testid="invite-submit-error">
              {submitError}
            </div>
          )}

          <form onSubmit={submit} className="space-y-3" data-testid="invite-form">
            <Field icon={User}>
              <input
                data-testid="invite-full-name" type="text" placeholder="Your full name" required
                value={fullName} onChange={(e) => setFullName(e.target.value)} className={inputCls}
              />
            </Field>
            <Field icon={Envelope}>
              <input
                data-testid="invite-email-input" type="email" placeholder="Work email" required
                value={email} onChange={(e) => setEmail(e.target.value)} className={inputCls}
                disabled={!!invite.email_hint}
              />
            </Field>
            <Field icon={Lock}>
              <input
                data-testid="invite-password" type="password" placeholder="Set a password (min 8 chars)" required minLength={8}
                value={password} onChange={(e) => setPassword(e.target.value)} className={inputCls}
              />
            </Field>

            <button type="submit" disabled={submitting}
              data-testid="invite-accept-btn"
              className="w-full mt-2 py-3 rounded-lg text-white font-bold text-sm tracking-wide disabled:opacity-50"
              style={{ background: 'linear-gradient(135deg, #4C1D95 0%, #7C35DC 100%)' }}
            >
              {submitting ? 'Joining…' : `Join ${invite.tenant_name}`}
            </button>
          </form>

          <div className="flex items-center justify-center gap-1.5 mt-4 text-[10px] text-[#9B8AB0]">
            <ShieldCheck size={11} weight="fill" />
            <span>Already have an account? Use the same email + your existing password to merge.</span>
          </div>
        </div>

        <p className="text-[11px] text-center text-[#9B8AB0] mt-5">
          By joining, you agree to our Terms and Privacy Policy.
        </p>
      </div>
    </Center>
  );
};

const Center = ({ children }) => (
  <div className="min-h-screen flex items-center justify-center p-4" style={{ background: 'linear-gradient(135deg, #FAFAFA 0%, #F4F0FF 100%)' }}>
    {children}
  </div>
);

const inputCls = "w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] pl-10 pr-3 py-2.5 rounded-lg text-sm focus:border-[#7C35DC] focus:ring-2 focus:ring-[#7C35DC]/15 outline-none transition disabled:bg-[#F4F0FF] disabled:cursor-not-allowed";

const Field = ({ icon: Icon, children }) => (
  <div className="relative">
    <Icon size={16} className="absolute left-3 top-3.5 text-[#9B8AB0]" />
    {children}
  </div>
);

export default InviteAccept;
