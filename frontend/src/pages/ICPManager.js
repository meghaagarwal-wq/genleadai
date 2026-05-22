import React, { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import {
  Target, Plus, PencilSimple, Trash, X, Sparkle,
  Buildings, Briefcase, Lightning, Heart, CurrencyInr, Tag,
} from '@phosphor-icons/react';
import api from '../config/api';

const TONES = [
  { value: 'professional', label: 'Professional', tint: 'bg-slate-100 text-slate-700 border-slate-300' },
  { value: 'casual', label: 'Casual', tint: 'bg-amber-100 text-amber-700 border-amber-300' },
  { value: 'bold', label: 'Bold', tint: 'bg-rose-100 text-rose-700 border-rose-300' },
];

const EMPTY_FORM = {
  label: '',
  title_targets: [],
  industry: '',
  company_size: '',
  pain_point: '',
  value_prop: '',
  tone: 'professional',
  deal_size: '',
};

export default function ICPManager() {
  const [icps, setIcps] = useState([]);
  const [meta, setMeta] = useState({ count: 0 });
  const [loading, setLoading] = useState(true);
  const [linkingIcp, setLinkingIcp] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get('/api/icps/list');
      setIcps(r.data.icps || []);
      setMeta({ count: r.data.count });
    } catch (e) {
      toast.error('Could not load ICPs');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const openCreate = () => {
    setEditing({ ...EMPTY_FORM, isNew: true });
    setModalOpen(true);
  };

  const openEdit = (icp) => {
    setEditing({ ...icp, isNew: false });
    setModalOpen(true);
  };

  const handleSave = async (form) => {
    try {
      if (form.isNew) {
        const { isNew, id, created_at, updated_at, tenant_id, ...payload } = form;
        await api.post('/api/icps/create', payload);
        toast.success('ICP created');
      } else {
        const { isNew, id, created_at, updated_at, tenant_id, ...payload } = form;
        await api.put(`/api/icps/${form.id}`, payload);
        toast.success('ICP updated');
      }
      setModalOpen(false);
      setEditing(null);
      load();
    } catch (e) {
      const detail = e.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Save failed');
    }
  };

  const handleDelete = async (icp, force = false) => {
    try {
      await api.delete(`/api/icps/${icp.id}${force ? '?force=true' : ''}`);
      toast.success(force ? 'ICP deleted (untagged records)' : 'ICP deleted');
      load();
    } catch (e) {
      const detail = e.response?.data?.detail;
      if (e.response?.status === 409 && typeof detail === 'object' && detail.counts) {
        const total = (detail.counts.contacts || 0) + (detail.counts.assets || 0) + (detail.counts.conversations || 0);
        if (window.confirm(
          `This ICP is tagged on ${total} record(s):\n` +
          `• ${detail.counts.contacts} contact(s)\n` +
          `• ${detail.counts.assets} asset(s)\n` +
          `• ${detail.counts.conversations} conversation(s)\n\n` +
          `Untag them and delete the ICP?`
        )) {
          handleDelete(icp, true);
        }
      } else {
        toast.error(typeof detail === 'string' ? detail : 'Delete failed');
      }
    }
  };

  return (
    <div data-testid="icp-manager-page" className="max-w-6xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="flex items-start justify-between mb-8 gap-4 flex-wrap">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-violet-600 font-semibold mb-2">
            Multi-ICP Architecture
          </p>
          <h1 className="text-3xl font-semibold text-slate-900 mb-2">Your Ideal Customer Profiles</h1>
          <p className="text-slate-600 text-sm max-w-2xl">
            Define every customer type you sell to. Aria switches tone, pain points, and value prop
            based on which ICP each contact is tagged with — so your outbound sounds like it was written
            for them, not for everyone.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div data-testid="icp-tier-meter" className="text-right">
            <div className="text-xs text-slate-500 uppercase tracking-wider">ICPs defined</div>
            <div className="text-2xl font-semibold text-slate-900">{meta.count}</div>
          </div>
          <button
            type="button"
            onClick={openCreate}
            data-testid="icp-create-btn"
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-900 text-white text-sm font-medium hover:bg-slate-800 transition-colors"
          >
            <Plus size={16} weight="bold" />
            New ICP
          </button>
        </div>
      </div>

      {/* Grid */}
      {loading ? (
        <div data-testid="icp-loading" className="text-center py-16 text-slate-400">Loading ICPs…</div>
      ) : icps.length === 0 ? (
        <EmptyState onCreate={openCreate} />
      ) : (
        <div data-testid="icp-grid" className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {icps.map((icp) => (
            <ICPCard
              key={icp.id}
              icp={icp}
              onEdit={() => openEdit(icp)}
              onDelete={() => handleDelete(icp)}
              onLinkCampaign={() => setLinkingIcp(icp)}
            />
          ))}
        </div>
      )}

      {modalOpen && editing && (
        <ICPModal
          form={editing}
          onChange={setEditing}
          onClose={() => { setModalOpen(false); setEditing(null); }}
          onSave={handleSave}
        />
      )}

      {linkingIcp && (
        <LinkCampaignModal
          icp={linkingIcp}
          onClose={() => setLinkingIcp(null)}
          onLinked={async () => { setLinkingIcp(null); await load(); }}
        />
      )}
    </div>
  );
}

function EmptyState({ onCreate }) {
  return (
    <div
      data-testid="icp-empty-state"
      className="bg-white/70 backdrop-blur-md border border-slate-200 rounded-3xl p-12 text-center"
    >
      <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-600 text-white mb-4">
        <Target size={32} weight="duotone" />
      </div>
      <h3 className="text-xl font-semibold text-slate-900 mb-2">No ICPs yet</h3>
      <p className="text-slate-600 text-sm max-w-md mx-auto mb-6">
        Create your first Ideal Customer Profile. Aria will tailor every outbound message to match
        the tone and pain points of that buyer.
      </p>
      <button
        type="button"
        onClick={onCreate}
        data-testid="icp-empty-create-btn"
        className="inline-flex items-center gap-2 px-5 py-3 rounded-xl bg-slate-900 text-white text-sm font-medium hover:bg-slate-800 transition-colors"
      >
        <Plus size={16} weight="bold" />
        Create your first ICP
      </button>
    </div>
  );
}

function ICPCard({ icp, onEdit, onDelete, onLinkCampaign }) {
  const tone = TONES.find((t) => t.value === icp.tone) || TONES[0];
  const hasCampaign = !!icp.icp_campaign_id;
  return (
    <div
      data-testid={`icp-card-${icp.id}`}
      className="group bg-white/80 backdrop-blur-sm border border-slate-200 rounded-2xl p-5 hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200"
    >
      <div className="flex items-start justify-between mb-3 gap-3">
        <h3 className="text-base font-semibold text-slate-900 leading-tight">{icp.label}</h3>
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button type="button" onClick={onEdit} data-testid={`icp-edit-${icp.id}`} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-500 hover:text-slate-900">
            <PencilSimple size={14} weight="bold" />
          </button>
          <button type="button" onClick={onDelete} data-testid={`icp-delete-${icp.id}`} className="p-1.5 rounded-lg hover:bg-rose-50 text-slate-500 hover:text-rose-600">
            <Trash size={14} weight="bold" />
          </button>
        </div>
      </div>

      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-md border font-semibold ${tone.tint}`}>
          {tone.label}
        </span>
        {icp.industry && <span className="text-[10px] text-slate-500 px-2 py-0.5 rounded-md bg-slate-50 border border-slate-200">{icp.industry}</span>}
        {icp.company_size && <span className="text-[10px] text-slate-500 px-2 py-0.5 rounded-md bg-slate-50 border border-slate-200">{icp.company_size}</span>}
      </div>

      {icp.title_targets?.length > 0 && (
        <div className="mb-3">
          <div className="text-[10px] uppercase tracking-wider text-slate-400 mb-1.5 flex items-center gap-1">
            <Briefcase size={10} /> Title targets
          </div>
          <div className="flex flex-wrap gap-1">
            {icp.title_targets.slice(0, 6).map((t) => (
              <span key={t} className="text-xs text-slate-700 px-2 py-0.5 rounded-md bg-violet-50 border border-violet-100">{t}</span>
            ))}
          </div>
        </div>
      )}

      {icp.pain_point && (
        <div className="text-xs text-slate-600 mt-3 line-clamp-2 leading-relaxed">
          <span className="text-rose-600 font-semibold">Pain:</span> {icp.pain_point}
        </div>
      )}
      {icp.value_prop && (
        <div className="text-xs text-slate-600 mt-1 line-clamp-2 leading-relaxed">
          <span className="text-emerald-600 font-semibold">Value:</span> {icp.value_prop}
        </div>
      )}

      {/* Iter78 S3 — linked campaign chip + manage button */}
      <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between gap-2 flex-wrap">
        {hasCampaign ? (
          <div
            data-testid={`icp-linked-campaign-${icp.id}`}
            className="text-[10px] font-semibold inline-flex items-center gap-1 px-2 py-1 rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200"
          >
            <Lightning size={10} weight="bold" /> Linked: {icp.icp_campaign_name || icp.icp_campaign_id}
          </div>
        ) : (
          <div className="text-[10px] text-slate-400 italic">No campaign linked</div>
        )}
        <button
          type="button"
          onClick={onLinkCampaign}
          data-testid={`icp-link-campaign-btn-${icp.id}`}
          className="text-[10px] font-bold text-violet-700 hover:text-violet-900 hover:underline"
        >
          {hasCampaign ? 'Change campaign' : 'Link a campaign'}
        </button>
      </div>
    </div>
  );
}

function ICPModal({ form, onChange, onClose, onSave }) {
  const [titleInput, setTitleInput] = useState('');

  const addTitle = () => {
    const v = titleInput.trim();
    if (!v || form.title_targets.includes(v)) return;
    onChange({ ...form, title_targets: [...form.title_targets, v] });
    setTitleInput('');
  };

  const removeTitle = (t) => onChange({ ...form, title_targets: form.title_targets.filter((x) => x !== t) });

  const submit = (e) => {
    e.preventDefault();
    if (!form.label.trim()) {
      toast.error('Label is required');
      return;
    }
    onSave(form);
  };

  return (
    <div data-testid="icp-modal" className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
      <form onSubmit={submit} className="bg-white rounded-3xl shadow-2xl max-w-2xl w-full my-8 overflow-hidden">
        <div className="px-6 py-5 border-b border-slate-100 flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-wider text-violet-600 font-semibold">
              {form.isNew ? 'New ICP' : 'Edit ICP'}
            </p>
            <h2 className="text-xl font-semibold text-slate-900">
              {form.isNew ? 'Define a new customer type' : form.label}
            </h2>
          </div>
          <button type="button" onClick={onClose} className="p-2 rounded-lg hover:bg-slate-100">
            <X size={18} />
          </button>
        </div>

        <div className="px-6 py-5 space-y-4 max-h-[70vh] overflow-y-auto">
          <Field label="Label" required hint="A short name to identify this ICP">
            <input
              data-testid="icp-form-label"
              value={form.label}
              onChange={(e) => onChange({ ...form, label: e.target.value })}
              placeholder="e.g. CFO at Series B SaaS"
              className="w-full px-3 py-2 rounded-lg border border-slate-300 focus:border-violet-500 focus:ring-2 focus:ring-violet-100 outline-none text-sm"
            />
          </Field>

          <Field label="Title targets" icon={<Briefcase size={12} />} hint="Press Enter to add">
            <div className="flex flex-wrap gap-1.5 mb-2">
              {form.title_targets.map((t) => (
                <span key={t} className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-violet-50 border border-violet-200 text-violet-700">
                  {t}
                  <button type="button" onClick={() => removeTitle(t)} className="hover:text-rose-600"><X size={10} /></button>
                </span>
              ))}
            </div>
            <input
              data-testid="icp-form-title-input"
              value={titleInput}
              onChange={(e) => setTitleInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addTitle(); } }}
              placeholder="e.g. VP Finance, CFO, Finance Director"
              className="w-full px-3 py-2 rounded-lg border border-slate-300 focus:border-violet-500 focus:ring-2 focus:ring-violet-100 outline-none text-sm"
            />
          </Field>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Field label="Industry" icon={<Buildings size={12} />}>
              <input
                data-testid="icp-form-industry"
                value={form.industry || ''}
                onChange={(e) => onChange({ ...form, industry: e.target.value })}
                placeholder="SaaS"
                className="w-full px-3 py-2 rounded-lg border border-slate-300 focus:border-violet-500 focus:ring-2 focus:ring-violet-100 outline-none text-sm"
              />
            </Field>
            <Field label="Company size" icon={<UsersThree />}>
              <input
                data-testid="icp-form-company-size"
                value={form.company_size || ''}
                onChange={(e) => onChange({ ...form, company_size: e.target.value })}
                placeholder="50-200 employees"
                className="w-full px-3 py-2 rounded-lg border border-slate-300 focus:border-violet-500 focus:ring-2 focus:ring-violet-100 outline-none text-sm"
              />
            </Field>
          </div>

          <Field label="Pain point" icon={<Lightning size={12} className="text-rose-500" />}>
            <textarea
              data-testid="icp-form-pain"
              value={form.pain_point || ''}
              onChange={(e) => onChange({ ...form, pain_point: e.target.value })}
              placeholder="Manually closing month-end finance ops takes 5 days"
              rows={2}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 focus:border-violet-500 focus:ring-2 focus:ring-violet-100 outline-none text-sm resize-none"
            />
          </Field>

          <Field label="Value prop" icon={<Heart size={12} className="text-emerald-500" />}>
            <textarea
              data-testid="icp-form-value"
              value={form.value_prop || ''}
              onChange={(e) => onChange({ ...form, value_prop: e.target.value })}
              placeholder="Automate close in 1 day with audit-ready trails"
              rows={2}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 focus:border-violet-500 focus:ring-2 focus:ring-violet-100 outline-none text-sm resize-none"
            />
          </Field>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Field label="Tone" icon={<Sparkle size={12} />}>
              <div className="flex gap-2">
                {TONES.map((t) => (
                  <button
                    key={t.value}
                    type="button"
                    data-testid={`icp-form-tone-${t.value}`}
                    onClick={() => onChange({ ...form, tone: t.value })}
                    className={`flex-1 text-xs font-semibold py-2 rounded-lg border transition-all ${
                      form.tone === t.value ? t.tint + ' ring-2 ring-offset-1 ring-violet-300' : 'bg-white border-slate-200 text-slate-500 hover:bg-slate-50'
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </Field>
            <Field label="Deal size" icon={<CurrencyInr size={12} />}>
              <input
                data-testid="icp-form-deal-size"
                value={form.deal_size || ''}
                onChange={(e) => onChange({ ...form, deal_size: e.target.value })}
                placeholder="₹30 LPA / $30k ACV"
                className="w-full px-3 py-2 rounded-lg border border-slate-300 focus:border-violet-500 focus:ring-2 focus:ring-violet-100 outline-none text-sm"
              />
            </Field>
          </div>
        </div>

        <div className="px-6 py-4 bg-slate-50 border-t border-slate-100 flex items-center justify-end gap-2">
          <button type="button" onClick={onClose} className="px-4 py-2 rounded-lg text-sm text-slate-600 hover:bg-slate-200">Cancel</button>
          <button type="submit" data-testid="icp-form-save" className="px-5 py-2 rounded-lg bg-slate-900 text-white text-sm font-medium hover:bg-slate-800">
            {form.isNew ? 'Create ICP' : 'Save changes'}
          </button>
        </div>
      </form>
    </div>
  );
}

function UsersThree(props) {
  return <Tag size={12} {...props} />;
}

function Field({ label, icon, hint, required, children }) {
  return (
    <div>
      <label className="text-xs font-semibold text-slate-700 mb-1.5 flex items-center gap-1.5">
        {icon}
        <span>{label}{required && <span className="text-rose-500 ml-0.5">*</span>}</span>
        {hint && <span className="text-slate-400 font-normal ml-2 normal-case">{hint}</span>}
      </label>
      {children}
    </div>
  );
}

// Iter78 — S3: campaign-link modal
function LinkCampaignModal({ icp, onClose, onLinked }) {
  const [campaigns, setCampaigns] = useState([]);
  const [selected, setSelected] = useState(icp.icp_campaign_id || '');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const r = await api.get('/api/outreach/campaigns');
        setCampaigns(r.data?.campaigns || []);
      } catch (_e) {
        toast.error('Could not load campaigns');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      await api.post(`/api/icps/${icp.id}/link-campaign`, { campaign_id: selected || null });
      toast.success(selected ? 'Campaign linked' : 'Campaign unlinked');
      onLinked();
    } catch (e) {
      const d = e?.response?.data?.detail;
      toast.error(typeof d === 'string' ? d : 'Link failed');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center z-50 p-4" data-testid="icp-link-campaign-modal">
      <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl">
        <h3 className="text-base font-bold text-slate-900 mb-1">Link a campaign to <span className="text-violet-700">{icp.label}</span></h3>
        <p className="text-xs text-slate-500 mb-4">When a lead is tagged with this ICP, the linked campaign becomes its default enrollment target.</p>
        {loading ? (
          <p className="text-sm text-slate-400 text-center py-6">Loading campaigns…</p>
        ) : campaigns.length === 0 ? (
          <p className="text-sm text-slate-500 text-center py-6">No campaigns yet — create one first from <strong>Outreach Campaigns</strong>.</p>
        ) : (
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            data-testid="icp-link-campaign-select"
            className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:border-violet-500"
          >
            <option value="">— Unlink / no campaign —</option>
            {campaigns.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        )}
        <div className="flex items-center justify-end gap-2 mt-5">
          <button type="button" onClick={onClose} className="px-4 py-2 rounded-lg text-xs font-bold text-slate-600 hover:bg-slate-100">Cancel</button>
          <button
            type="button"
            onClick={save}
            disabled={saving || loading}
            data-testid="icp-link-campaign-save"
            className="px-4 py-2 rounded-lg text-xs font-bold bg-violet-600 text-white hover:bg-violet-700 disabled:opacity-50"
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}
