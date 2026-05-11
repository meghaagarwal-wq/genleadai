/**
 * StaleLeadAlertChip — banner on Dashboard showing stale-lead count.
 * Only renders when there are stale leads.
 */
import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../config/api';
import { Warning, ArrowRight } from '@phosphor-icons/react';

const StaleLeadAlertChip = () => {
  const [count, setCount] = useState(0);

  useEffect(() => {
    api.get('/api/health/stale-leads')
      .then((r) => setCount(r.data?.count || 0))
      .catch(() => setCount(0));
  }, []);

  if (!count) return null;

  return (
    <Link
      to="/leads?filter=stale"
      data-testid="stale-lead-alert"
      className="block bg-[#FEF3C7] border border-[#D97706]/30 rounded-xl px-5 py-3 hover:bg-[#FDE68A] transition-colors"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Warning size={20} weight="fill" className="text-[#D97706] flex-shrink-0" />
          <div>
            <div className="font-bold text-[#92400E] text-sm" style={{ fontFamily: 'Plus Jakarta Sans' }}>
              {count} lead{count > 1 ? 's have' : ' has'} gone cold
            </div>
            <div className="text-xs text-[#92400E]/80">Aria is sending re-engagement messages. Click to review.</div>
          </div>
        </div>
        <ArrowRight size={14} weight="bold" className="text-[#92400E]" />
      </div>
    </Link>
  );
};

export default StaleLeadAlertChip;
