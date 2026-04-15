import React, { useState, useEffect } from 'react';
import api from '../config/api';
import { useAuth } from '../context/AuthContext';
import { User, ShieldCheck, Envelope, Clock, Gear } from '@phosphor-icons/react';

const Settings = () => {
  const { user } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('team');

  useEffect(() => { fetchUsers(); }, []);

  const fetchUsers = async () => {
    try {
      const res = await api.get('/api/users');
      setUsers(res.data.users);
    } catch (err) {
      console.error('Failed to fetch users', err);
    } finally {
      setLoading(false);
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
        <p className="text-sm text-[#A3A3A3] mt-1">Team management and workspace configuration</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-[#141414] border border-[#262626] rounded-lg p-1 w-fit" data-testid="settings-tabs">
        {[
          { id: 'team', label: 'Team', icon: User },
          { id: 'workspace', label: 'Workspace', icon: Gear },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${activeTab === tab.id ? 'bg-[#0055FF] text-white' : 'text-[#A3A3A3] hover:text-white'}`}
            data-testid={`settings-tab-${tab.id}`}
          >
            <tab.icon size={16} /> {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'team' && (
        <div className="space-y-4">
          {/* Team Members */}
          <div className="bg-[#141414] border border-[#262626] rounded-lg" data-testid="team-members-list">
            <div className="p-6 border-b border-[#262626]">
              <h3 className="text-lg font-semibold text-white">Team Members</h3>
              <p className="text-sm text-[#A3A3A3] mt-1">{users.length} members</p>
            </div>
            <div className="divide-y divide-[#262626]">
              {users.map((member, index) => (
                <div key={index} className="p-6 flex items-center justify-between hover:bg-[#1E1E1E] transition-colors" data-testid={`team-member-${member.email}`}>
                  <div className="flex items-center gap-4">
                    <img
                      src={member.avatar_url || `https://ui-avatars.com/api/?name=${member.full_name}`}
                      alt={member.full_name}
                      className="w-10 h-10 rounded-full"
                    />
                    <div>
                      <div className="text-sm font-medium text-white">{member.full_name}</div>
                      <div className="text-xs text-[#737373] font-mono">{member.email}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-xs text-[#A3A3A3]">{member.team}</span>
                    <span className={roleBadge(member.role)}>{member.role.replace('_', ' ')}</span>
                    <div className={`w-2 h-2 rounded-full ${member.is_active ? 'bg-[#10B981]' : 'bg-[#737373]'}`}></div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'workspace' && (
        <div className="space-y-4">
          {/* Workspace Info */}
          <div className="bg-[#141414] border border-[#262626] rounded-lg p-6" data-testid="workspace-info">
            <h3 className="text-lg font-semibold text-white mb-4">Workspace Settings</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-[0.2em] text-[#737373] mb-2">Workspace Name</label>
                <input type="text" defaultValue="GenLeadAI" className="w-full max-w-md bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2.5 rounded-md text-sm" data-testid="workspace-name-input" />
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase tracking-[0.2em] text-[#737373] mb-2">ICP Definition</label>
                <textarea
                  rows={4}
                  defaultValue="Target: SaaS companies with $1M-$10M ARR, B2B focused, with 50-500 employees, looking to scale their growth systems."
                  className="w-full max-w-lg bg-[#0A0A0A] border border-[#262626] text-white px-3 py-2.5 rounded-md text-sm resize-none"
                  data-testid="icp-definition-input"
                />
              </div>
            </div>
          </div>

          {/* API Keys */}
          <div className="bg-[#141414] border border-[#262626] rounded-lg p-6" data-testid="api-keys-section">
            <h3 className="text-lg font-semibold text-white mb-4">API Configuration</h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 bg-[#0A0A0A] rounded-lg">
                <div>
                  <div className="text-sm font-medium text-white">AI Scoring (Claude API)</div>
                  <div className="text-xs text-[#737373]">Emergent LLM Key</div>
                </div>
                <span className="px-2 py-0.5 text-xs font-medium uppercase tracking-wider rounded-sm border bg-[#10B981]/10 text-[#10B981] border-[#10B981]/30">Connected</span>
              </div>
              <div className="flex items-center justify-between p-3 bg-[#0A0A0A] rounded-lg">
                <div>
                  <div className="text-sm font-medium text-white">Email (Resend)</div>
                  <div className="text-xs text-[#737373]">Transactional email service</div>
                </div>
                <span className="px-2 py-0.5 text-xs font-medium uppercase tracking-wider rounded-sm border bg-[#10B981]/10 text-[#10B981] border-[#10B981]/30">Connected</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Settings;
