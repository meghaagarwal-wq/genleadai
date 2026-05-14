/**
 * Aria Inline Contact Form Widget — embeddable inline form for blog
 * posts, landing pages, and any third-party site that wants Aria to
 * capture inbound interest right inside the page (no popup, no chat
 * bubble — just a clean form).
 *
 * Posts to /api/contact/request, the same endpoint that powers the
 * Master Admin Contact Inbox.
 *
 * Usage (drop anywhere inside the host page's <body>):
 *
 *   <div id="aria-form-widget"></div>
 *   <script>
 *     window.AriaFormWidget = {
 *       endpoint: 'https://api.genleadai.com', // optional; auto-derived
 *       title:    'Talk to us about Aria',     // optional
 *       subtitle: 'We typically reply within 1 business day.', // optional
 *       buttonLabel: 'Send message',           // optional
 *       color:    '#7C35DC',                   // optional
 *       page:     'docs',                      // optional analytics tag
 *     };
 *   </script>
 *   <script src="https://api.genleadai.com/aria-form-widget.js" async defer></script>
 */
(function () {
  'use strict';
  if (window.__AriaFormWidgetLoaded__) return;
  window.__AriaFormWidgetLoaded__ = true;

  var W = window.AriaFormWidget || {};
  var COLOR = W.color || '#7C35DC';
  var TITLE = W.title || 'Talk to us';
  var SUBTITLE = W.subtitle || "We typically reply within 1 business day.";
  var BUTTON_LABEL = W.buttonLabel || 'Send message';
  var PAGE = W.page || 'inline-widget';

  // Derive endpoint from this script's own URL if not passed.
  var endpoint = (W.endpoint || (function () {
    var scripts = document.getElementsByTagName('script');
    for (var i = scripts.length - 1; i >= 0; i--) {
      var s = scripts[i].getAttribute('src') || '';
      if (s.indexOf('aria-form-widget.js') !== -1) {
        try { return new URL(s, location.href).origin; } catch (e) {}
      }
    }
    return '';
  })()).replace(/\/+$/, '');

  function attachStyles() {
    var s = document.createElement('style');
    s.textContent = ''
      + '.aria-fw{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;max-width:480px;width:100%;'
      + 'background:linear-gradient(135deg,#FFFFFF 0%,#FAF7FF 100%);border:1px solid #E0D4F7;border-radius:18px;'
      + 'padding:24px;box-shadow:0 12px 32px rgba(124,53,220,0.10);box-sizing:border-box;color:#1A0A2E;}'
      + '.aria-fw__eyebrow{font-size:10px;font-weight:800;letter-spacing:0.22em;text-transform:uppercase;color:' + COLOR + ';margin-bottom:6px;}'
      + '.aria-fw__title{font-size:20px;font-weight:800;line-height:1.15;margin:0 0 4px 0;}'
      + '.aria-fw__subtitle{font-size:13px;color:#5A4A7A;margin:0 0 16px 0;}'
      + '.aria-fw__field{display:block;margin-bottom:10px;}'
      + '.aria-fw__field label{display:block;font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:0.18em;color:#9B8AB0;margin-bottom:4px;}'
      + '.aria-fw__field input,.aria-fw__field textarea{width:100%;background:#fff;border:1px solid #E8E0F5;border-radius:10px;padding:9px 12px;font-size:13.5px;color:#1A0A2E;box-sizing:border-box;font-family:inherit;outline:none;transition:border-color 160ms ease,box-shadow 160ms ease;}'
      + '.aria-fw__field input:focus,.aria-fw__field textarea:focus{border-color:' + COLOR + ';box-shadow:0 0 0 3px ' + COLOR + '20;}'
      + '.aria-fw__field textarea{resize:vertical;min-height:88px;}'
      + '.aria-fw__btn{width:100%;margin-top:6px;padding:11px 16px;border:none;border-radius:10px;background:' + COLOR + ';color:#fff;font-weight:800;font-size:13px;letter-spacing:0.02em;cursor:pointer;transition:transform 160ms ease,box-shadow 160ms ease,opacity 160ms ease;}'
      + '.aria-fw__btn:hover:not(:disabled){transform:translateY(-1px);box-shadow:0 8px 20px ' + COLOR + '55;}'
      + '.aria-fw__btn:disabled{opacity:.55;cursor:not-allowed;}'
      + '.aria-fw__success{background:#DCFCE7;border:1px solid #16A34A33;color:#15803D;padding:12px 14px;border-radius:10px;font-size:13px;}'
      + '.aria-fw__error{background:#FEE2E2;border:1px solid #DC262633;color:#B91C1C;padding:10px 12px;border-radius:10px;font-size:12px;margin-bottom:10px;}'
      + '.aria-fw__powered{text-align:center;margin-top:14px;font-size:10px;letter-spacing:0.18em;font-weight:700;text-transform:uppercase;color:#A0A8C0;}'
      + '.aria-fw__powered a{color:#7C35DC;text-decoration:none;}';
    document.head.appendChild(s);
  }

  function render(host) {
    host.classList.add('aria-fw');
    host.setAttribute('data-testid', 'aria-form-widget');
    host.innerHTML = ''
      + '<div class="aria-fw__eyebrow">Aria · GenLeadAI</div>'
      + '<h3 class="aria-fw__title">' + esc(TITLE) + '</h3>'
      + '<p class="aria-fw__subtitle">' + esc(SUBTITLE) + '</p>'
      + '<form id="aria-fw-form" novalidate>'
      + '  <div class="aria-fw__error" id="aria-fw-error" style="display:none;"></div>'
      + '  <div class="aria-fw__field"><label>Your name</label><input name="name" required maxlength="120" autocomplete="name"/></div>'
      + '  <div class="aria-fw__field"><label>Email</label><input name="email" type="email" required autocomplete="email"/></div>'
      + '  <div class="aria-fw__field"><label>Company <span style="text-transform:none;font-weight:600;color:#C9B6FF;">(optional)</span></label><input name="company" maxlength="200" autocomplete="organization"/></div>'
      + '  <div class="aria-fw__field"><label>Message</label><textarea name="message" required minlength="3" maxlength="4000"></textarea></div>'
      + '  <button type="submit" class="aria-fw__btn">' + esc(BUTTON_LABEL) + '</button>'
      + '</form>'
      + '<div class="aria-fw__powered">Powered by <a href="https://app.genleadai.com" target="_blank" rel="noopener">Aria · GenLeadAI</a></div>';
    var form = host.querySelector('#aria-fw-form');
    var btn  = host.querySelector('.aria-fw__btn');
    var err  = host.querySelector('#aria-fw-error');
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      err.style.display = 'none';
      var fd = new FormData(form);
      var payload = {
        name: (fd.get('name') || '').trim(),
        email: (fd.get('email') || '').trim(),
        company: (fd.get('company') || '').trim(),
        website: location.href,
        message: (fd.get('message') || '').trim(),
        page: PAGE,
      };
      if (!payload.name || !payload.email || payload.message.length < 3) {
        err.textContent = 'Please fill in name, email, and a short message.';
        err.style.display = 'block';
        return;
      }
      btn.disabled = true;
      btn.textContent = 'Sending…';
      fetch(endpoint + '/api/contact/request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        keepalive: true,
      })
        .then(function (r) { return r.ok ? r.json() : Promise.reject(r); })
        .then(function () {
          host.innerHTML = '<div class="aria-fw__success">Thanks — we\'ll be in touch within 1 business day.</div><div class="aria-fw__powered">Powered by <a href="https://app.genleadai.com" target="_blank" rel="noopener">Aria · GenLeadAI</a></div>';
        })
        .catch(function () {
          err.textContent = 'Could not send. Please try again or email hi@genleadai.com.';
          err.style.display = 'block';
          btn.disabled = false;
          btn.textContent = BUTTON_LABEL;
        });
    });
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c];
    });
  }

  function init() {
    attachStyles();
    var host = document.getElementById('aria-form-widget');
    if (host) render(host);
    // Also render into any element with data-aria-form attr
    var others = document.querySelectorAll('[data-aria-form]');
    for (var i = 0; i < others.length; i++) render(others[i]);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
