import React, { useEffect, useMemo, useState } from 'react';
import {
  ChatText, Microphone, FileText, Article, User, ShieldCheck, CurrencyDollar,
  Plus, Copy, PencilSimple, Trash, Sparkle, TrendUp, Stack, Clock,
} from '@phosphor-icons/react';
import { toast } from 'sonner';
import api from '../config/api';
import PageHeader from '../components/PageHeader';

const ICON_MAP = { ChatText, Microphone, FileText, Article, User, ShieldCheck, CurrencyDollar };

const DEFAULT_FORM = { title: '', type: 'message_template', body: '', tags: '', channel: '', used_by_aria: true };

const SalesAssets = () => {
  const [data, setData] = useState(null);
  const [activeType, setActiveType] = useState('all');
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [editingId, setEditingId] = useState(null);

  const load = async () => {
    try {
      const r = await api.get('/api/aria-agent/assets');
      setData(r.data);
    } catch { /* swallow */ } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const types = data?.types || [];
  const filteredAssets = useMemo(() => {
    if (!data) return [];
    if (activeType === 'all') return data.assets || [];
    return (data.assets || []).filter(a => a.type === activeType);
  }, [data, activeType]);

  const openCreate = () => {
    setEditingId(null);
    setForm({ ...DEFAULT_FORM, type: activeType === 'all' ? 'message_template' : activeType });
    setShowForm(true);
  };

  const openEdit = (asset) => {
    setEditingId(asset.id);
    setForm({
      title: asset.title || '', type: asset.type, body: asset.body || '',
      tags: (asset.tags || []).join(', '), channel: asset.channel || '',
      used_by_aria: asset.used_by_aria !== false,
    });
    setShowForm(true);
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!form.title.trim()) { toast.error('Title is required'); return; }
    const payload = {
      title: form.title.trim(), type: form.type, body: form.body,
      tags: form.tags.split(',').map(t => t.trim()).filter(Boolean),
      channel: form.channel || null, used_by_aria: !!form.used_by_aria,
    };
    try {
      if (editingId) {
        await api.patch(`/api/aria-agent/assets/${editingId}`, payload);
        toast.success('Asset updated');
      } else {
        await api.post('/api/aria-agent/assets', payload);
        toast.success('Asset saved to ARIA');
      }
      setShowForm(false); setForm(DEFAULT_FORM); setEditingId(null); load();
    } catch { toast.error('Could not save asset'); }
  };

  const remove = async (id) => {
    if (!window.confirm('Delete this asset?')) return;
    try { await api.delete(`/api/aria-agent/assets/${id}`); toast.success('Asset deleted'); load(); }
    catch { toast.error('Could not delete'); }
  };

  const copyBody = async (a) => {
    try {
      await navigator.clipboard.writeText(a.body || '');
      await api.post(`/api/aria-agent/assets/${a.id}/use`).catch(() => {});
      toast.success('Copied. ARIA marked this as used.');
      load();
    } catch { toast.error('Copy failed'); }
  };

  const stats = data?.stats || {};
  const typeTabs = [{ id: 'all', label: 'All', icon: 'Stack' }, ...types];

  return (
    <div className="space-y-6" data-testid="sales-assets-page">
      <PageHeader
        eyebrow="ARIA · Sales assets"
        title="The content ARIA sends on your behalf"
        subtitle="Drop your best messages, voice notes, case studies and proposals here. ARIA picks the right one for the right moment — no more scrambling for copy."
        actions={
          <button onClick={openCreate} data-testid="create-asset-btn"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-white font-semibold text-sm"
            style={{ background: 'var(--gradient-brand)', boxShadow: 'var(--shadow-hover)' }}>
            <Plus size={16} weight="bold" /> New asset
          </button>
        }
      />

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="asset-stats">
        <StatTile icon={Stack} label="Total assets" value={stats.total ?? 0} accent="#7C35DC" />
        <StatTile icon={Sparkle} label="Active for ARIA" value={stats.active ?? 0} accent="#C044E0" />
        <StatTile icon={Clock} label="Used this week" value={stats.used_this_week ?? 0} accent="#16A34A" />
        <StatTile icon={TrendUp} label="Top asset" value={stats.top_asset?.title || '—'} accent="#D97706" small />
      </div>

      {/* Type tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1" data-testid="asset-type-tabs">
        {typeTabs.map(t => {
          const Icon = ICON_MAP[t.icon] || Stack;
          const count = t.id === 'all' ? stats.total ?? 0 : (stats.by_type?.[t.id] ?? 0);
          const isActive = activeType === t.id;
          return (
            <button key={t.id} onClick={() => setActiveType(t.id)} data-testid={`asset-tab-${t.id}`}
              className={`inline-flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold whitespace-nowrap transition-all ${
                isActive ? 'text-white' : 'text-[#5A4A7A] hover:text-[#1A0A2E] border border-[#E8E0F5] bg-white'
              }`}
              style={isActive ? { background: 'var(--gradient-brand)', boxShadow: 'var(--shadow-card)' } : {}}>
              <Icon size={14} weight="fill" />
              {t.label}
              <span className={`text-[10px] px-1.5 py-0.5 rounded-md ${isActive ? 'bg-white/20' : 'bg-[#F4F0FF] text-[#7C35DC]'}`}>{count}</span>
            </button>
          );
        })}
      </div>

      {/* Assets grid */}
      {loading ? (
        <div className="text-sm text-[#9B8AB0] p-6">Loading assets…</div>
      ) : filteredAssets.length === 0 ? (
        <EmptyState onCreate={openCreate} activeType={activeType} types={types} />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="assets-grid">
          {filteredAssets.map(a => {
            const typeMeta = types.find(t => t.id === a.type) || {};
            const Icon = ICON_MAP[typeMeta.icon] || ChatText;
            return (
              <div key={a.id} className="bg-white border border-[#E8E0F5] rounded-2xl p-5 flex flex-col gap-3"
                style={{ boxShadow: 'var(--shadow-card)' }} data-testid={`asset-card-${a.id}`}>
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
                    style={{ background: '#F4F0FF', border: '1px solid #E0D4F7' }}>
                    <Icon size={18} weight="fill" className="text-[#7C35DC]" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#7C35DC]" style={{ fontFamily: 'Plus Jakarta Sans' }}>
                      {typeMeta.label || a.type.replace(/_/g, ' ')}
                    </div>
                    <h3 className="text-base font-extrabold text-[#1A0A2E] truncate" style={{ fontFamily: 'Plus Jakarta Sans' }}>{a.title}</h3>
                  </div>
                  {a.used_by_aria && (
                    <span className="px-2 py-1 rounded-md text-[9px] font-bold uppercase tracking-[0.15em] bg-[#DCFCE7] text-[#16A34A] border border-[#16A34A]/30 flex-shrink-0">
                      ARIA on
                    </span>
                  )}
                </div>
                {a.body && (
                  <div className="text-sm text-[#5A4A7A] leading-relaxed line-clamp-4 bg-[#FAF7FF] border border-[#EDE5FA] rounded-xl px-3 py-2 whitespace-pre-wrap">
                    {a.body}
                  </div>
                )}
                {(a.tags || []).length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {a.tags.map(t => (
                      <span key={t} className="text-[10px] font-semibold text-[#5A4A7A] bg-[#F4F0FF] border border-[#E0D4F7] px-2 py-0.5 rounded-md">#{t}</span>
                    ))}
                  </div>
                )}
                <div className="flex items-center justify-between pt-2 border-t border-[#F0ECF9] text-xs text-[#9B8AB0]">
                  <span>Used {a.usage_count || 0}×{a.channel ? ` · ${a.channel}` : ''}</span>
                  <div className="flex items-center gap-1">
                    <button onClick={() => copyBody(a)} data-testid={`asset-copy-${a.id}`} title="Copy"
                      className="p-1.5 rounded-lg hover:bg-[#F4F0FF] text-[#7C35DC]"><Copy size={14} weight="fill" /></button>
                    <button onClick={() => openEdit(a)} data-testid={`asset-edit-${a.id}`} title="Edit"
                      className="p-1.5 rounded-lg hover:bg-[#F4F0FF] text-[#5A4A7A]"><PencilSimple size={14} weight="fill" /></button>
                    <button onClick={() => remove(a.id)} data-testid={`asset-delete-${a.id}`} title="Delete"
                      className="p-1.5 rounded-lg hover:bg-[#FEE2E2] text-[#DC2626]"><Trash size={14} weight="fill" /></button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Create/Edit modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#1A0A2E]/60 backdrop-blur-sm p-4" onClick={() => setShowForm(false)}>
          <form onSubmit={submit} onClick={e => e.stopPropagation()}
            className="bg-white rounded-2xl p-6 w-full max-w-lg space-y-4" style={{ boxShadow: 'var(--shadow-deep)' }}
            data-testid="asset-form-modal">
            <div>
              <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#7C35DC]">{editingId ? 'Edit' : 'New'} sales asset</div>
              <h2 className="text-xl font-extrabold text-[#1A0A2E] mt-1" style={{ fontFamily: 'Plus Jakarta Sans' }}>Train ARIA with your best content</h2>
            </div>
            <Field label="Title">
              <input required value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
                data-testid="asset-title-input"
                className="w-full px-3 py-2 rounded-lg border border-[#E8E0F5] focus:outline-none focus:ring-2 focus:ring-[#7C35DC]/30 text-sm"
                placeholder="e.g. Pricing response — enterprise" />
            </Field>
            <Field label="Type">
              <select value={form.type} onChange={e => setForm(f => ({ ...f, type: e.target.value }))}
                data-testid="asset-type-select"
                className="w-full px-3 py-2 rounded-lg border border-[#E8E0F5] focus:outline-none focus:ring-2 focus:ring-[#7C35DC]/30 text-sm">
                {types.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}
              </select>
            </Field>
            <Field label="Content">
              <textarea value={form.body} onChange={e => setForm(f => ({ ...f, body: e.target.value }))}
                data-testid="asset-body-input" rows={6}
                className="w-full px-3 py-2 rounded-lg border border-[#E8E0F5] focus:outline-none focus:ring-2 focus:ring-[#7C35DC]/30 text-sm font-mono"
                placeholder="Paste the template, script, or key talking points…" />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Tags (comma-separated)">
                <input value={form.tags} onChange={e => setForm(f => ({ ...f, tags: e.target.value }))}
                  data-testid="asset-tags-input"
                  className="w-full px-3 py-2 rounded-lg border border-[#E8E0F5] focus:outline-none focus:ring-2 focus:ring-[#7C35DC]/30 text-sm"
                  placeholder="pricing, enterprise" />
              </Field>
              <Field label="Channel">
                <input value={form.channel} onChange={e => setForm(f => ({ ...f, channel: e.target.value }))}
                  data-testid="asset-channel-input"
                  className="w-full px-3 py-2 rounded-lg border border-[#E8E0F5] focus:outline-none focus:ring-2 focus:ring-[#7C35DC]/30 text-sm"
                  placeholder="WhatsApp, Email…" />
              </Field>
            </div>
            <label className="flex items-center gap-2 text-sm text-[#5A4A7A] cursor-pointer">
              <input type="checkbox" checked={form.used_by_aria}
                onChange={e => setForm(f => ({ ...f, used_by_aria: e.target.checked }))}
                data-testid="asset-active-toggle"
                className="w-4 h-4 accent-[#7C35DC]" />
              Let ARIA use this asset automatically
            </label>
            <div className="flex items-center justify-end gap-2 pt-2 border-t border-[#F0ECF9]">
              <button type="button" onClick={() => setShowForm(false)}
                className="px-4 py-2 rounded-xl text-sm font-semibold text-[#5A4A7A] hover:bg-[#F4F0FF]"
                data-testid="asset-cancel-btn">Cancel</button>
              <button type="submit" data-testid="asset-submit-btn"
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-white font-semibold text-sm"
                style={{ background: 'var(--gradient-brand)' }}>
                <Sparkle size={14} weight="fill" />{editingId ? 'Save changes' : 'Add to ARIA'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};

const StatTile = ({ icon: Icon, label, value, accent, small }) => (
  <div className="bg-white border border-[#E8E0F5] rounded-2xl p-4" style={{ boxShadow: 'var(--shadow-card)' }}>
    <div className="flex items-center gap-2 mb-2">
      <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: `${accent}14`, border: `1px solid ${accent}33` }}>
        <Icon size={14} weight="fill" style={{ color: accent }} />
      </div>
      <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#7B6D9C]">{label}</div>
    </div>
    <div className={`${small ? 'text-base' : 'text-2xl'} font-extrabold text-[#1A0A2E] truncate`} style={{ fontFamily: 'Plus Jakarta Sans' }}>{value}</div>
  </div>
);

const Field = ({ label, children }) => (
  <div>
    <label className="block text-[10px] font-bold uppercase tracking-[0.2em] text-[#7B6D9C] mb-1.5">{label}</label>
    {children}
  </div>
);

const EmptyState = ({ onCreate, activeType, types }) => {
  const typeMeta = types.find(t => t.id === activeType);
  return (
    <div className="bg-white border border-dashed border-[#E0D4F7] rounded-2xl p-12 text-center" data-testid="assets-empty-state">
      <div className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4"
        style={{ background: 'var(--gradient-subtle)', border: '1px solid #E0D4F7' }}>
        <Stack size={28} weight="duotone" className="text-[#7C35DC]" />
      </div>
      <h3 className="text-xl font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>
        {typeMeta ? `No ${typeMeta.label.toLowerCase()} yet` : 'Your asset library is empty'}
      </h3>
      <p className="text-sm text-[#5A4A7A] mt-2 max-w-md mx-auto">
        {typeMeta?.description || 'Add your best messages, voice notes, and proposals. ARIA uses them to reply in your exact voice.'}
      </p>
      <button onClick={onCreate} data-testid="empty-create-btn"
        className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-white font-semibold text-sm mt-5"
        style={{ background: 'var(--gradient-brand)', boxShadow: 'var(--shadow-hover)' }}>
        <Plus size={16} weight="bold" /> Add your first asset
      </button>
    </div>
  );
};

export default SalesAssets;
