/**
 * LeadCapture — /settings → Lead Capture tab.
 *
 * Configure the embeddable website widget + copy embed snippet.
 */
import React, { useEffect, useState } from 'react';
import api from '../../config/api';
import { toast } from 'sonner';
import { Copy, Globe, CheckCircle, FloppyDisk, Eye } from '@phosphor-icons/react';

const FIELD_LABELS = {
  first_name: 'First name',
  last_name: 'Last name',
  email: 'Email',
  phone: 'Phone',
  company: 'Company',
  message: 'Message',
};

const LeadCapture = () => {
  const [config, setConfig] = useState(null);
  const [snippet, setSnippet] = useState('');
  const [saving, setSaving] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showPreview, setShowPreview] = useState(false);

  const load = async () => {
    try { const r = await api.get('/api/lead-capture/config'); setConfig(r.data.config); setSnippet(r.data.embed_snippet); }
    catch (e) { toast.error('Failed to load widget config'); }
  };
  useEffect(() => { load(); }, []);

  const save = async () => {
    setSaving(true);
    try {
      const payload = { ...config };
      delete payload.tenant_id; delete payload.updated_at;
      const r = await api.post('/api/lead-capture/config', payload);
      setConfig(r.data.config);
      toast.success('Widget settings saved');
    } catch (e) { toast.error(e.response?.data?.detail || 'Save failed'); }
    finally { setSaving(false); }
  };

  const copy = async () => {
    try { await navigator.clipboard.writeText(snippet); setCopied(true); setTimeout(() => setCopied(false), 2000); toast.success('Embed code copied'); }
    catch { toast.error('Could not copy'); }
  };

  const toggleField = (f) => {
    const cur = new Set(config.fields || []);
    if (cur.has(f)) cur.delete(f); else cur.add(f);
    setConfig({ ...config, fields: Array.from(cur) });
  };

  if (!config) return <div className="p-8 text-sm text-[#9B8AB0]">Loading widget config…</div>;

  return (
    <div className="space-y-5" data-testid="lead-capture-settings">
      <div className="bg-gradient-to-r from-[#F4F0FF] to-[#FFFFFF] border border-[#E0D4F7] rounded-xl p-5">
        <div className="flex items-center gap-2 mb-1">
          <Globe size={18} weight="duotone" className="text-[#7C35DC]" />
          <h2 className="text-base font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Website Lead Capture Widget</h2>
        </div>
        <p className="text-xs text-[#5A4A7A]">Embed a floating contact form on your website. Every submission instantly creates a lead, fires CRM sync, and starts your touchpoint sequence.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Configuration */}
        <div className="bg-white border border-[#E8E0F5] rounded-xl p-5 space-y-4" style={{ boxShadow: 'var(--shadow-card)' }}>
          <h3 className="text-sm font-extrabold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Appearance</h3>

          <div className="flex items-center gap-3">
            <label className="text-[10px] font-bold uppercase tracking-wider text-[#9B8AB0]">Enabled</label>
            <button onClick={() => setConfig({ ...config, enabled: !config.enabled })} data-testid="widget-enabled-toggle"
              className={`relative inline-flex h-5 w-10 items-center rounded-full transition-colors ${config.enabled ? 'bg-[#16A34A]' : 'bg-[#CBD5E1]'}`}>
              <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${config.enabled ? 'translate-x-5' : 'translate-x-1'}`}></span>
            </button>
            <span className="text-xs text-[#5A4A7A]">{config.enabled ? 'Live on your site' : 'Disabled'}</span>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] font-bold uppercase tracking-wider text-[#9B8AB0]">Title</label>
              <input value={config.title} onChange={(e) => setConfig({ ...config, title: e.target.value })} data-testid="widget-title"
                className="w-full bg-white border border-[#E8E0F5] px-3 py-2 rounded-md text-sm mt-1" />
            </div>
            <div>
              <label className="text-[10px] font-bold uppercase tracking-wider text-[#9B8AB0]">Button label</label>
              <input value={config.button_label} onChange={(e) => setConfig({ ...config, button_label: e.target.value })} data-testid="widget-button"
                className="w-full bg-white border border-[#E8E0F5] px-3 py-2 rounded-md text-sm mt-1" />
            </div>
          </div>

          <div>
            <label className="text-[10px] font-bold uppercase tracking-wider text-[#9B8AB0]">Subtitle</label>
            <input value={config.subtitle} onChange={(e) => setConfig({ ...config, subtitle: e.target.value })} data-testid="widget-subtitle"
              className="w-full bg-white border border-[#E8E0F5] px-3 py-2 rounded-md text-sm mt-1" />
          </div>

          <div>
            <label className="text-[10px] font-bold uppercase tracking-wider text-[#9B8AB0]">Accent colour</label>
            <div className="flex items-center gap-2 mt-1">
              <input type="color" value={config.accent_color} onChange={(e) => setConfig({ ...config, accent_color: e.target.value })} data-testid="widget-color" className="w-12 h-9 rounded cursor-pointer" />
              <input value={config.accent_color} onChange={(e) => setConfig({ ...config, accent_color: e.target.value })} className="flex-1 bg-white border border-[#E8E0F5] px-3 py-2 rounded-md text-sm font-mono" />
            </div>
          </div>

          <div>
            <label className="text-[10px] font-bold uppercase tracking-wider text-[#9B8AB0] mb-1.5 block">Fields to show</label>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(FIELD_LABELS).map(([key, lbl]) => {
                const active = (config.fields || []).includes(key);
                return (
                  <button key={key} onClick={() => toggleField(key)} data-testid={`widget-field-${key}`}
                    className={`px-2.5 py-1 rounded-md text-xs font-bold border transition-all ${active ? 'bg-[#7C35DC] text-white border-[#7C35DC]' : 'bg-white text-[#5A4A7A] border-[#E8E0F5] hover:border-[#7C35DC]/30'}`}>
                    {lbl}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="pt-3 border-t border-[#F0ECF9] space-y-2">
            <label className="flex items-center gap-2 text-xs text-[#5A4A7A]">
              <input type="checkbox" checked={config.require_consent} onChange={(e) => setConfig({ ...config, require_consent: e.target.checked })} data-testid="widget-consent-required" />
              Require consent checkbox (recommended)
            </label>
            {config.require_consent && (
              <input value={config.consent_text} onChange={(e) => setConfig({ ...config, consent_text: e.target.value })} data-testid="widget-consent-text"
                className="w-full bg-white border border-[#E8E0F5] px-3 py-2 rounded-md text-xs" placeholder="Consent text shown to visitors" />
            )}
          </div>

          <div className="pt-3 border-t border-[#F0ECF9]">
            <label className="text-[10px] font-bold uppercase tracking-wider text-[#9B8AB0]">Allowed origins (optional)</label>
            <textarea
              rows={2}
              value={(config.allowed_origins || []).join('\n')}
              onChange={(e) => setConfig({ ...config, allowed_origins: e.target.value.split('\n').map((l) => l.trim()).filter(Boolean) })}
              data-testid="widget-allowed-origins"
              placeholder="https://yourwebsite.com&#10;https://www.yourwebsite.com"
              className="w-full bg-white border border-[#E8E0F5] px-3 py-2 rounded-md text-xs font-mono mt-1 resize-none"
            />
            <p className="text-[10px] text-[#9B8AB0] mt-1">Leave empty to accept submissions from any site (less secure).</p>
          </div>

          <div className="flex items-center justify-end gap-2 pt-3">
            <button onClick={() => setShowPreview(!showPreview)} data-testid="widget-preview-toggle"
              className="inline-flex items-center gap-1.5 px-3 py-2 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-lg text-xs font-bold">
              <Eye size={12} weight="bold" /> {showPreview ? 'Hide preview' : 'Preview'}
            </button>
            <button onClick={save} disabled={saving} data-testid="widget-save"
              className="inline-flex items-center gap-1.5 px-4 py-2 btn-gradient rounded-lg text-xs font-bold disabled:opacity-40"
              style={{ fontFamily: 'Plus Jakarta Sans' }}>
              <FloppyDisk size={12} weight="bold" /> {saving ? 'Saving…' : 'Save settings'}
            </button>
          </div>
        </div>

        {/* Embed code + preview */}
        <div className="space-y-4">
          <div className="bg-[#1A0A2E] rounded-xl p-5 text-white" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="embed-snippet-card">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-extrabold" style={{ fontFamily: 'Plus Jakarta Sans' }}>Embed code</h3>
              <button onClick={copy} data-testid="embed-copy"
                className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-[#7C35DC] rounded text-xs font-bold hover:bg-[#6B28C8]">
                {copied ? <><CheckCircle size={11} weight="fill" /> Copied</> : <><Copy size={11} /> Copy</>}
              </button>
            </div>
            <pre className="text-[11px] text-[#C9B6FF] font-mono whitespace-pre-wrap break-all overflow-y-auto max-h-56 leading-relaxed">{snippet}</pre>
            <p className="text-[10px] text-[#9B8AB0] mt-3">Paste this snippet inside the <code className="text-[#C044E0]">{'<head>'}</code> of every page where you want the widget to appear.</p>
          </div>

          {showPreview && (
            <div className="bg-white border border-[#E8E0F5] rounded-xl p-4" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="widget-preview">
              <div className="rounded-lg overflow-hidden border border-[#E8E0F5]">
                <div className="p-4 text-white" style={{ background: `linear-gradient(135deg, ${config.accent_color} 0%, #C044E0 100%)` }}>
                  <h4 className="text-base font-extrabold">{config.title}</h4>
                  {config.subtitle && <p className="text-xs opacity-90 mt-0.5">{config.subtitle}</p>}
                </div>
                <div className="p-3 space-y-2 bg-[#FAFAFA]">
                  {(config.fields || []).map((f) => (
                    <div key={f}>
                      <label className="text-[9px] font-bold uppercase tracking-wider text-[#9B8AB0]">{FIELD_LABELS[f] || f}</label>
                      {f === 'message' ? (
                        <textarea disabled className="w-full bg-white border border-[#E8E0F5] px-2 py-1.5 rounded text-xs mt-0.5" rows={2}></textarea>
                      ) : (
                        <input disabled className="w-full bg-white border border-[#E8E0F5] px-2 py-1.5 rounded text-xs mt-0.5" />
                      )}
                    </div>
                  ))}
                  {config.require_consent && <label className="flex items-start gap-1.5 text-[10px] text-[#5A4A7A] mt-2"><input type="checkbox" disabled /> {config.consent_text}</label>}
                  <button disabled className="w-full text-white text-xs font-bold py-2 rounded mt-2" style={{ background: config.accent_color }}>{config.button_label}</button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default LeadCapture;
