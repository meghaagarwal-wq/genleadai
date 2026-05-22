import React, { useState } from 'react';
import { UploadSimple } from '@phosphor-icons/react';

export default function UploadPanel({ onDrop, onPickClick, inputRef }) {
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
