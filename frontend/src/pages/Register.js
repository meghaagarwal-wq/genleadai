import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Envelope, Lock, User, Eye, EyeSlash } from '@phosphor-icons/react';

const Register = () => {
  const navigate = useNavigate();
  const { register } = useAuth();
  const [formData, setFormData] = useState({ full_name: '', email: '', password: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await register(formData.email, formData.password, formData.full_name);
      navigate('/');
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#FAFAFA] flex items-center justify-center p-4">
      <div className="w-full max-w-md">
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

        <div className="bg-white border border-[#E8E0F5] rounded-2xl p-8" style={{ boxShadow: 'var(--shadow-card)' }}>
          <div className="h-1 w-16 rounded-full mb-6" style={{ background: 'var(--gradient-brand)' }}></div>
          <h2 className="text-2xl font-bold text-[#1A0A2E] mb-1" style={{ fontFamily: 'Plus Jakarta Sans' }}>Create account</h2>
          <p className="text-[#5A4A7A] mb-6 text-sm">Get started with GenLeadAI</p>

          {error && <div className="bg-red-50 border border-red-200 text-[#DC2626] rounded-lg p-3 mb-4 text-sm">{error}</div>}

          <form onSubmit={handleSubmit} data-testid="register-form">
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-[#1A0A2E] mb-2" style={{ fontFamily: 'Plus Jakarta Sans' }}>Full Name</label>
                <div className="relative">
                  <User size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9B8AB0]" />
                  <input type="text" value={formData.full_name} onChange={(e) => setFormData({...formData, full_name: e.target.value})} required data-testid="fullname-input"
                    className="w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] pl-10 pr-4 py-2.5 rounded-lg focus:border-[#7C35DC] focus:ring-2 focus:ring-[rgba(124,53,220,0.12)] transition-all text-sm" placeholder="John Doe" />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-[#1A0A2E] mb-2" style={{ fontFamily: 'Plus Jakarta Sans' }}>Email</label>
                <div className="relative">
                  <Envelope size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9B8AB0]" />
                  <input type="email" value={formData.email} onChange={(e) => setFormData({...formData, email: e.target.value})} required data-testid="email-input"
                    className="w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] pl-10 pr-4 py-2.5 rounded-lg focus:border-[#7C35DC] focus:ring-2 focus:ring-[rgba(124,53,220,0.12)] transition-all text-sm" placeholder="you@company.com" />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-[#1A0A2E] mb-2" style={{ fontFamily: 'Plus Jakarta Sans' }}>Password</label>
                <div className="relative">
                  <Lock size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9B8AB0]" />
                  <input type={showPassword ? 'text' : 'password'} value={formData.password} onChange={(e) => setFormData({...formData, password: e.target.value})} required data-testid="password-input"
                    className="w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] pl-10 pr-12 py-2.5 rounded-lg focus:border-[#7C35DC] focus:ring-2 focus:ring-[rgba(124,53,220,0.12)] transition-all text-sm" placeholder="Create a strong password" />
                  <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#9B8AB0] hover:text-[#7C35DC] transition-colors">
                    {showPassword ? <EyeSlash size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>
            </div>
            <button type="submit" disabled={loading} data-testid="register-submit-button"
              className="w-full mt-6 btn-gradient font-semibold py-2.5 rounded-lg disabled:opacity-50 text-sm" style={{ fontFamily: 'Plus Jakarta Sans' }}>
              {loading ? 'Creating account...' : 'Create account'}
            </button>
          </form>

          <div className="mt-6 text-center">
            <p className="text-[#5A4A7A] text-sm">
              Already have an account?{' '}
              <Link to="/login" className="text-[#7C35DC] hover:text-[#6B28C8] font-semibold" data-testid="login-link">Sign in</Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Register;
