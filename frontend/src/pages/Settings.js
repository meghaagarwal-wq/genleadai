import React, { useState, useEffect } from 'react';
import api from '../config/api';
import { useAuth } from '../context/AuthContext';
import { User, Gear, Robot, FileArrowUp, Trash, ToggleLeft, ToggleRight, CloudArrowUp, File, Key, Code, Copy, CheckCircle } from '@phosphor-icons/react';

const Settings = () => {
  const { user } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('team');
  const [ariaSettings, setAriaSettings] = useState(null);
  const [assets, setAssets] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [savingSettings, setSavingSettings] = useState(false);
  const [apiKeys, setApiKeys] = useState([]);
  const [newKeyName, setNewKeyName] = useState('');
  const [newKey, setNewKey] = useState(null);
  const [embedCode, setEmbedCode] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetchUsers();
    fetchAriaSettings();
    fetchAssets();
    fetchApiKeys();
  }, []);

  const fetchUsers = async () => {
    try { const res = await api.get('/api/users'); setUsers(res.data.users); }
    catch (err) { console.error(err); } finally { setLoading(false); }
  };

  const fetchAriaSettings = async () => {
    try { const res = await api.get('/api/aria/settings'); setAriaSettings(res.data); }
    catch (err) { console.error(err); }
  };

  const saveAriaSettings = async () => {
    setSavingSettings(true);
    try { await api.put('/api/aria/settings', ariaSettings); }
    catch (err) { console.error(err); } finally { setSavingSettings(false); }
  };

  const fetchAssets = async () => {
    try { const res = await api.get('/api/assets'); setAssets(res.data.assets); }
    catch (err) { console.error(err); }
  };

  const fetchApiKeys = async () => {
    try { const res = await api.get('/api/settings/api-keys'); setApiKeys(res.data.keys); }
    catch (err) { console.error(err); }
  };

  const createApiKey = async () => {
    if (!newKeyName.trim()) return;
    try {
      const res = await api.post('/api/settings/api-keys', { name: newKeyName });
      setNewKey(res.data.key);
      setNewKeyName('');
      await fetchApiKeys();
    } catch (err) { console.error(err); }
  };

  const fetchEmbedCode = async () => {
    try { const res = await api.get('/api/form/embed-code'); setEmbedCode(res.data); }
    catch (err) { console.error(err); }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('asset_type', 'brand_deck');
      formData.append('send_in_first_touch', 'true');
      await api.post('/api/assets/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      await fetchAssets();
    } catch (err) {
      console.error('Upload failed', err);
    } finally {
      setUploading(false);
    }
  };

  const toggleAsset = async (assetId) => {
    try {
      await api.patch(`/api/assets/${assetId}`);
      await fetchAssets();
    } catch (err) {
      console.error('Toggle failed', err);
    }
  };

  const deleteAsset = async (assetId) => {
    try {
      await api.delete(`/api/assets/${assetId}`);
      await fetchAssets();
    } catch (err) {
      console.error('Delete failed', err);
    }
  };

  const roleBadge = (role) => {
    const styles = {
      admin: 'bg-[#FF3B30]/10 text-[#FF3B30] border-[#FF3B30]/30',
      manager: 'bg-[#F59E0B]/10 text-[#F59E0B] border-[#F59E0B]/30',
      sales_rep: 'bg-[#0055FF]/10 text-[#0055FF] border-[#0055FF]/30',
      viewer: 'bg-[#737373]/10 text-[#737373] border-[#737373]/30',
    };
    return `px-2 py-0.5 text-xs font-medium uppercase tracking-wider rounded-sm border ${styles[role] || styles.viewer}`;
  };

  return (
    <div data-testid="settings-page" className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white tracking-tight">Settings</h1>
        <p className="text-sm text-[#A3A3A3] mt-1">Team, AI agent, and workspace configuration</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-[#141414] border border-[#262626] rounded-lg p-1 w-fit" data-testid="settings-tabs">
        {[
          { id: 'team', label: 'Team', icon: User },
          { id: 'aria', label: 'ARIA Agent', icon: Robot },
          { id: 'assets', label: 'Asset Library', icon: FileArrowUp },
          { id: 'integrations', label: 'API & Forms', icon: Key },
          { id: 'workspace', label: 'Workspace', icon: Gear },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${activeTab === tab.id ? (tab.id === 'aria' ? 'bg-[#8B5CF6] text-white' : 'bg-[#0055FF] text-white') : 'text-[#A3A3A3] hover:text-white'}`}
            data-testid={`settings-tab-${tab.id}`}
          >
            <tab.icon size={16} /> {tab.label}
          </button>
        ))}
      </div>

      {/* Team Tab */}
      {activeTab === 'team' && (
        <div className="bg-[#141414] border border-[#262626] rounded-lg" data-testid="team-members-list">
          <div className="p-6 border-b border-[#262626]">
            <h3 className="text-lg font-semibold text-white">Team Members</h3>
            <p className="text-sm text-[#A3A3A3] mt-1">{users.length} members</p>
          </div>
          <div className="divide-y divide-[#262626]">
            {users.map((member, index) => (
              <div key={index} className="p-6 flex items-center justify-between hover:bg-[#1E1E1E] transition-colors" data-testid={`team-member-${member.email}`}>
                <div className="flex items-center gap-4">
                  <img src={member.avatar_url || `https://ui-avatars.com/api/?name=${member.full_name}`} alt={member.full_name} className="w-10 h-10 rounded-full" />
                  <div>
                    <div className="text-sm font-medium text-white">{member.full_name}</div>
                    <div className="text-xs text-[#737373] font-mono">{member.email}</div>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-xs text-[#A3A3A3]">{member.team}</span>
                  <span className={roleBadge(member.role)}>{member.role.replace('_', ' ')}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ARIA Agent Tab */}
      {activeTab === 'aria' && ariaSettings && (
        <div className="space-y-4">
          <div className="bg-[#141414] border border-[#262626] rounded-lg p-6" data-testid="aria-control-panel">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: '#8B5CF6', boxShadow: 'inset 0 0 12px rgba(139,92,246,0.3)' }}>
                  <Robot size={16} className="text-white" weight="fill" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-white">ARIA Control Panel</h3>
                  <p className="text-xs text-[#737373]">Configure the AI sales agent</p>
                </div>
              </div>
              <button
                onClick={() => setAriaSettings({...ariaSettings, enabled: !ariaSettings.enabled})}
                className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${ariaSettings.enabled ? 'bg-[#10B981]/10 text-[#10B981] border border-[#10B981]/30' : 'bg-[#FF3B30]/10 text-[#FF3B30] border border-[#FF3B30]/30'}`}
                data-testid="aria-toggle-btn"
              >
                {ariaSettings.enabled ? <ToggleRight size={20} weight="fill" /> : <ToggleLeft size={20} />}
                {ariaSettings.enabled ? 'Active' : 'Disabled'}
              </button>
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-[0.2em] text-[#737373] mb-2">Persona Name</label>
                  <input type="text" value={ariaSettings.persona_name} onChange={(e) => setAriaSettings({...ariaSettings, persona_name: e.target.value})} className="w-full bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2.5 rounded-md text-sm" data-testid="aria-persona-name-input" />
                </div>
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-[0.2em] text-[#737373] mb-2">Founder Name</label>
                  <input type="text" value={ariaSettings.founder_name} onChange={(e) => setAriaSettings({...ariaSettings, founder_name: e.target.value})} className="w-full bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2.5 rounded-md text-sm" data-testid="aria-founder-name-input" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-[0.2em] text-[#737373] mb-2">Company Name</label>
                  <input type="text" value={ariaSettings.company_name} onChange={(e) => setAriaSettings({...ariaSettings, company_name: e.target.value})} className="w-full bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2.5 rounded-md text-sm" data-testid="aria-company-name-input" />
                </div>
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-[0.2em] text-[#737373] mb-2">Max Messages Per Lead</label>
                  <input type="number" value={ariaSettings.max_messages_per_lead} onChange={(e) => setAriaSettings({...ariaSettings, max_messages_per_lead: parseInt(e.target.value)})} className="w-full bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2.5 rounded-md text-sm" data-testid="aria-max-messages-input" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-[0.2em] text-[#737373] mb-2">First Touch Delay (minutes)</label>
                  <input type="number" value={ariaSettings.first_touch_delay_minutes} onChange={(e) => setAriaSettings({...ariaSettings, first_touch_delay_minutes: parseInt(e.target.value)})} className="w-full bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2.5 rounded-md text-sm" data-testid="aria-first-touch-delay-input" />
                </div>
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-[0.2em] text-[#737373] mb-2">Follow-up Delay (hours)</label>
                  <input type="number" value={ariaSettings.followup_delay_hours} onChange={(e) => setAriaSettings({...ariaSettings, followup_delay_hours: parseInt(e.target.value)})} className="w-full bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2.5 rounded-md text-sm" data-testid="aria-followup-delay-input" />
                </div>
              </div>

              <button onClick={saveAriaSettings} disabled={savingSettings} className="px-6 py-2 bg-[#0055FF] text-white rounded-md hover:bg-[#0044CC] transition-colors text-sm font-medium disabled:opacity-50" data-testid="save-aria-settings-btn">
                {savingSettings ? 'Saving...' : 'Save Settings'}
              </button>
            </div>
          </div>

          {/* Calendly Config */}
          <div className="bg-[#141414] border border-[#262626] rounded-lg p-6" data-testid="calendly-config">
            <h3 className="text-lg font-semibold text-white mb-4">Calendly Integration</h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 bg-[#0A0A0A] rounded-lg">
                <div>
                  <div className="text-sm font-medium text-white">Calendly API</div>
                  <div className="text-xs text-[#737373]">Personal Access Token configured</div>
                </div>
                <span className="px-2 py-0.5 text-xs font-medium uppercase tracking-wider rounded-sm border bg-[#10B981]/10 text-[#10B981] border-[#10B981]/30">Connected</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Asset Library Tab */}
      {activeTab === 'assets' && (
        <div className="space-y-4">
          <div className="bg-[#141414] border border-[#262626] rounded-lg p-6" data-testid="asset-library">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-lg font-semibold text-white">Asset Library</h3>
                <p className="text-xs text-[#737373] mt-1">Upload brand deck, portfolio, and other assets for ARIA's first touch</p>
              </div>
              <label className="flex items-center gap-2 px-4 py-2 bg-[#0055FF] text-white rounded-md hover:bg-[#0044CC] transition-colors text-sm font-medium cursor-pointer" data-testid="upload-asset-btn">
                <CloudArrowUp size={16} />
                {uploading ? 'Uploading...' : 'Upload Asset'}
                <input type="file" accept=".pdf,.doc,.docx,.png,.jpg,.jpeg" onChange={handleUpload} className="hidden" />
              </label>
            </div>

            {assets.length === 0 ? (
              <div className="border-2 border-dashed border-[#262626] rounded-lg p-12 text-center">
                <FileArrowUp size={48} className="text-[#737373] mx-auto mb-4" />
                <h4 className="text-sm font-semibold text-white mb-2">No assets uploaded</h4>
                <p className="text-xs text-[#A3A3A3] max-w-md mx-auto">ARIA will send messages without attachments until you upload your Brand Deck and Portfolio here.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {assets.map(asset => (
                  <div key={asset.id} className="flex items-center justify-between p-4 bg-[#0A0A0A] rounded-lg border border-[#262626]" data-testid={`asset-${asset.id}`}>
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-[#262626] rounded-lg flex items-center justify-center">
                        <File size={20} className="text-[#A3A3A3]" weight="duotone" />
                      </div>
                      <div>
                        <div className="text-sm font-medium text-white">{asset.name}</div>
                        <div className="flex items-center gap-2 text-xs text-[#737373]">
                          <span>{asset.asset_type?.replace('_', ' ')}</span>
                          <span>-</span>
                          <span>{asset.file_size_kb?.toFixed(1)} KB</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => toggleAsset(asset.id)}
                        className={`flex items-center gap-1 px-3 py-1.5 rounded-md text-xs transition-colors ${asset.send_in_first_touch ? 'bg-[#10B981]/10 text-[#10B981] border border-[#10B981]/30' : 'bg-[#262626] text-[#737373] border border-[#262626]'}`}
                        data-testid={`toggle-asset-${asset.id}`}
                      >
                        {asset.send_in_first_touch ? <ToggleRight size={16} weight="fill" /> : <ToggleLeft size={16} />}
                        First Touch
                      </button>
                      <button onClick={() => deleteAsset(asset.id)} className="p-1.5 text-[#FF3B30] hover:bg-[#FF3B30]/10 rounded transition-colors" data-testid={`delete-asset-${asset.id}`}>
                        <Trash size={16} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Integrations Tab */}
      {activeTab === 'integrations' && (
        <div className="space-y-4">
          {/* API Keys */}
          <div className="bg-white border border-[#E8E0F5] rounded-xl p-6" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="api-keys-management">
            <h3 className="text-lg font-bold text-[#1A0A2E] mb-1" style={{ fontFamily: 'Plus Jakarta Sans' }}>API Keys</h3>
            <p className="text-xs text-[#5A4A7A] mb-4">Create API keys for external integrations (Zapier, Make, ad platforms)</p>

            <div className="flex gap-2 mb-4">
              <input type="text" value={newKeyName} onChange={(e) => setNewKeyName(e.target.value)} placeholder="Key name (e.g., Zapier, Meta Ads)" className="flex-1 bg-white border border-[#E8E0F5] text-[#1A0A2E] px-3 py-2 rounded-lg text-sm focus:border-[#7C35DC]" data-testid="new-key-name-input" />
              <button onClick={createApiKey} className="btn-gradient px-4 py-2 rounded-lg text-sm font-semibold" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid="create-key-btn">Create Key</button>
            </div>

            {newKey && (
              <div className="bg-[#DCFCE7] border border-[#16A34A]/20 rounded-lg p-4 mb-4" data-testid="new-key-display">
                <p className="text-sm font-semibold text-[#16A34A] mb-1">New API Key Created!</p>
                <p className="text-xs text-[#5A4A7A] mb-2">Copy this key now — it won't be shown again.</p>
                <div className="flex items-center gap-2">
                  <code className="flex-1 bg-white border border-[#E8E0F5] rounded-lg px-3 py-2 text-xs font-mono text-[#1A0A2E] select-all">{newKey}</code>
                  <button onClick={() => copyToClipboard(newKey)} className="p-2 bg-white border border-[#E8E0F5] rounded-lg hover:bg-[#F9F5FF] transition-all" data-testid="copy-key-btn">
                    {copied ? <CheckCircle size={16} className="text-[#16A34A]" /> : <Copy size={16} className="text-[#5A4A7A]" />}
                  </button>
                </div>
              </div>
            )}

            {apiKeys.length > 0 && (
              <div className="space-y-2">
                {apiKeys.map((k, i) => (
                  <div key={i} className="flex items-center justify-between p-3 bg-[#FAFAFA] rounded-lg border border-[#F0ECF9]">
                    <div>
                      <div className="text-sm font-medium text-[#1A0A2E]">{k.name}</div>
                      <div className="text-xs text-[#9B8AB0] font-mono">{k.key}</div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-[#9B8AB0]">{k.usage_count || 0} calls</span>
                      <span className={`px-2 py-0.5 text-xs font-semibold rounded border ${k.is_active ? 'bg-[#DCFCE7] text-[#16A34A] border-[#16A34A]/20' : 'bg-[#FEE2E2] text-[#DC2626] border-[#DC2626]/20'}`}>{k.is_active ? 'Active' : 'Revoked'}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="mt-4 p-4 bg-[#F4F0FF] rounded-lg border border-[#E0D4F7]">
              <p className="text-xs font-semibold text-[#7C35DC] mb-1">API Endpoint</p>
              <code className="text-xs font-mono text-[#5A4A7A]">POST /api/v1/leads</code>
              <p className="text-xs text-[#9B8AB0] mt-1">Include header: <code className="font-mono">X-API-Key: your_key</code></p>
            </div>
          </div>

          {/* Embeddable Form */}
          <div className="bg-white border border-[#E8E0F5] rounded-xl p-6" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="embed-form-section">
            <h3 className="text-lg font-bold text-[#1A0A2E] mb-1" style={{ fontFamily: 'Plus Jakarta Sans' }}>Embeddable Lead Form</h3>
            <p className="text-xs text-[#5A4A7A] mb-4">Paste this on your website to capture leads directly into GenLeadAI</p>

            {!embedCode ? (
              <button onClick={fetchEmbedCode} className="btn-gradient px-4 py-2 rounded-lg text-sm font-semibold" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid="generate-embed-btn">
                <Code size={16} className="inline mr-2" />Generate Embed Code
              </button>
            ) : (
              <div>
                <p className="text-xs text-[#5A4A7A] mb-2">{embedCode.instructions}</p>
                <div className="relative">
                  <pre className="bg-[#FAFAFA] border border-[#E8E0F5] rounded-lg p-4 text-xs font-mono text-[#5A4A7A] overflow-x-auto max-h-48">{embedCode.embed_code}</pre>
                  <button onClick={() => copyToClipboard(embedCode.embed_code)} className="absolute top-2 right-2 p-1.5 bg-white border border-[#E8E0F5] rounded-lg hover:bg-[#F9F5FF] transition-all" data-testid="copy-embed-btn">
                    {copied ? <CheckCircle size={14} className="text-[#16A34A]" /> : <Copy size={14} className="text-[#5A4A7A]" />}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Webhook URLs */}
          <div className="bg-white border border-[#E8E0F5] rounded-xl p-6" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="webhook-urls">
            <h3 className="text-lg font-bold text-[#1A0A2E] mb-1" style={{ fontFamily: 'Plus Jakarta Sans' }}>Webhook URLs</h3>
            <p className="text-xs text-[#5A4A7A] mb-4">Configure these in your external tools</p>
            <div className="space-y-3">
              {[
                { name: 'Calendly Webhook', url: '/api/webhooks/calendly', desc: 'Receives booking confirmations' },
                { name: 'Meta Lead Ads', url: '/api/webhooks/meta-leads', desc: 'Facebook/Instagram lead form submissions' },
                { name: 'Web Form', url: '/api/form/submit', desc: 'Public form endpoint (no auth needed)' },
              ].map(wh => (
                <div key={wh.name} className="flex items-center justify-between p-3 bg-[#FAFAFA] rounded-lg border border-[#F0ECF9]">
                  <div>
                    <div className="text-sm font-medium text-[#1A0A2E]">{wh.name}</div>
                    <div className="text-xs text-[#9B8AB0]">{wh.desc}</div>
                  </div>
                  <code className="text-xs font-mono text-[#7C35DC] bg-[#F4F0FF] px-2 py-1 rounded">{wh.url}</code>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Workspace Tab */}
      {activeTab === 'workspace' && (
        <div className="space-y-4">
          <div className="bg-[#141414] border border-[#262626] rounded-lg p-6" data-testid="workspace-info">
            <h3 className="text-lg font-semibold text-white mb-4">Workspace Settings</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-[0.2em] text-[#737373] mb-2">Workspace Name</label>
                <input type="text" defaultValue="GenLeadAI" className="w-full max-w-md bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2.5 rounded-md text-sm" data-testid="workspace-name-input" />
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase tracking-[0.2em] text-[#737373] mb-2">ICP Definition</label>
                <textarea rows={4} defaultValue="Target: SaaS companies with $1M-$10M ARR, B2B focused, with 50-500 employees, looking to scale their growth systems." className="w-full max-w-lg bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2.5 rounded-md text-sm resize-none" data-testid="icp-definition-input" />
              </div>
            </div>
          </div>

          <div className="bg-[#141414] border border-[#262626] rounded-lg p-6" data-testid="api-keys-section">
            <h3 className="text-lg font-semibold text-white mb-4">API Configuration</h3>
            <div className="space-y-3">
              {[
                { name: 'AI Scoring (Claude API)', desc: 'Emergent LLM Key', connected: true },
                { name: 'Email (Resend)', desc: 'Transactional email service', connected: true },
                { name: 'Calendly', desc: 'Meeting booking integration', connected: true },
                { name: 'Object Storage', desc: 'Emergent Object Storage', connected: true },
              ].map(item => (
                <div key={item.name} className="flex items-center justify-between p-3 bg-[#0A0A0A] rounded-lg">
                  <div>
                    <div className="text-sm font-medium text-white">{item.name}</div>
                    <div className="text-xs text-[#737373]">{item.desc}</div>
                  </div>
                  <span className={`px-2 py-0.5 text-xs font-medium uppercase tracking-wider rounded-sm border ${item.connected ? 'bg-[#10B981]/10 text-[#10B981] border-[#10B981]/30' : 'bg-[#FF3B30]/10 text-[#FF3B30] border-[#FF3B30]/30'}`}>
                    {item.connected ? 'Connected' : 'Not configured'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Settings;
