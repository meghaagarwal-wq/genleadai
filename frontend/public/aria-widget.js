/**
 * Aria Lead Capture Widget — embeddable script.
 *
 * Usage on third-party sites:
 *   <script>
 *     window.AriaWidget = { tenantId: "ten_xyz", endpoint: "https://api.genleadai.com" };
 *   </script>
 *   <script src="https://api.genleadai.com/aria-widget.js" async defer></script>
 *
 * Falls back to whatever <script src> origin if endpoint is omitted.
 */
(function () {
  'use strict';
  if (window.__AriaWidgetLoaded__) return;
  window.__AriaWidgetLoaded__ = true;

  var W = window.AriaWidget || {};
  var TENANT = W.tenantId;
  // Derive endpoint from the script src if not explicitly set.
  var ENDPOINT = (W.endpoint || (function () {
    var scripts = document.getElementsByTagName('script');
    for (var i = scripts.length - 1; i >= 0; i--) {
      var s = scripts[i].getAttribute('src') || '';
      if (s.indexOf('aria-widget.js') !== -1) {
        try { return new URL(s, location.href).origin; } catch (e) { /* noop */ }
      }
    }
    return '';
  })()).replace(/\/+$/, '');

  if (!TENANT) {
    console.warn('[Aria] Missing tenantId — widget disabled.');
    return;
  }

  // Fetch config and render
  fetch(ENDPOINT + '/api/lead-capture/public-config?tenant_id=' + encodeURIComponent(TENANT))
    .catch(function () { return null; })
    .then(function (r) { return r ? r.json() : null; })
    .then(function (cfg) {
      var c = (cfg && cfg.config) || {
        mode: 'floating',
        title: 'Get in touch',
        subtitle: '',
        button_label: 'Send',
        accent_color: '#7C35DC',
        fields: ['first_name', 'email', 'phone', 'message'],
        require_consent: true,
        consent_text: 'I agree to be contacted.',
      };
      render(c);
    });

  function getUTM() {
    try {
      var p = new URLSearchParams(location.search);
      return { source: p.get('utm_source'), campaign: p.get('utm_campaign'), medium: p.get('utm_medium') };
    } catch (e) { return {}; }
  }

  function render(cfg) {
    var bg = cfg.accent_color || '#7C35DC';
    var css = [
      '.aria-w-launcher{position:fixed;right:24px;bottom:24px;width:60px;height:60px;border-radius:50%;background:' + bg + ';color:#fff;display:flex;align-items:center;justify-content:center;cursor:pointer;box-shadow:0 12px 30px rgba(0,0,0,0.2);z-index:2147483646;border:none;font-size:26px;font-family:system-ui,sans-serif;}',
      '.aria-w-panel{position:fixed;right:24px;bottom:96px;width:340px;max-width:calc(100vw - 48px);background:#fff;border-radius:16px;box-shadow:0 20px 50px rgba(0,0,0,0.2);z-index:2147483647;font-family:system-ui,-apple-system,sans-serif;color:#1A0A2E;display:none;overflow:hidden;}',
      '.aria-w-panel.aria-w-open{display:block;}',
      '.aria-w-head{padding:18px 20px;background:linear-gradient(135deg,' + bg + ' 0%,#C044E0 100%);color:#fff;}',
      '.aria-w-head h3{margin:0 0 4px;font-size:16px;font-weight:800;}',
      '.aria-w-head p{margin:0;font-size:12px;opacity:.92;}',
      '.aria-w-body{padding:14px 16px;max-height:60vh;overflow-y:auto;}',
      '.aria-w-row{margin:0 0 10px;}',
      '.aria-w-row label{display:block;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.12em;color:#5A4A7A;margin-bottom:4px;}',
      '.aria-w-row input,.aria-w-row textarea{width:100%;padding:8px 10px;border:1px solid #E8E0F5;border-radius:8px;font-size:13px;background:#fafafa;color:#1A0A2E;font-family:inherit;box-sizing:border-box;}',
      '.aria-w-row textarea{min-height:64px;resize:vertical;}',
      '.aria-w-consent{font-size:11px;color:#5A4A7A;display:flex;align-items:flex-start;gap:6px;line-height:1.4;margin:6px 0 12px;}',
      '.aria-w-submit{width:100%;background:' + bg + ';color:#fff;border:none;border-radius:10px;padding:10px;font-weight:700;font-size:13px;cursor:pointer;}',
      '.aria-w-submit:disabled{opacity:.5;cursor:wait;}',
      '.aria-w-foot{padding:8px 16px 14px;font-size:10px;color:#9B8AB0;text-align:center;}',
      '.aria-w-success{padding:32px 16px;text-align:center;}',
      '.aria-w-success h4{margin:8px 0 4px;font-size:15px;font-weight:800;color:#16A34A;}',
      '.aria-w-success p{margin:0;font-size:12px;color:#5A4A7A;}',
    ].join('\n');
    var style = document.createElement('style');
    style.textContent = css;
    document.head.appendChild(style);

    var launcher = document.createElement('button');
    launcher.className = 'aria-w-launcher';
    launcher.setAttribute('aria-label', 'Open contact form');
    launcher.innerHTML = '\u2709';
    document.body.appendChild(launcher);

    var panel = document.createElement('div');
    panel.className = 'aria-w-panel';
    var fields = (cfg.fields || ['first_name', 'email', 'phone', 'message']);

    var fieldHtml = fields.map(function (f) {
      var label = { first_name: 'Your Name', last_name: 'Last Name', email: 'Email', phone: 'WhatsApp Phone', company: 'Company', message: 'How can we help?' }[f] || f;
      var type = f === 'email' ? 'email' : f === 'phone' ? 'tel' : 'text';
      if (f === 'message') {
        return '<div class="aria-w-row"><label>' + label + '</label><textarea name="' + f + '" required></textarea></div>';
      }
      var req = (f === 'first_name' || f === 'phone' || f === 'email') ? 'required' : '';
      return '<div class="aria-w-row"><label>' + label + '</label><input name="' + f + '" type="' + type + '" ' + req + ' /></div>';
    }).join('');

    panel.innerHTML =
      '<div class="aria-w-head"><h3>' + (cfg.title || 'Get in touch') + '</h3>' + (cfg.subtitle ? '<p>' + cfg.subtitle + '</p>' : '') + '</div>' +
      '<form class="aria-w-body" id="aria-w-form">' + fieldHtml +
      (cfg.require_consent ? '<label class="aria-w-consent"><input type="checkbox" name="consent" required /> <span>' + (cfg.consent_text || 'I agree to be contacted.') + '</span></label>' : '') +
      '<button type="submit" class="aria-w-submit">' + (cfg.button_label || 'Send') + '</button>' +
      '</form>' +
      '<div class="aria-w-foot">Powered by Aria \u00b7 GenLeadAI</div>';
    document.body.appendChild(panel);

    launcher.addEventListener('click', function () { panel.classList.toggle('aria-w-open'); });

    var form = panel.querySelector('#aria-w-form');
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var btn = form.querySelector('.aria-w-submit');
      btn.disabled = true;
      btn.textContent = 'Sending\u2026';
      var fd = new FormData(form);
      var utm = getUTM();
      var body = {
        tenant_id: TENANT,
        consent: fd.get('consent') === 'on',
        first_name: fd.get('first_name') || '',
        last_name: fd.get('last_name') || '',
        email: fd.get('email') || null,
        phone: fd.get('phone') || '',
        company: fd.get('company') || '',
        message: fd.get('message') || '',
        utm_source: utm.source, utm_campaign: utm.campaign, utm_medium: utm.medium,
      };
      fetch(ENDPOINT + '/api/leads/capture', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
        .then(function (r) { return r.ok ? r.json() : r.text().then(function (t) { throw new Error(t); }); })
        .then(function () {
          panel.innerHTML = '<div class="aria-w-success"><h4>Thanks \u2014 you\'ll hear from us shortly</h4><p>Aria is preparing a personalised reply.</p></div><div class="aria-w-foot">Powered by Aria \u00b7 GenLeadAI</div>';
        })
        .catch(function (err) {
          btn.disabled = false;
          btn.textContent = cfg.button_label || 'Send';
          alert('Could not send right now \u2014 please try again. (' + (err.message || 'error') + ')');
        });
    });
  }
})();
