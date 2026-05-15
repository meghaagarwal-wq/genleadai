import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Target, Plus, CaretDown, Check, X } from '@phosphor-icons/react';
import { toast } from 'sonner';
import api from '../config/api';

/**
 * IcpPickerForLead — small dropdown to tag/untag a lead with an ICP.
 * Mounted on the Lead Detail screen.
 */
export default function IcpPickerForLead({ leadId, currentIcpId, onAssigned }) {
  const [icps, setIcps] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await api.get('/api/icps/list');
      setIcps(r.data.icps || []);
    } catch (e) { /* silently */ }
  }, []);

  useEffect(() => { load(); }, [load]);

  const current = icps.find((i) => i.id === currentIcpId);

  const assign = async (icpId) => {
    setLoading(true);
    try {
      await api.post('/api/icps/assign-contact', { contact_id: leadId, icp_id: icpId });
      toast.success(icpId ? `Tagged as ${icps.find((i) => i.id === icpId)?.label}` : 'ICP cleared');
      setOpen(false);
      if (onAssigned) onAssigned(icpId);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Could not assign ICP');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div data-testid="icp-picker-card" className="bg-white border border-[#E8E0F5] rounded-xl p-4" style={{ boxShadow: 'var(--shadow-card)' }}>
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-xs font-semibold uppercase tracking-[0.15em] text-[#9B8AB0] flex items-center gap-1.5" style={{ fontFamily: 'Plus Jakarta Sans' }}>
          <Target size={12} /> Ideal Customer Profile
        </h4>
      </div>

      {icps.length === 0 ? (
        <div className="text-xs text-slate-500">
          No ICPs yet — <Link to="/icps" className="text-violet-600 font-semibold hover:underline">create your first one</Link> so Aria can tailor messages.
        </div>
      ) : (
        <div className="relative">
          <button
            type="button"
            onClick={() => setOpen(!open)}
            disabled={loading}
            data-testid="icp-picker-trigger"
            className="w-full flex items-center justify-between px-3 py-2 rounded-lg border border-slate-200 bg-white hover:border-violet-300 transition-colors text-left text-sm"
          >
            <span className={current ? 'text-slate-900 font-medium' : 'text-slate-400'}>
              {current ? current.label : 'Tag this lead with an ICP'}
            </span>
            <CaretDown size={12} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
          </button>

          {open && (
            <div data-testid="icp-picker-menu" className="absolute z-20 mt-1 w-full bg-white border border-slate-200 rounded-lg shadow-lg max-h-64 overflow-y-auto">
              {current && (
                <button
                  type="button"
                  onClick={() => assign(null)}
                  data-testid="icp-picker-clear"
                  className="w-full text-left px-3 py-2 text-xs text-rose-600 hover:bg-rose-50 flex items-center gap-2 border-b border-slate-100"
                >
                  <X size={12} /> Clear ICP
                </button>
              )}
              {icps.map((icp) => (
                <button
                  key={icp.id}
                  type="button"
                  onClick={() => assign(icp.id)}
                  data-testid={`icp-picker-option-${icp.id}`}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-violet-50 flex items-center justify-between gap-2"
                >
                  <div className="min-w-0 flex-1">
                    <div className="text-slate-900 font-medium truncate">{icp.label}</div>
                    {icp.industry && <div className="text-[10px] text-slate-400 truncate">{icp.industry}</div>}
                  </div>
                  {icp.id === currentIcpId && <Check size={14} className="text-violet-600 flex-shrink-0" />}
                </button>
              ))}
              <Link
                to="/icps"
                className="block px-3 py-2 text-xs text-violet-600 hover:bg-violet-50 border-t border-slate-100 font-medium flex items-center gap-1.5"
              >
                <Plus size={12} /> Manage ICPs
              </Link>
            </div>
          )}

          {current && current.pain_point && (
            <div className="mt-3 text-[11px] text-slate-500 leading-relaxed border-t border-slate-100 pt-2">
              <span className="font-semibold text-rose-600">Pain:</span> {current.pain_point}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
