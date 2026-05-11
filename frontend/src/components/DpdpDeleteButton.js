import React, { useState } from 'react';
import api from '../config/api';
import { toast } from 'sonner';
import { Trash, X, Warning } from '@phosphor-icons/react';

const DpdpDeleteButton = ({ leadId, leadName, onDeleted }) => {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState('anonymise');
  const [reason, setReason] = useState('user_request');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (confirm.toLowerCase() !== 'delete') { toast.error('Please type DELETE to confirm'); return; }
    setBusy(true);
    try {
      await api.post(`/api/leads/${leadId}/delete-personal-data`, { mode, reason });
      toast.success(mode === 'anonymise' ? 'Personal data anonymised' : 'Lead permanently deleted');
      onDeleted && onDeleted();
    } catch (e) { toast.error(e.response?.data?.detail || 'Deletion failed'); }
    finally { setBusy(false); setOpen(false); }
  };

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        data-testid="dpdp-delete-btn"
        className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-[#DC2626]/30 text-[#DC2626] rounded-lg text-xs font-bold hover:bg-[#FEE2E2]"
        title="Delete personal data under DPDP Act 2023"
      >
        <Trash size={12} weight="bold" /> Delete personal data
      </button>

      {open && (
        <div className="fixed inset-0 bg-black/30 backdrop-blur-sm z-50 flex items-center justify-center p-4" data-testid="dpdp-modal">
          <div className="bg-white border border-[#E8E0F5] rounded-2xl w-full max-w-lg" style={{ boxShadow: 'var(--shadow-hover)' }}>
            <div className="flex items-center justify-between p-5 border-b border-[#E8E0F5]">
              <div className="flex items-center gap-2">
                <Warning size={20} weight="fill" className="text-[#DC2626]" />
                <h3 className="text-lg font-bold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Delete personal data</h3>
              </div>
              <button onClick={() => setOpen(false)}><X size={18} className="text-[#9B8AB0]" /></button>
            </div>
            <div className="p-5 space-y-4">
              <p className="text-sm text-[#5A4A7A]">
                You are about to delete personal data for <strong className="text-[#1A0A2E]">{leadName}</strong> under the
                Digital Personal Data Protection Act 2023. This action is logged in the deletion log (kept 7 years for legal record).
              </p>

              <div className="space-y-2">
                <label className="flex items-start gap-3 px-3 py-2 rounded-lg border border-[#E8E0F5] hover:border-[#7C35DC]/40 cursor-pointer">
                  <input type="radio" name="mode" value="anonymise" checked={mode === 'anonymise'} onChange={() => setMode('anonymise')} data-testid="mode-anonymise" className="mt-1 accent-[#7C35DC]" />
                  <div>
                    <div className="font-bold text-[#1A0A2E] text-sm">Anonymise (recommended)</div>
                    <div className="text-xs text-[#5A4A7A]">Name → "Deleted User", phone redacted, conversations cleared. Lead row kept for analytics. Reversible by support only.</div>
                  </div>
                </label>
                <label className="flex items-start gap-3 px-3 py-2 rounded-lg border border-[#DC2626]/30 hover:bg-[#FEE2E2] cursor-pointer">
                  <input type="radio" name="mode" value="hard" checked={mode === 'hard'} onChange={() => setMode('hard')} data-testid="mode-hard" className="mt-1 accent-[#DC2626]" />
                  <div>
                    <div className="font-bold text-[#DC2626] text-sm">Hard delete</div>
                    <div className="text-xs text-[#5A4A7A]">Permanently delete the lead and ALL conversations, activities, touchpoints. <strong>Irreversible.</strong></div>
                  </div>
                </label>
              </div>

              <div>
                <label className="text-xs font-bold uppercase tracking-[0.15em] text-[#5A4A7A]">Reason</label>
                <select data-testid="dpdp-reason" value={reason} onChange={(e) => setReason(e.target.value)} className="mt-1 w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-2 rounded-lg text-sm">
                  <option value="user_request">Subject requested deletion</option>
                  <option value="duplicate">Duplicate entry</option>
                  <option value="invalid_data">Invalid / test data</option>
                  <option value="retention_policy">Retention policy expiry</option>
                  <option value="other">Other</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-bold uppercase tracking-[0.15em] text-[#5A4A7A]">Type <span className="font-mono text-[#DC2626]">DELETE</span> to confirm</label>
                <input data-testid="dpdp-confirm" value={confirm} onChange={(e) => setConfirm(e.target.value)} className="mt-1 w-full bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-2 rounded-lg text-sm font-mono" />
              </div>
            </div>
            <div className="px-5 py-4 border-t border-[#E8E0F5] flex items-center justify-end gap-2">
              <button onClick={() => setOpen(false)} className="px-4 py-2 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-lg text-sm font-medium">Cancel</button>
              <button
                data-testid="dpdp-submit"
                onClick={submit}
                disabled={busy || confirm.toLowerCase() !== 'delete'}
                className="px-5 py-2 bg-[#DC2626] hover:bg-[#B91C1C] disabled:opacity-40 text-white rounded-lg text-sm font-bold"
                style={{ fontFamily: 'Plus Jakarta Sans' }}
              >
                {busy ? 'Deleting…' : 'Delete personal data'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default DpdpDeleteButton;
