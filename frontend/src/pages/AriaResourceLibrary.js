/**
 * Iter100 — Aria Resource Library panel.
 *
 * Used inside TrainAriaV2 as section "09 — Resource Library".
 *
 * - Lists resources (filterable by category + tag).
 * - Upload PDF/DOCX/etc → server returns file_id → POST resource.
 * - Or paste a URL (case study link, blog, demo video).
 * - Tag with free-text + ICP from training profile.
 * - Edit / archive inline.
 */
import { useEffect, useState, useCallback } from 'react';
import api from '../config/api';
import { toast } from 'sonner';

const CATEGORIES = [
  { id: 'case_study', label: 'Case study' },
  { id: 'deck',       label: 'Deck' },
  { id: 'one_pager',  label: 'One-pager' },
  { id: 'blog',       label: 'Blog post' },
  { id: 'demo',       label: 'Demo video' },
  { id: 'other',      label: 'Other' },
];

const ResourceLibrary = ({ icpProfiles = [] }) => {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState(null);
  const [filterCat, setFilterCat] = useState('');
  const [filterTag, setFilterTag] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (filterCat) params.category = filterCat;
      if (filterTag) params.tag = filterTag;
      const r = await api.get('/api/aria/resources', { params });
      setItems(r.data.resources || []);
    } catch (e) {
      toast.error('Could not load resources');
    } finally {
      setLoading(false);
    }
  }, [filterCat, filterTag]);

  useEffect(() => { load(); }, [load]);

  const onSaved = async () => {
    setShowForm(false);
    setEditId(null);
    await load();
  };

  return (
    <div data-testid="aria-resource-library">
      <h2 className="text-lg font-bold text-slate-900 mb-2">Resource Library</h2>
      <p className="text-sm text-slate-600 mb-4">
        Upload sales collateral (case studies, decks, one-pagers, demo videos) and tag
        each by ICP + keyword. Aria attaches the right resource on outbound based on
        the lead's ICP and pain-point match.
      </p>

      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <select
          data-testid="resource-filter-category"
          value={filterCat}
          onChange={(e) => setFilterCat(e.target.value)}
          className="text-sm border border-slate-200 rounded-md px-2 py-1.5"
        >
          <option value="">All categories</option>
          {CATEGORIES.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
        </select>
        <input
          data-testid="resource-filter-tag"
          value={filterTag}
          onChange={(e) => setFilterTag(e.target.value)}
          placeholder="Filter by tag…"
          className="text-sm border border-slate-200 rounded-md px-2 py-1.5"
        />
        <div className="flex-1" />
        <button
          data-testid="resource-new-btn"
          onClick={() => { setEditId(null); setShowForm(true); }}
          className="text-sm font-semibold text-white bg-violet-600 hover:bg-violet-700 px-3 py-1.5 rounded-md"
        >
          + New resource
        </button>
      </div>

      {showForm && (
        <ResourceForm
          icpProfiles={icpProfiles}
          editId={editId}
          existing={items.find(x => x.id === editId)}
          onCancel={() => { setShowForm(false); setEditId(null); }}
          onSaved={onSaved}
        />
      )}

      {/* List */}
      {loading ? (
        <div className="text-sm text-slate-500">Loading…</div>
      ) : items.length === 0 ? (
        <div className="text-sm text-slate-500 bg-slate-50 border border-dashed border-slate-200 rounded-lg p-6 text-center" data-testid="resource-empty">
          No resources yet. Click <span className="font-semibold text-violet-700">+ New resource</span> to add your first case study or deck.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3" data-testid="resource-grid">
          {items.map(r => (
            <ResourceCard
              key={r.id}
              r={r}
              icpProfiles={icpProfiles}
              onEdit={() => { setEditId(r.id); setShowForm(true); }}
              onArchived={load}
            />
          ))}
        </div>
      )}
    </div>
  );
};

