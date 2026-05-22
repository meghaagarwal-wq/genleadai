// Iter79 — S6 enhancement: surface which workspace asset(s) Aria would lean on
// for this lead. Pulls from GET /api/aria-agent/suggested-assets/{lead_id}.
import React, { useEffect, useState } from 'react';
import { FileText, ArrowRight, Books, CurrencyInr, ChatCircleDots } from '@phosphor-icons/react';
import api from '../config/api';

const TYPE_META = {
  objection_response: { label: 'Objection response', icon: ChatCircleDots, color: 'rose' },
  pricing_doc:        { label: 'Pricing',           icon: CurrencyInr,    color: 'amber' },
  case_study:         { label: 'Case study',        icon: Books,          color: 'emerald' },
  message_template:   { label: 'Template',          icon: FileText,       color: 'indigo' },
};

export default function SuggestedAssetWidget({ leadId, contextQuery }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!leadId) return;
    setLoading(true);
    const params = contextQuery ? `?q=${encodeURIComponent(contextQuery)}` : '';
    api.get(`/api/aria-agent/suggested-assets/${leadId}${params}`)
      .then((r) => setData(r.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [leadId, contextQuery]);

  if (loading) {
    return (
      <div className="bg-white border border-slate-200 rounded-2xl p-4" data-testid="suggested-assets-loading">
        <div className="text-[10px] uppercase tracking-wider font-bold text-slate-500 mb-1">Suggested Assets</div>
        <div className="text-xs text-slate-400">Reading the lead's last message…</div>
      </div>
    );
  }
  if (!data || data.count === 0) {
    return (
      <div className="bg-white border border-slate-200 rounded-2xl p-4" data-testid="suggested-assets-empty">
        <div className="text-[10px] uppercase tracking-wider font-bold text-slate-500 mb-1">Suggested Assets</div>
        <p className="text-xs text-slate-500 italic">
          No assets match this lead's current state. Add objection responses / pricing docs / case studies under <strong>Assets</strong> to give Aria more ammo.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-gradient-to-br from-violet-50 to-indigo-50 border border-violet-200 rounded-2xl p-4" data-testid="suggested-assets-widget">
      <div className="text-[10px] uppercase tracking-wider font-bold text-violet-700 mb-2">Suggested Assets — Aria is using</div>
      <div className="space-y-2">
        {data.suggested.map((a) => {
          const meta = TYPE_META[a.asset_type] || TYPE_META.message_template;
          const Icon = meta.icon;
          return (
            <div
              key={a.id}
              data-testid={`suggested-asset-${a.id}`}
              className="bg-white border border-slate-200 rounded-lg p-2.5 flex items-start gap-2"
            >
              <Icon size={16} weight="duotone" className={`text-${meta.color}-600 flex-shrink-0 mt-0.5`} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5 flex-wrap">
                  <strong className="text-xs text-[#1A0A2E] truncate">{a.name}</strong>
                  <span className={`text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-${meta.color}-50 text-${meta.color}-700 border border-${meta.color}-200`}>{meta.label}</span>
                </div>
                <p className="text-[11px] text-slate-600 line-clamp-2 mt-0.5">{(a.content || '').slice(0, 120)}</p>
                {a.match_reason && (
                  <p className="text-[10px] text-violet-700 italic mt-1">→ {a.match_reason}</p>
                )}
              </div>
            </div>
          );
        })}
      </div>
      <a
        href="/aria-agent/assets"
        className="inline-flex items-center gap-1 mt-2 text-[10px] font-bold text-violet-700 hover:text-violet-900"
      >
        Manage assets <ArrowRight size={9} weight="bold" />
      </a>
    </div>
  );
}
