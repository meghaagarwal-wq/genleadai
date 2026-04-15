import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Envelope, Lock, User, Eye, EyeSlash } from '@phosphor-icons/react';

const Register = () => {
  const navigate = useNavigate();
  const { register } = useAuth();
  const [formData, setFormData] = useState({
    full_name: '',
    email: '',
    password: '',
  });
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
    <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="flex justify-center mb-8">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-[#0055FF] rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-xl">GL</span>
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">GenLeadAI</h1>
              <p className="text-sm text-[#737373]">Lead Management System</p>
            </div>
          </div>
        </div>

        <div className="bg-[#141414] border border-[#262626] rounded-lg p-8">
          <h2 className="text-2xl font-bold text-white mb-2">Create account</h2>
          <p className="text-[#A3A3A3] mb-6">Get started with GenLeadAI</p>

          {error && (
            <div className="bg-[#FF3B30]/10 border border-[#FF3B30]/30 text-[#FF3B30] rounded-md p-3 mb-4 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} data-testid="register-form">
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-[#F5F5F5] mb-2">
                  Full Name
                </label>
                <div className="relative">
                  <User
                    size={20}
                    className="absolute left-3 top-1/2 -translate-y-1/2 text-[#737373]"
                  />
                  <input
                    type="text"
                    value={formData.full_name}
                    onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                    required
                    data-testid="fullname-input"
                    className="w-full bg-[#0A0A0A] border border-[#262626] text-white pl-10 pr-4 py-2.5 rounded-md focus:border-[#0055FF] focus:ring-1 focus:ring-[#0055FF] transition-all"
                    placeholder="John Doe"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-[#F5F5F5] mb-2">
                  Email
                </label>
                <div className="relative">
                  <Envelope
                    size={20}
                    className="absolute left-3 top-1/2 -translate-y-1/2 text-[#737373]"
                  />
                  <input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    required
                    data-testid="email-input"
                    className="w-full bg-[#0A0A0A] border border-[#262626] text-white pl-10 pr-4 py-2.5 rounded-md focus:border-[#0055FF] focus:ring-1 focus:ring-[#0055FF] transition-all"
                    placeholder="you@company.com"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-[#F5F5F5] mb-2">
                  Password
                </label>
                <div className="relative">
                  <Lock
                    size={20}
                    className="absolute left-3 top-1/2 -translate-y-1/2 text-[#737373]"
                  />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    required
                    data-testid="password-input"
                    className="w-full bg-[#0A0A0A] border border-[#262626] text-white pl-10 pr-12 py-2.5 rounded-md focus:border-[#0055FF] focus:ring-1 focus:ring-[#0055FF] transition-all"
                    placeholder="Create a strong password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[#737373] hover:text-white transition-colors"
                  >
                    {showPassword ? <EyeSlash size={20} /> : <Eye size={20} />}
                  </button>
                </div>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              data-testid="register-submit-button"
              className="w-full mt-6 bg-[#0055FF] text-white font-medium py-2.5 rounded-md hover:bg-[#0044CC] transition-colors disabled:opacity-50"
            >
              {loading ? 'Creating account...' : 'Create account'}
            </button>
          </form>

          <div className="mt-6 text-center">
            <p className="text-[#A3A3A3] text-sm">
              Already have an account?{' '}
              <Link
                to="/login"
                className="text-[#0055FF] hover:text-[#0044CC] font-medium"
                data-testid="login-link"
              >
                Sign in
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Register;