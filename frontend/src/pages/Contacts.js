import React, { useEffect, useState } from 'react';
import api from '../config/api';
import { toast } from 'sonner';
import { Plus, Trash, PencilSimple, AddressBook, Funnel, ChatCircleDots } from '@phosphor-icons/react';
import PageHeader from '../components/PageHeader';

const CONTACT_TYPES = [
  { id: 'existing_client', label: 'Existing client', color: '#16A34A' },
  { id: 'vendor', label: 'Vendor', color: '#7C35DC' },
  { id: 'blocked', label: 'Blocked', color: '#DC2626' },
  { id: 'personal', label: 'Personal', color: '#0055FF' },
  { id: 'press', label: 'Press', color: '#F59E0B' },
  { id: 'job_applicant', label: 'Job applicant', color: '#0EA5E9' },
];

const Contacts = () => {
  const [activeTab, setActiveTab] = useState('contacts');
  const [contacts, setContacts] = useState([]);
  const [log, setLog] = useState([]);
  const [filter, setFilter] = useState('');
  const [showAdd, setShowAdd] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ name: '', phone: '', contact_type: 'vendor', company: '', notes: '' });

  const load = async () => {
    try {
      const r = await api.get('/api/contacts');
      setContacts(r.data?.contacts || []);
    } catch (err) {
      console.error(err);
    }
  };
  const loadLog = async () => {
    try {
      const r = await api.get('/api/classification/log?limit=100');
      setLog(r.data?.log || []);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => { load(); loadLog(); }, []);

  const submit = async (e) => {
    e?.preventDefault?.();
    try {
      if (editing) {
        await api.put(`/api/contacts/${editing.id}`, form);
        toast.success('Contact updated');
      } else {
        await api.post('/api/contacts', form);
        toast.success('Contact added');
      }
      setShowAdd(false);
      setEditing(null);
      setForm({ name: '', phone: '', contact_type: 'vendor', company: '', notes: '' });
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Could not save contact');
    }
  };

  const remove = async (id) => {
    if (!window.confirm('Remove this contact?')) return;
    try {
      await api.delete(`/api/contacts/${id}`);
      toast.success('Removed');
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Could not delete');
    }
  };

  const startEdit = (c) => {
    setEditing(c);
    setForm({
      name: c.name || '',
      phone: c.phone || '',
      contact_type: c.contact_type,
      company: c.company || '',
      notes: c.notes || '',
    });
    setShowAdd(true);
  };

  const filtered = filter ? contacts.filter((c) => c.contact_type === filter) : contacts;

  return (
    <div className="space-y-6" data-testid="contacts-page">
      <PageHeader
        eyebrow="Workspace"
        title="Contacts"
        subtitle="Pre-register vendors, existing clients, and known non-leads. Aria routes their inbound messages with the right canned response instead of treating them as sales leads."
      />

      <div className="flex items-center gap-1 bg-white border border-[#E8E0F5] rounded-xl p-1 w-fit" data-testid="contacts-tabs">
        <button onClick={() => setActiveTab('contacts')} data-testid="tab-contacts"
          className={`px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-[0.14em] ${activeTab === 'contacts' ? 'bg-[#7C35DC] text-white' : 'text-[#5A4A7A]'}`}>
          <AddressBook size={11} weight="fill" className="inline mr-1.5 -mt-0.5" /> Contacts
        </button>
        <button onClick={() => setActiveTab('log')} data-testid="tab-classification-log"
          className={`px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-[0.14em] ${activeTab === 'log' ? 'bg-[#7C35DC] text-white' : 'text-[#5A4A7A]'}`}>
          <ChatCircleDots size={11} weight="fill" className="inline mr-1.5 -mt-0.5" /> Classification log
        </button>
      </div>

      {activeTab === 'contacts' && (
        <>
          <div className="flex items-center gap-2 flex-wrap">
            <button onClick={() => { setEditing(null); setForm({ name: '', phone: '', contact_type: 'vendor', company: '', notes: '' }); setShowAdd(true); }} data-testid="contact-add-btn"
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-bold text-white" style={{ background: 'linear-gradient(135deg, #4C1D95, #7C35DC)' }}>
              <Plus size={13} weight="bold" /> Add contact
            </button>
            <div className="ml-auto flex items-center gap-2 text-xs text-[#5A4A7A]">
              <Funnel size={11} /> Filter:
              <select value={filter} onChange={(e) => setFilter(e.target.value)} data-testid="contacts-filter"
                className="bg-white border border-[#E8E0F5] rounded px-2 py-1 text-xs">
                <option value="">All ({contacts.length})</option>
                {CONTACT_TYPES.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
              </select>            </div>
          </div>

          <div className="bg-white border border-[#E8E0F5] rounded-xl overflow-hidden">
            <table className="w-full">
              <thead className="bg-[#F9F5FF]">
                <tr>
                  <th className="text-left px-4 py-2 text-[10px] font-bold uppercase tracking-wider text-[#5A4A7A]">Name</th>
                  <th className="text-left px-4 py-2 text-[10px] font-bold uppercase tracking-wider text-[#5A4A7A]">Phone</th>
                  <th className="text-left px-4 py-2 text-[10px] font-bold uppercase tracking-wider text-[#5A4A7A]">Type</th>
                  <th className="text-left px-4 py-2 text-[10px] font-bold uppercase tracking-wider text-[#5A4A7A]">Company</th>
                  <th className="text-left px-4 py-2 text-[10px] font-bold uppercase tracking-wider text-[#5A4A7A]"></th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr><td colSpan={5} className="px-4 py-6 text-center text-sm text-[#9B8AB0]">No contacts yet. Add a vendor or existing client to keep them out of your sales pipeline.</td></tr>
                ) : filtered.map((c) => {
                  const t = CONTACT_TYPES.find((x) => x.id === c.contact_type);
                  return (
                    <tr key={c.id} className="border-t border-[#F0ECF9] hover:bg-[#FBF9FE]" data-testid={`contact-row-${c.id}`}>
                      <td className="px-4 py-3 text-sm font-bold text-[#1A0A2E]">{c.name || '—'}</td>
                      <td className="px-4 py-3 text-xs text-[#5A4A7A] font-mono">{c.phone}</td>
                      <td className="px-4 py-3"><span className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider" style={{ background: `${t?.color || '#9B8AB0'}1A`, color: t?.color || '#9B8AB0' }}>{t?.label || c.contact_type}</span></td>
                      <td className="px-4 py-3 text-xs text-[#5A4A7A]">{c.company || '—'}</td>
                      <td className="px-4 py-3 text-right">
                        <button onClick={() => startEdit(c)} className="p-1 rounded text-[#5A4A7A] hover:text-[#7C35DC]" data-testid={`contact-edit-${c.id}`}><PencilSimple size={12} /></button>
                        <button onClick={() => remove(c.id)} className="p-1 rounded text-[#DC2626] hover:bg-[#DC2626]/10 ml-1" data-testid={`contact-delete-${c.id}`}><Trash size={12} /></button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      {activeTab === 'log' && (
        <div className="bg-white border border-[#E8E0F5] rounded-xl overflow-hidden" data-testid="classification-log">
          <table className="w-full">
            <thead className="bg-[#F9F5FF]">
              <tr>
                <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-[#5A4A7A]">Time</th>
                <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-[#5A4A7A]">Phone</th>
                <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-[#5A4A7A]">Message</th>
                <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-[#5A4A7A]">Layer</th>
                <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-[#5A4A7A]">Category</th>
                <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-[#5A4A7A]">Confidence</th>
                <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-[#5A4A7A]">Action</th>
              </tr>
            </thead>
            <tbody>
              {log.length === 0 ? (
                <tr><td colSpan={7} className="px-3 py-6 text-center text-sm text-[#9B8AB0]">No inbound classifications yet. When WhatsApp messages start arriving, you'll see them here.</td></tr>
              ) : log.map((l) => (
                <tr key={l.id} className="border-t border-[#F0ECF9] hover:bg-[#FBF9FE]" data-testid={`log-row-${l.id}`}>
                  <td className="px-3 py-2 text-[10px] text-[#9B8AB0] whitespace-nowrap">{new Date(l.created_at).toLocaleString()}</td>
                  <td className="px-3 py-2 text-xs text-[#5A4A7A] font-mono">{l.phone}</td>
                  <td className="px-3 py-2 text-xs text-[#1A0A2E] max-w-md truncate">{l.inbound_message}</td>
                  <td className="px-3 py-2 text-xs text-[#5A4A7A]">L{l.layer_resolved}</td>
                  <td className="px-3 py-2"><span className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-[#F4F0FF] text-[#7C35DC]">{l.category}</span></td>
                  <td className="px-3 py-2 text-xs text-[#5A4A7A]">{l.confidence != null ? `${Math.round(l.confidence * 100)}%` : '—'}</td>
                  <td className="px-3 py-2 text-xs text-[#5A4A7A]">{l.action_taken}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Add / Edit modal */}
      {showAdd && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60" onClick={() => setShowAdd(false)}>
          <form onSubmit={submit} onClick={(e) => e.stopPropagation()} className="bg-white rounded-2xl p-6 max-w-md w-full space-y-3" data-testid="contact-modal">
            <h3 className="text-lg font-extrabold text-[#1A0A2E]">{editing ? 'Edit contact' : 'Add contact'}</h3>
            <label className="block">
              <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#5A4A7A]">Name</span>
              <input data-testid="contact-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-1 w-full bg-white border border-[#E8E0F5] rounded px-3 py-2 text-sm" />
            </label>
            <label className="block">
              <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#5A4A7A]">Phone *</span>
              <input data-testid="contact-phone" required value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="mt-1 w-full bg-white border border-[#E8E0F5] rounded px-3 py-2 text-sm" placeholder="+15551234567" />
            </label>
            <label className="block">
              <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#5A4A7A]">Type *</span>
              <select data-testid="contact-type" value={form.contact_type} onChange={(e) => setForm({ ...form, contact_type: e.target.value })} className="mt-1 w-full bg-white border border-[#E8E0F5] rounded px-3 py-2 text-sm">
                {CONTACT_TYPES.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#5A4A7A]">Company</span>
              <input data-testid="contact-company" value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} className="mt-1 w-full bg-white border border-[#E8E0F5] rounded px-3 py-2 text-sm" />
            </label>
            <div className="flex gap-2 pt-2">
              <button type="submit" data-testid="contact-save"
                className="px-4 py-2 rounded-lg text-sm font-bold text-white" style={{ background: 'linear-gradient(135deg, #4C1D95, #7C35DC)' }}>
                {editing ? 'Save' : 'Add'}
              </button>
              <button type="button" onClick={() => { setShowAdd(false); setEditing(null); }} className="px-4 py-2 rounded-lg text-sm font-bold text-[#5A4A7A] hover:text-[#7C35DC]">Cancel</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};

export default Contacts;
