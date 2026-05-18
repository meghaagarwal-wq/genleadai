import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import {
  Sparkle, UploadSimple, FileText, Check, ArrowRight, Target,
  Megaphone, MapTrifold, Lightning, Bell, Warning, PencilSimple,
  X, FloppyDisk, Brain, Rocket, ChatTeardropDots, FunnelSimple,
  CheckCircle,
} from '@phosphor-icons/react';
import api from '../config/api';

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
  const fileRef = useRef();

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
        timeout: 120000,  // Claude can take up to ~60-90s on bigger docs
      });
      setExtracted(r.data?.extracted || null);
      setStage('review');
      toast.success(`Aria mapped ${r.data?.extracted?.touchpoints?.length || 0} touchpoints from your doc`);
      // Fire-and-forget diff against current workspace state
      try {
        const d = await api.post('/api/aria/auto-map/diff', {
          icps: r.data?.extracted?.icps || [],
          touchpoints: r.data?.extracted?.touchpoints || [],
          lead_sources: r.data?.extracted?.lead_sources || [],
        });
        setDiff(d.data);
      } catch (_e) { /* diff is optional */ }
    } catch (e) {
      // Build a useful, specific message instead of axios's generic "Network Error".
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

  const handlePublish = async () => {
    if (!extracted) return;
    setStage('publishing');
    try {
      const r = await api.post('/api/aria/auto-map/publish', {
        icps: extracted.icps || [],
        touchpoints: extracted.touchpoints || [],
        lead_sources: extracted.lead_sources || [],
        recommended_integrations: extracted.recommended_integrations || [],
        sales_channels: extracted.sales_channels || [],
        qualification: extracted.qualification || {},
        handoff: extracted.handoff || {},
        summary: extracted.summary || '',
        overwrite_journey: overwriteJourney,
      });
      setPublishResult(r.data);
      setStage('done');
      const channelsBit = (r.data.sales_channels_saved || []).length > 0
        ? `, ${(r.data.sales_channels_saved || []).length} sales channel(s)` : '';
      toast.success(`Published — ${r.data.icps_created} ICP(s), ${r.data.touchpoints_saved} touchpoint(s)${channelsBit}`);
    } catch (e) {
      const d = e?.response?.data?.detail;
      toast.error(typeof d === 'string' ? d : 'Publish failed');
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
          publishing={stage === 'publishing'}
          overwriteJourney={overwriteJourney}
          setOverwriteJourney={setOverwriteJourney}
          filename={filename}
          onStartOver={reset}
        />
      )}

      {stage === 'done' && publishResult && (
        <DonePanel result={publishResult} onStartOver={reset} navigate={navigate} />
      )}
    </div>
  );
}

// ─── STAGE 1: Upload ────────────────────────────────────────────────────────
function UploadPanel({ onDrop, onPickClick, inputRef }) {
  const [dragOver, setDragOver] = useState(false);
  return (
    <div
      data-testid="auto-map-upload-panel"
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => { e.preventDefault(); setDragOver(false); onDrop(e.dataTransfer.files?.[0]); }}
      className={`bg-white border-2 border-dashed rounded-3xl p-16 text-center transition-all ${
        dragOver ? 'border-violet-500 bg-violet-50' : 'border-slate-300 hover:border-violet-300'
      }`}
    >
      <div className="inline-flex items-center justify-center w-20 h-20 rounded-3xl bg-gradient-to-br from-violet-500 to-indigo-600 text-white mb-5 shadow-lg">
        <UploadSimple size={36} weight="duotone" />
      </div>
      <h2 className="text-xl font-semibold text-slate-900 mb-2">Upload your ICP, journey, or GTM document</h2>
      <p className="text-slate-600 text-sm max-w-md mx-auto mb-6">
        Drop a PDF, DOCX, XLSX, TXT, or CSV. Aria will read it and extract every ICP, lead source,
        touchpoint, condition, qualification rule, and handoff trigger.
      </p>
      <button
        type="button"
        onClick={onPickClick}
        data-testid="auto-map-upload-btn"
        className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-slate-900 text-white text-sm font-medium hover:bg-slate-800 transition-colors"
      >
        <UploadSimple size={16} weight="bold" /> Upload Document
      </button>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.docx,.xlsx,.xls,.txt,.csv"
        data-testid="auto-map-file-input"
        className="hidden"
        onChange={(e) => onDrop(e.target.files?.[0])}
      />
      <p className="text-[11px] text-slate-400 mt-3">PDF · DOCX · XLSX · TXT · CSV · max 10MB</p>
    </div>
  );
}

