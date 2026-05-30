/**
 * /apply/thank-you — Personalised confirmation page (V4, iter140).
 *
 * Picks up ?id=app_xxx from the redirect after a successful POST /api/applications
 * and fetches name + company from the public confirm endpoint so the page
 * greets the applicant by name.
 */
import React, { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

const ApplyThankYou = () => {
  const [params] = useSearchParams();
  const id = params.get('id');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(!!id);

  useEffect(() => {
    if (!id) { setLoading(false); return; }
    axios
      .get(`${API}/api/applications/${id}/confirm`)
      .then((r) => setData(r.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [id]);

  return (
    <div className="min-h-screen bg-[#FAFAFA] flex flex-col" data-testid="apply-thank-you-page">
      <header className="border-b border-[#E8E0F5] bg-white">
        <div className="mx-auto w-full max-w-5xl px-4 h-14 flex items-center">
          <Link to="/" className="text-base font-extrabold tracking-tight" style={{
            background: 'linear-gradient(90deg, #7C35DC, #E2B96F)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          }} data-testid="thanks-logo-home">
            ARIA by GenLeadAI
          </Link>
        </div>
      </header>

      <main className="flex-1 flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-xl bg-white border border-[#E8E0F5] rounded-2xl p-8 md:p-10 text-center" style={{ boxShadow: '0 12px 40px rgba(26,10,46,0.08)' }}>
          {/* Checkmark badge */}
          <div className="mx-auto mb-6 w-16 h-16 rounded-full flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #7C35DC 0%, #C044E0 100%)' }}>
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </div>

          <h1 className="text-3xl md:text-4xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid="thanks-heading">
            Application received
          </h1>

          {loading ? (
            <p className="text-[#5A4A7A] mt-4 text-sm">Loading…</p>
          ) : data ? (
            <>
              <p className="text-[#5A4A7A] mt-4 text-base leading-relaxed">
                Thanks, <span className="font-bold text-[#1A0A2E]" data-testid="thanks-applicant-name">{data.full_name}</span>.
                We've got everything we need from <span className="font-bold text-[#1A0A2E]" data-testid="thanks-company-name">{data.company_name}</span>.
              </p>
              <p className="text-[#5A4A7A] mt-4 text-sm leading-relaxed">
                We review every application personally and will be in touch within <strong className="text-[#1A0A2E]">48 hours</strong> if we see a strong fit.
              </p>
            </>
          ) : (
            <p className="text-[#5A4A7A] mt-4 text-sm leading-relaxed">
              Thanks for applying. We review every application personally and will be in touch within <strong className="text-[#1A0A2E]">48 hours</strong> if we see a strong fit.
            </p>
          )}

          <div className="mt-8 flex flex-col sm:flex-row gap-3 justify-center">
            <Link to="/demo" className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-full text-sm font-extrabold text-white transition-all hover:opacity-90"
              style={{ background: 'linear-gradient(90deg, #7C35DC 0%, #C044E0 100%)' }}
              data-testid="thanks-see-demo-btn"
            >
              See ARIA in action →
            </Link>
          </div>

          <p className="text-xs text-[#9B8AB0] mt-8">
            While you wait, watch the demo — it'll give you a feel for exactly what ARIA does inside your pipeline.
          </p>
        </div>
      </main>
    </div>
  );
};

export default ApplyThankYou;
