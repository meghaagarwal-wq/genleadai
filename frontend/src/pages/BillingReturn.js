import React, { useEffect, useState } from 'react';
import { useLocation, Link, useNavigate } from 'react-router-dom';
import { Check, ArrowClockwise, House, Crown, X } from '@phosphor-icons/react';
import { toast } from 'sonner';
import api from '../config/api';

function useSessionId() {
  const { search } = useLocation();
  return new URLSearchParams(search).get('session_id');
}

export function BillingSuccess() {
  const sessionId = useSessionId();
  const navigate = useNavigate();
  const [status, setStatus] = useState({ payment_status: 'pending', plan_target: null, plan_applied: false });
  const [attempts, setAttempts] = useState(0);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const r = await api.get(`/api/billing/checkout/status/${sessionId}`);
        if (cancelled) return;
        setStatus(r.data);
        if (r.data.payment_status === 'paid' || r.data.status === 'expired') {
          setDone(true);
          if (r.data.payment_status === 'paid') {
            toast.success(`Plan upgraded to ${(r.data.plan_target || '').toUpperCase()}`);
          }
          return;
        }
        if (attempts < 8) {
          setAttempts((a) => a + 1);
          setTimeout(poll, 2000);
        } else {
          setDone(true);
        }
      } catch (e) {
        if (!cancelled) setDone(true);
      }
    };
    poll();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const paid = status.payment_status === 'paid';

  return (
    <div data-testid="billing-success-page" className="min-h-[70vh] flex items-center justify-center px-6">
      <div className="max-w-md w-full bg-white border border-slate-200 rounded-3xl p-10 text-center shadow-sm">
        <div className={`inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-5 ${paid ? 'bg-gradient-to-br from-emerald-500 to-teal-600 text-white' : 'bg-slate-100 text-slate-500'}`}>
          {paid ? <Check size={32} weight="bold" /> : <ArrowClockwise size={32} weight="bold" className="animate-spin" />}
        </div>
        <h1 className="text-2xl font-semibold text-slate-900 mb-2">
          {paid ? 'Plan upgraded — welcome aboard' : done ? 'Payment status pending' : 'Confirming your payment…'}
        </h1>
        <p className="text-slate-600 text-sm mb-6">
          {paid
            ? `You're now on the ${(status.plan_target || '').toUpperCase()} plan. All new limits are live.`
            : done
            ? "We couldn't confirm payment automatically. Check your email or contact support."
            : 'This usually takes a couple of seconds.'}
        </p>
        <Link
          to="/"
          data-testid="billing-success-home-btn"
          className="inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-slate-900 text-white text-sm font-medium hover:bg-slate-800"
          onClick={() => navigate('/')}
        >
          <House size={16} weight="bold" /> Back to Aria
        </Link>
      </div>
    </div>
  );
}

export function BillingCancel() {
  return (
    <div data-testid="billing-cancel-page" className="min-h-[70vh] flex items-center justify-center px-6">
      <div className="max-w-md w-full bg-white border border-slate-200 rounded-3xl p-10 text-center shadow-sm">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-slate-100 text-slate-500 mb-5">
          <X size={32} weight="bold" />
        </div>
        <h1 className="text-2xl font-semibold text-slate-900 mb-2">Checkout cancelled</h1>
        <p className="text-slate-600 text-sm mb-6">No card was charged. Want to upgrade later? Re-open the upgrade modal anytime.</p>
        <Link
          to="/"
          className="inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-slate-900 text-white text-sm font-medium hover:bg-slate-800"
        >
          <Crown size={16} weight="bold" /> Back to dashboard
        </Link>
      </div>
    </div>
  );
}