// ─── STAGE 2: Extracting (animated) ─────────────────────────────────────────
function ExtractingPanel({ filename }) {
  const messages = [
    'Aria is reading your document…',
    'Mapping your ICP…',
    'Building your touchpoint journey…',
    'Creating conditional logic…',
    'Almost ready to review…',
  ];
  const [idx, setIdx] = useState(0);
  React.useEffect(() => {
    const t = setInterval(() => setIdx((x) => Math.min(x + 1, messages.length - 1)), 4500);
    return () => clearInterval(t);
  }, [messages.length]);
  return (
    <div data-testid="auto-map-extracting-panel" className="bg-white border border-slate-200 rounded-3xl p-12 text-center">
      <div className="inline-flex items-center justify-center w-20 h-20 rounded-3xl bg-gradient-to-br from-violet-500 to-indigo-600 text-white mb-5 animate-pulse">
        <Brain size={36} weight="duotone" />
      </div>
      <h2 className="text-xl font-semibold text-slate-900 mb-2">Analyzing {filename || 'your document'}…</h2>
      <p className="text-violet-600 text-sm font-medium mb-1">{messages[idx]}</p>
      <p className="text-slate-500 text-xs">This usually takes 20-40 seconds for the first analysis.</p>
      <div className="mt-6 max-w-md mx-auto bg-slate-100 rounded-full h-1.5 overflow-hidden">
        <div className="h-full bg-gradient-to-r from-violet-500 to-indigo-500 animate-pulse" style={{ width: `${((idx + 1) / messages.length) * 100}%` }} />
      </div>
    </div>
  );
}

