/**
 * ContactRequestsTab — Master Admin inbound CRM.
 *
 * Sortable, status-filtered table of every contact-form submission
 * (Signup contact modal, LandingPage contact modal, future SDK widgets).
 * Each row expands to show the message + admin-note input + status update
 * dropdown (new → contacted → qualified → closed → spam).
 *
 * Backend: GET /api/admin/contact-requests, PATCH /api/admin/contact-requests/{id}/status
 */
import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import api from '../../config/api';
import {
  Envelope, Buildings, Globe, ArrowsClockwise, CaretDown, CaretUp,
  CheckCircle, Tag, EnvelopeOpen, X,
} from '@phosphor-icons/react';

const STATUS_META = {
  new:       { tint: '#0055FF', bg: '#DCEEFE', label: 'New' },
  contacted: { tint: '#7C35DC', bg: '#F4F0FF', label: 'Contacted' },
  qualified: { tint: '#16A34A', bg: '#DCFCE7', label: 'Qualified' },
  closed:    { tint: '#5A4A7A', bg: '#F0ECF9', label: 'Closed' },
  spam:      { tint: '#DC2626', bg: '#FEE2E2', label: 'Spam' },
};
const STATUS_ORDER = ['new', 'contacted', 'qualified', 'closed', 'spam'];

