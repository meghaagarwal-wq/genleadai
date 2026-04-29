import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../config/api';
import { DragDropContext, Droppable, Draggable } from 'react-beautiful-dnd';
import { Buildings } from '@phosphor-icons/react';

const PIPELINE_STAGES = {
  B2B: ['new','contacted','qualified','proposal_sent','negotiation','won','lost'],
  B2C: ['new','contacted','qualified','proposal_sent','won','lost'],
};
const STAGE_COLORS = { new:'#7C35DC', contacted:'#A855F7', qualified:'#16A34A', proposal_sent:'#D97706', negotiation:'#D97706', won:'#16A34A', lost:'#DC2626' };

const Pipeline = () => {
  const navigate = useNavigate();
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [pipelineType, setPipelineType] = useState('B2B');

  useEffect(() => { fetchLeads(); }, [pipelineType]);
  const fetchLeads = async () => {
    setLoading(true);
    try { const res = await api.get('/api/leads', { params: { limit:200, lead_type:pipelineType } }); setLeads(res.data.leads); }
    catch(err) { console.error(err); }
    finally { setLoading(false); }
  };

  const stages = PIPELINE_STAGES[pipelineType];
  const grouped = {}; stages.forEach(s => { grouped[s] = []; });
  leads.forEach(l => { if(grouped[l.status]) grouped[l.status].push(l); else if(grouped['new']) grouped['new'].push(l); });

  const fmtInr = (n) => {
    if (!n) return '—';
    if (n >= 10000000) return `₹${(n/10000000).toFixed(1)}Cr`;
    if (n >= 100000) return `₹${(n/100000).toFixed(1)}L`;
    if (n >= 1000) return `₹${Math.round(n/1000)}K`;
    return `₹${n}`;
  };
  const stageValue = (stage) => grouped[stage].reduce((sum, l) => sum + (l.deal_value || 0), 0);
  const totalPipelineValue = stages.filter(s => !['won','lost'].includes(s)).reduce((sum, s) => sum + stageValue(s), 0);

  const handleDragEnd = async (result) => {
    if(!result.destination) return;
    const { draggableId, destination } = result;
    setLeads(prev => prev.map(l => l.id === draggableId ? {...l, status:destination.droppableId} : l));
    try { await api.patch(`/api/leads/${draggableId}`, { status: destination.droppableId }); } catch(err) { fetchLeads(); }
  };

  return (
    <div data-testid="pipeline-page" className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-extrabold text-[#1A0A2E] tracking-tight" style={{ fontFamily:'Plus Jakarta Sans' }}>Pipeline</h1>
          <p className="text-sm text-[#5A4A7A] mt-1">Drag leads across stages — pipeline value updates live.</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="hidden md:flex items-center gap-2 px-4 py-2 bg-white border border-[#E8E0F5] rounded-xl" style={{ boxShadow:'var(--shadow-card)' }} data-testid="pipeline-total-value">
            <span className="text-xs font-bold uppercase tracking-[0.15em] text-[#9B8AB0]" style={{ fontFamily:'Plus Jakarta Sans' }}>Active pipeline</span>
            <span className="text-base font-extrabold text-[#7C35DC]" style={{ fontFamily:'Plus Jakarta Sans' }}>{fmtInr(totalPipelineValue)}</span>
          </div>
          <div className="flex items-center gap-1 bg-white border border-[#E8E0F5] rounded-xl p-1" style={{ boxShadow:'var(--shadow-card)' }} data-testid="pipeline-type-toggle">
            {['B2B','B2C'].map(type => (
              <button key={type} onClick={() => setPipelineType(type)} className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all ${pipelineType === type ? 'text-white' : 'text-[#5A4A7A] hover:text-[#7C35DC] hover:bg-[#F9F5FF]'}`} style={pipelineType === type ? { background:'var(--gradient-brand)', fontFamily:'Plus Jakarta Sans' } : { fontFamily:'Plus Jakarta Sans' }} data-testid={`pipeline-${type.toLowerCase()}-btn`}>{type}</button>
            ))}
          </div>
        </div>
      </div>

      {loading ? <div className="flex items-center justify-center h-64"><div className="text-[#9B8AB0] text-sm">Loading...</div></div> : (
        <DragDropContext onDragEnd={handleDragEnd}>
          <div className="flex gap-4 overflow-x-auto pb-4" data-testid="kanban-board">
            {stages.map(stage => (
              <Droppable key={stage} droppableId={stage}>
                {(provided, snapshot) => (
                  <div ref={provided.innerRef} {...provided.droppableProps}
                    className={`flex-shrink-0 w-72 bg-white border rounded-xl ${snapshot.isDraggingOver ? 'border-[#7C35DC]/40 bg-[#F9F5FF]' : 'border-[#E8E0F5]'}`}
                    style={{ boxShadow:'var(--shadow-card)' }} data-testid={`pipeline-column-${stage}`}>
                    <div className="p-4 border-b border-[#E8E0F5]">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor:STAGE_COLORS[stage] }}></div>
                          <span className="text-sm font-bold text-[#1A0A2E] capitalize" style={{ fontFamily:'Plus Jakarta Sans' }}>{stage.replace('_',' ')}</span>
                        </div>
                        <span className="text-xs font-mono text-[#9B8AB0] bg-[#F4F0FF] px-2 py-0.5 rounded-md">{grouped[stage].length}</span>
                      </div>
                      <div className="text-xs font-extrabold mt-2 tracking-wide" style={{ color: STAGE_COLORS[stage], fontFamily:'Plus Jakarta Sans' }} data-testid={`pipeline-stage-value-${stage}`}>{fmtInr(stageValue(stage))}</div>
                    </div>
                    <div className="p-2 space-y-2 min-h-[200px] max-h-[60vh] overflow-y-auto scrollbar-hide">
                      {grouped[stage].map((lead, index) => (
                        <Draggable key={lead.id} draggableId={lead.id} index={index}>
                          {(prov, snap) => (
                            <div ref={prov.innerRef} {...prov.draggableProps} {...prov.dragHandleProps}
                              onClick={() => navigate(`/leads/${lead.id}`)}
                              className={`bg-[#FAFAFA] border border-[#E8E0F5] rounded-lg p-3 cursor-pointer hover:bg-[#F9F5FF] hover:border-[#7C35DC]/20 transition-all ${snap.isDragging ? 'shadow-lg border-[#7C35DC]/30' : ''}`}
                              data-testid={`pipeline-card-${lead.id}`}>
                              <div className="flex items-start justify-between mb-2">
                                <div className="text-sm font-semibold text-[#1A0A2E] truncate">{lead.first_name} {lead.last_name}</div>
                                <div className="w-2 h-2 rounded-full shrink-0 mt-1.5" style={{ backgroundColor: lead.icp_tier === 'hot' ? '#7C35DC' : lead.icp_tier === 'warm' ? '#D97706' : '#94A3B8' }}></div>
                              </div>
                              {lead.company_name && <div className="flex items-center gap-1 text-xs text-[#9B8AB0] mb-2"><Buildings size={12} /> {lead.company_name}</div>}
                              <div className="flex items-center justify-between">
                                <span className="text-xs text-[#9B8AB0]">{lead.source_channel?.replace('_',' ')}</span>
                                <span className="text-xs font-mono font-semibold" style={{ color: lead.icp_score >= 70 ? '#7C35DC' : lead.icp_score >= 40 ? '#D97706' : '#94A3B8' }}>{lead.icp_score}</span>
                              </div>
                              {lead.deal_value > 0 && (
                                <div className="mt-2 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-[#F4F0FF] text-[#7C35DC] border border-[#7C35DC]/15" data-testid={`pipeline-card-value-${lead.id}`}>{fmtInr(lead.deal_value)}</div>
                              )}
                            </div>
                          )}
                        </Draggable>
                      ))}
                      {provided.placeholder}
                    </div>
                  </div>
                )}
              </Droppable>
            ))}
          </div>
        </DragDropContext>
      )}
    </div>
  );
};

export default Pipeline;