// ─── STAGE 3: Review (editable cards) ───────────────────────────────────────
function ReviewPanel({ extracted, diff, onChange, onPublish, onAskAria, askingAria, suggestions, publishing, overwriteJourney, setOverwriteJourney, filename, onStartOver }) {
  const updateField = (path, val) => {
    const next = JSON.parse(JSON.stringify(extracted));
    let ref = next;
    const keys = path.slice(0, -1);
    for (const k of keys) ref = ref[k];
    ref[path[path.length - 1]] = val;
    onChange(next);
  };

  return (
    <div className="space-y-5">
      {/* Aria summary */}
      <div className="bg-gradient-to-br from-violet-50 to-indigo-50 border border-violet-200 rounded-2xl p-5 flex items-start gap-3">
        <Sparkle size={20} weight="duotone" className="text-violet-600 flex-shrink-0 mt-0.5" />
        <div className="flex-1">
          <p className="text-xs uppercase tracking-wider text-violet-700 font-semibold mb-1">Aria says</p>
          <p className="text-sm text-slate-700 leading-relaxed">{extracted.summary || 'Review the extracted sections below, then publish.'}</p>
          <p className="text-[10px] text-slate-500 mt-2">From: <strong>{filename}</strong></p>
        </div>
        <button onClick={onStartOver} className="text-xs text-slate-500 hover:text-rose-600 px-2 py-1 rounded">
          <X size={14} /> Start over
        </button>
      </div>

      {/* Diff vs. current workspace */}
      {diff && (diff.icp_changes?.length > 0 || diff.touchpoint_diff) && (
        <div data-testid="auto-map-diff-card" className="bg-white border border-sky-200 bg-sky-50/40 rounded-2xl p-4 flex items-start gap-3">
          <ChatTeardropDots size={18} weight="duotone" className="text-sky-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1 text-xs text-slate-700">
            <div className="text-[10px] uppercase tracking-wider text-sky-700 font-semibold mb-1">What will change if you publish</div>
            <p>{diff.summary}</p>
            <div className="flex flex-wrap gap-1.5 mt-2">
              {diff.icp_changes?.filter((c) => c.action === 'create').map((c, i) => (
                <span key={i} className="text-[10px] px-2 py-0.5 rounded bg-emerald-100 text-emerald-700 border border-emerald-200">+ {c.label}</span>
              ))}
              {diff.icp_changes?.filter((c) => c.action === 'skip_exists').map((c, i) => (
                <span key={`s${i}`} className="text-[10px] px-2 py-0.5 rounded bg-slate-100 text-slate-500 border border-slate-200">= {c.label}</span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* CARD 1: ICPs */}
      <Card
        testid="auto-map-card-icps"
        icon={<Target size={16} weight="duotone" />}
        title={`${(extracted.icps || []).length} ICP${(extracted.icps || []).length === 1 ? '' : 's'} detected`}
        tint="violet"
      >
        {(extracted.icps || []).length === 0 ? (
          <p className="text-xs text-slate-400">No ICPs detected — Aria couldn't infer a buyer persona from the doc.</p>
        ) : (
          <div className="space-y-3">
            {extracted.icps.map((icp, i) => (
              <div key={i} className="bg-white border border-slate-200 rounded-xl p-3" data-testid={`auto-map-icp-${i}`}>
                <div className="grid grid-cols-2 gap-3 mb-2">
                  <FieldInline label="Label" value={icp.label} onChange={(v) => updateField(['icps', i, 'label'], v)} />
                  <FieldInline label="Industry" value={icp.industry} onChange={(v) => updateField(['icps', i, 'industry'], v)} />
                  <FieldInline label="Company size" value={icp.company_size} onChange={(v) => updateField(['icps', i, 'company_size'], v)} />
                  <FieldInline label="Geography" value={icp.geography} onChange={(v) => updateField(['icps', i, 'geography'], v)} />
                </div>
                <FieldInline label="Pain point" value={icp.pain_point} onChange={(v) => updateField(['icps', i, 'pain_point'], v)} multiline />
                <FieldInline label="Value prop" value={icp.value_prop} onChange={(v) => updateField(['icps', i, 'value_prop'], v)} multiline />
                <div className="mt-2 flex flex-wrap gap-1">
                  {(icp.title_targets || []).map((t) => (
                    <span key={t} className="text-[10px] px-2 py-0.5 rounded bg-violet-50 text-violet-700 border border-violet-200">{t}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* CARD 2: Lead sources */}
      <Card
        testid="auto-map-card-sources"
        icon={<FunnelSimple size={16} weight="duotone" />}
        title={`${(extracted.lead_sources || []).length} lead source${(extracted.lead_sources || []).length === 1 ? '' : 's'} detected`}
        tint="emerald"
      >
        {(extracted.lead_sources || []).length === 0 ? (
          <p className="text-xs text-slate-400">No lead sources detected in the document.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {extracted.lead_sources.map((s, i) => (
              <span key={i} className="text-xs px-3 py-1.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">{s}</span>
            ))}
          </div>
        )}
      </Card>

      {/* CARD 2b: Recommended integrations (iter 69 — Saleshandy/Lemlist/Zoho etc.) */}
      <Card
        testid="auto-map-card-integrations"
        icon={<FunnelSimple size={16} weight="duotone" />}
        title={`${(extracted.recommended_integrations || []).length} integration${(extracted.recommended_integrations || []).length === 1 ? '' : 's'} recommended`}
        tint="indigo"
      >
        {(extracted.recommended_integrations || []).length === 0 ? (
          <p className="text-xs text-slate-400">Aria didn't spot any specific tools (Saleshandy, Lemlist, Zoho, Calendly, etc.) in the document. You can connect any tool from the Integration Hub later.</p>
        ) : (
          <div className="space-y-2">
            <div className="flex flex-wrap gap-2">
              {extracted.recommended_integrations.map((s, i) => (
                <span
                  key={i}
                  data-testid={`auto-map-integration-${s}`}
                  className="text-xs px-3 py-1.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200 font-mono"
                >
                  {s}
                </span>
              ))}
            </div>
            <p className="text-[11px] text-slate-500">Head to <strong>Integration Hub</strong> after publishing to paste API keys + import campaigns/leads from these tools.</p>
          </div>
        )}
      </Card>

      {/* CARD 2c: Sales channel preferences inferred from the doc */}
      <Card
        testid="auto-map-card-sales-channels"
        icon={<FunnelSimple size={16} weight="duotone" />}
        title={`${(extracted.sales_channels || []).length} sales channel${(extracted.sales_channels || []).length === 1 ? '' : 's'} suggested`}
        tint="violet"
      >
        {(extracted.sales_channels || []).length === 0 ? (
          <p className="text-xs text-slate-400">Aria didn't infer specific channels (email / linkedin / whatsapp) from the document.</p>
        ) : (
          <div className="space-y-2">
            <div className="flex flex-wrap gap-2">
              {extracted.sales_channels.map((s, i) => (
                <span
                  key={i}
                  data-testid={`auto-map-sales-channel-${s}`}
                  className={`text-xs px-3 py-1.5 rounded-full border font-mono ${i === 0 ? 'bg-violet-100 text-violet-800 border-violet-300' : 'bg-violet-50 text-violet-700 border-violet-200'}`}
                >
                  {i === 0 ? '★ ' : ''}{s}
                </span>
              ))}
            </div>
            <p className="text-[11px] text-slate-500">★ = primary channel. Publishing will save this to your Sales Channel Preferences (overrides any prior selection).</p>
          </div>
        )}
      </Card>

      {/* CARD 3: Touchpoints */}
      <Card
        testid="auto-map-card-touchpoints"
        icon={<MapTrifold size={16} weight="duotone" />}
        title={`${(extracted.touchpoints || []).length} touchpoints mapped`}
        tint="sky"
      >
        {(extracted.touchpoints || []).length === 0 ? (
          <p className="text-xs text-slate-400">No touchpoints generated.</p>
        ) : (
          <div className="space-y-2">
            {extracted.touchpoints.map((tp, i) => (
              <div key={i} className="bg-white border border-slate-200 rounded-lg p-3 flex items-start gap-3" data-testid={`auto-map-tp-${i}`}>
                <div className="w-7 h-7 rounded-full bg-sky-100 text-sky-700 text-xs font-bold flex items-center justify-center flex-shrink-0">{i + 1}</div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className="text-[10px] uppercase tracking-wider font-bold text-slate-700 bg-slate-100 px-2 py-0.5 rounded">{tp.channel}</span>
                    <span className="text-[10px] text-slate-500">{tp.message_type}</span>
                    <span className="text-[10px] text-slate-400">Day {tp.day} · {tp.hour}:00</span>
                    {Object.keys(tp.conditions || {}).length > 0 && (
                      <span className="text-[10px] font-semibold text-violet-700 inline-flex items-center gap-0.5"><Lightning size={9} /> {Object.keys(tp.conditions).length} branch</span>
                    )}
                  </div>
                  <textarea
                    value={tp.message_template || ''}
                    onChange={(e) => updateField(['touchpoints', i, 'message_template'], e.target.value)}
                    rows={2}
                    data-testid={`auto-map-tp-message-${i}`}
                    className="w-full text-xs text-slate-700 bg-slate-50 border border-slate-200 rounded p-2 font-mono resize-none"
                  />
                </div>
              </div>
            ))}
          </div>
        )}

        <label className="flex items-center gap-2 mt-4 text-xs text-slate-700 cursor-pointer">
          <input
            type="checkbox"
            checked={overwriteJourney}
            onChange={(e) => setOverwriteJourney(e.target.checked)}
            data-testid="auto-map-overwrite-toggle"
            className="rounded"
          />
          <span>On publish, replace my current 32-touchpoint journey with this sequence</span>
        </label>
      </Card>

      {/* CARD 4: Qualification + Handoff */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <Card testid="auto-map-card-qualification" icon={<CheckCircle size={16} weight="duotone" />} title="Qualification logic" tint="amber" small>
          <Subhead label="Must-have criteria" />
          <ChipList values={extracted.qualification?.must_have_criteria || []} tint="amber" />
          <Subhead label="Disqualifiers" />
          <ChipList values={extracted.qualification?.disqualifiers || []} tint="rose" />
          <Subhead label="Qualifying questions" />
          <ChipList values={extracted.qualification?.qualifying_questions || []} tint="slate" />
        </Card>

        <Card testid="auto-map-card-handoff" icon={<Bell size={16} weight="duotone" />} title="Sales handoff" tint="rose" small>
          <Subhead label="Trigger" />
          <p className="text-xs text-slate-700">{extracted.handoff?.trigger || <em className="text-slate-400">Not detected</em>}</p>
          <Subhead label="Alert channels" />
          <ChipList values={extracted.handoff?.alert_channels || []} tint="rose" />
          <Subhead label="Info passed" />
          <ChipList values={extracted.handoff?.info_passed || []} tint="slate" />
        </Card>
      </div>

      {/* Aria suggestions */}
      {suggestions.length > 0 && (
        <Card testid="auto-map-suggestions" icon={<Warning size={16} weight="duotone" />} title={`Aria's improvement suggestions (${suggestions.length})`} tint="amber">
          <div className="space-y-2">
            {suggestions.map((s, i) => (
              <div key={i} className="bg-amber-50 border border-amber-200 rounded-lg p-3" data-testid={`auto-map-suggestion-${i}`}>
                <div className="text-[10px] uppercase tracking-wider font-bold text-amber-700 mb-1">{(s.type || 'tip').replace(/_/g, ' ')}</div>
                <p className="text-sm text-slate-800">{s.message}</p>
                {s.fix_hint && <p className="text-xs text-slate-600 mt-1 italic">→ {s.fix_hint}</p>}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Sticky action bar */}
      <div className="sticky bottom-4 bg-white border border-slate-200 shadow-xl rounded-2xl p-4 flex items-center justify-between gap-3 flex-wrap">
        <button
          type="button"
          onClick={onAskAria}
          disabled={askingAria}
          data-testid="auto-map-ask-aria-btn"
          className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-lg text-xs font-medium bg-amber-50 border border-amber-200 text-amber-700 hover:bg-amber-100 disabled:opacity-50"
        >
          <Sparkle size={14} weight="duotone" /> {askingAria ? 'Aria is thinking…' : 'Ask Aria to Improve This Journey'}
        </button>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onStartOver}
            className="px-4 py-2.5 rounded-lg text-xs text-slate-600 hover:bg-slate-100"
          >Cancel</button>
          <button
            type="button"
            onClick={onPublish}
            disabled={publishing}
            data-testid="auto-map-publish-btn"
            className="inline-flex items-center gap-1.5 px-5 py-2.5 rounded-lg bg-slate-900 text-white text-sm font-medium hover:bg-slate-800 disabled:opacity-50"
          >
            <Rocket size={14} weight="bold" /> {publishing ? 'Publishing…' : 'Publish Workflow'} <ArrowRight size={12} />
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── STAGE 4: Done ──────────────────────────────────────────────────────────
function DonePanel({ result, onStartOver, navigate }) {
  return (
    <div data-testid="auto-map-done-panel" className="bg-gradient-to-br from-emerald-50 to-teal-50 border border-emerald-200 rounded-3xl p-12 text-center">
      <div className="inline-flex items-center justify-center w-20 h-20 rounded-3xl bg-gradient-to-br from-emerald-500 to-teal-600 text-white mb-5 shadow-lg">
        <Check size={36} weight="bold" />
      </div>
      <h2 className="text-2xl font-semibold text-slate-900 mb-2">Workflow published</h2>
      <p className="text-slate-600 text-sm max-w-md mx-auto mb-6">
        Aria created <strong>{result.icps_created}</strong> new ICP(s)
        {result.icps_skipped?.length > 0 && <> · {result.icps_skipped.length} already existed</>}
        {' '}and saved <strong>{result.touchpoints_saved}</strong> touchpoints into your 32-touchpoint journey.
      </p>
      <div className="flex flex-wrap justify-center gap-2">
        <button onClick={() => navigate('/touchpoint-journey')} data-testid="auto-map-go-journey" className="inline-flex items-center gap-1.5 px-5 py-3 rounded-xl bg-slate-900 text-white text-sm font-medium hover:bg-slate-800">
          <MapTrifold size={14} /> View Journey
        </button>
        <button onClick={() => navigate('/icps')} className="inline-flex items-center gap-1.5 px-5 py-3 rounded-xl bg-white border border-slate-200 text-slate-700 text-sm font-medium hover:bg-slate-50">
          <Target size={14} /> View ICPs
        </button>
        <button onClick={onStartOver} data-testid="auto-map-upload-another" className="inline-flex items-center gap-1.5 px-5 py-3 rounded-xl bg-violet-600 text-white text-sm font-medium hover:bg-violet-700">
          <UploadSimple size={14} /> Upload another version
        </button>
      </div>
      <p className="text-[10px] text-slate-500 mt-4">
        Tip: when you upload a v2/v3 of your GTM doc, Aria's preview panel will let you see exactly what changed before re-publishing.
      </p>
    </div>
  );
}

// ─── Reusable atoms ─────────────────────────────────────────────────────────
function Card({ icon, title, tint = 'violet', testid, small = false, children }) {
  const tintMap = {
    violet: 'border-violet-200 bg-violet-50/40',
    emerald: 'border-emerald-200 bg-emerald-50/40',
    sky: 'border-sky-200 bg-sky-50/40',
    amber: 'border-amber-200 bg-amber-50/40',
    rose: 'border-rose-200 bg-rose-50/40',
    indigo: 'border-indigo-200 bg-indigo-50/40',
  };
  const iconColor = {
    violet: 'text-violet-600', emerald: 'text-emerald-600',
    sky: 'text-sky-600', amber: 'text-amber-600', rose: 'text-rose-600',
    indigo: 'text-indigo-600',
  };
  return (
    <div data-testid={testid} className={`bg-white border rounded-2xl p-5 ${tintMap[tint]}`}>
      <h3 className={`flex items-center gap-2 text-sm font-semibold text-slate-900 mb-3 ${small ? 'text-xs' : ''}`}>
        <span className={iconColor[tint]}>{icon}</span>
        {title}
      </h3>
      {children}
    </div>
  );
}

function FieldInline({ label, value, onChange, multiline = false }) {
  return (
    <div>
      <label className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 mb-0.5 block">{label}</label>
      {multiline ? (
        <textarea
          value={value || ''} onChange={(e) => onChange(e.target.value)}
          rows={2}
          className="w-full text-xs text-slate-800 px-2 py-1.5 rounded border border-slate-200 bg-white focus:border-violet-400 outline-none resize-none"
        />
      ) : (
        <input
          value={value || ''} onChange={(e) => onChange(e.target.value)}
          className="w-full text-xs text-slate-800 px-2 py-1.5 rounded border border-slate-200 bg-white focus:border-violet-400 outline-none"
        />
      )}
    </div>
  );
}

function Subhead({ label }) {
  return <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mt-2 mb-1">{label}</div>;
}

function ChipList({ values, tint = 'slate' }) {
  const tintMap = {
    amber: 'bg-amber-50 text-amber-700 border-amber-200',
    rose: 'bg-rose-50 text-rose-700 border-rose-200',
    slate: 'bg-slate-50 text-slate-700 border-slate-200',
    emerald: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  };
  if (!values?.length) return <p className="text-[11px] text-slate-400 italic">Nothing detected</p>;
  return (
    <div className="flex flex-wrap gap-1">
      {values.map((v, i) => (
        <span key={i} className={`text-[10px] px-2 py-0.5 rounded border ${tintMap[tint]}`}>{v}</span>
      ))}
    </div>
  );
}