const ContactRequestsTab = () => {
  const [items, setItems] = useState([]);
  const [counts, setCounts] = useState({});
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(false);
  const [openId, setOpenId] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const params = statusFilter ? { status: statusFilter } : {};
      const r = await api.get('/api/admin/contact-requests', { params });
      setItems(r.data?.items || []);
      setCounts(r.data?.counts || {});
    } catch (e) {
      toast.error('Could not load contact requests');
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [statusFilter]);  // eslint-disable-line

  const setStatus = async (id, next) => {
    try {
      await api.patch(`/api/admin/contact-requests/${id}/status`, { status: next });
      toast.success(`Marked as ${STATUS_META[next].label}`);
      load();
    } catch (e) {
      toast.error('Update failed');
    }
  };

  const TABS = [
    { key: '', label: 'All', count: counts.all },
    ...STATUS_ORDER.map((s) => ({ key: s, label: STATUS_META[s].label, count: counts[s] })),
  ];

  return (
    <div className="space-y-4" data-testid="contact-requests-tab">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-lg font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Contact Requests</h2>
          <p className="text-xs text-[#5A4A7A]">Inbound leads from the signup page, landing page, and contact widgets. Reply directly from your email — the prospect's address is set as reply-to.</p>
        </div>
        <button onClick={load} data-testid="contact-requests-refresh"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-[#E8E0F5] rounded-lg text-xs font-bold text-[#5A4A7A] hover:bg-[#F9F5FF]">
          <ArrowsClockwise size={12} weight="bold" className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      {/* Status pivots */}
      <div className="flex items-center gap-1.5 flex-wrap" data-testid="contact-requests-tabs">
        {TABS.map((t) => {
          const isActive = statusFilter === t.key;
          return (
            <button key={t.key || 'all'} onClick={() => setStatusFilter(t.key)} data-testid={`contact-tab-${t.key || 'all'}`}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-bold transition-all ${
                isActive ? 'text-white border-transparent shadow-[0_4px_12px_rgba(124,53,220,0.25)]' : 'bg-white text-[#5A4A7A] border-[#E8E0F5] hover:border-[#7C35DC]/30 hover:text-[#7C35DC]'
              }`}
              style={isActive ? { background: 'var(--gradient-brand)', fontFamily: 'Plus Jakarta Sans' } : { fontFamily: 'Plus Jakarta Sans' }}>
              {t.label}
              {typeof t.count === 'number' && (
                <span className={`text-[10px] font-extrabold px-1.5 py-0.5 rounded-full ${isActive ? 'bg-white/25 text-white' : 'bg-[#F4F0FF] text-[#7C35DC]'}`}>{t.count}</span>
              )}
            </button>
          );
        })}
      </div>

      {items.length === 0 && !loading && (
        <div className="bg-white border border-[#E8E0F5] rounded-2xl p-10 text-center" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="contact-requests-empty">
          <EnvelopeOpen size={28} weight="duotone" className="mx-auto text-[#9B8AB0] mb-2" />
          <p className="text-sm text-[#5A4A7A]">No inbound contact requests {statusFilter ? `in "${STATUS_META[statusFilter]?.label}"` : 'yet'}. They'll appear here when someone uses the contact form on your landing or signup page.</p>
        </div>
      )}

      {items.length > 0 && (
        <div className="bg-white border border-[#E8E0F5] rounded-2xl overflow-hidden" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="contact-requests-list">
          {items.map((it) => {
            const meta = STATUS_META[it.status] || STATUS_META.new;
            const open = openId === it.id;
            return (
              <div key={it.id} className="border-b border-[#F0ECF9] last:border-0" data-testid={`contact-row-${it.id}`}>
                <button onClick={() => setOpenId(open ? null : it.id)} className="w-full flex items-start gap-3 px-4 py-3 hover:bg-[#FAF7FF] text-left transition-colors" data-testid={`contact-row-toggle-${it.id}`}>
                  <div className="flex-shrink-0 mt-0.5">
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold border" style={{ background: meta.bg, borderColor: meta.tint + '55', color: meta.tint }}>
                      <Tag size={9} weight="fill" /> {meta.label}
                    </span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-sm font-extrabold text-[#1A0A2E] truncate" style={{ fontFamily: 'Plus Jakarta Sans' }}>{it.name}</div>
                      <span className="text-[10px] text-[#9B8AB0] flex-shrink-0">{new Date(it.created_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}</span>
                    </div>
                    <div className="flex items-center gap-3 flex-wrap text-[11px] text-[#5A4A7A] mt-0.5">
                      <span className="inline-flex items-center gap-1"><Envelope size={10} weight="fill" /> {it.email}</span>
                      {it.company && <span className="inline-flex items-center gap-1"><Buildings size={10} weight="fill" /> {it.company}</span>}
                      {it.website && <span className="inline-flex items-center gap-1"><Globe size={10} weight="fill" /> {it.website}</span>}
                    </div>
                    {!open && <p className="text-xs text-[#5A4A7A] mt-1 line-clamp-1">{it.message}</p>}
                  </div>
                  {open ? <CaretUp size={12} weight="bold" className="text-[#9B8AB0] mt-1" /> : <CaretDown size={12} weight="bold" className="text-[#9B8AB0] mt-1" />}
                </button>
                {open && (
                  <div className="px-4 pb-4 ml-[68px]" data-testid={`contact-row-detail-${it.id}`}>
                    <div className="bg-[#FAF7FF] border border-[#E0D4F7] rounded-lg p-3 text-sm text-[#1A0A2E] whitespace-pre-wrap">{it.message}</div>
                    <div className="flex items-center gap-2 mt-3 flex-wrap">
                      <span className="text-[10px] font-extrabold uppercase tracking-[0.18em] text-[#9B8AB0]">Mark as</span>
                      {STATUS_ORDER.map((s) => (
                        <button key={s} onClick={() => setStatus(it.id, s)} disabled={it.status === s} data-testid={`contact-set-${it.id}-${s}`}
                          className={`px-2.5 py-1 rounded-md text-[11px] font-bold transition-all ${
                            it.status === s ? 'opacity-40 cursor-default' : 'hover:-translate-y-0.5'
                          }`}
                          style={{ background: STATUS_META[s].bg, color: STATUS_META[s].tint, border: `1px solid ${STATUS_META[s].tint}33` }}>
                          {STATUS_META[s].label}
                        </button>
                      ))}
                      <a href={`mailto:${it.email}?subject=Re:%20your%20Aria%20request`} className="ml-auto inline-flex items-center gap-1 px-3 py-1 btn-gradient text-white rounded-md text-[11px] font-extrabold" data-testid={`contact-reply-${it.id}`} style={{ fontFamily: 'Plus Jakarta Sans' }}>
                        <Envelope size={11} weight="fill" /> Reply
                      </a>
                    </div>
                    {it.admin_note && (
                      <div className="mt-3 text-[11px] text-[#5A4A7A]">
                        <span className="font-bold text-[#1A0A2E]">Note:</span> {it.admin_note}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default ContactRequestsTab;
