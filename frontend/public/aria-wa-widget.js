/**
 * Aria Click-to-WhatsApp Widget — embeddable script (v2 lite alternative to aria-widget.js).
 *
 * Drops a fixed bottom-right "Chat on WhatsApp" floating button. One click
 * opens wa.me/<phone>?text=<encoded_text> in a new tab, and fires a
 * background ping to /api/integrations/widget/wa-click (optional analytics
 * — server logs to integration_events; never blocks the WA deeplink).
 *
 * Usage on third-party sites:
 *   <script>
 *     window.AriaWaWidget = {
 *       phone: '+919999999999',
 *       text: 'Hi! I saw your website and want to know more.',
 *       tenantId: 'ten_xyz',          // optional — enables click analytics
 *       endpoint: 'https://api.genleadai.com', // optional, auto-derived
 *       label: 'Chat on WhatsApp',    // optional
 *       color: '#25D366',             // optional
 *     };
 *   </script>
 *   <script src="https://api.genleadai.com/aria-wa-widget.js" async defer></script>
 */
(function () {
  'use strict';
  if (window.__AriaWaWidgetLoaded__) return;
  window.__AriaWaWidgetLoaded__ = true;

  var W = window.AriaWaWidget || {};
  var phoneRaw = String(W.phone || '').trim();
  if (!phoneRaw) {
    console.warn('[AriaWaWidget] Missing window.AriaWaWidget.phone — widget will not render.');
    return;
  }
  var phone = phoneRaw.replace(/[^0-9]/g, '');
  if (!phone) return;

  var text  = W.text  || 'Hi! I would like to know more.';
  var label = W.label || 'Chat on WhatsApp';
  var color = W.color || '#25D366';

  var endpoint = (W.endpoint || (function () {
    var scripts = document.getElementsByTagName('script');
    for (var i = scripts.length - 1; i >= 0; i--) {
      var s = scripts[i].getAttribute('src') || '';
      if (s.indexOf('aria-wa-widget.js') !== -1) {
        try { return new URL(s, location.href).origin; } catch (e) { /* noop */ }
      }
    }
    return '';
  })()).replace(/\/+$/, '');

  function buildHref() {
    return 'https://wa.me/' + phone + '?text=' + encodeURIComponent(text);
  }

  function pingClick() {
    if (!W.tenantId || !endpoint) return;
    try {
      var body = JSON.stringify({
        tenant_id: W.tenantId,
        phone: phone,
        page_url: location.href,
        referrer: document.referrer || null,
      });
      // Best-effort, non-blocking; the WA tab opens regardless.
      if (navigator.sendBeacon) {
        navigator.sendBeacon(endpoint + '/api/integrations/widget/wa-click', new Blob([body], { type: 'application/json' }));
      } else {
        fetch(endpoint + '/api/integrations/widget/wa-click', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body, keepalive: true }).catch(function(){});
      }
    } catch (e) { /* noop */ }
  }

  // ── DOM render ───────────────────────────────────────────────────────
  var style = document.createElement('style');
  style.textContent = ''
    + '.aria-wa-fab{position:fixed;right:20px;bottom:20px;z-index:2147483600;display:inline-flex;align-items:center;gap:8px;padding:12px 18px;'
    + 'background:' + color + ';color:#fff;border-radius:999px;text-decoration:none;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;'
    + 'font-weight:700;font-size:14px;box-shadow:0 8px 24px rgba(37,211,102,0.35);cursor:pointer;'
    + 'transition:transform 180ms ease, box-shadow 180ms ease;}'
    + '.aria-wa-fab:hover{transform:translateY(-2px);box-shadow:0 12px 32px rgba(37,211,102,0.45);}'
    + '.aria-wa-fab svg{width:18px;height:18px;}'
    + '.aria-wa-fab::before{content:"";position:absolute;inset:-4px;border-radius:999px;border:2px solid ' + color + ';opacity:.4;animation:aria-wa-pulse 2.2s cubic-bezier(.2,.8,.2,1) infinite;pointer-events:none;}'
    + '@keyframes aria-wa-pulse{0%{transform:scale(.95);opacity:.45}70%{transform:scale(1.15);opacity:0}100%{opacity:0}}';
  document.head.appendChild(style);

  function render() {
    var a = document.createElement('a');
    a.className = 'aria-wa-fab';
    a.setAttribute('data-testid', 'aria-wa-fab');
    a.href = buildHref();
    a.target = '_blank';
    a.rel = 'noopener';
    a.innerHTML = ''
      + '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">'
      + '<path d="M20.52 3.48A11.93 11.93 0 0 0 12.03 0C5.42 0 .06 5.36.06 11.97c0 2.11.55 4.16 1.6 5.97L0 24l6.2-1.63a11.95 11.95 0 0 0 5.82 1.5h.01c6.6 0 11.97-5.37 11.97-11.97 0-3.2-1.24-6.2-3.48-8.42zM12.03 22a9.92 9.92 0 0 1-5.06-1.38l-.36-.21-3.68.97.98-3.58-.24-.37A9.92 9.92 0 0 1 2.05 11.97C2.05 6.46 6.52 1.99 12.03 1.99c2.66 0 5.16 1.04 7.04 2.92a9.92 9.92 0 0 1 2.92 7.06c0 5.51-4.47 9.98-9.97 9.98zm5.45-7.46c-.3-.15-1.77-.87-2.04-.97-.27-.1-.47-.15-.67.15-.2.3-.77.97-.94 1.17-.18.2-.35.22-.65.07-.3-.15-1.27-.47-2.42-1.5-.9-.8-1.5-1.78-1.68-2.08-.18-.3-.02-.46.13-.6.13-.13.3-.35.45-.52.15-.18.2-.3.3-.5.1-.2.05-.37-.02-.52-.07-.15-.67-1.62-.92-2.22-.24-.58-.5-.5-.67-.5h-.57c-.2 0-.52.07-.8.37-.27.3-1.05 1.02-1.05 2.5 0 1.47 1.08 2.9 1.23 3.1.15.2 2.12 3.24 5.13 4.55.72.31 1.28.5 1.72.64.72.23 1.38.2 1.9.12.58-.08 1.77-.72 2.02-1.42.25-.7.25-1.3.18-1.42-.07-.13-.27-.2-.57-.35z"/>'
      + '</svg>'
      + label;
    a.addEventListener('click', pingClick);
    document.body.appendChild(a);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', render);
  } else {
    render();
  }
})();
