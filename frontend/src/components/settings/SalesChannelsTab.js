import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { FloppyDisk, Megaphone } from '@phosphor-icons/react';
import api from '../../config/api';
import SalesChannelsPicker from '../onboarding/SalesChannelsPicker';

/**
 * Settings → Sales Channels — Edit channel preferences post-onboarding.
 * Reads /api/tenant/sales-channels on mount, PUT on save.
 */
export default function SalesChannelsTab() {
  const [value, setValue] = useState({
    selected_channels: [], priority_order: [],
    conversation_style: null, selected_preset: null,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [recs, setRecs] = useState(null);

  useEffect(() => {
    api.get('/api/tenant/sales-channels')
      .then((r) => setValue((v) => ({ ...v, ...(r.data || {}) })))
      .catch(() => {})
      .finally(() => setLoading(false));
    api.get('/api/tenant/sales-channels/recommendations')
      .then((r) => setRecs(r.data))
      .catch(() => {});
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      const r = await api.put('/api/tenant/sales-channels', value);
      setValue(r.data.preferences);
      const recR = await api.get('/api/tenant/sales-channels/recommendations');
      setRecs(recR.data);
      toast.success('Sales channel preferences saved. Aria will use these for follow-ups.');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not save');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="text-slate-400 text-sm">Loading…</div>;

  return (
    <div className="space-y-4" data-testid="sales-channels-tab">
      <div className="bg-white border border-[#E8E0F5] rounded-2xl p-5" style={{ boxShadow: 'var(--shadow-card)' }}>
        <div className="flex items-start gap-3 mb-5">
          <div className="w-10 h-10 rounded-xl bg-violet-50 text-violet-600 flex items-center justify-center">
            <Megaphone size={18} weight="duotone" />
          </div>
          <div>
            <h3 className="text-base font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Sales channels</h3>
            <p className="text-xs text-[#5A4A7A] mt-0.5">
              Where Aria talks to your leads. Changes affect the touchpoint generator, lead-card recommendations, and the integrations Aria suggests.
            </p>
          </div>
        </div>

        <SalesChannelsPicker value={value} onChange={setValue} />

        {recs?.workflow_rule && (
          <div className="mt-5 p-4 rounded-xl bg-violet-50 border border-violet-200" data-testid="sales-channels-rule">
            <div className="text-[10px] uppercase tracking-wider font-extrabold text-violet-700 mb-1">Aria's first-touch rule</div>
            <div className="text-sm text-slate-900">
              <span className="font-bold">When:</span> {recs.workflow_rule.trigger}
            </div>
            {recs.workflow_rule.primary_action && (
              <div className="text-sm text-slate-900 mt-1">
                <span className="font-bold">Do:</span> {recs.workflow_rule.primary_action}
              </div>
            )}
            {recs.workflow_rule.fallback_chain?.length > 0 && (
              <div className="text-sm text-slate-700 mt-1">
                <span className="font-bold">If no reply:</span> {recs.workflow_rule.fallback_chain.join(' → ')}
              </div>
            )}
          </div>
        )}

        <div className="flex justify-end mt-5">
          <button
            data-testid="sales-channels-save-btn"
            onClick={save}
            disabled={saving || (value.selected_channels || []).length === 0}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-900 text-white text-xs font-bold uppercase tracking-wider hover:bg-slate-800 disabled:opacity-50"
          >
            <FloppyDisk size={14} weight="bold" /> {saving ? 'Saving…' : 'Save sales channels'}
          </button>
        </div>
      </div>
    </div>
  );
}
