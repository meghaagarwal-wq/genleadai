import React, { useEffect, useState } from 'react';
import { Brain } from '@phosphor-icons/react';

const MESSAGES = [
  'Aria is reading your document…',
  'Mapping your ICP…',
  'Building your touchpoint journey…',
  'Creating conditional logic…',
  'Almost ready to review…',
];

export default function ExtractingPanel({ filename }) {
  const [idx, setIdx] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setIdx((x) => Math.min(x + 1, MESSAGES.length - 1)), 4500);
    return () => clearInterval(t);
  }, []);
  return (
    <div data-testid="auto-map-extracting-panel" className="bg-white border border-slate-200 rounded-3xl p-12 text-center">
      <div className="inline-flex items-center justify-center w-20 h-20 rounded-3xl bg-gradient-to-br from-violet-500 to-indigo-600 text-white mb-5 animate-pulse">
        <Brain size={36} weight="duotone" />
      </div>
      <h2 className="text-xl font-semibold text-slate-900 mb-2">Analyzing {filename || 'your document'}…</h2>
      <p className="text-violet-600 text-sm font-medium mb-1">{MESSAGES[idx]}</p>
      <p className="text-slate-500 text-xs">This usually takes 20-40 seconds for the first analysis.</p>
      <div className="mt-6 max-w-md mx-auto bg-slate-100 rounded-full h-1.5 overflow-hidden">
        <div className="h-full bg-gradient-to-r from-violet-500 to-indigo-500 animate-pulse" style={{ width: `${((idx + 1) / MESSAGES.length) * 100}%` }} />
      </div>
    </div>
  );
}
