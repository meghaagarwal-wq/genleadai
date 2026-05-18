import React from 'react';
import { Warning, ArrowClockwise, House } from '@phosphor-icons/react';

/**
 * Wraps the app so a single render crash doesn't blank the entire screen.
 * Most common cause in this codebase: rendering a FastAPI 422 `detail` array
 * (array of Pydantic error objects) directly as a React child via toast or
 * inline text. The fix is normally upstream (stringify the detail), but this
 * boundary ensures the user still sees the chrome and can recover.
 */
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error('[ErrorBoundary]', error, info);
  }

  reset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (!this.state.hasError) return this.props.children;

    const errText =
      this.state.error?.message ||
      (typeof this.state.error === 'string' ? this.state.error : 'Unknown error');

    return (
      <div
        data-testid="error-boundary"
        className="min-h-screen flex items-center justify-center px-6 bg-gradient-to-br from-slate-50 via-white to-rose-50"
      >
        <div className="max-w-lg w-full bg-white/80 backdrop-blur-md border border-rose-200 rounded-3xl p-10 text-center shadow-lg">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-rose-100 text-rose-600 mb-5">
            <Warning size={28} weight="duotone" />
          </div>
          <p className="text-xs uppercase tracking-[0.18em] text-rose-600 font-semibold mb-2">
            Aria hit an unexpected error
          </p>
          <h1 className="text-2xl font-semibold text-slate-900 mb-3">
            Something rendered incorrectly
          </h1>
          <p className="text-slate-600 text-sm leading-relaxed mb-6 line-clamp-3">
            {errText}
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <button
              type="button"
              onClick={this.reset}
              data-testid="error-boundary-retry-btn"
              className="inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-slate-900 text-white text-sm font-medium hover:bg-slate-800 transition-colors"
            >
              <ArrowClockwise size={18} weight="bold" />
              Try again
            </button>
            <a
              href="/"
              data-testid="error-boundary-home-btn"
              className="inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-white border border-slate-200 text-slate-700 text-sm font-medium hover:bg-slate-50 transition-colors"
            >
              <House size={18} weight="bold" />
              Back to dashboard
            </a>
          </div>
        </div>
      </div>
    );
  }
}