// ─── List card ─────────────────────────────────────────────────────────────
const ResourceCard = ({ r, icpProfiles, onEdit, onArchived }) => {
  const archive = async () => {
    if (!window.confirm(`Archive "${r.title}"?`)) return;
    try {
      await api.delete(`/api/aria/resources/${r.id}`);
      toast.success('Archived');
      onArchived();
    } catch (e) {
      toast.error('Could not archive');
    }
  };

  const namedIcps = (r.target_icp_ids || []).map(id => {
    const m = icpProfiles.find(p => (p.id === id) || (p.icp_name && p.icp_name.toLowerCase() === id.toLowerCase()));
    return m ? (m.icp_name || m.name || id) : id;
  });

  return (
    <div className="bg-white border border-slate-200 rounded-lg p-4" data-testid={`resource-card-${r.id}`}>
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex-1 min-w-0">
          <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-violet-700">
            {CATEGORIES.find(c => c.id === r.category)?.label || r.category}
          </div>
          <div className="text-sm font-bold text-slate-900 truncate" data-testid={`resource-title-${r.id}`}>
            {r.title}
          </div>
          {r.description && (
            <div className="text-xs text-slate-600 mt-1 line-clamp-2">{r.description}</div>
          )}
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <button onClick={onEdit} className="text-xs text-violet-700 font-semibold hover:underline" data-testid={`resource-edit-${r.id}`}>Edit</button>
          <button onClick={archive} className="text-xs text-slate-500 hover:text-red-600" data-testid={`resource-archive-${r.id}`}>Archive</button>
        </div>
      </div>

      <div className="flex items-center gap-2 text-[10px] text-slate-500 mb-2">
        {r.type === 'file' ? (
          <a className="text-violet-700 hover:underline" href={r.file_url} target="_blank" rel="noopener noreferrer" data-testid={`resource-file-link-${r.id}`}>
            📎 {r.file_name || 'View file'}
          </a>
        ) : (
          <a className="text-violet-700 hover:underline truncate" href={r.url} target="_blank" rel="noopener noreferrer" data-testid={`resource-url-link-${r.id}`}>
            🔗 {r.url}
          </a>
        )}
      </div>

      {(r.tags?.length || namedIcps.length) ? (
        <div className="flex flex-wrap gap-1 text-[10px]">
          {namedIcps.map(t => (
            <span key={t} className="bg-violet-100 text-violet-800 rounded-full px-2 py-0.5 font-semibold">ICP · {t}</span>
          ))}
          {(r.tags || []).map(t => (
            <span key={t} className="bg-slate-100 text-slate-700 rounded-full px-2 py-0.5">#{t}</span>
          ))}
        </div>
      ) : null}

      {r.send_count > 0 && (
        <div className="mt-2 text-[10px] text-slate-500">Attached {r.send_count} time(s) by Aria</div>
      )}
    </div>
  );
};

