import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../config/api';
import { DragDropContext, Droppable, Draggable } from 'react-beautiful-dnd';
import { Fire, User, Buildings } from '@phosphor-icons/react';

const PIPELINE_STAGES = {
  B2B: ['new', 'contacted', 'qualified', 'proposal_sent', 'negotiation', 'won', 'lost'],
  B2C: ['new', 'contacted', 'qualified', 'proposal_sent', 'won', 'lost'],
};

const STAGE_COLORS = {
  new: '#0055FF',
  contacted: '#8B5CF6',
  qualified: '#10B981',
  proposal_sent: '#F59E0B',
  negotiation: '#F59E0B',
  won: '#10B981',
  lost: '#FF3B30',
};

const Pipeline = () => {
  const navigate = useNavigate();
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [pipelineType, setPipelineType] = useState('B2B');

  useEffect(() => { fetchLeads(); }, [pipelineType]);

  const fetchLeads = async () => {
    setLoading(true);
    try {
      const res = await api.get('/api/leads', { params: { limit: 200, lead_type: pipelineType } });
      setLeads(res.data.leads);
    } catch (err) {
      console.error('Failed to fetch leads', err);
    } finally {
      setLoading(false);
    }
  };

  const stages = PIPELINE_STAGES[pipelineType];
  const groupedLeads = {};
  stages.forEach(s => { groupedLeads[s] = []; });
  leads.forEach(lead => {
    if (groupedLeads[lead.status]) groupedLeads[lead.status].push(lead);
    else if (groupedLeads['new']) groupedLeads['new'].push(lead);
  });

  const handleDragEnd = async (result) => {
    if (!result.destination) return;
    const { draggableId, destination } = result;
    const newStatus = destination.droppableId;
    
    setLeads(prev => prev.map(l => l.id === draggableId ? { ...l, status: newStatus } : l));
    
    try {
      await api.patch(`/api/leads/${draggableId}`, { status: newStatus });
    } catch (err) {
      console.error('Failed to update status', err);
      fetchLeads();
    }
  };

  const tierDot = (tier) => {
    const c = { hot: '#FF3B30', warm: '#F59E0B', cold: '#0055FF' };
    return <div className="w-2 h-2 rounded-full" style={{ backgroundColor: c[tier] || c.cold }}></div>;
  };

  return (
    <div data-testid="pipeline-page" className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Pipeline</h1>
          <p className="text-sm text-[#A3A3A3] mt-1">Drag and drop leads across stages</p>
        </div>
        <div className="flex items-center gap-2 bg-[#141414] border border-[#262626] rounded-lg p-1" data-testid="pipeline-type-toggle">
          {['B2B', 'B2C'].map(type => (
            <button
              key={type}
              onClick={() => setPipelineType(type)}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${pipelineType === type ? 'bg-[#0055FF] text-white' : 'text-[#A3A3A3] hover:text-white'}`}
              data-testid={`pipeline-${type.toLowerCase()}-btn`}
            >
              {type}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64"><div className="text-[#A3A3A3] font-mono text-sm">Loading pipeline...</div></div>
      ) : (
        <DragDropContext onDragEnd={handleDragEnd}>
          <div className="flex gap-4 overflow-x-auto pb-4" data-testid="kanban-board">
            {stages.map(stage => (
              <Droppable key={stage} droppableId={stage}>
                {(provided, snapshot) => (
                  <div
                    ref={provided.innerRef}
                    {...provided.droppableProps}
                    className={`flex-shrink-0 w-72 bg-[#141414] border rounded-lg ${snapshot.isDraggingOver ? 'border-[#0055FF]/50' : 'border-[#262626]'}`}
                    data-testid={`pipeline-column-${stage}`}
                  >
                    {/* Column Header */}
                    <div className="p-4 border-b border-[#262626]">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <div className="w-2 h-2 rounded-full" style={{ backgroundColor: STAGE_COLORS[stage] }}></div>
                          <span className="text-sm font-semibold text-white capitalize">{stage.replace('_', ' ')}</span>
                        </div>
                        <span className="text-xs font-mono text-[#737373] bg-[#262626] px-2 py-0.5 rounded">
                          {groupedLeads[stage].length}
                        </span>
                      </div>
                    </div>

                    {/* Cards */}
                    <div className="p-2 space-y-2 min-h-[200px] max-h-[60vh] overflow-y-auto scrollbar-hide">
                      {groupedLeads[stage].map((lead, index) => (
                        <Draggable key={lead.id} draggableId={lead.id} index={index}>
                          {(provided, snapshot) => (
                            <div
                              ref={provided.innerRef}
                              {...provided.draggableProps}
                              {...provided.dragHandleProps}
                              onClick={() => navigate(`/leads/${lead.id}`)}
                              className={`bg-[#0A0A0A] border border-[#262626] rounded-lg p-3 cursor-pointer hover:border-white/20 transition-all ${snapshot.isDragging ? 'shadow-lg shadow-black/50 border-[#0055FF]/50' : ''}`}
                              data-testid={`pipeline-card-${lead.id}`}
                            >
                              <div className="flex items-start justify-between mb-2">
                                <div className="text-sm font-medium text-white truncate">{lead.first_name} {lead.last_name}</div>
                                {tierDot(lead.icp_tier)}
                              </div>
                              {lead.company_name && (
                                <div className="flex items-center gap-1 text-xs text-[#737373] mb-2">
                                  <Buildings size={12} /> {lead.company_name}
                                </div>
                              )}
                              <div className="flex items-center justify-between">
                                <span className="text-xs text-[#737373]">{lead.source_channel?.replace('_', ' ')}</span>
                                <span className="text-xs font-mono" style={{ color: lead.icp_score >= 70 ? '#FF3B30' : lead.icp_score >= 40 ? '#F59E0B' : '#0055FF' }}>
                                  {lead.icp_score}
                                </span>
                              </div>
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
