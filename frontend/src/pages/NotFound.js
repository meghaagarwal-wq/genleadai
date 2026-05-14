import React from 'react';
import { Link } from 'react-router-dom';
import { Compass, House, ArrowLeft } from '@phosphor-icons/react';

export default function NotFound() {
  return (
    <div
      data-testid="not-found-page"
      className="min-h-[70vh] flex items-center justify-center px-6"
    >
      <div className="max-w-lg w-full bg-white/70 backdrop-blur-md border border-slate-200/70 rounded-3xl p-10 text-center shadow-sm">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 text-white mb-6 shadow-lg">
          <Compass size={32} weight="duotone" />
        </div>
        <p className="text-xs uppercase tracking-[0.18em] text-violet-600 font-semibold mb-2">
          Aria couldn't find that
        </p>
        <h1 className="text-3xl font-semibold text-slate-900 mb-3">
          This page isn't part of your workspace
        </h1>
        <p className="text-slate-600 text-sm leading-relaxed mb-8">
          The link you followed may be outdated or the page may have moved.
          Head back to your command center and Aria will pick up where you left off.
        </p>
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <Link
            to="/"
            data-testid="not-found-home-btn"
            className="inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-slate-900 text-white text-sm font-medium hover:bg-slate-800 transition-colors"
          >
            <House size={18} weight="bold" />
            Back to dashboard
          </Link>
          <button
            type="button"
            data-testid="not-found-back-btn"
            onClick={() => window.history.back()}
            className="inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-white border border-slate-200 text-slate-700 text-sm font-medium hover:bg-slate-50 transition-colors"
          >
            <ArrowLeft size={18} weight="bold" />
            Go back
          </button>
        </div>
      </div>
    </div>
  );
}
