/**
 * demoSession — iter177
 *
 * Tiny localStorage-backed session + identity helpers for the /aria-demo
 * surface. Session ID is a short UUID written once per browser; identity
 * is a { name, email } blob the prospect gives us via the prefill prompt.
 *
 * All analytics calls are fire-and-forget (keepalive on best-effort basis)
 * so they never block the UI.
 */

const SID_KEY     = 'aria-demo-sid';
const IDENT_KEY   = 'aria-demo-identity';
const STARTED_KEY = 'aria-demo-started-at';

function uuid4() {
  // RFC4122 v4; prefers crypto.randomUUID when available
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  const b = new Uint8Array(16);
  if (typeof crypto !== 'undefined' && crypto.getRandomValues) crypto.getRandomValues(b);
  else for (let i = 0; i < 16; i++) b[i] = Math.floor(Math.random() * 256);
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = Array.from(b, (x) => x.toString(16).padStart(2, '0')).join('');
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

export function getOrCreateSessionId() {
  if (typeof window === 'undefined') return '';
  try {
    let sid = window.localStorage.getItem(SID_KEY);
    if (!sid) {
      sid = uuid4();
      window.localStorage.setItem(SID_KEY, sid);
      window.localStorage.setItem(STARTED_KEY, new Date().toISOString());
    }
    return sid;
  } catch (_) {
    // Private-mode / blocked storage — fall back to in-memory sid for the tab
    if (!window.__ariaDemoSid) window.__ariaDemoSid = uuid4();
    return window.__ariaDemoSid;
  }
}

export function getIdentity() {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(IDENT_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (_) { return null; }
}

export function setIdentity(ident) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(IDENT_KEY, JSON.stringify({
      name:  (ident?.name  || '').toString().slice(0, 120),
      email: (ident?.email || '').toString().slice(0, 200),
      at:    new Date().toISOString(),
    }));
  } catch (_) { /* noop */ }
}

export function clearIdentity() {
  try { window.localStorage.removeItem(IDENT_KEY); } catch (_) {}
}

export function postAnalytics(apiUrl, endpoint, body) {
  if (!apiUrl) return Promise.resolve();
  try {
    return fetch(`${apiUrl}/api/demo-analytics/${endpoint}`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(body || {}),
      keepalive: true,
    }).catch(() => {});
  } catch (_) { return Promise.resolve(); }
}
