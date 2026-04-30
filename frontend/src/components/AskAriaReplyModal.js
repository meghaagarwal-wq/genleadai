import React, { useState } from 'react';
import { X, Sparkle, Copy, CheckCircle, ArrowClockwise, PaperPlaneTilt, WhatsappLogo, EnvelopeSimple, LinkedinLogo, Phone } from '@phosphor-icons/react';
import api from '../config/api';

const CHANNELS = [
  { id: 'whatsapp', label: 'WhatsApp', icon: WhatsappLogo },
  { id: 'email', label: 'Email', icon: EnvelopeSimple },
  { id: 'linkedin', label: 'LinkedIn', icon: LinkedinLogo },
  { id: 'call_script', label: 'Call Script', icon: Phone },
];

const TONES = [
  { id: 'founder_led', label: 'Founder-led' },
  { id: 'friendly', label: 'Friendly' },
  { id: 'direct', label: 'Direct' },
  { id: 'premium', label: 'Premium' },
  { id: 'consultative', label: 'Consultative' },
  { id: 'sharp_closer', label: 'Sharp Closer' },
  { id: 'soft_nurture', label: 'Soft Nurture' },
];

const AskAriaReplyModal = ({ leadId, leadName, onClose }) => {
  const [channel, setChannel] = useState('whatsapp');
  const [tone, setTone] = useState('founder_led');
  const [userNote, setUserNote] = useState('');
  const [reply, setReply] = useState('');
  const [loading, setLoading] = useState(false);
  const [aiPowered, setAiPowered] = useState(false);
  const [copied, setCopied] = useState(false);
  const [edited, setEdited] = useState(false);

  const generate = async () => {
    setLoading(true);
    setEdited(false);
    try {
      const res = await api.post(`/api/aria-agent/workspace/ask-reply/${leadId}`, { channel, tone, user_note: userNote });
      setReply(res.data?.message || '');
      setAiPowered(!!res.data?.ai_powered);
    } catch (err) {
      setReply('ARIA could not reach Claude right now. Please try again.');
      setAiPowered(false);
    } finally { setLoading(false); }
  };

  React.useEffect(() => { generate(); /* eslint-disable-next-line */ }, []);

  const copyReply = () => {
    if (!reply) return;
    navigator.clipboard.writeText(reply);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4" data-testid="ask-aria-reply-modal">
      <div className="absolute inset-0 bg-black/55 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-[560px] max-h-[90vh] overflow-y-auto rounded-3xl bg-white overflow-hidden aria-fade-up" style={{ boxShadow: '0 24px 64px -12px rgba(26,15,56,0.35)' }}>
        {/* Header */}
        <div className="relative px-6 py-5 aria-grain border-b border-[#F0ECF9]" style={{ background: 'var(--gradient-aria-deep)' }}>
          <button onClick={onClose} className="absolute top-4 right-4 p-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white border border-white/20 backdrop-blur-sm transition-colors" data-testid="reply-modal-close"><X size={16} /></button>
          <div className="relative">
            <div className="flex items-center gap-2 mb-1">
              <Sparkle size={11} weight="fill" className="text-[#C9B6FF] aria-glow" />
              <span className="text-[10px] font-bold uppercase tracking-[0.3em] text-[#C9B6FF] numeric">ARIA · COMPOSE REPLY</span>
              {aiPowered && <span className="px-1.5 py-0.5 rounded text-[9px] font-extrabold uppercase tracking-[0.15em] bg-[#DCFCE7] text-[#16A34A] border border-[#16A34A]/30 numeric">AI-POWERED</span>}
            </div>
            <div className="font-display text-2xl text-white leading-tight">Reply to {leadName}</div>
            <div className="text-xs text-[#C9B6FF] mt-1 font-display-italic">ARIA drafts, you approve.</div>
          </div>
        </div>

        {/* Controls */}
        <div className="px-6 pt-4 space-y-4">
          {/* Channel */}
          <div>
            <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#9B8AB0] mb-2 numeric">CHANNEL</div>
            <div className="grid grid-cols-4 gap-1.5">
              {CHANNELS.map(c => {
                const Icon = c.icon;
                const active = channel === c.id;
                return (
                  <button key={c.id} onClick={() => setChannel(c.id)} className={`flex flex-col items-center gap-1 py-2.5 rounded-xl text-[10px] font-bold uppercase tracking-[0.1em] border transition-all numeric ${active ? 'bg-[#7C35DC] text-white border-[#7C35DC]' : 'bg-white text-[#5A4A7A] border-[#E8E0F5] hover:border-[#7C35DC]/40'}`} data-testid={`reply-channel-${c.id}`}>
                    <Icon size={15} weight="fill" />{c.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Tone */}
          <div>
            <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#9B8AB0] mb-2 numeric">TONE</div>
            <div className="flex flex-wrap gap-1.5">
              {TONES.map(t => {
                const active = tone === t.id;
                return (
                  <button key={t.id} onClick={() => setTone(t.id)} className={`px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-[0.12em] border transition-all numeric ${active ? 'bg-[#7C35DC] text-white border-[#7C35DC]' : 'bg-white text-[#5A4A7A] border-[#E8E0F5] hover:border-[#7C35DC]/40'}`} data-testid={`reply-tone-${t.id}`}>
                    {t.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Reply */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#7C35DC] numeric">ARIA'S DRAFT</div>
              <button onClick={generate} disabled={loading} className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-[0.15em] text-[#7C35DC] hover:underline disabled:opacity-50 numeric" data-testid="reply-regenerate">
                <ArrowClockwise size={11} weight="bold" className={loading ? 'animate-spin' : ''} /> {loading ? 'Writing…' : 'Regenerate'}
              </button>
            </div>
            <textarea value={reply} onChange={(e) => { setReply(e.target.value); setEdited(true); }} rows={7}
              className="w-full bg-white border border-[#E8E0F5] rounded-xl px-4 py-3 text-sm text-[#1A0A2E] font-display-italic leading-relaxed focus:border-[#7C35DC] focus:ring-2 focus:ring-[#7C35DC]/15 outline-none transition resize-y"
              placeholder={loading ? 'ARIA is writing your reply…' : 'ARIA will draft a reply here.'}
              data-testid="reply-textarea" />
            {edited && <div className="text-[10px] text-[#9B8AB0] mt-1 font-display-italic">Edited from ARIA's draft</div>}
          </div>

          {/* Optional user note */}
          <details className="group">
            <summary className="cursor-pointer text-[10px] font-bold uppercase tracking-[0.2em] text-[#9B8AB0] hover:text-[#7C35DC] numeric select-none">ADD CONTEXT FOR ARIA</summary>
            <textarea value={userNote} onChange={(e) => setUserNote(e.target.value)} rows={2}
              className="w-full mt-2 bg-white border border-[#E8E0F5] rounded-xl px-4 py-2.5 text-sm text-[#1A0A2E] focus:border-[#7C35DC] focus:ring-2 focus:ring-[#7C35DC]/15 outline-none transition resize-y"
              placeholder="e.g. Mention we can do a pilot without a contract." data-testid="reply-user-note" />
          </details>
        </div>

        {/* Actions */}
        <div className="sticky bottom-0 px-6 py-4 bg-white border-t border-[#F0ECF9] flex flex-wrap gap-2">
          <button onClick={copyReply} disabled={!reply || loading} className="flex-1 min-w-[120px] flex items-center justify-center gap-2 py-3 rounded-xl bg-white border border-[#E8E0F5] text-[#5A4A7A] hover:bg-[#F4F0FF] hover:text-[#7C35DC] hover:border-[#7C35DC]/30 text-[10px] font-extrabold uppercase tracking-[0.18em] disabled:opacity-50 numeric" data-testid="reply-copy">
            {copied ? <CheckCircle size={12} weight="fill" /> : <Copy size={12} weight="fill" />}{copied ? 'Copied' : 'Copy'}
          </button>
          <button disabled={!reply || loading} className="flex-1 min-w-[160px] flex items-center justify-center gap-2 btn-gradient py-3 rounded-xl text-[10px] font-extrabold uppercase tracking-[0.2em] disabled:opacity-50 numeric" data-testid="reply-send">
            <PaperPlaneTilt size={12} weight="fill" /> Send on {channel === 'whatsapp' ? 'WhatsApp' : channel === 'email' ? 'Email' : channel === 'linkedin' ? 'LinkedIn' : 'Call'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default AskAriaReplyModal;
