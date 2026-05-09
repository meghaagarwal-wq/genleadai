import React, { useState, useEffect } from 'react';
import api from '../config/api';
import { X, Copy, CheckCircle, Trash, UserPlus, Sparkle, Clock, Warning, PaperPlaneTilt } from '@phosphor-icons/react';
import { toast } from 'sonner';

const ROLE_OPTIONS = [
  { id: 'admin', label: 'Admin', desc: 'Manage team, edit Aria config, full read/write' },
  { id: 'member', label: 'Member', desc: 'Manage leads + pipeline, take over conversations' },
  { id: 'viewer', label: 'Viewer', desc: 'Read-only — see leads + conversations only' },
];

/**
 * InviteTeamModal — owner/admin creates a tokenized invite link for a teammate.
 * On success, displays a copyable URL the user can share via any channel.
 */
const InviteTeamModal = ({ open, onClose, onCreated }) => {
  const [role, setRole] = useState('member');
  const [email, setEmail] = useState('');
  const [expiresInDays, setExpiresInDays] = useState(14);
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (open) { setCreated(null); setCopied(false); setEmail(''); setRole('member'); setExpiresInDays(14); }
  }, [open]);

  if (!open) return null;

  const submit = async (e) => {
    e?.preventDefault?.();
    setCreating(true);
    try {
      const res = await api.post('/api/invitations', {
        email: email || null,
        role,
        expires_in_days: Number(expiresInDays) || 14,
      });
      const inv = res.data?.invitation;
      const fullUrl = res.data?.invite_full_url || `${window.location.origin}/invite/${inv?.token}`;
      const emailStatus = res.data?.email || {};
      setCreated({ ...inv, full_url: fullUrl, email_status: emailStatus });
      if (emailStatus.sent) {
        toast.success(`Invite emailed to ${inv.email}`);
      } else if (inv?.email && emailStatus.error) {
        toast.error(`Email failed (${emailStatus.error}). Share the link manually.`);
      } else {
        toast.success('Invite link ready. Copy and share.');
      }
      onCreated?.();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Could not create invite');
    } finally {
      setCreating(false);
    }
  };

  const copy = () => {
    if (!created?.full_url) return;
    navigator.clipboard.writeText(created.full_url);
    setCopied(true);
    toast.success('Copied');
    setTimeout(() => setCopied(false), 1800);
  };

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center p-4" data-testid="invite-modal">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-md bg-[#141414] border border-[#262626] rounded-2xl overflow-hidden">
        <div className="px-5 py-4 border-b border-[#262626] flex items-center justify-between" style={{ background: 'linear-gradient(135deg, #1A0A2E 0%, #4C1D95 100%)' }}>
          <div className="flex items-center gap-2">
            <UserPlus size={16} weight="fill" className="text-[#C9B6FF]" />
            <h3 className="text-base font-bold text-white">Invite teammate</h3>
          </div>
          <button onClick={onClose} className="p-1 rounded text-white/60 hover:text-white hover:bg-white/10" data-testid="invite-modal-close">
            <X size={14} />
          </button>
        </div>

        {!created ? (
          <form onSubmit={submit} className="p-5 space-y-4">
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-[0.2em] text-[#737373] mb-2">Role</label>
              <div className="space-y-1.5">
                {ROLE_OPTIONS.map((r) => (
                  <button
                    key={r.id} type="button" onClick={() => setRole(r.id)}
                    data-testid={`invite-role-${r.id}`}
                    className={`w-full text-left px-3 py-2.5 rounded-lg border transition ${
                      role === r.id ? 'bg-[#7C35DC]/15 border-[#7C35DC] text-white' : 'bg-[#0A0A0A] border-[#262626] text-[#A3A3A3] hover:border-[#7C35DC]/40'
                    }`}
                  >
                    <div className="text-sm font-bold">{r.label}</div>
                    <div className="text-xs opacity-80 mt-0.5">{r.desc}</div>
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-[10px] font-bold uppercase tracking-[0.2em] text-[#737373] mb-2">Email (optional)</label>
              <input
                type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                data-testid="invite-email"
                placeholder="Optional — pre-fills the signup form"
                className="w-full bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2 rounded-md text-sm focus:border-[#7C35DC] outline-none"
              />
              <div className="text-[10px] text-[#737373] mt-1">Leaving blank lets the link be shared with anyone you want.</div>
            </div>

            <div>
              <label className="block text-[10px] font-bold uppercase tracking-[0.2em] text-[#737373] mb-2">Link expires in</label>
              <select
                value={expiresInDays} onChange={(e) => setExpiresInDays(e.target.value)}
                data-testid="invite-expires"
                className="w-full bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2 rounded-md text-sm focus:border-[#7C35DC] outline-none"
              >
                <option value={1}>1 day</option>
                <option value={7}>7 days</option>
                <option value={14}>14 days</option>
                <option value={30}>30 days</option>
                <option value={90}>90 days</option>
              </select>
            </div>

            <button
              type="submit" disabled={creating}
              data-testid="invite-create-btn"
              className="w-full py-2.5 rounded-md text-white font-bold text-sm disabled:opacity-50"
              style={{ background: 'linear-gradient(135deg, #4C1D95, #7C35DC)' }}
            >
              {creating ? 'Creating link…' : 'Create invite link'}
            </button>
          </form>
        ) : (
          <div className="p-5 space-y-3" data-testid="invite-created-view">
            {created.email_status?.sent ? (
              <div className="bg-[#10B981]/10 border border-[#10B981]/30 rounded-md px-3 py-2 flex items-start gap-2" data-testid="invite-email-sent-banner">
                <CheckCircle size={14} weight="fill" className="text-[#10B981] mt-0.5" />
                <div className="text-xs text-[#10B981]">
                  <div className="font-bold">Invite emailed to {created.email}</div>
                  <div className="opacity-80 mt-0.5">They'll get a click-to-accept link in their inbox. The link below is the same one — copy it if you want to share via Slack/WhatsApp too.</div>
                </div>
              </div>
            ) : (
              <div className="bg-[#10B981]/10 border border-[#10B981]/30 rounded-md px-3 py-2 flex items-center gap-2">
                <CheckCircle size={14} weight="fill" className="text-[#10B981]" />
                <span className="text-sm text-[#10B981] font-semibold">Invite link ready</span>
              </div>
            )}
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-[0.2em] text-[#737373] mb-1.5">Share this link</label>
              <div className="flex items-center gap-1.5">
                <input
                  readOnly value={created.full_url}
                  data-testid="invite-link-input"
                  className="flex-1 bg-[#0A0A0A] border border-[#262626] text-white px-2.5 py-2 rounded-md text-xs font-mono"
                />
                <button onClick={copy} data-testid="invite-copy-btn"
                  className="px-3 py-2 rounded-md bg-[#7C35DC] text-white text-xs font-bold hover:bg-[#9B58E5]">
                  {copied ? <CheckCircle size={13} weight="fill" /> : <Copy size={13} weight="fill" />}
                </button>
              </div>
              <div className="text-[10px] text-[#737373] mt-1.5 flex items-center gap-1">
                <Clock size={10} weight="fill" /> Expires {new Date(created.expires_at).toLocaleDateString()} · Role: <span className="text-[#7C35DC] font-bold">{created.role}</span>
              </div>
            </div>
            <button onClick={onClose}
              className="w-full py-2 rounded-md bg-[#0A0A0A] border border-[#262626] text-white text-xs font-bold hover:bg-[#1E1E1E]">
              Done
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

/**
 * PendingInvitesList — shows pending tokenized invites, allows revoke.
 */
export const PendingInvitesList = ({ refreshKey }) => {
  const [invites, setInvites] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    api.get('/api/invitations').then((r) => {
      if (alive) setInvites(r.data?.invitations || []);
    }).catch(() => {}).finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [refreshKey]);

  const revoke = async (id) => {
    if (!window.confirm('Revoke this invite link? It will stop working immediately.')) return;
    try {
      await api.delete(`/api/invitations/${id}`);
      setInvites((arr) => arr.map((x) => x.id === id ? { ...x, revoked: true } : x));
      toast.success('Revoked');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Could not revoke');
    }
  };

  const copyAgain = (token) => {
    const url = `${window.location.origin}/invite/${token}`;
    navigator.clipboard.writeText(url);
    toast.success('Copied');
  };

  const resendEmail = async (id, email) => {
    try {
      await api.post(`/api/invitations/${id}/resend`);
      toast.success(`Re-sent to ${email}`);
      setInvites((arr) => arr.map((x) => x.id === id ? { ...x, email_sent: true, email_last_sent_at: new Date().toISOString(), email_send_count: (x.email_send_count || 0) + 1 } : x));
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Could not resend email');
    }
  };

  if (loading) return null;
  if (invites.length === 0) return null;

  return (
    <div className="bg-[#141414] border border-[#262626] rounded-lg" data-testid="pending-invites-list">
      <div className="p-5 border-b border-[#262626]">
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          <Sparkle size={12} weight="fill" className="text-[#7C35DC]" />
          Pending invites
        </h3>
        <p className="text-xs text-[#A3A3A3] mt-0.5">{invites.filter(i => !i.accepted && !i.revoked).length} active link(s)</p>
      </div>
      <div className="divide-y divide-[#262626]">
        {invites.map((inv) => {
          const expired = inv.expires_at && inv.expires_at < new Date().toISOString();
          const status = inv.revoked ? 'revoked' : inv.accepted ? 'accepted' : expired ? 'expired' : 'active';
          const statusColor = {
            active: 'bg-[#10B981]/10 text-[#10B981] border-[#10B981]/30',
            accepted: 'bg-[#7C35DC]/15 text-[#C9B6FF] border-[#7C35DC]/30',
            revoked: 'bg-[#FF3B30]/10 text-[#FF3B30] border-[#FF3B30]/30',
            expired: 'bg-[#737373]/10 text-[#A3A3A3] border-[#262626]',
          }[status];
          return (
            <div key={inv.id} className="px-5 py-3 flex items-center gap-3" data-testid={`invite-row-${inv.id}`}>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-mono text-white truncate">{inv.email || '<any email>'}</span>
                  <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#7C35DC]">{inv.role}</span>
                  <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase border ${statusColor}`}>{status}</span>
                </div>
                <div className="text-[10px] text-[#737373] mt-0.5">
                  Created {new Date(inv.created_at).toLocaleDateString()} · Expires {new Date(inv.expires_at).toLocaleDateString()}
                  {inv.email && (
                    <span className={`ml-2 ${inv.email_sent ? 'text-[#10B981]' : 'text-[#A3A3A3]'}`}>
                      · {inv.email_sent ? `Emailed${inv.email_send_count > 1 ? ` (${inv.email_send_count}×)` : ''}` : 'Email pending'}
                    </span>
                  )}
                </div>
              </div>
              {status === 'active' && (
                <>
                  {inv.email && (
                    <button onClick={() => resendEmail(inv.id, inv.email)} data-testid={`invite-resend-${inv.id}`}
                      className="p-1.5 rounded text-[#A3A3A3] hover:text-[#10B981] hover:bg-[#10B981]/10" title={inv.email_sent ? `Re-send (sent ${inv.email_send_count || 1}x)` : 'Send email'}>
                      <PaperPlaneTilt size={13} weight="fill" />
                    </button>
                  )}
                  <button onClick={() => copyAgain(inv.token)} data-testid={`invite-copy-${inv.id}`}
                    className="p-1.5 rounded text-[#A3A3A3] hover:text-white hover:bg-[#262626]" title="Copy link">
                    <Copy size={13} weight="fill" />
                  </button>
                  <button onClick={() => revoke(inv.id)} data-testid={`invite-revoke-${inv.id}`}
                    className="p-1.5 rounded text-[#FF3B30] hover:bg-[#FF3B30]/10" title="Revoke">
                    <Trash size={13} weight="fill" />
                  </button>
                </>
              )}
              {status === 'expired' && (
                <span className="text-[10px] text-[#A3A3A3] flex items-center gap-1"><Warning size={10} /> Expired</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default InviteTeamModal;