// ─── Create / Edit form ────────────────────────────────────────────────────
const ResourceForm = ({ icpProfiles, editId, existing, onCancel, onSaved }) => {
  const [type, setType] = useState(existing?.type || 'url');
  const [title, setTitle] = useState(existing?.title || '');
  const [description, setDescription] = useState(existing?.description || '');
  const [category, setCategory] = useState(existing?.category || 'case_study');
  const [url, setUrl] = useState(existing?.url || '');
  const [fileId, setFileId] = useState(existing?.file_id || '');
  const [fileName, setFileName] = useState(existing?.file_name || '');
  const [fileSize, setFileSize] = useState(existing?.size || null);
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [tagsInput, setTagsInput] = useState((existing?.tags || []).join(', '));
  const [icpIds, setIcpIds] = useState(existing?.target_icp_ids || []);

  const toggleIcp = (id) => {
    setIcpIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  };

  const handleFile = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', f);
      const r = await api.post('/api/aria/resources/upload', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setFileId(r.data.file_id);
      setFileName(r.data.file_name);
      setFileSize(r.data.size);
      toast.success(`Uploaded ${r.data.file_name}`);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Upload failed');
    } finally { setUploading(false); }
  };

  const save = async () => {
    if (!title.trim()) { toast.error('Title required'); return; }
    if (type === 'url' && !url.trim()) { toast.error('URL required'); return; }
    if (type === 'file' && !fileId) { toast.error('Upload a file first'); return; }
    setSaving(true);
    try {
      const tags = tagsInput.split(',').map(t => t.trim()).filter(Boolean);
      const body = {
        title: title.trim(),
        description: description.trim(),
        category,
        type,
        url: type === 'url' ? url.trim() : null,
        file_id: type === 'file' ? fileId : null,
        file_name: type === 'file' ? fileName : null,
        size: type === 'file' ? fileSize : null,
        tags,
        target_icp_ids: icpIds,
      };
      if (editId) {
        // PATCH — only mutable fields
        await api.patch(`/api/aria/resources/${editId}`, {
          title: body.title, description: body.description, category: body.category,
          url: body.url, tags: body.tags, target_icp_ids: body.target_icp_ids,
        });
        toast.success('Updated');
      } else {
        await api.post('/api/aria/resources', body);
        toast.success('Resource added');
      }
      onSaved();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Save failed');
    } finally { setSaving(false); }
  };

  return (
    <div className="bg-violet-50 border border-violet-200 rounded-lg p-4 mb-4" data-testid="resource-form">
      <div className="flex items-center justify-between mb-3">
        <div className="text-sm font-bold text-violet-900">{editId ? 'Edit resource' : 'New resource'}</div>
        <button onClick={onCancel} className="text-slate-500 text-lg leading-none" data-testid="resource-form-cancel">×</button>
      </div>

      {/* Type toggle (only on create) */}
      {!editId && (
        <div className="flex gap-2 mb-3">
          {['url', 'file'].map(t => (
            <button
              key={t}
              data-testid={`resource-type-${t}`}
              onClick={() => setType(t)}
              className={`text-xs font-semibold px-3 py-1 rounded-md ${type === t ? 'bg-violet-600 text-white' : 'bg-white text-slate-700 border border-slate-200'}`}
            >
              {t === 'url' ? 'Link / URL' : 'Upload file'}
            </button>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1">Title</label>
          <input
            data-testid="resource-form-title"
            value={title} onChange={(e) => setTitle(e.target.value)}
            placeholder="Acme case study — 3x pipeline"
            className="w-full text-sm border border-slate-200 rounded-md px-2 py-1.5"
          />
        </div>
        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1">Category</label>
          <select
            data-testid="resource-form-category"
            value={category} onChange={(e) => setCategory(e.target.value)}
            className="w-full text-sm border border-slate-200 rounded-md px-2 py-1.5"
          >
            {CATEGORIES.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
          </select>
        </div>
      </div>

      <div className="mb-3">
        <label className="block text-xs font-semibold text-slate-700 mb-1">Short description (optional)</label>
        <textarea
          data-testid="resource-form-description"
          value={description} onChange={(e) => setDescription(e.target.value)}
          rows={2}
          placeholder="When Aria should attach this — e.g. 'Pricing-aware case study for SaaS founders'"
          className="w-full text-sm border border-slate-200 rounded-md px-2 py-1.5"
        />
      </div>

      {type === 'url' ? (
        <div className="mb-3">
          <label className="block text-xs font-semibold text-slate-700 mb-1">URL</label>
          <input
            data-testid="resource-form-url"
            value={url} onChange={(e) => setUrl(e.target.value)}
            placeholder="https://your-site.com/case-studies/acme"
            className="w-full text-sm border border-slate-200 rounded-md px-2 py-1.5"
          />
        </div>
      ) : (
        <div className="mb-3">
          <label className="block text-xs font-semibold text-slate-700 mb-1">File</label>
          {fileId ? (
            <div className="flex items-center justify-between text-xs bg-white border border-slate-200 rounded-md px-2 py-1.5">
              <span className="text-slate-700">📎 {fileName} ({(fileSize / 1024).toFixed(1)} KB)</span>
              <button onClick={() => { setFileId(''); setFileName(''); setFileSize(null); }} className="text-red-600 font-semibold">Remove</button>
            </div>
          ) : (
            <input
              data-testid="resource-form-file"
              type="file" onChange={handleFile} disabled={uploading}
              className="block w-full text-xs text-slate-700"
            />
          )}
          {uploading && <div className="text-xs text-violet-700 mt-1">Uploading…</div>}
        </div>
      )}

      <div className="mb-3">
        <label className="block text-xs font-semibold text-slate-700 mb-1">Tags (comma-separated)</label>
        <input
          data-testid="resource-form-tags"
          value={tagsInput} onChange={(e) => setTagsInput(e.target.value)}
          placeholder="pricing, saas, fintech"
          className="w-full text-sm border border-slate-200 rounded-md px-2 py-1.5"
        />
      </div>

      {icpProfiles.length > 0 && (
        <div className="mb-3">
          <label className="block text-xs font-semibold text-slate-700 mb-1">Target ICPs</label>
          <div className="flex flex-wrap gap-1.5">
            {icpProfiles.map((p, i) => {
              const id = p.id || p.icp_name || `icp_${i}`;
              const on = icpIds.includes(id);
              return (
                <button
                  key={id}
                  data-testid={`resource-form-icp-${id}`}
                  onClick={() => toggleIcp(id)}
                  className={`text-[10px] font-semibold px-2 py-1 rounded-full ${on ? 'bg-violet-600 text-white' : 'bg-white text-slate-700 border border-slate-200'}`}
                >
                  {p.icp_name || p.name || id}
                </button>
              );
            })}
          </div>
        </div>
      )}

      <div className="flex items-center justify-end gap-2 pt-2 border-t border-violet-200">
        <button onClick={onCancel} className="text-xs font-semibold text-slate-700 px-3 py-1.5">Cancel</button>
        <button
          data-testid="resource-form-save"
          onClick={save} disabled={saving || uploading}
          className="text-xs font-semibold text-white bg-violet-600 hover:bg-violet-700 px-4 py-1.5 rounded-md disabled:opacity-50"
        >
          {saving ? 'Saving…' : (editId ? 'Update' : 'Save')}
        </button>
      </div>
    </div>
  );
};

export default ResourceLibrary;
