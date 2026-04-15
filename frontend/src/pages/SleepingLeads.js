import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../config/api';
import { Moon, Rocket, Lightning, ArrowRight, X, Warning, WarningCircle } from '@phosphor-icons/react';

const SleepingLeads = () => {
  const navigate = useNavigate();
  const [leads, setLeads] = useState([]);
  const [segments, setSegments] = useState({});
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('all');
  const [showRevival, setShowRevival] = useState(false);
  const [selectedIds, setSelectedIds] = useState(new Set());

  useEffect(() => { fetchSleeping(); }, []);
  const fetchSleeping = async () => {
    try { const res = await api.get('/api/leads/sleeping?threshold_days=14'); setLeads(res.data.leads || []); setSegments(res.data.segments || {}); }
    catch(e) { console.error(e); }
    finally { setLoading(false); }
  };

  const filtered = activeTab === 'all' ? leads : leads.filter(l => l._segment === activeTab);
  const toggleSelect = (id) => { setSelectedIds(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; }); };
  const selectAll = () => { filtered.forEach(l => selectedIds.add(l.id)); setSelectedIds(new Set(selectedIds)); };
  const tierColor = { hot: '#7C35DC', warm: '#D97706', cold: '#94A3B8' };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-[#9B8AB0] text-sm">Loading sleeping leads...</div></div>;

  return (
    <div data-testid="sleeping-leads-page" className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-[#F4F0FF] border border-[#E0D4F7]">
            <Moon size={22} className="text-[#7C35DC]" weight="duotone" />
          </div>
          <div>
            <h1 className="text-3xl font-extrabold text-[#1A0A2E] tracking-tight" style={{ fontFamily: 'Plus Jakarta Sans' }}>Sleeping Leads</h1>
            <p className="text-sm text-[#5A4A7A] mt-0.5">Leads with no activity in 14+ days</p>
          </div>
        </div>
        {selectedIds.size > 0 && (
          <button onClick={() => setShowRevival(true)} data-testid="launch-revival-btn" className="flex items-center gap-2 btn-gradient px-4 py-2 rounded-lg text-sm font-semibold" style={{ fontFamily: 'Plus Jakarta Sans' }}>
            <Rocket size={16} weight="fill" /> Revive {selectedIds.size} Leads
          </button>
        )}
      </div>

      {/* Alert Banner */}
      {leads.length > 0 && (
        <div className="bg-[#FEF3C7] border border-[#D97706]/20 rounded-xl p-4 flex items-start gap-3" data-testid="sleeping-banner">
          <WarningCircle size={20} className="text-[#D97706] shrink-0 mt-0.5" weight="fill" />
          <div>
            <p className="text-sm font-semibold text-[#92400E]">You have {leads.length} sleeping leads.</p>
            <p className="text-xs text-[#92400E]/80 mt-0.5">ARIA can re-engage them with personalized messages. Select leads and launch a revival campaign.</p>
          </div>
        </div>
      )}

      {/* Segment Tabs */}
      <div className="flex gap-1 bg-white border border-[#E8E0F5] rounded-xl p-1 w-fit" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="sleeping-tabs">
        {[
          { id: 'all', label: `All (${leads.length})` },
          { id: 'sleeping', label: `Sleeping 14-30d (${segments.sleeping || 0})` },
          { id: 'at_risk', label: `At Risk 30-60d (${segments.at_risk || 0})` },
          { id: 'cold_vault', label: `Cold Vault 60d+ (${segments.cold_vault || 0})` },
        ].map(tab => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${activeTab === tab.id ? 'text-white' : 'text-[#5A4A7A] hover:text-[#7C35DC] hover:bg-[#F9F5FF]'}`}
            style={activeTab === tab.id ? { background: 'var(--gradient-brand)', fontFamily: 'Plus Jakarta Sans' } : { fontFamily: 'Plus Jakarta Sans' }}
            data-testid={`sleeping-tab-${tab.id}`}>{tab.label}</button>
        ))}
      </div>

      {/* Select All */}
      <div className="flex items-center gap-3">
        <button onClick={selectAll} className="text-xs text-[#7C35DC] hover:text-[#6B28C8] font-semibold" data-testid="select-all-sleeping">Select All ({filtered.length})</button>
        {selectedIds.size > 0 && <button onClick={() => setSelectedIds(new Set())} className="text-xs text-[#DC2626] hover:text-[#DC2626]/80 font-medium">Clear Selection</button>}
      </div>

      {/* Leads Table */}
      <div className="bg-white border border-[#E8E0F5] rounded-xl overflow-hidden" style={{ boxShadow: 'var(--shadow-card)' }} data-testid="sleeping-leads-table">
        {filtered.length === 0 ? (
          <div className="p-12 text-center"><Moon size={48} className="text-[#9B8AB0] mx-auto mb-4" weight="duotone" /><p className="text-sm text-[#5A4A7A]">No sleeping leads in this segment.</p></div>
        ) : (
          <table className="w-full text-sm text-left">
            <thead>
              <tr className="bg-[#F4F0FF]">
                <th className="px-4 py-3 w-10"></th>
                {['Name', 'Company', 'Days Asleep', 'Source', 'ICP Score', 'Segment', 'Status'].map(h => (
                  <th key={h} className="px-4 py-3 text-xs font-semibold uppercase tracking-[0.15em] text-[#5A4A7A]" style={{ fontFamily: 'Plus Jakarta Sans' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map(lead => (
                <tr key={lead.id} className="border-b border-[#F0ECF9] hover:bg-[#F9F5FF] transition-colors" data-testid={`sleeping-row-${lead.id}`}>
                  <td className="px-4 py-3">
                    <input type="checkbox" checked={selectedIds.has(lead.id)} onChange={() => toggleSelect(lead.id)} className="w-4 h-4 rounded border-[#E8E0F5] text-[#7C35DC] focus:ring-[#7C35DC]" />
                  </td>
                  <td className="px-4 py-3 cursor-pointer" onClick={() => navigate(`/leads/${lead.id}`)}>
                    <div className="font-semibold text-[#1A0A2E] hover:text-[#7C35DC]">{lead.first_name} {lead.last_name}</div>
                    <div className="text-xs text-[#9B8AB0] font-mono">{lead.email}</div>
                  </td>
                  <td className="px-4 py-3 text-[#5A4A7A]">{lead.company_name || '—'}</td>
                  <td className="px-4 py-3">
                    <span className={`font-mono font-bold ${lead._days_asleep >= 60 ? 'text-[#DC2626]' : lead._days_asleep >= 30 ? 'text-[#D97706]' : 'text-[#5A4A7A]'}`}>{lead._days_asleep}d</span>
                  </td>
                  <td className="px-4 py-3 text-[#5A4A7A] text-xs">{lead.source_channel?.replace('_', ' ')}</td>
                  <td className="px-4 py-3"><span className="font-mono font-bold" style={{ color: tierColor[lead.icp_tier] }}>{lead.icp_score}</span></td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 text-xs font-semibold uppercase rounded border ${lead._segment === 'cold_vault' ? 'bg-[#FEE2E2] text-[#DC2626] border-[#DC2626]/20' : lead._segment === 'at_risk' ? 'bg-[#FEF3C7] text-[#D97706] border-[#D97706]/30' : 'bg-[#F4F0FF] text-[#7C35DC] border-[#7C35DC]/20'}`}>
                      {lead._segment?.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-[#9B8AB0] text-xs">{lead.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Revival Campaign Modal */}
      {showRevival && <RevivalModal selectedIds={[...selectedIds]} onClose={() => setShowRevival(false)} onSuccess={() => { setShowRevival(false); setSelectedIds(new Set()); fetchSleeping(); }} />}
    </div>
  );
};

const RevivalModal = ({ selectedIds, onClose, onSuccess }) => {
  const [angle, setAngle] = useState('check_in');
  const [channel, setChannel] = useState('email');
  const [step, setStep] = useState(1);
  const [previews, setPreviews] = useState([]);
  const [launching, setLaunching] = useState(false);
  const [result, setResult] = useState(null);

  const angles = [
    { id: 'check_in', label: 'Check-in', desc: 'Warm friendly re-open' },
    { id: 'new_value', label: 'New Value', desc: 'Share an asset or insight' },
    { id: 'limited_time', label: 'Limited Time', desc: 'Urgency/offer angle' },
    { id: 'direct_ask', label: 'Direct Ask', desc: 'Straight to booking' },
  ];

  const launch = async () => {
    setLaunching(true);
    try {
      const res = await api.post('/api/leads/revival-campaign', { lead_ids: selectedIds, angle, channel });
      setResult(res.data);
      setStep(3);
    } catch(e) { console.error(e); }
    finally { setLaunching(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/20 backdrop-blur-sm flex items-center justify-center z-50 p-4" data-testid="revival-modal">
      <div className="bg-white border border-[#E8E0F5] rounded-2xl w-full max-w-xl" style={{ boxShadow: 'var(--shadow-hover)' }}>
        <div className="flex items-center justify-between p-6 border-b border-[#E8E0F5]">
          <div className="flex items-center gap-2">
            <Rocket size={20} className="text-[#7C35DC]" weight="fill" />
            <h2 className="text-lg font-bold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Launch Revival Campaign</h2>
          </div>
          <button onClick={onClose} className="text-[#9B8AB0] hover:text-[#7C35DC]"><X size={24} /></button>
        </div>

        <div className="p-6">
          {step === 1 && (
            <div className="space-y-4">
              <p className="text-sm text-[#5A4A7A]">Re-engaging <span className="font-bold text-[#7C35DC]">{selectedIds.length}</span> sleeping leads</p>

              <div>
                <label className="block text-sm font-semibold text-[#1A0A2E] mb-2" style={{ fontFamily: 'Plus Jakarta Sans' }}>Revival Angle</label>
                <div className="grid grid-cols-2 gap-2">
                  {angles.map(a => (
                    <button key={a.id} onClick={() => setAngle(a.id)}
                      className={`p-3 rounded-lg border text-left transition-all ${angle === a.id ? 'bg-[#F4F0FF] border-[#7C35DC]/30 text-[#7C35DC]' : 'bg-white border-[#E8E0F5] text-[#5A4A7A] hover:bg-[#F9F5FF]'}`}
                      data-testid={`angle-${a.id}`}>
                      <div className="text-sm font-semibold">{a.label}</div>
                      <div className="text-xs mt-0.5 opacity-75">{a.desc}</div>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-semibold text-[#1A0A2E] mb-2" style={{ fontFamily: 'Plus Jakarta Sans' }}>Channel</label>
                <div className="flex gap-2">
                  {[{ id: 'email', label: 'Email' }, { id: 'whatsapp', label: 'WhatsApp' }, { id: 'both', label: 'Both' }].map(ch => (
                    <button key={ch.id} onClick={() => setChannel(ch.id)}
                      className={`px-4 py-2 rounded-lg border text-sm font-medium transition-all ${channel === ch.id ? 'bg-[#F4F0FF] border-[#7C35DC]/30 text-[#7C35DC]' : 'bg-white border-[#E8E0F5] text-[#5A4A7A] hover:bg-[#F9F5FF]'}`}
                      data-testid={`channel-${ch.id}`}>{ch.label}{ch.id === 'whatsapp' && <span className="text-xs ml-1 text-[#9B8AB0]">(simulated)</span>}</button>
                  ))}
                </div>
              </div>

              <button onClick={() => setStep(2)} className="w-full btn-gradient py-2.5 rounded-lg text-sm font-semibold" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid="revival-next-btn">
                Preview & Launch
              </button>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <div className="bg-[#F4F0FF] border border-[#E0D4F7] rounded-xl p-4">
                <p className="text-sm text-[#7C35DC] font-semibold">Ready to re-engage {selectedIds.length} leads</p>
                <p className="text-xs text-[#5A4A7A] mt-1">Angle: <span className="font-semibold">{angles.find(a => a.id === angle)?.label}</span> | Channel: <span className="font-semibold capitalize">{channel}</span></p>
                <p className="text-xs text-[#5A4A7A] mt-1">ARIA will handle all replies automatically.</p>
              </div>
              <div className="flex gap-3">
                <button onClick={() => setStep(1)} className="flex-1 px-4 py-2.5 bg-white border border-[#E8E0F5] text-[#5A4A7A] rounded-lg hover:bg-[#F9F5FF] text-sm font-medium">Back</button>
                <button onClick={launch} disabled={launching} className="flex-1 btn-gradient py-2.5 rounded-lg text-sm font-semibold disabled:opacity-50" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid="revival-launch-btn">
                  {launching ? 'Launching...' : `Launch Revival`}
                </button>
              </div>
            </div>
          )}

          {step === 3 && result && (
            <div className="space-y-4 text-center">
              <div className="w-16 h-16 rounded-full flex items-center justify-center mx-auto" style={{ background: 'var(--gradient-brand)' }}>
                <Rocket size={32} className="text-white" weight="fill" />
              </div>
              <h3 className="text-lg font-bold text-[#1A0A2E]" style={{ fontFamily: 'Plus Jakarta Sans' }}>Revival Launched!</h3>
              <p className="text-sm text-[#5A4A7A]">Sent to <span className="font-bold text-[#7C35DC]">{result.sent}</span> leads. {result.failed > 0 && <span className="text-[#DC2626]">{result.failed} failed.</span>}</p>
              <button onClick={onSuccess} className="btn-gradient px-6 py-2.5 rounded-lg text-sm font-semibold" style={{ fontFamily: 'Plus Jakarta Sans' }} data-testid="revival-done-btn">Done</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SleepingLeads;
