import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import {
  UploadSimple, Check, Brain, PencilSimple, Rocket,
} from '@phosphor-icons/react';
import api from '../config/api';

import UploadPanel from '../components/ai-setup/UploadPanel';
import ExtractingPanel from '../components/ai-setup/ExtractingPanel';
import ReviewPanel from '../components/ai-setup/ReviewPanel';
import DonePanel from '../components/ai-setup/DonePanel';

const STEPS = [
  { key: 'upload', label: 'Upload Document', icon: UploadSimple },
  { key: 'extract', label: 'Aria Extracts Data', icon: Brain },
  { key: 'review', label: 'Review Auto-Mapped Journey', icon: PencilSimple },
  { key: 'publish', label: 'Publish Workflow', icon: Rocket },
];

export default function AISetupAssistant() {
  const navigate = useNavigate();
  const [stage, setStage] = useState('upload');     // upload | extracting | review | publishing | done
  const [extracted, setExtracted] = useState(null);
  const [diff, setDiff] = useState(null);
  const [filename, setFilename] = useState(null);
  const [overwriteJourney, setOverwriteJourney] = useState(true);
  const [suggestions, setSuggestions] = useState([]);
  const [askingAria, setAskingAria] = useState(false);
  const [publishResult, setPublishResult] = useState(null);
  const [overwriteWarning, setOverwriteWarning] = useState(null);
  const [showSuggestions, setShowSuggestions] = useState(false);
  // Iter 76 — last-published automap_summary fetched on mount.
  // Lets founders pick up where they left off instead of re-uploading.
  const [lastSummary, setLastSummary] = useState(null);
  const fileRef = useRef();

  // Fetch last-published summary on mount (only on the upload step).
  useEffect(() => {
    let alive = true;
    api.get('/api/aria/auto-map/summary').then((r) => {
      if (!alive) return;
      const s = r.data?.summary;
      if (s && (s.touchpoints_extracted || []).length > 0) {
        setLastSummary(s);
      }
    }).catch(() => { /* non-blocking */ });
    return () => { alive = false; };
  }, []);

  const resumeLast = () => {
    if (!lastSummary) return;
    // Re-hydrate the review stage with the last-published state.
    setExtracted({
      icps: [],
      touchpoints: [],
      touchpoints_extracted: lastSummary.touchpoints_extracted || [],
      lead_sources: lastSummary.lead_sources || [],
      recommended_integrations: lastSummary.recommended_integrations || [],
      sales_channels: [],
      qualification: lastSummary.qualification || {},
      handoff: lastSummary.handoff || {},
      summary: lastSummary.summary || 'Resumed your last published workflow — edit any row and re-publish to overwrite.',
    });
    setFilename(`Resumed from last publish (${lastSummary.applied_at?.slice(0, 10) || 'previous session'})`);
    setStage('review');
    setLastSummary(null);
  };

  const currentStepIdx = stage === 'upload' ? 0 : stage === 'extracting' ? 1 : stage === 'review' ? 2 : 3;

  const handleFile = async (file) => {
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) { toast.error('File over 10MB'); return; }
    setStage('extracting');
    setFilename(file.name);
    try {
      const form = new FormData();
      form.append('file', file);
      const r = await api.post('/api/aria/auto-map/analyze', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000,
      });
      setExtracted(r.data?.extracted || null);
      setStage('review');
      const tpCount = (r.data?.extracted?.touchpoints_extracted?.length || r.data?.extracted?.touchpoints?.length || 0);
      if (tpCount > 0) {
        toast.success(`Aria mapped ${tpCount} touchpoint flow${tpCount === 1 ? '' : 's'} from your doc`);
      } else {
        toast.warning("Aria didn't find a touchpoint sequence in this doc — review below before publishing.");
      }
      try {
        const d = await api.post('/api/aria/auto-map/diff', {
          icps: r.data?.extracted?.icps || [],
          touchpoints: r.data?.extracted?.touchpoints || [],
          lead_sources: r.data?.extracted?.lead_sources || [],
        });
        setDiff(d.data);
      } catch (_e) { /* diff is optional */ }
    } catch (e) {
      const d = e?.response?.data?.detail;
      let msg;
      if (typeof d === 'string') {
        msg = d;
      } else if (Array.isArray(d)) {
        msg = d.map((x) => x?.msg).filter(Boolean).join('; ');
      } else if (e?.code === 'ECONNABORTED' || (e?.message || '').toLowerCase().includes('timeout')) {
        msg = "Aria's brain timed out reading your doc (>2 min). Try uploading a smaller / text-only version.";
      } else if (!e?.response) {
        msg = 'Could not reach Aria. If your network is fine, your document may have been blocked by the upload proxy — try a smaller TXT/DOCX.';
      } else {
        msg = `Aria couldn't analyze the document (HTTP ${e?.response?.status || '???'}). Try a cleaner doc.`;
      }
      toast.error(msg);
      setStage('upload');
    }
  };

  const handlePublish = async (forceEmpty = false) => {
    if (!extracted) return;
    setStage('publishing');
    try {
      const r = await api.post('/api/aria/auto-map/publish', {
        icps: extracted.icps || [],
        touchpoints: extracted.touchpoints || [],
        touchpoints_extracted: extracted.touchpoints_extracted || [],
        lead_sources: extracted.lead_sources || [],
        recommended_integrations: extracted.recommended_integrations || [],
        sales_channels: extracted.sales_channels || [],
        qualification: extracted.qualification || {},
        handoff: extracted.handoff || {},
        summary: extracted.summary || '',
        overwrite_journey: overwriteJourney,
        force_empty_overwrite: forceEmpty,
      });
      setPublishResult(r.data);
      setStage('done');
      const channelsBit = (r.data.sales_channels_saved || []).length > 0
        ? `, ${(r.data.sales_channels_saved || []).length} sales channel(s)` : '';
      toast.success(`Published — ${r.data.icps_created} ICP(s), ${r.data.touchpoints_saved} touchpoint(s)${channelsBit}`);
    } catch (e) {
      const d = e?.response?.data?.detail;
      if (e?.response?.status === 409 && d?.code === 'empty_overwrite_blocked') {
        setStage('review');
        setOverwriteWarning({
          existing: d.existing_touchpoint_count,
          message: d.message,
        });
        return;
      }
      // Surface the real backend reason — string, validation array, or 500 trace.
      let msg = 'Publish failed';
      if (typeof d === 'string') {
        msg = d;
      } else if (Array.isArray(d)) {
        msg = d.map((x) => x?.msg || x?.detail || JSON.stringify(x)).filter(Boolean).join('; ');
      } else if (d && typeof d === 'object') {
        msg = d.message || d.detail || JSON.stringify(d);
      } else if (e?.message) {
        msg = `${msg}: ${e.message}`;
      }
      toast.error(msg, { duration: 8000 });
      setStage('review');
    }
  };

  const handleAskAria = async () => {
    setAskingAria(true);
    try {
      const r = await api.post('/api/aria/auto-map/improve', {
        icps: extracted.icps || [],
        touchpoints: extracted.touchpoints || [],
        lead_sources: extracted.lead_sources || [],
        qualification: extracted.qualification,
        handoff: extracted.handoff,
      });
      setSuggestions(r.data?.suggestions || []);
      setShowSuggestions(true);
      if ((r.data?.suggestions || []).length === 0) {
        toast.success('Aria says: your workflow looks complete.');
      }
    } catch (e) {
      toast.error('Could not get suggestions');
    } finally {
      setAskingAria(false);
    }
  };

  const reset = () => {
    setStage('upload'); setExtracted(null); setFilename(null);
    setSuggestions([]); setPublishResult(null); setDiff(null);
  };

  return (
    <div data-testid="ai-setup-assistant" className="max-w-6xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="mb-8">
        <p className="text-xs uppercase tracking-[0.18em] text-violet-600 font-semibold mb-2">AI Setup Assistant</p>
        <h1 className="text-3xl font-semibold text-slate-900 mb-2">Upload your GTM doc. Aria builds your lead journey.</h1>
        <p className="text-slate-600 text-sm max-w-2xl">
          From ICPs to touchpoints to follow-up logic, Aria reads your document and turns it into an
          automated sales workflow with branching conditional logic — editable before you publish.
        </p>
      </div>

      {/* Stepper */}
      <ol className="mb-8 flex items-center justify-between gap-2 max-w-3xl" data-testid="auto-map-stepper">
        {STEPS.map((s, i) => {
          const Icon = s.icon;
          const isActive = i === currentStepIdx;
          const isDone = i < currentStepIdx;
          return (
            <li key={s.key} className="flex items-center flex-1 min-w-0">
              <div className={`flex flex-col items-center text-center ${isActive || isDone ? 'opacity-100' : 'opacity-50'}`}>
                <div className={`w-10 h-10 rounded-full flex items-center justify-center border-2 ${
                  isDone ? 'bg-violet-600 border-violet-600 text-white' :
                  isActive ? 'bg-white border-violet-600 text-violet-700' :
                  'bg-white border-slate-300 text-slate-400'
                }`}>
                  {isDone ? <Check size={16} weight="bold" /> : <Icon size={16} weight="duotone" />}
                </div>
                <div className={`text-[10px] mt-1.5 font-semibold uppercase tracking-wider whitespace-nowrap ${isActive ? 'text-violet-700' : isDone ? 'text-slate-700' : 'text-slate-400'}`}>
                  {s.label}
                </div>
              </div>
              {i < STEPS.length - 1 && (
                <div className={`flex-1 h-0.5 mx-2 ${isDone ? 'bg-violet-600' : 'bg-slate-200'}`} />
              )}
            </li>
          );
        })}
      </ol>

      {/* Stage panels */}
      {stage === 'upload' && lastSummary && (
        <div
          data-testid="auto-map-resume-banner"
          className="mb-4 bg-gradient-to-r from-violet-50 to-indigo-50 border border-violet-200 rounded-2xl p-4 flex items-center justify-between gap-4"
        >
          <div className="flex-1 min-w-0">
            <p className="text-xs font-bold uppercase tracking-wider text-violet-700 mb-1">Resume your last setup</p>
            <p className="text-sm text-slate-700">
              You previously published a workflow with{' '}
              <strong>{lastSummary.touchpoints_extracted.length}</strong> edited touchpoint
              {lastSummary.touchpoints_extracted.length === 1 ? '' : 's'}
              {lastSummary.applied_at && <> on <strong>{lastSummary.applied_at.slice(0, 10)}</strong></>}. Pick up where you left off.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setLastSummary(null)}
              data-testid="auto-map-resume-dismiss"
              className="text-xs text-slate-500 hover:text-slate-700 px-3 py-2 rounded-lg"
            >
              Start fresh
            </button>
            <button
              onClick={resumeLast}
              data-testid="auto-map-resume-btn"
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-violet-600 text-white text-xs font-bold hover:bg-violet-700"
            >
              <PencilSimple size={14} weight="bold" /> Resume last edit
            </button>
          </div>
        </div>
      )}

      {stage === 'upload' && (
        <UploadPanel
          onDrop={handleFile}
          onPickClick={() => fileRef.current?.click()}
          inputRef={fileRef}
        />
      )}

      {stage === 'extracting' && (
        <ExtractingPanel filename={filename} />
      )}

      {(stage === 'review' || stage === 'publishing') && extracted && (
        <ReviewPanel
          extracted={extracted}
          diff={diff}
          onChange={setExtracted}
          onPublish={handlePublish}
          onAskAria={handleAskAria}
          askingAria={askingAria}
          suggestions={suggestions}
          showSuggestions={showSuggestions}
          setShowSuggestions={setShowSuggestions}
          publishing={stage === 'publishing'}
          overwriteJourney={overwriteJourney}
          setOverwriteJourney={setOverwriteJourney}
          filename={filename}
          onStartOver={reset}
          overwriteWarning={overwriteWarning}
          onDismissWarning={() => setOverwriteWarning(null)}
        />
      )}

      {stage === 'done' && publishResult && (
        <DonePanel result={publishResult} onStartOver={reset} navigate={navigate} />
      )}
    </div>
  );
}
