/**
 * RecordDemoButton — iter174
 *
 * A top-bar button that records the browser tab (screen + presenter mic)
 * using MediaRecorder, then shows a modal to review + email the recording.
 * On send we POST the blob to /api/demo-recording/upload, then hit
 * /api/demo-recording/send with the returned share URL.
 *
 * Defensive: any browser without getDisplayMedia (Safari on iOS, some
 * embed contexts) falls back to a "not supported" toast — the demo
 * never breaks.
 */
import React, { useEffect, useRef, useState } from 'react';
import { Video, Square, Mail, X, Copy, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';

const SUPPORTS_DISPLAY = typeof navigator !== 'undefined'
  && navigator.mediaDevices
  && typeof navigator.mediaDevices.getDisplayMedia === 'function';

export default function RecordDemoButton({ brand, apiUrl, T }) {
  const [state, setState] = useState('idle'); // idle | recording | review | uploading | sent | error
  const [error, setError] = useState('');
  const [seconds, setSeconds] = useState(0);
  const [videoBlob, setVideoBlob] = useState(null);
  const [videoUrl, setVideoUrl] = useState('');
  const [shareUrl, setShareUrl] = useState('');
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [copied, setCopied] = useState(false);
  const recorderRef = useRef(null);
  const streamRef   = useRef(null);
  const chunksRef   = useRef([]);
  const timerRef    = useRef(null);

  useEffect(() => () => cleanup(), []);

  function cleanup() {
    try { recorderRef.current?.stop(); } catch { /* noop */ }
    streamRef.current?.getTracks().forEach((t) => t.stop());
    if (timerRef.current) clearInterval(timerRef.current);
  }

  async function startRecording() {
    if (!SUPPORTS_DISPLAY) {
      setError('Screen recording is not supported in this browser. Try desktop Chrome.');
      setState('error');
      return;
    }
    try {
      const screen = await navigator.mediaDevices.getDisplayMedia({
        video: { frameRate: 12 }, audio: true,
      });
      let mic;
      try {
        mic = await navigator.mediaDevices.getUserMedia({ audio: true });
      } catch { mic = null; }
      const combined = new MediaStream([
        ...screen.getVideoTracks(),
        ...screen.getAudioTracks(),
        ...(mic ? mic.getAudioTracks() : []),
      ]);
      streamRef.current = combined;

      chunksRef.current = [];
      const mime = pickMime();
      const rec = new MediaRecorder(combined, mime ? { mimeType: mime, videoBitsPerSecond: 900_000 } : undefined);
      rec.ondataavailable = (e) => { if (e.data && e.data.size) chunksRef.current.push(e.data); };
      rec.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: rec.mimeType || 'video/webm' });
        setVideoBlob(blob);
        setVideoUrl(URL.createObjectURL(blob));
        streamRef.current?.getTracks().forEach((t) => t.stop());
        if (timerRef.current) clearInterval(timerRef.current);
        setState('review');
      };
      screen.getVideoTracks()[0].onended = () => {
        // User clicked the browser "Stop sharing" bar
        if (rec.state !== 'inactive') rec.stop();
      };
      recorderRef.current = rec;
      rec.start(1000);
      setState('recording');
      setSeconds(0);
      timerRef.current = setInterval(() => setSeconds((s) => s + 1), 1000);
    } catch (e) {
      setError(e?.message || 'Recording cancelled or denied.');
      setState('error');
    }
  }

  function stopRecording() {
    try { recorderRef.current?.stop(); } catch { /* noop */ }
  }

  async function uploadAndSend() {
    if (!videoBlob) return;
    setState('uploading');
    try {
      const fd = new FormData();
      fd.append('file', videoBlob, `demo-${Date.now()}.webm`);
      fd.append('brand', brand?.companyName || '');
      fd.append('duration_sec', String(seconds));
      const up = await fetch(`${apiUrl}/api/demo-recording/upload`, { method: 'POST', body: fd });
      const upJson = await up.json();
      if (!up.ok) throw new Error(upJson.detail || 'Upload failed.');
      setShareUrl(upJson.share_url || '');

      if (email) {
        const sendRes = await fetch(`${apiUrl}/api/demo-recording/send`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            recording_id: upJson.recording_id,
            to_email: email,
            brand: brand?.companyName || 'your team',
            message,
          }),
        });
        await sendRes.json();
      }
      setState('sent');
    } catch (e) {
      setError(e?.message || 'Something went wrong.');
      setState('error');
    }
  }

  function reset() {
    if (videoUrl) URL.revokeObjectURL(videoUrl);
    setVideoBlob(null); setVideoUrl(''); setShareUrl(''); setEmail(''); setMessage('');
    setSeconds(0); setError(''); setState('idle');
  }

  const modalOpen = ['review', 'uploading', 'sent', 'error'].includes(state);

  return (
    <>
      {state === 'idle' && (
        <button
          onClick={startRecording}
          data-testid="record-demo-btn"
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium transition-colors"
          style={{ background: T.card, color: T.ink, border: `1px solid ${T.line}` }}
          title="Record the demo — share a clip with the prospect after the call"
        >
          <Video size={12} strokeWidth={2.5} /> Record
        </button>
      )}
      {state === 'recording' && (
        <button
          onClick={stopRecording}
          data-testid="record-stop-btn"
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium transition-all"
          style={{ background: T.danger, color: '#0B0A14', fontWeight: 700 }}
        >
          <Square size={11} strokeWidth={3} fill="currentColor" />
          <span className="tabular-nums">{fmtTime(seconds)}</span>
        </button>
      )}

      {modalOpen && (
        <div className="fixed inset-0 z-[58] flex items-center justify-center p-6"
          style={{ background: 'rgba(11,10,20,0.72)', backdropFilter: 'blur(10px)' }}
          data-testid="record-modal">
          <div className="w-full max-w-[640px] rounded-3xl overflow-hidden"
            style={{ background: T.card, border: `1px solid ${T.line}`, boxShadow: '0 40px 120px rgba(124,53,220,0.28)' }}>
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="inline-flex items-center gap-2 text-xs px-2.5 py-1 rounded-full uppercase tracking-[0.14em]"
                  style={{ background: T.accentSoft, color: T.accent, fontWeight: 700 }}>
                  <Video size={11} /> {state === 'sent' ? 'Sent' : state === 'uploading' ? 'Uploading' : state === 'error' ? 'Error' : 'Review'}
                </div>
                <button onClick={reset} className="w-8 h-8 rounded-full flex items-center justify-center hover:bg-white/5"
                  style={{ color: T.muted }} data-testid="record-modal-close">
                  <X size={16} />
                </button>
              </div>

              {state === 'review' && (
                <>
                  <h3 className="text-[20px] font-semibold tracking-tight"
                    style={{ fontFamily: T.fontDisplay, color: T.ink }}>
                    Here's your walkthrough
                  </h3>
                  <p className="text-sm mt-1" style={{ color: T.muted }}>
                    {fmtTime(seconds)} · {(videoBlob?.size / 1024 / 1024).toFixed(1)} MB · sends in one click
                  </p>
                  <video src={videoUrl} controls playsInline
                    className="w-full mt-4 rounded-xl"
                    style={{ background: '#000', maxHeight: 300 }}
                    data-testid="record-preview" />
                  <div className="mt-4 space-y-2">
                    <input
                      value={email} onChange={(e) => setEmail(e.target.value)}
                      placeholder="Prospect's email (optional)"
                      className="w-full px-3 py-2.5 rounded-lg text-sm outline-none"
                      style={{ background: T.canvas, color: T.ink, border: `1px solid ${T.line}` }}
                      data-testid="record-email-input"
                    />
                    <textarea
                      value={message} onChange={(e) => setMessage(e.target.value)}
                      placeholder="Optional note that appears in the email…"
                      rows={2}
                      className="w-full px-3 py-2.5 rounded-lg text-sm outline-none resize-none"
                      style={{ background: T.canvas, color: T.ink, border: `1px solid ${T.line}` }}
                      data-testid="record-message-input"
                    />
                  </div>
                  <div className="mt-5 flex items-center gap-2 justify-end">
                    <button onClick={reset} className="text-sm px-3 py-2 rounded-lg" style={{ color: T.muted, background: T.canvas, border: `1px solid ${T.line}` }}>
                      Discard
                    </button>
                    <button
                      onClick={uploadAndSend}
                      data-testid="record-send-btn"
                      className="text-sm px-4 py-2 rounded-lg inline-flex items-center gap-2 font-semibold"
                      style={{ background: T.accent, color: '#fff' }}
                    >
                      <Mail size={14} /> {email ? 'Send & get link' : 'Upload & get link'}
                    </button>
                  </div>
                </>
              )}

              {state === 'uploading' && (
                <div className="py-10 flex flex-col items-center gap-4 text-sm" style={{ color: T.muted }}>
                  <Loader2 size={28} className="animate-spin" style={{ color: T.accent }} />
                  Uploading and preparing your share link…
                </div>
              )}

              {state === 'sent' && (
                <>
                  <div className="py-6 flex flex-col items-center gap-3 text-center">
                    <CheckCircle2 size={36} style={{ color: T.success }} />
                    <div className="text-lg font-semibold" style={{ color: T.ink, fontFamily: T.fontDisplay }}>Sent.</div>
                    <div className="text-sm" style={{ color: T.muted }}>
                      {email ? `Delivered to ${email}` : 'Ready to share — copy the link below.'}
                    </div>
                  </div>
                  <div className="mt-2 flex items-center gap-2 rounded-lg p-2.5"
                    style={{ background: T.canvas, border: `1px solid ${T.line}` }}>
                    <input readOnly value={shareUrl} data-testid="record-share-url"
                      className="flex-1 bg-transparent text-xs outline-none"
                      style={{ color: T.ink }} />
                    <button
                      onClick={() => { navigator.clipboard.writeText(shareUrl); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
                      className="text-xs px-2.5 py-1.5 rounded-md inline-flex items-center gap-1.5"
                      style={{ background: T.accent, color: '#fff', fontWeight: 600 }}
                      data-testid="record-copy-btn"
                    >
                      {copied ? <><CheckCircle2 size={12} /> Copied</> : <><Copy size={12} /> Copy</>}
                    </button>
                  </div>
                  <div className="mt-4 flex justify-end">
                    <button onClick={reset} className="text-sm px-3 py-2 rounded-lg font-semibold"
                      style={{ background: T.canvas, color: T.ink, border: `1px solid ${T.line}` }}>
                      Done
                    </button>
                  </div>
                </>
              )}

              {state === 'error' && (
                <>
                  <div className="py-6 flex flex-col items-center gap-3 text-center">
                    <AlertCircle size={32} style={{ color: T.danger }} />
                    <div className="text-lg font-semibold" style={{ color: T.ink }}>Recording didn't complete</div>
                    <div className="text-sm max-w-[440px]" style={{ color: T.muted }}>{error}</div>
                  </div>
                  <div className="mt-3 flex justify-end">
                    <button onClick={reset} className="text-sm px-3 py-2 rounded-lg font-semibold"
                      style={{ background: T.accent, color: '#fff' }}>
                      Close
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ── helpers ──
function fmtTime(s) {
  const m = Math.floor(s / 60), r = s % 60;
  return `${m}:${String(r).padStart(2, '0')}`;
}

function pickMime() {
  const candidates = [
    'video/webm;codecs=vp9,opus',
    'video/webm;codecs=vp8,opus',
    'video/webm',
    'video/mp4',
  ];
  if (typeof MediaRecorder === 'undefined') return null;
  for (const c of candidates) {
    if (MediaRecorder.isTypeSupported(c)) return c;
  }
  return null;
}
