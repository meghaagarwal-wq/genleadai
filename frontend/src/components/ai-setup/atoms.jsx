// Reusable atoms for the AI Setup Assistant. Extracted from AISetupAssistant.js
// during the iter75 split. Behavior + data-testid contracts unchanged.
import React from 'react';

export function Card({ icon, title, tint = 'violet', testid, small = false, children }) {
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

export function FieldInline({ label, value, onChange, multiline = false }) {
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

export function Subhead({ label }) {
  return <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mt-2 mb-1">{label}</div>;
}

export function ChipList({ values, tint = 'slate' }) {
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

export function FieldInput({ label, value, onChange, testid, placeholder }) {
  return (
    <label className="block">
      <span className="text-[10px] uppercase tracking-wider font-bold text-slate-600">{label}</span>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        data-testid={testid}
        placeholder={placeholder}
        className="mt-0.5 w-full text-xs bg-white border border-violet-200 rounded px-2 py-1.5 focus:outline-none focus:border-violet-500"
      />
    </label>
  );
}
