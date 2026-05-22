import React from 'react';
import { Check, MapTrifold, Target, UploadSimple } from '@phosphor-icons/react';

export default function DonePanel({ result, onStartOver, navigate }) {
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
