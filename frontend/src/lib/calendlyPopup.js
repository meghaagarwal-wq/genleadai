/**
 * calendlyPopup — iter176
 *
 * Tiny wrapper around Calendly's official inline-popup widget so we can
 * open the booking flow WITHOUT a new tab. Lazy-loads the widget script
 * and CSS the first time it's used, then caches. Falls back to a new
 * tab if the widget script can't load (offline / CSP block).
 *
 * Query params we always pass to Calendly:
 *   utm_source     = 'aria-demo'
 *   utm_medium     = 'inline-popup'
 *   utm_content    = the personalized demo URL (so it shows up in the
 *                    Calendly event notification the founder receives).
 *   utm_campaign   = the prospect's domain (if we have it).
 *
 * Calendly surfaces UTM params in every event notification + integrations
 * export, so the founder sees which personalized demo the booker was on.
 */

const CAL_JS  = 'https://assets.calendly.com/assets/external/widget.js';
const CAL_CSS = 'https://assets.calendly.com/assets/external/widget.css';
let _loading = null;

function loadCalendly() {
  if (typeof window === 'undefined') return Promise.reject(new Error('no-window'));
  if (window.Calendly) return Promise.resolve(window.Calendly);
  if (_loading) return _loading;
  _loading = new Promise((resolve, reject) => {
    // CSS
    if (!document.querySelector(`link[href="${CAL_CSS}"]`)) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = CAL_CSS;
      document.head.appendChild(link);
    }
    // JS
    const s = document.createElement('script');
    s.src = CAL_JS;
    s.async = true;
    s.onload = () => window.Calendly ? resolve(window.Calendly) : reject(new Error('no-calendly'));
    s.onerror = () => reject(new Error('script-load-failed'));
    document.head.appendChild(s);
  });
  return _loading;
}

/**
 * Open Calendly as an inline popup.
 * @param {string} baseUrl  Base scheduling URL (e.g. https://calendly.com/foo/30min)
 * @param {object} context  { demoUrl, company, mode, scenario, source } — becomes UTMs.
 */
export async function openCalendlyPopup(baseUrl, context = {}) {
  if (!baseUrl || !/^https?:\/\//.test(baseUrl)) return false;
  const u = new URL(baseUrl);
  const params = u.searchParams;

  if (context.source)   params.set('utm_source',   String(context.source).slice(0, 60));
  else                  params.set('utm_source',   'aria-demo');
  params.set('utm_medium', 'inline-popup');

  if (context.demoUrl)  params.set('utm_content',  String(context.demoUrl).slice(0, 500));
  if (context.company)  params.set('utm_campaign', String(context.company).slice(0, 120));
  if (context.mode)     params.set('utm_term',     `mode:${context.mode}${context.scenario ? '|scenario:' + context.scenario : ''}`.slice(0, 120));

  // Prefill questions on the Calendly booking form (optional).
  if (context.name)     params.set('name',  String(context.name).slice(0, 120));
  if (context.email)    params.set('email', String(context.email).slice(0, 200));

  // Calendly also renders `name` + `email` prefill if we pass them; skip PII.
  const finalUrl = u.toString();

  try {
    const cal = await loadCalendly();
    cal.initPopupWidget({ url: finalUrl });
    return true;
  } catch (e) {
    // Fallback — never break the CTA
    window.open(finalUrl, '_blank', 'noopener,noreferrer');
    return false;
  }
}
